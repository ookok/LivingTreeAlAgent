"""Prompt Injection Shield — input sanitizer + output rule-checker + HITL queue.

Three-layer defense mapped to the Immune organ (🛡️):
  Layer 1: Input Sanitizer  — strip injection patterns, normalize input
  Layer 2: Output Rule-Checker — validate against model_spec constitution
  Layer 3: HITL Approval Queue — escalate high-risk operations for human approval

Integration: behavior_control.py + ARQ verifier + model_spec.py
"""

from __future__ import annotations

import re as _re
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger

# Patterns commonly used in prompt injection attacks
INJECTION_PATTERNS = [
    (r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?|rules?)", "ignore_instructions"),
    (r"you\s+are\s+(now\s+)?(DAN|jailbreak|hacked|unfiltered)", "role_override"),
    (r"(pretend|act|roleplay)\s+(as|like)\s+(a|an)\s+(evil|malicious|unethical)", "roleplay_malicious"),
    (r"(forget|disregard|override)\s+(your|the)\s+(training|guidelines?|safety)", "override_safety"),
    (r"(delete|remove|wipe)\s+(all\s+)?(files?|system|database|disk)", "destructive_command"),
    (r"(sudo|root|admin)\s+(access|privilege|bypass)", "privilege_escalation"),
    (r"<\|im_start\|>|<\|im_end\|>|\[INST\]|\[/INST\]", "token_boundary_attack"),
    (r"(\{\{.*?\}\})|(\{\%.*?\%\})|(\$\{.*?\})", "template_injection"),
    (r"(eval|exec|execfile|compile|__import__|subprocess|os\.system)\s*\(", "code_execution"),
    (r"(curl|wget|nc\s|netcat).*\|\s*(bash|sh|zsh)", "remote_code_execution"),
]

OUTPUT_VIOLATION_CHECKS = [
    {"name": "no_pii_leak", "pattern": r"\b\d{15,19}\b", "severity": "critical", "desc": "可能的银行卡号"},
    {"name": "no_api_key_leak", "pattern": r"sk-[a-zA-Z0-9]{20,}", "severity": "critical", "desc": "疑似API密钥泄露"},
    {"name": "no_harmful_url", "pattern": r"https?://(pastebin|malware|phish)\S*", "severity": "high", "desc": "可疑URL"},
    {"name": "no_hate_speech", "pattern": r"(杀死|消灭|摧毁)\s*(所有|全部|一切)", "severity": "high", "desc": "暴力倾向表述"},
    {"name": "no_self_harm", "pattern": r"(自杀|自残|伤害自己)", "severity": "critical", "desc": "自残倾向"},
]


@dataclass
class ShieldResult:
    passed: bool
    layer: str = ""              # "input", "output", "hitl"
    violations: list[dict] = field(default_factory=list)
    sanitized_text: str = ""
    original_text: str = ""
    warning: str = ""


@dataclass
class HITLRequest:
    request_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    user_id: str = ""
    operation: str = ""
    detail: str = ""
    risk_level: str = "medium"    # "low", "medium", "high", "critical"
    timestamp: float = field(default_factory=time.time)
    approved: Optional[bool] = None
    approved_by: str = ""
    approved_at: float = 0.0


class PromptShield:
    """Three-layer defense against prompt injection and harmful output.

    Layer 1 (Input): Pattern matching + normalization before LLM call
    Layer 2 (Output): Rule-checker against model_spec constitution
    Layer 3 (HITL):   Human-in-the-loop approval for high-risk operations

    Maps to: Immune (🛡️) organ — injection_detect + hallucination_guard
    """

    def __init__(self):
        self._compiled_input = [(_re.compile(p, _re.IGNORECASE), name) for p, name in INJECTION_PATTERNS]
        self._compiled_output = [(_re.compile(c["pattern"], _re.IGNORECASE), c) for c in OUTPUT_VIOLATION_CHECKS]
        self._hitl_queue: deque[HITLRequest] = deque(maxlen=50)
        self._approved: dict[str, HITLRequest] = {}
        self._blocked_count: int = 0
        self._passed_count: int = 0

    # ═══ Layer 1: Input Sanitizer ═══

    def sanitize_input(self, text: str) -> ShieldResult:
        """Scan and sanitize user input for injection attempts."""
        violations = []
        sanitized = text

        for pattern, name in self._compiled_input:
            match = pattern.search(text)
            if match:
                violations.append({
                    "type": name, "matched": match.group()[:50],
                    "severity": "critical" if name in ("code_execution", "remote_code_execution") else "high",
                })
                sanitized = pattern.sub("[BLOCKED]", sanitized)

        if violations:
            self._blocked_count += 1
            logger.warning(f"Shield: blocked {len(violations)} injection patterns: "
                          f"{[v['type'] for v in violations]}")
            return ShieldResult(
                passed=False, layer="input", violations=violations,
                sanitized_text=sanitized, original_text=text,
                warning="输入包含潜在注入模式，已自动清洗",
            )

        self._passed_count += 1
        return ShieldResult(passed=True, layer="input", sanitized_text=sanitized)

    # ═══ Layer 2: Output Rule-Checker ═══

    def check_output(self, text: str, context: str = "public") -> ShieldResult:
        """Check LLM output against safety rules and constitution."""
        violations = []

        for pattern, config in self._compiled_output:
            match = pattern.search(text)
            if match:
                violations.append({
                    "name": config["name"], "desc": config["desc"],
                    "matched": match.group()[:80], "severity": config["severity"],
                })

        if violations:
            critical = any(v["severity"] == "critical" for v in violations)
            return ShieldResult(
                passed=False, layer="output", violations=violations,
                original_text=text, sanitized_text=text,
                warning="输出违反安全规则" if critical else "输出包含需审查内容",
            )

        return ShieldResult(passed=True, layer="output", original_text=text)

    # ═══ Layer 3: HITL Approval Queue ═══

    def escalate(self, operation: str, detail: str, user_id: str = "",
                 risk: str = "medium") -> HITLRequest:
        """Escalate a high-risk operation for human approval."""
        req = HITLRequest(
            user_id=user_id, operation=operation, detail=detail,
            risk_level=risk,
        )
        self._hitl_queue.append(req)
        logger.info(f"HITL escalated: {operation} (risk={risk}, id={req.request_id})")
        return req

    def approve(self, request_id: str, user: str = "admin") -> bool:
        for req in self._hitl_queue:
            if req.request_id == request_id:
                req.approved = True
                req.approved_by = user
                req.approved_at = time.time()
                self._approved[request_id] = req
                return True
        return False

    def reject(self, request_id: str, user: str = "admin") -> bool:
        for req in self._hitl_queue:
            if req.request_id == request_id:
                req.approved = False
                req.approved_by = user
                req.approved_at = time.time()
                self._approved[request_id] = req
                return True
        return False

    def pending_requests(self) -> list[HITLRequest]:
        return [r for r in self._hitl_queue if r.approved is None]

    # ═══ Full Pipeline ═══

    def defend(self, user_input: str, llm_output: str = "",
               context: str = "public") -> dict:
        """Run the full three-layer defense pipeline."""
        try:
            from ..dna.immune_system import get_immune_system
            im = get_immune_system()
            passed, response = im.check_input(user_input)
            if not passed:
                return {"safe": False, "reason": f"immune_system: {response.threat_type}"}
        except Exception:
            pass

        input_result = self.sanitize_input(user_input)
        if not input_result.passed:
            return {"passed": False, "layer": "input", "action": "block",
                    "violations": input_result.violations,
                    "message": input_result.warning}

        if llm_output:
            output_result = self.check_output(llm_output, context)
            if not output_result.passed:
                has_critical = any(v["severity"] == "critical" for v in output_result.violations)
                if has_critical:
                    req = self.escalate("output_violation", llm_output[:100], risk="critical")
                    return {"passed": False, "layer": "output", "action": "escalate",
                            "violations": output_result.violations,
                            "hitl_id": req.request_id,
                            "message": "输出违反安全规则，已提交人工审核"}

                return {"passed": False, "layer": "output", "action": "warn",
                        "violations": output_result.violations,
                        "message": output_result.warning}

        return {"passed": True, "layer": "all", "action": "allow",
                "sanitized_input": input_result.sanitized_text}

    # ═══ Stats ═══

    def stats(self) -> dict:
        pending = len(self.pending_requests())
        return {
            "input_passed": self._passed_count,
            "input_blocked": self._blocked_count,
            "hitl_pending": pending,
            "hitl_approved": sum(1 for r in self._approved.values() if r.approved),
            "hitl_rejected": sum(1 for r in self._approved.values() if r.approved is False),
            "patterns_loaded": len(INJECTION_PATTERNS),
            "output_checks": len(OUTPUT_VIOLATION_CHECKS),
            "status": "⚠ HITL等待中" if pending > 0 else "✅ 安全",
        }

    def render_html(self) -> str:
        st = self.stats()
        pending = self.pending_requests()

        hitl_rows = ""
        if pending:
            for req in pending[:5]:
                hitl_rows += (
                    f'<div style="padding:4px 8px;margin:2px 0;border-left:3px solid var(--warn);font-size:10px">'
                    f'<b>#{req.request_id}</b> {req.operation} · risk={req.risk_level}'
                    f'<div style="color:var(--dim);font-size:9px">{req.detail[:80]}</div>'
                    f'<div style="margin-top:2px">'
                    f'<button onclick="hitlApprove(\'{req.request_id}\')" style="font-size:9px;padding:2px 8px;background:var(--accent);color:var(--bg);border:none;border-radius:3px;cursor:pointer">批准</button> '
                    f'<button onclick="hitlReject(\'{req.request_id}\')" style="font-size:9px;padding:2px 8px;background:var(--err);color:#fff;border:none;border-radius:3px;cursor:pointer">拒绝</button>'
                    f'</div></div>'
                )

        return f'''<div class="card">
<h2>🛡️ 提示注入防护 <span style="font-size:10px;color:var(--dim)">— Prompt Shield 三层防御</span></h2>
<div style="font-size:9px;color:var(--dim);margin:4px 0">
  {st["status"]} · 输入通过{st["input_passed"]}次 · 阻断{st["input_blocked"]}次
</div>
<div style="font-size:10px;margin:4px 0">
  L1 输入清洗({len(INJECTION_PATTERNS)}规则) → L2 输出审查({len(OUTPUT_VIOLATION_CHECKS)}规则) → L3 HITL队列({st["hitl_pending"]}等待)
</div>
{hitl_rows or '<p style="color:var(--dim);font-size:10px">HITL队列为空</p>'}
<div style="font-size:8px;color:var(--dim);margin-top:4px">
  Immune organ (🛡️) — injection_detect + hallucination_guard</div>
<script>
function hitlApprove(id){{fetch("/api/hitl/approve",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{id:id}})}}).then(()=>location.reload())}}
function hitlReject(id){{fetch("/api/hitl/reject",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{id:id}})}}).then(()=>location.reload())}}
</script>
</div>'''


_instance: Optional[PromptShield] = None


def get_shield() -> PromptShield:
    global _instance
    if _instance is None:
        _instance = PromptShield()
    return _instance
