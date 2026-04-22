"""
移动端测试脚本
=======

测试移动端各功能模块

Usage:
    python mobile/test_mobile.py
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def test_adaptive_layout():
    """测试自适应布局"""
    print("=" * 60)
    print("测试: 自适应布局")
    print("=" * 60)
    
    try:
        from mobile.adaptive_layout import (
            DeviceDetector, LayoutConfigFactory, 
            AdaptiveManager, AdaptiveGridLayout
        )
        
        # 测试设备检测
        print("\n1. 设备检测测试:")
        devices = ["phone", "phablet", "tablet", "large_tablet"]
        for device in devices:
            config = LayoutConfigFactory.get_config(device, "portrait")
            print(f"   {device:15s}: cols={config.grid_cols:2d}, icon={config.icon_size:3.0f}, font={config.font_size:2d}")
        
        # 测试屏幕方向
        print("\n2. 屏幕方向测试:")
        for device in devices:
            portrait = LayoutConfigFactory.get_config(device, "portrait")
            landscape = LayoutConfigFactory.get_config(device, "landscape")
            print(f"   {device:15s}: portrait={portrait.grid_cols:2d} cols, landscape={landscape.grid_cols:2d} cols")
        
        # 测试自适应管理器
        print("\n3. 自适应管理器测试:")
        manager = AdaptiveManager()
        print(f"   设备类型: {manager.device_type}")
        print(f"   屏幕方向: {manager.orientation}")
        print(f"   是否移动设备: {manager.is_mobile}")
        print(f"   是否平板设备: {manager.is_tablet}")
        
        print("\n✅ 自适应布局测试通过")
        return True
    except Exception as e:
        print(f"\n❌ 自适应布局测试失败: {e}")
        return False


def test_screens():
    """测试屏幕组件"""
    print("\n" + "=" * 60)
    print("测试: 屏幕组件")
    print("=" * 60)
    
    try:
        from mobile.screens import (
            ChatScreen, SkillsScreen, SettingsScreen,
            BottomNav, GestureNav, MobileScreenManager
        )
        
        print("\n1. 屏幕类测试:")
        print(f"   ChatScreen: {ChatScreen}")
        print(f"   SkillsScreen: {SkillsScreen}")
        print(f"   SettingsScreen: {SettingsScreen}")
        
        print("\n2. 导航组件测试:")
        print(f"   BottomNav: {BottomNav}")
        print(f"   GestureNav: {GestureNav}")
        
        print("\n3. 屏幕管理器测试:")
        print(f"   MobileScreenManager: {MobileScreenManager}")
        
        print("\n✅ 屏幕组件测试通过")
        return True
    except Exception as e:
        print(f"\n❌ 屏幕组件测试失败: {e}")
        return False


def test_tablet_features():
    """测试平板功能"""
    print("\n" + "=" * 60)
    print("测试: 平板功能")
    print("=" * 60)
    
    try:
        from mobile.tablet_features import (
            TabletEnhancementManager, SplitScreenLayout,
            MultiWindowManager, KeyboardShortcuts, StylusSupport
        )
        
        print("\n1. 平板增强管理器测试:")
        manager = TabletEnhancementManager()
        manager.enable_tablet_features("tablet")
        print(f"   分屏功能: {'✅' if manager.is_feature_enabled('split_screen') else '❌'}")
        print(f"   键盘快捷键: {'✅' if manager.is_feature_enabled('keyboard_shortcuts') else '❌'}")
        
        print("\n2. 分屏布局测试:")
        split = SplitScreenLayout(orientation="horizontal", split_ratio=0.5)
        config = split.get_layout_config(1024, 768)
        print(f"   左面板: {config['left']['width']}x{config['left']['height']}")
        print(f"   右面板: {config['right']['width']}x{config['right']['height']}")
        
        print("\n3. 多窗口管理器测试:")
        multi = MultiWindowManager(max_windows=4)
        win1 = multi.create_window("Window 1", 400, 300)
        win2 = multi.create_window("Window 2", 300, 200)
        print(f"   创建窗口: {win1}, {win2}")
        print(f"   窗口数: {len(multi.windows)}")
        
        print("\n4. 键盘快捷键测试:")
        keyboard = KeyboardShortcuts()
        keyboard.register_handler("save", lambda: print("   保存动作触发"))
        keyboard.register_handler("undo", lambda: print("   撤销动作触发"))
        print(f"   快捷键数: {len(keyboard._shortcuts)}")
        
        print("\n5. 手写笔支持测试:")
        stylus = StylusSupport()
        has_stylus = stylus.detect_stylus()
        print(f"   检测到手写笔: {'✅' if has_stylus else '⚠️ 未检测到'}")
        
        print("\n✅ 平板功能测试通过")
        return True
    except Exception as e:
        print(f"\n❌ 平板功能测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_pwa_integration():
    """测试 PWA 集成"""
    print("\n" + "=" * 60)
    print("测试: PWA 集成")
    print("=" * 60)
    
    try:
        from mobile.pwa_integration import PWAManager, OfflineStorage, get_pwa_manager
        
        print("\n1. PWA 管理器测试:")
        pwa = PWAManager()
        manifest = pwa.get_manifest()
        print(f"   应用名称: {manifest['name']}")
        print(f"   显示模式: {manifest['display']}")
        print(f"   图标数: {len(manifest['icons'])}")
        
        print("\n2. Service Worker 生成测试:")
        sw_code = pwa.generate_service_worker_js()
        print(f"   Service Worker 代码长度: {len(sw_code)} 字符")
        print(f"   包含 install 事件: {'✅' if 'install' in sw_code else '❌'}")
        print(f"   包含 fetch 事件: {'✅' if 'fetch' in sw_code else '❌'}")
        
        print("\n3. 离线存储测试:")
        storage = OfflineStorage()
        print(f"   数据库名称: {storage.DB_NAME}")
        print(f"   数据库版本: {storage.DB_VERSION}")
        
        print("\n4. 全局实例测试:")
        pwa_mgr = get_pwa_manager()
        offline_mgr = get_pwa_manager()  # 应该是同一个实例
        print(f"   PWA 管理器单例: {'✅' if pwa_mgr is offline_mgr else '❌'}")
        
        print("\n✅ PWA 集成测试通过")
        return True
    except Exception as e:
        print(f"\n❌ PWA 集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_foldable_support():
    """测试折叠屏支持"""
    print("\n" + "=" * 60)
    print("测试: 折叠屏支持")
    print("=" * 60)
    
    try:
        from mobile.foldable_support import FoldableManager
        
        print("\n1. 折叠屏管理器测试:")
        manager = FoldableManager()
        print(f"   支持折叠屏: {'✅' if manager.is_foldable_supported() else '⚠️ 未检测到'}")
        
        print("\n✅ 折叠屏支持测试通过")
        return True
    except Exception as e:
        print(f"\n❌ 折叠屏支持测试失败: {e}")
        return False


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Hermes Desktop Mobile - 移动端测试套件")
    print("=" * 60)
    
    tests = [
        ("自适应布局", test_adaptive_layout),
        ("屏幕组件", test_screens),
        ("平板功能", test_tablet_features),
        ("PWA 集成", test_pwa_integration),
        ("折叠屏支持", test_foldable_support),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ {name} 测试异常: {e}")
            results.append((name, False))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"   {name:15s}: {status}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过!")
    else:
        print(f"\n⚠️ 有 {total - passed} 个测试失败")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
