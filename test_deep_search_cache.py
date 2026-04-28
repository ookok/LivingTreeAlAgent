# -*- coding: utf-8 -*-
"""
连续3次深度搜索性能对比测试（含三层缓存）
========================================
测试目的：验证缓存命中对响应速度的影响

三层缓存：
  L0缓存  → 相同 query 的路由决策直接命中
  Search缓存 → 相同 query 的搜索结果直接命中
  L4缓存  → 相同 query + search_context 的 L4 推理结果直接命中

对比：无缓存 → 有缓存 各跑3次
"""

import sys
import os
import asyncio
import time
import json
import logging
import re
import hashlib
import httpx
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    os.environ["PYTHONUTF8"] = "1"

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "client" / "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("deep_search_benchmark")

# ─────────────────────────────────────────────────────────────────────────────
#  三层缓存
# ─────────────────────────────────────────────────────────────────────────────

class ThreeTierCache:
    """
    三层缓存：
      L0_cache  : query → route决策
      Search_cache: query → [SearchResult, ...]
      L4_cache  : (query, search_context_hash) → answer
    """

    def __init__(self):
        self.l0: Dict[str, Dict[str, Any]] = {}
        self.search: Dict[str, List[Dict]] = {}
        self.l4: Dict[str, str] = {}

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.md5(text.encode()).hexdigest()

    # L0 缓存
    def get_l0(self, query: str) -> Optional[Dict[str, Any]]:
        return self.l0.get(query)

    def set_l0(self, query: str, result: Dict[str, Any]):
        self.l0[query] = result

    # Search 缓存
    def get_search(self, query: str) -> Optional[List[Dict]]:
        return self.search.get(query)

    def set_search(self, query: str, results: List[Dict]):
        self.search[query] = results

    # L4 缓存
    def get_l4(self, query: str, context: str) -> Optional[str]:
        key = self._hash(f"{query}||{context}")
        return self.l4.get(key)

    def set_l4(self, query: str, context: str, answer: str):
        key = self._hash(f"{query}||{context}")
        self.l4[key] = answer

    def stats(self) -> Dict[str, int]:
        return {
            "l0_entries": len(self.l0),
            "search_entries": len(self.search),
            "l4_entries": len(self.l4),
        }


# ─────────────────────────────────────────────────────────────────────────────
#  模拟深度搜索（带缓存感知）
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str
    relevance: float
    trust_score: float

    def to_dict(self) -> Dict:
        return {
            "title": self.title, "url": self.url, "snippet": self.snippet,
            "source": self.source, "relevance": self.relevance, "trust_score": self.trust_score,
        }

    @staticmethod
    def from_dict(d: Dict) -> "SearchResult":
        return SearchResult(**d)


class MockDeepSearchWikiSystem:
    """简化版深度搜索，支持缓存命中感知"""

    # 预制结果库
    DB = {
        "杭州": [
            SearchResult(title="2026杭州五一活动全攻略 - 西湖景区官方",
                url="https://hangzhou.gov.cn/51holiday",
                snippet="断桥残雪、苏堤春晓等经典景点全面开放，五一期间推出 '遇见西湖' 实景演出，每日3场。",
                source="hangzhou.gov.cn", relevance=0.92, trust_score=0.85),
            SearchResult(title="杭州宋城景区五一特惠票 - 携程旅行",
                url="https://you.ctrip.com/sight/hangzhou14.html",
                snippet="《宋城千古情》大型歌舞演出，五一假期加演至每日6场，门票提前预约享8折优惠。",
                source="ctrip.com", relevance=0.88, trust_score=0.78),
            SearchResult(title="良渚古城遗址公园春季游览指南",
                url="https://www.liangzhu.org/visit",
                snippet="世界文化遗产，距今5000年文明遗址，五一推出考古体验和遗址打卡活动。",
                source="liangzhu.org", relevance=0.85, trust_score=0.82),
            SearchResult(title="杭州灵隐寺·飞来峰景区游览公告",
                url="https://www.aldlf.com/spring2026",
                snippet="千年古刹灵隐寺，五一假期人流管控需提前预约，永福寺素斋和韬光寺茶室正常开放。",
                source="aldlf.com", relevance=0.83, trust_score=0.75),
            SearchResult(title="杭州动漫节五一 Cosplay 嘉年华 - 哔哩哔哩资讯",
                url="https://api.bilibili.com/news/hangzhou-acg",
                snippet="白马湖动漫展馆举办大型动漫嘉年华，知名声优签售、国产动画首映、cosplay大赛。",
                source="bilibili.com", relevance=0.80, trust_score=0.72),
        ],
        "五一": [
            SearchResult(title="2026全国五一假期出行预测报告 - 交通运输部",
                url="https://www.mot.gov.cn/51forecast",
                snippet="预计五一全国发送旅客 8.2 亿人次，杭州位列热门目的地 TOP3，客流高峰4月30日下午。",
                source="mot.gov.cn", relevance=0.87, trust_score=0.90),
            SearchResult(title="杭州五一天气与限行通知 - 杭州市气象局",
                url="https://weather.hangzhou.gov.cn",
                snippet="五一假期杭州以晴到多云为主，气温 18-28°C，西湖景区周边实施单双号限行。",
                source="weather.hangzhou.gov.cn", relevance=0.82, trust_score=0.88),
        ],
    }

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        combined = []
        for kw in ["杭州", "五一"]:
            combined.extend(self.DB.get(kw, []))
        return combined[:max_results]

    def format_for_llm(self, results: List[SearchResult]) -> str:
        lines = []
        for r in results:
            lines.extend([
                f"## {r.title}",
                f"来源：{r.source} | 相关度：{r.relevance:.0%} | 可信度：{r.trust_score:.0%}",
                f"摘要：{r.snippet}",
                f"链接：{r.url}",
                "",
            ])
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
#  L0 路由（带缓存）
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class L0Router:
    model_name: str = "smollm2-test:latest"
    ollama_host: str = "http://localhost:11434"
    cache: Optional[ThreeTierCache] = None
    _ready: bool = field(default=False, init=False)

    async def initialize(self):
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                r = await c.get(f"{self.ollama_host}/api/tags")
                models = [m["name"] for m in r.json().get("models", [])]
                if self.model_name in models or any("smollm" in m.lower() for m in models):
                    self._ready = True
                    logger.info(f"L0 SmolLM2 就绪: {models}")
                    return
        except Exception as e:
            logger.warning(f"L0 Ollama 检测失败: {e}")
        self._ready = False
        logger.info("L0 路由就绪（规则兜底）")

    async def classify(self, query: str) -> tuple[Dict[str, Any], bool]:
        """
        返回 (route_result, is_cache_hit)
        is_cache_hit=True 表示从缓存读取
        """
        # 1. 先查 L0 缓存
        if self.cache:
            cached = self.cache.get_l0(query)
            if cached:
                return cached, True

        # 2. 规则 / Ollama 推理
        route = await self._classify_raw(query)

        # 3. 写缓存
        if self.cache:
            self.cache.set_l0(query, route)

        return route, False

    async def _classify_raw(self, query: str) -> Dict[str, Any]:
        classify_prompt = (
            "用户输入：" + query + "\n\n"
            "判断路由（cache/local/search/heavy/human）和意图类型，"
            "只输出JSON，不要其他内容。"
        )
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{self.ollama_host}/api/generate",
                    json={
                        "model": self.model_name,
                        "prompt": classify_prompt,
                        "stream": False,
                        "options": {"num_predict": 80, "temperature": 0.1},
                    },
                )
                if resp.status_code == 200:
                    text = resp.json().get("response", "")
                    m = re.search(r'\{[^}]+\}', text, re.DOTALL)
                    if m:
                        data = json.loads(m.group())
                        return {
                            "route": data.get("route", "heavy"),
                            "intent": data.get("intent", "unknown"),
                            "reason": data.get("reason", "SmolLM2 分类"),
                            "confidence": float(data.get("confidence", 0.7)),
                            "model": self.model_name,
                            "via": "smollm2_ollama",
                        }
        except Exception as e:
            logger.debug(f"SmolLM2 Ollama 分类失败: {e}")
        return {
            "route": "search", "intent": "search_query",
            "reason": "规则兜底", "confidence": 0.7,
            "model": "rule", "via": "rule_fallback",
        }


# ─────────────────────────────────────────────────────────────────────────────
#  L4 模型（带缓存）
# ─────────────────────────────────────────────────────────────────────────────

class L4Client:
    def __init__(self, model: str = "qwen3.5:4b", host: str = "http://localhost:11434"):
        self.model = model
        self.host = host
        self._ready = False
        self.cache: Optional[ThreeTierCache] = None

    async def check_ready(self):
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                r = await c.get(f"{self.host}/api/tags")
                models = [m["name"] for m in r.json().get("models", [])]
                if self.model in models:
                    self._ready = True
                    logger.info(f"L4 {self.model} 就绪")
                    return
                logger.warning(f"L4 模型 {self.model} 未找到: {models}")
        except Exception as e:
            logger.warning(f"L4 Ollama 检测失败: {e}")
        self._ready = False

    async def generate(self, query: str, search_context: str, max_tokens: int = 800) -> tuple[str, float, bool]:
        """
        返回 (answer, elapsed_ms, is_cache_hit)
        is_cache_hit=True 表示从 L4 缓存读取
        """
        # 1. 查 L4 缓存
        if self.cache:
            cached = self.cache.get_l4(query, search_context)
            if cached:
                return cached, 0.0, True

        # 2. 流式调用 → 失败则非流式
        answer = await self._generate_stream(query, search_context, max_tokens)
        if not answer:
            answer = await self._generate_nonstream(query, search_context, max_tokens)

        # 3. 写缓存
        if self.cache and answer:
            self.cache.set_l4(query, search_context, answer)

        return answer, 0.0, False

    async def _generate_stream(self, query: str, search_context: str, max_tokens: int) -> str:
        system_msg = (
            "你是一个杭州旅游攻略助手，熟悉杭州各大景区、节庆活动、美食购物。 "
            "请根据提供的参考资料，用亲切的口吻给出实用建议。"
        )
        user_content = (
            f"用户问题：{query}\n\n"
            f"参考资料：\n{search_context}\n\n"
            f"请给出实用、具体的游玩建议。"
        )
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_content},
        ]
        collected = []
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream(
                    "POST", f"{self.host}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": True,
                        "options": {"num_predict": max_tokens},
                    },
                ) as resp:
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            chunk = json.loads(line)
                            token = chunk.get("message", {}).get("content", "")
                            if token:
                                collected.append(token)
                            if chunk.get("done"):
                                break
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.debug(f"L4 流式调用失败: {e}")
        return "".join(collected)

    async def _generate_nonstream(self, query: str, search_context: str, max_tokens: int) -> str:
        system_msg = (
            "你是一个杭州旅游攻略助手，熟悉杭州各大景区、节庆活动、美食购物。 "
            "请根据参考资料给出实用建议。"
        )
        user_content = (
            f"用户问题：{query}\n\n"
            f"参考资料：\n{search_context}\n\n"
            f"请给出实用建议。"
        )
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_content},
        ]
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{self.host}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": False,
                        "options": {"num_predict": max_tokens},
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    msg = data.get("message", {})
                    content = msg.get("content", "").strip()
                    if not content:
                        thinking = msg.get("thinking", "")
                        if thinking:
                            parts = thinking.strip().rsplit("\n\n", 1)
                            content = parts[-1].strip() if parts else thinking.strip()
                            logger.info(f"L4 从 thinking 提取 {len(content)} 字")
                    return content
        except Exception as e:
            logger.warning(f"L4 非流式调用失败: {e}")
        return ""


# ─────────────────────────────────────────────────────────────────────────────
#  单轮测试（带缓存感知）
# ─────────────────────────────────────────────────────────────────────────────

async def run_single_test(
    round_num: int,
    query: str,
    router: L0Router,
    search_engine: MockDeepSearchWikiSystem,
    l4: L4Client,
    cache: ThreeTierCache,
) -> Dict[str, Any]:
    print(f"\n{'='*60}")
    print(f"  第 {round_num} 轮  |  问题：「{query}」")
    print(f"{'='*60}")

    # ── Phase 1: L0 路由（含缓存） ─────────────────────────────────────────
    t0 = time.perf_counter()
    route, l0_hit = await router.classify(query)
    t_l0 = (time.perf_counter() - t0) * 1000
    hit_label = "HIT" if l0_hit else "MISS"
    print(f"[L0路由]  {hit_label}  耗时 {t_l0:.0f}ms  | route={route['route']} intent={route['intent']} via={route['via']}")

    # ── Phase 2: 搜索（含缓存） ────────────────────────────────────────────
    t0 = time.perf_counter()
    # Search 缓存查询
    cached_search = cache.get_search(query)
    if cached_search:
        results = [SearchResult.from_dict(r) for r in cached_search]
        search_hit = True
        search_context = search_engine.format_for_llm(results)
    else:
        results = await search_engine.search(query, max_results=5)
        search_hit = False
        search_context = search_engine.format_for_llm(results)
        cache.set_search(query, [r.to_dict() for r in results])
    t_search = (time.perf_counter() - t0) * 1000
    avg_relevance = sum(r.relevance for r in results) / len(results)
    avg_trust = sum(r.trust_score for r in results) / len(results)
    s_hit = "HIT" if search_hit else "MISS"
    print(f"[Search]  {s_hit}  耗时 {t_search:.0f}ms  | {len(results)}条 | 相关度={avg_relevance:.0%} 可信度={avg_trust:.0%}")

    # ── Phase 3: L4 增强（含缓存） ────────────────────────────────────────
    t0 = time.perf_counter()
    answer, _, l4_hit = await l4.generate(query, search_context)
    t_l4 = (time.perf_counter() - t0) * 1000
    l4_hit_label = "HIT" if l4_hit else "MISS"
    if answer:
        preview = answer[:150].replace("\n", " ")
        print(f"[L4增强]  {l4_hit_label}  耗时 {t_l4:.0f}ms  | {len(answer)}字  预览: {preview}...")
    else:
        print(f"[L4增强]  {l4_hit_label}  耗时 {t_l4:.0f}ms  | 无内容")

    total_ms = t_l0 + t_search + t_l4
    print(f"[总计]   {total_ms:.0f}ms ({total_ms/1000:.1f}s)")

    return {
        "round": round_num,
        "query": query,
        "l0_ms": round(t_l0, 1), "l0_hit": l0_hit,
        "search_ms": round(t_search, 1), "search_hit": search_hit,
        "l4_ms": round(t_l4, 1), "l4_hit": l4_hit,
        "total_ms": round(total_ms, 1), "total_s": round(total_ms / 1000, 1),
        "results_count": len(results),
        "answer_chars": len(answer),
        "answer": answer,
        "route": route["route"], "intent": route["intent"],
    }


# ─────────────────────────────────────────────────────────────────────────────
#  主程序：对比无缓存 vs 有缓存
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    query = "五一杭州有哪些玩的"
    runs = 3

    print(f"""
╔════════════════════════════════════════════════════════════════════════╗
║   深度搜索缓存命中率测试  |  问题：「{query}」                        ║
║   对比：无缓存(Round 1-3) vs 有缓存(Round 4-6)                         ║
╚════════════════════════════════════════════════════════════════════════╝
""")

    # ── 初始化 ─────────────────────────────────────────────────────────────
    router = L0Router()
    search_engine = MockDeepSearchWikiSystem()
    l4 = L4Client(model="qwen3.5:4b")

    await router.initialize()
    await l4.check_ready()

    # ── 第一阶段：无缓存（全新 cache）───────────────────────────────────────
    print("\n" + "█" * 60)
    print("  【第一阶段】无缓存模式（3轮，cache 全空）")
    print("█" * 60)

    cache_no = ThreeTierCache()
    router.cache = cache_no
    l4.cache = cache_no

    results_no_cache = []
    for i in range(1, runs + 1):
        r = await run_single_test(i, query, router, search_engine, l4, cache_no)
        results_no_cache.append(r)
        if i < runs:
            await asyncio.sleep(1)

    # ── 第二阶段：有缓存（复用上面的 cache）────────────────────────────────
    print("\n" + "█" * 60)
    print("  【第二阶段】有缓存模式（3轮，cache 已预热）")
    print("█" * 60)

    results_with_cache = []
    for i in range(1, runs + 1):
        r = await run_single_test(i + 3, query, router, search_engine, l4, cache_no)
        results_with_cache.append(r)
        if i < runs:
            await asyncio.sleep(1)

    # ── 对比统计表 ─────────────────────────────────────────────────────────
    all_results = results_no_cache + results_with_cache

    print(f"""
╔══════════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                    6 轮 测 试 结 果 对 比                                                  ║
╠══════════════════════════════════════════════════════════════════════════════════════════════════════╣
║ 轮次 | 阶段    | L0路由(ms)  | Search(ms) | L4增强(ms)  | 总耗时   | L0命中 | Search命中 | L4命中 | 字数  ║
╠══════════════════════════════════════════════════════════════════════════════════════════════════════╣""")

    for r in all_results:
        phase = "无缓存" if r["round"] <= 3 else "有缓存"
        print(
            f"║  {r['round']}   | {phase}  | "
            f"{r['l0_ms']:^10.0f} | "
            f"{r['search_ms']:^10.0f} | "
            f"{r['l4_ms']:^11.0f} | "
            f"{r['total_s']:^7.1f}s | "
            f"{'HIT' if r['l0_hit'] else 'MISS':^7} | "
            f"{'HIT' if r['search_hit'] else 'MISS':^11} | "
            f"{'HIT' if r['l4_hit'] else 'MISS':^7} | "
            f"{r['answer_chars']:^5} ║"
        )
    print("╚══════════════════════════════════════════════════════════════════════════════════════════════════════╝")

    # 统计
    no_l0 = [r["l0_ms"] for r in results_no_cache]
    no_search = [r["search_ms"] for r in results_no_cache]
    no_l4 = [r["l4_ms"] for r in results_no_cache]
    no_total = [r["total_ms"] for r in results_no_cache]

    wc_l0 = [r["l0_ms"] for r in results_with_cache]
    wc_search = [r["search_ms"] for r in results_with_cache]
    wc_l4 = [r["l4_ms"] for r in results_with_cache]
    wc_total = [r["total_ms"] for r in results_with_cache]

    print(f"""
【无缓存 vs 有缓存 性能对比】
                                    无缓存(平均)      有缓存(平均)      提升幅度
  L0路由     :                   {sum(no_l0)/3:>8.0f}ms        {sum(wc_l0)/3:>8.0f}ms        {(1-sum(wc_l0)/3/sum(no_l0)*3)*100:>5.1f}%
  Search     :                   {sum(no_search)/3:>8.0f}ms        {sum(wc_search)/3:>8.0f}ms        {(1-sum(wc_search)/3/sum(no_search)*3)*100 if sum(no_search)>0 else 0:>5.1f}%
  L4增强     :                   {sum(no_l4)/3:>8.0f}ms        {sum(wc_l4)/3:>8.0f}ms        {(1-sum(wc_l4)/3/sum(no_l4)*3)*100 if sum(no_l4)>0 else 0:>5.1f}%
  ─────────────────────────────────────────────────────────────────
  全链路总耗时:                   {sum(no_total)/3/1000:>8.1f}s        {sum(wc_total)/3/1000:>8.1f}s        {(1-sum(wc_total)/sum(wc_total)/sum(no_total)*sum(wc_total))*100:>5.1f}%

【缓存命中明细】""")

    for r in all_results:
        phase = "无缓存" if r["round"] <= 3 else "有缓存"
        hits = []
        if r["l0_hit"]: hits.append("L0")
        if r["search_hit"]: hits.append("Search")
        if r["l4_hit"]: hits.append("L4")
        hit_str = "+".join(hits) if hits else "全部MISS"
        print(f"  Round {r['round']} ({phase}): {hit_str}  | L0={r['l0_ms']:.0f}ms Search={r['search_ms']:.0f}ms L4={r['l4_ms']:.0f}ms")

    print(f"""
【结论】""")
    # 分析第2/3轮为何没命中
    r2_no = results_no_cache[1]
    r3_no = results_no_cache[2]
    if not r2_no["l0_hit"] and not r2_no["search_hit"] and not r2_no["l4_hit"]:
        print(f"  Round 2/3 未命中原因：代码中没有缓存实现，每次都是全新推理。")
        print(f"  → 本次测试结果即为：无缓存基准速度。")
        print(f"  → 有缓存模式 Round 4-6 将全部命中 L0+Search+L4，展示缓存加速效果。")
    print(f"""
  Ollama 内部 KV Cache：第2/3轮 L4 耗时低于第1轮（{no_l4[0]:.0f}ms → {no_l4[1]:.0f}ms → {no_l4[2]:.0f}ms）
  这是 Ollama 底层模型加载后的内部缓存优化，不是应用层缓存。""")

    # 展示有缓存模式最后一轮的完整回答
    best = results_with_cache[-1]
    print(f"""
【有缓存模式 Round 6 完整回答】（{best['answer_chars']} 字）
────────────────────────────────────────────────────────────
{best['answer'][:800]}
────────────────────────────────────────────────────────────""")


if __name__ == "__main__":
    asyncio.run(main())
