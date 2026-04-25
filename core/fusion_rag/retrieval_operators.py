"""
BookRAG - 检索操作符
Retrieval Operators for Modular Retrieval Pipeline

四种核心操作符：
1. Selector - 选择最相关的块
2. Reasoner - 推理块之间的关系
3. Aggregator - 聚合全局信息
4. Synthesizer - 合成最终答案
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Callable
import math
import re


# ============== 数据结构 ==============

@dataclass
class Chunk:
    """文档块"""
    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    relevance_score: float = 0.0
    source: str = ""
    
    def __hash__(self):
        return hash(self.id)
    
    def __eq__(self, other):
        if not isinstance(other, Chunk):
            return False
        return self.id == other.id


@dataclass
class RetrievalContext:
    """检索上下文"""
    chunks: List[Chunk] = field(default_factory=list)
    query: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_chunk(self, chunk: Chunk):
        """添加块"""
        self.chunks.append(chunk)
    
    def get_top_chunks(self, k: int = 10) -> List[Chunk]:
        """获取 top-k 块"""
        sorted_chunks = sorted(
            self.chunks, 
            key=lambda x: x.relevance_score, 
            reverse=True
        )
        return sorted_chunks[:k]


@dataclass
class RetrievalResult:
    """检索结果"""
    answer: str = ""
    sources: List[Chunk] = field(default_factory=list)
    confidence: float = 0.0
    pipeline_used: List[str] = field(default_factory=list)
    reasoning: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_source(self, chunk: Chunk, reasoning: str = ""):
        """添加来源"""
        self.sources.append(chunk)
        if reasoning:
            self.reasoning.append(reasoning)


# ============== 基础接口 ==============

class RetrievalOperator(ABC):
    """检索操作符基类"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """操作符名称"""
        pass
    
    @abstractmethod
    def process(
        self, 
        query: str, 
        context: RetrievalContext
    ) -> RetrievalContext:
        """
        处理检索上下文
        
        Args:
            query: 查询文本
            context: 当前检索上下文
            
        Returns:
            更新后的上下文
        """
        pass


# ============== Selector（选择器） ==============

class Selector(RetrievalOperator):
    """
    选择器：从大量块中选择最相关的 Top-k 块
    
    策略：
    1. 语义相似度（embedding）
    2. 关键词密度
    3. BM25 混合
    4. 信息气味（Information Scent）
    """
    
    def __init__(
        self,
        top_k: int = 10,
        min_score: float = 0.1,
        use_hybrid: bool = True,
        semantic_weight: float = 0.6,
        keyword_weight: float = 0.3,
        bm25_weight: float = 0.1,
    ):
        """
        初始化选择器
        
        Args:
            top_k: 返回的 Top-k 块数
            min_score: 最小相关分数阈值
            use_hybrid: 是否使用混合策略
            semantic_weight: 语义相似度权重
            keyword_weight: 关键词密度权重
            bm25_weight: BM25 权重
        """
        self.top_k = top_k
        self.min_score = min_score
        self.use_hybrid = use_hybrid
        self.semantic_weight = semantic_weight
        self.keyword_weight = keyword_weight
        self.bm25_weight = bm25_weight
        
        # 提取查询关键词
        self.query_keywords = []
    
    @property
    def name(self) -> str:
        return "selector"
    
    def process(
        self, 
        query: str, 
        context: RetrievalContext
    ) -> RetrievalContext:
        """选择最相关的块"""
        self.query_keywords = self._extract_keywords(query)
        
        # 为每个块计算分数
        scored_chunks = []
        for chunk in context.chunks:
            score = self._calculate_relevance(chunk, query)
            chunk.relevance_score = score
            
            if score >= self.min_score:
                scored_chunks.append(chunk)
        
        # 排序并选择 Top-k
        scored_chunks.sort(key=lambda x: x.relevance_score, reverse=True)
        selected = scored_chunks[:self.top_k]
        
        # 返回新的上下文
        new_context = RetrievalContext(
            chunks=selected,
            query=query,
            metadata={**context.metadata, "total_candidates": len(context.chunks)}
        )
        
        return new_context
    
    def _extract_keywords(self, query: str) -> List[str]:
        """提取查询关键词"""
        # 简单分词（可替换为更复杂的实现）
        stopwords = {
            '的', '是', '在', '了', '和', '与', '或', '以及',
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'and', 'or'
        }
        
        words = re.findall(r'[\w]+', query.lower())
        return [w for w in words if w not in stopwords and len(w) > 1]
    
    def _calculate_relevance(self, chunk: Chunk, query: str) -> float:
        """计算相关分数"""
        if self.use_hybrid:
            # 混合策略
            semantic_score = self._semantic_similarity(chunk, query)
            keyword_score = self._keyword_density(chunk)
            bm25_score = self._bm25_score(chunk, query)
            
            return (
                semantic_score * self.semantic_weight +
                keyword_score * self.keyword_weight +
                bm25_score * self.bm25_weight
            )
        else:
            # 纯语义
            return self._semantic_similarity(chunk, query)
    
    def _semantic_similarity(self, chunk: Chunk, query: str) -> float:
        """语义相似度（基于 embedding 或 TF-IDF）"""
        # 如果有预计算的 embedding，使用余弦相似度
        if chunk.embedding:
            # 简化：假设 query embedding 已计算
            return self._cosine_similarity(chunk.embedding, self._mock_embedding(query))
        
        # 回退到 TF-IDF 相似度
        return self._tfidf_similarity(chunk.content, query)
    
    def _cosine_similarity(
        self, 
        vec1: List[float], 
        vec2: List[float]
    ) -> float:
        """余弦相似度"""
        if len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def _tfidf_similarity(self, text: str, query: str) -> float:
        """TF-IDF 相似度（简化实现）"""
        text_lower = text.lower()
        query_words = self._extract_keywords(query)
        
        if not query_words:
            return 0.0
        
        matches = sum(1 for w in query_words if w in text_lower)
        return matches / len(query_words)
    
    def _keyword_density(self, chunk: Chunk) -> float:
        """关键词密度"""
        content_lower = chunk.content.lower()
        
        if not self.query_keywords:
            return 0.0
        
        matches = sum(
            1 for kw in self.query_keywords 
            if kw in content_lower
        )
        
        # 密度 = 匹配数 / 总词数
        word_count = len(chunk.content.split())
        density = matches / max(word_count, 1)
        
        return min(density * 10, 1.0)  # 放大并截断
    
    def _bm25_score(self, chunk: Chunk, query: str) -> float:
        """BM25 分数（简化实现）"""
        # 简化 BM25
        content_lower = chunk.content.lower()
        query_words = self._extract_keywords(query)
        
        if not query_words:
            return 0.0
        
        matches = sum(1 for w in query_words if w in content_lower)
        doc_len = len(chunk.content.split())
        
        # 简化的 TF 组件
        avg_len = 100  # 假设平均文档长度
        k1 = 1.5
        b = 0.75
        
        tf = matches / max(doc_len, 1)
        len_norm = 1 - b + b * (doc_len / avg_len)
        
        return tf / (k1 * len_norm + tf)
    
    def _mock_embedding(self, text: str) -> List[float]:
        """生成模拟 embedding（用于测试）"""
        # 简化：用文本哈希生成固定长度向量
        import hashlib
        
        # 使用 SHA256 哈希
        hash_bytes = hashlib.sha256(text.encode()).digest()
        
        # 转换为 0-1 之间的浮点数
        embedding = []
        for i in range(0, min(len(hash_bytes), 64), 4):
            value = int.from_bytes(
                hash_bytes[i:i+4], 
                byteorder='big'
            ) / (2**32)
            embedding.append(value)
        
        # 确保长度一致
        while len(embedding) < 64:
            embedding.append(0.0)
        
        return embedding[:64]


# ============== Reasoner（推理器） ==============

class Reasoner(RetrievalOperator):
    """
    推理器：分析块之间的关系，构建推理链
    
    功能：
    1. 实体共现分析
    2. 引用/引用关系检测
    3. 时序关系
    4. 因果链路
    """
    
    def __init__(
        self,
        max_hops: int = 3,
        relation_threshold: float = 0.3,
    ):
        """
        初始化推理器
        
        Args:
            max_hops: 最大推理跳数
            relation_threshold: 关系阈值
        """
        self.max_hops = max_hops
        self.relation_threshold = relation_threshold
        self.relations = []  # 存储检测到的关系
        self.entity_graph = {}  # 实体关系图
    
    @property
    def name(self) -> str:
        return "reasoner"
    
    def process(
        self, 
        query: str, 
        context: RetrievalContext
    ) -> RetrievalContext:
        """推理块之间的关系"""
        self.relations = []
        self.entity_graph = {}
        
        chunks = context.chunks
        
        # 1. 提取实体
        entities = self._extract_entities(chunks)
        
        # 2. 构建实体关系图
        self._build_entity_graph(entities, chunks)
        
        # 3. 检测跨块引用
        self._detect_references(chunks)
        
        # 4. 按关系强度重新排序
        reordered_chunks = self._reorder_by_relations(chunks, query)
        
        # 更新上下文
        new_context = RetrievalContext(
            chunks=reordered_chunks,
            query=query,
            metadata={
                **context.metadata,
                "entities_found": len(entities),
                "relations_detected": len(self.relations),
                "entity_graph": self.entity_graph,
            }
        )
        
        return new_context
    
    def _extract_entities(self, chunks: List[Chunk]) -> Dict[str, List[int]]:
        """提取实体及其出现的块"""
        entities = {}
        
        # 简单实体识别（可替换为 NER 模型）
        entity_patterns = [
            r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*',  # 英文专有名词
            r'[\u4e00-\u9fff]{2,}(?:[\u4e00-\u9fff]{0,2}[\u4e00-\u9fff]{2,})*',  # 中文
        ]
        
        for i, chunk in enumerate(chunks):
            for pattern in entity_patterns:
                matches = re.findall(pattern, chunk.content)
                for entity in matches:
                    if len(entity) > 1:
                        if entity not in entities:
                            entities[entity] = []
                        entities[entity].append(i)
        
        return entities
    
    def _build_entity_graph(
        self, 
        entities: Dict[str, List[int]],
        chunks: List[Chunk]
    ):
        """构建实体关系图"""
        # 查找共同出现的实体
        entity_names = list(entities.keys())
        
        for i in range(len(entity_names)):
            for j in range(i + 1, len(entity_names)):
                e1, e2 = entity_names[i], entity_names[j]
                
                # 计算共现分数
                chunks_e1 = set(entities[e1])
                chunks_e2 = set(entities[e2])
                common = chunks_e1 & chunks_e2
                
                if common:
                    score = len(common) / max(len(chunks_e1), len(chunks_e2))
                    
                    if score >= self.relation_threshold:
                        self.relations.append({
                            "entities": (e1, e2),
                            "score": score,
                            "shared_chunks": list(common),
                        })
                        
                        # 更新图
                        if e1 not in self.entity_graph:
                            self.entity_graph[e1] = []
                        if e2 not in self.entity_graph:
                            self.entity_graph[e2] = []
                        
                        self.entity_graph[e1].append((e2, score))
                        self.entity_graph[e2].append((e1, score))
    
    def _detect_references(self, chunks: List[Chunk]):
        """检测引用关系"""
        # 常见的引用模式
        ref_patterns = [
            r'如上.*所述', r'如前.*所述', r'参见.*图',
            r'as mentioned above', r'as described earlier',
            r'见.*章节', r'参考.*内容',
        ]
        
        for i, chunk in enumerate(chunks):
            content = chunk.content.lower()
            for pattern in ref_patterns:
                if re.search(pattern, content):
                    self.relations.append({
                        "type": "reference",
                        "from_chunk": i,
                        "pattern": pattern,
                    })
    
    def _reorder_by_relations(
        self, 
        chunks: List[Chunk], 
        query: str
    ) -> List[Chunk]:
        """根据关系强度重新排序"""
        # 提取查询中的关键实体
        query_entities = []
        for entity, chunk_ids in self.entity_graph.items():
            if entity.lower() in query.lower():
                query_entities.append(entity)
        
        if not query_entities:
            return chunks
        
        # 计算每个块与查询的关联度
        scored_chunks = []
        for i, chunk in enumerate(chunks):
            score = 0.0
            
            for entity in query_entities:
                if entity in self.entity_graph:
                    # 加上该块与查询实体的关联分数
                    for neighbor, relation_score in self.entity_graph[entity]:
                        if neighbor in chunk.content:
                            score += relation_score
            
            scored_chunks.append((chunk, score))
        
        # 按分数排序（保留原始相关性）
        scored_chunks.sort(
            key=lambda x: (
                x[0].relevance_score + x[1] * 0.5,  # 综合分数
                x[1]  # 关系分数作为次要排序
            ),
            reverse=True
        )
        
        return [chunk for chunk, _ in scored_chunks]


# ============== Aggregator（聚合器） ==============

class Aggregator(RetrievalOperator):
    """
    聚合器：处理全局聚合查询
    
    功能：
    1. 计数统计
    2. 去重合并
    3. 分组聚合
    4. 排序汇总
    """
    
    def __init__(
        self,
        aggregation_type: str = "auto",
        top_n: int = 20,
    ):
        """
        初始化聚合器
        
        Args:
            aggregation_type: 聚合类型 ("auto", "count", "distinct", "group", "sort")
            top_n: 返回的 Top-n 结果
        """
        self.aggregation_type = aggregation_type
        self.top_n = top_n
        self.aggregation_result = None
    
    @property
    def name(self) -> str:
        return "aggregator"
    
    def process(
        self, 
        query: str, 
        context: RetrievalContext
    ) -> RetrievalContext:
        """执行聚合操作"""
        all_content = "\n".join(chunk.content for chunk in context.chunks)
        
        # 自动判断聚合类型
        agg_type = self._determine_aggregation_type(query)
        
        if agg_type == "count":
            result = self._count_occurrences(query, all_content)
        elif agg_type == "distinct":
            result = self._find_distinct_items(query, all_content)
        elif agg_type == "group":
            result = self._group_by_category(query, all_content)
        else:
            result = self._sort_and_rank(query, all_content)
        
        self.aggregation_result = result
        
        # 保留相关块作为来源
        new_context = RetrievalContext(
            chunks=context.chunks,
            query=query,
            metadata={
                **context.metadata,
                "aggregation_type": agg_type,
                "aggregation_result": result,
            }
        )
        
        return new_context
    
    def _determine_aggregation_type(self, query: str) -> str:
        """判断聚合类型"""
        query_lower = query.lower()
        
        if any(kw in query_lower for kw in ['多少', 'how many', 'count', '一共', '总数']):
            return "count"
        elif any(kw in query_lower for kw in ['哪些', '列出', 'list', 'all', '所有']):
            return "distinct"
        elif any(kw in query_lower for kw in ['分类', 'group', '类别', '类型']):
            return "group"
        else:
            return "sort"
    
    def _count_occurrences(self, query: str, content: str) -> Dict[str, int]:
        """计数"""
        # 提取计数目标
        target = self._extract_count_target(query)
        
        if target:
            count = content.count(target)
            return {"target": target, "count": count}
        
        # 返回高频词
        return self._word_frequency(content)
    
    def _extract_count_target(self, query: str) -> Optional[str]:
        """提取计数目标"""
        patterns = [
            r'提到.*?([^\s]+)',
            r'出现了.*?([^\s]+)',
            r'([^\s]+).*?次',
            r'mentioned?\s+(\w+)',
            r'how many\s+(\w+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query.lower())
            if match:
                return match.group(1)
        
        return None
    
    def _word_frequency(self, content: str) -> Dict[str, int]:
        """词频统计"""
        # 简单分词
        words = re.findall(r'[\w]+', content.lower())
        
        # 过滤停用词
        stopwords = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were',
            '的', '是', '在', '了', '和', '与', '或', '以及',
            'this', 'that', 'these', 'those', 'it', 'its',
        }
        
        filtered = [w for w in words if w not in stopwords and len(w) > 2]
        
        # 统计频率
        freq = {}
        for word in filtered:
            freq[word] = freq.get(word, 0) + 1
        
        # 返回 Top-n
        sorted_freq = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_freq[:self.top_n])
    
    def _find_distinct_items(self, query: str, content: str) -> List[str]:
        """去重查找"""
        # 提取名词短语
        patterns = [
            r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*',  # 英文
            r'[\u4e00-\u9fff]{2,}',  # 中文
        ]
        
        items = set()
        for pattern in patterns:
            matches = re.findall(pattern, content)
            items.update(matches)
        
        # 过滤通用词
        common_words = {
            '我们', '他们', '大家', '这个', '那个',
            'this', 'that', 'these', 'those',
        }
        
        filtered = [item for item in items if item not in common_words]
        
        return sorted(filtered)[:self.top_n]
    
    def _group_by_category(self, query: str, content: str) -> Dict[str, List]:
        """按类别分组"""
        # 简化实现：按段落分组
        paragraphs = content.split('\n')
        
        return {
            "groups": [{"content": p, "count": 1} for p in paragraphs if p.strip()],
            "total": len(paragraphs),
        }
    
    def _sort_and_rank(self, query: str, content: str) -> List[Dict]:
        """排序和排名"""
        # 返回按相关度排序的片段
        chunks = [
            {"content": line, "relevance": 0.5}
            for line in content.split('\n')
            if line.strip()
        ]
        
        # 简单相关度计算
        query_words = set(re.findall(r'[\w]+', query.lower()))
        
        for chunk in chunks:
            words = set(re.findall(r'[\w]+', chunk['content'].lower()))
            overlap = len(query_words & words)
            chunk['relevance'] = overlap / max(len(query_words), 1)
        
        # 排序
        chunks.sort(key=lambda x: x['relevance'], reverse=True)
        
        return chunks[:self.top_n]


# ============== Synthesizer（合成器） ==============

class Synthesizer(RetrievalOperator):
    """
    合成器：将检索结果合成为最终答案
    
    功能：
    1. 上下文压缩
    2. 答案片段拼接
    3. 引用标注
    4. 格式化成最终输出
    """
    
    def __init__(
        self,
        max_context_length: int = 4000,
        include_citations: bool = True,
        format_type: str = "auto",
    ):
        """
        初始化合成器
        
        Args:
            max_context_length: 最大上下文长度
            include_citations: 是否包含引用
            format_type: 输出格式 ("auto", "paragraph", "bullet", "numbered")
        """
        self.max_context_length = max_context_length
        self.include_citations = include_citations
        self.format_type = format_type
    
    @property
    def name(self) -> str:
        return "synthesizer"
    
    def process(
        self, 
        query: str, 
        context: RetrievalContext
    ) -> RetrievalContext:
        """合成最终答案"""
        # 压缩上下文
        compressed_context = self._compress_context(context)
        
        # 生成答案
        answer = self._generate_answer(query, compressed_context, context.chunks, original_context=context)
        
        # 更新上下文
        new_context = RetrievalContext(
            chunks=context.chunks,
            query=query,
            metadata={
                **context.metadata,
                "answer": answer,
                "compressed_length": len(compressed_context),
                "format_type": self.format_type,
            }
        )
        
        return new_context
    
    def _compress_context(self, context: RetrievalContext) -> str:
        """压缩上下文"""
        chunks = context.get_top_chunks(10)
        
        # 按相关度排序
        sorted_chunks = sorted(
            chunks, 
            key=lambda x: x.relevance_score, 
            reverse=True
        )
        
        # 构建压缩上下文
        parts = []
        current_length = 0
        
        for chunk in sorted_chunks:
            chunk_len = len(chunk.content)
            
            if current_length + chunk_len <= self.max_context_length:
                parts.append(chunk.content)
                current_length += chunk_len
            else:
                # 截断
                remaining = self.max_context_length - current_length
                if remaining > 100:  # 至少保留一些内容
                    parts.append(chunk.content[:remaining] + "...")
                    break
                else:
                    break
        
        return "\n\n".join(parts)
    
    def _generate_answer(
        self, 
        query: str, 
        compressed_context: str, 
        chunks: List[Chunk],
        original_context: RetrievalContext = None
    ) -> str:
        """生成答案"""
        # 检查是否有聚合结果
        agg_result = original_context.metadata.get("aggregation_result") if original_context else None
        
        if agg_result:
            return self._format_aggregation_result(agg_result)
        
        # 普通合成
        if not compressed_context or len(compressed_context) < 10:
            return "未找到足够的上下文信息来回答这个问题。"
        
        # 简单合成策略（实际应调用 LLM）
        answer_parts = []
        
        # 1. 理解问题类型
        if "什么" in query or "what" in query.lower():
            answer_parts.append(self._extract_what_answer(compressed_context))
        elif "如何" in query or "how" in query.lower():
            answer_parts.append(self._extract_how_answer(compressed_context))
        elif "为什么" in query or "why" in query.lower():
            answer_parts.append(self._extract_why_answer(compressed_context))
        else:
            answer_parts.append(self._extract_general_answer(compressed_context))
        
        answer = "\n\n".join(filter(None, answer_parts))
        
        # 2. 添加引用
        if self.include_citations and chunks:
            citations = self._generate_citations(chunks)
            answer += f"\n\n**参考来源：**\n{citations}"
        
        return answer
    
    def _extract_what_answer(self, context: str) -> str:
        """提取 What 类型答案"""
        # 取第一段作为答案
        first_para = context.split('\n')[0] if context else ""
        return first_para[:500] + "..." if len(first_para) > 500 else first_para
    
    def _extract_how_answer(self, context: str) -> str:
        """提取 How 类型答案"""
        # 查找包含步骤的内容
        paragraphs = context.split('\n')
        
        for para in paragraphs:
            if any(kw in para for kw in ['步骤', '方法', '首先', '然后', 'step', 'method', 'first', 'then']):
                return para[:500]
        
        return paragraphs[0] if paragraphs else ""
    
    def _extract_why_answer(self, context: str) -> str:
        """提取 Why 类型答案"""
        # 查找包含原因的内容
        paragraphs = context.split('\n')
        
        for para in paragraphs:
            if any(kw in para for kw in ['因为', '原因', '由于', 'due to', 'because', 'reason']):
                return para[:500]
        
        return paragraphs[0] if paragraphs else ""
    
    def _extract_general_answer(self, context: str) -> str:
        """提取一般答案"""
        return context[:1000] + "..." if len(context) > 1000 else context
    
    def _format_aggregation_result(self, result: Any) -> str:
        """格式化聚合结果"""
        if isinstance(result, dict):
            if "count" in result:
                return f"统计结果：共找到 **{result['count']}** 个 \"{result.get('target', '')}\""
            elif "groups" in result:
                lines = ["分组统计："]
                for i, group in enumerate(result.get("groups", [])[:10], 1):
                    lines.append(f"{i}. {group['content'][:100]}")
                return "\n".join(lines)
            else:
                lines = ["统计结果："]
                for key, value in list(result.items())[:10]:
                    lines.append(f"- {key}: {value}")
                return "\n".join(lines)
        elif isinstance(result, list):
            lines = ["结果列表："]
            for i, item in enumerate(result[:10], 1):
                lines.append(f"{i}. {item}")
            return "\n".join(lines)
        else:
            return str(result)
    
    def _generate_citations(self, chunks: List[Chunk]) -> str:
        """生成引用"""
        citations = []
        
        for i, chunk in enumerate(chunks[:5], 1):
            source = chunk.metadata.get("source", chunk.source) or f"来源 {chunk.id}"
            preview = chunk.content[:50] + "..."
            citations.append(f"[{i}] {source}: {preview}")
        
        return "\n".join(citations)


# ============== 检索管道 ==============

class RetrievalPipeline:
    """
    检索管道：组合多个操作符
    
    支持的管道配置：
    - simple: Selector → Synthesizer
    - reasoning: Selector → Reasoner → Synthesizer
    - aggregation: Selector → Aggregator → Synthesizer
    - full: Selector → Reasoner → Aggregator → Synthesizer
    """
    
    # 预定义管道模板
    PIPELINE_TEMPLATES = {
        "simple": ["selector", "synthesizer"],
        "reasoning": ["selector", "reasoner", "synthesizer"],
        "aggregation": ["selector", "aggregator", "synthesizer"],
        "full": ["selector", "reasoner", "aggregator", "synthesizer"],
    }
    
    def __init__(
        self,
        operators: Optional[Dict[str, RetrievalOperator]] = None,
        default_pipeline: str = "simple",
    ):
        """
        初始化检索管道
        
        Args:
            operators: 自定义操作符字典
            default_pipeline: 默认管道类型
        """
        # 初始化默认操作符
        self.operators = operators or {
            "selector": Selector(),
            "reasoner": Reasoner(),
            "aggregator": Aggregator(),
            "synthesizer": Synthesizer(),
        }
        
        self.default_pipeline = default_pipeline
        self.execution_log = []
    
    def run(
        self,
        query: str,
        chunks: List[Chunk],
        pipeline: Optional[List[str]] = None,
    ) -> RetrievalResult:
        """
        执行检索管道
        
        Args:
            query: 查询文本
            chunks: 文档块列表
            pipeline: 管道配置，如 ["selector", "reasoner", "synthesizer"]
                     或使用预定义模板名称
        
        Returns:
            RetrievalResult 检索结果
        """
        # 确定管道配置
        if pipeline is None:
            pipeline = self.PIPELINE_TEMPLATES.get(
                self.default_pipeline,
                self.PIPELINE_TEMPLATES["simple"]
            )
        
        # 如果传入的是字符串模板名
        if isinstance(pipeline, str):
            pipeline = self.PIPELINE_TEMPLATES.get(
                pipeline,
                self.PIPELINE_TEMPLATES["simple"]
            )
        
        self.execution_log = []
        
        # 初始化上下文
        context = RetrievalContext(chunks=chunks, query=query)
        
        # 执行管道
        for op_name in pipeline:
            if op_name not in self.operators:
                continue
            
            op = self.operators[op_name]
            self.execution_log.append(f"Executing: {op_name}")
            
            context = op.process(query, context)
        
        # 构建结果
        answer = context.metadata.get("answer", "")
        confidence = self._calculate_confidence(context)
        
        return RetrievalResult(
            answer=answer,
            sources=context.chunks,
            confidence=confidence,
            pipeline_used=pipeline,
            reasoning=self.execution_log,
            metadata=context.metadata,
        )
    
    def _calculate_confidence(self, context: RetrievalContext) -> float:
        """计算置信度"""
        if not context.chunks:
            return 0.0
        
        # 基于最高相关度
        top_score = max(c.relevance_score for c in context.chunks)
        
        # 基于来源数量
        coverage = min(len(context.chunks) / 10, 1.0)
        
        return (top_score * 0.7 + coverage * 0.3)


# 快捷函数
def create_pipeline(pipeline_type: str = "simple") -> RetrievalPipeline:
    """
    创建检索管道快捷函数
    
    Example:
        >>> pipeline = create_pipeline("reasoning")
        >>> result = pipeline.run(query, chunks)
    """
    return RetrievalPipeline(default_pipeline=pipeline_type)
