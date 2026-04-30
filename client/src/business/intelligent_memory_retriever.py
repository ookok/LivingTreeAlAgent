"""
智能记忆检索器 (Intelligent Memory Retriever)
============================================

借鉴 Claude Managed Agents 的智能检索能力：
1. 意图识别 - 识别用户查询意图类型
2. 相关性判断 - 判断是否需要检索记忆
3. 多策略检索 - 关键词+语义向量混合检索
4. 结果排序 - 按相关性和时间排序
5. 上下文融合 - 将检索结果融入响应

核心特性：
- 智能判断何时需要检索记忆
- 支持多种检索策略
- 自动融合上下文
- 可配置的检索阈值

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import json
import time
import asyncio
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4

from business.unified_memory import (
    MemoryRouter,
    MemoryItem,
    MemoryType,
    MemoryQuery,
)
from business.auto_memory_manager import get_auto_memory_manager

logger = __import__('logging').getLogger(__name__)


class QueryIntent(Enum):
    """查询意图类型"""
    MEMORY_RETRIEVAL = "memory_retrieval"    # 明确的记忆检索请求
    CONTEXTUAL = "contextual"                # 需要上下文理解的查询
    STANDALONE = "standalone"                # 独立查询，不需要记忆
    SUMMARY = "summary"                      # 摘要请求
    FOLLOW_UP = "follow_up"                  # 跟进问题
    UNKNOWN = "unknown"                      # 未知意图


class RetrievalStrategy(Enum):
    """检索策略"""
    KEYWORD = "keyword"           # 关键词检索
    SEMANTIC = "semantic"         # 语义向量检索
    HYBRID = "hybrid"             # 混合检索（关键词+语义）
    CHRONOLOGICAL = "chronological" # 时间顺序检索


@dataclass
class RetrievalResult:
    """检索结果"""
    items: List[Dict[str, Any]]
    intent: QueryIntent
    strategy: RetrievalStrategy
    confidence: float              # 检索置信度 0-1
    relevance_score: float         # 相关性分数 0-1
    total_found: int
    execution_time: float


@dataclass
class IntentAnalysis:
    """意图分析结果"""
    intent: QueryIntent
    confidence: float
    keywords: List[str]
    entities: List[str]
    requires_memory: bool


class IntelligentMemoryRetriever:
    """
    智能记忆检索器
    
    核心功能：
    1. 分析用户查询意图
    2. 智能判断是否需要检索记忆
    3. 选择最优检索策略
    4. 执行检索并返回结果
    5. 融合上下文到响应中
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
        
        self._memory_router = MemoryRouter.get_instance()
        self._auto_memory = get_auto_memory_manager()
        
        # 意图关键词
        self._intent_keywords = {
            QueryIntent.MEMORY_RETRIEVAL: [
                "记得", "回忆", "之前", "上次", "之前说", "之前讨论",
                "历史", "过去", "以前", "曾经", "之前提到", "之前的",
                "之前做的", "之前完成的", "之前讨论的", "之前决定的",
            ],
            QueryIntent.CONTEXTUAL: [
                "这个", "那个", "它", "该", "此", "上述", "以上",
                "继续", "接下来", "然后", "之后", "下一步",
            ],
            QueryIntent.SUMMARY: [
                "总结", "概括", "回顾", "整理", "复述", "要点",
                "摘要", "归纳", "汇总",
            ],
            QueryIntent.FOLLOW_UP: [
                "为什么", "如何", "怎么", "什么", "哪个", "是否",
                "还有", "另外", "此外", "同时", "也", "还",
            ],
        }
        
        # 配置参数
        self._config = {
            "min_confidence": 0.3,      # 最小置信度阈值
            "relevance_threshold": 0.5,  # 相关性阈值
            "default_strategy": "hybrid",
            "max_results": 10,
            "enable_auto_retrieval": True,
        }
        
        # LLM 调用函数（用于意图分析增强）
        self._llm_callable = None
        
        self._initialized = True
        logger.info("[IntelligentMemoryRetriever] 智能记忆检索器初始化完成")
    
    def set_llm_callable(self, llm_callable: Callable[[str], str]):
        """设置 LLM 调用函数"""
        self._llm_callable = llm_callable
    
    def configure(self, **kwargs):
        """配置检索器"""
        self._config.update(kwargs)
        logger.info(f"[IntelligentMemoryRetriever] 配置更新: {kwargs}")
    
    def analyze_intent(self, query: str, conversation_history: List[Dict] = None) -> IntentAnalysis:
        """
        分析用户查询意图
        
        Args:
            query: 用户查询
            conversation_history: 对话历史（可选）
            
        Returns:
            IntentAnalysis: 意图分析结果
        """
        query_lower = query.lower()
        
        # 计算各意图的置信度
        intent_confidences = {}
        
        for intent, keywords in self._intent_keywords.items():
            matched = sum(1 for keyword in keywords if keyword in query_lower)
            confidence = min(matched / len(keywords), 1.0)
            intent_confidences[intent] = confidence
        
        # 找到最可能的意图
        max_intent = max(intent_confidences, key=intent_confidences.get)
        max_confidence = intent_confidences[max_intent]
        
        # 如果置信度太低，使用 LLM 增强分析
        if max_confidence < self._config["min_confidence"] and self._llm_callable:
            enhanced_intent = self._enhance_intent_analysis(query)
            if enhanced_intent:
                max_intent = enhanced_intent
                max_confidence = min(max_confidence + 0.3, 1.0)
        
        # 提取关键词和实体
        keywords = self._extract_keywords(query)
        entities = self._extract_entities(query)
        
        # 判断是否需要记忆
        requires_memory = self._determine_requires_memory(
            max_intent, 
            max_confidence, 
            len(conversation_history) if conversation_history else 0
        )
        
        return IntentAnalysis(
            intent=max_intent,
            confidence=max_confidence,
            keywords=keywords,
            entities=entities,
            requires_memory=requires_memory
        )
    
    def retrieve(self, query: str, conversation_id: str = None, 
                 conversation_history: List[Dict] = None) -> RetrievalResult:
        """
        执行智能记忆检索
        
        Args:
            query: 用户查询
            conversation_id: 对话ID
            conversation_history: 对话历史
            
        Returns:
            RetrievalResult: 检索结果
        """
        start_time = time.time()
        
        # 分析意图
        intent_analysis = self.analyze_intent(query, conversation_history)
        
        if not intent_analysis.requires_memory:
            return RetrievalResult(
                items=[],
                intent=intent_analysis.intent,
                strategy=RetrievalStrategy.KEYWORD,
                confidence=intent_analysis.confidence,
                relevance_score=0.0,
                total_found=0,
                execution_time=time.time() - start_time
            )
        
        # 选择检索策略
        strategy = self._select_strategy(intent_analysis)
        
        # 执行检索
        items = self._execute_retrieval(query, intent_analysis, strategy)
        
        # 计算相关性分数
        relevance_score = self._calculate_relevance(items, query)
        
        # 排序结果
        items = self._rank_results(items, query)
        
        # 限制结果数量
        items = items[:self._config["max_results"]]
        
        return RetrievalResult(
            items=items,
            intent=intent_analysis.intent,
            strategy=strategy,
            confidence=intent_analysis.confidence,
            relevance_score=relevance_score,
            total_found=len(items),
            execution_time=time.time() - start_time
        )
    
    async def retrieve_async(self, query: str, conversation_id: str = None,
                            conversation_history: List[Dict] = None) -> RetrievalResult:
        """异步执行检索"""
        return self.retrieve(query, conversation_id, conversation_history)
    
    def should_retrieve(self, query: str, conversation_history: List[Dict] = None) -> bool:
        """
        判断是否需要检索记忆（简化版）
        
        Args:
            query: 用户查询
            conversation_history: 对话历史
            
        Returns:
            bool: 是否需要检索
        """
        intent_analysis = self.analyze_intent(query, conversation_history)
        return intent_analysis.requires_memory
    
    def get_context_for_response(self, query: str, conversation_id: str = None,
                                conversation_history: List[Dict] = None) -> str:
        """
        获取用于响应的上下文信息
        
        将检索到的记忆结果格式化为上下文字符串
        
        Args:
            query: 用户查询
            conversation_id: 对话ID
            conversation_history: 对话历史
            
        Returns:
            上下文字符串（用于拼接到 prompt 中）
        """
        result = self.retrieve(query, conversation_id, conversation_history)
        
        if not result.items:
            return ""
        
        # 构建上下文
        context_parts = []
        
        # 添加摘要
        if conversation_id:
            summary = self._auto_memory.get_conversation_summary(conversation_id)
            if summary:
                context_parts.append(f"【对话摘要】\n{summary.content}\n")
        
        # 添加相关记忆
        if result.items:
            context_parts.append("【相关记忆】")
            for i, item in enumerate(result.items[:5], 1):
                content = item.get("content", "")
                if len(content) > 200:
                    content = content[:200] + "..."
                context_parts.append(f"{i}. {content}")
        
        return "\n".join(context_parts)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "config": self._config,
            "intent_types": [i.value for i in QueryIntent],
            "strategies": [s.value for s in RetrievalStrategy],
        }
    
    # ========== 私有方法 ==========
    
    def _enhance_intent_analysis(self, query: str) -> Optional[QueryIntent]:
        """使用 LLM 增强意图分析"""
        try:
            prompt = f"""分析以下用户查询的意图类型：
            
查询：{query}

请选择意图类型（仅输出类型名称）：
- memory_retrieval: 用户明确要求回忆或检索之前的信息
- contextual: 查询需要上下文理解，依赖之前的对话
- standalone: 查询是独立的，不需要之前的对话上下文
- summary: 用户要求总结或概括
- follow_up: 用户在追问或跟进之前的问题
- unknown: 无法确定意图

输出格式：仅输出类型名称，不要其他内容"""
            
            response = self._llm_callable(prompt)
            response = response.strip()
            
            try:
                return QueryIntent(response)
            except ValueError:
                return None
                
        except Exception as e:
            logger.error(f"[IntelligentMemoryRetriever] 意图增强分析失败: {e}")
            return None
    
    def _extract_keywords(self, query: str) -> List[str]:
        """提取关键词"""
        # 简单的关键词提取（可以扩展为使用分词器）
        import re
        
        # 移除标点符号
        punctuation = r'[, .!?、;:\"\'（）\[\]{}]'
        cleaned = re.sub(punctuation, ' ', query)
        words = cleaned.split()
        
        # 过滤停用词
        stop_words = {"的", "是", "在", "有", "和", "了", "我", "你", "他", "她", "它",
                      "这", "那", "哪", "什么", "怎么", "为什么", "如何", "一个", "一些"}
        
        keywords = [word for word in words if word not in stop_words and len(word) >= 2]
        return keywords[:10]  # 最多10个关键词
    
    def _extract_entities(self, query: str) -> List[str]:
        """提取实体"""
        import re
        
        # 匹配大写开头的单词（可能是实体）
        entity_pattern = r'\b[A-Z][a-zA-Z]+\b'
        entities = re.findall(entity_pattern, query)
        
        # 匹配中文实体（包含特定关键词的短语）
        chinese_entities = []
        entity_keywords = ["公司", "产品", "项目", "系统", "功能", "模块", "方法", "类", "文件"]
        for keyword in entity_keywords:
            if keyword in query:
                # 尝试提取实体名称
                parts = query.split(keyword)
                if len(parts) > 1:
                    # 获取关键词前面的内容作为实体名称
                    prefix = parts[0].strip()
                    if prefix:
                        # 取最后一个词作为实体名
                        words = prefix.split()
                        if words:
                            chinese_entities.append(words[-1] + keyword)
        
        return list(set(entities + chinese_entities))
    
    def _determine_requires_memory(self, intent: QueryIntent, confidence: float, 
                                   history_length: int) -> bool:
        """判断是否需要记忆"""
        # 明确的记忆检索请求
        if intent == QueryIntent.MEMORY_RETRIEVAL:
            return True
        
        # 摘要请求
        if intent == QueryIntent.SUMMARY:
            return True
        
        # 需要上下文的查询
        if intent == QueryIntent.CONTEXTUAL and confidence > 0.3:
            return True
        
        # 跟进问题且对话较长
        if intent == QueryIntent.FOLLOW_UP and history_length > 5:
            return True
        
        # 低置信度的未知意图，默认需要检查记忆
        if intent == QueryIntent.UNKNOWN and confidence < 0.3:
            return True
        
        return False
    
    def _select_strategy(self, intent_analysis: IntentAnalysis) -> RetrievalStrategy:
        """选择检索策略"""
        strategy = self._config["default_strategy"]
        
        if intent_analysis.intent == QueryIntent.SUMMARY:
            # 摘要请求使用语义检索
            return RetrievalStrategy.SEMANTIC
        
        if len(intent_analysis.keywords) >= 3:
            # 关键词较多时使用混合检索
            return RetrievalStrategy.HYBRID
        
        if len(intent_analysis.entities) >= 2:
            # 有明确实体时使用关键词检索
            return RetrievalStrategy.KEYWORD
        
        # 默认混合检索
        return RetrievalStrategy.HYBRID
    
    def _execute_retrieval(self, query: str, intent_analysis: IntentAnalysis, 
                           strategy: RetrievalStrategy) -> List[Dict[str, Any]]:
        """执行检索"""
        results = []
        
        if strategy in (RetrievalStrategy.KEYWORD, RetrievalStrategy.HYBRID):
            # 关键词检索
            keyword_results = self._keyword_retrieval(query, intent_analysis.keywords)
            results.extend(keyword_results)
        
        if strategy in (RetrievalStrategy.SEMANTIC, RetrievalStrategy.HYBRID):
            # 语义检索
            semantic_results = self._semantic_retrieval(query)
            results.extend(semantic_results)
        
        if strategy == RetrievalStrategy.CHRONOLOGICAL:
            # 时间顺序检索
            chrono_results = self._chronological_retrieval()
            results.extend(chrono_results)
        
        # 去重
        seen_ids = set()
        unique_results = []
        for item in results:
            item_id = item.get("id", str(id(item)))
            if item_id not in seen_ids:
                seen_ids.add(item_id)
                unique_results.append(item)
        
        return unique_results
    
    def _keyword_retrieval(self, query: str, keywords: List[str]) -> List[Dict[str, Any]]:
        """关键词检索"""
        try:
            memory_query = MemoryQuery(
                query=" ".join(keywords),
                memory_types=[MemoryType.SESSION, MemoryType.SEMANTIC, MemoryType.LONG_TERM],
                limit=self._config["max_results"]
            )
            result = self._memory_router.query(memory_query)
            return [item.to_dict() for item in result.items]
        except Exception as e:
            logger.error(f"[IntelligentMemoryRetriever] 关键词检索失败: {e}")
            return []
    
    def _semantic_retrieval(self, query: str) -> List[Dict[str, Any]]:
        """语义向量检索"""
        try:
            # 使用智能记忆系统的语义检索能力
            results = self._auto_memory._intelligent_memory.search(
                query,
                limit=self._config["max_results"]
            )
            return results
        except Exception as e:
            logger.error(f"[IntelligentMemoryRetriever] 语义检索失败: {e}")
            return []
    
    def _chronological_retrieval(self) -> List[Dict[str, Any]]:
        """时间顺序检索（最近的记忆）"""
        try:
            memory_query = MemoryQuery(
                query="",
                memory_types=[MemoryType.SESSION],
                limit=self._config["max_results"]
            )
            result = self._memory_router.query(memory_query)
            # 按时间排序
            items = sorted(
                [item.to_dict() for item in result.items],
                key=lambda x: x.get("created_at", 0),
                reverse=True
            )
            return items
        except Exception as e:
            logger.error(f"[IntelligentMemoryRetriever] 时间检索失败: {e}")
            return []
    
    def _calculate_relevance(self, items: List[Dict[str, Any]], query: str) -> float:
        """计算相关性分数"""
        if not items:
            return 0.0
        
        # 简单的相关性计算：检查关键词匹配
        query_lower = query.lower()
        match_count = 0
        
        for item in items[:5]:  # 只检查前5个结果
            content = str(item.get("content", "")).lower()
            # 检查是否有重叠的词
            query_words = set(query_lower.split())
            content_words = set(content.split())
            overlap = query_words & content_words
            if overlap:
                match_count += 1
        
        return match_count / min(len(items), 5)
    
    def _rank_results(self, items: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """排序检索结果"""
        query_lower = query.lower()
        
        def score(item: Dict[str, Any]) -> float:
            """计算单个结果的分数"""
            score = 0.0
            content = str(item.get("content", "")).lower()
            
            # 关键词匹配分数
            query_words = query_lower.split()
            for word in query_words:
                if word in content:
                    score += 0.2
            
            # 时间衰减（最近的记忆权重更高）
            created_at = item.get("created_at", 0)
            if created_at > 0:
                age_days = (time.time() - created_at) / (24 * 60 * 60)
                if age_days < 1:
                    score += 0.3
                elif age_days < 7:
                    score += 0.2
                elif age_days < 30:
                    score += 0.1
            
            # 标签匹配
            tags = item.get("tags", [])
            for tag in tags:
                if str(tag).lower() in query_lower:
                    score += 0.1
            
            return score
        
        # 按分数排序
        return sorted(items, key=score, reverse=True)


# 便捷函数
def get_intelligent_retriever() -> IntelligentMemoryRetriever:
    """获取智能记忆检索器单例"""
    return IntelligentMemoryRetriever()


__all__ = [
    "QueryIntent",
    "RetrievalStrategy",
    "RetrievalResult",
    "IntentAnalysis",
    "IntelligentMemoryRetriever",
    "get_intelligent_retriever",
]