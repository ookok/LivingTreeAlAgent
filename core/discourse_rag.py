#!/usr/bin/env python3
"""
RAG 增强模块 - Discourse-Aware RAG
实现块内话语树、块间修辞图、规划蓝图生成
"""

import re
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from core.logger import get_logger
logger = get_logger('discourse_rag')



class RhetoricalRelation(Enum):
    """修辞关系"""
    SUPPORT = "support"         # 支持
    ELABORATION = "elaboration"  # 详细说明
    EXAMPLE = "example"         # 举例
    CONTRAST = "contrast"       # 对比
    CAUSE = "cause"             # 原因
    CONSEQUENCE = "consequence"  # 结果
    SUMMARY = "summary"          # 总结
    SEQUENCE = "sequence"       # 序列


@dataclass
class TextChunk:
    """文本块"""
    chunk_id: str
    content: str
    position: int
    discourse_tree: Dict[str, Any] = field(default_factory=dict)
    relations: List[Tuple[str, RhetoricalRelation]] = field(default_factory=list)
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalResult:
    """检索结果"""
    chunk: TextChunk
    score: float
    position_weight: float
    coherence_score: float
    final_score: float


class DiscourseAwareRAG:
    """
    Discourse-Aware RAG

    特性:
    1. 块内话语树构建
    2. 块间修辞关系图
    3. 结构化规划蓝图生成
    4. 多跳推理增强
    """

    def __init__(self):
        self._chunks: Dict[str, TextChunk] = {}
        self._rhetorical_graph: Dict[str, Dict[str, RhetoricalRelation]] = defaultdict(dict)
        self._next_chunk_id = 1
        self._embedding_func: Optional[Callable[[str], List[float]]] = None

    def set_embedding_func(self, func: Callable[[str], List[float]]):
        """设置嵌入函数"""
        self._embedding_func = func

    def add_document(self, text: str, metadata: Dict[str, Any] = None) -> List[str]:
        """
        添加文档

        Args:
            text: 文档文本
            metadata: 元数据

        Returns:
            chunk_ids: 块 ID 列表
        """
        chunks = self._split_into_chunks(text)
        chunk_ids = []

        for i, chunk_content in enumerate(chunks):
            chunk_id = f"chunk_{self._next_chunk_id:06d}"
            self._next_chunk_id += 1

            discourse_tree = self._build_discourse_tree(chunk_content)

            chunk = TextChunk(
                chunk_id=chunk_id,
                content=chunk_content,
                position=i,
                discourse_tree=discourse_tree,
                metadata=metadata or {},
            )

            if self._embedding_func:
                chunk.embedding = self._embedding_func(chunk_content)

            self._chunks[chunk_id] = chunk
            chunk_ids.append(chunk_id)

        self._build_rhetorical_graph(chunk_ids)

        return chunk_ids

    def _split_into_chunks(self, text: str, chunk_size: int = 200) -> List[str]:
        """将文本分割成块"""
        sentences = re.split(r"[。！？.!?\n]+", text)
        chunks = []
        current_chunk = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            if len(current_chunk) + len(sentence) <= chunk_size:
                current_chunk += sentence + "。"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + "。"

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks if chunks else [text]

    def _build_discourse_tree(self, text: str) -> Dict[str, Any]:
        """
        构建话语树

        分析文本内部的话语结构
        """
        tree = {
            "root": {"type": "paragraph", "text": text[:50]},
            "nodes": [],
            "edges": [],
        }

        words = text.split()
        if not words:
            return tree

        if len(words) <= 5:
            tree["nodes"].append({"id": "n1", "type": "sentence", "text": text})
        else:
            tree["nodes"].append({"id": "n1", "type": "clause", "text": " ".join(words[:len(words)//2])})
            tree["nodes"].append({"id": "n2", "type": "clause", "text": " ".join(words[len(words)//2:])})
            tree["edges"].append({"from": "root", "to": "n1"})
            tree["edges"].append({"from": "root", "to": "n2"})

        return tree

    def _build_rhetorical_graph(self, chunk_ids: List[str]):
        """构建块间修辞关系图"""
        for i in range(len(chunk_ids) - 1):
            current = self._chunks[chunk_ids[i]]
            next_chunk = self._chunks[chunk_ids[i + 1]]

            relation = self._infer_rhetorical_relation(current.content, next_chunk.content)

            self._rhetorical_graph[chunk_ids[i]][chunk_ids[i + 1]] = relation
            current.relations.append((chunk_ids[i + 1], relation))

    def _infer_rhetorical_relation(self, text1: str, text2: str) -> RhetoricalRelation:
        """推断两个文本块之间的修辞关系"""
        text1_lower = text1.lower()
        text2_lower = text2.lower()

        if any(word in text2_lower for word in ["例如", "比如", "比方", "example"]):
            return RhetoricalRelation.EXAMPLE
        elif any(word in text2_lower for word in ["因为", "由于", "所以", "因此", "原因"]):
            return RhetoricalRelation.CAUSE
        elif any(word in text2_lower for word in ["但是", "然而", "不过", "可是", "然而", "相反"]):
            return RhetoricalRelation.CONTRAST
        elif any(word in text2_lower for word in ["首先", "其次", "然后", "最后", "第一", "第二"]):
            return RhetoricalRelation.SEQUENCE
        elif any(word in text2_lower for word in ["总之", "总而言之", "总结", "综上所述"]):
            return RhetoricalRelation.SUMMARY
        elif any(word in text2_lower for word in ["具体来说", "详细", "进一步", "此外"]):
            return RhetoricalRelation.ELABORATION
        elif len(text2) > len(text1) * 0.8:
            return RhetoricalRelation.SUPPORT
        else:
            return RhetoricalRelation.ELABORATION

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        use_rhetorical: bool = True,
    ) -> List[RetrievalResult]:
        """
        检索增强

        Args:
            query: 查询文本
            top_k: 返回数量
            use_rhetorical: 是否使用修辞关系

        Returns:
            检索结果
        """
        if not self._embedding_func:
            return self._basic_retrieve(query, top_k)

        query_embedding = self._embedding_func(query)
        results = []

        for chunk in self._chunks.values():
            if not chunk.embedding:
                continue

            similarity = self._cosine_similarity(query_embedding, chunk.embedding)
            position_weight = self._calculate_position_weight(chunk.position)
            coherence_score = 1.0

            if use_rhetorical and chunk.relations:
                coherence_score = self._calculate_coherence(chunk)

            final_score = (
                similarity * 0.6 +
                position_weight * 0.2 +
                coherence_score * 0.2
            )

            results.append(RetrievalResult(
                chunk=chunk,
                score=similarity,
                position_weight=position_weight,
                coherence_score=coherence_score,
                final_score=final_score,
            ))

        results.sort(key=lambda x: x.final_score, reverse=True)
        return results[:top_k]

    def _basic_retrieve(self, query: str, top_k: int) -> List[RetrievalResult]:
        """基础检索"""
        query_lower = query.lower()
        results = []

        for chunk in self._chunks.values():
            content_lower = chunk.content.lower()
            score = sum(1 for word in query_lower.split() if word in content_lower)
            score = min(score / max(len(query_lower.split()), 1), 1.0)

            position_weight = self._calculate_position_weight(chunk.position)

            results.append(RetrievalResult(
                chunk=chunk,
                score=score,
                position_weight=position_weight,
                coherence_score=1.0,
                final_score=score * 0.8 + position_weight * 0.2,
            ))

        results.sort(key=lambda x: x.final_score, reverse=True)
        return results[:top_k]

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """计算余弦相似度"""
        if not a or not b:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def _calculate_position_weight(self, position: int) -> float:
        """计算位置权重（前部内容更重要）"""
        return 1.0 / (1.0 + 0.1 * position)

    def _calculate_coherence(self, chunk: TextChunk) -> float:
        """计算连贯性分数"""
        if not chunk.relations:
            return 0.5

        coherence_scores = []
        for target_id, relation in chunk.relations:
            if relation == RhetoricalRelation.SEQUENCE:
                coherence_scores.append(1.0)
            elif relation == RhetoricalRelation.SUPPORT:
                coherence_scores.append(0.9)
            elif relation == RhetoricalRelation.ELABORATION:
                coherence_scores.append(0.8)
            elif relation == RhetoricalRelation.CONTRAST:
                coherence_scores.append(0.6)
            else:
                coherence_scores.append(0.7)

        return sum(coherence_scores) / len(coherence_scores) if coherence_scores else 0.5

    def generate_blueprint_info(
        self,
        query: str,
        retrieval_results: List[RetrievalResult],
    ) -> Dict[str, Any]:
        """
        生成结构化规划蓝图

        Args:
            query: 查询
            retrieval_results: 检索结果

        Returns:
            规划蓝图
        """
        blueprint = {
            "query": query,
            "sections": [],
            "reasoning_chain": [],
            "answer_structure": "",
        }

        if not retrieval_results:
            return blueprint

        sections = []
        reasoning = []

        for i, result in enumerate(retrieval_results[:3]):
            chunk = result.chunk
            section = {
                "order": i + 1,
                "content": chunk.content,
                "source": chunk.chunk_id,
                "relevance": result.final_score,
                "relation": None,
            }

            if chunk.relations:
                section["relation"] = chunk.relations[0][1].value

            sections.append(section)
            reasoning.append(f"{i+1}. {chunk.content[:50]}...")

        blueprint["sections"] = sections
        blueprint["reasoning_chain"] = reasoning
        blueprint["answer_structure"] = self._generate_structure_description(sections)

        return blueprint

    def _generate_structure_description(self, sections: List[Dict]) -> str:
        """生成结构描述"""
        if not sections:
            return "直接回答问题"

        structure = "首先" if len(sections) > 1 else ""

        for i, section in enumerate(sections):
            relation = section.get("relation")
            if relation == RhetoricalRelation.SEQUENCE.value:
                structure += f"{'然后' if i > 0 else ''}说明第{i+1}点；"
            elif relation == RhetoricalRelation.ELABORATION.value:
                structure += f"{'接着' if i > 0 else ''}详细阐述；"
            elif relation == RhetoricalRelation.SUPPORT.value:
                structure += f"{'其次' if i > 0 else ''}提供支持证据；"
            elif relation == RhetoricalRelation.SUMMARY.value:
                structure += "最后进行总结"
            else:
                structure += f"{'此外' if i > 0 else ''}补充说明"

        return structure

    def multi_hop_reasoning(
        self,
        query: str,
        hops: int = 2,
    ) -> Dict[str, Any]:
        """
        多跳推理

        Args:
            query: 查询
            hops: 跳数

        Returns:
            推理结果
        """
        results = self.retrieve(query, top_k=5, use_rhetorical=True)

        if hops <= 1 or not results:
            return {
                "query": query,
                "hops": 1,
                "reasoning": [r.chunk.content for r in results],
                "final_answer": results[0].chunk.content if results else None,
            }

        reasoning_chain = []
        current_chunks = {r.chunk.chunk_id for r in results[:2]}

        for hop in range(1, hops):
            next_results = []
            for chunk_id in current_chunks:
                chunk = self._chunks.get(chunk_id)
                if chunk and chunk.relations:
                    for target_id, _ in chunk.relations:
                        target = self._chunks.get(target_id)
                        if target:
                            next_results.append(target)

            if next_results:
                reasoning_chain.append([c.content for c in next_results[:2]])
                current_chunks = {c.chunk_id for c in next_results[:2]}

        return {
            "query": query,
            "hops": hops,
            "reasoning": reasoning_chain,
            "final_answer": reasoning_chain[-1][0] if reasoning_chain else None,
        }

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_chunks = len(self._chunks)

        relation_counts = defaultdict(int)
        for chunk in self._chunks.values():
            for _, rel in chunk.relations:
                relation_counts[rel.value] += 1

        return {
            "total_chunks": total_chunks,
            "relation_distribution": dict(relation_counts),
            "avg_relations_per_chunk": (
                sum(len(c.relations) for c in self._chunks.values()) / max(total_chunks, 1)
            ),
        }


def test_discourse_rag():
    """测试 Discourse-Aware RAG"""
    logger.info("=== 测试 Discourse-Aware RAG ===")

    rag = DiscourseAwareRAG()

    logger.info("\n1. 测试添加文档")
    doc1 = """
Python 是一种高级编程语言。由于其简洁易学的特点，Python 在近年来变得越来越流行。
首先，Python 拥有丰富的库支持。例如，NumPy 和 Pandas 用于数据分析。
其次，Python 的语法非常优雅。比如，列表推导式让代码更简洁。
然而，Python 的执行速度相对较慢。但是，这可以通过使用 Cython 或 PyPy 来改善。
最后，Python 是开源的。开源意味着社区的支持很重要。
    """

    chunk_ids = rag.add_document(doc1, metadata={"source": "python_intro"})
    logger.info(f"  添加文档，分割为 {len(chunk_ids)} 个块")

    logger.info("\n2. 测试检索")
    results = rag.retrieve("Python 有什么特点", top_k=3)
    logger.info(f"  找到 {len(results)} 个相关块:")
    for i, r in enumerate(results, 1):
        logger.info(f"    {i}. {r.chunk.content[:40]}... (分数: {r.final_score:.3f})")

    logger.info("\n3. 测试统计")
    stats = rag.get_stats()
    logger.info(f"  总块数: {stats['total_chunks']}")
    logger.info(f"  平均关系数: {stats['avg_relations_per_chunk']:.2f}")
    logger.info(f"  关系分布: {stats['relation_distribution']}")

    logger.info("\n4. 测试生成规划蓝图")
    blueprint = rag.generate_bluelogger.info("Python 有什么特点", results)
    logger.info(f"  蓝图中包含 {len(blueprint['sections'])} 个部分")
    logger.info(f"  结构描述: {blueprint['answer_structure']}")

    logger.info("\n5. 测试多跳推理")
    reasoning = rag.multi_hop_reasoning("Python 的生态系统", hops=2)
    logger.info(f"  推理跳数: {reasoning['hops']}")
    logger.info(f"  推理链长度: {len(reasoning['reasoning'])}")

    logger.info("\nDiscourse-Aware RAG 测试完成！")


if __name__ == "__main__":
    test_discourse_rag()