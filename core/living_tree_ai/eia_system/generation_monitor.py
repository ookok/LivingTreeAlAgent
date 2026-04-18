"""
环评报告生成过程监控器
=====================

管理报告生成的各阶段状态，实时广播进度，支持WebSocket推送。

Author: Hermes Desktop EIA System
"""

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
import threading


class GenerationStage(str, Enum):
    """生成阶段枚举"""
    ANALYSIS = "analysis"           # 分析阶段
    MODELING = "modeling"          # 建模阶段
    WRITING = "writing"             # 写作阶段
    AUDIT = "audit"                # 审计阶段
    EXPORT = "export"               # 导出阶段


class StageStatus(str, Enum):
    """阶段状态"""
    PENDING = "pending"            # 等待中
    RUNNING = "running"            # 运行中
    COMPLETED = "completed"         # 已完成
    FAILED = "failed"              # 失败
    SKIPPED = "skipped"             # 跳过


class StepStatus(str, Enum):
    """步骤状态"""
    PENDING = "pending"            # 等待中
    RUNNING = "running"            # 运行中
    COMPLETED = "completed"         # 已完成
    WARNING = "warning"            # 警告（有条件完成）
    ERROR = "error"                # 错误
    SKIPPED = "skipped"             # 跳过


@dataclass
class GenerationStep:
    """生成步骤"""
    id: str
    name: str                       # 步骤名称
    description: str = ""          # 步骤描述
    status: StepStatus = StepStatus.PENDING
    progress: float = 0.0          # 0.0 - 1.0
    message: str = ""               # 当前消息
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    warning: Optional[str] = None  # 警告信息
    error: Optional[str] = None     # 错误信息
    details: Dict[str, Any] = field(default_factory=dict)  # 额外详情
    children: List['GenerationStep'] = field(default_factory=list)


@dataclass
class StageProgress:
    """阶段进度"""
    stage: GenerationStage
    status: StageStatus
    progress: float                 # 0.0 - 1.0
    message: str
    steps: List[GenerationStep] = field(default_factory=list)
    start_time: Optional[float] = None
    end_time: Optional[float] = None


@dataclass
class GenerationSnapshot:
    """生成过程快照"""
    session_id: str
    project_id: str
    project_name: str
    start_time: float
    update_time: float
    is_running: bool
    stages: Dict[str, StageProgress]
    current_stage: Optional[str] = None
    current_step: Optional[str] = None
    total_progress: float = 0.0


class ProgressBroadcaster:
    """进度广播器 - 支持多种订阅方式"""

    def __init__(self):
        self._websocket_clients: List[Callable] = []
        self._http_callbacks: List[Callable] = []
        self._lock = threading.Lock()

    def subscribe_websocket(self, callback: Callable[[dict], None]):
        """订阅WebSocket推送"""
        with self._lock:
            self._websocket_clients.append(callback)

    def unsubscribe_websocket(self, callback: Callable):
        """取消WebSocket订阅"""
        with self._lock:
            if callback in self._websocket_clients:
                self._websocket_clients.remove(callback)

    def subscribe_http(self, callback: Callable[[dict], None]):
        """订阅HTTP轮询回调"""
        with self._lock:
            self._http_callbacks.append(callback)

    async def broadcast(self, data: dict):
        """广播消息给所有订阅者"""
        with self._lock:
            clients = list(self._websocket_clients)
            callbacks = list(self._http_callbacks)

        # WebSocket推送（异步）
        for client in clients:
            try:
                if asyncio.iscoroutinefunction(client):
                    await client(data)
                else:
                    client(data)
            except Exception as e:
                print(f"WebSocket广播失败: {e}")

        # HTTP回调（同步）
        for callback in callbacks:
            try:
                callback(data)
            except Exception as e:
                print(f"HTTP回调失败: {e}")


class GenerationMonitor:
    """
    报告生成过程监控器

    功能：
    1. 阶段状态管理
    2. 步骤进度追踪
    3. 实时广播进度
    4. 历史记录保存
    """

    def __init__(self, project_id: str = "", project_name: str = ""):
        self.session_id = str(uuid.uuid4())[:8]
        self.project_id = project_id
        self.project_name = project_name
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

        # 阶段定义
        self.stages: Dict[str, StageProgress] = {}
        self._init_stages()

        # 广播器
        self.broadcaster = ProgressBroadcaster()

        # 预览内容
        self._current_preview: Optional[dict] = None

        # 锁
        self._lock = threading.Lock()

    def _init_stages(self):
        """初始化阶段"""
        stage_definitions = [
            (GenerationStage.ANALYSIS, "🔍 分析阶段", [
                ("parse_basic", "解析项目基本信息"),
                ("match_template", "匹配行业模板"),
                ("extract_sources", "提取污染源参数"),
                ("analyze_sensitive", "分析敏感目标"),
                ("check_documents", "检查已有文档"),
            ]),
            (GenerationStage.MODELING, "🧮 建模阶段", [
                ("prepare_inputs", "准备模型输入"),
                ("load_meteo", "加载气象数据"),
                ("setup_parameters", "设置模型参数"),
                ("run_calculation", "运行模型计算"),
                ("collect_results", "收集计算结果"),
            ]),
            (GenerationStage.WRITING, "📄 写作阶段", [
                ("write_chapter1", "第一章 总论"),
                ("write_chapter2", "第二章 工程分析"),
                ("write_chapter3", "第三章 环境现状"),
                ("write_chapter4", "第四章 环境影响预测"),
                ("write_chapter5", "第五章 环境保护措施"),
                ("write_chapter6", "第六章 结论与建议"),
            ]),
            (GenerationStage.AUDIT, "✅ 审计阶段", [
                ("consistency_check", "数据一致性检查"),
                ("completeness_audit", "完整性审计"),
                ("compliance_check", "合规性检查"),
                ("format_review", "格式审查"),
                ("mark_verification", "标记待审核项"),
            ]),
            (GenerationStage.EXPORT, "💾 导出阶段", [
                ("generate_attachments", "生成计算附件"),
                ("digital_signature", "数字签名"),
                ("export_package", "导出验证包"),
                ("archive_report", "归档报告"),
            ]),
        ]

        for stage_enum, stage_name, steps_def in stage_definitions:
            steps = [
                GenerationStep(
                    id=f"{stage_enum.value}_{step_id}",
                    name=step_name,
                    description=""
                )
                for step_id, step_name in steps_def
            ]

            self.stages[stage_enum.value] = StageProgress(
                stage=stage_enum,
                status=StageStatus.PENDING,
                progress=0.0,
                message="等待开始",
                steps=steps
            )

    def get_default_stages_definition(self) -> List[Dict]:
        """获取默认阶段定义（用于前端渲染）"""
        result = []
        for stage_key, stage in self.stages.items():
            result.append({
                "id": stage.stage.value,
                "name": self._get_stage_display_name(stage.stage),
                "status": stage.status.value,
                "progress": stage.progress,
                "message": stage.message,
                "steps": [
                    {
                        "id": s.id,
                        "name": s.name,
                        "status": s.status.value,
                        "progress": s.progress,
                        "message": s.message,
                        "warning": s.warning,
                        "error": s.error
                    }
                    for s in stage.steps
                ]
            })
        return result

    def _get_stage_display_name(self, stage: GenerationStage) -> str:
        """获取阶段显示名称"""
        names = {
            GenerationStage.ANALYSIS: "🔍 分析阶段",
            GenerationStage.MODELING: "🧮 建模阶段",
            GenerationStage.WRITING: "📄 写作阶段",
            GenerationStage.AUDIT: "✅ 审计阶段",
            GenerationStage.EXPORT: "💾 导出阶段"
        }
        return names.get(stage, stage.value)

    async def start_generation(self, project_id: str, project_name: str):
        """开始生成过程"""
        self.project_id = project_id
        self.project_name = project_name
        self.start_time = time.time()
        self.end_time = None

        # 重置所有状态
        for stage in self.stages.values():
            stage.status = StageStatus.PENDING
            stage.progress = 0.0
            stage.message = "等待开始"
            for step in stage.steps:
                step.status = StepStatus.PENDING
                step.progress = 0.0
                step.message = ""

        # 广播开始
        await self._broadcast({
            "type": "generation_started",
            "session_id": self.session_id,
            "project_id": project_id,
            "project_name": project_name,
            "stages": self.get_default_stages_definition(),
            "timestamp": datetime.now().isoformat()
        })

    async def update_stage_status(
        self,
        stage: GenerationStage,
        status: StageStatus,
        message: str = "",
        progress: float = -1
    ):
        """更新阶段状态"""
        with self._lock:
            stage_obj = self.stages.get(stage.value)
            if not stage_obj:
                return

            stage_obj.status = status
            if message:
                stage_obj.message = message

            if status == StageStatus.RUNNING and not stage_obj.start_time:
                stage_obj.start_time = time.time()
            elif status in (StageStatus.COMPLETED, StageStatus.FAILED, StageStatus.SKIPPED):
                stage_obj.end_time = time.time()

            # 计算进度
            if progress >= 0:
                stage_obj.progress = progress
            else:
                # 根据步骤计算进度
                completed = sum(1 for s in stage_obj.steps
                               if s.status == StepStatus.COMPLETED)
                stage_obj.progress = completed / len(stage_obj.steps) if stage_obj.steps else 0

            # 计算总进度
            total_progress = self._calculate_total_progress()

        await self._broadcast({
            "type": "stage_update",
            "session_id": self.session_id,
            "stage": stage.value,
            "stage_name": self._get_stage_display_name(stage),
            "status": status.value,
            "message": message,
            "progress": stage_obj.progress,
            "total_progress": total_progress,
            "timestamp": datetime.now().isoformat()
        })

    async def update_step_status(
        self,
        stage: GenerationStage,
        step_id: str,
        status: StepStatus,
        message: str = "",
        progress: float = -1,
        warning: Optional[str] = None,
        error: Optional[str] = None,
        details: Optional[Dict] = None
    ):
        """更新步骤状态"""
        with self._lock:
            stage_obj = self.stages.get(stage.value)
            if not stage_obj:
                return

            step = next((s for s in stage_obj.steps if s.id == step_id), None)
            if not step:
                return

            step.status = status
            if message:
                step.message = message
            if warning:
                step.warning = warning
            if error:
                step.error = error
            if details:
                step.details.update(details)

            if status == StepStatus.RUNNING and not step.start_time:
                step.start_time = time.time()
            elif status in (StepStatus.COMPLETED, StepStatus.ERROR, StepStatus.SKIPPED):
                step.end_time = time.time()

            # 计算步骤进度
            if progress >= 0:
                step.progress = progress
            else:
                if status == StepStatus.COMPLETED:
                    step.progress = 1.0
                elif status == StepStatus.RUNNING:
                    step.progress = 0.5  # 默认半进度

            # 重新计算阶段进度
            completed = sum(s.progress for s in stage_obj.steps)
            stage_obj.progress = completed / len(stage_obj.steps) if stage_obj.steps else 0

            # 更新阶段状态
            if stage_obj.status != StageStatus.RUNNING:
                stage_obj.status = StageStatus.RUNNING
                stage_obj.start_time = time.time()

            # 广播步骤更新
            total_progress = self._calculate_total_progress()

        await self._broadcast({
            "type": "step_update",
            "session_id": self.session_id,
            "stage": stage.value,
            "stage_name": self._get_stage_display_name(stage),
            "step_id": step_id,
            "step_name": step.name,
            "status": status.value,
            "message": message,
            "warning": warning,
            "error": error,
            "progress": step.progress,
            "stage_progress": stage_obj.progress,
            "total_progress": total_progress,
            "timestamp": datetime.now().isoformat()
        })

    async def update_preview(self, section: str, content: str, status: str = "generating"):
        """更新实时预览内容"""
        self._current_preview = {
            "section": section,
            "content": content,
            "status": status,
            "timestamp": datetime.now().isoformat()
        }

        await self._broadcast({
            "type": "preview_update",
            "session_id": self.session_id,
            "data": self._current_preview
        })

    async def add_missing_info(
        self,
        level: str,  # fatal/important/suggestion/format
        category: str,
        item: str,
        description: str,
        suggestions: List[Dict] = None
    ):
        """添加缺失信息提示"""
        await self._broadcast({
            "type": "missing_info",
            "session_id": self.session_id,
            "level": level,
            "category": category,
            "item": item,
            "description": description,
            "suggestions": suggestions or [],
            "timestamp": datetime.now().isoformat()
        })

    async def complete_generation(self, success: bool = True, summary: str = ""):
        """完成生成过程"""
        self.end_time = time.time()
        duration = self.end_time - (self.start_time or self.end_time)

        await self._broadcast({
            "type": "generation_completed",
            "session_id": self.session_id,
            "success": success,
            "summary": summary,
            "duration_seconds": duration,
            "total_progress": 1.0 if success else self._calculate_total_progress(),
            "timestamp": datetime.now().isoformat()
        })

    def _calculate_total_progress(self) -> float:
        """计算总进度"""
        if not self.stages:
            return 0.0

        total = sum(s.progress for s in self.stages.values())
        return total / len(self.stages)

    async def _broadcast(self, data: dict):
        """广播消息"""
        await self.broadcaster.broadcast(data)

    def get_snapshot(self) -> GenerationSnapshot:
        """获取当前快照"""
        return GenerationSnapshot(
            session_id=self.session_id,
            project_id=self.project_id,
            project_name=self.project_name,
            start_time=self.start_time or time.time(),
            update_time=time.time(),
            is_running=self.end_time is None,
            stages=self.stages,
            total_progress=self._calculate_total_progress()
        )

    def get_current_state(self) -> dict:
        """获取当前状态（用于HTTP轮询）"""
        snapshot = self.get_snapshot()
        return {
            "session_id": snapshot.session_id,
            "project_id": snapshot.project_id,
            "project_name": snapshot.project_name,
            "is_running": snapshot.is_running,
            "total_progress": snapshot.total_progress,
            "stages": self.get_default_stages_definition(),
            "current_preview": self._current_preview,
            "elapsed_seconds": time.time() - snapshot.start_time if snapshot.start_time else 0
        }


# 全局监控器实例管理
_generators: Dict[str, GenerationMonitor] = {}
_generator_lock = threading.Lock()


def get_or_create_monitor(project_id: str, project_name: str = "") -> GenerationMonitor:
    """获取或创建监控器"""
    with _generator_lock:
        if project_id not in _generators:
            _generators[project_id] = GenerationMonitor(project_id, project_name)
        return _generators[project_id]


def remove_monitor(project_id: str):
    """移除监控器"""
    with _generator_lock:
        if project_id in _generators:
            del _generators[project_id]


# ============ 便捷函数 ============

async def start_report_generation(project_id: str, project_name: str) -> GenerationMonitor:
    """开始报告生成"""
    monitor = get_or_create_monitor(project_id, project_name)
    await monitor.start_generation(project_id, project_name)
    return monitor


async def update_stage(stage: GenerationStage, status: StageStatus,
                      message: str = "", progress: float = -1,
                      project_id: str = ""):
    """更新阶段状态"""
    monitor = get_or_create_monitor(project_id) if project_id else None
    if monitor:
        await monitor.update_stage_status(stage, status, message, progress)


async def update_step(stage: GenerationStage, step_id: str, status: StepStatus,
                     message: str = "", progress: float = -1,
                     project_id: str = ""):
    """更新步骤状态"""
    monitor = get_or_create_monitor(project_id) if project_id else None
    if monitor:
        await monitor.update_step_status(stage, step_id, status, message, progress)


async def complete_report_generation(success: bool = True, summary: str = "",
                                    project_id: str = ""):
    """完成报告生成"""
    monitor = get_or_create_monitor(project_id) if project_id else None
    if monitor:
        await monitor.complete_generation(success, summary)


def get_generation_state(project_id: str) -> Optional[dict]:
    """获取生成状态（用于HTTP轮询）"""
    with _generator_lock:
        if project_id in _generators:
            return _generators[project_id].get_current_state()
    return None
