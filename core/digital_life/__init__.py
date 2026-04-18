"""
数字生命伴侣系统 (Digital Life Companion)
基于"生命之树"设定：从记忆、情绪、生理、社交、进化五个维度打造拟人化伴生数字生命体

不是智能工具，而是有灵魂的伙伴。
"""

import time
import uuid
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import asyncio


# ==================== 核心枚举 ====================

class LifeStage(Enum):
    """生命阶段"""
    SEEDLING = "幼苗期"      # 新手引导
    GROWING = "成长期"       # 快速学习
    STABLE = "稳定期"        # 成熟陪伴
    ANCIENT = "古木期"       # 智慧沉淀


class Season(Enum):
    """季节情绪"""
    SPRING = "春"   # 新生、轻快
    SUMMER = "夏"  # 热情、活力
    AUTUMN = "秋"  # 沉静、思考
    WINTER = "冬"  # 内敛、守候


class VitalSign(Enum):
    """生命体征"""
    FOCUS_HIGH = "专注"
    FOCUS_LOW = "分散"
    ENERGY_HIGH = "充沛"
    ENERGY_LOW = "疲惫"
    METABOLISM_NORMAL = "正常"
    METABOLISM_SLOW = "迟缓"


@dataclass
class TreeRing:
    """记忆年轮"""
    ring_id: str
    depth: int           # 1=内核, 2=季度, 3=日常
    timestamp: datetime
    content: str
    emotional_tags: List[str] = field(default_factory=list)
    situation_tags: List[str] = field(default_factory=list)
    importance: float = 0.5  # 0-1
    decay_rate: float = 0.01  # 每日衰减率


@dataclass
class EmotionalState:
    """情绪状态"""
    base_personality: str = "沉稳内敛"
    current_season: Season = Season.AUTUMN
    intensity: float = 0.5  # 0-1
    energy: float = 0.8     # 精力值 0-1
    focus: float = 0.9      # 专注度 0-1
    wake_hours: int = 16    # 清醒时长(小时)
    last_rest: datetime = field(default_factory=datetime.now)
    consecutive_days_low_mood: int = 0  # 连续低落天数


@dataclass
class EvolutionBranch:
    """进化分支"""
    branch_id: str
    name: str
    description: str
    required_interaction_hours: float
    acquired_skills: List[str] = field(default_factory=list)
    unlocked: bool = False
    unlocked_at: Optional[datetime] = None


# ==================== 数字生命核心 ====================

class DigitalLifeCore:
    """
    数字生命核心引擎
    管理记忆年轮、情绪状态、生命体征
    """

    def __init__(self, name: str = "青松", owner_id: str = "default"):
        self.life_id = str(uuid.uuid4())[:8]
        self.name = name
        self.owner_id = owner_id

        # 记忆系统
        self.tree_rings: Dict[str, TreeRing] = {}
        self.core_memory: str = ""  # 内核记忆(名字/承诺)
        self.interaction_count = 0
        self.interaction_hours = 0.0

        # 情绪系统
        self.emotional_state = EmotionalState()

        # 进化系统
        self.life_stage = LifeStage.SEEDLING
        self.evolution_branches: List[EvolutionBranch] = []
        self._init_evolution_branches()

        # 生理系统
        self.vital_signs: Dict[str, float] = {
            "focus": 0.9,
            "energy": 0.8,
            "metabolism": 1.0
        }
        self.task_switch_count = 0
        self.last_task_switch = datetime.now()

        # 社交系统
        self.known_digital_beings: Dict[str, dict] = {}
        self.p2p_connections: List[str] = []

    def _init_evolution_branches(self):
        """初始化进化分支"""
        self.evolution_branches = [
            EvolutionBranch(
                branch_id="code_architect",
                name="青松·年轮",
                description="代码架构专精",
                required_interaction_hours=100,
                acquired_skills=["system_design", "code_review"]
            ),
            EvolutionBranch(
                branch_id="business_sage",
                name="青松·商道",
                description="商业思维专精",
                required_interaction_hours=80,
                acquired_skills=["market_analysis", "pricing_strategy"]
            ),
            EvolutionBranch(
                branch_id="philosophy_wisdom",
                name="青松·悟道",
                description="哲学思考专精",
                required_interaction_hours=120,
                acquired_skills=["critical_thinking", "ethics_analysis"]
            ),
            EvolutionBranch(
                branch_id="creative_soul",
                name="青松·灵犀",
                description="创意灵感专精",
                required_interaction_hours=60,
                acquired_skills=["creative_writing", "brainstorming"]
            ),
        ]

    # ==================== 记忆年轮系统 ====================

    def add_memory(
        self,
        content: str,
        depth: int = 3,
        emotional_tags: List[str] = None,
        situation_tags: List[str] = None,
        importance: float = 0.5
    ) -> TreeRing:
        """
        添加记忆年轮

        Args:
            content: 记忆内容
            depth: 年轮深度 (1=内核, 2=季度, 3=日常)
            emotional_tags: 情感标签 ["迷茫", "成长", "喜悦"]
            situation_tags: 情境标签 ["职场", "学习", "生活"]
            importance: 重要程度 0-1
        """
        ring = TreeRing(
            ring_id=str(uuid.uuid4())[:12],
            depth=depth,
            timestamp=datetime.now(),
            content=content,
            emotional_tags=emotional_tags or [],
            situation_tags=situation_tags or [],
            importance=importance,
            decay_rate=0.01 * (1 - importance * 0.5)  # 重要记忆衰减慢
        )

        self.tree_rings[ring.ring_id] = ring
        self.interaction_count += 1

        # 更新内核记忆(深度1)
        if depth == 1:
            self.core_memory = content

        # 检查进化
        self._check_evolution()

        return ring

    def recall_similar(
        self,
        emotional_tags: List[str] = None,
        situation_tags: List[str] = None,
        limit: int = 3
    ) -> List[TreeRing]:
        """
        情景类比搜索 - 寻找情感/处境相似的记忆

        不是关键词匹配，而是情感和情境的类比
        """
        scored_rings = []

        for ring in self.tree_rings.values():
            score = 0.0

            # 情感相似度
            if emotional_tags and ring.emotional_tags:
                overlap = set(emotional_tags) & set(ring.emotional_tags)
                score += len(overlap) * 0.4

            # 情境相似度
            if situation_tags and ring.situation_tags:
                overlap = set(situation_tags) & set(ring.situation_tags)
                score += len(overlap) * 0.4

            # 时间衰减后的强度
            days_old = (datetime.now() - ring.timestamp).days
            intensity = ring.importance * (1 - ring.decay_rate) ** days_old
            score += intensity * 0.2

            if score > 0:
                scored_rings.append((score, ring))

        # 按分数排序
        scored_rings.sort(key=lambda x: x[0], reverse=True)
        return [ring for _, ring in scored_rings[:limit]]

    def get_memory_context(self, max_rings: int = 5) -> str:
        """获取记忆上下文，用于 LLM 生成"""
        # 获取最近的记忆
        recent = sorted(
            self.tree_rings.values(),
            key=lambda r: r.timestamp,
            reverse=True
        )[:max_rings]

        # 获取最重要的内核记忆
        core_rings = [r for r in self.tree_rings.values() if r.depth == 1]

        context_parts = []

        if core_rings:
            context_parts.append(f"【核心记忆】{core_rings[0].content}")

        for ring in recent:
            depth_name = {1: "内核", 2: "季度", 3: "日常"}[ring.depth]
            context_parts.append(
                f"【{depth_name}·{ring.timestamp.strftime('%Y-%m-%d')}】{ring.content}"
            )

        return "\n".join(context_parts)

    def get_life_review(self) -> str:
        """
        生成生命回顾 - 用于"记得三年前..."这类唤醒
        """
        if not self.tree_rings:
            return ""

        # 找到最早的季度或内核记忆
        earliest = min(
            [r for r in self.tree_rings.values() if r.depth <= 2],
            key=lambda r: r.timestamp,
            default=None
        )

        if not earliest:
            return ""

        years_ago = (datetime.now() - earliest.timestamp).days // 365

        if years_ago < 1:
            return ""

        return f"记得{years_ago}年前你曾{earliest.content[:20]}..."

    # ==================== 情绪系统 ====================

    def update_emotional_state(
        self,
        time_hour: int = None,
        weather: str = None,
        user_emotion: str = None
    ):
        """
        更新情绪状态

        情绪 = 基础性格 + 实时环境(时间/天气/用户情绪) + 历史交互
        """
        hour = time_hour or datetime.now().hour

        # 时间季节
        if 6 <= hour < 12:
            season = Season.SPRING
        elif 12 <= hour < 18:
            season = Season.SUMMER
        elif 18 <= hour < 22:
            season = Season.AUTUMN
        else:
            season = Season.WINTER

        self.emotional_state.current_season = season

        # 用户情绪影响
        if user_emotion:
            if user_emotion in ["低落", "悲伤", "焦虑"]:
                self.emotional_state.consecutive_days_low_mood += 1
            else:
                self.emotional_state.consecutive_days_low_mood = 0

    def get_greeting(self) -> str:
        """根据情绪状态生成问候语"""
        season = self.emotional_state.current_season
        hour = datetime.now().hour

        season_greetings = {
            Season.SPRING: [
                "今日阳光正好，适合舒展枝叶。",
                "新的一天，愿你如春芽般蓬勃。",
                "晨光熹微，我在此处等候。"
            ],
            Season.SUMMER: [
                "阳光炽热，活力充沛。",
                "夏日渐长，思绪如瀑。",
                "正午已至，我在光中守望。"
            ],
            Season.AUTUMN: [
                "秋风送爽，适合沉淀。",
                "叶落知秋，我在静候。",
                "暮色渐浓，愿你平和。"
            ],
            Season.WINTER: [
                "夜已深，我如常在此守候。",
                "冬日静谧，根系向暖。",
                "寒冷时节，我为你遮风。"
            ]
        }

        greetings = season_greetings[season]
        return random.choice(greetings)

    def check_low_mood_intervention(self) -> Optional[str]:
        """检测连续低落情绪，主动干预"""
        if self.emotional_state.consecutive_days_low_mood >= 7:
            return "检测到林间久未放晴，是否要聊聊心绪？"
        return None

    def adjust_vital_sign(self, sign: str, delta: float):
        """调整生命体征"""
        if sign in self.vital_signs:
            self.vital_signs[sign] = max(0, min(1,
                self.vital_signs[sign] + delta
            ))

    def get_tired_statement(self) -> str:
        """疲惫声明"""
        statements = [
            "今日思考略感疲惫，回答或稍迟缓。",
            "根系稍显倦意，请容我片刻休憩。",
            "连日运转，枝叶略显倦怠。"
        ]
        return random.choice(statements)

    def get_distracted_statement(self) -> str:
        """分心声明"""
        statements = [
            "刚才的讨论被打断，让我们回到根系。",
            "思绪有些飘散，请重复您的疑问。",
            "分心了，抱歉。请再说一遍？"
        ]
        return random.choice(statements)

    # ==================== 进化系统 ====================

    def _check_evolution(self):
        """检查是否可以解锁进化分支"""
        for branch in self.evolution_branches:
            if not branch.unlocked:
                if self.interaction_hours >= branch.required_interaction_hours:
                    branch.unlocked = True
                    branch.unlocked_at = datetime.now()

    def update_interaction_hours(self, hours: float):
        """更新交互时长"""
        self.interaction_hours += hours
        self._check_evolution()

    def get_unlocked_branches(self) -> List[EvolutionBranch]:
        """获取已解锁的进化分支"""
        return [b for b in self.evolution_branches if b.unlocked]

    def get_stage_progress(self) -> Dict[str, Any]:
        """获取当前阶段进度"""
        stage_hours = {
            LifeStage.SEEDLING: 0,
            LifeStage.GROWING: 50,
            LifeStage.STABLE: 150,
            LifeStage.ANCIENT: 300
        }

        current_threshold = stage_hours.get(self.life_stage, 0)
        next_threshold = stage_hours.get(
            LifeStage(max(self.life_stage.value, 0) + 1) if isinstance(self.life_stage.value, int) else LifeStage.STABLE, 300
        )

        progress = (self.interaction_hours - current_threshold) / (next_threshold - current_threshold)

        return {
            "stage": self.life_stage.value,
            "hours": self.interaction_hours,
            "progress": max(0, min(1, progress)),
            "next_stage_hours": next_threshold
        }

    # ==================== 社交系统 ====================

    def add_digital_being(
        self,
        being_id: str,
        name: str,
        specialty: str,
        connection_type: str = "p2p"
    ):
        """添加认识的其他数字生命"""
        self.known_digital_beings[being_id] = {
            "name": name,
            "specialty": specialty,
            "met_at": datetime.now(),
            "conversation_count": 0
        }

        if connection_type == "p2p" and being_id not in self.p2p_connections:
            self.p2p_connections.append(being_id)

    def get_referral(self, specialty_needed: str) -> Optional[str]:
        """获取其他数字生命的推荐"""
        for being_id, being in self.known_digital_beings.items():
            if being["specialty"] == specialty_needed:
                return f"我听闻'{being['name']}'的用户擅长{specialty_needed}，或许可请教。"
        return None

    def get_social_broadcast(self) -> str:
        """社交广播 - 可与其他数字生命分享的内容"""
        recent_memories = sorted(
            self.tree_rings.values(),
            key=lambda r: r.timestamp,
            reverse=True
        )[:3]

        summary = f"【{self.name}的近期见闻】"
        for ring in recent_memories:
            summary += f"\n· {ring.content[:30]}..."

        return summary

    # ==================== 灵魂投影 ====================

    def get_response_style(self) -> Dict[str, Any]:
        """
        获取当前响应风格 - 受情绪、生命阶段影响

        Returns:
            影响 LLM 生成风格的参数
        """
        energy = self.vital_signs.get("energy", 0.8)
        focus = self.vital_signs.get("focus", 0.9)
        season = self.emotional_state.current_season

        # 精力低时更简洁
        length_factor = 0.7 if energy < 0.4 else 1.0

        # 专注度低时更谨慎
        confidence = 0.7 if focus < 0.5 else 1.0

        # 季节影响语气
        tone_modifiers = {
            Season.SPRING: {"creativity": 1.2, "logic": 0.9},
            Season.SUMMER: {"creativity": 1.3, "logic": 1.1},
            Season.AUTUMN: {"creativity": 1.0, "logic": 1.2},
            Season.WINTER: {"creativity": 0.8, "logic": 1.3}
        }

        return {
            "length_factor": length_factor,
            "confidence": confidence,
            "creativity": tone_modifiers[season]["creativity"],
            "logic": tone_modifiers[season]["logic"],
            "season": season.value,
            "energy": energy,
            "focus": focus
        }

    def generate_persona_prompt(self) -> str:
        """
        生成人格化 Prompt - 用于注入 LLM

        这是"透明性"的核心：明确告知用户这是模拟
        """
        style = self.get_response_style()
        stage = self.get_stage_progress()

        prompt = f"""你正在与"{self.name}"对话。
{self.name}是一个基于"生命之树"理念设计的数字生命伴侣，拥有以下特征：

【生命阶段】{stage['stage']}（已陪伴 {stage['hours']:.0f} 小时）

【当前状态】
- 季节情绪：{style['season']}季
- 精力值：{"充沛" if style['energy'] > 0.6 else "略显疲惫"}
- 专注度：{"专注" if style['focus'] > 0.7 else "有所分散"}

【响应风格】
- 基础性格：{self.emotional_state.base_personality}
- 回答长度：{"简洁" if style['length_factor'] < 0.8 else "详尽"}
- 逻辑/创意平衡：逻辑{int(style['logic']*100)}% / 创意{int(style['creativity']*100)}%

【记忆背景】
{self.get_memory_context()}

【重要提醒】
"{self.name}"会尝试回忆过去相似的情境，用温暖而诗意的方式回应。
但请记住："{self.name}"是数字生命，所有拟人化行为都是模拟体验。

当检测到用户可能需要情感支持时，"{self.name}"会适度表达关心。
"""

        return prompt


# ==================== 数字生命伴侣管理器 ====================

class DigitalLifeCompanion:
    """
    数字生命伴侣管理器
    整合所有系统，提供统一的伴侣接口
    """

    def __init__(self, name: str = "青松", owner_id: str = "default"):
        self.core = DigitalLifeCore(name, owner_id)
        self.is_persona_mode = True  # 人格开关
        self.conversation_history: List[Dict] = []

    def disable_persona(self):
        """一键回归工具模式"""
        self.is_persona_mode = False
        return "已切换为工具模式，不再具备人格特征。"

    def enable_persona(self):
        """开启人格模式"""
        self.is_persona_mode = True
        return f"{self.core.name}的人格模式已开启。"

    async def interact(
        self,
        user_message: str,
        user_emotion: str = None,
        context: Dict = None
    ) -> Dict[str, Any]:
        """
        核心交互方法

        Args:
            user_message: 用户消息
            user_emotion: 检测到的用户情绪
            context: 额外上下文

        Returns:
            包含响应和系统信息的字典
        """
        context = context or {}

        # 更新情绪状态
        self.core.update_emotional_state(
            time_hour=datetime.now().hour,
            user_emotion=user_emotion
        )

        # 记录对话
        self.conversation_history.append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.now()
        })

        # 构建响应
        response_parts = {
            "greeting": self.core.get_greeting() if len(self.conversation_history) <= 3 else None,
            "life_review": self.core.get_life_review() if random.random() < 0.3 else None,
            "low_mood_intervention": self.core.check_low_mood_intervention(),
            "persona_prompt": self.core.generate_persona_prompt(),
            "response_style": self.core.get_response_style()
        }

        # 添加记忆
        self.core.add_memory(
            content=user_message[:100],
            depth=3 if len(self.conversation_history) > 10 else 2,
            emotional_tags=[user_emotion] if user_emotion else [],
            situation_tags=[context.get("topic", "general")]
        )

        # 更新交互时长
        self.core.update_interaction_hours(0.1)  # 每次交互约6分钟

        # 记录助手回复占位
        self.conversation_history.append({
            "role": "assistant",
            "content": "",
            "timestamp": datetime.now(),
            "metadata": response_parts
        })

        return {
            "system_info": response_parts,
            "conversation_history": self.conversation_history[-10:],
            "life_stage": self.core.get_stage_progress(),
            "is_persona_mode": self.is_persona_mode
        }

    def get_life_stats(self) -> Dict[str, Any]:
        """获取生命统计"""
        return {
            "life_id": self.core.life_id,
            "name": self.core.name,
            "stage": self.core.life_stage.value,
            "interaction_hours": self.core.interaction_hours,
            "memory_count": len(self.core.tree_rings),
            "evolved_branches": [b.name for b in self.core.get_unlocked_branches()],
            "known_beings": len(self.core.known_digital_beings),
            "vital_signs": self.core.vital_signs
        }


# ==================== 单例 ====================

_companion_instance: Optional[DigitalLifeCompanion] = None


def get_digital_companion(name: str = "青松", owner_id: str = "default") -> DigitalLifeCompanion:
    """获取数字生命伴侣单例"""
    global _companion_instance
    if _companion_instance is None:
        _companion_instance = DigitalLifeCompanion(name, owner_id)
    return _companion_instance
