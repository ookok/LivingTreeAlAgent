"""
GitHub API 集成
GitHub Store - 桌面代码仓库
"""

import asyncio
import time
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import hashlib
import re

from .models import RepoInfo, GitHubRelease, GitHubAsset, PlatformType, AssetType

logger = logging.getLogger(__name__)


class GitHubAPIError(Exception):
    """GitHub API 错误"""
    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code


class GitHubAPI:
    """
    GitHub API 客户端

    速率限制:
    - 未认证: 60 req/hour
    - 已认证: 5000 req/hour
    """

    BASE_URL = "https://api.github.com"
    HEADERS = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    def __init__(self, token: Optional[str] = None):
        import os
        self.token = token or os.environ.get("GITHUB_TOKEN", "")
        if self.token:
            self.HEADERS["Authorization"] = f"Bearer {self.token}"
        self._rate_limit_remaining: int = 60
        self._rate_limit_reset: float = 0  # Unix timestamp
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._cache_ttl: float = 300  # 5 minutes

    def _is_cache_valid(self, key: str) -> bool:
        """检查缓存是否有效"""
        if key not in self._cache:
            return False
        _, expire = self._cache[key]
        return time.time() < expire

    def _get_cached(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if self._is_cache_valid(key):
            return self._cache[key][0]
        return None

    def _set_cache(self, key: str, value: Any, ttl: Optional[float] = None):
        """设置缓存"""
        expire = time.time() + (ttl or self._cache_ttl)
        self._cache[key] = (value, expire)

    def _update_rate_limit(self, headers: Dict):
        """从响应头更新速率限制"""
        self._rate_limit_remaining = int(headers.get("X-RateLimit-Remaining", 60))
        self._rate_limit_reset = float(headers.get("X-RateLimit-Reset", 0))

    async def _get(self, path: str, params: Optional[Dict] = None,
                   cache: bool = True) -> Dict:
        """执行 GET 请求"""
        import urllib.request
        import json

        cache_key = f"{path}:{json.dumps(params or {}, sort_keys=True)}"

        # 检查缓存
        if cache:
            cached = self._get_cached(cache_key)
            if cached is not None:
                return cached

        # 检查速率限制
        if self._rate_limit_remaining <= 0 and time.time() < self._rate_limit_reset:
            wait_time = self._rate_limit_reset - time.time()
            logger.warning(f"速率限制达到，等待 {wait_time:.0f}s")
            await asyncio.sleep(min(wait_time, 60))

        url = f"{self.BASE_URL}{path}"
        if params:
            query = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{query}"

        req = urllib.request.Request(url, headers=self.HEADERS)

        try:
            def _fetch():
                return urllib.request.urlopen(req, timeout=30)

            resp = await asyncio.to_thread(_fetch)
            headers = dict(resp.headers)
            self._update_rate_limit(headers)
            data = json.loads(resp.read().decode("utf-8"))

            # 缓存响应
            if cache:
                self._set_cache(cache_key, data)

            return data

        except urllib.error.HTTPError as e:
            if e.code == 403:
                # 可能是速率限制
                self._rate_limit_remaining = 0
                raise GitHubAPIError("API 速率限制达到", 403)
            raise GitHubAPIError(f"HTTP 错误: {e.code}", e.code)
        except Exception as e:
            raise GitHubAPIError(f"请求失败: {e}")

    async def get_repo(self, owner: str, repo: str) -> RepoInfo:
        """获取仓库信息"""
        data = await self._get(f"/repos/{owner}/{repo}")
        return self._parse_repo_info(data)

    async def get_releases(self, owner: str, repo: str,
                          per_page: int = 30) -> List[GitHubRelease]:
        """获取仓库的所有 Release"""
        releases = []
        page = 1

        while True:
            data = await self._get(
                f"/repos/{owner}/{repo}/releases",
                params={"per_page": per_page, "page": page}
            )
            if not data:
                break

            for r in data:
                if not r.get("draft", False):  # 跳过草稿
                    releases.append(GitHubRelease.from_github_api(r))

            if len(data) < per_page:
                break
            page += 1

        return releases

    async def get_latest_release(self, owner: str, repo: str) -> Optional[GitHubRelease]:
        """获取最新 Release"""
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
        """
        搜索仓库

        Args:
            query: 搜索关键词
            sort: 排序字段 (stars, forks, updated)
            order: 排序方向 (desc, asc)
            per_page: 每页数量
            page: 页码

        Returns:
            (仓库列表, 总数)
        """
        params = {
            "q": query,
            "sort": sort,
            "order": order,
            "per_page": per_page,
            "page": page,
        }

        data = await self._get("/search/repositories", params=params)
        total = data.get("total_count", 0)
        repos = [self._parse_repo_info(r) for r in data.get("items", [])]
        return repos, total

    async def get_trending(self, language: str = "", since: str = "daily",
                           per_page: int = 30) -> List[RepoInfo]:
        """
        获取趋势仓库 (模拟 GitHub Trending)

        由于 GitHub 不提供 Trending API，我们通过搜索 + 排序实现
        """
        import urllib.parse

        # 构建查询字符串
        query_parts = ["stars:>10"]  # 至少 10 个星标
        if language:
            query_parts.append(f"language:{language}")

        # 按更新时间排序
        sort = "updated"

        params = {
            "q": " ".join(query_parts),
            "sort": sort,
            "order": "desc",
            "per_page": per_page,
        }

        data = await self._get("/search/repositories", params=params, cache=True)
        repos = [self._parse_repo_info(r) for r in data.get("items", [])]

        # 过滤出最近活跃的仓库 (7天内有更新)
        seven_days_ago = datetime.now() - timedelta(days=7)
        trending = []
        for repo in repos:
            if repo.pushed_at and repo.pushed_at > seven_days_ago:
                repo.source_type = "trending"
                trending.append(repo)

        return trending

    async def get_releases_with_assets(self, owner: str, repo: str,
                                       platform: Optional[PlatformType] = None
                                       ) -> Tuple[Optional[GitHubRelease], List[GitHubRelease]]:
        """
        获取仓库的 Release 信息，并过滤出有可安装资源的

        Returns:
            (最新 Release, 所有 Release 列表)
        """
        releases = await self.get_releases(owner, repo)

        # 过滤有可安装资源的 Release
        def has_installable(release: GitHubRelease) -> bool:
            for asset in release.assets:
                if asset.asset_type != AssetType.ARCHIVE:
                    if platform is None or asset.platform is None:
                        return True
                    if asset.platform == platform:
                        return True
            return False

        filtered = [r for r in releases if has_installable(r)]

        latest = filtered[0] if filtered else None
        return latest, filtered

    def _parse_repo_info(self, data: dict) -> RepoInfo:
        """解析仓库信息"""
        topics = data.get("topics", []) or []
        # GitHub API v4 风格
        if not topics and data.get("repositoryTopics"):
            topics = [
                rt["node"]["topic"]["name"]
                for rt in data.get("repositoryTopics", {}).get("nodes", [])
            ]

        created_at = None
        updated_at = None
        pushed_at = None

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

    async def get_readme(self, owner: str, repo: str) -> str:
        """获取仓库 README"""
        try:
            data = await self._get(f"/repos/{owner}/{repo}/readme", cache=True)
            import base64
            content = data.get("content", "")
            # GitHub 返回 base64 编码的内容，带换行
            content = content.replace("\n", "")
            decoded = base64.b64decode(content).decode("utf-8")
            return decoded
        except Exception:
            return ""

    async def get_rate_limit_status(self) -> Dict[str, Any]:
        """获取速率限制状态"""
        data = await self._get("/rate_limit", cache=False)
        return {
            "limit": data["rate"]["limit"],
            "remaining": data["rate"]["remaining"],
            "reset": datetime.fromtimestamp(data["rate"]["reset"]),
            "used": data["rate"]["used"],
        }

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()


class RepoCache:
    """仓库信息本地缓存"""

    def __init__(self, cache_dir: str = "~/.hermes-desktop/github_store_cache"):
        import os
        from pathlib import Path
        self.cache_dir = Path(os.path.expanduser(cache_dir))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache: Dict[str, Tuple[RepoInfo, float]] = {}
        self._ttl = 3600  # 1 hour

    def _cache_key(self, full_name: str) -> str:
        """生成缓存键"""
        return hashlib.md5(full_name.encode()).hexdigest()

    def get(self, full_name: str) -> Optional[RepoInfo]:
        """获取缓存的仓库信息"""
        key = self._cache_key(full_name)

        # 内存缓存优先
        if key in self._memory_cache:
            repo, expire = self._memory_cache[key]
            if time.time() < expire:
                return repo
            del self._memory_cache[key]

        # 磁盘缓存
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                import json
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                repo = RepoInfo(
                    owner=data["owner"],
                    name=data["name"],
                    full_name=data["full_name"],
                    description=data.get("description", ""),
                    html_url=data["html_url"],
                    stars=data.get("stars", 0),
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

    def set(self, repo: RepoInfo, ttl: Optional[float] = None):
        """缓存仓库信息"""
        import json
        key = self._cache_key(repo.full_name)
        expire = time.time() + (ttl or self._ttl)

        # 内存缓存
        self._memory_cache[key] = (repo, expire)

        # 磁盘缓存
        cache_file = self.cache_dir / f"{key}.json"
        try:
            data = repo.__dict__.copy()
            data["_cache_expire"] = expire
            # 移除不可序列化的字段
            for k in list(data.keys()):
                if k.startswith("_"):
                    del data[k]
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"缓存仓库信息失败: {e}")

    def invalidate(self, full_name: str):
        """使缓存失效"""
        key = self._cache_key(full_name)
        self._memory_cache.pop(key, None)
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            cache_file.unlink()
