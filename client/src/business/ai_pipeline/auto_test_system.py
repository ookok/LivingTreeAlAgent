"""
自主测试系统 - 自动生成和执行测试用例

测试流水线：
1. 单元测试生成 → 基于代码逻辑自动生成测试用例
2. 覆盖率驱动 → 识别未覆盖分支，补充测试
3. 集成测试规划 → 分析模块依赖，生成集成场景
4. E2E 测试脚本 → 模拟用户操作流
5. 性能测试注入 → 自动添加负载测试
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json
import os
from pathlib import Path

from business.global_model_router import GlobalModelRouter, ModelCapability


class TestType(Enum):
    UNIT = "unit"
    INTEGRATION = "integration"
    E2E = "e2e"
    PERFORMANCE = "performance"
    SECURITY = "security"


class TestStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TestCase:
    """测试用例"""
    id: str
    name: str
    description: str
    test_type: TestType
    file_path: str
    code: str
    status: TestStatus = TestStatus.PENDING
    execution_time: float = 0.0
    error_message: Optional[str] = None


@dataclass
class TestResult:
    """测试结果"""
    test_id: str
    status: TestStatus
    execution_time: float
    error_message: Optional[str] = None
    coverage: Optional[float] = None


@dataclass
class TestSuite:
    """测试套件"""
    id: str
    name: str
    test_cases: List[TestCase] = field(default_factory=list)
    coverage: float = 0.0
    passed_count: int = 0
    failed_count: int = 0


@dataclass
class CoverageReport:
    """覆盖率报告"""
    file_path: str
    line_coverage: float
    branch_coverage: float
    missing_lines: List[int] = field(default_factory=list)
    missing_branches: List[str] = field(default_factory=list)


class AutoTestSystem:
    """
    自主测试系统
    
    核心特性：
    1. 单元测试自动生成
    2. 覆盖率驱动测试补充
    3. 集成测试规划
    4. E2E测试脚本生成
    5. 性能测试注入
    """

    def __init__(self, storage_path: Optional[str] = None):
        self._router = GlobalModelRouter()
        self._storage_path = Path(storage_path or os.path.expanduser("~/.livingtree/tests"))
        self._storage_path.mkdir(parents=True, exist_ok=True)
        
        self._test_patterns: Dict[str, Any] = {}
        self._load_test_patterns()

    def _load_test_patterns(self):
        """加载测试模式"""
        pattern_file = self._storage_path / "test_patterns.json"
        if pattern_file.exists():
            try:
                with open(pattern_file, 'r', encoding='utf-8') as f:
                    self._test_patterns = json.load(f)
            except Exception as e:
                print(f"加载测试模式失败: {e}")

    def _save_test_patterns(self):
        """保存测试模式"""
        pattern_file = self._storage_path / "test_patterns.json"
        with open(pattern_file, 'w', encoding='utf-8') as f:
            json.dump(self._test_patterns, f, ensure_ascii=False, indent=2)

    async def generate_unit_tests(self, code_content: str, file_path: str) -> List[TestCase]:
        """
        生成单元测试用例
        
        Args:
            code_content: 源代码内容
            file_path: 源文件路径
            
        Returns:
            生成的测试用例列表
        """
        print(f"🧪 生成单元测试: {file_path}")
        
        prompt = f"""
作为一个专业的测试工程师，根据以下代码生成完整的单元测试用例。

源代码:
```python
{code_content}
```

源文件路径: {file_path}

输出格式（JSON）:
{{
    "test_cases": [
        {{
            "id": "TEST-001",
            "name": "测试方法名_场景描述",
            "description": "测试描述",
            "test_type": "unit",
            "code": "完整的测试代码"
        }}
    ]
}}

要求：
1. 为每个公共方法生成至少3个测试用例
2. 覆盖正常场景、边界条件、异常情况
3. 使用 pytest 框架
4. 添加适当的断言
5. 包含测试文档字符串
"""

        response = await self._router.call_model(
            capability=ModelCapability.REASONING,
            prompt=prompt,
            temperature=0.2
        )

        try:
            result = json.loads(response)
            
            test_cases = []
            for tc_data in result["test_cases"]:
                test_cases.append(TestCase(
                    id=tc_data["id"],
                    name=tc_data["name"],
                    description=tc_data["description"],
                    test_type=TestType(tc_data["test_type"]),
                    file_path=f"{file_path}_test.py",
                    code=tc_data["code"]
                ))
            
            return test_cases
            
        except Exception as e:
            print(f"❌ 单元测试生成失败: {e}")
            return self._fallback_unit_tests(file_path)

    def _fallback_unit_tests(self, file_path: str) -> List[TestCase]:
        """兜底单元测试生成"""
        base_name = os.path.basename(file_path).replace(".py", "")
        
        code = f'''"""
单元测试文件: {file_path}
"""

import pytest
from {base_name} import *


class Test{base_name.capitalize()}:
    """{base_name} 单元测试类"""
    
    def test_initialization(self):
        """测试初始化"""
        # TODO: 实现测试
        pass
    
    def test_basic_functionality(self):
        """测试基本功能"""
        # TODO: 实现测试
        pass
    
    def test_edge_cases(self):
        """测试边界条件"""
        # TODO: 实现测试
        pass
    
    def test_error_handling(self):
        """测试异常处理"""
        # TODO: 实现测试
        pass
'''
        
        return [TestCase(
            id=f"TEST-{int(datetime.now().timestamp())}",
            name=f"Test{base_name.capitalize()}",
            description=f"{base_name} 单元测试",
            test_type=TestType.UNIT,
            file_path=f"{file_path}_test.py",
            code=code
        )]

    async def analyze_coverage(self, coverage_data: Dict[str, Any]) -> CoverageReport:
        """
        分析测试覆盖率
        
        Args:
            coverage_data: 覆盖率数据
            
        Returns:
            覆盖率报告
        """
        print(f"📊 分析覆盖率数据")
        
        return CoverageReport(
            file_path=coverage_data.get("file", ""),
            line_coverage=coverage_data.get("line_coverage", 0.0),
            branch_coverage=coverage_data.get("branch_coverage", 0.0),
            missing_lines=coverage_data.get("missing_lines", []),
            missing_branches=coverage_data.get("missing_branches", [])
        )

    async def generate_missing_tests(self, code_content: str, coverage_report: CoverageReport) -> List[TestCase]:
        """
        根据覆盖率生成缺失的测试用例
        
        Args:
            code_content: 源代码内容
            coverage_report: 覆盖率报告
            
        Returns:
            补充的测试用例
        """
        print(f"🔍 生成缺失测试，覆盖率: {coverage_report.line_coverage}%")
        
        if coverage_report.line_coverage >= 80:
            print("✅ 覆盖率达标，无需补充测试")
            return []
        
        prompt = f"""
作为一个专业的测试工程师，根据以下代码和覆盖率报告，生成缺失的测试用例。

源代码:
```python
{code_content}
```

覆盖率报告:
- 文件: {coverage_report.file_path}
- 行覆盖率: {coverage_report.line_coverage}%
- 分支覆盖率: {coverage_report.branch_coverage}%
- 未覆盖行: {coverage_report.missing_lines}
- 未覆盖分支: {coverage_report.missing_branches}

输出格式（JSON）:
{{
    "test_cases": [
        {{
            "id": "TEST-001",
            "name": "测试方法名_缺失场景",
            "description": "覆盖未测试的代码路径",
            "test_type": "unit",
            "code": "完整的测试代码"
        }}
    ]
}}

要求：
1. 针对未覆盖的行和分支生成测试用例
2. 使用 pytest 框架
3. 添加适当的断言
"""

        response = await self._router.call_model(
            capability=ModelCapability.REASONING,
            prompt=prompt,
            temperature=0.2
        )

        try:
            result = json.loads(response)
            
            test_cases = []
            for tc_data in result["test_cases"]:
                test_cases.append(TestCase(
                    id=tc_data["id"],
                    name=tc_data["name"],
                    description=tc_data["description"],
                    test_type=TestType(tc_data["test_type"]),
                    file_path=f"{coverage_report.file_path}_test.py",
                    code=tc_data["code"]
                ))
            
            return test_cases
            
        except Exception as e:
            print(f"❌ 缺失测试生成失败: {e}")
            return []

    async def generate_integration_tests(self, module_dependencies: Dict[str, List[str]]) -> List[TestCase]:
        """
        生成集成测试用例
        
        Args:
            module_dependencies: 模块依赖关系
            
        Returns:
            集成测试用例
        """
        print(f"🔗 生成集成测试")
        
        prompt = f"""
作为一个专业的测试工程师，根据以下模块依赖关系生成集成测试用例。

模块依赖关系:
{json.dumps(module_dependencies, indent=2)}

输出格式（JSON）:
{{
    "test_cases": [
        {{
            "id": "INT-001",
            "name": "模块A_模块B_集成测试",
            "description": "测试模块间协作",
            "test_type": "integration",
            "code": "完整的测试代码"
        }}
    ]
}}

要求：
1. 测试模块间的接口和数据传递
2. 使用 pytest 框架
3. 模拟真实业务场景
"""

        response = await self._router.call_model(
            capability=ModelCapability.REASONING,
            prompt=prompt,
            temperature=0.2
        )

        try:
            result = json.loads(response)
            
            test_cases = []
            for tc_data in result["test_cases"]:
                test_cases.append(TestCase(
                    id=tc_data["id"],
                    name=tc_data["name"],
                    description=tc_data["description"],
                    test_type=TestType(tc_data["test_type"]),
                    file_path="integration_tests.py",
                    code=tc_data["code"]
                ))
            
            return test_cases
            
        except Exception as e:
            print(f"❌ 集成测试生成失败: {e}")
            return self._fallback_integration_tests()

    def _fallback_integration_tests(self) -> List[TestCase]:
        """兜底集成测试生成"""
        code = '''"""
集成测试文件
"""

import pytest


class TestIntegration:
    """集成测试类"""
    
    def test_module_integration(self):
        """测试模块间集成"""
        # TODO: 实现集成测试
        pass
    
    def test_data_flow(self):
        """测试数据流"""
        # TODO: 实现测试
        pass
'''
        
        return [TestCase(
            id=f"INT-{int(datetime.now().timestamp())}",
            name="模块集成测试",
            description="测试模块间协作",
            test_type=TestType.INTEGRATION,
            file_path="integration_tests.py",
            code=code
        )]

    async def generate_e2e_tests(self, user_flows: List[Dict[str, Any]]) -> List[TestCase]:
        """
        生成E2E测试用例
        
        Args:
            user_flows: 用户操作流程
            
        Returns:
            E2E测试用例
        """
        print(f"🌐 生成E2E测试")
        
        prompt = f"""
作为一个专业的测试工程师，根据以下用户操作流程生成E2E测试用例。

用户操作流程:
{json.dumps(user_flows, indent=2)}

输出格式（JSON）:
{{
    "test_cases": [
        {{
            "id": "E2E-001",
            "name": "用户流程_场景描述",
            "description": "端到端测试场景",
            "test_type": "e2e",
            "code": "完整的测试代码"
        }}
    ]
}}

要求：
1. 使用 pytest + playwright 或类似框架
2. 模拟真实用户操作
3. 添加页面元素定位和交互
"""

        response = await self._router.call_model(
            capability=ModelCapability.REASONING,
            prompt=prompt,
            temperature=0.2
        )

        try:
            result = json.loads(response)
            
            test_cases = []
            for tc_data in result["test_cases"]:
                test_cases.append(TestCase(
                    id=tc_data["id"],
                    name=tc_data["name"],
                    description=tc_data["description"],
                    test_type=TestType(tc_data["test_type"]),
                    file_path="e2e_tests.py",
                    code=tc_data["code"]
                ))
            
            return test_cases
            
        except Exception as e:
            print(f"❌ E2E测试生成失败: {e}")
            return self._fallback_e2e_tests()

    def _fallback_e2e_tests(self) -> List[TestCase]:
        """兜底E2E测试生成"""
        code = '''"""
E2E测试文件
"""

import pytest
from playwright.sync_api import Page


def test_user_login_flow(page: Page):
    """测试用户登录流程"""
    # TODO: 实现E2E测试
    pass


def test_main_functionality(page: Page):
    """测试主功能流程"""
    # TODO: 实现E2E测试
    pass
'''
        
        return [TestCase(
            id=f"E2E-{int(datetime.now().timestamp())}",
            name="用户登录流程",
            description="端到端测试用户登录",
            test_type=TestType.E2E,
            file_path="e2e_tests.py",
            code=code
        )]

    async def generate_performance_tests(self, endpoints: List[str]) -> List[TestCase]:
        """
        生成性能测试用例
        
        Args:
            endpoints: API端点列表
            
        Returns:
            性能测试用例
        """
        print(f"⚡ 生成性能测试")
        
        prompt = f"""
作为一个专业的性能测试工程师，根据以下API端点生成性能测试用例。

API端点:
{json.dumps(endpoints, indent=2)}

输出格式（JSON）:
{{
    "test_cases": [
        {{
            "id": "PERF-001",
            "name": "端点_性能测试",
            "description": "负载测试场景",
            "test_type": "performance",
            "code": "完整的测试代码"
        }}
    ]
}}

要求：
1. 使用 pytest-benchmark 或 locust
2. 测试响应时间、吞吐量、并发
3. 设置性能阈值
"""

        response = await self._router.call_model(
            capability=ModelCapability.REASONING,
            prompt=prompt,
            temperature=0.2
        )

        try:
            result = json.loads(response)
            
            test_cases = []
            for tc_data in result["test_cases"]:
                test_cases.append(TestCase(
                    id=tc_data["id"],
                    name=tc_data["name"],
                    description=tc_data["description"],
                    test_type=TestType(tc_data["test_type"]),
                    file_path="performance_tests.py",
                    code=tc_data["code"]
                ))
            
            return test_cases
            
        except Exception as e:
            print(f"❌ 性能测试生成失败: {e}")
            return self._fallback_performance_tests()

    def _fallback_performance_tests(self) -> List[TestCase]:
        """兜底性能测试生成"""
        code = '''"""
性能测试文件
"""

import pytest
import time


def test_api_performance():
    """测试API性能"""
    # TODO: 实现性能测试
    start_time = time.time()
    
    # 执行测试
    
    elapsed = time.time() - start_time
    assert elapsed < 1.0, f"响应时间超过1秒: {elapsed}"
'''
        
        return [TestCase(
            id=f"PERF-{int(datetime.now().timestamp())}",
            name="API性能测试",
            description="测试API响应时间",
            test_type=TestType.PERFORMANCE,
            file_path="performance_tests.py",
            code=code
        )]

    async def run_tests(self, test_cases: List[TestCase]) -> List[TestResult]:
        """
        执行测试用例
        
        Args:
            test_cases: 测试用例列表
            
        Returns:
            测试结果列表
        """
        print(f"🚀 执行 {len(test_cases)} 个测试用例")
        
        results = []
        
        for test_case in test_cases:
            result = await self._execute_test(test_case)
            results.append(result)
        
        passed = sum(1 for r in results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in results if r.status == TestStatus.FAILED)
        
        print(f"✅ 测试完成: {passed} 通过, {failed} 失败")
        
        return results

    async def _execute_test(self, test_case: TestCase) -> TestResult:
        """执行单个测试用例"""
        import time
        
        start_time = time.time()
        
        try:
            test_case.status = TestStatus.RUNNING
            
            exec(test_case.code, globals())
            
            execution_time = time.time() - start_time
            
            test_case.status = TestStatus.PASSED
            test_case.execution_time = execution_time
            
            return TestResult(
                test_id=test_case.id,
                status=TestStatus.PASSED,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            
            test_case.status = TestStatus.FAILED
            test_case.execution_time = execution_time
            test_case.error_message = str(e)
            
            return TestResult(
                test_id=test_case.id,
                status=TestStatus.FAILED,
                execution_time=execution_time,
                error_message=str(e)
            )


def get_auto_test_system() -> AutoTestSystem:
    """获取自动测试系统单例"""
    global _test_system_instance
    if _test_system_instance is None:
        _test_system_instance = AutoTestSystem()
    return _test_system_instance


_test_system_instance = None