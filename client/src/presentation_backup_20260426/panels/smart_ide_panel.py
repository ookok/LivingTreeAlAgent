# -*- coding: utf-8 -*-
"""
Smart IDE Panel - PyQt6 智能IDE与游戏系统 UI
==============================================

功能：
- 代码编辑器核心
- AI编程助手
- 调试系统
- 记忆增强编辑器
- 协同编辑
- GitHub 项目集成（克隆、编辑、推送、拉取）

Author: Hermes Desktop Team
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QListWidget,
    QListWidgetItem, QComboBox, QTabWidget, QGroupBox,
    QScrollArea, QFrame, QProgressBar, QTableWidget,
    QTableWidgetItem, QHeaderView, QStatusBar, QMenuBar, QMenu,
    QToolButton, QStackedWidget, QFormLayout, QSpinBox,
    QCheckBox, QMessageBox, QSplitter, QFileDialog,
    QInputDialog, QDialog, QPlainTextEdit
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QThread, pyqtSlot, QTimer, QRegularExpression
from PyQt6.QtGui import QFont, QIcon, QAction, QColor, QPalette, QPainter, QPen, QSyntaxHighlighter, QTextCharFormat, QRegularExpressionValidator

import asyncio
import json
import time
import os
import subprocess
from datetime import datetime
from typing import Optional, Dict, List

from client.src.business.smart_ide_game import (
    SmartIDEGameSystem, CodeEditorCore, AICodingAssistant,
    MemoryEnhancedEditor, CollabEditor,
    LanguageType, TaskType
)
from client.src.business.github_project_manager import GitHubProjectManager, get_github_project_manager


# ==================== 代码编辑器组件 ====================

class CodeEditorWidget(QPlainTextEdit):
    """代码编辑器组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        self.setFont(QFont("Consolas", 10))
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: none;
                padding: 8px;
            }
        """)


class SimpleHighlighter(QSyntaxHighlighter):
    """简单语法高亮"""

    def __init__(self, parent):
        super().__init__(parent)
        self.highlighting_rules = []
        
        # 关键字
        keywords = ["def", "class", "if", "else", "elif", "for", "while", "return", "import", "from", "as", "try", "except", "with", "True", "False", "None"]
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#569cd6"))
        for word in keywords:
            self.highlighting_rules.append((QRegularExpression(f"\\b{word}\\b"), keyword_format))
        
        # 字符串
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#ce9178"))
        self.highlighting_rules.append((QRegularExpression("\".*\""), string_format))
        self.highlighting_rules.append((QRegularExpression("'.*'"), string_format))
        
        # 注释
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6a9955"))
        self.highlighting_rules.append((QRegularExpression("#.*"), comment_format))

    def highlightBlock(self, text):
        for pattern, fmt in self.highlighting_rules:
            expression = QRegularExpression(pattern)
            index = expression.match(text)
            while index >= 0:
                length = expression.capturedLength()
                self.setFormat(index, length, fmt)
                index = expression.match(text, index + length)


# ==================== AI 推荐卡片 ====================

class AIRecommendationCard(QFrame):
    """AI 推荐卡片"""

    def __init__(self, recommendation: Dict, parent=None):
        super().__init__(parent)
        self.recommendation = recommendation
        self._setup_ui()
        self._update_style()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        # 类型标签
        type_layout = QHBoxLayout()
        type_label = QLabel(f"[{self.recommendation.get('type', 'general')}]")
        type_label.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        type_label.setStyleSheet("""
            background-color: #e6f7ff;
            color: #1890ff;
            border-radius: 4px;
            padding: 2px 6px;
        """)
        type_layout.addWidget(type_label)
        type_layout.addStretch()
        
        confidence = self.recommendation.get('confidence', 0)
        confidence_label = QLabel(f"置信度: {confidence:.2f}")
        confidence_label.setFont(QFont("Microsoft YaHei", 9))
        confidence_label.setStyleSheet("color: #888;")
        type_layout.addWidget(confidence_label)
        
        layout.addLayout(type_layout)

        # 内容
        content_label = QLabel(self.recommendation.get('content', ''))
        content_label.setWordWrap(True)
        content_label.setFont(QFont("Microsoft YaHei", 10))
        layout.addWidget(content_label)

        # 操作按钮
        if self.recommendation.get('actions'):
            actions_layout = QHBoxLayout()
            for action in self.recommendation.get('actions', [])[:2]:
                action_btn = QPushButton(action.get('label', 'Action'))
                action_btn.setFont(QFont("Microsoft YaHei", 9))
                actions_layout.addWidget(action_btn)
            actions_layout.addStretch()
            layout.addLayout(actions_layout)

    def _update_style(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet("""
            AIRecommendationCard {
                background-color: #fff;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
            }
            AIRecommendationCard:hover {
                border-color: #1890ff;
            }
        """)


# ==================== 代码片段卡片 ====================

class SnippetCard(QFrame):
    """代码片段卡片"""

    apply_signal = pyqtSignal(str)  # 触发词信号

    def __init__(self, snippet: Dict, parent=None):
        super().__init__(parent)
        self.snippet = snippet
        self._setup_ui()
        self._update_style()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # 头部
        header_layout = QHBoxLayout()
        
        trigger_label = QLabel(f"📎 {self.snippet.get('trigger', 'unknown')}")
        trigger_label.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        header_layout.addWidget(trigger_label)
        
        language_label = QLabel(self.snippet.get('language', 'plaintext'))
        language_label.setFont(QFont("Consolas", 8))
        language_label.setStyleSheet("""
            background-color: #f0f0f0;
            color: #666;
            border-radius: 4px;
            padding: 2px 6px;
        """)
        header_layout.addWidget(language_label)
        
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # 预览
        preview_label = QLabel(self.snippet.get('code', '')[:100] + "..." if len(self.snippet.get('code', '')) > 100 else self.snippet.get('code', ''))
        preview_label.setFont(QFont("Consolas", 9))
        preview_label.setStyleSheet("color: #666;")
        preview_label.setWordWrap(True)
        layout.addWidget(preview_label)

        # 上下文
        context_label = QLabel(f"📝 {self.snippet.get('context', '')}")
        context_label.setFont(QFont("Microsoft YaHei", 9))
        context_label.setStyleSheet("color: #888;")
        context_label.setWordWrap(True)
        layout.addWidget(context_label)

        # 使用按钮
        apply_btn = QPushButton("✨ 插入代码")
        apply_btn.setFont(QFont("Microsoft YaHei", 9))
        apply_btn.clicked.connect(lambda: self.apply_signal.emit(self.snippet.get('trigger', '')))
        layout.addWidget(apply_btn)

    def _update_style(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet("""
            SnippetCard {
                background-color: #fff;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
            }
            SnippetCard:hover {
                border-color: #52c41a;
            }
        """)


# ==================== Smart IDE Panel ====================

class SmartIDEPanel(QWidget):
    """智能IDE面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 初始化系统
        self.storage_path = "~/.hermes-desktop/smart_ide_game"
        self.system = SmartIDEGameSystem(self.storage_path)
        
        # GitHub 项目管理器
        self._github_manager = get_github_project_manager()
        
        # 协程事件循环
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        self._setup_ui()
        self._load_snippets()
        self._refresh_github_projects()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 顶部工具栏
        toolbar = QFrame()
        toolbar.setStyleSheet("background-color: #f5f5f5; border-bottom: 1px solid #e0e0e0;")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(12, 8, 12, 8)
        toolbar_layout.setSpacing(12)

        # 文件操作
        new_file_btn = QPushButton("📄 新建")
        new_file_btn.clicked.connect(self._on_new_file)
        toolbar_layout.addWidget(new_file_btn)

        open_file_btn = QPushButton("📂 打开")
        open_file_btn.clicked.connect(self._on_open_file)
        toolbar_layout.addWidget(open_file_btn)

        save_file_btn = QPushButton("💾 保存")
        save_file_btn.clicked.connect(self._on_save_file)
        toolbar_layout.addWidget(save_file_btn)

        toolbar_layout.addSpacing(20)

        # 语言选择
        language_label = QLabel("语言:")
        toolbar_layout.addWidget(language_label)

        self.language_combo = QComboBox()
        self.language_combo.addItems([
            "python", "javascript", "typescript", "java", "cpp", "c",
            "go", "rust", "ruby", "php", "swift", "html", "css", "json", "yaml", "markdown"
        ])
        self.language_combo.setCurrentText("python")
        self.language_combo.currentTextChanged.connect(self._on_language_changed)
        toolbar_layout.addWidget(self.language_combo)

        toolbar_layout.addStretch()

        # AI 助手按钮
        ai_btn = QPushButton("🤖 AI 助手")
        ai_btn.clicked.connect(self._on_show_ai_assistant)
        toolbar_layout.addWidget(ai_btn)

        main_layout.addWidget(toolbar)

        # 主内容区
        content_layout = QHBoxLayout()
        content_layout.setSpacing(0)

        # 左侧：文件浏览器（简化）
        left_panel = QFrame()
        left_panel.setMaximumWidth(200)
        left_panel.setStyleSheet("background-color: #fafafa; border-right: 1px solid #e0e0e0;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)

        files_label = QLabel("📁 文件")
        files_label.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        left_layout.addWidget(files_label)

        self.file_list = QListWidget()
        self.file_list.setStyleSheet("""
            QListWidget {
                border: none;
                background-color: transparent;
            }
            QListWidget::item {
                padding: 4px;
            }
        """)
        left_layout.addWidget(self.file_list)

        main_layout.addLayout(content_layout)

        # 中央：代码编辑器
        center_panel = QFrame()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)

        # 编辑器标签栏
        self.editor_tabs = QTabWidget()
        self.editor_tabs.setTabsClosable(True)
        self.editor_tabs.tabCloseRequested.connect(self._on_close_tab)
        center_layout.addWidget(self.editor_tabs)

        # 默认标签
        self.code_editor = CodeEditorWidget()
        self.highlighter = SimpleHighlighter(self.code_editor.document())
        self.editor_tabs.addTab(self.code_editor, "untitled.py")

        content_layout.addWidget(center_panel, 1)

        # 右侧：AI 推荐和代码片段
        right_panel = QFrame()
        right_panel.setMaximumWidth(300)
        right_panel.setStyleSheet("background-color: #f5f5f5; border-left: 1px solid #e0e0e0;")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(12)

        # AI 推荐
        ai_group = QGroupBox("🤖 AI 编程助手")
        ai_layout = QVBoxLayout()
        
        self.ai_input = QLineEdit()
        self.ai_input.setPlaceholderText("描述你想做什么...")
        ai_layout.addWidget(self.ai_input)
        
        ai_btns = QHBoxLayout()
        generate_btn = QPushButton("✨ 生成代码")
        generate_btn.clicked.connect(self._on_generate_code)
        ai_btns.addWidget(generate_btn)
        
        diagnose_btn = QPushButton("🔍 诊断错误")
        diagnose_btn.clicked.connect(self._on_diagnose_error)
        ai_btns.addWidget(diagnose_btn)
        ai_layout.addLayout(ai_btns)
        
        self.ai_recommendations = QListWidget()
        self.ai_recommendations.setMaximumHeight(200)
        self.ai_recommendations.setStyleSheet("""
            QListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background-color: #fff;
            }
        """)
        ai_layout.addWidget(self.ai_recommendations)
        
        ai_group.setLayout(ai_layout)
        right_layout.addWidget(ai_group)

        # 代码片段
        snippet_group = QGroupBox("📚 代码片段库")
        snippet_layout = QVBoxLayout()
        
        self.snippet_search = QLineEdit()
        self.snippet_search.setPlaceholderText("🔍 搜索片段...")
        self.snippet_search.textChanged.connect(self._on_snippet_search)
        snippet_layout.addWidget(self.snippet_search)
        
        self.snippet_list = QListWidget()
        self.snippet_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background-color: #fff;
            }
        """)
        snippet_layout.addWidget(self.snippet_list)
        
        snippet_group.setLayout(snippet_layout)
        right_layout.addWidget(snippet_group, 1)

        content_layout.addWidget(right_panel)

        # 底部状态栏
        status_bar = QFrame()
        status_bar.setStyleSheet("background-color: #f5f5f5; border-top: 1px solid #e0e0e0;")
        status_layout = QHLayout(status_bar)
        status_layout.setContentsMargins(12, 4, 12, 4)

        self.status_label = QLabel("就绪")
        status_label_font = QFont("Microsoft YaHei", 9)
        self.status_label.setFont(status_label_font)
        status_layout.addWidget(self.status_label)

        status_layout.addStretch()

        self.cursor_label = QLabel("行: 1, 列: 1")
        self.cursor_label.setFont(QFont("Consolas", 9))
        status_layout.addWidget(self.cursor_label)

        main_layout.addWidget(status_bar)
        
        # GitHub 工具栏
        self._setup_github_toolbar()
    
    def _setup_github_toolbar(self):
        """设置 GitHub 工具栏"""
        # 在主布局下方添加 GitHub 操作按钮
        github_bar = QFrame()
        github_bar.setStyleSheet("background-color: #24292e; padding: 8px;")
        github_layout = QHBoxLayout(github_bar)
        github_layout.setContentsMargins(12, 4, 12, 4)
        
        # GitHub 图标和标题
        github_title = QLabel("🐙 GitHub")
        github_title.setStyleSheet("color: white; font-size: 14px; font-weight: bold;")
        github_layout.addWidget(github_title)
        
        github_layout.addSpacing(20)
        
        # 克隆按钮
        clone_btn = QPushButton("⬇️ 克隆")
        clone_btn.setStyleSheet("background: #2ea44f; color: white; border: none; padding: 6px 12px; border-radius: 6px;")
        clone_btn.clicked.connect(self._on_github_clone)
        github_layout.addWidget(clone_btn)
        
        # 拉取按钮
        pull_btn = QPushButton("🔄 拉取")
        pull_btn.setStyleSheet("background: #0366d6; color: white; border: none; padding: 6px 12px; border-radius: 6px;")
        pull_btn.clicked.connect(self._on_github_pull)
        github_layout.addWidget(pull_btn)
        
        # 推送按钮
        push_btn = QPushButton("⬆️ 推送")
        push_btn.setStyleSheet("background: #d73a49; color: white; border: none; padding: 6px 12px; border-radius: 6px;")
        push_btn.clicked.connect(self._on_github_push)
        github_layout.addWidget(push_btn)
        
        github_layout.addStretch()
        
        # 分支信息
        self.branch_label = QLabel("分支: main")
        self.branch_label.setStyleSheet("color: #e1e4e8; font-size: 12px;")
        github_layout.addWidget(self.branch_label)
        
        # 添加到主布局
        self.layout().addWidget(github_bar)
    
    def _refresh_github_projects(self):
        """刷新 GitHub 项目列表"""
        try:
            projects = self._github_manager.list_projects()
            if projects:
                self.status_label.setText(f"已加载 {len(projects)} 个 GitHub 项目")
        except Exception:
            pass
        """加载代码片段"""
        # 从记忆编辑器获取片段
        try:
            snippets = self.system.memory_editor.get_all_snippets()
            for snippet in snippets[:10]:
                item = QListWidgetItem()
                item.setSizeHint(QSize(260, 100))
                self.snippet_list.addItem(item)
                
                card = SnippetCard(snippet)
                card.apply_signal.connect(self._on_apply_snippet)
                self.snippet_list.setItemWidget(item, card)
        except Exception as e:
            pass

    def _on_new_file(self):
        """新建文件"""
        self.code_editor.clear()
        self.editor_tabs.addTab(self.code_editor, "untitled.py")

    def _on_open_file(self):
        """打开文件"""
        path, _ = QFileDialog.getOpenFileName(
            self, "打开文件", "~", "All Files (*.*)"
        )
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.code_editor.setPlainText(content)
                self.editor_tabs.setTabText(self.editor_tabs.currentIndex(), os.path.basename(path))
                self.status_label.setText(f"已打开: {path}")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"无法打开文件: {e}")

    def _on_save_file(self):
        """保存文件"""
        path, _ = QFileDialog.getSaveFileName(
            self, "保存文件", "~", "All Files (*.*)"
        )
        if path:
            try:
                content = self.code_editor.toPlainText()
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                self.editor_tabs.setTabText(self.editor_tabs.currentIndex(), os.path.basename(path))
                self.status_label.setText(f"已保存: {path}")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"无法保存文件: {e}")

    def _on_close_tab(self, index: int):
        """关闭标签"""
        self.editor_tabs.removeTab(index)

    def _on_language_changed(self, language: str):
        """语言变更"""
        self.status_label.setText(f"当前语言: {language}")

    def _on_show_ai_assistant(self):
        """显示 AI 助手"""
        self.status_label.setText("AI 助手已激活")

    def _on_generate_code(self):
        """生成代码"""
        prompt = self.ai_input.text().strip()
        if not prompt:
            return
        
        self.status_label.setText("正在生成代码...")
        
        # 异步生成
        def generate():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(
                    self.system.generate_code(prompt, self.language_combo.currentText())
                )
                loop.close()
                
                # 在主线程更新 UI
                self.code_editor.setPlainText(result)
                self.status_label.setText("代码生成完成")
                
                # 添加推荐卡片
                self._add_ai_recommendation({
                    'type': 'code_generation',
                    'content': result[:200] + "..." if len(result) > 200 else result,
                    'confidence': 0.85
                })
            except Exception as e:
                self.status_label.setText(f"生成失败: {e}")
        
        QTimer.singleShot(100, generate)

    def _on_diagnose_error(self):
        """诊断错误"""
        code = self.code_editor.toPlainText()
        if not code:
            return
        
        self.status_label.setText("正在诊断错误...")
        
        # 模拟诊断
        def diagnose():
            try:
                recommendations = [
                    {
                        'type': 'error_fix',
                        'content': '检测到可能的语法错误，请检查括号匹配',
                        'confidence': 0.9,
                        'actions': [{'label': '自动修复'}]
                    }
                ]
                
                for rec in recommendations:
                    self._add_ai_recommendation(rec)
                
                self.status_label.setText("诊断完成")
            except Exception as e:
                self.status_label.setText(f"诊断失败: {e}")
        
        QTimer.singleShot(100, diagnose)

    def _add_ai_recommendation(self, recommendation: Dict):
        """添加 AI 推荐"""
        item = QListWidgetItem()
        item.setSizeHint(QSize(260, 100))
        self.ai_recommendations.addItem(item)
        
        card = AIRecommendationCard(recommendation)
        self.ai_recommendations.setItemWidget(item, card)

    def _on_snippet_search(self, text: str):
        """搜索代码片段"""
        for i in range(self.snippet_list.count()):
            item = self.snippet_list.item(i)
            widget = self.snippet_list.itemWidget(item)
            if widget and text.lower() in widget.snippet.get('trigger', '').lower():
                item.setHidden(False)
            else:
                item.setHidden(True)

    def _on_apply_snippet(self, trigger: str):
        """应用代码片段"""
        snippet = self.system.memory_editor.get_snippet(trigger)
        if snippet:
            # 在光标位置插入代码
            cursor = self.code_editor.textCursor()
            cursor.insertText(snippet.get('code', ''))
            self.status_label.setText(f"已插入片段: {trigger}")

    def _on_github_clone(self):
        """从 GitHub 克隆仓库"""
        repo, ok = QInputDialog.getText(
            self, "克隆仓库", "请输入仓库地址 (owner/repo 或完整 URL):"
        )
        if not ok or not repo:
            return
        
        branch, ok = QInputDialog.getText(
            self, "选择分支", "请输入分支名 (默认 main):", text="main"
        )
        if not ok:
            branch = "main"
        
        self.status_label.setText(f"正在克隆 {repo}...")
        
        def do_clone():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                success, message = loop.run_until_complete(
                    self._github_manager.clone(repo, branch=branch)
                )
                loop.close()
                
                # 更新 UI
                if success:
                    self.status_label.setText(f"克隆成功: {message}")
                    self._refresh_github_projects()
                else:
                    self.status_label.setText(f"克隆失败: {message}")
            except Exception as e:
                self.status_label.setText(f"克隆异常: {e}")
        
        QTimer.singleShot(100, do_clone)
    
    def _on_github_pull(self):
        """从 GitHub 拉取更新"""
        projects = self._github_manager.list_projects()
        if not projects:
            QMessageBox.information(self, "提示", "没有已克隆的项目")
            return
        
        # 选择项目
        project_names = [p['name'] for p in projects]
        project_path = projects[0]['path']  # 默认选择第一个
        
        self.status_label.setText("正在拉取更新...")
        
        def do_pull():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                success, message = loop.run_until_complete(
                    self._github_manager.pull(project_path)
                )
                loop.close()
                
                if success:
                    self.status_label.setText("拉取成功")
                else:
                    self.status_label.setText(f"拉取失败: {message}")
            except Exception as e:
                self.status_label.setText(f"拉取异常: {e}")
        
        QTimer.singleShot(100, do_pull)
    
    def _on_github_push(self):
        """推送代码到 GitHub"""
        projects = self._github_manager.list_projects()
        if not projects:
            QMessageBox.information(self, "提示", "没有已克隆的项目")
            return
        
        # 提交信息
        message, ok = QInputDialog.getText(
            self, "提交更改", "请输入提交信息:"
        )
        if not ok or not message:
            return
        
        project_path = projects[0]['path']  # 默认选择第一个
        
        self.status_label.setText("正在提交并推送...")
        
        def do_push():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                success, result_msg = loop.run_until_complete(
                    self._github_manager.commit_and_push(project_path, message)
                )
                loop.close()
                
                if success:
                    self.status_label.setText(f"推送成功: {result_msg}")
                else:
                    self.status_label.setText(f"推送失败: {result_msg}")
            except Exception as e:
                self.status_label.setText(f"推送异常: {e}")
        
        QTimer.singleShot(100, do_push)


# ==================== 导出 ====================

__all__ = ['SmartIDEPanel', 'CodeEditorWidget', 'AIRecommendationCard', 'SnippetCard']
