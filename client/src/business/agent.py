# =================================================================
# HermesAgent - Herms智能体
# =================================================================

from typing import Optional, Dict, Any

from core.agent import HermesAgent as CoreHermesAgent
from core.agent import AgentCallbacks


class HermesAgent(CoreHermesAgent):
    """Hermes智能体"""

    def __init__(self, config: Optional[Dict[str, Any]] = None, session_id: Optional[str] = None, callbacks: Optional[AgentCallbacks] = None, backend: str = "vllm"):
        super().__init__(config, session_id, callbacks, backend)


__all__ = ['HermesAgent', 'AgentCallbacks']