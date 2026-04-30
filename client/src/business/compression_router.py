"""
智能压缩路由中间件

将压缩功能深度集成到模型路由系统中：
1. 自动压缩模型响应
2. 智能选择压缩策略
3. 透明的压缩/解压流程
4. 性能监控与统计

Author: LivingTreeAI Agent
Date: 2026-04-30
"""

import asyncio
from typing import Dict, Any, Optional, List, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
from functools import wraps

from business.compression_integration import get_compression_integration, CompressionStrategy
from business.global_model_router import GlobalModelRouter


class CompressionMode(Enum):
    """压缩模式"""
    AUTO = "auto"              # 自动选择
    ALWAYS = "always"          # 始终压缩
    NEVER = "never"            # 从不压缩
    ADAPTIVE = "adaptive"      # 自适应


@dataclass
class CompressionPolicy:
    """压缩策略配置"""
    mode: CompressionMode = CompressionMode.AUTO
    min_length: int = 100      # 最小压缩长度
    max_length: int = 100000   # 最大压缩长度
    enabled_backends: List[str] = field(default_factory=lambda: ["ollama", "openai", "custom"])
    exclude_capabilities: List[str] = field(default_factory=lambda: ["vision", "audio"])


class CompressionRouter:
    """
    智能压缩路由中间件
    
    创新设计：
    1. 透明集成 - 不修改现有调用接口
    2. 智能策略 - 根据内容和后端自动选择
    3. 性能监控 - 实时统计压缩效果
    4. 可配置性 - 灵活的压缩策略配置
    """
    
    def __init__(self):
        self._logger = logger.bind(component="CompressionRouter")
        self._compression = get_compression_integration()
        self._router = None
        self._policy = CompressionPolicy()
        self._stats = {
            "total_calls": 0,
            "compressed_calls": 0,
            "total_original_size": 0,
            "total_compressed_size": 0,
            "avg_compression_ratio": 0.0,
            "avg_latency_ms": 0.0
        }
    
    def set_router(self, router: GlobalModelRouter):
        """设置全局模型路由器"""
        self._router = router
    
    def set_policy(self, policy: CompressionPolicy):
        """设置压缩策略"""
        self._policy = policy
    
    def _should_compress(self, capability: str, backend: str, content_length: int) -> bool:
        """判断是否需要压缩"""
        if self._policy.mode == CompressionMode.NEVER:
            return False
        
        if self._policy.mode == CompressionMode.ALWAYS:
            return True
        
        if content_length < self._policy.min_length:
            return False
        
        if content_length > self._policy.max_length:
            return False
        
        if backend.lower() not in self._policy.enabled_backends:
            return False
        
        if capability.lower() in self._policy.exclude_capabilities:
            return False
        
        return True
    
    async def _compress_response(self, response: Dict[str, Any], capability: str, backend: str) -> Dict[str, Any]:
        """压缩模型响应"""
        content = response.get("content", "")
        
        if not isinstance(content, str):
            return response
        
        if not self._should_compress(capability, backend, len(content)):
            return response
        
        start_time = asyncio.get_event_loop().time()
        compressed = await self._compression.compress_text(content)
        latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
        
        if compressed.get("success"):
            self._stats["compressed_calls"] += 1
            self._stats["total_original_size"] += compressed["original_length"]
            self._stats["total_compressed_size"] += compressed["compressed_length"]
            
            if self._stats["compressed_calls"] > 0:
                self._stats["avg_compression_ratio"] = (
                    1 - (self._stats["total_compressed_size"] / self._stats["total_original_size"])
                )
            
            self._stats["avg_latency_ms"] = (
                (self._stats["avg_latency_ms"] * (self._stats["total_calls"] - 1) + latency_ms) 
                / self._stats["total_calls"]
            )
            
            return {
                **response,
                "content": compressed["compressed_text"],
                "compression": {
                    "level": compressed.get("level", "full"),
                    "ratio": compressed["compression_ratio"],
                    "original_length": compressed["original_length"],
                    "compressed_length": compressed["compressed_length"],
                    "latency_ms": latency_ms
                }
            }
        
        return response
    
    async def chat(self, model: str, messages: List[Dict], capability: str = "general", 
                   backend: str = None, **kwargs) -> Dict[str, Any]:
        """
        带压缩的聊天接口
        
        Args:
            model: 模型名称
            messages: 消息列表
            capability: 能力类型
            backend: 指定后端
            **kwargs: 其他参数
        
        Returns:
            可能被压缩的响应
        """
        self._stats["total_calls"] += 1
        
        if self._router is None:
            raise RuntimeError("全局模型路由器未设置")
        
        response = await self._router.chat(model, messages, backend, **kwargs)
        return await self._compress_response(response, capability, backend or "")
    
    async def complete(self, model: str, prompt: str, capability: str = "general",
                       backend: str = None, **kwargs) -> Dict[str, Any]:
        """
        带压缩的补全接口
        
        Args:
            model: 模型名称
            prompt: 提示词
            capability: 能力类型
            backend: 指定后端
            **kwargs: 其他参数
        
        Returns:
            可能被压缩的响应
        """
        self._stats["total_calls"] += 1
        
        if self._router is None:
            raise RuntimeError("全局模型路由器未设置")
        
        response = await self._router.complete(model, prompt, backend, **kwargs)
        return await self._compress_response(response, capability, backend or "")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取压缩统计"""
        return self._stats
    
    def reset_stats(self):
        """重置统计"""
        self._stats = {
            "total_calls": 0,
            "compressed_calls": 0,
            "total_original_size": 0,
            "total_compressed_size": 0,
            "avg_compression_ratio": 0.0,
            "avg_latency_ms": 0.0
        }


# 全局实例
_compression_router = CompressionRouter()


def get_compression_router() -> CompressionRouter:
    """获取压缩路由器实例"""
    return _compression_router


# ========== 路由装饰器 ==========

def with_compression(capability: str = "general") -> Callable:
    """
    装饰器：自动压缩模型响应
    
    使用示例：
        @with_compression(capability="writing")
        async def generate_report(prompt: str) -> Dict:
            return await llm.complete("report_model", prompt)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            
            if isinstance(result, dict) and "content" in result:
                compression = get_compression_integration()
                compressed = await compression.compress_text(result["content"])
                result["content"] = compressed.get("compressed_text", result["content"])
                result["compression_info"] = {
                    "capability": capability,
                    "ratio": compressed.get("compression_ratio", 0),
                    "level": compressed.get("level", "full")
                }
            
            return result
        
        return wrapper
    
    return decorator


# ========== 便捷函数 ==========

async def compress_llm_response(response: Dict[str, Any], capability: str = "general") -> Dict[str, Any]:
    """
    便捷函数：压缩LLM响应
    
    Args:
        response: LLM响应字典
        capability: 能力类型
    
    Returns:
        压缩后的响应
    """
    compression = get_compression_integration()
    
    if "content" in response and isinstance(response["content"], str):
        compressed = await compression.compress_text(response["content"])
        response["content"] = compressed.get("compressed_text", response["content"])
        response["compression"] = {
            "ratio": compressed.get("compression_ratio", 0),
            "level": compressed.get("level", "full"),
            "capability": capability
        }
    
    return response
