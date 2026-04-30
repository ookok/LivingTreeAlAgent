"""
LLM Wiki 模块 - KnowledgeGraph 集成器（优化版）
================================================

Phase 2+ (优化): 保留 LLM Wiki 完整分块结构

改进点：
1. ✅ 保留原始分块顺序（chunk_index）
2. ✅ 建立分块先后顺序关系（next_chunk / prev_chunk）
3. ✅ 更精确的章节层级（使用 parent_section 字段）
4. ✅ 增强的元数据（完整保留 DocumentChunk 信息）
5. ✅ 支持分块类型统计和查询

作者: LivingTreeAI Team
日期: 2026-04-29
版本: 2.1.0 (Phase 2+ 优化)
"""

import re
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

from loguru import logger

# 导入 Phase 1 的数据模型
from .models import DocumentChunk

# 导入 KnowledgeGraph 核心类
from business.knowledge_graph.graph import (
    KnowledgeGraph,
    KnowledgeNode,
    KnowledgeRelation
)


@dataclass
class WikiNodeMapping:
    """Wiki 节点映射（增强版）"""
    chunk_id: str
    node_id: str
    title: str
    node_type: str
    chunk: DocumentChunk
    parent_node_id: Optional[str] = None
    chunk_index: int = 0


class LLMWikiKnowledgeGraphIntegratorV2:
    """
    LLM Wiki → KnowledgeGraph 集成器（优化版）
    
    改进：
    1. 保留完整分块结构
    2. 建立分块顺序关系
    3. 精确章节层级
    4. 增强元数据
    """
    
    def __init__(self, domain: str = "llm_wiki"):
        """初始化集成器"""
        self.domain = domain
        self.graph = KnowledgeGraph()
        self.node_mappings: List[WikiNodeMapping] = []
        
        # 章节层级跟踪（增强版：记录完整路径）
        self._section_hierarchy: Dict[str, str] = {}  # title -> node_id
        self._section_parent: Dict[str, Optional[str]] = {}  # node_id -> parent_node_id
        
        # 分块顺序跟踪
        self._last_chunk_node_id: Optional[str] = None
        
        # 统计信息
        self._chunk_order: List[str] = []  # node_id 的顺序列表
        
        logger.info(f"LLMWikiKnowledgeGraphIntegratorV2 初始化完成 (domain={domain})")
    
    def integrate_chunks(self, chunks: List[DocumentChunk]) -> KnowledgeGraph:
        """
        将 DocumentChunk 列表集成到 KnowledgeGraph（优化版）
        
        Args:
            chunks: Phase 1 解析的文档块列表
            
        Returns:
            KnowledgeGraph 实例
        """
        logger.info(f"开始集成 {len(chunks)} 个文档块到知识图谱（优化模式）")
        
        # 0. 重置状态
        self._reset_state()
        
        # 1. 按 source 分组
        chunks_by_source = self._group_by_source(chunks)
        
        for source, source_chunks in chunks_by_source.items():
            logger.info(f"处理文档: {source} ({len(source_chunks)} 个块)")
            
            # 2. 为每个块创建节点（保留顺序）
            for index, chunk in enumerate(source_chunks):
                node = self._create_node_with_order(chunk, index)
                
                # 3. 建立章节层级关系
                self._establish_hierarchy(node, chunk)
                
                # 4. 建立分块顺序关系
                self._establish_chunk_order(node.node_id)
                
                # 5. 提取概念
                self._extract_concepts(chunk.content, node.node_id)
        
        # 6. 建立跨文档关系（可选）
        self._link_cross_references()
        
        logger.info(f"集成完成: {len(self.graph.nodes)} 个节点, {len(self.graph.relations)} 个关系")
        return self.graph
    
    def _reset_state(self) -> None:
        """重置内部状态"""
        self._section_hierarchy = {}
        self._section_parent = {}
        self._last_chunk_node_id = None
        self._chunk_order = []
    
    def _group_by_source(self, chunks: List[DocumentChunk]) -> Dict[str, List[DocumentChunk]]:
        """按 source 分组"""
        groups = {}
        for chunk in chunks:
            source = chunk.source or "unknown"
            if source not in groups:
                groups[source] = []
            groups[source].append(chunk)
        return groups
    
    def _create_node_with_order(self, chunk: DocumentChunk, index: int) -> KnowledgeNode:
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
                "full_content": chunk.content  # 完整内容
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
            chunk_index=index
        )
        self.node_mappings.append(mapping)
        
        logger.debug(f"创建节点: {title} ({node_type}) [index={index}]")
        return node
    
    def _establish_hierarchy(self, node: KnowledgeNode, chunk: DocumentChunk) -> None:
        """建立章节层级关系（增强版）"""
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
    
    def _extract_concepts(self, text: str, context_node_id: str) -> None:
        """从文本中提取概念（增强版：更多模式）"""
        # 模式 1: **加粗术语**
        bold_terms = re.findall(r"\*\*(.+?)\*\*", text)
        
        # 模式 2: `代码术语`
        code_terms = re.findall(r"`([^`]+)`", text)
        
        # 模式 3: 标题式术语（大写字母开头 + 冒号）
        title_terms = re.findall(r"^([A-Z][a-zA-Z\s]{2,}):", text, re.MULTILINE)
        
        # 模式 4: 定义式术语（术语 + 是/是指）
        definition_terms = re.findall(r"^(.+?)\s+(?:是|是指|refers to|is defined as)", text, re.MULTILINE | re.IGNORECASE)
        
        all_terms = set(bold_terms + code_terms + title_terms + definition_terms)
        
        for term in all_terms:
            if len(term) < 3 or len(term) > 50:
                continue
            
            # 创建概念节点
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
            
            # 建立关系
            self._add_relation(context_node_id, "mentions", concept_node.node_id, weight=0.8)
    
    def _find_parent_in_hierarchy(self, current_level: int, current_title: str) -> Optional[str]:
        """在层级表中查找父章节"""
        # 遍历层级表，找到层级小于当前层级的最近章节
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
        """映射 chunk_type 到 node_type（增强版）"""
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
        import hashlib
        content_hash = hashlib.md5(chunk.content.encode()).hexdigest()[:8]
        return f"{chunk.chunk_type}_{content_hash}"
    
    def _link_cross_references(self) -> None:
        """建立跨文档引用关系（可选，高级功能）"""
        # TODO: 实现跨文档引用检测
        pass
    
    # ============================================================
    # 查询接口（新增）
    # ============================================================
    
    def get_chunk_order(self) -> List[str]:
        """获取分块顺序（node_id 列表）"""
        return self._chunk_order
    
    def get_chunk_by_index(self, index: int) -> Optional[KnowledgeNode]:
        """根据索引获取分块节点"""
        if 0 <= index < len(self._chunk_order):
            node_id = self._chunk_order[index]
            return self.graph.nodes.get(node_id)
        return None
    
    def get_parent_section(self, node_id: str) -> Optional[KnowledgeNode]:
        """获取父章节"""
        parent_id = self._section_parent.get(node_id)
        if parent_id:
            return self.graph.nodes.get(parent_id)
        return None
    
    def get_children_sections(self, node_id: str) -> List[KnowledgeNode]:
        """获取子章节"""
        children = []
        for rel in self.graph.relations:
            if rel.relation_type == "part_of" and rel.target_id == node_id:
                child = self.graph.nodes.get(rel.source_id)
                if child:
                    children.append(child)
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
    
    # ============================================================
    # 导出功能（增强版）
    # ============================================================
    
    def get_graph(self) -> KnowledgeGraph:
        """获取知识图谱"""
        return self.graph
    
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
        
        return stats
    
    def export_to_json(self, preserve_structure: bool = True) -> str:
        """
        导出为 JSON（增强版）
        
        Args:
            preserve_structure: 是否保留完整结构（包括 chunk_order）
        """
        import json
        
        data = {
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
                "domain": self.domain
            }
        
        return json.dumps(data, ensure_ascii=False, indent=2)
    
    def save_graph(self, file_path: str) -> None:
        """保存知识图谱到文件"""
        json_str = self.export_to_json(preserve_structure=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(json_str)
        logger.info(f"知识图谱已保存: {file_path}")


# ============================================================
# 便捷函数
# ============================================================

def integrate_llm_wiki_to_graph_v2(chunks: List[DocumentChunk], domain: str = "llm_wiki") -> KnowledgeGraph:
    """
    便捷函数（优化版）：将 LLM Wiki 文档块集成到知识图谱
    
    Args:
        chunks: DocumentChunk 列表
        domain: 知识图谱域名
        
    Returns:
        KnowledgeGraph 实例
    """
    integrator = LLMWikiKnowledgeGraphIntegratorV2(domain=domain)
    return integrator.integrate_chunks(chunks)


def load_and_integrate_markdown_v2(file_path: str, domain: str = "llm_wiki") -> KnowledgeGraph:
    """
    便捷函数（优化版）：加载 Markdown 文件并集成到知识图谱
    
    Args:
        file_path: Markdown 文件路径
        domain: 知识图谱域名
        
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
    
    # 2. 集成到知识图谱（优化版）
    return integrate_llm_wiki_to_graph_v2(chunks, domain=domain)


