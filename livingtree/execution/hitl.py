"""HITL — Human-in-the-Loop pause/resume for task execution.

Inspired by Hive's intervention nodes: pauses execution at critical
decision points, waits for human input, then resumes.

Integrated directly into LifeEngine.execute() — no separate layer.

Usage:
    hitl = HumanInTheLoop()
    task = {"name": "deploy", "action": "deploy", "needs_approval": True}
    approved = await hitl.request_approval(task, "Production deployment?")
    if approved: execute(task)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from loguru import logger


@dataclass
class ApprovalRequest:
    """A pending approval request waiting for human decision."""
    id: str
    task_name: str
    question: str
    context: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    created: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved: Optional[str] = None
    response: Optional[str] = None
    timeout_seconds: float = 300.0
    _future: Optional[asyncio.Future] = field(default=None, repr=False)


class HumanInTheLoop:
    """Pause-and-wait approval system for critical task steps.

    Tasks with needs_approval=True trigger a pause. The system
    waits for approve() or deny() before proceeding.
    """

    def __init__(self, default_timeout: float = 300.0):
        self._pending: dict[str, ApprovalRequest] = {}
        self._lock = asyncio.Lock()
        self._default_timeout = default_timeout
        self._on_approval_requested: list[Callable] = []

    def on_request(self, callback: Callable) -> None:
        """Register a callback(ApprovalRequest) when approval is requested."""
        self._on_approval_requested.append(callback)

    async def request_approval(self, task_name: str, question: str,
                                context: dict[str, Any] | None = None,
                                timeout: float | None = None) -> bool:
        """Request human approval for a task step.

        Pauses execution until approve() or deny() is called,
        or timeout expires. Returns True if approved, False if denied/timed out.
        """
        import uuid
        req_id = uuid.uuid4().hex[:8]
        future: asyncio.Future = asyncio.get_event_loop().create_future()

        request = ApprovalRequest(
            id=req_id,
            task_name=task_name,
            question=question,
            context=context or {},
            timeout_seconds=timeout or self._default_timeout,
            _future=future,
        )

        async with self._lock:
            self._pending[req_id] = request

        logger.info(f"[HITL] Approval requested: {task_name} — {question[:80]}")

        for cb in self._on_approval_requested:
            try:
                cb(request)
            except Exception:
                pass

        try:
            result = await asyncio.wait_for(future, timeout=request.timeout_seconds)
            request.status = "approved" if result else "denied"
            request.resolved = datetime.now(timezone.utc).isoformat()
            return result
        except asyncio.TimeoutError:
            request.status = "timeout"
            request.resolved = datetime.now(timezone.utc).isoformat()
            return False
        finally:
            async with self._lock:
                self._pending.pop(req_id, None)

    def approve(self, request_id: str, response: str = "") -> bool:
        """Approve a pending request."""
        request = self._pending.get(request_id)
        if request and request._future and not request._future.done():
            request.response = response
            request._future.set_result(True)
            return True
        return False

    def deny(self, request_id: str, reason: str = "") -> bool:
        """Deny a pending request."""
        request = self._pending.get(request_id)
        if request and request._future and not request._future.done():
            request.response = reason
            request._future.set_result(False)
            return True
        return False

    def get_pending(self) -> list[ApprovalRequest]:
        return [r for r in self._pending.values() if r.status == "pending"]

    def pending_count(self) -> int:
        return len([r for r in self._pending.values() if r.status == "pending"])

    def purge(self) -> int:
        """Cancel all pending requests. Returns count cancelled."""
        count = 0
        for r in self._pending.values():
            if r._future and not r._future.done():
                r._future.set_result(False)
                count += 1
        self._pending.clear()
        return count
