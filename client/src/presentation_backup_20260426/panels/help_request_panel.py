"""
Help Request Panel - 求助面板UI

提供可视化界面：
1. 问题输入区
2. 脱敏预览区
3. 平台选择区
4. 帖子预览区
5. 监控状态区
6. 答案展示区
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit,
    QLabel, QComboBox, QCheckBox, QProgressBar, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox,
    QFormLayout, QLineEdit, QSpinBox, QDoubleSpinBox,
    QListWidget, QListWidgetItem, QTextBrowser, QSplitter,
    QFrame, QStatusBar, QProgressDialog, QMessageBox,
    QDialog, QDialogButtonBox, QApplication
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QTimer
from PyQt6.QtGui import QFont, QTextCharFormat, QColor, QTextCursor

import sys
import threading
from typing import Optional, Dict, Any
from datetime import datetime

# 导入核心模块
try:
    from client.src.business.smart_help_system import (
        SmartHelpController, HelpRequest, HelpStatus,
        QuestionSanitizer, PlatformSelector, Platform
    )
    MODULE_AVAILABLE = True
except ImportError:
    MODULE_AVAILABLE = False


class HelpRequestPanel(QWidget):
    """
    智能求助面板

    提供完整的求助流程界面
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.controller: Optional[SmartHelpController] = None
        self.current_request: Optional[HelpRequest] = None
        self._init_ui()
        self._init_controller()

    def _init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)

        # 标题
        title_label = QLabel("🌐 智能求助系统")
        title_label.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        main_layout.addWidget(title_label)

        # 创建分标签页面
        self.tabs = QTabWidget()

        # Tab 1: 问题输入
        self.tabs.addTab(self._create_input_tab(), "📝 问题输入")

        # Tab 2: 预览与发布
        self.tabs.addTab(self._create_preview_tab(), "👁️ 预览发布")

        # Tab 3: 监控状态
        self.tabs.addTab(self._create_monitor_tab(), "📡 监控状态")

        # Tab 4: 答案结果
        self.tabs.addTab(self._create_answers_tab(), "💡 答案结果")

        main_layout.addWidget(self.tabs)

        # 状态栏
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("就绪")
        main_layout.addWidget(self.status_bar)

        self.setLayout(main_layout)

    def _create_input_tab(self) -> QWidget:
        """创建问题输入标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 问题输入区
        input_group = QGroupBox("问题描述")
        input_layout = QVBoxLayout()

        self.question_input = QTextEdit()
        self.question_input.setPlaceholderText(
            "请输入您的问题...\n"
            "例如：Python连接MongoDB超时怎么解决？\n"
            "支持包含错误信息、代码片段、环境描述等"
        )
        self.question_input.setMinimumHeight(150)
        input_layout.addWidget(self.question_input)

        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # 上下文信息区
        context_group = QGroupBox("上下文信息（可选）")
        context_layout = QFormLayout()

        self.error_input = QLineEdit()
        self.error_input.setPlaceholderText("错误信息（如果有）")
        context_layout.addRow("错误信息:", self.error_input)

        self.os_input = QLineEdit()
        self.os_input.setText("Windows 11")
        context_layout.addRow("操作系统:", self.os_input)

        self.language_input = QLineEdit()
        self.language_input.setText("Python 3.11")
        context_layout.addRow("编程语言:", self.language_input)

        self.framework_input = QLineEdit()
        self.framework_input.setPlaceholderText("框架/库（可选）")
        context_layout.addRow("框架:", self.framework_input)

        self.code_input = QTextEdit()
        self.code_input.setPlaceholderText("相关代码（可选）")
        self.code_input.setMaximumHeight(100)
        context_layout.addRow("代码:", self.code_input)

        context_group.setLayout(context_layout)
        layout.addWidget(context_group)

        # 按钮区
        button_layout = QHBoxLayout()

        self.analyze_btn = QPushButton("🔍 分析问题")
        self.analyze_btn.clicked.connect(self._on_analyze)
        button_layout.addWidget(self.analyze_btn)

        self.preview_btn = QPushButton("👁️ 预览帖子")
        self.preview_btn.clicked.connect(self._on_preview)
        self.preview_btn.setEnabled(False)
        button_layout.addWidget(self.preview_btn)

        self.submit_btn = QPushButton("🚀 一键求助")
        self.submit_btn.clicked.connect(self._on_submit)
        self.submit_btn.setEnabled(False)
        self.submit_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
            }
        """)
        button_layout.addWidget(self.submit_btn)

        layout.addLayout(button_layout)

        # 脱敏预览区
        sanitize_group = QGroupBox("脱敏预览")
        sanitize_layout = QVBoxLayout()

        self.sanitize_preview = QTextBrowser()
        self.sanitize_preview.setMaximumHeight(120)
        sanitize_layout.addWidget(self.sanitize_preview)

        sanitize_group.setLayout(sanitize_layout)
        layout.addWidget(sanitize_group)

        layout.addStretch()

        return widget

    def _create_preview_tab(self) -> QWidget:
        """创建预览发布标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 平台选择区
        platform_group = QGroupBox("选择发布平台")
        platform_layout = QHBoxLayout()

        self.platform_combo = QComboBox()
        self.platform_combo.addItems([
            "自动选择（推荐）",
            "Stack Overflow",
            "知乎",
            "GitHub Issues",
            "CSDN",
            "博客园",
            "V2EX",
        ])
        platform_layout.addWidget(QLabel("目标平台:"))
        platform_layout.addWidget(self.platform_combo)
        platform_layout.addStretch()

        platform_group.setLayout(platform_layout)
        layout.addWidget(platform_group)

        # 帖子预览区
        post_group = QGroupBox("帖子预览")
        post_layout = QVBoxLayout()

        self.post_title = QLabel("(标题将在这里显示)")
        self.post_title.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        post_layout.addWidget(self.post_title)

        self.post_body = QTextBrowser()
        self.post_body.setMinimumHeight(300)
        post_layout.addWidget(self.post_body)

        post_group.setLayout(post_layout)
        layout.addWidget(post_group)

        # 发布按钮
        button_layout = QHBoxLayout()

        self.publish_btn = QPushButton("📤 发布帖子")
        self.publish_btn.clicked.connect(self._on_publish)
        self.publish_btn.setEnabled(False)
        button_layout.addWidget(self.publish_btn)

        self.refresh_btn = QPushButton("🔄 刷新答案")
        self.refresh_btn.clicked.connect(self._on_refresh_answers)
        self.refresh_btn.setEnabled(False)
        button_layout.addWidget(self.refresh_btn)

        button_layout.addStretch()

        layout.addLayout(button_layout)

        return widget

    def _create_monitor_tab(self) -> QWidget:
        """创建监控状态标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 监控概览
        overview_group = QGroupBox("监控概览")
        overview_layout = QFormLayout()

        self.monitor_status = QLabel("空闲")
        overview_layout.addRow("状态:", self.monitor_status)

        self.monitor_posts_count = QLabel("0")
        overview_layout.addRow("监控帖子数:", self.monitor_posts_count)

        self.monitor_answers_count = QLabel("0")
        overview_layout.addRow("收到回答:", self.monitor_answers_count)

        overview_group.setLayout(overview_layout)
        layout.addWidget(overview_group)

        # 帖子列表
        posts_group = QGroupBox("监控中的帖子")
        posts_layout = QVBoxLayout()

        self.posts_table = QTableWidget()
        self.posts_table.setColumnCount(5)
        self.posts_table.setHorizontalHeaderLabels([
            "平台", "标题", "状态", "回答数", "链接"
        ])
        self.posts_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.posts_table.setMaximumHeight(200)
        posts_layout.addWidget(self.posts_table)

        posts_group.setLayout(posts_layout)
        layout.addWidget(posts_group)

        # 实时日志
        log_group = QGroupBox("实时日志")
        log_layout = QVBoxLayout()

        self.log_output = QTextBrowser()
        self.log_output.setMaximumHeight(150)
        log_layout.addWidget(self.log_output)

        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        # 按钮
        button_layout = QHBoxLayout()

        self.stop_monitor_btn = QPushButton("⏹️ 停止监控")
        self.stop_monitor_btn.clicked.connect(self._on_stop_monitor)
        self.stop_monitor_btn.setEnabled(False)
        button_layout.addWidget(self.stop_monitor_btn)

        button_layout.addStretch()

        layout.addLayout(button_layout)

        return widget

    def _create_answers_tab(self) -> QWidget:
        """创建答案结果标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 答案概览
        overview_group = QGroupBox("答案概览")
        overview_layout = QFormLayout()

        self.answer_confidence = QLabel("0%")
        overview_layout.addRow("置信度:", self.answer_confidence)

        self.answer_sources = QLabel("0个来源")
        overview_layout.addRow("来源数量:", self.answer_sources)

        overview_group.setLayout(overview_layout)
        layout.addWidget(overview_group)

        # 整合答案
        answer_group = QGroupBox("整合答案")
        answer_layout = QVBoxLayout()

        self.aggregated_answer = QTextBrowser()
        self.aggregated_answer.setMinimumHeight(250)
        answer_layout.addWidget(self.aggregated_answer)

        answer_group.setLayout(answer_layout)
        layout.addWidget(answer_group)

        # 关键点
        keypoints_group = QGroupBox("关键要点")
        keypoints_layout = QVBoxLayout()

        self.keypoints_list = QListWidget()
        keypoints_layout.addWidget(self.keypoints_list)

        keypoints_group.setLayout(keypoints_layout)
        layout.addWidget(keypoints_group)

        # 按钮
        button_layout = QHBoxLayout()

        self.copy_answer_btn = QPushButton("📋 复制答案")
        self.copy_answer_btn.clicked.connect(self._on_copy_answer)
        self.copy_answer_btn.setEnabled(False)
        button_layout.addWidget(self.copy_answer_btn)

        self.export_answer_btn = QPushButton("💾 导出报告")
        self.export_answer_btn.clicked.connect(self._on_export_answer)
        self.export_answer_btn.setEnabled(False)
        button_layout.addWidget(self.export_answer_btn)

        button_layout.addStretch()

        layout.addLayout(button_layout)

        return widget

    def _init_controller(self):
        """初始化控制器"""
        if MODULE_AVAILABLE:
            self.controller = SmartHelpController()
            self.controller.register_status_callback(self._on_status_changed)
            self.controller.register_answer_callback(self._on_new_answer_received)

    @pyqtSlot()
    def _on_analyze(self):
        """分析问题"""
        if not MODULE_AVAILABLE:
            self._show_error("模块未正确加载")
            return

        question = self.question_input.toPlainText().strip()
        if not question:
            self._show_error("请输入问题")
            return

        # 获取上下文
        context = {
            'error_message': self.error_input.text(),
            'os': self.os_input.text(),
            'language': self.language_input.text(),
            'framework': self.framework_input.text(),
            'code': self.code_input.toPlainText(),
        }

        # 创建请求
        self.current_request = self.controller.create_help_request(question, context)

        # 脱敏预览
        sanitizer = QuestionSanitizer()
        sanitized = sanitizer.sanitize(question)

        # 显示脱敏预览
        preview_lines = [
            "=== 脱敏预览 ===",
            "",
            f"隐私等级: {sanitized.privacy_level.upper()}",
            "",
            "脱敏后的问题:",
            sanitized.sanitized,
            "",
            "检测到的敏感信息:",
        ]

        if sanitized.substitutions:
            for placeholder, category in sanitized.substitutions.items():
                preview_lines.append(f"  • {placeholder} -> {category}")
        else:
            preview_lines.append("  (无)")

        if sanitized.generalization_suggestions:
            preview_lines.append("")
            preview_lines.append("泛化建议:")
            for suggestion in sanitized.generalization_suggestions:
                preview_lines.append(f"  • {suggestion}")

        self.sanitize_preview.setPlainText("\n".join(preview_lines))

        # 平台选择预览
        selector = PlatformSelector()
        selection = selector.select(question, context.get('language', 'auto'))

        platform_info = selector.get_platform_info(selection.primary_platform)

        preview_lines = [
            "=== 平台推荐 ===",
            "",
            f"问题类型: {selection.question_type.value}",
            f"推荐平台: {platform_info.name if platform_info else selection.primary_platform.value}",
            f"置信度: {selection.confidence:.0%}",
            "",
            f"推理: {selection.reasoning}",
            "",
            "建议标签:",
            ", ".join(selection.suggested_tags) if selection.suggested_tags else "(无)",
            "",
            "备选平台:",
        ]

        for alt in selection.alternative_platforms:
            alt_info = selector.get_platform_info(alt)
            if alt_info:
                preview_lines.append(f"  • {alt_info.name}")

        self._log(f"分析完成: {selection.primary_platform.value}")

        # 启用按钮
        self.preview_btn.setEnabled(True)
        self.submit_btn.setEnabled(True)

        self.status_bar.showMessage("分析完成，可以预览或直接提交")

    @pyqtSlot()
    def _on_preview(self):
        """预览帖子"""
        if not self.current_request or not MODULE_AVAILABLE:
            return

        # 生成帖子预览
        post = self.controller.preview_post(
            question=self.current_request.original_question,
            platform=self.current_request.platform_selection.primary_platform,
            context=self.current_request.context
        )

        if post:
            self.post_title.setText(post.title)
            self.post_body.setPlainText(post.body)
            self._log(f"生成预览: {post.platform.value}")
            self.tabs.setCurrentIndex(1)  # 切换到预览标签

    @pyqtSlot()
    def _on_submit(self):
        """一键提交"""
        if not MODULE_AVAILABLE or not self.current_request:
            return

        self._log("开始执行求助流程...")
        self.analyze_btn.setEnabled(False)
        self.preview_btn.setEnabled(False)
        self.submit_btn.setEnabled(False)

        # 显示进度对话框
        self.progress = QProgressDialog("正在处理...", "取消", 0, 100, self)
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.show()

        # 后台执行
        def execute():
            try:
                # 执行请求
                self.current_request = self.controller.execute_help_request(
                    self.current_request,
                    auto_publish=True
                )

                # 更新UI
                QTimer.singleShot(0, lambda: self._on_execution_complete())

            except Exception as e:
                QTimer.singleShot(0, lambda: self._show_error(str(e)))

        thread = threading.Thread(target=execute)
        thread.daemon = True
        thread.start()

    def _on_execution_complete(self):
        """执行完成回调"""
        self.progress.close()

        if self.current_request.status == HelpStatus.COMPLETED:
            self._log("求助流程完成！")

            # 更新监控标签
            self._update_monitor_tab()

            # 更新答案标签
            self._update_answers_tab()

            # 启用相关按钮
            self.refresh_btn.setEnabled(True)
            self.publish_btn.setEnabled(True)

            # 切换到监控标签
            self.tabs.setCurrentIndex(2)

            QMessageBox.information(
                self,
                "求助已提交",
                f"您的帖子已发布到 {len(self.current_request.monitored_posts)} 个平台\n"
                "系统将自动监控回答并整合结果"
            )
        else:
            self._show_error(
                f"求助失败: {self.current_request.error_message or '未知错误'}"
            )

        self.analyze_btn.setEnabled(True)

    @pyqtSlot()
    def _on_publish(self):
        """发布帖子"""
        if not MODULE_AVAILABLE:
            return

        self._log("正在发布帖子...")
        # 实现发布逻辑

    @pyqtSlot()
    def _on_refresh_answers(self):
        """刷新答案"""
        if not self.current_request or not MODULE_AVAILABLE:
            return

        self._log("正在刷新答案...")

        # 重新整合答案
        aggregated = self.controller.refresh_answers(self.current_request.request_id)

        if aggregated:
            self._update_answers_tab()
            self._log("答案已更新")

    @pyqtSlot()
    def _on_stop_monitor(self):
        """停止监控"""
        if not self.current_request or not MODULE_AVAILABLE:
            return

        self.controller.stop_monitoring(self.current_request.request_id)
        self._log("已停止监控")
        self.monitor_status.setText("已停止")

    @pyqtSlot()
    def _on_copy_answer(self):
        """复制答案"""
        if not self.current_request or not self.current_request.aggregated_answer:
            return

        report = self.controller.get_user_report(self.current_request.request_id)
        if report:
            clipboard = QApplication.clipboard()
            clipboard.setText(report)
            self.status_bar.showMessage("已复制到剪贴板")

    @pyqtSlot()
    def _on_export_answer(self):
        """导出答案"""
        if not self.current_request:
            return

        # 显示导出对话框
        QMessageBox.information(self, "导出", "报告导出功能")

    def _on_status_changed(self, request: HelpRequest):
        """状态变更回调"""
        status_text = self.controller.get_status_description(request.status)
        self.status_bar.showMessage(f"状态: {status_text}")
        self._log(f"状态更新: {status_text}")

    def _on_new_answer_received(self, request: HelpRequest, answer):
        """新回答回调"""
        self._log(f"收到新回答 from {answer.author}")
        self._update_monitor_tab()
        self._update_answers_tab()

    def _update_monitor_tab(self):
        """更新监控标签页"""
        if not self.current_request:
            return

        request = self.current_request

        # 更新概览
        self.monitor_status.setText(request.status.value)
        self.monitor_posts_count.setText(str(len(request.monitored_posts)))

        total_answers = sum(len(p.answers) for p in request.monitored_posts)
        self.monitor_answers_count.setText(str(total_answers))

        # 更新帖子表格
        self.posts_table.setRowCount(len(request.monitored_posts))

        for i, post in enumerate(request.monitored_posts):
            self.posts_table.setItem(i, 0, QTableWidgetItem(post.platform.value))
            self.posts_table.setItem(i, 1, QTableWidgetItem(post.title[:30] + "..."))
            self.posts_table.setItem(i, 2, QTableWidgetItem(post.status.value))
            self.posts_table.setItem(i, 3, QTableWidgetItem(str(len(post.answers))))
            self.posts_table.setItem(i, 4, QTableWidgetItem(post.post_url[:30] + "..."))

        # 启用停止按钮
        self.stop_monitor_btn.setEnabled(True)

    def _update_answers_tab(self):
        """更新答案标签页"""
        if not self.current_request or not self.current_request.aggregated_answer:
            return

        aggregated = self.current_request.aggregated_answer

        # 更新概览
        self.answer_confidence.setText(f"{aggregated.confidence:.0%}")
        self.answer_sources.setText(f"{len(aggregated.sources)}个来源")

        # 更新整合答案
        report = self.controller.get_user_report(self.current_request.request_id)
        if report:
            self.aggregated_answer.setPlainText(report)

        # 更新关键点
        self.keypoints_list.clear()
        for point in aggregated.key_points:
            self.keypoints_list.addItem(point)

        # 启用按钮
        self.copy_answer_btn.setEnabled(True)
        self.export_answer_btn.setEnabled(True)

    def _log(self, message: str):
        """添加日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_output.append(f"[{timestamp}] {message}")

    def _show_error(self, message: str):
        """显示错误"""
        QMessageBox.critical(self, "错误", message)
        self.status_bar.showMessage(f"错误: {message}")

    def set_controller(self, controller: SmartHelpController):
        """设置控制器（供外部调用）"""
        self.controller = controller
        self.controller.register_status_callback(self._on_status_changed)
        self.controller.register_answer_callback(self._on_new_answer_received)
