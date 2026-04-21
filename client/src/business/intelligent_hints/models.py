"""
智能提示系统 — 数据模型
=======================
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime


class HintLevel(Enum):
    """提示层级"""
    # 透明层 — 完全不打扰，仅记录
    TRANSPARENT = "transparent"
    # 微光层 — 安静存在，悬停可见
    GLOW = "glow"
    # 轻柔层 — 右下角小卡片，不遮挡
    # 轻柔层 — 右下角小卡片，不遮挡
    GENTLE = "gentle"
    # 重要层 — 明确提示，需要关注
    IMPORTANT = "important"
    # 紧急层 — 立即处理，不容忽视
    URGENT = "urgent"


class HintType(Enum):
    """提示类型"""
    # 场景相关
    SCENE_ENTRY = "scene_entry"          # 进入场景
    SCENE_EXIT = "scene_exit"            # 离开场景
    SCENE_HINT = "scene_hint"            # 场景内提示

    # 操作建议
    ACTION_SUGGESTION = "action_suggestion"  # 操作建议
    ACTION_WARNING = "action_warning"        # 操作警告
    ACTION_SHORTCUT = "action_shortcut"      # 快捷键提示

    # 决策支持
    DECISION_SUPPORT = "decision_support"    # 决策支持
    COMPARISON_HINT = "comparison_hint"     # 对比提示
    RECOMMENDATION = "recommendation"       # 推荐建议

    # 智能伴随
    PROACTIVE_HELP = "proactive_help"        # 主动帮助
    CONTEXT_REMINDER = "context_reminder"    # 上下文提醒
    LEARNING_HINT = "learning_hint"          # 学习提示

    # 情感陪伴
    ENCOURAGEMENT = "encouragement"          # 鼓励
    CELEBRATION = "celebration"              # 庆祝成功
    COMFORT = "comfort"                      # 安慰


@dataclass
class ContextInfo:
    """
    情境信息 — AI 感知到的用户当前状态
    """
    # 场景标识
    scene_id: str                     # 如 "model_select", "chat", "writing"
    scene_name: str                   # 场景中文名
    scene_type: str = "unknown"       # 场景类型: page/operation/dialog/background

    # 用户状态
    user_action: str = ""             # 当前操作
    user_goal: str = ""               # 用户目标
    user_history: List[str] = field(default_factory=list)  # 最近操作历史

    # 环境信息
    device_info: Dict[str, Any] = field(default_factory=dict)  # 设备性能/网络等
    app_state: Dict[str, Any] = field(default_factory=dict)    # 应用状态
    options: List[str] = field(default_factory=list)          # 当前选项列表

    # 时间戳
    timestamp: datetime = field(default_factory=datetime.now)

    # 用户画像（来自记忆宫殿）
    user_profile: Dict[str, Any] = field(default_factory=dict)

    # 优先级
    urgency: float = 0.5              # 0.0-1.0，紧急程度
    importance: float = 0.5           # 0.0-1.0，重要程度

    def to_dict(self) -> dict:
        return {
            "scene_id": self.scene_id,
            "scene_name": self.scene_name,
            "scene_type": self.scene_type,
            "user_action": self.user_action,
            "user_goal": self.user_goal,
            "user_history": self.user_history[-5:],  # 最近5条
            "device_info": self.device_info,
            "app_state": self.app_state,
            "options": self.options,
            "timestamp": self.timestamp.isoformat(),
            "user_profile": self.user_profile,
            "urgency": self.urgency,
            "importance": self.importance,
        }


@dataclass
class GeneratedHint:
    """
    生成的提示 — 最终呈现给用户的 AI 提示
    """
    # 基础信息
    hint_id: str
    hint_type: HintType
    hint_level: HintLevel

    # 内容（Markdown 支持）
    title: str                        # 标题（可选）
    content: str                     # 主体内容
    emoji: str = "💡"                # 图标

    # 关联
    context: Optional[ContextInfo] = None  # 触发情境
    related_actions: List[str] = field(default_factory=list)  # 相关操作建议

    # 元数据
    source: str = "intent_engine"     # 来源: template/intent_engine/user_profile
    confidence: float = 1.0          # 置信度 0.0-1.0
    generated_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None  # 过期时间

    # 状态
    is_read: bool = False
    is_dismissed: bool = False
    is_actioned: bool = False

    def to_dict(self) -> dict:
        return {
            "hint_id": self.hint_id,
            "hint_type": self.hint_type.value,
            "hint_level": self.hint_level.value,
            "title": self.title,
            "content": self.content,
            "emoji": self.emoji,
            "source": self.source,
            "confidence": self.confidence,
            "generated_at": self.generated_at.isoformat(),
            "is_read": self.is_read,
        }

    @property
    def display_text(self) -> str:
        """格式化显示文本"""
        if self.title:
            return f"{self.emoji} {self.title}\n{self.content}"
        return f"{self.emoji} {self.content}"


@dataclass
class HintConfig:
    """提示系统配置"""
    # 开关
    enabled: bool = True

    # 显示设置
    show_air_icon: bool = True        # 显示空气图标
    air_icon_position: str = "top_right"  # top_right / top_left / bottom_right / bottom_left
    max_visible_hints: int = 3        # 最多同时显示的提示数

    # 层级阈值
    auto_show_level: HintLevel = HintLevel.GLOW  # 自动显示的最低层级
    requires_action_level: HintLevel = HintLevel.IMPORTANT  # 需要用户操作的层级

    # 动画设置
    breath_animation: bool = True     # 呼吸动画
    fade_in_duration: int = 300      # 淡入时长(ms)
    fade_out_duration: int = 200     # 淡出时长(ms)
    auto_hide_delay: int = 8000       # 自动隐藏延迟(ms)

    # 生成设置
    use_local_model: bool = True      # 使用本地模型生成
    local_model_name: str = "smolllm2:135m"  # 本地快脑模型
    fallback_to_templates: bool = True  # 本地失败时回退到模板
    generate_interval: int = 5000    # 生成检查间隔(ms)

    # 记忆设置
    learn_from_user: bool = True      # 从用户行为学习
    remember_dismissed: bool = True   # 记住用户忽略的提示
    preference_decay: float = 0.95     # 偏好衰减因子

    # 声音设置（预留TTS接口）
    tts_enabled: bool = False
    tts_rate: float = 1.0

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "show_air_icon": self.show_air_icon,
            "air_icon_position": self.air_icon_position,
            "max_visible_hints": self.max_visible_hints,
            "auto_show_level": self.auto_show_level.value,
            "breath_animation": self.breath_animation,
            "fade_in_duration": self.fade_in_duration,
            "fade_out_duration": self.fade_out_duration,
            "auto_hide_delay": self.auto_hide_delay,
            "use_local_model": self.use_local_model,
            "local_model_name": self.local_model_name,
            "learn_from_user": self.learn_from_user,
            "remember_dismissed": self.remember_dismissed,
            "tts_enabled": self.tts_enabled,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "HintConfig":
        data = data.copy()
        if "auto_show_level" in data:
            data["auto_show_level"] = HintLevel(data["auto_show_level"])
        return cls(**data)
