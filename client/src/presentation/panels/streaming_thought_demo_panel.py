"""
共脑系统 Demo - StreamingThoughtExecutor 实时思考展示
PyQt6 UI 界面
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QLabel, QGroupBox, QListWidget,
    QListWidgetItem, QMessageBox, QSplitter,
    QProgressBar
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QTextCursor, QColor

logger = logging.getLogger(__name__)


# ============= 信号桥接（解决 async -> Qt 通信问题） =============

class ChunkSignalBridge(QObject):
    """将异步生成器的 chunk 转发为 Qt 信号"""
    
    chunk_received = pyqtSignal(dict)
    finished = pyqtSignal()
    error = pyqtSignal(str)


# ============= 高亮器（思考/动作/结果不同颜色） =============

class ThoughtHighlighter(QSyntaxHighlighter):
    """思考文本高亮器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 思考文本格式（灰色，斜体）
        self.thought_format = QTextCharFormat()
        self.thought_format.setForeground(QColor(150, 150, 150))
        self.thought_format.setFontItalic(True)
        
        # 动作文本格式（蓝色）
        self.action_format = QTextCharFormat()
        self.action_format.setForeground(QColor(0, 100, 200))
        self.action_format.setFontWeight(QFont.Weight.Bold)
        
        # 结果文本格式（绿色）
        self.result_format = QTextCharFormat()
        self.result_format.setForeground(QColor(0, 150, 0))
        
        # 错误文本格式（红色）
        self.error_format = QTextCharFormat()
        self.error_format.setForeground(QColor(200, 0, 0))
        self.error_format.setFontWeight(QFont.Weight.Bold)
    
    def highlightBlock(self, text: str):
        """高亮文本块"""
        # 这里简化实现，实际高亮由 append_formatted_text() 处理
        pass


# ============= 共脑系统 Demo 面板 =============

class StreamingThoughtDemoPanel(QWidget):
    """
    共脑系统 Demo 面板
    
    功能：
    1. 用户输入意图
    2. 实时显示思考过程（流式）
    3. 实时显示动作执行状态
    4. 显示最终结果
    """
    
    def __init__(self, model_router=None, parent=None):
        super().__init__(parent)
        
        self.model_router = model_router
        self.executor = None
        self.current_task = None  # 当前运行的异步任务
        
        # 模拟演示数据
        self.demo_thoughts = [
            "思考：用户想要查询天气信息，我需要调用 weather 动作...",
            "思考：用户还想要计算 2+2，我需要调用 calculate 动作...",
            "思考：已获取所有必要信息，可以给出最终答案了...",
        ]
        
        self.demo_actions = [
            {"type": "weather", "status": "running", "result": "", "error": ""},
            {"type": "weather", "status": "success", "result": "北京今天晴天，温度 20-25 度", "error": ""},
            {"type": "calculate", "status": "running", "result": "", "error": ""},
            {"type": "calculate", "status": "success", "result": "计算结果: 2+2 = 4", "error": ""},
        ]
        
        self.demo_final = {
            "summary": "已成功查询天气并计算结果",
            "full_result": {
                "executed_actions": ["weather", "calculate"],
                "weather_result": "北京今天晴天，温度 20-25 度",
                "calc_result": "2+2 = 4",
            }
        }
        
        # 模拟演示定时器
        self.demo_timer = QTimer()
        self.demo_timer.timeout.connect(self._demo_step)
        self.demo_step_index = 0
        self.demo_steps = []  # 存储所有演示步骤
        
        self._init_ui()
        self._init_executor()
    
    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 标题
        title = QLabel("🧠 共脑系统 Demo - 实时思考展示")
        title.setStyleSheet("font-size: 18px; font-weight: bold; padding: 10px;")
        layout.addWidget(title)
        
        # 说明文字
        desc = QLabel("输入你的意图，观察 AI 的实时思考过程和动作执行")
        desc.setStyleSheet("color: gray; padding: 5px;")
        layout.addWidget(desc)
        
        # 分隔线
        layout.addWidget(self._create_separator())
        
        # 输入区域
        input_group = QGroupBox("📝 输入区域")
        input_layout = QVBoxLayout(input_group)
        
        # 意图输入框
        self.intent_input = QTextEdit()
        self.intent_input.setPlaceholderText("输入你的意图，例如：帮我查一下今天的天气，然后计算 2+2，最后总结")
        self.intent_input.setMaximumHeight(80)
        input_layout.addWidget(self.intent_input)
        
        # 上下文输入（可选）
        context_layout = QHBoxLayout()
        context_layout.addWidget(QLabel("上下文 (JSON，可选):"))
        self.context_input = QTextEdit()
        self.context_input.setPlaceholderText('{"user_location": "北京"}')
        self.context_input.setMaximumHeight(50)
        context_layout.addWidget(self.context_input)
        input_layout.addLayout(context_layout)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        self.execute_btn = QPushButton("🚀 开始执行")
        self.execute_btn.clicked.connect(self._on_execute_clicked)
        self.execute_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 8px;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:disabled { background-color: #cccccc; }
        """)
        button_layout.addWidget(self.execute_btn)
        
        # 模拟演示按钮
        self.demo_btn = QPushButton("🎭 模拟演示")
        self.demo_btn.clicked.connect(self._on_demo_clicked)
        self.demo_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                padding: 8px;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #0b7dda; }
        """)
        button_layout.addWidget(self.demo_btn)
        
        self.clear_btn = QPushButton("🗑️ 清空")
        self.clear_btn.clicked.connect(self._on_clear_clicked)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                padding: 8px;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #da190b; }
        """)
        button_layout.addWidget(self.clear_btn)
        
        button_layout.addStretch()
        input_layout.addLayout(button_layout)
        
        layout.addWidget(input_group)
        
        # 分隔线
        layout.addWidget(self._create_separator())
        
        # 输出区域（使用分割器）
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # 1. 思考过程展示区
        thought_group = QGroupBox("💭 思考过程 (实时)")
        thought_layout = QVBoxLayout(thought_group)
        self.thought_display = QTextEdit()
        self.thought_display.setReadOnly(True)
        self.thought_display.setStyleSheet("""
            QTextEdit {
                background-color: #f5f5f5;
                font-family: 'Consolas', 'Microsoft YaHei';
                font-size: 13px;
            }
        """)
        thought_layout.addWidget(self.thought_display)
        splitter.addWidget(thought_group)
        
        # 2. 动作执行展示区
        action_group = QGroupBox("⚡ 动作执行 (实时)")
        action_layout = QVBoxLayout(action_group)
        self.action_list = QListWidget()
        self.action_list.setStyleSheet("""
            QListWidget {
                background-color: #f0f8ff;
                font-family: 'Consolas', 'Microsoft YaHei';
                font-size: 12px;
            }
        """)
        action_layout.addWidget(self.action_list)
        splitter.addWidget(action_group)
        
        # 3. 最终结果展示区
        result_group = QGroupBox("✅ 最终结果")
        result_layout = QVBoxLayout(result_group)
        self.result_display = QTextEdit()
        self.result_display.setReadOnly(True)
        self.result_display.setMaximumHeight(150)
        self.result_display.setStyleSheet("""
            QTextEdit {
                background-color: #f0fff0;
                font-family: 'Consolas', 'Microsoft YaHei';
                font-size: 13px;
            }
        """)
        result_layout.addWidget(self.result_display)
        splitter.addWidget(result_group)
        
        # 设置分割器比例
        splitter.setStretchFactor(0, 3)  # 思考过程占 3 份
        splitter.setStretchFactor(1, 2)  # 动作执行占 2 份
        splitter.setStretchFactor(2, 1)  # 最终结果占 1 份
        
        layout.addWidget(splitter)
        
        # 状态栏
        status_layout = QHBoxLayout()
        
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: gray;")
        status_layout.addWidget(self.status_label)
        
        status_layout.addStretch()
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # 不确定模式
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(200)
        status_layout.addWidget(self.progress_bar)
        
        layout.addLayout(status_layout)
    
    def _create_separator(self) -> QWidget:
        """创建分隔线"""
        separator = QWidget()
        separator.setFixedHeight(2)
        separator.setStyleSheet("background-color: #e0e0e0;")
        return separator
    
    def _init_executor(self):
        """初始化流式执行器"""
        try:
            from client.src.business.streaming_thought_executor import (
                create_streaming_executor,
                DefaultActionExecutor
            )
            
            if self.model_router is None:
                from client.src.business.global_model_router import get_global_router
                self.model_router = get_global_router()
            
            action_executor = DefaultActionExecutor().execute
            self.executor = create_streaming_executor(self.model_router, action_executor)
            
            logger.info("StreamingThoughtExecutor 初始化成功")
        
        except Exception as e:
            logger.error(f"初始化 StreamingThoughtExecutor 失败: {e}")
            self.executor = None
    
    def _on_execute_clicked(self):
        """执行按钮点击"""
        if self.executor is None:
            QMessageBox.warning(self, "警告", "执行器未初始化，请检查模型配置")
            return
        
        intent = self.intent_input.toPlainText().strip()
        if not intent:
            QMessageBox.warning(self, "警告", "请输入意图")
            return
        
        # 解析上下文
        context = {}
        context_text = self.context_input.toPlainText().strip()
        if context_text:
            try:
                context = json.loads(context_text)
            except json.JSONDecodeError as e:
                QMessageBox.warning(self, "警告", f"上下文 JSON 格式错误: {e}")
                return
        
        # 停止可能正在运行的模拟演示
        self._stop_demo()
        
        # 清空之前的输出
        self.thought_display.clear()
        self.action_list.clear()
        self.result_display.clear()
        
        # 更新 UI 状态
        self.execute_btn.setEnabled(False)
        self.status_label.setText("正在执行...")
        self.progress_bar.setVisible(True)
        
        # 启动异步执行
        self._start_async_execution(intent, context)
    
    def _on_demo_clicked(self):
        """模拟演示按钮点击"""
        # 停止可能正在运行的演示
        self._stop_demo()
        
        # 清空之前的输出
        self.thought_display.clear()
        self.action_list.clear()
        self.result_display.clear()
        
        # 设置默认输入
        self.intent_input.setPlainText("帮我查一下今天的天气，然后计算 2+2，最后总结")
        self.context_input.setPlainText('{"user_location": "北京"}')
        
        # 更新 UI 状态
        self.execute_btn.setEnabled(False)
        self.demo_btn.setEnabled(False)
        self.status_label.setText("模拟演示中...")
        self.progress_bar.setVisible(True)
        
        # 准备演示步骤
        self.demo_steps = []
        
        # 添加思考步骤
        for thought in self.demo_thoughts:
            self.demo_steps.append({"type": "thought", "content": thought + "\n"})
        
        # 添加动作步骤
        for action in self.demo_actions:
            self.demo_steps.append({"type": "action", "data": action})
        
        # 添加最终步骤
        self.demo_steps.append({"type": "final", "data": self.demo_final})
        
        # 启动演示
        self.demo_step_index = 0
        self.demo_timer.start(800)  # 每 800ms 执行一步
    
    def _demo_step(self):
        """演示步骤（由定时器调用）"""
        if self.demo_step_index >= len(self.demo_steps):
            # 演示完成
            self._stop_demo()
            return
        
        step = self.demo_steps[self.demo_step_index]
        step_type = step["type"]
        
        # 根据步骤类型处理
        if step_type == "thought":
            # 显示思考片段
            content = step["content"]
            self._append_thought(content)
        
        elif step_type == "action":
            # 显示动作执行
            data = step["data"]
            self._append_action(
                data["type"],
                data["status"],
                data.get("result", ""),
                data.get("error", "")
            )
        
        elif step_type == "final":
            # 显示最终结果
            data = step["data"]
            self._show_final_result(data)
        
        # 下一步
        self.demo_step_index += 1
    
    def _stop_demo(self):
        """停止演示"""
        self.demo_timer.stop()
        
        self.execute_btn.setEnabled(True)
        self.demo_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText("模拟演示完成")
        self.status_label.setStyleSheet("color: #008000;")
    
    def _start_async_execution(self, intent: str, context: Dict[str, Any]):
        """启动异步执行"""
        try:
            # 创建事件循环（如果在主线程中）
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # 创建任务
            task = loop.create_task(self._run_execution(intent, context))
            self.current_task = task
        
        except Exception as e:
            logger.error(f"启动异步执行失败: {e}")
            self._on_execution_finished(error=str(e))
    
    async def _run_execution(self, intent: str, context: Dict[str, Any]):
        """运行执行（异步）"""
        try:
            # 用于收集最终结果
            final_result = None
            all_thoughts = []
            
            # 流式执行
            async for chunk in self.executor.execute_stream(intent, context):
                chunk_type = chunk.get("type")
                
                # 1. 处理思考片段
                if chunk_type == "thought":
                    content = chunk.get("content", "")
                    if content:
                        self._append_thought(content)
                        all_thoughts.append(content)
                
                # 2. 处理动作片段
                elif chunk_type == "action":
                    action_type = chunk.get("action_type", "")
                    status = chunk.get("status", "")
                    result = chunk.get("result", "")
                    error = chunk.get("error", "")
                    
                    self._append_action(action_type, status, result, error)
                
                # 3. 处理最终总结
                elif chunk_type == "final":
                    summary = chunk.get("summary", "")
                    full_result = chunk.get("full_result", {})
                    
                    final_result = {
                        "summary": summary,
                        "full_result": full_result,
                        "all_thoughts": "".join(all_thoughts),
                    }
                    
                    self._show_final_result(final_result)
                
                # 4. 处理错误
                elif chunk_type == "error":
                    error = chunk.get("error", "")
                    self._append_thought(f"\n[错误] {error}\n", is_error=True)
            
            # 执行完成
            self._on_execution_finished()
        
        except Exception as e:
            logger.error(f"执行异常: {e}")
            self._on_execution_finished(error=str(e))
    
    def _append_thought(self, text: str, is_error: bool = False):
        """追加思考文本"""
        cursor = self.thought_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        if is_error:
            # 错误文本（红色）
            cursor.insertHtml(f'<span style="color: #ff0000;">{text}</span>')
        else:
            # 思考文本（灰色，斜体）
            cursor.insertHtml(f'<span style="color: #888888; font-style: italic;">{text}</span>')
        
        # 滚动到底部
        self.thought_display.setTextCursor(cursor)
        self.thought_display.ensureCursorVisible()
    
    def _append_action(self, action_type: str, status: str, result: str = "", error: str = ""):
        """追加动作执行信息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # 根据状态选择图标和颜色
        if status == "running":
            icon = "⏳"
            color = "#0000ff"
            text = f"[{timestamp}] {icon} 执行动作: {action_type}..."
        
        elif status == "success":
            icon = "✅"
            color = "#008000"
            text = f"[{timestamp}] {icon} 动作完成: {action_type}"
            if result:
                text += f"\n    结果: {result}"
        
        elif status == "failed":
            icon = "❌"
            color = "#ff0000"
            text = f"[{timestamp}] {icon} 动作失败: {action_type}"
            if error:
                text += f"\n    错误: {error}"
        
        else:
            icon = "❓"
            color = "#888888"
            text = f"[{timestamp}] {icon} 未知状态: {action_type}"
        
        # 添加到列表
        item = QListWidgetItem(text)
        item.setForeground(QColor(color))
        self.action_list.addItem(item)
        
        # 滚动到底部
        self.action_list.scrollToBottom()
    
    def _show_final_result(self, result: Dict[str, Any]):
        """显示最终结果"""
        summary = result.get("summary", "")
        full_result = result.get("full_result", {})
        
        html = f"""
        <h3>✅ 执行完成</h3>
        <p><b>总结:</b> {summary}</p>
        <hr>
        <p><b>详细信息:</b></p>
        <pre>{json.dumps(full_result, indent=2, ensure_ascii=False)}</pre>
        """
        
        self.result_display.setHtml(html)
    
    def _on_execution_finished(self, error: str = ""):
        """执行完成"""
        self.execute_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        if error:
            self.status_label.setText(f"执行失败: {error}")
            self.status_label.setStyleSheet("color: #ff0000;")
        else:
            self.status_label.setText("执行完成")
            self.status_label.setStyleSheet("color: #008000;")
        
        self.current_task = None
    
    def _on_clear_clicked(self):
        """清空按钮点击"""
        # 停止模拟演示
        self._stop_demo()
        
        # 清空输入和输出
        self.intent_input.clear()
        self.context_input.clear()
        self.thought_display.clear()
        self.action_list.clear()
        self.result_display.clear()
        self.status_label.setText("就绪")
        self.status_label.setStyleSheet("color: gray;")
        
        # 如果有正在执行的任务，取消它
        if self.current_task and not self.current_task.done():
            self.current_task.cancel()
            self.current_task = None


# ============= 独立窗口（用于测试） =============

class StreamingThoughtDemoWindow(QWidget):
    """共脑系统 Demo 独立窗口"""
    
    def __init__(self, model_router=None, parent=None):
        super().__init__(parent)
        
        self.setWindowTitle("共脑系统 Demo - 实时思考展示")
        self.setMinimumSize(1000, 700)
        
        layout = QVBoxLayout(self)
        
        # 创建 Demo 面板
        self.demo_panel = StreamingThoughtDemoPanel(model_router, self)
        layout.addWidget(self.demo_panel)
        
        # 设置样式
        self.setStyleSheet("""
            QWidget {
                font-family: 'Microsoft YaHei', 'Segoe UI';
                font-size: 14px;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)


# ============= 测试入口 =============

if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    window = StreamingThoughtDemoWindow()
    window.show()
    
    sys.exit(app.exec())
