"""Knowledge Forager tests — auto-patrol, auto-graph, succession, daily brief.

Tests all four innovations:
  1. Food map registration + patrol scheduling
  2. Entity extraction + knowledge graph building
  3. Project timeline tracking (succession)
  4. Daily brief generation
"""

from __future__ import annotations

import time
import pytest

from livingtree.capability.knowledge_forager import (
    KnowledgeForager, FoodSource, KnowledgeGraph,
    SuccessionTracker, ProjectTimeline, ProjectStage, DailyBrief,
    get_forager,
)


# ═══ Sample Announcements ═══

ANNOUNCEMENTS = [
    ("[受理公示] 江苏亚威变压器有限公司扩建项目环评受理公示", "2026-04-28", "受理审批"),
    ("[拟批准公示] 江苏亚威变压器有限公司扩建项目拟批准公示", "2026-05-05", "拟批准审批"),
    ("[审批批复] 江苏亚威变压器有限公司扩建项目环评批复", "2026-05-20", "审批批复"),
    ("[受理公示] 海安恒力磁电有限公司钕铁硼永磁材料项目受理公示", "2026-04-28", "受理审批"),
    ("[受理公示] 南通大正电气有限公司变压器项目受理公示", "2026-04-10", "受理审批"),
    ("[审批批复] 南通大正电气有限公司变压器项目环评批复", "2026-04-20", "审批批复"),
    ("[招标公告] 海安高新区清洁低碳供热管网施工招标", "2026-04-10", "招标公告"),
]


# ═══ Food Map ═══

class TestFoodMap:
    @pytest.mark.asyncio
    async def test_register_site(self):
        forager = KnowledgeForager()
        source = await forager.register_site("test", "https://test.gov.cn/gg")
        assert source.domain == "test.gov.cn"
        assert source.enabled is True

    def test_get_due_sources(self):
        forager = KnowledgeForager()
        s = FoodSource(domain="t.com", url="https://t.com", last_scan=0, scan_interval_hours=0)
        forager.food_map["t"] = s
        due = forager.get_due_sources()
        assert len(due) >= 1

    def test_persistence_roundtrip(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            f1 = KnowledgeForager(data_dir=tmp)
            f1.food_map["x"] = FoodSource(domain="x.com", url="https://x.com")
            f1._save_food_map()

            f2 = KnowledgeForager(data_dir=tmp)
            f2._load_food_map()
            assert "x" in f2.food_map
            assert f2.food_map["x"].domain == "x.com"


# ═══ Knowledge Graph ═══

class TestKnowledgeGraph:
    def test_add_entity(self):
        kg = KnowledgeGraph()
        eid = kg.add_entity("亚威变压器", "company", "2026-04-28")
        assert eid
        assert kg.nodes[eid].name == "亚威变压器"
        assert kg.nodes[eid].entity_type == "company"

    def test_duplicate_entity_increments_count(self):
        kg = KnowledgeGraph()
        eid1 = kg.add_entity("亚威变压器", "company")
        eid2 = kg.add_entity("亚威变压器", "company")
        assert eid1 == eid2
        assert kg.nodes[eid1].occurrences == 2

    def test_add_relation(self):
        kg = KnowledgeGraph()
        pid = kg.add_entity("扩建项目", "project")
        cid = kg.add_entity("亚威公司", "company")
        kg.add_relation("扩建项目", "亚威公司", "submitted_by")
        assert len(kg.relations) == 1

    def test_query_entity(self):
        kg = KnowledgeGraph()
        kg.add_entity("亚威", "company")
        kg.add_entity("扩建", "project")
        kg.add_relation("扩建", "亚威", "submitted_by")
        result = kg.query("扩建", "project")
        assert "亚威" in str(result)


# ═══ Succession Tracker ═══

class TestSuccessionTracker:
    def test_single_stage(self):
        st = SuccessionTracker()
        tl = st.ingest("[受理公示] 亚威变压器项目受理", "2026-04-28", "https://t.com")
        assert tl.project_name
        assert len(tl.stages) == 1
        assert tl.stages[0].stage == "受理公示"

    def test_multi_stage_merge(self):
        st = SuccessionTracker()
        st.ingest("[受理公示] 江苏亚威变压器有限公司扩建项目", "2026-04-01", "url1")
        st.ingest("[审批批复] 江苏亚威变压器有限公司扩建项目", "2026-04-28", "url2")

        # Both should merge into same project (same title minus prefix)
        stats = st.get_stats()
        assert stats["total_projects"] == 1
        assert stats["total_stages"] == 2
        assert stats["multi_stage_projects"] == 1

    def test_company_extraction(self):
        st = SuccessionTracker()
        company = st._extract_company("[受理公示] 江苏亚威变压器有限公司扩建项目")
        assert "亚威" in company or "有限公司" in company

    def test_stage_detection(self):
        st = SuccessionTracker()
        assert st._detect_stage("[环评审批决定公告]批复") == "审批批复"
        assert st._detect_stage("[建设项目环评受理公示]受理") == "受理公示"
        assert st._detect_stage("[拟批准公示]拟批") == "拟批准公示"

    def test_stats(self):
        st = SuccessionTracker()
        for title, date, _ in ANNOUNCEMENTS:
            st.ingest(title, date, "test")
        stats = st.get_stats()
        assert stats["total_projects"] >= 1
        assert stats["total_stages"] == len(ANNOUNCEMENTS)

    def test_active_projects(self):
        st = SuccessionTracker()
        st.ingest("[受理公示] 新项目", time.strftime("%Y-%m-%d"), "test")
        active = st.get_active_projects(since_days=365)
        assert len(active) >= 1


# ═══ Daily Brief ═══

class TestDailyBrief:
    def test_generate_brief(self):
        forager = KnowledgeForager()
        for title, date, _ in ANNOUNCEMENTS:
            forager.succession.ingest(title, date, "test_url")
            company = forager._extract_entity_company(title)
            if company:
                forager.graph.add_entity(company, "company", date)

        brief = forager.generate_daily_brief()
        assert brief.date
        assert brief.total_new_items > 0
        assert brief.raw_text
        assert "📰" in brief.raw_text or "情报" in brief.raw_text

    def test_recommendations(self):
        forager = KnowledgeForager()
        brief = DailyBrief(new_projects=15, standard_mentions=["GB12348"])
        recs = forager._generate_recommendations(brief)
        assert len(recs) > 0


# ═══ Integration ═══

class TestForagerIntegration:
    @pytest.mark.asyncio
    async def test_digest_results(self):
        """Test the full digest pipeline with collected results."""
        forager = KnowledgeForager()

        # Simulate collect result
        class FakeResult:
            details = [
                {"title": "[受理公示] 测试变压器有限公司扩建项目", "date": "2026-05-01",
                 "decision": "新增", "source": "https://test.gov.cn"},
                {"title": "[审批批复] 测试变压器有限公司扩建项目批复", "date": "2026-05-20",
                 "decision": "新增", "source": "https://test.gov.cn"},
            ]

        await forager._digest_results(FakeResult())

        assert len(forager.graph.nodes) > 0
        stats = forager.succession.get_stats()
        assert stats["total_stages"] == 2

    def test_entity_extraction_full(self):
        forager = KnowledgeForager()
        title = "[受理公示] 江苏亚威变压器有限公司非晶合金扩建项目 引用GB 25446-2010标准"
        assert forager._extract_entity_company(title)
        assert forager._extract_entity_project(title)
        assert forager._extract_entity_standards(title)

    def test_singleton(self):
        f1 = get_forager()
        f2 = get_forager()
        assert f1 is f2
