"""
Wisdom Network Example - 去中心化智慧网络使用示例
================================================

演示三网合一的工作流程

Author: LivingTreeAI Community
"""

import asyncio
import time


async def example_basic_search():
    """
    基础搜索示例

    场景：执行一次去中心化搜索
    """
    from wisdom_network import (
        WisdomNetwork,
        QueryContext,
        QueryCategory,
    )

    # 创建智慧网络
    network = WisdomNetwork("node_a")

    # 执行搜索
    result = await network.search(
        query="2025年排污许可新规",
        context=QueryContext(
            query="2025年排污许可新规",
            category=QueryCategory.LEGAL,
            language="zh",
        ),
    )

    print(f"查询: {result.query}")
    print(f"来源节点: {result.source_node}")
    print(f"结果数量: {len(result.results)}")
    print(f"执行时间: {result.execution_time:.3f}s")
    print(f"来自缓存: {result.from_cache}")

    return result


async def example_search_with_cache():
    """
    缓存查询示例

    演示：
    1. 首次搜索（缓存未命中）
    2. 再次搜索（缓存命中）
    """
    from wisdom_network import WisdomNetwork

    network = WisdomNetwork("node_b")
    query = "人工智能最新发展趋势"

    # 第一次搜索
    start1 = time.time()
    result1 = await network.search(query)
    time1 = time.time() - start1

    # 第二次搜索（应该命中缓存）
    start2 = time.time()
    result2 = await network.search(query)
    time2 = time.time() - start2

    print(f"第一次搜索: {time1:.3f}s, 来自缓存: {result1.from_cache}")
    print(f"第二次搜索: {time2:.3f}s, 来自缓存: {result2.from_cache}")
    print(f"加速比: {time1/time2:.1f}x")


async def example_contribution_recording():
    """
    贡献记录示例

    演示如何记录和查询贡献
    """
    from wisdom_network import get_credit_network, ContributionType

    credit = get_credit_network("node_c")

    # 记录多种类型的贡献
    await credit.record_contribution(
        event_type=ContributionType.SEARCH_EXECUTED,
        details={"query": "测试查询", "beneficiary": "node_d"},
    )

    await credit.record_contribution(
        event_type=ContributionType.CACHE_PROVIDED,
        details={"cache_size_kb": 512, "beneficiary": "network"},
    )

    await credit.record_contribution(
        event_type=ContributionType.DATA_RELAYED,
        details={"data_size_mb": 10, "beneficiary": "node_e"},
    )

    # 查询统计
    stats = credit.get_network_stats()
    print(f"贡献记录数: {stats['total_records']}")

    # 查询排行榜
    leaderboard = credit.get_reputation_leaderboard()
    print("声誉排行榜:")
    for entry in leaderboard[:5]:
        print(f"  {entry['node_id']}: {entry['score']:.3f}")


async def example_quota_calculation():
    """
    配额计算示例

    演示如何基于贡献计算资源配额
    """
    from wisdom_network import get_credit_network, ContributionType

    credit = get_credit_network("node_f")

    # 模拟一些贡献
    for i in range(10):
        await credit.record_contribution(
            event_type=ContributionType.SEARCH_EXECUTED,
            details={"query": f"查询{i}", "beneficiary": "network"},
        )

    # 计算配额
    quotas = credit.calculate_quotas("node_f", hours=24)

    print("基础配额:")
    print(f"  搜索查询: {quotas.get('search_queries', 0)}")
    print(f"  带宽(MB): {quotas.get('bandwidth_mb', 0)}")
    print(f"  缓存(MB): {quotas.get('cache_mb', 0)}")


async def example_network_stats():
    """
    网络统计示例

    演示如何获取全网统计信息
    """
    from wisdom_network import WisdomNetwork

    network = WisdomNetwork("node_g")

    # 执行一些搜索
    queries = [
        "人工智能",
        "机器学习",
        "深度学习",
        "自然语言处理",
        "计算机视觉",
    ]

    for query in queries:
        await network.search(query)

    # 获取统计
    all_stats = network.get_all_stats()

    print("=== 网络统计 ===")
    workflow_stats = all_stats["self"]["workflow_stats"]
    print(f"总查询数: {workflow_stats['total_queries']}")
    print(f"缓存命中率: {workflow_stats['cache_hit_rate']}")
    print(f"平均查询时间: {workflow_stats['avg_query_time_ms']}")

    print("\n缓存统计:")
    cache_stats = all_stats["self"]["distributed_cache"]["local_cache"]
    print(f"  缓存条目: {cache_stats['entries']}")
    print(f"  内存使用: {cache_stats['memory_mb']:.2f}MB")

    print("\n趋势查询:")
    trending = all_stats["self"]["distributed_cache"]["trending_queries"]
    for q in trending[:3]:
        print(f"  - {q}")


async def example_full_workflow():
    """
    完整工作流示例

    模拟场景：节点A搜索"2025年排污许可新规"
    """
    from wisdom_network import (
        WisdomNetwork,
        QueryContext,
        QueryCategory,
        ContributionType,
    )

    print("=== 完整工作流示例 ===")
    print("场景: 节点A搜索'2025年排污许可新规'\n")

    # 创建节点A
    node_a = WisdomNetwork("node_a")

    # 步骤1-2: 接收搜索请求，查询本地缓存 → 未命中
    print("步骤1-2: 查询本地缓存 → 未命中")

    # 步骤3: SearchRouter工作
    print("步骤3: SearchRouter匹配专长节点...")
    print("  - 匹配到节点B（环境法规专长）")
    print("  - 匹配到节点C（最近缓存过类似查询）")

    # 步骤4-6: 并行发送搜索请求，获得结果
    print("步骤4-6: 向B、C并行发送搜索请求...")

    # 模拟执行搜索
    result = await node_a.search(
        query="2025年排污许可新规",
        context=QueryContext(
            query="2025年排污许可新规",
            category=QueryCategory.LEGAL,
            domain="environmental_law",
        ),
    )

    print(f"\n获得结果:")
    print(f"  - 来源节点: {result.source_node}")
    print(f"  - 结果数量: {len(result.results)}")
    print(f"  - 执行时间: {result.execution_time:.3f}s")

    # 步骤7: 记录贡献
    print("\n步骤7: 记录贡献证明...")

    # 模拟节点B的贡献
    credit = node_a.workflow.credit
    proof = await credit.record_contribution(
        event_type=ContributionType.SEARCH_EXECUTED,
        details={
            "query": "2025年排污许可新规",
            "beneficiary": "node_a",
        },
        broadcast=True,
    )

    print(f"  - 贡献证明ID: {proof.proof_id}")
    print(f"  - 贡献类型: {proof.event_type.value}")
    print(f"  - 资源消耗: {proof.resource_consumed:.2f}")

    # 步骤8: 广播缓存通知
    print("\n步骤8: 广播缓存通知...")
    print("  - 节点D收到通知，存储索引")
    print("  - 下次类似查询可直接从D获取")

    # 最终统计
    print("\n=== 最终统计 ===")
    stats = node_a.workflow.get_network_stats()
    print(f"缓存命中率: {stats['workflow_stats']['cache_hit_rate']}")
    print(f"平均查询时间: {stats['workflow_stats']['avg_query_time_ms']}")


async def main():
    """运行所有示例"""
    print("=" * 60)
    print("去中心化智慧网络示例")
    print("=" * 60)

    examples = [
        ("基础搜索", example_basic_search),
        ("缓存查询", example_search_with_cache),
        ("贡献记录", example_contribution_recording),
        ("配额计算", example_quota_calculation),
        ("网络统计", example_network_stats),
        ("完整工作流", example_full_workflow),
    ]

    for name, func in examples:
        print(f"\n{'=' * 40}")
        print(f"示例: {name}")
        print("=" * 40)
        try:
            await func()
        except Exception as e:
            print(f"错误: {e}")
        await asyncio.sleep(0.5)


if __name__ == "__main__":
    asyncio.run(main())