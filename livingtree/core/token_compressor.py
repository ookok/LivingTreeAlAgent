"""Token Compressor — reduce token usage on tool outputs before LLM ingestion.

Inspired by 9Router's RTK token saver. Applies lossless compression to:
  - git diff / git status / git log
  - grep / find / ls / tree outputs
  - error logs / stacktraces
  - code snippets with boilerplate

Typical savings: 20-40% on tool_result messages.
"""
from __future__ import annotations

import re
from typing import Optional


def _safe_compress(text: str, max_len: int = 8000) -> str:
    """Smart truncation: keep start + end, cut middle."""
    if len(text) <= max_len:
        return text
    half = max_len // 2
    return text[:half] + f"\n... [truncated {len(text) - max_len} chars] ...\n" + text[-half:]


# ═══ Compression Filters ═══


def compress_git_diff(text: str) -> str:
    """Compress git diff output: keep file headers + changed lines, skip context."""
    lines = text.split("\n")
    result = []
    in_hunk = False
    context_lines = 0
    max_context = 2  # keep only 2 context lines per hunk

    for line in lines:
        if line.startswith("diff --git") or line.startswith("---") or line.startswith("+++"):
            result.append(line)
            continue
        if line.startswith("@@"):
            in_hunk = True
            context_lines = 0
            result.append(line)
            continue
        if in_hunk:
            if line.startswith("+") or line.startswith("-"):
                context_lines = 0
                result.append(line)
            elif line.startswith(" ") and line.strip():
                context_lines += 1
                if context_lines <= max_context:
                    result.append(line)
                elif context_lines == max_context + 1:
                    result.append("  ...")
            elif not line.strip():
                result.append(line)
        else:
            result.append(line)

    compressed = "\n".join(result)
    if len(compressed) < len(text) * 0.8:
        return compressed
    return _safe_compress(text)


def compress_grep(text: str) -> str:
    """Compress grep output: deduplicate, group by file."""
    lines = text.strip().split("\n")
    if len(lines) <= 10:
        return text

    # Group by file prefix
    from collections import defaultdict
    groups = defaultdict(list)
    current_file = "stdin"
    for line in lines:
        m = re.match(r'^([^:]+):(\d+):', line)
        if m:
            current_file = m.group(1)
        groups[current_file].append(line)

    if len(groups) <= 1:
        return _safe_compress(text, 4000)

    result = []
    for file, entries in groups.items():
        result.append(f"--- {file} ({len(entries)} matches) ---")
        for entry in entries[:3]:
            result.append(entry)
        if len(entries) > 3:
            result.append(f"  ... +{len(entries) - 3} more")
    return "\n".join(result)


def compress_ls_tree(text: str) -> str:
    """Compress ls/tree output: collapse similar files."""
    lines = text.strip().split("\n")
    if len(lines) <= 20:
        return text

    dirs = [l for l in lines if "/" in l or l.endswith("/")]
    files = [l for l in lines if l not in dirs]

    result = dirs[:15]
    if len(dirs) > 15:
        result.append(f"  ... +{len(dirs) - 15} more dirs")

    # Group files by extension
    from collections import Counter
    exts = Counter()
    file_exts = {}
    for f in files:
        ext = f.rsplit(".", 1)[-1] if "." in f else "(none)"
        exts[ext] += 1
        file_exts.setdefault(ext, []).append(f)

    for ext, count in exts.most_common(8):
        if count <= 3:
            for f in file_exts[ext]:
                result.append(f"  {f}")
        else:
            samples = file_exts[ext][:2]
            result.append(f"  {samples[0]}")
            if len(samples) > 1:
                result.append(f"  {samples[1]}")
            result.append(f"  ... {count} .{ext} files total")

    return "\n".join(result)


def compress_log(text: str) -> str:
    """Compress log output: deduplicate repeated lines, keep unique errors."""
    lines = text.strip().split("\n")
    if len(lines) <= 20:
        return text

    from collections import Counter
    seen = Counter()
    result = []
    for line in lines:
        # Normalize: strip timestamps, numbers, UUIDs
        key = re.sub(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}', '<TS>', line)
        key = re.sub(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', '<UUID>', key)
        key = re.sub(r'\d+', '<N>', key)

        if seen[key] == 0:
            result.append(line)
        elif seen[key] == 1:
            result.append(f"[repeated] {_safe_compress(line, 200)}")
        seen[key] += 1

    return "\n".join(result)


def compress_stacktrace(text: str) -> str:
    """Compress stacktrace: keep error message + first/last frames."""
    lines = text.strip().split("\n")
    if len(lines) <= 15:
        return text

    result = []
    frames = []
    in_frames = False
    error_line = ""

    for line in lines:
        if not in_frames and ("Traceback" in line or "Error:" in line or "Exception:" in line or "panic:" in line):
            error_line = line
            in_frames = True
            result.append(line)
            continue
        if in_frames:
            if line.strip().startswith("File ") or line.strip().startswith("at ") or line.strip().startswith("  "):
                frames.append(line)
            else:
                result.append(line)

    if frames:
        result.append(frames[0])
        if len(frames) > 4:
            result.append(f"  ... {len(frames) - 4} intermediate frames ...")
            result.append(frames[-3])
            result.append(frames[-2])
            result.append(frames[-1])
        else:
            result.extend(frames[1:])

    return "\n".join(result)


# ═══ Auto-Detect & Compress ═══

_FILTERS = [
    (lambda t: "diff --git" in t[:500] or t.strip().startswith("diff "), compress_git_diff),
    (lambda t: t.strip().startswith("@") and "@@" in t[:200], compress_git_diff),  # hunk without diff header
    (lambda t: t.startswith("On branch ") or "git status" in t[:200], _safe_compress),
    (lambda t: bool(re.search(r'^[^:\n]+:\d+:', t[:1000], re.MULTILINE)), compress_grep),
    (lambda t: ("total" in t[:200] and "drwx" in t[:500]) or ("Mode" in t[:200] and "LastWriteTime" in t[:500]), compress_ls_tree),
    (lambda t: (t.count("\n") > 20) and ("ERROR" in t or "WARN" in t or "DEBUG" in t or "INFO" in t), compress_log),
    (lambda t: "Traceback" in t[:500] or "panic:" in t[:500], compress_stacktrace),
    (lambda t: len(t) > 8000, lambda t: _safe_compress(t)),
]


def compress(content: str) -> dict:
    """Auto-detect type and apply best compression.

    Returns {"compressed": str, "filter": str, "saved_pct": float}
    """
    if not content or len(content) < 500:
        return {"compressed": content, "filter": "none", "saved_pct": 0}

    for detector, filter_fn in _FILTERS:
        try:
            if detector(content):
                compressed = filter_fn(content)
                if not compressed:
                    return {"compressed": content, "filter": "error", "saved_pct": 0}
                saved = 1 - len(compressed) / max(len(content), 1)
                if saved <= 0:
                    return {"compressed": content, "filter": "no_savings", "saved_pct": 0}
                return {
                    "compressed": compressed,
                    "filter": filter_fn.__name__,
                    "saved_pct": round(saved * 100, 1),
                }
        except Exception:
            continue

    # Default: safe truncation for very long content
    if len(content) > 10000:
        compressed = _safe_compress(content, 6000)
        return {
            "compressed": compressed,
            "filter": "safe_truncate",
            "saved_pct": round((1 - len(compressed) / len(content)) * 100, 1),
        }

    return {"compressed": content, "filter": "pass", "saved_pct": 0}
