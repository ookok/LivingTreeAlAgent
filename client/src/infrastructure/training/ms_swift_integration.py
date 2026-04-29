"""
MS-SWIFT 训练框架集成

阿里官方训练框架，对 Qwen 系列支持最完善。
通过 CLI 调用方式，由决策层调度。

项目地址: https://github.com/modelscope/swift

支持的训练方式：
- LoRA 微调
- 全参微调
- 知识蒸馏
- 指令微调
"""

import subprocess
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Union
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class TrainingConfig:
    """训练配置"""
    model_name: str = "Qwen/Qwen3.5-4B"
    dataset_name: str = ""
    output_dir: str = "./output"
    training_type: str = "lora"  # lora, full, distill
    epochs: int = 3
    batch_size: int = 8
    learning_rate: float = 2e-5
    lora_rank: int = 8
    lora_alpha: int = 16
    max_seq_length: int = 2048
    fp16: bool = True
    gradient_accumulation_steps: int = 4
    logging_steps: int = 10
    save_steps: int = 100
    eval_steps: int = 100
    device: str = "auto"  # auto, cpu, gpu, mps
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "model_name": self.model_name,
            "dataset_name": self.dataset_name,
            "output_dir": self.output_dir,
            "training_type": self.training_type,
            "epochs": self.epochs,
            "batch_size": self.batch_size,
            "learning_rate": self.learning_rate,
            "lora_rank": self.lora_rank,
            "lora_alpha": self.lora_alpha,
            "max_seq_length": self.max_seq_length,
            "fp16": self.fp16,
            "gradient_accumulation_steps": self.gradient_accumulation_steps,
            "logging_steps": self.logging_steps,
            "save_steps": self.save_steps,
            "eval_steps": self.eval_steps,
            "device": self.device
        }


@dataclass
class TrainingResult:
    """训练结果"""
    success: bool
    model_path: Optional[str] = None
    training_time: Optional[float] = None
    loss: Optional[float] = None
    eval_loss: Optional[float] = None
    error: Optional[str] = None
    metrics: Dict = field(default_factory=dict)


class MSSwiftIntegration:
    """
    MS-SWIFT 训练框架集成
    
    通过 CLI 调用方式与 MS-SWIFT 交互
    """
    
    # 支持的模型
    SUPPORTED_MODELS = [
        "Qwen/Qwen3.6-35B",
        "Qwen/Qwen3.6-14B",
        "Qwen/Qwen3.6-8B",
        "Qwen/Qwen3.5-72B",
        "Qwen/Qwen3.5-32B",
        "Qwen/Qwen3.5-14B",
        "Qwen/Qwen3.5-7B",
        "Qwen/Qwen3.5-4B",
        "Qwen/Qwen3.5-2B",
        "Qwen/Qwen2.5-7B",
        "Qwen/Qwen2.5-14B",
    ]
    
    # 支持的训练类型
    TRAINING_TYPES = {
        "lora": "LoRA 微调",
        "full": "全参微调",
        "distill": "知识蒸馏",
        "sft": "指令微调"
    }
    
    def __init__(self):
        self._logger = logger.bind(component="MSSwiftIntegration")
        self._swift_available = self._check_swift_available()
    
    def _check_swift_available(self) -> bool:
        """检查 MS-SWIFT 是否安装"""
        try:
            result = subprocess.run(
                ["swift", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                self._logger.info(f"MS-SWIFT 版本: {result.stdout.strip()}")
                return True
            else:
                self._logger.warning(f"MS-SWIFT 不可用: {result.stderr}")
                return False
        except FileNotFoundError:
            self._logger.warning("MS-SWIFT 未安装，请执行: pip install ms-swift")
            return False
        except Exception as e:
            self._logger.warning(f"检查 MS-SWIFT 失败: {e}")
            return False
    
    def is_available(self) -> bool:
        """检查 MS-SWIFT 是否可用"""
        return self._swift_available
    
    def install_swift(self) -> bool:
        """安装 MS-SWIFT"""
        try:
            self._logger.info("正在安装 MS-SWIFT...")
            result = subprocess.run(
                ["pip", "install", "ms-swift", "-U"],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                self._logger.info("MS-SWIFT 安装成功")
                self._swift_available = True
                return True
            else:
                self._logger.error(f"MS-SWIFT 安装失败: {result.stderr}")
                return False
        except Exception as e:
            self._logger.error(f"安装 MS-SWIFT 异常: {e}")
            return False
    
    def train(self, config: TrainingConfig) -> TrainingResult:
        """
        执行训练任务
        
        Args:
            config: 训练配置
        
        Returns:
            训练结果
        """
        if not self._swift_available:
            return TrainingResult(
                success=False,
                error="MS-SWIFT 不可用，请先安装"
            )
        
        try:
            # 创建输出目录
            output_path = Path(config.output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # 构建命令
            cmd = self._build_train_command(config)
            
            self._logger.info(f"开始训练: {config.model_name}")
            self._logger.info(f"训练类型: {config.training_type}")
            self._logger.info(f"输出目录: {config.output_dir}")
            
            # 执行训练命令
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600 * 24,  # 最长24小时
                cwd=os.getcwd()
            )
            
            if result.returncode == 0:
                # 解析训练结果
                return self._parse_train_result(result.stdout, config.output_dir)
            else:
                error_msg = f"训练失败: {result.stderr[:1000]}"
                self._logger.error(error_msg)
                return TrainingResult(
                    success=False,
                    error=error_msg
                )
                
        except subprocess.TimeoutExpired:
            return TrainingResult(
                success=False,
                error="训练超时"
            )
        except Exception as e:
            error_msg = f"训练异常: {str(e)}"
            self._logger.error(error_msg)
            return TrainingResult(
                success=False,
                error=error_msg
            )
    
    def _build_train_command(self, config: TrainingConfig) -> List[str]:
        """构建训练命令"""
        cmd = ["swift", "sft"]
        
        # 基础参数
        cmd.extend(["--model", config.model_name])
        
        if config.dataset_name:
            cmd.extend(["--dataset", config.dataset_name])
        
        cmd.extend(["--output-dir", config.output_dir])
        
        # 训练类型
        if config.training_type == "lora":
            cmd.extend(["--lora", "--lora-r", str(config.lora_rank)])
            cmd.extend(["--lora-alpha", str(config.lora_alpha)])
        elif config.training_type == "full":
            cmd.append("--full-finetune")
        elif config.training_type == "distill":
            cmd.append("--distill")
        
        # 训练参数
        cmd.extend(["--num-epochs", str(config.epochs)])
        cmd.extend(["--batch-size", str(config.batch_size)])
        cmd.extend(["--learning-rate", str(config.learning_rate)])
        cmd.extend(["--max-seq-length", str(config.max_seq_length)])
        cmd.extend(["--gradient-accumulation-steps", str(config.gradient_accumulation_steps)])
        cmd.extend(["--logging-steps", str(config.logging_steps)])
        cmd.extend(["--save-steps", str(config.save_steps)])
        cmd.extend(["--eval-steps", str(config.eval_steps)])
        
        # 设备配置
        if config.device != "auto":
            cmd.extend(["--device", config.device])
        
        # 混合精度
        if config.fp16:
            cmd.append("--fp16")
        
        return cmd
    
    def _parse_train_result(self, output: str, output_dir: str) -> TrainingResult:
        """解析训练结果"""
        result = TrainingResult(success=True)
        
        # 查找模型路径
        model_path = Path(output_dir) / "pytorch_model.bin"
        if model_path.exists():
            result.model_path = str(model_path)
        
        # 尝试解析损失值
        import re
        
        # 查找最终损失
        loss_match = re.search(r"final.*loss.*?:\s*([\d.]+)", output, re.IGNORECASE)
        if loss_match:
            result.loss = float(loss_match.group(1))
        
        # 查找评估损失
        eval_loss_match = re.search(r"eval.*loss.*?:\s*([\d.]+)", output, re.IGNORECASE)
        if eval_loss_match:
            result.eval_loss = float(eval_loss_match.group(1))
        
        # 查找训练时间
        time_match = re.search(r"training.*time.*?:\s*([\d.]+)", output, re.IGNORECASE)
        if time_match:
            result.training_time = float(time_match.group(1))
        
        # 提取指标
        result.metrics = self._extract_metrics(output)
        
        return result
    
    def _extract_metrics(self, output: str) -> Dict:
        """从输出中提取指标"""
        metrics = {}
        
        # 尝试提取常见指标
        patterns = {
            "accuracy": r"accuracy.*?:\s*([\d.]+)",
            "perplexity": r"perplexity.*?:\s*([\d.]+)",
            "f1": r"f1.*?:\s*([\d.]+)",
            "bleu": r"bleu.*?:\s*([\d.]+)",
            "rouge": r"rouge.*?:\s*([\d.]+)",
        }
        
        for name, pattern in patterns.items():
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                metrics[name] = float(match.group(1))
        
        return metrics
    
    def fine_tune_lora(self, model_name: str, dataset_name: str, output_dir: str) -> TrainingResult:
        """
        执行 LoRA 微调
        
        Args:
            model_name: 模型名称
            dataset_name: 数据集名称
            output_dir: 输出目录
        
        Returns:
            训练结果
        """
        config = TrainingConfig(
            model_name=model_name,
            dataset_name=dataset_name,
            output_dir=output_dir,
            training_type="lora"
        )
        return self.train(config)
    
    def fine_tune_full(self, model_name: str, dataset_name: str, output_dir: str) -> TrainingResult:
        """
        执行全参微调
        
        Args:
            model_name: 模型名称
            dataset_name: 数据集名称
            output_dir: 输出目录
        
        Returns:
            训练结果
        """
        config = TrainingConfig(
            model_name=model_name,
            dataset_name=dataset_name,
            output_dir=output_dir,
            training_type="full"
        )
        return self.train(config)
    
    def distill(self, teacher_model: str, student_model: str, dataset_name: str, output_dir: str) -> TrainingResult:
        """
        执行知识蒸馏
        
        Args:
            teacher_model: 教师模型
            student_model: 学生模型
            dataset_name: 数据集名称
            output_dir: 输出目录
        
        Returns:
            训练结果
        """
        config = TrainingConfig(
            model_name=student_model,
            dataset_name=dataset_name,
            output_dir=output_dir,
            training_type="distill"
        )
        return self.train(config)
    
    def get_supported_models(self) -> List[str]:
        """获取支持的模型列表"""
        return self.SUPPORTED_MODELS
    
    def get_training_types(self) -> Dict[str, str]:
        """获取支持的训练类型"""
        return self.TRAINING_TYPES


# 训练调度器
class TrainingScheduler:
    """
    训练调度器 - 由决策层调用
    
    负责：
    1. 检测系统空闲状态
    2. 判断数据积累阈值
    3. 触发训练任务
    4. 管理训练队列
    """
    
    def __init__(self):
        self._logger = logger.bind(component="TrainingScheduler")
        self._swift = MSSwiftIntegration()
        self._pending_tasks = []
        self._is_running = False
    
    def schedule_training(self, config: TrainingConfig) -> bool:
        """
        调度训练任务
        
        Args:
            config: 训练配置
        
        Returns:
            是否成功调度
        """
        if not self._swift.is_available():
            self._logger.warning("MS-SWIFT 不可用，跳过训练调度")
            return False
        
        # 检查系统状态
        if not self._is_system_idle():
            self._logger.info("系统繁忙，将训练任务加入队列")
            self._pending_tasks.append(config)
            return True
        
        # 立即执行训练
        self._execute_training(config)
        return True
    
    def _is_system_idle(self) -> bool:
        """检查系统是否空闲"""
        try:
            import psutil
            
            # CPU 使用率 < 30%
            cpu_usage = psutil.cpu_percent()
            if cpu_usage > 30:
                return False
            
            # 内存使用率 < 50%
            mem_usage = psutil.virtual_memory().percent
            if mem_usage > 50:
                return False
            
            # GPU 显存使用率 < 20%（如果有 GPU）
            try:
                import pynvml
                pynvml.nvmlInit()
                device_count = pynvml.nvmlDeviceGetCount()
                for i in range(device_count):
                    handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                    memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    gpu_usage = (memory_info.used / memory_info.total) * 100
                    if gpu_usage > 20:
                        pynvml.nvmlShutdown()
                        return False
                pynvml.nvmlShutdown()
            except ImportError:
                pass  # 没有 GPU 或 pynvml 未安装
            
            return True
        except Exception as e:
            self._logger.warning(f"检查系统状态失败: {e}")
            return False
    
    def _execute_training(self, config: TrainingConfig):
        """执行训练任务"""
        self._is_running = True
        
        try:
            self._logger.info(f"开始执行训练任务: {config.model_name}")
            result = self._swift.train(config)
            
            if result.success:
                self._logger.info(f"训练成功: {result.model_path}")
                # 可以在这里触发模型评估和部署
            else:
                self._logger.error(f"训练失败: {result.error}")
                
        finally:
            self._is_running = False
            # 执行队列中的下一个任务
            if self._pending_tasks:
                next_task = self._pending_tasks.pop(0)
                self.schedule_training(next_task)
    
    def get_pending_tasks(self) -> List[TrainingConfig]:
        """获取待执行的训练任务队列"""
        return self._pending_tasks
    
    def is_training(self) -> bool:
        """检查是否正在训练"""
        return self._is_running


# 快捷函数
def get_swift_integration() -> MSSwiftIntegration:
    """获取 MS-SWIFT 集成实例"""
    return MSSwiftIntegration()


def get_training_scheduler() -> TrainingScheduler:
    """获取训练调度器实例"""
    return TrainingScheduler()


# 测试代码
if __name__ == "__main__":
    print("=" * 60)
    print("MS-SWIFT 集成测试")
    print("=" * 60)
    
    swift = MSSwiftIntegration()
    
    print(f"MS-SWIFT 可用: {'是' if swift.is_available() else '否'}")
    print(f"支持的模型数量: {len(swift.get_supported_models())}")
    print(f"支持的训练类型: {list(swift.get_training_types().keys())}")
    
    if swift.is_available():
        # 创建训练配置
        config = TrainingConfig(
            model_name="Qwen/Qwen3.5-4B",
            dataset_name="mydata",
            output_dir="./output/test",
            training_type="lora",
            epochs=1,
            batch_size=4
        )
        print(f"\n训练配置:")
        print(f"  模型: {config.model_name}")
        print(f"  类型: {config.training_type}")
        print(f"  轮数: {config.epochs}")
    
    print("\n" + "=" * 60)