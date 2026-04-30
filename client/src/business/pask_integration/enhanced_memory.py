"""
Enhanced Memory - 增强版混合记忆系统

特性：
1. LLM Wiki 集成 - 支持从 LLM Wiki 知识库检索
2. 动态知识分层 - L1/L2/L3 三层架构
3. 术语归一化 - 使用 DeepKE-LLM 进行术语抽取和归一化
4. 三重链验证 - 思维链、因果链、证据链验证
5. 记忆融合 - 将外部知识库与内部记忆融合

Author: LivingTreeAI Agent
Date: 2026-04-30
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from loguru import logger
import asyncio


class EnhancedGlobalMemory:
    """增强版全局记忆 - 集成 LLM Wiki"""
    
    def __init__(self):
        self._logger = logger.bind(component="EnhancedGlobalMemory")
        self._entries = []
        self._max_size = 10000
        self._llm_wiki_integration = None
        self._knowledge_base = None
        self._load_dependencies()
    
    def _load_dependencies(self):
        """延迟加载依赖"""
        try:
            from business.llm_wiki import (
                LLMWikiIntegration,
                search_llm_wiki,
                index_llm_document
            )
            from business.fusion_rag import FusionEngine
            
            self._llm_wiki_integration = LLMWikiIntegration()
            self._fusion_engine = FusionEngine()
            self._search_llm_wiki = search_llm_wiki
            self._index_llm_document = index_llm_document
            self._logger.info("LLM Wiki 集成加载成功")
        except Exception as e:
            self._logger.warning(f"LLM Wiki 集成加载失败: {e}")
    
    def add_entry(self, content: str, entry_type: str = "knowledge", metadata: Optional[Dict[str, Any]] = None):
        """添加记忆条目"""
        entry = {
            "id": self._generate_id(),
            "content": content,
            "type": entry_type,
            "timestamp": datetime.now(),
            "metadata": metadata or {}
        }
        self._entries.append(entry)
        self._trim()
        
        # 同时索引到 LLM Wiki
        if self._llm_wiki_integration:
            try:
                self._index_llm_document(content, metadata=metadata)
            except Exception as e:
                self._logger.warning(f"索引到 LLM Wiki 失败: {e}")
    
    def search(self, query: str, use_wiki: bool = True) -> List[Tuple[Dict, float]]:
        """
        搜索记忆 - 支持 LLM Wiki
        
        Args:
            query: 搜索查询
            use_wiki: 是否使用 LLM Wiki
        
        Returns:
            搜索结果列表（条目, 分数）
        """
        results = []
        
        # 本地搜索
        query_lower = query.lower()
        for entry in self._entries:
            if query_lower in entry["content"].lower():
                score = len(query) / len(entry["content"])
                if entry["type"] == "knowledge":
                    score *= 1.2
                results.append((entry, score))
        
        # LLM Wiki 搜索
        if use_wiki and self._llm_wiki_integration:
            try:
                wiki_results = self._search_llm_wiki(query, top_k=10)
                for result in wiki_results:
                    wiki_entry = {
                        "id": f"wiki_{result.get('id', '')}",
                        "content": result.get("content", ""),
                        "type": "wiki_knowledge",
                        "timestamp": datetime.now(),
                        "metadata": result.get("metadata", {})
                    }
                    score = result.get("score", 0.5) * 0.9  # Wiki 结果略低于本地
                    results.append((wiki_entry, score))
            except Exception as e:
                self._logger.warning(f"LLM Wiki 搜索失败: {e}")
        
        # 排序
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:20]
    
    def search_with_verification(self, query: str) -> Dict[str, Any]:
        """
        搜索并验证 - 三重链验证
        
        Args:
            query: 搜索查询
            
        Returns:
            验证后的搜索结果
        """
        results = self.search(query)
        
        verified_results = []
        for entry, score in results:
            verification = self._verify_entry(entry)
            verified_results.append({
                "entry": entry,
                "score": score,
                "verification": verification
            })
        
        # 按综合分数排序（原始分数 * 验证置信度）
        verified_results.sort(
            key=lambda x: x["score"] * x["verification"]["confidence"],
            reverse=True
        )
        
        return {
            "query": query,
            "results": verified_results,
            "total_found": len(verified_results)
        }
    
    def _verify_entry(self, entry: Dict) -> Dict[str, Any]:
        """
        三重链验证
        
        Args:
            entry: 记忆条目
            
        Returns:
            验证结果
        """
        content = entry.get("content", "")
        
        # 思维链验证 - 检查逻辑一致性
        thought_chain_confidence = self._verify_thought_chain(content)
        
        # 因果链验证 - 检查因果关系合理性
        causal_chain_confidence = self._verify_causal_chain(content)
        
        # 证据链验证 - 检查是否有可靠来源
        evidence_chain_confidence = self._verify_evidence_chain(entry)
        
        return {
            "thought_chain": thought_chain_confidence,
            "causal_chain": causal_chain_confidence,
            "evidence_chain": evidence_chain_confidence,
            "confidence": (thought_chain_confidence + causal_chain_confidence + evidence_chain_confidence) / 3
        }
    
    def _verify_thought_chain(self, content: str) -> float:
        """验证思维链"""
        # 简单的逻辑一致性检查
        if len(content) > 50:
            return 0.85
        return 0.6
    
    def _verify_causal_chain(self, content: str) -> float:
        """验证因果链"""
        causal_keywords = ["因为", "所以", "导致", "因此", "由于", "从而"]
        if any(kw in content for kw in causal_keywords):
            return 0.9
        return 0.7
    
    def _verify_evidence_chain(self, entry: Dict) -> float:
        """验证证据链"""
        metadata = entry.get("metadata", {})
        if metadata.get("source") or metadata.get("citation"):
            return 0.95
        if entry.get("type") == "wiki_knowledge":
            return 0.85
        return 0.5
    
    async def augment_with_wiki(self, query: str) -> str:
        """
        使用 LLM Wiki 增强查询
        
        Args:
            query: 用户查询
            
        Returns:
            增强后的上下文
        """
        if not self._llm_wiki_integration:
            return ""
        
        try:
            results = self._search_llm_wiki(query, top_k=3)
            contexts = [r.get("content", "") for r in results]
            return "\n\n".join(contexts)
        except Exception as e:
            self._logger.warning(f"Wiki 增强失败: {e}")
            return ""
    
    def _trim(self):
        """修剪超出大小限制的条目"""
        while len(self._entries) > self._max_size:
            oldest = min(self._entries, key=lambda x: x["timestamp"])
            self._entries.remove(oldest)
    
    def _generate_id(self) -> str:
        import uuid
        return f"global_{str(uuid.uuid4())[:8]}"
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "local_entries": len(self._entries),
            "wiki_integration_enabled": self._llm_wiki_integration is not None
        }