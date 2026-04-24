"""测试深度搜索面板和主题系统"""
import sys
sys.path.insert(0, ".")

from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton
from PyQt6.QtCore import QTimer
from client.src.presentation.modules.deep_search_panel import DeepSearchPanel, get_mock_results
from client.src.presentation.theme import theme_manager
from client.src.presentation.main_window import AdvancedChatPanel


def test_deep_search_panel():
    """测试深度搜索面板"""
    app = QApplication(sys.argv)
    
    window = QWidget()
    window.setWindowTitle("深度搜索面板测试")
    window.resize(900, 700)
    
    layout = QVBoxLayout(window)
    
    # 创建深度搜索面板
    search_panel = DeepSearchPanel()
    layout.addWidget(search_panel)
    
    # 模拟搜索完成
    def show_results():
        results = get_mock_results()
        search_panel.show_results(results, total=50, related=["AI", "机器学习", "深度学习", "神经网络"])
    
    QTimer.singleShot(1500, show_results)
    
    window.show()
    return app, window


def test_theme_system():
    """测试主题系统"""
    app = QApplication(sys.argv)
    
    window = QWidget()
    window.setWindowTitle("主题系统测试")
    window.resize(600, 500)
    
    layout = QVBoxLayout(window)
    
    # 显示当前主题
    label = QLabel(f"当前主题: {theme_manager.current_theme}")
    layout.addWidget(label)
    
    # 切换主题按钮
    themes = ["light", "dark", "blue"]
    
    for theme in themes:
        btn = QPushButton(f"切换到 {theme_manager.THEMES[theme]['name']}")
        btn.clicked.connect(lambda c, t=theme: _change_theme(t, label))
        layout.addWidget(btn)
    
    def _change_theme(t, lbl):
        theme_manager.set_theme(t)
        lbl.setText(f"当前主题: {theme_manager.current_theme}")
    
    window.show()
    return app, window


def test_chat_panel():
    """测试聊天面板 - 任务树折叠"""
    app = QApplication(sys.argv)
    
    window = QWidget()
    window.setWindowTitle("聊天面板测试 - 任务树折叠")
    window.resize(800, 600)
    
    layout = QVBoxLayout(window)
    
    chat = AdvancedChatPanel()
    layout.addWidget(chat)
    
    # 模拟添加任务
    def add_tasks():
        chat.add_task("任务1: 分析需求")
        chat.add_task("任务2: 编写代码")
        chat.add_task("任务3: 测试验证")
    
    # 添加测试按钮
    test_btn = QPushButton("添加任务")
    test_btn.clicked.connect(add_tasks)
    layout.addWidget(test_btn)
    
    window.show()
    return app, window


if __name__ == "__main__":
    print("选择测试:")
    print("1. 深度搜索面板")
    print("2. 主题系统")
    print("3. 聊天面板")
    
    choice = input("请选择 (1/2/3): ").strip() or "1"
    
    if choice == "1":
        app, _ = test_deep_search_panel()
    elif choice == "2":
        app, _ = test_theme_system()
    elif choice == "3":
        app, _ = test_chat_panel()
    else:
        app, _ = test_deep_search_panel()
    
    sys.exit(app.exec())

