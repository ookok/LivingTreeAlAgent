"""
虚拟会议系统

实现虚拟会议角色系统，支持多种场景（评审会、法庭、课堂等）
"""

import asyncio
import json
import uuid
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod


class RoleType(Enum):
    """角色类型"""
    # 会议角色
    CHAIRMAN = "chairman"           # 主持人/会议主席
    EXPERT = "expert"               # 专家
    GOVERNMENT = "government"        # 政府代表
    ENTERPRISE = "enterprise"       # 企业代表
    EMPLOYEE = "employee"           # 员工代表
    RECORDER = "recorder"          # 记录员
    OBSERVER = "observer"           # 观察员
    
    # 法庭角色
    JUDGE = "judge"                 # 法官
    PROSECUTOR = "prosecutor"      # 检察官
    DEFENDER = "defender"          # 辩护律师
    JURY = "jury"                  # 陪审团
    WITNESS = "witness"            # 证人
    
    # 课堂角色
    TEACHER = "teacher"            # 教师
    STUDENT = "student"            # 学生
    ASSISTANT = "assistant"        # 助教


class ScenarioType(Enum):
    """场景类型"""
    REVIEW_MEETING = "review_meeting"    # 评审会
    GOVERNMENT_MEETING = "government_meeting"  # 政府会议
    COURTROOM = "courtroom"            # 虚拟法庭
    CLASSROOM = "classroom"           # 虚拟课堂
    NEGOTIATION = "negotiation"        # 商务谈判
    PRESS_CONFERENCE = "press_conference"  # 新闻发布会


@dataclass
class RoleProfile:
    """角色配置"""
    name: str
    title: str  # 职务/头衔
    role_type: RoleType
    voice: str  # 语音配置
    personality: Dict[str, Any] = field(default_factory=dict)  # 性格特征
    expertise: List[str] = field(default_factory=list)  # 专业领域
    speaking_style: str = "formal"  # 说话风格: formal, casual, technical, persuasive


@dataclass
class VirtualParticipant:
    """虚拟参与者"""
    id: str
    name: str
    role: RoleProfile
    avatar: Optional[str] = None
    audio_enabled: bool = True
    video_enabled: bool = False
    is_speaking: bool = False
    is_muted: bool = False
    is_deafened: bool = False
    audio_level: float = 0.0
    agent_id: Optional[str] = None
    is_digital_twin: bool = False
    twin_id: Optional[str] = None
    voice_profile: Optional[Any] = None  # 关联的 Agent ID


@dataclass
class MeetingTopic:
    """会议议题"""
    id: str
    title: str
    description: str
    presenter_id: Optional[str] = None
    duration: int = 300  # 默认 5 分钟
    status: str = "pending"  # pending, active, completed
    materials: List[str] = field(default_factory=list)  # 相关材料


@dataclass
class MeetingRecord:
    """会议记录"""
    meeting_id: str
    start_time: float
    end_time: Optional[float] = None
    transcript: List[Dict[str, Any]] = field(default_factory=list)
    participants: List[str] = field(default_factory=list)
    topics: List[MeetingTopic] = field(default_factory=list)
    summary: str = ""


class VirtualAgent:
    """虚拟 Agent"""
    
    def __init__(
        self,
        participant: VirtualParticipant,
        llm_handler: Callable
    ):
        self.participant = participant
        self.llm_handler = llm_handler
        self.conversation_history: List[Dict[str, str]] = []
        self.context: Dict[str, Any] = {}
    
    async def think(self, prompt: str) -> str:
        """
        思考并生成回复
        
        Args:
            prompt: 输入提示
            
        Returns:
            str: 生成的回复
        """
        # 构建角色提示
        role_prompt = self._build_role_prompt(prompt)
        
        # 调用 LLM
        response = await self.llm_handler(role_prompt)
        
        # 记录对话历史
        self.conversation_history.append({
            "role": "user",
            "content": prompt
        })
        self.conversation_history.append({
            "role": "assistant",
            "content": response
        })
        
        return response
    
    def _build_role_prompt(self, prompt: str) -> str:
        """构建角色提示"""
        role = self.participant.role
        
        role_prompt = f"""你扮演 {role.name}，{role.title}。

角色特征：
- 专业领域：{', '.join(role.expertise)}
- 说话风格：{role.speaking_style}
- 性格特点：{json.dumps(role.personality, ensure_ascii=False)}

请以 {role.name} 的身份和说话风格回答以下问题或发表意见。

{prompt}

请用符合角色身份的方式回答。
"""
        return role_prompt
    
    def set_context(self, key: str, value: Any):
        """设置上下文"""
        self.context[key] = value
    
    def get_context(self, key: str) -> Any:
        """获取上下文"""
        return self.context.get(key)


class VirtualConferenceSystem:
    """虚拟会议系统 - 集成共享工作空间"""

    def __init__(self, scenario: ScenarioType = ScenarioType.REVIEW_MEETING):
        self.scenario = scenario
        self.participants: Dict[str, VirtualParticipant] = {}
        self.agents: Dict[str, VirtualAgent] = {}
        self.topics: List[MeetingTopic] = []
        self.current_topic_index: int = 0
        self.meeting_record: Optional[MeetingRecord] = None
        self.is_recording: bool = False
        self.is_active: bool = False

        # 共享工作空间
        from core.living_tree_ai.agency_integration.shared_workspace import SharedWorkspace
        self.workspace = SharedWorkspace(workspace_id=f"conference_{uuid.uuid4()}")
        self.workspace_name = f"conference_{uuid.uuid4()}"

        # 回调函数
        self.on_message: Optional[Callable] = None
        self.on_participant_update: Optional[Callable] = None
        self.on_topic_change: Optional[Callable] = None

        # 注册工作空间事件
        self._setup_workspace_events()

    def _setup_workspace_events(self):
        """设置工作空间事件处理"""
        async def on_agent_registered(data):
            print(f"[Conference] Agent 注册: {data.get('agent_name')}")

        async def on_context_updated(data):
            key = data.get("key")
            owner = data.get("owner_id")
            print(f"[Conference] 上下文更新: {key} by {owner}")

        async def on_message_sent(data):
            msg_type = data.get("msg_type")
            sender = data.get("sender_name")
            content = data.get("content")
            print(f"[Conference] 消息: {sender} - {msg_type}")

        self.workspace.message_bus.subscribe("agent_registered", on_agent_registered)
        self.workspace.message_bus.subscribe("context_updated", on_context_updated)
        self.workspace.message_bus.subscribe("message_sent", on_message_sent)

    def add_participant(
        self,
        name: str,
        role: RoleProfile,
        is_ai_controlled: bool = False,
        llm_handler: Optional[Callable] = None
    ) -> str:
        """
        添加参与者

        Args:
            name: 名称
            role: 角色配置
            is_ai_controlled: 是否由 AI 控制
            llm_handler: LLM 处理函数

        Returns:
            str: 参与者 ID
        """
        participant_id = str(uuid.uuid4())

        participant = VirtualParticipant(
            id=participant_id,
            name=name,
            role=role
        )

        self.participants[participant_id] = participant

        if is_ai_controlled and llm_handler:
            agent = VirtualAgent(participant, llm_handler)
            self.agents[participant_id] = agent
            participant.agent_id = participant_id

        self.workspace.register_agent(
            agent_id=participant_id,
            agent_name=name,
            role=role.role_type.value,
            capabilities=role.expertise
        )

        return participant_id

    def add_digital_twin(
        self,
        twin_id: str,
        name: str,
        role: RoleProfile,
        voice_profile: Optional[Any] = None,
        llm_handler: Optional[Callable] = None
    ) -> str:
        """
        添加数字分身参与者

        Args:
            twin_id: 数字分身 ID
            name: 名称
            role: 角色配置
            voice_profile: 语音配置
            llm_handler: LLM 处理函数

        Returns:
            str: 参与者 ID
        """
        participant_id = str(uuid.uuid4())

        participant = VirtualParticipant(
            id=participant_id,
            name=name,
            role=role,
            is_digital_twin=True,
            twin_id=twin_id,
            voice_profile=voice_profile
        )

        self.participants[participant_id] = participant

        if llm_handler:
            agent = VirtualAgent(participant, llm_handler)
            self.agents[participant_id] = agent
            participant.agent_id = participant_id

        self.workspace.register_agent(
            agent_id=participant_id,
            agent_name=name,
            role=role.role_type.value,
            capabilities=["数字分身"] + role.expertise
        )

        print(f"[Conference] 添加数字分身: {name} (twin_id: {twin_id})")
        return participant_id

    def remove_participant(self, participant_id: str):
        """移除参与者"""
        if participant_id in self.participants:
            del self.participants[participant_id]
        if participant_id in self.agents:
            del self.agents[participant_id]
    
    def set_participant_mute(self, participant_id: str, muted: bool):
        """设置参与者静音状态"""
        if participant_id in self.participants:
            self.participants[participant_id].is_muted = muted
            self._notify_participant_update(participant_id)
    
    def set_participant_deafen(self, participant_id: str, deafened: bool):
        """设置参与者关闭声音状态"""
        if participant_id in self.participants:
            self.participants[participant_id].is_deafened = deafened
            self._notify_participant_update(participant_id)
    
    def add_topic(self, topic: MeetingTopic) -> str:
        """添加议题"""
        topic.id = str(uuid.uuid4())
        self.topics.append(topic)
        return topic.id
    
    def set_current_topic(self, topic_index: int):
        """设置当前议题"""
        if 0 <= topic_index < len(self.topics):
            self.current_topic_index = topic_index
            self.topics[topic_index].status = "active"
            self._notify_topic_change(topic_index)
    
    async def start_meeting(self, title: str, description: str = ""):
        """开始会议"""
        self.is_active = True
        self.meeting_record = MeetingRecord(
            meeting_id=str(uuid.uuid4()),
            start_time=time.time(),
            participants=list(self.participants.keys()),
            topics=self.topics.copy()
        )
        
        await self._notify_message({
            "type": "meeting_started",
            "title": title,
            "description": description,
            "participants": [p.name for p in self.participants.values()]
        })
    
    async def end_meeting(self):
        """结束会议"""
        self.is_active = False
        
        if self.meeting_record:
            self.meeting_record.end_time = time.time()
        
        await self._notify_message({
            "type": "meeting_ended",
            "duration": time.time() - self.meeting_record.start_time if self.meeting_record else 0
        })
    
    async def ai_participant_speak(
        self,
        participant_id: str,
        prompt: str
    ) -> str:
        """
        AI 参与者发言
        
        Args:
            participant_id: 参与者 ID
            prompt: 发言提示
            
        Returns:
            str: 生成的发言内容
        """
        if participant_id not in self.agents:
            return ""
        
        agent = self.agents[participant_id]
        
        # 标记为正在发言
        self.participants[participant_id].is_speaking = True
        self._notify_participant_update(participant_id)
        
        try:
            # AI 生成回复
            response = await agent.think(prompt)
            
            # 记录到会议记录
            if self.meeting_record:
                self.meeting_record.transcript.append({
                    "timestamp": time.time(),
                    "participant_id": participant_id,
                    "participant_name": self.participants[participant_id].name,
                    "content": response,
                    "type": "speech"
                })
            
            # 通知消息
            await self._notify_message({
                "type": "speech",
                "participant_id": participant_id,
                "participant_name": self.participants[participant_id].name,
                "content": response
            })
            
            return response
            
        finally:
            # 标记为停止发言
            self.participants[participant_id].is_speaking = False
            self._notify_participant_update(participant_id)
    
    async def human_participant_speak(
        self,
        participant_id: str,
        content: str
    ):
        """
        人类参与者发言
        
        Args:
            participant_id: 参与者 ID
            content: 发言内容
        """
        # 记录到会议记录
        if self.meeting_record:
            self.meeting_record.transcript.append({
                "timestamp": time.time(),
                "participant_id": participant_id,
                "participant_name": self.participants[participant_id].name,
                "content": content,
                "type": "speech"
            })
        
        # 通知消息
        await self._notify_message({
            "type": "speech",
            "participant_id": participant_id,
            "participant_name": self.participants[participant_id].name,
            "content": content
        })
    
    def get_meeting_summary(self) -> str:
        """获取会议摘要"""
        if not self.meeting_record:
            return ""
        
        summary = f"会议参与人数: {len(self.meeting_record.participants)}\n"
        summary += f"议题数量: {len(self.meeting_record.topics)}\n"
        summary += f"发言次数: {len(self.meeting_record.transcript)}\n"
        
        return summary
    
    def _notify_participant_update(self, participant_id: str):
        """通知参与者更新"""
        if self.on_participant_update:
            self.on_participant_update(
                participant_id,
                self.participants[participant_id]
            )
    
    def _notify_topic_change(self, topic_index: int):
        """通知议题变更"""
        if self.on_topic_change:
            self.on_topic_change(topic_index, self.topics[topic_index])
    
    async def _notify_message(self, message: Dict[str, Any]):
        """通知消息"""
        if self.on_message:
            await self.on_message(message)


class ReviewMeetingScenario:
    """评审会场景"""
    
    # 预设角色模板
    ROLE_TEMPLATES = {
        "chairman": RoleProfile(
            name="会议主持人",
            title="会议主持人",
            role_type=RoleType.CHAIRMAN,
            voice="zh-CN-XiaoxiaoNeural",
            expertise=["会议主持", "流程控制"],
            speaking_style="formal"
        ),
        "expert1": RoleProfile(
            name="李明",
            title="技术专家",
            role_type=RoleType.EXPERT,
            voice="zh-CN-YunxiNeural",
            expertise=["人工智能", "软件工程"],
            personality={"性格": "严谨", "特点": "善于提问"},
            speaking_style="technical"
        ),
        "expert2": RoleProfile(
            name="王芳",
            title="财务专家",
            role_type=RoleType.EXPERT,
            voice="zh-CN-XiaoxiaoNeural",
            expertise=["财务管理", "成本控制"],
            personality={"性格": "务实", "特点": "注重细节"},
            speaking_style="formal"
        ),
        "government": RoleProfile(
            name="张处长",
            title="发改委处长",
            role_type=RoleType.GOVERNMENT,
            voice="zh-CN-YunyangNeural",
            expertise=["政策制定", "项目管理"],
            personality={"性格": "稳重", "特点": "关注合规性"},
            speaking_style="formal"
        ),
        "enterprise": RoleProfile(
            name="陈总",
            title="企业代表",
            role_type=RoleType.ENTERPRISE,
            voice="zh-CN-YunxiNeural",
            expertise=["企业管理", "市场运营"],
            personality={"性格": "积极", "特点": "善于表达"},
            speaking_style="persuasive"
        ),
        "employee": RoleProfile(
            name="刘经理",
            title="员工代表",
            role_type=RoleType.EMPLOYEE,
            voice="zh-CN-XiaoyiNeural",
            expertise=["一线业务", "实际操作"],
            personality={"性格": "务实", "特点": "了解实际需求"},
            speaking_style="casual"
        ),
        "recorder": RoleProfile(
            name="记录员",
            title="会议记录员",
            role_type=RoleType.RECORDER,
            voice="zh-CN-XiaoxiaoNeural",
            expertise=["文档管理", "文字记录"],
            speaking_style="formal"
        )
    }
    
    @classmethod
    def create_review_meeting(
        cls,
        llm_handler: Callable,
        include_roles: List[str] = None
    ) -> VirtualConferenceSystem:
        """
        创建评审会
        
        Args:
            llm_handler: LLM 处理函数
            include_roles: 要包含的角色列表
            
        Returns:
            VirtualConferenceSystem: 虚拟会议系统实例
        """
        system = VirtualConferenceSystem(ScenarioType.REVIEW_MEETING)
        
        if include_roles is None:
            include_roles = ["chairman", "expert1", "expert2", "government", "enterprise", "employee"]
        
        for role_key in include_roles:
            if role_key in cls.ROLE_TEMPLATES:
                role = cls.ROLE_TEMPLATES[role_key]
                system.add_participant(
                    name=role.name,
                    role=role,
                    is_ai_controlled=True,
                    llm_handler=llm_handler
                )
        
        # 添加议题
        system.add_topic(MeetingTopic(
            title="项目概述",
            description="介绍项目背景、目标和主要工作内容",
            duration=300
        ))
        
        system.add_topic(MeetingTopic(
            title="技术方案评审",
            description="评审技术方案的可行性和创新性",
            duration=600
        ))
        
        system.add_topic(MeetingTopic(
            title="财务预算审议",
            description="审议项目预算和资金使用计划",
            duration=450
        ))
        
        system.add_topic(MeetingTopic(
            title="风险评估",
            description="评估项目风险及应对措施",
            duration=300
        ))
        
        system.add_topic(MeetingTopic(
            title="专家质询",
            description="专家就项目相关问题进行质询",
            duration=600
        ))
        
        system.add_topic(MeetingTopic(
            title="总结与表决",
            description="形成评审结论和建议",
            duration=300
        ))
        
        return system


class CourtroomScenario:
    """虚拟法庭场景"""
    
    @classmethod
    def create_courtroom(
        cls,
        llm_handler: Callable
    ) -> VirtualConferenceSystem:
        """创建虚拟法庭"""
        system = VirtualConferenceSystem(ScenarioType.COURTROOM)
        
        # 法官
        system.add_participant(
            name="审判长",
            role=RoleProfile(
                name="审判长",
                title="审判长",
                role_type=RoleType.JUDGE,
                voice="zh-CN-YunyangNeural",
                expertise=["法律", "审判"],
                speaking_style="formal"
            ),
            is_ai_controlled=True,
            llm_handler=llm_handler
        )
        
        # 检察官
        system.add_participant(
            name="公诉人",
            role=RoleProfile(
                name="公诉人",
                title="检察官",
                role_type=RoleType.PROSECUTOR,
                voice="zh-CN-XiaoxiaoNeural",
                expertise=["刑事诉讼", "证据分析"],
                speaking_style="formal"
            ),
            is_ai_controlled=True,
            llm_handler=llm_handler
        )
        
        # 辩护律师
        system.add_participant(
            name="辩护律师",
            role=RoleProfile(
                name="辩护律师",
                title="辩护律师",
                role_type=RoleType.DEFENDER,
                voice="zh-CN-YunxiNeural",
                expertise=["刑事辩护", "法律咨询"],
                speaking_style="persuasive"
            ),
            is_ai_controlled=True,
            llm_handler=llm_handler
        )
        
        # 添加议题
        system.add_topic(MeetingTopic(
            title="开庭",
            description="宣布开庭，核对当事人身份",
            duration=180
        ))
        
        system.add_topic(MeetingTopic(
            title="法庭调查",
            description="公诉人宣读起诉书",
            duration=300
        ))
        
        system.add_topic(MeetingTopic(
            title="举证质证",
            description="控辩双方举证、质证",
            duration=600
        ))
        
        system.add_topic(MeetingTopic(
            title="法庭辩论",
            description="控辩双方进行辩论",
            duration=900
        ))
        
        system.add_topic(MeetingTopic(
            title="最后陈述",
            description="被告人进行最后陈述",
            duration=300
        ))
        
        return system


class ClassroomScenario:
    """虚拟课堂场景"""
    
    @classmethod
    def create_classroom(
        cls,
        llm_handler: Callable,
        student_count: int = 5
    ) -> VirtualConferenceSystem:
        """创建虚拟课堂"""
        system = VirtualConferenceSystem(ScenarioType.CLASSROOM)
        
        # 教师
        system.add_participant(
            name="王教授",
            role=RoleProfile(
                name="王教授",
                title="教授",
                role_type=RoleType.TEACHER,
                voice="zh-CN-YunyangNeural",
                expertise=["人工智能", "机器学习"],
                speaking_style="educational"
            ),
            is_ai_controlled=True,
            llm_handler=llm_handler
        )
        
        # 学生
        student_names = ["张三", "李四", "王五", "赵六", "钱七"]
        for i in range(min(student_count, len(student_names))):
            system.add_participant(
                name=student_names[i],
                role=RoleProfile(
                    name=student_names[i],
                    title="学生",
                    role_type=RoleType.STUDENT,
                    voice="zh-CN-XiaoyiNeural" if i % 2 == 0 else "zh-CN-YunxiNeural",
                    expertise=["学习"],
                    speaking_style="curious"
                ),
                is_ai_controlled=True,
                llm_handler=llm_handler
            )
        
        return system


# 全局实例
_conference_system: Optional[VirtualConferenceSystem] = None


def get_conference_system() -> VirtualConferenceSystem:
    """获取虚拟会议系统实例"""
    global _conference_system
    if _conference_system is None:
        _conference_system = VirtualConferenceSystem()
    return _conference_system
