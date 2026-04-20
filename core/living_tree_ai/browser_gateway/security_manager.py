"""
browser-use 安全管理器

实现域名白名单和权限控制，增强浏览器操作的安全性
"""

import re
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field


@dataclass
class SecurityRule:
    """安全规则"""
    domain: str  # 域名，支持通配符，如 "*.example.com"
    allowed: bool = True  # 是否允许访问
    allowed_actions: Set[str] = field(default_factory=lambda: {"navigate", "extract", "fill_form", "search", "screenshot"})
    comment: Optional[str] = None


class SecurityManager:
    """安全管理器"""
    
    def __init__(self):
        """初始化安全管理器"""
        # 默认规则：允许访问所有域名
        self.rules: List[SecurityRule] = [
            SecurityRule(domain="*", allowed=True, comment="默认规则：允许所有域名")
        ]
        # 内置的危险域名黑名单
        self._blacklisted_domains = {
            "localhost", "127.0.0.1", "0.0.0.0",  # 本地地址
            "file://",  # 文件协议
        }
    
    def add_rule(self, domain: str, allowed: bool = True, allowed_actions: Optional[Set[str]] = None, comment: Optional[str] = None):
        """
        添加安全规则
        
        Args:
            domain: 域名，支持通配符，如 "*.example.com"
            allowed: 是否允许访问
            allowed_actions: 允许的操作类型
            comment: 规则注释
        """
        if allowed_actions is None:
            allowed_actions = {"navigate", "extract", "fill_form", "search", "screenshot"}
        
        # 检查是否已存在相同域名的规则
        for i, rule in enumerate(self.rules):
            if rule.domain == domain:
                # 更新现有规则
                self.rules[i] = SecurityRule(
                    domain=domain,
                    allowed=allowed,
                    allowed_actions=allowed_actions,
                    comment=comment
                )
                return
        
        # 添加新规则
        self.rules.append(SecurityRule(
            domain=domain,
            allowed=allowed,
            allowed_actions=allowed_actions,
            comment=comment
        ))
    
    def add_whitelist(self, domains: List[str]):
        """
        添加白名单域名
        
        Args:
            domains: 域名列表
        """
        for domain in domains:
            self.add_rule(domain, allowed=True, comment="白名单域名")
    
    def add_blacklist(self, domains: List[str]):
        """
        添加黑名单域名
        
        Args:
            domains: 域名列表
        """
        for domain in domains:
            self.add_rule(domain, allowed=False, comment="黑名单域名")
    
    def is_allowed(self, url: str, action: str = "navigate") -> bool:
        """
        检查 URL 是否允许访问
        
        Args:
            url: 要访问的 URL
            action: 操作类型
            
        Returns:
            bool: 是否允许访问
        """
        # 提取域名
        domain = self._extract_domain(url)
        if not domain:
            return False
        
        # 检查内置黑名单
        for blacklisted in self._blacklisted_domains:
            if blacklisted in url:
                return False
        
        # 查找匹配的规则
        matched_rule = None
        for rule in self.rules:
            if self._match_domain(domain, rule.domain):
                matched_rule = rule
                break
        
        # 如果没有匹配的规则，使用默认规则
        if not matched_rule:
            for rule in self.rules:
                if rule.domain == "*":
                    matched_rule = rule
                    break
        
        # 检查是否允许访问
        if not matched_rule or not matched_rule.allowed:
            return False
        
        # 检查操作是否允许
        return action in matched_rule.allowed_actions
    
    def _extract_domain(self, url: str) -> Optional[str]:
        """
        从 URL 中提取域名
        
        Args:
            url: URL
            
        Returns:
            Optional[str]: 域名
        """
        try:
            # 处理 http:// 和 https://
            if url.startswith("http://"):
                url = url[7:]
            elif url.startswith("https://"):
                url = url[8:]
            
            # 提取域名部分
            domain = url.split("/")[0]
            # 移除端口号
            if ":" in domain:
                domain = domain.split(":")[0]
            
            return domain
        except Exception:
            return None
    
    def _match_domain(self, domain: str, pattern: str) -> bool:
        """
        检查域名是否匹配模式
        
        Args:
            domain: 域名
            pattern: 模式，支持通配符
            
        Returns:
            bool: 是否匹配
        """
        # 转换为正则表达式
        regex_pattern = pattern.replace(".", "\\.")
        regex_pattern = regex_pattern.replace("*", ".*")
        regex_pattern = f"^{regex_pattern}$"
        
        return bool(re.match(regex_pattern, domain))
    
    def get_rules(self) -> List[SecurityRule]:
        """
        获取所有安全规则
        
        Returns:
            List[SecurityRule]: 安全规则列表
        """
        return self.rules
    
    def clear_rules(self):
        """
        清除所有规则（保留默认规则）
        """
        self.rules = [
            SecurityRule(domain="*", allowed=True, comment="默认规则：允许所有域名")
        ]


# 全局安全管理器实例
_security_manager: Optional[SecurityManager] = None


def get_security_manager() -> SecurityManager:
    """
    获取安全管理器实例
    
    Returns:
        SecurityManager: 安全管理器实例
    """
    global _security_manager
    if _security_manager is None:
        _security_manager = SecurityManager()
    return _security_manager


def create_security_manager() -> SecurityManager:
    """
    创建安全管理器
    
    Returns:
        SecurityManager: 安全管理器实例
    """
    return SecurityManager()
