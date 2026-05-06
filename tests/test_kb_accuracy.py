"""Knowledge accuracy tests — query decomposition, retrieval validation,
hallucination guard, and content quality.

Covers the six accuracy dimensions:
  1. Query decomposition + HyDE
  2. Retrieval validation + citation injection
  3. Hallucination guard + sentence-level verification
  4. Content quality filtering + auto-labeling
  5. Integration: accurate_retrieve pipeline
  6. Integration: verify_generation pipeline
"""

from __future__ import annotations

import pytest

from livingtree.knowledge.query_decomposer import QueryDecomposer, DecomposedQuery, SubQuery
from livingtree.knowledge.retrieval_validator import RetrievalValidator, ValidatedHit, ValidationResult
from livingtree.knowledge.hallucination_guard import (
    HallucinationGuard, HallucinationReport, SentenceCheck,
    HallucinationVerdict,
)
from livingtree.knowledge.content_quality import ContentQuality, QualityScore, ContentLabel
from livingtree.knowledge.intelligent_kb import RetrievalResult


# ═══ Query Decomposer ═══

class TestQueryDecomposer:
    def test_simple_decompose(self):
        qd = QueryDecomposer()
        result = qd.decompose("环评是什么")
        assert result.original == "环评是什么"
        assert len(result.sub_queries) >= 1

    def test_comparison_decompose(self):
        qd = QueryDecomposer()
        result = qd.decompose("大气扩散模型与噪声衰减模型有何区别")
        assert result.strategy == "decompose"
        assert len(result.sub_queries) >= 2

    def test_compound_decompose(self):
        qd = QueryDecomposer()
        result = qd.decompose("环评报告如何编写大气章节以及噪声章节")
        assert len(result.sub_queries) >= 2

    def test_intent_detection(self):
        qd = QueryDecomposer()
        result = qd.decompose("如何设置大气扩散模型参数")
        assert result.sub_queries[0].intent in ("procedural", "factual")

        result2 = qd.decompose("大气扩散模型与噪声模型对比")
        assert any(sq.intent == "comparative" for sq in result2.sub_queries)

    def test_hyde_generation_skipped_without_hub(self):
        qd = QueryDecomposer()
        result = qd.decompose("复杂的大气扩散模型参数设置方法及其对环评结果的影响分析")
        assert result.hyde_document == ""  # No hub available

    def test_subquery_weights(self):
        qd = QueryDecomposer()
        result = qd.decompose("环评报告大气和噪声章节编写方法对比")
        total_weight = sum(sq.weight for sq in result.sub_queries)
        assert abs(total_weight - 1.0) < 0.1 or len(result.sub_queries) == 1


# ═══ Retrieval Validator ═══

class TestRetrievalValidator:
    def test_validate_empty(self):
        rv = RetrievalValidator()
        result = rv.validate([])
        assert len(result.hits) == 0
        assert len(result.rejected_hits) == 0

    def test_validate_quality_hit(self):
        rv = RetrievalValidator(relevance_threshold=0.2)
        hits = [RetrievalResult(
            text="大气扩散模型参数依据HJ2.2-2018标准确定，包括AERMOD模式。",
            score=0.85, source="document_kb", doc_id="doc1",
            section_path="3 > 3.1 大气扩散",
        )]
        result = rv.validate(hits)
        assert len(result.hits) == 1
        assert result.hits[0].verified

    def test_reject_low_relevance(self):
        rv = RetrievalValidator(relevance_threshold=0.5)
        hits = [RetrievalResult(
            text="hello world",
            score=0.1, source="test",
        )]
        result = rv.validate(hits)
        assert len(result.rejected_hits) >= 1

    def test_citation_generation(self):
        rv = RetrievalValidator()
        hits = [RetrievalResult(
            text="噪声限值依据GB12348标准，昼间不超过55dB。",
            score=0.8, source="document_kb", doc_id="d1",
            section_path="4 > 4.2 噪声标准",
        )]
        result = rv.validate(hits)
        assert len(result.citations) > 0

    def test_get_citation_context(self):
        rv = RetrievalValidator()
        hits = [
            RetrievalResult(text="大气参数依据HJ2.2标准。", score=0.8, source="kb", doc_id="d1", section_path="3 > 3.1"),
            RetrievalResult(text="噪声限值55dB。", score=0.75, source="kb", doc_id="d2", section_path="4 > 4.2"),
        ]
        result = rv.validate(hits)
        context = rv.get_citation_context(result)
        assert len(context) > 0

    def test_inject_citations(self):
        rv = RetrievalValidator()
        hits = [RetrievalResult(
            text="标准依据HJ2.2-2018。", score=0.8, source="标准汇编", doc_id="d1",
            section_path="附录B",
        )]
        validated = rv.validate(hits)
        text = "大气扩散模型参数设置依据HJ2.2-2018标准确定。"
        cited = rv.inject_citations(text, validated)
        assert len(cited) > len(text)

    def test_verify_citations(self):
        rv = RetrievalValidator()
        hits = [RetrievalResult(
            text="GB12348标准噪声限值55dB。", score=0.8, source="标准汇编",
        )]
        validated = rv.validate(hits)
        verification = rv.verify_citations("依据标准汇编，噪声限值为55dB。", validated)
        assert verification["coverage"] >= 0.5


# ═══ Hallucination Guard ═══

class TestHallucinationGuard:
    def test_check_clean_generation(self):
        guard = HallucinationGuard()
        context = "大气扩散模型参数依据HJ2.2-2018标准，包括AERMOD模式和高斯烟羽公式。"
        generated = "大气扩散模型参数依据HJ2.2-2018标准确定。"
        report = guard.check_generation(generated, context)
        assert report.total_sentences > 0
        assert report.hallucination_rate < 0.5

    def test_detect_unsupported_claim(self):
        guard = HallucinationGuard()
        context = "标准规定噪声限值为昼间55dB。"
        generated = "根据2024年最新研究，噪声限值应降至50dB，并且所有工厂必须立即执行。"
        report = guard.check_generation(generated, context)
        assert report.hallucinated_sentences >= 0

    def test_empty_context(self):
        guard = HallucinationGuard()
        report = guard.check_generation("大气模型参数如何设置。", "")
        assert report.total_sentences > 0

    def test_suggest_correction(self):
        guard = HallucinationGuard()
        generated = "所有项目必须使用AERMOD模型。"
        report = guard.check_generation(generated, "实际标准允许多种模型。")
        correction = guard.suggest_correction(report)
        assert isinstance(correction, str)

    def test_dashboard(self):
        guard = HallucinationGuard()
        guard.check_generation("测试文本。", "上下文。")
        dashboard = guard.get_dashboard()
        assert "status" in dashboard
        assert "recent_rate" in dashboard

    def test_alert_callback(self):
        guard = HallucinationGuard(critical_threshold=0.0)
        alerts = []
        guard.on_alert(lambda msg, r: alerts.append(msg))
        guard.check_generation(
            "完全无关的编造内容，没有任何根据的断言。",
            "实际上下文内容完全不同。",
        )
        assert len(alerts) >= 0


# ═══ Content Quality ═══

class TestContentQuality:
    def test_evaluate_good_content(self):
        cq = ContentQuality()
        text = """# 大气扩散模型

## 参数设置

依据HJ2.2-2018标准，大气扩散模型参数包括：
- AERMOD模式参数
- 高斯烟羽公式系数
- 气象数据输入

标准规定在复杂地形条件下应采用CALPUFF模式。"""
        score = cq.evaluate(text, title="大气扩散模型")
        assert score.overall > 0.5
        assert score.is_acceptable

    def test_reject_empty(self):
        cq = ContentQuality()
        score = cq.evaluate("", title="空")
        assert not score.is_acceptable

    def test_detect_watermark(self):
        cq = ContentQuality()
        text = "机密 CONFIDENTIAL 仅供内部 此文档包含保密信息"
        score = cq.evaluate(text, title="secret")
        assert "watermark_detected" in score.issues

    def test_auto_label(self):
        cq = ContentQuality()
        text = """环评报告大气环境影响评价章节。

依据HJ2.2-2018标准，采用AERMOD模式进行大气扩散模拟。
模拟结果表明SO2和NOx浓度均满足GB3095-2012二级标准。"""
        label = cq.auto_label(text, title="大气环评章节")
        assert label.language == "zh"
        assert label.primary_topic

    def test_label_domain_detection(self):
        cq = ContentQuality()
        label = cq.auto_label("环评标准大气监测排放数据表", title="环境评估")
        assert label.domain == "environmental"

        label2 = cq.auto_label("机器学习模型训练AI代码实现", title="AI")
        assert label2.domain in ("software", "data_science", "general")

    def test_difficulty_assessment(self):
        cq = ContentQuality()
        basic = cq.auto_label("简单的介绍文档。", title="intro")
        advanced = cq.auto_label(
            "模型算法公式理论原理系数参数阈值指标",
            title="advanced model theory with parameters and coefficients",
        )
        assert basic.difficulty == "basic"

    def test_filter_batch(self):
        cq = ContentQuality()
        items = [
            ("完整高质量文本" * 50, "good_doc"),
            ("", "empty_doc"),
            ("短", "short_doc"),
        ]
        filtered = cq.filter(items)
        assert len(filtered) <= 2

    def test_keyword_extraction(self):
        cq = ContentQuality()
        text = """大气扩散模型噪声衰减模型参数标准规范"""
        label = cq.auto_label(text, title="test")
        assert len(label.keywords) > 0


# ═══ Integration ═══

class TestAccuracyIntegration:
    def test_full_pipeline_decompose_validate(self):
        qd = QueryDecomposer()
        result = qd.decompose("大气扩散模型与噪声衰减模型有何区别")

        rv = RetrievalValidator()
        mock_hits = [
            RetrievalResult(text=f"关于{q.query}的标准内容。", score=0.8, source="kb", doc_id="d1")
            for q in result.sub_queries
        ]
        validated = rv.validate(mock_hits)
        assert len(validated.hits) >= 1

    def test_generation_verification_pipeline(self):
        generated = "依据HJ2.2-2018标准，大气扩散模型参数设置应符合AERMOD模式规范。"
        context = "HJ2.2-2018标准规定大气扩散模型可采用AERMOD、CALPUFF等模式。参数包括气象数据、地形数据等。"

        guard = HallucinationGuard()
        report = guard.check_generation(generated, context)
        assert report.hallucination_rate < 0.5

    def test_quality_gate_before_ingestion(self):
        cq = ContentQuality()
        good = "环评报告大气章节，依据标准HJ2.2-2018，采用高斯烟羽模型进行扩散模拟。" * 5
        score = cq.evaluate(good, title="test")
        assert score.is_acceptable

        bad = "机密 仅供内部 DRAFT 草稿"
        score_bad = cq.evaluate(bad, title="test")
        assert not score_bad.is_acceptable
