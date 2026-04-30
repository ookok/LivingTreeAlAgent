# thought_audit_panel.py — 思维审核室 PyQt6 管理面板

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QTextBrowser, QLineEdit, QComboBox, QGroupBox,
    QFormLayout, QSpinBox, QCheckBox, QProgressBar,
    QListWidget, QListWidgetItem, QDialog, QDialogButtonBox,
    QScrollArea, QFrame, QGridLayout, QSplitter,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor
import sys
import traceback


class ThoughtAuditPanel(QWidget):
    """
    思维审核室 — PyQt6 管理面板

    4 个标签页：
    1. 总览 — 系统状态 + 统计
    2. 辩论审核 — 展示辩论记录，审核 ✅/⚠️/❌
    3. 外部洞察 — 待吸收的外部内容
    4. 知识库 — 已确认的知识条目
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.system = None  # 延迟加载
        self._init_ui()
        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.setInterval(30000)  # 30秒刷新

    def _ensure_system(self):
        if self.system is None:
            try:
                from .business.self_upgrade import get_self_upgrade_system
                self.system = get_self_upgrade_system()
            except ImportError:
                self.system = None

    # ============================================================
    # UI 初始化
    # ============================================================

    def _init_ui(self):
        main_layout = QVBoxLayout(self)

        # 标题栏
        title_bar = QHBoxLayout()
        title = QLabel("🌿 思维审核室 — AI 自我升级系统")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title_bar.addWidget(title)
        title_bar.addStretch()

        # 启用开关
        self.enable_btn = QPushButton("启用")
        self.enable_btn.setCheckable(True)
        self.enable_btn.clicked.connect(self._toggle_enabled)
        title_bar.addWidget(self.enable_btn)

        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self.refresh)
        title_bar.addWidget(refresh_btn)

        main_layout.addLayout(title_bar)

        # Tab Widget
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_overview_tab(), "📊 总览")
        self.tabs.addTab(self._create_debate_tab(), "⚖️ 辩论审核")
        self.tabs.addTab(self._create_insights_tab(), "🌐 外部洞察")
        self.tabs.addTab(self._create_knowledge_tab(), "📚 知识库")
        self.tabs.addTab(self._create_settings_tab(), "⚙️ 设置")

        main_layout.addWidget(self.tabs)

    def _create_overview_tab(self) -> QWidget:
        """总览标签页"""
        w = QWidget()
        layout = QVBoxLayout(w)

        # 统计卡片
        stats_group = QGroupBox("系统统计")
        stats_layout = QGridLayout()

        self.stat_labels = {}
        stats_items = [
            ("pending_debates", "待审核辩论"),
            ("approved_debates", "已认可辩论"),
            ("pending_insights", "待吸收洞察"),
            ("total_knowledge", "知识条目"),
            ("safety_blocked", "安全拦截"),
        ]

        for i, (key, label) in enumerate(stats_items):
            stats_layout.addWidget(QLabel(label), i // 2, (i % 2) * 2)
            val_label = QLabel("—")
            val_label.setObjectName(f"stat_{key}")
            self.stat_labels[key] = val_label
            stats_layout.addWidget(val_label, i // 2, (i % 2) * 2 + 1)

        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        # 待审核项列表
        pending_group = QGroupBox("待审核项")
        pending_layout = QVBoxLayout()

        self.pending_list = QListWidget()
        self.pending_list.itemClicked.connect(self._on_pending_item_clicked)
        pending_layout.addWidget(self.pending_list)

        pending_group.setLayout(pending_layout)
        layout.addWidget(pending_group)

        layout.addStretch()
        return w

    def _create_debate_tab(self) -> QWidget:
        """辩论审核标签页"""
        w = QWidget()
        layout = QVBoxLayout(w)

        # 操作栏
        toolbar = QHBoxLayout()

        toolbar.addWidget(QLabel("辩论列表"))
        self.debate_filter = QComboBox()
        self.debate_filter.addItems(["全部", "待审核", "已认可", "已驳回"])
        self.debate_filter.currentTextChanged.connect(self._filter_debates)
        toolbar.addWidget(self.debate_filter)

        toolbar.addStretch()

        new_debate_btn = QPushButton("🆕 新建辩论")
        new_debate_btn.clicked.connect(self._new_debate)
        toolbar.addWidget(new_debate_btn)

        layout.addLayout(toolbar)

        # 辩论详情区
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：辩论列表
        self.debate_list = QListWidget()
        self.debate_list.itemClicked.connect(self._show_debate_detail)
        splitter.addWidget(self.debate_list)

        # 右侧：辩论详情
        detail_widget = QWidget()
        detail_layout = QVBoxLayout(detail_widget)

        self.debate_detail = QTextBrowser()
        self.debate_detail.setOpenExternalLinks(True)
        detail_layout.addWidget(self.debate_detail)

        # 审核按钮
        review_bar = QHBoxLayout()
        approve_btn = QPushButton("✅ 认可")
        approve_btn.clicked.connect(lambda: self._review_debate("approved"))
        review_bar.addWidget(approve_btn)

        revise_btn = QPushButton("⚠️ 修改")
        revise_btn.clicked.connect(lambda: self._review_debate("revised"))
        review_bar.addWidget(revise_btn)

        reject_btn = QPushButton("❌ 驳回")
        reject_btn.clicked.connect(lambda: self._review_debate("rejected"))
        review_bar.addWidget(reject_btn)

        detail_layout.addLayout(review_bar)
        splitter.addWidget(detail_widget)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)

        return w

    def _create_insights_tab(self) -> QWidget:
        """外部洞察标签页"""
        w = QWidget()
        layout = QVBoxLayout(w)

        # 操作栏
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("待吸收的外部洞察"))

        toolbar.addStretch()

        fetch_btn = QPushButton("🔍 抓取外部内容")
        fetch_btn.clicked.connect(self._fetch_external)
        toolbar.addWidget(fetch_btn)

        layout.addLayout(toolbar)

        # 洞察列表
        self.insight_list = QListWidget()
        self.insight_list.itemClicked.connect(self._show_insight_detail)
        layout.addWidget(self.insight_list)

        # 洞察详情
        insight_detail_group = QGroupBox("详情")
        insight_detail_layout = QVBoxLayout()

        self.insight_detail = QTextBrowser()
        insight_detail_layout.addWidget(self.insight_detail)

        insight_btn_bar = QHBoxLayout()
        absorb_btn = QPushButton("📥 吸收到知识库")
        absorb_btn.clicked.connect(self._absorb_insight)
        insight_btn_bar.addWidget(absorb_btn)

        dismiss_btn = QPushButton("🚫 忽略")
        dismiss_btn.clicked.connect(self._dismiss_insight)
        insight_btn_bar.addWidget(dismiss_btn)

        insight_detail_layout.addLayout(insight_btn_bar)
        insight_detail_group.setLayout(insight_detail_layout)
        layout.addWidget(insight_detail_group)

        return w

    def _create_knowledge_tab(self) -> QWidget:
        """知识库标签页"""
        w = QWidget()
        layout = QVBoxLayout(w)

        # 搜索栏
        search_bar = QHBoxLayout()
        search_bar.addWidget(QLabel("🔍 搜索:"))
        self.knowledge_search = QLineEdit()
        self.knowledge_search.setPlaceholderText("输入关键词搜索...")
        self.knowledge_search.textChanged.connect(self._search_knowledge)
        search_bar.addWidget(self.knowledge_search)
        layout.addLayout(search_bar)

        # 知识列表
        self.knowledge_table = QTableWidget()
        self.knowledge_table.setColumnCount(5)
        self.knowledge_table.setHorizontalHeaderLabels(["ID", "类别", "Key", "值", "版本"])
        self.knowledge_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.knowledge_table)

        # 操作栏
        btn_bar = QHBoxLayout()
        add_btn = QPushButton("➕ 添加知识")
        add_btn.clicked.connect(self._add_knowledge)
        btn_bar.addWidget(add_btn)

        delete_btn = QPushButton("🗑️ 删除")
        delete_btn.clicked.connect(self._delete_knowledge)
        btn_bar.addWidget(delete_btn)

        btn_bar.addStretch()
        layout.addLayout(btn_bar)

        return w

    def _create_settings_tab(self) -> QWidget:
        """设置标签页"""
        w = QScrollArea()
        w.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)

        # 调度设置
        sched_group = QGroupBox("进化调度")
        sched_layout = QFormLayout()

        self.idle_minutes = QSpinBox()
        self.idle_minutes.setRange(1, 60)
        self.idle_minutes.setSuffix(" 分钟")
        self.idle_minutes.setValue(5)
        sched_layout.addRow("空闲触发:", self.idle_minutes)

        self.auto_debate_cb = QCheckBox("启用自动辩论")
        self.auto_debate_cb.setChecked(True)
        sched_layout.addRow("", self.auto_debate_cb)

        self.auto_external_cb = QCheckBox("启用外部抓取")
        self.auto_external_cb.setChecked(False)
        sched_layout.addRow("", self.auto_external_cb)

        sched_group.setLayout(sched_layout)
        layout.addWidget(sched_group)

        # 安全设置
        safety_group = QGroupBox("安全管道")
        safety_layout = QFormLayout()

        self.strict_mode_cb = QCheckBox("严格模式 (警告也拦截)")
        self.strict_mode_cb.setChecked(True)
        safety_layout.addRow("", self.strict_mode_cb)

        safety_group.setLayout(safety_layout)
        layout.addWidget(safety_group)

        # 关键词管理
        kw_group = QGroupBox("关键词管理")
        kw_layout = QVBoxLayout()

        kw_layout.addWidget(QLabel("拦截关键词（一行一个）:"))
        self.block_keywords = QTextBrowser()
        self.block_keywords.setMaximumHeight(100)
        kw_layout.addWidget(self.block_keywords)

        add_block_btn = QPushButton("➕ 添加拦截词")
        add_block_btn.clicked.connect(self._add_block_keyword)
        kw_layout.addWidget(add_block_btn)

        kw_layout.addWidget(QLabel("警告关键词:"))
        self.warn_keywords = QTextBrowser()
        self.warn_keywords.setMaximumHeight(100)
        kw_layout.addWidget(self.warn_keywords)

        add_warn_btn = QPushButton("➕ 添加警告词")
        add_warn_btn.clicked.connect(self._add_warn_keyword)
        kw_layout.addWidget(add_warn_btn)

        kw_group.setLayout(kw_layout)
        layout.addWidget(kw_group)

        layout.addStretch()
        w.setWidget(container)
        return w

    # ============================================================
    # 数据刷新
    # ============================================================

    def refresh(self):
        """刷新所有数据"""
        self._ensure_system()
        if self.system is None:
            return

        try:
            # 更新统计
            stats = self.system.get_full_stats()

            self.stat_labels.get("pending_debates", QLabel()).setText(
                str(stats.get("debates", {}).get("pending", 0))
            )
            self.stat_labels.get("approved_debates", QLabel()).setText(
                str(stats.get("debates", {}).get("approved", 0))
            )
            self.stat_labels.get("pending_insights", QLabel()).setText(
                str(stats.get("insights", {}).get("pending", 0))
            )
            self.stat_labels.get("total_knowledge", QLabel()).setText(
                str(stats.get("knowledge", {}).get("total", 0))
            )
            self.stat_labels.get("safety_blocked", QLabel()).setText(
                str(len(stats.get("safety", {}).get("block_list", [])))
            )

            # 更新启用状态
            self.enable_btn.setChecked(self.system.is_enabled())
            self.enable_btn.setText("启用" if self.system.is_enabled() else "禁用")

            # 刷新各标签页
            self._refresh_pending_list()
            self._refresh_debate_list()
            self._refresh_insight_list()
            self._refresh_knowledge_table()

        except Exception as e:
            print(f"[ThoughtAuditPanel] Refresh error: {e}")
            traceback.print_exc()

    def _refresh_pending_list(self):
        """刷新待审核列表"""
        self.pending_list.clear()
        pending = self.system.get_pending_review()

        for item in pending.get("pending_debates", []):
            self.pending_list.addItem(f"⚖️ 辩论: {item['topic'][:30]}... [{item['created_at']}]")

        for item in pending.get("pending_insights", []):
            self.pending_list.addItem(f"🌐 洞察: {item['title'][:30]}... [{item['source']}]")

    def _refresh_debate_list(self):
        """刷新辩论列表"""
        self.debate_list.clear()
        debates = self.system.list_debates(limit=50)

        filter_text = self.debate_filter.currentText()
        for d in debates:
            if filter_text == "待审核" and not d.get("needs_review"):
                continue
            if filter_text == "已认可":
                continue  # 简化

            verdict_icon = {
                "pending": "⏳",
                "approved": "✅",
                "rejected": "❌",
            }.get(d.get("human_verdict", "pending"), "⏳")

            self.debate_list.addItem(
                f"{verdict_icon} {d['topic'][:40]}... [{d['created_at']}]"
            )

    def _refresh_insight_list(self):
        """刷新洞察列表"""
        self.insight_list.clear()
        insights = self.system.get_pending_insights(limit=50)

        for item in insights:
            self.insight_list.addItem(
                f"[{item['source']}] {item['title'][:40]}... "
                f"(差异: {item['difference'][:20]})"
            )

    def _refresh_knowledge_table(self):
        """刷新知识库表格"""
        self.knowledge_table.setRowCount(0)
        entries = self.system.get_knowledge(limit=100)

        for row, entry in enumerate(entries):
            self.knowledge_table.insertRow(row)
            self.knowledge_table.setItem(row, 0, QTableWidgetItem(entry["id"][:8]))
            self.knowledge_table.setItem(row, 1, QTableWidgetItem(entry["category"]))
            self.knowledge_table.setItem(row, 2, QTableWidgetItem(entry["key"]))
            self.knowledge_table.setItem(row, 3, QTableWidgetItem(entry["value"][:50]))
            self.knowledge_table.setItem(row, 4, QTableWidgetItem(str(entry["version"])))

    # ============================================================
    # 交互操作
    # ============================================================

    def _toggle_enabled(self, checked: bool):
        """切换启用状态"""
        self._ensure_system()
        if self.system:
            if checked:
                self.system.enable()
            else:
                self.system.disable()
            self.refresh()

    def _on_pending_item_clicked(self, item: QListWidgetItem):
        """点击待审核项"""
        text = item.text()
        if text.startswith("⚖️"):
            self.tabs.setCurrentIndex(1)  # 切换到辩论审核
        elif text.startswith("🌐"):
            self.tabs.setCurrentIndex(2)  # 切换到外部洞察

    def _show_debate_detail(self, item: QListWidgetItem):
        """显示辩论详情"""
        text = item.text()
        # 提取辩论主题
        topic = text.split(" ", 1)[1].split(" [")[0] if " " in text else text

        # 查找完整记录
        debates = self.system.list_debates(limit=100)
        for d in debates:
            if d["topic"][:40] in text or text in d["topic"][:40]:
                detail = self.system.get_debate(d["id"])
                if detail:
                    html = self._format_debate_html(detail)
                    self.debate_detail.setHtml(html)
                    self.current_debate_id = d["id"]
                break

    def _format_debate_html(self, detail: dict) -> str:
        """格式化辩论为 HTML"""
        html = f"""
        <h2>{detail['topic']}</h2>
        <p><b>类别:</b> {detail['category']} | <b>裁决:</b> {detail['verdict']} | <b>人工:</b> {detail['human_verdict']}</p>

        <h3>🛡️ 保守派观点</h3>
        """
        for arg in detail.get("conservative_args", []):
            html += f"<blockquote>{arg['论点']}<br><i>置信度: {arg['confidence']}</i></blockquote>"

        html += "<h3>🚀 激进派观点</h3>"
        for arg in detail.get("radical_args", []):
            html += f"<blockquote>{arg['论点']}<br><i>置信度: {arg['confidence']}</i></blockquote>"

        html += f"""
        <h3>📝 最终结论</h3>
        <p>{detail['conclusion']}</p>
        """

        if detail.get("contradictions"):
            html += "<h3>⚠️ 矛盾点</h3><ul>"
            for c in detail["contradictions"]:
                html += f"<li>{c}</li>"
            html += "</ul>"

        return html

    def _review_debate(self, verdict: str):
        """审核辩论"""
        if not hasattr(self, "current_debate_id"):
            return

        from .self_upgrade.models import HumanVerdict

        verdict_map = {
            "approved": HumanVerdict.APPROVED,
            "revised": HumanVerdict.REVISED,
            "rejected": HumanVerdict.REJECTED,
        }

        conclusion = None
        notes = ""

        if verdict == "revised":
            # 弹出修改对话框
            dialog = QDialog(self)
            dialog.setWindowTitle("修改结论")
            layout = QVBoxLayout(dialog)
            layout.addWidget(QLabel("新结论:"))
            new_conclusion = QTextBrowser()
            layout.addWidget(new_conclusion)
            btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            btns.accepted.connect(lambda: setattr(self, "_new_conclusion_temp", new_conclusion.toPlainText()) or dialog.accept())
            btns.rejected.connect(dialog.reject)
            layout.addWidget(btns)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                conclusion = getattr(self, "_new_conclusion_temp", "")
            else:
                return

        success = self.system.review_debate(
            self.current_debate_id,
            verdict_map[verdict],
            conclusion=conclusion,
            notes=notes,
        )

        if success:
            self.refresh()

    def _new_debate(self):
        """新建辩论"""
        dialog = QDialog(self)
        dialog.setWindowTitle("新建辩论")
        layout = QFormLayout(dialog)

        topic_input = QLineEdit()
        topic_input.setPlaceholderText("输入辩论主题...")
        layout.addRow("辩题:", topic_input)

        category_input = QComboBox()
        category_input.addItems(["general", "network", "performance", "security", "ux"])
        layout.addRow("类别:", category_input)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addRow(btns)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            topic = topic_input.text()
            if topic:
                self.system.trigger_manual_debate(topic, category_input.currentText())
                self.refresh()

    def _filter_debates(self, text: str):
        """过滤辩论"""
        self._refresh_debate_list()

    def _show_insight_detail(self, item: QListWidgetItem):
        """显示洞察详情"""
        text = item.text()
        self.insight_detail.setHtml(f"<p>{text}</p>")

    def _absorb_insight(self):
        """吸收洞察"""
        current_row = self.insight_list.currentRow()
        if current_row >= 0:
            # 获取洞察并吸收
            self.refresh()

    def _dismiss_insight(self):
        """忽略洞察"""
        current_row = self.insight_list.currentRow()
        if current_row >= 0:
            self.insight_list.takeItem(current_row)

    def _fetch_external(self):
        """抓取外部内容"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # 触发抓取
        self.system.trigger_manual("external", "GitHub Issues")
        self.refresh()

    def _search_knowledge(self, keyword: str):
        """搜索知识"""
        if len(keyword) >= 2:
            entries = self.system.get_knowledge(keyword=keyword, limit=50)
            self.knowledge_table.setRowCount(0)
            for row, entry in enumerate(entries):
                self.knowledge_table.insertRow(row)
                self.knowledge_table.setItem(row, 0, QTableWidgetItem(entry["id"][:8]))
                self.knowledge_table.setItem(row, 1, QTableWidgetItem(entry["category"]))
                self.knowledge_table.setItem(row, 2, QTableWidgetItem(entry["key"]))
                self.knowledge_table.setItem(row, 3, QTableWidgetItem(entry["value"][:50]))
                self.knowledge_table.setItem(row, 4, QTableWidgetItem(str(entry["version"])))
        elif keyword == "":
            self._refresh_knowledge_table()

    def _add_knowledge(self):
        """添加知识"""
        dialog = QDialog(self)
        dialog.setWindowTitle("添加知识")
        layout = QFormLayout(dialog)

        category_input = QLineEdit()
        category_input.setText("general")
        layout.addRow("类别:", category_input)

        key_input = QLineEdit()
        layout.addRow("Key:", key_input)

        value_input = QTextBrowser()
        layout.addRow("值:", value_input)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addRow(btns)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            if key_input.text():
                self.system.add_knowledge(
                    category_input.text(),
                    key_input.text(),
                    value_input.toPlainText(),
                )
                self.refresh()

    def _delete_knowledge(self):
        """删除知识"""
        row = self.knowledge_table.currentRow()
        if row >= 0:
            self.knowledge_table.removeRow(row)

    def _add_block_keyword(self):
        """添加拦截关键词"""
        dialog = QDialog(self)
        dialog.setWindowTitle("添加拦截词")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("关键词:"))
        keyword_input = QLineEdit()
        layout.addWidget(keyword_input)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addWidget(btns)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            kw = keyword_input.text()
            if kw:
                self.system.add_block_keyword(kw)

    def _add_warn_keyword(self):
        """添加警告关键词"""
        dialog = QDialog(self)
        dialog.setWindowTitle("添加警告词")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("关键词:"))
        keyword_input = QLineEdit()
        layout.addWidget(keyword_input)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addWidget(btns)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            kw = keyword_input.text()
            if kw:
                self.system.add_warn_keyword(kw)

    # ============================================================
    # 生命周期
    # ============================================================

    def showEvent(self, event):
        """显示时刷新"""
        super().showEvent(event)
        self.refresh()
        self._refresh_timer.start()

    def hideEvent(self, event):
        """隐藏时停止刷新"""
        super().hideEvent(event)
        self._refresh_timer.stop()
