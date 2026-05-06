"""Claim Verification — AutoResearchClaw-inspired anti-fabrication system.

Extracts factual claims from AI-generated text and cross-references them
against the KnowledgeBase to detect unverified or fabricated statements.

Usage:
    from livingtree.observability.claim_checker import get_claim_checker
    cc = get_claim_checker()
    result = cc.verify_output("The system handles 10,000 users daily.")
"""

from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

CLAIMS_LOG = Path(".livingtree/claims")


class Claim(BaseModel):
    """A factual claim extracted from text."""
    id: str
    text: str
    source: str = "output"  # "output" | "thinking" | "plan"
    confidence: float = 0.5  # 0.0–1.0 extraction confidence
    extracted_at: float = 0.0


class VerificationResult(BaseModel):
    """Result of verifying a claim against known sources."""
    claim_id: str
    verified: bool = False
    verdict: str = "unverified"  # confirmed | plausible | unverified | contradicted
    confidence: float = 0.0
    evidence: list[str] = Field(default_factory=list)
    kb_matches: list[dict] = Field(default_factory=list)
    score: float = 0.0  # 0.0–1.0 overall verification score


class ClaimChecker:
    """Anti-fabrication claim verification against KnowledgeBase and references."""

    def __init__(self):
        CLAIMS_LOG.mkdir(parents=True, exist_ok=True)
        self._last_results: list[VerificationResult] = []
        self._last_claims: list[Claim] = []

    # ═══ Extraction ═══

    def extract_claims(self, text: str, source: str = "output") -> list[Claim]:
        """Extract factual claims from text using heuristics.

        Identifies sentences that contain:
        - Numbers with units (claims about quantities)
        - Proper nouns (claims about specific entities)
        - Citation patterns [N] or (Author, Year)
        - Comparative assertions (more/less than, is/are)
        """
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

    # ═══ Verification ═══

    def verify_against_kb(
        self, claims: list[Claim], knowledge_base=None, top_k: int = 5,
    ) -> list[VerificationResult]:
        """Verify claims by searching the KnowledgeBase for supporting evidence.

        Uses simple word overlap to determine support level:
        - > 0.5 overlap → confirmed
        - 0.2–0.5 overlap → plausible
        - < 0.2 overlap → unverified
        """
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

            # Determine verdict
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
        """Verify a single claim against a list of reference strings."""
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
        """End-to-end verification: extract claims → verify against KB and references.

        Returns:
            dict with claims, verification_results, counts, and overall score.
        """
        claims = self.extract_claims(text, source="output")
        self._last_claims = claims

        if not claims:
            return {
                "claims": [], "verified_count": 0, "unverified_count": 0,
                "overall_score": 1.0, "verification_results": [],
            }

        # Primary: verify against KB
        results = self.verify_against_kb(claims, knowledge_base)

        # Secondary: cross-check with references if provided
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
        """Generate a summary report of the last verification run."""
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

    # ═══ Helpers ═══

    @staticmethod
    def _word_overlap(text_a: str, text_b: str) -> float:
        """Compute simple word overlap ratio between two texts."""
        words_a = set(re.findall(r'\w+', text_a.lower()))
        words_b = set(re.findall(r'\w+', text_b.lower()))
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        return len(intersection) / min(len(words_a), len(words_b))


# ── Singleton ──

CLAIM_CHECKER = ClaimChecker()


def get_claim_checker() -> ClaimChecker:
    """Get the global ClaimChecker singleton."""
    return CLAIM_CHECKER
