"""
GitHub Store — 桌面代码仓库

发现、下载、安装、管理 GitHub Release 中的桌面应用。

整合功能：
1. GitHub API 集成 — 搜索仓库、获取 Release、速率限制
2. Release 检测 — 自动识别可安装资源、平台/架构匹配
3. 下载管理 — 断点续传、进度追踪、自动安装
4. 应用管理 — 本地安装记录、收藏、星标、更新检测

从 client/src/business/github_store/ 迁移，修复 2 个 bug：
  - AssetType 拼写错误 ASSET→APK
  - GitHubAsset 与 ReleaseDetector 资产检测逻辑重复（已统一到 _detect_asset_info）
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import platform as _platform
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# 1. 枚举
# ═══════════════════════════════════════════════════════════════════════

class PlatformType(Enum):
    """支持的桌面平台"""
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    ANDROID = "android"
    ALL = "all"


class AssetType(Enum):
    """资源文件类型"""
    EXE = "exe"
    MSI = "msi"
    DMG = "dmg"
    APP = "app"
    APPIMAGE = "appimage"
    DEB = "deb"
    RPM = "rpm"
    APK = "apk"
    ARCHIVE = "archive"


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
    TRENDING = "trending"
    STARRED = "starred"
    FAVORITE = "favorite"
    RECENT = "recent"
    SEARCH = "search"
    CATEGORY = "category"


# ═══════════════════════════════════════════════════════════════════════
# 2. 数据模型
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class GitHubAsset:
    """GitHub Release 资源文件"""
    name: str
    download_url: str
    size: int
    asset_id: int
    content_type: str = ""
    asset_type: AssetType = AssetType.ARCHIVE
    platform: Optional[PlatformType] = None
    architecture: Optional[str] = None
    is_compatible: bool = True
    checksum: Optional[str] = None


@dataclass
class GitHubRelease:
    """GitHub Release 信息"""
    tag_name: str
    name: str = ""
    body: str = ""
    published_at: Optional[datetime] = None
    html_url: str = ""
    assets: List[GitHubAsset] = field(default_factory=list)
    is_prerelease: bool = False
    is_draft: bool = False
    target_commitish: str = ""
    author: str = ""
    version: str = ""

    @classmethod
    def from_github_api(cls, data: dict) -> "GitHubRelease":
        assets = []
        for a in data.get("assets", []):
            info = _detect_asset_info(a["name"])
            assets.append(GitHubAsset(
                name=a["name"],
                download_url=a["browser_download_url"],
                size=a["size"],
                asset_id=a["id"],
                content_type=a.get("content_type", ""),
                asset_type=info[0],
                platform=info[1],
                architecture=info[2],
            ))
        tag = data.get("tag_name", "")
        version = _parse_version(tag)
        published = None
        if data.get("published_at"):
            published = datetime.fromisoformat(data["published_at"].replace("Z", "+00:00"))
        return cls(
            tag_name=tag,
            name=data.get("name") or tag,
            body=data.get("body") or "",
            published_at=published,
            html_url=data.get("html_url", ""),
            assets=assets,
            is_prerelease=data.get("prerelease", False),
            is_draft=data.get("draft", False),
            target_commitish=data.get("target_commitish", ""),
            author=data.get("author", {}).get("login", ""),
            version=version,
        )


@dataclass
class RepoInfo:
    """GitHub 仓库信息"""
    owner: str
    name: str
    full_name: str
    description: str = ""
    html_url: str = ""
    stars: int = 0
    forks: int = 0
    language: str = ""
    topics: List[str] = field(default_factory=list)
    latest_release: Optional[GitHubRelease] = None
    releases: List[GitHubRelease] = field(default_factory=list)
    readme: str = ""
    avatar_url: str = ""
    license: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    pushed_at: Optional[datetime] = None
    source_type: SourceType = SourceType.SEARCH
    is_installable: bool = False

    @property
    def repo_id(self) -> str:
        return hashlib.md5(self.full_name.encode()).hexdigest()[:12]

    @property
    def platform_tags(self) -> List[str]:
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


@dataclass
class InstalledApp:
    """已安装的应用"""
    repo_full_name: str
    installed_version: str
    installed_at: datetime
    install_path: str
    asset_name: str = ""
    asset_size: int = 0
    platform: PlatformType = PlatformType.ALL
    architecture: Optional[str] = None
    current_version: str = ""
    update_available: bool = False
    download_url: str = ""
    notes: str = ""


@dataclass
class DownloadTask:
    """下载任务"""
    id: str
    repo_full_name: str
    asset: GitHubAsset
    total_size: int
    downloaded_size: int = 0
    status: str = "pending"
    progress: float = 0.0
    download_path: str = ""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: str = ""
    speed_bps: int = 0


@dataclass
class CategoryInfo:
    """分类信息"""
    id: str
    name: str
    icon: str
    topics: List[str] = field(default_factory=list)
    description: str = ""
    count: int = 0


# ═══════════════════════════════════════════════════════════════════════
# 共享工具函数
# ═══════════════════════════════════════════════════════════════════════

# 文件扩展名 → 类型映射
_EXT_TO_ASSET: Dict[str, Tuple[AssetType, Optional[PlatformType]]] = {
    '.exe':      (AssetType.EXE,      PlatformType.WINDOWS),
    '.msi':      (AssetType.MSI,      PlatformType.WINDOWS),
    '.dmg':      (AssetType.DMG,      PlatformType.MACOS),
    '.appimage': (AssetType.APPIMAGE, PlatformType.LINUX),
    '.deb':      (AssetType.DEB,      PlatformType.LINUX),
    '.rpm':      (AssetType.RPM,      PlatformType.LINUX),
    '.apk':      (AssetType.APK,      PlatformType.ANDROID),
}

# 平台文件名模式（用于无明确扩展名时推断）
_PLATFORM_PATTERNS: Dict[PlatformType, List[str]] = {
    PlatformType.WINDOWS: [
        r"windows", r"win64", r"win32", r"windows-x64",
        r"windows-amd64", r"windows-x86", r"\.exe", r"\.msi",
        r"-windows", r"_windows",
    ],
    PlatformType.LINUX: [
        r"linux", r"ubuntu", r"debian", r"fedora", r"arch",
        r"\.appimage", r"\.deb", r"\.rpm", r"-linux", r"_linux",
        r"linux-x64", r"linux-amd64", r"linux-arm64",
    ],
    PlatformType.MACOS: [
        r"macos", r"darwin", r"mac-os", r"\.dmg", r"\.app",
        r"-macos", r"_macos", r"-mac", r"_mac",
        r"apple-silicon", r"arm64-macos",
    ],
    PlatformType.ANDROID: [
        r"android", r"\.apk", r"-android", r"_android",
        r"arm64-v8a", r"armeabi-v7a",
    ],
}

_ARCH_PATTERNS: List[Tuple[str, str]] = [
    (r"amd64|x86_64|x64", "x64"),
    (r"386|i386|i686|x86", "x86"),
    (r"arm64|aarch64|armv8", "arm64"),
    (r"armv7|armeabi-v7", "armv7"),
]


def _detect_asset_info(name: str) -> Tuple[AssetType, Optional[PlatformType], Optional[str]]:
    """统一的资产信息检测 — 合并了 GitHubAsset.detect_asset_type 和 ReleaseDetector._analyze_asset"""
    name_lower = name.lower()

    # 1. 扩展名精确匹配
    for ext, suffixes in {
        '.exe': (AssetType.EXE, PlatformType.WINDOWS),
        '.msi': (AssetType.MSI, PlatformType.WINDOWS),
        '.dmg': (AssetType.DMG, PlatformType.MACOS),
        '.appimage': (AssetType.APPIMAGE, PlatformType.LINUX),
        '.deb': (AssetType.DEB, PlatformType.LINUX),
        '.rpm': (AssetType.RPM, PlatformType.LINUX),
        '.apk': (AssetType.APK, PlatformType.ANDROID),
    }.items():
        if name_lower.endswith(ext):
            plat = _detect_platform_from_name(name_lower) or suffixes[1]
            arch = _detect_arch_from_name(name_lower)
            return _EXT_TO_ASSET[ext][0], plat, arch

    # 2. macOS app bundle
    if name_lower.endswith('.app.zip') or name_lower.endswith('-mac.zip'):
        arch = _detect_arch_from_name(name_lower)
        return AssetType.APP, PlatformType.MACOS, arch

    # 3. 通用归档
    if any(name_lower.endswith(ext) for ext in ('.zip', '.tar.gz', '.tgz', '.tar.bz2', '.tar.xz')):
        plat = _detect_platform_from_name(name_lower)
        arch = _detect_arch_from_name(name_lower)
        return AssetType.ARCHIVE, plat, arch

    # 4. 纯平台关键词匹配
    plat = _detect_platform_from_name(name_lower)
    if plat:
        arch = _detect_arch_from_name(name_lower)
        return AssetType.ARCHIVE, plat, arch

    return AssetType.ARCHIVE, None, None


def _detect_platform_from_name(name: str) -> Optional[PlatformType]:
    for platform_type, patterns in _PLATFORM_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, name):
                return platform_type
    return None


def _detect_arch_from_name(name: str) -> Optional[str]:
    for pattern, arch in _ARCH_PATTERNS:
        if re.search(pattern, name):
            return arch
    return None


def _parse_version(tag: str) -> str:
    tag = tag.lstrip("v")
    match = re.search(r"(\d+\.\d+\.\d+[\w.-]*)", tag)
    return match.group(1) if match else tag


def _detect_current_platform() -> PlatformType:
    system = _platform.system().lower()
    if system == "windows":
        return PlatformType.WINDOWS
    elif system == "linux":
        return PlatformType.LINUX
    elif system == "darwin":
        return PlatformType.MACOS
    return PlatformType.LINUX


def _detect_current_arch() -> str:
    machine = _platform.machine().lower()
    if machine in ("amd64", "x86_64"):
        return "x64"
    elif machine in ("arm64", "aarch64"):
        return "arm64"
    elif machine in ("i386", "i686", "x86"):
        return "x86"
    elif "arm" in machine:
        return "armv7"
    return "x64"


# ═══════════════════════════════════════════════════════════════════════
# 3. GitHubAPI — GitHub API 客户端
# ═══════════════════════════════════════════════════════════════════════

class GitHubAPIError(Exception):
    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code


class GitHubAPI:
    """GitHub API 客户端 — 速率限制 + 缓存"""

    BASE_URL = "https://api.github.com"

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("GITHUB_TOKEN", "")
        self._headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "LivingTree-GitHub-Store/1.0",
        }
        if self.token:
            self._headers["Authorization"] = f"Bearer {self.token}"
        self._rate_limit_remaining: int = 60
        self._rate_limit_reset: float = 0.0
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._cache_ttl: float = 300.0

    def _is_cache_valid(self, key: str) -> bool:
        if key not in self._cache:
            return False
        _, expire = self._cache[key]
        return time.time() < expire

    def _get_cached(self, key: str) -> Optional[Any]:
        return self._cache[key][0] if self._is_cache_valid(key) else None

    def _set_cache(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        self._cache[key] = (value, time.time() + (ttl or self._cache_ttl))

    def _update_rate_limit(self, headers: Dict) -> None:
        self._rate_limit_remaining = int(headers.get("X-RateLimit-Remaining", 60))
        self._rate_limit_reset = float(headers.get("X-RateLimit-Reset", 0))

    async def _get(self, path: str, params: Optional[Dict] = None,
                   cache: bool = True) -> Dict:
        import json as _json
        cache_key = f"{path}:{_json.dumps(params or {}, sort_keys=True)}"

        if cache:
            cached = self._get_cached(cache_key)
            if cached is not None:
                return cached

        if self._rate_limit_remaining <= 0 and time.time() < self._rate_limit_reset:
            wait_time = self._rate_limit_reset - time.time()
            logger.warning(f"速率限制达到，等待 {wait_time:.0f}s")
            await asyncio.sleep(min(wait_time, 60))

        url = f"{self.BASE_URL}{path}"
        if params:
            query = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{query}"

        req = urllib.request.Request(url, headers=self._headers)

        try:
            def _fetch():
                return urllib.request.urlopen(req, timeout=30)
            resp = await asyncio.to_thread(_fetch)
            headers = dict(resp.headers)
            self._update_rate_limit(headers)
            data = _json.loads(resp.read().decode("utf-8"))
            if cache:
                self._set_cache(cache_key, data)
            return data
        except urllib.error.HTTPError as e:
            if e.code == 403:
                self._rate_limit_remaining = 0
                raise GitHubAPIError("API 速率限制达到", 403)
            raise GitHubAPIError(f"HTTP 错误: {e.code}", e.code)
        except Exception as e:
            raise GitHubAPIError(f"请求失败: {e}")

    def clear_cache(self) -> None:
        self._cache.clear()

    # ── 仓库 API ──

    async def get_repo(self, owner: str, repo: str) -> RepoInfo:
        data = await self._get(f"/repos/{owner}/{repo}")
        return self._parse_repo_info(data)

    async def get_releases(self, owner: str, repo: str,
                           per_page: int = 30) -> List[GitHubRelease]:
        releases: List[GitHubRelease] = []
        page = 1
        while True:
            data = await self._get(
                f"/repos/{owner}/{repo}/releases",
                params={"per_page": per_page, "page": page},
            )
            if not data:
                break
            for r in data:
                if not r.get("draft", False):
                    releases.append(GitHubRelease.from_github_api(r))
            if len(data) < per_page:
                break
            page += 1
        return releases

    async def get_latest_release(self, owner: str, repo: str) -> Optional[GitHubRelease]:
        try:
            data = await self._get(f"/repos/{owner}/{repo}/releases/latest")
            return GitHubRelease.from_github_api(data)
        except GitHubAPIError as e:
            if "Not Found" in str(e) or e.status_code == 404:
                return None
            raise

    async def search_repos(self, query: str, sort: str = "stars",
                           order: str = "desc", per_page: int = 30,
                           page: int = 1) -> Tuple[List[RepoInfo], int]:
        params = {"q": query, "sort": sort, "order": order,
                  "per_page": per_page, "page": page}
        data = await self._get("/search/repositories", params=params)
        total = data.get("total_count", 0)
        repos = [self._parse_repo_info(r) for r in data.get("items", [])]
        return repos, total

    async def get_trending(self, language: str = "",
                           per_page: int = 30) -> List[RepoInfo]:
        query_parts = ["stars:>10"]
        if language:
            query_parts.append(f"language:{language}")
        params = {
            "q": " ".join(query_parts),
            "sort": "updated", "order": "desc", "per_page": per_page,
        }
        data = await self._get("/search/repositories", params=params, cache=True)
        repos = [self._parse_repo_info(r) for r in data.get("items", [])]
        seven_days_ago = datetime.now() - timedelta(days=7)
        trending = []
        for repo in repos:
            if repo.pushed_at and repo.pushed_at > seven_days_ago:
                repo.source_type = SourceType.TRENDING
                trending.append(repo)
        return trending

    async def get_readme(self, owner: str, repo: str) -> str:
        try:
            import base64
            data = await self._get(f"/repos/{owner}/{repo}/readme", cache=True)
            content = data.get("content", "").replace("\n", "")
            return base64.b64decode(content).decode("utf-8")
        except Exception:
            return ""

    async def get_rate_limit_status(self) -> Dict[str, Any]:
        data = await self._get("/rate_limit", cache=False)
        return {
            "limit": data["rate"]["limit"],
            "remaining": data["rate"]["remaining"],
            "reset": datetime.fromtimestamp(data["rate"]["reset"]),
            "used": data["rate"]["used"],
        }

    @staticmethod
    def _parse_repo_info(data: dict) -> RepoInfo:
        topics = data.get("topics", []) or []
        created_at = updated_at = pushed_at = None
        if data.get("created_at"):
            created_at = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
        if data.get("updated_at"):
            updated_at = datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))
        if data.get("pushed_at"):
            pushed_at = datetime.fromisoformat(data["pushed_at"].replace("Z", "+00:00"))

        return RepoInfo(
            owner=data["owner"]["login"],
            name=data["name"],
            full_name=data["full_name"],
            description=data.get("description") or "",
            html_url=data["html_url"],
            stars=data.get("stargazers_count", 0),
            forks=data.get("forks_count", 0),
            language=data.get("language") or "",
            topics=topics,
            avatar_url=data.get("owner", {}).get("avatar_url", ""),
            license=data.get("license", {}).get("spdx_id", "") if data.get("license") else "",
            created_at=created_at,
            updated_at=updated_at,
            pushed_at=pushed_at,
        )


# ═══════════════════════════════════════════════════════════════════════
# 4. RepoCache — 本地仓库信息缓存
# ═══════════════════════════════════════════════════════════════════════

class RepoCache:
    """仓库信息本地缓存 — 内存 + 磁盘双层"""

    def __init__(self, cache_dir: str = "~/.livingtree/github_store_cache"):
        self.cache_dir = Path(os.path.expanduser(cache_dir))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache: Dict[str, Tuple[RepoInfo, float]] = {}
        self._ttl: float = 3600.0

    @staticmethod
    def _cache_key(full_name: str) -> str:
        return hashlib.md5(full_name.encode()).hexdigest()

    def get(self, full_name: str) -> Optional[RepoInfo]:
        key = self._cache_key(full_name)
        if key in self._memory_cache:
            repo, expire = self._memory_cache[key]
            if time.time() < expire:
                return repo
            del self._memory_cache[key]

        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                repo = RepoInfo(
                    owner=data["owner"], name=data["name"],
                    full_name=data["full_name"],
                    description=data.get("description", ""),
                    html_url=data["html_url"], stars=data.get("stars", 0),
                    forks=data.get("forks", 0),
                    language=data.get("language", ""),
                    topics=data.get("topics", []),
                    license=data.get("license", ""),
                )
                expire = data.get("_cache_expire", 0)
                if time.time() < expire:
                    self._memory_cache[key] = (repo, expire)
                    return repo
            except Exception:
                pass
        return None

    def set(self, repo: RepoInfo, ttl: Optional[float] = None) -> None:
        key = self._cache_key(repo.full_name)
        expire = time.time() + (ttl or self._ttl)
        self._memory_cache[key] = (repo, expire)
        cache_file = self.cache_dir / f"{key}.json"
        try:
            data = {k: v for k, v in repo.__dict__.items() if not k.startswith("_")}
            data["_cache_expire"] = expire
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"缓存仓库信息失败: {e}")

    def invalidate(self, full_name: str) -> None:
        key = self._cache_key(full_name)
        self._memory_cache.pop(key, None)
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            cache_file.unlink()


# ═══════════════════════════════════════════════════════════════════════
# 5. ReleaseDetector — Release 资源检测器
# ═══════════════════════════════════════════════════════════════════════

class ReleaseDetector:
    """从 Release 中检测可安装的桌面应用资源"""

    PLATFORM_TOPICS: Dict[PlatformType, List[str]] = {
        PlatformType.WINDOWS: ["windows", "win", "win32", "win64", "desktop"],
        PlatformType.LINUX: ["linux", "ubuntu", "debian", "fedora", "arch", "appimage", "unix"],
        PlatformType.MACOS: ["macos", "mac", "darwin", "apple", "desktop"],
        PlatformType.ANDROID: ["android", "mobile"],
    }

    DESKTOP_KEYWORDS: List[str] = [
        "desktop", "windows", "linux", "macos", "android",
        "app", "application", "software", "tool",
        "gui", "electron", "qt", "tkinter", "pyqt",
    ]

    def __init__(self):
        self._current_platform = _detect_current_platform()
        self._current_arch = _detect_current_arch()

    @property
    def current_platform(self) -> PlatformType:
        return self._current_platform

    @property
    def current_arch(self) -> str:
        return self._current_arch

    def detect_platform_from_topics(self, topics: List[str]) -> List[PlatformType]:
        supported = []
        topics_lower = [t.lower() for t in topics]
        for plat, keywords in self.PLATFORM_TOPICS.items():
            if any(k in topics_lower for k in keywords):
                supported.append(plat)
        return supported if supported else [PlatformType.ALL]

    def detect_installable_assets(self, release: GitHubRelease,
                                   preferred_platform: Optional[PlatformType] = None
                                   ) -> List[GitHubAsset]:
        candidates: List[Tuple[float, GitHubAsset]] = []
        for asset in release.assets:
            atype, aplat, aarch = _detect_asset_info(asset.name)
            asset.asset_type = atype
            asset.platform = aplat
            asset.architecture = aarch
            asset.is_compatible = self._is_compatible(
                aplat, aarch, preferred_platform)

            if atype != AssetType.ARCHIVE or aplat is not None:
                score = self._calculate_match_score(aplat, aarch, preferred_platform)
                candidates.append((score, asset))

        candidates.sort(key=lambda x: x[0], reverse=True)
        return [asset for _, asset in candidates]

    def _is_compatible(self, asset_platform: Optional[PlatformType],
                       asset_arch: Optional[str],
                       preferred_platform: Optional[PlatformType]) -> bool:
        if asset_platform is None:
            return True
        if preferred_platform is not None:
            return asset_platform == preferred_platform
        return asset_platform == self._current_platform

    def _calculate_match_score(self, asset_platform: Optional[PlatformType],
                                asset_arch: Optional[str],
                                preferred_platform: Optional[PlatformType]) -> float:
        if asset_platform is None:
            return 0.1
        score = 0.0
        if preferred_platform:
            if asset_platform == preferred_platform:
                score += 50
        elif asset_platform == self._current_platform:
            score += 40
        if asset_arch == self._current_arch:
            score += 30
        elif asset_arch is None:
            score += 10
        if asset_platform == PlatformType.WINDOWS:
            score += 10
        elif asset_platform in (PlatformType.LINUX, PlatformType.MACOS):
            score += 8
        return score

    def find_best_asset(self, assets: List[GitHubAsset],
                        platform: Optional[PlatformType] = None,
                        arch: Optional[str] = None) -> Optional[GitHubAsset]:
        if not assets:
            return None
        candidates = []
        for asset in assets:
            score = 0
            if platform and asset.platform == platform:
                score += 100
            elif platform is None and asset.platform == self._current_platform:
                score += 50
            if arch and asset.architecture == arch:
                score += 50
            elif arch is None and asset.architecture == self._current_arch:
                score += 25
            if asset.is_compatible:
                score += 20
            candidates.append((score, asset))
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    def filter_by_platform(self, assets: List[GitHubAsset],
                            platform: PlatformType) -> List[GitHubAsset]:
        return [a for a in assets if a.platform == platform]

    def is_desktop_app(self, repo: RepoInfo) -> bool:
        topics_lower = [t.lower() for t in repo.topics]
        for topic in topics_lower:
            if any(kw in topic for kw in self.DESKTOP_KEYWORDS):
                return True
        if repo.latest_release:
            assets = self.detect_installable_assets(repo.latest_release)
            return len(assets) > 0
        return False


# ═══════════════════════════════════════════════════════════════════════
# 6. Downloader — 下载管理器
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class DownloadConfig:
    download_dir: str = "~/.livingtree/downloads"
    max_concurrent: int = 3
    chunk_size: int = 1024 * 1024
    timeout: int = 300
    retry_times: int = 3
    retry_delay: float = 2.0


class Downloader:
    """下载管理器 — 断点续传 + 进度追踪 + 自动安装"""

    def __init__(self, config: Optional[DownloadConfig] = None):
        self.config = config or DownloadConfig()
        self._tasks: Dict[str, DownloadTask] = {}
        self._download_dir = Path(os.path.expanduser(self.config.download_dir))
        self._download_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _generate_task_id(url: str, repo: str) -> str:
        return hashlib.md5(f"{repo}:{url}".encode()).hexdigest()[:16]

    async def download_asset(
        self, asset: GitHubAsset, repo_full_name: str, version: str,
        platform: PlatformType,
        progress_callback: Optional[Callable[[DownloadTask], None]] = None,
        install_after_download: bool = False,
    ) -> Optional[str]:
        task_id = self._generate_task_id(asset.download_url, repo_full_name)
        task = DownloadTask(
            id=task_id, repo_full_name=repo_full_name, asset=asset,
            total_size=asset.size, status="pending",
            started_at=datetime.now(),
        )
        self._tasks[task_id] = task

        try:
            save_path = self._get_save_path(repo_full_name, version, asset.name)
            task.download_path = str(save_path)
            task.status = "downloading"
            success = await self._do_download(task, progress_callback)

            if success:
                task.status = "completed"
                task.completed_at = datetime.now()
                task.progress = 100.0
                logger.info(f"下载完成: {asset.name} -> {save_path}")
                if install_after_download:
                    await self._install_asset(save_path, asset, repo_full_name)
                return str(save_path)
            else:
                task.status = "failed"
                return None
        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            logger.error(f"下载失败: {asset.name}, 错误: {e}")
            return None
        finally:
            if progress_callback:
                progress_callback(task)

    async def _do_download(self, task: DownloadTask,
                           progress_callback: Optional[Callable]) -> bool:
        save_path = Path(task.download_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)

        downloaded = 0
        if save_path.exists():
            downloaded = save_path.stat().st_size
            if downloaded >= task.total_size:
                task.progress = 100.0
                return True

        headers = {"User-Agent": "LivingTree-GitHub-Store/1.0"}
        if downloaded > 0:
            headers["Range"] = f"bytes={downloaded}-"

        req = urllib.request.Request(task.asset.download_url, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                code = resp.status if hasattr(resp, 'status') else (resp.getcode() if hasattr(resp, 'getcode') else 200)
                if code not in (200, 206):
                    logger.error(f"HTTP {code}")
                    return False

                mode = "ab" if downloaded > 0 else "wb"
                with open(save_path, mode) as f:
                    while True:
                        chunk = resp.read(self.config.chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if task.total_size > 0:
                            task.progress = round(downloaded / task.total_size * 100, 1)
                        task.downloaded_size = downloaded
                        if progress_callback:
                            progress_callback(task)
                return True
        except Exception as e:
            logger.error(f"下载异常: {e}")
            task.error_message = str(e)
            if save_path.exists() and save_path.stat().st_size < task.total_size:
                try:
                    save_path.unlink()
                except Exception:
                    pass
            return False

    def _get_save_path(self, repo_full_name: str, version: str, asset_name: str) -> Path:
        repo_dir = self._download_dir / repo_full_name.replace("/", "_") / version
        repo_dir.mkdir(parents=True, exist_ok=True)
        return repo_dir / asset_name

    async def _install_asset(self, file_path: Path, asset: GitHubAsset,
                              repo_full_name: str) -> None:
        try:
            system = _platform.system().lower()

            if asset.asset_type == AssetType.EXE and system == "windows":
                await self._run_installer(file_path, ["/S", "/SILENT"])
            elif asset.asset_type == AssetType.MSI and system == "windows":
                await self._run_installer(file_path, ["/quiet", "/qn"])
            elif asset.asset_type == AssetType.APPIMAGE and system == "linux":
                os.chmod(file_path, 0o755)
            elif asset.asset_type == AssetType.DEB and system == "linux":
                await self._run_installer(file_path, ["-i"], dpkg=True)
            elif asset.asset_type == AssetType.RPM and system == "linux":
                await self._run_installer(file_path, ["-i"], rpm=True)
            elif asset.asset_type == AssetType.DMG and system == "darwin":
                await self._mount_dmg(file_path)
            elif asset.asset_type == AssetType.ARCHIVE:
                await self._extract_archive(file_path)
            else:
                logger.info(f"不支持自动安装类型: {asset.asset_type}")
        except Exception as e:
            logger.error(f"安装失败: {e}")

    @staticmethod
    async def _run_installer(file_path: Path, extra_args: list,
                              dpkg: bool = False, rpm: bool = False) -> None:
        if dpkg:
            cmd = ["dpkg", "-i", str(file_path)]
        elif rpm:
            cmd = ["rpm", "-i", "--force", str(file_path)]
        else:
            cmd = [str(file_path)] + extra_args

        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.error(f"安装失败: {stderr.decode() if stderr else stdout.decode()}")
        else:
            logger.info(f"安装完成: {file_path}")

    @staticmethod
    async def _mount_dmg(file_path: Path) -> None:
        mount_point = Path(f"/Volumes/{file_path.stem}")
        proc = await asyncio.create_subprocess_exec(
            "hdiutil", "attach", str(file_path),
            "-mountpoint", str(mount_point),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await proc.communicate()
        app_path = Path("/Applications")
        if mount_point.exists():
            for item in mount_point.iterdir():
                if item.suffix == ".app":
                    dest = app_path / item.name
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(item, dest)
        await asyncio.create_subprocess_exec(
            "hdiutil", "detach", str(mount_point),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

    @staticmethod
    async def _extract_archive(file_path: Path) -> None:
        extract_dir = file_path.parent / file_path.stem
        if file_path.suffix in (".gz", ".bz2") and ".tar" in file_path.name:
            import tarfile
            with tarfile.open(file_path) as tar:
                tar.extractall(extract_dir)
        else:
            import zipfile
            with zipfile.ZipFile(file_path) as zf:
                zf.extractall(extract_dir)

    def get_task(self, task_id: str) -> Optional[DownloadTask]:
        return self._tasks.get(task_id)

    def get_active_tasks(self) -> List[DownloadTask]:
        return [t for t in self._tasks.values()
                if t.status in ("pending", "downloading")]

    def cancel_task(self, task_id: str) -> bool:
        if task_id in self._tasks:
            self._tasks[task_id].status = "cancelled"
            return True
        return False

    def get_downloads_dir(self) -> Path:
        return self._download_dir

    def open_downloads_dir(self) -> None:
        path = str(self._download_dir)
        system = _platform.system()
        if system == "Windows":
            os.startfile(path)
        elif system == "Darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])


# ═══════════════════════════════════════════════════════════════════════
# 7. AppManager — 本地应用管理器
# ═══════════════════════════════════════════════════════════════════════

class AppManager:
    """管理本地已安装的 GitHub Store 应用"""

    def __init__(self, data_dir: str = "~/.livingtree/github_store"):
        self.data_dir = Path(os.path.expanduser(data_dir))
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.apps_file = self.data_dir / "installed_apps.json"
        self.favorites_file = self.data_dir / "favorites.json"
        self.starred_file = self.data_dir / "starred.json"
        self.recent_file = self.data_dir / "recent.json"

        self._apps: Dict[str, InstalledApp] = {}
        self._favorites: List[str] = []
        self._starred: List[str] = []
        self._recent: List[str] = []
        self._load()

    def _load(self) -> None:
        if self.apps_file.exists():
            try:
                with open(self.apps_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for k, v in data.items():
                        v["installed_at"] = datetime.fromisoformat(v["installed_at"])
                        self._apps[k] = InstalledApp(**v)
            except Exception as e:
                logger.warning(f"加载已安装应用失败: {e}")
        for attr, file in [('_favorites', self.favorites_file),
                            ('_starred', self.starred_file),
                            ('_recent', self.recent_file)]:
            if file.exists():
                try:
                    with open(file, "r", encoding="utf-8") as f:
                        setattr(self, attr, json.load(f))
                except Exception:
                    pass

    def _save(self) -> None:
        from dataclasses import asdict
        try:
            data = {k: asdict(v) for k, v in self._apps.items()}
            with open(self.apps_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.warning(f"保存已安装应用失败: {e}")
        for attr, file in [('_favorites', self.favorites_file),
                            ('_starred', self.starred_file),
                            ('_recent', self.recent_file)]:
            with open(file, "w", encoding="utf-8") as f:
                data = getattr(self, attr)
                json.dump(data[:100] if attr == '_recent' else data,
                          f, ensure_ascii=False, indent=2)

    # ── 已安装应用 ──

    def get_installed_apps(self) -> List[InstalledApp]:
        return list(self._apps.values())

    def get_app(self, full_name: str) -> Optional[InstalledApp]:
        return self._apps.get(full_name)

    def is_installed(self, full_name: str) -> bool:
        return full_name in self._apps

    def install_app(self, repo: RepoInfo, version: str, install_path: str,
                    asset_name: str, asset_size: int, platform: PlatformType,
                    architecture: Optional[str], download_url: str,
                    notes: str = "") -> None:
        app = InstalledApp(
            repo_full_name=repo.full_name,
            installed_version=version,
            installed_at=datetime.now(),
            install_path=install_path,
            asset_name=asset_name,
            asset_size=asset_size,
            platform=platform,
            architecture=architecture,
            current_version=version,
            update_available=False,
            download_url=download_url,
            notes=notes,
        )
        self._apps[repo.full_name] = app
        self._save()
        self._add_history(repo.full_name, "install", version)
        logger.info(f"记录应用安装: {repo.full_name} v{version}")

    def update_app_version(self, full_name: str, new_version: str,
                           new_install_path: str, download_url: str) -> None:
        if full_name in self._apps:
            app = self._apps[full_name]
            app.installed_version = new_version
            app.current_version = new_version
            app.update_available = False
            app.install_path = new_install_path
            app.download_url = download_url
            self._save()
            self._add_history(full_name, "update", new_version)
            logger.info(f"更新应用版本: {full_name} -> v{new_version}")

    def uninstall_app(self, full_name: str) -> None:
        if full_name in self._apps:
            version = self._apps[full_name].installed_version
            del self._apps[full_name]
            self._save()
            self._add_history(full_name, "uninstall", version)
            logger.info(f"卸载应用: {full_name}")

    def check_updates(self, updates: Dict[str, str]) -> None:
        for full_name, latest_version in updates.items():
            if full_name in self._apps:
                app = self._apps[full_name]
                if app.installed_version != latest_version:
                    app.current_version = latest_version
                    app.update_available = True
        self._save()

    # ── 收藏 ──

    def get_favorites(self) -> List[str]:
        return self._favorites.copy()

    def add_favorite(self, full_name: str) -> None:
        if full_name not in self._favorites:
            self._favorites.append(full_name)
            self._save()

    def remove_favorite(self, full_name: str) -> None:
        if full_name in self._favorites:
            self._favorites.remove(full_name)
            self._save()

    def is_favorite(self, full_name: str) -> bool:
        return full_name in self._favorites

    def toggle_favorite(self, full_name: str) -> bool:
        if full_name in self._favorites:
            self._favorites.remove(full_name)
            result = False
        else:
            self._favorites.append(full_name)
            result = True
        self._save()
        return result

    # ── 星标 ──

    def get_starred(self) -> List[str]:
        return self._starred.copy()

    def add_starred(self, full_name: str) -> None:
        if full_name not in self._starred:
            self._starred.append(full_name)
            self._save()

    def remove_starred(self, full_name: str) -> None:
        if full_name in self._starred:
            self._starred.remove(full_name)
            self._save()

    def is_starred(self, full_name: str) -> bool:
        return full_name in self._starred

    # ── 最近浏览 ──

    def get_recent(self, limit: int = 50) -> List[str]:
        return self._recent[:limit]

    def add_recent(self, full_name: str) -> None:
        if full_name in self._recent:
            self._recent.remove(full_name)
        self._recent.insert(0, full_name)
        self._recent = self._recent[:100]
        self._save()

    # ── 安装历史 ──

    def _add_history(self, full_name: str, action: str, version: str) -> None:
        hid = hashlib.md5(full_name.encode()).hexdigest()[:8]
        history_file = self.data_dir / "history" / f"{hid}.json"
        history_file.parent.mkdir(parents=True, exist_ok=True)
        history = []
        if history_file.exists():
            try:
                with open(history_file, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except Exception:
                pass
        history.append({
            "action": action, "version": version,
            "timestamp": datetime.now().isoformat(),
        })
        history = history[-50:]
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

    def get_history(self, full_name: str) -> List[Dict]:
        hid = hashlib.md5(full_name.encode()).hexdigest()[:8]
        history_file = self.data_dir / "history" / f"{hid}.json"
        if history_file.exists():
            try:
                with open(history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    # ── 统计 ──

    def get_stats(self) -> Dict[str, Any]:
        total_size = sum(a.asset_size for a in self._apps.values())
        platform_counts: Dict[str, int] = {}
        for app in self._apps.values():
            p = app.platform.value
            platform_counts[p] = platform_counts.get(p, 0) + 1
        return {
            "total_apps": len(self._apps),
            "total_favorites": len(self._favorites),
            "total_starred": len(self._starred),
            "total_recent": len(self._recent),
            "total_size_bytes": total_size,
            "total_size_gb": round(total_size / 1024**3, 2),
            "platform_counts": platform_counts,
            "update_available_count": sum(1 for a in self._apps.values() if a.update_available),
        }


# ═══════════════════════════════════════════════════════════════════════
# 8. GitHubStore — 统一入口
# ═══════════════════════════════════════════════════════════════════════

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


class GitHubStore:
    """GitHub Store — 桌面应用发现、下载、安装统一入口"""

    def __init__(self, token: Optional[str] = None,
                 data_dir: str = "~/.livingtree/github_store"):
        self.api = GitHubAPI(token)
        self.cache = RepoCache(os.path.join(data_dir, "cache"))
        self.detector = ReleaseDetector()
        self.downloader = Downloader()
        self.manager = AppManager(data_dir)

    # ── 仓库搜索与浏览 ──

    async def search(self, query: str, sort: str = "stars",
                     page: int = 1) -> Tuple[List[RepoInfo], int]:
        repos, total = await self.api.search_repos(query, sort=sort, page=page)
        for repo in repos:
            repo.is_installable = self.detector.is_desktop_app(repo)
        return repos, total

    async def get_trending(self, language: str = "") -> List[RepoInfo]:
        repos = await self.api.get_trending(language=language)
        for repo in repos:
            repo.is_installable = self.detector.is_desktop_app(repo)
        return repos

    async def get_repo_detail(self, owner: str, repo: str) -> Optional[RepoInfo]:
        info = await self.api.get_repo(owner, repo)
        if info:
            info.releases = await self.api.get_releases(owner, repo)
            if info.releases:
                info.latest_release = info.releases[0]
            info.readme = await self.api.get_readme(owner, repo)
            info.is_installable = self.detector.is_desktop_app(info)
            self.cache.set(info)
        return info

    # ── 下载与安装 ──

    async def download_and_install(self, owner: str, repo: str,
                                    progress_callback: Optional[Callable] = None
                                    ) -> Optional[str]:
        info = await self.get_repo_detail(owner, repo)
        if not info or not info.latest_release:
            return None

        assets = self.detector.detect_installable_assets(info.latest_release)
        best = self.detector.find_best_asset(assets)
        if not best:
            logger.warning(f"未找到兼容的安装资源: {owner}/{repo}")
            return None

        path = await self.downloader.download_asset(
            best, info.full_name, info.latest_release.version,
            self.detector.current_platform,
            progress_callback=progress_callback,
            install_after_download=True,
        )
        if path:
            self.manager.install_app(
                info, info.latest_release.version, path,
                best.name, best.size, self.detector.current_platform,
                best.architecture, best.download_url,
            )
        return path

    # ── 应用管理 ──

    def get_desktop_categories(self) -> List[CategoryInfo]:
        return DESKTOP_CATEGORIES


# ═══════════════════════════════════════════════════════════════════════
# 便捷工厂
# ═══════════════════════════════════════════════════════════════════════

def create_github_store(token: Optional[str] = None) -> GitHubStore:
    """创建 GitHubStore 实例"""
    return GitHubStore(token)
