# -*- coding: utf-8 -*-
"""
插件定义 - Plugin Definition
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Set
import hashlib
import json


class PluginCategory(Enum):
    """插件分类"""
    PRODUCTIVITY = "productivity"          # 效率工具
    INTEGRATION = "integration"            # 集成服务
    AI_MODELS = "ai_models"                # AI 模型
    AUTOMATION = "automation"              # 自动化
    DATA_VISUALIZATION = "data_viz"        # 数据可视化
    COMMUNICATION = "communication"        # 通讯协作
    DEVELOPER = "developer"                # 开发者工具
    UTILITY = "utility"                   # 实用工具
    ENTERTAINMENT = "entertainment"        # 娱乐
    CUSTOM = "custom"                     # 自定义


class PluginStatus(Enum):
    """插件状态"""
    DRAFT = "draft"            # 草稿
    PENDING = "pending"        # 待审核
    APPROVED = "approved"      # 已通过
    REJECTED = "rejected"      # 已拒绝
    DELETED = "deleted"        # 已删除


@dataclass
class PluginVersion:
    """插件版本"""
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=datetime.now)
    changelog: str = ""
    min_app_version: str = "1.0.0"
    max_app_version: str = ""
    download_url: str = ""
    file_size: int = 0  # bytes
    checksum: str = ""
    is_stable: bool = True
    is_beta: bool = False
    is_latest: bool = True
    
    def get_version_number(self) -> tuple:
        """获取版本号元组"""
        return tuple(int(x) for x in self.version.split('.'))
    
    def is_compatible(self, app_version: str) -> bool:
        """检查兼容性"""
        app_parts = tuple(int(x) for x in app_version.split('.')[:3])
        
        min_parts = tuple(int(x) for x in self.min_app_version.split('.')[:3])
        if app_parts < min_parts:
            return False
        
        if self.max_app_version:
            max_parts = tuple(int(x) for x in self.max_app_version.split('.')[:3])
            if app_parts > max_parts:
                return False
        
        return True


@dataclass
class Plugin:
    """插件"""
    id: str = ""
    name: str = ""
    slug: str = ""  # URL 友好名称
    description: str = ""
    long_description: str = ""
    version: str = "1.0.0"
    
    # 发布者
    author_id: str = ""
    author_name: str = ""
    author_url: str = ""
    homepage_url: str = ""
    support_url: str = ""
    
    # 分类和标签
    category: PluginCategory = PluginCategory.UTILITY
    tags: List[str] = field(default_factory=list)
    
    # 媒体
    icon_url: str = ""
    screenshots: List[str] = field(default_factory=list)
    demo_url: str = ""
    
    # 版本管理
    versions: List[PluginVersion] = field(default_factory=list)
    current_version: Optional[PluginVersion] = None
    
    # 统计
    downloads: int = 0
    rating: float = 0.0
    rating_count: int = 0
    review_count: int = 0
    
    # 权限
    required_permissions: List[str] = field(default_factory=list)
    optional_permissions: List[str] = field(default_factory=list)
    
    # 配置
    settings_schema: Dict = field(default_factory=dict)
    default_settings: Dict = field(default_factory=dict)
    
    # 状态
    status: PluginStatus = PluginStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    published_at: Optional[datetime] = None
    
    # 特性
    is_featured: bool = False
    is_premium: bool = False
    is_open_source: bool = False
    source_url: str = ""
    
    # 本地状态（安装后）
    is_installed: bool = False
    installed_version: Optional[str] = None
    is_enabled: bool = False
    
    def get_latest_version(self) -> Optional[PluginVersion]:
        """获取最新版本"""
        for v in self.versions:
            if v.is_latest:
                return v
        return self.versions[-1] if self.versions else None
    
    def get_stable_version(self) -> Optional[PluginVersion]:
        """获取最新稳定版"""
        stable = [v for v in self.versions if v.is_stable]
        return stable[-1] if stable else None
    
    def has_update(self) -> bool:
        """是否有更新"""
        if not self.is_installed or not self.installed_version:
            return False
        
        latest = self.get_latest_version()
        if not latest:
            return False
        
        return latest.get_version_number() > self._parse_version(self.installed_version)
    
    def _parse_version(self, version: str) -> tuple:
        """解析版本号"""
        return tuple(int(x) for x in version.split('.'))
    
    def check_permission(self, permission: str) -> bool:
        """检查是否有权限"""
        return permission in self.required_permissions
    
    def to_dict(self) -> Dict:
        """转字典"""
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "long_description": self.long_description,
            "version": self.version,
            "author_id": self.author_id,
            "author_name": self.author_name,
            "category": self.category.value,
            "tags": self.tags,
            "icon_url": self.icon_url,
            "downloads": self.downloads,
            "rating": self.rating,
            "rating_count": self.rating_count,
            "is_featured": self.is_featured,
            "is_premium": self.is_premium,
            "is_installed": self.is_installed,
            "installed_version": self.installed_version,
            "is_enabled": self.is_enabled,
            "has_update": self.has_update(),
            "latest_version": self.get_latest_version().version if self.get_latest_version() else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> Plugin:
        """从字典创建"""
        plugin = cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            slug=data.get('slug', ''),
            description=data.get('description', ''),
            long_description=data.get('long_description', ''),
            version=data.get('version', '1.0.0'),
            author_id=data.get('author_id', ''),
            author_name=data.get('author_name', ''),
        )
        
        # 分类
        if 'category' in data:
            try:
                plugin.category = PluginCategory(data['category'])
            except ValueError:
                plugin.category = PluginCategory.UTILITY
        
        # 标签
        plugin.tags = data.get('tags', [])
        
        # 版本
        if 'versions' in data:
            for v_data in data['versions']:
                version = PluginVersion(
                    version=v_data.get('version', '1.0.0'),
                    changelog=v_data.get('changelog', ''),
                    min_app_version=v_data.get('min_app_version', '1.0.0'),
                    download_url=v_data.get('download_url', ''),
                    file_size=v_data.get('file_size', 0),
                    is_stable=v_data.get('is_stable', True),
                    is_beta=v_data.get('is_beta', False),
                    is_latest=v_data.get('is_latest', True)
                )
                plugin.versions.append(version)
        
        # 权限
        plugin.required_permissions = data.get('required_permissions', [])
        plugin.optional_permissions = data.get('optional_permissions', [])
        
        # 设置
        plugin.settings_schema = data.get('settings_schema', {})
        plugin.default_settings = data.get('default_settings', {})
        
        # 统计
        plugin.downloads = data.get('downloads', 0)
        plugin.rating = data.get('rating', 0.0)
        plugin.rating_count = data.get('rating_count', 0)
        
        # 特性
        plugin.is_featured = data.get('is_featured', False)
        plugin.is_premium = data.get('is_premium', False)
        plugin.is_open_source = data.get('is_open_source', False)
        plugin.source_url = data.get('source_url', '')
        
        return plugin


@dataclass
class PluginReview:
    """插件评论"""
    id: str = ""
    plugin_id: str = ""
    user_id: str = ""
    user_name: str = ""
    rating: int = 0  # 1-5
    title: str = ""
    content: str = ""
    pros: List[str] = field(default_factory=list)
    cons: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    helpful_count: int = 0
    is_verified: bool = False  # 是否是已安装用户
    
    def to_dict(self) -> Dict:
        """转字典"""
        return {
            "id": self.id,
            "plugin_id": self.plugin_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "rating": self.rating,
            "title": self.title,
            "content": self.content,
            "pros": self.pros,
            "cons": self.cons,
            "created_at": self.created_at.isoformat(),
            "helpful_count": self.helpful_count,
            "is_verified": self.is_verified
        }
