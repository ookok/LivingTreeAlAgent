#!/usr/bin/env python3
"""测试所有UI模块的导入"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath('.'))

print("Testing imports...", flush=True)

try:
    print("1. Testing theme_manager...", flush=True)
    from client.src.presentation.theme import theme_manager
    print("   OK", flush=True)
except Exception as e:
    print(f"   FAILED: {e}", flush=True)

try:
    print("2. Testing router...")
    from client.src.presentation.router import get_router, Router
    print("   OK")
except Exception as e:
    print(f"   FAILED: {e}")

try:
    print("3. Testing sidebar...")
    from client.src.presentation.layouts.sidebar import SidebarWidget
    print("   OK")
except Exception as e:
    print(f"   FAILED: {e}")

try:
    print("4. Testing main_window...")
    from client.src.presentation.layouts.main_window import MainWindow
    print("   OK")
except Exception as e:
    print(f"   FAILED: {e}")

try:
    print("5. Testing routes...")
    from client.src.presentation.router.routes import register_default_routes
    print("   OK")
except Exception as e:
    print(f"   FAILED: {e}")

print("\nAll tests completed!")
