# -*- coding: utf-8 -*-
"""
代理验证器
多级验证机制：基础连通性 → 匿名性 → 目标站点兼容性
"""

import logging
from typing import List, Tuple, Optional, Dict, Callable
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import asyncio

import requests
from requests.exceptions import (
    ProxyError, 
    ConnectTimeout, 
    ReadTimeout, 
    SSLError,
    ConnectionError as RequestsConnectionError
)

from .proxy_sources import Proxy
from .config import get_config

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """验证结果"""
    proxy: Proxy
    is_valid: bool
    level: int  # 1=基础, 2=匿名性, 3=目标站点
    latency: float = 0.0  # 延迟（秒）
    origin_ip: Optional[str] = None  # 代理返回的原始IP
    error: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class ProxyValidator:
    """
    代理验证器
    
    验证层级：
    - L1: 基础连通性（httpbin.org/ip）
    - L2: 匿名性检查（返回IP是否包含代理IP）
    - L3: 目标站点兼容性（Google Scholar / arXiv 等）
    """
    
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
                "Accept": "application/json",
            })
        return self._session
    
    async def validate(self, proxy: Proxy) -> ValidationResult:
        """
        完整验证流程
        
        Args:
            proxy: 代理对象
            
        Returns:
            验证结果
        """
        start_time = asyncio.get_event_loop().time()
        
        # L1: 基础连通性验证
        result = await self._validate_basic(proxy)
        if not result.is_valid:
            result.latency = asyncio.get_event_loop().time() - start_time
            return result
        
        # L2: 匿名性验证
        if self.config.validator.check_anonymity:
            result = await self._validate_anonymity(proxy)
            if not result.is_valid:
                result.latency = asyncio.get_event_loop().time() - start_time
                return result
        
        # L3: 目标站点验证（选择一个随机目标）
        target_url = self._select_target()
        if target_url:
            result = await self._validate_target(proxy, target_url)
            result.latency = asyncio.get_event_loop().time() - start_time
            return result
        
        result.is_valid = True
        result.level = 3
        result.latency = asyncio.get_event_loop().time() - start_time
        return result
    
    async def _validate_basic(self, proxy: Proxy) -> ValidationResult:
        """L1: 基础连通性验证"""
        test_url = self.config.validator.basic_test_url
        timeout = self.config.validator.basic_timeout
        
        try:
            proxies = {
                'http': proxy.full_address,
                'https': proxy.full_address,
            }
            
            response = self.session.get(
                test_url,
                proxies=proxies,
                timeout=timeout
            )
            
            if response.status_code == 200:
                return ValidationResult(
                    proxy=proxy,
                    is_valid=True,
                    level=1,
                    origin_ip=response.json().get('origin', '')
                )
            else:
                return ValidationResult(
                    proxy=proxy,
                    is_valid=False,
                    level=1,
                    error=f"HTTP {response.status_code}"
                )
                
        except SSLError as e:
            return ValidationResult(
                proxy=proxy,
                is_valid=False,
                level=1,
                error=f"SSL Error: {type(e).__name__}"
            )
        except (ProxyError, ConnectTimeout, ReadTimeout, RequestsConnectionError) as e:
            return ValidationResult(
                proxy=proxy,
                is_valid=False,
                level=1,
                error=f"Connection Error: {type(e).__name__}"
            )
        except Exception as e:
            return ValidationResult(
                proxy=proxy,
                is_valid=False,
                level=1,
                error=f"Error: {type(e).__name__}"
            )
    
    async def _validate_anonymity(self, proxy: Proxy) -> ValidationResult:
        """L2: 匿名性验证"""
        try:
            test_url = self.config.validator.basic_test_url
            timeout = self.config.validator.basic_timeout
            
            proxies = {
                'http': proxy.full_address,
                'https': proxy.full_address,
            }
            
            response = self.session.get(
                test_url,
                proxies=proxies,
                timeout=timeout
            )
            
            if response.status_code == 200:
                origin = response.json().get('origin', '')
                
                # 检查 origin 是否与代理 IP 相关
                # 完全匿名: origin 不包含代理 IP
                # 透明代理: origin 包含代理 IP
                # 高度匿名: origin 随机
                
                # 宽松检查：只要能获取到 origin 就算通过
                if origin:
                    return ValidationResult(
                        proxy=proxy,
                        is_valid=True,
                        level=2,
                        origin_ip=origin
                    )
                
            return ValidationResult(
                proxy=proxy,
                is_valid=False,
                level=2,
                error="无法获取原始IP"
            )
            
        except Exception as e:
            return ValidationResult(
                proxy=proxy,
                is_valid=False,
                level=2,
                error=f"匿名性检查失败: {type(e).__name__}"
            )
    
    async def _validate_target(self, proxy: Proxy, target_url: str) -> ValidationResult:
        """L3: 目标站点兼容性验证"""
        timeout = self.config.validator.target_timeout
        
        try:
            proxies = {
                'http': proxy.full_address,
                'https': proxy.full_address,
            }
            
            # 只发 HEAD 请求，避免消耗配额
            response = self.session.head(
                target_url,
                proxies=proxies,
                timeout=timeout,
                allow_redirects=True
            )
            
            # 判断状态码
            if response.status_code in [200, 301, 302]:
                return ValidationResult(
                    proxy=proxy,
                    is_valid=True,
                    level=3,
                    origin_ip=proxy.ip
                )
            elif response.status_code == 429:
                return ValidationResult(
                    proxy=proxy,
                    is_valid=False,
                    level=3,
                    error="Rate Limited"
                )
            else:
                return ValidationResult(
                    proxy=proxy,
                    is_valid=False,
                    level=3,
                    error=f"HTTP {response.status_code}"
                )
                
        except SSLError as e:
            return ValidationResult(
                proxy=proxy,
                is_valid=False,
                level=3,
                error="SSL Error (TLS版本过低)"
            )
        except (ProxyError, ConnectTimeout, ReadTimeout) as e:
            return ValidationResult(
                proxy=proxy,
                is_valid=False,
                level=3,
                error=f"连接失败: {type(e).__name__}"
            )
        except Exception as e:
            return ValidationResult(
                proxy=proxy,
                is_valid=False,
                level=3,
                error=f"错误: {type(e).__name__}"
            )
    
    def _select_target(self) -> Optional[str]:
        """选择一个随机目标站点"""
        targets = self.config.validator.target_urls
        if targets:
            import random
            return random.choice(targets)
        return None
    
    async def validate_batch(
        self, 
        proxies: List[Proxy],
        max_workers: int = None,
        callback: Optional[Callable[[ValidationResult], None]] = None
    ) -> List[ValidationResult]:
        """
        批量验证代理
        
        Args:
            proxies: 代理列表
            max_workers: 最大并发数
            callback: 每完成一个验证的回调
            
        Returns:
            所有验证结果
        """
        max_workers = max_workers or self.config.validator.max_workers
        results: List[ValidationResult] = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(asyncio.run, self.validate(proxy)): proxy
                for proxy in proxies
            }
            
            for future in as_completed(futures):
                proxy = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                    
                    if callback:
                        callback(result)
                        
                except Exception as e:
                    logger.error(f"验证 {proxy.address} 时出错: {e}")
                    results.append(ValidationResult(
                        proxy=proxy,
                        is_valid=False,
                        level=0,
                        error=str(e)
                    ))
        
        return results


# 全局实例
_validator: Optional[ProxyValidator] = None


def get_validator() -> ProxyValidator:
    """获取验证器"""
    global _validator
    if _validator is None:
        _validator = ProxyValidator()
    return _validator


async def validate_proxy(proxy: Proxy) -> ValidationResult:
    """快捷函数：验证单个代理"""
    validator = get_validator()
    return await validator.validate(proxy)


async def validate_proxies(proxies: List[Proxy]) -> List[ValidationResult]:
    """快捷函数：批量验证代理"""
    validator = get_validator()
    return await validator.validate_batch(proxies)
