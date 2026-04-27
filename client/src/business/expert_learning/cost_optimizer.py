# -*- coding: utf-8 -*-
"""
成本优化引擎 (Cost Optimizer)
=============================

智能切换免费/收费模型，在保证质量的前提下最大化节省成本。

功能:
1. 成本追踪 - 实时监控各模型使用成本
2. 智能切换 - 根据预算和质量需求自动切换
3. 预算管理 - 多层级预算控制
4. 成本预测 - 预测未来成本趋势
5. 优化建议 - 提供成本优化建议

Author: LivingTreeAI Agent
Date: 2026-04-24
"""

from __future__ import annotations

import json
import time
from typing import Optional, List, Dict, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import threading
from client.src.business.logger import get_logger
logger = get_logger('expert_learning.cost_optimizer')



class CostMode(Enum):
    """成本模式"""
    FREE_ONLY = "free_only"         # 纯免费
    FREE_PREFERRED = "free_preferred"  # 免费优先
    BALANCED = "balanced"           # 平衡模式
    QUALITY_FIRST = "quality_first"  # 质量优先


@dataclass
class CostRecord:
    """成本记录"""
    timestamp: float
    model_id: str
    input_tokens: int
    output_tokens: int
    cost: float
    quality_score: float = 0


@dataclass
class BudgetStatus:
    """预算状态"""
    period: str  # daily/weekly/monthly
    limit: float
    used: float
    remaining: float
    usage_pct: float
    projected_exhaustion: Optional[float] = None  # 预计耗尽时间戳


@dataclass
class OptimizationResult:
    """优化结果"""
    recommended_model: str
    estimated_cost: float
    quality_tradeoff: float  # 0-1, 1=无质量损失
    reasoning: str
    alternatives: List[str] = field(default_factory=list)


class CostOptimizer:
    """
    成本优化引擎

    使用方式:
    ```python
    optimizer = CostOptimizer()

    # 设置预算
    optimizer.set_budget(daily=5.0, weekly=30.0)

    # 优化选择
    result = optimizer.optimize(
        task_type="reasoning",
        estimated_tokens=1000,
        min_quality=0.7
    )
    logger.info(f"推荐: {result.recommended_model}, 节省: ${result.estimated_cost}")
    ```
    """

    def __init__(
        self,
        default_daily: float = 5.0,
        default_weekly: float = 30.0,
        default_monthly: float = 100.0,
    ):
        # 预算配置
        self._budgets = {
            "daily": default_daily,
            "weekly": default_weekly,
            "monthly": default_monthly,
        }

        # 使用记录
        self._records: List[CostRecord] = []
        self._daily_records: Dict[str, List[CostRecord]] = defaultdict(list)

        # 成本模式
        self._mode = CostMode.FREE_PREFERRED

        # 回调
        self._on_budget_warning: Optional[Callable] = None
        self._on_budget_exceeded: Optional[Callable] = None

        # 锁
        self._lock = threading.RLock()

        # 模型定价
        self._pricing: Dict[str, Tuple[float, float]] = {}  # model_id -> (input_cost, output_cost) per 1M

        logger.info(f"[CostOptimizer] 已初始化 (daily=${default_daily}, weekly=${default_weekly})")

    def set_budget(self, daily: Optional[float] = None, weekly: Optional[float] = None, monthly: Optional[float] = None):
        """设置预算"""
        if daily is not None: self._budgets["daily"] = daily
        if weekly is not None: self._budgets["weekly"] = weekly
        if monthly is not None: self._budgets["monthly"] = monthly

    def set_mode(self, mode: CostMode):
        """设置成本模式"""
        self._mode = mode
        logger.info(f"[CostOptimizer] 模式切换: {mode.value}")

    def set_pricing(self, model_id: str, input_cost_per_m: float, output_cost_per_m: float):
        """设置模型定价"""
        self._pricing[model_id] = (input_cost_per_m, output_cost_per_m)

    def register_free_model(self, model_id: str):
        """注册免费模型"""
        self._pricing[model_id] = (0, 0)

    def can_afford(self, model_id: str, input_tokens: int, output_tokens: int, period: str = "daily") -> bool:
        """检查是否可以负担"""
        cost = self.calculate_cost(model_id, input_tokens, output_tokens)
        status = self.get_budget_status(period)
        return cost <= status.remaining

    def calculate_cost(self, model_id: str, input_tokens: int, output_tokens: int) -> float:
        """计算成本"""
        pricing = self._pricing.get(model_id, (0, 0))
        input_cost, output_cost = pricing
        return (input_tokens / 1_000_000) * input_cost + (output_tokens / 1_000_000) * output_cost

    def get_budget_status(self, period: str = "daily") -> BudgetStatus:
        """获取预算状态"""
        with self._lock:
            limit = self._budgets.get(period, 0)
            cutoff = self._get_period_start(period)

            used = sum(
                r.cost for r in self._records
                if r.timestamp >= cutoff and r.model_id in self._pricing
                and self._pricing[r.model_id] != (0, 0)
            )

            remaining = max(0, limit - used)
            usage_pct = (used / limit * 100) if limit > 0 else 0

            # 预测耗尽时间
            projected = None
            if used > 0 and remaining > 0:
                elapsed = time.time() - cutoff
                rate = used / elapsed  # 每秒消耗
                remaining_seconds = remaining / rate if rate > 0 else float('inf')
                projected = time.time() + remaining_seconds

            return BudgetStatus(
                period=period,
                limit=limit,
                used=used,
                remaining=remaining,
                usage_pct=usage_pct,
                projected_exhaustion=projected,
            )

    def optimize(
        self,
        task_type: str,
        estimated_tokens: int,
        min_quality: float = 0.5,
        preferred_model: Optional[str] = None,
    ) -> OptimizationResult:
        """优化模型选择"""
        with self._lock:
            candidates = []

            for model_id, pricing in self._pricing.items():
                input_cost, output_cost = pricing
                cost = (estimated_tokens / 1_000_000) * (input_cost + output_cost * 2)

                # 检查预算
                daily_status = self.get_budget_status("daily")
                if cost > daily_status.remaining and pricing != (0, 0):
                    continue

                # 估算质量
                quality = self._estimate_quality(model_id, task_type)

                # 质量必须满足最低要求
                if quality < min_quality:
                    continue

                # 计算性价比
                if cost == 0:
                    value_score = quality * 2  # 免费模型加权
                else:
                    value_score = quality / cost if cost > 0 else quality * 10

                candidates.append({
                    "model_id": model_id,
                    "cost": cost,
                    "quality": quality,
                    "value_score": value_score,
                    "is_free": cost == 0,
                })

            if not candidates:
                # 没有合适的选择，使用最便宜的
                cheapest = min(
                    [(m, c) for m, p in self._pricing.items() for c in [self.calculate_cost(m, estimated_tokens, estimated_tokens * 2)]],
                    key=lambda x: x[1],
                    default=(None, 0)
                )
                return OptimizationResult(
                    recommended_model=cheapest[0] or "unknown",
                    estimated_cost=cheapest[1],
                    quality_tradeoff=0.3,
                    reasoning="没有满足条件的选择，使用最便宜的",
                )

            # 排序
            if self._mode == CostMode.FREE_ONLY:
                candidates = [c for c in candidates if c["is_free"]]
            elif self._mode == CostMode.FREE_PREFERRED:
                candidates.sort(key=lambda x: (not x["is_free"], -x["value_score"]))
            elif self._mode == CostMode.QUALITY_FIRST:
                candidates.sort(key=lambda x: (-x["quality"], x["cost"]))
            else:  # BALANCED
                candidates.sort(key=lambda x: -x["value_score"])

            if not candidates:
                candidates = [c for c in candidates if c["is_free"]]

            best = candidates[0]
            alternatives = [c["model_id"] for c in candidates[1:4]]

            # 计算质量权衡
            max_quality = max(c["quality"] for c in candidates) if candidates else 1
            quality_tradeoff = best["quality"] / max_quality if max_quality > 0 else 1

            return OptimizationResult(
                recommended_model=best["model_id"],
                estimated_cost=best["cost"],
                quality_tradeoff=quality_tradeoff,
                reasoning=self._generate_reasoning(best, task_type),
                alternatives=alternatives,
            )

    def _estimate_quality(self, model_id: str, task_type: str) -> float:
        """估算模型在任务上的质量"""
        # 简化实现：基于任务类型估算
        quality_map = {
            "reasoning": {"qwen3.5:9b": 0.9, "qwen2.5:1.5b": 0.6, "qwen2.5:0.5b": 0.4},
            "code_generation": {"qwen3.5:9b": 0.9, "qwen2.5:1.5b": 0.7, "qwen2.5:0.5b": 0.5},
            "general": {"qwen3.5:9b": 0.85, "qwen2.5:1.5b": 0.7, "qwen2.5:0.5b": 0.5},
        }

        return quality_map.get(task_type, {}).get(model_id, 0.5)

    def _generate_reasoning(self, candidate: Dict, task_type: str) -> str:
        """生成推理"""
        if candidate["is_free"]:
            return f"选择免费模型 {candidate['model_id']}"
        return f"选择 {candidate['model_id']} (成本: ${candidate['cost']:.4f}, 质量: {candidate['quality']:.2f})"

    def record_usage(
        self,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        quality_score: float = 0,
    ):
        """记录使用"""
        cost = self.calculate_cost(model_id, input_tokens, output_tokens)

        record = CostRecord(
            timestamp=time.time(),
            model_id=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            quality_score=quality_score,
        )

        with self._lock:
            self._records.append(record)

            # 检查预算警告
            daily = self.get_budget_status("daily")
            if daily.usage_pct >= 80:
                if self._on_budget_warning:
                    self._on_budget_warning("daily", daily.usage_pct)

            if daily.remaining <= 0:
                if self._on_budget_exceeded:
                    self._on_budget_exceeded("daily")

    def get_savings_report(self, period: str = "weekly") -> Dict:
        """获取节省报告"""
        with self._lock:
            cutoff = self._get_period_start(period)
            period_records = [r for r in self._records if r.timestamp >= cutoff]

            if not period_records:
                return {"period": period, "total_cost": 0, "free_usage": 0, "savings": 0, "breakdown": {}}

            total_cost = sum(r.cost for r in period_records)
            free_cost = sum(r.cost for r in period_records if self._pricing.get(r.model_id) == (0, 0))

            # 如果全部用付费模型的成本估算
            hypothetical_cost = sum(
                (r.input_tokens + r.output_tokens) / 1_000_000 * 0.5  # 假设平均$0.5/1M
                for r in period_records
            )

            savings = hypothetical_cost - total_cost

            breakdown = defaultdict(float)
            for r in period_records:
                breakdown[r.model_id] += r.cost

            return {
                "period": period,
                "total_cost": total_cost,
                "free_usage": free_cost,
                "paid_usage": total_cost - free_cost,
                "savings": savings,
                "savings_rate": savings / hypothetical_cost if hypothetical_cost > 0 else 0,
                "breakdown": dict(breakdown),
                "record_count": len(period_records),
            }

    def get_optimization_tips(self) -> List[str]:
        """获取优化建议"""
        tips = []

        daily = self.get_budget_status("daily")
        if daily.usage_pct > 70:
            tips.append(f"日预算使用率{daily.usage_pct:.0%}，考虑使用更小的模型处理简单任务")

        # 检查是否有未使用的免费模型
        free_models = [m for m, p in self._pricing.items() if p == (0, 0)]
        if free_models:
            tips.append(f"可用的免费模型: {', '.join(free_models)}")

        return tips

    def _get_period_start(self, period: str) -> float:
        """获取周期开始时间"""
        now = time.localtime()

        if period == "daily":
            return time.mktime((now.tm_year, now.tm_mon, now.tm_mday, 0, 0, 0, 0, 0, 0))
        elif period == "weekly":
            week_start = now.tm_mday - now.tm_wday
            return time.mktime((now.tm_year, now.tm_mon, week_start, 0, 0, 0, 0, 0, 0))
        elif period == "monthly":
            return time.mktime((now.tm_year, now.tm_mon, 1, 0, 0, 0, 0, 0, 0))
        else:
            return 0

    def set_callbacks(
        self,
        on_warning: Callable = None,
        on_exceeded: Callable = None,
    ):
        """设置回调"""
        self._on_budget_warning = on_warning
        self._on_budget_exceeded = on_exceeded

    def get_stats(self) -> Dict:
        """获取统计"""
        with self._lock:
            total = sum(r.cost for r in self._records)
            return {
                "total_cost": total,
                "total_records": len(self._records),
                "mode": self._mode.value,
                "budgets": self._budgets,
                "registered_models": len(self._pricing),
            }


# ═══════════════════════════════════════════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("成本优化引擎测试")
    logger.info("=" * 60)

    optimizer = CostOptimizer(default_daily=5.0)

    # 注册模型
    optimizer.set_pricing("qwen3.5:9b", 0, 0)  # 免费
    optimizer.set_pricing("gpt-4o", 2.5, 10.0)  # 收费

    logger.info("\n[Test 1: 预算状态]")
    status = optimizer.get_budget_status("daily")
    logger.info(f"  日预算: ${status.limit}")
    logger.info(f"  已使用: ${status.used:.4f}")
    logger.info(f"  剩余: ${status.remaining:.4f}")
    logger.info(f"  使用率: {status.usage_pct:.1f}%")

    logger.info("\n[Test 2: 优化选择]")
    result = optimizer.optimize("reasoning", estimated_tokens=1000, min_quality=0.5)
    logger.info(f"  推荐: {result.recommended_model}")
    logger.info(f"  成本: ${result.estimated_cost:.4f}")
    logger.info(f"  质量权衡: {result.quality_tradeoff:.2f}")
    logger.info(f"  推理: {result.reasoning}")

    logger.info("\n[Test 3: 记录使用]")
    optimizer.record_usage("qwen3.5:9b", 100, 200, 0.9)
    optimizer.record_usage("gpt-4o", 50, 100, 0.95)
    status = optimizer.get_budget_status("daily")
    logger.info(f"  记录后已使用: ${status.used:.4f}")

    logger.info("\n[Test 4: 节省报告]")
    report = optimizer.get_savings_report("daily")
    logger.info(f"  总成本: ${report['total_cost']:.4f}")
    logger.info(f"  节省: ${report['savings']:.4f}")

    logger.info("\n" + "=" * 60)
