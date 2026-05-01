"""
资源感知调度器（ResourceAwareScheduler）

实时监控 GPU/CPU/内存使用，动态调整并发数和模型选择。

功能：
1. 实时资源监控（CPU、内存、GPU）
2. 动态并发数调整
3. 优先级任务队列
4. 自动降级机制
5. 负载均衡优化

作者: LivingTreeAI Team
日期: 2026-04-30
版本: 1.0.0
"""

import asyncio
import logging
import time
import threading
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, Awaitable, Tuple
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class ResourceStatus(Enum):
    """资源状态"""
    IDLE = "idle"           # 空闲
    LOW = "low"             # 低负载
    MEDIUM = "medium"       # 中等负载
    HIGH = "high"           # 高负载
    CRITICAL = "critical"   # 临界


class TaskPriority(Enum):
    """任务优先级"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class ResourceMetrics:
    """资源指标"""
    cpu_usage: float = 0.0          # CPU 使用率 (0-1)
    memory_usage: float = 0.0       # 内存使用率 (0-1)
    gpu_usage: float = 0.0          # GPU 使用率 (0-1)
    gpu_memory_usage: float = 0.0   # GPU 显存使用率 (0-1)
    network_io: float = 0.0         # 网络 IO (MB/s)
    timestamp: float = 0.0          # 时间戳


@dataclass
class ScheduledTask:
    """调度任务"""
    task_id: str
    coroutine: Awaitable
    priority: TaskPriority
    submitted_at: float
    estimated_tokens: int
    required_tier: Optional[str] = None
    context_length: int = 0
    
    def __lt__(self, other):
        """优先级比较（用于优先队列）"""
        return self.priority.value > other.priority.value


class ResourceAwareScheduler:
    """
    资源感知调度器
    
    核心功能：
    1. 实时监控系统资源
    2. 根据资源状态动态调整并发数
    3. 管理优先级任务队列
    4. 实现自动降级机制
    """
    
    def __init__(self, model_router):
        """
        初始化调度器
        
        Args:
            model_router: GlobalModelRouter 实例
        """
        self.model_router = model_router
        
        # 资源监控配置
        self.monitor_interval = 2  # 监控间隔（秒）
        self.history_size = 60     # 历史记录大小
        
        # 当前资源状态
        self.current_metrics = ResourceMetrics()
        self.metrics_history = deque(maxlen=self.history_size)
        
        # 并发控制
        self.max_concurrent = 10
        self.current_concurrent = 0
        self.concurrent_lock = threading.Lock()
        
        # 优先级队列
        self.task_queue = []
        
        # 任务状态追踪
        self.running_tasks = {}  # {task_id: task}
        self.completed_tasks = []
        
        # 自动降级配置
        self.degradation_level = 0  # 0 = 正常, 1-3 = 降级级别
        
        # 监控线程
        self.monitor_thread = None
        self.monitor_stop_event = threading.Event()
        
        # 调度线程
        self.scheduler_thread = None
        self.scheduler_stop_event = threading.Event()
        
        # 统计信息
        self.stats = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "avg_wait_time": 0.0,
            "avg_execution_time": 0.0,
        }
        
        # 启动监控和调度
        self.start_monitor()
        self.start_scheduler()
        
        logger.info("ResourceAwareScheduler 初始化完成")
    
    def start_monitor(self):
        """启动资源监控线程"""
        if self.monitor_thread and self.monitor_thread.is_alive():
            return
        
        self.monitor_stop_event.clear()
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="ResourceMonitor"
        )
        self.monitor_thread.start()
    
    def stop_monitor(self):
        """停止资源监控线程"""
        self.monitor_stop_event.set()
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
    
    def start_scheduler(self):
        """启动调度线程"""
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            return
        
        self.scheduler_stop_event.clear()
        self.scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            daemon=True,
            name="TaskScheduler"
        )
        self.scheduler_thread.start()
    
    def stop_scheduler(self):
        """停止调度线程"""
        self.scheduler_stop_event.set()
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
    
    def _monitor_loop(self):
        """资源监控循环"""
        while not self.monitor_stop_event.is_set():
            self._update_metrics()
            self._check_degradation()
            time.sleep(self.monitor_interval)
    
    def _update_metrics(self):
        """更新资源指标"""
        metrics = ResourceMetrics()
        metrics.timestamp = time.time()
        
        try:
            # CPU 使用率
            try:
                import psutil
                metrics.cpu_usage = psutil.cpu_percent() / 100.0
            except ImportError:
                metrics.cpu_usage = 0.0
            
            # 内存使用率
            try:
                import psutil
                mem = psutil.virtual_memory()
                metrics.memory_usage = mem.percent / 100.0
            except ImportError:
                metrics.memory_usage = 0.0
            
            # GPU 使用率（如果可用）
            try:
                metrics.gpu_usage, metrics.gpu_memory_usage = self._get_gpu_metrics()
            except Exception as e:
                metrics.gpu_usage = 0.0
                metrics.gpu_memory_usage = 0.0
            
            # 网络 IO（简化版）
            try:
                import psutil
                net_io = psutil.net_io_counters()
                metrics.network_io = (net_io.bytes_sent + net_io.bytes_recv) / (1024 * 1024)
            except ImportError:
                metrics.network_io = 0.0
            
        except Exception as e:
            logger.error(f"更新资源指标失败: {e}")
        
        self.current_metrics = metrics
        self.metrics_history.append(metrics)
    
    def _get_gpu_metrics(self) -> Tuple[float, float]:
        """获取 GPU 指标"""
        try:
            import torch
            if torch.cuda.is_available():
                device = torch.cuda.current_device()
                gpu_usage = torch.cuda.utilization(device) / 100.0
                memory_info = torch.cuda.memory_allocated(device) / torch.cuda.max_memory_allocated(device)
                return gpu_usage, min(memory_info, 1.0)
        except Exception:
            pass
        
        return 0.0, 0.0
    
    def _check_degradation(self):
        """检查并更新降级级别"""
        cpu = self.current_metrics.cpu_usage
        mem = self.current_metrics.memory_usage
        gpu = self.current_metrics.gpu_usage
        gpu_mem = self.current_metrics.gpu_memory_usage
        
        # 计算综合负载
        load_score = (cpu * 0.3 + mem * 0.3 + gpu * 0.2 + gpu_mem * 0.2)
        
        # 确定降级级别
        if load_score > 0.9:
            new_level = 3
        elif load_score > 0.75:
            new_level = 2
        elif load_score > 0.6:
            new_level = 1
        else:
            new_level = 0
        
        if new_level != self.degradation_level:
            self.degradation_level = new_level
            logger.info(f"资源状态变化，降级级别: {new_level}")
            self._adjust_concurrent()
    
    def _adjust_concurrent(self):
        """根据降级级别调整并发数"""
        base_concurrent = 10
        
        if self.degradation_level == 3:
            # 严重降级：只允许最小并发
            self.max_concurrent = 2
        elif self.degradation_level == 2:
            # 中等降级：减少并发
            self.max_concurrent = 4
        elif self.degradation_level == 1:
            # 轻度降级：适度减少
            self.max_concurrent = 7
        else:
            # 正常状态
            self.max_concurrent = base_concurrent
        
        logger.info(f"最大并发数已调整为: {self.max_concurrent}")
    
    def _scheduler_loop(self):
        """调度循环"""
        while not self.scheduler_stop_event.is_set():
            self._process_queue()
            time.sleep(0.1)
    
    def _process_queue(self):
        """处理任务队列"""
        with self.concurrent_lock:
            available_slots = self.max_concurrent - self.current_concurrent
        
        if available_slots <= 0:
            return
        
        # 按优先级排序队列
        self.task_queue.sort()
        
        # 处理最高优先级的任务
        while available_slots > 0 and self.task_queue:
            task = self.task_queue.pop(0)
            
            # 检查是否需要降级
            adjusted_tier = self._get_adjusted_tier(task)
            if adjusted_tier:
                task.required_tier = adjusted_tier
            
            # 提交任务
            asyncio.create_task(self._execute_task(task))
            
            available_slots -= 1
    
    def _get_adjusted_tier(self, task: ScheduledTask) -> Optional[str]:
        """根据资源状态调整任务层级"""
        if self.degradation_level == 0:
            return task.required_tier
        
        if not task.required_tier:
            return None
        
        current_num = int(task.required_tier[1:])
        adjusted_num = max(0, current_num - self.degradation_level)
        
        new_tier = f"L{adjusted_num}"
        if new_tier != task.required_tier:
            logger.info(f"降级调整: {task.required_tier} → {new_tier}")
        
        return new_tier
    
    async def _execute_task(self, task: ScheduledTask):
        """执行任务"""
        start_time = time.time()
        
        with self.concurrent_lock:
            self.current_concurrent += 1
            self.running_tasks[task.task_id] = task
        
        try:
            # 执行任务
            await task.coroutine
            
            # 更新统计
            self.stats["completed_tasks"] += 1
            self.stats["avg_execution_time"] = (
                self.stats["avg_execution_time"] * 0.9 + 
                (time.time() - start_time) * 0.1
            )
            
            logger.debug(f"任务完成: {task.task_id}")
            
        except Exception as e:
            self.stats["failed_tasks"] += 1
            logger.error(f"任务失败: {task.task_id}, 错误: {e}")
        
        finally:
            with self.concurrent_lock:
                self.current_concurrent -= 1
                self.running_tasks.pop(task.task_id, None)
            
            # 记录完成任务
            self.completed_tasks.append({
                "task_id": task.task_id,
                "priority": task.priority.value,
                "duration": time.time() - start_time,
                "tier": task.required_tier,
            })
            
            # 限制完成任务记录
            if len(self.completed_tasks) > 1000:
                self.completed_tasks = self.completed_tasks[-500:]
    
    def submit_task(self, task_id: str, coroutine: Awaitable,
                    priority: TaskPriority = TaskPriority.NORMAL,
                    estimated_tokens: int = 0,
                    required_tier: Optional[str] = None,
                    context_length: int = 0) -> bool:
        """
        提交任务到调度队列
        
        Args:
            task_id: 任务ID
            coroutine: 任务协程
            priority: 优先级
            estimated_tokens: 估算token数
            required_tier: 要求的层级
            
        Returns:
            是否提交成功
        """
        task = ScheduledTask(
            task_id=task_id,
            coroutine=coroutine,
            priority=priority,
            submitted_at=time.time(),
            estimated_tokens=estimated_tokens,
            required_tier=required_tier,
            context_length=context_length
        )
        
        self.task_queue.append(task)
        self.stats["total_tasks"] += 1
        
        return True
    
    def get_resource_status(self) -> ResourceStatus:
        """获取当前资源状态"""
        load_score = (
            self.current_metrics.cpu_usage * 0.3 +
            self.current_metrics.memory_usage * 0.3 +
            self.current_metrics.gpu_usage * 0.2 +
            self.current_metrics.gpu_memory_usage * 0.2
        )
        
        if load_score < 0.3:
            return ResourceStatus.IDLE
        elif load_score < 0.5:
            return ResourceStatus.LOW
        elif load_score < 0.7:
            return ResourceStatus.MEDIUM
        elif load_score < 0.9:
            return ResourceStatus.HIGH
        else:
            return ResourceStatus.CRITICAL
    
    def get_scheduler_info(self) -> Dict[str, Any]:
        """获取调度器信息"""
        return {
            "resource_status": self.get_resource_status().value,
            "degradation_level": self.degradation_level,
            "max_concurrent": self.max_concurrent,
            "current_concurrent": self.current_concurrent,
            "queue_size": len(self.task_queue),
            "running_tasks": list(self.running_tasks.keys()),
            "metrics": {
                "cpu_usage": round(self.current_metrics.cpu_usage, 2),
                "memory_usage": round(self.current_metrics.memory_usage, 2),
                "gpu_usage": round(self.current_metrics.gpu_usage, 2),
                "gpu_memory_usage": round(self.current_metrics.gpu_memory_usage, 2),
            },
            "stats": self.stats,
        }
    
    def shutdown(self):
        """关闭调度器"""
        self.stop_monitor()
        self.stop_scheduler()
        logger.info("ResourceAwareScheduler 已关闭")