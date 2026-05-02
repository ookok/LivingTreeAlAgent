"""
Agent Registry — Compatibility Stub

Functionality migrated to livingtree.core.agent.
"""

from typing import Dict, Any, Optional


class AgentRegistry:
    """Agent registry for discovery and lifecycle management"""

    def __init__(self):
        self._agents: Dict[str, Any] = {}

    def register(self, agent_id: str, agent, **meta):
        self._agents[agent_id] = {"agent": agent, "meta": meta}

    def get(self, agent_id: str):
        entry = self._agents.get(agent_id)
        return entry["agent"] if entry else None

    def list_all(self):
        return [{"id": k, "meta": v.get("meta", {})} for k, v in self._agents.items()]

    def unregister(self, agent_id: str):
        self._agents.pop(agent_id, None)

    def count(self) -> int:
        return len(self._agents)


def get_agent_registry():
    return AgentRegistry()


__all__ = ["AgentRegistry", "get_agent_registry"]
