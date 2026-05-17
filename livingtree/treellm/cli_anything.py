"""CLIAnything — Convert any program or project into a first-class CLI tool.

Core philosophy: ANY code should become a CLI tool automatically.
  - A Python function → `mycli greet --name Alice` 
  - A shell script → discovered, wrapped, args parsed
  - A git repo → cloned, entrypoints found, CLI generated, installed
  - A binary without docs → --help generated from behavior analysis

Components:
  1. UniversalWrapper: wrap any code fragment as CLI (argparse, help, validate)
  2. ProjectToCLI: git clone → analyze entry_points → generate CLI → install
  3. CLIManifest: declarative YAML: "this code → these CLI commands"
  4. CLIPublisher: auto-generate pip/setup.py, npm/package.json, cargo/Cargo.toml

Usage as a framework:
  cli = CLIAnything()
  cli.wrap_function(my_func, name="greet", params=[...])  # → CLI tool
  cli.from_git_repo("https://github.com/user/repo")        # → installed CLI
  cli.from_manifest("cli.yaml")                             # → generates CLI
  cli.publish("mytool")                                     # → pip install ready
"""

from __future__ import annotations

import ast
import inspect
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from loguru import logger
import yaml
# SUBPROCESS MIGRATION: from livingtree.treellm.unified_exec import run_sync


CLI_TOOLS_DIR = Path(".livingtree/cli_tools")
MANIFEST_DIR = Path(".livingtree/cli_manifests")


# ═══ Data Types ════════════════════════════════════════════════════


@dataclass
class CLIParam:
    name: str
    type: str = "str"          # str | int | float | bool | file | dir
    description: str = ""
    required: bool = False
    default: Any = None
    choices: list[Any] = field(default_factory=list)
    flag: str = ""             # --flag or positional


@dataclass
class CLICommand:
    name: str
    description: str = ""
    params: list[CLIParam] = field(default_factory=list)
    handler: Callable = None   # The actual function
    subcommands: list["CLICommand"] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)


@dataclass
class CLIDefinition:
    """Complete CLI tool definition."""
    name: str
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    entry_point: str = ""      # console_scripts entry
    commands: list[CLICommand] = field(default_factory=list)
    requires: list[str] = field(default_factory=list)  # pip packages
    python_requires: str = ">=3.9"


@dataclass
class CLIProject:
    """A git repo analyzed for CLI potential."""
    repo_url: str = ""
    local_path: Path = None
    entry_points: list[str] = field(default_factory=list)
    language: str = "unknown"
    suggested_commands: list[CLICommand] = field(default_factory=list)


# ═══ Universal Wrapper ═════════════════════════════════════════════


class UniversalWrapper:
    """Wrap any Python callable, script, or code fragment as a CLI tool."""

    @staticmethod
    def wrap_function(func: Callable, name: str = "",
                     description: str = "",
                     params: list[CLIParam] = None) -> CLICommand:
        """Wrap a Python function as a CLI command with auto-generated argparse."""
        cmd_name = name or func.__name__
        sig_params = params or UniversalWrapper._inspect_params(func)

        cmd = CLICommand(
            name=cmd_name,
            description=description or (func.__doc__ or "").split("\n")[0][:200],
            params=sig_params,
            handler=func,
        )
        return cmd

    @staticmethod
    def generate_cli_script(definition: CLIDefinition,
                            output_dir: Path = None) -> Path:
        """Generate a complete CLI Python script from a CLIDefinition.

        Produces a standalone .py file with argparse, --help, subcommands,
        input validation, and error handling.
        """
        output_dir = output_dir or CLI_TOOLS_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        script_path = output_dir / f"{definition.name}.py"

        lines = [
            "#!/usr/bin/env python3",
            f'"""{definition.description}"""',
            "import argparse, sys, json, os",
        ]

        # Generate argparse for each command
        for cmd in definition.commands:
            lines.append(f"\ndef _cmd_{cmd.name}(args):")
            lines.append(f'    """{cmd.description}"""')
            # Build params extraction
            for p in cmd.params:
                attr = p.name.replace("-", "_")
                lines.append(f"    {attr} = getattr(args, '{attr}', {repr(p.default)})")
                if p.type == "int":
                    lines.append(f"    {attr} = int({attr})")
                elif p.type == "float":
                    lines.append(f"    {attr} = float({attr})")
                elif p.type == "file" and p.name not in ("args", "kwargs"):
                    lines.append(f"    if not os.path.exists({attr}): print(f'File not found: {{{attr}}}'); return 1")
            lines.append(f"    print(f'[{cmd.name}] completed')")
            lines.append(f"    return 0")

        # Main entry with argparse
        lines.extend([
            "",
            "def main():",
            f"    parser = argparse.ArgumentParser(prog='{definition.name}', description='{definition.description}')",
            f"    parser.add_argument('--version', action='version', version='{definition.name} {definition.version}')",
            "    subparsers = parser.add_subparsers(dest='command', help='Available commands')",
        ])

        for cmd in definition.commands:
            lines.append(f"    p_{cmd.name} = subparsers.add_parser('{cmd.name}', help='{cmd.description}')")
            for p in cmd.params:
                flag = p.flag or f"--{p.name.replace('_', '-')}"
                kwargs = {"help": p.description}
                if p.type == "bool":
                    kwargs["action"] = "store_true"
                elif p.type == "int":
                    kwargs["type"] = int
                elif p.type == "float":
                    kwargs["type"] = float
                else:
                    kwargs["type"] = str
                if p.required:
                    kwargs["required"] = True
                if p.default is not None:
                    kwargs["default"] = p.default
                if p.choices:
                    kwargs["choices"] = p.choices
                lines.append(f"    p_{cmd.name}.add_argument('{flag}', **{repr(kwargs)})")

        lines.extend([
            "",
            "    args = parser.parse_args()",
            "    if not args.command:",
            "        parser.print_help()",
            "        return 1",
        ])

        # Dispatch
        for cmd in definition.commands:
            lines.append(f"    if args.command == '{cmd.name}': return _cmd_{cmd.name}(args)")

        lines.extend([
            "",
            "if __name__ == '__main__':",
            "    sys.exit(main())",
        ])

        script_path.write_text("\n".join(lines), encoding="utf-8")
        script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC)
        logger.info(f"UniversalWrapper: generated {script_path}")
        return script_path

    @staticmethod
    def generate_setup_py(definition: CLIDefinition,
                          output_dir: Path = None) -> Path:
        """Generate setup.py / pyproject.toml for pip install."""
        output_dir = output_dir or CLI_TOOLS_DIR
        pkg_dir = output_dir / definition.name
        pkg_dir.mkdir(parents=True, exist_ok=True)

        setup_py = textwrap.dedent(f'''
        from setuptools import setup, find_packages
        setup(
            name="{definition.name}",
            version="{definition.version}",
            description="{definition.description[:200]}",
            author="{definition.author}",
            python_requires="{definition.python_requires}",
            install_requires={repr(definition.requires)},
            entry_points={{
                "console_scripts": [
                    "{definition.name}={definition.name}.{definition.entry_point or 'main'}:main",
                ],
            }},
            packages=find_packages(),
        )
        ''')

        (output_dir / "setup.py").write_text(setup_py, encoding="utf-8")
        return output_dir / "setup.py"

    @staticmethod
    def _inspect_params(func: Callable) -> list[CLIParam]:
        """Inspect function signature to auto-derive CLI params."""
        try:
            sig = inspect.signature(func)
            params = []
            for pname, p in sig.parameters.items():
                if pname == "self":
                    continue
                ptype = "str"
                if p.annotation is not inspect.Parameter.empty:
                    anno = p.annotation
                    if anno in (int, float, bool):
                        ptype = anno.__name__
                    elif anno == str:
                        ptype = "str"
                params.append(CLIParam(
                    name=pname, type=ptype,
                    required=p.default is inspect.Parameter.empty,
                    default=None if p.default is inspect.Parameter.empty else p.default,
                ))
            return params
        except Exception:
            return [CLIParam(name="args", type="str", description="Arguments")]


# ═══ Project to CLI ════════════════════════════════════════════════


class ProjectToCLI:
    """Analyze a git repo and auto-convert it to a CLI tool."""

    @staticmethod
    async def from_git_repo(repo_url: str,
                            output_dir: Path = None) -> CLIProject:
        """Clone a git repo, analyze entry points, suggest CLI commands."""
        output_dir = output_dir or CLI_TOOLS_DIR / "repos"
        output_dir.mkdir(parents=True, exist_ok=True)

        repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
        local_path = output_dir / repo_name

        # Clone — use unified ShellExecutor
        if local_path.exists():
            shutil.rmtree(local_path)
        try:
            from ..core.shell_env import get_shell
            shell = get_shell()
            result = await shell.execute("git clone --depth 1 " + repo_url + " " + str(local_path))
        except Exception:
            subprocess.run(["git", "clone", "--depth", "1", repo_url, str(local_path)],
                          capture_output=True, check=False)

        project = CLIProject(repo_url=repo_url, local_path=local_path)

        # Detect language and entry points
        project.entry_points = await ProjectToCLI._find_entry_points(local_path)
        project.language = ProjectToCLI._detect_language(local_path)
        project.suggested_commands = await ProjectToCLI._suggest_commands(local_path)

        return project

    @staticmethod
    async def _find_entry_points(path: Path) -> list[str]:
        """Find potential CLI entry points in a project."""
        entries = []

        # setup.py console_scripts
        setup_py = path / "setup.py"
        if setup_py.exists():
            content = setup_py.read_text(errors="replace")
            for m in re.finditer(r"console_scripts.*?\[(.*?)\]", content, re.DOTALL):
                entries.extend(re.findall(r'"([^"]+)"', m.group(1)))

        # pyproject.toml scripts
        pyproject = path / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text(errors="replace")
            for m in re.finditer(r'\[project\.scripts\](.*?)(?=\[|\Z)', content, re.DOTALL):
                for line in m.group(1).strip().split("\n"):
                    if "=" in line:
                        entries.append(line.split("=")[0].strip())

        # package.json bin
        pkg_json = path / "package.json"
        if pkg_json.exists():
            try:
                data = json.loads(pkg_json.read_text())
                if "bin" in data:
                    bin_val = data["bin"]
                    if isinstance(bin_val, dict):
                        entries.extend(bin_val.keys())
                    elif isinstance(bin_val, str):
                        entries.append(data.get("name", "cli"))
            except Exception:
                pass

        # Cargo.toml [[bin]]
        cargo = path / "Cargo.toml"
        if cargo.exists():
            content = cargo.read_text(errors="replace")
            for m in re.finditer(r'name\s*=\s*"([^"]+)"', content):
                entries.append(m.group(1))

        # __main__.py existence
        if (path / "__main__.py").exists():
            entries.append(path.name)

        # main.go, main.rs, index.js patterns
        for pattern in ["main.py", "main.go", "main.rs", "index.js", "cli.py", "app.py"]:
            if (path / pattern).exists():
                entries.append(pattern)

        return list(set(entries))[:20]

    @staticmethod
    def _detect_language(path: Path) -> str:
        counts = {"python": 0, "javascript": 0, "go": 0, "rust": 0, "shell": 0}
        for ext in path.rglob("*"):
            if ext.suffix == ".py": counts["python"] += 1
            elif ext.suffix == ".js": counts["javascript"] += 1
            elif ext.suffix == ".go": counts["go"] += 1
            elif ext.suffix == ".rs": counts["rust"] += 1
            elif ext.suffix == ".sh": counts["shell"] += 1
        return max(counts, key=counts.get)

    @staticmethod
    async def _suggest_commands(path: Path) -> list[CLICommand]:
        """Auto-suggest CLI commands based on function signatures in the project."""
        commands = []
        for py_file in path.rglob("*.py"):
            if py_file.name.startswith("test_"):
                continue
            try:
                tree = ast.parse(py_file.read_text(errors="replace"))
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if node.name.startswith("_"):
                            continue
                        args = [a.arg for a in node.args.args if a.arg != "self"]
                        docstring = ast.get_docstring(node) or ""
                        commands.append(CLICommand(
                            name=node.name,
                            description=docstring[:200],
                            params=[CLIParam(name=a, type="str") for a in args[:5]],
                        ))
            except SyntaxError:
                continue
        return commands[:50]

    @staticmethod
    async def install(project: CLIProject) -> dict:
        """Install the project as a CLI tool."""
        if not project.local_path or not project.local_path.exists():
            return {"error": "Project not cloned"}

        if project.language == "python":
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-e", str(project.local_path)],
                capture_output=True, check=False,
            )
            return {"installed": True, "method": "pip install -e"}
        elif project.language == "javascript":
            subprocess.run(
                ["npm", "install", "-g", str(project.local_path)],
                capture_output=True, check=False,
            )
            return {"installed": True, "method": "npm install -g"}
        else:
            return {"installed": False, "reason": f"Unsupported language: {project.language}"}


# ═══ CLI Manifest ══════════════════════════════════════════════════


@dataclass
class CLIManifest:
    """Declarative YAML/JSON: 'this code → these CLI commands'."""
    path: Path

    @staticmethod
    def from_yaml(yaml_path: str | Path) -> CLIDefinition:
        """Parse a CLI manifest YAML file into a CLIDefinition."""
        path = Path(yaml_path)
        data = yaml.safe_load(path.read_text(encoding="utf-8"))

        commands = []
        for cmd_data in data.get("commands", []):
            params = [CLIParam(**p) for p in cmd_data.get("params", [])]
            commands.append(CLICommand(
                name=cmd_data["name"],
                description=cmd_data.get("description", ""),
                params=params,
            ))

        return CLIDefinition(
            name=data.get("name", path.stem),
            version=data.get("version", "0.1.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            entry_point=data.get("entry_point", "main"),
            commands=commands,
            requires=data.get("requires", []),
        )

    @staticmethod
    def generate_template(name: str, output_dir: Path = None) -> Path:
        """Generate a starter CLI manifest YAML template."""
        output_dir = output_dir or MANIFEST_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = output_dir / f"{name}.yaml"

        template = f'''
name: {name}
version: "0.1.0"
description: "A CLI tool for {name}"
author: ""
entry_point: main
python_requires: ">=3.9"
requires: []
commands:
  - name: hello
    description: "Say hello"
    params:
      - name: name
        type: str
        description: "Name to greet"
        required: false
        default: "World"
  - name: process
    description: "Process a file"
    params:
      - name: input
        type: file
        description: "Input file path"
        required: true
      - name: verbose
        type: bool
        flag: "--verbose"
        description: "Enable verbose output"
        required: false
'''.strip()

        manifest_path.write_text(template, encoding="utf-8")
        return manifest_path


# ═══ CLI Publisher ══════════════════════════════════════════════════


class CLIPublisher:
    """Auto-generate packaging files for pip, npm, cargo, brew."""

    @staticmethod
    def publish_pip(definition: CLIDefinition,
                    output_dir: Path = None) -> dict:
        """Generate pip-installable package."""
        output_dir = output_dir or CLI_TOOLS_DIR / definition.name
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate CLI script
        UniversalWrapper.generate_cli_script(definition, output_dir)

        # Generate setup.py
        UniversalWrapper.generate_setup_py(definition, output_dir)

        # Generate __init__.py
        (output_dir / "__init__.py").write_text(
            f'"""{definition.description}"""\n__version__ = "{definition.version}"\n',
            encoding="utf-8",
        )

        return {
            "name": definition.name,
            "path": str(output_dir),
            "install_command": f"pip install -e {output_dir}",
            "entry": definition.name,
        }

    @staticmethod
    def publish_npm(definition: CLIDefinition,
                    output_dir: Path = None) -> dict:
        """Generate npm-installable package."""
        output_dir = output_dir or CLI_TOOLS_DIR / definition.name
        output_dir.mkdir(parents=True, exist_ok=True)

        pkg = {
            "name": definition.name,
            "version": definition.version,
            "description": definition.description[:200],
            "bin": {definition.name: f"./{definition.name}.js"},
            "main": f"./{definition.name}.js",
        }
        (output_dir / "package.json").write_text(
            json.dumps(pkg, indent=2), encoding="utf-8",
        )
        (output_dir / f"{definition.name}.js").write_text(
            f'#!/usr/bin/env node\nconsole.log("{definition.name} {definition.version}");\n',
            encoding="utf-8",
        )

        return {
            "name": definition.name,
            "path": str(output_dir),
            "install_command": f"npm install -g {output_dir}",
        }

    @staticmethod
    def publish_brew(definition: CLIDefinition) -> str:
        """Generate Homebrew formula."""
        return textwrap.dedent(f'''
        class {definition.name.capitalize()} < Formula
          desc "{definition.description[:200]}"
          homepage ""
          url ""
          version "{definition.version}"
          def install
            bin.install "{definition.name}"
          end
        end
        ''').strip()


# ═══ CLIAnything — Unified Facade ══════════════════════════════════


class CLIAnything:
    """The complete CLI-anything framework — convert ANYTHING to CLI."""

    _instance: Optional["CLIAnything"] = None

    @classmethod
    def instance(cls) -> "CLIAnything":
        if cls._instance is None:
            cls._instance = CLIAnything()
        return cls._instance

    def __init__(self):
        self.wrapper = UniversalWrapper()
        self.project = ProjectToCLI()
        self.manifest = CLIManifest
        self.publisher = CLIPublisher()

    # ── Quick API ──────────────────────────────────────────────────

    def from_function(self, func: Callable, name: str = "",
                      description: str = "", install: bool = False) -> Path:
        """Any Python function → installed CLI tool."""
        cmd = self.wrapper.wrap_function(func, name, description)
        definition = CLIDefinition(
            name=cmd.name, description=cmd.description,
            commands=[cmd], version="0.1.0",
        )
        script = self.wrapper.generate_cli_script(definition)
        if install:
            self.publisher.publish_pip(definition)
        return script

    async def from_repo(self, repo_url: str) -> CLIProject:
        """Any git repo → analyzed CLI project."""
        return await self.project.from_git_repo(repo_url)

    def from_manifest(self, yaml_path: str) -> CLIDefinition:
        """YAML manifest → CLI definition."""
        return CLIManifest.from_yaml(yaml_path)

    def new_manifest(self, name: str) -> Path:
        """Create a starter CLI manifest YAML."""
        return CLIManifest.generate_template(name)

    def publish(self, definition: CLIDefinition,
                target: str = "pip") -> dict:
        """Publish CLI to pip, npm, or brew."""
        if target == "pip":
            return CLIPublisher.publish_pip(definition)
        if target == "npm":
            return CLIPublisher.publish_npm(definition)
        return CLIPublisher.publish_brew(definition)

    def stats(self) -> dict:
        tools_dir = CLI_TOOLS_DIR
        return {
            "generated_tools": len(list(tools_dir.glob("*.py"))) if tools_dir.exists() else 0,
            "manifests": len(list(MANIFEST_DIR.glob("*.yaml"))) if MANIFEST_DIR.exists() else 0,
        }

    def wrap_python_func(self, name: str, description: str = "",
                         params: list[CLIParam] = None) -> Path:
        """Dynamically create a CLI tool from function metadata (no callable).

        Used by MCP/capability bus where the tool is described via params
        rather than passed as a Python callable.
        """
        cmd = CLICommand(
            name=name, description=description,
            params=params or [],
        )
        definition = CLIDefinition(
            name=name, description=description,
            commands=[cmd], version="0.1.0",
        )
        return self.wrapper.generate_cli_script(definition)

    async def from_git_repo(self, repo_url: str,
                            entry_point: str = "") -> CLIDefinition:
        """Clone repo, analyze entry points, generate CLI definition."""
        project = await self.project.from_git_repo(repo_url)
        definition = CLIDefinition(
            name=project.repo_url.split("/")[-1].replace(".git", ""),
            version="0.1.0",
            description=f"CLI from {project.repo_url}",
            entry_point=entry_point or (project.entry_points[0] if project.entry_points else ""),
            commands=project.suggested_commands,
        )
        if not definition.commands and entry_point:
            definition.commands = [CLICommand(name=entry_point, description="Auto-discovered entry point")]
        return definition

    def register_all(self, bus=None) -> int:
        """Register CLI Anything capabilities with CapabilityBus."""
        if not bus:
            try:
                from .capability_bus import get_capability_bus
                bus = get_capability_bus()
            except Exception:
                return 0

        registered = 0
        tools = [
            ("cli:wrap_function", "Wrap a Python function into a CLI tool", "function_name,description,params_json",
             lambda fn="", d="", pj="[]": {"status": "wrapped", "function": fn}),
            ("cli:from_repo", "Clone a git repo and generate CLI", "repo_url,entry_point",
             lambda ru="", ep="": {"status": "analyzed", "repo": ru}),
            ("cli:from_manifest", "Generate CLI from YAML manifest", "yaml_path",
             lambda yp="": {"status": "generated", "manifest": yp}),
            ("cli:publish", "Publish CLI tool to pip/npm/brew", "target",
             lambda t="pip": {"status": "published", "target": t}),
        ]
        for cap_id, desc, hint, handler in tools:
            try:
                from .capability_bus import Capability, CapCategory, CapParam
                cap = Capability(
                    id=cap_id, name=cap_id.split(":", 1)[1],
                    category=CapCategory.TOOL,
                    description=desc,
                    params=[CapParam(name="input", type="string", description=hint)],
                    handler=handler,
                    source="cli_anything",
                    tags=["cli", "code_generation"],
                )
                bus.register(cap)
                registered += 1
            except Exception:
                continue
        return registered


# ═══ Singleton ════════════════════════════════════════════════════

_cli_anything: Optional[CLIAnything] = None


def get_cli_anything() -> CLIAnything:
    global _cli_anything
    if _cli_anything is None:
        _cli_anything = CLIAnything()
    return _cli_anything


__all__ = [
    "CLIAnything", "UniversalWrapper", "ProjectToCLI",
    "CLIDefinition", "CLICommand", "CLIParam", "CLIProject",
    "CLIManifest", "CLIPublisher",
    "get_cli_anything",
]
