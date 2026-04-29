"""
browser-use 浏览器会话池

管理浏览器会话的创建、复用和销毁，减少启动开销
"""

import asyncio
import logging
from typing import Dict, Optional, List
from dataclasses import dataclass, field

from browser_use import Browser


@dataclass
class BrowserSession:
    """浏览器会话"""
    browser: Browser
    last_used: float
    in_use: bool = False
    session_id: str = field(default_factory=lambda: str(id(Browser())))


class BrowserPool:
    """浏览器会话池"""
    
    def __init__(
        self,
        max_sessions: int = 5,
        session_timeout: int = 300,  # 5分钟
        use_cloud: bool = False
    ):
        """
        初始化浏览器会话池
        
        Args:
            max_sessions: 最大会话数
            session_timeout: 会话超时时间（秒）
            use_cloud: 是否使用云浏览器
        """
        self.max_sessions = max_sessions
        self.session_timeout = session_timeout
        self.use_cloud = use_cloud
        self.sessions: Dict[str, BrowserSession] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task = None
        self._running = False
    
    async def start(self):
        """启动会话池"""
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_expired_sessions())
    
    async def stop(self):
        """停止会话池"""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # 关闭所有会话
        async with self._lock:
            for session in self.sessions.values():
                try:
                    await session.browser.close()
                except Exception as e:
                    logging.error(f"关闭浏览器会话失败: {e}")
            self.sessions.clear()
    
    async def get_session(self) -> BrowserSession:
        """
        获取一个浏览器会话
        
        Returns:
            BrowserSession: 浏览器会话
        """
        async with self._lock:
            # 查找可用会话
            for session_id, session in self.sessions.items():
                if not session.in_use:
                    session.in_use = True
                    session.last_used = asyncio.get_event_loop().time()
                    return session
            
            # 如果没有可用会话，创建新会话
            if len(self.sessions) < self.max_sessions:
                session = await self._create_session()
                session.in_use = True
                return session
            
            # 如果达到最大会话数，等待可用会话
            return await self._wait_for_available_session()
    
    async def release_session(self, session_id: str):
        """
        释放浏览器会话
        
        Args:
            session_id: 会话 ID
        """
        async with self._lock:
            if session_id in self.sessions:
                session = self.sessions[session_id]
                session.in_use = False
                session.last_used = asyncio.get_event_loop().time()
    
    async def _create_session(self) -> BrowserSession:
        """
        创建新的浏览器会话
        
        Returns:
            BrowserSession: 新创建的浏览器会话
        """
        try:
            browser = Browser(use_cloud=self.use_cloud)
            session = BrowserSession(
                browser=browser,
                last_used=asyncio.get_event_loop().time()
            )
            self.sessions[session.session_id] = session
            logging.info(f"创建新浏览器会话: {session.session_id}")
            return session
        except Exception as e:
            logging.error(f"创建浏览器会话失败: {e}")
            raise
    
    async def _wait_for_available_session(self) -> BrowserSession:
        """
        等待可用会话
        
        Returns:
            BrowserSession: 可用的浏览器会话
        """
        start_time = asyncio.get_event_loop().time()
        timeout = 60  # 60秒超时
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            await asyncio.sleep(1)
            
            async with self._lock:
                for session_id, session in self.sessions.items():
                    if not session.in_use:
                        session.in_use = True
                        session.last_used = asyncio.get_event_loop().time()
                        return session
        
        # 超时后创建新会话（即使超过最大会话数）
        session = await self._create_session()
        session.in_use = True
        return session
    
    async def _cleanup_expired_sessions(self):
        """
        清理过期会话
        """
        while self._running:
            await asyncio.sleep(60)  # 每分钟检查一次
            
            async with self._lock:
                current_time = asyncio.get_event_loop().time()
                expired_sessions = []
                
                for session_id, session in self.sessions.items():
                    if not session.in_use and current_time - session.last_used > self.session_timeout:
                        expired_sessions.append(session_id)
                
                for session_id in expired_sessions:
                    session = self.sessions.pop(session_id)
                    try:
                        await session.browser.close()
                        logging.info(f"清理过期浏览器会话: {session_id}")
                    except Exception as e:
                        logging.error(f"关闭过期浏览器会话失败: {e}")
    
    def get_session_count(self) -> int:
        """
        获取当前会话数
        
        Returns:
            int: 当前会话数
        """
        return len(self.sessions)
    
    def get_available_session_count(self) -> int:
        """
        获取可用会话数
        
        Returns:
            int: 可用会话数
        """
        count = 0
        for session in self.sessions.values():
            if not session.in_use:
                count += 1
        return count


# 全局浏览器会话池实例
_browser_pool: Optional[BrowserPool] = None


def get_browser_pool() -> BrowserPool:
    """
    获取浏览器会话池实例
    
    Returns:
        BrowserPool: 浏览器会话池实例
    """
    global _browser_pool
    if _browser_pool is None:
        _browser_pool = BrowserPool()
        asyncio.create_task(_browser_pool.start())
    return _browser_pool


def create_browser_pool(
    max_sessions: int = 5,
    session_timeout: int = 300,
    use_cloud: bool = False
) -> BrowserPool:
    """
    创建浏览器会话池
    
    Args:
        max_sessions: 最大会话数
        session_timeout: 会话超时时间（秒）
        use_cloud: 是否使用云浏览器
        
    Returns:
        BrowserPool: 浏览器会话池实例
    """
    pool = BrowserPool(
        max_sessions=max_sessions,
        session_timeout=session_timeout,
        use_cloud=use_cloud
    )
    asyncio.create_task(pool.start())
    return pool
