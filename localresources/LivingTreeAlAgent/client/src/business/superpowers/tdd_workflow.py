"""
TDD 工作流集成

实现测试驱动开发流程：红-绿-重构
"""

import asyncio
import time
import unittest
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, field
import re


@dataclass
class TestCase:
    """测试用例"""
    test_id: str
    name: str
    description: str
    input: Dict[str, Any]
    expected_output: Any
    actual_output: Optional[Any] = None
    passed: Optional[bool] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None


@dataclass
class TestResult:
    """测试结果"""
    test_id: str
    name: str
    passed: bool
    error: Optional[str] = None
    execution_time: Optional[float] = None
    expected: Optional[Any] = None
    actual: Optional[Any] = None


class TestRunner:
    """
    测试运行器

    负责运行测试用例
    """

    def __init__(self):
        self.test_history: List[TestResult] = []

    async def run_test(
        self,
        test_case: TestCase,
        implementation: Callable
    ) -> TestResult:
        """
        运行单个测试

        Args:
            test_case: 测试用例
            implementation: 实现函数

        Returns:
            TestResult: 测试结果
        """
        start_time = time.time()

        try:
            actual_output = implementation(test_case.input)
            execution_time = time.time() - start_time

            # 比较预期输出和实际输出
            passed = self._compare_outputs(test_case.expected_output, actual_output)

            test_case.actual_output = actual_output
            test_case.passed = passed
            test_case.execution_time = execution_time

            result = TestResult(
                test_id=test_case.test_id,
                name=test_case.name,
                passed=passed,
                execution_time=execution_time,
                expected=test_case.expected_output,
                actual=actual_output
            )

        except Exception as e:
            execution_time = time.time() - start_time
            test_case.error = str(e)
            test_case.passed = False
            test_case.execution_time = execution_time

            result = TestResult(
                test_id=test_case.test_id,
                name=test_case.name,
                passed=False,
                error=str(e),
                execution_time=execution_time,
                expected=test_case.expected_output
            )

        self.test_history.append(result)
        return result

    async def run_tests(
        self,
        test_cases: List[TestCase],
        implementation: Callable
    ) -> List[TestResult]:
        """
        运行多个测试

        Args:
            test_cases: 测试用例列表
            implementation: 实现函数

        Returns:
            List[TestResult]: 测试结果列表
        """
        results = []
        for test_case in test_cases:
            result = await self.run_test(test_case, implementation)
            results.append(result)
        return results

    def _compare_outputs(self, expected: Any, actual: Any) -> bool:
        """
        比较输出

        Args:
            expected: 预期输出
            actual: 实际输出

        Returns:
            bool: 是否匹配
        """
        if isinstance(expected, dict) and isinstance(actual, dict):
            return self._compare_dicts(expected, actual)
        elif isinstance(expected, list) and isinstance(actual, list):
            return self._compare_lists(expected, actual)
        else:
            return expected == actual

    def _compare_dicts(self, expected: Dict, actual: Dict) -> bool:
        """
        比较字典

        Args:
            expected: 预期字典
            actual: 实际字典

        Returns:
            bool: 是否匹配
        """
        if set(expected.keys()) != set(actual.keys()):
            return False

        for key, expected_value in expected.items():
            actual_value = actual.get(key)
            if not self._compare_outputs(expected_value, actual_value):
                return False

        return True

    def _compare_lists(self, expected: List, actual: List) -> bool:
        """
        比较列表

        Args:
            expected: 预期列表
            actual: 实际列表

        Returns:
            bool: 是否匹配
        """
        if len(expected) != len(actual):
            return False

        for expected_item, actual_item in zip(expected, actual):
            if not self._compare_outputs(expected_item, actual_item):
                return False

        return True

    def get_test_history(self) -> List[TestResult]:
        """
        获取测试历史

        Returns:
            List[TestResult]: 测试历史
        """
        return self.test_history

    def get_test_stats(self) -> Dict[str, Any]:
        """
        获取测试统计

        Returns:
            Dict: 测试统计
        """
        if not self.test_history:
            return {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "success_rate": 0.0
            }

        total = len(self.test_history)
        passed = sum(1 for result in self.test_history if result.passed)
        failed = total - passed

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "success_rate": passed / total if total > 0 else 0.0
        }


class TDDWorkflow:
    """
    TDD 工作流

    实现红-绿-重构流程
    """

    def __init__(self, test_runner: Optional[TestRunner] = None):
        self.test_runner = test_runner or TestRunner()
        self.cycles: List[Dict[str, Any]] = []

    async def run_cycle(
        self,
        feature: str,
        test_cases: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        运行 TDD 循环

        Args:
            feature: 功能描述
            test_cases: 测试用例

        Returns:
            Dict: TDD 循环结果
        """
        cycle_id = str(time.time())
        cycle = {
            "cycle_id": cycle_id,
            "feature": feature,
            "test_cases": test_cases,
            "phases": [],
            "start_time": time.time()
        }

        # 红阶段：运行测试，应该失败
        red_result = await self._red_phase(test_cases)
        cycle["phases"].append({
            "phase": "red",
            "result": red_result
        })

        # 绿阶段：实现功能，使测试通过
        green_result = await self._green_phase(feature, test_cases, red_result)
        cycle["phases"].append({
            "phase": "green",
            "result": green_result
        })

        # 重构阶段：优化代码
        refactor_result = await self._refactor_phase(feature, green_result)
        cycle["phases"].append({
            "phase": "refactor",
            "result": refactor_result
        })

        cycle["end_time"] = time.time()
        cycle["duration"] = cycle["end_time"] - cycle["start_time"]
        self.cycles.append(cycle)

        return cycle

    async def _red_phase(
        self,
        test_cases: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        红阶段：运行测试，应该失败

        Args:
            test_cases: 测试用例

        Returns:
            Dict: 红阶段结果
        """
        test_objects = []
        for i, test_info in enumerate(test_cases):
            test_case = TestCase(
                test_id=f"test_{i+1}",
                name=test_info.get("name", f"Test {i+1}"),
                description=test_info.get("description", ""),
                input=test_info.get("input", {}),
                expected_output=test_info.get("expected_output")
            )
            test_objects.append(test_case)

        # 模拟未实现的函数
        def not_implemented(input_data):
            raise NotImplementedError("Function not implemented yet")

        results = await self.test_runner.run_tests(test_objects, not_implemented)

        return {
            "tests": [
                {
                    "test_id": result.test_id,
                    "name": result.name,
                    "passed": result.passed,
                    "error": result.error
                }
                for result in results
            ],
            "passed_count": sum(1 for r in results if r.passed),
            "total_count": len(results),
            "phase": "red"
        }

    async def _green_phase(
        self,
        feature: str,
        test_cases: List[Dict[str, Any]],
        red_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        绿阶段：实现功能，使测试通过

        Args:
            feature: 功能描述
            test_cases: 测试用例
            red_result: 红阶段结果

        Returns:
            Dict: 绿阶段结果
        """
        test_objects = []
        for i, test_info in enumerate(test_cases):
            test_case = TestCase(
                test_id=f"test_{i+1}",
                name=test_info.get("name", f"Test {i+1}"),
                description=test_info.get("description", ""),
                input=test_info.get("input", {}),
                expected_output=test_info.get("expected_output")
            )
            test_objects.append(test_case)

        # 模拟实现函数
        def mock_implementation(input_data):
            # 根据输入返回预期输出
            for test_info in test_cases:
                if test_info.get("input") == input_data:
                    return test_info.get("expected_output")
            return None

        results = await self.test_runner.run_tests(test_objects, mock_implementation)

        return {
            "tests": [
                {
                    "test_id": result.test_id,
                    "name": result.name,
                    "passed": result.passed,
                    "error": result.error
                }
                for result in results
            ],
            "passed_count": sum(1 for r in results if r.passed),
            "total_count": len(results),
            "phase": "green",
            "implementation": "Mock implementation that passes all tests"
        }

    async def _refactor_phase(
        self,
        feature: str,
        green_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        重构阶段：优化代码

        Args:
            feature: 功能描述
            green_result: 绿阶段结果

        Returns:
            Dict: 重构阶段结果
        """
        # 模拟重构过程
        await asyncio.sleep(0.5)

        refactor_suggestions = [
            "提取重复代码到函数",
            "优化算法复杂度",
            "改进变量命名",
            "添加文档注释"
        ]

        return {
            "refactor_suggestions": refactor_suggestions,
            "phase": "refactor",
            "status": "completed"
        }

    def get_cycles(self) -> List[Dict[str, Any]]:
        """
        获取所有 TDD 循环

        Returns:
            List[Dict[str, Any]]: TDD 循环列表
        """
        return self.cycles

    def get_cycle_stats(self) -> Dict[str, Any]:
        """
        获取循环统计

        Returns:
            Dict: 循环统计
        """
        if not self.cycles:
            return {
                "total_cycles": 0,
                "average_duration": 0.0
            }

        total_duration = sum(cycle.get("duration", 0) for cycle in self.cycles)
        return {
            "total_cycles": len(self.cycles),
            "average_duration": total_duration / len(self.cycles)
        }


# 全局实例

_global_tdd_workflow: Optional[TDDWorkflow] = None


def get_tdd_workflow() -> TDDWorkflow:
    """获取 TDD 工作流"""
    global _global_tdd_workflow
    if _global_tdd_workflow is None:
        _global_tdd_workflow = TDDWorkflow()
    return _global_tdd_workflow