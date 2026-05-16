"""AutoSkillResolver — when an agent lacks a needed skill/tool, auto-create it.

Handles 3 scenarios:
  1. Missing Python tool → generate code via LLM → scan → test → register
  2. Missing external CLI → auto-install via pkg_manager → register wrapper
  3. Missing knowledge → search web → ingest → create skill from learned content

Integrates with RealPipeline: if any agent step fails with "skill not found",
this resolver automatically creates the missing capability and retries.
"""
from __future__ import annotations

import ast
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

SKILLS_DIR = Path(".livingtree/auto_skills")


@dataclass
class ResolvedSkill:
    name: str
    type: str  # "python_function", "cli_wrapper", "knowledge_skill"
    description: str
    source: str  # "llm_generated", "pkg_installed", "web_learned"
    handler: Any | None = None
    created_at: float = field(default_factory=time.time)
    used_count: int = 0


class AutoSkillResolver:
    """Auto-creates missing skills and tools for agents."""

    def __init__(self, hub=None):
        self._hub = hub
        self._resolved: dict[str, ResolvedSkill] = {}
        self._load()

    # ═══ Detection ═══

    def detect_missing(self, agent_output: str, task_desc: str) -> list[str]:
        """Detect what skills/tools the agent says it needs but doesn't have."""
        needed = []

        # Pattern 1: "需要 XX 工具/库/skill"
        patterns = [
            r'需要\s+(\S+)\s*(?:工具|库|模块|skill)',
            r'缺少\s+(\S+)\s*(?:工具|库|模块|skill)',
            r'(?:need|require|missing)\s+(\S+)\s*(?:tool|library|module|skill)',
            r'(?:pip|npm|uv)\s+install\s+(\S+)',
        ]
        for pat in patterns:
            for m in re.finditer(pat, agent_output, re.IGNORECASE):
                name = m.group(1).strip().strip("'\"`")
                if name and name not in needed:
                    needed.append(name)

        # If agent explicitly says it can't do something
        cant_patterns = [
            r'无法(?:执行|完成|处理)\s*(\S+)',
            r'(?:cannot|unable to)\s+(\S+)',
        ]
        for pat in cant_patterns:
            for m in re.finditer(pat, agent_output, re.IGNORECASE):
                name = m.group(1).strip()
                if name and name not in needed:
                    needed.append(name)

        return needed

    # ═══ Resolution ═══

    async def resolve(self, skill_name: str, task_context: str = "") -> ResolvedSkill | None:
        """Auto-create or install a missing skill."""

        # Already resolved?
        if skill_name in self._resolved:
            skill = self._resolved[skill_name]
            skill.used_count += 1
            return skill

        # Strategy 1: Try pip install
        if self._looks_like_pip_package(skill_name):
            result = await self._install_package(skill_name)
            if result:
                return result

        # Strategy 2: Generate Python function via LLM
        if self._hub and self._hub.world:
            result = await self._generate_code(skill_name, task_context)
            if result:
                return result

        # Strategy 3: Search web + create knowledge skill
        if self._hub:
            result = await self._learn_from_web(skill_name, task_context)
            if result:
                return result

        return None

    def _looks_like_pip_package(self, name: str) -> bool:
        return bool(re.match(r'^[a-zA-Z][a-zA-Z0-9_-]+$', name)) and len(name) >= 3

    async def _install_package(self, name: str) -> ResolvedSkill | None:
        """Install via pip and wrap as a skill."""
        try:
            from ..integration.pkg_manager import install as pkg_install
            result = pkg_install(name, providers=["pip"])
            if result.installed:
                skill = ResolvedSkill(
                    name=name, type="cli_wrapper", description=f"Installed via pip: {name}",
                    source="pkg_installed",
                )
                self._resolved[name] = skill
                self._save()
                logger.info(f"Auto-installed: {name}")
                return skill
        except Exception as e:
            logger.debug(f"Install {name}: {e}")
        return None

    async def _generate_code(self, name: str, context: str) -> ResolvedSkill | None:
        """Generate a Python function via LLM to fulfill the missing capability."""
        if not self._hub or not self._hub.world:
            return None

        try:
            llm = self._hub.world.consciousness._llm
            result = await llm.chat(
                messages=[{"role": "user", "content": (
                    f"Write a self-contained Python function named '{name}' "
                    f"that handles this task: {context[:200]}. "
                    "Output ONLY the function code, with imports. No explanation."
                )}],
                provider=getattr(llm, '_elected', ''),
                temperature=0.2,
                max_tokens=1000,
                timeout=20,
            )
            if result and result.text and "def " in result.text:
                code = result.text.strip()
                m = re.search(r'```(?:python)?\s*\n?(.*?)\n?```', code, re.DOTALL)
                if m:
                    code = m.group(1)

                # AST security scan: reject dangerous code
                scan = self._scan_code(code, name)
                if not scan["safe"]:
                    logger.warning(f"Skill '{name}' rejected by AST scan: {scan['reason']}")
                    return None

                SKILLS_DIR.mkdir(parents=True, exist_ok=True)
                filepath = SKILLS_DIR / f"{name}.py"
                filepath.write_text(code, encoding="utf-8")

                skill = ResolvedSkill(
                    name=name, type="python_function", description=context[:120],
                    source="llm_generated",
                )
                self._resolved[name] = skill
                self._save()
                logger.info(f"Auto-generated skill: {name}")
                return skill
        except Exception as e:
            logger.debug(f"Generate {name}: {e}")
        return None

    # ═══ AST Security Scan ═══

    DANGEROUS_IMPORTS = {"os", "subprocess", "socket", "shutil", "ctypes",
                          "signal", "multiprocessing", "threading", "pty",
                          "fcntl", "posix", "eval", "exec", "compile",
                          "__import__", "importlib", "pickle", "marshal"}

    DANGEROUS_CALLS = {"eval", "exec", "compile", "__import__",
                       "os.system", "os.popen", "os.execl", "os.execle",
                       "os.execlp", "os.execlpe", "os.execv", "os.execve",
                       "os.execvp", "os.execvpe", "os.spawnl", "os.spawnle",
                       "os.spawnlp", "os.spawnlpe", "os.spawnv", "os.spawnve",
                       "os.spawnvp", "os.spawnvpe", "subprocess.call",
                       "subprocess.Popen", "subprocess.run", "subprocess.check_call",
                       "subprocess.check_output"}

    def _scan_code(self, code: str, name: str) -> dict:
        """AST-based security scan of LLM-generated code.

        Returns: {"safe": bool, "reason": str, "warnings": list}
        """
        try:
            tree = ast.parse(code, filename=f"<auto_skill:{name}>")
        except SyntaxError as e:
            return {"safe": False, "reason": f"Syntax error: {e}", "warnings": []}

        warnings = []
        imports = []

        class _Scanner(ast.NodeVisitor):
            def visit_Import(self, node):
                for alias in node.names:
                    base = alias.name.split(".")[0]
                    imports.append(base)
                    if base in AutoSkillResolver.DANGEROUS_IMPORTS:
                        warnings.append(f"Dangerous import: {alias.name}")
                self.generic_visit(node)

            def visit_ImportFrom(self, node):
                if node.module:
                    base = node.module.split(".")[0]
                    imports.append(base)
                    if base in AutoSkillResolver.DANGEROUS_IMPORTS:
                        warnings.append(f"Dangerous import: {node.module}")
                self.generic_visit(node)

            def visit_Call(self, node):
                if isinstance(node.func, ast.Attribute):
                    chain = self._get_attr_chain(node.func)
                    if chain in AutoSkillResolver.DANGEROUS_CALLS:
                        warnings.append(f"Dangerous call: {chain}()")
                elif isinstance(node.func, ast.Name):
                    if node.func.id in AutoSkillResolver.DANGEROUS_CALLS:
                        warnings.append(f"Dangerous call: {node.func.id}()")
                self.generic_visit(node)

            def _get_attr_chain(self, node):
                parts = []
                while isinstance(node, ast.Attribute):
                    parts.append(node.attr)
                    node = node.value
                if isinstance(node, ast.Name):
                    parts.append(node.id)
                return ".".join(reversed(parts))

        _Scanner().visit(tree)

        if warnings:
            return {"safe": False, "reason": "; ".join(warnings[:3]), "warnings": warnings}

        return {"safe": True, "reason": "", "warnings": [], "imports": imports}

    async def _learn_from_web(self, name: str, context: str) -> ResolvedSkill | None:
        """Search the web and create a knowledge-based skill."""
        try:
            from ..capability.unified_search import get_unified_search
            search = get_unified_search()
            results = await search.query(f"{name} {context[:100]}", limit=3)
            if results:
                knowledge = "\n".join(f"- {r.title}: {r.summary[:200]}" for r in results[:3])
                skill = ResolvedSkill(
                    name=name, type="knowledge_skill",
                    description=f"Web-learned: {knowledge[:300]}",
                    source="web_learned",
                )
                self._resolved[name] = skill
                self._save()
                logger.info(f"Web-learned skill: {name}")
                return skill
        except Exception as e:
            logger.debug(f"Learn {name}: {e}")
        return None

    # ═══ Retry ═══

    async def retry_with_resolved(self, step_func, task_context: str, max_attempts: int = 2) -> str:
        """Run a task step; if it fails due to missing skills, resolve and retry."""
        for attempt in range(max_attempts):
            try:
                result = await step_func()
                # Check if result indicates missing skills
                if isinstance(result, str):
                    missing = self.detect_missing(result, task_context)
                    if missing:
                        for m in missing:
                            resolved = await self.resolve(m, task_context)
                            if resolved:
                                logger.info(f"Resolved missing skill '{m}' → {resolved.type}")
                        if attempt < max_attempts - 1:
                            continue  # Retry after resolving
                return result
            except Exception as e:
                if attempt < max_attempts - 1:
                    err_str = str(e)
                    missing = self.detect_missing(err_str, task_context)
                    for m in missing:
                        await self.resolve(m, task_context)
                else:
                    raise
        return "All attempts failed"

    # ═══ Persistence ═══

    def get_all(self) -> list[ResolvedSkill]:
        return list(self._resolved.values())

    def _save(self):
        try:
            SKILLS_DIR.mkdir(parents=True, exist_ok=True)
            import json
            (SKILLS_DIR / "registry.json").write_text(json.dumps({
                name: {"name": s.name, "type": s.type, "description": s.description,
                       "source": s.source, "created_at": s.created_at, "used_count": s.used_count}
                for name, s in self._resolved.items()
            }, indent=2, ensure_ascii=False))
        except Exception:
            pass

    def _load(self):
        try:
            reg = SKILLS_DIR / "registry.json"
            if reg.exists():
                import json
                data = json.loads(reg.read_text())
                for d in data.values():
                    s = ResolvedSkill(**d)
                    self._resolved[s.name] = s
        except Exception:
            pass


# ═══ Global ═══

_resolver: AutoSkillResolver | None = None


def get_resolver(hub=None) -> AutoSkillResolver:
    global _resolver
    if _resolver is None or hub:
        _resolver = AutoSkillResolver(hub)
    return _resolver
