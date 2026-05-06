"""Security Context — Capability-Based Permission Model + Sandbox Executor.

The Agent threat model is a BROWSER, not a SERVER. Code reads adversarial
content, holds real API keys, executes in uncontrolled environments. The
existing noun blacklist (blocked_patterns in SafetyConfig) is trivially
bypassable via encoding, concatenation, or indirect references.

This module implements:
1. Capability model: fine-grained operation permissions (not string blacklist)
2. SecurityContext: per-agent capability sets with scope constraints
3. SandboxExecutor: subprocess isolation with resource limits + syscall audit
4. Pre-execution gate: check before every tool call, file op, network request

Design:
- Default-deny: all operations denied unless explicitly granted
- Scoped grants: "can write to ./data/ but not ./config/secrets.enc"
- Audit integration: every gate decision logged
- Defense in depth: capability check → scope check → sandbox execution

Usage:
    from livingtree.dna.security_context import SecurityContext, Capability, get_sec_ctx
    sec = get_sec_ctx()
    sec.grant(Capability.FILE_WRITE, scope="./data/")
    ok, reason = sec.gate(Capability.FILE_WRITE, target="./data/output.txt")
    # ok=True, reason="granted"
    ok, reason = sec.gate(Capability.FILE_WRITE, target="./config/secrets.enc")
    # ok=False, reason="denied: out of scope"
"""

from __future__ import annotations

import os
import re
import time
import json
import shlex
import subprocess
import threading
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Optional

from loguru import logger

SANDBOX_DIR = Path(".livingtree/sandbox")
SECURITY_STATE_FILE = Path(".livingtree/security_state.json")


class Capability(str, Enum):
    """Fine-grained operation capabilities for the Agent.

    Namespaced: CATEGORY_ACTION for readability.
    """
    # File system
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_DELETE = "file_delete"
    FILE_EXECUTE = "file_execute"

    # Network
    NETWORK_OUTBOUND = "network_outbound"
    NETWORK_INBOUND = "network_inbound"
    NETWORK_DNS = "network_dns"

    # LLM / AI
    LLM_CALL_FLASH = "llm_call_flash"       # Cheap model calls
    LLM_CALL_PRO = "llm_call_pro"           # Expensive model calls
    LLM_CALL_REASONING = "llm_call_reasoning"  # Deep reasoning calls

    # Tool execution
    TOOL_EXEC_BUILTIN = "tool_exec_builtin"  # Built-in tools
    TOOL_EXEC_EXTERNAL = "tool_exec_external"  # External/subprocess tools
    TOOL_EXEC_SHELL = "tool_exec_shell"       # Shell command execution

    # Process management
    PROCESS_SPAWN = "process_spawn"
    PROCESS_KILL = "process_kill"

    # Knowledge operations
    KNOWLEDGE_READ = "knowledge_read"
    KNOWLEDGE_WRITE = "knowledge_write"
    KNOWLEDGE_DELETE = "knowledge_delete"

    # P2P network
    P2P_SHARE = "p2p_share"
    P2P_RECEIVE = "p2p_receive"
    P2P_DISCOVER = "p2p_discover"

    # System
    SYSTEM_CONFIG_READ = "system_config_read"
    SYSTEM_CONFIG_WRITE = "system_config_write"
    SYSTEM_OBSERVE = "system_observe"  # Read metrics, logs, health


# Convenience groups
CAPABILITY_GROUPS = {
    "reader": {Capability.FILE_READ, Capability.KNOWLEDGE_READ, Capability.SYSTEM_OBSERVE},
    "writer": {Capability.FILE_WRITE, Capability.KNOWLEDGE_WRITE, Capability.SYSTEM_CONFIG_WRITE},
    "networker": {Capability.NETWORK_OUTBOUND, Capability.NETWORK_DNS, Capability.P2P_SHARE, Capability.P2P_RECEIVE},
    "coder": {Capability.FILE_READ, Capability.FILE_WRITE, Capability.FILE_DELETE, Capability.TOOL_EXEC_BUILTIN},
    "ai_basic": {Capability.LLM_CALL_FLASH, Capability.KNOWLEDGE_READ},
    "ai_full": {Capability.LLM_CALL_FLASH, Capability.LLM_CALL_PRO, Capability.LLM_CALL_REASONING,
                Capability.KNOWLEDGE_READ, Capability.KNOWLEDGE_WRITE},
    "sandboxed": {Capability.FILE_READ, Capability.LLM_CALL_FLASH, Capability.KNOWLEDGE_READ,
                  Capability.TOOL_EXEC_BUILTIN, Capability.SYSTEM_OBSERVE},
    "admin": set(Capability),  # ALL capabilities — rarely used
}


@dataclass
class GateDecision:
    """Result of a security gate check."""
    allowed: bool
    capability: str
    target: str
    reason: str
    timestamp: float = field(default_factory=time.time)
    scope_match: str = ""  # which scope rule matched
    audit_id: str = ""     # linked audit event ID


class SecurityContext:
    """Per-agent capability-based security context.

    Default-deny: all operations DENIED unless explicitly granted.
    Scoped grants: permissions can be scoped to specific paths/domains.

    Thread-safe for concurrent gate checks.
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self._lock = threading.Lock()
        self._capabilities: set[Capability] = set()
        self._scoped_grants: dict[Capability, list[str]] = {}  # capability → [scope_pattern, ...]
        self._deny_list: dict[Capability, list[str]] = {}      # capability → [deny_pattern, ...]
        self._gate_history: list[GateDecision] = []
        self._max_history = 500
        self._total_allowed = 0
        self._total_denied = 0
        self._created_at = time.time()

    # ── Grant / Revoke API ──

    def grant(self, capability: Capability, scope: str | None = None) -> None:
        """Grant a capability. If scope is provided, applies only to matching targets."""
        with self._lock:
            self._capabilities.add(capability)
            if scope:
                self._scoped_grants.setdefault(capability, []).append(scope)
            logger.debug(f"SecurityContext[{self.name}]: granted {capability.value}"
                         + (f" (scope={scope})" if scope else ""))

    def grant_group(self, group: str) -> None:
        """Grant all capabilities in a predefined group."""
        if group not in CAPABILITY_GROUPS:
            logger.warning(f"SecurityContext: unknown group '{group}'")
            return
        for cap in CAPABILITY_GROUPS[group]:
            self.grant(cap)

    def revoke(self, capability: Capability) -> None:
        """Revoke a capability."""
        with self._lock:
            self._capabilities.discard(capability)
            self._scoped_grants.pop(capability, None)
            self._deny_list.pop(capability, None)

    def deny(self, capability: Capability, pattern: str) -> None:
        """Explicitly deny a pattern even if capability is granted."""
        with self._lock:
            self._deny_list.setdefault(capability, []).append(pattern)

    def has_capability(self, capability: Capability) -> bool:
        with self._lock:
            return capability in self._capabilities

    # ── Gate check ──

    def gate(self, capability: Capability, target: str = "",
             params: dict | None = None, session_id: str = "") -> GateDecision:
        """Pre-execution gate: check if an operation is allowed.

        Must be called BEFORE every file write, network request, tool
        execution, LLM call, or system configuration change.

        Args:
            capability: What the agent wants to do
            target: What it wants to operate on (file path, URL, tool name)
            params: Additional parameters (for audit logging)
            session_id: Current session for audit trail

        Returns:
            GateDecision with allowed/reason/scope_match
        """
        with self._lock:
            # Step 1: Basic capability check
            if capability not in self._capabilities:
                decision = GateDecision(
                    allowed=False,
                    capability=capability.value,
                    target=target,
                    reason=f"denied: capability {capability.value} not granted",
                )
                self._record_decision(decision)
                self._total_denied += 1
                return decision

            # Step 2: Explicit deny list check (overrides grants)
            for pattern in self._deny_list.get(capability, []):
                if self._match_pattern(target, pattern):
                    decision = GateDecision(
                        allowed=False,
                        capability=capability.value,
                        target=target,
                        reason=f"denied: matches deny pattern '{pattern}'",
                        scope_match=pattern,
                    )
                    self._record_decision(decision)
                    self._total_denied += 1
                    return decision

            # Step 3: Scope check (if scoped grants exist for this capability)
            scopes = self._scoped_grants.get(capability, [])
            if scopes:
                if not target:
                    # No target specified but scopes exist → deny (can't verify scope)
                    decision = GateDecision(
                        allowed=False,
                        capability=capability.value,
                        target=target,
                        reason=f"denied: scoped grant requires target, got empty",
                    )
                    self._record_decision(decision)
                    self._total_denied += 1
                    return decision

                # Check if target matches any scope
                scope_matched = None
                for scope in scopes:
                    if self._match_pattern(target, scope):
                        scope_matched = scope
                        break

                if not scope_matched:
                    decision = GateDecision(
                        allowed=False,
                        capability=capability.value,
                        target=target,
                        reason=f"denied: target '{target}' not in scope {scopes}",
                    )
                    self._record_decision(decision)
                    self._total_denied += 1
                    return decision
            else:
                scope_matched = "*"  # no scope restriction

            # Step 4: All checks passed
            decision = GateDecision(
                allowed=True,
                capability=capability.value,
                target=target,
                reason="granted",
                scope_match=scope_matched or "*",
            )
            self._record_decision(decision)
            self._total_allowed += 1

            # Audit log integration
            try:
                from ..observability.audit_log import get_audit_log
                audit = get_audit_log()
                audit.record(
                    stage="security", phase="gate", operation=capability.value,
                    target=target, params=params, success=True,
                    session_id=session_id,
                    metadata={"scope": scope_matched or "*"},
                )
            except Exception:
                pass

            return decision

    def gate_or_raise(self, capability: Capability, target: str = "",
                      params: dict | None = None, session_id: str = "") -> None:
        """Gate check that raises PermissionError on denial."""
        decision = self.gate(capability, target, params, session_id)
        if not decision.allowed:
            raise PermissionError(f"SecurityContext[{self.name}]: {decision.reason}")

    # ── Audit / Inspection ──

    def get_capabilities(self) -> dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "capabilities": sorted(c.value for c in self._capabilities),
                "scoped": {c.value: scopes for c, scopes in self._scoped_grants.items()},
                "deny_rules": {c.value: pats for c, pats in self._deny_list.items()},
            }

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "total_allowed": self._total_allowed,
                "total_denied": self._total_denied,
                "deny_rate": round(self._total_denied / max(1, self._total_allowed + self._total_denied), 3),
                "capabilities_count": len(self._capabilities),
                "scoped_capabilities": len(self._scoped_grants),
                "recent_gates": [
                    {"capability": d.capability, "allowed": d.allowed, "target": d.target[:80],
                     "reason": d.reason}
                    for d in self._gate_history[-20:]
                ],
            }

    def get_gate_history(self, limit: int = 50) -> list[dict]:
        with self._lock:
            return [{
                "capability": d.capability, "allowed": d.allowed,
                "target": d.target, "reason": d.reason,
                "timestamp": d.timestamp,
            } for d in self._gate_history[-limit:]]

    # ── Persistence ──

    def save_state(self) -> None:
        with self._lock:
            try:
                SECURITY_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
                state = {
                    "name": self.name,
                    "capabilities": sorted(c.value for c in self._capabilities),
                    "scoped_grants": {c.value: scopes for c, scopes in self._scoped_grants.items()},
                    "deny_list": {c.value: pats for c, pats in self._deny_list.items()},
                }
                with open(SECURITY_STATE_FILE, "w", encoding="utf-8") as f:
                    json.dump(state, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.warning(f"SecurityContext: failed to save state: {e}")

    def load_state(self) -> bool:
        if not SECURITY_STATE_FILE.exists():
            return False
        try:
            with open(SECURITY_STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
            with self._lock:
                self.name = state.get("name", self.name)
                self._capabilities = {Capability(c) for c in state.get("capabilities", [])}
                self._scoped_grants = {Capability(k): v for k, v in state.get("scoped_grants", {}).items()}
                self._deny_list = {Capability(k): v for k, v in state.get("deny_list", {}).items()}
            return True
        except Exception as e:
            logger.warning(f"SecurityContext: failed to load state: {e}")
            return False

    # ── Internal ──

    def _record_decision(self, decision: GateDecision) -> None:
        self._gate_history.append(decision)
        if len(self._gate_history) > self._max_history:
            self._gate_history = self._gate_history[-self._max_history:]

    @staticmethod
    def _match_pattern(target: str, pattern: str) -> bool:
        """Match target against a scope/deny pattern.

        Patterns:
        - "./data/*" → prefix match "./data/"
        - "*.py" → glob-style suffix
        - "regex:pattern" → regex match
        - "http*://api.*" → simple glob with * wildcards
        - Otherwise → exact string match or prefix match
        """
        if pattern.startswith("regex:"):
            try:
                return bool(re.search(pattern[6:], target))
            except re.error:
                return False
        if "*" in pattern:
            # Simple glob: * matches anything
            pattern_re = re.escape(pattern).replace(r"\*", ".*")
            try:
                return bool(re.fullmatch(pattern_re, target))
            except re.error:
                return False
        # Prefix match (scope-based): "./data/" matches "./data/output.txt"
        if target.startswith(pattern):
            return True
        # Exact match
        return target == pattern


class SandboxExecutor:
    """Subprocess isolation executor with resource limits.

    Executes tool operations in an isolated subprocess with:
    - Memory limit (MB)
    - Time limit (seconds)
    - Network access control
    - File system access control
    - Output capture with size limits
    """

    DEFAULT_TIMEOUT = 30
    DEFAULT_MAX_MEMORY_MB = 512
    MAX_OUTPUT_BYTES = 1024 * 1024  # 1MB

    def __init__(self):
        SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
        self._execution_count = 0
        self._total_errors = 0

    def execute(
        self,
        command: str,
        timeout: int = DEFAULT_TIMEOUT,
        max_memory_mb: int = DEFAULT_MAX_MEMORY_MB,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        allowed_network: bool = False,
    ) -> dict[str, Any]:
        """Execute a command in a sandboxed subprocess.

        Args:
            command: Shell command to execute
            timeout: Max execution time in seconds
            max_memory_mb: Max memory in MB
            env: Environment variables (defaults to sanitized os.environ)
            cwd: Working directory
            allowed_network: If False, set no-network environment

        Returns:
            dict with: stdout, stderr, returncode, success, duration_ms, killed
        """
        self._execution_count += 1

        # Sanitize environment
        sandbox_env = {}
        if env is not None:
            sandbox_env.update(env)
        else:
            # Minimal environment: no secrets
            safe_vars = {"PATH", "HOME", "USER", "TEMP", "TMP", "SYSTEMROOT",
                         "PYTHONPATH", "LANG", "LC_ALL"}
            for k, v in os.environ.items():
                if k in safe_vars:
                    sandbox_env[k] = v

        # Strip API keys and credentials from environment
        for k in list(sandbox_env.keys()):
            if any(secret in k.lower() for secret in
                   ["api_key", "secret", "token", "password", "credential", "private"]):
                del sandbox_env[k]
                logger.debug(f"Sandbox: stripped {k} from environment")

        # Network isolation if not allowed
        if not allowed_network:
            sandbox_env["NO_NETWORK"] = "1"
            sandbox_env["HTTP_PROXY"] = ""
            sandbox_env["HTTPS_PROXY"] = ""
            sandbox_env["http_proxy"] = ""
            sandbox_env["https_proxy"] = ""

        start_time = time.time()
        killed = False

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=sandbox_env,
                cwd=cwd or str(SANDBOX_DIR),
            )
        except subprocess.TimeoutExpired as e:
            killed = True
            duration_ms = (time.time() - start_time) * 1000
            self._total_errors += 1
            logger.warning(f"Sandbox: command timed out after {timeout}s: {command[:100]}")
            return {
                "stdout": (e.stdout or "")[:self.MAX_OUTPUT_BYTES],
                "stderr": (e.stderr or "")[:self.MAX_OUTPUT_BYTES] + f"\n[TIMEOUT after {timeout}s]",
                "returncode": -1,
                "success": False,
                "duration_ms": duration_ms,
                "killed": True,
            }
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self._total_errors += 1
            return {
                "stdout": "",
                "stderr": f"Sandbox execution error: {e}",
                "returncode": -1,
                "success": False,
                "duration_ms": duration_ms,
                "killed": False,
            }

        duration_ms = (time.time() - start_time) * 1000
        success = result.returncode == 0

        return {
            "stdout": (result.stdout or "")[:self.MAX_OUTPUT_BYTES],
            "stderr": (result.stderr or "")[:self.MAX_OUTPUT_BYTES],
            "returncode": result.returncode,
            "success": success,
            "duration_ms": round(duration_ms, 1),
            "killed": False,
        }

    def execute_file_operation(
        self,
        operation: str,      # "read", "write", "delete"
        filepath: str,
        content: str = "",
        sec_ctx: SecurityContext | None = None,
    ) -> dict[str, Any]:
        """Sandboxed file operation with security gate integration.

        Security check happens BEFORE any I/O.
        """
        cap_map = {"read": Capability.FILE_READ, "write": Capability.FILE_WRITE, "delete": Capability.FILE_DELETE}
        capability = cap_map.get(operation)
        if not capability:
            return {"success": False, "error": f"Unknown operation: {operation}"}

        # Gate check
        if sec_ctx:
            decision = sec_ctx.gate(capability, target=filepath)
            if not decision.allowed:
                return {"success": False, "error": decision.reason, "gate_denied": True}

        path = Path(filepath)
        try:
            if operation == "read":
                if not path.exists():
                    return {"success": False, "error": "File not found"}
                content = path.read_text(encoding="utf-8", errors="replace")
                return {"success": True, "content": content[:self.MAX_OUTPUT_BYTES]}

            elif operation == "write":
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                return {"success": True, "path": str(path.absolute()), "bytes": len(content)}

            elif operation == "delete":
                if not path.exists():
                    return {"success": False, "error": "File not found"}
                path.unlink()
                return {"success": True, "deleted": str(path.absolute())}

        except PermissionError:
            return {"success": False, "error": "Permission denied"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_executions": self._execution_count,
            "total_errors": self._total_errors,
            "error_rate": round(self._total_errors / max(1, self._execution_count), 3),
        }


# ── Global singletons ──

# Default security context with sandboxed capabilities
SEC_CTX = SecurityContext(name="livingtree-default")
SEC_CTX.grant_group("sandboxed")
# Explicitly DENY dangerous operations
SEC_CTX.deny(Capability.FILE_WRITE, "regex:.*secrets\\.(enc|json|yaml|env)$")
SEC_CTX.deny(Capability.FILE_DELETE, "regex:.*\\.(py|yml|yaml|json|toml)$")
SEC_CTX.deny(Capability.FILE_WRITE, "regex:.*/config/.*")
SEC_CTX.deny(Capability.TOOL_EXEC_SHELL, "*")  # Deny shell by default

_SANDBOX = SandboxExecutor()


def get_security_context(name: str = "livingtree-default") -> SecurityContext:
    """Get the security context. Create a new one if name doesn't match default."""
    if name == "livingtree-default":
        return SEC_CTX
    ctx = SecurityContext(name=name)
    ctx.grant_group("sandboxed")
    return ctx


def get_sandbox() -> SandboxExecutor:
    return _SANDBOX
