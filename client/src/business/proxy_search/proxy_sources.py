# -*- coding: utf-8 -*-
"""
代理源管理
从多个聚合 API 获取代理列表
"""

import re
import logging
from typing import List, Set, Optional, Dict
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio

import requests
from bs4 import BeautifulSoup

from .config import ProxySource, get_config

logger = logging.getLogger(__name__)


@dataclass
class Proxy:
    """代理项"""
    ip: str
    port: int
    protocol: str = "http"
    source: str = ""
    
    @property
    def address(self) -> str:
        """代理地址"""
        return f"{self.ip}:{self.port}"
    
    @property
    def full_address(self) -> str:
        """完整代理地址（带协议）"""
        return f"{self.protocol}://{self.address}"
    
    def __str__(self):
        return self.address
    
    def __hash__(self):
        return hash(self.address)
    
    def __eq__(self, other):
        if isinstance(other, Proxy):
            return self.address == other.address
        return False


class ProxyFetcher:
    """代理获取器"""
    
    def __init__(self):
        self.config = get_config()
        self._session: Optional[requests.Session] = None
    
    @property
    def session(self) -> requests.Session:
        """获取请求会话"""
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({
                "User-Agent": self.config.user_agent,
            })
        return self._session
    
    async def fetch_all(self, max_workers: int = 5) -> List[Proxy]:
        """
        从所有启用的源获取代理
        
        Args:
            max_workers: 最大并发数
            
        Returns:
            代理列表（去重）
        """
        all_proxies: Set[Proxy] = set()
        
        # 并发获取所有源
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._fetch_source, source): source
                for source in self.config.sources
                if source.enabled
            }
            
            for future in as_completed(futures):
                source = futures[future]
                try:
                    proxies = future.result()
                    all_proxies.update(proxies)
                    logger.info(f"从 {source.name} 获取到 {len(proxies)} 个代理")
                except Exception as e:
                    logger.error(f"从 {source.name} 获取失败: {e}")
        
        return list(all_proxies)
    
    def _fetch_source(self, source: ProxySource) -> List[Proxy]:
        """从单个源获取代理"""
        try:
            response = self.session.get(source.url, timeout=source.timeout)
            response.raise_for_status()
            
            content = response.text
            
            # 根据源类型解析
            if "proxyscrape" in source.name:
                return self._parse_proxyscrape(content, source)
            elif "free-proxy-list" in source.name:
                return self._parse_free_proxy_list(content, source)
            elif "89ip" in source.name:
                return self._parse_89ip(content, source)
            elif "spys" in source.name:
                return self._parse_spys(content, source)
            else:
                # 通用纯文本格式（每行 IP:PORT）
                return self._parse_text_format(content, source)
                
        except requests.RequestException as e:
            logger.error(f"请求 {source.name} 失败: {e}")
            return []
        except Exception as e:
            logger.error(f"解析 {source.name} 失败: {e}")
            return []
    
    def _parse_proxyscrape(self, content: str, source: ProxySource) -> List[Proxy]:
        """
        解析 proxyscrape 格式
        格式: IP:PORT[@protocol]
        """
        proxies = []
        for line in content.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # 格式: IP:PORT 或 IP:PORT@protocol
            parts = line.split('@')
            addr_port = parts[0]
            protocol = parts[1] if len(parts) > 1 else source.protocol
            
            if ':' in addr_port:
                try:
                    ip, port = addr_port.split(':')
                    proxies.append(Proxy(
                        ip=ip.strip(),
                        port=int(port.strip()),
                        protocol=protocol,
                        source=source.name
                    ))
                except ValueError:
                    continue
        
        return proxies
    
    def _parse_free_proxy_list(self, content: str, source: ProxySource) -> List[Proxy]:
        """
        解析 free-proxy-list.net HTML 格式
        查找表格中的 IP 和 Port
        """
        proxies = []
        
        try:
            soup = BeautifulSoup(content, 'html.parser')
            
            # 查找表格
            table = soup.find('table', class_='table')
            if not table:
                # 尝试直接查找所有表格
                tables = soup.find_all('table')
                for t in tables:
                    rows = t.find_all('tr')
                    for row in rows[1:]:  # 跳过表头
                        cols = row.find_all(['td', 'th'])
                        if len(cols) >= 2:
                            ip = cols[0].get_text(strip=True)
                            port = cols[1].get_text(strip=True)
                            if self._is_valid_ip(ip) and port.isdigit():
                                proxies.append(Proxy(
                                    ip=ip,
                                    port=int(port),
                                    protocol="http",
                                    source=source.name
                                ))
            else:
                rows = table.find_all('tr')
                for row in rows[1:]:
                    cols = row.find_all('td')
                    if len(cols) >= 2:
                        ip = cols[0].get_text(strip=True)
                        port = cols[1].get_text(strip=True)
                        if self._is_valid_ip(ip) and port.isdigit():
                            proxies.append(Proxy(
                                ip=ip,
                                port=int(port),
                                protocol="http",
                                source=source.name
                            ))
                            
        except Exception as e:
            logger.error(f"解析 HTML 失败: {e}")
            # fallback: 尝试正则匹配 IP:PORT
            proxies.extend(self._parse_text_format(content, source))
        
        return proxies
    
    def _parse_89ip(self, content: str, source: ProxySource) -> List[Proxy]:
        """解析 89ip.cn 格式"""
        proxies = []
        
        try:
            soup = BeautifulSoup(content, 'html.parser')
            
            # 查找包含 IP 和 Port 的行
            text = soup.get_text()
            
            # 格式: IP  \t  PORT
            pattern = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*[：:]\s*(\d+)'
            matches = re.findall(pattern, text)
            
            for ip, port in matches:
                proxies.append(Proxy(
                    ip=ip,
                    port=int(port),
                    protocol="http",
                    source=source.name
                ))
                
        except Exception as e:
            logger.error(f"解析 89ip 失败: {e}")
        
        return proxies
    
    def _parse_spys(self, content: str, source: ProxySource) -> List[Proxy]:
        """解析 spys.one 格式（复杂，需处理 JavaScript）"""
        proxies = []
        
        try:
            soup = BeautifulSoup(content, 'html.parser')
            
            # spys.one 的格式较复杂，尝试多种匹配方式
            # 格式可能包含 JavaScript 编码
            pattern = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)'
            matches = re.findall(pattern, content)
            
            for ip, port in matches:
                proxies.append(Proxy(
                    ip=ip,
                    port=int(port),
                    protocol="http",
                    source=source.name
                ))
                
        except Exception as e:
            logger.error(f"解析 spys 失败: {e}")
        
        return proxies
    
    def _parse_text_format(self, content: str, source: ProxySource) -> List[Proxy]:
        """
        通用纯文本格式解析
        支持格式:
        - IP:PORT
        - IP PORT
        - IP:PORT@protocol
        """
        proxies = []
        
        for line in content.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # 尝试多种格式
            # 格式1: IP:PORT
            match = re.match(r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)', line)
            if match:
                proxies.append(Proxy(
                    ip=match.group(1),
                    port=int(match.group(2)),
                    protocol=source.protocol,
                    source=source.name
                ))
                continue
            
            # 格式2: IP PORT
            match = re.match(r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s+(\d+)', line)
            if match:
                proxies.append(Proxy(
                    ip=match.group(1),
                    port=int(match.group(2)),
                    protocol=source.protocol,
                    source=source.name
                ))
        
        return proxies
    
    @staticmethod
    def _is_valid_ip(ip: str) -> bool:
        """验证 IP 格式"""
        parts = ip.split('.')
        if len(parts) != 4:
            return False
        return all(part.isdigit() and 0 <= int(part) <= 255 for part in parts)


# 全局实例
_fetcher: Optional[ProxyFetcher] = None


def get_fetcher() -> ProxyFetcher:
    """获取代理获取器"""
    global _fetcher
    if _fetcher is None:
        _fetcher = ProxyFetcher()
    return _fetcher


async def fetch_proxies() -> List[Proxy]:
    """快捷函数：获取所有代理"""
    fetcher = get_fetcher()
    return await fetcher.fetch_all()
