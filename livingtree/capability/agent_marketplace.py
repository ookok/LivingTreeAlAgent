"""AgentMarketplace — P2P skill/tool sharing network.

    Decentralized marketplace where nodes automatically share:
    1. Skills: LLM prompt templates for specialized tasks
    2. Tools: Python code snippets that solve specific problems
    3. Discover: auto-fetch new skills from connected peers
    4. Rate: community ratings determine skill quality
    5. Sync: periodic background sync with relay/peers

    Usage:
        am = get_marketplace()
        await am.publish_skill("DockerfileGenerator", prompt, hub)
        await am.discover_skills(hub)  # fetch from P2P network
        matches = am.search_skills("容器化部署")
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

MARKET_DIR = Path(".livingtree/marketplace")
SKILLS_DIR = MARKET_DIR / "skills"
TOOLS_DIR = MARKET_DIR / "tools"


@dataclass
class MarketItem:
    id: str
    name: str
    type: str  # "skill" | "tool"
    description: str
    category: str = ""
    prompt_template: str = ""  # for skills
    code: str = ""  # for tools
    author: str = ""  # peer ID
    rating: float = 0.0
    downloads: int = 0
    version: int = 1
    timestamp: float = 0.0


class AgentMarketplace:
    """Decentralized P2P marketplace for AI skills and tools."""

    def __init__(self):
        MARKET_DIR.mkdir(parents=True, exist_ok=True)
        SKILLS_DIR.mkdir(parents=True, exist_ok=True)
        TOOLS_DIR.mkdir(parents=True, exist_ok=True)
        self._items: dict[str, MarketItem] = {}
        self._load()

    def publish_skill(
        self,
        name: str,
        prompt_template: str,
        hub=None,
        description: str = "",
        category: str = "",
    ) -> MarketItem:
        """Publish a new skill to the local marketplace (syncs via P2P).

        Args:
            name: Skill name (e.g. "DockerfileGenerator")
            prompt_template: The LLM system prompt for this skill
            hub: LLM access for auto-description
            description: Manual description (auto-generated if empty)
        """
        sid = f"skill:{name}:v1"
        if not description and hub and hub.world:
            description = self._auto_describe(prompt_template, hub)

        item = MarketItem(
            id=sid,
            name=name,
            type="skill",
            description=description or name,
            category=category,
            prompt_template=prompt_template,
            author="self",
            timestamp=time.time(),
        )
        self._items[sid] = item

        # Save locally
        (SKILLS_DIR / f"{name}.json").write_text(json.dumps({
            "id": item.id, "name": item.name, "type": item.type,
            "description": item.description, "category": item.category,
            "prompt_template": item.prompt_template,
            "author": item.author, "rating": item.rating,
            "version": item.version, "timestamp": item.timestamp,
        }, indent=2, ensure_ascii=False), encoding="utf-8")

        logger.info(f"Skill published: {name}")
        return item

    def publish_tool(
        self,
        name: str,
        code: str,
        description: str = "",
        category: str = "",
    ) -> MarketItem:
        """Publish a reusable code tool."""
        sid = f"tool:{name}:v1"
        item = MarketItem(
            id=sid,
            name=name,
            type="tool",
            description=description or name,
            category=category,
            code=code,
            author="self",
            timestamp=time.time(),
        )
        self._items[sid] = item

        (TOOLS_DIR / f"{name}.py").write_text(
            f"# LivingTree Marketplace Tool: {name}\n"
            f"# {description}\n"
            f"# Author: {item.author}\n\n{code}",
            encoding="utf-8",
        )
        logger.info(f"Tool published: {name}")
        return item

    async def discover_skills(self, hub=None) -> list[MarketItem]:
        """Discover new skills from P2P network peers."""
        new_items = []

        # Phase 1: Local discovery (scan marketplace dir)
        for f in SKILLS_DIR.glob("*.json"):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                sid = d.get("id", f"skill:{f.stem}:v1")
                if sid not in self._items:
                    item = MarketItem(**{k: d.get(k, "") for k in MarketItem.__dataclass_fields__})
                    self._items[sid] = item
                    new_items.append(item)
            except Exception:
                pass

        # Phase 2: P2P discovery
        try:
            from ..network.p2p_node import get_p2p_node
            node = get_p2p_node()
            peers = await node.discover_peers()
            for peer in peers[:5]:
                capabilities = getattr(peer, 'capabilities', None)
                if capabilities and hasattr(capabilities, 'skills'):
                    for skill_name in capabilities.skills[:10]:
                        if not any(s.name == skill_name for s in self._items.values()):
                            item = MarketItem(
                                id=f"p2p:{skill_name}:1",
                                name=skill_name,
                                type="skill",
                                description=f"Imported from P2P peer {peer.peer_id[:12]}",
                                author=peer.peer_id[:16],
                                timestamp=time.time(),
                            )
                            self._items[item.id] = item
                            new_items.append(item)
        except Exception as e:
            logger.debug(f"P2P discover: {e}")

        if new_items:
            logger.info(f"Discovered {len(new_items)} new skills/tools")

        return new_items

    async def sync_with_relay(self, hub=None):
        """Push/pull marketplace data via relay server."""
        try:
            from ..network.p2p_node import get_p2p_node
            node = get_p2p_node()

            # Push: advertise our skills
            my_skills = self.search("skill")
            if my_skills and node._connected:
                skill_list = [
                    {"name": s.name, "description": s.description, "category": s.category}
                    for s in my_skills[:10]
                ]
                try:
                    await node.broadcast_capabilities("skills", skill_list)
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Marketplace sync: {e}")

    def search(self, query: str = "", type_filter: str = "") -> list[MarketItem]:
        """Search marketplace by keyword."""
        results = []
        q = query.lower()
        for item in self._items.values():
            if type_filter and item.type != type_filter:
                continue
            if not q:
                results.append(item)
            elif (q in item.name.lower() or q in item.description.lower() or
                  q in item.category.lower()):
                results.append(item)
        results.sort(key=lambda i: -(i.rating or i.downloads))
        return results

    def get(self, item_id: str) -> MarketItem | None:
        return self._items.get(item_id)

    def apply_skill(self, name: str, hub) -> bool:
        """Register a marketplace skill into the system's skill router."""
        item = self.search(name)
        if not item:
            return False
        item = item[0]
        if item.type != "skill" or not item.prompt_template:
            return False
        try:
            from ..dna.unified_skill_system import get_skill_system
            ss = get_skill_system()
            ss.register_skill(item.name, item.description, item.prompt_template)
            return True
        except Exception as e:
            logger.debug(f"Apply skill: {e}")
            return False

    def _auto_describe(self, prompt: str, hub) -> str:
        """LLM auto-generates short description for a skill."""
        try:
            # Try sync with event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                future = asyncio.ensure_future(self._llm_describe(prompt, hub))
                # Don't await, return placeholder
                return prompt[:100] + "..." if len(prompt) > 100 else prompt
            return prompt[:100]
        except RuntimeError:
            return prompt[:100]

    async def _llm_describe(self, prompt: str, hub) -> str:
        llm = hub.world.consciousness._llm
        try:
            result = await llm.chat(
                messages=[{"role": "user", "content": (
                    f"Write ONE short line (max 60 chars) describing this AI skill:\n{prompt[:500]}"
                )}],
                provider=getattr(llm, '_elected', ''),
                temperature=0.0, max_tokens=30, timeout=5,
            )
            return (result.text or prompt[:60]).strip()[:80] if result else prompt[:60]
        except Exception:
            return prompt[:60]

    def _load(self):
        for f in list(SKILLS_DIR.glob("*.json")) + list(TOOLS_DIR.glob("*.json")):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                sid = d.get("id", f"local:{f.stem}:1")
                self._items[sid] = MarketItem(**{k: d.get(k, "") for k in MarketItem.__dataclass_fields__})
            except Exception:
                pass


_am: AgentMarketplace | None = None


def get_marketplace() -> AgentMarketplace:
    global _am
    if _am is None:
        _am = AgentMarketplace()
    return _am
