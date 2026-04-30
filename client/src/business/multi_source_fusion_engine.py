"""多源结果融合引擎 - 知识图谱融合与逻辑一致性校验"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import asyncio

class ConflictType(Enum):
    FACTUAL = "factual"
    LOGICAL = "logical"
    TEMPORAL = "temporal"
    SEMANTIC = "semantic"

@dataclass
class Conflict:
    """冲突定义"""
    type: ConflictType
    sources: List[str]
    evidence: Dict[str, Any]
    severity: float
    description: str

@dataclass
class FusedResult:
    """融合结果"""
    content: str
    sources: List[str]
    confidence: float
    conflicts: List[Conflict] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

class GraphFusion:
    """图谱融合器"""
    
    async def merge(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """融合多源结果"""
        merged = {
            "texts": [],
            "facts": [],
            "entities": [],
            "relations": [],
            "sources": set()
        }
        
        for result in results:
            source = result.get("source", "unknown")
            merged["sources"].add(source)
            
            if "content" in result:
                merged["texts"].append({
                    "content": result["content"],
                    "source": source,
                    "relevance": result.get("relevance", 0.5)
                })
            
            if "title" in result:
                merged["facts"].append({
                    "title": result["title"],
                    "source": source
                })
            
            if "parameters" in result:
                merged["entities"].append({
                    "parameters": result["parameters"],
                    "source": source
                })
        
        merged["sources"] = list(merged["sources"])
        
        return merged

class ConsistencyChecker:
    """一致性检查器"""
    
    def check(self, fused: Dict[str, Any]) -> List[Conflict]:
        """检查逻辑一致性"""
        conflicts = []
        
        texts = fused.get("texts", [])
        if len(texts) >= 2:
            for i, t1 in enumerate(texts):
                for j, t2 in enumerate(texts):
                    if i < j:
                        conflict = self._compare_texts(t1, t2)
                        if conflict:
                            conflicts.append(conflict)
        
        return conflicts
    
    def _compare_texts(self, t1, t2) -> Optional[Conflict]:
        """比较两段文本"""
        content1 = t1.get("content", "").lower()
        content2 = t2.get("content", "").lower()
        
        if len(content1) < 10 or len(content2) < 10:
            return None
        
        if "不是" in content1 and "是" in content2:
            if any(word in content1 and word in content2 for word in ["重要", "正确", "关键"]):
                return Conflict(
                    type=ConflictType.FACTUAL,
                    sources=[t1["source"], t2["source"]],
                    evidence={"text1": content1, "text2": content2},
                    severity=0.8,
                    description="检测到事实冲突"
                )
        
        return None

class MultiSourceFusionEngine:
    """多源结果融合引擎"""
    
    def __init__(self):
        self._graph_fusion = GraphFusion()
        self._consistency_checker = ConsistencyChecker()
        self._initialized = False
    
    async def initialize(self):
        """初始化引擎"""
        self._initialized = True
    
    async def fuse(self, results: List[Dict[str, Any]]) -> FusedResult:
        """融合多源结果"""
        if not self._initialized:
            await self.initialize()
        
        fused = await self._graph_fusion.merge(results)
        
        conflicts = self._consistency_checker.check(fused)
        
        resolved = await self._resolve_conflicts(fused, conflicts)
        
        return FusedResult(
            content=self._generate_content(resolved),
            sources=fused.get("sources", []),
            confidence=self._calculate_confidence(resolved, conflicts),
            conflicts=conflicts,
            metadata=fused
        )
    
    async def _resolve_conflicts(self, fused: Dict[str, Any], conflicts: List[Conflict]) -> Dict[str, Any]:
        """解决冲突"""
        resolved = fused.copy()
        
        for conflict in conflicts:
            if conflict.severity > 0.7:
                resolved["conflict_resolved"] = True
                resolved["resolved_conflicts"] = len(conflicts)
        
        return resolved
    
    def _generate_content(self, fused: Dict[str, Any]) -> str:
        """生成融合内容"""
        texts = fused.get("texts", [])
        texts.sort(key=lambda x: x.get("relevance", 0.5), reverse=True)
        
        content_parts = []
        seen = set()
        
        for text in texts[:5]:
            content = text.get("content", "")
            if content and content[:50] not in seen:
                seen.add(content[:50])
                content_parts.append(content)
        
        return "\n\n".join(content_parts)
    
    def _calculate_confidence(self, fused: Dict[str, Any], conflicts: List[Conflict]) -> float:
        """计算置信度"""
        base_confidence = 0.7
        
        if conflicts:
            avg_severity = sum(c.severity for c in conflicts) / len(conflicts)
            base_confidence -= avg_severity * 0.3
        
        source_count = len(fused.get("sources", []))
        if source_count >= 3:
            base_confidence += 0.1
        if source_count >= 5:
            base_confidence += 0.1
        
        return min(0.99, max(0.5, base_confidence))
    
    def has_conflicts(self, results: List[Dict[str, Any]]) -> bool:
        """检查是否存在冲突"""
        fused = self._graph_fusion.merge(results)
        conflicts = self._consistency_checker.check(fused)
        return len(conflicts) > 0

_fusion_engine_instance = None

def get_multi_source_fusion_engine() -> MultiSourceFusionEngine:
    """获取多源结果融合引擎实例"""
    global _fusion_engine_instance
    if _fusion_engine_instance is None:
        _fusion_engine_instance = MultiSourceFusionEngine()
    return _fusion_engine_instance