"""
Fault Tolerance System - Data Models
强容错分布式任务处理系统 - 数据模型

定义任务、节点、故障、状态等核心数据模型
"""

import uuid
import json
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"           # 等待分配
    ASSIGNED = "assigned"         # 已分配
    RUNNING = "running"           # 执行中
    CHECKPOINTING = "checkpointing"  # 检查点保存中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败
    CANCELLED = "cancelled"       # 已取消
    RETRYING = "retrying"         # 重试中
    MIGRATING = "migrating"       # 迁移中


class TaskType(Enum):
    """任务类型"""
    COMPUTE_INTENSIVE = "compute_intensive"   # 计算密集型
    IO_INTENSIVE = "io_intensive"             # IO密集型
    MEMORY_INTENSIVE = "memory_intensive"     # 内存密集型
    NETWORK_INTENSIVE = "network_intensive"   # 网络密集型
    CRITICAL = "critical"                     # 关键任务
    BATCH = "batch"                           # 批处理任务


class NodeStatus(Enum):
    """节点状态"""
    ACTIVE = "active"             # 活跃
    SUSPECTED = "suspected"       # 可疑(可能故障)
    TEMPORARY_FAILURE = "temporary_failure"  # 临时故障
    PERMANENT_FAILURE = "permanent_failure"  # 永久故障
    OFFLINE = "offline"           # 离线
    RECOVERING = "recovering"     # 恢复中


class NodeRole(Enum):
    """节点角色"""
    COORDINATOR = "coordinator"   # 协调节点
    WORKER = "worker"             # 工作节点
    BACKUP_COORDINATOR = "backup_coordinator"  # 备用协调节点
    RELAY = "relay"               # 中继节点


class FaultType(Enum):
    """故障类型"""
    NETWORK_TEMPORARY = "network_temporary"   # 临时网络故障
    NETWORK_PERMANENT = "network_permanent"  # 永久网络故障
    NODE_TEMPORARY = "node_temporary"         # 节点临时故障
    NODE_PERMANENT = "node_permanent"         # 节点永久故障
    TASK_TIMEOUT = "task_timeout"             # 任务超时
    TASK_ERROR = "task_error"                 # 任务执行错误
    STORAGE_FAILURE = "storage_failure"       # 存储故障
    CONSENSUS_FAILURE = "consensus_failure"   # 一致性协议故障


class RecoveryStrategy(Enum):
    """恢复策略"""
    AUTO_RETRY = "auto_retry"           # 自动重试
    NODE_TRANSFER = "node_transfer"      # 节点转移
    CHECKPOINT_RECOVERY = "checkpoint_recovery"  # 检查点恢复
    DEGRADED_MODE = "degraded_mode"      # 降级模式
    MANUAL_INTERVENTION = "manual_intervention"  # 人工干预


class CheckpointType(Enum):
    """检查点类型"""
    FULL = "full"               # 完整检查点
    INCREMENTAL = "incremental" # 增量检查点
    DIFFERENTIAL = "differential"  # 差异检查点


class ConsensusAlgorithm(Enum):
    """一致性算法"""
    GOSSIP = "gossip"           # Gossip协议
    RAFT = "raft"               # Raft协议
    PAXOS = "paxos"             # Paxos协议
    STRONG_CONSISTENCY = "strong_consistency"  # 强一致性


class ReplicaStrategy(Enum):
    """副本策略"""
    NONE = "none"               # 无副本
    SINGLE = "single"           # 单副本
    DOUBLE = "double"           # 双副本
    TRIPLE = "triple"           # 三副本


@dataclass
class Task:
    """分布式任务"""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_type: TaskType = TaskType.BATCH
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 5
    
    # 任务数据
    payload: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    
    # 分配信息
    assigned_node: Optional[str] = None
    backup_node: Optional[str] = None
    
    # 执行信息
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    retry_count: int = 0
    max_retries: int = 3
    
    # 检查点信息
    checkpoint_id: Optional[str] = None
    last_checkpoint: Optional[datetime] = None
    
    # 错误信息
    error_message: Optional[str] = None
    fault_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # 时间戳
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['task_type'] = self.task_type.value
        data['status'] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Task':
        """从字典创建"""
        if isinstance(data.get('task_type'), str):
            data['task_type'] = TaskType(data['task_type'])
        if isinstance(data.get('status'), str):
            data['status'] = TaskStatus(data['status'])
        return cls(**data)


@dataclass
class Node:
    """分布式节点"""
    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    node_name: str = "worker"
    role: NodeRole = NodeRole.WORKER
    status: NodeStatus = NodeStatus.ACTIVE
    
    # 节点能力
    cpu_cores: int = 4
    memory_gb: int = 8
    storage_gb: int = 100
    network_bandwidth_mbps: int = 100
    
    # 资源使用
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    active_tasks: int = 0
    
    # 网络信息
    host: str = "localhost"
    port: int = 8766
    last_heartbeat: Optional[datetime] = None
    
    # 可靠性指标
    reliability_score: float = 100.0  # 0-100
    total_tasks: int = 0
    failed_tasks: int = 0
    avg_response_time: float = 0.0
    
    # 选举信息
    election_term: int = 0
    is_leader: bool = False
    voted_for: Optional[str] = None
    
    # 元数据
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # 时间戳
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['role'] = self.role.value
        data['status'] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Node':
        """从字典创建"""
        if isinstance(data.get('role'), str):
            data['role'] = NodeRole(data['role'])
        if isinstance(data.get('status'), str):
            data['status'] = NodeStatus(data['status'])
        return cls(**data)
    
    @property
    def health_score(self) -> float:
        """健康评分"""
        score = 100.0
        
        # 资源使用扣分
        score -= self.cpu_usage * 0.3
        score -= self.memory_usage * 0.3
        
        # 可靠性扣分
        if self.total_tasks > 0:
            failure_rate = self.failed_tasks / self.total_tasks
            score -= failure_rate * 30
        
        # 响应时间扣分
        if self.avg_response_time > 5000:  # > 5秒
            score -= 10
        
        return max(0, min(100, score))


@dataclass
class Fault:
    """故障记录"""
    fault_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    fault_type: FaultType = FaultType.NETWORK_TEMPORARY
    severity: str = "low"  # low, medium, high, critical
    
    # 关联信息
    node_id: Optional[str] = None
    task_id: Optional[str] = None
    
    # 故障详情
    description: str = ""
    error_code: Optional[str] = None
    stack_trace: Optional[str] = None
    
    # 影响范围
    affected_tasks: List[str] = field(default_factory=list)
    affected_nodes: List[str] = field(default_factory=list)
    
    # 状态
    is_resolved: bool = False
    resolution: Optional[str] = None
    resolved_at: Optional[datetime] = None
    
    # 时间戳
    detected_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['fault_type'] = self.fault_type.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Fault':
        """从字典创建"""
        if isinstance(data.get('fault_type'), str):
            data['fault_type'] = FaultType(data['fault_type'])
        return cls(**data)


@dataclass
class Checkpoint:
    """检查点"""
    checkpoint_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    checkpoint_type: CheckpointType = CheckpointType.INCREMENTAL
    
    # 关联信息
    task_id: str = ""
    node_id: str = ""
    
    # 检查点数据
    state_data: Dict[str, Any] = field(default_factory=dict)
    state_size: int = 0
    
    # 存储位置
    storage_path: Optional[str] = None
    storage_type: str = "local"  # local, distributed, cloud
    
    # 元信息
    sequence_number: int = 0
    is_valid: bool = True
    parent_checkpoint_id: Optional[str] = None
    
    # 时间戳
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['checkpoint_type'] = self.checkpoint_type.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Checkpoint':
        """从字典创建"""
        if isinstance(data.get('checkpoint_type'), str):
            data['checkpoint_type'] = CheckpointType(data['checkpoint_type'])
        return cls(**data)


@dataclass
class RecoveryRecord:
    """恢复记录"""
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # 故障信息
    fault_id: Optional[str] = None
    fault_type: FaultType = FaultType.TASK_ERROR
    
    # 恢复信息
    strategy: RecoveryStrategy = RecoveryStrategy.AUTO_RETRY
    source_node: Optional[str] = None
    target_node: Optional[str] = None
    
    # 恢复详情
    recovered_task_id: Optional[str] = None
    checkpoint_id: Optional[str] = None
    
    # 结果
    is_success: bool = False
    recovery_time_ms: int = 0
    data_loss: int = 0  # 数据丢失量(字节)
    
    # 详情
    details: Dict[str, Any] = field(default_factory=dict)
    
    # 时间戳
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['fault_type'] = self.fault_type.value
        data['strategy'] = self.strategy.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RecoveryRecord':
        """从字典创建"""
        if isinstance(data.get('fault_type'), str):
            data['fault_type'] = FaultType(data['fault_type'])
        if isinstance(data.get('strategy'), str):
            data['strategy'] = RecoveryStrategy(data['strategy'])
        return cls(**data)


@dataclass
class NetworkPartition:
    """网络分区"""
    partition_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # 分区信息
    primary_nodes: List[str] = field(default_factory=list)  # 多数派
    secondary_nodes: List[str] = field(default_factory=list)  # 少数派
    
    # 状态
    is_active: bool = True
    is_resolved: bool = False
    
    # 时间戳
    detected_at: datetime = field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class SystemMetrics:
    """系统指标"""
    timestamp: datetime = field(default_factory=datetime.now)
    
    # 节点指标
    total_nodes: int = 0
    active_nodes: int = 0
    failed_nodes: int = 0
    
    # 任务指标
    total_tasks: int = 0
    pending_tasks: int = 0
    running_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    
    # 故障指标
    active_faults: int = 0
    resolved_faults: int = 0
    
    # 性能指标
    avg_task_duration_ms: float = 0.0
    task_throughput: float = 0.0  # tasks/second
    recovery_success_rate: float = 0.0
    
    # 资源指标
    total_cpu_usage: float = 0.0
    total_memory_usage: float = 0.0
    network_bandwidth_usage: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class SchedulerConfig:
    """调度器配置"""
    max_parallel_tasks: int = 10
    task_timeout_seconds: int = 300
    heartbeat_interval_seconds: int = 1
    fault_detection_threshold: int = 3  # 连续失败次数
    
    # 调度策略
    enable_preemption: bool = True
    enable_work_stealing: bool = True
    enable_affinity: bool = True
    
    # 检查点配置
    checkpoint_interval_seconds: int = 60
    max_checkpoint_age_seconds: int = 300
    
    # 副本配置
    replica_strategy: ReplicaStrategy = ReplicaStrategy.SINGLE
    min_replicas: int = 1
    
    # 一致性配置
    consensus_algorithm: ConsensusAlgorithm = ConsensusAlgorithm.RAFT
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['replica_strategy'] = self.replica_strategy.value
        data['consensus_algorithm'] = self.consensus_algorithm.value
        return data


@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 3
    base_delay_ms: int = 1000
    max_delay_ms: int = 60000
    backoff_factor: float = 2.0
    jitter: bool = True
    
    # 层级重试
    fast_retries: int = 3      # 毫秒级重试
    transfer_retries: int = 2  # 秒级重试
    degraded_retries: int = 1  # 降级重试
    
    def get_delay(self, attempt: int, layer: str = "fast") -> int:
        """计算延迟时间"""
        if layer == "fast":
            return 0
        
        delay = self.base_delay_ms * (self.backoff_factor ** attempt)
        delay = min(delay, self.max_delay_ms)
        
        if self.jitter:
            import random
            jitter_range = delay * 0.1
            delay += random.uniform(-jitter_range, jitter_range)
        
        return int(delay)
