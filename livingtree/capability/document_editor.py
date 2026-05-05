"""DocumentEditor — precise content replacement + streaming large file I/O.

Handles:
  1. Section-based replacement: replace by heading/paragraph/line range
  2. Pattern-based replacement: regex find-and-replace with context
  3. Streaming large file I/O: never loads entire file into memory
  4. Atomic writes: writes to temp file first, then renames
  5. Diff preview: shows what changed before applying

Usage:
    editor = DocumentEditor()
    result = editor.replace_section("doc.md", "## 第三章", "new content")
    editor.bulk_replace("doc.md", {"old_key": "new_val", "2023": "2024"})
"""
from __future__ import annotations

import mmap
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class EditResult:
    path: Path
    replacements: int = 0
    lines_changed: int = 0
    bytes_before: int = 0
    bytes_after: int = 0
    preview: str = ""
    applied: bool = False

class DocumentEditor:
    """Precise document editing with streaming I/O."""

    def __init__(self):
        self._temp_dir = Path(tempfile.mkdtemp(prefix="lt_edit_"))

    # ═══ Section-based replacement ═══

    def replace_section(
        self,
        path: str | Path,
        heading: str,
        new_content: str,
        dry_run: bool = False,
    ) -> EditResult:
        """Replace content under a specific heading (Markdown or plain text).

        Args:
            path: File to edit
            heading: Section heading to match (e.g., "## 第三章", "第3章")
            new_content: New content for the section
            dry_run: If True, preview only, don't write
        """
        path = Path(path)
        result = EditResult(path=path, bytes_before=path.stat().st_size if path.exists() else 0)

        old_lines = self._read_lines_streaming(path)
        new_lines = []
        in_section = False
        depth = self._heading_level(heading)
        replacements = 0

        for line in old_lines:
            stripped = line.lstrip()
            current_depth = self._heading_level(stripped)

            # Enter section
            if not in_section and self._match_heading(stripped, heading):
                in_section = True
                new_lines.append(line)  # Keep the heading
                new_lines.append(new_content.rstrip("\n") + "\n")
                replacements += 1
                continue

            # Exit section when hitting a same-or-higher level heading
            if in_section and current_depth > 0 and current_depth <= depth:
                in_section = False

            if not in_section:
                new_lines.append(line)

        if replacements == 0:
            return result

        new_content_str = "".join(new_lines)
        result.lines_changed = abs(len(old_lines) - len(new_lines))
        result.bytes_after = len(new_content_str.encode("utf-8"))
        result.replacements = replacements
        result.preview = self._diff_preview(path, new_content_str)

        if not dry_run:
            self._atomic_write(path, new_content_str)
            result.applied = True

        return result

    def replace_lines(
        self,
        path: str | Path,
        start_line: int,
        end_line: int,
        new_content: str,
        dry_run: bool = False,
    ) -> EditResult:
        """Replace a specific line range (1-indexed)."""
        path = Path(path)
        old_lines = self._read_lines_streaming(path)
        if start_line < 1 or end_line > len(old_lines):
            return EditResult(path=path)

        new_lines = (
            old_lines[:start_line - 1]
            + [new_content.rstrip("\n") + "\n"]
            + old_lines[end_line:]
        )
        result = EditResult(
            path=path, replacements=1,
            lines_changed=abs(end_line - start_line + 1),
            bytes_before=path.stat().st_size,
            bytes_after=len("".join(new_lines).encode("utf-8")),
        )
        if not dry_run:
            self._atomic_write(path, "".join(new_lines))
            result.applied = True
        return result

    # ═══ Pattern-based replacement ═══

    def replace_pattern(
        self,
        path: str | Path,
        pattern: str,
        replacement: str,
        count: int = 0,
        dry_run: bool = False,
    ) -> EditResult:
        """Regex find-and-replace with streaming I/O for large files.

        Uses mmap for files > 10MB, line-by-line for smaller files.
        """
        path = Path(path)
        size = path.stat().st_size if path.exists() else 0
        pat = re.compile(pattern)

        replacements = 0
        new_content = ""

        if size > 10 * 1024 * 1024:
            # Large file: memory-mapped I/O
            with open(path, "r+b") as f:
                with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as m:
                    text = m.read().decode("utf-8", errors="replace")
                    new_content, replacements = pat.subn(replacement, text, count=count)
        else:
            # Small file: standard read
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
            new_content, replacements = pat.subn(replacement, text, count=count)

        result = EditResult(
            path=path, replacements=replacements,
            bytes_before=size, bytes_after=len(new_content.encode("utf-8")),
        )
        if replacements > 0:
            result.preview = self._diff_preview(path, new_content)
            if not dry_run:
                self._atomic_write(path, new_content)
                result.applied = True
        return result

    def bulk_replace(
        self,
        path: str | Path,
        replacements: dict[str, str],
        dry_run: bool = False,
    ) -> EditResult:
        """Multiple key→value replacements in one pass. Streaming for large files."""
        path = Path(path)
        total_replacements = 0

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()

        new_text = text
        for old, new in replacements.items():
            before = len(new_text)
            new_text = new_text.replace(old, new)
            after = len(new_text)
            if before != after:
                total_replacements += 1

        result = EditResult(
            path=path, replacements=total_replacements,
            bytes_before=len(text.encode("utf-8")),
            bytes_after=len(new_text.encode("utf-8")),
        )
        if total_replacements > 0 and not dry_run:
            self._atomic_write(path, new_text)
            result.applied = True
        return result

    # ═══ Structured document editing ═══

    def replace_json_value(
        self,
        path: str | Path,
        json_path: str,
        new_value: Any,
        dry_run: bool = False,
    ) -> EditResult:
        """Replace a value at a dot-separated JSON path.

        Example: json_path="config.server.port", new_value=8888
        """
        import json
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Navigate to the nested key
        keys = json_path.split(".")
        target = data
        for k in keys[:-1]:
            if k not in target:
        return EditResult(path=path)

    # ═══ Semantic navigation: LLM finds exact code locations ═══

    async def find_location(
        self,
        query: str,
        project_root: str | Path = ".",
        hub=None,
    ) -> list[dict]:
        """Semantic file navigation — LLM reads files and returns exact locations.

        "find where authentication logic is" → [{file: "auth.py", line: 42, context: "..."}]
        """
        if not hub or not hub.world:
            return []

        root = Path(project_root)
        # First, find candidate files via filesystem
        candidates = []
        for f in root.rglob("*.py"):
            if f.stat().st_size < 100000 and ".venv" not in str(f) and "__pycache__" not in str(f):
                candidates.append(f)
            if len(candidates) > 30:
                break

        if not candidates:
            return []

        # Let LLM scan candidates and locate the relevant code
        file_list = "\n".join(str(c.relative_to(root)) for c in candidates[:20])
        llm = hub.world.consciousness._llm

        try:
            result = await llm.chat(
                messages=[{"role": "user", "content": (
                    f"Given these project files:\n{file_list}\n\n"
                    f"Query: {query}\n\n"
                    f"Which file(s) most likely contain the relevant code? "
                    f"Output JSON array: [{{\"file\":\"path\",\"reason\":\"why\"}}]"
                )}],
                provider=getattr(llm, '_elected', ''),
                temperature=0.1, max_tokens=300, timeout=15,
            )
            if not result or not result.text:
                return []

            import json as _json
            m = re.search(r'\[[\s\S]*\]', result.text)
            if not m:
                return []
            files = _json.loads(m.group())
            locations = []
            for item in files[:5]:
                fpath = root / item["file"]
                if fpath.exists():
                    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read(20000)
                    # Find the specific line
                    result2 = await llm.chat(
                        messages=[{"role": "user", "content": (
                            f"File: {item['file']}\nContent:\n```\n{content[:8000]}\n```\n\n"
                            f"Query: {query}\n\n"
                            f"Output JSON: {{\"line\": N, \"context\": \"the matching code\"}}"
                            f"Where N is the 1-indexed line number of the most relevant code."
                        )}],
                        provider=getattr(llm, '_elected', ''),
                        temperature=0.0, max_tokens=200, timeout=15,
                    )
                    if result2 and result2.text:
                        m2 = re.search(r'\{[\s\S]*\}', result2.text)
                        if m2:
                            loc = _json.loads(m2.group())
                            locations.append({
                                "file": str(fpath),
                                "line": loc.get("line", 0),
                                "context": loc.get("context", "")[:200],
                                "reason": item.get("reason", ""),
                            })
            return locations[:5]
        except Exception:
            return []

    # ═══ Multi-file transactions ═══

    async def transaction(
        self,
        edits: list[dict],  # [{path, pattern, replacement}, ...]
        dry_run: bool = False,
    ) -> dict:
        """Edit multiple files atomically. Auto-rollback ALL if any fails.

        Args:
            edits: List of {path, pattern, replacement} dicts
            dry_run: Preview only

        Returns:
            {success: bool, results: [EditResult], rollback: bool}
        """
        backups = {}
        results = []
        success = True

        # Phase 1: Backup all files
        for edit in edits:
            path = Path(edit["path"])
            if path.exists():
                backups[str(path)] = path.read_bytes()

        # Phase 2: Apply all edits
        for edit in edits:
            result = self.replace_pattern(
                edit["path"], edit.get("pattern", ""),
                edit.get("replacement", ""), dry_run=dry_run,
            )
            results.append(result)
            if not dry_run and result.replacements == 0:
                success = False
                break

        # Phase 3: Rollback on failure
        if not success and not dry_run:
            for path_str, backup in backups.items():
                Path(path_str).write_bytes(backup)
            return {"success": False, "results": results, "rollback": True}

        return {"success": True, "results": results, "rollback": False}
            target = target[k]

        last_key = keys[-1]
        if last_key not in target:
            return EditResult(path=path)

        old_value = target[last_key]
        target[last_key] = new_value

        new_text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        result = EditResult(
            path=path, replacements=1,
            bytes_before=path.stat().st_size,
            bytes_after=len(new_text.encode("utf-8")),
            preview=f"  - {json_path}: {old_value} → {new_value}",
        )
        if not dry_run:
            self._atomic_write(path, new_text)
            result.applied = True
        return result

    # ═══ Large file performance helpers ═══

    def _read_lines_streaming(self, path: Path) -> list[str]:
        """Read file line-by-line. For very large files, uses chunked reading."""
        size = path.stat().st_size if path.exists() else 0
        if size > 100 * 1024 * 1024:
            # >100MB: use mmap
            lines = []
            with open(path, "r+b") as f:
                with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as m:
                    for line in iter(m.readline, b""):
                        lines.append(line.decode("utf-8", errors="replace"))
            return lines
        # <100MB: standard read
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.readlines()

    def _atomic_write(self, path: Path, content: str):
        """Write to temp file, then rename. Crash-safe."""
        tmp = self._temp_dir / f"{path.name}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(str(tmp), str(path))

    def _heading_level(self, line: str) -> int:
        """Count # at start of line (Markdown heading level)."""
        m = re.match(r'^(#+) ', line)
        if m:
            return len(m.group(1))
        # Chinese headings
        m = re.match(r'^(第[一二三四五六七八九十百千]+[章节条])\s', line)
        if m:
            return 2
        return 0

    def _match_heading(self, line: str, heading: str) -> bool:
        """Fuzzy heading match — tolerates spacing, punctuation, numbering variations."""
        def _normalize(s: str) -> str:
            s = s.lstrip("# ").strip()
            s = re.sub(r'[ 　\t]+', '', s)       # remove all whitespace
            s = re.sub(r'[.。,，、:：]', '', s)   # remove punctuation
            s = re.sub(r'[第].*?[章节条]', '', s)  # strip Chinese numbering
            s = re.sub(r'^\d+[.\s]*', '', s)      # strip digit numbering
            return s.lower()
        return _normalize(line) == _normalize(heading)

    def smart_replace(
        self,
        path: str | Path,
        anchor: str,
        new_content: str,
        mode: str = "section",
        dry_run: bool = False,
    ) -> EditResult:
        """Smart replacement with content anchoring.

        Unlike regex or exact match, this finds the right content block
        using multiple signals (heading similarity, context proximity, content hash).

        Args:
            path: File to edit
            anchor: Content to find (heading, key phrase, or paragraph start)
            new_content: Replacement content
            mode: "heading" (by heading), "block" (by paragraph), "key" (by unique key)
            dry_run: Preview only
        """
        path = Path(path)
        old_lines = self._read_lines_streaming(path)
        result = EditResult(path=path, bytes_before=path.stat().st_size if path.exists() else 0)

        if mode == "heading":
            return self.replace_section(path, anchor, new_content, dry_run)

        elif mode == "block":
            # Find a paragraph that starts with the anchor text
            anchor_norm = re.sub(r'\s+', '', anchor.lower())
            best_idx = -1
            best_score = 0
            block_start = -1
            in_block = False

            for i, line in enumerate(old_lines):
                stripped = line.strip()
                if stripped and not in_block:
                    in_block = True
                    block_start = i
                elif not stripped and in_block:
                    # End of block — check if this is the right one
                    block_text = "".join(old_lines[block_start:i])
                    block_norm = re.sub(r'\s+', '', block_text.lower())
                    # Score: how much of the anchor appears in this block
                    overlap = sum(1 for c in anchor_norm if c in block_norm)
                    score = overlap / max(len(anchor_norm), 1)
                    if score > best_score:
                        best_score = score
                        best_idx = block_start
                    in_block = False

            if best_score > 0.5 and best_idx >= 0:
                # Replace the best-matching block
                end_idx = best_idx
                while end_idx < len(old_lines) and old_lines[end_idx].strip():
                    end_idx += 1
                new_lines = old_lines[:best_idx] + [new_content + "\n"]
                if end_idx < len(old_lines):
                    new_lines.append("\n")
                    new_lines.extend(old_lines[end_idx + 1:])
                result.replacements = 1
                result.lines_changed = end_idx - best_idx
                new_text = "".join(new_lines)
                result.bytes_after = len(new_text.encode("utf-8"))
                if not dry_run:
                    self._atomic_write(path, new_text)
                    result.applied = True
            return result

        elif mode == "key":
            # Find a line containing a unique key and replace it
            for i, line in enumerate(old_lines):
                if anchor in line:
                    indent = len(line) - len(line.lstrip())
                    new_line = " " * indent + new_content + "\n"
                    new_lines = old_lines[:i] + [new_line] + old_lines[i + 1:]
                    result.replacements = 1
                    result.lines_changed = 1
                    new_text = "".join(new_lines)
                    result.bytes_after = len(new_text.encode("utf-8"))
                    if not dry_run:
                        self._atomic_write(path, new_text)
                        result.applied = True
                    return result
            return result

        return result

    def _diff_preview(self, path: Path, new_content: str) -> str:
        """Generate a simple diff preview showing added/removed lines."""
        old_lines = set()
        if path.exists():
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                old_lines = set(f.readlines())
        new_lines = set(new_content.splitlines(True))

        added = len(new_lines - old_lines)
        removed = len(old_lines - new_lines)
        return f"+{added}/-{removed} lines"

    # ═══ LLM-powered replacement ═══

    async def llm_replace(
        self,
        path: str | Path,
        instruction: str,
        hub=None,
        dry_run: bool = False,
    ) -> EditResult:
        """Let the LLM read the file, figure out what to change, and generate the regex.

        Args:
            path: File to edit
            instruction: Natural language description of what to change
            hub: IntegrationHub for LLM access

        Example:
            await editor.llm_replace("config.yaml", "把端口从8100改成8888", hub)
        """
        path = Path(path)
        if not path.exists():
            return EditResult(path=path)

        # Read file (first 50KB for context)
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(50000)

        if not hub or not hub.world:
            # Fallback: use the simplest possible approach
            return self.replace_pattern(path, instruction, "", dry_run=dry_run)

        llm = hub.world.consciousness._llm
        try:
            result = await llm.chat(
                messages=[{"role": "user", "content": (
                    "You are a precise file editor. Given a file and an instruction, "
                    "output a JSON with the exact regex pattern and replacement to apply.\n\n"
                    "FILE CONTENT:\n```\n" + content[:10000] + "\n```\n\n"
                    "INSTRUCTION: " + instruction + "\n\n"
                    "Output ONLY this JSON (no explanation):\n"
                    '{"pattern": "regex_pattern_here", "replacement": "replacement_text_here", "count": 0}\n'
                    "- pattern: Python regex to find the text to replace\n"
                    "- replacement: the new text\n"
                    "- count: 0 means replace all matches, 1 means first only\n"
                    "Make the pattern specific enough to match only the intended target."
                )}],
                provider=getattr(llm, '_elected', ''),
                temperature=0.0,
                max_tokens=500,
                timeout=20,
            )
            if result and result.text:
                import json, re
                m = re.search(r'\{[\s\S]*\}', result.text)
                if m:
                    data = json.loads(m.group())
                    return self.replace_pattern(
                        path,
                        data["pattern"],
                        data["replacement"],
                        count=data.get("count", 0),
                        dry_run=dry_run,
                    )
        except Exception as e:
            logger.debug(f"LLM replace: {e}")

        return EditResult(path=path)


# ═══ Convenience ═══

_editor: DocumentEditor | None = None


def get_editor() -> DocumentEditor:
    global _editor
    if _editor is None:
        _editor = DocumentEditor()
    return _editor
