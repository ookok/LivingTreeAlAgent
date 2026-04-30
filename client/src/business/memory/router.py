"""
自适应记忆路由器 (Adaptive Memory Router)

核心功能：
1. 意图分析 - 识别查询意图类型（增强版）
2. 上下文感知 - 考虑当前对话上下文
3. 策略决策 - 根据策略选择记忆源
4. 性能监控 - 实时监控各记忆类型的访问统计
5. 异步支持 - 支持异步查询提高性能
6. 结果融合 - 合并多源结果

路由策略优先级：
1. 会话级记忆 (short_term) - 最快，优先检查
2. 检索级记忆 (mid_term) - 中等速度，主要数据源
3. 长期知识 (long_term) - 较慢，用于复杂推理
4. 特殊记忆 (error/evolution) - 根据意图匹配
"""

import time
import asyncio
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from loguru import logger

# 导入统一意图定义
from business.intent_definitions import Intent


@dataclass
class MemoryType:
    """记忆类型定义"""
    name: str
    priority: int
    latency_ms: int
    capacity: str
    retention_hours: Optional[int] = None


@dataclass
class RouteResult:
    """路由结果"""
    memory_type: str
    confidence: float
    latency_ms: int = 0
    result: Optional[Dict] = None


@dataclass
class PerformanceMetrics:
    """性能指标"""
    total_queries: int = 0
    total_latency_ms: int = 0
    hits: int = 0
    misses: int = 0
    avg_latency_ms: float = 0.0
    hit_rate: float = 0.0
    
    def update(self, latency_ms: int, hit: bool):
        """更新指标"""
        self.total_queries += 1
        self.total_latency_ms += latency_ms
        if hit:
            self.hits += 1
        else:
            self.misses += 1
        self.avg_latency_ms = self.total_latency_ms / self.total_queries
        self.hit_rate = self.hits / self.total_queries if self.total_queries > 0 else 0.0


class PolicyEngine:
    """策略引擎 - 根据意图和上下文选择记忆源"""
    
    def __init__(self):
        self._logger = logger.bind(component="PolicyEngine")
        
        self._memory_types = {
            "short_term": MemoryType(
                name="short_term", priority=1, latency_ms=10, 
                capacity="limited", retention_hours=1
            ),
            "mid_term": MemoryType(
                name="mid_term", priority=2, latency_ms=100, 
                capacity="large", retention_hours=720
            ),
            "long_term": MemoryType(
                name="long_term", priority=3, latency_ms=1000, 
                capacity="unlimited", retention_hours=None
            ),
            "error": MemoryType(
                name="error", priority=2, latency_ms=50, 
                capacity="medium", retention_hours=168
            ),
            "evolution": MemoryType(
                name="evolution", priority=3, latency_ms=200, 
                capacity="large", retention_hours=None
            )
        }
        
        # 使用统一意图定义中心的意图路由映射
        self._intent_routing = {
            Intent.DOCUMENT_QUERY.value: ["mid_term", "long_term"],
            Intent.ERROR_RECOVERY.value: ["error", "short_term", "mid_term"],
            Intent.CODE_GENERATION.value: ["mid_term", "long_term"],
            Intent.EVOLUTION_DECISION.value: ["evolution", "long_term", "mid_term"],
            Intent.SIMPLE_QA.value: ["short_term", "mid_term"],
            Intent.COMPLEX_REASONING.value: ["long_term", "mid_term", "short_term"],
            Intent.QUERY_KNOWLEDGE.value: ["short_term", "mid_term", "long_term"],
            Intent.CONFIGURATION.value: ["long_term", "mid_term"],
            Intent.NLU_FALLBACK.value: ["short_term", "mid_term", "long_term"]
        }
    
    def select(self, intent: Dict, context: Dict, performance: Dict) -> List[str]:
        """
        根据意图、上下文和性能数据选择记忆源
        
        Args:
            intent: 意图分类结果
            context: 上下文特征
            performance: 性能统计数据
        
        Returns:
            按优先级排序的记忆类型列表
        """
        intent_type = intent.get("type", "unknown")
        confidence = intent.get("confidence", 0.5)
        
        # 获取基础路由列表
        base_routes = self._intent_routing.get(intent_type, self._intent_routing[Intent.NLU_FALLBACK.value])
        
        # 根据性能数据动态调整
        adjusted_routes = self._adjust_by_performance(base_routes, performance)
        
        # 根据上下文调整
        final_routes = self._adjust_by_context(adjusted_routes, context)
        
        self._logger.debug(f"路由选择: {intent_type} (置信度: {confidence:.2f}) -> {final_routes}")
        
        return final_routes
    
    def _adjust_by_performance(self, routes: List[str], performance: Dict) -> List[str]:
        """根据性能数据调整路由优先级"""
        adjusted = routes.copy()
        
        # 如果某项记忆类型延迟过高，降低优先级
        for i, mem_type in enumerate(adjusted[:]):
            avg_latency = performance.get(f"{mem_type}_latency_ms", 0)
            if avg_latency > self._memory_types[mem_type].latency_ms * 10:
                # 延迟超过预期10倍，移到末尾
                adjusted.remove(mem_type)
                adjusted.append(mem_type)
                self._logger.debug(f"性能调整: {mem_type} 延迟过高，移到末尾")
        
        return adjusted
    
    def _adjust_by_context(self, routes: List[str], context: Dict) -> List[str]:
        """根据上下文调整路由优先级"""
        adjusted = routes.copy()
        
        # 如果有会话ID，优先检查短-term记忆
        if context.get("session_id") and "short_term" in adjusted and adjusted[0] != "short_term":
            adjusted.remove("short_term")
            adjusted.insert(0, "short_term")
        
        # 如果查询涉及错误处理，优先检查error记忆
        if (context.get("is_error_recovery") or context.get("has_failed_attempts")):
            if "error" in adjusted and adjusted[0] != "error":
                adjusted.remove("error")
                adjusted.insert(0, "error")
        
        # 如果涉及进化决策，优先检查evolution记忆
        if context.get("is_evolution"):
            if "evolution" in adjusted and adjusted[0] != "evolution":
                adjusted.remove("evolution")
                adjusted.insert(0, "evolution")
        
        return adjusted


class PerformanceTracker:
    """性能追踪器 - 记录各记忆类型的访问性能"""
    
    def __init__(self):
        self._stats: Dict[str, PerformanceMetrics] = {
            "short_term": PerformanceMetrics(),
            "mid_term": PerformanceMetrics(),
            "long_term": PerformanceMetrics(),
            "error": PerformanceMetrics(),
            "evolution": PerformanceMetrics()
        }
        self._total_queries = 0
        self._start_time = time.time()
        self._logger = logger.bind(component="PerformanceTracker")
    
    def record_query(self, memory_type: str, latency_ms: int, hit: bool):
        """记录查询性能"""
        if memory_type in self._stats:
            self._stats[memory_type].update(latency_ms, hit)
            self._total_queries += 1
            
            # 定期输出统计
            if self._total_queries % 100 == 0:
                self._logger.info(f"累计查询: {self._total_queries}")
    
    def get_stats(self) -> Dict:
        """获取性能统计"""
        result = {}
        for mem_type, metrics in self._stats.items():
            result[f"{mem_type}_latency_ms"] = metrics.avg_latency_ms
            result[f"{mem_type}_hits"] = metrics.hits
            result[f"{mem_type}_misses"] = metrics.misses
            result[f"{mem_type}_hit_rate"] = metrics.hit_rate
        
        result["total_queries"] = self._total_queries
        result["uptime_seconds"] = time.time() - self._start_time
        
        return result
    
    def get_detailed_stats(self) -> Dict:
        """获取详细统计"""
        result = {}
        for mem_type, metrics in self._stats.items():
            result[mem_type] = {
                "total_queries": metrics.total_queries,
                "total_latency_ms": metrics.total_latency_ms,
                "avg_latency_ms": metrics.avg_latency_ms,
                "hits": metrics.hits,
                "misses": metrics.misses,
                "hit_rate": metrics.hit_rate
            }
        return result


class EnhancedIntentClassifier:
    """增强版意图分类器"""
    
    def __init__(self):
        self._logger = logger.bind(component="EnhancedIntentClassifier")
        
        # 意图关键词映射（增强版）
        self._intent_keywords = {
            "document_query": [
                "文档", "文件", "查找", "搜索", "知识库", "手册", "指南",
                "资料", "文档", "说明", "帮助", "文档中心", "知识库查询"
            ],
            "error_recovery": [
                "错误", "失败", "异常", "重试", "修复", "问题", "崩溃",
                "报错", "异常处理", "错误处理", "故障", "bug", "exception"
            ],
            "code_generation": [
                "代码", "编程", "python", "java", "function", "函数", "方法",
                "代码生成", "写代码", "实现", "开发", "脚本", "程序", "api"
            ],
            "evolution_decision": [
                "进化", "升级", "优化", "训练", "学习", "改进", "自我进化",
                "模型升级", "系统优化", "自适应", "进化策略"
            ],
            "simple_qa": [
                "什么是", "什么", "如何", "为什么", "怎么样", "介绍", "说明",
                "解释", "定义", "含义", "概念", "基础", "入门"
            ],
            "complex_reasoning": [
                "分析", "推理", "论证", "证明", "推导", "逻辑", "复杂",
                "深入", "详细", "探讨", "研究", "分析报告", "深度分析"
            ],
            "personal_knowledge": [
                "我的", "个人", "记录", "笔记", "日记", "日程", "计划",
                "个人信息", "我的资料", "个人设置", "偏好"
            ],
            "system_prompt": [
                "系统", "设置", "配置", "参数", "选项", "命令", "帮助",
                "关于", "版本", "更新", "升级", "系统信息"
            ]
        }
        
        # 否定词（降低置信度）
        self._negative_keywords = ["不", "不要", "无", "没有", "不是", "无法"]
    
    def classify(self, query: str) -> Dict:
        """分类查询意图（增强版）"""
        query_lower = query.lower()
        
        # 计算否定词数量（影响置信度）
        negative_count = sum(1 for kw in self._negative_keywords if kw in query_lower)
        
        # 查找匹配的意图
        matched_intents = []
        
        for intent_type, keywords in self._intent_keywords.items():
            matched_keywords = [kw for kw in keywords if kw in query_lower]
            if matched_keywords:
                # 计算匹配分数
                score = len(matched_keywords) / len(keywords)
                matched_intents.append((intent_type, score))
        
        if matched_intents:
            # 排序并选择最高分
            matched_intents.sort(key=lambda x: x[1], reverse=True)
            best_intent, confidence = matched_intents[0]
            
            # 根据否定词调整置信度
            confidence = max(0.3, confidence - negative_count * 0.15)
            
            # 如果有多个意图匹配，取最高置信度
            return {
                "type": best_intent,
                "confidence": confidence,
                "matched_keywords": self._intent_keywords[best_intent],
                "candidates": [(i, c) for i, c in matched_intents[:3]]
            }
        
        # 默认返回未知
        return {"type": "unknown", "confidence": 0.5}


class AdaptiveMemoryRouter:
    """自适应记忆路由器"""
    
    def __init__(self):
        self._logger = logger.bind(component="AdaptiveMemoryRouter")
        self._policy_engine = PolicyEngine()
        self._performance_tracker = PerformanceTracker()
        self._intent_classifier = EnhancedIntentClassifier()
        
        # 延迟加载记忆组件
        self._memory_cache = {}
        
        self._logger.info("自适应记忆路由器初始化完成")
    
    def _get_memory(self, memory_type: str):
        """延迟加载记忆组件"""
        if memory_type not in self._memory_cache:
            self._memory_cache[memory_type] = self._create_memory(memory_type)
        
        return self._memory_cache[memory_type]
    
    def _create_memory(self, memory_type: str):
        """创建记忆组件实例"""
        try:
            if memory_type == "short_term":
                from .short_term import SessionMemory
                return SessionMemory()
            
            elif memory_type == "mid_term":
                from .mid_term import VectorMemory
                return VectorMemory()
            
            elif memory_type == "long_term":
                from .long_term import KnowledgeGraphMemory
                return KnowledgeGraphMemory()
            
            elif memory_type == "error":
                from .specialized import ErrorMemory
                return ErrorMemory()
            
            elif memory_type == "evolution":
                from .specialized import EvolutionMemory
                return EvolutionMemory()
            
            else:
                self._logger.warning(f"未知记忆类型: {memory_type}")
                return None
        
        except Exception as e:
            self._logger.error(f"创建记忆组件失败 {memory_type}: {e}")
            return None
    
    def _analyze_intent(self, query: str) -> Dict:
        """分析查询意图（使用增强版分类器）"""
        return self._intent_classifier.classify(query)
    
    def route(self, query: str, context: Dict) -> List[str]:
        """
        自适应路由决策
        
        Returns:
            按优先级排序的记忆类型列表
        """
        # 1. 意图分析
        intent = self._analyze_intent(query)
        
        # 2. 上下文特征提取
        context_features = self._extract_context_features(context)
        
        # 3. 策略决策
        candidates = self._policy_engine.select(
            intent=intent,
            context=context_features,
            performance=self._performance_tracker.get_stats()
        )
        
        return candidates
    
    def _extract_context_features(self, context: Dict) -> Dict:
        """提取上下文特征"""
        return {
            "has_session_id": bool(context.get("session_id")),
            "has_history": bool(context.get("history")),
            "is_error_recovery": bool(context.get("is_error_recovery")),
            "has_failed_attempts": bool(context.get("failed_attempts", 0) > 0),
            "is_evolution": bool(context.get("is_evolution")),
            "user_role": context.get("user_role"),
            "query_length": len(context.get("query", "")),
            "timestamp": context.get("timestamp", time.time())
        }
    
    def query(self, query: str, context: Dict = None) -> Dict:
        """
        统一查询接口（同步）
        
        Args:
            query: 查询内容
            context: 上下文信息
        
        Returns:
            包含结果、来源、置信度等信息的字典
        """
        context = context or {}
        results = []
        best_result = None
        best_confidence = 0.0
        
        # 获取路由列表
        routes = self.route(query, context)
        
        # 按优先级依次查询
        for memory_type in routes:
            memory = self._get_memory(memory_type)
            if not memory:
                continue
            
            start_time = time.time()
            
            try:
                result = memory.query(query, context)
                
                latency_ms = int((time.time() - start_time) * 1000)
                confidence = result.get("confidence", 0.0)
                
                route_result = RouteResult(
                    memory_type=memory_type,
                    confidence=confidence,
                    latency_ms=latency_ms,
                    result=result
                )
                results.append(route_result)
                
                # 记录性能
                self._performance_tracker.record_query(
                    memory_type, latency_ms, confidence > 0.5
                )
                
                # 更新最佳结果
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_result = result
                    best_result["memory_source"] = memory_type
                
                # 如果置信度足够高，提前返回
                if confidence >= 0.9:
                    self._logger.debug(f"高置信度命中 ({confidence})，提前返回")
                    break
            
            except Exception as e:
                self._logger.error(f"查询 {memory_type} 失败: {e}")
        
        # 如果没有找到结果，返回空结果
        if best_result is None:
            best_result = {
                "success": False,
                "content": "",
                "confidence": 0.0,
                "memory_source": "none",
                "message": "未找到相关记忆"
            }
        
        # 添加路由信息
        best_result["routes"] = routes
        best_result["all_results"] = [
            {"type": r.memory_type, "confidence": r.confidence, "latency_ms": r.latency_ms}
            for r in results
        ]
        
        return best_result
    
    async def query_async(self, query: str, context: Dict = None) -> Dict:
        """
        统一查询接口（异步）
        
        Args:
            query: 查询内容
            context: 上下文信息
        
        Returns:
            包含结果、来源、置信度等信息的字典
        """
        context = context or {}
        
        # 获取路由列表
        routes = self.route(query, context)
        
        # 并行查询所有记忆源
        tasks = []
        for memory_type in routes:
            memory = self._get_memory(memory_type)
            if memory:
                tasks.append(self._query_memory_async(memory, memory_type, query, context))
        
        # 并发执行
        results = await asyncio.gather(*tasks)
        
        # 找到最佳结果
        best_result = None
        best_confidence = 0.0
        
        for result in results:
            if result:
                confidence = result.get("confidence", 0.0)
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_result = result
        
        if best_result is None:
            best_result = {
                "success": False,
                "content": "",
                "confidence": 0.0,
                "memory_source": "none",
                "message": "未找到相关记忆"
            }
        
        best_result["routes"] = routes
        best_result["all_results"] = [
            {"type": r.get("memory_source", "unknown"), "confidence": r.get("confidence", 0.0)}
            for r in results if r
        ]
        
        return best_result
    
    async def _query_memory_async(self, memory, memory_type: str, query: str, context: Dict):
        """异步查询单个记忆源"""
        start_time = time.time()
        
        try:
            # 如果支持异步查询，使用异步方法
            if hasattr(memory, 'query_async'):
                result = await memory.query_async(query, context)
            else:
                # 否则在线程池中执行同步查询
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, memory.query, query, context)
            
            latency_ms = int((time.time() - start_time) * 1000)
            self._performance_tracker.record_query(memory_type, latency_ms, result.get("confidence", 0.0) > 0.5)
            
            return result
        
        except Exception as e:
            self._logger.error(f"异步查询 {memory_type} 失败: {e}")
            return None
    
    def store(self, content: str, memory_type: str = "mid_term", **kwargs) -> str:
        """
        统一存储接口
        
        Args:
            content: 要存储的内容
            memory_type: 记忆类型
            **kwargs: 额外参数
        
        Returns:
            存储的ID
        """
        memory = self._get_memory(memory_type)
        if not memory:
            self._logger.error(f"存储失败：未知记忆类型 {memory_type}")
            return ""
        
        try:
            return memory.store(content, **kwargs)
        except Exception as e:
            self._logger.error(f"存储失败 {memory_type}: {e}")
            return ""
    
    async def store_async(self, content: str, memory_type: str = "mid_term", **kwargs) -> str:
        """
        统一存储接口（异步）
        
        Args:
            content: 要存储的内容
            memory_type: 记忆类型
            **kwargs: 额外参数
        
        Returns:
            存储的ID
        """
        memory = self._get_memory(memory_type)
        if not memory:
            self._logger.error(f"异步存储失败：未知记忆类型 {memory_type}")
            return ""
        
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, memory.store, content, kwargs)
        except Exception as e:
            self._logger.error(f"异步存储失败 {memory_type}: {e}")
            return ""
    
    def get_stats(self) -> Dict:
        """获取路由器统计信息"""
        return {
            "performance": self._performance_tracker.get_stats(),
            "detailed_performance": self._performance_tracker.get_detailed_stats(),
            "memory_types": list(self._memory_cache.keys()),
            "total_queries": self._performance_tracker._total_queries
        }
    
    def reset_stats(self):
        """重置统计信息"""
        self._performance_tracker = PerformanceTracker()
        self._logger.info("性能统计已重置")


# 单例模式
_router_instance = None

def get_memory_router() -> AdaptiveMemoryRouter:
    """获取自适应记忆路由器实例"""
    global _router_instance
    if _router_instance is None:
        _router_instance = AdaptiveMemoryRouter()
    return _router_instance


if __name__ == "__main__":
    print("=" * 60)
    print("自适应记忆路由器测试")
    print("=" * 60)
    
    router = get_memory_router()
    
    # 测试意图分类（增强版）
    print("\n[1] 测试意图分类（增强版）")
    test_queries = [
        "如何修复代码中的错误？",
        "帮我写一个 Python 函数",
        "解释一下量子计算的原理",
        "查找用户手册文档",
        "系统如何进行自我进化？",
        "不要帮我写代码"
    ]
    
    for query in test_queries:
        intent = router._analyze_intent(query)
        print(f'"{query}"')
        print(f'  -> 意图: {intent["type"]}, 置信度: {intent["confidence"]:.2f}')
        if intent.get("candidates"):
            print(f'  -> 候选: {intent["candidates"]}')
    
    # 测试查询
    print("\n[2] 测试查询")
    result = router.query("什么是人工智能？")
    print(f'查询 "什么是人工智能？":')
    print(f'  来源: {result.get("memory_source")}')
    print(f'  置信度: {result.get("confidence", 0):.2f}')
    
    # 测试性能统计
    print("\n[3] 测试性能统计")
    stats = router.get_stats()
    print(f'总查询数: {stats["total_queries"]}')
    print(f'详细性能: {stats["detailed_performance"]}')
    
    print("\n" + "=" * 60)