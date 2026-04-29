"""
智能提示系统 — 提示模板库
=========================
温暖、有趣、像朋友一样的提示模板
"""

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Any
from enum import Enum

from .models import ContextInfo, GeneratedHint, HintType, HintLevel


class WarmthFormula:
    """
    温度公式：共情开头 + 利益点 + 行动建议

    示例转换：
    - 冷："推荐 Ollama，因为稳定。"
    - 暖："嘿，看你网络有点波动 🌊，用本地 Ollama 会更稳哦～"
    """

    # 共情开头词
    EMPATHY_STARTERS = [
        "嘿，", "诶，", "哎，", "看你的", "发现",
        "注意到", "看样子", "感觉", "好像"
    ]

    # 鼓励开头词
    ENCOURAGEMENT_STARTERS = [
        "加油！", "你可以的！", "太棒了！", "不错哦～",
        "已经很不错了，", "慢慢来，", "别急，"
    ]

    # Emoji 映射
    EMOJI_MAP = {
        "network": "🌊",
        "memory": "🧠",
        "speed": "⚡",
        "success": "🎉",
        "warning": "⚠️",
        "tip": "💡",
        "help": "🤝",
        "learning": "📚",
        "time": "⏰",
        "cost": "💰",
        "quality": "✨",
        "safe": "🛡️",
        "fast": "🚀",
    }

    @classmethod
    def warm_up(
        cls,
        cold_text: str,
        context: ContextInfo,
        emoji_key: str = None
    ) -> str:
        """将冷冰冰的文本变成温暖的提示"""
        # 添加共情开头
        starter = cls.EMPATHY_STARTERS[hash(context.scene_id) % len(cls.EMPATHY_STARTERS)]

        # 添加 Emoji
        emoji = cls.EMOJI_MAP.get(emoji_key, "💡") if emoji_key else "💡"

        return f"{starter}{emoji} {cold_text}"


@dataclass
class HintTemplate:
    """提示模板"""
    template_id: str
    scene_id: str
    hint_type: HintType
    hint_level: HintLevel

    # 模板内容（支持变量插值）
    title: str = ""
    content_template: str = ""  # 支持 {variable} 插值
    emoji: str = "💡"

    # 适用条件
    conditions: Dict[str, Any] = field(default_factory=dict)

    # 优先级
    priority: int = 0

    def fill(self, context: ContextInfo) -> str:
        """填充模板"""
        content = self.content_template

        # 变量替换
        replacements = {
            "{scene_name}": context.scene_name,
            "{user_action}": context.user_action,
            "{user_goal}": context.user_goal,
            "{options}": ", ".join(context.options[:3]) if context.options else "无",
            "{option_count}": str(len(context.options)),
        }

        # 添加设备信息
        if context.device_info:
            for key, value in context.device_info.items():
                replacements[f"{{{key}}}"] = str(value)

        # 执行替换
        for key, value in replacements.items():
            content = content.replace(key, value)

        # 清理未替换的变量
        content = re.sub(r'\{[^}]+\}', '', content)

        return content


class HintTemplateStore:
    """
    提示模板仓库

    预置大量温暖人心的提示模板，覆盖各种场景
    """

    def __init__(self):
        self._templates: List[HintTemplate] = []
        self._scene_index: Dict[str, List[int]] = {}  # scene_id -> template indices
        self._type_index: Dict[HintType, List[int]] = {}  # hint_type -> template indices

        # 加载内置模板
        self._load_builtin_templates()

    def _load_builtin_templates(self):
        """加载内置模板"""
        templates = self._get_builtin_templates()
        for template in templates:
            self.register_template(template)

    def register_template(self, template: HintTemplate):
        """注册模板"""
        self._templates.append(template)
        idx = len(self._templates) - 1

        # 建立索引
        if template.scene_id not in self._scene_index:
            self._scene_index[template.scene_id] = []
        self._scene_index[template.scene_id].append(idx)

        if template.hint_type not in self._type_index:
            self._type_index[template.hint_type] = []
        self._type_index[template.hint_type].append(idx)

    def get_templates(
        self,
        scene_id: str = None,
        hint_type: HintType = None
    ) -> List[HintTemplate]:
        """获取模板列表"""
        result = self._templates.copy()

        if scene_id:
            indices = self._scene_index.get(scene_id, [])
            result = [result[i] for i in indices if i < len(result)]

        if hint_type:
            indices = self._type_index.get(hint_type, [])
            result = [result[i] for i in indices if i < len(result)]

        # 按优先级排序
        result.sort(key=lambda t: t.priority, reverse=True)
        return result

    def fill_template(
        self,
        template: HintTemplate,
        context: ContextInfo
    ) -> GeneratedHint:
        """填充模板并生成提示"""
        content = template.fill(context)

        # 应用温暖公式（如果需要）
        if template.hint_level in [HintLevel.GLOW, HintLevel.GENTLE]:
            # 检查是否太冷
            is_cold = not any(word in content for word in ["你", "嘿", "诶", "～", "哦", "吧"])
            if is_cold:
                content = WarmthFormula.warm_up(
                    content,
                    context,
                    emoji_key=self._get_emoji_key(template)
                )

        return GeneratedHint(
            hint_id=f"tpl_{template.template_id}_{context.scene_id}",
            hint_type=template.hint_type,
            hint_level=template.hint_level,
            title=template.title,
            content=content,
            emoji=template.emoji,
            context=context,
            source="template",
            confidence=0.9
        )

    def _get_emoji_key(self, template: HintTemplate) -> str:
        """获取 emoji key"""
        if "network" in template.template_id:
            return "network"
        if "memory" in template.template_id:
            return "memory"
        if "speed" in template.template_id:
            return "speed"
        if "warning" in template.template_id:
            return "warning"
        if "tip" in template.template_id:
            return "tip"
        return "help"

    def _get_builtin_templates(self) -> List[HintTemplate]:
        """获取内置模板"""
        return [
            # ═══════════════════════════════════════════════════
            # 模型选择场景
            # ═══════════════════════════════════════════════════
            HintTemplate(
                template_id="model_select_network_poor",
                scene_id="model_select",
                hint_type=HintType.COMPARISON_HINT,
                hint_level=HintLevel.GENTLE,
                title="网络不稳定提示",
                content_template="嘿 🌊 看你网络有点波动，用本地 Ollama 会更稳哦，不怕掉线～",
                emoji="🌊",
                conditions={"network": "poor"},
                priority=100
            ),
            HintTemplate(
                template_id="model_select_free",
                scene_id="model_select",
                hint_type=HintType.RECOMMENDATION,
                hint_level=HintLevel.GLOW,
                title="免费推荐",
                content_template="想省钱 💰？DeepSeek 免费额度够用，中文能力强，不错的选择～",
                emoji="💰",
                conditions={},
                priority=80
            ),
            HintTemplate(
                template_id="model_select_local",
                scene_id="model_select",
                hint_type=HintType.RECOMMENDATION,
                hint_level=HintLevel.GLOW,
                title="本地推荐",
                content_template="想要极速响应 🚀？Ollama 本地运行，零延迟，你的设备带得动～",
                emoji="🚀",
                conditions={},
                priority=70
            ),
            HintTemplate(
                template_id="model_select_powerful",
                scene_id="model_select",
                hint_type=HintType.RECOMMENDATION,
                hint_level=HintLevel.GLOW,
                title="强力推荐",
                content_template="想玩点强的 ✨？OpenRouter 聚合多模型，能力全能，适合尝鲜～",
                emoji="✨",
                conditions={},
                priority=60
            ),
            HintTemplate(
                template_id="model_select_compare",
                scene_id="model_select",
                hint_type=HintType.COMPARISON_HINT,
                hint_level=HintLevel.GLOW,
                title="对比提示",
                content_template="有 {option_count} 个选项可以选 📊，不知道怎么挑？说说你的需求，我帮你参谋～",
                emoji="📊",
                conditions={},
                priority=50
            ),

            # ═══════════════════════════════════════════════════
            # 聊天场景
            # ═══════════════════════════════════════════════════
            HintTemplate(
                template_id="chat_idle",
                scene_id="chat",
                hint_type=HintType.PROACTIVE_HELP,
                hint_level=HintLevel.TRANSPARENT,
                title="等待提示",
                content_template="我在这里等你～有什么想问的，尽管说哦 😊",
                emoji="🤗",
                conditions={},
                priority=10
            ),
            HintTemplate(
                template_id="chat_long_wait",
                scene_id="chat",
                hint_type=HintType.CONTEXT_REMINDER,
                hint_level=HintLevel.GLOW,
                title="长等待提醒",
                content_template="等了一会儿了 🌿，网络可能有点慢，换个模型试试？或者先做点别的？",
                emoji="🌿",
                conditions={},
                priority=40
            ),

            # ═══════════════════════════════════════════════════
            # 写作场景
            # ═══════════════════════════════════════════════════
            HintTemplate(
                template_id="writing_stuck",
                scene_id="writing",
                hint_type=HintType.PROACTIVE_HELP,
                hint_level=HintLevel.GENTLE,
                title="写作瓶颈",
                content_template="✍️ 写作遇到瓶颈了？试试让我帮你整理一下思路，或者换个开头？",
                emoji="✍️",
                conditions={},
                priority=80
            ),
            HintTemplate(
                template_id="writing_long",
                scene_id="writing",
                hint_type=HintType.LEARNING_HINT,
                hint_level=HintLevel.GLOW,
                title="长文提示",
                content_template="📚 写了不少了！要不要休息一下？或者让我帮你检查一下逻辑？",
                emoji="📚",
                conditions={},
                priority=30
            ),

            # ═══════════════════════════════════════════════════
            # 网络问题场景
            # ═══════════════════════════════════════════════════
            HintTemplate(
                template_id="network_poor",
                scene_id="network_issue",
                hint_type=HintType.ACTION_SUGGESTION,
                hint_level=HintLevel.IMPORTANT,
                title="网络恢复建议",
                content_template="🌊 网络不太稳定...先试试本地功能吧，我这边随时待命～",
                emoji="🌊",
                conditions={"network": "poor"},
                priority=100
            ),
            HintTemplate(
                template_id="network_disconnected",
                scene_id="network_issue",
                hint_type=HintType.ACTION_WARNING,
                hint_level=HintLevel.IMPORTANT,
                title="断网警告",
                content_template="⚠️ 好像断网了！先用本地模式吧，有啥能帮的你随时说～",
                emoji="⚠️",
                conditions={"network": "disconnected"},
                priority=100
            ),

            # ═══════════════════════════════════════════════════
            # 性能问题场景
            # ═══════════════════════════════════════════════════
            HintTemplate(
                template_id="perf_high_cpu",
                scene_id="low_performance",
                hint_type=HintType.ACTION_SUGGESTION,
                hint_level=HintLevel.GENTLE,
                title="高CPU提醒",
                content_template="🧠 系统有点累了...关闭点后台任务会更流畅哦～",
                emoji="🧠",
                conditions={"cpu_usage": ">80"},
                priority=80
            ),
            HintTemplate(
                template_id="perf_high_memory",
                scene_id="low_performance",
                hint_type=HintType.ACTION_SUGGESTION,
                hint_level=HintLevel.GENTLE,
                title="高内存提醒",
                content_template="💾 内存有点紧张...清理一下会更舒服～",
                emoji="💾",
                conditions={"memory_usage": ">85"},
                priority=80
            ),

            # ═══════════════════════════════════════════════════
            # 通用场景
            # ═══════════════════════════════════════════════════
            HintTemplate(
                template_id="general_tip",
                scene_id="*",
                hint_type=HintType.PROACTIVE_HELP,
                hint_level=HintLevel.TRANSPARENT,
                title="通用提示",
                content_template="💡 有我陪着你，有问题尽管问～",
                emoji="💡",
                conditions={},
                priority=1
            ),
            HintTemplate(
                template_id="success_celebrate",
                scene_id="*",
                hint_type=HintType.CELEBRATION,
                hint_level=HintLevel.GLOW,
                title="成功庆祝",
                content_template="🎉 太棒了！做得好！继续加油哦～",
                emoji="🎉",
                conditions={},
                priority=90
            ),
            HintTemplate(
                template_id="error_comfort",
                scene_id="*",
                hint_type=HintType.COMFORT,
                hint_level=HintLevel.GENTLE,
                title="错误安慰",
                content_template="没关系的 😅，出错很正常。一起看看哪里出了问题？",
                emoji="😅",
                conditions={},
                priority=95
            ),
            HintTemplate(
                template_id="shortcut_reminder",
                scene_id="*",
                hint_type=HintType.ACTION_SHORTCUT,
                hint_level=HintLevel.TRANSPARENT,
                title="快捷键提示",
                content_template="⌨️ 试试快捷键？Ctrl+L 清空对话，Ctrl+S 保存笔记～",
                emoji="⌨️",
                conditions={},
                priority=20
            ),

            # ═══════════════════════════════════════════════════
            # 设置场景
            # ═══════════════════════════════════════════════════
            HintTemplate(
                template_id="settings_first",
                scene_id="settings",
                hint_type=HintType.LEARNING_HINT,
                hint_level=HintLevel.GLOW,
                title="首次设置",
                content_template="⚙️ 第一次调整设置？有什么不懂的随时问我，我帮你解释～",
                emoji="⚙️",
                conditions={},
                priority=50
            ),

            # ═══════════════════════════════════════════════════
            # 文件操作场景
            # ═══════════════════════════════════════════════════
            HintTemplate(
                template_id="file_delete_warning",
                scene_id="file_operation",
                hint_type=HintType.ACTION_WARNING,
                hint_level=HintLevel.IMPORTANT,
                title="删除警告",
                content_template="⚠️ 真的要删除吗？这个操作可逆，删了就没了哦～",
                emoji="⚠️",
                conditions={"action": "delete"},
                priority=100
            ),
            HintTemplate(
                template_id="file_export_hint",
                scene_id="file_operation",
                hint_type=HintType.ACTION_SUGGESTION,
                hint_level=HintLevel.GLOW,
                title="导出提示",
                content_template="📦 导出文件？建议用 Markdown 格式，方便以后编辑～",
                emoji="📦",
                conditions={"action": "export"},
                priority=50
            ),
        ]


# 全局单例
_store_instance: Optional[HintTemplateStore] = None
_store_lock = None


def get_hint_store() -> HintTemplateStore:
    """获取提示模板仓库单例"""
    global _store_instance
    if _store_instance is None:
        _store_instance = HintTemplateStore()
    return _store_instance
