"""
Change Manifest — Agentic Harness-style falsifiable edit contracts.

Every code modification is recorded as a falsifiable contract with:
- A predicted outcome (what SHOULD happen)
- Actual verification result (what DID happen)
- Self-correcting feedback loop that feeds into CalibrationTracker

Inspired by the Agentic Harness paper: "each edit is a claim that can be falsified."

Usage:
    from livingtree.observability.change_manifest import CHANGE_MANIFEST, get_manifest
    m = get_manifest()
    cid = m.record("tracer.py", "add", "New distil method will enable layered trace analysis")
    m.verify(cid, success=True, actual="distil_evidence() produces 4-layer output")
    report = m.get_verification_report()
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional

from loguru import logger

MANIFEST_DIR = Path(".livingtree/manifests")
MANIFEST_FILE = MANIFEST_DIR / "change_manifest.json"


class ChangeType(str, Enum):
    ADD = "add"
    MODIFY = "modify"
    DELETE = "delete"
    REFACTOR = "refactor"
    FIX = "fix"


class VerificationStatus(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    FALSIFIED = "falsified"
    PARTIAL = "partial"


@dataclass
class ChangeEntry:
    """A single change manifest record — one falsifiable edit contract."""
    id: str
    file: str
    change_type: ChangeType
    description: str
    predicted_outcome: str
    actual_outcome: str = ""
    status: VerificationStatus = VerificationStatus.PENDING
    success: bool = False
    score: float = 0.0
    tags: list[str] = field(default_factory=list)
    parent_span_id: str = ""
    created_at: float = 0.0
    verified_at: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["change_type"] = self.change_type.value
        d["status"] = self.status.value
        return d


class ChangeManifest:
    """Records and verifies every code change as a falsifiable contract.

    Each change is recorded BEFORE execution (as a "prediction contract")
    and verified AFTER execution (checking predicted vs actual outcome).
    This creates a self-correcting feedback loop that improves agent reliability.
    """

    def __init__(self):
        MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
        self._entries: list[dict] = []
        self._load()

    # ── Recording ──

    def record(
        self,
        file: str,
        change_type: str | ChangeType,
        description: str,
        predicted_outcome: str = "",
        tags: Optional[list[str]] = None,
        parent_span_id: str = "",
    ) -> str:
        """Record a change BEFORE execution. Returns change ID for later verification.

        Args:
            file: The file being changed (relative path)
            change_type: 'add', 'modify', 'delete', 'refactor', 'fix'
            description: Human-readable description of the change
            predicted_outcome: What SHOULD happen after this change
            tags: Optional tags for categorization
            parent_span_id: Tracing span ID this change belongs to
        """
        if isinstance(change_type, ChangeType):
            change_type = change_type.value

        entry = ChangeEntry(
            id=f"chg_{uuid.uuid4().hex[:12]}",
            file=file,
            change_type=ChangeType(change_type),
            description=description,
            predicted_outcome=predicted_outcome,
            tags=tags or [],
            parent_span_id=parent_span_id,
            created_at=time.time(),
        )
        self._entries.append(entry.to_dict())
        self._save()
        logger.debug(f"Change manifest recorded: {entry.id} ({file})")
        return entry.id

    def verify(
        self,
        change_id: str,
        success: bool,
        actual: str = "",
        score: float = 0.0,
    ) -> bool:
        """Verify a change AFTER execution. Returns True if entry found and updated.

        Args:
            change_id: The ID returned by record()
            success: Whether the predicted outcome was achieved
            actual: What ACTUALLY happened
            score: Verification score (0.0-1.0), auto-computed if not provided
        """
        for entry_dict in self._entries:
            if entry_dict["id"] == change_id:
                entry_dict["success"] = success
                entry_dict["actual_outcome"] = actual
                entry_dict["verified_at"] = time.time()

                if not success:
                    entry_dict["status"] = VerificationStatus.FALSIFIED.value
                    entry_dict["score"] = score if score > 0 else 0.0
                elif score >= 0.8 or (score == 0.0 and success):
                    entry_dict["status"] = VerificationStatus.VERIFIED.value
                    entry_dict["score"] = score if score > 0 else 0.85
                else:
                    entry_dict["status"] = VerificationStatus.PARTIAL.value
                    entry_dict["score"] = score

                self._save()
                logger.info(f"Change verified: {change_id} → {entry_dict['status']} (score={entry_dict['score']:.2f})")
                return True
        logger.warning(f"Change ID not found: {change_id}")
        return False

    # ── Queries ──

    def get(self, change_id: str) -> Optional[ChangeEntry]:
        """Get a specific change entry by ID."""
        for e in self._entries:
            if e["id"] == change_id:
                return ChangeEntry(
                    id=e["id"], file=e["file"],
                    change_type=ChangeType(e["change_type"]),
                    description=e["description"],
                    predicted_outcome=e["predicted_outcome"],
                    actual_outcome=e["actual_outcome"],
                    status=VerificationStatus(e["status"]),
                    success=e["success"], score=e["score"],
                    tags=e["tags"], parent_span_id=e.get("parent_span_id", ""),
                    created_at=e["created_at"], verified_at=e["verified_at"],
                )
        return None

    def get_unverified(self) -> list[ChangeEntry]:
        """Get all changes that are still pending verification."""
        return [
            self._to_entry(e) for e in self._entries
            if e["status"] == VerificationStatus.PENDING.value
        ]

    def get_falsified(self, limit: int = 20) -> list[ChangeEntry]:
        """Get changes where prediction was falsified."""
        entries = [self._to_entry(e) for e in self._entries if e["status"] == VerificationStatus.FALSIFIED.value]
        entries.sort(key=lambda x: x.verified_at, reverse=True)
        return entries[:limit]

    def get_by_file(self, file: str) -> list[ChangeEntry]:
        """Get all changes for a specific file."""
        return [self._to_entry(e) for e in self._entries if e["file"] == file]

    def get_verification_report(self) -> dict:
        """Get a comprehensive verification report."""
        total = len(self._entries)
        if total == 0:
            return {"total_changes": 0, "verified_rate": 0.0, "falsified_rate": 0.0,
                    "avg_score": 0.0, "pending": 0, "verified": 0, "falsified": 0, "partial": 0}

        status_counts = {"pending": 0, "verified": 0, "falsified": 0, "partial": 0}
        scores = []

        for e in self._entries:
            st = e["status"]
            status_counts[st] = status_counts.get(st, 0) + 1
            if e.get("score", 0) > 0:
                scores.append(e["score"])

        verified = status_counts["verified"] + status_counts["partial"]
        return {
            "total_changes": total,
            "verified_rate": round(verified / total, 3) if total > 0 else 0.0,
            "falsified_rate": round(status_counts["falsified"] / total, 3) if total > 0 else 0.0,
            "avg_score": round(sum(scores) / len(scores), 3) if scores else 0.0,
            "pending": status_counts["pending"],
            "verified": status_counts["verified"],
            "falsified": status_counts["falsified"],
            "partial": status_counts["partial"],
        }

    def get_recent(self, n: int = 20) -> list[ChangeEntry]:
        """Get most recent changes (by creation time)."""
        entries = sorted(self._entries, key=lambda e: e["created_at"], reverse=True)
        return [self._to_entry(e) for e in entries[:n]]

    def get_stats_by_file(self) -> dict[str, dict]:
        """Get per-file verification statistics."""
        by_file: dict[str, dict] = {}
        for e in self._entries:
            f = by_file.setdefault(e["file"], {"total": 0, "verified": 0, "falsified": 0, "avg_score": 0.0, "scores": []})
            f["total"] += 1
            if e["status"] in (VerificationStatus.VERIFIED.value, VerificationStatus.PARTIAL.value):
                f["verified"] += 1
            elif e["status"] == VerificationStatus.FALSIFIED.value:
                f["falsified"] += 1
            if e.get("score", 0) > 0:
                f["scores"].append(e["score"])
        for f in by_file.values():
            f["avg_score"] = round(sum(f["scores"]) / len(f["scores"]), 3) if f["scores"] else 0.0
            del f["scores"]
        return by_file

    # ── Persistence ──

    def _save(self):
        try:
            MANIFEST_FILE.write_text(json.dumps(self._entries, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to save change manifest: {e}")

    def _load(self):
        if MANIFEST_FILE.exists():
            try:
                self._entries = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
            except Exception:
                self._entries = []

    def _to_entry(self, d: dict) -> ChangeEntry:
        return ChangeEntry(
            id=d["id"], file=d["file"], change_type=ChangeType(d["change_type"]),
            description=d["description"], predicted_outcome=d["predicted_outcome"],
            actual_outcome=d["actual_outcome"], status=VerificationStatus(d["status"]),
            success=d["success"], score=d["score"], tags=d["tags"],
            parent_span_id=d.get("parent_span_id", ""),
            created_at=d["created_at"], verified_at=d["verified_at"],
        )


# ── Singleton ──

CHANGE_MANIFEST = ChangeManifest()


def get_manifest() -> ChangeManifest:
    """Get the global ChangeManifest singleton."""
    return CHANGE_MANIFEST
