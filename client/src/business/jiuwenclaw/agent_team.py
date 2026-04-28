"""
AgentTeam - Agent团队协同层

实现 JiuwenClaw 的核心功能：
1. Leader + Teammate 架构
2. 共享任务列表
3. Team Workspace（团队共享工作区）
4. 消息和任务双驱动模式
5. 全生命周期管控

核心理念：从单智能体"驾驭与治理"到多智能体协调

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
import asyncio
import time
import os


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"        # 待认领
    CLAIMED = "claimed"        # 已认领
    IN_PROGRESS = "in_progress" # 进行中
    COMPLETED = "completed"    # 已完成
    VERIFIED = "verified"      # 已验证
    CLOSED = "closed"          # 已关闭
    BLOCKED = "blocked"        # 阻塞


class AgentRole(Enum):
    """Agent角色"""
    LEADER = "leader"      # 协调者
    TEAMMATE = "teammate"  # 执行者


class MessageType(Enum):
    """消息类型"""
    TASK_CLAIM = "task_claim"
    TASK_UPDATE = "task_update"
    TASK_COMPLETE = "task_complete"
    TASK_BLOCKED = "task_blocked"
    MESSAGE = "message"
    REQUEST_HELP = "request_help"
    APPROVAL_REQUEST = "approval_request"


@dataclass
class Task:
    """
    任务
    
    支持有向无环图（DAG）依赖关系。
    """
    task_id: str
    title: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    assignee: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    priority: int = 1  # 1-5，5最高
    created_at: float = field(default_factory=lambda: time.time())
    updated_at: float = field(default_factory=lambda: time.time())
    execution_plan: Optional[str] = None
    result: Optional[str] = None


@dataclass
class Message:
    """
    消息
    
    用于团队成员之间的通信。
    """
    message_id: str
    sender_id: str
    receiver_id: str
    type: MessageType
    content: str
    task_id: Optional[str] = None
    timestamp: float = field(default_factory=lambda: time.time())
    is_read: bool = False


@dataclass
class TeamMember:
    """
    团队成员
    
    代表一个Agent成员。
    """
    agent_id: str
    name: str
    role: AgentRole
    status: str = "idle"  # idle, busy, offline
    skills: List[str] = field(default_factory=list)
    current_task: Optional[str] = None


class AgentTeam:
    """
    Agent团队协同层
    
    核心功能：
    1. Leader + Teammate 架构
    2. 共享任务列表（支持DAG依赖）
    3. Team Workspace（团队共享工作区）
    4. 消息和任务双驱动模式
    5. 全生命周期管控
    
    团队编排流程：
    1. Leader分析需求，拆解任务
    2. Teammate主动认领任务
    3. Teammate执行任务
    4. Leader验证结果
    5. 任务完成/关闭
    """
    
    def __init__(self, team_id: str):
        self._logger = logger.bind(component=f"AgentTeam_{team_id}")
        
        # 团队信息
        self._team_id = team_id
        self._members: Dict[str, TeamMember] = {}
        
        # 共享任务列表
        self._tasks: Dict[str, Task] = {}
        
        # 消息队列
        self._messages: List[Message] = []
        
        # Team Workspace
        self._workspace_dir = f".team/{team_id}/artifacts"
        self._init_workspace()
        
        # 审批模式
        self._plan_approval_required = True
        self._tool_approval_required = True
        
        # 事件订阅
        self._event_listeners: List[Callable] = []
        
        self._logger.info(f"✅ AgentTeam '{team_id}' 初始化完成")
    
    def _init_workspace(self):
        """初始化团队工作区"""
        os.makedirs(os.path.join(self._workspace_dir, "data"), exist_ok=True)
        os.makedirs(os.path.join(self._workspace_dir, "docs"), exist_ok=True)
        os.makedirs(os.path.join(self._workspace_dir, "reports"), exist_ok=True)
    
    def add_member(self, agent_id: str, name: str, role: AgentRole, skills: List[str] = None):
        """
        添加团队成员
        
        Args:
            agent_id: Agent ID
            name: Agent名称
            role: 角色（Leader/Teammate）
            skills: 技能列表
        """
        member = TeamMember(
            agent_id=agent_id,
            name=name,
            role=role,
            skills=skills or []
        )
        
        self._members[agent_id] = member
        self._logger.info(f"👤 添加成员: {name} ({role.value})")
    
    def remove_member(self, agent_id: str):
        """
        移除团队成员
        
        Args:
            agent_id: Agent ID
        """
        if agent_id in self._members:
            del self._members[agent_id]
            self._logger.info(f"👤 移除成员: {agent_id}")
    
    def get_members(self) -> List[TeamMember]:
        """获取团队成员列表"""
        return list(self._members.values())
    
    def get_member(self, agent_id: str) -> Optional[TeamMember]:
        """获取单个成员"""
        return self._members.get(agent_id)
    
    def add_task(self, title: str, description: str, dependencies: List[str] = None, priority: int = 1) -> str:
        """
        添加任务
        
        Args:
            title: 任务标题
            description: 任务描述
            dependencies: 依赖任务ID列表
            priority: 优先级（1-5）
            
        Returns:
            任务ID
        """
        task_id = f"task_{int(time.time())}"
        task = Task(
            task_id=task_id,
            title=title,
            description=description,
            dependencies=dependencies or [],
            priority=priority
        )
        
        self._tasks[task_id] = task
        self._logger.info(f"📋 添加任务: {title}")
        
        # 触发任务添加事件
        self._trigger_event("task_added", task)
        
        return task_id
    
    def get_tasks(self, status: TaskStatus = None) -> List[Task]:
        """
        获取任务列表
        
        Args:
            status: 任务状态过滤（可选）
            
        Returns:
            任务列表
        """
        tasks = list(self._tasks.values())
        
        if status:
            tasks = [t for t in tasks if t.status == status]
        
        # 按优先级排序
        tasks.sort(key=lambda t: (-t.priority, t.created_at))
        
        return tasks
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取单个任务"""
        return self._tasks.get(task_id)
    
    def update_task(self, task_id: str, **kwargs):
        """
        更新任务
        
        Args:
            task_id: 任务ID
            **kwargs: 更新字段
        """
        task = self._tasks.get(task_id)
        if task:
            for key, value in kwargs.items():
                if hasattr(task, key):
                    setattr(task, key, value)
            task.updated_at = time.time()
            
            # 触发任务更新事件
            self._trigger_event("task_updated", task)
    
    def claim_task(self, agent_id: str, task_id: str) -> bool:
        """
        认领任务
        
        Args:
            agent_id: Agent ID
            task_id: 任务ID
            
        Returns:
            是否认领成功
        """
        task = self._tasks.get(task_id)
        
        if not task:
            return False
        
        if task.status != TaskStatus.PENDING:
            return False
        
        # 检查依赖是否满足
        for dep_id in task.dependencies:
            dep_task = self._tasks.get(dep_id)
            if dep_task and dep_task.status != TaskStatus.COMPLETED:
                return False
        
        # 更新任务状态
        task.status = TaskStatus.CLAIMED
        task.assignee = agent_id
        task.updated_at = time.time()
        
        # 更新成员状态
        member = self._members.get(agent_id)
        if member:
            member.status = "busy"
            member.current_task = task_id
        
        self._logger.info(f"👤 {agent_id} 认领任务: {task.title}")
        
        # 触发事件
        self._trigger_event("task_claimed", task)
        
        return True
    
    def complete_task(self, agent_id: str, task_id: str, result: str = "") -> bool:
        """
        完成任务
        
        Args:
            agent_id: Agent ID
            task_id: 任务ID
            result: 任务结果
            
        Returns:
            是否完成成功
        """
        task = self._tasks.get(task_id)
        
        if not task:
            return False
        
        if task.assignee != agent_id:
            return False
        
        task.status = TaskStatus.COMPLETED
        task.result = result
        task.updated_at = time.time()
        
        # 更新成员状态
        member = self._members.get(agent_id)
        if member:
            member.status = "idle"
            member.current_task = None
        
        self._logger.info(f"✅ {agent_id} 完成任务: {task.title}")
        
        # 触发事件
        self._trigger_event("task_completed", task)
        
        return True
    
    def send_message(self, sender_id: str, receiver_id: str, type: MessageType, content: str, task_id: Optional[str] = None):
        """
        发送消息
        
        Args:
            sender_id: 发送者ID
            receiver_id: 接收者ID
            type: 消息类型
            content: 消息内容
            task_id: 关联任务ID（可选）
        """
        message = Message(
            message_id=f"msg_{int(time.time())}",
            sender_id=sender_id,
            receiver_id=receiver_id,
            type=type,
            content=content,
            task_id=task_id
        )
        
        self._messages.append(message)
        
        # 触发消息事件
        self._trigger_event("message_received", message)
        
        self._logger.debug(f"💬 消息: {sender_id} -> {receiver_id} [{type.value}]")
    
    def get_messages(self, receiver_id: str = None) -> List[Message]:
        """
        获取消息
        
        Args:
            receiver_id: 接收者ID过滤（可选）
            
        Returns:
            消息列表
        """
        messages = self._messages
        
        if receiver_id:
            messages = [m for m in messages if m.receiver_id == receiver_id]
        
        return messages
    
    def mark_message_read(self, message_id: str):
        """标记消息为已读"""
        for msg in self._messages:
            if msg.message_id == message_id:
                msg.is_read = True
                break
    
    def _trigger_event(self, event_type: str, data: Any):
        """触发事件"""
        for listener in self._event_listeners:
            try:
                listener(event_type, data)
            except Exception as e:
                self._logger.error(f"❌ 事件监听执行失败: {e}")
    
    def add_event_listener(self, listener: Callable):
        """添加事件监听器"""
        self._event_listeners.append(listener)
    
    def get_workspace_path(self, subdir: str = "") -> str:
        """
        获取工作区路径
        
        Args:
            subdir: 子目录（data/docs/reports）
            
        Returns:
            工作区路径
        """
        if subdir:
            return os.path.join(self._workspace_dir, subdir)
        return self._workspace_dir
    
    def write_workspace_file(self, path: str, content: str):
        """
        写入工作区文件
        
        Args:
            path: 文件路径（相对路径）
            content: 文件内容
        """
        full_path = os.path.join(self._workspace_dir, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        self._logger.debug(f"📝 写入文件: {path}")
    
    def read_workspace_file(self, path: str) -> Optional[str]:
        """
        读取工作区文件
        
        Args:
            path: 文件路径（相对路径）
            
        Returns:
            文件内容（如果存在）
        """
        full_path = os.path.join(self._workspace_dir, path)
        
        if os.path.exists(full_path):
            with open(full_path, 'r', encoding='utf-8') as f:
                return f.read()
        
        return None
    
    def get_team_info(self) -> Dict[str, Any]:
        """获取团队信息"""
        tasks = self.get_tasks()
        stats = {
            "total": len(tasks),
            "pending": len([t for t in tasks if t.status == TaskStatus.PENDING]),
            "in_progress": len([t for t in tasks if t.status == TaskStatus.IN_PROGRESS]),
            "completed": len([t for t in tasks if t.status == TaskStatus.COMPLETED]),
        }
        
        return {
            "team_id": self._team_id,
            "member_count": len(self._members),
            "task_stats": stats,
            "workspace_dir": self._workspace_dir
        }


# 创建全局实例
agent_team = AgentTeam("default_team")


def get_agent_team(team_id: str = "default_team") -> AgentTeam:
    """获取Agent团队实例"""
    global agent_team
    if team_id != "default_team":
        return AgentTeam(team_id)
    return agent_team


# 测试函数
async def test_agent_team():
    """测试Agent团队协同层"""
    import sys
    logger.remove()
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)
    
    print("=" * 60)
    print("测试 AgentTeam")
    print("=" * 60)
    
    # 1. 创建团队
    print("\n[1] 创建团队...")
    team = AgentTeam("test_team")
    print(f"    ✓ 团队ID: {team._team_id}")
    
    # 2. 添加成员
    print("\n[2] 添加成员...")
    team.add_member("leader_agent", "领导者", AgentRole.LEADER, ["规划", "协调"])
    team.add_member("teammate_1", "执行者1", AgentRole.TEAMMATE, ["编程", "分析"])
    team.add_member("teammate_2", "执行者2", AgentRole.TEAMMATE, ["写作", "报告"])
    members = team.get_members()
    print(f"    ✓ 成员数量: {len(members)}")
    for m in members:
        print(f"      - {m.name} ({m.role.value})")
    
    # 3. 添加任务
    print("\n[3] 添加任务...")
    task_id1 = team.add_task("分析需求", "分析用户需求文档", priority=5)
    task_id2 = team.add_task("设计方案", "设计技术方案", dependencies=[task_id1], priority=4)
    task_id3 = team.add_task("编写报告", "编写最终报告", dependencies=[task_id2], priority=3)
    tasks = team.get_tasks()
    print(f"    ✓ 任务数量: {len(tasks)}")
    for t in tasks:
        print(f"      - {t.title} (状态: {t.status.value}, 优先级: {t.priority})")
    
    # 4. 认领任务
    print("\n[4] 认领任务...")
    success = team.claim_task("teammate_1", task_id1)
    print(f"    ✓ 认领成功: {success}")
    task = team.get_task(task_id1)
    print(f"    ✓ 任务状态: {task.status.value}")
    
    # 5. 完成任务
    print("\n[5] 完成任务...")
    success = team.complete_task("teammate_1", task_id1, "需求分析完成")
    print(f"    ✓ 完成成功: {success}")
    task = team.get_task(task_id1)
    print(f"    ✓ 任务状态: {task.status.value}")
    
    # 6. 发送消息
    print("\n[6] 发送消息...")
    team.send_message("teammate_1", "leader_agent", MessageType.TASK_COMPLETE, "任务1已完成")
    messages = team.get_messages("leader_agent")
    print(f"    ✓ 消息数量: {len(messages)}")
    
    # 7. Team Workspace
    print("\n[7] Team Workspace...")
    team.write_workspace_file("reports/analysis.md", "# 分析报告\n\n内容...")
    content = team.read_workspace_file("reports/analysis.md")
    print(f"    ✓ 文件内容长度: {len(content)}")
    
    # 8. 获取团队信息
    print("\n[8] 获取团队信息...")
    info = team.get_team_info()
    print(f"    ✓ 团队ID: {info['team_id']}")
    print(f"    ✓ 成员数: {info['member_count']}")
    print(f"    ✓ 任务统计: {info['task_stats']}")
    
    print("\n" + "=" * 60)
    print("🎉 所有测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_agent_team())