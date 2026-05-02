"""
Message Sync Service — Re-export from livingtree.core.agent.comm

Full migration complete.
"""

from livingtree.core.agent.comm import (
    MessageSyncService, MessageChannel, SyncMessage, get_message_sync_service,
)

__all__ = ["MessageSyncService", "MessageChannel", "SyncMessage", "get_message_sync_service"]
