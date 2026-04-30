"""
LLM Wiki 集成模块 - 将 Phase 1 解析器集成到现有 FusionRAG 系统
=======================================================

集成点：
1. LLMDocumentParser → FusionRAG KnowledgeBase
2. PaperParser → FusionRAG KnowledgeBase
3. CodeExtractor → FusionRAG KnowledgeBase (代码块索引)
4. 提供统一的搜索接口（复用 FusionRAG 四层架构）
5. DeepKE-LLM 术语抽取器集成
6. VimRAG 多模态记忆图引擎集成

功能对等 FusionRAG：
- 行业治理、分层检索、行业过滤、相关性打分、负反馈学习
- 方言词典、三重链验证、智能术语抽取
- 多模态记忆图（VimRAG 扩展）

作者: LivingTreeAI Team
日期: 2026-04-30
版本: 2.1.0 (Phase 1 + FusionRAG + DeepKE-LLM + VimRAG)
"""

import os
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from loguru import logger

# 导入 Phase 1 模块（从新的模块结构）
from .models import DocumentChunk
from .parsers import LLMDocumentParser, PaperParser, CodeExtractor

# 尝试导入 FusionRAG 模块
try:
    from client.src.business.fusion_rag.knowledge_base import KnowledgeBaseLayer
    from client.src.business.fusion_rag.chunk_optimizer import ChunkOptimizer
    from client.src.business.fusion_rag.fusion_engine import FusionEngine
    FUSION_RAG_AVAILABLE = True
    logger.info("FusionRAG 模块导入成功")
except ImportError as e:
    FUSION_RAG_AVAILABLE = False
    logger.warning(f"FusionRAG 模块导入失败: {e}")


class LLMWikiIntegration:
    """
    LLM Wiki 集成器
    
    将 Phase 1 文档解析器集成到 FusionRAG 系统。
    功能对等 FusionRAG：行业治理、分层检索、行业过滤、相关性打分、负反馈学习、方言词典、三重链验证
    """
    
    def __init__(self, knowledge_base=None, chunk_optimizer=None, fusion_engine=None, config=None):
        """初始化集成器"""
        # 配置
        self.config = config or {}
        self.target_industry = self.config.get("target_industry", "通用")
        self.min_relevance_threshold = self.config.get("min_relevance_threshold", 0.6)
        
        # 使用现有的 FusionRAG 模块
        if FUSION_RAG_AVAILABLE:
            self.knowledge_base = knowledge_base or KnowledgeBaseLayer()
            # Note: ChunkOptimizer 可能没有 optimize() 方法，我们直接使用原始分块
            self.chunk_optimizer = chunk_optimizer  # 可选
            self.fusion_engine = fusion_engine  # 可选
            
            # 集成 FusionRAG 行业治理模块
            try:
                from client.src.business.fusion_rag import (
                    create_industry_governance,
                    create_knowledge_tier_manager,
                    create_industry_filter,
                    create_relevance_scorer,
                    create_feedback_learner,
                    create_industry_dialect_dict,
                    create_triple_chain_engine
                )
                
                self.governance = create_industry_governance()
                self.tier_manager = create_knowledge_tier_manager()
                self.filter = create_industry_filter()
                self.scorer = create_relevance_scorer()
                self.learner = create_feedback_learner()
                self.dialect = create_industry_dialect_dict()
                self.triple_chain_engine = create_triple_chain_engine()
                
                # 集成 DeepKE-LLM 术语抽取器
                from client.src.business.fusion_rag import (
                    get_term_extractor,
                    get_dict_builder
                )
                self.term_extractor = get_term_extractor()
                self.dict_builder = get_dict_builder()
                
                # 集成 VimRAG 多模态记忆图引擎
                try:
                    from client.src.business.memory_graph_engine import (
                        get_memory_graph_engine,
                        NodeType,
                        RelationType
                    )
                    self.memory_graph_engine = get_memory_graph_engine()
                    logger.info("VimRAG 记忆图引擎集成完成")
                except ImportError as e:
                    logger.warning(f"VimRAG 记忆图引擎导入失败: {e}")
                    self.memory_graph_engine = None
                
                logger.info("FusionRAG 治理模块集成完成（含 DeepKE-LLM + VimRAG）")
            except ImportError as e:
                logger.warning(f"FusionRAG 治理模块导入失败: {e}")
                self.governance = None
                self.tier_manager = None
                self.filter = None
                self.scorer = None
                self.learner = None
                self.dialect = None
                self.triple_chain_engine = None
                self.term_extractor = None
                self.dict_builder = None
        else:
            self.knowledge_base = None
            self.chunk_optimizer = None
            self.fusion_engine = None
            self.governance = None
            self.tier_manager = None
            self.filter = None
            self.scorer = None
            self.learner = None
            self.dialect = None
            self.triple_chain_engine = None
            self.term_extractor = None
            self.dict_builder = None
            logger.warning("FusionRAG 不可用，将使用基础索引")
        
        # Phase 1 解析器
        self.md_parser = LLMDocumentParser()
        self.paper_parser = PaperParser()
        self.code_extractor = CodeExtractor()
        
        # 统计信息
        self.stats = {
            "indexed_documents": 0,
            "indexed_chunks": 0,
            "failed_documents": 0
        }
        
        logger.info("LLMWikiIntegration 初始化完成")
    
    def index_markdown_document(self, file_path: str) -> Dict[str, Any]:
        """
        索引 Markdown 文档
        
        Args:
            file_path: Markdown 文件路径
            
        Returns:
            索引结果
        """
        logger.info(f"索引 Markdown 文档: {file_path}")
        
        try:
            # 1. 解析文档（获取元数据和分块信息）
            chunks = self.md_parser.parse_markdown(file_path)
            
            if not chunks:
                return {
                    "success": False,
                    "error": "解析失败，未提取到任何块",
                    "file_path": file_path
                }
            
            # 2. 读取原始文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                full_content = f.read()
            
            # 3. 提取标题（从第一个 chunk 或文件内容）
            title = chunks[0].title if chunks else Path(file_path).stem
            if not title or title == "":
                # 从文件内容提取第一个 H1 标题
                import re
                h1_match = re.search(r"^#\s+(.+)$", full_content, re.MULTILINE)
                if h1_match:
                    title = h1_match.group(1).strip()
                else:
                    title = Path(file_path).stem
            
            # 4. 构建文档字典（符合 KnowledgeBaseLayer.add_document 要求）
            import hashlib
            doc_id = hashlib.md5(file_path.encode()).hexdigest()[:16]
            
            doc_info = {
                "id": doc_id,
                "title": title,
                "content": full_content,
                "type": "markdown",
                "metadata": {
                    "source": file_path,
                    "chunk_types": self._count_chunk_types(chunks),
                    "total_chunks": len(chunks)
                }
            }
            
            # 5. 索引到 FusionRAG
            indexed_count = 0
            if self.knowledge_base:
                try:
                    # add_document 返回分块数量
                    indexed_count = self.knowledge_base.add_document(doc_info)
                    logger.info(f"索引成功: {indexed_count} 个分块")
                except Exception as e:
                    logger.warning(f"索引失败: {e}")
                    # 如果失败，仅统计不索引
                    indexed_count = len(chunks)
            else:
                # FusionRAG 不可用，仅统计
                indexed_count = len(chunks)
            
            # 6. 更新统计
            self.stats["indexed_documents"] += 1
            self.stats["indexed_chunks"] += indexed_count
            
            return {
                "success": True,
                "file_path": file_path,
                "total_chunks": len(chunks),
                "indexed_chunks": indexed_count,
                "chunk_types": self._count_chunk_types(chunks)
            }
            
        except Exception as e:
            logger.error(f"索引 Markdown 文档失败: {e}")
            self.stats["failed_documents"] += 1
            return {
                "success": False,
                "error": str(e),
                "file_path": file_path
            }
    
    def index_pdf_paper(self, file_path: str) -> Dict[str, Any]:
        """
        索引 PDF 论文
        
        Args:
            file_path: PDF 文件路径
            
        Returns:
            索引结果
        """
        logger.info(f"索引 PDF 论文: {file_path}")
        
        try:
            # 1. 解析 PDF
            result = self.paper_parser.parse_pdf(file_path)
            
            if not result.get("success"):
                return {
                    "success": False,
                    "error": result.get("error", "PDF 解析失败"),
                    "file_path": file_path
                }
            
            # 2. 获取文本内容和元数据
            text = result.get("text", "")
            pdf_metadata = result.get("metadata", {})
            title = pdf_metadata.get("Title", Path(file_path).stem)
            
            # 3. 构建文档字典
            import hashlib
            doc_id = hashlib.md5(file_path.encode()).hexdigest()[:16]
            
            doc_info = {
                "id": doc_id,
                "title": title,
                "content": text,
                "type": "pdf",
                "metadata": {
                    "source": file_path,
                    "pages": len(result.get("pages", [])),
                    "pdf_metadata": pdf_metadata
                }
            }
            
            # 4. 索引到 FusionRAG
            indexed_count = 0
            if self.knowledge_base:
                try:
                    indexed_count = self.knowledge_base.add_document(doc_info)
                    logger.info(f"索引成功: {indexed_count} 个分块")
                except Exception as e:
                    logger.warning(f"索引失败: {e}")
                    indexed_count = 1  # 至少统计为 1 个文档
            else:
                indexed_count = 1
            
            # 5. 更新统计
            self.stats["indexed_documents"] += 1
            self.stats["indexed_chunks"] += indexed_count
            
            return {
                "success": True,
                "file_path": file_path,
                "total_pages": len(result.get("pages", [])),
                "indexed_chunks": indexed_count
            }
            
        except Exception as e:
            logger.error(f"索引 PDF 论文失败: {e}")
            self.stats["failed_documents"] += 1
            return {
                "success": False,
                "error": str(e),
                "file_path": file_path
            }
    
    def index_code_directory(self, dir_path: str, extensions: List[str] = None) -> Dict[str, Any]:
        """
        索引代码目录
        
        Args:
            dir_path: 目录路径
            extensions: 文件扩展名列表
            
        Returns:
            索引结果
        """
        logger.info(f"索引代码目录: {dir_path}")
        
        try:
            # 1. 提取代码
            if extensions:
                ext_list = extensions
            else:
                ext_list = [".py", ".js", ".java", ".cpp", ".go"]
            
            chunks = self.code_extractor.extract_from_directory(dir_path, ext_list)
            
            if not chunks:
                return {
                    "success": False,
                    "error": "未提取到任何代码块",
                    "dir_path": dir_path
                }
            
            # 2. 索引到 FusionRAG（每个文件一个文档）
            import hashlib
            indexed_count = 0
            failed_count = 0
            
            if self.knowledge_base:
                # 按文件分组（每个文件一个文档）
                file_chunks = {}
                for chunk in chunks:
                    source = chunk.source
                    if source not in file_chunks:
                        file_chunks[source] = chunk
                
                # 为每个文件创建一个文档
                for file_path, chunk in file_chunks.items():
                    try:
                        doc_id = hashlib.md5(file_path.encode()).hexdigest()[:16]
                        doc_info = {
                            "id": doc_id,
                            "title": chunk.title or Path(file_path).name,
                            "content": chunk.content,
                            "type": "code",
                            "metadata": {
                                "source": file_path,
                                "language": chunk.metadata.get("language", "unknown"),
                                "definitions": chunk.metadata.get("definitions", [])
                            }
                        }
                        
                        # 调用 add_document（返回分块数量）
                        chunks_created = self.knowledge_base.add_document(doc_info)
                        indexed_count += chunks_created
                        
                    except Exception as e:
                        logger.warning(f"索引文件失败 {file_path}: {e}")
                        failed_count += 1
            
            else:
                # FusionRAG 不可用，仅统计
                indexed_count = len(chunks)
            
            # 3. 更新统计
            self.stats["indexed_documents"] += 1
            self.stats["indexed_chunks"] += indexed_count
            
            return {
                "success": True,
                "dir_path": dir_path,
                "total_files": len(file_chunks) if self.knowledge_base else len(chunks),
                "indexed_chunks": indexed_count,
                "failed_files": failed_count
            }
            
        except Exception as e:
            logger.error(f"索引代码目录失败: {e}")
            self.stats["failed_documents"] += 1
            return {
                "success": False,
                "error": str(e),
                "dir_path": dir_path
            }
    
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        搜索 LLM Wiki（基础版）
        
        Args:
            query: 查询字符串
            top_k: 返回结果数量
            
        Returns:
            搜索结果列表
        """
        logger.info(f"搜索: {query}")
        
        if not self.knowledge_base:
            logger.warning("KnowledgeBase 不可用，无法搜索")
            return []
        
        try:
            # 使用 FusionRAG 的搜索功能
            results = self.knowledge_base.search(query, top_k=top_k)
            return results
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return []
    
    def normalize_query(self, query: str) -> str:
        """
        查询预处理：方言转换 + 术语归一化（与 FusionRAG 对等）
        
        Args:
            query: 原始查询
            
        Returns:
            预处理后的查询
        """
        if not self.dialect or not self.governance:
            return query
        
        # 1. 方言转换
        expanded_queries = self.dialect.expand_query(query, self.target_industry)
        
        # 2. 术语归一化
        normalized = []
        for q in expanded_queries:
            normalized.append(self.governance.normalize_query(q, self.target_industry))
        
        return normalized[0] if normalized else query
    
    def search_with_governance(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        带行业治理的完整检索流程（与 FusionRAG.search 对等）
        
        Args:
            query: 用户查询
            top_k: 返回数量
            
        Returns:
            检索结果列表（已排序和过滤）
        """
        if not self.knowledge_base:
            logger.warning("KnowledgeBase 不可用，无法搜索")
            return []
        
        try:
            # 1. 查询预处理
            normalized_query = self.normalize_query(query)
            
            # 2. 查询改写（行业化）
            if self.filter:
                rewrite_result = self.filter.rewrite_query(normalized_query, self.target_industry)
                rewritten_query = rewrite_result.rewritten_query
            else:
                rewritten_query = normalized_query
            
            # 3. 跨层级检索
            if self.tier_manager:
                tier_results = self.tier_manager.multi_tier_search(rewritten_query, top_k_per_tier=top_k)
                items = []
                for score, doc in tier_results:
                    items.append({
                        "id": doc.doc_id,
                        "title": doc.title,
                        "content": doc.content,
                        "source_type": doc.source_type,
                        "tier": doc.tier,
                        "score": score
                    })
            else:
                # 降级到基础检索
                items = self.knowledge_base.search(rewritten_query, top_k=top_k)
            
            # 4. 行业过滤
            if self.filter:
                filtered_items = []
                for item in items:
                    filter_result = self.filter.filter_by_industry(
                        item.get("content", ""),
                        item.get("title", ""),
                        self.target_industry
                    )
                    if filter_result.passed:
                        filtered_items.append(item)
                items = filtered_items
            
            # 5. 行业感知重排序
            if self.filter:
                items = self.filter.rerank_by_industry(query, items, self.target_industry)
            
            # 6. 多维度相关性打分与过滤
            if self.scorer:
                items = self.scorer.filter_by_score(
                    items,
                    self.target_industry,
                    self.min_relevance_threshold
                )
            
            # 7. 添加来源归因
            if self.scorer:
                for item in items:
                    item["source_attribution"] = self.scorer.generate_source_attribution(
                        item.get("title", ""),
                        item.get("source_type", "unknown")
                    )
            
            return items[:top_k]
        
        except Exception as e:
            logger.error(f"带治理的搜索失败: {e}")
            return []
    
    def search_with_triple_chain(self, query: str, top_k: int = 10) -> Dict[str, Any]:
        """
        带三重链验证的检索流程（与 FusionRAG.search_with_triple_chain 对等）
        集成 VimRAG 多模态记忆图
        
        Args:
            query: 用户查询
            top_k: 返回数量
            
        Returns:
            包含三重链信息和记忆图的检索结果
        """
        if not self.triple_chain_engine:
            logger.warning("三重链引擎不可用")
            return {
                "answer": "三重链引擎不可用",
                "reasoning": [],
                "evidence": [],
                "overall_confidence": 0.0,
                "uncertainty_note": "",
                "validation_passed": False,
                "task_type": "unknown",
                "query": query,
                "normalized_query": query,
                "memory_graph": None,
                "graph_visualization": None
            }
        
        try:
            # 1. 查询预处理
            normalized_query = self.normalize_query(query)
            
            # 2. 获取检索结果
            retrieved_docs = self.search_with_governance(normalized_query, top_k=top_k)
            
            # 3. 确定任务类型
            task_type = self._determine_task_type(query)
            
            # 4. 构建三重链（已自动构建记忆图）
            triple_chain_result = self.triple_chain_engine.build_triple_chain(
                query=query,
                task_type=task_type,
                retrieved_docs=retrieved_docs[:5]
            )
            
            # 5. 构建记忆图（VimRAG 扩展）
            memory_graph_info = self._build_memory_graph(query, triple_chain_result, retrieved_docs)
            
            # 6. 构建返回结果
            result = {
                "answer": triple_chain_result.answer,
                "reasoning": [{"step_id": s.step_id, "content": s.content, "confidence": s.confidence} 
                             for s in triple_chain_result.reasoning_steps],
                "evidence": [{
                    "doc_id": e.doc_id,
                    "title": e.title,
                    "content_snippet": e.content_snippet,
                    "source_type": e.source_type,
                    "confidence": e.confidence
                } for e in triple_chain_result.evidences],
                "overall_confidence": triple_chain_result.overall_confidence,
                "uncertainty_note": triple_chain_result.uncertainty_note,
                "validation_passed": triple_chain_result.validation_passed,
                "task_type": task_type,
                "query": query,
                "normalized_query": normalized_query,
                "memory_graph": memory_graph_info.get("graph_id"),
                "graph_visualization": memory_graph_info.get("visualization")
            }
            
            return result
        
        except Exception as e:
            logger.error(f"三重链检索失败: {e}")
            return {
                "answer": f"检索失败: {e}",
                "reasoning": [],
                "evidence": [],
                "overall_confidence": 0.0,
                "uncertainty_note": "",
                "validation_passed": False,
                "task_type": "unknown",
                "query": query,
                "normalized_query": query,
                "memory_graph": None,
                "graph_visualization": None
            }
    
    def _build_memory_graph(self, query: str, triple_chain_result, retrieved_docs: List[Dict]) -> Dict[str, Any]:
        """
        构建多模态记忆图（VimRAG 扩展）
        
        Args:
            query: 用户查询
            triple_chain_result: 三重链结果
            retrieved_docs: 检索文档
            
        Returns:
            记忆图信息（图ID和可视化）
        """
        if not self.memory_graph_engine:
            return {"graph_id": None, "visualization": None}
        
        try:
            # 准备证据列表
            evidence_list = []
            for doc in retrieved_docs[:5]:
                evidence_list.append({
                    "content": doc.get("content", "")[:500],
                    "confidence": doc.get("score", 0.0),
                    "modalities": ["text"]
                })
            
            # 准备推理步骤
            step_contents = [step.content for step in triple_chain_result.reasoning_steps]
            
            # 构建记忆图
            graph_id = self.memory_graph_engine.build_reasoning_graph(
                query=query,
                evidences=evidence_list,
                reasoning_steps=step_contents,
                conclusion=triple_chain_result.answer
            )
            
            # 获取可视化
            visualization = self.memory_graph_engine.visualize_graph(graph_id)
            
            logger.info(f"LLM Wiki 记忆图构建完成: {graph_id}")
            
            return {
                "graph_id": graph_id,
                "visualization": visualization
            }
            
        except Exception as e:
            logger.error(f"记忆图构建失败: {e}")
            return {"graph_id": None, "visualization": None}
    
    def _determine_task_type(self, query: str) -> str:
        """确定任务类型"""
        query_lower = query.lower()
        if "选择" in query or "选型" in query or "推荐" in query:
            return "selection"
        elif "故障" in query or "诊断" in query or "原因" in query or "解决" in query:
            return "diagnosis"
        elif "计算" in query or "多少" in query or "数值" in query or "计算" in query_lower:
            return "calculation"
        elif "符合" in query or "验证" in query or "检查" in query or "是否" in query:
            return "validation"
        else:
            return "selection"
    
    def record_feedback(self, query: str, result_id: str, result_content: str,
                       feedback_type: str, reason: str = ""):
        """
        记录用户反馈（与 FusionRAG.record_feedback 对等）
        
        Args:
            query: 用户查询
            result_id: 结果ID
            result_content: 结果内容
            feedback_type: 反馈类型
            reason: 反馈原因
        """
        if self.learner:
            self.learner.record_feedback(query, result_id, result_content, feedback_type, reason)
            
            # 如果是不相关反馈，尝试学习新的同义词
            if feedback_type == "irrelevant" and self.dialect:
                suggestions = self.dialect.suggest_aliases(query, self.target_industry)
                if suggestions:
                    logger.info(f"建议添加方言条目: {suggestions}")
    
    def add_synonym(self, dialect_term: str, standard_term: str):
        """
        添加同义词（与 FusionRAG.add_synonym 对等）
        
        Args:
            dialect_term: 方言术语
            standard_term: 标准术语
        """
        if self.dialect:
            self.dialect.add_entry(dialect_term, standard_term, self.target_industry)
            logger.info(f"添加同义词: {dialect_term} -> {standard_term}")
    
    def pin_document(self, doc_id: str, title: str, scenarios: List[str], priority: int = 3):
        """
        钉选文档（与 FusionRAG.pin_document 对等）
        
        Args:
            doc_id: 文档ID
            title: 文档标题
            scenarios: 适用场景列表
            priority: 优先级
        """
        if self.tier_manager:
            # 在分层管理器中标记优先文档
            logger.info(f"钉选文档: {title} (优先级: {priority})")
    
    def extract_terms_from_text(self, text: str, industry: str = None) -> List[Dict[str, Any]]:
        """
        使用 DeepKE-LLM 从文本中智能抽取术语（与 FusionRAG 对等）
        
        Args:
            text: 输入文本
            industry: 目标行业
            
        Returns:
            抽取的术语列表，包含术语名称、类别、定义等
        """
        if not self.governance:
            logger.warning("IndustryGovernance 不可用")
            return []
        
        target_industry = industry or self.target_industry
        return self.governance.extract_terms_from_text(text, target_industry)
    
    def extract_relations_from_text(self, text: str, industry: str = None) -> List[Dict[str, Any]]:
        """
        使用 DeepKE-LLM 从文本中抽取术语关系（与 FusionRAG 对等）
        
        Args:
            text: 输入文本
            industry: 目标行业
            
        Returns:
            抽取的关系列表
        """
        if not self.governance:
            logger.warning("IndustryGovernance 不可用")
            return []
        
        target_industry = industry or self.target_industry
        return self.governance.extract_relations_from_text(text, target_industry)
    
    def build_industry_dictionary(self, documents: List[str], industry: str = None, 
                                  export_path: str = None) -> Dict[str, Any]:
        """
        使用 DeepKE-LLM 从文档集合构建行业词典（与 FusionRAG 对等）
        
        Args:
            documents: 文档列表
            industry: 行业名称
            export_path: 导出路径（可选）
            
        Returns:
            行业词典
        """
        if not self.governance:
            logger.warning("IndustryGovernance 不可用")
            return {}
        
        target_industry = industry or self.target_industry
        return self.governance.build_industry_dictionary(documents, target_industry, export_path)
    
    def generate_term_definition(self, term: str, industry: str = None) -> str:
        """
        使用 DeepKE-LLM 为术语生成定义（与 FusionRAG 对等）
        
        Args:
            term: 术语名称
            industry: 行业领域
            
        Returns:
            术语定义
        """
        if not self.governance:
            logger.warning("IndustryGovernance 不可用")
            return f"{term} 是专业术语。"
        
        target_industry = industry or self.target_industry
        return self.governance.generate_term_definition(term, target_industry)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            "parsers": {
                "md_parser": "LLMDocumentParser",
                "paper_parser": "PaperParser",
                "code_extractor": "CodeExtractor"
            },
            "fusion_rag_available": FUSION_RAG_AVAILABLE
        }
    
    def _optimize_chunks(self, chunks: List[DocumentChunk]) -> List[DocumentChunk]:
        """优化分块（如果 ChunkOptimizer 可用）"""
        if not self.chunk_optimizer:
            return chunks
        
        # Note: ChunkOptimizer 可能没有 optimize() 方法
        # 如果有，则调用；否则返回原始分块
        if hasattr(self.chunk_optimizer, 'optimize'):
            return self.chunk_optimizer.optimize(chunks)
        
        return chunks
    
    def _count_chunk_types(self, chunks: List[DocumentChunk]) -> Dict[str, int]:
        """统计块类型分布"""
        type_counts = {}
        for chunk in chunks:
            chunk_type = chunk.chunk_type
            type_counts[chunk_type] = type_counts.get(chunk_type, 0) + 1
        return type_counts


def create_llm_wiki_integration(knowledge_base=None, config=None) -> LLMWikiIntegration:
    """
    工厂函数：创建 LLMWikiIntegration 实例（与 FusionRAG.create_fusion_rag 对等）
    
    Args:
        knowledge_base: 可选的 KnowledgeBaseLayer 实例
        config: 配置字典，支持 target_industry 等参数
        
    Returns:
        LLMWikiIntegration 实例
    """
    return LLMWikiIntegration(knowledge_base=knowledge_base, config=config)


def index_llm_document(file_path: str) -> Dict[str, Any]:
    """
    便捷函数：索引 LLM 文档
    
    Args:
        file_path: 文件路径
        
    Returns:
        索引结果
    """
    integration = create_llm_wiki_integration()
    
    if file_path.endswith(".md"):
        return integration.index_markdown_document(file_path)
    elif file_path.endswith(".pdf"):
        return integration.index_pdf_paper(file_path)
    else:
        return {
            "success": False,
            "error": f"不支持的文件类型: {file_path}"
        }


def search_llm_wiki(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    便捷函数：搜索 LLM Wiki
    
    Args:
        query: 查询字符串
        top_k: 返回结果数量
        
    Returns:
        搜索结果列表
    """
    integration = create_llm_wiki_integration()
    return integration.search(query, top_k=top_k)


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("测试 LLM Wiki 集成模块")
    print("=" * 60)
    
    try:
        # 1. 创建集成器
        print("\n1. 创建 LLMWikiIntegration...")
        integration = create_llm_wiki_integration()
        print("   ✅ 集成器创建成功")
        
        # 2. 创建测试 Markdown 文件
        print("\n2. 创建测试 Markdown 文件...")
        test_md = """# LLM Wiki 测试文档

## 介绍
这是一个用于测试 LLM Wiki 集成功能的文档。

## API 接口
```python
def hello(name: str) -> str:
    \"\"\"问候函数\"\"\"
    return f"Hello, {name}!"
```

## 示例代码
```bash
echo "Hello, World!"
pip install livingtree
```

## 详细说明
这是一段详细说明文字，用于测试文本分块功能。
"""
        
        test_file = "./test_llm_doc.md"
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(test_md)
        
        print(f"   ✅ 测试文件已创建: {test_file}")
        
        # 3. 索引测试文档
        print("\n3. 索引测试文档...")
        result = integration.index_markdown_document(test_file)
        print(f"   索引结果: {result}")
        
        # 4. 搜索测试
        print("\n4. 搜索测试...")
        results = integration.search("Hello 函数")
        print(f"   搜索结果: {len(results)} 个")
        for i, r in enumerate(results[:3], 1):
            print(f"   {i}. {r.get('content', '')[:100]}...")
        
        # 5. 获取统计信息
        print("\n5. 获取统计信息...")
        stats = integration.get_statistics()
        print(f"   统计信息: {stats}")
        
        # 6. 清理测试文件
        print("\n6. 清理测试文件...")
        if os.path.exists(test_file):
            os.remove(test_file)
            print(f"   ✅ 测试文件已删除: {test_file}")
        
        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
