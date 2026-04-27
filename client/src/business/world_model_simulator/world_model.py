"""
世界模型模拟器 - 世界模型核心引擎

管理模拟世界的状态、规则和转移函数
"""

import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable, Set, Tuple
from datetime import datetime
import random

from .simulation_models import (
    State,
    StateTransition,
    Entity,
    SimulationStep,
    SimulationTrajectory,
    SimulationResult
)


@dataclass
class WorldModelConfig:
    """世界模型配置"""
    # 模拟参数
    max_depth: int = 10                    # 最大模拟深度
    max_breadth: int = 5                   # 最大分支数
    simulation_timeout: float = 5.0        # 模拟超时（秒）
    
    # 随机性
    enable_randomness: bool = True         # 启用随机性
    random_seed: Optional[int] = None      # 随机种子
    
    # 不确定性
    track_uncertainty: bool = True          # 追踪不确定性
    confidence_threshold: float = 0.7       # 置信度阈值
    
    # 优化
    enable_pruning: bool = True            # 启用剪枝
    prune_threshold: float = 0.3            # 剪枝阈值
    
    def __post_init__(self):
        if self.random_seed is not None:
            random.seed(self.random_seed)


class WorldModel:
    """
    世界模型
    
    管理模拟世界的状态、规则和转移函数
    核心功能：
    1. 维护世界状态
    2. 注册状态转移规则
    3. 预测动作效果
    4. 模拟执行轨迹
    """
    
    def __init__(self, config: Optional[WorldModelConfig] = None):
        self.config = config or WorldModelConfig()
        
        # 实体管理
        self._entities: Dict[str, Entity] = {}
        
        # 状态转移规则: action -> List[StateTransition]
        self._transitions: Dict[str, List[StateTransition]] = {}
        
        # 初始状态
        self._initial_state: Optional[State] = None
        
        # 当前状态
        self._current_state: Optional[State] = None
        
        # 转移函数（用于动态计算）
        self._transition_functions: Dict[str, Callable] = {}
        
        # 预测器（用于预测结果）
        self._predictors: Dict[str, Callable] = {}
        
        # 统计信息
        self._stats = {
            "total_simulations": 0,
            "successful_predictions": 0,
            "failed_predictions": 0,
            "avg_simulation_depth": 0.0
        }
    
    # ==================== 实体管理 ====================
    
    def add_entity(self, entity: Entity) -> None:
        """添加实体"""
        self._entities[entity.entity_id] = entity
        
        # 初始化状态
        if self._current_state:
            self._current_state.entity_states[entity.entity_id] = entity.properties.copy()
    
    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """获取实体"""
        return self._entities.get(entity_id)
    
    def remove_entity(self, entity_id: str) -> None:
        """移除实体"""
        if entity_id in self._entities:
            del self._entities[entity_id]
        if self._current_state and entity_id in self._current_state.entity_states:
            del self._current_state.entity_states[entity_id]
    
    def get_all_entities(self, entity_type: str = None) -> List[Entity]:
        """获取所有实体"""
        if entity_type is None:
            return list(self._entities.values())
        return [e for e in self._entities.values() if e.entity_type.value == entity_type]
    
    # ==================== 状态管理 ====================
    
    def set_initial_state(self, state: State) -> None:
        """设置初始状态"""
        self._initial_state = state.clone()
        self._current_state = state.clone()
        
        # 确保所有实体状态都被初始化
        for entity_id in self._entities:
            if entity_id not in state.entity_states:
                entity = self._entities[entity_id]
                state.entity_states[entity_id] = entity.properties.copy()
    
    def get_current_state(self) -> Optional[State]:
        """获取当前状态"""
        return self._current_state
    
    def reset_state(self) -> None:
        """重置到初始状态"""
        if self._initial_state:
            self._current_state = self._initial_state.clone()
    
    # ==================== 转移规则 ====================
    
    def register_transition(self, transition: StateTransition) -> None:
        """注册状态转移规则"""
        if transition.action not in self._transitions:
            self._transitions[transition.action] = []
        self._transitions[transition.action].append(transition)
    
    def register_transition_function(
        self,
        action: str,
        func: Callable[[State, Dict[str, Any]], State]
    ) -> None:
        """注册动态转移函数"""
        self._transition_functions[action] = func
    
    def get_transitions(self, action: str) -> List[StateTransition]:
        """获取动作的转移规则"""
        return self._transitions.get(action, [])
    
    def has_transition(self, action: str) -> bool:
        """检查是否有动作的转移规则"""
        return action in self._transitions or action in self._transition_functions
    
    # ==================== 预测器 ====================
    
    def register_predictor(
        self,
        action: str,
        predictor: Callable[[State, Dict[str, Any]], Dict[str, Any]]
    ) -> None:
        """注册结果预测器"""
        self._predictors[action] = predictor
    
    def predict_outcome(self, action: str, state: State, params: Dict[str, Any]) -> Dict[str, Any]:
        """预测动作结果"""
        predictor = self._predictors.get(action)
        if predictor:
            return predictor(state, params)
        
        # 默认预测：假设成功
        return {
            "success": True,
            "confidence": 0.5,
            "message": "No predictor registered, assuming success"
        }
    
    # ==================== 状态转移 ====================
    
    def apply_transition(
        self,
        state: State,
        transition: StateTransition,
        params: Dict[str, Any] = None,
        random_factor: float = None
    ) -> Tuple[State, bool, List[str]]:
        """
        应用状态转移
        
        Args:
            state: 当前状态
            transition: 转移规则
            params: 动作参数
            random_factor: 随机因子
            
        Returns:
            (新状态, 是否成功, 不满足条件列表)
        """
        # 检查前置条件
        satisfied, unsatisfied = transition.check_preconditions(state)
        if not satisfied:
            return state, False, unsatisfied
        
        # 应用随机性
        if random_factor is None and self.config.enable_randomness:
            random_factor = random.random()
        elif random_factor is None:
            random_factor = 1.0
        
        # 应用效果
        new_state = transition.apply(state, random_factor)
        
        return new_state, True, []
    
    def predict_next_state(
        self,
        state: State,
        action: str,
        params: Dict[str, Any] = None
    ) -> Optional[State]:
        """
        预测下一个状态
        
        Args:
            state: 当前状态
            action: 动作
            params: 动作参数
            
        Returns:
            预测的状态，如果动作无法执行则返回None
        """
        params = params or {}
        
        # 优先使用转移函数
        if action in self._transition_functions:
            try:
                return self._transition_functions[action](state, params)
            except Exception:
                return None
        
        # 使用注册的转移规则
        transitions = self.get_transitions(action)
        if not transitions:
            return None
        
        # 选择最匹配的转移
        for transition in transitions:
            new_state, success, _ = self.apply_transition(state, transition, params)
            if success:
                return new_state
        
        return None
    
    # ==================== 轨迹模拟 ====================
    
    def simulate_trajectory(
        self,
        task: str,
        actions: List[Tuple[str, Dict[str, Any]]],
        initial_state: Optional[State] = None
    ) -> SimulationTrajectory:
        """
        模拟一条轨迹
        
        Args:
            task: 任务描述
            actions: 动作序列 [(action, params), ...]
            initial_state: 初始状态
            
        Returns:
            模拟轨迹
        """
        trajectory_id = str(uuid.uuid4())[:8]
        initial = initial_state or self._current_state or State(state_id="initial")
        
        trajectory = SimulationTrajectory(
            trajectory_id=trajectory_id,
            task=task,
            initial_state=initial.clone()
        )
        
        current_state = initial.clone()
        all_correct = True
        
        for i, (action, params) in enumerate(actions):
            step_id = f"{trajectory_id}_step_{i}"
            
            # 预测下一个状态
            predicted_state = self.predict_next_state(current_state, action, params)
            predicted_outcome = self.predict_outcome(action, current_state, params)
            
            # 创建步骤
            step = SimulationStep(
                step_id=step_id,
                action=action,
                params=params,
                predicted_state=predicted_state,
                predicted_outcome=predicted_outcome,
                confidence=1.0 if predicted_state else 0.5
            )
            
            trajectory.add_step(step)
            
            # 检查是否能执行
            if predicted_state is None:
                step.error = f"No transition registered for action: {action}"
                all_correct = False
                continue
            
            # 更新状态
            current_state = predicted_state
        
        trajectory.final_state = current_state
        trajectory.predicted_outcome = predicted_outcome
        trajectory.is_valid = all_correct and len([s for s in trajectory.steps if s.error]) == 0
        trajectory.score = trajectory.success_rate
        trajectory.confidence = sum(s.confidence for s in trajectory.steps) / len(trajectory.steps) if trajectory.steps else 0.0
        
        return trajectory
    
    def find_best_trajectory(
        self,
        task: str,
        action_sequences: List[List[Tuple[str, Dict[str, Any]]]],
        initial_state: Optional[State] = None
    ) -> SimulationResult:
        """
        找到最佳轨迹
        
        Args:
            task: 任务描述
            action_sequences: 多个可能的动作序列
            initial_state: 初始状态
            
        Returns:
            模拟结果
        """
        start_time = datetime.now()
        result = SimulationResult(task=task)
        
        for actions in action_sequences:
            trajectory = self.simulate_trajectory(task, actions, initial_state)
            result.add_trajectory(trajectory)
        
        # 计算模拟时间
        end_time = datetime.now()
        result.simulation_time = (end_time - start_time).total_seconds()
        
        # 更新统计
        self._update_stats(result)
        
        return result
    
    # ==================== BFS/DFS 探索 ====================
    
    def explore_with_bfs(
        self,
        task: str,
        available_actions: Callable[[State], List[str]],
        get_action_params: Callable[[State, str], List[Dict[str, Any]]],
        goal_check: Callable[[State], bool],
        initial_state: Optional[State] = None,
        max_depth: int = None,
        max_breadth: int = None
    ) -> SimulationResult:
        """
        BFS探索找到目标状态
        
        Args:
            task: 任务描述
            available_actions: 获取可用动作的函数
            get_action_params: 获取动作参数的函数
            goal_check: 检查是否达到目标的函数
            initial_state: 初始状态
            max_depth: 最大深度
            max_breadth: 最大宽度
            
        Returns:
            模拟结果
        """
        max_depth = max_depth or self.config.max_depth
        max_breadth = max_breadth or self.config.max_breadth
        
        start_time = datetime.now()
        result = SimulationResult(task=task)
        
        initial = initial_state or self._current_state
        if initial is None:
            return result
        
        # BFS队列: (state, trajectory)
        from collections import deque
        queue = deque([(initial.clone(), [])])
        visited = set()
        
        depth = 0
        
        while queue and depth < max_depth:
            level_size = min(len(queue), max_breadth)
            
            for _ in range(level_size):
                if not queue:
                    break
                
                current_state, actions = queue.popleft()
                
                # 序列化状态用于访问检查
                state_key = self._serialize_state(current_state)
                if state_key in visited:
                    continue
                visited.add(state_key)
                
                # 检查目标
                if goal_check(current_state):
                    trajectory = self.simulate_trajectory(task, actions, initial)
                    trajectory.score = 1.0
                    trajectory.confidence = 1.0
                    result.add_trajectory(trajectory)
                    result.simulation_time = (datetime.now() - start_time).total_seconds()
                    return result
                
                # 探索子节点
                available = available_actions(current_state)
                for action in available:
                    params_list = get_action_params(current_state, action)
                    
                    for params in params_list[:max_breadth]:
                        next_state = self.predict_next_state(current_state, action, params)
                        if next_state:
                            queue.append((next_state, actions + [(action, params)]))
            
            depth += 1
        
        # 探索完成但未找到目标
        result.simulation_time = (datetime.now() - start_time).total_seconds()
        
        # 添加探索过的轨迹
        for state_key in visited:
            # 这里可以添加已探索状态的信息
            pass
        
        return result
    
    def _serialize_state(self, state: State) -> str:
        """序列化状态用于访问检查"""
        key_parts = []
        
        # 实体状态
        for entity_id in sorted(state.entity_states.keys()):
            props = state.entity_states[entity_id]
            key_parts.append(f"{entity_id}:{hash(frozenset(props.items()))}")
        
        # 全局状态
        if state.global_state:
            key_parts.append(f"g:{hash(frozenset(state.global_state.items()))}")
        
        return "|".join(key_parts)
    
    def _update_stats(self, result: SimulationResult) -> None:
        """更新统计信息"""
        self._stats["total_simulations"] += 1
        
        if result.best_trajectory:
            self._stats["successful_predictions"] += 1
            self._stats["avg_simulation_depth"] = (
                (self._stats["avg_simulation_depth"] * (self._stats["total_simulations"] - 1) +
                 result.best_trajectory.length) / self._stats["total_simulations"]
            )
        else:
            self._stats["failed_predictions"] += 1
    
    # ==================== 统计 ====================
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self._stats.copy()
    
    def get_config(self) -> WorldModelConfig:
        """获取配置"""
        return self.config
    
    # ==================== 预设规则 ====================
    
    def load_common_rules(self) -> None:
        """加载通用规则"""
        # 添加通用状态转移
        common_transitions = [
            # 设置属性
            StateTransition(
                transition_id="set_property",
                action="set_property",
                effects=[
                    {"type": "set_entity_property", "entity_id": "${entity_id}", "key": "${key}", "value": "${value}"}
                ]
            ),
            # 增加数值
            StateTransition(
                transition_id="increment",
                action="increment",
                effects=[
                    {"type": "increment", "entity_id": "${entity_id}", "key": "${key}", "delta": 1}
                ]
            ),
            # 减少数值
            StateTransition(
                transition_id="decrement",
                action="decrement",
                effects=[
                    {"type": "decrement", "entity_id": "${entity_id}", "key": "${key}", "delta": 1}
                ]
            ),
        ]
        
        for t in common_transitions:
            self.register_transition(t)
    
    def create_task_world(self, task: str, entities: List[Entity], initial_goals: Dict[str, Any]) -> None:
        """
        创建任务世界
        
        Args:
            task: 任务描述
            entities: 初始实体
            initial_goals: 初始目标状态
        """
        # 添加实体
        for entity in entities:
            self.add_entity(entity)
        
        # 创建初始状态
        state = State(state_id="initial")
        for entity in entities:
            state.entity_states[entity.entity_id] = entity.properties.copy()
        
        # 设置全局状态
        state.global_state["task"] = task
        state.global_state["goals"] = initial_goals
        state.global_state["completed"] = False
        
        self.set_initial_state(state)
