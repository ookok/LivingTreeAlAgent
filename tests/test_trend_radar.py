"""Trend Radar tests — multi-platform trend aggregation + smart filtering.

Tests:
  - TrendClassifier: domain-aware keyword matching
  - TrendItem: composite scoring
  - TrendRadar: scanning, reporting, caching
  - Integration: report generation
"""

from __future__ import annotations

import time
import pytest
import asyncio

from livingtree.capability.trend_radar import (
    TrendRadar, TrendClassifier, TrendItem, TrendReport,
    TrendSource, TrendDomain, get_trend_radar,
)


# ═══ TrendClassifier ═══

class TestTrendClassifier:
    def test_classify_environment(self):
        tc = TrendClassifier()
        domain, score, keywords = tc.classify("大气扩散模型参数设置方法", "HJ2.2-2018标准")
        assert domain == TrendDomain.ENVIRONMENT
        assert score > 0

    def test_classify_ai(self):
        tc = TrendClassifier()
        domain, score, keywords = tc.classify("DeepSeek发布新版本大模型", "LLM推理性能提升")
        assert domain == TrendDomain.AI_MODEL
        assert score > 0

    def test_classify_engineering(self):
        tc = TrendClassifier()
        domain, score, keywords = tc.classify("Docker部署微服务架构", "Kubernetes编排")
        assert domain == TrendDomain.ENGINEERING
        assert score > 0

    def test_classify_general(self):
        tc = TrendClassifier()
        domain, score, keywords = tc.classify("今天天气很好", "")
        assert score < 0.5

    def test_get_monitoring_keywords(self):
        tc = TrendClassifier()
        keywords = tc.get_monitoring_keywords()
        assert len(keywords) > 20

    def test_get_domain_keywords(self):
        tc = TrendClassifier()
        env_kw = tc.get_monitoring_keywords([TrendDomain.ENVIRONMENT])
        ai_kw = tc.get_monitoring_keywords([TrendDomain.AI_MODEL])
        assert len(env_kw) > 0
        assert len(ai_kw) > 0
        assert len(set(env_kw) | set(ai_kw)) > 0


# ═══ TrendItem ═══

class TestTrendItem:
    def test_composite_score(self):
        item = TrendItem(
            id="test_1", title="Test", source="github",
            heat_score=80, relevance_score=0.5,
        )
        assert item.composite_score == pytest.approx(40.0)

    def test_is_high_value(self):
        high = TrendItem(id="h", title="H", source="test", heat_score=80, relevance_score=0.5)
        low = TrendItem(id="l", title="L", source="test", heat_score=10, relevance_score=0.1)
        assert high.is_high_value
        assert not low.is_high_value


# ═══ TrendRadar ═══

class TestTrendRadar:
    @pytest.mark.asyncio
    async def test_initialize(self):
        radar = TrendRadar()
        await radar.initialize()
        stats = radar.get_stats()
        assert "total_items" in stats

    @pytest.mark.asyncio
    async def test_scan_github(self):
        radar = TrendRadar()
        await radar.initialize()
        items = await radar._scan_github(["AI", "model", "大模型"])
        assert isinstance(items, list)

    def test_top_trends(self):
        radar = TrendRadar()
        radar._items = [
            TrendItem(id="a", title="A", source="test", heat_score=90, relevance_score=0.9, domain=TrendDomain.AI_MODEL),
            TrendItem(id="b", title="B", source="test", heat_score=80, relevance_score=0.8, domain=TrendDomain.ENVIRONMENT),
            TrendItem(id="c", title="C", source="test", heat_score=10, relevance_score=0.1, domain=TrendDomain.GENERAL),
        ]
        top = radar.top_trends(min_composite=30, limit=5)
        assert len(top) == 2

    def test_generate_report(self):
        radar = TrendRadar()
        radar._items = [
            TrendItem(id="1", title="大气新标准发布", source="github", heat_score=85,
                     relevance_score=0.9, domain=TrendDomain.ENVIRONMENT, summary="HJ2.2更新"),
            TrendItem(id="2", title="DeepSeek V4发布", source="github", heat_score=95,
                     relevance_score=0.95, domain=TrendDomain.AI_MODEL, summary="最新大模型"),
            TrendItem(id="3", title="天气", source="test", heat_score=5,
                     relevance_score=0.05, domain=TrendDomain.GENERAL),
        ]
        report = radar.generate_report(period="daily")
        assert report.total_items == 3
        assert report.high_value_items == 2
        assert len(report.recommendations) > 0
        assert len(report.raw_text) > 0

    def test_report_format(self):
        radar = TrendRadar()
        radar._items = [
            TrendItem(id="1", title="环保新政", source="test", heat_score=90,
                     relevance_score=1.0, domain=TrendDomain.ENVIRONMENT,
                     summary="新政策出台", url="https://example.com"),
        ]
        report = radar.generate_report()
        text = report.raw_text
        assert "环保新政" in text
        assert "https://example.com" in text

    def test_singleton(self):
        r1 = get_trend_radar()
        r2 = get_trend_radar()
        assert r1 is r2

    def test_stats(self):
        radar = TrendRadar()
        stats = radar.get_stats()
        assert stats["total_items"] == 0
        assert stats["scan_count"] == 0


# ═══ Integration ═══

class TestIntegration:
    @pytest.mark.asyncio
    async def test_scan_and_report_pipeline(self):
        """Full pipeline: init → scan → filter → report."""
        radar = TrendRadar()
        await radar.initialize()

        items = await radar.scan(sources=[TrendSource.GITHUB])
        assert isinstance(items, list)

        top = radar.top_trends(limit=5)
        assert isinstance(top, list)

        report = radar.generate_report(items, period="daily")
        assert isinstance(report, TrendReport)
        assert report.title

    def test_classifier_coverage(self):
        """All domains should have keyword coverage."""
        tc = TrendClassifier()
        for domain in TrendDomain:
            if domain == TrendDomain.GENERAL:
                continue
            keywords = tc.get_monitoring_keywords([domain])
            assert len(keywords) > 0, f"{domain.value} has no keywords"

    def test_cache_roundtrip(self):
        """Items should survive save/load."""
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            radar = TrendRadar(cache_dir=tmpdir)
            radar._items = [
                TrendItem(id="test", title="Test Trend", source="test",
                         heat_score=90, relevance_score=0.9, domain=TrendDomain.AI_MODEL),
            ]
            radar._save_cache()

            radar2 = TrendRadar(cache_dir=tmpdir)
            radar2._load_cache()
            assert len(radar2._items) == 1
            assert radar2._items[0].title == "Test Trend"


# ═══ Horizon-inspired Features ═══

class TestHorizonFeatures:
    def test_ai_score_field(self):
        item = TrendItem(id='t', title='Test', source='test')
        item.ai_score = 8.5
        item.ai_reason = "important"
        assert item.ai_score == 8.5

    def test_composite_score_with_ai(self):
        item = TrendItem(id='t', title='T', source='test', heat_score=50, relevance_score=0.5)
        item.ai_score = 8.0
        assert item.composite_score > 30  # AI boost applies

    def test_parse_scores_json(self):
        radar = TrendRadar()
        response = '[{"score":7,"reason":"relevant"},{"score":3,"reason":"no"}]'
        scores = radar._parse_scores(response, 2)
        assert scores[0][0] == 7
        assert scores[1][0] == 3

    def test_parse_scores_fallback_numbers(self):
        radar = TrendRadar()
        scores = radar._parse_scores("scores: 5, 8, 2", 3)
        assert scores[0][0] == 5

    def test_dedup_removes_duplicates(self):
        radar = TrendRadar()
        items = [
            TrendItem(id='a', title='DeepSeek V4 Released', source='github', heat_score=90),
            TrendItem(id='b', title='DeepSeek V4 发布', source='hackernews', heat_score=85),
            TrendItem(id='c', title='Unrelated News', source='test', heat_score=50),
        ]
        result = radar.dedup_trends(items)
        assert len(result) < 3

    def test_dedup_keeps_higher_score(self):
        radar = TrendRadar()
        high = TrendItem(id='high', title='Important AI News Today', source='github', heat_score=95)
        low = TrendItem(id='low', title='Important AI News Today', source='reddit', heat_score=60)
        result = radar.dedup_trends([low, high])
        assert result[0].id == 'high'

    def test_title_similarity(self):
        radar = TrendRadar()
        assert radar._title_similarity("hello world", "hello world") > 0.5
        assert radar._title_similarity("abc", "xyz") < 0.3

    def test_build_scoring_prompt(self):
        radar = TrendRadar()
        items = [
            TrendItem(id='1', title='DeepSeek发布新版本', source='github'),
            TrendItem(id='2', title='大气标准更新', source='github'),
        ]
        prompt = radar._build_scoring_prompt(items)
        assert 'DeepSeek' in prompt

    @pytest.mark.asyncio
    async def test_deliver_console(self):
        radar = TrendRadar()
        radar._items = [
            TrendItem(id='1', title='Test', source='test', heat_score=50, relevance_score=0.5),
        ]
        report = radar.generate_report()
        results = await radar.deliver_report(report, channels=['console', 'log'])
        assert results['console'] == 'ok'

    @pytest.mark.asyncio
    async def test_enrich_no_hub(self):
        radar = TrendRadar()
        item = TrendItem(id='t', title='Test', source='test')
        result = await radar.enrich_trend(item, None)
        assert result.enriched_context == ''

    def test_duplicate_tracking(self):
        radar = TrendRadar()
        items = [
            TrendItem(id='a', title='Breaking AI News', source='github', heat_score=95),
            TrendItem(id='b', title='Breaking AI News', source='reddit', heat_score=80),
        ]
        result = radar.dedup_trends(items)
        assert result[0].id == 'a'
        assert 'reddit' in result[0].metadata.get('duplicate_sources', [])
