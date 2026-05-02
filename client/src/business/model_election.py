"""
ModelElection — Compatibility Stub
====================================

已迁移至 livingtree.core.model.router。
Model election (投票选择最优模型) 功能整合入 UnifiedModelRouter.
"""


class ModelElection:
    def __init__(self, **kwargs):
        self._candidates = []

    def add_candidate(self, model_name: str, score: float = 0.0):
        self._candidates.append({"name": model_name, "score": score})

    def elect(self) -> str:
        if not self._candidates:
            return "qwen2.5:7b"
        self._candidates.sort(key=lambda x: x["score"], reverse=True)
        return self._candidates[0]["name"]


__all__ = ["ModelElection"]
