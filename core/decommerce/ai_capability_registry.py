"""
AI能力一键上架系统
AI Capability Registry & One-Click Listing

让卖家一键上架AI能力，买家下单即用。

核心功能:
1. 自动探测本地AI能力 (Ollama/Hermes模型)
2. 生成标准化服务描述
3. 一键发布到市场
4. 能力动态更新
5. 与Hermes/OfficeCLI/CLI-Anything集成
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import logging
import time
import uuid
import json

from core.config.unified_config import UnifiedConfig

logger = logging.getLogger(__name__)


class CapabilityType(Enum):
    """能力类型"""
    TEXT_CHAT = "text_chat"
    CODE_COMPLETION = "code_completion"
    CODE_REVIEW = "code_review"
    IMAGE_GEN = "image_gen"
    IMAGE_EDIT = "image_edit"
    TEXT_EDIT = "text_edit"
    TRANSLATION = "translation"
    SUMMARIZATION = "summarization"
    REASONING = "reasoning"
    OCR = "ocr"
    VOICE_TTS = "voice_tts"
    VOICE_STT = "voice_stt"


@dataclass
class AICapability:
    """AI能力描述"""
    capability_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    capability_type: CapabilityType = CapabilityType.TEXT_CHAT

    model_name: str = ""
    model_backend: str = ""
    model_size: str = ""

    display_name: str = ""
    description: str = ""
    prompt_template: str = ""
    input_examples: List[str] = field(default_factory=list)
    output_examples: List[str] = field(default_factory=list)

    avg_latency_ms: int = 0
    max_tokens: int = 4096
    price_per_1k_tokens: int = 10
    price_per_call: int = 0

    is_enabled: bool = True
    is_available: bool = False
    last_used_at: float = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "capability_type": self.capability_type.value,
            "model_name": self.model_name,
            "model_backend": self.model_backend,
            "model_size": self.model_size,
            "display_name": self.display_name,
            "description": self.description,
            "prompt_template": self.prompt_template,
            "input_examples": self.input_examples,
            "output_examples": self.output_examples,
            "avg_latency_ms": self.avg_latency_ms,
            "max_tokens": self.max_tokens,
            "price_per_1k_tokens": self.price_per_1k_tokens,
            "price_per_call": self.price_per_call,
            "is_enabled": self.is_enabled,
            "is_available": self.is_available,
            "last_used_at": self.last_used_at,
        }


@dataclass
class ListingTemplate:
    """服务发布模板"""
    template_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    name: str = ""
    description: str = ""
    capability_type: CapabilityType = CapabilityType.TEXT_CHAT

    base_price: int = 100
    per_minute_price: int = 0
    per_call_price: int = 10

    max_concurrent: int = 1
    timeout_seconds: int = 300
    requires_stream: bool = False

    tags: List[str] = field(default_factory=list)

    @classmethod
    def get_default_templates(cls) -> List["ListingTemplate"]:
        return [
            ListingTemplate(
                name="AI对话助手",
                description="基于大模型的智能对话服务",
                capability_type=CapabilityType.TEXT_CHAT,
                base_price=50,
                per_call_price=10,
                tags=["AI", "对话", "助手"],
            ),
            ListingTemplate(
                name="代码审查",
                description="AI自动审查代码问题和建议",
                capability_type=CapabilityType.CODE_REVIEW,
                base_price=100,
                per_call_price=50,
                tags=["代码", "审查", "编程"],
            ),
            ListingTemplate(
                name="代码补全",
                description="智能代码补全和建议",
                capability_type=CapabilityType.CODE_COMPLETION,
                base_price=30,
                per_call_price=5,
                tags=["代码", "补全", "编程"],
            ),
            ListingTemplate(
                name="文案润色",
                description="专业文案修改和润色",
                capability_type=CapabilityType.TEXT_EDIT,
                base_price=80,
                per_call_price=30,
                tags=["文案", "润色", "写作"],
            ),
            ListingTemplate(
                name="文章总结",
                description="快速提取文章要点",
                capability_type=CapabilityType.SUMMARIZATION,
                base_price=60,
                per_call_price=20,
                tags=["总结", "摘要", "文章"],
            ),
            ListingTemplate(
                name="翻译服务",
                description="多语言翻译",
                capability_type=CapabilityType.TRANSLATION,
                base_price=40,
                per_call_price=15,
                tags=["翻译", "语言"],
            ),
            ListingTemplate(
                name="逻辑推理助手",
                description="复杂问题分析和推理",
                capability_type=CapabilityType.REASONING,
                base_price=100,
                per_call_price=50,
                tags=["推理", "分析", "逻辑"],
            ),
            ListingTemplate(
                name="OCR文字识别",
                description="图片转文字",
                capability_type=CapabilityType.OCR,
                base_price=30,
                per_call_price=10,
                tags=["OCR", "识别", "图片"],
            ),
        ]


class AICapabilityRegistry:
    """AI能力注册表"""

    def __init__(self):
        self._capabilities: Dict[str, AICapability] = {}
        self._listing_templates: List[ListingTemplate] = ListingTemplate.get_default_templates()
        self._ollama_client = None
        self._hermes_client = None
        self._on_capability_discovered: List[Callable] = []
        self._on_capability_changed: List[Callable] = []
        logger.info("[AICapabilityRegistry] Initialized")

    async def discover_capabilities(self) -> List[AICapability]:
        """自动探测本地AI能力"""
        discovered = []
        ollama_caps = await self._discover_ollama()
        discovered.extend(ollama_caps)
        hermes_caps = await self._discover_hermes()
        discovered.extend(hermes_caps)

        for cap in discovered:
            self._capabilities[cap.capability_id] = cap
            self._notify_capability_discovered(cap)

        logger.info(f"[AICapabilityRegistry] Discovered {len(discovered)} capabilities")
        return discovered

    async def _discover_ollama(self) -> List[AICapability]:
        """探测Ollama模型"""
        caps = []
        try:
            import aiohttp
            config = UnifiedConfig.get_instance()
            discovery_timeout = config.get("decommerce.discovery_timeout", 5)
            
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:11434/api/tags", timeout=discovery_timeout) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        models = data.get("models", [])
                        for model in models:
                            model_name = model.get("name", "")
                            if not model_name:
                                continue
                            cap_type = self._infer_capability_from_model(model_name)
                            model_size = self._extract_model_size(model_name)
                            cap = AICapability(
                                capability_type=cap_type,
                                model_name=model_name,
                                model_backend="ollama",
                                model_size=model_size,
                                display_name=model_name.split(":")[0].replace("-", " ").title(),
                                description=self._generate_description(cap_type, model_name),
                                max_tokens=4096 if "70b" not in model_name.lower() else 8192,
                                price_per_1k_tokens=self._calculate_price(model_size),
                            )
                            cap.is_available = True
                            caps.append(cap)
                            logger.info(f"[AICapabilityRegistry] Found Ollama model: {model_name}")
        except Exception as e:
            logger.debug(f"[AICapabilityRegistry] Ollama not available: {e}")
        return caps

    async def _discover_hermes(self) -> List[AICapability]:
        """探测Hermes System Brain"""
        caps = []
        try:
            from ..system_brain import get_system_brain
            brain = get_system_brain()
            if brain:
                models = brain.get_available_models() or []
                for model_name in models:
                    cap = AICapability(
                        capability_type=CapabilityType.TEXT_CHAT,
                        model_name=model_name,
                        model_backend="hermes",
                        display_name=f"Hermes {model_name}",
                        description="Hermes系统大脑模型",
                        is_available=True,
                    )
                    caps.append(cap)
        except Exception as e:
            logger.debug(f"[AICapabilityRegistry] Hermes brain not available: {e}")
        return caps

    def _infer_capability_from_model(self, model_name: str) -> CapabilityType:
        name_lower = model_name.lower()
        if "code" in name_lower:
            return CapabilityType.CODE_COMPLETION if "llama" in name_lower or "qwen" in name_lower else CapabilityType.CODE_REVIEW
        elif "vision" in name_lower or "llava" in name_lower:
            return CapabilityType.IMAGE_EDIT
        elif "embed" in name_lower:
            return CapabilityType.TEXT_EDIT
        return CapabilityType.TEXT_CHAT

    def _extract_model_size(self, model_name: str) -> str:
        import re
        match = re.search(r"(\d+)[bB]", model_name)
        if match:
            size = int(match.group(1))
            if size >= 70:
                return "70B+"
            elif size >= 30:
                return "30B"
            elif size >= 13:
                return "13B"
            return "7B"
        return "Unknown"

    def _calculate_price(self, model_size: str) -> int:
        price_map = {"7B": 5, "13B": 10, "30B": 20, "70B+": 50, "Unknown": 10}
        return price_map.get(model_size, 10)

    def _generate_description(self, cap_type: CapabilityType, model_name: str) -> str:
        desc_map = {
            CapabilityType.TEXT_CHAT: f"基于{model_name}的智能对话服务",
            CapabilityType.CODE_COMPLETION: f"基于{model_name}的代码补全服务",
            CapabilityType.CODE_REVIEW: f"基于{model_name}的代码审查服务",
            CapabilityType.TEXT_EDIT: f"基于{model_name}的文本编辑润色服务",
            CapabilityType.SUMMARIZATION: f"基于{model_name}的文章总结服务",
            CapabilityType.TRANSLATION: f"基于{model_name}的多语言翻译服务",
            CapabilityType.REASONING: f"基于{model_name}的逻辑推理服务",
            CapabilityType.OCR: f"基于{model_name}的OCR文字识别服务",
        }
        return desc_map.get(cap_type, f"基于{model_name}的AI服务")

    def get_capabilities(self) -> List[AICapability]:
        return list(self._capabilities.values())

    def get_available_capabilities(self) -> List[AICapability]:
        return [c for c in self._capabilities.values() if c.is_available and c.is_enabled]

    def get_capability(self, capability_id: str) -> Optional[AICapability]:
        return self._capabilities.get(capability_id)

    def enable_capability(self, capability_id: str) -> bool:
        cap = self._capabilities.get(capability_id)
        if cap:
            cap.is_enabled = True
            self._notify_capability_changed(cap)
            return True
        return False

    def disable_capability(self, capability_id: str) -> bool:
        cap = self._capabilities.get(capability_id)
        if cap:
            cap.is_enabled = False
            self._notify_capability_changed(cap)
            return True
        return False

    def update_capability(self, capability_id: str, **updates) -> Optional[AICapability]:
        cap = self._capabilities.get(capability_id)
        if not cap:
            return None
        allowed = ["display_name", "description", "price_per_1k_tokens", "price_per_call", "max_tokens", "prompt_template"]
        for key, value in updates.items():
            if key in allowed and hasattr(cap, key):
                setattr(cap, key, value)
        self._notify_capability_changed(cap)
        return cap

    def create_listing_from_capability(
        self,
        capability_id: str,
        seller_id: str,
        template_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        cap = self._capabilities.get(capability_id)
        if not cap or not cap.is_enabled:
            return None

        template = None
        if template_id:
            template = next((t for t in self._listing_templates if t.template_id == template_id), None)

        if not template:
            template = next((
                t for t in self._listing_templates
                if t.capability_type == cap.capability_type
            ), self._listing_templates[0])

        from .models import ServiceType

        listing_data = {
            "title": cap.display_name or template.name,
            "description": cap.description or template.description,
            "price": template.base_price + cap.price_per_call * 100,
            "service_type": ServiceType.AI_COMPUTING,
            "ai_model": cap.model_name,
            "ai_capabilities": [cap.capability_type.value],
            "max_concurrent": template.max_concurrent,
            "tags": template.tags + [cap.model_size],
        }

        logger.info(f"[AICapabilityRegistry] Created listing: {listing_data['title']}")
        return listing_data

    def publish_all_enabled(self, seller_id: str) -> List[Dict[str, Any]]:
        listings = []
        for cap in self._capabilities.values():
            if cap.is_enabled and cap.is_available:
                listing = self.create_listing_from_capability(cap.capability_id, seller_id)
                if listing:
                    listings.append(listing)
        logger.info(f"[AICapabilityRegistry] Published {len(listings)} listings")
        return listings

    def get_templates(self) -> List[ListingTemplate]:
        return self._listing_templates

    def add_template(self, template: ListingTemplate) -> None:
        self._listing_templates.append(template)

    def on_capability_discovered(self, callback: Callable) -> None:
        self._on_capability_discovered.append(callback)

    def on_capability_changed(self, callback: Callable) -> None:
        self._on_capability_changed.append(callback)

    def _notify_capability_discovered(self, cap: AICapability) -> None:
        for cb in self._on_capability_discovered:
            try:
                if asyncio.iscoroutinefunction(cb):
                    asyncio.create_task(cb(cap))
                else:
                    cb(cap)
            except Exception as e:
                logger.error(f"[AICapabilityRegistry] Callback error: {e}")

    def _notify_capability_changed(self, cap: AICapability) -> None:
        for cb in self._on_capability_changed:
            try:
                if asyncio.iscoroutinefunction(cb):
                    asyncio.create_task(cb(cap))
                else:
                    cb(cap)
            except Exception as e:
                logger.error(f"[AICapabilityRegistry] Callback error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        caps = list(self._capabilities.values())
        return {
            "total_capabilities": len(caps),
            "available": sum(1 for c in caps if c.is_available),
            "enabled": sum(1 for c in caps if c.is_enabled),
            "by_type": {
                ct.value: sum(1 for c in caps if c.capability_type == ct)
                for ct in CapabilityType
            },
            "by_backend": {
                backend: sum(1 for c in caps if c.model_backend == backend)
                for backend in set(c.model_backend for c in caps)
            },
        }


_ai_capability_registry: Optional[AICapabilityRegistry] = None

def get_ai_capability_registry() -> AICapabilityRegistry:
    global _ai_capability_registry
    if _ai_capability_registry is None:
        _ai_capability_registry = AICapabilityRegistry()
    return _ai_capability_registry
