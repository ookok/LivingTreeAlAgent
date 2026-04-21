# -*- coding: utf-8 -*-
"""
🎮 挂机积分与等级粘性增强系统
================================
核心理念："让用户的每一秒在线时间都产生价值，构建可见的成长路径和社会地位体系"

Author: Hermes Desktop Team
"""

import uuid
import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict


# ==================== 1. 智能挂机积分系统 ====================

class IdleCreditSystem:
    """智能挂机积分系统"""

    # 收益因子权重
    REWARD_FACTORS = {
        "online_duration": 0.30,     # 在线时长
        "network_contribution": 0.25,  # 网络贡献
        "device_capability": 0.20,   # 设备能力
        "social_engagement": 0.15,    # 社交参与
        "asset_wealth": 0.10,         # 资产财富
    }

    # 每日挂机上限（按等级）
    DAILY_IDLE_CAPS = {
        1: 1000, 3: 3000, 5: 10000, 7: 50000, 9: 200000
    }

    def __init__(self):
        self.online_users: Dict[str, datetime] = {}  # user_id -> 上线时间
        self.idle_rewards: Dict[str, List[Dict]] = defaultdict(list)  # 用户挂机收益记录
        self.user_states: Dict[str, Dict] = {}  # 缓存用户状态

    async def calculate_idle_rewards(self, user_id: str,
                                     checkin_time: datetime = None) -> Dict:
        """计算挂机收益"""
        checkin_time = checkin_time or datetime.now()

        # 1. 获取用户状态
        user_state = await self.get_user_state(user_id)

        # 2. 多维度计算收益
        rewards = {
            "base_reward": await self.calculate_base_reward(user_state, checkin_time),
            "network_bonus": await self.calculate_network_bonus(user_id),
            "device_bonus": await self.calculate_device_bonus(user_state.get("device_info", {})),
            "social_bonus": await self.calculate_social_bonus(user_id),
            "wealth_bonus": await self.calculate_wealth_bonus(user_state.get("assets", {})),
            "achievement_bonus": await self.calculate_achievement_bonus(user_id)
        }

        # 3. 应用衰减和上限
        total_reward = self.apply_reward_limits(sum(rewards.values()), user_state.get("level", 1))

        # 4. 生成收益报告
        reward_report = {
            "user_id": user_id,
            "checkin_time": checkin_time.isoformat(),
            "total_credits": int(total_reward),
            "breakdown": {k: int(v) for k, v in rewards.items()},
            "multipliers": await self.get_active_multipliers(user_id),
            "next_checkin": (checkin_time + timedelta(minutes=5)).isoformat(),
            "daily_cap": self.get_daily_cap(user_state.get("level", 1)),
            "cap_remaining": await self.get_cap_remaining(user_id, user_state.get("level", 1))
        }

        return reward_report

    async def get_user_state(self, user_id: str) -> Dict:
        """获取用户状态"""
        if user_id in self.user_states:
            return self.user_states[user_id]

        # 模拟从数据库加载
        state = {
            "user_id": user_id,
            "level": 1,
            "total_credits": 0,
            "online_duration_hours": 0,
            "device_info": {
                "cpu_cores": 4,
                "gpu_memory_mb": 4096,
                "storage_gb": 500,
                "bandwidth_mbps": 50
            },
            "assets": {"total_value": 0},
            "social_score": 50
        }

        self.user_states[user_id] = state
        return state

    async def calculate_base_reward(self, user_state: Dict, checkin_time: datetime) -> float:
        """计算基础奖励"""
        base_rate = 1.0  # 每分钟基础积分

        # 在线时长加成
        online_hours = user_state.get("online_duration_hours", 0)
        if online_hours > 24:
            multiplier = 1.5
        elif online_hours > 48:
            multiplier = 2.0
        else:
            multiplier = 1.0

        return base_rate * 5 * multiplier  # 每5分钟结算

    async def calculate_network_bonus(self, user_id: str) -> float:
        """计算网络贡献奖励"""
        bonuses = []

        # 1. 节点中继奖励
        if await self.is_relay_node(user_id):
            relay_performance = await self.get_relay_performance(user_id)
            bonuses.append(relay_performance * 10)

        # 2. 数据贡献奖励
        data_shared = await self.get_data_sharing(user_id)
        bonuses.append(data_shared * 0.1)

        # 3. 计算资源贡献
        compute_shared = await self.get_compute_sharing(user_id)
        bonuses.append(compute_shared * 0.5)

        return sum(bonuses)

    async def is_relay_node(self, user_id: str) -> bool:
        """检查是否为中继节点"""
        return random.random() < 0.3  # 30%概率

    async def get_relay_performance(self, user_id: str) -> float:
        """获取中继性能"""
        return random.uniform(0.5, 1.0)

    async def get_data_sharing(self, user_id: str) -> float:
        """获取数据共享量"""
        return random.uniform(0, 100)

    async def get_compute_sharing(self, user_id: str) -> float:
        """获取计算资源共享量"""
        return random.uniform(0, 50)

    async def calculate_device_bonus(self, device_info: Dict) -> float:
        """计算设备能力奖励"""
        device_score = 0

        # CPU能力
        if device_info.get("cpu_cores", 0) >= 8:
            device_score += 20
        elif device_info.get("cpu_cores", 0) >= 4:
            device_score += 10

        # GPU能力
        if device_info.get("gpu_memory_mb", 0) >= 8000:
            device_score += 30
        elif device_info.get("gpu_memory_mb", 0) >= 4000:
            device_score += 15

        # 存储能力
        if device_info.get("storage_gb", 0) >= 1000:
            device_score += 20
        elif device_info.get("storage_gb", 0) >= 500:
            device_score += 10

        # 网络带宽
        if device_info.get("bandwidth_mbps", 0) >= 100:
            device_score += 30
        elif device_info.get("bandwidth_mbps", 0) >= 50:
            device_score += 15

        return device_score * 0.5

    async def calculate_social_bonus(self, user_id: str) -> float:
        """计算社交参与奖励"""
        base = 5.0

        # 好友数量加成
        friend_count = await self.get_friend_count(user_id)
        if friend_count > 10:
            base *= 1.5
        elif friend_count > 5:
            base *= 1.2

        # 群组参与加成
        group_count = await self.get_group_count(user_id)
        base *= (1 + group_count * 0.1)

        return base

    async def get_friend_count(self, user_id: str) -> int:
        """获取好友数量"""
        return random.randint(0, 20)

    async def get_group_count(self, user_id: str) -> int:
        """获取群组数量"""
        return random.randint(0, 5)

    async def calculate_wealth_bonus(self, assets: Dict) -> float:
        """计算资产财富奖励"""
        total_value = assets.get("total_value", 0)

        if total_value > 100000:
            return 50.0
        elif total_value > 50000:
            return 30.0
        elif total_value > 10000:
            return 15.0
        else:
            return 5.0

    async def calculate_achievement_bonus(self, user_id: str) -> float:
        """计算成就奖励"""
        achievement_count = await self.get_achievement_count(user_id)
        return achievement_count * 2.0

    async def get_achievement_count(self, user_id: str) -> int:
        """获取成就数量"""
        return random.randint(0, 10)

    def apply_reward_limits(self, total_reward: float, level: int) -> float:
        """应用奖励上限和衰减"""
        # 获取每日上限
        daily_cap = self.get_daily_cap(level)

        # 检查今日已获取
        today_reward = self.get_today_reward(level)
        remaining = daily_cap - today_reward

        if remaining <= 0:
            return 0

        # 应用上限
        reward = min(total_reward, remaining)

        # 超过12小时有衰减
        # ... 简化处理

        return reward

    def get_daily_cap(self, level: int) -> int:
        """获取每日挂机上限"""
        for req_level in sorted(self.DAILY_IDLE_CAPS.keys(), reverse=True):
            if level >= req_level:
                return self.DAILY_IDLE_CAPS[req_level]
        return 1000

    def get_today_reward(self, user_id: str) -> float:
        """获取今日已获得挂机积分"""
        today = datetime.now().date()
        rewards = self.idle_rewards.get(user_id, [])

        today_total = 0
        for reward in rewards:
            reward_date = datetime.fromisoformat(reward.get("checkin_time", "")).date()
            if reward_date == today:
                today_total += reward.get("total_credits", 0)

        return today_total

    async def get_cap_remaining(self, user_id: str, level: int) -> Dict:
        """获取剩余额度"""
        today_reward = self.get_today_reward(user_id)
        daily_cap = self.get_daily_cap(level)

        return {
            "used": today_reward,
            "cap": daily_cap,
            "remaining": max(0, daily_cap - today_reward),
            "reset_at": datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=1)
        }

    async def get_active_multipliers(self, user_id: str) -> List[Dict]:
        """获取活跃的加成器"""
        multipliers = []

        # VIP加成
        if await self.is_vip(user_id):
            multipliers.append({"type": "vip", "multiplier": 1.5, "expires": None})

        # 活动加成
        multipliers.append({"type": "activity", "multiplier": 1.2, "expires": "2026-04-30"})

        # 设备加成
        multipliers.append({"type": "device", "multiplier": 1.1, "expires": None})

        return multipliers

    async def is_vip(self, user_id: str) -> bool:
        """检查是否为VIP"""
        return random.random() < 0.2


# ==================== 2. 挂机小游戏系统 ====================

class IdleMiniGame:
    """挂机小游戏系统"""

    MINI_GAMES = {
        "data_mining": {
            "name": "数据挖矿",
            "description": "自动挖掘网络中的有价值数据",
            "base_reward": 1,
            "upgrade_cost": {"credits": 100, "level": 1},
            "max_level": 20,
            "emoji": "⛏️"
        },
        "node_farming": {
            "name": "节点耕作",
            "description": "运行网络节点获得稳定收益",
            "base_reward": 2,
            "upgrade_cost": {"credits": 200, "level": 1},
            "max_level": 15,
            "emoji": "🌾"
        },
        "ai_training": {
            "name": "AI训练场",
            "description": "用闲置算力训练AI模型",
            "base_reward": 5,
            "upgrade_cost": {"credits": 500, "level": 1},
            "max_level": 10,
            "emoji": "🤖"
        },
        "knowledge_harvest": {
            "name": "知识收割",
            "description": "从知识库中提取有价值信息",
            "base_reward": 3,
            "upgrade_cost": {"credits": 300, "level": 1},
            "max_level": 12,
            "emoji": "📚"
        }
    }

    # 随机事件
    RANDOM_EVENTS = [
        {"type": "lucky", "multiplier": 2.0, "message": "幸运一击！", "chance": 0.05},
        {"type": "bonus", "multiplier": 1.5, "message": "额外奖励！", "chance": 0.10},
        {"type": "combo", "multiplier": 1.3, "message": "连击加成！", "chance": 0.15},
        {"type": "slow", "multiplier": 0.5, "message": "网络延迟...", "chance": 0.05}
    ]

    def __init__(self):
        self.user_games: Dict[str, Dict[str, Dict]] = defaultdict(dict)

    async def get_user_games(self, user_id: str) -> Dict[str, Dict]:
        """获取用户的小游戏状态"""
        if user_id not in self.user_games:
            # 初始化用户小游戏
            self.user_games[user_id] = {
                game_id: {
                    "active": True,
                    "level": 1,
                    "duration_hours": 0,
                    "total_earned": 0
                }
                for game_id in self.MINI_GAMES.keys()
            }
        return self.user_games[user_id]

    async def run_idle_games(self, user_id: str) -> Dict:
        """运行挂机小游戏"""
        user_games = await self.get_user_games(user_id)
        results = []

        for game_id, game_info in user_games.items():
            if game_info.get("active", False):
                # 计算本轮收益
                game_config = self.MINI_GAMES[game_id]
                reward = self.calculate_game_reward(game_config, game_info["level"])

                # 随机事件
                random_event = self.generate_random_event()
                if random_event:
                    reward *= random_event.get("multiplier", 1.0)
                    results.append({
                        "game_id": game_id,
                        "game_name": game_config["name"],
                        "event": random_event
                    })

                # 累计收益
                results.append({
                    "game_id": game_id,
                    "game_name": game_config["name"],
                    "reward": int(reward),
                    "duration_hours": game_info.get("duration_hours", 1)
                })

                # 更新游戏时长
                game_info["duration_hours"] = game_info.get("duration_hours", 0) + 1
                game_info["total_earned"] = game_info.get("total_earned", 0) + reward

        return {
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
            "game_results": results,
            "total_reward": sum(r.get("reward", 0) for r in results)
        }

    def calculate_game_reward(self, game_config: Dict, level: int) -> float:
        """计算游戏收益"""
        base = game_config["base_reward"]
        level_multiplier = 1 + (level - 1) * 0.2  # 每级+20%

        return base * level_multiplier

    def generate_random_event(self) -> Optional[Dict]:
        """生成随机事件"""
        roll = random.random()
        cumulative = 0

        for event in self.RANDOM_EVENTS:
            cumulative += event["chance"]
            if roll < cumulative:
                return event

        return None

    async def upgrade_game(self, user_id: str, game_id: str) -> Dict:
        """升级小游戏"""
        user_games = await self.get_user_games(user_id)

        if game_id not in user_games:
            return {"success": False, "error": "游戏不存在"}

        game_info = user_games[game_id]
        game_config = self.MINI_GAMES[game_id]

        # 检查等级上限
        if game_info["level"] >= game_config["max_level"]:
            return {"success": False, "error": "已达最大等级"}

        # 计算升级费用
        upgrade_cost = game_config["upgrade_cost"]["credits"] * game_info["level"]

        # 简化：假设用户有足够积分
        game_info["level"] += 1

        return {
            "success": True,
            "game_id": game_id,
            "new_level": game_info["level"],
            "cost_paid": int(upgrade_cost)
        }

    def get_available_games(self) -> List[Dict]:
        """获取可用小游戏列表"""
        return [
            {"id": game_id, **config}
            for game_id, config in self.MINI_GAMES.items()
        ]


# ==================== 3. 动态等级系统 ====================

class DynamicLevelSystem:
    """动态等级系统"""

    LEVEL_THRESHOLDS = {
        1: {"min_credits": 0, "name": "萌新", "color": "#808080", "emoji": "🐣"},
        2: {"min_credits": 1000, "name": "见习", "color": "#A0522D", "emoji": "🌱"},
        3: {"min_credits": 5000, "name": "熟练", "color": "#C0C0C0", "emoji": "⚡"},
        4: {"min_credits": 20000, "name": "精英", "color": "#FFD700", "emoji": "⭐"},
        5: {"min_credits": 50000, "name": "专家", "color": "#00CED1", "emoji": "🎯"},
        6: {"min_credits": 150000, "name": "大师", "color": "#9370DB", "emoji": "🔥"},
        7: {"min_credits": 500000, "name": "宗师", "color": "#FF4500", "emoji": "💫"},
        8: {"min_credits": 1500000, "name": "传奇", "color": "#8A2BE2", "emoji": "👑"},
        9: {"min_credits": 5000000, "name": "史诗", "color": "#FF1493", "emoji": "💎"},
        10: {"min_credits": 15000000, "name": "神话", "color": "#00FF00", "emoji": "🌟"},
    }

    def __init__(self):
        self.user_levels: Dict[str, Dict] = {}

    async def calculate_user_level(self, user_id: str) -> Dict:
        """计算用户等级"""
        total_credits = await self.get_total_credits(user_id)
        level_info = self.get_level_by_credits(total_credits)

        # 计算等级进度
        current_level = level_info["level"]
        next_level = min(current_level + 1, 10)

        current_min = level_info["min_credits"]
        next_min = self.LEVEL_THRESHOLDS.get(next_level, {}).get("min_credits", current_min)

        if next_min > current_min:
            progress = (total_credits - current_min) / (next_min - current_min) * 100
        else:
            progress = 100

        return {
            "level": current_level,
            "name": level_info["name"],
            "emoji": level_info["emoji"],
            "color": level_info["color"],
            "total_credits": total_credits,
            "next_level": next_level,
            "next_level_name": self.LEVEL_THRESHOLDS.get(next_level, {}).get("name", "Max"),
            "next_level_emoji": self.LEVEL_THRESHOLDS.get(next_level, {}).get("emoji", "✨"),
            "progress_percentage": round(progress, 1),
            "credits_to_next": max(0, next_min - total_credits),
            "badge_url": await self.generate_level_badge(current_level, level_info["name"])
        }

    def get_level_by_credits(self, credits: int) -> Dict:
        """根据积分获取等级"""
        current_level = 1
        level_info = self.LEVEL_THRESHOLDS[1]

        for level, threshold in sorted(self.LEVEL_THRESHOLDS.items()):
            if credits >= threshold["min_credits"]:
                current_level = level
                level_info = threshold

        return {"level": current_level, **level_info}

    async def get_total_credits(self, user_id: str) -> int:
        """获取用户总积分"""
        # 模拟返回
        if user_id in self.user_levels:
            return self.user_levels[user_id].get("total_credits", 0)
        return 10000  # 默认给一些积分用于测试

    async def set_total_credits(self, user_id: str, credits: int):
        """设置用户总积分"""
        self.user_levels[user_id] = {"total_credits": credits}

    async def generate_level_badge(self, level: int, name: str) -> str:
        """生成等级徽章URL"""
        return f"/badges/level_{level}_{name}.png"

    def get_level_info(self, level: int) -> Dict:
        """获取等级信息"""
        return self.LEVEL_THRESHOLDS.get(level, self.LEVEL_THRESHOLDS[1])

    def get_all_levels(self) -> List[Dict]:
        """获取所有等级信息"""
        return [
            {"level": level, **info}
            for level, info in self.LEVEL_THRESHOLDS.items()
        ]


# ==================== 4. 等级特权系统 ====================

class LevelPrivileges:
    """等级特权系统"""

    LEVEL_PRIVILEGES = {
        1: {  # 萌新
            "daily_idle_cap": 1000,
            "max_assets": 5,
            "transaction_fee": 0.05,
            "ui_effects": ["basic_glow"],
            "chat_color": "#FFFFFF"
        },
        3: {  # 熟练
            "daily_idle_cap": 3000,
            "max_assets": 20,
            "transaction_fee": 0.03,
            "ui_effects": ["sparkle", "level_badge"],
            "custom_title": True,
            "chat_color": "#C0C0C0"
        },
        5: {  # 专家
            "daily_idle_cap": 10000,
            "max_assets": 50,
            "transaction_fee": 0.01,
            "ui_effects": ["golden_glow", "particles"],
            "market_fee_discount": 0.30,
            "early_access": True,
            "chat_color": "#00CED1"
        },
        7: {  # 宗师
            "daily_idle_cap": 50000,
            "max_assets": 200,
            "transaction_fee": 0,
            "ui_effects": ["rainbow_glow", "animated_background"],
            "vip_support": True,
            "governance_voting": True,
            "chat_color": "#FF4500"
        },
        9: {  # 史诗
            "daily_idle_cap": 200000,
            "max_assets": 1000,
            "ui_effects": ["nebula_background", "crown"],
            "custom_landing_page": True,
            "founder_status": True,
            "chat_color": "#FF1493"
        }
    }

    def __init__(self, level_system: DynamicLevelSystem = None):
        self.level_system = level_system or DynamicLevelSystem()

    async def get_user_privileges(self, user_id: str) -> Dict:
        """获取用户特权"""
        level_info = await self.level_system.calculate_user_level(user_id)
        level = level_info["level"]

        # 合并所有符合条件的特权
        privileges = {}
        for privilege_level, privs in sorted(self.LEVEL_PRIVILEGES.items()):
            if level >= privilege_level:
                privileges.update(privs)

        # 添加特殊成就特权
        achievements = await self.get_user_achievements(user_id)
        for achievement in achievements:
            if "privilege" in achievement:
                privileges.update(achievement["privilege"])

        return {
            "level": level,
            "level_name": level_info["name"],
            "privileges": privileges,
            "unlocked_features": self.get_unlocked_features(level),
            "next_privilege": self.get_next_privilege(level)
        }

    def get_unlocked_features(self, level: int) -> List[str]:
        """获取已解锁功能"""
        features = []

        feature_requirements = {
            "custom_username_color": 3,
            "basic_emojis": 3,
            "animated_avatar": 5,
            "custom_status": 5,
            "create_private_groups": 5,
            "host_events": 5,
            "3d_avatar": 7,
            "voice_effects": 7,
            "found_community": 7,
            "moderation_powers": 7,
            "virtual_office": 9,
            "ai_assistant": 9,
            "global_announcement": 9,
            "feature_request": 9
        }

        for feature, req_level in feature_requirements.items():
            if level >= req_level:
                features.append(feature)

        return features

    def get_next_privilege(self, level: int) -> Optional[Dict]:
        """获取下一特权"""
        next_level = level + 1
        if next_level > 10:
            return None

        new_privileges = self.LEVEL_PRIVILEGES.get(next_level, {})
        if not new_privileges:
            return None

        # 找出新增的特权
        current_privileges = self.LEVEL_PRIVILEGES.get(level, {})
        new_features = {k: v for k, v in new_privileges.items() if k not in current_privileges}

        return {
            "next_level": next_level,
            "new_features": new_features,
            "level_name": self.level_system.get_level_info(next_level)["name"]
        }

    async def get_user_achievements(self, user_id: str) -> List[Dict]:
        """获取用户成就"""
        # 模拟返回
        return []


# ==================== 5. 等级成就系统 ====================

class LevelAchievementSystem:
    """等级成就系统"""

    ACHIEVEMENTS = {
        "quick_learner": {
            "name": "快速学习者",
            "description": "在7天内达到熟练等级",
            "reward": 1000,
            "badge": "🚀"
        },
        "idle_master": {
            "name": "挂机大师",
            "description": "连续挂机30天",
            "reward": 5000,
            "badge": "⏳"
        },
        "network_pillar": {
            "name": "网络支柱",
            "description": "节点在线时间超过1000小时",
            "reward": 10000,
            "badge": "🌐"
        },
        "credit_tycoon": {
            "name": "积分大亨",
            "description": "拥有100万积分",
            "reward": 50000,
            "badge": "💰"
        },
        "level_legend": {
            "name": "等级传奇",
            "description": "达到传奇等级",
            "reward": 100000,
            "badge": "👑"
        },
        "social_butterfly": {
            "name": "社交蝴蝶",
            "description": "拥有超过50个好友",
            "reward": 2000,
            "badge": "🦋"
        },
        "early_bird": {
            "name": "早起鸟",
            "description": "连续7天在早上6点前登录",
            "reward": 1500,
            "badge": "🐦"
        },
        "night_owl": {
            "name": "夜猫子",
            "description": "连续7天在凌晨1点后下线",
            "reward": 1500,
            "badge": "🦉"
        }
    }

    def __init__(self):
        self.user_achievements: Dict[str, set] = defaultdict(set)

    async def check_level_achievements(self, user_id: str, new_level: int) -> List[Dict]:
        """检查等级相关成就"""
        unlocked = []

        if new_level >= 3:
            unlocked.append(await self.unlock_achievement(user_id, "quick_learner"))

        if new_level >= 6:
            unlocked.append(await self.unlock_achievement(user_id, "level_master"))

        if new_level >= 8:
            unlocked.append(await self.unlock_achievement(user_id, "level_legend"))

        return unlocked

    async def unlock_achievement(self, user_id: str, achievement_id: str) -> Dict:
        """解锁成就"""
        if achievement_id in self.user_achievements[user_id]:
            return {"already_unlocked": True, "achievement_id": achievement_id}

        achievement = self.ACHIEVEMENTS.get(achievement_id)
        if not achievement:
            return {"error": "成就不存在"}

        self.user_achievements[user_id].add(achievement_id)

        return {
            "unlocked": True,
            "achievement_id": achievement_id,
            "achievement": achievement,
            "reward_credits": achievement["reward"]
        }

    async def get_user_achievements(self, user_id: str) -> List[Dict]:
        """获取用户成就"""
        user_achieves = self.user_achievements.get(user_id, set())
        all_achieves = []

        for achieve_id in user_achieves:
            achieve = self.ACHIEVEMENTS.get(achieve_id, {})
            all_achieves.append({
                "id": achieve_id,
                "unlocked": True,
                **achieve
            })

        # 添加未解锁的
        for achieve_id, achieve in self.ACHIEVEMENTS.items():
            if achieve_id not in user_achieves:
                all_achieves.append({
                    "id": achieve_id,
                    "unlocked": False,
                    **achieve
                })

        return all_achieves

    def get_all_achievements(self) -> List[Dict]:
        """获取所有成就"""
        return [
            {"id": aid, **ainfo}
            for aid, ainfo in self.ACHIEVEMENTS.items()
        ]


# ==================== 6. 每日登录连续奖励 ====================

class DailyLoginReward:
    """每日登录连续奖励"""

    # 奖励日程表
    REWARD_SCHEDULE = {
        1: {"credits": 100, "badge": "🎁", "message": "第一天奖励"},
        3: {"credits": 300, "badge": "🎁🎁", "message": "连续三天"},
        7: {"credits": 1000, "badge": "🏆", "message": "每周成就"},
        14: {"credits": 2500, "badge": "🏆🏆", "message": "两周坚持"},
        30: {"credits": 10000, "badge": "👑", "message": "月度王者"}
    }

    def __init__(self):
        self.login_records: Dict[str, Dict] = {}

    async def get_daily_reward(self, user_id: str) -> Dict:
        """获取每日奖励"""
        streak = await self.get_login_streak(user_id)
        today_reward = await self.get_today_reward(user_id)

        # 如果今天已领取
        if today_reward > 0:
            return {
                "already_claimed": True,
                "streak": streak,
                "today_reward": today_reward,
                "next_claim": self.get_next_claim_time()
            }

        # 基础奖励
        base_reward = 50 + streak * 10

        # 特殊日奖励
        special_reward = 0
        special_badge = None
        for day, reward_info in sorted(self.REWARD_SCHEDULE.items(), reverse=True):
            if streak >= day:
                special_reward = reward_info["credits"]
                special_badge = reward_info["badge"]
                break

        total_reward = base_reward + special_reward

        # 随机惊喜 (10%几率)
        surprise = None
        if random.random() < 0.1:
            surprise = await self.get_surprise_reward()
            total_reward += surprise["amount"]

        # 记录领取
        await self.record_login_reward(user_id, total_reward)

        return {
            "already_claimed": False,
            "streak": streak,
            "base_reward": base_reward,
            "special_reward": special_reward,
            "special_badge": special_badge,
            "surprise": surprise,
            "total_reward": total_reward,
            "next_milestone": self.get_next_milestone(streak)
        }

    async def get_login_streak(self, user_id: str) -> int:
        """获取登录连续天数"""
        if user_id not in self.login_records:
            self.login_records[user_id] = {
                "streak": 0,
                "last_login_date": None,
                "total_logins": 0
            }

        record = self.login_records[user_id]
        today = datetime.now().date()

        if record["last_login_date"]:
            last_date = record["last_login_date"]
            if isinstance(last_date, str):
                last_date = datetime.fromisoformat(last_date).date()

            if last_date == today:
                pass  # 今天已登录
            elif (today - last_date).days == 1:
                # 连续登录
                record["streak"] += 1
            else:
                # 中断
                record["streak"] = 1
        else:
            record["streak"] = 1

        record["last_login_date"] = today.isoformat()
        record["total_logins"] += 1

        return record["streak"]

    async def get_today_reward(self, user_id: str) -> int:
        """获取今日已领取奖励"""
        if user_id not in self.login_records:
            return 0

        record = self.login_records[user_id]
        last_claim = record.get("last_claim_date")

        if not last_claim:
            return 0

        if isinstance(last_claim, str):
            last_claim = datetime.fromisoformat(last_claim).date()

        today = datetime.now().date()
        return record.get("last_claim_amount", 0) if last_claim == today else 0

    async def record_login_reward(self, user_id: str, amount: int):
        """记录登录奖励"""
        if user_id not in self.login_records:
            self.login_records[user_id] = {}

        self.login_records[user_id]["last_claim_date"] = datetime.now().date().isoformat()
        self.login_records[user_id]["last_claim_amount"] = amount

    async def get_surprise_reward(self) -> Dict:
        """获取惊喜奖励"""
        surprises = [
            {"type": "double", "amount": 200, "message": "双倍积分！"},
            {"type": "lucky", "amount": 500, "message": "幸运加成！"},
            {"type": "mystery", "amount": 1000, "message": "神秘大礼！"}
        ]
        return random.choice(surprises)

    def get_next_milestone(self, current_streak: int) -> Optional[Dict]:
        """获取下一里程碑"""
        for day in sorted(self.REWARD_SCHEDULE.keys()):
            if current_streak < day:
                return {
                    "days": day,
                    "credits": self.REWARD_SCHEDULE[day]["credits"],
                    "badge": self.REWARD_SCHEDULE[day]["badge"]
                }
        return None

    def get_next_claim_time(self) -> str:
        """获取下次可领取时间"""
        tomorrow = datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=1)
        return tomorrow.isoformat()


# ==================== 7. 等级专属功能 ====================

class LevelExclusiveFeatures:
    """等级专属功能"""

    EXCLUSIVE_FEATURES = {
        3: {
            "name": "熟练",
            "features": ["custom_username_color", "basic_emojis"],
            "social": ["create_public_chat", "join_advanced_groups"]
        },
        5: {
            "name": "专家",
            "features": ["animated_avatar", "custom_status"],
            "social": ["create_private_groups", "host_events"]
        },
        7: {
            "name": "宗师",
            "features": ["3d_avatar", "voice_effects"],
            "social": ["found_community", "moderation_powers"]
        },
        9: {
            "name": "史诗",
            "features": ["virtual_office", "ai_assistant"],
            "social": ["global_announcement", "feature_request"]
        }
    }

    async def unlock_exclusive_feature(self, user_id: str, feature_type: str = "all") -> Dict:
        """解锁专属功能"""
        level = await self.get_user_level(user_id)

        unlocked_features = []
        for req_level, features in sorted(self.EXCLUSIVE_FEATURES.items()):
            if level >= req_level:
                if feature_type == "all":
                    unlocked_features.extend(features.get("features", []))
                    unlocked_features.extend(features.get("social", []))
                else:
                    unlocked_features.extend(features.get(feature_type, []))

        return {
            "level": level,
            "level_name": self.EXCLUSIVE_FEATURES.get(level, {}).get("name", "萌新"),
            "unlocked_features": unlocked_features,
            "feature_count": len(unlocked_features),
            "next_unlock_at": await self.get_next_unlock_level(level, feature_type)
        }

    async def get_user_level(self, user_id: str) -> int:
        """获取用户等级"""
        return 3  # 模拟

    async def get_next_unlock_level(self, current_level: int, feature_type: str) -> Optional[Dict]:
        """获取下一解锁等级"""
        for req_level in sorted(self.EXCLUSIVE_FEATURES.keys()):
            if current_level < req_level:
                features = self.EXCLUSIVE_FEATURES[req_level]
                return {
                    "level": req_level,
                    "level_name": features["name"],
                    "features": features.get(feature_type, [])
                }
        return None


# ==================== 8. 等级挑战系统 ====================

class LevelChallengeSystem:
    """等级挑战任务系统"""

    CHALLENGES = {
        "weekly_challenge": {
            "name": "每周挑战",
            "duration_days": 7,
            "min_level": 1,
            "tasks": [
                {"type": "earn_credits", "target": 5000, "progress": 0, "reward": 500},
                {"type": "complete_transactions", "target": 10, "progress": 0, "reward": 300},
                {"type": "help_others", "target": 5, "progress": 0, "reward": 200}
            ],
            "completion_reward": {"credits": 2000, "badge": "🏅"}
        },
        "level_up_challenge": {
            "name": "升级挑战",
            "duration_days": 30,
            "min_level": 3,
            "tasks": [
                {"type": "reach_level", "target": 5, "progress": 0, "reward": 5000},
                {"type": "unlock_features", "target": 3, "progress": 0, "reward": 3000}
            ],
            "completion_reward": {"credits": 10000, "title": "挑战者"}
        },
        "social_challenge": {
            "name": "社交挑战",
            "duration_days": 14,
            "min_level": 2,
            "tasks": [
                {"type": "add_friends", "target": 10, "progress": 0, "reward": 500},
                {"type": "join_groups", "target": 3, "progress": 0, "reward": 300},
                {"type": "send_messages", "target": 50, "progress": 0, "reward": 200}
            ],
            "completion_reward": {"credits": 1500, "badge": "🦋"}
        }
    }

    def __init__(self):
        self.user_challenges: Dict[str, Dict] = defaultdict(dict)

    async def get_level_based_challenges(self, user_id: str, user_level: int) -> List[Dict]:
        """获取等级相关挑战"""
        available_challenges = []

        for challenge_id, challenge in self.CHALLENGES.items():
            if challenge.get("min_level", 1) <= user_level:
                progress = await self.get_challenge_progress(user_id, challenge_id)

                available_challenges.append({
                    "id": challenge_id,
                    "name": challenge["name"],
                    "duration_days": challenge["duration_days"],
                    "tasks": challenge["tasks"],
                    "progress": progress,
                    "completion_reward": challenge.get("completion_reward", {}),
                    "estimated_time": await self.estimate_completion_time(challenge, progress)
                })

        return available_challenges

    async def get_challenge_progress(self, user_id: str, challenge_id: str) -> Dict:
        """获取挑战进度"""
        key = f"{user_id}_{challenge_id}"
        if key not in self.user_challenges:
            self.user_challenges[key] = {
                "started_at": datetime.now().isoformat(),
                "task_progress": {},
                "completed": False
            }
        return self.user_challenges[key]

    async def estimate_completion_time(self, challenge: Dict, progress: Dict) -> str:
        """估算完成时间"""
        remaining_tasks = sum(
            1 for task in challenge.get("tasks", [])
            if progress.get("task_progress", {}).get(task["type"], 0) < task["target"]
        )

        if remaining_tasks == 0:
            return "已完成"

        days_remaining = challenge.get("duration_days", 7)
        return f"约 {remaining_tasks * days_remaining // 3} 天"


# ==================== 9. 等级排行榜 ====================

class LevelLeaderboard:
    """等级排行榜"""

    def __init__(self):
        self.leaderboard_cache: Dict[str, List[Dict]] = {}
        self.cache_time: Dict[str, datetime] = {}

    async def get_leaderboards(self, user_id: str, scope: str = "global") -> Dict:
        """获取排行榜"""
        # 模拟排行榜数据
        leaders = await self._generate_mock_leaders(user_id, scope)

        # 添加奖牌
        for i, leader in enumerate(leaders[:10]):
            if i == 0:
                leader["medal"] = "🥇"
            elif i == 1:
                leader["medal"] = "🥈"
            elif i == 2:
                leader["medal"] = "🥉"
            else:
                leader["medal"] = f"#{i + 1}"

            leader["trend"] = random.choice(["↑3", "↓2", "→", "↑1", "新"])

        # 用户排名
        user_position = self._find_user_position(user_id, leaders)

        return {
            "scope": scope,
            "updated_at": datetime.now().isoformat(),
            "leaders": leaders[:100],
            "user_position": user_position,
            "next_reward_at": await self.get_next_reward_time()
        }

    async def _generate_mock_leaders(self, user_id: str, scope: str) -> List[Dict]:
        """生成模拟排行榜数据"""
        names = ["AI大师", "数据侠", "代码狂", "算法师", "网络王", "创意家",
                 "效率帝", "技术宅", "智慧星", "创新者"]
        levels = [8, 7, 7, 6, 6, 5, 5, 4, 4, 3]

        leaders = []
        for i in range(20):
            leaders.append({
                "user_id": f"user_{i}" if i < 10 else user_id if i == 10 else f"user_other_{i}",
                "nickname": names[i % len(names)] + (f"_{i}" if i >= 10 else ""),
                "level": levels[i % len(levels)],
                "total_credits": (10 - i) * 50000 + random.randint(0, 10000),
                "is_current_user": i == 10
            })

        # 确保当前用户在列表中
        user_in_list = any(l.get("is_current_user") for l in leaders)
        if not user_in_list:
            leaders.append({
                "user_id": user_id,
                "nickname": "你",
                "level": 3,
                "total_credits": 25000,
                "is_current_user": True
            })

        leaders.sort(key=lambda x: x["total_credits"], reverse=True)
        return leaders

    def _find_user_position(self, user_id: str, leaders: List[Dict]) -> Dict:
        """查找用户排名"""
        for i, leader in enumerate(leaders):
            if leader.get("user_id") == user_id:
                return {
                    "rank": i + 1,
                    "level": leader["level"],
                    "credits": leader["total_credits"],
                    "medal": "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"#{i + 1}"
                }

        return {"rank": "未上榜", "level": 0, "credits": 0}

    async def get_next_reward_time(self) -> str:
        """获取下次奖励时间"""
        # 每周一结算
        today = datetime.now()
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0 and today.hour >= 12:
            days_until_monday = 7

        next_monday = today + timedelta(days=days_until_monday)
        next_monday = next_monday.replace(hour=12, minute=0, second=0)

        return next_monday.isoformat()


# ==================== 10. 等级炫耀系统 ====================

class LevelShowcaseSystem:
    """等级炫耀系统"""

    SHOWCASE_TEMPLATES = {
        "classic": {"name": "经典", "style": "traditional"},
        "modern": {"name": "现代", "style": "gradient"},
        "gaming": {"name": "游戏风", "style": "neon"},
        "minimal": {"name": "简约", "style": "clean"}
    }

    def __init__(self, level_system: DynamicLevelSystem = None):
        self.level_system = level_system or DynamicLevelSystem()
        self.showcases: Dict[str, Dict] = {}

    async def create_showcase(self, user_id: str, showcase_type: str = "public") -> Dict:
        """创建炫耀卡片"""
        level_info = await self.level_system.calculate_user_level(user_id)
        achievements = await self.get_recent_achievements(user_id)

        showcase = {
            "user_id": user_id,
            "level": level_info["level"],
            "level_name": level_info["name"],
            "level_emoji": level_info["emoji"],
            "total_credits": level_info["total_credits"],
            "showcase_type": showcase_type,
            "created_at": datetime.now().isoformat(),
            "achievements": achievements[:3],
            "stats": await self.get_impressive_stats(user_id),
            "theme": await self.select_showcase_theme(level_info["level"])
        }

        # 生成炫耀卡片
        showcase_id = f"showcase_{uuid.uuid4().hex[:8]}"
        self.showcases[showcase_id] = showcase

        return {
            "showcase_id": showcase_id,
            "card_url": f"/showcase/{showcase_id}.png",
            "qr_code_url": f"/qr/{showcase_id}.png",
            "share_text": self.generate_share_text(level_info)
        }

    async def get_recent_achievements(self, user_id: str) -> List[Dict]:
        """获取最近成就"""
        return [
            {"name": "快速学习者", "badge": "🚀"},
            {"name": "挂机大师", "badge": "⏳"}
        ]

    async def get_impressive_stats(self, user_id: str) -> Dict:
        """获取令人印象深刻的统计"""
        return {
            "total_online_hours": 500,
            "transactions_completed": 120,
            "friends_count": 35,
            "achievements_count": 8
        }

    async def select_showcase_theme(self, level: int) -> Dict:
        """选择炫耀主题"""
        if level >= 8:
            return self.SHOWCASE_TEMPLATES["gaming"]
        elif level >= 5:
            return self.SHOWCASE_TEMPLATES["modern"]
        elif level >= 3:
            return self.SHOWCASE_TEMPLATES["classic"]
        else:
            return self.SHOWCASE_TEMPLATES["minimal"]

    def generate_share_text(self, level_info: Dict) -> str:
        """生成分享文案"""
        templates = [
            f"刚刚达到 {level_info['name']} 等级！距离下一级还差 {level_info['credits_to_next']:,} 积分 💪",
            f"🎉 升级到 {level_info['name']} 啦！在这个数字社会稳步成长中~",
            f"累计获得 {level_info['total_credits']:,} 积分，成为 {level_info['name']} 等级用户！"
        ]
        return random.choice(templates)


# ==================== 11. 等级养成宠物 ====================

class LevelCompanionPet:
    """等级养成宠物"""

    PET_TYPES = {
        "digital_cat": {
            "name": "电子猫",
            "base_speed": 1.0,
            "idle_bonus": 1.1,
            "emoji": "🐱",
            "min_level": 1
        },
        "data_dragon": {
            "name": "数据龙",
            "base_speed": 1.2,
            "idle_bonus": 1.3,
            "emoji": "🐉",
            "min_level": 4
        },
        "ai_phoenix": {
            "name": "AI凤凰",
            "base_speed": 1.5,
            "idle_bonus": 1.8,
            "emoji": "🦅",
            "min_level": 6
        },
        "quantum_fox": {
            "name": "量子狐狸",
            "base_speed": 2.0,
            "idle_bonus": 2.5,
            "emoji": "🦊",
            "min_level": 8
        }
    }

    def __init__(self):
        self.user_pets: Dict[str, Dict] = {}

    async def get_level_based_pet(self, user_id: str, user_level: int = None) -> Dict:
        """获取基于等级的宠物"""
        if user_level is None:
            user_level = await self.get_user_level(user_id)

        # 根据等级选择宠物
        pet_type = "digital_cat"
        for ptype, pinfo in sorted(self.PET_TYPES.items(), key=lambda x: x[1]["min_level"], reverse=True):
            if user_level >= pinfo["min_level"]:
                pet_type = ptype
                break

        pet_info = self.PET_TYPES[pet_type]

        # 获取或创建宠物
        if user_id not in self.user_pets:
            self.user_pets[user_id] = {
                "type": pet_type,
                "name": await self.generate_pet_name(pet_type),
                "level": user_level,
                "exp": 0,
                "skills": []
            }

        pet = self.user_pets[user_id]

        return {
            "type": pet_type,
            "name": pet["name"],
            "emoji": pet_info["emoji"],
            "level": user_level,
            "stats": {
                "idle_bonus": pet_info["idle_bonus"],
                "collection_speed": pet_info["base_speed"] * (1 + user_level * 0.1)
            },
            "appearance": await self.generate_pet_appearance(pet_type, user_level),
            "abilities": await self.get_pet_abilities(pet_type, user_level)
        }

    async def get_user_level(self, user_id: str) -> int:
        """获取用户等级"""
        return 3  # 模拟

    async def generate_pet_name(self, pet_type: str) -> str:
        """生成宠物名字"""
        prefixes = ["小", "可爱", "聪明", "超级", "无敌"]
        suffixes = ["球", "宝", "蛋", "灵", "豆"]

        prefix = random.choice(prefixes)
        suffix = suffixes[list(self.PET_TYPES.keys()).index(pet_type) % len(suffixes)]

        return f"{prefix}{suffix}"

    async def generate_pet_appearance(self, pet_type: str, level: int) -> Dict:
        """生成宠物外观"""
        colors = ["红色", "蓝色", "金色", "紫色", "绿色"]
        return {
            "color": random.choice(colors),
            "size": "medium" if level < 5 else "large",
            "accessories": ["帽子", "眼镜", "披风", "项链"][:min(level // 3, 4)]
        }

    async def get_pet_abilities(self, pet_type: str, level: int) -> List[str]:
        """获取宠物技能"""
        abilities = ["自动收集", "双倍积分"]
        if level >= 3:
            abilities.append("幸运加成")
        if level >= 5:
            abilities.append("社交光环")
        if level >= 7:
            abilities.append("时间扭曲")
        return abilities

    async def pet_collect_credits(self, user_id: str) -> Dict:
        """宠物收集积分"""
        pet = await self.get_level_based_pet(user_id)
        if not pet:
            return {"credits": 0, "message": "无宠物"}

        # 计算收集量
        collection_rate = pet["stats"]["collection_speed"]
        idle_bonus = pet["stats"]["idle_bonus"]

        # 基础收集
        base_collection = 10 * collection_rate

        # 宠物技能加成
        skill_bonus = 1.0  # 简化

        # 随机事件
        random_event = None
        if random.random() < 0.1:
            events = [
                {"type": "lucky", "multiplier": 2.0, "message": "宠物发现宝藏！"},
                {"type": "bonus", "multiplier": 1.5, "message": "宠物找到零食！"}
            ]
            random_event = random.choice(events)

        total_credits = int(base_collection * idle_bonus * skill_bonus)

        if random_event:
            total_credits = int(total_credits * random_event["multiplier"])

        return {
            "credits": total_credits,
            "pet_name": pet["name"],
            "pet_emoji": pet["emoji"],
            "collection_rate": collection_rate,
            "bonus_multiplier": idle_bonus * skill_bonus,
            "random_event": random_event,
            "next_collection": (datetime.now() + timedelta(minutes=30)).isoformat()
        }


# ==================== 统一管理器 ====================

class IdleGradeSystem:
    """挂机积分与等级系统统一管理器"""

    def __init__(self):
        # 核心子系统
        self.idle_credits = IdleCreditSystem()
        self.mini_games = IdleMiniGame()
        self.level_system = DynamicLevelSystem()
        self.privileges = LevelPrivileges(self.level_system)
        self.achievements = LevelAchievementSystem()
        self.daily_rewards = DailyLoginReward()
        self.exclusive_features = LevelExclusiveFeatures()
        self.challenges = LevelChallengeSystem()
        self.leaderboards = LevelLeaderboard()
        self.showcase = LevelShowcaseSystem(self.level_system)
        self.pets = LevelCompanionPet()

    async def get_user_dashboard(self, user_id: str) -> Dict:
        """获取用户仪表板"""
        # 获取基本信息
        level_info = await self.level_system.calculate_user_level(user_id)
        privileges = await self.privileges.get_user_privileges(user_id)
        daily_reward = await self.daily_rewards.get_daily_reward(user_id)
        achievements = await self.achievements.get_user_achievements(user_id)
        challenges = await self.challenges.get_level_based_challenges(user_id, level_info["level"])
        leaderboard = await self.leaderboards.get_leaderboards(user_id, "global")
        pet = await self.pets.get_level_based_pet(user_id, level_info["level"])

        # 计算今日收益
        today_rewards = await self.idle_credits.calculate_idle_rewards(user_id)

        return {
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),

            # 等级信息
            "level": level_info,

            # 今日收益
            "today_idle_rewards": today_rewards,

            # 特权
            "privileges": privileges,

            # 每日奖励
            "daily_reward": daily_reward,

            # 成就
            "achievements": achievements,
            "achievement_count": len([a for a in achievements if a.get("unlocked")]),

            # 挑战
            "challenges": challenges,

            # 排行榜
            "leaderboard": leaderboard,

            # 宠物
            "pet": pet,

            # 小游戏
            "mini_games": self.mini_games.get_available_games()
        }

    def get_system_status(self) -> Dict:
        """获取系统状态"""
        return {
            "status": "running",
            "version": "1.0.0",
            "modules": {
                "idle_credits": "active",
                "mini_games": "active",
                "level_system": "active",
                "achievements": "active",
                "daily_rewards": "active",
                "challenges": "active",
                "leaderboards": "active",
                "pets": "active"
            },
            "timestamp": datetime.now().isoformat()
        }
