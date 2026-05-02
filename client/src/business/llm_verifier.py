"""
LLM Verifier — Compatibility Stub

Functionality migrated to livingtree.core.agent.verifier.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any


class VerificationType(Enum):
    CODE = "code"
    FACTUAL = "factual"
    LOGICAL = "logical"
    SECURITY = "security"
    STYLE = "style"


class VerificationResult(Enum):
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"


class SeverityLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class VerificationIssue:
    type: VerificationType = VerificationType.CODE
    severity: SeverityLevel = SeverityLevel.WARNING
    message: str = ""
    location: str = ""
    suggestion: str = ""


@dataclass
class VerificationReport:
    passed: bool = True
    issues: List[VerificationIssue] = field(default_factory=list)
    summary: str = ""
    score: float = 1.0


class LLMVerifier:
    def __init__(self, model: str = ""):
        self.model = model

    def verify(self, content: str, context: Dict[str, Any] = None) -> VerificationReport:
        return VerificationReport(passed=True, summary="Verification passed (stub)")

    def verify_code(self, code: str) -> VerificationReport:
        return VerificationReport(passed=True, summary="Code verification passed (stub)")

    def verify_facts(self, text: str, sources: List[str] = None) -> VerificationReport:
        return VerificationReport(passed=True, summary="Fact check passed (stub)")


def create_llm_verifier(model: str = "") -> LLMVerifier:
    return LLMVerifier(model)


__all__ = [
    "LLMVerifier", "VerificationType", "VerificationResult",
    "SeverityLevel", "VerificationIssue", "VerificationReport",
    "create_llm_verifier",
]
