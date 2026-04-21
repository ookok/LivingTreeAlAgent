"""
环保数字护照UI面板 - Environmental Passport Panel
=============================================

为Hermes Desktop创建的环保全生命周期管理UI面板
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QTabWidget, QTableWidget,
    QTableWidgetItem, QLineEdit, QComboBox, QTextEdit,
    QProgressBar, QFrame, QScrollArea, QGroupBox,
    QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QPainter
from typing import Dict, List, Optional


class StageIndicator(QWidget):
    """阶段指示器"""

    def __init__(self, stage_name: str, stage_icon: str = "📋"):
        super().__init__()
        self.stage_name = stage_name
        self.stage_icon = stage_icon
        self._is_active = False
        self._is_completed = False
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        self.icon_label = QLabel(self.stage_icon)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFont(QFont("Microsoft YaHei", 16))

        self.name_label = QLabel(self.stage_name)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setFont(QFont("Microsoft YaHei", 9))

        self.status_label = QLabel("待开始")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: gray; font-size: 10px;")

        layout.addWidget(self.icon_label)
        layout.addWidget(self.name_label)
        layout.addWidget(self.status_label)

        self.setLayout(layout)

    def set_active(self):
        self._is_active = True
        self._is_completed = False
        self.setStyleSheet("""
            QWidget {
                background-color: #E3F2FD;
                border: 2px solid #2196F3;
                border-radius: 8px;
            }
        """)
        self.status_label.setText("进行中")
        self.status_label.setStyleSheet("color: #2196F3; font-size: 10px;")

    def set_completed(self):
        self._is_completed = True
        self._is_active = False
        self.setStyleSheet("""
            QWidget {
                background-color: #E8F5E9;
                border: 2px solid #4CAF50;
                border-radius: 8px;
            }
        """)
        self.status_label.setText("已完成")
        self.status_label.setStyleSheet("color: #4CAF50; font-size: 10px;")

    def set_pending(self):
        self._is_completed = False
        self._is_active = False
        self.setStyleSheet("""
            QWidget {
                background-color: #F5F5F5;
                border: 1px solid #E0E0E0;
                border-radius: 8px;
            }
        """)
        self.status_label.setText("待开始")
        self.status_label.setStyleSheet("color: gray; font-size: 10px;")


class HealthScoreGauge(QWidget):
    """环保健康指数仪表盘"""

    def __init__(self, score: float = 85.0):
        super().__init__()
        self.score = score
        self.setMinimumSize(200, 150)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.score >= 90:
            color = QColor("#4CAF50")
        elif self.score >= 70:
            color = QColor("#FFC107")
        elif self.score >= 60:
            color = QColor("#FF9800")
        else:
            color = QColor("#F44336")

        painter.setPen(QColor("#E0E0E0"))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(30, 30, 140, 140, 45 * 16, 270 * 16)

        painter.setPen(color)
        span = int(270 * (self.score / 100))
        painter.drawArc(30, 30, 140, 140, 45 * 16, span * 16)

        painter.setPen(QColor("#333333"))
        font = QFont("Microsoft YaHei", 24, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, f"{self.score:.0f}")

        font = QFont("Microsoft YaHei", 10)
        painter.setFont(font)
        painter.drawText(self.rect().adjusted(0, 60, 0, 0), Qt.AlignmentFlag.AlignCenter, "环保健康指数")


class AlertCard(QWidget):
    """预警卡片"""

    def __init__(self, alert_type: str, message: str, level: str = "warning"):
        super().__init__()
        self.alert_type = alert_type
        self.message = message
        self.level = level
        self.init_ui()

    def init_ui(self):
        colors = {
            "critical": ("#F44336", "🔴"),
            "warning": ("#FF9800", "🟠"),
            "info": ("#2196F3", "🔵"),
        }
        bg_color, icon = colors.get(self.level, colors["info"])

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color}15;
                border-left: 4px solid {bg_color};
                border-radius: 4px;
                padding: 8px;
            }}
        """)

        layout = QHBoxLayout()

        self.icon_label = QLabel(icon)
        self.icon_label.setFont(QFont("Microsoft YaHei", 14))

        text_layout = QVBoxLayout()
        type_label = QLabel(self.alert_type)
        type_label.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))

        message_label = QLabel(self.message)
        message_label.setFont(QFont("Microsoft YaHei", 9))
        message_label.setWordWrap(True)

        text_layout.addWidget(type_label)
        text_layout.addWidget(message_label)

        layout.addWidget(self.icon_label)
        layout.addLayout(text_layout)
        layout.addStretch()

        self.setLayout(layout)


class EnvPassportPanel(QWidget):
    """
    环保数字护照主面板
    =================
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lifecycle_manager = None
        self.current_project_id = None
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()

        # 顶部标题栏
        header = self._create_header()
        main_layout.addWidget(header)

        # 主内容区 - 使用标签页
        tabs = QTabWidget()

        tabs.addTab(self._create_overview_tab(), "📊 项目概览")
        tabs.addTab(self._create_lifecycle_tab(), "🔄 生命周期")
        tabs.addTab(self._create_alerts_tab(), "🚨 预警中心")
        tabs.addTab(self._create_datalake_tab(), "💾 数据湖")
        tabs.addTab(self._create_models_tab(), "🧮 模型库")

        main_layout.addWidget(tabs)
        self.setLayout(main_layout)

    def _create_header(self) -> QWidget:
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background-color: #1976D2;
                border-radius: 8px;
                padding: 10px;
            }
        """)

        layout = QHBoxLayout()

        title = QLabel("🌱 环保数字护照")
        title.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: white;")

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 输入项目ID或名称搜索...")
        self.search_input.setMinimumWidth(300)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background: white;
                border: none;
                border-radius: 15px;
                padding: 8px 15px;
            }
        """)

        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(self.search_input)

        header.setLayout(layout)
        return header

    def _create_overview_tab(self) -> QWidget:
        widget = QScrollArea()
        widget.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout()

        gauge_layout = QHBoxLayout()
        self.health_gauge = HealthScoreGauge(85.0)
        gauge_layout.addWidget(self.health_gauge)

        stats_group = QGroupBox("📈 快速统计")
        stats_layout = QGridLayout()
        stats_data = [
            ("项目总数", "12"), ("进行中", "3"), ("合规率", "92%"), ("待整改", "2")
        ]
        for i, (label, value) in enumerate(stats_data):
            stats_layout.addWidget(QLabel(label), i, 0)
            stats_layout.addWidget(QLabel(value), i, 1)
        stats_group.setLayout(stats_layout)
        gauge_layout.addWidget(stats_group)
        gauge_layout.addStretch()
        layout.addLayout(gauge_layout)

        projects_group = QGroupBox("📋 项目列表")
        projects_layout = QVBoxLayout()
        self.project_table = QTableWidget()
        self.project_table.setColumnCount(5)
        self.project_table.setHorizontalHeaderLabels(["项目ID", "项目名称", "当前阶段", "状态", "健康指数"])

        sample_data = [
            ("P001", "南京化工园区A区", "排污许可", "🟢 正常", "92"),
            ("P002", "苏州印染厂B栋", "运营期", "🟡 预警", "78"),
            ("P003", "无锡电子厂新建", "建设期", "🟢 正常", "88"),
            ("P004", "常州制药厂", "环评中", "🟢 正常", "95"),
            ("P005", "镇江食品厂扩建", "竣工验收", "🟠 警告", "65"),
        ]

        self.project_table.setRowCount(len(sample_data))
        for row, data in enumerate(sample_data):
            for col, value in enumerate(data):
                self.project_table.setItem(row, col, QTableWidgetItem(value))

        projects_layout.addWidget(self.project_table)
        projects_group.setLayout(projects_layout)
        layout.addWidget(projects_group)

        content.setLayout(layout)
        widget.setWidget(content)
        return widget

    def _create_lifecycle_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout()

        stages_label = QLabel("🔄 生命周期阶段")
        stages_label.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        layout.addWidget(stages_label)

        stages_layout = QHBoxLayout()
        self.stage_indicators = {}

        stages = [
            ("EIA", "📝", "智能环评"),
            ("CONSTRUCTION", "🏗️", "建设监理"),
            ("ACCEPTANCE", "✅", "竣工验收"),
            ("PERMIT", "📋", "排污许可"),
            ("OPERATION", "⚙️", "运营期"),
            ("EMERGENCY", "🚨", "应急预案"),
            ("DECOMMISSION", "🏭", "退役管理"),
        ]

        for stage_id, icon, name in stages:
            indicator = StageIndicator(name, icon)
            self.stage_indicators[stage_id] = indicator
            stages_layout.addWidget(indicator)

        layout.addLayout(stages_layout)

        detail_group = QGroupBox("📌 阶段详情")
        detail_layout = QVBoxLayout()
        self.stage_detail_text = QTextEdit()
        self.stage_detail_text.setReadOnly(True)
        self.stage_detail_text.setHtml("""
            <h3>当前阶段：排污许可</h3>
            <p><b>许可证编号：</b>912301137×××××××××</p>
            <p><b>有效期至：</b>2026-06-30</p>
            <p><b>许可排放量：</b>SO₂: 50t/年, NOₓ: 80t/年</p>
            <p><b>下次报告提交：</b>2026-05-01（月报）</p>
        """)
        detail_layout.addWidget(self.stage_detail_text)
        detail_group.setLayout(detail_layout)
        layout.addWidget(detail_group)

        widget.setLayout(layout)
        return widget

    def _create_alerts_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout()

        title = QLabel("🚨 预警中心")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        self.alert_list = QListWidget()
        alerts = [
            ("CRITICAL", "P002 SO₂日排放量已达配额的95%", "critical"),
            ("WARNING", "P005 排污许可证将在30天后到期", "warning"),
            ("INFO", "P001 本月监测数据已全部达标", "info"),
            ("WARNING", "P003 建设期存在2项待整改违规", "warning"),
        ]

        for alert_type, message, level in alerts:
            item = QListWidgetItem()
            alert_card = AlertCard(alert_type, message, level)
            item.setSizeHint(alert_card.sizeHint())
            self.alert_list.addItem(item)
            self.alert_list.setItemWidget(item, alert_card)

        layout.addWidget(self.alert_list)
        widget.setLayout(layout)
        return widget

    def _create_datalake_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout()

        title = QLabel("💾 数据源状态")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        self.datasource_table = QTableWidget()
        self.datasource_table.setColumnCount(5)
        self.datasource_table.setHorizontalHeaderLabels(["数据源", "类型", "状态", "最后同步", "记录数"])

        datasources = [
            ("DCS-001", "DCS", "🟢 已连接", "2分钟前", "1,234,567"),
            ("ONLINE-001", "废气在线", "🟢 已连接", "1分钟前", "876,543"),
            ("WEATHER-001", "气象站", "🟢 已连接", "5分钟前", "123,456"),
            ("PERMIT-001", "排污许可", "🟡 待同步", "1小时前", "5,678"),
        ]

        self.datasource_table.setRowCount(len(datasources))
        for row, data in enumerate(datasources):
            for col, value in enumerate(data):
                self.datasource_table.setItem(row, col, QTableWidgetItem(value))

        layout.addWidget(self.datasource_table)
        widget.setLayout(layout)
        return widget

    def _create_models_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout()

        title = QLabel("🧮 专业模型库")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        model_layout = QGridLayout()
        models = [
            ("AERMOD", "大气扩散", "📊"),
            ("CALPUFF", "扩散模型", "📊"),
            ("QUAL2K", "水质模拟", "💧"),
            ("CadnaA", "噪声预测", "🔊"),
            ("ALOHA", "事故后果", "⚠️"),
            ("HHRA", "健康风险", "🏥"),
        ]

        for i, (model_id, name, icon) in enumerate(models):
            btn = QPushButton(f"{icon}\n{name}")
            btn.setMinimumSize(100, 60)
            btn.clicked.connect(lambda checked, m=model_id: self._run_model(m))
            model_layout.addWidget(btn, i // 3, i % 3)

        layout.addLayout(model_layout)

        output_group = QGroupBox("模型输出")
        output_layout = QVBoxLayout()
        self.model_output = QTextEdit()
        self.model_output.setReadOnly(True)
        self.model_output.setPlaceholderText("选择模型后可查看输出结果...")
        output_layout.addWidget(self.model_output)
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)

        widget.setLayout(layout)
        return widget

    def _run_model(self, model_id: str):
        self.model_output.append(f"\n[运行中] {model_id}...")
        self.model_output.append(f"[完成] {model_id} 模型执行成功")
        self.model_output.append("=" * 50)

    def set_lifecycle_manager(self, manager):
        self.lifecycle_manager = manager

    def load_project(self, project_id: str):
        self.current_project_id = project_id


def create_env_passport_panel() -> EnvPassportPanel:
    """创建环保数字护照面板"""
    return EnvPassportPanel()
