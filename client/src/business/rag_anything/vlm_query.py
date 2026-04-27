"""
VLM 增强查询处理器

支持视觉语言模型增强的查询理解：
- 查询意图分析
- 多模态上下文构建
- VLM 增强查询
- 跨模态检索
"""

import time
import asyncio
from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum


# ============ 查询类型 ============

class QueryType(Enum):
    """查询类型"""
    TEXT_ONLY = "text_only"              # 仅文本
    IMAGE_QUERY = "image_query"          # 图像查询
    TABLE_QUERY = "table_query"          # 表格查询
    EQUATION_QUERY = "equation_query"    # 公式查询
    MULTIMODAL = "multimodal"           # 多模态查询


@dataclass
class QueryContext:
    """查询上下文"""
    query_text: str
    query_type: QueryType
    relevant_images: List[Any] = field(default_factory=list)
    relevant_tables: List[Any] = field(default_factory=list)
    relevant_equations: List[Any] = field(default_factory=list)
    text_chunks: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VLMQueryResult:
    """VLM 查询结果"""
    query: str
    enhanced_query: str
    query_type: QueryType
    confidence: float
    relevant_modalities: List[str]
    generated_insights: List[str] = field(default_factory=list)
    suggested_refinements: List[str] = field(default_factory=list)


# ============ 查询分析器 ============

class QueryAnalyzer:
    """
    查询分析器
    
    分析查询类型和意图
    """
    
    def __init__(self):
        self.image_keywords = [
            "图片", "图像", "照片", "图", "image", "picture", "photo", "figure",
            "显示", "展示", "看到", "图中", "image contains", "show", "display"
        ]
        self.table_keywords = [
            "表格", "表", "数据", "列", "行", "table", "data", "row", "column",
            "统计", "汇总", "compare", "statistics"
        ]
        self.equation_keywords = [
            "公式", "方程", "计算", "equation", "formula", "calculate", "compute",
            "数学", "mathematical", "等于", "solve"
        ]
    
    def analyze(self, query: str) -> QueryType:
        """
        分析查询类型
        
        Args:
            query: 查询文本
            
        Returns:
            QueryType: 查询类型
        """
        query_lower = query.lower()
        
        # 检查是否涉及图像
        has_image = any(kw in query_lower for kw in self.image_keywords)
        
        # 检查是否涉及表格
        has_table = any(kw in query_lower for kw in self.table_keywords)
        
        # 检查是否涉及公式
        has_equation = any(kw in query_lower for kw in self.equation_keywords)
        
        # 判断查询类型
        if has_image and (has_table or has_equation):
            return QueryType.MULTIMODAL
        elif has_image:
            return QueryType.IMAGE_QUERY
        elif has_table:
            return QueryType.TABLE_QUERY
        elif has_equation:
            return QueryType.EQUATION_QUERY
        else:
            return QueryType.TEXT_ONLY
    
    def extract_query_intent(self, query: str) -> Dict[str, Any]:
        """
        提取查询意图
        
        Args:
            query: 查询文本
            
        Returns:
            Dict: 查询意图
        """
        query_type = self.analyze(query)
        
        intent = {
            "type": query_type.value,
            "needs_vlm": query_type in [QueryType.IMAGE_QUERY, QueryType.MULTIMODAL],
            "needs_table": query_type in [QueryType.TABLE_QUERY, QueryType.MULTIMODAL],
            "needs_equation": query_type in [QueryType.EQUATION_QUERY, QueryType.MULTIMODAL],
        }
        
        return intent


# ============ 上下文构建器 ============

class ContextBuilder:
    """
    上下文构建器
    
    为查询构建多模态上下文
    """
    
    def __init__(self):
        self.max_text_length = 2000
        self.max_images = 5
        self.max_tables = 3
    
    def build_context(
        self,
        query: str,
        retrieved_content: Dict[str, Any],
    ) -> QueryContext:
        """
        构建查询上下文
        
        Args:
            query: 查询文本
            retrieved_content: 检索到的内容
            
        Returns:
            QueryContext: 查询上下文
        """
        query_type = QueryAnalyzer().analyze(query)
        
        # 收集相关图像
        images = self._collect_images(retrieved_content)
        
        # 收集相关表格
        tables = self._collect_tables(retrieved_content)
        
        # 收集相关公式
        equations = self._collect_equations(retrieved_content)
        
        # 收集相关文本
        text_chunks = self._collect_text(retrieved_content)
        
        return QueryContext(
            query_text=query,
            query_type=query_type,
            relevant_images=images[:self.max_images],
            relevant_tables=tables[:self.max_tables],
            relevant_equations=equations,
            text_chunks=text_chunks,
            metadata={
                "image_count": len(images),
                "table_count": len(tables),
                "equation_count": len(equations),
            }
        )
    
    def _collect_images(self, content: Dict[str, Any]) -> List[Any]:
        """收集图像"""
        images = content.get("images", [])
        if isinstance(images, list):
            return images
        return []
    
    def _collect_tables(self, content: Dict[str, Any]) -> List[Any]:
        """收集表格"""
        tables = content.get("tables", [])
        if isinstance(tables, list):
            return tables
        return []
    
    def _collect_equations(self, content: Dict[str, Any]) -> List[Any]:
        """收集公式"""
        equations = content.get("equations", [])
        if isinstance(equations, list):
            return equations
        return []
    
    def _collect_text(self, content: Dict[str, Any]) -> List[str]:
        """收集文本"""
        chunks = content.get("text_chunks", [])
        if isinstance(chunks, list):
            # 限制总长度
            result = []
            total_length = 0
            
            for chunk in chunks:
                if total_length + len(chunk) <= self.max_text_length:
                    result.append(chunk)
                    total_length += len(chunk)
                else:
                    break
            
            return result
        
        return []


# ============ VLM 查询处理器 ============

class VLMQueryProcessor:
    """
    VLM 查询处理器
    
    使用视觉语言模型增强查询理解
    """
    
    def __init__(
        self,
        vlm_client: Optional[Callable] = None,
        query_analyzer: Optional[QueryAnalyzer] = None,
    ):
        self.vlm_client = vlm_client
        self.query_analyzer = query_analyzer or QueryAnalyzer()
        self.context_builder = ContextBuilder()
    
    async def process(
        self,
        query: str,
        retrieved_content: Dict[str, Any],
    ) -> VLMQueryResult:
        """
        处理查询
        
        Args:
            query: 查询文本
            retrieved_content: 检索到的内容
            
        Returns:
            VLMQueryResult: VLM 查询结果
        """
        # 1. 分析查询
        query_type = self.query_analyzer.analyze(query)
        intent = self.query_analyzer.extract_query_intent(query)
        
        # 2. 构建上下文
        context = self.context_builder.build_context(query, retrieved_content)
        
        # 3. 检查是否需要 VLM
        enhanced_query = query
        insights = []
        refinements = []
        
        if intent["needs_vlm"] and self.vlm_client:
            # VLM 增强查询
            result = await self._vlm_enhance_query(query, context)
            enhanced_query = result.get("enhanced_query", query)
            insights = result.get("insights", [])
            refinements = result.get("refinements", [])
        
        # 4. 生成建议的细化
        if context.relevant_tables:
            refinements.append("考虑结合表格数据进行更精确的分析")
        if context.relevant_equations:
            refinements.append("可以使用数学模型进行验证")
        
        return VLMQueryResult(
            query=query,
            enhanced_query=enhanced_query,
            query_type=query_type,
            confidence=self._calculate_confidence(query_type, context),
            relevant_modalities=self._get_relevant_modalities(query_type, context),
            generated_insights=insights,
            suggested_refinements=refinements,
        )
    
    async def _vlm_enhance_query(
        self,
        query: str,
        context: QueryContext,
    ) -> Dict[str, Any]:
        """
        VLM 增强查询
        
        Args:
            query: 原始查询
            context: 查询上下文
            
        Returns:
            Dict: 增强结果
        """
        if not self.vlm_client:
            return {"enhanced_query": query, "insights": [], "refinements": []}
        
        try:
            # 构建 VLM 输入
            vlm_input = self._build_vlm_input(query, context)
            
            # 调用 VLM
            if asyncio.iscoroutinefunction(self.vlm_client.analyze):
                vlm_result = await self.vlm_client.analyze(vlm_input)
            else:
                vlm_result = self.vlm_client.analyze(vlm_input)
            
            # 解析 VLM 结果
            enhanced_query = vlm_result.get("enhanced_query", query)
            insights = vlm_result.get("insights", [])
            refinements = vlm_result.get("refinements", [])
            
            return {
                "enhanced_query": enhanced_query,
                "insights": insights,
                "refinements": refinements,
            }
            
        except Exception as e:
            # VLM 调用失败，返回原始查询
            return {
                "enhanced_query": query,
                "insights": [],
                "refinements": [f"VLM 分析失败: {str(e)}"],
            }
    
    def _build_vlm_input(
        self,
        query: str,
        context: QueryContext,
    ) -> Dict[str, Any]:
        """构建 VLM 输入"""
        input_data = {
            "query": query,
            "images": [],
            "tables": [],
            "equations": [],
        }
        
        # 添加图像
        for img in context.relevant_images:
            if hasattr(img, "image_data"):
                input_data["images"].append(img.image_data)
            elif isinstance(img, dict):
                input_data["images"].append(img.get("data", ""))
        
        # 添加表格
        for table in context.relevant_tables:
            if isinstance(table, dict):
                input_data["tables"].append(table.get("summary", str(table)))
            else:
                input_data["tables"].append(str(table))
        
        # 添加公式
        for eq in context.relevant_equations:
            if isinstance(eq, dict):
                input_data["equations"].append(eq.get("latex", str(eq)))
            elif hasattr(eq, "latex"):
                input_data["equations"].append(eq.latex)
        
        return input_data
    
    def _calculate_confidence(self, query_type: QueryType, context: QueryContext) -> float:
        """计算置信度"""
        base_confidence = 0.8
        
        # 根据上下文调整
        if query_type == QueryType.IMAGE_QUERY:
            if context.relevant_images:
                base_confidence += 0.1
            else:
                base_confidence -= 0.2
        
        elif query_type == QueryType.TABLE_QUERY:
            if context.relevant_tables:
                base_confidence += 0.1
            else:
                base_confidence -= 0.2
        
        elif query_type == QueryType.MULTIMODAL:
            modalities_count = (
                len(context.relevant_images) +
                len(context.relevant_tables) +
                len(context.relevant_equations)
            )
            if modalities_count >= 2:
                base_confidence += 0.1
            else:
                base_confidence -= 0.2
        
        return min(1.0, max(0.0, base_confidence))
    
    def _get_relevant_modalities(
        self,
        query_type: QueryType,
        context: QueryContext,
    ) -> List[str]:
        """获取相关模态"""
        modalities = ["text"]
        
        if context.relevant_images:
            modalities.append("image")
        if context.relevant_tables:
            modalities.append("table")
        if context.relevant_equations:
            modalities.append("equation")
        
        return modalities


# ============ 多模态 RAG 流水线 ============

class MultimodalRAGPipeline:
    """
    多模态 RAG 流水线
    
    端到端的多模态检索和生成
    """
    
    def __init__(
        self,
        knowledge_graph: Any,
        vector_store: Any,
        vlm_processor: Optional[VLMQueryProcessor] = None,
    ):
        self.knowledge_graph = knowledge_graph
        self.vector_store = vector_store
        self.vlm_processor = vlm_processor or VLMQueryProcessor()
        self.query_analyzer = QueryAnalyzer()
    
    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
    ) -> Dict[str, Any]:
        """
        检索
        
        Args:
            query: 查询文本
            top_k: 返回数量
            
        Returns:
            Dict: 检索结果
        """
        # 1. 分析查询
        query_type = self.query_analyzer.analyze(query)
        
        # 2. 文本检索
        text_results = await self._retrieve_text(query, top_k)
        
        # 3. 根据查询类型检索其他模态
        image_results = []
        table_results = []
        equation_results = []
        
        if query_type in [QueryType.IMAGE_QUERY, QueryType.MULTIMODAL]:
            image_results = await self._retrieve_images(query, top_k)
        
        if query_type in [QueryType.TABLE_QUERY, QueryType.MULTIMODAL]:
            table_results = await self._retrieve_tables(query, top_k)
        
        if query_type in [QueryType.EQUATION_QUERY, QueryType.MULTIMODAL]:
            equation_results = await self._retrieve_equations(query, top_k)
        
        # 4. 构建检索结果
        retrieved_content = {
            "text_chunks": text_results,
            "images": image_results,
            "tables": table_results,
            "equations": equation_results,
        }
        
        # 5. VLM 增强处理
        vlm_result = await self.vlm_processor.process(query, retrieved_content)
        
        return {
            "query": query,
            "enhanced_query": vlm_result.enhanced_query,
            "query_type": query_type.value,
            "confidence": vlm_result.confidence,
            "relevant_modalities": vlm_result.relevant_modalities,
            "insights": vlm_result.generated_insights,
            "refinements": vlm_result.suggested_refinements,
            "content": retrieved_content,
        }
    
    async def _retrieve_text(self, query: str, top_k: int) -> List[str]:
        """检索文本"""
        try:
            results = await self.vector_store.search(query, top_k=top_k)
            return [r["text"] for r in results if "text" in r]
        except Exception:
            return []
    
    async def _retrieve_images(self, query: str, top_k: int) -> List[Any]:
        """检索图像"""
        # 从知识图谱检索图像
        try:
            entities = self.knowledge_graph.search_entities(
                query,
                entity_type=None,  # 需要根据实际定义
                limit=top_k,
            )
            return [e for e in entities if e.entity_type.value == "image"]
        except Exception:
            return []
    
    async def _retrieve_tables(self, query: str, top_k: int) -> List[Any]:
        """检索表格"""
        try:
            entities = self.knowledge_graph.search_entities(
                query,
                entity_type=None,
                limit=top_k,
            )
            return [e for e in entities if e.entity_type.value == "table"]
        except Exception:
            return []
    
    async def _retrieve_equations(self, query: str, top_k: int) -> List[Any]:
        """检索公式"""
        try:
            entities = self.knowledge_graph.search_entities(
                query,
                entity_type=None,
                limit=top_k,
            )
            return [e for e in entities if e.entity_type.value == "equation"]
        except Exception:
            return []


# ============ 导出 ============

__all__ = [
    "QueryType",
    "QueryContext",
    "VLMQueryResult",
    "QueryAnalyzer",
    "ContextBuilder",
    "VLMQueryProcessor",
    "MultimodalRAGPipeline",
]
