"""
融合意图分类服务 (Hybrid Intent Classification Service)

将 L0 Router (SmolLM2) 和增强意图分类器融合：
1. 快速路径：增强意图分类器（规则引擎+相似度匹配）
2. 深度路径：L0 Router（SmolLM2语义理解）
3. 智能融合：根据置信度自动选择或融合结果

核心特性：
- 支持训练升级（动态添加训练数据）
- 可配置置信度阈值
- 支持多意图识别
- 支持实体识别
- 支持缓存优化
"""

import asyncio
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from loguru import logger

# 导入统一意图定义
from business.intent_definitions import Intent


@dataclass
class HybridIntentResult:
    """融合意图识别结果"""
    intent: str
    confidence: float
    entities: List[Dict] = field(default_factory=list)
    text: str = ""
    source: str = "hybrid"  # fast/classic/l0/fusion
    candidates: List[Dict] = field(default_factory=list)
    routing_decision: Optional[str] = None


@dataclass
class TrainingRecord:
    """训练记录"""
    text: str
    intent: str
    entities: List[Dict] = field(default_factory=list)
    confidence: float = 1.0
    timestamp: float = field(default_factory=lambda: time.time())


class HybridIntentClassifier:
    """融合意图分类器"""
    
    def __init__(self):
        self._logger = logger.bind(component="HybridIntentClassifier")
        
        # 组件
        self._fast_classifier = None  # 增强意图分类器
        self._l0_router = None       # L0 Router
        self._entity_recognizer = None
        
        # 配置
        self._config = {
            "fast_threshold": 0.7,        # 快速分类器置信度阈值
            "l0_fallback_threshold": 0.5, # L0降级阈值
            "fusion_enabled": True,       # 是否启用融合
            "enable_l0": True,            # 是否启用L0
            "enable_cache": True          # 是否启用缓存
        }
        
        # 训练数据存储
        self._training_records: List[TrainingRecord] = []
        
        # 缓存
        self._cache: Dict[str, HybridIntentResult] = {}
        
        # 统计
        self._stats = {
            "total_queries": 0,
            "fast_hits": 0,
            "l0_hits": 0,
            "fusion_hits": 0,
            "cache_hits": 0,
            "training_updates": 0
        }
        
        # 初始化组件
        self._init_components()
        
        self._logger.info("融合意图分类器初始化完成")
    
    def _init_components(self):
        """初始化组件"""
        # 1. 增强意图分类器（快速路径）
        try:
            from .intent_classifier import EnhancedIntentClassifier
            self._fast_classifier = EnhancedIntentClassifier()
            self._logger.info("✓ 集成 EnhancedIntentClassifier")
        except Exception as e:
            self._logger.warning(f"EnhancedIntentClassifier 加载失败: {e}")
        
        # 2. L0 Router（深度路径）
        try:
            from business.smolllm2.router import L0Router
            self._l0_router = L0Router(enable_cache=self._config["enable_cache"])
            self._logger.info("✓ 集成 L0Router (SmolLM2)")
        except Exception as e:
            self._logger.warning(f"L0Router 加载失败: {e}")
    
    async def classify(self, query: str, context: Dict = None) -> HybridIntentResult:
        """
        融合意图分类
        
        Args:
            query: 用户输入
            context: 上下文信息
        
        Returns:
            融合意图识别结果
        """
        self._stats["total_queries"] += 1
        
        # 1. 缓存检查
        if self._config["enable_cache"]:
            cache_key = self._hash_query(query)
            cached = self._cache.get(cache_key)
            if cached:
                self._stats["cache_hits"] += 1
                self._logger.debug(f"缓存命中: {query[:30]}...")
                return cached
        
        # 2. 快速分类器（增强意图分类器）
        fast_result = None
        if self._fast_classifier:
            fast_result = self._fast_classifier.classify(query)
            self._logger.debug(f"快速分类结果: {fast_result.intent} (置信度: {fast_result.confidence:.2f})")
        
        # 3. 决策逻辑
        if fast_result and fast_result.confidence >= self._config["fast_threshold"]:
            # 快速分类器置信度足够，直接返回
            self._stats["fast_hits"] += 1
            result = HybridIntentResult(
                intent=fast_result.intent,
                confidence=fast_result.confidence,
                entities=fast_result.entities,
                text=fast_result.text,
                source="fast"
            )
            self._cache_result(query, result)
            return result
        
        # 4. L0 Router（深度语义理解）
        l0_result = None
        if self._config["enable_l0"] and self._l0_router:
            try:
                l0_result = await self._l0_router.route(query)
                self._logger.debug(f"L0分类结果: {l0_result.route.value} (置信度: {l0_result.confidence:.2f})")
            except Exception as e:
                self._logger.warning(f"L0 Router 调用失败: {e}")
        
        # 5. 融合决策
        result = self._fusion_results(fast_result, l0_result, query)
        
        # 6. 缓存结果
        self._cache_result(query, result)
        
        return result
    
    def _fusion_results(self, fast_result, l0_result, query: str) -> HybridIntentResult:
        """融合多个分类器的结果"""
        candidates = []
        
        # 收集候选意图
        if fast_result:
            candidates.append({
                "intent": fast_result.intent,
                "confidence": fast_result.confidence,
                "source": "fast"
            })
        
        if l0_result:
            # L0 返回的是路由类型，需要转换为意图
            intent_from_l0 = self._map_route_to_intent(l0_result)
            candidates.append({
                "intent": intent_from_l0,
                "confidence": l0_result.confidence,
                "source": "l0",
                "route": l0_result.route.value
            })
        
        # 排序并选择最优
        candidates.sort(key=lambda x: x["confidence"], reverse=True)
        
        if not candidates:
            return HybridIntentResult(
                intent=Intent.NLU_FALLBACK.value,
                confidence=0.0,
                source="fallback"
            )
        
        # 选择最佳结果
        best = candidates[0]
        source = best["source"]
        routing_decision = best.get("route")
        
        # 如果有多个候选且置信度接近，标记为融合
        if self._config["fusion_enabled"] and len(candidates) > 1:
            confidence_diff = candidates[0]["confidence"] - candidates[1]["confidence"]
            if confidence_diff < 0.2:
                source = "fusion"
                self._stats["fusion_hits"] += 1
        
        entities = fast_result.entities if fast_result else []
        
        result = HybridIntentResult(
            intent=best["intent"],
            confidence=best["confidence"],
            entities=entities,
            text=query,
            source=source,
            candidates=candidates,
            routing_decision=routing_decision
        )
        
        # 更新统计
        if source == "l0":
            self._stats["l0_hits"] += 1
        
        return result
    
    def _map_route_to_intent(self, l0_result) -> str:
        """将 L0 路由类型映射为意图"""
        # 使用统一意图定义中心的路由映射
        route_map = Intent.get_routing_map()
        return route_map.get(l0_result.route.value, Intent.NLU_FALLBACK.value)
    
    def _hash_query(self, query: str) -> str:
        """哈希查询"""
        import hashlib
        return hashlib.md5(query.encode()).hexdigest()
    
    def _cache_result(self, query: str, result: HybridIntentResult):
        """缓存结果"""
        if self._config["enable_cache"]:
            cache_key = self._hash_query(query)
            self._cache[cache_key] = result
            
            # 限制缓存大小
            max_cache_size = 1000
            if len(self._cache) > max_cache_size:
                # 删除最旧的缓存（简单实现）
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
    
    def add_training_data(self, text: str, intent: str, entities: List[Dict] = None):
        """
        添加训练数据（支持训练升级）
        
        Args:
            text: 示例文本
            intent: 意图标签
            entities: 实体列表
        """
        # 添加到增强意图分类器
        if self._fast_classifier:
            self._fast_classifier.add_training_example(text, intent, entities)
        
        # 记录训练记录
        self._training_records.append(TrainingRecord(
            text=text,
            intent=intent,
            entities=entities or []
        ))
        
        self._stats["training_updates"] += 1
        self._logger.debug(f"添加训练数据: '{text[:30]}...' -> {intent}")
        
        # 清空相关缓存
        self._clear_cache_for_text(text)
    
    def add_training_batch(self, training_data: List[Dict]):
        """批量添加训练数据"""
        for item in training_data:
            self.add_training_data(
                text=item["text"],
                intent=item["intent"],
                entities=item.get("entities")
            )
        self._logger.info(f"批量添加训练数据: {len(training_data)} 条")
    
    def _clear_cache_for_text(self, text: str):
        """清除相关缓存"""
        cache_key = self._hash_query(text)
        if cache_key in self._cache:
            del self._cache[cache_key]
    
    def set_config(self, key: str, value):
        """设置配置"""
        if key in self._config:
            self._config[key] = value
            self._logger.debug(f"配置更新: {key} = {value}")
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "total_queries": self._stats["total_queries"],
            "fast_hits": self._stats["fast_hits"],
            "l0_hits": self._stats["l0_hits"],
            "fusion_hits": self._stats["fusion_hits"],
            "cache_hits": self._stats["cache_hits"],
            "training_updates": self._stats["training_updates"],
            "cache_size": len(self._cache),
            "training_records": len(self._training_records),
            "config": self._config.copy()
        }
    
    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        self._logger.info("缓存已清空")
    
    async def classify_multi_intent(self, query: str, top_n: int = 3) -> List[Dict]:
        """多意图识别"""
        # 获取所有候选意图
        result = await self.classify(query)
        return result.candidates[:top_n]
    
    def classify_sync(self, query: str) -> HybridIntentResult:
        """同步分类（方便在同步代码中使用）"""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.classify(query))


# 单例模式
_hybrid_classifier_instance = None

def get_hybrid_intent_classifier() -> HybridIntentClassifier:
    """获取融合意图分类器实例"""
    global _hybrid_classifier_instance
    if _hybrid_classifier_instance is None:
        _hybrid_classifier_instance = HybridIntentClassifier()
    return _hybrid_classifier_instance


# ==================== 便捷函数 ====================

async def classify_intent(query: str, context: Dict = None) -> HybridIntentResult:
    """便捷分类函数"""
    classifier = get_hybrid_intent_classifier()
    return await classifier.classify(query, context)


def classify_intent_sync(query: str) -> HybridIntentResult:
    """同步便捷分类函数"""
    classifier = get_hybrid_intent_classifier()
    return classifier.classify_sync(query)


def train_intent_classifier(text: str, intent: str, entities: List[Dict] = None):
    """训练意图分类器"""
    classifier = get_hybrid_intent_classifier()
    classifier.add_training_data(text, intent, entities)


def get_intent_classifier_stats() -> Dict:
    """获取分类器统计信息"""
    classifier = get_hybrid_intent_classifier()
    return classifier.get_stats()


if __name__ == "__main__":
    print("=" * 60)
    print("融合意图分类器测试")
    print("=" * 60)
    
    # 初始化分类器
    classifier = get_hybrid_intent_classifier()
    
    # 添加训练数据（使用统一意图定义）
    training_data = [
        {"text": "你好", "intent": Intent.GREET.value},
        {"text": "帮我写代码", "intent": Intent.CODE_GENERATION.value},
        {"text": "什么是人工智能", "intent": Intent.QUERY_KNOWLEDGE.value},
        {"text": "修复错误", "intent": Intent.ERROR_RECOVERY.value},
        {"text": "查一下库存", "intent": Intent.SEARCH_QUERY.value},
        {"text": "写一篇报告", "intent": Intent.LONG_WRITING.value},
        {"text": "谢谢", "intent": Intent.THANKS.value},
        {"text": "再见", "intent": Intent.GOODBYE.value}
    ]
    classifier.add_training_batch(training_data)
    
    # 测试分类
    test_queries = [
        "你好！",
        "帮我写一个Python函数",
        "什么是机器学习？",
        "如何修复代码错误？",
        "查一下今天的股票行情",
        "写一篇市场分析报告",
        "谢谢！",
        "这个问题比较复杂，需要深入分析"
    ]
    
    print("\n[1] 融合意图分类测试")
    for query in test_queries:
        result = classifier.classify_sync(query)
        print(f'"{query}"')
        print(f'  -> 意图: {result.intent}, 置信度: {result.confidence:.2f}, 来源: {result.source}')
        if result.candidates:
            print(f'  -> 候选: {[(c["intent"], c["confidence"]) for c in result.candidates]}')
    
    # 测试训练升级
    print("\n[2] 测试训练升级")
    print(f"添加新训练数据: '帮我查天气' -> {Intent.WEATHER_QUERY.value}")
    classifier.add_training_data("帮我查天气", Intent.WEATHER_QUERY.value)
    
    result = classifier.classify_sync("帮我查一下明天的天气")
    print(f'"帮我查一下明天的天气"')
    print(f'  -> 意图: {result.intent}, 置信度: {result.confidence:.2f}, 来源: {result.source}')
    
    # 统计信息
    print("\n[3] 统计信息")
    stats = classifier.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)