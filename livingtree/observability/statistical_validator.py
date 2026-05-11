"""StatisticalRealismValidator — SSDataBench-inspired population-level validation.

Based on "Evaluating the Statistical Realism of LLM-Generated Social Science Data"
(PNAS, doi:10.1073/pnas.2538145123).

Five dimensions of statistical validation:
  1. UNIVARIATE   — distribution shape comparison (KS test, summary statistics)
  2. BIVARIATE    — pairwise association comparison (correlation, contingency)
  3. MULTIVARIATE — regression coefficient agreement
  4. SEQUENCE     — event sequence distribution comparison
  5. COVARIATE    — sequence × covariate association patterns

All dimensions produce a 0-100 score and a pass/fail verdict.
PASS threshold: 75 (aligned with EvalHarness.AcademiClaw convention).

Usage:
    from livingtree.observability.statistical_validator import StatisticalRealismValidator

    validator = StatisticalRealismValidator()
    # Univariate: step count distribution
    report = validator.validate_univariate(
        synthetic_values=[3, 4, 5, 3, 6, ...],
        reference_values=[4, 3, 5, 4, 5, ...],
        dimension_name="trajectory_step_count",
    )
    # Bivariate: tool count vs difficulty
    report = validator.validate_bivariate(
        synthetic_x=[...], synthetic_y=[...],
        reference_x=[...], reference_y=[...],
        dimension_name="tools_vs_difficulty",
    )
    # Full SSDataBench report
    full = validator.ssdata_report(results)
    # → {overall_score: 82, passed: True, dimensions: [...], warnings: [...]}
"""

from __future__ import annotations

import math
import hashlib
import json
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import numpy as np
from loguru import logger

REPORT_DIR = Path(".livingtree/statistical_reports")
PASS_THRESHOLD = 75  # Aligned with EvalHarness


class ValidationDimension(Enum):
    UNIVARIATE = "univariate"
    BIVARIATE = "bivariate"
    MULTIVARIATE = "multivariate"
    SEQUENCE = "sequence"
    COVARIATE = "covariate"


class Severity(str, Enum):
    CRITICAL = "critical"  # Score < 40 — strong evidence of distribution shift
    WARNING = "warning"    # Score 40-60 — moderate deviation
    CAUTION = "caution"    # Score 60-75 — marginal, needs monitoring
    PASS = "pass"          # Score >= 75 — statistically consistent


@dataclass
class DimensionReport:
    """Report for a single SSDataBench dimension."""
    dimension: str
    score: float  # 0-100
    passed: bool
    severity: str
    synthetic_count: int
    reference_count: int
    ks_statistic: float = 0.0  # Two-sample KS distance
    mean_diff_pct: float = 0.0  # Relative mean difference %
    std_diff_pct: float = 0.0   # Relative std difference %
    correlation_diff: float = 0.0  # abs(corr_synth - corr_ref)
    details: str = ""
    histogram_bins: list[dict] = field(default_factory=list)


@dataclass
class SSDataReport:
    """Full SSDataBench-style statistical realism report."""
    id: str
    target: str  # What was validated (e.g., "trajectory_synthesizer")
    timestamp: float
    dimensions: list[DimensionReport] = field(default_factory=list)
    overall_score: float = 0.0
    passed: bool = False
    critical_count: int = 0
    warning_count: int = 0
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "target": self.target, "timestamp": self.timestamp,
            "overall_score": round(self.overall_score, 1),
            "passed": self.passed,
            "critical_count": self.critical_count,
            "warning_count": self.warning_count,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
            "dimensions": [
                {
                    "dimension": d.dimension, "score": round(d.score, 1),
                    "passed": d.passed, "severity": d.severity,
                    "ks_statistic": round(d.ks_statistic, 4),
                    "mean_diff_pct": round(d.mean_diff_pct, 1),
                    "std_diff_pct": round(d.std_diff_pct, 1),
                    "correlation_diff": round(d.correlation_diff, 4),
                    "details": d.details,
                    "synthetic_n": d.synthetic_count, "reference_n": d.reference_count,
                }
                for d in self.dimensions
            ],
        }


class StatisticalRealismValidator:
    """SSDataBench-inspired population-level statistical validator.

    Evaluates whether synthetic data preserves real-world population-level
    statistical patterns across five dimensions.
    """

    def __init__(self, pass_threshold: float = PASS_THRESHOLD):
        self._pass_threshold = pass_threshold
        self._reports: list[SSDataReport] = []
        REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # ═══ Dimension 1: Univariate Distribution ═══

    def validate_univariate(
        self,
        synthetic_values: list[float],
        reference_values: list[float],
        dimension_name: str = "univariate",
        bins: int = 20,
    ) -> DimensionReport:
        """Compare univariate distributions via KS-like distance + summary stats.

        KPIs (from paper):
        - KS distance (max |CDF_synth - CDF_ref|)
        - Mean difference %
        - Standard deviation difference %
        - Histogram bin overlap
        """
        synth = np.array(synthetic_values, dtype=float)
        ref = np.array(reference_values, dtype=float)

        if len(synth) < 5 or len(ref) < 5:
            return DimensionReport(
                dimension=dimension_name, score=50.0, passed=False,
                severity=Severity.WARNING, synthetic_count=len(synth),
                reference_count=len(ref), details="Insufficient data for validation",
            )

        # KS statistic: max difference between empirical CDFs
        ks_stat = self._two_sample_ks(synth, ref)

        # Summary statistics
        synth_mean = float(np.mean(synth))
        ref_mean = float(np.mean(ref))
        synth_std = float(np.std(synth))
        ref_std = float(np.std(ref))

        mean_diff_pct = abs(synth_mean - ref_mean) / max(abs(ref_mean), 0.001) * 100
        std_diff_pct = abs(synth_std - ref_std) / max(ref_std, 0.001) * 100

        # Score: combine KS distance + mean/std difference
        ks_score = max(0, 100 - ks_stat * 200)  # KS 0→100, KS 0.5→0
        mean_score = max(0, 100 - mean_diff_pct)  # 0% diff→100, 100% diff→0
        std_score = max(0, 100 - std_diff_pct * 0.5)  # std difference penalized less
        score = ks_score * 0.5 + mean_score * 0.25 + std_score * 0.25
        score = round(min(100, max(0, score)), 1)

        # Severity classification (paper: "compression of heterogeneity")
        if score < 40:
            severity = Severity.CRITICAL
            if std_diff_pct > 50:
                detail = f"CRITICAL variance collapse: synthetic std {std_diff_pct:.0f}% different from real. Evidence of typological compression."
            else:
                detail = f"CRITICAL distribution mismatch: KS={ks_stat:.4f}, mean Δ={mean_diff_pct:.0f}%"
        elif score < 60:
            severity = Severity.WARNING
            detail = f"Moderate distribution deviation: KS={ks_stat:.4f}, mean Δ={mean_diff_pct:.0f}%, std Δ={std_diff_pct:.0f}%"
        elif score < self._pass_threshold:
            severity = Severity.CAUTION
            detail = f"Slight deviation: KS={ks_stat:.4f}, mean Δ={mean_diff_pct:.0f}% — monitor"
        else:
            severity = Severity.PASS
            detail = f"Distribution consistent: KS={ks_stat:.4f}, mean Δ={mean_diff_pct:.0f}%"

        # Histogram bin comparison
        hist_bins = self._compare_histograms(synth, ref, bins)

        return DimensionReport(
            dimension=dimension_name, score=score,
            passed=score >= self._pass_threshold, severity=severity,
            synthetic_count=len(synth), reference_count=len(ref),
            ks_statistic=round(ks_stat, 4),
            mean_diff_pct=round(mean_diff_pct, 1),
            std_diff_pct=round(std_diff_pct, 1),
            details=detail, histogram_bins=hist_bins,
        )

    # ═══ Dimension 2: Bivariate Association ═══

    def validate_bivariate(
        self,
        synthetic_x: list[float],
        synthetic_y: list[float],
        reference_x: list[float],
        reference_y: list[float],
        dimension_name: str = "bivariate",
    ) -> DimensionReport:
        """Compare bivariate association (Pearson correlation difference).

        From paper: "regression coefficients often differ significantly
        from equivalent estimates obtained using real data."
        """
        sx = np.array(synthetic_x, dtype=float)
        sy = np.array(synthetic_y, dtype=float)
        rx = np.array(reference_x, dtype=float)
        ry = np.array(reference_y, dtype=float)

        n = min(len(sx), len(sy), len(rx), len(ry))
        if n < 5:
            return DimensionReport(
                dimension=dimension_name, score=50.0, passed=False,
                severity=Severity.WARNING, synthetic_count=len(sx),
                reference_count=len(rx), details="Insufficient data",
            )

        # Pearson correlation
        synth_corr = float(np.corrcoef(sx[:n], sy[:n])[0, 1]) if n > 1 else 0.0
        ref_corr = float(np.corrcoef(rx[:n], ry[:n])[0, 1]) if n > 1 else 0.0
        corr_diff = abs(synth_corr - ref_corr)

        # Also compute KS on residuals for deeper comparison
        if n > 3:
            # Simple linear fit: y = a*x + b
            synth_a = (np.mean(sx * sy) - np.mean(sx) * np.mean(sy)) / max(np.var(sx), 1e-8)
            ref_a = (np.mean(rx * ry) - np.mean(rx) * np.mean(ry)) / max(np.var(rx), 1e-8)
            # Predicted y based on reference's x
            synth_pred = synth_a * rx[:n] + (np.mean(sy) - synth_a * np.mean(sx))
            residuals = sy[:n] - synth_pred
            ref_residuals = ry[:n] - (ref_a * rx[:n] + (np.mean(ry) - ref_a * np.mean(rx)))
            ks_residual = self._two_sample_ks(residuals, ref_residuals)
        else:
            synth_a, ref_a, ks_residual = 0, 0, 0

        # Score
        corr_score = max(0, 100 - corr_diff * 100)  # corr_diff 0→100, 1→0
        ks_score = max(0, 100 - ks_residual * 200)
        score = corr_score * 0.6 + ks_score * 0.4
        score = round(min(100, max(0, score)), 1)

        if score < 40:
            severity = Severity.CRITICAL
            detail = f"CRITICAL association mismatch: corr Δ={corr_diff:.3f} (synth={synth_corr:.3f} vs ref={ref_corr:.3f})"
        elif score < 60:
            severity = Severity.WARNING
            detail = f"Association deviation: corr Δ={corr_diff:.3f} (synth={synth_corr:.3f} vs ref={ref_corr:.3f})"
        elif score < self._pass_threshold:
            severity = Severity.CAUTION
            detail = f"Slight association mismatch: corr Δ={corr_diff:.3f}"
        else:
            severity = Severity.PASS
            detail = f"Association consistent: corr Δ={corr_diff:.3f}"

        return DimensionReport(
            dimension=dimension_name, score=score,
            passed=score >= self._pass_threshold, severity=severity,
            synthetic_count=len(sx), reference_count=len(rx),
            correlation_diff=round(corr_diff, 4),
            details=detail,
        )

    # ═══ Dimension 3: Multivariate Outcome Prediction ═══

    def validate_multivariate(
        self,
        synthetic_features: list[list[float]],
        synthetic_outcomes: list[float],
        reference_features: list[list[float]],
        reference_outcomes: list[float],
        dimension_name: str = "multivariate",
    ) -> DimensionReport:
        """Compare multivariate prediction: regression coefficient agreement.

        From paper: "assess the ability of LLM-generated data to reproduce
        real-world, population-level statistical patterns" including
        multivariate outcome predictions.
        """
        sx = np.array(synthetic_features, dtype=float)
        sy = np.array(synthetic_outcomes, dtype=float)
        rx = np.array(reference_features, dtype=float)
        ry = np.array(reference_outcomes, dtype=float)

        if sx.shape[0] < 10 or rx.shape[0] < 10 or sx.shape[1] < 1:
            return DimensionReport(
                dimension=dimension_name, score=50.0, passed=False,
                severity=Severity.WARNING, synthetic_count=sx.shape[0],
                reference_count=rx.shape[0], details="Insufficient data for multivariate",
            )

        # Simple OLS: (X^T X)^(-1) X^T y with pseudoinverse for stability
        try:
            synth_coef = np.linalg.lstsq(
                np.c_[np.ones(sx.shape[0]), sx], sy, rcond=None
            )[0]
            ref_coef = np.linalg.lstsq(
                np.c_[np.ones(rx.shape[0]), rx], ry, rcond=None
            )[0]
        except np.linalg.LinAlgError:
            synth_coef = np.zeros(sx.shape[1] + 1)
            ref_coef = np.zeros(rx.shape[1] + 1)

        # Compare coefficients (normalized)
        coef_diff = np.abs(synth_coef - ref_coef)
        ref_magnitude = np.abs(ref_coef)
        norm_diff = np.mean(coef_diff / np.maximum(ref_magnitude, 0.01))

        # R² comparison
        synth_pred = np.c_[np.ones(sx.shape[0]), sx] @ synth_coef
        ref_pred = np.c_[np.ones(rx.shape[0]), rx] @ ref_coef
        synth_r2 = 1 - np.var(sy - synth_pred) / max(np.var(sy), 1e-8)
        ref_r2 = 1 - np.var(ry - ref_pred) / max(np.var(ry), 1e-8)
        r2_diff = abs(synth_r2 - ref_r2)

        score = max(0, 100 - norm_diff * 100 - r2_diff * 50)
        score = round(min(100, max(0, score)), 1)

        if score < 40:
            severity = Severity.CRITICAL
        elif score < 60:
            severity = Severity.WARNING
        elif score < self._pass_threshold:
            severity = Severity.CAUTION
        else:
            severity = Severity.PASS

        return DimensionReport(
            dimension=dimension_name, score=score,
            passed=score >= self._pass_threshold, severity=severity,
            synthetic_count=sx.shape[0], reference_count=rx.shape[0],
            details=f"Coef norm diff={norm_diff:.3f}, R² Δ={r2_diff:.3f}",
        )

    # ═══ Dimension 4: Sequence Distribution ═══

    def validate_sequence(
        self,
        synthetic_sequences: list[list[str]],
        reference_sequences: list[list[str]],
        dimension_name: str = "sequence",
    ) -> DimensionReport:
        """Compare sequence (e.g., action chain) distributions.

        From paper: "life event sequence distributions".
        Uses n-gram frequency distribution comparison.
        """
        synth_bigrams = self._extract_ngram_freq(synthetic_sequences, n=2)
        ref_bigrams = self._extract_ngram_freq(reference_sequences, n=2)

        all_keys = set(synth_bigrams.keys()) | set(ref_bigrams.keys())
        if not all_keys:
            return DimensionReport(
                dimension=dimension_name, score=50.0, passed=False,
                severity=Severity.WARNING, synthetic_count=len(synthetic_sequences),
                reference_count=len(reference_sequences), details="No sequences to compare",
            )

        # Jensen-Shannon-like divergence on n-gram distributions
        synth_total = sum(synth_bigrams.values()) or 1
        ref_total = sum(ref_bigrams.values()) or 1
        divergence = 0.0
        for k in all_keys:
            p = synth_bigrams.get(k, 0) / synth_total
            q = ref_bigrams.get(k, 0) / ref_total
            m = (p + q) / 2
            if p > 0 and m > 0:
                divergence += p * math.log(p / m)
            if q > 0 and m > 0:
                divergence += q * math.log(q / m)
        divergence = divergence / 2  # Normalize JS divergence

        score = max(0, 100 - divergence * 200)
        score = round(min(100, max(0, score)), 1)

        if score < 40:
            severity = Severity.CRITICAL
            detail = f"CRITICAL sequence distribution divergence: JS={divergence:.4f}"
        elif score < 60:
            severity = Severity.WARNING
            detail = f"Sequence pattern deviation: JS={divergence:.4f}"
        elif score < self._pass_threshold:
            severity = Severity.CAUTION
            detail = f"Minor sequence mismatch: JS={divergence:.4f}"
        else:
            severity = Severity.PASS
            detail = f"Sequence distribution consistent: JS={divergence:.4f}"

        return DimensionReport(
            dimension=dimension_name, score=score,
            passed=score >= self._pass_threshold, severity=severity,
            synthetic_count=len(synthetic_sequences),
            reference_count=len(reference_sequences),
            details=detail,
        )

    # ═══ Dimension 5: Sequence × Covariate Association ═══

    def validate_covariate(
        self,
        synthetic_sequences: list[list[str]],
        synthetic_covariates: list[float],
        reference_sequences: list[list[str]],
        reference_covariates: list[float],
        dimension_name: str = "covariate",
    ) -> DimensionReport:
        """Compare association between sequences and covariates.

        From paper: "associations between life event sequences and covariates".
        Checks if the relationship (e.g., sequence length vs difficulty)
        is preserved.
        """
        synth_lens = [len(s) for s in synthetic_sequences]
        ref_lens = [len(s) for s in reference_sequences]

        # Correlation between sequence length and covariate
        n_s = min(len(synth_lens), len(synthetic_covariates))
        n_r = min(len(ref_lens), len(reference_covariates))

        if n_s < 5 or n_r < 5:
            return DimensionReport(
                dimension=dimension_name, score=50.0, passed=False,
                severity=Severity.WARNING, synthetic_count=n_s,
                reference_count=n_r, details="Insufficient data",
            )

        synth_corr = float(np.corrcoef(synth_lens[:n_s], synthetic_covariates[:n_s])[0, 1])
        ref_corr = float(np.corrcoef(ref_lens[:n_r], reference_covariates[:n_r])[0, 1])
        corr_diff = abs(synth_corr - ref_corr)

        score = max(0, 100 - corr_diff * 100)
        score = round(min(100, max(0, score)), 1)

        if score < 40:
            severity = Severity.CRITICAL
        elif score < 60:
            severity = Severity.WARNING
        elif score < self._pass_threshold:
            severity = Severity.CAUTION
        else:
            severity = Severity.PASS

        return DimensionReport(
            dimension=dimension_name, score=score,
            passed=score >= self._pass_threshold, severity=severity,
            synthetic_count=n_s, reference_count=n_r,
            correlation_diff=round(corr_diff, 4),
            details=f"Seq×cov correlation Δ={corr_diff:.3f} (synth={synth_corr:.3f} vs ref={ref_corr:.3f})",
        )

    # ═══ Full SSDataBench Report ═══

    def ssdata_report(
        self,
        target: str,
        dimension_reports: list[DimensionReport],
    ) -> SSDataReport:
        """Generate full SSDataBench-style report from dimension results."""
        if not dimension_reports:
            return SSDataReport(
                id=self._report_id(),
                target=target,
                timestamp=time.time(),
                overall_score=0.0, passed=False,
                warnings=["No dimensions evaluated"],
            )

        scores = [d.score for d in dimension_reports]
        overall = sum(scores) / len(scores)
        passed = overall >= self._pass_threshold

        criticals = [d for d in dimension_reports if d.severity == Severity.CRITICAL]
        warnings = [d for d in dimension_reports if d.severity == Severity.WARNING]
        cautions = [d for d in dimension_reports if d.severity == Severity.CAUTION]

        warning_msgs = []
        recommendations = []

        for d in criticals:
            warning_msgs.append(f"CRITICAL [{d.dimension}]: {d.details}")
            recommendations.append(f"URGENT: Fix {d.dimension} — distribution mismatch may cause compounding bias in downstream training.")

        for d in warnings:
            warning_msgs.append(f"WARNING [{d.dimension}]: {d.details}")

        for d in cautions:
            warning_msgs.append(f"CAUTION [{d.dimension}]: {d.details}")
            if "variance" in d.details.lower():
                recommendations.append("Consider: increase sampling diversity or add entropy bonus to reduce typological compression.")
            if "association" in d.details.lower():
                recommendations.append("Consider: calibrate synthetic data weights to match reference correlation structure.")

        if not criticals and not warnings and not cautions:
            recommendations.append("All dimensions pass. Continue monitoring for drift over time.")

        report = SSDataReport(
            id=self._report_id(),
            target=target,
            timestamp=time.time(),
            dimensions=dimension_reports,
            overall_score=round(overall, 1),
            passed=passed,
            critical_count=len(criticals),
            warning_count=len(warnings),
            warnings=warning_msgs,
            recommendations=recommendations,
        )

        self._reports.append(report)
        self._save_report(report)
        return report

    # ═══ Helpers ═══

    @staticmethod
    def _two_sample_ks(a: np.ndarray, b: np.ndarray) -> float:
        """Two-sample KS statistic: max |CDF_a(x) - CDF_b(x)|.

        Pure numpy implementation — no scipy dependency.
        """
        combined = np.sort(np.concatenate([a, b]))
        cdf_a = np.searchsorted(np.sort(a), combined, side='right') / len(a)
        cdf_b = np.searchsorted(np.sort(b), combined, side='right') / len(b)
        return float(np.max(np.abs(cdf_a - cdf_b)))

    @staticmethod
    def _compare_histograms(
        synth: np.ndarray, ref: np.ndarray, bins: int,
    ) -> list[dict]:
        """Compare histogram bin proportions."""
        all_vals = np.concatenate([synth, ref])
        bin_edges = np.linspace(all_vals.min(), all_vals.max(), bins + 1)
        s_hist, _ = np.histogram(synth, bins=bin_edges)
        r_hist, _ = np.histogram(ref, bins=bin_edges)

        result = []
        for i in range(bins):
            s_prop = s_hist[i] / max(len(synth), 1)
            r_prop = r_hist[i] / max(len(ref), 1)
            result.append({
                "bin_start": round(float(bin_edges[i]), 2),
                "bin_end": round(float(bin_edges[i + 1]), 2),
                "synthetic_ratio": round(s_prop, 4),
                "reference_ratio": round(r_prop, 4),
                "diff": round(abs(s_prop - r_prop), 4),
            })
        return result

    @staticmethod
    def _extract_ngram_freq(
        sequences: list[list[str]], n: int,
    ) -> dict[tuple, int]:
        """Extract n-gram frequency from sequences."""
        freq: dict[tuple, int] = Counter()
        for seq in sequences:
            for i in range(len(seq) - n + 1):
                ngram = tuple(seq[i:i + n])
                freq[ngram] += 1
        return freq

    def _report_id(self) -> str:
        return hashlib.md5(str(time.time()).encode()).hexdigest()[:12]

    def _save_report(self, report: SSDataReport) -> None:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        path = REPORT_DIR / f"{report.id}.json"
        path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def load_report(self, report_id: str) -> Optional[dict]:
        path = REPORT_DIR / f"{report_id}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return None

    def list_reports(self, target: str = "") -> list[dict]:
        items = []
        for f in sorted(REPORT_DIR.glob("*.json"), reverse=True):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                if not target or d.get("target") == target:
                    items.append({"id": d.get("id"), "target": d.get("target"),
                                  "score": d.get("overall_score"), "passed": d.get("passed"),
                                  "time": d.get("timestamp")})
            except Exception:
                continue
        return items


# ── Singleton ──

_validator: Optional[StatisticalRealismValidator] = None


def get_validator() -> StatisticalRealismValidator:
    global _validator
    if _validator is None:
        _validator = StatisticalRealismValidator()
    return _validator


def reset_validator() -> None:
    global _validator
    _validator = None
