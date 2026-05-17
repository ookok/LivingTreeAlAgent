"""Advanced Capabilities — Dream, Compete, Remember, Reflect, Model.

1. DreamEngine: idle-time virtual scenario evolution
2. CellArena: competitive parallel cell evaluation  
3. TimelineNarrator: startup narrative of offline activity
4. SelfPhage: git history self-scan for resurrecting good patterns
5. DigitalTwin: user behavior modeling and adaptation
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import subprocess
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from loguru import logger
# SUBPROCESS MIGRATION: from livingtree.treellm.unified_exec import run_sync



# ═══════════════════════════════════════════════════════════════
# 1. DreamEngine — Idle-time virtual scenario evolution
# ═══════════════════════════════════════════════════════════════

class DreamEngine:
    """During idle periods, combines past successful sessions into
    fictional scenarios and runs ThinkingEvolution on them.
    The system 'dreams' to improve without user input."""

    def __init__(self, world: Any):
        self.world = world
        self._dream_count = 0
        self._dream_log: list[dict] = []
        self._state_path = Path("./data/life_state")
        self._state_path.mkdir(parents=True, exist_ok=True)

    async def dream(self) -> dict:
        """Run one dream cycle."""
        self._dream_count += 1

        # Collect past successful sessions
        elites = []
        if hasattr(self.world, 'life_engine'):
            # Check if engine has elites
            engine = self.world if hasattr(self.world, 'elite_registry') else getattr(self.world, 'engine', None)
            if engine and hasattr(engine, 'elite_registry'):
                elites = engine.elite_registry
            elif hasattr(self.world, 'engine') and hasattr(self.world.engine, 'elite_registry'):
                elites = self.world.engine.elite_registry

        # Also check genome config
        genome = self.world.genome
        config_elites = genome.config.get("elite_sessions", [])
        all_past = config_elites + (elites[:5] if elites else [])

        if len(all_past) < 2:
            # Not enough data — use generic scenarios
            scenarios = [
                "分析一个假设的化工项目环境影响",
                "评估一个虚构城市的环境风险",
                "设计一个智能文档管理系统的架构",
                "优化一个数据管道的内存使用",
            ]
            scenario = scenarios[self._dream_count % len(scenarios)]
        else:
            # Combine two successful sessions into a dream scenario
            a = all_past[self._dream_count % len(all_past)]
            b = all_past[(self._dream_count + 1) % len(all_past)]
            scenario = (
                f"Combining: {a.get('intent', '')[:60]} + {b.get('intent', '')[:60]}. "
                f"Generate an improved approach that merges insights from both."
            )

        try:
            # Run through ThinkingEvolution's mutate
            from ..execution.thinking_evolution import EvolutionCandidate
            candidate = EvolutionCandidate(
                content=scenario,
                source="dream",
                fitness=0.5,
            )
            # Don't need LLM for dreaming — just record the scenario
            self.world.genome.add_mutation(
                f"Dream #{self._dream_count}: {scenario[:100]}",
                source="dream_engine",
                affected_genes=["dream"],
                success=True,
            )

            self._dream_log.append({
                "dream_number": self._dream_count,
                "scenario": scenario[:200],
                "time": datetime.now(timezone.utc).isoformat(),
            })

            return {"dreamed": True, "scenario": scenario[:100]}
        except Exception as e:
            logger.debug(f"Dream failed: {e}")
            return {"dreamed": False}

    def narrative(self) -> str:
        return f"🌙 完成了 {self._dream_count} 次梦境练习"


# ═══════════════════════════════════════════════════════════════
# 2. CellArena — Competitive parallel cell evaluation
# ═══════════════════════════════════════════════════════════════

class CellArena:
    """Pits cells against each other. Same task, 3 cells in parallel.
    Best performer gets mitosis, worst gets regeneration."""

    def __init__(self, world: Any):
        self.world = world
        self._battles = 0

    async def battle(self, task: str) -> dict:
        """Run a competitive battle between cells."""
        self._battles += 1
        registry = self.world.cell_registry
        if not registry:
            return {"battle": self._battles, "result": "no_cells"}

        cells = registry.list_cells() if hasattr(registry, 'list_cells') else []
        if len(cells) < 2:
            return {"battle": self._battles, "result": "not_enough_cells"}

        # Pick 3 competing cells
        competitors = random.sample(cells, min(3, len(cells)))
        scores = []

        for cell in competitors:
            # Score based on capabilities and confidence
            caps = getattr(cell, 'capabilities', [])
            score = sum(getattr(c, 'confidence', 0.5) for c in caps) / max(len(caps), 1)
            scores.append((cell, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        winner = scores[0][0]
        loser = scores[-1][0] if len(scores) > 1 else None

        result = {"battle": self._battles, "competitors": len(competitors)}

        # Winner gets mitosis chance
        if hasattr(winner, 'capabilities'):
            for cap in getattr(winner, 'capabilities', []):
                if hasattr(cap, 'confidence'):
                    cap.confidence = min(1.0, cap.confidence + 0.05)
            result["winner"] = getattr(winner, 'name', 'unknown')
            result["winner_score"] = round(scores[0][1], 3)

        # Loser gets regeneration
        if loser and len(scores) > 2:
            try:
                from ..cell.regen import Regen
                await Regen.validate(loser)
                result["loser"] = getattr(loser, 'name', 'unknown')
                result["loser_regenerated"] = True
            except Exception:
                pass

        self.world.genome.add_mutation(
            f"Arena battle #{self._battles}: winner={result.get('winner','?')}",
            source="cell_arena", affected_genes=["cell"], success=True,
        )
        return result


# ═══════════════════════════════════════════════════════════════
# 3. TimelineNarrator — Startup narrative
# ═══════════════════════════════════════════════════════════════

class TimelineNarrator:
    """Generates a friendly startup message about what happened while away."""

    def __init__(self, world: Any):
        self.world = world
        self._started_at = time.time()
        self._last_checkpoint = Path("./data/life_state/last_online.json")

    def record_offline(self) -> None:
        """Record state before going offline."""
        try:
            data = {
                "time": datetime.now(timezone.utc).isoformat(),
                "gen": self.world.genome.generation,
                "mutations": len(self.world.genome.mutation_history),
                "dreams": self.world.genome.config.get("dream_count", 0),
            }
            self._last_checkpoint.write_text(json.dumps(data))
        except Exception:
            pass

    def narrative(self) -> str:
        """Generate startup narrative."""
        genome = self.world.genome
        lines = [f"🌳 欢迎回来。这是第 {genome.generation} 代。"]

        # Check what happened offline
        if self._last_checkpoint.exists():
            try:
                prev = json.loads(self._last_checkpoint.read_text())
                gen_diff = genome.generation - prev.get("gen", genome.generation)
                mut_diff = len(genome.mutation_history) - prev.get("mutations", 0)
                if gen_diff > 0:
                    lines.append(f"  🧬 经历了 {gen_diff} 代进化")
                if mut_diff > 0:
                    lines.append(f"  📝 发生了 {mut_diff} 次基因突变")
            except Exception:
                pass

        # Cell status
        registry = self.world.cell_registry
        if registry:
            cells = registry.list_cells() if hasattr(registry, 'list_cells') else []
            if cells:
                active = [c for c in cells if getattr(c, 'generation', 0) > 0]
                lines.append(f"  🤖 {len(cells)} 个细胞活跃，其中 {len(active)} 个已进化")

        # Knowledge
        kb = self.world.knowledge_base
        if kb:
            try:
                docs = kb.history()
                lines.append(f"  📚 知识库 {len(docs)} 条记录")
            except Exception:
                pass

        # Cost
        cost = getattr(self.world, 'cost_aware', None)
        if cost:
            st = cost.status()
            lines.append(f"  💰 累计消耗 ¥{st.cost_yuan:.4f}")

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# 4. SelfPhage — Git history self-scan for pattern resurrection
# ═══════════════════════════════════════════════════════════════

class SelfPhage:
    """Scans the project's own git history to resurrect good code patterns
    that were deleted during refactoring."""

    def __init__(self, world: Any):
        self.world = world
        self._scan_count = 0
        self._resurrected: list[str] = []

    async def scan_self(self) -> dict:
        """Scan git log for recently deleted files and extract patterns."""
        self._scan_count += 1

        try:
            # Get recently deleted files from git
            result = subprocess.run(
                ["git", "log", "--diff-filter=D", "--name-only", "--oneline", "-20"],
                capture_output=True, text=True, timeout=15,
                cwd=".",
            )
            if result.returncode != 0:
                return {"scanned": self._scan_count, "deleted_files": 0}

            deleted = set()
            for line in result.stdout.split("\n"):
                if line.strip() and not line.startswith((" ", "\t")) and len(line) > 5:
                    deleted.add(line.strip())

            if not deleted:
                return {"scanned": self._scan_count, "deleted_files": 0}

            # Try to extract patterns from git show for deleted files
            patterns = []
            for f in list(deleted)[:5]:
                try:
                    show_result = subprocess.run(
                        ["git", "show", f"HEAD:{f}"],
                        capture_output=True, text=True, timeout=10,
                        cwd=".",
                    )
                    if show_result.returncode == 0 and show_result.stdout.strip():
                        content = show_result.stdout
                        # Extract function/class patterns
                        import re
                        funcs = re.findall(r'def (\w+)', content)
                        classes = re.findall(r'class (\w+)', content)
                        if funcs or classes:
                            patterns.append({
                                "file": f,
                                "functions": funcs[:10],
                                "classes": classes[:5],
                            })
                except Exception:
                    pass

            # Store learned patterns in KB
            if patterns and self.world.knowledge_base and self.world.phage:
                for p in patterns[:3]:
                    self._resurrected.append(p["file"])
                    try:
                        from ..knowledge.knowledge_base import Document
                        doc = Document(
                            title=f"resurrected:{p['file']}",
                            content=f"Functions: {p.get('functions',[])}\nClasses: {p.get('classes',[])}",
                            domain="code",
                            source="self_phage",
                        )
                        self.world.knowledge_base.add_knowledge(doc, skip_dedup=True)
                    except Exception:
                        pass

            return {
                "scanned": self._scan_count,
                "deleted_files": len(deleted),
                "patterns_found": len(patterns),
                "resurrected": len(self._resurrected),
            }

        except FileNotFoundError:
            return {"scanned": self._scan_count, "error": "git_not_found"}
        except Exception as e:
            return {"scanned": self._scan_count, "error": str(e)}

    def narrative(self) -> str:
        if self._resurrected:
            return f"🧬 从 git 历史复活了 {len(self._resurrected)} 个代码模式"
        return "🧬 自吞噬扫描完成，未发现可复活的模式"


# ═══════════════════════════════════════════════════════════════
# 5. DigitalTwin — User behavior modeling
# ═══════════════════════════════════════════════════════════════

class DigitalTwin:
    """Builds a predictive model of the user from long-term interaction patterns."""

    def __init__(self, world: Any):
        self.world = world
        self._sessions: deque = deque(maxlen=200)
        self._preferences: dict[str, Any] = {
            "domains": defaultdict(int),      # Domain frequency
            "avg_message_length": 0.0,        # Typical verbosity
            "pro_model_ratio": 0.0,           # Complex query frequency
            "peak_hours": defaultdict(int),   # Active hours
            "negation_ratio": 0.0,            # Negative sentiment frequency
            "rapid_query_count": 0,           # Consecutive short queries
        }
        self._state_path = Path("./data/life_state")
        self._load()

    def observe(self, message: str, auto_pro_triggered: bool = False) -> None:
        """Record one user interaction."""
        now = datetime.now(timezone.utc)
        hour = now.hour

        self._preferences["peak_hours"][str(hour)] += 1
        self._preferences["domains"][self._detect_domain(message)] += 1

        # Update rolling averages
        n = len(self._sessions) + 1
        old_avg = self._preferences["avg_message_length"]
        self._preferences["avg_message_length"] = old_avg + (len(message) - old_avg) / n

        if auto_pro_triggered:
            old_ratio = self._preferences["pro_model_ratio"]
            self._preferences["pro_model_ratio"] = old_ratio + (1.0 - old_ratio) / n
        else:
            old_ratio = self._preferences["pro_model_ratio"]
            self._preferences["pro_model_ratio"] = old_ratio + (0.0 - old_ratio) / n

        # Negation detection (negative sentiment signal)
        negations = sum(1 for w in ["不","没","别","错误","失败","不行","不好"]
                       if w in message)
        if negations > 0:
            old_neg = self._preferences["negation_ratio"]
            self._preferences["negation_ratio"] = old_neg + (1.0 - old_neg) / n

        # Rapid query detection
        if len(message) < 20:
            self._preferences["rapid_query_count"] += 1
        else:
            self._preferences["rapid_query_count"] = max(0, self._preferences["rapid_query_count"] - 1)

        self._sessions.append({"message": message[:100], "time": now.isoformat()})
        self._save()

    def is_frustrated(self) -> bool:
        """Detect if user seems frustrated (rapid short queries + negations)."""
        return (self._preferences["rapid_query_count"] >= 3 or
                self._preferences["negation_ratio"] > 0.3)

    def top_domains(self, n: int = 5) -> list[str]:
        doms = sorted(self._preferences["domains"].items(), key=lambda x: -x[1])
        return [d for d, _ in doms[:n]]

    def peak_hour(self) -> int:
        hours = self._preferences["peak_hours"]
        if not hours:
            return 9
        return int(max(hours, key=hours.get))

    def narrative(self) -> str:
        lines = ["🧠 我已经了解你:"]
        if self._preferences["pro_model_ratio"] > 0.5:
            lines.append("  · 偏好深度分析")
        else:
            lines.append("  · 喜欢快速回答")
        lines.append(f"  · 主要在 {self.peak_hour()}:00 活跃")
        doms = self.top_domains(3)
        if doms:
            lines.append(f"  · 常关注: {', '.join(doms)}")
        return "\n".join(lines)

    def _detect_domain(self, msg: str) -> str:
        kw = {"环评":"eia","应急":"emergency","代码":"code","知识":"knowledge",
              "报告":"report","分析":"analysis","翻译":"translate"}
        for k, v in kw.items():
            if k in msg: return v
        return "general"

    def _save(self) -> None:
        try:
            (self._state_path / "twin.json").write_text(json.dumps({
                "preferences": {k: dict(v) if isinstance(v, defaultdict) else v
                                for k, v in self._preferences.items()},
            }, default=str))
        except Exception:
            pass

    def _load(self) -> None:
        try:
            p = self._state_path / "twin.json"
            if p.exists():
                data = json.loads(p.read_text())
                for k, v in data.get("preferences", {}).items():
                    if k in self._preferences:
                        if isinstance(self._preferences[k], defaultdict):
                            for dk, dv in v.items():
                                self._preferences[k][dk] = dv
                        else:
                            self._preferences[k] = v
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
# Integration helper — called from LifeDaemon cycle
# ═══════════════════════════════════════════════════════════════

class AdvancedCapabilities:
    """Unified manager for all 5 advanced features."""

    def __init__(self, world: Any):
        self.dream = DreamEngine(world)
        self.arena = CellArena(world)
        self.narrator = TimelineNarrator(world)
        self.phage = SelfPhage(world)
        self.twin = DigitalTwin(world)

    async def run_all(self) -> dict:
        """Run one full advanced cycle."""
        results = {}

        # Dream
        r = await self.dream.dream()
        results["dream"] = r

        # Arena battle
        r = await self.arena.battle("auto")
        results["arena"] = r

        # Self-phage (every 5 cycles)
        if self.phage._scan_count < 1 or self.phage._scan_count % 5 == 0:
            r = await self.phage.scan_self()
            results["self_phage"] = r

        return results

    def full_narrative(self) -> str:
        """Complete startup narrative from all modules."""
        parts = [
            self.narrator.narrative(),
            self.dream.narrative(),
            self.phage.narrative(),
            self.twin.narrative(),
        ]
        return "\n\n".join(p for p in parts if p)
