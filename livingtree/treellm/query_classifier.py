"""QueryClassifier — Zero-cost local task type classification.

Classifies user queries into task types (chat/code/reasoning/search/long_context)
using pure keyword + heuristic matching. ~5ms latency, no LLM call needed.

Only falls back to recognize_intent() (L1 LLM call) when confidence is low (<0.6).

Integration:
    qc = get_query_classifier()
    task_type, confidence = qc.classify(query)
    if confidence < 0.6:
        task_type = await consciousness.recognize_intent(query)  # LLM fallback
"""

from __future__ import annotations

import threading
from typing import Optional


class QueryClassifier:
    """Fast local task type classification using keyword + pattern heuristics."""

    _instance: Optional["QueryClassifier"] = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls) -> "QueryClassifier":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = QueryClassifier()
        return cls._instance

    def __init__(self):
        self._classifications = 0

    def classify(self, query: str) -> tuple[str, float]:
        """Classify query into (task_type, confidence)."""
        self._classifications += 1
        q = query.lower().strip()
        qlen = len(q)

        # Very short → chat
        if qlen < 8:
            return "chat", 0.9

        # Chinese greeting patterns
        if q in ("你好", "嗨", "hello", "hi", "在吗", "在不在"):
            return "chat", 0.95

        # Code indicators
        code_kw = ["写", "实现", "代码", "函数", "bug", "修复", "错误", "报错",
                   "import", "def ", "class ", "print(", "npm ", "pip ",
                   "python", "javascript", "java", "rust", "go "]
        if any(k in q for k in code_kw):
            return "code", 0.8

        # Reasoning indicators (question words + analysis)
        reason_kw = ["为什么", "原因", "原理", "如何工作", "怎么回事",
                     "分析", "比较", "区别", "优缺点", "影响",
                     "explain", "analyze", "compare", "why"]
        if any(k in q for k in reason_kw) and qlen > 20:
            return "reasoning", 0.7

        # Search indicators
        search_kw = ["搜索", "查找", "找一下", "有没有", "在哪", "怎么查",
                     "search", "find", "lookup", "where is"]
        if any(k in q for k in search_kw):
            return "search", 0.75

        # Long context indicators
        if qlen > 500:
            return "long_context", 0.65

        # Question marks → chat/reasoning
        if "?" in q or "？" in q:
            if qlen > 50:
                return "reasoning", 0.55
            return "chat", 0.6

        # Translation
        if any(k in q for k in ["翻译", "translate", "英文", "中文"]):
            return "chat", 0.8

        # Default
        if qlen < 30:
            return "chat", 0.5
        return "general", 0.45

    def needs_llm_classification(self, confidence: float) -> bool:
        """Return True if LLM-based classification should be used."""
        return confidence < 0.6

    def stats(self) -> dict:
        return {"classifications": self._classifications}


_classifier: Optional[QueryClassifier] = None
_classifier_lock = threading.Lock()


def get_query_classifier() -> QueryClassifier:
    global _classifier
    if _classifier is None:
        with _classifier_lock:
            if _classifier is None:
                _classifier = QueryClassifier()
    return _classifier


__all__ = ["QueryClassifier", "get_query_classifier"]
