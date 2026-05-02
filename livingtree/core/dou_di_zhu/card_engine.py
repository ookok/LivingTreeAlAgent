# -*- coding: utf-8 -*-
"""
斗地主卡牌引擎
Card Engine for Dou Di Zhu

作者：Hermes Desktop V2.0
版本：1.0.0
"""

from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
import random
from collections import Counter


class CardSuit(Enum):
    """花色枚举"""
    HEART = "♥"    # 红桃
    DIAMOND = "♦"  # 方块
    CLUB = "♣"    # 梅花
    SPADE = "♠"   # 黑桃
    JOKER = "🃏"   # 王


class CardRank(Enum):
    """牌值枚举"""
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11     # J
    QUEEN = 12    # Q
    KING = 13     # K
    ACE = 14      # A
    TWO = 15      # 2
    SMALL_JOKER = 16  # 小王
    BIG_JOKER = 17    # 大王


@dataclass
class Card:
    """单张卡牌"""
    suit: CardSuit
    rank: CardRank
    value: int
    is_joker: bool = False

    def __repr__(self):
        if self.is_joker:
            return f"{self.suit.value}"
        rank_char = self.rank.name[0] if self.rank.value <= 10 else self.rank.name[0]
        return f"{rank_char}{self.suit.value}"

    def get_image_key(self) -> str:
        """获取图片key"""
        if self.is_joker:
            if self.rank == CardRank.SMALL_JOKER:
                return "joker_black"
            else:
                return "joker_red"
        return f"{self.suit.name.lower()}_{self.rank.value}"

    def __lt__(self, other):
        """比较大小"""
        return self.value < other.value

    def __eq__(self, other):
        """等于"""
        return self.value == other.value and self.suit == other.suit


class CardDeck:
    """扑克牌堆"""

    def __init__(self):
        self.cards = self.create_deck()
        self.shuffle()

    def create_deck(self) -> List[Card]:
        """创建完整牌组（54张）"""
        cards = []

        # 常规牌
        for suit in [CardSuit.HEART, CardSuit.DIAMOND, CardSuit.CLUB, CardSuit.SPADE]:
            for rank in CardRank:
                if rank.value <= 15:  # 3-2
                    value = rank.value
                    cards.append(Card(suit, rank, value))

        # 大小王
        cards.append(Card(CardSuit.JOKER, CardRank.SMALL_JOKER, 16, True))
        cards.append(Card(CardSuit.JOKER, CardRank.BIG_JOKER, 17, True))

        return cards

    def shuffle(self):
        """洗牌"""
        random.shuffle(self.cards)

    def deal(self, player_count: int = 3) -> Dict[str, List[Card]]:
        """发牌"""
        # 每人17张，底牌3张
        hands = {f"player_{i}": [] for i in range(player_count)}

        for i in range(51):  # 51张牌
            player_idx = i % player_count
            hands[f"player_{player_idx}"].append(self.cards[i])

        # 底牌
        bottom_cards = self.cards[51:54]

        return {
            "hands": hands,
            "bottom_cards": bottom_cards,
            "remaining": []
        }

    def sort_hand(self, cards: List[Card], order: str = "desc") -> List[Card]:
        """手牌排序"""
        return sorted(cards,
                     key=lambda c: (c.value, c.suit.value),
                     reverse=(order == "desc"))


class CardCombination:
    """牌型识别"""

    @staticmethod
    def recognize(cards: List[Card]) -> Dict:
        """识别牌型"""
        if not cards:
            return {"type": "pass", "valid": True}

        cards = sorted(cards, key=lambda c: c.value)
        values = [c.value for c in cards]
        value_counts = Counter(values)

        # 单张
        if len(cards) == 1:
            return {"type": "single", "value": values[0], "valid": True}

        # 对子
        if len(cards) == 2 and len(set(values)) == 1:
            return {"type": "pair", "value": values[0], "valid": True}

        # 三张
        if len(cards) == 3 and len(set(values)) == 1:
            return {"type": "triple", "value": values[0], "valid": True}

        # 三带一
        if len(cards) == 4:
            if 3 in value_counts.values():
                main_value = next(k for k, v in value_counts.items() if v == 3)
                return {"type": "triple_with_single", "value": main_value, "valid": True}

        # 三带二
        if len(cards) == 5:
            if 3 in value_counts.values() and 2 in value_counts.values():
                main_value = next(k for k, v in value_counts.items() if v == 3)
                return {"type": "triple_with_pair", "value": main_value, "valid": True}

        # 顺子
        if len(cards) >= 5 and CardCombination._is_straight(values):
            return {"type": "straight", "length": len(cards), "value": values[0], "valid": True}

        # 连对
        if len(cards) >= 6 and len(cards) % 2 == 0:
            if CardCombination._is_consecutive_pairs(values, value_counts):
                return {"type": "consecutive_pairs", "pairs": len(cards)//2, "value": values[0], "valid": True}

        # 飞机
        if len(cards) >= 6 and CardCombination._is_airplane(values, value_counts):
            return {"type": "airplane", "valid": True}

        # 四带二
        if len(cards) == 6 and 4 in value_counts.values():
            return {"type": "four_with_two", "valid": True}

        # 炸弹
        if len(cards) == 4 and len(set(values)) == 1:
            return {"type": "bomb", "value": values[0], "valid": True}

        # 火箭
        if len(cards) == 2 and {16, 17} == set(values):
            return {"type": "rocket", "valid": True}

        return {"type": "invalid", "valid": False}

    @staticmethod
    def _is_straight(values: List[int]) -> bool:
        """判断顺子"""
        if 15 in values or 16 in values or 17 in values:  # 2和王不能进顺子
            return False

        sorted_values = sorted(set(values))
        if len(sorted_values) < 5:
            return False

        for i in range(1, len(sorted_values)):
            if sorted_values[i] - sorted_values[i-1] != 1:
                return False
        return True

    @staticmethod
    def _is_consecutive_pairs(values: List[int], value_counts: Counter) -> bool:
        """判断连对"""
        # 每个值必须正好出现2次
        for v in values:
            if value_counts[v] != 2:
                return False

        # 值必须连续
        unique_values = sorted(set(values))
        if len(unique_values) < 3:
            return False

        for i in range(1, len(unique_values)):
            if unique_values[i] - unique_values[i-1] != 1:
                return False

        return True

    @staticmethod
    def _is_airplane(values: List[int], value_counts: Counter) -> bool:
        """判断飞机"""
        # 找出所有出现3次或4次的值
        triple_values = [v for v, c in value_counts.items() if c >= 3]
        if len(triple_values) < 2:
            return False

        # 检查是否连续
        triple_values = sorted(triple_values)
        for i in range(1, len(triple_values)):
            if triple_values[i] - triple_values[i-1] != 1:
                return False

        # 检查总牌数是否匹配（每个三张至少带一个单张或对子）
        min_length = len(triple_values) * 3 + len(triple_values)  # 三张 + 单张/对子
        if len(values) < min_length:
            return False

        return True

    @staticmethod
    def compare(prev: Optional[Dict], current: Dict) -> bool:
        """比较牌型"""
        if not current["valid"]:
            return False

        if prev is None:
            return True

        if prev["type"] == "pass":
            return True

        # 火箭最大
        if current["type"] == "rocket":
            return True

        if prev["type"] == "rocket":
            return False

        # 炸弹比较
        if current["type"] == "bomb" and prev["type"] != "bomb":
            return True

        if current["type"] == "bomb" and prev["type"] == "bomb":
            return current["value"] > prev["value"]

        if current["type"] != "bomb" and prev["type"] == "bomb":
            return False

        # 同类型比较
        if current["type"] == prev["type"]:
            if current["type"] in ["single", "pair", "triple", "bomb"]:
                return current["value"] > prev["value"]
            elif current["type"] == "straight":
                return len(cards) == len(prev.get("cards", [])) and \
                       current["value"] > prev["value"]
            elif current["type"] == "consecutive_pairs":
                return len(cards) // 2 == prev["pairs"] and \
                       current["value"] > prev["value"]
            elif current["type"] == "triple_with_single":
                return current["value"] > prev["value"]
            elif current["type"] == "triple_with_pair":
                return current["value"] > prev["value"]

        return False

    @staticmethod
    def get_combo_name(combo_type: str) -> str:
        """获取牌型名称"""
        names = {
            "pass": "过",
            "single": "单张",
            "pair": "对子",
            "triple": "三张",
            "triple_with_single": "三带一",
            "triple_with_pair": "三带二",
            "straight": "顺子",
            "consecutive_pairs": "连对",
            "airplane": "飞机",
            "four_with_two": "四带二",
            "bomb": "炸弹",
            "rocket": "火箭",
            "invalid": "无效"
        }
        return names.get(combo_type, "未知")
