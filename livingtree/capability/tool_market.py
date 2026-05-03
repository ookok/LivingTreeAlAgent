"""Tool registry and marketplace for LivingTree capabilities.

Supports MCP-compatible tools, with runtime validation and sandboxed
execution where possible. Tools can be of type: shell, http, python, and mcp.
"""

from __future__ import annotations

import json
import importlib
import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field
from loguru import logger
from types import ModuleType


class ToolSpec(BaseModel):
    name: str
    description: str
    type: str = "shell"
    endpoint: Optional[str] = None
    command_template: Optional[str] = None
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    category: str = "general"
    rating: float = 0.0


class ToolMarket:
    def __init__(self) -> None:
        self._tools: Dict[str, ToolSpec] = {}

    # Registration
    def register_tool(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec
        logger.info("Registered tool: {}", spec.name)

    # Discovery
    def discover_tools(self) -> List[ToolSpec]:
        return list(self._tools.values())

    # Validation helper for input data against a dynamic pydantic model
    def _validate_input(self, spec: ToolSpec, input_data: Dict[str, Any]) -> None:
        if not spec.input_schema:
            return
        try:
            from pydantic import create_model
            fields = {k: (Any, ...) for k in spec.input_schema.keys()}
            DynamicModel = create_model(f"ToolInput_{spec.name}", __base__=BaseModel, **fields)  # type: ignore
            DynamicModel(**input_data)  # type: ignore
        except Exception as e:
            raise ValueError(f"Input validation failed for tool {spec.name}: {e}")

    # Execution
    def execute_tool(self, name: str, input_data: Dict[str, Any]) -> Any:
        spec = self._tools.get(name)
        if not spec:
            raise ValueError(f"Tool not found: {name}")
        # Basic safety: avoid dangerous commands in shell templates
        if spec.type == "shell" and spec.command_template:
            if any(danger in spec.command_template.lower() for danger in ["rm -rf", "sudo", "mkfs"]):
                raise RuntimeError("Unsafe shell template detected")
            cmd = spec.command_template.format(**{k: v for k, v in input_data.items()})
            logger.info("Executing shell tool: {} -> {}", name, cmd)
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                logger.error("Tool {} failed: {}", name, result.stderr)
                raise RuntimeError(result.stderr)
            return result.stdout
        elif spec.type == "http":
            try:
                import urllib.request as _ur
                data = json.dumps(input_data).encode("utf-8")
                req = _ur.Request(spec.endpoint or "", data=data, headers={"Content-Type": "application/json"})
                with _ur.urlopen(req, timeout=60) as resp:
                    return resp.read().decode()
            except Exception as e:
                logger.error("HTTP tool error: {}", e)
                raise
        elif spec.type == "python":
            if spec.endpoint and ":" in spec.endpoint:
                module_path, func_name = spec.endpoint.split(":", 1)
                spec_mod = importlib.import_module(module_path)
                func = getattr(spec_mod, func_name)
                if callable(func):
                    return func(input_data)
            raise ValueError("Invalid Python tool endpoint or missing function")
        elif spec.type == "mcp":
            # Placeholder for MCP-based tool invocation
            return {"status": "mcp_invoke", "tool": name, "input": input_data}
        else:
            raise ValueError(f"Unsupported tool type: {spec.type}")

    def get_tool_schema(self, name: str) -> Optional[Dict[str, Any]]:
        spec = self._tools.get(name)
        return spec.input_schema if spec else None

    def rate_tool(self, name: str, rating: float) -> None:
        if name in self._tools:
            self._tools[name].rating = rating
        else:
            raise ValueError(f"Tool not found: {name}")

    def search_tools(self, query: str) -> List[ToolSpec]:
        q = query.lower()
        return [t for t in self._tools.values() if q in t.name.lower() or q in t.description.lower()]
