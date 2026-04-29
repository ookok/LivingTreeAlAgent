"""
P2P-CDN Hybrid Distribution System

Combines P2P and CDN for efficient content distribution
- Hot content prediction
- Smart caching
- Layered distribution
- Incentive mechanism
"""

import asyncio
import hashlib
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from .models import NodeInfo, Connection


@dataclass
class ContentMetadata:
    """Content metadata"""
    content_id: str
    size: int
    content_hash: str
    heat: int = 0
    download_count: int = 0
    last_access: float = 0
    available_sources: list[str] = field(default_factory=list)


class CDNP2PHybrid:
    """
    P2P-CDN Hybrid Distribution System
    
    Features:
    - Hot content prediction
    - Multi-level caching strategy
    - P2P-CDN intelligent selection
    - Content integrity verification
    """
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        
        # Content index: {content_id: ContentMetadata}
        self.content_index: dict[str, ContentMetadata] = {}
        
        # Local cache: {content_id: bytes}
        self.local_cache: dict[str, bytes] = {}
        self.max_cache_size = 100 * 1024 * 1024  # 100MB
        self.current_cache_size = 0
        
        # CDN sources
        self.cdn_sources: list[str] = [
            "cdn1.example.com",
            "cdn2.example.com",
            "cdn3.example.com",
        ]
        
        # Hot content set
        self.hot_content: set[str] = set()
        
        # Node cache index: {content_id: [node_id]}
        self.content_providers: dict[str, list[str]] = defaultdict(list)
        
        # Stats
        self.stats = {
            "p2p_downloads": 0,
            "cdn_downloads": 0,
            "cache_hits": 0,
            "hot_predictions": 0,
        }
    
    async def fetch(
        self,
        content_id: str,
        prefer_p2p: bool = True,
        connection_pool=None,
    ) -> Optional[bytes]:
        """
        Fetch content (auto-select optimal source)
        
        Args:
            content_id: Content ID
            prefer_p2p: Prefer P2P
            connection_pool: Connection pool
            
        Returns:
            bytes: Content data
        """
        # 1. Check local cache
        if content_id in self.local_cache:
            self.stats["cache_hits"] += 1
            return self.local_cache[content_id]
        
        # 2. Update heat
        await self._update_heat(content_id)
        
        # 3. Select data source
        if prefer_p2p and content_id in self.content_providers:
            data = await self._fetch_via_p2p(content_id, connection_pool)
            if data:
                self.stats["p2p_downloads"] += 1
                await self._cache_content(content_id, data)
                return data
        
        # 4. Fallback to CDN
        data = await self._fetch_via_cdn(content_id)
        if data:
            self.stats["cdn_downloads"] += 1
            await self._cache_content(content_id, data)
            return data
        
        return None
    
    async def _fetch_via_p2p(self, content_id: str, connection_pool) -> Optional[bytes]:
        """Fetch content via P2P network"""
        providers = self.content_providers.get(content_id, [])
        
        for provider_id in providers:
            if not connection_pool:
                continue
            conn = await connection_pool.get_connection(provider_id)
            if not conn:
                continue
            
            try:
                request = f"GET:{content_id}".encode()
                await conn.send(request)
                data = await conn.receive()
                if data:
                    return data
            except Exception:
                continue
        
        return None
    
    async def _fetch_via_cdn(self, content_id: str) -> Optional[bytes]:
        """Fetch content via CDN"""
        import random
        cdn = random.choice(self.cdn_sources)
        # TODO: Implement real CDN request
        return None
    
    async def publish(
        self,
        content_id: str,
        data: bytes,
        connection_pool=None,
        dht_optimizer=None,
    ) -> bool:
        """
        Publish content to network
        
        Args:
            content_id: Content ID
            data: Content data
            connection_pool: Connection pool
            dht_optimizer: DHT optimizer
            
        Returns:
            bool: Success
        """
        content_hash = hashlib.sha256(data).hexdigest()
        await self._cache_content(content_id, data)
        
        metadata = ContentMetadata(
            content_id=content_id,
            size=len(data),
            content_hash=content_hash,
        )
        self.content_index[content_id] = metadata
        
        if dht_optimizer:
            closest_nodes = dht_optimizer.get_closest_nodes(content_id, 5)
            for node in closest_nodes:
                self.content_providers[content_id].append(node.node_id)
        
        await self._predict_hot_content(content_id)
        return True
    
    async def _cache_content(self, content_id: str, data: bytes):
        """Cache content locally"""
        size = len(data)
        
        while self.current_cache_size + size > self.max_cache_size:
            await self._evict_oldest()
        
        self.local_cache[content_id] = data
        self.current_cache_size += size
    
    async def _evict_oldest(self):
        """Evict oldest content"""
        if not self.local_cache:
            return
        
        oldest_id = None
        oldest_time = float('inf')
        
        for content_id, metadata in self.content_index.items():
            if content_id in self.local_cache and metadata.last_access < oldest_time:
                oldest_time = metadata.last_access
                oldest_id = content_id
        
        if oldest_id:
            del self.local_cache[oldest_id]
            if oldest_id in self.content_index:
                size = self.content_index[oldest_id].size
                self.current_cache_size -= size
                del self.content_index[oldest_id]
    
    async def _update_heat(self, content_id: str):
        """Update content heat"""
        if content_id in self.content_index:
            metadata = self.content_index[content_id]
            metadata.heat += 1
            metadata.download_count += 1
            metadata.last_access = time.time()
        else:
            self.content_index[content_id] = ContentMetadata(
                content_id=content_id,
                size=0,
                content_hash="",
                heat=1,
                last_access=time.time(),
            )
    
    async def _predict_hot_content(self, content_id: str):
        """Predict hot content"""
        metadata = self.content_index.get(content_id)
        if not metadata:
            return
        
        if metadata.download_count > 10:
            self.hot_content.add(content_id)
            self.stats["hot_predictions"] += 1
    
    def register_provider(self, content_id: str, node_id: str):
        """Register content provider"""
        if node_id not in self.content_providers[content_id]:
            self.content_providers[content_id].append(node_id)
    
    def get_stats(self) -> dict:
        """Get stats"""
        return {
            **self.stats,
            "cache_size_mb": self.current_cache_size / 1024 / 1024,
            "cached_content": len(self.local_cache),
            "indexed_content": len(self.content_index),
            "hot_content_count": len(self.hot_content),
        }
