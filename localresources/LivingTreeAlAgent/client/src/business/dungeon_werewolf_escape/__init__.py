# -*- coding: utf-8 -*-
"""
融合游戏系统：暗黑地牢 + 狼人杀 + 密室逃脱
=====================================

核心创新理念："无限生成的地牢冒险 + 社交推理的狼人杀 + 智力解谜的密室逃脱 = 下一代沉浸式AI游戏"

作者：Hermes Desktop V2.0
版本：1.0.0
"""

import asyncio
import random
import uuid
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from collections import defaultdict
import json
import math


# ==================== 枚举定义 ====================

class DungeonTheme(Enum):
    """地牢主题"""
    ANCIENT_CRYPT = "ancient_crypt"
    MAGIC_ACADEMY = "magic_academy"
    ABANDONED_MINE = "abandoned_mine"
    DEMON_FORGE = "demon_forge"
    CELESTIAL_PRISON = "celestial_prison"
    CLOCKWORK_CITY = "clockwork_city"
    LIVING_FOREST = "living_forest"
    DREAM_PALACE = "dream_palace"
    VOID_TEMPLE = "void_temple"
    ABYSSAL_DEPTHS = "abyssal_depths"


class RoomType(Enum):
    """房间类型"""
    COMBAT = "combat"
    TREASURE = "treasure"
    PUZZLE = "puzzle"
    REST = "rest"
    EVENT = "event"
    BOSS = "boss"
    SECRET = "secret"
    TRAP = "trap"


class WerewolfRole(Enum):
    """狼人杀角色"""
    VILLAGER = "villager"
    WEREWOLF = "werewolf"
    SEER = "seer"
    GUARDIAN = "guardian"
    HUNTER = "hunter"
    WITCH = "witch"
    FOOL = "fool"
    SERIAL_KILLER = "serial_killer"


class GamePhase(Enum):
    """游戏阶段"""
    LOBBY = "lobby"
    NIGHT = "night"
    DAY = "day"
    DISCUSSION = "discussion"
    VOTE = "vote"
    ESCAPE = "escape"
    COMBAT = "combat"
    END = "end"


class PuzzleType(Enum):
    """谜题类型"""
    LOGIC = "logic"
    PATTERN = "pattern"
    MATH = "math"
    WORD = "word"
    SEQUENCE = "sequence"
    SPATIAL = "spatial"
    CRYPTIC = "cryptic"
    MULTISTEP = "multistep"


class ItemRarity(Enum):
    """物品稀有度"""
    COMMON = ("common", 1.0, 0.6)
    UNCOMMON = ("uncommon", 1.5, 0.25)
    RARE = ("rare", 2.0, 0.1)
    EPIC = ("epic", 3.0, 0.04)
    LEGENDARY = ("legendary", 5.0, 0.01)

    def __init__(self, name: str, value_mult: float, chance: float):
        self.name = name
        self.value_mult = value_mult
        self.chance = chance


# ==================== 数据类定义 ====================

@dataclass
class Position:
    """位置坐标"""
    x: int
    y: int

    def distance_to(self, other: 'Position') -> float:
        return math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)

    def __hash__(self):
        return hash((self.x, self.y))


@dataclass
class Player:
    """玩家基础信息"""
    player_id: str
    name: str
    level: int = 1
    hp: int = 100
    max_hp: int = 100
    mp: int = 50
    max_mp: int = 50
    credits: int = 0
    exp: int = 0
    alive: bool = True
    location: Optional[Position] = None
    role: Optional[str] = None
    team: Optional[str] = None
    inventory: List[str] = field(default_factory=list)
    abilities: List[str] = field(default_factory=list)
    status_effects: Dict[str, int] = field(default_factory=dict)


@dataclass
class DungeonLayer:
    """地牢层"""
    layer_id: str
    depth: int
    theme: DungeonTheme
    difficulty: float
    rooms: List['Room'] = field(default_factory=list)
    corridors: List[Tuple[str, str]] = field(default_factory=list)
    monsters: List['NPC'] = field(default_factory=list)
    npcs: List['NPC'] = field(default_factory=list)
    secrets: List['Secret'] = field(default_factory=list)
    boss: Optional['NPC'] = None
    dynamic_events: List['DynamicEvent'] = field(default_factory=list)
    main_story: Optional['StoryArc'] = None
    environment_story: str = ""


@dataclass
class Room:
    """房间"""
    room_id: str
    room_type: RoomType
    position: Position
    theme: DungeonTheme
    contents: Dict[str, Any] = field(default_factory=dict)
    connections: List[str] = field(default_factory=list)
    secret_doors: List[str] = field(default_factory=list)
    environment_effects: List[str] = field(default_factory=list)
    story: str = ""
    discovered: bool = False
    cleared: bool = False


@dataclass
class NPC:
    """NPC/怪物"""
    npc_id: str
    name: str
    role: str
    level: int
    stats: Dict[str, int] = field(default_factory=dict)
    abilities: List[str] = field(default_factory=list)
    ai_behavior: Dict[str, Any] = field(default_factory=dict)
    dialogue: List[str] = field(default_factory=list)
    loot_table: List[Tuple[str, float]] = field(default_factory=list)
    visual_appearance: Dict[str, str] = field(default_factory=dict)
    backstory: str = ""
    quests: List[Dict] = field(default_factory=list)
    boss_mechanics: Optional[Dict] = None
    phases: Optional[List[Dict]] = None
    alive: bool = True
    hp: int = 100
    max_hp: int = 100


@dataclass
class Secret:
    """隐藏要素"""
    secret_id: str
    secret_type: str
    location: Position
    hint: str = ""
    discovered: bool = False
    content: Any = None


@dataclass
class DynamicEvent:
    """动态事件"""
    event_id: str
    event_type: str
    trigger: str
    chance: float
    effects: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StoryArc:
    """故事弧"""
    arc_id: str
    title: str
    description: str
    objectives: List[str] = field(default_factory=list)
    rewards: Dict[str, Any] = field(default_factory=dict)
    completed: bool = False


@dataclass
class WerewolfGame:
    """狼人杀游戏"""
    game_id: str
    dungeon_layer: DungeonLayer
    players: Dict[str, Player] = field(default_factory=dict)
    phase: GamePhase = GamePhase.LOBBY
    day_number: int = 1
    alive_players: int = 0
    chat_log: List[Dict] = field(default_factory=list)
    vote_history: List[Dict] = field(default_factory=list)
    kill_log: List[Dict] = field(default_factory=list)
    special_events: List[Dict] = field(default_factory=list)
    night_actions: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EscapeRoom:
    """密室逃脱"""
    room_id: str
    theme: DungeonTheme
    difficulty: int
    time_limit: int
    puzzles: List['Puzzle'] = field(default_factory=list)
    clues: List['Clue'] = field(default_factory=list)
    red_herrings: List['RedHerring'] = field(default_factory=list)
    environment: Dict[str, Any] = field(default_factory=dict)
    story: str = ""
    progression_gates: List[str] = field(default_factory=list)
    hidden_compartments: List[Dict] = field(default_factory=list)
    interactive_objects: List[Dict] = field(default_factory=list)
    escape_conditions: List[str] = field(default_factory=list)


@dataclass
class Puzzle:
    """谜题"""
    puzzle_id: str
    puzzle_type: PuzzleType
    difficulty: float
    description: str = ""
    solution: Any = None
    hints: List[str] = field(default_factory=list)
    solved: bool = False
    attempts: int = 0
    time_limit: Optional[int] = None


@dataclass
class Clue:
    """线索"""
    clue_id: str
    puzzle_id: str
    clue_type: str
    content: str = ""
    hidden_in: str = ""
    requires_action: bool = False
    used: bool = False


@dataclass
class RedHerring:
    """误导线索"""
    herring_id: str
    description: str
    misdirection: str = ""


@dataclass
class FusionGame:
    """融合游戏"""
    game_id: str
    dungeon: Optional[DungeonLayer] = None
    werewolf: Optional[WerewolfGame] = None
    escape_room: Optional[EscapeRoom] = None
    phase: GamePhase = GamePhase.LOBBY
    players: Dict[str, Player] = field(default_factory=dict)
    story: Dict[str, Any] = field(default_factory=dict)
    victory_conditions: Dict[str, str] = field(default_factory=dict)
    narrative_events: List[Dict] = field(default_factory=list)
    cross_game_progress: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Item:
    """物品"""
    item_id: str
    name: str
    item_type: str
    rarity: ItemRarity
    value: int
    stats: Dict[str, int] = field(default_factory=dict)
    effects: List[str] = field(default_factory=list)
    description: str = ""
    stackable: bool = False
    quantity: int = 1


# ==================== AI地牢生成器 ====================

class AI_DungeonGenerator:
    """AI驱动的无限地牢生成器"""

    THEMES = [
        DungeonTheme.ANCIENT_CRYPT,
        DungeonTheme.MAGIC_ACADEMY,
        DungeonTheme.ABANDONED_MINE,
        DungeonTheme.DEMON_FORGE,
        DungeonTheme.CELESTIAL_PRISON,
        DungeonTheme.CLOCKWORK_CITY,
        DungeonTheme.LIVING_FOREST,
        DungeonTheme.DREAM_PALACE,
        DungeonTheme.VOID_TEMPLE,
        DungeonTheme.ABYSSAL_DEPTHS
    ]

    ROOM_TYPES = {
        RoomType.COMBAT: 0.35,
        RoomType.TREASURE: 0.12,
        RoomType.PUZZLE: 0.18,
        RoomType.REST: 0.08,
        RoomType.EVENT: 0.15,
        RoomType.TRAP: 0.08,
        RoomType.BOSS: 0.04
    }

    def __init__(self):
        self.generation_seed = None
        self.procedural_rules = ProceduralRuleEngine()
        self.ai_storyteller = AI_Storyteller()
        self.dynamic_npc_generator = IntelligentNPCSystem()
        self._theme_descriptions = self._load_theme_descriptions()

    def _load_theme_descriptions(self) -> Dict[str, Dict]:
        """加载主题描述"""
        return {
            "ancient_crypt": {
                "atmosphere": "阴暗潮湿，充满腐朽气息",
                "common_monsters": ["骷髅兵", "僵尸", "幽灵"],
                "special_features": ["墓碑", "石棺", "古老符文"],
                "story_hints": ["失落文明的墓葬", "被诅咒的贵族"]
            },
            "magic_academy": {
                "atmosphere": "魔法能量涌动，书架林立",
                "common_monsters": ["魔法学徒", "被激活的构装体", "魔法傀儡"],
                "special_features": ["魔法书", "实验台", "悬浮水晶"],
                "story_hints": ["禁忌的魔法实验", "失踪的教授"]
            },
            "abandoned_mine": {
                "atmosphere": "狭窄矿道，矿车轨道延伸",
                "common_monsters": ["矿工幽灵", "洞穴蜘蛛", "矿晶怪"],
                "special_features": ["矿石", "矿车", "炸药桶"],
                "story_hints": ["废弃的金矿", "矿难真相"]
            },
            "demon_forge": {
                "atmosphere": "灼热地狱，火焰永恒燃烧",
                "common_monsters": ["恶魔锻造师", "火焰精灵", "地狱犬"],
                "special_features": ["熔岩池", "锻造炉", "恶魔雕塑"],
                "story_hints": ["地狱的武器工坊", "恶魔王子的阴谋"]
            },
            "celestial_prison": {
                "atmosphere": "神圣光芒，洁白大理石",
                "common_monsters": ["堕落天使", "神圣守卫", "光之傀儡"],
                "special_features": ["光柱", "天使雕像", "神圣符文"],
                "story_hints": ["囚禁神明的监狱", "光的真相"]
            },
            "clockwork_city": {
                "atmosphere": "齿轮转动，机械律动",
                "common_monsters": ["齿轮怪", "发条士兵", "发条猎犬"],
                "special_features": ["巨大齿轮", "发条装置", "蒸汽管道"],
                "story_hints": ["永动机城市", "失控的造物"]
            },
            "living_forest": {
                "atmosphere": "参天大树，藤蔓缠绕",
                "common_monsters": ["树人", "藤蔓怪", "森林精灵"],
                "special_features": ["古树", "魔法蘑菇", "精灵花园"],
                "story_hints": ["古老森林的意识", "自然的愤怒"]
            },
            "dream_palace": {
                "atmosphere": "超现实空间，扭曲现实",
                "common_monsters": ["梦魇", "记忆投影", "虚影"],
                "special_features": ["漂浮阶梯", "镜子房间", "时间沙漏"],
                "story_hints": ["梦境的中心", "清醒梦的秘密"]
            },
            "void_temple": {
                "atmosphere": "虚空漆黑，星光点缀",
                "common_monsters": ["虚影", "虚空行者", "星尘守护者"],
                "special_features": ["悬浮平台", "星空穹顶", "黑洞"],
                "story_hints": ["宇宙的神殿", "虚空的召唤"]
            },
            "abyssal_depths": {
                "atmosphere": "深海高压，黑暗未知",
                "common_monsters": ["深海巨兽", "灯笼鱼", "克拉肯触须"],
                "special_features": ["发光水母", "沉船残骸", "珊瑚礁"],
                "story_hints": ["海底的失落文明", "深渊的呼唤"]
            }
        }

    async def generate_dungeon_layer(self, layer_depth: int,
                                      party_size: int = 1,
                                      seed: Optional[int] = None) -> DungeonLayer:
        """生成地牢层"""
        self.generation_seed = seed or random.randint(0, 99999999)
        random.seed(self.generation_seed)

        # 1. 选择主题
        theme = await self.select_theme(layer_depth)

        # 2. 生成地图布局
        layout = await self.generate_layout(theme, party_size)

        # 3. 生成房间
        rooms = await self.generate_rooms(layout, theme)

        # 4. 生成走廊连接
        corridors = await self.generate_corridors(layout)

        # 5. 生成怪物
        monsters = await self.populate_monsters(theme, layer_depth, party_size)

        # 6. 生成NPC
        npcs = await self.generate_npcs(theme, layer_depth)

        # 7. 隐藏秘密
        secrets = await self.hide_secrets(theme, layer_depth, layout)

        # 8. 设计Boss房间
        boss = await self.design_boss_room(layer_depth, theme)

        # 9. 计算难度
        difficulty = await self.calculate_difficulty(layer_depth)

        # 10. 生成环境故事
        environment_story = await self.ai_storyteller.create_environment_story(theme, layer_depth)

        # 11. 动态事件
        dynamic_events = await self.generate_dynamic_events(theme, layer_depth)

        # 12. 主线剧情
        main_story = None
        if layer_depth % 5 == 0:
            main_story = await self.generate_story_arc(layer_depth, theme)

        dungeon = DungeonLayer(
            layer_id=f"layer_{layer_depth}_{uuid.uuid4().hex[:8]}",
            depth=layer_depth,
            theme=theme,
            difficulty=difficulty,
            rooms=rooms,
            corridors=corridors,
            monsters=monsters,
            npcs=npcs,
            secrets=secrets,
            boss=boss,
            dynamic_events=dynamic_events,
            main_story=main_story,
            environment_story=environment_story
        )

        return dungeon

    async def select_theme(self, layer_depth: int) -> DungeonTheme:
        """根据层深选择主题"""
        if layer_depth <= 3:
            available_themes = [DungeonTheme.ANCIENT_CRYPT, DungeonTheme.ABANDONED_MINE]
        elif layer_depth <= 7:
            available_themes = [DungeonTheme.MAGIC_ACADEMY, DungeonTheme.LIVING_FOREST, DungeonTheme.CLOCKWORK_CITY]
        elif layer_depth <= 12:
            available_themes = [DungeonTheme.DEMON_FORGE, DungeonTheme.DREAM_PALACE, DungeonTheme.CELESTIAL_PRISON]
        else:
            available_themes = [DungeonTheme.VOID_TEMPLE, DungeonTheme.ABYSSAL_DEPTHS]

        return random.choice(available_themes)

    async def generate_layout(self, theme: DungeonTheme, party_size: int) -> Dict:
        """生成地牢布局"""
        base_rooms = 8 + party_size * 2
        width = 10 + party_size
        height = 8 + party_size

        layout = {
            "width": width,
            "height": height,
            "rooms": {},
            "connections": {},
            "grid": [[None for _ in range(width)] for _ in range(height)]
        }

        # 生成房间位置
        room_count = min(base_rooms, width * height // 4)
        placed_rooms = 0
        attempts = 0

        while placed_rooms < room_count and attempts < 100:
            attempts += 1
            room_width = random.randint(2, 4)
            room_height = random.randint(2, 3)
            x = random.randint(0, width - room_width)
            y = random.randint(0, height - room_height)

            # 检查是否与现有房间重叠
            overlap = False
            for rx in range(x - 1, x + room_width + 1):
                for ry in range(y - 1, y + room_height + 1):
                    if 0 <= rx < width and 0 <= ry < height:
                        if layout["grid"][ry][rx] is not None:
                            overlap = True
                            break

            if not overlap:
                room_id = f"room_{placed_rooms}"
                center_x = x + room_width // 2
                center_y = y + room_height // 2
                layout["rooms"][room_id] = {"x": center_x, "y": center_y}
                layout["connections"][room_id] = []
                for rx in range(x, x + room_width):
                    for ry in range(y, y + room_height):
                        layout["grid"][ry][rx] = room_id
                placed_rooms += 1

        return layout

    async def generate_rooms(self, layout: Dict, theme: DungeonTheme) -> List[Room]:
        """生成房间"""
        rooms = []

        for room_id, pos in layout["rooms"].items():
            # 随机房间类型
            room_type = await self.weighted_random(self.ROOM_TYPES)

            room = Room(
                room_id=room_id,
                room_type=room_type,
                position=Position(pos["x"], pos["y"]),
                theme=theme,
                contents=await self.generate_room_contents(room_type, theme),
                connections=layout["connections"].get(room_id, []),
                secret_doors=[],
                environment_effects=await self.generate_environment_effects(theme, room_type),
                story=await self.ai_storyteller.create_room_story(theme, room_type, room_id),
                discovered=False,
                cleared=False
            )

            # 特殊房间
            if room_type == RoomType.TREASURE:
                room.contents["chest"] = await self.generate_treasure(theme)
            elif room_type == RoomType.PUZZLE:
                room.contents["puzzle"] = await self.generate_room_puzzle(theme)

            rooms.append(room)

        # 生成房间连接
        await self.connect_rooms(layout, rooms)

        # 生成密门
        await self.add_secret_doors(rooms, theme)

        return rooms

    async def connect_rooms(self, layout: Dict, rooms: List[Room]):
        """连接房间"""
        room_ids = list(layout["rooms"].keys())

        for i, room_id in enumerate(room_ids):
            if i + 1 < len(room_ids):
                next_room = room_ids[i + 1]
                layout["connections"][room_id].append(next_room)
                layout["connections"][next_room].append(room_id)

        # 更新房间的连接信息
        for room in rooms:
            room.connections = layout["connections"].get(room.room_id, [])

    async def add_secret_doors(self, rooms: List[Room], theme: DungeonTheme):
        """添加密门"""
        for room in rooms:
            if random.random() < 0.15:  # 15%几率有密门
                room.secret_doors.append(f"secret_{room.room_id}_{uuid.uuid4().hex[:4]}")

    async def generate_room_contents(self, room_type: RoomType, theme: DungeonTheme) -> Dict:
        """生成房间内容"""
        contents = {}

        if room_type == RoomType.COMBAT:
            contents["enemy_count"] = random.randint(1, 3)
            contents["elite_chance"] = random.random() * 0.3
        elif room_type == RoomType.TREASURE:
            contents["chest_locked"] = random.random() < 0.7
            contents["chest_trap"] = random.random() < 0.4
        elif room_type == RoomType.PUZZLE:
            contents["puzzle_difficulty"] = random.uniform(0.3, 0.9)
        elif room_type == RoomType.REST:
            contents["healing_fountain"] = random.random() < 0.5
            contents["merchant"] = random.random() < 0.3
        elif room_type == RoomType.EVENT:
            contents["event_type"] = random.choice(["treasure_find", "ambush", "npc_encounter", "choice"])

        return contents

    async def generate_environment_effects(self, theme: DungeonTheme, room_type: RoomType) -> List[str]:
        """生成环境效果"""
        effects = []
        theme_name = theme.value

        if theme_name == "demon_forge":
            effects.append("火焰伤害: 每回合10点火焰伤害")
        elif theme_name == "celestial_prison":
            effects.append("神圣祝福: 治疗效果+50%")
        elif theme_name == "void_temple":
            effects.append("虚空侵蚀: 技能冷却+2秒")
        elif theme_name == "abyssal_depths":
            effects.append("水压: 最大生命值-20%")

        if room_type == RoomType.TRAP:
            effects.append("陷阱触发: 随机负面效果")

        return effects

    async def generate_treasure(self, theme: DungeonTheme) -> Dict:
        """生成宝箱"""
        rarity_roll = random.random()
        if rarity_roll < 0.6:
            rarity = ItemRarity.COMMON
        elif rarity_roll < 0.85:
            rarity = ItemRarity.UNCOMMON
        elif rarity_roll < 0.95:
            rarity = ItemRarity.RARE
        else:
            rarity = ItemRarity.EPIC

        return {
            "rarity": rarity,
            "gold_range": (int(50 * rarity.value_mult), int(200 * rarity.value_mult))
        }

    async def generate_room_puzzle(self, theme: DungeonTheme) -> Dict:
        """生成房间谜题"""
        puzzle_types = list(PuzzleType)

        return {
            "puzzle_type": random.choice(puzzle_types),
            "difficulty": random.uniform(0.3, 0.9),
            "attempts": 0,
            "solved": False
        }

    async def populate_monsters(self, theme: DungeonTheme, depth: int,
                                party_size: int) -> List[NPC]:
        """填充怪物"""
        monsters = []
        monster_count = 3 + depth // 3 + party_size

        theme_desc = self._theme_descriptions.get(theme.value, {})
        monster_names = theme_desc.get("common_monsters", ["怪物"])

        for i in range(monster_count):
            monster = await self.dynamic_npc_generator.generate_dungeon_npc(
                theme=theme.value,
                depth=depth,
                role="enemy"
            )
            monster.name = random.choice(monster_names)
            monsters.append(monster)

        return monsters

    async def generate_npcs(self, theme: DungeonTheme, depth: int) -> List[NPC]:
        """生成NPC"""
        npcs = []

        # 商人
        if random.random() < 0.3:
            merchant = await self.dynamic_npc_generator.generate_dungeon_npc(
                theme=theme.value,
                depth=depth,
                role="merchant"
            )
            merchant.name = "流浪商人"
            merchant.dialogue = [
                "旅者，要看看我的货物吗？",
                "这些可都是好东西，错过就没了。"
            ]
            npcs.append(merchant)

        # 任务给予者
        if random.random() < 0.4:
            quest_giver = await self.dynamic_npc_generator.generate_dungeon_npc(
                theme=theme.value,
                depth=depth,
                role="quest_giver"
            )
            quest_giver.name = "迷途的魂魄"
            quest_giver.dialogue = [
                "你能帮我找到...回家的路吗？"
            ]
            npcs.append(quest_giver)

        return npcs

    async def hide_secrets(self, theme: DungeonTheme, depth: int,
                          layout: Dict) -> List[Secret]:
        """隐藏秘密"""
        secrets = []
        secret_count = 2 + depth // 5

        for i in range(secret_count):
            room_ids = list(layout["rooms"].keys())
            if not room_ids:
                continue

            room_id = random.choice(room_ids)
            pos = layout["rooms"][room_id]

            secret_types = ["hidden_chest", "bonus_monster", "rare_material", "backstory"]
            secret = Secret(
                secret_id=f"secret_{uuid.uuid4().hex[:8]}",
                secret_type=random.choice(secret_types),
                location=Position(pos["x"], pos["y"]),
                hint=self._generate_secret_hint(theme),
                discovered=False
            )
            secrets.append(secret)

        return secrets

    def _generate_secret_hint(self, theme: DungeonTheme) -> str:
        """生成秘密提示"""
        hints = {
            "ancient_crypt": "石像鬼的眼睛在注视着你...",
            "magic_academy": "书架上的书摆放得不太整齐...",
            "abandoned_mine": "矿道的墙壁似乎有空鼓声...",
            "demon_forge": "熔岩的倒影中有什么在闪烁...",
            "clockwork_city": "某个齿轮转动得不太顺畅...",
            "living_forest": "古树的年轮似乎藏着什么...",
            "dream_palace": "镜子里的倒影不太一样...",
            "void_temple": "星空的某处似乎有异常的光点..."
        }
        return hints.get(theme.value, "仔细观察四周...")

    async def design_boss_room(self, depth: int, theme: DungeonTheme) -> Optional[NPC]:
        """设计Boss房间"""
        if depth % 5 != 0:  # 每5层有Boss
            return None

        boss = await self.dynamic_npc_generator.generate_dungeon_npc(
            theme=theme.value,
            depth=depth,
            role="boss"
        )

        boss.name = self._get_boss_name(theme, depth)
        boss.level = depth * 3
        boss.max_hp = depth * 500
        boss.hp = boss.max_hp
        boss.boss_mechanics = await self.dynamic_npc_generator.generate_boss_mechanics(depth, theme.value)
        boss.phases = await self.dynamic_npc_generator.generate_boss_phases(depth)

        return boss

    def _get_boss_name(self, theme: DungeonTheme, depth: int) -> str:
        """获取Boss名称"""
        boss_names = {
            "ancient_crypt": ["骷髅领主", "死亡骑士", "远古骸骨王"],
            "magic_academy": ["疯狂教授", "禁忌构装体", "魔法院长"],
            "demon_forge": ["地狱公爵", "炎魔领主", "锻造之王"],
            "celestial_prison": ["堕落天使长", "光辉破灭者", "天使审判者"],
            "clockwork_city": ["齿轮暴君", "发条皇帝", "永动核心"],
            "living_forest": ["森林噩梦", "古老树精", "自然之怒"],
            "dream_palace": ["梦魇之主", "清醒者", "梦境编织者"],
            "void_temple": ["虚空大君", "星神残骸", "虚无所生"]
        }

        names = boss_names.get(theme.value, ["未知Boss"])
        return random.choice(names)

    async def calculate_difficulty(self, layer_depth: int) -> float:
        """计算难度"""
        base = 1.0
        depth_mult = layer_depth * 0.15
        return min(base + depth_mult, 10.0)

    async def generate_dynamic_events(self, theme: DungeonTheme,
                                      depth: int) -> List[DynamicEvent]:
        """生成动态事件"""
        events = []

        # 怪物潮汐
        events.append(DynamicEvent(
            event_id=f"evt_{uuid.uuid4().hex[:8]}",
            event_type="monster_swarm",
            trigger="time_elapsed",
            chance=0.1 + depth * 0.02,
            effects={"monster_count": random.randint(3, 6)}
        ))

        # 环境变化
        events.append(DynamicEvent(
            event_id=f"evt_{uuid.uuid4().hex[:8]}",
            event_type="environment_change",
            trigger="room_entered",
            chance=0.15,
            effects={"new_effects": ["黑暗", "中毒", "滑倒"]}
        ))

        # AI生成特殊事件
        ai_events = await self.ai_storyteller.generate_special_events(theme.value, depth)
        events.extend(ai_events)

        return events

    async def generate_story_arc(self, depth: int, theme: DungeonTheme) -> StoryArc:
        """生成故事弧"""
        story_templates = {
            "ancient_crypt": {
                "title": "失落的王室",
                "description": "在古老的墓穴深处，埋葬着一位被遗忘的国王...",
                "objectives": ["找到王室祭坛", "收集三件圣物", "唤醒沉睡的王"]
            },
            "magic_academy": {
                "title": "禁忌的实验",
                "description": "魔法学院的地下室里，进行着不可告人的实验...",
                "objectives": ["获取实验记录", "阻止失控的构装体", "封印时空裂缝"]
            },
            "demon_forge": {
                "title": "地狱的阴谋",
                "description": "恶魔们正在打造一件足以毁灭世界的神器...",
                "objectives": ["摧毁锻造图纸", "击败首席锻造师", "阻止神器完成"]
            }
        }

        template = story_templates.get(theme.value, story_templates["ancient_crypt"])

        return StoryArc(
            arc_id=f"arc_{uuid.uuid4().hex[:8]}",
            title=template["title"],
            description=template["description"],
            objectives=template["objectives"],
            rewards={"credits": depth * 500, "items": ["legendary_weapon"]},
            completed=False
        )

    async def weighted_random(self, weights: Dict[Any, float]) -> Any:
        """加权随机选择"""
        items = list(weights.keys())
        probs = list(weights.values())
        return random.choices(items, weights=probs, k=1)[0]


# ==================== 程序化规则引擎 ====================

class ProceduralRuleEngine:
    """程序化规则引擎"""

    def __init__(self):
        self.rules = self._load_rules()

    def _load_rules(self) -> Dict:
        """加载规则"""
        return {
            "room_density": {"min": 5, "max": 20, "default": 10},
            "corridor_length": {"min": 1, "max": 5, "default": 2},
            "secret_probability": 0.15,
            "treasure_value_mult": 1.0,
            "monster_scaling": 0.1
        }

    def apply_rules(self, context: Dict) -> Dict:
        """应用规则"""
        result = context.copy()

        # 房间密度
        if "party_size" in context:
            result["room_count"] = min(
                self.rules["room_density"]["max"],
                self.rules["room_density"]["default"] + context["party_size"]
            )

        return result


# ==================== AI叙事导演 ====================

class AI_Storyteller:
    """AI叙事导演系统"""

    def __init__(self):
        self.story_templates = self._load_story_templates()
        self.narrative_arcs = self._load_narrative_arcs()

    def _load_story_templates(self) -> Dict:
        """加载故事模板"""
        return {
            "room_stories": {
                "combat": [
                    "这里发生过激烈的战斗，墙壁上还留着战斗的痕迹...",
                    "地上散落着武器碎片，似乎是一场恶战...",
                    "空气中弥漫着血腥味，令人生畏..."
                ],
                "treasure": [
                    "闪闪发光的金币从宝箱中溢出...",
                    "宝物散发着你从未见过的光芒...",
                    "这里似乎藏着重大的秘密..."
                ],
                "puzzle": [
                    "古老的机关静静地等待着能解开它的人...",
                    "墙上的符文闪烁着神秘的光芒...",
                    "这个房间似乎隐藏着智慧的考验..."
                ],
                "rest": [
                    "篝火在角落里静静地燃烧...",
                    "清泉从石缝中流出，带来一丝宁静...",
                    "这里是一个难得的安宁之所..."
                ],
                "event": [
                    "命运的齿轮在这里悄然转动...",
                    "一个意想不到的相遇即将发生...",
                    "某种力量正在改变着一切..."
                ]
            },
            "boss_intros": [
                "{boss_name} 出现在你面前，双眼燃烧着复仇的火焰！",
                "空气中充斥着 {boss_name} 的咆哮！",
                "{boss_name} 从阴影中现身，等待已久..."
            ]
        }

    def _load_narrative_arcs(self) -> Dict:
        """加载叙事弧"""
        return {
            "betrayal": {
                "trigger": "player_suspicion > 0.7",
                "event": "reveal_traitor",
                "dramatic_timing": "climax"
            },
            "redemption": {
                "trigger": "player_morale < 0.3",
                "event": "unexpected_ally",
                "dramatic_timing": "low_point"
            },
            "twist": {
                "trigger": "puzzle_solved_count > 3",
                "event": "identity_swap",
                "dramatic_timing": "midpoint"
            },
            "sacrifice": {
                "trigger": "time_remaining < 0.2",
                "event": "heroic_sacrifice",
                "dramatic_timing": "climax"
            }
        }

    async def create_environment_story(self, theme: DungeonTheme, depth: int) -> str:
        """创建环境故事"""
        theme_stories = {
            "ancient_crypt": f"第{depth}层 - 古老的墓穴中回荡着亡者的低语...",
            "magic_academy": f"第{depth}层 - 魔法的残余能量在空中舞动...",
            "abandoned_mine": f"第{depth}层 - 废弃的矿道中传来金属的回响...",
            "demon_forge": f"第{depth}层 - 地狱之火永不熄灭...",
            "celestial_prison": f"第{depth}层 - 被囚禁的神明仍在祈祷...",
            "clockwork_city": f"第{depth}层 - 齿轮的咔嗒声永不停歇...",
            "living_forest": f"第{depth}层 - 古树的根系深入地下...",
            "dream_palace": f"第{depth}层 - 梦境与现实的边界模糊不清...",
            "void_temple": f"第{depth}层 - 虚空中隐藏着宇宙的秘密...",
            "abyssal_depths": f"第{depth}层 - 深渊之下还有深渊..."
        }
        return theme_stories.get(theme.value, f"第{depth}层 - 未知之地...")

    async def create_room_story(self, theme: DungeonTheme, room_type: RoomType, room_id: str) -> str:
        """创建房间故事"""
        stories = self.story_templates["room_stories"].get(room_type.value, ["这里充满神秘..."])
        return random.choice(stories)

    async def generate_special_events(self, theme: str, depth: int) -> List[DynamicEvent]:
        """生成特殊事件"""
        events = []

        special_events = [
            {
                "type": "mysterious_merchant",
                "trigger": "random",
                "chance": 0.05,
                "effects": {"merchant_appears": True}
            },
            {
                "type": "ancient_awakening",
                "trigger": "combat_end",
                "chance": 0.1,
                "effects": {"awakened": True}
            },
            {
                "type": "treasure_blessing",
                "trigger": "treasure_opened",
                "chance": 0.2,
                "effects": {"blessing": "lucky"}
            }
        ]

        for event_data in special_events:
            if random.random() < event_data["chance"]:
                events.append(DynamicEvent(
                    event_id=f"evt_{uuid.uuid4().hex[:8]}",
                    event_type=event_data["type"],
                    trigger=event_data["trigger"],
                    chance=event_data["chance"],
                    effects=event_data["effects"]
                ))

        return events

    async def generate_boss_intro(self, boss_name: str) -> str:
        """生成Boss介绍"""
        template = random.choice(self.story_templates["boss_intros"])
        return template.format(boss_name=boss_name)


# ==================== 智能NPC系统 ====================

class IntelligentNPCSystem:
    """智能NPC与怪物系统"""

    def __init__(self):
        self.npc_templates = NPCTemplateLibrary()
        self.ai_behavior = AIBehaviorEngine()
        self.dialogue_system = AIDialogueSystem()
        self._stats_cache = {}

    async def generate_dungeon_npc(self, theme: str, depth: int,
                                   role: str = "enemy") -> NPC:
        """生成地牢NPC"""

        # 基础属性
        npc_base = await self.npc_templates.get_template(theme, role)

        # 动态属性
        dynamic_stats = await self.calculate_dynamic_stats(depth, role)

        level = depth * 2 + random.randint(1, 5)

        npc = NPC(
            npc_id=f"npc_{uuid.uuid4().hex[:8]}",
            name=f"{theme}_{role}_{uuid.uuid4().hex[:4]}",
            role=role,
            level=level,
            stats={**npc_base.get("stats", {}), **dynamic_stats},
            abilities=await self.generate_abilities(theme, role, depth),
            ai_behavior=await self.ai_behavior.generate_behavior(role, theme),
            dialogue=await self.dialogue_system.generate_dialogue(theme, role),
            loot_table=await self.generate_loot_table(depth, role),
            visual_appearance=await self.generate_visual_appearance(theme, role),
            backstory=await self.generate_backstory(theme, role, depth),
            quests=[] if role != "enemy" else [],
            alive=True,
            hp=dynamic_stats.get("hp", level * 100),
            max_hp=dynamic_stats.get("hp", level * 100)
        )

        return npc

    async def calculate_dynamic_stats(self, depth: int, role: str) -> Dict[str, int]:
        """计算动态属性"""
        base_stats = {
            "hp": depth * 100,
            "attack": depth * 10 + 5,
            "defense": depth * 5 + 2,
            "speed": depth * 2 + 10,
            "magic": depth * 8 + 3
        }

        if role == "boss":
            for key in base_stats:
                base_stats[key] = int(base_stats[key] * 2.5)

        return base_stats

    async def generate_abilities(self, theme: str, role: str, depth: int) -> List[str]:
        """生成能力"""
        common_abilities = ["普通攻击", "防御姿态"]
        special_abilities = []

        if role == "enemy":
            special_abilities = [
                "重击", "顺劈", "嘲讽", "冲锋", "怒吼",
                "闪避", "反击", "吸血", "再生"
            ]
        elif role == "boss":
            special_abilities = [
                "终极毁灭", "地狱之门", "神圣审判", "时间静止",
                "分身术", "元素爆发", "战吼"
            ]
        elif role == "merchant":
            special_abilities = ["交易", "鉴定", "修复"]

        ability_count = min(3 + depth // 5, 6)
        return common_abilities + random.sample(special_abilities, min(ability_count, len(special_abilities)))

    async def generate_loot_table(self, depth: int, role: str) -> List[Tuple[str, float]]:
        """生成掉落表"""
        loot_table = []

        base_drops = [
            ("gold", 0.8),
            ("common_material", 0.5),
            ("uncommon_material", 0.3)
        ]

        if role == "boss":
            base_drops.extend([
                ("rare_item", 0.7),
                ("epic_item", 0.4),
                ("legendary_item", 0.1)
            ])

        return base_drops

    async def generate_visual_appearance(self, theme: str, role: str) -> Dict[str, str]:
        """生成外观描述"""
        appearances = {
            "enemy": {
                "body": "人形/兽形",
                "color": "暗色调",
                "features": "狰狞的面容"
            },
            "boss": {
                "body": "巨大化人形",
                "color": "深红色/紫色",
                "features": "王冠/翅膀/光环"
            },
            "merchant": {
                "body": "人形",
                "color": "棕色/金色",
                "features": "商人帽/背包"
            }
        }

        return appearances.get(role, appearances["enemy"])

    async def generate_backstory(self, theme: str, role: str, depth: int) -> str:
        """生成背景故事"""
        backstories = [
            f"来自{theme}的古老存在，已经在这里守护了千年...",
            f"曾经是英勇的战士，如今被黑暗力量侵蚀...",
            f"被囚禁在此，等待着能够解救它的人..."
        ]
        return random.choice(backstories)

    async def generate_boss_mechanics(self, depth: int, theme: str) -> Dict:
        """生成Boss机制"""
        mechanics_pool = {
            "phase_transition": {
                "description": "血量到一定百分比转换形态",
                "phases": ["激怒", "狂暴", "毁灭"],
                "transition_triggers": [0.7, 0.3]
            },
            "environment_interaction": {
                "description": "Boss与场景互动",
                "interactable_objects": ["石柱", "水晶", "陷阱"],
                "destruction_effects": ["治疗", "激怒", "召唤"]
            },
            "player_debuff": {
                "description": "给玩家添加减益效果",
                "debuffs": ["诅咒", "减速", "持续伤害"],
                "application_method": "aoe"
            },
            "add_spawning": {
                "description": "召唤小怪",
                "spawn_triggers": ["时间", "血量", "阶段"],
                "add_types": ["小怪", "精英", "治疗者"]
            }
        }

        selected = random.sample(list(mechanics_pool.items()),
                                random.randint(2, 3))
        return dict(selected)

    async def generate_boss_phases(self, depth: int) -> List[Dict]:
        """生成Boss阶段"""
        phases = []

        for i, trigger in enumerate([0.7, 0.3]):
            phase = {
                "phase_id": i + 1,
                "trigger_hp": trigger,
                "abilities": [f"phase_{i+1}_ability_{j}" for j in range(2)],
                "stat_mult": 1.0 + i * 0.3,
                "new_mechanics": i > 0
            }
            phases.append(phase)

        return phases


# ==================== NPC模板库 ====================

class NPCTemplateLibrary:
    """NPC模板库"""

    def __init__(self):
        self.templates = self._load_templates()

    def _load_templates(self) -> Dict:
        """加载模板"""
        return {
            "enemy": {
                "stats": {"hp": 100, "attack": 10, "defense": 5, "speed": 10},
                "abilities": ["普通攻击"]
            },
            "elite": {
                "stats": {"hp": 250, "attack": 20, "defense": 12, "speed": 15},
                "abilities": ["普通攻击", "重击"]
            },
            "boss": {
                "stats": {"hp": 1000, "attack": 50, "defense": 30, "speed": 20},
                "abilities": ["普通攻击", "特殊攻击"]
            },
            "merchant": {
                "stats": {"hp": 50, "attack": 0, "defense": 0, "speed": 5},
                "abilities": ["交易"]
            },
            "quest_giver": {
                "stats": {"hp": 30, "attack": 0, "defense": 0, "speed": 5},
                "abilities": ["任务"]
            }
        }

    async def get_template(self, theme: str, role: str) -> Dict:
        """获取模板"""
        return self.templates.get(role, self.templates["enemy"])


# ==================== AI行为引擎 ====================

class AIBehaviorEngine:
    """AI行为引擎"""

    def __init__(self):
        self.behaviors = self._load_behaviors()

    def _load_behaviors(self) -> Dict:
        """加载行为"""
        return {
            "aggressive": {
                "attack_chance": 0.8,
                "preferred_actions": ["attack", "charge", "berserk"],
                "target_selection": "weakest"
            },
            "defensive": {
                "attack_chance": 0.4,
                "preferred_actions": ["defend", "retreat", "heal"],
                "target_selection": "self"
            },
            "cunning": {
                "attack_chance": 0.6,
                "preferred_actions": ["ambush", "trap", "retreat"],
                "target_selection": "random"
            },
            "balanced": {
                "attack_chance": 0.5,
                "preferred_actions": ["attack", "defend", "special"],
                "target_selection": "nearest"
            }
        }

    async def generate_behavior(self, role: str, theme: str) -> Dict:
        """生成AI行为"""
        if role == "boss":
            return self.behaviors["aggressive"].copy()
        elif role == "elite":
            return random.choice([self.behaviors["aggressive"], self.behaviors["cunning"]])
        else:
            return random.choice(list(self.behaviors.values()))


# ==================== AI对话系统 ====================

class AIDialogueSystem:
    """AI对话系统"""

    def __init__(self):
        self.dialogues = self._load_dialogues()

    def _load_dialogues(self) -> Dict:
        """加载对话"""
        return {
            "enemy": [
                "给我滚出去！",
                "你的灵魂属于我！",
                "又是一个送死的..."
            ],
            "merchant": [
                "旅者，要看看我的货物吗？",
                "好东西都在这里了！",
                "今天运气不错，找到了稀有物品..."
            ],
            "quest_giver": [
                "帮帮我，旅者...",
                "我有一个任务想委托你...",
                "只有你才能完成这件事..."
            ]
        }

    async def generate_dialogue(self, theme: str, role: str) -> List[str]:
        """生成对话"""
        return self.dialogues.get(role, ["..."])


# ==================== 智能战利品系统 ====================

class SmartLootSystem:
    """智能战利品系统"""

    def __init__(self):
        self.item_generator = ItemGenerator()
        self.economy_balancer = EconomyBalancer()
        self._daily_earnings = defaultdict(int)

    async def generate_boss_loot(self, boss_level: int, party_size: int,
                                 difficulty: float) -> Dict:
        """生成Boss战利品"""

        loot = {
            "credits": 0,
            "items": [],
            "materials": [],
            "recipes": [],
            "cosmetics": [],
            "special_rewards": []
        }

        # 计算积分奖励
        loot["credits"] = await self.calculate_credit_reward(
            boss_level, difficulty, party_size
        )

        # 基础掉落
        base_items = await self.generate_base_items(boss_level)
        loot["items"].extend(base_items)

        # 稀有掉落
        if random.random() < 0.3:
            rare_item = await self.generate_rare_item(boss_level)
            loot["items"].append(rare_item)

        # 传奇掉落
        if random.random() < 0.1:
            legendary_item = await self.generate_legendary_item(boss_level)
            loot["items"].append(legendary_item)

        # 材料
        loot["materials"] = await self.generate_materials(boss_level, difficulty)

        # 配方
        if random.random() < 0.15:
            recipe = await self.generate_recipe(boss_level)
            loot["recipes"].append(recipe)

        # 外观
        if random.random() < 0.05:
            cosmetic = await self.generate_cosmetic(boss_level)
            loot["cosmetics"].append(cosmetic)

        return loot

    async def calculate_credit_reward(self, level: int, difficulty: float,
                                       party_size: int) -> int:
        """计算积分奖励"""
        base_reward = level * 100
        difficulty_multiplier = 1.0 + (difficulty - 1) * 0.5
        party_multiplier = 1.0 / party_size

        calculated = int(base_reward * difficulty_multiplier * party_multiplier)

        # 每日上限
        daily_limit = 20000
        return min(calculated, daily_limit)

    async def generate_base_items(self, level: int) -> List[Item]:
        """生成基础物品"""
        items = []
        item_count = random.randint(2, 5)

        for i in range(item_count):
            item = await self.item_generator.generate_item(
                rarity=ItemRarity.COMMON,
                level=level
            )
            items.append(item)

        return items

    async def generate_rare_item(self, level: int) -> Item:
        """生成稀有物品"""
        return await self.item_generator.generate_item(
            rarity=ItemRarity.RARE,
            level=level
        )

    async def generate_legendary_item(self, level: int) -> Item:
        """生成传奇物品"""
        return await self.item_generator.generate_item(
            rarity=ItemRarity.LEGENDARY,
            level=level
        )

    async def generate_materials(self, level: int, difficulty: float) -> List[Item]:
        """生成材料"""
        materials = []
        material_count = random.randint(1, 4)

        for i in range(material_count):
            material = Item(
                item_id=f"mat_{uuid.uuid4().hex[:8]}",
                name=f"强化材料Lv{level}",
                item_type="material",
                rarity=ItemRarity.COMMON,
                value=int(20 * difficulty),
                stackable=True,
                quantity=random.randint(1, 5)
            )
            materials.append(material)

        return materials

    async def generate_recipe(self, level: int) -> Dict:
        """生成配方"""
        return {
            "recipe_id": f"recipe_{uuid.uuid4().hex[:8]}",
            "name": f"史诗配方Lv{level}",
            "required_materials": ["material_1", "material_2"],
            "result": "legendary_weapon"
        }

    async def generate_cosmetic(self, level: int) -> Dict:
        """生成外观物品"""
        return {
            "cosmetic_id": f"cosmetic_{uuid.uuid4().hex[:8]}",
            "name": f"稀有外观Lv{level}",
            "type": random.choice(["skin", "effect", "trail"])
        }


# ==================== 物品生成器 ====================

class ItemGenerator:
    """物品生成器"""

    WEAPON_TYPES = ["剑", "斧", "锤", "弓", "法杖", "匕首"]
    ARMOR_TYPES = ["头盔", "胸甲", "护腿", "护靴", "护腕", "盾牌"]

    ITEM_PREFIXES = {
        ItemRarity.COMMON: ["普通的", "破旧的"],
        ItemRarity.UNCOMMON: ["精良的", "坚固的"],
        ItemRarity.RARE: ["稀有的", "魔法加持的"],
        ItemRarity.EPIC: ["史诗级的", "传说碎片的"],
        ItemRarity.LEGENDARY: ["传奇的", "神圣的"]
    }

    async def generate_item(self, rarity: ItemRarity, level: int) -> Item:
        """生成物品"""
        is_weapon = random.random() < 0.5

        if is_weapon:
            base_type = random.choice(self.WEAPON_TYPES)
            item_type = "weapon"
        else:
            base_type = random.choice(self.ARMOR_TYPES)
            item_type = "armor"

        prefix = random.choice(self.ITEM_PREFIXES[rarity])
        name = f"{prefix}{base_type}"

        stats = await self.generate_item_stats(item_type, rarity, level)

        return Item(
            item_id=f"item_{uuid.uuid4().hex[:8]}",
            name=name,
            item_type=item_type,
            rarity=rarity,
            value=int(level * 10 * rarity.value_mult),
            stats=stats,
            description=f"一件{name}，散发着{rarity.name}的光芒。"
        )

    async def generate_item_stats(self, item_type: str, rarity: ItemRarity,
                                  level: int) -> Dict[str, int]:
        """生成物品属性"""
        stats = {}

        if item_type == "weapon":
            stats["attack"] = int(level * 5 * rarity.value_mult)
            if random.random() < 0.3 * rarity.value_mult:
                stats["crit_chance"] = int(random.uniform(5, 15) * rarity.value_mult)
        else:
            stats["defense"] = int(level * 3 * rarity.value_mult)
            if random.random() < 0.3 * rarity.value_mult:
                stats["hp"] = int(level * 20 * rarity.value_mult)

        return stats


# ==================== 经济平衡器 ====================

class EconomyBalancer:
    """经济平衡器"""

    def __init__(self):
        self.economy_state = {
            "total_supply": 0,
            "total_demand": 0,
            "price_index": 1.0
        }

    async def adjust_economy(self, transaction_type: str, amount: int) -> float:
        """调整经济"""
        if transaction_type == "add":
            self.economy_state["total_supply"] += amount
        else:
            self.economy_state["total_demand"] += amount

        # 计算价格指数
        if self.economy_state["total_demand"] > 0:
            self.economy_state["price_index"] = (
                self.economy_state["total_supply"] /
                self.economy_state["total_demand"]
            )

        return self.economy_state["price_index"]


# ==================== 地牢狼人杀融合系统 ====================

class DungeonWerewolf:
    """地牢狼人杀融合系统"""

    ROLES = {
        "villager": {"team": "innocent", "abilities": ["vote"]},
        "werewolf": {"team": "werewolf", "abilities": ["kill_night", "vote"]},
        "seer": {"team": "innocent", "abilities": ["check_role", "vote"]},
        "guardian": {"team": "innocent", "abilities": ["protect", "vote"]},
        "hunter": {"team": "innocent", "abilities": ["shoot", "vote"]},
        "witch": {"team": "innocent", "abilities": ["heal", "poison", "vote"]},
        "fool": {"team": "neutral", "abilities": ["survive", "vote"]},
        "serial_killer": {"team": "neutral", "abilities": ["kill_night", "vote"]}
    }

    def __init__(self):
        self.ai_werewolf = AI_WerewolfBehavior()

    async def start_werewolf_game(self, dungeon_layer: DungeonLayer,
                                  player_count: int = 8) -> WerewolfGame:
        """在指定地牢层开始狼人杀"""

        # 1. 分配角色
        roles = await self.assign_roles(player_count)

        # 2. 准备地牢
        werewolf_dungeon = await self.prepare_werewolf_dungeon(
            dungeon_layer, player_count
        )

        # 3. 创建游戏
        game = WerewolfGame(
            game_id=f"ww_{uuid.uuid4().hex[:8]}",
            dungeon_layer=werewolf_dungeon,
            players={},
            phase=GamePhase.NIGHT,
            day_number=1,
            alive_players=player_count,
            chat_log=[],
            vote_history=[],
            kill_log=[],
            special_events=[]
        )

        # 4. 初始化玩家
        for i, (player_id, role) in enumerate(roles.items()):
            role_info = self.ROLES.get(role, self.ROLES["villager"])
            player = Player(
                player_id=player_id,
                name=f"玩家{i+1}",
                role=role,
                team=role_info["team"],
                abilities=role_info["abilities"],
                alive=True
            )
            game.players[player_id] = player

        return game

    async def assign_roles(self, player_count: int) -> Dict[str, str]:
        """分配角色"""
        role_pool = []

        # 根据玩家数量配置角色
        if player_count >= 8:
            role_pool = ["werewolf", "werewolf", "seer", "guardian", "witch", "hunter", "villager", "villager"]
        elif player_count >= 6:
            role_pool = ["werewolf", "seer", "guardian", "witch", "villager", "villager"]
        else:
            role_pool = ["werewolf", "seer", "villager", "villager", "villager"]

        # 填充村民
        while len(role_pool) < player_count:
            role_pool.append("villager")

        random.shuffle(role_pool)

        roles = {}
        for i in range(player_count):
            roles[f"player_{i}"] = role_pool[i]

        return roles

    async def prepare_werewolf_dungeon(self, base_dungeon: DungeonLayer,
                                        player_count: int) -> DungeonLayer:
        """准备狼人杀地牢"""
        werewolf_dungeon = base_dungeon

        # 修改地牢适应狼人杀
        werewolf_dungeon.rooms[0].contents["special_rules"] = {
            "lighting": "dim",
            "sound_propagation": 0.5,
            "vision_range": 3,
            "movement_noise": True,
            "hiding_spots": await self._generate_hiding_spots(player_count)
        }

        return werewolf_dungeon

    async def _generate_hiding_spots(self, player_count: int) -> List[str]:
        """生成藏身点"""
        spots = []
        for i in range(player_count // 2):
            spots.append(f"hiding_spot_{i}")
        return spots

    async def night_phase(self, game_id: str) -> Dict:
        """夜晚阶段"""
        # 狼人行动
        # 预言家行动
        # 守卫行动
        # 女巫行动

        return {
            "game_id": game_id,
            "day": 1,
            "night_actions": {},
            "results": {}
        }

    async def day_phase(self, game_id: str) -> Dict:
        """白天阶段"""
        return {
            "game_id": game_id,
            "day": 1,
            "deaths": [],
            "discussion": {},
            "votes": {}
        }


# ==================== AI狼人行为 ====================

class AI_WerewolfBehavior:
    """AI驱动的狼人行为"""

    def __init__(self):
        self.strategies = {
            "aggressive": {"kill_strong": 0.7, "frame_suspect": 0.3},
            "subtle": {"kill_weak": 0.6, "pretend_villager": 0.4},
            "chaotic": {"random_kill": 0.5, "create_confusion": 0.5}
        }

    async def simulate_ai_werewolf(self, werewolf_id: str, game: WerewolfGame) -> Dict:
        """模拟AI狼人行为"""

        # 分析局势
        analysis = await self.analyze_game_state(game, werewolf_id)

        # 选择策略
        strategy = await self.select_strategy(analysis)

        # 夜晚行动
        night_action = await self.plan_night_action(
            werewolf_id, game, strategy, analysis
        )

        # 白天行为
        day_behavior = await self.plan_day_behavior(
            werewolf_id, game, strategy, analysis
        )

        return {
            "werewolf_id": werewolf_id,
            "strategy": strategy,
            "night_action": night_action,
            "day_behavior": day_behavior,
            "suspected_targets": analysis.get("suspected_roles", {}),
            "allies": analysis.get("potential_allies", [])
        }

    async def analyze_game_state(self, game: WerewolfGame,
                                 werewolf_id: str) -> Dict:
        """分析游戏状态"""
        analysis = {
            "player_count": len([p for p in game.players.values() if p.alive]),
            "werewolf_count": len([p for p in game.players.values()
                                  if p.role == "werewolf" and p.alive]),
            "known_roles": {},
            "suspected_roles": {},
            "player_behaviors": {},
            "voting_patterns": {},
            "potential_allies": [],
            "threats": []
        }

        return analysis

    async def select_strategy(self, analysis: Dict) -> Dict:
        """选择策略"""
        if analysis["werewolf_count"] >= 3:
            return self.strategies["aggressive"]
        elif analysis["werewolf_count"] >= 2:
            return self.strategies["subtle"]
        else:
            return self.strategies["chaotic"]

    async def plan_night_action(self, werewolf_id: str, game: WerewolfGame,
                                strategy: Dict, analysis: Dict) -> Dict:
        """计划夜晚行动"""
        return {
            "action": "kill",
            "target": "random_villager",
            "reasoning": "击杀弱势玩家"
        }

    async def plan_day_behavior(self, werewolf_id: str, game: WerewolfGame,
                               strategy: Dict, analysis: Dict) -> Dict:
        """计划白天行为"""
        return {
            "speech": "质疑某人",
            "target": "suspect_1",
            "tone": "aggressive"
        }


# ==================== 智能谜题生成器 ====================

class EscapeRoomPuzzleGenerator:
    """智能密室逃脱谜题生成器"""

    def __init__(self):
        self.puzzle_types = {
            "logic": LogicPuzzleGenerator(),
            "pattern": PatternRecognitionGenerator(),
            "math": MathPuzzleGenerator(),
            "word": WordPuzzleGenerator(),
            "sequence": SequencePuzzleGenerator(),
            "spatial": SpatialPuzzleGenerator(),
            "cryptic": CrypticPuzzleGenerator(),
            "multistep": MultiStepPuzzleGenerator()
        }

    async def generate_escape_room(self, theme: DungeonTheme, difficulty: int,
                                   player_count: int) -> EscapeRoom:
        """生成密室逃脱"""

        escape_room = EscapeRoom(
            room_id=f"escape_{uuid.uuid4().hex[:8]}",
            theme=theme,
            difficulty=difficulty,
            time_limit=1800,
            puzzles=[],
            clues=[],
            red_herrings=[],
            environment=await self.generate_environment(theme),
            story=await self.generate_story(theme, difficulty),
            progression_gates=[],
            hidden_compartments=[],
            interactive_objects=[],
            escape_conditions=[]
        )

        # 生成谜题序列
        puzzle_count = min(5 + difficulty, 10)
        for i in range(puzzle_count):
            puzzle_type_name = random.choice(list(self.puzzle_types.keys()))
            puzzle_gen = self.puzzle_types[puzzle_type_name]

            puzzle = await puzzle_gen.generate_puzzle(
                difficulty=difficulty + i * 0.5,
                theme=theme.value
            )
            escape_room.puzzles.append(puzzle)

            # 添加线索
            if random.random() < 0.7:
                clue = await self.generate_clue(puzzle, theme, difficulty)
                escape_room.clues.append(clue)

            # 添加误导线索
            if random.random() < 0.3:
                red_herring = await self.generate_red_herring(puzzle, theme)
                escape_room.red_herrings.append(red_herring)

        # 生成最终谜题
        final_puzzle = await self.generate_final_puzzle(escape_room.puzzles, theme, difficulty)
        escape_room.progression_gates.append(final_puzzle.puzzle_id)

        # 生成逃脱条件
        escape_room.escape_conditions = await self.generate_escape_conditions(escape_room.puzzles)

        return escape_room

    async def generate_environment(self, theme: DungeonTheme) -> Dict:
        """生成环境"""
        environments = {
            "ancient_crypt": {
                "lighting": "torch",
                "ambient_sound": "wind",
                "temperature": "cold",
                "objects": ["石棺", "墓碑", "火把", "铁链"]
            },
            "magic_academy": {
                "lighting": "crystal",
                "ambient_sound": "magical hum",
                "temperature": "cool",
                "objects": ["书架", "实验台", "水晶球", "魔法书"]
            },
            "demon_forge": {
                "lighting": "lava",
                "ambient_sound": "hammering",
                "temperature": "hot",
                "objects": ["熔炉", "铁砧", "工具", "锁链"]
            }
        }
        return environments.get(theme, environments["ancient_crypt"])

    async def generate_story(self, theme: DungeonTheme, difficulty: int) -> str:
        """生成故事"""
        stories = {
            "ancient_crypt": "你被困在古老的墓穴中，必须在时限内找到出路...",
            "magic_academy": "魔法学院的地下室发生了意外，你必须在魔力耗尽前逃出...",
            "demon_forge": "恶魔锻造师将你囚禁，只有解开他的谜题才能获得自由..."
        }
        return stories.get(theme.value, "你被困在未知的空间中...")

    async def generate_clue(self, puzzle: Puzzle, theme: DungeonTheme,
                           difficulty: int) -> Clue:
        """生成线索"""
        clue_types = {
            "direct": 0.3,
            "indirect": 0.4,
            "cryptic": 0.2,
            "misleading": 0.1
        }

        clue_type = random.choices(
            list(clue_types.keys()),
            weights=list(clue_types.values())
        )[0]

        return Clue(
            clue_id=f"clue_{uuid.uuid4().hex[:8]}",
            puzzle_id=puzzle.puzzle_id,
            clue_type=clue_type,
            content=f"线索提示: {puzzle.description}",
            hidden_in="room",
            requires_action=random.random() < 0.5
        )

    async def generate_red_herring(self, puzzle: Puzzle,
                                   theme: DungeonTheme) -> RedHerring:
        """生成误导线索"""
        return RedHerring(
            herring_id=f"herring_{uuid.uuid4().hex[:8]}",
            description="一个看似重要但实际无关的线索",
            misdirection="诱导玩家走向错误方向"
        )

    async def generate_final_puzzle(self, puzzles: List[Puzzle],
                                   theme: DungeonTheme,
                                   difficulty: int) -> Puzzle:
        """生成最终谜题"""
        return Puzzle(
            puzzle_id=f"final_{uuid.uuid4().hex[:8]}",
            puzzle_type=PuzzleType.MULTISTEP,
            difficulty=difficulty * 1.5,
            description="最终谜题: 需要结合之前所有线索",
            hints=["仔细回顾之前的所有线索..."]
        )

    async def generate_escape_conditions(self, puzzles: List[Puzzle]) -> List[str]:
        """生成逃脱条件"""
        return [f"解开谜题 {p.puzzle_id}" for p in puzzles]


# ==================== 各类型谜题生成器 ====================

class LogicPuzzleGenerator:
    """逻辑谜题生成器"""

    async def generate_puzzle(self, difficulty: float, theme: str) -> Puzzle:
        """生成逻辑谜题"""
        puzzle_templates = [
            ("谁拿了宝藏？", "A、B、C三人中有一人拿了宝藏..."),
            ("密码锁的密码？", "密码是三个不同数字之和为15..."),
            ("罪犯识别", "四个嫌疑人，每个人的话只有一半是真的...")
        ]

        template = random.choice(puzzle_templates)

        return Puzzle(
            puzzle_id=f"logic_{uuid.uuid4().hex[:8]}",
            puzzle_type=PuzzleType.LOGIC,
            difficulty=difficulty,
            description=template[1],
            hints=["尝试用排除法..."]
        )


class PatternRecognitionGenerator:
    """模式识别生成器"""

    async def generate_puzzle(self, difficulty: float, theme: str) -> Puzzle:
        """生成模式识别谜题"""
        patterns = [
            ("形状序列", "找出下一个形状: ○△□○△?"),
            ("颜色序列", "红蓝黄红蓝?，下一个是什么颜色？"),
            ("数字规律", "2、4、8、16、?，下一个数字是什么？")
        ]

        template = random.choice(patterns)

        return Puzzle(
            puzzle_id=f"pattern_{uuid.uuid4().hex[:8]}",
            puzzle_type=PuzzleType.PATTERN,
            difficulty=difficulty,
            description=template[1],
            hints=["观察规律..."]
        )


class MathPuzzleGenerator:
    """数学谜题生成器"""

    async def generate_puzzle(self, difficulty: float, theme: str) -> Puzzle:
        """生成数学谜题"""
        puzzles = [
            ("计算", f"({int(difficulty * 10)}+{int(difficulty * 20)})×{int(difficulty)}="),
            ("概率", "袋中有3红2白球，连续取2个都是红的概率？"),
            ("几何", "正方形边长为10，对角线长度是多少？")
        ]

        template = random.choice(puzzles)

        return Puzzle(
            puzzle_id=f"math_{uuid.uuid4().hex[:8]}",
            puzzle_type=PuzzleType.MATH,
            difficulty=difficulty,
            description=template[1],
            hints=["运用数学知识..."]
        )


class WordPuzzleGenerator:
    """文字谜题生成器"""

    async def generate_puzzle(self, difficulty: float, theme: str) -> Puzzle:
        """生成文字谜题"""
        puzzles = [
            ("字谜", "一加一等于什么字？"),
            ("成语", "在纸上画圈打一成语"),
            ("谜语", "上上下下，不上不下，打一字")
        ]

        template = random.choice(puzzles)

        return Puzzle(
            puzzle_id=f"word_{uuid.uuid4().hex[:8]}",
            puzzle_type=PuzzleType.WORD,
            difficulty=difficulty,
            description=template[1],
            hints=["发挥想象力..."]
        )


class SequencePuzzleGenerator:
    """序列谜题生成器"""

    async def generate_puzzle(self, difficulty: float, theme: str) -> Puzzle:
        """生成序列谜题"""
        return Puzzle(
            puzzle_id=f"seq_{uuid.uuid4().hex[:8]}",
            puzzle_type=PuzzleType.SEQUENCE,
            difficulty=difficulty,
            description="找规律: 1、1、2、3、5、8、?",
            hints=["斐波那契数列..."]
        )


class SpatialPuzzleGenerator:
    """空间谜题生成器"""

    async def generate_puzzle(self, difficulty: float, theme: str) -> Puzzle:
        """生成空间谜题"""
        return Puzzle(
            puzzle_id=f"spatial_{uuid.uuid4().hex[:8]}",
            puzzle_type=PuzzleType.SPATIAL,
            difficulty=difficulty,
            description="将立方体展开后是什么样的？",
            hints=["发挥空间想象力..."]
        )


class CrypticPuzzleGenerator:
    """隐晦谜题生成器"""

    async def generate_puzzle(self, difficulty: float, theme: str) -> Puzzle:
        """生成隐晦谜题"""
        return Puzzle(
            puzzle_id=f"cryptic_{uuid.uuid4().hex[:8]}",
            puzzle_type=PuzzleType.CRYPTIC,
            difficulty=difficulty,
            description="墙上的符号代表着什么？仔细观察...",
            hints=["与环境互动..."]
        )


class MultiStepPuzzleGenerator:
    """多步谜题生成器"""

    async def generate_puzzle(self, difficulty: float, theme: str) -> Puzzle:
        """生成多步谜题"""
        return Puzzle(
            puzzle_id=f"multi_{uuid.uuid4().hex[:8]}",
            puzzle_type=PuzzleType.MULTISTEP,
            difficulty=difficulty,
            description="需要多个步骤才能解决的谜题...",
            hints=["一步一步来..."]
        )


# ==================== 实时协作解谜系统 ====================

class CollaborativeEscapeRoom:
    """实时协作解谜系统"""

    def __init__(self):
        self.sessions = {}

    async def start_escape_room(self, player_ids: List[str],
                                escape_room: EscapeRoom) -> Dict:
        """开始密室逃脱"""

        session = {
            "session_id": f"session_{uuid.uuid4().hex[:8]}",
            "escape_room": escape_room,
            "players": {},
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "status": "in_progress",
            "puzzle_progress": {},
            "found_clues": [],
            "used_hints": 0,
            "chat_log": [],
            "action_log": [],
            "player_positions": {},
            "inventory": {}
        }

        # 初始化玩家
        for player_id in player_ids:
            session["players"][player_id] = {
                "player_id": player_id,
                "role": "explorer",
                "special_ability": random.choice(["hint_finder", "key_master", "code_cracker"]),
                "personal_inventory": [],
                "observed_clues": set(),
                "solved_puzzles": set(),
                "contribution_score": 0
            }
            session["player_positions"][player_id] = "start"

        # 初始化谜题进度
        for puzzle in escape_room.puzzles:
            session["puzzle_progress"][puzzle.puzzle_id] = {
                "solved": False,
                "attempts": 0,
                "hints_used": 0,
                "solvers": [],
                "time_started": None,
                "time_solved": None
            }

        self.sessions[session["session_id"]] = session
        return session

    async def solve_puzzle(self, session_id: str, puzzle_id: str,
                          solution: str, solver_id: str) -> Dict:
        """解谜"""
        session = self.sessions.get(session_id)
        if not session:
            return {"success": False, "error": "会话不存在"}

        puzzle = next((p for p in session["escape_room"]["puzzles"]
                      if p.puzzle_id == puzzle_id), None)
        if not puzzle:
            return {"success": False, "error": "谜题不存在"}

        progress = session["puzzle_progress"][puzzle_id]

        # 验证答案
        is_correct = await self.verify_solution(puzzle, solution)

        if is_correct and not progress["solved"]:
            progress["solved"] = True
            progress["solvers"].append(solver_id)
            progress["time_solved"] = datetime.now().isoformat()

            # 奖励
            reward = await self.calculate_puzzle_reward(puzzle)

            return {
                "success": True,
                "solved": True,
                "reward": reward,
                "unlocked_content": [],
                "escape_progress": await self.calculate_escape_progress(session)
            }
        else:
            progress["attempts"] += 1
            return {
                "success": False,
                "solved": False,
                "feedback": "答案不正确，请再试一次",
                "attempts": progress["attempts"]
            }

    async def verify_solution(self, puzzle: Puzzle, solution: str) -> bool:
        """验证答案"""
        return str(solution).lower().strip() == str(puzzle.solution).lower().strip()

    async def calculate_puzzle_reward(self, puzzle: Puzzle) -> int:
        """计算谜题奖励"""
        base = int(puzzle.difficulty * 100)
        return base

    async def calculate_escape_progress(self, session: Dict) -> float:
        """计算逃脱进度"""
        total = len(session["puzzle_progress"])
        solved = sum(1 for p in session["puzzle_progress"].values() if p["solved"])
        return solved / total if total > 0 else 0


# ==================== 自适应难度系统 ====================

class AdaptiveDifficultyEscape:
    """自适应难度密室逃脱"""

    def __init__(self):
        self.difficulty_history = []

    async def adjust_difficulty(self, session: Dict) -> Dict:
        """根据表现调整难度"""
        performance = await self.analyze_performance(session)

        adjustments = {
            "puzzle_difficulty": 0,
            "time_adjustment": 0,
            "hint_availability": 0,
            "clue_visibility": 0
        }

        if performance["success_rate"] < 0.3:
            adjustments["puzzle_difficulty"] = -1
            adjustments["time_adjustment"] = 300
            adjustments["hint_availability"] = 1
        elif performance["success_rate"] > 0.8:
            adjustments["puzzle_difficulty"] = 1
            adjustments["time_adjustment"] = -180
            adjustments["hint_availability"] = -1

        return {
            "session_id": session["session_id"],
            "performance_analysis": performance,
            "adjustments": adjustments,
            "new_difficulty": session["escape_room"].difficulty + adjustments["puzzle_difficulty"]
        }

    async def analyze_performance(self, session: Dict) -> Dict:
        """分析表现"""
        total_attempts = sum(p["attempts"] for p in session["puzzle_progress"].values())
        solved_count = sum(1 for p in session["puzzle_progress"].values() if p["solved"])
        total_puzzles = len(session["puzzle_progress"])

        return {
            "success_rate": solved_count / total_puzzles if total_puzzles > 0 else 0,
            "total_attempts": total_attempts,
            "hints_used": session["used_hints"],
            "time_elapsed": await self.calculate_time_elapsed(session)
        }

    async def calculate_time_elapsed(self, session: Dict) -> int:
        """计算已用时间"""
        start = datetime.fromisoformat(session["start_time"])
        now = datetime.now()
        return int((now - start).total_seconds())


# ==================== 三合一融合引擎 ====================

class DungeonWerewolfEscape:
    """地牢狼人杀密室三合一"""

    def __init__(self):
        self.dungeon_gen = AI_DungeonGenerator()
        self.werewolf = DungeonWerewolf()
        self.escape_gen = EscapeRoomPuzzleGenerator()
        self.narrative_director = AI_NarrativeDirector()
        self.cross_progress = CrossGameProgression()

    async def create_fusion_game(self, player_count: int = 6,
                                 base_difficulty: int = 1) -> FusionGame:
        """创建融合游戏"""

        # 1. 生成地牢
        dungeon = await self.dungeon_gen.generate_dungeon_layer(
            layer_depth=base_difficulty,
            party_size=player_count
        )

        # 2. 转换为密室逃脱
        escape_room = await self.escape_gen.generate_escape_room(
            theme=dungeon.theme,
            difficulty=base_difficulty,
            player_count=player_count
        )

        # 3. 加入狼人杀元素
        werewolf_game = await self.werewolf.start_werewolf_game(
            dungeon_layer=dungeon,
            player_count=player_count
        )

        # 4. 生成剧情
        story = await self.generate_fusion_story(player_count, dungeon)

        # 5. 融合游戏
        fusion_game = FusionGame(
            game_id=f"fusion_{uuid.uuid4().hex[:8]}",
            dungeon=dungeon,
            werewolf=werewolf_game,
            escape_room=escape_room,
            phase=GamePhase.LOBBY,
            players={},
            story=story,
            victory_conditions={
                "escape_room": "在时限内解谜逃脱",
                "werewolf": "消灭所有狼人/村民",
                "dungeon": "击败最终Boss",
                "combined": "完成任意两种即可胜利"
            }
        )

        return fusion_game

    async def generate_fusion_story(self, player_count: int,
                                   dungeon: DungeonLayer) -> Dict:
        """生成融合剧情"""
        story_arcs = {
            "main": {
                "title": "深渊的召唤",
                "chapters": [
                    "第一章: 神秘的地牢",
                    "第二章: 隐藏的背叛者",
                    "第三章: 智慧的试炼",
                    "第四章: 最终的抉择"
                ]
            }
        }

        return story_arcs

    async def play_fusion_game(self, game: FusionGame, action: str,
                              player_id: str, data: Dict) -> Dict:
        """进行融合游戏"""

        if game.phase == GamePhase.ESCAPE:
            result = await self.handle_escape_action(game, player_id, action, data)
        elif game.phase == GamePhase.WEREWOLF:
            result = await self.handle_werewolf_action(game, player_id, action, data)
        elif game.phase == GamePhase.COMBAT:
            result = await self.handle_combat_action(game, player_id, action, data)

        # 检查阶段转换
        phase_transition = await self.check_phase_transition(game)
        if phase_transition["transition"]:
            game.phase = phase_transition["new_phase"]

        # AI叙事导演
        narrative_result = await self.narrative_director.direct_fusion_game(game)

        return {
            "action_result": result,
            "phase_transition": phase_transition,
            "narrative": narrative_result,
            "game_state": await self.get_game_state_for_player(game, player_id)
        }

    async def handle_escape_action(self, game: FusionGame, player_id: str,
                                   action: str, data: Dict) -> Dict:
        """处理逃脱动作"""
        return {"action": "escape", "result": "puzzle_solved"}

    async def handle_werewolf_action(self, game: FusionGame, player_id: str,
                                    action: str, data: Dict) -> Dict:
        """处理狼人杀动作"""
        return {"action": "werewolf", "result": "vote_cast"}

    async def handle_combat_action(self, game: FusionGame, player_id: str,
                                  action: str, data: Dict) -> Dict:
        """处理战斗动作"""
        return {"action": "combat", "result": "attack_success"}

    async def check_phase_transition(self, game: FusionGame) -> Dict:
        """检查阶段转换"""
        return {"transition": False, "new_phase": game.phase}

    async def get_game_state_for_player(self, game: FusionGame,
                                        player_id: str) -> Dict:
        """获取玩家视角的游戏状态"""
        return {
            "phase": game.phase.value,
            "player_count": len(game.players),
            "your_role": game.players.get(player_id, {}).get("role", "unknown")
        }


# ==================== AI叙事导演 ====================

class AI_NarrativeDirector:
    """AI叙事导演系统"""

    def __init__(self):
        self.narrative_arcs = {
            "betrayal": {"trigger": "player_suspicion > 0.7", "event": "reveal_traitor", "dramatic_timing": "climax"},
            "redemption": {"trigger": "player_morale < 0.3", "event": "unexpected_ally", "dramatic_timing": "low_point"},
            "twist": {"trigger": "puzzle_solved_count > 3", "event": "identity_swap", "dramatic_timing": "midpoint"},
            "sacrifice": {"trigger": "time_remaining < 0.2", "event": "heroic_sacrifice", "dramatic_timing": "climax"}
        }

    async def direct_fusion_game(self, game: FusionGame) -> Dict:
        """导演融合游戏"""
        dramatic_tension = await self.analyze_dramatic_tension(game)

        selected_arc = await self.select_narrative_arc(dramatic_tension, game)

        if selected_arc:
            narrative_event = await self.generate_narrative_event(
                selected_arc, game, dramatic_tension
            )
            return {
                "directed": True,
                "narrative_arc": selected_arc,
                "event": narrative_event
            }

        return {"directed": False}

    async def analyze_dramatic_tension(self, game: FusionGame) -> float:
        """分析戏剧张力"""
        tension = 0.5

        if game.phase == GamePhase.COMBAT:
            tension += 0.2
        elif game.phase == GamePhase.WEREWOLF:
            tension += 0.3

        return tension

    async def select_narrative_arc(self, tension: float, game: FusionGame) -> Optional[Dict]:
        """选择叙事弧"""
        for arc_name, arc in self.narrative_arcs.items():
            if random.random() < 0.2:  # 20%几率触发
                return arc
        return None

    async def generate_narrative_event(self, arc: Dict, game: FusionGame,
                                      tension: float) -> Dict:
        """生成叙事事件"""
        event_templates = {
            "reveal_traitor": {
                "type": "revelation",
                "dramatic_lines": ["等等...这不可能！", "我一直信任着你！"]
            },
            "unexpected_ally": {
                "type": "assistance",
                "dramatic_lines": ["黑暗中传来一个声音...", "有人留下了这个线索..."]
            }
        }

        template = event_templates.get(arc["event"], {})

        return {
            "event_id": f"story_{uuid.uuid4().hex[:8]}",
            "arc": arc["event"],
            "dramatic_lines": template.get("dramatic_lines", []),
            "customized_elements": {}
        }


# ==================== 跨游戏进度系统 ====================

class CrossGameProgression:
    """跨游戏进度系统"""

    def __init__(self):
        self.user_progress = {}

    async def track_cross_game_progress(self, user_id: str) -> Dict:
        """追踪跨游戏进度"""
        progress = self.user_progress.get(user_id, {
            "dungeon_mastery": {"deepest_layer": 0, "bosses_defeated": 0},
            "werewolf_skill": {"games_played": 0, "win_rate": 0.0},
            "escape_expertise": {"rooms_escaped": 0, "puzzle_success_rate": 0.0},
            "fusion_achievements": {"fusion_games_completed": 0, "unique_endings": 0}
        })

        overall_level = await self.calculate_overall_level(progress)

        return {
            "user_id": user_id,
            "progress": progress,
            "overall_level": overall_level,
            "title": await self.get_cross_game_title(overall_level)
        }

    async def calculate_overall_level(self, progress: Dict) -> int:
        """计算综合等级"""
        dungeon_lv = progress.get("dungeon_mastery", {}).get("deepest_layer", 0) // 5
        werewolf_lv = int(progress.get("werewolf_skill", {}).get("win_rate", 0) * 10)
        escape_lv = progress.get("escape_expertise", {}).get("rooms_escaped", 0)

        return max(dungeon_lv, werewolf_lv, escape_lv)

    async def get_cross_game_title(self, level: int) -> str:
        """获取称号"""
        titles = {
            0: "新手冒险者",
            5: "地牢探索者",
            10: "狼人猎人",
            15: "解谜大师",
            20: "全能冒险王"
        }

        for lv, title in sorted(titles.items(), reverse=True):
            if level >= lv:
                return title
        return titles[0]


# ==================== 动态角色系统 ====================

class DynamicRoleSystem:
    """动态角色系统"""

    def __init__(self):
        self.base_classes = ["战士", "法师", "游侠", "刺客", "圣职者"]
        self.specializations = {}

    async def assign_dynamic_role(self, player_id: str,
                                 game_context: Dict) -> Dict:
        """分配动态角色"""

        playstyle = await self.analyze_playstyle(player_id)
        base_class = await self.select_base_class(playstyle)
        specialization = await self.select_specialization(playstyle, game_context)

        role = {
            "base_class": base_class,
            "specialization": specialization,
            "unique_ability": f"{base_class}_{specialization}_ability",
            "role_flaw": await self.generate_role_flaw(playstyle),
            "hidden_objective": await self.generate_hidden_objective(game_context),
            "cross_game_bonus": await self.get_cross_game_bonus(player_id, base_class)
        }

        return role

    async def analyze_playstyle(self, player_id: str) -> Dict:
        """分析玩家风格"""
        return {
            "aggression": random.uniform(0, 1),
            "caution": random.uniform(0, 1),
            "social": random.uniform(0, 1),
            "exploration": random.uniform(0, 1)
        }

    async def select_base_class(self, playstyle: Dict) -> str:
        """选择基础职业"""
        return random.choice(self.base_classes)

    async def select_specialization(self, playstyle: Dict,
                                    game_context: Dict) -> str:
        """选择专精"""
        specializations = ["战斗", "防御", "支援", "控制"]
        return random.choice(specializations)

    async def generate_role_flaw(self, playstyle: Dict) -> str:
        """生成角色缺陷"""
        flaws = ["黑暗过去", "致命弱点", "诅咒物品", "复仇执念"]
        return random.choice(flaws)

    async def generate_hidden_objective(self, game_context: Dict) -> str:
        """生成隐藏目标"""
        objectives = ["保护某人", "收集特定物品", "触发隐藏结局"]
        return random.choice(objectives)

    async def get_cross_game_bonus(self, player_id: str,
                                   base_class: str) -> Optional[Dict]:
        """获取跨游戏奖励"""
        return None


# ==================== 环境叙事系统 ====================

class EnvironmentalStorytelling:
    """环境叙事系统"""

    def __init__(self):
        self.story_elements = {}

    async def generate_environmental_story(self, location: Dict,
                                          game_context: Dict) -> Dict:
        """生成环境叙事"""

        story_elements = {
            "visual_clues": await self.generate_visual_clues(location, game_context),
            "audio_ambience": await self.generate_audio_ambience(location, game_context),
            "interactive_objects": await self.generate_interactive_objects(location, game_context),
            "written_material": await self.generate_written_material(location, game_context),
            "environmental_changes": await self.generate_environmental_changes(location, game_context)
        }

        return {
            "location_id": location.get("id", "unknown"),
            "story_elements": story_elements,
            "mystery_level": random.uniform(0.3, 0.9),
            "reveal_progression": []
        }

    async def generate_visual_clues(self, location: Dict,
                                   game_context: Dict) -> List[str]:
        """生成视觉线索"""
        return ["墙上的划痕", "地板的血迹", "散落的纸张"]

    async def generate_audio_ambience(self, location: Dict,
                                     game_context: Dict) -> Dict:
        """生成音频氛围"""
        return {
            "ambient": "dripping_water",
            "background_music": "tension",
            "sfx": ["footsteps", "distant_screams"]
        }

    async def generate_interactive_objects(self, location: Dict,
                                         game_context: Dict) -> List[Dict]:
        """生成可交互对象"""
        return [
            {"id": "lever_1", "name": "拉杆", "state": "off"},
            {"id": "chest_1", "name": "宝箱", "state": "locked"}
        ]

    async def generate_written_material(self, location: Dict,
                                        game_context: Dict) -> List[Dict]:
        """生成文字材料"""
        return [
            {"type": "note", "content": "不要相信任何人..."},
            {"type": "diary", "content": "今天发现了奇怪的符号..."}
        ]

    async def generate_environmental_changes(self, location: Dict,
                                           game_context: Dict) -> List[str]:
        """生成环境变化"""
        return ["灯光闪烁", "墙壁震动", "温度下降"]


# ==================== 社交推理引擎 ====================

class SocialDeductionEngine:
    """社交推理引擎"""

    def __init__(self):
        self.trust_network = {}

    async def analyze_social_dynamics(self, game: WerewolfGame) -> Dict:
        """分析社交动态"""

        analysis = {
            "trust_network": await self.build_trust_network(game),
            "communication_patterns": await self.analyze_communication_patterns(game),
            "behavioral_anomalies": await self.detect_behavioral_anomalies(game),
            "group_dynamics": await self.analyze_group_dynamics(game),
            "hidden_agendas": await self.infer_hidden_agendas(game)
        }

        predictions = {
            "next_betrayal": await self.predict_next_betrayal(analysis),
            "likely_alliances": await self.predict_alliances(analysis),
            "vulnerable_players": await self.identify_vulnerable_players(analysis),
            "dramatic_turning_points": await self.predict_turning_points(analysis)
        }

        return {
            "analysis": analysis,
            "predictions": predictions,
            "confidence_scores": {},
            "narrative_suggestions": []
        }

    async def build_trust_network(self, game: WerewolfGame) -> Dict:
        """构建信任网络"""
        trust = {}
        for player_id in game.players:
            trust[player_id] = {"trusted_by": [], "distrusted_by": []}
        return trust

    async def analyze_communication_patterns(self, game: WerewolfGame) -> Dict:
        """分析通信模式"""
        return {"speech_frequency": {}, "topics_discussed": []}

    async def detect_behavioral_anomalies(self, game: WerewolfGame) -> List[Dict]:
        """检测行为异常"""
        return []

    async def analyze_group_dynamics(self, game: WerewolfGame) -> Dict:
        """分析群体动态"""
        return {"leaders": [], "followers": [], "isolated": []}

    async def infer_hidden_agendas(self, game: WerewolfGame) -> Dict:
        """推断隐藏议程"""
        return {}

    async def predict_next_betrayal(self, analysis: Dict) -> Optional[str]:
        """预测下一个背叛"""
        return None

    async def predict_alliances(self, analysis: Dict) -> List[Tuple[str, str]]:
        """预测联盟"""
        return []

    async def identify_vulnerable_players(self, analysis: Dict) -> List[str]:
        """识别弱势玩家"""
        return []

    async def predict_turning_points(self, analysis: Dict) -> List[Dict]:
        """预测转折点"""
        return []


# ==================== 主类导出 ====================

class FusionGameEngine:
    """融合游戏引擎 - 统一入口"""

    def __init__(self):
        self.dungeon_gen = AI_DungeonGenerator()
        self.werewolf = DungeonWerewolf()
        self.escape_gen = EscapeRoomPuzzleGenerator()
        self.collaborative_escape = CollaborativeEscapeRoom()
        self.adaptive_difficulty = AdaptiveDifficultyEscape()
        self.fusion_engine = DungeonWerewolfEscape()
        self.narrative_director = AI_NarrativeDirector()
        self.cross_progress = CrossGameProgression()
        self.dynamic_role = DynamicRoleSystem()
        self.env_story = EnvironmentalStorytelling()
        self.social_deduction = SocialDeductionEngine()
        self.loot_system = SmartLootSystem()

    async def create_new_game(self, player_count: int = 6,
                             game_type: str = "fusion",
                             difficulty: int = 1) -> FusionGame:
        """创建新游戏"""
        return await self.fusion_engine.create_fusion_game(
            player_count=player_count,
            base_difficulty=difficulty
        )

    async def start_game(self, game: FusionGame, player_ids: List[str]) -> Dict:
        """开始游戏"""
        for player_id in player_ids:
            player = Player(
                player_id=player_id,
                name=f"Player_{player_id[-4:]}",
                level=1
            )
            game.players[player_id] = player

        game.phase = GamePhase.NIGHT

        return {
            "game_id": game.game_id,
            "players": list(game.players.keys()),
            "phase": game.phase.value,
            "start_time": datetime.now().isoformat()
        }

    async def execute_action(self, game: FusionGame, player_id: str,
                           action: str, data: Dict) -> Dict:
        """执行动作"""
        return await self.fusion_engine.play_fusion_game(
            game=game,
            action=action,
            player_id=player_id,
            data=data
        )


# 导出所有类
__all__ = [
    'AI_DungeonGenerator',
    'IntelligentNPCSystem',
    'SmartLootSystem',
    'DungeonWerewolf',
    'AI_WerewolfBehavior',
    'EscapeRoomPuzzleGenerator',
    'CollaborativeEscapeRoom',
    'AdaptiveDifficultyEscape',
    'DungeonWerewolfEscape',
    'AI_NarrativeDirector',
    'CrossGameProgression',
    'DynamicRoleSystem',
    'EnvironmentalStorytelling',
    'SocialDeductionEngine',
    'FusionGameEngine',
    'DungeonTheme',
    'RoomType',
    'WerewolfRole',
    'GamePhase',
    'PuzzleType',
    'ItemRarity',
    'Player',
    'Room',
    'NPC',
    'DungeonLayer',
    'WerewolfGame',
    'EscapeRoom',
    'Puzzle',
    'FusionGame',
    'Item'
]
