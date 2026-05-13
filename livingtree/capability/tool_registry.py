"""Tool & Role Registry — migrated from removed TUI widgets.

Provides SYSTEM_TOOLS and EXPERT_ROLES dictionaries that were previously
defined in livingtree/tui/widgets/enhanced_tool_call.py (TUI stub).

These are runtime registries populated by tool discovery and role management.
"""

SYSTEM_TOOLS: dict = {}
"""Registry of system tools. Populated by tool_synthesis.py and tool discovery."""

EXPERT_ROLES: dict = {}
"""Registry of expert roles. Populated by expert_role_manager.py."""
