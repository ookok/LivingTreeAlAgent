#!/usr/bin/env python3
"""
专家模型微调脚本 - fine_tune_expert.py

使用 LLaMA-Factory 或 Unsloth 微调垂直领域专家模型。

使用方法:
    # 快速开始（使用默认配置）
    python fine_tune_expert.py --domain 金融 --data data/fin_train.jsonl

    # 自定义配置
    python fine_tune_expert.py --domain 金融 --base-model qwen2.5:1.5b --lora-rank 16 --epochs 3

    # 使用 Unsloth（更快）
    python fine_tune_expert.py --domain 金融 --use-unsloth --batch-size 4
"""

import argparse
import json
import os
import sys
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from datetime import datetime


@dataclass
class TrainConfig:
    """训练配置"""
    # 模型配置
    base_model: str = "qwen2.5:1.5b"
    template: str = "qwen"

    # 数据配置
    data_path: str = "data/distillation/train.jsonl"
    output_dir: str = "models/experts"
    val_size: float = 0.1

    # 训练配置
    finetune_type: str = "lora"  # lora/qlora/full
    epochs: int = 3
    batch_size: int = 2
    learning_rate: float = 2e-4
    lora_rank: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    lora_target: str = "all"

    # 量化配置
    quant_bit: Optional[int] = None  # 4, 8

    # 其他
    warmup_steps: int = 10
    save_steps: int = 100
    eval_steps: int = 100
    use_unsloth: bool = False


class FineTuner:
    """微调引擎"""

    def __init__(self, config: TrainConfig):
        self.config = config

    def prepare_data(self, input_path: str, output_path: str) -> str:
        """
        准备训练数据

        Args:
            input_path: 输入 JSONL 路径
            output_path: 输出路径

        Returns:
            处理后的数据路径
        """
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        # 读取并转换数据
        samples = []
        with open(input_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    # LLaMA-Factory 格式
                    sample = {
                        "instruction": data.get("question", data.get("instruction", "")),
                        "input": data.get("input", ""),
                        "output": data.get("rationale", "") + "\n\n" + data.get("answer", data.get("output", ""))
                    }
                    samples.append(sample)
                except json.JSONDecodeError:
                    continue

        # 分割训练/验证集
        val_count = int(len(samples) * self.config.val_size)
        train_samples = samples[val_count:]
        val_samples = samples[:val_count]

        # 保存
        train_path = output.parent / "train.jsonl"
        val_path = output.parent / "val.jsonl"

        with open(train_path, "w", encoding="utf-8") as f:
            for s in train_samples:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")

        with open(val_path, "w", encoding="utf-8") as f:
            for s in val_samples:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")

        return str(train_path)

    def generate_llama_factory_config(self, train_data: str, val_data: str) -> str:
        """生成 LLaMA-Factory 配置文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        config_path = f"{self.config.output_dir}/config_{timestamp}.yaml"

        os.makedirs(self.config.output_dir, exist_ok=True)

        config = f"""### model
model_name_or_path: {self.config.base_model}
model_revision: null
quantization_bit: {self.config.quant_bit or 'null'}

### method
stage: sft
finetuning_type: {self.config.finetune_type}
setting:
  stage: sft
  do_train: true
  finetuning_type: {self.config.finetune_type}
  report_to: none
  output_dir: {self.config.output_dir}/output
  num_train_epochs: {self.config.epochs}
  per_device_train_batch_size: {self.config.batch_size}
  gradient_accumulation_steps: 4
  learning_rate: {self.config.learning_rate}
  num_freeze_layers: 4
  lr_scheduler_type: cosine
  warmup_steps: {self.config.warmup_steps}
  save_steps: {self.config.save_steps}
  eval_steps: {self.config.eval_steps}
  evaluation_strategy: steps
  load_best_model_at_end: true

### lora
lora:
  lora_rank: {self.config.lora_rank}
  lora_alpha: {self.config.lora_alpha}
  lora_dropout: {self.config.lora_dropout}
  lora_target: {self.config.lora_target}

### dataset
dataset: custom
template: {self.config.template}
Cutoff_len: 1024
max_samples: 10000

### output
output_dir: {self.config.output_dir}
logging_dir: {self.config.output_dir}/logs
"""

        with open(config_path, "w", encoding="utf-8") as f:
            f.write(config)

        return config_path

    def train_with_llama_factory(self, config_path: str):
        """使用 LLaMA-Factory 训练"""
        cmd = [
            "llamafactory-cli", "train", config_path
        ]

        logger.info(f"执行命令: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)

    def train_with_unsloth(self, train_data: str):
        """使用 Unsloth 训练（更快）"""
        # Unsloth 需要专门的训练脚本
        script = f"""
from unsloth import FastLanguageModel
import torch
from datasets import load_dataset
from business.logger import get_logger
logger = get_logger('expert_distillation.fine_tune_expert')


# 加载模型
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "{self.config.base_model}",
    max_seq_length = 2048,
    dtype = torch.float16,
    load_in_4bit = {self.config.quant_bit == 4},
)

# 添加 LoRA
model = FastLanguageModel.get_peft_model(
    model,
    r = {self.config.lora_rank},
    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_alpha = {self.config.lora_alpha},
    lora_dropout = {self.config.lora_dropout},
    bias = "none",
    use_gradient_checkpointing = "unsloth",
)

# 加载数据
dataset = load_dataset("json", data_files="{train_data}", split="train")

# 训练
model.train()
"""

        script_path = Path(self.config.output_dir) / "unsloth_train.py"
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script)

        logger.info(f"Unsloth 训练脚本已生成: {script_path}")
        logger.info("请运行: python " + str(script_path))

    def export_model(self, output_path: str, format: str = "gguf"):
        """导出模型"""
        if format == "gguf":
            cmd = [
                "llamafactory-cli", "export",
                self.config.output_dir,
                "--gguf", output_path
            ]
            subprocess.run(cmd, check=True)
        logger.info(f"模型已导出到: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="专家模型微调工具")
    parser.add_argument("--domain", required=True, help="领域名称")
    parser.add_argument("--data", required=True, help="训练数据路径")
    parser.add_argument("--base-model", default="qwen2.5:1.5b", help="基础模型")
    parser.add_argument("--output-dir", default="models/experts", help="输出目录")
    parser.add_argument("--epochs", type=int, default=3, help="训练轮数")
    parser.add_argument("--batch-size", type=int, default=2, help="批大小")
    parser.add_argument("--lora-rank", type=int, default=16, help="LoRA rank")
    parser.add_argument("--use-unsloth", action="store_true", help="使用 Unsloth")
    parser.add_argument("--quant-bit", type=int, choices=[4, 8], help="量化位数")

    args = parser.parse_args()

    # 构建配置
    config = TrainConfig(
        base_model=args.base_model,
        data_path=args.data,
        output_dir=f"{args.output_dir}/{args.domain}",
        epochs=args.epochs,
        batch_size=args.batch_size,
        lora_rank=args.lora_rank,
        use_unsloth=args.use_unsloth,
        quant_bit=args.quant_bit
    )

    # 创建微调器
    tuner = FineTuner(config)

    # 准备数据
    logger.info(f"准备训练数据: {args.data}")
    train_data = tuner.prepare_data(args.data, f"{config.output_dir}/data")

    # 训练
    if config.use_unsloth:
        logger.info("使用 Unsloth 训练...")
        tuner.train_with_unsloth(train_data)
    else:
        logger.info("使用 LLaMA-Factory 训练...")
        llm_config = tuner.generate_llama_factory_config(
            f"{config.output_dir}/data/train.jsonl",
            f"{config.output_dir}/data/val.jsonl"
        )
        # 检查是否有 llamafactory-cli
        try:
            tuner.train_with_llama_factory(llm_config)
        except FileNotFoundError:
            logger.info("警告: 未找到 llamafactory-cli")
            logger.info("请先安装: pip install llamafactory")
            logger.info("或使用 --use-unsloth 选项")

    # 导出
    logger.info("训练完成！")
    logger.info(f"输出目录: {config.output_dir}")


if __name__ == "__main__":
    main()
