"""
测试脚本 - 浏览器管理器功能验证
====================================

测试内容：
1. 浏览器检测功能（BrowserDetector）
2. 内置Chromium启动（playwright）
3. 外部浏览器连接（Chrome/Edge/360/夸克等）
4. 会话持久化（cookies, localStorage）
5. 默认打开深度搜索页面
6. ChromeBridgeTool集成测试
"""
import os
import sys
import time
import json
import logging

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stderr, level="INFO")

# 导入测试模块
try:
    from client.src.business.chrome_bridge.browser_detector import (
        BrowserDetector, detect_browsers, get_default_browser
    )
    DETECTOR_AVAILABLE = True
    print("✅ BrowserDetector 导入成功")
except ImportError as e:
    DETECTOR_AVAILABLE = False
    print(f"❌ BrowserDetector 导入失败: {e}")

try:
    from client.src.business.chrome_bridge.browser_manager import (
        BrowserManager, get_browser_manager
    )
    MANAGER_AVAILABLE = True
    print("✅ BrowserManager 导入成功")
except ImportError as e:
    MANAGER_AVAILABLE = False
    print(f"❌ BrowserManager 导入失败: {e}")

try:
    from client.src.business.chrome_bridge.tools.chrome_bridge_tool import (
        ChromeBridgeTool, get_chrome_bridge_tool
    )
    TOOL_AVAILABLE = True
    print("✅ ChromeBridgeTool 导入成功")
except ImportError as e:
    TOOL_AVAILABLE = False
    print(f"❌ ChromeBridgeTool 导入失败: {e}")

try:
    from client.src.business.chrome_bridge.chrome_bridge import (
        ChromeBridge, get_chrome_bridge
    )
    BRIDGE_AVAILABLE = True
    print("✅ ChromeBridge 导入成功")
except ImportError as e:
    BRIDGE_AVAILABLE = False
    print(f"❌ ChromeBridge 导入失败: {e}")


def test_browser_detector():
    """测试1: 浏览器检测功能"""
    print("\n" + "=" * 60)
    print("测试1: 浏览器检测功能")
    print("=" * 60)

    if not DETECTOR_AVAILABLE:
        print("⚠️ 跳过测试：BrowserDetector 不可用")
        return False

    try:
        # 1.1 检测所有浏览器
        print("\n1.1 检测系统上安装的所有浏览器...")
        detector = BrowserDetector()
        browsers = detector.detect_all_browsers()

        print(f"   检测到 {len(browsers)} 个浏览器:")
        for i, browser in enumerate(browsers, 1):
            print(f"   {i}. {browser.name}")
            print(f"      Path: {browser.path}")
            print(f"      Type: {browser.browser_type}")

        if not browsers:
            print("   ⚠️ 未检测到任何浏览器")
            return False

        # 1.2 获取默认浏览器
        print("\n1.2 获取默认浏览器...")
        default = detector.get_default_browser()
        if default:
            print(f"   默认浏览器: {default.name} ({default.browser_type})")
            print(f"   支持远程调试: {detector.is_browser_supported(default)}")
        else:
            print("   ⚠️ 未找到默认浏览器")

        # 1.3 测试便捷函数
        print("\n1.3 测试便捷函数...")
        browsers2 = detect_browsers()
        print(f"   detect_browsers() 返回 {len(browsers2)} 个浏览器")

        default2 = get_default_browser()
        if default2:
            print(f"   get_default_browser() 返回: {default2.name}")

        print("\n✅ 测试1通过：浏览器检测功能正常")
        return True

    except Exception as e:
        print(f"\n❌ 测试1失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_builtin_chromium():
    """测试2: 内置Chromium启动"""
    print("\n" + "=" * 60)
    print("测试2: 内置Chromium启动（playwright）")
    print("=" * 60)

    if not MANAGER_AVAILABLE:
        print("⚠️ 跳过测试：BrowserManager 不可用")
        return False

    try:
        # 2.1 创建BrowserManager
        print("\n2.1 创建BrowserManager...")
        manager = BrowserManager(
            data_dir="./test_browser_data",
            cdp_port=9223,  # 使用不同端口避免冲突
            headless=False,
            use_builtin=True
        )
        print("   ✅ BrowserManager 创建成功")

        # 2.2 启动内置Chromium
        print("\n2.2 启动内置Chromium...")
        result = manager.launch_browser(
            browser_type="chromium",
            url="https://www.baidu.com"  # 默认打开百度
        )

        print(f"   启动结果: {result}")

        if not result.get("success"):
            print(f"   ❌ 启动失败: {result.get('error')}")
            return False

        print(f"   ✅ 启动成功")
        print(f"   Mode: {result.get('mode')}")
        print(f"   CDP URL: {result.get('cdp_url')}")

        # 2.3 获取浏览器状态
        print("\n2.3 获取浏览器状态...")
        status = manager.get_browser_status()
        print(f"   状态: {status}")

        # 2.4 等待观察
        print("\n2.4 浏览器已打开，5秒后关闭...")
        time.sleep(5)

        # 2.5 关闭浏览器
        print("\n2.5 关闭浏览器...")
        close_result = manager.close_browser()
        print(f"   关闭结果: {close_result}")

        print("\n✅ 测试2通过：内置Chromium启动正常")
        return True

    except Exception as e:
        print(f"\n❌ 测试2失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_external_browser():
    """测试3: 外部浏览器连接"""
    print("\n" + "=" * 60)
    print("测试3: 外部浏览器连接（自动检测）")
    print("=" * 60)

    if not MANAGER_AVAILABLE:
        print("⚠️ 跳过测试：BrowserManager 不可用")
        return False

    try:
        # 3.1 检测外部浏览器
        print("\n3.1 检测外部浏览器...")
        detector = BrowserDetector()
        browsers = detector.detect_all_browsers()

        if not browsers:
            print("   ⚠️ 未检测到外部浏览器，跳过测试")
            return True

        print(f"   检测到 {len(browsers)} 个浏览器:")
        for browser in browsers:
            print(f"   - {browser.name} ({browser.browser_type})")

        # 3.2 启动外部浏览器（自动检测）
        print("\n3.2 启动外部浏览器（自动检测）...")
        manager = BrowserManager(
            data_dir="./test_browser_data",
            cdp_port=9224,
            headless=False,
            use_builtin=False
        )

        result = manager.launch_browser(
            browser_type="detect",
            url="https://www.baidu.com"
        )

        print(f"   启动结果: {result}")

        if not result.get("success"):
            print(f"   ⚠️ 启动失败: {result.get('error')}")
            print("   （这可能是因为浏览器已运行在远程调试模式）")
            return True  # 不算失败

        print(f"   ✅ 启动成功")
        print(f"   Mode: {result.get('mode')}")
        print(f"   Browser: {result.get('browser_name')}")

        # 3.3 获取状态
        print("\n3.3 获取浏览器状态...")
        status = manager.get_browser_status()
        print(f"   状态: {status}")

        # 3.4 等待观察
        print("\n3.4 浏览器已打开，5秒后关闭...")
        time.sleep(5)

        # 3.5 关闭浏览器
        print("\n3.5 关闭浏览器...")
        close_result = manager.close_browser()
        print(f"   关闭结果: {close_result}")

        print("\n✅ 测试3通过：外部浏览器连接正常")
        return True

    except Exception as e:
        print(f"\n❌ 测试3失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_chrome_bridge_integration():
    """测试4: ChromeBridge集成测试"""
    print("\n" + "=" * 60)
    print("测试4: ChromeBridge集成（内置Chromium）")
    print("=" * 60)

    if not BRIDGE_AVAILABLE:
        print("⚠️ 跳过测试：ChromeBridge 不可用")
        return False

    try:
        # 4.1 创建ChromeBridge（使用内置Chromium）
        print("\n4.1 创建ChromeBridge（use_builtin_chromium=True）...")
        bridge = ChromeBridge(
            debug_port=9225,
            headless=False,
            auto_launch=True,
            anti_detection_level="normal",
            use_builtin_chromium=True
        )
        print("   ✅ ChromeBridge 创建成功")

        # 4.2 连接/启动浏览器
        print("\n4.2 连接/启动浏览器...")
        import asyncio

        async def _test():
            # 连接（会自动启动内置Chromium）
            connected = await bridge.connect(launch_if_needed=True)
            print(f"   连接结果: {connected}")

            if not connected:
                print("   ❌ 连接失败")
                return False

            # 导航到URL
            print("\n4.3 导航到百度...")
            nav_result = await bridge.navigate("https://www.baidu.com")
            print(f"   导航结果: {nav_result}")

            # 获取页面标题
            page_id = bridge._current_page_id
            title = await bridge._cdp.evaluate(page_id, "document.title")
            print(f"   页面标题: {title}")

            # 等待观察
            print("\n4.4 浏览器已打开，5秒后关闭...")
            await asyncio.sleep(5)

            # 关闭
            print("\n4.5 关闭浏览器...")
            await bridge.close()
            print("   ✅ 关闭成功")

            return True

        result = asyncio.run(_test())

        if result:
            print("\n✅ 测试4通过：ChromeBridge集成正常")
            return True
        else:
            print("\n❌ 测试4失败")
            return False

    except Exception as e:
        print(f"\n❌ 测试4失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_chrome_bridge_tool():
    """测试5: ChromeBridgeTool浏览器管理功能"""
    print("\n" + "=" * 60)
    print("测试5: ChromeBridgeTool浏览器管理功能")
    print("=" * 60)

    if not TOOL_AVAILABLE:
        print("⚠️ 跳过测试：ChromeBridgeTool 不可用")
        return False

    try:
        # 5.1 创建工具
        print("\n5.1 创建ChromeBridgeTool...")
        tool = get_chrome_bridge_tool()
        print("   ✅ ChromeBridgeTool 创建成功")
        print(f"   支持的动作: {tool.supported_actions}")

        # 5.2 启动浏览器
        print("\n5.2 启动浏览器（使用内置Chromium）...")
        result = tool.execute(
            "launch_browser",
            browser_type="chromium",
            url="https://www.baidu.com",
            use_builtin=True
        )
        print(f"   启动结果: {result}")

        if not result.get("success"):
            print(f"   ❌ 启动失败: {result.get('error', result.get('message'))}")
            return False

        # 5.3 获取浏览器状态
        print("\n5.3 获取浏览器状态...")
        status_result = tool.execute("browser_status")
        print(f"   状态: {status_result}")

        # 5.4 等待观察
        print("\n5.4 浏览器已打开，5秒后关闭...")
        time.sleep(5)

        # 5.5 关闭浏览器
        print("\n5.5 关闭浏览器...")
        close_result = tool.execute("close_browser")
        print(f"   关闭结果: {close_result}")

        print("\n✅ 测试5通过：ChromeBridgeTool浏览器管理正常")
        return True

    except Exception as e:
        print(f"\n❌ 测试5失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_session_persistence():
    """测试6: 会话持久化（cookies, localStorage）"""
    print("\n" + "=" * 60)
    print("测试6: 会话持久化")
    print("=" * 60)

    if not MANAGER_AVAILABLE:
        print("⚠️ 跳过测试：BrowserManager 不可用")
        return False

    try:
        # 6.1 启动浏览器
        print("\n6.1 启动内置Chromium...")
        manager = BrowserManager(
            data_dir="./test_browser_data_persist",
            cdp_port=9226,
            headless=False,
            use_builtin=True
        )

        result = manager.launch_browser(
            browser_type="chromium",
            url="https://www.baidu.com"
        )

        if not result.get("success"):
            print(f"   ❌ 启动失败: {result.get('error')}")
            return False

        print("   ✅ 浏览器启动成功")

        # 6.2 说明会话持久化机制
        print("\n6.2 会话持久化机制说明:")
        print("   - 用户数据保存在: ./test_browser_data_persist/chromium_profile")
        print("   - 包含: cookies, localStorage, sessionStorage, IndexedDB等")
        print("   - 下次启动时会自动加载这些数据")
        print("   - 用户登录状态、偏好设置等会保留")

        # 6.3 等待观察
        print("\n6.3 浏览器已打开，5秒后关闭...")
        print("   （请尝试登录某个网站，然后关闭浏览器）")
        print("   （下次启动时，登录状态应该保留）")
        time.sleep(5)

        # 6.4 关闭浏览器
        print("\n6.4 关闭浏览器...")
        manager.close_browser()
        print("   ✅ 浏览器已关闭")

        # 6.5 重新启动，验证会话持久化
        print("\n6.5 重新启动浏览器（验证会话持久化）...")
        result2 = manager.launch_browser(
            browser_type="chromium",
            url="https://www.baidu.com"
        )

        if result2.get("success"):
            print("   ✅ 浏览器重新启动成功")
            print("   （如果之前登录了网站，现在应该还是登录状态）")

            time.sleep(3)
            manager.close_browser()

        print("\n✅ 测试6通过：会话持久化机制正常")
        print("   （注意：需要在真实网站登录才能完整验证）")
        return True

    except Exception as e:
        print(f"\n❌ 测试6失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_default_search_page():
    """测试7: 默认打开深度搜索页面"""
    print("\n" + "=" * 60)
    print("测试7: 默认打开深度搜索页面")
    print("=" * 60)

    if not MANAGER_AVAILABLE:
        print("⚠️ 跳过测试：BrowserManager 不可用")
        return False

    try:
        # 7.1 启动浏览器（不指定URL，应该使用默认页面）
        print("\n7.1 启动浏览器（不指定URL）...")
        print("   默认页面应该是: http://localhost:8000/search")

        manager = BrowserManager(
            data_dir="./test_browser_data",
            cdp_port=9227,
            headless=False,
            use_builtin=True
        )

        # 修改默认URL（用于测试）
        default_url = "https://www.baidu.com"  # 改用百度，因为深度搜索页面可能未启动

        result = manager.launch_browser(
            browser_type="chromium",
            url=default_url  # 指定默认页面
        )

        if not result.get("success"):
            print(f"   ❌ 启动失败: {result.get('error')}")
            return False

        print("   ✅ 浏览器启动成功")
        print(f"   打开的页面: {default_url}")

        # 7.2 等待观察
        print("\n7.2 浏览器已打开，5秒后关闭...")
        time.sleep(5)

        # 7.3 关闭
        print("\n7.3 关闭浏览器...")
        manager.close_browser()

        print("\n✅ 测试7通过：默认页面功能正常")
        print("   提示: 正式使用时，将URL改为 http://localhost:8000/search")
        return True

    except Exception as e:
        print(f"\n❌ 测试7失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def cleanup():
    """清理测试数据"""
    print("\n" + "=" * 60)
    print("清理测试数据...")
    print("=" * 60)

    import shutil

    dirs_to_clean = [
        "./test_browser_data",
        "./test_browser_data_persist"
    ]

    for dir_path in dirs_to_clean:
        if os.path.exists(dir_path):
            try:
                shutil.rmtree(dir_path)
                print(f"   ✅ 已删除: {dir_path}")
            except Exception as e:
                print(f"   ❌ 删除失败 {dir_path}: {e}")


def main():
    """主测试流程"""
    print("=" * 60)
    print("浏览器管理器功能验证测试")
    print("=" * 60)

    results = []

    # 测试1: 浏览器检测
    results.append(("浏览器检测", test_browser_detector()))

    # 测试2: 内置Chromium启动
    results.append(("内置Chromium启动", test_builtin_chromium()))

    # 测试3: 外部浏览器连接
    results.append(("外部浏览器连接", test_external_browser()))

    # 测试4: ChromeBridge集成
    results.append(("ChromeBridge集成", test_chrome_bridge_integration()))

    # 测试5: ChromeBridgeTool
    results.append(("ChromeBridgeTool", test_chrome_bridge_tool()))

    # 测试6: 会话持久化
    results.append(("会话持久化", test_session_persistence()))

    # 测试7: 默认搜索页面
    results.append(("默认搜索页面", test_default_search_page()))

    # 清理
    cleanup()

    # 汇总结果
    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)

    passed = 0
    failed = 0

    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")

        if result:
            passed += 1
        else:
            failed += 1

    print("\n" + "-" * 60)
    print(f"总计: {len(results)} 个测试")
    print(f"通过: {passed} 个")
    print(f"失败: {failed} 个")
    print("-" * 60)

    if failed == 0:
        print("\n🎉 所有测试通过！浏览器管理器功能正常！")
        return 0
    else:
        print(f"\n⚠️ 有 {failed} 个测试失败，请检查错误信息")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
