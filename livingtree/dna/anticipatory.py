"""Anticipatory Intelligence — Predicts user intent before typing completes.

Uses pattern matching + lightweight prediction to:
- Pre-load context for likely next actions
- Suggest shortcuts based on history
- Detect emotional state from typing patterns
"""

from __future__ import annotations
from collections import defaultdict
from loguru import logger

class Anticipatory:
    """Predictive intelligence — anticipates user needs."""
    
    def __init__(self):
        self._patterns = defaultdict(lambda: defaultdict(int))  # prefix → next_word → count
        self._sessions = []  # recent session types
        self._mood_history = []
        
    def learn(self, query: str, action_taken: str, success: bool = True):
        words = query.lower().split()
        for i in range(len(words) - 1):
            prefix = " ".join(words[max(0,i-2):i+1])
            next_w = words[i+1] if i+1 < len(words) else ""
            self._patterns[prefix][next_w] += 1
        self._sessions.append({"query": query[:100], "action": action_taken, "success": success})
    
    def predict(self, partial: str) -> list[str]:
        words = partial.lower().split()
        if not words: return []
        prefix = " ".join(words[-2:])
        probs = self._patterns.get(prefix, {})
        if probs:
            total = sum(probs.values())
            return sorted(probs, key=probs.get, reverse=True)[:3]
        return []
    
    def suggest_action(self, query: str) -> dict:
        q = query.lower()
        suggestions = []
        confidence = 0.0
        
        if any(kw in q for kw in ["extract","提取","pipeline","管道"]):
            suggestions.append("/pipeline")
            confidence = 0.8
        elif any(kw in q for kw in ["search","搜索","find","查找"]):
            suggestions.append("/search")
            confidence = 0.7
        elif any(kw in q for kw in ["code","代码","generate","生成","write","写"]):
            suggestions.append("/code")
            confidence = 0.6
        elif any(kw in q for kw in ["file","文件","preview","预览"]):
            suggestions.append("/file")
            confidence = 0.5
        elif any(kw in q for kw in ["report","报告"]):
            suggestions.append("/report")
            confidence = 0.7
        elif any(kw in q for kw in ["help","帮助","?"]):
            suggestions.append("/help")
            confidence = 0.9
        
        for s in self._sessions[-5:]:
            if s["success"] and s["action"] not in suggestions:
                suggestions.append(s["action"])
        
        return {"suggestions": suggestions[:3], "confidence": confidence}
    
    def detect_mood(self, text: str) -> float:
        low = text.lower()
        urgency = sum(1 for c in text if c in "!！?？") / max(len(text), 1)
        gratitude = 0.5 if any(w in low for w in ["thanks","谢谢","good","好","great","excellent","优秀"]) else 0
        frustration = 0.5 if any(w in low for w in ["wrong","错","no","不","error","fail","失败","bug","broken"]) else 0
        return min(1.0, max(0.0, 0.5 + gratitude * 0.3 - frustration * 0.3 + urgency * 0.1))
    
    def get_top_patterns(self, n=5) -> list[dict]:
        result = []
        for prefix, nexts in sorted(self._patterns.items(), key=lambda x: sum(x[1].values()), reverse=True)[:n]:
            top = sorted(nexts, key=nexts.get, reverse=True)[:2]
            result.append({"prefix": prefix[:40], "next": top})
        return result
