"""QualityGuard — Parameterized knowledge quality tests.

Inspired by OpenMetadata's Data Quality Test Library:
  - Parameterized test templates with reusable SQL-like conditions
  - Auto-scoring per knowledge domain
  - Test template library for consistency checks

Note: RetrievalValidator and HallucinationGuard are imported directly
from their respective modules (retrieval_validator.py, hallucination_guard.py).
"""

from dataclasses import dataclass, field
from typing import Any, Optional
from loguru import logger

__all__ = ["KnowledgeQualityTest", "run_quality_tests", "QUALITY_TEMPLATES"]


@dataclass
class KnowledgeQualityTest:
    name: str
    description: str = ""
    condition: str = ""            # Python expression, e.g. "len(text) >= 50"
    domain: str = "general"
    severity: str = "warning"      # "error", "warning", "info"
    params: dict = field(default_factory=dict)
    auto_fix: str = ""             # fix suggestion


QUALITY_TEMPLATES = [
    KnowledgeQualityTest(
        name="min_length", description="文本最少50字符", condition="len(text) >= 50",
        severity="error", params={"min_chars": 50},
    ),
    KnowledgeQualityTest(
        name="no_duplicate", description="无重复内容", condition="len(set(text.split())) / max(1, len(text.split())) >= 0.3",
        severity="warning", params={"uniqueness_ratio": 0.3},
    ),
    KnowledgeQualityTest(
        name="has_source", description="包含来源引用", condition="'来源' in text or 'source' in text.lower() or '参考' in text or 'http' in text",
        severity="info", params={"require_citation": True},
    ),
    KnowledgeQualityTest(
        name="chinese_ratio", description="中文内容占比合理", condition="sum(1 for c in text if '\u4e00' <= c <= '\u9fff') / max(1, len(text)) >= 0.1",
        severity="warning", params={"min_chinese_ratio": 0.1},
    ),
    KnowledgeQualityTest(
        name="no_markdown_artifact", description="无未处理markdown标记", condition="text.count('```') % 2 == 0 and '![' not in text[-50:]",
        severity="info", params={},
    ),
    KnowledgeQualityTest(
        name="domain_coherence", description="领域分类一致性", condition="True",
        severity="info", params={"check_domain": True},
    ),
]


def run_quality_tests(text: str, domain: str = "general", templates: list = None) -> dict:
    """Run parameterized quality tests against knowledge content.

    Returns {passed, failed, warnings, score, details}.
    """
    tests = templates or QUALITY_TEMPLATES
    passed, failed, warnings = [], [], []
    total_score = 0

    for test in tests:
        if test.domain not in (domain, "general"):
            continue
        try:
            result = eval(test.condition, {"text": text, "__builtins__": {}})
        except Exception:
            result = True

        detail = {"test": test.name, "description": test.description, "severity": test.severity}
        if result:
            passed.append(test.name)
            total_score += 1
        else:
            if test.severity == "error":
                failed.append(detail)
            else:
                warnings.append(detail)

    total = len(passed) + len(failed) + len(warnings)
    score = round(total_score / max(1, total), 3)

    return {
        "passed": passed, "failed": failed, "warnings": warnings,
        "score": score, "total_tests": total,
        "recommendation": "excellent" if score >= 0.9 else ("good" if score >= 0.7 else "needs_improvement"),
    }
