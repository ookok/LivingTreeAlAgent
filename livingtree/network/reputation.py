"""Reputation — Exponential decay reputation scores for P2P peers."""
from __future__ import annotations
import asyncio, time
from loguru import logger

class Reputation:
    def __init__(self, decay_interval: float = 10.0):
        self._scores: dict[str, float] = {}; self._timestamps: dict[str, float] = {}
        self._banned: set[str] = set(); self.decay_interval = decay_interval
    def rate_peer(self, peer_id: str, score: float) -> None:
        self._scores[peer_id] = max(-10, min(10, self._scores.get(peer_id, 0) + score))
        self._timestamps[peer_id] = time.time()
    def get_score(self, peer_id: str) -> float: return self._scores.get(peer_id, 0.0)
    def is_trusted(self, peer_id: str, threshold: float = 1.0) -> bool:
        return peer_id not in self._banned and self.get_score(peer_id) >= threshold
    def ban_node(self, peer_id: str) -> None: self._banned.add(peer_id); logger.warning(f"Node banned: {peer_id}")
    async def decay_scores(self) -> None:
        while True:
            now = time.time()
            for pid in list(self._scores.keys()):
                age = now - self._timestamps.get(pid, now)
                self._scores[pid] *= 0.95 ** (age / self.decay_interval)
            await asyncio.sleep(self.decay_interval)
