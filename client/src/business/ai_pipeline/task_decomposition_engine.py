"""
任务分解引擎 - EPIC→User Story→Task三层自动拆解

核心功能：
1. 意图识别：区分任务类型（新功能/修复/优化）
2. 复杂度评估：估算工作量、依赖项、风险
3. 任务拆解：自动生成 EPIC → User Story → Task
4. 技术选型：基于代码库现状推荐技术栈
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json
import os
from pathlib import Path

from business.global_model_router import GlobalModelRouter, ModelCapability


class TaskType(Enum):
    FEATURE = "feature"
    BUGFIX = "bugfix"
    OPTIMIZATION = "optimization"
    REFACTOR = "refactor"
    DOCUMENTATION = "documentation"


class Complexity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Task:
    """任务定义"""
    id: str
    title: str
    description: str
    task_type: TaskType
    complexity: Complexity
    estimated_hours: float
    dependencies: List[str] = field(default_factory=list)
    acceptance_criteria: List[str] = field(default_factory=list)
    priority: int = 0
    status: str = "pending"
    assignee: Optional[str] = None


@dataclass
class UserStory:
    """用户故事"""
    id: str
    title: str
    description: str
    acceptance_criteria: List[str] = field(default_factory=list)
    tasks: List[Task] = field(default_factory=list)
    complexity: Complexity = Complexity.MEDIUM
    estimated_hours: float = 0.0


@dataclass
class Epic:
    """史诗级需求"""
    id: str
    title: str
    description: str
    user_stories: List[UserStory] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    total_estimated_hours: float = 0.0


@dataclass
class DecompositionResult:
    """分解结果"""
    epic: Epic
    execution_plan: List[str]
    dependency_graph: Dict[str, List[str]]
    risk_assessment: Dict[str, Any]
    recommended_tech_stack: List[str]


class TaskDecompositionEngine:
    """
    任务分解引擎
    
    核心特性：
    1. 多层级拆解：EPIC → User Story → Task
    2. 智能复杂度评估
    3. 依赖关系分析
    4. 技术栈推荐
    5. 持续学习优化
    """

    def __init__(self, storage_path: Optional[str] = None):
        self._router = GlobalModelRouter()
        self._storage_path = Path(storage_path or os.path.expanduser("~/.livingtree/decomposition"))
        self._storage_path.mkdir(parents=True, exist_ok=True)
        
        self._learning_patterns: Dict[str, Any] = {}
        self._load_learning_patterns()

    def _load_learning_patterns(self):
        """加载学习模式"""
        pattern_file = self._storage_path / "patterns.json"
        if pattern_file.exists():
            try:
                with open(pattern_file, 'r', encoding='utf-8') as f:
                    self._learning_patterns = json.load(f)
            except Exception as e:
                print(f"加载学习模式失败: {e}")

    def _save_learning_patterns(self):
        """保存学习模式"""
        pattern_file = self._storage_path / "patterns.json"
        with open(pattern_file, 'w', encoding='utf-8') as f:
            json.dump(self._learning_patterns, f, ensure_ascii=False, indent=2)

    async def decompose(self, requirement: str, context: Optional[Dict[str, Any]] = None) -> DecompositionResult:
        """
        分解用户需求
        
        Args:
            requirement: 用户自然语言需求
            context: 上下文信息（代码库现状、历史数据等）
            
        Returns:
            分解结果
        """
        print(f"🧠 开始任务分解: {requirement[:50]}...")
        
        # 1. 识别任务类型
        task_type = await self._identify_task_type(requirement)
        print(f"📋 识别任务类型: {task_type.value}")
        
        # 2. 尝试使用已学习的模式
        pattern = self._match_pattern(requirement, task_type)
        
        if pattern:
            print(f"🎯 使用已学习模式: {pattern.get('pattern_name')}")
            result = await self._apply_pattern(requirement, pattern, context)
        else:
            print(f"🔍 学习新模式并分解")
            result = await self._generate_decomposition(requirement, task_type, context)
            self._learn_pattern(requirement, task_type, result)
        
        return result

    async def _identify_task_type(self, requirement: str) -> TaskType:
        """识别任务类型"""
        prompt = f"""
分析以下需求，判断任务类型：

需求: {requirement}

任务类型选项：
- feature: 新功能开发
- bugfix: Bug修复
- optimization: 性能优化
- refactor: 代码重构
- documentation: 文档编写

只返回任务类型名称，不要有其他内容。
"""

        response = await self._router.call_model(
            capability=ModelCapability.REASONING,
            prompt=prompt,
            temperature=0.1
        )

        try:
            return TaskType(response.strip().lower())
        except:
            # 兜底规则匹配
            requirement_lower = requirement.lower()
            if any(kw in requirement_lower for kw in ["修复", "bug", "错误", "问题"]):
                return TaskType.BUGFIX
            elif any(kw in requirement_lower for kw in ["优化", "性能", "速度"]):
                return TaskType.OPTIMIZATION
            elif any(kw in requirement_lower for kw in ["重构", "重构代码"]):
                return TaskType.REFACTOR
            elif any(kw in requirement_lower for kw in ["文档", "README", "说明"]):
                return TaskType.DOCUMENTATION
            else:
                return TaskType.FEATURE

    def _match_pattern(self, requirement: str, task_type: TaskType) -> Optional[Dict[str, Any]]:
        """匹配已学习的分解模式"""
        pattern_key = task_type.value
        
        if pattern_key in self._learning_patterns:
            patterns = self._learning_patterns[pattern_key]
            for pattern in patterns:
                keywords = pattern.get("keywords", [])
                if any(kw in requirement for kw in keywords):
                    return pattern
        
        return None

    async def _apply_pattern(self, requirement: str, pattern: Dict[str, Any], context: Optional[Dict[str, Any]]) -> DecompositionResult:
        """应用已学习的模式"""
        epic = Epic(
            id=f"EPIC-{int(datetime.now().timestamp())}",
            title=pattern.get("epic_title", requirement),
            description=requirement
        )
        
        # 根据模式模板生成User Stories
        for us_data in pattern.get("user_stories", []):
            user_story = UserStory(
                id=us_data["id"],
                title=us_data["title"],
                description=us_data.get("description", ""),
                acceptance_criteria=us_data.get("acceptance_criteria", []),
                complexity=Complexity(us_data.get("complexity", "medium")),
                estimated_hours=us_data.get("estimated_hours", 4.0)
            )
            
            for task_data in us_data.get("tasks", []):
                user_story.tasks.append(Task(
                    id=task_data["id"],
                    title=task_data["title"],
                    description=task_data.get("description", ""),
                    task_type=TaskType.FEATURE,
                    complexity=Complexity(task_data.get("complexity", "low")),
                    estimated_hours=task_data.get("estimated_hours", 1.0),
                    dependencies=task_data.get("dependencies", []),
                    acceptance_criteria=task_data.get("acceptance_criteria", [])
                ))
            
            epic.user_stories.append(user_story)
        
        epic.total_estimated_hours = sum(us.estimated_hours for us in epic.user_stories)
        
        return DecompositionResult(
            epic=epic,
            execution_plan=pattern.get("execution_plan", []),
            dependency_graph=pattern.get("dependency_graph", {}),
            risk_assessment=pattern.get("risk_assessment", {}),
            recommended_tech_stack=pattern.get("tech_stack", [])
        )

    async def _generate_decomposition(self, requirement: str, task_type: TaskType, context: Optional[Dict[str, Any]]) -> DecompositionResult:
        """使用LLM生成分解结果"""
        prompt = f"""
作为一个专业的软件需求分析专家，请将以下需求分解为 EPIC → User Story → Task 层级结构。

需求: {requirement}
任务类型: {task_type.value}

输出格式（JSON）:
{{
    "epic": {{
        "title": "EPIC标题",
        "description": "EPIC描述",
        "dependencies": ["依赖项1", "依赖项2"],
        "risks": ["风险1", "风险2"]
    }},
    "user_stories": [
        {{
            "id": "US-001",
            "title": "用户故事标题",
            "description": "用户故事描述",
            "acceptance_criteria": ["条件1", "条件2"],
            "complexity": "low|medium|high|critical",
            "estimated_hours": 4.0,
            "tasks": [
                {{
                    "id": "T-001",
                    "title": "任务标题",
                    "description": "任务描述",
                    "complexity": "low|medium|high",
                    "estimated_hours": 1.0,
                    "dependencies": ["T-002"],
                    "acceptance_criteria": ["完成条件"]
                }}
            ]
        }}
    ],
    "execution_plan": ["步骤1", "步骤2", "步骤3"],
    "dependency_graph": {{
        "US-001": ["US-002"]
    }},
    "risk_assessment": {{
        "high": ["高风险项"],
        "medium": ["中风险项"]
    }},
    "recommended_tech_stack": ["技术1", "技术2"]
}}

注意事项：
1. 用户故事数量建议3-7个
2. 每个用户故事包含3-5个任务
3. 复杂度评估要合理
4. 估计时间要符合实际开发经验
"""

        response = await self._router.call_model(
            capability=ModelCapability.REASONING,
            prompt=prompt,
            temperature=0.2
        )

        try:
            result = json.loads(response)
            
            epic = Epic(
                id=f"EPIC-{int(datetime.now().timestamp())}",
                title=result["epic"]["title"],
                description=result["epic"]["description"],
                dependencies=result["epic"].get("dependencies", []),
                risks=result["epic"].get("risks", [])
            )
            
            total_hours = 0.0
            
            for us_data in result["user_stories"]:
                user_story = UserStory(
                    id=us_data["id"],
                    title=us_data["title"],
                    description=us_data.get("description", ""),
                    acceptance_criteria=us_data.get("acceptance_criteria", []),
                    complexity=Complexity(us_data.get("complexity", "medium")),
                    estimated_hours=us_data.get("estimated_hours", 4.0)
                )
                
                total_hours += user_story.estimated_hours
                
                for task_data in us_data.get("tasks", []):
                    user_story.tasks.append(Task(
                        id=task_data["id"],
                        title=task_data["title"],
                        description=task_data.get("description", ""),
                        task_type=task_type,
                        complexity=Complexity(task_data.get("complexity", "low")),
                        estimated_hours=task_data.get("estimated_hours", 1.0),
                        dependencies=task_data.get("dependencies", []),
                        acceptance_criteria=task_data.get("acceptance_criteria", [])
                    ))
                
                epic.user_stories.append(user_story)
            
            epic.total_estimated_hours = total_hours
            
            return DecompositionResult(
                epic=epic,
                execution_plan=result.get("execution_plan", []),
                dependency_graph=result.get("dependency_graph", {}),
                risk_assessment=result.get("risk_assessment", {}),
                recommended_tech_stack=result.get("recommended_tech_stack", [])
            )
            
        except Exception as e:
            print(f"❌ LLM分解失败，使用兜底方案: {e}")
            return self._fallback_decomposition(requirement, task_type)

    def _fallback_decomposition(self, requirement: str, task_type: TaskType) -> DecompositionResult:
        """兜底分解方案"""
        epic = Epic(
            id=f"EPIC-{int(datetime.now().timestamp())}",
            title=requirement,
            description=requirement,
            dependencies=[],
            risks=[]
        )
        
        user_story = UserStory(
            id="US-001",
            title=f"实现{requirement[:20]}",
            description=f"完成{requirement}",
            acceptance_criteria=["功能实现完成", "测试通过"],
            complexity=Complexity.MEDIUM,
            estimated_hours=8.0
        )
        
        user_story.tasks.append(Task(
            id="T-001",
            title="需求分析",
            description="分析需求并确定技术方案",
            task_type=task_type,
            complexity=Complexity.LOW,
            estimated_hours=1.0
        ))
        
        user_story.tasks.append(Task(
            id="T-002",
            title="代码实现",
            description="实现核心功能",
            task_type=task_type,
            complexity=Complexity.MEDIUM,
            estimated_hours=4.0,
            dependencies=["T-001"]
        ))
        
        user_story.tasks.append(Task(
            id="T-003",
            title="单元测试",
            description="编写单元测试",
            task_type=task_type,
            complexity=Complexity.LOW,
            estimated_hours=2.0,
            dependencies=["T-002"]
        ))
        
        user_story.tasks.append(Task(
            id="T-004",
            title="代码审查",
            description="代码审查和优化",
            task_type=task_type,
            complexity=Complexity.LOW,
            estimated_hours=1.0,
            dependencies=["T-003"]
        ))
        
        epic.user_stories.append(user_story)
        epic.total_estimated_hours = 8.0
        
        return DecompositionResult(
            epic=epic,
            execution_plan=["需求分析", "代码实现", "单元测试", "代码审查"],
            dependency_graph={"US-001": []},
            risk_assessment={"low": ["基础功能风险较低"]},
            recommended_tech_stack=["Python", "PyQt6"]
        )

    def _learn_pattern(self, requirement: str, task_type: TaskType, result: DecompositionResult):
        """学习新的分解模式"""
        pattern_key = task_type.value
        
        if pattern_key not in self._learning_patterns:
            self._learning_patterns[pattern_key] = []
        
        # 提取关键词
        words = requirement.split()[:5]
        
        pattern = {
            "pattern_name": f"{task_type.value}_{len(self._learning_patterns[pattern_key])}",
            "keywords": words,
            "epic_title": result.epic.title,
            "user_stories": [],
            "execution_plan": result.execution_plan,
            "dependency_graph": result.dependency_graph,
            "risk_assessment": result.risk_assessment,
            "tech_stack": result.recommended_tech_stack,
            "usage_count": 1,
            "success_count": 1,
            "created_at": datetime.now().isoformat()
        }
        
        for us in result.epic.user_stories:
            us_data = {
                "id": us.id,
                "title": us.title,
                "description": us.description,
                "acceptance_criteria": us.acceptance_criteria,
                "complexity": us.complexity.value,
                "estimated_hours": us.estimated_hours,
                "tasks": []
            }
            
            for task in us.tasks:
                us_data["tasks"].append({
                    "id": task.id,
                    "title": task.title,
                    "description": task.description,
                    "complexity": task.complexity.value,
                    "estimated_hours": task.estimated_hours,
                    "dependencies": task.dependencies,
                    "acceptance_criteria": task.acceptance_criteria
                })
            
            pattern["user_stories"].append(us_data)
        
        self._learning_patterns[pattern_key].append(pattern)
        self._save_learning_patterns()
        
        print(f"📝 学习新分解模式: {pattern['pattern_name']}")

    def update_pattern_success(self, pattern_key: str, success: bool):
        """更新模式成功率"""
        if pattern_key in self._learning_patterns:
            for pattern in self._learning_patterns[pattern_key]:
                pattern["usage_count"] = pattern.get("usage_count", 0) + 1
                if success:
                    pattern["success_count"] = pattern.get("success_count", 0) + 1
            self._save_learning_patterns()

    def get_pattern_stats(self) -> Dict[str, Any]:
        """获取模式统计"""
        stats = {}
        for task_type, patterns in self._learning_patterns.items():
            total_usage = sum(p.get("usage_count", 0) for p in patterns)
            total_success = sum(p.get("success_count", 0) for p in patterns)
            
            stats[task_type] = {
                "pattern_count": len(patterns),
                "total_usage": total_usage,
                "success_rate": total_success / total_usage if total_usage > 0 else 0.0
            }
        
        return stats


def get_task_decomposition_engine() -> TaskDecompositionEngine:
    """获取任务分解引擎单例"""
    global _decomposition_engine_instance
    if _decomposition_engine_instance is None:
        _decomposition_engine_instance = TaskDecompositionEngine()
    return _decomposition_engine_instance


_decomposition_engine_instance = None