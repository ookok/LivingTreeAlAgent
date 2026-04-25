"""
SmartAI Router - 智能AI路由系统
=================================

三层算力池：
1. Local - 本地小模型 (Qwen2-1.5B/Phi-3-mini) 免费但慢
2. Edge - 边缘/私有服务器中模型 (Qwen2-7B/14B via Ollama) 低成本
3. Cloud - 云端大模型 (OpenAI/Azure) 准且贵

核心理念：
- 放弃"纯本地"，拥抱"智能分流"
- 轻量任务走本地，中量任务走边缘，重量任务走云端
- 缓存优先，避免重复调用
- 成本控制，超支自动降级

Author: Hermes Desktop AI Assistant
"""

import json
import hashlib
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class ComputeTier(Enum):
    """算力层级"""
    LOCAL = "local"           # 本地小模型
    EDGE = "edge"            # 边缘/私有服务器
    CLOUD = "cloud"          # 云端付费API
    OFFLINE = "offline"      # 离线降级模式


class TaskType(Enum):
    """任务类型"""
    # 轻量任务 - 本地
    TEXT_CLEAN = "text_clean"           # 文本清洗
    KEYWORD_EXTRACT = "keyword_extract"  # 关键词提取
    SIMPLE_CLASSIFY = "simple_classify"  # 简单分类
    QUICK_SUMMARY = "quick_summary"     # 快速摘要

    # 中量任务 - 边缘
    NORMAL_CHAT = "normal_chat"         # 普通对话
    TEXT_SUMMARY = "text_summary"        # 文本摘要
    TRANSLATION = "translation"          # 翻译
    CODE_COMPLETION = "code_completion"   # 代码补全

    # 重量任务 - 云端
    CODE_GENERATE = "code_generate"       # 代码生成
    DEEP_REASONING = "deep_reasoning"    # 深度推理
    HIGH_QUALITY_WRITE = "high_quality_write"  # 高质量写作
    COMPLEX_ANALYSIS = "complex_analysis"  # 复杂分析

    # 特殊任务
    UNKNOWN = "unknown"                  # 未知类型


@dataclass
class AIResponse:
    """AI响应"""
    content: str
    tier_used: ComputeTier
    model_used: str
    tokens_used: int = 0
    cost: float = 0.0
    cached: bool = False
    latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class CostBudget:
    """成本预算"""
    monthly_limit: float = 50.0      # 月度限额
    daily_limit: float = 5.0        # 日限额
    per_request_limit: float = 0.5  # 单次请求限额

    current_month_spent: float = 0.0
    current_day_spent: float = 0.0
    last_reset: datetime = field(default_factory=datetime.now)

    def can_afford(self, cost: float) -> bool:
        """检查是否可以承担成本"""
        if cost > self.per_request_limit:
            return False
        if self.current_day_spent + cost > self.daily_limit:
            return False
        if self.current_month_spent + cost > self.monthly_limit:
            return False
        return True

    def record_spend(self, cost: float):
        """记录支出"""
        self.current_day_spent += cost
        self.current_month_spent += cost

    def reset_if_needed(self):
        """必要时重置"""
        now = datetime.now()
        if now.date() > self.last_reset.date():
            self.current_day_spent = 0.0
            self.last_reset = now
        if now.month != self.last_reset.month:
            self.current_month_spent = 0.0
            self.last_reset = now


@dataclass
class TierEndpoint:
    """算力端点配置"""
    name: str
    tier: ComputeTier
    endpoint: str                          # API地址或模型名
    api_key: Optional[str] = None           # API密钥
    max_tokens: int = 4096                 # 最大令牌数
    cost_per_1k_input: float = 0.0         # 输入成本 ($/1K tokens)
    cost_per_1k_output: float = 0.0         # 输出成本
    is_available: bool = True               # 是否可用
    latency_ms: float = 1000.0             # 预估延迟
    success_rate: float = 1.0              # 成功率


class SmartCache:
    """智能缓存"""

    def __init__(self, cache_dir: str = "~/.hermes/ai_cache"):
        self.cache_dir = Path(cache_dir).expanduser()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.memory_cache: Dict[str, AIResponse] = {}
        self.hit_count = 0
        self.miss_count = 0

    def _make_key(self, task_type: str, prompt: str, context: Dict) -> str:
        """生成缓存键"""
        data = json.dumps({
            "task": task_type,
            "prompt": prompt[:500],  # 限制长度
            "context": {k: v for k, v in context.items() if k in ["lang", "max_length"]}
        }, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()

    def get(self, task_type: str, prompt: str, context: Dict) -> Optional[AIResponse]:
        """获取缓存"""
        key = self._make_key(task_type, prompt, context)

        # 先查内存缓存
        if key in self.memory_cache:
            self.hit_count += 1
            cached = self.memory_cache[key]
            cached.cached = True
            return cached

        # 查磁盘缓存
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    cached = AIResponse(
                        content=data['content'],
                        tier_used=ComputeTier(data['tier_used']),
                        model_used=data['model_used'],
                        tokens_used=data.get('tokens_used', 0),
                        cost=data.get('cost', 0.0),
                        cached=True,
                        latency_ms=0.0,
                        timestamp=datetime.fromisoformat(data.get('timestamp', datetime.now().isoformat()))
                    )
                self.hit_count += 1
                return cached
            except Exception as e:
                logger.warning(f"Cache read failed: {e}")

        self.miss_count += 1
        return None

    def set(self, task_type: str, prompt: str, context: Dict, response: AIResponse):
        """设置缓存"""
        key = self._make_key(task_type, prompt, context)

        # 存内存缓存
        self.memory_cache[key] = response

        # 存磁盘缓存 (只缓存非云端结果)
        if response.tier_used != ComputeTier.CLOUD:
            try:
                cache_file = self.cache_dir / f"{key}.json"
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        'content': response.content,
                        'tier_used': response.tier_used.value,
                        'model_used': response.model_used,
                        'tokens_used': response.tokens_used,
                        'cost': response.cost,
                        'timestamp': response.timestamp.isoformat()
                    }, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.warning(f"Cache write failed: {e}")

    def get_hit_rate(self) -> float:
        """获取缓存命中率"""
        total = self.hit_count + self.miss_count
        return self.hit_count / total if total > 0 else 0.0

    def clear_expired(self, max_age_days: int = 7):
        """清理过期缓存"""
        cutoff = datetime.now() - timedelta(days=max_age_days)
        removed = 0

        for cache_file in self.cache_dir.glob("*.json"):
            try:
                mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
                if mtime < cutoff:
                    cache_file.unlink()
                    removed += 1
            except Exception:
                pass

        # 清理内存缓存
        expired_keys = [k for k, v in self.memory_cache.items()
                       if v.timestamp < cutoff]
        for k in expired_keys:
            del self.memory_cache[k]

        logger.info(f"Cleared {removed} expired cache entries")
        return removed


class SmartAI Router:
    """
    智能AI路由器

    根据任务类型、成本预算、系统负载自动选择最佳算力层
    """

    # 任务类型 -> 推荐算力层
    TASK_TIER_MAP = {
        # 轻量任务 - 本地
        TaskType.TEXT_CLEAN: ComputeTier.LOCAL,
        TaskType.KEYWORD_EXTRACT: ComputeTier.LOCAL,
        TaskType.SIMPLE_CLASSIFY: ComputeTier.LOCAL,
        TaskType.QUICK_SUMMARY: ComputeTier.LOCAL,

        # 中量任务 - 边缘
        TaskType.NORMAL_CHAT: ComputeTier.EDGE,
        TaskType.TEXT_SUMMARY: ComputeTier.EDGE,
        TaskType.TRANSLATION: ComputeTier.EDGE,
        TaskType.CODE_COMPLETION: ComputeTier.EDGE,

        # 重量任务 - 云端
        TaskType.CODE_GENERATE: ComputeTier.CLOUD,
        TaskType.DEEP_REASONING: ComputeTier.CLOUD,
        TaskType.HIGH_QUALITY_WRITE: ComputeTier.CLOUD,
        TaskType.COMPLEX_ANALYSIS: ComputeTier.CLOUD,
    }

    # 层级描述
    TIER_NAMES = {
        ComputeTier.LOCAL: "本地小模型",
        ComputeTier.EDGE: "边缘服务器",
        ComputeTier.CLOUD: "云端大模型",
        ComputeTier.OFFLINE: "离线降级"
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.cache = SmartCache()

        # 成本预算
        self.budget = CostBudget(
            monthly_limit=self.config.get("monthly_limit", 50.0),
            daily_limit=self.config.get("daily_limit", 5.0),
            per_request_limit=self.config.get("per_request_limit", 0.5)
        )

        # 端点配置
        self.endpoints: Dict[ComputeTier, List[TierEndpoint]] = {
            ComputeTier.LOCAL: [],
            ComputeTier.EDGE: [],
            ComputeTier.CLOUD: [],
        }

        # 本地模型配置
        self._setup_local_endpoints()

        # 边缘服务器配置
        self._setup_edge_endpoints()

        # 云端API配置
        self._setup_cloud_endpoints()

        # 统计
        self.stats = defaultdict(int)  # 各层级调用次数
        self.total_cost = 0.0

        # 降级回调
        self.fallback_handler: Optional[Callable] = None

        logger.info("SmartAI Router initialized")

    def _setup_local_endpoints(self):
        """配置本地端点"""
        # 检查可用的本地模型
        local_models = self.config.get("local_models", [
            "qwen2:1.5b",
            "phi3:mini",
            "tinyllama"
        ])

        for model in local_models:
            self.endpoints[ComputeTier.LOCAL].append(TierEndpoint(
                name=f"local_{model}",
                tier=ComputeTier.LOCAL,
                endpoint=model,
                max_tokens=2048,
                cost_per_1k_input=0.0,
                cost_per_1k_output=0.0,
                latency_ms=5000,  # 本地较慢
                success_rate=0.95
            ))

    def _setup_edge_endpoints(self):
        """配置边缘端点"""
        edge_configs = self.config.get("edge_servers", [
            {"name": "ollama_local", "endpoint": "http://localhost:11434", "model": "qwen2:7b"}
        ])

        for cfg in edge_configs:
            self.endpoints[ComputeTier.EDGE].append(TierEndpoint(
                name=cfg.get("name", "edge"),
                tier=ComputeTier.EDGE,
                endpoint=cfg.get("endpoint", "http://localhost:11434"),
                api_key=cfg.get("api_key"),
                max_tokens=4096,
                cost_per_1k_input=0.0,
                cost_per_1k_output=0.0,
                latency_ms=1000,
                success_rate=0.98
            ))

    def _setup_cloud_endpoints(self):
        """配置云端端点"""
        cloud_configs = self.config.get("cloud_apis", [
            {
                "name": "openai",
                "endpoint": "https://api.openai.com/v1/chat/completions",
                "model": "gpt-4o-mini",
                "cost_input": 0.00015,
                "cost_output": 0.0006
            },
            {
                "name": "azure",
                "endpoint": "https://your-resource.openai.azure.com",
                "model": "gpt-4o-mini",
                "cost_input": 0.00012,
                "cost_output": 0.00048
            }
        ])

        for cfg in cloud_configs:
            self.endpoints[ComputeTier.CLOUD].append(TierEndpoint(
                name=cfg.get("name", "cloud"),
                tier=ComputeTier.CLOUD,
                endpoint=cfg.get("endpoint"),
                api_key=cfg.get("api_key"),
                max_tokens=4096,
                cost_per_1k_input=cfg.get("cost_input", 0.001),
                cost_per_1k_output=cfg.get("cost_output", 0.002),
                latency_ms=500,
                success_rate=0.99
            ))

    def register_edge_server(self, name: str, endpoint: str, model: str = "qwen2:7b",
                            api_key: Optional[str] = None):
        """注册边缘服务器"""
        self.endpoints[ComputeTier.EDGE].append(TierEndpoint(
            name=name,
            tier=ComputeTier.EDGE,
            endpoint=endpoint,
            api_key=api_key,
            max_tokens=4096,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
            latency_ms=800,
            success_rate=0.98
        ))
        logger.info(f"Registered edge server: {name} at {endpoint}")

    def register_cloud_api(self, name: str, endpoint: str, api_key: str,
                          model: str, cost_input: float, cost_output: float):
        """注册云端API"""
        self.endpoints[ComputeTier.CLOUD].append(TierEndpoint(
            name=name,
            tier=ComputeTier.CLOUD,
            endpoint=endpoint,
            api_key=api_key,
            max_tokens=4096,
            cost_per_1k_input=cost_input,
            cost_per_1k_output=cost_output,
            latency_ms=500,
            success_rate=0.99
        ))
        logger.info(f"Registered cloud API: {name}")

    def classify_task(self, prompt: str, context: Dict[str, Any]) -> TaskType:
        """识别任务类型"""
        prompt_lower = prompt.lower()

        # 轻量任务关键词
        light_keywords = ["清洗", "clean", "提取关键词", "extract keyword",
                        "简单分类", "simple classify", "快速摘要", "quick summary"]
        for kw in light_keywords:
            if kw in prompt_lower:
                return TaskType.QUICK_SUMMARY

        # 中量任务关键词
        medium_keywords = ["总结", "summarize", "翻译", "translate",
                         "补全", "complete", "对话", "chat"]
        for kw in medium_keywords:
            if kw in prompt_lower:
                return TaskType.NORMAL_CHAT

        # 重量任务关键词
        heavy_keywords = ["生成代码", "generate code", "深度推理", "deep reasoning",
                         "高质量写作", "high quality writing", "复杂分析"]
        for kw in heavy_keywords:
            if kw in prompt_lower:
                return TaskType.CODE_GENERATE

        # 基于上下文推断
        if context.get("is_coding"):
            return TaskType.CODE_GENERATE
        if context.get("is_analysis"):
            return TaskType.COMPLEX_ANALYSIS

        return TaskType.NORMAL_CHAT

    def route_request(self, prompt: str, context: Optional[Dict[str, Any]] = None,
                     force_tier: Optional[ComputeTier] = None) -> ComputeTier:
        """
        路由请求到最佳算力层

        Returns:
            ComputeTier: 最佳算力层
        """
        context = context or {}
        task_type = context.get("task_type") or self.classify_task(prompt, context)

        # 1. 检查缓存
        cached = self.cache.get(task_type.value, prompt, context)
        if cached:
            logger.info(f"Cache hit for {task_type.value}")
            return cached.tier_used

        # 2. 确定目标层级
        if force_tier:
            target_tier = force_tier
        else:
            target_tier = self.TASK_TIER_MAP.get(task_type, ComputeTier.EDGE)

        # 3. 成本检查 - 如果目标层级太贵，降级
        self.budget.reset_if_needed()

        if target_tier == ComputeTier.CLOUD:
            # 估算云端成本
            estimated_cost = self._estimate_cloud_cost(prompt)
            if not self.budget.can_afford(estimated_cost):
                logger.warning(f"Budget exceeded, degrading from cloud to edge")
                target_tier = ComputeTier.EDGE

        # 4. 可用性检查
        if not self._is_tier_available(target_tier):
            target_tier = self._find_available_alternative(target_tier)

        # 5. 如果所有层级都不可用，返回离线模式
        if not self._is_tier_available(target_tier):
            target_tier = ComputeTier.OFFLINE

        return target_tier

    def _estimate_cloud_cost(self, prompt: str) -> float:
        """估算云端成本"""
        # 简单估算：假设prompt约500 tokens，输出约200 tokens
        input_tokens = len(prompt) // 4
        output_tokens = 200
        cost_per_1k = 0.001  # 假设平均成本
        return (input_tokens + output_tokens) / 1000 * cost_per_1k

    def _is_tier_available(self, tier: ComputeTier) -> bool:
        """检查层级是否可用"""
        if tier == ComputeTier.OFFLINE:
            return True
        return any(ep.is_available for ep in self.endpoints.get(tier, []))

    def _find_available_alternative(self, original_tier: ComputeTier) -> ComputeTier:
        """找到可用的替代层级"""
        # 降级顺序：Cloud -> Edge -> Local -> Offline
        downgrade_order = [ComputeTier.CLOUD, ComputeTier.EDGE,
                          ComputeTier.LOCAL, ComputeTier.OFFLINE]

        try:
            start_idx = downgrade_order.index(original_tier)
        except ValueError:
            start_idx = 0

        for tier in downgrade_order[start_idx:]:
            if self._is_tier_available(tier):
                return tier

        return ComputeTier.OFFLINE

    def get_best_endpoint(self, tier: ComputeTier) -> Optional[TierEndpoint]:
        """获取最佳端点"""
        endpoints = self.endpoints.get(tier, [])
        if not endpoints:
            return None

        # 按可用性、延迟、成功率排序
        available = [ep for ep in endpoints if ep.is_available]
        if not available:
            return None

        # 选择最佳端点（最低延迟 * 最高成功率）
        best = min(available,
                  key=lambda ep: ep.latency_ms / (ep.success_rate + 0.01))
        return best

    async def execute_request(self, prompt: str,
                              context: Optional[Dict[str, Any]] = None,
                              callback: Optional[Callable] = None) -> AIResponse:
        """
        执行AI请求

        Args:
            prompt: 输入提示
            context: 上下文信息
            callback: 进度回调

        Returns:
            AIResponse: AI响应
        """
        context = context or {}
        start_time = time.time()

        # 1. 路由
        tier = self.route_request(prompt, context)
        endpoint = self.get_best_endpoint(tier)

        logger.info(f"Routing to {self.TIER_NAMES.get(tier, tier.value)}, "
                   f"endpoint: {endpoint.name if endpoint else 'None'}")

        # 2. 缓存检查
        task_type = context.get("task_type") or self.classify_task(prompt, context)
        cached = self.cache.get(task_type.value, prompt, context)
        if cached:
            return cached

        # 3. 执行请求
        response = AIResponse(
            content="",
            tier_used=tier,
            model_used=endpoint.name if endpoint else "unknown",
            latency_ms=0.0
        )

        try:
            if tier == ComputeTier.LOCAL:
                response = await self._execute_local(prompt, endpoint, context)
            elif tier == ComputeTier.EDGE:
                response = await self._execute_edge(prompt, endpoint, context)
            elif tier == ComputeTier.CLOUD:
                response = await self._execute_cloud(prompt, endpoint, context)
            else:  # OFFLINE
                response = await self._execute_offline(prompt, context)

        except Exception as e:
            logger.error(f"Request failed: {e}")
            # 降级重试
            alt_tier = self._find_available_alternative(tier)
            if alt_tier != tier:
                logger.info(f"Retrying with {self.TIER_NAMES.get(alt_tier)}")
                response = await self.execute_request(prompt, context,
                                                     force_tier=alt_tier)
            else:
                response.content = f"请求失败: {str(e)}"
                response.tier_used = ComputeTier.OFFLINE

        # 4. 后处理
        response.latency_ms = (time.time() - start_time) * 1000
        self.stats[f"{tier.value}_calls"] += 1

        # 5. 缓存结果
        if response.content and tier != ComputeTier.OFFLINE:
            self.cache.set(task_type.value, prompt, context, response)

        # 6. 记录成本
        if tier == ComputeTier.CLOUD:
            self.budget.record_spend(response.cost)
            self.total_cost += response.cost

        return response

    async def _execute_local(self, prompt: str, endpoint: Optional[TierEndpoint],
                            context: Dict) -> AIResponse:
        """执行本地模型"""
        try:
            from client.src.business.ollama_client import OllamaClient

            client = OllamaClient(base_url="http://localhost:11434")
            model = endpoint.endpoint if endpoint else "qwen2:1.5b"

            result = await client.generate(model, prompt)

            return AIResponse(
                content=result.get("response", ""),
                tier_used=ComputeTier.LOCAL,
                model_used=model,
                tokens_used=result.get("eval_count", 0),
                cost=0.0
            )
        except Exception as e:
            logger.error(f"Local execution failed: {e}")
            # 标记端点不可用
            if endpoint:
                endpoint.is_available = False
            raise

    async def _execute_edge(self, prompt: str, endpoint: Optional[TierEndpoint],
                           context: Dict) -> AIResponse:
        """执行边缘服务器"""
        try:
            import aiohttp

            url = f"{endpoint.endpoint}/api/generate"
            payload = {
                "model": endpoint.endpoint.split("/")[-1] if "/" in endpoint.endpoint else "qwen2:7b",
                "prompt": prompt,
                "stream": False
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=30) as resp:
                    result = await resp.json()

            return AIResponse(
                content=result.get("response", ""),
                tier_used=ComputeTier.EDGE,
                model_used=endpoint.name,
                tokens_used=result.get("eval_count", 0),
                cost=0.0
            )
        except Exception as e:
            logger.error(f"Edge execution failed: {e}")
            if endpoint:
                endpoint.is_available = False
            raise

    async def _execute_cloud(self, prompt: str, endpoint: Optional[TierEndpoint],
                           context: Dict) -> AIResponse:
        """执行云端API"""
        try:
            import aiohttp

            headers = {
                "Authorization": f"Bearer {endpoint.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": endpoint.endpoint.split("/")[-1] if "/" in str(endpoint.endpoint) else "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": endpoint.max_tokens
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    str(endpoint.endpoint),
                    headers=headers,
                    json=payload,
                    timeout=60
                ) as resp:
                    result = await resp.json()

            choices = result.get("choices", [])
            content = choices[0].get("message", {}).get("content", "") if choices else ""

            # 计算成本
            usage = result.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            cost = (input_tokens / 1000 * endpoint.cost_per_1k_input +
                   output_tokens / 1000 * endpoint.cost_per_1k_output)

            return AIResponse(
                content=content,
                tier_used=ComputeTier.CLOUD,
                model_used=endpoint.name,
                tokens_used=input_tokens + output_tokens,
                cost=cost
            )
        except Exception as e:
            logger.error(f"Cloud execution failed: {e}")
            raise

    async def _execute_offline(self, prompt: str, context: Dict) -> AIResponse:
        """离线降级模式"""
        return AIResponse(
            content="当前处于离线模式，无法访问AI服务。请检查网络连接或配置本地模型。",
            tier_used=ComputeTier.OFFLINE,
            model_used="offline",
            cost=0.0
        )

    def get_status(self) -> Dict[str, Any]:
        """获取路由状态"""
        return {
            "budget": {
                "monthly_limit": self.budget.monthly_limit,
                "monthly_spent": self.budget.current_month_spent,
                "daily_limit": self.budget.daily_limit,
                "daily_spent": self.budget.current_day_spent,
                "can_afford_cloud": self.budget.can_afford(0.1)
            },
            "cache_hit_rate": self.cache.get_hit_rate(),
            "stats": dict(self.stats),
            "total_cost": self.total_cost,
            "endpoints": {
                tier.value: [
                    {"name": ep.name, "available": ep.is_available,
                     "latency_ms": ep.latency_ms}
                    for ep in endpoints
                ]
                for tier, endpoints in self.endpoints.items()
            }
        }

    def set_budget(self, monthly: float = None, daily: float = None,
                  per_request: float = None):
        """设置预算"""
        if monthly is not None:
            self.budget.monthly_limit = monthly
        if daily is not None:
            self.budget.daily_limit = daily
        if per_request is not None:
            self.budget.per_request_limit = per_request


# 全局实例
_router: Optional[SmartAIRouter] = None


def get_smart_router() -> SmartAIRouter:
    """获取全局路由器"""
    global _router
    if _router is None:
        _router = SmartAIRouter()
    return _router


def route_ai_request(prompt: str, context: Optional[Dict] = None) -> AIResponse:
    """快捷路由函数"""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        get_smart_router().execute_request(prompt, context)
    )