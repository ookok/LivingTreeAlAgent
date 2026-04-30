"""
知识库智能路由器 (Knowledge Base Smart Router)

功能：
1. IntentClassifier - 意图分类（检索/定位/生成/混合）
2. QueryAnalyzer - 查询分析（复杂度/长度/类型）
3. KnowledgeRouter - 智能路由（多路并行）
4. ResultFuser - 结果融合（去重/排序）
5. ResultScorer - 结果评分（相关性/权威性/时效性）

架构：
    Query → IntentClassifier → QueryAnalyzer → KnowledgeRouter
                                                    │
                    ┌──────────────────────────────┼──────────────────────────────┐
                    ▼                              ▼                              ▼
            KnowledgeBaseLayer              PageIndex                   LLMWikiGenerator
                    │                              │                              │
                    └──────────────────────────────┴──────────────────────────────┘
                                                    │
                                                    ▼
                                              ResultFuser
                                                    │
                                                    ▼
                                              ResultScorer
                                                    │
                                                    ▼
                                               Final Results

Author: Hermes Desktop Team
"""

import re
import time
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed


# ============================================================
# Part 1: Intent Classification
# ============================================================

class QueryIntent(Enum):
    """查询意图类型"""
    RETRIEVAL = "retrieval"           # 简单事实检索
    LOCATE = "locate"                 # 文档定位
    GENERATE = "generate"             # 生成式探索
    HYBRID = "hybrid"                 # 组合查询
    UNKNOWN = "unknown"               # 未知


class IntentClassifier:
    """
    意图分类器

    根据查询特征识别用户意图：
    - 检索型：问事实、找定义（"什么是X"、"如何做Y"）
    - 定位型：找文档、找章节（"找XX文档"、"第N章"）
    - 生成型：分析、比较、总结（"分析XX趋势"、"比较X和Y"）
    - 混合型：包含多种意图
    """

    # 检索型关键词
    RETRIEVAL_PATTERNS = [
        r"什么是", r"怎么", r"如何", r"是不是", r"是不是",
        r"哪有", r"哪里", r"哪个", r"多少", r"多久",
        r"是什么", r"怎么做", r"告诉我", r"查一下", r"找一下", r"找.*安装",
        r"介绍一下", r"解释一下", r"说明一下",
    ]

    # 定位型关键词
    LOCATE_PATTERNS = [
        r"第.*章", r"第.*节", r"第.*页",
        r"找.*文档", r"找.*文件", r"找.*文章",
        r"在.*哪里", r"位于", r"位置",
        r"打开", r"定位", r"跳转到",
    ]

    # 生成型关键词
    GENERATE_PATTERNS = [
        r"分析", r"对比", r"比较", r"总结", r"概括",
        r"趋势", r"预测", r"展望", r"未来",
        r"报告", r"文档", r"生成", r"编写",
        r"区别", r"差异", r"优缺点", r"好处",
    ]

    # 混合型模式（多个意图关键词同时出现）
    HYBRID_PATTERNS = [
        r".*\+.*",  # "X+Y" 模式
        r".*和.*和.*",  # 多个并列
        r".*以及.*",  # X以及Y
        r".*并.*",  # X并Y
    ]

    def __init__(self):
        self.stats = {"total": 0, "distribution": {}}

    def classify(self, query: str) -> QueryIntent:
        """
        分类查询意图

        Args:
            query: 用户查询

        Returns:
            QueryIntent: 识别的意图类型
        """
        self.stats["total"] += 1
        query_lower = query.lower()

        # 首先检查是否为明确的混合模式
        for pattern in self.HYBRID_PATTERNS:
            if re.search(pattern, query_lower):
                self.stats["distribution"]["hybrid"] = self.stats["distribution"].get("hybrid", 0) + 1
                return QueryIntent.HYBRID

        # 计算各类型匹配分数
        retrieval_score = self._match_patterns(query_lower, self.RETRIEVAL_PATTERNS)
        locate_score = self._match_patterns(query_lower, self.LOCATE_PATTERNS)
        generate_score = self._match_patterns(query_lower, self.GENERATE_PATTERNS)

        scores = {
            QueryIntent.RETRIEVAL: retrieval_score,
            QueryIntent.LOCATE: locate_score,
            QueryIntent.GENERATE: generate_score,
        }

        # 判断是否为混合意图（多个类型都有匹配）
        matched_types = [k for k, v in scores.items() if v > 0]

        if len(matched_types) >= 2:
            intent = QueryIntent.HYBRID
        elif matched_types:
            intent = matched_types[0]
        else:
            intent = QueryIntent.UNKNOWN

        # 统计
        intent_name = intent.value
        self.stats["distribution"][intent_name] = self.stats["distribution"].get(intent_name, 0) + 1

        return intent

    def _match_patterns(self, query: str, patterns: List[str]) -> float:
        """计算模式匹配分数"""
        score = 0.0
        for pattern in patterns:
            if re.search(pattern, query):
                score += 1.0
        return score

    def get_stats(self) -> Dict[str, Any]:
        return self.stats


# ============================================================
# Part 2: Query Analysis
# ============================================================

@dataclass
class QueryAnalysis:
    """查询分析结果"""
    original: str
    normalized: str
    keywords: List[str]
    complexity: str  # "simple" / "medium" / "complex"
    length: int
    has_code: bool
    is_chinese: bool
    recommended_sources: List[str]  # 推荐的检索源


class QueryAnalyzer:
    """
    查询分析器

    分析查询特征，为路由提供依据：
    - 关键词提取
    - 复杂度评估
    - 语言检测
    - 代码检测
    """

    def __init__(self):
        # 停用词
        self.stopwords = set([
            "的", "了", "是", "在", "和", "与", "或", "的", "了", "吗", "呢",
            "the", "a", "an", "is", "are", "was", "were", "to", "of", "and",
        ])

        # 代码相关关键词
        self.code_keywords = set([
            "code", "代码", "函数", "class", "function", "method",
            "api", "api", "接口", "参数", "return", "import",
            "python", "javascript", "java", "cpp", "rust",
        ])

    def analyze(self, query: str) -> QueryAnalysis:
        """
        分析查询

        Args:
            query: 原始查询

        Returns:
            QueryAnalysis: 分析结果
        """
        # 基础特征
        length = len(query)
        is_chinese = bool(re.search(r'[\u4e00-\u9fff]', query))
        has_code = any(kw in query.lower() for kw in self.code_keywords)

        # 提取关键词
        keywords = self._extract_keywords(query)

        # 复杂度评估
        complexity = self._assess_complexity(query, length, keywords)

        # 推荐检索源
        recommended = self._recommend_sources(query, complexity, has_code)

        # 标准化
        normalized = self._normalize(query)

        return QueryAnalysis(
            original=query,
            normalized=normalized,
            keywords=keywords,
            complexity=complexity,
            length=length,
            has_code=has_code,
            is_chinese=is_chinese,
            recommended_sources=recommended
        )

    def _extract_keywords(self, query: str) -> List[str]:
        """提取关键词"""
        # 分词
        words = re.findall(r'[\w]+', query.lower())

        # 过滤停用词和短词
        keywords = [w for w in words if w not in self.stopwords and len(w) >= 2]

        return keywords[:10]  # 最多10个关键词

    def _assess_complexity(self, query: str, length: int, keywords: List[str]) -> str:
        """评估查询复杂度"""
        # 复杂度指标
        score = 0

        # 长度
        if length > 100:
            score += 2
        elif length > 50:
            score += 1

        # 关键词数
        if len(keywords) > 5:
            score += 2
        elif len(keywords) > 3:
            score += 1

        # 包含特殊模式
        if re.search(r'比较|对比|分析', query):
            score += 2
        if re.search(r'如果|假设|当.*时', query):
            score += 1

        # 判断
        if score >= 4:
            return "complex"
        elif score >= 2:
            return "medium"
        else:
            return "simple"

    def _recommend_sources(self, query: str, complexity: str, has_code: bool) -> List[str]:
        """推荐检索源"""
        sources = ["knowledge_base"]  # 默认

        if complexity == "complex":
            sources.append("llm_wiki")

        if has_code:
            sources.append("knowledge_base")  # 代码类文档

        # 检查是否需要文档定位
        if re.search(r'文档|文件|章节', query):
            sources.append("page_index")

        return sources

    def _normalize(self, query: str) -> str:
        """标准化查询"""
        # 去除多余空格
        query = re.sub(r'\s+', ' ', query).strip()
        return query


# ============================================================
# Part 3: Result Structure
# ============================================================

@dataclass
class ScoredResult:
    """评分结果"""
    content: str
    source: str  # "knowledge_base" / "page_index" / "llm_wiki"
    source_id: str
    title: str = ""
    score: float = 0.0
    relevance: float = 0.0
    authority: float = 0.0
    recency: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __lt__(self, other):
        return self.score < other.score


@dataclass
class RouterResponse:
    """路由器响应"""
    query: str
    intent: QueryIntent
    analysis: QueryAnalysis
    results: List[ScoredResult]
    total_time_ms: float
    sources_used: List[str]
    fusion_method: str = "rrf"  # Reciprocal Rank Fusion


# ============================================================
# Part 4: Knowledge Router
# ============================================================

class KnowledgeRouter:
    """
    知识库智能路由器

    核心功能：
    1. 多路并行检索
    2. 结果融合（RRF算法）
    3. 统一评分排序
    """

    def __init__(self):
        # 初始化各层
        self._init_knowledge_base()
        self._init_page_index()
        self._init_wiki_generator()

        # 分类器和分析器
        self.classifier = IntentClassifier()
        self.analyzer = QueryAnalyzer()

        # 并行执行器
        self.executor = ThreadPoolExecutor(max_workers=3)

        # 统计
        self.stats = {
            "total_queries": 0,
            "parallel_queries": 0,
            "avg_latency_ms": 0,
        }

    def _init_knowledge_base(self):
        """初始化知识库层"""
        try:
            from client.src.business.fusion_rag.knowledge_base import KnowledgeBaseLayer
            self.kb_layer = KnowledgeBaseLayer(
                embedding_model="BAAI/bge-small-zh",
                top_k=10,
                chunk_size=256,
            )
        except Exception as e:
            print(f"[Router] KB Layer init failed: {e}")
            self.kb_layer = None

    def _init_page_index(self):
        """初始化 PageIndex"""
        try:
            from client.src.business.page_index.index_builder import PageIndexBuilder
            self.page_index = PageIndexBuilder(
                chunk_size=200,
                tree_height=3,
                index_dir="~/.hermes-desktop/page_index"
            )
        except Exception as e:
            print(f"[Router] PageIndex init failed: {e}")
            self.page_index = None

    def _init_wiki_generator(self):
        """初始化 Wiki 生成器"""
        try:
            from client.src.business.deep_search_wiki.wiki_generator import WikiGenerator
            self.wiki_generator = WikiGenerator()
        except Exception as e:
            print(f"[Router] Wiki Generator init failed: {e}")
            self.wiki_generator = None

    async def route(self, query: str, top_k: int = 10) -> RouterResponse:
        """
        路由查询

        Args:
            query: 用户查询
            top_k: 返回结果数量

        Returns:
            RouterResponse: 路由响应
        """
        start_time = time.time()
        self.stats["total_queries"] += 1

        # Step 1: 意图分类
        intent = self.classifier.classify(query)

        # Step 2: 查询分析
        analysis = self.analyzer.analyze(query)

        # Step 3: 多路并行检索
        results = await self._parallel_search(query, intent, analysis)

        # Step 4: 结果融合
        fused_results = self._fuse_results(results, top_k)

        # Step 5: 评分排序
        scored_results = self._score_results(fused_results)

        total_time = (time.time() - start_time) * 1000
        self.stats["avg_latency_ms"] = (
            (self.stats["avg_latency_ms"] * (self.stats["total_queries"] - 1) + total_time)
            / self.stats["total_queries"]
        )

        return RouterResponse(
            query=query,
            intent=intent,
            analysis=analysis,
            results=scored_results,
            total_time_ms=total_time,
            sources_used=list(set(r.source for r in scored_results)),
        )

    async def _parallel_search(
        self,
        query: str,
        intent: QueryIntent,
        analysis: QueryAnalysis
    ) -> List[List[ScoredResult]]:
        """
        多路并行搜索

        根据意图选择要搜索的知识库：
        - 简单检索 → 主要 KB
        - 文档定位 → KB + PageIndex
        - 生成探索 → KB + Wiki
        - 混合 → 全搜
        """
        tasks = []

        # 决定搜索源
        search_kb = True
        search_page = False
        search_wiki = False

        if intent == QueryIntent.LOCATE:
            search_page = True
        elif intent == QueryIntent.GENERATE:
            search_wiki = True
        elif intent == QueryIntent.HYBRID:
            search_page = True
            search_wiki = True
        elif intent == QueryIntent.UNKNOWN:
            # 默认全搜
            search_page = True
            search_wiki = True

        self.stats["parallel_queries"] += 1

        # KB 搜索
        if search_kb and self.kb_layer:
            loop = asyncio.get_event_loop()
            tasks.append(loop.run_in_executor(
                self.executor,
                self._search_knowledge_base,
                query
            ))

        # PageIndex 搜索
        if search_page and self.page_index:
            loop = asyncio.get_event_loop()
            tasks.append(loop.run_in_executor(
                self.executor,
                self._search_page_index,
                query
            ))

        # Wiki 生成
        if search_wiki and self.wiki_generator:
            loop = asyncio.get_event_loop()
            tasks.append(loop.run_in_executor(
                self.executor,
                self._generate_wiki,
                query
            ))

        # 并行执行
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return [r if isinstance(r, list) else [] for r in results]
        else:
            return []

    def _search_knowledge_base(self, query: str) -> List[ScoredResult]:
        """搜索知识库"""
        if not self.kb_layer:
            return []

        try:
            results = self.kb_layer.search(query, top_k=10, alpha=0.6)
            return [
                ScoredResult(
                    content=r.get("content", "")[:500],
                    source="knowledge_base",
                    source_id=r.get("id", ""),
                    title=r.get("title", ""),
                    relevance=r.get("score", 0),
                    metadata={"type": r.get("type", "unknown")}
                )
                for r in results
            ]
        except Exception as e:
            print(f"[Router] KB search error: {e}")
            return []

    def _search_page_index(self, query: str) -> List[ScoredResult]:
        """搜索 PageIndex"""
        if not self.page_index:
            return []

        try:
            # 获取所有文档
            docs = self.page_index.list_documents()
            results = []

            for doc in docs[:5]:  # 限制数量
                # 在节点中搜索
                indexed = self.page_index.load_index(doc["doc_id"])
                if not indexed:
                    continue

                for node_id, node in indexed._nodes.items():
                    if any(kw in node.summary.lower() for kw in self.analyzer._extract_keywords(query)):
                        # 获取关联的 chunks
                        for chunk_id in node.chunk_ids[:2]:
                            if chunk_id in indexed._chunks:
                                chunk = indexed._chunks[chunk_id]
                                results.append(ScoredResult(
                                    content=chunk.text[:500],
                                    source="page_index",
                                    source_id=f"{doc['doc_id']}:{chunk_id}",
                                    title=doc.get("title", ""),
                                    relevance=0.7,
                                    metadata={"node_id": node_id}
                                ))

            return results[:10]
        except Exception as e:
            print(f"[Router] PageIndex search error: {e}")
            return []

    def _generate_wiki(self, query: str) -> List[ScoredResult]:
        """生成 Wiki"""
        if not self.wiki_generator:
            return []

        try:
            wiki = self.wiki_generator.generate(
                topic=query,
                use_search=False
            )

            md_content = wiki.to_markdown()

            return [
                ScoredResult(
                    content=md_content,
                    source="llm_wiki",
                    source_id=f"wiki_{hash(query) % 10000}",
                    title=f"Wiki: {query}",
                    relevance=wiki.confidence,
                    authority=wiki.credibility_avg / 100,
                    metadata={"sections": len(wiki.sections)}
                )
            ]
        except Exception as e:
            print(f"[Router] Wiki generation error: {e}")
            return []

    def _fuse_results(self, result_lists: List[List[ScoredResult]], top_k: int) -> List[ScoredResult]:
        """
        结果融合 - 使用 RRF (Reciprocal Rank Fusion)

        RRF 公式: score(d) = Σ 1/(k + rank(d))
        """
        if not result_lists:
            return []

        # 收集所有结果
        all_results = {}
        for results in result_lists:
            for i, r in enumerate(results):
                key = f"{r.source}:{r.source_id}"
                if key not in all_results:
                    all_results[key] = r
                    all_results[key].metadata["ranks"] = []
                all_results[key].metadata["ranks"].append(i + 1)

        # RRF 融合
        k = 60  # RRF 参数
        for key, result in all_results.items():
            ranks = result.metadata.get("ranks", [len(result.metadata.get("ranks", [1]))])
            rrf_score = sum(1 / (k + rank) for rank in ranks)
            result.metadata["rrf_score"] = rrf_score
            result.metadata["rank_count"] = len(ranks)

        # 排序
        sorted_results = sorted(
            all_results.values(),
            key=lambda x: x.metadata.get("rrf_score", 0),
            reverse=True
        )

        return sorted_results[:top_k]

    def _score_results(self, results: List[ScoredResult]) -> List[ScoredResult]:
        """
        结果评分

        综合评分 = 0.5 * 相关性 + 0.3 * 权威性 + 0.2 * 时效性
        """
        if not results:
            return results

        # 归一化
        max_relevance = max(r.relevance for r in results) if results else 1

        for r in results:
            # 基础评分
            r.score = (
                0.5 * (r.relevance / max_relevance if max_relevance > 0 else 0) +
                0.3 * r.authority +
                0.2 * r.recency
            )

            # 加入 RRF 分数
            r.score = 0.6 * r.score + 0.4 * r.metadata.get("rrf_score", r.score)

            # 来源权重
            source_weights = {
                "knowledge_base": 1.0,
                "page_index": 0.9,
                "llm_wiki": 0.8,
            }
            r.score *= source_weights.get(r.source, 0.8)

        # 最终排序
        results.sort(key=lambda x: x.score, reverse=True)

        return results

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "router": self.stats,
            "classifier": self.classifier.get_stats(),
        }


# ============================================================
# Part 5: Convenience Functions
# ============================================================

# 全局路由器实例
_router_instance: Optional[KnowledgeRouter] = None


def get_knowledge_router() -> KnowledgeRouter:
    """获取全局路由器实例"""
    global _router_instance
    if _router_instance is None:
        _router_instance = KnowledgeRouter()
    return _router_instance


async def smart_search(query: str, top_k: int = 10) -> RouterResponse:
    """
    便捷搜索接口

    Args:
        query: 查询文本
        top_k: 返回数量

    Returns:
        RouterResponse: 路由响应
    """
    router = get_knowledge_router()
    return await router.route(query, top_k)
