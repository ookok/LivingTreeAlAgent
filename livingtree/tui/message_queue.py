"""MessageQueue — prioritized render queue with backpressure for Toad.

    Replaces the ad-hoc _post_lock + ask_queue + asyncio.create_task chaos
    with a single coordinated pipeline:

    1. Priority ordering: system > tool_result > chat_fragment
    2. Rate limiting: max 20 messages/sec (token bucket, 50ms refill)
    3. Backpressure: queue > 50 → upstream slowed (asyncio.sleep)
    4. Cancel propagation: flush() discards pending, sends cancel to producer
    5. Cross-type ordering: guarantees ToolCall renders before its fragments

    Usage in Conversation:
        self._mq = MessageQueue()
        await self._mq.enqueue("chat_fragment", callback, priority=3)
        await self._mq.flush()  # on cancel

    Usage in NeonAgent:
        await mq.throttle()  # called before each token post — blocks if queue full
"""
from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable

from loguru import logger


@dataclass
class QueuedMessage:
    priority: int                         # 1(highest) to 5(lowest)
    msg_type: str                         # system, tool_call, tool_result, chat_fragment, thinking
    callback: Callable                    # async callable to execute
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    enqueued_at: float = 0.0
    seq: int = 0                          # monotonic sequence for FIFO within priority

    def __lt__(self, other):
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.seq < other.seq


PRIORITY_MAP = {
    "system": 1,           # Session updates, mode changes
    "tool_call": 2,        # Tool call display (user needs to see what's happening)
    "tool_result": 2,      # Tool results
    "thinking": 3,         # Agent thoughts (collapsible)
    "chat_fragment": 4,    # Streaming response text
    "status": 5,           # Status bar updates (lowest)
}


class MessageQueue:
    """Prioritized message render queue with rate limiting and backpressure."""

    # Rate limiting: token bucket
    MAX_RATE = 20             # max messages per second
    REFILL_INTERVAL = 0.050   # 50ms between tokens
    MAX_BURST = 5             # allow burst of 5 messages instantly

    # Backpressure thresholds
    SOFT_LIMIT = 30           # start slowing upstream
    HARD_LIMIT = 50           # block upstream until queue drains below this

    def __init__(self):
        self._queue: list[QueuedMessage] = []
        self._seq = 0
        self._tokens = float(self.MAX_BURST)
        self._last_refill = time.monotonic()
        self._draining = False
        self._drain_task: asyncio.Task | None = None
        self._cancelled = False
        self._on_flush_callbacks: list[Callable] = []

        # Stats
        self._enqueued = 0
        self._delivered = 0
        self._dropped = 0

    def enqueue(
        self,
        msg_type: str,
        callback: Callable,
        *args,
        priority: int | None = None,
        **kwargs,
    ):
        """Enqueue a message for rendering.

        Args:
            msg_type: Type string (see PRIORITY_MAP)
            callback: Async callable that renders the message
            priority: Override priority (1-5). Uses PRIORITY_MAP if None.
        """
        if self._cancelled:
            return

        self._seq += 1
        p = priority if priority is not None else PRIORITY_MAP.get(msg_type, 4)
        qm = QueuedMessage(
            priority=p, msg_type=msg_type, callback=callback,
            args=args, kwargs=kwargs, enqueued_at=time.monotonic(),
            seq=self._seq,
        )
        self._queue.append(qm)
        self._queue.sort()
        self._enqueued += 1

        # Start drainer if not running
        if not self._draining:
            self._draining = True
            self._cancelled = False
            self._drain_task = asyncio.create_task(self._drain())

    async def throttle(self):
        """Call before posting a new fragment. Blocks if queue is full.

        This provides backpressure — upstream producers wait until render
        pipeline has capacity.
        """
        while len(self._queue) >= self.HARD_LIMIT and not self._cancelled:
            await asyncio.sleep(0.05)

        if len(self._queue) >= self.SOFT_LIMIT:
            await asyncio.sleep(0.01)

    def on_flush(self, callback: Callable):
        """Register a callback to be called when queue is flushed/cancelled."""
        self._on_flush_callbacks.append(callback)

    async def flush(self):
        """Cancel all pending messages. Notify callbacks. Stop drainer."""
        self._cancelled = True
        self._dropped += len(self._queue)
        self._queue.clear()
        self._draining = False

        if self._drain_task and not self._drain_task.done():
            self._drain_task.cancel()
            try:
                await self._drain_task
            except asyncio.CancelledError:
                pass

        for cb in self._on_flush_callbacks:
            try:
                cb()
            except Exception:
                pass
        self._on_flush_callbacks.clear()

    async def _drain(self):
        """Main drain loop. Executes queued messages with rate limiting."""
        while self._queue and not self._cancelled:
            await self._acquire_token()

            if self._cancelled:
                break

            qm = self._queue.pop(0)
            try:
                result = qm.callback(*qm.args, **qm.kwargs)
                if asyncio.iscoroutine(result):
                    await result
                self._delivered += 1
            except Exception as e:
                logger.debug(f"MessageQueue drain: {e}")
                self._dropped += 1

        self._draining = False

    async def _acquire_token(self):
        """Token bucket rate limiter. Blocks until a token is available."""
        while True:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._last_refill = now

            # Refill tokens
            self._tokens = min(
                float(self.MAX_BURST),
                self._tokens + elapsed / self.REFILL_INTERVAL,
            )

            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return

            # Not enough tokens — wait
            await asyncio.sleep(self.REFILL_INTERVAL)

    @property
    def queue_size(self) -> int:
        return len(self._queue)

    @property
    def is_backpressured(self) -> bool:
        return len(self._queue) >= self.SOFT_LIMIT

    def stats(self) -> dict[str, Any]:
        return {
            "queue_size": len(self._queue),
            "enqueued_total": self._enqueued,
            "delivered_total": self._delivered,
            "dropped_total": self._dropped,
            "backpressured": self.is_backpressured,
            "cancelled": self._cancelled,
        }
