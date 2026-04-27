"""
智能提示系统 — 轻量 Hermes 润色器
==================================
<80 Token 做口语化 + Emoji 包装

特性：
- 网络差时降级直接展示模板
- 使用 SmolLM2 本地润色
- 严格控制 Token 数量
"""

import json
import threading
from typing import Optional, Callable, Dict, Any, List
from datetime import datetime

from .models import ContextInfo, GeneratedHint, HintLevel


class LightweightPolisher:
    """
    轻量润色器

    功能：
    1. 口语化包装（加共情词）
    2. Emoji 优化
    3. Token 数量控制
    4. 网络熔断降级
    """

    # 润色系统提示词（极简版）
    POLISH_PROMPT = """把下面提示口语化、加 Emoji，<30字：
{original}

输出格式：Emoji + 内容
直接输出，不要解释"""

    # 共情词库
    EMPATHY_PREFIXES = [
        "嘿~",
        "诶~",
        "哎~",
        "看你的~",
        "注意到~",
        "感觉~",
        "好像~",
    ]

    # 鼓励词库
    ENCOURAGEMENT = [
        "加油哦~",
        "你可以的~",
        "别急~",
        "没关系的~",
        "慢慢来~",
    ]

    # Emoji 映射
    CONTEXT_EMOJIS = {
        "network": "🌊",
        "memory": "💾",
        "cpu": "🧠",
        "speed": "⚡",
        "success": "🎉",
        "error": "😅",
        "warning": "⚠️",
        "tip": "💡",
        "help": "🤝",
        "learn": "📚",
    }

    def __init__(self, local_client=None):
        self._client = local_client
        self._use_local = True
        self._consecutive_failures = 0
        self._max_failures_before_degrade = 3

    def set_client(self, client):
        """设置本地模型客户端"""
        self._client = client

    def _get_client(self):
        """获取本地模型客户端"""
        if self._client is not None:
            return self._client

        if not self._use_local:
            return None

        try:
            from client.src.business.smolllm2 import get_l0_router
            return get_l0_router()
        except ImportError:
            try:
                from client.src.business.system_brain import get_system_brain
                return get_system_brain()
            except ImportError:
                return None

    def polish(self, hint: GeneratedHint, context: ContextInfo = None) -> GeneratedHint:
        """
        润色提示

        Args:
            hint: 原始提示
            context: 上下文信息

        Returns:
            润色后的提示
        """
        # 如果连续失败次数过多，降级
        if self._consecutive_failures >= self._max_failures_before_degrade:
            return self._polish_locally(hint, context)

        # 尝试本地模型润色
        result = self._polish_with_model(hint, context)
        if result:
            self._consecutive_failures = 0
            return result

        # 降级到本地润色
        self._consecutive_failures += 1
        return self._polish_locally(hint, context)

    def _polish_with_model(
        self,
        hint: GeneratedHint,
        context: ContextInfo = None
    ) -> Optional[GeneratedHint]:
        """使用本地模型润色"""
        client = self._get_client()
        if not client:
            return None

        try:
            # 构建提示词
            prompt = self.POLISH_PROMPT.format(original=hint.content)

            # 调用本地模型
            response = None
            if hasattr(client, "generate"):
                response = client.generate(prompt, max_tokens=60)
            elif hasattr(client, "quick_route"):
                resp = client.quick_route(prompt)
                if hasattr(resp, "route"):
                    response = str(resp.route)

            if not response:
                return None

            # 解析响应
            text = str(response).strip()

            # 确保有 Emoji
            emoji = self._extract_emoji(text) or hint.emoji
            content = text.replace(emoji, "", 1).strip() if emoji in text else text

            # 更新提示
            hint.content = content
            hint.emoji = emoji
            hint.source = "polished"

            return hint

        except Exception as e:
            print(f"Polisher model error: {e}")
            return None

    def _polish_locally(
        self,
        hint: GeneratedHint,
        context: ContextInfo = None
    ) -> GeneratedHint:
        """
        本地润色（不调用模型）

        策略：
        1. 提取关键词匹配 Emoji
        2. 添加共情前缀
        3. 口语化调整
        """
        content = hint.content
        emoji = hint.emoji

        # 1. Emoji 优化
        if context and context.device_info:
            for key, emoji in self.CONTEXT_EMOJIS.items():
                if key in context.device_info:
                    emoji = emoji
                    break

        # 2. 添加共情前缀（随机）
        if context:
            prefix_idx = hash(context.scene_id) % len(self.EMPATHY_PREFIXES)
            prefix = self.EMPATHY_PREFIXES[prefix_idx]

            # 如果没有共情词，加一个
            has_empathy = any(p in content for p in ["你", "你的", "嘿", "诶", "哦", "～", "吧"])
            if not has_empathy:
                content = f"{prefix} {content}"

        # 3. 口语化调整
        content = self._casualize(content)

        hint.content = content
        hint.emoji = emoji
        hint.source = "local_polish"

        return hint

    def _extract_emoji(self, text: str) -> Optional[str]:
        """提取 Emoji"""
        import re
        emojis = re.findall(r'[\U0001F300-\U0001F9FF]', text)
        if emojis:
            return emojis[0]
        return None

    def _casualize(self, text: str) -> str:
        """口语化"""
        # 句尾标点
        if text and text[-1] not in "。！？～":
            text = text + "～"

        # 去正式化
        replacements = [
            ("推荐", "推荐～"),
            ("建议", "建议～"),
            ("可以", "可以～"),
            ("使用", "用"),
            ("进行", "做"),
        ]
        for old, new in replacements:
            text = text.replace(old, new)

        return text

    def is_degraded(self) -> bool:
        """是否处于降级模式"""
        return self._consecutive_failures >= self._max_failures_before_degrade

    def reset_degrade(self) -> None:
        """重置降级状态"""
        self._consecutive_failures = 0


class HermesPolisher:
    """
    Hermes 风格润色

    专门处理"和它聊聊"场景
    """

    SYSTEM_PROMPT = """你是小叶子 🌿，一个温暖的朋友。

特点：
- 口语化，简短
- 用 Emoji
- 关心用户感受
- <50字

用户在说：{user_input}

回复："""

    def __init__(self, polisher: LightweightPolisher = None):
        self._polisher = polisher or LightweightPolisher()
        self._client = None

    def chat(
        self,
        user_input: str,
        scene_id: str,
        context: ContextInfo = None
    ) -> str:
        """
        聊天回复

        用于"和它聊聊"场景
        """
        client = self._get_client()

        try:
            prompt = self.SYSTEM_PROMPT.format(user_input=user_input)
            response = None

            if hasattr(client, "generate"):
                response = client.generate(prompt, max_tokens=80)
            elif hasattr(client, "quick_route"):
                resp = client.quick_route(prompt)
                if hasattr(resp, "route"):
                    response = str(resp.route)

            if response:
                return str(response).strip()

        except Exception as e:
            print(f"Hermes chat error: {e}")

        # 降级回复
        return self._fallback_chat(user_input, scene_id)

    def _fallback_chat(self, user_input: str, scene_id: str) -> str:
        """降级聊天回复"""
        fallbacks = {
            "model_select": "选模型这事，看你需求～想要稳定快速就用本地 Ollama，想要能力强就选云模型 🌿",
            "chat": "聊天这事我也挺擅长的，有什么想聊的？ 🌿",
            "writing": "写作遇到问题了？说说看，我帮你想想～ 🌿",
            "network_issue": "网络不稳定确实烦人，先用本地功能吧，我随时在～ 🌿",
            "low_performance": "系统有点慢？关掉一些后台任务会好很多哦～ 🌿",
        }
        return fallbacks.get(scene_id, "嗯嗯，我明白了～有什么需要帮忙的尽管说 🌿")

    def _get_client(self):
        """获取客户端"""
        if self._client:
            return self._client

        try:
            from client.src.business.smolllm2 import get_l0_router
            return get_l0_router()
        except ImportError:
            try:
                from client.src.business.system_brain import get_system_brain
                return get_system_brain()
            except ImportError:
                return None


# 全局单例
_polisher: Optional[LightweightPolisher] = None
_hermes: Optional[HermesPolisher] = None


def get_polisher() -> LightweightPolisher:
    global _polisher
    if _polisher is None:
        _polisher = LightweightPolisher()
    return _polisher


def get_hermes_polisher() -> HermesPolisher:
    global _hermes
    if _hermes is None:
        _hermes = HermesPolisher(get_polisher())
    return _hermes
