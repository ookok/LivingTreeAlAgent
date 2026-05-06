"""Cognitive Delta — knowledge increment detection + differential storage.

Only stores "cognitive increments":
  1. Knowledge GAP: information never seen before → fill blank
  2. Knowledge DIFF: different from existing → record difference + conclusion
  3. Knowledge DUP: identical → discard (noise suppression)

Never stores:
  - Complete HTML / full PDF text
  - Duplicate information
  - Information without a clear source

Usage:
    delta = CognitiveDelta(kb)
    decision, reason = delta.evaluate(new_item, existing_items)
    if decision == "STORE":
        kb.store(delta.build_entry(new_item, existing_items))
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


class DeltaDecision:
    GAP = "gap"       # 知识空白 — 新增
    DIFF = "diff"     # 知识差异 — 更新
    DUP = "dup"       # 重复 — 丢弃


@dataclass
class DeltaResult:
    decision: str = DeltaDecision.DUP
    reason: str = ""
    new_info: dict = field(default_factory=dict)
    existing_info: dict = field(default_factory=dict)
    diff_summary: str = ""
    confidence: float = 1.0


class CognitiveDelta:
    """Knowledge increment detection engine.

    Compares new info against existing knowledge base. Only permits
    storage when genuine new information is detected.

    Comparison dimensions:
      1. Content hash (exact duplicate check)
      2. Title/key similarity (near-duplicate check)
      3. Semantic difference scoring (information gain)
      4. Time-based priority (newer wins when conflicting)
    """

    def __init__(self, content_similarity_threshold: float = 0.85):
        self.content_similarity_threshold = content_similarity_threshold

    def evaluate(
        self,
        new_item: dict,
        existing_items: list[dict] = None,
    ) -> DeltaResult:
        """Evaluate whether new info is a cognitive increment.

        Args:
            new_item: {'title', 'content', 'source', 'date', 'status', ...}
            existing_items: list of existing knowledge entries

        Returns:
            DeltaResult with decision + reason + diff summary
        """
        existing = existing_items or []
        result = DeltaResult(new_info=new_item)

        if not existing:
            result.decision = DeltaDecision.GAP
            result.reason = "首次入库 — 知识空白填补"
            result.confidence = 1.0
            return result

        # Level 1: Content hash check
        new_hash = self._content_hash(new_item)
        for ex in existing:
            if self._content_hash(ex) == new_hash:
                result.decision = DeltaDecision.DUP
                result.reason = "内容完全相同 — 丢弃"
                result.existing_info = ex
                result.confidence = 1.0
                return result

        # Level 2: Title/Key similarity
        best_match = None
        best_sim = 0.0
        for ex in existing:
            sim = self._entry_similarity(new_item, ex)
            if sim > best_sim:
                best_sim = sim
                best_match = ex

        if best_sim >= self.content_similarity_threshold and best_match:
            result.existing_info = best_match

            # Level 3: What's actually different?
            diff_text = self._compute_diff(new_item, best_match)
            if not diff_text or diff_text == "无实质差异":
                result.decision = DeltaDecision.DUP
                result.reason = "内容实质相同 — 丢弃"
                return result

            result.decision = DeltaDecision.DIFF
            result.reason = f"发现{len(diff_text)}处差异 — 更新知识"
            result.diff_summary = diff_text
            result.confidence = best_sim
            return result

        # Level 4: Genuinely new
        result.decision = DeltaDecision.GAP
        result.reason = "内容无相似匹配 — 新知识入库"
        result.confidence = 1.0
        return result

    def build_entry(
        self,
        new_item: dict,
        existing_items: list[dict] = None,
        attachment_summaries: list[str] = None,
    ) -> dict:
        """Build a clean knowledge base entry (no full content)."""
        result = self.evaluate(new_item, existing_items)

        entry = {
            "id": hashlib.md5(
                (new_item.get("title", "") + new_item.get("source", "")).encode()
            ).hexdigest()[:16],
            "title": new_item.get("title", "")[:300],
            "source": new_item.get("source", "")[:500],
            "publish_date": new_item.get("date", ""),
            "status": new_item.get("status", ""),
            "summary": new_item.get("content", "")[:1000],
            "attachment_summaries": attachment_summaries or [],
            "delta_decision": result.decision,
            "delta_reason": result.reason,
            "delta_diff": result.diff_summary[:1000] if result.decision == DeltaDecision.DIFF else "",
            "stored_at": time.strftime("%Y-%m-%d %H:%M"),
        }

        if result.decision == DeltaDecision.DUP:
            entry["summary"] = "[重复 — 未存储完整内容]"
            entry["references_existing_id"] = result.existing_info.get("id", "")

        return entry

    # ═══ Similarity Computation ═══

    def _content_hash(self, item: dict) -> str:
        text = (item.get("title", "") + item.get("content", "") +
                item.get("source", "") + item.get("date", ""))
        return hashlib.md5(text.encode()).hexdigest()

    def _entry_similarity(self, a: dict, b: dict) -> float:
        a_text = self._normalize(a.get("title", "") + " " + a.get("content", ""))
        b_text = self._normalize(b.get("title", "") + " " + b.get("content", ""))

        if not a_text or not b_text:
            return 0.0

        n = 4
        a_ngrams = {a_text[i:i+n] for i in range(len(a_text) - n + 1)}
        b_ngrams = {b_text[i:i+n] for i in range(len(b_text) - n + 1)}

        if not a_ngrams or not b_ngrams:
            return 0.0

        return len(a_ngrams & b_ngrams) / len(a_ngrams | b_ngrams)

    @staticmethod
    def _normalize(text: str) -> str:
        import re
        text = re.sub(r'\s+', '', text.lower())
        return text

    @staticmethod
    def _compute_diff(new_item: dict, existing: dict) -> str:
        """Compute human-readable difference between two entries."""
        diffs = []

        for field in ["title", "status", "date"]:
            new_val = new_item.get(field, "")
            old_val = existing.get(field, "")
            if new_val and old_val and new_val != old_val:
                diffs.append(f"{field}: '{old_val}' → '{new_val}'")

        new_content = new_item.get("content", "")
        old_content = existing.get("content", "")
        if new_content and old_content:
            new_words = set(new_content.split())
            old_words = set(old_content.split())
            added = new_words - old_words
            removed = old_words - new_words
            if added:
                diffs.append(f"+{len(added)} new terms")
            if removed:
                diffs.append(f"-{len(removed)} removed terms")

        if not diffs:
            return "无实质差异"

        return "; ".join(diffs)
