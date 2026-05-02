"""
Ralph Agent Loop — Compatibility Stub
"""


class RalphAgentLoop:
    def __init__(self, model: str = ""):
        self.model = model

    def step(self, observation: str) -> str:
        return f"[Agent] Action for: {observation[:50]}"

    def run(self, task: str, max_steps: int = 10) -> str:
        return f"[AgentLoop] {task}"


__all__ = ["RalphAgentLoop"]
