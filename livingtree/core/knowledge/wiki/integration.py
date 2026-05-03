"""
LivingTree Wiki 集成桥接模块
=============================

将 Wiki 知识库连接到外部系统（FusionRAG / VimRAG / DeepKE-LLM / SmartVectorStore）

功能：
- FusionRAG 行业治理（行业过滤、相关性打分、反馈学习）
- 方言词典（同义词扩展 + 术语规范化）
- 三重链验证（三级证据校验 + 不确定性标注）
- VimRAG 多模态记忆图（可选）
- SmartVectorStore 智能向量存储（可选，混合模式自动降级）
- 统一搜索管道：规范化 → 重写 → 分层检索 → 过滤 → 重排序 → 打分

所有外部依赖均为可选，不可用时自动降级为基础功能。

Author: LivingTreeAI Team
Version: 3.0.0 (精简桥接版)
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from loguru import logger

# Wiki 核心模块
from .models import DocumentChunk
from .parsers import LLMDocumentParser, PaperParser, CodeExtractor
from .kg_integrator import WikiKGIntegrator, create_wiki_kg_integrator

# ---------------------------------------------------------------------------
# 可选外部依赖（全部延迟导入）
# ---------------------------------------------------------------------------

_HAS_FUSION_RAG = False
_HAS_VIMRAG = False
_HAS_DEEPKE = False
_HAS_SMART_VS = False


def _check_optional_deps() -> None:
    """检测可选外部依赖的可用性"""
    global _HAS_FUSION_RAG, _HAS_VIMRAG, _HAS_DEEPKE, _HAS_SMART_VS
    try:
        from business.fusion_rag.knowledge_base import KnowledgeBaseLayer
        _HAS_FUSION_RAG = True
    except ImportError:
        pass
    try:
        from business.memory_graph_engine import get_memory_graph_engine
        _HAS_VIMRAG = True
    except ImportError:
        pass
    try:
        from business.fusion_rag import get_term_extractor
        _HAS_DEEPKE = True
    except ImportError:
        pass
    try:
        from business.fusion_rag.smart_vector_store import get_smart_vector_store
        _HAS_SMART_VS = True
    except ImportError:
        pass


_check_optional_deps()


# ============================================================================
# 方言词典
# ============================================================================

class DialectDict:
    """
    行业方言词典

    功能：
    - 同义词扩展：查询词 → 扩展同义词列表
    - 术语规范化：口语化表达 → 标准术语
    - 缩写还原：LLM → Large Language Model
    """

    # 内置词典
    _SYNONYMS: Dict[str, List[str]] = {
        # AI/ML 领域
        "大模型": ["LLM", "大语言模型", "foundation model", "基座模型"],
        "微调": ["fine-tuning", "fine tuning", "指令微调", "SFT"],
        "RAG": ["检索增强生成", "retrieval-augmented generation"],
        "Agent": ["智能体", "AI代理", "autonomous agent"],
        "向量数据库": ["vector database", "vectorDB", "向量存储"],
        # 通用
        "优化": ["性能优化", "optimization", "调优"],
        "部署": ["deployment", "上线", "发布"],
    }

    # 缩写还原
    _ABBREVIATIONS: Dict[str, str] = {
        "rag": "Retrieval-Augmented Generation",
        "llm": "Large Language Model",
        "gpu": "Graphics Processing Unit",
        "api": "Application Programming Interface",
        "sdk": "Software Development Kit",
        "db": "Database",
    }

    def expand_query(self, query: str) -> List[str]:
        """扩展查询词 → 返回所有同义词变体"""
        expanded = [query]
        query_lower = query.lower().strip()

        for key, synonyms in self._SYNONYMS.items():
            if key.lower() in query_lower or any(s.lower() in query_lower for s in synonyms):
                expanded.extend(synonyms)

        # 缩写还原
        for abbr, full in self._ABBREVIATIONS.items():
            if abbr in query_lower:
                expanded.append(full)

        return list(set(expanded))

    def normalize_term(self, term: str) -> str:
        """将术语规范化为标准形式"""
        term_lower = term.lower().strip()
        for key, synonyms in self._SYNONYMS.items():
            if term_lower == key.lower() or term_lower in [s.lower() for s in synonyms]:
                return key
        return term


# ============================================================================
# 行业治理管道
# ============================================================================

class IndustryGovernance:
    """
    行业治理管道 —— 对等 FusionRAG 的四层治理架构

    管道流程:
    query → normalize → rewrite → tier_search → filter → rerank → score
    """

    def __init__(
        self,
        target_industry: str = "通用",
        min_relevance: float = 0.6,
    ):
        self.target_industry = target_industry
        self.min_relevance = min_relevance
        self.dialect = DialectDict()

        # 行业关键词（用于过滤）
        self._industry_keywords: Dict[str, List[str]] = {
            "AI": ["人工智能", "机器学习", "深度学习", "LLM", "神经网络"],
            "金融": ["风控", "量化", "交易", "信贷", "支付"],
            "医疗": ["诊断", "病历", "影像", "药物", "临床"],
            "环保": ["碳排放", "碳中和", "监测", "排放因子", "合规"],
        }

    def normalize_query(self, query: str) -> str:
        """查询规范化：去除冗余、统一大小写、术语标准化"""
        query = query.strip()
        # 去除多余标点
        query = re.sub(r"[，,。\.！!？?]+$", "", query)
        return query

    def expand_query(self, query: str) -> List[str]:
        """同义词扩展"""
        return self.dialect.expand_query(query)

    def is_industry_relevant(self, text: str) -> bool:
        """判断内容是否与目标行业相关"""
        if self.target_industry == "通用":
            return True
        keywords = self._industry_keywords.get(self.target_industry, [])
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in keywords)

    def score_relevance(self, query: str, content: str) -> float:
        """
        相关性打分

        综合评分因素：
        - 关键词匹配度
        - 行业相关性
        - 内容新鲜度（基于长度的启发式）
        """
        score = 0.0

        # 关键词匹配
        query_terms = set(query.lower().split())
        content_lower = content.lower()
        matches = sum(1 for t in query_terms if t in content_lower)
        if query_terms:
            score += (matches / len(query_terms)) * 0.6

        # 行业相关加分
        if self.is_industry_relevant(content):
            score += 0.2

        # 长度惩罚（太短或太长都降分）
        content_len = len(content)
        if 100 < content_len < 2000:
            score += 0.2
        elif content_len > 0:
            score += 0.1

        return min(score, 1.0)

    def filter_by_industry(
        self, items: List[Dict[str, Any]], content_key: str = "content"
    ) -> List[Dict[str, Any]]:
        """按行业过滤"""
        if self.target_industry == "通用":
            return items
        return [
            item
            for item in items
            if self.is_industry_relevant(item.get(content_key, ""))
        ]

    def rerank(
        self, query: str, items: List[Dict[str, Any]], content_key: str = "content"
    ) -> List[Tuple[Dict[str, Any], float]]:
        """重排序：按相关性打分排序"""
        scored = [
            (item, self.score_relevance(query, item.get(content_key, "")))
            for item in items
        ]
        scored.sort(key=lambda x: -x[1])
        return [(item, score) for item, score in scored if score >= self.min_relevance]

    def search_pipeline(
        self,
        query: str,
        items: List[Dict[str, Any]],
        content_key: str = "content",
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        完整搜索管道

        1. 规范化查询
        2. 同义词扩展
        3. 行业过滤
        4. 相关性打分
        5. 排序截断
        """
        query = self.normalize_query(query)
        filtered = self.filter_by_industry(items, content_key)
        ranked = self.rerank(query, filtered, content_key)
        return [item for item, _ in ranked[:top_k]]


# ============================================================================
# 三重链验证
# ============================================================================

class TripleChainVerifier:
    """
    三重链验证引擎

    三级证据验证：
    1. 直接匹配（一级）：查询词直接出现在文档中
    2. 语义相关（二级）：查询语义与内容相关
    3. 推理验证（三级）：知识图谱路径验证

    每级证据有置信度评分，最终输出不确定性标注。
    """

    # 验证等级
    LEVEL_DIRECT = 1        # 直接证据
    LEVEL_SEMANTIC = 2      # 语义证据
    LEVEL_INFERENCE = 3     # 推理证据

    def verify(
        self,
        query: str,
        items: List[Dict[str, Any]],
        kg_integrator: Optional[WikiKGIntegrator] = None,
    ) -> List[Dict[str, Any]]:
        """
        三重链验证

        Returns:
            每个 item 增加:
            - verification_level: 证据等级 (1-3)
            - confidence: 置信度 (0-1)
            - uncertainty_note: 不确定性说明
        """
        results = []
        for item in items:
            content = item.get("content", "")
            level = self.LEVEL_DIRECT
            confidence = 0.3

            # 一级：直接匹配
            if query.lower() in content.lower():
                level = self.LEVEL_DIRECT
                confidence = 0.9

            # 二级：语义相关（关键词重合度）
            query_terms = set(query.lower().split())
            content_terms = set(content.lower().split())
            overlap = len(query_terms & content_terms)
            if overlap > 0 and level < self.LEVEL_SEMANTIC:
                level = self.LEVEL_SEMANTIC
                confidence = min(0.5 + overlap * 0.1, 0.8)

            # 三级：知识图谱验证
            if kg_integrator:
                related = kg_integrator.query_related_concepts(
                    query, max_depth=2
                )
                if related and level < self.LEVEL_INFERENCE:
                    level = self.LEVEL_INFERENCE
                    confidence = min(0.6 + len(related) * 0.05, 0.95)

            # 不确定性标注
            uncertainty = self._assess_uncertainty(level, confidence, content)

            item["verification_level"] = level
            item["confidence"] = confidence
            item["uncertainty_note"] = uncertainty
            results.append(item)

        # 按验证等级和置信度排序
        results.sort(key=lambda x: (x["verification_level"], x["confidence"]), reverse=True)
        return results

    @staticmethod
    def _assess_uncertainty(level: int, confidence: float, content: str) -> str:
        """评估不确定性"""
        if level >= 3 and confidence > 0.8:
            return "高置信度（多级证据验证通过）"
        elif level >= 2 and confidence > 0.6:
            return "中等置信度（语义证据支持）"
        elif level == 1:
            return "基础置信度（仅直接匹配）"
        else:
            return "低置信度（证据不足，建议进一步确认）"


# ============================================================================
# 主集成桥接类
# ============================================================================

class WikiIntegrationBridge:
    """
    Wiki 集成桥接器 —— 连接 Wiki 知识库与外部生态系统

    用法:
        bridge = WikiIntegrationBridge(industry="AI")
        bridge.index_document("path/to/doc.md")

        # 统一搜索
        results = bridge.search("什么是RAG?", top_k=10)

        # 验证搜索
        verified = bridge.search_with_verification("微调参数建议")

        # 添加反馈
        bridge.add_learner_feedback(query="...", response="...", rating=4)
    """

    def __init__(
        self,
        industry: str = "通用",
        enable_kg: bool = True,
        enable_evorag: bool = True,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Args:
            industry: 目标行业（用于治理过滤）
            enable_kg: 是否启用知识图谱整合
            enable_evorag: 是否启用 EvoRAG
            config: 额外配置
        """
        self.config = config or {}
        self.industry = industry

        # 行业治理
        self.governance = IndustryGovernance(
            target_industry=industry,
            min_relevance=self.config.get("min_relevance", 0.6),
        )

        # 方言词典
        self.dialect = DialectDict()

        # 三重链验证
        self.verifier = TripleChainVerifier()

        # 知识图谱整合器
        self.kg_integrator: Optional[WikiKGIntegrator] = None
        if enable_kg:
            self.kg_integrator = create_wiki_kg_integrator(
                domain=f"wiki_{industry}",
                enable_evorag=enable_evorag,
            )

        # FusionRAG 组件（可选）
        self._fusion_kb: Any = None      # KnowledgeBaseLayer
        self._fusion_engine: Any = None  # FusionEngine
        self._term_extractor: Any = None # DeepKE-LLM

        # VimRAG 组件（可选）
        self._memory_graph: Any = None

        # 向量存储（可选）
        self._vector_store: Any = None

        # 反馈学习
        self._feedback_history: List[Dict[str, Any]] = []

        # 初始化可选组件
        self._init_optional_components()

        logger.info(
            f"WikiIntegrationBridge 初始化完成 "
            f"(industry={industry}, kg={enable_kg}, evorag={enable_evorag}, "
            f"fusion_rag={_HAS_FUSION_RAG}, vimrag={_HAS_VIMRAG})"
        )

    def _init_optional_components(self) -> None:
        """初始化可选的外部组件"""
        if _HAS_FUSION_RAG:
            try:
                from business.fusion_rag.knowledge_base import KnowledgeBaseLayer
                self._fusion_kb = KnowledgeBaseLayer()
                logger.info("FusionRAG KnowledgeBaseLayer 已连接")
            except Exception as e:
                logger.warning(f"FusionRAG 初始化失败: {e}")

        if _HAS_VIMRAG:
            try:
                from business.memory_graph_engine import get_memory_graph_engine
                self._memory_graph = get_memory_graph_engine()
                logger.info("VimRAG 记忆图引擎已连接")
            except Exception as e:
                logger.warning(f"VimRAG 初始化失败: {e}")

        if _HAS_DEEPKE:
            try:
                from business.fusion_rag import get_term_extractor
                self._term_extractor = get_term_extractor()
                logger.info("DeepKE-LLM 术语抽取器已连接")
            except Exception as e:
                logger.warning(f"DeepKE-LLM 初始化失败: {e}")

        if _HAS_SMART_VS:
            try:
                from business.fusion_rag.smart_vector_store import get_smart_vector_store
                self._vector_store = get_smart_vector_store()
                vs_info = self._vector_store.get_backend_info()
                logger.info(f"SmartVectorStore 已连接, 后端: {vs_info.name}")
            except Exception as e:
                logger.warning(f"SmartVectorStore 初始化失败: {e}")

    # ── 文档索引 ──────────────────────────────────────────

    def index_document(self, file_path: str) -> List[DocumentChunk]:
        """
        索引单个文档

        流程: 解析 → 知识图谱集成 → FusionRAG 索引（可选） → 向量存储（可选）
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        # 解析文档
        parser = LLMDocumentParser()
        chunks = parser.parse_file(str(path))
        logger.info(f"解析文档 {path.name}: {len(chunks)} 块")

        # 集成到知识图谱
        if self.kg_integrator:
            self.kg_integrator.integrate_chunks(chunks)

        # 索引到 FusionRAG（可选）
        if self._fusion_kb:
            for chunk in chunks:
                try:
                    self._fusion_kb.add_document(
                        content=chunk.content,
                        metadata={
                            "source": chunk.source,
                            "title": chunk.title,
                            "section": getattr(chunk, "section", ""),
                        },
                    )
                except Exception as e:
                    logger.warning(f"FusionRAG 索引失败: {e}")

        # 索引到向量存储（可选）
        if self._vector_store:
            try:
                texts = [c.content for c in chunks]
                metadatas = [{"source": c.source, "title": c.title} for c in chunks]
                self._vector_store.add_texts(texts, metadatas)
            except Exception as e:
                logger.warning(f"向量存储索引失败: {e}")

        return chunks

    def index_directory(self, dir_path: str, pattern: str = "*.md") -> int:
        """
        批量索引目录下的文档

        Returns:
            索引的文档数量
        """
        path = Path(dir_path)
        if not path.is_dir():
            raise NotADirectoryError(f"目录不存在: {dir_path}")

        files = list(path.glob(pattern))
        count = 0
        for f in files:
            try:
                self.index_document(str(f))
                count += 1
            except Exception as e:
                logger.warning(f"索引失败 {f}: {e}")

        logger.info(f"批量索引完成: {count}/{len(files)} 个文档")
        return count

    # ── 搜索 ──────────────────────────────────────────────

    def search(
        self,
        query: str,
        top_k: int = 10,
        use_kg: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        统一搜索入口 —— 多源融合

        搜索源（按优先级）：
        1. 知识图谱语义搜索
        2. 混合优先级检索（EvoRAG）
        3. FusionRAG 检索（可选）
        4. 向量存储检索（可选）

        所有结果经行业治理管道过滤、打分、排序。
        """
        all_items: List[Dict[str, Any]] = []

        # 1. 知识图谱搜索
        if use_kg and self.kg_integrator:
            # 语义搜索
            entities = self.kg_integrator.graph.search(query)
            for entity, score in entities[:top_k * 2]:
                all_items.append({
                    "source": "kg",
                    "content": entity.description,
                    "title": entity.name,
                    "type": entity.type.value,
                    "score": score,
                })

            # EvoRAG 混合检索
            if self.kg_integrator.hybrid_retriever:
                evorag_results = self.kg_integrator.hybrid_retrieve(query, top_k)
                for r in evorag_results:
                    all_items.append({
                        "source": "evorag",
                        "content": f"{r.head} → {r.tail}",
                        "title": r.head,
                        "relation": r.relation,
                        "score": r.hybrid_priority,
                    })

        # 2. FusionRAG 检索（可选）
        if self._fusion_engine:
            try:
                fusion_results = self._fusion_engine.search(query, top_k)
                for r in fusion_results:
                    all_items.append({
                        "source": "fusion_rag",
                        "content": r.get("content", ""),
                        "title": r.get("title", ""),
                        "score": r.get("score", 0.5),
                    })
            except Exception as e:
                logger.warning(f"FusionRAG 搜索失败: {e}")

        # 3. 向量存储检索（可选）
        if self._vector_store:
            try:
                vs_results = self._vector_store.search(query, top_k)
                for r in vs_results:
                    all_items.append({
                        "source": "vector_store",
                        "content": r.get("content", ""),
                        "score": r.get("score", 0.5),
                    })
            except Exception as e:
                logger.warning(f"向量存储搜索失败: {e}")

        # 4. 行业治理管道处理
        filtered = self.governance.filter_by_industry(all_items)
        ranked = self.governance.rerank(query, filtered)

        return [
            {"rank": i + 1, **item, "relevance": score}
            for i, (item, score) in enumerate(ranked[:top_k])
        ]

    def search_with_verification(
        self, query: str, top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        搜索 + 三重链验证

        返回验证后的结果，包含置信度和不确定性标注
        """
        results = self.search(query, top_k)
        return self.verifier.verify(query, results, self.kg_integrator)

    # ── 反馈学习 ──────────────────────────────────────────

    def add_feedback(
        self,
        query: str,
        response: str,
        rating: int,  # 1-5
        comment: str = "",
    ) -> None:
        """
        添加用户反馈 —— 驱动 EvoRAG 自进化

        Args:
            query: 用户查询
            response: 系统回答
            rating: 评分 (1-5)
            comment: 反馈备注
        """
        feedback_entry = {
            "query": query,
            "response": response,
            "rating": rating,
            "comment": comment,
            "timestamp": __import__("datetime").datetime.now().isoformat(),
        }
        self._feedback_history.append(feedback_entry)

        # 同步到 EvoRAG
        if self.kg_integrator and self.kg_integrator.feedback_manager:
            paths: List[List[str]] = []  # 简化版：无路径信息
            self.kg_integrator.add_feedback(
                query=query,
                response=response,
                paths=paths,
                feedback_score=float(rating),
                feedback_type="human",
            )

        logger.info(f"反馈已记录: rating={rating}, query='{query[:50]}...'")

    def get_feedback_stats(self) -> Dict[str, Any]:
        """获取反馈统计"""
        if not self._feedback_history:
            return {"total": 0, "avg_rating": 0.0}

        ratings = [e["rating"] for e in self._feedback_history]
        return {
            "total": len(self._feedback_history),
            "avg_rating": sum(ratings) / len(ratings),
            "positive_ratio": sum(1 for r in ratings if r >= 4) / len(ratings),
        }

    # ── 状态与诊断 ────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        """获取集成桥接器状态"""
        return {
            "industry": self.industry,
            "components": {
                "knowledge_graph": self.kg_integrator is not None,
                "fusion_rag": self._fusion_kb is not None,
                "vimrag": self._memory_graph is not None,
                "deepke_llm": self._term_extractor is not None,
                "vector_store": self._vector_store is not None,
            },
            "feedback": self.get_feedback_stats(),
            "kg_stats": (
                self.kg_integrator.get_performance_stats()
                if self.kg_integrator
                else None
            ),
            "evorag_stats": (
                self.kg_integrator.get_evorag_stats()
                if self.kg_integrator
                else None
            ),
        }


# ============================================================================
# 便捷工厂
# ============================================================================

def create_integration_bridge(
    industry: str = "通用",
    enable_kg: bool = True,
    enable_evorag: bool = True,
    **kwargs,
) -> WikiIntegrationBridge:
    """创建集成桥接器"""
    return WikiIntegrationBridge(
        industry=industry,
        enable_kg=enable_kg,
        enable_evorag=enable_evorag,
        config=kwargs,
    )


__all__ = [
    "WikiIntegrationBridge",
    "IndustryGovernance",
    "DialectDict",
    "TripleChainVerifier",
    "create_integration_bridge",
]
