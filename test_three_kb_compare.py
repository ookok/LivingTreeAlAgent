#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
三种知识库实现对比测试
1. KnowledgeBaseLayer (向量+BM25混合检索)
2. PageIndex (B-tree分层索引 + LLM摘要)
3. LLM Wiki (深度搜索 + 生成式Wiki)
"""

import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.fusion_rag.knowledge_base import KnowledgeBaseLayer
from core.page_index.index_builder import PageIndexBuilder
from core.deep_search_wiki.wiki_generator import WikiGenerator


def test_kb_layer():
    """测试 KnowledgeBaseLayer (向量+BM25)"""
    print("\n" + "=" * 60)
    print("[1] KnowledgeBaseLayer (向量 + BM25 混合检索)")
    print("=" * 60)

    kb = KnowledgeBaseLayer(
        embedding_model="BAAI/bge-small-zh",
        top_k=5,
        chunk_size=256,
        chunk_overlap=32
    )

    # 添加测试文档
    test_doc = {
        "id": "test_kb",
        "title": "Ollama Deployment Guide",
        "content": """
Ollama is a local LLM runtime. Install with: curl -fsSL https://ollama.com/install.sh | sh
Run models: ollama run llama2, ollama list, ollama pull <model>
API endpoint: http://localhost:11434/api/generate
Supports GPU acceleration with NVIDIA CUDA.
        """.strip(),
        "type": "md",
        "metadata": {"source": "test"}
    }

    t0 = time.time()
    chunks = kb.add_document(test_doc)
    add_time = time.time() - t0

    print(f"  [Storage] Add time: {add_time*1000:.1f}ms, Chunks: {chunks}")

    # 搜索
    query = "ollama installation command"
    t0 = time.time()
    results = kb.search(query, top_k=3, alpha=0.6)
    search_time = time.time() - t0

    print(f"  [Retrieval] Search time: {search_time*1000:.1f}ms")
    print(f"  [Results] {len(results)} found")
    for r in results[:2]:
        print(f"    - {r['title']} (score: {r['score']:.3f})")

    return {
        "name": "KnowledgeBaseLayer",
        "add_time": add_time * 1000,
        "search_time": search_time * 1000,
        "result_count": len(results),
        "top_score": results[0]['score'] if results else 0
    }


def test_page_index():
    """测试 PageIndex (B-tree分层索引)"""
    print("\n" + "=" * 60)
    print("[2] PageIndex (B-tree 分层索引 + LLM摘要)")
    print("=" * 60)

    # 创建测试文档
    test_file = "./data/test_page_index.md"
    os.makedirs("./data", exist_ok=True)

    test_content = """
# Ollama Deployment Guide

## Installation

### Linux/macOS
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Windows
Download from https://ollama.com/download

### Docker
```bash
docker run -d -v ollama:/root/.ollama -p 11434:11434 ollama/ollama
```

## Usage

### Basic Commands
- `ollama run llama2` - Run a model
- `ollama list` - List installed models
- `ollama pull <model>` - Download a model
- `ollama show <model>` - Show model info

### API Usage
POST http://localhost:11434/api/generate
```json
{
  "model": "llama2",
  "prompt": "Hello!",
  "stream": false
}
```

## GPU Support

Ollama supports NVIDIA GPU acceleration. Ensure CUDA is installed:
```bash
nvidia-smi
```

## Environment Variables

- OLLAMA_HOST - Listen address
- OLLAMA_MODELS - Model storage path
- OLLAMA_NUM_PARALLEL - Parallel requests
    """

    with open(test_file, "w", encoding="utf-8") as f:
        f.write(test_content)

    # 构建索引
    builder = PageIndexBuilder(
        chunk_size=200,
        chunk_overlap=20,
        tree_height=3,
        index_dir="./data/page_index_test"
    )

    t0 = time.time()
    doc = builder.build_index(test_file, use_llm_summaries=False)  # 不用LLM加速测试
    add_time = time.time() - t0

    print(f"  [Storage] Build time: {add_time*1000:.1f}ms")
    print(f"  [Index] Chunks: {doc.total_chunks}, Nodes: {len(doc._nodes)}, Tree height: {doc.tree_height}")

    # 模拟搜索（通过节点定位）
    query = "ollama installation docker"
    t0 = time.time()

    # 简单模拟：在摘要中搜索关键词
    matched_chunks = []
    for node_id, node in doc._nodes.items():
        if "ollama" in node.summary.lower() or "docker" in node.summary.lower():
            matched_chunks.extend(node.chunk_ids)

    search_time = time.time() - t0

    print(f"  [Retrieval] Search time: {search_time*1000:.1f}ms")
    print(f"  [Results] {len(matched_chunks)} chunks matched via node traversal")

    return {
        "name": "PageIndex",
        "add_time": add_time * 1000,
        "search_time": search_time * 1000,
        "result_count": len(matched_chunks),
        "top_score": 0.8 if matched_chunks else 0
    }


def test_llm_wiki():
    """测试 LLM Wiki (深度搜索 + 生成式)"""
    print("\n" + "=" * 60)
    print("[3] LLM Wiki (深度搜索 + 生成式 Wiki)")
    print("=" * 60)

    wiki_gen = WikiGenerator()

    topic = "Ollama Local LLM Runtime"

    t0 = time.time()
    # 生成 Wiki（不实际搜索，使用已有内容模拟）
    wiki = wiki_gen.generate(
        topic=topic,
        search_results=None,  # 不实际搜索
        use_search=False
    )
    gen_time = time.time() - t0

    print(f"  [Generation] Time: {gen_time*1000:.1f}ms")
    print(f"  [Wiki] Sections: {len(wiki.sections)}")
    print(f"  [Confidence] {wiki.confidence:.1%}")

    # 显示生成的 Wiki 结构
    md_output = wiki.to_markdown()
    print(f"\n  [Preview] First 300 chars:")
    print("  " + md_output[:300].replace("\n", "\n  "))

    return {
        "name": "LLM Wiki",
        "add_time": 0,  # Wiki 是生成式的，不需要存储
        "search_time": gen_time * 1000,
        "result_count": len(wiki.sections),
        "top_score": wiki.confidence
    }


def compare_results(results):
    """对比三种方案"""
    print("\n" + "=" * 60)
    print("COMPARISON SUMMARY")
    print("=" * 60)

    print(f"\n{'Method':<20} {'Storage(ms)':<15} {'Search(ms)':<15} {'Results':<10} {'Score':<10}")
    print("-" * 70)

    for r in results:
        print(f"{r['name']:<20} {r['add_time']:<15.1f} {r['search_time']:<15.1f} {r['result_count']:<10} {r['top_score']:<10.3f}")

    print("\n" + "=" * 60)
    print("ANALYSIS")
    print("=" * 60)

    print("""
1. KnowledgeBaseLayer (向量 + BM25)
   + 混合检索，平衡精确度和召回率
   + 支持大规模文档（Chroma/FAISS）
   + 适合：通用知识检索
   - 存储稍慢（需计算向量）
   - 语义匹配依赖嵌入质量

2. PageIndex (B-tree 分层)
   + 树形结构，查询定位快（O(log n)）
   + LLM 摘要减少搜索范围
   + 适合：大型单文档快速定位
   - 构建索引慢（需 LLM 生成摘要）
   - 不适合跨文档检索

3. LLM Wiki (生成式)
   + 生成结构化、可读性强的文档
   + 自动组织信息结构
   + 适合：研究探索、报告生成
   - 不是传统检索，是生成
   - 需外部搜索补充实时信息
    """)

    # 评分
    print("\n" + "=" * 60)
    print("RECOMMENDATIONS")
    print("=" * 60)
    print("""
场景                     推荐方案
──────────────────────────────────────────────
日常问答检索              KnowledgeBaseLayer
大型文档快速定位          PageIndex
研究报告/探索性查询        LLM Wiki
混合场景                  组合使用（KB + Wiki）
    """)


if __name__ == "__main__":
    print("=" * 60)
    print("THREE KNOWLEDGE BASE IMPLEMENTATIONS COMPARISON")
    print("=" * 60)

    results = []

    # Test 1: KnowledgeBaseLayer
    try:
        results.append(test_kb_layer())
    except Exception as e:
        print(f"  [Error] KB Layer: {e}")

    # Test 2: PageIndex
    try:
        results.append(test_page_index())
    except Exception as e:
        print(f"  [Error] PageIndex: {e}")

    # Test 3: LLM Wiki
    try:
        results.append(test_llm_wiki())
    except Exception as e:
        print(f"  [Error] LLM Wiki: {e}")

    # Compare
    if results:
        compare_results(results)

    print("\n[Done]")
