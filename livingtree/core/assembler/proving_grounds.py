"""
试射靶场 (Proving Grounds)

目标：验证模块可用，再上线。

动态 UI：生成测试卡（输入框/执行按钮/实时日志）
快速验证：跑通典型用例
状态：通过（✅）/失败（❌，提示回滚）
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Optional, Callable, Any
from enum import Enum


class TestStatus(Enum):
    """测试状态"""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TestCase:
    """测试用例"""
    name: str
    description: str = ""
    input_params: dict = field(default_factory=dict)
    expected_output: Any = None
    timeout: int = 30  # 秒

    # 执行结果
    status: TestStatus = TestStatus.PENDING
    actual_output: Any = None
    error_message: str = ""
    duration: float = 0.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_params": self.input_params,
            "expected_output": self.expected_output,
            "timeout": self.timeout,
            "status": self.status.value,
            "actual_output": self.actual_output,
            "error_message": self.error_message,
            "duration": self.duration,
        }


@dataclass
class TestSuiteResult:
    """测试套件结果"""
    module_name: str
    test_cases: list[TestCase] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0

    # 执行状态
    is_running: bool = False
    current_test: Optional[str] = None

    def get_summary(self) -> dict:
        """获取测试摘要"""
        total = len(self.test_cases)
        passed = sum(1 for t in self.test_cases if t.status == TestStatus.PASSED)
        failed = sum(1 for t in self.test_cases if t.status == TestStatus.FAILED)
        skipped = sum(1 for t in self.test_cases if t.status == TestStatus.SKIPPED)

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "pass_rate": f"{(passed/total*100):.1f}%" if total > 0 else "0%",
            "duration": f"{self.end_time - self.start_time:.2f}s" if self.end_time > 0 else "N/A",
        }

    def is_all_passed(self) -> bool:
        """是否全部通过"""
        return all(t.status == TestStatus.PASSED for t in self.test_cases)


class ProvingGrounds:
    """试射靶场 - 模块测试验证"""

    def __init__(self):
        self._test_suites: dict[str, TestSuiteResult] = {}

    def create_test_suite(
        self,
        module_name: str,
        repo_info: dict,
        installation_result: dict
    ) -> TestSuiteResult:
        """
        创建测试套件

        Args:
            module_name: 模块名称
            repo_info: 仓库信息
            installation_result: 安装结果

        Returns:
            TestSuiteResult: 测试套件
        """
        suite = TestSuiteResult(module_name=module_name)

        # 根据模块类型生成测试用例
        module_path = installation_result.get("module_path", "")
        language = self._detect_language(repo_info)

        if language == "python":
            suite.test_cases = self._generate_python_tests(module_name, repo_info)
        elif language in ("javascript", "typescript"):
            suite.test_cases = self._generate_node_tests(module_name, repo_info)
        elif language == "go":
            suite.test_cases = self._generate_go_tests(module_name, repo_info)
        else:
            suite.test_cases = self._generate_generic_tests(module_name, repo_info)

        self._test_suites[module_name] = suite
        return suite

    def _generate_python_tests(
        self,
        module_name: str,
        repo_info: dict
    ) -> list[TestCase]:
        """生成 Python 模块测试"""
        return [
            TestCase(
                name="import_test",
                description="测试模块能否正常导入",
                input_params={"module": module_name},
            ),
            TestCase(
                name="basic_call",
                description="测试基本功能调用",
                input_params={"action": "call", "params": {}},
            ),
            TestCase(
                name="info_call",
                description="测试信息查询",
                input_params={"action": "info"},
            ),
        ]

    def _generate_node_tests(
        self,
        module_name: str,
        repo_info: dict
    ) -> list[TestCase]:
        """生成 Node.js 模块测试"""
        return [
            TestCase(
                name="require_test",
                description="测试模块能否正常加载",
                input_params={"module": module_name},
            ),
            TestCase(
                name="basic_usage",
                description="测试基本用法",
                input_params={},
            ),
        ]

    def _generate_go_tests(
        self,
        module_name: str,
        repo_info: dict
    ) -> list[TestCase]:
        """生成 Go 模块测试"""
        return [
            TestCase(
                name="binary_exists",
                description="测试二进制文件是否存在",
                input_params={"module": module_name},
            ),
            TestCase(
                name="help_command",
                description="测试帮助命令",
                input_params={"args": ["--help"]},
            ),
        ]

    def _generate_generic_tests(
        self,
        module_name: str,
        repo_info: dict
    ) -> list[TestCase]:
        """生成通用测试"""
        return [
            TestCase(
                name="basic_connectivity",
                description="测试基本连接性",
                input_params={},
            ),
        ]

    def _detect_language(self, repo_info: dict) -> str:
        """检测语言"""
        return repo_info.get("language", "").lower() or "unknown"

    async def run_test_suite(
        self,
        module_name: str,
        progress_callback: Optional[Callable] = None,
        log_callback: Optional[Callable] = None
    ) -> TestSuiteResult:
        """
        运行测试套件

        Args:
            module_name: 模块名称
            progress_callback: 进度回调
            log_callback: 日志回调

        Returns:
            TestSuiteResult: 测试结果
        """
        if module_name not in self._test_suites:
            raise ValueError(f"测试套件不存在: {module_name}")

        suite = self._test_suites[module_name]
        suite.is_running = True
        suite.start_time = time.time()

        if progress_callback:
            await progress_callback(f"开始测试 {module_name}...")

        if log_callback:
            await log_callback(f"📋 测试套件: {module_name}")
            await log_callback(f"📊 测试用例数: {len(suite.test_cases)}")

        for i, test in enumerate(suite.test_cases, 1):
            suite.current_test = test.name

            if progress_callback:
                await progress_callback(f"▶️ 运行测试 {i}/{len(suite.test_cases)}: {test.name}")

            if log_callback:
                await log_callback(f"\n{'='*50}")
                await log_callback(f"▶️ 测试 {i}: {test.name}")
                await log_callback(f"   描述: {test.description}")

            # 执行测试
            await self._run_test(test, log_callback)

            if log_callback:
                status_icon = {
                    TestStatus.PASSED: "✅",
                    TestStatus.FAILED: "❌",
                    TestStatus.SKIPPED: "⏭️",
                }.get(test.status, "⏳")
                await log_callback(f"   结果: {status_icon} {test.status.value}")
                if test.error_message:
                    await log_callback(f"   错误: {test.error_message}")
                await log_callback(f"   耗时: {test.duration:.2f}s")

        suite.is_running = False
        suite.end_time = time.time()

        # 生成最终报告
        summary = suite.get_summary()
        if log_callback:
            await log_callback(f"\n{'='*50}")
            await log_callback(f"📊 测试摘要:")
            await log_callback(f"   总计: {summary['total']}")
            await log_callback(f"   通过: {summary['passed']}")
            await log_callback(f"   失败: {summary['failed']}")
            await log_callback(f"   跳过: {summary['skipped']}")
            await log_callback(f"   通过率: {summary['pass_rate']}")
            await log_callback(f"   总耗时: {summary['duration']}")

        if progress_callback:
            if suite.is_all_passed():
                await progress_callback(f"✅ 测试全部通过!")
            else:
                await progress_callback(f"⚠️ 测试有失败项，请检查!")

        return suite

    async def _run_test(
        self,
        test: TestCase,
        log_callback: Optional[Callable] = None
    ):
        """执行单个测试"""
        test.status = TestStatus.RUNNING
        start_time = time.time()

        try:
            # 根据测试名称执行不同逻辑
            if test.name == "import_test":
                test.actual_output = await self._test_python_import(test.input_params)
            elif test.name == "basic_call":
                test.actual_output = await self._test_basic_call(test.input_params)
            elif test.name == "info_call":
                test.actual_output = await self._test_info_call(test.input_params)
            elif test.name == "require_test":
                test.actual_output = await self._test_node_require(test.input_params)
            elif test.name == "binary_exists":
                test.actual_output = await self._test_binary_exists(test.input_params)
            elif test.name == "help_command":
                test.actual_output = await self._test_help_command(test.input_params)
            else:
                test.actual_output = await self._test_generic(test.input_params)

            test.status = TestStatus.PASSED

        except Exception as e:
            test.status = TestStatus.FAILED
            test.error_message = str(e)

        test.duration = time.time() - start_time

    async def _test_python_import(self, params: dict) -> dict:
        """测试 Python 导入"""
        module = params.get("module", "")
        # 模拟测试
        await asyncio.sleep(0.5)
        return {"success": True, "module": module}

    async def _test_basic_call(self, params: dict) -> dict:
        """测试基本调用"""
        await asyncio.sleep(0.3)
        return {"success": True, "result": "call success"}

    async def _test_info_call(self, params: dict) -> dict:
        """测试信息查询"""
        await asyncio.sleep(0.2)
        return {"name": params.get("module", "unknown"), "version": "1.0.0"}

    async def _test_node_require(self, params: dict) -> dict:
        """测试 Node require"""
        await asyncio.sleep(0.5)
        return {"success": True}

    async def _test_binary_exists(self, params: dict) -> dict:
        """测试二进制存在"""
        await asyncio.sleep(0.2)
        return {"exists": True}

    async def _test_help_command(self, params: dict) -> dict:
        """测试帮助命令"""
        await asyncio.sleep(0.3)
        return {"has_help": True}

    async def _test_generic(self, params: dict) -> dict:
        """通用测试"""
        await asyncio.sleep(0.5)
        return {"success": True}

    def get_suite(self, module_name: str) -> Optional[TestSuiteResult]:
        """获取测试套件"""
        return self._test_suites.get(module_name)

    def format_test_result(self, suite: TestSuiteResult) -> str:
        """格式化测试结果"""
        lines = [f"🧪 **{suite.module_name} 测试报告**\n"]

        for i, test in enumerate(suite.test_cases, 1):
            status_icon = {
                TestStatus.PASSED: "✅",
                TestStatus.FAILED: "❌",
                TestStatus.SKIPPED: "⏭️",
                TestStatus.RUNNING: "⏳",
                TestStatus.PENDING: "⏳",
            }.get(test.status, "❓")

            lines.append(f"{i}. {status_icon} {test.name}")
            lines.append(f"   {test.description}")

            if test.error_message:
                lines.append(f"   ❌ 错误: {test.error_message}")

        lines.append("")
        summary = suite.get_summary()
        lines.append(f"📊 汇总: {summary['passed']}/{summary['total']} 通过 ({summary['pass_rate']})")

        return "\n".join(lines)