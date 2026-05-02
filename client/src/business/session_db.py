"""
Session DB + Unified Context — Re-export from livingtree.core.session.manager

Full migration complete. Import from new location.
"""

from livingtree.core.session.manager import (
    SessionManager, SessionInfo, MessageRecord,
    ContextEntry, UnifiedContext,
    get_session_manager,
)

# Compatibility — old SessionDB API
SessionDB = SessionManager


def get_session_db(db_path=None):
    return SessionManager(db_path) if db_path else get_session_manager()


__all__ = [
    "SessionManager", "SessionDB", "SessionInfo", "MessageRecord",
    "ContextEntry", "UnifiedContext",
    "get_session_manager", "get_session_db",
]
