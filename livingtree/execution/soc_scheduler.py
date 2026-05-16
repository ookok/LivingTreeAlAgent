"""SOC Scheduler — Self-Organized Criticality task distribution.

Inspired by: Mi et al. (2026) "Self-organized Criticality in Aquatic Robot Swarm"
   Science Advances, 10.1126/sciadv.adq8222

Core principle:
  Each agent is a "sandpile". Tasks are grains of sand dropping onto the pile.
  When load exceeds threshold, an avalanche cascades tasks to neighbors.
  The system self-organizes to a critical state where event sizes follow
  power-law distributions — small redistributions are frequent, large
  avalanches are rare. No central scheduler needed.

Architecture:
  Agent (sandpile) → local load tracking → avalanche cascade → neighbors
  Power-law tracking → adaptive threshold → emergent load balancing

Usage:
  scheduler = SOCScheduler()
  scheduler.add_agent("cortex", capacity=10, threshold=0.7)
  scheduler.add_agent("liver", capacity=8, threshold=0.65)
  await scheduler.submit({"task_id": "123", "priority": 5, "payload": {...}})
  stats = scheduler.stats()
"""

from __future__ import annotations

import asyncio
import math
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class SOCSandpile:
    """An agent sandpile — tracks local load and manages avalanches."""

    id: str
    load: float = 0.0
    capacity: float = 10.0
    threshold: float = 0.7
    neighbors: list[str] = field(default_factory=list)
    tasks: list[dict] = field(default_factory=list)
    
    # SOC tracking
    avalanche_count: int = 0
    avalanche_sizes: list[int] = field(default_factory=list)  # last 100 avalanche sizes
    total_processed: int = 0
    total_forwarded: int = 0

    def load_ratio(self) -> float:
        return self.load / self.capacity if self.capacity > 0 else 1.0

    def is_critical(self) -> bool:
        return self.load_ratio() >= self.threshold

    def add_task(self, task: dict) -> bool:
        """Add a task to this sandpile. Returns True if avalanche needed."""
        self.tasks.append(task)
        self.load += 1.0
        self.total_processed += 1
        return self.is_critical()

    def avalanche(self, max_cascade: float = 0.5) -> tuple[list[dict], float]:
        """Trigger avalanche: overflow tasks cascade to neighbors.
        
        Returns: (overflow_tasks, severity) where severity is 0-1.
        """
        excess = self.load - (self.capacity * self.threshold)
        if excess <= 0:
            return [], 0.0
        
        avalanche_size = min(int(excess), len(self.tasks))
        
        # Power-law: severity = min(1, log(size+1) / log(capacity+1))
        severity = math.log(avalanche_size + 1) / math.log(self.capacity + 1) if self.capacity > 0 else 0.0
        
        overflow = self.tasks[-avalanche_size:]
        self.tasks = self.tasks[:-avalanche_size]
        self.load -= avalanche_size
        self.total_forwarded += avalanche_size
        
        self.avalanche_count += 1
        self.avalanche_sizes.append(avalanche_size)
        if len(self.avalanche_sizes) > 100:
            self.avalanche_sizes.pop(0)
        
        return overflow, severity

    def adapt_threshold(self, target_exponent: float = 1.8, step: float = 0.02):
        """Adjust threshold to push avalanche distribution toward target power-law exponent.
        
        If avalanches are too uniform (low exponent) → lower threshold (more cascading).
        If avalanches are too clustered (high exponent) → raise threshold (less cascading).
        """
        if len(self.avalanche_sizes) < 10:
            return
        
        sizes = self.avalanche_sizes[-50:]
        current_exponent = self._estimate_power_law(sizes)
        error = target_exponent - current_exponent
        self.threshold = max(0.3, min(0.95, self.threshold + error * step))

    @staticmethod
    def _estimate_power_law(sizes: list[int]) -> float:
        """Estimate power-law exponent via log-log regression (MLE approximation).
        
        P(s) ~ s^(-τ) → ln(P) ~ -τ * ln(s)
        τ ≈ 1 + n / Σ ln(s_i / s_min)
        """
        if len(sizes) < 5:
            return 2.0
        valid = [s for s in sizes if s > 0]
        if not valid:
            return 2.0
        s_min = min(valid)
        sum_log = sum(math.log(s / s_min) for s in valid if s >= s_min)
        if sum_log == 0:
            return 2.0
        return 1.0 + len(valid) / sum_log

    def stats(self) -> dict:
        return {
            "id": self.id,
            "load": self.load,
            "capacity": self.capacity,
            "load_ratio": round(self.load_ratio(), 3),
            "threshold": round(self.threshold, 3),
            "is_critical": self.is_critical(),
            "avalanche_count": self.avalanche_count,
            "total_processed": self.total_processed,
            "total_forwarded": self.total_forwarded,
            "power_law_exponent": round(self._estimate_power_law(self.avalanche_sizes), 3) if self.avalanche_sizes else 0,
            "neighbors": len(self.neighbors),
        }


class SOCScheduler:
    """Self-organized criticality task scheduler.

    Manages multiple sandpiles (agents). Tasks are distributed via random
    placement + local avalanche cascade. No central queue — the system
    self-organizes.
    """

    def __init__(self, name: str = "soc"):
        self.name = name
        self._piles: dict[str, SOCSandpile] = {}
        self._lock = asyncio.Lock()
        self._task_id_counter = 0
        self._start_time = time.time()
        self._total_submitted = 0
        self._total_avalanches = 0

    def add_agent(self, agent_id: str, capacity: float = 10.0,
                  threshold: float = 0.7,
                  neighbors: list[str] | None = None):
        """Register a new agent sandpile."""
        pile = SOCSandpile(
            id=agent_id, capacity=capacity, threshold=threshold,
            neighbors=neighbors or [],
        )
        self._piles[agent_id] = pile
        logger.debug(f"SOC: agent '{agent_id}' added (capacity={capacity}, threshold={threshold})")

    def remove_agent(self, agent_id: str):
        """Remove an agent. Its tasks are redistributed to others."""
        if agent_id not in self._piles:
            return
        pile = self._piles.pop(agent_id)
        if pile.tasks and self._piles:
            least = min(self._piles.values(), key=lambda p: p.load_ratio())
            least.tasks.extend(pile.tasks)
            least.load += len(pile.tasks)

    async def submit(self, task: dict) -> str:
        """Submit a task. Auto-assigns task_id if missing.
        
        Task is placed on the least-loaded sandpile. If that triggers an
        avalanche, tasks cascade to neighbors.
        """
        self._task_id_counter += 1
        if "task_id" not in task:
            task["task_id"] = f"soc_{self._task_id_counter}"
        task["submitted_at"] = time.time()

        async with self._lock:
            self._total_submitted += 1

            if not self._piles:
                return task.get("task_id", "")

            # Place on least-loaded sandpile
            target = min(self._piles.values(), key=lambda p: p.load_ratio())
            avalanche_needed = target.add_task(task)

            if avalanche_needed:
                await self._cascade(target)

        return task.get("task_id", "")

    async def submit_batch(self, tasks: list[dict]) -> list[str]:
        """Submit multiple tasks and cascade as needed."""
        ids = []
        for task in tasks:
            tid = await self.submit(task)
            ids.append(tid)
        return ids

    async def _cascade(self, source: SOCSandpile):
        """Cascade overflow from source sandpile to its neighbors."""
        overflow, severity = source.avalanche()
        if not overflow or not source.neighbors:
            return

        self._total_avalanches += 1

        # Sort neighbors by their current load (least loaded first)
        neighbor_piles = [
            self._piles[nid] for nid in source.neighbors
            if nid in self._piles and nid != source.id
        ]
        if not neighbor_piles:
            return

        neighbor_piles.sort(key=lambda p: p.load_ratio())

        # Distribute overflow evenly across neighbors
        per_neighbor = max(1, len(overflow) // len(neighbor_piles))
        idx = 0
        for neighbor in neighbor_piles:
            chunk = overflow[idx:idx + per_neighbor]
            idx += per_neighbor
            if not chunk:
                break
            neighbor.tasks.extend(chunk)
            neighbor.load += len(chunk)
            neighbor.total_processed += len(chunk)

            # Cascading avalanches: if a neighbor also becomes critical, cascade further
            if neighbor.is_critical():
                await self._cascade(neighbor)

            if idx >= len(overflow):
                break

        # Any remaining overflow goes to the least loaded agent
        if idx < len(overflow):
            leftover = overflow[idx:]
            least = min(self._piles.values(), key=lambda p: p.load_ratio())
            least.tasks.extend(leftover)
            least.load += len(leftover)
            least.total_processed += len(leftover)

        logger.debug(f"SOC avalanche: [{source.id}] severity={severity:.2f} "
                     f"size={len(overflow)} distributed to {len(neighbor_piles)} neighbors")

    async def adapt_all(self, target_exponent: float = 1.8):
        """Run adaptive threshold adjustment on all sandpiles."""
        for pile in self._piles.values():
            pile.adapt_threshold(target_exponent)

    async def get_task(self, agent_id: str) -> dict | None:
        """Get next task for an agent (pop from its queue)."""
        async with self._lock:
            if agent_id not in self._piles:
                return None
            pile = self._piles[agent_id]
            if not pile.tasks:
                return None
            task = pile.tasks.pop(0)
            pile.load -= 1.0
            return task

    def stats(self) -> dict:
        """Full system statistics including power-law analysis."""
        piles = [p.stats() for p in self._piles.values()]
        loads = [p["load_ratio"] for p in piles]
        all_sizes = []
        for p in self._piles.values():
            all_sizes.extend(p.avalanche_sizes)

        return {
            "name": self.name,
            "uptime_seconds": round(time.time() - self._start_time, 1),
            "total_agents": len(piles),
            "total_submitted": self._total_submitted,
            "total_avalanches": self._total_avalanches,
            "avg_load": round(sum(loads) / len(loads), 3) if loads else 0,
            "critical_agents": sum(1 for p in piles if p["is_critical"]),
            "load_distribution": {
                "min": round(min(loads), 3) if loads else 0,
                "max": round(max(loads), 3) if loads else 0,
                "std": round(self._stddev(loads), 3) if len(loads) > 1 else 0,
            },
            "power_law": {
                "exponent": round(SOCSandpile._estimate_power_law(all_sizes), 3) if all_sizes else 0,
                "sample_size": len(all_sizes),
            },
            "agents": piles[:20],
        }

    def event_severity(self, event_count: int, total_events: int) -> dict:
        """Classify an event by SOC severity (power-law binning).
        
        micro  (< 0.2)  → local fix, no report
        meso   (0.2-0.6) → single-organ self-heal
        macro  (0.6-0.9) → cross-organ coordination
        avalanche (> 0.9) → full-system degradation + LLM deep diagnosis
        """
        ratio = event_count / max(total_events, 1)
        # Power-law transform: richness of rare events
        severity = math.log(ratio + 0.001) / math.log(total_events + 1) if total_events > 1 else 0.0
        severity = max(0.0, min(1.0, abs(severity)))

        if severity < 0.2:
            level = "micro"
            action = "local_fix_no_report"
        elif severity < 0.6:
            level = "meso"
            action = "single_organ_self_heal"
        elif severity < 0.9:
            level = "macro"
            action = "cross_organ_coordination"
        else:
            level = "avalanche"
            action = "full_system_degradation_llm_diagnosis"

        return {"severity": round(severity, 3), "level": level, "action": action,
                "event_count": event_count, "total_events": total_events}

    @staticmethod
    def _stddev(values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        return math.sqrt(sum((v - mean) ** 2 for v in values) / (len(values) - 1))


# ═══ Singleton ═══

_scheduler: Optional[SOCScheduler] = None


def get_soc_scheduler(name: str = "soc") -> SOCScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = SOCScheduler(name)
    return _scheduler
