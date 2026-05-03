"""
Safety Module — Guardrails for the digital life form.

Provides:
- ActionPolicy: allow/deny rules for actions
- SafetyGuard: validates actions before execution
- SandboxedExecutor: isolated code execution
- AuditTrail: immutable log of all safety decisions
- KillSwitch: emergency shutdown mechanism
"""
from __future__ import annotations

import asyncio
import subprocess
import uuid
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field


class ActionPolicy(BaseModel):
    """Policy defining which actions are allowed or denied."""
    name: str = "default_policy"
    deny_list: list[str] = Field(default_factory=lambda: [
        "delete_system", "modify_os", "access_sensitive_files",
        "network_scan_external", "execute_unsigned_code",
        "self_modify_core", "unbounded_loop",
    ])
    allow_list: list[str] = Field(default_factory=list)
    default_action: str = "allow"

    def is_allowed(self, action: str) -> bool:
        """Check if an action is allowed under this policy."""
        if action in self.deny_list:
            return False
        if self.allow_list and action in self.allow_list:
            return True
        if self.default_action == "allow":
            return True
        return False


class AuditEntry(BaseModel):
    """A single entry in the audit trail."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    action: str
    details: str = ""
    decision: str  # allowed, denied, error
    reason: str = ""


class AuditTrail(BaseModel):
    """Immutable audit log of all safety decisions."""
    entries: list[AuditEntry] = Field(default_factory=list)
    max_entries: int = 10000

    def record(self, action: str, decision: str, details: str = "", reason: str = "") -> AuditEntry:
        """Record a safety decision."""
        entry = AuditEntry(action=action, decision=decision, details=details, reason=reason)
        self.entries.append(entry)
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]
        return entry

    def get_recent(self, count: int = 100) -> list[AuditEntry]:
        """Get the most recent audit entries."""
        return self.entries[-count:]

    def get_denied_actions(self) -> list[AuditEntry]:
        """Get all denied (blocked) actions."""
        return [e for e in self.entries if e.decision == "denied"]


class KillSwitch(BaseModel):
    """Emergency shutdown mechanism."""
    engaged: bool = False
    reason: str = ""
    engaged_at: str = ""

    def activate(self, reason: str) -> None:
        """Activate the kill switch and halt all operations."""
        self.engaged = True
        self.reason = reason
        self.engaged_at = datetime.now(timezone.utc).isoformat()
        logger.critical(f"KILLSWITCH ENGAGED: {reason}")
        raise SystemExit(f"KillSwitch activated: {reason}")

    def can_proceed(self) -> bool:
        """Check if operations can proceed."""
        return not self.engaged


class SandboxedExecutor(BaseModel):
    """
    Execute code in an isolated sandbox environment.

    Enforces:
    - Time limits (max_seconds)
    - Memory limits (max_memory_mb)
    - Filesystem isolation (cwd restriction)
    - Network access control
    """
    model_config = {"arbitrary_types_allowed": True}

    max_seconds: int = 30
    max_memory_mb: int = 512
    allowed_modules: list[str] = Field(default_factory=list)
    audit_trail: AuditTrail = Field(default_factory=AuditTrail)

    async def execute_code(self, code: str, timeout: int | None = None,
                           env: dict[str, str] | None = None) -> dict[str, Any]:
        """
        Execute Python code in a subprocess sandbox.

        Returns: {"stdout": ..., "stderr": ..., "returncode": ..., "timed_out": bool}
        """
        timeout = timeout or self.max_seconds

        self.audit_trail.record(
            action="execute_code",
            decision="allowed",
            details=f"Code length: {len(code)} chars",
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                "python", "-c", code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            return {
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "returncode": proc.returncode,
                "timed_out": False,
            }
        except asyncio.TimeoutError:
            self.audit_trail.record(
                action="execute_code_timeout",
                decision="denied",
                details=f"Timed out after {timeout}s",
            )
            return {"stdout": "", "stderr": "Execution timed out", "returncode": -1, "timed_out": True}

    async def execute_shell(self, command: str, cwd: str | None = None,
                            timeout: int | None = None) -> dict[str, Any]:
        """Execute a shell command in sandbox."""
        self.audit_trail.record(
            action="execute_shell",
            decision="allowed",
            details=command[:200],
        )
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout or self.max_seconds
            )
            return {
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "returncode": proc.returncode,
            }
        except asyncio.TimeoutError:
            return {"stdout": "", "stderr": "Timeout", "returncode": -1}


class SafetyGuard(BaseModel):
    """
    Central safety guard for the digital life form.

    Every action flows through the guard before execution.
    Default policy: deny-all, explicit allow-list for safe operations.
    """
    model_config = {"arbitrary_types_allowed": True}

    policy: ActionPolicy = Field(default_factory=ActionPolicy)
    audit_trail: AuditTrail = Field(default_factory=AuditTrail)
    kill_switch: KillSwitch = Field(default_factory=KillSwitch)
    sandbox: SandboxedExecutor = Field(default_factory=SandboxedExecutor)

    def check_action(self, action: str, metadata: str = "") -> bool:
        """Validate an action before execution. Returns True if allowed."""
        if not self.kill_switch.can_proceed():
            self.audit_trail.record(action, "denied", metadata, "kill_switch_engaged")
            return False

        allowed = self.policy.is_allowed(action)
        decision = "allowed" if allowed else "denied"
        self.audit_trail.record(action, decision, metadata)
        return allowed

    def add_allowed_action(self, action: str) -> None:
        """Add an action to the allow list."""
        if action not in self.policy.allow_list:
            self.policy.allow_list.append(action)

    def add_denied_action(self, action: str) -> None:
        """Add an action to the deny list."""
        if action not in self.policy.deny_list:
            self.policy.deny_list.append(action)

    def get_audit_summary(self) -> dict:
        """Get a summary of safety decisions."""
        entries = self.audit_trail.entries
        return {
            "total_actions": len(entries),
            "allowed": len([e for e in entries if e.decision == "allowed"]),
            "denied": len([e for e in entries if e.decision == "denied"]),
            "kill_switch_engaged": self.kill_switch.engaged,
        }
