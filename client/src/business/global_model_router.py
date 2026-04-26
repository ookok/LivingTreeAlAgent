"""
🌐 全局模型路由器
为整个LivingTreeAI项目提供统一的LLM调用路由

功能：
- 支持20+种模型能力
- 流式调用支持
- 自动fallback机制
- 响应缓存
- 负载均衡
- 历史成功率追踪
"""

import asyncio
import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, List, Callable, Iterator, AsyncIterator
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger(__name__)


# ============= 能力定义 =============

class ModelCapability(Enum):
    """模型能力（20+种）"""
    # 基础能力
    CHAT = "chat"                           # 对话
    COMPLETION = "completion"               # 文本补全
    
    # 理解与生成
    DOCUMENT_PLANNING = "document_planning" # 文档规划
    CONTENT_GENERATION = "content_generation" # 内容生成
    FORMAT_UNDERSTANDING = "format_understanding"  # 格式理解
    COMPLIANCE_CHECK = "compliance_check"     # 合规检查
    OPTIMIZATION = "optimization"             # 优化建议
    TRANSLATION = "translation"               # 翻译
    SUMMARIZATION = "summarization"           # 摘要
    PARAPHRASE = "paraphrase"               # 改写
    
    # 代码相关
    CODE_GENERATION = "code_generation"       # 代码生成
    CODE_REVIEW = "code_review"             # 代码审查
    CODE_DEBUG = "code_debug"               # 代码调试
    CODE_EXPLANATION = "code_explanation"   # 代码解释
    
    # 知识相关
    KNOWLEDGE_QUERY = "knowledge_query"       # 知识查询
    CONCEPT_EXPLAIN = "concept_explain"       # 概念解释
    WEB_SEARCH = "web_search"               # 网络搜索
    
    # 高级能力
    REASONING = "reasoning"                 # 推理
    PLANNING = "planning"                   # 规划
    DATA_ANALYSIS = "data_analysis"         # 数据分析
    IMAGE_UNDERSTANDING = "image_understanding"  # 图像理解
    
    # 特殊能力
    STREAMING = "streaming"                 # 流式输出
    FUNCTION_CALLING = "function_calling"   # 函数调用
    JSON_MODE = "json_mode"                 # JSON模式


class ModelBackend(Enum):
    """模型后端"""
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    LOCAL_GGUF = "local_gguf"
    CUSTOM = "custom"
    MOCK = "mock"  # 测试用


@dataclass
class ModelInfo:
    """模型信息"""
    model_id: str
    name: str
    backend: ModelBackend
    
    # 能力
    capabilities: List[ModelCapability] = field(default_factory=list)
    
    # 性能参数
    max_tokens: int = 4096
    context_length: int = 4096
    quality_score: float = 0.7     # 0-1, 质量评分
    speed_score: float = 0.5       # 0-1, 速度评分
    cost_score: float = 1.0        # 0-1, 1=免费, 0=极贵
    privacy_score: float = 1.0     # 0-1, 1=完全本地
    
    # 状态
    is_available: bool = True
    current_load: int = 0          # 当前负载（正在处理的请求数）
    success_rate: float = 1.0      # 历史成功率
    avg_response_time: float = 0.0  # 平均响应时间（秒）
    
    # 配置
    config: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "model_id": self.model_id,
            "name": self.name,
            "backend": self.backend.value,
            "capabilities": [c.value for c in self.capabilities],
            "max_tokens": self.max_tokens,
            "context_length": self.context_length,
            "quality": round(self.quality_score, 2),
            "speed": round(self.speed_score, 2),
            "cost": round(self.cost_score, 2),
            "privacy": round(self.privacy_score, 2),
            "available": self.is_available,
            "current_load": self.current_load,
            "success_rate": round(self.success_rate, 2),
            "avg_response_time": round(self.avg_response_time, 2),
        }
    
    def supports_capability(self, capability: ModelCapability) -> bool:
        """检查是否支持某能力"""
        return capability in self.capabilities
    
    def can_handle_context(self, context_length: int) -> bool:
        """检查是否能处理指定上下文长度"""
        return self.context_length >= context_length
    
    def update_stats(self, success: bool, response_time: float):
        """更新统计信息"""
        # 更新成功率（指数移动平均）
        alpha = 0.1
        self.success_rate = (1 - alpha) * self.success_rate + alpha * (1.0 if success else 0.0)
        
        # 更新平均响应时间
        if self.avg_response_time == 0:
            self.avg_response_time = response_time
        else:
            self.avg_response_time = (1 - alpha) * self.avg_response_time + alpha * response_time


# ============= 路由策略 =============

class RoutingStrategy(Enum):
    """路由策略"""
    QUALITY = "quality"       # 质量优先
    SPEED = "speed"           # 速度优先
    COST = "cost"             # 成本优先
    PRIVACY = "privacy"       # 隐私优先
    BALANCED = "balanced"     # 均衡模式
    AUTO = "auto"             # 自动选择（根据能力）


class GlobalModelRouter:
    """
    全局模型路由器
    
    所有LLM调用都应通过此路由器，不应直接调用OllamaClient等
    """
    
    # 任务 → 策略 映射（auto策略时使用）
    TASK_STRATEGY_MAP = {
        ModelCapability.DOCUMENT_PLANNING: RoutingStrategy.BALANCED,
        ModelCapability.CONTENT_GENERATION: RoutingStrategy.QUALITY,
        ModelCapability.FORMAT_UNDERSTANDING: RoutingStrategy.BALANCED,
        ModelCapability.COMPLIANCE_CHECK: RoutingStrategy.QUALITY,
        ModelCapability.OPTIMIZATION: RoutingStrategy.BALANCED,
        ModelCapability.TRANSLATION: RoutingStrategy.SPEED,
        ModelCapability.SUMMARIZATION: RoutingStrategy.SPEED,
        ModelCapability.CODE_GENERATION: RoutingStrategy.QUALITY,
        ModelCapability.CODE_REVIEW: RoutingStrategy.QUALITY,
        ModelCapability.CODE_DEBUG: RoutingStrategy.QUALITY,
        ModelCapability.WEB_SEARCH: RoutingStrategy.SPEED,
        ModelCapability.REASONING: RoutingStrategy.QUALITY,
        ModelCapability.PLANNING: RoutingStrategy.QUALITY,
    }
    
    def __init__(self):
        self.models: Dict[str, ModelInfo] = {}
        self._call_count: Dict[str, int] = defaultdict(int)
        self._cache: Dict[str, str] = {}  # 响应缓存 {hash: response}
        self._cache_ttl: int = 3600  # 缓存TTL（秒）
        self._cache_timestamps: Dict[str, float] = {}
        
        # 加载内置模型
        self._load_builtin_models()
    
    def _load_builtin_models(self):
        """加载内置模型配置"""
        builtin_models = [
            ModelInfo(
                model_id="ollama_qwen2.5",
                name="Qwen2.5 (Ollama)",
                backend=ModelBackend.OLLAMA,
                capabilities=[
                    ModelCapability.CHAT,
                    ModelCapability.CONTENT_GENERATION,
                    ModelCapability.SUMMARIZATION,
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.TRANSLATION,
                ],
                max_tokens=8192,
                context_length=32768,
                quality_score=0.75,
                speed_score=0.7,
                cost_score=1.0,
                privacy_score=1.0,
                config={"url": "http://localhost:11434", "model": "qwen2.5"},
            ),
            ModelInfo(
                model_id="ollama_deepseek",
                name="DeepSeek Coder (Ollama)",
                backend=ModelBackend.OLLAMA,
                capabilities=[
                    ModelCapability.CHAT,
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.CODE_REVIEW,
                    ModelCapability.CODE_DEBUG,
                    ModelCapability.FUNCTION_CALLING,
                ],
                max_tokens=8192,
                context_length=16384,
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
                    ModelCapability.CHAT,
                    ModelCapability.DOCUMENT_PLANNING,
                    ModelCapability.CONTENT_GENERATION,
                    ModelCapability.FORMAT_UNDERSTANDING,
                    ModelCapability.COMPLIANCE_CHECK,
                    ModelCapability.OPTIMIZATION,
                    ModelCapability.TRANSLATION,
                    ModelCapability.SUMMARIZATION,
                    ModelCapability.REASONING,
                    ModelCapability.PLANNING,
                    ModelCapability.FUNCTION_CALLING,
                    ModelCapability.JSON_MODE,
                ],
                max_tokens=8192,
                context_length=128000,
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
                    ModelCapability.CHAT,
                    ModelCapability.CONTENT_GENERATION,
                    ModelCapability.SUMMARIZATION,
                    ModelCapability.TRANSLATION,
                    ModelCapability.CODE_GENERATION,
                ],
                max_tokens=4096,
                context_length=16384,
                quality_score=0.7,
                speed_score=0.8,
                cost_score=0.5,
                privacy_score=0.1,
                config={"model": "gpt-3.5-turbo"},
            ),
        ]
        
        for m in builtin_models:
            self.models[m.model_id] = m
            logger.info(f"加载内置模型: {m.name} ({m.model_id})")
    
    def register_model(self, model: ModelInfo):
        """注册自定义模型"""
        self.models[model.model_id] = model
        logger.info(f"注册模型: {model.name} ({model.model_id})")
    
    def unregister_model(self, model_id: str):
        """注销模型"""
        if model_id in self.models:
            model_name = self.models[model_id].name
            del self.models[model_id]
            logger.info(f"注销模型: {model_name} ({model_id})")
    
    def route(self, capability: ModelCapability,
              strategy: RoutingStrategy = RoutingStrategy.AUTO,
              context_length: int = 0,
              exclude_models: List[str] = None) -> Optional[ModelInfo]:
        """
        路由到最佳模型
        
        Args:
            capability: 需要的能力
            strategy: 路由策略
            context_length: 需要的上下文长度（0=不限制）
            exclude_models: 排除的模型ID列表
        
        Returns:
            ModelInfo 最佳模型，如无则返回None
        """
        # 确定策略
        if strategy == RoutingStrategy.AUTO:
            strategy = self.TASK_STRATEGY_MAP.get(capability, RoutingStrategy.BALANCED)
        
        # 筛选具备该能力的可用模型
        exclude_set = set(exclude_models or [])
        candidates = [
            m for m in self.models.values()
            if capability in m.capabilities 
            and m.is_available
            and m.model_id not in exclude_set
            and (context_length == 0 or m.can_handle_context(context_length))
        ]
        
        if not candidates:
            logger.warning(f"无可用模型支持 {capability.value}")
            return None
        
        # 按策略排序
        if strategy == RoutingStrategy.QUALITY:
            candidates.sort(key=lambda m: (
                m.quality_score * 0.5 +
                m.success_rate * 0.3 +
                (1.0 / (m.current_load + 1)) * 0.2
            ), reverse=True)
        
        elif strategy == RoutingStrategy.SPEED:
            candidates.sort(key=lambda m: (
                m.speed_score * 0.4 +
                (1.0 / (m.avg_response_time + 0.001)) * 0.3 +
                (1.0 / (m.current_load + 1)) * 0.3
            ), reverse=True)
        
        elif strategy == RoutingStrategy.COST:
            candidates.sort(key=lambda m: m.cost_score, reverse=True)
        
        elif strategy == RoutingStrategy.PRIVACY:
            candidates.sort(key=lambda m: m.privacy_score, reverse=True)
        
        else:  # BALANCED
            candidates.sort(key=lambda m: (
                m.quality_score * 0.3 +
                m.speed_score * 0.2 +
                m.cost_score * 0.2 +
                m.privacy_score * 0.1 +
                m.success_rate * 0.1 +
                (1.0 / (m.current_load + 1)) * 0.1
            ), reverse=True)
        
        selected = candidates[0]
        self._call_count[selected.model_id] = self._call_count.get(selected.model_id, 0) + 1
        
        logger.info(f"模型路由: {capability.value} → {selected.name} (策略: {strategy.value})")
        return selected
    
    def route_with_fallback(self, capability: ModelCapability,
                           strategy: RoutingStrategy = RoutingStrategy.AUTO,
                           context_length: int = 0) -> List[ModelInfo]:
        """
        路由到模型列表（含fallback）
        
        Returns:
            按优先级排序的模型列表，第一个是最佳模型
        """
        # 确定策略
        if strategy == RoutingStrategy.AUTO:
            strategy = self.TASK_STRATEGY_MAP.get(capability, RoutingStrategy.BALANCED)
        
        # 筛选具备该能力的可用模型
        candidates = [
            m for m in self.models.values()
            if capability in m.capabilities 
            and m.is_available
            and (context_length == 0 or m.can_handle_context(context_length))
        ]
        
        if not candidates:
            return []
        
        # 按策略排序
        if strategy == RoutingStrategy.QUALITY:
            candidates.sort(key=lambda m: m.quality_score, reverse=True)
        elif strategy == RoutingStrategy.SPEED:
            candidates.sort(key=lambda m: m.speed_score, reverse=True)
        elif strategy == RoutingStrategy.COST:
            candidates.sort(key=lambda m: m.cost_score, reverse=True)
        elif strategy == RoutingStrategy.PRIVACY:
            candidates.sort(key=lambda m: m.privacy_score, reverse=True)
        else:  # BALANCED
            candidates.sort(key=lambda m: (
                m.quality_score * 0.4 +
                m.speed_score * 0.2 +
                m.cost_score * 0.2 +
                m.privacy_score * 0.2
            ), reverse=True)
        
        return candidates
    
    def _get_cache_key(self, model: ModelInfo, prompt: str, system_prompt: str = "") -> str:
        """生成缓存key"""
        content = f"{model.model_id}:{prompt}:{system_prompt}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _get_from_cache(self, cache_key: str) -> Optional[str]:
        """从缓存获取"""
        if cache_key not in self._cache:
            return None
        
        # 检查TTL
        timestamp = self._cache_timestamps.get(cache_key, 0)
        if time.time() - timestamp > self._cache_ttl:
            # 过期，删除
            del self._cache[cache_key]
            del self._cache_timestamps[cache_key]
            return None
        
        return self._cache[cache_key]
    
    def _save_to_cache(self, cache_key: str, response: str):
        """保存到缓存"""
        self._cache[cache_key] = response
        self._cache_timestamps[cache_key] = time.time()
        
        # 简单清理：如果缓存太多，删除最旧的20%
        if len(self._cache) > 1000:
            sorted_keys = sorted(self._cache_timestamps.items(), key=lambda x: x[1])
            for key, _ in sorted_keys[:200]:
                del self._cache[key]
                del self._cache_timestamps[key]
    
    async def call_model(self, capability: ModelCapability,
                        prompt: str,
                        system_prompt: str = "",
                        strategy: RoutingStrategy = RoutingStrategy.AUTO,
                        context_length: int = 0,
                        use_cache: bool = True,
                        **kwargs) -> str:
        """
        调用模型（同步返回）
        
        Args:
            capability: 需要的能力
            prompt: 用户提示
            system_prompt: 系统提示
            strategy: 路由策略
            context_length: 需要的上下文长度
            use_cache: 是否使用缓存
        
        Returns:
            模型输出文本
        """
        # 路由到模型
        model = self.route(capability, strategy, context_length)
        if not model:
            return ""
        
        # 检查缓存
        if use_cache:
            cache_key = self._get_cache_key(model, prompt, system_prompt)
            cached = self._get_from_cache(cache_key)
            if cached:
                logger.info(f"缓存命中: {model.name}")
                return cached
        
        # 调用模型
        model.current_load += 1
        start_time = time.time()
        success = False
        response = ""
        
        try:
            if model.backend == ModelBackend.MOCK:
                response = self._mock_response(prompt)
                success = True
            
            elif model.backend == ModelBackend.OLLAMA:
                response = await self._call_ollama(model, prompt, system_prompt)
                success = bool(response)
            
            elif model.backend == ModelBackend.OPENAI:
                response = await self._call_openai(model, prompt, system_prompt)
                success = bool(response)
            
            elif model.backend == ModelBackend.CUSTOM:
                handler = kwargs.get("handler")
                if handler and callable(handler):
                    response = await handler(prompt, system_prompt)
                    success = bool(response)
        
        except Exception as e:
            logger.error(f"模型调用异常: {e}")
            success = False
        
        finally:
            model.current_load -= 1
            response_time = time.time() - start_time
            model.update_stats(success, response_time)
        
        # 保存到缓存
        if success and use_cache:
            cache_key = self._get_cache_key(model, prompt, system_prompt)
            self._save_to_cache(cache_key, response)
        
        return response
    
    async def call_model_with_fallback(self, capability: ModelCapability,
                                      prompt: str,
                                      system_prompt: str = "",
                                      strategy: RoutingStrategy = RoutingStrategy.AUTO,
                                      context_length: int = 0,
                                      **kwargs) -> str:
        """
        调用模型（带fallback）
        
        如果最佳模型失败，自动尝试下一个
        """
        models = self.route_with_fallback(capability, strategy, context_length)
        
        for model in models:
            logger.info(f"尝试模型: {model.name}")
            
            model.current_load += 1
            start_time = time.time()
            success = False
            response = ""
            
            try:
                if model.backend == ModelBackend.OLLAMA:
                    response = await self._call_ollama(model, prompt, system_prompt)
                    success = bool(response)
                
                elif model.backend == ModelBackend.OPENAI:
                    response = await self._call_openai(model, prompt, system_prompt)
                    success = bool(response)
                
                elif model.backend == ModelBackend.CUSTOM:
                    handler = kwargs.get("handler")
                    if handler and callable(handler):
                        response = await handler(prompt, system_prompt)
                        success = bool(response)
                
                if success:
                    logger.info(f"模型调用成功: {model.name}")
                    return response
                else:
                    logger.warning(f"模型调用失败: {model.name}, 尝试下一个")
            
            except Exception as e:
                logger.error(f"模型调用异常: {model.name}, 错误: {e}")
            
            finally:
                model.current_load -= 1
                response_time = time.time() - start_time
                model.update_stats(success, response_time)
        
        logger.error("所有模型都调用失败")
        return ""
    
    async def call_model_stream(self, capability: ModelCapability,
                                prompt: str,
                                system_prompt: str = "",
                                strategy: RoutingStrategy = RoutingStrategy.AUTO,
                                context_length: int = 0,
                                **kwargs) -> AsyncIterator[str]:
        """
        调用模型（流式返回）
        
        Yields:
            文本片段
        """
        model = self.route(capability, strategy, context_length)
        if not model:
            yield ""
            return
        
        model.current_load += 1
        start_time = time.time()
        success = False
        
        try:
            if model.backend == ModelBackend.OLLAMA:
                async for chunk in self._call_ollama_stream(model, prompt, system_prompt):
                    yield chunk
                success = True
            
            elif model.backend == ModelBackend.OPENAI:
                async for chunk in self._call_openai_stream(model, prompt, system_prompt):
                    yield chunk
                success = True
        
        except Exception as e:
            logger.error(f"流式调用异常: {e}")
        
        finally:
            model.current_load -= 1
            response_time = time.time() - start_time
            model.update_stats(success, response_time)
    
    # ============= 后端调用实现 =============
    
    async def _call_ollama(self, model: ModelInfo, prompt: str,
                           system_prompt: str = "") -> str:
        """调用 Ollama 模型（同步）"""
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
        except Exception as e:
            logger.error(f"Ollama 调用异常: {e}")
            return ""
    
    async def _call_ollama_stream(self, model: ModelInfo, prompt: str,
                                  system_prompt: str = "") -> AsyncIterator[str]:
        """调用 Ollama 模型（流式）"""
        try:
            import aiohttp
            url = model.config.get("url", "http://localhost:11434")
            model_name = model.config.get("model", "qwen2.5")
            
            payload = {
                "model": model_name,
                "prompt": prompt,
                "system": system_prompt,
                "stream": True,
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{url}/api/generate", json=payload) as resp:
                    if resp.status == 200:
                        async for line in resp.content:
                            if line:
                                try:
                                    data = json.loads(line)
                                    if "response" in data:
                                        yield data["response"]
                                except:
                                    pass
        
        except Exception as e:
            logger.error(f"Ollama 流式调用异常: {e}")
    
    async def _call_openai(self, model: ModelInfo, prompt: str,
                           system_prompt: str = "") -> str:
        """调用 OpenAI API（同步）"""
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
    
    async def _call_openai_stream(self, model: ModelInfo, prompt: str,
                                  system_prompt: str = "") -> AsyncIterator[str]:
        """调用 OpenAI API（流式）"""
        try:
            import openai
            model_name = model.config.get("model", "gpt-3.5-turbo")
            
            client = openai.AsyncOpenAI()
            stream = await client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                stream=True,
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        
        except Exception as e:
            logger.error(f"OpenAI 流式调用异常: {e}")
    
    @staticmethod
    def _mock_response(prompt: str) -> str:
        """模拟模型响应（测试用）"""
        return f"[模拟响应] 基于提示生成的内容: {prompt[:50]}..."
    
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
            "available_models": sum(1 for m in self.models.values() if m.is_available),
            "call_counts": dict(self._call_count),
            "cache_size": len(self._cache),
        }
    
    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        self._cache_timestamps.clear()
        logger.info("缓存已清空")


# ============= 全局实例 =============

_global_router: Optional[GlobalModelRouter] = None

def get_global_router() -> GlobalModelRouter:
    """获取全局路由器实例（单例）"""
    global _global_router
    if _global_router is None:
        _global_router = GlobalModelRouter()
    return _global_router

def set_global_router(router: GlobalModelRouter):
    """设置全局路由器实例"""
    global _global_router
    _global_router = router


# ============= 同步调用辅助函数 =============

def call_model_sync(capability: ModelCapability,
                    prompt: str,
                    system_prompt: str = "",
                    strategy: RoutingStrategy = RoutingStrategy.AUTO,
                    context_length: int = 0,
                    use_cache: bool = True) -> str:
    """
    同步调用模型（供非异步函数使用）
    
    内部使用 asyncio.run() 调用异步的 call_model()
    注意：如果已有事件循环运行，此方法会失败
    
    Args:
        capability: 需要的能力
        prompt: 用户提示
        system_prompt: 系统提示
        strategy: 路由策略
        context_length: 需要的上下文长度
        use_cache: 是否使用缓存
    
    Returns:
        模型输出文本
    """
    router = get_global_router()
    
    try:
        # 尝试获取当前事件循环
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 已有运行中的事件循环，使用 run_until_complete
            # 注意：在某些环境中可能不支持
            return asyncio.run_coroutine_threadsafe(
                router.call_model(capability, prompt, system_prompt, strategy, context_length, use_cache),
                loop
            ).result(timeout=120)
        else:
            # 没有运行中的循环，使用 asyncio.run()
            return asyncio.run(
                router.call_model(capability, prompt, system_prompt, strategy, context_length, use_cache)
            )
    except RuntimeError:
        # 没有事件循环，创建新的
        return asyncio.run(
            router.call_model(capability, prompt, system_prompt, strategy, context_length, use_cache)
        )
