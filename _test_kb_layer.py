# -*- coding: utf-8 -*-
"""KB 层独立测试"""
import sys, traceback
sys.path.insert(0, 'd:/mhzyapp/LivingTreeAlAgent')

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    from core.fusion_rag.knowledge_base import KnowledgeBaseLayer
    kb = KnowledgeBaseLayer()
    print(f"KB initialized, model: {kb.embedding_model}")

    doc = {
        "id": "test001",
        "title": "测试文档",
        "content": "这是一条测试内容",
        "source": "test",
        "type": "text",
    }
    result = kb.add_document(doc)
    print(f"add_document result: {result}")

    # 搜索
    results = kb.search("测试", top_k=3)
    print(f"search results: {len(results)} items")
    for r in results:
        score = r.get("score", 0)
        content = r.get("content", r.get("text", ""))[:50]
        print(f"  score={score:.3f}, content={content}")

except Exception as e:
    traceback.print_exc()
