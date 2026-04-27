"""
EIWizard - 环评报告生成向导（极简聊天界面）
===============================================

采用自我学习策略 + 极简聊天界面设计。

设计理念：
1. 极简 UI - 类似 ChatGPT 的聊天界面
2. 对话式需求澄清 - Agent 通过对话引导用户输入
3. 自我学习 - 不预置判断逻辑，让 Agent 自己学习

Author: LivingTreeAI Agent
Date: 2026-04-27
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QScrollArea, QWidget, QLabel, QTextEdit, QPushButton,
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QFont, QIcon

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class MessageBubble(QWidget):
    """消息气泡组件"""
    
    def __init__(self, role: str, content: str = "", parent=None):
        """
        初始化消息气泡
        
        Args:
            role: 'user' 或 'assistant'
            content: 消息内容
            parent: 父组件
        """
        super().__init__(parent)
        self.role = role
        self.content = content
        self.init_ui()
    
    def init_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 5, 10, 5)
        
        # 创建气泡标签
        self.bubble_label = QLabel(self.content)
        self.bubble_label.setWordWrap(True)
        self.bubble_label.setMaximumWidth(600)
        self.bubble_label.setStyleSheet(self._get_bubble_style())
        
        if self.role == 'user':
            # 用户消息：右侧，蓝色背景
            layout.addStretch()
            layout.addWidget(self.bubble_label)
        else:
            # 助手消息：左侧，灰色背景
            layout.addWidget(self.bubble_label)
            layout.addStretch()
        
        self.setLayout(layout)
    
    def _get_bubble_style(self) -> str:
        """获取气泡样式"""
        if self.role == 'user':
            return """
                QLabel {
                    background-color: #0078d4;
                    color: white;
                    border-radius: 10px;
                    padding: 10px;
                    font-size: 14px;
                }
            """
        else:
            return """
                QLabel {
                    background-color: #f0f0f0;
                    color: #333;
                    border-radius: 10px;
                    padding: 10px;
                    font-size: 14px;
                }
            """
    
    def update_content(self, content: str):
        """更新消息内容（用于流式输出）"""
        self.content = content
        self.bubble_label.setText(content)


class EIWizardChat(QWidget):
    """
    环评报告生成向导（极简聊天界面）
    
    采用对话式需求澄清：
    1. Agent 询问用户需求
    2. 用户回复
    3. Agent 分析问题，引导用户提供更多信息
    4. 自动调用工具完成任务
    """
    
    # 信号
    task_started = Signal(str)  # 任务开始（任务ID）
    task_completed = Signal(dict)  # 任务完成（结果）
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.message_history = []
        self.current_assistant_bubble = None
        self.agent_available = False
        
        # 初始化 Agent
        self._init_agent()
        
        # 初始化 UI
        self.init_ui()
        
        # 显示欢迎消息
        self._show_welcome()
    
    def _init_agent(self):
        """初始化 EIAgent"""
        try:
            from client.src.business.ei_agent.ei_agent_adapter import (
                get_ei_agent_adapter,
                submit_ei_task,
            )
            self.adapter = get_ei_agent_adapter()
            self.submit_task = submit_ei_task
            self.agent_available = True
            logger.info("[EIWizardChat] EIAgent 初始化成功")
        except Exception as e:
            logger.warning(f"[EIWizardChat] EIAgent 初始化失败: {e}")
            self.adapter = None
            self.submit_task = None
    
    def init_ui(self):
        """初始化 UI（极简设计）"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 1. 聊天历史显示区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #fafafa;
                border: none;
            }
        """)
        
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_layout.addStretch()
        
        self.scroll_area.setWidget(self.scroll_content)
        layout.addWidget(self.scroll_area, 1)
        
        # 2. 输入区域（极简）
        input_container = QWidget()
        input_container.setStyleSheet("""
            QWidget {
                background-color: white;
                border-top: 1px solid #e0e0e0;
            }
        """)
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(10, 10, 10, 10)
        
        # 消息输入框
        self.message_input = QTextEdit()
        self.message_input.setMaximumHeight(80)
        self.message_input.setPlaceholderText("输入你的需求，我会帮你生成环评报告...")
        self.message_input.setStyleSheet("""
            QTextEdit {
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                padding: 8px;
                font-size: 14px;
                background-color: #fafafa;
            }
            QTextEdit:focus {
                border: 1px solid #0078d4;
            }
        """)
        
        # Ctrl+Enter 发送
        # 注意：PySide6 的快捷键设置需要额外处理
        
        input_layout.addWidget(self.message_input, 1)
        
        # 发送按钮
        self.send_btn = QPushButton("发送")
        self.send_btn.setFixedSize(80, 40)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.send_btn.clicked.connect(self._send_message)
        input_layout.addWidget(self.send_btn)
        
        layout.addWidget(input_container)
        
        self.setLayout(layout)
    
    def _show_welcome(self):
        """显示欢迎消息"""
        welcome_text = """👋 你好！我是环评助手。

我可以帮你：
- 📄 生成环评报告
- 🔍 查询环保法规
- 📊 计算污染物排放
- 🗺️ 分析环境敏感点
- 📝 学习 Word 模板格式

请告诉我你需要什么帮助？"""
        
        self._add_message('assistant', welcome_text)
    
    def _send_message(self):
        """发送消息"""
        message = self.message_input.toPlainText().strip()
        if not message:
            return
        
        # 显示用户消息
        self._add_message('user', message)
        
        # 清空输入框
        self.message_input.clear()
        
        # 处理消息
        self._process_message(message)
    
    def _process_message(self, message: str):
        """处理用户消息（调用 Agent）"""
        if not self.agent_available:
            self._add_message('assistant', "⚠️ EIAgent 不可用，请检查系统配置。")
            return
        
        # 显示"正在思考"提示
        self._add_message('assistant', "🤔 正在思考...")
        
        # 调用 Agent（异步）
        try:
            # 提交任务给 EIAgent
            task_id = self.submit_task(
                task_type="report_generation",  # 默认任务类型
                params={"message": message}
            )
            
            # 启动定时器，轮询任务状态
            self._check_task_status(task_id)
            
        except Exception as e:
            logger.error(f"[EIWizardChat] 调用 Agent 失败: {e}")
            self._update_last_assistant_message(f"❌ 调用失败: {str(e)}")
    
    def _check_task_status(self, task_id: str):
        """检查任务状态（简化实现）"""
        # 这里应该使用异步方式检查任务状态
        # 简化实现：直接显示"任务已提交"
        self._update_last_assistant_message(
            f"✅ 任务已提交（ID: {task_id}）\n\n正在处理中..."
        )
        
        # TODO: 实现异步任务状态轮询
        # 可以使用 QTimer 定时检查
    
    def _add_message(self, role: str, content: str):
        """添加消息到聊天历史"""
        self.message_history.append({'role': role, 'content': content})
        
        # 创建消息气泡
        bubble = MessageBubble(role, content)
        self.scroll_layout.insertWidget(self.scroll_layout.count() - 1, bubble)
        
        # 如果是助手消息，保存引用（用于更新）
        if role == 'assistant':
            self.current_assistant_bubble = bubble
        
        # 滚动到底部
        self._scroll_to_bottom()
    
    def _update_last_assistant_message(self, content: str):
        """更新最后一个助手消息（用于流式输出）"""
        if self.current_assistant_bubble:
            self.current_assistant_bubble.update_content(content)
        else:
            self._add_message('assistant', content)
    
    def _scroll_to_bottom(self):
        """滚动到底部"""
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def append_stream_chunk(self, chunk: str):
        """追加流式输出内容"""
        if not self.current_assistant_bubble:
            self._add_message('assistant', chunk)
        else:
            current_content = self.current_assistant_bubble.content
            self.current_assistant_bubble.update_content(current_content + chunk)
    
    def clear_history(self):
        """清空聊天历史"""
        # 删除所有消息气泡
        while self.scroll_layout.count() > 1:  # 保留最后的 stretch
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.message_history = []
        self.current_assistant_bubble = None
        
        # 显示欢迎消息
        self._show_welcome()


# ============================================================
# 主窗口（可选，用于独立运行）
# ============================================================

class EIWizardWindow(QWidget):
    """EIWizard 主窗口（极简设计）"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("环评助手")
        self.setMinimumSize(800, 600)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # 标题栏（极简）
        title_bar = QWidget()
        title_bar.setStyleSheet("""
            QWidget {
                background-color: #0078d4;
                color: white;
                padding: 10px;
            }
        """)
        title_layout = QHBoxLayout(title_bar)
        title_label = QLabel("环评助手")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        # 清空按钮
        clear_btn = QPushButton("清空")
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: white;
                border: 1px solid white;
                border-radius: 3px;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.2);
            }
        """)
        clear_btn.clicked.connect(self._clear_chat)
        title_layout.addWidget(clear_btn)
        
        layout.addWidget(title_bar)
        
        # 聊天界面
        self.chat_widget = EIWizardChat()
        layout.addWidget(self.chat_widget, 1)
        
        self.setLayout(layout)
    
    def _clear_chat(self):
        """清空聊天历史"""
        self.chat_widget.clear_history()


if __name__ == '__main__':
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    window = EIWizardWindow()
    window.show()
    sys.exit(app.exec())
