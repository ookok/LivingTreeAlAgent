"""
智能清理系统 PyQt6 UI 面板 - SmartCleanupPanel

功能:
1. 三级清理策略可视化 (即时/定期/归档)
2. 文件价值评估展示
3. 清理进度追踪
4. 清理历史记录
5. 清理报告生成

Author: Hermes Desktop Team
"""

import time
import psutil
from pathlib import Path
from typing import Optional, Dict, Any, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QProgressBar, QScrollArea,
    QTabWidget, QGroupBox, QCheckBox, QSpinBox,
    QSlider, QTextEdit, QListWidget, QListWidgetItem,
    QProgressDialog, QMessageBox, QDialog, QTableWidget,
    QTableWidgetItem, QHeaderView, QStatusBar
)
from PyQt6.QtCore import (
    Qt, QSize, QTimer, pyqtSignal, QThread,
    QPropertyAnimation, QRect, QAbstractItemView
)
from PyQt6.QtGui import (
    QFont, QColor, QPalette, QIcon, QPainter, QBrush, QPen
)

# 导入智能清理核心
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from .business.smart_cleanup import (
    SmartCleanupEngine, CleanupLevel, CleanupDecision,
    FileCategory, CleanupConfig, FileMetadata, CleanupCandidate
)


# ============ 样式定义 ============

SMART_CLEANUP_STYLE = """
/* 主面板 */
QWidget#smart_cleanup_panel {
    background-color: #1a1a2e;
    color: #e0e0e0;
}

/* 标题 */
.panel-title {
    font-size: 20px;
    font-weight: bold;
    color: #ffffff;
}

/* 卡片 */
.cleanup-card {
    background-color: #252540;
    border-radius: 12px;
    padding: 16px;
    margin: 8px;
}

/* 统计卡片 */
.stat-card {
    background-color: #2d2d44;
    border-radius: 8px;
    padding: 12px;
    min-width: 120px;
}

/* 进度条 */
QProgressBar {
    border: none;
    border-radius: 4px;
    background-color: #3d3d54;
    height: 8px;
}
QProgressBar::chunk {
    background-color: #2563eb;
    border-radius: 4px;
}

/* 按钮样式 */
.cleanup-btn {
    background-color: #2563eb;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-size: 14px;
}
.cleanup-btn:hover {
    background-color: #1d4ed8;
}
.cleanup-btn:pressed {
    background-color: #1e40af;
}
.cleanup-btn:disabled {
    background-color: #4b5563;
    color: #9ca3af;
}

.action-btn {
    background-color: #374151;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
}
.action-btn:hover {
    background-color: #4b5563;
}

/* 列表 */
QListWidget {
    background-color: #1f1f35;
    border: none;
    border-radius: 8px;
    padding: 8px;
}
QListWidget::item {
    padding: 8px;
    border-radius: 4px;
}
QListWidget::item:selected {
    background-color: #2563eb;
}

/* 标签页 */
QTabWidget::pane {
    border: none;
    background-color: #1a1a2e;
}
QTabBar::tab {
    background-color: #252540;
    color: #a0a0c0;
    padding: 10px 20px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
}
QTabBar::tab:selected {
    background-color: #2d2d44;
    color: #ffffff;
}
QTabBar::tab:hover {
    background-color: #3d3d54;
}

/* 复选框 */
QCheckBox {
    color: #e0e0e0;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
}

/* 滚动条 */
QScrollBar:vertical {
    background-color: transparent;
    width: 8px;
}
QScrollBar::handle:vertical {
    background-color: #3d3d54;
    border-radius: 4px;
}
"""


class StatCard(QFrame):
    """统计卡片组件"""

    def __init__(self, title: str, value: str, icon: str = "💾", parent=None):
        super().__init__(parent)
        self.title = title
        self.value = value
        self.icon = icon
        self.setup_ui()

    def setup_ui(self):
        """设置UI"""
        self.setStyleSheet("""
            QFrame {
                background-color: #2d2d44;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        self.setMinimumWidth(140)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # 图标和标题
        header_layout = QHBoxLayout()
        icon_label = QLabel(self.icon)
        icon_label.setStyleSheet("font-size: 20px;")
        title_label = QLabel(self.title)
        title_label.setStyleSheet("color: #a0a0c0; font-size: 12px;")
        header_layout.addWidget(icon_label)
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        # 值
        self.value_label = QLabel(self.value)
        self.value_label.setStyleSheet("""
            color: #ffffff;
            font-size: 24px;
            font-weight: bold;
        """)

        layout.addLayout(header_layout)
        layout.addWidget(self.value_label)

    def update_value(self, value: str):
        """更新值"""
        self.value_label.setText(value)


class DiskUsageWidget(QFrame):
    """磁盘使用情况组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.update_usage()

    def setup_ui(self):
        """设置UI"""
        self.setStyleSheet("""
            QFrame {
                background-color: #252540;
                border-radius: 12px;
                padding: 16px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 标题
        title_label = QLabel("💾 磁盘空间")
        title_label.setStyleSheet("color: #ffffff; font-size: 16px; font-weight: bold;")
        layout.addWidget(title_label)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 6px;
                background-color: #3d3d54;
                height: 16px;
                text-align: center;
                color: white;
            }
            QProgressBar::chunk {
                background-color: #2563eb;
                border-radius: 6px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # 统计信息
        self.stats_layout = QHBoxLayout()
        self.stats_layout.setSpacing(20)

        self.total_label = QLabel("总空间: --")
        self.used_label = QLabel("已用: --")
        self.free_label = QLabel("空闲: --")

        for label in [self.total_label, self.used_label, self.free_label]:
            label.setStyleSheet("color: #a0a0c0; font-size: 12px;")
            self.stats_layout.addWidget(label)

        self.stats_layout.addStretch()
        layout.addLayout(self.stats_layout)

        # 定时更新
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_usage)
        self.timer.start(5000)  # 每5秒更新

    def update_usage(self):
        """更新磁盘使用情况"""
        try:
            usage = psutil.disk_usage('/')

            percent = usage.percent
            self.progress_bar.setValue(int(percent))

            # 根据使用率设置颜色
            if percent >= 90:
                self.progress_bar.setFormat(f"危险! {percent:.1f}% 已使用")
                self.progress_bar.setStyleSheet("""
                    QProgressBar {
                        border: none;
                        border-radius: 6px;
                        background-color: #3d3d54;
                        height: 16px;
                        text-align: center;
                        color: white;
                    }
                    QProgressBar::chunk {
                        background-color: #dc2626;
                        border-radius: 6px;
                    }
                """)
            elif percent >= 80:
                self.progress_bar.setFormat(f"警告 {percent:.1f}% 已使用")
                self.progress_bar.setStyleSheet("""
                    QProgressBar {
                        border: none;
                        border-radius: 6px;
                        background-color: #3d3d54;
                        height: 16px;
                        text-align: center;
                        color: white;
                    }
                    QProgressBar::chunk {
                        background-color: #f59e0b;
                        border-radius: 6px;
                    }
                """)
            else:
                self.progress_bar.setFormat(f"{percent:.1f}% 已使用")
                self.progress_bar.setStyleSheet("""
                    QProgressBar {
                        border: none;
                        border-radius: 6px;
                        background-color: #3d3d54;
                        height: 16px;
                        text-align: center;
                        color: white;
                    }
                    QProgressBar::chunk {
                        background-color: #2563eb;
                        border-radius: 6px;
                    }
                """)

            self.total_label.setText(f"总空间: {usage.total / (1024**3):.2f} GB")
            self.used_label.setText(f"已用: {usage.used / (1024**3):.2f} GB")
            self.free_label.setText(f"空闲: {usage.free / (1024**3):.2f} GB")

        except Exception as e:
            self.total_label.setText("获取失败")


class CleanupCandidateWidget(QFrame):
    """清理候选文件组件"""

    def __init__(self, candidate: CleanupCandidate, parent=None):
        super().__init__(parent)
        self.candidate = candidate
        self.setup_ui()

    def setup_ui(self):
        """设置UI"""
        metadata = self.candidate.metadata

        self.setStyleSheet("""
            QFrame {
                background-color: #2d2d44;
                border-radius: 8px;
                padding: 8px;
                margin: 4px 0;
            }
            QFrame:hover {
                background-color: #3d3d54;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        # 文件图标
        icon_label = QLabel(self._get_category_icon(metadata.category))
        icon_label.setStyleSheet("font-size: 24px;")
        icon_label.setFixedWidth(36)
        layout.addWidget(icon_label)

        # 文件信息
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        name_label = QLabel(metadata.name)
        name_label.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: 500;")
        name_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        path_label = QLabel(metadata.path[:60] + "..." if len(metadata.path) > 60 else metadata.path)
        path_label.setStyleSheet("color: #888; font-size: 11px;")

        size_label = QLabel(self._format_size(metadata.size))
        size_label.setStyleSheet("color: #a0a0c0; font-size: 11px;")

        info_layout.addWidget(name_label)
        info_layout.addWidget(path_label)
        info_layout.addWidget(size_label)
        layout.addLayout(info_layout)

        # 决策标签
        decision_label = QLabel(self._get_decision_text(self.candidate.decision))
        decision_label.setStyleSheet(f"""
            background-color: {self._get_decision_color(self.candidate.decision)};
            color: white;
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 11px;
        """)
        layout.addWidget(decision_label)

        # 价值评分
        score_label = QLabel(f"评分: {metadata.value_score:.2f}")
        score_label.setStyleSheet("color: #a0a0c0; font-size: 11px;")
        layout.addWidget(score_label)

    def _get_category_icon(self, category: FileCategory) -> str:
        """获取类别图标"""
        icons = {
            FileCategory.TEMP_CACHE: "🗑️",
            FileCategory.MEMORY_BUFFER: "💨",
            FileCategory.SENSITIVE_DATA: "🔐",
            FileCategory.WORK_FILE: "📁",
            FileCategory.DOWNLOAD_CACHE: "📥",
            FileCategory.LOG_FILE: "📋",
            FileCategory.BUILD_ARTIFACT: "🏗️",
            FileCategory.ANALYSIS_RESULT: "📊",
            FileCategory.DRAFT_VERSION: "📝",
            FileCategory.FINAL_WORK: "⭐",
            FileCategory.PROJECT_BACKUP: "💾",
            FileCategory.OTHER: "📄",
        }
        return icons.get(category, "📄")

    def _get_decision_text(self, decision: CleanupDecision) -> str:
        """获取决策文本"""
        texts = {
            CleanupDecision.KEEP_FOREVER: "永久保留",
            CleanupDecision.KEEP_LONG: "长期保留",
            CleanupDecision.KEEP_MEDIUM: "中期保留",
            CleanupDecision.KEEP_SHORT: "短期保留",
            CleanupDecision.CLEAN_NOW: "立即清理",
            CleanupDecision.ARCHIVE: "归档",
            CleanupDecision.UNKNOWN: "未知",
        }
        return texts.get(decision, "未知")

    def _get_decision_color(self, decision: CleanupDecision) -> str:
        """获取决策颜色"""
        colors = {
            CleanupDecision.KEEP_FOREVER: "#059669",
            CleanupDecision.KEEP_LONG: "#2563eb",
            CleanupDecision.KEEP_MEDIUM: "#7c3aed",
            CleanupDecision.KEEP_SHORT: "#f59e0b",
            CleanupDecision.CLEAN_NOW: "#dc2626",
            CleanupDecision.ARCHIVE: "#0891b2",
            CleanupDecision.UNKNOWN: "#6b7280",
        }
        return colors.get(decision, "#6b7280")

    def _format_size(self, size: int) -> str:
        """格式化文件大小"""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.2f} GB"


class SmartCleanupPanel(QWidget):
    """
    智能清理系统主面板

    功能:
    - 总览: 磁盘使用情况、清理统计、快速操作
    - 分析: 文件扫描、价值评估、清理候选
    - 执行: 清理执行、进度追踪
    - 历史: 清理记录、恢复操作
    - 设置: 清理策略、阈值配置
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.engine = SmartCleanupEngine()
        self.cleanup_thread = None
        self.setup_ui()

    def setup_ui(self):
        """设置UI"""
        self.setStyleSheet(SMART_CLEANUP_STYLE)
        self.setObjectName("smart_cleanup_panel")

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        # 标题栏
        title_layout = QHBoxLayout()
        title_label = QLabel("🧹 智能清理系统")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #ffffff;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #374151;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #4b5563;
            }
        """)
        refresh_btn.clicked.connect(self._on_refresh)
        title_layout.addWidget(refresh_btn)

        main_layout.addLayout(title_layout)

        # 创建标签页
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_overview_tab(), "🏠 总览")
        self.tabs.addTab(self._create_analysis_tab(), "🔍 分析")
        self.tabs.addTab(self._create_execute_tab(), "⚡ 执行")
        self.tabs.addTab(self._create_history_tab(), "📜 历史")
        self.tabs.addTab(self._create_settings_tab(), "⚙️ 设置")

        main_layout.addWidget(self.tabs)

    def _create_overview_tab(self) -> QWidget:
        """创建总览标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(16)

        # 第一行: 磁盘使用情况
        layout.addWidget(DiskUsageWidget())

        # 第二行: 统计卡片
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(12)

        self.scan_count_card = StatCard("已扫描文件", "0", "📂")
        self.cleanable_card = StatCard("可清理文件", "0", "🧹")
        self.space_reclaimable_card = StatCard("可释放空间", "0 MB", "💾")
        self.protected_card = StatCard("已保护文件", "0", "🛡️")

        for card in [self.scan_count_card, self.cleanable_card,
                     self.space_reclaimable_card, self.protected_card]:
            stats_layout.addWidget(card)

        layout.addLayout(stats_layout)

        # 第三行: 快速操作
        quick_actions = QGroupBox("⚡ 快速操作")
        quick_actions.setStyleSheet("""
            QGroupBox {
                color: #a0a0c0;
                border: 1px solid #3d3d54;
                border-radius: 8px;
                padding: 16px;
                margin-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
            }
        """)

        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(12)

        quick_clean_btn = QPushButton("🧹 快速清理")
        quick_clean_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        quick_clean_btn.clicked.connect(self._on_quick_cleanup)

        deep_scan_btn = QPushButton("🔍 深度扫描")
        deep_scan_btn.setStyleSheet("""
            QPushButton {
                background-color: #374151;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #4b5563;
            }
        """)
        deep_scan_btn.clicked.connect(self._on_deep_scan)

        view_report_btn = QPushButton("📊 查看报告")
        view_report_btn.setStyleSheet("""
            QPushButton {
                background-color: #374151;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #4b5563;
            }
        """)
        view_report_btn.clicked.connect(self._on_view_report)

        actions_layout.addWidget(quick_clean_btn)
        actions_layout.addWidget(deep_scan_btn)
        actions_layout.addWidget(view_report_btn)
        actions_layout.addStretch()

        quick_actions.setLayout(actions_layout)
        layout.addWidget(quick_actions)

        layout.addStretch()

        return widget

    def _create_analysis_tab(self) -> QWidget:
        """创建分析标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # 扫描控制
        scan_control = QHBoxLayout()

        self.scan_path_label = QLabel("扫描路径:")
        self.scan_path_label.setStyleSheet("color: #a0a0c0;")
        scan_control.addWidget(self.scan_path_label)

        self.scan_path_input = QTextEdit()
        self.scan_path_input.setPlainText("C:/Users/Administrator/AppData/Local/Temp")
        self.scan_path_input.setMaximumHeight(60)
        self.scan_path_input.setStyleSheet("""
            QTextEdit {
                background-color: #1f1f35;
                color: #e0e0e0;
                border: 1px solid #3d3d54;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        scan_control.addWidget(self.scan_path_input)

        scan_btn = QPushButton("🔍 开始扫描")
        scan_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        scan_btn.clicked.connect(self._on_start_scan)
        scan_control.addWidget(scan_btn)

        layout.addLayout(scan_control)

        # 扫描结果列表
        self.candidates_list = QListWidget()
        self.candidates_list.setStyleSheet("""
            QListWidget {
                background-color: #1f1f35;
                border: none;
                border-radius: 8px;
            }
            QListWidget::item {
                padding: 0;
                margin: 4px 0;
            }
        """)
        layout.addWidget(self.candidates_list)

        return widget

    def _create_execute_tab(self) -> QWidget:
        """创建执行标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # 清理级别选择
        level_group = QGroupBox("⚡ 清理级别")
        level_group.setStyleSheet("""
            QGroupBox {
                color: #a0a0c0;
                border: 1px solid #3d3d54;
                border-radius: 8px;
                padding: 16px;
                margin-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
            }
        """)

        level_layout = QHBoxLayout()

        self.instant_radio = QCheckBox("Level 1: 即时清理 (临时文件/缓存)")
        self.instant_radio.setChecked(True)
        self.instant_radio.setStyleSheet("color: #e0e0e0;")
        level_layout.addWidget(self.instant_radio)

        self.regular_radio = QCheckBox("Level 2: 定期清理 (工作文件/下载)")
        self.regular_radio.setStyleSheet("color: #e0e0e0;")
        level_layout.addWidget(self.regular_radio)

        self.archive_radio = QCheckBox("Level 3: 智能归档 (低价值文件)")
        self.archive_radio.setStyleSheet("color: #e0e0e0;")
        level_layout.addWidget(self.archive_radio)

        level_group.setLayout(level_layout)
        layout.addWidget(level_group)

        # 清理选项
        options_group = QGroupBox("🛡️ 保护选项")
        options_group.setStyleSheet("""
            QGroupBox {
                color: #a0a0c0;
                border: 1px solid #3d3d54;
                border-radius: 8px;
                padding: 16px;
                margin-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
            }
        """)

        options_layout = QHBoxLayout()
        self.skip_protected_cb = QCheckBox("跳过保护文件")
        self.skip_protected_cb.setChecked(True)
        self.skip_protected_cb.setStyleSheet("color: #e0e0e0;")
        options_layout.addWidget(self.skip_protected_cb)

        self.dry_run_cb = QCheckBox("预览模式 (不实际删除)")
        self.dry_run_cb.setChecked(True)
        self.dry_run_cb.setStyleSheet("color: #e0e0e0;")
        options_layout.addWidget(self.dry_run_cb)

        options_layout.addStretch()
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # 执行按钮
        execute_layout = QHBoxLayout()

        execute_btn = QPushButton("⚡ 开始清理")
        execute_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 14px 32px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #b91c1c;
            }
        """)
        execute_btn.clicked.connect(self._on_execute_cleanup)
        execute_layout.addWidget(execute_btn)

        stop_btn = QPushButton("⏹️ 停止")
        stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #374151;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 14px 32px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #4b5563;
            }
        """)
        execute_layout.addWidget(stop_btn)

        execute_layout.addStretch()
        layout.addLayout(execute_layout)

        # 进度显示
        self.execute_progress = QProgressBar()
        self.execute_progress.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 4px;
                background-color: #3d3d54;
                height: 24px;
                text-align: center;
                color: white;
            }
            QProgressBar::chunk {
                background-color: #2563eb;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.execute_progress)

        # 执行日志
        self.execute_log = QTextEdit()
        self.execute_log.setReadOnly(True)
        self.execute_log.setMaximumHeight(150)
        self.execute_log.setStyleSheet("""
            QTextEdit {
                background-color: #1f1f35;
                color: #a0a0c0;
                border: 1px solid #3d3d54;
                border-radius: 8px;
                padding: 8px;
                font-family: 'Consolas', monospace;
                font-size: 12px;
            }
        """)
        layout.addWidget(self.execute_log)

        layout.addStretch()

        return widget

    def _create_history_tab(self) -> QWidget:
        """创建历史标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 历史记录表格
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(4)
        self.history_table.setHorizontalHeaderLabels(["时间", "清理文件数", "释放空间", "操作"])
        self.history_table.horizontalHeader().setStretchLastSection(True)
        self.history_table.setStyleSheet("""
            QTableWidget {
                background-color: #1f1f35;
                color: #e0e0e0;
                border: none;
                border-radius: 8px;
                gridline-color: #3d3d54;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QHeaderView::section {
                background-color: #252540;
                color: #a0a0c0;
                padding: 8px;
                border: none;
            }
        """)
        layout.addWidget(self.history_table)

        # 操作按钮
        history_actions = QHBoxLayout()

        refresh_history_btn = QPushButton("🔄 刷新")
        refresh_history_btn.setStyleSheet("""
            QPushButton {
                background-color: #374151;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #4b5563;
            }
        """)
        refresh_history_btn.clicked.connect(self._on_refresh_history)
        history_actions.addWidget(refresh_history_btn)

        export_history_btn = QPushButton("📤 导出记录")
        export_history_btn.setStyleSheet("""
            QPushButton {
                background-color: #374151;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #4b5563;
            }
        """)
        history_actions.addWidget(export_history_btn)

        history_actions.addStretch()
        layout.addLayout(history_actions)

        return widget

    def _create_settings_tab(self) -> QWidget:
        """创建设置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # 空间阈值设置
        threshold_group = QGroupBox("💾 空间阈值设置")
        threshold_group.setStyleSheet("""
            QGroupBox {
                color: #a0a0c0;
                border: 1px solid #3d3d54;
                border-radius: 8px;
                padding: 16px;
                margin-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
            }
        """)

        threshold_layout = QVBoxLayout()

        warning_layout = QHBoxLayout()
        warning_layout.addWidget(QLabel("警告阈值:"))
        warning_spin = QSpinBox()
        warning_spin.setRange(50, 95)
        warning_spin.setValue(80)
        warning_spin.setSuffix(" %")
        warning_spin.setStyleSheet("""
            QSpinBox {
                background-color: #1f1f35;
                color: #e0e0e0;
                border: 1px solid #3d3d54;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        warning_layout.addWidget(warning_spin)
        warning_layout.addWidget(QLabel("(80%时提醒)"))
        warning_layout.addStretch()
        threshold_layout.addLayout(warning_layout)

        critical_layout = QHBoxLayout()
        critical_layout.addWidget(QLabel("危险阈值:"))
        critical_spin = QSpinBox()
        critical_spin.setRange(60, 99)
        critical_spin.setValue(90)
        critical_spin.setSuffix(" %")
        critical_spin.setStyleSheet("""
            QSpinBox {
                background-color: #1f1f35;
                color: #e0e0e0;
                border: 1px solid #3d3d54;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        critical_layout.addWidget(critical_spin)
        critical_layout.addWidget(QLabel("(90%时强制清理)"))
        critical_layout.addStretch()
        threshold_layout.addLayout(critical_layout)

        threshold_group.setLayout(threshold_layout)
        layout.addWidget(threshold_group)

        # 保留时间设置
        retention_group = QGroupBox("⏰ 文件保留时间")
        retention_group.setStyleSheet("""
            QGroupBox {
                color: #a0a0c0;
                border: 1px solid #3d3d54;
                border-radius: 8px;
                padding: 16px;
                margin-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
            }
        """)

        retention_layout = QVBoxLayout()

        short_layout = QHBoxLayout()
        short_layout.addWidget(QLabel("短期保留:"))
        short_spin = QSpinBox()
        short_spin.setRange(1, 30)
        short_spin.setValue(7)
        short_spin.setSuffix(" 天")
        short_spin.setStyleSheet("""
            QSpinBox {
                background-color: #1f1f35;
                color: #e0e0e0;
                border: 1px solid #3d3d54;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        short_layout.addWidget(short_spin)
        short_layout.addStretch()
        retention_layout.addLayout(short_layout)

        long_layout = QHBoxLayout()
        long_layout.addWidget(QLabel("长期保留:"))
        long_spin = QSpinBox()
        long_spin.setRange(7, 365)
        long_spin.setValue(30)
        long_spin.setSuffix(" 天")
        long_spin.setStyleSheet("""
            QSpinBox {
                background-color: #1f1f35;
                color: #e0e0e0;
                border: 1px solid #3d3d54;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        long_layout.addWidget(long_spin)
        long_layout.addStretch()
        retention_layout.addLayout(long_layout)

        retention_group.setLayout(retention_layout)
        layout.addWidget(retention_group)

        # 保存按钮
        save_btn = QPushButton("💾 保存设置")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        layout.addWidget(save_btn)

        layout.addStretch()

        return widget

    # ============ 事件处理 ============

    def _on_refresh(self):
        """刷新"""
        self._update_stats()

    def _on_quick_cleanup(self):
        """快速清理"""
        self._log("开始快速清理...")

        # 获取临时目录
        import os
        temp_path = os.environ.get('TEMP', '')

        if not temp_path:
            self._log("❌ 无法获取临时目录")
            return

        # 扫描
        self._log(f"正在扫描: {temp_path}")
        files = self.engine.scan_directory(temp_path)
        self._log(f"扫描到 {len(files)} 个文件")

        # 评估
        candidates = self.engine.evaluate_cleanup_candidates(files)
        cleanable = [c for c in candidates if c.decision == CleanupDecision.CLEAN_NOW]
        self._log(f"发现 {len(cleanable)} 个可清理文件")

        # 执行
        if self.dry_run_cb.isChecked():
            self._log("⚠️ 预览模式，不实际删除")
            space = sum(c.metadata.size for c in cleanable)
            self._log(f"可释放空间: {space / (1024*1024):.2f} MB")
        else:
            result = self.engine.execute_cleanup(
                candidates,
                level=CleanupLevel.INSTANT,
                dry_run=False
            )
            self._log(f"✅ 清理完成，释放空间: {result.space_reclaimed / (1024*1024):.2f} MB")

        self._update_stats()

    def _on_deep_scan(self):
        """深度扫描"""
        self._log("开始深度扫描...")

        # 获取扫描路径
        scan_path = self.scan_path_input.toPlainText().strip()
        if not scan_path:
            self._log("❌ 请输入扫描路径")
            return

        self._log(f"正在扫描: {scan_path}")

        # 扫描
        files = self.engine.scan_directory(scan_path)
        self._log(f"扫描到 {len(files)} 个文件")

        # 评估
        candidates = self.engine.evaluate_cleanup_candidates(files)
        self._log(f"评估完成，发现 {len(candidates)} 个候选文件")

        # 显示结果
        self.candidates_list.clear()
        for candidate in candidates[:50]:  # 只显示前50个
            item = QListWidgetItem()
            widget = CleanupCandidateWidget(candidate)
            item.setSizeHint(widget.sizeHint())
            self.candidates_list.addItem(item)
            self.candidates_list.setItemWidget(item, widget)

        self._update_stats()

    def _on_start_scan(self):
        """开始扫描"""
        self._on_deep_scan()

    def _on_view_report(self):
        """查看报告"""
        report = self.engine.generate_cleanup_report()
        QMessageBox.information(self, "清理报告", report)

    def _on_execute_cleanup(self):
        """执行清理"""
        if self.dry_run_cb.isChecked():
            reply = QMessageBox.question(
                self,
                "预览模式",
                "当前为预览模式，不会实际删除文件。是否继续？"
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        # 确定清理级别
        if self.instant_radio.isChecked():
            level = CleanupLevel.INSTANT
        elif self.regular_radio.isChecked():
            level = CleanupLevel.REGULAR
        else:
            level = CleanupLevel.ARCHIVE

        self._log(f"开始执行 {level.name} 级别清理...")

        # 获取候选
        scan_path = self.scan_path_input.toPlainText().strip()
        if scan_path:
            files = self.engine.scan_directory(scan_path)
            candidates = self.engine.evaluate_cleanup_candidates(files)
        else:
            candidates = []

        if not candidates:
            self._log("❌ 没有找到可清理的文件")
            return

        # 执行
        self.execute_progress.setMaximum(len(candidates))

        result = self.engine.execute_cleanup(
            candidates,
            level=level,
            dry_run=self.dry_run_cb.isChecked()
        )

        self.execute_progress.setValue(len(result.cleaned_files))

        if result.space_reclaimed > 0:
            self._log(f"✅ 清理完成!")
            self._log(f"   清理文件: {len(result.cleaned_files)} 个")
            self._log(f"   归档文件: {len(result.archived_files)} 个")
            self._log(f"   释放空间: {result.space_reclaimed / (1024*1024):.2f} MB")
        else:
            self._log("ℹ️ 没有需要清理的文件")

        self._update_stats()

    def _on_refresh_history(self):
        """刷新历史"""
        history = self.engine.cleanup_history

        self.history_table.setRowCount(len(history))

        for i, h in enumerate(history):
            self.history_table.setItem(i, 0, QTableWidgetItem(
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(h.timestamp))
            ))
            self.history_table.setItem(i, 1, QTableWidgetItem(str(len(h.files))))
            self.history_table.setItem(i, 2, QTableWidgetItem(
                f"{h.space_reclaimed / (1024*1024):.2f} MB"
            ))
            self.history_table.setItem(i, 3, QTableWidgetItem(h.reason))

    def _log(self, message: str):
        """添加日志"""
        timestamp = time.strftime("%H:%M:%S")
        self.execute_log.append(f"[{timestamp}] {message}")

    def _update_stats(self):
        """更新统计信息"""
        stats = self.engine.get_stats()
        suggestions = self.engine.get_cleanup_suggestions()

        self.scan_count_card.update_value(str(stats.get("total_scanned", 0)))

        cleanable_count = len([c for c in self.engine.file_cache.values()
                               if c.value_score < 0.4])
        self.cleanable_card.update_value(str(cleanable_count))

        cleanable_size = suggestions.get("cleanable", {}).get("size", 0)
        self.space_reclaimable_card.update_value(
            f"{cleanable_size / (1024*1024):.1f} MB"
        )

        protected_count = len(self.engine.protected_files)
        self.protected_card.update_value(str(protected_count))