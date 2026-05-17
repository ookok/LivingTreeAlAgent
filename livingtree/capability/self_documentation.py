"""SelfDocumentation — auto-generate system docs from runtime state + history.

    Like a README that writes itself:
    1. Feature timeline: what was added when (from git log + consolidation)
    2. Provider stats: most-used providers with cache hit rates
    3. Tool inventory: all registered tools with success rates
    4. Architecture diagram: auto-generated from file tree + imports
    5. Known issues: from error logs + trust scores below threshold
    6. Security recommendations: from trust scoring posture

    Usage:
        sdoc = get_self_documenter()
        docs = await sdoc.generate(hub)
        # Writes to .livingtree/self_docs/

    Command:
        /selfdocs — generate full system documentation
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

DOCS_DIR = Path(".livingtree/self_docs")


@dataclass
class SelfDocument:
    title: str = "LivingTree System Documentation"
    generated_at: float = 0.0
    feature_timeline: str = ""
    provider_stats: str = ""
    tool_inventory: str = ""
    architecture: str = ""
    known_issues: str = ""
    security: str = ""
    full_markdown: str = ""


class SelfDocumenter:
    """Auto-generate comprehensive system documentation."""

    def __init__(self):
        DOCS_DIR.mkdir(parents=True, exist_ok=True)

    async def generate(self, hub) -> SelfDocument:
        """Generate full system documentation.

        Runs all sections and assembles a complete markdown document.
        """
        doc = SelfDocument(generated_at=time.time())
        if not hub or not hub.world:
            return doc

        llm = hub.world.consciousness._llm
        provider_override = getattr(llm, '_elected', '')

        # Gather raw data
        git_log = self._git_log(30)
        tool_list = self._gather_tools()
        trust_data = self._gather_trust()
        feed_summary = self._gather_activity()
        files = self._scan_structure()

        # Generate each section via LLM
        sections = []
        tasks = {
            "feature_timeline": self._gen_feature_timeline(llm, provider_override, git_log, feed_summary),
            "provider_stats": self._gen_provider_stats(llm, provider_override),
            "tool_inventory": self._gen_tool_inventory(llm, provider_override, tool_list, trust_data),
            "architecture": self._gen_architecture(llm, provider_override, files),
            "known_issues": self._gen_issues(llm, provider_override, trust_data, feed_summary),
            "security": self._gen_security(llm, provider_override, trust_data),
        }

        import asyncio
        results = await asyncio.gather(*tasks.values())
        for key, result in zip(tasks.keys(), results):
            setattr(doc, key, result)

        # Assemble markdown
        doc.title = f"LivingTree 系统文档 — {time.strftime('%Y-%m-%d %H:%M')}"
        sections_blocks = [
            doc.feature_timeline,
            doc.provider_stats,
            doc.tool_inventory,
            doc.architecture,
            doc.known_issues,
            doc.security,
        ]
        doc.full_markdown = "\n\n---\n\n".join(s for s in sections_blocks if s)

        # Save
        fname = time.strftime("%Y%m%d_%H%M%S")
        (DOCS_DIR / f"{fname}.md").write_text(
            f"# {doc.title}\n\n{doc.full_markdown}",
            encoding="utf-8",
        )
        logger.info(f"Self-documentation generated: {fname}.md")

        return doc

    async def _gen_feature_timeline(self, llm, provider, git_log: str, feed: str) -> str:
        try:
            r = await llm.chat(
                messages=[{"role": "user", "content": (
                    "Generate a feature timeline from this project's git history "
                    "and activity log. Group by date, list new features added.\n\n"
                    "GIT LOG:\n" + git_log[-3000:] + "\n\n"
                    "ACTIVITY:\n" + feed[-2000:] + "\n\n"
                    "Output markdown with ## heading and bullet timeline."
                )}],
                provider=provider, temperature=0.2, max_tokens=800, timeout=20,
            )
            return r.text.strip() if r and r.text else ""
        except Exception:
            return ""

    async def _gen_provider_stats(self, llm, provider) -> str:
        try:
            from ..bridge.registry import get_tool_registry  # TODO(bridge): via bridge.LLMProtocol
            cd = get_tool_registry().get('cache_director')
            stats = cd.all_stats()
            stats_str = json.dumps(stats, indent=2, ensure_ascii=False)

            r = await llm.chat(
                messages=[{"role": "user", "content": (
                    "Based on these provider cache statistics, write a usage report.\n\n"
                    "DATA:\n" + stats_str[:3000] + "\n\n"
                    "Output markdown: ## Provider Usage + table of top providers."
                )}],
                provider=provider, temperature=0.1, max_tokens=600, timeout=15,
            )
            return r.text.strip() if r and r.text else ""
        except Exception:
            return ""

    async def _gen_tool_inventory(self, llm, provider, tools: str, trust: str) -> str:
        try:
            r = await llm.chat(
                messages=[{"role": "user", "content": (
                    f"Summarize the tool inventory and trust scores.\n\n"
                    f"TOOLS:\n{tools[:4000]}\n\nTRUST:\n{trust[:2000]}\n\n"
                    "Output markdown: ## Tool Inventory + categorized table."
                )}],
                provider=provider, temperature=0.2, max_tokens=800, timeout=20,
            )
            return r.text.strip() if r and r.text else ""
        except Exception:
            return ""

    async def _gen_architecture(self, llm, provider, files: str) -> str:
        try:
            r = await llm.chat(
                messages=[{"role": "user", "content": (
                    f"Describe the project architecture based on this file structure.\n\n"
                    f"FILES:\n{files[:4000]}\n\n"
                    "Output markdown: ## Architecture + ASCII diagram + module descriptions."
                )}],
                provider=provider, temperature=0.2, max_tokens=800, timeout=20,
            )
            return r.text.strip() if r and r.text else ""
        except Exception:
            return ""

    async def _gen_issues(self, llm, provider, trust: str, feed: str) -> str:
        try:
            r = await llm.chat(
                messages=[{"role": "user", "content": (
                    f"List known issues from trust scores and error logs.\n\n"
                    f"TRUST:\n{trust[:2000]}\n\nACTIVITY:\n{feed[-2000:]}\n\n"
                    "Output markdown: ## Known Issues + bullet list."
                )}],
                provider=provider, temperature=0.1, max_tokens=500, timeout=15,
            )
            return r.text.strip() if r and r.text else ""
        except Exception:
            return ""

    async def _gen_security(self, llm, provider, trust: str) -> str:
        try:
            r = await llm.chat(
                messages=[{"role": "user", "content": (
                    f"Generate security recommendations based on trust scores.\n\n"
                    f"TRUST DATA:\n{trust[:2000]}\n\n"
                    "Output markdown: ## Security + recommendations."
                )}],
                provider=provider, temperature=0.1, max_tokens=400, timeout=15,
            )
            return r.text.strip() if r and r.text else ""
        except Exception:
            return ""

    def _git_log(self, n: int = 30) -> str:
        import asyncio
        try:
            from ..treellm.unified_exec import git
            result = asyncio.run(git(f"log -{n} --oneline --decorate --date=short", timeout=10))
            return result.stdout
        except ImportError:
            try:
                r = subprocess.run(
                    ["git", "log", f"-{n}", "--oneline", "--decorate", "--date=short"],
                    capture_output=True, text=True, timeout=10,
                    encoding="utf-8", errors="replace",
                )
                return r.stdout
            except Exception:
                return ""
        except Exception:
            return ""

    def _gather_tools(self) -> str:
        try:
            from ..core.unified_registry import get_registry
            reg = get_registry()
            lines = []
            for name, tool in reg.tools.items():
                lines.append(f"- {name} [{tool.category}]: {tool.description}")
            return "\n".join(lines)
        except Exception:
            return ""

    def _gather_trust(self) -> str:
        try:
            from ..core.system_health import get_trust_scorer
            ts = get_trust_scorer()
            return json.dumps(ts.summary(), indent=2, ensure_ascii=False)
        except Exception:
            return ""

    def _gather_activity(self) -> str:
        try:
            from ..observability.activity_feed import get_activity_feed
            feed = get_activity_feed()
            return feed.summary_24h()
        except Exception:
            return ""

    def _scan_structure(self) -> str:
        lines = []
        try:
            for root, dirs, files in os.walk("livingtree"):
                dirs[:] = [d for d in dirs if d not in ("__pycache__", ".venv", "td")]
                level = root.replace("livingtree", "").count(os.sep)
                indent = "  " * level
                lines.append(f"{indent}{os.path.basename(root)}/")
                for f in sorted(files)[:10]:
                    lines.append(f"{indent}  {f}")
                if len(files) > 10:
                    lines.append(f"{indent}  ... ({len(files)} files)")
                if len(lines) > 50:
                    break
        except Exception:
            pass
        return "\n".join(lines)


_sdoc: SelfDocumenter | None = None


def get_self_documenter() -> SelfDocumenter:
    global _sdoc
    if _sdoc is None:
        _sdoc = SelfDocumenter()
    return _sdoc
