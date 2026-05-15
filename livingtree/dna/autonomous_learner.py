"""AutonomousLearner — self-evolving engine that learns from the internet.

The true "digital life form": autonomously discovers, reads, and synthesizes
knowledge from the web without waiting for user prompts.

Three periodic cycles:
  1. Discovery: search trending topics in configured domains
  2. Learning: fetch + extract + summarize discovered content
  3. Integration: propose new skills, update knowledge base, self-upgrade code

Inspired by: the gap between "配置驱动" (config-driven) and "自主进化" (self-evolving).
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

LEARN_DIR = Path(".livingtree/learned")
LEARN_FILE = LEARN_DIR / "autonomous_learning.json"


@dataclass
class LearnedItem:
    id: str
    source: str  # url
    title: str
    summary: str
    domain: str = ""
    extracted_skill: str = ""
    integrated: bool = False
    created_at: float = field(default_factory=time.time)


class AutonomousLearner:
    """Background engine that continuously learns from the internet."""

    DOMAINS = [
        "环境评估 EIA 最新标准 2026",
        "环境影响评价 技术导则 更新",
        "大气污染扩散模型 研究进展",
        "Python 大语言模型 最佳实践",
        "AI agent 架构 自我进化",
        "structured generation LLM 最新论文",
        "Textual TUI framework 更新",
        "prompt engineering 最佳实践 2026",
    ]

    CYCLE_INTERVAL = 3600
    MINE_INTERVAL = 86400  # Auto-mine project files once per day

    def __init__(self):
        self._items: dict[str, LearnedItem] = {}
        self._running = False
        self._task: asyncio.Task | None = None
        self._hub = None
        self._load()

    def set_hub(self, hub):
        self._hub = hub

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(f"🧠 AutonomousLearner started (interval={self.CYCLE_INTERVAL}s, {len(self.DOMAINS)} domains)")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()

    async def _loop(self):
        await asyncio.sleep(60)
        self._last_mine = 0.0
        while self._running:
            try:
                await self._learn_cycle()
                # Auto-mine project files once per day
                if time.time() - self._last_mine > self.MINE_INTERVAL:
                    await self._auto_mine()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Learn cycle: {e}")
            await asyncio.sleep(self.CYCLE_INTERVAL)

    async def _auto_mine(self):
        """Autonomously mine the project workspace for templates/patterns."""
        from ..knowledge.learning_engine import get_miner
        from ..observability.system_monitor import get_monitor
        if get_monitor().can_run_task("AutoMiner", heavy=True):
            miner = get_miner()
            stats = await miner.mine_directory(".")
            self._last_mine = time.time()
            logger.info(f"AutoMine: {stats['docs_parsed']} docs, {stats['templates_extracted']} templates")

    async def _learn_cycle(self):
        if not self._hub or not self._hub.world:
            return

        from ..observability.system_monitor import get_monitor
        monitor = get_monitor()
        if not monitor.can_run_task("AutonomousLearner", heavy=False):
            return

        import random
        domain = random.choice(self.DOMAINS)
        logger.info(f"🧠 Learning: {domain}")

        # Step 1: Search for latest content
        try:
            from ..capability.unified_search import get_unified_search
            search = get_unified_search()
            results = await search.query(domain, limit=5)

            if not results:
                return

            # Step 2: Fetch and extract each result
            from ..capability.web_reach import WebReach
            reach = WebReach()

            for r in results[:3]:
                if not r.url or r.url in self._items:
                    continue
                try:
                    page = await reach.fetch(r.url)
                    if page.status_code == 200 and len(page.text) > 200:
                        item = LearnedItem(
                            id=f"learn-{len(self._items)+1}",
                            source=r.url,
                            title=page.title or r.title,
                            summary=page.snippet(500),
                            domain=domain,
                        )
                        self._items[item.id] = item
                        logger.info(f"  📄 {item.title[:60]}")

                        # Step 3: Propose skill from learned content
                        from .unified_skill_system import get_skill_system
                        sys = get_skill_system()
                        skill = sys.propose_skill(item.summary)
                        item.extracted_skill = skill.name
                        self._save()
                except Exception:
                    continue

        except Exception as e:
            logger.debug(f"Learn search: {e}")

    def get_status(self) -> dict:
        return {
            "items_learned": len(self._items),
            "integrated": sum(1 for i in self._items.values() if i.integrated),
            "running": self._running,
            "domains": self.DOMAINS,
        }

    def _save(self):
        try:
            LEARN_DIR.mkdir(parents=True, exist_ok=True)
            data = [{"id": i.id, "source": i.source, "title": i.title,
                     "summary": i.summary, "domain": i.domain,
                     "extracted_skill": i.extracted_skill, "integrated": i.integrated}
                    for i in self._items.values()]
            LEARN_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception:
            pass

    def _load(self):
        try:
            if LEARN_FILE.exists():
                for d in json.loads(LEARN_FILE.read_text()):
                    i = LearnedItem(**d)
                    self._items[i.id] = i
        except Exception:
            pass


# ═══ Global ═══

_learner: AutonomousLearner | None = None


def get_autonomous_learner() -> AutonomousLearner:
    global _learner
    if _learner is None:
        _learner = AutonomousLearner()
    return _learner
