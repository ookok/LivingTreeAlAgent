"""
OptimalConfig — Re-export from livingtree.infrastructure.config

Full migration complete. Use `config.compute_optimal(depth=N)` instead.
"""

from livingtree.infrastructure.config import config, get_config, OptimalParams


class OptimalConfig:
    @staticmethod
    def compute(depth: int = 1):
        return get_config().compute_optimal(depth)


__all__ = ["OptimalConfig", "OptimalParams"]
