"""
成本管理器 (Cost Manager)
========================

集成 Anthropic Pricing，实现：
1. 成本估算 - 根据Token数估算API调用成本
2. 预算控制 - 设置和管理API调用预算
3. 成本监控 - 实时监控API调用成本
4. 优化建议 - 基于成本数据提供优化建议

核心特性：
- 支持多种模型定价
- 实时成本计算
- 预算预警
- 成本分析和报告

参考项目：https://docs.anthropic.com/en/docs/about-claude/pricing

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = __import__('logging').getLogger(__name__)


class ModelType(Enum):
    """模型类型"""
    CLAUDE_3_OPUS = "claude-3-opus"
    CLAUDE_3_SONNET = "claude-3-sonnet"
    CLAUDE_3_HAIKU = "claude-3-haiku"
    CLAUDE_2_1 = "claude-2.1"
    CLAUDE_2 = "claude-2"


@dataclass
class PricingInfo:
    """定价信息"""
    model: ModelType
    input_price_per_million: float  # 每百万输入Token价格（美元）
    output_price_per_million: float  # 每百万输出Token价格（美元）
    context_window: int  # 上下文窗口大小
    description: str = ""


@dataclass
class CostRecord:
    """成本记录"""
    id: str
    model: ModelType
    input_tokens: int
    output_tokens: int
    cost: float
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Budget:
    """预算设置"""
    name: str
    limit: float  # 预算限额（美元）
    period: str  # 周期：daily, weekly, monthly
    used: float = 0.0
    last_reset: float = 0.0


@dataclass
class CostStats:
    """成本统计"""
    total_cost: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    total_calls: int = 0
    today_cost: float = 0.0
    weekly_cost: float = 0.0
    monthly_cost: float = 0.0
    model_breakdown: Dict[str, float] = field(default_factory=dict)


class CostManager:
    """
    成本管理器
    
    核心功能：
    1. 成本估算 - 根据Token数估算API调用成本
    2. 预算控制 - 设置和管理API调用预算
    3. 成本监控 - 实时监控API调用成本
    4. 优化建议 - 基于成本数据提供优化建议
    
    参考项目：https://docs.anthropic.com/en/docs/about-claude/pricing
    
    定价数据（2026年价格，实际使用时请更新）：
    - Claude 3 Opus: $15/百万输入Token, $75/百万输出Token
    - Claude 3 Sonnet: $3/百万输入Token, $15/百万输出Token
    - Claude 3 Haiku: $0.25/百万输入Token, $1.25/百万输出Token
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # 定价数据（基于Anthropic官方定价）
        self._pricing: Dict[ModelType, PricingInfo] = {
            ModelType.CLAUDE_3_OPUS: PricingInfo(
                model=ModelType.CLAUDE_3_OPUS,
                input_price_per_million=15.0,
                output_price_per_million=75.0,
                context_window=200000,
                description="最强大的模型，适合复杂任务"
            ),
            ModelType.CLAUDE_3_SONNET: PricingInfo(
                model=ModelType.CLAUDE_3_SONNET,
                input_price_per_million=3.0,
                output_price_per_million=15.0,
                context_window=200000,
                description="平衡性能和成本，适合大多数任务"
            ),
            ModelType.CLAUDE_3_HAIKU: PricingInfo(
                model=ModelType.CLAUDE_3_HAIKU,
                input_price_per_million=0.25,
                output_price_per_million=1.25,
                context_window=200000,
                description="最快最经济的模型，适合简单任务"
            ),
            ModelType.CLAUDE_2_1: PricingInfo(
                model=ModelType.CLAUDE_2_1,
                input_price_per_million=8.0,
                output_price_per_million=24.0,
                context_window=200000,
                description="Claude 2.1，适合较长上下文"
            ),
            ModelType.CLAUDE_2: PricingInfo(
                model=ModelType.CLAUDE_2,
                input_price_per_million=8.0,
                output_price_per_million=24.0,
                context_window=100000,
                description="原版Claude 2"
            ),
        }
        
        # 成本记录
        self._records: List[CostRecord] = []
        
        # 预算设置
        self._budgets: Dict[str, Budget] = {
            "daily": Budget(
                name="daily",
                limit=10.0,
                period="daily",
                last_reset=time.time()
            ),
            "weekly": Budget(
                name="weekly",
                limit=50.0,
                period="weekly",
                last_reset=time.time()
            ),
            "monthly": Budget(
                name="monthly",
                limit=200.0,
                period="monthly",
                last_reset=time.time()
            ),
        }
        
        # 配置参数
        self._config = {
            "enabled": True,
            "budget_warning_threshold": 0.8,  # 预算警告阈值（80%）
            "auto_switch_model": False,  # 自动切换模型以节约成本
        }
        
        self._initialized = True
        logger.info("[CostManager] 成本管理器初始化完成")
    
    def configure(self, **kwargs):
        """配置成本管理器"""
        self._config.update(kwargs)
        logger.info(f"[CostManager] 配置更新: {kwargs}")
    
    def calculate_cost(self, input_tokens: int, output_tokens: int, 
                       model: ModelType) -> float:
        """
        计算API调用成本
        
        Args:
            input_tokens: 输入Token数
            output_tokens: 输出Token数
            model: 模型类型
            
        Returns:
            成本（美元）
        """
        pricing = self._pricing.get(model)
        if not pricing:
            logger.warning(f"[CostManager] 未知模型: {model}")
            return 0.0
        
        input_cost = (input_tokens * pricing.input_price_per_million) / 1_000_000
        output_cost = (output_tokens * pricing.output_price_per_million) / 1_000_000
        
        return input_cost + output_cost
    
    def estimate_cost(self, prompt: str, model: ModelType, 
                      estimated_output_tokens: int = 500) -> float:
        """
        估算API调用成本
        
        Args:
            prompt: 提示词
            model: 模型类型
            estimated_output_tokens: 预估输出Token数
            
        Returns:
            预估成本（美元）
        """
        input_tokens = self._count_tokens(prompt)
        return self.calculate_cost(input_tokens, estimated_output_tokens, model)
    
    def record_call(self, model: ModelType, input_tokens: int, 
                    output_tokens: int, **metadata):
        """
        记录API调用
        
        Args:
            model: 模型类型
            input_tokens: 输入Token数
            output_tokens: 输出Token数
            **metadata: 额外元数据
        """
        cost = self.calculate_cost(input_tokens, output_tokens, model)
        
        record = CostRecord(
            id=f"cost_{int(time.time())}_{len(self._records)}",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            timestamp=time.time(),
            metadata=metadata
        )
        
        self._records.append(record)
        
        # 更新预算使用
        self._update_budgets(cost)
        
        # 检查预算警告
        self._check_budget_warnings()
        
        logger.debug(f"[CostManager] 记录调用: {model.value}, 成本: ${cost:.4f}")
    
    def get_stats(self) -> CostStats:
        """获取成本统计信息"""
        now = time.time()
        today_start = self._get_period_start("daily", now)
        week_start = self._get_period_start("weekly", now)
        month_start = self._get_period_start("monthly", now)
        
        stats = CostStats()
        model_breakdown = {}
        
        for record in self._records:
            stats.total_cost += record.cost
            stats.input_tokens += record.input_tokens
            stats.output_tokens += record.output_tokens
            stats.total_calls += 1
            
            # 按时间周期统计
            if record.timestamp >= today_start:
                stats.today_cost += record.cost
            if record.timestamp >= week_start:
                stats.weekly_cost += record.cost
            if record.timestamp >= month_start:
                stats.monthly_cost += record.cost
            
            # 按模型统计
            model_key = record.model.value
            model_breakdown[model_key] = model_breakdown.get(model_key, 0.0) + record.cost
        
        stats.model_breakdown = model_breakdown
        
        return stats
    
    def get_budgets(self) -> Dict[str, Budget]:
        """获取所有预算设置"""
        return self._budgets
    
    def get_budget_status(self, budget_name: str) -> Dict[str, Any]:
        """获取指定预算状态"""
        budget = self._budgets.get(budget_name)
        if not budget:
            return {"error": "预算不存在"}
        
        usage_percent = (budget.used / budget.limit) * 100
        remaining = budget.limit - budget.used
        
        return {
            "name": budget.name,
            "limit": budget.limit,
            "used": budget.used,
            "remaining": remaining,
            "usage_percent": usage_percent,
            "period": budget.period,
            "last_reset": budget.last_reset,
        }
    
    def reset_budget(self, budget_name: str):
        """重置指定预算"""
        budget = self._budgets.get(budget_name)
        if budget:
            budget.used = 0.0
            budget.last_reset = time.time()
            logger.info(f"[CostManager] 重置预算: {budget_name}")
    
    def get_optimization_suggestions(self) -> List[str]:
        """获取成本优化建议"""
        suggestions = []
        stats = self.get_stats()
        
        # 检查是否使用了昂贵的模型
        if stats.model_breakdown.get("claude-3-opus", 0) > stats.total_cost * 0.5:
            suggestions.append("建议：考虑将部分任务迁移到 Claude 3 Sonnet 或 Haiku，可显著降低成本")
        
        # 检查输出Token是否过多
        if stats.output_tokens > stats.input_tokens * 2:
            suggestions.append("建议：优化输出格式，减少不必要的输出内容")
        
        # 检查预算使用情况
        for budget_name, budget in self._budgets.items():
            usage = budget.used / budget.limit
            if usage > 0.8:
                suggestions.append(f"警告：{budget_name} 预算已使用 {usage:.1%}")
        
        # 如果没有特殊建议，提供通用建议
        if not suggestions:
            suggestions.append("当前成本使用正常，继续保持优化的提示词使用习惯")
        
        return suggestions
    
    def suggest_model(self, complexity: str = "medium") -> ModelType:
        """
        根据任务复杂度建议模型
        
        Args:
            complexity: 任务复杂度 (simple/medium/complex)
            
        Returns:
            推荐的模型类型
        """
        model_map = {
            "simple": ModelType.CLAUDE_3_HAIKU,
            "medium": ModelType.CLAUDE_3_SONNET,
            "complex": ModelType.CLAUDE_3_OPUS,
        }
        return model_map.get(complexity, ModelType.CLAUDE_3_SONNET)
    
    def get_pricing_info(self, model: ModelType) -> Optional[PricingInfo]:
        """获取模型定价信息"""
        return self._pricing.get(model)
    
    def get_all_pricing(self) -> Dict[str, Dict[str, Any]]:
        """获取所有模型定价信息"""
        result = {}
        for model, pricing in self._pricing.items():
            result[model.value] = {
                "input_price_per_million": pricing.input_price_per_million,
                "output_price_per_million": pricing.output_price_per_million,
                "context_window": pricing.context_window,
                "description": pricing.description,
            }
        return result
    
    # ========== 私有方法 ==========
    
    def _count_tokens(self, text: str) -> int:
        """估算Token数"""
        if not text:
            return 0
        
        english_words = len([w for w in text.split() if w.isalpha()])
        chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
        
        return english_words + int(chinese_chars * 0.5)
    
    def _get_period_start(self, period: str, now: float) -> float:
        """获取周期开始时间"""
        import datetime
        
        dt = datetime.datetime.fromtimestamp(now)
        
        if period == "daily":
            return datetime.datetime(dt.year, dt.month, dt.day).timestamp()
        elif period == "weekly":
            # 周一为一周开始
            monday = dt - datetime.timedelta(days=dt.weekday())
            return datetime.datetime(monday.year, monday.month, monday.day).timestamp()
        elif period == "monthly":
            return datetime.datetime(dt.year, dt.month, 1).timestamp()
        
        return now
    
    def _update_budgets(self, cost: float):
        """更新预算使用"""
        now = time.time()
        
        for budget in self._budgets.values():
            # 检查是否需要重置
            period_start = self._get_period_start(budget.period, now)
            if budget.last_reset < period_start:
                budget.used = 0.0
                budget.last_reset = now
            
            budget.used += cost
    
    def _check_budget_warnings(self):
        """检查预算警告"""
        threshold = self._config["budget_warning_threshold"]
        
        for budget_name, budget in self._budgets.items():
            usage = budget.used / budget.limit
            if usage >= threshold and usage < 1.0:
                logger.warning(f"[CostManager] {budget_name} 预算已使用 {usage:.1%}")
            elif usage >= 1.0:
                logger.error(f"[CostManager] {budget_name} 预算已用尽！")


# 便捷函数
def get_cost_manager() -> CostManager:
    """获取成本管理器单例"""
    return CostManager()


__all__ = [
    "ModelType",
    "PricingInfo",
    "CostRecord",
    "Budget",
    "CostStats",
    "CostManager",
    "get_cost_manager",
]