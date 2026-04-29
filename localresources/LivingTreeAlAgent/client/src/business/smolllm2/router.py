# -*- coding: utf-8 -*-
"""
L0 路由网关 - SmolLM2 快反大脑
==============================

在请求进 RelayFreeLLM 前先过 SmolLM2：
1. 意图分类：判断用户问题类型
2. 路由决策：缓存/本地/搜索/重型
3. 快速通道：简单任务直接返回

核心流程：
用户输入 → SmolLM2 意图分类 → 路由决策 → 执行通道
"""

import re
import time
import json
import hashlib
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .models import (
    RouteDecision, RouteType, IntentType, SmolLM2Config, CachedResponse, RouteStats
)
from .ollama_runner import OllamaRunner, get_runner_manager


# 简单任务规则（不走 SmolLM2 的快速路径）
FAST_PATTERNS = {
    # 问候
    r"^(你好|您好|嗨|hi|hello|hey)[\s,，.!]*$": (RouteType.LOCAL, IntentType.GREETING),
    r"^(早上好|下午好|晚上好|晚安|早)[\s,，.!]*$": (RouteType.LOCAL, IntentType.GREETING),

    # 简单问答
    r"^(是什么|有没有|是不是|能不能|要不要)[\s\S]*[?？]?$": (RouteType.LOCAL, IntentType.SIMPLE_QUESTION),
    r"^(谁|哪|怎么|多少|多久)[\s\S]*[?？]?$": (RouteType.LOCAL, IntentType.SIMPLE_QUESTION),

    # 格式化
    r"^(整理|格式化|规范|纠错|改正)": (RouteType.LOCAL, IntentType.FORMAT_CLEAN),
    r"^给我.*格式": (RouteType.LOCAL, IntentType.FORMAT_CLEAN),

    # JSON 提取
    r"^(提取|转成|转为).*json": (RouteType.LOCAL, IntentType.JSON_EXTRACT),
    r".*json.*提取": (RouteType.LOCAL, IntentType.JSON_EXTRACT),

    # 简单代码
    r"^(fix|typo|拼写|spell)": (RouteType.LOCAL, IntentType.CODE_SIMPLE),
    r"^(注释|comment|解释)[\s]+": (RouteType.LOCAL, IntentType.CODE_SIMPLE),

    # 搜索意图
    r"^(查一下|帮我查|查询|搜索).*(价格|库存|状态|行情)": (RouteType.SEARCH, IntentType.SEARCH_QUERY),
    r"^(最新|最近|今天|当前).*(价格|行情|新闻)": (RouteType.SEARCH, IntentType.SEARCH_QUERY),
}

# 重型任务规则（直接走大模型）
HEAVY_PATTERNS = [
    (r"(写|创作|生成).{20,}?(文章|报告|方案|小说|书籍)", RouteType.HEAVY, IntentType.LONG_WRITING),
    (r"(分析|评估|对比).{20,}?(市场|竞品|趋势|投资)", RouteType.HEAVY, IntentType.ANALYSIS),
    (r"(推理|推导|证明|论证)", RouteType.HEAVY, IntentType.REASONING),
    (r"(代码.{5,})?(架构|设计|重构|系统)", RouteType.HEAVY, IntentType.CODE_COMPLEX),
    (r"(长度|超过|不少于|大于).{5,}(字|词|字符)", RouteType.HEAVY, IntentType.LONG_WRITING),
]


class LRUCache:
    """简单 LRU 缓存"""

    def __init__(self, max_size: int = 100, ttl_hours: int = 24):
        self.max_size = max_size
        self.ttl = timedelta(hours=ttl_hours)
        self._cache: Dict[str, CachedResponse] = {}
        self._access_order: List[str] = []

    def get(self, key: str) -> Optional[CachedResponse]:
        """获取缓存"""
        if key not in self._cache:
            return None

        cached = self._cache[key]

        # 检查过期
        if datetime.now() - cached.created_at > self.ttl:
            del self._cache[key]
            self._access_order.remove(key)
            return None

        # 更新访问顺序
        self._access_order.remove(key)
        self._access_order.append(key)

        cached.hit_count += 1
        return cached

    def set(self, key: str, value: str, source: str = "local"):
        """设置缓存"""
        if key in self._cache:
            self._access_order.remove(key)
        elif len(self._cache) >= self.max_size:
            # 淘汰最旧的
            oldest = self._access_order.pop(0)
            del self._cache[oldest]

        self._cache[key] = CachedResponse(
            prompt_hash=key,
            response=value,
            source=source,
        )
        self._access_order.append(key)

    def clear(self):
        """清空缓存"""
        self._cache.clear()
        self._access_order.clear()


class L0Router:
    """
    L0 路由网关

    定位：
    - L0 = First Responder（第一响应者）
    - 轻量级意图分类 + 快速路由
    - 目标：<1s 响应
    """

    def __init__(
        self,
        config: Optional[SmolLM2Config] = None,
        enable_cache: bool = True
    ):
        self.config = config or SmolLM2Config()
        self._runner: Optional[OllamaRunner] = None
        self._cache = LRUCache() if enable_cache else None

        # 统计
        self._stats = RouteStats()

        # 回调函数
        self._on_route_decision: Optional[Callable[[RouteDecision], None]] = None

    # ==================== 核心路由 ====================

    async def route(self, prompt: str) -> RouteDecision:
        """
        路由决策

        Args:
            prompt: 用户输入

        Returns:
            RouteDecision: 路由决策结果
        """
        start_time = time.time()

        # 1. 长度预检
        if len(prompt) > self.config.heavy_threshold_chars:
            return self._make_decision(
                RouteType.HEAVY,
                IntentType.UNKNOWN,
                "输入过长，直接走大模型",
                1.0,
                start_time,
            )

        # 2. 快速模式匹配
        fast_decision = self._fast_match(prompt)
        if fast_decision:
            return fast_decision

        # 3. 缓存检查
        if self._cache:
            cached = self._cache.get(self._hash_prompt(prompt))
            if cached:
                self._stats.cache_hits += 1
                return RouteDecision(
                    route=RouteType.CACHE,
                    intent=IntentType.UNKNOWN,
                    reason=f"缓存命中 (hit={cached.hit_count})",
                    confidence=0.95,
                    latency_ms=(time.time() - start_time) * 1000,
                    fallback=False,
                )

        # 4. SmolLM2 意图分类
        try:
            decision = await self._smollm2_classify(prompt, start_time)
            if decision:
                return decision
        except Exception as e:
            print(f"SmolLM2 分类失败: {e}")

        # 5. 兜底：默认走本地
        return self._make_decision(
            RouteType.LOCAL,
            IntentType.UNKNOWN,
            "兜底：默认本地执行",
            0.5,
            start_time,
        )

    def _fast_match(self, prompt: str) -> Optional[RouteDecision]:
        """快速模式匹配"""
        prompt_lower = prompt.lower().strip()

        # 检查重型模式
        for pattern, route, intent in HEAVY_PATTERNS:
            if re.search(pattern, prompt_lower):
                return RouteDecision(
                    route=route,
                    intent=intent,
                    reason="快速模式：命中重型规则",
                    confidence=0.9,
                    latency_ms=0,
                    fallback=False,
                )

        # 检查快速模式
        for pattern, (route, intent) in FAST_PATTERNS.items():
            if re.match(pattern, prompt_lower):
                return RouteDecision(
                    route=route,
                    intent=intent,
                    reason="快速模式：命中简单规则",
                    confidence=0.85,
                    latency_ms=0,
                    fallback=False,
                )

        return None

    async def _smollm2_classify(
        self,
        prompt: str,
        start_time: float
    ) -> Optional[RouteDecision]:
        """使用 SmolLM2 进行意图分类"""
        # 确保 Runner 就绪
        if not self._runner:
            manager = await get_runner_manager()
            self._runner = await manager.get_runner()

            if not await manager.ensure_ready():
                return None

        # 构建提示词
        classify_prompt = f"""{self.config.system_prompt}

用户输入：{prompt}

只输出JSON，不要其他内容。"""

        # 调用 SmolLM2
        try:
            response = await self._runner.generate(
                prompt=classify_prompt,
                stream=False
            )

            # 解析 JSON
            json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                route_str = data.get("route", "local")
                intent_str = data.get("intent", "unknown")
                reason = data.get("reason", "")
                confidence = float(data.get("confidence", 0.7))

                # 转换枚举
                try:
                    route = RouteType(route_str)
                except ValueError:
                    route = RouteType.LOCAL

                try:
                    intent = IntentType(intent_str)
                except ValueError:
                    intent = IntentType.UNKNOWN

                # 更新统计
                self._update_stats(route)

                return RouteDecision(
                    route=route,
                    intent=intent,
                    reason=reason or "SmolLM2 分类",
                    confidence=confidence,
                    latency_ms=(time.time() - start_time) * 1000,
                    fallback=False,
                )

        except Exception as e:
            print(f"SmolLM2 调用异常: {e}")

        return None

    def _make_decision(
        self,
        route: RouteType,
        intent: IntentType,
        reason: str,
        confidence: float,
        start_time: float
    ) -> RouteDecision:
        """创建路由决策"""
        decision = RouteDecision(
            route=route,
            intent=intent,
            reason=reason,
            confidence=confidence,
            latency_ms=(time.time() - start_time) * 1000,
            fallback=True,
        )

        self._update_stats(route)
        return decision

    def _update_stats(self, route: RouteType):
        """更新统计"""
        self._stats.total_requests += 1

        if route == RouteType.CACHE:
            self._stats.cache_hits += 1
        elif route == RouteType.LOCAL:
            self._stats.local_executions += 1
        elif route == RouteType.SEARCH:
            self._stats.search_requests += 1
        elif route == RouteType.HEAVY:
            self._stats.heavy_inferences += 1
        elif route == RouteType.HUMAN:
            self._stats.human_escalations += 1

        # 计算快反率
        if self._stats.total_requests > 0:
            fast_count = self._stats.cache_hits + self._stats.local_executions
            self._stats.fast_response_rate = fast_count / self._stats.total_requests

    def _hash_prompt(self, prompt: str) -> str:
        """哈希提示词"""
        return hashlib.md5(prompt.encode()).hexdigest()

    # ==================== 缓存管理 ====================

    def cache_response(self, prompt: str, response: str, source: str = "local"):
        """缓存响应"""
        if self._cache:
            self._cache.set(self._hash_prompt(prompt), response, source)

    def clear_cache(self):
        """清空缓存"""
        if self._cache:
            self._cache.clear()

    # ==================== 统计 ====================

    def get_stats(self) -> Dict[str, Any]:
        """获取路由统计"""
        stats = self._stats.to_dict()
        if self._cache:
            stats["cache_size"] = len(self._cache._cache)
        return stats

    # ==================== 集成 RelayFreeLLM ====================

    async def pre_route(self, prompt: str) -> RouteDecision:
        """
        前置路由（集成点）

        在请求进 RelayFreeLLM 前调用：
        - 如果返回 HEAVY/SEARCH，继续走大模型
        - 如果返回 LOCAL/CODE_SIMPLE，直接执行或调用工具
        - 如果返回 CACHE，直接返回缓存
        """
        return await self.route(prompt)

    # ==================== 同步版本 ====================

    def route_sync(self, prompt: str) -> RouteDecision:
        """同步路由"""
        try:
            loop = None
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            return loop.run_until_complete(self.route(prompt))
        except Exception as e:
            print(f"同步路由失败: {e}")
            return RouteDecision(
                route=RouteType.LOCAL,
                intent=IntentType.UNKNOWN,
                reason=f"同步路由异常: {e}",
                confidence=0.0,
                fallback=True,
            )
