"""
任务规划系统（Trae 增强版）
==========================

整合 Trae IDE 的任务拆解 SKILL，增强智能任务拆解能力：
1. 与 TaskDecomposer 深度集成
2. 风险识别与应对方案
3. 优先级智能排序
4. 依赖关系可视化
5. 验收清单生成

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import re
import asyncio
import json
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from business.task_decomposer import (
    DecomposedTask,
    TaskStep,
    TaskDecomposer,
    ProcessType,
    create_task_split_task,
)
from business.agent_skills.task_decomposition_skills import (
    TaskSplitterProSkill,
    get_task_splitter,
)


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
    BLOCKED = "blocked"  # 新增：被依赖阻塞


class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskPriority(Enum):
    """任务优先级（增强版）"""
    CRITICAL = 10  # 关键任务，必须优先完成
    HIGH = 8       # 高优先级，核心功能
    MEDIUM = 5     # 中等优先级，重要但非紧急
    LOW = 2        # 低优先级，边缘功能
    OPTIONAL = 0   # 可选任务，锦上添花


@dataclass
class RiskInfo:
    """风险信息"""
    level: RiskLevel
    description: str
    mitigation: str  # 应对方案
    fallback: str = ""  # 备选方案


@dataclass
class AcceptanceCriteria:
    """验收标准"""
    criteria: List[str]
    pass_condition: str = "all"  # all 或 any


@dataclass
class Task:
    """任务（增强版）"""
    id: str
    title: str
    description: str
    task_type: TaskType
    priority: int = 5  # 0-10，10最高
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
    
    # 新增字段（Trae 增强）
    risk_info: Optional[RiskInfo] = None  # 风险信息
    acceptance_criteria: Optional[AcceptanceCriteria] = None  # 验收标准
    tags: List[str] = field(default_factory=list)  # 标签
    assignee: Optional[str] = None  # 负责人
    phase: Optional[str] = None  # 所属阶段
    order: int = 0  # 同阶段排序


@dataclass
class TaskTree:
    """任务树（增强版）"""
    root_task: Task
    tasks: Dict[str, Task] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)
    
    # 新增字段（Trae 增强）
    phases: List[str] = field(default_factory=list)  # 阶段列表
    critical_path: List[str] = field(default_factory=list)  # 关键路径任务ID
    high_risk_tasks: List[str] = field(default_factory=list)  # 高风险任务ID
    acceptance_checklist: List[str] = field(default_factory=list)  # 验收清单


class TaskPlanner:
    """任务规划器（Trae 增强版）
    
    整合 Trae IDE 的任务拆解能力：
    - 智能任务拆解
    - 风险识别与应对
    - 优先级排序
    - 依赖关系管理
    - 验收清单生成
    """
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.task_trees: Dict[str, TaskTree] = {}
        self._task_counter = 0
        self._task_decomposer = TaskDecomposer()
    
    def _detect_risk(self, task_description: str) -> Optional[RiskInfo]:
        """
        智能检测任务风险
        
        Args:
            task_description: 任务描述
            
        Returns:
            RiskInfo: 风险信息（如果检测到风险）
        """
        desc_lower = task_description.lower()
        
        # 高风险关键词
        critical_keywords = [
            "第三方接口", "第三方服务", "外部API",
            "支付接口", "支付服务", "支付",
            "复杂算法", "高性能", "大规模",
            "性能优化", "并发", "分布式",
            "数据库迁移", "数据同步", "数据迁移"
        ]
        
        high_keywords = [
            "新功能", "新技术", "首次",
            "复杂", "难点", "挑战",
            "集成", "对接", "联调"
        ]
        
        # 检测风险
        if any(k in desc_lower for k in critical_keywords):
            return RiskInfo(
                level=RiskLevel.CRITICAL,
                description=f"任务涉及高风险内容: {', '.join([k for k in critical_keywords if k in desc_lower])}",
                mitigation="1. 提前进行技术调研 2. 制定详细方案 3. 预留缓冲时间 4. 准备备选方案",
                fallback="考虑简化需求或寻找替代方案"
            )
        elif any(k in desc_lower for k in high_keywords):
            return RiskInfo(
                level=RiskLevel.HIGH,
                description=f"任务存在较高风险: {', '.join([k for k in high_keywords if k in desc_lower])}",
                mitigation="1. 进行充分测试 2. 寻求专家帮助 3. 分阶段实施",
                fallback="调整任务优先级或拆分任务"
            )
        
        return None
    
    def _generate_acceptance_criteria(self, task_title: str, task_description: str) -> AcceptanceCriteria:
        """
        生成任务验收标准
        
        Args:
            task_title: 任务标题
            task_description: 任务描述
            
        Returns:
            AcceptanceCriteria: 验收标准
        """
        criteria = []
        
        # 根据任务类型生成验收标准
        title_lower = task_title.lower()
        
        if "代码" in title_lower or "开发" in title_lower:
            criteria.extend([
                "代码符合编码规范",
                "通过单元测试",
                "无语法错误",
                "代码覆盖率达标"
            ])
        
        if "接口" in title_lower or "API" in title_lower:
            criteria.extend([
                "接口文档完整",
                "接口测试通过",
                "性能指标达标",
                "错误处理完善"
            ])
        
        if "测试" in title_lower:
            criteria.extend([
                "测试用例覆盖全面",
                "测试通过率100%",
                "测试报告完整"
            ])
        
        if "文档" in title_lower:
            criteria.extend([
                "文档内容完整",
                "格式规范",
                "内容准确"
            ])
        
        # 默认验收标准
        if not criteria:
            criteria = [
                "任务完成",
                "符合需求描述",
                "无明显缺陷"
            ]
        
        return AcceptanceCriteria(criteria=criteria)
    
    def _calculate_critical_path(self, task_tree: TaskTree) -> List[str]:
        """
        计算关键路径
        
        Args:
            task_tree: 任务树
            
        Returns:
            List[str]: 关键路径上的任务ID列表
        """
        critical_path = []
        
        # 简单策略：优先级最高且有依赖关系的任务构成关键路径
        tasks = sorted(
            task_tree.tasks.values(),
            key=lambda t: (-t.priority, len(t.dependencies))
        )
        
        # 找到最长依赖链
        for task in tasks:
            if task.priority >= 8:  # 高优先级
                critical_path.append(task.id)
                # 添加依赖的任务
                for dep_id in task.dependencies:
                    if dep_id not in critical_path:
                        critical_path.append(dep_id)
        
        return critical_path
    
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
    
    async def decompose_with_trae_skill(self, requirement: str) -> Optional[TaskTree]:
        """
        使用 Trae 的智能任务拆解大师 SKILL 进行任务拆解
        
        Args:
            requirement: 用户需求描述
            
        Returns:
            TaskTree: 拆解后的任务树
        """
        try:
            # 获取任务拆解技能
            skill = get_task_splitter()
            logger = __import__('logging').getLogger(__name__)
            logger.info(f"[TaskPlanner] 使用 Trae 任务拆解技能: {skill.get_manifest().name}")
            
            # 激活技能进行拆解
            decomposed_task = skill.activate(requirement)
            
            # 将 DecomposedTask 转换为 TaskTree
            task_tree = await self._convert_to_task_tree(decomposed_task, requirement)
            
            # 保存任务树
            tree_id = f"tree_{int(datetime.now().timestamp())}"
            self.task_trees[tree_id] = task_tree
            
            logger.info(f"[TaskPlanner] 任务拆解完成，生成 {len(task_tree.tasks)} 个任务")
            return task_tree
        except Exception as e:
            print(f"使用 Trae 技能拆解失败: {e}")
            # 回退到传统方法
            return await self.plan_from_natural_language(requirement)
    
    async def _convert_to_task_tree(self, decomposed_task: DecomposedTask, requirement: str) -> TaskTree:
        """
        将 DecomposedTask 转换为 TaskTree
        
        Args:
            decomposed_task: 拆解后的任务
            requirement: 原始需求
            
        Returns:
            TaskTree: 转换后的任务树
        """
        # 创建根任务
        root_task = Task(
            id=self._generate_task_id(),
            title=requirement,
            description=requirement,
            task_type=TaskType.OTHER,
            priority=10,
            phase="整体任务"
        )
        
        tasks = {root_task.id: root_task}
        
        # 阶段列表
        phases = []
        high_risk_tasks = []
        
        # 将步骤转换为任务
        for i, step in enumerate(decomposed_task.steps):
            # 确定任务类型
            task_type = self._map_step_to_task_type(step.title)
            
            # 确定优先级
            priority = self._calculate_priority(i, len(decomposed_task.steps), step.title)
            
            # 创建任务
            task = Task(
                id=self._generate_task_id(),
                title=step.title,
                description=step.description,
                task_type=task_type,
                priority=priority,
                estimated_time=self._estimate_time(step.title),
                phase=step.title,
                order=i,
                tags=[step.title],
            )
            
            # 检测风险
            risk_info = self._detect_risk(step.description)
            if risk_info:
                task.risk_info = risk_info
                if risk_info.level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                    high_risk_tasks.append(task.id)
            
            # 生成验收标准
            task.acceptance_criteria = self._generate_acceptance_criteria(step.title, step.description)
            
            # 设置依赖
            if step.depends_on:
                task.dependencies = step.depends_on
            
            tasks[task.id] = task
            root_task.subtasks.append(task.id)
            
            # 添加阶段
            if step.title not in phases:
                phases.append(step.title)
        
        # 创建任务树
        task_tree = TaskTree(
            root_task=root_task,
            tasks=tasks,
            phases=phases,
            high_risk_tasks=high_risk_tasks,
        )
        
        # 计算关键路径
        task_tree.critical_path = self._calculate_critical_path(task_tree)
        
        # 生成验收清单
        task_tree.acceptance_checklist = self._generate_acceptance_checklist(task_tree)
        
        return task_tree
    
    def _map_step_to_task_type(self, step_title: str) -> TaskType:
        """
        将步骤标题映射到任务类型
        
        Args:
            step_title: 步骤标题
            
        Returns:
            TaskType: 任务类型
        """
        title_lower = step_title.lower()
        
        if "代码" in title_lower or "开发" in title_lower:
            return TaskType.CODE_GENERATION
        elif "测试" in title_lower:
            return TaskType.TEST_GENERATION
        elif "文档" in title_lower:
            return TaskType.DOCUMENTATION
        elif "优化" in title_lower:
            return TaskType.PERFORMANCE_OPTIMIZATION
        elif "重构" in title_lower:
            return TaskType.REFACTORING
        elif "研究" in title_lower or "调研" in title_lower:
            return TaskType.RESEARCH
        else:
            return TaskType.OTHER
    
    def _calculate_priority(self, index: int, total: int, title: str) -> int:
        """
        计算任务优先级
        
        Args:
            index: 当前步骤索引
            total: 总步骤数
            title: 步骤标题
            
        Returns:
            int: 优先级（0-10）
        """
        title_lower = title.lower()
        
        # 关键任务关键词
        critical_keywords = ["核心", "关键", "必须", "重要", "登录", "支付", "安全"]
        if any(k in title_lower for k in critical_keywords):
            return 10
        
        # 靠前的步骤通常优先级更高
        if index < total * 0.3:
            return 8
        elif index < total * 0.7:
            return 5
        else:
            return 2
    
    def _estimate_time(self, title: str) -> int:
        """
        预估任务时间
        
        Args:
            title: 任务标题
            
        Returns:
            int: 预估时间（分钟）
        """
        title_lower = title.lower()
        
        if "设计" in title_lower:
            return 60
        elif "开发" in title_lower or "代码" in title_lower:
            return 120
        elif "测试" in title_lower:
            return 60
        elif "文档" in title_lower:
            return 30
        elif "调研" in title_lower:
            return 90
        else:
            return 45
    
    def _generate_acceptance_checklist(self, task_tree: TaskTree) -> List[str]:
        """
        生成整体验收清单
        
        Args:
            task_tree: 任务树
            
        Returns:
            List[str]: 验收清单
        """
        checklist = []
        
        # 添加整体验收项
        checklist.append("所有任务完成")
        checklist.append("所有高风险任务已处理")
        checklist.append("关键路径任务全部通过")
        
        # 添加各任务的验收标准
        for task in task_tree.tasks.values():
            if task.acceptance_criteria:
                for criteria in task.acceptance_criteria.criteria:
                    checklist.append(f"{task.title}: {criteria}")
        
        return checklist
    
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


__all__ = [
    # 枚举类型
    "TaskType",
    "TaskStatus",
    "RiskLevel",
    "TaskPriority",
    # 数据类
    "RiskInfo",
    "AcceptanceCriteria",
    "Task",
    "TaskTree",
    # 类
    "TaskPlanner",
    "TaskExecutor",
    # 便捷函数
    "create_task_planner",
    "create_task_executor",
]