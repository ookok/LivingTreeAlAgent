# -*- coding: utf-8 -*-
"""
斗地主完整系统
Dou Di Zhu Complete System

作者：Hermes Desktop V2.0
版本：1.0.0

包含模块：
- card_engine: 卡牌与牌型识别
- game_state: 游戏状态管理
- ai_player: AI玩家智能
- credit_system: 积分与成就系统
- room_manager: 房间管理与匹配
- special_effects: 特效系统
"""

from .card_engine import (
    CardSuit,
    CardRank,
    Card,
    CardDeck,
    CardCombination
)

from .game_state import (
    GamePhase,
    PlayerRole,
    PlayerState,
    GameState
)

from .ai_player import (
    DouDiZhuAI,
    AIMemory
)

from .credit_system import (
    AchievementType,
    Achievement,
    DouDiZhuCreditSystem
)

from .room_manager import (
    RoomStatus,
    MatchMode,
    PlayerInfo,
    GameRoom,
    RoomManager,
    Matchmaking
)

from .special_effects import (
    EffectType,
    EffectConfig,
    EffectLayer,
    BaseEffect,
    FlashEffect,
    ShockwaveEffect,
    ParticleEffect,
    BombEffect,
    RocketEffect,
    CardEffectSystem
)


class DouDiZhuEngine:
    """斗地主游戏引擎 - 统一入口"""

    def __init__(self):
        # 核心组件
        self.game_state: Optional[GameState] = None
        self.ai_player = DouDiZhuAI("medium")
        self.credit_system = DouDiZhuCreditSystem()
        self.room_manager = RoomManager()
        self.matchmaking = Matchmaking(self.room_manager)
        self.effect_system = CardEffectSystem()

        # 当前房间
        self.current_room: Optional[GameRoom] = None
        self.current_player_id: Optional[str] = None

    def create_room(self, player_id: str, player_name: str, config: Dict = None) -> GameRoom:
        """创建房间"""
        room = self.room_manager.create_room(player_id, player_name, config)
        self.current_room = room
        self.current_player_id = player_id
        return room

    def join_room(self, room_id: str, player_id: str, player_name: str,
                  credits: int = 0, is_ai: bool = False,
                  difficulty: str = "medium") -> bool:
        """加入房间"""
        player_info = PlayerInfo(
            player_id=player_id,
            name=player_name,
            credits=credits,
            is_ai=is_ai,
            difficulty=difficulty
        )

        success = self.room_manager.join_room(room_id, player_info)
        if success:
            self.current_room = self.room_manager.get_room(room_id)
            self.current_player_id = player_id
        return success

    def leave_room(self) -> bool:
        """离开房间"""
        if not self.current_player_id:
            return False

        success = self.room_manager.leave_room(self.current_player_id)
        if success:
            self.current_room = None
            self.current_player_id = None
        return success

    def start_game(self) -> bool:
        """开始游戏"""
        if not self.current_room:
            return False

        # 开始游戏
        if not self.current_room.start_game():
            return False

        # 创建游戏状态
        self.game_state = GameState(self.current_room.room_id)

        # 添加玩家
        for player_id, player_info in self.current_room.players.items():
            self.game_state.add_player(player_id, player_info.name)

        # 如果人不够，添加AI
        while len(self.game_state.players) < 3:
            ai_id = f"ai_{len(self.game_state.players)}"
            self.game_state.add_player(ai_id, f"AI{len(self.game_state.players)}")

        # 设置AI游戏状态
        self.ai_player.set_game_state(self.game_state)

        # 开始发牌
        self.game_state.start_game()

        return True

    def set_ready(self, ready: bool) -> bool:
        """设置准备状态"""
        if not self.current_room or not self.current_player_id:
            return False

        return self.current_room.set_ready(self.current_player_id, ready)

    def bid_landlord(self, score: int) -> Dict:
        """叫地主"""
        if not self.game_state or not self.current_player_id:
            return {"success": False, "error": "游戏未开始"}

        result = self.game_state.bid_landlord(self.current_player_id, score)

        # 如果是AI回合，执行AI决策
        if result.get("success") and not result.get("bidding_ended"):
            self._execute_ai_bid()

        return result

    def play_cards(self, card_indices: List[int]) -> Dict:
        """出牌"""
        if not self.game_state or not self.current_player_id:
            return {"success": False, "error": "游戏未开始"}

        result = self.game_state.play_cards(self.current_player_id, card_indices)

        # 如果是AI回合，执行AI出牌
        if result.get("success") and not result.get("game_over"):
            self._execute_ai_play()

        # 如果游戏结束，处理积分
        if result.get("game_over"):
            self._handle_game_end(result.get("winner"))

        return result

    def pass_turn(self) -> Dict:
        """过牌"""
        if not self.game_state or not self.current_player_id:
            return {"success": False, "error": "游戏未开始"}

        result = self.game_state.pass_turn(self.current_player_id)

        # 如果是AI回合，执行AI出牌
        if result.get("success"):
            self._execute_ai_play()

        return result

    def _execute_ai_bid(self):
        """执行AI叫地主"""
        if not self.game_state:
            return

        # 找出AI玩家
        ai_players = [pid for pid in self.game_state.players
                     if pid.startswith("ai_")]

        for ai_id in ai_players:
            if self.game_state.current_turn == ai_id:
                # AI叫地主
                bid_score = self.ai_player.decide_bid(ai_id)
                self.game_state.bid_landlord(ai_id, bid_score)
                break

    def _execute_ai_play(self):
        """执行AI出牌"""
        if not self.game_state:
            return

        # 找出AI玩家
        ai_players = [pid for pid in self.game_state.players
                     if pid.startswith("ai_")]

        for ai_id in ai_players:
            if self.game_state.current_turn == ai_id:
                # AI出牌
                ai_decision = self.ai_player.decide_play(ai_id)

                if ai_decision["action"] == "pass":
                    self.game_state.pass_turn(ai_id)
                else:
                    cards = ai_decision["cards"]
                    # 找到牌的索引
                    indices = []
                    for card in cards:
                        for i, c in enumerate(self.game_state.players[ai_id].cards):
                            if c == card:
                                indices.append(i)
                                break

                    if indices:
                        self.game_state.play_cards(ai_id, indices)
                break

    def _handle_game_end(self, winner_id: str):
        """处理游戏结束"""
        if not self.game_state:
            return

        winner = self.game_state.players.get(winner_id)
        if not winner:
            return

        # 计算每个玩家的奖励
        for player_id, player in self.game_state.players.items():
            is_winner = player_id == winner_id
            is_landlord = player.is_landlord

            game_result = {
                "player_id": player_id,
                "is_winner": is_winner,
                "is_landlord": is_landlord,
                "multiple": self.game_state.multiple,
                "stats": {
                    "bomb_count": self.game_state.bomb_count,
                    "is_spring": self.game_state.is_spring,
                    "combos": [h.get("combo") for h in self.game_state.play_history
                              if "combo" in h]
                }
            }

            reward = self.credit_system.calculate_reward(game_result)

        # 更新房间状态
        if self.current_room:
            self.current_room.status = RoomStatus.FINISHED

    def get_hint(self) -> List[int]:
        """获取出牌提示"""
        if not self.game_state or not self.current_player_id:
            return []

        player = self.game_state.players.get(self.current_player_id)
        if not player:
            return []

        valid_plays = self.game_state.get_valid_plays(self.current_player_id)

        if not valid_plays:
            return []

        # 返回最优出牌（最有把握赢的）
        best_play = valid_plays[0]  # 默认选第一个

        return best_play

    def get_game_state(self) -> Optional[Dict]:
        """获取游戏状态"""
        if not self.game_state:
            return None

        state = self.game_state.to_dict()

        # 添加当前玩家的手牌
        if self.current_player_id and self.current_player_id in self.game_state.players:
            player = self.game_state.players[self.current_player_id]
            state["my_cards"] = [str(c) for c in player.cards]
            state["my_role"] = player.role.value
            state["my_is_landlord"] = player.is_landlord

        # 添加底牌
        state["bottom_cards"] = [str(c) for c in self.game_state.bottom_cards]

        # 添加最后出牌
        if self.game_state.last_combo:
            state["last_combo"] = self.game_state.last_combo

        return state

    def get_player_info(self, player_id: str) -> Optional[Dict]:
        """获取玩家信息"""
        stats = self.credit_system.get_player_stats(player_id)
        achievements = self.credit_system.get_player_achievements(player_id)
        credits = self.credit_system.get_player_credits(player_id)

        return {
            "player_id": player_id,
            "credits": credits,
            "stats": stats,
            "achievements": achievements
        }

    def get_leaderboard(self) -> List[Dict]:
        """获取排行榜"""
        return self.credit_system.get_leaderboard()


# 导出主要类
__all__ = [
    # 核心枚举
    "CardSuit",
    "CardRank",
    "GamePhase",
    "PlayerRole",
    "RoomStatus",
    "MatchMode",
    "EffectType",
    "AchievementType",

    # 核心类
    "Card",
    "CardDeck",
    "CardCombination",
    "PlayerState",
    "GameState",
    "DouDiZhuAI",
    "AIMemory",
    "Achievement",
    "DouDiZhuCreditSystem",
    "PlayerInfo",
    "GameRoom",
    "RoomManager",
    "Matchmaking",
    "CardEffectSystem",

    # 特效类
    "EffectConfig",
    "EffectLayer",
    "BaseEffect",
    "FlashEffect",
    "ShockwaveEffect",
    "ParticleEffect",
    "BombEffect",
    "RocketEffect",

    # 引擎
    "DouDiZhuEngine"
]
