"""
AI测试指挥官 - PyQt6控制台
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import asyncio


class TaskPriority(Enum):
    """任务优先级"""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass
class TestTask:
    """测试任务"""
    task_id: str
    description: str
    priority: TaskPriority = TaskPriority.NORMAL
    target_app: str = ""
    steps: List[Dict[str, Any]] = field(default_factory=list)
    expected_result: Optional[str] = None
    status: str = "pending"
    result: Optional[Dict[str, Any]] = None


@dataclass
class TestStrategy:
    """测试策略"""
    name: str
    description: str
    max_retries: int = 3
    timeout: float = 60.0
    screenshot_on_fail: bool = True
    record_video: bool = False


class AITestCommander:
    """
    AI测试指挥官
    
    核心功能：
    1. 自然语言任务输入
    2. 测试策略配置
    3. AI模型选择
    4. 实时监控显示
    5. 结果分析报告
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.tasks: List[TestTask] = []
        self.strategies: Dict[str, TestStrategy] = {}
        self.current_task: Optional[TestTask] = None
        self.callbacks: Dict[str, Callable] = {}
        
        # 初始化默认策略
        self._init_default_strategies()
        
    def _init_default_strategies(self):
        """初始化默认测试策略"""
        self.strategies = {
            'quick': TestStrategy(
                name='quick',
                description='快速测试，适用于简单验证',
                max_retries=1,
                timeout=30.0,
            ),
            'standard': TestStrategy(
                name='standard',
                description='标准测试，适用于一般场景',
                max_retries=3,
                timeout=60.0,
            ),
            'deep': TestStrategy(
                name='deep',
                description='深度测试，适用于复杂场景',
                max_retries=5,
                timeout=120.0,
                screenshot_on_fail=True,
                record_video=True,
            ),
        }
        
    def add_task(self, description: str,
                target_app: str = "",
                priority: TaskPriority = TaskPriority.NORMAL) -> TestTask:
        """添加测试任务"""
        task = TestTask(
            task_id=self._generate_task_id(),
            description=description,
            priority=priority,
            target_app=target_app,
        )
        self.tasks.append(task)
        self._sort_tasks()
        return task
    
    def set_strategy(self, name: str, strategy: TestStrategy):
        """设置测试策略"""
        self.strategies[name] = strategy
        
    async def execute_task(self, task: TestTask,
                          strategy_name: str = 'standard',
                          ai_model: str = 'auto') -> Dict[str, Any]:
        """
        执行测试任务
        
        Args:
            task: 测试任务
            strategy_name: 策略名称
            ai_model: AI模型
            
        Returns:
            执行结果
        """
        strategy = self.strategies.get(strategy_name, self.strategies['standard'])
        self.current_task = task
        task.status = "running"
        
        # 触发开始回调
        self._trigger_callback('on_task_start', task)
        
        try:
            # 解析任务步骤
            steps = await self._parse_task_steps(task, ai_model)
            task.steps = steps
            
            # 执行测试步骤
            results = []
            for i, step in enumerate(steps):
                step_result = await self._execute_step(step, strategy)
                results.append(step_result)
                
                # 触发步骤回调
                self._trigger_callback('on_step_complete', {
                    'task': task,
                    'step': i,
                    'result': step_result
                })
                
                # 检查是否失败
                if not step_result.get('success', False):
                    if i < strategy.max_retries:
                        continue
                    else:
                        break
                        
            # 汇总结果
            task.result = self._summarize_results(results, task)
            task.status = "completed"
            
            # 触发完成回调
            self._trigger_callback('on_task_complete', task)
            
        except Exception as e:
            task.status = "failed"
            task.result = {'error': str(e)}
            self._trigger_callback('on_task_error', {'task': task, 'error': str(e)})
            
        return task.result or {}
    
    async def _parse_task_steps(self, task: TestTask, 
                               ai_model: str) -> List[Dict[str, Any]]:
        """解析任务为可执行步骤"""
        # 简化实现：基于描述生成步骤
        steps = []
        
        # 基础步骤
        if 'click' in task.description.lower():
            steps.append({
                'action': 'find_element',
                'target': 'button',
                'strategy': 'ocr'
            })
            steps.append({
                'action': 'click',
                'target': 'found_element'
            })
            
        if 'input' in task.description.lower() or 'type' in task.description.lower():
            steps.append({
                'action': 'find_element',
                'target': 'input',
                'strategy': 'ocr'
            })
            steps.append({
                'action': 'type',
                'target': 'found_element',
                'text': task.description
            })
            
        if 'verify' in task.description.lower() or 'check' in task.description.lower():
            steps.append({
                'action': 'verify',
                'target': 'expected_element',
                'condition': task.expected_result
            })
            
        # 确保至少有基础步骤
        if not steps:
            steps = [
                {'action': 'launch_app', 'target': task.target_app},
                {'action': 'wait', 'duration': 2},
                {'action': 'screenshot'},
            ]
            
        return steps
    
    async def _execute_step(self, step: Dict[str, Any],
                          strategy: TestStrategy) -> Dict[str, Any]:
        """执行单个测试步骤"""
        action = step.get('action', 'unknown')
        
        # 模拟执行
        await asyncio.sleep(0.5)  # 模拟延迟
        
        return {
            'action': action,
            'success': True,
            'message': f'Step {action} completed',
            'screenshot': None,
        }
    
    def _summarize_results(self, results: List[Dict[str, Any]],
                          task: TestTask) -> Dict[str, Any]:
        """汇总测试结果"""
        total = len(results)
        passed = sum(1 for r in results if r.get('success', False))
        failed = total - passed
        
        return {
            'task_id': task.task_id,
            'total_steps': total,
            'passed': passed,
            'failed': failed,
            'success_rate': passed / total if total > 0 else 0,
            'results': results,
        }
    
    def _generate_task_id(self) -> str:
        """生成任务ID"""
        import hashlib
        import time
        content = f"{time.time()}_{len(self.tasks)}"
        return hashlib.md5(content.encode()).hexdigest()[:8]
    
    def _sort_tasks(self):
        """按优先级排序任务"""
        self.tasks.sort(key=lambda t: t.priority.value)
    
    def register_callback(self, event: str, callback: Callable):
        """注册回调函数"""
        self.callbacks[event] = callback
        
    def _trigger_callback(self, event: str, data: Any):
        """触发回调"""
        if event in self.callbacks:
            self.callbacks[event](data)
            
    def get_task_status(self) -> Dict[str, Any]:
        """获取任务状态"""
        return {
            'total': len(self.tasks),
            'pending': sum(1 for t in self.tasks if t.status == 'pending'),
            'running': sum(1 for t in self.tasks if t.status == 'running'),
            'completed': sum(1 for t in self.tasks if t.status == 'completed'),
            'failed': sum(1 for t in self.tasks if t.status == 'failed'),
            'current_task': self.current_task.task_id if self.current_task else None,
        }
