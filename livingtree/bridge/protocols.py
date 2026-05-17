"""Abstract protocols for dependency inversion.

treellm and capability both import from here, never from each other.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ToolProtocol(Protocol):
    """Abstract tool interface — capability modules implement this."""
    name: str
    description: str

    async def execute(self, params: dict[str, Any]) -> Any: ...


@runtime_checkable
class LLMProtocol(Protocol):
    """Abstract LLM interface — treellm modules implement this."""

    async def chat(self, messages: list[dict], **kwargs) -> str: ...

    async def stream(self, messages: list[dict], **kwargs): ...


@runtime_checkable
class BusProtocol(Protocol):
    """Abstract capability bus — bridge module implements this."""

    def register_tool(self, tool: ToolProtocol) -> None: ...

    async def call_tool(self, name: str, params: dict) -> Any: ...

    def list_tools(self) -> list[str]: ...


__all__ = ["ToolProtocol", "LLMProtocol", "BusProtocol"]
