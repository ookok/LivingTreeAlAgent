"""Scinet Engine v2.1 — Unified integration engine for all Scinet subsystems.

Wires together all innovative modules into a single intelligent proxy pipeline:

Full Pipeline:
  Request → VLLMTrafficEngine (camouflage pattern)
         → SemanticCache (hit?)
         → BanditRouter (RL select proxy)
         → TopologyOptimizer (GNN find path)
         → QuicTunnel (QUIC transport + obfuscation)
         → FederatedLearner (update local model)
         → SwarmNetwork (hierarchical federated sync)
         → WebTransport (browser entry)

Features:
  - Progressive initialization (fast start, background heavy init)
  - Fallback chains at every level
  - LLM-driven traffic camouflage for GFW circumvention
  - Hierarchical swarm learning (Edge → Region → Global)
  - Unified stats collection
  - Auto-persistence of all learned states

Usage:
    engine = ScinetEngine(port=7890)
    await engine.start()
    status = engine.get_status()
    await engine.stop()
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from .scinet_quic import QuicTunnel, get_quic_tunnel
from .scinet_bandit import (
    BanditRouter, RequestContext, get_bandit_router,
)
from .scinet_federated import (
    FederatedLearner, get_federated_learner,
)
from .scinet_topology import (
    TopologyOptimizer, get_topology,
)
from .scinet_cache import (
    SemanticCache, get_semantic_cache,
)
from .scinet_webtransport import (
    WebTransportServer, get_webtransport_server,
)
from .scinet_vllm import (
    VLLMTrafficEngine, get_vllm_engine,
)
from .scinet_swarm import (
    SwarmNetwork, get_swarm_network, INPUT_DIM,
)
from .scinet_morph import (
    ProtocolMorphEngine, get_morph_engine,
)
from .scinet_dssa import (
    DSSARouter, get_dssa_router,
)
from .scinet_laser import (
    LaserRouter, get_laser_router,
)


@dataclass
class ScinetEngineStatus:
    """Unified status across all Scinet subsystems."""
    running: bool = False
    port: int = 7890
    uptime_seconds: float = 0.0

    # Subsystem status
    quic_active: bool = False
    bandit_ready: bool = False
    federated_ready: bool = False
    topology_ready: bool = False
    cache_ready: bool = False
    wt_active: bool = False

    # Performance
    total_requests: int = 0
    success_requests: int = 0
    failed_requests: int = 0
    cache_hit_rate: float = 0.0
    bandwidth_bytes: int = 0
    avg_latency_ms: float = 0.0

    # Learning
    bandit_arms: int = 0
    federated_peers: int = 0
    topology_nodes: int = 0


class ScinetEngine:
    """Unified intelligent proxy engine orchestrating all subsystems.

    Pipeline:
      1. SemanticCache — Check cache before making network requests
      2. BanditRouter — RL-based proxy selection
      3. TopologyOptimizer — GNN-inspired path optimization
      4. QuicTunnel — QUIC/HTTP3 transport with obfuscation
      5. FederatedLearner — Update local model, share with P2P peers
      6. WebTransport — Browser-native entry point (optional)
    """

    def __init__(self, port: int = 7890, node_id: str = ""):
        self.port = port
        self.node_id = node_id or f"scinet-{port}"
        self._status = ScinetEngineStatus(port=port)
        self._lock = asyncio.Lock()
        self._running = False
        self._start_time: float = 0.0

        # Subsystems (lazy init)
        self._quic: Optional[QuicTunnel] = None
        self._bandit: Optional[BanditRouter] = None
        self._federated: Optional[FederatedLearner] = None
        self._topology: Optional[TopologyOptimizer] = None
        self._cache: Optional[SemanticCache] = None
        self._wt: Optional[WebTransportServer] = None
        self._vllm: Optional[VLLMTrafficEngine] = None
        self._swarm: Optional[SwarmNetwork] = None
        self._morph: Optional[ProtocolMorphEngine] = None
        self._dssa: Optional[DSSARouter] = None
        self._laser: Optional[LaserRouter] = None

        # P2P bridge
        self._p2p_node: Any = None
        self._p2p_sync_task: Optional[asyncio.Task] = None

    async def start(self, enable_wt: bool = False) -> ScinetEngineStatus:
        """Start all Scinet subsystems with progressive initialization."""
        if self._running:
            return self._status

        self._start_time = time.time()
        self._running = True

        # Phase 1: Instant (0s)
        await self._init_fast()

        # Phase 2: Background (async, non-blocking)
        asyncio.create_task(self._init_background(enable_wt))

        async with self._lock:
            self._status.running = True

        logger.info("ScinetEngine v2.0 started on port %d", self.port)
        return self._status

    async def _init_fast(self) -> None:
        """Phase 1: Instant initialization."""
        # Bandit router (fast, just loads state)
        self._bandit = get_bandit_router()
        async with self._lock:
            self._status.bandit_ready = True

        # Cache (fast, just opens SQLite)
        self._cache = get_semantic_cache()
        await self._cache.initialize()
        async with self._lock:
            self._status.cache_ready = True

        logger.debug("ScinetEngine: fast init complete (bandit + cache)")

    async def _init_background(self, enable_wt: bool) -> None:
        """Phase 2: Background initialization (~30s)."""
        # QUIC tunnel
        try:
            self._quic = get_quic_tunnel()
            await self._quic.initialize()
            async with self._lock:
                self._status.quic_active = self._quic._quic_active
        except Exception as e:
            logger.debug("QUIC init: %s", e)

        # Topology optimizer
        try:
            self._topology = get_topology()
            await self._topology.initialize()
            async with self._lock:
                self._status.topology_ready = True
                self._status.topology_nodes = len(self._topology._nodes)
        except Exception as e:
            logger.debug("Topology init: %s", e)

        # Federated learner
        try:
            self._federated = get_federated_learner(node_id=self.node_id)
            async with self._lock:
                self._status.federated_ready = True
        except Exception as e:
            logger.debug("Federated init: %s", e)

        # VLLM Traffic Camouflage Engine
        try:
            self._vllm = get_vllm_engine()
            await self._vllm.initialize()
            async with self._lock:
                self._status.cache_ready = True  # reuse cache flag for vllm
        except Exception as e:
            logger.debug("VLLM init: %s", e)

        # Swarm hierarchical federated network
        try:
            self._swarm = get_swarm_network(node_id=self.node_id)
            await self._swarm.initialize(p2p_node=self._p2p_node)
            async with self._lock:
                self._status.federated_ready = True
        except Exception as e:
            logger.debug("Swarm init: %s", e)

        # Protocol Morphing Engine (deep traffic obfuscation)
        try:
            self._morph = get_morph_engine()
            await self._morph.initialize()
            # Create initial session pool
            for domain in ["github.com", "google.com"]:
                await self._morph.create_session(domain)
            async with self._lock:
                self._status.cache_ready = True
        except Exception as e:
            logger.debug("Morph init: %s", e)

        # DSSA Sparse Attention Router
        try:
            self._dssa = get_dssa_router()
            async with self._lock:
                self._status.cache_ready = True
        except Exception as e:
            logger.debug("DSSA init: %s", e)

        # LASER Superposition Router
        try:
            self._laser = get_laser_router()
            async with self._lock:
                self._status.cache_ready = True
        except Exception as e:
            logger.debug("LASER init: %s", e)

        # WebTransport (optional)
        if enable_wt:
            try:
                self._wt = get_webtransport_server(port=self.port + 1)
                await self._wt.start()
                async with self._lock:
                    self._status.wt_active = True
            except Exception as e:
                logger.debug("WebTransport init: %s", e)

        logger.info("ScinetEngine: full init complete (%d subsystems)", self._subsystem_count())

    async def stop(self) -> ScinetEngineStatus:
        """Gracefully shutdown all subsystems."""
        if not self._running:
            return self._status

        # Stop periodic tasks
        if self._p2p_sync_task:
            self._p2p_sync_task.cancel()

        # Save all state
        await self.save_state()

        # Close subsystems
        if self._quic:
            await self._quic.close()
        if self._cache:
            await self._cache.close()
        if self._wt:
            await self._wt.stop()

        async with self._lock:
            self._status.uptime_seconds = time.time() - self._start_time
            self._status.running = False

        logger.info("ScinetEngine stopped (uptime=%.0fs)", self._status.uptime_seconds)
        return self._status

    async def proxy_request(
        self, url: str, method: str = "GET", headers: dict = None,
        body: bytes = None, timeout: float = 30.0,
        domain_category: str = "GENERAL",
    ) -> tuple[int, bytes, dict]:
        """Execute a full proxy request through the intelligent pipeline.

        Pipeline stages:
        1. Cache lookup → return cached if hit
        2. Bandit proxy selection → pick best proxy
        3. Topology path optimization → find best routing path
        4. QUIC tunnel transport → execute request
        5. Federated update → learn from result

        Returns: (status_code, content_bytes, response_headers)
        """
        async with self._lock:
            self._status.total_requests += 1

        start_time = time.perf_counter()

        # Stage 0: VLLM Traffic Camouflage (GFW circumvention)
        camouflage = None
        if self._vllm and method == "GET":
            from urllib.parse import urlparse
            domain = urlparse(url).hostname or ""
            camouflage = await self._vllm.process_request(
                domain, path=urlparse(url).path or "/",
                category=domain_category,
            )
            if camouflage:
                strategy = camouflage["strategy"]
                if strategy == "OBFUSCATE":
                    headers = headers or {}
                    headers.update(camouflage["headers"])
                    headers["User-Agent"] = camouflage["headers"].get(
                        "user_agent", headers.get("User-Agent", "")
                    )
                    # Apply timing jitter
                    if camouflage.get("timing_ms"):
                        jitter = camouflage["timing_ms"][0] / 1000.0
                        if jitter > 0:
                            await asyncio.sleep(jitter)

        # Stage 0.5: Protocol Morphing (deep obfuscation — persona + rotation + noise)
        morph_session = None
        if self._morph:
            from urllib.parse import urlparse
            domain = urlparse(url).hostname or ""
            # Get or create a morphed session for this domain
            morph_session = await self._morph.create_session(domain, domain_category)
            if morph_session:
                # Apply persona headers
                headers = headers or {}
                persona_ua = morph_session.persona.get("ua", "")
                if persona_ua:
                    headers["User-Agent"] = persona_ua
                # Inject noise headers (anti-DPI)
                for k, v in morph_session.noise_headers.items():
                    if not k.startswith("__"):
                        headers[k] = v
                # Apply persona accept headers
                if "accept" in morph_session.persona:
                    headers.setdefault("Accept", morph_session.persona["accept"])

        # Stage 1: Cache check
        if self._cache and method == "GET":
            hit, cached_content, cached_headers = await self._cache.get(url, headers)
            if hit and cached_content:
                async with self._lock:
                    self._status.success_requests += 1
                    self._status.cache_hit_rate = self._compute_cache_hit_rate()
                return 200, cached_content, cached_headers or {}

        # Stage 2: Build request context
        context = RequestContext(
            domain_category=domain_category,
            time_hour=time.localtime().tm_hour,
            request_size_bytes=len(body) if body else 0,
            is_https=url.startswith("https"),
        )

        # Stage 3: Select proxy via Bandit
        selected_proxy = None
        if self._bandit:
            # Get candidates from existing proxy pool
            candidates = list(self._bandit._arms.keys())
            if candidates:
                selected_proxy = await self._bandit.select_proxy(context, candidates)

        # Stage 4: Find optimal path via Topology
        if self._topology:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.hostname or ""
            if domain:
                next_hop = self._topology.get_optimal_nexthop("proxy_gateway_asia", domain)
                if next_hop:
                    self._topology.update_edge_performance(
                        "proxy_gateway_asia", domain,
                        latency_ms=0, success=True,
                    )

        # Stage 5: Execute via QUIC tunnel (with fallback)
        try:
            if self._quic:
                status, content, resp_headers = await self._quic.fetch(
                    url, headers=headers, method=method,
                    body=body, timeout=timeout,
                )
            else:
                # Direct aiohttp fallback
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.request(
                        method, url, headers=headers, data=body,
                        timeout=aiohttp.ClientTimeout(total=timeout),
                    ) as resp:
                        content = await resp.read()
                        status = resp.status
                        resp_headers = dict(resp.headers)
        except Exception as e:
            async with self._lock:
                self._status.failed_requests += 1
            raise

        # Stage 6: Cache the response
        latency = (time.perf_counter() - start_time) * 1000
        if self._cache and method == "GET" and status == 200:
            await self._cache.set(url, content, resp_headers)

        # Stage 7: Update Bandit
        if self._bandit and selected_proxy:
            await self._bandit.update(
                selected_proxy, context,
                success=(status < 500), latency_ms=latency,
            )

        # Stage 8: Update Federated learner
        if self._federated:
            from urllib.parse import urlparse
            domain = urlparse(url).hostname or ""
            features = self._compute_features(status, latency)
            await self._federated.update_local(
                domain, features, success=(status < 500), latency_ms=latency,
            )

        # Stage 9: Update Topology
        if self._topology:
            from urllib.parse import urlparse
            domain = urlparse(url).hostname or ""
            if domain:
                self._topology.update_edge_performance(
                    "proxy_gateway_asia", domain,
                    latency_ms=latency, success=(status < 500),
                )

        # Stage 10: VLLM feedback (reinforce successful camouflage patterns)
        if self._vllm and camouflage:
            from urllib.parse import urlparse
            domain = urlparse(url).hostname or ""
            self._vllm.report_result(domain, method, success=(status < 500))

        # Stage 10.5: Morph feedback + genetic evolution
        if self._morph and morph_session:
            await self._morph.report_result(morph_session, success=(status < 500))
            # Evolve every 20 requests
            if self._status.total_requests % 20 == 0:
                await self._morph.evolve()

        # Stage 11: Swarm contribution (share learning with hierarchical network)
        if self._swarm and self._federated:
            try:
                from urllib.parse import urlparse
                domain = urlparse(url).hostname or ""
                features = self._compute_features(status, latency)
                target = np.array([
                    1.0 if status < 500 else 0.0,
                    min(1.0, latency / 5000.0),
                    0.0 if status < 500 else 1.0,
                ])
                await self._swarm.contribute(features, target)
            except Exception:
                pass

        async with self._lock:
            self._status.success_requests += 1
            self._status.bandwidth_bytes += len(content)
            self._status.avg_latency_ms = (
                self._status.avg_latency_ms * (self._status.success_requests - 1) + latency
            ) / max(self._status.success_requests, 1)

        return status, content, resp_headers

    def _compute_features(self, status: int, latency: float) -> "np.ndarray":
        import numpy as np
        features = np.zeros(INPUT_DIM, dtype=np.float32)
        features[0] = 1.0 if 200 <= status < 300 else 0.0
        features[1] = 0.0 if status >= 500 else 1.0
        features[2] = min(1.0, latency / 5000.0)
        features[3] = self._status.cache_hit_rate
        async with self._lock:
            total = max(self._status.total_requests, 1)
            features[4] = self._status.success_requests / total
            features[5] = self._status.failed_requests / total
        features[6] = float(self._status.bandit_arms > 0)
        features[7] = float(self._status.federated_peers > 0)
        features[8] = float(self._status.topology_nodes > 0)
        features[9] = float(self._status.quic_active)
        features[10] = float(self._vllm is not None)
        features[11] = float(self._morph is not None)
        return features

    def attach_p2p(self, p2p_node: Any) -> None:
        """Attach P2P node for federated learning sync."""
        self._p2p_node = p2p_node

        if p2p_node and self._federated:
            async def _p2p_handler(data: dict):
                """Handle incoming P2P messages for federated learning."""
                msg_type = data.get("type", "")
                if msg_type == "scinet_weights":
                    peer_id = data.get("from", "")
                    weights = data.get("weights", {})
                    if weights:
                        await self._federated.receive_peer_weights(peer_id, weights)
                elif msg_type == "scinet_request_weights":
                    if self._federated:
                        weights = await self._federated.share_weights()
                        await p2p_node.send_to_peer(
                            data.get("from", ""),
                            {"type": "scinet_weights", "from": self.node_id, "weights": weights},
                        )

            p2p_node.on_message(_p2p_handler)

            # Start periodic sync
            async def _periodic_sync():
                while self._running:
                    await asyncio.sleep(60)  # Sync every 60s
                    try:
                        # Broadcast weights to peers
                        if self._federated:
                            weights = await self._federated.share_weights()
                            for peer_id in p2p_node._peers:
                                await p2p_node.send_to_peer(
                                    peer_id,
                                    {"type": "scinet_weights", "from": self.node_id, "weights": weights},
                                )
                        # Aggregate received peer weights
                        await self._federated.aggregate_peers()
                    except Exception as e:
                        logger.debug("P2P sync: %s", e)

            self._p2p_sync_task = asyncio.create_task(_periodic_sync())

    def get_status(self) -> ScinetEngineStatus:
        async with self._lock:
            if self._running:
                self._status.uptime_seconds = time.time() - self._start_time
                self._status.bandit_arms = (
                    len(self._bandit._arms) if self._bandit else 0
                )
                self._status.topology_nodes = (
                    len(self._topology._nodes) if self._topology else 0
                )
            return self._status

    def get_detailed_status(self) -> dict:
        """Get comprehensive status from all subsystems."""
        status = {
            "engine": {
                "running": self._running,
                "port": self.port,
                "uptime_seconds": self._status.uptime_seconds,
                "total_requests": self._status.total_requests,
                "success_rate": (
                    self._status.success_requests / max(self._status.total_requests, 1)
                ),
                "bandwidth_bytes": self._status.bandwidth_bytes,
                "avg_latency_ms": round(self._status.avg_latency_ms, 1),
            },
            "quic": self._quic.get_stats() if self._quic else {},
            "bandit": self._bandit.get_stats() if self._bandit else {},
            "federated": self._federated.get_stats() if self._federated else {},
            "topology": self._topology.get_stats() if self._topology else {},
            "cache": self._cache.get_stats() if self._cache else {},
            "webtransport": self._wt.get_stats() if self._wt else {},
            "vllm": self._vllm.get_stats() if self._vllm else {},
            "swarm": self._swarm.get_stats() if self._swarm else {},
            "morph": self._morph.get_stats() if self._morph else {},
        }
        return status

    async def save_state(self) -> None:
        """Persist all learned states to disk."""
        if self._bandit:
            self._bandit.save_state()
        if self._federated:
            self._federated.save_state()
        if self._topology:
            self._topology.save_state()
        logger.debug("ScinetEngine: state saved")

    def _subsystem_count(self) -> int:
        n = 0
        if self._bandit:
            n += 1
        if self._cache:
            n += 1
        if self._quic:
            n += 1
        if self._topology:
            n += 1
        if self._federated:
            n += 1
        if self._wt:
            n += 1
        return n

    def _compute_cache_hit_rate(self) -> float:
        if not self._cache:
            return 0.0
        stats = self._cache.get_stats()
        return stats.get("hit_rate", 0.0)


# ═══ Singleton ═══

import numpy as np

_engine: Optional[ScinetEngine] = None
_engine_lock = threading.Lock()


def get_scinet_engine(port: int = 7890) -> ScinetEngine:
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = ScinetEngine(port=port)
    return _engine
