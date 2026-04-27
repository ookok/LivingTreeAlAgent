# -*- coding: utf-8 -*-
"""
可视化仪表盘 - Visual Dashboard
================================

功能：
1. 实时监控面板
2. 进化历史图谱
3. 决策推演视图
4. 手动控制台

Author: Hermes Desktop Team
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 数据模型
# ─────────────────────────────────────────────────────────────────────────────

class PanelType(Enum):
    """面板类型"""
    MONITOR = "monitor"           # 监控面板
    EVOLUTION = "evolution"       # 进化面板
    DECISION = "decision"        # 决策面板
    HISTORY = "history"          # 历史面板
    SETTINGS = "settings"        # 设置面板


@dataclass
class DashboardConfig:
    """仪表盘配置"""
    refresh_interval_ms: int = 2000  # 刷新间隔
    max_history_points: int = 60     # 最大历史数据点
    enable_notifications: bool = True  # 启用通知
    theme: str = "light"              # 主题
    
    # 阈值配置
    cpu_warning_threshold: float = 70.0
    cpu_critical_threshold: float = 90.0
    memory_warning_threshold: float = 70.0
    memory_critical_threshold: float = 90.0
    gpu_memory_warning_threshold: float = 80.0
    gpu_memory_critical_threshold: float = 95.0


@dataclass
class ChartDataPoint:
    """图表数据点"""
    timestamp: datetime
    value: float
    label: str = ""


@dataclass
class EvolutionHistory:
    """进化历史"""
    history_id: str
    timestamp: datetime
    from_model: str
    to_model: str
    status: str  # success, failed, cancelled
    duration_seconds: float
    error_message: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# 可视化仪表盘
# ─────────────────────────────────────────────────────────────────────────────

class EvolutionDashboard:
    """
    可视化仪表盘
    
    功能：
    1. 聚合系统监控数据
    2. 生成实时图表数据
    3. 管理进化历史
    4. 提供面板切换
    """
    
    def __init__(self, config: Optional[DashboardConfig] = None):
        self.config = config or DashboardConfig()
        
        # 数据缓存
        self._monitoring_data: List[Dict[str, Any]] = []
        self._evolution_history: List[EvolutionHistory] = []
        
        # 回调
        self._update_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        
        # 状态
        self._current_panel: PanelType = PanelType.MONITOR
        self._is_visible = False
    
    # ── 数据聚合 ────────────────────────────────────────────────────────────
    
    def update_monitoring_data(self, data: Dict[str, Any]):
        """更新监控数据"""
        self._monitoring_data.append({
            "timestamp": datetime.now(),
            "data": data,
        })
        
        # 保持数据点在限制内
        max_points = self.config.max_history_points
        if len(self._monitoring_data) > max_points:
            self._monitoring_data = self._monitoring_data[-max_points:]
        
        self._notify_update()
    
    def add_evolution_record(self, record: EvolutionHistory):
        """添加进化记录"""
        self._evolution_history.append(record)
        self._notify_update()
    
    # ── 图表数据生成 ────────────────────────────────────────────────────────
    
    def get_cpu_chart_data(self) -> Dict[str, Any]:
        """获取CPU图表数据"""
        points = []
        for entry in self._monitoring_data[-60:]:
            resources = entry["data"].get("resources", {})
            points.append({
                "timestamp": entry["timestamp"].isoformat(),
                "value": resources.get("cpu_percent", 0),
            })
        
        # 计算统计数据
        values = [p["value"] for p in points]
        stats = self._calculate_stats(values)
        
        return {
            "label": "CPU 使用率",
            "unit": "%",
            "current": values[-1] if values else 0,
            "average": stats["average"],
            "max": stats["max"],
            "min": stats["min"],
            "warning_threshold": self.config.cpu_warning_threshold,
            "critical_threshold": self.config.cpu_critical_threshold,
            "points": points,
        }
    
    def get_memory_chart_data(self) -> Dict[str, Any]:
        """获取内存图表数据"""
        points = []
        for entry in self._monitoring_data[-60:]:
            resources = entry["data"].get("resources", {})
            points.append({
                "timestamp": entry["timestamp"].isoformat(),
                "value": resources.get("memory_percent", 0),
            })
        
        values = [p["value"] for p in points]
        stats = self._calculate_stats(values)
        
        return {
            "label": "内存使用率",
            "unit": "%",
            "current": values[-1] if values else 0,
            "average": stats["average"],
            "max": stats["max"],
            "min": stats["min"],
            "warning_threshold": self.config.memory_warning_threshold,
            "critical_threshold": self.config.memory_critical_threshold,
            "points": points,
        }
    
    def get_gpu_chart_data(self) -> Dict[str, Any]:
        """获取GPU图表数据"""
        points = []
        for entry in self._monitoring_data[-60:]:
            gpu = entry["data"].get("gpu", {})
            if gpu.get("available"):
                points.append({
                    "timestamp": entry["timestamp"].isoformat(),
                    "value": gpu.get("memory_percent", 0),
                })
        
        values = [p["value"] for p in points]
        stats = self._calculate_stats(values) if values else {"average": 0, "max": 0, "min": 0}
        
        return {
            "label": "GPU 显存使用率",
            "unit": "%",
            "current": values[-1] if values else 0,
            "average": stats["average"],
            "max": stats["max"],
            "min": stats["min"],
            "warning_threshold": self.config.gpu_memory_warning_threshold,
            "critical_threshold": self.config.gpu_memory_critical_threshold,
            "points": points,
            "gpu_name": self._monitoring_data[-1]["data"].get("gpu", {}).get("name", "N/A") if self._monitoring_data else "N/A",
        }
    
    def get_network_chart_data(self) -> Dict[str, Any]:
        """获取网络图表数据"""
        points = []
        for entry in self._monitoring_data[-60:]:
            network = entry["data"].get("network", {})
            points.append({
                "timestamp": entry["timestamp"].isoformat(),
                "value": network.get("bandwidth_mbps", 0),
            })
        
        values = [p["value"] for p in points]
        stats = self._calculate_stats(values) if values else {"average": 0, "max": 0, "min": 0}
        
        return {
            "label": "网络带宽",
            "unit": "Mbps",
            "current": values[-1] if values else 0,
            "average": stats["average"],
            "max": stats["max"],
            "min": stats["min"],
            "points": points,
            "latency": self._monitoring_data[-1]["data"].get("network", {}).get("latency_ms", 0) if self._monitoring_data else 0,
        }
    
    def _calculate_stats(self, values: List[float]) -> Dict[str, float]:
        """计算统计值"""
        if not values:
            return {"average": 0, "max": 0, "min": 0}
        
        return {
            "average": round(sum(values) / len(values), 1),
            "max": round(max(values), 1),
            "min": round(min(values), 1),
        }
    
    # ── 概览数据 ───────────────────────────────────────────────────────────
    
    def get_overview_data(self) -> Dict[str, Any]:
        """获取概览数据"""
        if not self._monitoring_data:
            return self._get_empty_overview()
        
        latest = self._monitoring_data[-1]["data"]
        resources = latest.get("resources", {})
        gpu = latest.get("gpu", {})
        network = latest.get("network", {})
        disk = latest.get("disk", {})
        
        return {
            "system_status": latest.get("system_status", "unknown"),
            "cpu": {
                "usage": resources.get("cpu_percent", 0),
                "cores": resources.get("cpu_cores", 0),
                "frequency": resources.get("cpu_freq", 0),
            },
            "memory": {
                "total_gb": resources.get("memory_total_gb", 0),
                "used_gb": resources.get("memory_used_gb", 0),
                "percent": resources.get("memory_percent", 0),
                "available_gb": resources.get("memory_available_gb", 0),
            },
            "gpu": {
                "available": gpu.get("available", False),
                "name": gpu.get("name", "N/A"),
                "memory_used_mb": gpu.get("memory_used_mb", 0),
                "memory_total_mb": gpu.get("memory_total_mb", 0),
                "utilization": gpu.get("utilization_percent", 0),
                "temperature": gpu.get("temperature", 0),
            },
            "network": {
                "latency_ms": network.get("latency_ms", 0),
                "bandwidth_mbps": network.get("bandwidth_mbps", 0),
                "connected": network.get("connected", False),
            },
            "disk": {
                "total_gb": disk.get("total_gb", 0),
                "used_gb": disk.get("used_gb", 0),
                "free_gb": disk.get("free_gb", 0),
                "percent": disk.get("percent", 0),
                "model_dir_size_gb": disk.get("model_dir_size_gb", 0),
            },
            "models": latest.get("models", []),
            "current_model": latest.get("current_model", "N/A"),
        }
    
    def _get_empty_overview(self) -> Dict[str, Any]:
        """获取空概览"""
        return {
            "system_status": "unknown",
            "cpu": {"usage": 0, "cores": 0, "frequency": 0},
            "memory": {"total_gb": 0, "used_gb": 0, "percent": 0, "available_gb": 0},
            "gpu": {"available": False, "name": "N/A", "memory_used_mb": 0, "memory_total_mb": 0},
            "network": {"latency_ms": 0, "bandwidth_mbps": 0, "connected": False},
            "disk": {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0},
            "models": [],
            "current_model": "N/A",
        }
    
    # ── 进化历史 ───────────────────────────────────────────────────────────
    
    def get_evolution_history_data(self) -> List[Dict[str, Any]]:
        """获取进化历史数据"""
        return [
            {
                "history_id": h.history_id,
                "timestamp": h.timestamp.isoformat(),
                "from_model": h.from_model,
                "to_model": h.to_model,
                "status": h.status,
                "duration_seconds": h.duration_seconds,
                "error_message": h.error_message,
            }
            for h in self._evolution_history[-20:]  # 最近20条
        ]
    
    def get_success_rate(self) -> float:
        """计算成功率"""
        if not self._evolution_history:
            return 0.0
        
        successful = sum(1 for h in self._evolution_history if h.status == "success")
        return (successful / len(self._evolution_history)) * 100
    
    # ── 完整仪表盘数据 ──────────────────────────────────────────────────────
    
    def get_full_dashboard_data(self) -> Dict[str, Any]:
        """获取完整仪表盘数据"""
        return {
            "overview": self.get_overview_data(),
            "charts": {
                "cpu": self.get_cpu_chart_data(),
                "memory": self.get_memory_chart_data(),
                "gpu": self.get_gpu_chart_data(),
                "network": self.get_network_chart_data(),
            },
            "evolution": {
                "history": self.get_evolution_history_data(),
                "success_rate": self.get_success_rate(),
            },
            "config": {
                "refresh_interval_ms": self.config.refresh_interval_ms,
                "theme": self.config.theme,
            },
            "timestamp": datetime.now().isoformat(),
        }
    
    # ── 面板管理 ───────────────────────────────────────────────────────────
    
    def switch_panel(self, panel_type: PanelType):
        """切换面板"""
        self._current_panel = panel_type
        logger.info(f"切换到面板: {panel_type.value}")
    
    def get_current_panel(self) -> PanelType:
        """获取当前面板"""
        return self._current_panel
    
    def show(self):
        """显示仪表盘"""
        self._is_visible = True
        logger.info("仪表盘已显示")
    
    def hide(self):
        """隐藏仪表盘"""
        self._is_visible = False
        logger.info("仪表盘已隐藏")
    
    def is_visible(self) -> bool:
        """是否可见"""
        return self._is_visible
    
    # ── 回调管理 ───────────────────────────────────────────────────────────
    
    def add_update_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """添加更新回调"""
        self._update_callbacks.append(callback)
    
    def remove_update_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """移除更新回调"""
        if callback in self._update_callbacks:
            self._update_callbacks.remove(callback)
    
    def _notify_update(self):
        """通知更新"""
        data = self.get_full_dashboard_data()
        for callback in self._update_callbacks:
            try:
                callback(data)
            except Exception as e:
                logger.error(f"仪表盘更新回调失败: {e}")
    
    # ── 配置管理 ───────────────────────────────────────────────────────────
    
    def update_config(self, **kwargs):
        """更新配置"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        
        self._notify_update()
    
    def get_config(self) -> DashboardConfig:
        """获取配置"""
        return self.config


# ─────────────────────────────────────────────────────────────────────────────
# 状态机可视化
# ─────────────────────────────────────────────────────────────────────────────

class StateMachineVisualizer:
    """状态机可视化"""
    
    STATES = [
        "IDLE",
        "CHECKING",
        "DOWNLOADING",
        "TESTING",
        "SWITCHING",
        "CLEANUP",
        "COMPLETED",
        "ROLLBACK",
    ]
    
    TRANSITIONS = {
        "IDLE": ["CHECKING"],
        "CHECKING": ["DOWNLOADING", "IDLE", "ROLLBACK"],
        "DOWNLOADING": ["TESTING", "ROLLBACK"],
        "TESTING": ["SWITCHING", "ROLLBACK"],
        "SWITCHING": ["CLEANUP", "ROLLBACK"],
        "CLEANUP": ["COMPLETED"],
        "COMPLETED": ["IDLE"],
        "ROLLBACK": ["IDLE"],
    }
    
    def get_state_diagram_data(self, current_state: str) -> Dict[str, Any]:
        """获取状态图数据"""
        nodes = []
        edges = []
        
        for state in self.STATES:
            is_current = state == current_state
            is_completed = self._is_state_completed(state, current_state)
            is_pending = self._is_state_pending(state, current_state)
            
            # 状态颜色
            if is_current:
                color = "#2196F3"  # 蓝色 - 当前
            elif is_completed:
                color = "#4CAF50"  # 绿色 - 完成
            elif is_pending:
                color = "#9E9E9E"  # 灰色 - 等待
            else:
                color = "#9E9E9E"
            
            nodes.append({
                "id": state,
                "label": state,
                "color": color,
                "is_current": is_current,
                "is_completed": is_completed,
                "is_pending": is_pending,
            })
        
        # 生成边
        for from_state, to_states in self.TRANSITIONS.items():
            for to_state in to_states:
                edges.append({
                    "from": from_state,
                    "to": to_state,
                })
        
        return {
            "nodes": nodes,
            "edges": edges,
            "current_state": current_state,
        }
    
    def _is_state_completed(self, state: str, current: str) -> bool:
        """是否已完成"""
        state_order = self.STATES
        if current not in state_order:
            return False
        
        try:
            current_idx = state_order.index(current)
            state_idx = state_order.index(state)
            return state_idx < current_idx
        except ValueError:
            return False
    
    def _is_state_pending(self, state: str, current: str) -> bool:
        """是否等待中"""
        state_order = self.STATES
        if current not in state_order:
            return True
        
        try:
            current_idx = state_order.index(current)
            state_idx = state_order.index(state)
            return state_idx > current_idx
        except ValueError:
            return True


# ─────────────────────────────────────────────────────────────────────────────
# 单例访问
# ─────────────────────────────────────────────────────────────────────────────

_dashboard: Optional[EvolutionDashboard] = None


def get_evolution_dashboard() -> EvolutionDashboard:
    """获取仪表盘单例"""
    global _dashboard
    if _dashboard is None:
        _dashboard = EvolutionDashboard()
    return _dashboard
