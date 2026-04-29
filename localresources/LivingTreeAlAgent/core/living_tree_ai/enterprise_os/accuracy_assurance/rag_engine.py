"""
RAG检索增强引擎 (RAG Engine)

Retrieval-Augmented Generation，用于：
1. 写作时检索最新法规、标准原文作为AI生成依据
2. 防止法规引用过时或错误
3. 确保技术结论有据可查

核心功能：
1. 知识库构建 - 法规、标准、技术规范入库
2. 向量检索 - 基于语义相似度检索
3. 混合检索 - 关键词+向量双重检索
4. 引用追踪 - 记录每个结论的依据来源
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Any, Tuple
import hashlib
import re


class KnowledgeDomain(Enum):
    """知识领域"""
    ENVIRONMENTAL = "environmental"           # 环境保护
    SAFETY = "safety"                          # 安全
    HEALTH = "health"                          # 职业卫生
    PLANNING = "planning"                      # 规划
    CONSTRUCTION = "construction"              # 建设
    CHEMICAL = "chemical"                      # 化工
    ENERGY = "energy"                          # 能源
    GENERAL = "general"                        # 综合


class DocumentType(Enum):
    """文档类型"""
    LAW = "law"                                # 法律
    REGULATION = "regulation"                  # 行政法规
    DEPARTMENT_RULE = "department_rule"         # 部门规章
    NATIONAL_STANDARD = "national_standard"   # 国家标准
    INDUSTRY_STANDARD = "industry_standard"    # 行业标准
    LOCAL_STANDARD = "local_standard"         # 地方标准
    TECHNICAL_GUIDELINE = "technical_guideline"  # 技术导则
    TECHNICAL_SPECIFICATION = "technical_specification"  # 技术规范
    POLICY = "policy"                          # 政策文件
    INTERPRETATION = "interpretation"          # 解读材料


class RetrievalMode(Enum):
    """检索模式"""
    SEMANTIC = "semantic"                     # 纯语义
    KEYWORD = "keyword"                       # 纯关键词
    HYBRID = "hybrid"                         # 混合


@dataclass
class KnowledgeChunk:
    """知识片段"""
    chunk_id: str
    domain: KnowledgeDomain

    # 来源
    source_type: DocumentType
    source_name: str                           # 法规/标准名称
    source_code: str                          # 标准编号（如GB 12345-2020）
    chapter: str = ""                          # 章节
    section: str = ""                          # 小节

    # 内容
    content: str                               # 原文内容
    summary: str = ""                         # 摘要
    keywords: List[str] = field(default_factory=list)

    # 位置
    article_number: Optional[str] = None      # 条款编号
    page_number: Optional[int] = None

    # 元数据
    issuing_authority: str = ""               # 发布机关
    issue_date: Optional[str] = None           # 发布日期
    effective_date: Optional[str] = None       # 生效日期
    is_current: bool = True                   # 是否现行有效

    # 向量（存储时计算）
    embedding: Optional[List[float]] = None

    # 统计
    retrieval_count: int = 0
    last_retrieved: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "domain": self.domain.value,
            "source_type": self.source_type.value,
            "source_name": self.source_name,
            "source_code": self.source_code,
            "chapter": self.chapter,
            "content_preview": self.content[:200] + "..." if len(self.content) > 200 else self.content,
            "keywords": self.keywords,
            "is_current": self.is_current,
            "retrieval_count": self.retrieval_count,
        }


@dataclass
class RegulationStandard:
    """法规标准（完整文档）"""
    doc_id: str
    domain: KnowledgeDomain
    doc_type: DocumentType

    # 基础信息
    name: str
    code: str                                  # 编号
    chinese_name: Optional[str] = None         # 中文名（如有英文名）
    english_name: Optional[str] = None         # 英文名

    # 分类
    category: str = ""                         # 类别
    subcategory: str = ""                      # 子类别

    # 状态
    is_current: bool = True
    is_mandatory: bool = False                # 是否强制性标准

    # 时间
    issue_date: Optional[str] None
    effective_date: Optional[str] = None
    expiry_date: Optional[str] = None

    # 发布
    issuing_authority: str = ""
    implementing_authority: Optional[str] = None  # 实施机关

    # 内容统计
    total_articles: int = 0
    total_chapters: int = 0
    total_pages: int = 0

    # 版本信息
    replaces: Optional[str] = None              # 替代的标准
    replaced_by: Optional[str] = None          # 被谁替代
    version_history: List[str] = field(default_factory=list)

    # 关联
    related_docs: List[str] = field(default_factory=list)  # 相关标准
    related_industries: List[str] = field(default_factory=list)  # 适用行业

    # 知识片段
    chunks: List[KnowledgeChunk] = field(default_factory=list)

    # 统计
    retrieval_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "name": self.name,
            "code": self.code,
            "domain": self.domain.value,
            "doc_type": self.doc_type.value,
            "is_current": self.is_current,
            "is_mandatory": self.is_mandatory,
            "issuing_authority": self.issuing_authority,
            "effective_date": self.effective_date,
        }


@dataclass
class RetrievedKnowledge:
    """检索到的知识"""
    chunk: KnowledgeChunk

    # 相关性
    relevance_score: float = 0.0              # 相关性得分
    retrieval_mode: RetrievalMode = RetrievalMode.HYBRID

    # 匹配信息
    matched_keywords: List[str] = field(default_factory=list)
    matched_embedding_terms: List[str] = field(default_factory=list)

    # 引用信息
    citation_format: str = ""                  # 引用格式
    paragraph_id: Optional[str] = None        # 段落ID

    # 使用信息
    used_in_document: Optional[str] = None    # 使用此知识的文档ID
    used_in_section: Optional[str] = None     # 使用在哪个章节


@dataclass
class RAGQuery:
    """RAG查询"""
    query_id: str
    query_text: str
    domain: Optional[KnowledgeDomain] = None

    # 检索控制
    retrieval_mode: RetrievalMode = RetrievalMode.HYBRID
    top_k: int = 5
    min_relevance: float = 0.6

    # 过滤条件
    doc_types: Optional[List[DocumentType]] = None
    is_current_only: bool = True
    issuing_authority: Optional[str] = None

    # 关键词
    keywords: List[str] = field(default_factory=list)

    # 上下文（用于上下文增强检索）
    context: Optional[str] = None

    # 时间范围
    date_from: Optional[str] = None
    date_to: Optional[str] = None

    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class RAGResult:
    """RAG检索结果"""
    query_id: str
    query_text: str

    # 检索结果
    retrieved_knowledge: List[RetrievedKnowledge] = field(default_factory=list)

    # 统计
    total_retrieved: int = 0
    semantic_retrieved: int = 0
    keyword_retrieved: int = 0

    # 处理信息
    processing_time_ms: float = 0.0
    retrieval_mode: RetrievalMode = RetrievalMode.HYBRID

    # 生成提示
    prompt_context: str = ""                   # 用于LLM的上下文

    # 来源摘要
    sources_summary: List[Dict[str, Any]] = field(default_factory=list)

    def build_citation_block(self) -> str:
        """构建引用块（用于文档）"""
        if not self.retrieved_knowledge:
            return ""

        citations = []
        for i, k in enumerate(self.retrieved_knowledge, 1):
            source = k.chunk.source_name
            code = k.chunk.source_code
            article = k.chunk.article_number or ""

            citation = f"[{i}] {source}"
            if code:
                citation += f" ({code})"
            if article:
                citation += f" 第{article}条"

            citations.append(citation)

        return "\n".join(citations)

    def to_prompt_context(self) -> str:
        """构建用于LLM的提示上下文"""
        if not self.retrieved_knowledge:
            return "未检索到相关法规标准，请基于通用知识生成。"

        context_parts = ["参考以下法规标准进行回答：\n"]

        for i, k in enumerate(self.retrieved_knowledge, 1):
            context_parts.append(f"\n【依据{i}】{k.chunk.source_name}")
            if k.chunk.source_code:
                context_parts.append(f"标准号：{k.chunk.source_code}")
            if k.chunk.article_number:
                context_parts.append(f"条款：{k.chunk.article_number}")
            context_parts.append(f"内容：{k.chunk.content[:500]}...")
            context_parts.append("")

        return "\n".join(context_parts)


class RAGEngine:
    """
    RAG检索增强引擎

    核心功能：
    1. 知识库管理 - 法规标准入库、索引
    2. 向量检索 - 基于语义相似度
    3. 关键词检索 - BM25等算法
    4. 混合检索 - 融合两者结果
    5. 引用生成 - 自动生成引用格式
    """

    # 内置知识库配置
    DEFAULT_KNOWLEDGE = {
        "environmental": [
            {
                "name": "中华人民共和国环境影响评价法",
                "code": "主席令第24号",
                "type": DocumentType.LAW,
                "authority": "全国人民代表大会常务委员会",
                "issue_date": "2002-10-28",
            },
            {
                "name": "建设项目环境影响评价分类管理名录",
                "code": "生态环境部令第16号",
                "type": DocumentType.DEPARTMENT_RULE,
                "authority": "生态环境部",
                "issue_date": "2021-01-01",
            },
        ],
        "safety": [
            {
                "name": "中华人民共和国安全生产法",
                "code": "主席令第88号",
                "type": DocumentType.LAW,
                "authority": "全国人民代表大会常务委员会",
                "issue_date": "2021-06-10",
            },
            {
                "name": "危险化学品安全管理条例",
                "code": "国务院令第645号",
                "type": DocumentType.REGULATION,
                "authority": "国务院",
                "issue_date": "2011-03-02",
            },
        ]
    }

    def __init__(self):
        # 知识库存储
        self._documents: Dict[str, RegulationStandard] = {}
        self._chunks: Dict[str, KnowledgeChunk] = {}

        # 向量索引（简化版，实际应使用FAISS等）
        self._embeddings: Dict[str, List[float]] = {}

        # 统计
        self._stats = {
            "total_retrievals": 0,
            "total_documents": 0,
            "total_chunks": 0,
            "domains": {},
        }

        # 初始化内置知识库
        self._init_default_knowledge()

    def _init_default_knowledge(self) -> None:
        """初始化内置知识库"""
        for domain_str, docs in self.DEFAULT_KNOWLEDGE.items():
            domain = KnowledgeDomain(domain_str)

            for doc_dict in docs:
                doc = RegulationStandard(
                    doc_id=f"DOC:{hashlib.md5(doc_dict['code'].encode()).hexdigest()[:8].upper()}",
                    domain=domain,
                    doc_type=doc_dict["type"],
                    name=doc_dict["name"],
                    code=doc_dict["code"],
                    issuing_authority=doc_dict["authority"],
                    issue_date=doc_dict["issue_date"],
                )

                self._documents[doc.doc_id] = doc

                # 创建默认chunk
                chunk = KnowledgeChunk(
                    chunk_id=f"CHUNK:{doc.doc_id}:001",
                    domain=domain,
                    source_type=doc.doc_type,
                    source_name=doc.name,
                    source_code=doc.code,
                    content=f"{doc.name}（{doc.code}）是{domain.value}领域的重要法规标准。",
                    keywords=[doc.name, doc.code],
                    is_current=True,
                )

                self._chunks[chunk.chunk_id] = chunk
                doc.chunks.append(chunk)

        self._stats["total_documents"] = len(self._documents)
        self._stats["total_chunks"] = len(self._chunks)

    async def add_document(self, doc: RegulationStandard) -> bool:
        """添加文档到知识库"""
        self._documents[doc.doc_id] = doc
        self._stats["total_documents"] += 1

        for chunk in doc.chunks:
            await self._add_chunk(chunk)

        return True

    async def add_chunk(self, chunk: KnowledgeChunk) -> bool:
        """添加知识片段"""
        return await self._add_chunk(chunk)

    async def _add_chunk(self, chunk: KnowledgeChunk) -> bool:
        """内部方法：添加知识片段"""
        self._chunks[chunk.chunk_id] = chunk
        self._stats["total_chunks"] += 1

        # 更新领域统计
        domain = chunk.domain.value
        if domain not in self._stats["domains"]:
            self._stats["domains"][domain] = 0
        self._stats["domains"][domain] += 1

        # 计算embedding（简化版，实际应调用embedding模型）
        chunk.embedding = self._compute_simple_embedding(chunk.content)
        self._embeddings[chunk.chunk_id] = chunk.embedding

        return True

    async def retrieve(self, query: RAGQuery) -> RAGResult:
        """
        检索知识

        Args:
            query: RAG查询

        Returns:
            RAGResult: 检索结果
        """
        result = RAGResult(
            query_id=query.query_id,
            query_text=query.query_text,
            retrieval_mode=query.retrieval_mode,
        )

        start_time = datetime.now()

        all_candidates: List[Tuple[RetrievedKnowledge, float]] = []

        # 1. 语义检索
        if query.retrieval_mode in [RetrievalMode.SEMANTIC, RetrievalMode.HYBRID]:
            query_embedding = self._compute_simple_embedding(query.query_text)
            semantic_results = await self._semantic_search(query_embedding, query.top_k * 2)
            all_candidates.extend(semantic_results)

        # 2. 关键词检索
        if query.retrieval_mode in [RetrievalMode.KEYWORD, RetrievalMode.HYBRID]:
            keywords = query.keywords or self._extract_keywords(query.query_text)
            keyword_results = await self._keyword_search(keywords, query.top_k * 2)
            all_candidates.extend(keyword_results)

        # 3. 去重和排序
        seen_chunks = set()
        scored_results: List[Tuple[RetrievedKnowledge, float]] = []

        for rk, score in all_candidates:
            if rk.chunk.chunk_id not in seen_chunks:
                seen_chunks.add(rk.chunk.chunk_id)
                scored_results.append((rk, score))

        # 按得分排序
        scored_results.sort(key=lambda x: x[1], reverse=True)

        # 4. 过滤和截取
        for rk, score in scored_results[:query.top_k]:
            if score >= query.min_relevance:
                # 检查过滤条件
                if query.doc_types and rk.chunk.source_type not in query.doc_types:
                    continue
                if query.is_current_only and not rk.chunk.is_current:
                    continue

                rk.relevance_score = score
                result.retrieved_knowledge.append(rk)

                # 更新检索统计
                rk.chunk.retrieval_count += 1
                rk.chunk.last_retrieved = datetime.now()

        # 5. 统计
        result.total_retrieved = len(result.retrieved_knowledge)
        result.semantic_retrieved = sum(1 for r in result.retrieved_knowledge if r.retrieval_mode in [RetrievalMode.SEMANTIC, RetrievalMode.HYBRID])
        result.keyword_retrieved = sum(1 for r in result.retrieved_knowledge if r.retrieval_mode in [RetrievalMode.KEYWORD, RetrievalMode.HYBRID])

        # 6. 生成上下文
        result.prompt_context = result.to_prompt_context()

        # 7. 来源摘要
        result.sources_summary = [
            {
                "source_name": r.chunk.source_name,
                "source_code": r.chunk.source_code,
                "relevance": round(r.relevance_score, 3),
                "content_preview": r.chunk.content[:100] + "...",
            }
            for r in result.retrieved_knowledge
        ]

        # 处理时间
        result.processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        self._stats["total_retrievals"] += 1

        return result

    async def _semantic_search(
        self,
        query_embedding: List[float],
        top_k: int
    ) -> List[Tuple[RetrievedKnowledge, float]]:
        """语义检索"""
        results = []

        for chunk_id, chunk_emb in self._embeddings.items():
            if not chunk_emb:
                continue

            # 计算余弦相似度
            similarity = self._cosine_similarity(query_embedding, chunk_emb)

            if similarity > 0.5:  # 相似度阈值
                chunk = self._chunks.get(chunk_id)
                if chunk:
                    rk = RetrievedKnowledge(
                        chunk=chunk,
                        relevance_score=similarity,
                        retrieval_mode=RetrievalMode.SEMANTIC,
                    )
                    results.append((rk, similarity))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    async def _keyword_search(
        self,
        keywords: List[str],
        top_k: int
    ) -> List[Tuple[RetrievedKnowledge, float]]:
        """关键词检索"""
        results = []

        for chunk_id, chunk in self._chunks.items():
            # 计算关键词匹配得分
            matched = []
            for kw in keywords:
                if kw.lower() in chunk.content.lower():
                    matched.append(kw)
                elif kw.lower() in chunk.keywords:
                    matched.append(kw)

            if matched:
                # TF-IDF风格的简单评分
                score = len(matched) / len(keywords) if keywords else 0

                rk = RetrievedKnowledge(
                    chunk=chunk,
                    relevance_score=score,
                    retrieval_mode=RetrievalMode.KEYWORD,
                    matched_keywords=matched,
                )
                results.append((rk, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def _compute_simple_embedding(self, text: str) -> List[float]:
        """简化版embedding计算（实际应调用embedding模型）"""
        # 基于词频的简单向量
        words = re.findall(r'\w+', text.lower())
        unique_words = set(words)

        # 简单的hash向量化
        embedding = []
        for i in range(128):  # 128维
            hash_val = hashlib.md5(f"dim_{i}_{text[i % len(text)] if text else ''}".encode()).hexdigest()
            embedding.append(float(int(hash_val[:8], 16)) / 0xFFFFFFFF)

        return embedding

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """计算余弦相似度"""
        if len(a) != len(b):
            return 0.0

        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        # 简单的关键词提取
        words = re.findall(r'\w{2,}', text.lower())

        # 停用词
        stopwords = {'的', '了', '和', '是', '在', '有', '与', '及', '或', '等', '对', '于', '为', '以', '及', '其'}

        keywords = [w for w in words if w not in stopwords and len(w) >= 2]

        # 返回高频词
        from collections import Counter
        counter = Counter(keywords)
        return [word for word, _ in counter.most_common(10)]

    async def get_document(self, doc_id: str) -> Optional[RegulationStandard]:
        """获取文档"""
        return self._documents.get(doc_id)

    async def list_documents(
        self,
        domain: Optional[KnowledgeDomain] = None,
        doc_type: Optional[DocumentType] = None,
        is_current: bool = True
    ) -> List[RegulationStandard]:
        """列出文档"""
        docs = list(self._documents.values())

        if domain:
            docs = [d for d in docs if d.domain == domain]
        if doc_type:
            docs = [d for d in docs if d.doc_type == doc_type]
        if is_current:
            docs = [d for d in docs if d.is_current]

        return docs

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self._stats,
            "retrieval_rate": self._stats["total_retrievals"] / max(1, self._stats["total_chunks"]),
        }


# 全局单例
_rag_engine: Optional[RAGEngine] = None


def get_rag_engine() -> RAGEngine:
    """获取RAG引擎单例"""
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = RAGEngine()
    return _rag_engine