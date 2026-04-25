"""
L0 系统初始化层
===============

核心功能：
1. 系统健康检查
2. 模型就绪状态
3. 启动序列管理
4. 资源预热

Author: Hermes Desktop Team
"""

import time
import asyncio
import httpx
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ReadyStatus(Enum):
    """就绪状态"""
    UNKNOWN = "unknown"
    INITIALIZING = "initializing"
    READY = "ready"
    DEGRADED = "degraded"  # 部分能力可用
    UNAVAILABLE = "unavailable"


class HealthLevel(Enum):
    """健康等级"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class ComponentHealth:
    """组件健康状态"""
    name: str
    status: HealthLevel = HealthLevel.UNKNOWN
    latency_ms: float = 0
    error_message: str = ""
    last_check: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BootReport:
    """启动报告"""
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    duration_ms: float = 0
    
    # 组件状态
    ollama: Optional[ComponentHealth] = None
    gpu: Optional[ComponentHealth] = None
    memory: Optional[ComponentHealth] = None
    network: Optional[ComponentHealth] = None
    
    # 就绪状态
    status: ReadyStatus = ReadyStatus.INITIALIZING
    
    # 可用模型
    local_models: List[str] = field(default_factory=list)
    remote_models: List[str] = field(default_factory=list)
    
    # 推荐
    recommended_tier: str = "L2"
    recommended_model: str = ""


@dataclass
class ModelInfo:
    """模型信息"""
    name: str
    provider: str  # local, remote
    size_mb: float = 0
    loaded: bool = False
    latency_ms: float = 0


class SystemHealthChecker:
    """
    系统健康检查器
    
    检查项：
    - Ollama 服务
    - GPU 可用性
    - 内存状态
    - 网络连通性
    """
    
    def __init__(
        self,
        ollama_host: str = "http://localhost:11434",
        check_timeout: float = 5.0,
    ):
        self.ollama_host = ollama_host
        self.check_timeout = check_timeout
    
    async def run_health_checks(self) -> BootReport:
        """执行所有健康检查"""
        report = BootReport()
        start = time.perf_counter()
        
        # 并行执行所有检查
        results = await asyncio.gather(
            self.check_ollama(),
            self.check_gpu(),
            self.check_memory(),
            self.check_network(),
            self.check_local_models(),
            return_exceptions=True,
        )
        
        (
            report.ollama,
            report.gpu,
            report.memory,
            report.network,
            models,
        ) = results
        
        # 处理异常
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                names = ["ollama", "gpu", "memory", "network", "models"]
                comp = ComponentHealth(name=names[i], status=HealthLevel.CRITICAL)
                comp.error_message = str(r)
                if i == 0:
                    report.ollama = comp
                elif i == 1:
                    report.gpu = comp
                elif i == 2:
                    report.memory = comp
                elif i == 3:
                    report.network = comp
        
        # 解析模型列表
        if isinstance(models, list):
            report.local_models = models
        
        # 确定就绪状态
        report.status = self._determine_status(report)
        
        # 生成推荐
        report.recommended_tier, report.recommended_model = self._generate_recommendation(report)
        
        report.end_time = datetime.now()
        report.duration_ms = (time.perf_counter() - start) * 1000
        
        return report
    
    async def check_ollama(self) -> ComponentHealth:
        """检查 Ollama 服务"""
        comp = ComponentHealth(name="ollama")
        start = time.perf_counter()
        
        try:
            async with httpx.AsyncClient(timeout=self.check_timeout) as client:
                r = await client.get(f"{self.ollama_host}/api/tags")
                
                if r.status_code == 200:
                    comp.status = HealthLevel.HEALTHY
                    comp.metadata["version"] = r.json().get("version", "unknown")
                else:
                    comp.status = HealthLevel.CRITICAL
                    comp.error_message = f"HTTP {r.status_code}"
                    
        except httpx.ConnectError:
            comp.status = HealthLevel.CRITICAL
            comp.error_message = "Connection refused - Ollama not running"
        except httpx.TimeoutException:
            comp.status = HealthLevel.WARNING
            comp.error_message = "Connection timeout"
        except Exception as e:
            comp.status = HealthLevel.CRITICAL
            comp.error_message = str(e)
        
        comp.latency_ms = (time.perf_counter() - start) * 1000
        comp.last_check = datetime.now()
        
        return comp
    
    async def check_gpu(self) -> ComponentHealth:
        """检查 GPU 可用性"""
        comp = ComponentHealth(name="gpu")
        start = time.perf_counter()
        
        try:
            import pynvml
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            
            if device_count > 0:
                comp.status = HealthLevel.HEALTHY
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                mem_used_gb = mem_info.used / (1024 ** 3)
                mem_total_gb = mem_info.total / (1024 ** 3)
                
                comp.metadata = {
                    "device_count": device_count,
                    "memory_used_gb": mem_used_gb,
                    "memory_total_gb": mem_total_gb,
                    "memory_percent": (mem_used_gb / mem_total_gb * 100) if mem_total_gb > 0 else 0,
                }
                
                # 内存使用超过 90% 为警告
                if comp.metadata["memory_percent"] > 90:
                    comp.status = HealthLevel.WARNING
                    comp.error_message = "GPU memory nearly full"
            else:
                comp.status = HealthLevel.WARNING
                comp.error_message = "No GPU devices found"
                comp.metadata["device_count"] = 0
                
        except ImportError:
            comp.status = HealthLevel.WARNING
            comp.error_message = "pynvml not installed"
        except Exception as e:
            comp.status = HealthLevel.WARNING
            comp.error_message = str(e)
        
        comp.latency_ms = (time.perf_counter() - start) * 1000
        comp.last_check = datetime.now()
        
        return comp
    
    async def check_memory(self) -> ComponentHealth:
        """检查系统内存"""
        import psutil
        
        comp = ComponentHealth(name="memory")
        start = time.perf_counter()
        
        vm = psutil.virtual_memory()
        mem_available_gb = vm.available / (1024 ** 3)
        mem_total_gb = vm.total / (1024 ** 3)
        mem_percent = vm.percent
        
        comp.metadata = {
            "available_gb": mem_available_gb,
            "total_gb": mem_total_gb,
            "percent": mem_percent,
        }
        
        if mem_percent > 90:
            comp.status = HealthLevel.CRITICAL
            comp.error_message = "Memory nearly full"
        elif mem_percent > 70:
            comp.status = HealthLevel.WARNING
            comp.error_message = "Memory usage high"
        else:
            comp.status = HealthLevel.HEALTHY
        
        comp.latency_ms = (time.perf_counter() - start) * 1000
        comp.last_check = datetime.now()
        
        return comp
    
    async def check_network(self) -> ComponentHealth:
        """检查网络连通性"""
        comp = ComponentHealth(name="network")
        start = time.perf_counter()
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get("https://api.deepseek.com", timeout=3.0)
                if r.status_code < 500:
                    comp.status = HealthLevel.HEALTHY
                else:
                    comp.status = HealthLevel.WARNING
                    comp.error_message = f"API returned {r.status_code}"
        except httpx.ConnectError:
            comp.status = HealthLevel.WARNING
            comp.error_message = "No internet connection"
        except httpx.TimeoutException:
            comp.status = HealthLevel.WARNING
            comp.error_message = "Network timeout"
        except Exception as e:
            comp.status = HealthLevel.WARNING
            comp.error_message = str(e)
        
        comp.latency_ms = (time.perf_counter() - start) * 1000
        comp.last_check = datetime.now()
        
        return comp
    
    async def check_local_models(self) -> List[str]:
        """获取本地模型列表"""
        try:
            async with httpx.AsyncClient(timeout=self.check_timeout) as client:
                r = await client.get(f"{self.ollama_host}/api/tags")
                if r.status_code == 200:
                    models = r.json().get("models", [])
                    return [m.get("name", "") for m in models if m.get("name")]
        except:
            pass
        return []
    
    def _determine_status(self, report: BootReport) -> ReadyStatus:
        """确定就绪状态"""
        # Ollama 必须可用
        if not report.ollama or report.ollama.status == HealthLevel.CRITICAL:
            # 检查是否有远程能力
            if report.network and report.network.status == HealthLevel.HEALTHY:
                return ReadyStatus.DEGRADED
            return ReadyStatus.UNAVAILABLE
        
        # GPU 不可用但内存充足
        if not report.gpu or report.gpu.status != HealthLevel.HEALTHY:
            if report.memory and report.memory.status == HealthLevel.HEALTHY:
                return ReadyStatus.DEGRADED
        
        # 内存紧张
        if report.memory and report.memory.status == HealthLevel.CRITICAL:
            return ReadyStatus.DEGRADED
        
        return ReadyStatus.READY
    
    def _generate_recommendation(self, report: BootReport) -> tuple:
        """生成推荐"""
        if report.status == ReadyStatus.UNAVAILABLE:
            return "L0", ""
        
        # 检查可用资源
        memory_gb = 0
        gpu_available = False
        gpu_memory_gb = 0
        
        if report.memory:
            memory_gb = report.memory.metadata.get("available_gb", 0)
        
        if report.gpu and report.gpu.status == HealthLevel.HEALTHY:
            gpu_available = True
            gpu_memory_gb = (
                report.gpu.metadata.get("memory_total_gb", 0) -
                report.gpu.metadata.get("memory_used_gb", 0)
            )
        
        # 根据资源推荐模型
        if gpu_available and gpu_memory_gb > 10:
            return "L3", "qwen2.5:7b"
        elif gpu_available and gpu_memory_gb > 4:
            return "L2", "qwen2.5:3b"
        elif memory_gb > 4:
            return "L2", "qwen2.5:0.5b"
        elif memory_gb > 2:
            return "L1", ""  # 只能用缓存
        else:
            return "L0", ""


class BootSequence:
    """
    启动序列管理器
    """
    
    def __init__(self):
        self.health_checker = SystemHealthChecker()
        self._boot_report: Optional[BootReport] = None
    
    async def boot(self) -> BootReport:
        """执行启动序列"""
        logger.info("Starting LivingTreeAI boot sequence...")
        
        # 1. L0 健康检查
        report = await self.health_checker.run_health_checks()
        self._boot_report = report
        
        # 2. 记录日志
        logger.info(f"Boot complete: status={report.status.value}, "
                   f"duration={report.duration_ms:.0f}ms")
        
        if report.local_models:
            logger.info(f"Local models: {', '.join(report.local_models)}")
        
        return report
    
    def get_report(self) -> Optional[BootReport]:
        """获取启动报告"""
        return self._boot_report
    
    async def quick_health_check(self) -> Dict[str, bool]:
        """快速健康检查（同步）"""
        import psutil
        
        result = {
            "ollama": False,
            "gpu": False,
            "memory": False,
            "network": False,
        }
        
        # Ollama
        try:
            import httpx
            r = httpx.get("http://localhost:11434/api/tags", timeout=2)
            result["ollama"] = r.status_code == 200
        except:
            pass
        
        # GPU
        try:
            import pynvml
            pynvml.nvmlInit()
            result["gpu"] = pynvml.nvmlDeviceGetCount() > 0
        except:
            pass
        
        # Memory
        vm = psutil.virtual_memory()
        result["memory"] = vm.percent < 90
        
        # Network
        try:
            import httpx
            r = httpx.get("https://www.google.com", timeout=2)
            result["network"] = r.status_code == 200
        except:
            try:
                import httpx
                r = httpx.get("https://www.baidu.com", timeout=2)
                result["network"] = r.status_code == 200
            except:
                pass
        
        return result


# ─────────────────────────────────────────────────────────────────────────────
# 单例访问
# ─────────────────────────────────────────────────────────────────────────────

_boot_sequence: Optional[BootSequence] = None


def get_boot_sequence() -> BootSequence:
    """获取启动序列管理器"""
    global _boot_sequence
    if _boot_sequence is None:
        _boot_sequence = BootSequence()
    return _boot_sequence


async def system_ready() -> tuple:
    """快速检查系统是否就绪"""
    boot = get_boot_sequence()
    result = await boot.quick_health_check()
    
    ready = result["ollama"] or result["network"]
    
    # 确定可用模型
    if result["ollama"]:
        try:
            import httpx
            r = httpx.get("http://localhost:11434/api/tags", timeout=2)
            if r.status_code == 200:
                models = [m.get("name") for m in r.json().get("models", [])]
                return ready, models
        except:
            pass
    
    return ready, []
