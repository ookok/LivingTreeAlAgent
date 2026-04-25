#!/usr/bin/env python3
"""
LivingTreeAI Phase 2 - Multi-Agent 协作调度器
负责任务分发、结果聚合、冲突解决
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import threading
import uuid


class TaskPriority(Enum):
    """任务优先级"""
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3


class TaskState(Enum):
    """任务状态"""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ScheduledTask:
    """调度任务"""
    task_id: str
    description: str
    priority: TaskPriority
    state: TaskState = TaskState.PENDING
    assigned_agent: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=datetime.now().timestamp)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentCapabilities:
    """智能体能力"""
    agent_id: str
    skills: List[str]
    load: float = 0.0  # 0.0 - 1.0
    max_concurrent: int = 1
    current_tasks: int = 0


class TaskScheduler:
    """
    任务调度器
    负责任务分发、负载均衡
    """
    
    def __init__(self):
        self.tasks: Dict[str, ScheduledTask] = {}
        self.agents: Dict[str, AgentCapabilities] = {}
        self.task_queue: List[str] = []  # 按优先级排序
        self._lock = threading.RLock()
    
    def register_agent(self, agent_id: str, skills: List[str],
                      max_concurrent: int = 1) -> bool:
        """注册智能体"""
        with self._lock:
            if agent_id in self.agents:
                return False
            
            self.agents[agent_id] = AgentCapabilities(
                agent_id=agent_id,
                skills=skills,
                max_concurrent=max_concurrent
            )
            return True
    
    def submit_task(self, description: str, priority: TaskPriority,
                   required_skills: List[str] = None,
                   dependencies: List[str] = None) -> str:
        """提交任务"""
        task_id = str(uuid.uuid4())[:8]
        task = ScheduledTask(
            task_id=task_id,
            description=description,
            priority=priority,
            dependencies=dependencies or []
        )
        
        with self._lock:
            self.tasks[task_id] = task
            self._reorder_queue()
        
        return task_id
    
    def _reorder_queue(self):
        """重新排序任务队列"""
        self.task_queue = sorted(
            self.tasks.keys(),
            key=lambda tid: (
                self.tasks[tid].priority.value,
                self.tasks[tid].created_at
            ),
            reverse=True
        )
    
    def _find_best_agent(self, required_skills: List[str]) -> Optional[str]:
        """找到最佳智能体"""
        with self._lock:
            candidates = []
            
            for agent_id, caps in self.agents.items():
                # 检查负载
                if caps.current_tasks >= caps.max_concurrent:
                    continue
                
                # 检查技能匹配
                if required_skills:
                    match_count = sum(1 for s in required_skills if s in caps.skills)
                    if match_count == 0:
                        continue
                    match_ratio = match_count / len(required_skills)
                else:
                    match_ratio = 1.0
                
                candidates.append((agent_id, match_ratio, caps.load))
            
            if not candidates:
                return None
            
            # 按匹配度和负载排序
            candidates.sort(key=lambda x: (x[1], -x[2]), reverse=True)
            return candidates[0][0]
    
    def _can_schedule(self, task_id: str) -> bool:
        """检查任务是否可以调度"""
        task = self.tasks[task_id]
        
        if task.state != TaskState.PENDING:
            return False
        
        # 检查依赖
        for dep_id in task.dependencies:
            if dep_id not in self.tasks:
                continue
            dep_task = self.tasks[dep_id]
            if dep_task.state != TaskState.COMPLETED:
                return False
        
        return True
    
    def schedule_next(self) -> Optional[str]:
        """调度下一个任务"""
        with self._lock:
            for task_id in self.task_queue:
                if self._can_schedule(task_id):
                    task = self.tasks[task_id]
                    
                    # 找到最佳智能体
                    agent_id = self._find_best_agent(
                        self._extract_skills(task.description)
                    )
                    
                    if agent_id:
                        task.state = TaskState.SCHEDULED
                        task.assigned_agent = agent_id
                        self.agents[agent_id].current_tasks += 1
                        self._reorder_queue()
                        return task_id
            
            return None
    
    def _extract_skills(self, description: str) -> List[str]:
        """从描述中提取技能需求"""
        skill_keywords = {
            'coding': ['代码', '编程', '写', 'code', 'implement'],
            'testing': ['测试', 'test', '验证'],
            'review': ['审查', 'review', '审核'],
            'deploy': ['部署', 'deploy', '发布'],
            'design': ['设计', 'design', '架构'],
        }
        
        skills = []
        desc_lower = description.lower()
        
        for skill, keywords in skill_keywords.items():
            if any(kw in desc_lower for kw in keywords):
                skills.append(skill)
        
        return skills
    
    def complete_task(self, task_id: str, result: Any) -> bool:
        """完成任务"""
        with self._lock:
            if task_id not in self.tasks:
                return False
            
            task = self.tasks[task_id]
            task.state = TaskState.COMPLETED
            task.result = result
            task.completed_at = datetime.now().timestamp
            
            if task.assigned_agent:
                self.agents[task.assigned_agent].current_tasks -= 1
            
            return True
    
    def fail_task(self, task_id: str, error: str) -> bool:
        """任务失败"""
        with self._lock:
            if task_id not in self.tasks:
                return False
            
            task = self.tasks[task_id]
            task.state = TaskState.FAILED
            task.error = error
            task.completed_at = datetime.now().timestamp
            
            if task.assigned_agent:
                self.agents[task.assigned_agent].current_tasks -= 1
            
            return True
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        with self._lock:
            task = self.tasks.get(task_id)
            if not task:
                return None
            
            return {
                'task_id': task.task_id,
                'description': task.description,
                'priority': task.priority.name,
                'state': task.state.value,
                'assigned_agent': task.assigned_agent,
                'result': task.result,
                'error': task.error,
                'duration': self._calc_duration(task)
            }
    
    def _calc_duration(self, task: ScheduledTask) -> Optional[float]:
        """计算任务耗时"""
        if task.started_at and task.completed_at:
            return task.completed_at - task.started_at
        return None
    
    def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """获取智能体状态"""
        with self._lock:
            caps = self.agents.get(agent_id)
            if not caps:
                return None
            
            return {
                'agent_id': agent_id,
                'skills': caps.skills,
                'load': caps.load,
                'max_concurrent': caps.max_concurrent,
                'current_tasks': caps.current_tasks
            }
    
    def get_all_tasks(self, state: TaskState = None) -> List[Dict[str, Any]]:
        """获取所有任务"""
        with self._lock:
            tasks = list(self.tasks.values())
            if state:
                tasks = [t for t in tasks if t.state == state]
            
            return [
                {
                    'task_id': t.task_id,
                    'description': t.description,
                    'priority': t.priority.name,
                    'state': t.state.value,
                    'assigned_agent': t.assigned_agent
                }
                for t in tasks
            ]


class ResultAggregator:
    """
    结果聚合器
    收集和聚合多个智能体的执行结果
    """
    
    def __init__(self):
        self.results: Dict[str, Any] = {}
        self._lock = threading.RLock()
    
    def add_result(self, task_id: str, agent_id: str, result: Any) -> None:
        """添加结果"""
        with self._lock:
            self.results[task_id] = {
                'agent_id': agent_id,
                'result': result,
                'timestamp': datetime.now().timestamp
            }
    
    def get_result(self, task_id: str) -> Optional[Any]:
        """获取结果"""
        with self._lock:
            entry = self.results.get(task_id)
            return entry['result'] if entry else None
    
    def get_all_results(self) -> Dict[str, Any]:
        """获取所有结果"""
        with self._lock:
            return self.results.copy()
    
    def aggregate(self, task_ids: List[str]) -> Dict[str, Any]:
        """聚合多个任务结果"""
        with self._lock:
            aggregated = {}
            
            for task_id in task_ids:
                if task_id in self.results:
                    aggregated[task_id] = self.results[task_id]['result']
            
            return aggregated


class ConflictResolver:
    """
    冲突解决器
    解决多智能体协作中的冲突
    """
    
    def __init__(self):
        self.conflict_rules: Dict[str, Callable] = {}
    
    def register_rule(self, conflict_type: str, resolver: Callable) -> None:
        """注册冲突解决规则"""
        self.conflict_rules[conflict_type] = resolver
    
    def resolve(self, conflict_type: str, options: List[Any]) -> Any:
        """解决冲突"""
        if conflict_type in self.conflict_rules:
            return self.conflict_rules[conflict_type](options)
        
        # 默认策略：选择第一个
        return options[0] if options else None


# ==================== CLI ====================

def main():
    """命令行工具"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Multi-Agent 协作调度器')
    parser.add_argument('--submit', '-s', help='提交任务')
    parser.add_argument('--priority', '-p', choices=['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'],
                       default='MEDIUM', help='任务优先级')
    
    args = parser.parse_args()
    
    scheduler = TaskScheduler()
    
    # 注册测试智能体
    scheduler.register_agent("coder", ["coding", "design"], max_concurrent=2)
    scheduler.register_agent("tester", ["testing", "review"], max_concurrent=2)
    print("注册智能体: coder, tester")
    
    if args.submit:
        # 提交任务
        priority = TaskPriority[args.priority]
        task_id = scheduler.submit_task(args.submit, priority)
        print(f"提交任务: {task_id} - {args.submit}")
        
        # 调度任务
        scheduled = scheduler.schedule_next()
        if scheduled:
            print(f"调度任务: {scheduled}")
        
        # 模拟完成
        scheduler.complete_task(task_id, "完成")


if __name__ == "__main__":
    main()
