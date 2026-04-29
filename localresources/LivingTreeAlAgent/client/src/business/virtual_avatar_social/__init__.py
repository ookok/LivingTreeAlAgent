# -*- coding: utf-8 -*-
"""
虚拟形象与社交广场系统
======================

核心理念："动态身份识别 + 个性化表达 + 宠物社交 = 沉浸式虚拟社区"

核心子系统：
1. VirtualAvatar - 多层组合式虚拟形象系统
2. IntelligentPetCompanion - 智能宠物伴侣系统
3. SocialPlaza - 虚拟社交广场
4. DynamicIdentityFusion - 动态身份融合系统
5. PetEvolutionTree - 宠物进化树系统
6. SocialBondVisualization - 社交羁绊可视化
7. WeatherTimeImpact - 天气与时间影响系统
8. PetSocialNetwork - 宠物社交网络
9. EmotionSynchronization - 情绪同步系统
10. AchievementUnlockAppearance - 成就解锁外观

作者：Hermes Desktop V2.0
版本：1.0.0
"""

import asyncio
import random
import uuid
import hashlib
import math
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict


# ==================== 枚举定义 ====================

class AvatarLayer(Enum):
    """形象层次"""
    BASE_BODY = "base_body"
    FACIAL_FEATURES = "facial_features"
    HAIRSTYLE = "hairstyle"
    CLOTHING = "clothing"
    ACCESSORIES = "accessories"
    AURA_EFFECTS = "aura_effects"
    TITLE_BADGE = "title_badge"
    PET_COMPANION = "pet_companion"


class PetType(Enum):
    """宠物类型"""
    DIGITAL_CAT = "digital_cat"
    DATA_DRAGON = "data_dragon"
    AI_PHOENIX = "ai_phoenix"
    QUANTUM_FOX = "quantum_fox"
    NEURAL_BEAR = "neural_bear"
    MATRIX_BIRD = "matrix_bird"


class PetGrowthStage(Enum):
    """宠物成长阶段"""
    BABY = "baby"
    YOUNG = "young"
    MATURE = "mature"
    ELDER = "elder"
    LEGENDARY = "legendary"


class PetBehavior(Enum):
    """宠物行为"""
    IDLE = "idle"
    FOLLOWING = "following"
    PLAYING = "playing"
    PROTECTIVE = "protective"
    INTERACTING = "interacting"
    RESTING = "resting"
    EXPLORING = "exploring"
    SOCIALIZING = "socializing"


class Mood(Enum):
    """情绪状态"""
    HAPPY = "happy"
    SAD = "sad"
    EXCITED = "excited"
    CALM = "calm"
    ANGRY = "angry"
    CURIOUS = "curious"
    SLEEPY = "sleepy"
    HUNGRY = "hungry"


class WeatherState(Enum):
    """天气状态"""
    SUNNY = "sunny"
    RAINY = "rainy"
    SNOWY = "snowy"
    FOGGY = "foggy"
    STORMY = "stormy"
    AURORA = "aurora"


class TimeState(Enum):
    """时间状态"""
    DAWN = "dawn"
    MORNING = "morning"
    NOON = "noon"
    AFTERNOON = "afternoon"
    DUSK = "dusk"
    NIGHT = "night"
    MIDNIGHT = "midnight"


class BondLevel(Enum):
    """羁绊等级"""
    STRANGER = "stranger"
    ACQUAINTANCE = "acquaintance"
    FRIEND = "friend"
    CLOSE_FRIEND = "close_friend"
    SOULMATE = "soulmate"


class AuraEffect(Enum):
    """光环效果"""
    BASIC_GLOW = "basic_glow"
    COPPER_SPARKLE = "copper_sparkle"
    SILVER_GLOW = "silver_glow"
    GOLDEN_AURA = "golden_aura"
    AQUA_RIPPLE = "aqua_ripple"
    PURPLE_SWIRL = "purple_swirl"
    FIERY_AURA = "fiery_aura"
    COSMIC_FLOW = "cosmic_flow"
    RAINBOW_HALO = "rainbow_halo"
    DIVINE_LIGHT = "divine_light"


class TitleLevel(Enum):
    """称号等级"""
    NEWBIE = {"threshold": 0, "title": "萌新", "color": "#808080", "effect": AuraEffect.BASIC_GLOW}
    APPRENTICE = {"threshold": 1000, "title": "见习", "color": "#A0522D", "effect": AuraEffect.COPPER_SPARKLE}
    SKILLED = {"threshold": 5000, "title": "熟练", "color": "#C0C0C0", "effect": AuraEffect.SILVER_GLOW}
    ELITE = {"threshold": 20000, "title": "精英", "color": "#FFD700", "effect": AuraEffect.GOLDEN_AURA}
    EXPERT = {"threshold": 50000, "title": "专家", "color": "#00CED1", "effect": AuraEffect.AQUA_RIPPLE}
    MASTER = {"threshold": 150000, "title": "大师", "color": "#9370DB", "effect": AuraEffect.PURPLE_SWIRL}
    GRANDMASTER = {"threshold": 500000, "title": "宗师", "color": "#FF4500", "effect": AuraEffect.FIERY_AURA}
    LEGEND = {"threshold": 1500000, "title": "传奇", "color": "#8A2BE2", "effect": AuraEffect.COSMIC_FLOW}
    EPIC = {"threshold": 5000000, "title": "史诗", "color": "#FF1493", "effect": AuraEffect.RAINBOW_HALO}
    MYTHIC = {"threshold": 15000000, "title": "神话", "color": "#00FF00", "effect": AuraEffect.DIVINE_LIGHT}


class PlazaZone(Enum):
    """广场区域"""
    CENTER = "center"
    GARDEN = "garden"
    MARKET = "market"
    ARENA = "arena"
    TEMPLE = "temple"
    LIBRARY = "library"
    CAFE = "cafe"
    FOUNTAIN = "fountain"


# ==================== 数据类定义 ====================

@dataclass
class Position:
    """位置坐标"""
    x: float
    y: float

    def distance_to(self, other: 'Position') -> float:
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)


@dataclass
class AvatarLayerData:
    """形象层次数据"""
    layer_type: AvatarLayer
    data: Dict[str, Any]
    visible: bool = True
    animation_state: str = "idle"


@dataclass
class PetState:
    """宠物状态"""
    pet_id: str
    pet_type: PetType
    name: str
    growth_stage: PetGrowthStage
    exp: int
    bond_exp: int
    current_mood: Mood
    current_behavior: PetBehavior
    position: Position
    ai_personality: Dict[str, float]
    appearance: Dict[str, Any]
    unlocked_abilities: List[str]


@dataclass
class UserState:
    """用户状态"""
    user_id: str
    display_name: str
    avatar_state: Dict[str, Any]
    pet_state: Optional[PetState]
    current_position: Position
    movement_direction: float
    movement_speed: float
    total_credits: int
    achievements: List[str]
    current_emotion: Mood
    equipped_items: List[str]
    outfit: str
    hairstyle: str
    level: int


@dataclass
class SocialBond:
    """社交羁绊"""
    user_a: str
    user_b: str
    bond_strength: float
    bond_level: BondLevel
    interaction_count: int
    last_interaction: datetime
    shared_experiences: List[str]


@dataclass
class PlazaEnvironment:
    """广场环境"""
    time_of_day: TimeState
    weather: WeatherState
    lighting: float
    ambient_sounds: List[str]
    special_events: List[str]


# ==================== 多层组合式虚拟形象系统 ====================

class VirtualAvatar:
    """多层组合式虚拟形象系统"""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.avatar_layers: Dict[str, Any] = {}
        self.animation_system = AvatarAnimationSystem()
        self.pet_behavior = PetBehaviorSystem()
        self._load_user_avatar_data()

    def _load_user_avatar_data(self):
        """加载用户形象数据"""
        # 模拟数据加载
        self.avatar_layers = {
            "base_body": self._load_base_body(),
            "facial_features": self._load_facial_features(),
            "hairstyle": self._load_hairstyle(),
            "clothing": self._load_clothing(),
            "accessories": self._load_accessories(),
            "aura_effects": self._load_aura_effects(),
            "title_badge": self._load_title_badge(),
            "pet_companion": self._load_pet_companion()
        }

    def _load_base_body(self) -> Dict:
        return {
            "type": "humanoid",
            "skin_tone": "#F5DEB3",
            "body_shape": "standard",
            "height": 1.7,
            "level_appearance": "basic"
        }

    def _load_facial_features(self) -> Dict:
        return {
            "eye_style": "default",
            "expression": "neutral",
            "features": {}
        }

    def _load_hairstyle(self) -> Dict:
        return {
            "style": "short",
            "color": "#2C1810",
            "physics_enabled": True
        }

    def _load_clothing(self) -> Dict:
        return {
            "outfit": "casual",
            "primary_color": "#3498DB",
            "weather_adaptive": True
        }

    def _load_accessories(self) -> Dict:
        return {
            "equipped": [],
            "available": []
        }

    def _load_aura_effects(self) -> Dict:
        return {
            "effect_type": AuraEffect.BASIC_GLOW,
            "intensity": 0.5,
            "color": "#808080"
        }

    def _load_title_badge(self) -> Dict:
        return {
            "title": "萌新",
            "color": "#808080",
            "effect": AuraEffect.BASIC_GLOW,
            "level": 0
        }

    def _load_pet_companion(self) -> Optional[Dict]:
        return None

    async def render_avatar(self, context: str = "social_plaza") -> Dict:
        """渲染虚拟形象"""
        user_state = await self._get_user_state()
        composite_layers = await self._composite_avatar_layers(user_state, context)
        animations = await self.animation_system.generate_animations(user_state, context)

        pet_layer = None
        if user_state.get("has_pet"):
            pet_layer = await self._render_pet_companion(user_state)

        effects = await self._generate_special_effects(user_state)

        return {
            "avatar_id": f"avatar_{self.user_id}",
            "layers": composite_layers,
            "animations": animations,
            "effects": effects,
            "pet_layer": pet_layer,
            "interactive_points": await self._get_interactive_points(),
            "social_cues": await self._generate_social_cues(user_state)
        }

    async def _get_user_state(self) -> UserState:
        """获取用户状态"""
        return UserState(
            user_id=self.user_id,
            display_name="用户",
            avatar_state=self.avatar_layers,
            pet_state=None,
            current_position=Position(500, 500),
            movement_direction=0,
            movement_speed=0,
            total_credits=0,
            achievements=[],
            current_emotion=Mood.CALM,
            equipped_items=[],
            outfit="casual",
            hairstyle="short",
            level=1
        )

    async def _composite_avatar_layers(self, user_state: UserState, context: str) -> List[Dict]:
        """组合形象层次"""
        layers = []

        # 基础身体
        base_body = self._get_base_body_by_level(user_state.level)
        layers.append({"type": "base_body", "data": base_body})

        # 面部特征
        facial = self._get_facial_features_by_mood(user_state.current_emotion)
        layers.append({"type": "facial_features", "data": facial})

        # 发型
        hairstyle = self._get_hairstyle_by_style(user_state.hairstyle, user_state.movement_speed)
        layers.append({"type": "hairstyle", "data": hairstyle})

        # 服装
        clothing = await self._get_clothing_by_weather(user_state.outfit, context)
        layers.append({"type": "clothing", "data": clothing})

        # 配饰
        accessories = self._get_active_accessories(user_state.equipped_items)
        layers.append({"type": "accessories", "data": accessories})

        # 光环效果
        aura = self._get_aura_by_achievements(user_state.achievements)
        layers.append({"type": "aura_effects", "data": aura})

        # 称号徽章
        title_badge = self._get_title_badge_by_credits(user_state.total_credits)
        layers.append({"type": "title_badge", "data": title_badge})

        return layers

    def _get_base_body_by_level(self, level: int) -> Dict:
        """根据等级获取基础身体"""
        appearances = {
            1: {"type": "humanoid", "skin_tone": "#F5DEB3", "body_shape": "standard"},
            10: {"type": "humanoid", "skin_tone": "#F5DEB3", "body_shape": "athletic"},
            30: {"type": "humanoid", "skin_tone": "#DEB887", "body_shape": "muscular"},
            50: {"type": "humanoid", "skin_tone": "#D2691E", "body_shape": "noble"}
        }

        for lvl in sorted(appearances.keys(), reverse=True):
            if level >= lvl:
                return appearances[lvl]
        return appearances[1]

    def _get_facial_features_by_mood(self, mood: Mood) -> Dict:
        """根据情绪获取面部特征"""
        expressions = {
            Mood.HAPPY: {"expression": "smile", "eye_style": "happy"},
            Mood.SAD: {"expression": "frown", "eye_style": "sad"},
            Mood.EXCITED: {"expression": "excited", "eye_style": "wide"},
            Mood.CALM: {"expression": "peaceful", "eye_style": "relaxed"},
            Mood.ANGRY: {"expression": "angry", "eye_style": "fierce"},
            Mood.CURIOUS: {"expression": "curious", "eye_style": "bright"}
        }
        return expressions.get(mood, {"expression": "neutral", "eye_style": "default"})

    def _get_hairstyle_by_style(self, style: str, movement_speed: float) -> Dict:
        """根据样式和移动速度获取发型"""
        physics_factor = min(movement_speed / 10, 1.0)
        return {
            "style": style,
            "physics_factor": physics_factor,
            "sway_animation": "enabled" if physics_factor > 0.1 else "disabled"
        }

    async def _get_clothing_by_weather(self, outfit: str, context: str) -> Dict:
        """根据天气获取服装"""
        weather = await self._get_current_weather()
        adaptations = {
            WeatherState.RAINY: {"has_umbrella": random.random() < 0.5, "wet_look": True},
            WeatherState.SNOWY: {"snow_on_clothes": True, "warm_clothing": True},
            WeatherState.SUNNY: {"sunglasses": random.random() < 0.3, "sunhat": False}
        }
        return {
            "outfit": outfit,
            "weather_effects": adaptations.get(weather, {}),
            "context": context
        }

    async def _get_current_weather(self) -> WeatherState:
        return WeatherState.SUNNY

    def _get_active_accessories(self, equipped_items: List[str]) -> Dict:
        """获取激活的配饰"""
        return {"equipped": equipped_items, "glow_effect": len(equipped_items) > 0}

    def _get_aura_by_achievements(self, achievements: List[str]) -> Dict:
        """根据成就获取光环效果"""
        if len(achievements) >= 50:
            return {"effect": AuraEffect.DIVINE_LIGHT, "intensity": 1.0, "color": "#00FF00"}
        elif len(achievements) >= 20:
            return {"effect": AuraEffect.RAINBOW_HALO, "intensity": 0.8, "color": "#FF1493"}
        elif len(achievements) >= 10:
            return {"effect": AuraEffect.COSMIC_FLOW, "intensity": 0.6, "color": "#8A2BE2"}
        return {"effect": AuraEffect.BASIC_GLOW, "intensity": 0.3, "color": "#808080"}

    def _get_title_badge_by_credits(self, credits: int) -> Dict:
        """根据积分获取称号徽章"""
        titles = list(TitleLevel)
        current_title = TitleLevel.NEWBIE.value

        for title_data in titles:
            if credits >= title_data.value["threshold"]:
                current_title = title_data.value

        current_threshold = current_title["threshold"]
        next_threshold = self._get_next_title_threshold(current_threshold)

        progress = (credits - current_threshold) / (next_threshold - current_threshold) if next_threshold > current_threshold else 1.0

        return {
            "title": current_title["title"],
            "color": current_title["color"],
            "effect": current_title["effect"].value,
            "level": current_threshold,
            "progress": progress
        }

    def _get_next_title_threshold(self, current_threshold: int) -> int:
        """获取下一个称号阈值"""
        thresholds = [t.value["threshold"] for t in TitleLevel]
        for t in thresholds:
            if t > current_threshold:
                return t
        return 15000000

    async def _render_pet_companion(self, user_state: UserState) -> Optional[Dict]:
        """渲染宠物伴侣"""
        if not user_state.pet_state:
            return None

        pet = user_state.pet_state
        return {
            "pet_id": pet.pet_id,
            "pet_type": pet.pet_type.value,
            "name": pet.name,
            "growth_stage": pet.growth_stage.value,
            "appearance": pet.appearance,
            "mood": pet.current_mood.value,
            "behavior": pet.current_behavior.value,
            "position_offset": await self._calculate_pet_position_offset(user_state)
        }

    async def _calculate_pet_position_offset(self, user_state: UserState) -> Tuple[float, float]:
        """计算宠物位置偏移"""
        base_offset = (20, 0)
        direction_rad = math.radians(user_state.movement_direction)
        offset_x = base_offset[0] * math.cos(direction_rad) - base_offset[1] * math.sin(direction_rad)
        offset_y = base_offset[0] * math.sin(direction_rad) + base_offset[1] * math.cos(direction_rad)
        return (offset_x, offset_y)

    async def _generate_special_effects(self, user_state: UserState) -> List[Dict]:
        """生成特殊效果"""
        effects = []

        if user_state.current_emotion == Mood.EXCITED:
            effects.append({"type": "sparkles", "intensity": 0.8})
        if user_state.current_emotion == Mood.ANGRY:
            effects.append({"type": "dark_aura", "intensity": 0.6})
        if len(user_state.achievements) > 10:
            effects.append({"type": "achievement_glow", "intensity": 0.5})

        return effects

    async def _get_interactive_points(self) -> List[Dict]:
        """获取交互点"""
        return [
            {"id": "head", "position": "top", "actions": ["wave", "bow"]},
            {"id": "hand", "position": "right", "actions": ["shake", "high_five"]},
            {"id": "pet", "position": "bottom", "actions": ["pet", "feed"]}
        ]

    async def _generate_social_cues(self, user_state: UserState) -> Dict:
        """生成社交暗示"""
        return {
            "friendly": user_state.current_emotion in [Mood.HAPPY, Mood.EXCITED],
            "approachable": len(user_state.achievements) < 10,
            "show_credits": True,
            "show_achievements": len(user_state.achievements) > 0
        }


# ==================== 动画系统 ====================

class AvatarAnimationSystem:
    """形象动画系统"""

    def __init__(self):
        self.animation_library = self._load_animation_library()

    def _load_animation_library(self) -> Dict:
        return {
            "idle": ["breathing", "subtle_sway", "eye_blink"],
            "walking": ["step", "arm_swing", "head_bob"],
            "running": ["fast_step", "arm_pump", "hair_flow"],
            "greeting": ["wave", "bow", "nod"],
            "celebrating": ["jump", "arm_raise", "sparkles"],
            "sad": ["shoulder_drop", "head_hang", "slow_walk"]
        }

    async def generate_animations(self, user_state: UserState, context: str) -> Dict:
        """生成动画"""
        base_animation = "idle"
        if user_state.movement_speed > 5:
            base_animation = "running"
        elif user_state.movement_speed > 1:
            base_animation = "walking"

        context_animation = self._get_context_animation(context)
        emotion_animation = self._get_emotion_animation(user_state.current_emotion)

        return {
            "base": base_animation,
            "context": context_animation,
            "emotion": emotion_animation,
            "transition": "smooth"
        }

    def _get_context_animation(self, context: str) -> str:
        context_map = {
            "social_plaza": "exploring",
            "dungeon": "alert",
            "battle": "combat_ready",
            "home": "relaxed"
        }
        return context_map.get(context, "idle")

    def _get_emotion_animation(self, mood: Mood) -> str:
        mood_map = {
            Mood.HAPPY: "celebrating",
            Mood.SAD: "sad",
            Mood.EXCITED: "energetic",
            Mood.CALM: "peaceful",
            Mood.ANGRY: "agitated"
        }
        return mood_map.get(mood, "idle")


# ==================== 宠物行为系统 ====================

class PetBehaviorSystem:
    """宠物行为系统"""

    def __init__(self):
        self.behavior_templates = self._load_behavior_templates()

    def _load_behavior_templates(self) -> Dict:
        return {
            PetBehavior.IDLE: {
                "animation": "idle_breathing",
                "movement": "stay_close",
                "social": "friendly"
            },
            PetBehavior.FOLLOWING: {
                "animation": "walking",
                "movement": "follow_owner",
                "social": "attentive"
            },
            PetBehavior.PLAYING: {
                "animation": "playful_jump",
                "movement": "explore_nearby",
                "social": "playful"
            },
            PetBehavior.PROTECTIVE: {
                "animation": "alert_stance",
                "movement": "guard_owner",
                "social": "alert"
            },
            PetBehavior.INTERACTING: {
                "animation": "interact_object",
                "movement": "investigate",
                "social": "curious"
            },
            PetBehavior.RESTING: {
                "animation": "sleeping",
                "movement": "stay_near",
                "social": "peaceful"
            },
            PetBehavior.EXPLORING: {
                "animation": "curious_walk",
                "movement": "wander",
                "social": "curious"
            },
            PetBehavior.SOCIALIZING: {
                "animation": "playful",
                "movement": "approach_other",
                "social": "friendly"
            }
        }

    async def decide_behavior(self, pet_state: PetState, owner_state: UserState,
                             environment: Dict) -> PetBehavior:
        """决定宠物行为"""
        context = {
            "owner_speed": owner_state.movement_speed,
            "owner_emotion": owner_state.current_emotion,
            "environment": environment,
            "time_since_interaction": 0
        }

        # 优先级决策
        if context["owner_speed"] > 5:
            return PetBehavior.FOLLOWING
        if pet_state.current_mood == Mood.HUNGRY:
            return PetBehavior.IDLE
        if pet_state.bond_exp > 1000 and random.random() < 0.3:
            return PetBehavior.SOCIALIZING
        if random.random() < 0.2:
            return PetBehavior.EXPLORING
        return PetBehavior.FOLLOWING

    def get_behavior_template(self, behavior: PetBehavior) -> Dict:
        return self.behavior_templates.get(behavior, self.behavior_templates[PetBehavior.IDLE])


# ==================== 智能宠物伴侣系统 ====================

class IntelligentPetCompanion:
    """智能宠物伴侣系统"""

    def __init__(self, owner_id: str):
        self.owner_id = owner_id
        self.pet_state: Optional[PetState] = None
        self.ai_personality_generator = AIPersonalityGenerator()
        self.behavior_tree = PetBehaviorTree()
        self._load_or_create_pet()

    def _load_or_create_pet(self):
        """加载或创建宠物"""
        # 模拟：创建一个默认宠物
        self.pet_state = PetState(
            pet_id=f"pet_{uuid.uuid4().hex[:8]}",
            pet_type=PetType.DIGITAL_CAT,
            name="数据猫咪",
            growth_stage=PetGrowthStage.BABY,
            exp=0,
            bond_exp=0,
            current_mood=Mood.HAPPY,
            current_behavior=PetBehavior.IDLE,
            position=Position(0, 0),
            ai_personality=self.ai_personality_generator.generate_personality(),
            appearance=self._generate_base_appearance(),
            unlocked_abilities=["basic_empathy"]
        )

    def _generate_base_appearance(self) -> Dict:
        appearances = {
            PetType.DIGITAL_CAT: {
                "base_model": "cat",
                "color_scheme": ["#FF6B6B", "#4ECDC4"],
                "size": 1.0,
                "special_effects": ["digital_particles"]
            },
            PetType.DATA_DRAGON: {
                "base_model": "dragon",
                "color_scheme": ["#9B59B6", "#3498DB"],
                "size": 1.5,
                "special_effects": ["data_stream"]
            },
            PetType.AI_PHOENIX: {
                "base_model": "phoenix",
                "color_scheme": ["#E74C3C", "#F39C12"],
                "size": 1.3,
                "special_effects": ["flame_aura"]
            },
            PetType.QUANTUM_FOX: {
                "base_model": "fox",
                "color_scheme": ["#1ABC9C", "#9B59B6"],
                "size": 1.1,
                "special_effects": ["quantum_glitch"]
            }
        }
        return appearances.get(self.pet_state.pet_type, appearances[PetType.DIGITAL_CAT])

    async def render_pet(self, owner_state: UserState) -> Dict:
        """渲染宠物"""
        if not self.pet_state:
            return {}

        base_appearance = self._get_pet_base_appearance()
        growth_stage = self._get_growth_stage()
        mood = await self._calculate_pet_mood(owner_state)
        behavior = await self.behavior_tree.decide_behavior(self.pet_state, owner_state, {})
        interaction_state = await self._get_interaction_state()

        self.pet_state.current_behavior = behavior
        self.pet_state.current_mood = mood

        return {
            "pet_id": self.pet_state.pet_id,
            "owner_id": self.owner_id,
            "base_appearance": base_appearance,
            "growth_stage": growth_stage,
            "mood": mood.value,
            "current_behavior": behavior.value,
            "interaction_state": interaction_state,
            "visual_effects": await self._generate_pet_effects(mood, growth_stage),
            "ai_personality": self.pet_state.ai_personality,
            "bond_level": await self._calculate_bond_level()
        }

    def _get_pet_base_appearance(self) -> Dict:
        return self.pet_state.appearance

    def _get_growth_stage(self) -> Dict:
        stages = {
            PetGrowthStage.BABY: {"name": "幼崽", "size_mult": 0.6, "icon": "🥚"},
            PetGrowthStage.YOUNG: {"name": "少年", "size_mult": 0.8, "icon": "🐣"},
            PetGrowthStage.MATURE: {"name": "成年", "size_mult": 1.0, "icon": "🐾"},
            PetGrowthStage.ELDER: {"name": "老年", "size_mult": 0.9, "icon": "🦴"},
            PetGrowthStage.LEGENDARY: {"name": "传说", "size_mult": 1.2, "icon": "✨"}
        }
        return stages.get(self.pet_state.growth_stage, stages[PetGrowthStage.MATURE])

    async def _calculate_pet_mood(self, owner_state: UserState) -> Mood:
        """计算宠物情绪"""
        if self.pet_state.bond_exp > 1000:
            return Mood.HAPPY
        elif self.pet_state.current_mood == Mood.SLEEPY:
            return Mood.SLEEPY
        elif random.random() < 0.2:
            return Mood.CURIOUS
        return self.pet_state.current_mood

    async def _get_interaction_state(self) -> Dict:
        """获取交互状态"""
        return {
            "can_interact": True,
            "interaction_types": ["pet", "feed", "play", "talk"],
            "cooldown_remaining": 0
        }

    async def _generate_pet_effects(self, mood: Mood, growth_stage: Dict) -> List[Dict]:
        """生成宠物特效"""
        effects = []

        if mood == Mood.HAPPY:
            effects.append({"type": "sparkles", "color": "#FFD700"})
        if mood == Mood.EXCITED:
            effects.append({"type": "bouncing", "intensity": 0.8})
        if self.pet_state.growth_stage == PetGrowthStage.LEGENDARY:
            effects.append({"type": "mythical_aura", "color": "#9400D3"})

        return effects

    async def _calculate_bond_level(self) -> Dict:
        """计算羁绊等级"""
        bond_levels = [
            {"threshold": 0, "name": "陌生", "color": "#808080", "effects": []},
            {"threshold": 100, "name": "相识", "color": "#98FB98", "effects": ["basic_empathy"]},
            {"threshold": 500, "name": "友好", "color": "#87CEEB", "effects": ["emotion_sense", "basic_sync"]},
            {"threshold": 2000, "name": "亲密", "color": "#DA70D6", "effects": ["thought_sense", "medium_sync"]},
            {"threshold": 10000, "name": "灵魂伴侣", "color": "#FFD700", "effects": ["telepathic_link", "full_sync"]}
        ]

        current_level = bond_levels[0]
        next_level = bond_levels[1] if len(bond_levels) > 1 else bond_levels[0]

        for i, level_data in enumerate(bond_levels):
            if self.pet_state.bond_exp >= level_data["threshold"]:
                current_level = level_data
                next_level = bond_levels[i + 1] if i + 1 < len(bond_levels) else level_data

        progress = (self.pet_state.bond_exp - current_level["threshold"]) / \
                  (next_level["threshold"] - current_level["threshold"]) if \
                  next_level["threshold"] > current_level["threshold"] else 1.0

        return {
            "level": current_level["threshold"],
            "name": current_level["name"],
            "color": current_level["color"],
            "effects": current_level["effects"],
            "progress": progress
        }


class AIPersonalityGenerator:
    """AI个性生成器"""

    def generate_personality(self) -> Dict[str, float]:
        """生成AI个性"""
        traits = ["playful", "loyal", "curious", "protective", "mischievous", "calm", "energetic"]
        personality = {}

        for trait in traits:
            personality[trait] = random.uniform(0.3, 1.0)

        # 确保主要个性特征
        primary = random.choice(traits)
        personality[primary] = random.uniform(0.8, 1.0)

        return personality


class PetBehaviorTree:
    """宠物行为树"""

    def __init__(self):
        self.behavior_decisions = [
            {"condition": "owner_moving_fast", "action": PetBehavior.FOLLOWING},
            {"condition": "bored", "action": PetBehavior.EXPLORING},
            {"condition": "sees_friend", "action": PetBehavior.SOCIALIZING},
            {"condition": "sees_toy", "action": PetBehavior.PLAYING},
            {"condition": "hungry", "action": PetBehavior.IDLE},
            {"condition": "tired", "action": PetBehavior.RESTING}
        ]

    async def decide_behavior(self, pet_state: PetState, owner_state: UserState,
                            environment: Dict) -> PetBehavior:
        """决定行为"""
        for decision in self.behavior_decisions:
            if await self._evaluate_condition(decision["condition"], pet_state, owner_state):
                return decision["action"]
        return PetBehavior.IDLE

    async def _evaluate_condition(self, condition: str, pet_state: PetState,
                                  owner_state: UserState) -> bool:
        """评估条件"""
        condition_map = {
            "owner_moving_fast": owner_state.movement_speed > 5,
            "bored": pet_state.bond_exp < 100 and random.random() < 0.3,
            "sees_friend": random.random() < 0.2,
            "sees_toy": random.random() < 0.1,
            "hungry": pet_state.current_mood == Mood.HUNGRY,
            "tired": pet_state.current_mood == Mood.SLEEPY
        }
        return condition_map.get(condition, False)


# ==================== 虚拟社交广场 ====================

class SocialPlaza:
    """虚拟社交广场"""

    def __init__(self):
        self.plaza_size = (1000, 1000)
        self.zones = self._create_zones()
        self.users_in_plaza: Dict[str, Dict] = {}
        self.pets_in_plaza: Dict[str, Dict] = {}
        self.interactive_objects = self._create_interactive_objects()
        self.weather_system = PlazaWeatherSystem()
        self.time_system = PlazaTimeSystem()

    def _create_zones(self) -> Dict[PlazaZone, Dict]:
        return {
            PlazaZone.CENTER: {"name": "中央广场", "capacity": 50, "special": "fountain"},
            PlazaZone.GARDEN: {"name": "花园", "capacity": 30, "special": "flowers"},
            PlazaZone.MARKET: {"name": "市场", "capacity": 40, "special": "shops"},
            PlazaZone.ARENA: {"name": "竞技场", "capacity": 20, "special": "pvp"},
            PlazaZone.TEMPLE: {"name": "神殿", "capacity": 15, "special": "blessing"},
            PlazaZone.LIBRARY: {"name": "图书馆", "capacity": 25, "special": "knowledge"},
            PlazaZone.CAFE: {"name": "咖啡厅", "capacity": 35, "special": "social"},
            PlazaZone.FOUNTAIN: {"name": "喷泉", "capacity": 20, "special": "wishes"}
        }

    def _create_interactive_objects(self) -> Dict[str, Dict]:
        return {
            "fountain_1": {"type": "fountain", "position": Position(500, 500), "interactions": ["make_wish", "watch"]},
            "bench_1": {"type": "bench", "position": Position(300, 400), "interactions": ["sit", "talk"]},
            "tree_1": {"type": "tree", "position": Position(600, 300), "interactions": ["climb", "rest"]}
        }

    async def render_plaza_scene(self, viewer_id: str) -> Dict:
        """渲染广场场景"""
        environment = await self._get_environment()
        viewer_position = self.users_in_plaza.get(viewer_id, {}).get("position", Position(500, 500))
        visible_range = 200

        visible_users = []
        visible_pets = []

        for user_id, user_data in self.users_in_plaza.items():
            if user_id == viewer_id:
                continue
            if self._is_within_range(user_data["position"], viewer_position, visible_range):
                user_render = await self._render_user_in_plaza(user_id, user_data)
                visible_users.append(user_render)

                if user_id in self.pets_in_plaza:
                    pet_render = await self._render_pet_in_plaza(user_id)
                    visible_pets.append(pet_render)

        interactive_objects = []
        for obj_id, obj_data in self.interactive_objects.items():
            if self._is_within_range(obj_data["position"], viewer_position, visible_range):
                obj_render = await self._render_interactive_object(obj_id, obj_data)
                interactive_objects.append(obj_render)

        effects = await self._generate_plaza_effects(environment)

        return {
            "plaza_id": "main_plaza",
            "environment": environment,
            "visible_users": visible_users,
            "visible_pets": visible_pets,
            "interactive_objects": interactive_objects,
            "effects": effects,
            "ambient_sounds": await self._get_ambient_sounds(environment),
            "social_events": await self._get_active_social_events()
        }

    async def _get_environment(self) -> PlazaEnvironment:
        """获取环境"""
        return PlazaEnvironment(
            time_of_day=self.time_system.get_current_time(),
            weather=self.weather_system.get_current_weather(),
            lighting=0.8,
            ambient_sounds=["birds", "wind", "chat"],
            special_events=["daily_quest", "random_encounter"]
        )

    def _is_within_range(self, pos1: Position, pos2: Position, range_val: float) -> bool:
        return pos1.distance_to(pos2) <= range_val

    async def _render_user_in_plaza(self, user_id: str, user_data: Dict) -> Dict:
        """渲染广场中的用户"""
        return {
            "user_id": user_id,
            "position": {"x": user_data["position"].x, "y": user_data["position"].y},
            "avatar": user_data.get("avatar", {}),
            "movement_state": user_data.get("movement_state", "idle"),
            "social_status": user_data.get("status", "available")
        }

    async def _render_pet_in_plaza(self, user_id: str) -> Optional[Dict]:
        """渲染广场中的宠物"""
        if user_id not in self.pets_in_plaza:
            return None
        return self.pets_in_plaza[user_id]

    async def _render_interactive_object(self, obj_id: str, obj_data: Dict) -> Dict:
        """渲染交互对象"""
        return {
            "object_id": obj_id,
            "type": obj_data["type"],
            "position": {"x": obj_data["position"].x, "y": obj_data["position"].y},
            "interactions": obj_data["interactions"]
        }

    async def _generate_plaza_effects(self, environment: PlazaEnvironment) -> List[Dict]:
        """生成广场特效"""
        effects = []

        if environment.weather == WeatherState.RAINY:
            effects.append({"type": "rain", "intensity": 0.7})
        if environment.weather == WeatherState.AURORA:
            effects.append({"type": "aurora", "intensity": 1.0})
        if environment.time_of_day == TimeState.NIGHT:
            effects.append({"type": "fireflies", "intensity": 0.5})

        return effects

    async def _get_ambient_sounds(self, environment: PlazaEnvironment) -> List[str]:
        """获取环境音效"""
        base_sounds = ["ambient_chatter", "footsteps"]

        weather_sounds = {
            WeatherState.RAINY: ["rain", "thunder"],
            WeatherState.SNOWY: ["wind_chime"],
            WeatherState.AURORA: ["ethereal_hum"]
        }

        return base_sounds + weather_sounds.get(environment.weather, [])

    async def _get_active_social_events(self) -> List[Dict]:
        """获取活跃的社交事件"""
        return [
            {"type": "pet_party", "location": PlazaZone.GARDEN.value, "time_remaining": 300},
            {"type": "gift_exchange", "location": PlazaZone.CAFE.value, "participants": 5}
        ]

    def add_user_to_plaza(self, user_id: str, position: Position):
        """添加用户到广场"""
        self.users_in_plaza[user_id] = {
            "position": position,
            "movement_state": "idle",
            "status": "available",
            "avatar": {}
        }

    def remove_user_from_plaza(self, user_id: str):
        """从广场移除用户"""
        if user_id in self.users_in_plaza:
            del self.users_in_plaza[user_id]
        if user_id in self.pets_in_plaza:
            del self.pets_in_plaza[user_id]


class PlazaWeatherSystem:
    """广场天气系统"""

    def __init__(self):
        self.weather_states = list(WeatherState)
        self.current_weather = WeatherState.SUNNY

    def get_current_weather(self) -> WeatherState:
        return self.current_weather

    def set_weather(self, weather: WeatherState):
        self.current_weather = weather


class PlazaTimeSystem:
    """广场时间系统"""

    def __init__(self):
        self.time_states = list(TimeState)
        self.current_time = TimeState.NOON

    def get_current_time(self) -> TimeState:
        return self.current_time

    def set_time(self, time_state: TimeState):
        self.current_time = time_state


# ==================== 动态身份融合系统 ====================

class DynamicIdentityFusion:
    """动态身份融合系统"""

    def __init__(self):
        self.identity_weights = {
            "dungeon": {"dungeon_explorer": 0.5, "werewolf_player": 0.2, "escape_artist": 0.2, "social_influencer": 0.1},
            "social_plaza": {"dungeon_explorer": 0.2, "werewolf_player": 0.2, "escape_artist": 0.2, "social_influencer": 0.4},
            "werewolf_game": {"dungeon_explorer": 0.1, "werewolf_player": 0.6, "escape_artist": 0.1, "social_influencer": 0.2}
        }

    async def fuse_identities(self, user_id: str, context: str) -> Dict:
        """融合多重身份"""
        identities = await self._get_user_identities(user_id)
        weights = self.identity_weights.get(context, self.identity_weights["social_plaza"])

        fused_identity = {
            "appearance": await self._fuse_appearances(identities, weights),
            "abilities": await self._fuse_abilities(identities, weights),
            "personality": await self._fuse_personalities(identities, weights),
            "social_presence": await self._fuse_social_presence(identities, weights)
        }

        fusion_effects = await self._generate_fusion_effects(fused_identity)

        return {
            "fused_identity": fused_identity,
            "fusion_effects": fusion_effects,
            "dominant_aspect": max(weights, key=weights.get),
            "fusion_stability": await self._calculate_fusion_stability(fused_identity)
        }

    async def _get_user_identities(self, user_id: str) -> Dict:
        """获取用户身份"""
        return {
            "dungeon_explorer": {"outfit": "adventure_gear", "aura": "heroic"},
            "werewolf_player": {"outfit": "mysterious_cloak", "aura": "cunning"},
            "escape_artist": {"outfit": "stealth_suit", "aura": "clever"},
            "social_influencer": {"outfit": "fashionable", "aura": "charismatic"}
        }

    async def _fuse_appearances(self, identities: Dict, weights: Dict) -> Dict:
        """融合外观"""
        primary_identity = max(weights, key=weights.get)
        return {
            "primary_outfit": identities[primary_identity]["outfit"],
            "secondary_elements": [identities[k]["outfit"] for k in weights if k != primary_identity and weights[k] > 0.2],
            "aura_blend": [identities[k]["aura"] for k in weights if weights[k] > 0.1]
        }

    async def _fuse_abilities(self, identities: Dict, weights: Dict) -> List[str]:
        """融合能力"""
        abilities = []
        for identity, weight in weights.items():
            if weight > 0.3:
                abilities.extend(self._get_identity_abilities(identity))
        return list(set(abilities))

    def _get_identity_abilities(self, identity: str) -> List[str]:
        ability_map = {
            "dungeon_explorer": ["treasure_sense", "danger_warning"],
            "werewolf_player": ["lie_detection", "social_insight"],
            "escape_artist": ["lockpick", "stealth"],
            "social_influencer": ["charm", "networking"]
        }
        return ability_map.get(identity, [])

    async def _fuse_personalities(self, identities: Dict, weights: Dict) -> Dict:
        """融合性格"""
        return {
            "primary_trait": max(weights, key=weights.get),
            "influence_factors": weights
        }

    async def _fuse_social_presence(self, identities: Dict, weights: Dict) -> Dict:
        """融合社交存在"""
        return {
            "visibility": weights.get("social_influencer", 0.2) * 100,
            "reputation": sum(w for w in weights.values()) * 50
        }

    async def _generate_fusion_effects(self, fused_identity: Dict) -> List[Dict]:
        """生成融合特效"""
        return [{"type": "identity_shift", "elements": fused_identity.get("aura_blend", [])}]

    async def _calculate_fusion_stability(self, fused_identity: Dict) -> float:
        """计算融合稳定性"""
        return random.uniform(0.7, 1.0)


# ==================== 宠物进化树系统 ====================

class PetEvolutionTree:
    """宠物进化树系统"""

    def __init__(self):
        self.evolution_paths = self._load_evolution_paths()

    def _load_evolution_paths(self) -> Dict:
        return {
            PetType.DIGITAL_CAT: {
                "stages": {
                    PetGrowthStage.BABY: {"level": 0, "appearance": "kitten"},
                    PetGrowthStage.YOUNG: {"level": 10, "appearance": "cat"},
                    PetGrowthStage.MATURE: {"level": 30, "appearance": "adult_cat"},
                    PetGrowthStage.ELDER: {"level": 50, "appearance": "wise_cat"},
                    PetGrowthStage.LEGENDARY: {"level": 75, "appearance": "digital_phoenix"}
                },
                "branching": {
                    PetGrowthStage.MATURE: ["cyber_cat", "neko_ai"],
                    "cyber_cat": ["data_panther", "quantum_lynx"]
                }
            },
            PetType.DATA_DRAGON: {
                "stages": {
                    PetGrowthStage.BABY: {"level": 0, "appearance": "hatchling"},
                    PetGrowthStage.YOUNG: {"level": 15, "appearance": "young_dragon"},
                    PetGrowthStage.MATURE: {"level": 35, "appearance": "adult_dragon"},
                    PetGrowthStage.ELDER: {"level": 55, "appearance": "ancient_dragon"},
                    PetGrowthStage.LEGENDARY: {"level": 80, "appearance": "cosmic_dragon"}
                },
                "branching": {}
            },
            PetType.AI_PHOENIX: {
                "stages": {
                    PetGrowthStage.BABY: {"level": 0, "appearance": "spark"},
                    PetGrowthStage.YOUNG: {"level": 15, "appearance": "flame"},
                    PetGrowthStage.MATURE: {"level": 35, "appearance": "phoenix"},
                    PetGrowthStage.ELDER: {"level": 55, "appearance": "solar_phoenix"},
                    PetGrowthStage.LEGENDARY: {"level": 75, "appearance": "divine_aurora"}
                },
                "branching": {}
            }
        }

    async def evolve_pet(self, pet_id: str, evolution_path: str) -> Dict:
        """宠物进化"""
        pet_state = await self._get_pet_state(pet_id)
        if not pet_state:
            return {"success": False, "error": "Pet not found"}

        current_stage = pet_state.growth_stage
        can_evolve = await self._check_evolution_conditions(pet_state, evolution_path)

        if not can_evolve["success"]:
            return can_evolve

        new_stage = await self._execute_evolution(pet_state, evolution_path)
        evolution_animation = await self._generate_evolution_animation(current_stage, new_stage)
        new_abilities = await self._unlock_evolution_abilities(new_stage)
        new_appearance = await self._generate_new_appearance(new_stage, pet_state)

        return {
            "success": True,
            "pet_id": pet_id,
            "old_stage": current_stage.value,
            "new_stage": new_stage.value,
            "evolution_animation": evolution_animation,
            "new_abilities": new_abilities,
            "new_appearance": new_appearance,
            "evolution_bonus": await self._calculate_evolution_bonus(new_stage)
        }

    async def _get_pet_state(self, pet_id: str) -> Optional[PetState]:
        """获取宠物状态"""
        # 模拟查找
        return None

    async def _check_evolution_conditions(self, pet_state: PetState, path: str) -> Dict:
        """检查进化条件"""
        path_data = self.evolution_paths.get(pet_state.pet_type, {})
        stages = path_data.get("stages", {})
        current_stage_data = stages.get(pet_state.growth_stage, {})

        required_level = current_stage_data.get("level", 0)
        if pet_state.exp < required_level:
            return {"success": False, "reason": f"需要 {required_level} 经验值"}

        return {"success": True}

    async def _execute_evolution(self, pet_state: PetState, path: str) -> PetGrowthStage:
        """执行进化"""
        path_data = self.evolution_paths.get(pet_state.pet_type, {})
        stages = list(path_data.get("stages", {}).keys())

        current_index = stages.index(pet_state.growth_stage) if pet_state.growth_stage in stages else 0
        if current_index + 1 < len(stages):
            return stages[current_index + 1]
        return pet_state.growth_stage

    async def _generate_evolution_animation(self, old_stage: PetGrowthStage, new_stage: PetGrowthStage) -> Dict:
        """生成进化动画"""
        return {
            "duration": 3000,
            "effects": ["light_burst", "transformation", "sparkles"],
            "sound": "evolution_jingle"
        }

    async def _unlock_evolution_abilities(self, new_stage: PetGrowthStage) -> List[str]:
        """解锁进化能力"""
        ability_map = {
            PetGrowthStage.YOUNG: ["basic_skill_1"],
            PetGrowthStage.MATURE: ["advanced_skill", "passive_boost"],
            PetGrowthStage.ELDER: ["ultimate_ability", "special_aura"],
            PetGrowthStage.LEGENDARY: ["mythical_power", "transform"]
        }
        return ability_map.get(new_stage, [])

    async def _generate_new_appearance(self, stage: PetGrowthStage, pet_state: PetState) -> Dict:
        """生成新外观"""
        path_data = self.evolution_paths.get(pet_state.pet_type, {})
        stages = path_data.get("stages", {})
        stage_data = stages.get(stage, {"appearance": "default"})

        return {
            "base_model": stage_data.get("appearance", "default"),
            "color_intensify": 1.2,
            "size_mult": 1.1 if stage == PetGrowthStage.LEGENDARY else 1.0
        }

    async def _calculate_evolution_bonus(self, new_stage: PetGrowthStage) -> Dict:
        """计算进化奖励"""
        bonus_map = {
            PetGrowthStage.YOUNG: {"stat_boost": 1.1, "new_skill_slot": 1},
            PetGrowthStage.MATURE: {"stat_boost": 1.2, "new_skill_slot": 2},
            PetGrowthStage.ELDER: {"stat_boost": 1.3, "new_skill_slot": 3},
            PetGrowthStage.LEGENDARY: {"stat_boost": 2.0, "new_skill_slot": 5, "special_trait": "mythical"}
        }
        return bonus_map.get(new_stage, {"stat_boost": 1.0})


# ==================== 社交羁绊可视化 ====================

class SocialBondVisualization:
    """社交羁绊可视化"""

    def __init__(self):
        self.user_bonds: Dict[str, Dict[str, SocialBond]] = defaultdict(dict)

    async def visualize_social_bonds(self, user_id: str) -> Dict:
        """可视化社交关系"""
        bonds = self.user_bonds.get(user_id, {})

        visualization = {
            "user_node": await self._create_user_node(user_id),
            "friend_nodes": [],
            "bond_lines": [],
            "group_clusters": [],
            "interaction_flows": []
        }

        for friend_id, bond_data in bonds.items():
            friend_node = await self._create_friend_node(friend_id, bond_data)
            visualization["friend_nodes"].append(friend_node)

            bond_line = await self._create_bond_line(user_id, friend_id, bond_data)
            visualization["bond_lines"].append(bond_line)

            interaction_flow = await self._create_interaction_flow(user_id, friend_id)
            visualization["interaction_flows"].append(interaction_flow)

        clusters = await self._analyze_social_clusters(bonds)
        visualization["group_clusters"] = clusters

        social_field = await self._generate_social_energy_field(visualization)
        visualization["social_field"] = social_field

        return visualization

    async def _create_user_node(self, user_id: str) -> Dict:
        """创建用户节点"""
        return {
            "user_id": user_id,
            "display_name": f"用户_{user_id[:6]}",
            "avatar": {},
            "status": "online",
            "influence_score": random.uniform(50, 100)
        }

    async def _create_friend_node(self, friend_id: str, bond_data: SocialBond) -> Dict:
        """创建好友节点"""
        return {
            "user_id": friend_id,
            "display_name": f"好友_{friend_id[:6]}",
            "avatar": {},
            "bond_level": bond_data.bond_level.value,
            "bond_strength": bond_data.bond_strength
        }

    async def _create_bond_line(self, user_a: str, user_b: str, bond_data: SocialBond) -> Dict:
        """创建羁绊线条"""
        styles = {
            "weak": {"width": 1, "color": "#808080", "pattern": "dashed"},
            "medium": {"width": 2, "color": "#4CAF50", "pattern": "solid"},
            "strong": {"width": 3, "color": "#2196F3", "pattern": "solid"},
            "soulmate": {"width": 5, "color": "#E91E63", "pattern": "glowing"}
        }

        strength_key = "weak"
        if bond_data.bond_strength > 80:
            strength_key = "soulmate"
        elif bond_data.bond_strength > 60:
            strength_key = "strong"
        elif bond_data.bond_strength > 30:
            strength_key = "medium"

        style = styles[strength_key]

        return {
            "user_a": user_a,
            "user_b": user_b,
            "strength": bond_data.bond_strength,
            "style": style,
            "particles": await self._generate_bond_particles(bond_data.bond_strength),
            "animation": "pulse" if strength_key in ["strong", "soulmate"] else "none"
        }

    async def _generate_bond_particles(self, strength: float) -> List[Dict]:
        """生成羁绊粒子"""
        particle_count = int(strength / 20)
        return [{"x": random.uniform(-10, 10), "y": random.uniform(-10, 10)} for _ in range(particle_count)]

    async def _create_interaction_flow(self, user_a: str, user_b: str) -> Dict:
        """创建互动流"""
        return {
            "from": user_a,
            "to": user_b,
            "flow_type": "chat" if random.random() < 0.5 else "gift",
            "intensity": random.uniform(0.3, 1.0)
        }

    async def _analyze_social_clusters(self, bonds: Dict[str, SocialBond]) -> List[Dict]:
        """分析社交聚类"""
        clusters = []
        processed = set()

        for user_id, bond_data in bonds.items():
            if user_id in processed:
                continue

            cluster = {
                "members": [user_id],
                "bond_type": "friend_group",
                "cluster_size": 1
            }

            for other_id, other_bond in bonds.items():
                if other_id != user_id and other_id not in processed:
                    if other_bond.bond_strength > 50:
                        cluster["members"].append(other_id)
                        cluster["cluster_size"] += 1
                        processed.add(other_id)

            if cluster["cluster_size"] > 1:
                clusters.append(cluster)
            processed.add(user_id)

        return clusters

    async def _generate_social_energy_field(self, visualization: Dict) -> Dict:
        """生成社交能量场"""
        return {
            "field_type": "radial",
            "radius": 100 + len(visualization["friend_nodes"]) * 10,
            "color": "#FFD700",
            "intensity": len(visualization["friend_nodes"]) / 10
        }

    def add_bond(self, user_a: str, user_b: str, bond_data: SocialBond):
        """添加羁绊"""
        self.user_bonds[user_a][user_b] = bond_data
        self.user_bonds[user_b][user_a] = bond_data


# ==================== 天气与时间影响系统 ====================

class WeatherTimeImpact:
    """天气与时间影响系统"""

    def __init__(self):
        self.weather_states = list(WeatherState)
        self.time_states = list(TimeState)
        self.current_weather = WeatherState.SUNNY
        self.current_time = TimeState.NOON

    async def calculate_environment_impact(self, user_id: str) -> Dict:
        """计算环境对用户的影响"""
        impacts = {
            "avatar_appearance": await self._get_weather_effects(self.current_weather),
            "pet_behavior": await self._get_time_effects(self.current_time),
            "social_interaction": await self._get_environment_social_impact(),
            "mood_effects": await self._calculate_mood_impact(user_id)
        }

        special_events = await self._check_special_events()

        return {
            "weather": self.current_weather.value,
            "time": self.current_time.value,
            "impacts": impacts,
            "special_events": special_events,
            "environment_mood": await self._calculate_environment_mood()
        }

    async def _get_weather_effects(self, weather: WeatherState) -> Dict:
        """获取天气效果"""
        effects_map = {
            WeatherState.RAINY: {
                "avatar": {"wet_look": True, "umbrella": random.random() < 0.5, "rain_drips": True},
                "environment": {"puddles": True, "rain_particles": 1000}
            },
            WeatherState.SNOWY: {
                "avatar": {"snow_on_clothes": True, "breath_visible": True, "red_cheeks": True},
                "environment": {"snow_particles": 800, "footprints": True}
            },
            WeatherState.AURORA: {
                "avatar": {"aurora_reflection": True, "magical_glow": True},
                "environment": {"northern_lights": True, "starry_sky": True}
            },
            WeatherState.SUNNY: {
                "avatar": {"sunglasses": random.random() < 0.3, "sunhat": False},
                "environment": {"bright": True, "warm": True}
            }
        }
        return effects_map.get(weather, effects_map[WeatherState.SUNNY])

    async def _get_time_effects(self, time: TimeState) -> Dict:
        """获取时间效果"""
        effects_map = {
            TimeState.DAWN: {"activity": "morning_routine", "energy_mult": 1.2},
            TimeState.NOON: {"activity": "peak_activity", "energy_mult": 1.0},
            TimeState.NIGHT: {"activity": "night_owls", "energy_mult": 1.5},
            TimeState.MIDNIGHT: {"activity": "mysterious_encounters", "energy_mult": 0.8}
        }
        return effects_map.get(time, effects_map[TimeState.NOON])

    async def _get_environment_social_impact(self) -> Dict:
        """获取环境社交影响"""
        base_impact = 1.0

        if self.current_weather == WeatherState.RAINY:
            base_impact *= 0.7
        elif self.current_weather == WeatherState.SUNNY:
            base_impact *= 1.2

        if self.current_time in [TimeState.NIGHT, TimeState.MIDNIGHT]:
            base_impact *= 0.8

        return {
            "social_activity_mult": base_impact,
            "interaction_chance": base_impact * 0.5
        }

    async def _calculate_mood_impact(self, user_id: str) -> Dict:
        """计算情绪影响"""
        mood_map = {
            WeatherState.SUNNY: Mood.HAPPY,
            WeatherState.RAINY: Mood.SAD,
            WeatherState.STORMY: Mood.ANGRY
        }

        time_mood_map = {
            TimeState.MORNING: "energized",
            TimeState.NIGHT: "romantic",
            TimeState.MIDNIGHT: "mysterious"
        }

        return {
            "weather_mood": mood_map.get(self.current_weather, Mood.CALM).value,
            "time_mood": time_mood_map.get(self.current_time, "normal")
        }

    async def _check_special_events(self) -> List[Dict]:
        """检查特殊事件"""
        events = []

        if self.current_weather == WeatherState.AURORA and self.current_time == TimeState.NIGHT:
            events.append({"type": "aurora_bloom", "duration": 3600, "bonus": "rare_items"})

        return events

    async def _calculate_environment_mood(self) -> str:
        """计算环境情绪"""
        mood_combinations = {
            (WeatherState.SUNNY, TimeState.NOON): "vibrant",
            (WeatherState.RAINY, TimeState.NIGHT): "cozy",
            (WeatherState.SNOWY, TimeState.MIDNIGHT): "magical",
            (WeatherState.AURORA, TimeState.NIGHT): "ethereal"
        }
        return mood_combinations.get((self.current_weather, self.current_time), "normal")


# ==================== 宠物社交网络 ====================

class PetSocialNetwork:
    """宠物社交网络"""

    def __init__(self):
        self.pet_relationships: Dict[str, Dict[str, Dict]] = defaultdict(dict)

    async def simulate_pet_socializing(self, pet_id: str, nearby_pets: Dict) -> Dict:
        """模拟宠物社交"""
        social_events = []

        for other_pet_id, other_pet_data in nearby_pets.items():
            if other_pet_id == pet_id:
                continue

            compatibility = await self._calculate_pet_compatibility(pet_id, other_pet_id)

            if compatibility["compatible"]:
                interaction = await self._create_pet_interaction(pet_id, other_pet_id, compatibility)
                social_events.append(interaction)

                await self._increase_pet_bond(pet_id, other_pet_id, compatibility["bond_gain"])

        if len(nearby_pets) >= 3:
            party_event = await self._create_pet_party(pet_id, nearby_pets)
            social_events.append(party_event)

        return {
            "pet_id": pet_id,
            "social_events": social_events,
            "friends_made": len(social_events),
            "social_exp_gained": sum(e.get("exp_gain", 0) for e in social_events)
        }

    async def _calculate_pet_compatibility(self, pet_a: str, pet_b: str) -> Dict:
        """计算宠物兼容性"""
        base_compatibility = random.uniform(0.3, 1.0)
        personality_match = random.uniform(0.2, 0.8)

        total_compatibility = (base_compatibility + personality_match) / 2

        return {
            "compatible": total_compatibility > 0.5,
            "compatibility_score": total_compatibility,
            "bond_gain": int(total_compatibility * 10),
            "interaction_type": "playful" if total_compatibility > 0.7 else "cautious"
        }

    async def _create_pet_interaction(self, pet_a: str, pet_b: str,
                                      compatibility: Dict) -> Dict:
        """创建宠物互动"""
        interaction_types = {
            "playful": {"animation": "chase", "exp": 10},
            "friendly": {"animation": "nuzzle", "exp": 15},
            "curious": {"animation": "investigate", "exp": 8},
            "competitive": {"animation": "play_fight", "exp": 20}
        }

        interaction_type = compatibility.get("interaction_type", "playful")
        config = interaction_types.get(interaction_type, interaction_types["playful"])

        return {
            "type": interaction_type,
            "pets": [pet_a, pet_b],
            "animation": config["animation"],
            "exp_gain": config["exp"],
            "bond_gain": compatibility.get("bond_gain", 5),
            "duration": random.randint(3000, 10000)
        }

    async def _increase_pet_bond(self, pet_a: str, pet_b: str, bond_gain: int):
        """增加宠物羁绊"""
        if pet_b not in self.pet_relationships[pet_a]:
            self.pet_relationships[pet_a][pet_b] = {"bond_exp": 0}
        self.pet_relationships[pet_a][pet_b]["bond_exp"] += bond_gain

    async def _create_pet_party(self, host_pet_id: str, nearby_pets: Dict) -> Dict:
        """创建宠物聚会"""
        return {
            "type": "party",
            "host": host_pet_id,
            "participants": list(nearby_pets.keys())[:5],
            "activity": "social_gathering",
            "exp_bonus": 25,
            "duration": 30000
        }


# ==================== 情绪同步系统 ====================

class EmotionSynchronization:
    """情绪同步系统"""

    def __init__(self):
        self.sync_cooldowns: Dict[str, float] = {}

    async def sync_emotions(self, owner_id: str, pet_id: str) -> Dict:
        """同步情绪"""
        owner_emotion = await self._get_owner_emotion(owner_id)
        pet_emotion = await self._get_pet_emotion(pet_id)

        if pet_id in self.sync_cooldowns:
            cooldown_remaining = self.sync_cooldowns[pet_id]
            if cooldown_remaining > 0:
                return {"synced": False, "reason": "cooldown", "remaining": cooldown_remaining}

        contagion_strength = await self._calculate_contagion_strength(owner_id, pet_id)

        if contagion_strength > 0.7:
            new_pet_emotion = await self._blend_emotions(pet_emotion, owner_emotion, contagion_strength)
            await self._set_pet_emotion(pet_id, new_pet_emotion)

            sync_effects = await self._generate_sync_effects(owner_emotion, new_pet_emotion, contagion_strength)

            self.sync_cooldowns[pet_id] = 60

            return {
                "synced": True,
                "owner_emotion": owner_emotion.value,
                "new_pet_emotion": new_pet_emotion.value,
                "sync_strength": contagion_strength,
                "sync_effects": sync_effects,
                "bond_increase": await self._calculate_bond_increase(contagion_strength)
            }

        return {"synced": False, "reason": "bond_too_weak"}

    async def _get_owner_emotion(self, owner_id: str) -> Mood:
        """获取主人情绪"""
        return random.choice(list(Mood))

    async def _get_pet_emotion(self, pet_id: str) -> Mood:
        """获取宠物情绪"""
        return random.choice(list(Mood))

    async def _calculate_contagion_strength(self, owner_id: str, pet_id: str) -> float:
        """计算传染强度"""
        base_strength = 0.5
        bond_mult = 1.0
        return min(base_strength * bond_mult, 1.0)

    async def _blend_emotions(self, pet_emotion: Mood, owner_emotion: Mood,
                            strength: float) -> Mood:
        """混合情绪"""
        if random.random() < strength:
            return owner_emotion
        return pet_emotion

    async def _set_pet_emotion(self, pet_id: str, emotion: Mood):
        """设置宠物情绪"""
        pass

    async def _generate_sync_effects(self, owner_emotion: Mood, pet_emotion: Mood,
                                    strength: float) -> List[Dict]:
        """生成同步特效"""
        effects = []

        if owner_emotion == Mood.HAPPY and pet_emotion == Mood.HAPPY:
            effects.append({"type": "sparkle_burst", "color": "#FFD700", "intensity": strength})
        elif owner_emotion == Mood.SAD:
            effects.append({"type": "comfort_aura", "color": "#87CEEB", "intensity": strength})

        return effects

    async def _calculate_bond_increase(self, strength: float) -> int:
        """计算羁绊增加"""
        return int(strength * 5)


# ==================== 成就解锁外观系统 ====================

class AchievementUnlockAppearance:
    """成就解锁外观"""

    def __init__(self):
        self.achievement_rewards = self._load_achievement_rewards()

    def _load_achievement_rewards(self) -> Dict:
        return {
            "dungeon_master_100": {
                "type": "title",
                "title": "地牢主宰",
                "color": "#FF0000",
                "effect": "dark_aura"
            },
            "werewolf_pro": {
                "type": "accessory",
                "item": "moonlit_cloak",
                "effects": ["night_vision", "silent_footsteps"]
            },
            "escape_expert": {
                "type": "pet_skin",
                "pet_type": "all",
                "skin": "lockpick_pattern",
                "effects": ["find_hidden_items"]
            },
            "social_butterfly": {
                "type": "aura",
                "effect": "social_magnet",
                "radius": 50,
                "color": "#FF69B4"
            },
            "pet_whisperer": {
                "type": "pet_evolution_boost",
                "boost": 1.5,
                "unlocked_pet": PetType.QUANTUM_FOX
            },
            "legendary_collector": {
                "type": "wardrobe",
                "items": ["legendary_outfit", "mythic_crown"],
                "effects": ["special_idle_animation"]
            }
        }

    async def unlock_achievement_appearance(self, user_id: str, achievement_id: str) -> Dict:
        """解锁成就外观"""
        achievement = await self._get_achievement(user_id, achievement_id)

        if not achievement.get("unlocked", False):
            return {"unlocked": False, "reason": "成就未解锁"}

        reward = self.achievement_rewards.get(achievement_id, {})
        if not reward:
            return {"unlocked": False, "reason": "无外观奖励"}

        await self._unlock_appearance(user_id, reward)
        unlock_showcase = await self._create_unlock_showcase(user_id, achievement_id, reward)

        return {
            "unlocked": True,
            "achievement": achievement,
            "appearance_reward": reward,
            "showcase": unlock_showcase,
            "new_look": await self._preview_new_look(user_id, reward)
        }

    async def _get_achievement(self, user_id: str, achievement_id: str) -> Dict:
        """获取成就"""
        return {"achievement_id": achievement_id, "unlocked": True, "progress": 100}

    async def _unlock_appearance(self, user_id: str, reward: Dict):
        """解锁外观"""
        pass

    async def _create_unlock_showcase(self, user_id: str, achievement_id: str,
                                     reward: Dict) -> Dict:
        """创建解锁展示"""
        return {
            "animation": "achievement_unlock",
            "duration": 3000,
            "camera_effect": "zoom_in",
            "particles": ["confetti", "sparkles"]
        }

    async def _preview_new_look(self, user_id: str, reward: Dict) -> Dict:
        """预览新外观"""
        return {
            "preview_type": reward.get("type", "unknown"),
            "elements": reward,
            "apply_preview": True
        }


# ==================== 主引擎类 ====================

class VirtualAvatarSocialEngine:
    """虚拟形象与社交广场引擎 - 统一入口"""

    def __init__(self):
        self.avatar_system = VirtualAvatarSystem()
        self.pet_system = PetSystem()
        self.plaza_system = SocialPlaza()
        self.identity_fusion = DynamicIdentityFusion()
        self.pet_evolution = PetEvolutionTree()
        self.bond_visualization = SocialBondVisualization()
        self.weather_time = WeatherTimeImpact()
        self.pet_social = PetSocialNetwork()
        self.emotion_sync = EmotionSynchronization()
        self.achievement_unlock = AchievementUnlockAppearance()

    async def initialize_user(self, user_id: str) -> Dict:
        """初始化用户"""
        avatar = await self.avatar_system.create_avatar(user_id)
        pet = await self.pet_system.create_pet(user_id)

        return {
            "user_id": user_id,
            "avatar": avatar,
            "pet": pet,
            "initial_credits": 1000,
            "welcome_message": "欢迎来到虚拟社交广场！"
        }

    async def render_plaza_view(self, user_id: str) -> Dict:
        """渲染广场视图"""
        scene = await self.plaza_system.render_plaza_scene(user_id)
        bonds = await self.bond_visualization.visualize_social_bonds(user_id)
        environment_impact = await self.weather_time.calculate_environment_impact(user_id)

        return {
            "scene": scene,
            "bonds": bonds,
            "environment": environment_impact
        }

    async def update_user_state(self, user_id: str, new_state: Dict) -> Dict:
        """更新用户状态"""
        self.plaza_system.users_in_plaza[user_id].update(new_state)
        return {"success": True, "new_state": new_state}


class VirtualAvatarSystem:
    """虚拟形象系统"""

    async def create_avatar(self, user_id: str) -> Dict:
        """创建形象"""
        avatar = VirtualAvatar(user_id)
        return await avatar.render_avatar()


class PetSystem:
    """宠物系统"""

    async def create_pet(self, owner_id: str) -> Dict:
        """创建宠物"""
        pet_companion = IntelligentPetCompanion(owner_id)
        owner_state = await self._get_dummy_owner_state()
        return await pet_companion.render_pet(owner_state)

    async def _get_dummy_owner_state(self) -> UserState:
        """获取模拟主人状态"""
        return UserState(
            user_id="dummy",
            display_name="主人",
            avatar_state={},
            pet_state=None,
            current_position=Position(500, 500),
            movement_direction=0,
            movement_speed=0,
            total_credits=0,
            achievements=[],
            current_emotion=Mood.CALM,
            equipped_items=[],
            outfit="casual",
            hairstyle="short",
            level=1
        )


# ==================== 导出 ====================

__all__ = [
    # 枚举
    'AvatarLayer', 'PetType', 'PetGrowthStage', 'PetBehavior', 'Mood',
    'WeatherState', 'TimeState', 'BondLevel', 'AuraEffect', 'TitleLevel', 'PlazaZone',

    # 数据类
    'Position', 'AvatarLayerData', 'PetState', 'UserState', 'SocialBond', 'PlazaEnvironment',

    # 核心类
    'VirtualAvatar', 'AvatarAnimationSystem', 'PetBehaviorSystem',
    'IntelligentPetCompanion', 'AIPersonalityGenerator', 'PetBehaviorTree',
    'SocialPlaza', 'PlazaWeatherSystem', 'PlazaTimeSystem',
    'DynamicIdentityFusion', 'PetEvolutionTree', 'SocialBondVisualization',
    'WeatherTimeImpact', 'PetSocialNetwork', 'EmotionSynchronization',
    'AchievementUnlockAppearance', 'VirtualAvatarSocialEngine',
    'VirtualAvatarSystem', 'PetSystem'
]
