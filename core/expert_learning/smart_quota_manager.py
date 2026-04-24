"""
智能配额管理器 (SmartQuotaManager)
===================================
API聚合层的成本控制核心模块

功能:
1. 配额模式管理 (HARVEST/MAINTENANCE/CONSERVATION)
2. 成本追踪 (调用次数/token消耗/费用估算)
3. 智能切换 (基于预算和使用趋势自动切换)
4. 配额限制 (日/周/月多层级限制)

Author: LivingTreeAI Agent
Date: 2026-04-24
"""

import time
import threading
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import json
import os


class QuotaMode(Enum):
    """配额模式"""
    HARVEST = "harvest"           # 收割模式: 积极使用外部API
    MAINTENANCE = "maintenance"   # 维护模式: 平衡使用
    CONSERVATION = "conservation" # 保守模式: 尽量使用本地


class Provider(Enum):
    """API提供商 (保留用于内置枚举)"""
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    ANTHROPIC = "anthropic"
    OPENROUTER = "openrouter"
    GROQ = "groq"
    OLLAMA = "ollama"   # 本地免费
    LOCAL = "local"     # 本地模型
    CUSTOM = "custom"    # 自定义提供者


# ==================== 定价配置 ====================

@dataclass
class PricingConfig:
    """API定价配置 (每1M token的价格，USD)"""
    input_cost: float = 0.0
    output_cost: float = 0.0
    per_call_cost: float = 0.0

    def calculate(self, input_tokens: int, output_tokens: int) -> float:
        """计算费用"""
        return (input_tokens / 1_000_000) * self.input_cost + \
               (output_tokens / 1_000_000) * self.output_cost + \
               self.per_call_cost


DEFAULT_PRICING: Dict[Provider, PricingConfig] = {
    Provider.OPENAI: PricingConfig(input_cost=2.5, output_cost=10.0),
    Provider.DEEPSEEK: PricingConfig(input_cost=0.14, output_cost=0.28),
    Provider.ANTHROPIC: PricingConfig(input_cost=3.0, output_cost=15.0),
    Provider.OPENROUTER: PricingConfig(input_cost=1.0, output_cost=2.0),
    Provider.GROQ: PricingConfig(input_cost=0.0, output_cost=0.0),
    Provider.OLLAMA: PricingConfig(input_cost=0.0, output_cost=0.0),
    Provider.LOCAL: PricingConfig(input_cost=0.0, output_cost=0.0),
}


@dataclass
class BudgetConfig:
    """预算配置"""
    daily_limit: float = 10.0
    weekly_limit: float = 50.0
    monthly_limit: float = 200.0
    warning_threshold: float = 0.8


@dataclass
class ProviderQuota:
    """提供商配额状态"""
    provider: str
    call_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost: float = 0.0
    last_reset: float = field(default_factory=time.time)
    reset_period: str = "daily"


@dataclass
class UsageRecord:
    """使用记录"""
    timestamp: float
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost: float
    success: bool
    latency_ms: float
    cached: bool = False


@dataclass
class ModeRecommendation:
    """模式推荐"""
    current_mode: QuotaMode
    recommended_mode: QuotaMode
    reason: str
    urgency: str  # low/medium/high


# ==================== 核心管理器 ====================

class SmartQuotaManager:
    """
    智能配额管理器

    自动追踪API使用情况，计算成本，并根据预算和模式策略
    智能决定是否允许调用外部API。

    支持内置Provider枚举和动态自定义Provider配置。

    使用示例:
    ```python
    manager = SmartQuotaManager(
        budget=BudgetConfig(daily_limit=5.0),
        default_mode=QuotaMode.MAINTENANCE
    )

    # 检查是否可以调用
    if manager.can_call(Provider.DEEPSEEK, estimated_tokens=1000):
        # 调用API...
        manager.record_usage(
            provider=Provider.DEEPSEEK,
            model="deepseek-chat",
            input_tokens=500,
            output_tokens=200,
            success=True,
            latency_ms=1500
        )

    # 使用自定义提供者ID (来自ExternalProviderManager)
    if manager.can_call_by_id("provider_abc123", estimated_tokens=1000):
        logger.info("可以使用自定义提供者")
    ```
    """

    def __init__(
        self,
        budget: Optional[BudgetConfig] = None,
        default_mode: QuotaMode = QuotaMode.MAINTENANCE,
        pricing: Optional[Dict[Provider, PricingConfig]] = None,
        storage_path: Optional[str] = None,
        prefer_free: bool = True,
    ):
        self.budget = budget or BudgetConfig()
        self.default_mode = default_mode
        self.current_mode = default_mode
        self.locked_mode: Optional[QuotaMode] = None
        self.pricing = pricing or DEFAULT_PRICING.copy()
        self.storage_path = storage_path
        self.prefer_free = prefer_free  # 优先使用免费模型

        # 动态提供者管理器 (懒加载)
        self._provider_manager = None

        self._daily: Dict[str, ProviderQuota] = {}
        self._weekly: Dict[str, ProviderQuota] = {}
        self._monthly: Dict[str, ProviderQuota] = {}
        self._usage_history: List[UsageRecord] = []
        self._mode_history: List[Dict] = []

        self._on_mode_change: Optional[Callable[[QuotaMode, QuotaMode], None]] = None
        self._on_warning: Optional[Callable[[str, float], None]] = None
        self._on_limit_reached: Optional[Callable[[str], None]] = None

        self._lock = threading.RLock()
        self._init_periods()
        self._load_state()

        logger.info("[SmartQuotaManager] Smart quota management enabled (prefer_free={})".format(prefer_free))

    @property
    def provider_manager(self):
        """获取提供者管理器 (懒加载)"""
        if self._provider_manager is None:
            try:
                from core.expert_learning.external_provider_config import get_provider_manager
                self._provider_manager = get_provider_manager()
            except ImportError:
                self._provider_manager = None
        return self._provider_manager

    # ==================== 公共API ====================

    def can_call(
        self,
        provider: Provider,
        estimated_tokens: int = 0,
        priority: str = "normal"
    ) -> bool:
        """检查是否可以调用API"""
        with self._lock:
            if self.locked_mode == QuotaMode.CONSERVATION:
                if priority != "high":
                    return False

            if provider in [Provider.OLLAMA, Provider.LOCAL]:
                return True

            pricing = self.pricing.get(provider, PricingConfig())
            estimated_cost = pricing.calculate(estimated_tokens, estimated_tokens * 2)

            limits = [
                ("daily", self._daily, self.budget.daily_limit),
                ("weekly", self._weekly, self.budget.weekly_limit),
                ("monthly", self._monthly, self.budget.monthly_limit),
            ]

            for period_name, period_data, limit in limits:
                if period_name not in period_data:
                    continue
                quota = period_data[period_name]
                remaining = limit - quota.total_cost

                if priority == "high" and remaining >= estimated_cost * 0.5:
                    continue

                if remaining < estimated_cost:
                    return False

            if self.current_mode == QuotaMode.CONSERVATION and priority == "low":
                return False

            return True

    # ── 动态提供者支持 ⭐ ──────────────────────────────────────────────

    def can_call_by_id(
        self,
        provider_id: str,
        estimated_tokens: int = 0,
        priority: str = "normal"
    ) -> bool:
        """
        检查自定义提供者是否可用

        Args:
            provider_id: 提供者ID (来自ExternalProviderManager)
            estimated_tokens: 预估token数
            priority: 优先级

        Returns:
            bool: 是否可以调用
        """
        pm = self.provider_manager
        if pm is None:
            return True  # 没有提供者管理器，默认允许

        config = pm.get_provider(provider_id)
        if not config:
            return False
        if not config.enabled:
            return False

        # 免费提供者直接返回True
        if config.is_free():
            return True

        # 检查配额
        if config.daily_limit > 0 and config.use_count >= config.daily_limit:
            return False

        # 如果是保守模式，只允许高优先级请求
        if self.locked_mode == QuotaMode.CONSERVATION and priority != "high":
            return False

        return True

    def select_best_provider(
        self,
        estimated_tokens: int = 1000,
        prefer_free: bool = None,
        required_model: str = "",
    ) -> Optional[Dict[str, Any]]:
        """
        选择最优提供者 (内置 + 动态)

        策略:
        1. 优先使用免费的
        2. 按优先级排序
        3. 考虑预算限制

        Args:
            estimated_tokens: 预估输入token数
            prefer_free: 是否优先免费 (None=使用默认设置)
            required_model: 需要的模型名称

        Returns:
            Dict: {"type": "builtin"|"custom", "provider": Provider|provider_id, "model": str}
        """
        if prefer_free is None:
            prefer_free = self.prefer_free

        pm = self.provider_manager

        # 1. 先尝试动态提供者 (ExternalProviderManager)
        if pm:
            # 优先获取免费提供者
            if prefer_free:
                free_provider = pm.get_best_free_provider(required_model)
                if free_provider and self.can_call_by_id(free_provider.id, estimated_tokens):
                    return {
                        "type": "custom",
                        "provider_id": free_provider.id,
                        "name": free_provider.name,
                        "model": free_provider.default_model,
                        "is_free": True,
                        "cost_type": free_provider.cost_type.value,
                    }

            # 获取最优提供者
            best = pm.get_best_provider(
                estimated_tokens=estimated_tokens,
                prefer_free=prefer_free,
                required_model=required_model,
            )
            if best and self.can_call_by_id(best.id, estimated_tokens):
                return {
                    "type": "custom",
                    "provider_id": best.id,
                    "name": best.name,
                    "model": best.default_model,
                    "is_free": best.is_free(),
                    "cost_type": best.cost_type.value,
                }

        # 2. 回退到内置提供者
        builtin_providers = [
            Provider.OLLAMA,
            Provider.LOCAL,
            Provider.GROQ,
            Provider.DEEPSEEK,
            Provider.OPENROUTER,
            Provider.ANTHROPIC,
            Provider.OPENAI,
        ]

        for provider in builtin_providers:
            if provider in [Provider.OLLAMA, Provider.LOCAL]:
                return {
                    "type": "builtin",
                    "provider": provider.value,
                    "model": "",
                    "is_free": True,
                }

            if prefer_free:
                continue  # 跳过收费的

            if self.can_call(provider, estimated_tokens):
                return {
                    "type": "builtin",
                    "provider": provider.value,
                    "model": "",
                    "is_free": False,
                }

        # 3. 最后允许使用OLLAMA作为后备
        return {
            "type": "builtin",
            "provider": Provider.OLLAMA.value,
            "model": "qwen2.5:1.5b",
            "is_free": True,
        }

    def record_usage_by_id(
        self,
        provider_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        success: bool,
        latency_ms: float,
        cached: bool = False,
    ) -> float:
        """
        记录自定义提供者的使用

        Args:
            provider_id: 提供者ID
            model: 模型名称
            input_tokens: 输入token数
            output_tokens: 输出token数
            success: 是否成功
            latency_ms: 延迟(ms)
            cached: 是否使用缓存

        Returns:
            float: 估算费用
        """
        pm = self.provider_manager
        if pm:
            pm.record_usage(provider_id, success)

        # 尝试获取定价
        cost = 0.0
        if pm:
            config = pm.get_provider(provider_id)
            if config:
                pricing = config.get_default_pricing()
                cost = (input_tokens / 1_000_000) * pricing.input_cost_per_million + \
                       (output_tokens / 1_000_000) * pricing.output_cost_per_million

        # 记录到配额管理器
        record = UsageRecord(
            timestamp=time.time(),
            provider=provider_id,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            success=success,
            latency_ms=latency_ms,
            cached=cached,
        )
        self._usage_history.append(record)

        if not cached:
            self._update_period(self._daily, provider_id, input_tokens, output_tokens, cost)
            self._update_period(self._weekly, provider_id, input_tokens, output_tokens, cost)
            self._update_period(self._monthly, provider_id, input_tokens, output_tokens, cost)

            self._check_warnings()
            self._auto_evaluate_mode()
            self._save_state()

        return cost

    def set_prefer_free(self, prefer_free: bool) -> None:
        """设置是否优先使用免费模型"""
        self.prefer_free = prefer_free

    def record_usage(
        self,
        provider: Provider,
        model: str,
        input_tokens: int,
        output_tokens: int,
        success: bool,
        latency_ms: float,
        cached: bool = False,
    ) -> float:
        """记录API使用情况"""
        with self._lock:
            pricing = self.pricing.get(provider, PricingConfig())
            cost = pricing.calculate(input_tokens, output_tokens)

            record = UsageRecord(
                timestamp=time.time(),
                provider=provider.value,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost,
                success=success,
                latency_ms=latency_ms,
                cached=cached,
            )
            self._usage_history.append(record)

            if not cached:
                self._update_period(self._daily, provider.value, input_tokens, output_tokens, cost)
                self._update_period(self._weekly, provider.value, input_tokens, output_tokens, cost)
                self._update_period(self._monthly, provider.value, input_tokens, output_tokens, cost)

            self._check_warnings()
            self._auto_evaluate_mode()
            self._save_state()

            return cost

    def get_mode(self) -> QuotaMode:
        """获取当前模式"""
        return self.locked_mode or self.current_mode

    def set_mode(self, mode: QuotaMode, locked: bool = False) -> None:
        """设置配额模式"""
        old_mode = self.get_mode()

        if locked:
            self.locked_mode = mode
            self.current_mode = mode
        else:
            self.current_mode = mode
            self.locked_mode = None

        if old_mode != self.get_mode():
            self._mode_history.append({
                "timestamp": time.time(),
                "from": old_mode.value,
                "to": self.get_mode().value,
                "locked": locked,
            })
            if self._on_mode_change:
                self._on_mode_change(old_mode, self.get_mode())

    def set_budget(self, budget: BudgetConfig) -> None:
        """更新预算配置"""
        self.budget = budget

    def set_callbacks(
        self,
        on_mode_change: Callable[[QuotaMode, QuotaMode], None] = None,
        on_warning: Callable[[str, float], None] = None,
        on_limit_reached: Callable[[str], None] = None,
    ) -> None:
        """设置回调函数"""
        self._on_mode_change = on_mode_change
        self._on_warning = on_warning
        self._on_limit_reached = on_limit_reached

    def get_usage_stats(self, period: str = "daily") -> Dict[str, Any]:
        """获取使用统计"""
        with self._lock:
            if period == "all":
                return {
                    "daily": self._get_period_summary(self._daily),
                    "weekly": self._get_period_summary(self._weekly),
                    "monthly": self._get_period_summary(self._monthly),
                    "total_calls": len(self._usage_history),
                    "success_rate": self._calc_success_rate(),
                }

            period_data = getattr(self, f"_{period}", {})
            budget = getattr(self.budget, f"{period}_limit")

            total_cost = sum(q.total_cost for q in period_data.values())
            total_calls = sum(q.call_count for q in period_data.values())

            by_provider = {}
            for name, quota in period_data.items():
                by_provider[name] = {
                    "calls": quota.call_count,
                    "input_tokens": quota.input_tokens,
                    "output_tokens": quota.output_tokens,
                    "cost": quota.total_cost,
                }

            return {
                "period": period,
                "budget": budget,
                "used": total_cost,
                "remaining": budget - total_cost,
                "usage_pct": (total_cost / budget * 100) if budget > 0 else 0,
                "total_calls": total_calls,
                "by_provider": by_provider,
                "mode": self.get_mode().value,
                "locked": self.locked_mode is not None,
            }

    def get_recommendation(self) -> ModeRecommendation:
        """获取模式推荐"""
        with self._lock:
            daily_pct = self._get_period_usage_pct(self._daily, self.budget.daily_limit)
            weekly_pct = self._get_period_usage_pct(self._weekly, self.budget.weekly_limit)
            monthly_pct = self._get_period_usage_pct(self._monthly, self.budget.monthly_limit)

            if monthly_pct >= 90 or weekly_pct >= 85:
                recommended = QuotaMode.CONSERVATION
                reason = f"Budget critical: monthly {monthly_pct:.1f}%, weekly {weekly_pct:.1f}%"
                urgency = "high"
            elif daily_pct >= 80:
                recommended = QuotaMode.CONSERVATION
                reason = f"Daily budget nearly exhausted ({daily_pct:.1f}%)"
                urgency = "high"
            elif daily_pct >= 50 or weekly_pct >= 40:
                recommended = QuotaMode.MAINTENANCE
                reason = f"Moderate usage: daily {daily_pct:.1f}%, weekly {weekly_pct:.1f}%"
                urgency = "medium"
            elif monthly_pct < 30 and weekly_pct < 20 and daily_pct < 10:
                recommended = QuotaMode.HARVEST
                reason = f"Budget healthy, harvest knowledge ({monthly_pct:.1f}%)"
                urgency = "low"
            else:
                recommended = QuotaMode.MAINTENANCE
                reason = "Budget usage normal"
                urgency = "low"

            return ModeRecommendation(
                current_mode=self.get_mode(),
                recommended_mode=recommended,
                reason=reason,
                urgency=urgency,
            )

    def get_cost_breakdown(self, days: int = 7) -> Dict[str, Any]:
        """获取成本分解"""
        with self._lock:
            cutoff = time.time() - (days * 86400)
            recent = [r for r in self._usage_history if r.timestamp >= cutoff]

            by_day = defaultdict(lambda: {"cost": 0.0, "calls": 0, "tokens": 0})
            by_provider = defaultdict(lambda: {"cost": 0.0, "calls": 0})

            for r in recent:
                day = time.strftime("%Y-%m-%d", time.localtime(r.timestamp))
                by_day[day]["cost"] += r.cost
                by_day[day]["calls"] += 1
                by_day[day]["tokens"] += r.input_tokens + r.output_tokens

                by_provider[r.provider]["cost"] += r.cost
                by_provider[r.provider]["calls"] += 1

            total_cost = sum(r.cost for r in recent)
            avg_cost = total_cost / days if days > 0 else 0

            return {
                "days": days,
                "total_cost": total_cost,
                "avg_daily_cost": avg_cost,
                "projected_monthly": avg_cost * 30,
                "by_day": dict(by_day),
                "by_provider": dict(by_provider),
                "total_calls": len(recent),
            }

    def reset(self, period: str = "daily") -> None:
        """重置配额统计"""
        with self._lock:
            if period == "daily":
                self._daily.clear()
            elif period == "weekly":
                self._weekly.clear()
            elif period == "monthly":
                self._monthly.clear()
            elif period == "all":
                self._daily.clear()
                self._weekly.clear()
                self._monthly.clear()

    # ==================== 内部方法 ====================

    def _init_periods(self) -> None:
        """初始化周期追踪"""
        self._last_daily_reset = self._get_day_start()
        self._last_weekly_reset = self._get_week_start()
        self._last_monthly_reset = self._get_month_start()

    def _get_day_start(self) -> float:
        return time.mktime(time.strptime(time.strftime("%Y-%m-%d"), "%Y-%m-%d"))

    def _get_week_start(self) -> float:
        now = time.localtime()
        week_start = time.mktime((now.tm_year, now.tm_mon, now.tm_mday - now.tm_wday, 0, 0, 0, 0, 0, 0))
        return week_start

    def _get_month_start(self) -> float:
        now = time.localtime()
        return time.mktime((now.tm_year, now.tm_mon, 1, 0, 0, 0, 0, 0, 0))

    def _update_period(
        self,
        period_data: Dict[str, ProviderQuota],
        provider: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
    ) -> None:
        if provider not in period_data:
            period_data[provider] = ProviderQuota(provider=provider)
        q = period_data[provider]
        q.call_count += 1
        q.input_tokens += input_tokens
        q.output_tokens += output_tokens
        q.total_cost += cost

    def _check_warnings(self) -> None:
        """检查是否需要警告"""
        for period_name, period_data, limit in [
            ("daily", self._daily, self.budget.daily_limit),
            ("weekly", self._weekly, self.budget.weekly_limit),
        ]:
            total_cost = sum(q.total_cost for q in period_data.values())
            usage_pct = total_cost / limit if limit > 0 else 0

            if usage_pct >= self.budget.warning_threshold:
                if self._on_warning:
                    self._on_warning(period_name, usage_pct)

            if total_cost >= limit:
                if self._on_limit_reached:
                    self._on_limit_reached(period_name)

    def _auto_evaluate_mode(self) -> None:
        """自动评估模式"""
        if self.locked_mode is not None:
            return

        rec = self.get_recommendation()
        if rec.urgency == "high" and self.current_mode != QuotaMode.CONSERVATION:
            self.set_mode(QuotaMode.CONSERVATION)
        elif rec.urgency == "low" and self.current_mode == QuotaMode.MAINTENANCE:
            self.set_mode(QuotaMode.HARVEST)

    def _get_period_summary(self, period_data: Dict[str, ProviderQuota]) -> Dict[str, Any]:
        total_cost = sum(q.total_cost for q in period_data.values())
        total_calls = sum(q.call_count for q in period_data.values())
        return {
            "cost": total_cost,
            "calls": total_calls,
            "providers": len(period_data),
        }

    def _get_period_usage_pct(self, period_data: Dict[str, ProviderQuota], limit: float) -> float:
        total_cost = sum(q.total_cost for q in period_data.values())
        return (total_cost / limit * 100) if limit > 0 else 0

    def _calc_success_rate(self) -> float:
        if not self._usage_history:
            return 0.0
        successes = sum(1 for r in self._usage_history if r.success)
        return successes / len(self._usage_history) * 100

    def _save_state(self) -> None:
        """保存状态到磁盘"""
        if not self.storage_path:
            return
        try:
            state = {
                "daily": [(k, vars(v)) for k, v in self._daily.items()],
                "weekly": [(k, vars(v)) for k, v in self._weekly.items()],
                "monthly": [(k, vars(v)) for k, v in self._monthly.items()],
                "mode_history": self._mode_history[-100:],
                "current_mode": self.current_mode.value,
                "locked_mode": self.locked_mode.value if self.locked_mode else None,
                "last_save": time.time(),
            }
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.info(f"[SmartQuotaManager] Failed to save state: {e}")

    def _load_state(self) -> None:
        """从磁盘加载状态"""
        if not self.storage_path or not os.path.exists(self.storage_path):
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                state = json.load(f)

            self._daily = {k: ProviderQuota(**v) for k, v in dict(state.get("daily", []))}
            self._weekly = {k: ProviderQuota(**v) for k, v in dict(state.get("weekly", []))}
            self._monthly = {k: ProviderQuota(**v) for k, v in dict(state.get("monthly", []))}

            if state.get("current_mode"):
                self.current_mode = QuotaMode(state["current_mode"])
            if state.get("locked_mode"):
                self.locked_mode = QuotaMode(state["locked_mode"])

            self._mode_history = state.get("mode_history", [])

            # 检查是否需要重置
            self._check_period_reset()
        except Exception as e:
            logger.info(f"[SmartQuotaManager] Failed to load state: {e}")

    def _check_period_reset(self) -> None:
        """检查并重置过期周期"""
        now = time.time()

        if now - self._last_daily_reset >= 86400:
            self._daily.clear()
            self._last_daily_reset = self._get_day_start()

        if now - self._last_weekly_reset >= 604800:
            self._weekly.clear()
            self._last_weekly_reset = self._get_week_start()

        if now - self._last_monthly_reset >= 2592000:
            self._monthly.clear()
            self._last_monthly_reset = self._get_month_start()

    # ==================== 便捷方法 ====================

    def estimate_cost(
        self,
        provider: Provider,
        input_tokens: int,
        output_tokens: int = 0,
    ) -> float:
        """估算成本"""
        pricing = self.pricing.get(provider, PricingConfig())
        output_tokens = output_tokens or input_tokens
        return pricing.calculate(input_tokens, output_tokens)

    def should_use_cache(self, provider: Provider) -> bool:
        """判断是否应该优先使用缓存"""
        return self.current_mode == QuotaMode.CONSERVATION

    def get_provider_priority(self, provider: Provider) -> int:
        """获取提供商优先级 (数字越小优先级越高)"""
        priorities = {
            Provider.LOCAL: 0,
            Provider.OLLAMA: 1,
            Provider.GROQ: 2,
            Provider.DEEPSEEK: 3,
            Provider.OPENROUTER: 4,
            Provider.ANTHROPIC: 5,
            Provider.OPENAI: 6,
        }
        return priorities.get(provider, 10)

    def select_best_builtin_provider(
        self,
        required_tokens: int,
        available_providers: List[Provider] = None,
    ) -> Optional[Provider]:
        """
        选择最优内置提供商 (仅限Provider枚举)

        考虑因素:
        1. 预算限制
        2. 当前模式
        3. 成本效率
        """
        if available_providers is None:
            available_providers = [
                Provider.DEEPSEEK,
                Provider.ANTHROPIC,
                Provider.OPENAI,
                Provider.OPENROUTER,
            ]

        candidates = []
        for provider in available_providers:
            if self.can_call(provider, required_tokens):
                cost = self.estimate_cost(provider, required_tokens)
                priority = self.get_provider_priority(provider)
                candidates.append((provider, cost, priority))

        if not candidates:
            return None

        # 按成本和优先级排序
        candidates.sort(key=lambda x: (x[1], x[2]))
        return candidates[0][0]

    # ── 提供者管理便捷方法 ⭐ ──────────────────────────────────────

    def add_custom_provider(
        self,
        name: str,
        provider_type: str,
        api_key: str = "",
        cost_type: str = "paid",
        endpoint_base_url: str = "",
        priority: int = 100,
        default_model: str = "",
        **kwargs
    ) -> Optional[str]:
        """
        添加自定义提供者 (便捷方法)

        Args:
            name: 显示名称
            provider_type: 提供者类型 (openai/deepseek/anthropic等)
            api_key: API Key
            cost_type: 费用类型 (free/freemium/paid)
            endpoint_base_url: API基础URL
            priority: 优先级
            default_model: 默认模型

        Returns:
            str: 提供者ID 或 None
        """
        pm = self.provider_manager
        if pm is None:
            return None

        try:
            from core.expert_learning.external_provider_config import ProviderType, CostType
from core.logger import get_logger
logger = get_logger('expert_learning.smart_quota_manager')


            # 转换类型
            p_type = ProviderType(provider_type.lower())
            c_type = CostType(cost_type.lower())

            return pm.add_provider(
                name=name,
                provider_type=p_type,
                api_key=api_key,
                cost_type=c_type,
                endpoint_base_url=endpoint_base_url,
                priority=priority,
                default_model=default_model,
                **kwargs
            )
        except Exception as e:
            logger.info(f"[SmartQuotaManager] 添加提供者失败: {e}")
            return None

    def list_available_providers(self, include_free_first: bool = True) -> List[Dict[str, Any]]:
        """
        列出所有可用的提供者

        Args:
            include_free_first: 是否优先显示免费的

        Returns:
            List[Dict]: 提供者信息列表
        """
        pm = self.provider_manager
        if pm is None:
            return []

        providers = pm.get_available_providers(include_free_first=include_free_first)
        return [
            {
                "id": p.id,
                "name": p.name,
                "type": p.provider_type.value,
                "cost_type": p.cost_type.value,
                "is_free": p.is_free(),
                "enabled": p.enabled,
                "priority": p.priority,
                "use_count": p.use_count,
                "daily_limit": p.daily_limit,
            }
            for p in providers
        ]

    def get_free_providers(self) -> List[Dict[str, Any]]:
        """获取所有免费提供者"""
        pm = self.provider_manager
        if pm is None:
            return []

        free = pm.get_available_providers(
            include_free_first=True,
            cost_type=None,  # 不过滤
        )
        free = [p for p in free if p.is_free()]
        return [
            {
                "id": p.id,
                "name": p.name,
                "type": p.provider_type.value,
                "default_model": p.default_model,
            }
            for p in free
        ]


# ==================== 单例 ====================

_quota_manager: Optional[SmartQuotaManager] = None


def get_quota_manager() -> SmartQuotaManager:
    """获取全局配额管理器实例"""
    global _quota_manager
    if _quota_manager is None:
        storage_path = os.path.join(
            os.path.dirname(__file__),
            "../../../config/quota_state.json"
        )
        _quota_manager = SmartQuotaManager(
            budget=BudgetConfig(
                daily_limit=5.0,
                weekly_limit=30.0,
                monthly_limit=100.0,
            ),
            default_mode=QuotaMode.MAINTENANCE,
            storage_path=storage_path,
        )
    return _quota_manager
