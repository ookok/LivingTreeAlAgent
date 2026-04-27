"""
智能提示系统 — 提示记忆管理
============================
集成 MemPalace，永久记忆用户的"别烦我"选择

特性：
- 场景级别永久隐藏
- 规则级别永久隐藏
- 用户偏好学习
- 记忆衰减（可选）
"""

import json
import threading
from typing import Dict, Set, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .models import HintConfig


@dataclass
class HideRecord:
    """隐藏记录"""
    scene_id: str
    rule_id: str = ""                    # 空表示整个场景
    hide_type: str = "perma"            # temp / perma
    created_at: datetime = field(default_factory=datetime.now)
    dismissed_count: int = 0            # 被忽略次数（用于统计）
    last_dismissed: Optional[datetime] = None


class HintMemory:
    """
    提示记忆管理

    功能：
    1. 永久隐藏记忆（MemPalace 持久化）
    2. 临时隐藏（仅内存）
    3. 用户偏好学习
    4. 记忆衰减
    """

    def __init__(self, config: HintConfig = None, storage_path: str = None):
        self.config = config or HintConfig()

        # 存储路径
        if storage_path is None:
            storage_path = Path.home() / ".hermes-desktop" / "hint_memory.json"
        self.storage_path = Path(storage_path)

        # 永久隐藏记录
        self._perma_hides: Dict[str, HideRecord] = {}  # key = "scene_id:rule_id"

        # 临时隐藏（内存）
        self._temp_hides: Dict[str, datetime] = {}    # key = scene_id

        # 临时隐藏有效期（秒）
        self._temp_hide_ttl = 3600  # 1小时

        # 用户偏好
        self._preferences: Dict[str, Any] = {}

        # 加载持久化数据
        self._load()

    def _load(self):
        """加载持久化数据"""
        if not self.storage_path.exists():
            return

        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 恢复永久隐藏记录
            for key, record_data in data.get("perma_hides", {}).items():
                record = HideRecord(
                    scene_id=record_data["scene_id"],
                    rule_id=record_data.get("rule_id", ""),
                    hide_type=record_data.get("hide_type", "perma"),
                    created_at=datetime.fromisoformat(record_data["created_at"]),
                    dismissed_count=record_data.get("dismissed_count", 0),
                )
                self._perma_hides[key] = record

            # 恢复用户偏好
            self._preferences = data.get("preferences", {})

        except Exception as e:
            print(f"Failed to load hint memory: {e}")

    def _save(self):
        """保存持久化数据"""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "perma_hides": {
                key: {
                    "scene_id": r.scene_id,
                    "rule_id": r.rule_id,
                    "hide_type": r.hide_type,
                    "created_at": r.created_at.isoformat(),
                    "dismissed_count": r.dismissed_count,
                }
                for key, r in self._perma_hides.items()
            },
            "preferences": self._preferences,
        }

        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save hint memory: {e}")

    # ── 隐藏控制 ────────────────────────────────────────────

    def is_hidden(self, scene_id: str, rule_id: str = "") -> bool:
        """检查是否被隐藏"""
        key = f"{scene_id}:{rule_id}"

        # 检查永久隐藏
        if key in self._perma_hides:
            return True

        # 检查临时隐藏（可能已过期）
        if scene_id in self._temp_hides:
            expire_time = self._temp_hides[scene_id]
            if (datetime.now() - expire_time).total_seconds() < self._temp_hide_ttl:
                return True
            else:
                # 已过期，删除
                del self._temp_hides[scene_id]

        return False

    def hide_scene(
        self,
        scene_id: str,
        rule_id: str = "",
        hide_type: str = "perma",
        remember: bool = True
    ) -> None:
        """
        隐藏场景/规则

        Args:
            scene_id: 场景ID
            rule_id: 规则ID（空表示整个场景）
            hide_type: temp / perma
            remember: 是否持久化（仅 hide_type=perma 时有效）
        """
        key = f"{scene_id}:{rule_id}"

        if hide_type == "perma" and remember:
            # 永久隐藏
            record = HideRecord(
                scene_id=scene_id,
                rule_id=rule_id,
                hide_type="perma",
            )
            self._perma_hides[key] = record
            self._save()

            # 如果是整个场景隐藏，也添加到 MemPalace
            if not rule_id:
                self._remember_in_mempalace(scene_id)

        else:
            # 临时隐藏
            self._temp_hides[scene_id] = datetime.now()

        # 记录忽略
        if key in self._perma_hides:
            self._perma_hides[key].dismissed_count += 1
            self._perma_hides[key].last_dismissed = datetime.now()

    def unhide_scene(self, scene_id: str, rule_id: str = "") -> None:
        """取消隐藏"""
        key = f"{scene_id}:{rule_id}"

        # 删除永久隐藏
        if key in self._perma_hides:
            del self._perma_hides[key]
            self._save()

        # 删除临时隐藏
        if scene_id in self._temp_hides:
            del self._temp_hides[scene_id]

    def clear_perma_hides(self) -> None:
        """清除所有永久隐藏"""
        self._perma_hides.clear()
        self._save()

    # ── 用户偏好 ───────────────────────────────────────────

    def set_preference(self, key: str, value: Any) -> None:
        """设置用户偏好"""
        self._preferences[key] = value
        if self.config.learn_from_user:
            self._save()

    def get_preference(self, key: str, default: Any = None) -> Any:
        """获取用户偏好"""
        return self._preferences.get(key, default)

    def learn_from_action(
        self,
        scene_id: str,
        action: str,
        result: str
    ) -> None:
        """
        从用户行为学习

        例如：
        - 用户选择了"免费"模型 → 偏好免费
        - 用户总是忽略某类提示 → 降低该类提示频率
        """
        if not self.config.learn_from_user:
            return

        # 学习模型选择偏好
        if scene_id == "model_select":
            if "免费" in action or "free" in action.lower():
                self.set_preference("prefers_free", True)
            if "快" in action or "speed" in action.lower():
                self.set_preference("prioritizes", "speed")
            if "强" in action or "quality" in action.lower():
                self.set_preference("prioritizes", "quality")

        # 学习忽略行为
        key = f"ignore_count_{scene_id}"
        current = self.get_preference(key, 0)
        if result == "dismissed":
            self.set_preference(key, current + 1)

    # ── MemPalace 集成 ────────────────────────────────────

    def _remember_in_mempalace(self, scene_id: str) -> None:
        """在 MemPalace 中记忆"""
        try:
            from client.src.business.memory_palace import get_memory_palace, MemoryLevel

            palace = get_memory_palace()

            # 获取或创建 palace
            user_id = "local_user"  # 简化版
            palace_data = palace.recall_user_context(user_id)

            if not palace_data["palace"]:
                palace.create_palace(user_id)

            # 存储为抽屉事实
            palace.store_fact(
                room_id="hint_settings",
                fact_type="hidden_scene",
                content=f"用户选择隐藏场景: {scene_id}",
                source="intelligent_hints",
                importance=0.8
            )

        except ImportError:
            # MemPalace 未安装，仅使用本地存储
            pass

    def get_hidden_scenes(self) -> Set[str]:
        """获取所有被隐藏的场景"""
        return {record.scene_id for record in self._perma_hides.values()}

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "perma_hides": len(self._perma_hides),
            "temp_hides": len(self._temp_hides),
            "preferences": len(self._preferences),
            "hidden_scenes": list(self.get_hidden_scenes()),
        }


# 全局单例
_memory_instance: Optional[HintMemory] = None
_memory_lock = threading.Lock()


def get_hint_memory() -> HintMemory:
    """获取提示记忆单例"""
    global _memory_instance
    with _memory_lock:
        if _memory_instance is None:
            _memory_instance = HintMemory()
        return _memory_instance
