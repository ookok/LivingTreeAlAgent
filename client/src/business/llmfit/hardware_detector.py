"""
硬件检测模块

检测系统硬件配置：
- CPU 检测
- 内存检测
- GPU 检测
- 运行时检测
"""

import platform
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum


# ============ 硬件类型 ============

class HardwareBackend(Enum):
    """硬件后端类型"""
    OLLAMA = "ollama"
    LLAMA_CPP = "llama.cpp"
    VLLM = "vLLM"
    MLX = "MLX"
    DOCKER = "Docker"
    LM_STUDIO = "LM Studio"
    OPENAI = "OpenAI"
    ANTHROPIC = "Anthropic"
    UNKNOWN = "unknown"


@dataclass
class HardwareSpec:
    """硬件规格"""
    cpu_cores: int = 0
    cpu_model: str = ""
    ram_gb: float = 0.0
    ram_available_gb: float = 0.0
    gpu_name: str = ""
    gpu_memory_gb: float = 0.0
    gpu_count: int = 0
    gpu_vendor: str = ""
    backend: HardwareBackend = HardwareBackend.UNKNOWN
    os_name: str = ""
    os_version: str = ""
    python_version: str = ""
    is_apple_silicon: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelRequirements:
    """模型要求"""
    min_ram_gb: float = 0.0
    min_vram_gb: float = 0.0
    min_cpu_cores: int = 0
    supported_backends: List[HardwareBackend] = field(default_factory=list)
    quantization: str = ""  # e.g., "4bit", "8bit", "fp16"


# ============ 基础硬件检测 ============

class BaseHardwareDetector:
    """基础硬件检测"""
    
    def detect_cpu(self) -> Dict[str, Any]:
        """检测 CPU"""
        cpu_count = os.cpu_count() or 0
        
        # 获取 CPU 型号
        cpu_model = platform.processor() or "Unknown"
        
        return {
            "cores": cpu_count,
            "model": cpu_model,
        }
    
    def detect_memory(self) -> Dict[str, Any]:
        """检测内存"""
        try:
            import psutil
            vm = psutil.virtual_memory()
            return {
                "total_gb": vm.total / (1024**3),
                "available_gb": vm.available / (1024**3),
                "percent_used": vm.percent,
            }
        except ImportError:
            # 尝试从 /proc/meminfo 读取（Linux）
            try:
                with open("/proc/meminfo", "r") as f:
                    lines = f.readlines()
                    mem_total = 0
                    mem_available = 0
                    for line in lines:
                        if line.startswith("MemTotal:"):
                            mem_total = int(line.split()[1]) / (1024**2)  # KB to GB
                        elif line.startswith("MemAvailable:"):
                            mem_available = int(line.split()[1]) / (1024**2)
                    return {
                        "total_gb": mem_total,
                        "available_gb": mem_available,
                        "percent_used": (1 - mem_available / mem_total) * 100 if mem_total > 0 else 0,
                    }
            except:
                return {"total_gb": 0, "available_gb": 0, "percent_used": 0}
    
    def detect_os(self) -> Dict[str, str]:
        """检测操作系统"""
        return {
            "name": platform.system(),
            "version": platform.version(),
            "release": platform.release(),
        }
    
    def detect(self) -> HardwareSpec:
        """检测完整硬件规格"""
        cpu = self.detect_cpu()
        memory = self.detect_memory()
        os_info = self.detect_os()
        
        return HardwareSpec(
            cpu_cores=cpu.get("cores", 0),
            cpu_model=cpu.get("model", ""),
            ram_gb=memory.get("total_gb", 0),
            ram_available_gb=memory.get("available_gb", 0),
            os_name=os_info.get("name", ""),
            os_version=os_info.get("version", ""),
            backend=HardwareBackend.UNKNOWN,
        )


# ============ GPU 检测 ============

class GPUDetector:
    """GPU 检测"""
    
    def detect_nvidia(self) -> Optional[Dict[str, Any]]:
        """检测 NVIDIA GPU"""
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                gpus = []
                for line in lines:
                    parts = line.split(",")
                    if len(parts) >= 2:
                        gpus.append({
                            "name": parts[0].strip(),
                            "memory_total_mb": float(parts[1].strip().replace("MiB", "")),
                            "memory_free_mb": float(parts[2].strip().replace("MiB", "")),
                        })
                return {"gpus": gpus, "count": len(gpus)} if gpus else None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return None
    
    def detect_amd(self) -> Optional[Dict[str, Any]]:
        """检测 AMD GPU"""
        try:
            import subprocess
            result = subprocess.run(
                ["rocm-smi", "--showid", "--showmeminfo", "v"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                # 解析 ROCm 输出
                return {"gpus": [], "count": 0}
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return None
    
    def detect_apple_metal(self) -> Optional[Dict[str, Any]]:
        """检测 Apple Metal GPU"""
        import platform as plat
        if plat.system() == "Darwin":
            try:
                import subprocess
                result = subprocess.run(
                    ["system_profiler", "SPDisplaysDataType", "-json"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    import json
                    data = json.loads(result.stdout)
                    if "SPDisplaysDataType" in data:
                        gpus = []
                        for item in data["SPDisplaysDataType"]:
                            gpus.append({
                                "name": item.get("sppdisplays_vram", "Apple Metal"),
                                "memory_total_mb": 0,  # macOS 不直接暴露
                            })
                        return {"gpus": gpus, "count": len(gpus)} if gpus else None
            except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
                pass
        return None
    
    def detect(self) -> Dict[str, Any]:
        """检测所有 GPU"""
        # 尝试 NVIDIA
        nvidia = self.detect_nvidia()
        if nvidia and nvidia.get("count", 0) > 0:
            return {
                "gpus": nvidia["gpus"],
                "count": nvidia["count"],
                "vendor": "NVIDIA",
            }
        
        # 尝试 AMD
        amd = self.detect_amd()
        if amd and amd.get("count", 0) > 0:
            return {
                "gpus": amd["gpus"],
                "count": amd["count"],
                "vendor": "AMD",
            }
        
        # 尝试 Apple Metal
        apple = self.detect_apple_metal()
        if apple and apple.get("count", 0) > 0:
            return {
                "gpus": apple["gpus"],
                "count": apple["count"],
                "vendor": "Apple",
            }
        
        return {"gpus": [], "count": 0, "vendor": "Unknown"}


# ============ 运行时检测 ============

class RuntimeDetector:
    """运行时检测"""
    
    def detect_ollama(self) -> bool:
        """检测 Ollama 是否安装"""
        try:
            import subprocess
            result = subprocess.run(
                ["ollama", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def detect_llama_cpp(self) -> bool:
        """检测 llama.cpp 是否安装"""
        try:
            import subprocess
            result = subprocess.run(
                ["llama-cli", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def detect_vllm(self) -> bool:
        """检测 vLLM 是否安装"""
        try:
            import vllm
            return True
        except ImportError:
            return False
    
    def detect_lm_studio(self) -> bool:
        """检测 LM Studio 是否运行"""
        try:
            import urllib.request
            response = urllib.request.urlopen("http://localhost:1234/v1/models", timeout=2)
            return response.status == 200
        except:
            return False
    
    def detect(self) -> HardwareBackend:
        """检测主要运行时"""
        if self.detect_ollama():
            return HardwareBackend.OLLAMA
        elif self.detect_llama_cpp():
            return HardwareBackend.LLAMA_CPP
        elif self.detect_lm_studio():
            return HardwareBackend.LM_STUDIO
        elif self.detect_vllm():
            return HardwareBackend.VLLM
        return HardwareBackend.UNKNOWN


# ============ 完整硬件检测器 ============

class HardwareDetector(BaseHardwareDetector):
    """
    完整硬件检测器
    
    综合检测 CPU、内存、GPU、运行时等硬件配置
    """
    
    def __init__(self):
        self.gpu_detector = GPUDetector()
        self.runtime_detector = RuntimeDetector()
    
    def detect(self) -> HardwareSpec:
        """检测完整硬件规格"""
        # 基础检测
        spec = super().detect()
        
        # GPU 检测
        gpu_info = self.gpu_detector.detect()
        if gpu_info.get("count", 0) > 0:
            gpus = gpu_info.get("gpus", [])
            if gpus:
                primary_gpu = gpus[0]
                spec.gpu_name = primary_gpu.get("name", "")
                spec.gpu_memory_gb = primary_gpu.get("memory_total_mb", 0) / 1024
                spec.gpu_count = gpu_info.get("count", 0)
                spec.gpu_vendor = gpu_info.get("vendor", "")
        
        # Apple Silicon 检测
        import platform
        spec.is_apple_silicon = (
            platform.system() == "Darwin" and
            platform.machine() == "arm64"
        )
        if spec.is_apple_silicon:
            spec.backend = HardwareBackend.MLX
        
        # 运行时检测
        if spec.backend == HardwareBackend.UNKNOWN:
            spec.backend = self.runtime_detector.detect()
        
        # Python 版本
        spec.python_version = platform.python_version()
        
        # macOS 检测
        if platform.system() == "Darwin":
            try:
                import subprocess
                result = subprocess.run(
                    ["sw_vers", "-productVersion"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    spec.os_version = result.stdout.strip()
            except:
                pass
        
        return spec
    
    def get_model_requirements(self, model_name: str, quantization: str = "fp16") -> ModelRequirements:
        """
        估算模型要求
        
        Args:
            model_name: 模型名称
            quantization: 量化方式
            
        Returns:
            ModelRequirements: 模型要求
        """
        # 简单估算
        req = ModelRequirements()
        req.quantization = quantization
        
        # 根据量化方式调整
        if quantization in ["4bit", "Q4_K_M", "Q4_0"]:
            ram_mult = 0.25
            vram_mult = 0.25
        elif quantization in ["8bit", "Q8_0"]:
            ram_mult = 0.5
            vram_mult = 0.5
        elif quantization in ["fp16", "f16"]:
            ram_mult = 1.0
            vram_mult = 1.0
        else:  # fp32
            ram_mult = 2.0
            vram_mult = 2.0
        
        # 估算参数量
        param_size = self._estimate_params(model_name)
        
        req.min_ram_gb = param_size * ram_mult
        req.min_vram_gb = param_size * vram_mult
        req.min_cpu_cores = 4
        
        return req
    
    def _estimate_params(self, model_name: str) -> float:
        """估算模型参数量"""
        # 简单模式匹配
        name_lower = model_name.lower()
        
        if "7b" in name_lower or "7B" in name_lower:
            return 7.0
        elif "13b" in name_lower or "13B" in name_lower:
            return 13.0
        elif "30b" in name_lower or "30B" in name_lower:
            return 30.0
        elif "34b" in name_lower or "34B" in name_lower:
            return 34.0
        elif "70b" in name_lower or "70B" in name_lower:
            return 70.0
        elif "405b" in name_lower or "405B" in name_lower:
            return 405.0
        else:
            return 7.0  # 默认 7B


# ============ 导出 ============

__all__ = [
    "HardwareBackend",
    "HardwareSpec",
    "ModelRequirements",
    "BaseHardwareDetector",
    "GPUDetector",
    "RuntimeDetector",
    "HardwareDetector",
]
