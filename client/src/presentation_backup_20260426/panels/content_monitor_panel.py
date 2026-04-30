"""
内容监控面板 UI

集成到主窗口的内容监控功能界面
"""

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QLabel, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QTabWidget, QProgressBar, QLineEdit, QCheckBox, QGroupBox,
    QGridLayout, QScrollArea, QFrame, QStatusBar, QToolButton,
    QSpinBox, QDoubleSpinBox, QTextBrowser, QInputDialog, QMessageBox
)
from PyQt6.QtGui import QFont, QColor, QTextCharFormat, QTextCursor

from .business.content_monitor import (
    ContentMonitor, ContentRecognizer, ContentSummarizer,
    create_server, ContentType, AlertLevel, ContentStatus
)


class ContentMonitorPanel(QWidget):
    """
    内容监控面板

    功能：
    - 内容分析与监控
    - 敏感词管理
    - 告警记录查看
    - 归纳总结
    """

    content_analyzed = pyqtSignal(dict)  # 分析完成信号
    alert_triggered = pyqtSignal(dict)    # 告警触发信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self._monitor = ContentMonitor()
        self._recognizer = ContentRecognizer()
        self._summarizer = ContentSummarizer()
        self._server = None
        self._server_running = False

        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 顶部：功能标签页
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.West)

        # 1. 内容分析页
        self.analysis_tab = self._create_analysis_tab()
        self.tabs.addTab(self.analysis_tab, "🔍 内容分析")

        # 2. 监控告警页
        self.monitor_tab = self._create_monitor_tab()
        self.tabs.addTab(self.monitor_tab, "🛡️ 监控告警")

        # 3. 归纳总结页
        self.summarize_tab = self._create_summarize_tab()
        self.tabs.addTab(self.summarize_tab, "📝 归纳总结")

        # 4. 敏感词管理页
        self.words_tab = self._create_words_tab()
        self.tabs.addTab(self.words_tab, "⚠️ 敏感词库")

        # 5. 系统状态页
        self.status_tab = self._create_status_tab()
        self.tabs.addTab(self.status_tab, "📊 系统状态")

        layout.addWidget(self.tabs)

    def _create_analysis_tab(self) -> QWidget:
        """创建内容分析页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        # 输入区域
        input_group = QGroupBox("📥 内容输入")
        input_layout = QVBoxLayout(input_group)

        self.analysis_input = QTextEdit()
        self.analysis_input.setPlaceholderText("在此输入需要分析的内容...")
        self.analysis_input.setMaximumHeight(150)
        input_layout.addWidget(self.analysis_input)

        # 操作按钮
        btn_layout = QHBoxLayout()
        self.analyze_btn = QPushButton("🔍 开始分析")
        self.analyze_btn.clicked.connect(self._do_analyze)
        self.clear_analyze_btn = QPushButton("🗑️ 清空")
        self.clear_analyze_btn.clicked.connect(lambda: self.analysis_input.clear())
        btn_layout.addWidget(self.analyze_btn)
        btn_layout.addWidget(self.clear_analyze_btn)
        btn_layout.addStretch()
        input_layout.addLayout(btn_layout)

        layout.addWidget(input_group)

        # 结果区域
        result_group = QGroupBox("📤 分析结果")
        result_layout = QVBoxLayout(result_group)

        self.analysis_result = QTextBrowser()
        self.analysis_result.setOpenExternalLinks(False)
        result_layout.addWidget(self.analysis_result)

        layout.addWidget(result_group)
        return tab

    def _create_monitor_tab(self) -> QWidget:
        """创建监控告警页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        # 顶部工具栏
        toolbar = QHBoxLayout()

        self.monitor_input = QLineEdit()
        self.monitor_input.setPlaceholderText("输入内容进行监控...")
        self.monitor_input.returnPressed.connect(self._do_monitor)
        toolbar.addWidget(self.monitor_input, 1)

        self.monitor_btn = QPushButton("🛡️ 监控")
        self.monitor_btn.clicked.connect(self._do_monitor)
        toolbar.addWidget(self.monitor_btn)

        self.monitor_clear_btn = QPushButton("清空")
        self.monitor_clear_btn.clicked.connect(lambda: (self.monitor_input.clear(), self.monitor_result.clear()))
        toolbar.addWidget(self.monitor_clear_btn)

        layout.addLayout(toolbar)

        # 告警级别选择
        level_layout = QHBoxLayout()
        level_layout.addWidget(QLabel("告警级别过滤:"))
        self.level_filter = QComboBox()
        self.level_filter.addItems(["全部", "正常", "轻度", "中度", "高度", "紧急"])
        level_layout.addWidget(self.level_filter)
        level_layout.addStretch()
        layout.addLayout(level_layout)

        # 监控结果
        self.monitor_result = QTextBrowser()
        layout.addWidget(self.monitor_result)

        return tab

    def _create_summarize_tab(self) -> QWidget:
        """创建归纳总结页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        # 输入区域
        input_group = QGroupBox("📥 待归纳内容")
        input_layout = QVBoxLayout(input_group)

        self.summarize_input = QTextEdit()
        self.summarize_input.setPlaceholderText("输入需要归纳的内容...")
        self.summarize_input.setMaximumHeight(150)
        input_layout.addWidget(self.summarize_input)

        # 选项
        options_layout = QHBoxLayout()
        options_layout.addWidget(QLabel("内容类型:"))
        self.summarize_type = QComboBox()
        self.summarize_type.addItems([
            "自动识别", "财务内容", "法律文档", "项目计划",
            "会议记录", "工作日志", "学习笔记", "通用内容"
        ])
        options_layout.addWidget(self.summarize_type)
        options_layout.addStretch()

        self.summarize_btn = QPushButton("📝 生成归纳")
        self.summarize_btn.clicked.connect(self._do_summarize)
        options_layout.addWidget(self.summarize_btn)

        input_layout.addLayout(options_layout)
        layout.addWidget(input_group)

        # 结果区域
        result_group = QGroupBox("📤 归纳结果")
        result_layout = QVBoxLayout(result_group)

        self.summarize_result = QTextBrowser()
        self.summarize_result.setOpenExternalLinks(False)
        result_layout.addWidget(self.summarize_result)

        layout.addWidget(result_group)
        return tab

    def _create_words_tab(self) -> QWidget:
        """创建敏感词库管理页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        # 工具栏
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("⚠️ 敏感词库管理"))
        toolbar.addStretch()

        self.add_word_btn = QPushButton("➕ 添加词汇")
        self.add_word_btn.clicked.connect(self._add_sensitive_word)
        toolbar.addWidget(self.add_word_btn)

        layout.addLayout(toolbar)

        # 敏感词列表
        self.words_table = QTableWidget()
        self.words_table.setColumnCount(4)
        self.words_table.setHorizontalHeaderLabels(["词汇", "类别", "级别", "权重"])
        self.words_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.words_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.words_table)

        self._load_sensitive_words()

        return tab

    def _create_status_tab(self) -> QWidget:
        """创建系统状态页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        # 统计概览
        stats_group = QGroupBox("📊 统计概览")
        stats_layout = QGridLayout(stats_group)

        self.total_content_label = QLabel("0")
        self.total_alerts_label = QLabel("0")
        self.pending_label = QLabel("0")
        self.uptime_label = QLabel("0秒")

        stats_layout.addWidget(QLabel("总内容数:"), 0, 0)
        stats_layout.addWidget(self.total_content_label, 0, 1)
        stats_layout.addWidget(QLabel("总告警数:"), 0, 2)
        stats_layout.addWidget(self.total_alerts_label, 0, 3)
        stats_layout.addWidget(QLabel("待审核:"), 1, 0)
        stats_layout.addWidget(self.pending_label, 1, 1)
        stats_layout.addWidget(QLabel("运行时间:"), 1, 2)
        stats_layout.addWidget(self.uptime_label, 1, 3)

        layout.addWidget(stats_group)

        # 告警分布
        alerts_group = QGroupBox("🚨 告警分布")
        alerts_layout = QVBoxLayout(alerts_group)

        self.alerts_by_level = QTextBrowser()
        alerts_layout.addWidget(self.alerts_by_level)

        layout.addWidget(alerts_group)

        # 启动服务器按钮
        server_layout = QHBoxLayout()
        self.server_status_label = QLabel("🖥️ 服务器: 未启动")
        self.toggle_server_btn = QPushButton("启动服务器")
        self.toggle_server_btn.clicked.connect(self._toggle_server)
        server_layout.addWidget(self.server_status_label)
        server_layout.addStretch()
        server_layout.addWidget(self.toggle_server_btn)
        layout.addLayout(server_layout)

        layout.addStretch()

        # 定时更新状态
        self._update_status_timer = QTimer()
        self._update_status_timer.timeout.connect(self._refresh_status)
        self._update_status_timer.start(5000)
        self._refresh_status()

        return tab

    def _do_analyze(self):
        """执行内容分析"""
        content = self.analysis_input.toPlainText().strip()
        if not content:
            self.analysis_result.setHtml("<p style='color:orange;'>请输入内容</p>")
            return

        result = self._monitor.analyze_content(content)

        # 生成结果HTML
        alert_colors = {
            AlertLevel.NORMAL: "#22c55e",
            AlertLevel.LOW: "#eab308",
            AlertLevel.MEDIUM: "#f97316",
            AlertLevel.HIGH: "#ef4444",
            AlertLevel.CRITICAL: "#dc2626"
        }
        color = alert_colors.get(result.alert_level, "#888")

        html = f"""
        <div style="padding:10px; background:#1a1a2e; border-radius:8px;">
            <p><b style="color:#60a5fa;">内容类型:</b> <span style="color:#a78bfa;">{result.content_type.value}</span></p>
            <p><b style="color:#60a5fa;">告警级别:</b> <span style="color:{color};">{result.alert_level.name}</span></p>
            <p><b style="color:#60a5fa;">置信度:</b> <span style="color:#34d399;">{result.confidence:.2%}</span></p>
            <p><b style="color:#60a5fa;">处理时间:</b> <span style="color:#f472b6;">{result.processing_time_ms:.2f}ms</span></p>
        """

        if result.alert_reasons:
            html += "<p><b style='color:#ef4444;'>告警原因:</b></p><ul>"
            for reason in result.alert_reasons[:5]:
                html += f"<li style='color:#fca5a5;'>{reason}</li>"
            html += "</ul>"

        html += "</div>"
        self.analysis_result.setHtml(html)
        self.content_analyzed.emit({
            "type": result.content_type.value,
            "level": result.alert_level.name,
            "confidence": result.confidence
        })

    def _do_monitor(self):
        """执行内容监控"""
        content = self.monitor_input.text().strip()
        if not content:
            return

        result = self._monitor.analyze_content(content)

        level_icons = {
            AlertLevel.NORMAL: "✅",
            AlertLevel.LOW: "⚠️",
            AlertLevel.MEDIUM: "🔶",
            AlertLevel.HIGH: "🔴",
            AlertLevel.CRITICAL: "🚨"
        }
        icon = level_icons.get(result.alert_level, "❓")

        html = f"""
        <div style="padding:12px; margin:8px 0; background:#1a1a2e; border-radius:8px; border-left:4px solid {
            '#22c55e' if result.alert_level == AlertLevel.NORMAL else
            '#eab308' if result.alert_level == AlertLevel.LOW else
            '#f97316' if result.alert_level == AlertLevel.MEDIUM else
            '#ef4444' if result.alert_level == AlertLevel.HIGH else '#dc2626'
        };">
            <p style="color:#60a5fa; font-size:14px;">{icon} <b>{result.alert_level.name}</b></p>
            <p style="color:#a78bfa;">类型: {result.content_type.value} | 置信度: {result.confidence:.2%}</p>
        """

        if result.alert_reasons:
            html += "<p style='color:#fca5a5;'>原因: " + "; ".join(result.alert_reasons[:3]) + "</p>"

        html += "</div>" + self.monitor_result.toHtml()
        self.monitor_result.setHtml(html)

        if result.alert_level.value >= AlertLevel.MEDIUM.value:
            self.alert_triggered.emit({"level": result.alert_level.name, "content": content[:50]})

    def _do_summarize(self):
        """执行归纳总结"""
        content = self.summarize_input.toPlainText().strip()
        if not content:
            self.summarize_result.setHtml("<p style='color:orange;'>请输入内容</p>")
            return

        type_map = {
            0: None,  # 自动识别
            1: ContentType.FINANCIAL,
            2: ContentType.LEGAL,
            3: ContentType.PROJECT_PLAN,
            4: ContentType.MEETING_NOTES,
            5: ContentType.WORK_LOG,
            6: ContentType.LEARNING_NOTES,
            7: ContentType.GENERAL
        }
        content_type = type_map.get(self.summarize_type.currentIndex(), None)

        result = self._summarizer.summarize(content, content_type)

        html = f"""
        <div style="padding:12px; background:#1a1a2e; border-radius:8px;">
            <p style="color:#60a5fa; font-size:16px;"><b>📋 归纳结果</b></p>
            <p style="color:#a78bfa;"><b>识别类型:</b> {result.content_type.value}</p>
            <p style="color:#34d399;"><b>置信度:</b> {result.confidence:.2%}</p>
            <hr style="border-color:#333;">
            <p style="color:#f472b6;"><b>📌 摘要:</b></p>
            <p style="color:#e2e8f0;">{result.summary or '无'}</p>
        """

        if result.key_points:
            html += "<p style='color:#fbbf24;'><b>✨ 关键要点:</b></p><ul>"
            for point in result.key_points[:5]:
                html += f"<li style='color:#fde68a;'>{point}</li>"
            html += "</ul>"

        if result.categories:
            html += "<p style='color:#22d3ee;'><b>📂 分类:</b></p><ul>"
            for cat, items in list(result.categories.items())[:3]:
                html += f"<li style='color:#a5f3fc;'><b>{cat}:</b> {', '.join(items[:3])}</li>"
            html += "</ul>"

        if result.suggestions:
            html += "<p style='color:#c084fc;'><b>💡 建议:</b></p><ul>"
            for suggestion in result.suggestions[:3]:
                html += f"<li style='color:#e9d5ff;'>{suggestion}</li>"
            html += "</ul>"

        html += "</div>"
        self.summarize_result.setHtml(html)

    def _load_sensitive_words(self):
        """加载敏感词列表"""
        words = self._monitor.get_sensitive_words()
        self.words_table.setRowCount(len(words))

        level_names = {
            AlertLevel.NORMAL: "正常",
            AlertLevel.LOW: "轻度",
            AlertLevel.MEDIUM: "中度",
            AlertLevel.HIGH: "高度",
            AlertLevel.CRITICAL: "紧急"
        }

        for i, word_info in enumerate(words[:50]):
            # 兼容 dataclass 对象和字典两种形式
            if hasattr(word_info, 'word'):
                word_text = word_info.word
                category = word_info.category
                level = word_info.alert_level
                weight = word_info.weight
            else:
                word_text = word_info.get("word", "")
                category = word_info.get("category", "")
                level = word_info.get("alert_level", AlertLevel.LOW)
                weight = word_info.get("weight", 1)
            self.words_table.setItem(i, 0, QTableWidgetItem(word_text))
            self.words_table.setItem(i, 1, QTableWidgetItem(category))
            self.words_table.setItem(i, 2, QTableWidgetItem(level_names.get(level, "未知")))
            self.words_table.setItem(i, 3, QTableWidgetItem(str(weight)))

    def _add_sensitive_word(self):
        """添加敏感词"""
        word, ok = QInputDialog.getText(self, "添加敏感词", "请输入敏感词:")
        if ok and word:
            self._monitor.add_sensitive_word(word)
            self._load_sensitive_words()

    def _toggle_server(self):
        """切换服务器状态"""
        if self._server_running:
            # 停止服务器
            if self._server:
                import asyncio
                asyncio.create_task(self._server.shutdown())
            self._server_running = False
            self.server_status_label.setText("🖥️ 服务器: 已停止")
            self.toggle_server_btn.setText("启动服务器")
        else:
            # 启动服务器
            try:
                import asyncio
                self._server = asyncio.run(create_server({"host": "0.0.0.0", "port": 8765}))
                self._server_running = True
                self.server_status_label.setText("🖥️ 服务器: 运行中 (8765)")
                self.toggle_server_btn.setText("停止服务器")
            except Exception as e:
                self.server_status_label.setText("🖥️ 服务器: 启动失败")
                QMessageBox.warning(self, "服务器错误", str(e))

    def _refresh_status(self):
        """刷新状态信息"""
        stats = self._monitor.get_stats()

        self.total_content_label.setText(str(stats.total_content))
        self.total_alerts_label.setText(str(stats.total_alerts))
        self.pending_label.setText(str(stats.pending_review))

        # 告警分布
        alerts_html = "<div style='padding:8px;'>"
        for level, count in stats.alerts_by_level.items():
            colors = {
                "NORMAL": "#22c55e", "LOW": "#eab308",
                "MEDIUM": "#f97316", "HIGH": "#ef4444", "CRITICAL": "#dc2626"
            }
            color = colors.get(level, "#888")
            alerts_html += f"<p style='color:{color};'>● {level}: <b>{count}</b></p>"
        alerts_html += "</div>"
        self.alerts_by_level.setHtml(alerts_html)
