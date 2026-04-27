#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
Version: 1.1.0
"""

from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import json
import time

# PyQt6 导入
try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
        QLabel, QPushButton, QTabWidget, QTableWidget, QTableWidgetItem,
        QHeaderView, QGroupBox, QFormLayout, QProgressBar,
        QComboBox, QLineEdit, QDoubleSpinBox, QMessageBox,
        QDateEdit, QTextEdit, QSplitter, QFrame,
    )
    from PyQt6.QtCore import (
        Qt, QTimer, pyqtSignal, QDate, QSize,
    )
    from PyQt6.QtGui import QFont, QIcon, QPalette, QColor
    HAS_PYQT = True
except ImportError:
    HAS_PYQT = False


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
            timestamp=time.time(),
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
            timestamp=time.time(),
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
            timestamp=time.time(),
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
    

# ────────────────────────────────────────────────────────
# PyQt6 UI 层
# ────────────────────────────────────────────────────────

if HAS_PYQT:
    class FinanceHubPanelUI(QWidget):
        """
        FinanceHub 主面板 UI
        
        整合所有金融模块的可视化界面。
        """
        
        # 信号
        tab_changed = pyqtSignal(str)
        transaction_created = pyqtSignal(dict)
        
        def __init__(self, parent: Optional[QWidget] = None):
            super().__init__(parent)
            self._panel = FinanceHubPanel()
            self._current_tab = PanelTab.DASHBOARD
            self._init_ui()
            self._init_mock_data()
            self._update_ui()
        
        def _init_ui(self) -> None:
            """初始化 UI"""
            layout = QVBoxLayout(self)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(8)
            
            # 标题
            title = QLabel("💰 金融中心")
            font = QFont()
            font.setPointSize(16)
            font.setBold(True)
            title.setFont(font)
            layout.addWidget(title)
            
            # 选项卡
            self._tabs = QTabWidget()
            self._tabs.currentChanged.connect(self._on_tab_changed)
            
            # Dashboard 选项卡
            self._dashboard_widget = self._create_dashboard_tab()
            self._tabs.addTab(self._dashboard_widget, "📊 总览")
            
            # 投资选项卡
            self._investment_widget = self._create_investment_tab()
            self._tabs.addTab(self._investment_widget, "📈 投资")
            
            # 支付选项卡
            self._payment_widget = self._create_payment_tab()
            self._tabs.addTab(self._payment_widget, "💳 支付")
            
            # 积分选项卡
            self._credit_widget = self._create_credit_tab()
            self._tabs.addTab(self._credit_widget, "🎁 积分")
            
            # 项目财务选项卡
            self._project_widget = self._create_project_tab()
            self._tabs.addTab(self._project_widget, "📁 项目")
            
            # 经济分析选项卡
            self._economics_widget = self._create_economics_tab()
            self._tabs.addTab(self._economics_widget, "📊 经济")
            
            layout.addWidget(self._tabs)
            
            # 状态栏
            self._status_bar = QLabel("就绪")
            self._status_bar.setStyleSheet("color: #666; font-size: 12px;")
            layout.addWidget(self._status_bar)
        
        def _create_dashboard_tab(self) -> QWidget:
            """创建总览选项卡"""
            widget = QWidget()
            layout = QVBoxLayout(widget)
            layout.setContentsMargins(8, 8, 8, 8)
            
            # 资产卡片
            cards_layout = QHBoxLayout()
            
            # 总资产
            self._total_assets_card = self._create_value_card("总资产", "¥0.00", "#4CAF50")
            cards_layout.addWidget(self._total_assets_card)
            
            # 负债
            self._total_liabilities_card = self._create_value_card("总负债", "¥0.00", "#F44336")
            cards_layout.addWidget(self._total_liabilities_card)
            
            # 净资产
            self._net_assets_card = self._create_value_card("净资产", "¥0.00", "#2196F3")
            cards_layout.addWidget(self._net_assets_card)
            
            # 日收益
            self._daily_change_card = self._create_value_card("日收益", "+¥0.00", "#FF9800")
            cards_layout.addWidget(self._daily_change_card)
            
            layout.addLayout(cards_layout)
            
            # 资产分布（占位）
            dist_group = QGroupBox("资产分布")
            dist_layout = QVBoxLayout(dist_group)
            dist_layout.addWidget(QLabel("（图表组件待集成）"))
            layout.addWidget(dist_group)
            
            # 最近交易
            recent_group = QGroupBox("最近交易")
            recent_layout = QVBoxLayout(recent_group)
            self._recent_transactions_table = QTableWidget()
            self._recent_transactions_table.setColumnCount(4)
            self._recent_transactions_table.setHorizontalHeaderLabels(["时间", "类型", "金额", "描述"])
            self._recent_transactions_table.horizontalHeader().setStretchLastSection(True)
            recent_layout.addWidget(self._recent_transactions_table)
            layout.addWidget(recent_group)
            
            layout.addStretch()
            return widget
        
        def _create_investment_tab(self) -> QWidget:
            """创建投资选项卡"""
            widget = QWidget()
            layout = QVBoxLayout(widget)
            layout.setContentsMargins(8, 8, 8, 8)
            
            # 持仓列表
            positions_group = QGroupBox("当前持仓")
            positions_layout = QVBoxLayout(positions_group)
            self._positions_table = QTableWidget()
            self._positions_table.setColumnCount(7)
            self._positions_table.setHorizontalHeaderLabels(["代码", "名称", "数量", "成本", "现价", "市值", "盈亏"])
            self._positions_table.horizontalHeader().setStretchLastSection(True)
            positions_layout.addWidget(self._positions_table)
            layout.addWidget(positions_group)
            
            # 操作按钮
            btn_layout = QHBoxLayout()
            buy_btn = QPushButton("买入")
            sell_btn = QPushButton("卖出")
            refresh_btn = QPushButton("刷新")
            btn_layout.addWidget(buy_btn)
            btn_layout.addWidget(sell_btn)
            btn_layout.addStretch()
            btn_layout.addWidget(refresh_btn)
            layout.addLayout(btn_layout)
            
            # 组合表现
            perf_group = QGroupBox("组合表现")
            perf_layout = QFormLayout(perf_group)
            self._total_cost_label = QLabel("¥0.00")
            self._total_value_label = QLabel("¥0.00")
            self._total_pl_label = QLabel("¥0.00")
            self._total_pl_rate_label = QLabel("0.00%")
            perf_layout.addRow("总成本：", self._total_cost_label)
            perf_layout.addRow("总市值：", self._total_value_label)
            perf_layout.addRow("总盈亏：", self._total_pl_label)
            perf_layout.addRow("盈亏率：", self._total_pl_rate_label)
            layout.addWidget(perf_group)
            
            layout.addStretch()
            return widget
        
        def _create_payment_tab(self) -> QWidget:
            """创建支付选项卡"""
            widget = QWidget()
            layout = QVBoxLayout(widget)
            layout.setContentsMargins(8, 8, 8, 8)
            
            # 余额显示
            balance_layout = QHBoxLayout()
            balance_label = QLabel("当前余额：")
            self._balance_label = QLabel("¥0.00")
            font = QFont()
            font.setPointSize(24)
            font.setBold(True)
            self._balance_label.setFont(font)
            self._balance_label.setStyleSheet("color: #4CAF50;")
            balance_layout.addWidget(balance_label)
            balance_layout.addWidget(self._balance_label)
            balance_layout.addStretch()
            layout.addLayout(balance_layout)
            
            # 操作区
            op_group = QGroupBox("操作")
            op_layout = QHBoxLayout(op_group)
            deposit_btn = QPushButton("存款")
            withdraw_btn = QPushButton("取款")
            transfer_btn = QPushButton("转账")
            op_layout.addWidget(deposit_btn)
            op_layout.addWidget(withdraw_btn)
            op_layout.addWidget(transfer_btn)
            op_layout.addStretch()
            layout.addWidget(op_group)
            
            # 交易历史
            history_group = QGroupBox("交易历史")
            history_layout = QVBoxLayout(history_group)
            self._payment_history_table = QTableWidget()
            self._payment_history_table.setColumnCount(5)
            self._payment_history_table.setHorizontalHeaderLabels(["ID", "类型", "金额", "状态", "时间"])
            self._payment_history_table.horizontalHeader().setStretchLastSection(True)
            history_layout.addWidget(self._payment_history_table)
            layout.addWidget(history_group)
            
            layout.addStretch()
            return widget
        
        def _create_credit_tab(self) -> QWidget:
            """创建积分选项卡"""
            widget = QWidget()
            layout = QVBoxLayout(widget)
            layout.setContentsMargins(8, 8, 8, 8)
            
            # 积分余额
            balance_layout = QHBoxLayout()
            balance_label = QLabel("积分余额：")
            self._credit_balance_label = QLabel("0")
            font = QFont()
            font.setPointSize(24)
            font.setBold(True)
            self._credit_balance_label.setFont(font)
            self._credit_balance_label.setStyleSheet("color: #FF9800;")
            balance_layout.addWidget(balance_label)
            balance_layout.addWidget(self._credit_balance_label)
            balance_layout.addStretch()
            layout.addLayout(balance_layout)
            
            # 操作区
            op_group = QGroupBox("操作")
            op_layout = QHBoxLayout(op_group)
            add_btn = QPushButton("增加积分")
            deduct_btn = QPushButton("扣除积分")
            op_layout.addWidget(add_btn)
            op_layout.addWidget(deduct_btn)
            op_layout.addStretch()
            layout.addWidget(op_group)
            
            # 积分历史
            history_group = QGroupBox("积分历史")
            history_layout = QVBoxLayout(history_group)
            self._credit_history_table = QTableWidget()
            self._credit_history_table.setColumnCount(4)
            self._credit_history_table.setHorizontalHeaderLabels(["类型", "数量", "余额", "说明"])
            self._credit_history_table.horizontalHeader().setStretchLastSection(True)
            history_layout.addWidget(self._credit_history_table)
            layout.addWidget(history_group)
            
            layout.addStretch()
            return widget
        
        def _create_project_tab(self) -> QWidget:
            """创建项目财务选项卡"""
            widget = QWidget()
            layout = QVBoxLayout(widget)
            layout.setContentsMargins(8, 8, 8, 8)
            
            # 项目列表
            projects_group = QGroupBox("项目列表")
            projects_layout = QVBoxLayout(projects_group)
            self._projects_table = QTableWidget()
            self._projects_table.setColumnCount(5)
            self._projects_table.setHorizontalHeaderLabels(["ID", "名称", "预算", "支出", "状态"])
            self._projects_table.horizontalHeader().setStretchLastSection(True)
            projects_layout.addWidget(self._projects_table)
            layout.addWidget(projects_group)
            
            # 添加项目
            add_layout = QHBoxLayout()
            self._project_name_input = QLineEdit()
            self._project_name_input.setPlaceholderText("项目名称")
            self._project_budget_input = QDoubleSpinBox()
            self._project_budget_input.setRange(0, 999999999)
            self._project_budget_input.setSuffix(" 元")
            add_project_btn = QPushButton("添加项目")
            add_layout.addWidget(self._project_name_input)
            add_layout.addWidget(self._project_budget_input)
            add_layout.addWidget(add_project_btn)
            layout.addLayout(add_layout)
            
            layout.addStretch()
            return widget
        
        def _create_economics_tab(self) -> QWidget:
            """创建经济分析选项卡"""
            widget = QWidget()
            layout = QVBoxLayout(widget)
            layout.setContentsMargins(8, 8, 8, 8)
            
            # 指标列表
            indicators_group = QGroupBox("经济指标")
            indicators_layout = QFormLayout(indicators_group)
            self._indicator_inputs = {}
            for name in ["GDP增长率", "CPI", "失业率", "利率"]:
                input_field = QLineEdit()
                input_field.setPlaceholderText("输入数值")
                self._indicator_inputs[name] = input_field
                indicators_layout.addRow(f"{name}：", input_field)
            layout.addWidget(indicators_group)
            
            # 更新按钮
            update_btn = QPushButton("更新指标")
            update_btn.clicked.connect(self._on_update_indicators)
            layout.addWidget(update_btn)
            
            # 趋势分析（占位）
            trend_group = QGroupBox("趋势分析")
            trend_layout = QVBoxLayout(trend_group)
            trend_layout.addWidget(QLabel("（趋势图表待集成）"))
            layout.addWidget(trend_group)
            
            layout.addStretch()
            return widget
        
        def _create_value_card(self, title: str, value: str, color: str) -> QGroupBox:
            """创建数值卡片"""
            card = QGroupBox(title)
            card.setStyleSheet(f"QGroupBox {{ color: {color}; font-weight: bold; }}")
            card_layout = QVBoxLayout(card)
            value_label = QLabel(value)
            font = QFont()
            font.setPointSize(18)
            font.setBold(True)
            value_label.setFont(font)
            value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value_label.setStyleSheet(f"color: {color};")
            card_layout.addWidget(value_label)
            # 存储引用
            setattr(card, "_value_label", value_label)
            return card
        
        def _init_mock_data(self) -> None:
            """初始化模拟数据"""
            # Dashboard
            self._panel.dashboard.total_assets = 1000000.0
            self._panel.dashboard.total_liabilities = 200000.0
            self._panel.dashboard.net_assets = 800000.0
            self._panel.dashboard.daily_change = 5000.0
            self._panel.dashboard.daily_change_rate = 0.5
            self._panel.dashboard.assets_breakdown = {
                "股票": 400000.0,
                "基金": 200000.0,
                "存款": 300000.0,
                "其他": 100000.0,
            }
            
            # Investment
            self._panel.investment.add_position(InvestmentPosition(
                symbol="600519.SH",
                name="贵州茅台",
                quantity=100,
                cost=1800.0,
                current_price=1850.0,
                market_value=185000.0,
                profit_loss=5000.0,
                profit_loss_rate=2.78,
            ))
            
            # Payment
            self._panel.payment.balance = 50000.0
            
            # Credit
            self._panel.credit.total_credits = 1000.0
        
        def _update_ui(self) -> None:
            """更新 UI 显示"""
            # Dashboard
            summary = self._panel.dashboard.get_summary()
            self._update_card_value(self._total_assets_card, f"¥{summary.total_assets:,.2f}")
            self._update_card_value(self._total_liabilities_card, f"¥{summary.total_liabilities:,.2f}")
            self._update_card_value(self._net_assets_card, f"¥{summary.net_assets:,.2f}")
            daily_sign = "+" if summary.daily_change >= 0 else ""
            self._update_card_value(self._daily_change_card, f"{daily_sign}¥{summary.daily_change:,.2f}")
            
            # Investment
            perf = self._panel.investment.get_portfolio_performance()
            self._total_cost_label.setText(f"¥{perf['total_cost']:,.2f}")
            self._total_value_label.setText(f"¥{perf['total_value']:,.2f}")
            pl_sign = "+" if perf['profit_loss'] >= 0 else ""
            self._total_pl_label.setText(f"{pl_sign}¥{perf['profit_loss']:,.2f}")
            self._total_pl_rate_label.setText(f"{pl_sign}{perf['profit_loss_rate']:.2f}%")
            
            # Payment
            self._balance_label.setText(f"¥{self._panel.payment.balance:,.2f}")
            
            # Credit
            self._credit_balance_label.setText(f"{self._panel.credit.total_credits:,.0f}")
            
            self._status_bar.setText(f"最后更新：{time.strftime('%H:%M:%S')}")
        
        def _update_card_value(self, card: QGroupBox, value: str) -> None:
            """更新卡片数值"""
            if hasattr(card, "_value_label"):
                card._value_label.setText(value)
        
        def _on_tab_changed(self, index: int) -> None:
            """选项卡切换"""
            tab_map = {
                0: PanelTab.DASHBOARD,
                1: PanelTab.INVESTMENT,
                2: PanelTab.PAYMENT,
                3: PanelTab.CREDIT,
                4: PanelTab.PROJECT,
                5: PanelTab.ECONOMICS,
            }
            self._current_tab = tab_map.get(index, PanelTab.DASHBOARD)
            self.tab_changed.emit(self._current_tab.value)
        
        def _on_update_indicators(self) -> None:
            """更新经济指标"""
            for name, input_field in self._indicator_inputs.items():
                value_str = input_field.text().strip()
                if value_str:
                    try:
                        value = float(value_str)
                        self._panel.economics.update_indicator(name, value)
                    except ValueError:
                        pass
            self._status_bar.setText(f"指标已更新：{time.strftime('%H:%M:%S')}")
        
        def refresh(self) -> None:
            """刷新数据"""
            self._update_ui()
        
        def get_panel(self) -> FinanceHubPanel:
            """获取底层面板（用于数据操作）"""
            return self._panel
        
else:
    # 无 PyQt6 时的占位
    class FinanceHubPanelUI:
        def __init__(self, *args, **kwargs):
            raise ImportError("PyQt6 未安装，无法使用 FinanceHubPanelUI")


# 全局面板实例
_global_panel: Optional[FinanceHubPanel] = None


def get_finance_hub_panel() -> FinanceHubPanel:
    """获取全局金融面板实例"""
    global _global_panel
    
    if _global_panel is None:
        _global_panel = FinanceHubPanel()
    
    return _global_panel
