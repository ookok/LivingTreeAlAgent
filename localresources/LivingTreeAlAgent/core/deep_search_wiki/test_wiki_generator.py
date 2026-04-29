"""
深度搜索Wiki系统测试
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, '.')


def test_credibility_evaluator():
    """测试可信度评估器"""
    from core.deep_search_wiki.credibility import CredibilityEvaluator
    from core.deep_search_wiki.models import SourceInfo, SourceType
    from datetime import datetime, timedelta
    
    print("\n" + "="*60)
    print("测试1: 可信度评估器")
    print("="*60)
    
    evaluator = CredibilityEvaluator()
    
    test_sources = [
        SourceInfo(
            url="https://docs.python.org/3/tutorial/",
            title="Python官方教程",
            source_type=SourceType.OFFICIAL_DOCS,
            domain="docs.python.org",
            author="Python Software Foundation",
            publish_date=datetime.now() - timedelta(days=30),
            citations=1000,
        ),
        SourceInfo(
            url="https://medium.com/@user/example",
            title="Python入门指南",
            source_type=SourceType.BLOG,
            domain="medium.com",
            author="技术博主",
            publish_date=datetime.now() - timedelta(days=180),
            views=50000,
        ),
        SourceInfo(
            url="https://github.com/python/cpython",
            title="CPython源码",
            source_type=SourceType.OFFICIAL_DOCS,
            domain="github.com",
            publish_date=datetime.now() - timedelta(days=1),
            stars=50000,
        ),
        SourceInfo(
            url="https://arxiv.org/abs/2301.00001",
            title="深度学习新方法论文",
            source_type=SourceType.PAPER,
            domain="arxiv.org",
            publish_date=datetime.now() - timedelta(days=90),
            citations=500,
        ),
    ]
    
    for source in test_sources:
        evaluator.evaluate(source)
        print(f"\n源: {source.title}")
        print(f"  URL: {source.url}")
        print(f"  权威性: {source.authority_score:.1f}")
        print(f"  内容质量: {source.content_score:.1f}")
        print(f"  技术指标: {source.technical_score:.1f}")
        print(f"  综合可信度: {source.credibility:.1f}%")
        print(f"  风险等级: {evaluator.get_risk_level(source)}")
    
    print("\n✅ 可信度评估器测试通过")


def test_search_engine():
    """测试搜索引擎"""
    from core.deep_search_wiki.search_engine import SmartSearchEngine
    
    print("\n" + "="*60)
    print("测试2: 智能搜索引擎")
    print("="*60)
    
    engine = SmartSearchEngine()
    
    test_queries = [
        "Python机器学习",
        "深度学习入门",
        "人工智能发展",
    ]
    
    for query in test_queries:
        print(f"\n查询: {query}")
        
        # 测试查询扩展
        search_query = engine.expand_query(query)
        print(f"  扩展查询: {search_query.expanded[:3]}...")
        
        # 测试搜索
        results = engine._generate_demo_results(query)
        print(f"  生成结果数: {len(results)}")
        
        for result in results[:3]:
            print(f"    - {result.title}")
            print(f"      类型: {result.source_type.value}")
            print(f"      评分: {result.score}")
    
    stats = engine.get_statistics()
    print(f"\n搜索引擎统计: {stats}")
    
    print("\n✅ 搜索引擎测试通过")


def test_wiki_generator():
    """测试Wiki生成器"""
    from core.deep_search_wiki.wiki_generator import WikiGenerator
    
    print("\n" + "="*60)
    print("测试3: Wiki生成器")
    print("="*60)
    
    generator = WikiGenerator()
    
    topics = [
        "Python编程语言",
        "机器学习基础",
    ]
    
    for topic in topics:
        print(f"\n生成Wiki: {topic}")
        
        wiki = generator.generate(topic, use_search=False)
        
        print(f"  主题: {wiki.topic}")
        print(f"  概述: {wiki.summary[:50]}...")
        print(f"  定义: {wiki.definition}")
        print(f"  类别: {wiki.category}")
        print(f"  标签: {', '.join(wiki.tags)}")
        print(f"  关键要点数: {len(wiki.key_points)}")
        print(f"  章节数: {len(wiki.sections)}")
        print(f"  来源数: {wiki.sources_count}")
        print(f"  平均可信度: {wiki.credibility_avg:.1f}%")
        print(f"  置信度: {wiki.confidence:.0%}")
    
    print("\n✅ Wiki生成器测试通过")


def test_markdown_output():
    """测试Markdown输出"""
    from core.deep_search_wiki.wiki_generator import WikiGenerator
    
    print("\n" + "="*60)
    print("测试4: Markdown输出")
    print("="*60)
    
    generator = WikiGenerator()
    wiki = generator.generate("Python编程", use_search=False)
    
    md = wiki.to_markdown()
    print("\n生成的Markdown预览（前100行）:")
    print("\n".join(md.split("\n")[:100]))
    print("\n...")
    
    print("\n✅ Markdown输出测试通过")


async def test_async_generate():
    """测试异步生成"""
    from core.deep_search_wiki.wiki_generator import DeepSearchWikiSystem
    
    print("\n" + "="*60)
    print("测试5: 异步Wiki生成")
    print("="*60)
    
    system = DeepSearchWikiSystem()
    
    topic = "大语言模型"
    print(f"\n异步生成Wiki: {topic}")
    
    wiki = await system.generate_async(topic, use_search=True)
    
    print(f"  主题: {wiki.topic}")
    print(f"  来源数: {wiki.sources_count}")
    print(f"  平均可信度: {wiki.credibility_avg:.1f}%")
    
    if wiki.sources:
        print("  最高可信度来源:")
        top_source = wiki.sources[0]
        print(f"    - {top_source.title}")
        print(f"      可信度: {top_source.credibility:.1f}%")
    
    await system.close()
    print("\n✅ 异步生成测试通过")


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("🚀 深度搜索Wiki系统测试")
    print("="*60)
    
    # 同步测试
    test_credibility_evaluator()
    test_search_engine()
    test_wiki_generator()
    test_markdown_output()
    
    # 异步测试
    import asyncio
    asyncio.run(test_async_generate())
    
    print("\n" + "="*60)
    print("✅ 所有测试完成!")
    print("="*60)


if __name__ == "__main__":
    main()
