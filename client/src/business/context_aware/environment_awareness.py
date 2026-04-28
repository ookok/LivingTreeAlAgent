"""
EnvironmentAwareness - 环境感知能力

功能：
1. 硬件资源监控（CPU、内存、GPU）
2. 网络状态监控（在线/离线、延迟）
3. 系统信息获取（OS、Python版本）
4. 电池状态（移动设备）
5. 位置信息（GPS）

遵循自我进化原则：
- 根据环境状态动态调整行为
- 从环境数据中学习优化策略
"""

import platform
import psutil
import socket
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger
from datetime import datetime


class NetworkStatus(Enum):
    """网络状态"""
    ONLINE = "online"
    OFFLINE = "offline"
    UNSTABLE = "unstable"


@dataclass
class HardwareInfo:
    """硬件信息"""
    cpu_count: int
    cpu_usage: float
    memory_total: float  # MB
    memory_usage: float
    disk_total: float  # GB
    disk_usage: float
    gpu_info: Optional[str] = None


@dataclass
class NetworkInfo:
    """网络信息"""
    status: NetworkStatus
    latency: float  # ms
    public_ip: Optional[str] = None
    hostname: str = ""


@dataclass
class SystemInfo:
    """系统信息"""
    os_name: str
    os_version: str
    python_version: str
    platform: str


@dataclass
class BatteryInfo:
    """电池信息"""
    percentage: float
    is_charging: bool
    remaining_time: Optional[int] = None  # 分钟


class EnvironmentAwareness:
    """
    环境感知能力
    
    实时监控和感知运行环境状态，为智能体决策提供上下文信息。
    """

    def __init__(self):
        self._logger = logger.bind(component="EnvironmentAwareness")
        self._history = []
        self._network_check_interval = 30  # 30秒检查一次网络

    def get_hardware_info(self) -> HardwareInfo:
        """获取硬件信息"""
        cpu_count = psutil.cpu_count(logical=True) or 0
        cpu_usage = psutil.cpu_percent(interval=0.1)
        
        memory = psutil.virtual_memory()
        memory_total = memory.total / (1024 * 1024)  # MB
        memory_usage = memory.percent
        
        disk = psutil.disk_usage('/')
        disk_total = disk.total / (1024 ** 3)  # GB
        disk_usage = disk.percent

        return HardwareInfo(
            cpu_count=cpu_count,
            cpu_usage=cpu_usage,
            memory_total=memory_total,
            memory_usage=memory_usage,
            disk_total=disk_total,
            disk_usage=disk_usage,
            gpu_info=self._get_gpu_info()
        )

    def _get_gpu_info(self) -> Optional[str]:
        """获取 GPU 信息"""
        try:
            import GPUtil
            gpus = GPUtil.getGPUs()
            if gpus:
                return f"{gpus[0].name} ({gpus[0].memoryTotal}MB)"
        except ImportError:
            pass
        return None

    def get_network_info(self) -> NetworkInfo:
        """获取网络信息"""
        status, latency = self._check_network()
        
        return NetworkInfo(
            status=status,
            latency=latency,
            public_ip=self._get_public_ip(),
            hostname=socket.gethostname()
        )

    def _check_network(self) -> tuple:
        """检查网络状态"""
        try:
            # 尝试连接到 Google DNS
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            start = datetime.now()
            result = sock.connect_ex(("8.8.8.8", 53))
            latency = (datetime.now() - start).total_seconds() * 1000
            sock.close()
            
            if result == 0:
                if latency > 500:
                    return NetworkStatus.UNSTABLE, latency
                return NetworkStatus.ONLINE, latency
        except:
            pass
        
        return NetworkStatus.OFFLINE, 0

    def _get_public_ip(self) -> Optional[str]:
        """获取公网 IP"""
        try:
            import requests
            return requests.get("https://api.ipify.org", timeout=5).text
        except:
            return None

    def get_system_info(self) -> SystemInfo:
        """获取系统信息"""
        return SystemInfo(
            os_name=platform.system(),
            os_version=platform.version(),
            python_version=platform.python_version(),
            platform=platform.platform()
        )

    def get_battery_info(self) -> Optional[BatteryInfo]:
        """获取电池信息（仅移动设备）"""
        try:
            battery = psutil.sensors_battery()
            if battery:
                return BatteryInfo(
                    percentage=battery.percent,
                    is_charging=battery.power_plugged,
                    remaining_time=battery.secsleft // 60 if battery.secsleft != psutil.POWER_TIME_UNLIMITED else None
                )
        except:
            pass
        return None

    def get_context(self) -> Dict[str, Any]:
        """获取完整的环境上下文"""
        context = {
            "timestamp": datetime.now().isoformat(),
            "hardware": self.get_hardware_info().__dict__,
            "network": self.get_network_info().__dict__,
            "system": self.get_system_info().__dict__,
            "battery": self.get_battery_info().__dict__ if self.get_battery_info() else None
        }
        
        # 记录历史
        self._history.append(context)
        if len(self._history) > 100:
            self._history.pop(0)
        
        return context

    def should_use_local_model(self) -> bool:
        """判断是否应该使用本地模型"""
        network = self.get_network_info()
        if network.status == NetworkStatus.OFFLINE:
            return True
        
        hardware = self.get_hardware_info()
        # 如果内存使用率超过 80%，不建议运行大型模型
        if hardware.memory_usage > 80:
            return False
        
        return True

    def get_resource_level(self) -> str:
        """获取资源级别（high/medium/low）"""
        hardware = self.get_hardware_info()
        
        if hardware.cpu_usage < 30 and hardware.memory_usage < 50:
            return "high"
        elif hardware.cpu_usage < 70 and hardware.memory_usage < 80:
            return "medium"
        else:
            return "low"

    def get_stats(self) -> Dict[str, Any]:
        """获取环境感知统计信息"""
        return {
            "history_count": len(self._history),
            "last_check": self._history[-1]["timestamp"] if self._history else None,
            "resource_level": self.get_resource_level()
        }

from enum import Enum