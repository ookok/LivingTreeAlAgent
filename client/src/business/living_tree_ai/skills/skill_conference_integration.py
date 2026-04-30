"""
技能系统与虚拟会议集成

实现技能在虚拟会议中的使用和管理
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
import uuid

from client.src.business.living_tree_ai.skills.skill_manager import (
    SkillManager, SkillExecutor, get_skill_manager, get_skill_executor
)
from client.src.business.living_tree_ai.voice.virtual_conference import VirtualConferenceSystem


@dataclass
class SkillInvocation:
    """技能调用"""
    invocation_id: str
    skill_instance_id: str
    participant_id: str
    input_data: Dict[str, Any]
    status: str
    result: Optional[Dict[str, Any]] = None
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None


class SkillConferenceIntegration:
    """技能系统与虚拟会议集成"""

    def __init__(self):
        self.skill_manager = get_skill_manager()
        self.skill_executor = get_skill_executor()
        self.invocations: Dict[str, SkillInvocation] = {}
        self.conference_skills: Dict[str, List[str]] = {}  # conference_id -> [skill_instance_id]

    def register_skill_for_conference(self, conference_id: str, skill_instance_id: str) -> bool:
        """
        为会议注册技能

        Args:
            conference_id: 会议 ID
            skill_instance_id: 技能实例 ID

        Returns:
            bool: 是否成功
        """
        skill = self.skill_manager.get_skill(skill_instance_id)
        if not skill or not skill.enabled:
            return False

        if conference_id not in self.conference_skills:
            self.conference_skills[conference_id] = []

        if skill_instance_id not in self.conference_skills[conference_id]:
            self.conference_skills[conference_id].append(skill_instance_id)

        return True

    def unregister_skill_from_conference(self, conference_id: str, skill_instance_id: str) -> bool:
        """
        从会议中移除技能

        Args:
            conference_id: 会议 ID
            skill_instance_id: 技能实例 ID

        Returns:
            bool: 是否成功
        """
        if conference_id not in self.conference_skills:
            return False

        if skill_instance_id in self.conference_skills[conference_id]:
            self.conference_skills[conference_id].remove(skill_instance_id)
            return True

        return False

    def get_conference_skills(self, conference_id: str) -> List[Dict]:
        """
        获取会议的技能列表

        Args:
            conference_id: 会议 ID

        Returns:
            List[Dict]: 技能列表
        """
        skills = []
        if conference_id not in self.conference_skills:
            return skills

        for skill_instance_id in self.conference_skills[conference_id]:
            skill = self.skill_manager.get_skill(skill_instance_id)
            if skill:
                skills.append({
                    "instance_id": skill.instance_id,
                    "name": skill.manifest.name,
                    "version": skill.manifest.version,
                    "description": skill.manifest.description,
                    "platform": skill.manifest.platform.value,
                    "enabled": skill.enabled
                })

        return skills

    async def invoke_skill(
        self,
        conference_id: str,
        skill_instance_id: str,
        participant_id: str,
        input_data: Dict[str, Any]
    ) -> SkillInvocation:
        """
        调用技能

        Args:
            conference_id: 会议 ID
            skill_instance_id: 技能实例 ID
            participant_id: 参与者 ID
            input_data: 输入数据

        Returns:
            SkillInvocation: 技能调用
        """
        # 检查技能是否在会议中注册
        if conference_id not in self.conference_skills or skill_instance_id not in self.conference_skills[conference_id]:
            invocation = SkillInvocation(
                invocation_id=str(uuid.uuid4()),
                skill_instance_id=skill_instance_id,
                participant_id=participant_id,
                input_data=input_data,
                status="error"
            )
            invocation.result = {"error": "Skill not registered for this conference"}
            invocation.completed_at = time.time()
            self.invocations[invocation.invocation_id] = invocation
            return invocation

        # 创建调用记录
        invocation = SkillInvocation(
            invocation_id=str(uuid.uuid4()),
            skill_instance_id=skill_instance_id,
            participant_id=participant_id,
            input_data=input_data,
            status="running"
        )

        self.invocations[invocation.invocation_id] = invocation

        # 执行技能
        try:
            result = self.skill_executor.execute_skill(skill_instance_id, input_data)
            invocation.result = result
            invocation.status = "completed"
        except Exception as e:
            invocation.result = {"error": str(e)}
            invocation.status = "error"
        finally:
            invocation.completed_at = time.time()

        return invocation

    def get_invocation_status(self, invocation_id: str) -> Optional[SkillInvocation]:
        """
        获取调用状态

        Args:
            invocation_id: 调用 ID

        Returns:
            Optional[SkillInvocation]: 调用信息
        """
        return self.invocations.get(invocation_id)

    def get_participant_invocations(self, participant_id: str) -> List[SkillInvocation]:
        """
        获取参与者的调用记录

        Args:
            participant_id: 参与者 ID

        Returns:
            List[SkillInvocation]: 调用记录
        """
        return [
            inv for inv in self.invocations.values()
            if inv.participant_id == participant_id
        ]

    def get_conference_invocations(self, conference_id: str) -> List[SkillInvocation]:
        """
        获取会议的调用记录

        Args:
            conference_id: 会议 ID

        Returns:
            List[SkillInvocation]: 调用记录
        """
        if conference_id not in self.conference_skills:
            return []

        conference_skill_ids = set(self.conference_skills[conference_id])
        return [
            inv for inv in self.invocations.values()
            if inv.skill_instance_id in conference_skill_ids
        ]


class ConferenceSkillManager:
    """会议技能管理器"""

    def __init__(self, conference: VirtualConferenceSystem):
        self.conference = conference
        self.integration = SkillConferenceIntegration()
        self.conference_id = str(uuid.uuid4())

    def add_skill(self, skill_instance_id: str) -> bool:
        """
        添加技能到会议

        Args:
            skill_instance_id: 技能实例 ID

        Returns:
            bool: 是否成功
        """
        return self.integration.register_skill_for_conference(self.conference_id, skill_instance_id)

    def remove_skill(self, skill_instance_id: str) -> bool:
        """
        从会议中移除技能

        Args:
            skill_instance_id: 技能实例 ID

        Returns:
            bool: 是否成功
        """
        return self.integration.unregister_skill_from_conference(self.conference_id, skill_instance_id)

    def get_skills(self) -> List[Dict]:
        """
        获取会议技能列表

        Returns:
            List[Dict]: 技能列表
        """
        return self.integration.get_conference_skills(self.conference_id)

    async def use_skill(
        self,
        skill_instance_id: str,
        participant_id: str,
        input_data: Dict[str, Any]
    ) -> SkillInvocation:
        """
        在会议中使用技能

        Args:
            skill_instance_id: 技能实例 ID
            participant_id: 参与者 ID
            input_data: 输入数据

        Returns:
            SkillInvocation: 技能调用
        """
        invocation = await self.integration.invoke_skill(
            self.conference_id,
            skill_instance_id,
            participant_id,
            input_data
        )

        # 向会议发送技能执行结果
        if invocation.status == "completed" and invocation.result:
            participant = self.conference.participants.get(participant_id)
            if participant:
                skill = self.integration.skill_manager.get_skill(skill_instance_id)
                if skill:
                    message = f"技能执行结果 ({skill.manifest.name}): {json.dumps(invocation.result, ensure_ascii=False)}"
                    self.conference.send_message(
                        participant_id=participant_id,
                        message=message
                    )

        return invocation

    def get_skill_history(self) -> List[SkillInvocation]:
        """
        获取技能使用历史

        Returns:
            List[SkillInvocation]: 调用记录
        """
        return self.integration.get_conference_invocations(self.conference_id)


class SkillCommandHandler:
    """技能命令处理器"""

    def __init__(self, conference_skill_manager: ConferenceSkillManager):
        self.manager = conference_skill_manager

    def handle_command(self, command: str, participant_id: str) -> Optional[str]:
        """
        处理技能命令

        Args:
            command: 命令字符串
            participant_id: 参与者 ID

        Returns:
            Optional[str]: 命令响应
        """
        parts = command.strip().split(' ', 1)
        if len(parts) < 1:
            return "技能命令格式: /skill <技能名称> <参数>"

        cmd = parts[0].lower()

        if cmd == "/skill":
            return self._handle_skill_command(parts[1] if len(parts) > 1 else "", participant_id)
        elif cmd == "/skills":
            return self._handle_skills_command()
        elif cmd == "/skillhelp":
            return self._handle_skill_help()

        return None

    def _handle_skill_command(self, args: str, participant_id: str) -> str:
        """处理技能调用命令"""
        if not args:
            return "请指定技能名称和参数"

        skill_args = args.split(' ', 1)
        if len(skill_args) < 1:
            return "请指定技能名称"

        skill_name = skill_args[0]
        skill_args = skill_args[1] if len(skill_args) > 1 else ""

        # 查找技能
        skills = self.manager.integration.skill_manager.get_all_skills()
        target_skill = None
        for skill in skills:
            if skill.manifest.name.lower() == skill_name.lower():
                target_skill = skill
                break

        if not target_skill:
            return f"技能 {skill_name} 不存在"

        # 检查技能是否在会议中注册
        conference_skills = self.manager.get_skills()
        registered = any(s["instance_id"] == target_skill.instance_id for s in conference_skills)

        if not registered:
            # 自动注册
            self.manager.add_skill(target_skill.instance_id)

        # 执行技能
        input_data = {
            "args": skill_args,
            "participant_id": participant_id,
            "conference_id": self.manager.conference_id
        }

        asyncio.create_task(self.manager.use_skill(
            target_skill.instance_id,
            participant_id,
            input_data
        ))

        return f"正在执行技能 {target_skill.manifest.name}..."

    def _handle_skills_command(self) -> str:
        """处理技能列表命令"""
        skills = self.manager.get_skills()
        if not skills:
            return "当前会议中没有注册的技能"

        response = "当前会议中的技能:\n"
        for skill in skills:
            status = "启用" if skill["enabled"] else "禁用"
            response += f"- {skill['name']} v{skill['version']} ({status}) - {skill['description'][:50]}...\n"

        return response

    def _handle_skill_help(self) -> str:
        """处理技能帮助命令"""
        return """
技能命令帮助:
/skill <技能名称> <参数> - 执行指定技能
/skills - 查看当前会议中的技能
/skillhelp - 查看技能命令帮助

示例:
/skill web_search 人工智能最新进展
/skill code_generator 生成 Python 排序算法
        """


class SkillAgent:
    """技能代理"""

    def __init__(self, conference: VirtualConferenceSystem):
        self.conference = conference
        self.skill_manager = ConferenceSkillManager(conference)
        self.command_handler = SkillCommandHandler(self.skill_manager)

    def process_message(self, participant_id: str, message: str) -> Optional[str]:
        """
        处理消息

        Args:
            participant_id: 参与者 ID
            message: 消息内容

        Returns:
            Optional[str]: 响应
        """
        if message.startswith('/'):
            return self.command_handler.handle_command(message, participant_id)
        return None

    def add_skill(self, skill_instance_id: str) -> bool:
        """
        添加技能

        Args:
            skill_instance_id: 技能实例 ID

        Returns:
            bool: 是否成功
        """
        return self.skill_manager.add_skill(skill_instance_id)

    def get_skills(self) -> List[Dict]:
        """
        获取技能列表

        Returns:
            List[Dict]: 技能列表
        """
        return self.skill_manager.get_skills()

    async def use_skill(
        self,
        skill_instance_id: str,
        participant_id: str,
        input_data: Dict[str, Any]
    ) -> SkillInvocation:
        """
        使用技能

        Args:
            skill_instance_id: 技能实例 ID
            participant_id: 参与者 ID
            input_data: 输入数据

        Returns:
            SkillInvocation: 技能调用
        """
        return await self.skill_manager.use_skill(skill_instance_id, participant_id, input_data)


# 全局实例
_global_integration: Optional[SkillConferenceIntegration] = None


def get_skill_conference_integration() -> SkillConferenceIntegration:
    """获取技能会议集成"""
    global _global_integration
    if _global_integration is None:
        _global_integration = SkillConferenceIntegration()
    return _global_integration


def create_skill_agent(conference: VirtualConferenceSystem) -> SkillAgent:
    """创建技能代理"""
    return SkillAgent(conference)


# 示例使用
async def demo_skill_integration():
    """演示技能集成"""
    from client.src.business.living_tree_ai.voice.virtual_conference import VirtualConferenceSystem

    # 创建会议
    conference = VirtualConferenceSystem()

    # 创建技能代理
    skill_agent = create_skill_agent(conference)

    # 添加技能
    manager = get_skill_manager()
    skill = manager.create_skill(
        name="Test Skill",
        description="A test skill",
        author="User"
    )

    if skill:
        skill_agent.add_skill(skill.instance_id)
        print(f"添加技能: {skill.manifest.name}")

        # 处理命令
        response = skill_agent.process_message("user1", "/skills")
        print(f"命令响应: {response}")

        # 使用技能
        invocation = await skill_agent.use_skill(
            skill.instance_id,
            "user1",
            {"test": "data"}
        )
        print(f"技能执行结果: {invocation.result}")


if __name__ == "__main__":
    asyncio.run(demo_skill_integration())
