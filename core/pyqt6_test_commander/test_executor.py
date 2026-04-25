"""
测试执行器 - 执行测试任务
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import time


class TestStatus(Enum):
    """测试状态"""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TestResult:
    """测试结果"""
    test_id: str
    status: TestStatus
    duration: float = 0.0
    steps: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    screenshot: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class TestExecutor:
    """测试执行器"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.results: List[TestResult] = []
        self.current_test: Optional[TestResult] = None
        self.on_step_complete: Optional[Callable] = None
        
    async def execute_test(self, test_steps: List[Dict[str, Any]],
                         timeout: float = 60.0) -> TestResult:
        """执行测试"""
        test_id = f"test_{int(time.time())}"
        result = TestResult(test_id=test_id, status=TestStatus.RUNNING)
        self.current_test = result
        
        start_time = time.time()
        
        try:
            for i, step in enumerate(test_steps):
                step_result = await self._execute_step(step)
                result.steps.append(step_result)
                
                # 回调
                if self.on_step_complete:
                    self.on_step_complete({
                        'step': i,
                        'total': len(test_steps),
                        'result': step_result
                    })
                    
                if not step_result.get('success', False):
                    result.status = TestStatus.FAILED
                    break
                    
            if result.status != TestStatus.FAILED:
                result.status = TestStatus.PASSED
                
        except Exception as e:
            result.status = TestStatus.FAILED
            result.error = str(e)
            
        finally:
            result.duration = time.time() - start_time
            self.results.append(result)
            self.current_test = None
            
        return result
    
    async def _execute_step(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """执行单个步骤"""
        action = step.get('action', 'unknown')
        
        # 模拟执行
        await asyncio.sleep(0.3)
        
        return {
            'action': action,
            'success': True,
            'message': f'Action {action} completed'
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """获取测试摘要"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in self.results if r.status == TestStatus.FAILED)
        
        return {
            'total': total,
            'passed': passed,
            'failed': failed,
            'pass_rate': passed / total if total > 0 else 0,
            'total_duration': sum(r.duration for r in self.results)
        }
