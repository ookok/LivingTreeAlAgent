"""
世界模型模拟器 - 模拟执行引擎

在执行前模拟任务，预测结果并验证
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable, Tuple
import random

from .simulation_models import (
    State,
    SimulationStep,
    SimulationTrajectory,
    SimulationResult
)
from .world_model import WorldModel, WorldModelConfig
from .predictors import OutcomePredictor, RuleBasedPredictor


@dataclass
class SimulationConfig:
    """模拟配置"""
    # 执行配置
    max_simulations: int = 10              # 最大模拟次数
    max_steps_per_simulation: int = 20    # 每条轨迹最大步数
    simulation_timeout: float = 10.0       # 模拟超时（秒）
    
    # 探索配置
    exploration_strategy: str = "best_first"  # best_first / bfs / dfs / random
    max_parallel_simulations: int = 3      # 最大并行模拟数
    
    # 预测配置
    use_predictor: bool = True             # 使用预测器
    predictor_confidence_threshold: float = 0.6  # 预测器置信度阈值
    
    # 验证配置
    verify_predictions: bool = True        # 验证预测结果
    max_verification_attempts: int = 3     # 最大验证次数
    
    # 优化配置
    enable_caching: bool = True            # 启用结果缓存
    cache_size: int = 100                  # 缓存大小


@dataclass
class ExecutorConfig:
    """执行器配置"""
    action: str
    executor: Callable  # 实际执行函数
    pre_conditions: List[Callable] = field(default_factory=list)
    post_conditions: List[Callable] = field(default_factory=list)
    rollback_fn: Optional[Callable] = None  # 回滚函数


class SimulationEngine:
    """
    模拟执行引擎
    
    在实际执行前进行模拟，验证可行性并预测结果
    核心功能：
    1. 多轨迹模拟
    2. 结果预测
    3. 预测验证
    4. 最优执行路径选择
    """
    
    def __init__(
        self,
        config: Optional[SimulationConfig] = None,
        world_model: Optional[WorldModel] = None
    ):
        self.config = config or SimulationConfig()
        self.world_model = world_model or WorldModel()
        
        # 执行器注册
        self._executors: Dict[str, ExecutorConfig] = {}
        
        # 预测器
        self._predictor = OutcomePredictor()
        self._predictor.set_default_predictor(RuleBasedPredictor().predict)
        
        # 结果缓存
        self._cache: Dict[str, SimulationTrajectory] = {}
        
        # 统计
        self._stats = {
            "total_simulations": 0,
            "cache_hits": 0,
            "successful_simulations": 0,
            "failed_simulations": 0
        }
    
    # ==================== 执行器注册 ====================
    
    def register_executor(
        self,
        action: str,
        executor: Callable,
        pre_conditions: List[Callable] = None,
        post_conditions: List[Callable] = None,
        rollback_fn: Callable = None
    ) -> None:
        """注册执行器"""
        self._executors[action] = ExecutorConfig(
            action=action,
            executor=executor,
            pre_conditions=pre_conditions or [],
            post_conditions=post_conditions or [],
            rollback_fn=rollback_fn
        )
        
        # 注册到世界模型
        self.world_model._transition_functions[action] = self._create_transition_fn(action)
    
    def _create_transition_fn(self, action: str) -> Callable:
        """创建转移函数"""
        def transition_fn(state: State, params: Dict[str, Any]) -> State:
            executor_config = self._executors.get(action)
            if not executor_config:
                return state
            
            new_state = state.clone()
            
            # 应用预期的效果
            # 这里简化处理，实际应该根据动作类型决定效果
            new_state.context["last_action"] = action
            new_state.context["last_params"] = params
            
            return new_state
        
        return transition_fn
    
    def register_predictor(
        self,
        action: str,
        predictor: Callable
    ) -> None:
        """注册动作预测器"""
        self._predictor.register_predictor(action, predictor)
    
    # ==================== 模拟执行 ====================
    
    async def simulate_and_execute(
        self,
        task: str,
        action_sequence: List[Tuple[str, Dict[str, Any]]],
        initial_state: Optional[State] = None,
        verify: bool = True
    ) -> Tuple[SimulationTrajectory, Any]:
        """
        模拟并执行
        
        Args:
            task: 任务描述
            action_sequence: 动作序列
            initial_state: 初始状态
            verify: 是否验证预测
            
        Returns:
            (模拟轨迹, 执行结果)
        """
        # 1. 模拟
        trajectory = await self._simulate_trajectory(task, action_sequence, initial_state)
        
        # 2. 决定是否执行
        if not trajectory.is_valid or trajectory.confidence < self.config.predictor_confidence_threshold:
            return trajectory, None
        
        # 3. 验证（如果启用）
        if verify and self.config.verify_predictions:
            verified = await self._verify_trajectory(trajectory)
            if not verified:
                trajectory.metadata["verified"] = False
                trajectory.score *= 0.5  # 降低分数
        
        # 4. 实际执行
        result = await self._execute_trajectory(trajectory)
        
        return trajectory, result
    
    async def _simulate_trajectory(
        self,
        task: str,
        action_sequence: List[Tuple[str, Dict[str, Any]]],
        initial_state: Optional[State] = None
    ) -> SimulationTrajectory:
        """模拟一条轨迹"""
        # 检查缓存
        cache_key = self._get_cache_key(task, action_sequence)
        if self.config.enable_caching and cache_key in self._cache:
            self._stats["cache_hits"] += 1
            return self._cache[cache_key]
        
        initial = initial_state or self.world_model.get_current_state()
        if initial is None:
            initial = State(state_id="initial")
        
        trajectory = SimulationTrajectory(
            trajectory_id=str(uuid.uuid4())[:8],
            task=task,
            initial_state=initial.clone()
        )
        
        current_state = initial.clone()
        all_correct = True
        
        for i, (action, params) in enumerate(action_sequence):
            if i >= self.config.max_steps_per_simulation:
                break
            
            step_id = f"{trajectory.trajectory_id}_step_{i}"
            
            # 预测下一步
            predicted_state = self.world_model.predict_next_state(current_state, action, params)
            
            # 预测结果
            prediction = self._predictor.predict(action, current_state, params)
            
            step = SimulationStep(
                step_id=step_id,
                action=action,
                params=params,
                predicted_state=predicted_state,
                predicted_outcome=prediction.to_dict(),
                probability=prediction.confidence,
                confidence=prediction.confidence
            )
            
            if predicted_state is None:
                step.error = f"Cannot predict next state for action: {action}"
                all_correct = False
                trajectory.is_valid = False
            else:
                current_state = predicted_state
            
            trajectory.add_step(step)
        
        trajectory.final_state = current_state
        trajectory.predicted_outcome = prediction.to_dict() if prediction else None
        trajectory.is_valid = all_correct
        trajectory.score = trajectory.success_rate * (prediction.confidence if prediction else 0.5)
        trajectory.confidence = prediction.confidence if prediction else 0.5
        
        # 更新统计
        self._stats["total_simulations"] += 1
        if trajectory.is_valid:
            self._stats["successful_simulations"] += 1
        else:
            self._stats["failed_simulations"] += 1
        
        # 缓存
        if self.config.enable_caching:
            self._cache[cache_key] = trajectory
            if len(self._cache) > self.config.cache_size:
                # 简单的LRU清理
                oldest = list(self._cache.keys())[0]
                del self._cache[oldest]
        
        return trajectory
    
    async def _verify_trajectory(self, trajectory: SimulationTrajectory) -> bool:
        """验证轨迹"""
        for step in trajectory.steps:
            # 简单验证：检查实际执行与预测是否一致
            if step.predicted_state and step.actual_state:
                if step.predicted_state.state_id != step.actual_state.state_id:
                    step.metadata["mismatch"] = True
                    return False
        
        return True
    
    async def _execute_trajectory(self, trajectory: SimulationTrajectory) -> Any:
        """执行轨迹"""
        results = []
        
        for step in trajectory.steps:
            executor_config = self._executors.get(step.action)
            if not executor_config:
                results.append({"error": f"No executor for action: {step.action}"})
                continue
            
            try:
                # 执行前检查
                for pre_cond in executor_config.pre_conditions:
                    if not pre_cond():
                        raise Exception("Pre-condition failed")
                
                # 执行
                if asyncio.iscoroutinefunction(executor_config.executor):
                    result = await executor_config.executor(step.params)
                else:
                    result = executor_config.executor(step.params)
                
                # 更新实际状态
                step.actual_outcome = result
                
                # 执行后检查
                for post_cond in executor_config.post_conditions:
                    if not post_cond(result):
                        raise Exception("Post-condition failed")
                
                results.append(result)
                
            except Exception as e:
                step.error = str(e)
                step.actual_outcome = {"error": str(e)}
                
                # 回滚
                if executor_config.rollback_fn:
                    try:
                        executor_config.rollback_fn()
                    except Exception:
                        pass
                
                results.append({"error": str(e)})
                break
        
        return results
    
    # ==================== 多轨迹探索 ====================
    
    async def explore_and_select(
        self,
        task: str,
        action_sequences: List[List[Tuple[str, Dict[str, Any]]]],
        initial_state: Optional[State] = None
    ) -> SimulationResult:
        """
        探索多条轨迹并选择最优
        
        Args:
            task: 任务描述
            action_sequences: 多个动作序列
            initial_state: 初始状态
            
        Returns:
            模拟结果
        """
        start_time = datetime.now()
        result = SimulationResult(task=task)
        
        # 并行模拟
        tasks = [
            self._simulate_trajectory(task, actions, initial_state)
            for actions in action_sequences
        ]
        
        trajectories = await asyncio.gather(*tasks, return_exceptions=True)
        
        for traj in trajectories:
            if isinstance(traj, SimulationTrajectory):
                result.add_trajectory(traj)
            elif isinstance(traj, Exception):
                # 创建失败轨迹
                error_traj = SimulationTrajectory(
                    trajectory_id=str(uuid.uuid4())[:8],
                    task=task,
                    initial_state=initial_state.clone() if initial_state else State(state_id="initial"),
                    is_valid=False,
                    error=str(traj)
                )
                result.add_trajectory(error_traj)
        
        # 计算模拟时间
        result.simulation_time = (datetime.now() - start_time).total_seconds()
        
        return result
    
    def generate_variations(
        self,
        base_action: str,
        base_params: Dict[str, Any],
        num_variations: int = 3
    ) -> List[Dict[str, Any]]:
        """生成动作参数变体"""
        variations = [base_params.copy()]
        
        # 参数组合变体
        for key, value in base_params.items():
            if isinstance(value, list):
                for item in value[:num_variations]:
                    new_params = base_params.copy()
                    new_params[key] = item
                    variations.append(new_params)
        
        # 添加默认值变体
        for key in ["timeout", "retry", "depth"]:
            if key not in base_params:
                for val in [1, 2, 3]:
                    new_params = base_params.copy()
                    new_params[key] = val
                    variations.append(new_params)
        
        return variations[:num_variations]
    
    # ==================== 辅助方法 ====================
    
    def _get_cache_key(self, task: str, actions: List[Tuple[str, Dict[str, Any]]]) -> str:
        """生成缓存键"""
        action_str = "|".join(f"{a}:{sorted(p.items())}" for a, p in actions)
        return f"{task}:{action_str}"
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        stats = self._stats.copy()
        stats["cache_hit_rate"] = (
            stats["cache_hits"] / stats["total_simulations"]
            if stats["total_simulations"] > 0 else 0
        )
        stats["success_rate"] = (
            stats["successful_simulations"] / stats["total_simulations"]
            if stats["total_simulations"] > 0 else 0
        )
        return stats
    
    def clear_cache(self) -> None:
        """清空缓存"""
        self._cache.clear()


class SafeSimulationEngine(SimulationEngine):
    """
    安全模拟引擎
    
    专门用于危险操作的模拟和验证
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 危险操作标记
        self._dangerous_actions: Set[str] = {
            "delete_file",
            "rm",
            "drop_table",
            "kill",
            "shutdown",
            "exec",
            "eval"
        }
        
        # 模拟前必须检查
        self._require_simulation: Set[str] = self._dangerous_actions.copy()
    
    def is_dangerous(self, action: str) -> bool:
        """检查是否危险操作"""
        return action in self._dangerous_actions
    
    def requires_simulation(self, action: str) -> bool:
        """检查是否需要模拟"""
        return action in self._require_simulation
    
    async def safe_execute(
        self,
        action: str,
        params: Dict[str, Any],
        dry_run: bool = True
    ) -> Tuple[bool, str, Any]:
        """
        安全执行
        
        Args:
            action: 动作
            params: 参数
            dry_run: 是否仅模拟
            
        Returns:
            (是否成功, 消息, 结果)
        """
        # 检查是否需要模拟
        if self.requires_simulation(action) and dry_run:
            # 先模拟
            trajectory = await self._simulate_trajectory(
                f"Safety check for {action}",
                [(action, params)]
            )
            
            if not trajectory.is_valid:
                return False, f"Simulation failed: {trajectory.error}", None
            
            if trajectory.confidence < 0.7:
                return False, f"Low confidence: {trajectory.confidence}", None
            
            return True, "Simulation passed, execution required", trajectory
        
        # 直接执行
        return await super()._execute_trajectory(
            SimulationTrajectory(
                trajectory_id="safe_exec",
                task=action,
                initial_state=self.world_model.get_current_state() or State(state_id="initial"),
                steps=[
                    SimulationStep(
                        step_id="safe_step",
                        action=action,
                        params=params
                    )
                ]
            )
        )
