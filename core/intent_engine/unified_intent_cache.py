"""
Unified Intent Cache - 统一意图缓存

整合精确缓存（IntentCache）和语义缓存（SemanticCache），
提供统一的缓存接口，并智能路由查询到最佳缓存层。

设计理念：
1. 分层缓存：L1 精确匹配 → L2 语义匹配
2. 智能路由：根据查询特征自动选择缓存策略
3. 统一接口：调用方不需要关心底层缓存实现
4. 自动优化：根据命中率自动调整路由策略
"""

import time
import hashlib
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import threading

logger = logging.getLogger(__name__)


class CacheLayer(Enum):
    """缓存层级"""
    EXACT = "exact"       # 精确匹配（IntentCache）
    SEMANTIC = "semantic"  # 语义匹配（SemanticCache）
    HYBRID = "hybrid"    # 混合（先精确，后语义）


class QueryComplexity(Enum):
    """查询复杂度"""
    SIMPLE = "simple"    # 简单查询（精确匹配即可）
    MODERATE = "moderate"  # 中等复杂度（建议语义）
    COMPLEX = "complex"   # 复杂查询（必须语义）


@dataclass
class UnifiedCacheStats:
    """统一缓存统计"""
    exact_hits: int = 0
    exact_misses: int = 0
    semantic_hits: int = 0
    semantic_misses: int = 0
    hybrid_hits: int = 0
    hybrid_misses: int = 0
    total_queries: int = 0
    semantic_fallbacks: int = 0  # 精确未命中，语义命中的次数
    avg_similarity: float = 0.0
    cache_size: int = 0

    @property
    def exact_hit_rate(self) -> float:
        total = self.exact_hits + self.exact_misses
        return self.exact_hits / total if total > 0 else 0.0

    @property
    def semantic_hit_rate(self) -> float:
        total = self.semantic_hits + self.semantic_misses
        return self.semantic_hits / total if total > 0 else 0.0

    @property
    def overall_hit_rate(self) -> float:
        return (self.exact_hits + self.semantic_hits) / max(self.total_queries, 1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exact_hits": self.exact_hits,
            "exact_misses": self.exact_misses,
            "exact_hit_rate": f"{self.exact_hit_rate:.2%}",
            "semantic_hits": self.semantic_hits,
            "semantic_misses": self.semantic_misses,
            "semantic_hit_rate": f"{self.semantic_hit_rate:.2%}",
            "hybrid_hits": self.hybrid_hits,
            "hybrid_misses": self.hybrid_misses,
            "total_queries": self.total_queries,
            "overall_hit_rate": f"{self.overall_hit_rate:.2%}",
            "semantic_fallbacks": self.semantic_fallbacks,
            "avg_similarity": round(self.avg_similarity, 4),
            "cache_size": self.cache_size,
        }


class UnifiedIntentCache:
    """
    统一意图缓存

    整合精确缓存和语义缓存，提供智能路由。

    使用示例：
        cache = UnifiedIntentCache()

        # 设置缓存
        cache.set("帮我写代码", result)

        # 获取缓存（自动路由）
        result = cache.get("帮我生成代码")  # 语义相似，命中！

        # 强制使用特定层级
        result = cache.get("帮我写代码", layer=CacheLayer.EXACT)

        # 获取统计
        stats = cache.get_stats()
    """

    def __init__(
        self,
        exact_max_size: int = 1000,
        exact_ttl: float = 3600.0,
        semantic_dim: int = 384,
        semantic_threshold: float = 0.85,
        enable_hybrid: bool = True,
        auto_optimize: bool = True,
    ):
        """
        初始化统一缓存

        Args:
            exact_max_size: 精确缓存最大条目数
            exact_ttl: 精确缓存 TTL（秒）
            semantic_dim: 语义向量维度
            semantic_threshold: 语义相似度阈值
            enable_hybrid: 是否启用混合模式
            auto_optimize: 是否自动优化路由策略
        """
        self._lock = threading.RLock()

        # L1: 精确缓存（IntentCache）
        from .intent_cache import IntentCache, CacheStrategy
        self._exact_cache = IntentCache(
            max_size=exact_max_size,
            strategy=CacheStrategy.LRU,
            default_ttl=exact_ttl,
        )

        # L2: 语义缓存（SemanticCache）
        self._semantic_cache = None
        self._semantic_dim = semantic_dim
        self._semantic_threshold = semantic_threshold
        self._init_semantic_cache()

        # 配置
        self._enable_hybrid = enable_hybrid
        self._auto_optimize = auto_optimize

        # 统计
        self._stats = UnifiedCacheStats()

        # 路由策略（可以根据命中率自动调整）
        self._prefer_exact_for_simple = True  # 简单查询优先精确缓存

        logger.info(
            f"[UnifiedIntentCache] Initialized: "
            f"exact_max={exact_max_size}, semantic_dim={semantic_dim}, "
            f"semantic_threshold={semantic_threshold}, hybrid={enable_hybrid}"
        )

    def _init_semantic_cache(self) -> None:
        """初始化语义缓存（延迟加载）"""
        try:
            from core.tier_model.semantic_cache import SemanticCache
            self._semantic_cache = SemanticCache(
                vector_dim=self._semantic_dim,
                similarity_threshold=self._semantic_threshold,
                index_type="faiss",
            )
            logger.info("[UnifiedIntentCache] Semantic cache initialized")
        except Exception as e:
            logger.warning(f"[UnifiedIntentCache] Semantic cache not available: {e}")
            self._semantic_cache = None

    def _compute_exact_key(self, query: str, context: Optional[Dict] = None) -> str:
        """计算精确缓存键"""
        from .intent_cache import compute_intent_key
        return compute_intent_key(query, context)

    def _assess_complexity(self, query: str) -> QueryComplexity:
        """
        评估查询复杂度

        简单查询：短句、关键词
        中等复杂度：完整句子
        复杂查询：多句、包含专业术语
        """
        word_count = len(query.split())

        # 简单启发式
        if word_count <= 3:
            return QueryComplexity.SIMPLE
        elif word_count <= 10:
            return QueryComplexity.MODERATE
        else:
            return QueryComplexity.COMPLEX

    def get(
        self,
        query: str,
        context: Optional[Dict] = None,
        layer: Optional[CacheLayer] = None,
    ) -> Optional[Any]:
        """
        获取缓存

        Args:
            query: 查询文本
            context: 上下文
            layer: 强制使用特定层级（None = 自动路由）

        Returns:
            缓存结果，未命中则返回 None
        """
        with self._lock:
            self._stats.total_queries += 1

            # 确定缓存层级
            if layer is None:
                complexity = self._assess_complexity(query)
                layer = self._route(query, complexity)

            # L1: 精确匹配
            if layer == CacheLayer.EXACT:
                exact_key = self._compute_exact_key(query, context)
                result = self._exact_cache.get(exact_key)
                if result is not None:
                    self._stats.exact_hits += 1
                    return result
                self._stats.exact_misses += 1

                # 如果启用了混合模式，回退到语义缓存
                if self._enable_hybrid and self._semantic_cache is not None:
                    return self._get_semantic(query)

                return None

            # L2: 语义匹配
            elif layer == CacheLayer.SEMANTIC:
                return self._get_semantic(query)

            # L3: 混合（先精确，后语义）
            elif layer == CacheLayer.HYBRID:
                # 先试精确
                exact_key = self._compute_exact_key(query, context)
                result = self._exact_cache.get(exact_key)
                if result is not None:
                    self._stats.hybrid_hits += 1
                    return result

                # 回退到语义
                semantic_result = self._get_semantic(query)
                if semantic_result is not None:
                    self._stats.semantic_fallbacks += 1
                    return semantic_result

                self._stats.hybrid_misses += 1
                return None

            return None

    def _get_semantic(self, query: str) -> Optional[Any]:
        """从语义缓存获取"""
        if self._semantic_cache is None:
            self._stats.semantic_misses += 1
            return None

        try:
            from core.tier_model.semantic_cache import SemanticCacheResult
            result = self._semantic_cache.get(query)
            if result is not None:
                self._stats.semantic_hits += 1
                # 更新平均相似度
                total = self._stats.semantic_hits + self._stats.semantic_misses
                self._stats.avg_similarity = (
                    self._stats.avg_similarity * (total - 1) + result.similarity
                ) / total
                return result.response
            else:
                self._stats.semantic_misses += 1
                return None
        except Exception as e:
            logger.error(f"[UnifiedIntentCache] Semantic get error: {e}")
            self._stats.semantic_misses += 1
            return None

    def set(
        self,
        query: str,
        value: Any,
        context: Optional[Dict] = None,
        ttl: Optional[float] = None,
        update_exact: bool = True,
        update_semantic: bool = True,
    ) -> None:
        """
        设置缓存（同时更新精确缓存和语义缓存）

        Args:
            query: 查询文本
            value: 缓存值
            context: 上下文
            ttl: 过期时间（仅用于精确缓存）
            update_exact: 是否更新精确缓存
            update_semantic: 是否更新语义缓存
        """
        with self._lock:
            # 更新精确缓存
            if update_exact:
                exact_key = self._compute_exact_key(query, context)
                self._exact_cache.set(exact_key, value, ttl=ttl)

            # 更新语义缓存
            if update_semantic and self._semantic_cache is not None:
                try:
                    self._semantic_cache.set(query, value)
                except Exception as e:
                    logger.error(f"[UnifiedIntentCache] Semantic set error: {e}")

    def _route(self, query: str, complexity: QueryComplexity) -> CacheLayer:
        """
        智能路由：根据查询特征选择缓存层级

        路由规则：
        1. 简单查询 → EXACT（快速）
        2. 中等复杂度 + 精确缓存命中率高 → EXACT
        3. 中等复杂度 + 精确缓存命中率低 → HYBRID
        4. 复杂查询 → SEMANTIC
        """
        # 简单查询优先精确匹配
        if complexity == QueryComplexity.SIMPLE and self._prefer_exact_for_simple:
            return CacheLayer.EXACT

        # 复杂查询必须语义匹配
        if complexity == QueryComplexity.COMPLEX:
            if self._semantic_cache is not None:
                return CacheLayer.SEMANTIC
            else:
                return CacheLayer.EXACT  # 回退

        # 中等复杂度：根据命中率决定
        if self._auto_optimize:
            if self._stats.exact_hit_rate > 0.7:
                return CacheLayer.EXACT
            elif self._enable_hybrid:
                return CacheLayer.HYBRID
            else:
                return CacheLayer.SEMANTIC if self._semantic_cache else CacheLayer.EXACT

        # 默认：混合模式
        return CacheLayer.HYBRID if self._enable_hybrid else CacheLayer.EXACT

    def clear(self) -> None:
        """清空所有缓存"""
        with self._lock:
            self._exact_cache.clear()
            if self._semantic_cache is not None:
                try:
                    self._semantic_cache.clear()
                except Exception:
                    pass
            self._stats = UnifiedCacheStats()
            logger.info("[UnifiedIntentCache] All caches cleared")

    def clear_exact(self) -> None:
        """清空精确缓存"""
        with self._lock:
            self._exact_cache.clear()
            logger.info("[UnifiedIntentCache] Exact cache cleared")

    def clear_semantic(self) -> None:
        """清空语义缓存"""
        with self._lock:
            if self._semantic_cache is not None:
                try:
                    self._semantic_cache.clear()
                except Exception as e:
                    logger.error(f"[UnifiedIntentCache] Failed to clear semantic cache: {e}")

    def warm_up_from_history(
        self,
        history: List[Tuple[str, Any]],
        batch_size: int = 100,
    ) -> int:
        """
        从历史事件批量预热缓存

        Args:
            history: [(query, response), ...]
            batch_size: 批量大小

        Returns:
            预热的条目数
        """
        count = 0
        for query, response in history:
            try:
                self.set(query, response, update_semantic=True)
                count += 1
                if count % batch_size == 0:
                    logger.info(f"[UnifiedIntentCache] Warming up: {count} entries...")
            except Exception as e:
                logger.error(f"[UnifiedIntentCache] Warm-up error for '{query}': {e}")

        logger.info(f"[UnifiedIntentCache] Warm-up completed: {count} entries")
        return count

    def optimize_routing(self) -> None:
        """
        优化路由策略

        根据最近的命中率统计，自动调整路由规则。
        """
        if not self._auto_optimize:
            return

        with self._lock:
            # 如果语义缓存可用，且精确缓存命中率低于 50%，增加语义路由比例
            if self._semantic_cache is not None:
                if self._stats.exact_hit_rate < 0.5:
                    self._prefer_exact_for_simple = False
                    logger.info(
                        "[UnifiedIntentCache] Routing optimized: "
                        "prefer_semantic_for_simple = True"
                    )
                else:
                    self._prefer_exact_for_simple = True

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            stats = self._stats.to_dict()
            stats["exact_cache_size"] = len(self._exact_cache)
            stats["semantic_available"] = self._semantic_cache is not None
            stats["hybrid_enabled"] = self._enable_hybrid
            stats["auto_optimize"] = self._auto_optimize
            return stats

    def __contains__(self, query: str) -> bool:
        """检查查询是否在缓存中（精确匹配）"""
        exact_key = self._compute_exact_key(query)
        return exact_key in self._exact_cache


# ──────────────────────────────────────────────────────────────
# 全局单例
# ──────────────────────────────────────────────────────────────

_global_cache: Optional[UnifiedIntentCache] = None
_cache_lock = threading.RLock()


def get_unified_intent_cache(
    exact_max_size: int = 1000,
    semantic_dim: int = 384,
    semantic_threshold: float = 0.85,
) -> UnifiedIntentCache:
    """
    获取统一意图缓存单例

    Args:
        exact_max_size: 精确缓存最大条目数
        semantic_dim: 语义向量维度
        semantic_threshold: 语义相似度阈值

    Returns:
        统一意图缓存实例
    """
    global _global_cache
    with _cache_lock:
        if _global_cache is None:
            _global_cache = UnifiedIntentCache(
                exact_max_size=exact_max_size,
                semantic_dim=semantic_dim,
                semantic_threshold=semantic_threshold,
            )
        return _global_cache


def reset_unified_intent_cache() -> None:
    """重置统一意图缓存（测试用）"""
    global _global_cache
    with _cache_lock:
        if _global_cache is not None:
            _global_cache.clear()
        _global_cache = None


# ──────────────────────────────────────────────────────────────
# 便捷装饰器
# ──────────────────────────────────────────────────────────────


def cached_intent_unified(ttl: Optional[float] = None):
    """
    统一意图缓存装饰器

    Args:
        ttl: 过期时间（仅用于精确缓存）

    Returns:
        装饰器函数
    """
    cache = get_unified_intent_cache()

    def decorator(func):
        def wrapper(query: str, **kwargs):
            # 尝试从缓存获取
            cached = cache.get(query, context=kwargs.get("context"))
            if cached is not None:
                return cached

            # 执行函数
            result = func(query, **kwargs)

            # 存入缓存
            cache.set(query, result, ttl=ttl)

            return result

        return wrapper

    return decorator
