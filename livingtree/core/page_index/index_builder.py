"""
PageIndex 索引构建器
构建 B-tree 风格的索引结构

核心思想:
1. 将文档分成多个 chunk
2. 底层节点包含原始 chunk
3. 上层节点是对下层的摘要 (由 LLM 生成)
4. 查询时从根向下定位到目标 chunk
"""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Optional

from .document_loader import DocumentLoader
from .models import (
    Chunk,
    ChunkType,
    DocumentType,
    IndexedDocument,
    IndexNode,
    IndexStats,
)


class PageIndexBuilder:
    """
    PageIndex 索引构建器

    使用 B-tree 风格的分层索引:
    - Level 0: 叶子节点 (原始 chunks)
    - Level 1-N: 内部节点 (chunk 摘要的摘要)
    - Root: 整个文档的顶级摘要
    """

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        tree_height: int = 4,
        index_dir: str = "~/.hermes-desktop/page_index"
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.tree_height = tree_height
        self.index_dir = Path(os.path.expanduser(index_dir))
        self.index_dir.mkdir(parents=True, exist_ok=True)

        self.loader = DocumentLoader()
        self.stats = IndexStats()

    def build_index(
        self,
        file_path: str,
        doc_key: Optional[str] = None,
        use_llm_summaries: bool = True
    ) -> IndexedDocument:
        """
        构建文档索引

        Args:
            file_path: 文档路径
            doc_key: 文档标识键 (默认用文件名)
            use_llm_summaries: 是否使用 LLM 生成摘要

        Returns:
            IndexedDocument: 索引后的文档对象
        """
        start_time = time.time()

        # 加载文档
        result = self.loader.load(file_path)
        doc_key = doc_key or Path(file_path).stem

        # 创建文档对象
        doc = IndexedDocument(
            doc_id=self._generate_doc_id(doc_key),
            title=result.metadata.get("title", doc_key),
            file_path=file_path,
            doc_type=result.doc_type,
            total_pages=result.metadata.get("total_pages", 1),
            total_chunks=0,
            tree_height=self.tree_height,
            root_node_id="",
            metadata=result.metadata
        )

        # 分块
        chunks = list(self.loader.chunk_text(
            result.content,
            page_num=1,
            chunk_size=self.chunk_size,
            overlap=self.chunk_overlap
        ))

        # 添加 chunks 到文档
        for chunk in chunks:
            doc.add_chunk(chunk)

        # 构建索引树
        root_node = self._build_tree(doc, chunks, use_llm_summaries)
        doc.root_node_id = root_node.node_id

        # 更新统计
        self.stats.total_documents += 1
        self.stats.total_chunks += len(chunks)
        self.stats.total_nodes += len(doc._nodes)
        self.stats.last_build_time = time.time() - start_time

        # 保存索引到磁盘
        self._save_index(doc)

        return doc

    def _build_tree(
        self,
        doc: IndexedDocument,
        chunks: list[Chunk],
        use_llm: bool
    ) -> IndexNode:
        """
        构建索引树 (自底向上)

        Level 0: chunks 本身
        Level 1: chunk 组的摘要
        Level 2: 摘要组的摘要
        ...
        """
        current_level_nodes = []
        current_chunk_ids = [c.chunk_id for c in chunks]

        # 计算每层的分支因子
        branch_factor = max(2, len(chunks) // (self.tree_height - 1))

        # Level 1: 创建 chunk 组节点
        for i in range(0, len(chunks), branch_factor):
            chunk_group = chunks[i:i + branch_factor]
            group_text = "\n".join([c.text for c in chunk_group])

            # 生成或使用 LLM 摘要
            if use_llm and self._has_ollama():
                summary = self._llm_summarize(group_text)
            else:
                summary = self._simple_summarize(group_text)

            node = IndexNode(
                node_id=f"node_L1_{len(current_level_nodes):04d}",
                level=1,
                summary=summary,
                chunk_ids=[c.chunk_id for c in chunk_group],
                metadata={"range": f"{chunk_group[0].chunk_id}-{chunk_group[-1].chunk_id}"}
            )

            doc.add_node(node)
            current_level_nodes.append(node)

        # 自底向上构建更高层级
        level = 2
        while len(current_level_nodes) > 1:
            next_level_nodes = []
            branch = max(2, len(current_level_nodes) // 2)

            for i in range(0, len(current_level_nodes), branch):
                node_group = current_level_nodes[i:i + branch]
                group_text = "\n".join([n.summary for n in node_group])

                if use_llm and self._has_ollama():
                    summary = self._llm_summarize(group_text)
                else:
                    summary = self._simple_summarize(group_text[:500])

                node = IndexNode(
                    node_id=f"node_L{level}_{len(next_level_nodes):04d}",
                    level=level,
                    summary=summary,
                    chunk_ids=[],
                    children=[n.node_id for n in node_group],
                    metadata={"child_count": len(node_group)}
                )

                doc.add_node(node)
                next_level_nodes.append(node)

            current_level_nodes = next_level_nodes
            level += 1

        # 返回根节点
        return current_level_nodes[0] if current_level_nodes else None

    def _simple_summarize(self, text: str) -> str:
        """
        简单摘要 (不依赖 LLM)
        取前 N 个字符 + 关键词提取
        """
        # 取前 100 字符
        preview = text[:100].strip()

        # 提取关键词 (高频词)
        words = text.lower().split()
        word_freq = {}
        for word in words:
            if len(word) > 3:
                word_freq[word] = word_freq.get(word, 0) + 1

        # 取 top 3 关键词
        top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:3]
        keywords = ", ".join([w[0] for w in top_words])

        return f"{preview}... [关键词: {keywords}]"

    def _has_ollama(self) -> bool:
        """检查是否有 Ollama 服务"""
        try:
            from ..ollama_client import OllamaClient
            client = OllamaClient()
            return client.is_available()
        except:
            return False

    def _llm_summarize(self, text: str) -> str:
        """使用 LLM 生成摘要"""
        try:
            from ..ollama_client import OllamaClient

            client = OllamaClient()
            prompt = f"""请生成以下文本的简短摘要 (不超过50字):

{text[:1000]}

摘要:"""

            response = client.generate(prompt, max_tokens=100)
            return response.strip() if response else self._simple_summarize(text)

        except Exception as e:
            return self._simple_summarize(text)

    def _generate_doc_id(self, doc_key: str) -> str:
        """生成文档 ID"""
        return hashlib.md5(doc_key.encode()).hexdigest()[:12]

    def _save_index(self, doc: IndexedDocument):
        """保存索引到磁盘"""
        # 保存文档元数据
        meta_path = self.index_dir / f"{doc.doc_id}.meta.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(doc.to_dict(), f, ensure_ascii=False, indent=2)

        # 保存 chunks
        chunks_path = self.index_dir / f"{doc.doc_id}.chunks.json"
        chunks_data = {
            chunk_id: chunk.to_dict()
            for chunk_id, chunk in doc._chunks.items()
        }
        with open(chunks_path, "w", encoding="utf-8") as f:
            json.dump(chunks_data, f, ensure_ascii=False, indent=2)

        # 保存节点
        nodes_path = self.index_dir / f"{doc.doc_id}.nodes.json"
        nodes_data = {
            node_id: node.to_dict()
            for node_id, node in doc._nodes.items()
        }
        with open(nodes_path, "w", encoding="utf-8") as f:
            json.dump(nodes_data, f, ensure_ascii=False, indent=2)

    def load_index(self, doc_id: str) -> Optional[IndexedDocument]:
        """从磁盘加载索引"""
        meta_path = self.index_dir / f"{doc_id}.meta.json"
        if not meta_path.exists():
            return None

        # 加载元数据
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        # 创建文档对象
        doc = IndexedDocument(
            doc_id=meta["doc_id"],
            title=meta["title"],
            file_path=meta["file_path"],
            doc_type=DocumentType(meta["doc_type"]),
            total_pages=meta["total_pages"],
            total_chunks=meta["total_chunks"],
            tree_height=meta["tree_height"],
            root_node_id=meta["root_node_id"],
            created_at=meta["created_at"],
            updated_at=meta["updated_at"],
            metadata=meta.get("metadata", {})
        )

        # 加载 chunks
        chunks_path = self.index_dir / f"{doc_id}.chunks.json"
        if chunks_path.exists():
            with open(chunks_path, "r", encoding="utf-8") as f:
                chunks_data = json.load(f)
            for chunk_id, chunk_dict in chunks_data.items():
                chunk = Chunk(
                    chunk_id=chunk_dict["chunk_id"],
                    text=chunk_dict["text"],
                    chunk_type=ChunkType(chunk_dict["chunk_type"]),
                    page_num=chunk_dict["page_num"],
                    position=chunk_dict["position"],
                    metadata=chunk_dict.get("metadata", {})
                )
                doc.add_chunk(chunk)

        # 加载节点
        nodes_path = self.index_dir / f"{doc_id}.nodes.json"
        if nodes_path.exists():
            with open(nodes_path, "r", encoding="utf-8") as f:
                nodes_data = json.load(f)
            for node_id, node_dict in nodes_data.items():
                node = IndexNode(
                    node_id=node_dict["node_id"],
                    level=node_dict["level"],
                    summary=node_dict["summary"],
                    chunk_ids=node_dict.get("chunk_ids", []),
                    children=node_dict.get("children", []),
                    metadata=node_dict.get("metadata", {})
                )
                doc.add_node(node)

        return doc

    def list_documents(self) -> list[dict]:
        """列出所有已索引的文档"""
        docs = []
        for meta_file in self.index_dir.glob("*.meta.json"):
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                docs.append(meta)
            except:
                continue
        return docs

    def delete_index(self, doc_id: str):
        """删除索引"""
        for ext in [".meta.json", ".chunks.json", ".nodes.json"]:
            file_path = self.index_dir / f"{doc_id}{ext}"
            if file_path.exists():
                file_path.unlink()
        self.stats.total_documents -= 1

    def get_stats(self) -> IndexStats:
        """获取索引统计"""
        return self.stats
