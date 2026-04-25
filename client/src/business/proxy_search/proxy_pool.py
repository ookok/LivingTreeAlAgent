# -*- coding: utf-8 -*-
"""
代理池管理
维护可用代理队列，支持自动刷新和淘汰
"""

import logging
import asyncio
import random
import threading
from typing import List, Optional, Set, Dict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from .proxy_sources import Proxy, ProxyFetcher, fetch_proxies, get_fetcher
from .validator import ProxyValidator, ValidationResult, get_validator
from .config import get_config

logger = logging.getLogger(__name__)


@dataclass
class PooledProxy:
    """池中代理"""
    proxy: Proxy
    failure_count: int = 0
    last_failure: Optional[datetime] = None
    last_success: datetime = field(default_factory=datetime.now)
    success_count: int = 0
    avg_latency: float = 0.0
    validation_level: int = 0
    
    def is_healthy(self) -> bool:
        """检查是否健康"""
        config = get_config()
        
        # 检查失败次数
        if self.failure_count >= config.pool.max_failures:
            return False
        
        # 检查失败窗口
        if self.last_failure:
            window = datetime.now() - self.last_failure
            if window.total_seconds() > config.pool.failure_window:
                # 重置失败计数
                self.failure_count = max(0, self.failure_count - 1)
        
        return True
    
    def record_success(self, latency: float = 0.0):
        """记录成功"""
        self.success_count += 1
        self.last_success = datetime.now()
        self.failure_count = max(0, self.failure_count - 1)
        
        # 更新平均延迟
        if latency > 0:
            self.avg_latency = (self.avg_latency * (self.success_count - 1) + latency) / self.success_count
    
    def record_failure(self):
        """记录失败"""
        self.failure_count += 1
        self.last_failure = datetime.now()
    
    @property
    def score(self) -> float:
        """综合评分"""
        # 成功率权重
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.5
        
        success_rate = self.success_count / total
        
        # 延迟权重（越低越好）
        latency_score = max(0, 1 - self.avg_latency / 10) if self.avg_latency > 0 else 0.5
        
        # 验证级别权重
        level_score = self.validation_level / 3
        
        return success_rate * 0.6 + latency_score * 0.2 + level_score * 0.2


class ProxyPool:
    """
    代理池
    
    功能：
    - 自动从多个源获取代理
    - 多级验证
    - 自动淘汰不健康代理
    - 按评分排序
    - 定时刷新
    """
    
    def __init__(self):
        self.config = get_config()
        self._proxies: Dict[str, PooledProxy] = {}
        self._fetcher = get_fetcher()
        self._validator = get_validator()
        self._lock = threading.Lock()
        
        self._is_refreshing = False
        self._refresh_task: Optional[asyncio.Task] = None
        self._last_refresh: Optional[datetime] = None
    
    @property
    def proxies(self) -> List[PooledProxy]:
        """获取所有代理"""
        with self._lock:
            return list(self._proxies.values())
    
    @property
    def healthy_proxies(self) -> List[PooledProxy]:
        """获取健康代理"""
        with self._lock:
            return [p for p in self._proxies.values() if p.is_healthy()]
    
    @property
    def size(self) -> int:
        """代理池大小"""
        with self._lock:
            return len(self._proxies)
    
    @property
    def healthy_size(self) -> int:
        """健康代理数量"""
        return len(self.healthy_proxies)
    
    async def initialize(self, min_size: int = None):
        """
        初始化代理池
        
        Args:
            min_size: 最小需要的代理数量
        """
        min_size = min_size or self.config.pool.min_pool_size
        
        logger.info("初始化代理池...")
        
        # 获取代理
        raw_proxies = await fetch_proxies()
        logger.info(f"获取到 {len(raw_proxies)} 个原始代理")
        
        if not raw_proxies:
            logger.warning("未获取到任何代理")
            return
        
        # 验证代理
        logger.info("开始验证代理...")
        
        def validation_callback(result: ValidationResult):
            if result.is_valid:
                self.add_proxy(result.proxy, validation_level=result.level)
        
        results = await self._validator.validate_batch(
            raw_proxies,
            callback=validation_callback
        )
        
        # 统计
        valid_count = sum(1 for r in results if r.is_valid)
        logger.info(f"验证完成：{valid_count}/{len(raw_proxies)} 有效")
        
        self._last_refresh = datetime.now()
    
    async def refresh(self, force: bool = False):
        """
        刷新代理池
        
        Args:
            force: 是否强制刷新
        """
        if self._is_refreshing:
            logger.info("刷新已在进行中，跳过")
            return
        
        self._is_refreshing = True
        
        try:
            logger.info("开始刷新代理池...")
            
            # 检查是否需要刷新
            if not force and self.healthy_size >= self.config.pool.min_pool_size:
                logger.info(f"健康代理数量 {self.healthy_size} >= 最小要求 {self.config.pool.min_pool_size}，跳过刷新")
                return
            
            # 获取新代理
            raw_proxies = await fetch_proxies()
            
            # 只验证新的代理
            existing_addrs = {p.proxy.address for p in self.proxies}
            new_proxies = [p for p in raw_proxies if p.address not in existing_addrs]
            
            logger.info(f"发现 {len(new_proxies)} 个新代理")
            
            if new_proxies:
                # 验证
                for result in await self._validator.validate_batch(new_proxies):
                    if result.is_valid:
                        self.add_proxy(result.proxy, validation_level=result.level)
            
            # 清理不健康的代理
            self._cleanup_unhealthy()
            
            self._last_refresh = datetime.now()
            logger.info(f"刷新完成：当前 {self.size} 个代理，{self.healthy_size} 个健康")
            
        except Exception as e:
            logger.error(f"刷新代理池失败: {e}")
        finally:
            self._is_refreshing = False
    
    def add_proxy(self, proxy: Proxy, validation_level: int = 0):
        """添加代理到池中"""
        with self._lock:
            if proxy.address in self._proxies:
                # 更新现有代理
                pooled = self._proxies[proxy.address]
                pooled.validation_level = max(pooled.validation_level, validation_level)
                pooled.record_success()
            else:
                # 添加新代理
                if len(self._proxies) < self.config.pool.max_pool_size:
                    self._proxies[proxy.address] = PooledProxy(
                        proxy=proxy,
                        validation_level=validation_level
                    )
    
    def get_proxy(self) -> Optional[PooledProxy]:
        """
        获取一个可用代理（按评分随机）
        
        Returns:
            池中代理，如果无可用则返回 None
        """
        healthy = self.healthy_proxies
        
        if not healthy:
            return None
        
        # 按评分加权随机选择
        scores = [p.score for p in healthy]
        total_score = sum(scores)
        
        if total_score == 0:
            return random.choice(healthy)
        
        weights = [s / total_score for s in scores]
        return random.choices(healthy, weights=weights)[0]
    
    def record_proxy_success(self, proxy: Proxy, latency: float = 0.0):
        """记录代理使用成功"""
        with self._lock:
            if proxy.address in self._proxies:
                self._proxies[proxy.address].record_success(latency)
    
    def record_proxy_failure(self, proxy: Proxy):
        """记录代理使用失败"""
        with self._lock:
            if proxy.address in self._proxies:
                self._proxies[proxy.address].record_failure()
                
                # 如果失败次数过多，移除
                pooled = self._proxies[proxy.address]
                if pooled.failure_count >= self.config.pool.max_failures * 2:
                    del self._proxies[proxy.address]
                    logger.info(f"移除失败代理: {proxy.address}")
    
    def remove_proxy(self, proxy: Proxy):
        """移除代理"""
        with self._lock:
            if proxy.address in self._proxies:
                del self._proxies[proxy.address]
    
    def _cleanup_unhealthy(self):
        """清理不健康的代理"""
        with self._lock:
            unhealthy = [
                addr for addr, p in self._proxies.items()
                if not p.is_healthy()
            ]
            
            for addr in unhealthy:
                del self._proxies[addr]
            
            if unhealthy:
                logger.info(f"清理了 {len(unhealthy)} 个不健康代理")
    
    async def start_auto_refresh(self):
        """启动自动刷新"""
        if self._refresh_task and not self._refresh_task.done():
            logger.info("自动刷新已在运行")
            return
        
        async def _auto_refresh_loop():
            while True:
                try:
                    await asyncio.sleep(self.config.pool.refresh_interval)
                    await self.refresh()
                    
                    # 如果代理数量不足，尝试强制刷新
                    if self.healthy_size < self.config.pool.min_pool_size:
                        logger.warning(f"健康代理数量不足，强制刷新")
                        await self.refresh(force=True)
                        
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"自动刷新出错: {e}")
        
        self._refresh_task = asyncio.create_task(_auto_refresh_loop())
        logger.info(f"启动自动刷新，间隔 {self.config.pool.refresh_interval} 秒")
    
    async def stop_auto_refresh(self):
        """停止自动刷新"""
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
            self._refresh_task = None
            logger.info("停止自动刷新")
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        healthy = self.healthy_proxies
        
        total_success = sum(p.success_count for p in self.proxies)
        total_failure = sum(p.failure_count for p in self.proxies)
        
        avg_latency = 0
        if healthy:
            latencies = [p.avg_latency for p in healthy if p.avg_latency > 0]
            if latencies:
                avg_latency = sum(latencies) / len(latencies)
        
        return {
            "total_proxies": self.size,
            "healthy_proxies": len(healthy),
            "total_success": total_success,
            "total_failure": total_failure,
            "avg_latency": avg_latency,
            "last_refresh": self._last_refresh.isoformat() if self._last_refresh else None,
            "is_refreshing": self._is_refreshing,
        }


# 全局实例
_pool: Optional[ProxyPool] = None


def get_proxy_pool() -> ProxyPool:
    """获取代理池"""
    global _pool
    if _pool is None:
        _pool = ProxyPool()
    return _pool


async def initialize_pool(min_size: int = None) -> ProxyPool:
    """初始化并获取代理池"""
    pool = get_proxy_pool()
    await pool.initialize(min_size)
    return pool
