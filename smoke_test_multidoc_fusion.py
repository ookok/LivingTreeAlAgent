#!/usr/bin/env python3
"""Quick smoke test for MultiDocFusion integration.

Usage:
    python smoke_test_multidoc_fusion.py
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from livingtree.knowledge.document_tree import DocumentTree, DocSection
from livingtree.knowledge.hierarchical_chunker import (
    HierarchicalChunker, build_document_tree, chunk_document,
)
from livingtree.knowledge.multidoc_fusion import MultiDocFusionEngine
from livingtree.knowledge.layout_analyzer import DocumentLayoutAnalyzer
from livingtree.knowledge.modern_ocr import ModernOCR

SIMPLE_DOC = """# Introduction
This is the introduction.
## Background
Background information.
## Goals
Main goals here.
# Methods
The methodology section.
## Approach
Our approach details.
# Results
Summary of findings."""


def test_document_tree():
    print("1. DocumentTree...", end=" ")
    tree = DocumentTree.create(title="Test")
    s1 = tree.add_section(tree.root, "1", "Introduction", text="Intro text", level=1)
    s1_1 = tree.add_section(s1, "1.1", "Background", text="BG text", level=2)
    assert tree.section_count == 2
    assert "1.1" in s1_1.path
    assert tree.find_section("1") is not None
    leaves = list(tree.root.iter_leaves())
    assert len(leaves) == 1
    assert tree.print_tree()
    print("OK")

def test_hierarchical_chunker():
    print("2. HierarchicalChunker...", end=" ")
    chunker = HierarchicalChunker(chunk_size=300, chunk_overlap=50, mode="REGEX")
    tree = chunker.build_tree(SIMPLE_DOC, title="Test")
    assert tree.section_count >= 3
    chunks = chunker.dfs_chunk(tree)
    assert len(chunks) > 0
    assert any(c.section_path for c in chunks)
    print(f"OK ({len(chunks)} chunks)")

def test_convenience_functions():
    print("3. Convenience functions...", end=" ")
    tree = build_document_tree(SIMPLE_DOC, title="Quick")
    assert tree.section_count >= 3
    chunks = chunk_document(SIMPLE_DOC, title="Quick", chunk_size=400)
    assert len(chunks) > 0
    print("OK")

def test_multidoc_fusion():
    print("4. MultiDocFusion...", end=" ")
    engine = MultiDocFusionEngine(similarity_threshold=0.5)
    doc_a = """# Intro\n\nText A.\n\n# Methods\n\nMethod A details."""
    doc_b = """# Intro\n\nText A.\n\n# Results\n\nUnique results B."""
    tree_a = build_document_tree(doc_a, title="Doc A")
    tree_b = build_document_tree(doc_b, title="Doc B")
    result = engine.fuse([tree_a, tree_b])
    assert abs(len(result.sources)) == 2
    assert abs(len(result.references)) > 0
    assert abs(result.metadata["tree_count"]) == 2
    print(f"OK ({len(result.references)} refs, {len(result.conflicts)} conflicts)")

def test_layout_analyzer():
    print("5. LayoutAnalyzer...", end=" ")
    analyzer = DocumentLayoutAnalyzer()
    blocks = [
        {"bbox": (50, 20, 550, 60), "lines": [{"spans": [{"text": "Chapter 1", "size": 24, "flags": 0}]}]},
        {"bbox": (50, 70, 550, 200), "lines": [{"spans": [{"text": "Body text here.", "size": 12, "flags": 0}]}]},
    ]
    page = analyzer.analyze_page(blocks, page_number=1, page_width=600, page_height=800)
    assert page.page_number == 1
    assert any(r.region_type == "title" for r in page.regions)
    assert any(r.region_type == "body" for r in page.regions)
    print("OK")

def test_modern_ocr():
    print("6. ModernOCR...", end=" ")
    ocr = ModernOCR()
    assert isinstance(ocr, ModernOCR)
    result = ocr.extract("nonexistent_file.png", language="eng")
    assert result.backend_used in ("none", "fallback_failed")
    print("OK")

def test_chinese_document():
    print("7. Chinese document...", end=" ")
    doc = """第一章 概述
第一节 项目背景
项目位于北京朝阳区。
第二节 研究目标
完成环境影响评估报告。
第二章 方法
第一节 数据采集
采集2024年全年监测数据。
第二节 分析方法
采用高斯烟羽模型。"""
    tree = build_document_tree(doc, title="环评报告")
    chunker = HierarchicalChunker(chunk_size=500, mode="REGEX")
    chunks = chunker.dfs_chunk(tree)
    assert len(chunks) > 0
    assert tree.section_count >= 2
    print(f"OK ({len(chunks)} chunks)")

def main():
    print("=" * 60)
    print("  MultiDocFusion Smoke Test")
    print("=" * 60)

    tests = [
        test_document_tree,
        test_hierarchical_chunker,
        test_convenience_functions,
        test_multidoc_fusion,
        test_layout_analyzer,
        test_modern_ocr,
        test_chinese_document,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"FAIL: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("=" * 60)
    print(f"  Results: {passed} passed, {failed} failed")
    print("=" * 60)
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
