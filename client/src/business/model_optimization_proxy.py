"""
模型优化代理 (Model Optimization Proxy)
======================================

集成所有优化组件，为全局模型路由器提供优化能力：
1. Token优化 - 优化输入Prompt，减少Token消耗
2. Prompt缓存 - 缓存重复请求，减少API调用
3. Token压缩 - 压缩输出响应，减少Token消耗
4. 成本管理 - 监控和控制API调用成本

核心特性：
- 透明代理模式，无需修改现有代码
- 支持所有优化组件的开关控制
- 详细的优化统计和报告
- 智能决策引擎选择最优策略

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import asyncio
import time
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = __import__('logging').getLogger(__name__)


class OptimizationFeature(Enum):
    """优化特性"""
    TOKEN_OPTIMIZATION = "token_optimization"
    PROMPT_CACHING = "prompt_caching"
    TOKEN_COMPRESSION = "token_compression"
    COST_MANAGEMENT = "cost_management"


@dataclass
class OptimizationStats:
    """优化统计"""
    total_calls: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    token_saved: int = 0
    cost_saved: float = 0.0  # 美元
    compression_ratio: float = 0.0
    avg_optimization_time: float = 0.0


@dataclass
class OptimizationResult:
    """优化结果"""
    optimized_prompt: str
    original_prompt_tokens: int
    optimized_prompt_tokens: int
    cached: bool
    cached_response: Optional[str] = None
    compression_applied: bool = False
    compressed_tokens: int = 0


class ModelOptimizationProxy:
    """
    模型优化代理
    
    作为全局模型路由器的代理层，自动应用各种优化：
    1. Token优化 - 优化输入Prompt
    2. Prompt缓存 - 检查并返回缓存响应
    3. Token压缩 - 压缩输出响应
    4. 成本管理 - 记录调用成本
    
    使用方式：
    proxy = ModelOptimizationProxy()
    response = await proxy.call_with_optimization(prompt, model_callable)
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # 优化组件（延迟加载）
        self._token_optimizer = None
        self._prompt_cache = None
        self._token_compressor = None
        self._cost_manager = None
        
        # 启用/禁用各优化特性
        self._features = {
            OptimizationFeature.TOKEN_OPTIMIZATION: True,
            OptimizationFeature.PROMPT_CACHING: True,
            OptimizationFeature.TOKEN_COMPRESSION: True,
            OptimizationFeature.COST_MANAGEMENT: True,
        }
        
        # 配置参数
        self._config = {
            "max_prompt_tokens": 8192,
            "default_compression_level": "balanced",
            "cache_ttl": 3600,
        }
        
        # 统计信息
        self._stats = OptimizationStats()
        
        # 总优化时间
        self._total_optimization_time = 0.0
        
        self._initialized = True
        logger.info("[ModelOptimizationProxy] 模型优化代理初始化完成")
    
    def configure(self, **kwargs):
        """配置优化代理"""
        self._config.update(kwargs)
        logger.info(f"[ModelOptimizationProxy] 配置更新: {kwargs}")
    
    def set_feature(self, feature: OptimizationFeature, enabled: bool):
        """设置优化特性的启用/禁用状态"""
        self._features[feature] = enabled
        logger.info(f"[ModelOptimizationProxy] {feature.value} {'启用' if enabled else '禁用'}")
    
    def toggle_feature(self, feature: OptimizationFeature):
        """切换优化特性状态"""
        self._features[feature] = not self._features[feature]
    
    async def call_with_optimization(self, prompt: str, 
                                     model_callable: Callable[[str], Any],
                                     model_type: str = "claude-3-sonnet",
                                     **kwargs) -> Tuple[str, Dict[str, Any]]:
        """
        带优化的模型调用
        
        Args:
            prompt: 原始提示词
            model_callable: 实际模型调用函数
            model_type: 模型类型（用于成本计算）
            **kwargs: 额外参数
            
        Returns:
            (响应内容, 优化元数据)
        """
        start_time = time.time()
        self._stats.total_calls += 1
        
        metadata = {
            "original_tokens": 0,
            "optimized_tokens": 0,
            "cache_hit": False,
            "compression_applied": False,
            "cost_saved": 0.0,
            "optimization_time": 0.0,
        }
        
        # Step 1: Token优化
        optimized_prompt = prompt
        if self._features[OptimizationFeature.TOKEN_OPTIMIZATION]:
            optimizer = self._get_token_optimizer()
            if optimizer:
                result = optimizer.optimize(
                    prompt, 
                    target_tokens=self._config["max_prompt_tokens"]
                )
                optimized_prompt = result.optimized_text
                metadata["original_tokens"] = result.original_tokens
                metadata["optimized_tokens"] = result.optimized_tokens
                self._stats.token_saved += result.original_tokens - result.optimized_tokens
        
        # Step 2: Prompt缓存
        response = None
        if self._features[OptimizationFeature.PROMPT_CACHING]:
            cache = self._get_prompt_cache()
            if cache:
                cached_response, status = await cache.get(optimized_prompt)
                if status.value == "hit":
                    response = cached_response
                    metadata["cache_hit"] = True
                    self._stats.cache_hits += 1
        
        # Step 3: 实际模型调用（如果缓存未命中）
        if response is None:
            # 调用实际模型
            response = await model_callable(optimized_prompt) if asyncio.iscoroutinefunction(model_callable) else model_callable(optimized_prompt)
            
            # 缓存结果
            if self._features[OptimizationFeature.PROMPT_CACHING]:
                cache = self._get_prompt_cache()
                if cache:
                    await cache.set(optimized_prompt, response, ttl=self._config["cache_ttl"])
            
            self._stats.cache_misses += 1
        
        # Step 4: Token压缩
        if self._features[OptimizationFeature.TOKEN_COMPRESSION] and response:
            compressor = self._get_token_compressor()
            if compressor:
                result = compressor.compress(response)
                response = result.compressed_text
                metadata["compression_applied"] = True
                metadata["compressed_tokens"] = result.compressed_tokens
        
        # Step 5: 成本管理
        if self._features[OptimizationFeature.COST_MANAGEMENT]:
            cost_manager = self._get_cost_manager()
            if cost_manager:
                from business.cost_manager import ModelType
                model_enum = ModelType(model_type) if model_type in [m.value for m in ModelType] else ModelType.CLAUDE_3_SONNET
                cost_manager.record_call(
                    model=model_enum,
                    input_tokens=metadata.get("optimized_tokens", 0),
                    output_tokens=metadata.get("compressed_tokens", 0)
                )
        
        # 更新统计
        optimization_time = time.time() - start_time
        metadata["optimization_time"] = optimization_time
        self._total_optimization_time += optimization_time
        self._stats.avg_optimization_time = self._total_optimization_time / self._stats.total_calls
        
        return response, metadata
    
    def get_stats(self) -> OptimizationStats:
        """获取优化统计信息"""
        return self._stats
    
    def get_full_report(self) -> Dict[str, Any]:
        """获取完整的优化报告"""
        stats = self.get_stats()
        cache_hit_rate = stats.cache_hits / (stats.cache_hits + stats.cache_misses) if (stats.cache_hits + stats.cache_misses) > 0 else 0.0
        
        report = {
            "total_calls": stats.total_calls,
            "cache_hits": stats.cache_hits,
            "cache_misses": stats.cache_misses,
            "cache_hit_rate": cache_hit_rate,
            "token_saved": stats.token_saved,
            "cost_saved": stats.cost_saved,
            "compression_ratio": stats.compression_ratio,
            "avg_optimization_time": stats.avg_optimization_time,
            "features": {f.value: enabled for f, enabled in self._features.items()},
        }
        
        # 添加缓存统计
        try:
            cache = self._get_prompt_cache()
            if cache:
                report["cache_stats"] = cache.get_cache_info()
        except Exception:
            pass
        
        # 添加成本统计
        try:
            cost_manager = self._get_cost_manager()
            if cost_manager:
                report["cost_stats"] = {
                    "total_cost": cost_manager.get_stats().total_cost,
                    "model_breakdown": cost_manager.get_stats().model_breakdown,
                    "budgets": {name: cost_manager.get_budget_status(name) for name in ["daily", "weekly", "monthly"]},
                }
        except Exception:
            pass
        
        return report
    
    def reset_stats(self):
        """重置统计信息"""
        self._stats = OptimizationStats()
        self._total_optimization_time = 0.0
        logger.info("[ModelOptimizationProxy] 统计信息已重置")
    
    # ========== 延迟加载组件 ==========
    
    def _get_token_optimizer(self):
        if self._token_optimizer is None:
            try:
                from business.optimization import get_unified_optimizer, TaskType
                self._token_optimizer = get_unified_optimizer()
                self._token_optimizer.start_session()
            except Exception as e:
                try:
                    from business.token_optimizer import get_token_optimizer
                    self._token_optimizer = get_token_optimizer()
                except Exception as fallback_e:
                    logger.warning(f"[ModelOptimizationProxy] Token优化器加载失败: {fallback_e}")
        return self._token_optimizer
    
    def _get_prompt_cache(self):
        if self._prompt_cache is None:
            try:
                from business.prompt_cache_manager import get_prompt_cache
                self._prompt_cache = get_prompt_cache()
            except Exception as e:
                logger.warning(f"[ModelOptimizationProxy] Prompt缓存加载失败: {e}")
        return self._prompt_cache
    
    def _get_token_compressor(self):
        if self._token_compressor is None:
            try:
                from business.token_compressor import get_token_compressor
                self._token_compressor = get_token_compressor()
            except Exception as e:
                logger.warning(f"[ModelOptimizationProxy] Token压缩器加载失败: {e}")
        return self._token_compressor
    
    def _get_cost_manager(self):
        if self._cost_manager is None:
            try:
                from business.cost_manager import get_cost_manager
                self._cost_manager = get_cost_manager()
            except Exception as e:
                logger.warning(f"[ModelOptimizationProxy] 成本管理器加载失败: {e}")
        return self._cost_manager


# 便捷函数
def get_model_optimization_proxy() -> ModelOptimizationProxy:
    """获取模型优化代理单例"""
    return ModelOptimizationProxy()


__all__ = [
    "OptimizationFeature",
    "OptimizationStats",
    "OptimizationResult",
    "ModelOptimizationProxy",
    "get_model_optimization_proxy",
]