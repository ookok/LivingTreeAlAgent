"""Compatibility stub — original enhanced_tool_call from TUI has been removed.

SYSTEM_TOOLS and EXPERT_ROLES registries are now empty. Tool discovery
is handled by core/interactive_tools.py (InteractiveToolRegistry) and
capability/tool_market.py at runtime.

These empty dicts prevent ImportError while consumers gracefully handle
the absence of data via their existing try/except or .get() guards.
"""

SYSTEM_TOOLS: dict = {}
EXPERT_ROLES: dict = {}


def format_tool_list() -> str:
    """Return empty tool list string."""
    return ""
