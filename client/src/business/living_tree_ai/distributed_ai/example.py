"""
分布式 AI 计算网络示例

展示完整的三层架构运作流程
"""

import asyncio
from business.living_tree_ai.distributed_ai import (
    # 核心组件
    CentralBrain,
    IntentCollector,
    OverseasCluster,
    EdgeAccelerator,
    NodeInfo,
    NodeRole,
    NodeStatus,
    TaskType,
    RoutingStrategy,
    TaskRequest,
    TaskResult,
    TaskStatus,
    # 深度匹配
    MatchingDispatcher,
    MatchingContext,
    MatchingType,
)


async def example_basic_flow():
    """
    基础流程示例：用户发出请求 → 三层协作 → 返回结果
    """
    print("=" * 60)
    print("示例1: 基础流程 - 代码补全请求")
    print("=" * 60)

    # 1. 创建中心大脑
    brain = CentralBrain("central_brain_001")

    # 2. 注册节点
    brain.register_node(NodeInfo(
        node_id="edge_node_001",
        role=NodeRole.EDGE,
        status=NodeStatus.ONLINE,
        capabilities=["code", "lsp", "completion"],
        latency_ms=15.0,
        region="cn-east"
    ))

    brain.register_node(NodeInfo(
        node_id="overseas_cluster_001",
        role=NodeRole.OVERSEAS,
        status=NodeStatus.ONLINE,
        capabilities=["search", "academic", "heavy_compute"],
        latency_ms=200.0,
        gpu_count=4,
        region="us-west"
    ))

    print(f"✓ 中心大脑初始化完成")
    print(f"✓ 已注册 {len(brain.node_registry.nodes)} 个节点")
    print(f"  - 边缘节点: 1 (延迟 15ms)")
    print(f"  - 海外集群: 1 (延迟 200ms)")

    # 3. 创建客户端感知器
    collector = IntentCollector("user_laptop_001")
    collector.active_apps["ide"] = {
        "project": {"name": "my-project", "language": "python"}
    }

    # 4. 捕获用户意图
    task = await collector.capture_intent(
        "帮我补全这个异步函数",
        input_type="text"
    )
    task.task_type = TaskType.CODE_COMPLETION
    task.routing = RoutingStrategy.LOWEST_LATENCY

    print(f"\n✓ 用户意图捕获")
    print(f"  - 任务ID: {task.task_id}")
    print(f"  - 任务类型: {task.task_type.value}")
    print(f"  - 路由策略: {task.routing.value}")

    # 5. 提交到中心大脑
    result = await brain.submit_task(task)

    print(f"\n✓ 任务执行完成")
    print(f"  - 执行节点: {result.node_id}")
    print(f"  - 执行时间: {result.execution_time_ms:.2f}ms")
    print(f"  - 状态: {result.status.value}")
    print(f"  - 结果: {result.result}")

    return result


async def example_deep_search():
    """
    深度搜索示例：多节点协作
    """
    print("\n" + "=" * 60)
    print("示例2: 深度搜索 - 搜索 + 本地关联")
    print("=" * 60)

    brain = CentralBrain("central_brain_002")
    dispatcher = MatchingDispatcher(brain)

    # 创建匹配上下文
    context = MatchingContext(
        user_id="user_desktop_001",
        matching_type=MatchingType.DEEP_SEARCH,
        source="browser",
        current_content={
            "query": "Python 异步编程",
            "project_context": "src/api/client.py"
        },
        user_profile={"interests": ["Python", "异步", "架构"]}
    )

    # 执行深度搜索
    result = await dispatcher.dispatch(context)

    print(f"\n✓ 深度搜索完成")
    print(f"  - 匹配置信度: {result.confidence:.2%}")
    print(f"  - 推理说明: {result.reasoning}")
    print(f"  - 结果数量: {len(result.items)}")
    print(f"  - 可执行操作: {result.actions}")

    return result


async def example_overseas_heavy_task():
    """
    海外集群示例：重量级任务处理
    """
    print("\n" + "=" * 60)
    print("示例3: 海外集群 - 学术搜索")
    print("=" * 60)

    # 1. 创建海外集群
    overseas = OverseasCluster("overseas_001", region="us-west")

    # 2. 创建任务
    task = TaskRequest(
        task_id="task_overseas_001",
        task_type=TaskType.ACADEMIC_SEARCH,
        user_id="researcher_001",
        intent="搜索 Transformer 架构的最新论文",
        routing=RoutingStrategy.BEST_QUALITY
    )

    # 3. 提交到海外集群
    task_id = await overseas.submit_heavy_task(task)
    print(f"✓ 任务已提交到海外集群")
    print(f"  - 任务ID: {task_id}")
    print(f"  - 集群区域: {overseas.region}")

    # 4. 处理队列
    asyncio.create_task(overseas.process_queue())

    # 等待处理
    await asyncio.sleep(1)

    return task_id


async def example_edge_acceleration():
    """
    边缘加速示例：预测性缓存
    """
    print("\n" + "=" * 60)
    print("示例4: 边缘加速 - 代码补全预测")
    print("=" * 60)

    # 1. 创建边缘节点
    edge = EdgeAccelerator("edge_shanghai", region="cn-east")

    # 2. 模拟用户上下文
    user_context = {
        "time": "morning",
        "location": "office",
        "current_project": "api-service"
    }

    # 3. 预测性预取
    await edge.prefetch_resources("user_001", user_context)
    print(f"✓ 预测性资源预取完成")

    # 4. 处理代码补全请求
    task = TaskRequest(
        task_id="task_edge_001",
        task_type=TaskType.CODE_COMPLETION,
        user_id="user_001",
        intent="asyncio",
        context={"file_path": "src/main.py"}
    )

    result = await edge.handle_code_completion(task)
    print(f"\n✓ 代码补全请求")
    print(f"  - 命中缓存: {result.get('cached', False)}")
    print(f"  - 补全建议: {result.get('completion', 'N/A')}")
    print(f"  - 置信度: {result.get('confidence', 0):.2%}")

    return result


async def example_matching_strategies():
    """
    深度匹配策略示例
    """
    print("\n" + "=" * 60)
    print("示例5: 深度匹配策略 - 智能 IDE + 浏览器")
    print("=" * 60)

    brain = CentralBrain("central_brain_003")
    dispatcher = MatchingDispatcher(brain)

    # 示例1: 智能 IDE
    ide_context = MatchingContext(
        user_id="developer_001",
        matching_type=MatchingType.SMART_IDE,
        source="ide",
        current_content={
            "request_type": "completion",
            "file_path": "src/utils/helpers.py",
            "code": "async def fetch"
        },
        user_profile={"language": "python", "level": "advanced"}
    )

    ide_result = await dispatcher.dispatch(ide_context)
    print(f"\n📝 智能 IDE 补全:")
    print(f"  - 置信度: {ide_result.confidence:.2%}")
    print(f"  - 建议数: {len(ide_result.items)}")

    # 示例2: 智能浏览器
    browser_context = MatchingContext(
        user_id="researcher_002",
        matching_type=MatchingType.SMART_BROWSER,
        source="browser",
        current_content={
            "request_type": "content_extract",
            "url": "https://docs.python.org/3/library/asyncio.html"
        },
        user_profile={"interests": ["Python", "异步编程"]}
    )

    browser_result = await dispatcher.dispatch(browser_context)
    print(f"\n🌐 智能浏览器内容提取:")
    print(f"  - 置信度: {browser_result.confidence:.2%}")
    print(f"  - 提取内容: {browser_result.items[0] if browser_result.items else 'N/A'}")

    return ide_result, browser_result


async def example_network_status():
    """
    网络状态监控示例
    """
    print("\n" + "=" * 60)
    print("示例6: 网络状态监控")
    print("=" * 60)

    brain = CentralBrain("central_brain_004")

    # 注册各种节点
    nodes_config = [
        ("edge_1", NodeRole.EDGE, "cn-east", 10),
        ("edge_2", NodeRole.EDGE, "cn-north", 15),
        ("edge_3", NodeRole.EDGE, "us-west", 80),
        ("overseas_1", NodeRole.OVERSEAS, "us-west", 200),
        ("overseas_2", NodeRole.OVERSEAS, "eu-west", 180),
    ]

    for node_id, role, region, latency in nodes_config:
        brain.register_node(NodeInfo(
            node_id=node_id,
            role=role,
            status=NodeStatus.ONLINE,
            capabilities=["general"],
            latency_ms=latency,
            region=region
        ))

    # 获取网络状态
    status = brain.get_network_status()

    print(f"\n📊 网络状态:")
    print(f"  - 总节点数: {status['total_nodes']}")
    print(f"  - 按角色分布:")
    for role, count in status["by_role"].items():
        print(f"    · {role}: {count}")
    print(f"  - 活跃任务: {status['active_tasks']}")
    print(f"  - 已完成任务: {status['completed_tasks']}")

    return status


async def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("🧠 私有分布式 AI 计算网络 - 完整示例")
    print("=" * 60 + "\n")

    # 运行所有示例
    await example_basic_flow()
    await example_deep_search()
    await example_overseas_heavy_task()
    await example_edge_acceleration()
    await example_matching_strategies()
    await example_network_status()

    print("\n" + "=" * 60)
    print("✅ 所有示例执行完成!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
