"""
性能监控与优化

FPS监控、内存优化、异步更新
from __future__ import annotations
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import threading
import time
import logging
import os

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    psutil = None

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """性能指标"""
    fps: int = 60
    frame_time: float = 0  # ms
    memory_usage: int = 0  # bytes
    memory_percent: float = 0
    cpu_percent: float = 0
    update_count: int = 0
    last_update: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        return {
            "fps": self.fps,
            "frame_time_ms": round(self.frame_time, 2),
            "memory_mb": round(self.memory_usage / 1024 / 1024, 2),
            "memory_percent": round(self.memory_percent, 1),
            "cpu_percent": round(self.cpu_percent, 1),
            "update_count": self.update_count,
        }


class FPSCounter:
    """
    FPS计数器
    
    使用滑动窗口计算实时帧率
    """
    
    def __init__(self, window_size: int = 60):
        self.window_size = window_size
        self._frames: List[float] = []
        self._lock = threading.Lock()
        self._last_time = time.perf_counter()
        self._running = False
        self._current_fps = 60
    
    def start(self):
        self._running = True
        self._last_time = time.perf_counter()
    
    def stop(self):
        self._running = False
    
    def tick(self):
        """记录一帧"""
        if not self._running:
            return
        
        now = time.perf_counter()
        elapsed = (now - self._last_time) * 1000  # 转换为毫秒
        self._last_time = now
        
        with self._lock:
            self._frames.append(elapsed)
            
            # 保持窗口大小
            while len(self._frames) > self.window_size:
                self._frames.pop(0)
            
            # 计算FPS
            if self._frames:
                avg_frame_time = sum(self._frames) / len(self._frames)
                self._current_fps = 1000 / avg_frame_time if avg_frame_time > 0 else 60
    
    def get_fps(self) -> int:
        """获取当前FPS"""
        with self._lock:
            return int(self._current_fps)
    
    def get_frame_time(self) -> float:
        """获取帧时间"""
        with self._lock:
            if self._frames:
                return sum(self._frames) / len(self._frames)
            return 0
    
    def reset(self):
        """重置计数器"""
        with self._lock:
            self._frames.clear()
            self._current_fps = 60


class MemoryOptimizer:
    """
    内存优化器
    
    监控内存使用，支持自动清理
    """
    
    def __init__(self, max_memory_mb: int = 200, cleanup_threshold: float = 0.8):
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.cleanup_threshold = cleanup_threshold
        self._process = None
        if HAS_PSUTIL:
            try:
                self._process = psutil.Process(os.getpid())
            except Exception:
                self._process = None
        self._cache: Dict[str, Any] = {}
        self._cache_access_times: Dict[str, datetime] = {}
        self._max_cache_items = 1000
    
    def get_memory_usage(self) -> int:
        """获取当前内存使用"""
        if self._process is None:
            return 0
        try:
            return self._process.memory_info().rss
        except Exception:
            return 0
    
    def get_memory_percent(self) -> float:
        """获取内存使用百分比"""
        if self._process is None:
            return 0
        try:
            return self._process.memory_percent()
        except Exception:
            return 0
    
    def start(self):
        """启动优化器"""
        pass
    
    def stop(self):
        """停止优化器"""
        pass
    
    def check_memory(self) -> bool:
        """
        检查内存使用
        
        Returns:
            True表示需要清理
        """
        current = self.get_memory_usage()
        return current > self.max_memory_bytes * self.cleanup_threshold
    
    def cleanup(self):
        """执行内存清理"""
        # 清理缓存
        self._cleanup_cache()
        
        # 触发垃圾回收
        import gc
        gc.collect()
        
        logger.info(f"Memory cleaned. Current usage: {self.get_memory_usage() / 1024 / 1024:.2f} MB")
    
    def _cleanup_cache(self):
        """清理缓存"""
        if len(self._cache) <= self._max_cache_items:
            return
        
        # 按访问时间排序
        sorted_items = sorted(
            self._cache_access_times.items(),
            key=lambda x: x[1]
        )
        
        # 删除一半最旧的
        remove_count = len(sorted_items) // 2
        for key, _ in sorted_items[:remove_count]:
            self._cache.pop(key, None)
            self._cache_access_times.pop(key, None)
    
    def cache_set(self, key: str, value: Any):
        """设置缓存"""
        self._cache[key] = value
        self._cache_access_times[key] = datetime.now()
        
        if len(self._cache) > self._max_cache_items:
            self._cleanup_cache()
    
    def cache_get(self, key: str, default: Any = None) -> Any:
        """获取缓存"""
        value = self._cache.get(key, default)
        if key in self._cache_access_times:
            self._cache_access_times[key] = datetime.now()
        return value
    
    def cache_delete(self, key: str):
        """删除缓存"""
        self._cache.pop(key, None)
        self._cache_access_times.pop(key, None)


class AsyncUpdater:
    """
    异步更新器
    
    支持批量更新、优先级调度
    """
    
    def __init__(self, max_concurrent: int = 3):
        self.max_concurrent = max_concurrent
        self._queue: List[tuple[int, Callable, tuple, dict]] = []  # (priority, func, args, kwargs)
        self._running = False
        self._active_count = 0
        self._lock = threading.Lock()
        self._semaphore = threading.Semaphore(max_concurrent)
    
    def start(self):
        self._running = True
    
    def stop(self):
        self._running = False
        with self._lock:
            self._queue.clear()
    
    def add_task(self, func: Callable, priority: int = 0, *args, **kwargs):
        """
        添加异步任务
        
        Args:
            func: 要执行的函数
            priority: 优先级（数字越大优先级越高）
            *args, **kwargs: 函数参数
        """
        with self._lock:
            # 保持优先级顺序
            inserted = False
            for i, (p, _, _, _) in enumerate(self._queue):
                if priority > p:
                    self._queue.insert(i, (priority, func, args, kwargs))
                    inserted = True
                    break
            
            if not inserted:
                self._queue.append((priority, func, args, kwargs))
    
    def _execute_task(self, func: Callable, args: tuple, kwargs: dict):
        """执行任务"""
        try:
            self._active_count += 1
            func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Async task error: {e}")
        finally:
            self._active_count -= 1
            self._semaphore.release()
    
    def execute_next(self) -> bool:
        """
        执行下一个任务
        
        Returns:
            True表示有任务被执行
        """
        if not self._running:
            return False
        
        with self._lock:
            if not self._queue:
                return False
        
        # 获取信号量
        if not self._semaphore.acquire(blocking=False):
            return False
        
        with self._lock:
            if not self._queue:
                self._semaphore.release()
                return False
            
            _, func, args, kwargs = self._queue.pop(0)
        
        thread = threading.Thread(
            target=self._execute_task,
            args=(func, args, kwargs),
            daemon=True
        )
        thread.start()
        
        return True
    
    def get_queue_size(self) -> int:
        """获取队列大小"""
        with self._lock:
            return len(self._queue)
    
    def get_active_count(self) -> int:
        """获取活跃任务数"""
        return self._active_count
    
    def clear(self):
        """清空队列"""
        with self._lock:
            self._queue.clear()


class PerformanceMonitor:
    """
    性能监控器
    
    统一监控系统性能指标
    """
    
    def __init__(self):
        self.fps_counter = FPSCounter()
        self.memory_optimizer = MemoryOptimizer()
        self.async_updater = AsyncUpdater()
        
        self._running = False
        self._metrics = PerformanceMetrics()
        self._listeners: List[Callable] = []
        self._monitor_thread: Optional[threading.Thread] = None
        self._monitor_interval = 1.0  # 秒
    
    def start(self):
        """启动监控"""
        if self._running:
            return
        
        self._running = True
        self.fps_counter.start()
        self.memory_optimizer.start()
        self.async_updater.start()
        
        # 启动监控线程
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
    
    def stop(self):
        """停止监控"""
        if not self._running:
            return
        
        self._running = False
        self.fps_counter.stop()
        self.memory_optimizer.stop()
        self.async_updater.stop()
        
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2)
    
    def _monitor_loop(self):
        """监控循环"""
        while self._running:
            try:
                # 更新FPS
                self._metrics.fps = self.fps_counter.get_fps()
                self._metrics.frame_time = self.fps_counter.get_frame_time()
                
                # 更新内存
                self._metrics.memory_usage = self.memory_optimizer.get_memory_usage()
                self._metrics.memory_percent = self.memory_optimizer.get_memory_percent()
                
                # 更新CPU
                try:
                    self._metrics.cpu_percent = self._metrics.memory_usage  # 简化
                except Exception:
                    pass
                
                self._metrics.last_update = datetime.now()
                
                # 检查内存是否需要清理
                if self.memory_optimizer.check_memory():
                    self.memory_optimizer.cleanup()
                
                # 通知监听器
                for listener in self._listeners:
                    try:
                        listener(self._metrics)
                    except Exception:
                        pass
                
            except Exception as e:
                logger.error(f"Monitor error: {e}")
            
            time.sleep(self._monitor_interval)
    
    def tick(self):
        """记录帧"""
        self.fps_counter.tick()
        self._metrics.update_count += 1
    
    def get_metrics(self) -> PerformanceMetrics:
        """获取当前指标"""
        self._metrics.fps = self.fps_counter.get_fps()
        self._metrics.memory_usage = self.memory_optimizer.get_memory_usage()
        return self._metrics
    
    def subscribe(self, callback: Callable):
        """订阅性能更新"""
        self._listeners.append(callback)
        return lambda: self._listeners.remove(callback)


__all__ = [
    "PerformanceMetrics",
    "FPSCounter",
    "MemoryOptimizer",
    "AsyncUpdater",
    "PerformanceMonitor",
]
