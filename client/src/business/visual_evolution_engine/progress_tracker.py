# -*- coding: utf-8 -*-
"""
进度追踪器 - Progress Tracker
==============================

功能：
1. 进化进度跟踪
2. 多阶段状态管理
3. 日志记录
4. 实时可视化数据生成

Author: Hermes Desktop Team
"""

import time
import asyncio
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import deque
import logging

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 数据模型
# ─────────────────────────────────────────────────────────────────────────────

class ProgressStage(Enum):
    """进度阶段"""
    IDLE = "idle"
    CHECKING = "checking"
    DOWNLOADING = "downloading"
    TESTING = "testing"
    SWITCHING = "switching"
    CLEANUP = "cleanup"
    ROLLED_BACK = "rolled_back"


class StepStatus(Enum):
    """步骤状态"""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepProgress:
    """步骤进度"""
    step_id: str
    name: str
    description: str = ""
    
    status: StepStatus = StepStatus.PENDING
    progress_percent: float = 0.0
    
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    
    logs: List[str] = field(default_factory=list)
    error: str = ""
    
    # 子步骤进度
    sub_steps: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class EvolutionProgress:
    """进化进度"""
    progress_id: str
    created_at: datetime = field(default_factory=datetime.now)
    
    # 目标模型
    target_model: str = ""
    
    # 当前阶段
    current_stage: ProgressStage = ProgressStage.IDLE
    stage_progress_percent: float = 0.0
    
    # 总体进度
    total_progress_percent: float = 0.0
    
    # 步骤列表
    steps: List[StepProgress] = field(default_factory=list)
    
    # 时间统计
    started_at: Optional[datetime] = None
    estimated_remaining_seconds: float = 0.0
    actual_duration_seconds: float = 0.0
    
    # 状态
    is_running: bool = False
    is_paused: bool = False
    is_cancelled: bool = False
    is_completed: bool = False
    is_failed: bool = False
    
    # 错误
    error_message: str = ""
    
    # 资源占用
    current_cpu_percent: float = 0.0
    current_memory_mb: float = 0.0
    current_network_mbps: float = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# 进度追踪器
# ─────────────────────────────────────────────────────────────────────────────

class ProgressTracker:
    """
    进度追踪器
    
    功能：
    1. 管理进化进度状态
    2. 跟踪各阶段完成情况
    3. 记录详细日志
    4. 生成可视化数据
    5. 估算剩余时间
    """
    
    # 阶段权重（用于计算总体进度）
    STAGE_WEIGHTS = {
        ProgressStage.IDLE: 0,
        ProgressStage.CHECKING: 0.1,
        ProgressStage.DOWNLOADING: 0.5,
        ProgressStage.TESTING: 0.15,
        ProgressStage.SWITCHING: 0.2,
        ProgressStage.CLEANUP: 0.05,
    }
    
    # 步骤定义
    STEPS = [
        {"id": "env_check", "name": "环境检查", "description": "检查系统资源和网络状态"},
        {"id": "download", "name": "下载模型", "description": "下载目标模型文件"},
        {"id": "verify", "name": "验证测试", "description": "验证模型完整性和功能"},
        {"id": "switch", "name": "热切换", "description": "切换到新模型"},
        {"id": "cleanup", "name": "清理归档", "description": "清理旧文件和缓存"},
    ]
    
    def __init__(self):
        self._current_progress: Optional[EvolutionProgress] = None
        self._log_history: deque = deque(maxlen=500)  # 保留最近500条日志
        self._callbacks: List[Callable[[EvolutionProgress], None]] = []
        self._paused = False
    
    # ── 进度管理 ────────────────────────────────────────────────────────────
    
    def start_tracking(self, target_model: str) -> EvolutionProgress:
        """开始追踪"""
        progress_id = f"EV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # 初始化步骤
        steps = [
            StepProgress(
                step_id=s["id"],
                name=s["name"],
                description=s["description"],
            )
            for s in self.STEPS
        ]
        
        self._current_progress = EvolutionProgress(
            progress_id=progress_id,
            target_model=target_model,
            steps=steps,
            is_running=True,
            started_at=datetime.now(),
        )
        
        self._log("开始追踪进化进度")
        self._notify_callbacks()
        
        return self._current_progress
    
    def stop_tracking(self):
        """停止追踪"""
        if self._current_progress:
            self._current_progress.is_running = False
            self._current_progress.is_completed = True
            self._current_progress.actual_duration_seconds = (
                datetime.now() - self._current_progress.started_at
            ).total_seconds()
            
            self._log("进化追踪结束")
            self._notify_callbacks()
    
    def pause(self):
        """暂停"""
        if self._current_progress:
            self._current_progress.is_paused = True
            self._paused = True
            self._log("进度已暂停")
    
    def resume(self):
        """继续"""
        if self._current_progress:
            self._current_progress.is_paused = False
            self._paused = False
            self._log("进度已继续")
    
    def cancel(self):
        """取消"""
        if self._current_progress:
            self._current_progress.is_running = False
            self._current_progress.is_cancelled = True
            self._log("进化已取消")
    
    # ── 阶段更新 ────────────────────────────────────────────────────────────
    
    def update_stage(
        self, 
        stage: ProgressStage, 
        progress_percent: float = 0.0,
        logs: Optional[List[str]] = None
    ):
        """更新当前阶段"""
        if not self._current_progress:
            return
        
        self._current_progress.current_stage = stage
        self._current_progress.stage_progress_percent = progress_percent
        
        # 计算总体进度
        total_progress = self._calculate_total_progress()
        self._current_progress.total_progress_percent = total_progress
        
        # 更新步骤进度
        self._update_step_progress(stage, progress_percent)
        
        # 添加日志
        if logs:
            for log in logs:
                self._log(log)
        
        self._notify_callbacks()
    
    def _update_step_progress(self, stage: ProgressStage, progress_percent: float):
        """更新步骤进度"""
        if not self._current_progress:
            return
        
        # 映射阶段到步骤
        stage_to_step = {
            ProgressStage.CHECKING: "env_check",
            ProgressStage.DOWNLOADING: "download",
            ProgressStage.TESTING: "verify",
            ProgressStage.SWITCHING: "switch",
            ProgressStage.CLEANUP: "cleanup",
        }
        
        step_id = stage_to_step.get(stage)
        if not step_id:
            return
        
        # 更新步骤状态
        for step in self._current_progress.steps:
            if step.step_id == step_id:
                if progress_percent > 0 and step.status == StepStatus.PENDING:
                    step.status = StepStatus.RUNNING
                    step.started_at = datetime.now()
                
                step.progress_percent = progress_percent
                
                if progress_percent >= 100:
                    step.status = StepStatus.PASSED
                    step.completed_at = datetime.now()
                    step.duration_seconds = (
                        step.completed_at - step.started_at
                    ).total_seconds() if step.started_at else 0
                
                break
    
    def _calculate_total_progress(self) -> float:
        """计算总体进度"""
        if not self._current_progress:
            return 0.0
        
        total = 0.0
        
        # 计算当前阶段的贡献
        current_weight = self.STAGE_WEIGHTS.get(
            self._current_progress.current_stage, 0
        )
        total += current_weight * (
            self._current_progress.stage_progress_percent / 100
        )
        
        # 计算已完成阶段的贡献
        completed_weight = 0.0
        for stage, weight in self.STAGE_WEIGHTS.items():
            if stage.value < self._current_progress.current_stage.value:
                completed_weight += weight
        
        total += completed_weight
        
        return min(100.0, total * 100)
    
    # ── 日志记录 ────────────────────────────────────────────────────────────
    
    def log(self, message: str, level: str = "info"):
        """记录日志"""
        self._log(message, level)
        self._notify_callbacks()
    
    def _log(self, message: str, level: str = "info"):
        """内部日志记录"""
        timestamp = datetime.now()
        log_entry = {
            "timestamp": timestamp,
            "level": level,
            "message": message,
        }
        
        self._log_history.append(log_entry)
        
        if self._current_progress:
            # 找到当前步骤并记录
            for step in reversed(self._current_progress.steps):
                if step.status == StepStatus.RUNNING:
                    step.logs.append(f"[{timestamp.strftime('%H:%M:%S')}] {message}")
                    break
        
        logger.info(f"[ProgressTracker] {message}")
    
    def get_recent_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取最近日志"""
        return list(self._log_history)[-limit:]
    
    # ── 资源监控 ────────────────────────────────────────────────────────────
    
    def update_resources(
        self, 
        cpu_percent: float, 
        memory_mb: float, 
        network_mbps: float
    ):
        """更新资源占用"""
        if self._current_progress:
            self._current_progress.current_cpu_percent = cpu_percent
            self._current_progress.current_memory_mb = memory_mb
            self._current_progress.current_network_mbps = network_mbps
    
    # ── 错误处理 ────────────────────────────────────────────────────────────
    
    def report_error(self, error_message: str):
        """报告错误"""
        if self._current_progress:
            self._current_progress.is_running = False
            self._current_progress.is_failed = True
            self._current_progress.error_message = error_message
            
            # 更新当前步骤状态
            for step in reversed(self._current_progress.steps):
                if step.status == StepStatus.RUNNING:
                    step.status = StepStatus.FAILED
                    step.error = error_message
                    step.completed_at = datetime.now()
                    break
        
        self._log(f"错误: {error_message}", "error")
        self._notify_callbacks()
    
    def start_rollback(self):
        """开始回滚"""
        if self._current_progress:
            self._current_progress.current_stage = ProgressStage.ROLLED_BACK
            self._log("开始回滚...")
            self._notify_callbacks()
    
    # ── 回调管理 ────────────────────────────────────────────────────────────
    
    def add_callback(self, callback: Callable[[EvolutionProgress], None]):
        """添加进度回调"""
        self._callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[EvolutionProgress], None]):
        """移除进度回调"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def _notify_callbacks(self):
        """通知所有回调"""
        if self._current_progress:
            for callback in self._callbacks:
                try:
                    callback(self._current_progress)
                except Exception as e:
                    logger.error(f"回调执行失败: {e}")
    
    # ── 可视化数据生成 ──────────────────────────────────────────────────────
    
    def get_visualization_data(self) -> Dict[str, Any]:
        """获取可视化数据"""
        if not self._current_progress:
            return {"status": "idle"}
        
        p = self._current_progress
        
        # 阶段数据
        stages_data = []
        for stage in ProgressStage:
            if stage == ProgressStage.IDLE:
                continue
            
            is_current = stage == p.current_stage
            is_completed = stage.value < p.current_stage.value
            is_pending = stage.value > p.current_stage.value
            
            stages_data.append({
                "stage": stage.value,
                "label": stage.name.lower().replace("_", " ").title(),
                "is_current": is_current,
                "is_completed": is_completed,
                "is_pending": is_pending,
                "progress": p.stage_progress_percent if is_current else (100 if is_completed else 0),
            })
        
        # 步骤数据
        steps_data = [
            {
                "id": step.step_id,
                "name": step.name,
                "description": step.description,
                "status": step.status.value,
                "progress": step.progress_percent,
                "duration": step.duration_seconds,
                "logs": step.logs[-5:] if step.logs else [],  # 最近5条
            }
            for step in p.steps
        ]
        
        # 时间统计
        elapsed = (
            datetime.now() - p.started_at
        ).total_seconds() if p.started_at else 0
        
        estimated_total = elapsed / (p.total_progress_percent / 100) if p.total_progress_percent > 0 else 0
        remaining = max(0, estimated_total - elapsed)
        
        return {
            "status": {
                "running": p.is_running,
                "paused": p.is_paused,
                "cancelled": p.is_cancelled,
                "completed": p.is_completed,
                "failed": p.is_failed,
            },
            "progress": {
                "total": p.total_progress_percent,
                "stage": p.stage_progress_percent,
            },
            "target_model": p.target_model,
            "stages": stages_data,
            "steps": steps_data,
            "time": {
                "elapsed_seconds": elapsed,
                "remaining_seconds": remaining,
                "estimated_total_seconds": estimated_total,
            },
            "resources": {
                "cpu_percent": p.current_cpu_percent,
                "memory_mb": p.current_memory_mb,
                "network_mbps": p.current_network_mbps,
            },
            "logs": self.get_recent_logs(20),
        }
    
    def get_timeline_data(self) -> List[Dict[str, Any]]:
        """获取时间线数据"""
        timeline = []
        
        if not self._current_progress:
            return timeline
        
        for step in self._current_progress.steps:
            entry = {
                "step_id": step.step_id,
                "name": step.name,
                "status": step.status.value,
            }
            
            if step.started_at:
                entry["started_at"] = step.started_at.isoformat()
            
            if step.completed_at:
                entry["completed_at"] = step.completed_at.isoformat()
            
            if step.duration_seconds:
                entry["duration_seconds"] = step.duration_seconds
            
            timeline.append(entry)
        
        return timeline
    
    # ── 状态访问 ────────────────────────────────────────────────────────────
    
    def get_current_progress(self) -> Optional[EvolutionProgress]:
        """获取当前进度"""
        return self._current_progress
    
    def is_tracking(self) -> bool:
        """是否正在追踪"""
        return self._current_progress is not None and self._current_progress.is_running


# ─────────────────────────────────────────────────────────────────────────────
# 单例访问
# ─────────────────────────────────────────────────────────────────────────────

_progress_tracker: Optional[ProgressTracker] = None


def get_progress_tracker() -> ProgressTracker:
    """获取进度追踪器单例"""
    global _progress_tracker
    if _progress_tracker is None:
        _progress_tracker = ProgressTracker()
    return _progress_tracker
