"""
决策支持面板 UI
Decision Support Panel UI

提供：
1. 情景概率分析卡片
2. 个性化策略对比表格
3. 风险收益矩阵可视化
4. 用户画像设置
5. 合规确认对话框
"""

import json
import uuid
from typing import Optional, Dict, Any, Callable
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QScrollArea, QTextEdit, QDialog,
    QCheckBox, QComboBox, QSpinBox, QDoubleSpinBox,
    QTabWidget, QProgressBar, QFrame, QSizePolicy,
    QLineEdit, QFormLayout, QDialogButtonBox,
    QMessageBox, QGraphicsView, QGraphicsScene,
    QGraphicsRectItem, QGraphicsTextItem, QGraphicsEllipseItem
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, pyqtSlot, QTimer
from PyQt6.QtGui import QFont, QColor, QPalette, QBrush, QPainter, QPen

from .business.decision_engine import (
    MarketScenario, InvestmentStrategy, RiskRewardMetric,
    UserProfile, ScenarioType, StrategyType, RiskLevel
)


class ScenarioCard(QFrame):
    """情景分析卡片"""

    # 情景颜色映射
    SCENARIO_COLORS = {
        ScenarioType.OPTIMISTIC: ("#E8F5E9", "#4CAF50"),  # 绿色
        ScenarioType.NEUTRAL: ("#E3F2FD", "#2196F3"),     # 蓝色
        ScenarioType.PESSIMISTIC: ("#FFEBEE", "#F44336"),  # 红色
    }

    def __init__(self, scenario: MarketScenario, parent=None):
        super().__init__(parent)
        self.scenario = scenario
        self._setup_ui()
        self._populate_data()

    def _setup_ui(self):
        """初始化UI"""
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setMinimumHeight(180)

        # 根据情景类型设置颜色
        scenario_type = ScenarioType(self.scenario.type)
        bg_color, accent_color = self.SCENARIO_COLORS.get(
            scenario_type, ("#F5F5F5", "#9E9E9E")
        )
        self.setStyleSheet(f"""
            ScenarioCard {{
                background-color: {bg_color};
                border: 2px solid {accent_color};
                border-radius: 8px;
                margin: 4px;
            }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)

        # 标题行
        header_layout = QHBoxLayout()

        # 情景图标和名称
        type_names = {
            ScenarioType.OPTIMISTIC: "【乐观情景】",
            ScenarioType.NEUTRAL: "【中性情景】",
            ScenarioType.PESSIMISTIC: "【悲观情景】",
        }
        type_emojis = {
            ScenarioType.OPTIMISTIC: "📈",
            ScenarioType.NEUTRAL: "➡️",
            ScenarioType.PESSIMISTIC: "📉",
        }

        type_label = QLabel(f"{type_emojis.get(scenario_type, '❓')} {type_names.get(scenario_type, '')}")
        type_label.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        header_layout.addWidget(type_label)

        # 概率标签
        prob_label = QLabel(f"概率: {self.scenario.probability:.1%}")
        prob_label.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        prob_label.setStyleSheet(f"color: {accent_color};")
        header_layout.addWidget(prob_label)
        header_layout.addStretch()

        main_layout.addLayout(header_layout)

        # 价格目标
        price_layout = QHBoxLayout()
        price_layout.addWidget(QLabel(f"📍 价格区间:"))
        price_low = QLabel(f"{self.scenario.price_target_low:.2f}")
        price_low.setFont(QFont("Consolas", 10))
        price_layout.addWidget(price_low)
        price_layout.addWidget(QLabel("~"))
        price_high = QLabel(f"{self.scenario.price_target_high:.2f}")
        price_high.setFont(QFont("Consolas", 10))
        price_layout.addWidget(price_high)
        price_layout.addWidget(QLabel(f"(约{self.scenario.timeframe_days}天)"))
        price_layout.addStretch()
        main_layout.addLayout(price_layout)

        # 触发条件
        trigger_label = QLabel("🔔 触发条件:")
        trigger_label.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        main_layout.addWidget(trigger_label)

        for i, condition in enumerate(self.scenario.trigger_conditions[:3], 1):
            cond_widget = QLabel(f"   {i}. {condition}")
            cond_widget.setWordWrap(True)
            main_layout.addWidget(cond_widget)

        # 信号区域
        signals_layout = QHBoxLayout()

        # 确认信号
        confirm_widget = QWidget()
        confirm_layout = QVBoxLayout(confirm_widget)
        confirm_layout.setContentsMargins(0, 0, 0, 0)
        confirm_label = QLabel("✅ 确认信号:")
        confirm_label.setFont(QFont("Microsoft YaHei", 8, QFont.Weight.Bold))
        confirm_layout.addWidget(confirm_label)
        for signal in self.scenario.confirmation_signals[:2]:
            sig_label = QLabel(f"• {signal}")
            sig_label.setFont(QFont("Microsoft YaHei", 8))
            sig_label.setWordWrap(True)
            confirm_layout.addWidget(sig_label)
        signals_layout.addWidget(confirm_widget)

        # 失效信号
        invalidate_widget = QWidget()
        invalidate_layout = QVBoxLayout(invalidate_widget)
        invalidate_layout.setContentsMargins(0, 0, 0, 0)
        invalidate_label = QLabel("❌ 失效信号:")
        invalidate_label.setFont(QFont("Microsoft YaHei", 8, QFont.Weight.Bold))
        invalidate_layout.addWidget(invalidate_label)
        for signal in self.scenario.invalidation_signals[:2]:
            sig_label = QLabel(f"• {signal}")
            sig_label.setFont(QFont("Microsoft YaHei", 8))
            sig_label.setWordWrap(True)
            invalidate_layout.addWidget(sig_label)
        signals_layout.addWidget(invalidate_widget)

        main_layout.addLayout(signals_layout)

    def _populate_data(self):
        """填充数据"""
        pass  # 已在 _setup_ui 中处理


class StrategyTableWidget(QTableWidget):
    """策略对比表格"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """初始化UI"""
        self.setColumnCount(7)
        self.setHorizontalHeaderLabels([
            "策略", "预期收益", "最大回撤", "夏普比率", "胜率", "风险等级", "适合度"
        ])

        # 设置列宽
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 7):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

    def populate_strategies(self, strategies: list, risk_matrix: list, user_profile: UserProfile = None):
        """填充策略数据"""
        self.setRowCount(len(strategies))

        # 风险等级颜色
        risk_colors = {
            RiskLevel.HIGH.value: ("#FFCDD2", "#D32F2F"),
            RiskLevel.MEDIUM.value: ("#FFE0B2", "#F57C00"),
            RiskLevel.LOW.value: ("#C8E6C9", "#388E3C"),
        }

        for i, (strategy, metrics) in enumerate(zip(strategies, risk_matrix)):
            # 策略名称
            type_names = {
                StrategyType.AGGRESSIVE.value: "🚀 激进型",
                StrategyType.MODERATE.value: "⚖️ 稳健型",
                StrategyType.CONSERVATIVE.value: "🛡️ 保守型",
            }
            name_item = QTableWidgetItem(type_names.get(strategy.type, strategy.type))
            name_item.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
            self.setItem(i, 0, name_item)

            # 预期收益（绿色为正，红色为负）
            return_item = QTableWidgetItem(metrics.expected_return)
            if "+" in metrics.expected_return:
                return_item.setForeground(QColor("#2E7D32"))
            else:
                return_item.setForeground(QColor("#C62828"))
            self.setItem(i, 1, return_item)

            # 最大回撤
            self.setItem(i, 2, QTableWidgetItem(metrics.max_drawdown))

            # 夏普比率
            self.setItem(i, 3, QTableWidgetItem(metrics.sharpe_ratio))

            # 胜率
            self.setItem(i, 4, QTableWidgetItem(metrics.win_rate))

            # 风险等级
            risk_item = QTableWidgetItem(metrics.risk_level.upper())
            bg_color, fg_color = risk_colors.get(
                metrics.risk_level, ("#E0E0E0", "#424242")
            )
            risk_item.setBackground(QBrush(QColor(bg_color)))
            risk_item.setForeground(QBrush(QColor(fg_color)))
            risk_item.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
            self.setItem(i, 5, risk_item)

            # 适合度
            suitability = self._calculate_suitability(strategy, user_profile)
            suit_item = QTableWidgetItem(suitability)
            suit_colors = {"高": "#4CAF50", "中": "#FF9800", "低": "#F44336"}
            suit_item.setForeground(QBrush(QColor(suit_colors.get(suitability, "#666"))))
            suit_item.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
            self.setItem(i, 6, suit_item)

        self.resizeRowsToContents()

    def _calculate_suitability(self, strategy: InvestmentStrategy, user_profile: UserProfile) -> str:
        """计算策略对用户的适合度"""
        if user_profile is None:
            return "中"

        risk_tolerance = user_profile.risk_tolerance
        experience = user_profile.investment_experience

        # 激进策略适合高风险承受者
        if strategy.type == StrategyType.AGGRESSIVE.value:
            if risk_tolerance >= 0.7 and experience in ["intermediate", "experienced"]:
                return "高"
            elif risk_tolerance >= 0.4:
                return "中"
            return "低"

        # 保守策略适合低风险承受者
        elif strategy.type == StrategyType.CONSERVATIVE.value:
            if risk_tolerance <= 0.4:
                return "高"
            elif risk_tolerance <= 0.7:
                return "中"
            return "低"

        # 稳健策略适合大多数
        else:
            if 0.3 <= risk_tolerance <= 0.7:
                return "高"
            return "中"


class RiskMatrixWidget(QWidget):
    """风险收益矩阵可视化"""

    def __init__(self, strategies: list, risk_matrix: list, parent=None):
        super().__init__(parent)
        self.strategies = strategies
        self.risk_matrix = risk_matrix
        self._setup_ui()

    def _setup_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)

        title = QLabel("📊 风险收益矩阵")
        title.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        main_layout.addWidget(title)

        # 创建矩阵表格
        matrix_table = QTableWidget()
        matrix_table.setColumnCount(5)
        matrix_table.setRowCount(len(self.strategies))
        matrix_table.setHorizontalHeaderLabels([
            "策略", "预期收益", "最大回撤", "夏普比率", "风险等级"
        ])

        for i, (strategy, metrics) in enumerate(zip(self.strategies, self.risk_matrix)):
            type_names = {
                StrategyType.AGGRESSIVE.value: "🚀激进",
                StrategyType.MODERATE.value: "⚖️稳健",
                StrategyType.CONSERVATIVE.value: "🛡️保守",
            }
            matrix_table.setItem(i, 0, QTableWidgetItem(type_names.get(strategy.type, "")))
            matrix_table.setItem(i, 1, QTableWidgetItem(metrics.expected_return))
            matrix_table.setItem(i, 2, QTableWidgetItem(metrics.max_drawdown))
            matrix_table.setItem(i, 3, QTableWidgetItem(metrics.sharpe_ratio))

            risk_item = QTableWidgetItem(metrics.risk_level.upper())
            risk_colors = {
                "HIGH": "#FFCDD2", "MEDIUM": "#FFE0B2", "LOW": "#C8E6C9"
            }
            risk_item.setBackground(QBrush(QColor(risk_colors.get(metrics.risk_level.upper(), "#E0E0E0"))))
            matrix_table.setItem(i, 4, risk_item)

        matrix_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        for i in range(1, 5):
            matrix_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
        matrix_table.setAlternatingRowColors(True)

        main_layout.addWidget(matrix_table)

        # 图例
        legend_layout = QHBoxLayout()
        legend_layout.addWidget(QLabel("风险等级图例:"))
        for level, color in [("HIGH 高风险", "#FFCDD2"), ("MEDIUM 中风险", "#FFE0B2"), ("LOW 低风险", "#C8E6C9")]:
            label = QLabel(f"  {level}  ")
            label.setStyleSheet(f"background-color: {color}; padding: 2px 8px; border-radius: 4px;")
            legend_layout.addWidget(label)
        legend_layout.addStretch()

        main_layout.addLayout(legend_layout)


class UserProfileDialog(QDialog):
    """用户画像设置对话框"""

    profile_changed = pyqtSignal(dict)  # 用户画像变更信号

    def __init__(self, current_profile: Dict = None, parent=None):
        super().__init__(parent)
        self.current_profile = current_profile or {}
        self._setup_ui()
        self._load_profile()

    def _setup_ui(self):
        """初始化UI"""
        self.setWindowTitle("投资画像设置")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        main_layout = QVBoxLayout(self)

        # 风险承受能力
        risk_group = QGroupBox("风险承受能力")
        risk_layout = QFormLayout()

        self.risk_slider = QDoubleSpinBox()
        self.risk_slider.setRange(0, 1)
        self.risk_slider.setSingleStep(0.1)
        self.risk_slider.setDecimals(1)
        self.risk_slider.setSuffix(" (0=保守, 1=激进)")

        risk_tolerance_layout = QHBoxLayout()
        risk_tolerance_layout.addWidget(QLabel("保守"))
        risk_tolerance_layout.addWidget(self.risk_slider)
        risk_tolerance_layout.addWidget(QLabel("激进"))
        risk_layout.addRow("风险偏好:", risk_tolerance_layout)

        self.experience_combo = QComboBox()
        self.experience_combo.addItems(["新手", "有一定经验", "经验丰富"])
        risk_layout.addRow("投资经验:", self.experience_combo)

        risk_group.setLayout(risk_layout)
        main_layout.addWidget(risk_group)

        # 资金和周期
        capital_group = QGroupBox("资金和投资周期")
        capital_layout = QFormLayout()

        self.capital_combo = QComboBox()
        self.capital_combo.addItems(["小资金 (<10万)", "中等资金 (10-50万)", "大资金 (>50万)"])
        capital_layout.addRow("资金规模:", self.capital_combo)

        self.horizon_combo = QComboBox()
        self.horizon_combo.addItems(["短期 (<1个月)", "中期 (1-6个月)", "长期 (>6个月)"])
        capital_layout.addRow("投资周期:", self.horizon_combo)

        capital_group.setLayout(capital_layout)
        main_layout.addWidget(capital_group)

        # 投资偏好
        preference_group = QGroupBox("投资偏好")
        preference_layout = QVBoxLayout()

        self.stop_loss_check = QCheckBox("有止损经验")
        preference_layout.addWidget(self.stop_loss_check)

        self.margin_check = QCheckBox("有融资融券经验")
        preference_layout.addWidget(self.margin_check)

        preference_group.setLayout(preference_layout)
        main_layout.addWidget(preference_group)

        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.save_btn = QPushButton("保存")
        self.save_btn.clicked.connect(self._on_save)
        button_layout.addWidget(self.save_btn)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        main_layout.addLayout(button_layout)

    def _load_profile(self):
        """加载当前画像"""
        if not self.current_profile:
            return

        profile = self.current_profile.get("investment_profile", {})

        self.risk_slider.setValue(profile.get("risk_tolerance", 0.5))

        experience_map = {"beginner": "新手", "intermediate": "有一定经验", "experienced": "经验丰富"}
        experience = profile.get("investment_experience", "beginner")
        self.experience_combo.setCurrentText(experience_map.get(experience, "新手"))

        capital_map = {"small": "小资金 (<10万)", "medium": "中等资金 (10-50万)", "large": "大资金 (>50万)"}
        capital = profile.get("capital_size", "small")
        self.capital_combo.setCurrentText(capital_map.get(capital, "小资金 (<10万)"))

        horizon_map = {"short": "短期 (<1个月)", "medium": "中期 (1-6个月)", "long": "长期 (>6个月)"}
        horizon = profile.get("investment_horizon", "short")
        self.horizon_combo.setCurrentText(horizon_map.get(horizon, "短期 (<1个月)"))

        self.stop_loss_check.setChecked(bool(profile.get("has_stop_loss_experience")))
        self.margin_check.setChecked(bool(profile.get("has_margin_experience")))

    def _on_save(self):
        """保存画像"""
        experience_map = {"新手": "beginner", "有一定经验": "intermediate", "经验丰富": "experienced"}
        capital_map = {"小资金 (<10万)": "small", "中等资金 (10-50万)": "medium", "大资金 (>50万)": "large"}
        horizon_map = {"短期 (<1个月)": "short", "中期 (1-6个月)": "medium", "长期 (>6个月)": "long"}

        profile = {
            "risk_tolerance": self.risk_slider.value(),
            "investment_experience": experience_map.get(self.experience_combo.currentText(), "beginner"),
            "capital_size": capital_map.get(self.capital_combo.currentText(), "small"),
            "investment_horizon": horizon_map.get(self.horizon_combo.currentText(), "short"),
            "has_stop_loss_experience": self.stop_loss_check.isChecked(),
            "has_margin_experience": self.margin_check.isChecked(),
        }

        self.profile_changed.emit(profile)
        self.accept()

    def get_profile(self) -> UserProfile:
        """获取 UserProfile 对象"""
        experience_map = {"新手": "beginner", "有一定经验": "intermediate", "经验丰富": "experienced"}
        capital_map = {"小资金 (<10万)": "small", "中等资金 (10-50万)": "medium", "大资金 (>50万)": "large"}
        horizon_map = {"短期 (<1个月)": "short", "中期 (1-6个月)": "medium", "长期 (>6个月)": "long"}

        return UserProfile(
            risk_tolerance=self.risk_slider.value(),
            investment_experience=experience_map.get(self.experience_combo.currentText(), "beginner"),
            capital_size=capital_map.get(self.capital_combo.currentText(), "small"),
            investment_horizon=horizon_map.get(self.horizon_combo.currentText(), "short"),
            has_stop_loss_experience=self.stop_loss_check.isChecked(),
            has_margin_experience=self.margin_check.isChecked(),
        )


class DisclaimerDialog(QDialog):
    """合规免责声明对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.agreed = False
        self._setup_ui()

    def _setup_ui(self):
        """初始化UI"""
        self.setWindowTitle("风险提示")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

        main_layout = QVBoxLayout(self)

        # 警告图标和标题
        header_layout = QHBoxLayout()
        warning_label = QLabel("⚠️ 重要风险提示")
        warning_label.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        warning_label.setStyleSheet("color: #D32F2F;")
        header_layout.addWidget(warning_label)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        # 免责声明文本
        disclaimer_text = QTextEdit()
        disclaimer_text.setReadOnly(True)
        disclaimer_text.setHtml("""
        <h3>免责声明</h3>
        <p>本系统提供的分析基于公开数据和概率模型，<strong>不构成投资建议</strong>。</p>

        <h4>1. 风险提示</h4>
        <ul>
            <li>市场有风险，投资需谨慎</li>
            <li>过去业绩不代表未来表现</li>
            <li>任何投资都存在本金损失的可能</li>
        </ul>

        <h4>2. 分析局限性</h4>
        <ul>
            <li>情景分析基于概率模型，可能与实际走势不符</li>
            <li>策略建议仅供参考，不保证收益</li>
            <li>市场突发事件可能导致分析失效</li>
        </ul>

        <h4>3. 用户责任</h4>
        <ul>
            <li>您的投资决策应基于自身独立判断</li>
            <li>请充分了解投资产品的风险特征</li>
            <li>建议在投资前咨询专业 financial 顾问</li>
        </ul>

        <h4>4. 数据记录</h4>
        <p>您使用本系统的所有操作记录将被加密保存在本地日志中，仅供您个人复盘使用。</p>
        """)
        main_layout.addWidget(disclaimer_text)

        # 同意复选框
        self.agree_check = QCheckBox("我已阅读并理解上述风险提示，同意使用决策支持功能")
        main_layout.addWidget(self.agree_check)

        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.continue_btn = QPushButton("继续使用")
        self.continue_btn.clicked.connect(self._on_continue)
        self.continue_btn.setEnabled(False)
        button_layout.addWidget(self.continue_btn)

        self.agree_check.toggled.connect(lambda checked: self.continue_btn.setEnabled(checked))

        self.exit_btn = QPushButton("退出")
        self.exit_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.exit_btn)

        main_layout.addLayout(button_layout)

    def _on_continue(self):
        """继续使用"""
        self.agreed = True
        self.accept()

    def is_agreed(self) -> bool:
        """检查是否已同意"""
        return self.agreed


class DecisionSupportPanel(QWidget):
    """
    决策支持面板主组件

    Signals:
        strategy_selected: 当用户选择一个策略时发出
        profile_settings_requested: 当用户请求设置画像时发出
        analysis_requested: 当用户请求重新分析时发出
    """

    strategy_selected = pyqtSignal(dict)  # 选中的策略
    profile_settings_requested = pyqtSignal()  # 请求设置画像
    analysis_requested = pyqtSignal(str, dict, list, list)  # 请求分析 (symbol, data, news, indicators)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_data = None
        self.disclaimer_agreed = False
        self._setup_ui()

    def _setup_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        # 顶部工具栏
        toolbar_layout = QHBoxLayout()

        self.profile_btn = QPushButton("👤 投资画像设置")
        self.profile_btn.clicked.connect(self._on_profile_settings)
        toolbar_layout.addWidget(self.profile_btn)

        self.refresh_btn = QPushButton("🔄 重新分析")
        self.refresh_btn.clicked.connect(self._on_refresh)
        toolbar_layout.addWidget(self.refresh_btn)

        toolbar_layout.addStretch()

        # 免责声明标签
        disclaimer_label = QLabel("⚠️ 本系统不构成投资建议，仅供参考")
        disclaimer_label.setStyleSheet("color: #F44336; font-size: 12px;")
        toolbar_layout.addWidget(disclaimer_label)

        main_layout.addLayout(toolbar_layout)

        # 选项卡
        self.tabs = QTabWidget()

        # 情景分析标签页
        scenario_tab = QWidget()
        scenario_layout = QVBoxLayout(scenario_tab)

        scenario_header = QLabel("📈 情景概率分析")
        scenario_header.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        scenario_layout.addWidget(scenario_header)

        self.scenario_scroll = QScrollArea()
        self.scenario_scroll.setWidgetResizable(True)
        self.scenario_container = QWidget()
        self.scenario_container_layout = QVBoxLayout(self.scenario_container)
        self.scenario_scroll.setWidget(self.scenario_container)
        scenario_layout.addWidget(self.scenario_scroll)

        self.tabs.addTab(scenario_tab, "情景分析")

        # 策略建议标签页
        strategy_tab = QWidget()
        strategy_layout = QVBoxLayout(strategy_tab)

        strategy_header = QLabel("🎯 个性化策略建议")
        strategy_header.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        strategy_layout.addWidget(strategy_header)

        self.strategy_table = StrategyTableWidget()
        strategy_layout.addWidget(self.strategy_table)

        # 快速执行按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.btn_aggressive = QPushButton("🚀 执行激进策略")
        self.btn_aggressive.setStyleSheet("background-color: #FFCDD2; padding: 8px 16px;")
        self.btn_aggressive.clicked.connect(lambda: self._on_strategy_select(0))
        button_layout.addWidget(self.btn_aggressive)

        self.btn_moderate = QPushButton("⚖️ 执行稳健策略")
        self.btn_moderate.setStyleSheet("background-color: #FFE0B2; padding: 8px 16px;")
        self.btn_moderate.clicked.connect(lambda: self._on_strategy_select(1))
        button_layout.addWidget(self.btn_moderate)

        self.btn_conservative = QPushButton("🛡️ 执行保守策略")
        self.btn_conservative.setStyleSheet("background-color: #C8E6C9; padding: 8px 16px;")
        self.btn_conservative.clicked.connect(lambda: self._on_strategy_select(2))
        button_layout.addWidget(self.btn_conservative)

        strategy_layout.addLayout(button_layout)

        self.tabs.addTab(strategy_tab, "策略建议")

        # 风险矩阵标签页
        risk_tab = QWidget()
        risk_layout = QVBoxLayout(risk_tab)

        self.risk_matrix_widget = RiskMatrixWidget([], [])
        risk_layout.addWidget(self.risk_matrix_widget)

        self.tabs.addTab(risk_tab, "风险矩阵")

        main_layout.addWidget(self.tabs)

        # 底部状态栏
        status_layout = QHBoxLayout()

        self.status_label = QLabel("状态: 等待分析...")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()

        self.last_update_label = QLabel("最后更新: --")
        status_layout.addWidget(self.last_update_label)

        main_layout.addLayout(status_layout)

    def set_disclaimer_agreed(self, agreed: bool):
        """设置免责声明已同意"""
        self.disclaimer_agreed = agreed

    def display_decision_report(self, report: Dict, user_profile: UserProfile = None):
        """显示决策报告"""
        if not self.disclaimer_agreed:
            dialog = DisclaimerDialog(self)
            if not dialog.exec():
                return
            self.disclaimer_agreed = True

        self.current_data = report

        # 清空并重建情景卡片
        while self.scenario_container_layout.count():
            item = self.scenario_container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        scenarios = report.get("scenarios", [])
        for scenario_data in scenarios:
            scenario = MarketScenario(**scenario_data)
            card = ScenarioCard(scenario)
            self.scenario_container_layout.addWidget(card)

        self.scenario_container_layout.addStretch()

        # 更新策略表格
        strategies_data = report.get("strategies", [])
        risk_matrix = report.get("risk_matrix", [])

        # 转换为对象
        strategies = [InvestmentStrategy(**s) for s in strategies_data]
        metrics = [RiskRewardMetric(**m) for m in risk_matrix]

        self.strategy_table.populate_strategies(strategies, metrics, user_profile)

        # 更新风险矩阵
        # 重新创建风险矩阵组件
        risk_layout = self.tabs.widget(2).layout()
        while risk_layout.count():
            item = risk_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        new_risk_widget = RiskMatrixWidget(strategies, metrics)
        risk_layout.addWidget(new_risk_widget)

        # 更新状态
        import datetime
        self.last_update_label.setText(f"最后更新: {datetime.datetime.now().strftime('%H:%M:%S')}")
        self.status_label.setText(f"状态: 已分析 {len(scenarios)} 种情景, {len(strategies)} 种策略")

    def _on_profile_settings(self):
        """打开画像设置"""
        self.profile_settings_requested.emit()

    def _on_refresh(self):
        """重新分析"""
        if self.current_data:
            symbol = self.current_data.get("symbol", "")
            data = self.current_data.get("data", {})
            news = self.current_data.get("news", [])
            indicators = self.current_data.get("indicators", [])
            self.analysis_requested.emit(symbol, data, news, indicators)

    def _on_strategy_select(self, index: int):
        """选择策略"""
        if self.current_data:
            strategies = self.current_data.get("strategies", [])
            if index < len(strategies):
                self.strategy_selected.emit(strategies[index])
                QMessageBox.information(
                    self,
                    "策略已记录",
                    f"您已选择: {strategies[index].get('name', '策略' + str(index+1))}\n\n"
                    "请注意：这仅作为记录，不代表实际执行。\n"
                    "如需实盘操作，请通过正规券商渠道。"
                )

    def clear(self):
        """清空面板"""
        while self.scenario_container_layout.count():
            item = self.scenario_container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.strategy_table.setRowCount(0)
        self.status_label.setText("状态: 等待分析...")
        self.current_data = None


def create_decision_panel(parent=None) -> DecisionSupportPanel:
    """创建决策支持面板"""
    return DecisionSupportPanel(parent)
