"""
Conversational Clarifier - 主动需求引导系统

在聊天/写作等交互场景中，定期检测用户需求是否模糊，
主动询问是否需要头脑风暴来明确需求。

核心原则：
1. 不打断 - 只在自然时机询问，不阻断用户操作
2. 可拒绝 - 用户拒绝后临时关闭，不反复询问
3. 一次一问 - 每次只问一个问题
4. 与IdeaClarifier集成 - 使用已有的头脑风暴框架
"""

import re
import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Callable, List
from pathlib import Path
import json


class PromptStyle(Enum):
    """引导风格"""
    GENTLE = "gentle"           # 温和询问
    SUGGESTIVE = "suggestive"   # 建议型
    DIRECT = "direct"           # 直接型


@dataclass
class ClarifyPrompt:
    """引导提示"""
    style: PromptStyle
    message: str
    options: List[str] = field(default_factory=list)  # 选项列表

    def to_card_text(self) -> str:
        """转换为卡片显示文本"""
        if self.options:
            options_text = "\n".join(f"[{i+1}] {opt}" for i, opt in enumerate(self.options))
            return f"{self.message}\n\n{options_text}"
        return self.message


@dataclass
class InteractionRecord:
    """交互记录"""
    role: str  # "user" / "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)
    was_ambiguous: bool = False  # 是否被判定为模糊需求
    clarified: bool = False      # 是否经过头脑风暴澄清


class ConversationalClarifier:
    """
    对话式需求澄清引导器

    工作机制：
    1. 监听用户消息
    2. 检测需求模糊度
    3. 定期触发引导询问
    4. 用户拒绝后冷却
    """

    # 模糊需求关键词（中文）
    AMBIGUOUS_PATTERNS = [
        # 任务类模糊词
        r"帮我做",
        r"搞一下",
        r"弄一下",
        r"处理一下",
        r"看看",
        r"检查检查",
        r"优化优化",
        r"整理整理",
        r"搞个",
        r"弄个",
        r"做个",
        # 缺少具体规格
        r"和原来一样",
        r"跟之前一样",
        r"差不多就行",
        r"简单弄一下",
        r"随便",
        # 询问类但缺乏上下文
        r"这个行不行",
        r"那个行不行",
        r"能不能",
        r"可以不",
        # 项目/任务模糊描述
        r"项目",
        r"功能",
        r"模块",
        r"系统",
    ]

    # 明确需求关键词
    CLEAR_PATTERNS = [
        r"具体是",
        r"具体来说",
        r"详细需求",
        r"规格如下",
        r"需求如下",
        r"目标是",
        r"实现步骤",
        r"界面包括",
        r"输入.*输出",
        r"用户名.*密码",
        r"API.*endpoint",
    ]

    def __init__(self, config_path: Optional[str] = None):
        self.clarifier = None  # 延迟导入，避免循环引用

        # 配置
        self._enabled = True
        self._prompt_interval = 3  # 每隔几次用户消息触发一次引导
        self._cooldown = 300  # 拒绝后冷却5分钟
        self._last_prompt_time = 0
        self._last_reject_time = 0
        self._user_interaction_count = 0
        self._interaction_history: List[InteractionRecord] = []

        # 用户偏好存储
        self._pref_path = Path(config_path) if config_path else self._get_default_pref_path()
        self._load_preferences()

        # 当前活跃的头脑风暴会话
        self._active_session_id: Optional[str] = None

    def _get_default_pref_path(self) -> Path:
        """获取默认偏好存储路径"""
        base = Path.home() / ".workbuddy"
        base.mkdir(parents=True, exist_ok=True)
        return base / "clarifier_prefs.json"

    def _load_preferences(self):
        """加载用户偏好"""
        try:
            if self._pref_path.exists():
                with open(self._pref_path, "r", encoding="utf-8") as f:
                    prefs = json.load(f)
                    self._enabled = prefs.get("enabled", True)
                    self._cooldown = prefs.get("cooldown", 300)
        except Exception:
            pass

    def _save_preferences(self):
        """保存用户偏好"""
        try:
            prefs = {
                "enabled": self._enabled,
                "cooldown": self._cooldown
            }
            with open(self._pref_path, "w", encoding="utf-8") as f:
                json.dump(prefs, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _init_clarifier(self):
        """延迟初始化IdeaClarifier"""
        if self.clarifier is None:
            try:
                from business.idea_clarifier import get_idea_clarifier
                self.clarifier = get_idea_clarifier()
            except ImportError:
                self.clarifier = None

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    @property
    def is_in_cooldown(self) -> bool:
        """是否在冷却期"""
        if time.time() - self._last_reject_time < self._cooldown:
            return True
        return False

    def enable(self):
        """启用引导"""
        self._enabled = True
        self._save_preferences()

    def disable(self):
        """禁用引导"""
        self._enabled = False
        self._save_preferences()

    def record_interaction(self, role: str, content: str):
        """记录一次交互"""
        if role == "user":
            self._user_interaction_count += 1

        record = InteractionRecord(role=role, content=content)
        record.was_ambiguous = self._is_ambiguous(content)
        self._interaction_history.append(record)

        # 保持历史记录在合理范围
        if len(self._interaction_history) > 50:
            self._interaction_history = self._interaction_history[-50:]

    def _is_ambiguous(self, text: str) -> bool:
        """检测文本是否模糊/缺乏具体规格"""
        text_lower = text.lower()

        # 检查模糊模式
        ambiguous_count = sum(1 for p in self.AMBIGUOUS_PATTERNS
                             if re.search(p, text_lower))
        if ambiguous_count > 0:
            return True

        # 检查是否缺乏明确规格
        clear_count = sum(1 for p in self.CLEAR_PATTERNS
                         if re.search(p, text_lower))
        if clear_count == 0 and len(text) < 100:
            return True

        return False

    def should_prompt(self) -> bool:
        """
        判断是否应该触发引导提示

        条件：
        1. 功能已启用
        2. 不在冷却期
        3. 距离上次提示有足够间隔
        4. 达到触发间隔
        """
        if not self._enabled:
            return False

        if self.is_in_cooldown:
            return False

        # 每隔N次用户交互触发一次
        if self._user_interaction_count % self._prompt_interval == 0:
            # 检查最近的消息是否足够模糊
            recent_user_msgs = [r for r in self._interaction_history[-5:]
                               if r.role == "user"]
            if recent_user_msgs and any(r.was_ambiguous for r in recent_user_msgs):
                return True

        return False

    def get_prompt(self) -> ClarifyPrompt:
        """获取当前应该显示的引导提示"""
        self._init_clarifier()

        recent_content = ""
        if self._interaction_history:
            recent = self._interaction_history[-3:]
            recent_content = " ".join(r.content for r in recent if r.role == "user")

        # 根据模糊程度选择提示风格
        if self._is_ambiguous(recent_content):
            style = PromptStyle.SUGGESTIVE
            message = (
                "💡 我注意到你刚才的描述比较简略。\n\n"
                "为了确保我理解正确，是否需要我们做一个快速的需求头脑风暴？\n"
                "这可以帮助你把想法更清晰地表达出来。"
            )
        else:
            style = PromptStyle.GENTLE
            message = (
                "💡 在我们继续之前，\n\n"
                "你是否希望我帮你梳理一下需求？\n"
                "有时候花1-2分钟明确需求，可以节省后续很多时间。"
            )

        options = [
            "好，帮我梳理需求",
            "不用，继续当前话题",
            "以后再说"
        ]

        return ClarifyPrompt(style=style, message=message, options=options)

    def on_user_response(self, response: str):
        """
        处理用户对引导提示的响应

        Args:
            response: 用户选择的选项编号或文本
        """
        self._last_prompt_time = time.time()

        # 解析响应
        if response in ["1", "好，帮我梳理需求", "是", "好"]:
            # 用户同意，启动头脑风暴
            self._start_clarification()
        elif response in ["2", "不用，继续当前话题"]:
            # 暂时关闭，设置较短冷却
            self._last_reject_time = time.time()
        elif response in ["3", "以后再说"]:
            # 禁用一段时间
            self._enabled = False
            self._save_preferences()

    def _start_clarification(self):
        """启动头脑风暴会话"""
        self._init_clarifier()
        if self.clarifier:
            # 获取最近的对话上下文
            context = self._build_context_for_clarifier()
            session = self.clarifier.create_session(initial_topic=context)
            self._active_session_id = session.session_id
        else:
            # 没有IdeaClarifier时，创建简单会话
            self._active_session_id = f"simple_{int(time.time())}"

    def _build_context_for_clarifier(self) -> str:
        """构建头脑风暴上下文"""
        recent = self._interaction_history[-10:]
        lines = []
        for r in recent:
            role = "用户" if r.role == "user" else "助手"
            lines.append(f"{role}: {r.content}")

        return "\n".join(lines)

    def get_active_session_id(self) -> Optional[str]:
        """获取当前活跃的头脑风暴会话ID"""
        return self._active_session_id

    def close_active_session(self):
        """关闭当前头脑风暴会话"""
        self._active_session_id = None

    def get_clarifier(self):
        """获取IdeaClarifier实例"""
        self._init_clarifier()
        return self.clarifier

    def get_stats(self) -> dict:
        """获取统计信息"""
        total = len(self._interaction_history)
        user_msgs = sum(1 for r in self._interaction_history if r.role == "user")
        ambiguous = sum(1 for r in self._interaction_history if r.was_ambiguous)

        return {
            "enabled": self._enabled,
            "total_interactions": total,
            "user_messages": user_msgs,
            "ambiguous_count": ambiguous,
            "in_cooldown": self.is_in_cooldown,
            "active_session": self._active_session_id is not None
        }


# ============ 全局单例 ============

_instance: Optional[ConversationalClarifier] = None


def get_conversational_clarifier() -> ConversationalClarifier:
    """获取全局实例"""
    global _instance
    if _instance is None:
        _instance = ConversationalClarifier()
    return _instance


def reset_clarifier():
    """重置实例（用于测试）"""
    global _instance
    _instance = None