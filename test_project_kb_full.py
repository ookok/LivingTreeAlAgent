"""
测试：对项目文件夹进行知识库初始化，搜索"项目简介"（完整版）
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.fusion_rag.knowledge_base import KnowledgeBaseLayer


def scan_all_docs(project_root: str, max_docs: int = 200) -> list:
    """扫描项目所有文档"""
    extensions = ['.md', '.txt', '.py', '.yaml', '.yml', '.json', '.toml']
    
    docs = []
    root = Path(project_root)
    
    skip_dirs = {
        '__pycache__', '.git', '.pytest_cache', 'node_modules',
        '.venv', 'venv', 'env', '.env', 'data', 'assets',
        '.workbuddy', 'test', 'tests', '.idea', '.vscode'
    }
    
    for ext in extensions:
        for f in root.rglob(f'*{ext}'):
            if len(docs) >= max_docs:
                break
            if any(skip in f.parts for skip in skip_dirs):
                continue
            try:
                content = f.read_text(encoding='utf-8', errors='ignore')
                if len(content) < 100 or len(content) > 30000:
                    continue
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
    print("Project Knowledge Base Full Test")
    print("=" * 70)
    
    # ========== Scan ==========
    print(f"\n[1] Scanning docs...")
    scan_start = time.time()
    docs = scan_all_docs(project_root, max_docs=200)
    scan_time = (time.time() - scan_start) * 1000
    
    # Type distribution
    type_counts = {}
    total_chars = 0
    for d in docs:
        t = d['type']
        type_counts[t] = type_counts.get(t, 0) + 1
        total_chars += len(d['content'])
    
    print(f"  Scan: {len(docs)} docs, {total_chars} chars")
    print(f"  Time: {scan_time:.1f}ms")
    print(f"  Types: {dict(sorted(type_counts.items(), key=lambda x: -x[1]))}")
    
    # ========== Init KB ==========
    print(f"\n[2] Init KB...")
    kb_start = time.time()
    kb = KnowledgeBaseLayer(chunk_size=512, chunk_overlap=64)
    kb_init_time = (time.time() - kb_start) * 1000
    print(f"  Time: {kb_init_time:.1f}ms")
    
    # ========== Add docs ==========
    print(f"\n[3] Adding docs...")
    add_start = time.time()
    total_chunks = 0
    for doc in docs:
        chunks = kb.add_document(doc)
        total_chunks += chunks
    add_time = (time.time() - add_start) * 1000
    print(f"  Added: {len(docs)} docs -> {total_chunks} chunks")
    print(f"  Time: {add_time:.1f}ms")
    
    # ========== Search ==========
    print(f"\n[4] Search: '{query}'")
    
    # Search 3 times
    search_times = []
    for i in range(3):
        search_start = time.time()
        results = kb.search(query, top_k=5)
        search_time = (time.time() - search_start) * 1000
        search_times.append(search_time)
        if i == 0:
            print(f"  Round {i+1}: {search_time:.1f}ms, {len(results)} results")
        else:
            print(f"  Round {i+1}: {search_time:.1f}ms")
    
    avg_search_time = sum(search_times) / len(search_times)
    print(f"  Avg: {avg_search_time:.1f}ms")
    
    # ========== Show results ==========
    print(f"\n[5] Results:")
    for i, r in enumerate(results, 1):
        print(f"\n{i}. {r['title']} (score: {r['score']:.3f})")
        print(f"   vector: {r.get('vector_score', 0):.3f}, bm25: {r.get('bm25_score', 0):.3f}")
        preview = r['content'][:120].replace('\n', ' ')
        print(f"   {preview}...")
    
    # ========== Stats ==========
    stats = kb.get_stats()
    print(f"\n[6] KB Stats:")
    print(f"  docs: {stats['document_count']}")
    print(f"  chunks: {stats['chunk_count']}")
    print(f"  vocab: {stats['vocabulary_size']}")
    print(f"  avg_chunks/doc: {stats['avg_chunks_per_doc']:.1f}")
    
    # ========== Performance Report ==========
    total_time = scan_time + kb_init_time + add_time + avg_search_time
    print(f"\n" + "=" * 70)
    print("PERFORMANCE REPORT")
    print("=" * 70)
    print(f"  Scan docs:      {scan_time:>8.1f}ms  ({len(docs)} docs)")
    print(f"  Init KB:        {kb_init_time:>8.1f}ms")
    print(f"  Add docs:       {add_time:>8.1f}ms  ({total_chunks} chunks)")
    print(f"  Search (avg):   {avg_search_time:>8.1f}ms  (3 rounds)")
    print(f"  " + "-" * 40)
    print(f"  TOTAL:          {total_time:>8.1f}ms")
    print("=" * 70)


if __name__ == "__main__":
    main()
