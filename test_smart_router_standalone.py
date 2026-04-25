"""
智能模型路由器 - 独立测试版本
"""

import sys
import time
import psutil
from typing import Optional, List, Callable, Dict, Any
from dataclasses import dataclass, field
from enum import Enum


class ModelProvider(Enum):
    """模型提供者"""
    LOCAL_OLLAMA = "local_ollama"
    REMOTE_OPENAI = "remote_openai"
    REMOTE_DEEPSEEK = "remote_deepseek"
    REMOTE_OLLAMA = "remote_ollama"
    REMOTE_GROQ = "remote_groq"


@dataclass
class ModelRequirements:
    """模型资源需求"""
    name: str
    provider: ModelProvider
    min_memory_gb: float = 4.0
    recommended_memory_gb: float = 8.0
    min_gpu_memory_mb: float = 0
    recommended_gpu_memory_mb: float = 0
    min_compute_score: float = 1.0
    context_length: int = 4096
    requires_gpu: bool = False
    quantization: str = "q4_0"
    priority: int = 100
    cost_per_million: float = 0.0
    api_endpoint: str = ""
    api_key_env: str = ""


@dataclass
class HardwareProfile:
    """硬件配置"""
    cpu_cores: int = 4
    cpu_score: float = 1.0
    total_memory_gb: float = 8.0
    available_memory_gb: float = 4.0
    has_gpu: bool = False
    gpu_name: str = ""
    total_gpu_memory_mb: float = 0
    available_gpu_memory_mb: float = 0
    network_available: bool = True
    network_latency_ms: float = 50.0


@dataclass
class RoutingDecision:
    """路由决策"""
    timestamp: str = ""
    selected_provider: ModelProvider = ModelProvider.LOCAL_OLLAMA
    selected_model: str = ""
    reason: str = ""
    confidence: float = 1.0
    meets_requirements: bool = True
    alternatives: List = field(default_factory=list)


class HardwareProfiler:
    """硬件能力评估"""
    
    @staticmethod
    def get_current_profile() -> HardwareProfile:
        """获取当前硬件配置"""
        cpu_cores = psutil.cpu_count()
        cpu_score = cpu_cores / 4.0
        
        vm = psutil.virtual_memory()
        total_memory_gb = vm.total / (1024 ** 3)
        available_memory_gb = vm.available / (1024 ** 3)
        
        has_gpu = False
        gpu_name = ""
        total_gpu_memory_mb = 0
        available_gpu_memory_mb = 0
        
        try:
            import pynvml
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            if device_count > 0:
                has_gpu = True
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode('utf-8')
                gpu_name = name
                total_gpu_memory_mb = mem_info.total / (1024 ** 2)
                available_gpu_memory_mb = mem_info.free / (1024 ** 2)
        except:
            pass
        
        return HardwareProfile(
            cpu_cores=cpu_cores,
            cpu_score=cpu_score,
            total_memory_gb=total_memory_gb,
            available_memory_gb=available_memory_gb,
            has_gpu=has_gpu,
            gpu_name=gpu_name,
            total_gpu_memory_mb=total_gpu_memory_mb,
            available_gpu_memory_mb=available_gpu_memory_mb,
        )
    
    @staticmethod
    def can_run_model(profile: HardwareProfile, requirements: ModelRequirements) -> tuple:
        """检查硬件是否能运行模型"""
        reasons = []
        can_run = True
        
        if profile.available_memory_gb < requirements.min_memory_gb:
            can_run = False
            reasons.append(f"RAM: need {requirements.min_memory_gb}GB, have {profile.available_memory_gb:.1f}GB")
        
        if requirements.requires_gpu and not profile.has_gpu:
            can_run = False
            reasons.append("GPU required but not available")
        
        if requirements.min_gpu_memory_mb > 0:
            if profile.available_gpu_memory_mb < requirements.min_gpu_memory_mb:
                can_run = False
                reasons.append(f"GPU RAM: need {requirements.min_gpu_memory_mb}MB, have {profile.available_gpu_memory_mb:.0f}MB")
        
        if profile.cpu_score < requirements.min_compute_score:
            can_run = False
            reasons.append(f"CPU score: need {requirements.min_compute_score}, have {profile.cpu_score:.1f}")
        
        return can_run, "; ".join(reasons) if reasons else "OK"


# 模型注册表
MODEL_REGISTRY = {
    # 本地 Ollama 模型
    "llama3.2:1b": ModelRequirements("llama3.2:1b", ModelProvider.LOCAL_OLLAMA, 
                                       min_memory_gb=1.5, priority=50),
    "qwen2.5:0.5b": ModelRequirements("qwen2.5:0.5b", ModelProvider.LOCAL_OLLAMA,
                                        min_memory_gb=1.0, priority=45),
    "phi3:3.8b": ModelRequirements("phi3:3.8b", ModelProvider.LOCAL_OLLAMA,
                                      min_memory_gb=2.5, priority=60),
    "qwen2.5:3b": ModelRequirements("qwen2.5:3b", ModelProvider.LOCAL_OLLAMA,
                                      min_memory_gb=2.5, priority=35),
    "qwen2.5:7b": ModelRequirements("qwen2.5:7b", ModelProvider.LOCAL_OLLAMA,
                                      min_memory_gb=5.5, priority=25),
    "qwen2.5:14b": ModelRequirements("qwen2.5:14b", ModelProvider.LOCAL_OLLAMA,
                                        min_memory_gb=10.0, priority=15),
    "qwen2.5:32b": ModelRequirements("qwen2.5:32b", ModelProvider.LOCAL_OLLAMA,
                                        min_memory_gb=20.0, priority=10, requires_gpu=True),
    "llama3.1:70b": ModelRequirements("llama3.1:70b", ModelProvider.LOCAL_OLLAMA,
                                         min_memory_gb=40.0, priority=5, requires_gpu=True),
    
    # 远程模型
    "deepseek-chat": ModelRequirements("deepseek-chat", ModelProvider.REMOTE_DEEPSEEK,
                                        priority=100, cost_per_million=0.14),
    "deepseek-coder": ModelRequirements("deepseek-coder", ModelProvider.REMOTE_DEEPSEEK,
                                         priority=95, cost_per_million=0.14),
    "gpt-4o-mini": ModelRequirements("gpt-4o-mini", ModelProvider.REMOTE_OPENAI,
                                        priority=90, cost_per_million=0.15),
    "gpt-4o": ModelRequirements("gpt-4o", ModelProvider.REMOTE_OPENAI,
                                  priority=85, cost_per_million=2.5),
}


class SmartModelRouter:
    """智能模型路由器"""
    
    def __init__(self, prefer_local: bool = True, fallback_to_remote: bool = True):
        self.prefer_local = prefer_local
        self.fallback_to_remote = fallback_to_remote
    
    def route(self, preferred_model: Optional[str] = None,
              task_type: Optional[str] = None) -> RoutingDecision:
        """路由决策"""
        profile = HardwareProfiler.get_current_profile()
        decision = RoutingDecision()
        decision.hardware_profile = profile
        
        if preferred_model:
            return self._route_specific(preferred_model, profile, decision)
        
        if task_type:
            return self._route_by_task(task_type, profile, decision)
        
        return self._route_default(profile, decision)
    
    def _route_specific(self, model_name: str, profile: HardwareProfile, decision: RoutingDecision) -> RoutingDecision:
        """指定模型"""
        req = MODEL_REGISTRY.get(model_name)
        if not req:
            req = ModelRequirements(model_name, ModelProvider.LOCAL_OLLAMA)
            MODEL_REGISTRY[model_name] = req
        
        can_run, reason = HardwareProfiler.can_run_model(profile, req)
        decision.selected_model = model_name
        decision.meets_requirements = can_run
        decision.reason = reason
        
        if can_run:
            decision.selected_provider = req.provider
        elif self.fallback_to_remote:
            decision.selected_provider = ModelProvider.REMOTE_DEEPSEEK
            decision.selected_model = "deepseek-chat"
            decision.reason = f"Local {model_name} unavailable, fallback to remote"
        
        return decision
    
    def _route_by_task(self, task_type: str, profile: HardwareProfile, decision: RoutingDecision) -> RoutingDecision:
        """按任务类型"""
        task_preferences = {
            "fast": ["qwen2.5:0.5b", "llama3.2:1b", "phi3:3.8b"],
            "chat": ["qwen2.5:7b", "llama3.2:3b", "deepseek-chat"],
            "coding": ["qwen2.5:14b", "deepseek-coder", "gpt-4o"],
            "reasoning": ["qwen2.5:32b", "llama3.1:70b", "deepseek-chat"],
        }
        
        preferred = task_preferences.get(task_type.lower(), task_preferences["chat"])
        
        for model_name in preferred:
            req = MODEL_REGISTRY.get(model_name)
            if not req:
                continue
            
            can_run, reason = HardwareProfiler.can_run_model(profile, req)
            
            if can_run and req.provider == ModelProvider.LOCAL_OLLAMA:
                decision.selected_provider = ModelProvider.LOCAL_OLLAMA
                decision.selected_model = model_name
                decision.reason = f"Task '{task_type}': {reason}"
                decision.confidence = 0.9
                return decision
        
        # 远程
        if self.fallback_to_remote:
            for model_name in preferred:
                req = MODEL_REGISTRY.get(model_name)
                if req and req.provider != ModelProvider.LOCAL_OLLAMA:
                    decision.selected_provider = req.provider
                    decision.selected_model = model_name
                    decision.reason = f"Task '{task_type}': using remote model"
                    return decision
        
        return self._route_default(profile, decision)
    
    def _route_default(self, profile: HardwareProfile, decision: RoutingDecision) -> RoutingDecision:
        """默认路由"""
        local_models = sorted(
            [m for name, m in MODEL_REGISTRY.items() if m.provider == ModelProvider.LOCAL_OLLAMA],
            key=lambda m: m.priority
        )
        
        for req in local_models:
            can_run, reason = HardwareProfiler.can_run_model(profile, req)
            if can_run:
                decision.selected_provider = ModelProvider.LOCAL_OLLAMA
                decision.selected_model = req.name
                decision.reason = f"Best local model: {reason}"
                decision.confidence = 0.8
                return decision
        
        # 远程兜底
        decision.selected_provider = ModelProvider.REMOTE_DEEPSEEK
        decision.selected_model = "deepseek-chat"
        decision.reason = "No local model available, using remote"
        decision.confidence = 0.7
        return decision


def print_decision(decision: RoutingDecision, title: str):
    """打印决策"""
    print(f"\n{'='*55}")
    print(f"  {title}")
    print('='*55)
    print(f"  Model:   {decision.selected_model}")
    print(f"  Provider: {decision.selected_provider.value}")
    print(f"  Reason:  {decision.reason}")
    print(f"  Confidence: {decision.confidence:.0%}")
    print(f"  Meets requirements: {'Yes' if decision.meets_requirements else 'No'}")


def main():
    print("""
    +========================================================+
    |         Smart Model Router - Test Suite               |
    +========================================================+
    """)
    
    # 1. 硬件评估
    print("\n[1] Hardware Profile")
    print("-" * 55)
    profile = HardwareProfiler.get_current_profile()
    print(f"  CPU:   {profile.cpu_cores} cores, score {profile.cpu_score:.1f}")
    print(f"  RAM:   {profile.available_memory_gb:.1f}GB / {profile.total_memory_gb:.1f}GB")
    print(f"  GPU:   {'Yes' if profile.has_gpu else 'No'} {profile.gpu_name}")
    if profile.has_gpu:
        print(f"  VRAM:  {profile.available_gpu_memory_mb:.0f}MB / {profile.total_gpu_memory_mb:.0f}MB")
    
    # 2. 模型兼容性
    print("\n[2] Model Compatibility")
    print("-" * 55)
    test_models = ["qwen2.5:0.5b", "qwen2.5:3b", "qwen2.5:7b", "qwen2.5:14b", "qwen2.5:32b"]
    for name in test_models:
        req = MODEL_REGISTRY.get(name)
        if req:
            can_run, reason = HardwareProfiler.can_run_model(profile, req)
            status = "[OK]" if can_run else "[XX]"
            print(f"  {status} {name}: {reason}")
    
    # 3. 路由决策测试
    print("\n[3] Routing Decisions")
    print("-" * 55)
    
    router = SmartModelRouter()
    
    print_decision(router.route(preferred_model="qwen2.5:14b"), "Specific: qwen2.5:14b")
    print_decision(router.route(preferred_model="qwen2.5:0.5b"), "Specific: qwen2.5:0.5b")
    print_decision(router.route(task_type="fast"), "Task: fast")
    print_decision(router.route(task_type="chat"), "Task: chat")
    print_decision(router.route(task_type="coding"), "Task: coding")
    print_decision(router.route(task_type="reasoning"), "Task: reasoning")
    print_decision(router.route(), "Default")
    
    print("\n" + "="*55)
    print("  Test Complete!")
    print("="*55)


if __name__ == "__main__":
    main()
