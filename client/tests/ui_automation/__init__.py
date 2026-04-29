"""
PyQt6 UI 自动化测试框架
======================

为 OpenCode IDE 设计的 UI 自动化测试框架：
- 组件测试：测试独立 UI 组件
- 业务逻辑测试：测试组件背后的业务逻辑
- 集成测试：测试组件间的交互
- 回归测试：防止功能退化

核心功能：
- 自动等待机制（避免 flaky tests）
- 截图对比（视觉回归测试）
- 事件模拟（鼠标、键盘、触摸）
- 状态断言（验证 UI 状态）
- 自动生成测试代码（分析业务逻辑）
- 自动查找测试资源（localresources）
"""

__version__ = "1.1.0"

from .test_base import (
    TestCase,
    TestRunner,
    wait_for,
    wait_until,
    ensure_visible,
    screenshot_on_failure,
)

from .component_tester import (
    ComponentTester,
    assert_widget_exists,
    assert_widget_enabled,
    assert_widget_visible,
    assert_text_contains,
    simulate_click,
    simulate_type,
)

from .business_logic_tester import (
    BusinessLogicTester,
    test_message_rendering,
    test_streaming_output,
    test_tool_call_timeline,
    test_pipeline_progress,
)

from .opencode_ide_tester import (
    OpenCodeIDETester,
    IDEComponentTest,
    IDETestSuite,
)

from .resource_locator import (
    ResourceLocator,
    ResourceFile,
    SearchCriteria,
    get_resource_locator,
    find_test_resource,
    find_test_data_file,
)

from .auto_test_generator import (
    CodeAnalyzer,
    ClassInfo,
    MethodInfo,
    TestCodeGenerator,
    TestSuiteGenerator,
    auto_generate_tests,
    generate_opencode_ide_tests,
)

__all__ = [
    # Base
    "TestCase",
    "TestRunner",
    "wait_for",
    "wait_until",
    "ensure_visible",
    "screenshot_on_failure",
    # Component
    "ComponentTester",
    "assert_widget_exists",
    "assert_widget_enabled",
    "assert_widget_visible",
    "assert_text_contains",
    "simulate_click",
    "simulate_type",
    # Business Logic
    "BusinessLogicTester",
    "test_message_rendering",
    "test_streaming_output",
    "test_tool_call_timeline",
    "test_pipeline_progress",
    # OpenCode IDE
    "OpenCodeIDETester",
    "IDEComponentTest",
    "IDETestSuite",
    # Resource Locator
    "ResourceLocator",
    "ResourceFile",
    "SearchCriteria",
    "get_resource_locator",
    "find_test_resource",
    "find_test_data_file",
    # Auto Test Generator
    "CodeAnalyzer",
    "ClassInfo",
    "MethodInfo",
    "TestCodeGenerator",
    "TestSuiteGenerator",
    "auto_generate_tests",
    "generate_opencode_ide_tests",
]
