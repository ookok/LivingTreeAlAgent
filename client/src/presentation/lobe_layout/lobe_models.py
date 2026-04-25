"""
Lobe 风格会话数据模型

定义会话类型、技能绑定、状态流等核心数据
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import uuid
import time


class SessionType(Enum):
    """会话类型"""
    TRADE = "trade"           # 电商咨询
    CODE = "code"             # 代码助手
    SEARCH = "search"         # 全网搜索
    RAG = "rag"               # 文档库/RAG
    PERSONA = "persona"       # 角色对话
    CUSTOM = "custom"         # 自定义


class SkillCategory(Enum):
    """技能类别"""
    SEARCH = "search"         # 搜索与联网
    AI_MODEL = "ai_model"     # AI 模型路由
    PERSONA = "persona"       # 角色技能
    TOOL = "tool"            # 工具能力
    MEMORY = "memory"         # 记忆能力


@dataclass
class SkillBinding:
    """技能绑定"""
    skill_id: str
    name: str
    category: SkillCategory
    description: str
    icon: str = "🔧"
    enabled: bool = False
    config_keys: dict = field(default_factory=dict)  # 后端配置键值对


@dataclass
class SessionConfig:
    """会话配置"""
    session_type: SessionType
    name: str
    icon: str
    description: str
    default_skills: list[str] = field(default_factory=list)  # 默认启用的技能ID
    system_prompt: str = ""
    model_hint: str = ""  # 推荐的模型


@dataclass
class ChatMessage:
    """聊天消息"""
    msg_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    role: str = "user"  # user/assistant/system
    content: str = ""
    timestamp: float = field(default_factory=time.time)
    status: str = "sent"  # sending/sent/error
    skill_used: list[str] = field(default_factory=list)  # 使用的技能
    token_count: int = 0


@dataclass
class StatusFlowStep:
    """状态流步骤"""
    icon: str
    label: str
    status: str = "idle"  # idle/running/success/error
    duration_ms: float = 0.0


@dataclass
class LobeSession:
    """Lobe 风格会话"""
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    config: Optional[SessionConfig] = None
    messages: list[ChatMessage] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    is_active: bool = False

    # 当前激活的技能
    active_skills: list[str] = field(default_factory=list)


# ==================== 内置会话配置 ====================

SESSION_PRESETS: dict[SessionType, SessionConfig] = {
    SessionType.TRADE: SessionConfig(
        session_type=SessionType.TRADE,
        name="电商咨询",
        icon="💬",
        description="买卖对话、报价谈判、选品建议",
        default_skills=["colleague_sales", "memory_palace"],
        system_prompt="你是一名资深电商销售专家，精通SPIN法则和报价谈判技巧。",
        model_hint="deepseek"
    ),
    SessionType.CODE: SessionConfig(
        session_type=SessionType.CODE,
        name="代码助手",
        icon="💻",
        description="代码生成、调试、架构设计",
        default_skills=["colleague_architect", "smollm2_router"],
        system_prompt="你是一名资深架构师，擅长系统设计和代码评审。",
        model_hint="qwen"
    ),
    SessionType.SEARCH: SessionConfig(
        session_type=SessionType.SEARCH,
        name="全网搜索",
        icon="🌐",
        description="联网搜索、新闻资讯、竞品分析",
        default_skills=["agent_reach", "p2p_proxy"],
        system_prompt="你是一名专业的信息检索助手，善于从全网获取最新资讯。",
        model_hint="smollm2"
    ),
    SessionType.RAG: SessionConfig(
        session_type=SessionType.RAG,
        name="文档库",
        icon="📦",
        description="本地文档检索、知识库问答",
        default_skills=["fusion_rag", "memory_palace"],
        system_prompt="你是一名知识库管理员，擅长从文档中提取关键信息。",
        model_hint="qwen"
    ),
    SessionType.PERSONA: SessionConfig(
        session_type=SessionType.PERSONA,
        name="角色对话",
        icon="🧙",
        description="与预设角色对话（乔布斯/马斯克/纳瓦尔等）",
        default_skills=["persona_skill"],
        system_prompt="你正在与一个传奇人物对话。",
        model_hint="deepseek"
    ),
}


# ==================== 内置技能绑定 ====================

SKILL_PRESETS: dict[str, SkillBinding] = {
    # 搜索类
    "agent_reach": SkillBinding(
        skill_id="agent_reach",
        name="Agent-Reach 搜索",
        category=SkillCategory.SEARCH,
        description="免费联网搜索，支持 Twitter/GitHub/Reddit",
        icon="🔍",
        config_keys={"search_backend": "agent_reach"}
    ),
    "p2p_proxy": SkillBinding(
        skill_id="p2p_proxy",
        name="P2P 外网代理",
        category=SkillCategory.SEARCH,
        description="通过外网节点路由搜索请求",
        icon="🌐",
        config_keys={"search_mode": "p2p"}
    ),
    "smollm2_router": SkillBinding(
        skill_id="smollm2_router",
        name="SmolLM2 轻量路由",
        category=SkillCategory.AI_MODEL,
        description="本地意图识别，<1s 响应",
        icon="⚡",
        config_keys={"router": "smollm2"}
    ),
    "deepseek": SkillBinding(
        skill_id="deepseek",
        name="DeepSeek 深度推理",
        category=SkillCategory.AI_MODEL,
        description="复杂推理、长篇写作",
        icon="🧠",
        config_keys={"model": "deepseek"}
    ),
    # 角色类
    "colleague_sales": SkillBinding(
        skill_id="colleague_sales",
        name="金牌销售同事",
        category=SkillCategory.PERSONA,
        description="SPIN法则、报价谈判话术",
        icon="👔",
        config_keys={"persona": "colleague_sales"}
    ),
    "colleague_architect": SkillBinding(
        skill_id="colleague_architect",
        name="架构师同事",
        category=SkillCategory.PERSONA,
        description="系统设计、代码评审",
        icon="🏗️",
        config_keys={"persona": "colleague_architect"}
    ),
    "jobs": SkillBinding(
        skill_id="jobs",
        name="乔布斯",
        category=SkillCategory.PERSONA,
        description="极简主义产品思维",
        icon="🍎",
        config_keys={"persona": "jobs"}
    ),
    "musk": SkillBinding(
        skill_id="musk",
        name="马斯克",
        category=SkillCategory.PERSONA,
        description="第一性原理、10倍思维",
        icon="🚀",
        config_keys={"persona": "musk"}
    ),
    "naval": SkillBinding(
        skill_id="naval",
        name="纳瓦尔",
        category=SkillCategory.PERSONA,
        description="财富杠杆、复利决策",
        icon="💰",
        config_keys={"persona": "naval"}
    ),
    # 记忆类
    "memory_palace": SkillBinding(
        skill_id="memory_palace",
        name="记忆宫殿",
        category=SkillCategory.MEMORY,
        description="跨会话上下文记忆",
        icon="🏛️",
        config_keys={"memory": "palace"}
    ),
    "fusion_rag": SkillBinding(
        skill_id="fusion_rag",
        name="FusionRAG 检索",
        category=SkillCategory.MEMORY,
        description="多源知识融合检索",
        icon="📦",
        config_keys={"rag": "fusion"}
    ),
    # 工具类
    "persona_skill": SkillBinding(
        skill_id="persona_skill",
        name="角色智库",
        category=SkillCategory.TOOL,
        description="13+ 预设人格角色",
        icon="🧙",
        config_keys={"skills": ["persona_skill"]}
    ),
}
