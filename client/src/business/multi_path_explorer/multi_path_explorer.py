"""
多路径探索器 - 核心探索引擎

同时探索多个执行路径，智能选择最优方案
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable, Set
from concurrent.futures import ThreadPoolExecutor
import traceback

from .path_models import (
    ExplorationPath,
    ExplorationResult,
    PathNode,
    PathStatus,
    PathType,
    PathGenerator
)
from .path_evaluator import PathEvaluator, AdaptiveEvaluator, EvaluationMetrics


@dataclass
class ExplorerConfig:
    """探索器配置"""
    # 并行配置
    max_parallel_paths: int = 4        # 最大并行路径数
    max_total_paths: int = 8           # 最大总路径数
    
    # 超时配置
    path_timeout: float = 30.0         # 单路径超时（秒）
    total_timeout: float = 120.0        # 总超时（秒）
    
    # 评估配置
    auto_evaluate: bool = True          # 自动评估
    evaluation_interval: float = 1.0   # 评估间隔（秒）
    
    # 路径生成配置
    enable_creative_paths: bool = True  # 启用创意路径
    paths_per_type: int = 2             # 每种类型路径数
    
    # 早停配置
    early_stopping: bool = True         # 启用早停
    early_stop_threshold: float = 0.95  # 早停阈值
    early_stop_attempts: int = 2        # 连续多少次达到阈值后停止
    
    # 合并配置
    enable_path_merging: bool = True    # 启用路径合并
    merge_threshold: float = 0.8        # 合并相似度阈值
    
    # 回调配置
    progress_callback: Optional[Callable] = None
    status_callback: Optional[Callable] = None
    
    def __post_init__(self):
        # 验证配置
        if self.max_parallel_paths > self.max_total_paths:
            self.max_parallel_paths = self.max_total_paths


@dataclass
class ExecutionNode:
    """可执行的节点配置"""
    node_id: str
    action: str
    params: Dict[str, Any]
    dependencies: Set[str] = field(default_factory=set)  # 依赖的节点ID
    timeout: float = 10.0
    retry_on_failure: bool = True
    max_retries: int = 2


class MultiPathExplorer:
    """
    多路径探索器
    
    核心功能：
    1. 生成多个探索路径（不同策略）
    2. 并行执行路径探索
    3. 实时评估和早停
    4. 智能路径合并
    5. 最优路径选择
    """
    
    def __init__(
        self,
        config: Optional[ExplorerConfig] = None,
        evaluator: Optional[PathEvaluator] = None
    ):
        self.config = config or ExplorerConfig()
        self.evaluator = evaluator or AdaptiveEvaluator()
        
        # 执行器注册
        self._executors: Dict[str, Callable] = {}
        
        # 路径生成器注册
        self._path_generators: List[PathGenerator] = []
        
        # 当前探索状态
        self._active_paths: Dict[str, ExplorationPath] = {}
        self._completed_paths: List[ExplorationPath] = []
        self._cancelled_paths: Set[str] = set()
        
        # 统计信息
        self._stats = {
            "total_explorations": 0,
            "successful_paths": 0,
            "failed_paths": 0,
            "avg_exploration_time": 0.0,
            "early_stops": 0
        }
        
        # 锁（用于线程安全）
        self._lock = asyncio.Lock()
    
    # ==================== 注册接口 ====================
    
    def register_executor(
        self,
        action: str,
        executor: Callable
    ) -> None:
        """
        注册执行器
        
        Args:
            action: 执行动作名称
            executor: 异步执行函数，签名: async def executor(node: ExecutionNode) -> dict
        """
        self._executors[action] = executor
    
    def register_path_generator(self, generator: PathGenerator) -> None:
        """注册路径生成器"""
        self._path_generators.append(generator)
    
    def set_default_generators(self) -> None:
        """设置默认路径生成器"""
        self._path_generators = [
            PathGenerator(
                generator_id="default",
                name="默认生成器",
                description="生成标准探索路径",
                path_types=[PathType.DEFAULT, PathType.OPTIMISTIC, PathType.CONSERVATIVE],
                paths_per_type=self.config.paths_per_type,
                enable_creative=self.config.enable_creative_paths
            )
        ]
    
    # ==================== 核心探索 ====================
    
    async def explore(
        self,
        task: str,
        initial_nodes: List[ExecutionNode],
        context: Optional[Dict[str, Any]] = None
    ) -> ExplorationResult:
        """
        执行多路径探索
        
        Args:
            task: 任务描述
            initial_nodes: 初始执行节点
            context: 额外上下文
            
        Returns:
            探索结果
        """
        start_time = datetime.now()
        context = context or {}
        
        # 1. 生成探索路径
        paths = await self._generate_paths(task, initial_nodes, context)
        
        # 2. 并行探索
        await self._explore_paths_parallel(paths, context)
        
        # 3. 评估和选择最优
        best_path = await self._select_best_path(paths)
        
        # 4. 合并结果（如果启用）
        merged_result = None
        if self.config.enable_path_merging and best_path:
            merged_result = await self._merge_similar_paths(paths, best_path)
        
        # 5. 构建结果
        end_time = datetime.now()
        exploration_time = (end_time - start_time).total_seconds()
        
        result = ExplorationResult(
            task=task,
            paths=paths,
            best_path=best_path,
            merged_result=merged_result,
            exploration_time=exploration_time
        )
        
        # 更新统计
        self._update_stats(result)
        
        return result
    
    async def _generate_paths(
        self,
        task: str,
        nodes: List[ExecutionNode],
        context: Dict[str, Any]
    ) -> List[ExplorationPath]:
        """生成探索路径"""
        paths = []
        
        # 使用注册的生成器或默认生成器
        if not self._path_generators:
            self.set_default_generators()
        
        for generator in self._path_generators:
            for path_type in generator.path_types:
                if not generator.should_generate(path_type):
                    continue
                
                for i in range(generator.paths_per_type):
                    if len(paths) >= self.config.max_total_paths:
                        break
                    
                    path = self._create_path(
                        task=task,
                        path_type=path_type,
                        nodes=nodes,
                        name_suffix=f"{generator.name}_{i+1}"
                    )
                    paths.append(path)
        
        return paths
    
    def _create_path(
        self,
        task: str,
        path_type: PathType,
        nodes: List[ExecutionNode],
        name_suffix: str = ""
    ) -> ExplorationPath:
        """创建单条探索路径"""
        path_id = f"path_{uuid.uuid4().hex[:8]}"
        
        # 路径名称
        type_names = {
            PathType.DEFAULT: "默认",
            PathType.OPTIMISTIC: "快速",
            PathType.CONSERVATIVE: "保守",
            PathType.CREATIVE: "创意",
            PathType.FALLBACK: "备用"
        }
        
        path = ExplorationPath(
            path_id=path_id,
            path_type=path_type,
            name=f"{type_names.get(path_type, '默认')}路径-{name_suffix}",
            description=f"探索路径类型: {path_type.value}",
            metadata={
                "original_task": task,
                "path_type": path_type.value
            }
        )
        
        # 添加初始节点
        for node_config in nodes:
            node = PathNode(
                node_id=node_config.node_id,
                name=node_config.node_id,
                action=node_config.action,
                params=node_config.params,
                metadata={"dependencies": list(node_config.dependencies)}
            )
            path.add_node(node)
        
        return path
    
    async def _explore_paths_parallel(
        self,
        paths: List[ExplorationPath],
        context: Dict[str, Any]
    ) -> None:
        """并行探索多条路径"""
        # 创建信号量控制并发
        semaphore = asyncio.Semaphore(self.config.max_parallel_paths)
        
        async def explore_with_semaphore(path: ExplorationPath) -> None:
            async with semaphore:
                if path.path_id in self._cancelled_paths:
                    return
                await self._explore_single_path(path, context)
        
        # 并行启动所有路径
        tasks = [explore_with_semaphore(path) for path in paths]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # 标记所有路径为完成
        for path in paths:
            if not path.is_complete:
                path.status = PathStatus.CANCELLED
    
    async def _explore_single_path(
        self,
        path: ExplorationPath,
        context: Dict[str, Any]
    ) -> None:
        """探索单条路径"""
        path.status = PathStatus.RUNNING
        
        try:
            # 根据路径类型调整超时
            timeout = self._get_path_timeout(path)
            
            # 创建超时任务
            async with asyncio.timeout(timeout):
                await self._execute_path_nodes(path, context)
                
                # 标记成功
                path.status = PathStatus.SUCCESS
                path.completed_at = datetime.now()
                
                # 获取结果
                if path.nodes:
                    last_node = list(path.nodes.values())[-1]
                    path.result = last_node.result
                    path.error = last_node.error
                    
        except asyncio.TimeoutError:
            path.status = PathStatus.TIMEOUT
            path.error = f"Path exploration timed out after {timeout}s"
            path.completed_at = datetime.now()
            
        except Exception as e:
            path.status = PathStatus.FAILED
            path.error = f"Path exploration failed: {str(e)}"
            path.completed_at = datetime.now()
            
            # 更新失败节点
            for node in path.nodes.values():
                if node.status == PathStatus.RUNNING:
                    node.status = PathStatus.FAILED
                    node.error = str(e)
        
        # 保存到已完成列表
        self._completed_paths.append(path)
        
        # 早停检查
        if self.config.early_stopping:
            await self._check_early_stop(paths=[path])
    
    async def _execute_path_nodes(
        self,
        path: ExplorationPath,
        context: Dict[str, Any]
    ) -> None:
        """执行路径中的所有节点"""
        # 构建依赖图
        pending_nodes = set(path.nodes.keys())
        completed_nodes: Set[str] = set()
        
        # 迭代执行直到所有节点完成
        while pending_nodes:
            # 找出可执行的节点（依赖都已完成）
            ready_nodes = []
            for node_id in pending_nodes:
                node = path.nodes[node_id]
                deps = node.metadata.get("dependencies", [])
                if all(dep in completed_nodes for dep in deps):
                    ready_nodes.append(node)
            
            if not ready_nodes:
                # 无可执行节点但还有待处理，可能是依赖错误
                for node_id in pending_nodes:
                    node = path.nodes[node_id]
                    node.status = PathStatus.FAILED
                    node.error = "Unmet dependencies"
                break
            
            # 并行执行就绪的节点
            tasks = [self._execute_node(path, node, context) for node in ready_nodes]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 更新完成集合
            for node in ready_nodes:
                pending_nodes.discard(node.node_id)
                if node.is_completed:
                    completed_nodes.add(node.node_id)
            
            # 早停检查
            if self.config.early_stopping:
                await self._check_early_stop(paths=[path])
    
    async def _execute_node(
        self,
        path: ExplorationPath,
        node: PathNode,
        context: Dict[str, Any]
    ) -> None:
        """执行单个节点"""
        node.status = PathStatus.RUNNING
        node.start_time = datetime.now()
        
        try:
            # 查找执行器
            executor = self._executors.get(node.action)
            if not executor:
                raise ValueError(f"No executor registered for action: {node.action}")
            
            # 创建执行节点配置
            exec_node = ExecutionNode(
                node_id=node.node_id,
                action=node.action,
                params=node.params,
                timeout=30.0
            )
            
            # 执行
            if asyncio.iscoroutinefunction(executor):
                result = await executor(exec_node)
            else:
                result = executor(exec_node)
            
            # 成功
            node.status = PathStatus.SUCCESS
            node.result = result
            
        except Exception as e:
            node.status = PathStatus.FAILED
            node.error = f"{type(e).__name__}: {str(e)}"
            
        finally:
            node.end_time = datetime.now()
    
    def _get_path_timeout(self, path: ExplorationPath) -> float:
        """根据路径类型确定超时时间"""
        base_timeout = self.config.path_timeout
        
        # 保守路径给更多时间
        if path.path_type == PathType.CONSERVATIVE:
            return base_timeout * 1.5
        
        # 乐观路径快速失败
        if path.path_type == PathType.OPTIMISTIC:
            return base_timeout * 0.5
        
        # 创意路径可能需要更多尝试
        if path.path_type == PathType.CREATIVE:
            return base_timeout * 1.2
        
        return base_timeout
    
    async def _check_early_stop(self, paths: List[ExplorationPath]) -> bool:
        """检查是否应该早停"""
        if not self.config.early_stopping:
            return False
        
        # 检查是否有足够好的路径
        good_paths = [p for p in paths if p.is_success and p.success_rate >= self.config.early_stop_threshold]
        
        if len(good_paths) >= self.config.early_stop_attempts:
            self._stats["early_stops"] += 1
            
            # 取消其他路径
            for path in paths:
                if path.status == PathStatus.RUNNING:
                    self._cancelled_paths.add(path.path_id)
                    path.status = PathStatus.CANCELLED
            
            return True
        
        return False
    
    async def _select_best_path(
        self,
        paths: List[ExplorationPath]
    ) -> Optional[ExplorationPath]:
        """选择最优路径"""
        if not paths:
            return None
        
        # 只评估完成的路径
        completed = [p for p in paths if p.is_complete]
        if not completed:
            return None
        
        # 排序
        ranked = self.evaluator.rank_paths(completed)
        if not ranked:
            return None
        
        best_path, metrics = ranked[0]
        best_path.score = metrics.overall_score
        best_path.confidence = metrics.success_probability
        
        return best_path
    
    async def _merge_similar_paths(
        self,
        paths: List[ExplorationPath],
        primary: ExplorationPath
    ) -> Optional[Dict[str, Any]]:
        """合并相似路径"""
        if not primary.result:
            return None
        
        # 收集其他成功路径的结果
        similar_results = []
        for path in paths:
            if path != primary and path.is_success and path.result:
                similarity = self._calculate_similarity(primary, path)
                if similarity >= self.config.merge_threshold:
                    similar_results.append((path, similarity))
        
        if not similar_results:
            return primary.result
        
        # 合并结果
        merged = primary.result.copy()
        merged["_merged_from"] = [p.path_id for p, _ in similar_results]
        merged["_merge_count"] = len(similar_results)
        merged["_merged_insights"] = [
            {"path_id": p.path_id, "insight": p.metadata.get("insight", "")}
            for p, _ in similar_results
        ]
        
        return merged
    
    def _calculate_similarity(
        self,
        path1: ExplorationPath,
        path2: ExplorationPath
    ) -> float:
        """计算两条路径的相似度"""
        # 基于节点结构的相似度
        actions1 = set(n.action for n in path1.nodes.values())
        actions2 = set(n.action for n in path2.nodes.values())
        
        if not actions1 or not actions2:
            return 0.0
        
        intersection = len(actions1 & actions2)
        union = len(actions1 | actions2)
        
        return intersection / union if union > 0 else 0.0
    
    def _update_stats(self, result: ExplorationResult) -> None:
        """更新统计信息"""
        self._stats["total_explorations"] += 1
        self._stats["successful_paths"] += result.success_count
        self._stats["failed_paths"] += result.failed_count
        
        if result.exploration_time > 0:
            total = self._stats["total_explorations"]
            current_avg = self._stats["avg_exploration_time"]
            self._stats["avg_exploration_time"] = (
                (current_avg * (total - 1) + result.exploration_time) / total
            )
    
    # ==================== 统计和状态 ====================
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self._stats.copy()
    
    def get_active_paths(self) -> List[ExplorationPath]:
        """获取当前活跃路径"""
        return list(self._active_paths.values())
    
    def get_completed_paths(self) -> List[ExplorationPath]:
        """获取已完成的路径"""
        return self._completed_paths.copy()
    
    def cancel_path(self, path_id: str) -> bool:
        """取消指定路径"""
        if path_id in self._active_paths:
            self._cancelled_paths.add(path_id)
            path = self._active_paths[path_id]
            path.status = PathStatus.CANCELLED
            return True
        return False
    
    def cancel_all(self) -> int:
        """取消所有活跃路径"""
        count = len(self._active_paths)
        for path_id in self._active_paths:
            self._cancelled_paths.add(path_id)
            self._active_paths[path_id].status = PathStatus.CANCELLED
        return count


class StreamingMultiPathExplorer(MultiPathExplorer):
    """
    流式多路径探索器
    
    支持流式输出探索进度
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._progress_queue: Optional[asyncio.Queue] = None
    
    async def explore_streaming(
        self,
        task: str,
        initial_nodes: List[ExecutionNode],
        context: Optional[Dict[str, Any]] = None
    ):
        """
        流式探索
        
        产生以下事件:
        - {"type": "path_started", "path": path}
        - {"type": "node_completed", "path_id": str, "node": node}
        - {"type": "path_completed", "path": path}
        - {"type": "evaluation", "paths": [...], "best": path}
        - {"type": "final", "result": ExplorationResult}
        """
        self._progress_queue = asyncio.Queue()
        
        # 启动探索
        async def exploration_task():
            result = await self.explore(task, initial_nodes, context)
            await self._progress_queue.put({"type": "final", "result": result})
        
        # 启动任务
        exploration = asyncio.create_task(exploration_task())
        
        # 产生进度事件
        while not exploration.done():
            try:
                event = await asyncio.wait_for(
                    self._progress_queue.get(),
                    timeout=0.5
                )
                yield event
            except asyncio.TimeoutError:
                continue
        
        # 获取最终结果
        result = await exploration
        yield {"type": "final", "result": result}
