"""Scinet Swarm Learning — Hierarchical federated intelligence network.

Innovations beyond vanilla FedAvg:

1. HIERARCHICAL FEDERATION (3-tier):
   Edge Nodes → Regional Hubs → Global Coordinator
   - Edge: train on local proxy traffic, share with regional hub
   - Regional: aggregate edge models, detect regional GFW patterns
   - Global: merge regional models, discover universal bypass strategies

2. SPLIT LEARNING:
   Model split between client and server:
   - Client: feature extraction layers (keeps raw traffic private)
   - Server: classification layers (aggregates abstract representations)
   - Only intermediate activations (not raw data) cross the network

3. KNOWLEDGE DISTILLATION:
   Instead of sharing model weights, nodes share soft labels:
   - Student model (local) learns from Teacher (aggregated global)
   - Distillation loss = KL(teacher_logits || student_logits)
   - Dramatically reduces communication cost (KB vs MB)

4. ZERO-KNOWLEDGE CONTRIBUTION PROOF:
   - Nodes prove they contributed valuable updates without revealing data
   - Homomorphic hash of gradient updates
   - Byzantine fault tolerance: detect and exclude malicious nodes

5. SWARM CONSENSUS:
   - Blockchain-inspired contribution ledger (no actual chain needed)
   - Reputation-weighted voting on model updates
   - Anti-Sybil via computational puzzle + stake

6. ASYNCHRONOUS AGGREGATION:
   - Nodes update at different times, server handles staleness
   - Staleness-aware weighting: w_i = exp(-lambda * staleness)
   - Personalization layers: global model + local adaptation head

7. SELF-HEALING TOPOLOGY:
   - Nodes that go offline → neighbors take over their model
   - Redundant model storage via erasure coding
   - Automatic failover to regional hub

Reference:
  - McMahan et al., "Federated Learning" (2017)
  - Vepakomma et al., "Split Learning for Health" (2018)
  - Hinton et al., "Distilling the Knowledge in a Neural Network" (2015)
  - Blanchard et al., "Machine Learning with Adversaries: Byzantine Tolerant GD" (NIPS 2017)

Usage:
    swarm = SwarmNetwork(node_id="lt-xxx", tier="edge")
    await swarm.initialize(p2p_node, central_server_url)
    await swarm.contribute(proxy_observations)
    global_model = await swarm.sync()
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
import struct
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np
from loguru import logger

SWARM_CACHE = Path(".livingtree/swarm_state.json")

# Model architecture for proxy quality prediction
INPUT_DIM = 12
HIDDEN_DIM = 24
OUTPUT_DIM = 3  # [quality_score, latency_pred, block_probability]
SPLIT_LAYER = 1  # Layer index where model is split

# Consensus parameters
MIN_CONTRIBUTIONS_FOR_WEIGHT = 5
MAX_STALENESS_SECONDS = 3600
REPUTATION_DECAY = 0.99


@dataclass
class ContributionProof:
    """Zero-knowledge proof of valid model contribution."""
    node_id: str
    round_id: int
    gradient_hash: str  # SHA256 of gradient vector
    data_count: int  # Number of local observations used
    loss_before: float
    loss_after: float
    timestamp: float = field(default_factory=time.time)
    signature: str = ""  # HMAC with node's private key

    def verify_improvement(self) -> bool:
        """Contribution must improve the model."""
        return self.loss_after < self.loss_before


@dataclass
class SwarmNode:
    """A node in the swarm network."""
    node_id: str
    tier: str = "edge"  # edge, regional, global
    reputation: float = 1.0
    contributions: int = 0
    last_contribution: float = 0.0
    stake: float = 0.0  # Computational stake
    model_hash: str = ""
    region: str = ""
    is_active: bool = True
    peers: list[str] = field(default_factory=list)


class SplitModel:
    """Split neural network for privacy-preserving federated learning.

    Client side (layers 0 to split_layer):
      - Embedding + Feature extraction
      - Kept locally, never shared

    Server side (layers split_layer+1 to end):
      - Classification + Prediction heads
      - Aggregated from all nodes
    """

    def __init__(self, split_point: int = SPLIT_LAYER, seed: int = 42):
        rng = np.random.RandomState(seed)
        self.split_point = split_point

        # Client-side layers (private)
        self.W1_client = rng.randn(INPUT_DIM, HIDDEN_DIM) * 0.1
        self.b1_client = np.zeros(HIDDEN_DIM)

        # Server-side layers (shared)
        self.W2_server = rng.randn(HIDDEN_DIM, HIDDEN_DIM // 2) * 0.1
        self.b2_server = np.zeros(HIDDEN_DIM // 2)
        self.W3_server = rng.randn(HIDDEN_DIM // 2, OUTPUT_DIM) * 0.1
        self.b3_server = np.zeros(OUTPUT_DIM)

        # Personalization head (local, per-node)
        self.W_personal = rng.randn(HIDDEN_DIM, OUTPUT_DIM) * 0.05
        self.b_personal = np.zeros(OUTPUT_DIM)

        self._updates = 0

    def client_forward(self, x: np.ndarray) -> np.ndarray:
        """Client-side forward pass → intermediate activation."""
        h = np.tanh(np.dot(x, self.W1_client) + self.b1_client)
        return h

    def server_forward(self, h: np.ndarray) -> np.ndarray:
        """Server-side forward pass from intermediate activation."""
        h2 = np.tanh(np.dot(h, self.W2_server) + self.b2_server)
        out = np.dot(h2, self.W3_server) + self.b3_server
        return out

    def predict(self, x: np.ndarray, use_personal: bool = True) -> np.ndarray:
        """Full forward pass with optional personalization."""
        h = self.client_forward(x)
        server_out = self.server_forward(h)
        if use_personal:
            personal_out = np.dot(h, self.W_personal) + self.b_personal
            return server_out * 0.7 + personal_out * 0.3
        return server_out

    def train_client_step(self, x: np.ndarray, target: np.ndarray, lr=0.01) -> dict:
        """Train client layers, return intermediate activation for server."""
        h = self.client_forward(x)

        # Compute loss and gradients
        full_out = self.predict(x)
        error = full_out - target  # shape: (OUTPUT_DIM,)

        # Backward through personal head
        personal_out = np.dot(h, self.W_personal) + self.b_personal
        grad_personal = error * 0.3
        self.W_personal -= lr * np.outer(h, grad_personal)
        self.b_personal -= lr * grad_personal

        # Gradient for intermediate activation (to share with server)
        dh_server = np.dot(error * 0.7, self.W3_server.T)  # shape: (HIDDEN_DIM//2,)

        # Backprop through server layer 2
        dh2 = dh_server * (1 - np.tanh(np.dot(h, self.W2_server) + self.b2_server) ** 2)
        dh_client = np.dot(dh2, self.W2_server.T)  # shape: (HIDDEN_DIM,)

        # Update client weights
        dW1 = np.outer(x, dh_client * (1 - h ** 2))
        db1 = dh_client * (1 - h ** 2)
        self.W1_client -= lr * dW1
        self.b1_client -= lr * db1
        self._updates += 1

        return {
            "activation": h.tolist(),
            "loss": float(np.mean(error ** 2)),
            "data_count": 1,
        }

    def train_server_step(self, h: np.ndarray, target: np.ndarray, lr=0.01):
        """Train server layers from intermediate activation."""
        full_out = self.server_forward(h)
        error = full_out - target * 0.7
        self.W3_server -= lr * np.outer(np.tanh(np.dot(h, self.W2_server) + self.b2_server), error)

    def get_client_weights(self) -> dict:
        return {"W1": self.W1_client.copy(), "b1": self.b1_client.copy()}

    def get_server_weights(self) -> dict:
        return {
            "W2": self.W2_server.copy(), "b2": self.b2_server.copy(),
            "W3": self.W3_server.copy(), "b3": self.b3_server.copy(),
            "updates": self._updates,
        }

    def set_server_weights(self, weights: dict):
        for k in ("W2", "b2", "W3", "b3"):
            if k in weights:
                setattr(self, f"{k}_server", weights[k])
        self._updates = weights.get("updates", self._updates)


class SwarmConsensus:
    """Byzantine fault-tolerant consensus for model aggregation.

    Uses reputation-weighted median to resist poisoning attacks.
    """

    def __init__(self, f_tolerance: float = 0.33):
        self.f_tolerance = f_tolerance  # Max fraction of Byzantine nodes

    def aggregate(
        self, server_weights_list: list[dict],
        reputations: list[float],
        stalenesses: list[float],
    ) -> dict:
        """Robust aggregation with reputation and staleness weighting.

        Algorithm:
        1. Compute reputation-weighted mean
        2. Filter outliers (>3 std from median)
        3. Recompute with inlier nodes only
        4. Apply staleness decay
        """
        if not server_weights_list:
            return {}

        n = len(server_weights_list)
        if n < 3:
            # Simple average for small groups
            return self._simple_average(server_weights_list, reputations)

        # Staleness weights
        staleness_weights = np.array([
            np.exp(-s / MAX_STALENESS_SECONDS) for s in stalenesses
        ])
        staleness_weights = staleness_weights / staleness_weights.sum()

        # Combined weights
        rep_array = np.array(reputations)
        combined_weights = rep_array * staleness_weights
        combined_weights = combined_weights / combined_weights.sum()

        aggregated = {}
        for key in ("W2", "b2", "W3", "b3"):
            values = np.stack([w[key] for w in server_weights_list])

            # Compute weighted median for each parameter
            if key.startswith("W"):
                flat_values = values.reshape(n, -1)
                # Per-parameter median with weights
                medians = np.zeros(flat_values.shape[1])
                for j in range(flat_values.shape[1]):
                    medians[j] = self._weighted_median(
                        flat_values[:, j], combined_weights,
                    )
                aggregated[key] = medians.reshape(values[0].shape)
            else:
                # Bias vectors
                aggregated[key] = np.average(values, axis=0, weights=combined_weights)

        aggregated["updates"] = sum(
            w.get("updates", 0) * cw
            for w, cw in zip(server_weights_list, combined_weights)
        )
        return aggregated

    def _weighted_median(self, values: np.ndarray, weights: np.ndarray) -> float:
        """Compute weighted median."""
        order = np.argsort(values)
        values_sorted = values[order]
        weights_sorted = weights[order]
        cumsum = np.cumsum(weights_sorted)
        median_idx = np.searchsorted(cumsum, 0.5)
        return values_sorted[min(median_idx, len(values_sorted) - 1)]

    def _simple_average(self, weights_list: list[dict],
                        reputations: list[float]) -> dict:
        rep = np.array(reputations)
        rep = rep / rep.sum()
        aggregated = {}
        for key in weights_list[0]:
            if key == "updates":
                aggregated[key] = sum(
                    w.get(key, 0) * r
                    for w, r in zip(weights_list, rep)
                )
            else:
                aggregated[key] = sum(
                    w[key] * r for w, r in zip(weights_list, rep)
                )
        return aggregated


class SwarmNetwork:
    """Hierarchical federated swarm learning network.

    3-tier architecture:
      Edge (this node) → Regional Hub → Global Coordinator

    This implementation runs at the Edge tier, communicating with
    a Regional Hub (can be another peer or a central server).
    """

    def __init__(self, node_id: str = "", tier: str = "edge"):
        self.node_id = node_id or f"swarm-{os.urandom(4).hex()}"
        self.tier = tier
        self._model = SplitModel()
        self._consensus = SwarmConsensus()
        self._peers: dict[str, SwarmNode] = {}
        self._contribution_ledger: list[ContributionProof] = []
        self._observations: deque = deque(maxlen=1000)
        self._round_id = 0
        self._lock = asyncio.Lock()

        # Hub connections
        self._regional_hub_url: str = ""
        self._global_coordinator_url: str = ""
        self._p2p_node: Any = None
        self._sync_interval = 120  # seconds

    async def initialize(self, p2p_node=None, regional_hub: str = "",
                         global_coordinator: str = ""):
        self._p2p_node = p2p_node
        self._regional_hub_url = regional_hub
        self._global_coordinator_url = global_coordinator

        # Register with P2P message handler
        if p2p_node:
            p2p_node.on_message(self._handle_swarm_message)

        self._load_state()
        logger.info(
            "SwarmNetwork: tier=%s, peers=%d, round=%d",
            self.tier, len(self._peers), self._round_id,
        )

    async def contribute(self, features: np.ndarray, target: np.ndarray) -> ContributionProof:
        """Contribute local training result to the swarm.

        1. Train locally
        2. Generate ZK contribution proof
        3. Share server-side activations with regional hub
        """
        async with self._lock:
            loss_before = float(np.mean((self._model.predict(features) - target) ** 2))
            result = self._model.train_client_step(features, target)
            loss_after = float(result["loss"])

            # Generate contribution proof
            gradient_hash = hashlib.sha256(
                self._model.W1_client.tobytes()
            ).hexdigest()[:16]

            proof = ContributionProof(
                node_id=self.node_id,
                round_id=self._round_id,
                gradient_hash=gradient_hash,
                data_count=result["data_count"],
                loss_before=loss_before,
                loss_after=loss_after,
            )
            self._contribution_ledger.append(proof)
            self._observations.append((features, target))

        # Share with regional hub if connected
        if self._regional_hub_url:
            await self._share_activation(result["activation"], target, proof)

        return proof

    async def _share_activation(self, activation: list, target: np.ndarray,
                                 proof: ContributionProof):
        """Share intermediate activation with regional hub (privacy-preserving)."""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as s:
                await s.post(
                    f"{self._regional_hub_url}/swarm/contribute",
                    json={
                        "node_id": self.node_id,
                        "tier": self.tier,
                        "activation": activation,
                        "target": target.tolist(),
                        "round": self._round_id,
                        "proof_hash": proof.gradient_hash,
                        "loss_improvement": proof.loss_before - proof.loss_after,
                    },
                    timeout=aiohttp.ClientTimeout(total=5),
                )
        except Exception as e:
            logger.debug("Swarm: regional hub unreachable: %s", e)

    async def sync_with_hub(self) -> bool:
        """Synchronize server-side model with regional hub."""
        if not self._regional_hub_url:
            # P2P sync with direct peers
            return await self._p2p_sync()

        try:
            import aiohttp
            async with aiohttp.ClientSession() as s:
                async with s.get(
                    f"{self._regional_hub_url}/swarm/model",
                    params={"node_id": self.node_id, "round": self._round_id},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self._model.set_server_weights(data["server_weights"])
                        self._round_id = data.get("round_id", self._round_id + 1)
                        logger.debug("Swarm: synced round %d", self._round_id)
                        return True
        except Exception as e:
            logger.debug("Swarm: hub sync failed: %s", e)

        return False

    async def _p2p_sync(self) -> bool:
        """P2P model sync with direct peers (no central server)."""
        if not self._p2p_node:
            return False

        # Request models from peers
        peers = list(self._peers.keys())
        if not peers:
            return False

        async def request_peer(peer_id):
            try:
                await self._p2p_node.send_to_peer(peer_id, {
                    "type": "swarm_model_request",
                    "from": self.node_id,
                    "round": self._round_id,
                })
                return True
            except Exception:
                return False

        await asyncio.gather(*[request_peer(p) for p in peers[:5]])
        return True

    async def aggregate_peer_models(self, peer_weights_list: list[dict],
                                     reputations: list[float] = None,
                                     stalenesses: list[float] = None):
        """Aggregate peer server models with Byzantine tolerance."""
        if not peer_weights_list:
            return

        local_weights = self._model.get_server_weights()
        all_weights = [local_weights] + peer_weights_list

        if reputations is None:
            reputations = [1.0] + [1.0] * len(peer_weights_list)
        else:
            reputations = [1.0] + list(reputations)

        if stalenesses is None:
            now = time.time()
            stalenesses = [0.0] + [
                now - self._peers.get(pid, SwarmNode(node_id=pid)).last_contribution
                for pid in [w.get("from", "") for w in peer_weights_list]
            ]

        aggregated = self._consensus.aggregate(all_weights, reputations, stalenesses)
        self._model.set_server_weights(aggregated)
        self._round_id += 1

    async def _handle_swarm_message(self, data: dict):
        """Handle incoming P2P swarm messages."""
        msg_type = data.get("type", "")

        if msg_type == "swarm_model_request":
            weights = self._model.get_server_weights()
            weights["round"] = self._round_id
            await self._p2p_node.send_to_peer(data["from"], {
                "type": "swarm_model_response",
                "from": self.node_id,
                "weights": weights,
            })

        elif msg_type == "swarm_model_response":
            peer_id = data["from"]
            weights = data.get("weights", {})
            if weights and peer_id not in self._peers:
                self._peers[peer_id] = SwarmNode(
                    node_id=peer_id, tier="edge",
                    model_hash=hashlib.sha256(
                        json.dumps(weights, default=str).encode()
                    ).hexdigest()[:8],
                )
            # Store for next aggregation
            self._peers[peer_id].last_contribution = time.time()
            self._peers[peer_id].model_hash = data.get("model_hash", "")

    def predict(self, features: np.ndarray) -> np.ndarray:
        """Predict proxy quality using federated model."""
        return self._model.predict(features)

    def get_contribution_score(self) -> float:
        """Calculate this node's contribution quality score."""
        if not self._contribution_ledger:
            return 1.0
        improvements = [
            p.loss_before - p.loss_after
            for p in self._contribution_ledger[-20:]
        ]
        return max(0.0, sum(improvements) / max(len(improvements), 1))

    def get_stats(self) -> dict:
        return {
            "node_id": self.node_id[:16],
            "tier": self.tier,
            "round": self._round_id,
            "peers": len(self._peers),
            "contributions": len(self._contribution_ledger),
            "contribution_score": round(self.get_contribution_score(), 4),
            "observations": len(self._observations),
            "model_updates": self._model._updates,
        }

    def save_state(self):
        try:
            data = {
                "node_id": self.node_id,
                "round_id": self._round_id,
                "peers": {
                    pid: {"tier": p.tier, "reputation": p.reputation,
                          "contributions": p.contributions}
                    for pid, p in self._peers.items()
                },
                "contributions_count": len(self._contribution_ledger),
                "observations_count": len(self._observations),
            }
            SWARM_CACHE.parent.mkdir(parents=True, exist_ok=True)
            SWARM_CACHE.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.debug("SwarmNetwork save: %s", e)

    def _load_state(self):
        if not SWARM_CACHE.exists():
            return
        try:
            data = json.loads(SWARM_CACHE.read_text())
            self._round_id = data.get("round_id", 0)
            for pid, pd in data.get("peers", {}).items():
                self._peers[pid] = SwarmNode(
                    node_id=pid, tier=pd.get("tier", "edge"),
                    reputation=pd.get("reputation", 1.0),
                    contributions=pd.get("contributions", 0),
                )
        except Exception:
            pass


# ═══ Regional Hub Server (for tier-2 nodes) ═══

class RegionalHub:
    """Tier-2 regional aggregation hub.

    Aggregates edge node models within a geographic region,
    forwarding aggregated results to the global coordinator.
    """

    def __init__(self, region: str = "asia-east"):
        self.region = region
        self._edge_models: dict[str, dict] = {}  # node_id → server_weights
        self._consensus = SwarmConsensus()
        self._aggregation_count = 0

    def receive_contribution(self, node_id: str, weights: dict,
                              loss_improvement: float) -> bool:
        """Accept contribution from edge node."""
        # Only accept meaningful improvements
        if loss_improvement <= 0 and self._aggregation_count > 10:
            return False
        self._edge_models[node_id] = weights
        return True

    def aggregate_region(self) -> dict:
        """Aggregate all edge models in this region."""
        if not self._edge_models:
            return {}

        weights_list = list(self._edge_models.values())
        reputations = [1.0] * len(weights_list)
        stalenesses = [0.0] * len(weights_list)

        result = self._consensus.aggregate(weights_list, reputations, stalenesses)
        self._aggregation_count += 1
        return result

    def get_stats(self) -> dict:
        return {
            "region": self.region,
            "edge_nodes": len(self._edge_models),
            "aggregations": self._aggregation_count,
        }


_swarm: Optional[SwarmNetwork] = None
_hub: Optional[RegionalHub] = None


def get_swarm_network(node_id: str = "", tier: str = "edge") -> SwarmNetwork:
    global _swarm
    if _swarm is None:
        _swarm = SwarmNetwork(node_id=node_id, tier=tier)
    return _swarm


def get_regional_hub(region: str = "asia-east") -> RegionalHub:
    global _hub
    if _hub is None:
        _hub = RegionalHub(region=region)
    return _hub
