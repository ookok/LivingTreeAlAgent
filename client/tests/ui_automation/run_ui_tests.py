"""
PyQt6 UI 自动化测试运行器

运行 OpenCode IDE 的 UI 自动化测试

Usage:
    python run_ui_tests.py                    # 运行所有测试
    python run_ui_tests.py --component=chat   # 运行特定组件测试
    python run_ui_tests.py --list             # 列出所有测试
"""

import sys
import os
import argparse
from typing import List

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from PyQt6.QtWidgets import QApplication

from ui_automation import (
    TestRunner,
    TestActivityBar,
    TestChatPanel,
    TestMessageBubble,
    TestEditorPanel,
    TestPipelineProgress,
    TestToolCallTimeline,
    TestOpenCodeIDEIntegration,
    run_ide_tests,
)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="OpenCode IDE UI Automation Tests"
    )
    parser.add_argument(
        "--component",
        "-c",
        choices=["activity", "chat", "message", "editor", "pipeline", "tool", "integration", "all"],
        default="all",
        help="Component to test"
    )
    parser.add_argument(
        "--output",
        "-o",
        default="test_results",
        help="Output directory"
    )
    parser.add_argument(
        "--screenshot",
        "-s",
        default="test_screenshots",
        help="Screenshot directory"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List all tests"
    )
    parser.add_argument(
        "--no-screenshot",
        action="store_true",
        help="Disable screenshot on failure"
    )

    return parser.parse_args()


def get_test_classes(component: str) -> List[type]:
    """获取测试类"""
    mapping = {
        "activity": [TestActivityBar],
        "chat": [TestChatPanel],
        "message": [TestMessageBubble],
        "editor": [TestEditorPanel],
        "pipeline": [TestPipelineProgress],
        "tool": [TestToolCallTimeline],
        "integration": [TestOpenCodeIDEIntegration],
        "all": [
            TestActivityBar,
            TestChatPanel,
            TestMessageBubble,
            TestEditorPanel,
            TestPipelineProgress,
            TestToolCallTimeline,
            TestOpenCodeIDEIntegration,
        ]
    }
    return mapping.get(component, mapping["all"])


def list_tests(test_classes: List[type]):
    """列出所有测试"""
    print("\nAvailable Tests:")
    print("=" * 60)

    for test_class in test_classes:
        print(f"\n{test_class.__name__}:")
        methods = [m for m in dir(test_class) if m.startswith("test_")]
        for method in methods:
            print(f"  - {method}")

    print("\n" + "=" * 60)


def main():
    """主函数"""
    args = parse_args()

    # 获取测试类
    test_classes = get_test_classes(args.component)

    # 列出测试
    if args.list:
        list_tests(test_classes)
        return 0

    # 创建应用
    app = QApplication(sys.argv)
    app.setApplicationName("OpenCode IDE Tests")

    # 运行测试
    print("\n" + "=" * 60)
    print("OpenCode IDE UI Automation Tests")
    print("=" * 60)
    print(f"Component: {args.component}")
    print(f"Output: {args.output}")
    print(f"Screenshot: {args.screenshot}")
    print("=" * 60 + "\n")

    results = run_ide_tests(
        test_classes=test_classes,
        output_dir=args.output,
        screenshot_dir=args.screenshot
    )

    # 输出结果
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    print(f"Total: {results['total']}")
    print(f"Passed: {results['passed']}")
    print(f"Failed: {results['failed']}")
    print(f"Success Rate: {results['success_rate']:.1f}%")
    print(f"Duration: {results['duration']:.2f}s")
    print("=" * 60)

    # 退出
    app.quit()

    return 0 if results['failed'] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
