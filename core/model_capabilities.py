"""
模型能力管理系统
================

功能：
1. 检测模型是否支持 thinking（推理能力）
2. 检测模型是否支持多模态（图片/音视频）
3. 提供流式 thinking 输出支持
4. 提供多模态输入过滤

模型能力来源：
1. 模型名称模式匹配（快表）
2. Ollama API 查询模型元数据
3. 运行时行为检测

作者：Hermes Agent
日期：2026-04-25
"""

from dataclasses import dataclass, field
from typing import List, Optional, Callable
from enum import Enum
import re
import time
import httpx

# ── 能力枚举 ────────────────────────────────────────────────────────

class ThinkingCapability(Enum):
    """推理/思考能力级别"""
    NONE = "none"           # 不支持推理输出
    STREAMING = "streaming"  # 流式输出 thinking 内容
    FINAL_ONLY = "final_only"  # 仅在完成后返回 thinking

class MultimodalCapability(Enum):
    """多模态能力级别"""
    TEXT_ONLY = "text_only"     # 仅文本
    VISION = "vision"           # 支持图片
    AUDIO = "audio"            # 支持音频
    VIDEO = "video"            # 支持视频
    FULL = "full"              # 全部支持

@dataclass
class ModelCapabilities:
    """模型能力描述"""
    model_name: str
    thinking: ThinkingCapability = ThinkingCapability.NONE
    multimodal: MultimodalCapability = MultimodalCapability.TEXT_ONLY
    
    # 额外信息
    supports_streaming: bool = True
    max_context_tokens: int = 8192
    recommended_for: List[str] = field(default_factory=list)
    
    # 检测元数据
    detected_at: Optional[float] = None
    source: str = "unknown"  # "pattern" / "api" / "runtime"
    
    def can_think(self) -> bool:
        """是否支持 thinking"""
        return self.thinking != ThinkingCapability.NONE
    
    def can_stream_think(self) -> bool:
        """是否支持流式 thinking"""
        return self.thinking == ThinkingCapability.STREAMING
    
    def supports_image(self) -> bool:
        """是否支持图片输入"""
        return self.multimodal in (
            MultimodalCapability.VISION,
            MultimodalCapability.FULL
        )
    
    def supports_audio(self) -> bool:
        """是否支持音频输入"""
        return self.multimodal in (
            MultimodalCapability.AUDIO,
            MultimodalCapability.FULL
        )
    
    def supports_video(self) -> bool:
        """是否支持视频输入"""
        return self.multimodal in (
            MultimodalCapability.VIDEO,
            MultimodalCapability.FULL
        )
    
    def supports_multimodal(self) -> bool:
        """是否支持任何多模态"""
        return self.multimodal != MultimodalCapability.TEXT_ONLY
    
    def get_capability_summary(self) -> str:
        """获取能力摘要"""
        caps = []
        if self.can_think():
            caps.append("[THINK] thinking")
        if self.supports_image():
            caps.append("[IMG] image")
        if self.supports_audio():
            caps.append("[AUD] audio")
        if self.supports_video():
            caps.append("[VID] video")
        if not caps:
            caps.append("[TEXT] text only")
        return ", ".join(caps)


# ── 模型能力快速查找表 ──────────────────────────────────────────────

# Ollama 思考模型（内置 thinking 能力）
THINKING_MODELS = {
    # Qwen3 系列（带思考能力）
    "qwen3": True,
    "qwen3.5": True,
    "qwen3.6": True,
    
    # DeepSeek 系列（带思考能力）
    "deepseek-r1": True,
    "deepseek-coder": False,  # coder 版本可能不支持
    
    # 其他已知的思考模型
    "phi4": True,  # Microsoft Phi-4
    "izard": True,
}

# 多模态模型表
MULTIMODAL_MODELS = {
    # 支持视觉的模型
    "llava": MultimodalCapability.VISION,
    "llava-llama3": MultimodalCapability.VISION,
    "llava-vicuna": MultimodalCapability.VISION,
    "moondream": MultimodalCapability.VISION,
    "qwen2-vl": MultimodalCapability.VISION,
    "qwen2.5-vl": MultimodalCapability.VISION,
    "qwen-vl": MultimodalCapability.VISION,
    "qwen2.5-omni": MultimodalCapability.FULL,
    "qwq": MultimodalCapability.VISION,
    
    # 支持音频的模型
    "whisper": MultimodalCapability.AUDIO,
    "sensevoice": MultimodalCapability.AUDIO,
    "cosyvoice": MultimodalCapability.AUDIO,
    
    # 全能模型
    "gpt-4o": MultimodalCapability.FULL,
    "gpt-4-turbo": MultimodalCapability.FULL,
    "claude-3-opus": MultimodalCapability.FULL,
    "claude-3-sonnet": MultimodalCapability.FULL,
    "gemini-1.5-pro": MultimodalCapability.FULL,
    "gemini-2.0-flash": MultimodalCapability.FULL,
}

# 非思考模型（快速排除）
NON_THINKING_MODELS = {
    "qwen2.5": False,
    "qwen2": False,
    "qwen1.5": False,
    "llama3": False,
    "llama3.1": False,
    "llama3.2": False,
    "llama2": False,
    "gemma": False,
    "gemma2": False,
    "gemma3": False,
    "mistral": False,
    "mixtral": False,
    "yi": False,
    "baichuan": False,
    "chatglm": False,
    "smollm": False,
    "smollm2": False,
    "nomic-embed-text": False,
    "all-minilm": False,
    "bge": False,
}


# ── 能力检测器 ──────────────────────────────────────────────────────

class ModelCapabilityDetector:
    """
    模型能力检测器
    
    检测策略（优先级递减）：
    1. 已知模式匹配（毫秒级）
    2. Ollama API 查询（网络请求）
    3. 运行时行为检测（最后手段）
    """
    
    def __init__(self, ollama_base_url: str = "http://localhost:11434"):
        self.ollama_base_url = ollama_base_url.rstrip("/")
        self._cache: dict[str, ModelCapabilities] = {}
        self._cache_ttl = 300  # 缓存 5 分钟
    
    def detect(self, model_name: str) -> ModelCapabilities:
        """
        检测模型能力（带缓存）
        
        Args:
            model_name: 模型名称（如 qwen3.5:4b）
            
        Returns:
            ModelCapabilities: 模型能力描述
        """
        # 检查缓存
        if model_name in self._cache:
            cached = self._cache[model_name]
            if time.time() - cached.detected_at < self._cache_ttl:
                return cached
        
        # 1. 模式匹配（最快）
        caps = self._detect_by_pattern(model_name)
        if caps.source == "pattern":
            self._cache[model_name] = caps
            return caps
        
        # 2. API 查询
        caps = self._detect_by_api(model_name)
        if caps.source == "api":
            self._cache[model_name] = caps
            return caps
        
        # 3. 保守默认值
        caps = ModelCapabilities(
            model_name=model_name,
            thinking=ThinkingCapability.NONE,
            multimodal=MultimodalCapability.TEXT_ONLY,
            detected_at=time.time(),
            source="default"
        )
        self._cache[model_name] = caps
        return caps
    
    def _detect_by_pattern(self, model_name: str) -> ModelCapabilities:
        """通过名称模式检测能力"""
        model_lower = model_name.lower()
        
        # 检测 thinking 能力
        thinking = ThinkingCapability.NONE
        for prefix, is_thinking in THINKING_MODELS.items():
            if model_lower.startswith(prefix):
                thinking = ThinkingCapability.STREAMING if is_thinking else ThinkingCapability.NONE
                break
        
        # 如果没有命中，检查是否在非思考列表
        if thinking == ThinkingCapability.NONE:
            for prefix, is_thinking in NON_THINKING_MODELS.items():
                if model_lower.startswith(prefix):
                    thinking = ThinkingCapability.NONE
                    break
        
        # 检测多模态能力
        multimodal = MultimodalCapability.TEXT_ONLY
        for prefix, capability in MULTIMODAL_MODELS.items():
            if prefix in model_lower:
                multimodal = capability
                break
        
        # 特殊处理：qwen3.x 系列检测
        if "qwen3" in model_lower:
            if ":35b" in model_lower or ":72b" in model_lower or "qwen3.6" in model_lower:
                thinking = ThinkingCapability.STREAMING
            elif ":8b" in model_lower or ":14b" in model_lower or ":32b" in model_lower:
                thinking = ThinkingCapability.STREAMING
        
        return ModelCapabilities(
            model_name=model_name,
            thinking=thinking,
            multimodal=multimodal,
            detected_at=time.time(),
            source="pattern"
        )
    
    def _detect_by_api(self, model_name: str) -> ModelCapabilities:
        """通过 Ollama API 检测能力"""
        try:
            # 调用 /api/show 获取模型信息
            with httpx.Client(timeout=5.0) as client:
                resp = client.post(
                    f"{self.ollama_base_url}/api/show",
                    json={"name": model_name}
                )
                
                if resp.status_code == 200:
                    info = resp.json()
                    
                    # 从 details 中提取信息
                    details = info.get("details", {})
                    
                    # 检测 thinking 能力（通过 model info 中的提示）
                    thinking = ThinkingCapability.NONE
                    if details.get("supports_reasoning", False):
                        thinking = ThinkingCapability.STREAMING
                    
                    # 检测多模态能力
                    multimodal = MultimodalCapability.TEXT_ONLY
                    capabilities = details.get("capabilities", [])
                    if "vision" in capabilities or "multimodal" in capabilities:
                        multimodal = MultimodalCapability.FULL
                    
                    return ModelCapabilities(
                        model_name=model_name,
                        thinking=thinking,
                        multimodal=multimodal,
                        detected_at=time.time(),
                        source="api"
                    )
        except Exception:
            pass
        
        # API 失败，返回占位符
        return ModelCapabilities(
            model_name=model_name,
            source="api_fallback"
        )
    
    def detect_thinking_mode_runtime(self, model_name: str, first_chunk: str) -> bool:
        """
        运行时检测 thinking 模式
        
        通过观察第一个 chunk 判断模型是否输出 thinking
        
        Args:
            model_name: 模型名称
            first_chunk: 流式输出的第一个 chunk
            
        Returns:
            True 如果正在输出 thinking
        """
        caps = self.detect(model_name)
        if not caps.can_think():
            return False
        
        # 检测 thinking 标记
        thinking_markers = [
            "<think>", "<think>", "<thought>",
            "<reasoning>", " reasoning ",
            "\n### Reasoning\n", "\n**Reasoning:**",
        ]
        
        for marker in thinking_markers:
            if marker in first_chunk.lower():
                return True
        
        return False
    
    def can_process_multimodal(self, model_name: str, content_type: str) -> bool:
        """
        检查模型是否支持特定多模态内容
        
        Args:
            model_name: 模型名称
            content_type: 内容类型（"image", "audio", "video", "text"）
            
        Returns:
            True 如果支持
        """
        caps = self.detect(model_name)
        
        type_map = {
            "image": caps.supports_image,
            "audio": caps.supports_audio,
            "video": caps.supports_video,
            "text": True,
        }
        
        checker = type_map.get(content_type.lower(), lambda: False)
        return checker()


# ── 全局检测器实例 ────────────────────────────────────────────────────

_global_detector: Optional[ModelCapabilityDetector] = None

def get_capability_detector(
    ollama_base_url: str = "http://localhost:11434"
) -> ModelCapabilityDetector:
    """获取全局能力检测器（单例）"""
    global _global_detector
    if _global_detector is None:
        _global_detector = ModelCapabilityDetector(ollama_base_url)
    return _global_detector


# ── 消息过滤器 ────────────────────────────────────────────────────────

class MultimodalMessageFilter:
    """
    多模态消息过滤器
    
    根据模型能力自动过滤不支持的内容类型
    """
    
    def __init__(self, detector: ModelCapabilityDetector):
        self.detector = detector
    
    def filter_messages(
        self,
        model_name: str,
        messages: List[dict]
    ) -> tuple[List[dict], List[str]]:
        """
        过滤消息中不支持的多模态内容
        
        Args:
            model_name: 模型名称
            messages: 原始消息列表
            
        Returns:
            (过滤后的消息, 被过滤的内容描述列表)
        """
        caps = self.detector.detect(model_name)
        filtered = []
        removed = []
        
        for msg in messages:
            content = msg.get("content", "")
            
            # 检查是否是列表格式（多模态消息）
            if isinstance(content, list):
                new_content = []
                for item in content:
                    if isinstance(item, dict):
                        item_type = item.get("type", "text")
                        
                        if item_type == "text":
                            new_content.append(item)
                        elif item_type == "image_url":
                            if caps.supports_image():
                                new_content.append(item)
                            else:
                                removed.append(f"图片 (image_url)")
                        elif item_type == "audio_url":
                            if caps.supports_audio():
                                new_content.append(item)
                            else:
                                removed.append(f"音频 (audio_url)")
                        elif item_type == "video":
                            if caps.supports_video():
                                new_content.append(item)
                            else:
                                removed.append(f"视频")
                        else:
                            new_content.append(item)
                    else:
                        new_content.append(item)
                
                msg = {**msg, "content": new_content}
            else:
                # 文本消息直接保留
                pass
            
            filtered.append(msg)
        
        return filtered, removed
    
    def validate_single_message(
        self,
        model_name: str,
        message: dict
    ) -> tuple[bool, str]:
        """
        验证单条消息是否可被模型处理
        
        Returns:
            (是否有效, 错误消息)
        """
        caps = self.detector.detect(model_name)
        content = message.get("content", "")
        
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    item_type = item.get("type", "text")
                    
                    if item_type == "image_url" and not caps.supports_image():
                        return False, "模型不支持图片输入"
                    elif item_type == "audio_url" and not caps.supports_audio():
                        return False, "模型不支持音频输入"
                    elif item_type == "video" and not caps.supports_video():
                        return False, "模型不支持视频输入"
        
        return True, ""


# ── 能力提示生成器 ────────────────────────────────────────────────────

def generate_capability_hint(caps: ModelCapabilities) -> str:
    """
    根据模型能力生成提示信息
    
    用于在日志中显示模型能力
    """
    hints = []
    
    if caps.can_think():
        if caps.can_stream_think():
            hints.append("[OK] 支持流式 thinking")
        else:
            hints.append("[OK] 支持 thinking（非流式）")
    else:
        hints.append("[INFO] 不支持 thinking")
    
    if caps.supports_multimodal():
        modal_caps = []
        if caps.supports_image():
            modal_caps.append("[IMG]")
        if caps.supports_audio():
            modal_caps.append("[AUD]")
        if caps.supports_video():
            modal_caps.append("[VID]")
        hints.append(f"多模态: {''.join(modal_caps)}")
    else:
        hints.append("[INFO] 仅支持文本")
    
    return " | ".join(hints)
