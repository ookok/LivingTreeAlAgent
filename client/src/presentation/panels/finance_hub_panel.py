#!/usr/bin/env python3
"""
金融面板 - FinanceHubPanel
Phase 3: 领域面板 - 统一的金融管理界面

功能模块：
- 资产总览 (Dashboard)
- 投资中心 (股票/期货)
- 支付中心
- 积分中心
- 项目财务
- 经济分析

Author: LivingTreeAI Team
Version: 1.0.0
"""

from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import json


class PanelTab(Enum):
    """面板选项卡"""
    DASHBOARD = "dashboard"       # 总览
    INVESTMENT = "investment"      # 投资
    PAYMENT = "payment"           # 支付
    CREDIT = "credit"             # 积分
    PROJECT = "project"           # 项目财务
    ECONOMICS = "economics"      # 经济分析


@dataclass
class AssetSummary:
    """资产摘要"""
    total_assets: float = 0.0
    total_liabilities: float = 0.0
    net_assets: float = 0.0
    daily_change: float = 0.0
    daily_change_rate: float = 0.0
    assets_breakdown: Dict[str, float] = None
    
    def __post_init__(self):
        if self.assets_breakdown is None:
            self.assets_breakdown = {}


@dataclass
class InvestmentPosition:
    """投资持仓"""
    symbol: str
    name: str
    quantity: float
    cost: float
    current_price: float
    market_value: float
    profit_loss: float
    profit_loss_rate: float
    asset_type: str = "stock"


@dataclass
class Transaction:
    """交易记录"""
    id: str
    type: str  # deposit/withdraw/transfer/payment
    amount: float
    currency: str
    status: str
    timestamp: float
    description: str = ""


class DashboardWidget:
    """总览组件"""
    
    def __init__(self):
        self.total_assets = 0.0
        self.total_liabilities = 0.0
        self.net_assets = 0.0
        self.daily_change = 0.0
        self.daily_change_rate = 0.0
        self.assets_breakdown: Dict[str, float] = {}
        self.recent_transactions: List[Transaction] = []
        self.alerts: List[str] = []
    
    def get_summary(self) -> AssetSummary:
        """获取资产摘要"""
        return AssetSummary(
            total_assets=self.total_assets,
            total_liabilities=self.total_liabilities,
            net_assets=self.net_assets,
            daily_change=self.daily_change,
            daily_change_rate=self.daily_change_rate,
            assets_breakdown=self.assets_breakdown,
        )
    
    def get_assets_chart_data(self) -> Dict[str, Any]:
        """获取资产图表数据"""
        return {
            "type": "pie",
            "data": {
                "labels": list(self.assets_breakdown.keys()),
                "values": list(self.assets_breakdown.values()),
            },
            "options": {
                "title": "资产分布",
                "colors": ["#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", "#9966FF"],
            }
        }
    
    def add_alert(self, message: str) -> None:
        """添加告警"""
        self.alerts.append(message)
    
    def clear_alerts(self) -> None:
        """清除告警"""
        self.alerts.clear()


class InvestmentWidget:
    """投资中心组件"""
    
    def __init__(self):
        self.positions: List[InvestmentPosition] = []
        self.watchlist: List[str] = []
        self.order_history: List[Dict] = []
    
    def add_position(self, position: InvestmentPosition) -> None:
        """添加持仓"""
        self.positions.append(position)
    
    def remove_position(self, symbol: str) -> bool:
        """移除持仓"""
        for i, pos in enumerate(self.positions):
            if pos.symbol == symbol:
                self.positions.pop(i)
                return True
        return False
    
    def get_total_market_value(self) -> float:
        """获取总市值"""
        return sum(pos.market_value for pos in self.positions)
    
    def get_total_profit_loss(self) -> float:
        """获取总盈亏"""
        return sum(pos.profit_loss for pos in self.positions)
    
    def get_portfolio_performance(self) -> Dict[str, Any]:
        """获取组合表现"""
        total_cost = sum(pos.cost * pos.quantity for pos in self.positions)
        total_value = sum(pos.market_value for pos in self.positions)
        total_pl = total_value - total_cost
        
        return {
            "total_cost": total_cost,
            "total_value": total_value,
            "profit_loss": total_pl,
            "profit_loss_rate": (total_pl / total_cost * 100) if total_cost > 0 else 0,
            "positions_count": len(self.positions),
        }
    
    def add_to_watchlist(self, symbol: str) -> None:
        """添加到自选"""
        if symbol not in self.watchlist:
            self.watchlist.append(symbol)
    
    def remove_from_watchlist(self, symbol: str) -> bool:
        """从自选移除"""
        if symbol in self.watchlist:
            self.watchlist.remove(symbol)
            return True
        return False


class PaymentWidget:
    """支付中心组件"""
    
    def __init__(self):
        self.balance: float = 0.0
        self.currency: str = "CNY"
        self.payment_methods: List[Dict[str, Any]] = []
        self.transactions: List[Transaction] = []
    
    def deposit(self, amount: float, method: str = "bank") -> Transaction:
        """存款"""
        self.balance += amount
        txn = Transaction(
            id=f"dep_{len(self.transactions)}",
            type="deposit",
            amount=amount,
            currency=self.currency,
            status="completed",
            timestamp=0,  # 实际使用时间戳
            description=f"存款 - {method}",
        )
        self.transactions.append(txn)
        return txn
    
    def withdraw(self, amount: float, method: str = "bank") -> Optional[Transaction]:
        """取款"""
        if amount > self.balance:
            return None
        
        self.balance -= amount
        txn = Transaction(
            id=f"wd_{len(self.transactions)}",
            type="withdraw",
            amount=-amount,
            currency=self.currency,
            status="completed",
            timestamp=0,
            description=f"取款 - {method}",
        )
        self.transactions.append(txn)
        return txn
    
    def transfer(self, to: str, amount: float) -> Optional[Transaction]:
        """转账"""
        if amount > self.balance:
            return None
        
        self.balance -= amount
        txn = Transaction(
            id=f"tr_{len(self.transactions)}",
            type="transfer",
            amount=-amount,
            currency=self.currency,
            status="completed",
            timestamp=0,
            description=f"转账至 {to}",
        )
        self.transactions.append(txn)
        return txn
    
    def get_transaction_history(
        self,
        limit: int = 10,
        tx_type: Optional[str] = None,
    ) -> List[Transaction]:
        """获取交易历史"""
        result = self.transactions
        
        if tx_type:
            result = [t for t in result if t.type == tx_type]
        
        return sorted(result, key=lambda x: x.timestamp, reverse=True)[:limit]


class CreditWidget:
    """积分中心组件"""
    
    def __init__(self):
        self.total_credits: float = 0.0
        self.credit_history: List[Dict[str, Any]] = []
        self.credit_rules: Dict[str, float] = {}
    
    def add_credits(self, amount: float, source: str, description: str = "") -> None:
        """添加积分"""
        self.total_credits += amount
        self.credit_history.append({
            "type": "add",
            "amount": amount,
            "source": source,
            "description": description,
            "balance": self.total_credits,
        })
    
    def deduct_credits(self, amount: float, reason: str) -> bool:
        """扣除积分"""
        if amount > self.total_credits:
            return False
        
        self.total_credits -= amount
        self.credit_history.append({
            "type": "deduct",
            "amount": amount,
            "reason": reason,
            "balance": self.total_credits,
        })
        return True
    
    def get_credit_summary(self) -> Dict[str, Any]:
        """获取积分摘要"""
        return {
            "total": self.total_credits,
            "transactions": len(self.credit_history),
            "average_per_day": self._calculate_average(),
        }
    
    def _calculate_average(self) -> float:
        """计算日均积分"""
        if not self.credit_history:
            return 0.0
        
        # 简化计算
        return self.total_credits / max(len(self.credit_history), 1)


class ProjectFinanceWidget:
    """项目财务组件"""
    
    def __init__(self):
        self.projects: Dict[str, Dict[str, Any]] = {}
        self.budgets: Dict[str, float] = {}
        self.expenses: Dict[str, float] = {}
    
    def add_project(self, project_id: str, name: str, budget: float) -> None:
        """添加项目"""
        self.projects[project_id] = {
            "id": project_id,
            "name": name,
            "budget": budget,
            "status": "active",
        }
        self.budgets[project_id] = budget
        self.expenses[project_id] = 0.0
    
    def add_expense(self, project_id: str, amount: float, description: str = "") -> bool:
        """添加支出"""
        if project_id not in self.projects:
            return False
        
        self.expenses[project_id] += amount
        return True
    
    def get_project_status(self, project_id: str) -> Dict[str, Any]:
        """获取项目状态"""
        if project_id not in self.projects:
            return {}
        
        budget = self.budgets[project_id]
        expense = self.expenses[project_id]
        remaining = budget - expense
        
        return {
            "project_id": project_id,
            "budget": budget,
            "expense": expense,
            "remaining": remaining,
            "usage_rate": (expense / budget * 100) if budget > 0 else 0,
            "status": "over_budget" if remaining < 0 else "normal",
        }
    
    def get_all_projects_summary(self) -> Dict[str, Any]:
        """获取所有项目摘要"""
        total_budget = sum(self.budgets.values())
        total_expense = sum(self.expenses.values())
        
        return {
            "total_projects": len(self.projects),
            "total_budget": total_budget,
            "total_expense": total_expense,
            "total_remaining": total_budget - total_expense,
            "usage_rate": (total_expense / total_budget * 100) if total_budget > 0 else 0,
        }


class EconomicsWidget:
    """经济分析组件"""
    
    def __init__(self):
        self.economic_indicators: Dict[str, float] = {}
        self.historical_data: List[Dict[str, Any]] = []
    
    def update_indicator(self, name: str, value: float) -> None:
        """更新经济指标"""
        self.economic_indicators[name] = value
    
    def get_indicator_summary(self) -> Dict[str, Any]:
        """获取指标摘要"""
        return {
            "indicators": self.economic_indicators,
            "total_indicators": len(self.economic_indicators),
            "last_updated": "now",
        }
    
    def add_historical_data(self, data: Dict[str, Any]) -> None:
        """添加历史数据"""
        self.historical_data.append(data)
    
    def get_trend_analysis(self, indicator: str, periods: int = 30) -> Dict[str, Any]:
        """获取趋势分析"""
        filtered = [
            d for d in self.historical_data
            if indicator in d
        ][-periods:]
        
        if not filtered:
            return {"trend": "no_data", "values": []}
        
        values = [d[indicator] for d in filtered]
        return {
            "indicator": indicator,
            "values": values,
            "average": sum(values) / len(values),
            "max": max(values),
            "min": min(values),
        }


class FinanceHubPanel:
    """
    统一金融面板
    
    整合所有金融相关模块：
    - 资产总览
    - 投资中心
    - 支付中心
    - 积分中心
    - 项目财务
    - 经济分析
    """
    
    def __init__(self):
        # 初始化所有组件
        self.dashboard = DashboardWidget()
        self.investment = InvestmentWidget()
        self.payment = PaymentWidget()
        self.credit = CreditWidget()
        self.project_finance = ProjectFinanceWidget()
        self.economics = EconomicsWidget()
        
        # 当前选中的选项卡
        self.current_tab = PanelTab.DASHBOARD
        
        # 事件回调
        self._event_handlers: Dict[str, List[Callable]] = {
            "transaction": [],
            "alert": [],
            "update": [],
        }
    
    def switch_tab(self, tab: PanelTab) -> None:
        """
        切换选项卡
        
        Args:
            tab: 选项卡
        """
        self.current_tab = tab
        self._emit_event("update", {"tab": tab.value})
    
    def get_overall_summary(self) -> Dict[str, Any]:
        """
        获取整体摘要
        
        Returns:
            整体财务摘要
        """
        return {
            "assets": self.dashboard.get_summary().__dict__,
            "investment": self.investment.get_portfolio_performance(),
            "payment": {
                "balance": self.payment.balance,
                "currency": self.payment.currency,
            },
            "credits": self.credit.get_credit_summary(),
            "projects": self.project_finance.get_all_projects_summary(),
            "economics": self.economics.get_indicator_summary(),
        }
    
    def get_widget(self, tab: PanelTab) -> Any:
        """
        获取指定组件
        
        Args:
            tab: 选项卡
            
        Returns:
            对应组件
        """
        widgets = {
            PanelTab.DASHBOARD: self.dashboard,
            PanelTab.INVESTMENT: self.investment,
            PanelTab.PAYMENT: self.payment,
            PanelTab.CREDIT: self.credit,
            PanelTab.PROJECT: self.project_finance,
            PanelTab.ECONOMICS: self.economics,
        }
        return widgets.get(tab)
    
    def on_event(self, event_type: str, handler: Callable) -> None:
        """注册事件处理"""
        if event_type in self._event_handlers:
            self._event_handlers[event_type].append(handler)
    
    def _emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """触发事件"""
        for handler in self._event_handlers.get(event_type, []):
            try:
                handler(data)
            except Exception:
                pass
    
    def export_data(self) -> str:
        """
        导出数据
        
        Returns:
            JSON格式数据
        """
        return json.dumps(self.get_overall_summary(), indent=2, ensure_ascii=False)
    
    def import_data(self, json_str: str) -> bool:
        """
        导入数据
        
        Args:
            json_str: JSON字符串
            
        Returns:
            是否成功
        """
        try:
            data = json.loads(json_str)
            # 应用数据
            return True
        except Exception:
            return False


# 全局面板实例
_global_panel: Optional[FinanceHubPanel] = None


def get_finance_hub_panel() -> FinanceHubPanel:
    """获取全局金融面板实例"""
    global _global_panel
    
    if _global_panel is None:
        _global_panel = FinanceHubPanel()
    
    return _global_panel
