"""
模型评分模块

多维度评分系统：
- 质量评分 (Quality)
- 速度评分 (Speed)
- 适配度评分 (Fit)
- 上下文评分 (Context)
"""

import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum


# ============ 评分维度 ============

class ScoreDimension(Enum):
    """评分维度"""
    QUALITY = "quality"
    SPEED = "speed"
    FIT = "fit"
    CONTEXT = "context"


@dataclass
class ModelScore:
    """模型评分"""
    quality: float = 0.0
    speed: float = 0.0
    fit: float = 0.0
    context: float = 0.0
    composite: float = 0.0
    
    def calculate_composite(
        self,
        weights: Dict[str, float] = None
    ) -> float:
        """
        计算综合评分
        
        Args:
            weights: 各维度权重
            
        Returns:
            float: 综合评分
        """
        if weights is None:
            weights = {"quality": 0.3, "speed": 0.2, "fit": 0.3, "context": 0.2}
        
        self.composite = (
            self.quality * weights.get("quality", 0.3) +
            self.speed * weights.get("speed", 0.2) +
            self.fit * weights.get("fit", 0.3) +
            self.context * weights.get("context", 0.2)
        )
        
        return self.composite


@dataclass
class ModelInfo:
    """模型信息"""
    name: str
    provider: str
    params: float  # 参数量（B）
    context_length: int  # 上下文长度
    quantization: str = "fp16"
    base_score: float = 0.5  # 基础质量评分
    use_cases: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============ 质量评分器 ============

class QualityScorer:
    """
    质量评分器
    
    评估模型的生成质量
    """
    
    def __init__(self):
        self.quality_cache: Dict[str, float] = {}
    
    def score(self, model: ModelInfo) -> float:
        """
        评分
        
        Args:
            model: 模型信息
            
        Returns:
            float: 质量评分 (0-1)
        """
        cache_key = f"{model.name}_{model.quantization}"
        
        if cache_key in self.quality_cache:
            return self.quality_cache[cache_key]
        
        # 基于参数量估算
        # 通常参数量越大，质量越高
        if model.params <= 7:
            base_quality = 0.6
        elif model.params <= 13:
            base_quality = 0.7
        elif model.params <= 30:
            base_quality = 0.8
        elif model.params <= 70:
            base_quality = 0.85
        else:
            base_quality = 0.9
        
        # 量化影响
        quant_mult = {
            "fp32": 1.0,
            "fp16": 0.98,
            "bf16": 0.98,
            "int8": 0.90,
            "int4": 0.80,
            "Q8_0": 0.88,
            "Q4_K_M": 0.85,
            "Q4_0": 0.82,
            "Q3_K_M": 0.78,
            "Q2_K": 0.72,
        }
        quant_factor = quant_mult.get(model.quantization.upper(), 0.85)
        
        score = base_quality * quant_factor * model.base_score
        
        # 缓存
        self.quality_cache[cache_key] = min(1.0, score)
        
        return min(1.0, score)


# ============ 速度评分器 ============

class SpeedScorer:
    """
    速度评分器
    
    估算模型的推理速度
    """
    
    def __init__(self):
        self.hardware_spec = None
        self.speed_cache: Dict[str, float] = {}
    
    def set_hardware(self, hardware_spec):
        """设置硬件规格"""
        self.hardware_spec = hardware_spec
    
    def estimate_speed(
        self,
        model: ModelInfo,
        hardware_spec = None
    ) -> float:
        """
        估算推理速度
        
        Args:
            model: 模型信息
            hardware_spec: 硬件规格
            
        Returns:
            float: 估计的 tok/s
        """
        if hardware_spec is None:
            hardware_spec = self.hardware_spec
        
        cache_key = f"{model.name}_{hardware_spec.backend.value if hardware_spec else 'unknown'}"
        
        if cache_key in self.speed_cache:
            return self.speed_cache[cache_key]
        
        # 基础速度估算（基于参数量）
        base_speed = 50.0 / (model.params ** 0.5)  # tok/s
        
        # 硬件因素
        if hardware_spec:
            # CPU 因素
            cpu_factor = min(1.0, hardware_spec.cpu_cores / 8.0) * 0.3
            
            # 内存因素
            ram_factor = min(1.0, hardware_spec.ram_gb / 32.0) * 0.2
            
            # GPU 因素
            gpu_factor = 0.0
            if hardware_spec.gpu_count > 0:
                vram_gb = hardware_spec.gpu_memory_gb
                if model.params <= 7 and vram_gb >= 6:
                    gpu_factor = 0.4
                elif model.params <= 13 and vram_gb >= 10:
                    gpu_factor = 0.45
                elif model.params <= 30 and vram_gb >= 20:
                    gpu_factor = 0.45
                elif model.params > 30 and vram_gb >= 24:
                    gpu_factor = 0.5
                else:
                    gpu_factor = 0.2
            else:
                gpu_factor = 0.1  # CPU only
            
            # 量化因素
            quant_factor = {
                "fp32": 0.3,
                "fp16": 0.5,
                "bf16": 0.5,
                "int8": 0.7,
                "int4": 0.9,
                "Q8_0": 0.75,
                "Q4_K_M": 0.85,
                "Q4_0": 0.88,
                "Q3_K_M": 0.92,
                "Q2_K": 0.95,
            }.get(model.quantization.upper(), 0.7)
            
            # 计算速度
            speed = base_speed * (cpu_factor + ram_factor + gpu_factor) * quant_factor * 10
        
        else:
            speed = base_speed * 5
        
        # 缓存
        self.speed_cache[cache_key] = speed
        
        return speed
    
    def score(self, model: ModelInfo, hardware_spec = None) -> float:
        """
        速度评分
        
        Args:
            model: 模型信息
            hardware_spec: 硬件规格
            
        Returns:
            float: 速度评分 (0-1)
        """
        speed = self.estimate_speed(model, hardware_spec)
        
        # 归一化到 0-1，假设 50 tok/s 为满分
        score = min(1.0, speed / 50.0)
        
        return score


# ============ 适配度评分器 ============

class FitScorer:
    """
    适配度评分器
    
    评估模型与硬件的匹配程度
    """
    
    def __init__(self):
        self.hardware_spec = None
    
    def set_hardware(self, hardware_spec):
        """设置硬件规格"""
        self.hardware_spec = hardware_spec
    
    def calculate_fit(
        self,
        model: ModelInfo,
        hardware_spec = None
    ) -> float:
        """
        计算适配度
        
        Args:
            model: 模型信息
            hardware_spec: 硬件规格
            
        Returns:
            float: 适配度 (0-1)
        """
        if hardware_spec is None:
            hardware_spec = self.hardware_spec
        
        if not hardware_spec:
            return 0.5
        
        # 估算模型内存需求
        quant_mult = {
            "fp32": 4.0,
            "fp16": 2.0,
            "bf16": 2.0,
            "int8": 1.0,
            "int4": 0.5,
            "Q8_0": 1.0,
            "Q4_K_M": 0.65,
            "Q4_0": 0.55,
            "Q3_K_M": 0.45,
            "Q2_K": 0.35,
        }
        bytes_per_param = quant_mult.get(model.quantization.upper(), 2.0)
        model_memory_gb = model.params * bytes_per_param / (1024 ** 3)  # B to GB
        
        # 检查是否能在 GPU 运行
        if hardware_spec.gpu_count > 0:
            if model_memory_gb <= hardware_spec.gpu_memory_gb * 0.9:
                # 能在 GPU 运行
                gpu_fit = 1.0
            elif model_memory_gb <= hardware_spec.ram_gb * 0.8:
                # 能在 CPU + GPU 混合运行
                gpu_fit = 0.6
            else:
                # 只能在 CPU 运行
                gpu_fit = 0.3
        else:
            # 无 GPU
            if model_memory_gb <= hardware_spec.ram_gb * 0.5:
                gpu_fit = 0.5
            else:
                gpu_fit = 0.2
        
        # 检查参数量是否适合
        if model.params <= 7:
            param_fit = 1.0
        elif model.params <= 13:
            param_fit = 0.9 if hardware_spec.ram_gb >= 16 else 0.6
        elif model.params <= 30:
            param_fit = 0.8 if hardware_spec.ram_gb >= 32 else 0.4
        elif model.params <= 70:
            param_fit = 0.7 if hardware_spec.ram_gb >= 64 else 0.3
        else:
            param_fit = 0.5 if hardware_spec.ram_gb >= 128 else 0.2
        
        # 综合适配度
        fit = gpu_fit * 0.6 + param_fit * 0.4
        
        return min(1.0, max(0.0, fit))
    
    def score(self, model: ModelInfo, hardware_spec = None) -> float:
        """
        适配度评分
        
        Args:
            model: 模型信息
            hardware_spec: 硬件规格
            
        Returns:
            float: 适配度评分 (0-1)
        """
        return self.calculate_fit(model, hardware_spec)


# ============ 上下文评分器 ============

class ContextScorer:
    """
    上下文评分器
    
    评估模型的上下文处理能力
    """
    
    def __init__(self):
        self.max_context = 32768  # 最大上下文长度参考
    
    def score(self, model: ModelInfo) -> float:
        """
        上下文评分
        
        Args:
            model: 模型信息
            
        Returns:
            float: 上下文评分 (0-1)
        """
        # 归一化
        score = model.context_length / self.max_context
        
        return min(1.0, score)


# ============ 综合评分器 ============

class ModelScorer:
    """
    综合模型评分器
    
    结合质量、速度、适配度、上下文四个维度
    """
    
    def __init__(self):
        self.quality_scorer = QualityScorer()
        self.speed_scorer = SpeedScorer()
        self.fit_scorer = FitScorer()
        self.context_scorer = ContextScorer()
        
        # 权重配置
        self.weights = {
            "quality": 0.3,
            "speed": 0.2,
            "fit": 0.3,
            "context": 0.2,
        }
    
    def set_hardware(self, hardware_spec):
        """设置硬件规格"""
        self.speed_scorer.set_hardware(hardware_spec)
        self.fit_scorer.set_hardware(hardware_spec)
    
    def set_weights(
        self,
        quality: float = 0.3,
        speed: float = 0.2,
        fit: float = 0.3,
        context: float = 0.2
    ):
        """设置评分权重"""
        total = quality + speed + fit + context
        self.weights = {
            "quality": quality / total,
            "speed": speed / total,
            "fit": fit / total,
            "context": context / total,
        }
    
    def score(self, model: ModelInfo, hardware_spec = None) -> ModelScore:
        """
        综合评分
        
        Args:
            model: 模型信息
            hardware_spec: 硬件规格
            
        Returns:
            ModelScore: 模型评分
        """
        score = ModelScore()
        
        score.quality = self.quality_scorer.score(model)
        score.speed = self.speed_scorer.score(model, hardware_spec)
        score.fit = self.fit_scorer.score(model, hardware_spec)
        score.context = self.context_scorer.score(model)
        
        score.calculate_composite(self.weights)
        
        return score
    
    def score_multiple(
        self,
        models: List[ModelInfo],
        hardware_spec = None
    ) -> List[tuple]:
        """
        对多个模型评分并排序
        
        Args:
            models: 模型列表
            hardware_spec: 硬件规格
            
        Returns:
            List[tuple]: (model, score) 列表，按综合评分排序
        """
        scored_models = []
        
        for model in models:
            score = self.score(model, hardware_spec)
            scored_models.append((model, score))
        
        # 按综合评分排序
        scored_models.sort(key=lambda x: x[1].composite, reverse=True)
        
        return scored_models


# ============ 导出 ============

__all__ = [
    "ScoreDimension",
    "ModelScore",
    "ModelInfo",
    "QualityScorer",
    "SpeedScorer",
    "FitScorer",
    "ContextScorer",
    "ModelScorer",
]
