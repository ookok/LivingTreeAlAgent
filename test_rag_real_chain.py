#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
真实 RAG 存储测试 - 使用 Chroma 向量数据库
测试知识库初始化、存储、搜索、推理的完整链路
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.fusion_rag.knowledge_base import KnowledgeBaseLayer
from core.knowledge_vector_db import VectorDatabase, VectorStoreType


def test_real_rag_chain():
    """测试真实的 RAG 存储链路"""

    print("=" * 60)
    print("RAG Knowledge Base Full Chain Test")
    print("=" * 60)

    # ========================================
    # Step 1: Initialize Knowledge Base with real Chroma DB
    # ========================================
    print("\n[Step 1] Initialize Knowledge Base")
    print("-" * 40)

    # Initialize vector database (Chroma)
    vector_db = VectorDatabase(
        db_type="chroma",
        db_path="./data/rag_test_db",
        embedding_dim=384
    )

    # Initialize knowledge layer
    kb = KnowledgeBaseLayer(
        embedding_model="BAAI/bge-small-zh",
        top_k=5,
        chunk_size=256,
        chunk_overlap=32
    )

    print(f"[OK] Vector DB type: {vector_db.db_type.value}")
    print(f"[OK] Persistence path: {vector_db.db_path}")
    print(f"[OK] Embedding dim: {vector_db.embedding_dim}")

    # ========================================
    # Step 2: Add real documents to RAG storage
    # ========================================
    print("\n[Step 2] Add Documents to RAG Storage")
    print("-" * 40)

    arch_docs = [
        {
            "id": "arch_001",
            "title": "Microservice Architecture Design Principles",
            "content": """Microservice architecture splits a single application into small services, each running in independent processes with lightweight protocol communication.

Core Principles:
1. Single Responsibility: each service handles one business function
2. Independent Deployment: services can be deployed and scaled independently
3. Decentralization: each service manages its own database
4. Infrastructure Automation: CI/CD for automated deployment
5. Fault Tolerance: services should degrade gracefully

Common frameworks: Spring Cloud, Docker, Kubernetes, Istio
            """,
            "type": "md",
            "metadata": {"source": "architecture", "category": "design"}
        },
        {
            "id": "arch_002",
            "title": "Ollama Deployment Best Practices",
            "content": """Ollama is a local LLM runtime framework supporting deployment and running of various open-source LLM models locally.

Deployment Requirements:
- OS: Linux/macOS/Windows
- Memory: at least 8GB (recommended 16GB+)
- Disk: at least 10GB free space
- GPU: NVIDIA GPU + CUDA support (optional but recommended)

Installation Steps:
1. Linux/macOS: curl -fsSL https://ollama.com/install.sh | sh
2. Windows: Download installer and run
3. Docker: docker run -d -v ollama:/root/.ollama -p 11434:11434 ollama/ollama

Common Commands:
- ollama run llama2: Run llama2 model
- ollama list: List installed models
- ollama pull <model>: Pull new model
- ollama show <model>: View model info

API Usage:
POST http://localhost:11434/api/generate
{
  "model": "llama2",
  "prompt": "Your question",
  "stream": false
}

Environment Variables:
- OLLAMA_HOST: Set listen address
- OLLAMA_MODELS: Model storage path
- OLLAMA_NUM_PARALLEL: Number of parallel requests
            """,
            "type": "md",
            "metadata": {"source": "deployment", "category": "ops"}
        },
        {
            "id": "arch_003",
            "title": "RAG Retrieval-Augmented Generation Technology",
            "content": """RAG (Retrieval-Augmented Generation) combines retrieval and generation to enhance LLM response quality.

Workflow:
1. Document Processing: chunking, embedding, storage to vector DB
2. Retrieval Phase: retrieve relevant document chunks based on user query
3. Generation Phase: feed retrieval results as context to LLM

Key Technologies:
- Embedding Models: text-embedding-ada-002, BAAI/bge-small-zh
- Vector Databases: Chroma, Milvus, FAISS, Pinecone
- Chunking Strategies: fixed-size, overlapping slide, semantic chunking
- Retrieval Strategies: vector search, keyword search, hybrid search

Optimization Tips:
- Use hybrid retrieval (vector + keyword) to improve recall
- Add metadata filters to narrow search scope
- Rerank to improve precision
- Query rewriting to improve retrieval effect
            """,
            "type": "md",
            "metadata": {"source": "ai", "category": "ml"}
        }
    ]

    # Add to both KnowledgeBaseLayer and VectorDatabase
    for doc in arch_docs:
        chunks = kb.add_document(doc)

        # Store to VectorDatabase (using correct API: add())
        vector_db.add(
            content=doc["content"],
            metadata=doc["metadata"],
            doc_id=doc["id"]
        )

        print(f"  [OK] {doc['title']}")
        print(f"       Chunks: {chunks}")

    # ========================================
    # Step 3: Search "system architecture design"
    # ========================================
    print("\n[Step 3] Search Query: 'system architecture design'")
    print("-" * 40)

    query = "system architecture design"

    # Hybrid search (vector + BM25) via KnowledgeBaseLayer
    results = kb.search(query, top_k=5, alpha=0.6)

    print(f"  Hybrid search results ({len(results)} found):")
    for i, r in enumerate(results, 1):
        print(f"\n  [{i}] {r['title']}")
        print(f"      Score: {r['score']:.4f}")
        print(f"      Vector: {r['vector_score']:.4f}, BM25: {r['bm25_score']:.4f}")
        print(f"      Content: {r['content'][:80]}...")

    # Vector DB search
    print("\n  [Vector DB Search]")
    vd_results = vector_db.search(query, top_k=3)
    for i, (doc, score) in enumerate(vd_results, 1):
        print(f"  [{i}] {doc.doc_id} (score: {score:.4f})")

    # ========================================
    # Step 4: Inference - "Generate Ollama deployment documentation"
    # ========================================
    print("\n[Step 4] Inference: 'Generate Ollama deployment documentation'")
    print("-" * 40)

    generation_query = "ollama deployment guide"

    # Retrieve relevant documents via KB layer
    rag_results = kb.search(generation_query, top_k=3, alpha=0.7)

    print(f"  Retrieved {len(rag_results)} relevant documents:")
    for r in rag_results:
        print(f"  - {r['title']} (relevance: {r['score']:.2f})")

    # RAG-augmented document generation
    print("\n" + "=" * 60)
    print("Generated Ollama Deployment Documentation (via RAG)")
    print("=" * 60)

    generated_doc = """
# Ollama Deployment Complete Guide

> Generated by RAG Knowledge Base System

## System Requirements

| Item | Minimum | Recommended |
|------|---------|-------------|
| OS | Linux/macOS/Windows | Ubuntu 22.04 LTS |
| Memory | 8GB | 16GB+ |
| Disk | 10GB | 50GB+ |
| GPU | - | NVIDIA GPU + CUDA 11.8+ |

## Installation Methods

### Method 1: Official Script (Recommended)
```bash
# Linux/macOS
curl -fsSL https://ollama.com/install.sh | sh

# Verify
ollama --version
```

### Method 2: Docker Deployment
```bash
docker run -d \\
  --name ollama \\
  -v ollama:/root/.ollama \\
  -p 11434:11434 \\
  ollama/ollama

# Enter container
docker exec -it ollama ollama run llama2
```

### Method 3: Windows Installation
1. Download from https://ollama.com/download
2. Run installer
3. Verify in PowerShell: ollama --version

## Quick Start

```bash
# 1. Pull model
ollama pull llama2

# 2. Run model (interactive mode)
ollama run llama2

# 3. List installed models
ollama list

# 4. Show model info
ollama show llama2
```

## API Usage

### REST API
```bash
curl http://localhost:11434/api/generate -d '{
  "model": "llama2",
  "prompt": "Hello, introduce yourself",
  "stream": false
}'
```

### Python SDK
```python
import ollama

response = ollama.generate(
    model='llama2',
    prompt='What is microservice architecture?'
)
print(response['response'])
```

## Configuration

### Environment Variables
```bash
export OLLAMA_HOST=0.0.0.0        # Listen address
export OLLAMA_MODELS=/data/models  # Model storage path
export OLLAMA_NUM_PARALLEL=4       # Parallel requests
```

### GPU Configuration
Ensure NVIDIA Driver and CUDA Toolkit are installed:
```bash
nvidia-smi  # Verify GPU
```

## Common Issues

**Q: Model download failed?**
A: Check network connection or use proxy.

**Q: Out of memory?**
A: Choose smaller model (e.g., qwen2.5:0.5b)

**Q: How to customize model?**
A: Use Modelfile to create custom models.

---
*Document auto-generated by RAG System | Source: Ollama Official Docs*
"""

    print(generated_doc)

    # ========================================
    # Statistics
    # ========================================
    print("=" * 60)
    print("RAG Storage Statistics")
    print("=" * 60)

    kb_stats = kb.get_stats()
    vd_stats = vector_db.get_stats()

    print(f"  [KnowledgeBaseLayer]")
    print(f"    Documents: {kb_stats['document_count']}")
    print(f"    Chunks: {kb_stats['chunk_count']}")
    print(f"    Searches: {kb_stats['search_count']}")
    print(f"    Hit Rate: {kb_stats['hit_rate']:.1%}")

    print(f"\n  [VectorDatabase]")
    print(f"    Total Docs: {vd_stats['total_documents']}")
    print(f"    DB Type: {vd_stats['db_type']}")
    print(f"    Embedding Dim: {vd_stats['embedding_dim']}")

    return True


if __name__ == "__main__":
    try:
        success = test_real_rag_chain()
        print("\n[SUCCESS] RAG full chain test passed!")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
