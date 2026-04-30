"""
数据库浏览器 UI 面板
借鉴 onetcli 多数据库管理界面
支持：连接管理 / 数据库树 / SQL 查询 / AI 助手 / 表结构
"""

import sys
import threading
import time
import json
import re
from typing import List, Optional, Any, Tuple

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTreeWidget, QTreeWidgetItem,
    QTableWidget, QTableWidgetItem, QTextEdit, QPushButton, QLabel, QComboBox,
    QLineEdit, QTabWidget, QGroupBox, QFormLayout, QDialog, QDialogButtonBox,
    QMessageBox, QProgressBar, QToolBar, QStatusBar, QSpinBox, QCheckBox,
    QListWidget, QListWidgetItem, QTextBrowser, QScrollArea, QFrame,
    QGridLayout, QSplitter, QSizePolicy, QAbstractItemView
)
from PyQt6.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QSize, QAbstractTableModel, QModelIndex
)
from PyQt6.QtGui import (
    QFont, QColor, QAction, QTextCursor, QTextCharFormat, QTextTableFormat,
    QActionGroup, QIcon
)

from .business.database_browser import DatabaseBrowser, get_database_browser
from core.database_browser.models import (
    DatabaseType, ConnectionConfig, ConnectionStatus,
    TableSchema, QueryResult, QueryResultType, DEFAULT_PORTS,
    HistoryItem, FavoriteQuery
)


class DatabaseBrowserPanel(QWidget):
    """
    数据库浏览器主面板
    5 个标签页：连接管理 / 查询分析 / AI 助手 / 表结构 / 历史记录
    """

    def __init__(self):
        super().__init__()
        self.browser = get_database_browser()

        # UI 状态
        self._current_result: Optional[QueryResult] = None
        self._current_table: str = ""

        self._init_ui()
        self._refresh_connections()
        self._refresh_tree()

    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 顶部工具栏
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)

        # 主内容区：左侧数据库树 + 右侧标签页
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：数据库树
        self.tree_panel = self._create_tree_panel()
        splitter.addWidget(self.tree_panel)

        # 右侧：标签页
        self.right_panel = self._create_right_panel()
        splitter.addWidget(self.right_panel)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        layout.addWidget(splitter)

        # 底部状态栏
        self.status_bar = QStatusBar()
        self._update_status("就绪")
        layout.addWidget(self.status_bar)

    def _create_toolbar(self) -> QToolBar:
        """创建工具栏"""
        toolbar = QToolBar()
        toolbar.setIconSize(QSize(16, 16))

        # 连接选择
        toolbar.addWidget(QLabel(" 连接: "))
        self.conn_combo = QComboBox()
        self.conn_combo.setMinimumWidth(180)
        self.conn_combo.currentIndexChanged.connect(self._on_connection_changed)
        toolbar.addWidget(self.conn_combo)

        btn_connect = QPushButton("连接")
        btn_connect.clicked.connect(self._on_connect_clicked)
        toolbar.addWidget(btn_connect)

        btn_disconnect = QPushButton("断开")
        btn_disconnect.clicked.connect(self._on_disconnect_clicked)
        toolbar.addWidget(btn_disconnect)

        toolbar.addSeparator()

        btn_new = QPushButton("新建连接")
        btn_new.clicked.connect(self._show_new_connection_dialog)
        toolbar.addWidget(btn_new)

        btn_refresh = QPushButton("刷新树")
        btn_refresh.clicked.connect(self._refresh_tree)
        toolbar.addWidget(btn_refresh)

        toolbar.addWidget(QLabel("  |  "))

        btn_format = QPushButton("格式化SQL")
        btn_format.clicked.connect(self._format_sql)
        toolbar.addWidget(btn_format)

        return toolbar

    def _create_tree_panel(self) -> QWidget:
        """创建数据库树面板"""
        panel = QFrame()
        panel.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(2, 2, 2, 2)

        title = QLabel("🔗 数据库对象")
        title.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(title)

        self.db_tree = QTreeWidget()
        self.db_tree.setHeaderHidden(True)
        self.db_tree.setAnimated(True)
        self.db_tree.itemClicked.connect(self._on_tree_item_clicked)
        self.db_tree.itemExpanded.connect(self._on_tree_item_expanded)
        self.db_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.db_tree.customContextMenuRequested.connect(self._show_tree_context_menu)
        layout.addWidget(self.db_tree)

        return panel

    def _create_right_panel(self) -> QTabWidget:
        """创建右侧标签页"""
        tabs = QTabWidget()

        # 标签页1：查询分析
        tabs.addTab(self._create_query_tab(), "📝 查询分析")

        # 标签页2：AI 助手
        tabs.addTab(self._create_ai_tab(), "🤖 AI 助手")

        # 标签页3：表结构
        tabs.addTab(self._create_table_tab(), "🏗️ 表结构")

        # 标签页4：历史
        tabs.addTab(self._create_history_tab(), "📜 历史记录")

        return tabs

    def _create_query_tab(self) -> QWidget:
        """查询分析标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # SQL 编辑器
        editor_group = QGroupBox("SQL 编辑器")
        editor_layout = QVBoxLayout(editor_group)

        self.sql_editor = QTextEdit()
        self.sql_editor.setFont(QFont("Consolas", 10))
        self.sql_editor.setPlaceholderText("输入 SQL 语句，按 Ctrl+Enter 执行...")
        self.sql_editor.setMinimumHeight(120)
        self.sql_editor.setMaximumHeight(200)
        editor_layout.addWidget(self.sql_editor)

        # 执行按钮行
        btn_row = QHBoxLayout()
        self.btn_execute = QPushButton("▶ 执行 (Ctrl+Enter)")
        self.btn_execute.clicked.connect(self._execute_sql)
        btn_row.addWidget(self.btn_execute)

        self.btn_explain = QPushButton("📊 执行计划")
        self.btn_explain.clicked.connect(self._explain_sql)
        btn_row.addWidget(self.btn_explain)

        self.btn_export = QPushButton("💾 导出 CSV")
        self.btn_export.clicked.connect(self._export_csv)
        btn_row.addWidget(self.btn_export)

        btn_row.addStretch()

        # 分页控制
        btn_row.addWidget(QLabel(" 页面: "))
        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.setValue(1)
        self.page_spin.setMaximumWidth(80)
        self.page_spin.valueChanged.connect(self._on_page_changed)
        btn_row.addWidget(self.page_spin)

        btn_row.addWidget(QLabel(" 每页: "))
        self.page_size_spin = QSpinBox()
        self.page_size_spin.setMinimum(10)
        self.page_size_spin.setMaximum(1000)
        self.page_size_spin.setValue(100)
        self.page_size_spin.setMaximumWidth(80)
        self.page_size_spin.valueChanged.connect(self._on_page_size_changed)
        btn_row.addWidget(self.page_size_spin)

        editor_layout.addLayout(btn_row)
        layout.addWidget(editor_group)

        # 结果区
        result_group = QGroupBox("查询结果")
        result_layout = QVBoxLayout(result_group)

        # 结果信息栏
        self.result_info = QLabel("尚未执行查询")
        self.result_info.setStyleSheet("color: #666; padding: 4px;")
        result_layout.addWidget(self.result_info)

        # 结果表格
        self.result_table = QTableWidget()
        self.result_table.setAlternatingRowColors(True)
        self.result_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.result_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.result_table.customContextMenuRequested.connect(self._show_result_context_menu)
        result_layout.addWidget(self.result_table)

        # 快捷键
        self.sql_editor.keyPressEvent = self._sql_editor_key_press

        return widget

    def _create_ai_tab(self) -> QWidget:
        """AI 助手标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 自然语言查询
        nl_group = QGroupBox("自然语言 → SQL")
        nl_layout = QFormLayout(nl_group)

        self.nl_input = QLineEdit()
        self.nl_input.setPlaceholderText("用自然语言描述你想查询的内容，例如：查询最近一周的订单，按金额降序排列")
        nl_layout.addRow("查询描述:", self.nl_input)

        btn_row = QHBoxLayout()
        self.btn_nl_to_sql = QPushButton("🔄 生成 SQL")
        self.btn_nl_to_sql.clicked.connect(self._nl_to_sql)
        btn_row.addWidget(self.btn_nl_to_sql)

        self.btn_explain_sql = QPushButton("📖 解释 SQL")
        self.btn_explain_sql.clicked.connect(self._ai_explain_sql)
        btn_row.addWidget(self.btn_explain_sql)

        self.btn_analyze = QPushButton("📊 分析结果")
        self.btn_analyze.clicked.connect(self._ai_analyze_results)
        btn_row.addWidget(self.btn_analyze)

        btn_row.addStretch()
        nl_layout.addRow("", btn_row)

        layout.addWidget(nl_group)

        # AI 输出区
        output_group = QGroupBox("AI 输出")
        output_layout = QVBoxLayout(output_group)

        self.ai_output = QTextEdit()
        self.ai_output.setFont(QFont("Consolas", 10))
        self.ai_output.setReadOnly(True)
        self.ai_output.setPlaceholderText("AI 生成的内容将显示在这里...")
        output_layout.addWidget(self.ai_output)

        return widget

    def _create_table_tab(self) -> QWidget:
        """表结构标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 工具栏
        toolbar = QHBoxLayout()
        self.table_name_label = QLabel("未选择表")
        self.table_name_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        toolbar.addWidget(self.table_name_label)
        toolbar.addStretch()

        self.btn_ddl = QPushButton("📋 DDL 预览")
        self.btn_ddl.clicked.connect(self._show_ddl)
        toolbar.addWidget(self.btn_ddl)

        self.btn_copy_ddl = QPushButton("📋 复制 DDL")
        self.btn_copy_ddl.clicked.connect(self._copy_ddl)
        toolbar.addWidget(self.btn_copy_ddl)

        layout.addLayout(toolbar)

        # 表结构视图
        self.schema_table = QTableWidget()
        self.schema_table.setColumnCount(7)
        self.schema_table.setHorizontalHeaderLabels(["#", "字段名", "数据类型", "可空", "默认值", "键", "说明"])
        self.schema_table.setAlternatingRowColors(True)
        self.schema_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.schema_table)

        return widget

    def _create_history_tab(self) -> QWidget:
        """历史记录标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 工具栏
        toolbar = QHBoxLayout()
        self.history_search = QLineEdit()
        self.history_search.setPlaceholderText("搜索历史记录...")
        self.history_search.textChanged.connect(self._filter_history)
        toolbar.addWidget(self.history_search)

        btn_clear = QPushButton("清空历史")
        btn_clear.clicked.connect(self._clear_history)
        toolbar.addWidget(btn_clear)

        layout.addLayout(toolbar)

        # 历史列表
        self.history_list = QListWidget()
        self.history_list.itemDoubleClicked.connect(self._load_history_sql)
        layout.addWidget(self.history_list)

        return widget

    # ========== 数据刷新 ==========

    def _refresh_connections(self):
        """刷新连接列表"""
        self.conn_combo.blockSignals(True)
        self.conn_combo.clear()

        connections = self.browser.list_connections()
        for config in connections:
            status_icon = "🔴" if self.browser.conn_manager.is_connected(config.get_id()) else "⚪"
            self.conn_combo.addItem(f"{status_icon} {config.name} ({config.db_type.value})", config.get_id())

        # 设置当前活动连接
        active = self.browser.get_active_connection()
        if active:
            idx = self.conn_combo.findData(active.get_id())
            if idx >= 0:
                self.conn_combo.setCurrentIndex(idx)

        self.conn_combo.blockSignals(False)

    def _refresh_tree(self):
        """刷新数据库树"""
        self.db_tree.clear()

        active = self.browser.get_active_connection()
        if not active:
            # 显示保存的连接（未连接状态）
            for config in self.browser.list_connections():
                item = QTreeWidgetItem([f"⚪ {config.name} ({config.db_type.value})"])
                item.setData(0, Qt.ItemDataRole.UserRole, {"type": "connection", "id": config.get_id()})
                self.db_tree.addTopLevelItem(item)
            return

        # 构建数据库树
        try:
            nodes = self.browser.build_tree()
            for node in nodes:
                self._add_tree_node(None, node)
        except Exception as e:
            item = QTreeWidgetItem([f"❌ 加载失败: {e}"])
            self.db_tree.addTopLevelItem(item)

    def _add_tree_node(self, parent: Optional[QTreeWidgetItem], node):
        """添加树节点"""
        if parent:
            item = QTreeWidgetItem(parent, [node.name])
        else:
            item = QTreeWidgetItem(self.db_tree, [node.name])

        item.setData(0, Qt.ItemDataRole.UserRole, {
            "type": node.node_type,
            "id": node.id,
            "metadata": node.metadata
        })

        # 懒加载子节点
        if node.node_type == "folder":
            child_count = len(node.children)
            if child_count > 0:
                item.addChildren(self._build_lazy_placeholder(child_count))

        return item

    def _build_lazy_placeholder(self, count: int) -> List[QTreeWidgetItem]:
        """构建懒加载占位节点"""
        return [QTreeWidgetItem(["Loading..."]) for _ in range(count)]

    # ========== 事件处理 ==========

    def _on_connection_changed(self, index: int):
        """连接切换"""
        if index < 0:
            return
        conn_id = self.conn_combo.itemData(index)
        self.browser.set_active_connection(conn_id)
        self._refresh_tree()

    def _on_connect_clicked(self):
        """点击连接按钮"""
        index = self.conn_combo.currentIndex()
        if index < 0:
            return

        conn_id = self.conn_combo.itemData(index)
        self.browser.set_active_connection(conn_id)

        # 如果已断开，尝试连接
        if not self.browser.conn_manager.is_connected(conn_id):
            success, error = self.browser.connect(conn_id)
            if success:
                self._update_status(f"已连接: {self.browser.get_connection(conn_id).name}")
            else:
                QMessageBox.warning(self, "连接失败", f"无法连接到数据库:\n{error}")
                return

        self._refresh_connections()
        self._refresh_tree()

    def _on_disconnect_clicked(self):
        """断开连接"""
        index = self.conn_combo.currentIndex()
        if index < 0:
            return

        conn_id = self.conn_combo.itemData(index)
        self.browser.disconnect(conn_id)
        self._refresh_connections()
        self._refresh_tree()
        self._update_status("已断开连接")

    def _on_tree_item_clicked(self, item: QTreeWidgetItem, column: int):
        """树节点点击"""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        node_type = data.get("type", "")
        metadata = data.get("metadata", {})

        if node_type == "table":
            table_name = metadata.get("table_name", "")
            if table_name:
                self._current_table = table_name
                self._load_table_schema(table_name)
                # 双击执行 SELECT
                # self._execute_sql_for_table(table_name)

        elif node_type == "column":
            pass

    def _on_tree_item_expanded(self, item: QTreeWidgetItem):
        """树节点展开（懒加载）"""
        if item.childCount() > 0:
            first_child = item.child(0)
            if first_child and first_child.text(0) == "Loading...":
                # 加载真实子节点
                data = item.data(0, Qt.ItemDataRole.UserRole)
                item.takeChildren()
                # 触发加载
                conn_id = self.browser._active_connection_id
                if conn_id:
                    children = self.browser.schema_explorer.get_children(conn_id, data.get("id", ""))
                    for child in children:
                        self._add_tree_node(item, child)

    def _show_tree_context_menu(self, pos):
        """树右键菜单"""
        from PyQt6.QtWidgets import QMenu
        item = self.db_tree.itemAt(pos)
        if not item:
            return

        data = item.data(0, Qt.ItemDataRole.UserRole)
        menu = QMenu()

        if data.get("type") == "table":
            action_select = QAction("🔍 SELECT * FROM", self)
            action_select.triggered.connect(lambda: self._quick_select(data))
            menu.addAction(action_select)

            action_schema = QAction("📋 查看表结构", self)
            action_schema.triggered.connect(lambda: self._view_table_schema(data))
            menu.addAction(action_schema)

        elif data.get("type") == "connection":
            action_del = QAction("🗑️ 删除连接", self)
            action_del.triggered.connect(lambda: self._delete_connection(data))
            menu.addAction(action_del)

        menu.exec(self.db_tree.mapToGlobal(pos))

    # ========== SQL 执行 ==========

    def _sql_editor_key_press(self, event):
        """SQL 编辑器按键事件"""
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == 16777220:
            # Ctrl+Enter
            self._execute_sql()
        else:
            QTextEdit.keyPressEvent(self.sql_editor, event)

    def _execute_sql(self):
        """执行 SQL"""
        sql = self.sql_editor.toPlainText().strip()
        if not sql:
            return

        page = self.page_spin.value()
        page_size = self.page_size_spin.value()

        self._update_status("执行中...")
        self.result_table.setRowCount(0)
        self.result_info.setText("执行中...")

        # 后台执行
        threading.Thread(target=self._execute_sql_thread, args=(sql, page, page_size), daemon=True).start()

    def _execute_sql_thread(self, sql: str, page: int, page_size: int):
        """后台执行 SQL"""
        try:
            result = self.browser.execute(sql, page, page_size)
            self._current_result = result
            QTimer.singleShot(0, lambda: self._display_result(result, sql))
        except Exception as e:
            QTimer.singleShot(0, lambda: self._display_error(str(e)))

    def _display_result(self, result: QueryResult, sql: str):
        """显示查询结果"""
        if result.result_type == QueryResultType.ERROR:
            self._display_error(result.error_message)
            return

        self.result_info.setText(result.summary())
        self._update_status(result.summary())

        if result.result_type == QueryResultType.TABLE:
            self._populate_table(result)
        else:
            # 消息类型
            self.result_table.setRowCount(1)
            self.result_table.setColumnCount(1)
            self.result_table.setHorizontalHeaderLabels(["消息"])
            self.result_table.setItem(0, 0, QTableWidgetItem(result.ddl or "执行成功"))

    def _display_error(self, error: str):
        """显示错误"""
        self.result_info.setText(f"❌ {error}")
        self.result_table.setRowCount(1)
        self.result_table.setColumnCount(1)
        self.result_table.setHorizontalHeaderLabels(["错误"])
        self.result_table.setItem(0, 0, QTableWidgetItem(error))
        self._update_status(f"执行失败")

    def _populate_table(self, result: QueryResult):
        """填充结果表格"""
        if not result.columns:
            return

        self.result_table.blockSignals(True)
        self.result_table.setRowCount(min(result.row_count, result.page_size))
        self.result_table.setColumnCount(len(result.columns))
        self.result_table.setHorizontalHeaderLabels(result.columns)

        for row_idx, row in enumerate(result.rows):
            for col_idx, value in enumerate(row):
                item = QTableWidgetItem(str(value) if value is not None else "")
                self.result_table.setItem(row_idx, col_idx, item)

        self.result_table.blockSignals(False)
        self.result_table.resizeColumnsToContents()

    def _explain_sql(self):
        """执行计划"""
        sql = self.sql_editor.toPlainText().strip()
        if not sql:
            return

        self._update_status("获取执行计划...")
        threading.Thread(target=self._explain_thread, args=(sql,), daemon=True).start()

    def _explain_thread(self, sql: str):
        """后台获取执行计划"""
        try:
            result = self.browser.explain(sql)
            QTimer.singleShot(0, lambda: self._display_result(result, sql))
        except Exception as e:
            QTimer.singleShot(0, lambda: self._display_error(str(e)))

    def _export_csv(self):
        """导出 CSV"""
        if not self._current_result or self._current_result.result_type != QueryResultType.TABLE:
            QMessageBox.information(self, "提示", "当前没有可导出的表格数据")
            return

        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "导出 CSV", "", "CSV Files (*.csv)")
        if not path:
            return

        try:
            result = self._current_result
            with open(path, "w", encoding="utf-8-sig") as f:
                # 表头
                f.write(",".join(result.columns) + "\n")
                # 数据
                for row in result.rows:
                    f.write(",".join(f'"{str(v) if v is not None else ""}"' for v in row) + "\n")

            QMessageBox.information(self, "成功", f"已导出到:\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "导出失败", str(e))

    def _on_page_changed(self, page: int):
        """页码切换"""
        if self._current_result:
            self._execute_sql()

    def _on_page_size_changed(self, size: int):
        """每页数量变化"""
        self.page_spin.setValue(1)
        if self._current_result:
            self._execute_sql()

    def _format_sql(self):
        """格式化 SQL"""
        sql = self.sql_editor.toPlainText()
        if sql.strip():
            formatted = self.browser.format_sql(sql)
            self.sql_editor.setPlainText(formatted)

    # ========== AI 助手 ==========

    def _nl_to_sql(self):
        """自然语言转 SQL"""
        nl = self.nl_input.text().strip()
        if not nl:
            return

        self.ai_output.setPlainText("正在生成 SQL...")
        threading.Thread(target=self._nl_to_sql_thread, args=(nl,), daemon=True).start()

    def _nl_to_sql_thread(self, nl: str):
        """后台生成 SQL"""
        try:
            sql = self.browser.nl_to_sql(nl)
            QTimer.singleShot(0, lambda: self._set_ai_output(sql))
            # 自动填入编辑器
            QTimer.singleShot(0, lambda: self.sql_editor.setPlainText(sql))
        except Exception as e:
            QTimer.singleShot(0, lambda: self.ai_output.setPlainText(f"生成失败: {e}"))

    def _ai_explain_sql(self):
        """AI 解释 SQL"""
        sql = self.sql_editor.toPlainText().strip()
        if not sql:
            return

        self.ai_output.setPlainText("正在解释 SQL...")
        threading.Thread(target=self._explain_sql_thread, args=(sql,), daemon=True).start()

    def _explain_sql_thread(self, sql: str):
        """后台解释 SQL"""
        try:
            explanation = self.browser.explain_sql(sql)
            QTimer.singleShot(0, lambda: self.ai_output.setPlainText(explanation))
        except Exception as e:
            QTimer.singleShot(0, lambda: self.ai_output.setPlainText(f"解释失败: {e}"))

    def _ai_analyze_results(self):
        """AI 分析查询结果"""
        if not self._current_result or self._current_result.result_type != QueryResultType.TABLE:
            QMessageBox.information(self, "提示", "请先执行查询，再进行分析")
            return

        self.ai_output.setPlainText("正在分析数据...")
        threading.Thread(target=self._analyze_thread, daemon=True).start()

    def _analyze_thread(self):
        """后台分析"""
        try:
            result = self._current_result
            sql = self.sql_editor.toPlainText()
            question = self.nl_input.text()
            analysis = self.browser.analyze_results(
                sql, result.columns, result.rows, question
            )
            QTimer.singleShot(0, lambda: self.ai_output.setPlainText(analysis))
        except Exception as e:
            QTimer.singleShot(0, lambda: self.ai_output.setPlainText(f"分析失败: {e}"))

    def _set_ai_output(self, text: str):
        """设置 AI 输出"""
        self.ai_output.setPlainText(text)

    # ========== 表结构 ==========

    def _load_table_schema(self, table_name: str):
        """加载表结构"""
        self.table_name_label.setText(f"📋 {table_name}")
        threading.Thread(target=self._load_schema_thread, args=(table_name,), daemon=True).start()

    def _load_schema_thread(self, table_name: str):
        """后台加载表结构"""
        try:
            schema = self.browser.get_table_schema(table_name)
            QTimer.singleShot(0, lambda: self._display_schema(schema))
        except Exception as e:
            QTimer.singleShot(0, lambda: self.table_name_label.setText(f"加载失败: {e}"))

    def _display_schema(self, schema: Optional[TableSchema]):
        """显示表结构"""
        if not schema:
            return

        self.schema_table.blockSignals(True)
        self.schema_table.setRowCount(len(schema.columns))

        for row_idx, col in enumerate(schema.columns):
            self.schema_table.setItem(row_idx, 0, QTableWidgetItem(str(col.ordinal)))
            self.schema_table.setItem(row_idx, 1, QTableWidgetItem(col.name))
            self.schema_table.setItem(row_idx, 2, QTableWidgetItem(col.type_display()))
            self.schema_table.setItem(row_idx, 3, QTableWidgetItem("✓" if col.nullable else "✗"))
            self.schema_table.setItem(row_idx, 4, QTableWidgetItem(col.default_value or ""))
            keys = []
            if col.is_primary_key:
                keys.append("PK")
            if col.is_foreign_key:
                keys.append(f"FK→{col.foreign_table}")
            self.schema_table.setItem(row_idx, 5, QTableWidgetItem(",".join(keys)))
            self.schema_table.setItem(row_idx, 6, QTableWidgetItem(col.comment))

        self.schema_table.blockSignals(False)
        self.schema_table.resizeColumnsToContents()

    def _show_ddl(self):
        """显示 DDL"""
        if not self._current_table:
            return

        schema = self.browser.get_table_schema(self._current_table)
        if not schema:
            return

        config = self.browser.get_active_connection()
        db_type = config.db_type if config else DatabaseType.MYSQL

        ddl = self.browser.generate_ddl(self._current_table, schema.columns, db_type)
        self.ai_output.setPlainText(f"-- {self._current_table} DDL\n\n{ddl}")

    def _copy_ddl(self):
        """复制 DDL"""
        ddl = self.ai_output.toPlainText()
        if ddl:
            clipboard = QApplication.clipboard()
            clipboard.setText(ddl)
            self._update_status("DDL 已复制到剪贴板")

    # ========== 历史记录 ==========

    def _load_history(self):
        """加载历史记录"""
        self.history_list.clear()
        history = self.browser.get_history(limit=100)

        for item in history:
            icon = "❌" if item.is_error else "✅"
            time_str = item.timestamp_str()
            sql_preview = item.sql[:60].replace("\n", " ")
            list_item = QListWidgetItem(f"{icon} [{time_str}] {sql_preview}...")
            list_item.setData(Qt.ItemDataRole.UserRole, item.sql)
            self.history_list.addItem(list_item)

    def _load_history_sql(self, item: QListWidgetItem):
        """从历史加载 SQL"""
        sql = item.data(Qt.ItemDataRole.UserRole)
        if sql:
            self.sql_editor.setPlainText(sql)

    def _filter_history(self, text: str):
        """过滤历史"""
        for i in range(self.history_list.count()):
            item = self.history_list.item(i)
            item.setHidden(text not in item.text() if text else False)

    def _clear_history(self):
        """清空历史"""
        reply = QMessageBox.question(self, "确认", "确定清空所有历史记录？")
        if reply == QMessageBox.StandardButton.Yes:
            self.history_list.clear()
            self._update_status("历史记录已清空")

    # ========== 上下文菜单 ==========

    def _show_result_context_menu(self, pos):
        """结果表格右键菜单"""
        from PyQt6.QtWidgets import QMenu
        menu = QMenu()

        action_copy = QAction("📋 复制单元格", self)
        action_copy.triggered.connect(lambda: self._copy_cell())
        menu.addAction(action_copy)

        action_copy_row = QAction("📋 复制整行", self)
        action_copy_row.triggered.connect(lambda: self._copy_row())
        menu.addAction(action_copy_row)

        menu.exec(self.result_table.mapToGlobal(pos))

    def _copy_cell(self):
        """复制单元格"""
        item = self.result_table.currentItem()
        if item:
            clipboard = QApplication.clipboard()
            clipboard.setText(item.text())

    def _copy_row(self):
        """复制整行"""
        row = self.result_table.currentRow()
        if row >= 0:
            texts = []
            for col in range(self.result_table.columnCount()):
                item = self.result_table.item(row, col)
                texts.append(item.text() if item else "")
            clipboard = QApplication.clipboard()
            clipboard.setText("\t".join(texts))

    # ========== 快捷操作 ==========

    def _quick_select(self, data: dict):
        """快速 SELECT"""
        table = data.get("metadata", {}).get("table_name", "")
        if table:
            self.sql_editor.setPlainText(f"SELECT * FROM `{table}` LIMIT 100;")

    def _view_table_schema(self, data: dict):
        """查看表结构"""
        table = data.get("metadata", {}).get("table_name", "")
        if table:
            self._current_table = table
            self._load_table_schema(table)
            # 切换到表结构标签
            for i in range(self.right_panel.count()):
                if "表结构" in self.right_panel.tabText(i):
                    self.right_panel.setCurrentIndex(i)
                    break

    def _delete_connection(self, data: dict):
        """删除连接"""
        conn_id = data.get("id", "")
        reply = QMessageBox.question(self, "确认", "确定删除该连接？")
        if reply == QMessageBox.StandardButton.Yes:
            self.browser.remove_connection(conn_id)
            self._refresh_connections()
            self._refresh_tree()

    # ========== 连接管理对话框 ==========

    def _show_new_connection_dialog(self):
        """显示新建连接对话框"""
        dialog = ConnectionDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._refresh_connections()
            self._refresh_tree()

    # ========== 状态栏 ==========

    def _update_status(self, message: str):
        """更新状态栏"""
        self.status_bar.showMessage(message)

    def refresh(self):
        """刷新"""
        self._refresh_connections()
        self._refresh_tree()


class ConnectionDialog(QDialog):
    """新建连接对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("新建数据库连接")
        self.setMinimumWidth(500)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 连接名称
        form = QFormLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("例如: 开发环境 MySQL")
        form.addRow("连接名称:", self.name_input)

        # 数据库类型
        self.db_type_combo = QComboBox()
        for dt in DatabaseType:
            available = check_driver_available(dt)
            icon = "✅" if available else "❌"
            self.db_type_combo.addItem(f"{icon} {dt.value}", dt)
        self.db_type_combo.currentIndexChanged.connect(self._on_db_type_changed)
        form.addRow("数据库类型:", self.db_type_combo)

        # 主机
        self.host_input = QLineEdit("localhost")
        form.addRow("主机:", self.host_input)

        # 端口
        self.port_input = QSpinBox()
        self.port_input.setMinimum(1)
        self.port_input.setMaximum(65535)
        self.port_input.setValue(3306)
        form.addRow("端口:", self.port_input)

        # 用户名
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("root")
        form.addRow("用户名:", self.user_input)

        # 密码
        self.pass_input = QLineEdit()
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("密码:", self.pass_input)

        # 数据库名
        self.db_input = QLineEdit()
        form.addRow("数据库名:", self.db_input)

        # SQLite 文件路径
        self.file_path_input = QLineEdit()
        self.file_path_input.setPlaceholderText("C:\\data\\mydb.sqlite")
        form.addRow("SQLite 路径:", self.file_path_input)
        self.file_path_input.hide()
        self.db_input_label = form.labelForField(self.db_input)

        layout.addLayout(form)

        # 按钮
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_db_type_changed(self, index: int):
        """切换数据库类型"""
        dt = self.db_type_combo.itemData(index)
        if dt == DatabaseType.SQLITE:
            self.host_input.hide()
            self.port_input.hide()
            self.user_input.hide()
            self.pass_input.hide()
            self.db_input.hide()
            self.file_path_input.show()
        else:
            self.host_input.show()
            self.port_input.show()
            self.user_input.show()
            self.pass_input.show()
            self.db_input.show()
            self.file_path_input.hide()

            default_port = DEFAULT_PORTS.get(dt, 0)
            self.port_input.setValue(default_port)

    def _on_ok(self):
        """确认"""
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入连接名称")
            return

        dt = self.db_type_combo.itemData(self.db_type_combo.currentIndex())

        config = ConnectionConfig()
        config.name = name
        config.db_type = dt
        config.host = self.host_input.text().strip()
        config.port = self.port_input.value()
        config.username = self.user_input.text().strip()
        config.password = self.pass_input.text()
        config.database = self.db_input.text().strip()
        config.file_path = self.file_path_input.text().strip()

        browser = get_database_browser()
        success, msg = browser.add_connection(config)

        if success:
            self.accept()
        else:
            QMessageBox.warning(self, "连接失败", msg)


from PyQt6.QtWidgets import QApplication, QAbstractItemView
from core.database_browser.models import check_driver_available
