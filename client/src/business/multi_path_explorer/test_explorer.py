"""
多路径探索器测试

测试多路径并行探索的核心功能
"""

import asyncio
import sys
sys.path.insert(0, 'f:/mhzyapp/LivingTreeAlAgent')

from client.src.business.multi_path_explorer import (
    MultiPathExplorer,
    ExplorerConfig,
    PathType,
    ExecutionNode,
    ExplorationPath,
    PathEvaluator
)


async def test_basic_exploration():
    """测试1: 基础探索"""
    print("\n" + "="*50)
    print("测试1: 基础多路径探索")
    print("="*50)
    
    # 创建配置
    config = ExplorerConfig(
        max_parallel_paths=3,
        max_total_paths=6,
        path_timeout=5.0,
        enable_creative_paths=False
    )
    
    # 创建探索器
    explorer = MultiPathExplorer(config)
    
    # 注册执行器
    async def search_executor(node: ExecutionNode):
        await asyncio.sleep(0.1)  # 模拟执行
        query = node.params.get("query", "")
        return {
            "results": [f"结果1 for {query}", f"结果2 for {query}"],
            "count": 2
        }
    
    async def analyze_executor(node: ExecutionNode):
        await asyncio.sleep(0.1)
        return {"analysis": f"分析: {node.params.get('text', '')}"}
    
    explorer.register_executor("search", search_executor)
    explorer.register_executor("analyze", analyze_executor)
    
    # 创建执行节点
    nodes = [
        ExecutionNode(
            node_id="search_step",
            action="search",
            params={"query": "AI最新进展"}
        ),
        ExecutionNode(
            node_id="analyze_step",
            action="analyze",
            params={"text": "AI分析文本"},
            dependencies={"search_step"}
        )
    ]
    
    # 执行探索
    print("开始探索...")
    result = await explorer.explore("搜索并分析AI最新进展", nodes)
    
    # 输出结果
    print(f"\n探索完成!")
    print(f"  总路径数: {result.total_paths}")
    print(f"  成功路径: {result.success_count}")
    print(f"  失败路径: {result.failed_count}")
    print(f"  探索时间: {result.exploration_time:.2f}s")
    
    if result.best_path:
        print(f"\n最优路径:")
        print(f"  ID: {result.best_path.path_id}")
        print(f"  类型: {result.best_path.path_type.value}")
        print(f"  评分: {result.best_path.score:.3f}")
        print(f"  置信度: {result.best_path.confidence:.3f}")
        print(f"  节点数: {result.best_path.node_count}")
        print(f"  结果: {result.best_path.result}")
    
    # 输出所有路径
    print(f"\nAll paths:")
    for i, path in enumerate(result.paths):
        status_icon = "[OK]" if path.is_success else "[X]" if path.is_complete else "[...]"
        print(f"  {status_icon} {path.name}: score={path.score:.3f}, type={path.path_type.value}")
    
    return result.success


async def test_path_types():
    """测试2: 不同路径类型"""
    print("\n" + "="*50)
    print("测试2: 不同路径类型探索")
    print("="*50)
    
    config = ExplorerConfig(
        max_parallel_paths=2,
        max_total_paths=5,
        path_timeout=3.0
    )
    
    explorer = MultiPathExplorer(config)
    
    # 注册执行器
    async def fast_executor(node):
        await asyncio.sleep(0.05)
        return {"method": "fast", "result": "快速结果"}
    
    async def thorough_executor(node):
        await asyncio.sleep(0.2)
        return {"method": "thorough", "result": "详细结果"}
    
    async def creative_executor(node):
        await asyncio.sleep(0.1)
        return {"method": "creative", "result": "创意结果"}
    
    explorer.register_executor("fast", fast_executor)
    explorer.register_executor("thorough", thorough_executor)
    explorer.register_executor("creative", creative_executor)
    
    # 创建不同类型的节点
    nodes = [
        ExecutionNode(node_id="fast", action="fast", params={}),
        ExecutionNode(node_id="thorough", action="thorough", params={}),
        ExecutionNode(node_id="creative", action="creative", params={})
    ]
    
    result = await explorer.explore("测试不同执行策略", nodes)
    
    print(f"\n探索完成!")
    print(f"  总路径数: {result.total_paths}")
    
    # 按类型分组
    for path_type in PathType:
        type_paths = result.get_path_by_type(path_type)
        if type_paths:
            print(f"\n{path_type.value}路径 ({len(type_paths)}):")
            for p in type_paths:
                print(f"  - {p.name}: score={p.score:.3f}")
    
    return True


async def test_evaluator():
    """测试3: 路径评估器"""
    print("\n" + "="*50)
    print("测试3: 路径评估器")
    print("="*50)
    
    evaluator = PathEvaluator()
    
    # 创建测试路径
    from client.src.business.multi_path_explorer import PathNode, PathStatus
    
    path = ExplorationPath(
        path_id="test_path",
        path_type=PathType.DEFAULT,
        name="测试路径"
    )
    
    # 添加节点
    for i in range(3):
        node = PathNode(
            node_id=f"node_{i}",
            name=f"节点{i}",
            action="test",
            status=PathStatus.SUCCESS,
            result={"score": 100 - i * 10}
        )
        from datetime import datetime
        node.start_time = datetime.now()
        node.end_time = datetime.now()
        path.add_node(node)
    
    path.status = PathStatus.SUCCESS
    path.result = {"final": "测试结果"}
    path.score = 0.8
    path.confidence = 0.9
    
    # 评估
    metrics = evaluator.evaluate(path)
    
    print(f"\n评估结果:")
    print(f"  综合评分: {metrics.overall_score:.3f}")
    print(f"  质量分数: {metrics.quality_score:.3f}")
    print(f"  效率分数: {metrics.efficiency_score:.3f}")
    print(f"  可靠性: {metrics.reliability_score:.3f}")
    print(f"  成本效益: {metrics.cost_score:.3f}")
    print(f"  新颖性: {metrics.novelty_score:.3f}")
    
    print(f"\n建议:")
    for rec in metrics.recommendations:
        print(f"  - {rec}")
    
    return True


async def test_adaptive_evaluator():
    """测试4: 自适应评估器"""
    print("\n" + "="*50)
    print("测试4: 自适应评估器")
    print("="*50)
    
    from client.src.business.multi_path_explorer import AdaptiveEvaluator
    
    evaluator = AdaptiveEvaluator()
    
    # 测试不同上下文
    contexts = ["speed_critical", "reliability_critical", "cost_critical", "innovation_focused"]
    
    for ctx in contexts:
        evaluator.set_context(ctx)
        weights = evaluator.weights
        print(f"\n{ctx}:")
        print(f"  质量: {weights['quality']:.2f}")
        print(f"  效率: {weights['efficiency']:.2f}")
        print(f"  可靠性: {weights['reliability']:.2f}")
        print(f"  成本: {weights['cost']:.2f}")
        print(f"  创新: {weights['novelty']:.2f}")
    
    return True


async def test_path_merger():
    """测试5: 路径合并"""
    print("\n" + "="*50)
    print("测试5: 路径合并")
    print("="*50)
    
    from client.src.business.multi_path_explorer import (
        PathMergerFactory,
        MergeStrategy,
        MergeConfig,
        PathStatus
    )
    
    # 创建测试路径
    paths = []
    for i in range(3):
        path = ExplorationPath(
            path_id=f"path_{i}",
            path_type=PathType.DEFAULT,
            name=f"路径{i}",
            status=PathStatus.SUCCESS,
            score=0.7 + i * 0.1,
            confidence=0.8 + i * 0.05,
            result={
                "answer": f"答案{i}",
                "confidence_score": 0.8 + i * 0.05,
                "method": "standard"
            }
        )
        paths.append(path)
    
    # 测试不同的合并策略
    strategies = [
        (MergeStrategy.BEST_ONLY, "最佳路径"),
        (MergeStrategy.WEIGHTED_AVERAGE, "加权平均"),
        (MergeStrategy.ENSEMBLE, "集成")
    ]
    
    for strategy, name in strategies:
        config = MergeConfig(strategy=strategy)
        merger = PathMergerFactory.create(strategy, config)
        merged = merger.merge(paths, paths[0])
        
        print(f"\n{name}策略:")
        print(f"  类型: {merged.get('_meta', {}).get('merge_type', 'N/A')}")
        if "result" in merged:
            print(f"  结果: {merged['result']}")
    
    return True


async def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("[MULTI-PATH EXPLORER TEST SUITE]")
    print("="*60)
    
    tests = [
        ("基础探索", test_basic_exploration),
        ("路径类型", test_path_types),
        ("评估器", test_evaluator),
        ("自适应评估", test_adaptive_evaluator),
        ("路径合并", test_path_merger)
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = await test_func()
            results.append((name, success))
            print(f"\n[PASS] {name}")
        except Exception as e:
            results.append((name, False))
            print(f"\n[FAIL] {name}: {e}")
            import traceback
            traceback.print_exc()
    
    # 总结
    print("\n" + "="*60)
    print("[TEST SUMMARY]")
    print("="*60)
    passed = sum(1 for _, s in results if s)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    for name, success in results:
        status = "[OK]" if success else "[FAIL]"
        print(f"  {status} {name}")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
