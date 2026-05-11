"""Conversation DNA — Extract and recombine successful session patterns.

Every successful LifeEngine cycle leaves "genetic material" — the intent,
pipeline pattern, and outcome. When a similar task arises, the system
synthesizes approaches from past successful sessions rather than starting
from scratch.

Usage:
    dna = ConversationDNA(world)
    
    # Auto-called after each successful cycle:
    dna.record(session_id, intent, ctx.plan, ctx.metadata["success_rate"])
    
    # Auto-called when similar intent detected:
    suggestions = dna.suggest(similar_intent)
"""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class SessionGene:
    id: str
    intent: str
    domain: str
    plan_pattern: list[str]
    success_rate: float
    tokens_used: int
    pipeline_steps: list[str]
    key_insights: list[str]
    timestamp: str
    vectors: list[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "intent": self.intent, "domain": self.domain,
            "plan_pattern": self.plan_pattern, "success_rate": self.success_rate,
            "tokens_used": self.tokens_used, "pipeline_steps": self.pipeline_steps,
            "key_insights": self.key_insights, "timestamp": self.timestamp,
        }


class ConversationDNA:

    STORE_PATH = ".livingtree/conversation_dna.json"
    MIN_SUCCESS_RATE = 0.7
    MAX_GENES = 500
    SIMILARITY_THRESHOLD = 0.6

    def __init__(self, world: Any = None):
        self._world = world
        self._genes: list[SessionGene] = []
        self._load()

    def record(
        self,
        session_id: str,
        intent: str,
        plan: list[dict],
        success_rate: float,
        tokens_used: int = 0,
        pipeline_steps: list[str] | None = None,
        key_insights: list[str] | None = None,
    ) -> SessionGene | None:
        if success_rate < self.MIN_SUCCESS_RATE:
            return None

        from datetime import datetime, timezone

        plan_names = [s.get("name", s.get("action", "?")) for s in plan]
        gene = SessionGene(
            id=session_id,
            intent=intent or "general",
            domain=self._detect_domain(intent or ""),
            plan_pattern=plan_names,
            success_rate=success_rate,
            tokens_used=tokens_used,
            pipeline_steps=pipeline_steps or plan_names,
            key_insights=key_insights or [],
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        self._genes.append(gene)
        if len(self._genes) > self.MAX_GENES:
            self._genes = self._genes[-self.MAX_GENES:]

        self._save()
        logger.debug(f"DNA recorded: {session_id} ({gene.domain}, {success_rate:.0%})")
        return gene

    def suggest(self, intent: str, domain: str = "") -> dict:
        domain = domain or self._detect_domain(intent)
        candidates = [g for g in self._genes if g.domain == domain or domain in g.intent]

        if len(candidates) < 3:
            candidates = self._genes[-10:]

        if len(candidates) < 2:
            return {"found": False, "message": "Not enough session history yet"}

        sorted_candidates = sorted(candidates, key=lambda g: g.success_rate, reverse=True)

        top = sorted_candidates[:5]
        merged_plan = self._merge_plans([g.plan_pattern for g in top])
        best_pipeline = self._best_pipeline(top)
        insights = list(set(i for g in top for i in g.key_insights))[:5]

        return {
            "found": True,
            "domain": domain,
            "based_on_sessions": len(candidates),
            "top_sessions": [g.id for g in top],
            "suggested_plan": merged_plan,
            "suggested_pipeline": best_pipeline,
            "key_insights": insights,
            "avg_success_rate": sum(g.success_rate for g in top) / len(top),
        }

    # ═══ SSDataBench: Association Fidelity Check ═══

    def check_association_fidelity(self) -> dict:
        """SSDataBench-style fidelity check on conversation DNA gene pool.

        From paper: synthetic data often distorts real-world association
        structures. Selection bias from SIMILARITY_THRESHOLD (0.6) may
        systematically filter certain patterns, creating a distorted gene pool.

        Checks:
          1. Domain distribution skew
          2. Success rate vs pipeline complexity association
          3. Temporal pattern drift (are older genes being crowded out?)

        Returns:
            Fidelity report dict
        """
        import numpy as np

        if len(self._genes) < 20:
            return {
                "status": "insufficient_data",
                "message": "Need >=20 genes for fidelity analysis (have {}).".format(len(self._genes)),
            }

        # 1. Domain distribution entropy
        domain_counts = Counter(g.domain for g in self._genes)
        total = len(self._genes)
        domain_entropy = -sum(
            (c/total) * math.log(c/total) for c in domain_counts.values() if c > 0
        )
        max_entropy = math.log(max(len(domain_counts), 1))
        domain_diversity = domain_entropy / max(max(domain_counts.values(), default=0), 1) if len(domain_counts) > 1 else 1.0
        normalized_entropy = domain_entropy / max(max_entropy, 0.001)

        # Dominant domain risk
        top_domain, top_count = domain_counts.most_common(1)[0] if domain_counts else ("none", 0)
        dominant_ratio = top_count / max(total, 1)

        # 2. Pipeline complexity vs success rate
        complexities = [len(g.pipeline_steps) for g in self._genes]
        successes = [g.success_rate for g in self._genes]
        if len(complexities) > 2:
            corr = float(np.corrcoef(complexities, successes)[0, 1])
        else:
            corr = 0.0

        # 3. Selection bias: are low-success genes being purged?
        # Success rate distribution
        success_bins = Counter(
            "high" if g.success_rate >= 0.8 else
            "medium" if g.success_rate >= 0.6 else
            "low"
            for g in self._genes
        )
        low_ratio = success_bins.get("low", 0) / max(total, 1)

        # 4. Association distortion risk
        association_distortion_risk = (
            dominant_ratio > 0.5 or   # One domain dominates
            normalized_entropy < 0.5 or  # Low diversity
            abs(corr) < 0.05           # No meaningful complexity-success relationship
        )

        recommendations = []
        if dominant_ratio > 0.5:
            recommendations.append(
                "Dominant domain '{}' occupies {:.0f}% of gene pool. "
                "Consider lowering MIN_SUCCESS_RATE or SIMILARITY_THRESHOLD "
                "to preserve domain diversity.".format(top_domain, dominant_ratio*100)
            )
        if normalized_entropy < 0.5:
            recommendations.append(
                "Low domain diversity (entropy ratio={:.3f}). "
                "Selection bias may be filtering out minority domains. "
                "Consider stratified gene retention.".format(normalized_entropy)
            )
        if abs(corr) < 0.05:
            recommendations.append(
                "No detectable association between pipeline complexity and "
                "success rate. This may indicate randomness in gene recording "
                "or systematic distortion in success rate measurement."
            )
        if not recommendations:
            recommendations.append("Gene pool association structure appears healthy.")

        return {
            "status": "analyzed",
            "total_genes": total,
            "domain_count": len(domain_counts),
            "domain_distribution": dict(domain_counts.most_common()),
            "domain_diversity": round(domain_diversity, 3),
            "domain_entropy_ratio": round(normalized_entropy, 3),
            "dominant_domain": top_domain,
            "dominant_ratio": round(dominant_ratio, 3),
            "complexity_success_correlation": round(corr, 4),
            "low_success_ratio": round(low_ratio, 3),
            "association_distortion_risk": association_distortion_risk,
            "recommendations": recommendations,
        }

    def get_stats(self) -> dict:
        domains = {}
        for g in self._genes:
            domains[g.domain] = domains.get(g.domain, 0) + 1
        return {
            "total_genes": len(self._genes),
            "domains": domains,
            "avg_success_rate": sum(g.success_rate for g in self._genes) / max(len(self._genes), 1),
            "top_domain": max(domains, key=domains.get) if domains else "none",
        }

    @staticmethod
    def _detect_domain(text: str) -> str:
        t = text.lower()
        for kw, domain in [
            ("eia", "eia"), ("环评", "eia"), ("环境", "eia"),
            ("code", "code"), ("代码", "code"), ("编程", "code"),
            ("report", "report"), ("报告", "report"), ("文档", "report"),
            ("analyze", "analysis"), ("分析", "analysis"),
            ("emergency", "emergency"), ("应急", "emergency"),
            ("knowledge", "knowledge"), ("知识", "knowledge"),
            ("train", "training"), ("训练", "training"),
        ]:
            if kw in t:
                return domain
        return "general"

    @staticmethod
    def _merge_plans(plan_sets: list[list[str]]) -> list[str]:
        freq: dict[str, int] = {}
        positions: dict[str, list[int]] = {}
        for plan in plan_sets:
            for i, step in enumerate(plan):
                freq[step] = freq.get(step, 0) + 1
                positions.setdefault(step, []).append(i)

        sorted_steps = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        threshold = max(2, len(plan_sets) // 2 + 1)
        return [step for step, count in sorted_steps if count >= threshold][:8]

    @staticmethod
    def _best_pipeline(genes: list[SessionGene]) -> list[str]:
        all_steps = []
        for g in genes:
            all_steps.extend(g.pipeline_steps)
        seen = set()
        unique = []
        for s in all_steps:
            if s not in seen:
                seen.add(s)
                unique.append(s)
        return unique[:7]

    def _load(self) -> None:
        path = Path(self.STORE_PATH)
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for item in data:
                self._genes.append(SessionGene(**item))
            self._genes = self._genes[-self.MAX_GENES:]
            logger.debug(f"DNA loaded: {len(self._genes)} genes")
        except Exception as e:
            logger.debug(f"DNA load: {e}")

    def _save(self) -> None:
        path = Path(self.STORE_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps([g.to_dict() for g in self._genes], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
