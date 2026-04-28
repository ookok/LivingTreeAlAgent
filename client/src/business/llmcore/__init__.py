"""
LTAI (LivingTreeAi) - 内置本地模型核心
基于 nanoGPT 架构，专注环评领域任务
双轨并行：Ollama（复杂推理）+ LTAI（结构化任务）
"""
from pathlib import Path

# 版本信息
__version__ = "0.1.0"
__codename__ = "LTAI"  # LivingTreeAi
BASE_DIR = Path(__file__).parent
CONFIGS_DIR = BASE_DIR / "configs"
CELLS_DIR = BASE_DIR / "cells"
DATA_DIR = BASE_DIR / "data"
TRAINING_DIR = BASE_DIR / "training"

# 确保目录存在
for d in [CONFIGS_DIR, CELLS_DIR, DATA_DIR, TRAINING_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# 默认细胞配置模板
DEFAULT_CELL_CONFIGS = {
    "table_cell": {
        "model_type": "nanogpt",
        "vocab_size": 30000,
        "n_layer": 6,
        "n_head": 8,
        "n_embd": 512,
        "block_size": 1024,
        "bias": False,
        "dropout": 0.1,
        "special_tokens": [
            "<project_name>", "<location>", "<pollutant>",
            "<standard>", "<monitoring_point>", "<sensitive_target>"
        ],
        "description": "表格字段填充细胞（10M参数）",
        "max_new_tokens": 256,
        "temperature": 0.8,
        "top_k": 50,
    },
    "regulation_cell": {
        "model_type": "nanogpt",
        "vocab_size": 30000,
        "n_layer": 8,
        "n_head": 12,
        "n_embd": 768,
        "block_size": 2048,
        "bias": False,
        "dropout": 0.1,
        "special_tokens": [
            "<regulation>", "<article>", "<clause>",
            "<standard_name>", "<effective_date>"
        ],
        "description": "法规问答细胞（30M参数）",
        "max_new_tokens": 512,
        "temperature": 0.7,
        "top_k": 40,
    },
    "report_cell": {
        "model_type": "nanogpt",
        "vocab_size": 30000,
        "n_layer": 10,
        "n_head": 12,
        "n_embd": 1024,
        "block_size": 2048,
        "bias": False,
        "dropout": 0.1,
        "special_tokens": [
            "<chapter>", "<section>", "<pollutant>",
            "<impact>", "<mitigation>"
        ],
        "description": "报告章节生成细胞（50M参数）",
        "max_new_tokens": 1024,
        "temperature": 0.9,
        "top_k": 50,
    },
}


def get_cell_config(cell_name: str) -> dict:
    """获取细胞配置"""
    return DEFAULT_CELL_CONFIGS.get(cell_name, DEFAULT_CELL_CONFIGS["table_cell"])


def list_available_cells() -> list[str]:
    """列出已配置的细胞和已训练的checkpoint"""
    configs = list(DEFAULT_CELL_CONFIGS.keys())
    # 检查哪些有训练好的checkpoint
    ready = []
    for name in configs:
        ckpt_path = CELLS_DIR / f"{name}_v1.pt"
        ready.append({
            "name": name,
            "description": DEFAULT_CELL_CONFIGS[name]["description"],
            "has_checkpoint": ckpt_path.exists(),
            "checkpoint_path": str(ckpt_path) if ckpt_path.exists() else None,
        })
    return ready
