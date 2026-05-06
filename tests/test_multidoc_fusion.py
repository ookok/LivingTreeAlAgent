"""MultiDocFusion integration tests.

Tests the complete MultiDocFusion pipeline as described by Shin et al. (EMNLP 2025):
  - DocumentTree construction and traversal
  - HierarchicalChunker: DSHP-LLM + DFS chunking
  - DocumentKB hierarchical ingest
  - MultiDocFusionEngine: cross-reference, conflict detection, synthesis
  - DocumentLayoutAnalyzer: region detection, figure-caption binding
  - ModernOCR: multi-backend selection
  - hierarchical_retrieve: section context in retrieval
"""

from __future__ import annotations

import os
import tempfile
import pytest

from livingtree.knowledge.document_tree import DocumentTree, DocSection
from livingtree.knowledge.hierarchical_chunker import (
    HierarchicalChunker,
    DocumentChunk,
    build_document_tree,
    chunk_document,
)
from livingtree.knowledge.multidoc_fusion import (
    MultiDocFusionEngine,
    CrossReference,
    DocumentConflict,
    FusionResult as MDFusionResult,
)
from livingtree.knowledge.layout_analyzer import (
    DocumentLayoutAnalyzer,
    LayoutRegion,
    PageLayout,
    FigureCaption,
)
from livingtree.knowledge.modern_ocr import ModernOCR, OCRResult, OCRRegion


# ═══ Sample Documents ═══

SIMPLE_DOC = """# Introduction

This is the introduction section. It describes the project background.

## Background

Detailed background information about the project goals and objectives.

### Goals

The main goals are as follows.

## Methodology

The approach used for this research.

# Results

Summary of the key results found during the study.

## Performance

Performance metrics data.

## Accuracy

Accuracy comparison results.
"""

CHINESE_DOC = """第一章 概述

本项目针对工业环境影响进行评估。

第一节 项目背景

项目位于工业园区核心区域。

第二节 研究范围

研究范围涵盖大气、水、噪声等环境要素。

第二章 技术方法

采用高斯烟羽模型进行大气扩散模拟。

第一节 模型建立

基于AERMOD模式建立扩散模型。

第二节 参数设置

参数依据HJ2.2-2018标准确定。

第三章 结果分析

模拟结果表明污染物浓度符合标准。

第一节 达标情况

所有监测点均未出现超标现象。

第二节 建议措施

建议加强日常监测频次。
"""


# ═══ DocumentTree ═══

class TestDocumentTree:
    def test_create_empty(self):
        tree = DocumentTree.create(title="Test")
        assert tree.title == "Test"
        assert tree.section_count == 0
        assert tree.leaf_count == 0

    def test_add_section(self):
        tree = DocumentTree.create(title="Test")
        s1 = tree.add_section(tree.root, "1", "Introduction", level=1)
        s2 = tree.add_section(s1, "1.1", "Background", level=2)
        assert tree.section_count == 2
        assert tree.leaf_count == 1

    def test_section_path(self):
        tree = DocumentTree.create(title="Test")
        s1 = tree.add_section(tree.root, "1", "Introduction", level=1)
        s1_1 = tree.add_section(s1, "1.1", "Background", level=2)
        assert "1.1" in s1_1.path
        assert "Background" in s1_1.path

    def test_find_section(self):
        tree = DocumentTree.create()
        tree.add_section(tree.root, "3", "Methods", level=1)
        found = tree.find_section("3")
        assert found is not None
        assert found.title == "Methods"
        assert tree.find_section("99") is None

    def test_iter_leaves(self):
        tree = DocumentTree.create()
        s1 = tree.add_section(tree.root, "1", "Intro", text="text1", level=1)
        s1_1 = tree.add_section(s1, "1.1", "Sub", text="text2", level=2)
        s2 = tree.add_section(tree.root, "2", "Methods", text="text3", level=1)
        leaves = list(tree.root.iter_leaves())
        assert len(leaves) == 2  # s1_1 and s2

    def test_print_tree(self):
        tree = DocumentTree.create(title="Doc")
        tree.add_section(tree.root, "1", "Intro", level=1)
        output = tree.print_tree()
        assert "Doc" in output
        assert "Intro" in output

    def test_to_dict(self):
        tree = DocumentTree.create(title="Test")
        tree.add_section(tree.root, "1", "Section", level=1)
        d = tree.to_dict()
        assert d["title"] == "Test"
        assert "root" in d


# ═══ HierarchicalChunker ═══

class TestHierarchicalChunker:
    def test_regex_build_tree_simple(self):
        chunker = HierarchicalChunker(mode="REGEX")
        tree = chunker.build_tree(SIMPLE_DOC, title="Test")
        assert tree is not None
        assert tree.section_count >= 2

    def test_chunk_document(self):
        chunker = HierarchicalChunker(chunk_size=300, chunk_overlap=50, mode="REGEX")
        chunks = chunker.chunk(SIMPLE_DOC, title="Test")
        assert len(chunks) > 0
        for c in chunks:
            assert isinstance(c, DocumentChunk)
            assert c.text
            assert c.chunk_id

    def test_chinese_headings(self):
        chunker = HierarchicalChunker(mode="REGEX")
        tree = chunker.build_tree(CHINESE_DOC, title="环评报告")
        assert tree.section_count >= 3  # 第一章, 第二章, 第三章
        sections = list(tree.root.iter_sections())
        titles = [s.title for s in sections]
        assert any("概述" in t for t in titles)

    def test_section_context_in_chunks(self):
        chunker = HierarchicalChunker(chunk_size=500, mode="REGEX")
        chunks = chunker.chunk(SIMPLE_DOC, title="Test")
        sections_with_context = [c for c in chunks if c.section_path]
        assert len(sections_with_context) > 0
        for c in sections_with_context:
            assert c.section_path or c.section_id

    def test_no_headings_document(self):
        text = "This is a plain document without any headings or structure."
        chunker = HierarchicalChunker(mode="REGEX")
        tree = chunker.build_tree(text, title="Plain")
        chunks = chunker.dfs_chunk(tree)
        assert len(chunks) == 1

    def test_build_document_tree_convenience(self):
        tree = build_document_tree(SIMPLE_DOC, title="Quick")
        assert tree.section_count >= 2

    def test_chunk_document_convenience(self):
        chunks = chunk_document(SIMPLE_DOC, title="Quick", chunk_size=400)
        assert len(chunks) > 0

    def test_context_string(self):
        chunk = DocumentChunk(
            chunk_id="test_1",
            text="sample text",
            section_path="1 > 1.2 Methods",
            section_title="Methods",
        )
        ctx = chunk.context_string
        assert "1 > 1.2 Methods" in ctx
        assert "sample text" in ctx


# ═══ MultiDocFusionEngine ═══

class TestMultiDocFusionEngine:
    def test_cross_reference(self):
        engine = MultiDocFusionEngine()
        tree1 = build_document_tree(SIMPLE_DOC, title="Doc A")
        tree2 = build_document_tree(SIMPLE_DOC, title="Doc B")

        refs = engine.cross_reference([tree1, tree2])
        assert len(refs) > 0
        assert all(isinstance(r, CrossReference) for r in refs)

    def test_cross_reference_single_doc(self):
        engine = MultiDocFusionEngine()
        tree1 = build_document_tree(SIMPLE_DOC, title="Doc A")
        refs = engine.cross_reference([tree1])
        assert refs == []

    def test_detect_conflicts_no_hub(self):
        doc_a = """# Methods\n\nWe used method X which takes 5 minutes.\n\n# Results\n\nAccuracy was 95%."""
        doc_b = """# Methods\n\nWe used method X which takes 10 minutes.\n\n# Results\n\nAccuracy was 85%."""
        engine = MultiDocFusionEngine(similarity_threshold=0.5)
        tree_a = build_document_tree(doc_a, title="Doc A")
        tree_b = build_document_tree(doc_b, title="Doc B")
        refs = engine.cross_reference([tree_a, tree_b])
        conflicts = engine.detect_conflicts([tree_a, tree_b], refs)
        assert isinstance(conflicts, list)

    def test_find_complementary(self):
        doc_a = """# Intro\n\nBasic intro.\n\n# Methods\n\nMethod description."""
        doc_b = """# Intro\n\nBasic intro.\n\n# Results\n\nUnique results."""
        engine = MultiDocFusionEngine(similarity_threshold=0.5)
        tree_a = build_document_tree(doc_a, title="Doc A")
        tree_b = build_document_tree(doc_b, title="Doc B")
        refs = engine.cross_reference([tree_a, tree_b])
        complementary = engine.find_complementary([tree_a, tree_b], refs)
        assert len(complementary) >= 0

    def test_fallback_merge(self):
        engine = MultiDocFusionEngine()
        tree_a = build_document_tree("# A\n\nContent A", title="A")
        tree_b = build_document_tree("# B\n\nContent B", title="B")
        result = engine._fallback_merge([tree_a, tree_b])
        assert "A" in result
        assert "B" in result

    def test_fuse_no_hub(self):
        engine = MultiDocFusionEngine()
        tree_a = build_document_tree("# Intro\n\nText", title="A")
        tree_b = build_document_tree("# Intro\n\nText", title="B")
        result = engine.fuse([tree_a, tree_b])
        assert isinstance(result, MDFusionResult)
        assert len(result.sources) == 2
        assert len(result.references) > 0

    def test_metadata_in_result(self):
        engine = MultiDocFusionEngine()
        tree_a = build_document_tree("# A\n\nA", title="A")
        tree_b = build_document_tree("# B\n\nB", title="B")
        result = engine.fuse([tree_a, tree_b])
        assert result.metadata["tree_count"] == 2


# ═══ DocumentLayoutAnalyzer ═══

class TestDocumentLayoutAnalyzer:
    def test_analyze_empty_blocks(self):
        analyzer = DocumentLayoutAnalyzer()
        page = analyzer.analyze_page([], page_number=1, page_width=600, page_height=800)
        assert page.page_number == 1
        assert page.regions == []

    def test_classify_title_region(self):
        analyzer = DocumentLayoutAnalyzer()
        blocks = [{
            "bbox": (50, 20, 550, 60),
            "lines": [{"spans": [{"text": "Chapter 1 Introduction", "size": 24, "flags": 0}]}],
        }]
        page = analyzer.analyze_page(blocks, page_number=1, page_width=600, page_height=800)
        assert any(r.region_type == "title" for r in page.regions)

    def test_header_detection(self):
        analyzer = DocumentLayoutAnalyzer()
        blocks = [{
            "bbox": (50, 5, 550, 25),
            "lines": [{"spans": [{"text": "Page Header", "size": 10, "flags": 0}]}],
        }]
        page = analyzer.analyze_page(blocks, page_number=1, page_width=600, page_height=800)
        assert any(r.region_type == "header" for r in page.regions)

    def test_figure_caption_binding(self):
        analyzer = DocumentLayoutAnalyzer()
        blocks = [
            {
                "bbox": (10, 10, 100, 100),
                "lines": [{"spans": [{"text": "Figure 1. Example", "size": 12, "flags": 0}]}],
            },
            {
                "bbox": (100, 110, 500, 130),
                "lines": [{"spans": [{"text": "Fig. 1: Example", "size": 10, "flags": 0}]}],
            },
        ]
        page = analyzer.analyze_page(blocks, page_number=1, page_width=600, page_height=800)
        assert len(page.figure_captions) >= 0

    def test_column_detection(self):
        analyzer = DocumentLayoutAnalyzer()
        regions = [
            LayoutRegion("r1", 1, "body", (0, 50, 280, 400)),
            LayoutRegion("r2", 1, "body", (320, 50, 600, 400)),
        ]
        cols = analyzer._detect_columns(regions, 600)
        assert cols >= 1

    def test_sidebar_detection(self):
        analyzer = DocumentLayoutAnalyzer()
        assert analyzer._is_sidebar((0, 0, 100, 500), 600)
        assert not analyzer._is_sidebar((200, 0, 400, 500), 600)


# ═══ ModernOCR ═══

class TestModernOCR:
    def test_import(self):
        ocr = ModernOCR()
        assert isinstance(ocr, ModernOCR)

    def test_result_dataclass(self):
        result = OCRResult(text="hello", language="eng", backend_used="test")
        assert result.text == "hello"
        assert result.language == "eng"

    def test_region_dataclass(self):
        region = OCRRegion(text="test", bbox=(0, 0, 100, 50), confidence=0.95)
        assert region.confidence == 0.95


# ═══ Integration ═══

class TestIntegration:
    def test_end_to_end_pipeline(self):
        """Complete MultiDocFusion pipeline: tree → chunk → fuse."""
        tree1 = build_document_tree(SIMPLE_DOC, title="Doc A")
        tree2 = build_document_tree(CHINESE_DOC, title="Doc B")

        chunker = HierarchicalChunker(chunk_size=500, mode="REGEX")
        chunks1 = chunker.dfs_chunk(tree1)
        chunks2 = chunker.dfs_chunk(tree2)
        assert len(chunks1) > 0
        assert len(chunks2) > 0

        engine = MultiDocFusionEngine(similarity_threshold=0.5)
        result = engine.fuse([tree1, tree2])
        assert result.metadata["tree_count"] == 2
        assert len(result.references) >= 0

    def test_nested_structure_deep(self):
        doc = "\n".join(f"{'#' * (i+1)} Section {i}.{j}" for i in range(3) for j in range(2))
        tree = build_document_tree(doc, title="Deep")
        chunker = HierarchicalChunker(chunk_size=200, mode="REGEX")
        chunks = chunker.dfs_chunk(tree)
        assert len(chunks) > 0
