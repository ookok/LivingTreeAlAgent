#!/usr/bin/env python
"""
完整测试聊天面板显示
"""

import sys
sys.path.insert(0, 'client/src')

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QFrame, QLabel, QTextEdit, QPushButton,
    QScrollArea, QToolButton
)
from PyQt6.QtCore import Qt

def create_test_chat_panel():
    """创建测试聊天面板"""
    panel = QWidget()
    chat_layout = QVBoxLayout(panel)
    chat_layout.setContentsMargins(0, 0, 0, 0)
    
    # 标题栏
    title_bar = QFrame()
    title_bar.setFixedHeight(52)
    title_bar.setStyleSheet("background: #44475a; border-bottom: 1px solid #282a36;")
    title_layout = QHBoxLayout(title_bar)
    title_layout.setContentsMargins(16, 0, 16, 0)
    
    title_label = QLabel("💬 智能对话")
    title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #f8f8f2;")
    title_layout.addWidget(title_label)
    
    model_label = QLabel("Model: deepseek-v4-flash")
    model_label.setStyleSheet("font-size: 12px; color: #bd93f9;")
    title_layout.addWidget(model_label)
    
    title_layout.addStretch()
    chat_layout.addWidget(title_bar)
    
    # 消息区域
    scroll_area = QScrollArea()
    scroll_area.setWidgetResizable(True)
    scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll_area.setStyleSheet("""
        QScrollArea { 
            border: none; 
            background: #282a36; 
        }
        QScrollArea QWidget {
            background: #282a36;
        }
    """)
    
    messages_container = QWidget()
    messages_container.setStyleSheet("background: #282a36;")
    messages_layout = QVBoxLayout(messages_container)
    messages_layout.setContentsMargins(16, 16, 16, 16)
    
    # 添加测试消息
    def add_message(role, content):
        bubble = QFrame()
        bubble.setStyleSheet(f"""
            QFrame {{
                background: {'#6272a4' if role == 'user' else '#44475a'};
                border-radius: 12px;
                margin-left: {'40px' if role == 'user' else '0'};
                margin-right: {'0' if role == 'user' else '40px'};
                padding: 12px;
            }}
        """)
        
        bubble_layout = QVBoxLayout(bubble)
        role_label = QLabel("🧑 用户" if role == "user" else "🤖 助手")
        role_label.setStyleSheet("font-size: 11px; color: #bd93f9; font-weight: bold;")
        bubble_layout.addWidget(role_label)
        
        content_label = QLabel(content)
        content_label.setWordWrap(True)
        content_label.setStyleSheet("font-size: 14px; color: #f8f8f2;")
        bubble_layout.addWidget(content_label)
        
        messages_layout.addWidget(bubble)
    
    add_message('user', '你好！')
    add_message('assistant', '你好！我是 LivingTree AI Agent，很高兴为你服务。')
    add_message('user', '我怎么用脚本一键下载安装ollama？')
    
    messages_layout.addStretch()
    scroll_area.setWidget(messages_container)
    chat_layout.addWidget(scroll_area, 1)
    
    # 输入区域
    input_frame = QFrame()
    input_frame.setStyleSheet("background: #44475a; border-top: 1px solid #44475a;")
    input_layout = QHBoxLayout(input_frame)
    input_layout.setContentsMargins(16, 12, 16, 12)
    
    command_btn = QToolButton()
    command_btn.setText("/")
    command_btn.setStyleSheet("""
        QToolButton {
            background-color: #6272a4;
            color: #f8f8f2;
            border: none;
            border-radius: 8px;
            padding: 8px 12px;
            font-size: 14px;
            font-weight: bold;
        }
        QToolButton:hover {
            background-color: #bd93f9;
            color: #282a36;
        }
    """)
    input_layout.addWidget(command_btn)
    
    input_field = QTextEdit()
    input_field.setPlaceholderText("输入消息...")
    input_field.setMaximumHeight(100)
    input_field.setStyleSheet("""
        QTextEdit {
            background-color: #282a36;
            color: #f8f8f2;
            border: 2px solid #44475a;
            border-radius: 8px;
            padding: 8px 12px;
            font-size: 14px;
        }
        QTextEdit:focus {
            border-color: #bd93f9;
        }
    """)
    input_layout.addWidget(input_field, 1)
    
    send_btn = QPushButton("发送")
    send_btn.setFixedSize(80, 40)
    send_btn.setStyleSheet("""
        QPushButton {
            background: #bd93f9;
            color: #282a36;
            border: none;
            border-radius: 8px;
            font-weight: bold;
        }
        QPushButton:hover { background: #ff79c6; }
        QPushButton:disabled { background: #44475a; color: #6272a4; }
    """)
    input_layout.addWidget(send_btn)
    
    chat_layout.addWidget(input_frame)
    
    return panel

def main():
    app = QApplication(sys.argv)
    
    # 设置全局样式
    app.setStyleSheet("""
        QMainWindow {
            background-color: #282a36;
        }
    """)
    
    # 创建主窗口
    window = QMainWindow()
    window.setWindowTitle("Chat Panel Test")
    window.resize(1000, 700)
    
    # 创建中心部件
    central_widget = QWidget()
    layout = QVBoxLayout(central_widget)
    layout.setContentsMargins(0, 0, 0, 0)
    
    # 添加聊天面板
    chat_panel = create_test_chat_panel()
    layout.addWidget(chat_panel)
    
    window.setCentralWidget(central_widget)
    
    # 显示窗口
    window.show()
    
    print('🎉 聊天面板测试窗口已显示')
    print('💡 按 Ctrl+C 或关闭窗口退出')
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()