"""
模型调度器
模型生命周期管理和实例池
"""

import asyncio
import time
from typing import Optional, Any, Dict, List, Callable
from threading import Lock
from dataclasses import dataclass
from enum import Enum
import logging

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    psutil = None


class ModelState(Enum):
    """模型状态"""
    UNLOADED = "unloaded"
    LOADING = "loading"
    READY = "ready"
    ACTIVE = "active"
    ERROR = "error"


@dataclass
class ModelInfo:
    """模型信息"""
    name: str
    size_mb: int
    min_memory_mb: int
    recommended_memory_mb: int
    context_length: int
    quantization: str = "fp16"
    state: ModelState = ModelState.UNLOADED
    load_time: float = 0
    last_used: float = 0


class ModelInstance:
    """模型实例"""
    
    def __init__(self, model: Any, info: ModelInfo):
        self.model = model
        self.info = info
        self.active_requests = 0
        self.total_requests = 0
        self.avg_latency = 0
        self._lock = Lock()
    
    def acquire(self):
        """获取实例"""
        with self._lock:
            self.active_requests += 1
            self.total_requests += 1
            self.info.state = ModelState.ACTIVE
            self.info.last_used = time.time()
    
    def release(self, latency: float):
        """释放实例"""
        with self._lock:
            self.active_requests -= 1
            # 更新平均延迟
            n = self.total_requests
            self.avg_latency = (self.avg_latency * (n - 1) + latency) / n
            if self.active_requests == 0:
                self.info.state = ModelState.READY
    
    def is_available(self) -> bool:
        """是否可用"""
        return self.info.state in (ModelState.READY, ModelState.ACTIVE) and self.active_requests < 3


class ModelScheduler:
    """
    模型调度器
    - 模型生命周期管理
    - 实例池管理
    - 负载均衡
    - 资源监控
    """
    
    def __init__(self):
        self.models: Dict[str, ModelInfo] = {}
        self.instances: Dict[str, List[ModelInstance]] = {}
        self.model_loader: Optional[Callable] = None
        self._lock = Lock()
        self.logger = logging.getLogger(__name__)
        
        # 资源配置
        self.max_instances_per_model = 3
        self.auto_unload_idle_seconds = 300  # 5分钟
        self.preload_models: List[str] = []
        
        # 系统资源
        if HAS_PSUTIL:
            self.total_memory_mb = psutil.virtual_memory().total / (1024 * 1024)
        else:
            self.total_memory_mb = 16384  # 默认16GB
        self.reserved_memory_mb = 4096  # 保留4GB
    
    def register_model(self, info: ModelInfo):
        """注册模型"""
        with self._lock:
            self.models[info.name] = info
            self.instances[info.name] = []
            self.logger.info(f"注册模型: {info.name} ({info.size_mb}MB)")
    
    def set_model_loader(self, loader: Callable):
        """设置模型加载器"""
        self.model_loader = loader
    
    async def load_model(self, model_name: str, wait: bool = True) -> Optional[ModelInstance]:
        """加载模型"""
        with self._lock:
            if model_name not in self.models:
                self.logger.error(f"模型未注册: {model_name}")
                return None
            
            info = self.models[model_name]
            
            # 检查是否已加载
            for inst in self.instances[model_name]:
                if inst.info.state == ModelState.READY:
                    return inst
            
            # 检查实例数量
            if len(self.instances[model_name]) >= self.max_instances_per_model:
                # 尝试等待可用实例
                if wait:
                    return await self._wait_for_instance(model_name)
                return None
            
            # 检查内存
            available_memory = self._get_available_memory()
            if info.recommended_memory_mb > available_memory:
                # 尝试释放其他模型
                await self._free_memory(info.recommended_memory_mb)
                
                available_memory = self._get_available_memory()
                if info.recommended_memory_mb > available_memory:
                    self.logger.warning(f"内存不足加载模型: {model_name}")
                    return None
        
        # 加载模型
        info.state = ModelState.LOADING
        
        try:
            if self.model_loader:
                model = await asyncio.to_thread(self.model_loader, model_name)
            else:
                model = None  # 模拟加载
            
            instance = ModelInstance(model, info)
            instance.info.state = ModelState.READY
            instance.info.load_time = time.time()
            
            with self._lock:
                self.instances[model_name].append(instance)
            
            self.logger.info(f"模型加载成功: {model_name}")
            return instance
            
        except Exception as e:
            info.state = ModelState.ERROR
            self.logger.error(f"模型加载失败: {model_name} - {e}")
            return None
    
    async def _wait_for_instance(self, model_name: str, timeout: float = 30) -> Optional[ModelInstance]:
        """等待可用实例"""
        start = time.time()
        
        while time.time() - start < timeout:
            await asyncio.sleep(0.1)
            
            for inst in self.instances[model_name]:
                if inst.is_available():
                    return inst
        
        return None
    
    async def _free_memory(self, required_mb: int):
        """释放内存"""
        with self._lock:
            for model_name, instances in list(self.instances.items()):
                for inst in instances[:]:
                    if inst.active_requests == 0:
                        age = time.time() - inst.info.last_used
                        if age > 60:  # 1分钟未使用
                            instances.remove(inst)
                            self.logger.info(f"卸载闲置模型: {model_name}")
                            return
    
    def _get_available_memory(self) -> float:
        """获取可用内存(MB)"""
        if HAS_PSUTIL:
            mem = psutil.virtual_memory()
            available = mem.available / (1024 * 1024)
        else:
            available = self.total_memory_mb - 4096  # 假设使用了4GB
        return available - self.reserved_memory_mb
    
    def get_instance(self, model_name: str) -> Optional[ModelInstance]:
        """获取可用实例"""
        with self._lock:
            if model_name not in self.instances:
                return None
            
            for inst in self.instances[model_name]:
                if inst.is_available():
                    inst.acquire()
                    return inst
        
        return None
    
    def release_instance(self, instance: ModelInstance, latency: float = 0):
        """释放实例"""
        instance.release(latency)
    
    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        if HAS_PSUTIL:
            mem = psutil.virtual_memory()
            cpu = psutil.cpu_percent()
            cpu_count = psutil.cpu_count()
            mem_info = {
                "total_mb": self.total_memory_mb,
                "available_mb": mem.available / (1024 * 1024),
                "used_mb": mem.used / (1024 * 1024),
                "percent": mem.percent
            }
        else:
            cpu = 50
            cpu_count = 4
            mem_info = {
                "total_mb": self.total_memory_mb,
                "available_mb": self.total_memory_mb / 2,
                "used_mb": self.total_memory_mb / 2,
                "percent": 50
            }
        
        with self._lock:
            total_model_memory = sum(
                inst.info.recommended_memory_mb
                for instances in self.instances.values()
                for inst in instances
            )
        
        return {
            "memory": {
                **mem_info,
                "models_using_mb": total_model_memory
            },
            "cpu": {
                "percent": cpu,
                "count": cpu_count
            },
            "models": {
                name: {
                    "state": info.state.value,
                    "load_time": info.load_time,
                    "instances": len(self.instances.get(name, [])),
                    "active_requests": sum(
                        inst.active_requests 
                        for inst in self.instances.get(name, [])
                    )
                }
                for name, info in self.models.items()
            }
        }
    
    def preload(self, model_names: List[str] = None):
        """预加载模型"""
        names = model_names or self.preload_models
        for name in names:
            if name in self.models:
                asyncio.create_task(self.load_model(name))
    
    def get_stats(self) -> Dict[str, Any]:
        """获取调度统计"""
        with self._lock:
            stats = {
                "registered_models": len(self.models),
                "total_instances": sum(len(instances) for instances in self.instances.values()),
                "active_instances": sum(
                    inst.active_requests
                    for instances in self.instances.values()
                    for inst in instances
                )
            }
            
            model_stats = {}
            for name, instances in self.instances.items():
                model_stats[name] = {
                    "instances": len(instances),
                    "ready": sum(1 for i in instances if i.info.state == ModelState.READY),
                    "active": sum(1 for i in instances if i.info.state == ModelState.ACTIVE),
                    "total_requests": sum(i.total_requests for i in instances),
                    "avg_latency": sum(i.avg_latency for i in instances) / max(1, len(instances))
                }
            
            stats["model_details"] = model_stats
            return stats
