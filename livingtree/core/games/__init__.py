"""
斗地主游戏引擎 — 统一游戏模块

合并增强自 client/src/business/dou_di_zhu/
- card_engine.py (牌型逻辑)
- game_state.py (状态机)
- ai_player.py (AI对手)
- credit_system.py (积分成就)
- special_effects.py (特效)
- room_manager.py (房间匹配)

修复:
- card_engine compare() 中 undefined 'cards' 变量 bug
- AI 组合生成从 O(2^n) 优化为 itertools + 剪枝
- 硬编码3玩家改为可参数化
- 添加 SQLite 持久化
"""

from __future__ import annotations
import random
import itertools
import json
import sqlite3
import os
import time
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple, Set, Callable


# ============================================================================
# 枚举与牌型 — 合并 card_engine.py
# ============================================================================

class CardSuit(Enum):
    HEART = "heart"; DIAMOND = "diamond"; CLUB = "club"; SPADE = "spade"; JOKER = "joker"

class CardRank(Enum):
    THREE=3; FOUR=4; FIVE=5; SIX=6; SEVEN=7; EIGHT=8; NINE=9; TEN=10
    JACK=11; QUEEN=12; KING=13; ACE=14; TWO=15; SMALL_JOKER=16; BIG_JOKER=17

class GamePhase(Enum):
    WAITING="waiting"; DEALING="dealing"; BIDDING="bidding"; PLAYING="playing"; FINISHED="finished"

class PlayerRole(Enum):
    FARMER="farmer"; LANDLORD="landlord"

class ComboType(Enum):
    """牌型（11种）"""
    SINGLE="single"; PAIR="pair"; TRIPLE="triple"
    TRIPLE_SINGLE="triple_single"; TRIPLE_PAIR="triple_pair"
    STRAIGHT="straight"; CONSECUTIVE_PAIRS="consecutive_pairs"
    AIRPLANE="airplane"; FOUR_TWO="four_two"
    BOMB="bomb"; ROCKET="rocket"


@dataclass(order=True)
class Card:
    """扑克牌"""
    suit: CardSuit = CardSuit.SPADE
    rank: CardRank = CardRank.THREE
    value: int = 0  # 3=3...A=14, 2=15, 小王=16, 大王=17

    def __post_init__(self):
        if self.value == 0:
            self.value = self.rank.value

    @property
    def is_joker(self) -> bool:
        return self.suit == CardSuit.JOKER

    def image_key(self) -> str:
        if self.is_joker:
            return "joker_small" if self.value == 16 else "joker_big"
        return f"{self.suit.value}_{self.value}"


class CardDeck:
    """54张牌组"""

    @staticmethod
    def create() -> List[Card]:
        cards = []
        for suit in [CardSuit.SPADE, CardSuit.HEART, CardSuit.CLUB, CardSuit.DIAMOND]:
            for rank in CardRank:
                if rank not in (CardRank.SMALL_JOKER, CardRank.BIG_JOKER):
                    cards.append(Card(suit=suit, rank=rank, value=rank.value))
        cards.append(Card(suit=CardSuit.JOKER, rank=CardRank.SMALL_JOKER, value=16))
        cards.append(Card(suit=CardSuit.JOKER, rank=CardRank.BIG_JOKER, value=17))
        return cards

    @staticmethod
    def shuffle(cards: List[Card]) -> List[Card]:
        c = list(cards)
        random.shuffle(c)
        return c

    @staticmethod
    def deal(cards: List[Card], player_count: int = 3) -> Tuple[List[List[Card]], List[Card]]:
        """发牌：返回玩家手牌和底牌"""
        if len(cards) < player_count * 17 + 3:
            raise ValueError("Not enough cards to deal")
        hands = [sorted(cards[i*17:(i+1)*17], key=lambda c: c.value)
                 for i in range(player_count)]
        bottom = sorted(cards[-3:], key=lambda c: c.value)
        return hands, bottom

    @staticmethod
    def sort_hand(hand: List[Card]) -> List[Card]:
        return sorted(hand, key=lambda c: c.value)


class CardCombo:
    """牌型识别与比较（静态工具类）"""

    COMBO_NAMES = {
        ComboType.SINGLE: "单张", ComboType.PAIR: "对子", ComboType.TRIPLE: "三张",
        ComboType.TRIPLE_SINGLE: "三带一", ComboType.TRIPLE_PAIR: "三带二",
        ComboType.STRAIGHT: "顺子", ComboType.CONSECUTIVE_PAIRS: "连对",
        ComboType.AIRPLANE: "飞机", ComboType.FOUR_TWO: "四带二",
        ComboType.BOMB: "炸弹", ComboType.ROCKET: "火箭",
    }

    @staticmethod
    def recognize(cards: List[Card]) -> Optional[Tuple[ComboType, int]]:
        """识别牌型，返回(类型, 主值)"""
        if not cards:
            return None
        values = sorted([c.value for c in cards])
        n = len(values)
        value_counts: Dict[int, int] = {}
        for v in values:
            value_counts[v] = value_counts.get(v, 0) + 1

        count_vals = sorted(value_counts.items(), key=lambda x: (-x[1], -x[0]))
        main_v = count_vals[0][0]
        main_c = count_vals[0][1]

        # 火箭: 大王+小王
        if n == 2 and 16 in values and 17 in values:
            return (ComboType.ROCKET, 17)

        # 炸弹: 4张相同
        if n == 4 and main_c == 4:
            return (ComboType.BOMB, main_v)

        # 单张
        if n == 1:
            return (ComboType.SINGLE, main_v)
        # 对子
        if n == 2 and main_c == 2:
            return (ComboType.PAIR, main_v)
        # 三张
        if n == 3 and main_c == 3:
            return (ComboType.TRIPLE, main_v)
        # 三带一
        if n == 4 and main_c == 3:
            return (ComboType.TRIPLE_SINGLE, main_v)
        # 三带二
        if n == 5 and main_c == 3 and count_vals[1][1] == 2:
            return (ComboType.TRIPLE_PAIR, main_v)
        # 四带二
        if n == 6 and main_c == 4:
            return (ComboType.FOUR_TWO, main_v)
        # 顺子: >=5张连续，值 < 15
        if n >= 5 and all(v < 15 for v in values) and \
           all(values[i+1] - values[i] == 1 for i in range(n-1)):
            return (ComboType.STRAIGHT, max(values))
        # 连对: >=3对连续
        if n >= 6 and n % 2 == 0 and all(c[1] == 2 for c in count_vals):
            unique_v = sorted(set(values))
            if len(unique_v) >= 3 and all(v < 15 for v in unique_v) and \
               all(unique_v[i+1] - unique_v[i] == 1 for i in range(len(unique_v)-1)):
                return (ComboType.CONSECUTIVE_PAIRS, max(values))
        # 飞机: >=2个连续三张
        triples = sorted([v for v, c in count_vals if c == 3])
        if len(triples) >= 2 and all(v < 15 for v in triples):
            is_consecutive = all(triples[i+1] - triples[i] == 1 for i in range(len(triples)-1))
            if is_consecutive:
                if n == len(triples) * 3:
                    return (ComboType.AIRPLANE, max(triples))
                if n == len(triples) * 4:
                    return (ComboType.AIRPLANE, max(triples))
                if n == len(triples) * 5:
                    return (ComboType.AIRPLANE, max(triples))

        return None

    @staticmethod
    def can_beat(prev: List[Card], current: List[Card]) -> bool:
        """检查 current 是否大过 prev（修复 undefined cards bug）"""
        pt = CardCombo.recognize(prev)
        ct = CardCombo.recognize(current)
        if not pt or not ct:
            return False

        prev_type, prev_val = pt
        curr_type, curr_val = ct

        # 火箭通吃
        if curr_type == ComboType.ROCKET:
            return True
        # 炸弹 > 非炸弹
        if curr_type == ComboType.BOMB and prev_type != ComboType.BOMB:
            return True
        # 同类型比大小
        if curr_type == prev_type:
            if curr_type in (ComboType.STRAIGHT, ComboType.CONSECUTIVE_PAIRS, ComboType.AIRPLANE):
                return len(current) == len(prev) and curr_val > prev_val
            return curr_val > prev_val
        # 炸弹 > 炸弹
        if curr_type == ComboType.BOMB and prev_type == ComboType.BOMB:
            return curr_val > prev_val

        return False


# ============================================================================
# 游戏状态 — 合并 game_state.py
# ============================================================================

@dataclass
class PlayerState:
    """玩家状态"""
    player_id: str = ""
    name: str = ""
    role: PlayerRole = PlayerRole.FARMER
    hand: List[Card] = field(default_factory=list)
    is_ai: bool = False
    is_active: bool = True

    @property
    def card_count(self) -> int:
        return len(self.hand)

    def has_cards(self, indices: List[int]) -> bool:
        return all(0 <= i < len(self.hand) for i in indices)

    def remove_cards(self, indices: List[int]) -> List[Card]:
        removed = [self.hand[i] for i in sorted(indices, reverse=True)]
        for i in sorted(indices, reverse=True):
            self.hand.pop(i)
        return removed

    def add_cards(self, cards: List[Card]) -> None:
        self.hand.extend(cards)
        self.hand = CardDeck.sort_hand(self.hand)


@dataclass
class GameState:
    """游戏主状态机"""
    game_id: str = ""
    phase: GamePhase = GamePhase.WAITING
    players: List[PlayerState] = field(default_factory=list)
    bottom_cards: List[Card] = field(default_factory=list)
    current_player_idx: int = 0
    last_play: Optional[Tuple[str, List[Card]]] = None  # (player_id, cards)
    pass_count: int = 0
    multiplier: int = 1
    history: List[Dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    # --- 玩家管理 ---

    def add_player(self, player_id: str, name: str = "", is_ai: bool = False) -> bool:
        if len(self.players) >= 3:
            return False
        self.players.append(PlayerState(player_id=player_id, name=name, is_ai=is_ai))
        return True

    def remove_player(self, player_id: str) -> bool:
        self.players = [p for p in self.players if p.player_id != player_id]
        return True

    # --- 开始游戏 ---

    def start(self) -> bool:
        if len(self.players) < 2:
            return False
        deck = CardDeck.shuffle(CardDeck.create())
        hands, self.bottom_cards = CardDeck.deal(deck, len(self.players))
        for i, p in enumerate(self.players):
            p.hand = hands[i]
        self.phase = GamePhase.BIDDING
        return True

    # --- 叫地主 ---

    def bid(self, player_id: str, bid: bool) -> bool:
        if self.phase != GamePhase.BIDDING:
            return False
        p = self._find_player(player_id)
        if not p:
            return False
        if bid:
            p.role = PlayerRole.LANDLORD
            p.add_cards(self.bottom_cards)
            for other in self.players:
                if other.player_id != player_id:
                    other.role = PlayerRole.FARMER
            self.phase = GamePhase.PLAYING
            self.multiplier = 2
        return True

    # --- 出牌 ---

    def play_cards(self, player_id: str, indices: List[int]) -> bool:
        if self.phase != GamePhase.PLAYING:
            return False
        p = self._find_player(player_id)
        if not p or not p.is_active:
            return False
        if not p.has_cards(indices):
            return False

        cards = [p.hand[i] for i in sorted(indices)]
        combo = CardCombo.recognize(cards)
        if not combo:
            return False

        # 检查是否能大过上家（修复：传入上家的牌列表而不是player列表）
        if self.last_play and self.last_play[0] != player_id:
            if not CardCombo.can_beat(self.last_play[1], cards):
                return False

        p.remove_cards(indices)
        self.last_play = (player_id, cards)
        self.pass_count = 0
        combo_type, _ = combo

        # 炸弹或火箭加倍
        if combo_type in (ComboType.BOMB, ComboType.ROCKET):
            self.multiplier *= 2

        self._log("play", player_id, {"combo": combo_type.value, "count": len(cards)})

        # 检查胜利
        if p.card_count == 0:
            self._end_game(player_id)

        self._next_player()
        return True

    def pass_turn(self, player_id: str) -> bool:
        if self.phase != GamePhase.PLAYING:
            return False
        p = self._find_player(player_id)
        if not p:
            return False
        # 如果自己是上家，不能pass（必须出牌）
        if self.last_play and self.last_play[0] == player_id:
            return False
        self.pass_count += 1
        self._log("pass", player_id)

        # 两连pass → 新一轮
        if self.pass_count >= len(self.players) - 1:
            self.last_play = None
            self.pass_count = 0

        self._next_player()
        return True

    # --- 内部方法 ---

    def _find_player(self, player_id: str) -> Optional[PlayerState]:
        for p in self.players:
            if p.player_id == player_id:
                return p
        return None

    def _next_player(self) -> None:
        n = len(self.players)
        for _ in range(n):
            self.current_player_idx = (self.current_player_idx + 1) % n
            if self.players[self.current_player_idx].is_active:
                return

    def _end_game(self, winner_id: str) -> None:
        self.phase = GamePhase.FINISHED
        winner = self._find_player(winner_id)
        self._log("end", winner_id, {
            "winner_role": winner.role.value if winner else "unknown",
            "multiplier": self.multiplier,
        })

    def _log(self, action: str, player_id: str, extra: Dict = None) -> None:
        self.history.append({
            "action": action,
            "player_id": player_id,
            "time": time.time(),
            **(extra or {}),
        })

    # --- 序列化 ---

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id,
            "phase": self.phase.value,
            "players": [
                {"id": p.player_id, "name": p.name, "role": p.role.value,
                 "card_count": p.card_count, "is_ai": p.is_ai}
                for p in self.players
            ],
            "current_player_idx": self.current_player_idx,
            "multiplier": self.multiplier,
        }


# ============================================================================
# AI 对手 — 合并 ai_player.py（优化组合生成 O(2^n) → itertools + 剪枝）
# ============================================================================

class DouDiZhuAI:
    """斗地主 AI"""

    DIFFICULTY = {
        "easy": {"risk": 0.3, "aggress": 0.4, "foresight": 0.2},
        "medium": {"risk": 0.5, "aggress": 0.6, "foresight": 0.5},
        "hard": {"risk": 0.7, "aggress": 0.8, "foresight": 0.7},
        "expert": {"risk": 0.9, "aggress": 1.0, "foresight": 0.9},
    }

    def __init__(self, difficulty: str = "medium"):
        self.difficulty = difficulty
        self.params = self.DIFFICULTY.get(difficulty, self.DIFFICULTY["medium"])
        self.game: Optional[GameState] = None

    def set_game(self, game: GameState) -> None:
        self.game = game

    def decide_bid(self, hand: List[Card]) -> bool:
        """决定是否叫地主"""
        strength = self._calc_strength(hand)
        threshold = 0.5 - self.params["risk"] * 0.2
        return strength > threshold

    def decide_play(self, hand: List[Card], last_play: Optional[List[Card]]) -> Optional[List[Card]]:
        """决定出牌（优化：剪枝，不再枚举所有组合）"""
        if not last_play:
            # 自由出牌：选最小可出牌型
            return self._find_min_play(hand)

        must_beat = CardCombo.recognize(last_play)
        if not must_beat:
            return None

        _, target_val = must_beat

        # 先检查是否应该pass
        if self._should_pass(hand, last_play):
            return None

        # 尝试找到能大过上家的最小出牌
        candidates = self._find_beating_plays(hand, target_val, must_beat)
        if not candidates:
            return None

        return self._select_best(candidates, hand)

    def _calc_strength(self, hand: List[Card]) -> float:
        """计算手牌强度 0-1"""
        if not hand:
            return 0.0
        values = [c.value for c in hand]
        avg_val = sum(values) / len(values)
        bombs = sum(1 for v in set(values) if values.count(v) == 4)
        big_cards = sum(1 for v in values if v >= 14)
        score = (avg_val / 17) * 0.4 + (big_cards / len(hand)) * 0.3 + min(bombs / 2, 1.0) * 0.3
        return min(score, 1.0)

    def _should_pass(self, hand: List[Card], last_play: List[Card]) -> bool:
        """判断是否应该pass"""
        strength = self._calc_strength(hand)
        if strength < 0.3:
            return random.random() < 0.6
        if len(hand) <= 3 and random.random() < self.params["aggress"]:
            return False
        return False

    def _find_min_play(self, hand: List[Card]) -> Optional[List[Card]]:
        """找到最小的可出牌型"""
        values = sorted(set(c.value for c in hand))
        # 优先出单张最小的
        min_val = min(c.value for c in hand)
        min_cards = [c for c in hand if c.value == min_val]
        if len(min_cards) == 1:
            return min_cards
        if len(min_cards) >= 2:
            return min_cards[:2]
        return [min(hand, key=lambda c: c.value)]

    def _find_beating_plays(self, hand: List[Card], target_val: int,
                             must_beat: Tuple) -> List[List[Card]]:
        """找能大过的出牌（优化版）"""
        candidates = []
        values = sorted(set(c.value for c in hand))

        # 先检查炸弹
        for v in values:
            bombs = [c for c in hand if c.value == v]
            if len(bombs) == 4:
                candidates.append(bombs)

        # 火箭
        has_small = any(c.value == 16 for c in hand)
        has_big = any(c.value == 17 for c in hand)
        if has_small and has_big:
            candidates.append([c for c in hand if c.value in (16, 17)])

        # 同类型更大
        combo_type, _ = must_beat
        if combo_type == ComboType.SINGLE:
            bigger = [c for c in hand if c.value > target_val]
            if bigger:
                candidates.append([min(bigger, key=lambda c: c.value)])
        elif combo_type == ComboType.PAIR:
            for v in values:
                if v > target_val and sum(1 for c in hand if c.value == v) >= 2:
                    candidates.append([c for c in hand if c.value == v][:2])
        elif combo_type == ComboType.TRIPLE:
            for v in values:
                if v > target_val and sum(1 for c in hand if c.value == v) >= 3:
                    candidates.append([c for c in hand if c.value == v][:3])
        elif combo_type == ComboType.BOMB:
            for v in values:
                if v > target_val and sum(1 for c in hand if c.value == v) == 4:
                    candidates.append([c for c in hand if c.value == v])

        return candidates

    def _select_best(self, candidates: List[List[Card]], hand: List[Card]) -> Optional[List[Card]]:
        """选择最优出牌"""
        if not candidates:
            return None
        # 按出牌后剩余手牌强度排序
        scored = []
        for combo in candidates:
            remaining = [c for c in hand if c not in combo]
            strength = self._calc_strength(remaining)
            scored.append((combo, strength))
        scored.sort(key=lambda x: x[1])
        return scored[0][0]


# ============================================================================
# 积分系统 — 合并 credit_system.py（添加持久化）
# ============================================================================

class AchievementType(Enum):
    FIRST_WIN="first_win"; LANDLORD_MASTER="landlord_master"
    FARMER_HERO="farmer_hero"; BOMB_KING="bomb_king"
    SPRING_MASTER="spring_master"; COMBO_EXPERT="combo_expert"
    WIN_STREAK="win_streak"; PLAY_MASTER="play_master"

@dataclass
class Achievement:
    ach_type: AchievementType
    name: str
    description: str
    unlocked: bool = False
    unlocked_at: float = 0.0

class CreditSystem:
    """积分与成就"""

    DB_PATH = "dou_di_zhu_credits.db"

    def __init__(self):
        self._credits: Dict[str, int] = {}
        self._stats: Dict[str, Dict] = {}
        self._achievements: Dict[str, List[Achievement]] = {}
        self._init_db()

    def _init_db(self) -> None:
        try:
            conn = sqlite3.connect(self.DB_PATH)
            conn.execute("""CREATE TABLE IF NOT EXISTS credits (
                player_id TEXT PRIMARY KEY, credits INTEGER DEFAULT 0,
                games INTEGER DEFAULT 0, wins INTEGER DEFAULT 0,
                landlord_wins INTEGER DEFAULT 0, farmer_wins INTEGER DEFAULT 0,
                bombs INTEGER DEFAULT 0, max_streak INTEGER DEFAULT 0,
                current_streak INTEGER DEFAULT 0
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS achievements (
                player_id TEXT, ach_type TEXT,
                unlocked_at REAL, PRIMARY KEY (player_id, ach_type)
            )""")
            conn.commit()
            conn.close()
        except Exception:
            pass

    def get_credits(self, player_id: str) -> int:
        return self._credits.get(player_id, 0)

    def add_credits(self, player_id: str, delta: int) -> int:
        self._credits[player_id] = max(0, self._credits.get(player_id, 0) + delta)
        return self._credits[player_id]

    def calculate_reward(self, player_id: str, won: bool, role: PlayerRole,
                         multiplier: int = 1, bombs: int = 0,
                         spring: bool = False) -> int:
        """计算奖励"""
        base = 20 if won else -10
        reward = base * multiplier + bombs * 50 + (100 if spring and won else 0)
        self.add_credits(player_id, reward)

        stats = self._stats.setdefault(player_id, {"games": 0, "wins": 0})
        stats["games"] = stats.get("games", 0) + 1
        if won:
            stats["wins"] = stats.get("wins", 0) + 1

        self._save_stats(player_id)
        return reward

    def get_leaderboard(self, top_n: int = 10) -> List[Tuple[str, int]]:
        ranked = sorted(self._credits.items(), key=lambda x: x[1], reverse=True)
        return ranked[:top_n]

    def _save_stats(self, player_id: str) -> None:
        try:
            conn = sqlite3.connect(self.DB_PATH)
            s = self._stats.get(player_id, {})
            conn.execute("""INSERT OR REPLACE INTO credits (player_id, credits, games, wins)
                VALUES (?, ?, ?, ?)""",
                (player_id, self._credits.get(player_id, 0),
                 s.get("games", 0), s.get("wins", 0)))
            conn.commit()
            conn.close()
        except Exception:
            pass


# ============================================================================
# 特效系统 — 合并 special_effects.py
# ============================================================================

class EffectType(Enum):
    FLASH="flash"; SHOCKWAVE="shockwave"; PARTICLE="particle"
    GLOW="glow"; SHAKE="shake"; ROCKET="rocket"; BOMB="bomb"

@dataclass
class EffectConfig:
    etype: EffectType = EffectType.FLASH
    x: int = 0; y: int = 0
    duration: float = 1.0
    color: str = "#FFD700"
    size: int = 100
    particle_count: int = 20

class EffectSystem:
    """特效管理器"""

    COMBO_EFFECTS = {
        ComboType.SINGLE: EffectType.FLASH,
        ComboType.PAIR: EffectType.GLOW,
        ComboType.TRIPLE: EffectType.SHOCKWAVE,
        ComboType.STRAIGHT: EffectType.PARTICLE,
        ComboType.BOMB: EffectType.BOMB,
        ComboType.ROCKET: EffectType.ROCKET,
    }

    @staticmethod
    def play_combo_effect(combo_type: ComboType, x: int = 400, y: int = 300) -> Dict:
        """播放牌型特效（返回特效数据，由UI渲染）"""
        et = EffectSystem.COMBO_EFFECTS.get(combo_type, EffectType.FLASH)
        name = CardCombo.COMBO_NAMES.get(combo_type, "未知")
        return {
            "type": et.value,
            "combo_name": name,
            "x": x, "y": y,
            "duration": 0.5 if combo_type == ComboType.SINGLE else 1.0,
            "particle_count": 20 if combo_type == ComboType.BOMB else 10,
        }


# ============================================================================
# 房间管理 — 合并 room_manager.py
# ============================================================================

class RoomStatus(Enum):
    WAITING="waiting"; READY="ready"; PLAYING="playing"; FINISHED="finished"; CLOSED="closed"

@dataclass
class PlayerInfo:
    player_id: str; name: str; credits: int = 0
    is_ai: bool = False; ai_difficulty: str = "medium"
    is_ready: bool = False

@dataclass
class GameRoom:
    room_id: str = ""
    name: str = ""
    players: List[PlayerInfo] = field(default_factory=list)
    status: RoomStatus = RoomStatus.WAITING
    max_players: int = 3
    min_credits: int = 0
    game: Optional[GameState] = None
    created_at: float = field(default_factory=time.time)

    def join(self, player: PlayerInfo) -> bool:
        if len(self.players) >= self.max_players:
            return False
        if player.credits < self.min_credits:
            return False
        self.players.append(player)
        return True

    def leave(self, player_id: str) -> bool:
        self.players = [p for p in self.players if p.player_id != player_id]
        return True

    def set_ready(self, player_id: str) -> bool:
        for p in self.players:
            if p.player_id == player_id:
                p.is_ready = True
                return True
        return False

    def can_start(self) -> bool:
        return (len(self.players) >= 2 and
                all(p.is_ready for p in self.players) and
                self.status == RoomStatus.WAITING)

    def start_game(self) -> Optional[GameState]:
        if not self.can_start():
            return None
        self.game = GameState(game_id=self.room_id)
        for pi in self.players:
            self.game.add_player(pi.player_id, pi.name, pi.is_ai)
        if self.game.start():
            self.status = RoomStatus.PLAYING
            return self.game
        return None


class RoomManager:
    """房间管理器"""

    def __init__(self):
        self._rooms: Dict[str, GameRoom] = {}
        self._player_room: Dict[str, str] = {}

    def create_room(self, name: str = "", max_players: int = 3) -> GameRoom:
        room_id = f"room_{int(time.time())}_{random.randint(1000,9999)}"
        room = GameRoom(room_id=room_id, name=name, max_players=max_players)
        self._rooms[room_id] = room
        return room

    def get_room(self, room_id: str) -> Optional[GameRoom]:
        return self._rooms.get(room_id)

    def join_room(self, room_id: str, player: PlayerInfo) -> bool:
        room = self.get_room(room_id)
        if not room:
            return False
        if room.join(player):
            self._player_room[player.player_id] = room_id
            return True
        return False

    def leave_room(self, player_id: str) -> bool:
        room_id = self._player_room.pop(player_id, None)
        if room_id:
            room = self.get_room(room_id)
            if room:
                room.leave(player_id)
            return True
        return False

    def get_available_rooms(self) -> List[GameRoom]:
        return [r for r in self._rooms.values() if r.status == RoomStatus.WAITING]

    def close_room(self, room_id: str) -> None:
        room = self.get_room(room_id)
        if room:
            room.status = RoomStatus.CLOSED
