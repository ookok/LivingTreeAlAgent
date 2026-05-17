"""UserMemory — auto-learn user preferences and inject into prompts.

Tracks: tone, terminology, preferred formats, common data structures.
Every interaction refines the profile. Auto-injected into Identity prompt.
"""

from __future__ import annotations

import re
import time
from collections import Counter
from pathlib import Path

from loguru import logger

MEMORY_PATH = Path(".livingtree/user_memory.json")


class UserMemory:
    """Learns user preferences from interactions. Zero-config — auto-detects."""

    def __init__(self):
        self.tone: str = ""              # "严谨学术" / "活泼营销" / "技术文档"
        self.terms: Counter = Counter()   # domain-specific terminology
        self.formats: Counter = Counter() # preferred output formats
        self.roles: Counter = Counter()   # frequent role templates used
        self.preferred_language: str = "" # "zh" / "en" / "zh+en"
        self._interaction_count: int = 0
        self._last_save: float = 0
        self._load()

    def learn_from_query(self, query: str) -> None:
        """Extract signals from user query."""
        self._interaction_count += 1

        # Detect tone from query style
        if any(kw in query for kw in ["正式", "报告", "评估", "分析报告", "学术"]):
            self.tone = self._merge_tone(self.tone, "严谨学术")
        elif any(kw in query for kw in ["宣传", "营销", "广告", "推广", "文案"]):
            self.tone = self._merge_tone(self.tone, "活泼营销")
        elif any(kw in query for kw in ["代码", "API", "文档", "技术", "接口"]):
            self.tone = self._merge_tone(self.tone, "技术文档")

        # Extract domain terms (Chinese 2-4 char words, English capitalized words)
        zh_terms = re.findall(r'[\u4e00-\u9fff]{2,4}', query)
        for t in zh_terms:
            if t not in ("一个", "这个", "那个", "可以", "需要", "什么", "怎么", "为什么"):
                self.terms[t] += 1

        # Detect language
        if re.search(r'[\u4e00-\u9fff]', query):
            if not self.preferred_language:
                self.preferred_language = "zh"

        self._maybe_save()

    def learn_from_response(self, response: str) -> None:
        """Extract signals from system response (format, style)."""
        if "```python" in response:
            self.formats["code_blocks"] += 1
        if "|" in response and "---" in response:
            self.formats["tables"] += 1
        if "```mermaid" in response:
            self.formats["diagrams"] += 1

    def learn_role(self, role_name: str) -> None:
        """Track which role templates are used."""
        self.roles[role_name] += 1

    def build_context(self) -> str:
        """Build context injection for system prompt."""
        parts = []
        if self.tone:
            parts.append(f"用户偏好风格: {self.tone}")
        top_terms = [t for t, _ in self.terms.most_common(5) if self.terms[t] >= 3]
        if top_terms:
            parts.append(f"用户常用术语: {', '.join(top_terms)}")
        top_formats = [f for f, _ in self.formats.most_common(3)]
        if top_formats:
            parts.append(f"用户偏好输出: {', '.join(top_formats)}")
        top_roles = [r for r, _ in self.roles.most_common(3)]
        if top_roles:
            parts.append(f"常用角色: {', '.join(top_roles)}")
        if self.preferred_language:
            parts.append(f"语言偏好: {self.preferred_language}")
        return "\n".join(f"[UserContext] {p}" for p in parts) if parts else ""

    @staticmethod
    def _merge_tone(old: str, new: str) -> str:
        if not old:
            return new
        if old == new:
            return old
        return f"{old}/{new}"

    def _maybe_save(self):
        if self._interaction_count % 10 == 0 or (time.time() - self._last_save) > 300:
            self._save()

    def _save(self):
        import json
        data = {
            "tone": self.tone,
            "terms": dict(self.terms.most_common(20)),
            "formats": dict(self.formats.most_common(10)),
            "roles": dict(self.roles.most_common(10)),
            "preferred_language": self.preferred_language,
            "interactions": self._interaction_count,
        }
        MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        MEMORY_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        self._last_save = time.time()

    def _load(self):
        if not MEMORY_PATH.exists():
            return
        try:
            import json
            data = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
            self.tone = data.get("tone", "")
            self.terms = Counter(data.get("terms", {}))
            self.formats = Counter(data.get("formats", {}))
            self.roles = Counter(data.get("roles", {}))
            self.preferred_language = data.get("preferred_language", "")
            self._interaction_count = data.get("interactions", 0)
        except Exception:
            pass


# Singleton
_memory: UserMemory | None = None


def get_user_memory() -> UserMemory:
    global _memory
    if _memory is None:
        _memory = UserMemory()
    return _memory
