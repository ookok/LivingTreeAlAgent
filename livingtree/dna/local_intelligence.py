"""LocalIntelligence — 边缘优先智能层：固化知识，渐进脱离 LLM 依赖.

哲学立场 (LivingTree 核心理念):
  大模型只是最强大脑，不是 AI 的全部。
  真正的智能分布在无数细胞 AI 的前端。
  细胞自身的智慧积累 > 依赖外部模型的调用。

三层智能架构:
  Tier 1 (Direct):  缓存规则 + 符号推理 + 模式匹配 → 零 LLM，即时响应
  Tier 2 (Local):   本地小模型 (Qwen 0.6B-8B) → 本地推理，离线可用
  Tier 3 (Remote):  外部 API 大模型 → 复杂任务，可选增强

知识压缩方向 (从高到低):
  LLM 输出 → 提取可复用模式 → 固化为 Tier 1 规则
  LLM 输出 → 蒸馏到本地模型 → 增强 Tier 2 能力
  Tier 2 输出 → 高频结果缓存 → Tier 1 直接命中

核心指标: LocalIQ — Tier 1+2 可处理的任务占比。
  目标: LocalIQ 从 10% → 50% → 90%，逐步脱离对外部模型的依赖。

Usage:
    li = LocalIntelligence()
    response, tier = await li.respond(query, domain="regulatory_compliance")
    # → ("GB3095标准SO2限值为500μg/m³", Tier.DIRECT)
    li.local_iq()  # → 42.5% (接近一半任务无需LLM)
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from loguru import logger

LOCAL_DIR = Path(".livingtree/local_intelligence")
CACHE_FILE = LOCAL_DIR / "tier1_cache.json"
PATTERNS_FILE = LOCAL_DIR / "learned_patterns.json"
MODEL_META_FILE = LOCAL_DIR / "model_meta.json"

# 已知的本地模型升级路径 (开源模型的演进)
KNOWN_MODEL_UPGRADE_PATH: dict[str, str] = {
    "Qwen3-0.6B": "Qwen3-1.7B",
    "Qwen3-1.7B": "Qwen3-4B",
    "Qwen3-4B": "Qwen3-8B",
    "Qwen3-8B": "Qwen3-14B",
    "Qwen3-14B": "Qwen3-30B-A3B",
    "Qwen3.5-0.6B": "Qwen3.5-1.7B",
    "Qwen3.5-1.7B": "Qwen3.5-4B",
    "Qwen3.5-4B": "Qwen3.5-8B",
}


# ═══════════════════════════════════════════════════════════════════
# Types
# ═══════════════════════════════════════════════════════════════════

class IntelligenceTier(str, Enum):
    DIRECT = "direct"     # Tier 1: 本地规则/缓存 → 零 LLM
    LOCAL = "local"       # Tier 2: 本地小模型 → 离线可用
    REMOTE = "remote"     # Tier 3: 外部 API → 复杂任务


@dataclass
class CachedPattern:
    """固化的知识模式——从 LLM 输出中提取的本地规则."""
    id: str
    pattern: str                  # 匹配模式 (关键词/正则)
    response: str                 # 直接响应
    domain: str = "general"
    confidence: float = 0.7
    hit_count: int = 0            # 命中次数
    source: str = "llm_distilled" # llm_distilled / human_curated / local_model
    created_at: float = field(default_factory=time.time)
    last_hit: float = 0.0

    @property
    def effectiveness(self) -> float:
        return min(1.0, self.hit_count / 10) * self.confidence


@dataclass
class TierResponse:
    """智能响应结果."""
    content: str
    tier: IntelligenceTier
    confidence: float
    latency_ms: float
    source_detail: str = ""       # 命中的具体规则/模型


@dataclass
class LocalIQ:
    """本地智能度量."""
    total_queries: int = 0
    direct_hits: int = 0
    local_hits: int = 0
    remote_hits: int = 0

    @property
    def direct_pct(self) -> float:
        return self.direct_hits / max(self.total_queries, 1)

    @property
    def local_pct(self) -> float:
        return (self.direct_hits + self.local_hits) / max(self.total_queries, 1)

    @property
    def remote_pct(self) -> float:
        return self.remote_hits / max(self.total_queries, 1)

    def summary(self) -> str:
        return (
            f"LocalIQ: {self.local_pct:.0%} "
            f"(Direct: {self.direct_pct:.0%}, Local: {(self.local_hits)/max(self.total_queries,1):.0%}, "
            f"Remote: {self.remote_pct:.0%}) | {self.total_queries} queries"
        )


# ═══════════════════════════════════════════════════════════════════
# LocalIntelligence Engine
# ═══════════════════════════════════════════════════════════════════

class LocalIntelligence:
    """边缘优先智能——让 Agent 自身成为模型，LLM 只是可选的增强.

    三层决策:
      Tier 1 (DIRECT): 先查本地缓存/规则 → 命中了直接返回
      Tier 2 (LOCAL):  再试本地小模型 → 如果有的话
      Tier 3 (REMOTE): 最后才调用外部 API
    """

    MAX_CACHE_SIZE = 1000    # Tier 1 最多缓存1000条
    MAX_PATTERN_LENGTH = 200

    def __init__(self, consciousness: Any = None, local_model: Any = None):
        self._consciousness = consciousness  # Tier 3
        self._local_model = local_model      # Tier 2 (e.g., Qwen local)
        self._local_model_name: str = self._detect_model_name()
        self._cache: OrderedDict[str, CachedPattern] = OrderedDict()
        self._iq = LocalIQ()
        self._domain_stats: dict[str, LocalIQ] = {}
        self._model_history: list[dict] = []  # [{model_name, started_at, patterns_count, ...}]
        self._load()

    # ═══ 核心: 三层智能响应 ═══

    async def respond(self, query: str, domain: str = "general") -> TierResponse:
        """三层智能路由——从快到慢，从本地到远程."""
        self._iq.total_queries += 1
        start = time.time()

        # ── Tier 1: Direct ──
        cached = self._match_cache(query, domain)
        if cached and cached.confidence >= 0.7:
            cached.hit_count += 1
            cached.last_hit = time.time()
            self._iq.direct_hits += 1
            return TierResponse(
                content=cached.response, tier=IntelligenceTier.DIRECT,
                confidence=cached.confidence,
                latency_ms=(time.time() - start) * 1000,
                source_detail=f"cached:{cached.id}",
            )

        # ── Tier 1: Pattern match ──
        pattern_match = self._match_pattern(query, domain)
        if pattern_match:
            self._iq.direct_hits += 1
            return TierResponse(
                content=pattern_match, tier=IntelligenceTier.DIRECT,
                confidence=0.85,
                latency_ms=(time.time() - start) * 1000,
                source_detail="pattern_match",
            )

        # ── Tier 1: ContextCodex lookup ──
        codex_result = self._codex_lookup(query)
        if codex_result:
            self._iq.direct_hits += 1
            return TierResponse(
                content=codex_result, tier=IntelligenceTier.DIRECT,
                confidence=0.8,
                latency_ms=(time.time() - start) * 1000,
                source_detail="context_codex",
            )

        # ── Tier 2: Local Model ──
        if self._local_model:
            try:
                local_response = await self._query_local(query, domain)
                if local_response:
                    self._iq.local_hits += 1
                    self._learn_from_response(query, local_response, domain)
                    return TierResponse(
                        content=local_response, tier=IntelligenceTier.LOCAL,
                        confidence=0.6,
                        latency_ms=(time.time() - start) * 1000,
                        source_detail="local_model",
                    )
            except Exception:
                pass

        # ── Tier 3: Remote LLM ──
        if self._consciousness:
            self._iq.remote_hits += 1
            response = await self._query_remote(query, domain)
            # 从 LLM 输出中学习，固化到 Tier 1
            self._learn_from_llm(query, response, domain)
            return TierResponse(
                content=response, tier=IntelligenceTier.REMOTE,
                confidence=0.9,
                latency_ms=(time.time() - start) * 1000,
                source_detail="remote_llm",
            )

        return TierResponse(
            content="无法处理此查询", tier=IntelligenceTier.REMOTE,
            confidence=0.1, latency_ms=0,
        )

    # ═══ Tier 1: Direct — 零 LLM ═══

    def _match_cache(self, query: str, domain: str) -> CachedPattern | None:
        """在本地缓存中查找匹配."""
        qhash = hashlib.sha256(query.encode()).hexdigest()[:12]
        if qhash in self._cache:
            return self._cache[qhash]
        # 模糊匹配（>80% 相似）
        for pattern in reversed(list(self._cache.values())):
            if pattern.domain == domain or pattern.domain == "general" or not domain:
                if self._similarity(query, pattern.pattern) > 0.8:
                    return pattern
        return None

    def _match_pattern(self, query: str, domain: str) -> str | None:
        """基于学习到的结构化模式匹配."""
        patterns = self._load_patterns().get(domain, {})
        for rule_id, rule in patterns.items():
            try:
                if re.search(rule["regex"], query, re.IGNORECASE):
                    rule["hits"] = rule.get("hits", 0) + 1
                    self._save_patterns(patterns)
                    return rule["response"]
            except re.error:
                continue
        return None

    def _codex_lookup(self, query: str) -> str | None:
        """从 ContextCodex 符号表查找."""
        try:
            from ..execution.context_codex import get_context_codex
            codex = get_context_codex(seed=False)
            # 检查 query 中是否包含已知 codex 符号的含义
            for symbol, entry in codex._table.items():
                if entry.meaning.lower() in query.lower():
                    return f"{symbol}: {entry.meaning}"
        except Exception:
            pass
        return None

    # ═══ Tier 2: Local Model ═══

    async def _query_local(self, query: str, domain: str) -> str | None:
        """查询本地小模型."""
        if not self._local_model:
            return None
        try:
            if hasattr(self._local_model, 'generate'):
                return await self._local_model.generate(query, max_tokens=200)
        except Exception:
            pass
        return None

    # ═══ Tier 3: Remote LLM ═══

    async def _query_remote(self, query: str, domain: str) -> str:
        """查询远程大模型."""
        try:
            raw = await self._consciousness.query(
                f"[{domain}] {query}", max_tokens=500, temperature=0.3)
            return raw.strip()
        except Exception:
            return f"[无法连接LLM] {query}"

    # ═══ Knowledge Compression: LLM → Local ═══

    def _learn_from_llm(self, query: str, response: str, domain: str):
        """从 LLM 回复中提取可复用的本地知识.

        这是核心机制——每次 LLM 调用都是学习机会:
          1. 缓存精确匹配 (query→response)
          2. 提取模式 (正则→通用响应)
          3. 更新领域知识
        """
        # 1. 缓存精确 Q&A
        qhash = hashlib.sha256(query.encode()).hexdigest()[:12]
        self._cache[qhash] = CachedPattern(
            id=qhash, pattern=query, response=response,
            domain=domain, confidence=0.85, hit_count=1,
            source="llm_distilled",
        )

        # 2. 从回复中提取可复用模式
        self._extract_patterns_from_response(query, response, domain)

        # 3. LRU 修剪
        if len(self._cache) > self.MAX_CACHE_SIZE:
            # 移除最不常用的
            sorted_items = sorted(
                self._cache.items(),
                key=lambda x: x[1].effectiveness,
            )
            for key, _ in sorted_items[:50]:
                del self._cache[key]

        self._save_cache()

    def _learn_from_response(self, query: str, response: str, domain: str):
        """从本地模型响应中学习."""
        qhash = hashlib.sha256(query.encode()).hexdigest()[:12]
        if qhash not in self._cache:
            self._cache[qhash] = CachedPattern(
                id=qhash, pattern=query, response=response,
                domain=domain, confidence=0.6,
                source="local_model",
            )
            self._save_cache()

    def _extract_patterns_from_response(self, query: str, response: str, domain: str):
        """从 LLM 回复中提取可复用的结构化模式.

        例如: "GB3095规定的SO2限值是500μg/m³"
          → 模式: r"GB3095.*SO2.*限值" → "500μg/m³ (GB3095-2012 二级标准)"
        """
        patterns = self._load_patterns()
        domain_patterns = patterns.setdefault(domain, {})

        # 检测回复中的定义性语句
        definition_regex = re.findall(
            r'(?:根据|依据|按照)([^，。,\.]{10,60})(?:规定|标准|要求)',
            response)
        for defn in definition_regex[:3]:
            rule_id = hashlib.sha256(defn.encode()).hexdigest()[:8]
            if rule_id not in domain_patterns:
                # 构建模糊匹配正则
                keywords = defn.strip().replace(" ", "|")
                domain_patterns[rule_id] = {
                    "regex": keywords[:100],
                    "response": response[:300],
                    "hits": 0,
                }

        self._save_patterns(patterns)

    # ═══ Helpers ═══

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        """简单文本相似度."""
        a_words = set(a.lower().split())
        b_words = set(b.lower().split())
        if not a_words or not b_words:
            return 0.0
        return len(a_words & b_words) / len(a_words | b_words)

    def local_iq(self) -> LocalIQ:
        return self._iq

    def domain_iq(self, domain: str) -> LocalIQ:
        return self._domain_stats.get(domain, LocalIQ())

    # ═══ Persistence ═══

    def _save_cache(self):
        try:
            LOCAL_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                "cache": {
                    k: {
                        "id": v.id, "pattern": v.pattern, "response": v.response,
                        "domain": v.domain, "confidence": v.confidence,
                        "hit_count": v.hit_count, "source": v.source,
                        "created_at": v.created_at, "last_hit": v.last_hit,
                    }
                    for k, v in list(self._cache.items())[-500:]
                },
                "iq": {
                    "total": self._iq.total_queries,
                    "direct": self._iq.direct_hits,
                    "local": self._iq.local_hits,
                    "remote": self._iq.remote_hits,
                },
            }
            (LOCAL_DIR / "tier1_cache.json").write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.debug(f"LocalIntelligence save: {e}")

    def _load(self):
        try:
            cf = LOCAL_DIR / "tier1_cache.json"
            if cf.exists():
                data = json.loads(cf.read_text(encoding="utf-8"))
                for k, v in data.get("cache", {}).items():
                    self._cache[k] = CachedPattern(**v)
                iq = data.get("iq", {})
                self._iq = LocalIQ(
                    total_queries=iq.get("total", 0),
                    direct_hits=iq.get("direct", 0),
                    local_hits=iq.get("local", 0),
                    remote_hits=iq.get("remote", 0),
                )
                logger.info(f"LocalIntelligence: loaded {len(self._cache)} cached patterns")
            self._load_model_meta()
        except Exception as e:
            logger.debug(f"LocalIntelligence load: {e}")

    def _load_patterns(self) -> dict:
        try:
            pf = LOCAL_DIR / "learned_patterns.json"
            if pf.exists():
                return json.loads(pf.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _save_patterns(self, patterns: dict):
        try:
            LOCAL_DIR.mkdir(parents=True, exist_ok=True)
            (LOCAL_DIR / "learned_patterns.json").write_text(
                json.dumps(patterns, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def stats(self) -> dict[str, Any]:
        return {
            "cached_patterns": len(self._cache),
            "local_model": self._local_model_name or "none",
            "local_iq": self._iq.summary(),
            "domain_count": len(self._domain_stats),
            "model_upgrades": len(self._model_history),
            "recommended_upgrade": self.recommended_upgrade(),
        }

    # ═══ Model Versioning & Knowledge Migration ═══

    async def auto_connect_local(self, base_url: str = "http://localhost:8000/v1",
                                  model_name: str = "qwen3.5-local",
                                  timeout: float = 5.0) -> bool:
        """自动检测并连接本地 vLLM/OpenAI 兼容模型服务.

        适用于 deploy_local_model.sh 部署的 vLLM 服务。
        如果检测不到本地模型，自动降级到远程 LLM（无需手动配置）。

        Returns:
            是否成功连接
        """
        try:
            import httpx
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(f"{base_url}/models")
                if resp.status_code == 200:
                    models = resp.json()
                    model_ids = [m.get("id", "") for m in models.get("data", [])]
                    logger.info(f"LocalIntelligence: detected {len(model_ids)} models at {base_url}")

                    # 创建简单的 OpenAI 兼容客户端包装
                    self._local_model = _OpenAILocalModel(base_url, model_name)
                    self._local_model_name = model_name
                    return True
        except Exception as e:
            logger.info(f"LocalIntelligence: no local model detected at {base_url} ({e})")
            logger.info("LocalIntelligence: falling back to remote LLM (Tier 3)")
        return False

    def _detect_model_name(self) -> str:
        """检测当前本地模型名称."""
        if not self._local_model:
            return ""
        for attr in ("model_name", "name", "model_id", "_model_name"):
            name = getattr(self._local_model, attr, "")
            if name:
                return str(name)
        return type(self._local_model).__name__

    def recommended_upgrade(self) -> str | None:
        """推荐升级到的下一个开源模型."""
        if not self._local_model_name:
            return None
        # 精确匹配
        if self._local_model_name in KNOWN_MODEL_UPGRADE_PATH:
            return KNOWN_MODEL_UPGRADE_PATH[self._local_model_name]
        # 模糊匹配（从名称中提取关键部分）
        for current, upgrade in KNOWN_MODEL_UPGRADE_PATH.items():
            if current.lower() in self._local_model_name.lower():
                return upgrade
        return None

    async def upgrade_local_model(
        self, new_model: Any, validate: bool = True,
    ) -> dict[str, Any]:
        """升级本地模型并迁移已有知识.

        Args:
            new_model: 新的本地模型实例
            validate: 是否验证知识迁移质量

        Returns:
            {success, patterns_retained, patterns_lost, benchmark}
        """
        old_name = self._local_model_name
        old_pattern_count = len(self._cache)
        result = {
            "success": False,
            "old_model": old_name,
            "new_model": "",
            "patterns_before": old_pattern_count,
            "patterns_retained": 0,
            "patterns_discarded": 0,
            "benchmark": {},
        }

        # 1. 记录旧模型元数据
        self._model_history.append({
            "model_name": old_name or "unknown",
            "ended_at": time.time(),
            "patterns_count": old_pattern_count,
            "iq_snapshot": {
                "total": self._iq.total_queries,
                "direct": self._iq.direct_hits,
                "local": self._iq.local_hits,
            },
        })

        # 2. 切换模型
        self._local_model = new_model
        self._local_model_name = self._detect_model_name()
        result["new_model"] = self._local_model_name

        # 3. 知识迁移：搁置信度低且从未命中过的缓存
        discarded = 0
        retain_keys = []
        for key, pattern in list(self._cache.items()):
            # 保留标准：高命中或高置信度或人工策展
            if pattern.hit_count >= 3 or pattern.confidence >= 0.9 or pattern.source == "human_curated":
                retain_keys.append(key)
            else:
                discarded += 1

        # 重建缓存，移除低质量条目
        new_cache: OrderedDict[str, CachedPattern] = OrderedDict()
        for key in retain_keys:
            if key in self._cache:
                new_cache[key] = self._cache[key]
        self._cache = new_cache

        result["patterns_retained"] = len(self._cache)
        result["patterns_discarded"] = discarded

        # 4. 验证迁移质量
        if validate and self._cache:
            result["benchmark"] = await self._validate_migration(old_name)

        result["success"] = True
        logger.info(
            f"LocalIntelligence: upgraded {old_name} → {self._local_model_name} "
            f"(retained {result['patterns_retained']}/{old_pattern_count} patterns, "
            f"discarded {discarded})")

        self._save_cache()
        self._save_model_meta()
        return result

    async def _validate_migration(self, old_model_name: str) -> dict:
        """验证知识迁移质量：抽样测试缓存一致性."""
        if not self._consciousness or not self._cache:
            return {"tested": 0}

        # 抽样10条缓存
        samples = list(self._cache.values())[-10:]
        passed = 0
        failed = 0

        for pattern in samples:
            try:
                # 用新模型重新生成，和缓存对比
                prompt = f"Briefly answer: {pattern.pattern[:100]}"
                new_response = ""
                if hasattr(self._local_model, 'generate'):
                    new_response = await self._local_model.generate(
                        prompt, max_tokens=100)

                if new_response and len(new_response) > 5:
                    # 简单检查：新回答是否包含关键信息
                    cached_keywords = set(pattern.response.lower().split()[:10])
                    new_keywords = set(new_response.lower().split()[:10])
                    overlap = len(cached_keywords & new_keywords) / max(len(cached_keywords), 1)
                    if overlap > 0.3:
                        passed += 1
                    else:
                        failed += 1
            except Exception:
                failed += 1

        return {
            "tested": passed + failed,
            "passed": passed,
            "failed": failed,
            "retention_rate": round(passed / max(passed + failed, 1), 2),
        }

    def _save_model_meta(self):
        try:
            LOCAL_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                "current_model": self._local_model_name,
                "history": self._model_history,
                "recommended_upgrade": self.recommended_upgrade(),
            }
            MODEL_META_FILE.write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def _load_model_meta(self):
        try:
            if MODEL_META_FILE.exists():
                data = json.loads(MODEL_META_FILE.read_text())
                self._local_model_name = self._local_model_name or data.get("current_model", "")
                self._model_history = data.get("history", [])
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════
# Helper: OpenAI-compatible local model wrapper
# ═══════════════════════════════════════════════════════════════════

class _OpenAILocalModel:
    """OpenAI 兼容的本地模型客户端（vLLM / Ollama / llama.cpp server）. """

    def __init__(self, base_url: str, model_name: str):
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.name = model_name

    async def generate(self, prompt: str, max_tokens: int = 200) -> str:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    json={
                        "model": self.model_name,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": max_tokens,
                        "temperature": 0.3,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "")
        except Exception:
            pass
        return ""


# ── Singleton ──────────────────────────────────────────────────────

_local_intelligence: LocalIntelligence | None = None


def get_local_intelligence(
    consciousness: Any = None, local_model: Any = None,
) -> LocalIntelligence:
    global _local_intelligence
    if _local_intelligence is None:
        _local_intelligence = LocalIntelligence(
            consciousness=consciousness, local_model=local_model)
    return _local_intelligence
