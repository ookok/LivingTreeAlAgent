"""
简单的 UI 自动化测试脚本

直接测试客户端启动
"""

import sys
import os
import time

# 添加项目路径
current_dir = os.path.dirname(__file__)
sys.path.insert(0, current_dir)
sys.path.insert(0, os.path.join(current_dir, '..', '..'))
sys.path.insert(0, os.path.join(current_dir, '..', '..', 'src'))


def test_client_startup():
    """测试客户端启动"""
    print("\n" + "="*60)
    print("UI 自动化测试 - 客户端启动测试")
    print("="*60)
    
    # 直接调用客户端主函数
    from src.main import main
    
    # 在子进程中运行客户端
    import subprocess
    import threading
    
    # 创建测试进程
    proc = subprocess.Popen(
        [sys.executable, "-m", "client.src.main"],
        cwd=os.path.join(current_dir, '..', '..'),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    # 等待启动
    print("\n等待客户端启动...")
    time.sleep(15)
    
    # 检查进程是否仍在运行
    if proc.poll() is None:
        print("✓ 客户端进程正在运行")
        
        # 尝试连接到运行中的应用
        try:
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            
            if app:
                top_level_widgets = app.topLevelWidgets()
                print(f"✓ 找到 {len(top_level_widgets)} 个顶层窗口")
                
                main_window = None
                from PyQt6.QtWidgets import QMainWindow
                for widget in top_level_widgets:
                    if isinstance(widget, QMainWindow):
                        main_window = widget
                        break
                
                if main_window:
                    print(f"✓ 主窗口标题: {main_window.windowTitle()}")
                    print(f"✓ 主窗口可见: {main_window.isVisible()}")
                    
                    # 测试侧边栏
                    from page_objects import SidebarPage
                    sidebar = SidebarPage(main_window)
                    if sidebar.widget:
                        print(f"✓ 侧边栏导航按钮: {sidebar.nav_buttons}")
                    else:
                        print("✗ 侧边栏未找到")
                else:
                    print("✗ 主窗口未找到")
            else:
                print("✗ 无法获取 QApplication 实例")
                
        except Exception as e:
            print(f"测试过程中出错: {e}")
        
        # 终止进程
        proc.terminate()
        proc.wait()
        print("\n✓ 测试完成")
        return 0
    else:
        # 读取错误输出
        output, _ = proc.communicate()
        print("✗ 客户端进程已退出")
        if output:
            print("输出:")
            print(output[-2000:])
        return 1


if __name__ == "__main__":
    sys.exit(test_client_startup())