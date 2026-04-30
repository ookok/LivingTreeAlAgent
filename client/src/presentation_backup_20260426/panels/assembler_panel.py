"""
根系装配园面板 (Root Assembly Garden Panel)

PyQt6 集成面板 - 林窗视图中的嫁接培育界面
"""

import asyncio
from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QLineEdit, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QProgressBar, QStatusBar, QGroupBox, QFrame,
    QScrollArea, QTextBrowser
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor, QPalette

from .business.assembler import get_assembler
from core.assembler.navigator import RequirementSpec
from core.assembler.conflict import ResolutionStrategy
from core.metaverse_ui.bridge_styles import HolographicColors, HolographicStyles


class LogTextEdit(QTextEdit):
    """日志文本框 - 支持追加和自动滚动"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setStyleSheet("""
            QTextEdit {
                background-color: #0a0a1a;
                color: #00ff88;
                border: 1px solid #2a2a4a;
                font-family: 'Consolas', 'Microsoft YaHei';
                font-size: 12px;
            }
        """)

    def append_log(self, text: str):
        """追加日志"""
        self.append(text)
        # 自动滚动到底部
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())


class RootAssemblyGardenPanel(QWidget):
    """
    根系装配园面板

    提供七阶嫁接管线的可视化界面
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.assembler = get_assembler()
        self.current_session = None
        self._init_ui()

        # 定时刷新已部署列表
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_deployed_list)
        self._refresh_timer.start(5000)
        self._refresh_deployed_list()

    def _init_ui(self):
        """初始化UI"""
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {HolographicColors.BG_PRIMARY};
                color: #ffffff;
            }}
            QLabel {{
                color: #ffffff;
            }}
            QPushButton {{
                background-color: {HolographicColors.ACCENT_BLUE};
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                color: #ffffff;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {HolographicColors.ACCENT_CYAN};
            }}
            QPushButton:disabled {{
                background-color: #3a3a4a;
                color: #888888;
            }}
            QLineEdit, QTextEdit {{
                background-color: {HolographicColors.BG_SECONDARY};
                color: #ffffff;
                border: 1px solid {HolographicColors.BORDER};
                border-radius: 5px;
                padding: 8px;
            }}
            QProgressBar {{
                border: 1px solid {HolographicColors.BORDER};
                border-radius: 5px;
                text-align: center;
                background-color: {HolographicColors.BG_SECONDARY};
            }}
            QProgressBar::chunk {{
                background-color: {HolographicColors.ACCENT_CYAN};
                border-radius: 3px;
            }}
            QTabWidget::pane {{
                border: 1px solid {HolographicColors.BORDER};
                background-color: {HolographicColors.BG_PRIMARY};
            }}
            QTabBar::tab {{
                background-color: {HolographicColors.BG_SECONDARY};
                padding: 8px 16px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background-color: {HolographicColors.ACCENT_BLUE};
            }}
            QTableWidget {{
                background-color: {HolographicColors.BG_SECONDARY};
                color: #ffffff;
                gridcolor: {HolographicColors.BORDER};
                border: none;
            }}
            QHeaderView::section {{
                background-color: {HolographicColors.BG_TERTIARY};
                color: #ffffff;
                padding: 5px;
                border: 1px solid {HolographicColors.BORDER};
            }}
        """)

        main_layout = QVBoxLayout(self)

        # 标题栏
        title_layout = QHBoxLayout()
        title = QLabel("🌳 根系装配园 (Root Assembly Garden)")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title_layout.addWidget(title)
        title_layout.addStretch()
        main_layout.addLayout(title_layout)

        # 标签页
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_assembly_tab(), "🌱 嫁接")
        self.tabs.addTab(self._create_deployed_tab(), "🌿 已扎根")
        self.tabs.addTab(self._create_log_tab(), "📋 日志")
        main_layout.addWidget(self.tabs, 1)

        # 状态栏
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("就绪")
        main_layout.addWidget(self.status_bar)

    def _create_assembly_tab(self) -> QWidget:
        """创建装配标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 输入区域
        input_group = QGroupBox("📥 输入需求")
        input_layout = QVBoxLayout()

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText(
            "输入需求，例如：能解析 PDF 表格的 Python 库\n"
            "或直接粘贴仓库 URL：https://github.com/owner/repo"
        )
        input_layout.addWidget(self.input_field)

        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("🌱 开始嫁接")
        self.start_btn.clicked.connect(self._on_start_grafting)
        btn_layout.addWidget(self.start_btn)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._on_cancel)
        btn_layout.addWidget(self.cancel_btn)

        input_layout.addLayout(btn_layout)
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # 进度区域
        progress_group = QGroupBox("📊 嫁接进度")
        progress_layout = QVBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(6)  # 6个阶段
        self.progress_layout = QVBoxLayout()

        self.stage_labels = []
        stages = ["良种搜寻", "良种雷达", "亲和试验", "育苗温床", "萌芽试炼", "扎根部署"]
        for i, stage in enumerate(stages):
            hbox = QHBoxLayout()
            label = QLabel(f"{'⏳' if i > 0 else '○'} {stage}")
            self.stage_labels.append(label)
            hbox.addWidget(label)
            hbox.addStretch()
            progress_layout.addLayout(hbox)

        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)

        # 冲突处理区域
        self.conflict_group = QGroupBox("⚠️ 冲突检测")
        conflict_layout = QVBoxLayout()

        self.conflict_label = QLabel("未检测到冲突")
        conflict_layout.addWidget(self.conflict_label)

        strategy_layout = QHBoxLayout()
        self.coexist_btn = QPushButton("✅ 并行共存")
        self.coexist_btn.clicked.connect(lambda: self._on_strategy_selected(ResolutionStrategy.COEXIST))
        self.replace_btn = QPushButton("🔄 替换旧版")
        self.replace_btn.clicked.connect(lambda: self._on_strategy_selected(ResolutionStrategy.REPLACE))
        self.conflict_cancel_btn = QPushButton("❌ 取消")
        self.conflict_cancel_btn.clicked.connect(self._on_cancel)

        strategy_layout.addWidget(self.coexist_btn)
        strategy_layout.addWidget(self.replace_btn)
        strategy_layout.addWidget(self.conflict_cancel_btn)
        conflict_layout.addLayout(strategy_layout)

        self.conflict_group.setLayout(conflict_layout)
        self.conflict_group.hide()
        layout.addWidget(self.conflict_group)

        # 结果区域
        result_group = QGroupBox("🌿 嫁接结果")
        result_layout = QVBoxLayout()

        self.result_label = QLabel("等待装配...")
        result_layout.addWidget(self.result_label)

        result_group.setLayout(result_layout)
        layout.addWidget(result_group)

        layout.addStretch()
        return widget

    def _create_deployed_tab(self) -> QWidget:
        """创建已部署标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 工具栏
        toolbar = QHBoxLayout()
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self._refresh_deployed_list)
        toolbar.addWidget(refresh_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # 表格
        self.deployed_table = QTableWidget()
        self.deployed_table.setColumnCount(5)
        self.deployed_table.setHorizontalHeaderLabels(["模块名", "版本", "状态", "热重载", "调用次数"])
        self.deployed_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.deployed_table)

        return widget

    def _create_log_tab(self) -> QWidget:
        """创建日志标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 工具栏
        toolbar = QHBoxLayout()
        clear_btn = QPushButton("🗑️ 清空日志")
        clear_btn.clicked.connect(lambda: self.log_view.clear())
        toolbar.addWidget(clear_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # 日志视图
        self.log_view = LogTextEdit()
        layout.addWidget(self.log_view, 1)

        return widget

    async def _on_start_grafting(self):
        """开始嫁接"""
        user_input = self.input_field.text().strip()
        if not user_input:
            self.log_view.append_log("⚠️ 请描述您需要的种子（功能需求）")
            return

        # 创建会话
        self.current_session = self.assembler.create_session()

        # 注册回调
        self.assembler.register_callback(
            self.current_session.session_id,
            self._on_session_event
        )

        # 更新UI
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.log_view.append_log(f"\n{'='*60}")
        self.log_view.append_log(f"🌱 开始嫁接: {user_input}")
        self._update_progress(0)

        # 运行装配流程
        self.assembler.run_assembly(
            session_id=self.current_session.session_id,
            user_input=user_input,
            auto_resolve=False,  # 需要用户决策
            progress_callback=self._on_progress,
            log_callback=self._on_log
        )

    def _on_session_event(self, event: str, data):
        """会话事件"""
        if event == "await_decision":
            # 等待用户决策
            self.conflict_group.show()
            if data.conflict_report:
                self.conflict_label.setText(data.conflict_report.summary or "检测到冲突")
            self.status_bar.showMessage("等待选择处理策略...")

        elif event == "assembly_complete":
            self._on_grafting_complete(data)

    def _on_progress(self, msg: str):
        """进度更新"""
        self.status_bar.showMessage(msg)
        self.log_view.append_log(msg)

        # 更新进度条
        stage_map = {
            "良种搜寻": 0,
            "良种雷达": 1,
            "亲和试验": 2,
            "育苗温床": 3,
            "萌芽试炼": 4,
            "扎根部署": 5,
        }

        for stage, idx in stage_map.items():
            if stage in msg:
                self._update_progress(idx)
                break

    def _update_progress(self, stage_idx: int):
        """更新进度显示"""
        for i, label in enumerate(self.stage_labels):
            if i < stage_idx:
                label.setText(f"✅ {label.text()[2:]}")  # 已完成
                label.setStyleSheet("color: #4CAF50;")
            elif i == stage_idx:
                label.setText(f"🔄 {label.text()[2:]}")  # 进行中
                label.setStyleSheet("color: #FFC107;")
            else:
                label.setText(f"⏳ {label.text()[2:]}")  # 未开始
                label.setStyleSheet("color: #888888;")

        self.progress_bar.setValue(stage_idx)

    async def _on_log(self, msg: str):
        """日志更新"""
        self.log_view.append_log(msg)

    def _on_strategy_selected(self, strategy: ResolutionStrategy):
        """策略被选中"""
        if not self.current_session:
            return

        self.log_view.append_log(f"\n📋 用户选择策略: {strategy.value}")
        self.conflict_group.hide()

        # 继续装配
        asyncio.create_task(
            self.assembler.resolve_and_continue(
                self.current_session.session_id,
                strategy
            )
        )

    def _on_cancel(self):
        """取消嫁接"""
        if self.current_session:
            self.assembler.close_session(self.current_session.session_id)
        self.current_session = None
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.conflict_group.hide()
        self.status_bar.showMessage("已取消")
        self.log_view.append_log("❌ 嫁接已取消")

    def _on_grafting_complete(self, session):
        """嫁接完成"""
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self._update_progress(6)

        if session.error_message:
            self.result_label.setText(f"❌ 嫁接失败: {session.error_message}")
            self.log_view.append_log(f"\n❌ 嫁接失败: {session.error_message}")
        elif session.deployed_module:
            msg = f"✅ 嫁接成功!\n新苗: ext:{session.selected_repo.name}\n版本: {session.deployed_module.version}"
            self.result_label.setText(msg)
            self.log_view.append_log(f"\n{msg}")
        else:
            self.result_label.setText("⚠️ 嫁接未完成")
            self.log_view.append_log("\n⚠️ 嫁接未完成")

        self.status_bar.showMessage("嫁接完成")
        self._refresh_deployed_list()

    def _refresh_deployed_list(self):
        """刷新已部署列表"""
        modules = self.assembler.list_deployed()

        self.deployed_table.setRowCount(len(modules))
        for i, module in enumerate(modules):
            self.deployed_table.setItem(i, 0, QTableWidgetItem(module.get("name", "")))
            self.deployed_table.setItem(i, 1, QTableWidgetItem(module.get("version", "")))
            self.deployed_table.setItem(i, 2, QTableWidgetItem(module.get("status", "")))
            self.deployed_table.setItem(i, 3, QTableWidgetItem("⚡" if module.get("is_hot_reload") else "❄️"))
            self.deployed_table.setItem(i, 4, QTableWidgetItem(str(module.get("call_count", 0))))