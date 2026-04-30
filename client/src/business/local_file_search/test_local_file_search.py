"""
本地文件搜索模块测试
"""

import os
import sys
import time
import tempfile
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_file_classifier():
    """测试文件分类器"""
    print("\n" + "="*60)
    print("测试 1: 文件分类器")
    print("="*60)
    
    from business.local_file_search import FileClassifier
    
    classifier = FileClassifier()
    
    test_cases = [
        ("/path/to/main.py", "代码"),
        ("/path/to/readme.md", "文档"),
        ("/path/to/image.png", "媒体"),
        ("/path/to/config.yaml", "配置"),
        ("/path/to/data.zip", "压缩包"),
        ("/path/to/db.sqlite", "数据"),
    ]
    
    all_passed = True
    for path, expected_category in test_cases:
        result = classifier.classify(path)
        status = "PASS" if result.value == expected_category else "FAIL"
        if status == "FAIL":
            all_passed = False
        print(f"  [{status}] {os.path.basename(path):20} -> {result.value} (期望: {expected_category})")
    
    return all_passed


def test_indexer_basic():
    """测试索引器基本功能"""
    print("\n" + "="*60)
    print("测试 2: 索引器基本功能")
    print("="*60)
    
    from business.local_file_search import FastFileIndexer
    
    db_path = os.path.join(tempfile.gettempdir(), "test_file_index.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    
    try:
        indexer = FastFileIndexer(db_path=db_path)
        indexer.init_database()
        
        test_dir = tempfile.gettempdir()
        print(f"  索引目录: {test_dir}")
        
        start_time = time.time()
        indexer.build_index([test_dir])
        elapsed = time.time() - start_time
        
        print(f"  索引用时: {elapsed:.2f}秒")
        print(f"  索引文件数: {indexer._indexed_count}")
        print(f"  索引大小: {indexer.get_index_size() / 1024:.1f} KB")
        
        print("\n  搜索测试:")
        results = indexer.search("*.py", limit=5)
        print(f"    搜索 '*.py': {len(results)} 结果")
        for r in results[:3]:
            print(f"      - {r.filename}")
        
        start_time = time.time()
        for _ in range(10):
            indexer.search("*.py", limit=20)
        avg_time = (time.time() - start_time) / 10 * 1000
        print(f"    平均搜索延迟: {avg_time:.1f}ms")
        
        return True
        
    except Exception as e:
        logger.error(f"索引器测试失败: {e}")
        return False


def test_router_intent():
    """测试路由意图解析"""
    print("\n" + "="*60)
    print("测试 3: 路由意图解析")
    print("="*60)
    
    from business.local_file_search import LocalFileSearchRouter
    
    router = LocalFileSearchRouter()
    
    test_queries = [
        "找一下 *.py 文件",
        "搜索 main.js 在哪里",
        "最近的文档有哪些",
        "大于 10MB 的文件",
        "配置文件的路径",
        "代码文件在哪里",
    ]
    
    for query in test_queries:
        sq = router.parse_intent(query)
        print(f"  '{query}'")
        print(f"    -> 意图: {sq.intent.value}")
        print(f"    -> 关键词: {sq.keywords}")
        print(f"    -> 过滤器: {sq.filters}")
        print()
    
    return True


def test_usn_monitor():
    """测试 USN Journal 监控"""
    print("\n" + "="*60)
    print("测试 4: USN Journal 监控")
    print("="*60)
    
    if sys.platform != 'win32':
        print("  [SKIP] USN Journal 仅在 Windows 上可用")
        return True
    
    from business.local_file_search.usn_monitor import is_usn_available
    
    available = is_usn_available()
    print(f"  USN Journal 可用: {available}")
    
    if available:
        from business.local_file_search import USNJournalMonitor
        changes = []
        
        def on_change(ch):
            changes.extend(ch)
        
        try:
            with USNJournalMonitor("C:", on_change=on_change) as monitor:
                time.sleep(1)
                monitor.poll()
                
                if changes:
                    print(f"  检测到 {len(changes)} 个变更")
                    for c in changes[:3]:
                        print(f"    - {c.path}")
                else:
                    print("  未检测到变更")
                        
        except Exception as e:
            print(f"  USN 监控测试失败: {e}")
    
    return True


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*60)
    print("本地文件搜索模块测试套件")
    print("="*60)
    
    tests = [
        ("文件分类器", test_file_classifier),
        ("索引器基本功能", test_indexer_basic),
        ("路由意图解析", test_router_intent),
        ("USN Journal 监控", test_usn_monitor),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            logger.error(f"测试 '{name}' 异常: {e}")
            results.append((name, False))
    
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    
    passed_count = sum(1 for _, p in results if p)
    total_count = len(results)
    
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")
    
    print(f"\n总计: {passed_count}/{total_count} 通过")
    
    return passed_count == total_count


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
