"""
🧠 模型路由系统

为不同任务选择最合适的大模型：
- 文档规划模型: 生成大纲和结构
- 内容生成模型: 填充具体内容
- 格式理解模型: 理解样式要求
- 合规检查模型: 检查合规性
- 优化建议模型: 提供优化建议

支持后端:
- Ollama (本地, 隐私优先)
- OpenAI API (云端, 高质量)
- 自定义 API
"""

import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Callable

logger = logging.getLogger(__name__)


class ModelCapability(Enum):
    """模型能力"""
    DOCUMENT_PLANNING = "document_planning"   # 文档规划
    CONTENT_GENERATION = "content_generation" # 内容生成
    FORMAT_UNDERSTANDING = "format_understanding"  # 格式理解
    COMPLIANCE_CHECK = "compliance_check"     # 合规检查
    OPTIMIZATION = "optimization"             # 优化建议
    TRANSLATION = "translation"               # 翻译
    SUMMARIZATION = "summarization"           # 摘要


class ModelBackend(Enum):
    """模型后端"""
    OLLAMA = "ollama"
    OPENAI = "openai"
    CUSTOM = "custom"
    MOCK = "mock"  # 测试用


@dataclass
class ModelInfo:
    """模型信息"""
    model_id: str
    name: str
    backend: ModelBackend
    capabilities: List[ModelCapability] = field(default_factory=list)
    max_tokens: int = 4096
    quality_score: float = 0.7     # 0-1, 质量评分
    speed_score: float = 0.5       # 0-1, 速度评分
    cost_score: float = 1.0        # 0-1, 1=免费, 0=极贵
    privacy_score: float = 1.0     # 0-1, 1=完全本地
    is_available: bool = True
    config: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "name": self.name,
            "backend": self.backend.value,
            "capabilities": [c.value for c in self.capabilities],
            "quality": round(self.quality_score, 2),
            "speed": round(self.speed_score, 2),
            "cost": round(self.cost_score, 2),
            "privacy": round(self.privacy_score, 2),
            "available": self.is_available,
        }


class ModelRouter:
    """
    模型路由器

    路由策略:
    - quality: 质量优先 (选择质量分最高的)
    - speed: 速度优先 (选择速度分最高的)
    - cost: 成本优先 (选择免费/最便宜的)
    - privacy: 隐私优先 (选择本地模型)
    - balanced: 均衡模式 (综合评分)
    - auto: 自动选择 (根据任务类型自动决定)
    """

    # 内置模型配置
    BUILTIN_MODELS = [
        ModelInfo(
            model_id="ollama_qwen2.5",
            name="Qwen2.5 (Ollama)",
            backend=ModelBackend.OLLAMA,
            capabilities=[
                ModelCapability.DOCUMENT_PLANNING,
                ModelCapability.CONTENT_GENERATION,
                ModelCapability.SUMMARIZATION,
            ],
            max_tokens=8192,
            quality_score=0.75,
            speed_score=0.7,
            cost_score=1.0,
            privacy_score=1.0,
            config={"url": "http://localhost:11434", "model": "qwen2.5"},
        ),
        ModelInfo(
            model_id="ollama_hermes",
            name="NousHermes (Ollama)",
            backend=ModelBackend.OLLAMA,
            capabilities=[
                ModelCapability.DOCUMENT_PLANNING,
                ModelCapability.CONTENT_GENERATION,
                ModelCapability.FORMAT_UNDERSTANDING,
            ],
            max_tokens=4096,
            quality_score=0.7,
            speed_score=0.8,
            cost_score=1.0,
            privacy_score=1.0,
            config={"url": "http://localhost:11434", "model": "nous-hermes2"},
        ),
        ModelInfo(
            model_id="ollama_deepseek",
            name="DeepSeek Coder (Ollama)",
            backend=ModelBackend.OLLAMA,
            capabilities=[
                ModelCapability.FORMAT_UNDERSTANDING,
                ModelCapability.COMPLIANCE_CHECK,
                ModelCapability.OPTIMIZATION,
            ],
            max_tokens=8192,
            quality_score=0.8,
            speed_score=0.6,
            cost_score=1.0,
            privacy_score=1.0,
            config={"url": "http://localhost:11434", "model": "deepseek-coder-v2"},
        ),
        ModelInfo(
            model_id="openai_gpt4",
            name="GPT-4 (OpenAI)",
            backend=ModelBackend.OPENAI,
            capabilities=[
                ModelCapability.DOCUMENT_PLANNING,
                ModelCapability.CONTENT_GENERATION,
                ModelCapability.FORMAT_UNDERSTANDING,
                ModelCapability.COMPLIANCE_CHECK,
                ModelCapability.OPTIMIZATION,
                ModelCapability.TRANSLATION,
                ModelCapability.SUMMARIZATION,
            ],
            max_tokens=8192,
            quality_score=0.95,
            speed_score=0.4,
            cost_score=0.2,
            privacy_score=0.1,
            config={"model": "gpt-4"},
        ),
        ModelInfo(
            model_id="openai_gpt35",
            name="GPT-3.5 Turbo (OpenAI)",
            backend=ModelBackend.OPENAI,
            capabilities=[
                ModelCapability.CONTENT_GENERATION,
                ModelCapability.SUMMARIZATION,
                ModelCapability.TRANSLATION,
            ],
            max_tokens=4096,
            quality_score=0.7,
            speed_score=0.8,
            cost_score=0.5,
            privacy_score=0.1,
            config={"model": "gpt-3.5-turbo"},
        ),
        ModelInfo(
            model_id="mock_planner",
            name="模拟规划器 (测试)",
            backend=ModelBackend.MOCK,
            capabilities=[ModelCapability.DOCUMENT_PLANNING],
            max_tokens=2048,
            quality_score=0.5,
            speed_score=1.0,
            cost_score=1.0,
            privacy_score=1.0,
        ),
    ]

    # 任务 → 策略 映射
    TASK_STRATEGY_MAP = {
        ModelCapability.DOCUMENT_PLANNING: "balanced",
        ModelCapability.CONTENT_GENERATION: "quality",
        ModelCapability.FORMAT_UNDERSTANDING: "balanced",
        ModelCapability.COMPLIANCE_CHECK: "quality",
        ModelCapability.OPTIMIZATION: "balanced",
        ModelCapability.TRANSLATION: "speed",
        ModelCapability.SUMMARIZATION: "speed",
    }

    def __init__(self):
        self.models: Dict[str, ModelInfo] = {}
        self._call_count: Dict[str, int] = {}

        # 加载内置模型
        for m in self.BUILTIN_MODELS:
            self.models[m.model_id] = m

    def register_model(self, model: ModelInfo):
        """注册自定义模型"""
        self.models[model.model_id] = model
        logger.info(f"注册模型: {model.name} ({model.model_id})")

    def route(self, capability: ModelCapability,
              strategy: str = "auto") -> ModelInfo:
        """
        路由到最佳模型

        Args:
            capability: 需要的能力
            strategy: 路由策略

        Returns:
            ModelInfo 最佳模型
        """
        if strategy == "auto":
            strategy = self.TASK_STRATEGY_MAP.get(capability, "balanced")

        # 筛选具备该能力的可用模型
        candidates = [
            m for m in self.models.values()
            if capability in m.capabilities and m.is_available
        ]

        if not candidates:
            logger.warning(f"无可用模型支持 {capability.value}, 使用模拟模型")
            return ModelInfo(
                model_id="fallback",
                name="Fallback Model",
                backend=ModelBackend.MOCK,
                capabilities=[capability],
            )

        # 按策略排序
        if strategy == "quality":
            candidates.sort(key=lambda m: m.quality_score, reverse=True)
        elif strategy == "speed":
            candidates.sort(key=lambda m: m.speed_score, reverse=True)
        elif strategy == "cost":
            candidates.sort(key=lambda m: m.cost_score, reverse=True)
        elif strategy == "privacy":
            candidates.sort(key=lambda m: m.privacy_score, reverse=True)
        else:  # balanced
            candidates.sort(key=lambda m: (
                m.quality_score * 0.4 +
                m.speed_score * 0.2 +
                m.cost_score * 0.2 +
                m.privacy_score * 0.2
            ), reverse=True)

        selected = candidates[0]
        self._call_count[selected.model_id] = self._call_count.get(selected.model_id, 0) + 1

        logger.info(f"模型路由: {capability.value} → {selected.name} (策略: {strategy})")
        return selected

    def route_pipeline(self, capabilities: List[ModelCapability],
                       strategy: str = "auto") -> Dict[ModelCapability, ModelInfo]:
        """
        为一组能力路由完整管线

        Returns:
            {能力: 模型} 的映射
        """
        pipeline = {}
        for cap in capabilities:
            pipeline[cap] = self.route(cap, strategy)
        return pipeline

    async def call_model(self, model: ModelInfo, prompt: str,
                         system_prompt: str = "", **kwargs) -> str:
        """
        调用模型

        Args:
            model: 模型信息
            prompt: 用户提示
            system_prompt: 系统提示

        Returns:
            模型输出文本
        """
        if model.backend == ModelBackend.MOCK:
            return self._mock_response(prompt)

        elif model.backend == ModelBackend.OLLAMA:
            return await self._call_ollama(model, prompt, system_prompt)

        elif model.backend == ModelBackend.OPENAI:
            return await self._call_openai(model, prompt, system_prompt)

        elif model.backend == ModelBackend.CUSTOM:
            handler = kwargs.get("handler")
            if handler and callable(handler):
                return await handler(prompt, system_prompt)
            return ""

        return ""

    async def _call_ollama(self, model: ModelInfo, prompt: str,
                           system_prompt: str = "") -> str:
        """调用 Ollama 模型"""
        try:
            import aiohttp
            url = model.config.get("url", "http://localhost:11434")
            model_name = model.config.get("model", "qwen2.5")

            payload = {
                "model": model_name,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(f"{url}/api/generate", json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("response", "")
                    else:
                        logger.error(f"Ollama 调用失败: {resp.status}")
                        return ""
        except ImportError:
            logger.warning("aiohttp 未安装, 尝试 requests")
            return self._call_ollama_sync(model, prompt, system_prompt)
        except Exception as e:
            logger.error(f"Ollama 调用异常: {e}")
            return ""

    def _call_ollama_sync(self, model: ModelInfo, prompt: str,
                          system_prompt: str = "") -> str:
        """同步调用 Ollama"""
        try:
            import requests
            url = model.config.get("url", "http://localhost:11434")
            model_name = model.config.get("model", "qwen2.5")

            resp = requests.post(f"{url}/api/generate", json={
                "model": model_name,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False,
            }, timeout=120)

            if resp.status_code == 200:
                return resp.json().get("response", "")
        except Exception as e:
            logger.error(f"Ollama 同步调用异常: {e}")
        return ""

    async def _call_openai(self, model: ModelInfo, prompt: str,
                           system_prompt: str = "") -> str:
        """调用 OpenAI API"""
        try:
            import openai
            model_name = model.config.get("model", "gpt-3.5-turbo")

            client = openai.AsyncOpenAI()
            response = await client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI 调用异常: {e}")
            return ""

    @staticmethod
    def _mock_response(prompt: str) -> str:
        """模拟模型响应 (测试用)"""
        if "规划" in prompt or "大纲" in prompt or "plan" in prompt.lower():
            return """# 文档大纲

## 1. 概述
- 背景
- 目标
- 范围

## 2. 详细内容
- 2.1 分析
- 2.2 方案
- 2.3 实施

## 3. 总结
- 结论
- 建议
"""

        return f"[模拟响应] 基于提示生成的内容: {prompt[:100]}..."

    def list_models(self, capability: ModelCapability = None) -> List[dict]:
        """列出可用模型"""
        results = []
        for m in self.models.values():
            if capability and capability not in m.capabilities:
                continue
            results.append(m.to_dict())
        return results

    def get_stats(self) -> dict:
        """获取路由统计"""
        return {
            "total_models": len(self.models),
            "call_counts": dict(self._call_count),
        }
