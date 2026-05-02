"""
跨域迁移引擎 (Analogy Transfer Engine)

核心功能：
1. 概念映射 - 在不同领域间建立概念对应关系
2. 类比推理 - 发现相似问题的解决思路
3. 零样本迁移 - 将一个领域的逻辑迁移到另一个领域
4. 概念化网络 - 存储"概念"而非死板的文本

基于CATS Net（概念化网络）思想。
"""
from .analogy_engine import AnalogyTransferEngine, DomainConcept, AnalogyMapping, TransferResult

__all__ = [
    "AnalogyTransferEngine",
    "DomainConcept",
    "AnalogyMapping",
    "TransferResult",
]