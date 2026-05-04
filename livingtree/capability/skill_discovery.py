"""Skill Discovery — Cross-tool skill directory walker.

Inspired by DeepSeek-TUI's skill discovery mechanism. Walks multiple
skill directories with first-wins precedence, discovers SKILL.md files,
and populates the skill registry.

Directory precedence:
1. .agents/skills (project-local, highest priority)
2. skills (project-local)
3. .opencode/skills (opencode compat)
4. .claude/skills (claude compat)
5. ~/.livingtree/skills (global)

Usage:
    discoverer = SkillDiscoveryManager()
    skills = discoverer.discover_all()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from loguru import logger


@dataclass
class DiscoveredSkill:
    name: str
    path: Path
    description: str = ""
    source: str = ""
    yaml_frontmatter: dict = field(default_factory=dict)
    body: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": str(self.path),
            "description": self.description,
            "source": self.source,
        }


class SkillDiscoveryManager:
    """Walks skill directories and discovers SKILL.md files."""

    SKILL_DIRS = [
        (".agents/skills", "project"),
        ("skills", "project"),
        (".opencode/skills", "opencode"),
        (".claude/skills", "claude"),
    ]

    def __init__(self, workspace: str = ".", global_dir: str | None = None):
        self._workspace = Path(workspace).resolve()
        self._global_dir = Path(global_dir) if global_dir else Path.home() / ".livingtree" / "skills"
        self._discovered: dict[str, DiscoveredSkill] = {}

    def discover_all(self) -> list[DiscoveredSkill]:
        """Discover all skills across all directories. First-wins precedence."""
        discovered = {}

        all_dirs = [
            (self._workspace / d[0], d[1]) for d in self.SKILL_DIRS
        ]
        if self._global_dir.exists():
            all_dirs.append((self._global_dir, "global"))

        for skill_dir, source in all_dirs:
            if not skill_dir.exists():
                continue

            for skill_path in self._walk_skill_dirs(skill_dir):
                name = skill_path.name

                if name in discovered:
                    continue

                skill = self._parse_skill(skill_path, source)
                if skill and skill.name:
                    if skill.name not in discovered:
                        discovered[skill.name] = skill

        self._discovered = discovered
        return list(discovered.values())

    def discover_for_context(self, source: str = "project") -> list[DiscoveredSkill]:
        """Discover skills from a specific source type."""
        all_skills = self.discover_all()
        return [s for s in all_skills if s.source == source]

    def get_skill(self, name: str) -> Optional[DiscoveredSkill]:
        if not self._discovered:
            self.discover_all()
        return self._discovered.get(name)

    def get_skill_body(self, name: str) -> Optional[str]:
        skill = self.get_skill(name)
        return skill.body if skill else None

    def list_for_context(self) -> str:
        skills = self.discover_all()
        if not skills:
            return "[dim]No skills discovered[/dim]"

        lines = ["[bold]Discovered Skills:[/bold]"]
        by_source: dict[str, list[DiscoveredSkill]] = {}
        for s in skills:
            by_source.setdefault(s.source, []).append(s)

        for source, slist in by_source.items():
            lines.append(f"  [{source}]:")
            for s in slist:
                lines.append(f"    [bold]{s.name}[/bold] — {s.description[:60] if s.description else 'no description'}")

        return "\n".join(lines)

    def _walk_skill_dirs(self, root: Path) -> list[Path]:
        results = []

        for item in root.iterdir():
            if item.is_dir():
                skill_md = item / "SKILL.md"
                if skill_md.exists():
                    results.append(item)
                else:
                    sub_results = self._walk_skill_dirs(item)
                    results.extend(sub_results)

        return results

    def _parse_skill(self, skill_dir: Path, source: str) -> Optional[DiscoveredSkill]:
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            return None

        try:
            content = skill_md.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Cannot read {skill_md}: {e}")
            return None

        frontmatter = {}
        body = content
        name = skill_dir.name
        description = ""

        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                fm_text = parts[1].strip()
                body = parts[2].strip()
                try:
                    for line in fm_text.split("\n"):
                        line = line.strip()
                        if ":" in line:
                            key, val = line.split(":", 1)
                            frontmatter[key.strip()] = val.strip().strip('"').strip("'")
                except Exception:
                    pass

                name = frontmatter.get("name", name)
                description = frontmatter.get("description", "")

        return DiscoveredSkill(
            name=name,
            path=skill_dir,
            description=description,
            source=source,
            yaml_frontmatter=frontmatter,
            body=body,
        )
