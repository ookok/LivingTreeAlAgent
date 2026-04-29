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
    """LLMFit 风格的智能模型选择器（完全动态获取模型列表）"""
    
    def __init__(self):
        self._logger = logger.bind(component="ModelFitter")
        self.system = SystemResources()
        self._available_models = {}
        self._use_synced_models = True  # 是否使用同步的模型列表
        self._model_requirements = {}  # 动态获取的模型资源需求
    
    def _get_model_requirements(self, model_name: str) -> Optional[dict]:
        """
        动态获取模型资源需求
        
        从模型名称自动推断资源需求：
        - 根据参数数量估算显存需求
        - 支持常见的模型命名约定
        
        Args:
            model_name: 模型名称（如 qwen3.5:4b）
        
        Returns:
            模型资源需求字典
        """
        # 如果已经缓存，直接返回
        if model_name in self._model_requirements:
            return self._model_requirements[model_name]
        
        # 尝试从模型名称推断资源需求
        requirements = self._infer_requirements_from_name(model_name)
        
        # 缓存结果
        self._model_requirements[model_name] = requirements
        return requirements
    
    def _infer_requirements_from_name(self, model_name: str) -> dict:
        """
        从模型名称推断资源需求
        
        支持的命名模式：
        - qwen3.6:8b → params_b=8, recommended_vram=8
        - qwen3.5:35b → params_b=35, recommended_vram=32
        - llama3:8b → params_b=8, recommended_vram=8
        - smollm2 → params_b=1.7, recommended_vram=2
        """
        model_lower = model_name.lower()
        
        # 提取参数数量
        params_b = self._extract_params_from_name(model_lower)
        
        # 计算显存需求
        # 基础显存 = 参数数量 × 2 (FP16)
        # 推荐显存 = 基础显存 × 安全系数（考虑量化后约为原始的 0.5-0.75）
        base_vram_gb = params_b * 2
        recommended_vram = max(2, int(params_b * 1.5))
        
        # 系列优先级（新版本优先）
        if "qwen3.6" in model_lower:
            version_priority = 10
        elif "qwen3.5" in model_lower:
            version_priority = 7
        elif "qwen3" in model_lower:
            version_priority = 6
        elif "qwen2.5" in model_lower:
            version_priority = 4
        elif "qwen2" in model_lower:
            version_priority = 3
        else:
            version_priority = 5
        
        return {
            "params_b": params_b,
            "base_vram_gb": base_vram_gb,
            "recommended_vram": recommended_vram,
            "quantized": True,
            "description": model_name,
            "version_priority": version_priority
        }
    
    def _extract_params_from_name(self, model_name: str) -> float:
        """
        从模型名称提取参数数量
        
        支持的格式：
        - qwen3.5:4b → 4
        - qwen3.6:32b → 32
        - llama3:8b → 8
        - smollm2 → 1.7 (默认)
        """
        import re
        
        # 匹配数字+b 或数字+B 的模式
        match = re.search(r'(\d+(?:\.\d+)?)\s*[bB]', model_name)
        if match:
            return float(match.group(1))
        
        # 针对没有明确参数的模型使用默认值
        if "smollm" in model_name:
            return 1.7
        elif "tinyllama" in model_name:
            return 1.1
        elif "phi3" in model_name:
            return 3.8
        elif "phi2" in model_name:
            return 2.7
        elif "phi" in model_name:
            return 1.3
        elif "gemma" in model_name:
            # 默认 gemma 为 7B
            return 7
        
        # 默认返回 4B（常见的基础模型大小）
        return 4.0
    
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
                    req = self._get_model_requirements(name)
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
        """
        动态生成备用模型列表（不再硬编码）
        
        根据系列名称动态生成常见的模型变体
        """
        models = []
        
        # 常见的模型标签
        common_tags = ["", ":latest", ":8b", ":14b", ":32b", ":7b", ":4b", ":2b"]
        
        for tag in common_tags[:6]:  # 限制数量
            model_name = family + tag
            if tag == "" or tag == ":latest":
                display_tag = "latest"
            else:
                display_tag = tag[1:]  # 去掉冒号
            
            req = self._get_model_requirements(model_name)
            models.append(ModelInfo(
                name=model_name,
                tag=display_tag,
                size_gb=req["base_vram_gb"] if req else 0,
                params_b=str(req["params_b"]) if req else "",
                description=f"{family} {display_tag}"
            ))
        
        return models
    
    def _score_model(self, model_name: str) -> Tuple[float, str]:
        """
        为模型评分（基于 LLMFit 原理）
        
        评分因素:
        1. GPU 显存充足度 (40分)
        2. 内存充足度 (30分)
        3. CPU 核心数 (20分)
        4. 模型偏好 (10分) - 优先选择更新的模型
        
        模型需求从动态获取，不再硬编码
        """
        req = self._get_model_requirements(model_name)
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