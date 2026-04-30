"""
AppProxyConfig - 应用代理配置模块
================================

功能：
1. 统一代理配置（使用 UnifiedProxyConfig）
2. Models市场白名单（哪些域名需要代理）
3. 搜索源白名单
4. 兼容旧版环境变量配置

设计原则：
- 代理设置只在 workspace panel 的代理源面板一处配置
- 所有模块使用统一的代理地址
- 不再分散设置多个环境变量

使用方式：
    from business.app_proxy_config import AppProxyConfig

    # 获取统一配置实例（单例）
    config = AppProxyConfig.get_instance()

    # 设置代理（只需一处）
    config.set_proxy("http://127.0.0.1:7890")

    # 获取代理（所有模块使用同一个）
    proxy = config.get_proxy()
"""

import os
import json
import logging
from typing import Dict, Optional, List, Any
from dataclasses import dataclass
from pathlib import Path
import shutil

logger = logging.getLogger(__name__)

# 延迟导入统一配置
_UnifiedProxyConfig = None


def _get_unified_config():
    """获取统一配置实例"""
    global _UnifiedProxyConfig
    if _UnifiedProxyConfig is None:
        try:
            from business.unified_proxy_config import UnifiedProxyConfig
            _UnifiedProxyConfig = UnifiedProxyConfig
        except ImportError:
            # 如果统一配置不存在，使用简化实现
            _UnifiedProxyConfig = None
    return _UnifiedProxyConfig


@dataclass
class AppConfig:
    """应用配置"""
    name: str
    config_type: str  # env, file, cli
    proxy_env: Optional[str] = None  # 环境变量名，如 HTTP_PROXY
    no_proxy_env: Optional[str] = None  # NO_PROXY
    config_file: Optional[str] = None  # 配置文件路径
    config_section: Optional[str] = None  # 配置中的section
    cli_command: Optional[str] = None  # CLI配置命令


class AppProxyConfig:
    """
    应用代理配置管理器（简化版）

    设计原则：一处设置，全局生效

    使用统一代理配置（UnifiedProxyConfig），不再分散设置多个环境变量。

    支持的应用类型：
    1. AI/ML服务
       - HuggingFace, OpenRouter, Groq, Anthropic, OpenAI

    2. Skills/MCP市场
       - WorkBuddy Skills, CodeBuddy, MCP Servers

    3. IDE模块（LivingTreeAlAgent智能IDE）
       - LivingTreeAlAgent, Ollama, Models API

    4. 开发工具
       - pip, npm, cargo, go get
    """

    _instance = None

    def __init__(self):
        # 使用统一配置
        unified = _get_unified_config()
        if unified:
            self._unified = unified.get_instance()
        else:
            self._unified = None
            self._proxy: Optional[str] = None

    @classmethod
    def get_instance(cls) -> 'AppProxyConfig':
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def set_proxy(self, proxy: Optional[str]):
        """设置代理地址（统一入口）"""
        if self._unified:
            self._unified.set_proxy(proxy)
        else:
            self._proxy = proxy
            if proxy:
                os.environ["HTTP_PROXY"] = proxy
                os.environ["HTTPS_PROXY"] = proxy
                os.environ["http_proxy"] = proxy
                os.environ["https_proxy"] = proxy
            else:
                for key in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
                    os.environ.pop(key, None)
        logger.info(f"设置应用代理: {proxy}")

    def get_proxy(self) -> Optional[str]:
        """获取代理地址"""
        if self._unified:
            return self._unified.get_proxy()
        return getattr(self, "_proxy", None)

    def is_enabled(self) -> bool:
        """代理是否启用"""
        if self._unified:
            return self._unified.is_enabled()
        return getattr(self, "_proxy", None) is not None

    def export_env_vars(self) -> Dict[str, str]:
        """导出环境变量配置"""
        proxy = self.get_proxy()
        if not proxy:
            return {}

        return {
            "HTTP_PROXY": proxy,
            "HTTPS_PROXY": proxy,
            "http_proxy": proxy,
            "https_proxy": proxy,
        }

    # ── 向后兼容方法 ──────────────────────────────────────────────

    def setup_ai_services_proxy(self, proxy: str):
        """快捷方法：配置AI服务代理（兼容旧代码）"""
        self.set_proxy(proxy)

    def setup_ide_proxy(self, proxy: str):
        """快捷方法：配置IDE模块代理（兼容旧代码）"""
        self.set_proxy(proxy)

    def export_shell_script(self) -> str:
        """导出Shell脚本（兼容旧代码）"""
        proxy = self.get_proxy()
        if not proxy:
            return "# No proxy configured"

        return f"""#!/bin/bash
# Application Proxy Configuration
export HTTP_PROXY="{proxy}"
export HTTPS_PROXY="{proxy}"
export http_proxy="{proxy}"
export https_proxy="{proxy}"
export NO_PROXY="localhost,127.0.0.1,.local"
export no_proxy="localhost,127.0.0.1,.local"
"""

    def export_powershell_script(self) -> str:
        """导出PowerShell脚本（兼容旧代码）"""
        proxy = self.get_proxy()
        if not proxy:
            return "# No proxy configured"

        return f"""# Application Proxy Configuration
$env:HTTP_PROXY = "{proxy}"
$env:HTTPS_PROXY = "{proxy}"
$env:NO_PROXY = "localhost,127.0.0.1,.local"
$env:no_proxy = "localhost,127.0.0.1,.local"
"""

    def apply_vscode_proxy(self, proxy: str) -> bool:
        """应用VSCode代理配置"""
        config_path = Path.home() / ".config" / "Code" / "User" / "settings.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if config_path.exists():
                settings = json.loads(config_path.read_text(encoding="utf-8"))
            else:
                settings = {}

            settings["http.proxy"] = proxy
            settings["http.proxySupport"] = "on"
            settings["http.proxyStrictSSL"] = False

            config_path.write_text(
                json.dumps(settings, indent=4, ensure_ascii=False),
                encoding="utf-8"
            )
            logger.info(f"VSCode代理配置已更新: {config_path}")
            return True

        except Exception as e:
            logger.error(f"VSCode代理配置失败: {e}")
            return False

    def apply_github_cli_proxy(self, proxy: str) -> bool:
        """应用GitHub CLI代理配置"""
        import subprocess

        try:
            result = subprocess.run(
                ["gh", "config", "set", "http.proxy", proxy],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                logger.info("GitHub CLI代理配置成功")
                return True
            else:
                logger.error(f"GitHub CLI代理配置失败: {result.stderr}")
                return False

        except FileNotFoundError:
            logger.error("GitHub CLI未安装")
            return False
        except Exception as e:
            logger.error(f"GitHub CLI代理配置失败: {e}")
            return False

    def get_proxy_script_path(self) -> Path:
        """获取代理脚本路径"""
        script_dir = Path.home() / ".proxy-gateway"
        script_dir.mkdir(exist_ok=True)
        return script_dir


class MarketWhitelist:
    """
    市场白名单

    定义哪些域名需要代理，支持 GitHub 搜索源
    """

    # Models市场
    MODEL_MARKETS = {
        "HuggingFace Models": ["huggingface.co", "hf.co", "models.huggingface.co"],
        "OpenRouter": ["openrouter.ai", "api.openrouter.ai"],
        "Groq": ["groq.com", "api.groq.com"],
        "OpenAI": ["api.openai.com", "openai.com"],
        "Anthropic": ["api.anthropic.com", "anthropic.com"],
        "Cohere": ["api.cohere.ai", "cohere.ai"],
        "Mistral": ["api.mistral.ai", "mistral.ai"],
    }

    # Skills市场
    SKILL_MARKETS = {
        "WorkBuddy Skills": ["workbuddy.com", "codebuddy.cn"],
        "MCP Servers": ["github.com/mcp-servers"],
        "VSCode Marketplace": ["marketplace.visualstudio.com", "open-vsx.org"],
        "JetBrains": ["plugins.jetbrains.com"],
    }

    # IDE插件/API
    IDE_MARKETS = {
        "GitHub API": ["api.github.com", "github.com"],
        "GitLab API": ["gitlab.com/api", "gitlab.org/api"],
        "VSCode Extensions": ["marketplace.visualstudio.com"],
    }

    # 搜索源白名单（新增 GitHub 搜索）
    SEARCH_SOURCES = {
        "GitHub": ["github.com", "api.github.com"],
        "DuckDuckGo": ["duckduckgo.com", "lite.duckduckgo.com"],
        "Google": ["google.com", "googleapis.com"],
        "Bing": ["bing.com", "api.bing.microsoft.com"],
        "SearXNG": ["searx.sh", "searxng.org"],
    }

    @classmethod
    def get_all_domains(cls) -> List[str]:
        """获取所有需要代理的域名"""
        domains = []

        for markets in [cls.MODEL_MARKETS, cls.SKILL_MARKETS, cls.IDE_MARKETS, cls.SEARCH_SOURCES]:
            for market_domains in markets.values():
                domains.extend(market_domains)

        return list(set(domains))

    @classmethod
    def check_url(cls, url: str) -> Optional[str]:
        """检查URL是否在市场白名单中，返回市场名称"""
        import re
        from urllib.parse import urlparse

        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        # 检查搜索源（优先检查）
        for name, domains in cls.SEARCH_SOURCES.items():
            for d in domains:
                if d in domain or domain.endswith(f".{d}"):
                    return name

        # 检查Models市场
        for name, domains in cls.MODEL_MARKETS.items():
            for d in domains:
                if d in domain or domain.endswith(f".{d}"):
                    return name

        # 检查Skills市场
        for name, domains in cls.SKILL_MARKETS.items():
            for d in domains:
                if d in domain or domain.endswith(f".{d}"):
                    return name

        # 检查IDE市场
        for name, domains in cls.IDE_MARKETS.items():
            for d in domains:
                if d in domain or domain.endswith(f".{d}"):
                    return name

        return None

    @classmethod
    def is_github_url(cls, url: str) -> bool:
        """检查是否是 GitHub 相关 URL"""
        return cls.check_url(url) == "GitHub"
