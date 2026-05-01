"""
RAGFlow 与 Doc-V* 深度融合模块
================================

将 RAGFlow 的企业级文档理解能力与 Doc-V* 的粗到细视觉推理相结合，
实现更强大的多页面文档理解系统。

核心功能：
1. 文档解析融合（视觉 + 语义）
2. 多模态证据聚合
3. 层次化检索
4. 智能问答增强

作者: LivingTreeAI Team
日期: 2026-04-30
版本: 1.0.0
"""

import asyncio
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger

# 导入 Doc-V* 模块
from .evidence_memory import (
    EvidenceMemory,
    Evidence,
    EvidenceType,
    get_evidence_memory
)
from .document_navigator import (
    DocumentNavigator,
    NavigationMode,
    get_document_navigator
)
from .visual_document_parser import (
    VisualDocumentParser,
    DocumentElement,
    DocumentElementType,
    get_visual_document_parser
)


class FusionMode(Enum):
    """融合模式"""
    VISUAL_ONLY = "visual_only"
    SEMANTIC_ONLY = "semantic_only"
    HYBRID = "hybrid"
    HIERARCHICAL = "hierarchical"


class RetrievalLevel(Enum):
    """检索层次"""
    OVERVIEW = "overview"      # 概览级别
    SECTION = "section"        # 章节级别
    PARAGRAPH = "paragraph"    # 段落级别
    SENTENCE = "sentence"      # 句子级别
    ELEMENT = "element"        # 元素级别


@dataclass
class FusionResult:
    """融合结果"""
    success: bool
    document_info: Optional[Dict[str, Any]] = None
    evidences: Optional[List[Dict[str, Any]]] = None
    retrieval_results: Optional[List[Dict[str, Any]]] = None
    answer: Optional[str] = None
    confidence: float = 0.0
    reasoning_steps: Optional[List[Dict]] = None


class RAGFlowDocVFusion:
    """
    RAGFlow 与 Doc-V* 融合器
    
    将 RAGFlow 的深度文档理解与 Doc-V* 的主动推理相结合：
    1. 视觉解析 + 语义理解
    2. 多层次证据聚合
    3. 自适应检索策略
    """
    
    def __init__(self):
        """初始化融合器"""
        self.evidence_memory = get_evidence_memory()
        self.document_navigator = get_document_navigator()
        self.visual_parser = get_visual_document_parser()
        
        # 融合配置
        self.fusion_mode = FusionMode.HYBRID
        self.default_retrieval_level = RetrievalLevel.PARAGRAPH
        
        logger.info("[RAGFlowDocVFusion] 初始化完成")
    
    async def process_document(
        self,
        file_path: str,
        query: Optional[str] = None,
        fusion_mode: Optional[FusionMode] = None,
        retrieval_level: Optional[RetrievalLevel] = None
    ) -> FusionResult:
        """
        处理文档，融合 RAGFlow 与 Doc-V* 能力
        
        Args:
            file_path: 文档路径
            query: 用户查询
            fusion_mode: 融合模式
            retrieval_level: 检索级别
            
        Returns:
            FusionResult
        """
        mode = fusion_mode or self.fusion_mode
        level = retrieval_level or self.default_retrieval_level
        
        logger.info(f"[RAGFlowDocVFusion] 开始处理文档: {file_path}, 模式: {mode.value}")
        
        result = FusionResult(success=False)
        
        try:
            # 步骤 1: 文档解析
            logger.info("Step 1: 视觉文档解析...")
            document_info = await self.visual_parser.parse_document(file_path)
            
            # 处理文件类型（可能是字符串或枚举）
            file_type = document_info.file_type
            if hasattr(file_type, 'value'):
                file_type = file_type.value
            
            result.document_info = {
                "filename": document_info.filename,
                "total_pages": document_info.total_pages,
                "title": document_info.title,
                "file_type": file_type
            }
            
            # 步骤 2: 加载到导航器
            logger.info("Step 2: 加载文档到导航器...")
            self.document_navigator.load_document(file_path, document_info.file_type)
            
            # 步骤 3: 根据融合模式执行不同策略
            if mode == FusionMode.VISUAL_ONLY:
                evidences = await self._visual_only_processing(document_info, level)
            elif mode == FusionMode.SEMANTIC_ONLY:
                evidences = await self._semantic_only_processing(document_info, query, level)
            elif mode == FusionMode.HYBRID:
                evidences = await self._hybrid_processing(document_info, query, level)
            else:  # HIERARCHICAL
                evidences = await self._hierarchical_processing(document_info, query)
            
            result.evidences = evidences
            
            # 步骤 4: 构建推理链
            logger.info("Step 4: 构建推理链...")
            reasoning_result = self.evidence_memory.aggregate_reasoning(query)
            result.reasoning_steps = reasoning_result["reasoning_chain"]
            result.confidence = reasoning_result.get("avg_confidence", 0.5)
            
            # 步骤 5: 生成答案
            if query:
                result.answer = self._generate_answer(query, evidences, reasoning_result)
            
            result.success = True
            logger.info("[RAGFlowDocVFusion] 文档处理完成")
            
        except Exception as e:
            logger.error(f"[RAGFlowDocVFusion] 处理文档失败: {e}")
            result.success = False
        
        return result
    
    async def _visual_only_processing(self, document_info, level):
        """纯视觉处理"""
        evidences = []
        
        # 提取关键视觉元素
        for page_num in range(1, min(document_info.total_pages, 10) + 1):
            elements = self.visual_parser.extract_visual_elements(page_num)
            
            for element in elements:
                if self._should_include_element(element, level):
                    evidence = {
                        "type": "visual",
                        "page": page_num,
                        "element_type": element.type.value,
                        "content": element.content,
                        "confidence": element.confidence,
                        "region": element.bbox
                    }
                    evidences.append(evidence)
                    
                    # 添加到证据记忆
                    self.evidence_memory.add_evidence(
                        content=f"视觉元素: {element.type.value} - {element.content}",
                        source=f"visual_{page_num}",
                        content_type=EvidenceType.VISUAL,
                        page_number=page_num,
                        region=element.bbox,
                        confidence=element.confidence,
                        relevance=0.7
                    )
        
        return evidences
    
    async def _semantic_only_processing(self, document_info, query, level):
        """纯语义处理"""
        evidences = []
        
        # 使用语义导航
        if query:
            nav_result = await self.document_navigator.semantic_navigate(query)
            if nav_result.success and nav_result.content:
                evidence = {
                    "type": "semantic",
                    "page": nav_result.page_number,
                    "content": nav_result.content,
                    "confidence": nav_result.confidence,
                    "relevance": 0.9
                }
                evidences.append(evidence)
                
                self.evidence_memory.add_evidence(
                    content=nav_result.content,
                    source=f"semantic_{nav_result.page_number}",
                    content_type=EvidenceType.SEMANTIC,
                    page_number=nav_result.page_number,
                    confidence=nav_result.confidence,
                    relevance=0.9,
                    query=query
                )
        
        return evidences
    
    async def _hybrid_processing(self, document_info, query, level):
        """混合处理（视觉 + 语义）"""
        # 先进行视觉处理
        visual_evidences = await self._visual_only_processing(document_info, level)
        
        # 再进行语义处理
        semantic_evidences = await self._semantic_only_processing(document_info, query, level)
        
        # 合并并去重
        all_evidences = visual_evidences + semantic_evidences
        
        # 按相关性排序
        all_evidences.sort(key=lambda e: e.get('relevance', 0.5), reverse=True)
        
        return all_evidences[:20]  # 最多返回20个证据
    
    async def _hierarchical_processing(self, document_info, query):
        """层次化处理"""
        evidences = []
        
        # 层次 1: 概览扫描
        logger.info("层次 1: 概览扫描")
        await self.document_navigator.overview_scan(max_pages=5)
        
        # 层次 2: 章节级别检索
        logger.info("层次 2: 章节级别检索")
        sections = self._extract_sections(document_info)
        for section in sections[:5]:
            evidence = {
                "type": "section",
                "level": "chapter",
                "content": section,
                "confidence": 0.8
            }
            evidences.append(evidence)
        
        # 层次 3: 段落级别检索
        logger.info("层次 3: 段落级别检索")
        if query:
            nav_result = await self.document_navigator.semantic_navigate(query)
            if nav_result.success:
                paragraphs = self._extract_paragraphs(nav_result.content)
                for para in paragraphs[:3]:
                    evidence = {
                        "type": "paragraph",
                        "level": "detail",
                        "content": para,
                        "page": nav_result.page_number,
                        "confidence": nav_result.confidence
                    }
                    evidences.append(evidence)
        
        return evidences
    
    def _should_include_element(self, element, level):
        """判断是否包含元素"""
        # 安全获取元素类型
        element_type = element.type if hasattr(element, 'type') else element
        
        # 定义元素优先级（使用getattr避免KeyError）
        element_priority = {}
        for name in ['TITLE', 'HEADING', 'PARAGRAPH', 'TABLE', 'LIST', 'IMAGE', 'TEXT']:
            attr = getattr(DocumentElementType, name, None)
            if attr:
                priority_map = {
                    'TITLE': 5, 'HEADING': 4, 'PARAGRAPH': 3,
                    'TABLE': 4, 'FIGURE': 3, 'LIST': 2, 'IMAGE': 3, 'TEXT': 2
                }
                element_priority[attr] = priority_map.get(name, 2)
        
        level_threshold = {
            RetrievalLevel.OVERVIEW: 4,
            RetrievalLevel.SECTION: 3,
            RetrievalLevel.PARAGRAPH: 3,
            RetrievalLevel.SENTENCE: 2,
            RetrievalLevel.ELEMENT: 1
        }
        
        priority = element_priority.get(element.type, 1)
        threshold = level_threshold.get(level, 3)
        
        return priority >= threshold
    
    def _extract_sections(self, document_info):
        """提取章节"""
        # 模拟章节提取
        return [
            "摘要",
            "引言",
            "相关工作",
            "方法",
            "实验结果",
            "结论"
        ]
    
    def _extract_paragraphs(self, content):
        """提取段落"""
        paragraphs = content.split('\n\n')
        return [p.strip() for p in paragraphs if p.strip() and len(p.strip()) > 50][:3]
    
    def _generate_answer(self, query, evidences, reasoning_result):
        """生成答案"""
        if not evidences:
            return "没有找到相关信息。"
        
        evidence_texts = [e['content'][:100] for e in evidences[:3]]
        evidence_summary = "; ".join(evidence_texts)
        
        return f"基于文档分析，关于 '{query}' 的回答：\n\n" \
               f"证据来源：\n{evidence_summary}\n\n" \
               f"推理置信度：{reasoning_result.get('avg_confidence', 0.5):.2f}"
    
    def query(self, query: str) -> Dict[str, Any]:
        """
        使用融合能力进行查询
        
        Args:
            query: 用户查询
            
        Returns:
            查询结果
        """
        # 获取证据记忆中的相关证据
        top_evidences = self.evidence_memory.get_top_evidences(top_k=10, query=query)
        
        # 构建查询结果
        result = {
            "query": query,
            "evidences": [e.to_dict() for e in top_evidences],
            "confidence": sum(e.confidence for e in top_evidences) / len(top_evidences) if top_evidences else 0.0,
            "count": len(top_evidences)
        }
        
        return result


# 单例模式
_fusion_instance = None

def get_ragflow_docv_fusion() -> RAGFlowDocVFusion:
    """获取全局 RAGFlow-DocV* 融合实例"""
    global _fusion_instance
    if _fusion_instance is None:
        _fusion_instance = RAGFlowDocVFusion()
    return _fusion_instance


# 便捷函数
async def fusion_process_document(
    file_path: str,
    query: Optional[str] = None,
    mode: str = "hybrid"
) -> FusionResult:
    """
    使用融合能力处理文档（便捷函数）
    
    Args:
        file_path: 文档路径
        query: 用户查询
        mode: 融合模式 (visual_only/semantic_only/hybrid/hierarchical)
    
    Returns:
        FusionResult
    """
    fusion = get_ragflow_docv_fusion()
    
    mode_map = {
        "visual_only": FusionMode.VISUAL_ONLY,
        "semantic_only": FusionMode.SEMANTIC_ONLY,
        "hybrid": FusionMode.HYBRID,
        "hierarchical": FusionMode.HIERARCHICAL
    }
    
    return await fusion.process_document(
        file_path,
        query,
        fusion_mode=mode_map.get(mode, FusionMode.HYBRID)
    )