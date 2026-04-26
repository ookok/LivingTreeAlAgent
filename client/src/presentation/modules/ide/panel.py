#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能 IDE 面板 - 完整自动化开发功能
======================================

集成功能：
1. 项目浏览器（文件树）
2. 代码编辑器（多标签）
3. 全局搜索/替换
4. 测试集成（pytest）
5. 重构引擎
6. 部署管理
7. Git 集成
8. AI 辅助编程

Author: LivingTreeAI Agent
Date: 2026-04-26
"""

import os
import sys
from typing import Optional, Dict
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
    QPushButton, QLabel, QFrame, QFileDialog, QMessageBox,
    QTabWidget, QComboBox, QSplitter, QTextEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtGui import QFont, QTextCursor

from client.src.business.nanochat_config import config
from client.src.business.ide_agent import get_ide_agent

# 导入新创建的组件
from client.src.presentation.widgets.project_browser import ProjectBrowser
from client.src.presentation.widgets.global_search import GlobalSearchPanel
from client.src.presentation.widgets.test_integration import TestIntegrationPanel
from client.src.presentation.widgets.git_integration import GitIntegrationPanel


# ── 代码执行工作线程 ────────────────────────────────────────────────

class CodeExecutionWorker(QThread):
    """代码执行工作线程（真实执行）"""
    
    output = pyqtSignal(str)          # 输出
    error = pyqtSignal(str)           # 错误
    finished = pyqtSignal(int)        # 完成（退出码）
    status = pyqtSignal(str)          # 状态更新
    
    def __init__(self, agent, code: str, language: str, parent=None):
        super().__init__(parent)
        self.agent = agent
        self.code = code
        self.language = language
        self._stop_requested = False
    
    def run(self):
        try:
            self.status.emit(f"正在执行 {self.language} 代码...")
            
            # 通过 Agent 执行代码（真实执行）
            result = self.agent.execute_code(self.code, self.language)
            
            # 发送输出
            if result['output']:
                self.output.emit(result['output'])
            
            # 发送错误
            if result['error']:
                self.error.emit(result['error'])
            
            # 发送完成信号
            self.finished.emit(result['exit_code'])
            self.status.emit(f"执行完成（退出码: {result['exit_code']}）")
            
        except Exception as e:
            import traceback
            error_msg = f"执行失败: {str(e)}\n{traceback.format_exc()}"
            self.error.emit(error_msg)
            self.finished.emit(1)
            self.status.emit("执行失败")
    
    def stop(self):
        self._stop_requested = True


# ── AI 辅助工作线程 ────────────────────────────────────────────────

class AIAssistWorker(QThread):
    """AI 辅助工作线程"""
    
    result_ready = pyqtSignal(str)     # 结果就绪
    error = pyqtSignal(str)           # 错误
    finished = pyqtSignal()            # 完成
    
    def __init__(self, agent, code: str, language: str, assist_type: str, parent=None):
        super().__init__(parent)
        self.agent = agent
        self.code = code
        self.language = language
        self.assist_type = assist_type
    
    def run(self):
        try:
            if self.assist_type == "explain":
                explanation = self.agent.explain_code(self.code, self.language)
                self.result_ready.emit(explanation)
            
            elif self.assist_type == "debug":
                debug_info = self.agent.debug_code(self.code, self.language)
                self.result_ready.emit(debug_info)
            
            elif self.assist_type == "optimize":
                optimization = self.agent.optimize_code(self.code, self.language)
                self.result_ready.emit(optimization)
            
            elif self.assist_type == "generate":
                intent = self.code
                result = self.agent.generate_code(intent, self.language)
                if result['success']:
                    self.result_ready.emit(result['code'])
                else:
                    self.error.emit(result['error'])
            
            else:
                self.error.emit(f"未知的辅助类型: {self.assist_type}")
            
            self.finished.emit()
            
        except Exception as e:
            import traceback
            error_msg = f"AI 辅助失败: {str(e)}\n{traceback.format_exc()}"
            self.error.emit(error_msg)
            self.finished.emit()


# ── 代码编辑器 ─────────────────────────────────────────────────────

class CodeEditor(QPlainTextEdit):
    """代码编辑器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        # 设置字体
        font = QFont("Consolas", 13)
        self.setFont(font)
        
        # 设置样式
        self.setStyleSheet("""
            QPlainTextEdit {
                background: #1E1E1E;
                color: #D4D4D4;
                border: none;
                padding: 12px;
                font-family: Consolas, 'Courier New', monospace;
            }
        """)
    
    def set_content(self, content: str):
        """设置内容"""
        self.setPlainText(content)
    
    def get_content(self) -> str:
        """获取内容"""
        return self.toPlainText()
    
    def set_language(self, language: str):
        """设置语言（用于语法高亮，暂未实现）"""
        pass


# ── 主智能 IDE 面板 ────────────────────────────────────────────────

class Panel(QWidget):
    """
    智能 IDE 面板 - 完整自动化开发功能
    
    架构：UI → Agent → Service
    """
    
    code_executed = pyqtSignal(str, str)  # 代码, 语言
    ai_requested = pyqtSignal(str)        # 请求 AI 辅助
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 架构修正：使用 Agent，不是直接调用 Service
        self.agent = get_ide_agent()
        self.current_file: Optional[str] = None
        self.worker: Optional[CodeExecutionWorker] = None
        self.ai_worker: Optional[AIAssistWorker] = None
        
        self._setup_ui()
        self._connect_signals()
        self._load_sample()
    
    def _setup_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 标题栏
        title_bar = self._create_title_bar()
        layout.addWidget(title_bar)
        
        # 主分割器（水平）
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.setStyleSheet("QSplitter::handle { background: #3E3E42; }")
        
        # 左侧：项目浏览器
        self.project_browser = ProjectBrowser()
        self.project_browser.setFixedWidth(250)
        self.project_browser.set_project_root(os.getcwd())
        main_splitter.addWidget(self.project_browser)
        
        # 中间：编辑器区域
        editor_widget = self._create_editor_area()
        main_splitter.addWidget(editor_widget)
        
        # 右侧：输出面板
        output_widget = self._create_output_area()
        main_splitter.addWidget(output_widget)
        
        # 设置分割比例
        main_splitter.setStretchFactor(0, 0)  # 项目浏览器固定宽度
        main_splitter.setStretchFactor(1, 2)  # 编辑器占 2/3
        main_splitter.setStretchFactor(2, 1)  # 输出占 1/3
        
        layout.addWidget(main_splitter, 1)
        
        # 底部：工具面板（搜索/测试/Git/部署）
        self.tool_tabs = self._create_tool_tabs()
        layout.addWidget(self.tool_tabs, 0)
        
        # 状态栏
        status_bar = self._create_status_bar()
        layout.addWidget(status_bar)
    
    def _create_title_bar(self) -> QFrame:
        """创建标题栏"""
        title_bar = QFrame()
        title_bar.setFixedHeight(52)
        title_bar.setStyleSheet("background: #252526; border-bottom: 1px solid #3E3E42;")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(16, 0, 16, 0)
        
        title_label = QLabel("💻 智能 IDE - 自动化开发平台")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF;")
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        # 语言选择
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("Python", "python")
        self.lang_combo.addItem("JavaScript", "javascript")
        self.lang_combo.addItem("TypeScript", "typescript")
        self.lang_combo.addItem("HTML", "html")
        self.lang_combo.addItem("CSS", "css")
        self.lang_combo.setStyleSheet("""
            QComboBox {
                background: #3E3E42;
                color: #FFFFFF;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QComboBox::dropDown {
                border: none;
            }
        """)
        title_layout.addWidget(self.lang_combo)
        
        # 运行按钮
        self.run_btn = QPushButton("▶️ 运行")
        self.run_btn.setFixedSize(100, 36)
        self.run_btn.setStyleSheet("""
            QPushButton {
                background: #0E639C;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover { background: #1177BB; }
            QPushButton:disabled { background: #555555; }
        """)
        title_layout.addWidget(self.run_btn)
        
        # AI 辅助按钮
        self.ai_btn = QPushButton("🤖 AI 辅助")
        self.ai_btn.setFixedSize(120, 36)
        self.ai_btn.setStyleSheet("""
            QPushButton {
                background: #4B0082;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover { background: #5A0099; }
        """)
        title_layout.addWidget(self.ai_btn)
        
        # 保存按钮
        self.save_btn = QPushButton("💾 保存")
        self.save_btn.setFixedSize(100, 36)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background: #0E639C;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover { background: #1177BB; }
        """)
        title_layout.addWidget(self.save_btn)
        
        # 打开按钮
        self.open_btn = QPushButton("📂 打开")
        self.open_btn.setFixedSize(100, 36)
        self.open_btn.setStyleSheet("""
            QPushButton {
                background: #0E639C;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover { background: #1177BB; }
        """)
        title_layout.addWidget(self.open_btn)
        
        return title_bar
    
    def _create_editor_area(self) -> QWidget:
        """创建编辑器区域"""
        editor_frame = QFrame()
        editor_frame.setStyleSheet("background: #1E1E1E;")
        editor_layout = QVBoxLayout(editor_frame)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        
        # 编辑器
        self.editor = CodeEditor()
        editor_layout.addWidget(self.editor)
        
        return editor_frame
    
    def _create_output_area(self) -> QWidget:
        """创建输出区域"""
        output_frame = QFrame()
        output_frame.setStyleSheet("background: #252526; border-left: 1px solid #3E3E42;")
        output_layout = QVBoxLayout(output_frame)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.setSpacing(0)
        
        # 输出标题
        output_title = QLabel("📤 输出")
        output_title.setStyleSheet("color: #FFFFFF; font-size: 12px; padding: 8px 12px; background: #2D2D30;")
        output_layout.addWidget(output_title)
        
        # 输出内容
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setStyleSheet("""
            QTextEdit {
                background: #252526;
                color: #D4D4D4;
                border: none;
                padding: 8px;
                font-family: Consolas, monospace;
                font-size: 12px;
            }
        """)
        output_layout.addWidget(self.output_text, 1)
        
        return output_frame
    
    def _create_tool_tabs(self) -> QTabWidget:
        """创建工具面板标签"""
        tool_tabs = QTabWidget()
        tool_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #3E3E42;
                background: #1E1E1E;
            }
            QTabBar::tab {
                background: #2D2D30;
                color: #D4D4D4;
                padding: 6px 12px;
                border: none;
            }
            QTabBar::tab:selected {
                background: #1E1E1E;
                color: #FFFFFF;
            }
        """)
        tool_tabs.setFixedHeight(300)
        
        # 搜索/替换面板
        self.search_panel = GlobalSearchPanel()
        self.search_panel.set_search_path(os.getcwd())
        tool_tabs.addTab(self.search_panel, "🔍 搜索")
        
        # 测试集成面板
        self.test_panel = TestIntegrationPanel()
        self.test_panel.set_test_path(os.getcwd())
        tool_tabs.addTab(self.test_panel, "🧪 测试")
        
        # Git 集成面板
        self.git_panel = GitIntegrationPanel()
        self.git_panel.set_repo_path(os.getcwd())
        tool_tabs.addTab(self.git_panel, "🔧 Git")
        
        return tool_tabs
    
    def _create_status_bar(self) -> QFrame:
        """创建状态栏"""
        status_bar = QFrame()
        status_bar.setFixedHeight(28)
        status_bar.setStyleSheet("background: #007ACC;")
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(12, 0, 12, 0)
        
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #FFFFFF; font-size: 11px;")
        status_layout.addWidget(self.status_label)
        
        status_layout.addStretch()
        
        self.cursor_label = QLabel("行 1, 列 1")
        self.cursor_label.setStyleSheet("color: #FFFFFF; font-size: 11px;")
        status_layout.addWidget(self.cursor_label)
        
        return status_bar
    
    def _connect_signals(self):
        """连接信号"""
        self.run_btn.clicked.connect(self._run_code)
        self.ai_btn.clicked.connect(self._request_ai_help)
        self.save_btn.clicked.connect(self._save_file)
        self.open_btn.clicked.connect(self._open_file)
        
        # 项目浏览器信号
        self.project_browser.file_double_clicked.connect(self._on_file_double_clicked)
    
    def _load_sample(self):
        """加载示例代码"""
        sample_code = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-

def greet(name: str) -> str:
    """问候函数"""
    return f"Hello, {name}!"

if __name__ == "__main__":
    # 测试代码
    print(greet("World"))
    print("智能 IDE 测试成功！")
'''
        self.editor.set_content(sample_code)
        self.status_label.setText("已加载示例代码")
    
    def _run_code(self):
        """运行代码（通过 Agent 真实执行）"""
        code = self.editor.get_content()
        language = self.lang_combo.currentData()
        
        if not code.strip():
            self.output_text.append("⚠️ 没有代码可运行\n")
            return
        
        # 更新状态
        self.status_label.setText(f"运行中 ({language})...")
        self.run_btn.setEnabled(False)
        self.run_btn.setText("运行中...")
        
        # 清空输出
        self.output_text.clear()
        
        # 启动工作线程（通过 Agent 执行代码）
        self.worker = CodeExecutionWorker(
            agent=self.agent,
            code=code,
            language=language,
        )
        self.worker.output.connect(self._on_output)
        self.worker.error.connect(self._on_error)
        self.worker.finished.connect(self._on_finished)
        self.worker.status.connect(self._on_status)
        self.worker.start()
        
        self.code_executed.emit(code, language)
    
    def _request_ai_help(self):
        """请求 AI 辅助（通过 Agent）"""
        code = self.editor.get_content()
        language = self.lang_combo.currentData()
        
        # 在输出面板显示
        self.output_text.append("🤖 正在请求 AI 辅助...\n")
        self.output_text.append("选择辅助类型：\n")
        self.output_text.append("1. 解释代码 (explain)\n")
        self.output_text.append("2. 调试代码 (debug)\n")
        self.output_text.append("3. 优化代码 (optimize)\n")
        self.output_text.append("4. 生成代码 (generate)\n")
        
        # TODO: 弹出对话框让用户选择辅助类型
        # 目前默认使用"解释代码"
        assist_type = "explain"
        
        # 启动 AI 辅助工作线程
        self.ai_worker = AIAssistWorker(
            agent=self.agent,
            code=code,
            language=language,
            assist_type=assist_type,
        )
        self.ai_worker.result_ready.connect(self._on_ai_result)
        self.ai_worker.error.connect(self._on_ai_error)
        self.ai_worker.finished.connect(self._on_ai_finished)
        self.ai_worker.start()
        
        self.ai_requested.emit(code)
    
    def _save_file(self):
        """保存文件"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存文件",
            "",
            "Python Files (*.py);;JavaScript Files (*.js);;TypeScript Files (*.ts);;HTML Files (*.html);;CSS Files (*.css);;All Files (*)",
        )
        
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self.editor.get_content())
                self.current_file = file_path
                self.status_label.setText(f"已保存: {file_path}")
            except Exception as e:
                QMessageBox.warning(self, "警告", f"保存失败: {e}")
    
    def _open_file(self):
        """打开文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "打开文件",
            "",
            "Python Files (*.py);;JavaScript Files (*.js);;TypeScript Files (*.ts);;HTML Files (*.html);;CSS Files (*.css);;All Files (*)",
        )
        
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.editor.set_content(content)
                self.current_file = file_path
                self.status_label.setText(f"已打开: {file_path}")
                
                # 自动检测语言
                if file_path.endswith(".py"):
                    self.lang_combo.setCurrentIndex(0)
                elif file_path.endswith(".js"):
                    self.lang_combo.setCurrentIndex(1)
                elif file_path.endswith(".ts"):
                    self.lang_combo.setCurrentIndex(2)
                elif file_path.endswith(".html"):
                    self.lang_combo.setCurrentIndex(3)
                elif file_path.endswith(".css"):
                    self.lang_combo.setCurrentIndex(4)
                
                # 刷新项目浏览器
                self.project_browser.refresh()
                
            except Exception as e:
                QMessageBox.warning(self, "警告", f"打开失败: {e}")
    
    def _on_file_double_clicked(self, file_path: str):
        """处理项目浏览器文件双击"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.editor.set_content(content)
            self.current_file = file_path
            self.status_label.setText(f"已打开: {file_path}")
            
            # 自动检测语言
            if file_path.endswith(".py"):
                self.lang_combo.setCurrentIndex(0)
            elif file_path.endswith(".js"):
                self.lang_combo.setCurrentIndex(1)
            elif file_path.endswith(".ts"):
                self.lang_combo.setCurrentIndex(2)
            elif file_path.endswith(".html"):
                self.lang_combo.setCurrentIndex(3)
            elif file_path.endswith(".css"):
                self.lang_combo.setCurrentIndex(4)
            
        except Exception as e:
            QMessageBox.warning(self, "警告", f"打开文件失败: {e}")
    
    @pyqtSlot(str)
    def _on_output(self, text: str):
        """收到输出"""
        self.output_text.append(text)
    
    @pyqtSlot(str)
    def _on_error(self, error_msg: str):
        """处理错误"""
        self.output_text.append(f"❌ 错误:\n{error_msg}\n")
        self.status_label.setText("运行出错")
    
    @pyqtSlot(int)
    def _on_finished(self, exit_code: int):
        """运行完成"""
        self.status_label.setText(f"运行完成 (退出码: {exit_code})")
        self.run_btn.setEnabled(True)
        self.run_btn.setText("▶️ 运行")
        self.worker = None
    
    @pyqtSlot(str)
    def _on_status(self, status: str):
        """状态更新"""
        self.status_label.setText(status)
    
    @pyqtSlot(str)
    def _on_ai_result(self, result: str):
        """收到 AI 辅助结果"""
        self.output_text.append("🤖 AI 辅助结果:\n")
        self.output_text.append(result)
        self.output_text.append("\n")
    
    @pyqtSlot(str)
    def _on_ai_error(self, error_msg: str):
        """AI 辅助错误"""
        self.output_text.append(f"❌ AI 辅助失败:\n{error_msg}\n")
    
    @pyqtSlot()
    def _on_ai_finished(self):
        """AI 辅助完成"""
        self.output_text.append("✅ AI 辅助完成\n")
        self.ai_worker = None
    
    def closeEvent(self, event):
        """关闭事件"""
        if self.worker and self.worker.isRunning():
            self.worker.wait()
        if self.ai_worker and self.ai_worker.isRunning():
            self.ai_worker.wait()
        super().closeEvent(event)


# ── 测试 ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow
    
    app = QApplication(sys.argv)
    
    window = QMainWindow()
    window.setWindowTitle("智能 IDE - 自动化开发平台")
    window.setGeometry(100, 100, 1400, 900)
    
    central_widget = QWidget()
    window.setCentralWidget(central_widget)
    
    layout = QVBoxLayout(central_widget)
    
    ide_panel = Panel()
    layout.addWidget(ide_panel)
    
    window.show()
    sys.exit(app.exec())
