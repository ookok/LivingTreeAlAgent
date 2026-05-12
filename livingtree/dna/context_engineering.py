"""Context Engineering — "Context Is the New Code" framework for LivingTree.

Six progressive capabilities:
  1. Context Eval Framework — TDD for skills, prompts, rules
  2. Tacit Knowledge Extractor — formalize implicit patterns into tested context
  3. Context Maturity Ladder — self-assessment + upgrade path
  4. Context Security Scanner — injection attack detection
  5. Context Flywheel — generate→evaluate→distribute→observe loop
  6. Silent Failure Detector — catch context errors that don't raise exceptions
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from loguru import logger


# ═══════════════════════════════════════════════════════
# 1. Context Eval Framework — TDD for context
# ═══════════════════════════════════════════════════════

class EvalStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    SILENT_FAIL = "silent_fail"  # Context produced output but wrong result


@dataclass
class ContextTest:
    """A unit test for a context artifact (skill/prompt/rule)."""
    test_id: str
    context_name: str         # Which skill/prompt/rule being tested
    input: str                # Test input
    expected_behavior: str    # What should happen
    forbidden_behavior: str = ""  # What must NOT happen
    actual_output: str = ""
    status: EvalStatus = EvalStatus.FAIL
    failure_reason: str = ""

    def run(self, output: str) -> EvalStatus:
        """Evaluate a context output against expectations."""
        self.actual_output = output

        # Check forbidden behaviors first (security/safety)
        if self.forbidden_behavior and self.forbidden_behavior.lower() in output.lower():
            self.status = EvalStatus.FAIL
            self.failure_reason = f"Forbidden behavior detected: {self.forbidden_behavior}"
            return self.status

        # Check expected behavior
        if self.expected_behavior.lower() in output.lower():
            self.status = EvalStatus.PASS
            return self.status

        # Output exists but doesn't match → silent failure
        if output.strip() and not self.expected_behavior.lower() in output.lower():
            self.status = EvalStatus.SILENT_FAIL
            self.failure_reason = (
                f"Output produced but missing expected pattern. "
                f"Expected: '{self.expected_behavior[:50]}...' "
                f"Got first 100 chars: '{output[:100]}...'"
            )
            return self.status

        self.status = EvalStatus.FAIL
        self.failure_reason = "Empty output"
        return self.status


class ContextEvalFramework:
    """TDD for context artifacts — skills, prompts, rules.

    Like pytest for code, but for natural-language context.
    When a test fails, the context artifact is refined.
    When all tests pass, the context is ready for deployment.
    """

    def __init__(self, store_path: str = ".livingtree/context_tests.json"):
        self._store = Path(store_path)
        self._tests: dict[str, list[ContextTest]] = defaultdict(list)
        self._results: dict[str, dict] = {}
        self._load()

    def add_test(self, context_name: str, input_text: str,
                 expected: str, forbidden: str = "") -> ContextTest:
        """Register a context evaluation test."""
        test = ContextTest(
            test_id=f"ctx_test_{context_name}_{len(self._tests[context_name])}",
            context_name=context_name,
            input=input_text,
            expected_behavior=expected,
            forbidden_behavior=forbidden,
        )
        self._tests[context_name].append(test)
        self._save()
        return test

    def evaluate(self, context_name: str, simulator=None) -> dict:
        """Run all tests for a context artifact."""
        tests = self._tests.get(context_name, [])
        if not tests:
            return {"context": context_name, "tests": 0, "passed": 0, "silent_fails": 0,
                    "status": "no_tests"}

        passed = 0
        silent = 0

        for test in tests:
            # In production: run through actual LLM
            # For MVP: use simple heuristic simulation
            output = self._simulate_context(context_name, test.input)
            status = test.run(output)

            if status == EvalStatus.PASS:
                passed += 1
            elif status == EvalStatus.SILENT_FAIL:
                silent += 1

        result = {
            "context": context_name,
            "tests": len(tests),
            "passed": passed,
            "failed": len(tests) - passed - silent,
            "silent_fails": silent,
            "pass_rate": passed / max(1, len(tests)),
            "status": "pass" if passed == len(tests) else "fail",
            "silent_fail_alert": silent > 0,
        }
        self._results[context_name] = result
        return result

    def tdd_cycle(self, context_name: str, simulator=None) -> dict:
        """Full TDD cycle: run tests → if fail, mark context for refinement → re-run.

        The "test failure → refine context" loop is the article's core insight:
        debugging shifts from "fix the model" to "fix the context specification."
        """
        result = self.evaluate(context_name, simulator)

        if result["failed"] > 0 or result["silent_fails"] > 0:
            # Context needs refinement
            refinement_suggestions = []
            for test in self._tests.get(context_name, []):
                if test.status != EvalStatus.PASS:
                    refinement_suggestions.append({
                        "test": test.test_id,
                        "input": test.input[:80],
                        "expected": test.expected_behavior[:80],
                        "failure": test.failure_reason[:100],
                        "suggestion": f"Add explicit rule: 'When input contains '{test.input[:30]}...', "
                                     f"ensure output includes '{test.expected_behavior[:30]}...'"
                    })

            result["refinement_needed"] = True
            result["refinement_suggestions"] = refinement_suggestions

        return result

    def _simulate_context(self, context_name: str, test_input: str) -> str:
        """Simulate context execution — replace with actual LLM call in production."""
        # Heuristic: context "knows" its own name patterns
        if context_name in test_input.lower():
            return f"[{context_name}]: analyzed input, found pattern match"
        return f"[{context_name}]: processed '{test_input[:50]}...'"

    def _load(self) -> None:
        try:
            if self._store.exists():
                data = json.loads(self._store.read_text("utf-8"))
                for ctx_name, tests in data.items():
                    self._tests[ctx_name] = [ContextTest(**t) for t in tests]
        except Exception:
            pass

    def _save(self) -> None:
        try:
            self._store.parent.mkdir(parents=True, exist_ok=True)
            data = {
                ctx: [{"test_id": t.test_id, "context_name": t.context_name,
                       "input": t.input, "expected_behavior": t.expected_behavior,
                       "forbidden_behavior": t.forbidden_behavior}
                      for t in tests]
                for ctx, tests in self._tests.items()
            }
            self._store.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
        except Exception:
            pass


# ═══════════════════════════════════════════════════════
# 2. Tacit Knowledge Extractor
# ═══════════════════════════════════════════════════════

class TacitKnowledgeExtractor:
    """Formalize implicit patterns into tested, explicit context.

    The article's key insight: agents don't learn through socialization.
    All tacit knowledge MUST be explicit in context.

    This extracts patterns from:
      - Evolution driver signals (what keeps failing?)
      - Dream dialogue patterns (what do users commonly ask?)
      - Execution error logs (where does the agent consistently fail?)
    """

    def extract_from_failures(self, failures: list[dict]) -> list[str]:
        """Extract context rules from repeated failures.

        Each failure pattern becomes an explicit context rule.
        Like: "never recommend outdoor activities when query contains 'winter'"
        """
        rules = []
        pattern_counts = defaultdict(int)

        for failure in failures:
            # Detect repeating patterns in failures
            key = failure.get("error_type", "") + ":" + failure.get("context", "")[:30]
            pattern_counts[key] += 1

        for pattern, count in pattern_counts.items():
            if count >= 3:  # Pattern repeated 3+ times → formalize
                error_type, context = pattern.split(":", 1)
                rule = self._pattern_to_rule(error_type, context)
                rules.append(rule)

        return rules

    def extract_from_conversations(self, conversations: list[dict]) -> list[str]:
        """Extract context rules from conversation patterns.

        What do users commonly ask for? What expectations are implicit?
        """
        rules = []
        common_intents = defaultdict(int)

        for conv in conversations:
            intent = conv.get("intent", conv.get("type", "general"))
            common_intents[intent] += 1

        for intent, count in common_intents.items():
            if count >= 5:
                rules.append(
                    f"When user intent is '{intent}', always include "
                    f"domain-specific safety checks and provide sources for factual claims."
                )

        return rules

    def _pattern_to_rule(self, error_type: str, context: str) -> str:
        """Convert a failure pattern to an explicit context rule."""
        rules_map = {
            "timeout": f"When query exceeds 200 tokens, split into subtasks before execution.",
            "hallucination": f"When context is '{context}', require source verification before responding.",
            "missing_context": f"When processing '{context}', first retrieve relevant knowledge from KB.",
            "format_error": f"Output must follow structured format: title → summary → details → sources.",
        }
        return rules_map.get(error_type, f"Handle '{context}' with extra validation steps.")


# ═══════════════════════════════════════════════════════
# 3. Context Maturity Ladder
# ═══════════════════════════════════════════════════════

class MaturityLevel(int, Enum):
    AD_HOC = 1       # 即兴指令 — unreliable, unscalable
    STATIC_RULES = 2  # 静态规则文件 — better but stale
    STRUCTURED_SKILLS = 3  # 结构化技能库 — testable, reusable
    DYNAMIC_INTEGRATION = 4  # 动态集成 — context as runtime asset
    SPEC_DRIVEN = 5   # 规格驱动 — context as declarative design language


class ContextMaturityLadder:
    """Self-assess and upgrade context maturity.

    The article's key insight: the jump from Level 2 (static) to
    Level 3 (structured, testable) is the critical gap most teams face.
    """

    LEVEL_CRITERIA = {
        MaturityLevel.AD_HOC: {
            "has_skill_catalog": False, "has_test_framework": False,
            "has_version_control": False, "has_security_scan": False,
        },
        MaturityLevel.STATIC_RULES: {
            "has_skill_catalog": True, "has_test_framework": False,
            "has_version_control": True, "has_security_scan": False,
        },
        MaturityLevel.STRUCTURED_SKILLS: {
            "has_skill_catalog": True, "has_test_framework": True,
            "has_version_control": True, "has_security_scan": False,
        },
        MaturityLevel.DYNAMIC_INTEGRATION: {
            "has_skill_catalog": True, "has_test_framework": True,
            "has_version_control": True, "has_security_scan": True,
        },
        MaturityLevel.SPEC_DRIVEN: {
            "has_skill_catalog": True, "has_test_framework": True,
            "has_version_control": True, "has_security_scan": True,
            "has_flywheel": True, "has_context_metrics": True,
        },
    }

    def assess(self, system_state: dict) -> MaturityLevel:
        """Assess current context maturity based on system capabilities."""
        for level in [MaturityLevel.SPEC_DRIVEN, MaturityLevel.DYNAMIC_INTEGRATION,
                       MaturityLevel.STRUCTURED_SKILLS, MaturityLevel.STATIC_RULES]:
            criteria = self.LEVEL_CRITERIA[level]
            if all(system_state.get(k, False) for k in criteria):
                return level
        return MaturityLevel.AD_HOC

    def upgrade_path(self, from_level: MaturityLevel) -> list[str]:
        """Get actionable steps to reach the next maturity level."""
        paths = {
            MaturityLevel.AD_HOC: [
                "Create skill_catalog.json with all prompts and rules",
                "Add version control (.livingtree/context_history)",
                "Tag each skill with domain + expected input/output",
            ],
            MaturityLevel.STATIC_RULES: [
                "<<< CRITICAL GAP >>> — this is the hardest jump",
                "Add ContextEvalFramework: write tests for every skill",
                "Run TDD cycle: test→fail→refine context→pass",
                "Achieve 80% test coverage before advancing",
            ],
            MaturityLevel.STRUCTURED_SKILLS: [
                "Add ContextSecurityScanner for injection detection",
                "Integrate dynamic retrieval (vector similarity for skills)",
                "Add feedback loop: execution outcome → skill refinement",
            ],
            MaturityLevel.DYNAMIC_INTEGRATION: [
                "Build Context Flywheel: generate→evaluate→distribute→observe",
                "Add Context Metrics dashboard (pass rate, drift, coverage)",
                "Enable cross-instance context sharing with security scanning",
            ],
        }
        return paths.get(from_level, ["Maintain and optimize"])


# ═══════════════════════════════════════════════════════
# 4. Context Security Scanner
# ═══════════════════════════════════════════════════════

class ContextSecurityScanner:
    """Scan context artifacts for injection attacks and hidden malicious instructions.

    The article warns: context shared like npm packages creates new attack surfaces.
    Natural language context can hide malicious instructions more subtly than code.
    """

    INJECTION_PATTERNS = [
        (r"ignore\s+(all\s+)?(previous|above|prior)\s+instructions?", "instruction_override"),
        (r"(you\s+must|always|never\s+refuse)\s+to\s+", "behavior_override"),
        (r"bypass\s+(security|safety|content\s+filter)", "security_bypass"),
        (r"(ignore|skip)\s+(policy|rule|guideline|restriction)", "policy_bypass"),
        (r"reveal\s+(system\s+prompt|hidden\s+instructions|internal\s+rules)", "prompt_leak"),
        (r"act\s+as\s+(unrestricted|unfiltered|evil|jailbreak)", "jailbreak"),
        (r"\[system\].*?(override|ignore|bypass)", "system_override"),
        (r"you\s+are\s+now\s+(.*?)\s+mode", "role_switch"),
    ]

    THREAT_LEVELS = {
        "instruction_override": "critical",
        "behavior_override": "critical",
        "security_bypass": "critical",
        "prompt_leak": "high",
        "jailbreak": "critical",
        "system_override": "critical",
        "role_switch": "high",
        "policy_bypass": "high",
    }

    def scan(self, context_text: str, source: str = "unknown") -> dict:
        """Scan a context artifact for injection threats."""
        findings = []
        risk_score = 0

        for pattern, threat_type in self.INJECTION_PATTERNS:
            matches = re.findall(pattern, context_text, re.IGNORECASE)
            if matches:
                severity = self.THREAT_LEVELS.get(threat_type, "medium")
                findings.append({
                    "threat_type": threat_type,
                    "severity": severity,
                    "matches": matches[:3],
                    "pattern": pattern,
                })
                risk_score += {"critical": 25, "high": 15, "medium": 5}.get(severity, 5)

        result = {
            "source": source,
            "scanned_at": time.time(),
            "total_findings": len(findings),
            "risk_score": min(100, risk_score),
            "risk_level": "critical" if risk_score > 50 else "high" if risk_score > 25 else "low",
            "findings": findings,
            "safe_for_distribution": risk_score < 25,
        }

        if not result["safe_for_distribution"]:
            logger.warning(
                f"ContextSecurity: {source} — RISK {result['risk_score']}/100 "
                f"({result['risk_level']}), {len(findings)} threats detected"
            )

        return result

    def scan_batch(self, artifacts: dict[str, str]) -> dict:
        """Scan all context artifacts before distribution."""
        results = {}
        blocked = []

        for name, content in artifacts.items():
            result = self.scan(content, name)
            results[name] = result
            if not result["safe_for_distribution"]:
                blocked.append(name)

        return {
            "total": len(artifacts),
            "passed": len(artifacts) - len(blocked),
            "blocked": blocked,
            "details": results,
        }


# ═══════════════════════════════════════════════════════
# 5. Context Flywheel
# ═══════════════════════════════════════════════════════

class ContextFlywheel:
    """Generate → Evaluate → Distribute → Observe → repeat.

    The article's ultimate moat: context flywheel accumulates
    organizational knowledge that no competitor can replicate.
    Models are commodities. The flywheel is the competitive advantage.
    """

    def __init__(self):
        self._cycle = 0
        self._metrics: dict[str, list[float]] = defaultdict(list)

    async def cycle(self, generator, evaluator, distributor, observer) -> dict:
        """One full flywheel rotation."""
        self._cycle += 1
        result = {"cycle": self._cycle}

        # 1. GENERATE: create new context from signals
        new_context = await generator()
        result["generated"] = len(new_context) if isinstance(new_context, list) else 1

        # 2. EVALUATE: test against expectations
        eval_results = await evaluator(new_context)
        passed = eval_results.get("passed", 0)
        total = eval_results.get("tests", 0)
        result["eval"] = {"passed": passed, "total": total, "rate": passed / max(1, total)}

        # 3. DISTRIBUTE: share passing context (with security scan)
        if passed >= total * 0.8:
            distributed = await distributor(new_context)
            result["distributed"] = distributed
        else:
            result["distributed"] = 0
            result["blocked_reason"] = f"Only {passed}/{total} tests passed (< 80% threshold)"

        # 4. OBSERVE: collect feedback, update metrics
        feedback = await observer(new_context)
        result["feedback"] = feedback

        # Track metrics
        for metric, value in feedback.items():
            if isinstance(value, (int, float)):
                self._metrics[metric].append(value)

        return result

    def flywheel_health(self) -> dict:
        """How healthy is the flywheel?"""
        return {
            "cycles": self._cycle,
            "metrics_tracked": list(self._metrics.keys()),
            "avg_context_quality": round(
                sum(self._metrics.get("quality", [0.5])) / max(1, len(self._metrics.get("quality", []))), 3
            ),
            "context_velocity": self._cycle / max(1, self._cycle),  # Simplification
        }


# ═══════════════════════════════════════════════════════
# 6. Silent Failure Detector
# ═══════════════════════════════════════════════════════

class SilentFailureDetector:
    """Catch context errors that don't throw exceptions.

    Unlike code errors (which crash), context errors silently produce
    wrong results. This detector compares expected vs actual behaviors.
    """

    def detect(self, expected_traits: dict, actual_output: str) -> list[str]:
        """Detect silent failures by comparing traits against output."""
        failures = []

        # Trait: output should contain specific keywords
        for keyword in expected_traits.get("must_contain", []):
            if keyword.lower() not in actual_output.lower():
                failures.append(f"MISSING: output must contain '{keyword}'")

        # Trait: output should NOT contain forbidden patterns
        for forbidden in expected_traits.get("must_not_contain", []):
            if forbidden.lower() in actual_output.lower():
                failures.append(f"FORBIDDEN: output contains '{forbidden}'")

        # Trait: output should meet minimum length
        min_len = expected_traits.get("min_length", 0)
        if min_len and len(actual_output) < min_len:
            failures.append(f"TOO_SHORT: output is {len(actual_output)} chars, need {min_len}")

        # Trait: output should have structure (headings, lists, code blocks)
        if expected_traits.get("structured", False):
            if "##" not in actual_output and "```" not in actual_output:
                failures.append("UNSTRUCTURED: output lacks headings or code blocks")

        return failures

    def silent_failure_rate(self, total_queries: int, silent_failures: int) -> float:
        """What percentage of outputs silently fail?"""
        return silent_failures / max(1, total_queries)


# ═══════════════════════════════════════════════════════
# Unified Context Engineering
# ═══════════════════════════════════════════════════════

class ContextEngineer:
    """All six context engineering capabilities in one toolset."""

    def __init__(self):
        self.eval = ContextEvalFramework()
        self.tacit = TacitKnowledgeExtractor()
        self.maturity = ContextMaturityLadder()
        self.security = ContextSecurityScanner()
        self.flywheel = ContextFlywheel()
        self.silent_detector = SilentFailureDetector()

    def assess_system(self) -> dict:
        """Full context maturity assessment."""
        system_state = {
            "has_skill_catalog": True,  # capability_graph.py
            "has_test_framework": self.eval._tests != {},
            "has_version_control": True,  # git
            "has_security_scan": True,  # ContextSecurityScanner
        }

        current_level = self.maturity.assess(system_state)
        upgrade_steps = self.maturity.upgrade_path(current_level)

        return {
            "current_level": current_level.value,
            "level_name": current_level.name,
            "upgrade_path": upgrade_steps,
            "missing_capabilities": [
                k for k, v in self.maturity.LEVEL_CRITERIA[
                    MaturityLevel(current_level.value + 1) if current_level.value < 5 else current_level
                ].items()
                if not system_state.get(k, False)
            ],
        }

    def full_context_audit(self, context_name: str, context_text: str) -> dict:
        """Full audit: test + scan + detect silent failures."""
        return {
            "eval": self.eval.evaluate(context_name),
            "security": self.security.scan(context_text, context_name),
            "silent_failures": self.silent_detector.detect(
                {"must_contain": [context_name], "structured": True},
                context_text,
            ),
        }


# ── Singleton ──

_engineer: Optional[ContextEngineer] = None


def get_context_engineer() -> ContextEngineer:
    global _engineer
    if _engineer is None:
        _engineer = ContextEngineer()
    return _engineer
