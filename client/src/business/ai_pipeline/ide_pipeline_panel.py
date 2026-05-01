"""
IDE页面组件 - 任务进度可视化面板

核心功能：
1. 任务进度可视化
2. 工作流状态监控
3. 审批点管理
4. 交互式任务管理
5. 实时更新通知
"""

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json
import os
from pathlib import Path


class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    ANALYZING = "analyzing"
    DECOMPOSING = "decomposing"
    CODING = "coding"
    TESTING = "testing"
    REVIEWING = "reviewing"
    DEPLOYING = "deploying"
    COMPLETED = "completed"
    FAILED = "failed"


class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class PipelineTask:
    """流水线任务"""
    id: str
    name: str
    description: str
    status: TaskStatus
    progress: int = 0
    estimated_time: float = 0.0
    elapsed_time: float = 0.0
    dependencies: List[str] = field(default_factory=list)
    assignee: Optional[str] = None
    subtasks: List["PipelineTask"] = field(default_factory=list)


@dataclass
class ApprovalPoint:
    """审批点"""
    id: str
    name: str
    description: str
    status: ApprovalStatus
    required_approvers: List[str] = field(default_factory=list)
    approved_by: List[str] = field(default_factory=list)
    due_date: Optional[datetime] = None
    comments: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class PipelineStage:
    """流水线阶段"""
    id: str
    name: str
    tasks: List[PipelineTask] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    progress: int = 0


@dataclass
class PipelineInstance:
    """流水线实例"""
    id: str
    workflow_id: str
    name: str
    stages: List[PipelineStage] = field(default_factory=list)
    approval_points: List[ApprovalPoint] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    progress: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_estimated_time: float = 0.0
    elapsed_time: float = 0.0


class PipelinePanel:
    """
    流水线面板 - 可视化任务进度和状态
    
    核心特性：
    1. 任务进度可视化
    2. 工作流状态监控
    3. 审批点管理
    4. 交互式任务管理
    5. 实时更新通知
    """

    def __init__(self):
        self._pipelines: Dict[str, PipelineInstance] = {}
        self._callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self._storage_path = Path(os.path.expanduser("~/.livingtree/pipelines"))
        self._storage_path.mkdir(parents=True, exist_ok=True)
        
        self._load_pipelines()

    def _load_pipelines(self):
        """加载流水线实例"""
        for filepath in self._storage_path.glob("*.json"):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    pipeline = self._deserialize_pipeline(data)
                    self._pipelines[pipeline.id] = pipeline
            except Exception as e:
                print(f"加载流水线失败 {filepath}: {e}")

    def _save_pipeline(self, pipeline: PipelineInstance):
        """保存流水线实例"""
        filepath = self._storage_path / f"{pipeline.id}.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self._serialize_pipeline(pipeline), f, ensure_ascii=False, indent=2)

    def _serialize_pipeline(self, pipeline: PipelineInstance) -> Dict[str, Any]:
        """序列化流水线"""
        return {
            "id": pipeline.id,
            "workflow_id": pipeline.workflow_id,
            "name": pipeline.name,
            "status": pipeline.status.value,
            "progress": pipeline.progress,
            "created_at": pipeline.created_at.isoformat(),
            "started_at": pipeline.started_at.isoformat() if pipeline.started_at else None,
            "completed_at": pipeline.completed_at.isoformat() if pipeline.completed_at else None,
            "total_estimated_time": pipeline.total_estimated_time,
            "elapsed_time": pipeline.elapsed_time,
            "stages": self._serialize_stages(pipeline.stages),
            "approval_points": self._serialize_approvals(pipeline.approval_points)
        }

    def _deserialize_pipeline(self, data: Dict[str, Any]) -> PipelineInstance:
        """反序列化流水线"""
        pipeline = PipelineInstance(
            id=data["id"],
            workflow_id=data["workflow_id"],
            name=data["name"],
            status=TaskStatus(data.get("status", "pending")),
            progress=data.get("progress", 0),
            total_estimated_time=data.get("total_estimated_time", 0.0),
            elapsed_time=data.get("elapsed_time", 0.0)
        )
        
        if "created_at" in data:
            pipeline.created_at = datetime.fromisoformat(data["created_at"])
        if "started_at" in data and data["started_at"]:
            pipeline.started_at = datetime.fromisoformat(data["started_at"])
        if "completed_at" in data and data["completed_at"]:
            pipeline.completed_at = datetime.fromisoformat(data["completed_at"])
        
        pipeline.stages = self._deserialize_stages(data.get("stages", []))
        pipeline.approval_points = self._deserialize_approvals(data.get("approval_points", []))
        
        return pipeline

    def _serialize_stages(self, stages: List[PipelineStage]) -> List[Dict[str, Any]]:
        """序列化阶段"""
        result = []
        for stage in stages:
            result.append({
                "id": stage.id,
                "name": stage.name,
                "status": stage.status.value,
                "progress": stage.progress,
                "tasks": self._serialize_tasks(stage.tasks)
            })
        return result

    def _deserialize_stages(self, data: List[Dict[str, Any]]) -> List[PipelineStage]:
        """反序列化阶段"""
        stages = []
        for stage_data in data:
            stage = PipelineStage(
                id=stage_data["id"],
                name=stage_data["name"],
                status=TaskStatus(stage_data.get("status", "pending")),
                progress=stage_data.get("progress", 0)
            )
            stage.tasks = self._deserialize_tasks(stage_data.get("tasks", []))
            stages.append(stage)
        return stages

    def _serialize_tasks(self, tasks: List[PipelineTask]) -> List[Dict[str, Any]]:
        """序列化任务"""
        result = []
        for task in tasks:
            result.append({
                "id": task.id,
                "name": task.name,
                "description": task.description,
                "status": task.status.value,
                "progress": task.progress,
                "estimated_time": task.estimated_time,
                "elapsed_time": task.elapsed_time,
                "dependencies": task.dependencies,
                "assignee": task.assignee,
                "subtasks": self._serialize_tasks(task.subtasks)
            })
        return result

    def _deserialize_tasks(self, data: List[Dict[str, Any]]) -> List[PipelineTask]:
        """反序列化任务"""
        tasks = []
        for task_data in data:
            task = PipelineTask(
                id=task_data["id"],
                name=task_data["name"],
                description=task_data.get("description", ""),
                status=TaskStatus(task_data.get("status", "pending")),
                progress=task_data.get("progress", 0),
                estimated_time=task_data.get("estimated_time", 0.0),
                elapsed_time=task_data.get("elapsed_time", 0.0),
                dependencies=task_data.get("dependencies", []),
                assignee=task_data.get("assignee")
            )
            task.subtasks = self._deserialize_tasks(task_data.get("subtasks", []))
            tasks.append(task)
        return task

    def _serialize_approvals(self, approvals: List[ApprovalPoint]) -> List[Dict[str, Any]]:
        """序列化审批点"""
        result = []
        for approval in approvals:
            result.append({
                "id": approval.id,
                "name": approval.name,
                "description": approval.description,
                "status": approval.status.value,
                "required_approvers": approval.required_approvers,
                "approved_by": approval.approved_by,
                "due_date": approval.due_date.isoformat() if approval.due_date else None,
                "comments": approval.comments
            })
        return result

    def _deserialize_approvals(self, data: List[Dict[str, Any]]) -> List[ApprovalPoint]:
        """反序列化审批点"""
        approvals = []
        for approval_data in data:
            approval = ApprovalPoint(
                id=approval_data["id"],
                name=approval_data["name"],
                description=approval_data.get("description", ""),
                status=ApprovalStatus(approval_data.get("status", "pending")),
                required_approvers=approval_data.get("required_approvers", []),
                approved_by=approval_data.get("approved_by", []),
                comments=approval_data.get("comments", [])
            )
            if "due_date" in approval_data and approval_data["due_date"]:
                approval.due_date = datetime.fromisoformat(approval_data["due_date"])
            approvals.append(approval)
        return approvals

    def create_pipeline(self, workflow_id: str, name: str, stages: Optional[List[PipelineStage]] = None) -> str:
        """
        创建流水线实例
        
        Args:
            workflow_id: 工作流ID
            name: 流水线名称
            stages: 阶段列表
            
        Returns:
            流水线ID
        """
        pipeline = PipelineInstance(
            id=f"pipeline_{int(datetime.now().timestamp())}",
            workflow_id=workflow_id,
            name=name,
            stages=stages or []
        )
        
        self._pipelines[pipeline.id] = pipeline
        self._save_pipeline(pipeline)
        
        self._notify({
            "type": "pipeline_created",
            "pipeline_id": pipeline.id,
            "name": pipeline.name
        })
        
        return pipeline.id

    def update_task_status(self, pipeline_id: str, task_id: str, status: TaskStatus, progress: int = 0):
        """
        更新任务状态
        
        Args:
            pipeline_id: 流水线ID
            task_id: 任务ID
            status: 新状态
            progress: 进度百分比
        """
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline:
            return
        
        task = self._find_task(pipeline, task_id)
        if task:
            task.status = status
            task.progress = progress
            
            self._update_pipeline_progress(pipeline)
            self._save_pipeline(pipeline)
            
            self._notify({
                "type": "task_updated",
                "pipeline_id": pipeline_id,
                "task_id": task_id,
                "status": status.value,
                "progress": progress
            })

    def _find_task(self, pipeline: PipelineInstance, task_id: str) -> Optional[PipelineTask]:
        """查找任务"""
        for stage in pipeline.stages:
            for task in stage.tasks:
                if task.id == task_id:
                    return task
                subtask = self._find_task_in_subtasks(task, task_id)
                if subtask:
                    return subtask
        return None

    def _find_task_in_subtasks(self, task: PipelineTask, task_id: str) -> Optional[PipelineTask]:
        """在子任务中查找"""
        for subtask in task.subtasks:
            if subtask.id == task_id:
                return subtask
            found = self._find_task_in_subtasks(subtask, task_id)
            if found:
                return found
        return None

    def _update_pipeline_progress(self, pipeline: PipelineInstance):
        """更新流水线进度"""
        total_tasks = 0
        completed_tasks = 0
        
        for stage in pipeline.stages:
            stage_tasks, stage_completed = self._count_tasks(stage)
            total_tasks += stage_tasks
            completed_tasks += stage_completed
            stage.progress = (stage_completed / stage_tasks) * 100 if stage_tasks > 0 else 0
            
            if stage_completed == stage_tasks and stage_tasks > 0:
                stage.status = TaskStatus.COMPLETED
            elif stage_completed > 0:
                stage.status = TaskStatus.IN_PROGRESS
        
        pipeline.progress = (completed_tasks / total_tasks) * 100 if total_tasks > 0 else 0
        
        if completed_tasks == total_tasks and total_tasks > 0:
            pipeline.status = TaskStatus.COMPLETED
            pipeline.completed_at = datetime.now()
        elif completed_tasks > 0:
            pipeline.status = TaskStatus.IN_PROGRESS
            if not pipeline.started_at:
                pipeline.started_at = datetime.now()

    def _count_tasks(self, stage: PipelineStage) -> tuple:
        """统计任务数量"""
        total = 0
        completed = 0
        
        for task in stage.tasks:
            t, c = self._count_task_and_subtasks(task)
            total += t
            completed += c
        
        return total, completed

    def _count_task_and_subtasks(self, task: PipelineTask) -> tuple:
        """统计任务和子任务"""
        total = 1
        completed = 1 if task.status == TaskStatus.COMPLETED else 0
        
        for subtask in task.subtasks:
            t, c = self._count_task_and_subtasks(subtask)
            total += t
            completed += c
        
        return total, completed

    def submit_approval(self, pipeline_id: str, approval_id: str, approver: str, approved: bool, comment: str = ""):
        """
        提交审批
        
        Args:
            pipeline_id: 流水线ID
            approval_id: 审批点ID
            approver: 审批人
            approved: 是否通过
            comment: 审批意见
        """
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline:
            return
        
        approval = self._find_approval(pipeline, approval_id)
        if approval:
            if approved:
                approval.status = ApprovalStatus.APPROVED
                approval.approved_by.append(approver)
            else:
                approval.status = ApprovalStatus.REJECTED
            
            if comment:
                approval.comments.append({
                    "user": approver,
                    "comment": comment,
                    "timestamp": datetime.now().isoformat()
                })
            
            self._save_pipeline(pipeline)
            
            self._notify({
                "type": "approval_submitted",
                "pipeline_id": pipeline_id,
                "approval_id": approval_id,
                "status": approval.status.value,
                "approver": approver
            })

    def _find_approval(self, pipeline: PipelineInstance, approval_id: str) -> Optional[ApprovalPoint]:
        """查找审批点"""
        for approval in pipeline.approval_points:
            if approval.id == approval_id:
                return approval
        return None

    def get_pipeline(self, pipeline_id: str) -> Optional[PipelineInstance]:
        """获取流水线实例"""
        return self._pipelines.get(pipeline_id)

    def list_pipelines(self) -> List[Dict[str, Any]]:
        """列出所有流水线"""
        result = []
        for pipeline in self._pipelines.values():
            result.append({
                "id": pipeline.id,
                "name": pipeline.name,
                "workflow_id": pipeline.workflow_id,
                "status": pipeline.status.value,
                "progress": pipeline.progress,
                "created_at": pipeline.created_at.isoformat(),
                "stages": len(pipeline.stages)
            })
        return result

    def get_pipeline_status(self, pipeline_id: str) -> Dict[str, Any]:
        """获取流水线状态"""
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline:
            return {"error": "流水线不存在"}
        
        stages_info = []
        for stage in pipeline.stages:
            stages_info.append({
                "id": stage.id,
                "name": stage.name,
                "status": stage.status.value,
                "progress": stage.progress,
                "tasks": [{
                    "id": t.id,
                    "name": t.name,
                    "status": t.status.value,
                    "progress": t.progress
                } for t in stage.tasks]
            })
        
        approvals_info = []
        for approval in pipeline.approval_points:
            approvals_info.append({
                "id": approval.id,
                "name": approval.name,
                "status": approval.status.value,
                "required_approvers": approval.required_approvers,
                "approved_by": approval.approved_by
            })
        
        return {
            "id": pipeline.id,
            "name": pipeline.name,
            "workflow_id": pipeline.workflow_id,
            "status": pipeline.status.value,
            "progress": pipeline.progress,
            "created_at": pipeline.created_at.isoformat(),
            "started_at": pipeline.started_at.isoformat() if pipeline.started_at else None,
            "completed_at": pipeline.completed_at.isoformat() if pipeline.completed_at else None,
            "total_estimated_time": pipeline.total_estimated_time,
            "elapsed_time": pipeline.elapsed_time,
            "stages": stages_info,
            "approval_points": approvals_info
        }

    def register_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """注册回调函数"""
        self._callbacks.append(callback)

    def _notify(self, event: Dict[str, Any]):
        """通知所有注册的回调"""
        for callback in self._callbacks:
            try:
                callback(event)
            except Exception as e:
                print(f"回调执行失败: {e}")


def get_pipeline_panel() -> PipelinePanel:
    """获取流水线面板单例"""
    global _pipeline_panel_instance
    if _pipeline_panel_instance is None:
        _pipeline_panel_instance = PipelinePanel()
    return _pipeline_panel_instance


_pipeline_panel_instance = None