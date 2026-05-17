"""Bridge layer — dependency inversion between treellm and capability.

This package defines abstract interfaces that both treellm and capability
depend on, breaking the circular dependency between them.

Rule: treellm → bridge ← capability  (both depend on bridge, never on each other)
"""

from .protocols import ToolProtocol, LLMProtocol, BusProtocol
from .registry import ToolRegistry, get_tool_registry

__all__ = [
    "ToolProtocol", "LLMProtocol", "BusProtocol",
    "ToolRegistry", "get_tool_registry",
]
