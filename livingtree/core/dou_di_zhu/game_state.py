# -*- coding: utf-8 -*-
"""
斗地主游戏状态管理
Game State Management for Dou Di Zhu

作者：Hermes Desktop V2.0
版本：1.0.0
"""

from enum import Enum
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from .card_engine import CardDeck, CardCombination, Card


class GamePhase(Enum):
    """游戏阶段"""
    WAITING = "waiting"      # 等待开始
    DEALING = "dealing"      # 发牌阶段
    BIDDING = "bidding"      # 叫地主阶段
    PLAYING = "playing"      # 出牌阶段
    FINISHED = "finished"    # 结束阶段


class PlayerRole(Enum):
    """玩家角色"""
    FARMER = "farmer"    # 农民
    LANDLORD = "landlord"  # 地主


@dataclass
class PlayerState:
    """玩家状态"""
    player_id: str
    cards: List[Card] = field(default_factory=list)
    role: PlayerRole = PlayerRole.FARMER
    is_landlord: bool = False
    score: int = 0
    is_online: bool = True
    ready: bool = False
    last_action_time: Optional[datetime] = None
    is_current_turn: bool = False
    passed: bool = False
    name: str = ""

    def get_card_count(self) -> int:
        return len(self.cards)

    def has_cards(self, card_indices: List[int]) -> bool:
        """检查是否有这些牌"""
        if not card_indices:
            return True
        return all(0 <= idx < len(self.cards) for idx in card_indices)

    def remove_cards(self, card_indices: List[int]) -> List[Card]:
        """移除手牌"""
        if not self.has_cards(card_indices):
            return []

        # 从大到小排序索引，避免移除时索引变化
        indices_sorted = sorted(card_indices, reverse=True)
        removed_cards = []

        for idx in indices_sorted:
            removed_cards.append(self.cards.pop(idx))

        return removed_cards


class GameState:
    """游戏状态"""

    def __init__(self, room_id: str):
        self.room_id = room_id
        self.phase = GamePhase.WAITING
        self.players: Dict[str, PlayerState] = {}
        self.deck = CardDeck()
        self.bottom_cards: List[Card] = []
        self.current_turn: Optional[str] = None
        self.landlord: Optional[str] = None
        self.current_combo: Optional[Dict] = None
        self.last_combo: Optional[Dict] = None
        self.last_player: Optional[str] = None
        self.play_history: List[Dict] = []
        self.start_time: Optional[datetime] = None
        self.round_count = 0
        self.multiple = 1  # 倍数
        self.winner: Optional[str] = None
        self.winner_role: Optional[PlayerRole] = None
        self.bomb_count = 0
        self.is_spring = False
        self.landlord_first_play = True
        self.turn_timer: Optional[datetime] = None

    def add_player(self, player_id: str, name: str = "") -> bool:
        """添加玩家"""
        if player_id not in self.players and len(self.players) < 3:
            self.players[player_id] = PlayerState(player_id, [], name=name or f"玩家{len(self.players)+1}")
            return True
        return False

    def remove_player(self, player_id: str) -> bool:
        """移除玩家"""
        if player_id in self.players:
            del self.players[player_id]
            return True
        return False

    def start_game(self) -> bool:
        """开始游戏"""
        if len(self.players) != 3:
            return False

        self.phase = GamePhase.DEALING
        self.deck.shuffle()
        deal_result = self.deck.deal(3)

        # 发牌给玩家
        player_ids = list(self.players.keys())
        for i, player_id in enumerate(player_ids):
            self.players[player_id].cards = deal_result["hands"][f"player_{i}"]
            self.players[player_id].cards = self.deck.sort_hand(self.players[player_id].cards)

        self.bottom_cards = deal_result["bottom_cards"]

        # 进入叫地主阶段
        self.phase = GamePhase.BIDDING
        self.current_turn = player_ids[0]  # 从第一个玩家开始叫地主
        self.players[self.current_turn].is_current_turn = True
        self.start_time = datetime.now()

        return True

    def bid_landlord(self, player_id: str, bid_score: int) -> Dict:
        """叫地主"""
        if self.phase != GamePhase.BIDDING:
            return {"success": False, "error": "不是叫地主阶段"}

        if player_id != self.current_turn:
            return {"success": False, "error": "不是你的回合"}

        if bid_score not in [0, 1, 2, 3]:
            return {"success": False, "error": "无效的叫分"}

        # 记录叫分
        self.players[player_id].score = max(self.players[player_id].score, bid_score)

        # 记录历史
        self.play_history.append({
            "player_id": player_id,
            "action": "bid",
            "bid_score": bid_score,
            "timestamp": datetime.now()
        })

        # 确定下一个玩家
        player_ids = list(self.players.keys())
        current_idx = player_ids.index(player_id)

        # 如果叫了3分，立即结束
        if bid_score == 3:
            self._determine_landlord()
            return {"success": True, "bidding_ended": True}

        # 如果是最后一个玩家，检查是否都叫0
        if current_idx == 2:
            bids = [p.score for p in self.players.values()]
            if all(b == 0 for b in bids):
                # 没人叫，重新发牌
                return {"success": True, "redraw": True}

        # 继续叫地主
        next_idx = (current_idx + 1) % 3
        self.current_turn = player_ids[next_idx]

        # 更新当前回合状态
        for pid, p in self.players.items():
            p.is_current_turn = (pid == self.current_turn)

        return {"success": True, "bidding_ended": False}

    def _determine_landlord(self):
        """确定地主"""
        # 找出叫分最高的玩家
        max_score = -1
        landlord_id = None

        for player_id, player in self.players.items():
            if player.score > max_score:
                max_score = player.score
                landlord_id = player_id

        if landlord_id and max_score > 0:
            # 设置地主
            self.landlord = landlord_id
            self.players[landlord_id].role = PlayerRole.LANDLORD
            self.players[landlord_id].is_landlord = True

            # 地主获得底牌
            self.players[landlord_id].cards.extend(self.bottom_cards)
            self.players[landlord_id].cards = self.deck.sort_hand(
                self.players[landlord_id].cards
            )

            # 进入出牌阶段
            self.phase = GamePhase.PLAYING
            self.current_turn = landlord_id
            self.multiple = max_score

            # 更新回合状态
            for pid, p in self.players.items():
                p.is_current_turn = (pid == self.current_turn)
                p.passed = False
        else:
            # 没人叫地主，重新开始
            self.start_game()

    def play_cards(self, player_id: str, card_indices: List[int]) -> Dict:
        """出牌"""
        if self.phase != GamePhase.PLAYING:
            return {"success": False, "error": "不是出牌阶段"}

        if player_id != self.current_turn:
            return {"success": False, "error": "不是你的回合"}

        player = self.players[player_id]

        if not player.has_cards(card_indices):
            return {"success": False, "error": "无效的牌"}

        # 获取要出的牌
        cards_to_play = [player.cards[i] for i in card_indices]

        # 识别牌型
        combo = CardCombination.recognize(cards_to_play)

        if not combo["valid"]:
            return {"success": False, "error": "无效的牌型"}

        # 比较牌型
        if self.last_combo and not CardCombination.compare(self.last_combo, combo):
            return {"success": False, "error": "不能压过上家的牌"}

        # 记录炸弹
        if combo["type"] in ["bomb", "rocket"]:
            self.bomb_count += 1
            self.multiple *= 2

        # 记录是否地主第一次出牌
        if player.is_landlord and self.landlord_first_play:
            self.landlord_first_play = False

        # 移除手牌
        removed_cards = player.remove_cards(card_indices)

        # 更新游戏状态
        self.last_combo = combo
        self.last_player = player_id
        self.current_combo = combo
        player.passed = False
        player.last_action_time = datetime.now()

        # 记录历史
        self.play_history.append({
            "player_id": player_id,
            "cards": cards_to_play,
            "combo": combo,
            "timestamp": datetime.now(),
            "round": self.round_count
        })

        # 检查是否获胜
        if len(player.cards) == 0:
            self._end_game(player_id)
            return {"success": True, "game_over": True, "winner": player_id, "combo": combo}

        # 切换到下一个玩家
        self._next_turn()

        return {
            "success": True,
            "combo": combo,
            "cards_played": cards_to_play,
            "remaining_cards": len(player.cards)
        }

    def pass_turn(self, player_id: str) -> Dict:
        """过牌"""
        if self.phase != GamePhase.PLAYING:
            return {"success": False, "error": "不是出牌阶段"}

        if player_id != self.current_turn:
            return {"success": False, "error": "不是你的回合"}

        player = self.players[player_id]
        player.passed = True
        player.last_action_time = datetime.now()

        # 记录过牌历史
        self.play_history.append({
            "player_id": player_id,
            "action": "pass",
            "timestamp": datetime.now(),
            "round": self.round_count
        })

        # 如果是地主第一次过牌
        if player.is_landlord:
            self.landlord_first_play = False

        # 如果所有人都过牌，清空上家牌型
        passed_count = sum(1 for p in self.players.values() if p.passed)
        if passed_count >= 2:  # 两人过牌
            self.last_combo = None
            self.last_player = None

        # 切换到下一个玩家
        self._next_turn()

        return {"success": True, "action": "pass"}

    def _next_turn(self):
        """下一个回合"""
        player_ids = list(self.players.keys())
        current_idx = player_ids.index(self.current_turn)

        # 找到下一个未出完牌的玩家
        for i in range(1, 4):
            next_idx = (current_idx + i) % 3
            next_player_id = player_ids[next_idx]
            next_player = self.players[next_player_id]

            if len(next_player.cards) > 0:
                # 重置当前玩家状态
                self.players[self.current_turn].is_current_turn = False

                # 设置新玩家
                self.current_turn = next_player_id
                self.players[next_player_id].is_current_turn = True

                # 如果新玩家是上家，重置过牌状态
                if next_player_id == self.last_player:
                    for p in self.players.values():
                        p.passed = False

                self.turn_timer = datetime.now()
                break

        self.round_count += 1

    def _end_game(self, winner_id: str):
        """结束游戏"""
        self.phase = GamePhase.FINISHED
        self.winner = winner_id
        self.winner_role = self.players[winner_id].role

        # 检查是否春天
        self._check_spring()

        # 计算积分
        self._calculate_scores()

    def _check_spring(self):
        """判断是否春天"""
        landlord_plays = [p for p in self.play_history
                        if p.get("player_id") == self.landlord and "cards" in p]
        farmer_plays = [p for p in self.play_history
                       if p.get("player_id") != self.landlord and "cards" in p]

        if self.winner_role == PlayerRole.LANDLORD:
            # 地主赢：农民没出过牌
            self.is_spring = len(farmer_plays) == 0
        else:
            # 农民赢：地主只出过一次牌
            self.is_spring = len(landlord_plays) == 1

        if self.is_spring:
            self.multiple *= 2

    def _calculate_scores(self) -> Dict[str, int]:
        """计算积分"""
        # 基础分
        base_score = 1 * self.multiple

        # 分配积分
        results = {}
        landlord = self.landlord
        farmers = [pid for pid in self.players if pid != landlord]

        if self.winner_role == PlayerRole.LANDLORD:
            # 地主赢
            for farmer_id in farmers:
                self.players[farmer_id].score = -base_score
                results[farmer_id] = -base_score
            self.players[landlord].score = base_score * 2
            results[landlord] = base_score * 2
        else:
            # 农民赢
            for farmer_id in farmers:
                self.players[farmer_id].score = base_score
                results[farmer_id] = base_score
            self.players[landlord].score = -base_score * 2
            results[landlord] = -base_score * 2

        return results

    def get_valid_plays(self, player_id: str) -> List[List[int]]:
        """获取玩家所有合法出牌索引"""
        if self.phase != GamePhase.PLAYING:
            return []

        player = self.players.get(player_id)
        if not player:
            return []

        all_indices = list(range(len(player.cards)))
        valid_plays = []

        for i in range(len(all_indices)):
            for j in range(i + 1, len(all_indices) + 1):
                indices = all_indices[i:j]
                cards = [player.cards[idx] for idx in indices]
                combo = CardCombination.recognize(cards)

                if combo["valid"]:
                    if self.last_combo is None or CardCombination.compare(self.last_combo, combo):
                        valid_plays.append(indices)

        # 加上过牌
        if self.last_combo is not None:
            valid_plays.append([])  # 过牌

        return valid_plays

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "room_id": self.room_id,
            "phase": self.phase.value,
            "players": {
                pid: {
                    "player_id": p.player_id,
                    "name": p.name,
                    "cards_count": len(p.cards),
                    "role": p.role.value,
                    "is_landlord": p.is_landlord,
                    "score": p.score,
                    "is_current_turn": p.is_current_turn,
                    "passed": p.passed
                }
                for pid, p in self.players.items()
            },
            "landlord": self.landlord,
            "multiple": self.multiple,
            "current_turn": self.current_turn,
            "bomb_count": self.bomb_count,
            "is_spring": self.is_spring,
            "winner": self.winner,
            "round_count": self.round_count
        }
