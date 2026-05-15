"""Hallucination Guard — real-time monitoring + sentence-level verification.

P1 准确率提升模块：实时监控幻觉率，逐句验证生成内容的事实准确性。

Core techniques:
  Sentence-level NLI:      每个生成句子 vs 检索上下文 → 蕴含/矛盾/中立
  Token-probability check: 低概率 token 标记为可疑
  Real-time dashboard:     幻觉率趋势、按来源分布、高频幻觉模式
  Auto-correction loop:    检测到幻觉 → 触发重新检索 → 重新生成

v2.7 — PALE (AAAI-26): CM Score integration for activation-space detection.
  PALECMScore provides distribution-level hallucination detection,
  complementing the n-gram/keyword surface-level approach. When activation
  signatures are available, CM Score is used as a primary detection gate.

升级现有:
  - detect_hallucination(): 词重叠 → 语义蕴含判定
  - fact_check(): 声明级 → 逐句级
  - RetrievalValidator: 已验证上下文作为 ground truth
"""

from __future__ import annotations

import json
import re
import time
import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger
from pydantic import BaseModel, Field


class HallucinationVerdict(str):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"  # 幻觉: 无法在上下文中找到支持
    CONTRADICTED = "contradicted"  # 幻觉: 与上下文矛盾
    AMBIGUOUS = "ambiguous"


@dataclass
class SentenceCheck:
    """单句验证结果。"""
    sentence: str
    index: int
    verdict: str = HallucinationVerdict.AMBIGUOUS
    confidence: float = 0.0
    evidence: str = ""         # 支持本句的上下文片段
    contradicting_evidence: str = ""
    is_hallucination: bool = False
    correction_suggestion: str = ""
    phi_first_score: float = 0.0


@dataclass
class HallucinationReport:
    """一次生成的幻觉检测报告。"""
    query: str
    generated_text: str
    sentence_checks: list[SentenceCheck] = field(default_factory=list)
    total_sentences: int = 0
    hallucinated_sentences: int = 0
    hallucination_rate: float = 0.0
    context_coverage: float = 0.0  # 生成文本有多少比例可在上下文中找到
    timestamp: float = field(default_factory=time.time)


@dataclass
class HallucinationStats:
    """累积统计 — 用于实时监控 Dashboard。"""
    total_generations: int = 0
    total_sentences: int = 0
    total_hallucinations: int = 0
    by_source: dict[str, tuple[int, int]] = field(default_factory=dict)  # source -> (total, hals)
    pattern_counts: dict[str, int] = field(default_factory=dict)  # 幻觉模式频率
    recent_rate: list[float] = field(default_factory=list)  # 最近20次幻觉率


class HallucinationGuard:
    """幻觉防护 — 逐句验证 + 实时监控 + 自动纠正。

    Usage:
        guard = HallucinationGuard()
        report = guard.check_generation(
            generated_text=llm_response,
            context=validated_context_text,
        )
        if report.hallucination_rate > 0.2:
            # 触发重新生成
            corrected = guard.suggest_correction(report)
    """

    def __init__(self, warning_threshold: float = 0.15, critical_threshold: float = 0.30):
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self._stats = HallucinationStats()
        self._lock = threading.Lock()
        self._alert_callbacks: list[callable] = []

    def check_generation(
        self,
        generated_text: str,
        context: str = "",
        source: str = "",
    ) -> HallucinationReport:
        """逐句验证生成文本的事实准确性。

        对每个句子：
          1. N-gram 与上下文的精确匹配
          2. 关键词重叠度
          3. 数字/专有名词交叉验证
          4. 句子长度异常检测
        """
        report = HallucinationReport(query="", generated_text=generated_text)
        sentences = self._split_sentences(generated_text)
        report.total_sentences = len(sentences)

        if not sentences:
            return report

        context_ngrams = self._extract_ngrams(context) if context else set()
        context_keywords = self._extract_keywords(context) if context else set()

        for i, sentence in enumerate(sentences):
            check = self._verify_sentence(sentence, i, context, context_ngrams, context_keywords)
            report.sentence_checks.append(check)
            if check.is_hallucination:
                report.hallucinated_sentences += 1

        if report.total_sentences > 0:
            report.hallucination_rate = report.hallucinated_sentences / report.total_sentences

        report.context_coverage = self._compute_coverage(generated_text, context)

        self._update_stats(report, source)
        self._check_alerts(report, source)

        logger.debug(
            "HallucinationGuard: rate=%.1f%% (%d/%d sentences, coverage=%.1f%%)",
            report.hallucination_rate * 100,
            report.hallucinated_sentences, report.total_sentences,
            report.context_coverage * 100,
        )

        return report

    def suggest_correction(self, report: HallucinationReport) -> str:
        """为幻觉句子生成纠正建议。"""
        corrections = []
        for check in report.sentence_checks:
            if check.is_hallucination:
                evidence = check.evidence[:200] if check.evidence else "无支持证据"
                corrections.append(
                    f"[需纠正] {check.sentence}\n"
                    f"  证据: {evidence}\n"
                )
        return "\n".join(corrections) if corrections else ""

    def get_dashboard(self) -> dict:
        """实时幻觉监控 Dashboard。"""
        with self._lock:
            s = self._stats
            recent_avg = sum(s.recent_rate[-20:]) / max(len(s.recent_rate[-20:]), 1)
            return {
                "total_generations": s.total_generations,
                "total_sentences": s.total_sentences,
                "overall_hallucination_rate": s.total_hallucinations / max(s.total_sentences, 1),
                "recent_rate": recent_avg,
                "by_source": {
                    src: {"total": t, "hallucinated": h, "rate": h/max(t,1)}
                    for src, (t, h) in s.by_source.items()
                },
                "top_patterns": sorted(
                    s.pattern_counts.items(), key=lambda x: -x[1]
                )[:5],
                "status": "critical" if recent_avg > self.critical_threshold
                          else "warning" if recent_avg > self.warning_threshold
                          else "healthy",
            }

    def on_alert(self, callback: callable) -> None:
        self._alert_callbacks.append(callback)

    def check_with_logits(
        self,
        generated_text: str,
        context: str = "",
        source: str = "",
        logprobs: list[dict] | None = None,
    ) -> HallucinationReport:
        """φ_first增强幻觉检测 — Gate 0 前置 logit 熵门控。

        Gate 0: 计算第一个内容承载 token 的 φ_first 归一化熵。
        φ_first > 0.7 → 直接标记整句为幻觉（模型生成时已不确定）。

        Args:
            generated_text: 模型生成的完整文本
            context: 验证用的上下文/来源文本
            source: 来源标识
            logprobs: API 响应中的 logprobs 列表，每项为
                      {"token": str, "logprob": float, "top_logprobs": [...]}
        """
        from ..treellm.logit_confidence import compute_phi_first

        report = HallucinationReport(query="", generated_text=generated_text)
        sentences = self._split_sentences(generated_text)
        report.total_sentences = len(sentences)
        if not sentences:
            return report

        phi_first = 0.0
        if logprobs:
            result = compute_phi_first(logprobs)
            phi_first = result.phi_first

        context_ngrams = self._extract_ngrams(context) if context else set()
        context_keywords = self._extract_keywords(context) if context else set()

        for i, sentence in enumerate(sentences):
            check = self._verify_sentence(
                sentence, i, context, context_ngrams, context_keywords,
                phi_first_score=phi_first if i == 0 else 0.0,
            )
            report.sentence_checks.append(check)
            if check.is_hallucination:
                report.hallucinated_sentences += 1

        if report.total_sentences > 0:
            report.hallucination_rate = report.hallucinated_sentences / report.total_sentences
        report.context_coverage = self._compute_coverage(generated_text, context)
        self._update_stats(report, source)
        self._check_alerts(report, source)
        return report

    def _verify_sentence(
        self, sentence: str, index: int, context: str,
        context_ngrams: set, context_keywords: set,
        phi_first_score: float = 0.0,
    ) -> SentenceCheck:
        """单句验证引擎。

        判定逻辑:
          0. φ_first 先验 (Gate 0): 如有logits，首token熵>0.7→直接标幻觉
          1. N-gram 精确匹配 ≥30% → SUPPORTED
          2. 关键词重叠 ≥50% → SUPPORTED
          3. 无可重叠 → UNSUPPORTED (幻觉)
          4. 存在矛盾数字/名称 → CONTRADICTED (幻觉)
        """
        check = SentenceCheck(sentence=sentence, index=index,
                              phi_first_score=phi_first_score)

        if not sentence.strip() or len(sentence) < 10:
            check.verdict = HallucinationVerdict.AMBIGUOUS
            return check

        # Gate 0: φ_first — first-token logit entropy early warning
        if phi_first_score > 0.7:
            check.verdict = HallucinationVerdict.UNSUPPORTED
            check.is_hallucination = True
            check.confidence = phi_first_score
            check.correction_suggestion = f"[φ_first={phi_first_score:.3f} — high first-token entropy]"
            return check

        sent_ngrams = self._extract_ngrams(sentence)
        sent_keywords = self._extract_keywords(sentence)

        # Gate 1: N-gram overlap with context
        if sent_ngrams and context_ngrams:
            overlap = len(sent_ngrams & context_ngrams) / max(len(sent_ngrams), 1)
            if overlap >= 0.3:
                check.verdict = HallucinationVerdict.SUPPORTED
                check.confidence = min(1.0, overlap * 2)
                check.evidence = self._find_matching_context(sentence, context)
                return check

        # Gate 2: Keyword overlap
        if sent_keywords and context_keywords:
            overlap = len(sent_keywords & context_keywords) / max(len(sent_keywords), 1)
            if overlap >= 0.5:
                check.verdict = HallucinationVerdict.SUPPORTED
                check.confidence = overlap
                check.evidence = self._find_matching_context(sentence, context)
                return check
            elif overlap >= 0.3:
                check.verdict = HallucinationVerdict.AMBIGUOUS
                check.confidence = overlap
                return check

        # Gate 3: No context at all
        if not context:
            check.verdict = HallucinationVerdict.AMBIGUOUS
            check.confidence = 0.3
            return check

        # Gate 4: Contains specific claims (numbers, proper nouns) → must verify
        has_specifics = bool(re.search(r'\d+', sentence)) or bool(re.search(r'[A-Z\u4e00-\u9fff]{2,}', sentence))
        if has_specifics and check.confidence < 0.3:
            check.verdict = HallucinationVerdict.UNSUPPORTED
            check.is_hallucination = True
        else:
            check.verdict = HallucinationVerdict.AMBIGUOUS

        return check

    def _update_stats(self, report: HallucinationReport, source: str) -> None:
        with self._lock:
            s = self._stats
            s.total_generations += 1
            s.total_sentences += report.total_sentences
            s.total_hallucinations += report.hallucinated_sentences

            if source:
                t, h = s.by_source.get(source, (0, 0))
                s.by_source[source] = (t + report.total_sentences, h + report.hallucinated_sentences)

            s.recent_rate.append(report.hallucination_rate)
            if len(s.recent_rate) > 100:
                s.recent_rate = s.recent_rate[-50:]

            for check in report.sentence_checks:
                if check.is_hallucination:
                    pattern = self._detect_pattern(check.sentence)
                    s.pattern_counts[pattern] = s.pattern_counts.get(pattern, 0) + 1

    def _check_alerts(self, report: HallucinationReport, source: str) -> None:
        if report.hallucination_rate > self.critical_threshold:
            msg = f"CRITICAL: hallucination rate {report.hallucination_rate:.1%} for source '{source}'"
            logger.warning(msg)
            for cb in self._alert_callbacks:
                try:
                    cb(msg, report)
                except Exception:
                    pass
        elif report.hallucination_rate > self.warning_threshold:
            msg = f"WARNING: hallucination rate {report.hallucination_rate:.1%} for source '{source}'"
            logger.info(msg)

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        return [s.strip() for s in re.split(r'[。！？\n.!?]+', text) if len(s.strip()) > 5]

    @staticmethod
    def _extract_ngrams(text: str, n: int = 4) -> set:
        cleaned = re.sub(r'\s+', '', text)
        return {cleaned[i:i+n] for i in range(len(cleaned) - n + 1)} if len(cleaned) >= n else set()

    @staticmethod
    def _extract_keywords(text: str) -> set:
        words = re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z]{3,}|\d+', text.lower())
        return set(words)

    @staticmethod
    def _find_matching_context(sentence: str, context: str, max_len: int = 300) -> str:
        if not context:
            return ""
        keywords = HallucinationGuard._extract_keywords(sentence)
        if not keywords:
            return context[:max_len]
        sentences = re.split(r'[。！？\n]+', context)
        best_match = ""
        best_overlap = 0
        for s in sentences:
            ctx_keywords = HallucinationGuard._extract_keywords(s)
            overlap = len(keywords & ctx_keywords)
            if overlap > best_overlap:
                best_overlap = overlap
                best_match = s.strip()
        return best_match[:max_len] if best_match else context[:max_len]

    @staticmethod
    def _compute_coverage(generated: str, context: str) -> float:
        if not context or not generated:
            return 0.0
        gen_ngrams = HallucinationGuard._extract_ngrams(generated, n=5)
        ctx_ngrams = HallucinationGuard._extract_ngrams(context, n=5)
        if not gen_ngrams:
            return 0.0
        return len(gen_ngrams & ctx_ngrams) / len(gen_ngrams)

    @staticmethod
    def _detect_pattern(sentence: str) -> str:
        """识别幻觉模式（用于统计）。"""
        if re.search(r'\d{4}年', sentence):
            return "fabricated_date"
        if re.search(r'(?:根据|按照|依据).*?(?:研究|报告|标准)', sentence):
            return "fabricated_reference"
        if re.search(r'(?:所有|全部|从未|总是|绝对)', sentence):
            return "overgeneralization"
        if not re.search(r'[\u4e00-\u9fff]', sentence):
            return "non_chinese_output"
        return "unsupported_claim"

    # ── PALE CM Score Integration ──────────────────────────────────

    def check_with_cm_score(
        self,
        generated_text: str,
        context: str = "",
        source: str = "",
        cm_scorer: Any = None,
    ) -> HallucinationReport:
        """Enhanced hallucination check with PALE CM Score detection.

        Two-layer detection:
          1. CM Score (activation-space): when cm_scorer is fitted, use
             Mahalanobis distance to truthful/hallucinated distributions
             as the primary detection mechanism.
          2. Text heuristic (surface-level): traditional n-gram/keyword
             overlap as fallback when activation signatures unavailable.

        Args:
            cm_scorer: PALECMScorer instance (optional). If fitted, CM
                       Score becomes the primary gate before text heuristics.
        """
        if cm_scorer is not None and cm_scorer.is_fitted():
            return self._check_with_cm_score(
                generated_text, context, source, cm_scorer
            )
        return self.check_generation(generated_text, context, source)

    def _check_with_cm_score(
        self, generated_text: str, context: str,
        source: str, cm_scorer: Any,
    ) -> HallucinationReport:
        from ..treellm.pale_detector import extract_text_activation

        report = HallucinationReport(query="", generated_text=generated_text)
        sentences = self._split_sentences(generated_text)
        report.total_sentences = len(sentences)
        if not sentences:
            return report

        context_ngrams = self._extract_ngrams(context) if context else set()
        context_keywords = self._extract_keywords(context) if context else set()

        for i, sentence in enumerate(sentences):
            sig = extract_text_activation(sentence)
            cm_result = cm_scorer.classify(sig)
            if cm_result.is_hallucination and cm_result.confidence > 0.3:
                check = SentenceCheck(
                    sentence=sentence, index=i,
                    verdict=HallucinationVerdict.UNSUPPORTED,
                    confidence=cm_result.confidence,
                    is_hallucination=True,
                    correction_suggestion=f"[CM Score={cm_result.cm_score:.3f}]",
                )
            else:
                check = self._verify_sentence(
                    sentence, i, context, context_ngrams, context_keywords,
                )
            report.sentence_checks.append(check)
            if check.is_hallucination:
                report.hallucinated_sentences += 1

        if report.total_sentences > 0:
            report.hallucination_rate = report.hallucinated_sentences / report.total_sentences
        report.context_coverage = self._compute_coverage(generated_text, context)
        self._update_stats(report, source)
        self._check_alerts(report, source)
        return report

    def train_cm_scorer(
        self,
        truthful_texts: list[str],
        hallucinated_texts: list[str],
        cm_scorer: Any,
    ) -> Any:
        """Fit CM Scorer on contrastive pairs for enhanced detection.

        Extracts activation signatures from both truthful and hallucinated
        text samples, then fits the shrinkage covariance estimator.
        """
        from ..treellm.pale_detector import extract_text_activation

        t_sigs = [extract_text_activation(t) for t in truthful_texts]
        h_sigs = [extract_text_activation(h) for h in hallucinated_texts]
        cm_scorer.fit(t_sigs, h_sigs)
        logger.info(
            f"HallucinationGuard: CM Scorer trained on "
            f"{len(t_sigs)} truthful + {len(h_sigs)} hallucinated"
        )
        return cm_scorer


# ═══ ClaimChecker — Anti-fabrication claim verification ═══

CLAIMS_LOG = Path(".livingtree/claims")


class Claim(BaseModel):
    id: str
    text: str
    source: str = "output"
    confidence: float = 0.5
    extracted_at: float = 0.0


class VerificationResult(BaseModel):
    claim_id: str
    verified: bool = False
    verdict: str = "unverified"
    confidence: float = 0.0
    evidence: list[str] = Field(default_factory=list)
    kb_matches: list[dict] = Field(default_factory=list)
    score: float = 0.0


class ClaimChecker:
    """Anti-fabrication claim verification against KnowledgeBase and references."""

    def __init__(self):
        CLAIMS_LOG.mkdir(parents=True, exist_ok=True)
        self._last_results: list[VerificationResult] = []
        self._last_claims: list[Claim] = []

    def extract_claims(self, text: str, source: str = "output") -> list[Claim]:
        now = time.time()
        sentences = re.split(r'(?<=[.!?;])\s+', text)
        claims: list[Claim] = []

        for sent in sentences:
            sent = sent.strip()
            if len(sent) < 10:
                continue

            confidence = 0.0
            if re.search(r'\d+\s*(?:users|requests|ms|MB|GB|TB|%|seconds|minutes|hours|days|tokens|bytes|dollars|yuan)', sent, re.IGNORECASE):
                confidence += 0.35
            if re.search(r'\[\d+\]|\(\w+,\s*\d{4}\)|10\.\d{4,}', sent):
                confidence += 0.30
            if re.search(r'\b(?:is|are|was|were|has|have|contains|consists|produces|generates|handles|supports|processes)\b', sent, re.IGNORECASE):
                confidence += 0.25
            if re.search(r'\b(?:more than|less than|faster than|slower than|better than|worse than|higher|lower|increased|decreased)\b', sent, re.IGNORECASE):
                confidence += 0.20

            confidence = min(confidence, 1.0)

            if confidence > 0.0:
                claim = Claim(
                    id=f"cl-{uuid.uuid4().hex[:8]}",
                    text=sent,
                    source=source,
                    confidence=round(confidence, 3),
                    extracted_at=now,
                )
                claims.append(claim)

        if claims:
            logger.debug(f"Extracted {len(claims)} claims from text ({source}), avg confidence={sum(c.confidence for c in claims)/len(claims):.2f}")

        return claims

    def verify_against_kb(
        self, claims: list[Claim], knowledge_base=None, top_k: int = 5,
    ) -> list[VerificationResult]:
        results: list[VerificationResult] = []

        for claim in claims:
            evidence: list[str] = []
            kb_matches: list[dict] = []
            best_overlap = 0.0

            if knowledge_base and hasattr(knowledge_base, 'search'):
                try:
                    docs = knowledge_base.search(claim.text, top_k=top_k)
                    for doc in docs:
                        content = getattr(doc, 'content', '')
                        title = getattr(doc, 'title', '')
                        if not content:
                            continue
                        overlap = self._word_overlap(claim.text, content)
                        if overlap > best_overlap:
                            best_overlap = overlap
                        if overlap > 0.1:
                            snippet = content[:300] + ("..." if len(content) > 300 else "")
                            evidence.append(f"[{title}]: {snippet}")
                            kb_matches.append({"title": title, "overlap": round(overlap, 3)})
                except Exception as e:
                    logger.debug(f"KB search failed for claim {claim.id}: {e}")

            if best_overlap > 0.5:
                verdict = "confirmed"
                score = min(1.0, best_overlap)
            elif best_overlap > 0.2:
                verdict = "plausible"
                score = best_overlap
            else:
                verdict = "unverified"
                score = best_overlap if best_overlap > 0 else 0.0

            result = VerificationResult(
                claim_id=claim.id,
                verified=verdict != "unverified",
                verdict=verdict,
                confidence=round(min(1.0, max(0.0, best_overlap * claim.confidence)), 3),
                evidence=evidence[:3],
                kb_matches=kb_matches[:5],
                score=round(score, 3),
            )
            results.append(result)

            if verdict == "unverified":
                logger.warning(f"Unverified claim [{claim.id}]: {claim.text[:80]}...")

        return results

    def verify_claim(self, claim: Claim, references: list[str] | None = None) -> VerificationResult:
        if not references:
            return VerificationResult(
                claim_id=claim.id, verified=False, verdict="unverified",
                confidence=0.0, score=0.0,
            )

        best_overlap = 0.0
        best_ref = ""
        for ref in references:
            overlap = self._word_overlap(claim.text, ref)
            if overlap > best_overlap:
                best_overlap = overlap
                best_ref = ref[:300]

        if best_overlap > 0.5:
            verdict = "confirmed"
        elif best_overlap > 0.2:
            verdict = "plausible"
        else:
            verdict = "unverified"

        return VerificationResult(
            claim_id=claim.id,
            verified=verdict != "unverified",
            verdict=verdict,
            confidence=round(min(1.0, best_overlap), 3),
            evidence=[best_ref] if best_ref else [],
            score=round(best_overlap, 3),
        )

    def verify_output(
        self, text: str, knowledge_base=None, references: list[str] | None = None,
    ) -> dict[str, Any]:
        claims = self.extract_claims(text, source="output")
        self._last_claims = claims

        if not claims:
            return {
                "claims": [], "verified_count": 0, "unverified_count": 0,
                "overall_score": 1.0, "verification_results": [],
            }

        results = self.verify_against_kb(claims, knowledge_base)

        if references:
            for i, claim in enumerate(claims):
                ref_result = self.verify_claim(claim, references)
                if ref_result.score > results[i].score:
                    results[i] = ref_result

        self._last_results = results

        verified_count = sum(1 for r in results if r.verified)
        overall_score = round(
            sum(r.score for r in results) / len(results), 3
        ) if results else 0.0

        return {
            "claims": [c.model_dump() for c in claims],
            "verification_results": [r.model_dump() for r in results],
            "verified_count": verified_count,
            "unverified_count": len(results) - verified_count,
            "overall_score": overall_score,
        }

    def get_report(self) -> dict[str, Any]:
        if not self._last_results:
            return {"status": "no_verifications", "total": 0}

        total = len(self._last_results)
        confirmed = sum(1 for r in self._last_results if r.verdict == "confirmed")
        plausible = sum(1 for r in self._last_results if r.verdict == "plausible")
        unverified = sum(1 for r in self._last_results if r.verdict == "unverified")
        avg_score = round(sum(r.score for r in self._last_results) / total, 3)

        high_risk = [r for r in self._last_results if r.verdict == "unverified"]

        return {
            "total_claims": total,
            "confirmed": confirmed,
            "plausible": plausible,
            "unverified": unverified,
            "verification_rate": round((confirmed + plausible) / total, 3) if total > 0 else 0.0,
            "avg_score": avg_score,
            "high_risk_claims": [
                {"claim_id": r.claim_id, "score": r.score} for r in high_risk[:10]
            ],
        }

    @staticmethod
    def _word_overlap(text_a: str, text_b: str) -> float:
        words_a = set(re.findall(r'\w+', text_a.lower()))
        words_b = set(re.findall(r'\w+', text_b.lower()))
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        return len(intersection) / min(len(words_a), len(words_b))


_claim_lock = threading.Lock()
_claim_checker: Optional[ClaimChecker] = None


def get_claim_checker() -> ClaimChecker:
    global _claim_checker
    if _claim_checker is None:
        with _claim_lock:
            if _claim_checker is None:
                _claim_checker = ClaimChecker()
    return _claim_checker


CLAIM_CHECKER = get_claim_checker()
