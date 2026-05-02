"""
Honcho 用户建模系统
==================

从交互中学习用户偏好，持续优化用户体验
"""

import re
import json
import os
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class Dialect(Enum):
    FORMAL = "formal"
    CASUAL = "casual"
    TECHNICAL = "technical"
    BRIEF = "brief"
    VERBOSE = "verbose"
    MIXED = "mixed"


class CommunicationStyle(Enum):
    DIRECT = "direct"
    EXPLAINING = "explaining"
    QUESTIONING = "questioning"
    COLLABORATIVE = "collaborative"


@dataclass
class UserPreference:
    preferred_style: CommunicationStyle = CommunicationStyle.EXPLAINING
    detail_level: str = "medium"
    include_reasoning: bool = True
    format_code: bool = True

    use_emoji: bool = False
    use_chinese: bool = True
    response_language: str = "zh-CN"

    ask_before_action: bool = True
    show_progress: bool = True
    auto_explain_errors: bool = True

    preferred_code_style: str = "pep8"
    comment_level: str = "moderate"
    variable_naming: str = "snake_case"

    confidence: float = 1.0
    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "preferred_style": self.preferred_style.value,
            "detail_level": self.detail_level,
            "include_reasoning": self.include_reasoning,
            "format_code": self.format_code,
            "use_emoji": self.use_emoji,
            "use_chinese": self.use_chinese,
            "response_language": self.response_language,
            "ask_before_action": self.ask_before_action,
            "show_progress": self.show_progress,
            "auto_explain_errors": self.auto_explain_errors,
            "preferred_code_style": self.preferred_code_style,
            "comment_level": self.comment_level,
            "variable_naming": self.variable_naming,
            "confidence": self.confidence,
            "last_updated": self.last_updated.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "UserPreference":
        pref = cls()
        for key, value in data.items():
            if hasattr(pref, key):
                if isinstance(value, str) and hasattr(CommunicationStyle, value.upper()):
                    setattr(pref, key, CommunicationStyle[value.upper()])
                else:
                    setattr(pref, key, value)
        return pref


@dataclass
class UserProfile:
    user_id: str
    name: Optional[str] = None
    role: Optional[str] = None
    dialect: Dialect = Dialect.MIXED

    preferences: UserPreference = field(default_factory=UserPreference)

    known_triggers: List[str] = field(default_factory=list)
    known_phrases: List[str] = field(default_factory=list)
    known_commands: List[str] = field(default_factory=list)

    project_context: Dict[str, Any] = field(default_factory=dict)
    recent_tasks: List[Dict] = field(default_factory=list)
    completed_work: List[str] = field(default_factory=list)

    total_interactions: int = 0
    last_seen: datetime = field(default_factory=datetime.now)
    learning_version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "role": self.role,
            "dialect": self.dialect.value,
            "preferences": self.preferences.to_dict(),
            "known_triggers": self.known_triggers,
            "known_phrases": self.known_phrases,
            "known_commands": self.known_commands,
            "project_context": self.project_context,
            "recent_tasks": self.recent_tasks[-10:],
            "completed_work": self.completed_work[-20:],
            "total_interactions": self.total_interactions,
            "last_seen": self.last_seen.isoformat(),
            "learning_version": self.learning_version,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "UserProfile":
        pref_data = data.pop("preferences", {})
        dialect_str = data.pop("dialect", "mixed")

        profile = cls(**data)
        profile.preferences = UserPreference.from_dict(pref_data)

        try:
            profile.dialect = Dialect(dialect_str)
        except ValueError:
            profile.dialect = Dialect.MIXED

        return profile


class HonchoUserModeling:
    def __init__(self, persistence_path: Optional[str] = None):
        self.persistence_path = persistence_path
        self._profiles: Dict[str, UserProfile] = {}
        self._interaction_buffer: List[Dict] = []
        self._max_buffer_size = 100

        self._dialect_indicators: Dict[Dialect, List[str]] = {
            Dialect.FORMAL: ["请", "麻烦", "能否", "谢谢", "您好", "尊敬"],
            Dialect.CASUAL: ["帮我", "搞", "搞一下", "搞定了", "ok", "好的"],
            Dialect.TECHNICAL: ["API", "SDK", "函数", "模块", "架构", "protocol"],
            Dialect.BRIEF: ["跑", "执行", "搞定", "OK", "done"],
            Dialect.VERBOSE: ["详细", "完整", "全面", "具体", "深入"],
        }

        self._style_indicators: Dict[CommunicationStyle, List[str]] = {
            CommunicationStyle.DIRECT: ["直接", "给我", "就", "只要", "只需要"],
            CommunicationStyle.EXPLAINING: ["为什么", "解释", "说明", "原因", "因为"],
            CommunicationStyle.QUESTIONING: ["吗", "是否", "要不要", "你看"],
            CommunicationStyle.COLLABORATIVE: ["我们", "一起", "合作", "讨论", "你觉得"],
        }

        self._load_profiles()

    def _load_profiles(self):
        if not self.persistence_path:
            return

        profile_file = os.path.join(self.persistence_path, "honcho_profiles.json")
        if os.path.exists(profile_file):
            try:
                with open(profile_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for user_id, profile_data in data.items():
                        self._profiles[user_id] = UserProfile.from_dict(profile_data)
                logger.info(f"[Honcho] 加载了 {len(self._profiles)} 个用户画像")
            except Exception as e:
                logger.warning(f"[Honcho] 加载用户数据失败: {e}")

    def _save_profiles(self):
        if not self.persistence_path:
            return

        os.makedirs(self.persistence_path, exist_ok=True)
        profile_file = os.path.join(self.persistence_path, "honcho_profiles.json")

        try:
            data = {uid: profile.to_dict() for uid, profile in self._profiles.items()}
            with open(profile_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[Honcho] 保存用户数据失败: {e}")

    def get_profile(self, user_id: str = "default") -> UserProfile:
        if user_id not in self._profiles:
            self._profiles[user_id] = UserProfile(user_id=user_id)
            logger.info(f"[Honcho] 创建新用户画像: {user_id}")

        profile = self._profiles[user_id]
        profile.last_seen = datetime.now()
        return profile

    def record_interaction(
        self, query: str, response: str = "",
        user_feedback: Optional[str] = None, user_id: str = "default",
        context: Optional[Dict] = None,
    ):
        profile = self.get_profile(user_id)
        profile.total_interactions += 1

        interaction = {
            "query": query, "response": response,
            "feedback": user_feedback, "context": context or {},
            "timestamp": datetime.now().isoformat(),
        }
        self._interaction_buffer.append(interaction)

        if profile.total_interactions % 10 == 0:
            self._learn_from_buffer(profile)

        self._learn_triggers(query, profile)

        if user_feedback:
            self._learn_from_feedback(user_feedback, profile)

        self._detect_dialect(query, profile)
        self._detect_style_preference(query, profile)

        if context:
            self._update_recent_tasks(context, profile)

        self._save_profiles()

    def _learn_triggers(self, query: str, profile: UserProfile):
        words = query.split()

        for i in range(len(words) - 1):
            phrase = ' '.join(words[i:i + 2])
            if phrase not in profile.known_phrases:
                profile.known_phrases.append(phrase)

        if len(query) < 20 and not any(c.isdigit() for c in query):
            for word in words[:2]:
                if word not in profile.known_triggers and len(word) > 1:
                    profile.known_triggers.append(word)

        profile.known_phrases = profile.known_phrases[-50:]
        profile.known_triggers = profile.known_triggers[-30:]

    def _learn_from_feedback(self, feedback: str, profile: UserProfile):
        feedback_lower = feedback.lower()

        positive_words = ["好", "棒", "赞", "完美", "正是", "谢谢", "great", "good", "perfect"]
        negative_words = ["不对", "不是", "错了", "不好", "差", "wrong", "bad", "not"]

        is_positive = any(w in feedback_lower for w in positive_words)
        is_negative = any(w in feedback_lower for w in negative_words)

        if is_positive:
            profile.preferences.confidence = min(1.0, profile.preferences.confidence * 1.05)
        elif is_negative:
            profile.preferences.confidence = max(0.3, profile.preferences.confidence * 0.9)

        if any(w in feedback_lower for w in ["太简单", "太basic", "not detailed"]):
            profile.preferences.detail_level = "high"
        elif any(w in feedback_lower for w in ["太复杂", "太多了", "too much"]):
            profile.preferences.detail_level = "low"

        profile.preferences.last_updated = datetime.now()

    def _detect_dialect(self, query: str, profile: UserProfile):
        query_lower = query.lower()
        dialect_scores: Dict[Dialect, int] = {d: 0 for d in Dialect}

        for dialect, indicators in self._dialect_indicators.items():
            for indicator in indicators:
                if indicator in query_lower:
                    dialect_scores[dialect] += 1

        max_score = max(dialect_scores.values())
        if max_score > 0:
            detected = max(dialect_scores, key=dialect_scores.get)
            if dialect_scores[detected] > dialect_scores.get(profile.dialect, 0):
                profile.dialect = detected
                logger.debug(f"[Honcho] 检测到方言: {detected.value}")

    def _detect_style_preference(self, query: str, profile: UserProfile):
        query_lower = query.lower()
        style_scores: Dict[CommunicationStyle, int] = {s: 0 for s in CommunicationStyle}

        for style, indicators in self._style_indicators.items():
            for indicator in indicators:
                if indicator in query_lower:
                    style_scores[style] += 1

        max_score = max(style_scores.values())
        if max_score > 0:
            detected = max(style_scores, key=style_scores.get)
            if style_scores[detected] > 2:
                profile.preferences.preferred_style = detected

    def _update_recent_tasks(self, context: Dict, profile: UserProfile):
        task = {
            "type": context.get("task_type", "unknown"),
            "description": context.get("description", "")[:100],
            "timestamp": datetime.now().isoformat(),
        }

        profile.recent_tasks.append(task)
        profile.recent_tasks = profile.recent_tasks[-20:]

    def _learn_from_buffer(self, profile: UserProfile):
        if not self._interaction_buffer:
            return

        recent = self._interaction_buffer[-10:]

        successful = sum(1 for i in recent if i.get("feedback") and
                        any(w in i["feedback"].lower() for w in ["好", "棒", "ok", "good", "perfect"]))
        failed = len(recent) - successful

        if failed > 6:
            logger.info(f"[Honcho] 检测到交互质量下降: 成功率 {successful}/{len(recent)}")
            profile.learning_version += 1

        self._interaction_buffer = []

    def adapt_response(
        self, base_response: str, user_id: str = "default",
        profile: Optional[UserProfile] = None,
    ) -> str:
        if profile is None:
            profile = self.get_profile(user_id)

        pref = profile.preferences
        adapted = base_response

        if pref.detail_level == "low":
            adapted = self._simplify_response(adapted)
        elif pref.detail_level == "high":
            adapted = self._expand_response(adapted)

        if pref.include_reasoning and "reasoning" not in adapted.lower():
            adapted = self._add_reasoning(adapted)

        return adapted

    def _simplify_response(self, response: str) -> str:
        lines = response.split('\n')
        simplified = []
        for line in lines:
            if len(line) < 200 or ':' in line or '#' in line:
                simplified.append(line)
        return '\n'.join(simplified) if simplified else response

    def _expand_response(self, response: str) -> str:
        if "```" in response:
            response += "\n\n> 以上代码可直接使用。"
        return response

    def _add_reasoning(self, response: str) -> str:
        return f"**分析：**\n{response}\n\n**结论：** 如上所示。"

    def _contains_chinese(self, text: str) -> bool:
        return bool(re.search(r'[\u4e00-\u9fff]', text))

    def adapt_query(self, query: str, user_id: str = "default") -> str:
        profile = self.get_profile(user_id)

        expansions = {
            "跑": "执行并运行", "测": "测试", "查": "查询",
            "看": "查看", "写": "编写",
        }

        adapted = query
        for short, full in expansions.items():
            if query.startswith(short) and len(query) < 10:
                adapted = f"{full}{query[1:]}"
                break

        return adapted

    def get_context_for_query(self, query: str, user_id: str = "default") -> Dict[str, Any]:
        profile = self.get_profile(user_id)

        context = {
            "project": profile.project_context,
            "recent_tasks": profile.recent_tasks[-3:],
            "dialect": profile.dialect.value,
            "style": profile.preferences.preferred_style.value,
        }

        query_keywords = set(query.lower().split())
        related_work = [
            w for w in profile.completed_work
            if any(kw in w.lower() for kw in query_keywords)
        ]

        if related_work:
            context["related_completed"] = related_work[:5]

        return context

    def remember_completed_work(self, description: str, user_id: str = "default"):
        profile = self.get_profile(user_id)
        profile.completed_work.append(description)
        profile.completed_work = profile.completed_work[-50:]
        self._save_profiles()

    def update_project_context(self, key: str, value: Any, user_id: str = "default"):
        profile = self.get_profile(user_id)
        profile.project_context[key] = value
        self._save_profiles()

    def get_report(self, user_id: str = "default") -> Dict[str, Any]:
        profile = self.get_profile(user_id)

        return {
            "user_id": user_id,
            "name": profile.name,
            "role": profile.role,
            "dialect": profile.dialect.value,
            "style": profile.preferences.preferred_style.value,
            "detail_level": profile.preferences.detail_level,
            "total_interactions": profile.total_interactions,
            "known_triggers_count": len(profile.known_triggers),
            "known_phrases_count": len(profile.known_phrases),
            "recent_tasks_count": len(profile.recent_tasks),
            "completed_work_count": len(profile.completed_work),
            "confidence": profile.preferences.confidence,
            "learning_version": profile.learning_version,
        }
