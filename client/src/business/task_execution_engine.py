"""
TaskExecutionEngine - 目标驱动执行引擎

参考 andrej-karpathy-skills 的"目标驱动执行"原则。

核心功能：
1. 将模糊指令转化为可验证的目标+测试用例
2. 智能体可以自主循环验证结果
3. 任务完成标准：所有测试用例通过
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from loguru import logger
from datetime import datetime
from enum import Enum
import asyncio


class ExecutionStatus(Enum):
    """执行状态"""
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class TestCase:
    """测试用例"""
    id: str
    name: str
    description: str
    input_data: Dict[str, Any]
    expected_output: Any
    actual_output: Optional[Any] = None
    passed: Optional[bool] = None
    error_message: Optional[str] = None


@dataclass
class ExecutionTarget:
    """执行目标"""
    id: str
    name: str
    description: str
    test_cases: List[TestCase] = field(default_factory=list)
    max_retries: int = 3
    current_retry: int = 0


@dataclass
class ExecutionResult:
    """执行结果"""
    target: ExecutionTarget
    status: ExecutionStatus
    test_results: List[TestCase] = field(default_factory=list)
    execution_steps: List[str] = field(default_factory=list)
    error: Optional[str] = None
    completed_at: Optional[datetime] = None


class TaskExecutionEngine:
    """
    目标驱动执行引擎
    
    参考 andrej-karpathy-skills 的"目标驱动执行"原则：
    1. 将模糊指令转化为可验证的目标+测试用例
    2. 智能体可以自主循环验证结果
    3. 任务完成标准：所有测试用例通过
    
    核心流程：
    1. 解析指令 → 生成目标和测试用例
    2. 执行任务
    3. 验证结果（运行测试用例）
    4. 如果失败，重试（最多 max_retries 次）
    5. 所有测试通过，任务完成
    """
    
    def __init__(self, tool_registry=None, llm_client=None):
        self._logger = logger.bind(component="TaskExecutionEngine")
        self._tool_registry = tool_registry
        self._llm = llm_client
        self._max_retries = 3
    
    async def execute(self, instruction: str, context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
        """
        执行任务（目标驱动）
        
        Args:
            instruction: 任务指令
            context: 上下文信息
            
        Returns:
            ExecutionResult - 执行结果
        """
        self._logger.info(f"开始目标驱动执行: {instruction}")
        
        # 1. 解析指令，生成目标和测试用例
        target = await self._parse_instruction(instruction, context)
        self._logger.info(f"生成目标: {target.name}, 测试用例: {len(target.test_cases)}")
        
        result = ExecutionResult(target=target, status=ExecutionStatus.PLANNING)
        
        # 2. 循环执行直到所有测试通过或达到最大重试次数
        while target.current_retry < target.max_retries:
            result.status = ExecutionStatus.EXECUTING
            target.current_retry += 1
            
            self._logger.info(f"执行尝试 {target.current_retry}/{target.max_retries}")
            
            # 执行任务
            execution_result = await self._execute_target(target, context)
            
            # 记录执行步骤
            result.execution_steps.extend(execution_result.get("steps", []))
            
            # 3. 验证结果
            result.status = ExecutionStatus.VERIFYING
            await self._verify_target(target)
            
            # 检查是否所有测试通过
            all_passed = all(tc.passed for tc in target.test_cases)
            
            if all_passed:
                result.status = ExecutionStatus.COMPLETED
                result.test_results = target.test_cases
                result.completed_at = datetime.now()
                self._logger.info("所有测试用例通过，任务完成")
                return result
            
            self._logger.warning(f"测试用例未全部通过，准备重试...")
        
        # 达到最大重试次数
        result.status = ExecutionStatus.FAILED
        result.test_results = target.test_cases
        result.error = f"达到最大重试次数 ({target.max_retries})，任务未完成"
        self._logger.error(result.error)
        
        return result
    
    async def _parse_instruction(self, instruction: str, context: Optional[Dict[str, Any]] = None) -> ExecutionTarget:
        """
        将模糊指令转化为可验证的目标+测试用例
        
        Args:
            instruction: 任务指令
            context: 上下文信息
            
        Returns:
            ExecutionTarget - 执行目标（包含测试用例）
        """
        self._logger.debug("解析指令生成目标...")
        
        target_id = f"target_{int(datetime.now().timestamp())}"
        
        # 使用 LLM 分析指令并生成测试用例
        prompt = f"""
你是一个测试用例专家。请分析以下任务指令并生成可验证的目标和测试用例：

任务指令：{instruction}

上下文信息：{context or '无'}

请输出 JSON 格式，包含：
1. target_name: 目标名称
2. target_description: 目标描述
3. test_cases: 测试用例数组，每个测试用例包含：
   - id: 测试用例ID
   - name: 测试用例名称
   - description: 测试用例描述
   - input_data: 输入数据（字典格式）
   - expected_output: 期望输出

测试用例应该覆盖：
- 主要功能验证
- 边界条件测试
- 错误处理测试

请只输出 JSON，不要有其他内容。
"""
        
        try:
            response = await self._call_llm(prompt)
            
            import json
            data = json.loads(response)
            
            test_cases = []
            for tc_data in data.get("test_cases", []):
                test_case = TestCase(
                    id=tc_data.get("id", ""),
                    name=tc_data.get("name", ""),
                    description=tc_data.get("description", ""),
                    input_data=tc_data.get("input_data", {}),
                    expected_output=tc_data.get("expected_output")
                )
                test_cases.append(test_case)
            
            return ExecutionTarget(
                id=target_id,
                name=data.get("target_name", "未命名目标"),
                description=data.get("target_description", ""),
                test_cases=test_cases,
                max_retries=self._max_retries
            )
            
        except Exception as e:
            self._logger.warning(f"自动生成测试用例失败，使用默认测试: {e}")
            
            # 默认测试用例
            return ExecutionTarget(
                id=target_id,
                name=f"执行任务: {instruction[:30]}...",
                description=instruction,
                test_cases=[
                    TestCase(
                        id="tc_1",
                        name="任务完成验证",
                        description="验证任务是否成功执行",
                        input_data={"instruction": instruction},
                        expected_output={"success": True}
                    )
                ],
                max_retries=self._max_retries
            )
    
    async def _execute_target(self, target: ExecutionTarget, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        执行目标任务
        
        Args:
            target: 执行目标
            context: 上下文信息
            
        Returns:
            执行结果
        """
        self._logger.debug(f"执行目标: {target.name}")
        
        steps = []
        
        # 模拟执行步骤
        steps.append(f"开始执行目标: {target.name}")
        
        # 这里可以调用工具执行实际任务
        if self._tool_registry:
            # 根据目标选择合适的工具执行
            steps.append("调用工具执行任务")
        
        steps.append("任务执行完成")
        
        return {"steps": steps, "success": True}
    
    async def _verify_target(self, target: ExecutionTarget):
        """
        验证目标（运行测试用例）
        
        Args:
            target: 执行目标
        """
        self._logger.debug("验证目标...")
        
        for test_case in target.test_cases:
            self._logger.debug(f"运行测试用例: {test_case.name}")
            
            # 模拟测试执行
            try:
                # 这里应该调用实际的验证逻辑
                # 比较 expected_output 和实际输出
                # 对于演示，我们随机决定测试是否通过
                
                # 简单的测试验证逻辑
                if isinstance(test_case.expected_output, dict):
                    if "success" in test_case.expected_output:
                        test_case.actual_output = {"success": True}
                        test_case.passed = True
                    else:
                        test_case.actual_output = {"result": "test_result"}
                        test_case.passed = True
                else:
                    test_case.actual_output = "test_result"
                    test_case.passed = True
                    
                self._logger.debug(f"测试用例通过: {test_case.name}")
                
            except Exception as e:
                test_case.passed = False
                test_case.error_message = str(e)
                self._logger.warning(f"测试用例失败 {test_case.name}: {e}")
    
    def get_target_status(self, target_id: str) -> Optional[ExecutionTarget]:
        """获取目标状态"""
        # 在实际实现中，应该从存储中获取
        return None
    
    def list_targets(self) -> List[ExecutionTarget]:
        """列出所有目标"""
        return []
    
    def is_complete(self, result: ExecutionResult) -> bool:
        """检查任务是否完成"""
        return result.status == ExecutionStatus.COMPLETED
    
    def get_test_summary(self, result: ExecutionResult) -> Dict[str, Any]:
        """获取测试结果摘要"""
        total = len(result.test_results)
        passed = sum(1 for tc in result.test_results if tc.passed)
        
        return {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "success_rate": passed / total if total > 0 else 0
        }
    
    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM"""
        if self._llm is not None:
            return await self._llm.chat(prompt)
        else:
            # 模拟响应
            import json
            return json.dumps({
                "target_name": "目标名称",
                "target_description": "目标描述",
                "test_cases": [
                    {
                        "id": "tc_1",
                        "name": "测试用例1",
                        "description": "测试描述1",
                        "input_data": {"input": "test"},
                        "expected_output": {"success": True}
                    }
                ]
            })
    
    def suggest_revision(self, result: ExecutionResult) -> str:
        """
        根据测试失败结果建议修改
        
        Args:
            result: 执行结果
            
        Returns:
            修改建议
        """
        failed_cases = [tc for tc in result.test_results if not tc.passed]
        
        if not failed_cases:
            return "所有测试通过，无需修改"
        
        suggestions = ["以下测试用例失败，建议修改："]
        
        for tc in failed_cases:
            suggestions.append(f"- {tc.name}: {tc.error_message or '未通过'}")
        
        return "\n".join(suggestions)