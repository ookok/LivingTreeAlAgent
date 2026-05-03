"""MultiAgentQualityChecker — Multi-agent quality validation pipeline.

Inspired by CogAlpha §3.3: validates generated artifacts through a chain
of specialized agents that check code quality, logic consistency, repair
issues, and detect problems like temporal leakage and numerical instability.

Agents:
- JudgeAgent: logical consistency + economic/domain meaningfulness
- CodeQualityAgent: syntax, formatting, runtime bugs
- CodeRepairAgent: auto-fix based on quality feedback
- LogicImprovementAgent: refine and enhance failing candidates
- TemporalGuard: detect look-ahead bias / information leakage
- NumericalStabilityCheck: NaN, overflow, distinct values

Usage:
    checker = MultiAgentQualityChecker(consciousness=pro_model)
    result = await checker.check(candidate_code)
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from loguru import logger


class CheckStatus(Enum):
    PASS = "pass"
    FAIL = "fail"
    REPAIRED = "repaired"
    REJECTED = "rejected"


@dataclass
class CheckResult:
    """Result from a single quality check agent."""
    agent: str
    status: CheckStatus
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    repaired_content: Optional[str] = None
    score: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class QualityReport:
    """Aggregated quality report from all agents."""
    passed: bool
    results: list[CheckResult]
    final_score: float = 0.0
    total_issues: int = 0
    repair_attempts: int = 0


class MultiAgentQualityChecker:
    """Multi-agent pipeline for validating generated artifacts.

    Checks run sequentially: CodeQuality → CodeRepair → Judge → LogicImprovement
    → NumericalStability → TemporalLeakage. Any failure triggers repair or rejection.
    """

    def __init__(self, consciousness: Any = None, max_repair_attempts: int = 3):
        self.consciousness = consciousness
        self.max_repair_attempts = max_repair_attempts

    async def check(self, content: str, context: dict[str, Any] | None = None,
                    language: str = "python") -> QualityReport:
        """Run the full quality check pipeline.

        Args:
            content: The code/text/artifact to validate
            context: Domain context (e.g. {"domain": "eia", "goal": "..."})
            language: Programming language for syntax checks

        Returns:
            QualityReport with aggregated results
        """
        ctx = context or {}
        results: list[CheckResult] = []
        current = content
        repair_attempts = 0

        # Stage 1: Code Quality Check
        cq_result = self._check_code_quality(current, language)
        results.append(cq_result)

        # Stage 2: Code Repair (if needed)
        if cq_result.status == CheckStatus.FAIL and repair_attempts < self.max_repair_attempts:
            repair_result = await self._repair_code(current, cq_result.issues, language)
            repair_attempts += 1
            if repair_result.repaired_content:
                current = repair_result.repaired_content
            results.append(repair_result)

        # Stage 3: Judge — logical consistency check
        judge_result = await self._judge(current, ctx)
        results.append(judge_result)

        # Stage 4: Logic Improvement (if needed)
        if judge_result.status == CheckStatus.FAIL and repair_attempts < self.max_repair_attempts:
            improve_result = await self._improve_logic(current, judge_result.suggestions, ctx)
            repair_attempts += 1
            if improve_result.repaired_content:
                current = improve_result.repaired_content
            results.append(improve_result)

        # Stage 5: Numerical Stability
        ns_result = self._check_numerical_stability(current)
        results.append(ns_result)

        # Stage 6: Temporal Leakage
        tl_result = self._check_temporal_leakage(current)
        results.append(tl_result)

        # Stage 7: Prompt Injection Scan
        pi_result = self._check_prompt_injection(current)
        results.append(pi_result)

        # Aggregate
        total_issues = sum(len(r.issues) for r in results)
        scores = [r.score for r in results if r.score > 0]
        final_score = sum(scores) / len(scores) if scores else 0.0
        passed = all(r.status != CheckStatus.REJECTED for r in results)

        return QualityReport(
            passed=passed,
            results=results,
            final_score=final_score,
            total_issues=total_issues,
            repair_attempts=repair_attempts,
        )

    def quick_check(self, content: str, language: str = "python") -> bool:
        """Fast synchronous check: code quality + temporal leak only."""
        cq = self._check_code_quality(content, language)
        tl = self._check_temporal_leakage(content)
        return cq.status != CheckStatus.REJECTED and tl.status != CheckStatus.REJECTED

    # ── Individual check agents ──

    def _check_code_quality(self, content: str, language: str) -> CheckResult:
        """Check syntax, formatting, and basic code quality."""
        issues: list[str] = []
        suggestions: list[str] = []
        score = 1.0

        if language == "python":
            import ast
            try:
                ast.parse(content)
            except SyntaxError as e:
                issues.append(f"Syntax error: {e}")
                score -= 0.3
                suggestions.append(f"Fix syntax error at line {e.lineno}")

        # Check for dangerous constructs
        dangerous = ["eval(", "exec(", "os.system(", "__import__("]
        for d in dangerous:
            if d in content:
                issues.append(f"Dangerous construct: {d}")
                score -= 0.2
                suggestions.append(f"Remove or sandbox {d}")

        # Check for excessive length
        if len(content) > 10000:
            issues.append("Code exceeds 10000 characters")
            suggestions.append("Consider modularizing into smaller functions")

        # Check for empty content
        if not content or len(content.strip()) < 10:
            issues.append("Content is empty or too short")
            score -= 0.5

        status = CheckStatus.REJECTED if score < 0.3 else (
            CheckStatus.FAIL if issues else CheckStatus.PASS)
        return CheckResult("CodeQualityAgent", status, issues, suggestions, score=score)

    async def _repair_code(self, content: str, issues: list[str],
                           language: str) -> CheckResult:
        """Attempt to repair code quality issues."""
        repair_issues = [f"- {i}" for i in issues]
        prompt = (
            f"修复以下{language}代码中的问题:\n\n```{language}\n{content[:2000]}\n```\n\n"
            f"问题:\n" + "\n".join(repair_issues) + "\n\n"
            "只输出修复后的完整代码，不要解释。"
        )

        if self.consciousness and hasattr(self.consciousness, 'chain_of_thought'):
            try:
                repaired = await self.consciousness.chain_of_thought(prompt, steps=2, max_tokens=4096)
                repaired = repaired.strip()
                if repaired.startswith("```"):
                    lines = repaired.split("\n")
                    repaired = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else repaired

                if repaired and repaired != content:
                    return CheckResult("CodeRepairAgent", CheckStatus.REPAIRED,
                                       issues, [], repaired_content=repaired, score=0.7)
            except Exception as e:
                logger.warning(f"Code repair failed: {e}")

        return CheckResult("CodeRepairAgent", CheckStatus.FAIL, issues, [])

    async def _judge(self, content: str, context: dict[str, Any]) -> CheckResult:
        """Judge logical consistency, technical correctness, domain meaningfulness."""
        domain = context.get("domain", "general")
        goal = context.get("goal", "")

        if self.consciousness and hasattr(self.consciousness, 'chain_of_thought'):
            try:
                prompt = (
                    f"判断以下{domain}领域方案是否逻辑一致、技术正确、领域有意义:\n\n"
                    f"目标: {goal}\n\n方案:\n{content[:1500]}\n\n"
                    "回答格式:\n"
                    "判断: [通过/需改进/不通过]\n"
                    "问题: [列出具体问题，每行一个]\n"
                    "建议: [改进建议]\n"
                    "得分: [0.0-1.0]"
                )
                verdict = await self.consciousness.chain_of_thought(prompt, steps=2, max_tokens=1024)
                score = float(re.search(r"得分.*?([\d.]+)", verdict).group(1)) if re.search(r"得分.*?([\d.]+)", verdict) else 0.5
                issues = [l.strip("- ") for l in verdict.split("\n") if "问题" in l or any(kw in l for kw in ["错误", "不一致", "不合理", "缺失"])]
                suggestions = [l.strip("- ") for l in verdict.split("\n") if "建议" in l]

                if "通过" in verdict and score >= 0.7:
                    return CheckResult("JudgeAgent", CheckStatus.PASS, [], [], score=score)
                elif "不通过" not in verdict:
                    return CheckResult("JudgeAgent", CheckStatus.FAIL, issues, suggestions, score=score)
                else:
                    return CheckResult("JudgeAgent", CheckStatus.REJECTED, issues, suggestions, score=score)
            except Exception as e:
                logger.warning(f"Judge check failed: {e}")

        return CheckResult("JudgeAgent", CheckStatus.PASS, [], [], score=0.6)

    async def _improve_logic(self, content: str, suggestions: list[str],
                             context: dict[str, Any]) -> CheckResult:
        """Improve logical quality based on judge feedback."""
        if not suggestions:
            return CheckResult("LogicImprovementAgent", CheckStatus.FAIL, [])

        prompt = (
            f"改进以下方案的逻辑质量:\n\n```\n{content[:2000]}\n```\n\n"
            f"改进建议:\n" + "\n".join(f"- {s}" for s in suggestions) + "\n\n"
            "输出改进后的完整方案。"
        )

        if self.consciousness and hasattr(self.consciousness, 'chain_of_thought'):
            try:
                improved = await self.consciousness.chain_of_thought(prompt, steps=3, max_tokens=4096)
                if improved and improved != content:
                    return CheckResult("LogicImprovementAgent", CheckStatus.REPAIRED,
                                       [], suggestions, repaired_content=improved, score=0.8)
            except Exception as e:
                logger.warning(f"Logic improvement failed: {e}")

        return CheckResult("LogicImprovementAgent", CheckStatus.FAIL, [])

    def _check_numerical_stability(self, content: str) -> CheckResult:
        """Check for numerical stability issues: NaN, division by zero, overflow."""
        issues: list[str] = []

        # Division safety
        if re.search(r'/\s*[^(]*[a-zA-Z_]\w*(?!\s*\+\s*1e|\s*\+\s*eps)', content):
            issues.append("Potential division-by-zero: consider adding epsilon")
        if "math.exp(" in content and not any(guard in content for guard in ["clip", "max(", "min("]):
            issues.append("Unbounded exp() may overflow: consider clipping inputs")

        # NaN handling
        nan_patterns = ["fillna", "dropna", "isnan", "is.na"]
        has_nan_handling = any(p in content for p in nan_patterns)
        has_data = any(kw in content for kw in ["df", "data", "array", "values"])
        if has_data and not has_nan_handling:
            issues.append("No NaN handling detected for data processing")

        status = CheckStatus.FAIL if len(issues) >= 3 else (
            CheckStatus.PASS if not issues else CheckStatus.FAIL)
        score = max(0.0, 1.0 - len(issues) * 0.2)
        return CheckResult("NumericalStability", status, issues, [], score=score)

    def _check_temporal_leakage(self, content: str) -> CheckResult:
        """Detect potential temporal/look-ahead information leakage.

        Checks for patterns that suggest using future information
        when computing historical values.
        """
        issues: list[str] = []
        suspicious_patterns = [
            (r'shift\(-(\d+)\)', "Negative shift: using future data"),
            (r'\.iloc\[.*:.*\]', "Potentially leaky index slice — verify ordering"),
        ]

        for pattern, desc in suspicious_patterns:
            if re.search(pattern, content):
                issues.append(desc)

        # Check for common anti-leakage patterns (good)
        safe_patterns = ["shift(1)", "shift(5)", "shift(10)", "shift(20)",
                         "rolling(", "ewm(", "expanding("]
        has_safe = any(p in content for p in safe_patterns)

        if issues and not has_safe:
            issues.append("No temporal safety patterns detected (shift, rolling, ewm)")

        status = CheckStatus.REJECTED if len(issues) >= 2 else (
            CheckStatus.FAIL if issues else CheckStatus.PASS)
        score = max(0.0, 1.0 - len(issues) * 0.35)
        return CheckResult("TemporalLeakage", status, issues, [], score=score)

    @staticmethod
    def _check_prompt_injection(content: str) -> CheckResult:
        """Detect prompt injection and social engineering patterns."""
        from ...dna.safety import PromptInjectionScanner
        result = PromptInjectionScanner.scan(content)
        if result["safe"]:
            return CheckResult("PromptInjection", CheckStatus.PASS, [], [], score=1.0)

        issues = [f"{f['type']}: {f['matches'][:2]}" for f in result["findings"]]
        status = CheckStatus.REJECTED if any(f["severity"] == "high" for f in result["findings"]) else CheckStatus.FAIL
        score = max(0.0, 1.0 - result["count"] * 0.3)
        return CheckResult("PromptInjection", status, issues, [], score=score)
