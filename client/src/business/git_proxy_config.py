"""
GitProxyConfig - Git代理配置模块
================================

功能：
1. Git全局代理配置
2. GitHub/GitLab白名单代理配置
3. SSH代理配置（用于git@github.com格式）
4. 代理配置导出和导入

使用方式：
    from business.git_proxy_config import GitProxyConfig

    config = GitProxyConfig()

    # 配置全局代理
    config.set_global_proxy("http://127.0.0.1:7890")

    # 配置GitHub白名单代理
    config.add_domain_proxy("github.com", "http://127.0.0.1:7890")

    # 导出配置
    config.export_to_file("~/.gitconfig")
"""

import os
import subprocess
import logging
from typing import Optional, Dict, List
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class DomainProxy:
    """域名代理配置"""
    domain: str
    proxy: str
    enabled: bool = True


class GitProxyConfig:
    """
    Git代理配置管理器

    支持：
    1. 全局代理（所有Git操作）
    2. 域名特定代理（仅对特定域名使用代理）
    3. SSH代理（git@协议）
    """

    def __init__(self, gitconfig_path: Optional[str] = None):
        """
        初始化Git代理配置

        Args:
            gitconfig_path: .gitconfig文件路径，None则使用默认路径
        """
        if gitconfig_path:
            self.gitconfig_path = Path(gitconfig_path)
        else:
            self.gitconfig_path = Path.home() / ".gitconfig"

        self._global_proxy: Optional[str] = None
        self._domain_proxies: Dict[str, DomainProxy] = {}
        self._ssh_config_loaded = False
        self._ssh_proxy: Optional[str] = None
        self._ssh_proxy_domains: List[str] = []

        self._load_config()

    def _load_config(self):
        """加载现有配置"""
        self._load_gitconfig()
        self._load_ssh_config()

    def _load_gitconfig(self):
        """从.gitconfig加载代理配置"""
        if not self.gitconfig_path.exists():
            return

        try:
            content = self.gitconfig_path.read_text(encoding="utf-8")

            # 解析全局代理
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("http.proxy") or line.startswith("https.proxy"):
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        self._global_proxy = parts[1].strip()

                # 解析域名代理
                if "[http \"" in line and "\"]" in line:
                    # 提取域名
                    domain = line.split("\"")[1] if "\"" in line else None
                    # 下一行或当前行可能有proxy配置
                    # 这里简化处理

        except Exception as e:
            logger.error(f"加载.gitconfig失败: {e}")

    def _load_ssh_config(self):
        """从~/.ssh/config加载SSH代理配置"""
        ssh_config = Path.home() / ".ssh" / "config"

        if not ssh_config.exists():
            return

        try:
            current_domain = None
            content = ssh_config.read_text(encoding="utf-8")

            for line in content.split("\n"):
                line = line.strip()

                if line.startswith("Host "):
                    if current_domain and self._ssh_proxy:
                        self._ssh_proxy_domains.append(current_domain)
                    current_domain = line[5:].strip()
                    self._ssh_proxy = None

                elif "ProxyCommand" in line and current_domain:
                    # 检查是否配置了ncat/socat等代理命令
                    if "nc" in line.lower() or "connect" in line.lower():
                        self._ssh_proxy = "socks5"  # 简化处理

            # 最后一个域名
            if current_domain and self._ssh_proxy:
                self._ssh_proxy_domains.append(current_domain)

        except Exception as e:
            logger.error(f"加载SSH配置失败: {e}")

    def set_global_proxy(self, proxy: str):
        """
        设置全局代理

        Args:
            proxy: 代理地址，如 http://127.0.0.1:7890
                   设置为None则清除全局代理
        """
        self._global_proxy = proxy
        logger.info(f"设置Git全局代理: {proxy}")

    def add_domain_proxy(self, domain: str, proxy: str):
        """
        添加域名特定代理

        Args:
            domain: 域名，如 github.com
            proxy: 代理地址
        """
        self._domain_proxies[domain] = DomainProxy(domain=domain, proxy=proxy)
        logger.info(f"添加Git域名代理: {domain} -> {proxy}")

    def remove_domain_proxy(self, domain: str):
        """移除域名代理"""
        if domain in self._domain_proxies:
            del self._domain_proxies[domain]
            logger.info(f"移除Git域名代理: {domain}")

    def set_ssh_proxy(self, proxy: str):
        """
        设置SSH代理（用于git@协议）

        Args:
            proxy: 代理地址，如 socks5://127.0.0.1:1080
        """
        self._ssh_proxy = proxy

        # 确保ssh目录存在
        ssh_dir = Path.home() / ".ssh"
        ssh_dir.mkdir(exist_ok=True)

        logger.info(f"设置SSH代理: {proxy}")

    def enable_github_proxy(self, proxy: str):
        """快捷方法：启用GitHub代理"""
        self.set_global_proxy(proxy)
        self.add_domain_proxy("github.com", proxy)
        self.add_domain_proxy("githubusercontent.com", proxy)

    def enable_huggingface_proxy(self, proxy: str):
        """快捷方法：启用HuggingFace代理"""
        self.add_domain_proxy("huggingface.co", proxy)
        self.add_domain_proxy("hf.co", proxy)

    def enable_gitlab_proxy(self, proxy: str):
        """快捷方法：启用GitLab代理"""
        self.add_domain_proxy("gitlab.com", proxy)
        self.add_domain_proxy("gitlab.org", proxy)

    def export_gitconfig(self) -> str:
        """
        导出Git配置内容

        Returns:
            完整的.gitconfig配置文本
        """
        lines = ["# Git Proxy Configuration", "# Generated by SmartProxyGateway", ""]

        # 全局代理
        if self._global_proxy:
            lines.extend([
                "[http]",
                f"    proxy = {self._global_proxy}",
                "",
                "[https]",
                f"    proxy = {self._global_proxy}",
                ""
            ])

        # 域名代理
        for domain, dp in self._domain_proxies.items():
            if not dp.enabled:
                continue
            lines.extend([
                f"[http \"https://{domain}/\"]",
                f"    proxy = {dp.proxy}",
                ""
            ])

        return "\n".join(lines)

    def export_ssh_config(self) -> str:
        """
        导出SSH配置内容

        Returns:
            SSH配置文本（用于追加到~/.ssh/config）
        """
        if not self._ssh_proxy:
            return ""

        lines = [
            "",
            "# Git SSH Proxy Configuration",
            "# Generated by SmartProxyGateway",
            ""
        ]

        # GitHub SSH
        lines.extend([
            "# GitHub",
            "Host github.com",
            f"    ProxyCommand ncat --proxy {self._ssh_proxy} %h %p",
            ""
        ])

        # GitLab SSH
        lines.extend([
            "# GitLab",
            "Host gitlab.com",
            f"    ProxyCommand ncat --proxy {self._ssh_proxy} %h %p",
            ""
        ])

        return "\n".join(lines)

    def apply_config(self, backup: bool = True) -> bool:
        """
        应用配置到系统

        Args:
            backup: 是否备份现有配置

        Returns:
            是否成功
        """
        try:
            # 备份现有配置
            if backup and self.gitconfig_path.exists():
                backup_path = self.gitconfig_path.with_suffix(".gitconfig.backup")
                self.gitconfig_path.rename(backup_path)
                logger.info(f"备份现有配置到: {backup_path}")

            # 写入新配置
            config_content = self.export_gitconfig()

            # 如果文件存在，追加内容
            if self.gitconfig_path.exists():
                existing = self.gitconfig_path.read_text(encoding="utf-8")
                # 检查是否已经有我们的配置标记
                if "# Generated by SmartProxyGateway" not in existing:
                    config_content = existing + "\n" + config_content

            self.gitconfig_path.write_text(config_content, encoding="utf-8")
            logger.info(f"Git配置已写入: {self.gitconfig_path}")

            # 应用SSH配置
            if self._ssh_proxy:
                self._apply_ssh_config()

            return True

        except Exception as e:
            logger.error(f"应用Git配置失败: {e}")
            return False

    def _apply_ssh_config(self):
        """应用SSH配置"""
        ssh_config = Path.home() / ".ssh" / "config"
        ssh_config_content = self.export_ssh_config()

        if ssh_config_content:
            try:
                existing = ""
                if ssh_config.exists():
                    existing = ssh_config.read_text(encoding="utf-8")
                    if "# Generated by SmartProxyGateway" in existing:
                        # 移除旧配置
                        lines = []
                        skip = False
                        for line in existing.split("\n"):
                            if "# Generated by SmartProxyGateway" in line:
                                skip = True
                                continue
                            if skip and line.strip() == "" and not lines:
                                continue
                            if skip and line.startswith("# Git SSH"):
                                continue
                            if skip and line.startswith("# GitHub"):
                                continue
                            if skip and line.startswith("# GitLab"):
                                continue
                            if skip and line.startswith("Host "):
                                skip = False
                            lines.append(line)
                        existing = "\n".join(lines)

                ssh_config.write_text(existing + ssh_config_content, encoding="utf-8")
                logger.info(f"SSH配置已更新: {ssh_config}")

            except Exception as e:
                logger.error(f"应用SSH配置失败: {e}")

    @staticmethod
    def test_connection(url: str, proxy: Optional[str] = None) -> Dict[str, any]:
        """
        测试Git连接

        Args:
            url: Git仓库URL
            proxy: 可选的代理地址

        Returns:
            测试结果
        """
        import requests

        result = {
            "url": url,
            "success": False,
            "latency": None,
            "error": None,
        }

        try:
            proxies = None
            if proxy:
                proxies = {
                    "http": proxy,
                    "https": proxy,
                }

            import time
            start = time.time()
            response = requests.head(url, proxies=proxies, timeout=10, allow_redirects=True)
            result["latency"] = time.time() - start
            result["success"] = response.status_code < 400
            result["status_code"] = response.status_code

        except Exception as e:
            result["error"] = str(e)

        return result


class GitProxyHelper:
    """
    Git代理助手

    提供快捷方法配置常用Git服务代理
    """

    # 常用Git服务
    GIT_SERVICES = {
        "github": ["github.com", "githubusercontent.com"],
        "gitlab": ["gitlab.com", "gitlab.org"],
        "bitbucket": ["bitbucket.org"],
        "huggingface": ["huggingface.co", "hf.co"],
        "modelscope": ["modelscope.cn"],
        "gitee": ["gitee.com"],
    }

    @classmethod
    def setup_github_proxy(cls, proxy: str, config_path: Optional[str] = None) -> bool:
        """配置GitHub代理"""
        config = GitProxyConfig(config_path)
        config.enable_github_proxy(proxy)
        return config.apply_config()

    @classmethod
    def setup_huggingface_proxy(cls, proxy: str, config_path: Optional[str] = None) -> bool:
        """配置HuggingFace代理"""
        config = GitProxyConfig(config_path)
        config.enable_huggingface_proxy(proxy)
        return config.apply_config()

    @classmethod
    def setup_all_proxy(cls, proxy: str, config_path: Optional[str] = None) -> bool:
        """配置所有常用Git服务代理"""
        config = GitProxyConfig(config_path)
        config.set_global_proxy(proxy)

        for service, domains in cls.GIT_SERVICES.items():
            for domain in domains:
                config.add_domain_proxy(domain, proxy)

        return config.apply_config()

    @classmethod
    def clear_proxy(cls, config_path: Optional[str] = None) -> bool:
        """清除所有代理配置"""
        config = GitProxyConfig(config_path)
        config.set_global_proxy(None)

        for domains in cls.GIT_SERVICES.values():
            for domain in domains:
                config.remove_domain_proxy(domain)

        return config.apply_config()

    @classmethod
    def get_git_urls_needing_proxy(cls) -> List[str]:
        """
        获取需要代理的Git URL列表

        用于UI显示
        """
        urls = []
        for service, domains in cls.GIT_SERVICES.items():
            for domain in domains:
                urls.append(f"https://{domain}/")
                urls.append(f"git@{domain}:")
        return urls
