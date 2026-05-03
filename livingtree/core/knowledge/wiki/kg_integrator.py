"""
LivingTree Wiki KG Integrator — 增强版知识图谱整合器
=====================================================

合并 Phase 3 (V3) 和 Phase 4 (V4) 功能为一个统一类：
- 文档块 → 知识图谱自动构建
- 实体链接（Entity Linking，去重合并）
- 跨文档引用检测
- 图谱推理（BFS 路径查找、子图提取、概念查询）
- EvoRAG 反馈驱动自进化
- 混合优先级检索
- 可插拔实体提取器（Regex + DeepKE-LLM）
- 统一缓存与性能统计

使用 livingtree 新架构：
- 图后端: livingtree.core.memory.graph_db.KnowledgeGraph
- EvoRAG组件: wiki/feedback_manager, wiki/kg_self_evolver, wiki/hybrid_retriever

Author: LivingTreeAI Team
Version: 5.0.0 (合并增强版)
"""

from __future__ import annotations

import hashlib
import re
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from loguru import logger

# 新架构图后端
from livingtree.core.memory.graph_db import (
    KnowledgeGraph,
    Entity,
    Relation,
    EntityType,
    RelationType,
)

# EvoRAG 组件（已迁移到 wiki 模块）
from .feedback_manager import FeedbackManager, FeedbackRecord
from .kg_self_evolver import KnowledgeGraphSelfEvolver
from .hybrid_retriever import HybridRetriever, RetrievalResult
from .models import DocumentChunk


# ============================================================================
# 配置数据类
# ============================================================================

@dataclass
class IntegratorConfig:
    """整合器配置 —— 统一 V3 和 V4 的所有参数"""

    # 基本
    domain: str = "llm_wiki"
    enable_cache: bool = True

    # EvoRAG
    enable_evorag: bool = True
    enable_feedback: bool = True
    enable_self_evolution: bool = True
    enable_hybrid_retrieval: bool = True

    # 反馈管理器
    feedback_db_path: str = "data/feedback_db.json"
    learning_rate: float = 0.5
    alpha: float = 0.5

    # 自进化器
    max_hops: int = 3
    min_path_score: float = 0.6
    evolution_interval: int = 5  # 每 N 次反馈触发一次进化

    # 混合检索
    top_n_entities: int = 10
    top_m_paths: int = 10

    # 实体提取
    min_term_length: int = 2
    max_term_length: int = 60

    # 批量处理
    batch_size: int = 50


@dataclass
class ChunkNodeMapping:
    """文档块 → 图节点的映射记录"""

    chunk_id: str
    node_id: str
    title: str
    entity_type: EntityType
    chunk: DocumentChunk
    parent_node_id: Optional[str] = None
    chunk_index: int = 0
    doc_source: str = ""


# ============================================================================
# 实体提取器接口（可插拔）
# ============================================================================

class EntityExtractor:
    """
    实体提取器接口 —— 支持可插拔策略

    内置实现：RegexEntityExtractor（基于正则表达式）
    可选实现：DeepKEExtractor（基于 LLM 的术语抽取）
    """

    def extract(self, text: str) -> List[str]:
        """从文本中提取实体/术语列表"""
        raise NotImplementedError


class RegexEntityExtractor(EntityExtractor):
    """
    基于正则表达式的实体提取器

    支持多种模式：
    - **粗体术语**
    - `代码术语`
    - 标题模式 (#、##)
    - "定义"模式
    - 引号术语
    - 专有名词（连续大写字母开头）
    - 括号注释术语
    """

    # 提取模式（按优先级排序）
    PATTERNS = [
        # Markdown 粗体: **term**
        (re.compile(r'\*\*(.+?)\*\*'), 1),
        # 行内代码: `term`
        (re.compile(r'`([^`]+?)`'), 1),
        # Markdown 标题: # Title
        (re.compile(r'^#{1,6}\s+(.+?)$', re.MULTILINE), 1),
        # "定义"模式: "术语" 或 「术语」
        (re.compile(r'[""]([^""]{1,30})[""]'), 1),
        (re.compile(r'「([^」]{1,30})」'), 1),
        # 括号注释: 术语（英文名）
        (re.compile(r'([A-Z][a-z]+(?:[A-Z][a-z]+)+)'), 1),
        # 专有名词: 连续大写字母开头的中文/英文词
        (re.compile(r'\b([A-Z][a-zA-Z]{2,})\b'), 1),
        # 中英混合: 术语(Term)
        (re.compile(r'([\u4e00-\u9fff]{2,10})\(([A-Z][a-zA-Z]+)\)'), 2),
    ]

    def __init__(self, min_length: int = 2, max_length: int = 60):
        self.min_length = min_length
        self.max_length = max_length

    def extract(self, text: str) -> List[str]:
        """提取实体列表，去重，过滤长度"""
        terms: Set[str] = set()

        for pattern, group_idx in self.PATTERNS:
            for match in pattern.finditer(text):
                term = match.group(group_idx).strip()
                if self.min_length <= len(term) <= self.max_length:
                    # 过滤纯数字和纯标点
                    if not term.isdigit() and not all(c in '，。；：！？、""''（）…—·' for c in term):
                        terms.add(term)

        return list(terms)


# ============================================================================
# 主整合器类
# ============================================================================

class WikiKGIntegrator:
    """
    Wiki 知识图谱整合器（合并 V3 + V4 增强版）

    用法:
        integrator = WikiKGIntegrator(domain="my_wiki")
        graph = integrator.integrate_chunks(chunks)         # 构建图谱
        results = integrator.hybrid_retrieve("查询")         # 混合检索
        integrator.add_feedback(query, response, paths, 4.0) # 反馈学习
        integrator.evolve_knowledge_graph()                  # 手动触发进化
    """

    def __init__(
        self,
        domain: str = "llm_wiki",
        config: Optional[IntegratorConfig] = None,
        entity_extractor: Optional[EntityExtractor] = None,
    ):
        """
        Args:
            domain: 知识图谱域名
            config: 整合器配置（None 则使用默认）
            entity_extractor: 自定义实体提取器（None 则使用 RegexEntityExtractor）
        """
        self.domain = domain
        self.config = config or IntegratorConfig(domain=domain)

        # ── 图后端 ──
        self.graph = KnowledgeGraph()

        # ── 实体提取器（可插拔）──
        self.entity_extractor = entity_extractor or RegexEntityExtractor(
            min_length=self.config.min_term_length,
            max_length=self.config.max_term_length,
        )

        # ── 内部状态 ──
        self.node_mappings: List[ChunkNodeMapping] = []
        self._section_hierarchy: Dict[str, str] = {}        # title → node_id
        self._section_parent: Dict[str, Optional[str]] = {}  # node_id → parent_node_id
        self._entity_index: Dict[str, str] = {}             # entity_name (lower) → node_id
        self._document_nodes: Dict[str, str] = {}           # doc_source → root_node_id
        self._last_chunk_node_id: Optional[str] = None
        self._chunk_order: List[str] = []                   # node_id 顺序列表

        # ── 缓存 ──
        self._cache: Dict[str, Any] = {}
        self._cache_hits = 0
        self._cache_misses = 0

        # ── EvoRAG 组件 ──
        self.feedback_manager: Optional[FeedbackManager] = None
        self.kg_evolver: Optional[KnowledgeGraphSelfEvolver] = None
        self.hybrid_retriever: Optional[HybridRetriever] = None
        self._kg_data: Dict[str, Dict[str, str]] = {}       # {triplet_id: {head,relation,tail}}
        self._reasoning_paths: Dict[str, List[List[str]]] = {}

        # ── EvoRAG 统计 ──
        self._evorag_stats: Dict[str, int] = {
            "feedback_count": 0,
            "evolution_count": 0,
            "retrieval_count": 0,
        }

        # ── 性能统计 ──
        self._perf_stats: Dict[str, int] = {
            "total_chunks": 0,
            "total_entities": 0,
            "total_relations": 0,
            "entity_links": 0,       # 实体链接命中数
            "cross_refs": 0,         # 跨文档引用数
            "cache_hits": 0,
            "cache_misses": 0,
        }

        # 初始化 EvoRAG
        if self.config.enable_evorag and self.config.enable_feedback:
            self._init_evorag()

        logger.info(
            f"WikiKGIntegrator 初始化完成 "
            f"(domain={domain}, evorag={self.config.enable_evorag}, "
            f"extractor={type(self.entity_extractor).__name__})"
        )

    # ========================================================================
    # 核心流程：文档块 → 知识图谱
    # ========================================================================

    def integrate_chunks(
        self, chunks: List[DocumentChunk], batch_size: Optional[int] = None
    ) -> KnowledgeGraph:
        """
        将文档块列表集成到知识图谱

        流程:
        1. 按 source 分组
        2. 批量创建节点（保留层级和顺序）
        3. 建立层次关系和前后关系
        4. 跨文档引用检测
        5. 实体链接去重优化
        6. 构建 EvoRAG 三元组数据

        Args:
            chunks: DocumentChunk 列表
            batch_size: 批量大小（默认使用 config.batch_size）

        Returns:
            KnowledgeGraph 实例
        """
        batch_size = batch_size or self.config.batch_size
        logger.info(f"开始集成 {len(chunks)} 个文档块到知识图谱")

        self._perf_stats["total_chunks"] = len(chunks)
        self._reset_state()

        # 1. 按 source 分组
        chunks_by_source = self._group_by_source(chunks)

        # 2. 逐文档处理
        for source, source_chunks in chunks_by_source.items():
            logger.info(f"处理文档: {source} ({len(source_chunks)} 块)")

            doc_root_id = self._create_document_root(source)
            self._document_nodes[source] = doc_root_id

            # 批量创建节点
            nodes = self._batch_create_nodes(source_chunks, doc_root_id, batch_size)

            # 建立所有关系
            self._establish_all_relations(nodes, source_chunks)

        # 3. 跨文档引用检测
        self._detect_cross_references()

        # 4. 实体链接优化
        self._optimize_entity_linking()

        # 5. 更新统计
        self._perf_stats["total_entities"] = self.graph.entity_count
        self._perf_stats["total_relations"] = self.graph.relation_count

        # 6. 构建 EvoRAG 三元组
        if self.config.enable_evorag:
            self._build_kg_data()

        logger.info(
            f"集成完成: {self.graph.entity_count} 实体, "
            f"{self.graph.relation_count} 关系"
        )
        return self.graph

    # ── 内部辅助方法 ──────────────────────────────────────

    def _reset_state(self) -> None:
        """重置所有内部状态"""
        self._section_hierarchy.clear()
        self._section_parent.clear()
        self._entity_index.clear()
        self._document_nodes.clear()
        self._last_chunk_node_id = None
        self._chunk_order.clear()
        self._cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0

    def _group_by_source(
        self, chunks: List[DocumentChunk]
    ) -> Dict[str, List[DocumentChunk]]:
        groups: Dict[str, List[DocumentChunk]] = {}
        for chunk in chunks:
            source = chunk.source or "unknown"
            groups.setdefault(source, []).append(chunk)
        return groups

    def _create_document_root(self, source: str) -> str:
        """为文档创建根实体"""
        entity = self.graph.add_entity(
            id=f"doc_root_{self._hash_text(source)}",
            name=f"Document: {source}",
            type=EntityType.DOCUMENT,
            description=f"文档根节点: {source}",
            source=source,
            is_root=True,
        )
        return entity.id

    def _batch_create_nodes(
        self, chunks: List[DocumentChunk], doc_root_id: str, batch_size: int
    ) -> List[Entity]:
        entities = []
        for i, chunk in enumerate(chunks):
            entity = self._create_chunk_entity(chunk, i, doc_root_id)
            entities.append(entity)
            if (i + 1) % batch_size == 0:
                logger.debug(f"已处理 {i + 1}/{len(chunks)} 块")
        return entities

    def _create_chunk_entity(
        self, chunk: DocumentChunk, index: int, doc_root_id: str
    ) -> Entity:
        """为单个文档块创建图实体"""
        title = chunk.title or f"Chunk_{index}"
        entity_type = self._infer_entity_type(chunk)
        chunk_id = self._generate_chunk_id(chunk)

        entity = self.graph.add_entity(
            id=f"chunk_{chunk_id}",
            name=title,
            type=entity_type,
            description=chunk.content[:200],
            source=chunk.source,
            chunk_type=chunk.chunk_type,
            section=chunk.section,
            chunk_index=index,
            full_content=chunk.content,
            doc_root_id=doc_root_id,
            metadata=chunk.metadata or {},
        )

        self._chunk_order.append(entity.id)
        self.node_mappings.append(
            ChunkNodeMapping(
                chunk_id=chunk_id,
                node_id=entity.id,
                title=title,
                entity_type=entity_type,
                chunk=chunk,
                chunk_index=index,
                doc_source=chunk.source or "unknown",
            )
        )
        return entity

    def _infer_entity_type(self, chunk: DocumentChunk) -> EntityType:
        """根据文档块类型推断实体类型"""
        chunk_type = getattr(chunk, "chunk_type", "text") or "text"
        type_map = {
            "code": EntityType.FUNCTION,
            "text": EntityType.CONCEPT,
            "heading": EntityType.CONCEPT,
            "table": EntityType.CONCEPT,
        }
        return type_map.get(chunk_type, EntityType.CONCEPT)

    # ── 关系建立 ──────────────────────────────────────────

    def _establish_all_relations(
        self, entities: List[Entity], chunks: List[DocumentChunk]
    ) -> None:
        """为所有实体建立层次关系和顺序关系"""
        for entity, chunk in zip(entities, chunks):
            self._establish_hierarchy(entity, chunk)
            self._establish_chunk_order(entity.id)
            self._extract_and_link_concepts(chunk.content, entity.id, chunk.source or "")

    def _establish_hierarchy(self, entity: Entity, chunk: DocumentChunk) -> None:
        """建立章节层级关系"""
        title = chunk.title or ""
        section = getattr(chunk, "section", "") or ""

        if not title:
            return

        level = self._detect_heading_level(section)
        if level == 0:
            return

        self._section_hierarchy[title] = entity.id

        parent_id = self._find_parent_in_hierarchy(level, title)
        if parent_id and parent_id != entity.id:
            try:
                self.graph.add_relation(
                    source_id=entity.id,
                    target_id=parent_id,
                    type=RelationType.PART_OF,
                    weight=1.0,
                    description=f"属于章节: {title}",
                )
                self._section_parent[entity.id] = parent_id
                for m in self.node_mappings:
                    if m.node_id == entity.id:
                        m.parent_node_id = parent_id
                        break
            except ValueError:
                pass

        self._cleanup_deeper_levels(level, title)

    @staticmethod
    def _detect_heading_level(section: str) -> int:
        """检测标题层级 (0=没有层级, 1=顶层, 2=子层...)"""
        if not section:
            return 0
        # 按路径分隔符判断: "Top > Sub > SubSub"
        parts = [p.strip() for p in section.replace(">", " > ").split(">") if p.strip()]
        return min(len(parts), 5)

    def _find_parent_in_hierarchy(self, level: int, current_title: str) -> Optional[str]:
        """在层级表中查找父节点"""
        if level <= 1:
            return None
        # 返回最近添加的同级或上级标题
        titles = list(self._section_hierarchy.keys())
        for prev_title in reversed(titles):
            if prev_title == current_title:
                continue
            prev_level = self._detect_heading_level(prev_title)
            if prev_level < level:
                return self._section_hierarchy[prev_title]
        return None

    def _cleanup_deeper_levels(self, level: int, title: str) -> None:
        """清理比当前层级更深的旧条目"""
        to_remove = []
        for t in self._section_hierarchy:
            if t != title and self._detect_heading_level(t) > level:
                to_remove.append(t)
        for t in to_remove:
            del self._section_hierarchy[t]

    def _establish_chunk_order(self, node_id: str) -> None:
        """建立分块之间的前后关系"""
        if self._last_chunk_node_id and self._last_chunk_node_id != node_id:
            try:
                self.graph.add_relation(
                    source_id=self._last_chunk_node_id,
                    target_id=node_id,
                    type=RelationType.REFERENCES,
                    weight=0.5,
                    description="next_chunk",
                )
                self.graph.add_relation(
                    source_id=node_id,
                    target_id=self._last_chunk_node_id,
                    type=RelationType.REFERENCES,
                    weight=0.5,
                    description="prev_chunk",
                )
            except ValueError:
                pass
        self._last_chunk_node_id = node_id

    # ── 实体链接 ──────────────────────────────────────────

    def _extract_and_link_concepts(
        self, text: str, context_node_id: str, doc_source: str
    ) -> None:
        """
        从文本中提取概念并执行实体链接

        如果概念已存在于全局实体索引中，则创建链接关系；
        否则创建新实体并加入索引。
        """
        terms = self.entity_extractor.extract(text)

        for term in terms:
            term_lower = term.lower().strip()

            # 实体链接：检查是否已存在
            if term_lower in self._entity_index:
                existing_id = self._entity_index[term_lower]
                try:
                    self.graph.add_relation(
                        source_id=context_node_id,
                        target_id=existing_id,
                        type=RelationType.REFERENCES,
                        weight=0.8,
                        description=f"引用概念: {term}",
                    )
                    self._perf_stats["entity_links"] += 1
                except ValueError:
                    pass
            else:
                # 创建新概念实体
                concept_id = f"concept_{self._hash_text(term_lower)}"
                try:
                    entity = self.graph.add_entity(
                        id=concept_id,
                        name=term,
                        type=EntityType.CONCEPT,
                        description=f"概念: {term}",
                        source_doc=doc_source,
                    )
                    self._entity_index[term_lower] = entity.id

                    # 链接上下文节点到新概念
                    self.graph.add_relation(
                        source_id=context_node_id,
                        target_id=entity.id,
                        type=RelationType.DEFINES,
                        weight=0.6,
                        description=f"定义概念: {term}",
                    )
                    self._perf_stats["entity_links"] += 1
                except ValueError:
                    pass

    def _optimize_entity_linking(self) -> None:
        """
        实体链接优化：合并相似名称的重复实体

        使用模糊匹配合并名称相近的实体（如 "deepseek" 和 "DeepSeek"）
        """
        merged = 0
        entities = self.graph.list_entities()
        name_index: Dict[str, str] = {}  # normalized_name → entity_id

        for entity in entities:
            norm_name = entity.name.lower().strip()
            if norm_name in name_index:
                # 合并到已有实体
                existing_id = name_index[norm_name]
                try:
                    self.graph.add_relation(
                        source_id=entity.id,
                        target_id=existing_id,
                        type=RelationType.RELATED_TO,
                        weight=0.9,
                        description="实体链接合并",
                    )
                    merged += 1
                except ValueError:
                    pass
            else:
                name_index[norm_name] = entity.id

        if merged:
            logger.info(f"实体链接优化完成: 合并 {merged} 个重复实体")

    # ── 跨文档引用检测 ────────────────────────────────────

    def _detect_cross_references(self) -> None:
        """
        检测跨文档引用

        模式：
        - "参见 xxx" / "参考 xxx" / "详见 xxx"
        - URL 引用
        - 文档内交叉引用 [xxx](./doc.md)
        """
        ref_patterns = [
            re.compile(r'(?:参见|参考|详见|引用)\s*[：:]*\s*(.+?)(?:[。，,;；\n]|$)'),
            re.compile(r'\[(.+?)\]\((.+?)\)'),  # Markdown 链接
            re.compile(r'https?://[^\s]+'),
        ]

        entities = self.graph.list_entities()

        for entity in entities:
            text = entity.attributes.get("full_content", entity.description)
            if not text:
                continue

            for pattern in ref_patterns:
                for match in pattern.finditer(text):
                    groups = match.groups()
                    ref_text = groups[0] if groups else match.group()
                    if len(ref_text) < 3:
                        continue

                    # 查找被引用的实体
                    for target in entities:
                        if target.id == entity.id:
                            continue
                        if ref_text.lower() in target.name.lower():
                            try:
                                self.graph.add_relation(
                                    source_id=entity.id,
                                    target_id=target.id,
                                    type=RelationType.REFERENCES,
                                    weight=0.7,
                                    description=f"跨文档引用: {ref_text[:50]}",
                                )
                                self._perf_stats["cross_refs"] += 1
                            except ValueError:
                                pass

    # ========================================================================
    # 图谱推理
    # ========================================================================

    def find_path(self, start_name: str, end_name: str) -> Optional[List[str]]:
        """通过名称查找两实体之间的最短路径"""
        start_id = self._find_entity_id(start_name)
        end_id = self._find_entity_id(end_name)
        if not start_id or not end_id:
            return None

        cache_key = f"path:{start_id}:{end_id}"
        if self.config.enable_cache and cache_key in self._cache:
            self._cache_hits += 1
            return self._cache[cache_key]

        self._cache_misses += 1
        path = self.graph.find_path(start_id, end_id)
        if self.config.enable_cache:
            self._cache[cache_key] = path
        return path

    def extract_subgraph(
        self, center_name: str, max_depth: int = 2
    ) -> Dict[str, Any]:
        """
        提取以指定实体为中心的子图

        Returns:
            {"center": entity, "nodes": [...], "relations": [...]}
        """
        center_id = self._find_entity_id(center_name)
        if not center_id:
            return {"center": None, "nodes": [], "relations": []}

        visited: Set[str] = {center_id}
        queue: deque = deque([(center_id, 0)])
        sub_nodes: List[Entity] = []
        sub_relations: List[Relation] = []

        while queue:
            node_id, depth = queue.popleft()
            entity = self.graph.get_entity(node_id)
            if entity:
                sub_nodes.append(entity)

            if depth >= max_depth:
                continue

            for rel in self.graph.get_relations(node_id):
                sub_relations.append(rel)
                neighbor = (
                    rel.target_id if rel.source_id == node_id else rel.source_id
                )
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, depth + 1))

        return {
            "center": self.graph.get_entity(center_id),
            "nodes": sub_nodes,
            "relations": sub_relations,
        }

    def query_related_concepts(
        self, name: str, max_depth: int = 2
    ) -> List[Dict[str, Any]]:
        """
        查询与指定实体相关的概念列表（BFS 遍历）

        Returns:
            [{name, type, distance, path}, ...]
        """
        start_id = self._find_entity_id(name)
        if not start_id:
            return []

        results: List[Dict[str, Any]] = []
        visited: Set[str] = {start_id}
        queue: deque = deque([(start_id, 0, [name])])

        while queue:
            node_id, depth, path = queue.popleft()

            if depth > 0:
                entity = self.graph.get_entity(node_id)
                if entity:
                    results.append({
                        "name": entity.name,
                        "type": entity.type.value,
                        "distance": depth,
                        "path": path,
                    })

            if depth >= max_depth:
                continue

            for rel in self.graph.get_relations(node_id):
                neighbor = (
                    rel.target_id if rel.source_id == node_id else rel.source_id
                )
                if neighbor not in visited:
                    visited.add(neighbor)
                    neighbor_entity = self.graph.get_entity(neighbor)
                    neighbor_name = neighbor_entity.name if neighbor_entity else neighbor
                    queue.append((neighbor, depth + 1, path + [neighbor_name]))

        return results

    def reason_over_graph(self, query: str) -> Dict[str, Any]:
        """
        基于图谱的语义推理

        通过搜索相关概念和路径来生成推理结果
        """
        # 搜索相关实体
        search_results = self.graph.search(query)
        entities = [e for e, score in search_results[:5]]

        # 子图提取
        subgraphs = []
        for entity in entities[:3]:
            subgraph = self.extract_subgraph(entity.name, max_depth=2)
            subgraphs.append(subgraph)

        # 路径查找（实体对之间）
        paths = []
        for i, e1 in enumerate(entities[:3]):
            for e2 in entities[i + 1 : 3]:
                path = self.graph.find_path(e1.id, e2.id)
                if path:
                    paths.append({
                        "from": e1.name,
                        "to": e2.name,
                        "path": [
                            self.graph.get_entity(nid).name
                            if self.graph.get_entity(nid)
                            else nid
                            for nid in path
                        ],
                    })

        return {
            "query": query,
            "matched_entities": [e.name for e in entities],
            "subgraph_count": len(subgraphs),
            "paths": paths,
            "timestamp": datetime.now().isoformat(),
        }

    # ========================================================================
    # EvoRAG: 反馈驱动自进化
    # ========================================================================

    def _init_evorag(self) -> None:
        """初始化 EvoRAG 组件"""
        try:
            self.feedback_manager = FeedbackManager(
                feedback_db_path=self.config.feedback_db_path,
                learning_rate=self.config.learning_rate,
                alpha=self.config.alpha,
            )

            if self.config.enable_self_evolution:
                self.kg_evolver = KnowledgeGraphSelfEvolver(
                    feedback_manager=self.feedback_manager,
                    max_hops=self.config.max_hops,
                    min_path_score=self.config.min_path_score,
                )

            if self.config.enable_hybrid_retrieval:
                self.hybrid_retriever = HybridRetriever(
                    feedback_manager=self.feedback_manager,
                    kg_self_evolver=self.kg_evolver,
                    top_n_entities=self.config.top_n_entities,
                    top_m_paths=self.config.top_m_paths,
                    alpha=self.config.alpha,
                )

            logger.info("EvoRAG 组件初始化完成")
        except Exception as e:
            logger.warning(f"EvoRAG 初始化失败: {e}")
            self.feedback_manager = None

    def _build_kg_data(self) -> None:
        """构建 EvoRAG 三元组数据（从 KnowledgeGraph 提取）"""
        self._kg_data.clear()

        entities = {e.id: e for e in self.graph.list_entities()}

        for rel in self.graph._relations:
            triplet_id = f"triplet_{self._hash_text(rel.source_id + rel.target_id + rel.type.value)}"
            head = entities.get(rel.source_id)
            tail = entities.get(rel.target_id)
            self._kg_data[triplet_id] = {
                "head": head.name if head else rel.source_id,
                "relation": rel.type.value,
                "tail": tail.name if tail else rel.target_id,
                "source_id": rel.source_id,
                "target_id": rel.target_id,
            }

        logger.debug(f"构建 KG 数据完成: {len(self._kg_data)} 三元组")

    def add_feedback(
        self,
        query: str,
        response: str,
        paths: List[List[str]],
        feedback_score: float,
        feedback_type: str = "human",
    ) -> Optional[str]:
        """
        添加用户反馈 → 触发自进化

        Args:
            query: 用户查询文本
            response: 生成的回答
            paths: 推理路径（三元组 ID 列表的列表）
            feedback_score: 反馈评分 (1-5)
            feedback_type: 反馈来源 (human/auto/implicit)

        Returns:
            反馈记录 ID，EvoRAG 未启用则返回 None
        """
        if not self.feedback_manager:
            logger.warning("EvoRAG 反馈管理器未启用")
            return None

        record_id = self.feedback_manager.add_feedback(
            query=query,
            response=response,
            paths=paths,
            feedback_score=feedback_score,
            feedback_type=feedback_type,
        )

        self._evorag_stats["feedback_count"] += 1

        # 定期触发进化
        if (
            self.config.enable_self_evolution
            and self.kg_evolver
            and self._evorag_stats["feedback_count"] % self.config.evolution_interval == 0
        ):
            self.evolve_knowledge_graph()

        logger.info(
            f"添加反馈 #{self._evorag_stats['feedback_count']}: "
            f"score={feedback_score}, type={feedback_type}"
        )
        return record_id

    def evolve_knowledge_graph(self) -> Dict[str, Any]:
        """
        执行知识图谱自进化

        基于累积的反馈数据优化图谱结构：
        - 创建高频路径的捷径边
        - 抑制低质量关系
        - 强化高贡献路径

        Returns:
            进化后的 KG 数据
        """
        if not self.kg_evolver:
            logger.warning("KG 自进化器未启用")
            return self._kg_data

        logger.info("开始 KG 自进化...")
        evolved = self.kg_evolver.evolve_knowledge_graph(self._kg_data)
        self._kg_data = evolved
        self._evorag_stats["evolution_count"] += 1

        stats = self.kg_evolver.get_statistics()
        logger.info(
            f"KG 进化完成: 捷径边={stats.get('shortcut_edges_count', 0)}, "
            f"抑制={stats.get('suppressed_triplets_count', 0)}"
        )
        return evolved

    def hybrid_retrieve(
        self, query: str, top_k: int = 10
    ) -> List[RetrievalResult]:
        """
        混合优先级检索（语义相似度 + 反馈贡献度）

        Args:
            query: 查询文本
            top_k: 返回结果数

        Returns:
            排序后的检索结果列表
        """
        if not self.hybrid_retriever:
            # 降级：仅用图谱搜索
            entities = self.graph.search(query)
            return [
                RetrievalResult(
                    triplet_id=e.id,
                    head=e.name,
                    relation="matches",
                    tail=query,
                    hybrid_priority=score,
                    semantic_similarity=score,
                    contribution_score=0.0,
                )
                for e, score in entities[:top_k]
            ]

        results = self.hybrid_retriever.retrieve_by_query(
            query=query, knowledge_graph=self._kg_data
        )
        self._evorag_stats["retrieval_count"] += 1
        return results[:top_k]

    def retrieve_paths(
        self, entity_name: str, max_hops: int = 3
    ) -> List[List[RetrievalResult]]:
        """检索从实体出发的推理路径"""
        if not self.hybrid_retriever:
            return []
        return self.hybrid_retriever.retrieve_paths_by_entity(
            entity=entity_name,
            knowledge_graph=self._kg_data,
            max_hops=max_hops,
        )

    # ========================================================================
    # 统计与诊断
    # ========================================================================

    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        return {
            **self._perf_stats,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_hit_rate": (
                self._cache_hits / max(self._cache_hits + self._cache_misses, 1)
            ),
        }

    def get_evorag_stats(self) -> Dict[str, Any]:
        """获取 EvoRAG 统计"""
        stats = dict(self._evorag_stats)
        if self.feedback_manager:
            stats["feedback_manager"] = self.feedback_manager.get_statistics()
        if self.kg_evolver:
            stats["kg_evolver"] = self.kg_evolver.get_statistics()
        if self.hybrid_retriever:
            stats["hybrid_retriever"] = self.hybrid_retriever.get_statistics()
        return stats

    def update_config(self, **kwargs) -> None:
        """运行时更新配置"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                logger.info(f"配置更新: {key} = {value}")

    # ========================================================================
    # 内部工具方法
    # ========================================================================

    def _find_entity_id(self, name: str) -> Optional[str]:
        """通过名称查找实体 ID（精确+模糊匹配）"""
        name_lower = name.lower().strip()
        for entity in self.graph.list_entities():
            if entity.name.lower().strip() == name_lower:
                return entity.id
        # 模糊匹配
        for entity in self.graph.list_entities():
            if name_lower in entity.name.lower():
                return entity.id
        return None

    @staticmethod
    def _hash_text(text: str) -> str:
        """生成短哈希"""
        return hashlib.md5(text.encode("utf-8")).hexdigest()[:12]

    @staticmethod
    def _generate_chunk_id(chunk: DocumentChunk) -> str:
        """为文档块生成唯一 ID"""
        source = getattr(chunk, "source", "") or ""
        title = getattr(chunk, "title", "") or ""
        content_prefix = (getattr(chunk, "content", "") or "")[:50]
        raw = f"{source}:{title}:{content_prefix}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


# ============================================================================
# 便捷工厂函数
# ============================================================================

def create_wiki_kg_integrator(
    chunks: Optional[List[DocumentChunk]] = None,
    domain: str = "llm_wiki",
    enable_evorag: bool = True,
    entity_extractor: Optional[EntityExtractor] = None,
    **config_overrides,
) -> WikiKGIntegrator:
    """
    便捷工厂：创建并初始化 Wiki 知识图谱整合器

    Args:
        chunks: 要集成的文档块列表（可选）
        domain: 域名
        enable_evorag: 是否启用 EvoRAG
        entity_extractor: 自定义实体提取器
        **config_overrides: 额外的配置覆盖

    Returns:
        已初始化的整合器实例
    """
    config = IntegratorConfig(
        domain=domain,
        enable_evorag=enable_evorag,
        enable_feedback=enable_evorag,
        **config_overrides,
    )

    integrator = WikiKGIntegrator(
        domain=domain,
        config=config,
        entity_extractor=entity_extractor,
    )

    if chunks:
        integrator.integrate_chunks(chunks)

    return integrator


__all__ = [
    "WikiKGIntegrator",
    "IntegratorConfig",
    "ChunkNodeMapping",
    "EntityExtractor",
    "RegexEntityExtractor",
    "create_wiki_kg_integrator",
]
