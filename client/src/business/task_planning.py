"""
任务规划系统
将自然语言需求转换为结构化的任务树
"""

import re
import asyncio
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class TaskType(Enum):
    """任务类型"""
    CODE_GENERATION = "code_generation"
    CODE_COMPLETION = "code_completion"
    ERROR_DIAGNOSIS = "error_diagnosis"
    REFACTORING = "refactoring"
    TEST_GENERATION = "test_generation"
    DOCUMENTATION = "documentation"
    PERFORMANCE_OPTIMIZATION = "performance_optimization"
    FILE_OPERATION = "file_operation"
    GIT_OPERATION = "git_operation"
    RESEARCH = "research"
    OTHER = "other"


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """任务"""
    id: str
    title: str
    description: str
    task_type: TaskType
    priority: int = 0  # 0-10，10最高
    status: TaskStatus = TaskStatus.PENDING
    dependencies: List[str] = field(default_factory=list)
    subtasks: List[str] = field(default_factory=list)
    estimated_time: int = 0  # 预估时间（分钟）
    actual_time: int = 0  # 实际时间（分钟）
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None


@dataclass
class TaskTree:
    """任务树"""
    root_task: Task
    tasks: Dict[str, Task] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)


class TaskPlanner:
    """任务规划器"""
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.task_trees: Dict[str, TaskTree] = {}
        self._task_counter = 0
    
    def _generate_task_id(self) -> str:
        """生成任务ID"""
        self._task_counter += 1
        return f"task_{self._task_counter}_{int(datetime.now().timestamp())}"
    
    async def plan_from_natural_language(self, natural_language: str) -> Optional[TaskTree]:
        """从自然语言生成任务计划"""
        try:
            # 分析自然语言需求
            analysis = await self._analyze_requirement(natural_language)
            
            # 构建任务树
            task_tree = await self._build_task_tree(analysis)
            
            # 保存任务树
            tree_id = f"tree_{int(datetime.now().timestamp())}"
            self.task_trees[tree_id] = task_tree
            
            return task_tree
        except Exception as e:
            print(f"任务规划失败: {e}")
            return None
    
    async def _analyze_requirement(self, requirement: str) -> Dict[str, Any]:
        """分析需求"""
        if self.llm_client:
            return await self._analyze_with_llm(requirement)
        else:
            return self._analyze_with_rules(requirement)
    
    async def _analyze_with_llm(self, requirement: str) -> Dict[str, Any]:
        """使用LLM分析需求"""
        prompt = f"""分析以下开发需求，识别需要完成的任务：

{requirement}

请返回一个JSON对象，包含：
1. 主要任务（main_task）：总体目标
2. 子任务（subtasks）：需要完成的具体任务列表，每个任务包含：
   - title: 任务标题
   - description: 任务描述
   - type: 任务类型（code_generation, code_completion, refactoring, test_generation, documentation, file_operation, git_operation, research, other）
   - priority: 优先级（0-10）
   - estimated_time: 预估时间（分钟）
   - dependencies: 依赖的任务ID列表（如果有）

请只返回JSON，不要包含其他内容。"""
        
        response = await self.llm_client.generate(prompt)
        
        # 解析JSON
        import json
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # 回退到规则分析
            return self._analyze_with_rules(requirement)
    
    def _analyze_with_rules(self, requirement: str) -> Dict[str, Any]:
        """使用规则分析需求"""
        analysis = {
            "main_task": requirement,
            "subtasks": []
        }
        
        # 简单的规则分析
        if "create" in requirement.lower() or "build" in requirement.lower():
            analysis["subtasks"].append({
                "title": "创建新文件",
                "description": "创建新的代码文件",
                "type": "code_generation",
                "priority": 8,
                "estimated_time": 30,
                "dependencies": []
            })
        
        if "fix" in requirement.lower() or "bug" in requirement.lower():
            analysis["subtasks"].append({
                "title": "修复错误",
                "description": "诊断并修复代码错误",
                "type": "error_diagnosis",
                "priority": 9,
                "estimated_time": 45,
                "dependencies": []
            })
        
        if "test" in requirement.lower():
            analysis["subtasks"].append({
                "title": "生成测试用例",
                "description": "为代码生成测试用例",
                "type": "test_generation",
                "priority": 7,
                "estimated_time": 20,
                "dependencies": []
            })
        
        if "doc" in requirement.lower() or "documentation" in requirement.lower():
            analysis["subtasks"].append({
                "title": "生成文档",
                "description": "为代码生成文档",
                "type": "documentation",
                "priority": 6,
                "estimated_time": 15,
                "dependencies": []
            })
        
        if "optimize" in requirement.lower() or "performance" in requirement.lower():
            analysis["subtasks"].append({
                "title": "性能优化",
                "description": "优化代码性能",
                "type": "performance_optimization",
                "priority": 7,
                "estimated_time": 30,
                "dependencies": []
            })
        
        return analysis
    
    async def _build_task_tree(self, analysis: Dict[str, Any]) -> TaskTree:
        """构建任务树"""
        # 创建根任务
        root_task = Task(
            id=self._generate_task_id(),
            title=analysis["main_task"],
            description=analysis["main_task"],
            task_type=TaskType.OTHER,
            priority=10
        )
        
        tasks = {root_task.id: root_task}
        
        # 创建子任务
        for subtask_data in analysis.get("subtasks", []):
            subtask = Task(
                id=self._generate_task_id(),
                title=subtask_data["title"],
                description=subtask_data["description"],
                task_type=TaskType(subtask_data["type"]),
                priority=subtask_data["priority"],
                dependencies=subtask_data.get("dependencies", []),
                estimated_time=subtask_data["estimated_time"]
            )
            tasks[subtask.id] = subtask
            root_task.subtasks.append(subtask.id)
        
        return TaskTree(
            root_task=root_task,
            tasks=tasks
        )
    
    def get_task_tree(self, tree_id: str) -> Optional[TaskTree]:
        """获取任务树"""
        return self.task_trees.get(tree_id)
    
    def list_task_trees(self) -> List[TaskTree]:
        """列出所有任务树"""
        return list(self.task_trees.values())
    
    def update_task_status(self, tree_id: str, task_id: str, status: TaskStatus) -> bool:
        """更新任务状态"""
        task_tree = self.task_trees.get(tree_id)
        if not task_tree:
            return False
        
        task = task_tree.tasks.get(task_id)
        if not task:
            return False
        
        task.status = status
        if status == TaskStatus.IN_PROGRESS and not task.started_at:
            task.started_at = datetime.now()
        elif status == TaskStatus.COMPLETED and not task.completed_at:
            task.completed_at = datetime.now()
            if task.started_at:
                task.actual_time = int((task.completed_at - task.started_at).total_seconds() / 60)
        
        task_tree.modified_at = datetime.now()
        return True
    
    def add_task(self, tree_id: str, task: Task) -> bool:
        """添加任务"""
        task_tree = self.task_trees.get(tree_id)
        if not task_tree:
            return False
        
        task_tree.tasks[task.id] = task
        task_tree.modified_at = datetime.now()
        return True
    
    def remove_task(self, tree_id: str, task_id: str) -> bool:
        """移除任务"""
        task_tree = self.task_trees.get(tree_id)
        if not task_tree:
            return False
        
        if task_id in task_tree.tasks:
            del task_tree.tasks[task_id]
            # 从依赖和子任务中移除
            for task in task_tree.tasks.values():
                if task_id in task.dependencies:
                    task.dependencies.remove(task_id)
                if task_id in task.subtasks:
                    task.subtasks.remove(task_id)
            task_tree.modified_at = datetime.now()
            return True
        
        return False
    
    def get_task_dependencies(self, tree_id: str, task_id: str) -> List[Task]:
        """获取任务依赖"""
        task_tree = self.task_trees.get(tree_id)
        if not task_tree:
            return []
        
        task = task_tree.tasks.get(task_id)
        if not task:
            return []
        
        dependencies = []
        for dep_id in task.dependencies:
            dep_task = task_tree.tasks.get(dep_id)
            if dep_task:
                dependencies.append(dep_task)
        
        return dependencies
    
    def get_task_subtasks(self, tree_id: str, task_id: str) -> List[Task]:
        """获取任务子任务"""
        task_tree = self.task_trees.get(tree_id)
        if not task_tree:
            return []
        
        task = task_tree.tasks.get(task_id)
        if not task:
            return []
        
        subtasks = []
        for sub_id in task.subtasks:
            sub_task = task_tree.tasks.get(sub_id)
            if sub_task:
                subtasks.append(sub_task)
        
        return subtasks
    
    def get_task_tree_stats(self, tree_id: str) -> Dict[str, Any]:
        """获取任务树统计信息"""
        task_tree = self.task_trees.get(tree_id)
        if not task_tree:
            return {}
        
        stats = {
            "total_tasks": len(task_tree.tasks),
            "pending_tasks": 0,
            "in_progress_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "total_estimated_time": 0,
            "total_actual_time": 0
        }
        
        for task in task_tree.tasks.values():
            if task.status == TaskStatus.PENDING:
                stats["pending_tasks"] += 1
            elif task.status == TaskStatus.IN_PROGRESS:
                stats["in_progress_tasks"] += 1
            elif task.status == TaskStatus.COMPLETED:
                stats["completed_tasks"] += 1
            elif task.status == TaskStatus.FAILED:
                stats["failed_tasks"] += 1
            
            stats["total_estimated_time"] += task.estimated_time
            stats["total_actual_time"] += task.actual_time
        
        return stats


class TaskExecutor:
    """任务执行器"""
    
    def __init__(self, task_planner: TaskPlanner):
        self.task_planner = task_planner
        self.execution_callbacks: Dict[TaskType, Callable] = {}
    
    def register_callback(self, task_type: TaskType, callback: Callable):
        """注册任务执行回调"""
        self.execution_callbacks[task_type] = callback
    
    async def execute_task(self, tree_id: str, task_id: str) -> bool:
        """执行任务"""
        task_tree = self.task_planner.get_task_tree(tree_id)
        if not task_tree:
            return False
        
        task = task_tree.tasks.get(task_id)
        if not task:
            return False
        
        # 检查依赖
        dependencies = self.task_planner.get_task_dependencies(tree_id, task_id)
        for dep in dependencies:
            if dep.status != TaskStatus.COMPLETED:
                print(f"任务 {task.title} 依赖的任务 {dep.title} 未完成")
                return False
        
        # 更新状态
        self.task_planner.update_task_status(tree_id, task_id, TaskStatus.IN_PROGRESS)
        
        try:
            # 执行任务
            if task.task_type in self.execution_callbacks:
                result = await self.execution_callbacks[task.task_type](task)
                task.result = result
                self.task_planner.update_task_status(tree_id, task_id, TaskStatus.COMPLETED)
                return True
            else:
                print(f"未找到任务类型 {task.task_type} 的执行回调")
                task.error = f"未找到执行回调"
                self.task_planner.update_task_status(tree_id, task_id, TaskStatus.FAILED)
                return False
        except Exception as e:
            print(f"执行任务失败: {e}")
            task.error = str(e)
            self.task_planner.update_task_status(tree_id, task_id, TaskStatus.FAILED)
            return False
    
    async def execute_task_tree(self, tree_id: str) -> bool:
        """执行任务树"""
        task_tree = self.task_planner.get_task_tree(tree_id)
        if not task_tree:
            return False
        
        # 按优先级排序任务
        tasks = sorted(
            task_tree.tasks.values(),
            key=lambda t: (-t.priority, len(t.dependencies))
        )
        
        # 执行任务
        for task in tasks:
            if task.status == TaskStatus.PENDING:
                success = await self.execute_task(tree_id, task.id)
                if not success:
                    print(f"任务 {task.title} 执行失败")
        
        # 检查是否所有任务都完成
        all_completed = all(
            task.status == TaskStatus.COMPLETED
            for task in task_tree.tasks.values()
        )
        
        return all_completed


def create_task_planner(llm_client=None) -> TaskPlanner:
    """
    创建任务规划器
    
    Args:
        llm_client: LLM客户端
        
    Returns:
        TaskPlanner: 任务规划器实例
    """
    return TaskPlanner(llm_client)


def create_task_executor(task_planner: TaskPlanner) -> TaskExecutor:
    """
    创建任务执行器
    
    Args:
        task_planner: 任务规划器
        
    Returns:
        TaskExecutor: 任务执行器实例
    """
    return TaskExecutor(task_planner)