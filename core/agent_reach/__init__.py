"""
Agent-Reach 集成模块
为 Hermes Agent 提供免费联网搜索能力

支持的平台:
- Twitter: 搜索推文、读取单条推文
- Reddit: 搜索帖子、读取帖子全文
- GitHub: 搜索仓库、查看仓库详情
- B站: 搜索视频
- 微博: 热搜、搜索内容
- 网页: Jina Reader 读取任意页面
- 全网搜索: Exa 语义搜索 (MCP)
"""

import asyncio
import json
import subprocess
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
import tempfile
import os

# ============================================================================
# 配置
# ============================================================================

AGENT_REACH_REPO = "https://github.com/Panniantong/agent-reach"
INSTALL_URL = "https://raw.githubusercontent.com/Panniantong/agent-reach/main/docs/install.md"


class SearchEngine(Enum):
    """支持的搜索引擎"""
    DUCKDUCKGO = "duckduckgo"
    EXA = "exa"           # 语义搜索 (MCP)
    SEARXNG = "searxng"
    GOOGLE = "google"     # 需要配置


@dataclass
class SearchResult:
    """搜索结果"""
    title: str = ""
    snippet: str = ""
    url: str = ""
    platform: str = ""


@dataclass
class AgentReachConfig:
    """Agent-Reach 配置"""
    binary_path: Optional[Path] = None
    enabled: bool = True
    default_engine: SearchEngine = SearchEngine.EXA
    timeout: int = 30
    max_results: int = 5

    # 各平台登录状态
    twitter_logged_in: bool = False
    reddit_logged_in: bool = False
    xhs_logged_in: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentReachConfig":
        return cls(
            binary_path=Path(data.get("binary_path", "")) if data.get("binary_path") else None,
            enabled=data.get("enabled", True),
            timeout=data.get("timeout", 30),
            max_results=data.get("max_results", 5),
            twitter_logged_in=data.get("twitter_logged_in", False),
            reddit_logged_in=data.get("reddit_logged_in", False),
            xhs_logged_in=data.get("xhs_logged_in", False),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "binary_path": str(self.binary_path) if self.binary_path else "",
            "enabled": self.enabled,
            "timeout": self.timeout,
            "max_results": self.max_results,
            "twitter_logged_in": self.twitter_logged_in,
            "reddit_logged_in": self.reddit_logged_in,
            "xhs_logged_in": self.xhs_logged_in,
        }


# ============================================================================
# 工具类
# ============================================================================

def get_default_path() -> Optional[Path]:
    """获取默认安装路径"""
    # Windows
    path = Path(os.environ.get("LOCALAPPDATA", "")) / "agent-reach" / "agent-reach.exe"
    if path.exists():
        return path

    # macOS / Linux
    for base in ["/usr/local/bin", "/opt/homebrew/bin", Path.home() / ".local" / "bin"]:
        p = Path(base) / "agent-reach"
        if p.exists():
            return p

    # PATH 中查找
    import shutil
    path = shutil.which("agent-reach")
    if path:
        return Path(path)

    return None


async def is_installed() -> bool:
    """检查是否已安装"""
    return get_default_path() is not None


async def run_command(cmd: List[str], timeout: int = 30) -> tuple[int, str, str]:
    """运行命令"""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout
        )
        return proc.returncode, stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace")
    except asyncio.TimeoutError:
        proc.kill()
        return -1, "", "Timeout"
    except Exception as e:
        return -1, "", str(e)


# ============================================================================
# AgentReach 客户端
# ============================================================================

class AgentReachClient:
    """Agent-Reach 客户端"""

    def __init__(self, config: Optional[AgentReachConfig] = None):
        self.config = config or AgentReachConfig()
        self._binary_path: Optional[Path] = self.config.binary_path or get_default_path()

    @property
    def is_available(self) -> bool:
        """检查是否可用"""
        return self._binary_path is not None and self._binary_path.exists()

    async def doctor(self) -> Dict[str, Any]:
        """诊断各渠道状态"""
        if not self.is_available:
            return {
                "installed": False,
                "error": "Agent-Reach not found",
                "suggestion": f"Run: pip install agent-reach && agent-reach install --env=auto"
            }

        code, stdout, stderr = await run_command([str(self._binary_path), "doctor"], timeout=60)
        return {
            "installed": True,
            "binary_path": str(self._binary_path),
            "returncode": code,
            "output": stdout,
            "error": stderr if code != 0 else None
        }

    async def twitter_search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """搜索 Twitter"""
        if not self.is_available:
            return []

        cmd = [str(self._binary_path), "twitter", "search", f'"{query}"']
        code, stdout, stderr = await run_command(cmd, timeout=self.config.timeout)

        if code != 0:
            return []

        return self._parse_twitter_results(stdout)

    async def twitter_read(self, url: str) -> Dict[str, Any]:
        """读取单条推文"""
        if not self.is_available:
            return {"error": "Agent-Reach not available"}

        cmd = [str(self._binary_path), "twitter", "tweet", url]
        code, stdout, stderr = await run_command(cmd, timeout=self.config.timeout)

        return {
            "success": code == 0,
            "content": stdout,
            "error": stderr if code != 0 else None
        }

    async def github_search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """搜索 GitHub 仓库"""
        if not self.is_available:
            return []

        cmd = [str(self._binary_path), "gh", "search", "repos", f'"{query}"']
        code, stdout, stderr = await run_command(cmd, timeout=self.config.timeout)

        if code != 0:
            return []

        return self._parse_github_results(stdout)

    async def github_read(self, repo: str) -> Dict[str, Any]:
        """读取 GitHub 仓库详情"""
        if not self.is_available:
            return {"error": "Agent-Reach not available"}

        cmd = [str(self._binary_path), "gh", "repo", "view", repo]
        code, stdout, stderr = await run_command(cmd, timeout=self.config.timeout)

        return {
            "success": code == 0,
            "content": stdout,
            "error": stderr if code != 0 else None
        }

    async def reddit_search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """搜索 Reddit"""
        if not self.is_available:
            return []

        cmd = [str(self._binary_path), "rdt", "search", f'"{query}"']
        code, stdout, stderr = await run_command(cmd, timeout=self.config.timeout)

        if code != 0:
            return []

        return self._parse_reddit_results(stdout)

    async def bili_search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """搜索 B站视频"""
        if not self.is_available:
            return []

        cmd = [str(self._binary_path), "bili-cli", "search", f'"{query}"']
        code, stdout, stderr = await run_command(cmd, timeout=self.config.timeout)

        if code != 0:
            return []

        return self._parse_bili_results(stdout)

    async def read_url(self, url: str) -> Dict[str, Any]:
        """读取任意网页 (Jina Reader)"""
        # 使用 Jina Reader，无需 Agent-Reach
        jina_url = f"https://r.jina.ai/{url}"

        try:
            proc = await asyncio.create_subprocess_exec(
                "curl", "-s", "-L", "--max-time", "30", jina_url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=35
            )

            content = stdout.decode("utf-8", errors="replace")

            # 解析 Jina AI 格式
            lines = content.split("\n")
            title = ""
            body_start = 0

            for i, line in enumerate(lines):
                if line.startswith("# "):
                    title = line[2:].strip()
                    body_start = i + 1
                    break

            body = "\n".join(lines[body_start:]) if body_start > 0 else content

            return {
                "success": True,
                "title": title,
                "url": url,
                "content": body[:5000],  # 限制长度
                "content_length": len(body)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def general_search(self, query: str, engine: SearchEngine = SearchEngine.EXA) -> Dict[str, Any]:
        """通用搜索（通过 MCP Exa）"""
        if not self.is_available:
            return {
                "error": "Agent-Reach not installed",
                "suggestion": f"pip install agent-reach && agent-reach install --env=auto"
            }

        # Exa 搜索需要通过 MCP，这里返回提示
        return {
            "query": query,
            "engine": engine.value,
            "note": "Exa search requires MCP configuration. Use 'agent-reach install --env=auto' first.",
            "alternative": "Use twitter_search, github_search, or read_url for specific platforms."
        }

    # =========================================================================
    # 解析方法
    # =========================================================================

    def _parse_twitter_results(self, output: str) -> List[SearchResult]:
        """解析 Twitter 搜索结果"""
        results = []
        lines = output.split("\n")

        current = None
        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line.startswith("@"):
                if current:
                    results.append(current)
                current = SearchResult(platform="twitter")
                # 从 URL 提取
                parts = line.split()
                for p in parts:
                    if "twitter.com/" in p or "x.com/" in p:
                        current.url = p

            elif current and not current.title and len(line) > 10:
                current.title = line[:200]
                current.snippet = line[:300]

        if current:
            results.append(current)

        return results[:self.config.max_results]

    def _parse_github_results(self, output: str) -> List[SearchResult]:
        """解析 GitHub 搜索结果"""
        results = []
        lines = output.split("\n")

        current = SearchResult(platform="github")
        for line in lines:
            line = line.strip()
            if not line:
                if current.title:
                    results.append(current)
                current = SearchResult(platform="github")
                continue

            if "/" in line and not line.startswith("#"):
                current.url = f"https://github.com/{line}"
                current.title = line
            elif line and not current.snippet:
                current.snippet = line[:200]

        if current.title:
            results.append(current)

        return results[:self.config.max_results]

    def _parse_reddit_results(self, output: str) -> List[SearchResult]:
        """解析 Reddit 搜索结果"""
        results = []
        lines = output.split("\n")

        for line in lines:
            line = line.strip()
            if "reddit.com/" in line or "r/" in line:
                result = SearchResult(platform="reddit")
                # 提取 URL
                import re
                urls = re.findall(r'https?://[^\s]+', line)
                if urls:
                    result.url = urls[0]
                # 提取标题
                title = re.sub(r'https?://[^\s]+', '', line).strip()
                if title:
                    result.title = title[:200]
                    result.snippet = line[:300]
                results.append(result)

        return results[:self.config.max_results]

    def _parse_bili_results(self, output: str) -> List[SearchResult]:
        """解析 B站搜索结果"""
        results = []
        lines = output.split("\n")

        for line in lines:
            line = line.strip()
            if "bilibili.com/" in line or "b23.tv/" in line:
                result = SearchResult(platform="bilibili")
                import re
                urls = re.findall(r'https?://[^\s]+', line)
                if urls:
                    result.url = urls[0]
                title = re.sub(r'https?://[^\s]+', '', line).strip()
                if title:
                    result.title = title[:200]
                    result.snippet = line[:300]
                results.append(result)

        return results[:self.config.max_results]


# ============================================================================
# 全局单例
# ============================================================================

_global_client: Optional[AgentReachClient] = None


def get_agent_reach(config: Optional[AgentReachConfig] = None) -> AgentReachClient:
    """获取全局 AgentReachClient 实例"""
    global _global_client
    if _global_client is None or config is not None:
        _global_client = AgentReachClient(config)
    return _global_client


# ============================================================================
# 便捷函数
# ============================================================================

async def search(query: str, platform: str = "auto") -> List[SearchResult]:
    """
    统一搜索接口

    Args:
        query: 搜索关键词
        platform: 目标平台 (auto/twitter/github/reddit/bilibili/web)

    Returns:
        搜索结果列表
    """
    client = get_agent_reach()

    if not client.is_available:
        return []

    if platform == "twitter":
        return await client.twitter_search(query)
    elif platform == "github":
        return await client.github_search(query)
    elif platform == "reddit":
        return await client.reddit_search(query)
    elif platform == "bilibili":
        return await client.bili_search(query)
    elif platform == "web":
        return []
    else:
        # 自动选择：优先 GitHub，其次 Twitter
        results = await client.github_search(query)
        if not results:
            results = await client.twitter_search(query)
        return results


async def read_content(url: str) -> Dict[str, Any]:
    """
    读取任意 URL 内容

    Args:
        url: 目标 URL

    Returns:
        页面内容
    """
    client = get_agent_reach()
    return await client.read_url(url)


# ============================================================================
# 安装检测
# ============================================================================

async def check_installation() -> Dict[str, Any]:
    """检查安装状态并返回诊断信息"""
    client = get_agent_reach()

    if client.is_available:
        return await client.doctor()
    else:
        return {
            "installed": False,
            "binary_path": None,
            "error": "Agent-Reach not found in PATH or standard locations",
            "install_command": "pip install agent-reach && agent-reach install --env=auto",
            "install_url": INSTALL_URL
        }
