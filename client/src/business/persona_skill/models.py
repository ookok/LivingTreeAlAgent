# -*- coding: utf-8 -*-
"""
Persona Skill 数据模型
角色智库核心数据结构
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime


class PersonaCategory(Enum):
    """角色类别"""
    SALES = "sales"           # 销售类
    TECHNICAL = "technical"    # 技术类
    DECISION = "decision"     # 决策类
    MANAGEMENT = "management" # 管理类
    CREATIVE = "creative"     # 创意类
    EMOTIONAL = "emotional"   # 情感类
    ENTERTAINMENT = "entertainment"  # 娱乐类


class PersonaTier(Enum):
    """角色等级"""
    LEGEND = "legend"         # 传奇 (乔布斯、马斯克)
    MASTER = "master"         # 大师 (纳瓦尔、芒格)
    EXPERT = "expert"         # 专家 (销售总监、风控专家)
    COLLEAGUE = "colleague"   # 同事 (可蒸馏本人/同事)
    CUSTOM = "custom"         # 自定义


@dataclass
class PersonaVariable:
    """角色变量定义"""
    name: str                 # 变量名
    description: str          # 描述
    default_value: str        # 默认值
    type: str = "str"         # 类型: str/int/float/bool


@dataclass
class PersonaTrigger:
    """触发条件"""
    keywords: List[str]       # 关键词列表
    intent: str               # 意图标识
    confidence: float = 0.7   # 最低置信度


@dataclass
class PersonaSkill:
    """Persona Skill 数据结构"""
    id: str                   # 唯一标识 (如 "jobs", "musk", "colleague_sales")
    name: str                 # 显示名称 (如 "乔布斯", "金牌销售同事")
    description: str          # 角色描述
    category: PersonaCategory # 类别
    tier: PersonaTier         # 等级
    icon: str                 # 图标 emoji

    # 核心内容
    system_prompt: str         # 系统提示词模板
    user_prompt_template: str # 用户输入模板

    # 变量
    variables: List[PersonaVariable] = field(default_factory=list)

    # 触发
    triggers: List[PersonaTrigger] = field(default_factory=list)

    # 元数据
    star: int = 0             # GitHub Star 数
    author: str = ""          # 作者
    version: str = "1.0"      # 版本
    tags: List[str] = field(default_factory=list)

    # 状态
    is_builtin: bool = True   # 是否内置
    is_active: bool = True    # 是否启用
    usage_count: int = 0      # 使用次数
    last_used: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "tier": self.tier.value,
            "icon": self.icon,
            "system_prompt": self.system_prompt,
            "user_prompt_template": self.user_prompt_template,
            "variables": [
                {"name": v.name, "description": v.description, "default": v.default_value, "type": v.type}
                for v in self.variables
            ],
            "triggers": [
                {"keywords": t.keywords, "intent": t.intent, "confidence": t.confidence}
                for t in self.triggers
            ],
            "star": self.star,
            "author": self.author,
            "version": self.version,
            "tags": self.tags,
            "is_builtin": self.is_builtin,
            "is_active": self.is_active,
            "usage_count": self.usage_count,
            "last_used": self.last_used.isoformat() if self.last_used else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PersonaSkill":
        variables = [
            PersonaVariable(name=v["name"], description=v["description"], default_value=v.get("default", ""), type=v.get("type", "str"))
            for v in data.get("variables", [])
        ]
        triggers = [
            PersonaTrigger(keywords=t["keywords"], intent=t["intent"], confidence=t.get("confidence", 0.7))
            for t in data.get("triggers", [])
        ]
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            category=PersonaCategory(data.get("category", "technical")),
            tier=PersonaTier(data.get("tier", "expert")),
            icon=data.get("icon", "🤖"),
            system_prompt=data.get("system_prompt", ""),
            user_prompt_template=data.get("user_prompt_template", "{task}"),
            variables=variables,
            triggers=triggers,
            star=data.get("star", 0),
            author=data.get("author", ""),
            version=data.get("version", "1.0"),
            tags=data.get("tags", []),
            is_builtin=data.get("is_builtin", True),
            is_active=data.get("is_active", True),
            usage_count=data.get("usage_count", 0),
            last_used=datetime.fromisoformat(data["last_used"]) if data.get("last_used") else None,
        )


@dataclass
class PersonaSession:
    """Persona 对话会话"""
    id: str
    persona_id: str
    messages: List[Dict[str, str]] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        self.updated_at = datetime.now()


@dataclass
class PersonaInvokeResult:
    """Persona 调用结果"""
    success: bool
    response: str
    persona_id: str
    persona_name: str
    tokens_used: int = 0
    latency_ms: float = 0
    error: Optional[str] = None
