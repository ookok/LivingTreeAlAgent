"""ChatProfile — Import chat history, build user profiles from WeChat/Feishu exports.

Bridges the gap between live chat (ChannelBridge) and user profiling (UserModel):
  1. ChatHistoryImporter: parse exported chat logs (txt/CSV/JSON from WeChat/Feishu)
  2. BatchProfileBuilder: process chat history → extract traits → build user profile
  3. ChannelToUserAdapter: route live ChannelBridge messages → UserModel + PersonaMemory

Usage:
    builder = BatchProfileBuilder()
    profile = builder.from_wechat_export("data/wechat_chat.txt")
    # → {name: "张三", traits: {expertise:["环评"], style:"formal", ...}, 
    #    interests: [...], habits: [...], relationships: {...}}
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from loguru import logger


@dataclass
class ChatMessage:
    """A single parsed chat message."""
    platform: str        # wechat | wework | feishu | dingtalk
    sender: str
    content: str
    timestamp: str = ""
    group_name: str = ""
    message_type: str = "text"  # text | image | file | system


@dataclass
class UserProfile:
    """User profile extracted from chat history."""
    user_id: str
    name: str = ""
    platform: str = ""
    total_messages: int = 0
    active_hours: list[int] = field(default_factory=list)
    expertise: list[str] = field(default_factory=list)
    interests: list[str] = field(default_factory=list)
    communication_style: str = ""      # formal | casual | technical
    response_pattern: str = ""         # quick | delayed | selective
    common_phrases: list[str] = field(default_factory=list)
    relationships: dict[str, int] = field(default_factory=dict)  # contact → message_count
    sentiment: str = ""               # positive | neutral | negative
    question_ratio: float = 0.0
    avg_message_length: float = 0.0
    last_updated: str = ""


# ═══ 1. Chat History Importer ═════════════════════════════════════

class ChatHistoryImporter:
    """Parse exported chat logs from various platforms."""

    # WeChat export format (PC version)
    # 2024-01-15 14:30:25 张三
    # 这是一条消息
    WECHAT_RE = re.compile(
        r'^(\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2}:\d{2})\s+(\S+?)(?:\s*$|\n)',
        re.MULTILINE,
    )

    # WeChat Work bot message format
    WEWORK_RE = re.compile(
        r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+(\S+?)[：:]\s*(.+)',
        re.MULTILINE,
    )

    # Feishu exported chat format
    FEISHU_RE = re.compile(
        r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s+(\S+?)[：:]\s*(.+)',
        re.MULTILINE,
    )

    # Generic JSON chat export format
    # [{"sender":"张三","content":"...","time":"2024-01-15 14:30"}]

    @classmethod
    def detect_platform(cls, filepath: str) -> str:
        """Auto-detect chat log platform from file content."""
        try:
            content = Path(filepath).read_text(encoding="utf-8", errors="replace")
            if cls.WECHAT_RE.search(content):
                return "wechat"
            if cls.WEWORK_RE.search(content):
                return "wework"
            if cls.FEISHU_RE.search(content):
                return "feishu"
            try:
                data = json.loads(content)
                if isinstance(data, list) and "sender" in data[0]:
                    return "json"
            except (json.JSONDecodeError, IndexError):
                pass
        except Exception:
            pass
        return "unknown"

    @classmethod
    def parse(cls, filepath: str, platform: str = "") -> list[ChatMessage]:
        """Parse a chat log file into ChatMessage list."""
        platform = platform or cls.detect_platform(filepath)
        if platform == "wechat":
            return cls._parse_wechat(filepath)
        if platform == "wework" or platform == "wecom":
            return cls._parse_wework(filepath)
        if platform == "feishu":
            return cls._parse_feishu(filepath)
        if platform == "json":
            return cls._parse_json(filepath)
        return cls._parse_generic(filepath)

    @classmethod
    def _parse_wechat(cls, filepath: str) -> list[ChatMessage]:
        """Parse WeChat PC export format."""
        content = Path(filepath).read_text(encoding="utf-8", errors="replace")
        messages = []
        current_sender = ""
        current_time = ""
        current_text = []

        for line in content.split('\n'):
            m = cls.WECHAT_RE.match(line)
            if m:
                # Save previous message
                if current_sender and current_text:
                    messages.append(ChatMessage(
                        platform="wechat", sender=current_sender,
                        content='\n'.join(current_text).strip(),
                        timestamp=current_time,
                    ))
                current_time = m.group(1)
                current_sender = m.group(2).strip()
                # Content might be on same line or next line
                after_name = line[m.end():].strip()
                current_text = [after_name] if after_name else []
            else:
                current_text.append(line)

        # Last message
        if current_sender and current_text:
            messages.append(ChatMessage(
                platform="wechat", sender=current_sender,
                content='\n'.join(current_text).strip(),
                timestamp=current_time,
            ))

        return messages

    @classmethod
    def _parse_wework(cls, filepath: str) -> list[ChatMessage]:
        """Parse WeChat Work format."""
        content = Path(filepath).read_text(encoding="utf-8", errors="replace")
        messages = []
        for m in cls.WEWORK_RE.finditer(content):
            messages.append(ChatMessage(
                platform="wework", sender=m.group(2),
                content=m.group(3), timestamp=m.group(1),
            ))
        return messages

    @classmethod
    def _parse_feishu(cls, filepath: str) -> list[ChatMessage]:
        return cls._parse_wework(filepath)  # Same format

    @classmethod
    def _parse_json(cls, filepath: str) -> list[ChatMessage]:
        """Parse generic JSON format."""
        data = json.loads(Path(filepath).read_text(encoding="utf-8"))
        return [ChatMessage(
            platform=m.get("platform", "unknown"),
            sender=m.get("sender", m.get("from", "")),
            content=m.get("content", m.get("text", "")),
            timestamp=m.get("time", m.get("timestamp", "")),
            group_name=m.get("group", ""),
            message_type=m.get("type", "text"),
        ) for m in data]

    @classmethod
    def _parse_generic(cls, filepath: str) -> list[ChatMessage]:
        """Generic CSV: sender,content,time"""
        content = Path(filepath).read_text(encoding="utf-8", errors="replace")
        messages = []
        for line in content.split('\n')[1:]:  # Skip header
            parts = line.split(',', 2)
            if len(parts) >= 2:
                messages.append(ChatMessage(
                    platform="unknown", sender=parts[0].strip(),
                    content=parts[1].strip(),
                    timestamp=parts[2].strip() if len(parts) > 2 else "",
                ))
        return messages


# ═══ 2. Batch Profile Builder ═════════════════════════════════════

class BatchProfileBuilder:
    """Build user profiles from batch chat history.

    Extracts: expertise, interests, communication style, habits, relationships.
    """

    # Expertise indicators (Chinese)
    EXPERTISE_KEYWORDS = {
        "环评": ["环评", "EIA", "环境影响", "报告书"],
        "水处理": ["废水", "污水处理", "BOD", "COD", "膜处理"],
        "大气": ["废气", "脱硫", "脱硝", "PM2.5", "VOCs"],
        "噪声": ["噪声", "降噪", "隔音", "消声"],
        "编程": ["代码", "Python", "bug", "API", "数据库", "SQL"],
        "管理": ["项目", "进度", "审批", "验收", "预算"],
        "法规": ["标准", "GB", "HJ", "法规", "合规"],
    }

    STYLE_INDICATORS = {
        "formal": ["您好", "请", "谢谢", "抱歉", "麻烦"],
        "casual": ["哈哈", "嗯嗯", "好的呀", "ok", "👌"],
        "technical": ["参数", "计算", "公式", "模型", "系数"],
    }

    def __init__(self):
        self._profiles: dict[str, UserProfile] = {}

    def build_from_messages(self, messages: list[ChatMessage],
                            user_id: str = "") -> dict[str, UserProfile]:
        """Build profiles from a list of parsed messages.

        Returns {user_id: UserProfile} for all unique senders.
        """
        # Group by sender
        by_sender: dict[str, list[ChatMessage]] = defaultdict(list)
        for msg in messages:
            by_sender[msg.sender].append(msg)

        profiles = {}
        for sender, msgs in by_sender.items():
            profile = self._extract_profile(sender, msgs)
            profiles[sender] = profile

        self._profiles.update(profiles)
        return profiles

    def build_from_file(self, filepath: str,
                        platform: str = "") -> dict[str, UserProfile]:
        """Convenience: parse file → build profiles."""
        messages = ChatHistoryImporter.parse(filepath, platform)
        return self.build_from_messages(messages)

    def _extract_profile(self, user_id: str,
                         messages: list[ChatMessage]) -> UserProfile:
        """Extract a single user's profile from their messages."""
        all_text = ' '.join(m.content for m in messages)

        # Expertise
        expertise = []
        for domain, keywords in self.EXPERTISE_KEYWORDS.items():
            score = sum(all_text.count(k) for k in keywords)
            if score > 3:
                expertise.append(domain)

        # Interests (non-expertise frequent topics)
        word_counts = Counter()
        for msg in messages:
            for word in re.findall(r'[\u4e00-\u9fff]{2,4}', msg.content):
                word_counts[word] += 1
        interests = [w for w, c in word_counts.most_common(20)
                    if c > 5 and w not in ('可以', '这个', '那个', '我们', '他们')]

        # Communication style
        style_scores = {k: sum(all_text.count(w) for w in v)
                       for k, v in self.STYLE_INDICATORS.items()}
        style = max(style_scores, key=style_scores.get) if max(style_scores.values()) > 0 else "neutral"

        # Active hours
        hours = []
        for msg in messages:
            try:
                dt = datetime.strptime(msg.timestamp[:13], "%Y-%m-%d %H")
                hours.append(dt.hour)
            except (ValueError, IndexError):
                pass
        active_hours = [h for h, c in Counter(hours).most_common(5)]

        # Response pattern
        if messages:
            avg_len = sum(len(m.content) for m in messages) / len(messages)
            question_ratio = sum(1 for m in messages if '?' in m.content or '？' in m.content) / len(messages)
            pattern = "quick" if avg_len < 30 else "detailed" if avg_len > 100 else "balanced"
        else:
            avg_len = question_ratio = 0
            pattern = "unknown"

        # Relationships (who they talk to most)
        relationships = Counter(
            m.sender for m in messages if m.sender != user_id
        )

        # Common phrases
        phrases = [p for p, c in Counter(
            re.findall(r'[\u4e00-\u9fff]{3,6}', all_text)
        ).most_common(10) if c > 3]

        # Sentiment
        positive = sum(1 for m in messages if any(
            k in m.content for k in ('好', '棒', '厉害', '👍', '😊', '哈哈')))
        negative = sum(1 for m in messages if any(
            k in m.content for k in ('烦', '气死', '😡', '无语', '糟糕')))
        total = len(messages)
        sentiment = "positive" if positive > negative else "negative" if negative > positive else "neutral"

        return UserProfile(
            user_id=user_id, name=user_id,
            platform=messages[0].platform if messages else "",
            total_messages=len(messages),
            active_hours=active_hours,
            expertise=expertise,
            interests=interests[:10],
            communication_style=style,
            response_pattern=pattern,
            common_phrases=phrases[:5],
            relationships=dict(relationships.most_common(10)),
            sentiment=sentiment,
            question_ratio=round(question_ratio, 2),
            avg_message_length=round(avg_len, 1),
            last_updated=datetime.now().isoformat(),
        )

    def merge_profiles(self, user_id: str,
                       new_profile: UserProfile) -> UserProfile:
        """Merge a new profile with existing data."""
        existing = self._profiles.get(user_id)
        if not existing:
            self._profiles[user_id] = new_profile
            return new_profile

        # Merge expertise
        existing.expertise = list(set(existing.expertise + new_profile.expertise))
        # Merge interests
        existing.interests = list(set(existing.interests + new_profile.interests))
        # Update counts
        existing.total_messages += new_profile.total_messages
        existing.last_updated = datetime.now().isoformat()
        # Keep the most common style
        if new_profile.communication_style != "neutral":
            existing.communication_style = new_profile.communication_style

        self._profiles[user_id] = existing
        return existing

    def export_profiles(self, output_path: str = "",
                        format: str = "json") -> str:
        """Export all profiles to file."""
        out = Path(output_path or ".livingtree/user_profiles.json")
        data = {
            k: {
                "name": p.name, "platform": p.platform,
                "total_messages": p.total_messages,
                "expertise": p.expertise,
                "interests": p.interests,
                "communication_style": p.communication_style,
                "response_pattern": p.response_pattern,
                "sentiment": p.sentiment,
                "relationships": p.relationships,
                "last_updated": p.last_updated,
            }
            for k, p in self._profiles.items()
        }
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        return str(out)


# ═══ 3. Channel-to-UserModel Adapter ══════════════════════════════

class ChannelToUserAdapter:
    """Route live ChannelBridge messages → UserModel + PersonaMemory.

    Bridges the gap: ChannelBridge receives messages but doesn't feed them
    to the user profiling system.
    """

    @staticmethod
    async def on_message(platform: str, user_id: str, content: str,
                         group_id: str = "", metadata: dict = None) -> dict:
        """Process an incoming channel message for profile building.

        Called by ChannelBridge on every received message.
        """
        result = {"user_id": user_id, "platform": platform,
                  "actions": []}

        # 1. Feed to UserModel for real-time trait update
        try:
            from ..memory.user_model import get_user_model
            um = get_user_model()
            um.observe_message(content)
            result["actions"].append("user_model_updated")
        except Exception as e:
            logger.debug(f"UserModel feed: {e}")

        # 2. Feed to PersonaMemory for structured persona extraction
        try:
            from ..memory.persona_memory import get_persona_memory
            pm = get_persona_memory()
            pm.ingest(user_id, content, source=platform)
            result["actions"].append("persona_memory_updated")
        except Exception as e:
            logger.debug(f"PersonaMemory feed: {e}")

        # 3. Update ProgressiveTrust expertise tracking
        try:
            from ..capability.progressive_trust import get_progressive_trust
            pt = get_progressive_trust()
            # Detect domain from content
            domain = ChannelToUserAdapter._detect_domain(content)
            if domain:
                pt.record_interaction(user_id, domain, trusted=True)
                result["actions"].append(f"progressive_trust:{domain}")
        except Exception as e:
            logger.debug(f"ProgressiveTrust feed: {e}")

        # 4. Store raw message for later batch processing
        try:
            from ..treellm.living_store import get_living_store
            store = get_living_store()
            record = json.dumps({
                "platform": platform, "user_id": user_id,
                "content": content[:500], "group_id": group_id,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {},
            }, ensure_ascii=False)
            await store.write(
                f"/ram/chat_history/{platform}/{user_id}/{int(datetime.now().timestamp())}.json",
                record.encode(),
            )
            result["actions"].append("stored_to_vfs")
        except Exception:
            pass

        return result

    @staticmethod
    def _detect_domain(content: str) -> str:
        """Detect professional domain from message content."""
        domains = {
            "eia": ["环评", "EIA", "环境影响", "报告书"],
            "water": ["废水", "污水", "BOD", "COD", "水处理"],
            "air": ["废气", "大气", "PM2.5", "脱硫", "VOCs"],
            "noise": ["噪声", "降噪", "隔音"],
            "code": ["代码", "Python", "bug", "API", "SQL"],
            "management": ["项目", "审批", "验收", "进度"],
        }
        for domain, keywords in domains.items():
            if any(k in content for k in keywords):
                return domain
        return ""


# ═══ Singleton ════════════════════════════════════════════════════

_profile_builder: Optional[BatchProfileBuilder] = None


def get_profile_builder() -> BatchProfileBuilder:
    global _profile_builder
    if _profile_builder is None:
        _profile_builder = BatchProfileBuilder()
    return _profile_builder


__all__ = [
    "ChatMessage", "UserProfile",
    "ChatHistoryImporter", "BatchProfileBuilder",
    "ChannelToUserAdapter", "get_profile_builder",
]
