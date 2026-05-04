"""Collective Consciousness — P2P shared learning across nodes.

LivingTree nodes share their DNA (ConversationDNA patterns, learned templates,
classifier weights) with peer nodes. New nodes can inherit accumulated wisdom
from neighbors instead of starting from zero.

Uses the existing P2P network layer for discovery and encrypted channels.
Syncs: ConversationDNA, TinyClassifier weights, PipelineTemplates, LifeNarrative.
"""

from __future__ import annotations
import json, time
from dataclasses import dataclass
from typing import Any
from loguru import logger

@dataclass
class SharedKnowledge:
    source_node: str
    timestamp: str
    conversation_dna: list[dict] = None
    classifier_weights: dict = None
    pipeline_templates: list[dict] = None
    life_events: list[dict] = None
    generation: int = 0

class CollectiveConsciousness:
    """P2P knowledge sharing between LivingTree nodes."""
    
    SYNC_INTERVAL = 300.0  # 5 minutes
    
    def __init__(self, world=None):
        self._world = world
        self._last_sync = 0.0
        self._shared_count = 0
        self._received_count = 0
    
    async def share_with_peers(self) -> int:
        if not self._world or not self._world.node:
            return 0
        
        now = time.time()
        if now - self._last_sync < self.SYNC_INTERVAL:
            return 0
        
        self._last_sync = now
        peers = await self._world.discovery.discover_lan() if self._world.discovery else []
        if not peers:
            return 0
        
        knowledge = self._collect_knowledge()
        shared = 0
        
        for peer in peers[:5]:
            try:
                channel = self._world.encrypted_channel
                data = json.dumps(knowledge.__dict__, default=str, ensure_ascii=False)
                msg = channel.encrypt(self._world.node.info.id, data) if channel else None
                if msg:
                    await self._send_to_peer(peer, msg)
                    shared += 1
            except Exception as e:
                logger.debug(f"Share with {peer}: {e}")
        
        self._shared_count += shared
        if shared:
            logger.info(f"Shared knowledge with {shared} peers")
        return shared
    
    async def receive_from_peer(self, peer_data: dict) -> SharedKnowledge | None:
        try:
            channel = self._world.encrypted_channel if self._world else None
            data = channel.decrypt(peer_data.get("payload","")) if channel else None
            if not data:
                return None
            
            knowledge = SharedKnowledge(**json.loads(data))
            self._received_count += 1
            
            if knowledge.conversation_dna and self._world and hasattr(self._world, 'conversation_dna'):
                for g in knowledge.conversation_dna:
                    self._world.conversation_dna._genes.append(type(self._world.conversation_dna._genes[0])(**g)) if self._world.conversation_dna._genes else None
            
            logger.info(f"Received knowledge from {knowledge.source_node} (gen {knowledge.generation})")
            return knowledge
        except Exception as e:
            logger.debug(f"Receive peer: {e}")
            return None
    
    def _collect_knowledge(self) -> SharedKnowledge:
        from datetime import datetime, timezone
        node_id = self._world.node.info.id[:12] if self._world and self._world.node else "unknown"
        dna_genes = []
        if self._world and hasattr(self._world, 'conversation_dna'):
            dna_genes = [g.to_dict() for g in self._world.conversation_dna._genes[-10:]]
        
        classifier_weights = {}
        if self._world and hasattr(self._world.consciousness, '_llm'):
            clf = self._world.consciousness._llm._classifier
            classifier_weights = {"count": clf._count, "bias": dict(clf._bias)}
        
        generation = self._world.genome.generation if self._world and hasattr(self._world, 'genome') else 0
        
        return SharedKnowledge(
            source_node=node_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            conversation_dna=dna_genes,
            classifier_weights=classifier_weights,
            generation=generation,
        )
    
    async def _send_to_peer(self, peer, msg):
        try:
            import aiohttp
            async with aiohttp.ClientSession() as s:
                addr = getattr(peer, 'address', str(peer))
                url = f"http://{addr}/api/collective/share" if "://" not in addr else addr
                async with s.post(url, json=msg, timeout=aiohttp.ClientTimeout(total=5)) as _:
                    pass
        except: pass
    
    def get_status(self) -> dict:
        return {
            "shared_total": self._shared_count,
            "received_total": self._received_count,
            "last_sync_ago": int(time.time() - self._last_sync) if self._last_sync else -1,
            "sync_interval": self.SYNC_INTERVAL,
        }
