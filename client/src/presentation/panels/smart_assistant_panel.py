"""
智能客户端AI助手 PyQt6 UI面板

提供可视化界面让用户使用智能助手功能
"""

import sys
from typing import Optional, List, Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTextEdit, QLineEdit, QPushButton, QLabel,
    QComboBox, QListWidget, QListWidgetItem,
    QGroupBox, QFrame, QScrollArea, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QStatusBar, QToolButton, QMenu, QProgressBar,
    QCheckBox, QSpinBox, QSlider, QDialog,
    QDialogButtonBox, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont, QTextCursor, QColor, QPalette, QAction


class SmartAssistantPanel(QWidget):
    """
    智能客户端AI助手面板
    
    提供聊天、导航、指引等功能
    """
    
    # 信号定义
    navigate_requested = pyqtSignal(str, dict)  # page_id, params
    guide_started = pyqtSignal(str)  # guide_id
    guide_action = pyqtSignal(str)  # action: next, skip, abort
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.assistant = None
        self.current_guide_id = None
        self._init_ui()
        self._init_assistant()
    
    def _init_ui(self):
        """初始化UI"""
        # 主布局
        main_layout = QVBoxLayout(self)
        
        # 创建标签页
        tab_widget = QTabWidget()
        tab_widget.addTab(self._create_chat_tab(), "💬 智能助手")
        tab_widget.addTab(self._create_guide_tab(), "🎯 指引系统")
        tab_widget.addTab(self._create_knowledge_tab(), "📚 知识库")
        tab_widget.addTab(self._create_stats_tab(), "📊 统计信息")
        
        main_layout.addWidget(tab_widget)
        
        # 状态栏
        self.status_bar = QStatusBar()
        main_layout.addWidget(self.status_bar)
        self.status_bar.showMessage("就绪")
    
    def _init_assistant(self):
        """初始化助手"""
        try:
            from core.smart_assistant import get_smart_assistant
            self.assistant = get_smart_assistant()
            
            # 注册导航回调
            self.assistant.navigation_callback = self._on_navigate
            self.assistant.guide_callback = self._on_guide_event
            
            self.status_bar.showMessage("助手已就绪")
        except Exception as e:
            self.status_bar.showMessage(f"助手初始化失败: {e}")
    
    def _create_chat_tab(self) -> QWidget:
        """创建聊天标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 标题
        title = QLabel("🤖 智能客户端助手")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # 说明
        intro = QLabel(
            "我是您的软件导航助手，可以帮您：\n"
            "• 了解功能模块  • 指导操作步骤  • 导航到指定页面\n"
            "• 配置系统选项  • 排查常见问题"
        )
        intro.setStyleSheet("color: gray; padding: 5px;")
        layout.addWidget(intro)
        
        # 快捷操作区
        quick_group = QGroupBox("快捷操作")
        quick_layout = QHBoxLayout()
        
        quick_buttons = [
            ("📖 功能介绍", "帮我介绍各个功能模块"),
            ("⚙️ 配置模型", "如何配置AI模型"),
            ("🔌 安装MCP", "如何安装MCP服务器"),
            ("🔧 常见问题", "解决常见问题"),
        ]
        
        for icon_text, query in quick_buttons:
            btn = QPushButton(icon_text)
            btn.clicked.connect(lambda checked, q=query: self._on_quick_action(q))
            quick_layout.addWidget(btn)
        
        quick_group.setLayout(quick_layout)
        layout.addWidget(quick_group)
        
        # 对话区域
        chat_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # 对话显示区
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("""
            QTextEdit {
                background-color: #fafafa;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 10px;
            }
        """)
        chat_splitter.addWidget(self.chat_display)
        
        # 指引显示区
        self.guide_display = QFrame()
        self.guide_display.setVisible(False)
        guide_layout = QVBoxLayout(self.guide_display)
        
        # 指引标题
        guide_title_layout = QHBoxLayout()
        self.guide_title = QLabel("🎯 当前指引")
        self.guide_title.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        guide_title_layout.addWidget(self.guide_title)
        guide_title_layout.addStretch()
        
        self.guide_abort_btn = QPushButton("结束指引")
        self.guide_abort_btn.clicked.connect(self._on_abort_guide)
        guide_title_layout.addWidget(self.guide_abort_btn)
        guide_layout.addLayout(guide_title_layout)
        
        # 指引进度
        self.guide_progress = QProgressBar()
        self.guide_progress.setTextVisible(True)
        guide_layout.addWidget(self.guide_progress)
        
        # 当前步骤
        self.current_step_label = QLabel()
        self.current_step_label.setWordWrap(True)
        self.current_step_label.setStyleSheet("padding: 10px; background: #e3f2fd; border-radius: 5px;")
        guide_layout.addWidget(self.current_step_label)
        
        # 指引按钮
        guide_btn_layout = QHBoxLayout()
        self.guide_skip_btn = QPushButton("跳过此步")
        self.guide_skip_btn.clicked.connect(self._on_guide_skip)
        guide_btn_layout.addWidget(self.guide_skip_btn)
        
        self.guide_next_btn = QPushButton("下一步 ✓")
        self.guide_next_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
        """)
        self.guide_next_btn.clicked.connect(self._on_guide_next)
        guide_btn_layout.addWidget(self.guide_next_btn)
        guide_layout.addLayout(guide_btn_layout)
        
        chat_splitter.addWidget(self.guide_display)
        chat_splitter.setSizes([400, 150])
        
        layout.addWidget(chat_splitter, 1)  # stretch=1
        
        # 输入区域
        input_group = QGroupBox("输入您的问题")
        input_layout = QVBoxLayout()
        
        # 输入框
        self.chat_input = QTextEdit()
        self.chat_input.setPlaceholderText(
            "请输入您的问题...\n\n"
            "示例:\n"
            "• 如何配置AI模型？\n"
            "• MCP服务器怎么安装？\n"
            "• 首页在哪里？\n"
            "• 帮我打开设置页面"
        )
        self.chat_input.setMaximumHeight(100)
        input_layout.addWidget(self.chat_input)
        
        # 发送按钮
        btn_layout = QHBoxLayout()
        self.send_btn = QPushButton("🚀 发送")
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        self.send_btn.clicked.connect(self._on_send)
        btn_layout.addWidget(self.send_btn)
        
        self.clear_btn = QPushButton("清空")
        self.clear_btn.clicked.connect(self._on_clear)
        btn_layout.addWidget(self.clear_btn)
        
        btn_layout.addStretch()
        input_layout.addLayout(btn_layout)
        
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)
        
        return widget
    
    def _create_guide_tab(self) -> QWidget:
        """创建指引标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 标题
        title = QLabel("🎯 交互式指引")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # 指引列表
        self.guide_list = QListWidget()
        self.guide_list.itemClicked.connect(self._on_guide_select)
        layout.addWidget(self.guide_list, 1)
        
        # 指引详情
        detail_group = QGroupBox("指引详情")
        detail_layout = QVBoxLayout()
        
        self.guide_detail = QTextEdit()
        self.guide_detail.setReadOnly(True)
        detail_layout.addWidget(self.guide_detail)
        
        # 开始按钮
        self.start_guide_btn = QPushButton("🚀 开始指引")
        self.start_guide_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 10px;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
        """)
        self.start_guide_btn.clicked.connect(self._on_start_guide_from_list)
        self.start_guide_btn.setEnabled(False)
        detail_layout.addWidget(self.start_guide_btn)
        
        detail_group.setLayout(detail_layout)
        layout.addWidget(detail_group)
        
        # 加载指引列表
        self._load_guide_list()
        
        return widget
    
    def _create_knowledge_tab(self) -> QWidget:
        """创建知识库标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 标题
        title = QLabel("📚 应用知识库")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # 知识库统计
        stats_group = QGroupBox("知识库统计")
        stats_layout = QVBoxLayout()
        
        self.kb_stats_label = QLabel()
        stats_layout.addWidget(self.kb_stats_label)
        
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        # 页面列表
        pages_group = QGroupBox("注册页面")
        pages_layout = QVBoxLayout()
        
        self.page_list = QListWidget()
        pages_layout.addWidget(self.page_list)
        
        pages_group.setLayout(pages_layout)
        layout.addWidget(pages_group, 1)
        
        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新知识库")
        refresh_btn.clicked.connect(self._refresh_knowledge)
        layout.addWidget(refresh_btn)
        
        # 初始加载
        self._refresh_knowledge()
        
        return widget
    
    def _create_stats_tab(self) -> QWidget:
        """创建统计标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 标题
        title = QLabel("📊 系统统计")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # 统计表格
        self.stats_table = QTableWidget(6, 2)
        self.stats_table.setHorizontalHeaderLabels(["统计项", "数值"])
        self.stats_table.horizontalHeader().setStretchLastSection(True)
        self.stats_table.verticalHeader().setVisible(False)
        
        layout.addWidget(self.stats_table, 1)
        
        # 诊断按钮
        diag_group = QGroupBox("系统诊断")
        diag_layout = QVBoxLayout()
        
        diag_btn = QPushButton("🔍 运行诊断")
        diag_btn.clicked.connect(self._run_diagnosis)
        diag_layout.addWidget(diag_btn)
        
        self.diag_result = QTextEdit()
        self.diag_result.setReadOnly(True)
        self.diag_result.setMaximumHeight(150)
        diag_layout.addWidget(self.diag_result)
        
        diag_group.setLayout(diag_layout)
        layout.addWidget(diag_group)
        
        # 初始加载
        self._refresh_stats()
        
        return widget
    
    # ==================== 事件处理 ====================
    
    def _on_send(self):
        """发送消息"""
        message = self.chat_input.toPlainText().strip()
        if not message:
            return
        
        # 显示用户消息
        self._add_message("user", message)
        self.chat_input.clear()
        
        # 处理消息
        try:
            response = self.assistant.chat(message)
            
            # 显示助手响应
            self._add_message("assistant", response.text)
            
            # 如果有导航结果
            if response.navigation.success:
                self._show_navigation_suggestion(response.navigation)
            
            # 如果有指引
            if response.show_guide and response.guide_steps:
                self._start_guide_display(response.guide_steps)
            
            # 显示置信度
            if response.confidence > 0:
                self.status_bar.showMessage(f"意图识别置信度: {response.confidence:.0%}")
            
        except Exception as e:
            self._add_message("assistant", f"抱歉，发生了错误: {str(e)}")
    
    def _on_quick_action(self, query: str):
        """快捷操作"""
        self.chat_input.setPlainText(query)
        self._on_send()
    
    def _on_clear(self):
        """清空对话"""
        self.chat_display.clear()
        self.guide_display.setVisible(False)
    
    def _on_guide_next(self):
        """下一步"""
        if self.assistant and self.assistant.is_guide_running():
            next_step = self.assistant.guide_next_step(success=True)
            if next_step:
                self._update_guide_step(next_step)
            else:
                self._on_guide_complete()
    
    def _on_guide_skip(self):
        """跳过步骤"""
        if self.assistant and self.assistant.is_guide_running():
            next_step = self.assistant.guide_skip()
            if next_step:
                self._update_guide_step(next_step)
            else:
                self._on_guide_complete()
    
    def _on_abort_guide(self):
        """中止指引"""
        if self.assistant:
            self.assistant.guide_abort()
        self.guide_display.setVisible(False)
        self._add_message("assistant", "指引已结束。有什么其他问题吗？")
    
    def _on_guide_complete(self):
        """指引完成"""
        self.guide_display.setVisible(False)
        self._add_message("assistant", "🎉 恭喜！您已完成本指引。有什么其他需要帮助的吗？")
    
    def _on_guide_select(self, item: QListWidgetItem):
        """选择指引"""
        guide_id = item.data(Qt.ItemDataRole.UserRole)
        self.current_guide_id = guide_id
        self.start_guide_btn.setEnabled(True)
        
        # 显示指引详情
        if self.assistant:
            from core.smart_assistant import get_guide_system
            guide_system = get_guide_system()
            guides = self.assistant.kg.find_guide(tags=[guide_id])
            if guides:
                detail = guide_system.render_full_guide(guides[0])
                self.guide_detail.setPlainText(detail)
    
    def _on_start_guide_from_list(self):
        """从列表开始指引"""
        if self.current_guide_id and self.assistant:
            self.assistant.start_guide(self.current_guide_id)
            self._add_message("assistant", f"正在启动指引...")
            
            # 切换到聊天标签页并显示指引
            self._show_guide_in_chat()
    
    # ==================== UI更新 ====================
    
    def _add_message(self, role: str, content: str):
        """添加消息到聊天显示"""
        if role == "user":
            html = f"""
            <div style="background: #E3F2FD; padding: 10px; border-radius: 10px; margin: 5px 0; text-align: right;">
                <b>您:</b><br>{content.replace(chr(10), '<br>')}
            </div>
            """
        else:
            html = f"""
            <div style="background: #F5F5F5; padding: 10px; border-radius: 10px; margin: 5px 0;">
                <b>助手:</b><br>{content.replace(chr(10), '<br>')}
            </div>
            """
        
        self.chat_display.append(html)
        self.chat_display.moveCursor(QTextCursor.MoveOperation.End)
    
    def _show_navigation_suggestion(self, navigation):
        """显示导航建议"""
        if navigation.target_page:
            page = self.assistant.kg.get_page_by_id(navigation.target_page)
            if page:
                self._add_message("assistant", 
                    f"📍 我可以导航您到「{page.title}」页面。\n"
                    f"路由: {navigation.route_url or page.path}\n\n"
                    f"[点击这里前往](请使用下方按钮导航)"
                )
    
    def _start_guide_display(self, steps: List[str]):
        """在聊天区显示指引"""
        self.guide_display.setVisible(True)
        
        if steps:
            # 显示第一步
            self.current_step_label.setText(steps[0])
            self.guide_progress.setValue(int(100 / len(steps)))
    
    def _update_guide_step(self, step_text: str):
        """更新当前步骤"""
        self.current_step_label.setText(step_text)
        
        # 更新进度
        progress = self.assistant.get_guide_progress()
        self.guide_progress.setValue(int(progress["completion_rate"] * 100))
    
    def _show_guide_in_chat(self):
        """在聊天区显示指引"""
        if self.assistant and self.assistant.is_guide_running():
            progress = self.assistant.get_guide_progress()
            self._add_message("assistant", f"🎯 正在执行指引: {progress['guide_name']}")
    
    def _load_guide_list(self):
        """加载指引列表"""
        self.guide_list.clear()
        
        if self.assistant:
            guides = self.assistant.kg.get_all_guides()
            for guide in guides:
                item = QListWidgetItem(f"📖 {guide.name}")
                item.setData(Qt.ItemDataRole.UserRole, guide.guide_id)
                self.guide_list.addItem(item)
    
    def _refresh_knowledge(self):
        """刷新知识库"""
        if self.assistant:
            stats = self.assistant.kg.get_stats()
            
            # 更新统计
            self.kb_stats_label.setText(
                f"页面数: {stats.get('total_pages', 0)} | "
                f"组件数: {stats.get('total_components', 0)} | "
                f"操作路径: {stats.get('total_paths', 0)} | "
                f"路由数: {stats.get('total_routes', 0)} | "
                f"指引数: {stats.get('total_guides', 0)}"
            )
            
            # 更新页面列表
            self.page_list.clear()
            pages = self.assistant.kg.get_all_pages()
            for page in pages:
                self.page_list.addItem(f"📄 {page.title} ({page.path})")
    
    def _refresh_stats(self):
        """刷新统计"""
        if self.assistant:
            stats = self.assistant.get_stats()
            
            # 更新表格
            kb_stats = stats.get("knowledge_base", {})
            guide_stats = stats.get("guide_system", {})
            
            data = [
                ("知识库页面数", str(kb_stats.get("total_pages", 0))),
                ("知识库组件数", str(kb_stats.get("total_components", 0))),
                ("指引总数", str(guide_stats.get("total_guides", 0))),
                ("完成指引数", str(guide_stats.get("completed", 0))),
                ("中止指引数", str(guide_stats.get("aborted", 0))),
                ("平均完成率", f"{guide_stats.get('avg_completion_rate', 0):.0%}"),
            ]
            
            for i, (name, value) in enumerate(data):
                self.stats_table.setItem(i, 0, QTableWidgetItem(name))
                self.stats_table.setItem(i, 1, QTableWidgetItem(value))
    
    def _run_diagnosis(self):
        """运行诊断"""
        if self.assistant:
            diag = self.assistant.diagnose()
            
            result = f"系统状态: {diag['status']}\n\n"
            result += "知识图谱:\n"
            for key, value in diag["knowledge_graph"].items():
                result += f"  • {key}: {value}\n"
            result += f"\n指引运行中: {'是' if diag['guide_running'] else '否'}\n"
            result += f"上下文激活: {'是' if diag['context_active'] else '否'}"
            
            self.diag_result.setPlainText(result)
    
    # ==================== 回调处理 ====================
    
    def _on_navigate(self, page_id: str, **kwargs):
        """导航回调"""
        self.navigate_requested.emit(page_id, kwargs)
        self._add_message("assistant", f"正在导航到「{page_id}」...")
    
    def _on_guide_event(self, event: str, **kwargs):
        """指引事件回调"""
        if event == "step_complete":
            self._update_guide_step(kwargs.get("step_text", ""))
        elif event == "guide_complete":
            self._on_guide_complete()


# 便捷函数
def show_assistant_panel(main_window):
    """在主窗口显示助手面板"""
    from PyQt6.QtWidgets import QTabWidget
    
    # 查找或创建标签页
    tab_widget = main_window.findChild(QTabWidget)
    if tab_widget:
        # 检查是否已有助手标签
        for i in range(tab_widget.count()):
            if "助手" in tab_widget.tabText(i):
                tab_widget.setCurrentIndex(i)
                return
        
        # 添加新标签
        panel = SmartAssistantPanel()
        tab_widget.addTab(panel, "🤖 助手")
        tab_widget.setCurrentWidget(panel)
