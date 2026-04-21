"""
用户数字分身模块
User Digital Twin Module

实现用户数字分身的管理、出租和参与活动的功能。
"""

import json
import uuid
import time
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import threading


class TwinStatus(Enum):
    """数字分身状态"""
    IDLE = "idle"          # 空闲
    BUSY = "busy"          # 忙碌（参与活动）
    RENTED = "rented"      # 已出租
    MAINTENANCE = "maintenance"  # 维护中
    OFFLINE = "offline"     # 离线


class TwinSkillLevel(Enum):
    """技能等级"""
    NOVICE = "novice"      # 新手
    INTERMEDIATE = "intermediate"  # 中级
    ADVANCED = "advanced"  # 高级
    EXPERT = "expert"      # 专家
    MASTER = "master"      # 大师


class ActivityType(Enum):
    """活动类型"""
    MEETING = "meeting"            # 会议
    LEARNING = "learning"          # 学习
    GAMING = "gaming"              # 游戏
    SOCIAL = "social"              # 社交
    WORK = "work"                  # 工作
    SHOPPING = "shopping"          # 购物
    ENTERTAINMENT = "entertainment"  # 娱乐
    OTHER = "other"                # 其他


class RentalStatus(Enum):
    """出租状态"""
    PENDING = "pending"      # 待确认
    ACTIVE = "active"        # 进行中
    COMPLETED = "completed"  # 已完成
    CANCELLED = "cancelled"  # 已取消


@dataclass
class UserTwin:
    """用户数字分身"""
    twin_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    name: str
    avatar_url: str = ""
    status: str = TwinStatus.IDLE.value
    level: int = 1
    experience: int = 0
    skills: Dict[str, int] = field(default_factory=dict)  # {skill_name: level}
    attributes: Dict[str, float] = field(default_factory=dict)  # {attribute: value}
    inventory: List[Dict] = field(default_factory=list)  # 物品栏
    activities: List[str] = field(default_factory=list)  # 参与过的活动ID
    rentals: List[str] = field(default_factory=list)  # 出租记录ID
    settings: Dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def add_experience(self, amount: int) -> bool:
        """添加经验值"""
        self.experience += amount
        # 检查是否升级
        new_level = self._calculate_level()
        if new_level > self.level:
            self.level = new_level
            return True
        return False

    def _calculate_level(self) -> int:
        """计算等级"""
        # 简单的等级计算：每100点经验升一级
        return (self.experience // 100) + 1

    def add_skill(self, skill_name: str, level: int = 1):
        """添加或升级技能"""
        current_level = self.skills.get(skill_name, 0)
        if level > current_level:
            self.skills[skill_name] = level

    def update_status(self, new_status: str):
        """更新状态"""
        self.status = new_status
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "twin_id": self.twin_id,
            "user_id": self.user_id,
            "name": self.name,
            "avatar_url": self.avatar_url,
            "status": self.status,
            "level": self.level,
            "experience": self.experience,
            "skills": self.skills,
            "attributes": self.attributes,
            "inventory": self.inventory,
            "activities": self.activities,
            "rentals": self.rentals,
            "settings": self.settings,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserTwin":
        """从字典创建"""
        return cls(**data)


@dataclass
class Activity:
    """活动"""
    activity_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    activity_type: str
    organizer_id: str
    start_time: str
    end_time: str
    duration_minutes: int
    required_skills: Dict[str, int] = field(default_factory=dict)  # {skill: level}
    rewards: Dict[str, Any] = field(default_factory=dict)  # 奖励
    participants: List[str] = field(default_factory=list)  # 参与者ID
    status: str = "scheduled"  # scheduled, ongoing, completed, cancelled
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def is_available(self, current_time: str) -> bool:
        """检查活动是否可参与"""
        return current_time < self.start_time and self.status == "scheduled"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "activity_id": self.activity_id,
            "name": self.name,
            "description": self.description,
            "activity_type": self.activity_type,
            "organizer_id": self.organizer_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_minutes": self.duration_minutes,
            "required_skills": self.required_skills,
            "rewards": self.rewards,
            "participants": self.participants,
            "status": self.status,
            "created_at": self.created_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Activity":
        """从字典创建"""
        return cls(**data)


@dataclass
class RentalRequest:
    """出租请求"""
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    twin_id: str
    renter_id: str
    activity_id: str
    start_time: str
    end_time: str
    duration_minutes: int
    price: float
    status: str = RentalStatus.PENDING.value
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def update_status(self, new_status: str):
        """更新状态"""
        self.status = new_status
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "request_id": self.request_id,
            "twin_id": self.twin_id,
            "renter_id": self.renter_id,
            "activity_id": self.activity_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_minutes": self.duration_minutes,
            "price": self.price,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RentalRequest":
        """从字典创建"""
        return cls(**data)


class UserTwinManager:
    """用户数字分身管理器"""

    def __init__(self, storage_path: str = None):
        from pathlib import Path
        if storage_path is None:
            storage_path = Path("~/.hermes/digital_twin").expanduser()

        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # 存储文件
        self.twins_file = self.storage_path / "twins.json"
        self.activities_file = self.storage_path / "activities.json"
        self.rentals_file = self.storage_path / "rentals.json"

        # 内存存储
        self.twins: Dict[str, UserTwin] = {}
        self.activities: Dict[str, Activity] = {}
        self.rentals: Dict[str, RentalRequest] = {}

        # 锁
        self._lock = threading.RLock()

        # 加载数据
        self._load_data()

    def _load_data(self):
        """加载数据"""
        try:
            if self.twins_file.exists():
                with open(self.twins_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for twin_id, twin_data in data.items():
                        self.twins[twin_id] = UserTwin.from_dict(twin_data)

            if self.activities_file.exists():
                with open(self.activities_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for activity_id, activity_data in data.items():
                        self.activities[activity_id] = Activity.from_dict(activity_data)

            if self.rentals_file.exists():
                with open(self.rentals_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for request_id, rental_data in data.items():
                        self.rentals[request_id] = RentalRequest.from_dict(rental_data)
        except Exception as e:
            print(f"加载数据失败: {e}")

    def _save_data(self):
        """保存数据"""
        try:
            # 保存数字分身
            twins_data = {twin_id: twin.to_dict() for twin_id, twin in self.twins.items()}
            with open(self.twins_file, "w", encoding="utf-8") as f:
                json.dump(twins_data, f, ensure_ascii=False, indent=2)

            # 保存活动
            activities_data = {activity_id: activity.to_dict() for activity_id, activity in self.activities.items()}
            with open(self.activities_file, "w", encoding="utf-8") as f:
                json.dump(activities_data, f, ensure_ascii=False, indent=2)

            # 保存出租记录
            rentals_data = {request_id: rental.to_dict() for request_id, rental in self.rentals.items()}
            with open(self.rentals_file, "w", encoding="utf-8") as f:
                json.dump(rentals_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存数据失败: {e}")

    def create_twin(self, user_id: str, name: str, avatar_url: str = "") -> UserTwin:
        """创建数字分身"""
        with self._lock:
            twin = UserTwin(user_id=user_id, name=name, avatar_url=avatar_url)
            self.twins[twin.twin_id] = twin
            self._save_data()
            return twin

    def get_twin(self, twin_id: str) -> Optional[UserTwin]:
        """获取数字分身"""
        return self.twins.get(twin_id)

    def get_user_twins(self, user_id: str) -> List[UserTwin]:
        """获取用户的所有数字分身"""
        return [twin for twin in self.twins.values() if twin.user_id == user_id]

    def update_twin(self, twin_id: str, **kwargs) -> bool:
        """更新数字分身"""
        with self._lock:
            twin = self.twins.get(twin_id)
            if not twin:
                return False

            for key, value in kwargs.items():
                if hasattr(twin, key):
                    setattr(twin, key, value)

            twin.updated_at = datetime.now().isoformat()
            self._save_data()
            return True

    def delete_twin(self, twin_id: str) -> bool:
        """删除数字分身"""
        with self._lock:
            if twin_id in self.twins:
                del self.twins[twin_id]
                self._save_data()
                return True
            return False

    def create_activity(self, name: str, description: str, activity_type: str, 
                       organizer_id: str, start_time: str, end_time: str, 
                       duration_minutes: int, required_skills: Dict[str, int] = None, 
                       rewards: Dict[str, Any] = None) -> Activity:
        """创建活动"""
        with self._lock:
            activity = Activity(
                name=name,
                description=description,
                activity_type=activity_type,
                organizer_id=organizer_id,
                start_time=start_time,
                end_time=end_time,
                duration_minutes=duration_minutes,
                required_skills=required_skills or {},
                rewards=rewards or {}
            )
            self.activities[activity.activity_id] = activity
            self._save_data()
            return activity

    def get_activity(self, activity_id: str) -> Optional[Activity]:
        """获取活动"""
        return self.activities.get(activity_id)

    def list_activities(self, activity_type: str = None, status: str = None) -> List[Activity]:
        """列出活动"""
        activities = list(self.activities.values())

        if activity_type:
            activities = [a for a in activities if a.activity_type == activity_type]

        if status:
            activities = [a for a in activities if a.status == status]

        return activities

    def create_rental_request(self, twin_id: str, renter_id: str, activity_id: str, 
                             start_time: str, end_time: str, duration_minutes: int, 
                             price: float) -> RentalRequest:
        """创建出租请求"""
        with self._lock:
            # 检查数字分身是否存在且空闲
            twin = self.twins.get(twin_id)
            if not twin or twin.status != TwinStatus.IDLE.value:
                raise ValueError("数字分身不存在或不空闲")

            # 检查活动是否存在
            activity = self.activities.get(activity_id)
            if not activity:
                raise ValueError("活动不存在")

            rental = RentalRequest(
                twin_id=twin_id,
                renter_id=renter_id,
                activity_id=activity_id,
                start_time=start_time,
                end_time=end_time,
                duration_minutes=duration_minutes,
                price=price
            )
            self.rentals[rental.request_id] = rental
            self._save_data()
            return rental

    def accept_rental_request(self, request_id: str) -> bool:
        """接受出租请求"""
        with self._lock:
            rental = self.rentals.get(request_id)
            if not rental or rental.status != RentalStatus.PENDING.value:
                return False

            # 更新出租状态
            rental.update_status(RentalStatus.ACTIVE.value)

            # 更新数字分身状态
            twin = self.twins.get(rental.twin_id)
            if twin:
                twin.update_status(TwinStatus.RENTED.value)

            # 添加到数字分身的出租记录
            if twin and rental.request_id not in twin.rentals:
                twin.rentals.append(rental.request_id)

            self._save_data()
            return True

    def complete_rental_request(self, request_id: str) -> bool:
        """完成出租请求"""
        with self._lock:
            rental = self.rentals.get(request_id)
            if not rental or rental.status != RentalStatus.ACTIVE.value:
                return False

            # 更新出租状态
            rental.update_status(RentalStatus.COMPLETED.value)

            # 更新数字分身状态
            twin = self.twins.get(rental.twin_id)
            if twin:
                twin.update_status(TwinStatus.IDLE.value)

                # 添加经验值
                twin.add_experience(rental.duration_minutes)

            self._save_data()
            return True

    def cancel_rental_request(self, request_id: str) -> bool:
        """取消出租请求"""
        with self._lock:
            rental = self.rentals.get(request_id)
            if not rental or rental.status not in [RentalStatus.PENDING.value, RentalStatus.ACTIVE.value]:
                return False

            # 更新出租状态
            rental.update_status(RentalStatus.CANCELLED.value)

            # 更新数字分身状态
            twin = self.twins.get(rental.twin_id)
            if twin and twin.status == TwinStatus.RENTED.value:
                twin.update_status(TwinStatus.IDLE.value)

            self._save_data()
            return True

    def get_rental_request(self, request_id: str) -> Optional[RentalRequest]:
        """获取出租请求"""
        return self.rentals.get(request_id)

    def get_user_rental_requests(self, user_id: str) -> List[RentalRequest]:
        """获取用户的出租请求"""
        # 获取用户的数字分身
        user_twins = self.get_user_twins(user_id)
        twin_ids = {twin.twin_id for twin in user_twins}

        # 获取这些数字分身的出租请求
        return [rental for rental in self.rentals.values() if rental.twin_id in twin_ids]

    def get_renter_rental_requests(self, renter_id: str) -> List[RentalRequest]:
        """获取租户的出租请求"""
        return [rental for rental in self.rentals.values() if rental.renter_id == renter_id]

    def get_twin_compatibility(self, twin_id: str, activity_id: str) -> float:
        """计算数字分身与活动的兼容性"""
        twin = self.twins.get(twin_id)
        activity = self.activities.get(activity_id)

        if not twin or not activity:
            return 0.0

        # 计算技能匹配度
        required_skills = activity.required_skills
        if not required_skills:
            return 1.0

        total_skills = len(required_skills)
        matching_skills = 0

        for skill, required_level in required_skills.items():
            twin_level = twin.skills.get(skill, 0)
            if twin_level >= required_level:
                matching_skills += 1

        return matching_skills / total_skills if total_skills > 0 else 1.0

    def recommend_activities(self, twin_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """推荐活动"""
        twin = self.twins.get(twin_id)
        if not twin:
            return []

        current_time = datetime.now().isoformat()
        available_activities = [a for a in self.activities.values() if a.is_available(current_time)]

        # 计算兼容性并排序
        activity_scores = []
        for activity in available_activities:
            compatibility = self.get_twin_compatibility(twin_id, activity.activity_id)
            activity_scores.append((activity, compatibility))

        # 按兼容性排序
        activity_scores.sort(key=lambda x: x[1], reverse=True)

        # 返回推荐结果
        recommendations = []
        for activity, score in activity_scores[:limit]:
            recommendations.append({
                "activity": activity.to_dict(),
                "compatibility": score
            })

        return recommendations

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_twins = len(self.twins)
        total_activities = len(self.activities)
        total_rentals = len(self.rentals)

        # 状态统计
        status_counts = {}
        for twin in self.twins.values():
            status = twin.status
            status_counts[status] = status_counts.get(status, 0) + 1

        # 活动类型统计
        activity_type_counts = {}
        for activity in self.activities.values():
            activity_type = activity.activity_type
            activity_type_counts[activity_type] = activity_type_counts.get(activity_type, 0) + 1

        return {
            "total_twins": total_twins,
            "total_activities": total_activities,
            "total_rentals": total_rentals,
            "status_counts": status_counts,
            "activity_type_counts": activity_type_counts
        }


# 全局实例
_user_twin_manager: Optional[UserTwinManager] = None
_user_twin_manager_lock = threading.Lock()


def get_user_twin_manager() -> UserTwinManager:
    """获取用户数字分身管理器"""
    global _user_twin_manager
    if _user_twin_manager is None:
        with _user_twin_manager_lock:
            if _user_twin_manager is None:
                _user_twin_manager = UserTwinManager()
    return _user_twin_manager


def create_user_twin(user_id: str, name: str, avatar_url: str = "") -> UserTwin:
    """创建用户数字分身"""
    return get_user_twin_manager().create_twin(user_id, name, avatar_url)


def get_user_twins(user_id: str) -> List[UserTwin]:
    """获取用户的所有数字分身"""
    return get_user_twin_manager().get_user_twins(user_id)
