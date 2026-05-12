"""Request Buffer with Backpressure — Token中转站削峰填谷。

Design (#6): 请求缓冲队列 + 背压反馈。

Scenario: "双十一"流量洪峰 → 瞬时45000 QPS → buffer排队 → 削峰填谷。
When queue fills up to 80%: signal "slow down" to upstream (429 with Retry-After).
When queue reaches 95%: reject new requests (503).

Three-tier architecture:
  L1: Immediate — fast path for cache hits / health checks (no queueing)
  L2: Buffer — normal chat requests, FIFO queue, max 1000 pending
  L3: Reject — queue full → 503 Service Unavailable

Integration:
  api/routes.py chat_stream endpoint:
    buffer.enqueue(request_id) → wait → dequeue → process → done
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class BufferSlot:
    """A single buffered request."""
    request_id: str
    enqueued_at: float = field(default_factory=time.time)
    priority: int = 0       # Lower = higher priority
    context: dict = field(default_factory=dict)


@dataclass
class BufferStats:
    """Real-time buffer statistics."""
    queue_depth: int = 0
    max_depth: int = 0
    total_enqueued: int = 0
    total_dequeued: int = 0
    total_rejected: int = 0
    avg_wait_ms: float = 0.0
    current_pressure: float = 0.0  # 0.0 (idle) to 1.0 (full)


class RequestBuffer:
    """FIFO request buffer with backpressure signaling.

    Attributes:
        max_queue: Maximum pending requests before rejection (default 1000).
        high_watermark: Queue depth ratio to start backpressure (default 0.80).
        critical_watermark: Queue depth ratio to reject (default 0.95).
        max_wait_seconds: Max time a request can wait in queue (default 60).
    """

    def __init__(
        self,
        max_queue: int = 1000,
        high_watermark: float = 0.80,
        critical_watermark: float = 0.95,
        max_wait_seconds: float = 60.0,
    ):
        self.max_queue = max_queue
        self.high_watermark = high_watermark
        self.critical_watermark = critical_watermark
        self.max_wait_seconds = max_wait_seconds
        self._queue: deque[BufferSlot] = deque()
        self._events: dict[str, asyncio.Event] = {}
        self._stats = BufferStats()
        self._lock = asyncio.Lock()

    async def enqueue(self, request_id: str, priority: int = 0) -> bool:
        """Try to enqueue a request. Returns False if rejected (queue full).

        Backpressure: when queue > high_watermark, logs warning.
        When queue > critical_watermark, rejects with False.
        """
        async with self._lock:
            depth = len(self._queue)
            ratio = depth / self.max_queue if self.max_queue > 0 else 0

            # Critical: reject
            if ratio >= self.critical_watermark:
                self._stats.total_rejected += 1
                logger.warning(
                    f"RequestBuffer: REJECT {request_id} "
                    f"(queue {depth}/{self.max_queue}, {ratio:.0%})"
                )
                return False

            # High: backpressure signal
            if ratio >= self.high_watermark:
                logger.debug(
                    f"RequestBuffer: BACKPRESSURE {request_id} "
                    f"(queue {depth}/{self.max_queue}, {ratio:.0%})"
                )

            slot = BufferSlot(request_id=request_id, priority=priority)
            self._queue.append(slot)
            self._stats.total_enqueued += 1
            self._stats.queue_depth = len(self._queue)
            self._stats.max_depth = max(self._stats.max_depth, len(self._queue))
            self._stats.current_pressure = ratio

            # Create event for this request
            self._events[request_id] = asyncio.Event()

        return True

    async def dequeue(self, timeout: float = None) -> Optional[str]:
        """Wait for and return next request ID from queue.

        Args:
            timeout: Max seconds to wait. None = wait forever.

        Returns:
            request_id or None if timed out.
        """
        deadline = (time.time() + timeout) if timeout else None

        while True:
            async with self._lock:
                if self._queue:
                    slot = self._queue.popleft()
                    self._stats.total_dequeued += 1
                    self._stats.queue_depth = len(self._queue)
                    self._stats.current_pressure = (
                        len(self._queue) / self.max_queue
                        if self.max_queue > 0 else 0
                    )

                    # Calculate wait time
                    wait_ms = (time.time() - slot.enqueued_at) * 1000
                    # Exponential moving average
                    alpha = 0.1
                    self._stats.avg_wait_ms = (
                        (1 - alpha) * self._stats.avg_wait_ms + alpha * wait_ms
                    )

                    # Signal the waiting coroutine
                    event = self._events.pop(slot.request_id, None)
                    if event:
                        event.set()  # Don't await — fire and forget

                    return slot.request_id

            # No request available yet
            if deadline and time.time() >= deadline:
                return None
            await asyncio.sleep(0.05)  # Poll interval

    async def wait_for_turn(self, request_id: str, timeout: float = 30.0) -> bool:
        """Wait until this request reaches the front of the queue.

        Returns True when it's this request's turn, False on timeout.
        """
        event = self._events.get(request_id)
        if not event:
            return True  # Not in queue, proceed

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            logger.warning(f"RequestBuffer: TIMEOUT {request_id}")
            return False

    def needs_backpressure(self) -> bool:
        """Check if upstream should be signaled to slow down."""
        ratio = len(self._queue) / max(1, self.max_queue)
        return ratio >= self.high_watermark

    def retry_after_header(self) -> Optional[int]:
        """Suggested Retry-After header value in seconds."""
        if not self.needs_backpressure():
            return None
        # Estimate: queue_depth / throughput_rate
        rate = max(1, self._stats.total_dequeued)
        wait = len(self._queue) / rate * 10  # rough estimate
        return max(1, int(wait))

    @property
    def stats(self) -> BufferStats:
        return self._stats


# ── Singleton ──

_buffer: Optional[RequestBuffer] = None


def get_request_buffer() -> RequestBuffer:
    global _buffer
    if _buffer is None:
        _buffer = RequestBuffer()
    return _buffer
