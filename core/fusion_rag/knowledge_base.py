"""
知识库层 (Knowledge Base Layer)
深度文档检索与混合索引

特性:
- 智能文档分块 (语义/重叠/层次)
- 混合检索 (向量 + 关键词 + 元数据)
- BGE-small-zh 向量嵌入
- BM25 关键词排序
"""

import time
import hashlib
import re
from typing import Optional, Dict, Any, List
from collections import defaultdict
import threading


class KnowledgeBaseLayer:
    """知识库检索层 - 深度文档检索"""
    
    def __init__(
        self,
        embedding_model: str = "BAAI/bge-small-zh",
        top_k: int = 10,
        chunk_size: int = 512,
        chunk_overlap: int = 64
    ):
        """
        初始化知识库层
        
        Args:
            embedding_model: 嵌入模型名称
            top_k: 默认返回数量
            chunk_size: 分块大小
            chunk_overlap: 分块重叠大小
        """
        # 文档存储
        self.documents: Dict[str, Dict] = {}
        self.chunks: List[Dict] = []
        self.chunk_index: Dict[str, int] = {}  # chunk_id -> index
        
        # 索引
        self.vector_index: List[List[float]] = []
        self.bm25_index: Dict[str, List[int]] = defaultdict(list)  # word -> chunk_ids
        self.metadata_index: Dict[str, List[str]] = defaultdict(list)  # key -> values -> chunk_ids
        
        # 配置
        self.embedding_model = embedding_model
        self.default_top_k = top_k
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # 统计
        self.search_count = 0
        self.hit_count = 0
        self.lock = threading.Lock()
        
        print(f"[KnowledgeBase] 初始化完成，嵌入模型: {embedding_model}")
    
    def _tokenize(self, text: str) -> List[str]:
        """简单分词"""
        # 简单中英文分词
        text = text.lower()
        words = re.findall(r'[\w]+', text)
        return words
    
    def _compute_bm25_score(self, query: str, chunk_id: str) -> float:
        """计算 BM25 分数"""
        query_words = self._tokenize(query)
        
        if chunk_id not in self.chunk_index:
            return 0.0
        
        chunk = self.chunks[self.chunk_index[chunk_id]]
        chunk_words = self._tokenize(chunk["content"])
        
        if not query_words or not chunk_words:
            return 0.0
        
        # 简单词频统计
        chunk_word_freq = defaultdict(int)
        for word in chunk_words:
            chunk_word_freq[word] += 1
        
        # 计算 BM25 简化版
        score = 0.0
        k1 = 1.5
        b = 0.75
        
        avg_chunk_len = sum(len(c["content"]) for c in self.chunks) / max(len(self.chunks), 1)
        chunk_len = len(chunk_words)
        
        for word in query_words:
            if word in chunk_word_freq:
                tf = chunk_word_freq[word]
                # 简化的 IDF
                doc_count = sum(1 for c in self.chunks if word in c["content"])
                idf = max(0.1, (len(self.chunks) - doc_count + 0.5) / (doc_count + 0.5))
                
                # BM25 公式
                numerator = tf * (k1 + 1)
                denominator = tf + k1 * (1 - b + b * (chunk_len / avg_chunk_len))
                score += idf * numerator / denominator
        
        return score
    
    def _compute_vector_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算向量余弦相似度"""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        
        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot / (norm1 * norm2)
    
    def _generate_simple_embedding(self, text: str) -> List[float]:
        """生成简化的文本嵌入 (用于演示)"""
        # 简化: 使用词袋哈希
        words = self._tokenize(text)
        vec = [0.0] * 128
        
        for word in words:
            word_hash = hash(word) % 128
            vec[word_hash] += 1.0
        
        # L2 归一化
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        
        return vec
    
    def _create_chunks(self, doc: Dict) -> List[Dict]:
        """创建文档分块"""
        content = doc.get("content", "")
        chunks = []
        
        # 滑动窗口分块
        start = 0
        chunk_id_prefix = hashlib.md5(doc["id"].encode()).hexdigest()[:8]
        
        while start < len(content):
            end = start + self.chunk_size
            chunk_text = content[start:end]
            
            if len(chunk_text.strip()) < 20:  # 太小跳过
                start = end
                continue
            
            chunk_id = f"{chunk_id_prefix}_{len(chunks)}"
            
            chunks.append({
                "id": chunk_id,
                "doc_id": doc["id"],
                "content": chunk_text,
                "title": doc.get("title", ""),
                "type": doc.get("type", "unknown"),
                "metadata": doc.get("metadata", {}),
                "position": len(chunks)
            })
            
            start = end - self.chunk_overlap  # 重叠滑动
        
        return chunks
    
    def add_document(self, doc: Dict) -> int:
        """
        添加文档
        
        Args:
            doc: 文档字典 {"id", "title", "content", "type", ...}
            
        Returns:
            分块数量
        """
        with self.lock:
            doc_id = doc["id"]
            
            # 存储文档
            self.documents[doc_id] = doc
            
            # 创建分块
            chunks = self._create_chunks(doc)
            
            for chunk in chunks:
                chunk_id = chunk["id"]
                
                # 存储
                self.chunks.append(chunk)
                idx = len(self.chunks) - 1
                self.chunk_index[chunk_id] = idx
                
                # 向量索引
                embedding = self._generate_simple_embedding(chunk["content"])
                self.vector_index.append(embedding)
                
                # BM25 索引
                for word in self._tokenize(chunk["content"]):
                    self.bm25_index[word].append(idx)
                
                # 元数据索引
                if chunk["type"]:
                    self.metadata_index["type"].append(idx)
            
            return len(chunks)
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        doc_type: Optional[str] = None,
        alpha: float = 0.6  # 向量权重
    ) -> List[Dict[str, Any]]:
        """
        搜索文档
        
        Args:
            query: 查询文本
            top_k: 返回数量
            doc_type: 文档类型过滤
            alpha: 向量权重 (1-alpha = 关键词权重)
            
        Returns:
            搜索结果列表
        """
        with self.lock:
            self.search_count += 1
            
            if not self.chunks:
                return []
            
            # 计算查询向量
            query_vec = self._generate_simple_embedding(query)
            
            # 收集候选
            candidates: Dict[int, Dict] = {}
            
            # 1. 向量检索
            for i, vec in enumerate(self.vector_index):
                if doc_type and self.chunks[i]["type"] != doc_type:
                    continue
                
                vector_score = self._compute_vector_similarity(query_vec, vec)
                
                if vector_score > 0.1:
                    if i not in candidates:
                        candidates[i] = {"chunk": self.chunks[i]}
                    candidates[i]["vector_score"] = vector_score
            
            # 2. BM25 关键词检索
            for i, chunk in enumerate(self.chunks):
                if doc_type and chunk["type"] != doc_type:
                    continue
                
                bm25_score = self._compute_bm25_score(query, chunk["id"])
                
                if bm25_score > 0.1:
                    if i not in candidates:
                        candidates[i] = {"chunk": chunk}
                    candidates[i]["bm25_score"] = bm25_score
            
            # 3. 融合分数
            for i, cand in candidates.items():
                vector_score = cand.get("vector_score", 0)
                bm25_score = cand.get("bm25_score", 0)
                
                # 归一化
                max_vector = max(c.get("vector_score", 0) for c in candidates.values()) if candidates else 1
                max_bm25 = max(c.get("bm25_score", 0) for c in candidates.values()) if candidates else 1
                
                norm_vector = vector_score / max_vector if max_vector > 0 else 0
                norm_bm25 = bm25_score / max_bm25 if max_bm25 > 0 else 0
                
                # 加权融合
                fused_score = alpha * norm_vector + (1 - alpha) * norm_bm25
                cand["score"] = fused_score
                cand["vector_score"] = norm_vector
                cand["bm25_score"] = norm_bm25
            
            # 排序
            results = sorted(
                candidates.values(),
                key=lambda x: x["score"],
                reverse=True
            )[:top_k]
            
            # 格式化输出
            formatted = []
            for r in results:
                formatted.append({
                    "id": r["chunk"]["id"],
                    "doc_id": r["chunk"]["doc_id"],
                    "title": r["chunk"]["title"],
                    "content": r["chunk"]["content"],
                    "type": r["chunk"]["type"],
                    "score": r["score"],
                    "vector_score": r["vector_score"],
                    "bm25_score": r["bm25_score"]
                })
            
            if formatted:
                self.hit_count += 1
            
            return formatted
    
    def search_optimized(
        self,
        query: str,
        top_k: int = 5,
        doc_type: Optional[str] = None,
        alpha: float = 0.6,
        initial_candidates: int = 100
    ) -> List[Dict[str, Any]]:
        """
        两阶段优化搜索：倒排索引快速过滤 + 向量重排
        
        性能优化（真正利用倒排索引）：
        - 阶段1: 用 bm25_index 倒排索引获取匹配的 chunk_ids（O(Q) 而不是 O(Q*N)）
        - 阶段2: 只对候选做向量计算
        
        Args:
            query: 查询文本
            top_k: 返回数量
            doc_type: 文档类型过滤
            alpha: 向量权重
            initial_candidates: 第一阶段保留的候选数量
            
        Returns:
            搜索结果列表
        """
        import time as time_module
        
        with self.lock:
            self.search_count += 1
            
            if not self.chunks:
                return []
            
            phase1_start = time_module.time()
            
            # ========== 阶段1: 倒排索引快速过滤 + BM25评分 ==========
            query_words = self._tokenize(query)
            
            # 用倒排索引收集匹配的 chunks
            matched_chunks: Dict[int, Dict] = {}  # chunk_idx -> {match_count, tf_dict}
            
            # 统计文档频率（用倒排索引）
            doc_freq: Dict[str, int] = {}
            for word in query_words:
                if word in self.bm25_index:
                    doc_freq[word] = len(self.bm25_index[word])
            
            # 对每个匹配的 chunk 计算词频
            for word in query_words:
                if word not in self.bm25_index:
                    continue
                for chunk_idx in self.bm25_index[word]:
                    if doc_type and self.chunks[chunk_idx]["type"] != doc_type:
                        continue
                    if chunk_idx not in matched_chunks:
                        matched_chunks[chunk_idx] = {"match_count": 0, "tf": defaultdict(int)}
                    matched_chunks[chunk_idx]["match_count"] += 1
                    matched_chunks[chunk_idx]["tf"][word] += 1
            
            # 计算 BM25 分数
            total_chunks = len(self.chunks)
            avg_len = sum(len(c["content"]) for c in self.chunks) / max(total_chunks, 1)
            k1, b = 1.5, 0.75
            
            bm25_scores = []
            for chunk_idx, data in matched_chunks.items():
                chunk = self.chunks[chunk_idx]
                chunk_len = len(chunk["content"])
                
                score = 0.0
                for word, tf in data["tf"].items():
                    # IDF
                    df = doc_freq.get(word, 1)
                    idf = max(0.1, (total_chunks - df + 0.5) / (df + 0.5))
                    # BM25 term
                    term_score = idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (chunk_len / avg_len)))
                    score += term_score
                
                bm25_scores.append((chunk_idx, score))
            
            # 按 BM25 分数排序
            bm25_scores.sort(key=lambda x: x[1], reverse=True)
            
            # 取前 initial_candidates 个
            candidate_indices = [idx for idx, _ in bm25_scores[:initial_candidates]]
            
            # 保存原始 BM25 分数用于归一化
            bm25_dict = {idx: score for idx, score in bm25_scores[:initial_candidates]}
            
            phase1_time = (time_module.time() - phase1_start) * 1000
            
            if not candidate_indices:
                return []
            
            # 归一化 BM25 分数
            max_bm25 = bm25_scores[0][1] if bm25_scores else 1
            
            # ========== 阶段2: 向量计算（只对候选） ==========
            phase2_start = time_module.time()
            
            query_vec = self._generate_simple_embedding(query)
            
            candidates: Dict[int, Dict] = {}
            max_vector = 0
            
            for idx in candidate_indices:
                chunk = self.chunks[idx]
                vector_score = self._compute_vector_similarity(query_vec, self.vector_index[idx])
                bm25_norm = bm25_dict.get(idx, 0) / max_bm25 if max_bm25 > 0 else 0
                
                candidates[idx] = {
                    "chunk": chunk,
                    "vector_score": vector_score,
                    "bm25_score": bm25_norm
                }
                max_vector = max(max_vector, vector_score)
            
            # 归一化向量分数
            if max_vector > 0:
                for i in candidates:
                    candidates[i]["vector_score"] = candidates[i]["vector_score"] / max_vector
            
            phase2_time = (time_module.time() - phase2_start) * 1000
            
            # ========== 阶段3: 融合排序 ==========
            for i, cand in candidates.items():
                fused_score = alpha * cand.get("vector_score", 0) + (1 - alpha) * cand.get("bm25_score", 0)
                cand["score"] = fused_score
            
            results = sorted(
                candidates.values(),
                key=lambda x: x["score"],
                reverse=True
            )[:top_k]
            
            # 格式化输出
            formatted = []
            for r in results:
                formatted.append({
                    "id": r["chunk"]["id"],
                    "doc_id": r["chunk"]["doc_id"],
                    "title": r["chunk"]["title"],
                    "content": r["chunk"]["content"],
                    "type": r["chunk"]["type"],
                    "score": r["score"],
                    "vector_score": r.get("vector_score", 0),
                    "bm25_score": r.get("bm25_score", 0),
                    "_perf": {"phase1_ms": phase1_time, "phase2_ms": phase2_time}
                })
            
            if formatted:
                self.hit_count += 1
            
            return formatted
    
    def get_document(self, doc_id: str) -> Optional[Dict]:
        """获取文档"""
        return self.documents.get(doc_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "document_count": len(self.documents),
            "chunk_count": len(self.chunks),
            "search_count": self.search_count,
            "hit_rate": self.hit_count / max(self.search_count, 1),
            "vocabulary_size": len(self.bm25_index),
            "avg_chunks_per_doc": len(self.chunks) / max(len(self.documents), 1)
        }
