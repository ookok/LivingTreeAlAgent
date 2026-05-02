"""
LivingTree 统一意图与语义分析中心
=================================

意图解析 + 分类器 + 多模态感知 + 多轮跟踪 + 语义相似度

Full migration from legacy memory/intent_classifier.py +
memory/hybrid_intent_classifier.py patterns.
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


class IntentType(Enum):
    CHAT = "chat"
    WRITING = "writing"
    CODE = "code"
    SEARCH = "search"
    ANALYSIS = "analysis"
    AUTOMATION = "automation"
    COMMAND = "command"
    FILE_OP = "file_operation"
    UNKNOWN = "unknown"


class SentimentLabel(Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    URGENT = "urgent"
    FRUSTRATED = "frustrated"


class LanguageHint(Enum):
    ZH = "zh"
    EN = "en"
    MIXED = "mixed"


@dataclass
class ParsedIntent:
    type: IntentType = IntentType.UNKNOWN
    raw_text: str = ""
    entities: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    complexity: float = 0.0
    priority: int = 1
    confidence: float = 0.0
    sentiment: str = "neutral"
    sentiment_score: float = 0.0
    language: str = "zh"
    requires_tools: bool = False
    projected_tokens: int = 500
    sub_intents: List["ParsedIntent"] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


_INTENT_PATTERNS: Dict[str, List[re.Pattern]] = {
    "writing": [
        re.compile(r"(写|撰写|编写|生成|起草|创作)(一|这篇|一个)"),
        re.compile(r"(报告|文章|文档|论文|摘要|方案|计划|总结)"),
        re.compile(r"(帮我|给我|为我)\s*(写|生成|编写)"),
    ],
    "code": [
        re.compile(r"(代码|编程|程序|脚本|bug|修复|编译|git|commit|pull|push)"),
        re.compile(r"(实现|开发|调试|重构)\s*(这个|该|一个)"),
        re.compile(r"(def|class|import|function)\s"),
    ],
    "search": [
        re.compile(r"(搜索|查找|搜一下|帮我搜|查一下)"),
        re.compile(r"(有什么|有哪些|什么是|怎么|如何)"),
        re.compile(r"(最新的|最近的|现在|当下)"),
    ],
    "analysis": [
        re.compile(r"(分析|解析|评估|审核|审计|检查|对比|比较)"),
        re.compile(r"(为什么|原因|怎么回事|该怎么办)"),
        re.compile(r"(风险|问题|影响|效果)"),
    ],
    "automation": [
        re.compile(r"(自动|批量|定时|定期|监控|巡检)"),
        re.compile(r"(每天|每小时|定时|周期)"),
        re.compile(r"(监控|监听|检测|扫描)"),
    ],
    "file_op": [
        re.compile(r"(打开|读取|修改|删除|复制|移动|重命名)\s*(文件)"),
        re.compile(r"(\.py|\.js|\.ts|\.json|\.yaml|\.md)"),
    ],
    "command": [
        re.compile(r"^(运行|执行|启动|停止|重启)\s"),
        re.compile(r"^(pip|npm|yarn|docker|kubectl)\s"),
    ],
}

_ENTITY_PATTERNS: Dict[str, re.Pattern] = {
    "file_path": re.compile(r"([\w./\\\-]+\.(py|js|ts|json|yaml|yml|md|txt|csv|xml|html|css))"),
    "url": re.compile(r"https?://[\w./\-?=&%#]+"),
    "email": re.compile(r"[\w.\-]+@[\w.\-]+\.\w+"),
    "version": re.compile(r"\d+\.\d+\.\d+"),
    "date": re.compile(r"\d{4}[-/]\d{2}[-/]\d{2}"),
    "number": re.compile(r"\b\d+\b"),
    "package": re.compile(r"(pip|npm|yarn|docker|kubectl|git)\s+\w+"),
}

_COMPLEXITY_KEYWORDS: Dict[str, float] = {
    "复杂": 0.3, "大型": 0.3, "全面": 0.2, "深度": 0.3,
    "简单": -0.2, "快速": -0.1, "简要": -0.2, "一句话": -0.3,
    "多种": 0.2, "多个": 0.15, "同时": 0.1, "所有": 0.15,
    "架构": 0.25, "重构": 0.3, "设计": 0.2, "系统": 0.15,
}

_SENTIMENT_WORDS: Dict[str, Tuple[float, SentimentLabel]] = {
    # Positive
    "谢谢": (0.8, SentimentLabel.POSITIVE), "很好": (0.7, SentimentLabel.POSITIVE),
    "非常好": (0.9, SentimentLabel.POSITIVE), "good": (0.6, SentimentLabel.POSITIVE),
    "great": (0.8, SentimentLabel.POSITIVE), "完美": (0.9, SentimentLabel.POSITIVE),
    # Negative
    "错误": (-0.6, SentimentLabel.NEGATIVE), "问题": (-0.4, SentimentLabel.NEGATIVE),
    "不行": (-0.7, SentimentLabel.NEGATIVE), "无法": (-0.5, SentimentLabel.NEGATIVE),
    "失败": (-0.8, SentimentLabel.NEGATIVE), "bug": (-0.5, SentimentLabel.NEGATIVE),
    "error": (-0.6, SentimentLabel.NEGATIVE),
    # Urgency
    "急": (0.0, SentimentLabel.URGENT), "紧急": (0.0, SentimentLabel.URGENT),
    "马上": (0.0, SentimentLabel.URGENT), "立即": (0.0, SentimentLabel.URGENT),
    "赶紧": (0.0, SentimentLabel.URGENT), "urgent": (0.0, SentimentLabel.URGENT),
    "asap": (0.0, SentimentLabel.URGENT),
    # Frustrated
    "还是不行": (-0.7, SentimentLabel.FRUSTRATED), "又错了": (-0.8, SentimentLabel.FRUSTRATED),
    "怎么又": (-0.6, SentimentLabel.FRUSTRATED), "第几次了": (-0.7, SentimentLabel.FRUSTRATED),
}


class IntentParser:
    """意图解析器 — 基于正则规则 + 统计特征."""

    def __init__(self):
        self._intent_history: List[ParsedIntent] = []

    def parse(self, text: str) -> ParsedIntent:
        if not text or not text.strip():
            return ParsedIntent(type=IntentType.CHAT, raw_text=text,
                                confidence=1.0)

        text_lower = text.lower()
        scores: Dict[IntentType, float] = {}
        all_keywords: List[str] = []

        for intent_name, patterns in _INTENT_PATTERNS.items():
            score = 0.0
            for pattern in patterns:
                matches = pattern.findall(text_lower)
                if matches:
                    score += len(matches) * 0.25
                    flat = self._flatten_matches(matches)
                    all_keywords.extend(flat)
            if score > 0:
                scores[IntentType(intent_name)] = score

        if scores:
            best_type = max(scores, key=scores.get)
            confidence = min(1.0, scores[best_type])
        else:
            best_type = IntentType.CHAT
            confidence = 0.5

        entities = self._extract_entities(text)
        keywords = list(dict.fromkeys(all_keywords[:8]))

        complexity = self._compute_complexity(text, text_lower)
        sentiment, sentiment_score = self._analyze_sentiment(text_lower)
        language = self._detect_language(text)

        projects_tokens = self._estimate_tokens(text, best_type, complexity)

        intent = ParsedIntent(
            type=best_type, raw_text=text,
            entities=entities[:10], keywords=keywords,
            complexity=min(1.0, complexity),
            priority=int(complexity * 5) + 1,
            confidence=min(1.0, confidence),
            sentiment=sentiment.value, sentiment_score=sentiment_score,
            language=language.value,
            requires_tools=best_type in (
                IntentType.CODE, IntentType.SEARCH,
                IntentType.AUTOMATION, IntentType.FILE_OP,
            ),
            projected_tokens=projects_tokens,
            metadata={
                "scores": {k.value: v for k, v in scores.items()},
                "entity_types": self._entity_types(entities),
            },
        )

        self._intent_history.append(intent)
        if len(self._intent_history) > 50:
            self._intent_history = self._intent_history[-50:]

        return intent

    def parse_batch(self, texts: List[str]) -> List[ParsedIntent]:
        return [self.parse(t) for t in texts]

    def _extract_entities(self, text: str) -> List[str]:
        entities: List[str] = []
        for entity_type, pattern in _ENTITY_PATTERNS.items():
            for match in pattern.finditer(text):
                entities.append(match.group(0))

        words = [w for w in text.split() if len(w) >= 2
                 and not w.startswith(("http", "www"))]
        words = [w.strip(",.;:!?，。；：！？\"\"''（）()[]【】") for w in words]

        seen = set()
        unique = []
        for e in entities + words:
            if e not in seen and len(e) >= 2:
                seen.add(e)
                unique.append(e)
        return unique[:15]

    def _entity_types(self, entities: List[str]) -> Dict[str, int]:
        counts: Dict[str, int] = Counter()
        for e in entities:
            for ename, pattern in _ENTITY_PATTERNS.items():
                if pattern.search(e):
                    counts[ename] += 1
                    break
        return dict(counts)

    def _compute_complexity(self, text: str, text_lower: str) -> float:
        base = max(0.1, len(text) / 200.0 + len(text.split()) / 50.0)
        base = min(0.8, base)

        for kw, boost in _COMPLEXITY_KEYWORDS.items():
            if kw.lower() in text_lower:
                base += boost

        question_marks = text.count("?") + text.count("？")
        base += question_marks * 0.05
        sentences = max(1, len(re.split(r"[.。!！?？\n]", text)))
        if sentences > 5:
            base += 0.1

        return max(0.05, min(1.0, base))

    def _analyze_sentiment(self, text_lower: str) -> Tuple[SentimentLabel, float]:
        score = 0.0
        label_counts: Dict[SentimentLabel, int] = Counter()

        for word, (val, label) in _SENTIMENT_WORDS.items():
            if word.lower() in text_lower:
                score += val
                label_counts[label] += 1

        if not label_counts:
            return SentimentLabel.NEUTRAL, 0.0

        dominant = max(label_counts, key=label_counts.get)
        normalized = max(-1.0, min(1.0, score / max(1, sum(label_counts.values()))))
        return dominant, normalized

    def _detect_language(self, text: str) -> LanguageHint:
        chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
        english = len(re.findall(r"[a-zA-Z]+", text))

        total = chinese + english
        if total == 0:
            return LanguageHint.ZH

        if chinese > 0 and english > chinese * 0.1:
            return LanguageHint.MIXED
        if english > chinese * 2:
            return LanguageHint.EN
        return LanguageHint.ZH

    def _estimate_tokens(self, text: str, intent_type: IntentType,
                         complexity: float) -> int:
        base_tokens = {
            IntentType.CHAT: 600, IntentType.WRITING: 2000,
            IntentType.CODE: 3000, IntentType.SEARCH: 800,
            IntentType.ANALYSIS: 2500, IntentType.AUTOMATION: 1500,
            IntentType.COMMAND: 300, IntentType.FILE_OP: 400,
        }
        base = base_tokens.get(intent_type, 800)
        return int(base * (1.0 + complexity))

    @staticmethod
    def _flatten_matches(matches) -> List[str]:
        result = []
        for m in matches:
            if isinstance(m, str):
                result.append(m)
            elif isinstance(m, tuple):
                result.extend(s for s in m if isinstance(s, str))
        return result


class IntentSimilarity:
    """意图相似度 — 用于意图变化检测."""

    @staticmethod
    def jaccard(a: ParsedIntent, b: ParsedIntent) -> float:
        a_set = set(a.keywords + a.entities)
        b_set = set(b.keywords + b.entities)
        if not a_set and not b_set:
            return 0.0
        if not a_set or not b_set:
            return 0.0
        return len(a_set & b_set) / len(a_set | b_set)

    @staticmethod
    def complexity_shift(a: ParsedIntent, b: ParsedIntent) -> float:
        return b.complexity - a.complexity

    @staticmethod
    def is_topic_switch(current: List[ParsedIntent],
                        new_intent: ParsedIntent,
                        threshold: float = 0.3) -> bool:
        if not current:
            return True
        last = current[-1]
        sim = IntentSimilarity.jaccard(last, new_intent)
        return sim < threshold


@dataclass
class DialogTurn:
    turn_id: int
    intent: ParsedIntent
    timestamp: float = 0.0
    user_input: str = ""


class IntentTracker:
    """多轮对话意图跟踪器 — 检测意图漂移、升级、切换."""

    def __init__(self, max_history: int = 20):
        self._history: List[DialogTurn] = []
        self._max_history = max_history
        self._turn_id = 0
        self._topic_segments: List[Tuple[int, IntentType]] = []

    def track(self, intent: ParsedIntent, user_input: str):
        import time
        self._turn_id += 1
        turn = DialogTurn(
            turn_id=self._turn_id,
            intent=intent,
            timestamp=time.time(),
            user_input=user_input,
        )
        self._history.append(turn)

        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        if (self._turn_id > 1
                and IntentSimilarity.is_topic_switch(
                    [t.intent for t in self._history[-3:-1]
                     if t.turn_id < self._turn_id],
                    intent)):
            self._topic_segments.append((self._turn_id, intent.type))

    def get_current_context(self) -> Dict[str, Any]:
        if not self._history:
            return {"active": False, "current_intent": None}

        latest = self._history[-1]
        recent = self._history[-3:]

        same_type = all(t.intent.type == latest.intent.type for t in recent)
        escalation = (
            sum(t.intent.complexity for t in recent) / max(len(recent), 1)
            > latest.intent.complexity * 1.2
        )

        topic_changes = len(self._topic_segments)
        sentiment_trend = self._sentiment_trend()

        return {
            "active": True,
            "current_intent": latest.intent.type.value,
            "turn_count": len(self._history),
            "is_deepening": same_type,
            "is_escalating": escalation,
            "topic_changes": topic_changes,
            "sentiment_trend": sentiment_trend,
            "suggested_approach": (
                "deep_analysis" if escalation else
                "continue_conversation" if same_type else
                "new_context"
            ),
            "last_entities": latest.intent.entities[:5],
        }

    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        return [
            {"turn": t.turn_id, "intent": t.intent.type.value,
             "complexity": t.intent.complexity, "sentiment": t.intent.sentiment}
            for t in self._history[-limit:]
        ]

    def _sentiment_trend(self) -> str:
        if len(self._history) < 3:
            return "stable"
        recent = self._history[-5:]
        scores = [t.intent.sentiment_score for t in recent]
        if len(scores) < 3:
            return "stable"
        first_half = sum(scores[:len(scores)//2]) / max(1, len(scores)//2)
        second_half = sum(scores[len(scores)//2:]) / max(1, len(scores) - len(scores)//2)
        if second_half > first_half + 0.2:
            return "improving"
        if second_half < first_half - 0.2:
            return "declining"
        return "stable"


__all__ = [
    "IntentParser",
    "IntentType",
    "ParsedIntent",
    "IntentTracker",
    "IntentSimilarity",
    "DialogTurn",
    "SentimentLabel",
    "LanguageHint",
]
