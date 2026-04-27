"""
FileCard 演示 - 文件智能展示组件

本模块演示如何使用聊天界面文件智能展示功能。

使用示例:

1. 单文件卡片
    from ui.unified_chat.chat_panel import FileCard

    card = FileCard(
        file_path="C:/Users/test/report.pdf",
        file_name="年度报告.pdf",
        file_size=1024 * 1024 * 2.5,  # 2.5 MB
        operations=["open", "show_in_folder", "copy_path"]
    )

2. 多文件卡片
    from ui.unified_chat.chat_panel import MultiFileCard

    files = [
        {"path": "C:/Users/test/report.pdf", "name": "年度报告.pdf", "size": 2621440},
        {"path": "C:/Users/test/data.xlsx", "name": "数据表格.xlsx", "size": 524288},
        {"path": "C:/Users/test/analyze.py", "name": "分析脚本.py", "size": 8192},
    ]
    multi_card = MultiFileCard(files=files)

3. 创建文件消息内容 (用于消息气泡)
    from ui.unified_chat.chat_panel import create_file_message_content

    content = create_file_message_content(files, "已为您生成以下文件:")
    # 返回格式化的 Markdown 文本

4. 文件操作工具函数
    from ui.unified_chat.chat_panel import (
        open_file_with_default_app,
        show_file_in_folder,
        copy_file_path_to_clipboard
    )

    open_file_with_default_app("C:/Users/test/report.pdf")  # 打开文件
    show_file_in_folder("C:/Users/test/report.pdf")          # 在文件夹中显示
    copy_file_path_to_clipboard("C:/Users/test/report.pdf")  # 复制路径

5. 文件类型工具
    from ui.unified_chat.chat_panel import get_file_icon, get_file_category

    icon = get_file_icon("data.xlsx")      # 返回 "📊"
    category = get_file_category("data.xlsx")  # 返回 "📊 表格文件"

支持的图标类型:
    文档: 📄📝📃📋📚
    表格: 📊
    演示: 🎨
    代码: 🐍🌐☕⚙️💜🔵🦀💎🐘🍎🤖⚛️💚
    配置: ⚙️🔐📁
    数据: 💾📦
    图片: 🖼️🎞️📈
    音频: 🎵
    视频: 🎬
    压缩: 📦
    可执行: 🔧🍎
    其他: 📋🗃️📧
"""

import sys
from pathlib import Path

# 仅用于类型提示
from typing import Optional


def demo_file_cards():
    """演示文件卡片组件"""
    from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
    from PyQt6.QtCore import Qt

    # 创建应用
    app = QApplication(sys.argv)

    # 创建窗口
    window = QMainWindow()
    window.setWindowTitle("FileCard 演示 - 文件智能展示")
    window.setGeometry(100, 100, 600, 500)

    # 创建中央组件
    central = QWidget()
    window.setCentralWidget(central)
    layout = QVBoxLayout(central)

    # 导入 FileCard 和 MultiFileCard
    from ui.unified_chat.chat_panel import (
        FileCard, MultiFileCard,
        create_file_message_content
    )

    # 单文件卡片演示
    print("=== 单文件卡片演示 ===")
    single_card = FileCard(
        file_path="C:/Users/Admin/Documents/年度报告.pdf",
        file_name="年度报告_2024.pdf",
        file_size=2621440,  # 2.5 MB
        operations=["open", "show_in_folder", "copy_path"]
    )
    layout.addWidget(single_card)
    print(f"文件图标: {single_card.file_name}")

    # 多文件卡片演示
    print("\n=== 多文件卡片演示 ===")
    demo_files = [
        {"path": "C:/Users/Admin/Documents/年度报告.pdf", "name": "年度报告.pdf", "size": 2621440},
        {"path": "C:/Users/Admin/Documents/数据表格.xlsx", "name": "数据分析.xlsx", "size": 524288},
        {"path": "C:/Users/Admin/Projects/analyze.py", "name": "分析脚本.py", "size": 8192},
        {"path": "C:/Users/Admin/Projects/config.json", "name": "配置文件.json", "size": 2048},
        {"path": "C:/Users/Admin/Pictures/图表.png", "name": "趋势图.png", "size": 156672},
        {"path": "C:/Users/Admin/Music/背景音乐.mp3", "name": "背景音乐.mp3", "size": 5242880},
        {"path": "C:/Users/Admin/Downloads/安装包.zip", "name": "工具包.zip", "size": 15728640},
    ]

    multi_card = MultiFileCard(files=demo_files)
    layout.addWidget(multi_card)

    # 连接信号
    def on_file_open(file_path: str, operation: str):
        print(f"文件操作: {operation} -> {file_path}")

    single_card.file_open_requested.connect(on_file_open)
    multi_card.file_open_requested.connect(on_file_open)

    # 显示窗口
    window.show()

    print("\n=== 工具函数演示 ===")
    from ui.unified_chat.chat_panel import get_file_icon, get_file_category, format_file_size

    for f in demo_files:
        path = f["path"]
        print(f"{get_file_icon(path)} {f['name']} -> {get_file_category(path)} ({format_file_size(f['size'])})")

    print("\n=== 文件消息内容生成 ===")
    content = create_file_message_content(demo_files, "🤖 已为您生成以下文件:")
    print(content[:500] + "..." if len(content) > 500 else content)

    return app.exec()


if __name__ == "__main__":
    sys.exit(demo_file_cards())