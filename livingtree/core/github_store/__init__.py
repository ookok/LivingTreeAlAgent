"""
GitHub Store - 桌面代码仓库

发现、安装、管理 GitHub Release 中的桌面应用

功能:
- 发现 GitHub 趋势项目和热门 Release
- 搜索和浏览 GitHub 仓库
- 检测 Release 中的可安装资源 (EXE/MSI/DMG/AppImage/DEB/RPM/APK)
- 一键安装和更新桌面应用
- 管理已安装应用、收藏和历史
"""

import logging
from typing import List, Optional, Dict, Any, Callable
import asyncio

from .models import (
    RepoInfo, GitHubRelease, GitHubAsset, InstalledApp,
    PlatformType, AssetType, SourceType, DownloadTask,
    CategoryInfo, DESKTOP_CATEGORIES,
)
from .github_api import GitHubAPI, GitHubAPIError, RepoCache
from .release_detector import ReleaseDetector
from .app_manager import AppManager
from .downloader import Downloader, DownloadConfig

logger = logging.getLogger(__name__)


class GitHubStore:
    """
    GitHub Store 主系统

    用法:
        store = GitHubStore()
        await store.initialize()

        # 搜索
        results = await store.search("VSCode", platform="windows")

        # 浏览趋势
        trending = await store.get_trending()

        # 安装应用
        await store.install_app(repo, asset)
    """

    def __init__(
        self,
        github_token: Optional[str] = None,
        download_dir: Optional[str] = None,
    ):
        self._api = GitHubAPI(token=github_token)
        self._cache = RepoCache()
        self._detector = ReleaseDetector()
        self._app_manager = AppManager()
        self._downloader = Downloader(
            config=DownloadConfig(
                download_dir=download_dir or "~/.hermes-desktop/github_store/downloads",
            )
        )

        self._initialized = False
        self._event_callbacks: Dict[str, List[Callable]] = {}

    async def initialize(self):
        """初始化"""
        if self._initialized:
            return

        # 检查 GitHub API 状态
        try:
            status = await self._api.get_rate_limit_status()
            logger.info(
                f"GitHub API 状态: {status['remaining']}/{status['limit']} "
                f"(重置于 {status['reset']})"
            )
        except Exception as e:
            logger.warning(f"无法获取 GitHub API 状态: {e}")

        self._initialized = True

    # ── 发现 ────────────────────────────────────────────────────────

    async def get_trending(
        self,
        language: str = "",
        platform: Optional[PlatformType] = None,
        per_page: int = 30,
    ) -> List[RepoInfo]:
        """
        获取趋势仓库

        Args:
            language: 编程语言筛选
            platform: 平台筛选
            per_page: 返回数量

        Returns:
            趋势仓库列表
        """
        repos = await self._api.get_trending(language=language, per_page=per_page)

        # 过滤有可安装资源的
        filtered = []
        for repo in repos:
            # 检查缓存
            cached = self._cache.get(repo.full_name)
            if cached:
                repo = cached

            # 检查最新 Release
            try:
                latest, _ = await self._api.get_releases_with_assets(
                    repo.owner, repo.name, platform=platform
                )
                repo.latest_release = latest
                repo.is_installable = repo.check_installable()
                self._cache.set(repo)
            except Exception as e:
                logger.debug(f"获取 {repo.full_name} Release 失败: {e}")

            if repo.is_installable or repo.latest_release:
                filtered.append(repo)

        return filtered[:per_page]

    async def search(
        self,
        query: str,
        platform: Optional[PlatformType] = None,
        language: Optional[str] = None,
        sort: str = "stars",
        per_page: int = 30,
    ) -> tuple[List[RepoInfo], int]:
        """
        搜索仓库

        Args:
            query: 搜索关键词
            platform: 平台筛选
            language: 语言筛选
            sort: 排序 (stars/forks/updated)
            per_page: 每页数量

        Returns:
            (仓库列表, 总数)
        """
        # 构建查询
        query_parts = [query]
        if platform:
            platform_keywords = {
                PlatformType.WINDOWS: "windows",
                PlatformType.LINUX: "linux",
                PlatformType.MACOS: "macos",
                PlatformType.ANDROID: "android",
            }
            query_parts.append(platform_keywords.get(platform, ""))
        if language:
            query_parts.append(f"language:{language}")

        # 添加桌面应用筛选
        query_parts.append("stars:>10")  # 至少 10 个星标

        full_query = " ".join(filter(None, query_parts))

        repos, total = await self._api.search_repos(
            full_query,
            sort=sort,
            per_page=per_page,
        )

        # 检查每个仓库的 Release
        for repo in repos:
            try:
                latest, _ = await self._api.get_releases_with_assets(
                    repo.owner, repo.name, platform=platform
                )
                repo.latest_release = latest
                repo.is_installable = repo.check_installable()
            except Exception:
                pass

        return repos, total

    async def get_repo_detail(
        self,
        owner: str,
        repo: str,
        include_readme: bool = True,
    ) -> RepoInfo:
        """
        获取仓库详细信息

        Args:
            owner: 仓库所有者
            repo: 仓库名
            include_readme: 是否获取 README

        Returns:
            仓库信息
        """
        # 检查缓存
        cached = self._cache.get(f"{owner}/{repo}")
        if cached and not include_readme:
            return cached

        repo_info = await self._api.get_repo(owner, repo)

        # 获取 Release
        latest, all_releases = await self._api.get_releases_with_assets(owner, repo)
        repo_info.latest_release = latest
        repo_info.releases = all_releases
        repo_info.is_installable = repo_info.check_installable()

        # 获取 README
        if include_readme:
            try:
                repo_info.readme = await self._api.get_readme(owner, repo)
            except Exception:
                pass

        # 缓存
        self._cache.set(repo_info)

        # 添加到最近浏览
        self._app_manager.add_recent(repo_info.full_name)

        return repo_info

    def get_categories(self) -> List[CategoryInfo]:
        """获取分类列表"""
        return DESKTOP_CATEGORIES

    async def get_category_repos(
        self,
        category: CategoryInfo,
        platform: Optional[PlatformType] = None,
        per_page: int = 30,
    ) -> List[RepoInfo]:
        """获取分类下的仓库"""
        # 用 Topics 搜索
        query = " ".join(category.topics) + " stars:>50"

        repos, _ = await self._api.search_repos(
            query,
            sort="stars",
            per_page=per_page,
        )

        # 过滤和检查
        filtered = []
        for repo in repos:
            if repo.topics:
                # 检查是否有匹配的 Topic
                repo_topics = set(t.lower() for t in repo.topics)
                cat_topics = set(t.lower() for t in category.topics)
                if not repo_topics & cat_topics:
                    continue

            try:
                latest, _ = await self._api.get_releases_with_assets(
                    repo.owner, repo.name, platform=platform
                )
                repo.latest_release = latest
                repo.is_installable = repo.check_installable()
                repo.source_type = SourceType.CATEGORY
            except Exception:
                pass

            if repo.is_installable:
                filtered.append(repo)

        return filtered[:per_page]

    # ── 应用管理 ────────────────────────────────────────────────────

    def get_installed_apps(self) -> List[InstalledApp]:
        """获取已安装的应用"""
        return self._app_manager.get_installed_apps()

    def get_favorites(self) -> List[str]:
        """获取收藏列表"""
        return self._app_manager.get_favorites()

    def toggle_favorite(self, full_name: str) -> bool:
        """切换收藏状态"""
        return self._app_manager.toggle_favorite(full_name)

    def is_favorite(self, full_name: str) -> bool:
        """是否已收藏"""
        return self._app_manager.is_favorite(full_name)

    def get_recent(self, limit: int = 50) -> List[str]:
        """获取最近浏览"""
        return self._app_manager.get_recent(limit)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self._app_manager.get_stats()

    # ── 下载安装 ────────────────────────────────────────────────────

    async def install_app(
        self,
        repo: RepoInfo,
        asset: GitHubAsset,
        version: str,
        progress_callback: Optional[Callable[[DownloadTask], None]] = None,
    ) -> Optional[str]:
        """
        安装应用

        Args:
            repo: 仓库信息
            asset: 要安装的资源
            version: 版本号
            progress_callback: 进度回调

        Returns:
            安装路径，失败返回 None
        """
        # 下载
        download_path = await self._downloader.download_asset(
            asset=asset,
            repo_full_name=repo.full_name,
            version=version,
            platform=asset.platform or PlatformType.ALL,
            progress_callback=progress_callback,
            install_after_download=True,
        )

        if download_path:
            # 记录安装
            self._app_manager.install_app(
                repo=repo,
                version=version,
                install_path=download_path,
                asset_name=asset.name,
                asset_size=asset.size,
                platform=asset.platform or PlatformType.ALL,
                architecture=asset.architecture,
                download_url=asset.download_url,
            )

        return download_path

    async def check_updates(self, repos: List[RepoInfo]) -> Dict[str, str]:
        """
        批量检查更新

        Args:
            repos: 需要检查更新的仓库列表

        Returns:
            {full_name: latest_version, ...}
        """
        updates = {}

        for repo in repos:
            try:
                latest = await self._api.get_latest_release(repo.owner, repo.name)
                if latest:
                    updates[repo.full_name] = latest.version
            except Exception:
                pass

        self._app_manager.check_updates(updates)
        return updates

    # ── 事件系统 ────────────────────────────────────────────────────

    def on(self, event: str, callback: Callable):
        """注册事件回调"""
        if event not in self._event_callbacks:
            self._event_callbacks[event] = []
        self._event_callbacks[event].append(callback)

    def _emit(self, event: str, data: Any):
        """触发事件"""
        if event in self._event_callbacks:
            for callback in self._event_callbacks[event]:
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f"事件回调错误: {e}")

    # ── 工具 ────────────────────────────────────────────────────────

    def get_recommended_assets(
        self,
        release: GitHubRelease,
        platform: Optional[PlatformType] = None,
    ) -> List[GitHubAsset]:
        """
        从 Release 中获取推荐的资源

        Args:
            release: Release 信息
            platform: 目标平台

        Returns:
            推荐的资源列表
        """
        return self._detector.detect_installable_assets(release, platform)

    def find_best_asset(
        self,
        assets: List[GitHubAsset],
        platform: Optional[PlatformType] = None,
    ) -> Optional[GitHubAsset]:
        """找到最佳匹配的资源"""
        return self._detector.find_best_asset(assets, platform)

    def get_current_platform(self) -> PlatformType:
        """获取当前平台"""
        return self._detector.current_platform

    def get_current_arch(self) -> str:
        """获取当前架构"""
        return self._detector.current_arch

    def open_downloads_folder(self):
        """打开下载文件夹"""
        self._downloader.open_downloads_dir()

    async def get_rate_limit(self) -> Dict[str, Any]:
        """获取 API 速率限制状态"""
        return await self._api.get_rate_limit_status()

    def clear_cache(self):
        """清空缓存"""
        self._api.clear_cache()
        self._cache = RepoCache()


# 单例
_instance: Optional[GitHubStore] = None


def get_github_store(
    github_token: Optional[str] = None,
    download_dir: Optional[str] = None,
) -> GitHubStore:
    """获取 GitHub Store 单例"""
    global _instance
    if _instance is None:
        _instance = GitHubStore(github_token=github_token, download_dir=download_dir)
    return _instance
