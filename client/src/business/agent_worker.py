"""
Agent Worker — Compatibility Stub

Functionality migrated to livingtree.core.agent.
PyQt6 QThread-based agent worker for background task execution.
"""


class AgentWorker:
    def __init__(self, agent_id: str = "", task=None, parent=None):
        self.agent_id = agent_id
        self.task = task
        self._running = False
        self._result = None

    def start(self):
        self._running = True
        if self.task:
            self._result = self.task()

    @property
    def is_running(self):
        return self._running

    @property
    def result(self):
        return self._result


__all__ = ["AgentWorker"]
