"""
Verifier Engine - 验证引擎
本地兼容实现：避免直接依赖 client.src.business.verifier_engine。
"""
from dataclasses import dataclass
from typing import List


@dataclass
class VerificationIssue:
    type: str = ""
    message: str = ""
    severity: str = "warning"


class VerifierEngine:
    def __init__(self):
        pass

    def verify(self, content: str) -> List[VerificationIssue]:
        return []

    def verify_code(self, code: str) -> List[VerificationIssue]:
        return []


__all__ = ["VerifierEngine", "VerificationIssue"]
