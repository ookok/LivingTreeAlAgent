"""
OpenCode IDE 测试器

专门为 OpenCode IDE Panel 设计的测试套件：
- ActivityBar 测试
- ChatPanel 测试
- MessageBubble 测试
- EditorPanel 测试
- PipelineProgress 测试
- 集成测试
"""

from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer

from .test_base import TestCase, TestRunner, wait_for, screenshot_on_failure
from .component_tester import ComponentTester
from .business_logic_tester import BusinessLogicTester


# ─────────────────────────────────────────────────────────────────────────────
# 测试数据
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class IDETestData:
    """IDE 测试数据"""
    # 消息数据
    user_messages: List[Dict[str, str]] = field(default_factory=list)
    assistant_messages: List[Dict[str, str]] = field(default_factory=list)

    # 工具调用数据
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)

    # 流水线数据
    pipeline_stages: List[Dict[str, Any]] = field(default_factory=list)

    # 主题数据
    theme: str = "dark"


# ─────────────────────────────────────────────────────────────────────────────
# IDEComponentTest
# ─────────────────────────────────────────────────────────────────────────────

class IDEComponentTest(TestCase):
    """
    IDE 组件测试基类

    Usage:
        class TestActivityBar(IDEComponentTest):
            def setUp(self):
                self.ide = create_test_ide()
                self.tester = self.create_tester(self.ide.activity_bar)

            def test_icon_buttons(self):
                self.tester.assert_visible()
                self.tester.assert_enabled()
    """

    def __init__(self, name: str = ""):
        super().__init__(name)
        self.ide: Optional[Any] = None
        self.tester: Optional[ComponentTester] = None

    def create_tester(self, widget, name: str = "") -> ComponentTester:
        """创建组件测试器"""
        self.tester = ComponentTester(widget, name)
        return self.tester

    def create_business_tester(self) -> BusinessLogicTester:
        """创建业务逻辑测试器"""
        return BusinessLogicTester()

    def simulate_ide_startup(self):
        """模拟 IDE 启动"""
        # 等待组件加载
        wait_for(lambda: self.ide is not None, timeout=3.0)

    def simulate_ide_shutdown(self):
        """模拟 IDE 关闭"""
        if self.ide:
            self.ide.close()
            self.ide.deleteLater()


# ─────────────────────────────────────────────────────────────────────────────
# ActivityBar 测试
# ─────────────────────────────────────────────────────────────────────────────

class TestActivityBar(IDEComponentTest):
    """ActivityBar 活动栏测试"""

    def setUp(self):
        """设置测试"""
        try:
            from presentation.modules.ide.opencode_ide_panel import OpenCodeIDEPanel
            self.ide = OpenCodeIDEPanel()
            self.tester = self.create_tester(self.ide.activity_bar, "ActivityBar")
        except ImportError:
            self.skip("OpenCodeIDEPanel not available")

    @screenshot_on_failure()
    def test_activity_bar_visible(self):
        """测试活动栏可见"""
        self.tester.assert_visible()

    @screenshot_on_failure()
    def test_icon_buttons_exist(self):
        """测试图标按钮存在"""
        buttons = self.tester.get_children()
        self.assert_true(len(buttons) > 0, "ActivityBar should have buttons")

    def test_icon_buttons_clickable(self):
        """测试图标按钮可点击"""
        buttons = self.tester.get_children()

        for button in buttons[:5]:  # 测试前5个
            tester = ComponentTester(button)
            tester.assert_enabled()

    def test_selected_icon_state(self):
        """测试选中状态"""
        # 默认选中 Chat
        pass

    def tearDown(self):
        if self.ide:
            self.ide.deleteLater()


# ─────────────────────────────────────────────────────────────────────────────
# ChatPanel 测试
# ─────────────────────────────────────────────────────────────────────────────

class TestChatPanel(IDEComponentTest):
    """ChatPanel 聊天面板测试"""

    def setUp(self):
        try:
            from presentation.modules.ide.opencode_ide_panel import OpenCodeIDEPanel
            self.ide = OpenCodeIDEPanel()
            self.tester = self.create_tester(self.ide.chat_panel, "ChatPanel")
        except ImportError:
            self.skip("OpenCodeIDEPanel not available")

    @screenshot_on_failure()
    def test_chat_panel_visible(self):
        """测试聊天面板可见"""
        self.tester.assert_visible()

    def test_message_list_exists(self):
        """测试消息列表存在"""
        message_list = self.tester.find_child("messageList")
        self.assert_not_none(message_list)

    def test_input_area_exists(self):
        """测试输入区域存在"""
        input_area = self.tester.find_child("inputArea")
        self.assert_not_none(input_area)

    def test_send_button_enabled(self):
        """测试发送按钮启用"""
        send_btn = self.tester.find_child("sendButton")
        if send_btn:
            tester = ComponentTester(send_btn)
            tester.assert_enabled()

    @screenshot_on_failure()
    def test_input_text_and_send(self):
        """测试输入文本并发送"""
        input_area = self.tester.find_child("inputArea")
        if input_area:
            tester = ComponentTester(input_area)
            tester.type("Hello, OpenCode!")
            text = tester.get_text()
            self.assert_contains(text, "Hello")

    def tearDown(self):
        if self.ide:
            self.ide.deleteLater()


# ─────────────────────────────────────────────────────────────────────────────
# MessageBubble 测试
# ─────────────────────────────────────────────────────────────────────────────

class TestMessageBubble(IDEComponentTest):
    """MessageBubble 消息气泡测试"""

    def setUp(self):
        try:
            from presentation.modules.ide.opencode_ide_panel import OpenCodeIDEPanel
            self.ide = OpenCodeIDEPanel()
        except ImportError:
            self.skip("OpenCodeIDEPanel not available")

    def test_user_message_bubble(self):
        """测试用户消息气泡"""
        # 模拟用户消息
        business_tester = self.create_business_tester()
        from .business_logic_tester import MockMessage

        messages = [
            MockMessage(role="user", content="Test message"),
            MockMessage(role="assistant", content="Response"),
        ]

        result = business_tester.test_message_rendering(messages)
        self.assert_true(result["user_messages"] == 1)
        self.assert_true(result["assistant_messages"] == 1)

    def test_assistant_message_bubble(self):
        """测试助手消息气泡"""
        from .business_logic_tester import MockMessage

        messages = [
            MockMessage(
                role="assistant",
                content="I can help you with that.",
                thinking="Let me analyze this problem..."
            )
        ]

        business_tester = self.create_business_tester()
        result = business_tester.test_message_rendering(messages)
        self.assert_true(result["with_thinking"] == 1)

    def test_streaming_message(self):
        """测试流式消息"""
        from .business_logic_tester import MockMessage

        messages = [
            MockMessage(
                role="assistant",
                content="",
                is_streaming=True
            )
        ]

        business_tester = self.create_business_tester()
        result = business_tester.test_message_rendering(messages)
        self.assert_true(result["streaming_messages"] == 1)

    def tearDown(self):
        if self.ide:
            self.ide.deleteLater()


# ─────────────────────────────────────────────────────────────────────────────
# EditorPanel 测试
# ─────────────────────────────────────────────────────────────────────────────

class TestEditorPanel(IDEComponentTest):
    """EditorPanel 编辑器面板测试"""

    def setUp(self):
        try:
            from presentation.modules.ide.opencode_ide_panel import OpenCodeIDEPanel
            self.ide = OpenCodeIDEPanel()
            self.tester = self.create_tester(self.ide.editor_panel, "EditorPanel")
        except ImportError:
            self.skip("OpenCodeIDEPanel not available")

    @screenshot_on_failure()
    def test_editor_panel_visible(self):
        """测试编辑器面板可见"""
        self.tester.assert_visible()

    def test_tab_widget_exists(self):
        """测试标签页组件存在"""
        tab_widget = self.tester.find_child("tabWidget")
        self.assert_not_none(tab_widget)

    def test_status_bar_exists(self):
        """测试状态栏存在"""
        status_bar = self.tester.find_child("statusBar")
        self.assert_not_none(status_bar)

    def test_create_new_tab(self):
        """测试创建新标签页"""
        # 模拟创建新标签
        pass

    def test_close_tab(self):
        """测试关闭标签页"""
        # 模拟关闭标签
        pass

    def tearDown(self):
        if self.ide:
            self.ide.deleteLater()


# ─────────────────────────────────────────────────────────────────────────────
# PipelineProgress 测试
# ─────────────────────────────────────────────────────────────────────────────

class TestPipelineProgress(IDEComponentTest):
    """PipelineProgress 流水线测试"""

    def setUp(self):
        try:
            from presentation.modules.ide.opencode_ide_panel import OpenCodeIDEPanel
            self.ide = OpenCodeIDEPanel()
        except ImportError:
            self.skip("OpenCodeIDEPanel not available")

    def test_pipeline_stages(self):
        """测试流水线阶段"""
        from .business_logic_tester import MockPipelineStage

        stages = [
            MockPipelineStage(name="Write", status="success", progress=1.0),
            MockPipelineStage(name="Test", status="running", progress=0.5),
            MockPipelineStage(name="Fix", status="pending", progress=0.0),
            MockPipelineStage(name="Publish", status="pending", progress=0.0),
        ]

        business_tester = self.create_business_tester()
        result = business_tester.test_pipeline_progress(stages)

        self.assert_true(result["completed_stages"] == 1)
        self.assert_true(result["current_stage"] == "Test")
        self.assert_true(result["passed"])

    def test_pipeline_stage_transitions(self):
        """测试阶段状态转换"""
        business_tester = self.create_business_tester()

        transitions = [
            ("pending", "running"),
            ("running", "success"),
        ]

        result = business_tester.test_pipeline_stage_transitions("Write", transitions)
        self.assert_true(result["valid_transitions"] == 2)
        self.assert_true(result["passed"])

    def tearDown(self):
        if self.ide:
            self.ide.deleteLater()


# ─────────────────────────────────────────────────────────────────────────────
# ToolCallTimeline 测试
# ─────────────────────────────────────────────────────────────────────────────

class TestToolCallTimeline(IDEComponentTest):
    """ToolCallTimeline 工具调用时间线测试"""

    def setUp(self):
        try:
            from presentation.modules.ide.opencode_ide_panel import OpenCodeIDEPanel
            self.ide = OpenCodeIDEPanel()
        except ImportError:
            self.skip("OpenCodeIDEPanel not available")

    def test_tool_call_sequence(self):
        """测试工具调用序列"""
        from .business_logic_tester import MockToolCall
        from datetime import datetime, timedelta

        start = datetime.now()
        calls = [
            MockToolCall(
                tool_name="ReadFile",
                status="running",
                start_time=start
            ),
            MockToolCall(
                tool_name="ReadFile",
                status="success",
                start_time=start,
                end_time=start + timedelta(seconds=0.5),
                result={"content": "file content"}
            ),
        ]

        business_tester = self.create_business_tester()
        result = business_tester.test_tool_call_timeline(calls)

        self.assert_true(result["success"] == 1)
        self.assert_true(result["passed"])

    def test_tool_call_error_handling(self):
        """测试工具调用错误处理"""
        from .business_logic_tester import MockToolCall
        from datetime import datetime

        call = MockToolCall(
            tool_name="ReadFile",
            status="failed",
            error="File not found"
        )

        business_tester = self.create_business_tester()
        result = business_tester.test_tool_call_timeline([call])

        self.assert_true(result["failed"] == 1)
        self.assert_true(result["passed"])

    def tearDown(self):
        if self.ide:
            self.ide.deleteLater()


# ─────────────────────────────────────────────────────────────────────────────
# 集成测试
# ─────────────────────────────────────────────────────────────────────────────

class TestOpenCodeIDEIntegration(IDEComponentTest):
    """OpenCode IDE 集成测试"""

    def setUp(self):
        try:
            from presentation.modules.ide.opencode_ide_panel import OpenCodeIDEPanel
            self.ide = OpenCodeIDEPanel()
        except ImportError:
            self.skip("OpenCodeIDEPanel not available")

    def test_ide_startup(self):
        """测试 IDE 启动"""
        self.assert_not_none(self.ide)
        self.assert_true(self.ide.isVisible())

    def test_chat_to_editor_workflow(self):
        """测试聊天到编辑器工作流"""
        # 输入消息
        # 等待响应
        # 打开编辑器
        # 验证代码显示
        pass

    def test_theme_switching(self):
        """测试主题切换"""
        business_tester = self.create_business_tester()

        themes = ["dark", "light"]
        result = business_tester.test_theme_switching(
            themes,
            lambda t: setattr(self.ide, 'theme', t)
        )

        self.assert_true(result["passed"])

    def test_layout_adjustment(self):
        """测试布局调整"""
        business_tester = self.create_business_tester()

        result = business_tester.test_layout_adjustment(
            current_layout="split",
            available_layouts=["split", "chat-only", "editor-only"],
            expected_ratio={"chat": 0.6, "editor": 0.4}
        )

        self.assert_true(result["ratio_correct"])

    def tearDown(self):
        if self.ide:
            self.ide.deleteLater()


# ─────────────────────────────────────────────────────────────────────────────
# IDETestSuite
# ─────────────────────────────────────────────────────────────────────────────

class IDETestSuite:
    """
    IDE 测试套件

    Usage:
        suite = IDETestSuite("OpenCode IDE Tests")
        suite.add_test(TestActivityBar())
        suite.add_test(TestChatPanel())
        ...

        runner = TestRunner()
        runner.add_suite(suite)
        result = runner.run()
    """

    def __init__(self, name: str = "OpenCode IDE Tests"):
        self.name = name
        self._tests: List[IDEComponentTest] = []

    def add_test(self, test: IDEComponentTest):
        """添加测试"""
        self._tests.append(test)

    def add_tests(self, tests: List[IDEComponentTest]):
        """批量添加测试"""
        self._tests.extend(tests)

    def run(self, pattern: str = "test_*", verbose: bool = True):
        """运行测试套件"""
        from .test_base import TestSuite

        suite = TestSuite(self.name)
        for test in self._tests:
            for method_name in dir(test):
                if method_name.startswith(pattern.replace("*", "")):
                    method = getattr(test, method_name)
                    if callable(method):
                        suite.add_test(lambda m=method, t=test: t.run_test(m))

        return suite.run(pattern=pattern, verbose=verbose)


# ─────────────────────────────────────────────────────────────────────────────
# 便捷运行函数
# ─────────────────────────────────────────────────────────────────────────────

def run_ide_tests(
    test_classes: List[type] = None,
    output_dir: str = "test_results",
    screenshot_dir: str = "test_screenshots"
) -> Dict[str, Any]:
    """
    便捷运行函数

    Usage:
        results = run_ide_tests()
        print(f"Passed: {results['passed']}/{results['total']}")
    """
    # 默认测试类
    if test_classes is None:
        test_classes = [
            TestActivityBar,
            TestChatPanel,
            TestEditorPanel,
            TestPipelineProgress,
            TestToolCallTimeline,
        ]

    runner = TestRunner(
        output_dir=output_dir,
        screenshot_dir=screenshot_dir,
        verbose=True
    )

    suite = IDETestSuite("OpenCode IDE Tests")
    for test_class in test_classes:
        try:
            suite.add_test(test_class())
        except Exception as e:
            print(f"Warning: Could not add {test_class.__name__}: {e}")

    result = runner.run()

    return {
        "total": result.total,
        "passed": result.passed,
        "failed": result.failed,
        "success_rate": result.success_rate,
        "duration": result.duration,
        "results": result.results
    }


if __name__ == "__main__":
    # 直接运行测试
    app = QApplication(sys.argv)
    results = run_ide_tests()
    app.quit()
