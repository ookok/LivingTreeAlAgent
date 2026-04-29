# living_tree_game/__init__.py
# 生命之树AI的趣味游戏生态系统
# 核心理念："将严肃的积分经济转化为有趣的生命探索，让用户在游戏中自然参与生态建设"

import asyncio
import uuid
import random
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import math


# ==================== 基础枚举和模型 ====================

class TreasureRarity(Enum):
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"

class Weather(Enum):
    SUNNY = "sunny"
    RAINY = "rainy"
    FOGGY = "foggy"
    STORMY = "stormy"

class Season(Enum):
    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"

class TreeStage(Enum):
    SEED = "seed"
    SAPLING = "sapling"
    YOUNG = "young"
    MATURE = "mature"
    ANCIENT = "ancient"
    WORLD_TREE = "world_tree"


# ==================== 森林探险挖宝系统 ====================

class ForestAdventure:
    """森林探险挖宝系统"""

    def __init__(self):
        self.treasure_distribution = {
            "common": {
                "rusty_key": {"credits": 10, "weight": 20},
                "ancient_coin": {"credits": 20, "weight": 15},
                "crystal_shard": {"credits": 30, "weight": 10},
                "herb_bundle": {"credits": 15, "weight": 15},
            },
            "uncommon": {
                "silver_pendant": {"credits": 50, "weight": 8},
                "enchanted_acorn": {"credits": 75, "weight": 6},
                "druid_scroll": {"credits": 100, "weight": 5},
                "tree_sapling": {"credits": 60, "weight": 6},
            },
            "rare": {
                "golden_root": {"credits": 200, "weight": 3},
                "phoenix_feather": {"credits": 300, "weight": 2},
                "moonstone": {"credits": 250, "weight": 3},
                "wisdom_seed": {"credits": 400, "weight": 2},
            },
            "epic": {
                "tree_heart": {"credits": 1000, "weight": 1},
                "forest_crown": {"credits": 1500, "weight": 0.5},
                "dragon_scale": {"credits": 1200, "weight": 0.8},
                "star_fruit": {"credits": 2000, "weight": 0.5},
            },
            "legendary": {
                "world_tree_leaf": {"credits": 5000, "weight": 0.2},
                "immortal_sap": {"credits": 10000, "weight": 0.1},
                "cosmic_acorn": {"credits": 8888, "weight": 0.1},
            }
        }

        self.environment_factors = {
            "weather": {"sunny": 1.0, "rainy": 1.2, "foggy": 0.8, "stormy": 0.5},
            "time": {"morning": 1.1, "noon": 1.0, "evening": 1.3, "night": 0.7},
            "season": {"spring": 1.2, "summer": 1.0, "autumn": 1.5, "winter": 0.6},
            "location": {"forest_edge": 0.8, "deep_forest": 1.5, "riverbank": 1.1, "mountain": 1.3}
        }

        self.user_stamina = defaultdict(lambda: 100)
        self.user_luck = defaultdict(lambda: 50)
        self.daily_earnings = defaultdict(lambda: {"total": 0, "dig_treasure": 0})
        self.dig_history = defaultdict(list)

    def get_treasure_name(self, item_id: str) -> str:
        names = {
            "rusty_key": "生锈的钥匙",
            "ancient_coin": "古钱币",
            "crystal_shard": "水晶碎片",
            "herb_bundle": "草药束",
            "silver_pendant": "银质吊坠",
            "enchanted_acorn": "附魔橡果",
            "druid_scroll": "德鲁伊卷轴",
            "tree_sapling": "树苗",
            "golden_root": "金根",
            "phoenix_feather": "凤凰羽毛",
            "moonstone": "月光石",
            "wisdom_seed": "智慧种子",
            "tree_heart": "树心",
            "forest_crown": "森林之冠",
            "dragon_scale": "龙鳞",
            "star_fruit": "星辰果",
            "world_tree_leaf": "世界树叶",
            "immortal_sap": "永恒树液",
            "cosmic_acorn": "宇宙橡果",
        }
        return names.get(item_id, item_id)

    def get_treasure_icon(self, item_id: str) -> str:
        icons = {
            "rusty_key": "🗝️", "ancient_coin": "🪙", "crystal_shard": "💎",
            "herb_bundle": "🌿", "silver_pendant": "📿", "enchanted_acorn": "🌰",
            "druid_scroll": "📜", "tree_sapling": "🌱", "golden_root": "🟡",
            "phoenix_feather": "🪶", "moonstone": "🌙", "wisdom_seed": "🌾",
            "tree_heart": "💚", "forest_crown": "👑", "dragon_scale": "🐉",
            "star_fruit": "⭐", "world_tree_leaf": "🍃", "immortal_sap": "💧",
            "cosmic_acorn": "🌌",
        }
        return icons.get(item_id, "🎁")

    def get_treasure_description(self, item_id: str) -> str:
        descriptions = {
            "rusty_key": "一把年代久远的钥匙，似乎能打开什么...",
            "ancient_coin": "来自古老文明的硬币",
            "crystal_shard": "闪烁着微光的晶石碎片",
            "herb_bundle": "森林中采集的珍贵草药",
            "silver_pendant": "精致的银饰，蕴含魔力",
            "enchanted_acorn": "被德鲁伊祝福的橡果",
            "druid_scroll": "记载着古老咒语的卷轴",
            "tree_sapling": "一株充满活力的树苗",
            "golden_root": "金色的树根，价值连城",
            "phoenix_feather": "凤凰的羽毛，蕴含重生之力",
            "moonstone": "月光凝成的宝石",
            "wisdom_seed": "据说吃了能增长智慧的种子",
            "tree_heart": "千年古树的心材",
            "forest_crown": "森林之王的冠冕",
            "dragon_scale": "巨龙的鳞片，坚硬无比",
            "star_fruit": "来自星辰的果实",
            "world_tree_leaf": "世界树的叶子，见证永恒",
            "immortal_sap": "永恒之树的汁液",
            "cosmic_acorn": "宇宙孕育的神奇橡果",
        }
        return descriptions.get(item_id, "神秘的物品")

    def calculate_environment_multiplier(self) -> float:
        weather = random.choice(list(self.environment_factors["weather"].keys()))
        hour = datetime.now().hour
        if 6 <= hour < 12:
            time_period = "morning"
        elif 12 <= hour < 18:
            time_period = "noon"
        elif 18 <= hour < 22:
            time_period = "evening"
        else:
            time_period = "night"

        month = datetime.now().month
        if 3 <= month < 6:
            season = "spring"
        elif 6 <= month < 9:
            season = "summer"
        elif 9 <= month < 12:
            season = "autumn"
        else:
            season = "winter"

        weather_mult = self.environment_factors["weather"].get(weather, 1.0)
        time_mult = self.environment_factors["time"].get(time_period, 1.0)
        season_mult = self.environment_factors["season"].get(season, 1.0)

        return weather_mult * time_mult * season_mult

    async def check_stamina(self, user_id: str, cost: int) -> bool:
        return self.user_stamina[user_id] >= cost

    async def consume_stamina(self, user_id: str, cost: int):
        self.user_stamina[user_id] = max(0, self.user_stamina[user_id] - cost)

    async def get_stamina(self, user_id: str) -> int:
        return self.user_stamina[user_id]

    async def get_user_luck(self, user_id: str) -> int:
        return self.user_luck[user_id]

    async def get_daily_earnings(self, user_id: str) -> int:
        return self.daily_earnings[user_id]["dig_treasure"]

    async def record_dig(self, user_id: str, treasure: Dict, location: str):
        self.dig_history[user_id].append({
            "treasure": treasure,
            "location": location,
            "time": datetime.now().isoformat()
        })

    async def reward_credits(self, user_id: str, amount: int, source: str):
        self.daily_earnings[user_id]["total"] += amount
        self.daily_earnings[user_id][source] += amount

    async def suggest_better_location(self, user_id: str) -> str:
        locations = list(self.environment_factors["location"].keys())
        best = max(locations, key=lambda x: self.environment_factors["location"][x])
        return best

    def draw_treasure(self, multiplier: float) -> Dict:
        rarity_weights = {
            "common": 60 * (1 / multiplier),
            "uncommon": 25,
            "rare": 10 * multiplier,
            "epic": 4 * multiplier,
            "legendary": 1 * multiplier
        }

        total = sum(rarity_weights.values())
        rand = random.random() * total

        current = 0
        selected_rarity = "common"
        for rarity, weight in rarity_weights.items():
            current += weight
            if rand <= current:
                selected_rarity = rarity
                break

        treasure_pool = self.treasure_distribution[selected_rarity]
        treasure_items = list(treasure_pool.items())
        weights = [item[1]["weight"] for item in treasure_items]

        selected_item = random.choices(treasure_items, weights=weights, k=1)[0]
        item_id, item_info = selected_item

        return {
            "id": item_id,
            "name": self.get_treasure_name(item_id),
            "rarity": selected_rarity,
            "credits": item_info["credits"],
            "description": self.get_treasure_description(item_id),
            "icon": self.get_treasure_icon(item_id),
            "collection_value": item_info["credits"] * 1.5
        }

    async def generate_dig_animation(self, rarity: str) -> str:
        animations = {
            "common": "✨", "uncommon": "🌟", "rare": "💫", "epic": "🌈", "legendary": "🎆"
        }
        return animations.get(rarity, "✨")

    async def dig_for_treasure(self, user_id: str, location: str,
                              tool_level: int = 1) -> Dict:
        stamina_cost = 10
        if not await self.check_stamina(user_id, stamina_cost):
            return {"success": False, "error": "体力不足"}

        env_multiplier = self.calculate_environment_multiplier()
        luck = await self.get_user_luck(user_id)
        luck_multiplier = 1 + (luck / 100)
        tool_multiplier = 1 + (tool_level - 1) * 0.2

        total_multiplier = env_multiplier * luck_multiplier * tool_multiplier
        treasure = self.draw_treasure(total_multiplier)

        await self.consume_stamina(user_id, stamina_cost)

        daily_earned = await self.get_daily_earnings(user_id)
        max_daily = 10000
        if daily_earned + treasure["credits"] > max_daily:
            treasure["credits"] = max(0, max_daily - daily_earned)

        await self.reward_credits(user_id, treasure["credits"], "dig_treasure")
        await self.record_dig(user_id, treasure, location)

        return {
            "success": True,
            "location": location,
            "treasure": treasure,
            "animation": await self.generate_dig_animation(treasure["rarity"]),
            "environment_bonus": env_multiplier,
            "luck_bonus": luck_multiplier,
            "stamina_remaining": await self.get_stamina(user_id),
            "daily_earned": daily_earned + treasure["credits"],
            "next_better_location": await self.suggest_better_location(user_id)
        }


# ==================== 数字猜谜游戏 ====================

class NumberPuzzleGame:
    """数字猜谜游戏"""

    def __init__(self):
        self.active_puzzles = {}
        self.difficulty_levels = {
            "easy": {"digits": 3, "range": (1, 9), "guesses": 10, "base_reward": 50},
            "medium": {"digits": 4, "range": (0, 9), "guesses": 8, "base_reward": 100},
            "hard": {"digits": 5, "range": (0, 9), "guesses": 6, "base_reward": 200},
            "expert": {"digits": 6, "range": (0, 9), "guesses": 5, "base_reward": 500}
        }
        self.user_puzzle_stats = defaultdict(lambda: {"wins": 0, "losses": 0, "streak": 0})

    def generate_solution(self, digits: int, range_tuple: tuple) -> str:
        digits_list = []
        for _ in range(digits):
            d = random.randint(range_tuple[0], range_tuple[1])
            digits_list.append(str(d))
        return ''.join(digits_list)

    def validate_guess(self, guess: str, difficulty: str) -> bool:
        config = self.difficulty_levels.get(difficulty, {})
        digits = config.get("digits", 4)
        if len(guess) != digits:
            return False
        return guess.isdigit()

    def compare_guess(self, guess: str, solution: str) -> Dict:
        correct_positions = 0
        guess_counts = {}
        solution_counts = {}

        for i in range(len(solution)):
            g = guess[i]
            s = solution[i]
            guess_counts[g] = guess_counts.get(g, 0) + 1
            solution_counts[s] = solution_counts.get(s, 0) + 1
            if g == s:
                correct_positions += 1

        correct_numbers = 0
        for digit in set(guess_counts.keys()) | set(solution_counts.keys()):
            correct_numbers += min(guess_counts.get(digit, 0), solution_counts.get(digit, 0))
        correct_numbers -= correct_positions

        return {
            "correct_positions": correct_positions,
            "correct_numbers": correct_numbers,
            "total_digits": len(solution),
            "hint": f"{correct_positions}A{correct_numbers}B"
        }

    async def generate_first_hint(self, solution: str, difficulty: str) -> str:
        if difficulty == "easy":
            return f"提示：答案是{solution[0]}开头的数字"
        hint_digit = random.randint(0, len(solution) - 1)
        return f"提示：第{hint_digit + 1}位是{solution[hint_digit]}"

    async def generate_final_hint(self, puzzle: Dict) -> str:
        solution = puzzle["solution"]
        return f"最终提示：答案包含 {len(set(solution))} 个不同数字"

    async def get_next_hint_time(self, puzzle: Dict) -> int:
        return max(0, puzzle["guesses_remaining"] - 2)

    async def calculate_similarity_score(self, puzzle: Dict, result: Dict) -> float:
        total = result["total_digits"]
        correct = result["correct_positions"] + result["correct_numbers"]
        return correct / total if total > 0 else 0

    async def calculate_reward(self, puzzle: Dict, result: Dict) -> int:
        config = self.difficulty_levels[puzzle["difficulty"]]
        base = config["base_reward"]
        guesses_left = puzzle["guesses_remaining"]
        max_guesses = config["guesses"]

        efficiency = guesses_left / max_guesses
        streak_bonus = puzzle.get("streak_bonus", 0)

        reward = int(base * (1 + efficiency) * (1 + streak_bonus))
        return reward

    async def calculate_consolation(self, puzzle: Dict) -> int:
        config = self.difficulty_levels[puzzle["difficulty"]]
        return int(config["base_reward"] * 0.1)

    async def reward_credits(self, user_id: str, amount: int, source: str):
        pass

    async def get_daily_puzzle_earnings(self, user_id: str) -> int:
        return 0

    async def generate_success_animation(self, difficulty: str) -> str:
        return "🎉" if difficulty != "expert" else "🏆"

    async def start_puzzle(self, user_id: str, difficulty: str = "medium") -> Dict:
        config = self.difficulty_levels[difficulty]
        puzzle_id = f"puzzle_{uuid.uuid4().hex[:8]}"
        solution = self.generate_solution(config["digits"], config["range"])

        puzzle = {
            "puzzle_id": puzzle_id,
            "user_id": user_id,
            "difficulty": difficulty,
            "solution": solution,
            "guesses_remaining": config["guesses"],
            "guesses_made": 0,
            "guesses": [],
            "started_at": datetime.now().isoformat(),
            "time_limit": 300,
            "hints_available": 1 if difficulty != "easy" else 2,
            "streak_bonus": 0
        }

        self.active_puzzles[puzzle_id] = puzzle

        return {
            "puzzle_id": puzzle_id,
            "difficulty": difficulty,
            "digits": config["digits"],
            "guesses_remaining": config["guesses"],
            "time_limit": puzzle["time_limit"],
            "first_hint": await self.generate_first_hint(solution, difficulty)
        }

    async def make_guess(self, puzzle_id: str, guess: str) -> Dict:
        if puzzle_id not in self.active_puzzles:
            return {"success": False, "error": "谜题不存在"}

        puzzle = self.active_puzzles[puzzle_id]

        started = datetime.fromisoformat(puzzle["started_at"])
        if datetime.now() > started + timedelta(seconds=puzzle["time_limit"]):
            return {"success": False, "error": "时间到"}

        if not self.validate_guess(guess, puzzle["difficulty"]):
            return {"success": False, "error": "猜测格式错误"}

        result = self.compare_guess(guess, puzzle["solution"])

        puzzle["guesses"].append({
            "guess": guess,
            "result": result,
            "time": datetime.now().isoformat()
        })
        puzzle["guesses_made"] += 1
        puzzle["guesses_remaining"] -= 1

        if result["correct_positions"] == len(puzzle["solution"]):
            reward = await self.calculate_reward(puzzle, result)

            if puzzle["guesses_made"] == 1:
                puzzle["streak_bonus"] += 0.5

            daily_earned = await self.get_daily_puzzle_earnings(puzzle["user_id"])
            max_daily = 5000
            if daily_earned + reward > max_daily:
                reward = max(0, max_daily - daily_earned)

            await self.reward_credits(puzzle["user_id"], reward, "puzzle_solved")

            del self.active_puzzles[puzzle_id]

            return {
                "success": True,
                "solved": True,
                "solution": puzzle["solution"],
                "reward": reward,
                "guesses_used": puzzle["guesses_made"],
                "streak_bonus": puzzle["streak_bonus"],
                "perfect_bonus": puzzle["guesses_made"] == 1,
                "animation": await self.generate_success_animation(puzzle["difficulty"])
            }

        if puzzle["guesses_remaining"] <= 0:
            consolation = await self.calculate_consolation(puzzle)
            await self.reward_credits(puzzle["user_id"], consolation, "puzzle_failed")

            del self.active_puzzles[puzzle_id]

            return {
                "success": False,
                "solved": False,
                "solution": puzzle["solution"],
                "consolation": consolation,
                "hint": await self.generate_final_hint(puzzle)
            }

        return {
            "success": True,
            "solved": False,
            "result": result,
            "guesses_remaining": puzzle["guesses_remaining"],
            "next_hint_in": await self.get_next_hint_time(puzzle),
            "similarity_score": await self.calculate_similarity_score(puzzle, result)
        }


# ==================== 生命之树养成系统 ====================

class LifeTreeNurturing:
    """生命之树养成系统"""

    def __init__(self):
        self.tree_stages = {
            "seed": {"health": 100, "size": 1, "abilities": [], "growth_threshold": 50},
            "sapling": {"health": 300, "size": 3, "abilities": ["basic_photosynthesis"], "growth_threshold": 200},
            "young": {"health": 600, "size": 6, "abilities": ["produce_fruit", "attract_birds"], "growth_threshold": 500},
            "mature": {"health": 1000, "size": 10, "abilities": ["seasonal_bloom", "wisdom_seeds"], "growth_threshold": 1500},
            "ancient": {"health": 5000, "size": 20, "abilities": ["weather_control", "ecosystem_support"], "growth_threshold": 5000},
            "world_tree": {"health": 10000, "size": 50, "abilities": ["realm_connection", "cosmic_roots"], "growth_threshold": float('inf')}
        }

        self.user_trees = {}
        self.fruit_types = {
            "health_fruit": {"credits": 50, "heal": 100, "weight": 0.5},
            "wisdom_fruit": {"credits": 100, "xp_bonus": 1.5, "weight": 0.3},
            "golden_fruit": {"credits": 500, "rare": True, "weight": 0.1},
            "mystery_fruit": {"credits": 0, "random_effect": True, "weight": 0.1}
        }

    async def get_user_tree(self, user_id: str) -> Optional[Dict]:
        return self.user_trees.get(user_id)

    async def create_new_tree(self, user_id: str) -> Dict:
        tree = {
            "tree_id": f"tree_{uuid.uuid4().hex[:8]}",
            "user_id": user_id,
            "stage": "seed",
            "health": 100,
            "max_health": 100,
            "size": 1,
            "growth": 0,
            "happiness": 50,
            "experience": 0,
            "water_count": 0,
            "fertilize_count": 0,
            "last_watered": None,
            "last_fertilized": None,
            "planted_at": datetime.now().isoformat()
        }
        self.user_trees[user_id] = tree
        return tree

    async def water_tree(self, tree: Dict, item_id: str = None) -> Dict:
        tree["water_count"] += 1
        tree["last_watered"] = datetime.now().isoformat()
        tree["growth"] += 10
        tree["happiness"] = min(100, tree["happiness"] + 5)
        tree["health"] = min(tree["max_health"], tree["health"] + 20)
        return {"action": "water", "growth_gained": 10, "happiness_gained": 5}

    async def fertilize_tree(self, tree: Dict, item_id: str = None) -> Dict:
        tree["fertilize_count"] += 1
        tree["last_fertilized"] = datetime.now().isoformat()
        tree["growth"] += 25
        tree["happiness"] = min(100, tree["happiness"] + 10)
        return {"action": "fertilize", "growth_gained": 25, "happiness_gained": 10}

    async def prune_tree(self, tree: Dict, item_id: str = None) -> Dict:
        tree["growth"] += 5
        tree["happiness"] = min(100, tree["happiness"] + 3)
        return {"action": "prune", "growth_gained": 5, "happiness_gained": 3}

    async def talk_to_tree(self, tree: Dict, item_id: str = None) -> Dict:
        tree["happiness"] = min(100, tree["happiness"] + 2)
        tree["experience"] += 5
        return {"action": "talk", "exp_gained": 5, "happiness_gained": 2}

    async def sing_to_tree(self, tree: Dict, item_id: str = None) -> Dict:
        tree["happiness"] = min(100, tree["happiness"] + 5)
        tree["experience"] += 10
        return {"action": "sing", "exp_gained": 10, "happiness_gained": 5}

    async def meditate_with_tree(self, tree: Dict, item_id: str = None) -> Dict:
        tree["happiness"] = min(100, tree["happiness"] + 8)
        tree["experience"] += 15
        return {"action": "meditate", "exp_gained": 15, "happiness_gained": 8}

    async def check_growth_condition(self, tree: Dict) -> bool:
        current_stage = tree["stage"]
        stage_info = self.tree_stages.get(current_stage, {})
        threshold = stage_info.get("growth_threshold", float('inf'))
        return tree["growth"] >= threshold

    async def grow_tree_stage(self, tree: Dict):
        stages = list(TreeStage)
        current_idx = stages.index(TreeStage(tree["stage"]))
        if current_idx < len(stages) - 1:
            next_stage = stages[current_idx + 1]
            tree["stage"] = next_stage.value
            next_stage_info = self.tree_stages[next_stage.value]
            tree["max_health"] = next_stage_info["health"]
            tree["size"] = next_stage_info["size"]
            tree["health"] = tree["max_health"]

    async def calculate_daily_yield(self, tree: Dict) -> int:
        base_yield = tree["size"] * 10
        happiness_modifier = tree["happiness"] / 100
        stage_modifier = {"seed": 0.5, "sapling": 1, "young": 1.5, "mature": 2, "ancient": 3, "world_tree": 5}
        return int(base_yield * happiness_modifier * stage_modifier.get(tree["stage"], 1))

    async def calculate_growth_progress(self, tree: Dict) -> float:
        current_stage = tree["stage"]
        stage_info = self.tree_stages.get(current_stage, {})
        threshold = stage_info.get("growth_threshold", 1)
        progress = (tree["growth"] / threshold) * 100 if threshold != float('inf') else 100
        return min(100, progress)

    async def get_next_ability(self, tree: Dict) -> Optional[str]:
        current_stage = tree["stage"]
        stages = list(TreeStage)
        current_idx = stages.index(TreeStage(current_stage))
        if current_idx < len(stages) - 1:
            next_stage = stages[current_idx + 1]
            next_info = self.tree_stages.get(next_stage.value, {})
            new_abilities = next_info.get("abilities", [])
            return new_abilities[0] if new_abilities else None
        return None

    async def check_seasonal_event(self) -> Optional[Dict]:
        month = datetime.now().month
        events = {
            3: {"name": "春日萌芽", "bonus": 1.2},
            6: {"name": "夏日盛放", "bonus": 1.3},
            9: {"name": "秋日丰收", "bonus": 1.5},
            12: {"name": "冬日静养", "bonus": 0.8}
        }
        for m, event in events.items():
            if abs(month - m) <= 1:
                return event
        return None

    async def get_daily_tree_earnings(self, user_id: str) -> int:
        return 0

    async def reward_credits(self, user_id: str, amount: int, source: str):
        pass

    async def harvest_fruit(self, user_id: str, fruit_id: str, fruit_info: Dict):
        credits = fruit_info.get("credits", 0)
        if credits > 0:
            await self.reward_credits(user_id, credits, "tree_harvest")

    async def tree_produces_fruit(self, user_id: str) -> Dict:
        tree = await self.get_user_tree(user_id)

        if not tree or tree["stage"] in ["seed", "sapling"]:
            return {"success": False, "error": "树木还未成熟"}

        production_chance = 0.3 + tree["happiness"] * 0.003

        if random.random() < production_chance:
            fruits = list(self.fruit_types.items())
            weights = [f[1]["weight"] for f in fruits]
            fruit = random.choices(fruits, weights=weights, k=1)[0]
            fruit_id, fruit_info = fruit

            await self.harvest_fruit(user_id, fruit_id, fruit_info)

            return {
                "success": True,
                "produced": True,
                "fruit": fruit_info,
                "animation": await self.generate_fruit_animation(fruit_id),
                "tree_happiness": tree["happiness"],
                "next_chance": production_chance
            }

        return {"success": False, "produced": False, "next_chance": production_chance}

    async def generate_fruit_animation(self, fruit_id: str) -> str:
        icons = {"health_fruit": "🍎", "wisdom_fruit": "🍇", "golden_fruit": "🍊", "mystery_fruit": "🍄"}
        return icons.get(fruit_id, "🍎")

    async def nurture_tree(self, user_id: str, action: str, item_id: str = None) -> Dict:
        tree = await self.get_user_tree(user_id)
        if not tree:
            tree = await self.create_new_tree(user_id)

        actions = {
            "water": self.water_tree,
            "fertilize": self.fertilize_tree,
            "prune": self.prune_tree,
            "talk": self.talk_to_tree,
            "sing": self.sing_to_tree,
            "meditate": self.meditate_with_tree
        }

        if action not in actions:
            return {"success": False, "error": "无效操作"}

        result = await actions[action](tree, item_id)

        if await self.check_growth_condition(tree):
            await self.grow_tree_stage(tree)

        daily_yield = await self.calculate_daily_yield(tree)
        max_daily = 3000
        if daily_yield > max_daily:
            daily_yield = max_daily

        await self.reward_credits(user_id, daily_yield, "tree_nurturing")

        return {
            "success": True,
            "action": action,
            "tree": tree,
            "result": result,
            "daily_yield": daily_yield,
            "growth_progress": await self.calculate_growth_progress(tree),
            "next_ability": await self.get_next_ability(tree),
            "seasonal_event": await self.check_seasonal_event()
        }


# ==================== 生态小游戏合集 ====================

class EcologyMiniGames:
    """生态小游戏合集"""

    def __init__(self):
        self.games = {
            "pollination_race": {
                "name": "授粉竞赛", "description": "帮助蜜蜂在花间授粉",
                "max_score": 1000, "credits_per_point": 0.5, "daily_limit": 2000, "icon": "🐝"
            },
            "water_cycle": {
                "name": "水循环挑战", "description": "引导水滴完成循环",
                "max_score": 800, "credits_per_point": 0.8, "daily_limit": 1500, "icon": "💧"
            },
            "food_chain": {
                "name": "食物链平衡", "description": "维持生态平衡",
                "max_score": 1200, "credits_per_point": 0.6, "daily_limit": 1800, "icon": "🦎"
            },
            "seed_dispersal": {
                "name": "种子传播", "description": "帮助种子找到新家",
                "max_score": 1500, "credits_per_point": 0.4, "daily_limit": 2500, "icon": "🌬️"
            }
        }

        self.user_game_stats = defaultdict(lambda: defaultdict(lambda: {"high_score": 0, "plays": 0}))
        self.user_stamina = defaultdict(lambda: 100)

    async def check_stamina(self, user_id: str, cost: int) -> bool:
        return self.user_stamina[user_id] >= cost

    async def consume_stamina(self, user_id: str, cost: int):
        self.user_stamina[user_id] = max(0, self.user_stamina[user_id] - cost)

    async def get_stamina(self, user_id: str) -> int:
        return self.user_stamina[user_id]

    async def get_daily_game_earnings(self, user_id: str, game_id: str) -> int:
        return 0

    async def reward_credits(self, user_id: str, amount: int, source: str):
        pass

    async def unlock_achievement(self, user_id: str, achievement_id: str):
        pass

    async def generate_game_session(self, game_id: str) -> Dict:
        return {
            "session_id": f"session_{uuid.uuid4().hex[:8]}",
            "game_id": game_id,
            "started_at": datetime.now().isoformat(),
            "state": "playing"
        }

    async def simulate_game_play(self, game_session: Dict) -> int:
        return random.randint(500, 1000)

    async def update_high_score(self, user_id: str, game_id: str, score: int) -> int:
        stats = self.user_game_stats[user_id][game_id]
        if score > stats["high_score"]:
            stats["high_score"] = score
        stats["plays"] += 1
        return stats["high_score"]

    async def calculate_skill_improvement(self, game_id: str, score: int) -> float:
        max_score = self.games[game_id]["max_score"]
        return (score / max_score) * 0.1

    async def play_mini_game(self, user_id: str, game_id: str) -> Dict:
        if game_id not in self.games:
            return {"success": False, "error": "游戏不存在"}

        game_config = self.games[game_id]
        stamina_cost = 5

        if not await self.check_stamina(user_id, stamina_cost):
            return {"success": False, "error": "体力不足"}

        game_session = await self.generate_game_session(game_id)
        score = await self.simulate_game_play(game_session)

        credits_earned = int(score * game_config["credits_per_point"])

        daily_earned = await self.get_daily_game_earnings(user_id, game_id)
        if daily_earned + credits_earned > game_config["daily_limit"]:
            credits_earned = max(0, game_config["daily_limit"] - daily_earned)

        await self.reward_credits(user_id, credits_earned, f"mini_game_{game_id}")
        await self.consume_stamina(user_id, stamina_cost)

        if score >= game_config["max_score"] * 0.9:
            await self.unlock_achievement(user_id, f"master_{game_id}")

        return {
            "success": True,
            "game": game_id,
            "game_name": game_config["name"],
            "score": score,
            "credits": credits_earned,
            "high_score": await self.update_high_score(user_id, game_id, score),
            "game_session": game_session,
            "stamina_remaining": await self.get_stamina(user_id),
            "skill_improvement": await self.calculate_skill_improvement(game_id, score)
        }


# ==================== 季节庆典活动 ====================

class SeasonalFestival:
    """季节庆典活动"""

    def __init__(self):
        self.seasonal_events = {
            "spring_bloom": {
                "name": "春日花开", "duration": 14,
                "activities": ["flower_planting", "butterfly_collecting", "rain_dance"],
                "special_rewards": {"blossom_crown": 1000, "spring_spirit": 2000},
                "icon": "🌸", "color": "#FF69B4"
            },
            "summer_solstice": {
                "name": "夏至庆典", "duration": 7,
                "activities": ["bonfire", "stargazing", "firefly_chase"],
                "special_rewards": {"sun_charm": 1500, "midsummer_dream": 3000},
                "icon": "☀️", "color": "#FFD700"
            },
            "autumn_harvest": {
                "name": "秋日丰收", "duration": 21,
                "activities": ["fruit_picking", "leaf_collecting", "harvest_feast"],
                "special_rewards": {"harvest_horn": 1200, "golden_sheaf": 2500},
                "icon": "🍂", "color": "#FF8C00"
            },
            "winter_solstice": {
                "name": "冬至夜话", "duration": 14,
                "activities": ["snow_sculpting", "storytelling", "lantern_making"],
                "special_rewards": {"winter_star": 1800, "yuletide_cheer": 3500},
                "icon": "❄️", "color": "#87CEEB"
            }
        }

        self.active_events = {}
        self.user_event_participation = defaultdict(lambda: defaultdict(list))

    async def get_season(self) -> str:
        month = datetime.now().month
        if 3 <= month < 6:
            return "spring_bloom"
        elif 6 <= month < 9:
            return "summer_solstice"
        elif 9 <= month < 12:
            return "autumn_harvest"
        else:
            return "winter_solstice"

    async def decorate_tree_for_season(self, season: str):
        pass

    async def announce_event(self, event: Dict):
        pass

    async def set_community_goals(self, season: str) -> List[Dict]:
        return [
            {"goal": "participation_count", "target": 1000, "reward": 5000},
            {"goal": "activity_completions", "target": 5000, "reward": 10000}
        ]

    async def get_season_decorations(self, season: str) -> List[str]:
        decorations = {
            "spring_bloom": ["🌸", "🌷", "🦋", "🌻"],
            "summer_solstice": ["☀️", "🌻", "🔥", "⭐"],
            "autumn_harvest": ["🍂", "🎃", "🌾", "🍊"],
            "winter_solstice": ["❄️", "🎄", "🎁", "🕯️"]
        }
        return decorations.get(season, ["✨"])

    async def get_event_rules(self, season: str) -> Dict:
        return {"bonus_multiplier": 1.5, "special_items": True, "community_challenges": True}

    async def start_seasonal_event(self, season: str) -> Dict:
        if season not in self.seasonal_events:
            season = await self.get_season()

        event_config = self.seasonal_events[season]

        event = {
            "event_id": f"event_{uuid.uuid4().hex[:8]}",
            "season": season,
            "name": event_config["name"],
            "start_time": datetime.now().isoformat(),
            "end_time": (datetime.now() + timedelta(days=event_config["duration"])).isoformat(),
            "activities": event_config["activities"],
            "participants": set(),
            "total_contributions": 0,
            "community_goals": await self.set_community_goals(season),
            "icon": event_config["icon"],
            "color": event_config["color"]
        }

        self.active_events[event["event_id"]] = event
        await self.decorate_tree_for_season(season)
        await self.announce_event(event)

        return {
            "success": True,
            "event": event,
            "decorations": await self.get_season_decorations(season),
            "event_special_rules": await self.get_event_rules(season)
        }

    async def perform_activity(self, user_id: str, activity: str, season: str) -> int:
        return random.randint(10, 50)

    async def calculate_personal_reward(self, contribution: int, activity: str) -> int:
        return int(contribution * 0.5)

    async def calculate_community_bonus(self, total_contributions: int, goals: List[Dict]) -> int:
        for goal in goals:
            if total_contributions >= goal["target"]:
                return goal["reward"]
        return 0

    async def get_community_progress(self, event: Dict) -> Dict:
        progress = {}
        for goal in event.get("community_goals", []):
            target = goal["target"]
            current = min(event["total_contributions"], target)
            progress[goal["goal"]] = {"current": current, "target": target, "percentage": int(current / target * 100) if target > 0 else 0}
        return progress

    async def get_next_community_reward(self, event: Dict) -> Optional[Dict]:
        for goal in event.get("community_goals", []):
            if event["total_contributions"] < goal["target"]:
                return goal
        return None

    async def calculate_special_item_chance(self, contribution: int) -> float:
        return min(0.5, contribution / 100)

    async def get_daily_event_earnings(self, user_id: str) -> int:
        return 0

    async def reward_credits(self, user_id: str, amount: int, source: str):
        pass

    async def participate_in_event(self, user_id: str, event_id: str, activity: str) -> Dict:
        if event_id not in self.active_events:
            return {"success": False, "error": "活动不存在"}

        event = self.active_events[event_id]

        if activity not in event["activities"]:
            return {"success": False, "error": "活动不存在"}

        contribution = await self.perform_activity(user_id, activity, event["season"])

        event["participants"].add(user_id)
        event["total_contributions"] += contribution

        personal_reward = await self.calculate_personal_reward(contribution, activity)

        community_bonus = await self.calculate_community_bonus(event["total_contributions"], event["community_goals"])

        total_reward = personal_reward + community_bonus

        max_daily = 4000
        if total_reward > max_daily:
            total_reward = max_daily

        await self.reward_credits(user_id, total_reward, f"event_{activity}")

        return {
            "success": True,
            "activity": activity,
            "contribution": contribution,
            "personal_reward": personal_reward,
            "community_bonus": community_bonus,
            "total_reward": total_reward,
            "community_progress": await self.get_community_progress(event),
            "next_community_reward": await self.get_next_community_reward(event),
            "special_item_chance": await self.calculate_special_item_chance(contribution)
        }


# ==================== 分层验证积分系统 ====================

class LayeredCreditConsistency:
    """分层验证积分系统"""

    def __init__(self):
        self.validation_layers = ["immediate", "local_consensus", "cross_node", "final_settlement"]
        self.credit_ledger = {}
        self.smart_contracts = {}

    async def pre_validate(self, transaction: Dict) -> bool:
        required_fields = ["user_id", "type", "amount", "id"]
        return all(field in transaction for field in required_fields)

    async def immediate_validation(self, transaction: Dict) -> Dict:
        return {"layer": "immediate", "valid": True}

    async def local_consensus(self, transaction: Dict) -> Dict:
        return {"layer": "local_consensus", "valid": True}

    async def cross_node_verification(self, transaction: Dict) -> Dict:
        return {"layer": "cross_node", "valid": True}

    async def final_settlement(self, transaction: Dict) -> Dict:
        return {"layer": "final_settlement", "valid": True}

    async def execute_smart_contract(self, transaction: Dict) -> Dict:
        return {"success": True, "contract_id": transaction.get("id")}

    async def write_to_ledger(self, transaction: Dict, contract_result: Dict) -> Dict:
        proof = hashlib.sha256(str(transaction).encode()).hexdigest()[:16]
        self.credit_ledger[transaction["id"]] = {
            "transaction": transaction,
            "proof": proof,
            "timestamp": datetime.now().isoformat()
        }
        return {"proof": proof}

    async def broadcast_confirmation(self, transaction: Dict, ledger_result: Dict):
        pass

    async def get_confirmations(self, transaction_id: str) -> int:
        return random.randint(3, 10)

    async def estimate_finality_time(self, transaction: Dict) -> float:
        return random.uniform(1.0, 5.0)

    async def get_daily_stats(self, user_id: str) -> Dict:
        return defaultdict(int)

    async def enforce_daily_limits(self, user_id: str, transaction: Dict) -> bool:
        limits = {
            "dig_treasure": 10000, "puzzle_game": 5000, "tree_nurturing": 3000,
            "mini_games": 2500, "seasonal_event": 4000, "achievement_reward": 20000,
            "social_reward": 1000, "total_daily": 50000
        }

        daily_stats = await self.get_daily_stats(user_id)
        transaction_type = transaction.get("type", "")

        if daily_stats.get(transaction_type, 0) + transaction.get("amount", 0) > limits.get(transaction_type, float('inf')):
            return False

        if sum(daily_stats.values()) + transaction.get("amount", 0) > limits["total_daily"]:
            return False

        return True

    async def process_credit_transaction(self, transaction: Dict) -> Dict:
        if not await self.pre_validate(transaction):
            return {"success": False, "error": "预验证失败"}

        if not await self.enforce_daily_limits(transaction["user_id"], transaction):
            return {"success": False, "error": "超出每日上限"}

        validation_results = []
        for layer_name in self.validation_layers:
            layer_method = getattr(self, f"{layer_name}_validation", None)
            if layer_method:
                result = await layer_method(transaction)
                validation_results.append(result)
                if not result.get("valid"):
                    return {"success": False, "error": f"{layer_name}验证失败", "details": result}

        contract_result = await self.execute_smart_contract(transaction)
        if not contract_result.get("success"):
            return {"success": False, "error": "智能合约执行失败"}

        ledger_result = await self.write_to_ledger(transaction, contract_result)
        await self.broadcast_confirmation(transaction, ledger_result)

        return {
            "success": True,
            "transaction_id": transaction["id"],
            "validation_results": validation_results,
            "contract_result": contract_result,
            "ledger_proof": ledger_result["proof"],
            "confirmations": await self.get_confirmations(transaction["id"]),
            "finality_time": await self.estimate_finality_time(transaction)
        }


# ==================== 概率证明共识 ====================

class ProbabilisticProofConsensus:
    """概率证明共识"""

    def __init__(self):
        self.confidence_levels = {"low": 0.6, "medium": 0.8, "high": 0.95, "final": 0.99}

    async def get_total_nodes(self) -> int:
        return 100

    async def select_validator_nodes(self, transaction: Dict, count: int = 5) -> List[str]:
        return [f"node_{uuid.uuid4().hex[:6]}" for _ in range(count)]

    async def request_validation(self, node_id: str, transaction: Dict) -> Dict:
        return {"node_id": node_id, "valid": random.random() > 0.1}

    def calculate_confidence(self, validations: List[Dict], total_nodes: int) -> float:
        if not validations:
            return 0.0

        positive = sum(1 for v in validations if v.get("valid", False))
        total = len(validations)

        if positive == 0:
            return 0.0
        elif positive == total:
            return 1.0

        confidence = positive / total
        sample_adjustment = total / (total + 10)
        return confidence * sample_adjustment

    async def verify_with_probability(self, transaction: Dict, required_confidence: float = 0.8) -> Dict:
        validations = []
        total_nodes = await self.get_total_nodes()

        for node_id in await self.select_validator_nodes(transaction, 5):
            validation = await self.request_validation(node_id, transaction)
            validations.append(validation)

            current_confidence = self.calculate_confidence(validations, total_nodes)

            if current_confidence >= required_confidence:
                return {"valid": True, "confidence": current_confidence, "validations_received": len(validations), "consensus_reached": True}

            if current_confidence < 0.3:
                return {"valid": False, "confidence": current_confidence, "validations_received": len(validations), "consensus_reached": False}

        return {"valid": False, "confidence": self.calculate_confidence(validations, total_nodes), "validations_received": len(validations), "consensus_reached": False}


# ==================== 时间锁积分 ====================

class TimeLockedCredits:
    """时间锁积分"""

    def __init__(self):
        self.time_locks = {}
        self.user_balances = defaultdict(int)

    async def check_balance(self, user_id: str, amount: int) -> bool:
        return self.user_balances[user_id] >= amount

    async def lock_credits(self, user_id: str, amount: int, lock_id: str):
        self.user_balances[user_id] -= amount

    async def release_credits(self, user_id: str, amount: int, lock_id: str):
        self.user_balances[user_id] += amount

    async def send_to_community_pool(self, amount: int, reason: str):
        pass

    async def calculate_interest_rate(self, lock_period_days: int) -> float:
        base_rate = 0.05
        return base_rate * (lock_period_days / 365)

    async def calculate_estimated_interest(self, time_lock: Dict) -> int:
        rate = time_lock.get("interest_rate", 0.05)
        return int(time_lock["amount"] * rate)

    async def calculate_actual_interest(self, time_lock: Dict) -> int:
        return await self.calculate_estimated_interest(time_lock)

    async def create_time_lock(self, user_id: str, amount: int, lock_period_days: int) -> Dict:
        if not await self.check_balance(user_id, amount):
            return {"success": False, "error": "积分不足"}

        lock_id = f"lock_{uuid.uuid4().hex[:8]}"
        unlock_time = datetime.now() + timedelta(days=lock_period_days)
        interest_rate = await self.calculate_interest_rate(lock_period_days)

        time_lock = {
            "lock_id": lock_id,
            "user_id": user_id,
            "amount": amount,
            "locked_at": datetime.now().isoformat(),
            "unlock_time": unlock_time.isoformat(),
            "status": "locked",
            "early_withdrawal_penalty": 0.1,
            "interest_rate": interest_rate
        }

        await self.lock_credits(user_id, amount, lock_id)
        self.time_locks[lock_id] = time_lock

        return {
            "success": True,
            "lock_id": lock_id,
            "amount": amount,
            "unlock_time": unlock_time.isoformat(),
            "interest_rate": interest_rate,
            "estimated_interest": await self.calculate_estimated_interest(time_lock)
        }

    async def unlock_credits(self, lock_id: str, force: bool = False) -> Dict:
        if lock_id not in self.time_locks:
            return {"success": False, "error": "时间锁不存在"}

        time_lock = self.time_locks[lock_id]
        current_time = datetime.now()
        unlock_time = datetime.fromisoformat(time_lock["unlock_time"])

        if current_time < unlock_time and not force:
            penalty = int(time_lock["amount"] * time_lock["early_withdrawal_penalty"])
            amount_to_unlock = time_lock["amount"] - penalty
            await self.send_to_community_pool(penalty, "early_withdrawal")
            unlocked_amount = amount_to_unlock
        else:
            interest = await self.calculate_actual_interest(time_lock)
            unlocked_amount = time_lock["amount"] + interest

        await self.release_credits(time_lock["user_id"], unlocked_amount, lock_id)

        time_lock["status"] = "unlocked"
        time_lock["unlocked_at"] = current_time.isoformat()
        time_lock["unlocked_amount"] = unlocked_amount

        return {
            "success": True,
            "lock_id": lock_id,
            "original_amount": time_lock["amount"],
            "unlocked_amount": unlocked_amount,
            "interest_earned": unlocked_amount - time_lock["amount"],
            "early_withdrawal": current_time < unlock_time
        }


# ==================== 积分保险机制 ====================

class CreditInsurance:
    """积分保险机制"""

    def __init__(self):
        self.insurance_policies = {}
        self.user_balances = defaultdict(int)

    async def check_balance(self, user_id: str, amount: int) -> bool:
        return self.user_balances[user_id] >= amount

    async def deduct_premium(self, user_id: str, premium: int):
        self.user_balances[user_id] -= premium

    async def find_active_policies(self, user_id: str) -> List[Dict]:
        policies = []
        for policy in self.insurance_policies.values():
            if policy["user_id"] == user_id and policy["status"] == "active":
                end_time = datetime.fromisoformat(policy["end_time"])
                if datetime.now() < end_time:
                    policies.append(policy)
        return policies

    async def validate_incident(self, incident: Dict) -> Dict:
        required = ["type", "loss_amount", "description"]
        if not all(k in incident for k in required):
            return {"valid": False, "reason": "缺少必要字段"}
        return {"valid": True}

    async def select_best_policy(self, policies: List[Dict], incident: Dict) -> Optional[Dict]:
        for policy in policies:
            if incident["type"] in policy.get("coverage", {}):
                if policy["coverage"][incident["type"]]:
                    return policy
        return None

    async def calculate_payout(self, policy: Dict, incident: Dict) -> int:
        loss = incident["loss_amount"]
        deductible = policy.get("deductible", 0)
        payout = max(0, loss - deductible)
        return min(payout, policy["insured_amount"])

    async def community_vote_on_claim(self, user_id: str, incident: Dict, policy: Dict, payout: int) -> Dict:
        return {"approved": True, "votes_for": 10, "votes_against": 2}

    async def execute_payout(self, user_id: str, amount: int, policy_id: str):
        self.user_balances[user_id] += amount

    async def calculate_premium(self, amount: int, period_days: int) -> int:
        base_rate = 0.01
        period_factor = period_days / 365
        return int(amount * base_rate * period_factor)

    async def calculate_deductible(self, amount: int) -> int:
        return int(amount * 0.1)

    async def purchase_insurance(self, user_id: str, amount: int, period_days: int) -> Dict:
        premium = await self.calculate_premium(amount, period_days)

        if not await self.check_balance(user_id, premium):
            return {"success": False, "error": "积分不足"}

        policy_id = f"ins_{uuid.uuid4().hex[:8]}"

        policy = {
            "policy_id": policy_id,
            "user_id": user_id,
            "insured_amount": amount,
            "premium": premium,
            "period_days": period_days,
            "start_time": datetime.now().isoformat(),
            "end_time": (datetime.now() + timedelta(days=period_days)).isoformat(),
            "coverage": {"accidental_loss": True, "hacking": True, "system_failure": True, "dispute_loss": False},
            "deductible": await self.calculate_deductible(amount),
            "status": "active"
        }

        await self.deduct_premium(user_id, premium)
        self.insurance_policies[policy_id] = policy

        return {
            "success": True,
            "policy_id": policy_id,
            "premium": premium,
            "insured_amount": amount,
            "deductible": policy["deductible"],
            "coverage_details": policy["coverage"]
        }

    async def file_claim(self, user_id: str, incident: Dict) -> Dict:
        active_policies = await self.find_active_policies(user_id)

        if not active_policies:
            return {"success": False, "error": "无有效保单"}

        incident_validation = await self.validate_incident(incident)

        if not incident_validation["valid"]:
            return {"success": False, "error": "事故验证失败"}

        best_policy = await self.select_best_policy(active_policies, incident)

        if not best_policy:
            return {"success": False, "error": "无适用保单"}

        payout = await self.calculate_payout(best_policy, incident)

        community_vote = await self.community_vote_on_claim(user_id, incident, best_policy, payout)

        if community_vote["approved"]:
            await self.execute_payout(user_id, payout, best_policy["policy_id"])

            return {
                "success": True,
                "policy_id": best_policy["policy_id"],
                "incident_type": incident["type"],
                "loss_amount": incident["loss_amount"],
                "payout_amount": payout,
                "deductible_applied": best_policy["deductible"],
                "community_vote_result": community_vote
            }

        return {"success": False, "error": "社区投票未通过", "community_vote_result": community_vote}


# ==================== AI森林宠物 ====================

class AIForestPet:
    """AI森林宠物"""

    def __init__(self):
        self.pet_types = {
            "fire_spirit": {"Name": "火精灵", "icon": "🔥", "abilities": ["warmth", "light"]},
            "water_sprite": {"Name": "水精灵", "icon": "💧", "abilities": ["healing", "purify"]},
            "earth_gnome": {"Name": "土精灵", "icon": "🪨", "abilities": ["stability", "strength"]},
            "wind_fairy": {"Name": "风精灵", "icon": "🌪️", "abilities": ["speed", "agility"]},
            "forest_elf": {"Name": "森林精灵", "icon": "🌲", "abilities": ["nature", "growth"]},
            "moon_rabbit": {"Name": "月兔", "icon": "🐰", "abilities": ["wisdom", "patience"]}
        }

        self.user_pets = {}

    async def generate_pet_name(self, pet_type: str) -> str:
        prefixes = ["小", "可爱的", "聪明的", "勇敢的", "温柔的"]
        suffixes = ["伙伴", "朋友", "宝贝", "精灵"]
        type_name = self.pet_types.get(pet_type, {}).get("name", "宠物")
        return f"{random.choice(prefixes)}{type_name}"

    async def generate_random_traits(self) -> List[str]:
        all_traits = ["好奇", "活泼", "害羞", "勇敢", "温柔", "贪玩", "聪明", "忠诚"]
        return random.sample(all_traits, min(3, len(all_traits)))

    async def get_pet_abilities(self, pet_type: str) -> List[str]:
        return self.pet_types.get(pet_type, {}).get("abilities", [])

    async def generate_ai_personality(self, pet: Dict) -> Dict:
        return {
            "personality_vector": [random.random() for _ in range(10)],
            "mood_state": "happy",
            "learning_rate": 0.01,
            "memory": []
        }

    async def get_user_pet(self, user_id: str) -> Optional[Dict]:
        return self.user_pets.get(user_id)

    async def gain_pet_exp(self, pet: Dict, exp_amount: int):
        pet["exp"] = pet.get("exp", 0) + exp_amount
        if pet["exp"] >= pet["level"] * 100:
            pet["level"] = pet.get("level", 1) + 1
            pet["exp"] = 0

    async def get_pet_reaction(self, pet: Dict, activity: str) -> str:
        reactions = {
            "dig": ["🐾 兴奋地刨土", "😺 好奇地看着", "🦊 若有所思"],
            "puzzle": ["🦉 认真地思考", "🐰 蹦蹦跳跳", "🌟 眼睛发亮"],
            "tree": ["🌱 开心地转圈", "🦋 翩翩起舞", "💚 发出柔和的光"]
        }
        return random.choice(reactions.get(activity, ["✨ 很开心"]))

    async def adopt_pet(self, user_id: str, pet_type: str) -> Dict:
        if pet_type not in self.pet_types:
            return {"success": False, "error": "宠物类型不存在"}

        pet = {
            "pet_id": f"pet_{uuid.uuid4().hex[:8]}",
            "type": pet_type,
            "name": await self.generate_pet_name(pet_type),
            "traits": await self.generate_random_traits(),
            "abilities": await self.get_pet_abilities(pet_type),
            "happiness": 50,
            "hunger": 50,
            "energy": 100,
            "level": 1,
            "exp": 0,
            "ai_personality": await self.generate_ai_personality({})
        }

        self.user_pets[user_id] = pet

        return {
            "success": True,
            "pet": pet,
            "type_name": self.pet_types[pet_type]["name"],
            "icon": self.pet_types[pet_type]["icon"]
        }

    async def pet_helps_collect(self, user_id: str, activity: str) -> Dict:
        pet = await self.get_user_pet(user_id)

        if not pet:
            return {"help_amount": 0, "bonus": 1.0}

        help_amount = 0
        multiplier = 1.0

        if activity == "dig":
            if "treasure_sense" in pet.get("abilities", []):
                help_amount += random.randint(1, 5)
                multiplier += 0.1
        elif activity == "puzzle":
            if "wise" in pet.get("traits", []):
                help_amount += random.randint(1, 3)
                multiplier += 0.05

        await self.gain_pet_exp(pet, help_amount * 2)

        return {
            "help_amount": help_amount,
            "bonus_multiplier": multiplier,
            "pet_gained_exp": help_amount * 2,
            "pet_reaction": await self.get_pet_reaction(pet, activity)
        }


# ==================== 生态成就链 ====================

class EcologyAchievementChain:
    """生态成就链"""

    def __init__(self):
        self.ecology_chains = {
            "plant_tree": {
                "name": "植树者", "description": "为森林添绿",
                "requirements": ["plant_10_trees", "water_50_trees", "fertilize_20_trees"],
                "rewards": {"credits": 1000, "title": "🌳 植树者"}, "icon": "🌳"
            },
            "protect_wildlife": {
                "name": "野生动物保护者", "description": "守护动物家园",
                "requirements": ["observe_20_species", "build_5_nests", "feed_animals_30_times"],
                "rewards": {"credits": 1500, "title": "🦉 保护者"}, "icon": "🦉"
            },
            "clean_environment": {
                "name": "环境清洁工", "description": "清洁我们的家园",
                "requirements": ["collect_100_trash", "recycle_50_items", "clean_10_spots"],
                "rewards": {"credits": 2000, "title": "🧹 清洁工"}, "icon": "🧹"
            },
            "water_guardian": {
                "name": "水源守护者", "description": "保护水资源",
                "requirements": ["clean_10_rivers", "build_5_ponds", "rescue_20_fish"],
                "rewards": {"credits": 1800, "title": "💧 守护者"}, "icon": "💧"
            },
            "fire_preventer": {
                "name": "火灾预防员", "description": "预防森林火灾",
                "requirements": ["report_10_dangers", "create_20_firebreaks", "educate_50_people"],
                "rewards": {"credits": 2200, "title": "🛡️ 预防员"}, "icon": "🛡️"
            }
        }

        self.user_progress = defaultdict(lambda: defaultdict(int))

    async def check_requirement(self, user_id: str, requirement: str) -> bool:
        progress = self.user_progress[user_id]
        req_type = requirement.split("_")[0]
        req_count = int(requirement.split("_")[-1])
        return progress[req_type] >= req_count

    async def calculate_ecology_score(self, user_id: str) -> int:
        total = 0
        for chain_id, chain in self.ecology_chains.items():
            completed = True
            for req in chain["requirements"]:
                if not await self.check_requirement(user_id, req):
                    completed = False
                    break
            if completed:
                total += chain["rewards"]["credits"]
        return total

    async def calculate_environment_impact(self, chain_id: str) -> Dict:
        impacts = {
            "plant_tree": {"trees": 10, "oxygen": 5, "biodiversity": 3},
            "protect_wildlife": {"animals": 5, "habitats": 3, "biodiversity": 5},
            "clean_environment": {"cleanliness": 20, "water_quality": 10, "air_quality": 5}
        }
        return impacts.get(chain_id, {"impact": 1})

    async def get_next_ecological_chain(self, chain_id: str) -> Optional[Dict]:
        chain_ids = list(self.ecology_chains.keys())
        if chain_id in chain_ids:
            idx = chain_ids.index(chain_id)
            if idx + 1 < len(chain_ids):
                next_id = chain_ids[idx + 1]
                return {"chain_id": next_id, **self.ecology_chains[next_id]}
        return None

    async def record_ecology_contribution(self, user_id: str, chain_id: str, rewards: Dict):
        pass

    async def complete_ecology_chain(self, user_id: str, chain_id: str) -> Dict:
        if chain_id not in self.ecology_chains:
            return {"success": False, "error": "生态链不存在"}

        chain = self.ecology_chains[chain_id]

        for req in chain["requirements"]:
            if not await self.check_requirement(user_id, req):
                return {"success": False, "error": f"未完成: {req}"}

        rewards = chain["rewards"]
        await self.record_ecology_contribution(user_id, chain_id, rewards)

        return {
            "success": True,
            "chain": chain_id,
            "chain_name": chain["name"],
            "rewards": rewards,
            "ecology_score": await self.calculate_ecology_score(user_id),
            "environment_impact": await self.calculate_environment_impact(chain_id),
            "next_chain": await self.get_next_ecological_chain(chain_id)
        }


# ==================== 天气系统影响 ====================

class WeatherImpactSystem:
    """天气系统影响"""

    def __init__(self):
        self.current_weather = Weather.SUNNY
        self.weather_duration = {"hours": 0, "started_at": None}
        self.weather_effects = {
            Weather.SUNNY: {"growth_multiplier": 1.2, "energy_regen": 1.1, "rare_find_chance": 1.0, "description": "晴朗天气，万物生长"},
            Weather.RAINY: {"growth_multiplier": 1.5, "water_actions": 0.5, "mushroom_spawn": 2.0, "description": "雨天，植物生长加速"},
            Weather.FOGGY: {"exploration_bonus": 1.3, "mystery_chance": 1.5, "visibility_penalty": 0.7, "description": "雾天，充满神秘感"},
            Weather.STORMY: {"danger": True, "rare_event_chance": 3.0, "risk_reward_multiplier": 2.0, "description": "暴风雨，危险与机遇并存"}
        }

    async def get_current_weather(self) -> Weather:
        return self.current_weather

    async def estimate_weather_duration(self) -> int:
        return max(1, 24 - self.weather_duration.get("hours", 0))

    async def broadcast_weather_change(self, weather: Weather, effects: Dict):
        pass

    async def change_weather(self) -> Weather:
        weights = [0.4, 0.25, 0.2, 0.15]
        weather = random.choices(list(Weather), weights=weights, k=1)[0]
        self.current_weather = weather
        self.weather_duration = {"hours": 0, "started_at": datetime.now().isoformat()}
        return weather

    async def apply_weather_effects(self) -> Dict:
        weather = await self.get_current_weather()
        weather_effect = self.weather_effects.get(weather, self.weather_effects[Weather.SUNNY])

        await self.broadcast_weather_change(weather, weather_effect)

        return {
            "weather": weather.value,
            "effects": weather_effect,
            "duration_hours": await self.estimate_weather_duration(),
            "weather_warning": weather_effect.get("danger", False)
        }


# ==================== 统一管理器 ====================

class LivingTreeGameManager:
    """生命之树游戏统一管理器"""

    def __init__(self):
        self.forest_adventure = ForestAdventure()
        self.number_puzzle = NumberPuzzleGame()
        self.tree_nurturing = LifeTreeNurturing()
        self.mini_games = EcologyMiniGames()
        self.seasonal_festival = SeasonalFestival()
        self.credit_consistency = LayeredCreditConsistency()
        self.probabilistic_consensus = ProbabilisticProofConsensus()
        self.time_locked = TimeLockedCredits()
        self.credit_insurance = CreditInsurance()
        self.ai_pet = AIForestPet()
        self.ecology_chain = EcologyAchievementChain()
        self.weather_system = WeatherImpactSystem()

    async def get_system_status(self) -> Dict:
        return {
            "active_puzzles": len(self.number_puzzle.active_puzzles),
            "user_trees": len(self.tree_nurturing.user_trees),
            "active_events": len(self.seasonal_festival.active_events),
            "current_weather": (await self.weather_system.get_current_weather()).value,
            "total_time_locks": len(self.time_locked.time_locks),
            "active_policies": len(self.credit_insurance.insurance_policies)
        }


# ==================== 导出 ====================

__all__ = [
    'ForestAdventure', 'NumberPuzzleGame', 'LifeTreeNurturing', 'EcologyMiniGames',
    'SeasonalFestival', 'LayeredCreditConsistency', 'ProbabilisticProofConsensus',
    'TimeLockedCredits', 'CreditInsurance', 'AIForestPet', 'EcologyAchievementChain',
    'WeatherImpactSystem', 'LivingTreeGameManager',
    'TreasureRarity', 'Weather', 'Season', 'TreeStage'
]
