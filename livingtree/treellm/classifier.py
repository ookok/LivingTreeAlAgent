"""SkillRouter / TinyClassifier — TF-IDF + self-learning provider classifier.

Routes user queries to best LLM provider, best system tools, and best expert role.
Uses full-text TF-IDF retrieval with self-learning from success/failure feedback.
Replaces the old binary-feature TinyClassifier with semantic TF-IDF routing.
"""
from __future__ import annotations

import json
import math
import re
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

# Lazy import to avoid circular dependency with capability/
SYSTEM_TOOLS = {}
EXPERT_ROLES = {}
try:
    from ..capability.tool_registry import SYSTEM_TOOLS as _st, EXPERT_ROLES as _er
    SYSTEM_TOOLS = _st
    EXPERT_ROLES = _er
except ImportError:
    pass

try:
    import numpy as np
except ImportError:
    np = None

WEIGHTS_FILE = Path(".livingtree/skill_router_weights.json")
HISTORY_FILE = Path(".livingtree/skill_router_history.jsonl")


# ═══ Pure Python TF-IDF (no numpy/sklearn needed) ═══

class PureTfidf:
    """Minimal TF-IDF implementation in pure Python."""

    def __init__(self, ngram_range=(1, 3), max_features=2000):
        self.ngram_range = ngram_range
        self.max_features = max_features
        self.vocabulary: dict[str, int] = {}
        self.idf: dict[str, float] = {}

    def _char_ngrams(self, text: str) -> list[str]:
        text = text.lower().strip()
        ngrams = []
        for n in range(self.ngram_range[0], self.ngram_range[1] + 1):
            for word in text.split():
                for i in range(len(word) - n + 1):
                    ngrams.append(word[i:i + n])
        return ngrams

    def fit(self, documents: list[str]):
        df = defaultdict(int)
        N = len(documents)
        for doc in documents:
            seen = set()
            for ng in self._char_ngrams(doc):
                if ng not in seen:
                    df[ng] += 1
                    seen.add(ng)

        sorted_terms = sorted(df.items(), key=lambda x: -x[1])[:self.max_features]
        self.vocabulary = {term: i for i, (term, _) in enumerate(sorted_terms)}
        self.idf = {term: math.log((N + 1) / (count + 1)) + 1 for term, count in sorted_terms}

    def transform(self, documents: list[str]) -> list[list[float]]:
        rows = []
        for doc in documents:
            vec = [0.0] * len(self.vocabulary)
            tf = defaultdict(int)
            for ng in self._char_ngrams(doc):
                if ng in self.vocabulary:
                    tf[ng] += 1
            for term, count in tf.items():
                idx = self.vocabulary[term]
                vec[idx] = (1 + math.log(count)) * self.idf.get(term, 1.0)
            rows.append(vec)
        return rows

    @staticmethod
    def cosine_similarity(query_vec: list[float], doc_vecs: list[list[float]]) -> list[float]:
        q_norm = math.sqrt(sum(v * v for v in query_vec)) or 1.0
        scores = []
        for dv in doc_vecs:
            dot = sum(q * d for q, d in zip(query_vec, dv))
            d_norm = math.sqrt(sum(v * v for v in dv)) or 1.0
            scores.append(dot / (q_norm * d_norm))
        return scores


@dataclass
class RouteResult:
    """A single routing match."""
    name: str
    score: float
    category: str = ""
    description: str = ""
    full_text: str = ""


@dataclass
class RoutingDecision:
    """Full routing decision for a user query."""
    query: str
    providers: list[RouteResult] = field(default_factory=list)
    tools: list[RouteResult] = field(default_factory=list)
    roles: list[RouteResult] = field(default_factory=list)
    top_provider: str = ""
    top_tool: str = ""
    top_role: str = ""

    def best_tools(self, n: int = 5) -> list[RouteResult]:
        return self.tools[:n]

    def best_provider(self) -> str:
        return self.top_provider or "auto"


class SkillRouter:
    def __init__(self):
        self._provider_texts: dict[str, str] = {}
        self._tool_texts: dict[str, str] = {}
        self._role_texts: dict[str, str] = {}
        self._vectorizer: PureTfidf | None = None
        self._provider_vectors: list[list[float]] = []
        self._tool_vectors: list[list[float]] = []
        self._role_vectors: list[list[float]] = []
        self._history: list[dict] = []
        self._built = False

    # ═══ Full-text catalog ═══

    def register_provider(self, name: str, description: str, capabilities: str = ""):
        self._provider_texts[name] = f"{name}. {description}. Capabilities: {capabilities}"

    def register_tool(self, name: str, description: str, category: str = "", params: str = ""):
        self._tool_texts[name] = f"Tool: {name}. Category: {category}. {description}. Parameters: {params}"

    def register_role(self, name: str, description: str):
        self._role_texts[name] = f"Role: {name}. {description}"

    def build(self):
        all_texts = list(self._provider_texts.values()) + list(self._tool_texts.values()) + list(self._role_texts.values())
        if not all_texts:
            return

        self._vectorizer = PureTfidf(ngram_range=(1, 3), max_features=2000)
        self._vectorizer.fit(all_texts)

        all_vectors = self._vectorizer.transform(all_texts)
        n_providers = len(self._provider_texts)
        n_tools = len(self._tool_texts)
        n_roles = len(self._role_texts)

        self._provider_vectors = all_vectors[:n_providers]
        self._tool_vectors = all_vectors[n_providers:n_providers + n_tools]
        self._role_vectors = all_vectors[n_providers + n_tools:]

        self._built = True
        logger.info(f"SkillRouter: {n_providers} providers, {n_tools} tools, {n_roles} roles")

    # ═══ Routing ═══

    def route(self, query: str) -> RoutingDecision:
        """Route a user query to providers, tools, and roles.

        Uses skill graph topology for context-aware routing:
        - If a tool is selected, boost its dependencies and compositions
        - Avoid routing to conflicting skills
        """
        if not self._built:
            self._build_default_catalog()
            self.build()

        result = RoutingDecision(query=query)

        result.providers = self._rank(query, self._provider_texts, self._provider_vectors)
        result.tools = self._rank(query, self._tool_texts, self._tool_vectors)
        result.roles = self._rank(query, self._role_texts, self._role_vectors)

        # ── Skill graph boost ──
        try:
            from ..dna.skill_graph import get_skill_graph
            graph = get_skill_graph()
            for tool in result.tools:
                # Boost dependencies
                deps = graph.get_dependencies(tool.name, recursive=False)
                for dep in deps:
                    for t in result.tools:
                        if t.name == dep:
                            t.score *= 1.5
                # Boost compositions
                comps = graph.get_compositions(tool.name)
                for comp in comps:
                    for t in result.tools:
                        if t.name == comp:
                            t.score *= 1.3
                # Penalize conflicts
                conflicts = graph.get_conflicts(tool.name)
                for conflict in conflicts:
                    for t in result.tools:
                        if t.name == conflict:
                            t.score *= 0.3
            # Re-sort after boosts
            result.tools.sort(key=lambda x: -x.score)
        except Exception:
            pass

        result.top_provider = result.providers[0].name if result.providers else "auto"
        result.top_tool = result.tools[0].name if result.tools else ""
        result.top_role = result.roles[0].name if result.roles else ""

        return result

    def _rank(self, query: str, texts: dict[str, str], vectors: list[list[float]]) -> list[RouteResult]:
        if not texts or self._vectorizer is None or not vectors:
            return []

        query_vec = self._vectorizer.transform([query])
        scores = PureTfidf.cosine_similarity(query_vec[0], vectors)
        names = list(texts.keys())

        results = []
        for name, score in zip(names, scores):
            if score > 0:
                results.append(RouteResult(
                    name=name, score=score,
                    description=texts[name][:200],
                    full_text=texts[name],
                ))
        results.sort(key=lambda x: -x.score)
        return results[:10]

    # ═══ Learning ═══

    def learn(self, prompt: str, chosen: str, success: bool):
        """Learn from routing outcomes (compatible with TinyClassifier API)."""
        self.feed_back(prompt, chosen, success)

    def predict(self, prompt: str, candidates: list[str], stats: dict | None = None) -> str:
        """Predict best provider (compatible with TinyClassifier API).

        Uses TF-IDF semantic matching instead of binary feature vectors.
        """
        if not candidates:
            return ""
        if len(candidates) == 1:
            return candidates[0]
        decision = self.route(prompt)
        for p in decision.providers:
            if p.name in candidates:
                return p.name
        return candidates[0]

    def feed_back(self, query: str, chosen: str, success: bool):
        """Learn from routing outcomes."""
        self._history.append({
            "query": query[:200],
            "chosen": chosen,
            "success": success,
        })
        if len(self._history) > 1000:
            self._history = self._history[-500:]
        self._save_history()

    def get_stats(self) -> dict:
        if not self._history:
            return {"total": 0}
        successes = sum(1 for h in self._history if h["success"])
        return {
            "total": len(self._history),
            "successes": successes,
            "rate": successes / len(self._history),
        }

    # ═══ Persistence ═══

    def _save_history(self):
        try:
            from ..core.async_disk import save_json
            data = {"history": self._history[-200:]}
            save_json(HISTORY_FILE, data, critical=False)
        except Exception:
            pass

    def _load_history(self):
        try:
            if HISTORY_FILE.exists():
                with open(HISTORY_FILE) as f:
                    self._history = [json.loads(line) for line in f if line.strip()]
        except Exception:
            pass

    # ═══ Default catalog ═══

    def _build_default_catalog(self):
        """Auto-populate from system tools, expert roles, and providers."""

        # ── Providers ──
        providers = {
            "siliconflow-flash": ("硅基流动 Qwen2.5-7B 快速模型", "通用对话、翻译、摘要、轻量分析"),
            "siliconflow-reasoning": ("硅基流动 DeepSeek-R1-Distill-Qwen-7B 推理模型", "深度推理、数学、逻辑、代码分析"),
            "siliconflow-small": ("硅基流动 Qwen2.5-1.5B 微型模型", "分类、关键词提取、简单问答"),
            "mofang-flash": ("模力方舟 Qwen2.5-7B 免费模型", "通用对话、文档处理"),
            "mofang-reasoning": ("模力方舟 DeepSeek-R1-Distill-Qwen-7B 推理", "复杂推理、多步思考"),
            "mofang-small": ("模力方舟 Qwen2.5-1.5B 微型", "快速分类、意图识别"),
            "longcat": ("LongCat Flash 免费模型", "通用对话、快速响应"),
            "zhipu": ("智谱 GLM-4-Flash 免费模型", "中文对话、文本理解"),
            "spark": ("讯飞星火 xDeepSeekV3 免费模型", "搜索增强、知识问答"),
            "deepseek": ("DeepSeek V4 Pro 付费模型", "高精度推理、代码生成、复杂分析"),
            "xiaomi": ("小米 MiMo V2 Flash 付费模型", "多模态、图像理解"),
            "aliyun": ("阿里云 Qwen-Turbo/Max 付费模型", "企业级分析、长文本"),
            "dmxapi": ("DMXAPI GPT-5-Mini", "通用对话、代码辅助"),
            "modelscope": ("ModelScope 魔搭社区免费推理", "开源模型推理、Qwen/DeepSeek/Llama"),
            "bailing": ("蚂蚁百灵 Baichuan4", "企业级LLM、Baichuan4旗舰推理"),
            "stepfun": ("阶跃星辰 Step-2", "深度推理、16K长上下文、多模态"),
            "internlm": ("书生 InternLM3", "上海AI Lab、中文推理强、长上下文"),
            "opencode-serve": ("本地 OpenCode Serve", "零延迟、离线可用"),
        }
        for name, (desc, caps) in providers.items():
            self.register_provider(name, desc, caps)

        # ── Tools ──
        for name, tool in SYSTEM_TOOLS.items():
            self.register_tool(
                name, tool["description"],
                category=tool.get("category", ""),
                params=str(tool.get("params", {}))
            )

        # ── Roles ──
        for name, desc in EXPERT_ROLES.items():
            self.register_role(name, desc)

        self._load_history()


# ═══ Global singleton ═══

_router: SkillRouter | None = None
_router_lock = threading.Lock()


def get_router() -> SkillRouter:
    global _router
    if _router is None:
        with _router_lock:
            if _router is None:
                _router = SkillRouter()
                _router._build_default_catalog()
                _router.build()
    return _router

# Backward compatibility alias (core.py uses TinyClassifier)
TinyClassifier = SkillRouter
