"""
Skill Discovery — Compatibility Stub

Functionality migrated to livingtree.core.skills.matcher.
"""


class SkillDiscovery:
    def __init__(self):
        self._skills = []

    def discover(self, task_description: str) -> list:
        return []

    def auto_register(self, skill_name: str, handler):
        self._skills.append({"name": skill_name, "handler": handler})


def create_skill_discovery():
    return SkillDiscovery()


__all__ = ["SkillDiscovery", "create_skill_discovery"]
