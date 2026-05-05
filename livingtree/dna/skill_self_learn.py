"""SkillSelfLearn — autonomous skill creation + self-improvement loop.

Inspired by Hermes Agent: after completing complex tasks, the system
can propose new skills, improve existing ones, and nudge itself to
persist knowledge.

Flow: task completed → analyze success → propose skill → user approve → register.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

SKILL_FILE = Path(".livingtree/learned_skills.json")
NUDGE_FILE = Path(".livingtree/knowledge_nudges.json")


@dataclass
class LearnedSkill:
    name: str
    description: str
    prompt_template: str
    category: str = ""
    usage_count: int = 0
    success_count: int = 0
    created_at: float = field(default_factory=time.time)
    last_used: float = 0.0
    version: int = 1
    proposed: bool = False  # True if waiting for user approval

    @property
    def success_rate(self) -> float:
        return self.success_count / max(self.usage_count, 1)


@dataclass
class KnowledgeNudge:
    id: str
    topic: str
    content: str
    created_at: float = field(default_factory=time.time)
    last_nudged: float = 0.0
    nudge_count: int = 0


class SkillSelfLearn:
    """Autonomous skill creation and improvement.

    After each task: analyze patterns → propose new skill or improve existing.
    Periodically nudge itself to persist important knowledge.
    """

    def __init__(self):
        self._skills: dict[str, LearnedSkill] = {}
        self._nudges: dict[str, KnowledgeNudge] = {}
        self._task_count = 0
        self._load()

    # ═══ Skill creation ═══

    def analyze_task(self, task: str, result: str, success: bool):
        """Analyze a completed task for skill extraction."""
        self._task_count += 1
        if not success or self._task_count % 10 != 0:
            return None

        # Check if this pattern is recurring
        for skill in self._skills.values():
            if skill.name.lower() in task.lower() or any(kw in task.lower() for kw in skill.description.lower().split()[:3]):
                skill.usage_count += 1
                if success:
                    skill.success_count += 1
                skill.last_used = time.time()
                logger.debug(f"Skill '{skill.name}' used: {skill.success_rate:.1%}")
                self._save()
                return skill

        return None

    def propose_skill(self, task: str, hub=None) -> LearnedSkill | None:
        """Use LLM to propose a new skill from a successful task pattern."""
        skill_name = f"auto-skill-{len(self._skills)+1}"
        # Generate from task description
        words = task.replace("，", " ").replace("。", " ").split()
        keywords = [w for w in words if len(w) >= 2][:3]
        skill_name = "-".join(keywords) if keywords else skill_name

        skill = LearnedSkill(
            name=skill_name,
            description=task[:120],
            prompt_template=task,
            proposed=True,
        )
        self._skills[skill.name] = skill
        self._save()
        logger.info(f"Proposed skill: {skill_name}")
        return skill

    def approve_skill(self, name: str) -> bool:
        skill = self._skills.get(name)
        if skill and skill.proposed:
            skill.proposed = False
            self._save()
            return True
        return False

    def reject_skill(self, name: str) -> bool:
        if name in self._skills and self._skills[name].proposed:
            del self._skills[name]
            self._save()
            return True
        return False

    def get_skills(self, proposed_only: bool = False) -> list[LearnedSkill]:
        skills = list(self._skills.values())
        if proposed_only:
            return [s for s in skills if s.proposed]
        return sorted(skills, key=lambda s: -s.success_rate)

    # ═══ Knowledge nudges ═══

    def add_nudge(self, topic: str, content: str) -> KnowledgeNudge:
        nudge = KnowledgeNudge(
            id=f"nudge-{len(self._nudges)+1}",
            topic=topic, content=content,
        )
        self._nudges[nudge.id] = nudge
        self._save_nudges()
        return nudge

    def get_due_nudges(self) -> list[KnowledgeNudge]:
        """Get nudges that haven't been shown in >24h."""
        now = time.time()
        return [n for n in self._nudges.values() if now - n.last_nudged > 86400]

    def nudge_completed(self, nudge_id: str):
        n = self._nudges.get(nudge_id)
        if n:
            n.last_nudged = time.time()
            n.nudge_count += 1
            self._save_nudges()

    def get_status(self) -> dict:
        return {
            "skills": len(self._skills),
            "proposed": sum(1 for s in self._skills.values() if s.proposed),
            "nudges": len(self._nudges),
            "due_nudges": len(self.get_due_nudges()),
            "avg_success_rate": sum(s.success_rate for s in self._skills.values()) / max(len(self._skills), 1),
        }

    # ═══ Persistence ═══

    def _save(self):
        try:
            SKILL_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = [{"name": s.name, "description": s.description,
                     "prompt_template": s.prompt_template, "category": s.category,
                     "usage_count": s.usage_count, "success_count": s.success_count,
                     "version": s.version, "proposed": s.proposed} for s in self._skills.values()]
            SKILL_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.debug(f"Skill save: {e}")

    def _load(self):
        try:
            if SKILL_FILE.exists():
                for d in json.loads(SKILL_FILE.read_text()):
                    s = LearnedSkill(**{k: d.get(k, "") for k in ["name", "description", "prompt_template", "category", "usage_count", "success_count", "version", "proposed"]})
                    self._skills[s.name] = s
        except Exception:
            pass

    def _save_nudges(self):
        try:
            NUDGE_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = [{"id": n.id, "topic": n.topic, "content": n.content,
                     "last_nudged": n.last_nudged, "nudge_count": n.nudge_count} for n in self._nudges.values()]
            NUDGE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception:
            pass


# ═══ Global ═══

_learner: SkillSelfLearn | None = None


def get_learner() -> SkillSelfLearn:
    global _learner
    if _learner is None:
        _learner = SkillSelfLearn()
    return _learner
