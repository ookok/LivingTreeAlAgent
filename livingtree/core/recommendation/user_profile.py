"""
用户画像管理
支持兴趣标签、行为记录、冷启动策略
"""

import json
import time
from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path


@dataclass
class InterestTag:
    """兴趣标签"""
    name: str           # 标签名
    weight: float = 1.0  # 权重 (0-1)
    count: int = 0       # 行为计数


@dataclass
class UserProfile:
    """
    用户画像
    用于推荐系统的用户特征表示
    """
    user_id: str
    interests: list[InterestTag] = field(default_factory=list)
    click_history: list[str] = field(default_factory=list)  # 内容ID列表
    view_history: list[str] = field(default_factory=list)
    preferred_sources: list[str] = field(default_factory=list)  # 偏好来源
    
    # 统计信息
    total_clicks: int = 0
    total_views: int = 0
    last_active: float = field(default_factory=time.time)
    
    # 冷启动状态
    is_cold_start: bool = True
    
    def add_interest(self, tag_name: str, weight: float = 1.0):
        """添加/更新兴趣标签"""
        for tag in self.interests:
            if tag.name == tag_name:
                tag.count += 1
                tag.weight = min(1.0, tag.weight + 0.1)
                return
        self.interests.append(InterestTag(name=tag_name, weight=weight, count=1))
    
    def record_click(self, content_id: str, content_type: str = ""):
        """记录点击行为"""
        if content_id not in self.click_history:
            self.click_history.append(content_id)
        self.total_clicks += 1
        self.last_active = time.time()
        self.is_cold_start = len(self.click_history) < 5
    
    def record_view(self, content_id: str):
        """记录浏览行为"""
        if content_id not in self.view_history:
            self.view_history.append(content_id)
        self.total_views += 1
        self.last_active = time.time()
    
    def get_top_interests(self, limit: int = 5) -> list[str]:
        """获取Top N兴趣标签"""
        sorted_interests = sorted(self.interests, key=lambda x: x.weight * x.count, reverse=True)
        return [tag.name for tag in sorted_interests[:limit]]
    
    def to_dict(self) -> dict:
        """序列化为字典"""
        data = asdict(self)
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> "UserProfile":
        """从字典反序列化"""
        if "interests" in data and data["interests"]:
            data["interests"] = [InterestTag(**t) if isinstance(t, dict) else t for t in data["interests"]]
        return cls(**data)


class UserProfileManager:
    """
    用户画像管理器
    负责用户画像的加载、保存、查询
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = Path(storage_path) if storage_path else Path.home() / ".hermes-desktop" / "user_profile.json"
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._profile: Optional[UserProfile] = None
    
    def get_profile(self, user_id: str = "default") -> UserProfile:
        """获取用户画像（单例）"""
        if self._profile is None:
            self._profile = self.load(user_id)
        return self._profile
    
    def load(self, user_id: str = "default") -> UserProfile:
        """从文件加载用户画像"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("user_id") == user_id:
                        return UserProfile.from_dict(data)
            except (json.JSONDecodeError, KeyError):
                pass
        
        # 创建新画像
        return UserProfile(user_id=user_id)
    
    def save(self, profile: Optional[UserProfile] = None):
        """保存用户画像到文件"""
        if profile is None:
            profile = self._profile
        if profile:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(profile.to_dict(), f, ensure_ascii=False, indent=2)
    
    def record_behavior(self, content_id: str, content_type: str, behavior: str = "click"):
        """记录用户行为"""
        profile = self.get_profile()
        if behavior == "click":
            profile.record_click(content_id, content_type)
        elif behavior == "view":
            profile.record_view(content_id)
        self.save()
    
    def update_from_tags(self, tags: list[str]):
        """从外部标签更新兴趣"""
        profile = self.get_profile()
        for tag in tags:
            profile.add_interest(tag)
        profile.is_cold_start = len(profile.click_history) >= 5
        self.save()


# 全局单例
_profile_manager: Optional[UserProfileManager] = None


def get_profile_manager(storage_path: Optional[str] = None) -> UserProfileManager:
    """获取全局画像管理器"""
    global _profile_manager
    if _profile_manager is None:
        _profile_manager = UserProfileManager(storage_path)
    return _profile_manager
