"""
工作流自定义消息通知系统

功能：
1. 多渠道消息通知
2. 自定义通知模板
3. 通知规则引擎
4. 通知历史记录
"""

import json
import uuid
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from pathlib import Path


class NotificationChannel(Enum):
    """通知渠道"""
    IN_APP = "in_app"           # 应用内通知
    EMAIL = "email"             # 邮件通知
    SMS = "sms"                # 短信通知
    WECHAT = "wechat"          # 微信通知
    PUSH = "push"              # 推送通知
    WEBHOOK = "webhook"        # Webhook回调


class NotificationPriority(Enum):
    """通知优先级"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationStatus(Enum):
    """通知状态"""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    READ = "read"
    CLICKED = "clicked"


@dataclass
class NotificationTemplate:
    """通知模板"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""

    # 模板内容
    title_template: str = ""   # 标题模板
    content_template: str = "" # 内容模板
    variables: List[str] = field(default_factory=list)  # 可用变量

    # 渠道设置
    default_channel: str = NotificationChannel.IN_APP.value
    enabled_channels: List[str] = field(default_factory=lambda: [NotificationChannel.IN_APP.value])

    # 样式
    icon: str = "🔔"
    color: str = "#007acc"

    # 规则
    batch_enabled: bool = True  # 是否允许批量通知
    deduplication: bool = True  # 去重

    # 状态
    is_active: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def render(self, variables: Dict[str, Any]) -> tuple:
        """渲染模板"""
        title = self.title_template
        content = self.content_template

        for key, value in variables.items():
            placeholder = f"{{{key}}}"
            title = title.replace(placeholder, str(value))
            content = content.replace(placeholder, str(value))

        return title, content


@dataclass
class NotificationRule:
    """通知规则"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""

    # 触发条件
    event_type: str = ""  # 事件类型
    conditions: List[Dict] = field(default_factory=list)  # 触发条件

    # 通知配置
    template_id: str = ""
    channel: str = NotificationChannel.IN_APP.value
    priority: str = NotificationPriority.NORMAL.value

    # 目标用户
    target_type: str = "assignee"  # assignee/initiator/role/expression
    target_expression: str = ""

    # 过滤条件
    filter_expression: str = ""

    # 状态
    is_active: bool = True

    def evaluate_conditions(self, context: Dict[str, Any]) -> bool:
        """评估条件是否满足"""
        for condition in self.conditions:
            field = condition.get("field", "")
            operator = condition.get("operator", "eq")
            value = condition.get("value", "")

            actual_value = context.get(field)

            if operator == "eq":
                if actual_value != value:
                    return False
            elif operator == "ne":
                if actual_value == value:
                    return False
            elif operator == "gt":
                if not (actual_value and actual_value > value):
                    return False
            elif operator == "lt":
                if not (actual_value and actual_value < value):
                    return False
            elif operator == "contains":
                if value not in str(actual_value):
                    return False
            elif operator == "in":
                if actual_value not in value:
                    return False

        return True


@dataclass
class Notification:
    """通知"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    template_id: str = ""
    template_name: str = ""

    # 内容
    title: str = ""
    content: str = ""
    priority: str = NotificationPriority.NORMAL.value

    # 目标
    user_id: str = ""
    user_name: str = ""
    channel: str = NotificationChannel.IN_APP.value

    # 来源
    source_type: str = ""  # workflow/task/form
    source_id: str = ""
    source_name: str = ""

    # 上下文数据
    context: Dict[str, Any] = field(default_factory=dict)

    # 状态
    status: str = NotificationStatus.PENDING.value
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    sent_at: Optional[str] = None
    read_at: Optional[str] = None
    clicked_at: Optional[str] = None

    # 错误信息
    error_message: Optional[str] = None
    retry_count: int = 0


@dataclass
class NotificationPreferences:
    """用户通知偏好"""
    user_id: str = ""

    # 各渠道开关
    channels_enabled: Dict[str, bool] = field(default_factory=lambda: {
        NotificationChannel.IN_APP.value: True,
        NotificationChannel.EMAIL.value: True,
        NotificationChannel.SMS.value: False,
        NotificationChannel.WECHAT.value: False,
        NotificationChannel.PUSH.value: True
    })

    # 免打扰设置
    do_not_disturb: bool = False
    do_not_disturb_start: str = "22:00"
    do_not_disturb_end: str = "08:00"

    # 频率限制
    batch_notifications: bool = True
    batch_interval_minutes: int = 30

    # 过滤设置
    filter_by_priority: Dict[str, bool] = field(default_factory=lambda: {
        NotificationPriority.LOW.value: False,
        NotificationPriority.NORMAL.value: True,
        NotificationPriority.HIGH.value: True,
        NotificationPriority.URGENT.value: True
    })

    # 关键词过滤
    keyword_blacklist: List[str] = field(default_factory=list)


class NotificationTemplateManager:
    """通知模板管理器"""

    # 内置模板
    BUILTIN_TEMPLATES = {
        "workflow_started": {
            "name": "工作流启动",
            "title_template": "🎬 工作流已启动",
            "content_template": "您发起的工作流「{workflow_name}」已开始执行",
            "variables": ["workflow_name", "initiator_name", "start_time"]
        },
        "workflow_completed": {
            "name": "工作流完成",
            "title_template": "✅ 工作流已完成",
            "content_template": "工作流「{workflow_name}」已顺利完成",
            "variables": ["workflow_name", "initiator_name", "completed_at"]
        },
        "task_assigned": {
            "name": "任务分配",
            "title_template": "📋 新任务待处理",
            "content_template": "您有一个新任务：{task_name}，来自工作流「{workflow_name}」",
            "variables": ["task_name", "workflow_name", "assignee_name", "due_time"]
        },
        "task_reminder": {
            "name": "任务提醒",
            "title_template": "⏰ 任务待处理提醒",
            "content_template": "任务「{task_name}」即将到期，请及时处理",
            "variables": ["task_name", "due_time", "urgency"]
        },
        "approval_needed": {
            "name": "待审批",
            "title_template": "✅ 审批待处理",
            "content_template": "您有一个待审批项：{item_name}，申请人：{applicant_name}",
            "variables": ["item_name", "applicant_name", "amount"]
        },
        "approval_result": {
            "name": "审批结果",
            "title_template": "📨 审批结果通知",
            "content_template": "您的{item_name}申请已被{result}，审批人：{approver_name}",
            "variables": ["item_name", "result", "approver_name", "comment"]
        },
        "form_submitted": {
            "name": "表单提交",
            "title_template": "📝 新表单提交",
            "content_template": "收到来自{submitter_name}的表单：{form_name}",
            "variables": ["form_name", "submitter_name", "submit_time"]
        },
        "update_available": {
            "name": "系统更新",
            "title_template": "🆕 新版本可用",
            "content_template": "系统已更新到v{version}，{update_summary}",
            "variables": ["version", "update_summary", "new_features"]
        },
        "vote_started": {
            "name": "投票开始",
            "title_template": "🗳️ 投票已开始",
            "content_template": "模板「{template_name}」的删除投票已开始，请参与投票",
            "variables": ["template_name", "initiator_name", "reason"]
        },
        "vote_result": {
            "name": "投票结果",
            "title_template": "📊 投票已结束",
            "content_template": "模板「{template_name}」的投票已结束，结果：{result}",
            "variables": ["template_name", "result", "vote_count"]
        }
    }

    def __init__(self, store_path: str = None):
        if store_path is None:
            store_path = Path("~/.hermes/notifications/templates").expanduser()

        self.store_path = Path(store_path)
        self.store_path.mkdir(parents=True, exist_ok=True)

        self._templates_file = self.store_path / "templates.json"
        self._templates: Dict[str, NotificationTemplate] = {}
        self._load_templates()

    def _load_templates(self):
        """加载模板"""
        if self._templates_file.exists():
            with open(self._templates_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for t in data:
                    self._templates[t["id"]] = NotificationTemplate(**t)
        else:
            # 加载内置模板
            self._load_builtin_templates()

    def _load_builtin_templates(self):
        """加载内置模板"""
        for template_id, template_data in self.BUILTIN_TEMPLATES.items():
            template = NotificationTemplate(
                id=template_id,
                name=template_data["name"],
                title_template=template_data["title_template"],
                content_template=template_data["content_template"],
                variables=template_data["variables"]
            )
            self._templates[template_id] = template
        self._save_templates()

    def _save_templates(self):
        """保存模板"""
        with open(self._templates_file, "w", encoding="utf-8") as f:
            data = [asdict(t) for t in self._templates.values()]
            json.dump(data, f, ensure_ascii=False, indent=2)

    def create_template(
        self,
        name: str,
        title_template: str,
        content_template: str,
        variables: List[str] = None,
        channel: str = NotificationChannel.IN_APP.value
    ) -> str:
        """创建模板"""
        template = NotificationTemplate(
            name=name,
            title_template=title_template,
            content_template=content_template,
            variables=variables or [],
            default_channel=channel
        )
        self._templates[template.id] = template
        self._save_templates()
        return template.id

    def get_template(self, template_id: str) -> Optional[NotificationTemplate]:
        """获取模板"""
        return self._templates.get(template_id)

    def list_templates(self) -> List[NotificationTemplate]:
        """列出所有模板"""
        return list(self._templates.values())


class WorkflowNotificationService:
    """工作流通知服务"""

    def __init__(
        self,
        template_manager: NotificationTemplateManager = None,
        store_path: str = None
    ):
        self.template_manager = template_manager or NotificationTemplateManager()

        if store_path is None:
            store_path = Path("~/.hermes/notifications").expanduser()

        self.store_path = Path(store_path)
        self.store_path.mkdir(parents=True, exist_ok=True)

        self._notifications_file = self.store_path / "notifications.json"
        self._rules_file = self.store_path / "rules.json"
        self._preferences_file = self.store_path / "preferences.json"

        self._notifications: List[Notification] = []
        self._rules: Dict[str, NotificationRule] = {}
        self._preferences: Dict[str, NotificationPreferences] = {}

        self._load_data()

        # 通知处理器
        self._handlers: Dict[str, Callable] = {
            NotificationChannel.IN_APP.value: self._send_in_app,
            NotificationChannel.EMAIL.value: self._send_email,
            NotificationChannel.SMS.value: self._send_sms,
        }

    def _load_data(self):
        """加载数据"""
        if self._notifications_file.exists():
            with open(self._notifications_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._notifications = [Notification(**n) for n in data]

        if self._rules_file.exists():
            with open(self._rules_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._rules = {r["id"]: NotificationRule(**r) for r in data}

        if self._preferences_file.exists():
            with open(self._preferences_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._preferences = {p["user_id"]: NotificationPreferences(**p) for p in data}

    def _save_notifications(self):
        """保存通知"""
        with open(self._notifications_file, "w", encoding="utf-8") as f:
            data = [asdict(n) for n in self._notifications]
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _save_rules(self):
        """保存规则"""
        with open(self._rules_file, "w", encoding="utf-8") as f:
            data = [asdict(r) for r in self._rules.values()]
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _save_preferences(self):
        """保存偏好"""
        with open(self._preferences_file, "w", encoding="utf-8") as f:
            data = [asdict(p) for p in self._preferences.values()]
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ============ 通知发送 ============

    async def send_notification(
        self,
        template_id: str,
        user_id: str,
        user_name: str,
        variables: Dict[str, Any],
        channel: str = NotificationChannel.IN_APP.value,
        priority: str = NotificationPriority.NORMAL.value,
        source_type: str = "",
        source_id: str = "",
        source_name: str = ""
    ) -> str:
        """发送通知"""
        template = self.template_manager.get_template(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")

        # 渲染内容
        title, content = template.render(variables)

        # 创建通知
        notification = Notification(
            template_id=template_id,
            template_name=template.name,
            title=title,
            content=content,
            priority=priority,
            user_id=user_id,
            user_name=user_name,
            channel=channel,
            source_type=source_type,
            source_id=source_id,
            source_name=source_name,
            context=variables
        )

        # 发送
        await self._send(notification)

        # 保存
        self._notifications.append(notification)
        self._save_notifications()

        return notification.id

    async def _send(self, notification: Notification):
        """发送通知"""
        handler = self._handlers.get(notification.channel)
        if handler:
            try:
                await handler(notification)
                notification.status = NotificationStatus.SENT.value
                notification.sent_at = datetime.now().isoformat()
            except Exception as e:
                notification.status = NotificationStatus.FAILED.value
                notification.error_message = str(e)
        else:
            notification.status = NotificationStatus.FAILED.value
            notification.error_message = f"No handler for channel: {notification.channel}"

    async def _send_in_app(self, notification: Notification):
        """发送应用内通知"""
        # 实际实现会调用通知面板
        print(f"[IN_APP] {notification.user_name}: {notification.title}")

    async def _send_email(self, notification: Notification):
        """发送邮件通知"""
        # 实际实现会调用邮件服务
        print(f"[EMAIL] {notification.user_name}: {notification.title}")
        print(f"  Content: {notification.content}")

    async def _send_sms(self, notification: Notification):
        """发送短信通知"""
        print(f"[SMS] {notification.user_id}: {notification.title}")

    # ============ 工作流事件通知 ============

    async def notify_workflow_started(
        self,
        workflow_name: str,
        initiator_id: str,
        initiator_name: str
    ):
        """通知工作流启动"""
        await self.send_notification(
            template_id="workflow_started",
            user_id=initiator_id,
            user_name=initiator_name,
            variables={
                "workflow_name": workflow_name,
                "initiator_name": initiator_name,
                "start_time": datetime.now().strftime("%Y-%m-%d %H:%M")
            },
            source_type="workflow",
            source_name=workflow_name
        )

    async def notify_workflow_completed(
        self,
        workflow_name: str,
        initiator_id: str,
        initiator_name: str
    ):
        """通知工作流完成"""
        await self.send_notification(
            template_id="workflow_completed",
            user_id=initiator_id,
            user_name=initiator_name,
            variables={
                "workflow_name": workflow_name,
                "initiator_name": initiator_name,
                "completed_at": datetime.now().strftime("%Y-%m-%d %H:%M")
            },
            source_type="workflow",
            source_name=workflow_name
        )

    async def notify_task_assigned(
        self,
        task_name: str,
        workflow_name: str,
        assignee_id: str,
        assignee_name: str,
        due_time: str = None
    ):
        """通知任务分配"""
        variables = {
            "task_name": task_name,
            "workflow_name": workflow_name,
            "assignee_name": assignee_name
        }
        if due_time:
            variables["due_time"] = due_time

        await self.send_notification(
            template_id="task_assigned",
            user_id=assignee_id,
            user_name=assignee_name,
            variables=variables,
            priority=NotificationPriority.HIGH.value,
            source_type="task",
            source_name=task_name
        )

    async def notify_approval_needed(
        self,
        item_name: str,
        applicant_name: str,
        approver_id: str,
        approver_name: str,
        amount: float = None
    ):
        """通知待审批"""
        variables = {
            "item_name": item_name,
            "applicant_name": applicant_name,
            "approver_name": approver_name
        }
        if amount:
            variables["amount"] = f"¥{amount:,.2f}"

        await self.send_notification(
            template_id="approval_needed",
            user_id=approver_id,
            user_name=approver_name,
            variables=variables,
            priority=NotificationPriority.HIGH.value,
            source_type="approval",
            source_name=item_name
        )

    async def notify_approval_result(
        self,
        item_name: str,
        result: str,  # 批准/拒绝
        approver_name: str,
        applicant_id: str,
        applicant_name: str,
        comment: str = None
    ):
        """通知审批结果"""
        variables = {
            "item_name": item_name,
            "result": result,
            "approver_name": approver_name
        }
        if comment:
            variables["comment"] = comment

        await self.send_notification(
            template_id="approval_result",
            user_id=applicant_id,
            user_name=applicant_name,
            variables=variables,
            source_type="approval",
            source_name=item_name
        )

    async def notify_task_reminder(
        self,
        task_name: str,
        assignee_id: str,
        assignee_name: str,
        due_time: str,
        urgency: str = "normal"
    ):
        """发送任务提醒"""
        priority = (NotificationPriority.URGENT.value
                    if urgency == "high"
                    else NotificationPriority.NORMAL.value)

        await self.send_notification(
            template_id="task_reminder",
            user_id=assignee_id,
            user_name=assignee_name,
            variables={
                "task_name": task_name,
                "due_time": due_time,
                "urgency": urgency
            },
            priority=priority,
            source_type="task",
            source_name=task_name
        )

    # ============ 通知查询 ============

    def get_user_notifications(
        self,
        user_id: str,
        unread_only: bool = False,
        limit: int = 50
    ) -> List[Notification]:
        """获取用户通知"""
        notifications = [n for n in self._notifications if n.user_id == user_id]

        if unread_only:
            notifications = [n for n in notifications
                           if n.status != NotificationStatus.READ.value]

        notifications.sort(key=lambda n: n.created_at, reverse=True)
        return notifications[:limit]

    def mark_as_read(self, notification_id: str) -> bool:
        """标记为已读"""
        for n in self._notifications:
            if n.id == notification_id:
                n.status = NotificationStatus.READ.value
                n.read_at = datetime.now().isoformat()
                self._save_notifications()
                return True
        return False

    def mark_all_as_read(self, user_id: str):
        """标记所有为已读"""
        for n in self._notifications:
            if n.user_id == user_id and n.status != NotificationStatus.READ.value:
                n.status = NotificationStatus.READ.value
                n.read_at = datetime.now().isoformat()
        self._save_notifications()

    def get_unread_count(self, user_id: str) -> int:
        """获取未读数量"""
        return sum(
            1 for n in self._notifications
            if n.user_id == user_id and n.status != NotificationStatus.READ.value
        )

    # ============ 用户偏好 ============

    def get_user_preferences(self, user_id: str) -> NotificationPreferences:
        """获取用户通知偏好"""
        if user_id not in self._preferences:
            self._preferences[user_id] = NotificationPreferences(user_id=user_id)
        return self._preferences[user_id]

    def update_user_preferences(self, preferences: NotificationPreferences):
        """更新用户偏好"""
        self._preferences[preferences.user_id] = preferences
        self._save_preferences()

    # ============ 通知规则 ============

    def create_rule(
        self,
        name: str,
        event_type: str,
        template_id: str,
        conditions: List[Dict] = None
    ) -> str:
        """创建通知规则"""
        rule = NotificationRule(
            name=name,
            event_type=event_type,
            template_id=template_id,
            conditions=conditions or []
        )
        self._rules[rule.id] = rule
        self._save_rules()
        return rule.id

    def get_rule(self, rule_id: str) -> Optional[NotificationRule]:
        """获取规则"""
        return self._rules.get(rule_id)

    def list_rules(self, event_type: str = None) -> List[NotificationRule]:
        """列出规则"""
        rules = list(self._rules.values())
        if event_type:
            rules = [r for r in rules if r.event_type == event_type]
        return rules


# ============ 全局实例 ============

_notification_service: Optional[WorkflowNotificationService] = None
_template_manager: Optional[NotificationTemplateManager] = None


def get_notification_service() -> WorkflowNotificationService:
    """获取通知服务"""
    global _notification_service
    if _notification_service is None:
        _notification_service = WorkflowNotificationService()
    return _notification_service


def get_template_manager() -> NotificationTemplateManager:
    """获取模板管理器"""
    global _template_manager
    if _template_manager is None:
        _template_manager = NotificationTemplateManager()
    return _template_manager