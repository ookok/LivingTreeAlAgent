"""EngramStore — O(1) N-gram conditional memory for high-frequency knowledge.

Engram (arxiv 2601.07372): decouples static knowledge lookup from dynamic
computation via N-gram hashing. This is a complementary sparsity axis to
existing vector search (knowledge_base.py).

Two-tier architecture (arxiv 2601.16531):
  Hot tier: N-gram hash lookup → O(1), for frequently accessed knowledge
  Cold tier: fallback to vector search / FTS5 → O(log n), for rare queries

Hot-to-Cold flip dynamics: entries naturally decay from hot to cold based
on access frequency. Cold entries re-promote when accessed frequently.

Usage:
    store = get_engram_store()
    store.insert("GB3095-2012", "环境空气质量标准", category="regulation")
    result = store.lookup("GB3095 颗粒物限值")  # O(1) if hot, else None
    if not result:
        result = await kb.search(...)  # cold tier fallback
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger

ENGRAM_DIR = Path(".livingtree/engram")
ENGRAM_FILE = ENGRAM_DIR / "hot_store.json"
ENGRAM_STATS = ENGRAM_DIR / "stats.json"


@dataclass
class EngramEntry:
    """A single knowledge entry indexed by N-gram hashes."""
    key: str
    value: str
    category: str = "general"
    ngrams: set[str] = field(default_factory=set)
    access_count: int = 0
    last_accessed: float = 0.0
    created_at: float = field(default_factory=time.time)
    hot: bool = True
    collision_count: int = 0


class EngramStore:
    """O(1) N-gram hash lookup for high-frequency knowledge.

    Builds an N-gram index (2-4 grams) over knowledge entries. Lookup
    computes N-gram hashes from query and does direct hash-table lookup.
    Hot entries stay in memory; cold entries are persisted and checked
    if hot miss.
    """

    MAX_HOT_ENTRIES = 5000
    NGRAM_MIN = 2
    NGRAM_MAX = 4

    def __init__(self):
        self._hot: dict[int, list[EngramEntry]] = {}
        self._cold: dict[str, EngramEntry] = {}
        self._key_index: dict[str, str] = {}
        self._total_lookups = 0
        self._hot_hits = 0
        self._cold_hits = 0
        self._misses = 0
        self._load()

    def insert(self, key: str, value: str, category: str = "general",
               hot: bool = True):
        """Insert a knowledge entry with N-gram indexing.

        Args:
            key: The retrieval key (e.g. "GB3095-2012 颗粒物限值")
            value: The knowledge content
            category: Domain category (regulation, standard, formula, etc.)
            hot: Whether to place in hot tier immediately
        """
        entry = EngramEntry(
            key=key, value=value, category=category,
            ngrams=self._compute_ngrams(key), hot=hot,
        )
        self._key_index[entry.key] = value

        if hot:
            if len(self._hot) >= self.MAX_HOT_ENTRIES:
                self._evict_coldest()
            for h in self._ngram_hashes(entry.ngrams):
                if h not in self._hot:
                    self._hot[h] = []
                self._hot[h].append(entry)
        else:
            self._cold[key] = entry

    def lookup(self, query: str) -> Optional[str]:
        """O(1) lookup: compute N-gram hashes, check hot tier, then cold.

        Returns the value string if found, None if miss.
        """
        self._total_lookups += 1
        q_ngrams = self._compute_ngrams(query)
        q_hashes = set(self._ngram_hashes(q_ngrams))

        candidates: dict[str, int] = {}
        for h in q_hashes:
            if h in self._hot:
                for entry in self._hot[h]:
                    overlap = len(q_ngrams & entry.ngrams)
                    if overlap > 0:
                        candidates[entry.key] = candidates.get(entry.key, 0) + overlap

        if candidates:
            best_key = max(candidates, key=lambda k: candidates[k])
            if best_key in self._key_index:
                self._hot_hits += 1
                for h in q_hashes:
                    if h in self._hot:
                        for entry in self._hot[h]:
                            if entry.key == best_key:
                                entry.access_count += 1
                                entry.last_accessed = time.time()
                return self._key_index[best_key]

        for h in q_hashes:
            if h in self._hot:
                for entry in self._hot[h]:
                    entry.collision_count += 1

        for key, entry in self._cold.items():
            if any(ng in query for ng in entry.ngrams):
                self._cold_hits += 1
                entry.access_count += 1
                entry.last_accessed = time.time()
                if entry.access_count >= 3:
                    self._promote_to_hot(key)
                return entry.value

        self._misses += 1
        return None

    def lookup_or_fallback(self, query: str, fallback_fn=None):
        """Lookup with async fallback to cold-tier search.

        Returns (result, source) where source is 'hot', 'cold', or 'fallback'.
        """
        result = self.lookup(query)
        if result is not None:
            return result, "hot" if self._hot_hits > 0 else "cold"
        return fallback_fn(query) if fallback_fn else (None, "miss")

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Search both hot and cold tiers, return ranked results."""
        q_ngrams = self._compute_ngrams(query)
        q_hashes = set(self._ngram_hashes(q_ngrams))

        scores: dict[str, float] = {}
        for h in q_hashes:
            if h in self._hot:
                for entry in self._hot[h]:
                    overlap = len(q_ngrams & entry.ngrams)
                    score = overlap / max(len(q_ngrams), 1)
                    if entry.key in scores:
                        scores[entry.key] = max(scores[entry.key], score)
                    else:
                        scores[entry.key] = score

        results = []
        for key, score in sorted(scores.items(), key=lambda x: -x[1])[:top_k]:
            results.append({"key": key, "value": self._key_index.get(key, ""),
                            "score": round(score, 3), "tier": "hot"})
        return results

    def batch_insert(self, items: list[dict[str, str]], category: str = "general"):
        """Batch insert multiple knowledge items."""
        for item in items:
            self.insert(item["key"], item["value"], category)

    def _promote_to_hot(self, key: str):
        """Promote a cold entry to hot tier."""
        if key not in self._cold:
            return
        entry = self._cold.pop(key)
        entry.hot = True
        if len(self._hot) >= self.MAX_HOT_ENTRIES:
            self._evict_coldest()
        for h in self._ngram_hashes(entry.ngrams):
            if h not in self._hot:
                self._hot[h] = []
            self._hot[h].append(entry)
        logger.debug(f"Engram promoted: {key[:60]} (cold → hot)")

    def _evict_coldest(self):
        """Evict the least-accessed hot entry to cold tier."""
        if not self._hot:
            return
        coldest: EngramEntry | None = None
        for entries in self._hot.values():
            for entry in entries:
                if coldest is None or entry.last_accessed < coldest.last_accessed:
                    coldest = entry
        if coldest:
            for h in self._ngram_hashes(coldest.ngrams):
                if h in self._hot:
                    self._hot[h] = [e for e in self._hot[h] if e.key != coldest.key]
                    if not self._hot[h]:
                        del self._hot[h]
            coldest.hot = False
            self._cold[coldest.key] = coldest
            logger.debug(f"Engram evicted: {coldest.key[:60]} (hot → cold)")

    def stats(self) -> dict[str, Any]:
        """Return lookup statistics and tier sizes."""
        return {
            "hot_entries": sum(len(v) for v in self._hot.values()),
            "cold_entries": len(self._cold),
            "total_lookups": self._total_lookups,
            "hot_hits": self._hot_hits,
            "cold_hits": self._cold_hits,
            "misses": self._misses,
            "hit_rate": round((self._hot_hits + self._cold_hits) / max(self._total_lookups, 1), 3),
            "hot_rate": round(self._hot_hits / max(self._total_lookups, 1), 3),
        }

    def seed_standards(self):
        """Pre-seed with common Chinese environmental standards and regulations.

        Also registers each standard in ContextCodex for semantic compression.
        """
        standards = [
            {"key": "GB3095-2012 环境空气质量标准 污染物浓度限值", "value": "GB3095-2012: SO2年均60μg/m³,日均150μg/m³; NO2年均40μg/m³,日均80μg/m³; PM10年均70μg/m³,日均150μg/m³; PM2.5年均35μg/m³,日均75μg/m³; CO日均4mg/m³; O3日最大8h平均160μg/m³", "category": "standard"},
            {"key": "GB3096-2008 声环境质量标准 噪声限值", "value": "GB3096-2008: 0类(康复疗养)昼50dB夜40dB; 1类(居住)昼55dB夜45dB; 2类(商住混合)昼60dB夜50dB; 3类(工业)昼65dB夜55dB; 4a类(交通干线)昼70dB夜55dB; 4b类(铁路)昼70dB夜60dB", "category": "standard"},
            {"key": "GB3838-2002 地表水环境质量标准 水质分类", "value": "GB3838-2002: I类(源头水); II类(饮用水一级保护区); III类(饮用水二级保护区); IV类(工业用水); V类(农业用水). 指标包括pH 6-9, DO≥2-7.5mg/L, COD≤15-40mg/L, NH3-N≤0.15-2.0mg/L", "category": "standard"},
            {"key": "HJ2.2-2018 大气环境影响评价技术导则 AERSCREEN估算模式", "value": "HJ2.2-2018: 大气环评技术导则. 估算模式AERSCREEN用于筛选评价等级. 一/二/三级评价对应不同深度. 参数: 排气筒高度≥15m, 烟气温度, 出口内径, 排放速率. SO2和NOx需考虑化学转化(分别取4h和1h半衰期)", "category": "regulation"},
            {"key": "HJ2.4-2021 声环境影响评价技术导则 噪声衰减公式", "value": "HJ2.4-2021: 声环评导则. 点声源距离衰减 Lp(r)=Lp(r0)-20lg(r/r0). 线声源衰减 Lp(r)=Lp(r0)-10lg(r/r0). 面声源当a/π<b/π时为面声源. 声屏障衰减计算使用菲涅尔数N=2δ/λ", "category": "regulation"},
            {"key": "HJ169-2018 建设项目环境风险评价技术导则 风险识别", "value": "HJ169-2018: 建设项目环境风险评价. 危险物质临界量按GB18218判定. 重大危险源/非重大危险源. 风险类型: 泄漏/火灾/爆炸. 大气风险预测用SLAB或AFTOX模型. 地表水风险采用完全混合或二维模式", "category": "regulation"},
            {"key": "大气扩散模型 高斯烟羽公式 污染物浓度计算", "value": "高斯烟羽模型: C(x,y,z)=Q/(2πuσyσz)*exp(-y²/(2σy²))*[exp(-(z-H)²/(2σz²))+exp(-(z+H)²/(2σz²))]. Q=源强(g/s), u=风速(m/s), H=有效源高(m). σy,σz=扩散参数, Brigg公式或PG曲线查表", "category": "formula"},
            {"key": "大气扩散模型 高斯烟团公式 瞬时排放", "value": "高斯烟团模型(瞬时源): C(x,y,z,t)=Q/[(2π)^(3/2)σxσyσz]*exp[-(x-ut)²/(2σx²)]*exp[-y²/(2σy²)]*[exp(-(z-H)²/(2σz²))+exp(-(z+H)²/(2σz²))]", "category": "formula"},
            {"key": "噪声叠加公式 声压级合成 dB计算", "value": "声压级叠加: Lp_total=10lg(∑10^(Lpi/10)). 两个相同声压级叠加: Lp+3dB. N个相同声压级叠加: Lp+10lg(N). 声压级相减: Lp_diff=10lg(10^(Lp1/10)-10^(Lp2/10))", "category": "formula"},
            {"key": "EIA报告 环评报告 标准结构 章节", "value": "环评报告标准结构: 1.总则(编制依据/评价因子/评价标准/评价等级/评价范围/保护目标); 2.建设项目工程分析(工艺流程/产污环节/源强核算); 3.环境现状调查与评价(自然环境/环境质量现状); 4.环境影响预测与评价(大气/地表水/地下水/声/固废/生态/风险); 5.环境保护措施及可行性论证; 6.环境影响经济损益分析; 7.环境管理与监测计划; 8.环评结论", "category": "template"},
        ]
        for s in standards:
            self.insert(s["key"], s["value"], s["category"])
        self._seed_codex()
        logger.info(f"EngramStore seeded with {len(standards)} standards/regulations")

    def _seed_codex(self):
        """Register engram entries in ContextCodex for semantic compression."""
        from ..execution.context_codex import get_context_codex
        codex = get_context_codex(seed=False)
        for key in self._key_index:
            codex.auto_generate(key, "standard", layer=2)

    def _compute_ngrams(self, text: str) -> set[str]:
        """Compute 2-NGRAM_MAX character n-grams from text."""
        clean = text.lower().strip()
        ngrams: set[str] = set()
        for n in range(self.NGRAM_MIN, self.NGRAM_MAX + 1):
            for i in range(len(clean) - n + 1):
                ngrams.add(clean[i:i + n])
        return ngrams

    def _ngram_hashes(self, ngrams: set[str]) -> list[int]:
        """Hash n-gram strings to bucket indices."""
        return [int(hashlib.md5(ng.encode()).hexdigest()[:8], 16) % 100003 for ng in ngrams]

    def _save(self):
        try:
            ENGRAM_DIR.mkdir(parents=True, exist_ok=True)
            cold_data = {k: {"key": e.key, "value": e.value, "category": e.category,
                             "access_count": e.access_count, "last_accessed": e.last_accessed,
                             "created_at": e.created_at}
                         for k, e in self._cold.items()}
            ENGRAM_FILE.write_text(json.dumps(cold_data, indent=2, ensure_ascii=False))
            ENGRAM_STATS.write_text(json.dumps(self.stats(), indent=2))
        except Exception as e:
            logger.debug(f"Engram save: {e}")

    def _load(self):
        try:
            if ENGRAM_FILE.exists():
                data = json.loads(ENGRAM_FILE.read_text())
                for entry_data in data.values():
                    entry = EngramEntry(
                        key=entry_data["key"], value=entry_data["value"],
                        category=entry_data.get("category", "general"),
                        ngrams=self._compute_ngrams(entry_data["key"]),
                        access_count=entry_data.get("access_count", 0),
                        last_accessed=entry_data.get("last_accessed", 0.0),
                        created_at=entry_data.get("created_at", time.time()),
                        hot=False,
                    )
                    self._cold[entry.key] = entry
                    self._key_index[entry.key] = entry.value
        except Exception as e:
            logger.debug(f"Engram load: {e}")


_engram_store: EngramStore | None = None


def get_engram_store(seed: bool = True) -> EngramStore:
    global _engram_store
    if _engram_store is None:
        _engram_store = EngramStore()
        if seed and _engram_store._total_lookups == 0 and not _engram_store._cold:
            _engram_store.seed_standards()
    return _engram_store
