"""
决策支持系统演示
Demonstrates the Decision Support System with PyQt6 UI

功能演示：
1. 情景概率分析
2. 个性化策略生成
3. 风险收益矩阵
4. 用户画像设置
5. 合规免责声明
"""

import sys
import asyncio
import json
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QGroupBox, QFormLayout, QLineEdit, QDoubleSpinBox, QComboBox
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont

from core.decision_engine import (
    get_decision_engine,
    UserProfile, MarketScenario, InvestmentStrategy, ScenarioType, StrategyType
)
from ui.decision_panel import (
    DecisionSupportPanel, UserProfileDialog, DisclaimerDialog, ScenarioCard, StrategyTableWidget
)


class DecisionDemoWindow(QMainWindow):
    """演示窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("决策支持系统 - 演示")
        self.setMinimumSize(1000, 700)

        # 决策引擎
        self.engine = get_decision_engine()

        # 当前用户画像
        self.user_profile = UserProfile(
            risk_tolerance=0.6,
            investment_experience="intermediate",
            capital_size="medium",
            investment_horizon="medium"
        )

        self._setup_ui()

        # 模拟数据
        self.simulated_data = {
            "symbol": "AAPL",
            "current_price": 175.50,
            "data": {
                "current": 175.50,
                "indicators": {
                    "trend": "上升",
                    "rsi": 58,
                    "macd": "金叉",
                    "volatility": 0.18
                }
            },
            "news": [
                "苹果发布新款iPhone，销量超预期",
                "分析师上调苹果目标价至200美元",
                "iPhone在中国市场份额持续增长"
            ],
            "news_sentiment": 0.75,
            "indicators": [
                {"type": "技术", "name": "RSI", "value": 58, "signal": "中性偏多"},
                {"type": "技术", "name": "MACD", "value": 0.5, "signal": "金叉"},
                {"type": "技术", "name": "MA", "value": "多头排列", "signal": "多头"}
            ]
        }

    def _setup_ui(self):
        """初始化UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)

        # 左侧：输入面板
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        # 标题
        title = QLabel("Decision Support System Demo")
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        left_layout.addWidget(title)

        # 输入区域
        input_group = QGroupBox("Analysis Parameters")
        input_layout = QFormLayout()

        self.symbol_input = QLineEdit("AAPL")
        self.symbol_input.setPlaceholderText("Stock Symbol")
        input_layout.addRow("Symbol:", self.symbol_input)

        self.price_input = QDoubleSpinBox()
        self.price_input.setRange(0, 10000)
        self.price_input.setValue(175.50)
        self.price_input.setDecimals(2)
        input_layout.addRow("Price:", self.price_input)

        self.sentiment_combo = QComboBox()
        self.sentiment_combo.addItems(["Very Bearish (0.1)", "Bearish (0.3)", "Neutral (0.5)", "Bullish (0.7)", "Very Bullish (0.9)"])
        self.sentiment_combo.setCurrentIndex(3)
        input_layout.addRow("Sentiment:", self.sentiment_combo)

        input_group.setLayout(input_layout)
        left_layout.addWidget(input_group)

        # 消息输入
        news_group = QGroupBox("Latest News (one per line)")
        news_layout = QVBoxLayout()
        self.news_text = QTextEdit()
        self.news_text.setPlaceholderText("Enter market news...")
        self.news_text.setMaximumHeight(150)
        news_layout.addWidget(self.news_text)
        news_group.setLayout(news_layout)
        left_layout.addWidget(news_group)

        # 画像按钮
        profile_btn = QPushButton("User Profile Settings")
        profile_btn.clicked.connect(self._on_profile_settings)
        left_layout.addWidget(profile_btn)

        # 分析按钮
        self.analyze_btn = QPushButton("Start Analysis")
        self.analyze_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 12px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.analyze_btn.clicked.connect(self._on_analyze)
        left_layout.addWidget(self.analyze_btn)

        # 生成报告按钮
        report_btn = QPushButton("Generate Full Report")
        report_btn.clicked.connect(self._on_generate_report)
        left_layout.addWidget(report_btn)

        left_layout.addStretch()

        main_layout.addWidget(left_panel, 1)

        # 右侧：决策面板
        self.decision_panel = DecisionSupportPanel()
        main_layout.addWidget(self.decision_panel, 2)

        # 信号连接
        self.decision_panel.strategy_selected.connect(self._on_strategy_selected)
        self.decision_panel.profile_settings_requested.connect(self._on_profile_settings)

    def _on_profile_settings(self):
        """打开画像设置"""
        dialog = UserProfileDialog({"investment_profile": self.user_profile.__dict__}, self)
        if dialog.exec():
            self.user_profile = dialog.get_profile()
            print(f"User profile updated: risk_tolerance={self.user_profile.risk_tolerance}")

    def _on_analyze(self):
        """执行分析"""
        self.analyze_btn.setEnabled(False)
        self.analyze_btn.setText("Analyzing...")

        # 模拟异步分析
        QTimer.singleShot(100, self._perform_analysis)

    def _perform_analysis(self):
        """执行实际分析"""
        sentiment_map = [0.1, 0.3, 0.5, 0.7, 0.9]
        sentiment = sentiment_map[self.sentiment_combo.currentIndex()]

        news = [line.strip() for line in self.news_text.toPlainText().split("\n") if line.strip()]
        if not news:
            news = ["Market trends are stable"]

        # 生成报告
        report = asyncio.run(self.engine.generate_analysis(
            symbol=self.symbol_input.text(),
            current_price=self.price_input.value(),
            indicators=self.simulated_data["indicators"],
            news=news,
            news_sentiment=sentiment,
            user_profile=self.user_profile
        ))

        # 添加 symbol 到报告
        report["symbol"] = self.symbol_input.text()
        report["data"] = {
            "current": self.price_input.value(),
            "indicators": self.simulated_data["indicators"]
        }

        # 显示报告
        self.decision_panel.display_decision_report(report, self.user_profile)

        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("Start Analysis")

    def _on_generate_report(self):
        """生成并显示完整报告文本"""
        sentiment_map = [0.1, 0.3, 0.5, 0.7, 0.9]
        sentiment = sentiment_map[self.sentiment_combo.currentIndex()]

        news = [line.strip() for line in self.news_text.toPlainText().split("\n") if line.strip()]
        if not news:
            news = ["Market trends are stable"]

        report = asyncio.run(self.engine.generate_analysis(
            symbol=self.symbol_input.text(),
            current_price=self.price_input.value(),
            indicators=self.simulated_data["indicators"],
            news=news,
            news_sentiment=sentiment,
            user_profile=self.user_profile
        ))

        report_text = self.engine.format_report_text(report)
        print("\n" + "=" * 60)
        print(report_text)
        print("=" * 60)

    def _on_strategy_selected(self, strategy: dict):
        """策略被选中"""
        print(f"User selected strategy: {strategy.get('name', 'Unknown')}")


def main():
    app = QApplication(sys.argv)

    # 设置字体
    font = QFont("Microsoft YaHei", 10)
    app.setFont(font)

    window = DecisionDemoWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
