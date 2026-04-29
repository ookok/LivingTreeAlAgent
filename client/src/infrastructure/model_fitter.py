"""
LLMFit 风格的智能模型选择器

参考 LLMFit 项目原理，根据系统资源智能选择最合适的模型：
- 检测 GPU 显存、CPU 核心、内存
- 根据模型的实际资源需求进行匹配
- 考虑模型的量化级别
- 提供多个备选方案

项目参考: https://github.com/haotian-liu/LLMFit
"""

import platform
import psutil
import json
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx
from loguru import logger


class ModelInfo:
    """模型信息"""
    def __init__(self, name: str, tag: str = "", size_gb: float = 0, 
                 params_b: str = "", description: str = ""):
        self.name = name
        self.tag = tag
        self.size_gb = size_gb
        self.params_b = params_b
        self.description = description
    
    def __repr__(self):
        return f"ModelInfo(name={self.name}, size={self.size_gb}GB, params={self.params_b})"


class SystemResources:
    """系统资源信息"""
    def __init__(self):
        self.os_type = platform.system().lower()
        self.cpu_cores = psutil.cpu_count(logical=False) or 4
        self.cpu_threads = psutil.cpu_count(logical=True) or 8
        self.ram_gb = round(psutil.virtual_memory().total / 1e9, 2)
        self.gpu_vram_gb = self._get_gpu_memory()
        self.gpu_count = self._get_gpu_count()
    
    def _get_gpu_memory(self) -> float:
        """获取 GPU 显存"""
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            pynvml.nvmlShutdown()
            return info.total / 1e9
        except:
            pass
        
        try:
            if self.os_type == "linux":
                result = subprocess.run(
                    ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    return float(result.stdout.strip()) / 1024
            else:
                result = subprocess.run(
                    ["nvidia-smi.exe", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    return float(result.stdout.strip()) / 1024
        except:
            pass
        
        return 0.0
    
    def _get_gpu_count(self) -> int:
        """获取 GPU 数量"""
        try:
            import pynvml
            pynvml.nvmlInit()
            count = pynvml.nvmlDeviceGetCount()
            pynvml.nvmlShutdown()
            return count
        except:
            pass
        return 0
    
    def __repr__(self):
        return (f"SystemResources(os={self.os_type}, cpu={self.cpu_cores} cores, "
                f"ram={self.ram_gb}GB, gpu={self.gpu_vram_gb}GB, gpus={self.gpu_count})")


class ModelLibrarySync:
    """从外部模型库同步模型列表（使用优化的注册表）"""
    
    @classmethod
    def sync_models(cls, output_path: str = None, force: bool = False) -> bool:
        """
        从外部模型库同步模型列表（使用索引+分片策略）
        
        Args:
            output_path: 输出目录路径（可选）
            force: 是否强制更新（忽略缓存时间）
        
        Returns:
            是否同步成功
        """
        from .model_registry import ModelRegistrySync
        
        sync = ModelRegistrySync(output_path)
        return sync.sync_models(force)
    
    @classmethod
    def load_synced_models(cls, model_family: str = None) -> List[dict]:
        """
        加载已同步的模型列表（使用懒加载注册表）
        
        Args:
            model_family: 模型系列过滤（如 "qwen"）
        
        Returns:
            模型列表
        """
        from .model_registry import LazyModelRegistry
        
        try:
            registry = LazyModelRegistry()
            
            if model_family:
                # 获取指定系列的模型
                model_names = registry.get_models_by_family(model_family)
                models = []
                for name in model_names[:20]:  # 限制数量
                    info = registry.get_model_info(name)
                    if info:
                        models.append(info)
                return models
            else:
                # 返回所有模型（仅索引信息）
                registry.load_index()
                return [{"name": name, **info} for name, info in registry.index.get("models", {}).items()]
        except Exception as e:
            logger.error(f"加载模型列表失败: {e}")
            return []


class ModelFitter:
    """LLMFit 风格的智能模型选择器"""
    
    # 模型资源需求估算（基于 LLMFit 公式）
    # 显存需求 ≈ 参数数量 (B) × 2 (FP16) × 安全系数
    # 内存需求 ≈ 显存需求 × 1.5 (CPU fallback)
    MODEL_REQUIREMENTS = {
        # Qwen 3.6 系列
        "qwen3.6": {"params_b": 235, "base_vram_gb": 460, "recommended_vram": 48, "quantized": True},
        "qwen3.6:32b": {"params_b": 32, "base_vram_gb": 64, "recommended_vram": 32, "quantized": True},
        "qwen3.6:14b": {"params_b": 14, "base_vram_gb": 28, "recommended_vram": 16, "quantized": True},
        "qwen3.6:8b": {"params_b": 8, "base_vram_gb": 16, "recommended_vram": 8, "quantized": True},
        
        # Qwen 3.5 系列
        "qwen3.5:122b": {"params_b": 122, "base_vram_gb": 244, "recommended_vram": 64, "quantized": True},
        "qwen3.5:35b": {"params_b": 35, "base_vram_gb": 70, "recommended_vram": 32, "quantized": True},
        "qwen3.5:27b": {"params_b": 27, "base_vram_gb": 54, "recommended_vram": 24, "quantized": True},
        "qwen3.5:9b": {"params_b": 9, "base_vram_gb": 18, "recommended_vram": 12, "quantized": True},
        "qwen3.5:4b": {"params_b": 4, "base_vram_gb": 8, "recommended_vram": 6, "quantized": True},
        "qwen3.5:2b": {"params_b": 2, "base_vram_gb": 4, "recommended_vram": 3, "quantized": True},
        "qwen3.5:0.8b": {"params_b": 0.8, "base_vram_gb": 1.6, "recommended_vram": 2, "quantized": True},
        "qwen3.5:latest": {"params_b": 4, "base_vram_gb": 8, "recommended_vram": 6, "quantized": True},
        
        # Qwen 2.5 系列（备用）
        "qwen2.5:0.5b": {"params_b": 0.5, "base_vram_gb": 1, "recommended_vram": 1, "quantized": True},
        "qwen2.5:1.5b": {"params_b": 1.5, "base_vram_gb": 3, "recommended_vram": 2, "quantized": True},
        "qwen2.5:7b": {"params_b": 7, "base_vram_gb": 14, "recommended_vram": 8, "quantized": True},
        "qwen2.5:14b": {"params_b": 14, "base_vram_gb": 28, "recommended_vram": 16, "quantized": True},
    }
    
    def __init__(self):
        self._logger = logger.bind(component="ModelFitter")
        self.system = SystemResources()
        self._available_models = {}
        self._use_synced_models = True  # 是否使用同步的模型列表
    
    def fit(self, model_family: str = "qwen") -> List[Tuple[str, float, str]]:
        """
        根据系统资源选择最合适的模型
        
        Returns:
            List of tuples: (model_name, score, reason)
            - score: 适配度分数 (0-100)
            - reason: 选择原因
        """
        self._logger.info(f"系统资源检测: {self.system}")
        
        # 获取可用模型列表
        available_models = self._fetch_available_models(model_family)
        self._logger.info(f"可用模型: {len(available_models)} 个")
        
        # 根据资源评分模型
        scored_models = []
        for model in available_models:
            score, reason = self._score_model(model.name)
            if score > 0:
                scored_models.append((model, score, reason))
        
        # 按评分排序
        scored_models.sort(key=lambda x: x[1], reverse=True)
        
        # 返回结果
        results = []
        for model, score, reason in scored_models[:5]:
            results.append((model.name, score, reason))
            self._logger.info(f"模型 {model.name}: 评分 {score} - {reason}")
        
        return results
    
    def _fetch_available_models(self, model_family: str) -> List[ModelInfo]:
        """从外部模型库或 Ollama 官方库获取可用模型（使用懒加载注册表）"""
        models = []
        
        # 优先使用同步的模型列表（索引+分片策略）
        if self._use_synced_models:
            from .model_registry import get_model_registry
            
            try:
                registry = get_model_registry()
                
                # 获取指定系列的候选模型
                if model_family == "qwen":
                    # 搜索所有 qwen 相关系列
                    candidates = []
                    for family in ["qwen", "qwen2", "qwen3"]:
                        try:
                            candidates.extend(registry.get_candidates_for_family(family, 10))
                        except:
                            pass
                else:
                    candidates = registry.get_candidates_for_family(model_family, 10)
                
                if candidates:
                    self._logger.info(f"使用注册表模型列表，共 {len(candidates)} 个候选模型")
                    for m in candidates:
                        name = m.get("name", "")
                        if name:
                            req = self.MODEL_REQUIREMENTS.get(name)
                            models.append(ModelInfo(
                                name=name,
                                tag=m.get("tag", ""),
                                size_gb=req["base_vram_gb"] if req else 0,
                                params_b=str(req["params_b"]) if req else "",
                                description=m.get("description", "")
                            ))
                    return models
            except Exception as e:
                self._logger.warning(f"使用注册表失败，回退到备用方案: {e}")
        
        # 备用：从 Ollama 官方库获取
        families = {
            "qwen": ["qwen3.6", "qwen3.5", "qwen2.5"],
            "qwen3.6": ["qwen3.6"],
            "qwen3.5": ["qwen3.5"],
            "qwen2.5": ["qwen2.5"],
        }
        
        for family in families.get(model_family, ["qwen3.5"]):
            url = f"https://registry.ollama.ai/v2/library/{family}/tags/list"
            try:
                response = httpx.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                for tag in data.get("tags", []):
                    name = f"{family}:{tag}" if tag != "latest" else family
                    req = self.MODEL_REQUIREMENTS.get(name)
                    size_gb = req["base_vram_gb"] if req else 0
                    params_b = req["params_b"] if req else ""
                    
                    models.append(ModelInfo(
                        name=name,
                        tag=tag,
                        size_gb=size_gb,
                        params_b=str(params_b),
                        description=f"{family} {tag}"
                    ))
            except Exception as e:
                self._logger.warning(f"获取 {family} 模型列表失败: {e}")
                models.extend(self._get_fallback_models(family))
        
        return models
    
    def _get_fallback_models(self, family: str) -> List[ModelInfo]:
        """备用模型列表"""
        fallback = {
            "qwen3.6": [
                ModelInfo("qwen3.6", "latest", 48, "235B", "Qwen 3.6 MoE"),
                ModelInfo("qwen3.6:32b", "32b", 32, "32B", "Qwen 3.6 32B"),
                ModelInfo("qwen3.6:14b", "14b", 16, "14B", "Qwen 3.6 14B"),
                ModelInfo("qwen3.6:8b", "8b", 8, "8B", "Qwen 3.6 8B"),
            ],
            "qwen3.5": [
                ModelInfo("qwen3.5", "latest", 6, "4B", "Qwen 3.5 4B"),
                ModelInfo("qwen3.5:122b", "122b", 64, "122B", "Qwen 3.5 122B"),
                ModelInfo("qwen3.5:35b", "35b", 32, "35B", "Qwen 3.5 35B"),
                ModelInfo("qwen3.5:27b", "27b", 24, "27B", "Qwen 3.5 27B"),
                ModelInfo("qwen3.5:9b", "9b", 12, "9B", "Qwen 3.5 9B"),
                ModelInfo("qwen3.5:4b", "4b", 6, "4B", "Qwen 3.5 4B"),
                ModelInfo("qwen3.5:2b", "2b", 3, "2B", "Qwen 3.5 2B"),
                ModelInfo("qwen3.5:0.8b", "0.8b", 2, "0.8B", "Qwen 3.5 0.8B"),
            ],
            "qwen2.5": [
                ModelInfo("qwen2.5:0.5b", "0.5b", 1, "0.5B", "Qwen 2.5 0.5B"),
                ModelInfo("qwen2.5:1.5b", "1.5b", 2, "1.5B", "Qwen 2.5 1.5B"),
                ModelInfo("qwen2.5:7b", "7b", 8, "7B", "Qwen 2.5 7B"),
                ModelInfo("qwen2.5:14b", "14b", 16, "14B", "Qwen 2.5 14B"),
            ],
        }
        return fallback.get(family, [])
    
    def _score_model(self, model_name: str) -> Tuple[float, str]:
        """
        为模型评分（基于 LLMFit 原理）
        
        评分因素:
        1. GPU 显存充足度 (40分)
        2. 内存充足度 (30分)
        3. CPU 核心数 (20分)
        4. 模型偏好 (10分) - 优先选择更新的模型
        """
        req = self.MODEL_REQUIREMENTS.get(model_name)
        if not req:
            return 0, "未知模型"
        
        scores = []
        reasons = []
        
        # 1. GPU 显存评分 (40分)
        if self.system.gpu_vram_gb >= req["recommended_vram"]:
            gpu_score = 40
            reasons.append(f"GPU显存充足 ({self.system.gpu_vram_gb}GB >= {req['recommended_vram']}GB)")
        elif self.system.gpu_vram_gb > 0:
            ratio = min(self.system.gpu_vram_gb / req["recommended_vram"], 1)
            gpu_score = int(ratio * 40)
            reasons.append(f"GPU显存紧张 ({self.system.gpu_vram_gb}GB / {req['recommended_vram']}GB)")
        else:
            gpu_score = 0
            reasons.append("无GPU加速")
        scores.append(gpu_score)
        
        # 2. 内存评分 (30分)
        memory_needed = req["recommended_vram"] * 1.5
        if self.system.ram_gb >= memory_needed:
            ram_score = 30
            reasons.append(f"内存充足 ({self.system.ram_gb}GB >= {memory_needed:.1f}GB)")
        else:
            ratio = min(self.system.ram_gb / memory_needed, 1)
            ram_score = int(ratio * 30)
            reasons.append(f"内存紧张 ({self.system.ram_gb}GB / {memory_needed:.1f}GB)")
        scores.append(ram_score)
        
        # 3. CPU 评分 (20分)
        min_cores = max(4, int(req["params_b"] / 3))
        if self.system.cpu_cores >= min_cores:
            cpu_score = 20
            reasons.append(f"CPU核心充足 ({self.system.cpu_cores} >= {min_cores})")
        else:
            ratio = min(self.system.cpu_cores / min_cores, 1)
            cpu_score = int(ratio * 20)
            reasons.append(f"CPU核心较少 ({self.system.cpu_cores} / {min_cores})")
        scores.append(cpu_score)
        
        # 4. 模型偏好评分 (10分) - 优先 Qwen 3.6 > 3.5 > 2.5
        if "qwen3.6" in model_name:
            version_score = 10
            reasons.append("推荐: Qwen 3.6 系列")
        elif "qwen3.5" in model_name:
            version_score = 7
            reasons.append("推荐: Qwen 3.5 系列")
        elif "qwen2.5" in model_name:
            version_score = 4
            reasons.append("备用: Qwen 2.5 系列")
        else:
            version_score = 5
        scores.append(version_score)
        
        total_score = sum(scores)
        return total_score, "; ".join(reasons)
    
    def select_best_model(self, model_family: str = "qwen") -> str:
        """选择最佳模型"""
        results = self.fit(model_family)
        if results:
            return results[0][0]
        return "qwen3.5:latest"
    
    def get_system_info(self) -> Dict:
        """获取系统信息"""
        return {
            "os": self.system.os_type,
            "cpu_cores": self.system.cpu_cores,
            "cpu_threads": self.system.cpu_threads,
            "ram_gb": self.system.ram_gb,
            "gpu_vram_gb": self.system.gpu_vram_gb,
            "gpu_count": self.system.gpu_count,
        }


# 单例模式
_model_fitter = None

def get_model_fitter() -> ModelFitter:
    """获取模型选择器实例"""
    global _model_fitter
    if _model_fitter is None:
        _model_fitter = ModelFitter()
    return _model_fitter


def fit_model(model_family: str = "qwen") -> str:
    """快捷函数：选择最佳模型"""
    fitter = get_model_fitter()
    return fitter.select_best_model(model_family)


def get_fit_results(model_family: str = "qwen") -> List[Tuple[str, float, str]]:
    """快捷函数：获取所有模型的适配结果"""
    fitter = get_model_fitter()
    return fitter.fit(model_family)


if __name__ == "__main__":
    # 测试模型选择器
    fitter = ModelFitter()
    
    print("=" * 60)
    print("LLMFit 风格模型选择器测试")
    print("=" * 60)
    print(f"系统资源: {fitter.system}")
    print()
    
    results = fitter.fit("qwen")
    print("模型适配结果:")
    print("-" * 60)
    for i, (model, score, reason) in enumerate(results, 1):
        print(f"{i}. {model}")
        print(f"   评分: {score}/100")
        print(f"   原因: {reason}")
        print()
    
    best_model = fitter.select_best_model()
    print(f"推荐模型: {best_model}")
    print("=" * 60)