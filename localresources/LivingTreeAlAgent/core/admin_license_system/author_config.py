"""
作者配置管理
Author Configuration Management

功能：
1. 三端发布时内置作者信息
2. 作者信息持久化存储
3. 作者身份验证
"""

import json
import os
import hashlib
import uuid
import secrets
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


class Platform(Enum):
    """发布平台"""
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"
    WEB = "web"


@dataclass
class AuthorInfo:
    """作者信息"""
    author_id: str           # 作者唯一ID
    name: str                # 作者名称
    email: str               # 作者邮箱
    company: str = ""        # 公司/组织
    website: str = ""         # 官方网站
    phone: str = ""          # 联系电话
    license_type: str = "enterprise"  # 授权类型
    max_admins: int = 100    # 最大管理员数量
    created_at: str = ""     # 创建时间
    version: str = "1.0"     # 配置版本

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AuthorInfo":
        return cls(**data)

    def get_author_hash(self) -> str:
        """获取作者哈希（用于验证）"""
        data = f"{self.author_id}:{self.email}:{self.name}"
        return hashlib.sha256(data.encode()).hexdigest()[:16].upper()

    def verify_signature(self, signature: str) -> bool:
        """验证作者签名"""
        return signature == self.get_author_hash()


@dataclass
class PlatformBinding:
    """平台绑定"""
    platform: Platform
    app_id: str              # 应用ID
    app_secret: str          # 应用密钥（哈希存储）
    enabled: bool = True
    bound_at: str = ""

    def __post_init__(self):
        if not self.bound_at:
            self.bound_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PlatformBinding":
        data['platform'] = Platform(data['platform'])
        return cls(**data)


class AuthorConfig:
    """
    作者配置

    用于三端发布时内置作者信息，支持：
    - Windows / macOS / Linux / Web
    """

    CONFIG_VERSION = "1.0"
    DEFAULT_CONFIG_PATH = Path.home() / ".hermes-desktop" / "author_config.json"

    def __init__(
        self,
        author_info: AuthorInfo,
        platform_bindings: List[PlatformBinding] = None,
        config_path: str = None
    ):
        self.author_info = author_info
        self.platform_bindings = platform_bindings or []
        self.config_path = Path(config_path) if config_path else self.DEFAULT_CONFIG_PATH
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

    def add_platform_binding(self, platform: Platform, app_id: str, app_secret: str) -> PlatformBinding:
        """添加平台绑定"""
        # 检查是否已存在
        for binding in self.platform_bindings:
            if binding.platform == platform:
                binding.app_id = app_id
                binding.app_secret = self._hash_secret(app_secret)
                binding.enabled = True
                return binding

        binding = PlatformBinding(
            platform=platform,
            app_id=app_id,
            app_secret=self._hash_secret(app_secret),
            enabled=True,
        )
        self.platform_bindings.append(binding)
        return binding

    def remove_platform_binding(self, platform: Platform) -> bool:
        """移除平台绑定"""
        for i, binding in enumerate(self.platform_bindings):
            if binding.platform == platform:
                self.platform_bindings.pop(i)
                return True
        return False

    def get_platform_binding(self, platform: Platform) -> Optional[PlatformBinding]:
        """获取平台绑定"""
        for binding in self.platform_bindings:
            if binding.platform == platform:
                return binding
        return None

    def verify_platform(self, platform: Platform, app_id: str, app_secret: str) -> bool:
        """验证平台凭证"""
        binding = self.get_platform_binding(platform)
        if not binding or not binding.enabled:
            return False
        return binding.app_id == app_id and binding.app_secret == self._hash_secret(app_secret)

    def _hash_secret(self, secret: str) -> str:
        """哈希密钥"""
        return hashlib.sha256(secret.encode()).hexdigest()

    def to_dict(self) -> dict:
        return {
            'author_info': self.author_info.to_dict(),
            'platform_bindings': [b.to_dict() for b in self.platform_bindings],
            'version': self.CONFIG_VERSION,
            'saved_at': datetime.now().isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AuthorConfig":
        author_info = AuthorInfo.from_dict(data['author_info'])
        platform_bindings = [PlatformBinding.from_dict(b) for b in data.get('platform_bindings', [])]
        return cls(author_info, platform_bindings)

    def save(self) -> bool:
        """保存配置"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    @classmethod
    def load(cls, config_path: str = None) -> Optional["AuthorConfig"]:
        """加载配置"""
        path = Path(config_path) if config_path else cls.DEFAULT_CONFIG_PATH
        if not path.exists():
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return cls.from_dict(data)
        except Exception:
            return None

    def export_for_build(self, platform: Platform) -> dict:
        """
        导出为构建配置（嵌入到发布包中）
        不包含敏感信息
        """
        binding = self.get_platform_binding(platform)
        return {
            'author_id': self.author_info.author_id,
            'author_name': self.author_info.name,
            'author_hash': self.author_info.get_author_hash(),
            'app_id': binding.app_id if binding else None,
            'platform': platform.value,
            'license_type': self.author_info.license_type,
            'max_admins': self.author_info.max_admins,
            'version': self.author_info.version,
        }


class AuthorConfigManager:
    """
    作者配置管理器

    功能：
    1. 创建作者配置
    2. 验证作者身份
    3. 导出构建配置
    4. 管理平台绑定
    """

    def __init__(self, config_path: str = None):
        self.config_path = config_path
        self._config: Optional[AuthorConfig] = None

    @property
    def config(self) -> Optional[AuthorConfig]:
        """获取配置（懒加载）"""
        if self._config is None:
            self._config = AuthorConfig.load(self.config_path)
        return self._config

    def has_author_config(self) -> bool:
        """检查是否已有作者配置"""
        return self.config is not None

    def create_author_config(
        self,
        name: str,
        email: str,
        company: str = "",
        website: str = "",
        phone: str = "",
        license_type: str = "enterprise",
        max_admins: int = 100
    ) -> AuthorConfig:
        """创建作者配置"""
        author_id = f"author_{uuid.uuid4().hex[:12]}"

        author_info = AuthorInfo(
            author_id=author_id,
            name=name,
            email=email,
            company=company,
            website=website,
            phone=phone,
            license_type=license_type,
            max_admins=max_admins,
        )

        self._config = AuthorConfig(author_info=author_info)
        self._config.save()

        return self._config

    def verify_author(self, author_id: str, email: str) -> bool:
        """验证作者身份"""
        if not self.config:
            return False
        return (self.config.author_info.author_id == author_id and
                self.config.author_info.email == email)

    def is_author(self, user_id: str, user_email: str) -> bool:
        """检查是否为作者"""
        if not self.config:
            return False
        info = self.config.author_info
        return (info.author_id == user_id or info.email == user_email)

    def get_author_info(self) -> Optional[AuthorInfo]:
        """获取作者信息"""
        return self.config.author_info if self.config else None

    def update_author_info(self, **kwargs) -> bool:
        """更新作者信息"""
        if not self.config:
            return False

        for key, value in kwargs.items():
            if hasattr(self.config.author_info, key):
                setattr(self.config.author_info, key, value)

        return self.config.save()

    def add_platform_binding(self, platform: Platform, app_id: str, app_secret: str) -> bool:
        """添加平台绑定"""
        if not self.config:
            return False
        self.config.add_platform_binding(platform, app_id, app_secret)
        return self.config.save()

    def remove_platform_binding(self, platform: Platform) -> bool:
        """移除平台绑定"""
        if not self.config:
            return False
        result = self.config.remove_platform_binding(platform)
        if result:
            return self.config.save()
        return False

    def get_build_config(self, platform: Platform) -> Optional[dict]:
        """获取构建配置"""
        if not self.config:
            return None
        return self.config.export_for_build(platform)

    def generate_author_credentials(self) -> tuple:
        """
        生成作者凭证

        Returns:
            (app_id, app_secret) - app_secret 仅显示一次
        """
        app_id = f"APP_{uuid.uuid4().hex[:8].upper()}"
        app_secret = secrets.token_hex(24)
        return app_id, app_secret


# 单例
_author_config_manager: Optional[AuthorConfigManager] = None


def get_author_config_manager() -> AuthorConfigManager:
    """获取作者配置管理器单例"""
    global _author_config_manager
    if _author_config_manager is None:
        _author_config_manager = AuthorConfigManager()
    return _author_config_manager