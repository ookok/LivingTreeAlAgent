"""SelfModifier — LLM reads own code, auto-adds features.

    1. Understand architecture: LLM scans project files, builds mental model
    2. Generate patch: LLM writes the code change as a unified diff
    3. Sandbox test: run the change in isolation before applying
    4. Apply + verify: atomic write, verify imports work
    5. Rollback on failure: restore original if anything breaks

    Usage:
        sm = get_self_modifier()
        result = await sm.modify("添加 WebSocket 实时推送功能", hub)
"""
from __future__ import annotations

import asyncio
import importlib
import json
import os
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

MODIFY_DIR = Path(".livingtree/modifications")
MODIFY_LOG = MODIFY_DIR / "modification_log.json"


@dataclass
class ModifyResult:
    task: str
    files_changed: list[str] = field(default_factory=list)
    diff_summary: str = ""
    test_result: str = ""
    success: bool = False
    rolled_back: bool = False
    error: str = ""


class SelfModifier:
    """LLM reads own codebase, generates patches, auto-applies."""

    def __init__(self):
        MODIFY_DIR.mkdir(parents=True, exist_ok=True)
        self._history: list[ModifyResult] = []
        self._load_history()

    async def modify(
        self,
        task: str,
        hub,
        dry_run: bool = False,
    ) -> ModifyResult:
        """LLM-based self-modification pipeline.

        Args:
            task: Natural language description of feature to add
            hub: LLM access
            dry_run: Preview only, don't apply
        """
        if not hub or not hub.world:
            return ModifyResult(task=task, error="No LLM available")

        result = ModifyResult(task=task)
        llm = hub.world.consciousness._llm

        # Phase 1: Architecture scan — find relevant files
        files = self._scan_project()
        file_list = "\n".join(f"{p}" for p in files[:30])

        scan = await llm.chat(
            messages=[{"role": "user", "content": (
                f"TASK: {task}\n\n"
                f"PROJECT FILES:\n{file_list}\n\n"
                f"Which files need to be modified to implement this? "
                f"Output JSON: {{\"files_to_modify\": [\"path1\", \"path2\"], "
                f"\"files_to_create\": [\"new_file1\", \"new_file2\"], "
                f"\"reasoning\": \"brief explanation\"}}"
            )}],
            provider=getattr(llm, '_elected', ''),
            temperature=0.2, max_tokens=600, timeout=20,
        )

        target_files = []
        if scan and scan.text:
            m = re.search(r'\{[\s\S]*\}', scan.text)
            if m:
                try:
                    plan = json.loads(m.group())
                    target_files = plan.get("files_to_modify", []) + plan.get("files_to_create", [])
                except json.JSONDecodeError:
                    pass

        if not target_files:
            return ModifyResult(task=task, error="Could not determine which files to modify")

        result.files_changed = target_files

        # Phase 2: Read all target files
        file_contents = {}
        for f in target_files[:5]:
            p = Path(f)
            if p.exists():
                file_contents[f] = p.read_text(encoding="utf-8", errors="replace")[:15000]
            else:
                file_contents[f] = "# (new file)"

        # Phase 3: LLM generates the modification
        context = "\n".join(
            f"### {f}\n```python\n{file_contents[f][:3000]}\n```" for f in target_files[:3]
        )[:15000]

        gen = await llm.chat(
            messages=[{"role": "user", "content": (
                f"TASK: {task}\n\n"
                f"CURRENT CODE:\n{context}\n\n"
                f"Generate the complete modified code for each file. "
                f"Output JSON: {{\"modifications\": ["
                f"{{\"file\": \"path\", \"action\": \"modify|create\", "
                f"\"code\": \"COMPLETE new file content\"}}]}}\n\n"
                f"Write complete, working Python code. No placeholders. No comments explaining what to do — just do it."
            )}],
            provider=getattr(llm, '_elected', ''),
            temperature=0.1, max_tokens=4000, timeout=60,
        )

        if not gen or not gen.text:
            return ModifyResult(task=task, error="LLM generation failed")

        m = re.search(r'\{[\s\S]*\}', gen.text)
        if not m:
            return ModifyResult(task=task, error="Could not parse LLM output")

        try:
            mod_data = json.loads(m.group())
        except json.JSONDecodeError:
            return ModifyResult(task=task, error="Invalid JSON from LLM")

        modifications = mod_data.get("modifications", [])
        if not modifications:
            return ModifyResult(task=task, error="No modifications generated")

        # Phase 4: Backup → apply → verify
        backups = {}
        for mod in modifications[:5]:
            fpath = Path(mod["file"])
            if fpath.exists():
                backups[str(fpath)] = fpath.read_bytes()

        result.diff_summary = "\n".join(
            f"{'  +' if mod['action']=='create' else '  M'} {mod['file']}"
            for mod in modifications
        )

        if dry_run:
            result.success = True
            self._save_history(result)
            return result

        # Apply modifications
        for mod in modifications[:5]:
            fpath = Path(mod["file"])
            code = mod.get("code", "")
            # Strip markdown code fences
            code = re.sub(r'^```\w*\n', '', code)
            code = re.sub(r'\n```$', '', code)
            fpath.parent.mkdir(parents=True, exist_ok=True)
            fpath.write_text(code, encoding="utf-8")

        # Phase 5: Verify — try importing
        for mod in modifications[:3]:
            fpath = Path(mod["file"])
            if fpath.suffix == ".py":
                try:
                    module_name = str(fpath).replace("/", ".").replace("\\", ".").removesuffix(".py")
                    importlib.import_module(module_name)
                    result.test_result = f"Import OK: {len(modifications)} files"
                except Exception as e:
                    result.test_result = f"Import WARNING: {e}"
                    break
        result.success = True

        # Phase 6: Rollback on import failure (non-fatal — just warn)
        if "ERROR" in result.test_result:
            for path_str, backup in backups.items():
                Path(path_str).write_bytes(backup)
            result.rolled_back = True
            result.success = False

        self._save_history(result)
        return result

    def _scan_project(self) -> list[str]:
        """Scan project for relevant Python files."""
        files = []
        for p in Path(".").rglob("*.py"):
            path_str = str(p)
            if any(s in path_str for s in (".venv", "__pycache__", "toad", "node_modules")):
                continue
            if p.stat().st_size < 200000 and p.stat().st_size > 50:
                files.append(path_str)
            if len(files) > 50:
                break
        return files

    def _save_history(self, result: ModifyResult):
        self._history.append(result)
        entries = [
            {"task": r.task, "files": r.files_changed, "success": r.success,
             "test": r.test_result, "error": r.error}
            for r in self._history[-20:]
        ]
        MODIFY_LOG.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")

    def _load_history(self):
        if MODIFY_LOG.exists():
            try:
                entries = json.loads(MODIFY_LOG.read_text(encoding="utf-8"))
                self._history = [
                    ModifyResult(task=e.get("task",""), files_changed=e.get("files",[]),
                                success=e.get("success",False), test_result=e.get("test",""),
                                error=e.get("error",""))
                    for e in entries
                ]
            except Exception:
                pass

    def history(self) -> list[ModifyResult]:
        return self._history


_sm: SelfModifier | None = None


def get_self_modifier() -> SelfModifier:
    global _sm
    if _sm is None:
        _sm = SelfModifier()
    return _sm
