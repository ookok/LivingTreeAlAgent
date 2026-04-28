"""
测试：对项目文件夹进行知识库初始化，搜索"项目简介"（快速版）
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.fusion_rag.knowledge_base import KnowledgeBaseLayer


def main():
    project_root = r"D:\mhzyapp\LivingTreeAlAgent"
    query = "项目简介"
    
    print("=" * 70)
    print("Project Knowledge Base Test")
    print("=" * 70)
    
    # Scan key docs
    key_files = [
        "README.md",
        "ARCHITECTURE.md", 
        "ARCHITECTURE_V2.md",
        "AGENTS.md",
        "package.json",
        "pyproject.toml",
    ]
    
    root = Path(project_root)
    docs = []
    
    for pattern in key_files:
        for f in root.rglob(pattern):
            try:
                content = f.read_text(encoding='utf-8', errors='ignore')
                if len(content) > 50:
                    rel_path = str(f.relative_to(root))
                    docs.append({
                        "id": rel_path.replace('/', '_'),
                        "title": f.name,
                        "content": content,
                        "type": f.suffix.lstrip('.'),
                        "metadata": {"path": rel_path, "size": len(content)}
                    })
                    print(f"  + {rel_path} ({len(content)} chars)")
            except:
                pass
    
    print(f"\nScan: {len(docs)} docs")
    
    # ========== Init KB ==========
    print(f"\n[Init KB]")
    kb_start = time.time()
    kb = KnowledgeBaseLayer(chunk_size=512, chunk_overlap=64)
    kb_init_time = (time.time() - kb_start) * 1000
    
    # ========== Add docs ==========
    print(f"\n[Add docs]")
    add_start = time.time()
    total_chunks = 0
    for doc in docs:
        chunks = kb.add_document(doc)
        total_chunks += chunks
    add_time = (time.time() - add_start) * 1000
    print(f"  Added: {len(docs)} docs -> {total_chunks} chunks ({add_time:.1f}ms)")
    
    # ========== Search ==========
    print(f"\n[Search] Query: '{query}'")
    search_start = time.time()
    results = kb.search(query, top_k=5)
    search_time = (time.time() - search_start) * 1000
    print(f"  Time: {search_time:.1f}ms, Results: {len(results)}")
    
    # ========== Show results ==========
    print(f"\n[Results]")
    for i, r in enumerate(results, 1):
        print(f"\n{i}. {r['title']} (score: {r['score']:.3f})")
        print(f"   path: {r.get('metadata', {}).get('path', 'N/A')}")
        print(f"   vector: {r.get('vector_score', 0):.3f}, bm25: {r.get('bm25_score', 0):.3f}")
        preview = r['content'][:150].replace('\n', ' ')
        print(f"   preview: {preview}...")
    
    # Stats
    stats = kb.get_stats()
    print(f"\n[Stats]")
    print(f"  docs: {stats['document_count']}, chunks: {stats['chunk_count']}")
    print(f"  search_count: {stats['search_count']}, hit_rate: {stats['hit_rate']:.1%}")
    
    print(f"\n[Performance]")
    print(f"  init: {kb_init_time:.1f}ms")
    print(f"  add: {add_time:.1f}ms")
    print(f"  search: {search_time:.1f}ms")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
