"""
MetaClaw-inspired cross-run learning system, AutoResearchClaw pattern
Evolution store for cross-run lesson extraction with time decay and auto-injection.
"""

import os
import json
import time
import re
import uuid
from typing import List, Optional, Dict, Set
from dataclasses import dataclass, field as dc_field
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict


@dataclass
class OntoEntityAudit:
    entity_id: str
    name: str
    namespace: str
    entity_type: str
    created_at: float
    last_active: float
    activity_count: int = 0
    decay_score: float = 1.0  # 1.0 = fully active, 0.0 = fully decayed
    status: str = "active"  # active, decaying, archived, error
    error_relations: List[str] = dc_field(default_factory=list)  # relation labels that have been marked as errors
    quality_score: float = 1.0  # 1.0 = high quality, 0.0 = poor
    snapshot_count: int = 0
    tags: List[str] = dc_field(default_factory=list)

@dataclass
class OntoSnapshot:
    snapshot_id: str
    entity_id: str
    timestamp: float
    entity_data: dict  # Full entity state at snapshot time
    reason: str = ""  # Why snapshot was taken


class EvolutionLesson(BaseModel):
    id: str
    session_id: str
    pattern: str
    category: str
    severity: str
    lesson_text: str
    context: str
    success_rate: float
    tokens_used: int = 0
    created_at: float
    decay_factor: float = 1.0
    times_injected: int = 0
    last_injected: float = 0.0
    tags: List[str] = Field(default_factory=list)

    model_config = ConfigDict(validate_assignment=True)


class OntologyAuditor:
    """Auditor for ontology entity evolution, decay, and quality tracking.

    Modeled after AutoResearchClaw's MetaClaw cross-run learning:
    - Tracks entity activity and applies time-decay scoring.
    - Detects stale/unused entities and marks them for archival.
    - Flags error relations discovered during cross-validation.
    - Snapshot management for rollback and version comparison.
    """

    def __init__(self, entity_store_path: str = ""):
        import os as _os
        default_root = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), "..", ".livingtree", "ontology"))
        self.storage_path: str = entity_store_path or default_root
        _os.makedirs(self.storage_path, exist_ok=True)
        self.audit_path: str = _os.path.join(self.storage_path, "audit.json")
        self.snapshots_path: str = _os.path.join(self.storage_path, "snapshots")
        _os.makedirs(self.snapshots_path, exist_ok=True)
        self.entities: dict[str, OntoEntityAudit] = {}
        self.snapshots: list[OntoSnapshot] = []
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.audit_path):
            try:
                with open(self.audit_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data:
                    e = OntoEntityAudit(**item)
                    self.entities[e.entity_id] = e
            except Exception:
                pass

    def _save(self) -> None:
        try:
            with open(self.audit_path, "w", encoding="utf-8") as f:
                json.dump([vars(e) for e in self.entities.values()], f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def register_entity(self, entity_id: str, name: str, namespace: str = "general",
                        entity_type: str = "concept", tags: List[str] | None = None) -> OntoEntityAudit:
        if entity_id in self.entities:
            e = self.entities[entity_id]
            e.last_active = time.time()
            e.activity_count += 1
            self._save()
            return e
        e = OntoEntityAudit(
            entity_id=entity_id, name=name, namespace=namespace,
            entity_type=entity_type, created_at=time.time(),
            last_active=time.time(), activity_count=1,
            tags=tags or [],
        )
        self.entities[entity_id] = e
        self._save()
        return e

    def record_activity(self, entity_id: str) -> bool:
        e = self.entities.get(entity_id)
        if not e:
            return False
        e.last_active = time.time()
        e.activity_count += 1
        e.decay_score = min(1.0, e.decay_score + 0.05)
        self._save()
        return True

    def record_error_relation(self, entity_id: str, relation_label: str) -> bool:
        e = self.entities.get(entity_id)
        if not e:
            return False
        if relation_label not in e.error_relations:
            e.error_relations.append(relation_label)
        e.quality_score = max(0.0, e.quality_score - 0.1)
        self._save()
        return True

    def snapshot(self, entity_id: str) -> str | None:
        e = self.entities.get(entity_id)
        if not e:
            return None
        snap_id = str(uuid.uuid4())
        snap = OntoSnapshot(
            snapshot_id=snap_id, entity_id=entity_id,
            timestamp=time.time(), entity_data=vars(e),
            reason="manual snapshot",
        )
        self.snapshots.append(snap)
        e.snapshot_count += 1
        try:
            snap_file = os.path.join(self.snapshots_path, f"{snap_id}.json")
            with open(snap_file, "w", encoding="utf-8") as f:
                json.dump(vars(snap), f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        self._save()
        return snap_id

    def apply_decay(self, decay_days: int = 30) -> int:
        """Apply time-decay to all entities. Returns count of archived."""
        now = time.time()
        archived = 0
        for e in self.entities.values():
            age_days = (now - e.last_active) / 86400.0
            e.decay_score = max(0.0, 1.0 - (age_days / decay_days))
            if e.decay_score < 0.1 and e.status == "active":
                e.status = "decaying"
            elif e.decay_score <= 0.0 and e.status == "decaying":
                e.status = "archived"
                archived += 1
        self._save()
        return archived

    def get_stale_entities(self, min_decay: float = 0.3) -> list[OntoEntityAudit]:
        return [e for e in self.entities.values() if e.decay_score < min_decay]

    def get_quality_report(self) -> dict:
        total = len(self.entities)
        if total == 0:
            return {"total": 0}
        low_quality = sum(1 for e in self.entities.values() if e.quality_score < 0.5)
        with_errors = sum(1 for e in self.entities.values() if e.error_relations)
        by_status = {}
        for e in self.entities.values():
            by_status[e.status] = by_status.get(e.status, 0) + 1
        return {
            "total_entities": total,
            "low_quality": low_quality,
            "with_error_relations": with_errors,
            "by_status": by_status,
            "avg_quality": round(sum(e.quality_score for e in self.entities.values()) / total, 3),
            "avg_decay": round(sum(e.decay_score for e in self.entities.values()) / total, 3),
        }

    def archive_dead_entities(self) -> int:
        """Archive entities that have fully decayed."""
        count = 0
        for e in list(self.entities.values()):
            if e.decay_score <= 0.0 and e.status == "archived":
                count += 1
        return count


class EvolutionStore:
    """Cross-run learning with SonA-inspired catastrophic forgetting protection.

    RuView SonA pattern: micro-LoRA + EWC++ enables $8 ESP32 self-learning without
    catastrophic forgetting. Applied here:
    - Golden genes: lessons that consistently produce high success → protected from
      decay/capacity eviction (EWC++ elastic weight consolidation)
    - Micro-LoRA: small, targeted "boosts" to near-expiry but proven-valuable genes
      rather than full retraining
    - Forgetting budget: tracks what was lost, alerts if critical patterns evaporate
    """

    def __init__(self, storage_subpath: Optional[str] = None, max_lessons: int = 500, decay_days: int = 30):
        # Path: livingtree/.livingtree/evolution
        default_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".livingtree", "evolution"))
        self.storage_path: str = storage_subpath or default_root
        os.makedirs(self.storage_path, exist_ok=True)
        self.json_path: str = os.path.join(self.storage_path, "lessons.json")
        self.golden_path: str = os.path.join(self.storage_path, "golden_genes.json")
        self.max_lessons = max_lessons
        self.decay_days = decay_days
        self.lessons: List[EvolutionLesson] = []
        # ── SonA: golden gene protection ──
        self.golden_genes: set[str] = set()          # lesson IDs never evicted
        self._forgetting_log: List[dict] = []         # tracks evicted patterns
        self._ewc_importances: Dict[str, float] = {}   # EWC-style per-lesson importance
        self.load()
        self._load_golden()
        self.decay_lessons()

    # internal helper: extract simple tags from a text
    def _tags_from_text(self, text: str) -> List[str]:
        words = re.findall(r"[A-Za-z0-9']+", text.lower())
        tags: List[str] = []
        for w in words:
            if len(w) >= 3:
                tags.append(w)
        seen: Set[str] = set()
        uniq: List[str] = []
        for t in tags:
            if t not in seen:
                uniq.append(t)
                seen.add(t)
        return uniq

    def load(self) -> None:
        if os.path.exists(self.json_path):
            try:
                with open(self.json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                lessons: List[EvolutionLesson] = []
                for item in data:
                    if isinstance(item, EvolutionLesson):
                        lessons.append(item)
                    elif isinstance(item, dict):
                        try:
                            lessons.append(EvolutionLesson(**item))
                        except Exception:
                            # skip invalid entries
                            pass
                self.lessons = lessons
            except Exception:
                self.lessons = []
        else:
            self.lessons = []

    def save(self) -> None:
        try:
            with open(self.json_path, "w", encoding="utf-8") as f:
                json.dump([l.model_dump() for l in self.lessons], f, ensure_ascii=False, indent=2)
        except Exception:
            # non-fatal
            pass

    def extract_lessons(self, session_id: str, reflections: List[str], metadata: Optional[Dict] = None) -> List[EvolutionLesson]:
        if not reflections:
            return []
        new_lessons: List[EvolutionLesson] = []

        pattern_from_meta: Optional[str] = None
        if isinstance(metadata, dict):
            p = metadata.get("pattern")
            if p:
                mapping = {
                    "code_review": "code",
                    "code-review": "code",
                    "reasoning": "reasoning",
                    "summarize": "generation",
                    "summarization": "generation",
                    "generate": "generation",
                    "generation": "generation",
                    "analysis": "analysis",
                }
                pattern_from_meta = str(p).lower()
                pattern_from_meta = mapping.get(pattern_from_meta, pattern_from_meta)

        for ref in reflections:
            text = str(ref).strip()
            if not text:
                continue
            lowered = text.lower()
            category = "insight"
            severity = "low"
            if "failed" in lowered or "error" in lowered or "exception" in lowered:
                category, severity = "failure", "high"
            elif "warning" in lowered or "slow" in lowered:
                category, severity = "warning", "medium"
            elif any(k in lowered for k in ["ok", "passed", "learned", "improved", "success"]):
                category, severity = "insight", "low"

            pattern: str = "generation"
            if pattern_from_meta:
                pattern = pattern_from_meta
            else:
                if isinstance(metadata, dict) and "pattern" in metadata:
                    val = str(metadata["pattern"]).lower()
                    mapping = {
                        "code_review": "code",
                        "code-review": "code",
                        "reasoning": "reasoning",
                        "summarize": "generation",
                        "summarization": "generation",
                        "generate": "generation",
                        "generation": "generation",
                        "analysis": "analysis",
                    }
                    pattern = mapping.get(val, val)

            success_rate = 0.5
            if isinstance(metadata, dict) and "success_rate" in metadata:
                try:
                    success_rate = float(metadata["success_rate"])
                except Exception:
                    pass

            lesson = EvolutionLesson(
                id=str(uuid.uuid4()),
                session_id=session_id,
                pattern=pattern,
                category=category,
                severity=severity,
                lesson_text=text,
                context=f"session {session_id} reflections",
                success_rate=float(success_rate),
                tokens_used=0,
                created_at=time.time(),
                decay_factor=1.0,
                times_injected=0,
                last_injected=0.0,
                tags=self._tags_from_text(text),
            )
            new_lessons.append(lesson)

            if isinstance(success_rate, (int, float)) and float(success_rate) >= 0.8:
                extra = EvolutionLesson(
                    id=str(uuid.uuid4()),
                    session_id=session_id,
                    pattern="generation",
                    category="insight",
                    severity="low",
                    lesson_text=f"High-success pattern observed: {text}",
                    context=f"auto-injected due to high success rate in session {session_id}",
                    success_rate=0.95,
                    tokens_used=0,
                    created_at=time.time(),
                    decay_factor=1.0,
                    times_injected=0,
                    last_injected=0.0,
                    tags=["high_success", "auto_injected"],
                )
                new_lessons.append(extra)

        if new_lessons:
            self.lessons.extend(new_lessons)
            # Decay pass to integrate with existing data
            self.decay_lessons()
            if len(self.lessons) > self.max_lessons:
                self.lessons = self.lessons[-self.max_lessons:]
            self.save()
        return new_lessons

    def _score_for_inject(self, l: EvolutionLesson, keywords: Set[str]) -> int:
        text = " ".join([l.lesson_text, l.context, " ".join(l.tags)]).lower()
        score = 0
        for kw in keywords:
            if kw and kw in text:
                score += 2
        sev_w = {"high": 3, "medium": 2, "low": 1}
        score += sev_w.get(l.severity, 1)
        return score

    def inject_lessons(self, intent_or_task: str, top_k: int = 5) -> str:
        if not intent_or_task:
            return "No intent provided."
        keywords: Set[str] = set(re.findall(r"[A-Za-z0-9_]+", intent_or_task.lower()))
        scored: List[tuple[int, EvolutionLesson]] = []  # type: ignore
        for l in self.lessons:
            if l.decay_factor <= 0.1:
                continue
            score = self._score_for_inject(l, keywords)
            scored.append((score, l))
        scored.sort(key=lambda t: (-t[0], -t[1].decay_factor, t[1].created_at))
        selected = [item[1] for item in scored[:top_k]]
        if not selected:
            return "No relevant lessons available for injection."
        now = time.time()
        lines: List[str] = []
        for l in selected:
            l.times_injected += 1
            l.last_injected = now
            lines.append(f"- [{l.severity.upper()}] {l.lesson_text} (pattern={l.pattern}, category={l.category})")
        self.save()
        injection_text = "## Lessons from past experience:\n" + "\n".join(lines)
        # Decay after injection to reflect usage
        self.decay_lessons()
        return injection_text

    def get_relevant_lessons(self, intent_or_task: str, top_k: int = 5, min_decay: float = 0.1) -> List[EvolutionLesson]:
        if not self.lessons:
            return []
        keywords: Set[str] = set(re.findall(r"[A-Za-z0-9_]+", intent_or_task.lower()))
        scored: List[tuple[int, EvolutionLesson]] = []
        for l in self.lessons:
            if l.decay_factor < min_decay:
                continue
            text = " ".join([l.lesson_text, l.context, " ".join(l.tags)]).lower()
            score = 0
            for kw in keywords:
                if kw and kw in text:
                    score += 1
            scored.append((score, l))
        scored.sort(key=lambda t: (-t[0], -t[1].decay_factor, t[1].created_at))
        return [t[1] for t in scored[:top_k]]

    def decay_lessons(self) -> int:
        """Decay with golden gene protection (SonA EWC++ pattern)."""
        return self.decay_lessons_with_protection()

    # ── SonA: Golden Gene Protection (RuView self-learning pattern) ──

    def _load_golden(self) -> None:
        """Load golden gene IDs from persistent storage."""
        if os.path.exists(self.golden_path):
            try:
                with open(self.golden_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.golden_genes = set(data.get("golden_ids", []))
                self._ewc_importances = data.get("ewc_importances", {})
            except Exception:
                self.golden_genes = set()

    def _save_golden(self) -> None:
        """Persist golden gene IDs and EWC importance weights."""
        try:
            with open(self.golden_path, "w", encoding="utf-8") as f:
                json.dump({
                    "golden_ids": list(self.golden_genes),
                    "ewc_importances": self._ewc_importances,
                }, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def protect_gene(self, lesson_id: str) -> bool:
        """Mark a lesson as a golden gene — immune to decay eviction (EWC++).

        Requirements for golden status:
        - success_rate >= 0.85
        - times_injected >= 3 (proven value)
        - category != 'failure' (don't protect bad patterns)
        """
        for l in self.lessons:
            if l.id == lesson_id:
                if l.success_rate >= 0.85 and l.times_injected >= 3 and l.category != "failure":
                    self.golden_genes.add(lesson_id)
                    # EWC importance: higher for more successful + more injected
                    self._ewc_importances[lesson_id] = l.success_rate * min(1.0, l.times_injected / 10.0)
                    l.decay_factor = 1.0  # Reset decay to max
                    if "golden" not in l.tags:
                        l.tags.append("golden")
                    self._save_golden()
                    self.save()
                    return True
                return False
        return False

    def auto_protect_genes(self) -> int:
        """Automatically identify and protect golden genes based on performance.

        Scans all lessons, promotes qualifying ones to golden status.
        Returns count of newly protected genes.
        """
        count = 0
        for l in self.lessons:
            if l.id not in self.golden_genes:
                if self.protect_gene(l.id):
                    count += 1
        return count

    def unprotect_gene(self, lesson_id: str) -> bool:
        """Remove golden protection (e.g., if pattern becomes obsolete)."""
        if lesson_id in self.golden_genes:
            self.golden_genes.discard(lesson_id)
            self._ewc_importances.pop(lesson_id, None)
            for l in self.lessons:
                if l.id == lesson_id:
                    if "golden" in l.tags:
                        l.tags.remove("golden")
                    break
            self._save_golden()
            self.save()
            return True
        return False

    def _ewc_decay_boost(self, lesson: EvolutionLesson) -> float:
        """EWC++ elastic weight consolidation: near-expiry golden genes get micro-boost.

        RuView SonA: prevents catastrophic forgetting by adding an elastic penalty
        to parameter updates that would overwrite important knowledge. Here, instead
        of zeroing out decay, we give a small boost to keep golden genes alive longer.

        Returns: decay_factor boost (0.0 = no boost, 1.0 = full preservation).
        """
        if lesson.id not in self.golden_genes:
            return 0.0
        importance = self._ewc_importances.get(lesson.id, 0.5)
        # Boost proportional to importance × proximity to expiry
        age_days = (time.time() - lesson.created_at) / 86400.0
        decay_progress = age_days / max(self.decay_days, 1)
        # More boost when closer to expiry (elastic pull-back)
        return importance * decay_progress * 0.5

    def get_golden_lessons(self, intent_or_task: str = "", top_k: int = 5) -> List[EvolutionLesson]:
        """Retrieve golden genes relevant to the task (prioritized injection)."""
        golden = [l for l in self.lessons if l.id in self.golden_genes]
        if not golden:
            return []
        if not intent_or_task:
            return golden[:top_k]
        # Score by relevance to intent
        keywords = set(re.findall(r"[A-Za-z0-9_]+", intent_or_task.lower()))
        scored = []
        for l in golden:
            text = " ".join([l.lesson_text, l.context, " ".join(l.tags)]).lower()
            score = sum(2 for kw in keywords if kw in text)
            # Golden genes get bonus for high EWC importance
            score += self._ewc_importances.get(l.id, 0) * 5
            scored.append((score, l))
        scored.sort(key=lambda t: (-t[0], -t[1].times_injected))
        return [t[1] for t in scored[:top_k]]

    def record_forgetting(self, evicted_lesson: EvolutionLesson) -> None:
        """Log evicted patterns to track forgetting budget."""
        self._forgetting_log.append({
            "id": evicted_lesson.id,
            "pattern": evicted_lesson.pattern,
            "category": evicted_lesson.category,
            "success_rate": evicted_lesson.success_rate,
            "times_injected": evicted_lesson.times_injected,
            "evicted_at": time.time(),
            "was_golden": evicted_lesson.id in self.golden_genes,
        })
        if len(self._forgetting_log) > 200:
            self._forgetting_log = self._forgetting_log[-200:]

    def get_forgetting_stats(self) -> dict:
        """Forgetting budget report: what was lost, is critical knowledge evaporating?"""
        if not self._forgetting_log:
            return {"evicted_total": 0}
        high_value_lost = sum(1 for f in self._forgetting_log
                             if f["success_rate"] >= 0.7 and f["times_injected"] >= 2)
        golden_lost = sum(1 for f in self._forgetting_log if f["was_golden"])
        patterns_lost = {}
        for f in self._forgetting_log:
            p = f["pattern"]
            patterns_lost[p] = patterns_lost.get(p, 0) + 1
        critical_loss = any(f["was_golden"] for f in self._forgetting_log[-20:])
        return {
            "evicted_total": len(self._forgetting_log),
            "high_value_evicted": high_value_lost,
            "golden_evicted": golden_lost,
            "top_lost_patterns": sorted(patterns_lost.items(), key=lambda x: -x[1])[:5],
            "critical_loss_detected": critical_loss,
            "recommendation": "increase capacity" if critical_loss else "stable",
        }

    # ── Enhanced decay with golden gene protection ──

    def decay_lessons_with_protection(self) -> int:
        """Decay all lessons, but golden genes get EWC-style micro-boost (SonA pattern)."""
        now = time.time()
        removed = 0
        new_list: List[EvolutionLesson] = []
        for l in self.lessons:
            age_days = (now - l.created_at) / 86400.0
            df = max(0.0, 1.0 - (age_days / float(self.decay_days)))
            # EWC elastic boost for golden genes
            if l.id in self.golden_genes:
                boost = self._ewc_decay_boost(l)
                df = min(1.0, df + boost)
            l.decay_factor = df
            if df <= 0.0:
                if l.id in self.golden_genes:
                    # Golden genes survive with a floor
                    l.decay_factor = 0.01
                    new_list.append(l)
                    continue
                if l.category != "failure":
                    self.record_forgetting(l)
                    removed += 1
                    continue
                else:
                    l.decay_factor = 0.0
                    if "archived" not in l.tags:
                        l.tags.append("archived")
            new_list.append(l)
        self.lessons = new_list
        self.save()
        return removed
        total = len(self.lessons)
        by_category: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        by_pattern: Dict[str, int] = {}
        total_sr = 0.0
        count_sr = 0
        most_injected: Optional[EvolutionLesson] = None
        for l in self.lessons:
            by_category[l.category] = by_category.get(l.category, 0) + 1
            by_severity[l.severity] = by_severity.get(l.severity, 0) + 1
            by_pattern[l.pattern] = by_pattern.get(l.pattern, 0) + 1
            total_sr += l.success_rate
            count_sr += 1
            if most_injected is None or l.times_injected > most_injected.times_injected:
                most_injected = l
        avg_sr = (total_sr / count_sr) if count_sr else 0.0
        active = sum(1 for l in self.lessons if l.decay_factor > 0.5)
        archived = sum(1 for l in self.lessons if l.decay_factor <= 0.5)
        top_patterns = sorted(by_pattern.items(), key=lambda kv: kv[1], reverse=True)[:5]
        return {
            "total_lessons": total,
            "golden_genes": len(self.golden_genes),
            "by_category": by_category,
            "by_severity": by_severity,
            "by_pattern": by_pattern,
            "avg_success_rate": avg_sr,
            "active_lessons": active,
            "archived_lessons": archived,
            "most_injected": {
                "id": most_injected.id if most_injected else None,
                "times_injected": most_injected.times_injected if most_injected else 0,
            } if most_injected else None,
            "top_patterns": top_patterns,
        }

    def clear(self) -> None:
        self.lessons = []
        self.save()

    def get_lessons_by_pattern(self, pattern: str) -> List[EvolutionLesson]:
        if not pattern:
            return list(self.lessons)
        pat = pattern.lower()
        out: List[EvolutionLesson] = []
        for l in self.lessons:
            if l.pattern.lower() == pat or any((str(t).lower() == pat) for t in l.tags):
                out.append(l)
        return out

    # Simple helper to enforce capacity in case external edits happen
    def _enforce_capacity_and_save(self) -> None:
        if len(self.lessons) > self.max_lessons:
            self.lessons = self.lessons[-self.max_lessons:]
        self.save()


# Singleton instance
EVOLUTION_STORE = EvolutionStore()


def get_evolution_store() -> EvolutionStore:
    return EVOLUTION_STORE
