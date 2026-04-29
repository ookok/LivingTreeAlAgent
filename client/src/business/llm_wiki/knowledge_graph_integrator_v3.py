"""
LLM Wiki 模块 - KnowledgeGraph 集成器（Phase 3 高级版）

================================================

Phase 3 (高级功能): 跨文档引用、实体链接、图谱推理 + 性能优化

新增功能：
1. ✅ 跨文档引用检测（cross_reference 关系）
2. ✅ 实体链接（Entity Linking，避免重复节点）
3. ✅ 图谱推理（路径查找、子图提取、问答推理）
4. ✅ 性能优化（批量处理、缓存、增量更新）

作者: LivingTreeAI Team
日期: 2026-04-29
版本: 3.0.0 (Phase 3 高级功能)
"""

import re
import json
import hashlib
import logging
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from collections import deque

from loguru import logger

# 导入 Phase 1 的数据模型
from .models import DocumentChunk

# 导入 KnowledgeGraph 核心类
from client.src.business.knowledge_graph.graph import (
    KnowledgeGraph,
    KnowledgeNode,
    KnowledgeRelation
)


@dataclass
class WikiNodeMapping:
    """Wiki 节点映射（Phase 3 增强版）"""
    chunk_id: str
    node_id: str
    title: str
    node_type: str
    chunk: DocumentChunk
    parent_node_id: Optional[str] = None
    chunk_index: int = 0
    doc_id: str = ""  # 新增：文档ID


class LLMWikiKnowledgeGraphIntegratorV3:
    """
    LLM Wiki → KnowledgeGraph 集成器（Phase 3 高级版）
    
    新增功能：
    1. 跨文档引用检测
    2. 实体链接（Entity Linking）
    3. 图谱推理
    4. 性能优化（缓存、批量处理）
    """
    
    def __init__(self, domain: str = "llm_wiki", enable_cache: bool = True):
        """初始化集成器"""
        self.domain = domain
        self.graph = KnowledgeGraph()
        self.node_mappings: List[WikiNodeMapping] = []
        
        # 章节层级跟踪
        self._section_hierarchy: Dict[str, str] = {}  # title -> node_id
        self._section_parent: Dict[str, Optional[str]] = {}  # node_id -> parent_node_id
        
        # 分块顺序跟踪
        self._last_chunk_node_id: Optional[str] = None
        self._chunk_order: List[str] = []  # node_id 的顺序列表
        
        # Phase 3 新增：实体索引（用于 Entity Linking）
        self._entity_index: Dict[str, str] = {}  # entity_name (lowercase) -> node_id
        
        # Phase 3 新增：文档索引（用于跨文档引用）
        self._document_nodes: Dict[str, str] = {}  # source -> root_node_id
        
        # Phase 3 新增：缓存
        self._enable_cache = enable_cache
        self._cache: Dict[str, Any] = {}
        self._cache_hits = 0
        self._cache_misses = 0
        
        # 性能统计
        self._performance_stats: Dict[str, Any] = {
            "total_chunks": 0,
            "total_nodes": 0,
            "total_relations": 0,
            "entity_links": 0,
            "cross_refs": 0,
            "cache_hits": 0,
            "cache_misses": 0
        }
        
        logger.info(f"LLMWikiKnowledgeGraphIntegratorV3 初始化完成 (domain={domain}, cache={enable_cache})")
    
    def integrate_chunks(self, chunks: List[DocumentChunk], batch_size: int = 50) -> KnowledgeGraph:
        """
        将 DocumentChunk 列表集成到 KnowledgeGraph（Phase 3）
        
        Args:
            chunks: Phase 1 解析的文档块列表
            batch_size: 批量处理大小
            
        Returns:
            KnowledgeGraph 实例
        """
        logger.info(f"开始集成 {len(chunks)} 个文档块到知识图谱（Phase 3 高级模式）")
        self._performance_stats["total_chunks"] = len(chunks)
        
        # 0. 重置状态
        self._reset_state()
        
        # 1. 按 source 分组
        chunks_by_source = self._group_by_source(chunks)
        
        # 2. 批量处理每个文档
        for source, source_chunks in chunks_by_source.items():
            logger.info(f"处理文档: {source} ({len(source_chunks)} 个块)")
            
            # 创建文档根节点
            doc_root_id = self._create_document_root(source)
            self._document_nodes[source] = doc_root_id
            
            # 批量创建节点
            nodes = self._batch_create_nodes(source_chunks, doc_root_id, batch_size)
            
            # 建立关系
            self._establish_all_relations(nodes, source_chunks)
        
        # 3. 跨文档引用检测
        self._link_cross_references_v3()
        
        # 4. 实体链接优化（合并重复实体）
        self._optimize_entity_linking()
        
        # 5. 更新性能统计
        self._performance_stats["total_nodes"] = len(self.graph.nodes)
        self._performance_stats["total_relations"] = len(self.graph.relations)
        
        logger.info(f"Phase 3 集成完成: {len(self.graph.nodes)} 个节点, {len(self.graph.relations)} 个关系")
        logger.info(f"性能统计: {self._performance_stats}")
        
        return self.graph
    
    def _reset_state(self) -> None:
        """重置内部状态"""
        self._section_hierarchy = {}
        self._section_parent = {}
        self._last_chunk_node_id = None
        self._chunk_order = []
        self._entity_index = {}
        self._document_nodes = {}
        self._cache = {}
        self._cache_hits = 0
        self._cache_misses = 0
    
    def _group_by_source(self, chunks: List[DocumentChunk]) -> Dict[str, List[DocumentChunk]]:
        """按 source 分组"""
        groups = {}
        for chunk in chunks:
            source = chunk.source or "unknown"
            if source not in groups:
                groups[source] = []
            groups[source].append(chunk)
        return groups
    
    def _create_document_root(self, source: str) -> str:
        """创建文档根节点"""
        doc_node = KnowledgeNode(
            title=f"Document: {source}",
            content=f"文档根节点: {source}",
            node_type="document_root",
            domain=self.domain,
            properties={
                "source": source,
                "is_root": True
            }
        )
        self.graph.add_node(doc_node)
        logger.debug(f"创建文档根节点: {doc_node.node_id} for {source}")
        return doc_node.node_id
    
    def _batch_create_nodes(self, chunks: List[DocumentChunk], doc_root_id: str, 
                           batch_size: int) -> List[KnowledgeNode]:
        """批量创建节点（性能优化）"""
        nodes = []
        
        for index, chunk in enumerate(chunks):
            node = self._create_node_with_order(chunk, index, doc_root_id)
            nodes.append(node)
            
            # 批量处理日志
            if (index + 1) % batch_size == 0:
                logger.debug(f"已处理 {index + 1}/{len(chunks)} 个块")
        
        return nodes
    
    def _establish_all_relations(self, nodes: List[KnowledgeNode], 
                                chunks: List[DocumentChunk]) -> None:
        """建立所有关系"""
        for i, (node, chunk) in enumerate(zip(nodes, chunks)):
            # 1. 建立章节层级关系
            self._establish_hierarchy(node, chunk)
            
            # 2. 建立分块顺序关系
            self._establish_chunk_order(node.node_id)
            
            # 3. 提取概念（使用实体链接）
            self._extract_concepts_with_linking(chunk.content, node.node_id)
    
    def _create_node_with_order(self, chunk: DocumentChunk, index: int, 
                                doc_root_id: str) -> KnowledgeNode:
        """创建节点（保留顺序信息）"""
        title = chunk.title or f"Chunk {index}"
        
        # 确定节点类型
        node_type = self._map_chunk_type_to_node_type(chunk)
        
        # 创建节点
        node = KnowledgeNode(
            title=title,
            content=chunk.content[:500],  # 限制长度
            node_type=node_type,
            domain=self.domain,
            properties={
                "source": chunk.source,
                "chunk_type": chunk.chunk_type,
                "section": chunk.section,
                "metadata": chunk.metadata,
                "chunk_index": index,  # ✅ 保留原始顺序
                "full_content": chunk.content,  # 完整内容
                "doc_root_id": doc_root_id  # 文档根节点
            }
        )
        
        # 添加到图谱
        self.graph.add_node(node)
        
        # 记录顺序
        self._chunk_order.append(node.node_id)
        
        # 记录映射
        mapping = WikiNodeMapping(
            chunk_id=self._generate_chunk_id(chunk),
            node_id=node.node_id,
            title=title,
            node_type=node_type,
            chunk=chunk,
            chunk_index=index,
            doc_id=chunk.source or "unknown"
        )
        self.node_mappings.append(mapping)
        
        logger.debug(f"创建节点: {title} ({node_type}) [index={index}]")
        return node
    
    def _establish_hierarchy(self, node: KnowledgeNode, chunk: DocumentChunk) -> None:
        """建立章节层级关系"""
        if chunk.chunk_type != "text":
            return
        
        title = chunk.title or ""
        if not title:
            return
        
        # 检测层级
        level = self._detect_heading_level(chunk.section)
        
        if level == 0:
            return
        
        # 记录到层级表
        self._section_hierarchy[title] = node.node_id
        
        # 查找父章节
        parent_id = self._find_parent_in_hierarchy(level, title)
        
        if parent_id:
            # 建立 part_of 关系
            self._add_relation(node.node_id, "part_of", parent_id)
            self._section_parent[node.node_id] = parent_id
            
            # 更新映射
            for mapping in self.node_mappings:
                if mapping.node_id == node.node_id:
                    mapping.parent_node_id = parent_id
                    break
        
        # 清理更深层级
        self._cleanup_deeper_levels(level, title)
    
    def _establish_chunk_order(self, node_id: str) -> None:
        """建立分块顺序关系"""
        if self._last_chunk_node_id:
            # 添加 next_chunk 关系
            self._add_relation(self._last_chunk_node_id, "next_chunk", node_id)
            
            # 添加 prev_chunk 关系
            self._add_relation(node_id, "prev_chunk", self._last_chunk_node_id)
        
        self._last_chunk_node_id = node_id
    
    def _extract_concepts_with_linking(self, text: str, context_node_id: str) -> None:
        """
        从文本中提取概念（带实体链接）
        
        Entity Linking: 如果概念已存在，则链接到已有节点；否则创建新节点
        """
        # 提取术语
        terms = self._extract_terms(text)
        
        for term in terms:
            if len(term) < 3 or len(term) > 50:
                continue
            
            # Entity Linking: 检查是否已存在
            entity_key = term.lower()
            
            if entity_key in self._entity_index:
                # 已存在：链接到已有节点
                existing_node_id = self._entity_index[entity_key]
                self._add_relation(context_node_id, "mentions", existing_node_id, weight=0.8)
                self._performance_stats["entity_links"] += 1
                logger.debug(f"Entity Linking: {term} -> {existing_node_id}")
            else:
                # 不存在：创建新节点
                concept_node = KnowledgeNode(
                    title=term,
                    content=f"概念: {term}",
                    node_type="concept",
                    domain=self.domain,
                    properties={
                        "extracted_from": context_node_id,
                        "extraction_method": "enhanced_pattern"
                    }
                )
                self.graph.add_node(concept_node)
                
                # 记录到实体索引
                self._entity_index[entity_key] = concept_node.node_id
                
                # 建立关系
                self._add_relation(context_node_id, "mentions", concept_node.node_id, weight=0.8)
                logger.debug(f"创建概念节点: {term} ({concept_node.node_id})")
    
    def _extract_terms(self, text: str) -> Set[str]:
        """提取术语（多种模式）"""
        terms = set()
        
        # 模式 1: **加粗术语**
        bold_terms = re.findall(r"\*\*(.+?)\*\*", text)
        terms.update(bold_terms)
        
        # 模式 2: `代码术语`
        code_terms = re.findall(r"`([^`]+)`", text)
        terms.update(code_terms)
        
        # 模式 3: 标题式术语（大写字母开头 + 冒号）
        title_terms = re.findall(r"^([A-Z][a-zA-Z\s]{2,}):", text, re.MULTILINE)
        terms.update(title_terms)
        
        # 模式 4: 定义式术语（术语 + 是/是指）
        definition_terms = re.findall(r"^(.+?)\s+(?:是|是指|refers to|is defined as)", text, re.MULTILINE | re.IGNORECASE)
        terms.update(definition_terms)
        
        # 模式 5: 引号术语（"术语" 或 '术语'）
        quote_terms = re.findall(r"[\"'](.+?)[\"']", text)
        terms.update([t for t in quote_terms if len(t) >= 3])
        
        return terms
    
    def _link_cross_references_v3(self) -> None:
        """
        建立跨文档引用关系（Phase 3 实现）
        
        检测模式：
        1. "参见 X", "参考 X", "See X", "Refer to X"
        2. URL 链接
        3. 文档标题匹配
        """
        logger.info("开始检测跨文档引用...")
        
        # 收集所有文档标题
        doc_titles = {}
        for mapping in self.node_mappings:
            if mapping.node_type in ["chapter", "section", "subsection"]:
                doc_titles[mapping.title.lower()] = mapping.node_id
        
        # 遍历所有节点，检测引用
        for mapping in self.node_mappings:
            chunk = mapping.chunk
            content = chunk.content
            
            # 模式 1: "参见/参考/See/Refer to"
            ref_patterns = [
                r"(?:参见|参考|See|Refer to)\s+[：:]\s*(.+?)(?:\n|$)",
                r"\[(.+?)\]\((?:http|https|.+\.md)\)",  # Markdown 链接
                r"https?://[^\s]+"  # URL
            ]
            
            for pattern in ref_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    ref_title = match.strip()
                    
                    # 查找匹配的文档标题
                    if ref_title.lower() in doc_titles:
                        target_node_id = doc_titles[ref_title.lower()]
                        
                        # 建立 cross_reference 关系
                        self._add_relation(
                            mapping.node_id, 
                            "cross_reference", 
                            target_node_id,
                            weight=0.9
                        )
                        self._performance_stats["cross_refs"] += 1
                        logger.debug(f"跨文档引用: {mapping.title} -> {ref_title}")
            
            # 模式 2: URL 链接（简化处理）
            urls = re.findall(r"https?://[^\s]+", content)
            for url in urls:
                # 创建 URL 节点
                url_node = KnowledgeNode(
                    title=url,
                    content=f"URL: {url}",
                    node_type="url_reference",
                    domain=self.domain,
                    properties={
                        "url": url,
                        "reference_type": "external_link"
                    }
                )
                self.graph.add_node(url_node)
                
                # 建立关系
                self._add_relation(mapping.node_id, "cross_reference", url_node.node_id, weight=0.7)
                self._performance_stats["cross_refs"] += 1
        
        logger.info(f"跨文档引用检测完成: {self._performance_stats['cross_refs']} 个引用关系")
    
    def _optimize_entity_linking(self) -> None:
        """
        优化实体链接：合并相同实体的节点
        
        如果同一个实体被多次提取，合并到同一个节点
        """
        logger.info("开始优化实体链接...")
        
        # 按实体名称分组
        entity_groups: Dict[str, List[str]] = {}  # entity_key -> [node_id1, node_id2, ...]
        
        for node_id, node in self.graph.nodes.items():
            if node.node_type == "concept":
                entity_key = node.title.lower()
                if entity_key not in entity_groups:
                    entity_groups[entity_key] = []
                entity_groups[entity_key].append(node_id)
        
        # 合并重复实体
        merged_count = 0
        for entity_key, node_ids in entity_groups.items():
            if len(node_ids) > 1:
                # 保留第一个节点，合并其他节点
                primary_node_id = node_ids[0]
                
                for duplicate_node_id in node_ids[1:]:
                    # 将所有指向重复节点的关系重定向到主节点
                    self._redirect_relations(duplicate_node_id, primary_node_id)
                    
                    # 删除重复节点
                    if duplicate_node_id in self.graph.nodes:
                        del self.graph.nodes[duplicate_node_id]
                    
                    merged_count += 1
                
                # 更新实体索引
                self._entity_index[entity_key] = primary_node_id
        
        logger.info(f"实体链接优化完成: 合并了 {merged_count} 个重复实体")
    
    def _redirect_relations(self, old_node_id: str, new_node_id: str) -> None:
        """将指向 old_node_id 的关系重定向到 new_node_id"""
        new_relations = []
        
        for rel in self.graph.relations:
            if rel.source_id == old_node_id:
                # 如果是源节点，改为新节点
                rel.source_id = new_node_id
                new_relations.append(rel)
            elif rel.target_id == old_node_id:
                # 如果是目标节点，改为新节点
                rel.target_id = new_node_id
                new_relations.append(rel)
            else:
                new_relations.append(rel)
        
        self.graph.relations = new_relations
    
    # ============================================================
    # 图谱推理功能（Phase 3 新增）
    # ============================================================
    
    def find_path(self, start_node_id: str, end_node_id: str) -> Optional[List[str]]:
        """
        查找两个节点之间的最短路径（BFS）
        
        Args:
            start_node_id: 起始节点ID
            end_node_id: 目标节点ID
            
        Returns:
            节点ID列表（包括起点和终点），如果不可达则返回None
        """
        if start_node_id not in self.graph.nodes or end_node_id not in self.graph.nodes:
            return None
        
        # BFS
        queue = deque([(start_node_id, [start_node_id])])
        visited = {start_node_id}
        
        while queue:
            current_id, path = queue.popleft()
            
            if current_id == end_node_id:
                return path
            
            # 获取邻居
            neighbors = self._get_neighbors(current_id)
            
            for neighbor_id in neighbors:
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    queue.append((neighbor_id, path + [neighbor_id]))
        
        return None  # 不可达
    
    def _get_neighbors(self, node_id: str) -> Set[str]:
        """获取节点的所有邻居（双向）"""
        neighbors = set()
        
        for rel in self.graph.relations:
            if rel.source_id == node_id:
                neighbors.add(rel.target_id)
            if rel.target_id == node_id:
                neighbors.add(rel.source_id)
        
        return neighbors
    
    def extract_subgraph(self, node_id: str, max_depth: int = 2) -> KnowledgeGraph:
        """
        提取以指定节点为中心的子图
        
        Args:
            node_id: 中心节点ID
            max_depth: 最大深度（跳数）
            
        Returns:
            子图（KnowledgeGraph 实例）
        """
        if node_id not in self.graph.nodes:
            return KnowledgeGraph()
        
        subgraph = KnowledgeGraph()
        visited = set()
        queue = deque([(node_id, 0)])
        
        while queue:
            current_id, depth = queue.popleft()
            
            if current_id in visited or depth > max_depth:
                continue
            
            visited.add(current_id)
            
            # 添加节点
            if current_id in self.graph.nodes:
                subgraph.add_node(self.graph.nodes[current_id])
            
            # 添加关系
            for rel in self.graph.relations:
                if rel.source_id == current_id or rel.target_id == current_id:
                    subgraph.add_relation(rel)
                    
                    # 添加邻居到队列
                    neighbor_id = rel.target_id if rel.source_id == current_id else rel.source_id
                    if neighbor_id not in visited and depth < max_depth:
                        queue.append((neighbor_id, depth + 1))
        
        logger.info(f"提取子图: 中心={node_id}, 深度={max_depth}, 节点数={len(subgraph.nodes)}")
        return subgraph
    
    def query_related_concepts(self, node_id: str, max_depth: int = 2) -> List[Dict[str, Any]]:
        """
        查询与指定节点相关的所有概念
        
        Args:
            node_id: 节点ID
            max_depth: 最大深度
            
        Returns:
            相关概念列表（每个元素包含 concept, depth, path）
        """
        if node_id not in self.graph.nodes:
            return []
        
        results = []
        visited = set()
        queue = deque([(node_id, 0, [node_id])])
        
        while queue:
            current_id, depth, path = queue.popleft()
            
            if current_id in visited or depth > max_depth:
                continue
            
            visited.add(current_id)
            
            # 检查当前节点是否是概念
            current_node = self.graph.nodes.get(current_id)
            if current_node and current_node.node_type == "concept" and current_id != node_id:
                results.append({
                    "concept": current_node.title,
                    "node_id": current_id,
                    "depth": depth,
                    "path": path.copy()
                })
            
            # 探索邻居
            for rel in self.graph.relations:
                if rel.source_id == current_id or rel.target_id == current_id:
                    neighbor_id = rel.target_id if rel.source_id == current_id else rel.source_id
                    
                    if neighbor_id not in visited and depth < max_depth:
                        queue.append((neighbor_id, depth + 1, path + [neighbor_id]))
        
        return results
    
    def reason_over_graph(self, query: str) -> Dict[str, Any]:
        """
        基于知识图谱进行推理（基础版）
        
        Args:
            query: 查询问题
            
        Returns:
            推理结果（包含 answer, evidence, confidence）
        """
        # 简单推理：提取查询中的关键词，查找相关概念
        query_terms = set(re.findall(r"\w+", query.lower()))
        
        # 查找匹配的概念节点
        matched_concepts = []
        for node_id, node in self.graph.nodes.items():
            if node.node_type == "concept":
                concept_terms = set(re.findall(r"\w+", node.title.lower()))
                if query_terms & concept_terms:  # 有交集
                    matched_concepts.append(node)
        
        if not matched_concepts:
            return {
                "answer": "未找到相关概念",
                "evidence": [],
                "confidence": 0.0
            }
        
        # 提取证据（相关节点和关系）
        evidence = []
        for concept in matched_concepts[:5]:  # 限制数量
            subgraph = self.extract_subgraph(concept.node_id, max_depth=1)
            evidence.append({
                "concept": concept.title,
                "node_id": concept.node_id,
                "subgraph_nodes": len(subgraph.nodes),
                "subgraph_relations": len(subgraph.relations)
            })
        
        return {
            "answer": f"找到 {len(matched_concepts)} 个相关概念",
            "matched_concepts": [c.title for c in matched_concepts],
            "evidence": evidence,
            "confidence": min(0.9, len(matched_concepts) * 0.1)
        }
    
    # ============================================================
    # 辅助方法（从 V2 继承）
    # ============================================================
    
    def _find_parent_in_hierarchy(self, current_level: int, current_title: str) -> Optional[str]:
        """在层级表中查找父章节"""
        candidates = []
        
        for title, node_id in self._section_hierarchy.items():
            if title == current_title:
                continue
            
            # 获取该章节的层级
            parent_level = self._detect_heading_level_by_title(title)
            
            if parent_level < current_level:
                candidates.append((parent_level, node_id))
        
        if not candidates:
            return None
        
        # 返回层级最接近的那个
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]
    
    def _detect_heading_level_by_title(self, title: str) -> int:
        """根据标题查找层级"""
        for mapping in self.node_mappings:
            if mapping.title == title:
                chunk = mapping.chunk
                return self._detect_heading_level(chunk.section)
        return 0
    
    def _cleanup_deeper_levels(self, current_level: int, current_title: str) -> None:
        """清理更深层级（从层级表中移除）"""
        to_remove = []
        
        for title, node_id in self._section_hierarchy.items():
            if title == current_title:
                continue
            
            level = self._detect_heading_level_by_title(title)
            if level >= current_level:
                to_remove.append(title)
        
        for title in to_remove:
            del self._section_hierarchy[title]
    
    def _add_relation(self, source_id: str, relation_type: str, target_id: str, weight: float = 1.0) -> None:
        """添加关系"""
        relation = KnowledgeRelation(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            weight=weight
        )
        self.graph.add_relation(relation)
        logger.debug(f"添加关系: {source_id} -[{relation_type}]-> {target_id}")
    
    def _detect_heading_level(self, section: str) -> int:
        """检测标题层级（# 数量）"""
        if not section:
            return 0
        
        match = re.match(r"^(#+) ", section)
        if match:
            return len(match.group(1))
        
        return 0
    
    def _map_chunk_type_to_node_type(self, chunk: DocumentChunk) -> str:
        """映射 chunk_type 到 node_type"""
        chunk_type = chunk.chunk_type
        section = chunk.section
        level = self._detect_heading_level(section)
        
        if chunk_type == "text":
            if level == 1:
                return "chapter"
            elif level == 2:
                return "section"
            elif level >= 3:
                return "subsection"
            else:
                return "concept"
        elif chunk_type == "code":
            return "code_example"
        elif chunk_type == "api":
            return "api_interface"
        elif chunk_type == "example":
            return "example"
        else:
            return "generic"
    
    def _generate_chunk_id(self, chunk: DocumentChunk) -> str:
        """生成 chunk 的唯一 ID"""
        content_hash = hashlib.md5(chunk.content.encode()).hexdigest()[:8]
        return f"{chunk.chunk_type}_{content_hash}"
    
    # ============================================================
    # 查询接口（增强版，新增缓存）
    # ============================================================
    
    def get_chunk_order(self) -> List[str]:
        """获取分块顺序（node_id 列表）"""
        return self._chunk_order
    
    def get_chunk_by_index(self, index: int) -> Optional[KnowledgeNode]:
        """根据索引获取分块节点"""
        cache_key = f"chunk_by_index:{index}"
        
        if self._enable_cache and cache_key in self._cache:
            self._cache_hits += 1
            return self._cache[cache_key]
        
        self._cache_misses += 1
        result = None
        if 0 <= index < len(self._chunk_order):
            node_id = self._chunk_order[index]
            result = self.graph.nodes.get(node_id)
        
        if self._enable_cache:
            self._cache[cache_key] = result
        
        return result
    
    def get_parent_section(self, node_id: str) -> Optional[KnowledgeNode]:
        """获取父章节"""
        cache_key = f"parent_section:{node_id}"
        
        if self._enable_cache and cache_key in self._cache:
            self._cache_hits += 1
            return self._cache[cache_key]
        
        self._cache_misses += 1
        parent_id = self._section_parent.get(node_id)
        result = self.graph.nodes.get(parent_id) if parent_id else None
        
        if self._enable_cache:
            self._cache[cache_key] = result
        
        return result
    
    def get_children_sections(self, node_id: str) -> List[KnowledgeNode]:
        """获取子章节"""
        cache_key = f"children_sections:{node_id}"
        
        if self._enable_cache and cache_key in self._cache:
            self._cache_hits += 1
            return self._cache[cache_key]
        
        self._cache_misses += 1
        children = []
        for rel in self.graph.relations:
            if rel.relation_type == "part_of" and rel.target_id == node_id:
                child = self.graph.nodes.get(rel.source_id)
                if child:
                    children.append(child)
        
        if self._enable_cache:
            self._cache[cache_key] = children
        
        return children
    
    def get_next_chunk(self, node_id: str) -> Optional[KnowledgeNode]:
        """获取下一个分块"""
        for rel in self.graph.relations:
            if rel.relation_type == "next_chunk" and rel.source_id == node_id:
                return self.graph.nodes.get(rel.target_id)
        return None
    
    def get_prev_chunk(self, node_id: str) -> Optional[KnowledgeNode]:
        """获取前一个分块"""
        for rel in self.graph.relations:
            if rel.relation_type == "prev_chunk" and rel.source_id == node_id:
                return self.graph.nodes.get(rel.target_id)
        return None
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total if total > 0 else 0
        
        return {
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate": hit_rate,
            "cache_size": len(self._cache)
        }
    
    def clear_cache(self) -> None:
        """清空缓存"""
        self._cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
        logger.info("缓存已清空")
    
    # ============================================================
    # 导出功能（增强版）
    # ============================================================
    
    def get_graph(self) -> KnowledgeGraph:
        """获取知识图谱"""
        return self.graph
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计（Phase 3 新增）"""
        stats = self._performance_stats.copy()
        stats["cache_stats"] = self.get_cache_stats()
        return stats
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息（增强版）"""
        stats = self.graph.get_statistics()
        stats["domain"] = self.domain
        stats["node_mappings"] = len(self.node_mappings)
        stats["chunk_order_length"] = len(self._chunk_order)
        
        # 新增：关系类型统计
        relation_type_count = {}
        for rel in self.graph.relations:
            rel_type = rel.relation_type
            relation_type_count[rel_type] = relation_type_count.get(rel_type, 0) + 1
        stats["relation_types"] = relation_type_count
        
        # 新增：Phase 3 统计
        stats["entity_links"] = self._performance_stats["entity_links"]
        stats["cross_refs"] = self._performance_stats["cross_refs"]
        stats["cache_hit_rate"] = self.get_cache_stats()["hit_rate"]
        
        return stats
    
    def export_to_json(self, preserve_structure: bool = True) -> str:
        """
        导出为 JSON（增强版）
        
        Args:
            preserve_structure: 是否保留完整结构（包括 chunk_order）
        """
        data = {
            "version": "3.0.0",
            "nodes": [{
                "node_id": node.node_id,
                "title": node.title,
                "content": node.content,
                "node_type": node.node_type,
                "domain": node.domain,
                "properties": node.properties
            } for node in self.graph.nodes.values()],
            "relations": [{
                "relation_id": rel.relation_id,
                "source_id": rel.source_id,
                "target_id": rel.target_id,
                "relation_type": rel.relation_type,
                "weight": rel.weight
            } for rel in self.graph.relations]
        }
        
        if preserve_structure:
            data["metadata"] = {
                "chunk_order": self._chunk_order,
                "section_parent": self._section_parent,
                "domain": self.domain,
                "entity_index": self._entity_index,
                "document_nodes": self._document_nodes
            }
        
        return json.dumps(data, ensure_ascii=False, indent=2)
    
    def save_graph(self, file_path: str) -> None:
        """保存知识图谱到文件"""
        json_str = self.export_to_json(preserve_structure=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(json_str)
        logger.info(f"知识图谱已保存: {file_path}")
    
    def load_graph(self, file_path: str) -> KnowledgeGraph:
        """从文件加载知识图谱（增量更新支持）"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 加载节点
        for node_data in data.get("nodes", []):
            node = KnowledgeNode(
                node_id=node_data["node_id"],
                title=node_data["title"],
                content=node_data["content"],
                node_type=node_data["node_type"],
                domain=node_data["domain"],
                properties=node_data.get("properties", {})
            )
            self.graph.add_node(node)
        
        # 加载关系
        for rel_data in data.get("relations", []):
            rel = KnowledgeRelation(
                relation_id=rel_data["relation_id"],
                source_id=rel_data["source_id"],
                target_id=rel_data["target_id"],
                relation_type=rel_data["relation_type"],
                weight=rel_data.get("weight", 1.0)
            )
            self.graph.add_relation(rel)
        
        # 加载元数据
        metadata = data.get("metadata", {})
        if "chunk_order" in metadata:
            self._chunk_order = metadata["chunk_order"]
        if "section_parent" in metadata:
            self._section_parent = metadata["section_parent"]
        if "entity_index" in metadata:
            self._entity_index = metadata["entity_index"]
        if "document_nodes" in metadata:
            self._document_nodes = metadata["document_nodes"]
        
        logger.info(f"知识图谱已加载: {file_path}")
        return self.graph


# ============================================================
# 便捷函数
# ============================================================

def integrate_llm_wiki_to_graph_v3(chunks: List[DocumentChunk], domain: str = "llm_wiki", 
                                    enable_cache: bool = True) -> KnowledgeGraph:
    """
    便捷函数（Phase 3 高级版）：将 LLM Wiki 文档块集成到知识图谱
    
    Args:
        chunks: DocumentChunk 列表
        domain: 知识图谱域名
        enable_cache: 是否启用缓存
        
    Returns:
        KnowledgeGraph 实例
    """
    integrator = LLMWikiKnowledgeGraphIntegratorV3(domain=domain, enable_cache=enable_cache)
    return integrator.integrate_chunks(chunks)


def load_and_integrate_markdown_v3(file_path: str, domain: str = "llm_wiki", 
                                    enable_cache: bool = True) -> KnowledgeGraph:
    """
    便捷函数（Phase 3 高级版）：加载 Markdown 文件并集成到知识图谱
    
    Args:
        file_path: Markdown 文件路径
        domain: 知识图谱域名
        enable_cache: 是否启用缓存
        
    Returns:
        KnowledgeGraph 实例
    """
    from .parsers import LLMDocumentParser
    
    # 1. 解析 Markdown
    parser = LLMDocumentParser()
    chunks = parser.parse_markdown(file_path)
    
    if not chunks:
        logger.warning(f"未提取到任何块: {file_path}")
        return KnowledgeGraph()
    
    # 2. 集成到知识图谱（Phase 3 高级版）
    return integrate_llm_wiki_to_graph_v3(chunks, domain=domain, enable_cache=enable_cache)


def load_and_integrate_multiple_v3(file_paths: List[str], domain: str = "llm_wiki", 
                                    enable_cache: bool = True) -> KnowledgeGraph:
    """
    便捷函数（Phase 3 高级版）：加载多个 Markdown 文件并集成到知识图谱
    
    Args:
        file_paths: Markdown 文件路径列表
        domain: 知识图谱域名
        enable_cache: 是否启用缓存
        
    Returns:
        KnowledgeGraph 实例（包含所有文档）
    """
    from .parsers import LLMDocumentParser
    
    parser = LLMDocumentParser()
    all_chunks = []
    
    for file_path in file_paths:
        chunks = parser.parse_markdown(file_path)
        if chunks:
            all_chunks.extend(chunks)
            logger.info(f"已加载: {file_path} ({len(chunks)} 个块)")
        else:
            logger.warning(f"未提取到任何块: {file_path}")
    
    if not all_chunks:
        logger.warning("未提取到任何块")
        return KnowledgeGraph()
    
    # 集成到知识图谱
    return integrate_llm_wiki_to_graph_v3(all_chunks, domain=domain, enable_cache=enable_cache)
