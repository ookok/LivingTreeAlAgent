"""LivingTree Skills — auto-evolving agent skills from real sessions.

Skill format (SKILL.md with YAML frontmatter):
    ---
    name: jwt-auth-best-practice
    description: JWT token authentication pattern for FastAPI
    tags: [python, fastapi, auth, jwt]
    version: 2
    source_project: myapp
    source_user: dev_1
    created_at: 1746700000.0
    updated_at: 1746710000.0
    usage_count: 5
    status: active
    ---
    # JWT Authentication Best Practice
    ...markdown content...

Skills can be local (per-user) or shared (per-workspace).
Auto-evolves from recorded sessions via dedup + improve + validate loop.

Inspired by SkillClaw (AMAP-ML/SkillClaw).
"""
from __future__ import annotations

import hashlib
import html as _html
import json
import re
import time
import yaml
from pathlib import Path
from typing import Optional

from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS_BASE = PROJECT_ROOT / "data" / "skills"
SESSIONS_DIR = PROJECT_ROOT / "data" / "skill_sessions"

FRONTMATTER_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)

MAX_FRONTMATTER_BYTES = 64 * 1024
MAX_BODY_BYTES = 512 * 1024
MAX_YAML_DEPTH = 10
SAFE_TAGS = {"b", "i", "em", "strong", "code", "pre", "blockquote",
             "h1", "h2", "h3", "h4", "h5", "h6", "p", "br", "hr",
             "ul", "ol", "li", "a", "img", "table", "thead", "tbody",
             "tr", "th", "td", "span", "div"}


class SkillEntry:
    """A parsed skill with frontmatter metadata and body content."""

    def __init__(self, filepath: Path, metadata: dict, body: str):
        self.filepath = filepath
        self.metadata = metadata
        self.body = body

    @property
    def name(self) -> str:
        return self.metadata.get("name", self.filepath.stem)

    @property
    def description(self) -> str:
        return self.metadata.get("description", "")

    @property
    def tags(self) -> list[str]:
        return self.metadata.get("tags", [])

    @property
    def version(self) -> int:
        return self.metadata.get("version", 1)

    @property
    def status(self) -> str:
        return self.metadata.get("status", "active")

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "tags": self.tags,
            "version": self.version,
            "status": self.status,
            "source_project": self.metadata.get("source_project", ""),
            "source_user": self.metadata.get("source_user", ""),
            "usage_count": self.metadata.get("usage_count", 0),
            "created_at": self.metadata.get("created_at", 0),
            "updated_at": self.metadata.get("updated_at", 0),
            "path": str(self.filepath.relative_to(SKILLS_BASE)).replace("\\", "/"),
            "preview": self.body[:200],
        }


def _get_skill_dir(*, user_id: str = "", workspace_id: str = "") -> Path:
    """Get the skills directory for a scope."""
    if workspace_id:
        return SKILLS_BASE / "workspaces" / workspace_id
    if user_id:
        return SKILLS_BASE / "local" / user_id
    return SKILLS_BASE / "shared"


def _parse_skill_file(filepath: Path) -> Optional[SkillEntry]:
    """Parse a SKILL.md file into a SkillEntry."""
    try:
        content = filepath.read_text(encoding="utf-8")
        m = FRONTMATTER_RE.match(content)
        if m:
            fm_text = m.group(1)
            if len(fm_text.encode("utf-8")) > MAX_FRONTMATTER_BYTES:
                logger.warning(f"Skill frontmatter too large ({len(fm_text)} bytes) for {filepath}")
                metadata = {}
            else:
                yaml.SafeLoader.add_constructor(
                    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
                    _safe_map_loader
                )
                yaml.SafeLoader.add_constructor(
                    yaml.resolver.BaseResolver.DEFAULT_SEQUENCE_TAG,
                    _safe_seq_loader
                )
                try:
                    metadata = yaml.safe_load(fm_text) or {}
                except yaml.YAMLError as e:
                    logger.warning(f"YAML parse error in {filepath}: {e}")
                    metadata = {}
            body = content[m.end():].strip()
        else:
            metadata = {}
            body = content.strip()
        return SkillEntry(filepath, metadata, body)
    except Exception as e:
        logger.warning(f"Failed to parse skill file {filepath}: {e}")
        return None


def _safe_map_loader(loader, node, deep=False):
    """Custom YAML mapping loader with nesting depth guard (prevents YAML bombs)."""
    mapping = {}
    for k, v in (node.value if hasattr(node, 'value') else []):
        if len(mapping) > 500:
            break
        key = loader.construct_object(k, deep=deep)
        if isinstance(key, str) and len(key) > 256:
            key = key[:256]
        val = loader.construct_object(v, deep=deep)
        if isinstance(val, str) and len(val) > 4096:
            val = val[:4096]
        mapping[key] = val
    return mapping


def _safe_seq_loader(loader, node, deep=False):
    """Custom YAML sequence loader with length guard."""
    seq = []
    for v in (node.value if hasattr(node, 'value') else []):
        if len(seq) > 200:
            break
        val = loader.construct_object(v, deep=deep)
        if isinstance(val, str) and len(val) > 4096:
            val = val[:4096]
        seq.append(val)
    return seq


def _write_skill_file(filepath: Path, metadata: dict, body: str) -> None:
    """Write a SKILL.md file with YAML frontmatter."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = yaml.dump(metadata, allow_unicode=True, default_flow_style=False, sort_keys=False).strip()
    filepath.write_text(f"---\n{frontmatter}\n---\n\n{body}", encoding="utf-8")


def _sanitize_body(body: str) -> str:
    """Strip dangerous HTML/JS from skill body to prevent XSS."""
    if not body:
        return ""
    if len(body.encode("utf-8")) > MAX_BODY_BYTES:
        body = body[:MAX_BODY_BYTES]
    body = re.sub(r'<script[^>]*>.*?</script>', '', body, flags=re.DOTALL | re.IGNORECASE)
    body = re.sub(r'<iframe[^>]*>.*?</iframe>', '', body, flags=re.DOTALL | re.IGNORECASE)
    body = re.sub(r'<object[^>]*>.*?</object>', '', body, flags=re.DOTALL | re.IGNORECASE)
    body = re.sub(r'<embed[^>]*>', '', body, flags=re.IGNORECASE)
    body = re.sub(r'javascript:', '', body, flags=re.IGNORECASE)
    body = re.sub(r'on\w+\s*=', '', body, flags=re.IGNORECASE)
    body = re.sub(r'style\s*=\s*"[^"]*expression\s*\(', '', body, flags=re.IGNORECASE)
    return body


def _skill_name_to_filename(name: str) -> str:
    """Convert skill name to a safe filename."""
    safe = re.sub(r'[^\w\-]', '-', name.lower()).strip('-')
    return f"{safe}.md" if safe else "skill.md"


def _content_hash(content: str) -> str:
    """SHA256 hash of content for deduplication."""
    return hashlib.sha256(content.encode()).hexdigest()[:16]


# ═══ Public API ═══


def list_skills(
    *,
    user_id: str = "",
    workspace_id: str = "",
    tag: str = "",
    status: str = "",
    search: str = "",
) -> list[dict]:
    """List skills for a scope, with optional filters."""
    skill_dir = _get_skill_dir(user_id=user_id, workspace_id=workspace_id)
    skills = []

    if not skill_dir.exists():
        return skills

    for md_file in skill_dir.rglob("*.md"):
        entry = _parse_skill_file(md_file)
        if not entry:
            continue
        if status and entry.status != status:
            continue
        if tag and tag not in entry.tags:
            continue
        if search:
            q = search.lower()
            if q not in entry.name.lower() and q not in entry.description.lower() and q not in entry.body.lower():
                continue
        skills.append(entry.to_dict())

    return sorted(skills, key=lambda s: s["updated_at"], reverse=True)


def get_skill(name: str, *, user_id: str = "", workspace_id: str = "") -> Optional[dict]:
    """Get a single skill by name."""
    skill_dir = _get_skill_dir(user_id=user_id, workspace_id=workspace_id)
    for md_file in skill_dir.rglob("*.md"):
        entry = _parse_skill_file(md_file)
        if entry and entry.name == name:
            return entry.to_dict()
    return None


def create_or_update_skill(
    name: str,
    body: str,
    *,
    user_id: str = "",
    workspace_id: str = "",
    description: str = "",
    tags: list[str] = None,
    source_project: str = "",
    source_user: str = "",
) -> dict:
    """Create a new skill or update an existing one (version bump)."""
    body = _sanitize_body(body)
    skill_dir = _get_skill_dir(user_id=user_id, workspace_id=workspace_id)
    filename = _skill_name_to_filename(name)
    filepath = skill_dir / filename

    existing = _parse_skill_file(filepath)

    now = time.time()
    if existing:
        # Update: bump version, preserve creation time
        metadata = existing.metadata.copy()
        metadata["version"] = metadata.get("version", 1) + 1
        metadata["updated_at"] = now
        if description:
            metadata["description"] = description
        if tags:
            metadata["tags"] = tags
    else:
        # Create new
        metadata = {
            "name": name,
            "description": description or f"Skill: {name}",
            "tags": tags or [],
            "version": 1,
            "source_project": source_project,
            "source_user": source_user,
            "created_at": now,
            "updated_at": now,
            "usage_count": 0,
            "status": "active",
        }

    _write_skill_file(filepath, metadata, body)
    logger.info(f"Skill {'updated' if existing else 'created'}: {name} v{metadata['version']}")

    return _parse_skill_file(filepath).to_dict()


def delete_skill(name: str, *, user_id: str = "", workspace_id: str = "") -> bool:
    """Delete a skill by name."""
    skill_dir = _get_skill_dir(user_id=user_id, workspace_id=workspace_id)
    filename = _skill_name_to_filename(name)
    filepath = skill_dir / filename
    if filepath.exists():
        filepath.unlink()
        logger.info(f"Skill deleted: {name}")
        return True
    return False


def touch_skill(name: str, *, user_id: str = "", workspace_id: str = "") -> bool:
    """Increment usage count for a skill."""
    skill_dir = _get_skill_dir(user_id=user_id, workspace_id=workspace_id)
    filename = _skill_name_to_filename(name)
    filepath = skill_dir / filename
    entry = _parse_skill_file(filepath)
    if entry:
        entry.metadata["usage_count"] = entry.metadata.get("usage_count", 0) + 1
        entry.metadata["updated_at"] = time.time()
        _write_skill_file(filepath, entry.metadata, entry.body)
        return True
    return False


# ═══ Session Recording for Skill Extraction ═══


def record_session(
    user_id: str,
    context: str,
    *,
    project: str = "",
    workspace_id: str = "",
    operation: str = "",
    file_path: str = "",
    before_content: str = "",
    after_content: str = "",
    tags: list[str] = None,
) -> str:
    """Record a session trace for potential skill extraction.

    Store structured session data that can be analyzed by the evolution pipeline
    to extract reusable skills. This is the "task-time loop" recording.
    """
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    session_entry = {
        "session_id": f"ses_{hashlib.sha256(f'{user_id}{time.time()}'.encode()).hexdigest()[:12]}",
        "user_id": user_id,
        "project": project,
        "workspace_id": workspace_id,
        "operation": operation,
        "file_path": file_path,
        "context": context,
        "before_snippet": before_content[:500] if before_content else "",
        "after_snippet": after_content[:500] if after_content else "",
        "tags": tags or [],
        "timestamp": time.time(),
    }

    scope_dir = SESSIONS_DIR / (workspace_id or user_id or "shared")
    scope_dir.mkdir(parents=True, exist_ok=True)

    date_str = time.strftime("%Y-%m-%d")
    session_file = scope_dir / f"session_{date_str}.jsonl"

    with open(session_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(session_entry, ensure_ascii=False) + "\n")

    return session_entry["session_id"]


def suggest_skills_from_sessions(
    *,
    user_id: str = "",
    workspace_id: str = "",
    min_similar_sessions: int = 2,
) -> list[dict]:
    """Analyze recorded sessions and suggest potential skills.

    Looks for repeated patterns (same operation type on similar files)
    and suggests creating skills from them.
    """
    scope_dir = SESSIONS_DIR / (workspace_id or user_id or "shared")
    if not scope_dir.exists():
        return []

    sessions = []
    for jsonl_file in sorted(scope_dir.glob("session_*.jsonl"), reverse=True):
        try:
            for line in jsonl_file.read_text(encoding="utf-8").strip().split("\n"):
                if line:
                    sessions.append(json.loads(line))
        except Exception:
            continue
        if len(sessions) >= 200:
            break

    if len(sessions) < min_similar_sessions:
        return []

    # Group sessions by operation + file pattern
    from collections import defaultdict
    groups = defaultdict(list)
    for s in sessions:
        # Extract file extension pattern as category
        op = s.get("operation", "")
        fp = s.get("file_path", "")
        ext = Path(fp).suffix if fp else "general"
        pattern_key = f"{op}:*{ext}" if ext else op
        groups[pattern_key].append(s)

    suggestions = []
    for pattern_key, group in groups.items():
        if len(group) >= min_similar_sessions:
            sample_contexts = [s["context"][:100] for s in group[:3]]
            suggestions.append({
                "pattern": pattern_key,
                "session_count": len(group),
                "suggested_skill_name": pattern_key.replace(":", "-").replace(".", "-"),
                "sample_sessions": sample_contexts,
                "tags": list(set(t for s in group for t in s.get("tags", []))),
            })

    return sorted(suggestions, key=lambda x: x["session_count"], reverse=True)


def deduplicate_skills(*, user_id: str = "", workspace_id: str = "") -> dict:
    """Find duplicate or similar skills and suggest merges."""
    all_skills = list_skills(user_id=user_id, workspace_id=workspace_id)

    duplicates = []
    seen_hashes = {}
    for skill in all_skills:
        skill_dir = _get_skill_dir(user_id=user_id, workspace_id=workspace_id)
        filepath = skill_dir / _skill_name_to_filename(skill["name"])
        if filepath.exists():
            content = filepath.read_text(encoding="utf-8")
            h = _content_hash(content)
            if h in seen_hashes:
                duplicates.append({
                    "skill_a": seen_hashes[h],
                    "skill_b": skill["name"],
                    "hash": h,
                })
            else:
                seen_hashes[h] = skill["name"]

    return {
        "total_skills": len(all_skills),
        "duplicates": duplicates,
        "duplicate_count": len(duplicates),
    }
