"""
统一模型网关 - 独立测试版本
"""

import asyncio
import time
import httpx
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum


# ─────────────────────────────────────────────────────────────────────────────
# 数据模型
# ─────────────────────────────────────────────────────────────────────────────

class ModelProvider(Enum):
    LOCAL = "local"
    REMOTE = "remote"


class TierLevel(Enum):
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"


class HealthLevel(Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class HardwareProfile:
    cpu_cores: int = 4
    cpu_available: float = 0.5
    memory_total_gb: float = 8.0
    memory_available_gb: float = 4.0
    has_gpu: bool = False
    gpu_name: str = ""
    gpu_memory_total_mb: float = 0
    gpu_memory_available_mb: float = 0
    network_available: bool = True


@dataclass
class ComponentHealth:
    name: str
    status: HealthLevel = HealthLevel.HEALTHY
    latency_ms: float = 0
    error: str = ""


@dataclass
class BootReport:
    status: str = "initializing"
    duration_ms: float = 0
    ollama: Optional[ComponentHealth] = None
    gpu: Optional[ComponentHealth] = None
    memory: Optional[ComponentHealth] = None
    local_models: List = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# L0 健康检查
# ─────────────────────────────────────────────────────────────────────────────

async def check_ollama() -> ComponentHealth:
    comp = ComponentHealth(name="ollama")
    start = time.perf_counter()
    
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get("http://localhost:11434/api/tags")
            if r.status_code == 200:
                comp.status = HealthLevel.HEALTHY
                data = r.json()
                print(f"      Ollama models: {len(data.get('models', []))}")
            else:
                comp.status = HealthLevel.CRITICAL
                comp.error = f"HTTP {r.status_code}"
    except httpx.ConnectError:
        comp.status = HealthLevel.CRITICAL
        comp.error = "Connection refused"
    except httpx.TimeoutException:
        comp.status = HealthLevel.WARNING
        comp.error = "Timeout"
    except Exception as e:
        comp.status = HealthLevel.CRITICAL
        comp.error = str(e)
    
    comp.latency_ms = (time.perf_counter() - start) * 1000
    return comp


async def check_gpu() -> ComponentHealth:
    comp = ComponentHealth(name="gpu")
    start = time.perf_counter()
    
    try:
        import pynvml
        pynvml.nvmlInit()
        count = pynvml.nvmlDeviceGetCount()
        
        if count > 0:
            comp.status = HealthLevel.HEALTHY
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            comp.latency_ms = (time.perf_counter() - start) * 1000
            return comp
        else:
            comp.status = HealthLevel.WARNING
            comp.error = "No GPU"
    except ImportError:
        comp.status = HealthLevel.WARNING
        comp.error = "pynvml not installed"
    except Exception as e:
        comp.status = HealthLevel.WARNING
        comp.error = str(e)
    
    comp.latency_ms = (time.perf_counter() - start) * 1000
    return comp


async def check_memory() -> ComponentHealth:
    import psutil
    
    comp = ComponentHealth(name="memory")
    start = time.perf_counter()
    
    vm = psutil.virtual_memory()
    if vm.percent > 90:
        comp.status = HealthLevel.CRITICAL
    elif vm.percent > 70:
        comp.status = HealthLevel.WARNING
    else:
        comp.status = HealthLevel.HEALTHY
    
    comp.latency_ms = (time.perf_counter() - start) * 1000
    return comp


# ─────────────────────────────────────────────────────────────────────────────
# 硬件感知路由器
# ─────────────────────────────────────────────────────────────────────────────

async def get_hardware_profile() -> HardwareProfile:
    import psutil
    
    profile = HardwareProfile()
    profile.cpu_cores = psutil.cpu_count()
    profile.cpu_available = 1.0 - psutil.cpu_percent(interval=0.1) / 100
    
    vm = psutil.virtual_memory()
    profile.memory_total_gb = vm.total / (1024 ** 3)
    profile.memory_available_gb = vm.available / (1024 ** 3)
    
    try:
        import pynvml
        pynvml.nvmlInit()
        if pynvml.nvmlDeviceGetCount() > 0:
            profile.has_gpu = True
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            profile.gpu_memory_total_mb = mem_info.total / (1024 ** 2)
            profile.gpu_memory_available_mb = mem_info.free / (1024 ** 2)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode('utf-8')
            profile.gpu_name = name
    except:
        pass
    
    return profile


# 模型配置
MODELS = {
    "qwen2.5:0.5b": {"tier": "L2", "memory_gb": 1.0, "provider": "local"},
    "qwen2.5:3b": {"tier": "L3", "memory_gb": 2.5, "provider": "local"},
    "qwen2.5:7b": {"tier": "L3", "memory_gb": 5.5, "gpu_mb": 2048, "provider": "local"},
    "qwen2.5:14b": {"tier": "L4", "memory_gb": 10.0, "gpu_mb": 6144, "provider": "local"},
    "deepseek-chat": {"tier": "L3", "provider": "remote", "cost": 0.14},
}


async def select_model(hint: str = None, prefer_local: bool = True) -> tuple:
    profile = await get_hardware_profile()
    
    candidates = []
    for name, cfg in MODELS.items():
        tier = cfg["tier"]
        
        # 层级过滤
        if hint == "L2" and tier not in ["L2"]:
            continue
        if hint == "L3" and tier not in ["L2", "L3"]:
            continue
        if hint == "L4" and tier not in ["L2", "L3", "L4"]:
            continue
        
        # 本地偏好
        if prefer_local and cfg["provider"] == "remote":
            continue
        
        # 资源检查
        mem_needed = cfg.get("memory_gb", 1.0)
        if profile.memory_available_gb < mem_needed:
            continue
        
        if cfg["provider"] == "local" and profile.memory_available_gb >= mem_needed:
            score = 1.0
            if prefer_local:
                score *= 1.5
            if tier == "L2":
                score *= 1.2
            candidates.append((name, tier, cfg["provider"], score))
    
    if not candidates:
        # 降级到远程
        return "deepseek-chat", "L3", "remote"
    
    candidates.sort(key=lambda x: x[3], reverse=True)
    return candidates[0][0], candidates[0][1], candidates[0][2]


# ─────────────────────────────────────────────────────────────────────────────
# 主测试
# ─────────────────────────────────────────────────────────────────────────────

async def test_l0_boot():
    print("\n" + "="*55)
    print("  L0 Boot Test")
    print("="*55)
    
    start = time.perf_counter()
    
    # 并行检查
    results = await asyncio.gather(
        check_ollama(),
        check_gpu(),
        check_memory(),
        return_exceptions=True,
    )
    
    ollama, gpu, memory = results
    
    duration_ms = (time.perf_counter() - start) * 1000
    
    print(f"\n  Duration: {duration_ms:.0f}ms")
    print(f"\n  Components:")
    
    for comp in [ollama, gpu, memory]:
        status = "[OK]" if comp.status == HealthLevel.HEALTHY else "[!!]" if comp.status == HealthLevel.CRITICAL else "[W!]"
        print(f"    {status} {comp.name}: {comp.status.value} ({comp.latency_ms:.0f}ms)")
        if comp.error:
            print(f"         Error: {comp.error}")
    
    # 确定状态
    if ollama.status == HealthLevel.CRITICAL:
        status = "DEGRADED" if memory.status == HealthLevel.HEALTHY else "UNAVAILABLE"
    elif gpu.status != HealthLevel.HEALTHY or memory.status != HealthLevel.HEALTHY:
        status = "DEGRADED"
    else:
        status = "READY"
    
    print(f"\n  System Status: {status}")


async def test_hardware():
    print("\n" + "="*55)
    print("  Hardware Profile Test")
    print("="*55)
    
    profile = await get_hardware_profile()
    
    print(f"\n  CPU:    {profile.cpu_cores} cores, {profile.cpu_available*100:.0f}% available")
    print(f"  Memory: {profile.memory_available_gb:.1f}GB / {profile.memory_total_gb:.1f}GB")
    print(f"  GPU:    {'Yes' if profile.has_gpu else 'No'} {profile.gpu_name}")
    if profile.has_gpu:
        print(f"          {profile.gpu_memory_available_mb:.0f}MB / {profile.gpu_memory_total_mb:.0f}MB")


async def test_model_selection():
    print("\n" + "="*55)
    print("  Model Selection Test")
    print("="*55)
    
    test_cases = [
        ("Auto (prefer local)", None),
        ("Force L2", "L2"),
        ("Force L3", "L3"),
        ("Force L4", "L4"),
    ]
    
    for name, hint in test_cases:
        model, tier, provider = await select_model(hint, prefer_local=True)
        print(f"\n    {name}:")
        print(f"      -> {model} ({tier}, {provider})")


async def main():
    print("""
    +========================================================+
    |     LivingTreeAI L0-L4 Integration Test              |
    +========================================================+
    """)
    
    await test_l0_boot()
    await test_hardware()
    await test_model_selection()
    
    print("\n" + "="*55)
    print("  All tests completed!")
    print("="*55)


if __name__ == "__main__":
    asyncio.run(main())
