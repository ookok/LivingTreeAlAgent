# 详细测试脚本
import sys
import os

sys.path.insert(0, '.')

print("测试步骤 1: 导入 PyQt6")
try:
    from PyQt6.QtWidgets import QApplication
    print("✅ PyQt6 导入成功")
except Exception as e:
    print(f"❌ PyQt6 导入失败: {e}")
    sys.exit(1)

print("\n测试步骤 2: 导入配置")
try:
    from core.config import load_config
    print("✅ 配置模块导入成功")
except Exception as e:
    print(f"❌ 配置模块导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n测试步骤 3: 加载配置")
try:
    cfg = load_config()
    print("✅ 配置加载成功")
except Exception as e:
    print(f"❌ 配置加载失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n测试步骤 4: 导入主窗口")
try:
    from ui.main_window import MainWindow
    print("✅ 主窗口导入成功")
except Exception as e:
    print(f"❌ 主窗口导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n测试步骤 5: 创建主窗口")
try:
    app = QApplication(sys.argv)
    window = MainWindow(cfg)
    print("✅ 主窗口创建成功")
    print("\n🎉 所有测试通过！主窗口可以正常启动")
except Exception as e:
    print(f"❌ 主窗口创建失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n测试完成")