"""
迁移学习模块 (Transfer Learning Module)
===========================================

提供领域适配和预训练模型能力。

包含:
1. DomainAdapter - 领域适配器 (简化版)
2. TransferTrainer - 迁移训练器
3. CodeBERTAdapter - CodeBERT 预训练模型适配器 (简化版)
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

__all__ = [
    "DomainAdapter",
    "TransferTrainer", 
    "CodeBERTAdapter",
    "AdaptiveTransfer",
]

MODULE_DIR = Path(__file__).parent


# 延迟导入
def __getattr__(name):
    """延迟导入，避免依赖问题"""
    if name == "DomainAdapter":
        from .domain_adapter import DomainAdapter
        return DomainAdapter
    elif name == "TransferTrainer":
        from .transfer_trainer import TransferTrainer
        return TransferTrainer
    elif name in ("CodeBERTAdapter",):
        from .pretrained_model import CodeBERTAdapter
        return CodeBERTAdapter
    elif name == "AdaptiveTransfer":
        from .adaptive_transfer import AdaptiveTransfer
        return AdaptiveTransfer
    
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
