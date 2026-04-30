"""
AdaptiveResourceGovernor - 自适应资源治理器

核心功能：
1. 根据系统状态动态设置资源限制
2. 支持用户活跃检测
3. 动态调整内存、CPU、GPU限制
4. IO优先级管理

资源限制策略：
- 高内存压力：严格限制
- 用户活跃：中等限制，保证响应
- 系统空闲：放宽限制
"""

import time
import psutil
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class ResourceLimits:
    """资源限制配置"""
    memory_mb: int = 2048
    cpu_percent: int = 70
    gpu_memory_ratio: float = 0.7
    io_priority: str = "normal"  # idle/normal/high


@dataclass
class SystemStatus:
    """系统状态"""
    memory_pressure: float = 0.0
    cpu_usage: float = 0.0
    gpu_usage: float = 0.0
    gpu_memory_used: float = 0.0
    gpu_memory_total: float = 0.0
    user_active: bool = False
    task_queue_length: int = 0


class AdaptiveResourceGovernor:
    """自适应资源治理器"""
    
    def __init__(self):
        self._logger = logger.bind(component="AdaptiveResourceGovernor")
        self._limits_cache: Dict[str, ResourceLimits] = {}
        self._user_activity_timestamp = time.time()
        self._user_activity_threshold = 300  # 5分钟无活动视为不活跃
        
        self._logger.info("AdaptiveResourceGovernor 初始化完成")
    
    def govern_task(self, task_id: str) -> ResourceLimits:
        """
        根据系统状态动态设置资源限制
        
        Args:
            task_id: 任务ID
        
        Returns:
            资源限制配置
        """
        system_status = self._get_system_status()
        limits = self._calculate_limits(system_status)
        
        # 缓存限制配置
        self._limits_cache[task_id] = limits
        
        self._logger.debug(f"为任务 {task_id} 设置资源限制: {limits}")
        return limits
    
    def _get_system_status(self) -> SystemStatus:
        """获取系统状态"""
        # CPU使用
        cpu_usage = psutil.cpu_percent(interval=0.1)
        
        # 内存使用
        memory = psutil.virtual_memory()
        memory_pressure = memory.percent / 100.0
        
        # GPU信息（简化实现）
        gpu_usage = 0.0
        gpu_memory_used = 0.0
        gpu_memory_total = 64.0  # 假设V100 64GB
        
        # 用户活跃检测
        user_active = self._is_user_active()
        
        # 任务队列长度（简化实现）
        task_queue_length = 0
        
        return SystemStatus(
            memory_pressure=memory_pressure,
            cpu_usage=cpu_usage,
            gpu_usage=gpu_usage,
            gpu_memory_used=gpu_memory_used,
            gpu_memory_total=gpu_memory_total,
            user_active=user_active,
            task_queue_length=task_queue_length
        )
    
    def _is_user_active(self) -> bool:
        """检测用户是否活跃"""
        return (time.time() - self._user_activity_timestamp) < self._user_activity_threshold
    
    def update_user_activity(self):
        """更新用户活动时间戳"""
        self._user_activity_timestamp = time.time()
        self._logger.debug("用户活动已更新")
    
    def _calculate_limits(self, status: SystemStatus) -> ResourceLimits:
        """根据系统状态计算资源限制"""
        if status.memory_pressure > 0.9:
            # 高内存压力：严格限制
            return ResourceLimits(
                memory_mb=1024,
                cpu_percent=50,
                gpu_memory_ratio=0.5,
                io_priority="idle"
            )
        
        elif status.user_active:
            # 用户活跃：限制资源，保证响应
            return ResourceLimits(
                memory_mb=4096,
                cpu_percent=70,
                gpu_memory_ratio=0.7,
                io_priority="normal"
            )
        
        elif status.cpu_usage < 30 and status.memory_pressure < 0.5:
            # 系统空闲：放宽限制
            return ResourceLimits(
                memory_mb=8192,
                cpu_percent=100,
                gpu_memory_ratio=1.0,
                io_priority="high"
            )
        
        else:
            # 默认：中等限制
            return ResourceLimits(
                memory_mb=4096,
                cpu_percent=80,
                gpu_memory_ratio=0.8,
                io_priority="normal"
            )
    
    def apply_limits(self, task_id: str, limits: ResourceLimits):
        """应用资源限制"""
        try:
            # 设置进程优先级（简化实现）
            self._set_process_priority(limits.io_priority)
            
            # 设置内存限制（简化实现）
            self._set_memory_limit(limits.memory_mb)
            
            self._logger.info(f"资源限制已应用: {task_id}")
            return True
        except Exception as e:
            self._logger.error(f"应用资源限制失败: {e}")
            return False
    
    def _set_process_priority(self, priority: str):
        """设置进程优先级"""
        # 简化实现
        self._logger.debug(f"设置进程优先级: {priority}")
    
    def _set_memory_limit(self, memory_mb: int):
        """设置内存限制"""
        # 简化实现
        self._logger.debug(f"设置内存限制: {memory_mb}MB")
    
    def get_task_limits(self, task_id: str) -> Optional[ResourceLimits]:
        """获取任务的资源限制"""
        return self._limits_cache.get(task_id)
    
    def get_system_status(self) -> SystemStatus:
        """获取当前系统状态"""
        return self._get_system_status()
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        status = self._get_system_status()
        return {
            "memory_pressure": status.memory_pressure,
            "cpu_usage": status.cpu_usage,
            "user_active": status.user_active,
            "active_tasks": len(self._limits_cache),
            "governed_tasks": len(self._limits_cache)
        }


# 单例模式
_adaptive_resource_governor_instance = None

def get_adaptive_resource_governor() -> AdaptiveResourceGovernor:
    """获取自适应资源治理器实例"""
    global _adaptive_resource_governor_instance
    if _adaptive_resource_governor_instance is None:
        _adaptive_resource_governor_instance = AdaptiveResourceGovernor()
    return _adaptive_resource_governor_instance


if __name__ == "__main__":
    print("=" * 60)
    print("AdaptiveResourceGovernor 测试")
    print("=" * 60)
    
    governor = get_adaptive_resource_governor()
    
    # 测试用户活跃状态
    print("\n[1] 用户活跃状态测试")
    governor.update_user_activity()
    status = governor.get_system_status()
    print(f"用户活跃: {status.user_active}")
    
    # 测试资源限制计算
    print("\n[2] 资源限制计算测试")
    limits = governor.govern_task("test_task_001")
    print(f"内存限制: {limits.memory_mb}MB")
    print(f"CPU限制: {limits.cpu_percent}%")
    print(f"GPU限制: {limits.gpu_memory_ratio * 100}%")
    print(f"IO优先级: {limits.io_priority}")
    
    # 模拟系统空闲
    time.sleep(1)
    limits = governor.govern_task("test_task_002")
    print(f"\n系统空闲时的限制:")
    print(f"内存限制: {limits.memory_mb}MB")
    print(f"CPU限制: {limits.cpu_percent}%")
    
    # 统计信息
    print("\n[3] 统计信息")
    stats = governor.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # 应用限制
    print("\n[4] 应用资源限制")
    success = governor.apply_limits("test_task_001", limits)
    print(f"应用结果: {'成功' if success else '失败'}")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)