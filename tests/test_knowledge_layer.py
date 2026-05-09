"""Unit tests for Knowledge Layer — hypergraph, precedence, order-aware reranker."""
import pytest
from livingtree.knowledge.hypergraph_store import (
    HypergraphStore, Hyperedge, EntityNode, HypergraphQueryResult)
from livingtree.knowledge.precedence_model import (
    PrecedenceModel, PrecedenceResult, Transition)
from livingtree.knowledge.order_aware_reranker import (
    OrderAwareReranker, get_order_aware_reranker)
from livingtree.knowledge.lazy_index import (
    LazyIndex, SectionParser, SectionRef, DocumentIndex)
from livingtree.knowledge.gravity_model import KnowledgeGravity, GravityField


class TestHypergraphStore:
    def test_add_entity(self):
        hg = HypergraphStore()
        eid = hg.add_entity(EntityNode(id="e1", label="Test Entity"))
        assert eid == "e1"
        assert hg.entity_count() == 1

    def test_add_hyperedge_basic(self):
        hg = HypergraphStore()
        hg.add_entity(EntityNode(id="a", label="A"))
        hg.add_entity(EntityNode(id="b", label="B"))
        he = Hyperedge(id="he1", entities=["a", "b"], relation="related", weight=0.5)
        hid = hg.add_hyperedge(he)
        assert hid == "he1"
        assert hg.hyperedge_count() == 1

    def test_add_hyperedge_nary(self):
        hg = HypergraphStore()
        for eid in ["GB3095", "SO2", "24h", "150ug"]:
            hg.add_entity(EntityNode(id=eid, label=eid))
        he = Hyperedge(id="h1", entities=["GB3095", "SO2", "24h", "150ug"],
                       relation="emission_limit", weight=0.8)
        hg.add_hyperedge(he)
        assert hg.hyperedge_count() == 1
        assert len(hg._hyperedges["h1"].entities) == 4

    def test_infer_sequence(self):
        hg = HypergraphStore()
        for eid in ["a", "b", "c", "d"]:
            hg.add_entity(EntityNode(id=eid, label=eid))
        hg.add_hyperedge(Hyperedge(id="h1", entities=["a", "b"], relation="step1",
                                    precedence_before=["h2"], weight=0.5))
        hg.add_hyperedge(Hyperedge(id="h2", entities=["b", "c"], relation="step2",
                                    precedence_after=["h1"], weight=0.6))
        result = hg.infer_sequence(seed_entities=["a"])
        assert isinstance(result, HypergraphQueryResult)
        assert len(result.hyperedges) >= 1

    def test_precedence_chain(self):
        hg = HypergraphStore()
        hg.add_entity(EntityNode(id="x", label="X"))
        hg.add_entity(EntityNode(id="y", label="Y"))
        hg.add_hyperedge(Hyperedge(id="ha", entities=["x", "y"], relation="first",
                                    precedence_before=["hb"], weight=0.5))
        hg.add_hyperedge(Hyperedge(id="hb", entities=["y"], relation="second",
                                    precedence_after=["ha"], weight=0.6))
        chain = hg.get_precedence_chain("ha", direction="forward")
        assert len(chain) >= 1


class TestPrecedenceModel:
    def test_observe_sequence(self):
        pm = PrecedenceModel()
        pm.observe_sequence(["a", "b", "c"])
        assert pm.transition_prob("a", "b") > 0
        assert pm.transition_prob("b", "c") > 0

    def test_order_facts(self):
        pm = PrecedenceModel()
        pm.observe_sequence(["background", "method", "results"])
        pm.observe_sequence(["background", "method", "results"])
        result = pm.order_facts(["results", "background", "method"])
        assert isinstance(result, PrecedenceResult)
        assert result.ordered_types[0] == "background"
        assert result.ordered_types[-1] == "results"

    def test_score_ordering(self):
        pm = PrecedenceModel()
        pm.observe_sequence(["a", "b", "c"])
        good = pm.score_ordering(["a", "b", "c"])
        bad = pm.score_ordering(["c", "b", "a"])
        assert good > bad

    def test_domain_initializers(self):
        env = PrecedenceModel.for_environmental_reports()
        code = PrecedenceModel.for_code_generation()
        assert len(env._sequences) > 0
        assert len(code._sequences) > 0

    def test_transition_prob_smoothing(self):
        pm = PrecedenceModel(smoothing=0.1)
        prob = pm.transition_prob("unknown_a", "unknown_b")
        assert prob > 0  # Smoothing ensures non-zero


class TestOrderAwareReranker:
    def test_infer_doc_type(self):
        reranker = OrderAwareReranker()
        assert reranker.infer_doc_type("SO2的24小时平均浓度限值是150μg/m³") == "threshold"
        assert reranker.infer_doc_type("根据GB3095-2012标准规定") == "regulation"
        assert reranker.infer_doc_type("监测数据显示PM2.5超标") == "data_observation"

    def test_infer_query_types(self):
        reranker = OrderAwareReranker()
        types = reranker.infer_query_types("分析SO2排放标准并评估影响")
        assert "analysis_result" in types or "regulation" in types or "threshold" in types

    def test_rerank_empty(self):
        reranker = OrderAwareReranker()
        result = reranker.rerank([], "test query")
        assert result.order_confidence == 0.0
        assert len(result.reranked_docs) == 0


class TestSectionParser:
    def test_parse_markdown(self):
        parser = SectionParser()
        content = "# Title\n\nSome text.\n\n## Section 1\n\nContent 1.\n\n### Sub A\n\nSub content."
        sections = parser.parse(content)
        assert len(sections) >= 3

    def test_parse_chinese(self):
        parser = SectionParser()
        content = "一、概述\n这是概述内容。\n二、方法\n这是方法内容。"
        sections = parser.parse(content)
        assert len(sections) >= 2

    def test_parse_numbered(self):
        parser = SectionParser()
        content = "1. Introduction\nText.\n2. Methods\nMethods text."
        sections = parser.parse(content)
        assert len(sections) >= 1  # At minimum we get one section


class TestLazyIndex:
    def test_index_document(self):
        lazy = LazyIndex(max_docs=10)
        content = "# Title\n\n## Section A\nA content.\n## Section B\nB content."
        idx = lazy.index_document("doc1", "Test Doc", content)
        assert idx.section_count >= 2
        assert lazy.has_index("doc1")

    def test_search_sections(self):
        lazy = LazyIndex()
        lazy.index_document("d1", "Doc", "# SO2 Standard\n\nContent about SO2.\n## Methods\nMethods text.")
        results = lazy.search_sections("SO2")
        assert len(results) > 0
        assert "SO2" in results[0].section.section_title

    def test_memory_efficiency(self):
        lazy = LazyIndex()
        content = ("# Title\n\n" + "## Section\nContent.\n" * 50)
        idx = lazy.index_document("big", "Big Doc", content)
        assert idx.section_count > 0


class TestKnowledgeGravity:
    def test_compute_mass(self):
        gm = KnowledgeGravity()
        mass = gm.compute_mass("test_entity")
        assert mass.raw_mass > 0

    def test_semantic_distance(self):
        gm = KnowledgeGravity()
        d1 = gm._semantic_distance("hello_world", "hello_world")
        assert d1 == 0.0
        d2 = gm._semantic_distance("abc", "xyz")
        assert d2 > 0.0

    def test_distribution_entropy(self):
        from livingtree.knowledge.gravity_model import distribution_entropy
        e = distribution_entropy([1.0, 1.0, 1.0, 1.0])
        assert e > 0.9  # Uniform → high entropy
        e2 = distribution_entropy([10.0, 0.1, 0.1])
        assert e2 < 0.9  # Concentrated → lower entropy
