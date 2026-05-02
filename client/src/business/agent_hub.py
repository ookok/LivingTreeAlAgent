"""
Agent Hub — Compatibility Stub

Agent management UI. Functionality migrated to livingtree.core.agent.
"""


class AgentHub:
    def __init__(self, parent=None):
        self.parent = parent
        self._agents = []

    def register(self, agent_id: str, agent):
        self._agents.append({"id": agent_id, "agent": agent})

    def list_agents(self):
        return [a["id"] for a in self._agents]

    def show(self):
        pass


def show_agent_hub(parent=None):
    h = AgentHub(parent)
    h.show()
    return h


__all__ = ["AgentHub", "show_agent_hub"]
