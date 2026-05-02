"""
QueryEngine - PageIndex 查询引擎
通过索引树定位目标 chunk

查询策略:
1. 从根节点开始
2. 计算与查询最相关的子节点
3. 递归向下直到叶子节点
4. 返回 top-k 个相关 chunk
"""

import time
from typing import Optional

from .index_builder import PageIndexBuilder
from .models import Chunk, IndexedDocument, QueryResponse, QueryResult


class QueryEngine:
    """
    PageIndex 查询引擎

    支持两种查询模式:
    1. Tree Walk: 从根向下遍历定位
    2. Direct Search: 直接在 chunks 中搜索
    """

    def __init__(self, builder: Optional[PageIndexBuilder] = None):
        self.builder = builder or PageIndexBuilder()
        self._index_cache: dict[str, IndexedDocument] = {}

    def has_index(self, doc_key: str) -> bool:
        """检查是否有指定文档的索引"""
        if doc_key in self._index_cache:
            return True
        # 尝试懒加载
        doc_id = self.builder._generate_doc_id(doc_key)
        doc = self.builder.load_index(doc_id)
        if doc:
            self._index_cache[doc_key] = doc
            return True
        return False

    def cache_index(self, doc_key: str, doc: IndexedDocument):
        """手动缓存索引"""
        self._index_cache[doc_key] = doc

    def query(
        self,
        question: str,
        doc_key: str,
        top_k: int = 3,
        use_tree_walk: bool = True
    ) -> QueryResponse:
        """
        查询索引

        Args:
            question: 查询问题
            doc_key: 文档键
            top_k: 返回 top-k 结果
            use_tree_walk: 是否使用树遍历

        Returns:
            QueryResponse: 查询结果
        """
        start_time = time.time()

        # 懒加载索引
        if doc_key not in self._index_cache:
            doc_id = self.builder._generate_doc_id(doc_key)
            doc = self.builder.load_index(doc_id)
            if doc:
                self._index_cache[doc_key] = doc

        doc = self._index_cache.get(doc_key)
        if not doc:
            return QueryResponse(
                query=question,
                results=[],
                context="",
                total_found=0,
                response_time_ms=(time.time() - start_time) * 1000
            )

        # 执行查询
        if use_tree_walk:
            results = self._tree_walk_query(doc, question, top_k)
        else:
            results = self._direct_search(doc, question, top_k)

        # 构建上下文
        context = self._build_context(results)

        # 更新统计
        self.builder.stats.query_count += 1
        response_time = (time.time() - start_time) * 1000
        self.builder.stats.avg_query_time_ms = (
            (self.builder.stats.avg_query_time_ms * (self.builder.stats.query_count - 1) + response_time)
            / self.builder.stats.query_count
        )

        return QueryResponse(
            query=question,
            results=results,
            context=context,
            total_found=len(results),
            response_time_ms=response_time
        )

    def _tree_walk_query(
        self,
        doc: IndexedDocument,
        question: str,
        top_k: int
    ) -> list[QueryResult]:
        """
        树遍历查询

        从根节点向下，选择与问题最相关的路径
        """
        if not doc.root_node_id:
            return self._direct_search(doc, question, top_k)

        # 获取根节点
        root = doc.get_node(doc.root_node_id)
        if not root:
            return self._direct_search(doc, question, top_k)

        # 向下遍历收集候选 chunks
        candidate_node_ids = self._collect_candidate_nodes(root, question)

        # 收集这些节点包含的 chunks
        candidate_chunks = []
        for node_id in candidate_node_ids:
            node = doc.get_node(node_id)
            if node:
                for chunk_id in node.chunk_ids:
                    chunk = doc.get_chunk(chunk_id)
                    if chunk:
                        candidate_chunks.append(chunk)

        # 如果没有通过节点找到 chunks，直接搜索所有 chunks
        if not candidate_chunks:
            candidate_chunks = list(doc._chunks.values())

        # 计算相关性得分并排序
        scored_chunks = []
        for chunk in candidate_chunks:
            score = self._calculate_relevance(chunk.text, question)
            scored_chunks.append((chunk, score))

        scored_chunks.sort(key=lambda x: x[1], reverse=True)

        # 构建结果
        results = []
        for chunk, score in scored_chunks[:top_k]:
            section_path = self._get_section_path(doc, chunk)
            results.append(QueryResult(
                chunk_id=chunk.chunk_id,
                text=chunk.text,
                page_num=chunk.page_num,
                score=score,
                section_title=section_path[-1] if section_path else "",
                section_path=section_path
            ))

        return results

    def _collect_candidate_nodes(
        self,
        node: "IndexNode",
        question: str,
        depth: int = 0,
        max_depth: int = 3
    ) -> list[str]:
        """
        收集候选节点

        从当前节点向下，选择最相关的子节点
        """
        if depth >= max_depth or not node.children:
            return [node.node_id]

        # 计算与每个子节点的相关性
        child_scores = []
        for child_id in node.children:
            child = self._index_cache.get(node.node_id)
            if not child:
                # 需要通过 doc 获取
                continue
            child_node = self._get_child_node(node, child_id)
            if child_node:
                score = self._calculate_relevance(child_node.summary, question)
                child_scores.append((child_id, score))

        # 选择 top 子节点
        child_scores.sort(key=lambda x: x[1], reverse=True)

        # 取 top-2 或全部（如果少于2个）
        top_children = [cid for cid, _ in child_scores[:2]]

        # 递归收集
        candidates = []
        for child_id in top_children:
            child_node = self._get_child_node(node, child_id)
            if child_node:
                candidates.extend(
                    self._collect_candidate_nodes(child_node, question, depth + 1, max_depth)
                )

        return candidates if candidates else [node.node_id]

    def _get_child_node(self, parent: "IndexNode", child_id: str) -> Optional["IndexNode"]:
        """获取子节点 (需要 doc 上下文)"""
        # 这个方法需要 doc 引用，在实际调用时通过 doc.get_node() 获取
        return None

    def _direct_search(
        self,
        doc: IndexedDocument,
        question: str,
        top_k: int
    ) -> list[QueryResult]:
        """
        直接搜索所有 chunks
        (降级方案)
        """
        scored_chunks = []

        for chunk in doc._chunks.values():
            score = self._calculate_relevance(chunk.text, question)
            scored_chunks.append((chunk, score))

        scored_chunks.sort(key=lambda x: x[1], reverse=True)

        results = []
        for chunk, score in scored_chunks[:top_k]:
            results.append(QueryResult(
                chunk_id=chunk.chunk_id,
                text=chunk.text,
                page_num=chunk.page_num,
                score=score,
                section_title="",
                section_path=[]
            ))

        return results

    def _calculate_relevance(self, text: str, question: str) -> float:
        """
        计算文本与问题的相关性

        使用关键词匹配 + 位置权重
        """
        text_lower = text.lower()
        question_lower = question.lower()

        # 提取问题关键词
        question_words = set(question_lower.split())
        question_keywords = {
            word for word in question_words
            if len(word) > 2 and word not in {
                "什么", "怎么", "如何", "为什么", "哪里", "哪个",
                "the", "a", "an", "is", "are", "was", "were",
                "what", "how", "why", "where", "which"
            }
        }

        # 计算匹配得分
        score = 0.0

        # 精确匹配关键词
        for keyword in question_keywords:
            if keyword in text_lower:
                score += 1.0
                # 计算出现次数加成
                count = text_lower.count(keyword)
                if count > 1:
                    score += min(count - 1, 2) * 0.5

        # 标题/开头匹配加权
        if text[:100].lower().startswith(question_lower[:20]):
            score += 2.0

        # 归一化
        if question_keywords:
            score = score / len(question_keywords)

        return min(score, 10.0)  # 最高10分

    def _build_context(self, results: list[QueryResult]) -> str:
        """构建 LLM 上下文"""
        if not results:
            return ""

        context_parts = []
        for i, result in enumerate(results, 1):
            context_parts.append(
                f"[候选 {i} - 第{result.page_num}页 - 相关度:{result.score:.2f}]\n"
                f"{result.text[:800]}"
                + ("..." if len(result.text) > 800 else "")
            )

        return "\n\n".join(context_parts)

    def _get_section_path(
        self,
        doc: IndexedDocument,
        chunk: Chunk
    ) -> list[str]:
        """
        获取 chunk 所属的章节路径

        通过向上遍历节点树获取
        """
        path = []

        # 找到包含此 chunk 的最高层节点
        for node in doc._nodes.values():
            if chunk.chunk_id in node.chunk_ids:
                path.append(node.summary[:50])
                # 向上查找父节点
                parent = self._find_parent(doc, node)
                while parent:
                    path.insert(0, parent.summary[:50])
                    parent = self._find_parent(doc, parent)

        return path if path else [chunk.text[:50]]

    def _find_parent(
        self,
        doc: IndexedDocument,
        node: "IndexNode"
    ) -> Optional["IndexNode"]:
        """找到节点的父节点"""
        for potential_parent in doc._nodes.values():
            if node.node_id in potential_parent.children:
                return potential_parent
        return None

    def cache_index(self, doc_key: str, doc: IndexedDocument):
        """缓存索引到内存"""
        self._index_cache[doc_key] = doc

    def clear_cache(self):
        """清空缓存"""
        self._index_cache.clear()

    def warm_up(self, doc_keys: list[str]):
        """
        预热缓存

        Args:
            doc_keys: 要预热的文档键列表
        """
        for doc_key in doc_keys:
            if doc_key not in self._index_cache:
                doc_id = self.builder._generate_doc_id(doc_key)
                doc = self.builder.load_index(doc_id)
                if doc:
                    self._index_cache[doc_key] = doc
