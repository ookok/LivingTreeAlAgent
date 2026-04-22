"""
工作流引擎 - Visual Workflow System

功能：
1. 可视化工作流设计
2. 工作流执行引擎
3. 状态跟踪与通知
4. 工作流模板库
"""

import json
import uuid
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from pathlib import Path
import asyncio


class WorkflowStatus(Enum):
    """工作流状态"""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class StepStatus(Enum):
    """步骤状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class StepAction(Enum):
    """步骤动作"""
    APPROVE = "approve"
    REJECT = "reject"
    RETURN = "return"
    TRANSFER = "transfer"
    COMMENT = "comment"
    ATTACH = "attach"


class TriggerType(Enum):
    """触发器类型"""
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    EVENT = "event"
    CONDITION = "condition"
    FORM_SUBMIT = "form_submit"
    WEBHOOK = "webhook"


@dataclass
class WorkflowNode:
    """工作流节点"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""

    # 节点类型
    node_type: str = "task"  # start/task/condition/end/join/fork

    # 位置（用于可视化设计）
    position: Dict[str, float] = field(default_factory=lambda: {"x": 0, "y": 0})
    size: Dict[str, float] = field(default_factory=lambda: {"width": 120, "height": 60})

    # 处理人
    assignee_type: str = "role"  # role/user/department/expression
    assignee_id: str = ""
    assignee_name: str = ""
    assignee_expression: str = ""  # 动态表达式

    # 表单
    form_template_id: Optional[str] = None
    form_fields_readonly: List[str] = field(default_factory=list)
    form_fields_hidden: List[str] = field(default_factory=list)

    # 动作
    available_actions: List[str] = field(default_factory=list)  # approve/reject/return/transfer/comment
    default_action: str = "approve"

    # 期限
    due_days: int = 0  # 0表示无期限
    due_hours: int = 24  # 默认24小时
    reminder_enabled: bool = True
    reminder_intervals: List[int] = field(default_factory=lambda: [1, 4, 24])  # 小时

    # 条件（用于条件节点）
    conditions: List[Dict] = field(default_factory=list)
    condition_expression: str = ""

    # 输出
    output_mapping: Dict[str, str] = field(default_factory=dict)

    # 样式
    color: str = "#007acc"
    icon: str = "📋"

    # 元数据
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class WorkflowEdge:
    """工作流边（连接线）"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str = ""
    target_id: str = ""

    # 条件（决定走哪条边）
    condition: str = ""  # 表达式
    label: str = ""  # 显示标签

    # 样式
    stroke_style: str = "solid"  # solid/dashed/dotted
    color: str = "#666666"

    # 动画
    animated: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class WorkflowDiagram:
    """工作流图"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""

    # 节点和边
    nodes: List[WorkflowNode] = field(default_factory=list)
    edges: List[WorkflowEdge] = field(default_factory=list)

    # 触发器
    trigger_type: str = TriggerType.MANUAL.value
    trigger_config: Dict = field(default_factory=dict)

    # 设置
    allow_withdraw: bool = True
    allow_transfer: bool = True
    allow_skip: bool = False
    allow_reassign: bool = True

    # 通知
    notify_on_start: bool = True
    notify_on_complete: bool = True
    notify_on_reject: bool = True
    notify_on_timeout: bool = True

    # 草稿保存
    auto_save_draft: bool = True
    draft_interval_minutes: int = 5

    # 版本
    version: str = "1.0.0"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # 发布状态
    published: bool = False
    published_at: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class WorkflowExecution:
    """工作流执行实例"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = ""

    # 状态
    status: str = WorkflowStatus.DRAFT.value

    # 发起人
    initiator_id: str = ""
    initiator_name: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    # 上下文数据
    context: Dict[str, Any] = field(default_factory=dict)

    # 当前节点
    current_node_id: str = ""
    node_history: List[Dict] = field(default_factory=list)

    # 节点执行状态
    node_states: Dict[str, Dict] = field(default_factory=dict)

    # 待处理任务
    pending_tasks: List[Dict] = field(default_factory=list)

    # 操作历史
    operation_history: List[Dict] = field(default_factory=list)

    # 备注
    comments: List[Dict] = field(default_factory=list)

    # 附件
    attachments: List[Dict] = field(default_factory=list)

    # 期限
    due_dates: Dict[str, str] = field(default_factory=dict)  # node_id -> due_date

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class WorkflowTask:
    """工作流任务"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    execution_id: str = ""
    workflow_id: str = ""
    node_id: str = ""

    # 任务信息
    name: str = ""
    description: str = ""

    # 处理人
    assignee_id: str = ""
    assignee_name: str = ""

    # 状态
    status: str = StepStatus.PENDING.value
    priority: int = 0  # 0-9

    # 时间
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    due_at: Optional[str] = None
    completed_at: Optional[str] = None

    # 操作
    available_actions: List[str] = field(default_factory=list)
    comment_required: bool = False

    # 表单数据
    form_data: Dict[str, Any] = field(default_factory=dict)

    # 审批意见
    decision: Optional[str] = None
    decision_comment: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


class WorkflowEngine:
    """工作流执行引擎"""

    def __init__(self):
        self._event_handlers: Dict[str, List[Callable]] = {}

    def on(self, event: str, handler: Callable):
        """注册事件处理器"""
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)

    def _emit(self, event: str, data: dict):
        """触发事件"""
        handlers = self._event_handlers.get(event, [])
        for handler in handlers:
            try:
                handler(data)
            except Exception as e:
                print(f"Workflow event handler error: {e}")

    async def start_workflow(
        self,
        workflow: WorkflowDiagram,
        initiator_id: str,
        initiator_name: str,
        context: Dict[str, Any] = None
    ) -> WorkflowExecution:
        """启动工作流"""
        execution = WorkflowExecution(
            workflow_id=workflow.id,
            status=WorkflowStatus.ACTIVE.value,
            initiator_id=initiator_id,
            initiator_name=initiator_name,
            started_at=datetime.now().isoformat(),
            context=context or {}
        )

        # 找到开始节点
        start_node = self._find_start_node(workflow)
        if not start_node:
            raise ValueError("Workflow has no start node")

        # 初始化节点状态
        for node in workflow.nodes:
            execution.node_states[node.id] = {
                "status": StepStatus.PENDING.value,
                "started_at": None,
                "completed_at": None
            }

        # 执行开始节点
        execution.current_node_id = start_node.id
        execution.node_states[start_node.id] = {
            "status": StepStatus.COMPLETED.value,
            "started_at": datetime.now().isoformat(),
            "completed_at": datetime.now().isoformat()
        }

        execution.node_history.append({
            "node_id": start_node.id,
            "action": "start",
            "timestamp": datetime.now().isoformat()
        })

        # 执行下一个节点
        await self._execute_node(workflow, execution, start_node.id)

        self._emit("workflow.started", {"execution": execution})
        return execution

    async def _execute_node(
        self,
        workflow: WorkflowDiagram,
        execution: WorkflowExecution,
        node_id: str
    ):
        """执行节点"""
        node = self._find_node(workflow, node_id)
        if not node:
            return

        # 更新节点状态
        execution.current_node_id = node.id
        execution.node_states[node.id]["status"] = StepStatus.IN_PROGRESS.value
        execution.node_states[node.id]["started_at"] = datetime.now().isoformat()

        # 创建待处理任务
        if node.node_type in ["task", "approval"]:
            task = WorkflowTask(
                execution_id=execution.id,
                workflow_id=workflow.id,
                node_id=node.id,
                name=node.name,
                description=node.description,
                assignee_id=node.assignee_id,
                assignee_name=node.assignee_name,
                available_actions=node.available_actions,
                comment_required="comment" in node.available_actions
            )

            # 设置期限
            if node.due_days > 0 or node.due_hours > 0:
                due_delta = timedelta(days=node.due_days, hours=node.due_hours)
                task.due_at = (datetime.now() + due_delta).isoformat()

            execution.pending_tasks.append(task.to_dict())

        # 触发节点开始事件
        self._emit("node.started", {
            "execution": execution,
            "node": node
        })

    async def complete_task(
        self,
        execution: WorkflowExecution,
        task_id: str,
        action: str,
        user_id: str,
        user_name: str,
        comment: str = None,
        form_data: Dict = None
    ) -> WorkflowExecution:
        """完成任务"""
        # 找到任务
        task_data = None
        task_index = -1
        for i, t in enumerate(execution.pending_tasks):
            if t["id"] == task_id:
                task_data = t
                task_index = i
                break

        if task_index == -1:
            raise ValueError("Task not found")

        task = WorkflowTask(**task_data)
        node_id = task.node_id

        # 记录操作
        execution.operation_history.append({
            "task_id": task_id,
            "action": action,
            "user_id": user_id,
            "user_name": user_name,
            "comment": comment,
            "timestamp": datetime.now().isoformat()
        })

        # 更新任务状态
        task.status = StepStatus.COMPLETED.value
        task.decision = action
        task.decision_comment = comment
        task.completed_at = datetime.now().isoformat()
        if form_data:
            task.form_data = form_data

        # 更新执行中的任务
        execution.pending_tasks[task_index] = task.to_dict()

        # 更新节点状态
        execution.node_states[node_id]["status"] = StepStatus.COMPLETED.value
        execution.node_states[node_id]["completed_at"] = datetime.now().isoformat()

        execution.node_history.append({
            "node_id": node_id,
            "action": action,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        })

        # 从待处理中移除
        execution.pending_tasks.pop(task_index)

        # 添加评论
        if comment:
            execution.comments.append({
                "node_id": node_id,
                "user_id": user_id,
                "user_name": user_name,
                "content": comment,
                "timestamp": datetime.now().isoformat()
            })

        # 根据动作决定下一步
        workflow = self._get_workflow(execution.workflow_id)
        if workflow:
            next_node_id = self._get_next_node(workflow, node_id, action)
            if next_node_id:
                await self._execute_node(workflow, execution, next_node_id)
            else:
                # 工作流完成
                execution.status = WorkflowStatus.COMPLETED.value
                execution.completed_at = datetime.now().isoformat()
        else:
            execution.status = WorkflowStatus.COMPLETED.value
            execution.completed_at = datetime.now().isoformat()

        self._emit("task.completed", {
            "execution": execution,
            "task": task
        })

        return execution

    async def withdraw_workflow(self, execution: WorkflowExecution, user_id: str, reason: str) -> WorkflowExecution:
        """撤回工作流"""
        if not execution.context.get("allow_withdraw", True):
            raise ValueError("Workflow does not allow withdraw")

        # 记录撤回
        execution.operation_history.append({
            "action": "withdraw",
            "user_id": user_id,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        })

        execution.status = WorkflowStatus.CANCELLED.value
        execution.completed_at = datetime.now().isoformat()

        self._emit("workflow.withdrawn", {"execution": execution})
        return execution

    def _find_start_node(self, workflow: WorkflowDiagram) -> Optional[WorkflowNode]:
        """找到开始节点"""
        for node in workflow.nodes:
            if node.node_type == "start":
                return node
        # 如果没有明确的开始节点，返回第一个节点
        return workflow.nodes[0] if workflow.nodes else None

    def _find_end_nodes(self, workflow: WorkflowDiagram) -> List[WorkflowNode]:
        """找到结束节点"""
        return [node for node in workflow.nodes if node.node_type == "end"]

    def _find_node(self, workflow: WorkflowDiagram, node_id: str) -> Optional[WorkflowNode]:
        """找到节点"""
        for node in workflow.nodes:
            if node.id == node_id:
                return node
        return None

    def _get_next_node(self, workflow: WorkflowDiagram, current_node_id: str, action: str) -> Optional[str]:
        """获取下一节点"""
        # 找到从当前节点出发的边
        for edge in workflow.edges:
            if edge.source_id == current_node_id:
                # 检查边条件
                if edge.condition:
                    # 评估条件表达式
                    condition = edge.condition
                    # 支持的条件类型：
                    # 1. 简单动作匹配: action == "approve"
                    # 2. 变量比较: status == "completed"
                    # 3. 布尔表达式: status == "completed" and priority == "high"
                    
                    # 构建评估上下文
                    eval_context = {
                        "action": action,
                        "current_node": current_node_id,
                        "workflow": workflow,
                        "True": True,
                        "False": False,
                        "None": None,
                    }
                    
                    try:
                        # 使用 eval 评估条件表达式
                        result = eval(condition, {"__builtins__": {}}, eval_context)
                        if result:
                            return edge.target_id
                    except Exception as e:
                        logger.warning(f"条件表达式评估失败: {condition}, 错误: {e}")
                        # 条件评估失败时，默认不匹配
                        continue
                else:
                    return edge.target_id
        return None

    def _get_workflow(self, workflow_id: str) -> Optional[WorkflowDiagram]:
        """获取工作流定义（需要外部提供）"""
        return None


class WorkflowDesigner:
    """可视化工作流设计器"""

    def __init__(self):
        self.workflow: Optional[WorkflowDiagram] = None
        self._observers: List[Callable] = []

    def create_workflow(self, name: str, description: str = "") -> WorkflowDiagram:
        """创建新工作流"""
        self.workflow = WorkflowDiagram(
            name=name,
            description=description
        )

        # 添加开始和结束节点
        self._add_start_node()
        self._add_end_node()

        return self.workflow

    def load_workflow(self, workflow: WorkflowDiagram):
        """加载工作流"""
        self.workflow = workflow

    def _add_start_node(self):
        """添加开始节点"""
        start_node = WorkflowNode(
            name="开始",
            node_type="start",
            color="#52c41a",
            icon="▶️"
        )
        self.workflow.nodes.append(start_node)

    def _add_end_node(self):
        """添加结束节点"""
        end_node = WorkflowNode(
            name="结束",
            node_type="end",
            color="#ff4d4f",
            icon="⏹️"
        )
        self.workflow.nodes.append(end_node)

    def add_task_node(
        self,
        name: str,
        description: str = "",
        assignee_type: str = "role",
        assignee_id: str = "",
        assignee_name: str = ""
    ) -> WorkflowNode:
        """添加任务节点"""
        node = WorkflowNode(
            name=name,
            description=description,
            node_type="task",
            assignee_type=assignee_type,
            assignee_id=assignee_id,
            assignee_name=assignee_name,
            available_actions=["complete", "comment"],
            icon="📋"
        )
        self.workflow.nodes.append(node)

        # 自动连接
        self._auto_connect(node.id)

        return node

    def add_approval_node(
        self,
        name: str,
        description: str = "",
        assignee_type: str = "role",
        assignee_id: str = "",
        assignee_name: str = ""
    ) -> WorkflowNode:
        """添加审批节点"""
        node = WorkflowNode(
            name=name,
            description=description,
            node_type="approval",
            assignee_type=assignee_type,
            assignee_id=assignee_id,
            assignee_name=assignee_name,
            available_actions=["approve", "reject", "return", "transfer", "comment"],
            due_days=1,
            reminder_enabled=True,
            icon="✅"
        )
        self.workflow.nodes.append(node)

        self._auto_connect(node.id)
        return node

    def add_condition_node(
        self,
        name: str,
        condition_expression: str = ""
    ) -> WorkflowNode:
        """添加条件节点"""
        node = WorkflowNode(
            name=name,
            node_type="condition",
            condition_expression=condition_expression,
            icon="❓"
        )
        self.workflow.nodes.append(node)

        self._auto_connect(node.id)
        return node

    def _auto_connect(self, node_id: str):
        """自动连接节点"""
        # 找到最后一个非结束节点，连接到这个节点
        if len(self.workflow.nodes) < 2:
            return

        last_node = None
        for n in self.workflow.nodes[:-1]:
            if n.id != node_id:
                last_node = n

        if last_node:
            # 检查是否已经连接
            existing = any(
                e.source_id == last_node.id and e.target_id == node_id
                for e in self.workflow.edges
            )
            if not existing:
                edge = WorkflowEdge(
                    source_id=last_node.id,
                    target_id=node_id
                )
                self.workflow.edges.append(edge)

    def connect(self, source_id: str, target_id: str, condition: str = "") -> WorkflowEdge:
        """手动连接两个节点"""
        edge = WorkflowEdge(
            source_id=source_id,
            target_id=target_id,
            condition=condition
        )
        self.workflow.edges.append(edge)
        return edge

    def remove_node(self, node_id: str):
        """移除节点及其连接"""
        self.workflow.nodes = [n for n in self.workflow.nodes if n.id != node_id]
        self.workflow.edges = [
            e for e in self.workflow.edges
            if e.source_id != node_id and e.target_id != node_id
        ]

    def move_node(self, node_id: str, x: float, y: float):
        """移动节点位置"""
        for node in self.workflow.nodes:
            if node.id == node_id:
                node.position = {"x": x, "y": y}
                break

    def set_node_assignee(self, node_id: str, assignee_type: str, assignee_id: str, assignee_name: str):
        """设置节点处理人"""
        for node in self.workflow.nodes:
            if node.id == node_id:
                node.assignee_type = assignee_type
                node.assignee_id = assignee_id
                node.assignee_name = assignee_name
                break

    def validate(self) -> Dict[str, Any]:
        """验证工作流"""
        errors = []
        warnings = []

        if not self.workflow:
            errors.append("工作流未初始化")
            return {"valid": False, "errors": errors, "warnings": warnings}

        # 检查节点数量
        if len(self.workflow.nodes) < 2:
            errors.append("工作流至少需要开始和结束节点")

        # 检查开始和结束节点
        has_start = any(n.node_type == "start" for n in self.workflow.nodes)
        has_end = any(n.node_type == "end" for n in self.workflow.nodes)

        if not has_start:
            errors.append("缺少开始节点")
        if not has_end:
            errors.append("缺少结束节点")

        # 检查孤立节点
        connected_nodes = set()
        for edge in self.workflow.edges:
            connected_nodes.add(edge.source_id)
            connected_nodes.add(edge.target_id)

        for node in self.workflow.nodes:
            if node.node_type not in ["start", "end"] and node.id not in connected_nodes:
                warnings.append(f"节点 '{node.name}' 未连接到任何其他节点")

        # 检查审批节点的处理人
        for node in self.workflow.nodes:
            if node.node_type == "approval":
                if not node.assignee_id:
                    warnings.append(f"审批节点 '{node.name}' 未设置处理人")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }

    def generate_workflow_code(self) -> str:
        """生成工作流代码（用于存储）"""
        return json.dumps(self.workflow.to_dict(), ensure_ascii=False, indent=2)

    @staticmethod
    def load_from_code(code: str) -> WorkflowDiagram:
        """从代码加载工作流"""
        data = json.loads(code)
        return WorkflowDiagram(**data)


class WorkflowStore:
    """工作流存储"""

    def __init__(self, store_path: str = None):
        if store_path is None:
            store_path = Path("~/.hermes/workflow").expanduser()

        self.store_path = Path(store_path)
        self.store_path.mkdir(parents=True, exist_ok=True)

        self._workflows_index = self.store_path / "workflows.json"
        self._executions_dir = self.store_path / "executions"
        self._executions_dir.mkdir(exist_ok=True)

        self._load_indexes()

    def _load_indexes(self):
        """加载索引"""
        if self._workflows_index.exists():
            with open(self._workflows_index, "r", encoding="utf-8") as f:
                self._workflows: Dict[str, dict] = json.load(f)
        else:
            self._workflows = {}

    def _save_workflows_index(self):
        """保存工作流索引"""
        with open(self._workflows_index, "w", encoding="utf-8") as f:
            json.dump(self._workflows, f, ensure_ascii=False, indent=2)

    def save_workflow(self, workflow: WorkflowDiagram) -> str:
        """保存工作流"""
        workflow.updated_at = datetime.now().isoformat()

        workflow_file = self.store_path / f"{workflow.id}.json"
        with open(workflow_file, "w", encoding="utf-8") as f:
            json.dump(workflow.to_dict(), f, ensure_ascii=False, indent=2)

        self._workflows[workflow.id] = {
            "name": workflow.name,
            "version": workflow.version,
            "published": workflow.published
        }
        self._save_workflows_index()

        return workflow.id

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowDiagram]:
        """获取工作流"""
        workflow_file = self.store_path / f"{workflow_id}.json"
        if not workflow_file.exists():
            return None

        with open(workflow_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return WorkflowDiagram(**data)

    def publish_workflow(self, workflow_id: str) -> bool:
        """发布工作流"""
        workflow = self.get_workflow(workflow_id)
        if not workflow:
            return False

        workflow.published = True
        workflow.published_at = datetime.now().isoformat()
        self.save_workflow(workflow)
        return True

    def save_execution(self, execution: WorkflowExecution):
        """保存执行实例"""
        execution_file = self._executions_dir / f"{execution.id}.json"
        with open(execution_file, "w", encoding="utf-8") as f:
            json.dump(execution.to_dict(), f, ensure_ascii=False, indent=2)

    def get_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        """获取执行实例"""
        execution_file = self._executions_dir / f"{execution_id}.json"
        if not execution_file.exists():
            return None

        with open(execution_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return WorkflowExecution(**data)

    def list_executions(
        self,
        workflow_id: str = None,
        status: str = None,
        assignee_id: str = None
    ) -> List[WorkflowExecution]:
        """列出执行实例"""
        executions = []

        for file in self._executions_dir.glob("*.json"):
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)

            execution = WorkflowExecution(**data)

            if workflow_id and execution.workflow_id != workflow_id:
                continue

            if status and execution.status != status:
                continue

            if assignee_id:
                # 检查是否分配给了该用户
                is_assignee = any(
                    task.get("assignee_id") == assignee_id
                    for task in execution.pending_tasks
                )
                if not is_assignee:
                    continue

            executions.append(execution)

        return sorted(executions, key=lambda e: e.started_at or "", reverse=True)


# 内置工作流模板
BUILTIN_WORKFLOWS = {
    "simple_approval": {
        "name": "简单审批流程",
        "description": "单级审批，适用于小额审批",
        "nodes": [
            {
                "id": "start",
                "name": "开始",
                "node_type": "start",
                "position": {"x": 100, "y": 200},
                "color": "#52c41a"
            },
            {
                "id": "approval",
                "name": "主管审批",
                "node_type": "approval",
                "position": {"x": 300, "y": 200},
                "assignee_type": "role",
                "assignee_id": "manager",
                "assignee_name": "部门主管",
                "available_actions": ["approve", "reject", "comment"],
                "due_days": 1
            },
            {
                "id": "end",
                "name": "结束",
                "node_type": "end",
                "position": {"x": 500, "y": 200},
                "color": "#ff4d4f"
            }
        ],
        "edges": [
            {"source_id": "start", "target_id": "approval"},
            {"source_id": "approval", "target_id": "end"}
        ]
    },
    "multi_approval": {
        "name": "多级审批流程",
        "description": "适用于大额审批，需多级批准",
        "nodes": [
            {"id": "start", "name": "开始", "node_type": "start", "position": {"x": 50, "y": 200}},
            {"id": "l1", "name": "一级审批", "node_type": "approval", "position": {"x": 200, "y": 200}, "due_days": 1},
            {"id": "l2", "name": "二级审批", "node_type": "approval", "position": {"x": 350, "y": 200}, "due_days": 2},
            {"id": "l3", "name": "三级审批", "node_type": "approval", "position": {"x": 500, "y": 200}, "due_days": 3},
            {"id": "end", "name": "结束", "node_type": "end", "position": {"x": 650, "y": 200}}
        ],
        "edges": [
            {"source_id": "start", "target_id": "l1"},
            {"source_id": "l1", "target_id": "l2"},
            {"source_id": "l2", "target_id": "l3"},
            {"source_id": "l3", "target_id": "end"}
        ]
    }
}


# 全局实例
_workflow_store: Optional[WorkflowStore] = None
_workflow_engine: Optional[WorkflowEngine] = None


def get_workflow_store() -> WorkflowStore:
    """获取工作流存储"""
    global _workflow_store
    if _workflow_store is None:
        _workflow_store = WorkflowStore()
    return _workflow_store


def get_workflow_engine() -> WorkflowEngine:
    """获取工作流引擎"""
    global _workflow_engine
    if _workflow_engine is None:
        _workflow_engine = WorkflowEngine()
    return _workflow_engine


# 导入节点类型
from .nodes.browser_use_node import (
    BrowserUseNode,
    create_browser_use_node,
)

# 导入通知服务
from .notification_service import (
    NotificationTemplateManager,
    NotificationTemplate,
    NotificationRule,
    Notification,
    NotificationChannel,
    NotificationPriority,
    NotificationStatus,
    WorkflowNotificationService,
    get_notification_service,
    get_template_manager,
)

__all__ = [
    # 工作流核心
    "WorkflowStatus", "StepStatus", "StepAction", "TriggerType",
    "WorkflowNode", "WorkflowEdge", "WorkflowDiagram",
    "WorkflowExecution", "WorkflowTask",
    "WorkflowEngine", "WorkflowDesigner", "WorkflowStore",
    "BUILTIN_WORKFLOWS",
    "get_workflow_store", "get_workflow_engine",

    # 节点类型
    "BrowserUseNode", "create_browser_use_node",

    # 通知服务
    "NotificationTemplateManager", "NotificationTemplate",
    "NotificationRule", "Notification",
    "NotificationChannel", "NotificationPriority", "NotificationStatus",
    "WorkflowNotificationService",
    "get_notification_service", "get_template_manager",
]