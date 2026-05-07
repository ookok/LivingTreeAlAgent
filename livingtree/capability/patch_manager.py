"""PatchManager — generate, apply, and revert .patch files with LLM assistance.

    1. Generate patch: diff before/after → unified diff → .patch file
    2. Apply patch: patch -p1 < file.patch (cross-platform)
    3. LLM patch: LLM reads file + instruction → outputs unified diff
    4. Revert: backup before patch → restore on failure
    5. Stack: named patch stack for multi-step changes

    Usage:
        pm = get_patch_manager()
        patch = await pm.generate("file.py", "old", "new", name="fix-port")
        await pm.apply("patches/fix-port.patch")
        await pm.revert("patches/fix-port.patch")  # restore backup
"""
from __future__ import annotations

import difflib
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

PATCH_DIR = Path(".livingtree/patches")


@dataclass
class PatchResult:
    name: str
    path: Path
    patch_path: Path | None = None
    backup_path: Path | None = None
    applied: bool = False
    reverted: bool = False
    files_changed: list[str] = field(default_factory=list)
    lines_added: int = 0
    lines_removed: int = 0
    error: str = ""


class PatchManager:
    """Generate/apply/revert unified diff patches."""

    def __init__(self):
        PATCH_DIR.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        filepath: str | Path,
        original_content: str,
        new_content: str,
        name: str = "",
    ) -> PatchResult:
        """Create a .patch file from before/after content.

        Args:
            filepath: The file being patched
            original_content: Original file content
            new_content: New file content  
            name: Patch name (auto: timestamp based)
        """
        filepath = Path(filepath)
        name = name or f"patch_{int(time.time())}_{filepath.name}"
        safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)
        patch_path = PATCH_DIR / f"{safe_name}.patch"

        diff = difflib.unified_diff(
            original_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=str(filepath),
            tofile=str(filepath),
        )

        patch_content = "".join(diff)
        if not patch_content.strip():
            return PatchResult(name=safe_name, path=filepath, error="No changes detected")

        patch_path.write_text(patch_content, encoding="utf-8")

        lines_added = patch_content.count("\n+") - patch_content.count("+++")
        lines_removed = patch_content.count("\n-") - patch_content.count("---")

        return PatchResult(
            name=safe_name, path=filepath, patch_path=patch_path,
            lines_added=lines_added, lines_removed=lines_removed,
        )

    def apply(self, patch_path: str | Path, target_dir: str | Path = ".") -> PatchResult:
        """Apply a .patch file with atomic multi-file modification.

        Crash-safe: all-or-nothing via disk-persistent backup.
        """
        from ..core.atomic_modification import AtomicModification

        patch_path = Path(patch_path)
        target_dir = Path(target_dir)

        if not patch_path.exists():
            return PatchResult(name=patch_path.stem, path=patch_path, error="Patch file not found")

        result = PatchResult(name=patch_path.stem, path=patch_path)

        patch_text = patch_path.read_text(encoding="utf-8")
        affected = self._parse_patch_files(patch_text)
        result.files_changed = affected

        edits = {}
        for f in affected:
            fpath = target_dir / f
            if not fpath.exists():
                continue
            hunks = self._extract_hunks_for_file(patch_text, f)
            if hunks:
                original = fpath.read_text(encoding="utf-8")
                new_text = self._apply_hunks(original, hunks)
                if new_text != original:
                    edits[str(fpath)] = new_text
                    result.lines_added += sum(h["added"] for h in hunks)
                    result.lines_removed += sum(h["removed"] for h in hunks)

        if not edits:
            result.error = "No hunks applied"
            return result

        with AtomicModification(edits, reason=f"Patch: {patch_path.stem}") as atom:
            atom.validate()
            apply_result = atom.apply()
            if apply_result.success:
                atom.commit()
                result.applied = True
            else:
                result.error = "; ".join(apply_result.errors)

        return result

    def revert(self, patch_path: str | Path, target_dir: str | Path = ".") -> PatchResult:
        """Revert a previously applied patch by restoring backups.

        Args:
            patch_path: Original patch file (backups are auto-located)
            target_dir: Working directory
        """
        patch_path = Path(patch_path)
        target_dir = Path(target_dir)
        result = PatchResult(name=patch_path.stem, path=patch_path)

        restored = 0
        for bak in PATCH_DIR.glob(f"{patch_path.stem}_*.bak"):
            orig_name = bak.stem.replace(f"{patch_path.stem}_", "")
            dest = target_dir / orig_name
            shutil.copy2(bak, dest)
            restored += 1
            logger.debug(f"Restored {bak} → {dest}")

        if restored:
            # Clean up backups
            for bak in PATCH_DIR.glob(f"{patch_path.stem}_*.bak"):
                bak.unlink(missing_ok=True)
            result.reverted = True
        else:
            result.error = "No backup files found to revert"

        return result

    async def llm_patch(
        self,
        filepath: str | Path,
        instruction: str,
        hub,
        name: str = "",
    ) -> PatchResult:
        """LLM reads file + instruction → generates unified diff patch.

        Args:
            filepath: File to modify
            instruction: What to change (natural language)
            hub: LLM access
            name: Patch name
        """
        filepath = Path(filepath)
        if not filepath.exists():
            return PatchResult(name=name, path=filepath, error="File not found")

        llm = hub.world.consciousness._llm
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read(20000)

        try:
            result = await llm.chat(
                messages=[{"role": "user", "content": (
                    "You are a code patcher. Read the file and instruction, "
                    "output the MODIFIED file content (the full file after changes).\n\n"
                    f"FILE: {filepath}\n\n```\n{content[:10000]}\n```\n\n"
                    f"INSTRUCTION: {instruction}\n\n"
                    "Output ONLY the complete modified file content. No explanation."
                )}],
                provider=getattr(llm, '_elected', ''),
                temperature=0.1, max_tokens=4000, timeout=30,
            )
            if result and result.text:
                new_text = result.text.strip()
                new_text = new_text.replace("```", "").strip()
                return self.generate(filepath, content, new_text, name)
        except Exception as e:
            logger.debug(f"LLM patch: {e}")

        return PatchResult(name=name, path=filepath, error="LLM failed")

    def list_patches(self) -> list[PatchResult]:
        """List all saved patches."""
        results = []
        for p in sorted(PATCH_DIR.glob("*.patch"), key=os.path.getmtime, reverse=True):
            text = p.read_text(encoding="utf-8", errors="replace")
            added = text.count("\n+") - text.count("+++")
            removed = text.count("\n-") - text.count("---")
            results.append(PatchResult(
                name=p.stem, path=p, lines_added=added, lines_removed=removed,
            ))
        return results

    def _parse_patch_files(self, patch_text: str) -> list[str]:
        """Extract file paths from unified diff headers."""
        files = []
        for m in __import__('re').findall(r'^[+]{3} (.+)', patch_text, re.MULTILINE):
            import re
            f = m.strip().replace("b/", "", 1).replace("a/", "", 1)
            if f and f not in ("/dev/null", "none"):
                files.append(f)
        return list(set(files))

    def _extract_hunks_for_file(self, patch_text: str, filename: str) -> list[dict]:
        """Parse unified diff hunks for a specific file."""
        hunks = []
        lines = patch_text.splitlines()
        in_hunk = False
        current = None
        hunk_lines = []

        for line in lines:
            if line.startswith("--- a/") or line.startswith("+++ b/"):
                if filename in line:
                    in_hunk = True
                else:
                    in_hunk = False
                continue
            if line.startswith("--- ") or line.startswith("+++ "):
                in_hunk = False
                if current:
                    hunks.append(current)
                current = None
                continue
            if in_hunk and line.startswith("@@"):
                from_file = re.search(r'-(\d+)(?:,(\d+))?', line)
                to_file = re.search(r'\+(\d+)(?:,(\d+))?', line)
                if current:
                    hunks.append(current)
                current = {
                    "old_start": int(from_file.group(1)) if from_file else 0,
                    "old_count": int(from_file.group(2) or 1) if from_file else 0,
                    "new_start": int(to_file.group(1)) if to_file else 0,
                    "new_count": int(to_file.group(2) or 1) if to_file else 0,
                    "lines": [],
                    "added": 0,
                    "removed": 0,
                }
            elif in_hunk and current is not None:
                current["lines"].append(line)
                if line.startswith("+") and not line.startswith("+++"):
                    current["added"] += 1
                elif line.startswith("-") and not line.startswith("---"):
                    current["removed"] += 1

        if current:
            hunks.append(current)
        return hunks

    def _apply_hunks(self, text: str, hunks: list[dict]) -> str:
        """Apply diff hunks to text (simplified, line-oriented)."""
        lines = text.splitlines()
        # Process hunks in reverse order to preserve line numbers
        for hunk in reversed(hunks):
            old_start = max(0, hunk["old_start"] - 1)
            old_end = old_start + hunk["old_count"]
            new_lines = []
            for l in hunk["lines"]:
                if l.startswith("+") and not l.startswith("+++"):
                    new_lines.append(l[1:])
                elif not l.startswith("-"):
                    new_lines.append(l[1:] if l.startswith(" ") else l)
            lines[old_start:old_end] = new_lines
        return "\n".join(lines) + ("\n" if text.endswith("\n") else "")

    def _rollback_last(self, patch_path: Path, target_dir: Path):
        """Restore the most recent backup for each file."""
        for bak in PATCH_DIR.glob(f"{patch_path.stem}_*.bak"):
            orig_name = bak.stem.replace(f"{patch_path.stem}_", "")
            dest = target_dir / orig_name
            if bak.exists() and dest.parent.exists():
                shutil.copy2(bak, dest)


import re as _re

_pm: PatchManager | None = None


def get_patch_manager() -> PatchManager:
    global _pm
    if _pm is None:
        _pm = PatchManager()
    return _pm
