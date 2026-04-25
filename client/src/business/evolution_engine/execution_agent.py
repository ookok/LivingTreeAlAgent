"""
Execution Agent - 工具执行集成
================================

将 Script Sandbox 能力整合到 Evolution Engine 框架中。

功能：
1. 安全代码执行 - 隔离环境、资源限制
2. 任务执行代理 - 复杂任务分解执行
3. 结果验证 - 自动化验证执行结果

Author: Hermes Desktop Team
"""

from core.logger import get_logger
logger = get_logger('evolution.execution_agent')

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

# 导入沙箱能力
from core.ai_script_generator.script_sandbox import (
    ScriptSandbox,
    SandboxExecutor,
    SandboxConfig,
    SandboxPermission,
    ResourceLimit,
    ExecutionResult,
    create_safe_sandbox,
    get_script_sandbox,
)


# ============= 枚举定义 =============

class ExecutionLevel(Enum):
    """执行级别"""
    SANDBOX = "sandbox"      # 沙箱执行 - 完全隔离
    RESTRICTED = "restricted" # 限制执行 - 允许部分文件操作
    FULL = "full"            # 完全执行 - 信任代码


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


# ============= 数据类 =============

@dataclass
class ExecutionTask:
    """执行任务"""
    task_id: str
    code: str
    description: str = ""
    level: ExecutionLevel = ExecutionLevel.SANDBOX
    timeout: int = 30
    retries: int = 0
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[ExecutionResult] = None
    error: Optional[str] = None


@dataclass
class ExecutionReport:
    """执行报告"""
    task_id: str
    success: bool
    output: str = ""
    error: str = ""
    execution_time: float = 0.0
    memory_peak_mb: float = 0.0
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============= 执行代理 =============

class ExecutionAgent:
    """
    执行代理 - Evolution Engine 的执行引擎
    
    整合沙箱能力，提供安全的代码执行环境。
    """
    
    def __init__(self, level: ExecutionLevel = ExecutionLevel.SANDBOX):
        """
        初始化执行代理
        
        Args:
            level: 执行级别
        """
        self.level = level
        self.sandbox = self._create_sandbox(level)
        self.executor = self.sandbox.executor
        
        # 任务历史
        self._task_history: Dict[str, ExecutionTask] = {}
        
        # 执行钩子
        self._pre_hooks: List[Callable] = []
        self._post_hooks: List[Callable] = []
        
        logger.info(f"执行代理初始化完成 (level={level.value})")
    
    def _create_sandbox(self, level: ExecutionLevel) -> ScriptSandbox:
        """根据执行级别创建沙箱"""
        if level == ExecutionLevel.SANDBOX:
            return create_safe_sandbox(
                allow_file_read=True,
                allow_file_write=False,
                allow_network=False,
                max_memory_mb=512,
                max_time_sec=30
            )
        elif level == ExecutionLevel.RESTRICTED:
            return create_safe_sandbox(
                allow_file_read=True,
                allow_file_write=True,
                allow_network=False,
                max_memory_mb=1024,
                max_time_sec=60
            )
        else:  # FULL
            return create_safe_sandbox(
                allow_file_read=True,
                allow_file_write=True,
                allow_network=True,
                max_memory_mb=2048,
                max_time_sec=120
            )
    
    def execute_task(self, task: ExecutionTask) -> ExecutionReport:
        """
        执行任务
        
        Args:
            task: 执行任务
            
        Returns:
            ExecutionReport: 执行报告
        """
        task_id = task.task_id
        self._task_history[task_id] = task
        
        # 前置钩子
        for hook in self._pre_hooks:
            try:
                hook(task)
            except Exception as e:
                logger.warning(f"前置钩子执行失败: {e}")
        
        task.status = TaskStatus.RUNNING
        start_time = time.time()
        
        try:
            # 执行代码
            result = self.executor.execute(
                code=task.code,
                script_id=task_id,
                context=task.context,
                timeout=task.timeout
            )
            
            task.result = result
            
            # 构建报告
            report = ExecutionReport(
                task_id=task_id,
                success=result.success,
                output=result.output,
                error=result.error,
                execution_time=result.execution_time,
                memory_peak_mb=result.memory_peak_mb,
                warnings=result.warnings,
                metadata={
                    'level': self.level.value,
                    'description': task.description,
                    'retries': task.retries
                }
            )
            
            task.status = TaskStatus.SUCCESS if result.success else TaskStatus.FAILED
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            
            report = ExecutionReport(
                task_id=task_id,
                success=False,
                error=str(e),
                execution_time=time.time() - start_time,
                metadata={'level': self.level.value}
            )
        
        # 后置钩子
        for hook in self._post_hooks:
            try:
                hook(task, report)
            except Exception as e:
                logger.warning(f"后置钩子执行失败: {e}")
        
        logger.info(f"任务执行完成: {task_id}, success={report.success}")
        return report
    
    def execute_code(
        self,
        code: str,
        description: str = "",
        context: Dict[str, Any] = None,
        timeout: int = 30
    ) -> ExecutionReport:
        """
        快捷执行代码
        
        Args:
            code: Python代码
            description: 描述
            context: 上下文
            timeout: 超时时间
            
        Returns:
            ExecutionReport: 执行报告
        """
        task = ExecutionTask(
            task_id=f"task_{uuid.uuid4().hex[:8]}",
            code=code,
            description=description,
            level=self.level,
            timeout=timeout,
            context=context or {}
        )
        return self.execute_task(task)
    
    def execute_with_validation(
        self,
        code: str,
        validator: Callable[[str], bool],
        description: str = "",
        max_retries: int = 3
    ) -> ExecutionReport:
        """
        带验证的执行
        
        Args:
            code: Python代码
            validator: 验证函数 (output -> bool)
            description: 描述
            max_retries: 最大重试次数
            
        Returns:
            ExecutionReport: 最终执行报告
        """
        attempts = 0
        last_report = None
        
        while attempts < max_retries:
            report = self.execute_code(code, description)
            
            if report.success and validator(report.output):
                return report
            
            attempts += 1
            last_report = report
            
            if attempts < max_retries:
                logger.info(f"验证失败，重试 {attempts}/{max_retries}")
        
        return last_report or ExecutionReport(
            task_id="validation_failed",
            success=False,
            error="验证失败或超时"
        )
    
    def add_pre_hook(self, hook: Callable[[ExecutionTask], None]):
        """添加前置钩子"""
        self._pre_hooks.append(hook)
    
    def add_post_hook(self, hook: Callable[[ExecutionTask, ExecutionReport], None]):
        """添加后置钩子"""
        self._post_hooks.append(hook)
    
    def get_task_history(self) -> List[ExecutionTask]:
        """获取任务历史"""
        return list(self._task_history.values())
    
    def get_task(self, task_id: str) -> Optional[ExecutionTask]:
        """获取指定任务"""
        return self._task_history.get(task_id)


# ============= 工具函数 =============

def create_execution_agent(level: str = "sandbox") -> ExecutionAgent:
    """
    创建执行代理
    
    Args:
        level: 执行级别 (sandbox/restricted/full)
        
    Returns:
        ExecutionAgent: 执行代理实例
    """
    level_map = {
        'sandbox': ExecutionLevel.SANDBOX,
        'restricted': ExecutionLevel.RESTRICTED,
        'full': ExecutionLevel.FULL
    }
    return ExecutionAgent(level_map.get(level, ExecutionLevel.SANDBOX))


# ============= 快速使用 =============

def quick_execute(code: str, timeout: int = 30) -> Dict[str, Any]:
    """
    快速执行代码 (便捷函数)
    
    Args:
        code: Python代码
        timeout: 超时时间
        
    Returns:
        dict: {'success', 'output', 'error', 'time'}
    """
    agent = create_execution_agent('sandbox')
    report = agent.execute_code(code, timeout=timeout)
    
    return {
        'success': report.success,
        'output': report.output,
        'error': report.error,
        'time': report.execution_time,
        'memory': report.memory_peak_mb
    }


# ============= 测试 =============

if __name__ == "__main__":
    print("=" * 60)
    print("Execution Agent 测试")
    print("=" * 60)
    
    # 创建执行代理
    agent = create_execution_agent('sandbox')
    
    # 测试 1: 简单计算
    print("\n[Test 1] 简单计算")
    report = agent.execute_code("""
result = 2 ** 10
print(f"2^10 = {result}")
""", description="计算2的10次方")
    print(f"Success: {report.success}")
    print(f"Output: {report.output.strip()}")
    
    # 测试 2: 带上下文
    print("\n[Test 2] 带上下文")
    report = agent.execute_code("""
print(f"半径 {radius} 的圆面积: {3.14 * radius ** 2}")
""", context={'radius': 5}, timeout=10)
    print(f"Output: {report.output.strip()}")
    
    # 测试 3: 危险代码检测
    print("\n[Test 3] 危险代码检测")
    report = agent.execute_code("""
import os
os.system("echo hacked")
""")
    print(f"Success: {report.success}")
    print(f"Warnings: {report.warnings}")
    
    # 测试 4: 快速执行
    print("\n[Test 4] 快速执行")
    result = quick_execute("""
data = [1, 2, 3, 4, 5]
print(f"Sum: {sum(data)}")
print(f"Avg: {sum(data)/len(data)}")
""")
    print(f"Success: {result['success']}")
    print(f"Output: {result['output'].strip()}")
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)
