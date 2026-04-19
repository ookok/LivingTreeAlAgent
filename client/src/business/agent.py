# =================================================================
# HermesAgent - Herms智能体
# =================================================================

from PyQt6.QtCore import QObject, pyqtSignal
from typing import Optional, Dict, Any


class AgentCallbacks:
    """智能体回调接口（占位）"""
    pass


class HermesAgent(QObject):
    """Hermes智能体（占位）"""

    # 信号
    message_ready = pyqtSignal(str)

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.config = config or {}

    def send_message(self, text: str):
        """发送消息"""
        pass


__all__ = ['HermesAgent', 'AgentCallbacks']