"""
多路径探索器数据模型

定义路径探索过程中的核心数据结构
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime
from enum import Enum


class PathStatus(Enum):
    """路径状态"""
    PENDING = "pending"           # 待探索
    RUNNING = "running"          # 探索中
    SUCCESS = "success"          # 成功
    FAILED = "failed"            # 失败
    TIMEOUT = "timeout"          # 超时
    CANCELLED = "cancelled"      # 已取消
    MERGED = "merged"            # 已合并到其他路径


class PathType(Enum):
    """路径类型"""
    DEFAULT = "default"          # 默认路径
    OPTIMISTIC = "optimistic"    # 乐观路径（快速但可能不完整）
    CONSERVATIVE = "conservative"  # 保守路径（完整但较慢）
    CREATIVE = "creative"        # 创意路径（尝试新方法）
    FALLBACK = "fallback"        # 备用路径


@dataclass
class PathNode:
    """
    路径节点
    
    代表一个执行路径中的一个节点（步骤）
    """
    node_id: str
    name: str
    action: str
    params: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    status: PathStatus = PathStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    children: List[str] = field(default_factory=list)  # 子节点ID列表
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration(self) -> float:
        """计算执行时长（秒）"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0
    
    @property
    def is_completed(self) -> bool:
        """是否完成"""
        return self.status in [
            PathStatus.SUCCESS,
            PathStatus.FAILED,
            PathStatus.TIMEOUT,
            PathStatus.CANCELLED,
            PathStatus.MERGED
        ]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "action": self.action,
            "params": self.params,
            "result": self.result,
            "error": self.error,
            "status": self.status.value,
            "duration": self.duration,
            "children": self.children,
            "metadata": self.metadata
        }


@dataclass
class ExplorationPath:
    """
    探索路径
    
    代表一条完整的执行路径
    """
    path_id: str
    path_type: PathType
    name: str
    description: str = ""
    root_node_id: Optional[str] = None
    nodes: Dict[str, PathNode] = field(default_factory=dict)
    status: PathStatus = PathStatus.PENDING
    score: float = 0.0
    confidence: float = 0.0  # 置信度
    cost: float = 0.0  # 资源消耗
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_node(self, node: PathNode) -> None:
        """添加节点"""
        self.nodes[node.node_id] = node
        if self.root_node_id is None:
            self.root_node_id = node.node_id
    
    def get_node(self, node_id: str) -> Optional[PathNode]:
        """获取节点"""
        return self.nodes.get(node_id)
    
    def get_ordered_nodes(self) -> List[PathNode]:
        """获取有序节点列表（按创建顺序）"""
        return list(self.nodes.values())
    
    @property
    def is_complete(self) -> bool:
        """是否完成"""
        return self.status in [
            PathStatus.SUCCESS,
            PathStatus.FAILED,
            PathStatus.TIMEOUT,
            PathStatus.CANCELLED,
            PathStatus.MERGED
        ]
    
    @property
    def is_success(self) -> bool:
        """是否成功"""
        return self.status == PathStatus.SUCCESS
    
    @property
    def node_count(self) -> int:
        """节点数量"""
        return len(self.nodes)
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        if not self.nodes:
            return 0.0
        completed = sum(1 for n in self.nodes.values() if n.status == PathStatus.SUCCESS)
        return completed / len(self.nodes)
    
    @property
    def total_duration(self) -> float:
        """总时长"""
        if not self.nodes:
            return 0.0
        return sum(n.duration for n in self.nodes.values())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "path_id": self.path_id,
            "path_type": self.path_type.value,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "score": self.score,
            "confidence": self.confidence,
            "cost": self.cost,
            "node_count": self.node_count,
            "success_rate": self.success_rate,
            "total_duration": self.total_duration,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata,
            "nodes": [n.to_dict() for n in self.get_ordered_nodes()]
        }


@dataclass
class ExplorationResult:
    """
    探索结果
    
    多路径探索的最终结果
    """
    task: str
    paths: List[ExplorationPath] = field(default_factory=list)
    best_path: Optional[ExplorationPath] = None
    merged_result: Optional[Dict[str, Any]] = None
    exploration_time: float = 0.0
    total_paths: int = 0
    success_count: int = 0
    failed_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def success(self) -> bool:
        """是否成功"""
        return self.best_path is not None and self.best_path.is_success
    
    def add_path(self, path: ExplorationPath) -> None:
        """添加路径"""
        self.paths.append(path)
        self.total_paths += 1
        if path.is_success:
            self.success_count += 1
        elif path.is_complete and not path.is_success:
            self.failed_count += 1
    
    def get_best_paths(self, n: int = 3) -> List[ExplorationPath]:
        """获取top N最佳路径"""
        sorted_paths = sorted(
            [p for p in self.paths if p.is_complete],
            key=lambda p: (p.score, p.confidence),
            reverse=True
        )
        return sorted_paths[:n]
    
    def get_path_by_type(self, path_type: PathType) -> List[ExplorationPath]:
        """获取指定类型的路径"""
        return [p for p in self.paths if p.path_type == path_type]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task": self.task,
            "success": self.success,
            "total_paths": self.total_paths,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "exploration_time": self.exploration_time,
            "best_path_id": self.best_path.path_id if self.best_path else None,
            "best_path_score": self.best_path.score if self.best_path else 0.0,
            "paths": [p.to_dict() for p in self.paths],
            "merged_result": self.merged_result,
            "metadata": self.metadata
        }


@dataclass
class PathGenerator:
    """
    路径生成器配置
    
    定义如何生成多个探索路径
    """
    generator_id: str
    name: str
    description: str = ""
    
    # 生成的路径类型
    path_types: List[PathType] = field(default_factory=lambda: [
        PathType.DEFAULT,
        PathType.OPTIMISTIC,
        PathType.CONSERVATIVE
    ])
    
    # 每个类型的数量
    paths_per_type: int = 2
    
    # 是否启用创意路径
    enable_creative: bool = True
    
    # 最大总路径数
    max_paths: int = 8
    
    # 自定义生成函数
    custom_generator: Optional[Callable[[str, PathType], List[Dict[str, Any]]]] = None
    
    def should_generate(self, path_type: PathType) -> bool:
        """判断是否应该生成指定类型的路径"""
        if path_type == PathType.CREATIVE and not self.enable_creative:
            return False
        return path_type in self.path_types
