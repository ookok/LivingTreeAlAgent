"""
GitHub Store 数据模型
桌面代码仓库 - 发现、安装、管理 GitHub Release 中的桌面应用
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import hashlib


class PlatformType(Enum):
    """支持的桌面平台"""
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    ANDROID = "android"
    ALL = "all"


class AssetType(Enum):
    """资源文件类型"""
    EXE = "exe"           # Windows 可执行
    MSI = "msi"           # Windows Installer
    DMG = "dmg"           # macOS
    APP = "app"           # macOS App Bundle
    APPIMAGE = "appimage" # Linux AppImage
    DEB = "deb"           # Debian/Ubuntu
    RPM = "rpm"           # Fedora/RHEL
    APK = "apk"           # Android
    ARCHIVE = "archive"   # 通用压缩包 (zip/tar.gz)


class InstallStatus(Enum):
    """安装状态"""
    NOT_INSTALLED = "not_installed"
    INSTALLED = "installed"
    UPDATE_AVAILABLE = "update_available"
    INSTALLING = "installing"
    UPDATING = "updating"
    UNINSTALLING = "uninstalling"


class SourceType(Enum):
    """应用来源"""
    TRENDING = "trending"       # 趋势推荐
    STARRED = "starred"        # GitHub 星标
    FAVORITE = "favorite"      # 本地收藏
    RECENT = "recent"          # 最近浏览
    SEARCH = "search"          # 搜索结果
    CATEGORY = "category"      # 分类浏览


@dataclass
class GitHubAsset:
    """GitHub Release 资源文件"""
    name: str                          # 文件名
    download_url: str                  # 下载地址
    size: int                          # 文件大小 (bytes)
    asset_id: int                      # GitHub Asset ID
    content_type: str                   # MIME 类型
    asset_type: AssetType = AssetType.ARCHIVE  # 分类后的类型
    platform: Optional[PlatformType] = None      # 对应平台
    architecture: Optional[str] = None            # 架构 (x64, arm64)
    is_compatible: bool = True                    # 是否兼容当前系统
    checksum: Optional[str] = None                 # 校验和 (可选)

    @classmethod
    def detect_asset_type(cls, name: str) -> tuple[AssetType, Optional[PlatformType], Optional[str]]:
        """从文件名推断资源类型、平台和架构"""
        name_lower = name.lower()

        # Windows
        if name_lower.endswith(".exe"):
            arch = cls._detect_arch(name_lower)
            return AssetType.EXE, PlatformType.WINDOWS, arch
        if name_lower.endswith(".msi"):
            arch = cls._detect_arch(name_lower)
            return AssetType.MSI, PlatformType.WINDOWS, arch

        # macOS
        if name_lower.endswith(".dmg"):
            arch = cls._detect_arch(name_lower)
            return AssetType.DMG, PlatformType.MACOS, arch
        if name_lower.endswith(".app.zip") or name_lower.endswith("-mac.zip"):
            arch = cls._detect_arch(name_lower)
            return AssetType.APP, PlatformType.MACOS, arch

        # Linux
        if name_lower.endswith(".appimage"):
            arch = cls._detect_arch(name_lower)
            return AssetType.APPIMAGE, PlatformType.LINUX, arch
        if name_lower.endswith(".deb"):
            arch = cls._detect_arch(name_lower)
            return AssetType.DEB, PlatformType.LINUX, arch
        if name_lower.endswith(".rpm"):
            arch = cls._detect_arch(name_lower)
            return AssetType.RPM, PlatformType.LINUX, arch

        # Android
        if name_lower.endswith(".apk"):
            arch = cls._detect_arch(name_lower)
            return AssetType.APK, PlatformType.ANDROID, arch

        # 通用归档
        if any(name_lower.endswith(ext) for ext in [".zip", ".tar.gz", ".tgz", ".tar.bz2"]):
            return AssetType.ARCHIVE, PlatformType.ALL, None

        return AssetType.ARCHIVE, None, None

    @staticmethod
    def _detect_arch(name: str) -> Optional[str]:
        """检测架构"""
        if "arm64" in name or "aarch64" in name:
            return "arm64"
        if "amd64" in name or "x86_64" in name or "-x64" in name:
            return "x64"
        if "386" in name or "i386" in name or "i686" in name:
            return "x86"
        if "armv7" in name or "armeabi-v7" in name:
            return "armv7"
        return None


@dataclass
class GitHubRelease:
    """GitHub Release 信息"""
    tag_name: str                       # 版本标签
    name: str                           # 发布名称
    body: str                           # 发布说明 (Markdown)
    published_at: datetime               # 发布时间
    html_url: str                       # Release 页面 URL
    assets: List[GitHubAsset] = field(default_factory=list)  # 资源文件
    is_prerelease: bool = False          # 是否预发布
    is_draft: bool = False               # 是否为草稿
    target_commitish: str = ""           # 目标分支/提交
    author: str = ""                    # 发布者
    version: str = ""                   # 解析后的版本号

    @classmethod
    def from_github_api(cls, data: dict) -> "GitHubRelease":
        """从 GitHub API 响应创建"""
        assets = []
        for a in data.get("assets", []):
            asset_type, platform, arch = GitHubAsset.detect_asset_type(a["name"])
            assets.append(GitHubAsset(
                name=a["name"],
                download_url=a["browser_download_url"],
                size=a["size"],
                asset_id=a["id"],
                content_type=a["content_type"],
                asset_type=asset_type,
                platform=platform,
                architecture=arch,
            ))

        tag = data.get("tag_name", "")
        version = cls._parse_version(tag)

        return cls(
            tag_name=tag,
            name=data.get("name") or tag,
            body=data.get("body") or "",
            published_at=datetime.fromisoformat(data["published_at"].replace("Z", "+00:00")),
            html_url=data["html_url"],
            assets=assets,
            is_prerelease=data.get("prerelease", False),
            is_draft=data.get("draft", False),
            target_commitish=data.get("target_commitish", ""),
            author=data.get("author", {}).get("login", ""),
            version=version,
        )

    @staticmethod
    def _parse_version(tag: str) -> str:
        """从 tag 解析版本号"""
        import re
        # 去除 v 前缀
        tag = tag.lstrip("v")
        # 提取版本号模式 X.Y.Z
        match = re.search(r"(\d+\.\d+\.\d+[\w.-]*)", tag)
        return match.group(1) if match else tag


@dataclass
class RepoInfo:
    """GitHub 仓库信息"""
    owner: str                          # 仓库所有者
    name: str                            # 仓库名
    full_name: str                      # owner/repo
    description: str                     # 描述
    html_url: str                       # 仓库 URL
    stars: int                          # 星标数
    forks: int                          # Fork 数
    language: str                       # 主要语言
    topics: List[str] = field(default_factory=list)  # 主题标签
    latest_release: Optional[GitHubRelease] = None   # 最新 Release
    releases: List[GitHubRelease] = field(default_factory=list)  # 所有 Release
    readme: str = ""                    # README 内容
    avatar_url: str = ""                 # 作者头像
    license: str = ""                   # 开源协议
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    pushed_at: Optional[datetime] = None
    source_type: SourceType = SourceType.SEARCH  # 来源类型
    is_installable: bool = False       # 是否有可安装资源

    @property
    def repo_id(self) -> str:
        """唯一 ID"""
        return hashlib.md5(self.full_name.encode()).hexdigest()[:12]

    @property
    def platform_tags(self) -> List[str]:
        """平台标签"""
        tags = []
        for topic in self.topics:
            t = topic.lower()
            if t in ("windows", "win", "win32", "win64"):
                tags.append("windows")
            elif t in ("linux", "ubuntu", "debian", "fedora"):
                tags.append("linux")
            elif t in ("macos", "mac", "darwin", "apple"):
                tags.append("macos")
            elif t in ("android", "apk"):
                tags.append("android")
        return tags if tags else ["all"]

    def check_installable(self) -> bool:
        """检查是否有可安装的 Release 资源"""
        if not self.latest_release:
            return False
        return any(
            a.asset_type != AssetType.ARCHIVE or a.platform is not None
            for a in self.latest_release.assets
        )


@dataclass
class InstalledApp:
    """已安装的应用"""
    repo_full_name: str                 # 仓库名 (owner/repo)
    installed_version: str              # 已安装版本
    installed_at: datetime               # 安装时间
    install_path: str                    # 安装路径
    asset_name: str                      # 安装时使用的资源文件名
    asset_size: int                      # 资源文件大小
    platform: PlatformType               # 平台
    architecture: Optional[str] = None   # 架构
    current_version: str = ""            # 最新版本 (用于检测更新)
    update_available: bool = False       # 是否有更新
    download_url: str = ""               # 当前版本的下载 URL
    notes: str = ""                     # 备注


@dataclass
class DownloadTask:
    """下载任务"""
    id: str                              # 任务 ID
    repo_full_name: str                  # 仓库名
    asset: GitHubAsset                   # 目标资源
    total_size: int                      # 总大小
    downloaded_size: int = 0             # 已下载大小
    status: str = "pending"              # pending/downloading/completed/failed
    progress: float = 0.0                # 进度 0-100
    download_path: str = ""              # 下载路径
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: str = ""              # 错误信息
    speed_bps: int = 0                  # 下载速度 (bytes/s)


@dataclass
class CategoryInfo:
    """分类信息"""
    id: str
    name: str                            # 显示名称
    icon: str                            # emoji 图标
    topics: List[str]                   # 对应的 GitHub topics
    description: str = ""               # 分类描述
    count: int = 0                      # 该分类下的应用数


# 预定义分类
DESKTOP_CATEGORIES: List[CategoryInfo] = [
    CategoryInfo("developer-tools", "开发者工具", "🛠️",
                 ["developer-tools", "cli", "terminal", "IDE"],
                 "命令行工具、IDE、调试器等"),
    CategoryInfo("utilities", "实用工具", "🔧",
                 ["utility", "tools", "system", "manager"],
                 "系统管理、文件处理、效率工具"),
    CategoryInfo("ai-ml", "AI 与机器学习", "🤖",
                 ["machine-learning", "deep-learning", "AI", "neural-network"],
                 "AI 模型、训练工具、推理框架"),
    CategoryInfo("media", "多媒体", "🎨",
                 ["media", "video", "audio", "image", "graphics"],
                 "视频、音频、图片处理工具"),
    CategoryInfo("network", "网络工具", "🌐",
                 ["network", "proxy", "vpn", "browser"],
                 "浏览器、代理、下载工具"),
    CategoryInfo("games", "游戏", "🎮",
                 ["game", "gaming", "emulator"],
                 "游戏客户端模拟器等"),
    CategoryInfo("productivity", "效率", "📊",
                 ["productivity", "office", "notes", "todo"],
                 "办公、笔记、项目管理"),
    CategoryInfo("security", "安全", "🔒",
                 ["security", "encryption", "privacy", "cryptography"],
                 "加密、隐私、安全工具"),
]

# 平台映射
PLATFORM_TOPICS = {
    PlatformType.WINDOWS: ["windows", "win", "win32", "win64", "desktop"],
    PlatformType.LINUX: ["linux", "ubuntu", "debian", "fedora", "arch", "appimage"],
    PlatformType.MACOS: ["macos", "mac", "darwin", "apple", "desktop"],
    PlatformType.ANDROID: ["android", "apk", "mobile"],
}
