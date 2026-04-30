"""
环评报告生成监控面板
====================

PyQt6 实现的可视化生成过程监控界面：
1. 分阶段进度可视化（树状结构）
2. 实时内容预览（Markdown渲染）
3. 缺失信息智能提示
4. WebSocket实时更新

Author: Hermes Desktop EIA System
"""

import json
import asyncio
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime

from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, QObject, QSize,
    QPropertyAnimation, QEasingCurve
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeWidget, QTreeWidgetItem, QLabel, QProgressBar,
    QTextEdit, QPushButton, QFrame, QScrollArea,
    QStackedWidget, QToolButton, QMenu, QBadge,
    QCardWidget, QListWidget, QListWidgetItem,
    QStatusBar, QGroupBox, QFormLayout, QLineEdit,
    QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
    QTabWidget, QTableWidget, QTableWidgetItem,
    QDialog, QDialogButtonBox, QMessageBox,
    QGraphicsView, QGraphicsScene, QGraphicsRectItem,
    QGraphicsTextItem, QGraphicsSimpleTextItem,
    QColorDialog, QFontDialog, QFileDialog,
    QProgressDialog
)
from PyQt6.QtGui import (
    QFont, QColor, QPalette, QIcon, QAction,
    QTextCursor, QTextCharFormat, QTextBlockFormat,
    QBrush, QPen, QPainter, QLinearGradient,
    QTextDocument, QTextOption, QPixmap, QPicture
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6 import QtCore

# 本地导入
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from client.src.business.living_tree_ai.eia_system.generation_monitor import (
        GenerationMonitor, GenerationStage, StageStatus, StepStatus,
        GenerationStep, StageProgress, get_or_create_monitor,
        start_report_generation, update_stage, update_step
    )
    from client.src.business.living_tree_ai.eia_system.report_completeness_auditor import (
        ReportCompletenessAuditor, MissingItem, MissingLevel, MissingCategory,
        AuditResult, get_auditor, audit_report_completeness
    )
    from client.src.business.living_tree_ai.eia_system.computation_fingerprint import (
        create_fingerprint_generator
    )
    EIA_SYSTEM_AVAILABLE = True
except ImportError as e:
    EIA_SYSTEM_AVAILABLE = False
    print(f"警告: EIA系统模块导入失败: {e}")


# ============ 样式定义 ============

PANEL_STYLE = """
/* 主面板 */
QLabel#stageTitle {
    font-size: 14px;
    font-weight: bold;
    color: #2c3e50;
}

QLabel#stepTitle {
    font-size: 12px;
    color: #34495e;
}

QLabel#statusLabel {
    font-size: 11px;
}

QLabel#messageLabel {
    font-size: 10px;
    color: #7f8c8d;
}

/* 进度条 */
QProgressBar {
    border: none;
    border-radius: 4px;
    background-color: #ecf0f1;
    height: 6px;
    text-align: center;
}

QProgressBar::chunk {
    border-radius: 4px;
    background-color: #3498db;
}

QProgressBar[level="warning"]::chunk {
    background-color: #f39c12;
}

QProgressBar[level="error"]::chunk {
    background-color: #e74c3c;
}

QProgressBar[level="success"]::chunk {
    background-color: #27ae60;
}

/* 卡片样式 */
QFrame#stepCard {
    background-color: white;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 8px;
}

QFrame#stepCard[status="running"] {
    border: 2px solid #3498db;
    background-color: #ebf5fb;
}

QFrame#stepCard[status="completed"] {
    border: 1px solid #27ae60;
    background-color: #eafaf1;
}

QFrame#stepCard[status="warning"] {
    border: 1px solid #f39c12;
    background-color: #fef9e7;
}

QFrame#stepCard[status="error"] {
    border: 1px solid #e74c3c;
    background-color: #fdedec;
}

/* 按钮样式 */
QPushButton#actionBtn {
    background-color: #3498db;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 6px 12px;
    font-size: 11px;
}

QPushButton#actionBtn:hover {
    background-color: #2980b9;
}

QPushButton#actionBtn:disabled {
    background-color: #bdc3c7;
}

/* 缺失项提示卡片 */
QFrame#missingCard {
    background-color: white;
    border-radius: 6px;
    padding: 10px;
    margin: 4px;
}

QFrame#missingCard[level="fatal"] {
    border-left: 4px solid #e74c3c;
    background-color: #fdedec;
}

QFrame#missingCard[level="important"] {
    border-left: 4px solid #f39c12;
    background-color: #fef9e7;
}

QFrame#missingCard[level="suggestion"] {
    border-left: 4px solid #3498db;
    background-color: #ebf5fb;
}

QFrame#missingCard[level="format"] {
    border-left: 4px solid #27ae60;
    background-color: #eafaf1;
}

/* 状态指示器 */
QLabel#statusIndicator {
    font-size: 16px;
}
"""


# ============ 辅助组件 ============

class StatusIndicator(QLabel):
    """状态指示器"""

    STATUS_ICONS = {
        StepStatus.PENDING: ("⏳", "#95a5a6"),
        StepStatus.RUNNING: ("🔄", "#3498db"),
        StepStatus.COMPLETED: ("✅", "#27ae60"),
        StepStatus.WARNING: ("⚠️", "#f39c12"),
        StepStatus.ERROR: ("❌", "#e74c3c"),
        StepStatus.SKIPPED: ("⏭️", "#95a5a6"),
    }

    def __init__(self, status: StepStatus = StepStatus.PENDING, parent=None):
        super().__init__(parent)
        self._status = status
        self.update_status(status)

    def update_status(self, status: StepStatus):
        """更新状态"""
        self._status = status
        icon, color = self.STATUS_ICONS.get(status, ("❓", "#95a5a6"))
        self.setText(icon)
        self.setStyleSheet(f"color: {color};")


class AnimatedProgressBar(QProgressBar):
    """带动画的进度条"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._animation = QPropertyAnimation(self, b"value")
        self._animation.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._animation.setDuration(300)

    def set_value_smooth(self, value: int):
        """平滑设置值"""
        self._animation.stop()
        self._animation.setStartValue(self.value())
        self._animation.setEndValue(value)
        self._animation.start()


class MarkdownRenderer:
    """简单的Markdown渲染器"""

    @staticmethod
    def to_html(text: str) -> str:
        """将Markdown转换为HTML"""
        import re

        # 转义HTML
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        # 代码块
        text = re.sub(r'```(\w*)\n(.*?)\n```', r'<pre><code class="\1">\2</code></pre>', text, flags=re.DOTALL)

        # 行内代码
        text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)

        # 标题
        for i in range(6, 0, -1):
            text = re.sub(r'^' + r'#' * i + r'\s+(.+)$', rf'<h{i}>\1</h{i}>', text, flags=re.MULTILINE)

        # 粗体
        text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)

        # 斜体
        text = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', text)

        # 链接
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)

        # 列表
        text = re.sub(r'^- (.+)$', r'<li>\1</li>', text, flags=re.MULTILINE)
        text = text.replace("<li>", "<ul><li>", 1)
        text = text.replace("</li>", "</li></ul>", 1)

        # 换行
        text = text.replace("\n\n", "</p><p>")
        text = f"<p>{text}</p>"

        return text


# ============ 步骤卡片组件 ============

class StepCard(QFrame):
    """步骤卡片"""

    clicked = pyqtSignal(str)  # step_id

    def __init__(self, step: GenerationStep, parent=None):
        super().__init__(parent)
        self.step_id = step.id
        self._setup_ui(step)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def _setup_ui(self, step: GenerationStep):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # 顶部：状态指示器 + 步骤名称
        top_layout = QHBoxLayout()
        top_layout.setSpacing(8)

        self.status_indicator = StatusIndicator(step.status)
        top_layout.addWidget(self.status_indicator)

        self.name_label = QLabel(step.name)
        self.name_label.setObjectName("stepTitle")
        font = QFont()
        font.setWeight(QFont.Weight.Bold)
        self.name_label.setFont(font)
        top_layout.addWidget(self.name_label, 1)

        # 进度标签
        self.progress_label = QLabel("0%")
        self.progress_label.setObjectName("statusLabel")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        top_layout.addWidget(self.progress_label)

        layout.addLayout(top_layout)

        # 进度条
        self.progress_bar = AnimatedProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(int(step.progress * 100))
        layout.addWidget(self.progress_bar)

        # 消息
        if step.message:
            self.message_label = QLabel(step.message)
            self.message_label.setObjectName("messageLabel")
            self.message_label.setWordWrap(True)
            layout.addWidget(self.message_label)

        # 警告/错误信息
        if step.warning:
            self.warning_label = QLabel(f"⚠️ {step.warning}")
            self.warning_label.setStyleSheet("color: #f39c12; font-size: 10px;")
            self.warning_label.setWordWrap(True)
            layout.addWidget(self.warning_label)

        if step.error:
            self.error_label = QLabel(f"❌ {step.error}")
            self.error_label.setStyleSheet("color: #e74c3c; font-size: 10px;")
            self.error_label.setWordWrap(True)
            layout.addWidget(self.error_label)

        self.update_style(step.status)

    def update_step(self, step: GenerationStep):
        """更新步骤"""
        self.status_indicator.update_status(step.status)
        self.progress_bar.set_value_smooth(int(step.progress * 100))
        self.progress_label.setText(f"{int(step.progress * 100)}%")

        if step.message and hasattr(self, 'message_label'):
            self.message_label.setText(step.message)

        if step.warning and not hasattr(self, 'warning_label'):
            self.warning_label = QLabel(f"⚠️ {step.warning}")
            self.warning_label.setStyleSheet("color: #f39c12; font-size: 10px;")
            self.layout().addWidget(self.warning_label)
        elif step.warning:
            self.warning_label.setText(f"⚠️ {step.warning}")

        self.update_style(step.status)

    def update_style(self, status: StepStatus):
        """更新样式"""
        status_map = {
            StepStatus.PENDING: "pending",
            StepStatus.RUNNING: "running",
            StepStatus.COMPLETED: "completed",
            StepStatus.WARNING: "warning",
            StepStatus.ERROR: "error",
            StepStatus.SKIPPED: "pending"
        }
        self.setProperty("status", status_map.get(status, "pending"))
        self.setStyle(QApplication.style())
        self.style().unpolish(self)
        self.style().polish(self)


# ============ 阶段卡片组件 ============

class StageCard(QFrame):
    """阶段卡片"""

    def __init__(self, stage: StageProgress, parent=None):
        super().__init__(parent)
        self.stage_id = stage.stage.value
        self._setup_ui(stage)

    def _setup_ui(self, stage: StageProgress):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(10)

        # 标题行
        title_layout = QHBoxLayout()

        self.icon_label = QLabel(self._get_stage_icon(stage.stage))
        self.icon_label.setFont(QFont("", 16))
        title_layout.addWidget(self.icon_label)

        self.title_label = QLabel(self._get_stage_name(stage.stage))
        self.title_label.setObjectName("stageTitle")
        font = QFont()
        font.setWeight(QFont.Weight.Bold)
        font.setPointSize(13)
        self.title_label.setFont(font)
        title_layout.addWidget(self.title_label, 1)

        self.status_label = QLabel(self._get_status_text(stage.status))
        self.status_label.setObjectName("statusLabel")
        title_layout.addWidget(self.status_label)

        layout.addLayout(title_layout)

        # 总体进度
        progress_layout = QHBoxLayout()
        progress_layout.setSpacing(10)

        self.progress_bar = AnimatedProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(int(stage.progress * 100))
        self.progress_bar.setFixedHeight(8)
        progress_layout.addWidget(self.progress_bar, 1)

        self.progress_pct = QLabel(f"{int(stage.progress * 100)}%")
        self.progress_pct.setObjectName("statusLabel")
        self.progress_pct.setFixedWidth(40)
        progress_layout.addWidget(self.progress_pct)

        layout.addLayout(progress_layout)

        # 消息
        if stage.message and stage.message != "等待开始":
            self.message_label = QLabel(stage.message)
            self.message_label.setObjectName("messageLabel")
            self.message_label.setWordWrap(True)
            layout.addWidget(self.message_label)

        # 步骤列表容器
        self.steps_container = QVBoxLayout()
        self.steps_container.setSpacing(6)
        layout.addLayout(self.steps_container)

        # 添加步骤卡片
        for step in stage.steps:
            step_card = StepCard(step)
            self.steps_container.addWidget(step_card)

        self._update_status_style(stage.status)

    def _get_stage_icon(self, stage: GenerationStage) -> str:
        """获取阶段图标"""
        icons = {
            GenerationStage.ANALYSIS: "🔍",
            GenerationStage.MODELING: "🧮",
            GenerationStage.WRITING: "📄",
            GenerationStage.AUDIT: "✅",
            GenerationStage.EXPORT: "💾"
        }
        return icons.get(stage, "📋")

    def _get_stage_name(self, stage: GenerationStage) -> str:
        """获取阶段名称"""
        names = {
            GenerationStage.ANALYSIS: "分析阶段",
            GenerationStage.MODELING: "建模阶段",
            GenerationStage.WRITING: "写作阶段",
            GenerationStage.AUDIT: "审计阶段",
            GenerationStage.EXPORT: "导出阶段"
        }
        return names.get(stage, str(stage.value))

    def _get_status_text(self, status: StageStatus) -> str:
        """获取状态文本"""
        texts = {
            StageStatus.PENDING: "⏳ 等待",
            StageStatus.RUNNING: "🔄 进行中",
            StageStatus.COMPLETED: "✅ 完成",
            StageStatus.FAILED: "❌ 失败",
            StageStatus.SKIPPED: "⏭️ 跳过"
        }
        return texts.get(status, "")

    def _get_status_color(self, status: StageStatus) -> str:
        """获取状态颜色"""
        colors = {
            StageStatus.PENDING: "#95a5a6",
            StageStatus.RUNNING: "#3498db",
            StageStatus.COMPLETED: "#27ae60",
            StageStatus.FAILED: "#e74c3c",
            StageStatus.SKIPPED: "#95a5a6"
        }
        return colors.get(status, "#95a5a6")

    def _update_status_style(self, status: StageStatus):
        """更新状态样式"""
        color = self._get_status_color(status)
        self.status_label.setStyleSheet(f"color: {color}; font-weight: bold;")

    def update_stage(self, stage: StageProgress):
        """更新阶段"""
        self.status_label.setText(self._get_status_text(stage.status))
        self.progress_bar.set_value_smooth(int(stage.progress * 100))
        self.progress_pct.setText(f"{int(stage.progress * 100)}%")

        if hasattr(self, 'message_label') and stage.message:
            self.message_label.setText(stage.message)

        self._update_status_style(stage.status)

        # 更新步骤
        for i, step in enumerate(stage.steps):
            if i < self.steps_container.count():
                step_card = self.steps_container.itemAt(i).widget()
                if isinstance(step_card, StepCard):
                    step_card.update_step(step)


# ============ 缺失项提示卡片 ============

class MissingItemCard(QFrame):
    """缺失项提示卡片"""

    action_clicked = pyqtSignal(str, str)  # item_id, action

    LEVEL_CONFIG = {
        MissingLevel.FATAL: {
            "icon": "🔴",
            "color": "#e74c3c",
            "bg": "#fdedec",
            "label": "致命缺失"
        },
        MissingLevel.IMPORTANT: {
            "icon": "🟡",
            "color": "#f39c12",
            "bg": "#fef9e7",
            "label": "重要提示"
        },
        MissingLevel.SUGGESTION: {
            "icon": "🔵",
            "color": "#3498db",
            "bg": "#ebf5fb",
            "label": "优化建议"
        },
        MissingLevel.FORMAT: {
            "icon": "🟢",
            "color": "#27ae60",
            "bg": "#eafaf1",
            "label": "格式提醒"
        }
    }

    def __init__(self, item: MissingItem, parent=None):
        super().__init__(parent)
        self.item_id = item.id
        self._setup_ui(item)

    def _setup_ui(self, item: MissingItem):
        """设置UI"""
        config = self.LEVEL_CONFIG.get(item.level, self.LEVEL_CONFIG[MissingLevel.FORMAT])

        self.setObjectName("missingCard")
        self.setProperty("level", item.level.value)
        self.setStyleSheet(f"""
            QFrame#missingCard {{
                background-color: {config['bg']};
                border-left: 4px solid {config['color']};
                border-radius: 6px;
                padding: 10px;
                margin: 4px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # 标题行
        header_layout = QHBoxLayout()

        icon_label = QLabel(config['icon'])
        icon_label.setFont(QFont("", 14))
        header_layout.addWidget(icon_label)

        title_label = QLabel(item.name)
        title_label.setFont(QFont("", 10, QFont.Weight.Bold))
        header_layout.addWidget(title_label, 1)

        level_label = QLabel(config['label'])
        level_label.setStyleSheet(f"color: {config['color']}; font-size: 10px;")
        header_layout.addWidget(level_label)

        layout.addLayout(header_layout)

        # 描述
        desc_label = QLabel(item.description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #34495e; font-size: 11px;")
        layout.addWidget(desc_label)

        # 位置
        if item.location:
            loc_label = QLabel(f"📍 位置: {item.location}")
            loc_label.setStyleSheet("color: #7f8c8d; font-size: 10px;")
            layout.addWidget(loc_label)

        # 建议按钮
        if item.suggestions:
            sug_layout = QHBoxLayout()
            sug_layout.setSpacing(6)

            for sug in item.suggestions[:3]:  # 最多显示3个建议
                btn = QPushButton(f"{sug.icon} {sug.label}")
                btn.setObjectName("actionBtn")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(lambda checked, a=sug.action: self._on_action_clicked(a))
                sug_layout.addWidget(btn)

            sug_layout.addStretch()
            layout.addLayout(sug_layout)

    def _on_action_clicked(self, action: str):
        """处理动作点击"""
        self.action_clicked.emit(self.item_id, action)


# ============ 实时预览组件 ============

class LivePreviewPanel(QFrame):
    """实时预览面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._init_web_view()

    def _setup_ui(self):
        """设置UI"""
        self.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 标题栏
        header = QFrame()
        header.setStyleSheet("background-color: #f8f9fa; border-bottom: 1px solid #e0e0e0;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(15, 10, 15, 10)

        title = QLabel("📝 实时预览")
        title.setFont(QFont("", 11, QFont.Weight.Bold))
        header_layout.addWidget(title)

        self.section_label = QLabel("等待生成...")
        self.section_label.setStyleSheet("color: #7f8c8d; font-size: 10px;")
        header_layout.addWidget(self.section_label, 1)

        self.status_indicator = QLabel("⏳")
        header_layout.addWidget(self.status_indicator)

        layout.addWidget(header)

        # 内容区域
        self.content_stack = QStackedWidget()
        layout.addWidget(self.content_stack)

        # 文本预览（用于不支持WebEngine的情况）
        self.text_preview = QTextEdit()
        self.text_preview.setReadOnly(True)
        self.text_preview.setStyleSheet("""
            QTextEdit {
                border: none;
                padding: 15px;
                font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
                font-size: 12px;
                line-height: 1.6;
                color: #2c3e50;
            }
        """)
        self.content_stack.addWidget(self.text_preview)

        # WebEngine预览
        self.web_preview = QWebEngineView()
        self.content_stack.addWidget(self.web_preview)

        # 状态栏
        footer = QFrame()
        footer.setStyleSheet("background-color: #f8f9fa; border-top: 1px solid #e0e0e0;")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(15, 8, 15, 8)

        self.timestamp_label = QLabel("")
        self.timestamp_label.setStyleSheet("color: #95a5a6; font-size: 10px;")
        footer_layout.addWidget(self.timestamp_label)

        footer_layout.addStretch()

        self.hint_label = QLabel("💡 点击「生成报告」开始")
        self.hint_label.setStyleSheet("color: #3498db; font-size: 10px;")
        footer_layout.addWidget(self.hint_label)

        layout.addWidget(footer)

    def _init_web_view(self):
        """初始化WebView"""
        # 设置WebEngine
        settings = self.web_preview.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)

        # 加载初始HTML
        initial_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {
                    font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
                    padding: 20px;
                    line-height: 1.8;
                    color: #2c3e50;
                    background-color: white;
                }
                h1 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
                h2 { color: #34495e; margin-top: 30px; }
                h3 { color: #7f8c8d; }
                code { background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }
                pre { background: #f8f9fa; padding: 15px; border-radius: 8px; overflow-x: auto; }
                .status-box {
                    background: #ebf5fb;
                    border-left: 4px solid #3498db;
                    padding: 10px 15px;
                    margin: 10px 0;
                    border-radius: 4px;
                }
                .warning-box {
                    background: #fef9e7;
                    border-left: 4px solid #f39c12;
                    padding: 10px 15px;
                    margin: 10px 0;
                    border-radius: 4px;
                }
                table { border-collapse: collapse; width: 100%; margin: 15px 0; }
                th, td { border: 1px solid #ddd; padding: 10px; text-align: left; }
                th { background-color: #3498db; color: white; }
                tr:nth-child(even) { background-color: #f9f9f9; }
            </style>
        </head>
        <body>
            <h1>📋 环评报告预览</h1>
            <div class="status-box">
                <strong>⏳ 等待生成...</strong><br>
                点击「生成报告」按钮开始自动生成报告
            </div>
            <p style="color: #95a5a6; text-align: center; margin-top: 50px;">
                报告内容将在此处实时显示
            </p>
        </body>
        </html>
        """
        self.web_preview.setHtml(initial_html)

    def update_preview(self, section: str, content: str, status: str):
        """更新预览内容"""
        self.section_label.setText(f"[{section}]")

        # 状态图标
        status_map = {
            "generating": ("🔄", "#3498db"),
            "completed": ("✅", "#27ae60"),
            "warning": ("⚠️", "#f39c12"),
            "error": ("❌", "#e74c3c")
        }
        icon, color = status_map.get(status, ("📝", "#2c3e50"))
        self.status_indicator.setText(icon)
        self.hint_label.setText(f"状态: {status}")

        # 更新文本预览
        self.text_preview.append(f"\n{'='*40}")
        self.text_preview.append(f"【{section}】 - {icon}")
        self.text_preview.append(f"{'='*40}\n")
        self.text_preview.append(content)
        self.text_preview.append("\n")

        # 滚动到底部
        cursor = self.text_preview.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.text_preview.setTextCursor(cursor)

        # 更新时间戳
        self.timestamp_label.setText(datetime.now().strftime("%H:%M:%S"))

    def show_completed(self):
        """显示完成状态"""
        self.status_indicator.setText("✅")
        self.section_label.setText("生成完成")
        self.hint_label.setText("✅ 报告已生成，可导出")


# ============ 缺失项提示面板 ============

class MissingItemsPanel(QFrame):
    """缺失项提示面板"""

    action_clicked = pyqtSignal(str, str)  # item_id, action

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        self.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 标题栏
        header_layout = QHBoxLayout()

        title = QLabel("⚠️ 缺失信息提示")
        title.setFont(QFont("", 11, QFont.Weight.Bold))
        header_layout.addWidget(title)

        self.count_label = QLabel("0 项")
        self.count_label.setStyleSheet("""
            background-color: #e74c3c;
            color: white;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 10px;
        """)
        header_layout.addWidget(self.count_label)

        self.audit_btn = QPushButton("🔍 重新审计")
        self.audit_btn.setObjectName("actionBtn")
        self.audit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        header_layout.addWidget(self.audit_btn)

        layout.addLayout(header_layout)

        # 缺失项列表
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("border: none;")
        self.scroll_area.setMinimumHeight(200)

        self.items_container = QWidget()
        self.items_layout = QVBoxLayout(self.items_container)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(8)
        self.items_layout.addStretch()

        self.scroll_area.setWidget(self.items_container)
        layout.addWidget(self.scroll_area)

    def set_audit_result(self, result: AuditResult):
        """设置审计结果"""
        # 更新计数
        if result.fatal_count > 0:
            self.count_label.setText(f"{result.fatal_count} 项致命")
            self.count_label.setStyleSheet("background-color: #e74c3c; color: white; padding: 2px 8px; border-radius: 10px; font-size: 10px;")
        elif result.important_count > 0:
            self.count_label.setText(f"{result.important_count} 项重要")
            self.count_label.setStyleSheet("background-color: #f39c12; color: white; padding: 2px 8px; border-radius: 10px; font-size: 10px;")
        elif result.suggestion_count > 0:
            self.count_label.setText(f"{result.suggestion_count} 项建议")
            self.count_label.setStyleSheet("background-color: #3498db; color: white; padding: 2px 8px; border-radius: 10px; font-size: 10px;")
        else:
            self.count_label.setText("无缺失")
            self.count_label.setStyleSheet("background-color: #27ae60; color: white; padding: 2px 8px; border-radius: 10px; font-size: 10px;")

        # 清空现有项
        while self.items_layout.count() > 1:
            item = self.items_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 添加缺失项卡片
        for item in result.items:
            card = MissingItemCard(item)
            card.action_clicked.connect(self._on_action_clicked)
            self.items_layout.insertWidget(self.items_layout.count() - 1, card)

    def clear(self):
        """清空"""
        while self.items_layout.count() > 1:
            item = self.items_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.count_label.setText("0 项")

    def _on_action_clicked(self, item_id: str, action: str):
        """处理动作点击"""
        self.action_clicked.emit(item_id, action)


# ============ 主监控面板 ============

class GenerationMonitorPanel(QFrame):
    """
    环评报告生成监控面板

    功能：
    1. 分阶段进度可视化
    2. 实时内容预览
    3. 缺失信息智能提示
    4. 一键审计
    """

    # 信号
    generation_started = pyqtSignal(str, str)  # project_id, project_name
    generation_completed = pyqtSignal(str, bool)  # project_id, success
    action_requested = pyqtSignal(str, str, dict)  # action, item_id, params

    def __init__(self, project_id: str = "", project_name: str = "", parent=None):
        super().__init__(parent)
        self.project_id = project_id
        self.project_name = project_name
        self.monitor: Optional[GenerationMonitor] = None
        self._setup_ui()
        self._init_monitor()

    def _setup_ui(self):
        """设置UI"""
        self.setStyleSheet(PANEL_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # 顶部：标题和项目信息
        header = QFrame()
        header_layout = QHBoxLayout(header)

        title = QLabel("📊 环评报告生成监控")
        title.setFont(QFont("", 14, QFont.Weight.Bold))
        header_layout.addWidget(title)

        header_layout.addStretch()

        # 项目信息
        if self.project_name:
            project_label = QLabel(f"📁 {self.project_name}")
            project_label.setStyleSheet("color: #7f8c8d; font-size: 12px;")
            header_layout.addWidget(project_label)

        # 总进度
        progress_layout = QHBoxLayout()
        progress_layout.setSpacing(10)

        self.total_progress = AnimatedProgressBar()
        self.total_progress.setRange(0, 100)
        self.total_progress.setValue(0)
        self.total_progress.setFixedHeight(10)
        progress_layout.addWidget(self.total_progress, 1)

        self.total_progress_label = QLabel("0%")
        self.total_progress_label.setFont(QFont("", 11, QFont.Weight.Bold))
        progress_layout.addWidget(self.total_progress_label)

        layout.addWidget(header)
        layout.addLayout(progress_layout)

        # 主内容区：左右分栏
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：阶段进度
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)

        left_title = QLabel("📋 生成进度")
        left_title.setFont(QFont("", 12, QFont.Weight.Bold))
        left_layout.addWidget(left_title)

        self.stages_scroll = QScrollArea()
        self.stages_scroll.setWidgetResizable(True)
        self.stages_scroll.setStyleSheet("border: none;")
        self.stages_container = QWidget()
        self.stages_layout = QVBoxLayout(self.stages_container)
        self.stages_layout.setContentsMargins(0, 0, 0, 0)
        self.stages_layout.setSpacing(12)
        self.stages_layout.addStretch()

        self.stages_scroll.setWidget(self.stages_container)
        left_layout.addWidget(self.stages_scroll)

        # 底部操作按钮
        actions_layout = QHBoxLayout()

        self.start_btn = QPushButton("🚀 开始生成")
        self.start_btn.setObjectName("actionBtn")
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.clicked.connect(self._on_start_generation)
        actions_layout.addWidget(self.start_btn)

        self.audit_btn = QPushButton("🔍 完整性审计")
        self.audit_btn.setObjectName("actionBtn")
        self.audit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.audit_btn.clicked.connect(self._on_run_audit)
        actions_layout.addWidget(self.audit_btn)

        left_layout.addLayout(actions_layout)

        main_splitter.addWidget(left_panel)
        main_splitter.setStretchFactor(0, 1)

        # 右侧：预览 + 缺失提示
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)

        # 实时预览
        self.preview_panel = LivePreviewPanel()
        right_layout.addWidget(self.preview_panel, 2)

        # 缺失项提示
        self.missing_panel = MissingItemsPanel()
        self.missing_panel.action_clicked.connect(self._on_missing_action)
        right_layout.addWidget(self.missing_panel, 1)

        main_splitter.addWidget(right_panel)
        main_splitter.setStretchFactor(1, 1)

        # 设置分割比例
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 1)

        layout.addWidget(main_splitter)

    def _init_monitor(self):
        """初始化监控器"""
        if EIA_SYSTEM_AVAILABLE and self.project_id:
            self.monitor = get_or_create_monitor(self.project_id, self.project_name)

            # 初始化阶段卡片
            if self.monitor:
                self._refresh_stages()

    def _refresh_stages(self):
        """刷新阶段显示"""
        if not self.monitor:
            return

        # 清空现有卡片
        while self.stages_layout.count() > 1:
            item = self.stages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 重新创建
        self._create_stage_cards()

    def _create_stage_cards(self):
        """创建阶段卡片"""
        if not self.monitor:
            return

        stages = self.monitor.stages
        for stage_key in ["analysis", "modeling", "writing", "audit", "export"]:
            if stage_key in stages:
                stage_card = StageCard(stages[stage_key])
                self.stages_layout.insertWidget(self.stages_layout.count() - 1, stage_card)

    def _on_start_generation(self):
        """开始生成"""
        if not self.project_id:
            self.project_id = "default_project"
        if not self.project_name:
            self.project_name = "新项目"

        self.generation_started.emit(self.project_id, self.project_name)

        # 更新按钮状态
        self.start_btn.setEnabled(False)
        self.start_btn.setText("🔄 生成中...")

        # TODO: 连接实际的生成过程

    def _on_run_audit(self):
        """运行审计"""
        # 模拟审计结果
        if EIA_SYSTEM_AVAILABLE:
            # TODO: 实际调用审计
            auditor = get_auditor()
            # 模拟数据
            mock_report_data = {
                "project_id": self.project_id,
                "basic_info": {},
                "pollution_sources": {},
                "has_air_model": True
            }
            mock_project_context = {
                "industry_type": "化工",
                "location": "某市"
            }
            result = auditor.audit_report(mock_report_data, mock_project_context)
            self.missing_panel.set_audit_result(result)

    def _on_missing_action(self, item_id: str, action: str):
        """处理缺失项动作"""
        self.action_requested.emit("missing_action", item_id, {"action": action})

    def update_progress(self, data: dict):
        """更新进度"""
        if not data:
            return

        data_type = data.get("type")

        if data_type == "stage_update":
            stage_key = data.get("stage")
            if self.monitor and stage_key in self.monitor.stages:
                stage = self.monitor.stages[stage_key]
                stage.status = StageStatus(data.get("status", "pending"))
                stage.progress = data.get("progress", 0)
                stage.message = data.get("message", "")

                # 更新总进度
                total = self.monitor._calculate_total_progress()
                self.total_progress.set_value_smooth(int(total * 100))
                self.total_progress_label.setText(f"{int(total * 100)}%")

        elif data_type == "step_update":
            # 更新步骤
            pass

        elif data_type == "preview_update":
            preview_data = data.get("data", {})
            self.preview_panel.update_preview(
                preview_data.get("section", ""),
                preview_data.get("content", ""),
                preview_data.get("status", "generating")
            )

        elif data_type == "generation_completed":
            self.start_btn.setEnabled(True)
            self.start_btn.setText("🚀 开始生成")
            self.preview_panel.show_completed()

    def set_project(self, project_id: str, project_name: str):
        """设置项目"""
        self.project_id = project_id
        self.project_name = project_name
        self._init_monitor()


# ============ 独立测试 ============

if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # 设置样式
    app.setStyle("Fusion")

    # 创建面板
    panel = GenerationMonitorPanel("test_001", "某化工厂项目")

    window = QWidget()
    layout = QVBoxLayout(window)
    layout.addWidget(panel)
    window.resize(1200, 800)
    window.show()

    sys.exit(app.exec())
