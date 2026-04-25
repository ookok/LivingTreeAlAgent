"""
test_execution_agent_standalone.py - Execution Agent 独立测试
"""

import sys
import os
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path(__file__).parent
CORE_DIR = PROJECT_ROOT / "core"
AI_SCRIPT_DIR = CORE_DIR / "ai_script_generator"
EXECUTION_DIR = PROJECT_ROOT / "core" / "evolution_engine"

# Add paths
sys.path.insert(0, str(AI_SCRIPT_DIR))
sys.path.insert(0, str(CORE_DIR))
sys.path.insert(0, str(EXECUTION_DIR))

# ============= 加载依赖 =============

# Load script_sandbox first
print("Loading script_sandbox...")
with open(AI_SCRIPT_DIR / "script_sandbox.py", "r", encoding="utf-8") as f:
    sandbox_code = f.read()

sandbox_ns = {'__name__': 'script_sandbox', '__file__': str(AI_SCRIPT_DIR / "script_sandbox.py")}
exec(compile(sandbox_code, str(AI_SCRIPT_DIR / "script_sandbox.py"), 'exec'), sandbox_ns)

# Import what we need
SandboxPermission = sandbox_ns['SandboxPermission']
SandboxConfig = sandbox_ns['SandboxConfig']
ResourceLimit = sandbox_ns['ResourceLimit']
ExecutionResult = sandbox_ns['ExecutionResult']
create_safe_sandbox = sandbox_ns['create_safe_sandbox']
ScriptSandbox = sandbox_ns['ScriptSandbox']
SandboxExecutor = sandbox_ns['SandboxExecutor']

print("✓ script_sandbox loaded")

# ============= Mock logger =============

class MockLogger:
    def info(self, msg): print(f"[INFO] {msg}")
    def warning(self, msg): print(f"[WARN] {msg}")
    def error(self, msg): print(f"[ERROR] {msg}")

logger = MockLogger()

# ============= Execution Agent Implementation =============

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

class ExecutionLevel(Enum):
    SANDBOX = "sandbox"
    RESTRICTED = "restricted"
    FULL = "full"

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"

@dataclass
class ExecutionTask:
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
    task_id: str
    success: bool
    output: str = ""
    error: str = ""
    execution_time: float = 0.0
    memory_peak_mb: float = 0.0
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

class ExecutionAgent:
    def __init__(self, level: ExecutionLevel = ExecutionLevel.SANDBOX):
        self.level = level
        self.sandbox = self._create_sandbox(level)
        self.executor = self.sandbox.executor
        self._task_history: Dict[str, ExecutionTask] = {}
        self._pre_hooks: List[Callable] = []
        self._post_hooks: List[Callable] = []
        logger.info(f"执行代理初始化完成 (level={level.value})")
    
    def _create_sandbox(self, level: ExecutionLevel) -> ScriptSandbox:
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
        else:
            return create_safe_sandbox(
                allow_file_read=True,
                allow_file_write=True,
                allow_network=True,
                max_memory_mb=2048,
                max_time_sec=120
            )
    
    def execute_task(self, task: ExecutionTask) -> ExecutionReport:
        task_id = task.task_id
        self._task_history[task_id] = task
        
        for hook in self._pre_hooks:
            try:
                hook(task)
            except Exception as e:
                logger.warning(f"前置钩子执行失败: {e}")
        
        task.status = TaskStatus.RUNNING
        start_time = time.time()
        
        try:
            result = self.executor.execute(
                code=task.code,
                script_id=task_id,
                context=task.context,
                timeout=task.timeout
            )
            
            task.result = result
            
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
        task = ExecutionTask(
            task_id=f"task_{uuid.uuid4().hex[:8]}",
            code=code,
            description=description,
            level=self.level,
            timeout=timeout,
            context=context or {}
        )
        return self.execute_task(task)

# ============= 测试 =============

def create_execution_agent(level: str = "sandbox") -> ExecutionAgent:
    level_map = {
        'sandbox': ExecutionLevel.SANDBOX,
        'restricted': ExecutionLevel.RESTRICTED,
        'full': ExecutionLevel.FULL
    }
    return ExecutionAgent(level_map.get(level, ExecutionLevel.SANDBOX))

def quick_execute(code: str, timeout: int = 30) -> Dict[str, Any]:
    agent = create_execution_agent('sandbox')
    report = agent.execute_code(code, timeout=timeout)
    return {
        'success': report.success,
        'output': report.output,
        'error': report.error,
        'time': report.execution_time,
        'memory': report.memory_peak_mb
    }

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
    print(f"✓ Success: {report.success}")
    if report.output:
        print(f"  Output: {report.output.strip()}")
    
    # 测试 2: 带上下文
    print("\n[Test 2] 带上下文执行")
    report = agent.execute_code("""
area = 3.14 * radius ** 2
print(f"半径 {radius} 的圆面积: {area:.2f}")
""", context={'radius': 5}, timeout=10)
    print(f"✓ Success: {report.success}")
    if report.output:
        print(f"  Output: {report.output.strip()}")
    
    # 测试 3: 危险代码检测
    print("\n[Test 3] 危险代码检测")
    report = agent.execute_code("""
import os
os.system("echo hacked")
""")
    print(f"  Success: {report.success}")
    print(f"  Warnings: {report.warnings}")
    
    # 测试 4: 快速执行
    print("\n[Test 4] 快速执行")
    result = quick_execute("""
data = [1, 2, 3, 4, 5]
print(f"Sum: {sum(data)}")
print(f"Avg: {sum(data)/len(data)}")
""")
    print(f"✓ Success: {result['success']}")
    print(f"  Output: {result['output'].strip()}")
    print(f"  Time: {result['time']:.4f}s")
    
    print("\n" + "=" * 60)
    print("所有测试完成!")
    print("=" * 60)
