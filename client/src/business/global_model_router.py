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
from typing import Optional, Dict, List, Callable, Iterator, AsyncIterator, Tuple
from pathlib import Path
from collections import defaultdict, OrderedDict
from functools import lru_cache
import asyncio.tasks

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
class RoutingWeights:
    """
    路由三维权重配置
    
    三个维度：
    - capability: 能力评分（质量/成功率/能力匹配度）
    - cost:        成本评分（费用越低分越高）
    - latency:     延迟评分（响应时间越短/负载越低分越高）
    
    权重和为1.0，自动归一化。
    """
    capability: float = 0.4
    cost: float = 0.3
    latency: float = 0.3

    def normalize(self) -> "RoutingWeights":
        """归一化权重（确保总和为1）"""
        total = self.capability + self.cost + self.latency
        if total == 0:
            return RoutingWeights(0.34, 0.33, 0.33)
        return RoutingWeights(
            self.capability / total,
            self.cost / total,
            self.latency / total,
        )

    def to_dict(self) -> dict:
        n = self.normalize()
        return {"capability": round(n.capability, 2), "cost": round(n.cost, 2), "latency": round(n.latency, 2)}


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
    
    def __init__(self, default_weights: RoutingWeights = None):
        """
        初始化路由器
        
        Args:
            default_weights: 默认三维权重（BALANCED策略使用），默认 capability=0.4, cost=0.3, latency=0.3
        """
        self.models: Dict[str, ModelInfo] = {}
        self._call_count: Dict[str, int] = defaultdict(int)
        
        # LRU 缓存（OrderedDict，最大 1000 条）
        self._cache: OrderedDict = OrderedDict()  # {hash: response}
        self._cache_timestamps: OrderedDict = OrderedDict()  # {hash: timestamp}
        self._cache_max_size: int = 1000
        
        # TTL 分层（不同 capability 不同 TTL）
        self._ttl_map: Dict[ModelCapability, int] = {
            ModelCapability.CHAT: 3600,           # 聊天 1 小时
            ModelCapability.CODE_GENERATION: 86400, # 代码生成 1 天（更稳定）
            ModelCapability.TRANSLATION: 7200,     # 翻译 2 小时
            ModelCapability.SUMMARIZATION: 3600,   # 摘要 1 小时
            ModelCapability.REASONING: 300,        # 推理 5 分钟（易变）
            ModelCapability.WEB_SEARCH: 60,        # 搜索 1 分钟（实时性）
        }
        self._default_ttl: int = 3600
        
        self.default_weights: RoutingWeights = default_weights or RoutingWeights()
        
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
                config={
                    "url": "http://localhost:11434",
                    "model": "qwen2.5",
                    "keep_alive": -1,  # 永久保持加载
                },
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
                config={
                    "url": "http://localhost:11434",
                    "model": "deepseek-coder-v2",
                    "keep_alive": -1,  # 永久保持加载
                },
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
            # 自定义端点 (mogoo.com.cn 测试地址)
            ModelInfo(
                model_id="mogoo_qwen",
                name="Qwen3.5 (mogoo.com.cn)",
                backend=ModelBackend.OPENAI,  # OpenAI兼容格式
                capabilities=[
                    ModelCapability.CHAT,
                    ModelCapability.CONTENT_GENERATION,
                    ModelCapability.SUMMARIZATION,
                    ModelCapability.TRANSLATION,
                    ModelCapability.REASONING,
                    ModelCapability.CODE_GENERATION,
                ],
                max_tokens=8192,
                context_length=32768,
                quality_score=0.85,
                speed_score=0.7,
                cost_score=1.0,  # 免费
                privacy_score=0.3,  # 远程服务
                config={
                    "model": "qwen3.5:9b",
                    "base_url": "http://www.mogoo.com.cn:8899/v1",
                    "api_key": "dummy",  # 可能不需要认证
                    "timeout": 120,  # 增加超时时间（秒）
                },
            ),
            ModelInfo(
                model_id="mogoo_smollm2",
                name="SmollM2 Test (mogoo.com.cn)",
                backend=ModelBackend.OPENAI,  # OpenAI兼容格式
                capabilities=[
                    ModelCapability.CHAT,
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.SUMMARIZATION,
                ],
                max_tokens=4096,
                context_length=8192,
                quality_score=0.6,
                speed_score=0.9,  # 小模型，速度快
                cost_score=1.0,
                privacy_score=0.3,
                config={
                    "model": "smollm2-test:latest",
                    "base_url": "http://www.mogoo.com.cn:8899/v1",
                    "api_key": "dummy",
                },
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
    
    # ============= 三维评分方法 =============

    def _capability_score(self, model: ModelInfo, context_length: int = 0) -> float:
        """
        能力评分（0-1）
        质量(50%) + 成功率(30%) + 上下文余量(20%)
        """
        quality = model.quality_score
        success = model.success_rate
        if context_length > 0 and model.context_length > 0:
            ctx_ratio = model.context_length / context_length
            ctx_score = min(ctx_ratio / 2.0, 1.0)  # 2倍余量得满分
        else:
            ctx_score = 1.0
        return quality * 0.5 + success * 0.3 + ctx_score * 0.2

    def _cost_score(self, model: ModelInfo) -> float:
        """
        成本评分（0-1，越高越便宜）
        直接使用 model.cost_score（1.0=免费, 0.0=极贵）
        """
        return model.cost_score

    def _latency_score(self, model: ModelInfo) -> float:
        """
        延迟评分（0-1，越高越快）
        预设速度(30%) + 历史响应时间(40%) + 当前负载(30%)
        """
        speed = model.speed_score
        rt = model.avg_response_time
        time_score = 1.0 / (1.0 + rt * 0.5)  # rt=0→1.0, rt=2→0.5, rt=10→0.09
        load = model.current_load
        load_score = 1.0 / (1.0 + load * 0.2)  # load=0→1.0, load=5→0.5
        return speed * 0.3 + time_score * 0.4 + load_score * 0.3

    def _combined_score(self, model: ModelInfo, context_length: int,
                       weights: RoutingWeights) -> float:
        """三维综合评分 = cap*Wc + cost*Wcost + latency*Wlat"""
        w = weights.normalize()
        return (self._capability_score(model, context_length) * w.capability
                + self._cost_score(model) * w.cost
                + self._latency_score(model) * w.latency)

    def route(self, capability: ModelCapability,
              strategy: RoutingStrategy = RoutingStrategy.AUTO,
              context_length: int = 0,
              exclude_models: List[str] = None,
              weights: RoutingWeights = None) -> Optional[ModelInfo]:
        """
        路由到最佳模型（三维评估）

        Args:
            capability: 需要的能力
            strategy: 路由策略
            context_length: 需要的上下文长度（0=不限制）
            exclude_models: 排除的模型ID列表
            weights: 自定义三维权重（仅BALANCED策略时使用）

        Returns:
            ModelInfo 最佳模型，如无则返回None
        """
        # 1. 确定策略
        if strategy == RoutingStrategy.AUTO:
            strategy = self.TASK_STRATEGY_MAP.get(capability, RoutingStrategy.BALANCED)

        # 2. 筛选候选模型
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

        # 3. 按策略评分排序
        if strategy == RoutingStrategy.QUALITY:
            candidates.sort(key=lambda m: self._capability_score(m, context_length), reverse=True)

        elif strategy == RoutingStrategy.SPEED:
            candidates.sort(key=lambda m: self._latency_score(m), reverse=True)

        elif strategy == RoutingStrategy.COST:
            candidates.sort(key=lambda m: self._cost_score(m), reverse=True)

        elif strategy == RoutingStrategy.PRIVACY:
            candidates.sort(key=lambda m: m.privacy_score, reverse=True)

        else:  # BALANCED
            w = (weights or self.default_weights)
            candidates.sort(key=lambda m: self._combined_score(m, context_length, w), reverse=True)

        # 4. 返回最佳模型
        selected = candidates[0]
        self._call_count[selected.model_id] = self._call_count.get(selected.model_id, 0) + 1

        logger.info(f"模型路由: {capability.value} → {selected.name} (策略: {strategy.value})")
        return selected
    
    def route_with_fallback(self, capability: ModelCapability,
                           strategy: RoutingStrategy = RoutingStrategy.AUTO,
                           context_length: int = 0,
                           weights: RoutingWeights = None) -> List[ModelInfo]:
        """
        路由到模型列表（含fallback，按优先级排序）

        Args:
            capability: 需要的能力
            strategy: 路由策略
            context_length: 需要的上下文长度
            weights: 自定义三维权重（仅BALANCED策略时使用）

        Returns:
            按优先级排序的模型列表，第一个是最佳模型
        """
        # 1. 确定策略
        if strategy == RoutingStrategy.AUTO:
            strategy = self.TASK_STRATEGY_MAP.get(capability, RoutingStrategy.BALANCED)

        # 2. 筛选候选模型
        candidates = [
            m for m in self.models.values()
            if capability in m.capabilities
            and m.is_available
            and (context_length == 0 or m.can_handle_context(context_length))
        ]

        if not candidates:
            return []

        # 3. 按策略评分排序（与route()保持一致）
        if strategy == RoutingStrategy.QUALITY:
            candidates.sort(key=lambda m: self._capability_score(m, context_length), reverse=True)

        elif strategy == RoutingStrategy.SPEED:
            candidates.sort(key=lambda m: self._latency_score(m), reverse=True)

        elif strategy == RoutingStrategy.COST:
            candidates.sort(key=lambda m: self._cost_score(m), reverse=True)

        elif strategy == RoutingStrategy.PRIVACY:
            candidates.sort(key=lambda m: m.privacy_score, reverse=True)

        else:  # BALANCED
            w = (weights or self.default_weights)
            candidates.sort(key=lambda m: self._combined_score(m, context_length, w), reverse=True)

        return candidates

    def explain_routing(self, capability: ModelCapability,
                        strategy: RoutingStrategy = RoutingStrategy.AUTO,
                        context_length: int = 0,
                        weights: RoutingWeights = None) -> dict:
        """
        解释路由决策（调试用）
        
        返回各候选模型的三维评分详情，方便理解为什么选某个模型。
        
        Returns:
            {
                "strategy": ...,
                "weights": {...},
                "candidates": [
                    {"model_id": ..., "capability": ..., "cost": ..., "latency": ..., "combined": ...},
                    ...
                ],
                "selected": ...
            }
        """
        # 1. 确定策略
        if strategy == RoutingStrategy.AUTO:
            strategy = self.TASK_STRATEGY_MAP.get(capability, RoutingStrategy.BALANCED)
        
        # 2. 筛选候选
        candidates = [
            m for m in self.models.values()
            if capability in m.capabilities
            and m.is_available
            and (context_length == 0 or m.can_handle_context(context_length))
        ]
        
        if not candidates:
            return {"error": f"无可用模型支持 {capability.value}"}
        
        # 3. 计算各维度评分
        w = (weights or self.default_weights).normalize()
        
        details = []
        for m in candidates:
            cap = self._capability_score(m, context_length)
            cost = self._cost_score(m)
            lat = self._latency_score(m)
            combined = cap * w.capability + cost * w.cost + lat * w.latency
            details.append({
                "model_id": m.model_id,
                "name": m.name,
                "capability": round(cap, 3),
                "cost": round(cost, 3),
                "latency": round(lat, 3),
                "combined": round(combined, 3),
                "quality_score": m.quality_score,
                "speed_score": m.speed_score,
                "cost_score": m.cost_score,
                "success_rate": round(m.success_rate, 3),
                "avg_response_time": round(m.avg_response_time, 3),
                "current_load": m.current_load,
            })
        
        # 按综合分排序
        details.sort(key=lambda x: x["combined"], reverse=True)
        
        return {
            "capability": capability.value,
            "strategy": strategy.value,
            "weights": w.to_dict(),
            "candidates": details,
            "selected": details[0]["model_id"] if details else None,
        }

    def _get_cache_key(self, model: ModelInfo, prompt: str, system_prompt: str = "") -> str:
        """生成缓存key"""
        content = f"{model.model_id}:{prompt}:{system_prompt}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _get_ttl_for_capability(self, capability: ModelCapability) -> int:
        """根据 capability 返回 TTL（秒）"""
        return self._ttl_map.get(capability, self._default_ttl)
    
    def _get_from_cache(self, cache_key: str, capability: ModelCapability = None) -> Optional[str]:
        """
        从缓存获取（LRU 行为）
        
        LRU：访问时移到末尾（最新位置）
        TTL：根据 capability 动态判断过期
        """
        if cache_key not in self._cache:
            return None
        
        # 检查 TTL（使用 capability 对应的 TTL）
        timestamp = self._cache_timestamps.get(cache_key, 0)
        ttl = self._default_ttl
        # 注意：capability 需要从外部传入，这里用默认 TTL
        if time.time() - timestamp > ttl:
            # 过期，删除
            del self._cache[cache_key]
            del self._cache_timestamps[cache_key]
            return None
        
        # LRU：访问时移到末尾（最新位置）
        value = self._cache.pop(cache_key)
        self._cache[cache_key] = value
        self._cache_timestamps.pop(cache_key)
        self._cache_timestamps[cache_key] = time.time()
        
        return value
    
    def _save_to_cache(self, cache_key: str, response: str):
        """
        保存到缓存（LRU 行为）
        
        LRU：新增时检查容量，删除最旧的（队首）
        """
        # 如果已存在，先删除（更新位置）
        if cache_key in self._cache:
            del self._cache[cache_key]
            del self._cache_timestamps[cache_key]
        
        # 新增到末尾（最新位置）
        self._cache[cache_key] = response
        self._cache_timestamps[cache_key] = time.time()
        
        # LRU 淘汰：如果超出容量，删除最旧的（队首）
        while len(self._cache) > self._cache_max_size:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            del self._cache_timestamps[oldest_key]
    
    async def call_model(self, capability: ModelCapability,
                        prompt: str,
                        system_prompt: str = "",
                        strategy: RoutingStrategy = RoutingStrategy.AUTO,
                        context_length: int = 0,
                        use_cache: bool = True,
                        model_id: str = "",  # 新增：直接指定模型ID
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
            model_id: 直接指定模型ID（不走路由）
        
        Returns:
            模型输出文本
        """
        # 如果指定了model_id，直接使用该模型
        if model_id:
            if model_id not in self.models:
                logger.error(f"模型不存在: {model_id}")
                return ""
            model = self.models[model_id]
        else:
            # 路由到模型
            model = self.route(capability, strategy, context_length)
            if not model:
                return ""
        
        # 检查缓存（传入 capability 以支持 TTL 分层）
        if use_cache:
            cache_key = self._get_cache_key(model, prompt, system_prompt)
            cached = self._get_from_cache(cache_key, capability)
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
    
    async def call_model_race(self, 
                              capability: ModelCapability,
                              prompt: str,
                              system_prompt: str = "",
                              strategy: RoutingStrategy = RoutingStrategy.AUTO,
                              context_length: int = 0,
                              top_n: int = 3,
                              timeout: float = 60.0,
                              **kwargs) -> str:
        """
        并发 Race 模式：同时调用多个模型，取第一个成功返回的
        
        Args:
            capability: 需要的能力
            prompt: 用户提示
            system_prompt: 系统提示
            strategy: 路由策略
            context_length: 需要的上下文长度
            top_n: 同时调用的模型数量（默认 3 个）
            timeout: 总超时时间（秒）
            **kwargs: 传递给模型调用的参数
        
        Returns:
            第一个成功模型的响应文本
        """
        # 1. 获取候选模型列表
        candidates = self.route_with_fallback(capability, strategy, context_length)
        if not candidates:
            logger.error("Race 模式：无可用模型")
            return ""
        
        # 2. 取前 top_n 个模型
        selected = candidates[:top_n]
        logger.info(f"Race 模式：同时调用 {len(selected)} 个模型")
        
        # 3. 为每个模型创建调用任务
        async def _race_call(model: ModelInfo) -> Tuple[ModelInfo, Optional[str], bool]:
            """单个模型的调用任务"""
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
            
            except Exception as e:
                logger.error(f"Race 调用异常 {model.name}: {e}")
            
            finally:
                model.current_load -= 1
                response_time = time.time() - start_time
                model.update_stats(success, response_time)
            
            return model, response, success
        
        # 4. 创建所有任务
        tasks = []
        for model in selected:
            task = asyncio.create_task(_race_call(model))
            tasks.append(task)
        
        # 5. 等待第一个成功返回
        try:
            done = set()
            pending = set(tasks)
            
            while pending:
                # 等待任意一个任务完成
                done_part, pending = await asyncio.wait(
                    pending, 
                    timeout=timeout / len(tasks),  # 每个任务分配相同时间
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # 检查完成的任务
                for task in done_part:
                    model, response, success = task.result()
                    
                    if success:
                        # 成功！取消其他任务
                        for t in pending:
                            t.cancel()
                        logger.info(f"Race 获胜者: {model.name}")
                        
                        # 保存到缓存
                        cache_key = self._get_cache_key(model, prompt, system_prompt)
                        self._save_to_cache(cache_key, response)
                        
                        return response
                
                # 如果所有任务都失败了
                done.update(done_part)
                if len(done) == len(tasks):
                    logger.error("Race 模式：所有模型都失败")
                    return ""
        
        except asyncio.TimeoutError:
            logger.error(f"Race 模式：超时（{timeout}秒）")
            for task in tasks:
                task.cancel()
            return ""
        
        except Exception as e:
            logger.error(f"Race 模式异常: {e}")
            for task in tasks:
                task.cancel()
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
                           system_prompt: str = "",
                           keep_alive: Optional[int] = None) -> str:
        """调用 Ollama 模型（同步）
        
        Args:
            keep_alive: 模型保持加载时间（秒）
                -1=永久, 0=立即卸载, 60=60秒
                默认从 model.config["keep_alive"] 读取，内置模型默认 -1
        """
        try:
            import aiohttp
            url = model.config.get("url", "http://localhost:11434")
            model_name = model.config.get("model", "qwen2.5")
            
            # keep_alive 参数（默认 -1 = 永久保持）
            if keep_alive is None:
                keep_alive = model.config.get("keep_alive", -1)
            
            payload = {
                "model": model_name,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False,
                "keep_alive": keep_alive,
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
                                  system_prompt: str = "",
                                  keep_alive: Optional[int] = None) -> AsyncIterator[str]:
        """调用 Ollama 模型（流式）
        
        Args:
            keep_alive: 模型保持加载时间（秒）
                -1=永久, 0=立即卸载, 60=60秒
                默认从 model.config["keep_alive"] 读取，内置模型默认 -1
        """
        try:
            import aiohttp
            url = model.config.get("url", "http://localhost:11434")
            model_name = model.config.get("model", "qwen2.5")
            
            # keep_alive 参数（默认 -1 = 永久保持）
            if keep_alive is None:
                keep_alive = model.config.get("keep_alive", -1)
            
            payload = {
                "model": model_name,
                "prompt": prompt,
                "system": system_prompt,
                "stream": True,
                "keep_alive": keep_alive,
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
        """调用 OpenAI API 或 OpenAI 兼容端点"""
        try:
            import openai
            
            model_name = model.config.get("model", "gpt-3.5-turbo")
            base_url = model.config.get("base_url")  # 支持自定义端点
            api_key = model.config.get("api_key", "dummy")  # 支持自定义key
            timeout = model.config.get("timeout", 60)  # 支持自定义超时（秒）
            
            # 创建客户端（支持自定义base_url和超时）
            client = openai.AsyncOpenAI(
                base_url=base_url if base_url else None,
                api_key=api_key,
                timeout=timeout,  # 设置超时
            )
            
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
        """调用 OpenAI API 或兼容端点（流式）"""
        try:
            import openai
            model_name = model.config.get("model", "gpt-3.5-turbo")
            base_url = model.config.get("base_url")
            api_key = model.config.get("api_key", "dummy")
            timeout = model.config.get("timeout", 60)  # 支持自定义超时
            
            client = openai.AsyncOpenAI(
                base_url=base_url if base_url else None,
                api_key=api_key,
                timeout=timeout,  # 设置超时
            )
            
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
            yield ""  # 流式函数需要yield
    
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
    
    # ============= 模型预热 =============
    
    async def warm_up(self, model_id: str = "") -> bool:
        """
        预热模型（加载到 GPU/内存）
        
        Args:
            model_id: 模型ID，空字符串=预热所有 Ollama 模型
        
        Returns:
            是否成功
        """
        if model_id:
            # 预热单个模型
            if model_id not in self.models:
                logger.error(f"模型不存在: {model_id}")
                return False
            
            model = self.models[model_id]
            if model.backend != ModelBackend.OLLAMA:
                logger.warning(f"模型 {model_id} 不是 Ollama 后端，无需预热")
                return True
            
            try:
                # 发送一个简单请求来预热（keep_alive=-1 永久保持）
                response = await self._call_ollama(
                    model, 
                    prompt="hi", 
                    system_prompt="",
                    keep_alive=-1
                )
                logger.info(f"模型预热成功: {model.name}")
                return bool(response)
            
            except Exception as e:
                logger.error(f"模型预热失败 {model.name}: {e}")
                return False
        
        else:
            # 预热所有 Ollama 模型
            results = []
            for model in self.models.values():
                if model.backend == ModelBackend.OLLAMA:
                    success = await self.warm_up(model.model_id)
                    results.append(success)
            
            return all(results) if results else False
    
    def start_keepalive(self, interval: int = 300):
        """
        启动后台心跳任务（防止模型被卸载）
        
        Args:
            interval: 心跳间隔（秒），默认 300 秒（5 分钟）
        """
        import threading
        
        def _keepalive_loop():
            """心跳循环"""
            import asyncio
            
            # 创建新的事件循环（因为在新线程中）
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            while True:
                try:
                    # 发送心跳请求（空 prompt，keep_alive=-1）
                    for model in self.models.values():
                        if model.backend == ModelBackend.OLLAMA:
                            try:
                                loop.run_until_complete(
                                    self._call_ollama(
                                        model,
                                        prompt="",
                                        system_prompt="",
                                        keep_alive=-1
                                    )
                                )
                            except Exception as e:
                                logger.warning(f"心跳失败 {model.name}: {e}")
                    
                    # 等待 interval 秒
                    time.sleep(interval)
                
                except Exception as e:
                    logger.error(f"心跳循环异常: {e}")
                    time.sleep(60)  # 异常后等待 1 分钟再试
        
        # 启动后台线程
        thread = threading.Thread(target=_keepalive_loop, daemon=True)
        thread.start()
        logger.info(f"心跳任务已启动（间隔 {interval} 秒）")
        return thread
    
    def stop_keepalive(self):
        """停止心跳任务（通过设置标志位）"""
        # 注意：当前实现使用 daemon=True 线程，程序退出时自动停止
        # 如果需要手动停止，需要添加标志位
        logger.info("心跳任务将在程序退出时自动停止")


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
                    use_cache: bool = True,
                    model_id: str = "") -> str:
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
        model_id: 直接指定模型ID（不走路由）
    
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
                router.call_model(capability, prompt, system_prompt, strategy, context_length, use_cache, model_id),
                loop
            ).result(timeout=120)
        else:
            # 没有运行中的循环，使用 asyncio.run()
            return asyncio.run(
                router.call_model(capability, prompt, system_prompt, strategy, context_length, use_cache, model_id)
            )
    except RuntimeError:
        # 没有事件循环，创建新的
        return asyncio.run(
            router.call_model(capability, prompt, system_prompt, strategy, context_length, use_cache, model_id)
        )


# ============= Handler 体系 =============

class BaseHandler(ABC):
    """处理器基类（Strategy模式）"""
    
    @abstractmethod
    async def handle(self, prompt: str, system_prompt: str = "", **kwargs) -> str:
        """处理请求"""
        pass
    
    @abstractmethod
    def get_capability(self) -> ModelCapability:
        """返回此处理器处理的能力"""
        pass
    
    def preprocess(self, prompt: str) -> str:
        """预处理（可选覆盖）"""
        return prompt
    
    def postprocess(self, response: str) -> str:
        """后处理（可选覆盖）"""
        return response


class ChatHandler(BaseHandler):
    """通用聊天处理器"""
    
    async def handle(self, prompt: str, system_prompt: str = "", **kwargs) -> str:
        router = get_global_router()
        return await router.call_model(
            capability=ModelCapability.CHAT,
            prompt=prompt,
            system_prompt=system_prompt or "你是一个有用的AI助手。"
        )
    
    def get_capability(self) -> ModelCapability:
        return ModelCapability.CHAT


class CodeGenerationHandler(BaseHandler):
    """代码生成处理器"""
    
    async def handle(self, prompt: str, system_prompt: str = "", **kwargs) -> str:
        # 增强：自动添加代码生成提示
        enhanced_prompt = f"请生成代码，只输出代码本身（不含解释）：\n{prompt}"
        
        router = get_global_router()
        return await router.call_model(
            capability=ModelCapability.CODE_GENERATION,
            prompt=enhanced_prompt,
            system_prompt=system_prompt or "你是一个代码生成助手。只输出代码，不要解释。"
        )
    
    def get_capability(self) -> ModelCapability:
        return ModelCapability.CODE_GENERATION


class ReasoningHandler(BaseHandler):
    """推理处理器（复杂问题）"""
    
    async def handle(self, prompt: str, system_prompt: str = "", **kwargs) -> str:
        # 增强：要求分步推理
        enhanced_prompt = f"请分步思考并给出答案：\n{prompt}"
        
        router = get_global_router()
        return await router.call_model(
            capability=ModelCapability.REASONING,
            prompt=enhanced_prompt,
            system_prompt=system_prompt or "你是一个推理助手。请分步思考，给出详细推理过程。"
        )
    
    def get_capability(self) -> ModelCapability:
        return ModelCapability.REASONING


class TranslationHandler(BaseHandler):
    """翻译处理器"""
    
    def __init__(self, source_lang: str = "auto", target_lang: str = "zh"):
        self.source_lang = source_lang
        self.target_lang = target_lang
    
    async def handle(self, prompt: str, system_prompt: str = "", **kwargs) -> str:
        # 构建翻译提示
        if self.source_lang == "auto":
            translate_prompt = f"翻译成{self.target_lang}：\n{prompt}"
        else:
            translate_prompt = f"从{self.source_lang}翻译成{self.target_lang}：\n{prompt}"
        
        router = get_global_router()
        return await router.call_model(
            capability=ModelCapability.TRANSLATION,
            prompt=translate_prompt,
            system_prompt=system_prompt or f"你是一个翻译助手。只输出翻译结果，不要解释。"
        )
    
    def get_capability(self) -> ModelCapability:
        return ModelCapability.TRANSLATION


class SummarizationHandler(BaseHandler):
    """摘要处理器"""
    
    def __init__(self, max_length: int = 100):
        self.max_length = max_length
    
    async def handle(self, prompt: str, system_prompt: str = "", **kwargs) -> str:
        # 构建摘要提示
        summary_prompt = f"请总结以下内容（不超过{self.max_length}字）：\n\n{prompt}"
        
        router = get_global_router()
        return await router.call_model(
            capability=ModelCapability.SUMMARIZATION,
            prompt=summary_prompt,
            system_prompt=system_prompt or f"你是一个文本摘要助手。总结要简洁准确，不超过{self.max_length}字。"
        )
    
    def get_capability(self) -> ModelCapability:
        return ModelCapability.SUMMARIZATION


class CodeReviewHandler(BaseHandler):
    """代码审查处理器"""
    
    async def handle(self, prompt: str, system_prompt: str = "", **kwargs) -> str:
        # 构建代码审查提示
        review_prompt = f"请审查以下代码，指出问题并给出改进建议：\n\n```\n{prompt}\n```"
        
        router = get_global_router()
        return await router.call_model(
            capability=ModelCapability.CODE_REVIEW,
            prompt=review_prompt,
            system_prompt=system_prompt or "你是一个代码审查专家。关注：bug、性能、安全性、可读性、最佳实践。"
        )
    
    def get_capability(self) -> ModelCapability:
        return ModelCapability.CODE_REVIEW


class DocumentGenerationHandler(BaseHandler):
    """文档生成处理器"""
    
    def __init__(self, doc_type: str = "report"):
        self.doc_type = doc_type  # report, manual, spec, etc.
    
    async def handle(self, prompt: str, system_prompt: str = "", **kwargs) -> str:
        # 构建文档生成提示
        doc_prompt = f"请生成{self.doc_type}文档：\n{prompt}"
        
        router = get_global_router()
        return await router.call_model(
            capability=ModelCapability.DOCUMENT_PLANNING,
            prompt=doc_prompt,
            system_prompt=system_prompt or f"你是一个{self.doc_type}文档生成助手。生成结构清晰、内容完整的文档。"
        )
    
    def get_capability(self) -> ModelCapability:
        return ModelCapability.DOCUMENT_PLANNING


class DataAnalysisHandler(BaseHandler):
    """数据分析处理器"""
    
    async def handle(self, prompt: str, system_prompt: str = "", **kwargs) -> str:
        # 构建数据分析提示
        analysis_prompt = f"请分析以下数据或问题：\n{prompt}"
        
        router = get_global_router()
        return await router.call_model(
            capability=ModelCapability.DATA_ANALYSIS,
            prompt=analysis_prompt,
            system_prompt=system_prompt or "你是一个数据分析助手。提供清晰的分析和可行的建议。"
        )
    
    def get_capability(self) -> ModelCapability:
        return ModelCapability.DATA_ANALYSIS


class CreativeWritingHandler(BaseHandler):
    """创意写作处理器"""
    
    def __init__(self, style: str = "general"):
        self.style = style  # general, poetry, story, marketing, etc.
    
    async def handle(self, prompt: str, system_prompt: str = "", **kwargs) -> str:
        write_prompt = f"请进行创意写作（风格：{self.style}）：\n{prompt}"
        
        router = get_global_router()
        return await router.call_model(
            capability=ModelCapability.CONTENT_GENERATION,
            prompt=write_prompt,
            system_prompt=system_prompt or f"你是一个创意写作助手。风格：{self.style}。"
        )
    
    def get_capability(self) -> ModelCapability:
        return ModelCapability.CONTENT_GENERATION


class QuestionAnsweringHandler(BaseHandler):
    """问答处理器（基于上下文）"""
    
    def __init__(self, context: str = ""):
        self.context = context
    
    async def handle(self, prompt: str, system_prompt: str = "", **kwargs) -> str:
        if self.context:
            qa_prompt = f"基于以下上下文回答问题：\n\n上下文：{self.context}\n\n问题：{prompt}"
        else:
            qa_prompt = prompt
        
        router = get_global_router()
        return await router.call_model(
            capability=ModelCapability.KNOWLEDGE_QUERY,
            prompt=qa_prompt,
            system_prompt=system_prompt or "你是一个问答助手。基于上下文回答，不知道就说不知道。"
        )
    
    def get_capability(self) -> ModelCapability:
        return ModelCapability.KNOWLEDGE_QUERY


# ============= Handler 工厂 =============

class HandlerFactory:
    """处理器工厂（Factory模式）"""
    
    _handlers = {
        ModelCapability.CHAT: ChatHandler,
        ModelCapability.CODE_GENERATION: CodeGenerationHandler,
        ModelCapability.REASONING: ReasoningHandler,
        ModelCapability.TRANSLATION: TranslationHandler,
        ModelCapability.SUMMARIZATION: SummarizationHandler,
        ModelCapability.CODE_REVIEW: CodeReviewHandler,
        ModelCapability.DOCUMENT_PLANNING: DocumentGenerationHandler,
        ModelCapability.DATA_ANALYSIS: DataAnalysisHandler,
        ModelCapability.CONTENT_GENERATION: CreativeWritingHandler,
        ModelCapability.KNOWLEDGE_QUERY: QuestionAnsweringHandler,
    }
    
    @classmethod
    def create_handler(cls, capability: ModelCapability, **kwargs) -> BaseHandler:
        """
        创建处理器
        
        Args:
            capability: 能力
            **kwargs: 传递给处理器构造函数的参数
        
        Returns:
            BaseHandler 处理器实例
        """
        handler_class = cls._handlers.get(capability)
        if not handler_class:
            # 默认使用ChatHandler
            logger.warning(f"未知能力 {capability}，使用ChatHandler")
            return ChatHandler()
        
        return handler_class(**kwargs)
    
    @classmethod
    def register_handler(cls, capability: ModelCapability, handler_class: type):
        """注册自定义处理器"""
        if not issubclass(handler_class, BaseHandler):
            raise ValueError(f"{handler_class} 必须继承 BaseHandler")
        
        cls._handlers[capability] = handler_class
        logger.info(f"注册处理器：{capability.value} → {handler_class.__name__}")


# ============= 便捷函数 =============

async def handle_with_handler(capability: ModelCapability, 
                             prompt: str, 
                             system_prompt: str = "",
                             **kwargs) -> str:
    """
    使用Handler处理请求（便捷函数）
    
    Args:
        capability: 能力
        prompt: 提示
        system_prompt: 系统提示
        **kwargs: 传递给处理器的参数
    
    Returns:
        str: 处理结果
    """
    handler = HandlerFactory.create_handler(capability, **kwargs)
    return await handler.handle(prompt, system_prompt)


# ============= 同步便捷函数 =============

def translate(text: str, source_lang: str = "auto", target_lang: str = "zh") -> str:
    """翻译（同步）"""
    import asyncio
    handler = TranslationHandler(source_lang=source_lang, target_lang=target_lang)
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.run_coroutine_threadsafe(
                handler.handle(text), loop
            ).result(timeout=60)
        else:
            return asyncio.run(handler.handle(text))
    except RuntimeError:
        return asyncio.run(handler.handle(text))


def summarize(text: str, max_length: int = 100) -> str:
    """摘要（同步）"""
    import asyncio
    handler = SummarizationHandler(max_length=max_length)
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.run_coroutine_threadsafe(
                handler.handle(text), loop
            ).result(timeout=60)
        else:
            return asyncio.run(handler.handle(text))
    except RuntimeError:
        return asyncio.run(handler.handle(text))


def review_code(code: str) -> str:
    """代码审查（同步）"""
    import asyncio
    handler = CodeReviewHandler()
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.run_coroutine_threadsafe(
                handler.handle(code), loop
            ).result(timeout=60)
        else:
            return asyncio.run(handler.handle(code))
    except RuntimeError:
        return asyncio.run(handler.handle(code))


def analyze_data(question: str) -> str:
    """数据分析（同步）"""
    import asyncio
    handler = DataAnalysisHandler()
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.run_coroutine_threadsafe(
                handler.handle(question), loop
            ).result(timeout=60)
        else:
            return asyncio.run(handler.handle(question))
    except RuntimeError:
        return asyncio.run(handler.handle(question))
