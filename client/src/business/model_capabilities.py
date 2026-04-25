"""
Model Capabilities - 模型能力检测与匹配
========================================

用于检测和匹配不同模型的能力，支持多模态、思考模式等功能。
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Set, Tuple
import re


class ThinkingCapability(Enum):
    """思考能力等级"""
    NONE = 0           # 无思考能力
    BASIC = 1          # 基础思考
    EXTENDED = 2       # 扩展思考
    DEEP = 3           # 深度思考
    MULTI_STEP = 4     # 多步推理


class MultimodalCapability(Enum):
    """多模态能力"""
    TEXT_ONLY = 0      # 仅文本
    IMAGE_INPUT = 1    # 图片输入
    IMAGE_OUTPUT = 2   # 图片输出
    VIDEO = 3          # 视频
    AUDIO = 4          # 音频
    DOCUMENT = 5       # 文档解析


@dataclass
class ModelCapabilities:
    """模型能力描述"""
    model_name: str
    supports_thinking: bool = False
    thinking_type: ThinkingCapability = ThinkingCapability.NONE

    # 多模态
    multimodal: MultimodalCapability = MultimodalCapability.TEXT_ONLY

    # 上下文
    max_context_tokens: int = 4096
    max_output_tokens: int = 2048

    # 推理能力
    supports_function_calling: bool = False
    supports_json_mode: bool = False

    # 速度与成本
    is_fast: bool = False
    is_cheap: bool = False

    # 支持的语言
    supports_languages: Set[str] = field(default_factory=lambda: {"en", "zh"})

    # 元数据
    provider: str = ""  # ollama, openai, etc.
    version: str = ""

    @property
    def is_multimodal(self) -> bool:
        """是否支持多模态"""
        return self.multimodal.value > MultimodalCapability.TEXT_ONLY.value

    def supports_language(self, lang: str) -> bool:
        """检查是否支持某语言"""
        lang_lower = lang.lower()
        return any(
            lang_lower in supported.lower()
            for supported in self.supports_languages
        )


class ModelCapabilityDetector:
    """
    模型能力检测器

    根据模型名称自动检测能力
    """

    # 思考模型模式
    THINKING_PATTERNS = [
        (r"qwen3[._-]?.*thinking", ThinkingCapability.DEEP),
        (r"deepseek[_-]r1", ThinkingCapability.DEEP),
        (r"qwen[_-]qwq", ThinkingCapability.EXTENDED),
        (r"qwen[_-]c4[_-]", ThinkingCapability.EXTENDED),
        (r"qwen3[._-]", ThinkingCapability.BASIC),
        (r"qwen2[._-]", ThinkingCapability.NONE),
        (r"llama[_-]3[_-].*think", ThinkingCapability.EXTENDED),
        (r"claude.*think", ThinkingCapability.EXTENDED),
        (r"gpt[_-]4[_-]o.*think", ThinkingCapability.DEEP),
    ]

    # 多模态模型模式
    MULTIMODAL_PATTERNS = [
        (r".*llava.*", MultimodalCapability.IMAGE_INPUT),
        (r".*qwen[_-]vl.*", MultimodalCapability.IMAGE_INPUT),
        (r".*qwen[_-]audio.*", MultimodalCapability.AUDIO),
        (r".*video.*", MultimodalCapability.VIDEO),
        (r".*dalle.*", MultimodalCapability.IMAGE_OUTPUT),
        (r".*gpt[_-]4[_-]o.*", MultimodalCapability.IMAGE_INPUT),
        (r".*gpt[_-]4[_-]v.*", MultimodalCapability.IMAGE_INPUT),
        (r".*gemini.*pro.*vision.*", MultimodalCapability.VIDEO),
        (r".*gemini.*", MultimodalCapability.IMAGE_INPUT),
    ]

    # 快速模型模式
    FAST_PATTERNS = [
        r".*smollm.*",
        r".*qwen[_-]2[._-]?5[._-]?0[._-]?5b.*",
        r".*phi[_-]?3[._-]?mini.*",
        r".*gemma[_-]2[._-]?b.*",
        r".*qwen[_-]2[._-]?5[._-]?1[._-]?5b.*",
    ]

    # 廉价模型模式
    CHEAP_PATTERNS = [
        r".*qwen[_-]2[._-]?5[._-]?0[._-]?5b.*",
        r".*llama[_-]3[._-]?2[._-]?1b.*",
        r".*phi[_-]?3.*",
    ]

    # 上下文大小估算
    CONTEXT_PATTERNS = [
        (r".*32k.*|.*32768.*", 32768),
        (r".*64k.*|.*65536.*", 65536),
        (r".*128k.*", 131072),
        (r".*7b.*", 8192),
        (r".*8b.*", 8192),
        (r".*14b.*", 16384),
        (r".*70b.*", 4096),
        (r".*72b.*", 4096),
        (r".*35b.*", 8192),
    ]

    # 函数调用支持
    FUNCTION_CALL_MODELS = [
        r".*gpt[_-]4[_-]turbo.*",
        r".*gpt[_-]4[_-]o.*",
        r".*claude[_-]3[_-].*sonnet.*",
        r".*claude[_-]3[_-].*opus.*",
        r".*qwen[_-]2[._-]?5[._-]?7b.*",
        r".*qwen[_-]3[._-]?.*",
    ]

    # JSON 模式支持
    JSON_MODE_MODELS = [
        r".*gpt[_-]4[_-]turbo.*",
        r".*gpt[_-]4[_-]o.*",
        r".*gpt[_-]3[_-]?5[_-]turbo.*",
        r".*claude[_-]3[_-].*",
        r".*qwen[_-]2[._-]?5[._-]?.*",
        r".*qwen[_-]3[._-]?.*",
    ]

    # 语言支持
    LANGUAGE_PATTERNS = {
        "zh": [r".*qwen.*", r".*yi.*", r".*deepseek.*", r".*chinese.*", r".*中文.*"],
        "en": [r".*"],  # 默认支持英文
        "ja": [r".*qwen.*", r".*.*"],
        "ko": [r".*qwen.*"],
    }

    def __init__(self):
        self._cache: Dict[str, ModelCapabilities] = {}

    def detect(self, model_name: str, provider: str = "ollama") -> ModelCapabilities:
        """
        检测模型能力

        Args:
            model_name: 模型名称
            provider: 提供商

        Returns:
            ModelCapabilities: 模型能力描述
        """
        # 检查缓存
        if model_name in self._cache:
            return self._cache[model_name]

        # 检测各项能力
        caps = ModelCapabilities(
            model_name=model_name,
            provider=provider,
        )

        # 思考能力
        caps.thinking_type = self._detect_thinking(model_name)
        caps.supports_thinking = caps.thinking_type.value > ThinkingCapability.NONE.value

        # 多模态
        caps.multimodal = self._detect_multimodal(model_name)

        # 上下文
        caps.max_context_tokens = self._detect_context(model_name)

        # 速度与成本
        caps.is_fast = self._detect_fast(model_name)
        caps.is_cheap = self._detect_cheap(model_name)

        # 函数调用
        caps.supports_function_calling = self._detect_pattern(model_name, self.FUNCTION_CALL_MODELS)

        # JSON 模式
        caps.supports_json_mode = self._detect_pattern(model_name, self.JSON_MODE_MODELS)

        # 语言
        caps.supports_languages = self._detect_languages(model_name)

        # 缓存
        self._cache[model_name] = caps
        return caps

    def _detect_thinking(self, model_name: str) -> ThinkingCapability:
        """检测思考能力"""
        for pattern, capability in self.THINKING_PATTERNS:
            if re.search(pattern, model_name, re.IGNORECASE):
                return capability
        return ThinkingCapability.NONE

    def _detect_multimodal(self, model_name: str) -> MultimodalCapability:
        """检测多模态能力"""
        for pattern, capability in self.MULTIMODAL_PATTERNS:
            if re.search(pattern, model_name, re.IGNORECASE):
                return capability
        return MultimodalCapability.TEXT_ONLY

    def _detect_context(self, model_name: str) -> int:
        """检测上下文大小"""
        for pattern, size in self.CONTEXT_PATTERNS:
            if re.search(pattern, model_name, re.IGNORECASE):
                return size
        return 4096  # 默认

    def _detect_fast(self, model_name: str) -> bool:
        """检测是否快速模型"""
        return self._detect_pattern(model_name, self.FAST_PATTERNS)

    def _detect_cheap(self, model_name: str) -> bool:
        """检测是否廉价模型"""
        return self._detect_pattern(model_name, self.CHEAP_PATTERNS)

    def _detect_pattern(self, model_name: str, patterns: List[str]) -> bool:
        """检测是否匹配模式"""
        for pattern in patterns:
            if re.search(pattern, model_name, re.IGNORECASE):
                return True
        return False

    def _detect_languages(self, model_name: str) -> Set[str]:
        """检测支持的语言"""
        languages = set()
        model_lower = model_name.lower()

        for lang, patterns in self.LANGUAGE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, model_lower):
                    languages.add(lang)
                    break

        # 默认支持英文
        languages.add("en")
        return languages

    def find_best_model(
        self,
        requirements: Dict[str, Any],
        available_models: List[str]
    ) -> Tuple[Optional[str], ModelCapabilities]:
        """
        根据需求找到最佳模型

        Args:
            requirements: 需求字典
            available_models: 可用模型列表

        Returns:
            (最佳模型名, 能力描述)
        """
        candidates = []

        for model_name in available_models:
            caps = self.detect(model_name)

            # 评分
            score = 0

            # 思考能力
            if requirements.get("needs_thinking"):
                score += caps.thinking_type.value * 10

            # 多模态
            if requirements.get("needs_multimodal"):
                if caps.is_multimodal:
                    score += 20

            # 速度
            if requirements.get("needs_fast") and caps.is_fast:
                score += 15

            # 成本
            if requirements.get("needs_cheap") and caps.is_cheap:
                score += 10

            # 上下文
            required_ctx = requirements.get("min_context", 0)
            if caps.max_context_tokens >= required_ctx:
                score += 5

            # 语言
            lang = requirements.get("language", "en")
            if caps.supports_language(lang):
                score += 5

            candidates.append((model_name, caps, score))

        # 排序
        candidates.sort(key=lambda x: x[2], reverse=True)

        if candidates:
            return candidates[0][0], candidates[0][1]
        return None, None


class MultimodalMessageFilter:
    """
    多模态消息过滤器

    根据模型能力过滤消息内容
    """

    def __init__(self, capabilities: ModelCapabilities):
        self.capabilities = capabilities

    def filter_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        过滤消息以适应模型能力

        Args:
            messages: 原始消息列表

        Returns:
            过滤后的消息列表
        """
        filtered = []

        for msg in messages:
            # 检查是否支持图片
            if msg.get("image_url") or msg.get("image_base64"):
                if not self.capabilities.is_multimodal:
                    # 将图片消息转换为文本描述
                    filtered.append({
                        "role": msg.get("role", "user"),
                        "content": "[图片内容已被过滤]" + msg.get("content", "")
                    })
                    continue

            filtered.append(msg)

        return filtered


# ═══════════════════════════════════════════════════════════════════════════
# 全局单例
# ═══════════════════════════════════════════════════════════════════════════

_detector: Optional[ModelCapabilityDetector] = None


def get_capability_detector() -> ModelCapabilityDetector:
    """获取全局能力检测器单例"""
    global _detector
    if _detector is None:
        _detector = ModelCapabilityDetector()
    return _detector


# ═══════════════════════════════════════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════════════════════════════════════

def detect_model(model_name: str, provider: str = "ollama") -> ModelCapabilities:
    """便捷函数：检测模型能力"""
    detector = get_capability_detector()
    return detector.detect(model_name, provider)


def is_thinking_model(model_name: str) -> bool:
    """便捷函数：判断是否为思考模型"""
    caps = detect_model(model_name)
    return caps.supports_thinking


def is_multimodal_model(model_name: str) -> bool:
    """便捷函数：判断是否为多模态模型"""
    caps = detect_model(model_name)
    return caps.is_multimodal
