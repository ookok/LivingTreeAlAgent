"""CLIIntrospector — Auto-discover any system CLI program and register as a living tool.

Scans $PATH, runs --help on each binary, parses flags/subcommands, and
auto-registers them as CapabilityBus capabilities. This gives the system
"CLI-anything": any installed program instantly becomes a callable tool.

Capabilities:
  1. PATH scan: find all executables on the system
  2. --help parser: extract flags, subcommands, descriptions
  3. Auto-register: create Capability descriptors and register in CapabilityBus
  4. Execute: wrap any CLI as bus.invoke("cli:program_name", ...)

Integration:
  introspector = get_cli_introspector()
  tools = await introspector.scan_path()      # Discover all CLI tools
  await introspector.register_all()            # Auto-register in CapabilityBus
  result = await introspector.execute("ffmpeg", "-i in.mp4 out.mp3")

Usage:
  livingtree cli scan           # Scan and list available CLI tools
  livingtree cli register NAME  # Register a specific tool
  livingtree cli register-all   # Register ALL discovered tools
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger


# ═══ Data Types ════════════════════════════════════════════════════


@dataclass
class CLITool:
    """A discovered CLI program with its parsed interface."""
    name: str
    path: str
    description: str = ""
    flags: list[dict] = field(default_factory=list)    # [{name, type, required, description}]
    subcommands: list[str] = field(default_factory=list)
    version: str = ""
    category: str = ""    # dev, media, system, network, data, util, unknown


@dataclass
class CLIScanResult:
    tools: list[CLITool]
    registered: int = 0
    failed: int = 0
    duration_ms: float = 0.0


# ═══ CLIIntrospector ══════════════════════════════════════════════


class CLIIntrospector:
    """Auto-discover, parse, and register any system CLI program."""

    _instance: Optional["CLIIntrospector"] = None

    @classmethod
    def instance(cls) -> "CLIIntrospector":
        if cls._instance is None:
            cls._instance = CLIIntrospector()
        return cls._instance

    def __init__(self):
        self._tools: dict[str, CLITool] = {}
        self._registered: set[str] = set()
        self._tool_categories = self._build_category_map()

    # ── PATH Scanning ──────────────────────────────────────────────

    def scan_path(self, filter_pattern: str = "",
                  max_tools: int = 200) -> list[CLITool]:
        """Scan all directories in $PATH for executable binaries."""
        paths = os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin").split(os.pathsep)
        seen = set()
        tools = []

        for dir_path in paths:
            if not os.path.isdir(dir_path):
                continue
            try:
                for entry in os.listdir(dir_path):
                    full_path = os.path.join(dir_path, entry)
                    if not os.access(full_path, os.X_OK) or os.path.isdir(full_path):
                        continue
                    if entry in seen:
                        continue
                    if filter_pattern and filter_pattern.lower() not in entry.lower():
                        continue
                    seen.add(entry)
                    tools.append(self._quick_introspect(entry, full_path))
                    if len(tools) >= max_tools:
                        return tools
            except PermissionError:
                continue

        return tools

    def _quick_introspect(self, name: str, path: str) -> CLITool:
        """Quick introspection without running --help (safe but limited)."""
        tool = CLITool(name=name, path=path)
        tool.category = self._categorize(name)
        return tool

    async def deep_introspect(self, name: str, path: str = "",
                              timeout: float = 5.0) -> CLITool:
        """Deep introspection: run --help and parse output."""
        if not path:
            path = shutil.which(name) or name
            if not os.path.exists(path):
                return CLITool(name=name, path=path,
                              description=f"Binary not found: {name}")

        tool = CLITool(name=name, path=path)
        tool.category = self._categorize(name)

        # Try --help
        for help_flag in ["--help", "-h", "-help", "/?"]:
            try:
                proc = await asyncio.create_subprocess_exec(
                    path, help_flag,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout,
                )
                output = (stdout + stderr).decode("utf-8", errors="replace")

                if output and len(output) > 10:
                    tool.description = self._extract_description(output)
                    tool.flags = self._parse_flags(output)
                    tool.subcommands = self._parse_subcommands(output)
                    break
            except (asyncio.TimeoutError, Exception):
                continue

        # Try --version
        for ver_flag in ["--version", "-V", "-version"]:
            try:
                proc = await asyncio.create_subprocess_exec(
                    path, ver_flag,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await asyncio.wait_for(
                    proc.communicate(), timeout=3.0,
                )
                ver_text = stdout.decode("utf-8", errors="replace").strip()
                if ver_text and len(ver_text) < 200:
                    tool.version = ver_text[:100]
                    break
            except Exception:
                continue

        self._tools[name] = tool
        return tool

    # ── Help Parsers ───────────────────────────────────────────────

    def _extract_description(self, output: str) -> str:
        """Extract first meaningful sentence from --help output."""
        lines = output.strip().split("\n")
        for line in lines:
            line = line.strip()
            # Skip header lines
            if line.startswith("Usage:") or line.startswith("用法:"):
                continue
            if len(line) > 20 and not line.startswith("-"):
                return line[:200]
        return lines[0][:200] if lines else ""

    def _parse_flags(self, output: str) -> list[dict]:
        """Parse flag definitions from --help output."""
        flags = []
        # Common patterns: -f, --flag, --flag=VALUE, --flag <value>
        patterns = [
            r'^\s*(-{1,2}[\w-]+)(?:[ =]([A-Z_]+|\w+))?\s*(.*)',
            r'^\s*(-{1,2}[\w-]+)\s+([A-Z_]+|\w+)\s*(.*)',
        ]
        for line in output.split("\n"):
            for pat in patterns:
                m = re.match(pat, line.strip())
                if m:
                    name = m.group(1)
                    value_type = m.group(2) or ""
                    desc = m.group(3).strip()[:100] if m.lastindex >= 3 else ""
                    if not name.startswith("-"):
                        continue
                    flags.append({
                        "name": name, "type": "string" if value_type else "bool",
                        "description": desc[:100],
                    })
                    break
        return flags[:20]  # Cap

    def _parse_subcommands(self, output: str) -> list[str]:
        """Extract subcommand names from --help output."""
        subs = []
        in_commands = False
        for line in output.split("\n"):
            line = line.strip()
            if re.match(r'^\s*(Commands|命令|子命令|subcommands):', line, re.IGNORECASE):
                in_commands = True
                continue
            if in_commands and line and not line.startswith("-") and len(line) > 1:
                word = line.split()[0] if line.split() else ""
                if word and not word.startswith("-") and len(word) > 1:
                    subs.append(word)
            if in_commands and not line:
                break
        return subs[:30]

    def _categorize(self, name: str) -> str:
        for cat, patterns in self._tool_categories.items():
            for pat in patterns:
                if pat in name.lower():
                    return cat
        return "util"

    def _build_category_map(self) -> dict[str, list[str]]:
        return {
            "dev": ["git", "python", "pip", "npm", "node", "cargo", "go", "rust",
                    "gcc", "clang", "make", "cmake", "docker", "kubectl", "grep",
                    "sed", "awk", "find", "xargs", "ssh", "scp", "rsync"],
            "media": ["ffmpeg", "ffprobe", "imagemagick", "convert", "sox",
                      "vlc", "mpv", "gimp", "inkscape", "audacity"],
            "system": ["ls", "ps", "top", "df", "du", "kill", "chmod", "chown",
                       "mount", "systemctl", "journalctl", "crontab"],
            "network": ["curl", "wget", "ping", "traceroute", "nslookup", "dig",
                        "nc", "nmap", "tcpdump", "iptables"],
            "data": ["sqlite3", "jq", "csvkit", "pandas", "mlr", "xsv", "datamash"],
            "util": ["tar", "zip", "gzip", "bzip2", "xz", "pandoc", "tree",
                     "watch", "timeout", "nice", "renice", "screen", "tmux"],
        }

    # ── Registration ───────────────────────────────────────────────

    async def register_tool(self, name: str, bus: Any = None) -> bool:
        """Register a CLI tool in CapabilityBus for unified invocation."""
        if name in self._registered:
            return True

        tool = self._tools.get(name)
        if not tool:
            tool = await self.deep_introspect(name)

        if not bus:
            try:
                from .capability_bus import get_capability_bus, Capability, CapCategory, CapParam
                bus = get_capability_bus()
            except Exception as e:
                logger.debug(f"CLIIntrospector: CapabilityBus not available: {e}")
                return False

        try:
            from .capability_bus import Capability, CapCategory, CapParam
            cap = Capability(
                id=f"cli:{tool.name}",
                name=tool.name,
                category=CapCategory.TOOL,
                description=tool.description or f"System CLI: {tool.path}",
                params=[CapParam(name="args", type="string",
                                description="CLI arguments and flags")],
                handler=lambda args="", _name=tool.name, _path=tool.path:
                    self._execute_sync(_path, args),
                source=f"cli_introspector:{tool.category}",
                tags=[tool.category, tool.version] if tool.version else [tool.category],
            )
            bus.register(cap)
            self._registered.add(name)
            logger.info(f"CLIIntrospector: registered 'cli:{name}'")
            return True
        except Exception as e:
            logger.debug(f"CLIIntrospector register {name}: {e}")
            return False

    async def register_all(self, max_tools: int = 50,
                           bus: Any = None) -> CLIScanResult:
        """Scan PATH and register all discovered tools."""
        t0 = time.time()
        result = CLIScanResult(tools=[], duration_ms=0)

        # Quick scan
        tools = self.scan_path(max_tools=max_tools)
        result.tools = tools

        # Deep introspect top tools (those with category)
        prioritized = [t for t in tools if t.category != "unknown"][:30]
        for tool in prioritized:
            try:
                await self.deep_introspect(tool.name, tool.path)
                if await self.register_tool(tool.name, bus):
                    result.registered += 1
                else:
                    result.failed += 1
            except Exception:
                result.failed += 1

        result.duration_ms = (time.time() - t0) * 1000
        logger.info(
            f"CLIIntrospector: registered {result.registered}/{len(prioritized)} tools "
            f"({result.failed} failed, {result.duration_ms:.0f}ms)"
        )
        return result

    # ── Execution ──────────────────────────────────────────────────

    async def execute(self, name: str, args: str = "",
                      timeout: float = 30.0,
                      cwd: str = "") -> dict:
        """Execute a CLI program and return structured result."""
        path = shutil.which(name) or name
        if not os.path.exists(path):
            return {"error": f"Binary not found: {name}", "exit_code": -1}

        try:
            import shlex
            cmd_parts = [path] + (shlex.split(args) if args else [])
            proc = await asyncio.create_subprocess_exec(
                *cmd_parts,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd or os.getcwd(),
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout,
            )
            return {
                "stdout": stdout.decode("utf-8", errors="replace")[:50000],
                "stderr": stderr.decode("utf-8", errors="replace")[:10000],
                "exit_code": proc.returncode or 0,
                "command": f"{name} {args}"[:200],
            }
        except asyncio.TimeoutError:
            return {"error": f"Timeout after {timeout}s", "exit_code": -1}
        except Exception as e:
            return {"error": str(e)[:500], "exit_code": -1}

    @staticmethod
    def _execute_sync(path: str, args: str) -> dict:
        """Sync wrapper for CapabilityBus handler."""
        try:
            import shlex
            result = subprocess.run(
                [path] + (shlex.split(args) if args else []),
                capture_output=True, text=True, timeout=30,
                cwd=os.getcwd(),
            )
            return {
                "stdout": result.stdout[:10000],
                "stderr": result.stderr[:5000],
                "exit_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"error": "Timeout after 30s", "exit_code": -1}
        except Exception as e:
            return {"error": str(e)[:500], "exit_code": -1}

    # ── Discovery Helpers ──────────────────────────────────────────

    def list_available(self, category: str = "") -> list[dict]:
        """List all discovered CLI tools."""
        tools = list(self._tools.values()) or self.scan_path()
        if category:
            tools = [t for t in tools if t.category == category]
        return [{"name": t.name, "path": t.path, "category": t.category,
                 "description": t.description[:120],
                 "flags": len(t.flags), "subcommands": len(t.subcommands),
                 "registered": t.name in self._registered}
                for t in tools[:100]]

    def search(self, query: str) -> list[dict]:
        """Search for CLI tools matching a query."""
        tools = self.scan_path(filter_pattern=query, max_tools=50)
        return [{"name": t.name, "category": t.category,
                 "description": t.description[:120]}
                for t in tools]

    def stats(self) -> dict:
        return {"tools_discovered": len(self._tools),
                "tools_registered": len(self._registered)}


# ═══ Singleton ════════════════════════════════════════════════════

_introspector: Optional[CLIIntrospector] = None


def get_cli_introspector() -> CLIIntrospector:
    global _introspector
    if _introspector is None:
        _introspector = CLIIntrospector()
    return _introspector


__all__ = ["CLIIntrospector", "CLITool", "CLIScanResult", "get_cli_introspector"]
