"""
智能表单系统 - Workflow-aware Custom Forms

功能：
1. 工作流感知的自定义表单
2. 表单与工作流集成
3. 智能数据验证
4. 表单模板管理
"""

import json
import uuid
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Callable
from enum import Enum


class WorkflowType(Enum):
    """工作流类型"""
    APPROVAL = "approval"              # 审批流程
    DATA_COLLECTION = "data_collection" # 数据收集
    TASK_ASSIGNMENT = "task_assignment" # 任务分配
    FEEDBACK = "feedback"               # 反馈收集
    GENERAL = "general"                 # 通用表单


class FieldType(Enum):
    """字段类型"""
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    DATETIME = "datetime"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    RADIO = "radio"
    CHECKBOX = "checkbox"
    TEXTAREA = "textarea"
    FILE = "file"
    IMAGE = "image"
    RATING = "rating"
    SLIDER = "slider"
    ADDRESS = "address"
    PHONE = "phone"
    EMAIL = "email"


class FieldValidation:
    """字段验证规则"""

    def __init__(self):
        self.rules: List[Dict[str, Any]] = []

    def required(self, message: str = "此字段必填"):
        self.rules.append({"type": "required", "message": message})
        return self

    def min_length(self, length: int, message: str = None):
        self.rules.append({
            "type": "min_length",
            "value": length,
            "message": message or f"最少{length}个字符"
        })
        return self

    def max_length(self, length: int, message: str = None):
        self.rules.append({
            "type": "max_length",
            "value": length,
            "message": message or f"最多{length}个字符"
        })
        return self

    def min_value(self, value: float, message: str = None):
        self.rules.append({
            "type": "min_value",
            "value": value,
            "message": message or f"最小值为{value}"
        })
        return self

    def max_value(self, value: float, message: str = None):
        self.rules.append({
            "type": "max_value",
            "value": value,
            "message": message or f"最大值为{value}"
        })
        return self

    def pattern(self, regex: str, message: str = "格式不正确"):
        self.rules.append({
            "type": "pattern",
            "value": regex,
            "message": message
        })
        return self

    def email(self, message: str = "请输入有效的邮箱地址"):
        self.rules.append({
            "type": "pattern",
            "value": r"^[\w\.-]+@[\w\.-]+\.\w+$",
            "message": message
        })
        return self

    def phone(self, message: str = "请输入有效的手机号码"):
        self.rules.append({
            "type": "pattern",
            "value": r"^1[3-9]\d{9}$",
            "message": message
        })
        return self

    def custom(self, validator: Callable, message: str = "验证失败"):
        self.rules.append({
            "type": "custom",
            "validator": validator,
            "message": message
        })
        return self


@dataclass
class FormField:
    """表单字段定义"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    label: str = ""
    field_type: str = FieldType.TEXT.value

    # 验证
    validation: List[Dict] = field(default_factory=list)
    required: bool = False
    default_value: Any = None

    # 选项（用于select/radio/checkbox）
    options: List[Dict[str, str]] = field(default_factory=list)

    # 布局
    width: int = 100  # 百分比
    visible: bool = True
    readonly: bool = False

    # 帮助
    placeholder: str = ""
    help_text: str = ""
    tooltip: str = ""

    # 工作流特殊字段
    workflow_field: bool = False  # 是否为工作流自动注入的字段
    workflow_injector: str = ""   # 注入器名称

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FormSection:
    """表单分区"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    fields: List[FormField] = field(default_factory=list)
    visible: bool = True
    collapsible: bool = False
    collapsed: bool = False
    order: int = 0


@dataclass
class WorkflowStep:
    """工作流步骤"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    step_type: str = "manual"  # manual/auto/condition

    # 处理人
    assignee_type: str = "role"  # role/user/department
    assignee_id: str = ""
    assignee_name: str = ""

    # 表单字段权限
    readonly_fields: List[str] = field(default_factory=list)
    hidden_fields: List[str] = field(default_factory=list)

    # 条件
    condition: Dict = field(default_factory=dict)

    # 动作
    actions: List[Dict] = field(default_factory=list)  # 批准/拒绝/退回等

    order: int = 0


@dataclass
class WorkflowDefinition:
    """工作流定义"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    workflow_type: str = WorkflowType.GENERAL.value

    steps: List[WorkflowStep] = field(default_factory=list)

    # 触发条件
    triggers: List[Dict] = field(default_factory=list)

    # 设置
    allow_withdraw: bool = True
    allow_transfer: bool = False
    notification_enabled: bool = True

    version: str = "1.0.0"


@dataclass
class FormTemplate:
    """表单模板"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""

    # 结构
    sections: List[FormSection] = field(default_factory=list)
    workflow: Optional[WorkflowDefinition] = None

    # 元数据
    version: str = "1.0.0"
    category: str = "general"
    tags: List[str] = field(default_factory=list)

    # 样式
    layout: str = "vertical"  # vertical/horizontal/grid
    theme: str = "default"

    # 创建者
    author_id: str = ""
    author_name: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # 使用统计
    use_count: int = 0
    submit_count: int = 0


@dataclass
class FormSubmission:
    """表单提交数据"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    template_id: str = ""

    # 提交的数据
    data: Dict[str, Any] = field(default_factory=dict)

    # 提交人
    submitter_id: str = ""
    submitter_name: str = ""
    submitted_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # 工作流状态
    workflow_instance_id: Optional[str] = None
    current_step_id: Optional[str] = None
    workflow_status: str = "draft"  # draft/submitted/in_progress/completed/rejected/withdrawn

    # 审批历史
    approval_history: List[Dict] = field(default_factory=list)

    # 备注
    comments: List[Dict] = field(default_factory=list)


class WorkflowAwareForm:
    """工作流感知的表单"""

    def __init__(self, form_config: FormTemplate, workflow_context: Dict = None):
        self.form_config = form_config
        self.workflow = workflow_context or self.infer_workflow(form_config)

        # 注入工作流字段
        self.inject_workflow_fields()

    def infer_workflow(self, form_config: FormTemplate) -> Dict:
        """根据表单内容推断工作流"""
        # 分析表单字段
        has_approval_fields = any(
            f.field_type in [FieldType.SELECT.value, FieldType.RADIO.value]
            and "审批" in (f.label or "")
            for section in form_config.sections
            for f in section.fields
        )

        has_amount_field = any(
            f.field_type == FieldType.NUMBER.value
            and "金额" in (f.label or "")
            for section in form_config.sections
            for f in section.fields
        )

        has_date_range = any(
            f.field_type in [FieldType.DATE.value, FieldType.DATETIME.value]
            for section in form_config.sections
            for f in section.fields
        )

        # 根据分析结果推断工作流类型
        if has_approval_fields or has_amount_field:
            workflow_type = WorkflowType.APPROVAL
        elif has_date_range:
            workflow_type = WorkflowType.TASK_ASSIGNMENT
        else:
            workflow_type = WorkflowType.DATA_COLLECTION

        return {
            "type": workflow_type.value,
            "steps": self.generate_workflow_steps(form_config, workflow_type),
            "triggers": self.detect_workflow_triggers(form_config)
        }

    def detect_workflow_triggers(self, form_config: FormTemplate) -> List[Dict]:
        """检测工作流触发条件"""
        triggers = []

        # 检查是否有金额字段（大额需审批）
        for section in form_config.sections:
            for field in section.fields:
                if field.field_type == FieldType.NUMBER.value and "金额" in (field.label or ""):
                    triggers.append({
                        "type": "amount_threshold",
                        "field_id": field.id,
                        "thresholds": [
                            {"amount": 1000, "require_approval_level": 1},
                            {"amount": 5000, "require_approval_level": 2},
                            {"amount": 10000, "require_approval_level": 3}
                        ]
                    })

        return triggers

    def generate_workflow_steps(
        self,
        form_config: FormTemplate,
        workflow_type: WorkflowType
    ) -> List[WorkflowStep]:
        """生成工作流步骤"""
        steps = []

        if workflow_type == WorkflowType.APPROVAL:
            # 审批流程
            steps.extend([
                WorkflowStep(
                    name="提交申请",
                    description="提交表单申请",
                    step_type="manual",
                    assignee_type="user",
                    actions=[
                        {"type": "submit", "label": "提交"},
                        {"type": "save_draft", "label": "保存草稿"}
                    ],
                    order=0
                ),
                WorkflowStep(
                    name="主管审批",
                    description="直接主管审批",
                    step_type="manual",
                    assignee_type="role",
                    assignee_id="manager",
                    assignee_name="部门主管",
                    actions=[
                        {"type": "approve", "label": "批准"},
                        {"type": "reject", "label": "拒绝"},
                        {"type": "return", "label": "退回"}
                    ],
                    order=1
                ),
                WorkflowStep(
                    name="完成",
                    description="流程结束",
                    step_type="auto",
                    order=2
                )
            ])

        elif workflow_type == WorkflowType.DATA_COLLECTION:
            # 数据收集流程
            steps.append(WorkflowStep(
                name="数据收集",
                description="收集并确认数据",
                step_type="manual",
                actions=[
                    {"type": "submit", "label": "提交"},
                    {"type": "save_draft", "label": "保存"}
                ],
                order=0
            ))

        return steps

    def inject_workflow_fields(self):
        """注入工作流特殊字段"""
        workflow_type = self.workflow.get("type")

        if workflow_type == WorkflowType.APPROVAL.value:
            self._inject_approval_fields()
        elif workflow_type == WorkflowType.TASK_ASSIGNMENT.value:
            self._inject_task_fields()
        elif workflow_type == WorkflowType.FEEDBACK.value:
            self._inject_feedback_fields()

    def _inject_approval_fields(self):
        """注入审批相关字段"""
        # 查找或创建审批区
        approval_section = None
        for section in self.form_config.sections:
            if section.title == "审批信息":
                approval_section = section
                break

        if not approval_section:
            approval_section = FormSection(
                title="审批信息",
                description="审批流程信息",
                order=999
            )
            self.form_config.sections.append(approval_section)

        # 审批人选择
        approval_section.fields.extend([
            FormField(
                name="approver_id",
                label="审批人",
                field_type=FieldType.SELECT.value,
                required=True,
                workflow_field=True,
                workflow_injector="approval",
                options=[
                    {"value": "", "label": "请选择审批人"}
                ]
            ),
            FormField(
                name="approval_comment",
                label="审批意见",
                field_type=FieldType.TEXTAREA.value,
                required=False,
                workflow_field=True,
                workflow_injector="approval"
            ),
            FormField(
                name="approval_level",
                label="审批级别",
                field_type=FieldType.RADIO.value,
                required=True,
                workflow_field=True,
                workflow_injector="approval",
                options=[
                    {"value": "1", "label": "一级审批"},
                    {"value": "2", "label": "二级审批"},
                    {"value": "3", "label": "三级审批"}
                ]
            )
        ])

        # 状态跟踪
        status_section = FormSection(
            title="状态跟踪",
            order=1000,
            collapsible=True,
            collapsed=True
        )
        status_section.fields.extend([
            FormField(
                name="current_status",
                label="当前状态",
                field_type=FieldType.TEXT.value,
                readonly=True,
                workflow_field=True,
                workflow_injector="status"
            ),
            FormField(
                name="submit_time",
                label="提交时间",
                field_type=FieldType.DATETIME.value,
                readonly=True,
                workflow_field=True,
                workflow_injector="status"
            ),
            FormField(
                name="approval_history",
                label="审批历史",
                field_type=FieldType.TEXTAREA.value,
                readonly=True,
                workflow_field=True,
                workflow_injector="status"
            )
        ])
        self.form_config.sections.append(status_section)

    def _inject_task_fields(self):
        """注入任务分配字段"""
        task_section = FormSection(
            title="任务信息",
            description="任务分配信息",
            order=999
        )
        task_section.fields.extend([
            FormField(
                name="assignee_id",
                label="负责人",
                field_type=FieldType.SELECT.value,
                required=True,
                workflow_field=True,
                workflow_injector="task"
            ),
            FormField(
                name="due_date",
                label="截止日期",
                field_type=FieldType.DATE.value,
                required=True,
                workflow_field=True,
                workflow_injector="task"
            ),
            FormField(
                name="priority",
                label="优先级",
                field_type=FieldType.RADIO.value,
                required=True,
                workflow_field=True,
                workflow_injector="task",
                options=[
                    {"value": "low", "label": "低"},
                    {"value": "normal", "label": "普通"},
                    {"value": "high", "label": "高"},
                    {"value": "urgent", "label": "紧急"}
                ]
            ),
            FormField(
                name="reminder",
                label="提醒设置",
                field_type=FieldType.CHECKBOX.value,
                workflow_field=True,
                workflow_injector="task"
            )
        ])
        self.form_config.sections.append(task_section)

    def _inject_feedback_fields(self):
        """注入反馈收集字段"""
        feedback_section = FormSection(
            title="反馈信息",
            description="反馈回复信息",
            order=999
        )
        feedback_section.fields.extend([
            FormField(
                name="feedback_type",
                label="反馈类型",
                field_type=FieldType.SELECT.value,
                required=True,
                workflow_field=True,
                workflow_injector="feedback",
                options=[
                    {"value": "suggestion", "label": "建议"},
                    {"value": "complaint", "label": "投诉"},
                    {"value": "inquiry", "label": "咨询"},
                    {"value": "other", "label": "其他"}
                ]
            ),
            FormField(
                name="contact_preference",
                label="回复方式",
                field_type=FieldType.RADIO.value,
                workflow_field=True,
                workflow_injector="feedback",
                options=[
                    {"value": "none", "label": "不需要回复"},
                    {"value": "email", "label": "邮件回复"},
                    {"value": "phone", "label": "电话回复"}
                ]
            ),
            FormField(
                name="rating",
                label="满意度评分",
                field_type=FieldType.RATING.value,
                workflow_field=True,
                workflow_injector="feedback"
            )
        ])
        self.form_config.sections.append(feedback_section)


class FormValidator:
    """表单验证器"""

    def __init__(self, form_template: FormTemplate):
        self.form_template = form_template

    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """验证表单数据"""
        errors = {}
        warnings = []

        # 收集所有字段
        all_fields = {}
        for section in self.form_template.sections:
            for field in section.fields:
                if field.visible:
                    all_fields[field.id] = field

        # 验证每个字段
        for field_id, field in all_fields.items():
            value = data.get(field_id)

            # 必填验证
            if field.required and (value is None or value == ""):
                errors[field_id] = f"{field.label}为必填项"
                continue

            # 类型验证
            if value is not None and value != "":
                type_error = self._validate_type(field, value)
                if type_error:
                    errors[field_id] = type_error

                # 规则验证
                for rule in field.validation:
                    rule_error = self._validate_rule(field, value, rule)
                    if rule_error:
                        if field_id not in errors:
                            errors[field_id] = []
                        if isinstance(errors[field_id], str):
                            errors[field_id] = [errors[field_id]]
                        errors[field_id].append(rule_error)

        # 工作流特定验证
        workflow_warnings = self._validate_workflow_rules(data)
        warnings.extend(workflow_warnings)

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }

    def _validate_type(self, field: FormField, value: Any) -> Optional[str]:
        """验证字段类型"""
        if field.field_type == FieldType.NUMBER.value:
            try:
                float(value)
            except:
                return f"{field.label}必须为数字"

        elif field.field_type == FieldType.EMAIL.value:
            import re
            if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", str(value)):
                return f"{field.label}必须为有效邮箱"

        elif field.field_type == FieldType.PHONE.value:
            import re
            if not re.match(r"^1[3-9]\d{9}$", str(value)):
                return f"{field.label}必须为有效手机号"

        return None

    def _validate_rule(self, field: FormField, value: Any, rule: Dict) -> Optional[str]:
        """验证规则"""
        rule_type = rule.get("type")

        if rule_type == "min_length":
            if len(str(value)) < rule["value"]:
                return rule["message"]

        elif rule_type == "max_length":
            if len(str(value)) > rule["value"]:
                return rule["message"]

        elif rule_type == "min_value":
            if float(value) < rule["value"]:
                return rule["message"]

        elif rule_type == "max_value":
            if float(value) > rule["value"]:
                return rule["message"]

        elif rule_type == "pattern":
            import re
            if not re.match(rule["value"], str(value)):
                return rule["message"]

        elif rule_type == "custom":
            validator = rule.get("validator")
            if callable(validator) and not validator(value):
                return rule["message"]

        return None

    def _validate_workflow_rules(self, data: Dict[str, Any]) -> List[str]:
        """验证工作流规则"""
        warnings = []

        # 检查金额阈值
        for section in self.form_template.sections:
            for field in section.fields:
                if field.field_type == FieldType.NUMBER.value and "金额" in (field.label or ""):
                    amount = float(data.get(field.id, 0))
                    if amount >= 10000:
                        warnings.append(f"金额超过10000元，需要高级审批")

        return warnings


class SmartFormManager:
    """智能表单管理器"""

    def __init__(self, store_path: str = None):
        from pathlib import Path
        if store_path is None:
            store_path = Path("~/.hermes/smart_form").expanduser()

        self.store_path = Path(store_path)
        self.store_path.mkdir(parents=True, exist_ok=True)

        # 索引文件
        self._templates_index = self.store_path / "templates.json"
        self._submissions_dir = self.store_path / "submissions"
        self._submissions_dir.mkdir(exist_ok=True)

        self._load_indexes()

    def _load_indexes(self):
        """加载索引"""
        if self._templates_index.exists():
            with open(self._templates_index, "r", encoding="utf-8") as f:
                self._templates: Dict[str, dict] = json.load(f)
        else:
            self._templates: Dict[str, dict] = {}

    def _save_templates_index(self):
        """保存模板索引"""
        with open(self._templates_index, "w", encoding="utf-8") as f:
            json.dump(self._templates, f, ensure_ascii=False, indent=2)

    # ============ 模板管理 ============

    def create_template(self, template: FormTemplate) -> str:
        """创建表单模板"""
        # 确保有工作流
        if not template.workflow:
            workflow_form = WorkflowAwareForm(template)
            template.workflow = WorkflowDefinition(
                name=f"{template.name}工作流",
                workflow_type=workflow_form.workflow["type"],
                steps=workflow_form.workflow.get("steps", [])
            )

        # 保存模板
        template_file = self.store_path / f"{template.id}.json"
        with open(template_file, "w", encoding="utf-8") as f:
            json.dump(asdict(template), f, ensure_ascii=False, indent=2)

        # 更新索引
        self._templates[template.id] = {
            "name": template.name,
            "category": template.category,
            "version": template.version,
            "use_count": template.use_count
        }
        self._save_templates_index()

        return template.id

    def get_template(self, template_id: str) -> Optional[FormTemplate]:
        """获取模板"""
        template_file = self.store_path / f"{template_id}.json"
        if not template_file.exists():
            return None

        with open(template_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return FormTemplate(**data)

    def update_template(self, template: FormTemplate) -> bool:
        """更新模板"""
        template.updated_at = datetime.now().isoformat()
        self.create_template(template)  # 覆盖保存
        return True

    def list_templates(
        self,
        category: str = None,
        search: str = None
    ) -> List[FormTemplate]:
        """列出模板"""
        templates = []

        for template_id in self._templates.keys():
            template = self.get_template(template_id)
            if not template:
                continue

            if category and template.category != category:
                continue

            if search and search.lower() not in template.name.lower():
                continue

            templates.append(template)

        return templates

    # ============ 表单提交 ============

    def create_submission(self, submission: FormSubmission) -> str:
        """创建表单提交"""
        # 验证表单
        template = self.get_template(submission.template_id)
        if not template:
            raise ValueError("表单模板不存在")

        validator = FormValidator(template)
        result = validator.validate(submission.data)

        if not result["valid"]:
            raise ValueError(f"表单验证失败: {result['errors']}")

        # 保存提交
        submission_file = self._submissions_dir / f"{submission.id}.json"
        with open(submission_file, "w", encoding="utf-8") as f:
            json.dump(asdict(submission), f, ensure_ascii=False, indent=2)

        # 更新模板使用统计
        template.use_count += 1
        template.submit_count += 1
        self.update_template(template)

        return submission.id

    def get_submission(self, submission_id: str) -> Optional[FormSubmission]:
        """获取提交"""
        submission_file = self._submissions_dir / f"{submission_id}.json"
        if not submission_file.exists():
            return None

        with open(submission_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return FormSubmission(**data)

    def list_submissions(
        self,
        template_id: str = None,
        submitter_id: str = None,
        status: str = None
    ) -> List[FormSubmission]:
        """列出提交"""
        submissions = []

        for file in self._submissions_dir.glob("*.json"):
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)

            submission = FormSubmission(**data)

            if template_id and submission.template_id != template_id:
                continue

            if submitter_id and submission.submitter_id != submitter_id:
                continue

            if status and submission.workflow_status != status:
                continue

            submissions.append(submission)

        return sorted(submissions, key=lambda s: s.submitted_at, reverse=True)

    # ============ 工作流操作 ============

    def submit_for_approval(self, submission_id: str) -> bool:
        """提交审批"""
        submission = self.get_submission(submission_id)
        if not submission:
            return False

        submission.workflow_status = "submitted"
        submission.submitted_at = datetime.now().isoformat()

        # 保存
        submission_file = self._submissions_dir / f"{submission_id}.json"
        with open(submission_file, "w", encoding="utf-8") as f:
            json.dump(asdict(submission), f, ensure_ascii=False, indent=2)

        return True

    def approve_step(self, submission_id: str, step_id: str, approver_id: str, comment: str = "") -> bool:
        """审批步骤"""
        submission = self.get_submission(submission_id)
        if not submission:
            return False

        # 添加审批历史
        submission.approval_history.append({
            "step_id": step_id,
            "action": "approve",
            "approver_id": approver_id,
            "comment": comment,
            "timestamp": datetime.now().isoformat()
        })

        # 更新状态
        submission.workflow_status = "in_progress"

        # 保存
        submission_file = self._submissions_dir / f"{submission_id}.json"
        with open(submission_file, "w", encoding="utf-8") as f:
            json.dump(asdict(submission), f, ensure_ascii=False, indent=2)

        return True

    def reject_step(self, submission_id: str, step_id: str, rejector_id: str, reason: str) -> bool:
        """拒绝步骤"""
        submission = self.get_submission(submission_id)
        if not submission:
            return False

        submission.approval_history.append({
            "step_id": step_id,
            "action": "reject",
            "approver_id": rejector_id,
            "comment": reason,
            "timestamp": datetime.now().isoformat()
        })

        submission.workflow_status = "rejected"

        submission_file = self._submissions_dir / f"{submission_id}.json"
        with open(submission_file, "w", encoding="utf-8") as f:
            json.dump(asdict(submission), f, ensure_ascii=False, indent=2)

        return True


# 全局实例
_form_manager: Optional[SmartFormManager] = None


def get_form_manager() -> SmartFormManager:
    """获取表单管理器"""
    global _form_manager
    if _form_manager is None:
        _form_manager = SmartFormManager()
    return _form_manager