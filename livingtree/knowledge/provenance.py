"""Grounded Provenance Graph — Char-level audit trail from KB entries to source.

Every fact in the KnowledgeBase gets a LangExtract char_interval linking it
to the exact source position. When LLM references a fact, the provenance is
automatically displayed — showing document, position, and extraction confidence.

Usage:
    provenance = ProvenanceTracker()
    
    # Record when a fact enters KB:
    provenance.record(fact_id, source_doc, char_start, char_end, extraction_confidence)
    
    # When LLM uses a fact, get its provenance:
    chain = provenance.trace(fact_id)
    # → "doc_03.txt:142-187 (extracted by LangExtract, confidence 0.95)"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class ProvenanceEntry:
    fact_id: str
    source_document: str
    char_start: int
    char_end: int
    extraction_confidence: float
    extracted_by: str
    extracted_at: str
    snippet: str = ""
    upstream_facts: list[str] = field(default_factory=list)

    def format_trace(self) -> str:
        pos = f"{self.char_start}-{self.char_end}" if self.char_start >= 0 else "?"
        conf = f"{self.extraction_confidence:.0%}" if self.extraction_confidence else "?"
        return f"{self.source_document}:{pos} [{self.extracted_by} conf={conf}]"

    def get_snippet_with_context(self, full_text: str = "") -> str:
        if self.snippet:
            return self.snippet
        if full_text and self.char_start >= 0:
            start = max(0, self.char_start - 30)
            end = min(len(full_text), self.char_end + 30)
            return full_text[start:end]
        return ""


class ProvenanceTracker:

    PROVENANCE_FILE = ".livingtree/provenance.jsonl"

    def __init__(self):
        self._entries: dict[str, ProvenanceEntry] = {}
        self._chains: dict[str, list[str]] = {}
        self._load()

    def record(
        self,
        fact_id: str,
        source_document: str,
        char_start: int = -1,
        char_end: int = -1,
        extraction_confidence: float = 0.0,
        extracted_by: str = "LangExtract",
        snippet: str = "",
        upstream_facts: list[str] | None = None,
    ) -> ProvenanceEntry:
        entry = ProvenanceEntry(
            fact_id=fact_id,
            source_document=source_document,
            char_start=char_start,
            char_end=char_end,
            extraction_confidence=extraction_confidence,
            extracted_by=extracted_by,
            extracted_at=datetime.now(timezone.utc).isoformat(),
            snippet=snippet,
            upstream_facts=upstream_facts or [],
        )
        self._entries[fact_id] = entry

        for up_id in entry.upstream_facts:
            chain = self._chains.setdefault(up_id, [])
            if fact_id not in chain:
                chain.append(fact_id)

        self._append_jsonl(entry)
        return entry

    def trace(self, fact_id: str) -> dict:
        entry = self._entries.get(fact_id)
        if not entry:
            return {"found": False, "fact_id": fact_id}

        chain_ids = self._chains.get(fact_id, [])
        chain_entries = [self._entries[cid] for cid in chain_ids if cid in self._entries]

        return {
            "found": True,
            "fact_id": fact_id,
            "source": entry.source_document,
            "position": f"{entry.char_start}:{entry.char_end}",
            "confidence": entry.extraction_confidence,
            "extracted_by": entry.extracted_by,
            "extracted_at": entry.extracted_at,
            "snippet": entry.snippet,
            "downstream_facts": len(chain_entries),
            "trace_format": entry.format_trace(),
        }

    def trace_all(self, fact_ids: list[str]) -> list[dict]:
        return [self.trace(fid) for fid in fact_ids]

    def record_from_extraction(
        self,
        extraction_results: list[Any],
        source_doc: str,
        source_text: str = "",
    ) -> int:
        count = 0
        for ext in extraction_results:
            ext_id = f"{source_doc}:{ext.char_start}:{ext.char_end}"
            snippet = ""
            if source_text and ext.char_start >= 0:
                s = max(0, ext.char_start - 20)
                e = min(len(source_text), ext.char_end + 20)
                snippet = source_text[s:e]

            self.record(
                fact_id=ext_id,
                source_document=source_doc,
                char_start=ext.char_start,
                char_end=ext.char_end,
                extraction_confidence=getattr(ext, 'confidence', 0.9),
                snippet=snippet,
            )
            count += 1
        return count

    def format_context_block(self, fact_id: str) -> str:
        trace = self.trace(fact_id)
        if not trace["found"]:
            return ""

        lines = [
            f"[PROVENANCE] {fact_id}",
            f"  Source: {trace['source']}",
            f"  Position: {trace['position']}",
            f"  Confidence: {trace['confidence']:.0%}",
            f"  Extracted: {trace['extracted_at'][:19]} by {trace['extracted_by']}",
        ]
        if trace["snippet"]:
            lines.append(f"  Context: \"{trace['snippet'][:100]}\"")

        return "\n".join(lines)

    def get_stats(self) -> dict:
        sources = {}
        for e in self._entries.values():
            sources[e.source_document] = sources.get(e.source_document, 0) + 1
        return {
            "total_facts": len(self._entries),
            "total_chains": len(self._chains),
            "sources": dict(list(sources.items())[:20]),
        }

    def _append_jsonl(self, entry: ProvenanceEntry) -> None:
        try:
            import json
            path = Path(self.PROVENANCE_FILE)
            path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "fact_id": entry.fact_id,
                "source_document": entry.source_document,
                "char_start": entry.char_start,
                "char_end": entry.char_end,
                "extraction_confidence": entry.extraction_confidence,
                "extracted_by": entry.extracted_by,
                "extracted_at": entry.extracted_at,
            }
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(data, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _load(self) -> None:
        path = Path(self.PROVENANCE_FILE)
        if not path.exists():
            return
        try:
            import json
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                data = json.loads(line)
                self._entries[data["fact_id"]] = ProvenanceEntry(**data)
        except Exception:
            pass
