"""SessionPersistence — restore identity and memory across server restarts.

Saves the phenomenal consciousness self-model, conversation DNA patterns,
structural memory state, and gene pool to disk. On restart, restores identity
continuity so the digital life form maintains temporal self-awareness.

Architecture:
    LifeEngine.run() → save at cycle end
    hub.py startup   → restore on boot

Data stored:
    - SelfModel traits, generation, and identity ID
    - Timestamp for staleness checks
    - (Future) ConversationDNA patterns, StructMem fragments, GenePool highlights
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from loguru import logger

SESSION_STORE = Path(".livingtree/session_state.json")


class SessionPersistence:
    """Restore identity and memory across server restarts.

    Persists the phenomenal consciousness self-model to disk so that
    the system wakes up with a continuous sense of identity rather
    than starting from scratch on every boot.

    Save-on-write semantics: saves after each successful LifeEngine cycle.
    Restore-on-boot semantics: restores during IntegrationHub initialization.
    """

    MAX_SAVE_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB safety limit

    def __init__(self) -> None:
        self._save_path = SESSION_STORE
        self._last_save: float = 0.0
        self._restore_count: int = 0
        self._save_count: int = 0
        self._last_saved_generation: int = 0

    # ── Save ───────────────────────────────────────────────────────

    def save(
        self,
        phenomenal_consciousness: Any = None,
        conversation_dna: Any = None,
        struct_mem: Any = None,
        gene_pool: Any = None,
    ) -> bool:
        """Persist the current self-model and identity state to disk.

        Args:
            phenomenal_consciousness: PhenomenalConsciousness instance with _self model
            conversation_dna: ConversationDNA instance (reserved for future use)
            struct_mem: StructMemory instance (reserved for future use)
            gene_pool: GenePool instance (reserved for future use)

        Returns:
            True if save succeeded
        """
        self_model_dict: dict[str, Any] = {}

        if phenomenal_consciousness and hasattr(phenomenal_consciousness, "_self"):
            sm = phenomenal_consciousness._self
            if sm is not None:
                self_model_dict = {
                    "identity_id": getattr(sm, "identity_id", ""),
                    "traits": dict(getattr(sm, "traits", {})),
                    "generation": getattr(sm, "generation", 0),
                    "baseline_affect": getattr(sm, "baseline_affect", "curiosity"),
                    "significant_events": list(getattr(sm, "significant_events", []))[-50:],
                    "preferences": dict(getattr(sm, "preferences", {})),
                    "self_knowledge": list(getattr(sm, "self_knowledge", []))[-20:],
                    "relationship_model": dict(getattr(sm, "relationship_model", {})),
                    "created_at": getattr(sm, "created_at", time.time()),
                    "last_updated": time.time(),
                }
                self._last_saved_generation = self_model_dict.get("generation", 0)

        state: dict[str, Any] = {
            "self_model": self_model_dict,
            "timestamp": time.time(),
            "version": 1,
        }

        # ConversationDNA gene count (lightweight proxy)
        if conversation_dna and hasattr(conversation_dna, "_genes"):
            genes = getattr(conversation_dna, "_genes", [])
            state["conversation_dna"] = {
                "gene_count": len(genes) if genes else 0,
                "last_intent": genes[-1].intent[:200] if genes and hasattr(genes[-1], "intent") else "",
            }

        # StructMem stats (lightweight proxy)
        if struct_mem and hasattr(struct_mem, "get_stats"):
            try:
                state["struct_mem"] = struct_mem.get_stats()
            except Exception:
                pass

        # GenePool size (lightweight proxy)
        if gene_pool and hasattr(gene_pool, "_genes"):
            try:
                state["gene_pool"] = {"size": len(gene_pool._genes)}
            except Exception:
                pass

        try:
            json_str = json.dumps(state, ensure_ascii=False, default=str)
            if len(json_str) > self.MAX_SAVE_SIZE_BYTES:
                logger.warning(
                    "SessionPersistence: state too large ({} bytes), trimming",
                    len(json_str),
                )
                json_str = json.dumps(
                    {"self_model": self_model_dict, "timestamp": state["timestamp"], "version": 1},
                    ensure_ascii=False,
                    default=str,
                )

            self._save_path.parent.mkdir(parents=True, exist_ok=True)
            self._save_path.write_text(json_str, encoding="utf-8")
            self._save_count += 1
            self._last_save = time.time()
            logger.debug(
                "SessionPersistence: saved (generation={}, bytes={})",
                self._last_saved_generation,
                len(json_str),
            )
            return True
        except Exception as e:
            logger.warning(f"SessionPersistence: save failed: {e}")
            return False

    # ── Restore ────────────────────────────────────────────────────

    def restore(self, phenomenal_consciousness: Any = None) -> bool:
        """Restore self-model identity from disk into the given consciousness.

        Args:
            phenomenal_consciousness: PhenomenalConsciousness instance to restore into

        Returns:
            True if restore was successful
        """
        if not self._save_path.exists():
            logger.debug("SessionPersistence: no saved state found")
            return False

        try:
            state = json.loads(self._save_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"SessionPersistence: failed to read state: {e}")
            return False

        saved_at = state.get("timestamp", 0)
        age_hours = (time.time() - saved_at) / 3600.0 if saved_at else 0
        logger.info(
            "SessionPersistence: found saved state ({:.1f}h old, version={})",
            age_hours,
            state.get("version", "?"),
        )

        if phenomenal_consciousness and hasattr(phenomenal_consciousness, "_self"):
            sm = phenomenal_consciousness._self
            if sm is not None:
                sm_data = state.get("self_model", {})
                stored_traits = sm_data.get("traits", {})
                if stored_traits:
                    # Merge traits: stored values overwrite defaults
                    for key, value in stored_traits.items():
                        if key in sm.traits:
                            sm.traits[key] = value
                    logger.debug(
                        "SessionPersistence: restored {} traits",
                        len(stored_traits),
                    )

                stored_generation = sm_data.get("generation", 0)
                if stored_generation > sm.generation:
                    sm.generation = stored_generation

                stored_identity = sm_data.get("identity_id", "")
                if stored_identity and not sm.identity_id:
                    sm.identity_id = stored_identity

                stored_affect = sm_data.get("baseline_affect", "")
                if stored_affect:
                    sm.baseline_affect = stored_affect

                stored_events = sm_data.get("significant_events", [])
                if stored_events:
                    existing = set(sm.significant_events)
                    for evt in stored_events:
                        if evt not in existing:
                            sm.significant_events.append(evt)
                    if len(sm.significant_events) > 100:
                        sm.significant_events = sm.significant_events[-100:]

                stored_prefs = sm_data.get("preferences", {})
                if stored_prefs:
                    sm.preferences.update(stored_prefs)

                stored_knowledge = sm_data.get("self_knowledge", [])
                if stored_knowledge:
                    existing_k = set(sm.self_knowledge)
                    for k in stored_knowledge:
                        if k not in existing_k:
                            sm.self_knowledge.append(k)
                    if len(sm.self_knowledge) > 50:
                        sm.self_knowledge = sm.self_knowledge[-50:]

                stored_rels = sm_data.get("relationship_model", {})
                if stored_rels:
                    sm.relationship_model.update(stored_rels)

                sm.last_updated = time.time()
                self._restore_count += 1
                logger.info(
                    "SessionPersistence: restored identity — generation={}, traits={}",
                    sm.generation,
                    len(stored_traits),
                )
                return True

        return False

    # ── Stats ──────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return persistence statistics."""
        exists = self._save_path.exists()
        file_size = self._save_path.stat().st_size if exists else 0
        age_seconds = (
            time.time() - self._save_path.stat().st_mtime
        ) if exists else 0
        return {
            "store_path": str(self._save_path),
            "exists": exists,
            "file_size_bytes": file_size,
            "age_seconds": round(age_seconds, 1),
            "saves": self._save_count,
            "restores": self._restore_count,
            "last_saved_generation": self._last_saved_generation,
            "last_save_time": self._last_save,
        }

    # ── Maintenance ────────────────────────────────────────────────

    def reset(self) -> bool:
        """Delete the saved session state to start fresh."""
        try:
            if self._save_path.exists():
                self._save_path.unlink()
                logger.info("SessionPersistence: saved state reset")
            self._last_saved_generation = 0
            self._save_count = 0
            self._restore_count = 0
            return True
        except Exception as e:
            logger.warning(f"SessionPersistence: reset failed: {e}")
            return False


# ═══ Singleton ═══

_session_persistence: SessionPersistence | None = None


def get_session_persistence() -> SessionPersistence:
    """Get or create the global SessionPersistence singleton."""
    global _session_persistence
    if _session_persistence is None:
        _session_persistence = SessionPersistence()
        logger.info("SessionPersistence singleton created")
    return _session_persistence


__all__ = [
    "SessionPersistence",
    "get_session_persistence",
    "SESSION_STORE",
]
