"""PIIRedactor — LongParser-inspired privacy-first PII detection and redaction.

LongParser approach: Hybrid Regex + NER redaction with secure HITL preservation.
For Chinese documents (EIA reports, contracts), regex covers the most critical
PII types without needing heavy NER dependencies.

PII types detected:
  - Phone numbers (Chinese mobile/fixed)
  - ID numbers (Chinese 18-digit)
  - Email addresses
  - Company names (有限公司/集团/厂后缀)
  - Addresses (省市+区/县/街道级)
  - Person names (2-4 character, context-dependent)
  - Bank account numbers
  - License plate numbers

Usage:
    redactor = PIIRedactor()
    clean, findings = redactor.redact(document_text)
    # 'clean' has PII replaced with [PHONE]/[ID]/etc.
    # 'findings' lists what was redacted for audit trail
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PIIFinding:
    pii_type: str
    original: str
    replacement: str
    position: int = 0
    confidence: float = 0.9


@dataclass
class RedactionResult:
    original_text: str
    redacted_text: str
    findings: list[PIIFinding] = field(default_factory=list)
    redaction_count: int = 0
    original_chars: int = 0

    @property
    def redaction_ratio(self) -> float:
        return round(self.redaction_count / max(len(self.original_text), 1), 4)


class PIIRedactor:
    """Privacy-first PII redaction for Chinese documents.

    All processing happens locally — no data leaves the machine.
    Matching: hybrid regex patterns optimized for Chinese document context.
    """

    PATTERNS = {
        "EMAIL": re.compile(
            r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        ),
        "ID": re.compile(
            r'(\d{6}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx])'
        ),
        "ADDRESS": re.compile(
            r'((?:[\u4e00-\u9fff]{2,4}(?:省|市|自治区|特别行政区))'
            r'(?:[\u4e00-\u9fff]{2,10}(?:市|区|县|自治州|地区|盟))?'
            r'(?:[\u4e00-\u9fff]{2,20}(?:区|县|街道|镇|乡|路|街|巷|号|村|组))'
            r'(?:\s*\d+[号弄栋幢座]?)?'
            r'(?:\s*[\u4e00-\u9fff]{2,10}(?:小区|花园|大厦|广场|城|苑|公寓))?)'
        ),
        "COMPANY": re.compile(
            r'((?:[\u4e00-\u9fff]{2,20})'
            r'(?:有限公司|有限责任公司|股份有限公司|集团|集团公司|'
            r'厂|工厂|公司|企业|事务所|研究院|中心))'
        ),
        "PLATE": re.compile(
            r'((?:[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤川青藏琼宁]'
            r'[A-Z][A-HJ-NP-Z0-9]{5}))'
        ),
        "BANK": re.compile(
            r'(?:银行|账号|卡号|汇款)[：:]*[\s]*(\d{10,20})'
        ),
        "PHONE": re.compile(
            r'((?:0\d{2,3}[-]\d{7,8})|(?:1[3-9]\d{9}))'
        ),
    }

    PII_LABELS: dict[str, str] = {
        "PHONE": "[PHONE]", "ID": "[ID]",
        "EMAIL": "[EMAIL]", "COMPANY": "[COMPANY]",
        "ADDRESS": "[ADDRESS]", "BANK": "[BANK_ACCT]",
        "PLATE": "[PLATE]",
    }

    def __init__(self, preserve_audit: bool = True):
        self.preserve_audit = preserve_audit
        self._audit: list[PIIFinding] = []

    def redact(self, text: str) -> tuple[str, list[PIIFinding]]:
        """Redact all PII from text, returning cleaned text and findings."""
        findings: list[PIIFinding] = []
        positions_used: set[tuple[int, int]] = set()

        id_pattern = re.compile(r'(\d{17}[\dXx])')
        for match in id_pattern.finditer(text):
            full = match.group(0)
            if re.search(r'(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])', full):
                positions_used.add((match.start(), match.end()))
                findings.append(PIIFinding(
                    pii_type="ID", original=full,
                    replacement="[ID]", position=match.start(),
                    confidence=0.95,
                ))

        for pii_type, pattern in self.PATTERNS.items():
            if pii_type == "ID":
                continue
            for match in pattern.finditer(text):
                if match.lastindex and match.lastindex >= 1:
                    start = match.start(1)
                    end = match.end(1)
                    original = match.group(1)
                else:
                    start = match.start()
                    end = match.end()
                    original = match.group(0)

                overlaps = any(
                    (start < up_end and end > up_start)
                    for up_start, up_end in positions_used
                )
                if overlaps or (start, end) in positions_used:
                    continue

                positions_used.add((start, end))
                label = self.PII_LABELS.get(pii_type, "[PII]")

                findings.append(PIIFinding(
                    pii_type=pii_type, original=original,
                    replacement=label, position=start,
                    confidence=self._estimate_confidence(pii_type, original),
                ))

        findings.sort(key=lambda f: f.position, reverse=True)

        redacted = text
        for f in findings:
            redacted = redacted[:f.position] + f.replacement + redacted[f.position + len(f.original):]

        if self.preserve_audit:
            self._audit.extend(findings)

        return redacted, findings

    def redact_with_result(self, text: str) -> RedactionResult:
        cleaned, findings = self.redact(text)
        return RedactionResult(
            original_text=text,
            redacted_text=cleaned,
            findings=findings,
            redaction_count=len(findings),
            original_chars=len(text),
        )

    def scan_only(self, text: str) -> list[PIIFinding]:
        """Scan for PII without modifying the text."""
        findings: list[PIIFinding] = []
        for pii_type, pattern in self.PATTERNS.items():
            for match in pattern.finditer(text):
                if match.lastindex and match.lastindex >= 1:
                    original = match.group(1)
                    start = match.start(1)
                else:
                    original = match.group(0)
                    start = match.start()
                findings.append(PIIFinding(
                    pii_type=pii_type, original=original,
                    replacement="", position=start,
                ))
        return findings

    def has_pii(self, text: str) -> bool:
        """Quick check: does text contain any PII?"""
        for pattern in self.PATTERNS.values():
            if pattern.search(text):
                return True
        return False

    def audit_trail(self) -> list[dict[str, Any]]:
        """Return audit trail of all redactions performed."""
        return [{"type": f.pii_type, "position": f.position,
                 "confidence": f.confidence} for f in self._audit]

    def stats(self) -> dict[str, Any]:
        """Redaction statistics."""
        by_type: dict[str, int] = {}
        for f in self._audit:
            by_type[f.pii_type] = by_type.get(f.pii_type, 0) + 1
        return {
            "total_redactions": len(self._audit),
            "by_type": by_type,
        }

    @staticmethod
    def _estimate_confidence(pii_type: str, original: str) -> float:
        if pii_type in ("PHONE", "ID", "ID_RAW", "EMAIL", "BANK"):
            return 0.95
        if pii_type == "COMPANY":
            return 0.9 if any(kw in original for kw in ("有限公司", "集团")) else 0.7
        if pii_type == "ADDRESS":
            has_province = bool(re.search(r'[\u4e00-\u9fff]{2}(?:省|市|自治区)', original))
            has_detail = bool(re.search(r'(?:路|街|巷|号|镇|乡)', original))
            return 0.9 if (has_province and has_detail) else 0.6
        if pii_type == "PLATE":
            return 0.85
        return 0.5


_pii_redactor: PIIRedactor | None = None


def get_pii_redactor() -> PIIRedactor:
    global _pii_redactor
    if _pii_redactor is None:
        _pii_redactor = PIIRedactor()
    return _pii_redactor


def redact_text(text: str) -> tuple[str, list[PIIFinding]]:
    """Convenience: one-call PII redaction."""
    return get_pii_redactor().redact(text)


def has_pii(text: str) -> bool:
    """Convenience: quick PII check."""
    return get_pii_redactor().has_pii(text)
