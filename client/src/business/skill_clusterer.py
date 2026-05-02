"""
Skill Clusterer — Compatibility Stub

Functionality migrated to livingtree.core.skills.matcher.
"""


class SkillClusterer:
    def __init__(self):
        self._clusters = {}

    def cluster(self, skills: list) -> dict:
        return self._clusters


def create_skill_clusterer():
    return SkillClusterer()


__all__ = ["SkillClusterer", "create_skill_clusterer"]
