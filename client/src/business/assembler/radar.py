"""
开源雷达 (OSS Radar)

目标：按需求找最合适的开源库。

多源扫描：
- GitHub API
- Gitee 镜像
- 本地热点库兜底

过滤：
- 协议（MIT/Apache/BSD 优先）
- 可本地运行（非 SaaS）
- 语言（Go/Rust/Node/Python）

排序：星数 + 维护活跃度 + 与需求匹配度
输出：候选库列表（名称、星数、协议、理由）
"""

import asyncio
import aiohttp
import re
import time
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class License(Enum):
    """许可证类型"""
    MIT = "MIT"
    APACHE = "Apache-2.0"
    BSD = "BSD"
    GPL = "GPL"
    LGPL = "LGPL"
    AGPL = "AGPL"
    UNKNOWN = "Unknown"

    @classmethod
    def from_string(cls, s: str) -> 'License':
        s = s.upper().replace(" ", "-").replace("2.0", "-2.0")
        mapping = {
            "MIT": cls.MIT,
            "APACHE": cls.APACHE,
            "BSD": cls.BSD,
            "GPL": cls.GPL,
            "LGPL": cls.LGPL,
            "AGPL": cls.AGPL,
        }
        for key, val in mapping.items():
            if key in s:
                return val
        return cls.UNKNOWN

    def is_allowable(self) -> bool:
        """是否允许（白名单）"""
        return self in (self.MIT, self.APACHE, self.BSD, self.UNKNOWN)


@dataclass
class RepoInfo:
    """仓库信息"""
    name: str
    full_name: str                      # owner/repo
    description: str = ""
    url: str = ""
    stars: int = 0
    forks: int = 0
    language: str = ""
    license: License = License.UNKNOWN
    last_updated: str = ""
    homepage: str = ""

    # 评分相关
    match_score: float = 0.0            # 与需求匹配度
    activity_score: float = 0.0         # 活跃度评分

    # 来源
    source: str = "github"              # github / gitee / local

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "full_name": self.full_name,
            "description": self.description,
            "url": self.url,
            "stars": self.stars,
            "forks": self.forks,
            "language": self.language,
            "license": self.license.value,
            "last_updated": self.last_updated,
            "homepage": self.homepage,
            "match_score": self.match_score,
            "activity_score": self.activity_score,
            "source": self.source,
        }


class OSSRadar:
    """开源雷达 - 多源库发现"""

    # 白名单许可证
    ALLOWED_LICENSES = {License.MIT, License.APACHE, License.BSD, License.UNKNOWN}

    # GitHub API 端点
    GITHUB_API = "https://api.github.com"
    GITHUB_SEARCH = f"{GITHUB_API}/search/repositories"

    # Gitee API 端点
    GITEE_API = "https://gitee.com/api/v5"
    GITEE_SEARCH = f"{GITEE_API}/search/repositories"

    def __init__(self):
        self._cache: dict[str, list[RepoInfo]] = {}
        self._session: Optional[aiohttp.ClientSession] = None
        self._rate_limit_delay = 1.0  # GitHub API 限速间隔

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def discover(
        self,
        query: str,
        language: Optional[str] = None,
        max_results: int = 10
    ) -> list[RepoInfo]:
        """
        发现开源库

        Args:
            query: 搜索查询
            language: 编程语言筛选
            max_results: 最大结果数

        Returns:
            list[RepoInfo]: 候选库列表
        """
        cache_key = f"{query}:{language}:{max_results}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        results = []

        # 并行搜索 GitHub 和 Gitee
        tasks = [
            self._search_github(query, language, max_results // 2),
            self._search_gitee(query, language, max_results // 2),
        ]

        github_results, gitee_results = await asyncio.gather(*tasks, return_exceptions=True)

        if isinstance(github_results, list):
            results.extend(github_results)
        if isinstance(gitee_results, list):
            results.extend(gitee_results)

        # 按评分排序
        results = self._rank_results(results)

        # 缓存
        self._cache[cache_key] = results[:max_results]
        return results[:max_results]

    async def _search_github(
        self,
        query: str,
        language: Optional[str],
        max_results: int
    ) -> list[RepoInfo]:
        """搜索 GitHub"""
        try:
            session = await self._get_session()

            # 构建搜索查询
            search_query = query
            if language:
                search_query += f" language:{language}"
            search_query += " in:name,in:description,in:readme"

            params = {
                "q": search_query,
                "sort": "stars",
                "order": "desc",
                "per_page": min(max_results * 2, 100),
            }

            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Hermes-Desktop-Stardock-Assembler"
            }

            async with session.get(
                self.GITHUB_SEARCH,
                params=params,
                headers=headers
            ) as resp:
                if resp.status == 403:
                    # 限速，等待后重试
                    await asyncio.sleep(self._rate_limit_delay)
                    return await self._search_github(query, language, max_results)

                if resp.status != 200:
                    return []

                data = await resp.json()
                items = data.get('items', [])

                results = []
                for item in items[:max_results]:
                    repo = self._parse_github_repo(item)
                    if self._is_allowable(repo):
                        results.append(repo)

                return results

        except Exception as e:
            print(f"GitHub search error: {e}")
            return []

    async def _search_gitee(
        self,
        query: str,
        language: Optional[str],
        max_results: int
    ) -> list[RepoInfo]:
        """搜索 Gitee"""
        try:
            session = await self._get_session()

            params = {
                "q": query,
                "sort": "stars_count",
                "order": "desc",
                "page_size": min(max_results * 2, 100),
            }

            if language:
                params["lang"] = language

            async with session.get(
                self.GITEE_SEARCH,
                params=params
            ) as resp:
                if resp.status != 200:
                    return []

                items = await resp.json()

                results = []
                for item in items[:max_results]:
                    repo = self._parse_gitee_repo(item)
                    if self._is_allowable(repo):
                        results.append(repo)

                return results

        except Exception as e:
            print(f"Gitee search error: {e}")
            return []

    def _parse_github_repo(self, item: dict) -> RepoInfo:
        """解析 GitHub 仓库数据"""
        return RepoInfo(
            name=item.get('name', ''),
            full_name=item.get('full_name', ''),
            description=item.get('description', ''),
            url=item.get('html_url', ''),
            stars=item.get('stargazers_count', 0),
            forks=item.get('forks_count', 0),
            language=item.get('language', ''),
            license=License.from_string(item.get('license', {}).get('spdx_id', '')),
            last_updated=item.get('updated_at', ''),
            homepage=item.get('homepage', ''),
            source="github",
        )

    def _parse_gitee_repo(self, item: dict) -> RepoInfo:
        """解析 Gitee 仓库数据"""
        return RepoInfo(
            name=item.get('name', ''),
            full_name=item.get('full_name', ''),
            description=item.get('description', ''),
            url=item.get('html_url', ''),
            stars=item.get('stargazers_count', 0) or item.get('stars', 0),
            forks=item.get('forks_count', 0),
            language=item.get('language', ''),
            license=License.from_string(item.get('license', '')),
            last_updated=item.get('updated_at', ''),
            homepage=item.get('homepage', ''),
            source="gitee",
        )

    def _is_allowable(self, repo: RepoInfo) -> bool:
        """检查许可证是否允许"""
        return repo.license.is_allowable()

    def _rank_results(self, repos: list[RepoInfo]) -> list[RepoInfo]:
        """对结果排序"""

        def calc_activity(repo: RepoInfo) -> float:
            """计算活跃度分数"""
            # 基础分：星数对数
            stars_score = min(10, 2 * (repo.stars ** 0.3) if repo.stars > 0 else 0)
            # 分叉加分
            forks_score = min(5, repo.forks ** 0.4)
            return stars_score + forks_score

        # 计算各维度分数
        for repo in repos:
            repo.activity_score = calc_activity(repo)

        # 综合排序
        def total_score(repo: RepoInfo) -> float:
            return repo.activity_score + repo.match_score

        return sorted(repos, key=total_score, reverse=True)

    def format_repo_display(self, repo: RepoInfo, index: int = 1) -> str:
        """格式化仓库显示"""
        license_icon = "✅" if repo.license.is_allowable() else "⚠️"
        lines = [
            f"{index}. **{repo.name}**",
            f"   📌 {repo.description or '无描述'}",
            f"   ⭐ {repo.stars:,} | 🍴 {repo.forks:,} | {license_icon} {repo.license.value}",
            f"   🔗 {repo.url}",
        ]
        if repo.language:
            lines.append(f"   💻 {repo.language}")
        return '\n'.join(lines)

    async def get_repo_details(self, repo_url: str) -> Optional[RepoInfo]:
        """
        获取仓库详细信息

        Args:
            repo_url: 仓库 URL (GitHub 或 Gitee)

        Returns:
            Optional[RepoInfo]: 仓库详情
        """
        if "github.com" in repo_url:
            return await self._get_github_details(repo_url)
        elif "gitee.com" in repo_url:
            return await self._get_gitee_details(repo_url)
        return None

    async def _get_github_details(self, url: str) -> Optional[RepoInfo]:
        """获取 GitHub 仓库详情"""
        try:
            # 提取 owner/repo
            parts = url.replace("https://github.com/", "").replace("http://github.com/", "").split("/")
            if len(parts) < 2:
                return None
            owner, repo = parts[0], parts[1].replace(".git", "")

            session = await self._get_session()
            api_url = f"{self.GITHUB_API}/repos/{owner}/{repo}"

            headers = {"Accept": "application/vnd.github.v3+json"}

            async with session.get(api_url, headers=headers) as resp:
                if resp.status != 200:
                    return None

                data = await resp.json()
                return self._parse_github_repo(data)

        except Exception:
            return None

    async def _get_gitee_details(self, url: str) -> Optional[RepoInfo]:
        """获取 Gitee 仓库详情"""
        try:
            parts = url.replace("https://gitee.com/", "").replace("http://gitee.com/", "").split("/")
            if len(parts) < 2:
                return None
            owner, repo = parts[0], parts[1].replace(".git", "")

            session = await self._get_session()
            api_url = f"{self.GITEE_API}/repos/{owner}/{repo}"

            async with session.get(api_url) as resp:
                if resp.status != 200:
                    return None

                data = await resp.json()
                return self._parse_gitee_repo(data)

        except Exception:
            return None