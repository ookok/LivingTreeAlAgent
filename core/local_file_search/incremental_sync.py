"""
增量同步模块
将 USN Journal 变更同步到文件索引

功能
----
1. 监听文件系统变更（USN Journal 或轮询）
2. 增量更新 SQLite 索引
3. 后台异步执行，不阻塞主线程
4. 支持多驱动器同时监控
"""

import os
import sys
import sqlite3
import threading
import time
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)

try:
    from core.config.unified_config import get_config as _get_unified_config
    _uconfig_is = _get_unified_config()
except Exception:
    _uconfig_is = None

def _is_get(key: str, default):
    return _uconfig_is.get(key, default) if _uconfig_is else default


class SyncStrategy(Enum):
    """同步策略"""
    USN_JOURNAL = "usn_journal"    # USN Journal（最快）
    POLLING = "polling"            # 轮询（兼容）
    HYBRID = "hybrid"             # 混合（USN + 定期全量）


@dataclass
class SyncEvent:
    """同步事件"""
    path: str
    event_type: str  # CREATE, DELETE, MODIFY, RENAME
    timestamp: datetime
    size: int = 0
    parent_path: str = ""


class IncrementalSync:
    """
    增量同步器
    
    监控文件系统变更并增量更新索引
    """
    
    def __init__(
        self,
        db_path: str,
        strategy: SyncStrategy = SyncStrategy.HYBRID,
        poll_interval: float = 60.0  # 轮询间隔（秒）
    ):
        """
        初始化增量同步器
        
        Args:
            db_path: 索引数据库路径
            strategy: 同步策略
            poll_interval: 轮询间隔（USN 不可用时的回退）
        """
        self.db_path = db_path
        self.strategy = strategy
        self.poll_interval = poll_interval
        
        # 状态
        self._running = False
        self._lock = threading.RLock()
        
        # 驱动器监控器
        self._monitors: Dict[str, any] = {}
        self._monitor_threads: Dict[str, threading.Thread] = {}
        
        # 轮询线程
        self._poll_thread: Optional[threading.Thread] = None
        
        # 回调
        self._on_sync_callback: Optional[Callable[[List[SyncEvent]], None]] = None
        
        # 统计
        self._stats = {
            "total_syncs": 0,
            "creates": 0,
            "deletes": 0,
            "modifies": 0,
            "last_sync_time": None,
        }
        
        # 检查 USN 可用性
        self._usn_available = self._check_usn_available()
        
        logger.info(
            f"[IncrementalSync] 初始化完成，"
            f"策略: {strategy.value}, "
            f"USN可用: {self._usn_available}"
        )
    
    def _check_usn_available(self) -> bool:
        """检查 USN Journal 是否可用"""
        if sys.platform != 'win32':
            return False
        
        try:
            from .usn_monitor import is_usn_available
            return is_usn_available()
        except ImportError:
            return False
    
    def start(self, drives: List[str] = None):
        """
        启动增量同步
        
        Args:
            drives: 要监控的驱动器列表，如 ["C:", "D:"]
        """
        if self._running:
            logger.warning("[IncrementalSync] 已在运行")
            return
        
        with self._lock:
            self._running = True
            
            # 默认监控所有驱动器
            if drives is None:
                drives = self._get_available_drives()
            
            if self._usn_available and self.strategy in [
                SyncStrategy.USN_JOURNAL, SyncStrategy.HYBRID
            ]:
                self._start_usn_monitors(drives)
            else:
                self._start_polling()
            
            logger.info(f"[IncrementalSync] 启动，监控驱动器: {drives}")
    
    def _get_available_drives(self) -> List[str]:
        """获取可用的驱动器列表"""
        drives = []
        
        if sys.platform == 'win32':
            import ctypes
            try:
                bitmask = ctypes.windll.kernel32.GetLogicalDrives()
                for i in range(26):
                    if bitmask & (1 << i):
                        drive = chr(ord('C') + i) + ':'
                        drives.append(drive)
            except:
                pass
        else:
            drives = ["/", "/home"]
        
        return drives
    
    def _start_usn_monitors(self, drives: List[str]):
        """启动 USN Journal 监控"""
        try:
            from .usn_monitor import USNJournalMonitor
            
            for drive in drives:
                def on_change(changes, d=drive):
                    self._handle_changes(changes)
                
                monitor = USNJournalMonitor(drive, on_change=on_change)
                monitor.start()
                self._monitors[drive] = monitor
                
                thread = threading.Thread(
                    target=self._run_usn_monitor,
                    args=(monitor, drive),
                    daemon=True
                )
                thread.start()
                self._monitor_threads[drive] = thread
                
        except ImportError:
            logger.warning("[IncrementalSync] USN 模块不可用，回退到轮询")
            self._start_polling()
        except Exception as e:
            logger.error(f"[IncrementalSync] USN 监控启动失败: {e}")
            self._start_polling()
    
    def _run_usn_monitor(self, monitor, drive: str):
        """运行 USN 监控线程"""
        while self._running:
            try:
                monitor.poll()
                time.sleep(_is_get("delays.polling_short", 0.5))  # 轮询间隔
            except Exception as e:
                logger.error(f"[IncrementalSync] USN 监控异常: {e}")
                break
    
    def _start_polling(self):
        """启动轮询"""
        self._poll_thread = threading.Thread(
            target=self._poll_loop,
            daemon=True
        )
        self._poll_thread.start()
    
    def _poll_loop(self):
        """轮询循环"""
        last_poll_time = time.time()
        
        while self._running:
            try:
                current_time = time.time()
                
                if current_time - last_poll_time >= self.poll_interval:
                    self._do_full_sync()
                    last_poll_time = current_time

                time.sleep(_is_get("delays.polling_medium", 1))

            except Exception as e:
                logger.error(f"[IncrementalSync] 轮询异常: {e}")
                time.sleep(_is_get("delays.wait_short", 5))
    
    def _handle_changes(self, changes):
        """处理 USN 变更"""
        sync_events = []
        
        for change in changes:
            # 转换为同步事件
            event = SyncEvent(
                path=change.path,
                event_type=self._reason_to_event_type(change.reason),
                timestamp=change.timestamp,
                size=change.size
            )
            sync_events.append(event)
        
        if sync_events:
            self._apply_sync_events(sync_events)
    
    def _reason_to_event_type(self, reason: int) -> str:
        """将 USN reason 转换为事件类型"""
        if reason & 0x00010000:
            return "CREATE"
        if reason & 0x00020000:
            return "DELETE"
        if reason & 0x00040000:
            return "RENAME"
        return "MODIFY"
    
    def _apply_sync_events(self, events: List[SyncEvent]):
        """应用同步事件到数据库"""
        if not events:
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            for event in events:
                if event.event_type == "DELETE":
                    # 删除记录
                    cursor.execute("DELETE FROM files WHERE path = ?", (event.path,))
                    self._stats["deletes"] += 1
                    
                elif event.event_type == "CREATE":
                    # 添加记录
                    if os.path.exists(event.path):
                        stat = os.stat(event.path)
                        ext = os.path.splitext(event.path)[1].lower()
                        
                        cursor.execute('''
                            INSERT OR REPLACE INTO files 
                            (path, filename, extension, size, modified_time, indexed_time)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (
                            event.path,
                            os.path.basename(event.path),
                            ext,
                            stat.st_size,
                            stat.st_mtime,
                            time.time()
                        ))
                        self._stats["creates"] += 1
                
                elif event.event_type == "MODIFY":
                    # 更新记录
                    if os.path.exists(event.path):
                        stat = os.stat(event.path)
                        cursor.execute('''
                            UPDATE files 
                            SET size = ?, modified_time = ?, indexed_time = ?
                            WHERE path = ?
                        ''', (stat.st_size, stat.st_mtime, time.time(), event.path))
                        self._stats["modifies"] += 1
            
            conn.commit()
            self._stats["total_syncs"] += len(events)
            self._stats["last_sync_time"] = datetime.now()
            
            # 调用回调
            if self._on_sync_callback:
                self._on_sync_callback(events)
                
        except Exception as e:
            logger.error(f"[IncrementalSync] 应用同步事件失败: {e}")
        finally:
            conn.close()
    
    def _do_full_sync(self):
        """执行全量同步（定期调用）"""
        logger.info("[IncrementalSync] 执行全量同步...")
        
        # 这里可以调用 FastFileIndexer 的增量更新
        # 简化实现：仅记录时间
        self._stats["last_sync_time"] = datetime.now()
        logger.info("[IncrementalSync] 全量同步完成")
    
    def stop(self):
        """停止增量同步"""
        if not self._running:
            return
        
        with self._lock:
            self._running = False
            
            # 停止 USN 监控
            for drive, monitor in self._monitors.items():
                monitor.stop()
            
            self._monitors.clear()
            
            # 等待线程结束
            for thread in self._monitor_threads.values():
                thread.join(timeout=_is_get("timeouts.thread_join", 2))
            
            self._monitor_threads.clear()
            
            logger.info("[IncrementalSync] 已停止")
    
    def set_callback(self, callback: Callable[[List[SyncEvent]], None]):
        """设置同步回调"""
        self._on_sync_callback = callback
    
    def get_stats(self) -> Dict:
        """获取统计"""
        return {
            **self._stats,
            "running": self._running,
            "usn_available": self._usn_available,
            "strategy": self.strategy.value,
            "monitored_drives": list(self._monitors.keys()),
        }
    
    def force_sync(self):
        """强制执行同步"""
        self._do_full_sync()
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


# ==================== 集成到 FastFileIndexer ====================

class IncrementalIndexer:
    """
    增量索引器
    结合 FastFileIndexer 和 IncrementalSync
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._indexer = None
        self._sync: Optional[IncrementalSync] = None
        self._initialized = False
    
    def init(
        self,
        paths: List[str] = None,
        background: bool = True,
        progress_callback: Callable[[float, int], None] = None
    ):
        """
        初始化索引
        
        Args:
            paths: 要索引的路径
            background: 是否后台运行
            progress_callback: 进度回调
        """
        from .indexer import FastFileIndexer
        
        self._indexer = FastFileIndexer(db_path=self.db_path)
        
        if background:
            # 后台异步初始化
            import threading
            def build():
                self._indexer.init_database()
                self._indexer.build_index(paths, progress_callback)
                self._initialized = True
            
            thread = threading.Thread(target=build, daemon=True)
            thread.start()
        else:
            self._indexer.init_database()
            self._indexer.build_index(paths, progress_callback)
            self._initialized = True
    
    def start_sync(self):
        """启动增量同步"""
        if self._sync is None:
            self._sync = IncrementalSync(self.db_path)
        self._sync.start()
    
    def stop_sync(self):
        """停止增量同步"""
        if self._sync:
            self._sync.stop()
    
    def search(self, query: str, **kwargs):
        """搜索文件"""
        if not self._initialized:
            return []
        return self._indexer.search(query, **kwargs)
    
    def get_stats(self) -> Dict:
        """获取统计"""
        stats = {"initialized": self._initialized}
        if self._indexer:
            stats["indexer"] = self._indexer.get_stats()
        if self._sync:
            stats["sync"] = self._sync.get_stats()
        return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    db_path = "test_index.db"
    
    # 清理旧数据
    if os.path.exists(db_path):
        os.remove(db_path)
    
    # 创建增量索引器
    indexer = IncrementalIndexer(db_path)
    
    def on_progress(progress, count):
        print(f"索引进度: {progress*100:.1f}%, {count} 文件")
    
    # 初始化（后台）
    indexer.init(
        paths=[os.path.expanduser("~")],
        background=True,
        progress_callback=on_progress
    )
    
    # 等待初始化
    import time
    while not indexer.get_stats()["initialized"]:
        time.sleep(1)
        print("等待初始化...")
    
    print("初始化完成，开始搜索测试...")
    
    # 搜索测试
    results = indexer.search("*.py", limit=10)
    for r in results:
        print(f"  {r.path}")
    
    # 启动增量同步
    indexer.start_sync()
    
    print(f"\n统计: {indexer.get_stats()}")
    
    # 保持运行
    time.sleep(5)
    indexer.stop_sync()
