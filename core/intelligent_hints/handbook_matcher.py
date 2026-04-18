"""
智能提示系统 — Handbook 加载器与匹配器
======================================
零网络匹配，直接读取 handbooks/*.json 场景规则

条件表达式支持：
- ">80" / "<50" / ">=70" / "<=90"
- ["value1", "value2"] 列表任一匹配
- "exact_value" 精确匹配
- {"key": "nested.value"} 嵌套访问
"""

import json
import os
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Any, Tuple
from datetime import datetime
import threading

from .models import ContextInfo, GeneratedHint, HintType, HintLevel
from .global_signals import HintSignal


@dataclass
class HandbookRule:
    """Handbook 规则"""
    rule_id: str
    conditions: Dict[str, Any]       # 条件表达式
    priority: int
    template: Dict[str, str]         # emoji, title, content, level

    def match(self, context: ContextInfo, payload: Dict = None) -> bool:
        """检查条件是否匹配"""
        payload = payload or {}
        return match_conditions(self.conditions, context, payload)


@dataclass
class HandbookScene:
    """Handbook 场景"""
    scene_id: str
    scene_name: str
    description: str
    rules: List[HandbookRule]
    chat_templates: Dict[str, Any]   # intro, questions
    hide_messages: Dict[str, str]    # temp, perma

    @classmethod
    def from_dict(cls, data: dict) -> "HandbookScene":
        rules = [
            HandbookRule(
                rule_id=r["rule_id"],
                conditions=r["conditions"],
                priority=r.get("priority", 0),
                template=r["template"]
            )
            for r in data.get("rules", [])
        ]
        return cls(
            scene_id=data["scene_id"],
            scene_name=data["scene_name"],
            description=data.get("description", ""),
            rules=rules,
            chat_templates=data.get("chat_templates", {}),
            hide_messages=data.get("hide_messages", {"temp": "好的~", "perma": "好的 🌿"})
        )


def match_conditions(conditions: Dict[str, Any], context: ContextInfo, payload: Dict) -> bool:
    """匹配条件表达式"""
    for key, expected in conditions.items():
        actual = resolve_value(key, context, payload)

        if actual is None:
            # 尝试从 payload 获取
            actual = payload.get(key)

        if actual is None:
            return False

        # 比较
        if not compare_values(actual, expected):
            return False

    return True


def resolve_value(key: str, context: ContextInfo, payload: Dict) -> Any:
    """解析嵌套值"""
    # 支持 device_info.xxx, user_profile.xxx, payload.xxx
    parts = key.split(".")
    current = None

    if parts[0] == "device_info":
        current = context.device_info
        parts = parts[1:]
    elif parts[0] == "user_profile":
        current = context.user_profile
        parts = parts[1:]
    elif parts[0] == "payload":
        current = payload
        parts = parts[1:]
    else:
        # 尝试从 context 直接访问
        if hasattr(context, key):
            return getattr(context, key)
        return None

    # 遍历嵌套
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        elif hasattr(current, part):
            current = getattr(current, part)
        else:
            return None

    return current


def compare_values(actual: Any, expected: Any) -> bool:
    """比较值，支持条件表达式"""
    # 字符串比较表达式
    if isinstance(expected, str):
        # 处理 > < >= <=
        match = re.match(r'^(>=|<=|>|<)(.+)$', expected.strip())
        if match:
            op, val = match.groups()
            try:
                num_val = float(val)
                num_actual = float(actual)
                if op == ">":
                    return num_actual > num_val
                elif op == "<":
                    return num_actual < num_val
                elif op == ">=":
                    return num_actual >= num_val
                elif op == "<=":
                    return num_actual <= num_val
            except (ValueError, TypeError):
                return False

        # 列表匹配
        if isinstance(actual, list):
            return expected in actual

        # 精确匹配
        return str(actual) == expected

    # 列表匹配（expected 是列表，任一匹配）
    if isinstance(expected, list):
        return actual in expected

    return actual == expected


class HandbookLoader:
    """
    Handbook 加载器

    从 handbooks/*.json 加载场景规则
    """

    def __init__(self, handbook_dir: str = None):
        if handbook_dir is None:
            handbook_dir = Path(__file__).parent / "handbooks"
        self.handbook_dir = Path(handbook_dir)
        self._scenes: Dict[str, HandbookScene] = {}
        self._lock = threading.RLock()
        self._load_all()

    def _load_all(self):
        """加载所有 handbook"""
        if not self.handbook_dir.exists():
            return

        for json_file in self.handbook_dir.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    scene = HandbookScene.from_dict(data)
                    self._scenes[scene.scene_id] = scene
            except Exception as e:
                print(f"Failed to load handbook {json_file}: {e}")

    def get_scene(self, scene_id: str) -> Optional[HandbookScene]:
        """获取场景"""
        with self._lock:
            return self._scenes.get(scene_id)

    def get_all_scenes(self) -> Dict[str, HandbookScene]:
        """获取所有场景"""
        with self._lock:
            return self._scenes.copy()

    def reload(self):
        """重新加载"""
        with self._lock:
            self._scenes.clear()
            self._load_all()


class HandbookMatcher:
    """
    Handbook 匹配器

    根据 ContextInfo 和 Payload 匹配最佳规则
    """

    def __init__(self, loader: HandbookLoader = None):
        self.loader = loader or HandbookLoader()

    def match(
        self,
        scene_id: str,
        context: ContextInfo,
        payload: Dict[str, Any] = None
    ) -> Optional[Tuple[HandbookRule, HandbookScene]]:
        """
        匹配最佳规则

        Returns:
            (匹配的规则, 所属场景) 或 None
        """
        scene = self.loader.get_scene(scene_id)
        if not scene:
            # 尝试 default 场景
            scene = self.loader.get_scene("default")
            if not scene:
                return None

        best_rule = None
        best_priority = -1

        for rule in scene.rules:
            if rule.match(context, payload or {}):
                if rule.priority > best_priority:
                    best_priority = rule.priority
                    best_rule = rule

        if best_rule:
            return best_rule, scene

        return None

    def generate_hint(
        self,
        scene_id: str,
        context: ContextInfo,
        payload: Dict[str, Any] = None
    ) -> Optional[GeneratedHint]:
        """根据匹配生成提示"""
        result = self.match(scene_id, context, payload)
        if not result:
            return None

        rule, scene = result
        tpl = rule.template

        # 填充模板变量
        content = tpl["content"]
        content = content.replace("{option_count}", str(len(context.options) if context.options else 0))

        # 填充 payload 变量
        if payload:
            for key, val in payload.items():
                content = content.replace(f"{{{key}}}", str(val))

        level = HintLevel(tpl.get("level", "glow"))

        return GeneratedHint(
            hint_id=f"hb_{rule.rule_id}_{scene_id}",
            hint_type=self._guess_hint_type(scene_id),
            hint_level=level,
            title=tpl.get("title", ""),
            content=content,
            emoji=tpl.get("emoji", "💡"),
            context=context,
            source="handbook",
            confidence=rule.priority / 100.0
        )

    def _guess_hint_type(self, scene_id: str) -> HintType:
        """猜测提示类型"""
        type_map = {
            "model_select": HintType.COMPARISON_HINT,
            "chat": HintType.PROACTIVE_HELP,
            "writing": HintType.PROACTIVE_HELP,
            "network_issue": HintType.ACTION_SUGGESTION,
            "low_performance": HintType.ACTION_SUGGESTION,
        }
        return type_map.get(scene_id, HintType.PROACTIVE_HELP)

    def get_chat_intro(self, scene_id: str) -> str:
        """获取聊天引导语"""
        scene = self.loader.get_scene(scene_id)
        if not scene:
            return "有什么想问的？"
        return scene.chat_templates.get("intro", "有什么想问的？")

    def get_chat_questions(self, scene_id: str) -> List[str]:
        """获取预设问题"""
        scene = self.loader.get_scene(scene_id)
        if not scene:
            return []
        return scene.chat_templates.get("questions", [])

    def get_hide_message(self, scene_id: str, hide_type: str = "temp") -> str:
        """获取隐藏提示语"""
        scene = self.loader.get_scene(scene_id)
        if not scene:
            return "好的~"
        return scene.hide_messages.get(hide_type, "好的~")


# 全局单例
_loader: Optional[HandbookLoader] = None
_matcher: Optional[HandbookMatcher] = None


def get_handbook_loader() -> HandbookLoader:
    global _loader
    if _loader is None:
        _loader = HandbookLoader()
    return _loader


def get_handbook_matcher() -> HandbookMatcher:
    global _matcher
    if _matcher is None:
        _matcher = HandbookMatcher(get_handbook_loader())
    return _matcher
