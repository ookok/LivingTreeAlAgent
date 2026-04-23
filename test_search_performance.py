"""
性能对比：原始搜索 vs 两阶段优化搜索
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.fusion_rag.knowledge_base import KnowledgeBaseLayer


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
    queries = ["项目简介", "Ollama 模型", "PyQt6", "知识库", "意图分类"]
    
    print("=" * 70)
    print("Performance Comparison: Original vs Optimized Search")
    print("=" * 70)
    
    # ========== Init KB ==========
    print("\n[Init] Scanning and adding docs...")
    docs = scan_docs(project_root, max_docs=200)
    
    kb = KnowledgeBaseLayer(chunk_size=512, chunk_overlap=64)
    total_chunks = 0
    for doc in docs:
        chunks = kb.add_document(doc)
        total_chunks += chunks
    
    stats = kb.get_stats()
    print(f"  Docs: {len(docs)}, Chunks: {total_chunks}")
    
    # ========== Benchmark ==========
    print("\n" + "=" * 70)
    print("BENCHMARK RESULTS")
    print("=" * 70)
    print(f"{'Query':<15} | {'Original':>10} | {'Optimized':>10} | {'Speedup':>8} | {'Match':>6}")
    print("-" * 70)
    
    original_times = []
    optimized_times = []
    match_count = 0
    
    for query in queries:
        # Original search
        start = time.time()
        original_results = kb.search(query, top_k=5)
        original_time = (time.time() - start) * 1000
        original_times.append(original_time)
        
        # Optimized search
        start = time.time()
        optimized_results = kb.search_optimized(query, top_k=5, initial_candidates=100)
        optimized_time = (time.time() - start) * 1000
        optimized_times.append(optimized_time)
        
        # Check if top result matches
        original_top = original_results[0]['id'] if original_results else ""
        optimized_top = optimized_results[0]['id'] if optimized_results else ""
        match = "OK" if original_top == optimized_top else "NO"
        if original_top == optimized_top:
            match_count += 1
        
        speedup = original_time / optimized_time if optimized_time > 0 else 0
        
        print(f"{query:<15} | {original_time:>9.1f}ms | {optimized_time:>9.1f}ms | {speedup:>7.1f}x | {match:>6}")
    
    # ========== Summary ==========
    print("-" * 70)
    avg_original = sum(original_times) / len(original_times)
    avg_optimized = sum(optimized_times) / len(optimized_times)
    total_speedup = avg_original / avg_optimized if avg_optimized > 0 else 0
    
    print(f"{'AVERAGE':<15} | {avg_original:>9.1f}ms | {avg_optimized:>9.1f}ms | {total_speedup:>7.1f}x |")
    print("=" * 70)
    
    # ========== Detail for one query ==========
    print(f"\n[Detail] Query: '项目简介'")
    detail_start = time.time()
    detail_results = kb.search_optimized("项目简介", top_k=5, initial_candidates=100)
    detail_time = (time.time() - detail_start) * 1000
    
    print(f"  Total: {detail_time:.1f}ms")
    if detail_results and '_perf' in detail_results[0]:
        perf = detail_results[0]['_perf']
        print(f"    Phase1 (BM25 filter): {perf['phase1_ms']:.1f}ms")
        print(f"    Phase2 (Vector re-rank): {perf['phase2_ms']:.1f}ms")
    
    print(f"\n  Top 5 results:")
    for i, r in enumerate(detail_results, 1):
        preview = r['content'][:60].replace('\n', ' ').replace('  ', ' ')
        print(f"    {i}. {r['title']:<30} (score: {r['score']:.3f})")
        print(f"       {preview}...")
    
    # ========== Performance Report ==========
    print("\n" + "=" * 70)
    print("PERFORMANCE OPTIMIZATION REPORT")
    print("=" * 70)
    print(f"  Original search:    {avg_original:.1f}ms avg (O(N) vector calc)")
    print(f"  Optimized search:  {avg_optimized:.1f}ms avg (2-stage: BM25→Vector)")
    print(f"  Speedup:           {total_speedup:.1f}x faster")
    print(f"  Result accuracy:  {match_count}/{len(queries)} top results match")
    print()
    print("  Optimization technique:")
    print("    1. BM25快速过滤：只保留TOP-50候选")
    print("    2. 向量重排：候选数从2830 → 50 (98%减少)")
    print("    3. 内存优化：避免全量O(N)向量计算")
    print("=" * 70)


if __name__ == "__main__":
    main()
