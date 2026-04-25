#!/usr/bin/env python3
"""
代理编排可视化 - AgentOrchestrationViewer
Phase 2 核心：可视化多代理工作流执行过程

Author: LivingTreeAI Team
Version: 1.0.0
"""

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import threading


class NodeStatus(Enum):
    """节点状态"""
    PENDING = "pending"      # 待执行
    RUNNING = "running"     # 执行中
    SUCCESS = "success"     # 成功
    FAILED = "failed"       # 失败
    SKIPPED = "skipped"     # 跳过


class EdgeStyle(Enum):
    """边样式"""
    NORMAL = "normal"       # 正常
    HIGHLIGHT = "highlight" # 高亮
    DISABLED = "disabled"   # 禁用


@dataclass
class OrchestrationNode:
    """编排节点"""
    id: str
    name: str
    agent_type: str
    status: NodeStatus = NodeStatus.PENDING
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error: Optional[str] = None
    
    @property
    def duration(self) -> Optional[float]:
        """执行时长"""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None
    
    @property
    def is_complete(self) -> bool:
        """是否完成"""
        return self.status in (NodeStatus.SUCCESS, NodeStatus.FAILED, NodeStatus.SKIPPED)


@dataclass
class OrchestrationEdge:
    """编排边"""
    id: str
    source: str
    target: str
    style: EdgeStyle = EdgeStyle.NORMAL
    label: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrchestrationSnapshot:
    """编排快照"""
    timestamp: float
    nodes: Dict[str, OrchestrationNode]
    edges: Dict[str, OrchestrationEdge]
    active_node_id: Optional[str] = None
    message: str = ""


class AgentOrchestrationViewer:
    """
    代理编排可视化器
    
    核心功能：
    - 实时状态跟踪
    - 执行历史记录
    - 快照保存
    - 统计信息
    - 导出可视化数据
    """
    
    def __init__(self, max_snapshots: int = 100):
        """
        初始化可视化器
        
        Args:
            max_snapshots: 最大快照数
        """
        self._nodes: Dict[str, OrchestrationNode] = {}
        self._edges: Dict[str, OrchestrationEdge] = {}
        self._snapshots: List[OrchestrationSnapshot] = []
        self._max_snapshots = max_snapshots
        self._lock = threading.RLock()
        self._start_time: Optional[float] = None
        self._current_workflow_id: Optional[str] = None
        self._event_log: List[Dict[str, Any]] = []
    
    def initialize_workflow(self, workflow_id: str) -> None:
        """
        初始化工作流
        
        Args:
            workflow_id: 工作流ID
        """
        with self._lock:
            self._nodes.clear()
            self._edges.clear()
            self._snapshots.clear()
            self._event_log.clear()
            self._start_time = time.time()
            self._current_workflow_id = workflow_id
    
    def add_node(
        self,
        node_id: str,
        name: str,
        agent_type: str,
        inputs: Optional[List[str]] = None,
        outputs: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        添加节点
        
        Args:
            node_id: 节点ID
            name: 节点名称
            agent_type: 代理类型
            inputs: 输入列表
            outputs: 输出列表
            metadata: 元数据
        """
        with self._lock:
            node = OrchestrationNode(
                id=node_id,
                name=name,
                agent_type=agent_type,
                inputs=inputs or [],
                outputs=outputs or [],
                metadata=metadata or {},
            )
            self._nodes[node_id] = node
            self._log_event("node_added", {"node_id": node_id, "name": name})
    
    def add_edge(
        self,
        source: str,
        target: str,
        label: Optional[str] = None,
        edge_id: Optional[str] = None,
    ) -> None:
        """
        添加边
        
        Args:
            source: 源节点ID
            target: 目标节点ID
            label: 边标签
            edge_id: 边ID
        """
        with self._lock:
            if edge_id is None:
                edge_id = f"{source}->{target}"
            
            edge = OrchestrationEdge(
                id=edge_id,
                source=source,
                target=target,
                label=label,
            )
            self._edges[edge_id] = edge
            self._log_event("edge_added", {"source": source, "target": target})
    
    def update_node_status(
        self,
        node_id: str,
        status: NodeStatus,
        error: Optional[str] = None,
    ) -> None:
        """
        更新节点状态
        
        Args:
            node_id: 节点ID
            status: 新状态
            error: 错误信息
        """
        with self._lock:
            node = self._nodes.get(node_id)
            if node is None:
                return
            
            node.status = status
            
            if status == NodeStatus.RUNNING:
                node.started_at = time.time()
            elif node.is_complete:
                node.completed_at = time.time()
            
            if error:
                node.error = error
            
            self._log_event(
                "node_status_changed",
                {"node_id": node_id, "status": status.value, "error": error}
            )
    
    def highlight_edge(self, edge_id: str, highlight: bool = True) -> None:
        """
        高亮边
        
        Args:
            edge_id: 边ID
            highlight: 是否高亮
        """
        with self._lock:
            edge = self._edges.get(edge_id)
            if edge:
                edge.style = EdgeStyle.HIGHLIGHT if highlight else EdgeStyle.NORMAL
    
    def save_snapshot(self, message: str = "") -> None:
        """
        保存快照
        
        Args:
            message: 快照消息
        """
        with self._lock:
            # 找到当前活跃节点
            active_node_id = None
            for node in self._nodes.values():
                if node.status == NodeStatus.RUNNING:
                    active_node_id = node.id
                    break
            
            snapshot = OrchestrationSnapshot(
                timestamp=time.time(),
                nodes={k: v for k, v in self._nodes.items()},
                edges={k: v for k, v in self._edges.items()},
                active_node_id=active_node_id,
                message=message,
            )
            
            self._snapshots.append(snapshot)
            
            # 限制快照数量
            if len(self._snapshots) > self._max_snapshots:
                self._snapshots.pop(0)
            
            self._log_event("snapshot_saved", {"message": message})
    
    def _log_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """记录事件"""
        self._event_log.append({
            "type": event_type,
            "timestamp": time.time(),
            "data": data,
        })
        
        # 限制事件日志大小
        if len(self._event_log) > 1000:
            self._event_log = self._event_log[-500:]
    
    def get_workflow_stats(self) -> Dict[str, Any]:
        """
        获取工作流统计
        
        Returns:
            统计信息
        """
        with self._lock:
            total = len(self._nodes)
            completed = sum(1 for n in self._nodes.values() if n.is_complete)
            running = sum(1 for n in self._nodes.values() if n.status == NodeStatus.RUNNING)
            failed = sum(1 for n in self._nodes.values() if n.status == NodeStatus.FAILED)
            
            # 计算总执行时长
            total_duration = sum(
                n.duration for n in self._nodes.values() if n.duration
            )
            
            elapsed = time.time() - self._start_time if self._start_time else 0
            
            return {
                "workflow_id": self._current_workflow_id,
                "total_nodes": total,
                "completed": completed,
                "running": running,
                "failed": failed,
                "pending": total - completed - running,
                "progress": f"{(completed / total * 100):.1f}%" if total > 0 else "0%",
                "total_duration": f"{total_duration:.2f}s",
                "elapsed": f"{elapsed:.2f}s",
                "snapshots": len(self._snapshots),
                "events": len(self._event_log),
            }
    
    def get_execution_timeline(self) -> List[Dict[str, Any]]:
        """
        获取执行时间线
        
        Returns:
            时间线数据
        """
        with self._lock:
            timeline = []
            
            for node in self._nodes.values():
                timeline.append({
                    "id": node.id,
                    "name": node.name,
                    "agent_type": node.agent_type,
                    "status": node.status.value,
                    "start": node.started_at,
                    "end": node.completed_at,
                    "duration": node.duration,
                    "error": node.error,
                })
            
            return sorted(timeline, key=lambda x: x["start"] or 0)
    
    def get_graph_data(self) -> Dict[str, Any]:
        """
        获取图形数据 (用于可视化)
        
        Returns:
            图形数据
        """
        with self._lock:
            nodes = []
            for node in self._nodes.values():
                nodes.append({
                    "id": node.id,
                    "label": node.name,
                    "type": node.agent_type,
                    "status": node.status.value,
                    "metadata": node.metadata,
                })
            
            edges = []
            for edge in self._edges.values():
                edges.append({
                    "id": edge.id,
                    "source": edge.source,
                    "target": edge.target,
                    "label": edge.label,
                    "style": edge.style.value,
                })
            
            return {
                "nodes": nodes,
                "edges": edges,
                "stats": self.get_workflow_stats(),
            }
    
    def export_json(self) -> str:
        """
        导出JSON格式
        
        Returns:
            JSON字符串
        """
        with self._lock:
            data = {
                "workflow_id": self._current_workflow_id,
                "graph": self.get_graph_data(),
                "timeline": self.get_execution_timeline(),
                "stats": self.get_workflow_stats(),
                "events": self._event_log,
            }
            return json.dumps(data, indent=2, ensure_ascii=False)
    
    def get_diagnostics(self) -> Dict[str, Any]:
        """
        获取诊断信息
        
        Returns:
            诊断信息
        """
        with self._lock:
            failed_nodes = [
                {"id": n.id, "name": n.name, "error": n.error}
                for n in self._nodes.values() if n.status == NodeStatus.FAILED
            ]
            
            bottlenecks = []
            for node in self._nodes.values():
                if node.duration and node.duration > 30:
                    bottlenecks.append({
                        "id": node.id,
                        "name": node.name,
                        "duration": node.duration,
                        "threshold": 30,
                    })
            
            return {
                "failed_nodes": failed_nodes,
                "bottlenecks": bottlenecks,
                "total_failures": len(failed_nodes),
                "total_bottlenecks": len(bottlenecks),
            }
    
    def get_snapshot_at(self, index: int) -> Optional[OrchestrationSnapshot]:
        """获取指定快照"""
        with self._lock:
            if 0 <= index < len(self._snapshots):
                return self._snapshots[index]
            return None
    
    def get_latest_snapshot(self) -> Optional[OrchestrationSnapshot]:
        """获取最新快照"""
        with self._lock:
            return self._snapshots[-1] if self._snapshots else None
    
    def __len__(self) -> int:
        """节点数量"""
        with self._lock:
            return len(self._nodes)


# 全局可视化器实例
_global_viewer: Optional[AgentOrchestrationViewer] = None
_viewer_lock = threading.Lock()


def get_orchestration_viewer() -> AgentOrchestrationViewer:
    """获取全局编排可视化器"""
    global _global_viewer
    
    with _viewer_lock:
        if _global_viewer is None:
            _global_viewer = AgentOrchestrationViewer()
        return _global_viewer
