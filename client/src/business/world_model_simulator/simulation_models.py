"""
世界模型模拟器 - 数据模型

定义模拟环境、状态和转移的核心数据结构
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set, Tuple, Callable
from datetime import datetime
from enum import Enum
import uuid


class EntityType(Enum):
    """实体类型"""
    AGENT = "agent"                    # 智能体
    OBJECT = "object"                  # 物体
    LOCATION = "location"              # 位置
    RESOURCE = "resource"              # 资源
    CONCEPT = "concept"                 # 概念
    EVENT = "event"                    # 事件


class StateType(Enum):
    """状态类型"""
    BOOLEAN = "boolean"               # 布尔状态
    NUMERIC = "numeric"                # 数值状态
    CATEGORICAL = "categorical"       # 分类状态
    RELATIONAL = "relational"          # 关系状态


@dataclass
class Entity:
    """
    世界中的实体
    
    代表模拟世界中的一个对象或概念
    """
    entity_id: str
    name: str
    entity_type: EntityType
    properties: Dict[str, Any] = field(default_factory=dict)
    relationships: Dict[str, Set[str]] = field(default_factory=dict)  # relation -> entity_ids
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_property(self, key: str, default: Any = None) -> Any:
        """获取属性"""
        return self.properties.get(key, default)
    
    def set_property(self, key: str, value: Any) -> None:
        """设置属性"""
        self.properties[key] = value
    
    def has_relationship(self, relation: str, entity_id: str) -> bool:
        """检查关系"""
        return entity_id in self.relationships.get(relation, set())
    
    def add_relationship(self, relation: str, entity_id: str) -> None:
        """添加关系"""
        if relation not in self.relationships:
            self.relationships[relation] = set()
        self.relationships[relation].add(entity_id)
    
    def remove_relationship(self, relation: str, entity_id: str) -> None:
        """移除关系"""
        if relation in self.relationships:
            self.relationships[relation].discard(entity_id)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "name": self.name,
            "type": self.entity_type.value,
            "properties": self.properties,
            "relationships": {k: list(v) for k, v in self.relationships.items()},
            "metadata": self.metadata
        }


@dataclass
class State:
    """
    世界状态
    
    包含所有实体的状态信息
    """
    state_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    # 实体状态: entity_id -> {property: value}
    entity_states: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # 全局状态
    global_state: Dict[str, Any] = field(default_factory=dict)
    
    # 关系状态: (entity1_id, relation, entity2_id) -> bool
    relation_states: Dict[Tuple[str, str, str], bool] = field(default_factory=dict)
    
    # 上下文信息
    context: Dict[str, Any] = field(default_factory=dict)
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_entity_state(self, entity_id: str, key: str = None) -> Any:
        """获取实体状态"""
        if entity_id not in self.entity_states:
            return None
        if key is None:
            return self.entity_states[entity_id]
        return self.entity_states[entity_id].get(key)
    
    def set_entity_state(self, entity_id: str, key: str, value: Any) -> None:
        """设置实体状态"""
        if entity_id not in self.entity_states:
            self.entity_states[entity_id] = {}
        self.entity_states[entity_id][key] = value
    
    def has_relation(self, entity1_id: str, relation: str, entity2_id: str) -> bool:
        """检查关系是否存在"""
        return self.relation_states.get((entity1_id, relation, entity2_id), False)
    
    def set_relation(self, entity1_id: str, relation: str, entity2_id: str, exists: bool = True) -> None:
        """设置关系"""
        self.relation_states[(entity1_id, relation, entity2_id)] = exists
    
    def get_all_entities(self) -> List[str]:
        """获取所有实体ID"""
        return list(self.entity_states.keys())
    
    def clone(self) -> "State":
        """复制状态"""
        return State(
            state_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            entity_states={k: v.copy() for k, v in self.entity_states.items()},
            global_state=self.global_state.copy(),
            relation_states=self.relation_states.copy(),
            context=self.context.copy(),
            metadata=self.metadata.copy()
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "state_id": self.state_id,
            "timestamp": self.timestamp.isoformat(),
            "entity_states": self.entity_states,
            "global_state": self.global_state,
            "relation_states": {
                f"{e1}|{rel}|{e2}": val 
                for (e1, rel, e2), val in self.relation_states.items()
            },
            "context": self.context,
            "metadata": self.metadata
        }


@dataclass
class StateTransition:
    """
    状态转移
    
    定义一个动作如何改变世界状态
    """
    transition_id: str
    action: str
    preconditions: List[Dict[str, Any]] = field(default_factory=dict)  # 前置条件
    effects: List[Dict[str, Any]] = field(default_factory=dict)           # 效果
    probability: float = 1.0                                               # 成功概率
    cost: float = 1.0                                                      # 执行成本
    duration: float = 0.0                                                  # 模拟时间
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def check_preconditions(self, state: State) -> Tuple[bool, List[str]]:
        """
        检查前置条件
        
        Returns:
            (是否满足, 不满足的条件列表)
        """
        unsatisfied = []
        for cond in self.preconditions:
            cond_type = cond.get("type")
            
            if cond_type == "entity_has_property":
                entity_id = cond["entity_id"]
                key = cond["key"]
                expected = cond.get("value")
                actual = state.get_entity_state(entity_id, key)
                if actual != expected:
                    unsatisfied.append(f"{entity_id}.{key}={expected} (actual: {actual})")
            
            elif cond_type == "entity_exists":
                entity_id = cond["entity_id"]
                if entity_id not in state.entity_states:
                    unsatisfied.append(f"entity {entity_id} exists")
            
            elif cond_type == "relation_exists":
                e1 = cond["entity1_id"]
                rel = cond["relation"]
                e2 = cond["entity2_id"]
                if not state.has_relation(e1, rel, e2):
                    unsatisfied.append(f"relation {e1}-{rel}-{e2}")
            
            elif cond_type == "global_state":
                key = cond["key"]
                expected = cond.get("value")
                actual = state.global_state.get(key)
                if actual != expected:
                    unsatisfied.append(f"global.{key}={expected} (actual: {actual})")
        
        return len(unsatisfied) == 0, unsatisfied
    
    def apply(self, state: State, random_factor: float = 1.0) -> State:
        """
        应用转移效果
        
        Args:
            state: 当前状态
            random_factor: 随机因子 (0-1)，用于概率性效果
            
        Returns:
            新状态
        """
        # 检查概率
        if random_factor > self.probability:
            # 效果失败，返回原状态
            return state
        
        new_state = state.clone()
        
        # 应用效果
        for effect in self.effects:
            effect_type = effect.get("type")
            
            if effect_type == "set_entity_property":
                entity_id = effect["entity_id"]
                key = effect["key"]
                value = effect["value"]
                new_state.set_entity_state(entity_id, key, value)
            
            elif effect_type == "delete_entity_property":
                entity_id = effect["entity_id"]
                key = effect["key"]
                if entity_id in new_state.entity_states:
                    new_state.entity_states[entity_id].pop(key, None)
            
            elif effect_type == "add_relation":
                e1 = effect["entity1_id"]
                rel = effect["relation"]
                e2 = effect["entity2_id"]
                new_state.set_relation(e1, rel, e2, True)
            
            elif effect_type == "remove_relation":
                e1 = effect["entity1_id"]
                rel = effect["relation"]
                e2 = effect["entity2_id"]
                new_state.set_relation(e1, rel, e2, False)
            
            elif effect_type == "set_global":
                key = effect["key"]
                value = effect["value"]
                new_state.global_state[key] = value
            
            elif effect_type == "increment":
                entity_id = effect["entity_id"]
                key = effect["key"]
                delta = effect.get("delta", 1)
                current = new_state.get_entity_state(entity_id, key) or 0
                new_state.set_entity_state(entity_id, key, current + delta)
            
            elif effect_type == "decrement":
                entity_id = effect["entity_id"]
                key = effect["key"]
                delta = effect.get("delta", 1)
                current = new_state.get_entity_state(entity_id, key) or 0
                new_state.set_entity_state(entity_id, key, current - delta)
        
        return new_state
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "transition_id": self.transition_id,
            "action": self.action,
            "preconditions": self.preconditions,
            "effects": self.effects,
            "probability": self.probability,
            "cost": self.cost,
            "duration": self.duration,
            "metadata": self.metadata
        }


@dataclass
class SimulationStep:
    """
    模拟步骤
    
    代表模拟中的一个执行步骤
    """
    step_id: str
    action: str
    params: Dict[str, Any] = field(default_factory=dict)
    predicted_state: Optional[State] = None
    actual_state: Optional[State] = None
    predicted_outcome: Optional[Dict[str, Any]] = None
    actual_outcome: Optional[Dict[str, Any]] = None
    probability: float = 1.0
    confidence: float = 1.0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_correct(self) -> bool:
        """预测是否正确"""
        if self.predicted_state is None or self.actual_state is None:
            return False
        return self.predicted_state.state_id == self.actual_state.state_id


@dataclass 
class SimulationTrajectory:
    """
    模拟轨迹
    
    代表一个完整的模拟路径
    """
    trajectory_id: str
    task: str
    initial_state: State
    steps: List[SimulationStep] = field(default_factory=list)
    final_state: Optional[State] = None
    outcome: Optional[Dict[str, Any]] = None
    predicted_outcome: Optional[Dict[str, Any]] = None
    is_valid: bool = True
    error: Optional[str] = None
    score: float = 0.0
    confidence: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_step(self, step: SimulationStep) -> None:
        """添加步骤"""
        self.steps.append(step)
    
    @property
    def length(self) -> int:
        """轨迹长度"""
        return len(self.steps)
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        if not self.steps:
            return 0.0
        correct = sum(1 for s in self.steps if s.is_correct)
        return correct / len(self.steps)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "trajectory_id": self.trajectory_id,
            "task": self.task,
            "initial_state": self.initial_state.to_dict(),
            "steps": [
                {
                    "step_id": s.step_id,
                    "action": s.action,
                    "is_correct": s.is_correct,
                    "confidence": s.confidence
                }
                for s in self.steps
            ],
            "final_state": self.final_state.to_dict() if self.final_state else None,
            "outcome": self.outcome,
            "predicted_outcome": self.predicted_outcome,
            "is_valid": self.is_valid,
            "error": self.error,
            "score": self.score,
            "confidence": self.confidence,
            "success_rate": self.success_rate,
            "length": self.length,
            "metadata": self.metadata
        }


@dataclass
class SimulationResult:
    """
    模拟结果
    
    包含多个模拟轨迹的结果
    """
    task: str
    trajectories: List[SimulationTrajectory] = field(default_factory=list)
    best_trajectory: Optional[SimulationTrajectory] = None
    aggregated_outcome: Optional[Dict[str, Any]] = None
    simulation_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def success(self) -> bool:
        """是否成功"""
        return self.best_trajectory is not None and self.best_trajectory.is_valid
    
    def add_trajectory(self, trajectory: SimulationTrajectory) -> None:
        """添加轨迹"""
        self.trajectories.append(trajectory)
        if trajectory.is_valid:
            if self.best_trajectory is None or trajectory.score > self.best_trajectory.score:
                self.best_trajectory = trajectory
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task": self.task,
            "success": self.success,
            "total_trajectories": len(self.trajectories),
            "best_score": self.best_trajectory.score if self.best_trajectory else 0.0,
            "best_trajectory_id": self.best_trajectory.trajectory_id if self.best_trajectory else None,
            "simulation_time": self.simulation_time,
            "metadata": self.metadata
        }
