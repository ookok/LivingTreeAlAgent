"""
增强版 IDE 面板
==============

PyQt6 UI 界面，提供智能代码生成、补全、测试功能。

Author: LivingTreeAI
from __future__ import annotations
"""

import logging
from typing import List, Optional, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTabWidget, QTextEdit, QLineEdit, QPushButton,
    QComboBox, QFormLayout, QSpinBox, QDoubleSpinBox,
    QCheckBox, QListWidget, QListWidgetItem,
    QMessageBox, QProgressBar, QSplitter,
    QFileDialog, QInputDialog
)
from PyQt6.QtCore import QTimer, Qt, pyqtSignal, QThread, QObject, QSize
from PyQt6.QtGui import QFont, QTextCursor, QAction, QKeySequence

logger = logging.getLogger(__name__)


class EnhancedIDEPanel(QWidget):
    """
    增强版 IDE 面板
    
    功能：
    1. AI 代码生成（自然语言 → 代码）
    2. 代码补全
    3. 测试生成
    4. 代码预览和应用
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._generator = None
        self._init_generator()
        self._init_ui()
        self._setup_timer()

    def _init_generator(self):
        """初始化代码生成器"""
        try:
            from client.src.business.ide.enhanced_ide import EnhancedIDEGenenerator, GenerationRequest
            self._generator = EnhancedIDEGenenerator()
            self._GenerationRequest = GenerationRequest
            logger.info("EnhancedIDE generator initialized")
        except Exception as e:
            logger.error(f"Failed to initialize generator: {e}")
            self._generator = None

    def _init_ui(self):
        """构建UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # 标题
        title = QLabel("🧠 智能 IDE")
        title.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #333333;
            padding-bottom: 8px;
        """)
        layout.addWidget(title)

        # 创建标签页
        self._tab_widget = QTabWidget()
        layout.addWidget(self._tab_widget)

        # 代码生成标签页
        self._generation_tab = self._create_generation_tab()
        self._tab_widget.addTab(self._generation_tab, "💡 代码生成")

        # 代码补全标签页
        self._completion_tab = self._create_completion_tab()
        self._tab_widget.addTab(self._completion_tab, "✏️ 代码补全")

        # 测试生成标签页
        self._testing_tab = self._create_testing_tab()
        self._tab_widget.addTab(self._testing_tab, "🧪 测试生成")

        # 历史记录标签页
        self._history_tab = self._create_history_tab()
        self._tab_widget.addTab(self._history_tab, "📋 历史记录")

        # 底部按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self._refresh_button = QPushButton("🔄 刷新")
        self._refresh_button.clicked.connect(self._refresh)
        button_layout.addWidget(self._refresh_button)

        layout.addLayout(button_layout)

    def _create_generation_tab(self) -> QWidget:
        """创建代码生成标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # 输入区域
        input_group = QGroupBox("代码生成请求")
        input_layout = QFormLayout(input_group)

        # 意图输入
        self._intent_edit = QLineEdit()
        self._intent_edit.setPlaceholderText("描述你想生成的代码...")
        input_layout.addRow("意图:", self._intent_edit)

        # 语言选择
        self._language_combo = QComboBox()
        self._language_combo.addItems(["python", "javascript", "typescript", "java", "go", "rust"])
        input_layout.addRow("语言:", self._language_combo)

        # 框架输入
        self._framework_edit = QLineEdit()
        self._framework_edit.setPlaceholderText("可选：如 FastAPI, React, Spring...")
        input_layout.addRow("框架:", self._framework_edit)

        # 选项
        self._include_tests_check = QCheckBox("生成测试")
        self._include_tests_check.setChecked(True)
        input_layout.addRow("", self._include_tests_check)

        self._include_comments_check = QCheckBox("包含注释")
        self._include_comments_check.setChecked(True)
        input_layout.addRow("", self._include_comments_check)

        self._optimize_check = QCheckBox("优化代码")
        self._optimize_check.setChecked(True)
        input_layout.addRow("", self._optimize_check)

        # 生成按钮
        self._generate_button = QPushButton("🚀 生成代码")
        self._generate_button.clicked.connect(self._generate_code)
        input_layout.addRow("", self._generate_button)

        layout.addWidget(input_group)

        # 输出区域
        output_group = QGroupBox("生成结果")
        output_layout = QVBoxLayout(output_group)

        self._generation_output = QTextEdit()
        self._generation_output.setReadOnly(True)
        self._generation_output.setFont(QFont("Courier", 10))
        self._generation_output.setMinimumHeight(300)
        output_layout.addWidget(self._generation_output)

        # 操作按钮
        button_layout = QHBoxLayout()

        self._copy_button = QPushButton("📋 复制")
        self._copy_button.clicked.connect(self._copy_generated)
        button_layout.addWidget(self._copy_button)

        self._apply_button = QPushButton("💾 应用")
        self._apply_button.clicked.connect(self._apply_generated)
        button_layout.addWidget(self._apply_button)

        self._test_button = QPushButton("🧪 生成测试")
        self._test_button.clicked.connect(self._generate_tests_for_code)
        button_layout.addWidget(self._test_button)

        button_layout.addStretch()
        output_layout.addLayout(button_layout)

        layout.addWidget(output_group)

        return widget

    def _create_completion_tab(self) -> QWidget:
        """创建代码补全标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # 输入区域
        input_group = QGroupBox("代码前缀")
        input_layout = QVBoxLayout(input_group)

        self._completion_input = QTextEdit()
        self._completion_input.setPlaceholderText("输入代码前缀...")
        self._completion_input.setMaximumHeight(100)
        input_layout.addWidget(self._completion_input)

        # 选项
        option_layout = QHBoxLayout()

        self._completion_language_combo = QComboBox()
        self._completion_language_combo.addItems(["python", "javascript", "typescript", "java"])
        option_layout.addWidget(QLabel("语言:"))
        option_layout.addWidget(self._completion_language_combo)

        self._completion_max_spin = QSpinBox()
        self._completion_max_spin.setRange(1, 10)
        self._completion_max_spin.setValue(3)
        option_layout.addWidget(QLabel("最大建议数:"))
        option_layout.addWidget(self._completion_max_spin)

        option_layout.addStretch()
        input_layout.addLayout(option_layout)

        # 补全按钮
        self._completion_button = QPushButton("✏️ 补全")
        self._completion_button.clicked.connect(self._complete_code)
        input_layout.addWidget(self._completion_button)

        layout.addWidget(input_group)

        # 输出区域
        output_group = QGroupBox("补全建议")
        output_layout = QVBoxLayout(output_group)

        self._completion_output = QListWidget()
        self._completion_output.itemClicked.connect(self._on_completion_selected)
        output_layout.addWidget(self._completion_output)

        # 补全详情
        self._completion_detail = QTextEdit()
        self._completion_detail.setReadOnly(True)
        self._completion_detail.setMaximumHeight(150)
        output_layout.addWidget(self._completion_detail)

        layout.addWidget(output_group)

        return widget

    def _create_testing_tab(self) -> QWidget:
        """创建测试生成标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # 输入区域
        input_group = QGroupBox("要测试的代码")
        input_layout = QVBoxLayout(input_group)

        self._test_input = QTextEdit()
        self._test_input.setPlaceholderText("输入要测试的代码...")
        input_layout.addWidget(self._test_input)

        # 选项
        option_layout = QHBoxLayout()

        self._test_language_combo = QComboBox()
        self._test_language_combo.addItems(["python", "javascript", "typescript", "java"])
        option_layout.addWidget(QLabel("语言:"))
        option_layout.addWidget(self._test_language_combo)

        self._test_type_combo = QComboBox()
        self._test_type_combo.addItems(["unit", "integration", "e2e"])
        option_layout.addWidget(QLabel("测试类型:"))
        option_layout.addWidget(self._test_type_combo)

        option_layout.addStretch()
        input_layout.addLayout(option_layout)

        # 生成按钮
        self._test_button = QPushButton("🧪 生成测试")
        self._test_button.clicked.connect(self._generate_tests)
        input_layout.addWidget(self._test_button)

        layout.addWidget(input_group)

        # 输出区域
        output_group = QGroupBox("生成的测试")
        output_layout = QVBoxLayout(output_group)

        self._test_output = QTextEdit()
        self._test_output.setReadOnly(True)
        self._test_output.setFont(QFont("Courier", 10))
        output_layout.addWidget(self._test_output)

        # 操作按钮
        button_layout = QHBoxLayout()

        self._test_copy_button = QPushButton("📋 复制")
        self._test_copy_button.clicked.connect(self._copy_tests)
        button_layout.addWidget(self._test_copy_button)

        self._test_apply_button = QPushButton("💾 保存")
        self._test_apply_button.clicked.connect(self._save_tests)
        button_layout.addWidget(self._test_apply_button)

        button_layout.addStretch()
        output_layout.addLayout(button_layout)

        layout.addWidget(output_group)

        return widget

    def _create_history_tab(self) -> QWidget:
        """创建历史记录标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # 历史列表
        self._history_list = QListWidget()
        self._history_list.itemClicked.connect(self._on_history_selected)
        layout.addWidget(self._history_list)

        # 历史详情
        self._history_detail = QTextEdit()
        self._history_detail.setReadOnly(True)
        self._history_detail.setMaximumHeight(200)
        layout.addWidget(self._history_detail)

        # 操作按钮
        button_layout = QHBoxLayout()

        self._history_clear_button = QPushButton("🗑️ 清空")
        self._history_clear_button.clicked.connect(self._clear_history)
        button_layout.addWidget(self._history_clear_button)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        return widget

    def _setup_timer(self):
        """设置定时器"""
        self._timer = QTimer()
        self._timer.timeout.connect(self._refresh)
        self._timer.start(30000)  # 每 30 秒刷新一次

    def _refresh(self):
        """刷新"""
        try:
            # 重新初始化生成器
            self._init_generator()

            # 更新历史记录
            self._update_history()

            logger.info("IDE panel refreshed")
        except Exception as e:
            logger.error(f"Refresh failed: {e}")

    def _generate_code(self):
        """生成代码"""
        try:
            if not self._generator:
                QMessageBox.warning(self, "警告", "代码生成器未初始化")
                return

            # 获取输入
            intent = self._intent_edit.text().strip()
            if not intent:
                QMessageBox.warning(self, "警告", "请输入代码生成意图")
                return

            language = self._language_combo.currentText()
            framework = self._framework_edit.text().strip()

            # 构建请求
            request = self._GenerationRequest(
                intent=intent,
                language=language,
                framework=framework,
                include_tests=self._include_tests_check.isChecked(),
                include_comments=self._include_comments_check.isChecked(),
                optimize=self._optimize_check.isChecked(),
            )

            # 生成代码
            self._generation_output.append("⏳ 正在生成代码...")

            result = self._generator.generate(request)

            if result.success:
                # 显示生成的代码
                code = result.generated.code
                self._generation_output.setPlainText(code)

                # 显示测试（如果有）
                if result.tests:
                    self._generation_output.append("\n\n# ===== 生成的测试 =====\n")
                    for test in result.tests:
                        self._generation_output.append(test.test_code)
                        self._generation_output.append("\n")

                self._generation_output.append("\n✅ 代码生成成功")

                # 更新历史记录
                self._update_history()

            else:
                self._generation_output.append(f"\n❌ 代码生成失败: {result.error}")

        except Exception as e:
            logger.error(f"Code generation failed: {e}")
            self._generation_output.append(f"\n❌ 代码生成失败: {e}")
            QMessageBox.critical(self, "错误", f"代码生成失败: {e}")

    def _complete_code(self):
        """代码补全"""
        try:
            if not self._generator:
                QMessageBox.warning(self, "警告", "代码生成器未初始化")
                return

            # 获取输入
            code_prefix = self._completion_input.toPlainText().strip()
            if not code_prefix:
                QMessageBox.warning(self, "警告", "请输入代码前缀")
                return

            language = self._completion_language_combo.currentText()
            max_suggestions = self._completion_max_spin.value()

            # 调用补全
            completions = self._generator.complete(
                code_prefix=code_prefix,
                language=language,
                max_suggestions=max_suggestions,
            )

            # 显示补全建议
            self._completion_output.clear()

            for i, comp in enumerate(completions):
                item = QListWidgetItem(f"{i+1}. {comp.completion}")
                item.setData(Qt.ItemDataRole.UserRole, i)
                self._completion_output.addItem(item)

            if completions:
                # 显示第一个补全的详情
                self._completion_detail.setPlainText(
                    f"解释: {completions[0].explanation}\n\n"
                    f"置信度: {completions[0].confidence:.0%}\n\n"
                    f"备选:\n" + "\n".join(completions[0].alternatives)
                )

        except Exception as e:
            logger.error(f"Code completion failed: {e}")
            QMessageBox.critical(self, "错误", f"代码补全失败: {e}")

    def _generate_tests(self):
        """生成测试"""
        try:
            if not self._generator:
                QMessageBox.warning(self, "警告", "代码生成器未初始化")
                return

            # 获取输入
            code = self._test_input.toPlainText().strip()
            if not code:
                QMessageBox.warning(self, "警告", "请输入要测试的代码")
                return

            language = self._test_language_combo.currentText()
            test_type = self._test_type_combo.currentText()

            # 生成测试
            self._test_output.append("⏳ 正在生成测试...")

            tests = self._generator.generate_tests(
                code=code,
                language=language,
                test_type=test_type,
            )

            if tests:
                # 显示生成的测试
                output = ""
                for i, test in enumerate(tests):
                    output += f"# ===== 测试 {i+1}: {test.test_description} =====\n"
                    output += test.test_code
                    output += f"\n\n# 覆盖率: {test.coverage:.0%}\n\n"

                self._test_output.setPlainText(output)
                self._test_output.append("\n✅ 测试生成成功")

            else:
                self._test_output.append("\n❌ 测试生成失败")

        except Exception as e:
            logger.error(f"Test generation failed: {e}")
            self._test_output.append(f"\n❌ 测试生成失败: {e}")
            QMessageBox.critical(self, "错误", f"测试生成失败: {e}")

    def _copy_generated(self):
        """复制生成的代码"""
        try:
            code = self._generation_output.toPlainText()
            if code:
                QApplication.clipboard().setText(code)
                QMessageBox.information(self, "成功", "代码已复制到剪贴板")
        except Exception as e:
            logger.error(f"Copy failed: {e}")

    def _apply_generated(self):
        """应用生成的代码"""
        try:
            code = self._generation_output.toPlainText()
            if not code:
                return

            # 选择文件路径
            file_path, _ = QFileDialog.getSaveFileName(
                self, "保存代码", "", "Python Files (*.py);;All Files (*)"
            )

            if file_path:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(code)
                QMessageBox.information(self, "成功", f"代码已保存到 {file_path}")

        except Exception as e:
            logger.error(f"Apply failed: {e}")
            QMessageBox.critical(self, "错误", f"应用失败: {e}")

    def _generate_tests_for_code(self):
        """为生成的代码生成测试"""
        try:
            code = self._generation_output.toPlainText()
            if not code:
                QMessageBox.warning(self, "警告", "请先生成代码")
                return

            # 切换到测试生成标签页
            self._tab_widget.setCurrentIndex(2)

            # 填充代码
            self._test_input.setPlainText(code)
            self._test_language_combo.setCurrentText(self._language_combo.currentText())

            # 生成测试
            self._generate_tests()

        except Exception as e:
            logger.error(f"Generate tests for code failed: {e}")

    def _on_completion_selected(self, item: QListWidgetItem):
        """补全建议选中事件"""
        try:
            index = item.data(Qt.ItemDataRole.UserRole)
            # TODO: 显示选中补全的详情
        except Exception as e:
            logger.error(f"Completion selection failed: {e}")

    def _on_history_selected(self, item: QListWidgetItem):
        """历史记录选中事件"""
        try:
            # TODO: 显示历史记录详情
            pass
        except Exception as e:
            logger.error(f"History selection failed: {e}")

    def _copy_tests(self):
        """复制生成的测试"""
        try:
            tests = self._test_output.toPlainText()
            if tests:
                QApplication.clipboard().setText(tests)
                QMessageBox.information(self, "成功", "测试已复制到剪贴板")
        except Exception as e:
            logger.error(f"Copy tests failed: {e}")

    def _save_tests(self):
        """保存生成的测试"""
        try:
            tests = self._test_output.toPlainText()
            if not tests:
                return

            # 选择文件路径
            file_path, _ = QFileDialog.getSaveFileName(
                self, "保存测试", "", "Python Files (*.py);;All Files (*)"
            )

            if file_path:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(tests)
                QMessageBox.information(self, "成功", f"测试已保存到 {file_path}")

        except Exception as e:
            logger.error(f"Save tests failed: {e}")
            QMessageBox.critical(self, "错误", f"保存失败: {e}")

    def _update_history(self):
        """更新历史记录"""
        try:
            if not self._generator:
                return

            history = self._generator.get_history()

            self._history_list.clear()

            for i, result in enumerate(history):
                if result.success and result.generated:
                    item = QListWidgetItem(f"{i+1}. {result.generated.description}")
                    item.setData(Qt.ItemDataRole.UserRole, i)
                    self._history_list.addItem(item)

        except Exception as e:
            logger.error(f"Update history failed: {e}")

    def _clear_history(self):
        """清空历史记录"""
        try:
            if self._generator:
                self._generator.clear_history()
                self._update_history()
                QMessageBox.information(self, "成功", "历史记录已清空")
        except Exception as e:
            logger.error(f"Clear history failed: {e}")

    def closeEvent(self, event):
        """关闭事件"""
        if hasattr(self, '_timer'):
            self._timer.stop()
        super().closeEvent(event)
