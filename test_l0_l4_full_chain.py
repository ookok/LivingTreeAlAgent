"""
测试完整 L0-L4 路由链路
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.fusion_rag.intent_classifier import QueryIntentClassifier
from core.fusion_rag.intelligent_router import IntelligentRouter
from core.fusion_rag.knowledge_base import KnowledgeBaseLayer
from core.fusion_rag.l4_aware_router import L4AwareRouter


def scan_docs(project_root: str, max_docs: int = 200) -> list:
    """扫描项目文档"""
    extensions = ['.md', '.txt', '.py', '.yaml', '.yml', '.json', '.toml']
    docs = []
    root = Path(project_root)
    skip_dirs = {'__pycache__', '.git', '.pytest_cache', 'node_modules',
                 '.venv', 'venv', 'env', 'data', 'assets', '.workbuddy', 'test', 'tests'}

    for ext in extensions:
        for f in root.rglob(f'*{ext}'):
            if len(docs) >= max_docs:
                break
            if any(skip in f.parts for skip in skip_dirs):
                continue
            try:
                content = f.read_text(encoding='utf-8', errors='ignore')
                if 100 < len(content) < 30000:
                    rel_path = str(f.relative_to(root))
                    docs.append({
                        "id": rel_path.replace('/', '_').replace('\\', '_'),
                        "title": f.name,
                        "content": content,
                        "type": ext.lstrip('.'),
                        "metadata": {"path": rel_path, "size": len(content)}
                    })
            except:
                pass
        if len(docs) >= max_docs:
            break
    return docs


def main():
    project_root = r"D:\mhzyapp\LivingTreeAlAgent"
    query = "项目简介"

    print("=" * 70)
    print("L0-L4 Full Routing Chain Test")
    print("=" * 70)

    # ========== L0: Intent Classification ==========
    print(f"\n[Step 1] L0: Intent Classification")
    l0_start = time.time()

    intent_classifier = QueryIntentClassifier()
    intent_result = intent_classifier.classify(query)
    l0_time = (time.time() - l0_start) * 1000

    print(f"  Intent: {intent_result['primary']} (confidence: {intent_result['confidence']:.2f})")
    print(f"  Recommended layers: {intent_classifier.get_recommended_layers(intent_result)}")
    print(f"  Time: {l0_time:.1f}ms")

    # ========== L1-L2: Intelligent Router ==========
    print(f"\n[Step 2] L1-L2: Intelligent Router")
    l1_start = time.time()

    router = IntelligentRouter()
    route_plan = router.route(
        query=query,
        intent=intent_result,
        latency_budget_ms=2000
    )
    l1_time = (time.time() - l1_start) * 1000

    print(f"  Strategy: {route_plan['strategy']}")
    print(f"  Selected layers: {route_plan['enabled_layers']}")
    print(f"  L4 needed: {route_plan['needs_llm']}")
    print(f"  Time: {l1_time:.1f}ms")

    # ========== L3: Knowledge Base Search ==========
    print(f"\n[Step 3] L3: Knowledge Base Search")

    # Scan docs
    print("  Scanning docs...")
    scan_start = time.time()
    docs = scan_docs(project_root, max_docs=200)
    scan_time = (time.time() - scan_start) * 1000
    print(f"  Scanned: {len(docs)} docs ({scan_time:.1f}ms)")

    # Init KB
    print("  Initializing KB...")
    kb_init_start = time.time()
    kb = KnowledgeBaseLayer(chunk_size=512, chunk_overlap=64)
    kb_init_time = (time.time() - kb_init_start) * 1000

    # Add docs
    print("  Adding docs to KB...")
    add_start = time.time()
    total_chunks = 0
    for doc in docs:
        chunks = kb.add_document(doc)
        total_chunks += chunks
    add_time = (time.time() - add_start) * 1000
    print(f"  Added: {len(docs)} docs -> {total_chunks} chunks ({add_time:.1f}ms)")

    # Search
    print(f"  Searching: '{query}'")
    l3_start = time.time()
    results = kb.search(query, top_k=5)
    l3_time = (time.time() - l3_start) * 1000
    print(f"  Found: {len(results)} results ({l3_time:.1f}ms)")

    # ========== L4: LLM Enhancement (Optional) ==========
    print(f"\n[Step 4] L4: LLM Enhancement")

    # Get L4 decision from router
    l4_decision = route_plan.get('needs_llm', False)
    print(f"  L4 Needed: {l4_decision}")
    print(f"  LLM Reason: {route_plan.get('llm_reason', 'N/A')}")

    # ========== Summary ==========
    print("\n" + "=" * 70)
    print("ROUTING CHAIN SUMMARY")
    print("=" * 70)
    print(f"  L0 Intent:       {l0_time:>8.1f}ms  [{intent_result['primary']}]")
    print(f"  L1-L2 Router:    {l1_time:>8.1f}ms  [{route_plan['strategy']}]")
    print(f"  L3 KB Search:    {scan_time + kb_init_time + add_time + l3_time:>8.1f}ms  [{total_chunks} chunks]")
    print(f"  L4 Enhancement:  {'N/A':>8}  [{route_plan.get('llm_reason', 'skipped') if not l4_decision else 'needed'}]")
    print("=" * 70)

    # Show search results
    print(f"\n[Results] Top {len(results)} results:")
    for i, r in enumerate(results, 1):
        print(f"  {i}. {r['title']} (score: {r['score']:.3f})")
        preview = r['content'][:80].replace('\n', ' ')
        print(f"     {preview}...")


if __name__ == "__main__":
    main()
