"""
Superpowers 模型定义

共享的数据模型和类型定义
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
import time


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    DEFERRED = "deferred"


class WorkflowState:
    """工作流状态"""
    def __init__(
        self,
        workflow_id: str,
        name: str,
        status: TaskStatus,
        current_task: Optional[str] = None,
        completed_tasks: Optional[List[str]] = None,
        pending_tasks: Optional[List[str]] = None,
        created_at: Optional[float] = None,
        updated_at: Optional[float] = None
    ):
        self.workflow_id = workflow_id
        self.name = name
        self.status = status
        self.current_task = current_task
        self.completed_tasks = completed_tasks or []
        self.pending_tasks = pending_tasks or []
        self.created_at = created_at or time.time()
        self.updated_at = updated_at or time.time()


@dataclass
class AgentConfig:
    """代理配置"""
    agent_id: str
    name: str
    model: str = "claude-3-opus-20240229"
    temperature: float = 0.7
    max_tokens: int = 8192
    tools: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)


@dataclass
class SkillDefinition:
    """技能定义"""
    skill_id: str
    name: str
    description: str
    version: str = "1.0.0"
    author: str = "system"
    requires: List[str] = field(default_factory=list)
    triggers: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)