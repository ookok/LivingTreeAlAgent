"""Online/Offline Dual Mode — P2P sync for disconnected operation.

When internet is available, LivingTree uses LongCat/DeepSeek cloud models
and syncs KnowledgeBase + StructMem + ConversationDNA to peer nodes.
When offline, it automatically switches to local Ollama models and queues
sync operations for when connectivity returns.

Usage:
    dual = DualMode(node, knowledge_base, struct_memory, offline_model="ollama/qwen3")
    
    # Auto-detected:
    status = await dual.check()
    # → {online: True, provider: "longcat", queue_size: 0}
    
    # Auto-sync when reconnecting:
    await dual.sync_on_reconnect()
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class SyncQueueItem:
    id: str
    action: str
    data: dict
    timestamp: str
    retry_count: int = 0
    max_retries: int = 5

    def to_dict(self) -> dict:
        return {
            "id": self.id, "action": self.action, "data": self.data,
            "timestamp": self.timestamp, "retry_count": self.retry_count,
        }


class DualMode:
    """Manages online/offline transitions and P2P sync."""

    SYNC_FILE = ".livingtree/sync_queue.jsonl"
    HEARTBEAT_URLS = [
        "https://api.deepseek.com/v1/models",
        "https://www.google.com/generate_204",
    ]
    CHECK_INTERVAL = 30.0
    MAX_QUEUE_SIZE = 1000

    def __init__(
        self,
        node: Any = None,
        knowledge_base: Any = None,
        struct_memory: Any = None,
        offline_model: str = "ollama/qwen3:latest",
    ):
        self._node = node
        self._kb = knowledge_base
        self._struct_mem = struct_memory
        self._offline_model = offline_model
        self._online: bool | None = None
        self._queue: list[SyncQueueItem] = []
        self._task: asyncio.Task | None = None
        self._load_queue()

    async def check(self) -> dict:
        online = await self._ping()
        changed = self._online is not None and online != self._online

        if changed:
            if online:
                logger.info("Online mode restored")
                await self._sync_queued()
            else:
                logger.warning("Switching to offline mode")

        self._online = online

        return {
            "online": online,
            "provider": "longcat" if online else self._offline_model,
            "queue_size": len(self._queue),
            "mode_changed": changed,
        }

    async def start_monitoring(self) -> None:
        if self._task:
            return
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("DualMode monitoring started")

    async def stop_monitoring(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def queue_sync(self, action: str, data: dict) -> str:
        from datetime import datetime, timezone
        import uuid

        if len(self._queue) >= self.MAX_QUEUE_SIZE:
            self._queue = self._queue[-self.MAX_QUEUE_SIZE // 2:]

        item = SyncQueueItem(
            id=uuid.uuid4().hex[:12],
            action=action,
            data=data,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._queue.append(item)
        self._save_queue()
        return item.id

    async def sync_on_reconnect(self) -> dict:
        synced = 0
        failed = 0

        if not self._online:
            return {"synced": 0, "queued": len(self._queue)}

        remaining = []
        for item in self._queue:
            ok = await self._sync_item(item)
            if ok:
                synced += 1
            else:
                item.retry_count += 1
                if item.retry_count < item.max_retries:
                    remaining.append(item)
                else:
                    failed += 1

        self._queue = remaining
        self._save_queue()

        if synced:
            logger.info(f"DualMode synced {synced} items, {len(remaining)} remaining")

        return {"synced": synced, "failed": failed, "queued": len(self._queue)}

    def get_status(self) -> dict:
        return {
            "online": self._online,
            "provider": "longcat" if self._online else self._offline_model,
            "queue_size": len(self._queue),
            "sync_file": str(Path(self.SYNC_FILE)),
        }

    async def _ping(self) -> bool:
        import aiohttp
        try:
            async with aiohttp.ClientSession() as s:
                for url in self.HEARTBEAT_URLS:
                    try:
                        async with s.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                            if resp.status < 500:
                                return True
                    except Exception:
                        continue
            return False
        except Exception:
            return False

    async def _sync_item(self, item: SyncQueueItem) -> bool:
        try:
            if item.action == "kb_add" and self._kb:
                from ..knowledge.knowledge_base import Document
                d = item.data
                doc = Document(
                    title=d.get("title", ""),
                    content=d.get("content", ""),
                    domain=d.get("domain"),
                    source=d.get("source", "offline_sync"),
                    metadata=d.get("metadata", {}),
                )
                self._kb.add_knowledge(doc)
                return True

            elif item.action == "struct_mem_bind" and self._struct_mem:
                entries = await self._struct_mem.bind_events(
                    session_id=item.data.get("session_id", "offline"),
                    messages=item.data.get("messages", []),
                    timestamp=item.data.get("timestamp"),
                )
                return len(entries) > 0

            return True

        except Exception as e:
            logger.debug(f"Sync item {item.id}: {e}")
            return False

    async def _sync_queued(self) -> None:
        if self._queue:
            await self.sync_on_reconnect()

    async def _monitor_loop(self) -> None:
        while True:
            try:
                await self.check()
            except Exception as e:
                logger.debug(f"DualMode monitor: {e}")
            await asyncio.sleep(self.CHECK_INTERVAL)

    def _load_queue(self) -> None:
        path = Path(self.SYNC_FILE)
        if not path.exists():
            return
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                data = json.loads(line)
                self._queue.append(SyncQueueItem(**data))
            logger.debug(f"DualMode loaded {len(self._queue)} queued items")
        except Exception:
            pass

    def _save_queue(self) -> None:
        path = Path(self.SYNC_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "\n".join(json.dumps(i.to_dict(), ensure_ascii=False) for i in self._queue),
            encoding="utf-8",
        )
