"""
Router Adapter - GlobalModelRouter 到 EnhancedModelRouter 的适配层

目的：
1. 提供向后兼容的接口，使现有代码可以无缝迁移
2. 自动将 GlobalModelRouter 的调用转发到 EnhancedModelRouter
3. 支持自适应 Thinking 模式判断
4. 逐步淘汰旧的 GlobalModelRouter 接口

使用方式：
from business.router_adapter import GlobalModelRouter

router = GlobalModelRouter()
result = await router.call_model(...)  # 自动转发到 EnhancedModelRouter
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Union
from enum import Enum

logger = logging.getLogger(__name__)


class ModelCapability(Enum):
    """模型能力枚举（保持向后兼容）"""
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


class RoutingStrategy(Enum):
    """路由策略枚举（保持向后兼容）"""
    AUTO = "auto"
    QUALITY = "quality"
    SPEED = "speed"
    COST = "cost"
    BALANCED = "balanced"


class GlobalModelRouter:
    """
    GlobalModelRouter 适配器类
    
    提供与旧版 GlobalModelRouter 兼容的接口，
    内部自动转发到 EnhancedModelRouter
    """
    
    def __init__(self):
        # 延迟导入，避免循环依赖
        from business.enhanced_model_router import get_enhanced_model_router
        
        self._enhanced_router = get_enhanced_model_router()
        logger.info("✅ GlobalModelRouter 适配器已初始化（内部使用 EnhancedModelRouter）")
    
    async def call_model(self, capability: Union[str, Enum], prompt: str,
                        system_prompt: str = "",
                        strategy: Union[str, Enum] = "balanced",
                        thinking_mode: Optional[bool] = None,
                        max_tokens: int = 1024,
                        temperature: float = 0.7,
                        **kwargs) -> Dict[str, Any]:
        """
        调用模型（兼容旧版接口）
        
        Args:
            capability: 需要的能力
            prompt: 用户提示
            system_prompt: 系统提示
            strategy: 路由策略
            thinking_mode: Thinking 模式（None 表示自适应判断）
            max_tokens: 最大 token 数
            temperature: 温度参数
        
        Returns:
            兼容旧版的响应字典
        """
        # 转换策略
        if isinstance(strategy, str):
            strategy_enum = getattr(RoutingStrategy, strategy.upper(), RoutingStrategy.BALANCED)
        else:
            strategy_enum = strategy
        
        # 调用增强版路由器
        response = await self._enhanced_router.call_model(
            capability=capability,
            prompt=prompt,
            system_prompt=system_prompt,
            strategy=strategy_enum,
            prefer_thinking=thinking_mode,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs
        )
        
        # 转换为兼容旧版的响应格式
        return {
            "content": response.content,
            "model_used": response.model_used,
            "provider_used": response.provider_used,
            "thinking_enabled": response.thinking_enabled,
            "tokens_used": response.tokens_used,
            "latency_ms": response.latency_ms,
            "cost_usd": response.cost_usd,
            "success": response.success,
            "error": response.error,
            "thinking_content": response.thinking_content
        }
    
    # 以下方法保持向后兼容
    def get_available_models(self) -> List[Dict[str, Any]]:
        """获取可用模型列表"""
        return self._enhanced_router.get_available_models()
    
    def get_providers(self) -> List[Dict[str, Any]]:
        """获取服务商列表"""
        return self._enhanced_router.get_providers()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取调用统计"""
        return self._enhanced_router.get_stats()
    
    def generate_report(self) -> str:
        """生成报告"""
        return self._enhanced_router.generate_report()


# 全局单例（保持向后兼容）
_global_model_router: Optional[GlobalModelRouter] = None


def get_instance() -> GlobalModelRouter:
    """获取全局实例（保持向后兼容）"""
    global _global_model_router
    if _global_model_router is None:
        _global_model_router = GlobalModelRouter()
    return _global_model_router


# 测试函数
async def test_adapter():
    """测试适配器"""
    print("🧪 测试 GlobalModelRouter 适配器")
    print("="*60)
    
    # 使用旧版接口
    router = GlobalModelRouter()
    
    # 测试调用（不指定 thinking_mode，让系统自适应判断）
    print("\n🔍 测试自适应 Thinking 模式判断:")
    
    # 测试简单对话（不应启用 thinking）
    result1 = await router.call_model(
        capability="chat",
        prompt="你好，今天天气怎么样？",
        strategy="balanced"
    )
    print(f"聊天任务 - Thinking: {result1['thinking_enabled']}, 成功: {result1['success']}")
    
    # 测试推理任务（应启用 thinking）
    result2 = await router.call_model(
        capability="reasoning",
        prompt="一个房间里有3个人，每个人有2个苹果，后来进来了2个人，每个人有3个苹果，现在总共有多少个苹果？",
        strategy="balanced"
    )
    print(f"推理任务 - Thinking: {result2['thinking_enabled']}, 成功: {result2['success']}")
    
    # 测试代码生成（根据复杂度自适应）
    result3 = await router.call_model(
        capability="code_generation",
        prompt="写一个简单的 Python 函数计算斐波那契数列",
        strategy="balanced"
    )
    print(f"简单代码生成 - Thinking: {result3['thinking_enabled']}, 成功: {result3['success']}")
    
    # 测试复杂代码生成（应启用 thinking）
    result4 = await router.call_model(
        capability="code_generation",
        prompt="设计一个完整的用户认证系统，包括注册、登录、密码重置、JWT 认证，需要考虑安全性和可扩展性",
        strategy="balanced"
    )
    print(f"复杂代码生成 - Thinking: {result4['thinking_enabled']}, 成功: {result4['success']}")
    
    # 输出报告
    print("\n📊 适配器报告:")
    print(router.generate_report())
    
    return all([result1['success'], result2['success'], result3['success'], result4['success']])


if __name__ == "__main__":
    asyncio.run(test_adapter())