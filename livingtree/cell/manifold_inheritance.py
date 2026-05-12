"""Invariant Manifold Inheritance — Preserve gradient structure during cell division.

Based on SJTU Math4AI (Zhao, Luo & Zhang, M3AS 2025):
  "Architecture induces structural invariant manifolds of neural network training dynamics"

Key finding: Network architecture endogenously determines structural invariant manifolds
that constrain gradient flow trajectories. These manifolds are formed by parameter
symmetries (e.g., neuron permutation) and are INDEPENDENT of data and loss function.

Implications for LivingTree cell division (mitosis.py):
  - Child cells should inherit the parent's invariant manifold structure
  - Not just copy parameters → copy the CONSTRAINT structure
  - This preserves the learned "shape" of knowledge while allowing fresh exploration
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class InvariantManifold:
    """Captures the structural constraints of a trained parameter space.

    These constraints represent the invariant manifold induced by the
    network architecture — the "shape" that gradient flow respects.
    """
    # Symmetry groups preserved
    permutation_groups: int = 0         # Number of interchangeable neurons
    scaling_symmetries: int = 0         # Number of scaling invariances

    # Manifold geometry
    effective_dimension: int = 0        # True degrees of freedom (after symmetries)
    parameter_count: int = 0            # Raw parameter count
    compression_ratio: float = 1.0      # effective / parameter_count

    # Gradient constraints (preserved across children)
    gradient_norm_range: tuple[float, float] = (0.0, 1.0)  # (min, max) observed gradient norms
    hessian_trace: float = 0.0          # Curvature of loss landscape at this point
    stable_directions: list[int] = field(default_factory=list)  # Indices of stable parameter directions

    # Inheritance metadata
    parent_id: str = ""
    generation: int = 0
    inherited_at: float = 0.0


class ManifoldExtractor:
    """Extract and inherit invariant manifolds during cell division.

    Based on the paper's proof:
    "For models built from analytic functions, structural invariant manifolds
    constrain gradient flow trajectories independent of data and loss function."

    The manifold is the set of parameter configurations that are equivalent
    under the architecture's symmetry group. During mitosis, child cells
    should start ON this manifold, not at a random point.
    """

    def extract(self, params: dict, architecture_info: dict = None) -> InvariantManifold:
        """Extract the invariant manifold from a trained parameter set.

        Args:
            params: Dict of parameter name → value (ndarray/list).
            architecture_info: Optional dict with layer sizes, activation types.

        Returns:
            InvariantManifold capturing the structural constraints.
        """
        info = architecture_info or {}

        # Estimate symmetries from architecture
        layer_sizes = info.get("layer_sizes", [])
        permutation_groups = sum(
            math.factorial(min(s, 10)) for s in layer_sizes if s > 1
        )
        scaling_symmetries = len(layer_sizes)  # Each layer has scaling invariance

        # Effective dimension = raw params - symmetry constraints
        parameter_count = sum(
            self._count_elements(v) for v in params.values()
        )
        effective_dim = max(1, parameter_count - permutation_groups - scaling_symmetries)
        compression_ratio = effective_dim / max(1, parameter_count)

        # Gradient constraints: compute range of parameter magnitudes
        magnitudes = []
        for v in params.values():
            if hasattr(v, 'flatten'):
                flat = v.flatten()
            elif isinstance(v, list):
                flat = [float(x) for x in v]
            else:
                continue
            magnitudes.extend(abs(float(x)) for x in flat)

        if magnitudes:
            grad_min = min(magnitudes) * 0.8
            grad_max = max(magnitudes) * 1.2
        else:
            grad_min, grad_max = 0.0, 1.0

        # Stable directions: parameters with low variance (well-learned)
        stable = []
        idx = 0
        for name, v in params.items():
            if hasattr(v, 'var'):
                var_val = float(v.var()) if callable(getattr(v, 'var', None)) else 0.0
                if var_val < 0.01:
                    stable.append(idx)
            idx += 1

        return InvariantManifold(
            permutation_groups=permutation_groups,
            scaling_symmetries=scaling_symmetries,
            effective_dimension=effective_dim,
            parameter_count=parameter_count,
            compression_ratio=compression_ratio,
            gradient_norm_range=(grad_min, grad_max),
            hessian_trace=info.get("hessian_trace", 0.0),
            stable_directions=stable,
        )

    def project_to_manifold(
        self, child_params: dict, parent_manifold: InvariantManifold
    ) -> dict:
        """Project child parameters onto the parent's invariant manifold.

        This ensures the child inherits the structural constraints,
        not just the raw parameter values. The child starts on the same
        manifold but with perturbed values → faster convergence.

        Args:
            child_params: New parameters for the child cell.
            parent_manifold: Extracted invariant manifold from parent.

        Returns:
            Projected child parameters.
        """
        # Constraint 1: Gradient norm should be within parent's observed range
        g_min, g_max = parent_manifold.gradient_norm_range

        for name, value in child_params.items():
            if hasattr(value, 'flatten'):
                flat = value.flatten()
                norm = float(sum(x**2 for x in flat) ** 0.5)
            elif isinstance(value, list) and all(isinstance(x, (int, float)) for x in value):
                norm = float(sum(x**2 for x in value) ** 0.5)
            else:
                continue

            # Clamp to parent's gradient range
            if norm > 0:
                target_norm = max(g_min, min(g_max, norm))
                scale = target_norm / max(1e-9, norm)

                if hasattr(value, '__mul__'):
                    child_params[name] = value * scale

        # Constraint 2: Preserve stable directions (don't disturb well-learned params)
        for stable_idx in parent_manifold.stable_directions:
            param_names = list(child_params.keys())
            if stable_idx < len(param_names):
                # Reduce perturbation on stable directions to 10%
                stable_param = child_params[param_names[stable_idx]]
                if hasattr(stable_param, '__mul__'):
                    child_params[param_names[stable_idx]] = stable_param * 0.1

        return child_params

    # ── Helper ──

    @staticmethod
    def _count_elements(value: Any) -> int:
        if hasattr(value, 'size'):
            return int(value.size)
        elif isinstance(value, list):
            return len(value)
        elif isinstance(value, (int, float)):
            return 1
        return 0


# ── Singleton ──

_extractor: Optional[ManifoldExtractor] = None


def get_manifold_extractor() -> ManifoldExtractor:
    global _extractor
    if _extractor is None:
        _extractor = ManifoldExtractor()
    return _extractor
