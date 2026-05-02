# -*- coding: utf-8 -*-
"""
斗地主AI玩家
AI Player for Dou Di Zhu

作者：Hermes Desktop V2.0
版本：1.0.0
"""

import random
from typing import List, Dict, Optional
from collections import Counter, defaultdict
from .card_engine import Card, CardCombination
from .game_state import GameState, PlayerRole


class DouDiZhuAI:
    """斗地主AI"""

    def __init__(self, difficulty: str = "medium"):
        self.difficulty = difficulty
        self.game_state: Optional[GameState] = None
        self.memory = AIMemory()

        # 难度参数
        self.difficulty_params = {
            "easy": {"risk_tolerance": 0.3, "aggression": 0.2, "foresight": 2},
            "medium": {"risk_tolerance": 0.5, "aggression": 0.5, "foresight": 4},
            "hard": {"risk_tolerance": 0.7, "aggression": 0.8, "foresight": 8},
            "expert": {"risk_tolerance": 0.9, "aggression": 0.9, "foresight": 12}
        }

    def set_game_state(self, game_state: GameState):
        """设置游戏状态"""
        self.game_state = game_state

    def decide_bid(self, player_id: str) -> int:
        """决定叫地主分数"""
        params = self.difficulty_params[self.difficulty]

        player = self.game_state.players.get(player_id)
        if not player:
            return 0

        # 计算手牌强度
        hand_strength = self.calculate_hand_strength(player.cards)

        # 叫分策略
        if hand_strength > 0.8:
            return 3
        elif hand_strength > 0.6 and params["aggression"] > 0.5:
            return random.choice([2, 3])
        elif hand_strength > 0.4 and params["risk_tolerance"] > 0.4:
            return 1
        else:
            return 0

    def decide_play(self, player_id: str) -> Dict:
        """决定出牌"""
        params = self.difficulty_params[self.difficulty]

        player = self.game_state.players.get(player_id)
        if not player:
            return {"action": "pass", "cards": []}

        hand = player.cards
        last_combo = self.game_state.last_combo

        # 获取所有合法出牌
        valid_plays = self.get_valid_plays(hand, last_combo)

        if not valid_plays:
            return {"action": "pass", "cards": []}

        # AI决策
        if self.should_pass(hand, valid_plays, params):
            return {"action": "pass", "cards": []}

        # 选择最佳出牌
        best_play = self.select_best_play(hand, valid_plays, params)

        return {"action": "play", "cards": best_play}

    def calculate_hand_strength(self, cards: List[Card]) -> float:
        """计算手牌强度"""
        if not cards:
            return 0.0

        strength = 0.0

        # 基础价值
        card_values = [c.value for c in cards]
        avg_value = sum(card_values) / len(card_values)
        strength += avg_value / 20  # 归一化

        # 大牌数量
        big_cards = sum(1 for v in card_values if v >= 14)  # A, 2, 王
        strength += big_cards * 0.1

        # 炸弹数量
        bombs = self.find_bombs(cards)
        strength += len(bombs) * 0.2

        # 控制牌
        controls = self.find_controls(cards)
        strength += len(controls) * 0.15

        # 牌型完整性
        if self._has_complete_straight(cards):
            strength += 0.2
        if self._has_complete_pairs(cards):
            strength += 0.15

        return min(1.0, strength)

    def find_bombs(self, cards: List[Card]) -> List[List[Card]]:
        """找出所有炸弹"""
        bombs = []
        value_counts = Counter(c.value for c in cards)

        for value, count in value_counts.items():
            if count == 4:
                bomb = [c for c in cards if c.value == value]
                bombs.append(bomb)

        # 火箭
        jokers = [c for c in cards if c.is_joker]
        if len(jokers) == 2:
            bombs.append(jokers)

        return bombs

    def find_controls(self, cards: List[Card]) -> List[Card]:
        """找出控制牌（大牌）"""
        controls = []
        for card in cards:
            if card.value >= 14:  # A及以上
                controls.append(card)
        return controls

    def get_valid_plays(self, hand: List[Card], last_combo: Optional[Dict]) -> List[List[Card]]:
        """获取所有合法出牌"""
        all_combinations = self.generate_all_combinations(hand)
        valid_plays = []

        for combo_cards in all_combinations:
            combo_type = CardCombination.recognize(combo_cards)

            if not combo_type["valid"]:
                continue

            if last_combo is None or CardCombination.compare(last_combo, combo_type):
                valid_plays.append(combo_cards)

        return valid_plays

    def generate_all_combinations(self, hand: List[Card]) -> List[List[Card]]:
        """生成所有可能的牌组合"""
        cards = sorted(hand, key=lambda c: c.value)
        all_combos = []

        # 单张
        for card in cards:
            all_combos.append([card])

        # 对子
        value_counts = Counter(c.value for c in cards)
        for value, count in value_counts.items():
            if count >= 2:
                pair = [c for c in cards if c.value == value][:2]
                all_combos.append(pair)

        # 三张
        for value, count in value_counts.items():
            if count >= 3:
                triple = [c for c in cards if c.value == value][:3]
                all_combos.append(triple)

        # 顺子
        straights = self._find_straights(cards)
        all_combos.extend(straights)

        # 连对
        consecutive_pairs = self._find_consecutive_pairs(cards)
        all_combos.extend(consecutive_pairs)

        # 三带一/三带二
        triples = [[c for c in cards if c.value == value][:3]
                   for value, count in value_counts.items() if count >= 3]

        for triple in triples:
            # 三带一
            singles = [c for c in cards if c not in triple]
            for single in singles:
                all_combos.append(triple + [single])

            # 三带二
            pairs = [[c for c in cards if c.value == value][:2]
                     for value, count in value_counts.items() if count >= 2 and c not in triple for c in [c for c in cards if c.value == value][:2]]

        # 炸弹
        for value, count in value_counts.items():
            if count == 4:
                bomb = [c for c in cards if c.value == value]
                all_combos.append(bomb)

        # 火箭
        jokers = [c for c in cards if c.is_joker]
        if len(jokers) == 2:
            all_combos.append(jokers)

        return all_combos

    def _find_straights(self, cards: List[Card]) -> List[List[Card]]:
        """找出所有顺子"""
        straights = []
        values = sorted(set(c.value for c in cards if c.value < 15))  # 排除2和王

        if len(values) < 5:
            return straights

        # 找出所有连续顺子
        for start in range(len(values)):
            for end in range(start + 5, len(values) + 1):
                straight_values = values[start:end]
                if len(straight_values) >= 5:
                    is_consecutive = all(straight_values[i] - straight_values[i-1] == 1
                                       for i in range(1, len(straight_values)))
                    if is_consecutive:
                        straight_cards = [c for c in cards if c.value in straight_values]
                        # 每种花色取一张
                        straight = []
                        for v in straight_values:
                            for c in straight_cards:
                                if c.value == v and c not in straight:
                                    straight.append(c)
                                    break
                        if len(straight) == len(straight_values):
                            straights.append(straight)

        return straights

    def _find_consecutive_pairs(self, cards: List[Card]) -> List[List[Card]]:
        """找出所有连对"""
        pairs = []
        value_counts = Counter(c.value for c in cards)

        # 找出所有有对的值
        pair_values = [v for v, c in value_counts.items() if c >= 2 and v < 15]

        if len(pair_values) < 3:
            return pairs

        pair_values = sorted(pair_values)

        # 找出连续的对子
        for i in range(len(pair_values)):
            for j in range(i + 3, len(pair_values) + 1):
                consecutive = pair_values[i:j]
                if len(consecutive) >= 3:
                    is_consecutive = all(consecutive[k] - consecutive[k-1] == 1
                                        for k in range(1, len(consecutive)))
                    if is_consecutive:
                        consecutive_pair = []
                        for v in consecutive:
                            pair_cards = [c for c in cards if c.value == v][:2]
                            consecutive_pair.extend(pair_cards)
                        pairs.append(consecutive_pair)

        return pairs

    def _has_complete_straight(self, cards: List[Card]) -> bool:
        """检查是否有完整顺子"""
        return len(self._find_straights(cards)) > 0

    def _has_complete_pairs(self, cards: List[Card]) -> bool:
        """检查是否有连对"""
        return len(self._find_consecutive_pairs(cards)) > 0

    def should_pass(self, hand: List[Card], valid_plays: List[List[Card]],
                   params: Dict) -> bool:
        """判断是否应该过牌"""
        if not valid_plays:
            return True

        # 手牌很少时尽量出牌
        if len(hand) <= 2:
            return False

        # 有必赢牌不出
        if self.has_winning_hand(hand):
            return False

        # 根据难度随机过牌
        pass_chance = 0.3 - (params["aggression"] * 0.2)
        return random.random() < pass_chance

    def has_winning_hand(self, hand: List[Card]) -> bool:
        """检查是否有必赢手牌（只剩一张）"""
        return len(hand) == 1

    def select_best_play(self, hand: List[Card], valid_plays: List[List[Card]],
                        params: Dict) -> List[Card]:
        """选择最佳出牌"""
        if not valid_plays:
            return []

        # 评分每个出牌
        scored_plays = []
        for play in valid_plays:
            score = self.evaluate_play(play, hand, params)
            scored_plays.append((score, play))

        # 选择最高分
        scored_plays.sort(key=lambda x: x[0], reverse=True)

        # 根据难度加入随机性
        if random.random() < params["aggression"]:
            # 激进：选高分牌
            return scored_plays[0][1]
        else:
            # 保守：随机选择
            top_n = min(3, len(scored_plays))
            return random.choice(scored_plays[:top_n])[1]

    def evaluate_play(self, play: List[Card], hand: List[Card], params: Dict) -> float:
        """评估出牌分数"""
        score = 0.0

        # 1. 剩余手牌强度
        remaining_cards = [c for c in hand if c not in play]
        remaining_strength = self.calculate_hand_strength(remaining_cards)
        score += remaining_strength * 0.4

        # 2. 出牌威胁性
        play_strength = self.calculate_hand_strength(play)
        score += play_strength * 0.3

        # 3. 出牌效率
        if len(hand) - len(play) == 0:
            score += 1.0  # 出完牌

        # 4. 控制牌保留
        control_cards = [c for c in play if c.value >= 14]
        score -= len(control_cards) * 0.2

        # 5. 牌型价值
        combo_type = CardCombination.recognize(play)
        if combo_type["type"] in ["bomb", "rocket"]:
            score -= 0.1  # 不随便用炸弹

        # 6. 是否主动出牌（不是跟牌）
        if self.game_state and self.game_state.last_combo is None:
            score += 0.2  # 主动出牌加分

        return score


class AIMemory:
    """AI记忆系统"""

    def __init__(self, memory_size: int = 100):
        self.memory_size = memory_size
        self.game_history = defaultdict(list)
        self.player_profiles = defaultdict(dict)
        self.card_patterns = defaultdict(list)

    def record_game(self, player_id: str, game_data: Dict):
        """记录游戏"""
        self.game_history[player_id].append({
            "timestamp": game_data.get("timestamp"),
            "data": game_data
        })

        # 限制记忆大小
        if len(self.game_history[player_id]) > self.memory_size:
            self.game_history[player_id].pop(0)

        # 更新玩家档案
        self.update_player_profiles(player_id, game_data)

    def update_player_profiles(self, player_id: str, game_data: Dict):
        """更新玩家档案"""
        profile = self.player_profiles[player_id]

        # 记录出牌风格
        if "play_style" not in profile:
            profile["play_style"] = {
                "aggression": 0.5,
                "risk_taking": 0.5,
                "bluff_frequency": 0.5
            }

        # 更新风格
        style = profile["play_style"]
        game_aggression = game_data.get("aggression", 0.5)
        style["aggression"] = (style["aggression"] + game_aggression) / 2

    def predict_opponent_move(self, player_id: str, game_state: GameState) -> Dict:
        """预测对手行动"""
        profile = self.player_profiles.get(player_id, {})

        if not profile:
            return {"confidence": 0, "prediction": "unknown"}

        # 基于历史预测
        predictions = {
            "likely_combo": self._predict_likely_combo(player_id, game_state),
            "play_aggression": profile.get("play_style", {}).get("aggression", 0.5),
            "bluff_chance": profile.get("play_style", {}).get("bluff_frequency", 0.5)
        }

        return {
            "confidence": 0.7,
            "predictions": predictions
        }

    def _predict_likely_combo(self, player_id: str, game_state: GameState) -> str:
        """预测可能的牌型"""
        return "single"  # 默认预测单张
