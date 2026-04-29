# patch_transition.py — 补丁安全过渡系统

import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib


logger = logging.getLogger(__name__)


# ============ 补丁遗留状态 ============

class LegacyStatus:
    """补丁遗留状态"""
    LEGACY_APPLIED = "legacy_applied"     # 已应用，标记为遗留
    LEGACY_REJECTED = "legacy_rejected"  # 已拒绝，标记为遗留
    PENDING_REVIEW = "pending_review"    # 待重审
    ACTIVE = "active"                   # 活动中
    MERGED = "merged"                   # 已合并到开源库


# ============ 补丁过渡记录 ============

@dataclass
class LegacyPatchInfo:
    """遗留补丁信息"""
    patch_id: str
    module: str
    legacy_status: str
    original_patch_data: Dict[str, Any]
    applied_at: Optional[int] = None
    marked_legacy_at: Optional[int] = None
    review_notes: str = ""
    conflict_with_oss: bool = False
    suggested_action: str = ""
    reviewed_by: str = ""  # "system" / "user"
    reviewed_at: Optional[int] = None


# ============ 补丁安全过渡管理器 ============

class PatchTransitionManager:
    """
    补丁安全过渡管理器

    功能:
    1. 升级后守护 - 已应用补丁标记为 legacy
    2. 未应用补丁重新评估 - 用新开源库能力重新评估
    3. 冲突检测 - 检测补丁与开源库的冲突
    4. 用户确认流程 - 审核室提示用户确认
    """

    def __init__(
        self,
        data_dir: Path = None,
        existing_patches_getter: Callable = None,
    ):
        if data_dir is None:
            data_dir = Path.home() / ".hermes-desktop" / "upgrade_scanner" / "patch_transition"
        data_dir.mkdir(parents=True, exist_ok=True)
        self._data_dir = data_dir

        # 外部补丁获取函数
        self._existing_patches_getter = existing_patches_getter

        # 遗留补丁存储
        self._legacy_file = data_dir / "legacy_patches.json"
        self._pending_review_file = data_dir / "pending_review.json"
        self._legacy_patches: Dict[str, LegacyPatchInfo] = {}
        self._pending_review: Dict[str, LegacyPatchInfo] = {}

        self._load_data()

    def _load_data(self):
        """加载数据"""
        # 加载遗留补丁
        if self._legacy_file.exists():
            try:
                data = json.loads(self._legacy_file.read_text(encoding="utf-8"))
                for k, v in data.items():
                    self._legacy_patches[k] = LegacyPatchInfo(**v)
            except Exception:
                pass

        # 加载待审核补丁
        if self._pending_review_file.exists():
            try:
                data = json.loads(self._pending_review_file.read_text(encoding="utf-8"))
                for k, v in data.items():
                    self._pending_review[k] = LegacyPatchInfo(**v)
            except Exception:
                pass

    def _save_data(self):
        """保存数据"""
        try:
            # 保存遗留补丁
            legacy_data = {
                k: {
                    "patch_id": v.patch_id,
                    "module": v.module,
                    "legacy_status": v.legacy_status,
                    "original_patch_data": v.original_patch_data,
                    "applied_at": v.applied_at,
                    "marked_legacy_at": v.marked_legacy_at,
                    "review_notes": v.review_notes,
                    "conflict_with_oss": v.conflict_with_oss,
                    "suggested_action": v.suggested_action,
                    "reviewed_by": v.reviewed_by,
                    "reviewed_at": v.reviewed_at,
                }
                for k, v in self._legacy_patches.items()
            }
            self._legacy_file.write_text(
                json.dumps(legacy_data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

            # 保存待审核补丁
            review_data = {
                k: {
                    "patch_id": v.patch_id,
                    "module": v.module,
                    "legacy_status": v.legacy_status,
                    "original_patch_data": v.original_patch_data,
                    "applied_at": v.applied_at,
                    "marked_legacy_at": v.marked_legacy_at,
                    "review_notes": v.review_notes,
                    "conflict_with_oss": v.conflict_with_oss,
                    "suggested_action": v.suggested_action,
                    "reviewed_by": v.reviewed_by,
                    "reviewed_at": v.reviewed_at,
                }
                for k, v in self._pending_review.items()
            }
            self._pending_review_file.write_text(
                json.dumps(review_data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            logger.error(f"Failed to save data: {e}")

    def mark_legacy(
        self,
        patch_id: str,
        module: str,
        patch_data: Dict[str, Any],
        reason: str = "",
    ) -> LegacyPatchInfo:
        """
        将已应用补丁标记为遗留

        Args:
            patch_id: 补丁ID
            module: 模块名
            patch_data: 原始补丁数据
            reason: 标记原因

        Returns:
            LegacyPatchInfo: 遗留补丁信息
        """
        info = LegacyPatchInfo(
            patch_id=patch_id,
            module=module,
            legacy_status=LegacyStatus.LEGACY_APPLIED,
            original_patch_data=patch_data,
            applied_at=patch_data.get("applied_at"),
            marked_legacy_at=int(time.time()),
            review_notes=reason,
            suggested_action="disable",  # 默认建议禁用
            reviewed_by="system",
            reviewed_at=int(time.time()),
        )

        self._legacy_patches[patch_id] = info
        self._save_data()

        logger.info(f"Marked patch {patch_id} as legacy for module {module}")
        return info

    def mark_pending_review(
        self,
        patch_id: str,
        module: str,
        patch_data: Dict[str, Any],
        suggested_action: str = "",
    ) -> LegacyPatchInfo:
        """
        将补丁标记为待重审

        Args:
            patch_id: 补丁ID
            module: 模块名
            patch_data: 原始补丁数据
            suggested_action: 建议操作

        Returns:
            LegacyPatchInfo: 待审核补丁信息
        """
        info = LegacyPatchInfo(
            patch_id=patch_id,
            module=module,
            legacy_status=LegacyStatus.PENDING_REVIEW,
            original_patch_data=patch_data,
            applied_at=patch_data.get("applied_at"),
            suggested_action=suggested_action,
        )

        self._pending_review[patch_id] = info
        self._save_data()

        logger.info(f"Marked patch {patch_id} as pending review for module {module}")
        return info

    def reevaluate_with_oss(
        self,
        patch_id: str,
        oss_library_info: Dict[str, Any],
    ) -> LegacyPatchInfo:
        """
        用开源库能力重新评估补丁

        Args:
            patch_id: 补丁ID
            oss_library_info: 开源库信息

        Returns:
            LegacyPatchInfo: 重新评估后的信息
        """
        if patch_id not in self._pending_review:
            return None

        info = self._pending_review[patch_id]
        patch_data = info.original_patch_data

        # 分析冲突
        conflict, reason = self._analyze_conflict(patch_data, oss_library_info)

        info.conflict_with_oss = conflict
        info.review_notes = reason
        info.suggested_action = self._suggest_action(conflict, info)

        self._save_data()
        return info

    def _analyze_conflict(
        self,
        patch_data: Dict[str, Any],
        oss_info: Dict[str, Any],
    ) -> tuple:
        """
        分析补丁与开源库的冲突

        Returns:
            (conflict: bool, reason: str)
        """
        module = patch_data.get("module", "")
        new_value = patch_data.get("new_value")
        action = patch_data.get("action", "")

        oss_module = oss_info.get("module", "")
        if module != oss_module:
            return False, "Different modules"

        # 检查配置项冲突
        # 如果开源库已有类似配置，补丁可能多余
        if "timeout" in module.lower():
            if isinstance(new_value, (int, float)):
                return True, f"OSS library may have different timeout defaults: {new_value}"
        elif "cache" in module.lower():
            return True, "OSS library may have built-in caching"
        elif "retry" in module.lower():
            return True, "OSS library may have different retry logic"

        return False, "No conflict detected"

    def _suggest_action(self, conflict: bool, info: LegacyPatchInfo) -> str:
        """建议操作"""
        if conflict:
            return "disable_conflict"
        else:
            return "keep_enhanced"

    def confirm_review(
        self,
        patch_id: str,
        action: str,
        user_confirmed: bool = False,
    ) -> bool:
        """
        确认审核结果

        Args:
            patch_id: 补丁ID
            action: 执行动作 (keep/disable/merge)
            user_confirmed: 是否用户确认

        Returns:
            bool: 是否成功
        """
        # 先在pending中找
        if patch_id in self._pending_review:
            info = self._pending_review[patch_id]
            info.reviewed_by = "user" if user_confirmed else "system"
            info.reviewed_at = int(time.time())

            if action == "disable":
                info.legacy_status = LegacyStatus.LEGACY_REJECTED
                del self._pending_review[patch_id]
                self._legacy_patches[patch_id] = info
            elif action == "keep":
                info.legacy_status = LegacyStatus.ACTIVE
                del self._pending_review[patch_id]
            elif action == "merge":
                info.legacy_status = LegacyStatus.MERGED
                del self._pending_review[patch_id]
                self._legacy_patches[patch_id] = info

            self._save_data()
            return True

        # 然后在legacy中找
        if patch_id in self._legacy_patches:
            info = self._legacy_patches[patch_id]
            info.reviewed_by = "user" if user_confirmed else "system"
            info.reviewed_at = int(time.time())

            if action == "reactivate":
                info.legacy_status = LegacyStatus.ACTIVE
            elif action == "remove":
                info.legacy_status = LegacyStatus.LEGACY_REJECTED

            self._save_data()
            return True

        return False

    def get_legacy_patches(self) -> List[LegacyPatchInfo]:
        """获取所有遗留补丁"""
        return list(self._legacy_patches.values())

    def get_pending_review(self) -> List[LegacyPatchInfo]:
        """获取所有待审核补丁"""
        return list(self._pending_review.values())

    def get_patch_info(self, patch_id: str) -> Optional[LegacyPatchInfo]:
        """获取补丁信息"""
        if patch_id in self._pending_review:
            return self._pending_review[patch_id]
        if patch_id in self._legacy_patches:
            return self._legacy_patches[patch_id]
        return None

    def is_legacy(self, patch_id: str) -> bool:
        """检查是否为遗留补丁"""
        return patch_id in self._legacy_patches

    def is_pending_review(self, patch_id: str) -> bool:
        """检查是否待审核"""
        return patch_id in self._pending_review

    def generate_review_notifications(self) -> List[Dict[str, Any]]:
        """
        生成审核通知

        Returns:
            List[Dict]: 通知列表
        """
        notifications = []

        for patch_id, info in self._pending_review.items():
            notifications.append({
                "type": "patch_review",
                "patch_id": patch_id,
                "module": info.module,
                "title": f"补丁需要重新评估: {info.module}",
                "message": info.review_notes or "开源库更新后，此补丁需要重新评估",
                "suggested_action": info.suggested_action,
                "priority": "high" if info.conflict_with_oss else "medium",
                "created_at": info.marked_legacy_at or int(time.time()),
            })

        return notifications

    def execute_upgrade_transition(
        self,
        upgraded_modules: List[str],
        oss_candidates: Dict[str, Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        执行升级后补丁过渡

        Args:
            upgraded_modules: 已升级的模块列表
            oss_candidates: 开源库候选信息 {module: oss_info}

        Returns:
            Dict: 执行结果
        """
        if oss_candidates is None:
            oss_candidates = {}

        results = {
            "marked_legacy": [],
            "pending_review": [],
            "no_change": [],
        }

        # 获取现有补丁
        existing_patches = []
        if self._existing_patches_getter:
            try:
                existing_patches = self._existing_patches_getter()
            except Exception as e:
                logger.warning(f"Failed to get existing patches: {e}")

        # 遍历已应用补丁
        for patch in existing_patches:
            patch_id = patch.get("id")
            module = patch.get("module")
            status = patch.get("status", "")

            # 只处理已应用且涉及升级模块的补丁
            if status != "applied" or module not in upgraded_modules:
                continue

            # 检查是否已有开源库替代
            oss_info = oss_candidates.get(module)

            if oss_info:
                # 标记为待审核
                info = self.mark_pending_review(
                    patch_id=patch_id,
                    module=module,
                    patch_data=patch,
                    suggested_action=self._suggest_action(True, LegacyPatchInfo("", "", "")),
                )
                results["pending_review"].append({
                    "patch_id": patch_id,
                    "module": module,
                    "reason": "OSS library available",
                })

                # 用开源库信息重新评估
                self.reevaluate_with_oss(patch_id, oss_info)
            else:
                # 标记为遗留
                self.mark_legacy(
                    patch_id=patch_id,
                    module=module,
                    patch_data=patch,
                    reason="Module upgraded, patch marked as legacy",
                )
                results["marked_legacy"].append({
                    "patch_id": patch_id,
                    "module": module,
                })

        self._save_data()
        return results


# ============ 审核室UI数据生成器 ============

class ReviewRoomGenerator:
    """
    审核室数据生成器

    生成供UI显示的审核室数据
    """

    def __init__(self, transition_manager: PatchTransitionManager):
        self._manager = transition_manager

    def generate_review_cards(self) -> List[Dict[str, Any]]:
        """
        生成审核卡片

        Returns:
            List[Dict]: 审核卡片列表
        """
        cards = []

        # 待审核补丁
        for info in self._manager.get_pending_review():
            cards.append({
                "type": "review_card",
                "id": f"review_{info.patch_id}",
                "title": f"补丁重审: {info.module}",
                "patch_id": info.patch_id,
                "module": info.module,
                "status": "needs_review",
                "conflict": info.conflict_with_oss,
                "suggested_action": info.suggested_action,
                "notes": info.review_notes,
                "actions": [
                    {"id": "keep", "label": "保留补丁", "icon": "✓"},
                    {"id": "disable", "label": "禁用补丁", "icon": "✗"},
                    {"id": "merge", "label": "合并到开源", "icon": "↗"},
                ],
                "priority": "high" if info.conflict_with_oss else "medium",
                "created_at": info.marked_legacy_at,
            })

        # 遗留补丁
        for info in self._manager.get_legacy_patches():
            cards.append({
                "type": "legacy_card",
                "id": f"legacy_{info.patch_id}",
                "title": f"遗留补丁: {info.module}",
                "patch_id": info.patch_id,
                "module": info.module,
                "status": info.legacy_status,
                "applied_at": info.applied_at,
                "marked_legacy_at": info.marked_legacy_at,
                "actions": [
                    {"id": "reactivate", "label": "重新激活", "icon": "↻"},
                    {"id": "remove", "label": "彻底移除", "icon": "🗑"},
                ],
            })

        return cards

    def generate_summary(self) -> Dict[str, Any]:
        """生成审核摘要"""
        pending = self._manager.get_pending_review()
        legacy = self._manager.get_legacy_patches()

        return {
            "total_pending": len(pending),
            "total_legacy": len(legacy),
            "high_priority": sum(1 for p in pending if p.conflict_with_oss),
            "medium_priority": sum(1 for p in pending if not p.conflict_with_oss),
            "recommendations": self._generate_recommendations(pending, legacy),
        }

    def _generate_recommendations(
        self,
        pending: List[LegacyPatchInfo],
        legacy: List[LegacyPatchInfo],
    ) -> List[str]:
        """生成建议列表"""
        recommendations = []

        if len(pending) > 0:
            recommendations.append(f"有 {len(pending)} 个补丁需要重新评估")

        if sum(1 for p in pending if p.conflict_with_oss) > 0:
            recommendations.append("存在与开源库冲突的补丁，建议优先处理")

        if len(legacy) > 5:
            recommendations.append(f"有 {len(legacy)} 个遗留补丁，可考虑清理")

        if not recommendations:
            recommendations.append("系统状态良好，无待处理事项")

        return recommendations


# ============ 全局实例 ============

_transition_manager: Optional[PatchTransitionManager] = None


def get_transition_manager() -> PatchTransitionManager:
    """获取过渡管理器"""
    global _transition_manager
    if _transition_manager is None:
        _transition_manager = PatchTransitionManager()
    return _transition_manager
