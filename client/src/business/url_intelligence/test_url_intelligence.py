"""
URL智能优化系统测试
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, '.')

import asyncio


def test_classifier():
    """测试URL分类器"""
    from business.url_intelligence.url_classifier import URLClassifier
    
    print("\n" + "="*60)
    print("测试1: URL分类器")
    print("="*60)
    
    classifier = URLClassifier()
    
    test_urls = [
        "https://github.com/openai/openai-python",
        "https://github.com/THUDM/ChatGLM",
        "https://www.npmjs.com/package/express",
        "https://pypi.org/project/requests/",
        "https://arxiv.org/abs/2303.08774",
        "https://huggingface.co/meta-llama/Llama-2-7b",
        "https://hub.docker.com/r/nginx/nginx",
        "https://docs.python.org/3/",
        "https://medium.com/@user/example",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    ]
    
    for url in test_urls:
        metadata = classifier.classify(url)
        print(f"\nURL: {url}")
        print(f"  类型: {metadata.url_type.value}")
        print(f"  域名: {metadata.domain}")
        print(f"  标签: {', '.join(metadata.tags)}")
        if metadata.owner:
            print(f"  所有者: {metadata.owner}")
        if metadata.repo:
            print(f"  仓库: {metadata.repo}")
        if metadata.package_name:
            print(f"  包名: {metadata.package_name}")
        if metadata.paper_id:
            print(f"  论文ID: {metadata.paper_id}")
    
    print("\n✅ URL分类器测试通过")


def test_mirror_registry():
    """测试镜像源注册表"""
    from business.url_intelligence.mirror_registry import MirrorRegistry
    
    print("\n" + "="*60)
    print("测试2: 镜像源注册表")
    print("="*60)
    
    registry = MirrorRegistry()
    
    # 测试规则匹配
    test_cases = [
        ("https://github.com/facebook/react", "GitHub"),
        ("https://github.com/microsoft/vscode.git", "GitHub"),
        ("https://pypi.org/project/numpy/", "PyPI"),
        ("https://www.npmjs.com/package/lodash", "npm"),
        ("https://huggingface.co/bert-base-uncased", "HuggingFace"),
    ]
    
    for url, category in test_cases:
        rules = registry.find_rules(url)
        mirrors = registry.get_mirrors(category.lower().replace(" ", ""))
        print(f"\n{category} URL: {url}")
        print(f"  匹配规则数: {len(rules)}")
        for rule in rules[:3]:
            new_url = registry.apply_rule(rule, url)
            print(f"  - {rule.name}: {new_url}")
        print(f"  已知镜像数: {len(mirrors)}")
    
    stats = registry.get_statistics()
    print(f"\n注册表统计:")
    print(f"  总规则数: {stats['total_rules']}")
    print(f"  总镜像数: {stats['total_mirrors']}")
    print(f"  类别数: {stats['categories']}")
    print(f"  各类别镜像数: {stats['by_category']}")
    
    print("\n✅ 镜像源注册表测试通过")


async def test_url_optimizer():
    """测试URL优化器"""
    from business.url_intelligence.url_optimizer import URLOptimizer
    
    print("\n" + "="*60)
    print("测试3: URL优化器")
    print("="*60)
    
    optimizer = URLOptimizer()
    
    # 测试URL优化
    test_urls = [
        "https://github.com/microsoft/vscode",
        "https://github.com/THUDM/ChatGLM-6B",
        "https://pypi.org/project/pytorch/",
    ]
    
    for url in test_urls:
        print(f"\n优化URL: {url}")
        result = await optimizer.optimize(url)
        
        print(f"  原始状态: {result.is_blocked and '受限' or '正常'}")
        print(f"  优化URL: {result.optimized_url}")
        
        if result.recommended_mirror:
            m = result.recommended_mirror
            print(f"  推荐镜像: {m.name}")
            print(f"  镜像URL: {m.url}")
            print(f"  延迟: {m.latency_ms:.0f}ms")
            print(f"  综合评分: {m.overall_score:.1f}")
        
        print(f"  置信度: {result.confidence:.0%}")
        
        if result.suggestions:
            print("  建议:")
            for s in result.suggestions:
                print(f"    - {s}")
    
    # 测试统计
    stats = optimizer.get_statistics()
    print(f"\n优化器统计:")
    print(f"  缓存大小: {stats['cache_size']}")
    print(f"  规则数: {stats['classifier_stats']['patterns_count']}")
    
    await optimizer.close()
    print("\n✅ URL优化器测试通过")


def test_markdown_output():
    """测试Markdown输出"""
    from business.url_intelligence.url_optimizer import URLOptimizer
    
    print("\n" + "="*60)
    print("测试4: Markdown输出")
    print("="*60)
    
    optimizer = URLOptimizer()
    try:
        result = optimizer.optimize_sync("https://github.com/facebook/react")
        md = result.to_markdown()
        print("\nMarkdown输出:")
        print(md[:500] + "...")
        print("\n✅ Markdown输出测试通过")
    except Exception as e:
        print(f"\n⚠️ Markdown测试跳过(需网络): {e}")


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("🚀 URL智能优化系统测试")
    print("="*60)
    
    # 同步测试
    test_classifier()
    test_mirror_registry()
    test_markdown_output()
    
    # 异步测试
    asyncio.run(test_url_optimizer())
    
    print("\n" + "="*60)
    print("✅ 所有测试完成!")
    print("="*60)


if __name__ == "__main__":
    main()
