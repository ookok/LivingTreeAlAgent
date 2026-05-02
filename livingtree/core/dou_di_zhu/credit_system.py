# -*- coding: utf-8 -*-
"""
斗地主积分与成就系统
Credit and Achievement System for Dou Di Zhu

作者：Hermes Desktop V2.0
版本：1.0.0
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class AchievementType(Enum):
    """成就类型"""
    FIRST_WIN = "first_win"              # 首胜
    LANDLORD_MASTER = "landlord_master"  # 地主大师
    FARMER_HERO = "farmer_hero"          # 农民英雄
    BOMB_KING = "bomb_king"              # 炸弹之王
    SPRING_MASTER = "spring_master"       # 春天专家
    COMBO_EXPERT = "combo_expert"        # 连招专家
    WIN_STREAK = "win_streak"            # 连胜
    PLAY_MASTER = "play_master"           # 对局大师


@dataclass
class Achievement:
    """成就"""
    type: AchievementType
    name: str
    description: str
    credits: int
    icon: str
    unlocked: bool = False
    unlocked_at: Optional[datetime] = None

    def to_dict(self) -> Dict:
        return {
            "type": self.type.value,
            "name": self.name,
            "description": self.description,
            "credits": self.credits,
            "icon": self.icon,
            "unlocked": self.unlocked,
            "unlocked_at": self.unlocked_at.isoformat() if self.unlocked_at else None
        }


class DouDiZhuCreditSystem:
    """斗地主积分系统"""

    def __init__(self):
        self.base_scores = {
            "win": 100,
            "lose": -50,
            "draw": 0
        }

        self.player_credits: Dict[str, int] = {}
        self.player_achievements: Dict[str, List[str]] = {}
        self.player_stats: Dict[str, Dict] = {}
        self.achievements = self._init_achievements()

    def _init_achievements(self) -> Dict[str, Achievement]:
        """初始化成就列表"""
        return {
            "first_win": Achievement(
                AchievementType.FIRST_WIN,
                "首胜",
                "赢得第一场对局",
                100,
                "🏆"
            ),
            "landlord_master": Achievement(
                AchievementType.LANDLORD_MASTER,
                "地主大师",
                "作为地主获胜10次",
                500,
                "👑"
            ),
            "farmer_hero": Achievement(
                AchievementType.FARMER_HERO,
                "农民英雄",
                "作为农民获胜10次",
                500,
                "🧑‍🌾"
            ),
            "bomb_king": Achievement(
                AchievementType.BOMB_KING,
                "炸弹之王",
                "在一局中打出3个炸弹",
                300,
                "💣"
            ),
            "spring_master": Achievement(
                AchievementType.SPRING_MASTER,
                "春天专家",
                "打出一次春天",
                400,
                "🌸"
            ),
            "combo_expert": Achievement(
                AchievementType.COMBO_EXPERT,
                "连招专家",
                "一次性打出5连及以上牌型",
                300,
                "🔥"
            ),
            "win_streak": Achievement(
                AchievementType.WIN_STREAK,
                "连胜",
                "连续获胜3次",
                400,
                "⚡"
            ),
            "play_master": Achievement(
                AchievementType.PLAY_MASTER,
                "对局大师",
                "完成100场对局",
                1000,
                "🎮"
            )
        }

    def get_player_credits(self, player_id: str) -> int:
        """获取玩家积分"""
        return self.player_credits.get(player_id, 0)

    def add_credits(self, player_id: str, credits: int) -> int:
        """添加积分"""
        if player_id not in self.player_credits:
            self.player_credits[player_id] = 0

        self.player_credits[player_id] += credits

        # 积分不能为负
        if self.player_credits[player_id] < 0:
            self.player_credits[player_id] = 0

        return self.player_credits[player_id]

    def calculate_reward(self, game_result: Dict) -> Dict:
        """计算奖励"""
        player_id = game_result["player_id"]
        is_winner = game_result["is_winner"]
        is_landlord = game_result["is_landlord"]
        game_stats = game_result.get("stats", {})

        # 初始化玩家数据
        if player_id not in self.player_stats:
            self.player_stats[player_id] = {
                "total_games": 0,
                "wins": 0,
                "landlord_wins": 0,
                "farmer_wins": 0,
                "bombs_played": 0,
                "springs_played": 0,
                "max_combo": 0,
                "win_streak": 0,
                "max_win_streak": 0
            }

        stats = self.player_stats[player_id]
        stats["total_games"] += 1

        if is_winner:
            stats["wins"] += 1
            stats["win_streak"] += 1
            stats["max_win_streak"] = max(stats["max_win_streak"], stats["win_streak"])

            if is_landlord:
                stats["landlord_wins"] += 1
            else:
                stats["farmer_wins"] += 1
        else:
            stats["win_streak"] = 0

        stats["bombs_played"] += game_stats.get("bomb_count", 0)
        stats["springs_played"] += 1 if game_stats.get("is_spring", False) else 0
        stats["max_combo"] = max(stats["max_combo"], game_stats.get("max_combo", 0))

        # 基础积分
        base_credits = self.base_scores["win"] if is_winner else self.base_scores["lose"]

        # 倍数奖励
        multiple_bonus = game_result.get("multiple", 1) * 20

        # 炸弹奖励
        bomb_bonus = game_stats.get("bomb_count", 0) * 50

        # 春天奖励
        spring_bonus = 100 if game_stats.get("is_spring", False) else 0

        # 连招奖励
        combo_bonus = self._calculate_combo_bonus(game_stats.get("combos", []))

        # 总积分
        total_credits = base_credits + multiple_bonus + bomb_bonus + spring_bonus + combo_bonus

        # 添加积分
        final_credits = self.add_credits(player_id, total_credits)

        # 检查成就
        new_achievements = self._check_achievements(player_id, stats)

        # 添加成就积分
        achievement_credits = sum(self.achievements[a].credits for a in new_achievements)
        for a in new_achievements:
            self.achievements[a].unlocked = True
            self.achievements[a].unlocked_at = datetime.now()
            self.achievements[a].credits = 0  # 已领取

        final_credits = self.add_credits(player_id, achievement_credits)

        # 更新成就记录
        if player_id not in self.player_achievements:
            self.player_achievements[player_id] = []
        self.player_achievements[player_id].extend(new_achievements)

        return {
            "player_id": player_id,
            "total_credits": final_credits,
            "breakdown": {
                "base": base_credits,
                "multiple_bonus": multiple_bonus,
                "bomb_bonus": bomb_bonus,
                "spring_bonus": spring_bonus,
                "combo_bonus": combo_bonus,
                "achievement_credits": achievement_credits
            },
            "new_achievements": new_achievements,
            "stats": stats
        }

    def _calculate_combo_bonus(self, combos: List[Dict]) -> int:
        """计算连招奖励"""
        bonus = 0

        for combo in combos:
            combo_type = combo.get("type", "")
            cards_count = len(combo.get("cards", []))

            if combo_type == "straight":
                bonus += cards_count * 2
            elif combo_type == "consecutive_pairs":
                bonus += combo.get("pairs", 0) * 3
            elif combo_type == "airplane":
                bonus += 50
            elif combo_type in ["bomb", "rocket"]:
                bonus += 30

        return bonus

    def _check_achievements(self, player_id: str, stats: Dict) -> List[str]:
        """检查成就"""
        new_achievements = []

        # 首胜
        if stats["wins"] == 1 and "first_win" not in self.player_achievements.get(player_id, []):
            new_achievements.append("first_win")

        # 地主大师
        if stats["landlord_wins"] >= 10 and "landlord_master" not in self.player_achievements.get(player_id, []):
            new_achievements.append("landlord_master")

        # 农民英雄
        if stats["farmer_wins"] >= 10 and "farmer_hero" not in self.player_achievements.get(player_id, []):
            new_achievements.append("farmer_hero")

        # 炸弹之王
        if stats["bombs_played"] >= 3 and "bomb_king" not in self.player_achievements.get(player_id, []):
            new_achievements.append("bomb_king")

        # 春天专家
        if stats["springs_played"] >= 1 and "spring_master" not in self.player_achievements.get(player_id, []):
            new_achievements.append("spring_master")

        # 连招专家
        if stats["max_combo"] >= 5 and "combo_expert" not in self.player_achievements.get(player_id, []):
            new_achievements.append("combo_expert")

        # 连胜
        if stats["max_win_streak"] >= 3 and "win_streak" not in self.player_achievements.get(player_id, []):
            new_achievements.append("win_streak")

        # 对局大师
        if stats["total_games"] >= 100 and "play_master" not in self.player_achievements.get(player_id, []):
            new_achievements.append("play_master")

        return new_achievements

    def get_player_achievements(self, player_id: str) -> List[Dict]:
        """获取玩家成就"""
        unlocked = self.player_achievements.get(player_id, [])
        result = []

        for key, achievement in self.achievements.items():
            ach_dict = achievement.to_dict()
            ach_dict["unlocked"] = key in unlocked
            result.append(ach_dict)

        return result

    def get_player_stats(self, player_id: str) -> Dict:
        """获取玩家统计"""
        return self.player_stats.get(player_id, {
            "total_games": 0,
            "wins": 0,
            "landlord_wins": 0,
            "farmer_wins": 0,
            "bombs_played": 0,
            "springs_played": 0,
            "max_combo": 0,
            "win_streak": 0,
            "max_win_streak": 0
        })

    def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        """获取排行榜"""
        sorted_players = sorted(
            self.player_credits.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limit]

        return [
            {
                "rank": i + 1,
                "player_id": player_id,
                "credits": credits
            }
            for i, (player_id, credits) in enumerate(sorted_players)
        ]
