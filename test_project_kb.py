"""
测试：对项目文件夹进行知识库初始化，搜索"项目简介"
"""
import sys
import os
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.fusion_rag.knowledge_base import KnowledgeBaseLayer


def scan_project_docs(project_root: str, extensions=None) -> list:
    """扫描项目文件夹中的文档"""
    if extensions is None:
        extensions = ['.md', '.txt', '.py', '.yaml', '.yml', '.json', '.toml']
    
    docs = []
    root = Path(project_root)
    
    # 跳过目录
    skip_dirs = {
        '__pycache__', '.git', '.pytest_cache', 'node_modules',
        '.venv', 'venv', 'env', '.env', 'data', 'assets',
        '.workbuddy', 'test', 'tests', '.idea', '.vscode'
    }
    
    for ext in extensions:
        for f in root.rglob(f'*{ext}'):
            # 跳过目录
            if any(skip in f.parts for skip in skip_dirs):
                continue
            
            try:
                # 读取文件
                content = f.read_text(encoding='utf-8', errors='ignore')
                
                # 跳过空文件或太大文件
                if len(content) < 50 or len(content) > 50000:
                    continue
                
                # 相对路径
                rel_path = str(f.relative_to(root))
                
                docs.append({
                    "id": rel_path.replace('/', '_').replace('\\', '_'),
                    "title": f.name,
                    "content": content,
                    "type": ext.lstrip('.'),
                    "metadata": {
                        "path": rel_path,
                        "size": len(content),
                        "extension": ext
                    }
                })
            except Exception as e:
                print(f"  Skip: {f.name} ({e})")
                continue
    
    return docs


def main():
    project_root = r"D:\mhzyapp\LivingTreeAlAgent"
    query = "项目简介"
    
    print("=" * 70)
    print(f"项目知识库初始化测试")
    print(f"项目路径: {project_root}")
    print("=" * 70)
    
    # ========== 步骤1: 扫描文档 ==========
    print(f"\n[步骤1] 扫描项目文档...")
    scan_start = time.time()
    docs = scan_project_docs(project_root)
    scan_time = (time.time() - scan_start) * 1000
    
    print(f"  扫描完成: {len(docs)} 个文档")
    print(f"  扫描耗时: {scan_time:.1f}ms")
    
    # 显示文档类型分布
    type_counts = {}
    for d in docs:
        t = d['type']
        type_counts[t] = type_counts.get(t, 0) + 1
    
    print(f"  文档类型分布:")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"    - {t}: {c} 个")
    
    # ========== 步骤2: 初始化知识库 ==========
    print(f"\n[步骤2] 初始化知识库...")
    kb_start = time.time()
    kb = KnowledgeBaseLayer(chunk_size=512, chunk_overlap=64)
    kb_init_time = (time.time() - kb_start) * 1000
    print(f"  初始化耗时: {kb_init_time:.1f}ms")
    
    # ========== 步骤3: 添加文档到知识库 ==========
    print(f"\n[步骤3] 添加文档到知识库...")
    add_start = time.time()
    total_chunks = 0
    for i, doc in enumerate(docs):
        chunks = kb.add_document(doc)
        total_chunks += chunks
        if (i + 1) % 100 == 0:
            print(f"  已处理 {i+1}/{len(docs)} 文档...")
    add_time = (time.time() - add_start) * 1000
    
    print(f"  添加完成: {len(docs)} 文档 -> {total_chunks} 分块")
    print(f"  添加耗时: {add_time:.1f}ms")
    
    # ========== 步骤4: 搜索"项目简介" ==========
    print(f"\n[步骤4] 搜索查询: '{query}'")
    search_start = time.time()
    results = kb.search(query, top_k=5, alpha=0.6)
    search_time = (time.time() - search_start) * 1000
    
    print(f"  搜索耗时: {search_time:.1f}ms")
    print(f"  找到 {len(results)} 条结果")
    
    # ========== 步骤5: 显示结果 ==========
    print(f"\n[步骤5] 搜索结果:")
    print("-" * 70)
    
    for i, r in enumerate(results, 1):
        print(f"\n结果 {i} (分数: {r['score']:.3f})")
        print(f"  文档: {r['chunk']['title']}")
        print(f"  路径: {r['chunk']['metadata'].get('path', 'N/A')}")
        print(f"  向量分: {r.get('vector_score', 0):.3f}, BM25分: {r.get('bm25_score', 0):.3f}")
        print(f"  内容预览: {r['chunk']['content'][:200]}...")
    
    # ========== 性能报告 ==========
    print("\n" + "=" * 70)
    print("性能报告")
    print("=" * 70)
    total_time = scan_time + kb_init_time + add_time + search_time
    print(f"  扫描文档:     {scan_time:>8.1f}ms  ({len(docs)} 文档)")
    print(f"  初始化知识库: {kb_init_time:>8.1f}ms")
    print(f"  添加文档:     {add_time:>8.1f}ms  ({total_chunks} 分块)")
    print(f"  搜索查询:     {search_time:>8.1f}ms  ({len(results)} 结果)")
    print(f"  " + "-" * 40)
    print(f"  总耗时:       {total_time:>8.1f}ms")
    
    # ========== 再次搜索（验证缓存） ==========
    print("\n[步骤6] 再次搜索（验证）...")
    search2_start = time.time()
    results2 = kb.search(query, top_k=5, alpha=0.6)
    search2_time = (time.time() - search2_start) * 1000
    print(f"  第二次搜索耗时: {search2_time:.3f}ms")
    print(f"  结果数量: {len(results2)}")
    
    print("\n" + "=" * 70)
    print("测试完成!")
    print("=" * 70)


if __name__ == "__main__":
    main()
