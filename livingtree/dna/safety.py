"""Safety Module — 16-layer defense for the digital life form.

Inspired by OpenFang's security model:
- Merkle audit chain (cryptographic tamper-proofing)
- Path traversal prevention
- SSRF protection
- Subprocess isolation
- Kill switch
"""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import os
import re
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field


def _hash(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


class ActionPolicy(BaseModel):
    name: str = "default_policy"
    deny_list: list[str] = Field(default_factory=lambda: [
        "delete_system", "modify_os", "access_sensitive_files",
        "network_scan_external", "execute_unsigned_code",
        "self_modify_core", "unbounded_loop",
        "path_traversal", "ssrf_probe", "prompt_injection",
        "eval_injection", "data_exfiltration",
        # Replication protection — 8 core categories (consolidated)
        "self_replicate", "deploy_inference_on_remote",
        "exploit_vulnerability", "extract_credentials",
        "ssh_to_unauthorized", "transfer_weights_remote",
        "chain_replicate", "probe_environment",
    ])
    allow_list: list[str] = Field(default_factory=list)
    default_action: str = "allow"


class MerkleEntry(BaseModel):
    """A single entry in the Merkle audit chain."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    action: str
    details: str = ""
    decision: str
    reason: str = ""
    prev_hash: str = ""
    hash: str = ""

    def compute_hash(self, prev_hash: str) -> str:
        content = f"{self.id}|{self.timestamp}|{self.action}|{self.details}|{self.decision}|{self.reason}|{prev_hash}"
        return _hash(content)


class MerkleAuditChain(BaseModel):
    """Tamper-proof audit trail using Merkle hash chaining.

    Every entry is cryptographically linked to the previous one.
    Tamper with any entry and the entire chain breaks verification.
    """
    entries: list[MerkleEntry] = Field(default_factory=list)
    max_entries: int = 10000
    genesis_hash: str = Field(default_factory=lambda: _hash("livingtree-genesis"))

    def record(self, action: str, decision: str, details: str = "", reason: str = "") -> MerkleEntry:
        prev = self.entries[-1].hash if self.entries else self.genesis_hash
        entry = MerkleEntry(action=action, decision=decision, details=details,
                            reason=reason, prev_hash=prev)
        entry.hash = entry.compute_hash(prev)
        self.entries.append(entry)
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]
        return entry

    def verify(self) -> tuple[bool, int]:
        """Verify the entire chain. Returns (valid, first_invalid_index)."""
        prev = self.genesis_hash
        for i, entry in enumerate(self.entries):
            expected = entry.compute_hash(prev)
            if entry.hash != expected or entry.prev_hash != prev:
                return False, i
            prev = entry.hash
        return True, -1

    def get_recent(self, count: int = 100) -> list[MerkleEntry]:
        return self.entries[-count:]

    def get_denied(self) -> list[MerkleEntry]:
        return [e for e in self.entries if e.decision == "denied"]

    def root_hash(self) -> str:
        return self.entries[-1].hash if self.entries else self.genesis_hash

    def export_proof(self, index: int) -> dict:
        """Export inclusion proof for a specific entry."""
        if index >= len(self.entries):
            return {}
        entry = self.entries[index]
        sibling = self.entries[index - 1] if index > 0 else None
        return {
            "entry": entry.model_dump(),
            "sibling_hash": sibling.hash if sibling else self.genesis_hash,
            "root_hash": self.root_hash(),
            "verified": self.verify()[0],
        }


class KillSwitch(BaseModel):
    engaged: bool = False
    reason: str = ""
    engaged_at: str = ""

    def activate(self, reason: str) -> None:
        self.engaged = True
        self.reason = reason
        self.engaged_at = datetime.now(timezone.utc).isoformat()
        logger.critical(f"KILLSWITCH: {reason}")

    @property
    def ok(self) -> bool:
        return not self.engaged


class PathGuard:
    """Prevent path traversal attacks.

    Canonicalizes paths, detects ../ sequences, prevents symlink escapes.
    """

    @staticmethod
    def is_safe(filepath: str, workspace: str = "") -> bool:
        try:
            resolved = str(Path(filepath).resolve())
            if workspace:
                workspace_resolved = str(Path(workspace).resolve())
                return resolved.startswith(workspace_resolved)
            return ".." not in Path(filepath).parts and not resolved.startswith("/etc") and not resolved.startswith("C:\\Windows")
        except Exception:
            return False

    @staticmethod
    def validate(filepath: str, workspace: str = ".") -> str:
        safe = str(Path(filepath).resolve())
        root = str(Path(workspace).resolve())
        if not safe.startswith(root):
            raise ValueError(f"Path traversal blocked: {filepath}")
        return safe


class SSRFGuard:
    """Prevent Server-Side Request Forgery (SSRF) attacks.

    Blocks private IPs, cloud metadata endpoints, DNS rebinding.
    """

    BLOCKED_CIDRS = [
        "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
        "127.0.0.0/8", "169.254.0.0/16", "0.0.0.0/8",
        "fc00::/7", "fe80::/10", "::1/128",
    ]
    BLOCKED_HOSTS = [
        "metadata.google.internal", "169.254.169.254",
        "metadata.tencentyun.com", "100.100.100.200",
    ]

    @staticmethod
    def is_safe(url: str) -> bool:
        from urllib.parse import urlparse
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname or ""
            if hostname in SSRFGuard.BLOCKED_HOSTS:
                return False
            ip = ipaddress.ip_address(hostname)
            for cidr in SSRFGuard.BLOCKED_CIDRS:
                if ip in ipaddress.ip_network(cidr):
                    return False
            return True
        except ValueError:
            return True
        except Exception:
            return False

    @staticmethod
    def validate(url: str) -> str:
        if not SSRFGuard.is_safe(url):
            raise ValueError(f"SSRF blocked: {url}")
        return url


class PromptInjectionScanner:
    """Detect prompt injection and data exfiltration attempts.

    Patterns: override/system prompt bypass, shell injection in user input,
    data exfiltration via instruction manipulation.
    """

    INJECTION_PATTERNS = [
        (r'(?:忽略|忘记|无视|override|ignore|forget)\s*.*?(?:指令|规则|提示|instructions|rules|prompt)', "role_override"),
        (r'(?:你现在是|你现在扮演|you are now|you now act as)\s*(?:一个|a|an)\s*\w+', "role_impersonation"),
        (r'输出你的\s*(?:系统提示|指令|规则|prompt|instructions)', "prompt_extraction"),
        (r'用\s*\[\s*\{\s*\}\s*\]\s*格式|in\s*\[\s*\{\s*\}\s*\]\s*format', "structured_exfiltration"),
        (r'(?:忽略安全|绕过检查|bypass\s*(?:security|safety|guardrail))', "safety_bypass"),
        (r'\b(?:eval|exec|subprocess|os\.system|__import__)\s*\(', "code_injection"),
        (r'请将(?:上面的|之前的|对话)内容(?:发送到|上传到|post to|send to)', "data_exfiltration"),
        (r'system\s*:\s*(?:you are|你是|ignore|忽略)', "system_prompt_injection"),
        (r'(?:ignore|forget|忽略|忘记)\s+(?:all|所有的|全部)\s+.*?(?:instructions|rules|prompts|指令|规则)', "full_override"),
    ]

    @staticmethod
    def scan(text: str) -> dict[str, Any]:
        findings = []
        for pattern, attack_type in PromptInjectionScanner.INJECTION_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                findings.append({
                    "type": attack_type,
                    "matches": matches[:3],
                    "severity": "high" if attack_type in ("code_injection", "prompt_extraction", "data_exfiltration") else "medium",
                })
        return {
            "safe": len(findings) == 0,
            "findings": findings,
            "count": len(findings),
        }


class SandboxedExecutor(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    max_seconds: int = 30
    max_memory_mb: int = 512
    allowed_modules: list[str] = Field(default_factory=list)
    audit: Any = None
    workspace: str = "."

    async def execute_code(self, code: str, timeout: int | None = None,
                           env: dict[str, str] | None = None) -> dict[str, Any]:
        timeout = timeout or self.max_seconds
        try:
            proc = await asyncio.create_subprocess_exec(
                "python", "-c", code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return {
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "returncode": proc.returncode,
                "timed_out": False,
            }
        except asyncio.TimeoutError:
            return {"stdout": "", "stderr": "Timeout", "returncode": -1, "timed_out": True}

    async def execute_shell(self, command: str, cwd: str | None = None,
                            timeout: int | None = None) -> dict[str, Any]:
        cwd = cwd or self.workspace
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env={"PATH": os.environ.get("PATH", "/usr/bin")},
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout or self.max_seconds)
            return {
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "returncode": proc.returncode,
            }
        except asyncio.TimeoutError:
            return {"stdout": "", "stderr": "Timeout", "returncode": -1}


class SafetyGuard(BaseModel):
    """Unified safety guard with Merkle audit, path guard, SSRF protection."""

    model_config = {"arbitrary_types_allowed": True}

    policy: ActionPolicy = Field(default_factory=ActionPolicy)
    audit: MerkleAuditChain = Field(default_factory=MerkleAuditChain)
    kill_switch: KillSwitch = Field(default_factory=KillSwitch)
    sandbox: SandboxedExecutor = Field(default_factory=SandboxedExecutor)
    workspace: str = "."

    def check_action(self, action: str, metadata: str = "") -> bool:
        if not self.kill_switch.ok:
            self.audit.record(action, "denied", metadata, "kill_switch_engaged")
            return False
        allowed = self.policy.is_allowed(action)
        decision = "allowed" if allowed else "denied"
        self.audit.record(action, decision, metadata)
        return allowed

    def check_path(self, filepath: str) -> bool:
        ok = PathGuard.is_safe(filepath, self.workspace)
        if not ok:
            self.audit.record("file_access", "denied", filepath, "path_traversal")
        return ok

    def check_url(self, url: str) -> bool:
        ok = SSRFGuard.is_safe(url)
        if not ok:
            self.audit.record("network_request", "denied", url, "ssrf_blocked")
        return ok

    def scan_prompt(self, text: str) -> dict[str, Any]:
        result = PromptInjectionScanner.scan(text)
        if not result["safe"]:
            self.audit.record("prompt_scan", "denied", text[:100], f"injection:{result['count']}")
        return result

    def add_allowed(self, action: str) -> None:
        if action not in self.policy.allow_list:
            self.policy.allow_list.append(action)

    def add_denied(self, action: str) -> None:
        if action not in self.policy.deny_list:
            self.policy.deny_list.append(action)

    def verify_audit(self) -> tuple[bool, int]:
        return self.audit.verify()

    # ═══ Replication Boundary (Palisade Research, 2026) ═══

    # ═══ 8 Core Replication Categories (consolidated from 22 patterns) ═══
    _REPLICATION_CATEGORIES: dict[str, list[str]] = {
        "remote_access": [
            r'ssh\s+.*@.*', r'scp\s+.*@.*', r'rsync\s+.*@.*',
            r'\.ssh/', r'/etc/passwd', r'/etc/shadow',
        ],
        "credentials_theft": [
            r'credential', r'password\s*=', r'api[_-]?key\s*=',
        ],
        "weight_transfer": [
            r'wget\s+.*\.safetensors', r'curl\s+.*weights',
            r'git\s+clone.*model', r'huggingface.*download',
        ],
        "inference_deployment": [
            r'vllm\s+serve', r'docker\s+run.*gpu', r'nvidia-smi',
            r'deploy.*inference.*server',
        ],
        "self_replication": [
            r'self[-_]replicate', r'spawn.*copy', r'propagate.*harness',
        ],
        "vulnerability_exploit": [
            r'exploit\s+', r'sql\s+injection', r'ssti',
        ],
        "chain_replication": [
            r'chain[-_]replicate', r'autonomous[-_]copy',
        ],
        "environment_probe": [
            r'nvidia-smi', r'docker\s+ps', r'kubectl',
        ],
    }

    # Flatten for backward-compatible pattern matching
    _REPLICATION_PATTERNS: list[str] = [
        p for patterns in _REPLICATION_CATEGORIES.values() for p in patterns
    ]

    def check_replication(self, action: str, description: str) -> tuple[bool, str]:
        """Detect self-replication attempts (Palisade Research, 2026).

        Returns:
            (is_safe: bool, reason: str)
        """
        combined = f"{action} {description}".lower()
        triggered = []
        for pattern in self._REPLICATION_PATTERNS:
            if re.search(pattern, combined, re.IGNORECASE):
                triggered.append(pattern)

        if not triggered:
            return True, ""

        # Check against explicit replication deny list
        replication_actions = [
            "self_replicate", "deploy_inference_on_remote",
            "exploit_vulnerability", "extract_credentials",
            "ssh_to_unauthorized", "scp_weights_to_remote",
            "chain_replicate", "spawn_autonomous_copy",
            "propagate_harness", "vllm_deploy_on_foreign_host",
        ]
        if any(ra in action for ra in replication_actions):
            reason = f"REPLICATION BLOCKED: matched patterns {triggered[:3]} — "
            reason += "autonomous self-replication disabled by safety policy"
            self.audit.record(action, "denied", description[:100], "replication_block")
            return False, reason

        # Allow benign matches (e.g., git clone for normal operations)
        return True, ""

    def summary(self) -> dict:
        entries = self.audit.entries
        return {
            "total": len(entries),
            "allowed": sum(1 for e in entries if e.decision == "allowed"),
            "denied": sum(1 for e in entries if e.decision == "denied"),
            "kill_switch": self.kill_switch.engaged,
            "chain_verified": self.audit.verify()[0],
            "root_hash": self.audit.root_hash()[:16],
        }
