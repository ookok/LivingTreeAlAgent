#!/usr/bin/env python
"""
简单测试聊天面板显示
"""

import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QTextEdit, QPushButton
from PyQt6.QtCore import Qt

app = QApplication(sys.argv)

# 设置全局样式
app.setStyleSheet("""
    QMainWindow { background-color: #282a36; }
    QWidget { background-color: #282a36; color: #f8f8f2; }
    QLabel { color: #f8f8f2; }
    QTextEdit { 
        background-color: #44475a; 
        color: #f8f8f2; 
        border: 2px solid #6272a4; 
        border-radius: 8px;
        padding: 8px;
    }
    QPushButton {
        background-color: #bd93f9;
        color: #282a36;
        border: none;
        border-radius: 8px;
        padding: 8px 16px;
        font-weight: bold;
    }
""")

# 创建主窗口
window = QMainWindow()
window.setWindowTitle("Simple Chat Test")
window.resize(800, 600)

# 创建中心部件
central_widget = QWidget()
layout = QVBoxLayout(central_widget)

# 添加标题
title_label = QLabel("💬 智能对话")
title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #bd93f9; margin: 16px;")
layout.addWidget(title_label)

# 添加消息显示区域
msg_area = QTextEdit()
msg_area.setReadOnly(True)
msg_area.setStyleSheet("""
    QTextEdit {
        background-color: #282a36;
        color: #f8f8f2;
        border: 2px solid #44475a;
        border-radius: 8px;
        padding: 12px;
        font-size: 14px;
    }
""")
msg_area.append("🤖 你好！我是 LivingTree AI Agent")
msg_area.append("")
msg_area.append("🧑 我怎么用脚本一键下载安装ollama？")
layout.addWidget(msg_area, 1)

# 添加输入区域
input_field = QTextEdit()
input_field.setMaximumHeight(60)
input_field.setPlaceholderText("输入消息...")
layout.addWidget(input_field)

# 添加发送按钮
send_btn = QPushButton("发送")
layout.addWidget(send_btn)

window.setCentralWidget(central_widget)

# 显示窗口
window.show()
window.activateWindow()
window.raise_()

print("🎉 测试窗口已显示")
sys.exit(app.exec())