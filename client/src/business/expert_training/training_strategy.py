"""
训练策略模块 (Training Strategy)

针对V100 64GB GPU的优化训练策略：
1. 模型选型与量化
2. LoRA 微调配置
3. 损失函数设计（含工业特异性惩罚）
4. 训练流程管理

核心原则：充分利用V100的显存优势，最大化工业任务的训练效果
"""

import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class LORAConfig:
    """LoRA 配置"""
    r: int = 32              # 秩（工业任务需更高秩）
    alpha: int = 64          # alpha
    dropout: float = 0.05    # dropout
    target_modules: List[str] = field(default_factory=lambda: [
        "q_proj", "v_proj", "k_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj"
    ])
    bias: str = "none"
    task_type: str = "CAUSAL_LM"


@dataclass
class TrainingHyperParams:
    """训练超参数"""
    learning_rate: float = 1e-5      # 工业数据噪声少，可用稍大学习率
    per_device_train_batch_size: int = 4
    per_device_eval_batch_size: int = 4
    gradient_accumulation_steps: int = 8
    num_train_epochs: int = 3         # 工业数据不追求多轮，防止过拟合
    max_steps: int = -1              # -1表示由epochs决定
    warmup_steps: int = 500
    weight_decay: float = 0.01
    logging_steps: int = 10
    evaluation_strategy: str = "epoch"
    save_strategy: str = "epoch"
    fp16: bool = True                # bfloat16训练
    optim: str = "adamw_torch"


@dataclass
class LossConfig:
    """损失函数配置"""
    use_custom_loss: bool = True
    term_penalty_weight: float = 0.1   # 非行业术语惩罚权重
    format_reward_weight: float = 0.05 # 格式正确奖励权重
    uncertainty_penalty_weight: float = 0.05  # 缺少不确定性说明惩罚


@dataclass
class ModelConfig:
    """模型配置"""
    model_name: str = "Qwen/Qwen2.5-7B-Instruct"
    tokenizer_name: str = ""
    load_in_4bit: bool = False
    load_in_8bit: bool = False
    device_map: str = "auto"
    max_seq_length: int = 4096
    truncation_side: str = "right"


class TrainingStrategy:
    """
    训练策略管理器
    
    针对V100 64GB GPU优化的训练策略：
    - 模型选型：Qwen2.5-7B 或 DeepSeek-V3-7B
    - 量化策略：训练bfloat16，推理int8
    - LoRA配置：高秩学习复杂逻辑
    - 自定义损失：术语惩罚 + 格式奖励
    """
    
    def __init__(self):
        # 配置
        self.lora_config = LORAConfig()
        self.hyper_params = TrainingHyperParams()
        self.loss_config = LossConfig()
        self.model_config = ModelConfig()
        
        # 训练状态
        self.training_started = False
        self.current_epoch = 0
        self.global_step = 0
        
        # 统计
        self.total_training_time = 0
        self.best_metrics = {}
        
        # 工业术语库（用于损失计算）
        self.industry_terms = {
            "机械制造": ["公差", "配合", "粗糙度", "热处理", "CNC", "加工中心", "轴承", "齿轮"],
            "电子电气": ["PLC", "MCU", "PCB", "继电器", "变频器", "传感器", "伺服", "控制"],
            "化工": ["反应釜", "精馏塔", "换热器", "催化剂", "工艺", "参数", "介质"],
            "汽车": ["ECU", "ESP", "ABS", "动力", "电池", "控制", "系统"],
            "能源": ["光伏", "风电", "储能", "逆变", "充电", "电网", "功率"]
        }
        
        # 非专业术语（惩罚词）
        self.unprofessional_terms = ["大概", "可能", "也许", "差不多", "应该", "好像", "据说"]
        
        # 标准格式模式（奖励）
        self.standard_formats = [
            r'GB/T\s*\d+(?:\.\d+)*',
            r'GB\s*\d+(?:\.\d+)*',
            r'IEC\s*\d+',
            r'ISO\s*\d+'
        ]
        
        print("[TrainingStrategy] 初始化完成")
    
    def configure_for_stage(self, stage: int):
        """
        根据训练阶段配置策略
        
        Args:
            stage: 训练阶段 (1-4)
        """
        if stage == 1:
            # 基础理解：简单任务，较低秩
            self.lora_config.r = 16
            self.lora_config.alpha = 32
            self.hyper_params.learning_rate = 2e-5
            self.hyper_params.num_train_epochs = 3
            
        elif stage == 2:
            # 逻辑推理：中等复杂度
            self.lora_config.r = 24
            self.lora_config.alpha = 48
            self.hyper_params.learning_rate = 1.5e-5
            self.hyper_params.num_train_epochs = 3
            
        elif stage == 3:
            # 任务规划：核心阶段，高秩
            self.lora_config.r = 32
            self.lora_config.alpha = 64
            self.hyper_params.learning_rate = 1e-5
            self.hyper_params.num_train_epochs = 4
            
        elif stage == 4:
            # 全流程生成：端到端任务
            self.lora_config.r = 32
            self.lora_config.alpha = 64
            self.hyper_params.learning_rate = 5e-6  # 微调，学习率更小
            self.hyper_params.num_train_epochs = 2
            
        print(f"[TrainingStrategy] 已配置阶段 {stage} 的训练策略")
    
    def configure_for_hardware(self, gpu_memory_gb: int = 64):
        """
        根据GPU显存配置策略
        
        Args:
            gpu_memory_gb: GPU显存大小（GB）
        """
        if gpu_memory_gb >= 64:
            # V100 64GB：完整配置
            self.hyper_params.per_device_train_batch_size = 4
            self.hyper_params.gradient_accumulation_steps = 8
            self.model_config.max_seq_length = 4096
            self.model_config.load_in_4bit = False
            self.model_config.load_in_8bit = False
            
        elif gpu_memory_gb >= 40:
            # A100 40GB：稍微压缩
            self.hyper_params.per_device_train_batch_size = 3
            self.hyper_params.gradient_accumulation_steps = 8
            self.model_config.max_seq_length = 3072
            self.model_config.load_in_4bit = False
            
        elif gpu_memory_gb >= 24:
            # RTX 3090/A10：需要量化
            self.hyper_params.per_device_train_batch_size = 2
            self.hyper_params.gradient_accumulation_steps = 8
            self.model_config.max_seq_length = 2048
            self.model_config.load_in_4bit = True
            
        else:
            # 更小显存：重度量化
            self.hyper_params.per_device_train_batch_size = 1
            self.hyper_params.gradient_accumulation_steps = 16
            self.model_config.max_seq_length = 1024
            self.model_config.load_in_4bit = True
        
        print(f"[TrainingStrategy] 已配置 {gpu_memory_gb}GB GPU 的训练策略")
    
    def set_model(self, model_name: str):
        """
        设置模型
        
        Args:
            model_name: 模型名称
        """
        self.model_config.model_name = model_name
        
        # 自动设置tokenizer
        if not self.model_config.tokenizer_name:
            self.model_config.tokenizer_name = model_name
        
        print(f"[TrainingStrategy] 设置模型: {model_name}")
    
    def calculate_custom_loss(self, logits, labels, generated_text: str) -> float:
        """
        计算自定义损失（包含工业特异性惩罚）
        
        Args:
            logits: 模型输出logits
            labels: 标签
            generated_text: 生成的文本
            
        Returns:
            调整后的损失
        """
        # 基础交叉熵损失（实际实现中会使用PyTorch计算）
        base_loss = 0.0  # 占位
        
        if not self.loss_config.use_custom_loss:
            return base_loss
        
        penalty = 0.0
        reward = 0.0
        
        # 术语惩罚：对非专业术语给予惩罚
        for term in self.unprofessional_terms:
            if term in generated_text:
                penalty += self.loss_config.term_penalty_weight
        
        # 格式奖励：对正确格式给予奖励
        import re
        for pattern in self.standard_formats:
            if re.search(pattern, generated_text):
                reward += self.loss_config.format_reward_weight
        
        # 不确定性惩罚：如果应该有不确定性说明但没有
        if self._should_have_uncertainty(generated_text) and "需确认" not in generated_text:
            penalty += self.loss_config.uncertainty_penalty_weight
        
        # 最终损失 = 基础损失 + 惩罚 - 奖励
        final_loss = base_loss + penalty - reward
        
        return final_loss
    
    def _should_have_uncertainty(self, text: str) -> bool:
        """判断文本是否应该包含不确定性说明"""
        # 如果文本包含以下模式，应该有不确定性说明
        uncertainty_triggers = [
            "推荐", "建议", "可能", "需要", "确认", "检查"
        ]
        
        return any(trigger in text for trigger in uncertainty_triggers)
    
    def export_config(self, filepath: str):
        """导出配置为JSON"""
        config = {
            "lora": {
                "r": self.lora_config.r,
                "alpha": self.lora_config.alpha,
                "dropout": self.lora_config.dropout,
                "target_modules": self.lora_config.target_modules,
                "bias": self.lora_config.bias,
                "task_type": self.lora_config.task_type
            },
            "hyper_params": {
                "learning_rate": self.hyper_params.learning_rate,
                "per_device_train_batch_size": self.hyper_params.per_device_train_batch_size,
                "per_device_eval_batch_size": self.hyper_params.per_device_eval_batch_size,
                "gradient_accumulation_steps": self.hyper_params.gradient_accumulation_steps,
                "num_train_epochs": self.hyper_params.num_train_epochs,
                "max_steps": self.hyper_params.max_steps,
                "warmup_steps": self.hyper_params.warmup_steps,
                "weight_decay": self.hyper_params.weight_decay,
                "logging_steps": self.hyper_params.logging_steps,
                "evaluation_strategy": self.hyper_params.evaluation_strategy,
                "save_strategy": self.hyper_params.save_strategy,
                "fp16": self.hyper_params.fp16,
                "optim": self.hyper_params.optim
            },
            "loss": {
                "use_custom_loss": self.loss_config.use_custom_loss,
                "term_penalty_weight": self.loss_config.term_penalty_weight,
                "format_reward_weight": self.loss_config.format_reward_weight,
                "uncertainty_penalty_weight": self.loss_config.uncertainty_penalty_weight
            },
            "model": {
                "model_name": self.model_config.model_name,
                "tokenizer_name": self.model_config.tokenizer_name,
                "load_in_4bit": self.model_config.load_in_4bit,
                "load_in_8bit": self.model_config.load_in_8bit,
                "device_map": self.model_config.device_map,
                "max_seq_length": self.model_config.max_seq_length,
                "truncation_side": self.model_config.truncation_side
            }
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        print(f"[TrainingStrategy] 配置已导出到 {filepath}")
    
    def import_config(self, filepath: str):
        """从JSON导入配置"""
        with open(filepath, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 更新配置
        if "lora" in config:
            lora = config["lora"]
            self.lora_config.r = lora.get("r", 32)
            self.lora_config.alpha = lora.get("alpha", 64)
            self.lora_config.dropout = lora.get("dropout", 0.05)
        
        if "hyper_params" in config:
            hp = config["hyper_params"]
            self.hyper_params.learning_rate = hp.get("learning_rate", 1e-5)
            self.hyper_params.per_device_train_batch_size = hp.get("per_device_train_batch_size", 4)
            self.hyper_params.gradient_accumulation_steps = hp.get("gradient_accumulation_steps", 8)
            self.hyper_params.num_train_epochs = hp.get("num_train_epochs", 3)
        
        if "model" in config:
            model = config["model"]
            self.model_config.model_name = model.get("model_name", "Qwen/Qwen2.5-7B-Instruct")
            self.model_config.max_seq_length = model.get("max_seq_length", 4096)
        
        print(f"[TrainingStrategy] 配置已从 {filepath} 导入")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "training_started": self.training_started,
            "current_epoch": self.current_epoch,
            "global_step": self.global_step,
            "total_training_time": self.total_training_time,
            "best_metrics": self.best_metrics,
            "model_name": self.model_config.model_name,
            "lora_rank": self.lora_config.r,
            "batch_size": self.hyper_params.per_device_train_batch_size,
            "gradient_accumulation": self.hyper_params.gradient_accumulation_steps
        }


def create_training_strategy() -> TrainingStrategy:
    """创建训练策略实例"""
    return TrainingStrategy()


# 推荐的模型列表
RECOMMENDED_MODELS = [
    {
        "name": "Qwen/Qwen2.5-7B-Instruct",
        "description": "阿里巴巴Qwen2.5系列，中文能力强，工业任务性价比最高",
        "parameter_count": "7B",
        "quantization": "bfloat16/int8"
    },
    {
        "name": "deepseek-ai/DeepSeek-V3-Lite-Instruct",
        "description": "DeepSeek-V3系列，推理能力强，适合复杂逻辑任务",
        "parameter_count": "7B",
        "quantization": "bfloat16/int8"
    },
    {
        "name": "Qwen/Qwen2.5-14B-Instruct",
        "description": "更大模型，更强能力，但显存需求更高",
        "parameter_count": "14B",
        "quantization": "int8/4bit"
    }
]


__all__ = [
    "TrainingStrategy",
    "LORAConfig",
    "TrainingHyperParams",
    "LossConfig",
    "ModelConfig",
    "create_training_strategy",
    "RECOMMENDED_MODELS"
]