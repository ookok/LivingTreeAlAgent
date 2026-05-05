"""DomainTransfer — abstract principles from known domains, apply to new ones.

    Like a human who learns EIA report patterns and applies them to safety
    assessment without being explicitly programmed for it.

    Three layers of abstraction:
    1. Structural principles: document organization patterns (abstract, concrete)
    2. Content principles: what every claim needs (proof, standard, uncertainty)
    3. Process principles: how data flows through a document (source → compute → cite)

    Usage:
        dt = get_domain_transfer()
        dt.learn_from_domain("环评报告", eia_docs)
        principles = dt.extract_principles()
        # → ["数据必须引用来源", "预测必须对比标准", ...]
        adapted = dt.apply_to("安全评价", principles)
        # → "危险源辨识需要引用设备清单" (映射自"污染源分析需要引用工艺数据")
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

DOMAIN_FILE = Path(".livingtree/domain_principles.json")


@dataclass
class Principle:
    id: str
    name: str                        # abstract principle name
    description: str                  # human-readable explanation
    level: str = "abstract"           # abstract | concrete
    domain_origin: str = ""           # which domain was this learned from
    evidence_count: int = 0          # how many documents support this
    confidence: float = 1.0
    domain_mappings: dict[str, str] = field(default_factory=dict)  # domain → concrete rule


@dataclass  
class DomainAdaptation:
    target_domain: str
    source_domain: str
    principles_applied: list[str] = field(default_factory=list)
    concrete_rules: dict[str, str] = field(default_factory=dict)
    suggestions: list[str] = field(default_factory=list)


class DomainTransfer:
    """Learn abstract principles from one domain, apply them to another."""

    def __init__(self):
        DOMAIN_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._principles: dict[str, Principle] = {}
        self._load()

    async def learn_from_domain(self, domain: str, hub, documents: list[str] | None = None):
        """Extract abstract principles from documents in a domain.

        Args:
            domain: Domain name (e.g. "环评报告")
            hub: LLM access
            documents: Optional document texts to analyze
        """
        if not hub or not hub.world:
            return

        llm = hub.world.consciousness._llm
        sample = "\n---\n".join(d[:2000] for d in (documents or [])[:3])

        try:
            result = await llm.chat(
                messages=[{"role": "user", "content": (
                    f"Analyze these documents from the '{domain}' domain. "
                    f"Extract ABSTRACT, DOMAIN-AGNOSTIC principles about document quality. "
                    f"NOT specific rules like 'cite GB3095', but general ones like "
                    f"'every measurement must cite a standard'. Principles should be "
                    f"applicable to OTHER document types too.\n\n"
                    f"DOCUMENTS:\n{sample[:5000]}\n\n"
                    "Output JSON array:\n"
                    '[{"id":"p1","name":"data_requires_source","description":"Every factual claim needs a verifiable source","level":"abstract"}, ...]'
                )}],
                provider=getattr(llm, '_elected', ''),
                temperature=0.3, max_tokens=800, timeout=30,
            )
            if result and result.text:
                import re
                m = re.search(r'\[[\s\S]*\]', result.text)
                if m:
                    principles = json.loads(m.group())
                    for p in principles:
                        pid = p.get("id", f"p{len(self._principles)}")
                        if pid not in self._principles:
                            self._principles[pid] = Principle(
                                id=pid, name=p.get("name", ""),
                                description=p.get("description", ""),
                                level=p.get("level", "abstract"),
                                domain_origin=domain, evidence_count=1,
                            )
                        else:
                            self._principles[pid].evidence_count += 1
                            self._principles[pid].confidence = min(
                                1.0, self._principles[pid].evidence_count / 10
                            )
        except Exception as e:
            logger.debug(f"DomainTransfer learn: {e}")
        self._save()

    async def apply_to(self, target_domain: str, hub, sample_document: str = "") -> DomainAdaptation:
        """Apply learned principles to a new domain.

        Args:
            target_domain: New domain name (e.g. "安全评价")
            hub: LLM access
            sample_document: Optional small sample of the new domain
        """
        if not self._principles:
            return DomainAdaptation(target_domain=target_domain, source_domain="")

        source = next(iter(self._principles.values())).domain_origin
        adaptation = DomainAdaptation(target_domain=target_domain, source_domain=source)

        principles_text = "\n".join(
            f"- {p.id}: {p.name} — {p.description}" for p in self._principles.values()
        )

        llm = hub.world.consciousness._llm
        try:
            result = await llm.chat(
                messages=[{"role": "user", "content": (
                    f"Apply these ABSTRACT document principles to the '{target_domain}' domain. "
                    f"Concretize each principle into a domain-specific rule.\n\n"
                    f"PRINCIPLES (from {source}):\n{principles_text}\n\n"
                    + (f"SAMPLE DOCUMENT:\n{sample_document[:2000]}\n\n" if sample_document else "") +
                    "Output JSON:\n"
                    '{"concrete_rules": {"principle_id": "concrete rule for target_domain"}, '
                    '"suggestions": ["practical suggestion 1", ...]}'
                )}],
                provider=getattr(llm, '_elected', ''),
                temperature=0.3, max_tokens=800, timeout=30,
            )
            if result and result.text:
                import re
                m = re.search(r'\{[\s\S]*\}', result.text)
                if m:
                    d = json.loads(m.group())
                    adaptation.concrete_rules = d.get("concrete_rules", {})
                    adaptation.suggestions = d.get("suggestions", [])
                    adaptation.principles_applied = list(adaptation.concrete_rules.keys())
        except Exception as e:
            logger.debug(f"DomainTransfer apply: {e}")

        return adaptation

    def extract_principles(self, min_confidence: float = 0.3) -> list[Principle]:
        """Get all learned principles above confidence threshold."""
        return sorted(
            [p for p in self._principles.values() if p.confidence >= min_confidence],
            key=lambda p: -p.confidence,
        )

    def principles_by_domain(self) -> dict[str, list[str]]:
        result = {}
        for p in self._principles.values():
            result.setdefault(p.domain_origin, []).append(p.name)
        return result

    def _save(self):
        data = {}
        for pid, p in self._principles.items():
            data[pid] = {
                "id": p.id, "name": p.name, "description": p.description,
                "level": p.level, "domain_origin": p.domain_origin,
                "evidence_count": p.evidence_count, "confidence": p.confidence,
                "domain_mappings": p.domain_mappings,
            }
        DOMAIN_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _load(self):
        if not DOMAIN_FILE.exists():
            return
        try:
            data = json.loads(DOMAIN_FILE.read_text(encoding="utf-8"))
            for pid, d in data.items():
                self._principles[pid] = Principle(**d)
        except Exception:
            pass


_dt: DomainTransfer | None = None


def get_domain_transfer() -> DomainTransfer:
    global _dt
    if _dt is None:
        _dt = DomainTransfer()
    return _dt
