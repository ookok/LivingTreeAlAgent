"""
统一记忆融合引擎 (Memory Fusion Engine)
=====================================

深度整合所有记忆模块，实现：
1. 多源记忆融合 - 整合自动记忆、智能检索、多模态、共享记忆
2. 记忆推理 - 基于记忆进行推理和决策
3. 记忆演化 - 随时间学习和进化
4. 上下文感知 - 智能理解用户上下文

核心特性：
- 统一接口访问所有记忆系统
- 跨模块记忆关联
- 智能记忆路由
- 记忆质量评估

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

logger = __import__('logging').getLogger(__name__)


class MemorySource(Enum):
    """记忆来源"""
    AUTO_MEMORY = "auto_memory"           # 自动记忆管理器
    INTELLIGENT_RETRIEVER = "intelligent_retriever"  # 智能检索器
    SUMMARY_GENERATOR = "summary_generator"  # 摘要生成器
    MULTIMODAL = "multimodal"             # 多模态记忆
    SHARED = "shared"                     # 共享记忆
    INTELLIGENT = "intelligent"           # 智能记忆系统
    KNOWLEDGE_GRAPH = "knowledge_graph"   # 知识图谱


class FusionStrategy(Enum):
    """融合策略"""
    BEST_MATCH = "best_match"           # 选择最佳匹配
    ALL_RELEVANT = "all_relevant"       # 返回所有相关结果
    WEIGHTED = "weighted"               # 加权融合
    CONSENSUS = "consensus"             # 共识融合


@dataclass
class FusionResult:
    """融合结果"""
    sources: List[Dict[str, Any]]
    fused_content: str
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryInsight:
    """记忆洞察"""
    insight_id: str
    type: str  # pattern / trend / anomaly / prediction
    content: str
    confidence: float
    related_memories: List[str]


class MemoryFusionEngine:
    """
    统一记忆融合引擎
    
    核心功能：
    1. 统一访问所有记忆模块
    2. 跨模块记忆关联和融合
    3. 智能记忆路由
    4. 记忆质量评估和优化
    5. 基于记忆的推理
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
        
        # 延迟加载各记忆模块
        self._modules: Dict[MemorySource, Any] = {}
        self._module_loaders: Dict[MemorySource, Callable] = {
            MemorySource.AUTO_MEMORY: self._load_auto_memory,
            MemorySource.INTELLIGENT_RETRIEVER: self._load_intelligent_retriever,
            MemorySource.SUMMARY_GENERATOR: self._load_summary_generator,
            MemorySource.MULTIMODAL: self._load_multimodal_memory,
            MemorySource.SHARED: self._load_shared_memory,
            MemorySource.INTELLIGENT: self._load_intelligent_memory,
        }
        
        # 模块权重配置
        self._module_weights: Dict[MemorySource, float] = {
            MemorySource.AUTO_MEMORY: 0.2,
            MemorySource.INTELLIGENT_RETRIEVER: 0.25,
            MemorySource.SUMMARY_GENERATOR: 0.15,
            MemorySource.MULTIMODAL: 0.15,
            MemorySource.SHARED: 0.15,
            MemorySource.INTELLIGENT: 0.1,
        }
        
        # 融合策略
        self._fusion_strategy = FusionStrategy.WEIGHTED
        
        # LLM 调用函数
        self._llm_callable = None
        
        self._initialized = True
        logger.info("[MemoryFusionEngine] 统一记忆融合引擎初始化完成")
    
    def set_llm_callable(self, llm_callable: Callable[[str], str]):
        """设置 LLM 调用函数"""
        self._llm_callable = llm_callable
    
    def configure(self, **kwargs):
        """配置融合引擎"""
        if "weights" in kwargs:
            self._module_weights.update(kwargs["weights"])
        if "strategy" in kwargs:
            self._fusion_strategy = FusionStrategy(kwargs["strategy"])
        logger.info(f"[MemoryFusionEngine] 配置更新: {kwargs}")
    
    def _load_module(self, source: MemorySource) -> Any:
        """延迟加载记忆模块"""
        if source not in self._modules:
            loader = self._module_loaders.get(source)
            if loader:
                self._modules[source] = loader()
                logger.debug(f"[MemoryFusionEngine] 加载模块: {source.value}")
        return self._modules.get(source)
    
    def _load_auto_memory(self):
        from business.auto_memory_manager import get_auto_memory_manager
        return get_auto_memory_manager()
    
    def _load_intelligent_retriever(self):
        from business.intelligent_memory_retriever import get_intelligent_retriever
        return get_intelligent_retriever()
    
    def _load_summary_generator(self):
        from business.memory_summary_generator import get_summary_generator
        return get_summary_generator()
    
    def _load_multimodal_memory(self):
        from business.multimodal_memory import get_multimodal_memory
        return get_multimodal_memory()
    
    def _load_shared_memory(self):
        from business.shared_memory_system import get_shared_memory
        return get_shared_memory()
    
    def _load_intelligent_memory(self):
        from business.intelligent_memory import get_memory_system
        return get_memory_system()
    
    async def query(self, query: str, conversation_id: str = None, 
                   sources: List[MemorySource] = None) -> FusionResult:
        """
        统一查询接口
        
        Args:
            query: 查询文本
            conversation_id: 对话ID
            sources: 指定查询的记忆源（默认全部）
            
        Returns:
            FusionResult: 融合结果
        """
        start_time = time.time()
        
        # 确定查询源
        query_sources = sources or list(MemorySource)
        
        # 并行查询所有源
        results = await asyncio.gather(*[
            self._query_source(source, query, conversation_id)
            for source in query_sources
        ])
        
        # 过滤空结果
        valid_results = [r for r in results if r and r.get("items")]
        
        # 融合结果
        fused_result = self._fuse_results(valid_results)
        
        # 生成融合内容
        fused_content = self._generate_fused_content(query, valid_results)
        
        return FusionResult(
            sources=valid_results,
            fused_content=fused_content,
            confidence=fused_result["confidence"],
            metadata={
                "execution_time": time.time() - start_time,
                "sources_used": len(valid_results),
                "total_items": sum(len(r.get("items", [])) for r in valid_results),
            }
        )
    
    async def _query_source(self, source: MemorySource, query: str, 
                           conversation_id: str) -> Optional[Dict[str, Any]]:
        """查询单个记忆源"""
        try:
            module = self._load_module(source)
            if not module:
                return None
            
            if source == MemorySource.AUTO_MEMORY:
                result = module.retrieve_memory(query, conversation_id)
                return {"source": source.value, "items": result.get("items", []), "summary": result.get("summary")}
            
            elif source == MemorySource.INTELLIGENT_RETRIEVER:
                result = module.retrieve(query, conversation_id)
                return {"source": source.value, "items": [item.to_dict() for item in result.items]}
            
            elif source == MemorySource.MULTIMODAL:
                result = module.retrieve_text(query)
                return {"source": source.value, "items": [item.__dict__ for item in result]}
            
            elif source == MemorySource.SHARED:
                result = module.retrieve(query, "user")
                return {"source": source.value, "items": [item.__dict__ for item in result]}
            
            elif source == MemorySource.INTELLIGENT:
                result = module.search(query)
                return {"source": source.value, "items": result}
            
        except Exception as e:
            logger.error(f"[MemoryFusionEngine] 查询 {source.value} 失败: {e}")
            return None
        
        return None
    
    def _fuse_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """融合多个源的结果"""
        if not results:
            return {"confidence": 0.0, "items": []}
        
        # 计算加权置信度
        total_weight = sum(self._module_weights.get(MemorySource(r["source"]), 0.1) for r in results)
        confidence = 0.0
        
        for result in results:
            weight = self._module_weights.get(MemorySource(result["source"]), 0.1)
            item_count = len(result.get("items", []))
            confidence += weight * min(item_count / 10, 1.0)
        
        confidence = confidence / max(total_weight, 0.1)
        
        return {"confidence": confidence, "items": results}
    
    def _generate_fused_content(self, query: str, results: List[Dict[str, Any]]) -> str:
        """生成融合后的内容摘要"""
        if not results:
            return ""
        
        # 收集所有内容
        all_contents = []
        for result in results:
            for item in result.get("items", []):
                content = item.get("content", "") or item.get("summary", "")
                if content:
                    all_contents.append(f"【{result['source']}】{content[:200]}")
        
        if not all_contents:
            return ""
        
        # 使用 LLM 生成融合摘要
        if self._llm_callable:
            prompt = f"""请根据以下记忆检索结果，针对用户查询生成一个综合回答：

用户查询：{query}

记忆检索结果：
{chr(10).join(all_contents)}

请整合这些信息，生成一个连贯、全面的回答。"""
            
            try:
                return self._llm_callable(prompt)
            except Exception as e:
                logger.error(f"[MemoryFusionEngine] 生成融合内容失败: {e}")
        
        # 简单拼接（备用）
        return "\n\n".join(all_contents)
    
    def get_insights(self, conversation_id: str = None) -> List[MemoryInsight]:
        """
        获取记忆洞察
        
        从记忆中发现模式、趋势、异常和预测
        
        Args:
            conversation_id: 对话ID（可选）
            
        Returns:
            记忆洞察列表
        """
        insights = []
        
        # 分析对话模式（优雅处理模块加载失败）
        try:
            auto_memory = self._load_module(MemorySource.AUTO_MEMORY)
            if auto_memory:
                summary = auto_memory.get_conversation_summary(conversation_id) if conversation_id else None
                if summary:
                    insights.append(MemoryInsight(
                        insight_id=f"insight_{uuid4().hex[:8]}",
                        type="pattern",
                        content=f"对话主题：{summary.content[:100]}",
                        confidence=0.8,
                        related_memories=[conversation_id] if conversation_id else []
                    ))
        except Exception as e:
            logger.debug(f"[MemoryFusionEngine] 分析对话模式失败: {e}")
        
        # 分析共享知识趋势（优雅处理模块加载失败）
        try:
            shared_memory = self._load_module(MemorySource.SHARED)
            if shared_memory:
                stats = shared_memory.get_stats()
                if stats.get("scope_counts", {}).get("team", 0) > 0:
                    insights.append(MemoryInsight(
                        insight_id=f"insight_{uuid4().hex[:8]}",
                        type="trend",
                        content=f"团队共享知识正在增长",
                        confidence=0.7,
                        related_memories=[]
                    ))
        except Exception as e:
            logger.debug(f"[MemoryFusionEngine] 分析共享知识趋势失败: {e}")
        
        return insights
    
    def learn_from_interaction(self, interaction: Dict[str, Any]):
        """
        从交互中学习
        
        Args:
            interaction: 交互数据，包含 user_input, assistant_response, feedback 等
        """
        # 存储到自动记忆
        auto_memory = self._load_module(MemorySource.AUTO_MEMORY)
        if auto_memory:
            conversation_id = interaction.get("conversation_id", "temp")
            auto_memory.start_conversation(conversation_id)
            auto_memory.add_message(conversation_id, "user", interaction.get("user_input", ""))
            auto_memory.add_message(conversation_id, "assistant", interaction.get("assistant_response", ""))
            
            # 如果有反馈，也存储
            feedback = interaction.get("feedback")
            if feedback:
                auto_memory.add_message(conversation_id, "system", f"反馈: {feedback}")
            
            auto_memory.end_conversation(conversation_id)
        
        # 如果是有价值的知识，存储到共享记忆
        if interaction.get("save_to_shared"):
            shared_memory = self._load_module(MemorySource.SHARED)
            if shared_memory:
                content = interaction.get("assistant_response", "")
                shared_memory.store(content, "user", scope="team")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {
            "modules": {source.value: {"loaded": source in self._modules} for source in MemorySource},
            "weights": {k.value: v for k, v in self._module_weights.items()},
            "strategy": self._fusion_strategy.value,
        }
        
        # 获取各模块统计
        for source in MemorySource:
            module = self._modules.get(source)
            if module and hasattr(module, 'get_stats'):
                try:
                    stats["modules"][source.value]["stats"] = module.get_stats()
                except Exception as e:
                    pass
        
        return stats


# 便捷函数
def get_memory_fusion_engine() -> MemoryFusionEngine:
    """获取统一记忆融合引擎单例"""
    return MemoryFusionEngine()


__all__ = [
    "MemorySource",
    "FusionStrategy",
    "FusionResult",
    "MemoryInsight",
    "MemoryFusionEngine",
    "get_memory_fusion_engine",
]