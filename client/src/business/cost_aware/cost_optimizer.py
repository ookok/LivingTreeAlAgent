"""
CostOptimizer - 成本优化器

实现成本认知系统的第四层：成本优化

核心功能：
- 自动优化成本
- 模型降级策略（优先用L0/L1）
- 缓存复用机制
- 结果裁剪策略

借鉴企业成本优化理念：降本增效、精益运营

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
import hashlib
import time


class OptimizationStrategy(Enum):
    """优化策略"""
    MODEL_DOWNGRADE = "model_downgrade"   # 模型降级
    CACHE_REUSE = "cache_reuse"           # 缓存复用
    PARALLEL_LIMIT = "parallel_limit"     # 并行限制
    RESULT_TRIM = "result_trim"           # 结果裁剪
    BATCH_OPTIMIZATION = "batch_optimization"  # 批量优化


class ModelTier(Enum):
    """模型层级"""
    L0 = 0  # 最快最轻量
    L1 = 1  # 轻量
    L2 = 2  # 中等
    L3 = 3  # 高质量
    L4 = 4  # 最高质量
    
    @property
    def name_str(self):
        """获取名称字符串（l0/l1/l2/l3/l4）"""
        return f"l{self.value}"
    
    @property
    def level(self):
        """获取层级数值"""
        return self.value


@dataclass
class OptimizationResult:
    """
    优化结果
    """
    strategy: OptimizationStrategy
    applied: bool
    original_cost: float = 0.0    # 优化前成本（USD）
    optimized_cost: float = 0.0   # 优化后成本（USD）
    savings: float = 0.0          # 节省金额（USD）
    savings_ratio: float = 0.0    # 节省比例（0-1）
    message: str = ""             # 优化说明


class CostOptimizer:
    """
    成本优化器
    
    在任务执行前自动优化成本，支持：
    1. 模型降级：能用L0/L1就不用L4
    2. 缓存复用：相同查询不重复调用
    3. 并行限制：限制并行Agent数量
    4. 结果裁剪：只保留必要的中间结果
    """
    
    def __init__(self):
        self._logger = logger.bind(component="CostOptimizer")
        
        # 模型成本映射
        self._model_costs = {
            ModelTier.L0: 0.0001,   # L0模型调用成本（USD）
            ModelTier.L1: 0.001,    # L1模型调用成本（USD）
            ModelTier.L2: 0.005,    # L2模型调用成本（USD）
            ModelTier.L3: 0.01,     # L3模型调用成本（USD）
            ModelTier.L4: 0.01,     # L4模型调用成本（USD）
        }
        
        # 缓存存储
        self._query_cache: Dict[str, Tuple[str, float, float]] = {}  # key -> (result, cost, timestamp)
        self._cache_timeout = 3600  # 缓存超时时间（秒）
        
        # 并行限制
        self._max_parallel = 3  # 最大并行Agent数量
        self._current_parallel = 0
        
        # 优化统计
        self._optimizations_applied = 0
        self._total_savings = 0.0
        
        self._logger.info("✅ CostOptimizer 初始化完成")
    
    def optimize(self, task_description: str, estimated_cost: float, 
                 model_tier: ModelTier = ModelTier.L4) -> List[OptimizationResult]:
        """
        执行成本优化
        
        Args:
            task_description: 任务描述
            estimated_cost: 预估成本（USD）
            model_tier: 目标模型层级
            
        Returns:
            优化结果列表
        """
        results = []
        
        # 1. 尝试缓存复用
        cache_result = self._try_cache_reuse(task_description)
        if cache_result.applied:
            results.append(cache_result)
            self._optimizations_applied += 1
            self._total_savings += cache_result.savings
            return results  # 如果命中缓存，直接返回
        
        # 2. 尝试模型降级
        downgrade_result = self._try_model_downgrade(task_description, estimated_cost, model_tier)
        if downgrade_result.applied:
            results.append(downgrade_result)
            self._optimizations_applied += 1
            self._total_savings += downgrade_result.savings
        
        # 3. 检查并行限制
        parallel_result = self._check_parallel_limit()
        if parallel_result.applied:
            results.append(parallel_result)
        
        # 4. 建议结果裁剪
        trim_result = self._suggest_result_trim(task_description)
        if trim_result.applied:
            results.append(trim_result)
        
        return results
    
    def _try_cache_reuse(self, query: str) -> OptimizationResult:
        """
        尝试缓存复用
        
        Args:
            query: 查询内容
            
        Returns:
            优化结果
        """
        # 生成缓存键
        cache_key = self._generate_cache_key(query)
        
        # 检查缓存
        if cache_key in self._query_cache:
            result, cost, timestamp = self._query_cache[cache_key]
            
            # 检查缓存是否过期
            if time.time() - timestamp < self._cache_timeout:
                self._logger.debug(f"💾 命中缓存: {cache_key[:20]}...")
                return OptimizationResult(
                    strategy=OptimizationStrategy.CACHE_REUSE,
                    applied=True,
                    original_cost=0.01,  # 假设原本需要调用L4
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
        """生成缓存键"""
        return hashlib.md5(query.encode()).hexdigest()
    
    def add_to_cache(self, query: str, result: str, cost: float):
        """
        添加到缓存
        
        Args:
            query: 查询内容
            result: 查询结果
            cost: 消耗成本（USD）
        """
        cache_key = self._generate_cache_key(query)
        self._query_cache[cache_key] = (result, cost, time.time())
        
        # 清理过期缓存
        self._cleanup_expired_cache()
        
        self._logger.debug(f"📥 添加缓存: {cache_key[:20]}...")
    
    def _cleanup_expired_cache(self):
        """清理过期缓存"""
        now = time.time()
        expired_keys = [
            key for key, (_, _, timestamp) in self._query_cache.items()
            if now - timestamp >= self._cache_timeout
        ]
        
        for key in expired_keys:
            del self._query_cache[key]
        
        if expired_keys:
            self._logger.debug(f"🗑️ 清理过期缓存: {len(expired_keys)} 条")
    
    def _try_model_downgrade(self, task_description: str, estimated_cost: float,
                            target_tier: ModelTier) -> OptimizationResult:
        """
        尝试模型降级
        
        Args:
            task_description: 任务描述
            estimated_cost: 预估成本（USD）
            target_tier: 目标模型层级
            
        Returns:
            优化结果
        """
        # 判断是否可以降级
        downgrade_tier = self._determine_optimal_tier(task_description, target_tier)
        
        if downgrade_tier == target_tier:
            return OptimizationResult(
                strategy=OptimizationStrategy.MODEL_DOWNGRADE,
                applied=False,
                message="已使用最优模型层级"
            )
        
        # 计算节省
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
        """
        确定最优模型层级
        
        Args:
            task_description: 任务描述
            target_tier: 目标模型层级
            
        Returns:
            最优模型层级
        """
        desc = task_description.lower()
        
        # 简单任务可以用L0
        simple_keywords = ["查询", "搜索", "帮助", "介绍", "解释", "定义"]
        if any(keyword in desc for keyword in simple_keywords):
            return ModelTier.L0 if ModelTier.L0.level < target_tier.level else target_tier
        
        # 中等任务可以用L1
        medium_keywords = ["分析", "总结", "翻译", "建议", "方案"]
        if any(keyword in desc for keyword in medium_keywords):
            return ModelTier.L1 if ModelTier.L1.level < target_tier.level else target_tier
        
        # 复杂任务需要L2或更高
        complex_keywords = ["深度分析", "推理", "规划", "优化", "设计"]
        if any(keyword in desc for keyword in complex_keywords):
            return ModelTier.L2 if ModelTier.L2.level < target_tier.level else target_tier
        
        # 默认使用目标层级
        return target_tier
    
    def _check_parallel_limit(self) -> OptimizationResult:
        """
        检查并行限制
        
        Returns:
            优化结果
        """
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
        """
        建议结果裁剪
        
        Args:
            task_description: 任务描述
            
        Returns:
            优化结果
        """
        desc = task_description.lower()
        
        # 如果任务不需要详细结果，可以裁剪
        if any(keyword in desc for keyword in ["简短", "简洁", "摘要"]):
            return OptimizationResult(
                strategy=OptimizationStrategy.RESULT_TRIM,
                applied=True,
                savings=0.005,  # 估算节省
                savings_ratio=0.5,
                message="建议启用结果裁剪，减少存储空间"
            )
        
        return OptimizationResult(
            strategy=OptimizationStrategy.RESULT_TRIM,
            applied=False,
            message="未启用结果裁剪"
        )
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """获取优化统计"""
        return {
            "optimizations_applied": self._optimizations_applied,
            "total_savings_usd": self._total_savings,
            "cache_size": len(self._query_cache),
            "current_parallel": self._current_parallel,
            "max_parallel": self._max_parallel
        }
    
    def set_max_parallel(self, max_parallel: int):
        """设置最大并行数"""
        self._max_parallel = max_parallel
        self._logger.info(f"🔧 设置最大并行数: {max_parallel}")


# 创建全局实例
cost_optimizer = CostOptimizer()


def get_cost_optimizer() -> CostOptimizer:
    """获取成本优化器实例"""
    return cost_optimizer


# 测试函数
async def test_cost_optimizer():
    """测试成本优化器"""
    import sys
    logger.remove()
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)
    
    print("=" * 60)
    print("测试 CostOptimizer")
    print("=" * 60)
    
    optimizer = CostOptimizer()
    
    # 1. 测试模型降级
    print("\n[1] 测试模型降级...")
    results = optimizer.optimize("帮我查询天气", 0.01, ModelTier.L4)
    for result in results:
        if result.strategy == OptimizationStrategy.MODEL_DOWNGRADE:
            print(f"    ✓ 策略: {result.strategy.value}")
            print(f"    ✓ 应用: {'是' if result.applied else '否'}")
            print(f"    ✓ 节省比例: {result.savings_ratio:.0%}")
            print(f"    ✓ 说明: {result.message}")
    
    # 2. 测试缓存复用
    print("\n[2] 测试缓存复用...")
    # 第一次查询（未命中）
    results = optimizer.optimize("帮我搜索人工智能", 0.01, ModelTier.L4)
    print(f"    ✓ 第一次查询 - 缓存命中: {'是' if any(r.strategy == OptimizationStrategy.CACHE_REUSE and r.applied for r in results) else '否'}")
    
    # 添加到缓存
    optimizer.add_to_cache("帮我搜索人工智能", "人工智能是...", 0.01)
    
    # 第二次查询（命中）
    results = optimizer.optimize("帮我搜索人工智能", 0.01, ModelTier.L4)
    print(f"    ✓ 第二次查询 - 缓存命中: {'是' if any(r.strategy == OptimizationStrategy.CACHE_REUSE and r.applied for r in results) else '否'}")
    
    # 3. 测试复杂任务优化
    print("\n[3] 测试复杂任务优化...")
    results = optimizer.optimize("使用深度强化学习优化复杂系统", 0.1, ModelTier.L4)
    print(f"    ✓ 优化策略数量: {len(results)}")
    for result in results:
        if result.applied:
            print(f"      - {result.strategy.value}: {result.message}")
    
    # 4. 测试统计信息
    print("\n[4] 测试统计信息...")
    stats = optimizer.get_optimization_stats()
    print(f"    ✓ 优化次数: {stats['optimizations_applied']}")
    print(f"    ✓ 总节省: ${stats['total_savings_usd']:.4f}")
    print(f"    ✓ 缓存大小: {stats['cache_size']}")
    
    print("\n" + "=" * 60)
    print("🎉 所有测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_cost_optimizer())