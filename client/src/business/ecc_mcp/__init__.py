"""
ECC MCP Bridge - CLI工具库动态挂载
Inspired by Everything Claude Code (ECC)

将 Hermes 的 CLI 工具库 (OfficeCLI/FFmpeg/PageIndex) 包装为 MCP 工具

功能:
- 动态工具发现
- 工具描述生成
- 参数模式匹配
- Hermès System Prompt 注入
"""

import json
import asyncio
import subprocess
from pathlib import Path
from typing import Optional, Callable, Dict, List, Any, Union
from dataclasses import dataclass, field
from enum import Enum

from business.tools_registry import ToolRegistry, ToolDef


class ToolCapability(Enum):
    """工具能力"""
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    COMMAND_EXEC = "command_exec"
    NETWORK = "network"
    SYSTEM = "system"


@dataclass
class MCPTool:
    """MCP 工具描述"""
    name: str
    description: str
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    capability: ToolCapability = ToolCapability.FILE_READ
    cli_command: str = ""  # 对应的 CLI 命令
    examples: List[Dict[str, str]] = field(default_factory=list)


class ToolManifest:
    """工具清单 (tools_manifest.json)"""

    @staticmethod
    def get_default_manifest() -> Dict[str, Any]:
        """获取默认工具清单"""
        return {
            "version": "1.0.0",
            "tools": [
                {
                    "id": "office_cli",
                    "name": "OfficeCLI",
                    "description": "Office文档操作工具",
                    "category": "document",
                    "capabilities": ["file_read", "file_write"],
                    "cli_command": "office-cli",
                    "install_hint": "npm install -g office-cli",
                    "tools": [
                        {"name": "doc_to_pdf", "description": "Word转PDF"},
                        {"name": "excel_summary", "description": "Excel摘要"},
                        {"name": "ppt_extract", "description": "PPT内容提取"},
                    ]
                },
                {
                    "id": "ffmpeg_cli",
                    "name": "FFmpeg",
                    "description": "音视频处理工具",
                    "category": "media",
                    "capabilities": ["command_exec"],
                    "cli_command": "ffmpeg",
                    "install_hint": "Download from ffmpeg.org",
                    "tools": [
                        {"name": "video_to_gif", "description": "视频转GIF"},
                        {"name": "audio_extract", "description": "音频提取"},
                        {"name": "video_compress", "description": "视频压缩"},
                    ]
                },
                {
                    "id": "page_index",
                    "name": "PageIndex",
                    "description": "文档索引和搜索",
                    "category": "search",
                    "capabilities": ["file_read", "search"],
                    "cli_command": "page-index",
                    "install_hint": "pip install page-index",
                    "tools": [
                        {"name": "index_docs", "description": "索引文档"},
                        {"name": "query_index", "description": "查询索引"},
                        {"name": "semantic_search", "description": "语义搜索"},
                    ]
                },
            ]
        }


class MCPToolBridge:
    """
    MCP 工具桥接器

    将 CLI 工具包装为 MCP 工具描述，供 Hermes 使用
    """

    def __init__(self):
        self._manifest = ToolManifest.get_default_manifest()
        self._installed_tools: Dict[str, bool] = {}
        self._tool_cache: List[MCPTool] = []

    def get_available_tools(self) -> List[MCPTool]:
        """获取所有可用工具"""
        tools = []

        for tool_group in self._manifest.get("tools", []):
            cli_cmd = tool_group.get("cli_command", "")
            if not cli_cmd:
                continue

            # 检查是否安装
            if not self._check_installed(cli_cmd):
                continue

            # 为每个子工具创建 MCP 工具描述
            for sub_tool in tool_group.get("tools", []):
                mcp_tool = MCPTool(
                    name=sub_tool["name"],
                    description=sub_tool["description"],
                    capability=self._capability_from_list(tool_group.get("capabilities", [])),
                    cli_command=cli_cmd,
                )
                tools.append(mcp_tool)

        self._tool_cache = tools
        return tools

    def _check_installed(self, cli_command: str) -> bool:
        """检查 CLI 工具是否安装"""
        if cli_command in self._installed_tools:
            return self._installed_tools[cli_command]

        try:
            result = subprocess.run(
                f"{cli_command} --version",
                shell=True,
                capture_output=True,
                timeout=5,
            )
            installed = result.returncode == 0
        except Exception:
            installed = False

        self._installed_tools[cli_command] = installed
        return installed

    @staticmethod
    def _capability_from_list(capabilities: List[str]) -> ToolCapability:
        """从能力列表推断主能力"""
        if "command_exec" in capabilities:
            return ToolCapability.COMMAND_EXEC
        elif "network" in capabilities:
            return ToolCapability.NETWORK
        elif "system" in capabilities:
            return ToolCapability.SYSTEM
        elif "file_write" in capabilities:
            return ToolCapability.FILE_WRITE
        return ToolCapability.FILE_READ

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """获取 OpenAI tools schema 格式"""
        tools = self.get_available_tools()
        schemas = []

        for tool in tools:
            schema = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema or {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                }
            }
            schemas.append(schema)

        return schemas

    def get_system_prompt_injection(self) -> str:
        """获取系统提示词注入 (MCP 工具说明)"""
        tools = self.get_available_tools()

        if not tools:
            return ""

        lines = ["\n## Available MCP Tools\n"]

        # 按能力分组
        by_cap = {}
        for tool in tools:
            by_cap.setdefault(tool.capability.value, []).append(tool)

        for cap, cap_tools in by_cap.items():
            lines.append(f"### {cap.replace('_', ' ').title()}")
            for t in cap_tools:
                lines.append(f"- **{t.name}**: {t.description}")
            lines.append("")

        return "\n".join(lines)

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """执行 MCP 工具"""
        tool = next((t for t in self._tool_cache if t.name == tool_name), None)
        if not tool:
            return {"error": f"Tool not found: {tool_name}"}

        if not self._check_installed(tool.cli_command):
            return {"error": f"Tool not installed: {tool.cli_command}"}

        try:
            # 构建命令
            cmd = f"{tool.cli_command} {tool_name}"

            # 添加参数
            for key, value in arguments.items():
                if value is not None:
                    if isinstance(value, bool):
                        if value:
                            cmd += f" --{key}"
                    else:
                        cmd += f' --{key} "{value}"'

            # 执行
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            return {
                "success": proc.returncode == 0,
                "stdout": stdout.decode() if stdout else "",
                "stderr": stderr.decode() if stderr else "",
                "returncode": proc.returncode,
            }

        except Exception as e:
            return {"error": str(e)}

    def install_tool(self, tool_id: str) -> Dict[str, Any]:
        """安装工具"""
        tool_group = next(
            (tg for tg in self._manifest.get("tools", [])
             if tg.get("id") == tool_id),
            None
        )

        if not tool_group:
            return {"error": f"Tool group not found: {tool_id}"}

        cli_cmd = tool_group.get("cli_command", "")
        install_hint = tool_group.get("install_hint", "")

        if not install_hint:
            return {"error": "No install hint available"}

        try:
            result = subprocess.run(
                install_hint,
                shell=True,
                capture_output=True,
                timeout=120,
            )
            success = result.returncode == 0

            if success:
                self._installed_tools[cli_cmd] = True
                self._tool_cache.clear()  # 清空缓存

            return {
                "success": success,
                "output": result.stdout.decode() if result.stdout else "",
                "error": result.stderr.decode() if result.stderr else "",
            }

        except Exception as e:
            return {"error": str(e)}


class MCPBridge:
    """
    MCP 桥接器

    对外提供统一接口:
    - 工具发现
    - 工具执行
    - System Prompt 注入
    """

    def __init__(self):
        self.tool_bridge = MCPToolBridge()
        self._initialized = False

    def initialize(self):
        """初始化"""
        if self._initialized:
            return

        # 预热工具缓存
        self.tool_bridge.get_available_tools()
        self._initialized = True

    def get_all_tools(self) -> List[MCPTool]:
        """获取所有 MCP 工具"""
        return self.tool_bridge.get_available_tools()

    def get_tools_schema(self) -> List[Dict[str, Any]]:
        """获取工具 schema (OpenAI function calling 格式)"""
        return self.tool_bridge.get_tool_schemas()

    def inject_into_system_prompt(self, system_prompt: str) -> str:
        """注入 MCP 工具说明到系统提示词"""
        injection = self.tool_bridge.get_system_prompt_injection()
        if not injection:
            return system_prompt
        return system_prompt + injection

    async def call_tool(self, tool_name: str,
                       arguments: Dict[str, Any]) -> Dict[str, Any]:
        """调用工具"""
        return await self.tool_bridge.execute_tool(tool_name, arguments)

    def is_tool_available(self, tool_name: str) -> bool:
        """检查工具是否可用"""
        return any(t.name == tool_name for t in self._tool_cache)

    def get_missing_tools(self) -> List[str]:
        """获取未安装的工具列表"""
        missing = []
        for tool_group in self._manifest.get("tools", []):
            cli_cmd = tool_group.get("cli_command", "")
            if cli_cmd and not self._check_installed(cli_cmd):
                missing.append({
                    "id": tool_group["id"],
                    "name": tool_group["name"],
                    "hint": tool_group.get("install_hint", ""),
                })
        return missing


# Singleton
_mcp_bridge: Optional[MCPBridge] = None


def get_mcp_bridge() -> MCPBridge:
    global _mcp_bridge
    if _mcp_bridge is None:
        _mcp_bridge = MCPBridge()
    return _mcp_bridge