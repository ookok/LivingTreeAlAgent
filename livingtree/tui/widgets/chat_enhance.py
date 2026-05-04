"""Chat Enhancements — Emotion mirror, auto-sectioning, knowledge cards, ghost suggestions.

1. Emotion Mirror: detects conversation mood, shows indicator, adapts response style.
2. Auto-sectioning: detects topic transitions, inserts section headers.
3. Knowledge Cards: shows inline source citations when KB facts are referenced.
4. Ghost Suggestions: shows dim completion hints while user types.
"""

from collections import defaultdict
from loguru import logger


class EmotionMirror:
    """Detects conversation mood and returns style adaptation."""

    MOOD_INDICATORS = {
        "casual": ("💬", "relaxed"),
        "technical": ("⚙", "precise"),
        "creative": ("🎨", "expressive"),
        "urgent": ("⚡", "concise"),
        "analytical": ("🔍", "thorough"),
        "learning": ("📚", "educational"),
    }

    def __init__(self):
        self._moods = []

    def detect(self, text: str) -> str:
        low = text.lower()
        scores = defaultdict(float)

        if any(kw in low for kw in ["urgent", "asap", "紧急", "马上", "立刻"]):
            scores["urgent"] += 1.0
        if any(kw in low for kw in ["code", "function", "class", "api", "bug", "error", "代码", "函数"]):
            scores["technical"] += 1.0
        if any(kw in low for kw in ["design", "create", "imagine", "创意", "设计", "画"]):
            scores["creative"] += 0.8
        if any(kw in low for kw in ["analyze", "分析", "why", "为什么", "原因", "推理"]):
            scores["analytical"] += 0.8
        if any(kw in low for kw in ["teach", "learn", "explain", "教", "学", "解释", "how"]):
            scores["learning"] += 0.7

        if not scores:
            scores["casual"] = 0.5

        mood = max(scores, key=scores.get)
        self._moods.append(mood)
        return mood

    def get_indicator(self) -> str:
        mood = self._moods[-1] if self._moods else "casual"
        icon, style = self.MOOD_INDICATORS.get(mood, ("💬", "relaxed"))
        return f"[dim]{icon} {style}[/dim]"

    def get_current_mood(self) -> str:
        return self._moods[-1] if self._moods else "casual"


class AutoSectioner:
    """Detects topic transitions and inserts section headers."""

    def __init__(self):
        self._topics = []
        self._last_topic = ""

    def detect_transition(self, text: str, previous_text: str = "") -> str | None:
        if not previous_text:
            self._last_topic = self._extract_topic(text)
            return None

        new_topic = self._extract_topic(text)
        if new_topic and new_topic != self._last_topic and len(new_topic) > 5:
            self._last_topic = new_topic
            return f"[bold #58a6ff]## {new_topic}[/bold #58a6ff]"
        return None

    def _extract_topic(self, text: str) -> str:
        low = text.lower()
        topic_map = {
            "auth": "Authentication & Security",
            "login": "Authentication & Security",
            "database": "Database & Storage",
            "db": "Database & Storage",
            "sql": "Database & Storage",
            "api": "API & Integration",
            "endpoint": "API & Integration",
            "ui": "User Interface",
            "frontend": "User Interface",
            "design": "User Interface",
            "test": "Testing & Quality",
            "testing": "Testing & Quality",
            "deploy": "Deployment & DevOps",
            "docker": "Deployment & DevOps",
            "performance": "Performance Optimization",
            "optimize": "Performance Optimization",
        }
        for keyword, topic in topic_map.items():
            if keyword in low:
                return topic
        return ""


class KnowledgeCards:
    """Shows inline source cards when KB facts are referenced."""

    def __init__(self, knowledge_base=None):
        self._kb = knowledge_base

    def detect_references(self, text: str) -> list[dict]:
        if not self._kb:
            return []
        cards = []
        try:
            results = self._kb.search(text, top_k=3)
            for doc in results[:2]:
                cards.append({
                    "title": getattr(doc, 'title', ''),
                    "source": getattr(doc, 'source', 'kb'),
                    "snippet": (getattr(doc, 'content', '') or '')[:80],
                })
        except Exception:
            pass
        return cards

    def format_card(self, card: dict) -> str:
        return f"\n[#58a6ff]📚 Source:[/#58a6ff] {card['title'][:50]} [dim]({card['source']})[/dim]\n"


class GhostSuggestions:
    """Shows dim completion hints while user types."""

    def __init__(self, anticipatory=None):
        self._anti = anticipatory

    def suggest(self, partial: str) -> str:
        if len(partial) < 5:
            return ""
        if self._anti:
            result = self._anti.suggest_action(partial)
            suggestions = result.get("suggestions", [])
            if suggestions:
                return f"[dim]Try: {' | '.join(suggestions[:3])}[/dim]"
        return ""
