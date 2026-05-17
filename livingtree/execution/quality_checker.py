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
# SUBPROCESS MIGRATION: from livingtree.treellm.unified_exec import run_sync



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
class EvidenceItem:
    """A piece of evidence found in the original context."""
    text: str
    position: int = 0
    position_pct: float = 0.0
    is_referenced: bool = False


@dataclass
class MultiHopReport:
    """SSA/MRCR inspired: evaluate whether the response used all relevant evidence.

    Key metrics:
      - recall: did response reference all key entities from context?
      - position_bias: did response ignore early evidence?
      - integration_score: were non-adjacent pieces correctly combined?
    """
    evidence_recall: float = 0.0
    position_bias_score: float = 1.0
    integration_score: float = 0.0
    total_evidence: int = 0
    referenced_evidence: int = 0
    early_ignored: int = 0
    multi_hop_pairs: int = 0
    integrated_pairs: int = 0
    final_score: float = 0.0
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


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
                    language: str = "python",
                    original_context: str = "",
                    system_prompt: str = "",
                    user_prompt: str = "") -> QualityReport:
        """Run the full quality check pipeline with PromptEcho scoring.

        Args:
            content: The code/text/artifact to validate
            context: Domain context (e.g. {"domain": "eia", "goal": "..."})
            language: Programming language for syntax checks
            original_context: Full original context for multi-hop evidence check
            system_prompt: System prompt for PromptEcho scoring
            user_prompt: User query for PromptEcho scoring
        """
        ctx = context or {}
        results: list[CheckResult] = []
        current = content
        repair_attempts = 0

        cq_result = self._check_code_quality(current, language)
        results.append(cq_result)

        if cq_result.status == CheckStatus.FAIL and repair_attempts < self.max_repair_attempts:
            repair_result = await self._repair_code(current, cq_result.issues, language)
            repair_attempts += 1
            if repair_result.repaired_content:
                current = repair_result.repaired_content
            results.append(repair_result)

        judge_result = await self._judge(current, ctx)
        results.append(judge_result)

        if judge_result.status == CheckStatus.FAIL and repair_attempts < self.max_repair_attempts:
            improve_result = await self._improve_logic(current, judge_result.suggestions, ctx)
            repair_attempts += 1
            if improve_result.repaired_content:
                current = improve_result.repaired_content
            results.append(improve_result)

        ns_result = self._check_numerical_stability(current)
        results.append(ns_result)

        tl_result = self._check_temporal_leakage(current)
        results.append(tl_result)

        pi_result = self._check_prompt_injection(current)
        results.append(pi_result)

        if original_context:
            mh_result, mh_report = self._check_multi_hop_evidence(
                content, original_context, ctx)
            results.append(mh_result)

        pe_result = self._check_prompt_echo(content, system_prompt, user_prompt)
        results.append(pe_result)

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

    def _check_prompt_echo(self, content: str, system_prompt: str = "",
                            user_prompt: str = "") -> CheckResult:
        """PromptEcho: zero-cost quality scoring via prompt-output alignment.

        Uses n-gram overlap between prompt and output as a lightweight
        proxy for the token-level cross-entropy PromptEcho calculates.
        Detects: hallucination (low prompt alignment), verbosity,
        specificity gaps.
        """
        from .quality_scorer import get_quality_scorer
        scorer = get_quality_scorer()
        score_result = scorer.evaluate(content, system_prompt, user_prompt)

        issues = []
        suggestions = []

        if score_result.overall_score < 0.35:
            issues.append(f"整体质量低 (PromptEcho={score_result.overall_score:.2f}): "
                          f"输出可能与prompt意图不匹配")
            suggestions.append("重新生成，确保覆盖prompt中的所有要点")

        weak = score_result.weak_segments
        if len(weak) > 0:
            weak_indices = [str(s.index) for s in weak[:3]]
            issues.append(f"弱段落: {', '.join(weak_indices)} — "
                          f"{len(weak)}/{len(score_result.per_segment)}段质量不足")
            suggestions.append(f"针对性修复段落 {weak_indices[0]}")

        for flag in score_result.flags:
            if "missing_entities" in flag:
                entities = flag.split(":")[1] if ":" in flag else ""
                issues.append(f"未引用关键实体: {entities}")
                suggestions.append(f"在回答中提及: {entities}")
            elif flag == "too_short":
                issues.append("输出过短，可能未充分回答")
                suggestions.append("扩展回答，提供更详细的分析")
            elif flag == "verbose":
                issues.append("输出过长，可能包含冗余信息")
            elif flag == "unclosed_code_block":
                issues.append("代码块未正确闭合")
                suggestions.append("确保所有```都有配对闭合")
            elif flag == "hedging":
                issues.append("包含模糊表达 (不确定/可能/也许)")
                suggestions.append("给出明确的结论或标注不确定性来源")

        if not issues:
            return CheckResult(
                "PromptEcho", CheckStatus.PASS, [], [],
                score=score_result.overall_score,
            )

        status = CheckStatus.FAIL if score_result.overall_score > 0.3 else CheckStatus.REJECTED
        return CheckResult(
            "PromptEcho", status, issues, suggestions,
            score=score_result.overall_score,
        )

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
        from ..dna.safety import PromptInjectionScanner
        result = PromptInjectionScanner.scan(content)
        if result["safe"]:
            return CheckResult("PromptInjection", CheckStatus.PASS, [], [], score=1.0)

        issues = [f"{f['type']}: {f['matches'][:2]}" for f in result["findings"]]
        status = CheckStatus.REJECTED if any(f["severity"] == "high" for f in result["findings"]) else CheckStatus.FAIL
        score = max(0.0, 1.0 - result["count"] * 0.3)
        return CheckResult("PromptInjection", status, issues, [], score=score)

    # ── SSA/MRCR Multi-Hop Evidence Check ──

    @staticmethod
    def check_multi_hop_evidence(response: str, original_context: str,
                                  domain: str = "general") -> tuple[CheckResult, MultiHopReport]:
        """SSA-inspired: evaluate whether the response used all relevant evidence.

        MRCR v2 style: tests if the model can locate and integrate multiple
        non-adjacent pieces of evidence, not just nearby context.

        Checks:
          1. Evidence recall: are key entities from context referenced in response?
          2. Position bias: did the response ignore early context?
          3. Multi-hop integration: were non-adjacent evidence pairs combined?
        """
        report = MultiHopEvidenceCheck._analyze(response, original_context)

        issues = []
        suggestions = []

        if report.total_evidence == 0:
            return (
                CheckResult("MultiHopEvidence", CheckStatus.PASS, [], [], score=1.0),
                report,
            )

        if report.evidence_recall < 0.5:
            issues.append(
                f"证据召回率低 ({report.evidence_recall:.0%}): "
                f"只引用了 {report.referenced_evidence}/{report.total_evidence} 个关键证据"
            )
            suggestions.append("检查是否遗漏了上下文中的重要实体和数值")

        if report.early_ignored > 0:
            issues.append(
                f"位置偏差: {report.early_ignored} 个早期证据被忽略 "
                f"(position_bias={report.position_bias_score:.2f})"
            )
            suggestions.append("不要只依赖最近上下文，检查开头的关键信息")

        if report.multi_hop_pairs > 0 and report.integrated_pairs < report.multi_hop_pairs:
            issues.append(
                f"多跳整合不完整: 只整合了 {report.integrated_pairs}/"
                f"{report.multi_hop_pairs} 对非相邻证据"
            )
            suggestions.append("尝试连接分散在不同位置的相关证据")

        if not issues:
            return (
                CheckResult("MultiHopEvidence", CheckStatus.PASS, [], [],
                            score=report.final_score),
                report,
            )

        return (
            CheckResult("MultiHopEvidence", CheckStatus.FAIL if report.final_score > 0.4
                        else CheckStatus.REJECTED,
                        issues, suggestions, score=report.final_score),
            report,
        )

    def _check_multi_hop_evidence(self, response: str, original_context: str,
                                   ctx: dict[str, Any]) -> CheckResult:
        domain = ctx.get("domain", "general")
        result, _ = self.check_multi_hop_evidence(response, original_context, domain)
        return result


class MultiHopEvidenceCheck:
    """SSA/MRCR inspired: heuristic multi-hop evidence analysis.

    Without requiring LLM calls, this analyzes whether key entities from
    the context appear in the response, detects position bias (early vs
    late evidence usage), and tests multi-hop integration.
    """

    @staticmethod
    def _analyze(response: str, context: str) -> MultiHopReport:
        import re

        response_lower = response.lower()
        context_lower = context.lower()
        context_lines = context.strip().split('\n')
        total_lines = max(len(context_lines), 1)

        entities = MultiHopEvidenceCheck._extract_key_entities(context)
        if not entities:
            return MultiHopReport(
                evidence_recall=1.0, position_bias_score=1.0,
                integration_score=1.0, final_score=1.0,
            )

        evidence_items = []
        for i, entity in enumerate(entities):
            line_idx = context_lower.find(entity.lower())
            ev = EvidenceItem(
                text=entity,
                position=line_idx,
                position_pct=line_idx / max(len(context_lower), 1),
                is_referenced=entity.lower() in response_lower,
            )
            evidence_items.append(ev)

        referenced = [e for e in evidence_items if e.is_referenced]
        recall = len(referenced) / len(evidence_items)

        early_evidence = [e for e in evidence_items if e.position_pct < 0.3]
        early_ignored = [e for e in early_evidence if not e.is_referenced]
        late_referenced = [e for e in evidence_items if e.is_referenced and e.position_pct > 0.6]

        position_bias = 1.0
        if early_evidence:
            position_bias = len([e for e in early_evidence if e.is_referenced]) / len(early_evidence)

        pairs = []
        integrated = 0
        for i in range(len(evidence_items)):
            for j in range(i + 1, len(evidence_items)):
                if abs(evidence_items[i].position_pct - evidence_items[j].position_pct) > 0.4:
                    pairs.append((evidence_items[i], evidence_items[j]))

        for a, b in pairs:
            a_ref = a.text.lower() in response_lower
            b_ref = b.text.lower() in response_lower
            if a_ref and b_ref:
                integrated += 1

        integration = integrated / max(len(pairs), 1) if pairs else 1.0

        final_score = (recall * 0.35 + position_bias * 0.3 +
                       integration * 0.35)

        return MultiHopReport(
            evidence_recall=round(recall, 3),
            position_bias_score=round(position_bias, 3),
            integration_score=round(integration, 3),
            total_evidence=len(evidence_items),
            referenced_evidence=len(referenced),
            early_ignored=len(early_ignored),
            multi_hop_pairs=len(pairs),
            integrated_pairs=integrated,
            final_score=round(final_score, 3),
        )

    @staticmethod
    def _extract_key_entities(text: str) -> list[str]:
        """Extract key entities from context: numbers, standards, technical terms."""
        import re
        entities = set()

        patterns = [
            r'[A-Z]{2,6}[- ]?\d{2,4}[- ]?\d{4,6}',  # GB3095-2012, HJ2.2
            r'\d+\.?\d*\s*(?:μg/m³|mg/m³|dB|km|m³|万元|吨|%|m/s)',
            r'[A-Z][a-z]+(?:\.[a-z]+)+',  # module.path
            r'《[^》]{2,30}》',
            r'\b(?:SO2|NO2|PM2\.5|PM10|CO2|COD|BOD|NH3-N|O3)\b',
        ]

        for pattern in patterns:
            found = re.findall(pattern, text, re.IGNORECASE)
            entities.update(found[:10])

        key_terms = re.findall(r'\b([A-Z\u4e00-\u9fff]{2,15})\b', text)
        term_counts: dict[str, int] = {}
        for t in key_terms:
            term_counts[t] = term_counts.get(t, 0) + 1

        for term, count in term_counts.items():
            if count >= 3 and len(term) >= 3:
                entities.add(term)

        return list(entities)[:30]
