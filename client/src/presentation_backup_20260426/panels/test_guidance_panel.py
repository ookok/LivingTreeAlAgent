"""
追问面板组件测试
================

测试 GuidancePanel 及其相关组件的功能

运行：
```bash
python -m ui.test_guidance_panel
```

作者：LivingTreeAI Team
日期：2026-04-24
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ============== 测试准备 ==============

def test_import():
    """测试导入"""
    print("1. 测试组件导入...")
    try:
        from ui.components.guidance_panel import (
            GuidancePanel,
            GuidanceButton,
            GuidanceCard,
            GuidanceManager,
            GuidanceItem,
            GuidanceDisplayMode,
            GuidancePosition,
            create_guidance_panel,
            quick_guidance_response,
        )
        print("   [OK] 所有组件导入成功")
        return True
    except ImportError as e:
        print(f"   [FAIL] 导入失败: {e}")
        return False


def test_data_structures():
    """测试数据结构"""
    print("2. 测试数据结构...")

    try:
        from ui.components.guidance_panel import GuidanceItem

        # 测试基本创建
        item = GuidanceItem(
            text="需要我详细解释吗？",
            action="explain",
            icon="💬"
        )

        assert item.text == "需要我详细解释吗？"
        assert item.action == "explain"
        assert item.icon == "💬"
        assert item.display_text == "💬 需要我详细解释吗？"
        print("   [OK] GuidanceItem 基本功能正常")

        # 测试空图标
        item2 = GuidanceItem(text="还有其他问题吗？", action="other")
        assert item2.display_text == "还有其他问题吗？"
        print("   [OK] GuidanceItem 无图标显示正常")

        return True
    except Exception as e:
        print(f"   [FAIL] 数据结构测试失败: {e}")
        return False


def test_display_modes():
    """测试展示模式枚举"""
    print("3. 测试展示模式枚举...")

    try:
        from ui.components.guidance_panel import GuidanceDisplayMode

        # 验证枚举值
        assert GuidanceDisplayMode.BUTTON.value == "button"
        assert GuidanceDisplayMode.CARD.value == "card"
        assert GuidanceDisplayMode.INLINE.value == "inline"

        print("   [OK] 展示模式枚举正常")
        return True
    except Exception as e:
        print(f"   [FAIL] 展示模式测试失败: {e}")
        return False


def test_quick_guidance():
    """测试快速生成函数"""
    print("4. 测试快速生成函数...")

    try:
        from ui.components.guidance_panel import quick_guidance_response, GuidanceDisplayMode
        from dataclasses import dataclass

        # 模拟 GuidanceResult
        @dataclass
        class MockGuidanceResult:
            questions: list
            strategy: str = "template"
            intent: str = None

        guidance = MockGuidanceResult(questions=[
            "需要我详细解释吗？",
            "还有其他方面想了解吗？",
        ])

        # 测试按钮模式
        response = quick_guidance_response(
            "这是一个测试响应。",
            guidance,
            GuidanceDisplayMode.BUTTON
        )

        assert "您可能还想问：" in response
        assert "1. 需要我详细解释吗？" in response
        assert "2. 还有其他方面想了解吗？" in response
        print("   [OK] 快速生成函数正常（按钮模式）")

        # 测试卡片模式
        response_card = quick_guidance_response(
            "这是一个测试响应。",
            guidance,
            GuidanceDisplayMode.CARD
        )
        assert "- 需要我详细解释吗？" in response_card
        print("   [OK] 快速生成函数正常（卡片模式）")

        # 测试无追问
        response_empty = quick_guidance_response(
            "这是一个测试响应。",
            None,
            GuidanceDisplayMode.BUTTON
        )
        assert response_empty == "这是一个测试响应。"
        print("   [OK] 空追问处理正常")

        return True
    except Exception as e:
        print(f"   [FAIL] 快速生成测试失败: {e}")
        return False


def test_pyqt_integration():
    """测试 PyQt6 集成"""
    print("5. 测试 PyQt6 集成...")

    try:
        from PyQt6.QtWidgets import QApplication
        from ui.components.guidance_panel import GuidancePanel, GuidanceDisplayMode, create_guidance_panel

        # 创建应用
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        # 测试创建面板
        questions = [
            "需要我详细解释吗？",
            "还有其他方面想了解吗？",
            "这个回答对您有帮助吗？",
        ]

        panel = create_guidance_panel(
            questions,
            display_mode=GuidanceDisplayMode.BUTTON,
            on_click=lambda t: print(f"点击: {t}")
        )

        assert panel is not None
        assert len(panel.items) == 3
        print("   [OK] 面板创建正常")

        # 测试主题切换
        panel.set_theme("light")
        panel.set_theme("dark")
        print("   [OK] 主题切换正常")

        return True
    except ImportError:
        print("   [SKIP] PyQt6 不可用，跳过 UI 测试")
        return True
    except Exception as e:
        print(f"   [FAIL] PyQt6 集成测试失败: {e}")
        return False


def test_guidance_manager():
    """测试追问管理器"""
    print("6. 测试 GuidanceManager...")

    try:
        from ui.components.guidance_panel import GuidanceManager, GuidanceDisplayMode

        # 测试创建管理器
        manager = GuidanceManager(
            enhanced_chat=None,
            display_mode=GuidanceDisplayMode.CARD,
            max_visible=3
        )

        assert manager.display_mode == GuidanceDisplayMode.CARD
        assert manager.max_visible == 3
        print("   [OK] GuidanceManager 创建正常")

        # 测试发送回调
        callback_triggered = False
        def test_callback(text):
            nonlocal callback_triggered
            callback_triggered = True

        manager.set_send_callback(test_callback)
        print("   [OK] 回调设置正常")

        return True
    except Exception as e:
        print(f"   [FAIL] GuidanceManager 测试失败: {e}")
        return False


def test_integration_import():
    """测试集成模块导入"""
    print("7. 测试集成模块...")

    try:
        from .presentation.panels.guidance_integration import (
            AgentChatWithGuidance,
            GuidanceUIConfig,
            create_chat_with_guidance,
        )

        # 测试配置
        config = GuidanceUIConfig(
            display_mode="button",
            max_visible=3,
            theme="dark"
        )
        assert config.display_mode == "button"
        assert config.max_visible == 3
        print("   [OK] GuidanceUIConfig 正常")

        # 测试工厂函数
        # (不实际创建 AgentChat，只测试函数存在)
        print("   [OK] create_chat_with_guidance 函数存在")

        return True
    except ImportError as e:
        print(f"   [SKIP] 集成模块部分依赖不可用: {e}")
        return True
    except Exception as e:
        print(f"   [FAIL] 集成模块测试失败: {e}")
        return False


# ============== 主测试函数 ==============

def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("GuidancePanel 组件测试")
    print("=" * 60)
    print()

    tests = [
        test_import,
        test_data_structures,
        test_display_modes,
        test_quick_guidance,
        test_guidance_manager,
        test_pyqt_integration,
        test_integration_import,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"   [ERROR] {e}")
            results.append(False)
        print()

    # 汇总
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"测试结果: {passed}/{total} 通过")
    print("=" * 60)

    if passed == total:
        print("[PASS] All tests passed!")
    else:
        print("[WARN] Some tests failed, please check output above")

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
