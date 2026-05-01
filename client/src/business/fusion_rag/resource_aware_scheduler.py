"""
资源感知调度器 (Resource-Aware Scheduler)
==========================================

实现基于系统资源状态的智能调度：
1. CPU/内存/GPU 监控
2. 资源阈值检测
3. 基于资源状态的模块选择
4. 自动降级策略

作者: LivingTreeAI Team
日期: 2026-04-30
版本: 1.0.0
"""

import asyncio
import psutil
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger


class ResourceStatus(Enum):
    """资源状态"""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class ResourceInfo:
    """资源信息"""
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    gpu_available: bool = False
    gpu_memory_usage: float = 0.0
    disk_usage: float = 0.0
    
    @property
    def overall_status(self) -> ResourceStatus:
        """获取整体资源状态"""
        if self.cpu_usage > 90 or self.memory_usage > 90 or self.disk_usage > 90:
            return ResourceStatus.CRITICAL
        if self.cpu_usage > 70 or self.memory_usage > 70 or self.disk_usage > 70:
            return ResourceStatus.WARNING
        return ResourceStatus.NORMAL


class ResourceMonitor:
    """资源监控器"""
    
    def __init__(self, check_interval: int = 5):
        """
        初始化资源监控器
        
        Args:
            check_interval: 检查间隔（秒）
        """
        self._check_interval = check_interval
        self._current_resources = ResourceInfo()
        self._monitor_task = None
        self._running = False
        
    async def start(self):
        """启动监控"""
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("[ResourceMonitor] 资源监控器已启动")
        
    async def stop(self):
        """停止监控"""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
        logger.info("[ResourceMonitor] 资源监控器已停止")
        
    async def _monitor_loop(self):
        """监控循环"""
        while self._running:
            await self._update_resources()
            await asyncio.sleep(self._check_interval)
            
    async def _update_resources(self):
        """更新资源信息"""
        try:
            # CPU 使用率
            self._current_resources.cpu_usage = psutil.cpu_percent(interval=0.1)
            
            # 内存使用率
            memory = psutil.virtual_memory()
            self._current_resources.memory_usage = memory.percent
            
            # 磁盘使用率
            disk = psutil.disk_usage('/')
            self._current_resources.disk_usage = disk.percent
            
            # GPU 检测（简化版）
            try:
                import GPUtil
                gpus = GPUtil.getGPUs()
                if gpus:
                    self._current_resources.gpu_available = True
                    self._current_resources.gpu_memory_usage = (1 - gpus[0].memoryFree / gpus[0].memoryTotal) * 100
            except ImportError:
                self._current_resources.gpu_available = False
                
        except Exception as e:
            logger.warning(f"[ResourceMonitor] 更新资源信息失败: {e}")
            
    def get_status(self) -> ResourceInfo:
        """获取当前资源状态"""
        return self._current_resources
    
    def is_overloaded(self) -> bool:
        """检查系统是否过载"""
        return self._current_resources.overall_status == ResourceStatus.CRITICAL
    
    def can_run_heavy_task(self) -> bool:
        """检查是否可以运行重量级任务"""
        return self._current_resources.overall_status == ResourceStatus.NORMAL


class ResourceAwareScheduler:
    """
    资源感知调度器
    
    根据系统资源状态动态调整任务调度策略：
    - 资源充足时：使用高性能模块
    - 资源紧张时：自动降级到轻量级模块
    """
    
    def __init__(self):
        """初始化调度器"""
        self._resource_monitor = ResourceMonitor()
        self._lightweight_modules: List[str] = []
        self._heavy_modules: List[str] = []
        
    async def start(self):
        """启动资源监控"""
        await self._resource_monitor.start()
        
    async def stop(self):
        """停止资源监控"""
        await self._resource_monitor.stop()
        
    def register_module_weight(self, module_name: str, is_lightweight: bool):
        """
        注册模块权重
        
        Args:
            module_name: 模块名称
            is_lightweight: 是否为轻量级模块
        """
        if is_lightweight:
            if module_name not in self._lightweight_modules:
                self._lightweight_modules.append(module_name)
        else:
            if module_name not in self._heavy_modules:
                self._heavy_modules.append(module_name)
                
    def filter_modules_by_resource(self, candidates: List[str]) -> List[str]:
        """
        根据资源状态过滤模块
        
        Args:
            candidates: 候选模块列表
            
        Returns:
            过滤后的模块列表
        """
        resources = self._resource_monitor.get_status()
        status = resources.overall_status
        
        if status == ResourceStatus.CRITICAL:
            # 资源严重不足，只使用轻量级模块
            filtered = [m for m in candidates if m in self._lightweight_modules]
            if filtered:
                logger.info(f"[ResourceAwareScheduler] 资源严重不足，仅使用轻量级模块: {filtered}")
                return filtered
            # 如果没有轻量级模块，返回所有候选
            return candidates
            
        elif status == ResourceStatus.WARNING:
            # 资源警告，优先使用轻量级模块
            lightweight = [m for m in candidates if m in self._lightweight_modules]
            heavy = [m for m in candidates if m in self._heavy_modules]
            # 轻量级在前，重量级在后
            result = lightweight + heavy
            logger.info(f"[ResourceAwareScheduler] 资源警告，优先轻量级模块: {result}")
            return result
            
        else:
            # 资源充足，正常调度
            return candidates
            
    def get_resource_status(self) -> ResourceInfo:
        """获取当前资源状态"""
        return self._resource_monitor.get_status()
