"""
章节审核追踪器 (Section Verification Tracker)
==========================================

核心理念：
- 每个 AI 生成的章节都有明确的审核状态
- 关键数据必须由工程师人工确认
- 建立完整的人机分工机制

审核状态流转：
┌─────────┐    ┌────────────┐    ┌─────────────────┐
│ PENDING │───▶│ GENERATING │───▶│AWAITING_VERIFICATION│
└─────────┘    └────────────┘    └────────┬────────┘
                                         │
         ┌───────────────────────────────┼───────────────────────────────┐
         │                               │                               │
         ▼                               ▼                               ▼
┌────────────────┐           ┌────────────────┐           ┌────────────────┐
│   VERIFIED     │           │   REJECTED     │           │ MANUAL_EDITED │
│   (通过)        │           │   (驳回)        │           │   (人工编辑)   │
└────────────────┘           └────────────────┘           └────────────────┘
                                  │
                                  ▼
                         ┌────────────────┐
                         │ RE_GENERATING  │
                         └────────────────┘
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional


class VerificationAction(Enum):
    """审核操作"""
    APPROVE = "approve"           # 批准
    REJECT = "reject"             # 驳回
    REQUEST_MENTION = "mention"    # 要求补充
    MANUAL_OVERRIDE = "override"   # 人工覆盖
    ESCALATE = "escalate"         # 升级处理


@dataclass
class VerificationRecord:
    """审核记录"""
    record_id: str
    section_id: str
    action: VerificationAction

    # 审核详情
    verifier: str                 # 审核人
    timestamp: datetime = field(default_factory=datetime.now)
    comment: str = ""            # 审核意见

    # 变更内容
    changed_fields: list = field(default_factory=list)  # 修改的字段
    previous_values: dict = field(default_factory=dict)  # 修改前的值
    new_values: dict = field(default_factory=dict)      # 修改后的值

    # 签名
    digital_signature: str = ""   # 数字签名（可选）


@dataclass
class VerificationTask:
    """审核任务"""
    task_id: str
    section_id: str
    section_title: str

    # 任务详情
    task_type: str               # verification/completion/signature
    priority: int = 1            # 优先级 1-5
    due_date: datetime = None

    # 依赖
    depends_on: list = field(default_factory=list)  # 依赖的任务

    # 状态
    status: str = "pending"       # pending/in_progress/completed/cancelled
    assigned_to: str = ""        # 指派人
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime = None

    # 审核结果
    verification_result: VerificationRecord = None


class SectionVerificationTracker:
    """
    章节审核追踪器

    核心理念：
    - 每个章节都有完整的审核历史
    - 审核状态可视化，一目了然
    - 支持审核流程的自动化触发

    用法:
        tracker = SectionVerificationTracker()

        # 创建审核任务
        task = tracker.create_verification_task(
            section_id="air_impact",
            section_title="大气环境影响",
            priority=1,
            assigned_to="张工"
        )

        # 提交审核结果
        tracker.submit_verification(
            task_id=task.task_id,
            action=VerificationAction.APPROVE,
            verifier="张工",
            comment="数据核实无误，同意通过"
        )

        # 获取审核进度
        progress = tracker.get_verification_progress(project_id)
    """

    def __init__(self, data_dir: str = "./data/eia"):
        self.data_dir = data_dir
        self._verification_tasks: dict[str, dict] = {}
        self._verification_history: list[VerificationRecord] = []
        self._workflow_rules: dict = {}

        self._load_default_rules()

    def _load_default_rules(self) -> None:
        """加载默认审核规则"""
        self._workflow_rules = {
            "air_impact": {
                "required_verifiers": ["大气工程师"],
                "depends_on": ["engineering"],
                "auto_trigger": True
            },
            "water_impact": {
                "required_verifiers": ["水工程师"],
                "depends_on": ["engineering"],
                "auto_trigger": True
            },
            "noise_impact": {
                "required_verifiers": ["噪声工程师"],
                "depends_on": ["engineering"],
                "auto_trigger": True
            },
            "conclusion": {
                "required_verifiers": ["项目负责人"],
                "depends_on": ["air_impact", "water_impact", "noise_impact"],
                "auto_trigger": False,
                "require_all_approved": True
            }
        }

    def create_verification_task(
        self,
        project_id: str,
        section_id: str,
        section_title: str,
        task_type: str = "verification",
        priority: int = 3,
        assigned_to: str = "",
        due_date: datetime = None,
        depends_on: list = None
    ) -> VerificationTask:
        """创建审核任务"""
        task_id = f"{project_id}_{section_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        task = VerificationTask(
            task_id=task_id,
            section_id=section_id,
            section_title=section_title,
            task_type=task_type,
            priority=priority,
            assigned_to=assigned_to,
            due_date=due_date,
            depends_on=depends_on or []
        )

        # 存储任务
        if project_id not in self._verification_tasks:
            self._verification_tasks[project_id] = {}

        self._verification_tasks[project_id][task_id] = {
            "task": task,
            "status_history": []
        }

        return task

    def submit_verification(
        self,
        task_id: str,
        action: VerificationAction,
        verifier: str,
        comment: str = "",
        changed_fields: list = None,
        previous_values: dict = None,
        new_values: dict = None
    ) -> VerificationRecord:
        """
        提交审核结果

        Args:
            task_id: 任务ID
            action: 审核操作
            verifier: 审核人
            comment: 审核意见
            changed_fields: 修改的字段列表
            previous_values: 修改前的值
            new_values: 修改后的值

        Returns:
            VerificationRecord: 审核记录
        """
        # 查找任务
        task_obj = None
        for project_tasks in self._verification_tasks.values():
            if task_id in project_tasks:
                task_obj = project_tasks[task_id]["task"]
                break

        if not task_obj:
            raise ValueError(f"任务 {task_id} 不存在")

        # 创建审核记录
        record = VerificationRecord(
            record_id=f"vr_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            section_id=task_obj.section_id,
            action=action,
            verifier=verifier,
            comment=comment,
            changed_fields=changed_fields or [],
            previous_values=previous_values or {},
            new_values=new_values or {}
        )

        # 更新任务状态
        if action == VerificationAction.APPROVE:
            task_obj.status = "completed"
            task_obj.completed_at = datetime.now()
            task_obj.verification_result = record

            # 如果有关联的后续任务，自动触发
            self._trigger_dependent_tasks(task_obj)

        elif action == VerificationAction.REJECT:
            task_obj.status = "rejected"
            # 可能需要重新生成

        elif action == VerificationAction.MANUAL_OVERRIDE:
            task_obj.status = "completed"
            task_obj.completed_at = datetime.now()
            task_obj.verification_result = record

        # 记录历史
        self._verification_history.append(record)

        return record

    def _trigger_dependent_tasks(self, completed_task: VerificationTask) -> None:
        """触发依赖此任务的其他任务"""
        # 如果完成的是 conclusion 依赖的前置任务，通知可以开始 conclusion 审核
        dependent_rules = {
            v.get("depends_on", []): k
            for k, v in self._workflow_rules.items()
            if completed_task.section_id in v.get("depends_on", [])
        }

        # 如果所有依赖都完成，通知 conclusion 可以开始

    def get_verification_progress(self, project_id: str) -> dict:
        """
        获取项目的审核进度

        Returns:
            dict: {
                "total": 10,
                "completed": 6,
                "pending": 2,
                "rejected": 1,
                "progress_rate": 0.6,
                "sections": {
                    "air_impact": {"status": "verified", "verifier": "张工", "date": "2024-01-15"},
                    ...
                }
            }
        """
        if project_id not in self._verification_tasks:
            return {
                "total": 0,
                "completed": 0,
                "pending": 0,
                "progress_rate": 0,
                "sections": {}
            }

        tasks = self._verification_tasks[project_id]

        total = len(tasks)
        completed = sum(1 for t in tasks.values() if t["task"].status == "completed")
        pending = sum(1 for t in tasks.values() if t["task"].status == "pending")
        rejected = sum(1 for t in tasks.values() if t["task"].status == "rejected")

        sections = {}
        for task_id, task_data in tasks.items():
            task = task_data["task"]
            result = task.verification_result

            sections[task.section_id] = {
                "title": task.section_title,
                "status": task.status,
                "assigned_to": task.assigned_to,
                "priority": task.priority,
                "verifier": result.verifier if result else None,
                "verified_at": result.timestamp.isoformat() if result else None,
                "comment": result.comment if result else None
            }

        return {
            "total": total,
            "completed": completed,
            "pending": pending,
            "rejected": rejected,
            "progress_rate": completed / total if total > 0 else 0,
            "sections": sections
        }

    def get_pending_tasks(
        self,
        project_id: str = None,
        assigned_to: str = None
    ) -> list[VerificationTask]:
        """获取待审核任务"""
        tasks = []

        for pid, project_tasks in self._verification_tasks.items():
            if project_id and pid != project_id:
                continue

            for task_id, task_data in project_tasks.items():
                task = task_data["task"]

                if task.status != "pending":
                    continue

                if assigned_to and task.assigned_to != assigned_to:
                    continue

                tasks.append(task)

        # 按优先级排序
        tasks.sort(key=lambda t: t.priority)

        return tasks

    def get_section_verification_history(
        self,
        section_id: str
    ) -> list[VerificationRecord]:
        """获取章节的审核历史"""
        return [
            r for r in self._verification_history
            if r.section_id == section_id
        ]

    def generate_verification_report(
        self,
        project_id: str,
        sections: dict
    ) -> str:
        """生成审核报告"""
        progress = self.get_verification_progress(project_id)

        # 构建章节状态表格
        section_rows = ""
        for section_id, info in progress["sections"].items():
            status_icon = "✅" if info["status"] == "completed" else "⏳" if info["status"] == "pending" else "❌"
            section_rows += f"""
<tr>
    <td>{info['title']}</td>
    <td>{status_icon} {info['status']}</td>
    <td>{info.get('verifier', '-')}</td>
    <td>{info.get('verified_at', '-')}</td>
    <td>{info.get('comment', '-')}</td>
</tr>
"""

        report = f"""
# 环评报告审核报告

## 审核进度

| 指标 | 数值 |
|------|------|
| 总章节数 | {progress['total']} |
| 已完成 | {progress['completed']} |
| 待审核 | {progress['pending']} |
| 驳回 | {progress['rejected']} |
| 完成率 | {progress['progress_rate']*100:.1f}% |

## 章节审核状态

| 章节 | 状态 | 审核人 | 审核时间 | 意见 |
|------|------|--------|----------|------|
{section_rows}

## 审核流程规则

"""

        # 添加审核规则说明
        for section_id, rule in self._workflow_rules.items():
            required = ", ".join(rule.get("required_verifiers", []))
            depends = ", ".join(rule.get("depends_on", [])) or "无"
            auto = "是" if rule.get("auto_trigger") else "否"

            report += f"""
### {section_id}
- **需要审核人**: {required}
- **依赖章节**: {depends}
- **自动触发**: {auto}
"""

        return report

    def export_verification_records(
        self,
        project_id: str,
        format: str = "json"
    ) -> str:
        """导出审核记录"""
        if project_id not in self._verification_tasks:
            return "{}"

        records = []

        for task_id, task_data in self._verification_tasks[project_id].items():
            task = task_data["task"]
            records.append({
                "task_id": task.task_id,
                "section_id": task.section_id,
                "section_title": task.section_title,
                "status": task.status,
                "priority": task.priority,
                "assigned_to": task.assigned_to,
                "created_at": task.created_at.isoformat(),
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "verification": {
                    "verifier": task.verification_result.verifier if task.verification_result else None,
                    "action": task.verification_result.action.value if task.verification_result else None,
                    "comment": task.verification_result.comment if task.verification_result else None,
                    "timestamp": task.verification_result.timestamp.isoformat() if task.verification_result else None
                }
            })

        if format == "json":
            return json.dumps(records, ensure_ascii=False, indent=2)
        else:
            # 其他格式可扩展
            return str(records)


def create_verification_tracker(data_dir: str = "./data/eia") -> SectionVerificationTracker:
    """创建审核追踪器实例"""
    return SectionVerificationTracker(data_dir=data_dir)