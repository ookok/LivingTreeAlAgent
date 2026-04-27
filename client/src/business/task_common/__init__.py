"""
Task Common - 任务分解器公共接口

提供所有任务分解器的公共抽象和工厂方法。
各领域的分解器应通过工厂方法创建，返回统一接口。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# ============================================================
# 公共枚举和数据类
# ============================================================

class DecomposerType(Enum):
    """分解器类型"""
    BASIC = "basic"              # 基础分解器（task_decomposer.py）
    DYNAMIC = "dynamic"          # 动态分解器（multi_agent/workflow_engine.py）
    SMART = "smart"              # 智能分解器（task_execution_engine.py）
    LLM_POWERED = "llm"        # LLM 驱动分解器


@dataclass
class TaskStep:
    """任务步骤（公共）"""
    step_id: str
    title: str
    description: str
    instruction: str
    input_data: Any = None
    output_data: Any = None
    status: str = "pending"      # pending/running/completed/failed/skipped
    error: Optional[str] = None
    confidence: float = 0.0
    depends_on: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "confidence": self.confidence,
            "error": self.error,
            "has_output": self.output_data is not None,
        }


@dataclass
class DecomposedTask:
    """分解后的任务（公共）"""
    task_id: str
    original_question: str
    steps: List[TaskStep]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def total_steps(self) -> int:
        return len(self.steps)
    
    @property
    def completed_steps(self) -> int:
        return sum(1 for s in self.steps if s.status == "completed")
    
    @property
    def progress(self) -> float:
        if self.total_steps == 0:
            return 0.0
        return self.completed_steps / self.total_steps
    
    def get_step(self, step_id: str) -> Optional[TaskStep]:
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None
    
    def can_execute_step(self, step_id: str) -> bool:
        step = self.get_step(step_id)
        if not step or step.status != "pending":
            return False
        return all(
            self.get_step(dep).status == "completed"
            for dep in step.depends_on
        )
    
    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "original_question": self.original_question,
            "steps": [s.to_dict() for s in self.steps],
            "metadata": self.metadata,
            "progress": self.progress,
            "completed": self.completed_steps,
            "total": self.total_steps,
        }


# ============================================================
# 抽象基类
# ============================================================

class BaseTaskDecomposer(ABC):
    """
    任务分解器抽象基类
    
    所有任务分解器应实现此接口。
    这样调用者无需关心底层是哪种分解器。
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        logger.info(f"[{self.__class__.__name__}] 初始化完成")
    
    # ---------- 子类必须实现的抽象方法 ----------
    
    @abstractmethod
    def decompose(self, task: str, **kwargs) -> DecomposedTask:
        """
        分解任务为子步骤
        
        Args:
            task: 原始任务描述
            **kwargs: 领域特定参数
            
        Returns:
            分解后的任务
        """
        pass
    
    @abstractmethod
    def execute_step(self, task: DecomposedTask, step_id: str, **kwargs) -> Any:
        """
        执行单个步骤
        
        Args:
            task: 分解后的任务
            step_id: 步骤 ID
            **kwargs: 执行参数
            
        Returns:
            步骤执行结果
        """
        pass
    
    # ---------- 可选覆盖的方法 ----------
    
    def refine(self, task: DecomposedTask, feedback: str) -> DecomposedTask:
        """
        根据反馈优化分解（默认实现：不优化）
        
        Args:
            task: 分解后的任务
            feedback: 用户反馈
            
        Returns:
            优化后的任务
        """
        logger.warning(f"[{self.__class__.__name__}] refine() 未实现，跳过优化")
        return task
    
    def merge(self, tasks: List[DecomposedTask]) -> DecomposedTask:
        """
        合并多个分解结果（默认实现：取第一个）
        
        Args:
            tasks: 多个分解结果
            
        Returns:
            合并后的任务
        """
        if not tasks:
            raise ValueError("任务列表为空")
        return tasks[0]
    
    # ---------- 公共工具方法 ----------
    
    def validate(self, task: DecomposedTask) -> bool:
        """验证分解结果是否合法"""
        if not task.steps:
            return False
        # 检查依赖是否形成环
        visited = set()
        for step in task.steps:
            if step.step_id in visited:
                return False
            visited.add(step.step_id)
        return True
    
    def visualize(self, task: DecomposedTask) -> str:
        """生成分解结果的可视化文本"""
        lines = [
            f"任务: {task.original_question}",
            f"进度: {task.progress*100:.0f}% ({task.completed_steps}/{task.total_steps})",
            "",
            "步骤:",
        ]
        for i, step in enumerate(task.steps, 1):
            status_icon = {
                "pending": "○",
                "running": "◔",
                "completed": "●",
                "failed": "✗",
                "skipped": "⊘",
            }.get(step.status, "?")
            lines.append(f"  {i}. [{status_icon}] {step.title}")
            if step.description:
                lines.append(f"       {step.description}")
        return "\n".join(lines)


# ============================================================
# 工厂方法
# ============================================================

def create_decomposer(
    decomposer_type: DecomposerType,
    config: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> BaseTaskDecomposer:
    """
    根据类型创建对应的任务分解器
    
    Args:
        decomposer_type: 分解器类型
        config: 配置字典
        **kwargs: 传递给具体分解器的额外参数
        
    Returns:
        对应的任务分解器实例
    """
    if decomposer_type == DecomposerType.BASIC:
        from client.src.business.task_decomposer import TaskDecomposer
        return TaskDecomposer()
    
    elif decomposer_type == DecomposerType.DYNAMIC:
        from client.src.business.multi_agent.workflow_engine import DynamicTaskDecomposer
        return DynamicTaskDecomposer()
    
    elif decomposer_type == DecomposerType.SMART:
        from client.src.business.task_execution_engine import SmartDecomposer
        return SmartDecomposer(**kwargs)
    
    else:
        raise ValueError(f"不支持的分解器类型: {decomposer_type}")


def auto_select_decomposer(task: str) -> DecomposerType:
    """
    根据任务自动选择合适的分解器类型
    
    Args:
        task: 任务描述
        
    Returns:
        推荐的分解器类型
    """
    task_lower = task.lower()
    
    # 多智能体协作任务 → 动态分解器
    if any(kw in task_lower for kw in ["协作", "多代理", "multi-agent", "分布式"]):
        return DecomposerType.DYNAMIC
    
    # 需要智能优化的任务 → 智能分解器
    if any(kw in task_lower for kw in ["优化", "自适应", "学习", "反馈"]):
        return DecomposerType.SMART
    
    # 默认 → 基础分解器
    return DecomposerType.BASIC


from .facade import (
    TaskDecomposerFacade,
    get_task_decomposer_facade,
    decompose_task,
    execute_step,
)

__all__ = [
    "DecomposerType",
    "TaskStep",
    "DecomposedTask",
    "BaseTaskDecomposer",
    "create_decomposer",
    "auto_select_decomposer",
    "TaskDecomposerFacade",
    "get_task_decomposer_facade",
    "decompose_task",
    "execute_step",
]
