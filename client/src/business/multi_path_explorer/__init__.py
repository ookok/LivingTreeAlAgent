"""
多路径探索器 (Multi-Path Explorer)

同时探索多个执行路径，智能选择最优方案

核心功能:
1. 多路径生成 - 生成不同策略的探索路径（默认/乐观/保守/创意/备用）
2. 并行执行 - 同时探索多条路径
3. 智能评估 - 多维度评估路径质量
4. 早停机制 - 达到足够好的结果时提前结束
5. 路径合并 - 合并多条路径的结果和见解

快速开始:
```python
from client.src.business.multi_path_explorer import MultiPathExplorer, ExplorerConfig, ExecutionNode

# 创建探索器
explorer = MultiPathExplorer(ExplorerConfig(max_parallel_paths=4))

# 注册执行器
async def search_executor(node):
    return {"results": await search(node.params["query"])}

explorer.register_executor("search", search_executor)

# 创建执行节点
nodes = [
    ExecutionNode(
        node_id="step1",
        action="search",
        params={"query": "AI最新进展"}
    )
]

# 执行探索
result = await explorer.explore("搜索AI最新进展", nodes)

print(f"最优路径: {result.best_path.path_id}")
print(f"评分: {result.best_path.score}")
print(f"结果: {result.best_path.result}")
```

架构:
    MultiPathExplorer
        ├── PathGenerator     (路径生成)
        ├── PathEvaluator     (路径评估)
        └── PathMerger        (路径合并)

Author: LivingTreeAI
Version: 1.0.0
"""

# 核心组件
from .path_models import (
    PathStatus,
    PathType,
    PathNode,
    ExplorationPath,
    ExplorationResult,
    PathGenerator
)

# ExecutionNode 在 multi_path_explorer.py 中定义
from .multi_path_explorer import ExecutionNode

from .path_evaluator import (
    EvaluationMetrics,
    PathEvaluator,
    AdaptiveEvaluator
)

from .multi_path_explorer import (
    ExplorerConfig,
    MultiPathExplorer,
    StreamingMultiPathExplorer
)

from .path_merger import (
    MergeStrategy,
    MergeConfig,
    PathMerger,
    PathMergerFactory,
    SmartMerger,
    BestOnlyMerger,
    WeightedAverageMerger,
    VoteMerger,
    EnsembleMerger,
    SelectiveMerger
)

# 版本信息
__version__ = "1.0.0"
__author__ = "LivingTreeAI"

# 公开的类列表
__all__ = [
    # 数据模型
    "PathStatus",
    "PathType",
    "PathNode",
    "ExplorationPath",
    "ExplorationResult",
    "PathGenerator",
    "ExecutionNode",
    
    # 评估器
    "EvaluationMetrics",
    "PathEvaluator",
    "AdaptiveEvaluator",
    
    # 探索器
    "ExplorerConfig",
    "MultiPathExplorer",
    "StreamingMultiPathExplorer",
    
    # 合并器
    "MergeStrategy",
    "MergeConfig",
    "PathMerger",
    "PathMergerFactory",
    "SmartMerger",
    "BestOnlyMerger",
    "WeightedAverageMerger",
    "VoteMerger",
    "EnsembleMerger",
    "SelectiveMerger",
]
