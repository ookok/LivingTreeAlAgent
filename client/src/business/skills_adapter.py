"""
SkillsAdapter — Compatibility Stub
====================================

已迁移至 livingtree.core.skills.matcher。
统一技能适配入口不再需要单独模块。
"""


class SkillAdapter:
    def __init__(self):
        self._skills = []

    def register(self, skill_name: str, handler=None):
        self._skills.append({"name": skill_name, "handler": handler})

    def list(self):
        return [s["name"] for s in self._skills]


__all__ = ["SkillAdapter"]
