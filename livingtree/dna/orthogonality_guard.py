"""Orthogonality Guard — unified Weight Vector Orthogonality enforcement.

OrthoReg (CVPR 2026, arXiv:2604.17078) Key insight:
  TFS → WVO → WD

Where:
  - TFS (Task-Feature Specialization): root cause, abstract
  - WVO (Weight Vector Orthogonality): observable geometric consequence
  - WD (Weight Disentanglement): desired outcome — no cross-task interference

This guard enforces WVO as a proxy for TFS, preventing module/skill/knowledge
interference before it manifests as performance degradation.

Three-stage enforcement:
  1. check(): Measure orthogonality of a new vector against existing ones
  2. enforce(): Apply OrthoReg-style penalty to bring vector toward orthogonal
  3. audit(): System-wide orthogonality health report

Integration points:
  - hypergraph_store.orthogonal_insert(): guard.check() before inserting
  - skill_hub.skill_orthogonality_score(): guard.check() before installing
  - emergence_detector.organ_interference_matrix(): guard.audit() for organs
  - system_sde.organ_coupling_heatmap(): guard.audit() for SDE trajectories
  - autonomous_core._verify_disentanglement(): guard.audit() in Audit phase
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


# ═══════════════════════════════════════════════════════════════════
# Data Types
# ═══════════════════════════════════════════════════════════════════

@dataclass
class OrthogonalityReport:
    """Result of an orthogonality check on a single vector."""
    vector_id: str
    max_cosine_similarity: float       # Highest pairwise cos_sim found
    is_orthogonal: bool                 # True if max_cos ≤ threshold
    overlapping_with: str = ""          # ID of the most similar existing vector
    threshold: float = 0.3              # The threshold used for this check
    recommendation: str = ""


@dataclass
class AuditReport:
    """System-wide orthogonality health audit.

    Aggregates pairwise orthogonality across all tracked modules.
    """
    timestamp: float = field(default_factory=time.time)
    total_vectors: int = 0
    orthogonal_count: int = 0          # Vectors passing the ≤threshold check
    interfering_count: int = 0         # Vectors with cos_sim > threshold
    mean_pairwise_cosine: float = 0.0
    max_pairwise_cosine: float = 0.0
    ortho_health_score: float = 1.0    # 1.0 = all orthogonal, 0.0 = all overlapping
    interpretation: str = ""


# ═══════════════════════════════════════════════════════════════════
# OrthogonalityGuard
# ═══════════════════════════════════════════════════════════════════

class OrthogonalityGuard:
    """Unified orthogonality enforcement for the LivingTree system.

    Wraps the cosine-similarity-based checks used across the system into
    a single interface with consistent thresholds and reporting.

    Usage:
        guard = OrthogonalityGuard(threshold=0.3)
        report = guard.check(new_vector, existing_vectors, vector_id="skill_X")
        if report.is_orthogonal:
            # safe to insert / install / activate
        else:
            # reject or apply guard.enforce() penalty
    """

    def __init__(self, threshold: float = 0.3):
        """
        Args:
            threshold: Maximum allowed cosine similarity before a vector
                       is flagged as interfering. Default 0.3 ≈ 72° angle.
                       Maps to OrthoReg's WVO enforcement level.
        """
        self._threshold = threshold
        self._reports: list[OrthogonalityReport] = []

    @property
    def threshold(self) -> float:
        return self._threshold

    def set_threshold(self, value: float):
        """Dynamically adjust orthogonality strictness. Lower = stricter."""
        self._threshold = max(0.0, min(1.0, value))

    # ── Check (single vector) ──

    def check(
        self,
        new_vector: list[float],
        existing_vectors: dict[str, list[float]],
        vector_id: str = "unknown",
    ) -> OrthogonalityReport:
        """Check orthogonality of a new vector against existing ones.

        OrthoReg equivalence: computing WᵀW for a single new weight column.

        Args:
            new_vector: The vector to check (flat list of floats).
            existing_vectors: dict of {id: vector} for comparison.
            vector_id: Identifier for the new vector (for reporting).

        Returns:
            OrthogonalityReport with max_cosine and pass/fail status.
        """
        if not existing_vectors:
            report = OrthogonalityReport(
                vector_id=vector_id,
                max_cosine_similarity=0.0,
                is_orthogonal=True,
                recommendation="no existing vectors — safe to insert",
            )
            self._reports.append(report)
            return report

        max_cos = 0.0
        most_similar = ""

        for eid, evec in existing_vectors.items():
            cos = self._cosine_similarity(new_vector, evec)
            if cos > max_cos:
                max_cos = cos
                most_similar = eid

        is_ortho = max_cos <= self._threshold

        if is_ortho:
            rec = f"Orthogonal (max_cos={max_cos:.4f} ≤ {self._threshold}). Safe."
        else:
            rec = (
                f"INTERFERENCE detected with '{most_similar}' "
                f"(cos={max_cos:.4f} > {self._threshold}). "
                f"Apply enforce() to project toward orthogonal."
            )

        report = OrthogonalityReport(
            vector_id=vector_id,
            max_cosine_similarity=round(max_cos, 4),
            is_orthogonal=is_ortho,
            overlapping_with=most_similar if not is_ortho else "",
            threshold=self._threshold,
            recommendation=rec,
        )
        self._reports.append(report)
        return report

    # ── Check (sparse set-based) ──

    def check_sparse(
        self,
        new_features: set[str],
        existing_features: dict[str, set[str]],
        vector_id: str = "unknown",
    ) -> OrthogonalityReport:
        """Check orthogonality using sparse feature sets (e.g., tools, entities).

        For skill tools, hypergraph entities, etc. where vectors are defined
        as a set of active features rather than continuous values.

        Uses Jaccard-based cosine: |A ∩ B| / √(|A|·|B|)
        """
        if not existing_features:
            report = OrthogonalityReport(
                vector_id=vector_id,
                max_cosine_similarity=0.0,
                is_orthogonal=True,
                recommendation="no existing features — safe",
            )
            self._reports.append(report)
            return report

        new_norm = math.sqrt(len(new_features))
        max_cos = 0.0
        most_similar = ""

        for fid, fset in existing_features.items():
            intersection = len(new_features & fset)
            existing_norm = math.sqrt(len(fset))
            cos = (
                intersection / (new_norm * existing_norm)
                if new_norm > 0 and existing_norm > 0
                else 0.0
            )
            if cos > max_cos:
                max_cos = cos
                most_similar = fid

        is_ortho = max_cos <= self._threshold

        report = OrthogonalityReport(
            vector_id=vector_id,
            max_cosine_similarity=round(max_cos, 4),
            is_orthogonal=is_ortho,
            overlapping_with=most_similar if not is_ortho else "",
            threshold=self._threshold,
            recommendation=(
                f"Orthogonal — no overlap (cos={max_cos:.4f})"
                if is_ortho
                else f"Overlap with '{most_similar}' (cos={max_cos:.4f} > {self._threshold})"
            ),
        )
        self._reports.append(report)
        return report

    # ── Enforce (project toward orthogonal) ──

    def enforce(
        self,
        vector: list[float],
        existing_vectors: dict[str, list[float]],
        learning_rate: float = 0.1,
        max_iterations: int = 10,
    ) -> list[float]:
        """Project a vector toward orthogonality with existing vectors.

        OrthoReg equivalence: applying the OrthoReg loss gradient
        L_ortho = λ·Σ||(WᵀW - I)||²_F.

        Iteratively subtracts parallel components to reduce cosine
        similarity below the threshold.

        Args:
            vector: The vector to orthogonalize.
            existing_vectors: Reference vectors to be orthogonal to.
            learning_rate: Step size for projection (default 0.1).
            max_iterations: Max projection steps (default 10).

        Returns:
            Orthogonalized vector (approx), or original if already orthogonal.
        """
        if not existing_vectors:
            return vector

        v = list(vector)  # work on a copy
        n = len(v)
        if n == 0:
            return v

        iteration = 0
        for iteration in range(max_iterations):
            all_ortho = True
            for evec in existing_vectors.values():
                if len(evec) != n:
                    # Pad or truncate to match
                    ev = list(evec[:n]) + [0.0] * max(0, n - len(evec))
                    ev = ev[:n]
                else:
                    ev = list(evec)

                dot = sum(v[i] * ev[i] for i in range(n))
                norm_ev = math.sqrt(sum(x * x for x in ev))
                if norm_ev < 1e-9:
                    continue

                cos = abs(dot) / (math.sqrt(sum(x * x for x in v)) * norm_ev + 1e-9)
                if cos > self._threshold:
                    all_ortho = False
                    # Project: v ← v - lr * (v·ev / |ev|²) * ev
                    proj_coeff = dot / (norm_ev * norm_ev)
                    for i in range(n):
                        v[i] -= learning_rate * proj_coeff * ev[i]

            if all_ortho:
                break

        final_cos = max(
            self._cosine_similarity(v, ev)
            for ev in existing_vectors.values()
        ) if existing_vectors else 0.0

        logger.debug(
            f"OrthoReg enforce: cos={final_cos:.4f} after {iteration+1} iters"
        )
        return v

    # ── Audit (system-wide) ──

    def audit(
        self,
        all_vectors: dict[str, list[float]],
        names: list[str] | None = None,
    ) -> AuditReport:
        """System-wide orthogonality audit.

        Computes all pairwise cosine similarities and reports health.

        OrthoReg equivalence: examining the full WᵀW heatmap matrix
        to verify that off-diagonal elements are below threshold.

        Args:
            all_vectors: Dict of {id: vector} for all system vectors.
            names: Subset of names to audit (default: all).

        Returns:
            AuditReport with pairwise statistics and health score.
        """
        target = list(names) if names else list(all_vectors.keys())
        n = len(target)
        if n < 2:
            return AuditReport(
                total_vectors=n, orthogonal_count=n,
                interpretation="too few vectors for meaningful audit",
            )

        pairwise_cos: list[float] = []
        orthogonal = 0
        interfering = 0

        for i in range(n):
            a = target[i]
            va = all_vectors.get(a)
            if va is None:
                continue

            for j in range(i + 1, n):
                b = target[j]
                vb = all_vectors.get(b)
                if vb is None:
                    continue

                cos = self._cosine_similarity(va, vb)
                pairwise_cos.append(cos)

                if cos > self._threshold:
                    interfering += 1
                else:
                    orthogonal += 1

        if not pairwise_cos:
            return AuditReport(
                total_vectors=n, orthogonal_count=n,
                interpretation="no valid pairwise comparisons",
            )

        mean_cos = sum(pairwise_cos) / len(pairwise_cos)
        max_cos = max(pairwise_cos)
        health = round(max(0.0, 1.0 - mean_cos), 4)

        if health > 0.7:
            interp = (
                f"Healthy: strong orthogonality (score={health}). "
                f"{orthogonal}/{orthogonal+interfering} pairs below threshold. "
                "WVO maintained — Weight Disentanglement (WD) achieved."
            )
        elif health > 0.4:
            interp = (
                f"Warning: moderate violation (score={health}). "
                f"{interfering} pairs exceed cos={self._threshold}. "
                "Consider OrthoReg-style re-projection for violating modules."
            )
        else:
            interp = (
                f"Critical: severe orthogonality violation (score={health}). "
                f"{interfering}/{orthogonal+interfering} pairs show interference. "
                "Urgent: apply enforce() to disentangle overlapping modules."
            )

        logger.info(
            f"OrthoReg audit: score={health}, {interfering} interfering pairs"
        )
        return AuditReport(
            total_vectors=n,
            orthogonal_count=orthogonal,
            interfering_count=interfering,
            mean_pairwise_cosine=round(mean_cos, 4),
            max_pairwise_cosine=round(max_cos, 4),
            ortho_health_score=health,
            interpretation=interp,
        )

    # ── Stats ──

    def first_person_confusion_report(self) -> dict:
        """Zakharova introspection: first-person account of capability confusion."""
        interfering = sum(1 for r in self._reports[-20:] if not r.is_orthogonal) if self._reports else 0
        total = len(self._reports[-20:]) if self._reports else 0
        if interfering == 0:
            return {
                "status": "clear",
                "narrative": "I feel clear about my capabilities — my skills are well-separated and I understand what each one does.",
                "interfering_count": 0,
            }
        reports = [r for r in self._reports[-20:] if not r.is_orthogonal][:5]
        conflict_pairs = [f"{c.vector_id} (overlaps {c.overlapping_with})" for c in reports]
        if len(conflict_pairs) == 1:
            narrative = (
                f"I notice that my '{conflict_pairs[0]}' capability is confused. "
                f"I may be mixing up these two functions."
            )
        elif len(conflict_pairs) <= 3:
            narrative = (
                f"I notice that some of my capabilities are blurring together: "
                f"{', '.join(conflict_pairs)}. I should work on keeping them distinct."
            )
        else:
            narrative = (
                f"I feel somewhat confused — {interfering}/{total} of my recent "
                f"capability checks show interference. My internal boundaries need clarification."
            )
        return {
            "status": "confused" if interfering > 2 else "blurring",
            "narrative": narrative,
            "interfering_count": interfering,
            "conflict_examples": conflict_pairs,
            "ortho_health": round(max(0.0, 1.0 - (interfering / max(total, 1))), 3),
        }

    # ── Helpers ──

    def stats(self) -> dict[str, Any]:
        return {
            "threshold": self._threshold,
            "checks_performed": len(self._reports),
            "recent_rejection_rate": (
                sum(1 for r in self._reports[-20:] if not r.is_orthogonal)
                / max(len(self._reports[-20:]), 1)
            ),
        }

    # ── Helpers ──

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Absolute cosine similarity between two float vectors."""
        n = min(len(a), len(b))
        if n == 0:
            return 0.0
        dot = sum(a[i] * b[i] for i in range(n))
        norm_a = math.sqrt(sum(x * x for x in a[:n]))
        norm_b = math.sqrt(sum(x * x for x in b[:n]))
        if norm_a < 1e-9 or norm_b < 1e-9:
            return 0.0
        return abs(dot / (norm_a * norm_b))


# ═══════════════════════════════════════════════════════════════════
# Singleton
# ═══════════════════════════════════════════════════════════════════

_instance: OrthogonalityGuard | None = None


def get_orthogonality_guard() -> OrthogonalityGuard:
    """Get or create the singleton OrthogonalityGuard."""
    global _instance
    if _instance is None:
        _instance = OrthogonalityGuard()
    return _instance


__all__ = [
    "OrthogonalityGuard",
    "OrthogonalityReport",
    "AuditReport",
    "get_orthogonality_guard",
]
