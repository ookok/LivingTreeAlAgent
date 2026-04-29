"""
消息模式与智能提示词系统 - 数据模型层
User-Defined Message Pattern & Smart Prompt System
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from datetime import datetime
import json
import uuid


# ==================== 枚举定义 ====================

class TriggerType(Enum):
    """触发类型"""
    AUTO = "auto"           # 自动触发
    MANUAL = "manual"        # 手动触发
    KEYWORD = "keyword"      # 关键词触发
    CONTEXT = "context"      # 上下文触发
    SCHEDULE = "schedule"    # 定时触发


class OperatorType(Enum):
    """操作符类型"""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    REGEX = "regex"
    GREATER_THAN = ">"
    LESS_THAN = "<"
    GREATER_EQUAL = ">="
    LESS_EQUAL = "<="
    IN = "in"
    NOT_IN = "not_in"


class VariableType(Enum):
    """变量类型"""
    SYSTEM = "system"        # 系统变量
    USER = "user"            # 用户变量
    CONTENT = "content"      # 内容变量
    CUSTOM = "custom"        # 自定义变量
    SMART = "smart"          # 智能变量
    COMPUTED = "computed"    # 计算变量


class VariableSource(Enum):
    """变量来源"""
    CONVERSATION_HISTORY = "conversation_history"
    CURRENT_MESSAGE = "current_message"
    USER_PROFILE = "user_profile"
    USER_PREFERENCE = "user_preference"
    PATTERN_CONFIG = "pattern_config"
    SYSTEM_STATE = "system_state"
    ENVIRONMENT = "environment"
    CUSTOM = "custom"


class TemplateType(Enum):
    """模板类型"""
    PROMPT = "prompt"        # 提示词模板
    MESSAGE = "message"      # 消息模板
    RESPONSE = "response"    # 回复模板


class StructureType(Enum):
    """结构类型"""
    STANDARD = "standard"    # 标准结构
    FREE = "free"            # 自由结构
    MARKDOWN = "markdown"    # Markdown格式
    CODE = "code"            # 代码格式


class ThinkingStyle(Enum):
    """思考风格"""
    STRUCTURED = "structured"    # 结构化思考
    FREE = "free"                # 自由思考
    STEP_BY_STEP = "step_by_step"  # 分步思考
    BRAINSTORM = "brainstorm"    # 头脑风暴


class ThinkingDepth(Enum):
    """思考深度"""
    SHALLOW = "shallow"      # 浅层思考
    MEDIUM = "medium"        # 中层思考
    DEEP = "deep"            # 深层思考


class OutputFormat(Enum):
    """输出格式"""
    MARKDOWN = "markdown"
    PLAIN = "plain"
    RICH = "rich"
    HTML = "html"
    JSON = "json"


class PatternCategory(Enum):
    """模式分类"""
    GENERAL = "general"                    # 通用
    ANALYSIS = "analysis"                  # 分析
    WRITING = "writing"                    # 写作
    CODING = "coding"                      # 编程
    LEARNING = "learning"                  # 学习
    BRAINSTORM = "brainstorm"              # 头脑风暴
    DECISION = "decision"                  # 决策
    PLANNING = "planning"                  # 规划
    RESEARCH = "research"                  # 研究
    CREATIVE = "creative"                  # 创意
    PROFESSIONAL = "professional"          # 专业


class SharingLicense(Enum):
    """分享许可"""
    PERSONAL_USE = "personal_use"
    ATTRIBUTION_REQUIRED = "attribution_required"
    COMMERCIAL_USE = "commercial_use"
    OPEN_SOURCE = "open_source"


# ==================== 数据模型 ====================

@dataclass
class TriggerCondition:
    """触发条件"""
    field: str = "content"                    # 检测字段
    operator: OperatorType = OperatorType.CONTAINS  # 操作符
    value: Any = None                         # 条件值
    confidence: float = 0.8                   # 触发置信度

    def to_dict(self) -> Dict:
        return {
            "field": self.field,
            "operator": self.operator.value if isinstance(self.operator, OperatorType) else self.operator,
            "value": self.value,
            "confidence": self.confidence
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'TriggerCondition':
        op = data.get("operator", "contains")
        if isinstance(op, str):
            op = OperatorType(op)
        return cls(
            field=data.get("field", "content"),
            operator=op,
            value=data.get("value"),
            confidence=data.get("confidence", 0.8)
        )


@dataclass
class TriggerConfig:
    """触发配置"""
    type: TriggerType = TriggerType.MANUAL   # 触发类型
    conditions: List[TriggerCondition] = field(default_factory=list)  # 触发条件
    keywords: List[str] = field(default_factory=list)  # 关键词列表
    confidence_threshold: float = 0.7       # 置信度阈值
    auto_apply: bool = False                # 是否自动应用

    def to_dict(self) -> Dict:
        return {
            "type": self.type.value if isinstance(self.type, TriggerType) else self.type,
            "conditions": [c.to_dict() for c in self.conditions],
            "keywords": self.keywords,
            "confidence_threshold": self.confidence_threshold,
            "auto_apply": self.auto_apply
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'TriggerConfig':
        t = data.get("type", "manual")
        if isinstance(t, str):
            t = TriggerType(t)
        conditions = [TriggerCondition.from_dict(c) for c in data.get("conditions", [])]
        return cls(
            type=t,
            conditions=conditions,
            keywords=data.get("keywords", []),
            confidence_threshold=data.get("confidence_threshold", 0.7),
            auto_apply=data.get("auto_apply", False)
        )


@dataclass
class VariableDefinition:
    """变量定义"""
    name: str                               # 变量名
    display_name: str = ""                   # 显示名称
    var_type: VariableType = VariableType.CUSTOM  # 变量类型
    source: VariableSource = VariableSource.CUSTOM  # 变量来源
    default: Any = ""                        # 默认值
    required: bool = False                  # 是否必需
    description: str = ""                   # 变量描述
    placeholder: str = ""                   # 输入提示
    options: List[str] = field(default_factory=list)  # 可选值列表
    validation: str = ""                     # 验证规则
    transform: str = ""                      # 转换函数

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "type": self.var_type.value if isinstance(self.var_type, VariableType) else self.var_type,
            "source": self.source.value if isinstance(self.source, VariableSource) else self.source,
            "default": self.default,
            "required": self.required,
            "description": self.description,
            "placeholder": self.placeholder,
            "options": self.options,
            "validation": self.validation,
            "transform": self.transform
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'VariableDefinition':
        vtype = data.get("type", "custom")
        if isinstance(vtype, str):
            vtype = VariableType(vtype)
        source = data.get("source", "custom")
        if isinstance(source, str):
            source = VariableSource(source)
        return cls(
            name=data.get("name", ""),
            display_name=data.get("display_name", ""),
            var_type=vtype,
            source=source,
            default=data.get("default", ""),
            required=data.get("required", False),
            description=data.get("description", ""),
            placeholder=data.get("placeholder", ""),
            options=data.get("options", []),
            validation=data.get("validation", ""),
            transform=data.get("transform", "")
        )


@dataclass
class TemplateConfig:
    """模板配置"""
    template_type: TemplateType = TemplateType.PROMPT   # 模板类型
    structure: StructureType = StructureType.STANDARD   # 结构类型
    content: str = ""                                    # 模板内容
    variables: Dict[str, VariableDefinition] = field(default_factory=dict)  # 变量定义

    def to_dict(self) -> Dict:
        return {
            "type": self.template_type.value if isinstance(self.template_type, TemplateType) else self.template_type,
            "structure": self.structure.value if isinstance(self.structure, StructureType) else self.structure,
            "content": self.content,
            "variables": {k: v.to_dict() for k, v in self.variables.items()}
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'TemplateConfig':
        ttype = data.get("type", "prompt")
        if isinstance(ttype, str):
            ttype = TemplateType(ttype)
        struct = data.get("structure", "standard")
        if isinstance(struct, str):
            struct = StructureType(struct)
        variables = {
            k: VariableDefinition.from_dict(v)
            for k, v in data.get("variables", {}).items()
        }
        return cls(
            template_type=ttype,
            structure=struct,
            content=data.get("content", ""),
            variables=variables
        )


@dataclass
class ThinkingConfig:
    """思考过程配置"""
    enabled: bool = True                     # 是否启用
    style: ThinkingStyle = ThinkingStyle.STRUCTURED  # 思考风格
    depth: ThinkingDepth = ThinkingDepth.MEDIUM      # 思考深度
    show_steps: bool = True                  # 显示推理步骤
    show_assumptions: bool = True           # 显示假设
    show_alternatives: bool = True           # 显示备选方案
    max_stages: int = 5                     # 最大阶段数
    include_reasoning: bool = True          # 包含推理过程
    reasoning_format: str = "bullet"         # 推理格式

    def to_dict(self) -> Dict:
        return {
            "enabled": self.enabled,
            "style": self.style.value if isinstance(self.style, ThinkingStyle) else self.style,
            "depth": self.depth.value if isinstance(self.depth, ThinkingDepth) else self.depth,
            "show_steps": self.show_steps,
            "show_assumptions": self.show_assumptions,
            "show_alternatives": self.show_alternatives,
            "max_stages": self.max_stages,
            "include_reasoning": self.include_reasoning,
            "reasoning_format": self.reasoning_format
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'ThinkingConfig':
        style = data.get("style", "structured")
        if isinstance(style, str):
            style = ThinkingStyle(style)
        depth = data.get("depth", "medium")
        if isinstance(depth, str):
            depth = ThinkingDepth(depth)
        return cls(
            enabled=data.get("enabled", True),
            style=style,
            depth=depth,
            show_steps=data.get("show_steps", True),
            show_assumptions=data.get("show_assumptions", True),
            show_alternatives=data.get("show_alternatives", True),
            max_stages=data.get("max_stages", 5),
            include_reasoning=data.get("include_reasoning", True),
            reasoning_format=data.get("reasoning_format", "bullet")
        )


@dataclass
class CustomRule:
    """自定义规则"""
    rule_id: str = ""                        # 规则ID
    name: str = ""                           # 规则名称
    condition: str = ""                       # 触发条件
    action: str = ""                         # 执行动作
    priority: int = 0                        # 优先级
    enabled: bool = True                     # 是否启用

    def to_dict(self) -> Dict:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "condition": self.condition,
            "action": self.action,
            "priority": self.priority,
            "enabled": self.enabled
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'CustomRule':
        return cls(
            rule_id=data.get("rule_id", ""),
            name=data.get("name", ""),
            condition=data.get("condition", ""),
            action=data.get("action", ""),
            priority=data.get("priority", 0),
            enabled=data.get("enabled", True)
        )


@dataclass
class EnhancementConfig:
    """增强配置"""
    thinking: ThinkingConfig = field(default_factory=ThinkingConfig)  # 思考过程
    custom_rules: List[CustomRule] = field(default_factory=list)       # 自定义规则
    auto_refine: bool = True                   # 自动优化
    adapt_to_user: bool = True                 # 适应用户

    def to_dict(self) -> Dict:
        return {
            "thinking": self.thinking.to_dict(),
            "custom_rules": [r.to_dict() for r in self.custom_rules],
            "auto_refine": self.auto_refine,
            "adapt_to_user": self.adapt_to_user
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'EnhancementConfig':
        thinking = ThinkingConfig.from_dict(data.get("thinking", {}))
        custom_rules = [CustomRule.from_dict(r) for r in data.get("custom_rules", [])]
        return cls(
            thinking=thinking,
            custom_rules=custom_rules,
            auto_refine=data.get("auto_refine", True),
            adapt_to_user=data.get("adapt_to_user", True)
        )


@dataclass
class ContextConfig:
    """上下文配置"""
    memory_window: int = 10                   # 记忆窗口大小
    include_history: bool = True              # 包含历史对话
    include_user_profile: bool = True        # 包含用户画像
    include_system_state: bool = True         # 包含系统状态
    include_environment: bool = True         # 包含环境信息
    max_context_tokens: int = 4000           # 最大上下文token
    context_priority: List[str] = field(default_factory=list)  # 上下文优先级

    def to_dict(self) -> Dict:
        return {
            "memory_window": self.memory_window,
            "include_history": self.include_history,
            "include_user_profile": self.include_user_profile,
            "include_system_state": self.include_system_state,
            "include_environment": self.include_environment,
            "max_context_tokens": self.max_context_tokens,
            "context_priority": self.context_priority
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'ContextConfig':
        return cls(
            memory_window=data.get("memory_window", 10),
            include_history=data.get("include_history", True),
            include_user_profile=data.get("include_user_profile", True),
            include_system_state=data.get("include_system_state", True),
            include_environment=data.get("include_environment", True),
            max_context_tokens=data.get("max_context_tokens", 4000),
            context_priority=data.get("context_priority", [])
        )


@dataclass
class OutputConfig:
    """输出配置"""
    format: OutputFormat = OutputFormat.MARKDOWN  # 输出格式
    length_limit: int = 2000                # 长度限制
    quality_threshold: float = 0.7          # 质量阈值
    retry_on_failure: int = 3              # 失败重试次数
    fallback_template: str = "default"      # 回退模板
    show_confidence: bool = True            # 显示置信度
    show_reasoning: bool = True             # 显示推理过程

    def to_dict(self) -> Dict:
        return {
            "format": self.format.value if isinstance(self.format, OutputFormat) else self.format,
            "length_limit": self.length_limit,
            "quality_threshold": self.quality_threshold,
            "retry_on_failure": self.retry_on_failure,
            "fallback_template": self.fallback_template,
            "show_confidence": self.show_confidence,
            "show_reasoning": self.show_reasoning
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'OutputConfig':
        fmt = data.get("format", "markdown")
        if isinstance(fmt, str):
            fmt = OutputFormat(fmt)
        return cls(
            format=fmt,
            length_limit=data.get("length_limit", 2000),
            quality_threshold=data.get("quality_threshold", 0.7),
            retry_on_failure=data.get("retry_on_failure", 3),
            fallback_template=data.get("fallback_template", "default"),
            show_confidence=data.get("show_confidence", True),
            show_reasoning=data.get("show_reasoning", True)
        )


@dataclass
class PatternMetadata:
    """模式元数据"""
    created_at: str = ""                    # 创建时间
    updated_at: str = ""                    # 更新时间
    usage_count: int = 0                    # 使用次数
    success_count: int = 0                  # 成功次数
    success_rate: float = 0.0               # 成功率
    user_rating: float = 0.0                # 用户评分
    popularity: float = 0.0                  # 受欢迎程度
    effectiveness: float = 0.0              # 有效性评分
    avg_response_time: float = 0.0          # 平均响应时间
    last_used: str = ""                     # 最后使用时间

    def to_dict(self) -> Dict:
        return {
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "usage_count": self.usage_count,
            "success_count": self.success_count,
            "success_rate": self.success_rate,
            "user_rating": self.user_rating,
            "popularity": self.popularity,
            "effectiveness": self.effectiveness,
            "avg_response_time": self.avg_response_time,
            "last_used": self.last_used
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'PatternMetadata':
        return cls(
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            usage_count=data.get("usage_count", 0),
            success_count=data.get("success_count", 0),
            success_rate=data.get("success_rate", 0.0),
            user_rating=data.get("user_rating", 0.0),
            popularity=data.get("popularity", 0.0),
            effectiveness=data.get("effectiveness", 0.0),
            avg_response_time=data.get("avg_response_time", 0.0),
            last_used=data.get("last_used", "")
        )


@dataclass
class SharingConfig:
    """分享配置"""
    public: bool = False                     # 是否公开
    shareable: bool = True                   # 是否可分享
    license: SharingLicense = SharingLicense.PERSONAL_USE  # 使用许可
    attribution: str = "optional"           # 署名要求
    tags: List[str] = field(default_factory=list)  # 分享标签

    def to_dict(self) -> Dict:
        return {
            "public": self.public,
            "shareable": self.shareable,
            "license": self.license.value if isinstance(self.license, SharingLicense) else self.license,
            "attribution": self.attribution,
            "tags": self.tags
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'SharingConfig':
        lic = data.get("license", "personal_use")
        if isinstance(lic, str):
            lic = SharingLicense(lic)
        return cls(
            public=data.get("public", False),
            shareable=data.get("shareable", True),
            license=lic,
            attribution=data.get("attribution", "optional"),
            tags=data.get("tags", [])
        )


@dataclass
class MessagePattern:
    """消息模式主类"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))  # 唯一标识
    name: str = ""                              # 模式名称
    description: str = ""                      # 模式描述
    version: str = "1.0.0"                     # 版本号
    category: PatternCategory = PatternCategory.GENERAL  # 分类
    tags: List[str] = field(default_factory=list)  # 标签
    author: str = ""                            # 创建者
    icon: str = "📝"                            # 图标

    # 核心配置
    trigger: TriggerConfig = field(default_factory=TriggerConfig)     # 触发配置
    template: TemplateConfig = field(default_factory=TemplateConfig)   # 模板配置
    enhancement: EnhancementConfig = field(default_factory=EnhancementConfig)  # 增强配置
    context: ContextConfig = field(default_factory=ContextConfig)     # 上下文配置
    output: OutputConfig = field(default_factory=OutputConfig)         # 输出配置

    # 元数据和分享
    metadata: PatternMetadata = field(default_factory=PatternMetadata)  # 元数据
    sharing: SharingConfig = field(default_factory=SharingConfig)       # 分享配置

    # 状态
    enabled: bool = True                       # 是否启用
    favorite: bool = False                      # 是否收藏
    is_system: bool = False                     # 是否系统内置

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "category": self.category.value if isinstance(self.category, PatternCategory) else self.category,
            "tags": self.tags,
            "author": self.author,
            "icon": self.icon,
            "trigger": self.trigger.to_dict(),
            "template": self.template.to_dict(),
            "enhancement": self.enhancement.to_dict(),
            "context": self.context.to_dict(),
            "output": self.output.to_dict(),
            "metadata": self.metadata.to_dict(),
            "sharing": self.sharing.to_dict(),
            "enabled": self.enabled,
            "favorite": self.favorite,
            "is_system": self.is_system
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'MessagePattern':
        """从字典创建"""
        cat = data.get("category", "general")
        if isinstance(cat, str):
            cat = PatternCategory(cat)

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", ""),
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            category=cat,
            tags=data.get("tags", []),
            author=data.get("author", ""),
            icon=data.get("icon", "📝"),
            trigger=TriggerConfig.from_dict(data.get("trigger", {})),
            template=TemplateConfig.from_dict(data.get("template", {})),
            enhancement=EnhancementConfig.from_dict(data.get("enhancement", {})),
            context=ContextConfig.from_dict(data.get("context", {})),
            output=OutputConfig.from_dict(data.get("output", {})),
            metadata=PatternMetadata.from_dict(data.get("metadata", {})),
            sharing=SharingConfig.from_dict(data.get("sharing", {})),
            enabled=data.get("enabled", True),
            favorite=data.get("favorite", False),
            is_system=data.get("is_system", False)
        )

    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'MessagePattern':
        """从JSON字符串创建"""
        return cls.from_dict(json.loads(json_str))


# ==================== 系统变量定义 ====================

class SystemVariables:
    """系统预定义变量"""

    # 时间变量
    CURRENT_TIME = VariableDefinition(
        name="current_time",
        display_name="当前时间",
        var_type=VariableType.SYSTEM,
        source=VariableSource.SYSTEM_STATE,
        default="",
        description="当前系统时间"
    )

    CURRENT_DATE = VariableDefinition(
        name="current_date",
        display_name="当前日期",
        var_type=VariableType.SYSTEM,
        source=VariableSource.SYSTEM_STATE,
        default="",
        description="当前系统日期"
    )

    TIMESTAMP = VariableDefinition(
        name="timestamp",
        display_name="时间戳",
        var_type=VariableType.SYSTEM,
        source=VariableSource.SYSTEM_STATE,
        default="",
        description="当前Unix时间戳"
    )

    # 用户变量
    USERNAME = VariableDefinition(
        name="username",
        display_name="用户名",
        var_type=VariableType.USER,
        source=VariableSource.USER_PROFILE,
        default="用户",
        description="当前用户名"
    )

    USER_ID = VariableDefinition(
        name="user_id",
        display_name="用户ID",
        var_type=VariableType.USER,
        source=VariableSource.USER_PROFILE,
        default="",
        description="用户唯一标识"
    )

    USER_ROLE = VariableDefinition(
        name="user_role",
        display_name="用户角色",
        var_type=VariableType.USER,
        source=VariableSource.USER_PROFILE,
        default="普通用户",
        description="用户角色"
    )

    # 会话变量
    SESSION_ID = VariableDefinition(
        name="session_id",
        display_name="会话ID",
        var_type=VariableType.SYSTEM,
        source=VariableSource.SYSTEM_STATE,
        default="",
        description="当前会话ID"
    )

    CONVERSATION_TOPIC = VariableDefinition(
        name="conversation_topic",
        display_name="对话主题",
        var_type=VariableType.SMART,
        source=VariableSource.CONVERSATION_HISTORY,
        default="一般对话",
        description="当前对话主题"
    )

    MESSAGE_COUNT = VariableDefinition(
        name="message_count",
        display_name="消息数量",
        var_type=VariableType.SYSTEM,
        source=VariableSource.CONVERSATION_HISTORY,
        default="0",
        description="当前会话消息数"
    )

    # 内容变量
    USER_INPUT = VariableDefinition(
        name="user_input",
        display_name="用户输入",
        var_type=VariableType.CONTENT,
        source=VariableSource.CURRENT_MESSAGE,
        default="",
        required=True,
        description="当前用户输入内容"
    )

    PREVIOUS_MESSAGE = VariableDefinition(
        name="previous_message",
        display_name="上一条消息",
        var_type=VariableType.CONTENT,
        source=VariableSource.CONVERSATION_HISTORY,
        default="",
        description="上一条用户消息"
    )

    CONVERSATION_CONTEXT = VariableDefinition(
        name="conversation_context",
        display_name="对话上下文",
        var_type=VariableType.CONTENT,
        source=VariableSource.CONVERSATION_HISTORY,
        default="",
        description="对话历史上下文"
    )

    # 智能变量
    USER_INTENT = VariableDefinition(
        name="user_intent",
        display_name="用户意图",
        var_type=VariableType.SMART,
        source=VariableSource.SYSTEM_STATE,
        default="未知",
        description="识别的用户意图"
    )

    USER_SENTIMENT = VariableDefinition(
        name="user_sentiment",
        display_name="用户情感",
        var_type=VariableType.SMART,
        source=VariableSource.SYSTEM_STATE,
        default="中性",
        description="用户情感倾向"
    )

    DOMAIN_KNOWLEDGE = VariableDefinition(
        name="domain_knowledge",
        display_name="领域知识",
        var_type=VariableType.SMART,
        source=VariableSource.USER_PROFILE,
        default="通用",
        description="用户专业领域"
    )

    WRITING_STYLE = VariableDefinition(
        name="writing_style",
        display_name="写作风格",
        var_type=VariableType.SMART,
        source=VariableSource.USER_PREFERENCE,
        default="专业严谨",
        description="用户写作风格偏好"
    )

    @classmethod
    def get_all_system_variables(cls) -> Dict[str, VariableDefinition]:
        """获取所有系统变量"""
        return {
            "current_time": cls.CURRENT_TIME,
            "current_date": cls.CURRENT_DATE,
            "timestamp": cls.TIMESTAMP,
            "username": cls.USERNAME,
            "user_id": cls.USER_ID,
            "user_role": cls.USER_ROLE,
            "session_id": cls.SESSION_ID,
            "conversation_topic": cls.CONVERSATION_TOPIC,
            "message_count": cls.MESSAGE_COUNT,
            "user_input": cls.USER_INPUT,
            "previous_message": cls.PREVIOUS_MESSAGE,
            "conversation_context": cls.CONVERSATION_CONTEXT,
            "user_intent": cls.USER_INTENT,
            "user_sentiment": cls.USER_SENTIMENT,
            "domain_knowledge": cls.DOMAIN_KNOWLEDGE,
            "writing_style": cls.WRITING_STYLE
        }


# ==================== 内置模式模板 ====================

class BuiltInPatterns:
    """内置模式模板"""

    @classmethod
    def get_professional_analysis_pattern(cls) -> MessagePattern:
        """专业需求分析模式"""
        pattern = MessagePattern()
        pattern.name = "专业需求分析"
        pattern.description = "用于专业需求分析的提示词模板"
        pattern.category = PatternCategory.ANALYSIS
        pattern.tags = ["需求分析", "专业", "系统设计"]
        pattern.icon = "🔍"
        pattern.is_system = True

        # 触发配置
        pattern.trigger.type = TriggerType.KEYWORD
        pattern.trigger.keywords = ["需求", "要求", "需要分析", "请分析"]

        # 模板配置
        pattern.template.template_type = TemplateType.PROMPT
        pattern.template.structure = StructureType.MARKDOWN
        pattern.template.content = """基于以下{context}，请按照{framework}框架分析{requirement}。

## 分析要求
1. 识别关键需求点
2. 分析需求合理性
3. 提出解决方案
4. 评估实施难度

## 输出格式
- 核心问题识别
- 需求拆解与分析
- 解决方案建议
- 实施建议与风险

请用{style}风格回答，注意{emphasis}。"""
        pattern.template.variables = {
            "context": VariableDefinition(
                name="context",
                display_name="背景上下文",
                var_type=VariableType.CONTENT,
                source=VariableSource.CONVERSATION_HISTORY,
                default="对话上下文",
                required=True
            ),
            "framework": VariableDefinition(
                name="framework",
                display_name="分析框架",
                var_type=VariableType.CUSTOM,
                source=VariableSource.USER_PREFERENCE,
                default="SW2H",
                options=["SW2H", "KANO", "MoSCoW", "用户故事"],
                description="使用的分析框架"
            ),
            "requirement": VariableDefinition(
                name="requirement",
                display_name="需求描述",
                var_type=VariableType.CONTENT,
                source=VariableSource.CURRENT_MESSAGE,
                default="",
                required=True,
                placeholder="请输入需要分析的需求..."
            ),
            "style": VariableDefinition(
                name="style",
                display_name="回答风格",
                var_type=VariableType.CUSTOM,
                source=VariableSource.USER_PREFERENCE,
                default="专业严谨",
                options=["专业严谨", "简洁明了", "详细深入", "通俗易懂"]
            ),
            "emphasis": VariableDefinition(
                name="emphasis",
                display_name="重点强调",
                var_type=VariableType.CUSTOM,
                source=VariableSource.PATTERN_CONFIG,
                default="逻辑严密性",
                options=["逻辑严密性", "实用性", "创新性", "可操作性"]
            )
        }

        # 思考配置
        pattern.enhancement.thinking.enabled = True
        pattern.enhancement.thinking.style = ThinkingStyle.STRUCTURED
        pattern.enhancement.thinking.depth = ThinkingDepth.DEEP

        return pattern

    @classmethod
    def get_code_review_pattern(cls) -> MessagePattern:
        """代码审查模式"""
        pattern = MessagePattern()
        pattern.name = "代码审查"
        pattern.description = "用于代码审查和优化的提示词模板"
        pattern.category = PatternCategory.CODING
        pattern.tags = ["代码审查", "编程", "质量"]
        pattern.icon = "🔧"
        pattern.is_system = True

        pattern.trigger.type = TriggerType.KEYWORD
        pattern.trigger.keywords = ["代码审查", "review", "检查代码", "优化代码"]

        pattern.template.template_type = TemplateType.PROMPT
        pattern.template.structure = StructureType.CODE
        pattern.template.content = """请对以下{language}代码进行{review_type}：

```{language}
{code}
```

## 审查重点
- {focus_area}

## 输出要求
1. 发现的问题及严重程度
2. 改进建议
3. 最佳实践推荐
4. 安全性检查结果"""

        pattern.template.variables = {
            "language": VariableDefinition(
                name="language",
                display_name="编程语言",
                var_type=VariableType.CUSTOM,
                source=VariableSource.USER_PREFERENCE,
                default="Python",
                options=["Python", "JavaScript", "Java", "C++", "Go", "Rust", "TypeScript"]
            ),
            "code": VariableDefinition(
                name="code",
                display_name="代码内容",
                var_type=VariableType.CONTENT,
                source=VariableSource.CURRENT_MESSAGE,
                default="",
                required=True,
                placeholder="粘贴需要审查的代码..."
            ),
            "review_type": VariableDefinition(
                name="review_type",
                display_name="审查类型",
                var_type=VariableType.CUSTOM,
                source=VariableSource.PATTERN_CONFIG,
                default="全面审查",
                options=["全面审查", "性能优化", "安全检查", "代码规范", "架构分析"]
            ),
            "focus_area": VariableDefinition(
                name="focus_area",
                display_name="重点关注",
                var_type=VariableType.CUSTOM,
                source=VariableSource.USER_PREFERENCE,
                default="代码质量和性能",
                options=["代码质量", "性能优化", "安全性", "可维护性", "错误处理"]
            )
        }

        pattern.enhancement.thinking.enabled = True
        pattern.enhancement.thinking.depth = ThinkingDepth.DEEP

        return pattern

    @classmethod
    def get_writing_assistant_pattern(cls) -> MessagePattern:
        """写作助手模式"""
        pattern = MessagePattern()
        pattern.name = "写作助手"
        pattern.description = "辅助写作和内容创作"
        pattern.category = PatternCategory.WRITING
        pattern.tags = ["写作", "创作", "文案"]
        pattern.icon = "✍️"
        pattern.is_system = True

        pattern.trigger.type = TriggerType.KEYWORD
        pattern.trigger.keywords = ["写作", "帮我写", "创作", "起草"]

        pattern.template.template_type = TemplateType.PROMPT
        pattern.template.structure = StructureType.MARKDOWN
        pattern.template.content = """请帮我{writing_task}：

主题：{topic}
目标读者：{audience}
风格要求：{tone}

## 内容要求
{requirements}

## 大纲（可选）
{outline}"""

        pattern.template.variables = {
            "writing_task": VariableDefinition(
                name="writing_task",
                display_name="写作任务",
                var_type=VariableType.CUSTOM,
                source=VariableSource.CURRENT_MESSAGE,
                default="撰写文章",
                options=["撰写文章", "起草报告", "编写方案", "创作故事", "起草邮件"],
                required=True
            ),
            "topic": VariableDefinition(
                name="topic",
                display_name="主题",
                var_type=VariableType.CONTENT,
                source=VariableSource.CURRENT_MESSAGE,
                default="",
                required=True,
                placeholder="请描述文章主题..."
            ),
            "audience": VariableDefinition(
                name="audience",
                display_name="目标读者",
                var_type=VariableType.CUSTOM,
                source=VariableSource.USER_PREFERENCE,
                default="一般读者",
                description="文章的目标受众"
            ),
            "tone": VariableDefinition(
                name="tone",
                display_name="语气风格",
                var_type=VariableType.SMART,
                source=VariableSource.USER_PREFERENCE,
                default="专业正式",
                options=["专业正式", "轻松随意", "亲切友好", "严肃严谨", "活泼有趣"]
            ),
            "requirements": VariableDefinition(
                name="requirements",
                display_name="内容要求",
                var_type=VariableType.CONTENT,
                source=VariableSource.CURRENT_MESSAGE,
                default="结构清晰，内容完整",
                description="具体的内容要求"
            ),
            "outline": VariableDefinition(
                name="outline",
                display_name="文章大纲",
                var_type=VariableType.CONTENT,
                source=VariableSource.USER_PREFERENCE,
                default="",
                description="可选的文章大纲"
            )
        }

        pattern.enhancement.thinking.enabled = True
        pattern.enhancement.thinking.style = ThinkingStyle.BRAINSTORM

        return pattern

    @classmethod
    def get_decision_making_pattern(cls) -> MessagePattern:
        """决策辅助模式"""
        pattern = MessagePattern()
        pattern.name = "决策辅助"
        pattern.description = "辅助决策和方案比较"
        pattern.category = PatternCategory.DECISION
        pattern.tags = ["决策", "方案比较", "分析"]
        pattern.icon = "⚖️"
        pattern.is_system = True

        pattern.trigger.type = TriggerType.KEYWORD
        pattern.trigger.keywords = ["决策", "选择", "比较", "建议"]

        pattern.template.template_type = TemplateType.PROMPT
        pattern.template.structure = StructureType.MARKDOWN
        pattern.template.content = """## 决策问题
{question}

## 可选方案
{options}

## 评估标准
{criteria}

请进行系统分析，提供决策建议。"""

        pattern.template.variables = {
            "question": VariableDefinition(
                name="question",
                display_name="决策问题",
                var_type=VariableType.CONTENT,
                source=VariableSource.CURRENT_MESSAGE,
                default="",
                required=True,
                placeholder="描述需要决策的问题..."
            ),
            "options": VariableDefinition(
                name="options",
                display_name="可选方案",
                var_type=VariableType.CONTENT,
                source=VariableSource.CURRENT_MESSAGE,
                default="",
                required=True,
                placeholder="列出所有可选方案..."
            ),
            "criteria": VariableDefinition(
                name="criteria",
                display_name="评估标准",
                var_type=VariableType.CUSTOM,
                source=VariableSource.USER_PREFERENCE,
                default="成本、效益、风险、时间",
                description="评估方案的标准"
            )
        }

        pattern.enhancement.thinking.enabled = True
        pattern.enhancement.thinking.show_alternatives = True
        pattern.enhancement.thinking.show_assumptions = True

        return pattern

    @classmethod
    def get_all_builtin_patterns(cls) -> List[MessagePattern]:
        """获取所有内置模式"""
        return [
            cls.get_professional_analysis_pattern(),
            cls.get_code_review_pattern(),
            cls.get_writing_assistant_pattern(),
            cls.get_decision_making_pattern()
        ]


# ==================== 模式使用记录 ====================

@dataclass
class PatternUsageRecord:
    """模式使用记录"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    pattern_id: str = ""
    pattern_name: str = ""
    user_id: str = ""
    input_content: str = ""
    output_content: str = ""
    variables: Dict[str, Any] = field(default_factory=dict)
    quality_score: float = 0.0
    response_time: float = 0.0
    success: bool = True
    feedback: str = ""
    created_at: str = ""

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "pattern_id": self.pattern_id,
            "pattern_name": self.pattern_name,
            "user_id": self.user_id,
            "input_content": self.input_content,
            "output_content": self.output_content,
            "variables": self.variables,
            "quality_score": self.quality_score,
            "response_time": self.response_time,
            "success": self.success,
            "feedback": self.feedback,
            "created_at": self.created_at
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'PatternUsageRecord':
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            pattern_id=data.get("pattern_id", ""),
            pattern_name=data.get("pattern_name", ""),
            user_id=data.get("user_id", ""),
            input_content=data.get("input_content", ""),
            output_content=data.get("output_content", ""),
            variables=data.get("variables", {}),
            quality_score=data.get("quality_score", 0.0),
            response_time=data.get("response_time", 0.0),
            success=data.get("success", True),
            feedback=data.get("feedback", ""),
            created_at=data.get("created_at", "")
        )
