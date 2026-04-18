"""
Cloud Driver Base Class - 云盘驱动抽象基类

定义统一的云盘驱动接口，所有具体驱动（阿里云盘、夸克、115等）都继承此基类。
参考 fsspec 抽象模式，提供一致的 open/read/write/stat 接口。
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, BinaryIO, Optional


# ============= 数据模型 =============

class CloudProvider(Enum):
    """云盘提供商枚举"""
    ALIYUN = "aliyun"
    QUARK = "quark"
    CC115 = "115"
    ONEDRIVE = "onedrive"
    UNKNOWN = "unknown"


class EntryType(Enum):
    """文件条目类型"""
    FILE = "file"
    FOLDER = "folder"
    SYMLINK = "symlink"


@dataclass
class CloudQuota:
    """云盘配额信息"""
    total: int = 0              # 总容量 (bytes)
    used: int = 0              # 已用容量 (bytes)
    free: int = 0              # 剩余容量 (bytes)
    quota_type: str = ""       # 配额类型 (free/premium/enterprise)

    @property
    def used_percent(self) -> float:
        """使用百分比"""
        if self.total == 0:
            return 0.0
        return (self.used / self.total) * 100


@dataclass
class CloudEntry:
    """云盘文件条目（虚拟路径映射）"""
    path: str                  # 虚拟路径: /clouds/aliyun/folder/file.txt
    name: str                  # 文件名: file.txt
    entry_type: EntryType      # 条目类型
    size: int = 0              # 文件大小 (bytes)
    cloud: str = ""           # 云盘标识: aliyun
    real_id: str = ""         # 网盘真实文件ID
    parent_id: str = ""        # 父目录ID
    created_time: Optional[datetime] = None
    modified_time: Optional[datetime] = None
    download_url: Optional[str] = None  # 预签名下载URL
    upload_url: Optional[str] = None     # 预签名上传URL
    etag: str = ""             # 文件etag (用于秒传/去重)
    is_shared: bool = False    # 是否为分享文件
    share_token: str = ""      # 分享令牌

    @property
    def virtual_path(self) -> str:
        """获取虚拟路径"""
        return self.path

    @property
    def is_file(self) -> bool:
        return self.entry_type == EntryType.FILE

    @property
    def is_folder(self) -> bool:
        return self.entry_type == EntryType.FOLDER

    @property
    def extension(self) -> str:
        """获取文件扩展名"""
        if self.is_folder:
            return ""
        import os
        return os.path.splitext(self.name)[1].lstrip(".")


@dataclass
class DriverConfig:
    """驱动配置"""
    name: str                  # 驱动名称
    provider: CloudProvider    # 提供商类型
    enabled: bool = True       # 是否启用
    credentials: dict = field(default_factory=dict)  # 凭据信息
    cache_dir: str = ""        # 本地缓存目录
    max_cache_size: int = 1024 * 1024 * 1024  # 最大缓存 1GB
    request_timeout: int = 30  # 请求超时 (秒)
    max_retries: int = 3       # 最大重试次数


# ============= 抽象驱动基类 =============

class BaseCloudDriver(ABC):
    """
    云盘驱动抽象基类

    所有云盘驱动必须实现以下方法：
    - 认证: login, logout, refresh_token
    - 文件操作: list, stat, download, upload, delete, move, copy
    - 元数据: get_quota, get_user_info
    - 分享: share, get_share_link
    """

    def __init__(self, config: DriverConfig):
        self.config = config
        self._authenticated = False
        self._user_info: dict = {}

    # ── 认证 ─────────────────────────────────────────────────────

    @abstractmethod
    async def login(self, **credentials) -> bool:
        """
        登录认证

        Args:
            credentials: 凭据信息，不同驱动有不同的凭据格式
                - aliyun: {"refresh_token": "xxx"}
                - quark: {"phone": "xxx", "password": "xxx"}
                - onedrive: {"access_token": "xxx", "refresh_token": "xxx"}

        Returns:
            bool: 登录是否成功
        """
        pass

    @abstractmethod
    async def logout(self) -> bool:
        """退出登录"""
        pass

    @abstractmethod
    async def refresh_token(self) -> bool:
        """刷新访问令牌"""
        pass

    @property
    @abstractmethod
    def is_authenticated(self) -> bool:
        """是否已认证"""
        pass

    # ── 文件操作 ─────────────────────────────────────────────────────

    @abstractmethod
    async def list(
        self,
        path: str = "/",
        page_size: int = 100,
        page_token: Optional[str] = None
    ) -> tuple[list[CloudEntry], Optional[str]]:
        """
        列出目录内容

        Args:
            path: 虚拟路径
            page_size: 每页数量
            page_token: 分页令牌

        Returns:
            (条目列表, 下一页令牌)
        """
        pass

    @abstractmethod
    async def stat(self, path: str) -> Optional[CloudEntry]:
        """
        获取文件/目录信息

        Args:
            path: 虚拟路径

        Returns:
            CloudEntry 或 None (不存在)
        """
        pass

    @abstractmethod
    async def download(
        self,
        path: str,
        dest: BinaryIO,
        progress_callback: Optional[callable] = None,
        offset: int = 0,
        length: Optional[int] = None
    ) -> int:
        """
        下载文件

        Args:
            path: 虚拟路径
            dest: 目标文件对象
            progress_callback: 进度回调 (bytes_downloaded, total_bytes)
            offset: 下载起始位置 (断点续传)
            length: 下载长度 (None = 全部)

        Returns:
            实际下载字节数
        """
        pass

    @abstractmethod
    async def upload(
        self,
        source: BinaryIO,
        dest_path: str,
        size: int,
        progress_callback: Optional[callable] = None,
        if_not_exists: bool = True
    ) -> Optional[CloudEntry]:
        """
        上传文件

        Args:
            source: 源文件对象
            dest_path: 目标虚拟路径
            size: 文件大小
            progress_callback: 进度回调
            if_not_exists: 是否仅在不存在时上传

        Returns:
            上传后的 CloudEntry 或 None
        """
        pass

    @abstractmethod
    async def delete(self, path: str, permanently: bool = False) -> bool:
        """
        删除文件/目录

        Args:
            path: 虚拟路径
            permanently: 是否永久删除 (vs 放入回收站)

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    async def move(self, src_path: str, dest_path: str) -> bool:
        """移动/重命名文件"""
        pass

    @abstractmethod
    async def copy(self, src_path: str, dest_path: str) -> bool:
        """复制文件"""
        pass

    @abstractmethod
    async def create_folder(self, path: str) -> Optional[CloudEntry]:
        """创建目录"""
        pass

    # ── 元数据 ─────────────────────────────────────────────────────

    @abstractmethod
    async def get_quota(self) -> CloudQuota:
        """获取云盘配额"""
        pass

    @abstractmethod
    async def get_user_info(self) -> dict:
        """获取用户信息"""
        pass

    # ── 分享 ─────────────────────────────────────────────────────

    @abstractmethod
    async def share(
        self,
        path: str,
        password: Optional[str] = None,
        expire_days: Optional[int] = None
    ) -> tuple[str, Optional[str]]:
        """
        创建分享链接

        Args:
            path: 要分享的路径
            password: 分享密码 (可选)
            expire_days: 过期天数 (可选)

        Returns:
            (分享链接, 分享密码)
        """
        pass

    @abstractmethod
    async def get_share_info(self, share_token: str) -> dict:
        """获取分享信息"""
        pass

    @abstractmethod
    async def download_from_share(
        self,
        share_token: str,
        password: Optional[str],
        path: str,
        dest: BinaryIO
    ) -> int:
        """从分享链接下载"""
        pass

    # ── 工具方法 ─────────────────────────────────────────────────────

    def path_to_virtual(self, real_id: str, name: str) -> str:
        """
        将云盘真实路径转换为虚拟路径

        Args:
            real_id: 云盘真实文件ID
            name: 文件名

        Returns:
            虚拟路径: /clouds/{provider}/{path}
        """
        return f"/clouds/{self.config.provider.value}/{name}"

    def virtual_to_cloud_path(self, virtual_path: str) -> str:
        """
        将虚拟路径转换为云盘内部路径

        Args:
            virtual_path: 虚拟路径

        Returns:
            云盘内部路径
        """
        # 默认实现：去掉 /clouds/{provider} 前缀
        parts = virtual_path.split("/", 3)
        if len(parts) >= 4:
            return "/" + parts[3]
        return "/"

    def _parse_cloud_path(self, virtual_path: str) -> tuple[str, str]:
        """
        解析虚拟路径

        Returns:
            (云盘标识, 云盘内部路径)
        """
        parts = virtual_path.split("/", 3)
        if len(parts) >= 4:
            return parts[2], "/" + parts[3]
        elif len(parts) >= 3:
            return parts[2], "/"
        return "", "/"


# ============= 驱动注册表 =============

class DriverRegistry:
    """
    云盘驱动注册表

    管理所有已注册的云盘驱动实例
    """

    def __init__(self):
        self._drivers: dict[str, BaseCloudDriver] = {}
        self._default: Optional[str] = None

    def register(
        self,
        name: str,
        driver: BaseCloudDriver,
        set_default: bool = False
    ) -> None:
        """
        注册驱动

        Args:
            name: 驱动标识名
            driver: 驱动实例
            set_default: 是否设为默认驱动
        """
        self._drivers[name] = driver
        if set_default or not self._default:
            self._default = name

    def unregister(self, name: str) -> bool:
        """取消注册"""
        if name in self._drivers:
            del self._drivers[name]
            if self._default == name:
                self._default = next(iter(self._drivers), None)
            return True
        return False

    def get(self, name: str) -> Optional[BaseCloudDriver]:
        """获取驱动"""
        return self._drivers.get(name)

    def get_default(self) -> Optional[BaseCloudDriver]:
        """获取默认驱动"""
        if self._default:
            return self._drivers.get(self._default)
        return None

    @property
    def names(self) -> list[str]:
        """获取所有已注册的驱动名称"""
        return list(self._drivers.keys())

    @property
    def default_name(self) -> Optional[str]:
        """获取默认驱动名称"""
        return self._default

    def list_drivers(self) -> dict[str, dict]:
        """列出所有驱动状态"""
        return {
            name: {
                "authenticated": driver.is_authenticated,
                "provider": driver.config.provider.value,
                "enabled": driver.config.enabled,
            }
            for name, driver in self._drivers.items()
        }
