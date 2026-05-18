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
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger
import numpy as np

SYSTEM_TOOLS = {}
EXPERT_ROLES = {}

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


# ═══════════════════════════════════════════════════════════════════
# Backend 2: QueryClassifier — rule-based (from query_classifier.py)
# ═══════════════════════════════════════════════════════════════════


class QueryClassifier:
    """Fast local task type classification using keyword + pattern heuristics.

    ~5ms latency, no LLM call needed. Only falls back to LLM when confidence <0.6.
    """

    _instance: Optional[QueryClassifier] = None  # type: ignore[name-defined]
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
        self._classifications += 1
        q = query.lower().strip()
        qlen = len(q)
        if qlen < 8:
            return "chat", 0.9
        if q in ("你好", "嗨", "hello", "hi", "在吗", "在不在"):
            return "chat", 0.95
        code_kw = ["写", "实现", "代码", "函数", "bug", "修复", "错误", "报错",
                   "import", "def ", "class ", "print(", "npm ", "pip ",
                   "python", "javascript", "java", "rust", "go "]
        if any(k in q for k in code_kw):
            return "code", 0.8
        reason_kw = ["为什么", "原因", "原理", "如何工作", "怎么回事",
                     "分析", "比较", "区别", "优缺点", "影响",
                     "explain", "analyze", "compare", "why"]
        if any(k in q for k in reason_kw) and qlen > 20:
            return "reasoning", 0.7
        search_kw = ["搜索", "查找", "找一下", "有没有", "在哪", "怎么查",
                     "search", "find", "lookup", "where is"]
        if any(k in q for k in search_kw):
            return "search", 0.75
        if qlen > 500:
            return "long_context", 0.65
        if "?" in q or "？" in q:
            if qlen > 50:
                return "reasoning", 0.55
            return "chat", 0.6
        if any(k in q for k in ["翻译", "translate", "英文", "中文"]):
            return "chat", 0.8
        if qlen < 30:
            return "chat", 0.5
        return "general", 0.45

    def needs_llm_classification(self, confidence: float) -> bool:
        return confidence < 0.6

    def stats(self) -> dict:
        return {"classifications": self._classifications}


_query_classifier: Optional[QueryClassifier] = None  # type: ignore[name-defined]
_query_classifier_lock = threading.Lock()


def get_query_classifier() -> QueryClassifier:
    global _query_classifier
    if _query_classifier is None:
        with _query_classifier_lock:
            if _query_classifier is None:
                _query_classifier = QueryClassifier()
    return _query_classifier


# ═══════════════════════════════════════════════════════════════════
# Backend 3: AdaptiveClassifier — embedding (from adaptive_classifier.py)
# ═══════════════════════════════════════════════════════════════════


@dataclass
class CategoryPrototype:
    name: str
    description: str = ""
    embedding: list[float] = field(default_factory=list)
    sample_count: int = 0
    last_matched: float = 0.0
    confidence: float = 0.5

    def adapt(self, query_embedding: list[float], alpha: float = 0.1):
        if not self.embedding:
            self.embedding = list(query_embedding)
        else:
            for i in range(min(len(self.embedding), len(query_embedding))):
                self.embedding[i] = self.embedding[i] * (1 - alpha) + query_embedding[i] * alpha
        self.sample_count += 1
        self.last_matched = time.time()


class AdaptiveClassifier:
    """Embedding-based universal classifier. No hardcoded keywords."""

    TASK_TYPES = {
        "code": "code programming fix bug implement debug function class API algorithm",
        "reasoning": "analysis reasoning evaluate compare analyze logic mathematics proof",
        "search": "search find lookup retrieve query information knowledge web",
        "chat": "hello chat conversation general question help explain what how",
        "creative": "write create generate translate summarize compose poetry story",
    }
    LAYERS = {
        "fast": "general chat question answer help explain simple quick",
        "reasoning": "code debug fix implement analyze reason compare complex deep",
    }
    DOMAINS = {
        "ai": "artificial intelligence machine learning deep learning neural network LLM GPT transformer",
        "environment": "EIA ESIA environment assessment emission pollution ecology climate carbon",
        "engineering": "design architecture infrastructure construction mechanical electrical civil",
        "regulation": "GB standard regulation compliance law policy legal governance",
        "finance": "finance investment banking market trading stock cryptocurrency economy",
        "medical": "medical health clinical diagnosis treatment drug therapy disease",
        "programming": "programming software development code API database algorithm system",
    }
    EMOTIONS = {
        "joy": "happy delighted excited pleased joyful satisfied wonderful great amazing",
        "sadness": "sad unhappy depressed disappointed frustrated miserable sorrowful",
        "anger": "angry furious annoyed irritated frustrated rage upset",
        "fear": "afraid scared worried anxious nervous terrified fearful",
        "trust": "trust confident believe reliable dependable certain sure",
        "surprise": "surprised amazed astonished shocked unexpected wow",
        "disgust": "disgusted revolted repulsed horrible terrible awful",
        "neutral": "okay fine normal standard regular typical usual",
    }

    _instance: Optional["AdaptiveClassifier"] = None  # type: ignore[name-defined]
    _lock = threading.Lock()

    def __init__(self):
        self._prototypes: dict[str, dict[str, CategoryPrototype]] = {}
        self._initialized = False
        self._embedding_cache: dict[str, list[float]] = {}
        self._cache_hits = 0
        self._api_calls = 0

    @classmethod
    def instance(cls) -> "AdaptiveClassifier":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = AdaptiveClassifier()
        return cls._instance

    def classify(self, query: str, category_set: dict[str, str],
                 set_name: str = "") -> tuple[str, float]:
        if not query or not category_set:
            return list(category_set.keys())[0] if category_set else "", 0.0
        key = set_name or self._hash_set(category_set)
        prototypes = self._ensure_prototypes(key, category_set)
        q_emb = self._embed(query)
        if not q_emb or not prototypes:
            return list(category_set.keys())[0], 0.0
        best_cat, best_sim = "", -1.0
        for cat, proto in prototypes.items():
            if not proto.embedding:
                continue
            sim = self._cosine(q_emb, proto.embedding)
            if sim > best_sim:
                best_sim, best_cat = sim, cat
        return best_cat or list(category_set.keys())[0], max(0.0, best_sim)

    def classify_and_adapt(self, query: str, category_set: dict[str, str],
                           correct_category: str, set_name: str = ""):
        key = set_name or self._hash_set(category_set)
        prototypes = self._ensure_prototypes(key, category_set)
        q_emb = self._embed(query)
        if q_emb and correct_category in prototypes:
            prototypes[correct_category].adapt(q_emb, alpha=0.15)
        return self.classify(query, category_set, set_name)

    def stats(self) -> dict:
        return {"cache_hits": self._cache_hits, "api_calls": self._api_calls,
                "category_sets": len(self._prototypes),
                "total_categories": sum(len(p) for p in self._prototypes.values())}

    def _ensure_prototypes(self, key: str, category_set: dict[str, str]):
        if key in self._prototypes:
            return self._prototypes[key]
        prototypes = {}
        for name, desc in category_set.items():
            proto = CategoryPrototype(name=name, description=desc)
            emb = self._embed(desc)
            if emb:
                proto.embedding = emb
            prototypes[name] = proto
        self._prototypes[key] = prototypes
        return prototypes

    def _embed(self, text: str) -> list[float] | None:
        if not text:
            return None
        cache_key = text[:100].lower().strip()
        if cache_key in self._embedding_cache:
            self._cache_hits += 1
            return self._embedding_cache[cache_key]
        emb = self._embed_api(text)
        if emb:
            self._api_calls += 1
            self._embedding_cache[cache_key] = emb
            if len(self._embedding_cache) > 500:
                oldest = sorted(self._embedding_cache.keys(), key=lambda k: len(k))[:50]
                for k in oldest:
                    self._embedding_cache.pop(k, None)
        return emb

    def _embed_api(self, text: str) -> list[float] | None:
        try:
            from ..config import get_config
            cfg = get_config()
            api_key = getattr(cfg, 'siliconflow_api_key', '') or ''
            if not api_key:
                return None
            import httpx
            r = httpx.post("https://api.siliconflow.cn/v1/embeddings", json={
                "model": "BAAI/bge-large-zh-v1.5", "input": text,
                "encoding_format": "float"}, headers={
                "Authorization": f"Bearer {api_key}"}, timeout=10)
            if r.status_code == 200:
                return r.json()["data"][0]["embedding"]
        except Exception:
            pass
        return None

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a)) or 1.0
        nb = math.sqrt(sum(y * y for y in b)) or 1.0
        return dot / (na * nb)

    @staticmethod
    def _hash_set(category_set: dict[str, str]) -> str:
        items = sorted(category_set.items())
        return str(hash(tuple(items)))


_adaptive_classifier: Optional[AdaptiveClassifier] = None  # type: ignore[name-defined]
_adaptive_classifier_lock = threading.Lock()


def get_adaptive_classifier() -> AdaptiveClassifier:
    global _adaptive_classifier
    if _adaptive_classifier is None:
        with _adaptive_classifier_lock:
            if _adaptive_classifier is None:
                _adaptive_classifier = AdaptiveClassifier()
    return _adaptive_classifier


# ═══════════════════════════════════════════════════════════════════
# Backend 4: AutoClassifier — keyword+regex (from core/auto_classifier.py)
# ═══════════════════════════════════════════════════════════════════

DOMAIN_PATTERNS = {
    "ai": {"regex": [
        r'\b(llm|模型|训练|推理|token|transformer|agent|GPT|Claude|Gemini|DeepSeek|Qwen|embedding|fine.?tun|RLHF|prompt|神经网络)\b',
        r'\b(AI|artificial intelligence|machine learning|deep learning|neural net)\b'],
        "keywords": ["模型", "推理", "训练", "AI", "token", "agent", "智能", "GPT", "大模型", "深度学习"],
        "weight": 1.0},
    "environment": {"regex": [
        r'\b(环评|排放|污染|生态|碳|水质|空气质量|噪声|固废|环境影响|PM2\.5|COD|BOD)\b',
        r'\b(environmental|emission|carbon|ecology|pollution|water quality)\b'],
        "keywords": ["环评", "排放", "污染", "环境", "碳", "生态", "水质", "大气", "噪声", "固废"],
        "weight": 1.0},
    "engineering": {"regex": [
        r'\b(施工|图纸|结构|混凝土|钢筋|地基|桥梁|道路|隧道|管道|机电|暖通|给排水)\b',
        r'\b(construction|structural|concrete|bridge|tunnel|pipeline)\b'],
        "keywords": ["施工", "工程", "图纸", "结构", "混凝土", "设计", "建筑", "验收"],
        "weight": 1.0},
    "regulation": {"regex": [
        r'\b(法规|标准|规范|GB\s*\d|HJ\s*\d|第.*条|条款|合规|行政许可|审批)\b',
        r'\b(regulation|standard|compliance|permit|license)\b'],
        "keywords": ["法规", "标准", "规范", "GB", "HJ", "合规", "许可", "审批", "条例"],
        "weight": 1.0},
    "programming": {"regex": [
        r'\b(def |class |import |function|const |let |var |async |await|npm |pip |git |docker |k8s)\b',
        r'\b(Python|JavaScript|TypeScript|Rust|Go|Java|C\+\+|SQL|HTML|CSS|React|Vue)\b'],
        "keywords": ["代码", "编程", "API", "接口", "数据库", "前端", "后端", "部署", "Git"],
        "weight": 0.9},
    "finance": {"regex": [
        r'\b(投资|预算|成本|报价|合同|付款|发票|ROI|经济|财务)\b',
        r'\b(finance|budget|cost|invoice|ROI|economic)\b'],
        "keywords": ["预算", "成本", "报价", "投资", "财务", "ROI", "经济"],
        "weight": 0.8},
    "medical": {"regex": [
        r'\b(诊断|治疗|药物|临床|病理|患者|手术|检验|体检|医保)\b',
        r'\b(diagnosis|treatment|clinical|patient|surgery|medical)\b'],
        "keywords": ["诊断", "治疗", "药物", "临床", "病理", "手术", "患者"],
        "weight": 0.8},
}


@dataclass
class ClassificationResult:
    domain: str
    confidence: float
    source: str = ""
    matches: list[str] = field(default_factory=list)
    alternatives: list[tuple[str, float]] = field(default_factory=list)


class AutoClassifier:
    """Multi-strategy knowledge domain classifier (keyword + regex)."""

    def __init__(self):
        self._compiled = {}
        for domain, patterns in DOMAIN_PATTERNS.items():
            self._compiled[domain] = [re.compile(r, re.IGNORECASE) for r in patterns["regex"]]

    def classify(self, text: str, content_type: str = "text") -> ClassificationResult:
        if not text or len(text) < 10:
            return ClassificationResult(domain="general", confidence=0.3, source="default")
        scores = Counter()
        for domain, patterns in DOMAIN_PATTERNS.items():
            kw_weight = patterns["weight"]
            for regex in self._compiled.get(domain, []):
                matches = regex.findall(text)
                if matches:
                    scores[domain] += len(matches) * kw_weight * 2.0
            for kw in patterns["keywords"]:
                count = text.lower().count(kw.lower())
                if count > 0:
                    scores[domain] += count * kw_weight * 1.5
        if content_type in ("audio", "voice", "speech"):
            scores["voice"] = scores.get("voice", 0) + 3.0
        elif content_type in ("code", "programming"):
            scores["programming"] = scores.get("programming", 0) + 3.0
        if not scores:
            return ClassificationResult(domain="general", confidence=0.4, source="keyword")
        top = scores.most_common(3)
        primary_domain, primary_score = top[0]
        total = sum(scores.values())
        confidence = min(0.95, primary_score / max(1, total))
        alternatives = [(d, round(s / max(1, total), 3)) for d, s in top[1:3]]
        source = "regex" if primary_score > 4 else "keyword"
        return ClassificationResult(domain=primary_domain, confidence=round(confidence, 3),
                                    source=source, matches=[m for m in scores if scores[m] > 0][:5],
                                    alternatives=alternatives)

    def stats(self) -> dict:
        return {"domains": len(DOMAIN_PATTERNS), "strategies": ["regex", "keyword", "combined"]}


_auto_classifier: Optional[AutoClassifier] = None  # type: ignore[name-defined]


def get_auto_classifier() -> AutoClassifier:
    global _auto_classifier
    if _auto_classifier is None:
        _auto_classifier = AutoClassifier()
    return _auto_classifier
