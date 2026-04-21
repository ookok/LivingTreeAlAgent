"""
智能路由引擎

根据任务类型和数据质量自动路由到合适的处理引擎。

核心功能：
1. 任务意图识别
2. 路由规则管理
3. 置信度阈值控制
4. 人机协同调度
"""

import json
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from datetime import datetime


# ==================== 数据模型 ====================

class TaskType(Enum):
    """任务类型"""
    # 文档生成
    DOCUMENT_GENERATION = "document_generation"
    DOCUMENT_REVIEW = "document_review"
    DOCUMENT_CONVERSION = "document_conversion"

    # 申报执行
    DECLARATION_EXECUTE = "declaration_execute"
    DECLARATION_STATUS_CHECK = "declaration_status_check"
    DECLARATION_DOCUMENT = "declaration_document"

    # 数据采集
    DATA_COLLECTION = "data_collection"
    DATA_VALIDATION = "data_validation"
    DATA_SYNC = "data_sync"

    # 合规检查
    COMPLIANCE_CHECK = "compliance_check"
    RISK_ASSESSMENT = "risk_assessment"

    # 政府网站
    GOV_LOGIN = "gov_login"
    GOV_FORM_FILL = "gov_form_fill"
    GOV_FILE_UPLOAD = "gov_file_upload"


class ExecutionMode(Enum):
    """执行模式"""
    AUTO_FULL = "auto_full"              # 全自动（置信度>90%）
    AUTO_PARTIAL = "auto_partial"         # 半自动（AI执行，人工复核）
    MANUAL = "manual"                      # 人工处理
    HYBRID = "hybrid"                      # 混合（AI+人工协同）


class RoutingDecision(Enum):
    """路由决策"""
    ACCEPT_AUTO = "accept_auto"           # 接受自动处理
    NEED_HUMAN_REVIEW = "need_human_review"  # 需要人工复核
    NEED_MORE_DATA = "need_more_data"      # 需要补充数据
    REJECT = "reject"                     # 拒绝/无法处理


@dataclass
class TaskIntent:
    """任务意图"""
    intent_id: str
    task_type: TaskType
    confidence: float                      # 0-1
    entities: Dict[str, Any] = field(default_factory=dict)  # 识别的实体
    context: Dict = field(default_factory=dict)
    required_data_fields: List[str] = field(default_factory=list)
    estimated_complexity: str = "medium"    # low/medium/high

    # 约束条件
    deadline: Optional[datetime] = None
    priority: int = 5                      # 1-10
    prefer_manual: bool = False


@dataclass
class RoutingRule:
    """路由规则"""
    rule_id: str
    name: str
    description: str = ""

    # 匹配条件
    task_types: List[TaskType] = field(default_factory=list)  # 任务类型
    condition_func: str = ""                                 # 条件函数

    # 路由目标
    target_engine: str = ""                                  # 目标引擎
    target_plugin: str = ""                                   # 目标插件
    execution_mode: ExecutionMode = ExecutionMode.AUTO_PARTIAL

    # 阈值
    confidence_threshold: float = 0.9
    data_quality_threshold: float = 0.8

    # 规则属性
    priority: int = 0                                          # 优先级（数字越大优先级越高）
    enabled: bool = True
    fallback_rule: str = ""                                   # 备用规则ID


@dataclass
class RoutingResult:
    """路由结果"""
    decision: RoutingDecision
    task_type: TaskType
    execution_mode: ExecutionMode

    # 路由信息
    target_engine: str = ""
    target_plugin: str = ""
    confidence_threshold: float = 0.9

    # 处理建议
    suggestions: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    required_verifications: List[str] = field(default_factory=list)

    # 详细原因
    reason: str = ""
    routing_path: List[str] = field(default_factory=list)  # 路由路径

    # 置信度
    overall_confidence: float = 0.0
    data_quality_score: float = 0.0


@dataclass
class HumanReviewTask:
    """人工复核任务"""
    task_id: str
    intent: TaskIntent
    routing_result: RoutingResult

    # 待复核内容
    auto_filled_data: Dict = field(default_factory=list)
    ai_suggestions: List[Dict] = field(default_factory=list)

    # 复核状态
    status: str = "pending"             # pending/completed/rejected
    assigned_to: str = ""
    assigned_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # 复核结果
    review_result: str = ""
    corrections: Dict = field(default_factory=dict)
    notes: str = ""


# ==================== 内置路由规则 ====================

BUILTIN_ROUTING_RULES = [
    {
        "name": "高置信度文档生成",
        "task_type": "DOCUMENT_GENERATION",
        "condition": "confidence >= 0.9 and data_quality >= 0.9",
        "execution_mode": "AUTO_FULL",
        "target_engine": "document_generator",
        "confidence_threshold": 0.9
    },
    {
        "name": "中置信度文档生成",
        "task_type": "DOCUMENT_GENERATION",
        "condition": "0.6 <= confidence < 0.9 or 0.7 <= data_quality < 0.9",
        "execution_mode": "AUTO_PARTIAL",
        "target_engine": "document_generator",
        "confidence_threshold": 0.7
    },
    {
        "name": "排污许可证申报",
        "task_type": "DECLARATION_EXECUTE",
        "condition": "task_type == 'pollution_permit'",
        "execution_mode": "HYBRID",
        "target_engine": "declaration_pipeline",
        "target_plugin": "env_pollution_permit",
        "confidence_threshold": 0.85
    },
    {
        "name": "营业执照申报",
        "task_type": "DECLARATION_EXECUTE",
        "condition": "task_type == 'business_license'",
        "execution_mode": "AUTO_PARTIAL",
        "target_engine": "declaration_pipeline",
        "target_plugin": "env_business_license",
        "confidence_threshold": 0.8
    },
    {
        "name": "政府网站表单填写",
        "task_type": "GOV_FORM_FILL",
        "condition": "True",
        "execution_mode": "HYBRID",
        "target_engine": "gov_site_adapter",
        "confidence_threshold": 0.85
    },
    {
        "name": "数据验证",
        "task_type": "DATA_VALIDATION",
        "condition": "True",
        "execution_mode": "AUTO_FULL",
        "target_engine": "validation_engine",
        "confidence_threshold": 0.95
    },
    {
        "name": "合规检查",
        "task_type": "COMPLIANCE_CHECK",
        "condition": "True",
        "execution_mode": "AUTO_PARTIAL",
        "target_engine": "compliance_graph",
        "confidence_threshold": 0.8
    }
]


# ==================== 智能路由引擎 ====================

class IntelligentRouter:
    """
    智能路由引擎

    核心功能：
    1. 任务意图识别
    2. 路由规则匹配
    3. 置信度阈值控制
    4. 人机协同调度
    """

    # 置信度阈值常量
    AUTO_FULL_THRESHOLD = 0.9      # 全自动阈值
    AUTO_PARTIAL_THRESHOLD = 0.6   # 半自动阈值
    HUMAN_REVIEW_THRESHOLD = 0.4   # 需要人工阈值

    def __init__(self):
        self._rules: Dict[str, RoutingRule] = {}
        self._intent_recognizers: List[Callable] = []  # 意图识别器列表
        self._review_queue: List[HumanReviewTask] = [] # 待复核任务队列

        # 知识库引用
        self._profile_service = None
        self._plugin_registry = None

        # 加载内置规则
        self._load_builtin_rules()

    def _load_builtin_rules(self):
        """加载内置路由规则"""
        for i, rule_config in enumerate(BUILTIN_ROUTING_RULES):
            rule = RoutingRule(
                rule_id=f"builtin_rule_{i}",
                name=rule_config["name"],
                task_types=[TaskType(t) for t in [rule_config["task_type"]]],
                condition_func=rule_config["condition"],
                target_engine=rule_config["target_engine"],
                target_plugin=rule_config.get("target_plugin", ""),
                execution_mode=ExecutionMode[rule_config["execution_mode"]],
                confidence_threshold=rule_config.get("confidence_threshold", 0.8),
                priority=i
            )
            self._rules[rule.rule_id] = rule

    def set_profile_service(self, service):
        """设置Profile服务引用"""
        self._profile_service = service

    def set_plugin_registry(self, registry):
        """设置插件注册中心引用"""
        self._plugin_registry = registry

    async def recognize_intent(
        self,
        user_input: str,
        context: Dict = None
    ) -> TaskIntent:
        """
        识别任务意图

        Args:
            user_input: 用户输入
            context: 上下文

        Returns:
            TaskIntent
        """
        intent_id = hashlib.md5(
            f"{user_input}:{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]

        # 简单的规则匹配（实际应用中可接入NLP模型）
        task_type, entities = self._match_task_type(user_input)

        # 评估置信度
        confidence = self._calculate_intent_confidence(task_type, entities, user_input)

        # 评估数据质量
        data_quality = await self._assess_data_quality(entities, context)

        intent = TaskIntent(
            intent_id=intent_id,
            task_type=task_type,
            confidence=confidence,
            entities=entities,
            context=context or {},
            required_data_fields=self._get_required_fields(task_type),
            estimated_complexity=self._estimate_complexity(task_type, entities)
        )

        return intent

    def _match_task_type(self, user_input: str) -> tuple:
        """匹配任务类型"""
        input_lower = user_input.lower()

        # 文档生成
        if any(k in input_lower for k in ["生成", "创建", "编写", "制作"]):
            if "环评" in user_input or "环境" in user_input:
                return TaskType.DOCUMENT_GENERATION, {"doc_category": "environmental"}
            if "可研" in user_input or "可行性" in user_input:
                return TaskType.DOCUMENT_GENERATION, {"doc_category": "feasibility"}
            if "申报" in user_input:
                return TaskType.DECLARATION_EXECUTE, {}
            return TaskType.DOCUMENT_GENERATION, {}

        # 申报
        if any(k in input_lower for k in ["申报", "申请", "填报", "提交"]):
            if "排污" in user_input:
                return TaskType.DECLARATION_EXECUTE, {"declaration_type": "pollution_permit"}
            if "工商" in user_input or "营业执照" in user_input:
                return TaskType.DECLARATION_EXECUTE, {"declaration_type": "business_license"}
            if "税务" in user_input or "纳税" in user_input:
                return TaskType.DECLARATION_EXECUTE, {"declaration_type": "tax"}
            return TaskType.DECLARATION_EXECUTE, {}

        # 政府网站操作
        if any(k in input_lower for k in ["登录", "填表", "上传", "自动填报"]):
            return TaskType.GOV_FORM_FILL, {}

        # 合规检查
        if any(k in input_lower for k in ["检查", "合规", "审查"]):
            return TaskType.COMPLIANCE_CHECK, {}

        # 数据验证
        if any(k in input_lower for k in ["验证", "校验", "核实"]):
            return TaskType.DATA_VALIDATION, {}

        return TaskType.DOCUMENT_GENERATION, {}

    def _calculate_intent_confidence(
        self,
        task_type: TaskType,
        entities: Dict,
        user_input: str
    ) -> float:
        """计算意图置信度"""
        confidence = 0.7  # 基础置信度

        # 实体越多越准确
        if entities:
            confidence += len(entities) * 0.05

        # 特定关键词提升置信度
        specific_keywords = {
            TaskType.DECLARATION_EXECUTE: ["排污许可证", "营业执照", "税务申报"],
            TaskType.DOCUMENT_GENERATION: ["环评报告", "可研报告", "方案"],
            TaskType.GOV_FORM_FILL: ["填表", "自动填报", "政府网站"],
        }

        for keyword in specific_keywords.get(task_type, []):
            if keyword in user_input:
                confidence += 0.1
                break

        return min(confidence, 1.0)

    async def _assess_data_quality(
        self,
        entities: Dict,
        context: Dict = None
    ) -> float:
        """评估数据质量"""
        if not self._profile_service:
            return 0.5

        # 检查是否有企业Profile
        profile_id = entities.get("profile_id")
        if not profile_id:
            return 0.5

        profile = await self._profile_service.get_profile(profile_id)
        if not profile:
            return 0.5

        return profile.data_quality_score

    def _get_required_fields(self, task_type: TaskType) -> List[str]:
        """获取任务所需字段"""
        required_fields = {
            TaskType.DOCUMENT_GENERATION: ["company_name", "credit_code", "project_info"],
            TaskType.DECLARATION_EXECUTE: ["credit_code", "legal_person", "business_scope"],
            TaskType.GOV_FORM_FILL: ["gov_account", "target_system"],
            TaskType.COMPLIANCE_CHECK: ["credit_code", "industry_code"],
            TaskType.DATA_VALIDATION: ["field_name", "field_value"],
        }
        return required_fields.get(task_type, [])

    def _estimate_complexity(
        self,
        task_type: TaskType,
        entities: Dict
    ) -> str:
        """估算任务复杂度"""
        if task_type in [TaskType.DATA_VALIDATION, TaskType.GOV_LOGIN]:
            return "low"
        if entities.get("declaration_type") or entities.get("doc_category"):
            return "medium"
        return "high"

    async def route(
        self,
        intent: TaskIntent,
        context: Dict = None
    ) -> RoutingResult:
        """
        执行路由

        Args:
            intent: 任务意图
            context: 上下文

        Returns:
            RoutingResult
        """
        # 1. 检查数据完整性
        missing_fields = self._check_required_fields(intent)

        if missing_fields:
            return RoutingResult(
                decision=RoutingDecision.NEED_MORE_DATA,
                task_type=intent.task_type,
                execution_mode=ExecutionMode.MANUAL,
                suggestions=[f"请提供: {', '.join(missing_fields)}"],
                reason="缺少必要数据",
                overall_confidence=intent.confidence
            )

        # 2. 匹配路由规则
        matched_rule = self._match_routing_rule(intent)

        if not matched_rule:
            return RoutingResult(
                decision=RoutingDecision.REJECT,
                task_type=intent.task_type,
                execution_mode=ExecutionMode.MANUAL,
                reason="没有匹配的路由规则",
                overall_confidence=intent.confidence
            )

        # 3. 确定执行模式
        execution_mode, decision = self._determine_execution_mode(
            intent,
            matched_rule
        )

        # 4. 生成路由结果
        result = RoutingResult(
            decision=decision,
            task_type=intent.task_type,
            execution_mode=execution_mode,
            target_engine=matched_rule.target_engine,
            target_plugin=matched_rule.target_plugin,
            confidence_threshold=matched_rule.confidence_threshold,
            reason=f"匹配规则: {matched_rule.name}",
            routing_path=[matched_rule.target_engine],
            overall_confidence=intent.confidence,
            data_quality_score=await self._assess_data_quality(intent.entities, context)
        )

        # 5. 添加建议和警告
        if execution_mode == ExecutionMode.AUTO_FULL:
            result.suggestions.append("任务将以全自动模式执行")
        elif execution_mode == ExecutionMode.AUTO_PARTIAL:
            result.suggestions.append("任务将自动执行，但需要人工复核")
            result.required_verifications.extend([
                "数据准确性验证",
                "关键字段复核",
                "提交前确认"
            ])
        elif execution_mode == ExecutionMode.MANUAL:
            result.suggestions.append("由于数据质量不足，需要人工处理")

        # 6. 添加警告
        if result.data_quality_score < 0.7:
            result.warnings.append(f"数据质量分数较低: {result.data_quality_score:.0%}")

        if intent.priority >= 8:
            result.warnings.append("高优先级任务，请注意时效性")

        return result

    def _check_required_fields(self, intent: TaskIntent) -> List[str]:
        """检查必要字段是否齐全"""
        missing = []
        for field in intent.required_data_fields:
            if field not in intent.entities or not intent.entities[field]:
                missing.append(field)
        return missing

    def _match_routing_rule(self, intent: TaskIntent) -> Optional[RoutingRule]:
        """匹配路由规则"""
        matched_rules = []

        for rule in self._rules.values():
            if not rule.enabled:
                continue

            # 检查任务类型匹配
            if rule.task_types and intent.task_type not in rule.task_types:
                continue

            matched_rules.append(rule)

        if not matched_rules:
            return None

        # 返回优先级最高的规则
        return max(matched_rules, key=lambda r: r.priority)

    def _determine_execution_mode(
        self,
        intent: TaskIntent,
        rule: RoutingRule
    ) -> tuple:
        """确定执行模式"""
        # 使用规则指定的执行模式
        mode = rule.execution_mode

        # 根据置信度和数据质量调整
        if intent.confidence < self.HUMAN_REVIEW_THRESHOLD:
            return ExecutionMode.MANUAL, RoutingDecision.NEED_HUMAN_REVIEW

        if intent.confidence >= self.AUTO_FULL_THRESHOLD:
            if mode == ExecutionMode.AUTO_PARTIAL:
                # 提升为全自动
                return ExecutionMode.AUTO_FULL, RoutingDecision.ACCEPT_AUTO
            return mode, RoutingDecision.ACCEPT_AUTO

        if intent.confidence >= self.AUTO_PARTIAL_THRESHOLD:
            if mode == ExecutionMode.AUTO_FULL:
                # 降级为半自动
                return ExecutionMode.AUTO_PARTIAL, RoutingDecision.ACCEPT_AUTO
            return mode, RoutingDecision.NEED_HUMAN_REVIEW

        return ExecutionMode.MANUAL, RoutingDecision.NEED_HUMAN_REVIEW

    async def create_review_task(
        self,
        intent: TaskIntent,
        routing_result: RoutingResult,
        auto_filled_data: Dict = None
    ) -> HumanReviewTask:
        """创建人工复核任务"""
        task_id = hashlib.md5(
            f"review:{intent.intent_id}:{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]

        task = HumanReviewTask(
            task_id=task_id,
            intent=intent,
            routing_result=routing_result,
            auto_filled_data=auto_filled_data or {}
        )

        self._review_queue.append(task)
        return task

    async def complete_review(
        self,
        task_id: str,
        result: str,
        corrections: Dict = None,
        notes: str = ""
    ) -> bool:
        """完成复核"""
        for task in self._review_queue:
            if task.task_id == task_id:
                task.status = "completed"
                task.completed_at = datetime.now()
                task.review_result = result
                task.corrections = corrections or {}
                task.notes = notes
                return True
        return False

    def get_pending_reviews(self, limit: int = 10) -> List[HumanReviewTask]:
        """获取待复核任务"""
        pending = [t for t in self._review_queue if t.status == "pending"]
        return sorted(pending, key=lambda x: x.intent.priority, reverse=True)[:limit]

    def add_routing_rule(
        self,
        name: str,
        task_type: TaskType,
        target_engine: str,
        execution_mode: ExecutionMode,
        **kwargs
    ) -> str:
        """添加路由规则"""
        rule_id = hashlib.md5(
            f"{name}:{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]

        rule = RoutingRule(
            rule_id=rule_id,
            name=name,
            task_types=[task_type],
            target_engine=target_engine,
            execution_mode=execution_mode,
            **kwargs
        )

        self._rules[rule_id] = rule
        return rule_id

    def export_rules(self) -> List[Dict]:
        """导出路由规则"""
        return [
            {
                "rule_id": r.rule_id,
                "name": r.name,
                "task_types": [t.value for t in r.task_types],
                "target_engine": r.target_engine,
                "execution_mode": r.execution_mode.value,
                "confidence_threshold": r.confidence_threshold,
                "enabled": r.enabled
            }
            for r in self._rules.values()
        ]


# ==================== 单例模式 ====================

_intelligent_router: Optional[IntelligentRouter] = None


def get_intelligent_router() -> IntelligentRouter:
    """获取智能路由引擎单例"""
    global _intelligent_router
    if _intelligent_router is None:
        _intelligent_router = IntelligentRouter()
    return _intelligent_router
