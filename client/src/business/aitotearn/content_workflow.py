"""
内容工作流模块

支持内容创作和发布的工作流编排：
- 内容策划
- 素材收集
- 内容生成
- 多平台发布
- 数据追踪
"""

import time
import asyncio
from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod


# ============ 工作流状态 ============

class WorkflowStatus(Enum):
    """工作流状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ============ 任务类型 ============

class TaskType(Enum):
    """任务类型"""
    CONTENT_CREATE = "content_create"      # 内容创作
    CONTENT_PLAN = "content_plan"         # 内容策划
    MATERIAL_COLLECT = "material_collect" # 素材收集
    CONTENT_PUBLISH = "content_publish"   # 内容发布
    DATA_TRACK = "data_track"            # 数据追踪
    ENGAGE = "engage"                    # 社交互动


# ============ 工作流任务 ============

@dataclass
class WorkflowTask:
    """工作流任务"""
    task_id: str
    task_type: TaskType
    description: str
    status: WorkflowStatus = WorkflowStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowResult:
    """工作流结果"""
    workflow_id: str
    success: bool
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_duration: float = 0
    results: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


# ============ 内容策划器 ============

class ContentPlanner:
    """
    内容策划器
    
    生成内容发布计划
    """
    
    def __init__(self):
        self.topics = []
        self.schedule = {}
    
    def add_topic(self, topic: str, priority: int = 1):
        """添加主题"""
        self.topics.append({
            "topic": topic,
            "priority": priority,
            "added_at": time.time(),
        })
    
    def generate_schedule(
        self,
        platforms: List[str],
        posts_per_week: int = 10
    ) -> List[Dict[str, Any]]:
        """
        生成分发计划
        
        Args:
            platforms: 平台列表
            posts_per_week: 每周帖子数
            
        Returns:
            List: 发布计划
        """
        schedule = []
        
        # 按优先级排序主题
        sorted_topics = sorted(self.topics, key=lambda x: x["priority"], reverse=True)
        
        posts_per_platform = posts_per_week // len(platforms) if platforms else 0
        
        for i, topic in enumerate(sorted_topics[:posts_per_week]):
            for j, platform in enumerate(platforms):
                schedule.append({
                    "task_id": f"plan_{i}_{j}",
                    "topic": topic["topic"],
                    "platform": platform,
                    "scheduled_time": self._calculate_time(i, j),
                    "priority": topic["priority"],
                })
        
        return schedule
    
    def _calculate_time(self, post_index: int, platform_index: int) -> float:
        """计算发布时间"""
        # 简单按顺序排，每天每个平台一篇
        days_offset = post_index // len(self.schedule) if self.schedule else 0
        return time.time() + (days_offset + 1) * 24 * 3600


# ============ 素材收集器 ============

class MaterialCollector:
    """
    素材收集器
    
    收集内容创作所需的素材
    """
    
    def __init__(self):
        self.materials = []
        self.sources = ["web", "ai_generate", "user_upload"]
    
    async def collect(
        self,
        topic: str,
        source: str = "web",
        max_materials: int = 10
    ) -> List[Dict[str, Any]]:
        """
        收集素材
        
        Args:
            topic: 主题
            source: 来源
            max_materials: 最大素材数
            
        Returns:
            List: 素材列表
        """
        materials = []
        
        if source == "web":
            # 模拟网络搜索
            await asyncio.sleep(0.1)
            materials = [
                {
                    "type": "text",
                    "content": f"关于 {topic} 的相关信息...",
                    "source": "web_search",
                }
                for _ in range(min(5, max_materials))
            ]
        elif source == "ai_generate":
            # 模拟 AI 生成
            await asyncio.sleep(0.2)
            materials = [
                {
                    "type": "image",
                    "content": f"AI 生成的 {topic} 相关图片",
                    "source": "ai_image_model",
                }
                for _ in range(min(3, max_materials))
            ]
        
        self.materials.extend(materials)
        return materials
    
    def get_materials(self, topic: str = None) -> List[Dict[str, Any]]:
        """获取素材"""
        if topic:
            return [m for m in self.materials if topic in str(m.get("content", ""))]
        return self.materials


# ============ 内容生成器 ============

class ContentGenerator:
    """
    内容生成器
    
    生成各类内容
    """
    
    def __init__(self, llm_client: Optional[Callable] = None):
        self.llm_client = llm_client
        self.generated_content = []
    
    async def generate(
        self,
        topic: str,
        content_type: str,  # video, image, article
        materials: List[Dict[str, Any]] = None,
        style: str = "friendly",
        language: str = "zh"
    ) -> Dict[str, Any]:
        """
        生成内容
        
        Args:
            topic: 主题
            content_type: 内容类型
            materials: 素材
            style: 风格
            language: 语言
            
        Returns:
            Dict: 生成的内容
        """
        content = {
            "topic": topic,
            "type": content_type,
            "style": style,
            "language": language,
            "created_at": time.time(),
        }
        
        if self.llm_client and materials:
            # 使用 LLM 生成
            prompt = self._build_prompt(topic, content_type, materials, style, language)
            result = await self.llm_client(prompt)
            content["body"] = result
        else:
            # 默认生成
            content["body"] = f"这是一篇关于 {topic} 的{content_type}内容"
            content["title"] = f"{topic} - 内容创作"
        
        if content_type == "video":
            content["script"] = f"视频脚本：{content['body']}"
            content["duration"] = 60  # 秒
        elif content_type == "article":
            content["body"] = f"# {content['title']}\n\n{content['body']}"
        
        self.generated_content.append(content)
        return content
    
    def _build_prompt(
        self,
        topic: str,
        content_type: str,
        materials: List[Dict[str, Any]],
        style: str,
        language: str
    ) -> str:
        """构建提示"""
        materials_text = "\n".join([str(m.get("content", "")) for m in materials])
        
        return f"""根据以下素材，生成一篇关于 "{topic}" 的{content_type}内容。
风格：{style}
语言：{language}

素材：
{materials_text}
"""


# ============ 内容工作流 ============

class ContentWorkflow:
    """
    内容工作流
    
    编排内容创作和发布的完整流程
    """
    
    def __init__(
        self,
        platform_manager,  # MultiPlatformManager
        content_planner: Optional[ContentPlanner] = None,
        material_collector: Optional[MaterialCollector] = None,
        content_generator: Optional[ContentGenerator] = None,
    ):
        self.platform_manager = platform_manager
        self.content_planner = content_planner or ContentPlanner()
        self.material_collector = material_collector or MaterialCollector()
        self.content_generator = content_generator or ContentGenerator()
        
        # 任务列表
        self.tasks: List[WorkflowTask] = []
        
        # 回调
        self.on_task_start: Optional[Callable[[WorkflowTask], None]] = None
        self.on_task_complete: Optional[Callable[[WorkflowTask], None]] = None
        self.on_workflow_complete: Optional[Callable[[WorkflowResult], None]] = None
    
    async def execute(
        self,
        topics: List[str],
        platforms: List[str],
        content_type: str = "article",
        auto_engage: bool = False
    ) -> WorkflowResult:
        """
        执行内容工作流
        
        Args:
            topics: 主题列表
            platforms: 平台列表
            content_type: 内容类型
            auto_engage: 是否自动互动
            
        Returns:
            WorkflowResult: 工作流结果
        """
        workflow_id = f"workflow_{int(time.time())}"
        start_time = time.time()
        
        # 添加策划任务
        for topic in topics:
            self.content_planner.add_topic(topic)
        
        # 生成分发计划
        schedule = self.content_planner.generate_schedule(platforms)
        
        results = {}
        errors = []
        tasks_completed = 0
        tasks_failed = 0
        
        # 执行计划
        for plan in schedule:
            task = WorkflowTask(
                task_id=plan["task_id"],
                task_type=TaskType.CONTENT_PUBLISH,
                description=f"发布到 {plan['platform']}: {plan['topic']}",
            )
            self.tasks.append(task)
            
            # 触发任务开始
            task.status = WorkflowStatus.RUNNING
            task.started_at = time.time()
            
            if self.on_task_start:
                self.on_task_start(task)
            
            try:
                # 1. 收集素材
                materials = await self.material_collector.collect(
                    plan["topic"],
                    source="web"
                )
                
                # 2. 生成内容
                content = await self.content_generator.generate(
                    topic=plan["topic"],
                    content_type=content_type,
                    materials=materials
                )
                
                # 3. 发布到平台
                from .platform_tools import PlatformType, Content, ContentType
                
                platform_type = PlatformType(plan["platform"])
                content_obj = Content(
                    title=content.get("title", plan["topic"]),
                    body=content.get("body", ""),
                    content_type=ContentType.ARTICLE if content_type == "article" else ContentType.VIDEO
                )
                
                publish_results = await self.platform_manager.publish([platform_type], content_obj)
                
                # 4. 自动互动（如果启用）
                engage_results = {}
                if auto_engage:
                    # 模拟互动
                    engage_results = {"simulated": True}
                
                # 任务完成
                task.status = WorkflowStatus.COMPLETED
                task.completed_at = time.time()
                task.result = {
                    "content": content,
                    "publish_results": publish_results,
                    "engage_results": engage_results,
                }
                
                results[plan["task_id"]] = task.result
                tasks_completed += 1
                
                if self.on_task_complete:
                    self.on_task_complete(task)
                
            except Exception as e:
                task.status = WorkflowStatus.FAILED
                task.error = str(e)
                task.completed_at = time.time()
                errors.append(f"{plan['task_id']}: {str(e)}")
                tasks_failed += 1
        
        # 构建工作流结果
        total_duration = time.time() - start_time
        
        workflow_result = WorkflowResult(
            workflow_id=workflow_id,
            success=tasks_failed == 0,
            tasks_completed=tasks_completed,
            tasks_failed=tasks_failed,
            total_duration=total_duration,
            results=results,
            errors=errors
        )
        
        if self.on_workflow_complete:
            self.on_workflow_complete(workflow_result)
        
        return workflow_result
    
    def get_tasks(self, status: WorkflowStatus = None) -> List[WorkflowTask]:
        """获取任务列表"""
        if status:
            return [t for t in self.tasks if t.status == status]
        return self.tasks
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        for task in self.tasks:
            if task.task_id == task_id and task.status == WorkflowStatus.PENDING:
                task.status = WorkflowStatus.CANCELLED
                task.completed_at = time.time()
                return True
        return False


# ============ 导出 ============

__all__ = [
    "WorkflowStatus",
    "TaskType",
    "WorkflowTask",
    "WorkflowResult",
    "ContentPlanner",
    "MaterialCollector",
    "ContentGenerator",
    "ContentWorkflow",
]
