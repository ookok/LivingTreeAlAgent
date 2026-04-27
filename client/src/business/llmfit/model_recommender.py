"""
模型推荐模块

硬件感知模型推荐：
- 硬件检测
- 模型筛选
- 多维度评分
- 推荐输出
"""

from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

from .hardware_detector import HardwareDetector, HardwareSpec, HardwareBackend
from .model_scorer import ModelScorer, ModelScore, ModelInfo


# ============ 使用场景 ============

class UseCase(Enum):
    """使用场景"""
    GENERAL = "general"          # 通用
    CODING = "coding"           # 编程
    REASONING = "reasoning"    # 推理
    CREATIVE = "creative"      # 创意写作
    SUMMARY = "summary"        # 摘要
    TRANSLATION = "translation"  # 翻译
    INSTRUCTION = "instruction"  # 指令跟随


@dataclass
class ModelRecommendation:
    """模型推荐"""
    model: ModelInfo
    score: ModelScore
    fit_level: str  # "perfect", "good", "marginal", "runnable"
    recommended_quantization: str
    estimated_speed: float  # tok/s
    notes: List[str] = field(default_factory=list)


@dataclass
class RecommendationResult:
    """推荐结果"""
    hardware: HardwareSpec
    use_case: UseCase
    recommendations: List[ModelRecommendation]
    total_models_scored: int = 0
    timestamp: float = field(default_factory=lambda: __import__("time").time())


# ============ 模型数据库 ============

class ModelDatabase:
    """
    模型数据库
    
    存储和管理可用模型信息
    """
    
    def __init__(self):
        self.models: List[ModelInfo] = []
        self._init_default_models()
    
    def _init_default_models(self):
        """初始化默认模型"""
        # Llama 系列
        self.add_model(ModelInfo(
            name="llama-3.2-1b",
            provider="Meta",
            params=1.0,
            context_length=128000,
            quantization="bf16",
            base_score=0.75,
            use_cases=["general", "coding"],
        ))
        
        self.add_model(ModelInfo(
            name="llama-3.2-3b",
            provider="Meta",
            params=3.0,
            context_length=128000,
            quantization="bf16",
            base_score=0.80,
            use_cases=["general", "coding"],
        ))
        
        self.add_model(ModelInfo(
            name="llama-3.1-8b",
            provider="Meta",
            params=8.0,
            context_length=128000,
            quantization="fp16",
            base_score=0.85,
            use_cases=["general", "coding", "reasoning"],
        ))
        
        self.add_model(ModelInfo(
            name="llama-3.1-70b",
            provider="Meta",
            params=70.0,
            context_length=128000,
            quantization="fp8",
            base_score=0.92,
            use_cases=["general", "coding", "reasoning"],
        ))
        
        self.add_model(ModelInfo(
            name="llama-3.1-405b",
            provider="Meta",
            params=405.0,
            context_length=128000,
            quantization="fp8",
            base_score=0.95,
            use_cases=["general", "reasoning"],
        ))
        
        # Qwen 系列
        self.add_model(ModelInfo(
            name="qwen-2.5-0.5b",
            provider="Alibaba",
            params=0.5,
            context_length=32768,
            quantization="fp16",
            base_score=0.70,
            use_cases=["general"],
        ))
        
        self.add_model(ModelInfo(
            name="qwen-2.5-1.5b",
            provider="Alibaba",
            params=1.5,
            context_length=32768,
            quantization="fp16",
            base_score=0.75,
            use_cases=["general", "coding"],
        ))
        
        self.add_model(ModelInfo(
            name="qwen-2.5-7b",
            provider="Alibaba",
            params=7.0,
            context_length=32768,
            quantization="fp16",
            base_score=0.83,
            use_cases=["general", "coding", "reasoning"],
        ))
        
        self.add_model(ModelInfo(
            name="qwen-2.5-14b",
            provider="Alibaba",
            params=14.0,
            context_length=32768,
            quantization="fp16",
            base_score=0.87,
            use_cases=["general", "coding", "reasoning", "creative"],
        ))
        
        self.add_model(ModelInfo(
            name="qwen-2.5-72b",
            provider="Alibaba",
            params=72.0,
            context_length=32768,
            quantization="fp8",
            base_score=0.91,
            use_cases=["general", "coding", "reasoning", "creative"],
        ))
        
        # Phi 系列
        self.add_model(ModelInfo(
            name="phi-3.5-mini-3.8b",
            provider="Microsoft",
            params=3.8,
            context_length=4096,
            quantization="fp16",
            base_score=0.78,
            use_cases=["general", "coding"],
        ))
        
        self.add_model(ModelInfo(
            name="phi-3.5-small-7b",
            provider="Microsoft",
            params=7.0,
            context_length=8192,
            quantization="fp16",
            base_score=0.82,
            use_cases=["general", "coding", "reasoning"],
        ))
        
        # Gemma 系列
        self.add_model(ModelInfo(
            name="gemma-2-2b",
            provider="Google",
            params=2.0,
            context_length=8192,
            quantization="fp16",
            base_score=0.76,
            use_cases=["general"],
        ))
        
        self.add_model(ModelInfo(
            name="gemma-2-9b",
            provider="Google",
            params=9.0,
            context_length=8192,
            quantization="fp16",
            base_score=0.84,
            use_cases=["general", "coding"],
        ))
        
        self.add_model(ModelInfo(
            name="gemma-2-27b",
            provider="Google",
            params=27.0,
            context_length=8192,
            quantization="fp16",
            base_score=0.88,
            use_cases=["general", "reasoning"],
        ))
        
        # DeepSeek 系列
        self.add_model(ModelInfo(
            name="deepseek-coder-1.3b",
            provider="DeepSeek",
            params=1.3,
            context_length=16384,
            quantization="fp16",
            base_score=0.77,
            use_cases=["coding"],
        ))
        
        self.add_model(ModelInfo(
            name="deepseek-coder-6.7b",
            provider="DeepSeek",
            params=6.7,
            context_length=16384,
            quantization="fp16",
            base_score=0.84,
            use_cases=["coding", "general"],
        ))
        
        self.add_model(ModelInfo(
            name="deepseek-coder-33b",
            provider="DeepSeek",
            params=33.0,
            context_length=16384,
            quantization="fp8",
            base_score=0.90,
            use_cases=["coding", "reasoning"],
        ))
        
        self.add_model(ModelInfo(
            name="deepseek-v2.5-7b",
            provider="DeepSeek",
            params=7.0,
            context_length=131072,
            quantization="fp16",
            base_score=0.85,
            use_cases=["general", "reasoning", "coding"],
        ))
        
        # Yi 系列
        self.add_model(ModelInfo(
            name="yi-1.5-6b",
            provider="01.AI",
            params=6.0,
            context_length=4096,
            quantization="fp16",
            base_score=0.81,
            use_cases=["general", "coding"],
        ))
        
        self.add_model(ModelInfo(
            name="yi-1.5-9b",
            provider="01.AI",
            params=9.0,
            context_length=4096,
            quantization="fp16",
            base_score=0.83,
            use_cases=["general", "coding", "reasoning"],
        ))
        
        self.add_model(ModelInfo(
            name="yi-1.5-34b",
            provider="01.AI",
            params=34.0,
            context_length=4096,
            quantization="fp8",
            base_score=0.89,
            use_cases=["general", "reasoning"],
        ))
        
        # WizardCoder 系列
        self.add_model(ModelInfo(
            name="wizardcoder-3-python-7b",
            provider="WizardLM",
            params=7.0,
            context_length=16384,
            quantization="fp16",
            base_score=0.83,
            use_cases=["coding"],
        ))
        
        self.add_model(ModelInfo(
            name="wizardcoder-3-python-34b",
            provider="WizardLM",
            params=34.0,
            context_length=16384,
            quantization="fp8",
            base_score=0.90,
            use_cases=["coding", "reasoning"],
        ))
    
    def add_model(self, model: ModelInfo):
        """添加模型"""
        self.models.append(model)
    
    def get_model(self, name: str) -> Optional[ModelInfo]:
        """获取模型"""
        for model in self.models:
            if model.name.lower() == name.lower():
                return model
        return None
    
    def filter_by_use_case(self, use_case: UseCase) -> List[ModelInfo]:
        """按使用场景筛选"""
        return [
            model for model in self.models
            if use_case.value in model.use_cases
        ]
    
    def filter_runnable(self, hardware_spec: HardwareSpec) -> List[ModelInfo]:
        """筛选能在指定硬件上运行的模型"""
        runnable = []
        
        for model in self.models:
            # 估算内存需求
            quant_mult = {
                "fp32": 4.0,
                "fp16": 2.0,
                "bf16": 2.0,
                "int8": 1.0,
                "int4": 0.5,
                "fp8": 1.5,
                "Q8_0": 1.0,
                "Q4_K_M": 0.65,
                "Q4_0": 0.55,
            }
            bytes_per_param = quant_mult.get(model.quantization.upper(), 2.0)
            model_memory_gb = model.params * bytes_per_param
            
            # 检查是否能运行
            if hardware_spec.gpu_count > 0:
                # 有 GPU
                if model_memory_gb <= hardware_spec.gpu_memory_gb * 1.2:
                    runnable.append(model)
                elif model_memory_gb <= hardware_spec.ram_gb * 0.9:
                    runnable.append(model)
            else:
                # 无 GPU
                if model_memory_gb <= hardware_spec.ram_gb * 0.7:
                    runnable.append(model)
        
        return runnable
    
    def list_all(self) -> List[ModelInfo]:
        """列出所有模型"""
        return self.models.copy()


# ============ 模型推荐器 ============

class ModelRecommender:
    """
    硬件感知模型推荐器
    
    根据硬件配置和使用场景推荐适合的模型
    """
    
    def __init__(self):
        self.hardware_detector = HardwareDetector()
        self.model_scorer = ModelScorer()
        self.model_database = ModelDatabase()
    
    def detect_hardware(self) -> HardwareSpec:
        """检测硬件"""
        return self.hardware_detector.detect()
    
    def recommend(
        self,
        hardware_spec: HardwareSpec = None,
        use_case: UseCase = UseCase.GENERAL,
        top_k: int = 5,
        min_fit: float = 0.3
    ) -> RecommendationResult:
        """
        推荐模型
        
        Args:
            hardware_spec: 硬件规格（可选，自动检测）
            use_case: 使用场景
            top_k: 返回数量
            min_fit: 最低适配度
            
        Returns:
            RecommendationResult: 推荐结果
        """
        # 检测硬件
        if hardware_spec is None:
            hardware_spec = self.hardware_detector.detect()
        
        # 设置评分器硬件
        self.model_scorer.set_hardware(hardware_spec)
        
        # 筛选能在当前硬件上运行的模型
        if use_case != UseCase.GENERAL:
            candidates = self.model_database.filter_by_use_case(use_case)
        else:
            candidates = self.model_database.list_all()
        
        runnable_candidates = [
            m for m in candidates
            if self._can_run(m, hardware_spec)
        ]
        
        # 评分
        scored_models = self.model_scorer.score_multiple(runnable_candidates, hardware_spec)
        
        # 构建推荐
        recommendations = []
        for model, score in scored_models:
            fit_level = self._get_fit_level(score.fit)
            
            if score.fit >= min_fit:
                recommendation = ModelRecommendation(
                    model=model,
                    score=score,
                    fit_level=fit_level,
                    recommended_quantization=self._recommend_quantization(model, hardware_spec),
                    estimated_speed=self.model_scorer.speed_scorer.estimate_speed(model, hardware_spec),
                    notes=self._generate_notes(model, score, hardware_spec),
                )
                recommendations.append(recommendation)
            
            if len(recommendations) >= top_k:
                break
        
        return RecommendationResult(
            hardware=hardware_spec,
            use_case=use_case,
            recommendations=recommendations,
            total_models_scored=len(runnable_candidates),
        )
    
    def _can_run(self, model: ModelInfo, hardware_spec: HardwareSpec) -> bool:
        """检查模型是否能运行"""
        quant_mult = {
            "fp32": 4.0,
            "fp16": 2.0,
            "bf16": 2.0,
            "int8": 1.0,
            "int4": 0.5,
            "fp8": 1.5,
            "Q8_0": 1.0,
            "Q4_K_M": 0.65,
            "Q4_0": 0.55,
        }
        bytes_per_param = quant_mult.get(model.quantization.upper(), 2.0)
        model_memory_gb = model.params * bytes_per_param
        
        # 有 GPU
        if hardware_spec.gpu_count > 0:
            if model_memory_gb <= hardware_spec.gpu_memory_gb * 1.2:
                return True
            elif model_memory_gb <= hardware_spec.ram_gb * 0.9:
                return True
        else:
            # 无 GPU
            if model_memory_gb <= hardware_spec.ram_gb * 0.6:
                return True
        
        return False
    
    def _get_fit_level(self, fit_score: float) -> str:
        """获取适配级别"""
        if fit_score >= 0.8:
            return "perfect"
        elif fit_score >= 0.6:
            return "good"
        elif fit_score >= 0.4:
            return "marginal"
        else:
            return "runnable"
    
    def _recommend_quantization(self, model: ModelInfo, hardware_spec: HardwareSpec) -> str:
        """推荐量化方式"""
        quant_mult = {
            "fp32": 4.0,
            "fp16": 2.0,
            "bf16": 2.0,
            "int8": 1.0,
            "int4": 0.5,
            "fp8": 1.5,
            "Q8_0": 1.0,
            "Q4_K_M": 0.65,
            "Q4_0": 0.55,
        }
        bytes_per_param = quant_mult.get(model.quantization.upper(), 2.0)
        model_memory_gb = model.params * bytes_per_param
        
        available_vram = hardware_spec.gpu_memory_gb if hardware_spec.gpu_count > 0 else hardware_spec.ram_gb * 0.5
        
        # 根据可用显存推荐量化
        if model_memory_gb <= hardware_spec.gpu_memory_gb * 0.6 if hardware_spec.gpu_count > 0 else True:
            return model.quantization  # 保持原始量化
        
        if model_memory_gb <= hardware_spec.gpu_memory_gb * 0.9:
            return "int8"
        elif model_memory_gb <= hardware_spec.gpu_memory_gb * 1.2:
            return "Q4_K_M"
        elif model_memory_gb <= hardware_spec.gpu_memory_gb * 1.5:
            return "Q4_0"
        else:
            return "Q3_K_M"
    
    def _generate_notes(
        self,
        model: ModelInfo,
        score: ModelScore,
        hardware_spec: HardwareSpec
    ) -> List[str]:
        """生成备注"""
        notes = []
        
        if score.fit >= 0.8:
            notes.append("此模型在此硬件上运行效果最佳")
        elif score.fit < 0.5:
            notes.append("可能需要较长的加载时间")
        
        if hardware_spec.gpu_count == 0:
            notes.append("将在 CPU 上运行，速度可能较慢")
        
        if model.params > 30 and hardware_spec.gpu_count == 0:
            notes.append("建议使用量化版本以减少内存占用")
        
        return notes
    
    def get_hardware_summary(self, hardware_spec: HardwareSpec = None) -> str:
        """获取硬件摘要"""
        if hardware_spec is None:
            hardware_spec = self.hardware_detector.detect()
        
        summary = f"""硬件配置:
- CPU: {hardware_spec.cpu_model} ({hardware_spec.cpu_cores} 核心)
- RAM: {hardware_spec.ram_gb:.1f} GB ({hardware_spec.ram_available_gb:.1f} GB 可用)
- GPU: {hardware_spec.gpu_count} x {hardware_spec.gpu_name} ({hardware_spec.gpu_memory_gb:.1f} GB VRAM)
- 后端: {hardware_spec.backend.value}
- OS: {hardware_spec.os_name} {hardware_spec.os_version}
"""
        return summary


# ============ 导出 ============

__all__ = [
    "UseCase",
    "ModelRecommendation",
    "RecommendationResult",
    "ModelDatabase",
    "ModelRecommender",
]
