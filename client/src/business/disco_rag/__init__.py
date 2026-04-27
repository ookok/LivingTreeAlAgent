"""
Discourse-Aware RAG
话语感知的检索增强生成

借鉴论文: Disco-RAG: Discourse-Aware Retrieval-Augmented Generation
https://arxiv.org/abs/2601.04377

核心思想：
1. 块内话语树 (Intra-chunk Discourse Trees)
2. 块间修辞图 (Inter-chunk Rhetorical Graphs)
3. 规划蓝图 (Planning Blueprint)
"""

import re
import json
import sqlite3
import hashlib
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class DiscourseRelation(Enum):
    """话语关系类型"""
    # 块内关系
    PARENT = "parent"           # 父节点
    CHILD = "child"            # 子节点
    SIBLING = "sibling"        # 兄弟节点

    # 块间修辞关系
    ELABORATION = "elaboration"      # 详细阐述
    CONTRAST = "contrast"            # 对比
    CAUSE = "cause"                  # 因果
    SEQUENCE = "sequence"            # 顺序
    EXAMPLE = "example"              # 示例
    SUMMARY = "summary"              # 总结


@dataclass
class DiscourseNode:
    """话语节点"""
    id: str = ""
    content: str = ""
    depth: int = 0           # 层级深度
    node_type: str = "text"   # text/heading/list
    parent_id: str = ""       # 父节点ID
    children_ids: List[str] = field(default_factory=list)
    relations: List[Dict[str, str]] = field(default_factory=list)  # 跨块关系
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Chunk:
    """文档块"""
    id: str = ""
    content: str = ""
    position: int = 0        # 文档中的位置
    discourse_tree: Optional[DiscourseNode] = None
    incoming_relations: List[Dict[str, str]] = field(default_factory=list)
    outgoing_relations: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class PlanningBlueprint:
    """规划蓝图"""
    query: str = ""
    relevant_chunks: List[Chunk] = field(default_factory=list)
    generation_order: List[str] = field(default_factory=list)  # chunk IDs
    key_points: List[str] = field(default_factory=list)       # 关键点
    summary: str = ""


class DiscourseTreeBuilder:
    """构建块内话语树"""

    # 话语标记词
    DISCOURSE_MARKERS = {
        "elaboration": ["具体来说", "例如", "比如", "尤其是", "特别是", "首先", "其次", "最后"],
        "contrast": ["然而", "但是", "不过", "然而", "相比之下", "另一方面"],
        "cause": ["因为", "由于", "所以", "因此", "导致", "造成"],
        "sequence": ["首先", "接着", "然后", "最后", "最终", "总之"],
        "example": ["比如", "例如", "以", "像", "如"],
        "summary": ["总之", "综上所述", "总的来说", "简而言之", "概括来说"],
    }

    @classmethod
    def build_tree(cls, text: str, chunk_id: str) -> DiscourseNode:
        """
        从文本构建话语树

        简化实现：基于句子和话语标记构建层级结构
        """
        sentences = cls._split_sentences(text)
        root = DiscourseNode(
            id=f"{chunk_id}_root",
            content=text,
            depth=0,
            node_type="root"
        )

        if len(sentences) <= 1:
            return root

        # 构建树结构
        current_depth = 0
        nodes = [root]

        for sentence in sentences:
            if not sentence.strip():
                continue

            # 检测话语关系
            relation = cls._detect_relation(sentence)

            # 创建节点
            node = DiscourseNode(
                id=f"{chunk_id}_{len(nodes)}",
                content=sentence,
                depth=current_depth + 1,
                node_type="text",
                relations=[{"type": relation, "marker": cls._get_marker(sentence)}]
            )

            # 找到合适的父节点
            parent = cls._find_parent(nodes, node.depth)
            if parent:
                node.parent_id = parent.id
                parent.children_ids.append(node.id)

            nodes.append(node)

        return root

    @classmethod
    def _split_sentences(cls, text: str) -> List[str]:
        """分割句子"""
        # 按句号、问号、感叹号分割
        sentences = re.split(r'[。！？；\n]+', text)
        return [s.strip() for s in sentences if s.strip()]

    @classmethod
    def _detect_relation(cls, sentence: str) -> str:
        """检测话语关系"""
        sentence_lower = sentence.lower()
        for rel_type, markers in cls.DISCOURSE_MARKERS.items():
            for marker in markers:
                if marker in sentence_lower:
                    return rel_type
        return "elaboration"  # 默认详细阐述

    @classmethod
    def _get_marker(cls, sentence: str) -> str:
        """获取话语标记词"""
        for markers in cls.DISCOURSE_MARKERS.values():
            for marker in markers:
                if marker in sentence:
                    return marker
        return ""


class InterChunkGraphBuilder:
    """构建块间修辞图"""

    def __init__(self):
        self.chunks: Dict[str, Chunk] = {}
        self.graph: Dict[str, List[Tuple[str, str]]] = {}  # chunk_id -> [(target_id, relation)]

    def add_chunk(self, chunk: Chunk):
        """添加块"""
        self.chunks[chunk.id] = chunk

    def build_graph(self) -> Dict[str, List[Tuple[str, str]]]:
        """
        构建块间关系图

        基于：
        1. 位置关系（相邻、连续）
        2. 词汇共现
        3. 话语过渡
        """
        chunk_ids = sorted(self.chunks.keys(), key=lambda x: self.chunks[x].position)

        for i, chunk_id in enumerate(chunk_ids):
            chunk = self.chunks[chunk_id]

            # 1. 顺序关系
            if i > 0:
                prev_id = chunk_ids[i - 1]
                chunk.outgoing_relations.append({
                    "target": prev_id,
                    "type": DiscourseRelation.SEQUENCE.value,
                    "direction": "prev"
                })
                self.chunks[prev_id].incoming_relations.append({
                    "source": chunk_id,
                    "type": DiscourseRelation.SEQUENCE.value,
                    "direction": "next"
                })

            # 2. 词汇共现关系
            for j, other_id in enumerate(chunk_ids[i + 1:], i + 1):
                if self._has_word_overlap(chunk.content, self.chunks[other_id].content):
                    chunk.outgoing_relations.append({
                        "target": other_id,
                        "type": DiscourseRelation.ELABORATION.value,
                        "strength": 0.5
                    })

            # 更新图
            self.graph[chunk_id] = [
                (rel["target"], rel["type"])
                for rel in chunk.outgoing_relations
            ]

        return self.graph

    def _has_word_overlap(self, text1: str, text2: str, threshold: float = 0.2) -> bool:
        """检测词汇重叠"""
        words1 = set(self._extract_words(text1))
        words2 = set(self._extract_words(text2))

        if not words1 or not words2:
            return False

        overlap = len(words1 & words2)
        jaccard = overlap / len(words1 | words2)

        return jaccard >= threshold

    def _extract_words(self, text: str) -> List[str]:
        """提取词汇"""
        # 提取中英文词
        chinese = re.findall(r'[\u4e00-\u9fa5]+', text)
        english = re.findall(r'[a-zA-Z]+', text)
        return chinese + english


class PlanningBlueprintGenerator:
    """生成规划蓝图"""

    def __init__(self):
        self.graph_builder = InterChunkGraphBuilder()

    def generate(
        self,
        query: str,
        chunks: List[Chunk],
        max_chunks: int = 5
    ) -> PlanningBlueprint:
        """
        生成规划蓝图

        1. 选择相关块
        2. 确定生成顺序
        3. 提取关键点
        """
        if not chunks:
            return PlanningBlueprint(query=query)

        # 添加到图中
        for chunk in chunks:
            self.graph_builder.add_chunk(chunk)

        # 构建图
        self.graph_builder.build_graph()

        # 选择相关块
        relevant = self._select_relevant_chunks(query, chunks, max_chunks)

        # 确定生成顺序
        order = self._topological_sort(relevant)

        # 提取关键点
        key_points = self._extract_key_points(query, relevant)

        # 生成摘要
        summary = self._generate_summary(query, relevant)

        return PlanningBlueprint(
            query=query,
            relevant_chunks=relevant,
            generation_order=order,
            key_points=key_points,
            summary=summary
        )

    def _select_relevant_chunks(
        self,
        query: str,
        chunks: List[Chunk],
        max_chunks: int
    ) -> List[Chunk]:
        """选择相关块"""
        query_words = set(self._extract_words(query.lower()))

        scored = []
        for chunk in chunks:
            chunk_words = set(self._extract_words(chunk.content.lower()))
            overlap = len(query_words & chunk_words)
            score = overlap / max(len(query_words), 1)
            scored.append((chunk, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [c for c, _ in scored[:max_chunks]]

    def _topological_sort(self, chunks: List[Chunk]) -> List[str]:
        """拓扑排序确定生成顺序"""
        # 简化：按位置顺序
        chunk_dict = {c.id: c for c in chunks}
        sorted_chunks = sorted(chunks, key=lambda x: x.position)

        return [c.id for c in sorted_chunks]

    def _extract_key_points(self, query: str, chunks: List[Chunk]) -> List[str]:
        """提取关键点"""
        key_points = []

        for chunk in chunks:
            # 取每块的前 N 个字符作为摘要
            summary = chunk.content[:100].strip()
            if summary:
                key_points.append(summary + "..." if len(chunk.content) > 100 else summary)

        return key_points

    def _generate_summary(self, query: str, chunks: List[Chunk]) -> str:
        """生成摘要"""
        summaries = []
        for chunk in chunks:
            # 取第一句
            first_sentence = chunk.content.split('。')[0].split('！')[0].split('？')[0]
            if first_sentence:
                summaries.append(first_sentence)

        return " ".join(summaries[:3])

    def _extract_words(self, text: str) -> List[str]:
        """提取词汇"""
        chinese = re.findall(r'[\u4e00-\u9fa5]+', text)
        english = re.findall(r'[a-zA-Z]+', text)
        return chinese + english


class DiscourseRAG:
    """
    话语感知 RAG 系统

    核心流程：
    1. 文档分块
    2. 块内话语树构建
    3. 块间修辞图构建
    4. 规划蓝图生成
    5. 结构化生成
    """

    def __init__(self, db_path: str | Path = None):
        from client.src.business.config import get_config_dir

        if db_path is None:
            db_path = get_config_dir() / "disco_rag.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

        self.tree_builder = DiscourseTreeBuilder()
        self.graph_builder = InterChunkGraphBuilder()
        self.blueprint_generator = PlanningBlueprintGenerator()

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    position INTEGER DEFAULT 0,
                    discourse_tree TEXT DEFAULT '{}',
                    created_at REAL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS relations (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    strength REAL DEFAULT 0.5,
                    created_at REAL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    title TEXT DEFAULT '',
                    chunks TEXT DEFAULT '[]',
                    created_at REAL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_chunks_position ON chunks(position);
                CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_id);
            """)
            conn.commit()
        finally:
            conn.close()

    def add_document(self, doc_id: str, title: str, content: str, chunk_size: int = 500) -> List[str]:
        """
        添加文档

        Args:
            doc_id: 文档ID
            title: 文档标题
            content: 文档内容
            chunk_size: 块大小

        Returns:
            块ID列表
        """
        # 分块
        chunks = self._split_into_chunks(content, chunk_size)

        chunk_ids = []
        for i, chunk_text in enumerate(chunks):
            chunk_id = f"{doc_id}_chunk_{i}"

            # 构建话语树
            tree = self.tree_builder.build_tree(chunk_text, chunk_id)

            # 保存
            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO chunks
                    (id, content, position, discourse_tree, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (chunk_id, chunk_text, i, json.dumps({
                    "id": tree.id,
                    "content": tree.content,
                    "depth": tree.depth,
                    "children": tree.children_ids
                }), 0))
                conn.commit()
            finally:
                conn.close()

            chunk_ids.append(chunk_id)

        # 保存文档
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("""
                INSERT OR REPLACE INTO documents (id, title, chunks, created_at)
                VALUES (?, ?, ?, ?)
            """, (doc_id, title, json.dumps(chunk_ids), 0))
            conn.commit()
        finally:
            conn.close()

        return chunk_ids

    def _split_into_chunks(self, text: str, chunk_size: int) -> List[str]:
        """将文本分割成块"""
        # 按段落分割
        paragraphs = re.split(r'\n+', text)

        chunks = []
        current = ""

        for para in paragraphs:
            if len(current) + len(para) <= chunk_size:
                current += para + "\n"
            else:
                if current.strip():
                    chunks.append(current.strip())
                current = para + "\n"

        if current.strip():
            chunks.append(current.strip())

        return chunks

    def retrieve_and_plan(self, query: str, doc_id: str = None, max_chunks: int = 5) -> PlanningBlueprint:
        """
        检索并生成规划蓝图

        等同于 Disco-RAG 的 retrieve + plan
        """
        # 获取块
        if doc_id:
            chunks = self._get_chunks_by_doc(doc_id)
        else:
            chunks = self._get_all_chunks()

        # 构建块对象
        chunk_objs = []
        for row in chunks:
            chunk = Chunk(
                id=row[0],
                content=row[1],
                position=row[2]
            )
            # 解析话语树
            tree_json = json.loads(row[3] or "{}")
            if tree_json:
                chunk.discourse_tree = DiscourseNode(
                    id=tree_json.get("id", ""),
                    content=tree_json.get("content", ""),
                    depth=tree_json.get("depth", 0)
                )
            chunk_objs.append(chunk)

        # 生成规划蓝图
        return self.blueprint_generator.generate(query, chunk_objs, max_chunks)

    def _get_chunks_by_doc(self, doc_id: str) -> List[Tuple]:
        """获取文档块"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            # 先获取文档的块ID列表
            doc_row = conn.execute(
                "SELECT chunks FROM documents WHERE id = ?", (doc_id,)
            ).fetchone()

            if not doc_row:
                return []

            chunk_ids = json.loads(doc_row[0])

            # 获取块内容
            placeholders = ','.join('?' * len(chunk_ids))
            rows = conn.execute(f"""
                SELECT * FROM chunks
                WHERE id IN ({placeholders})
                ORDER BY position
            """, chunk_ids).fetchall()

            return rows
        finally:
            conn.close()

    def _get_all_chunks(self) -> List[Tuple]:
        """获取所有块"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            return conn.execute(
                "SELECT * FROM chunks ORDER BY position"
            ).fetchall()
        finally:
            conn.close()

    def generate_with_blueprint(self, blueprint: PlanningBlueprint) -> str:
        """
        基于规划蓝图生成答案

        结构化生成，而非简单拼接
        """
        if not blueprint.relevant_chunks:
            return "未找到相关信息。"

        parts = []

        # 按生成顺序处理
        for chunk_id in blueprint.generation_order:
            chunk = next((c for c in blueprint.relevant_chunks if c.id == chunk_id), None)
            if not chunk:
                continue

            # 添加话语标记
            relations = chunk.discourse_tree.relations if chunk.discourse_tree else []
            if relations:
                rel_type = relations[0].get("type", "elaboration")
                marker = relations[0].get("marker", "")

                if marker:
                    parts.append(f"{marker}{chunk.content}")
                else:
                    parts.append(chunk.content)
            else:
                parts.append(chunk.content)

        # 添加总结
        if blueprint.summary:
            parts.append(f"\n【总结】{blueprint.summary}")

        return "\n".join(parts)


# 单例
_disco_rag: Optional[DiscourseRAG] = None


def get_disco_rag() -> DiscourseRAG:
    """获取 Discourse RAG 单例"""
    global _disco_rag
    if _disco_rag is None:
        _disco_rag = DiscourseRAG()
    return _disco_rag
