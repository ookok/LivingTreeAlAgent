"""Tiny Classifier — Built-in routing model for TreeLLM.

Pure Python. No sklearn, no numpy required (uses list-based math).
Learns from past routing successes to predict the best provider.

Features from user prompts:
- Length (short/medium/long)
- Keyword presence (analyze, code, report, search, etc.)
- Domain hints (eia, emergency, knowledge, training)
- Time of day (morning/afternoon/evening)
- Language (Chinese/English/mixed)

Weights updated via online logistic regression after each call.
Storage: ~20KB in memory, persists to JSON.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


class TinyClassifier:
    """Miniature logistic regression for LLM provider routing.

    Feature set: 30 binary features (keyword present) + 2 float features.
    Trained online — every success call updates weights directionally.
    """

    FEATURE_KEYWORDS = [
        "analyze", "分析", "code", "代码", "生成", "report", "报告",
        "search", "搜索", "knowledge", "知识", "train", "训练",
        "translate", "翻译", "summarize", "总结", "refactor", "重构",
        "fix", "修复", "debug", "emergency", "应急", "eia",
    ]

    def __init__(self):
        self._weights: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self._bias: dict[str, float] = defaultdict(float)
        self._count: int = 0

    def predict(self, prompt: str, candidates: list[str],
                stats: dict[str, Any]) -> str:
        if len(candidates) <= 1:
            return candidates[0] if candidates else ""

        features = self._extract_features(prompt)
        scores = {}

        for provider in candidates:
            w = self._weights.get(provider, {})
            score = self._bias.get(provider, 0.0)
            for fname, fval in features.items():
                score += w.get(fname, 0.0) * fval

            s = stats.get(provider)
            if s and hasattr(s, 'success_rate'):
                score += s.success_rate * 0.5
            if s and hasattr(s, 'avg_latency_ms') and s.avg_latency_ms > 0:
                score -= math.log(max(s.avg_latency_ms, 1)) * 0.1

            scores[provider] = score

        if not scores:
            return candidates[0] if candidates else ""

        best = max(scores, key=scores.get)
        if scores[best] < -2.0 and self._count < 50:
            return candidates[0]

        return best

    def learn(self, prompt: str, chosen: str, success: bool) -> None:
        self._count += 1
        features = self._extract_features(prompt)
        lr = 0.1 / max(1.0, math.sqrt(self._count / 10))
        direction = 1.0 if success else -0.5

        w = self._weights[chosen]
        for fname, fval in features.items():
            w[fname] = w.get(fname, 0.0) + lr * direction * fval

        self._bias[chosen] = self._bias.get(chosen, 0.0) + lr * direction * 0.1

        if self._count % 100 == 0:
            self._save()

    def reset(self) -> None:
        self._weights.clear()
        self._bias.clear()
        self._count = 0

    def _extract_features(self, prompt: str) -> dict[str, float]:
        p = prompt.lower()
        features = {}

        length = len(prompt)
        if length < 50:
            features["len_short"] = 1.0
        elif length < 300:
            features["len_medium"] = 1.0
        else:
            features["len_long"] = 1.0

        for kw in self.FEATURE_KEYWORDS:
            if kw.lower() in p:
                features[f"kw_{kw}"] = 1.0

        chinese_chars = sum(1 for c in prompt if '\u4e00' <= c <= '\u9fff')
        if chinese_chars > len(prompt) * 0.3:
            features["lang_zh"] = 1.0
        elif chinese_chars > 0:
            features["lang_mixed"] = 1.0
        else:
            features["lang_en"] = 1.0

        import datetime
        hour = datetime.datetime.now().hour
        if hour < 8:
            features["time_night"] = 1.0
        elif hour < 12:
            features["time_morning"] = 1.0
        elif hour < 18:
            features["time_afternoon"] = 1.0
        else:
            features["time_evening"] = 1.0

        if "?" in prompt or "？" in prompt:
            features["is_question"] = 1.0

        return features

    def _save(self) -> None:
        try:
            path = Path(".livingtree") / "classifier_weights.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            import json
            data = {
                "count": self._count,
                "bias": dict(self._bias),
                "weights": {k: dict(v) for k, v in self._weights.items()},
            }
            path.write_text(json.dumps(data, ensure_ascii=False))
        except Exception:
            pass

    def load(self, path: str = "") -> None:
        p = Path(path or ".livingtree/classifier_weights.json")
        if not p.exists():
            return
        try:
            import json
            data = json.loads(p.read_text(encoding="utf-8"))
            self._count = data.get("count", 0)
            self._bias = defaultdict(float, data.get("bias", {}))
            self._weights = defaultdict(dict)
            for k, v in data.get("weights", {}).items():
                self._weights[k] = defaultdict(float, v)
        except Exception:
            pass
