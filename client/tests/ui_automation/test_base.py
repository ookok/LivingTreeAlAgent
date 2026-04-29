"""
测试框架基础类

提供：
- TestCase：测试用例基类
- TestRunner：测试运行器
- wait_for：等待条件
- 装饰器：screenshot_on_failure 等
"""

import os
import time
import traceback
from typing import Callable, Optional, Any, List, Dict
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps
import unittest


# ─────────────────────────────────────────────────────────────────────────────
# 等待机制
# ─────────────────────────────────────────────────────────────────────────────

def wait_for(
    condition: Callable[[], bool],
    timeout: float = 5.0,
    interval: float = 0.1,
    description: str = "condition"
) -> bool:
    """
    等待条件满足

    Args:
        condition: 返回 bool 的条件函数
        timeout: 超时时间（秒）
        interval: 检查间隔（秒）
        description: 条件描述（用于日志）

    Returns:
        True if condition met, False if timeout
    """
    start = time.time()
    while time.time() - start < timeout:
        try:
            if condition():
                return True
        except Exception:
            pass
        time.sleep(interval)
    return False


def wait_until(
    func: Callable[[], Any],
    expected: Any,
    timeout: float = 5.0,
    interval: float = 0.1
) -> tuple[bool, Any]:
    """
    等待函数返回期望值

    Returns:
        (success, actual_value)
    """
    start = time.time()
    while time.time() - start < timeout:
        try:
            result = func()
            if result == expected:
                return True, result
        except Exception:
            pass
        time.sleep(interval)
    return False, func() if not wait_for(lambda: False) else None


def ensure_visible(widget) -> bool:
    """确保 widget 可见"""
    from PyQt6.QtWidgets import QWidget
    if isinstance(widget, QWidget):
        return widget.isVisible()
    return False


# ─────────────────────────────────────────────────────────────────────────────
# 截图装饰器
# ─────────────────────────────────────────────────────────────────────────────

def screenshot_on_failure(screenshot_dir: str = "test_screenshots"):
    """
    测试失败时自动截图的装饰器

    Usage:
        @screenshot_on_failure()
        def test_my_feature(self):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                # 截图保存
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                test_name = func.__name__
                screenshot_path = os.path.join(
                    screenshot_dir,
                    f"FAIL_{test_name}_{timestamp}.png"
                )

                os.makedirs(screenshot_dir, exist_ok=True)

                # 尝试截图
                try:
                    from PyQt6.QtWidgets import QApplication
                    app = QApplication.instance()
                    if app:
                        # 抓取主窗口
                        for widget in app.topLevelWidgets():
                            if widget.isVisible():
                                widget.grab().save(screenshot_path)
                                break
                except Exception:
                    pass

                # 重新抛出异常
                raise

        return wrapper
    return decorator


# ─────────────────────────────────────────────────────────────────────────────
# 测试结果
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TestResult:
    """单个测试结果"""
    name: str
    passed: bool
    duration: float
    error: Optional[str] = None
    screenshot: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TestSuiteResult:
    """测试套件结果"""
    suite_name: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    duration: float = 0.0
    results: List[TestResult] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.passed / self.total * 100


# ─────────────────────────────────────────────────────────────────────────────
# TestCase 基类
# ─────────────────────────────────────────────────────────────────────────────

class TestCase:
    """
    测试用例基类

    Usage:
        class TestMyFeature(TestCase):
            def setUp(self):
                self.app = MyApp()

            def test_feature(self):
                self.assert_true(self.app.is_ready())

            def tearDown(self):
                self.app.close()
    """

    def __init__(self, name: str = ""):
        self.name = name or self.__class__.__name__
        self._results: List[TestResult] = []
        self._start_time: float = 0
        self._current_test: Optional[str] = None

    def setUp(self):
        """设置测试环境"""
        pass

    def tearDown(self):
        """清理测试环境"""
        pass

    def assert_true(self, condition: bool, message: str = ""):
        """断言为真"""
        if not condition:
            raise AssertionError(message or "Expected True")

    def assert_false(self, condition: bool, message: str = ""):
        """断言为假"""
        if condition:
            raise AssertionError(message or "Expected False")

    def assert_equal(self, actual: Any, expected: Any, message: str = ""):
        """断言相等"""
        if actual != expected:
            raise AssertionError(
                message or f"Expected {expected!r}, got {actual!r}"
            )

    def assert_not_none(self, value: Any, message: str = ""):
        """断言不为 None"""
        if value is None:
            raise AssertionError(message or "Expected not None")

    def assert_contains(self, container: Any, item: Any, message: str = ""):
        """断言包含"""
        if item not in container:
            raise AssertionError(
                message or f"Expected {item!r} in {container!r}"
            )

    def skip(self, reason: str = ""):
        """跳过测试"""
        raise unittest.SkipTest(reason)

    def run_test(self, test_method: Callable) -> TestResult:
        """运行单个测试方法"""
        self._start_time = time.time()
        self._current_test = test_method.__name__
        error = None
        screenshot = None

        try:
            self.setUp()
            test_method()
            passed = True
        except unittest.SkipTest as e:
            passed = True
            error = f"SKIPPED: {e}"
        except AssertionError as e:
            passed = False
            error = str(e)
            # 自动截图
            screenshot = self._capture_screenshot()
        except Exception as e:
            passed = False
            error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
            screenshot = self._capture_screenshot()
        finally:
            try:
                self.tearDown()
            except Exception:
                pass

        duration = time.time() - self._start_time

        return TestResult(
            name=self._current_test,
            passed=passed,
            duration=duration,
            error=error,
            screenshot=screenshot
        )

    def _capture_screenshot(self) -> Optional[str]:
        """截图"""
        try:
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                path = f"test_screenshots/{self.name}_{self._current_test}_{timestamp}.png"
                os.makedirs("test_screenshots", exist_ok=True)

                for widget in app.topLevelWidgets():
                    if widget.isVisible():
                        widget.grab().save(path)
                        return path
        except Exception:
            pass
        return None


# ─────────────────────────────────────────────────────────────────────────────
# TestRunner
# ─────────────────────────────────────────────────────────────────────────────

class TestRunner:
    """
    测试运行器

    Usage:
        runner = TestRunner(output_dir="test_results")
        runner.add_suite(MyTestSuite())
        result = runner.run()
        print(f"Passed: {result.passed}/{result.total}")
    """

    def __init__(
        self,
        output_dir: str = "test_results",
        screenshot_dir: str = "test_screenshots",
        verbose: bool = True
    ):
        self.output_dir = output_dir
        self.screenshot_dir = screenshot_dir
        self.verbose = verbose
        self._suites: List[Any] = []
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(screenshot_dir, exist_ok=True)

    def add_suite(self, suite: 'TestSuite'):
        """添加测试套件"""
        self._suites.append(suite)

    def run(self, pattern: str = "test_*") -> TestSuiteResult:
        """运行所有测试"""
        total_result = TestSuiteResult(suite_name="All Tests")

        for suite in self._suites:
            if self.verbose:
                print(f"\n{'='*60}")
                print(f"Running: {suite.name}")
                print('='*60)

            suite_result = suite.run(pattern=pattern, verbose=self.verbose)
            total_result.total += suite_result.total
            total_result.passed += suite_result.passed
            total_result.failed += suite_result.failed
            total_result.skipped += suite_result.skipped
            total_result.results.extend(suite_result.results)
            total_result.duration += suite_result.duration

        if self.verbose:
            print(f"\n{'='*60}")
            print(f"Total: {total_result.total} | "
                  f"Passed: {total_result.passed} | "
                  f"Failed: {total_result.failed} | "
                  f"Success Rate: {total_result.success_rate:.1f}%")
            print('='*60)

        # 生成报告
        self._save_report(total_result)

        return total_result

    def _save_report(self, result: TestSuiteResult):
        """保存测试报告"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(self.output_dir, f"report_{timestamp}.txt")

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(f"Test Report - {timestamp}\n")
            f.write('='*60 + '\n\n')
            f.write(f"Total: {result.total}\n")
            f.write(f"Passed: {result.passed}\n")
            f.write(f"Failed: {result.failed}\n")
            f.write(f"Skipped: {result.skipped}\n")
            f.write(f"Success Rate: {result.success_rate:.1f}%\n")
            f.write(f"Duration: {result.duration:.2f}s\n\n")

            for test_result in result.results:
                status = "✓" if test_result.passed else "✗"
                f.write(f"\n{status} {test_result.name} ({test_result.duration:.3f}s)\n")
                if test_result.error:
                    f.write(f"  Error: {test_result.error}\n")
                if test_result.screenshot:
                    f.write(f"  Screenshot: {test_result.screenshot}\n")


class TestSuite:
    """测试套件"""

    def __init__(self, name: str):
        self.name = name
        self._tests: List[Callable] = []

    def add_test(self, test_method: Callable):
        """添加测试方法"""
        self._tests.append(test_method)

    def run(self, pattern: str = "test_*", verbose: bool = True) -> TestSuiteResult:
        """运行测试套件"""
        result = TestSuiteResult(suite_name=self.name)

        for test_method in self._tests:
            if not test_method.__name__.startswith(pattern.replace("*", "")):
                continue

            test_case = test_method.__self__
            test_result = test_case.run_test(test_method)

            result.results.append(test_result)
            result.total += 1
            if test_result.passed:
                result.passed += 1
            else:
                result.failed += 1
            result.duration += test_result.duration

            if verbose:
                status = "✓" if test_result.passed else "✗"
                print(f"  {status} {test_result.name} ({test_result.duration:.3f}s)")
                if test_result.error and not test_result.error.startswith("SKIPPED"):
                    print(f"    Error: {test_result.error[:100]}...")

        return result
