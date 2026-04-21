"""
积分经济系统
Credit Economy System

实现用户积分管理、养成系统和游戏系统的功能。
"""

import json
import uuid
import time
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import threading


class TransactionType(Enum):
    """交易类型"""
    EARN = "earn"          # 赚取积分
    SPEND = "spend"        # 花费积分
    TRANSFER = "transfer"  # 转移积分
    RENT = "rent"          # 出租收入
    FINE = "fine"          # 罚款
    REWARD = "reward"      # 奖励


class AchievementType(Enum):
    """成就类型"""
    FIRST_LOGIN = "first_login"            # 首次登录
    TWIN_CREATED = "twin_created"          # 创建数字分身
    ACTIVITY_PARTICIPATED = "activity_participated"  # 参与活动
    TWIN_RENTED = "twin_rented"            # 出租数字分身
    LEVEL_UP = "level_up"                  # 升级
    SKILL_MASTERED = "skill_mastered"      # 掌握技能
    BADGE_EARNED = "badge_earned"          # 获得徽章


class BadgeType(Enum):
    """徽章类型"""
    NEWBIE = "newbie"                # 新手
    SOCIALITE = "socialite"          # 社交达人
    RENTAL_KING = "rental_king"      # 出租之王
    SKILL_MASTER = "skill_master"    # 技能大师
    ACTIVITY_HUNTER = "activity_hunter"  # 活动猎手
    WEALTHY = "wealthy"              # 富有的
    LOYAL = "loyal"                  # 忠诚的


@dataclass
class Transaction:
    """交易记录"""
    user_id: str
    amount: int
    transaction_type: str
    description: str
    transaction_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    related_id: str = ""  # 相关ID（如活动ID、出租ID等）
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "transaction_id": self.transaction_id,
            "user_id": self.user_id,
            "amount": self.amount,
            "transaction_type": self.transaction_type,
            "description": self.description,
            "related_id": self.related_id,
            "created_at": self.created_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Transaction":
        """从字典创建"""
        return cls(**data)


@dataclass
class Achievement:
    """成就"""
    user_id: str
    achievement_type: str
    name: str
    description: str
    achievement_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    progress: float = 0.0  # 进度 (0-1)
    completed: bool = False
    completed_at: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "achievement_id": self.achievement_id,
            "user_id": self.user_id,
            "achievement_type": self.achievement_type,
            "name": self.name,
            "description": self.description,
            "progress": self.progress,
            "completed": self.completed,
            "completed_at": self.completed_at,
            "created_at": self.created_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Achievement":
        """从字典创建"""
        return cls(**data)


@dataclass
class Badge:
    """徽章"""
    user_id: str
    badge_type: str
    name: str
    description: str
    badge_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    level: int = 1
    acquired_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "badge_id": self.badge_id,
            "user_id": self.user_id,
            "badge_type": self.badge_type,
            "name": self.name,
            "description": self.description,
            "level": self.level,
            "acquired_at": self.acquired_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Badge":
        """从字典创建"""
        return cls(**data)


@dataclass
class UserCredit:
    """用户积分"""
    user_id: str
    balance: int = 0
    total_earned: int = 0
    total_spent: int = 0
    last_transaction_at: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def add_credit(self, amount: int, transaction_type: str, description: str, related_id: str = "") -> Transaction:
        """添加积分"""
        self.balance += amount
        self.total_earned += amount
        self.last_transaction_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()

        return Transaction(
            user_id=self.user_id,
            amount=amount,
            transaction_type=transaction_type,
            description=description,
            related_id=related_id
        )

    def deduct_credit(self, amount: int, transaction_type: str, description: str, related_id: str = "") -> Optional[Transaction]:
        """扣除积分"""
        if self.balance < amount:
            return None

        self.balance -= amount
        self.total_spent += amount
        self.last_transaction_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()

        return Transaction(
            user_id=self.user_id,
            amount=-amount,
            transaction_type=transaction_type,
            description=description,
            related_id=related_id
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "user_id": self.user_id,
            "balance": self.balance,
            "total_earned": self.total_earned,
            "total_spent": self.total_spent,
            "last_transaction_at": self.last_transaction_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserCredit":
        """从字典创建"""
        return cls(**data)


class CreditEconomySystem:
    """积分经济系统"""

    def __init__(self, storage_path: str = None):
        from pathlib import Path
        if storage_path is None:
            storage_path = Path("~/.hermes/credit_economy").expanduser()

        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # 存储文件
        self.credits_file = self.storage_path / "credits.json"
        self.transactions_file = self.storage_path / "transactions.json"
        self.achievements_file = self.storage_path / "achievements.json"
        self.badges_file = self.storage_path / "badges.json"

        # 内存存储
        self.credits: Dict[str, UserCredit] = {}
        self.transactions: List[Transaction] = []
        self.achievements: Dict[str, Achievement] = {}
        self.badges: Dict[str, Badge] = {}

        # 锁
        self._lock = threading.RLock()

        # 加载数据
        self._load_data()

    def _load_data(self):
        """加载数据"""
        try:
            if self.credits_file.exists():
                with open(self.credits_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for user_id, credit_data in data.items():
                        self.credits[user_id] = UserCredit.from_dict(credit_data)

            if self.transactions_file.exists():
                with open(self.transactions_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for transaction_data in data:
                        self.transactions.append(Transaction.from_dict(transaction_data))

            if self.achievements_file.exists():
                with open(self.achievements_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for achievement_id, achievement_data in data.items():
                        self.achievements[achievement_id] = Achievement.from_dict(achievement_data)

            if self.badges_file.exists():
                with open(self.badges_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for badge_id, badge_data in data.items():
                        self.badges[badge_id] = Badge.from_dict(badge_data)
        except Exception as e:
            print(f"加载数据失败: {e}")

    def _save_data(self):
        """保存数据"""
        try:
            # 保存积分
            credits_data = {user_id: credit.to_dict() for user_id, credit in self.credits.items()}
            with open(self.credits_file, "w", encoding="utf-8") as f:
                json.dump(credits_data, f, ensure_ascii=False, indent=2)

            # 保存交易
            transactions_data = [transaction.to_dict() for transaction in self.transactions]
            with open(self.transactions_file, "w", encoding="utf-8") as f:
                json.dump(transactions_data, f, ensure_ascii=False, indent=2)

            # 保存成就
            achievements_data = {achievement_id: achievement.to_dict() for achievement_id, achievement in self.achievements.items()}
            with open(self.achievements_file, "w", encoding="utf-8") as f:
                json.dump(achievements_data, f, ensure_ascii=False, indent=2)

            # 保存徽章
            badges_data = {badge_id: badge.to_dict() for badge_id, badge in self.badges.items()}
            with open(self.badges_file, "w", encoding="utf-8") as f:
                json.dump(badges_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存数据失败: {e}")

    def get_user_credit(self, user_id: str) -> UserCredit:
        """获取用户积分"""
        with self._lock:
            if user_id not in self.credits:
                self.credits[user_id] = UserCredit(user_id=user_id)
                self._save_data()
            return self.credits[user_id]

    def add_credit(self, user_id: str, amount: int, transaction_type: str, description: str, related_id: str = "") -> Transaction:
        """添加积分"""
        with self._lock:
            credit = self.get_user_credit(user_id)
            transaction = credit.add_credit(amount, transaction_type, description, related_id)
            self.transactions.append(transaction)
            self._save_data()
            return transaction

    def deduct_credit(self, user_id: str, amount: int, transaction_type: str, description: str, related_id: str = "") -> Optional[Transaction]:
        """扣除积分"""
        with self._lock:
            credit = self.get_user_credit(user_id)
            transaction = credit.deduct_credit(amount, transaction_type, description, related_id)
            if transaction:
                self.transactions.append(transaction)
                self._save_data()
            return transaction

    def transfer_credit(self, from_user_id: str, to_user_id: str, amount: int, description: str) -> bool:
        """转移积分"""
        with self._lock:
            # 扣除发送者积分
            deduct_transaction = self.deduct_credit(
                from_user_id, amount, TransactionType.TRANSFER.value,
                f"Transfer to {to_user_id}: {description}"
            )

            if not deduct_transaction:
                return False

            # 添加接收者积分
            self.add_credit(
                to_user_id, amount, TransactionType.TRANSFER.value,
                f"Transfer from {from_user_id}: {description}"
            )

            self._save_data()
            return True

    def get_user_transactions(self, user_id: str, limit: int = 100) -> List[Transaction]:
        """获取用户交易记录"""
        return [t for t in self.transactions if t.user_id == user_id][-limit:]

    def create_achievement(self, user_id: str, achievement_type: str, name: str, description: str) -> Achievement:
        """创建成就"""
        with self._lock:
            achievement = Achievement(
                user_id=user_id,
                achievement_type=achievement_type,
                name=name,
                description=description
            )
            self.achievements[achievement.achievement_id] = achievement
            self._save_data()
            return achievement

    def update_achievement_progress(self, user_id: str, achievement_type: str, progress: float) -> Optional[Achievement]:
        """更新成就进度"""
        with self._lock:
            # 查找用户的该类型成就
            for achievement in self.achievements.values():
                if achievement.user_id == user_id and achievement.achievement_type == achievement_type:
                    achievement.progress = min(progress, 1.0)
                    if achievement.progress >= 1.0 and not achievement.completed:
                        achievement.completed = True
                        achievement.completed_at = datetime.now().isoformat()
                        # 完成成就时奖励积分
                        self.add_credit(
                            user_id, 100, TransactionType.REWARD.value,
                            f"Achievement completed: {achievement.name}"
                        )
                    self._save_data()
                    return achievement
            return None

    def get_user_achievements(self, user_id: str) -> List[Achievement]:
        """获取用户成就"""
        return [a for a in self.achievements.values() if a.user_id == user_id]

    def award_badge(self, user_id: str, badge_type: str, name: str, description: str) -> Badge:
        """授予徽章"""
        with self._lock:
            # 检查是否已经有该类型的徽章
            existing_badge = None
            for badge in self.badges.values():
                if badge.user_id == user_id and badge.badge_type == badge_type:
                    existing_badge = badge
                    break

            if existing_badge:
                # 升级现有徽章
                existing_badge.level += 1
                badge = existing_badge
            else:
                # 创建新徽章
                badge = Badge(
                    user_id=user_id,
                    badge_type=badge_type,
                    name=name,
                    description=description
                )
                self.badges[badge.badge_id] = badge

            # 授予徽章时奖励积分
            self.add_credit(
                user_id, 200, TransactionType.REWARD.value,
                f"Badge awarded: {name}"
            )

            self._save_data()
            return badge

    def get_user_badges(self, user_id: str) -> List[Badge]:
        """获取用户徽章"""
        return [b for b in self.badges.values() if b.user_id == user_id]

    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """获取用户统计信息"""
        credit = self.get_user_credit(user_id)
        achievements = self.get_user_achievements(user_id)
        badges = self.get_user_badges(user_id)

        completed_achievements = [a for a in achievements if a.completed]
        total_achievements = len(achievements)
        completion_rate = len(completed_achievements) / total_achievements if total_achievements > 0 else 0

        return {
            "balance": credit.balance,
            "total_earned": credit.total_earned,
            "total_spent": credit.total_spent,
            "achievements": {
                "total": total_achievements,
                "completed": len(completed_achievements),
                "completion_rate": completion_rate
            },
            "badges": len(badges),
            "last_transaction_at": credit.last_transaction_at
        }

    def process_twin_rental(self, twin_owner_id: str, renter_id: str, amount: int, rental_id: str) -> bool:
        """处理数字分身出租交易"""
        with self._lock:
            # 从租户扣除积分
            renter_transaction = self.deduct_credit(
                renter_id, amount, TransactionType.RENT.value,
                f"Rental payment for twin", rental_id
            )

            if not renter_transaction:
                return False

            # 给数字分身所有者添加积分
            self.add_credit(
                twin_owner_id, amount, TransactionType.RENT.value,
                f"Rental income from twin", rental_id
            )

            # 更新成就进度
            self.update_achievement_progress(
                twin_owner_id, AchievementType.TWIN_RENTED.value, 1.0
            )

            # 检查是否授予徽章
            rental_achievements = [a for a in self.achievements.values() 
                                  if a.user_id == twin_owner_id and 
                                     a.achievement_type == AchievementType.TWIN_RENTED.value and 
                                     a.completed]
            
            if len(rental_achievements) >= 5:
                self.award_badge(
                    twin_owner_id, BadgeType.RENTAL_KING.value,
                    "出租之王", "成功出租数字分身5次"
                )

            self._save_data()
            return True

    def process_activity_participation(self, user_id: str, activity_id: str, reward_amount: int = 50) -> bool:
        """处理活动参与"""
        with self._lock:
            # 奖励积分
            self.add_credit(
                user_id, reward_amount, TransactionType.REWARD.value,
                f"Activity participation reward", activity_id
            )

            # 更新成就进度
            self.update_achievement_progress(
                user_id, AchievementType.ACTIVITY_PARTICIPATED.value, 1.0
            )

            # 检查是否授予徽章
            activity_achievements = [a for a in self.achievements.values() 
                                   if a.user_id == user_id and 
                                      a.achievement_type == AchievementType.ACTIVITY_PARTICIPATED.value and 
                                      a.completed]
            
            if len(activity_achievements) >= 10:
                self.award_badge(
                    user_id, BadgeType.ACTIVITY_HUNTER.value,
                    "活动猎手", "参与活动10次"
                )

            self._save_data()
            return True

    def get_leaderboard(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取排行榜"""
        with self._lock:
            # 按积分余额排序
            sorted_users = sorted(
                self.credits.items(),
                key=lambda x: x[1].balance,
                reverse=True
            )

            leaderboard = []
            for rank, (user_id, credit) in enumerate(sorted_users[:limit], 1):
                leaderboard.append({
                    "rank": rank,
                    "user_id": user_id,
                    "balance": credit.balance,
                    "total_earned": credit.total_earned
                })

            return leaderboard

    def get_stats(self) -> Dict[str, Any]:
        """获取系统统计信息"""
        total_users = len(self.credits)
        total_credits = sum(credit.balance for credit in self.credits.values())
        total_transactions = len(self.transactions)
        total_achievements = len(self.achievements)
        total_badges = len(self.badges)

        # 交易类型统计
        transaction_types = {}
        for transaction in self.transactions:
            transaction_type = transaction.transaction_type
            transaction_types[transaction_type] = transaction_types.get(transaction_type, 0) + 1

        return {
            "total_users": total_users,
            "total_credits": total_credits,
            "total_transactions": total_transactions,
            "total_achievements": total_achievements,
            "total_badges": total_badges,
            "transaction_types": transaction_types
        }


# 全局实例
_credit_system: Optional[CreditEconomySystem] = None
_credit_system_lock = threading.Lock()


def get_credit_system() -> CreditEconomySystem:
    """获取积分经济系统"""
    global _credit_system
    if _credit_system is None:
        with _credit_system_lock:
            if _credit_system is None:
                _credit_system = CreditEconomySystem()
    return _credit_system


def add_credit(user_id: str, amount: int, transaction_type: str, description: str, related_id: str = "") -> Transaction:
    """添加积分"""
    return get_credit_system().add_credit(user_id, amount, transaction_type, description, related_id)


def deduct_credit(user_id: str, amount: int, transaction_type: str, description: str, related_id: str = "") -> Optional[Transaction]:
    """扣除积分"""
    return get_credit_system().deduct_credit(user_id, amount, transaction_type, description, related_id)


def transfer_credit(from_user_id: str, to_user_id: str, amount: int, description: str) -> bool:
    """转移积分"""
    return get_credit_system().transfer_credit(from_user_id, to_user_id, amount, description)


def get_user_credit(user_id: str) -> UserCredit:
    """获取用户积分"""
    return get_credit_system().get_user_credit(user_id)


def get_user_stats(user_id: str) -> Dict[str, Any]:
    """获取用户统计信息"""
    return get_credit_system().get_user_stats(user_id)
