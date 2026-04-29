#!/usr/bin/env python3
"""
📊 Opik Phase 3 测试脚本

测试内容：
1. 导入 Opik Dashboard 面板
2. 检查路由注册
3. 测试 Dashboard 嵌入
4. 测试 Traces/Metrics/Alerts 标签页
5. 测试配置管理

作者: LivingTreeAI Team
日期: 2026-04-29
版本: 1.0.0
"""

import sys
import traceback

print("=" * 60)
print("📊 Opik Phase 3 测试开始")
print("=" * 60)

# ─── 测试1: 导入 Opik Dashboard 面板 ─────────────────────────
print("\n📋 测试1: 导入 Opik Dashboard 面板")

try:
    from client.src.presentation.panels.opik_panel import OpikDashboardPanel
    print("✅ OpikDashboardPanel 导入成功")
    test1_passed = True
except Exception as e:
    print(f"❌ OpikDashboardPanel 导入失败: {e}")
    traceback.print_exc()
    test1_passed = False

# ─── 测试2: 检查路由注册 ─────────────────────────────────────
print("\n📋 测试2: 检查路由注册")

try:
    from client.src.presentation.router.routes import register_default_routes
    from client.src.presentation.router.router import Router

    # 创建测试 Router
    test_router = Router()

    # 调用注册函数
    register_default_routes(test_router)

    # 检查 opik 路由是否存在
    opik_route = None
    for route in test_router.get_all_routes():
        if route.name == "opik":
            opik_route = route
            break

    if opik_route:
        print(f"✅ Opik 路由已注册: {opik_route.name} - {opik_route.display_name}")
        test2_passed = True
    else:
        print("❌ Opik 路由未注册")
        test2_passed = False

except Exception as e:
    print(f"❌ 路由注册检查失败: {e}")
    traceback.print_exc()
    test2_passed = False

# ─── 测试3: 测试 Dashboard 嵌入 (QWebEngineView) ───────────
print("\n📋 测试3: 测试 Dashboard 嵌入 (QWebEngineView)")

try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtWebEngineWidgets import QWebEngineView

    # 创建 QApplication（如果需要）
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    # 创建面板实例
    panel = OpikDashboardPanel()

    # 检查 web_view 是否存在
    if hasattr(panel, 'web_view') and panel.web_view is not None:
        print("✅ QWebEngineView 已创建")
        test3_passed = True
    else:
        print("⚠️ QWebEngineView 未创建（可能 QWebEngine 不可用）")
        test3_passed = False

    # 清理
    panel.deleteLater()

except ImportError:
    print("⚠️ PyQt6-WebEngine 未安装，跳过 Dashboard 嵌入测试")
    print("   安装: pip install PyQt6-WebEngine")
    test3_passed = False
except Exception as e:
    print(f"❌ Dashboard 嵌入测试失败: {e}")
    traceback.print_exc()
    test3_passed = False

# ─── 测试4: 测试 Traces/Metrics/Alerts 标签页 ──────────────
print("\n📋 测试4: 测试 Traces/Metrics/Alerts 标签页")

try:
    from PyQt6.QtWidgets import QApplication

    # 创建 QApplication（如果需要）
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    # 创建面板实例
    panel = OpikDashboardPanel()

    # 检查各标签页的组件是否存在
    tabs_exist = True

    if not hasattr(panel, 'traces_table') or panel.traces_table is None:
        print("❌ Traces 表格不存在")
        tabs_exist = False

    if not hasattr(panel, 'metrics_table') or panel.metrics_table is None:
        print("❌ Metrics 表格不存在")
        tabs_exist = False

    if not hasattr(panel, 'alerts_table') or panel.alerts_table is None:
        print("❌ Alerts 表格不存在")
        tabs_exist = False

    if tabs_exist:
        print("✅ 所有标签页组件已创建")
        test4_passed = True
    else:
        print("❌ 部分标签页组件缺失")
        test4_passed = False

    # 清理
    panel.deleteLater()

except Exception as e:
    print(f"❌ 标签页测试失败: {e}")
    traceback.print_exc()
    test4_passed = False

# ─── 测试5: 测试配置管理 ─────────────────────────────────────
print("\n📋 测试5: 测试配置管理")

try:
    from PyQt6.QtWidgets import QApplication

    # 创建 QApplication（如果需要）
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    # 创建面板实例
    panel = OpikDashboardPanel()

    # 检查配置组件是否存在
    config_exists = True

    if not hasattr(panel, 'config_url') or panel.config_url is None:
        print("❌ URL 输入框不存在")
        config_exists = False

    if not hasattr(panel, 'config_use_local') or panel.config_use_local is None:
        print("❌ 本地模式复选框不存在")
        config_exists = False

    if not hasattr(panel, 'trace_llm') or panel.trace_llm is None:
        print("❌ LLM 追踪复选框不存在")
        config_exists = False

    if config_exists:
        print("✅ 配置管理组件已创建")

        # 测试配置应用函数是否存在
        if hasattr(panel, '_on_apply_config'):
            print("✅ 配置应用函数存在")
            test5_passed = True
        else:
            print("❌ 配置应用函数不存在")
            test5_passed = False
    else:
        print("❌ 部分配置组件缺失")
        test5_passed = False

    # 清理
    panel.deleteLater()

except Exception as e:
    print(f"❌ 配置管理测试失败: {e}")
    traceback.print_exc()
    test5_passed = False

# ─── 测试6: 测试与 Opik 追踪模块的集成 ──────────────────────
print("\n📋 测试6: 测试与 Opik 追踪模块的集成")

try:
    from client.src.business.opik_tracer import (
        is_opik_enabled, OpikConfig, init_opik_for_livingtree
    )
    print("✅ Opik 追踪模块已导入")

    # 检查面板是否正确引用了追踪模块
    import inspect
    source = inspect.getsource(OpikDashboardPanel)

    if 'is_opik_enabled' in source:
        print("✅ 面板中使用了 is_opik_enabled()")
        test6_passed = True
    else:
        print("⚠️ 面板中未找到 is_opik_enabled() 调用")
        test6_passed = False

except ImportError:
    print("⚠️ Opik 追踪模块未安装，跳过集成测试")
    test6_passed = False
except Exception as e:
    print(f"❌ 集成测试失败: {e}")
    traceback.print_exc()
    test6_passed = False

# ─── 汇总测试结果 ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("📊 测试结果汇总")
print("=" * 60)

tests = [
    ("测试1: 导入面板", test1_passed),
    ("测试2: 路由注册", test2_passed),
    ("测试3: Dashboard 嵌入", test3_passed),
    ("测试4: 标签页组件", test4_passed),
    ("测试5: 配置管理", test5_passed),
    ("测试6: 模块集成", test6_passed),
]

passed = 0
failed = 0

for test_name, result in tests:
    if result:
        print(f"✅ {test_name}: 通过")
        passed += 1
    else:
        print(f"❌ {test_name}: 失败")
        failed += 1

print("\n" + "-" * 60)
print(f"总计: {passed + failed} 个测试")
print(f"✅ 通过: {passed} 个")
print(f"❌ 失败: {failed} 个")
print("-" * 60)

if failed == 0:
    print("\n🎉 所有测试通过！Opik Phase 3 集成成功！")
    sys.exit(0)
else:
    print(f"\n⚠️ 有 {failed} 个测试失败，请检查错误信息。")
    sys.exit(1)
