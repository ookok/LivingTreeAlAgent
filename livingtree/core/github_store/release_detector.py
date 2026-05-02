"""
Release 检测器
从 GitHub Release 中检测可安装的桌面应用资源
"""

import re
import platform
import logging
from typing import List, Optional, Tuple

from .models import (
    GitHubRelease, GitHubAsset, RepoInfo,
    AssetType, PlatformType
)

logger = logging.getLogger(__name__)


class ReleaseDetector:
    """
    从 Release 中检测可安装的桌面应用

    检测策略:
    1. 文件扩展名匹配 (.exe, .msi, .dmg, .appimage, .deb, .rpm, .apk)
    2. 文件名模式匹配 (包含 windows, linux, macos 等关键词)
    3. 平台标签辅助判断
    """

    # 各平台的文件名模式
    PLATFORM_PATTERNS = {
        PlatformType.WINDOWS: [
            r"windows", r"win64", r"win32", r"windows-x64",
            r"windows-amd64", r"windows-x86", r"\.exe", r"\.msi",
            r"-windows", r"_windows", r"win64.exe", r"win32.exe",
        ],
        PlatformType.LINUX: [
            r"linux", r"ubuntu", r"debian", r"fedora", r"arch",
            r"\.appimage", r"\.deb", r"\.rpm", r"-linux",
            r"_linux", r"linux-x64", r"linux-amd64", r"linux-arm64",
        ],
        PlatformType.MACOS: [
            r"macos", r"macosx", r"darwin", r"mac-os", r"macosx",
            r"\.dmg", r"\.app", r"-macos", r"_macos", r"macosx",
            r"-mac", r"_mac", r"apple-silicon", r"arm64-macos",
        ],
        PlatformType.ANDROID: [
            r"android", r"\.apk", r"-android", r"_android",
            r"arm64-v8a", r"armeabi-v7a", r"x86_64-android",
        ],
    }

    # 架构模式
    ARCH_PATTERNS = [
        (r"amd64|x86_64|x64", "x64"),
        (r"386|i386|i686|x86", "x86"),
        (r"arm64|aarch64|armv8", "arm64"),
        (r"armv7|armeabi-v7", "armv7"),
    ]

    # 桌面平台对应的 GitHub Topics
    PLATFORM_TOPICS = {
        PlatformType.WINDOWS: ["windows", "win", "win32", "win64", "desktop"],
        PlatformType.LINUX: ["linux", "ubuntu", "debian", "fedora", "arch", "appimage", "unix"],
        PlatformType.MACOS: ["macos", "mac", "darwin", "apple", "desktop"],
        PlatformType.ANDROID: ["android", "mobile"],
    }

    def __init__(self):
        self._current_platform = self._detect_current_platform()
        self._current_arch = self._detect_current_arch()

    def _detect_current_platform(self) -> PlatformType:
        """检测当前平台"""
        system = platform.system().lower()
        if system == "windows":
            return PlatformType.WINDOWS
        elif system == "linux":
            return PlatformType.LINUX
        elif system == "darwin":
            return PlatformType.MACOS
        return PlatformType.LINUX  # 默认 Linux

    def _detect_current_arch(self) -> str:
        """检测当前架构"""
        machine = platform.machine().lower()
        if machine in ("amd64", "x86_64"):
            return "x64"
        elif machine in ("arm64", "aarch64"):
            return "arm64"
        elif machine in ("i386", "i686", "x86"):
            return "x86"
        elif "arm" in machine:
            return "armv7"
        return "x64"  # 默认 x64

    @property
    def current_platform(self) -> PlatformType:
        return self._current_platform

    @property
    def current_arch(self) -> str:
        return self._current_arch

    def detect_platform_from_topics(self, topics: List[str]) -> List[PlatformType]:
        """从 Topics 检测支持的平台"""
        supported = []
        topics_lower = [t.lower() for t in topics]

        for plat, keywords in self.PLATFORM_TOPICS.items():
            if any(k in topics_lower for k in keywords):
                supported.append(plat)

        return supported if supported else [PlatformType.ALL]

    def detect_installable_assets(self, release: GitHubRelease,
                                   preferred_platform: Optional[PlatformType] = None
                                   ) -> List[GitHubAsset]:
        """
        从 Release 中检测可安装的资源

        Args:
            release: Release 信息
            preferred_platform: 偏好的平台

        Returns:
            可安装的资源列表，按匹配度排序
        """
        candidates = []

        for asset in release.assets:
            # 检测资源类型
            asset_type, asset_platform, asset_arch = self._analyze_asset(asset.name)

            asset.asset_type = asset_type
            asset.platform = asset_platform
            asset.architecture = asset_arch

            # 检查是否兼容当前系统
            is_compatible = self._is_compatible(
                asset_platform, asset_arch, preferred_platform
            )
            asset.is_compatible = is_compatible

            # 只保留可识别的桌面应用资源
            if asset_type != AssetType.ARCHIVE or asset_platform is not None:
                # 计算匹配分数
                score = self._calculate_match_score(
                    asset_platform, asset_arch, preferred_platform
                )
                candidates.append((score, asset))

        # 按匹配度排序
        candidates.sort(key=lambda x: x[0], reverse=True)
        return [asset for _, asset in candidates]

    def _analyze_asset(self, name: str) -> Tuple[AssetType, Optional[PlatformType], Optional[str]]:
        """
        分析资源文件

        Returns:
            (资源类型, 平台, 架构)
        """
        name_lower = name.lower()

        # 1. 先检测扩展名
        for ext, atype in [
            (".exe", AssetType.EXE),
            (".msi", AssetType.MSI),
            (".dmg", AssetType.DMG),
            (".appimage", AssetType.APPIMAGE),
            (".deb", AssetType.DEB),
            (".rpm", AssetType.RPM),
            (".apk", AssetType.ASSET),
        ]:
            if name_lower.endswith(ext):
                # 从文件名推断平台和架构
                plat = self._detect_platform_from_name(name_lower)
                arch = self._detect_arch_from_name(name_lower)
                return atype, plat, arch

        # 2. 检测平台关键词
        plat = self._detect_platform_from_name(name_lower)
        if plat:
            arch = self._detect_arch_from_name(name_lower)
            return AssetType.ARCHIVE, plat, arch

        return AssetType.ARCHIVE, None, None

    def _detect_platform_from_name(self, name: str) -> Optional[PlatformType]:
        """从文件名检测平台"""
        for platform_type, patterns in self.PLATFORM_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, name):
                    return platform_type
        return None

    def _detect_arch_from_name(self, name: str) -> Optional[str]:
        """从文件名检测架构"""
        for pattern, arch in self.ARCH_PATTERNS:
            if re.search(pattern, name):
                return arch
        return None

    def _is_compatible(self, asset_platform: Optional[PlatformType],
                       asset_arch: Optional[str],
                       preferred_platform: Optional[PlatformType]) -> bool:
        """检查资源是否与当前系统兼容"""
        # 如果没有平台信息，假设通用
        if asset_platform is None:
            return True

        # 如果有偏好平台，检查是否匹配
        if preferred_platform is not None:
            return asset_platform == preferred_platform

        # 检查是否与当前平台匹配
        return asset_platform == self._current_platform

    def _calculate_match_score(self, asset_platform: Optional[PlatformType],
                                asset_arch: Optional[str],
                                preferred_platform: Optional[PlatformType]) -> float:
        """计算匹配分数"""
        score = 0.0

        if asset_platform is None:
            # 通用资源的低优先级
            return 0.1

        if preferred_platform:
            # 偏好平台优先
            if asset_platform == preferred_platform:
                score += 50
        else:
            # 当前平台优先
            if asset_platform == self._current_platform:
                score += 40

        # 架构匹配
        if asset_arch == self._current_arch:
            score += 30
        elif asset_arch is None:
            score += 10  # 架构未指定，默认兼容

        # 平台精确匹配
        if asset_platform == PlatformType.WINDOWS:
            score += 10
        elif asset_platform == PlatformType.LINUX:
            score += 8
        elif asset_platform == PlatformType.MACOS:
            score += 8

        return score

    def filter_by_platform(self, assets: List[GitHubAsset],
                            platform: PlatformType) -> List[GitHubAsset]:
        """按平台过滤资源"""
        return [a for a in assets if a.platform == platform]

    def find_best_asset(self, assets: List[GitHubAsset],
                        platform: Optional[PlatformType] = None,
                        arch: Optional[str] = None) -> Optional[GitHubAsset]:
        """
        找到最佳匹配的资源

        Args:
            assets: 资源列表
            platform: 目标平台
            arch: 目标架构

        Returns:
            最佳匹配的资源，如果没有则返回 None
        """
        if not assets:
            return None

        candidates = []
        for asset in assets:
            score = 0

            # 平台匹配
            if platform and asset.platform == platform:
                score += 100
            elif platform is None and asset.platform == self._current_platform:
                score += 50

            # 架构匹配
            if arch and asset.architecture == arch:
                score += 50
            elif arch is None and asset.architecture == self._current_arch:
                score += 25

            # 可用性
            if asset.is_compatible:
                score += 20

            candidates.append((score, asset))

        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1] if candidates else None

    def is_desktop_app(self, repo: RepoInfo) -> bool:
        """
        判断仓库是否为桌面应用

        判断依据:
        1. Topics 包含平台关键词
        2. 最新 Release 有可安装资源
        """
        # 检查 Topics
        topics_lower = [t.lower() for t in repo.topics]

        desktop_keywords = [
            "desktop", "windows", "linux", "macos", "android",
            "app", "application", "software", "tool",
            "gui", "electron", "qt", "tkinter", "pyqt",
        ]

        for topic in topics_lower:
            if any(kw in topic for kw in desktop_keywords):
                return True

        # 检查是否有最新 Release 且包含可安装资源
        if repo.latest_release:
            assets = self.detect_installable_assets(repo.latest_release)
            return len(assets) > 0

        return False
