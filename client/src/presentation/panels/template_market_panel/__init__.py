"""
模板市场与智能表单UI面板

功能：
1. 模板市场 - 上传/下载/预览/投票
2. 智能表单 - 创建/填写/提交
3. 工作流 - 设计/执行/监控
4. 数据检索 - 自然语言查询
5. 升级管理 - 检查/预览/确认
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QTabWidget, QTableWidget, QTableWidgetItem, QPushButton,
    QLabel, QLineEdit, QTextEdit, QComboBox, QListWidget,
    QListWidgetItem, QDialog, QDialogButtonBox, QProgressBar,
    QGroupBox, QFormLayout, QSplitter, QScrollArea,
    QStatusBar, QMenuBar, QMenu, QToolBar, QFrame,
    QTreeWidget, QTreeWidgetItem, QCheckBox, QRadioButton,
    QButtonGroup, QSpinBox, QSlider, QColorDialog,
    QFontDialog, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QSize
from PyQt6.QtGui import QAction, QIcon, QPalette, QColor


class TemplateMarketPanel(QWidget):
    """模板市场面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.market = None  # TemplateMarket instance
        self.current_template = None
        self.pending_votes = []

        self._init_ui()
        self._init_connections()

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 顶部工具栏
        toolbar = QToolBar()
        toolbar.setMovable(False)

        self.capture_action = QAction("📸 捕获窗口", self)
        self.upload_action = QAction("⬆️ 上传模板", self)
        self.refresh_action = QAction("🔄 刷新", self)
        self.search_action = QAction("🔍 搜索", self)

        toolbar.addAction(self.capture_action)
        toolbar.addAction(self.upload_action)
        toolbar.addSeparator()
        toolbar.addAction(self.refresh_action)
        toolbar.addAction(self.search_action)

        # 搜索栏
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索模板...")
        self.category_combo = QComboBox()
        self.category_combo.addItems(["全部", "已捕获", "表单", "工作流", "UI组件"])
        search_layout.addWidget(QLabel("分类:"))
        self.category_combo.addWidget(self.search_input)
        search_layout.addWidget(self.category_combo)

        layout.addWidget(toolbar)

        # 主内容区 - 左右分栏
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：模板列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        self.template_list = QListWidget()
        self.template_list.setAlternatingRowColors(True)
        left_layout.addWidget(QLabel("📦 模板列表"))
        left_layout.addWidget(self.template_list)

        # 右侧：详情区
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # 模板详情
        detail_group = QGroupBox("模板详情")
        detail_layout = QFormLayout()

        self.template_name_label = QLabel("-")
        self.template_author_label = QLabel("-")
        self.template_version_label = QLabel("-")
        self.template_downloads_label = QLabel("-")
        self.template_rating_label = QLabel("-")
        self.template_desc_text = QTextEdit()
        self.template_desc_text.setReadOnly(True)
        self.template_desc_text.setMaximumHeight(80)

        detail_layout.addRow("名称:", self.template_name_label)
        detail_layout.addRow("作者:", self.template_author_label)
        detail_layout.addRow("版本:", self.template_version_label)
        detail_layout.addRow("下载:", self.template_downloads_label)
        detail_layout.addRow("评分:", self.template_rating_label)
        detail_layout.addRow("描述:", self.template_desc_text)
        detail_group.setLayout(detail_layout)
        right_layout.addWidget(detail_group)

        # 预览区
        preview_group = QGroupBox("👁️ 预览")
        preview_layout = QVBoxLayout()
        self.preview_widget = QLabel("选择模板查看预览")
        self.preview_widget.setFrameStyle(QFrame.Shape.StyledPanel)
        self.preview_widget.setMinimumSize(300, 200)
        self.preview_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(self.preview_widget)
        preview_group.setLayout(preview_layout)
        right_layout.addWidget(preview_group)

        # 操作按钮
        action_layout = QHBoxLayout()
        self.download_btn = QPushButton("📥 下载")
        self.fork_btn = QPushButton("🍴 Fork")
        self.edit_btn = QPushButton("✏️ 编辑")
        self.delete_btn = QPushButton("🗑️ 删除")
        self.vote_delete_btn = QPushButton("🗳️ 投票删除")

        action_layout.addWidget(self.download_btn)
        action_layout.addWidget(self.fork_btn)
        action_layout.addWidget(self.edit_btn)
        action_layout.addWidget(self.delete_btn)
        action_layout.addWidget(self.vote_delete_btn)
        right_layout.addLayout(action_layout)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        layout.addLayout(search_layout)
        layout.addWidget(splitter)

        # 状态栏
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("就绪")
        layout.addWidget(self.status_bar)

    def _init_connections(self):
        """初始化连接"""
        self.capture_action.triggered.connect(self._on_capture_window)
        self.upload_action.triggered.connect(self._on_upload_template)
        self.refresh_action.triggered.connect(self._on_refresh)
        self.template_list.itemClicked.connect(self._on_template_selected)
        self.download_btn.clicked.connect(self._on_download)
        self.fork_btn.clicked.connect(self._on_fork)
        self.delete_btn.clicked.connect(self._on_delete)
        self.vote_delete_btn.clicked.connect(self._on_vote_delete)

    def _on_capture_window(self):
        """捕获窗口"""
        if self.market:
            template = self.market.capture_window_as_template()
            if template:
                self.status_bar.showMessage(f"已捕获窗口并创建模板: {template.name}")
                self._on_refresh()
            else:
                self.status_bar.showMessage("捕获失败，请确保有焦点窗口")

    def _on_upload_template(self):
        """上传模板"""
        dialog = TemplateUploadDialog(self)
        if dialog.exec():
            self.status_bar.showMessage("模板上传成功")
            self._on_refresh()

    def _on_refresh(self):
        """刷新列表"""
        if not self.market:
            return

        self.template_list.clear()
        templates = self.market.store.list_templates()

        for template in templates:
            item = QListWidgetItem()
            item.setText(f"📦 {template.name} - by {template.author_name}")
            item.setData(Qt.ItemDataRole.UserRole, template.id)
            self.template_list.addItem(item)

        self.status_bar.showMessage(f"共 {len(templates)} 个模板")

    def _on_template_selected(self, item):
        """选择模板"""
        template_id = item.data(Qt.ItemDataRole.UserRole)
        if self.market:
            template = self.market.store.get_template(template_id)
            if template:
                self.current_template = template
                self._update_template_detail(template)

    def _update_template_detail(self, template):
        """更新模板详情"""
        self.template_name_label.setText(template.name)
        self.template_author_label.setText(template.author_name)
        self.template_version_label.setText(template.version)
        self.template_downloads_label.setText(str(template.download_count))
        self.template_rating_label.setText(f"{template.rating:.1f} ⭐ ({template.rating_count})")
        self.template_desc_text.setPlainText(template.description)

        # 更新预览
        self.preview_widget.setText(f"UI树预览\n{json.dumps(template.ui_tree, indent=2, ensure_ascii=False)[:500]}...")

    def _on_download(self):
        """下载模板"""
        if self.current_template:
            template = self.market.download_template(self.current_template.id)
            if template:
                self.status_bar.showMessage(f"下载成功: {template.name}")

    def _on_fork(self):
        """Fork模板"""
        if self.current_template:
            dialog = QInputDialog(self)
            dialog.setWindowTitle("Fork模板")
            dialog.setLabelText("新模板名称:")
            dialog.setTextValue(f"{self.current_template.name} (Fork)")

            if dialog.exec():
                new_name = dialog.textValue()
                forked = self.market.fork_template(self.current_template.id, new_name)
                if forked:
                    self.status_bar.showMessage(f"Fork成功: {forked.name}")
                    self._on_refresh()

    def _on_delete(self):
        """删除模板（仅上传者可删除）"""
        if not self.current_template:
            return

        # 检查是否是上传者
        if self.current_template.author_id != self.market.current_user_id:
            QMessageBox.warning(self, "无法删除", "只有上传者才能删除模板")
            return

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除模板「{self.current_template.name}」吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            if self.market.store.delete_template(self.current_template.id, self.market.current_user_id):
                self.status_bar.showMessage("删除成功")
                self._on_refresh()

    def _on_vote_delete(self):
        """投票删除"""
        if not self.current_template:
            return

        if self.current_template.author_id == self.market.current_user_id:
            QMessageBox.warning(self, "无法投票", "上传者不能发起自己的删除投票")
            return

        dialog = QInputDialog(self)
        dialog.setWindowTitle("投票删除")
        dialog.setLabelText("请输入删除原因:")
        dialog.setTextValue("")

        if dialog.exec():
            reason = dialog.textValue()
            vote_id = self.market.initiate_delete_vote(self.current_template.id, reason)
            if vote_id:
                self.status_bar.showMessage("投票发起成功")
                self._load_pending_votes()
            else:
                QMessageBox.warning(self, "投票失败", "无法发起投票")

    def _load_pending_votes(self):
        """加载待处理投票"""
        if not self.current_template:
            return

        votes = self.market.store.get_pending_votes_for_target(self.current_template.id)
        self.pending_votes = votes

        # 显示投票状态
        if votes:
            vote = votes[0]
            total = len(vote.upvotes) + len(vote.downvotes)
            self.status_bar.showMessage(
                f"删除投票进行中: {len(vote.upvotes)}赞成 / {len(vote.downvotes)}反对 (共{total}票)"
            )


class SmartFormPanel(QWidget):
    """智能表单面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.form_manager = None  # SmartFormManager instance
        self.current_template = None
        self.current_submission = None

        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 标签页
        tabs = QTabWidget()

        # Tab 1: 表单模板
        template_tab = QWidget()
        template_layout = QVBoxLayout(template_tab)

        # 模板列表
        self.form_template_list = QListWidget()
        self.form_template_list.itemClicked.connect(self._on_template_selected)
        template_layout.addWidget(QLabel("📋 表单模板"))
        template_layout.addWidget(self.form_template_list)

        # 模板操作
        template_btn_layout = QHBoxLayout()
        self.create_form_btn = QPushButton("➕ 创建模板")
        self.edit_form_btn = QPushButton("✏️ 编辑")
        self.delete_form_btn = QPushButton("🗑️ 删除")
        template_btn_layout.addWidget(self.create_form_btn)
        template_btn_layout.addWidget(self.edit_form_btn)
        template_btn_layout.addWidget(self.delete_form_btn)
        template_layout.addLayout(template_btn_layout)

        tabs.addTab(template_tab, "📋 模板管理")

        # Tab 2: 表单填写
        fill_tab = QWidget()
        fill_layout = QVBoxLayout(fill_tab)

        self.form_preview = QTextEdit()
        self.form_preview.setReadOnly(True)
        fill_layout.addWidget(QLabel("表单预览"))
        fill_layout.addWidget(self.form_preview)

        # 填写操作
        fill_btn_layout = QHBoxLayout()
        self.preview_form_btn = QPushButton("👁️ 预览")
        self.submit_form_btn = QPushButton("📤 提交")
        self.save_draft_btn = QPushButton("💾 保存草稿")
        fill_btn_layout.addWidget(self.preview_form_btn)
        fill_btn_layout.addWidget(self.submit_form_btn)
        fill_btn_layout.addWidget(self.save_draft_btn)
        fill_layout.addLayout(fill_btn_layout)

        tabs.addTab(fill_tab, "✍️ 填写表单")

        # Tab 3: 提交记录
        records_tab = QWidget()
        records_layout = QVBoxLayout(records_tab)

        self.submissions_table = QTableWidget()
        self.submissions_table.setColumnCount(5)
        self.submissions_table.setHorizontalHeaderLabels(["ID", "模板", "提交人", "时间", "状态"])
        records_layout.addWidget(QLabel("📜 提交记录"))
        records_layout.addWidget(self.submissions_table)

        tabs.addTab(records_tab, "📜 提交记录")

        layout.addWidget(tabs)

    def _on_template_selected(self, item):
        """选择模板"""
        # 实现模板选择逻辑
        pass

    def refresh_templates(self):
        """刷新模板列表"""
        if not self.form_manager:
            return

        self.form_template_list.clear()
        templates = self.form_manager.list_templates()

        for template in templates:
            item = QListWidgetItem(f"📋 {template.name}")
            item.setData(Qt.ItemDataRole.UserRole, template.id)
            self.form_template_list.addItem(item)


class WorkflowPanel(QWidget):
    """工作流面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.workflow_store = None  # WorkflowStore instance
        self.workflow_engine = None  # WorkflowEngine instance
        self.current_workflow = None
        self.current_execution = None

        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 顶部工具栏
        toolbar = QToolBar()

        self.create_workflow_action = QAction("➕ 新建工作流", self)
        self.import_action = QAction("📥 导入", self)
        self.export_action = QAction("📤 导出", self)
        self.execute_action = QAction("▶️ 执行", self)

        toolbar.addAction(self.create_workflow_action)
        toolbar.addAction(self.import_action)
        toolbar.addAction(self.export_action)
        toolbar.addSeparator()
        toolbar.addAction(self.execute_action)

        layout.addWidget(toolbar)

        # 标签页
        tabs = QTabWidget()

        # Tab 1: 工作流设计
        design_tab = QWidget()
        design_layout = QVBoxLayout(design_tab)

        # 左侧：节点列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.addWidget(QLabel("🧩 节点组件"))

        self.node_list = QListWidget()
        self.node_list.addItems([
            "▶️ 开始节点",
            "📋 任务节点",
            "✅ 审批节点",
            "❓ 条件节点",
            "🔀 分支节点",
            "⏹️ 结束节点"
        ])
        left_layout.addWidget(self.node_list)

        # 中间：画布
        center_widget = QFrame()
        center_layout = QVBoxLayout(center_widget)
        center_layout.addWidget(QLabel("🎨 工作流设计画布"))
        self.workflow_canvas = QLabel("拖拽节点到此处设计工作流")
        self.workflow_canvas.setFrameStyle(QFrame.Shape.StyledPanel)
        self.workflow_canvas.setMinimumSize(400, 300)
        self.workflow_canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.addWidget(self.workflow_canvas)

        # 右侧：属性面板
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.addWidget(QLabel("⚙️ 节点属性"))

        prop_group = QGroupBox("属性")
        prop_layout = QFormLayout()
        self.node_name_input = QLineEdit()
        self.node_type_combo = QComboBox()
        self.node_assignee_input = QLineEdit()
        self.node_due_days = QSpinBox()

        prop_layout.addRow("名称:", self.node_name_input)
        prop_layout.addRow("类型:", self.node_type_combo)
        prop_layout.addRow("处理人:", self.node_assignee_input)
        prop_layout.addRow("期限(天):", self.node_due_days)
        prop_group.setLayout(prop_layout)
        right_layout.addWidget(prop_group)

        # 三栏布局
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(center_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 1)

        design_layout.addWidget(splitter)

        tabs.addTab(design_tab, "🎨 设计")

        # Tab 2: 执行监控
        monitor_tab = QWidget()
        monitor_layout = QVBoxLayout(monitor_tab)

        self.execution_table = QTableWidget()
        self.execution_table.setColumnCount(6)
        self.execution_table.setHorizontalHeaderLabels(["ID", "工作流", "发起人", "状态", "当前节点", "操作"])
        monitor_layout.addWidget(QLabel("📊 执行实例"))
        monitor_layout.addWidget(self.execution_table)

        tabs.addTab(monitor_tab, "📊 监控")

        # Tab 3: 模板库
        templates_tab = QWidget()
        templates_layout = QVBoxLayout(templates_tab)

        self.workflow_templates = QListWidget()
        self.workflow_templates.addItems([
            "📄 简单审批流程",
            "📄 多级审批流程",
            "📄 任务分配流程",
            "📄 数据收集流程"
        ])
        templates_layout.addWidget(QLabel("📚 工作流模板"))
        templates_layout.addWidget(self.workflow_templates)

        templates_btn_layout = QHBoxLayout()
        self.use_template_btn = QPushButton("使用模板")
        templates_btn_layout.addWidget(self.use_template_btn)
        templates_layout.addLayout(templates_btn_layout)

        tabs.addTab(templates_tab, "📚 模板库")

        layout.addWidget(tabs)


class DataRetrieverPanel(QWidget):
    """数据检索面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.retriever = None  # UniversalDataRetriever instance
        self.explorer = None  # ConversationalDataExplorer instance

        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 搜索区
        search_group = QGroupBox("🔍 数据检索")
        search_layout = QVBoxLayout()

        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("输入自然语言查询，如：查找最近的表单提交...")
        self.query_input.returnPressed.connect(self._on_search)

        search_btn_layout = QHBoxLayout()
        self.search_btn = QPushButton("🔍 搜索")
        self.clear_btn = QPushButton("🗑️ 清除")
        self.export_btn = QPushButton("📤 导出")

        search_btn_layout.addWidget(self.search_btn)
        search_btn_layout.addWidget(self.clear_btn)
        search_btn_layout.addStretch()
        search_btn_layout.addWidget(self.export_btn)

        search_layout.addWidget(self.query_input)
        search_layout.addLayout(search_btn_layout)
        search_group.setLayout(search_layout)

        layout.addWidget(search_group)

        # 结果区
        splitter = QSplitter(Qt.Orientation.Vertical)

        # 摘要
        summary_group = QGroupBox("📝 查询摘要")
        summary_layout = QVBoxLayout()
        self.summary_label = QLabel("输入查询查看结果")
        summary_layout.addWidget(self.summary_label)
        summary_group.setLayout(summary_layout)

        # 结果表格
        result_group = QGroupBox("📊 查询结果")
        result_layout = QVBoxLayout()
        self.result_table = QTableWidget()
        self.result_table.setAlternatingRowColors(True)
        result_layout.addWidget(self.result_table)
        result_group.setLayout(result_layout)

        splitter.addWidget(summary_group)
        splitter.addWidget(result_group)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)

        layout.addWidget(splitter)

        # 建议区
        suggestions_group = QGroupBox("💡 智能建议")
        suggestions_layout = QHBoxLayout()
        self.suggestion_list = QListWidget()
        self.suggestion_list.itemClicked.connect(self._on_suggestion_clicked)
        suggestions_layout.addWidget(self.suggestion_list)
        suggestions_group.setLayout(suggestions_layout)

        layout.addWidget(suggestions_group)

    def _on_search(self):
        """执行搜索"""
        query = self.query_input.text()
        if not query:
            return

        # 异步执行搜索
        # self.explorer.process_query(query)
        self.summary_label.setText(f"正在搜索: {query}")

    def _on_suggestion_clicked(self, item):
        """点击建议"""
        suggestion = item.text()
        self.query_input.setText(suggestion)
        self._on_search()

    def display_results(self, results):
        """显示结果"""
        if not results:
            return

        # 更新摘要
        self.summary_label.setText(results.summary)

        # 更新表格
        if results.results:
            keys = list(results.results[0].keys())
            self.result_table.setColumnCount(len(keys))
            self.result_table.setHorizontalHeaderLabels(keys)
            self.result_table.setRowCount(len(results.results))

            for i, row in enumerate(results.results):
                for j, key in enumerate(keys):
                    value = row.get(key, "")
                    self.result_table.setItem(i, j, QTableWidgetItem(str(value)))

        # 更新建议
        self.suggestion_list.clear()
        for suggestion in results.suggestions:
            self.suggestion_list.addItem(suggestion)


class UpgradePanel(QWidget):
    """升级管理面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.upgrade_manager = None  # SmartUpgradeManager instance
        self.notification_manager = None  # UpgradeNotificationManager instance

        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 顶部版本信息
        version_group = QGroupBox("📌 版本信息")
        version_layout = QHBoxLayout()

        self.current_version_label = QLabel("当前版本: v1.0.0")
        self.check_update_btn = QPushButton("🔄 检查更新")
        self.upgrade_history_btn = QPushButton("📜 升级历史")

        version_layout.addWidget(self.current_version_label)
        version_layout.addStretch()
        version_layout.addWidget(self.check_update_btn)
        version_layout.addWidget(self.upgrade_history_btn)
        version_group.setLayout(version_layout)

        layout.addWidget(version_group)

        # 更新通知区
        self.update_notification = QGroupBox("🆕 有可用更新")
        notification_layout = QVBoxLayout()

        self.update_version_label = QLabel("新版本: v2.0.0")
        self.update_title_label = QLabel("标题: 重大功能更新")
        self.update_desc_text = QTextEdit()
        self.update_desc_text.setReadOnly(True)
        self.update_desc_text.setMaximumHeight(100)

        notification_layout.addWidget(self.update_version_label)
        notification_layout.addWidget(self.update_title_label)
        notification_layout.addWidget(self.update_desc_text)

        # 更新内容
        content_group = QGroupBox("更新内容")
        content_layout = QVBoxLayout()

        self.new_features_list = QListWidget()
        self.bug_fixes_list = QListWidget()
        content_layout.addWidget(QLabel("✨ 新功能:"))
        content_layout.addWidget(self.new_features_list)
        content_layout.addWidget(QLabel("🐛 Bug修复:"))
        content_layout.addWidget(self.bug_fixes_list)
        content_group.setLayout(content_layout)
        notification_layout.addWidget(content_group)

        # 操作按钮
        notification_btn_layout = QHBoxLayout()
        self.acknowledge_btn = QPushButton("✅ 已知悉")
        self.upgrade_now_btn = QPushButton("🚀 立即升级")
        self.defer_btn = QPushButton("⏰ 稍后提醒")
        self.vote_withdraw_btn = QPushButton("🗳️ 投票撤回")

        notification_btn_layout.addWidget(self.acknowledge_btn)
        notification_btn_layout.addWidget(self.upgrade_now_btn)
        notification_btn_layout.addWidget(self.defer_btn)
        notification_btn_layout.addWidget(self.vote_withdraw_btn)
        notification_layout.addLayout(notification_btn_layout)

        self.update_notification.setLayout(notification_layout)
        layout.addWidget(self.update_notification)

        # 升级策略
        strategy_group = QGroupBox("🛡️ 升级策略")
        strategy_layout = QVBoxLayout()

        self.strategy_group = QButtonGroup()
        self.preserve_radio = QRadioButton("保留所有用户自定义（推荐）")
        self.selective_radio = QRadioButton("选择性合并新功能")
        self.fresh_radio = QRadioButton("全新安装，导入用户数据")

        self.preserve_radio.setChecked(True)
        self.strategy_group.addButton(self.preserve_radio, 1)
        self.strategy_group.addButton(self.selective_radio, 2)
        self.strategy_group.addButton(self.fresh_radio, 3)

        strategy_layout.addWidget(self.preserve_radio)
        strategy_layout.addWidget(self.selective_radio)
        strategy_layout.addWidget(self.fresh_radio)
        strategy_group.setLayout(strategy_layout)

        layout.addWidget(strategy_group)

        # 进度条
        self.upgrade_progress = QProgressBar()
        self.upgrade_progress.setVisible(False)
        layout.addWidget(self.upgrade_progress)

        # 风险提示
        risk_group = QGroupBox("⚠️ 风险提示")
        risk_layout = QVBoxLayout()
        self.risk_label = QLabel("风险等级: 低")
        self.risk_factors_list = QListWidget()
        risk_layout.addWidget(self.risk_label)
        risk_layout.addWidget(self.risk_factors_list)
        risk_group.setLayout(risk_layout)

        layout.addWidget(risk_group)

    def check_for_updates(self):
        """检查更新"""
        if self.upgrade_manager:
            # 异步检查更新
            pass

    def show_update_notification(self, update_info):
        """显示更新通知"""
        self.update_version_label.setText(f"新版本: {update_info.get('version', '')}")
        self.update_title_label.setText(f"标题: {update_info.get('title', '')}")
        self.update_desc_text.setPlainText(update_info.get('description', ''))

        self.new_features_list.clear()
        for feature in update_info.get('new_features', []):
            self.new_features_list.addItem(f"✨ {feature}")

        self.bug_fixes_list.clear()
        for fix in update_info.get('bug_fixes', []):
            self.bug_fixes_list.addItem(f"🐛 {fix}")

        self.update_notification.setVisible(True)

    def start_upgrade(self):
        """开始升级"""
        # 获取选定的策略
        strategy_id = self.strategy_group.checkedId()
        strategies = {
            1: "preserve_all",
            2: "selective_merge",
            3: "fresh_install"
        }
        strategy = strategies.get(strategy_id, "preserve_all")

        # 显示进度
        self.upgrade_progress.setVisible(True)
        self.upgrade_progress.setValue(0)

        # 执行升级
        # self.upgrade_manager.perform_upgrade(package, strategy)

    def show_new_version_banner(self):
        """在标题栏显示新版本提示"""
        # 这个方法可以被main_window调用来显示标题栏提示
        pass


# 辅助对话框
class TemplateUploadDialog(QDialog):
    """模板上传对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("上传模板")
        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        form_layout = QFormLayout()
        self.name_input = QLineEdit()
        self.description_input = QTextEdit()
        self.category_combo = QComboBox()
        self.category_combo.addItems(["已捕获", "表单", "工作流", "UI组件", "其他"])

        form_layout.addRow("名称:", self.name_input)
        form_layout.addRow("描述:", self.description_input)
        form_layout.addRow("分类:", self.category_combo)

        layout.addLayout(form_layout)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class QInputDialog:
    """简化的输入对话框（使用QInputDialog替代）"""
    pass


# 导入必要的模块
import json