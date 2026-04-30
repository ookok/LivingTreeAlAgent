# -*- coding: utf-8 -*-
"""
统一代理配置中心 - UnifiedProxyConfig
=====================================

设计原则：
1. 一处设置，全局生效 - 所有代理设置集中在一个地方
2. 支持 GitHub 搜索源
3. 简化配置，无需到处设置环境变量

使用方式：
    from business.unified_proxy_config import UnifiedProxyConfig

    # 获取全局实例
    config = UnifiedProxyConfig.get_instance()

    # 设置代理（只需一处）
    config.set_proxy("http://127.0.0.1:7890")

    # 获取代理（所有模块使用同一个代理）
    proxy = config.get_proxy()
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SearchSource(Enum):
    """支持的搜索源"""
    DUCKDUCKGO = "duckduckgo"
    GOOGLE = "google"
    BING = "bing"
    GITHUB = "github"  # 新增 GitHub 搜索
    SEARXNG = "searxng"
    EXA = "exa"


@dataclass
class ProxySource:
    """代理源配置"""
    name: str
    url: str = ""
    enabled: bool = True
    source_type: str = "env"  # env, api, github
    description: str = ""


class UnifiedProxyConfig:
    """
    统一代理配置中心

    核心功能：
    1. 单一代理地址设置
    2. GitHub 搜索源支持
    3. 全局生效，无需多处配置
    """

    _instance: Optional['UnifiedProxyConfig'] = None
    _config_file: Path = Path.home() / ".hermes" / "proxy_config.json"

    def __init__(self):
        self._proxy: Optional[str] = None
        self._enabled_sources: List[SearchSource] = [SearchSource.DUCKDUCKGO, SearchSource.GITHUB]
        self._github_token: Optional[str] = None
        self._load_config()

    @classmethod
    def get_instance(cls) -> 'UnifiedProxyConfig':
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_config(self):
        """从文件加载配置"""
        if self._config_file.exists():
            try:
                config = json.loads(self._config_file.read_text(encoding="utf-8"))
                self._proxy = config.get("proxy")
                self._github_token = config.get("github_token")

                # 加载启用的搜索源
                enabled = config.get("enabled_sources", ["duckduckgo", "github"])
                self._enabled_sources = [
                    SearchSource(s) for s in enabled
                    if s in [e.value for e in SearchSource]
                ]
                if not self._enabled_sources:
                    self._enabled_sources = [SearchSource.DUCKDUCKGO, SearchSource.GITHUB]

                logger.info(f"Loaded proxy config: {self._proxy}")
            except Exception as e:
                logger.error(f"Failed to load proxy config: {e}")

    def _save_config(self):
        """保存配置到文件"""
        try:
            self._config_file.parent.mkdir(parents=True, exist_ok=True)
            config = {
                "proxy": self._proxy,
                "github_token": self._github_token,
                "enabled_sources": [s.value for s in self._enabled_sources]
            }
            self._config_file.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
            logger.info(f"Saved proxy config")
        except Exception as e:
            logger.error(f"Failed to save proxy config: {e}")

    # ==================== 代理设置 ====================

    def set_proxy(self, proxy: Optional[str]):
        """
        设置代理地址（全局唯一入口）

        Args:
            proxy: 代理地址，如 "http://127.0.0.1:7890"
        """
        self._proxy = proxy
        if proxy:
            # 设置系统环境变量（一次性设置，所有模块生效）
            os.environ["HTTP_PROXY"] = proxy
            os.environ["HTTPS_PROXY"] = proxy
            os.environ["http_proxy"] = proxy
            os.environ["https_proxy"] = proxy
            logger.info(f"Proxy set to: {proxy}")
        else:
            # 清除代理
            for key in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
                os.environ.pop(key, None)
            logger.info("Proxy cleared")
        self._save_config()

    def get_proxy(self) -> Optional[str]:
        """获取当前代理地址"""
        return self._proxy

    def is_enabled(self) -> bool:
        """代理是否启用"""
        return bool(self._proxy)

    # ==================== GitHub 配置 ====================

    def set_github_token(self, token: Optional[str]):
        """设置 GitHub Token（用于 API 调用）"""
        self._github_token = token
        if token:
            os.environ["GITHUB_TOKEN"] = token
        else:
            os.environ.pop("GITHUB_TOKEN", None)
        self._save_config()

    def get_github_token(self) -> Optional[str]:
        """获取 GitHub Token"""
        return self._github_token

    # ==================== 搜索源管理 ====================

    def get_enabled_sources(self) -> List[SearchSource]:
        """获取启用的搜索源列表"""
        return self._enabled_sources.copy()

    def enable_source(self, source: SearchSource):
        """启用搜索源"""
        if source not in self._enabled_sources:
            self._enabled_sources.append(source)
            self._save_config()

    def disable_source(self, source: SearchSource):
        """禁用搜索源"""
        if source in self._enabled_sources:
            self._enabled_sources.remove(source)
            self._save_config()

    def set_sources(self, sources: List[SearchSource]):
        """设置搜索源列表"""
        self._enabled_sources = sources.copy()
        self._save_config()

    # ==================== 搜索功能 ====================

    def search_github(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        搜索 GitHub 代码仓库

        Args:
            query: 搜索关键词
            max_results: 最大结果数

        Returns:
            搜索结果列表
        """
        import requests

        url = "https://api.github.com/search/repositories"
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self._github_token:
            headers["Authorization"] = f"token {self._github_token}"

        params = {
            "q": query,
            "per_page": max_results,
            "sort": "stars",
            "order": "desc"
        }

        try:
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=10,
                proxies=self._get_proxies()
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("items", []):
                results.append({
                    "title": item.get("full_name", ""),
                    "snippet": item.get("description", "") or "",
                    "url": item.get("html_url", ""),
                    "platform": "github",
                    "score": item.get("stargazers_count", 0)
                })
            return results

        except requests.RequestException as e:
            logger.error(f"GitHub search failed: {e}")
            return []

    def _get_proxies(self) -> Optional[Dict[str, str]]:
        """获取请求代理"""
        if self._proxy:
            return {
                "http": self._proxy,
                "https": self._proxy
            }
        return None

    # ==================== 通用搜索 ====================

    async def search(
        self,
        query: str,
        engine: SearchSource = SearchSource.DUCKDUCKGO,
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        统一搜索接口

        Args:
            query: 搜索关键词
            engine: 搜索引擎
            max_results: 最大结果数

        Returns:
            搜索结果列表
        """
        if engine == SearchSource.GITHUB:
            return self.search_github(query, max_results)

        # 其他搜索引擎使用 AgentReach
        try:
            from ..agent_reach import AgentReachClient, SearchEngine

            engine_map = {
                SearchSource.DUCKDUCKGO: SearchEngine.DUCKDUCKGO,
                SearchSource.GOOGLE: SearchEngine.GOOGLE,
                SearchSource.BING: SearchEngine.BING,
                SearchSource.SEARXNG: SearchEngine.SEARXNG,
                SearchSource.EXA: SearchEngine.EXA,
            }

            agent_reach = AgentReachClient()
            results = agent_reach.search(
                query=query,
                engine=engine_map.get(engine, SearchEngine.DUCKDUCKGO).value,
                max_results=max_results
            )
            return results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    # ==================== 配置导出 ====================

    def export_env_vars(self) -> Dict[str, str]:
        """导出环境变量（用于其他模块）"""
        env_vars = {}
        if self._proxy:
            env_vars["HTTP_PROXY"] = self._proxy
            env_vars["HTTPS_PROXY"] = self._proxy
            env_vars["http_proxy"] = self._proxy
            env_vars["https_proxy"] = self._proxy
        if self._github_token:
            env_vars["GITHUB_TOKEN"] = self._github_token
        return env_vars

    def get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要"""
        return {
            "proxy": self._proxy,
            "proxy_enabled": self.is_enabled(),
            "enabled_sources": [s.value for s in self._enabled_sources],
            "github_configured": bool(self._github_token)
        }
