"""
测试可视化工作流编辑器面板
"""

import sys
import os

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'client', 'src'))

# 检查 PyQt6 是否安装
try:
    from PyQt6.QtWidgets import QApplication, QMainWindow
    from presentation.panels.workflow_panel import WorkflowPanel
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False

def main():
    """测试工作流面板"""
    if not PYQT_AVAILABLE:
        print("❌ PyQt6 未安装，无法运行测试")
        return
    
    app = QApplication(sys.argv)
    
    # 创建主窗口
    window = QMainWindow()
    window.setWindowTitle("工作流编辑器测试")
    window.setGeometry(100, 100, 1000, 700)
    
    # 创建工作流面板
    panel = WorkflowPanel()
    window.setCentralWidget(panel)
    
    # 显示窗口
    window.show()
    
    # 运行应用
    sys.exit(app.exec())

if __name__ == "__main__":
    main()