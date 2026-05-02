"""
CostOptimizer - 成本优化器

实现成本认知系统的第四层：成本优化
"""

from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
import hashlib
import time


class OptimizationStrategy(Enum):
    MODEL_DOWNGRADE = "model_downgrade"
    CACHE_REUSE = "cache_reuse"
    PARALLEL_LIMIT = "parallel_limit"
    RESULT_TRIM = "result_trim"
    BATCH_OPTIMIZATION = "batch_optimization"


class ModelTier(Enum):
    L0 = 0
    L1 = 1
    L2 = 2
    L3 = 3
    L4 = 4

    @property
    def name_str(self):
        return f"l{self.value}"

    @property
    def level(self):
        return self.value


@dataclass
class OptimizationResult:
    strategy: OptimizationStrategy
    applied: bool
    original_cost: float = 0.0
    optimized_cost: float = 0.0
    savings: float = 0.0
    savings_ratio: float = 0.0
    message: str = ""


class CostOptimizer:

    def __init__(self):
        self._logger = logger.bind(component="CostOptimizer")
        self._model_costs = {
            ModelTier.L0: 0.0001,
            ModelTier.L1: 0.001,
            ModelTier.L2: 0.005,
            ModelTier.L3: 0.01,
            ModelTier.L4: 0.01,
        }
        self._query_cache: Dict[str, Tuple[str, float, float]] = {}
        self._cache_timeout = 3600
        self._max_parallel = 3
        self._current_parallel = 0
        self._optimizations_applied = 0
        self._total_savings = 0.0
        self._logger.info("✅ CostOptimizer 初始化完成")

    def optimize(self, task_description: str, estimated_cost: float,
                 model_tier: ModelTier = ModelTier.L4) -> List[OptimizationResult]:
        results = []
        cache_result = self._try_cache_reuse(task_description)
        if cache_result.applied:
            results.append(cache_result)
            self._optimizations_applied += 1
            self._total_savings += cache_result.savings
            return results
        downgrade_result = self._try_model_downgrade(task_description, estimated_cost, model_tier)
        if downgrade_result.applied:
            results.append(downgrade_result)
            self._optimizations_applied += 1
            self._total_savings += downgrade_result.savings
        parallel_result = self._check_parallel_limit()
        if parallel_result.applied:
            results.append(parallel_result)
        trim_result = self._suggest_result_trim(task_description)
        if trim_result.applied:
            results.append(trim_result)
        return results

    def _try_cache_reuse(self, query: str) -> OptimizationResult:
        cache_key = self._generate_cache_key(query)
        if cache_key in self._query_cache:
            result, cost, timestamp = self._query_cache[cache_key]
            if time.time() - timestamp < self._cache_timeout:
                self._logger.debug(f"💾 命中缓存: {cache_key[:20]}...")
                return OptimizationResult(
                    strategy=OptimizationStrategy.CACHE_REUSE,
                    applied=True,
                    original_cost=0.01,
                    optimized_cost=0.0,
                    savings=0.01,
                    savings_ratio=1.0,
                    message="命中缓存，无需重复调用"
                )
        return OptimizationResult(
            strategy=OptimizationStrategy.CACHE_REUSE,
            applied=False,
            message="未命中缓存"
        )

    def _generate_cache_key(self, query: str) -> str:
        return hashlib.md5(query.encode()).hexdigest()

    def add_to_cache(self, query: str, result: str, cost: float):
        cache_key = self._generate_cache_key(query)
        self._query_cache[cache_key] = (result, cost, time.time())
        self._cleanup_expired_cache()

    def _cleanup_expired_cache(self):
        now = time.time()
        expired_keys = [
            key for key, (_, _, timestamp) in self._query_cache.items()
            if now - timestamp >= self._cache_timeout
        ]
        for key in expired_keys:
            del self._query_cache[key]

    def _try_model_downgrade(self, task_description: str, estimated_cost: float,
                            target_tier: ModelTier) -> OptimizationResult:
        downgrade_tier = self._determine_optimal_tier(task_description, target_tier)
        if downgrade_tier == target_tier:
            return OptimizationResult(
                strategy=OptimizationStrategy.MODEL_DOWNGRADE,
                applied=False,
                message="已使用最优模型层级"
            )
        original_cost = self._model_costs.get(target_tier, 0.01)
        downgrade_cost = self._model_costs.get(downgrade_tier, 0.0001)
        savings = original_cost - downgrade_cost
        savings_ratio = savings / original_cost if original_cost > 0 else 0.0
        self._logger.info(
            f"🔻 模型降级: {target_tier.value} -> {downgrade_tier.value}, "
            f"节省: {savings_ratio:.0%}"
        )
        return OptimizationResult(
            strategy=OptimizationStrategy.MODEL_DOWNGRADE,
            applied=True,
            original_cost=original_cost,
            optimized_cost=downgrade_cost,
            savings=savings,
            savings_ratio=savings_ratio,
            message=f"模型从 {target_tier.value} 降级到 {downgrade_tier.value}"
        )

    def _determine_optimal_tier(self, task_description: str, target_tier: ModelTier) -> ModelTier:
        desc = task_description.lower()
        simple_keywords = ["查询", "搜索", "帮助", "介绍", "解释", "定义"]
        if any(keyword in desc for keyword in simple_keywords):
            return ModelTier.L0 if ModelTier.L0.level < target_tier.level else target_tier
        medium_keywords = ["分析", "总结", "翻译", "建议", "方案"]
        if any(keyword in desc for keyword in medium_keywords):
            return ModelTier.L1 if ModelTier.L1.level < target_tier.level else target_tier
        complex_keywords = ["深度分析", "推理", "规划", "优化", "设计"]
        if any(keyword in desc for keyword in complex_keywords):
            return ModelTier.L2 if ModelTier.L2.level < target_tier.level else target_tier
        return target_tier

    def _check_parallel_limit(self) -> OptimizationResult:
        if self._current_parallel >= self._max_parallel:
            return OptimizationResult(
                strategy=OptimizationStrategy.PARALLEL_LIMIT,
                applied=True,
                message=f"已达最大并行数 ({self._max_parallel})，需要等待"
            )
        return OptimizationResult(
            strategy=OptimizationStrategy.PARALLEL_LIMIT,
            applied=False,
            message="并行数在限制内"
        )

    def _suggest_result_trim(self, task_description: str) -> OptimizationResult:
        desc = task_description.lower()
        if any(keyword in desc for keyword in ["简短", "简洁", "摘要"]):
            return OptimizationResult(
                strategy=OptimizationStrategy.RESULT_TRIM,
                applied=True,
                savings=0.005,
                savings_ratio=0.5,
                message="建议启用结果裁剪，减少存储空间"
            )
        return OptimizationResult(
            strategy=OptimizationStrategy.RESULT_TRIM,
            applied=False,
            message="未启用结果裁剪"
        )

    def get_optimization_stats(self) -> Dict[str, Any]:
        return {
            "optimizations_applied": self._optimizations_applied,
            "total_savings_usd": self._total_savings,
            "cache_size": len(self._query_cache),
            "current_parallel": self._current_parallel,
            "max_parallel": self._max_parallel
        }

    def set_max_parallel(self, max_parallel: int):
        self._max_parallel = max_parallel


cost_optimizer = CostOptimizer()


def get_cost_optimizer() -> CostOptimizer:
    return cost_optimizer
