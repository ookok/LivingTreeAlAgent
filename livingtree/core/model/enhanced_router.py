"""
Enhanced Model Router - 增强版模型路由器

核心功能：
1. 集成 ProviderManager 支持多服务商
2. 优先使用 Thinking 模式
3. 完整的 Opik 可观测性
4. 智能路由和负载均衡
5. 自动故障转移

支持的服务商：
- DeepSeek (Thinking模式支持)
- OpenAI (Thinking模式支持)
- Anthropic Claude-3 (Thinking模式支持)
- Google Gemini (Thinking模式支持)
- Ollama (本地模型)
- Azure OpenAI
- Together AI
- Cohere

设计理念：
- Thinking 模式优先：对于需要深度推理的任务，优先选择支持 Thinking 模式的模型
- 质量优先：在成本允许范围内选择最佳质量模型
- 可观测性：所有调用都通过 Opik 追踪
- 智能降级：主模型失败时自动降级到备用模型

注意：ProviderManager 目前仍位于 legacy (`business.provider_manager`)，
     待 ProviderManager 迁移后需更新此处的导入路径。
"""

import asyncio
import time
import logging
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class RoutingStrategy(Enum):
    """路由策略"""
    AUTO = "auto"           # 自动选择
    QUALITY = "quality"     # 质量优先
    SPEED = "speed"         # 速度优先
    COST = "cost"           # 成本优先
    BALANCED = "balanced"   # 平衡策略


class ModelCapability(Enum):
    """模型能力枚举（与 legacy provider_manager 保持一致）"""
    CHAT = "chat"
    CONTENT_GENERATION = "content_generation"
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    REASONING = "reasoning"
    PLANNING = "planning"
    SUMMARIZATION = "summarization"
    TRANSLATION = "translation"
    FORMAT_UNDERSTANDING = "format_understanding"
    DOCUMENT_PLANNING = "document_planning"
    COMPLIANCE_CHECK = "compliance_check"
    OPTIMIZATION = "optimization"
    WEB_SEARCH = "web_search"


@dataclass
class EnhancedResponse:
    """增强版响应"""
    content: str
    model_used: str
    provider_used: str
    thinking_enabled: bool
    tokens_used: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    success: bool = True
    error: Optional[str] = None
    thinking_content: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "model_used": self.model_used,
            "provider_used": self.provider_used,
            "thinking_enabled": self.thinking_enabled,
            "tokens_used": self.tokens_used,
            "latency_ms": self.latency_ms,
            "cost_usd": self.cost_usd,
            "success": self.success,
            "error": self.error,
            "thinking_content": self.thinking_content,
        }


class EnhancedModelRouter:
    """
    增强版模型路由器

    核心特性：
    1. 多服务商支持（15+主流服务商）
    2. 自适应 Thinking 模式（根据任务类型自动判断）
    3. 完整的 Opik 可观测性
    4. 智能路由和负载均衡
    5. 自动故障转移

    ProviderManager 通过 lazy import 加载，支持后续切换路径。
    """

    def __init__(self, provider_manager=None):
        # 支持依赖注入（用于测试和迁移）
        if provider_manager is not None:
            self._provider_manager = provider_manager
            self._model_capability = type(list(provider_manager._models.values())[0].capabilities[0]) if provider_manager._models else ModelCapability
        else:
            # Lazy import — ProviderManager 迁移后可更新此路径
            from business.provider_manager import get_provider_manager, ModelCapability as _MC
            self._provider_manager = get_provider_manager()
            self._model_capability = _MC

        # Opik 追踪支持
        self._opik_available = False
        self._init_opik()

        # 调用统计
        self._call_stats: Dict[str, Any] = {
            "total_calls": 0,
            "success_calls": 0,
            "failed_calls": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "provider_stats": {}
        }

        # Thinking 模式自适应规则
        self._thinking_required_capabilities = {
            ModelCapability.REASONING,
            ModelCapability.PLANNING,
            ModelCapability.CODE_REVIEW,
            ModelCapability.COMPLIANCE_CHECK,
            ModelCapability.OPTIMIZATION,
            ModelCapability.DOCUMENT_PLANNING
        }

        self._thinking_optional_capabilities = {
            ModelCapability.CODE_GENERATION,
            ModelCapability.CONTENT_GENERATION,
            ModelCapability.FORMAT_UNDERSTANDING
        }

        self._thinking_not_needed = {
            ModelCapability.CHAT,
            ModelCapability.SUMMARIZATION,
            ModelCapability.TRANSLATION,
            ModelCapability.WEB_SEARCH
        }

        logger.info("EnhancedModelRouter 初始化完成 (livingtree.core.model)")

    def _should_use_thinking(self, capability, prompt: str,
                             prefer_thinking: Optional[bool] = None) -> bool:
        """自适应判断是否需要使用 Thinking 模式"""
        if prefer_thinking is not None:
            return prefer_thinking

        # 标准化 capability 为本地 ModelCapability 枚举
        cap = self._normalize_capability(capability)

        if cap in self._thinking_required_capabilities:
            return True
        if cap in self._thinking_not_needed:
            return False
        if cap in self._thinking_optional_capabilities:
            return self._assess_prompt_complexity(prompt)
        return False

    def _normalize_capability(self, capability):
        """将字符串或外部枚举标准化为本地 ModelCapability"""
        if isinstance(capability, ModelCapability):
            return capability
        if hasattr(capability, 'value'):
            name = capability.value.upper() if hasattr(capability.value, 'upper') else str(capability).upper()
        else:
            name = str(capability).upper()
        try:
            return ModelCapability(name.lower())
        except ValueError:
            return ModelCapability.CHAT

    def _assess_prompt_complexity(self, prompt: str) -> bool:
        """评估提示复杂度，决定是否需要 thinking 模式"""
        complexity_score = 0

        if len(prompt) > 200:
            complexity_score += 1
        if len(prompt) > 500:
            complexity_score += 1
        if len(prompt) > 1000:
            complexity_score += 1

        thinking_keywords = [
            "分析", "思考", "为什么", "如何", "怎样",
            "证明", "推导", "计算", "设计", "优化",
            "debug", "修复", "审查", "评估", "对比",
            "系统", "架构", "模块", "接口", "API",
            "认证", "安全", "扩展", "可扩展", "高可用",
            "数据库", "缓存", "分布式", "微服务"
        ]

        keyword_count = sum(1 for kw in thinking_keywords if kw in prompt)
        if keyword_count >= 2:
            complexity_score += 2
        elif keyword_count == 1:
            complexity_score += 1

        code_indicators = ["```", "def ", "function ", "class ", "import ",
                          "async ", "await ", "return ", "if ", "for ", "while "]
        if any(ind in prompt for ind in code_indicators):
            complexity_score += 2

        if "=" in prompt and sum(1 for c in prompt if c in "0123456789") > 5:
            complexity_score += 1

        if prompt.count("，") >= 3 or prompt.count(",") >= 3:
            complexity_score += 1

        return complexity_score >= 3

    def _init_opik(self):
        """初始化 Opik 可观测性"""
        try:
            from opik import Opik
            from opik.tracing import trace
            self._opik_client = Opik(project_name="LivingTreeAI-Pipeline")
            self._opik_trace = trace
            self._opik_available = True
            logger.info("Opik 可观测性已集成")
        except ImportError:
            logger.debug("Opik SDK 未安装，可观测性功能不可用")

    async def call_model(self, capability: Union[str, Enum], prompt: str,
                         system_prompt: str = "",
                         strategy: RoutingStrategy = RoutingStrategy.AUTO,
                         prefer_thinking: Optional[bool] = None,
                         max_tokens: int = 1024,
                         temperature: float = 0.7,
                         **kwargs) -> EnhancedResponse:
        """
        调用模型（统一入口）

        Args:
            capability: 需要的能力（字符串或 ModelCapability 枚举）
            prompt: 用户提示
            system_prompt: 系统提示
            strategy: 路由策略
            prefer_thinking: 是否优先使用 Thinking 模式（None 表示自适应判断）
            max_tokens: 最大 token 数
            temperature: 温度参数

        Returns:
            EnhancedResponse 对象
        """
        start_time = time.time()

        # 转换为 legacy ModelCapability（ProviderManager 需要）
        pm_capability = self._to_provider_capability(capability)

        # 自适应判断是否需要 Thinking 模式
        thinking_enabled = self._should_use_thinking(capability, prompt, prefer_thinking)

        # Opik 追踪
        opik_span = None
        opik_start_time = time.time()
        if self._opik_available:
            try:
                cap_name = capability.value if hasattr(capability, 'value') else str(capability)
                opik_span = self._opik_trace.start_span(
                    name=f"llm_call_{cap_name}",
                    trace_type="llm",
                    metadata={
                        "capability": cap_name,
                        "strategy": strategy.value,
                        "thinking_enabled": thinking_enabled,
                        "max_tokens": max_tokens,
                        "temperature": temperature
                    }
                )
            except Exception as e:
                logger.debug(f"Opik 追踪初始化失败: {e}")

        try:
            models = self._provider_manager.get_models_for_capability(
                pm_capability,
                prefer_thinking=thinking_enabled
            )

            if not models:
                cap_name = pm_capability.value if hasattr(pm_capability, 'value') else str(pm_capability)
                raise ValueError(f"无可用模型支持能力: {cap_name}")

            models = self._apply_strategy(models, strategy)

            # 尝试调用模型（带故障转移，最多3个）
            response = None
            last_error = None

            for model in models[:3]:
                try:
                    response = await self._provider_manager.call_model(
                        capability=pm_capability,
                        prompt=prompt,
                        system_prompt=system_prompt,
                        prefer_thinking=thinking_enabled and model.supports_thinking,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        **kwargs
                    )

                    if response.metrics.success:
                        break
                    else:
                        last_error = response.metrics.error
                except Exception as e:
                    last_error = str(e)
                    logger.warning(f"模型调用失败: {model.name}, 错误: {e}")

            if response is None or not response.metrics.success:
                raise ValueError(f"所有模型调用失败: {last_error}")

            latency_ms = (time.time() - start_time) * 1000
            self._update_stats(response, latency_ms)

            # 更新 Opik 追踪
            if opik_span:
                try:
                    opik_span.set_output(response.content)
                    opik_span.set_attributes({
                        "model": response.model_used,
                        "provider": response.provider_used,
                        "tokens_used": response.metrics.total_tokens,
                        "latency_ms": latency_ms,
                        "cost_usd": response.metrics.cost_usd,
                        "thinking_enabled": response.metrics.thinking_enabled,
                        "trace_duration_ms": (time.time() - opik_start_time) * 1000
                    })
                except Exception as e:
                    logger.debug(f"Opik 追踪更新失败: {e}")

            return EnhancedResponse(
                content=response.content,
                model_used=response.model_used,
                provider_used=response.provider_used,
                thinking_enabled=response.metrics.thinking_enabled,
                tokens_used=response.metrics.total_tokens,
                latency_ms=latency_ms,
                cost_usd=response.metrics.cost_usd,
                success=True,
                thinking_content=response.thinking_content
            )

        except Exception as e:
            self._call_stats["failed_calls"] += 1

            if opik_span:
                try:
                    opik_span.set_error(str(e))
                except Exception:
                    pass

            return EnhancedResponse(
                content="",
                model_used="",
                provider_used="",
                thinking_enabled=False,
                success=False,
                error=str(e)
            )

    def _to_provider_capability(self, capability):
        """将本地 ModelCapability 或字符串转换为 ProviderManager 的 ModelCapability"""
        if hasattr(capability, 'value'):
            name = capability.value
        else:
            name = str(capability)
        try:
            return getattr(self._model_capability, name.upper())
        except AttributeError:
            return self._model_capability.CHAT

    def _apply_strategy(self, models: List, strategy: RoutingStrategy) -> List:
        """根据策略排序模型"""
        if strategy == RoutingStrategy.QUALITY:
            models.sort(key=lambda x: (-x.quality_score, -x.supports_thinking))
        elif strategy == RoutingStrategy.SPEED:
            models.sort(key=lambda x: (-x.speed_score, -x.supports_thinking))
        elif strategy == RoutingStrategy.COST:
            models.sort(key=lambda x: (x.cost_score, -x.supports_thinking))
        elif strategy == RoutingStrategy.BALANCED:
            models.sort(key=lambda x: (
                -(x.quality_score * 0.4 + x.speed_score * 0.3 + x.cost_score * 0.3),
                -x.supports_thinking
            ))
        return models

    def _update_stats(self, response, latency_ms: float):
        """更新调用统计"""
        self._call_stats["total_calls"] += 1
        self._call_stats["success_calls"] += 1
        self._call_stats["total_tokens"] += response.metrics.total_tokens
        self._call_stats["total_cost_usd"] += response.metrics.cost_usd

        provider = response.provider_used
        if provider not in self._call_stats["provider_stats"]:
            self._call_stats["provider_stats"][provider] = {
                "calls": 0, "tokens": 0, "cost_usd": 0.0
            }
        self._call_stats["provider_stats"][provider]["calls"] += 1
        self._call_stats["provider_stats"][provider]["tokens"] += response.metrics.total_tokens
        self._call_stats["provider_stats"][provider]["cost_usd"] += response.metrics.cost_usd

    def get_stats(self) -> Dict[str, Any]:
        """获取调用统计"""
        total = max(self._call_stats["total_calls"], 1)
        return {
            "total_calls": self._call_stats["total_calls"],
            "success_calls": self._call_stats["success_calls"],
            "failed_calls": self._call_stats["failed_calls"],
            "success_rate": (self._call_stats["success_calls"] / total) * 100,
            "total_tokens": self._call_stats["total_tokens"],
            "total_cost_usd": round(self._call_stats["total_cost_usd"], 4),
            "provider_stats": self._call_stats["provider_stats"]
        }

    def generate_report(self) -> str:
        """生成完整报告"""
        stats = self.get_stats()
        provider_report = self._provider_manager.generate_report()

        report = f"""
╔══════════════════════════════════════════════════════════════╗
║              Enhanced Model Router 报告                     ║
╠══════════════════════════════════════════════════════════════╣
║  总调用次数:      {stats['total_calls']:>10} 次             ║
║  成功次数:       {stats['success_calls']:>10} 次             ║
║  失败次数:       {stats['failed_calls']:>10} 次             ║
║  成功率:         {stats['success_rate']:>10.2f}%             ║
║  总 Token 数:    {stats['total_tokens']:>10}               ║
║  总成本(USD):    ${stats['total_cost_usd']:>10.4f}        ║
╠══════════════════════════════════════════════════════════════╣
║  服务商统计:                                                ║
"""
        for provider, data in stats["provider_stats"].items():
            percentage = (data["calls"] / max(stats["total_calls"], 1)) * 100
            report += f"║    {provider:15}  {data['calls']:5} 次  ({percentage:5.1f}%)\n"

        report += f"""
╠══════════════════════════════════════════════════════════════╣
║  Provider Manager 报告:                                     ║
{provider_report}
╚══════════════════════════════════════════════════════════════╝
"""
        return report

    def get_available_models(self) -> List[Dict[str, Any]]:
        """获取可用模型列表"""
        models = []
        for model_id, model in self._provider_manager._models.items():
            provider_config = self._provider_manager._providers.get(model.provider)
            is_available = provider_config and provider_config.enabled and provider_config.api_key

            models.append({
                "model_id": model.model_id,
                "name": model.name,
                "provider": model.provider.value,
                "capabilities": [c.value for c in model.capabilities],
                "supports_thinking": model.supports_thinking,
                "quality_score": model.quality_score,
                "speed_score": model.speed_score,
                "cost_score": model.cost_score,
                "max_tokens": model.max_tokens,
                "context_length": model.context_length,
                "is_available": is_available
            })

        return models

    def get_providers(self) -> List[Dict[str, Any]]:
        """获取服务商列表"""
        providers = []
        for provider_type, config in self._provider_manager._providers.items():
            providers.append({
                "type": provider_type.value,
                "enabled": config.enabled,
                "has_api_key": bool(config.api_key),
                "priority": config.priority,
                "base_url": config.base_url,
                "model_count": len(config.models)
            })

        return providers


# ---------------------------------------------------------------------------
# 全局单例 + 快捷函数
# ---------------------------------------------------------------------------

_global_enhanced_router: Optional[EnhancedModelRouter] = None


def get_enhanced_model_router() -> EnhancedModelRouter:
    """获取全局 EnhancedModelRouter 单例"""
    global _global_enhanced_router
    if _global_enhanced_router is None:
        _global_enhanced_router = EnhancedModelRouter()
    return _global_enhanced_router


async def call_model(capability: Union[str, Enum], prompt: str,
                     system_prompt: str = "",
                     strategy: RoutingStrategy = RoutingStrategy.AUTO,
                     prefer_thinking: bool = True,
                     **kwargs) -> EnhancedResponse:
    """快捷调用函数"""
    router = get_enhanced_model_router()
    return await router.call_model(
        capability=capability,
        prompt=prompt,
        system_prompt=system_prompt,
        strategy=strategy,
        prefer_thinking=prefer_thinking,
        **kwargs
    )


# ---------------------------------------------------------------------------
# 测试函数
# ---------------------------------------------------------------------------

async def test_enhanced_router():
    """测试 EnhancedModelRouter"""
    print("Testing EnhancedModelRouter (livingtree.core.model)")
    print("=" * 60)

    router = get_enhanced_model_router()

    models = router.get_available_models()
    print(f"Available models: {len(models)}")

    providers = router.get_providers()
    print(f"Providers: {len(providers)}")
    for p in providers:
        status = "enabled" if p["enabled"] and p["has_api_key"] else "disabled"
        print(f"   {p['type']} ({status}, priority: {p['priority']})")

    print("\nTesting model call:")
    result = await router.call_model(
        capability="reasoning",
        prompt="What is 2 + 2? Please explain step by step.",
        system_prompt="You are a helpful math assistant.",
        strategy=RoutingStrategy.BALANCED,
        prefer_thinking=True,
        max_tokens=512
    )

    if result.success:
        print(f"SUCCESS - model: {result.model_used}, provider: {result.provider_used}")
        print(f"   Thinking: {result.thinking_enabled}")
        print(f"   Response: {result.content[:100]}...")
    else:
        print(f"FAILED: {result.error}")

    print("\nReport:")
    print(router.generate_report())

    return result.success


__all__ = [
    "EnhancedModelRouter",
    "EnhancedResponse",
    "RoutingStrategy",
    "ModelCapability",
    "get_enhanced_model_router",
    "call_model",
]


if __name__ == "__main__":
    asyncio.run(test_enhanced_router())
