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

    DANGEROUS_PATTERNS = [
        r"\brm\b", r"\brmdir\b", r"\bdel\b", r"\bformat\b", r"\bfdisk\b",
        r"\bmkfs\b", r"\bdd\s+if=", r"\bshutdown\b", r"\breboot\b",
        r"\bchmod\s+777\b", r"\bchown\b", r"\bsudo\b", r"\bsu\b",
        r"\beval\b", r"\bexec\b", r"\bsource\b", r"\bcurl.*\|.*sh\b",
        r"\bwget.*\|.*sh\b", r"\b>.*/dev/sd", r"\bmount\b", r"\bumount\b",
        r"\biptables\b", r"\bufw\b", r"\bchkconfig\b", r"\bcrontab\b",
        r"\bkill\b", r"\bpkill\b", r"\bkillall\b", r"\btaskkill\b",
        r"\bsc\s+stop\b", r"\bdocker\s+rm", r"\bdocker\s+prune",
        r"\bkubectl\s+delete\b", r"\bnet\s+user\b", r"\bnc\s+-e\b",
    ]
    DANGEROUS_COMMANDS = {
        "rm", "rmdir", "del", "format", "fdisk", "mkfs", "dd",
        "shutdown", "reboot", "halt", "poweroff", "sudo", "su", "chown",
        "chmod", "mount", "umount", "iptables", "ufw", "crontab",
        "kill", "pkill", "killall", "taskkill",
    }

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

    def _is_dangerous(self, name: str, args: str = "") -> str:
        """Check if command or args contain dangerous patterns. Returns reason or ''."""
        cmd = f"{name} {args}".lower()
        import re
        for pat in self.DANGEROUS_PATTERNS:
            if re.search(pat, cmd):
                return f"Blocked dangerous pattern: {pat}"
        if name.lower() in self.DANGEROUS_COMMANDS:
            return f"Blocked dangerous command: {name}"
        return ""

    async def execute(self, name: str, args: str = "",
                       timeout: float = 30.0,
                       cwd: str = "") -> dict:
        """Execute a CLI program through unified ShellExecutor with safety gates."""
        blocked = self._is_dangerous(name, args)
        if blocked:
            return {"error": blocked, "exit_code": -1}

        # Use unified ShellExecutor when available
        try:
            from ..core.shell_env import get_shell
            shell = get_shell()
            result = await shell.execute(f"{name} {args}", timeout=timeout, cwd=cwd or os.getcwd())
            return {
                "stdout": result.stdout[:50000],
                "stderr": result.stderr[:10000],
                "exit_code": result.exit_code,
                "command": f"{name} {args}"[:200],
            }
        except Exception:
            pass

        # Fallback: raw subprocess
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
        name = Path(path).name
        introspector = get_cli_introspector()
        blocked = introspector._is_dangerous(name, args)
        if blocked:
            return {"error": blocked, "exit_code": -1}
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


# ═══ CLI Pipeline Engine — Pipe, Stdin, Env, Compose ══════════════


@dataclass
class CLIPipelineStep:
    program: str
    args: str = ""
    stdin_data: str = ""   # If set, feed this as stdin
    env_vars: dict[str, str] = field(default_factory=dict)


@dataclass
class CLIPipelineResult:
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    steps: int = 0
    duration_ms: float = 0.0


class CLIEngine:
    """Advanced CLI execution: pipes, stdin, env, compose, output parsing."""

    _instance: Optional["CLIEngine"] = None

    @classmethod
    def instance(cls) -> "CLIEngine":
        if cls._instance is None:
            cls._instance = CLIEngine()
        return cls._instance

    # ── Pipeline (Pipe Chaining) ───────────────────────────────────

    async def pipeline(self, steps: list[dict],
                       timeout: float = 60.0) -> CLIPipelineResult:
        """Execute piped CLI chain: step1 | step2 | step3.

        steps: [{"program":"ls","args":"-la"}, {"program":"grep","args":"py"}]
        """
        result = CLIPipelineResult(steps=len(steps))
        t0 = time.time()

        try:
            procs = []
            prev_stdout = None

            for i, step_dict in enumerate(steps):
                cmd = [step_dict["program"]] + (
                    __import__('shlex').split(step_dict.get("args", ""))
                )
                stdin = prev_stdout if i > 0 else asyncio.subprocess.PIPE

                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdin=stdin,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                # Feed stdin data for first step
                if i == 0 and step_dict.get("stdin_data"):
                    proc.stdin.write(step_dict["stdin_data"].encode())
                    await proc.stdin.drain()
                    proc.stdin.close()

                procs.append(proc)
                prev_stdout = proc.stdout

            # Collect final output
            stdout, stderr = await asyncio.wait_for(
                procs[-1].communicate(), timeout=timeout,
            )
            result.stdout = stdout.decode("utf-8", errors="replace")[:50000]
            result.stderr = stderr.decode("utf-8", errors="replace")[:5000]
            result.exit_code = procs[-1].returncode or 0

            # Cleanup earlier procs
            for p in procs[:-1]:
                if p.returncode is None:
                    p.terminate()
        except asyncio.TimeoutError:
            result.stderr = f"Pipeline timeout ({timeout}s)"
            result.exit_code = -1
        except Exception as e:
            result.stderr = str(e)[:500]
            result.exit_code = -1

        result.duration_ms = (time.time() - t0) * 1000
        return result

    # ── With Stdin / File Input ────────────────────────────────────

    async def execute_with_stdin(self, program: str, args: str,
                                 stdin_data: str = "",
                                 input_file: str = "",
                                 env_vars: dict[str, str] = None,
                                 timeout: float = 30.0) -> dict:
        """Execute with stdin data or file input."""
        import shlex
        cmd = [program] + shlex.split(args)
        env = {**os.environ, **(env_vars or {})}

        # File input
        if input_file and os.path.exists(input_file):
            stdin = open(input_file, "rb")
        elif stdin_data:
            proc = await asyncio.create_subprocess_exec(
                *cmd, env=env,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            proc.stdin.write(stdin_data.encode())
            await proc.stdin.drain()
            proc.stdin.close()
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return {"stdout": stdout.decode(errors="replace")[:50000],
                    "stderr": stderr.decode(errors="replace")[:5000],
                    "exit_code": proc.returncode or 0}
        else:
            proc = await asyncio.create_subprocess_exec(
                *cmd, env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return {"stdout": stdout.decode(errors="replace")[:50000],
                "stderr": stderr.decode(errors="replace")[:5000],
                "exit_code": proc.returncode or 0}

    # ── Output Parser — Auto JSON/Table/CSV/TSV ────────────────────

    def parse_output(self, text: str) -> dict:
        """Auto-detect and parse CLI output into structured format."""
        if not text.strip():
            return {"format": "empty", "data": None}

        # Try JSON
        try:
            import json
            data = json.loads(text)
            return {"format": "json", "data": data}
        except (json.JSONDecodeError, ValueError):
            pass

        # Try CSV/TSV
        lines = text.strip().split("\n")
        if len(lines) >= 2:
            # CSV
            if "," in lines[0] and "," in lines[1]:
                try:
                    import csv, io
                    reader = csv.DictReader(io.StringIO(text))
                    rows = list(reader)
                    if rows:
                        return {"format": "csv", "columns": list(rows[0].keys()),
                                "rows": [{k: v for k, v in r.items()} for r in rows[:100]]}
                except Exception:
                    pass
            # TSV
            if "\t" in lines[0] and "\t" in lines[1]:
                headers = lines[0].split("\t")
                rows = []
                for line in lines[1:101]:
                    vals = line.split("\t")
                    if len(vals) == len(headers):
                        rows.append(dict(zip(headers, vals)))
                if rows:
                    return {"format": "tsv", "columns": headers, "rows": rows}

        # Try table (column-aligned text)
        if len(lines) >= 2 and any("  " in l for l in lines[:3]):
            return {"format": "table", "lines": [l.strip() for l in lines[:50]]}

        # Plain text
        return {"format": "text", "lines": lines[:100],
                "line_count": len(lines), "total_chars": len(text)}

    # ── Auto-Generator — NL → CLI Script → Register ────────────────

    async def generate_tool(self, description: str,
                            llm: Any = None) -> dict:
        """Auto-generate a CLI wrapper from natural language description."""
        import hashlib
        import stat

        if not llm:
            try:
                from .core import TreeLLM
                llm = TreeLLM()
            except Exception:
                return {"error": "LLM not available"}

        prompt = (
            f"Generate a bash/shell script that does this task:\n"
            f"  {description}\n\n"
            f"Requirements:\n"
            f"- Single executable script\n"
            f"- Accept command-line arguments (use $1, $2, or Python argparse)\n"
            f"- Print results to stdout (preferably JSON or table format)\n"
            f"- Handle errors gracefully\n"
            f"- The script will be saved and executed, so it must be SAFE\n\n"
            f"Output ONLY the script code in a ```bash or ```python block."
        )
        try:
            result = await llm.chat(
                [{"role": "user", "content": prompt}],
                max_tokens=2000, temperature=0.2, task_type="code",
            )
            code = getattr(result, 'text', '') or str(result)

            # Extract code block
            import re
            m = re.search(r'```(?:bash|python|sh|shell)?\n(.*?)```', code, re.DOTALL)
            if not m:
                return {"error": "Could not extract code from LLM response"}

            script = m.group(1).strip()
            tool_name = "cli_gen_" + hashlib.md5(description.encode()).hexdigest()[:8]

            # Save as executable
            tools_dir = Path(".livingtree/cli_tools")
            tools_dir.mkdir(parents=True, exist_ok=True)
            script_path = tools_dir / tool_name
            if "import " in script or "def " in script:
                script_path = tools_dir / f"{tool_name}.py"
                script = "#!/usr/bin/env python3\n" + script
            else:
                script = "#!/bin/bash\n" + script
            script_path.write_text(script, encoding="utf-8")
            script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC)

            # Auto-register
            introspector = get_cli_introspector()
            tool = await introspector.deep_introspect(str(script_path))
            await introspector.register_tool(tool_name)

            return {
                "tool_name": tool_name, "path": str(script_path),
                "registered": True, "script_length": len(script),
            }
        except Exception as e:
            return {"error": str(e)[:500]}

    # ── Compose / DAG Workflow ─────────────────────────────────────

    async def compose(self, workflow: list[dict],
                      timeout: float = 120.0) -> dict:
        """Execute a DAG of CLI steps with dependencies.

        workflow: [{id, program, args, depends_on:[...]}]
        Steps with no dependencies run in parallel. Depended steps wait.
        """
        completed = {}
        pending = {s["id"]: s for s in workflow}
        results = {}
        t0 = time.time()

        while pending:
            ready = [sid for sid, step in pending.items()
                    if all(d in completed for d in step.get("depends_on", []))]
            if not ready:
                return {"error": "Deadlock detected — check dependencies",
                        "pending": list(pending.keys())}

            tasks = []
            for sid in ready:
                step = pending.pop(sid)
                task = self.execute_with_stdin(
                    step["program"], step.get("args", ""),
                    stdin_data=completed.get(step.get("depends_on", [None])[0],
                                            {}).get("stdout", ""),
                )
                tasks.append((sid, asyncio.create_task(task)))

            for sid, task in tasks:
                try:
                    result = await asyncio.wait_for(task, timeout=timeout / max(len(ready), 1))
                    completed[sid] = result
                    results[sid] = result
                except asyncio.TimeoutError:
                    results[sid] = {"error": "Timeout", "exit_code": -1}
                except Exception as e:
                    results[sid] = {"error": str(e)[:200], "exit_code": -1}

        return {"results": results, "steps": len(workflow),
                "duration_ms": (time.time() - t0) * 1000}

    # ── Man / TLDR Integration ─────────────────────────────────────

    async def fetch_docs(self, program: str) -> dict:
        """Fetch documentation for a CLI program via man or tldr."""
        # Try man first
        try:
            proc = await asyncio.create_subprocess_exec(
                "man", program,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            if stdout:
                return {"source": "man", "content": stdout.decode(errors="replace")[:10000]}
        except Exception:
            pass

        # Try tldr
        try:
            proc = await asyncio.create_subprocess_exec(
                "tldr", program,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            if stdout:
                return {"source": "tldr", "content": stdout.decode(errors="replace")[:5000]}
        except Exception:
            pass

        # Try --help
        try:
            proc = await asyncio.create_subprocess_exec(
                program, "--help",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)
            content = (stdout + stderr).decode(errors="replace")
            if content.strip():
                return {"source": "help", "content": content[:5000]}
        except Exception:
            pass

        return {"source": "none", "content": f"No documentation found for {program}"}


# ═══ Singleton ════════════════════════════════════════════════════

_introspector: Optional[CLIIntrospector] = None
_engine: Optional[CLIEngine] = None


def get_cli_introspector() -> CLIIntrospector:
    global _introspector
    if _introspector is None:
        _introspector = CLIIntrospector()
    return _introspector


def get_cli_engine() -> CLIEngine:
    global _engine
    if _engine is None:
        _engine = CLIEngine()
    return _engine


__all__ = ["CLIIntrospector", "CLITool", "CLIScanResult",
           "CLIEngine", "CLIPipelineResult",
           "get_cli_introspector", "get_cli_engine"]
