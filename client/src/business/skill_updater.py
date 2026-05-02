"""
SkillUpdater — Compatibility Stub
===================================

已迁移至 livingtree.core.skills.matcher 的 SkillLoader。
热更新能力整合入 SkillLoader 中。
"""


class SkillUpdater:
    def __init__(self):
        self._last_updated = None

    def check_updates(self) -> list:
        return []

    def apply_update(self, skill_name: str, new_definition: dict) -> bool:
        return True


__all__ = ["SkillUpdater"]
