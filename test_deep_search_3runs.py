# -*- coding: utf-8 -*-
"""
连续3次深度搜索性能对比测试
============================
测试问题：五一杭州有哪些玩的
测试内容：测量每轮 L0→DeepSearch→L4 全链路耗时与结果质量

配置：
  L0: smollm2-test:latest @ Ollama
  L3: qwen3.5:2b @ Ollama
  L4: qwen3.6:latest @ Ollama
"""

import sys
import os
import asyncio
import time
import json
import logging
import re
import httpx
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

# Windows 控制台 UTF-8 编码修复
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
#  模拟 DeepSearchWikiSystem（跳过外部依赖）
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str
    relevance: float
    trust_score: float

class MockDeepSearchWikiSystem:
    """简化版深度搜索，模拟 5 条结果"""

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        results_map = {
            "杭州": [
                SearchResult(
                    title="2026杭州五一活动全攻略 - 西湖景区官方",
                    url="https://hangzhou.gov.cn/51holiday",
                    snippet="断桥残雪、苏堤春晓等经典景点全面开放，五一期间推出 '遇见西湖' 实景演出，每日3场。",
                    source="hangzhou.gov.cn",
                    relevance=0.92,
                    trust_score=0.85,
                ),
                SearchResult(
                    title="杭州宋城景区五一特惠票 - 携程旅行",
                    url="https://you.ctrip.com/sight/hangzhou14.html",
                    snippet="《宋城千古情》大型歌舞演出，五一假期加演至每日6场，门票提前预约享8折优惠。",
                    source="ctrip.com",
                    relevance=0.88,
                    trust_score=0.78,
                ),
                SearchResult(
                    title="良渚古城遗址公园春季游览指南",
                    url="https://www.liangzhu.org/visit",
                    snippet="世界文化遗产，距今5000年文明遗址，五一期间推出考古体验和遗址打卡活动。",
                    source="liangzhu.org",
                    relevance=0.85,
                    trust_score=0.82,
                ),
                SearchResult(
                    title="杭州灵隐寺·飞来峰景区游览公告",
                    url="https://www.aldlf.com/spring2026",
                    snippet="千年古刹灵隐寺，五一假期人流管控需提前预约，永福寺素斋和韬光寺茶室正常开放。",
                    source="aldlf.com",
                    relevance=0.83,
                    trust_score=0.75,
                ),
                SearchResult(
                    title="杭州动漫节五一 Cosplay 嘉年华 - 哔哩哔哩资讯",
                    url="https://api.bilibili.com/news/hangzhou-acg",
                    snippet="白马湖动漫展馆举办大型动漫嘉年华，知名声优签售、国产动画首映、cosplay 大赛。",
                    source="bilibili.com",
                    relevance=0.80,
                    trust_score=0.72,
                ),
            ],
            "五一": [
                SearchResult(
                    title="2026全国五一假期出行预测报告 - 交通运输部",
                    url="https://www.mot.gov.cn/51forecast",
                    snippet="预计五一全国发送旅客 8.2 亿人次，杭州位列热门目的地 TOP3，客流高峰4月30日下午。",
                    source="mot.gov.cn",
                    relevance=0.87,
                    trust_score=0.90,
                ),
                SearchResult(
                    title="杭州五一天气与限行通知 - 杭州市气象局",
                    url="https://weather.hangzhou.gov.cn",
                    snippet="五一假期杭州以晴到多云为主，气温 18-28°C，西湖景区周边实施单双号限行。",
                    source="weather.hangzhou.gov.cn",
                    relevance=0.82,
                    trust_score=0.88,
                ),
            ],
        }

        combined = []
        for kw in ["杭州", "五一"]:
            combined.extend(results_map.get(kw, []))
        return combined[:max_results]

    def format_for_llm(self, results: List[SearchResult]) -> str:
        lines = []
        for r in results:
            lines.append(f"## {r.title}")
            lines.append(f"来源：{r.source} | 相关度：{r.relevance:.0%} | 可信度：{r.trust_score:.0%}")
            lines.append(f"摘要：{r.snippet}")
            lines.append(f"链接：{r.url}")
            lines.append("")
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
#  L0 SmolLM2 路由分类（通过 Ollama）
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class L0Router:
    model_name: str = "smollm2-test:latest"
    ollama_host: str = "http://localhost:11434"
    _ready: bool = field(default=False, init=False)

    async def initialize(self):
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                r = await c.get(f"{self.ollama_host}/api/tags")
                models = [m["name"] for m in r.json().get("models", [])]
                if self.model_name in models or any("smollm" in m.lower() for m in models):
                    self._ready = True
                    logger.info(f"L0 SmolLM2 就绪（Ollama）: {models}")
                    return
        except Exception as e:
            logger.warning(f"L0 Ollama 检测失败: {e}")
        self._ready = False
        logger.info("L0 路由就绪（规则兜底）")

    async def classify(self, query: str) -> Dict[str, Any]:
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
            "route": "search",
            "intent": "search_query",
            "reason": "规则兜底",
            "confidence": 0.7,
            "model": "rule",
            "via": "rule_fallback",
        }


# ─────────────────────────────────────────────────────────────────────────────
#  L4 模型（兼容 Qwen3 思考模型）
# ─────────────────────────────────────────────────────────────────────────────

class L4Client:
    def __init__(self, model: str = "qwen3.6:latest", host: str = "http://localhost:11434"):
        self.model = model
        self.host = host
        self._ready = False

    async def check_ready(self):
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                r = await c.get(f"{self.host}/api/tags")
                models = [m["name"] for m in r.json().get("models", [])]
                if self.model in models:
                    self._ready = True
                    logger.info(f"L4 {self.model} 就绪")
                    return
                logger.warning(f"L4 模型 {self.model} 未找到，Ollama models: {models}")
        except Exception as e:
            logger.warning(f"L4 Ollama 检测失败: {e}")
        self._ready = False

    async def generate_stream(self, query: str, search_context: str, max_tokens: int = 800) -> tuple[str, float]:
        """流式调用，返回 (answer, elapsed_ms)"""
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
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream(
                    "POST",
                    f"{self.host}/api/chat",
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
            logger.warning(f"L4 流式调用失败: {e}")
            return "", 0

        elapsed_ms = (time.perf_counter() - start) * 1000
        return "".join(collected), elapsed_ms

    async def generate(self, query: str, search_context: str, max_tokens: int = 800) -> tuple[str, float]:
        """非流式调用"""
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
        start = time.perf_counter()
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
                            logger.info(f"L4 从 thinking 字段提取 {len(content)} 字")
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    return content, elapsed_ms
        except Exception as e:
            logger.warning(f"L4 非流式调用失败: {e}")
        return "", 0


# ─────────────────────────────────────────────────────────────────────────────
#  单轮测试
# ─────────────────────────────────────────────────────────────────────────────

async def run_single_test(
    round_num: int,
    query: str,
    router: L0Router,
    search_engine: MockDeepSearchWikiSystem,
    l4: L4Client,
) -> Dict[str, Any]:
    """执行单轮深度搜索，返回性能数据"""
    print(f"\n{'='*60}")
    print(f"  第 {round_num} 轮测试  |  问题：「{query}」")
    print(f"{'='*60}")

    # Phase 1: L0 路由
    t0 = time.perf_counter()
    route = await router.classify(query)
    t_l0 = (time.perf_counter() - t0) * 1000

    print(f"[L0 路由] 耗时 {t_l0:.0f}ms | "
          f"route={route['route']} intent={route['intent']} "
          f"confidence={route['confidence']:.2f} via={route['via']}")

    # Phase 2: 深度搜索
    t0 = time.perf_counter()
    results = await search_engine.search(query, max_results=5)
    t_search = (time.perf_counter() - t0) * 1000
    search_context = search_engine.format_for_llm(results)
    avg_relevance = sum(r.relevance for r in results) / len(results) if results else 0
    avg_trust = sum(r.trust_score for r in results) / len(results) if results else 0

    print(f"[DeepSearch] 耗时 {t_search:.0f}ms | "
          f"找到 {len(results)} 条 | 平均相关度={avg_relevance:.0%} 可信度={avg_trust:.0%}")

    # Phase 3: L4 增强生成
    t0 = time.perf_counter()

    # 先尝试流式
    answer, t_l4 = await l4.generate_stream(query, search_context)

    # 流式无内容则回退非流式
    if not answer:
        print(f"[L4 降级] 流式无内容，切换非流式...")
        answer, t_l4 = await l4.generate(query, search_context)

    t_l4 = (time.perf_counter() - t0) * 1000

    if answer:
        print(f"[L4 增强] 耗时 {t_l4:.0f}ms | 生成 {len(answer)} 字")
        # 截取前200字预览
        preview = answer[:200].replace("\n", " ")
        print(f"  预览: {preview}...")
    else:
        print(f"[L4 增强] 失败，耗时 {t_l4:.0f}ms")

    total_ms = t_l0 + t_search + t_l4
    print(f"[总计] {total_ms:.0f}ms ({total_ms/1000:.1f}s)")

    return {
        "round": round_num,
        "query": query,
        "l0_ms": round(t_l0, 1),
        "search_ms": round(t_search, 1),
        "l4_ms": round(t_l4, 1),
        "total_ms": round(total_ms, 1),
        "total_s": round(total_ms / 1000, 1),
        "route": route["route"],
        "intent": route["intent"],
        "confidence": route["confidence"],
        "results_count": len(results),
        "avg_relevance": round(avg_relevance, 3),
        "avg_trust": round(avg_trust, 3),
        "answer_chars": len(answer),
        "answer": answer,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  主程序
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    query = "五一杭州有哪些玩的"
    runs = 3

    print(f"""
╔══════════════════════════════════════════════════════════╗
║     连续3次深度搜索性能对比测试（qwen3.5:4b 非思考模型）                   ║
║     问题：「五一杭州有哪些玩的」                               ║
╚══════════════════════════════════════════════════════════╝
""")

    # 初始化组件
    router = L0Router()
    search_engine = MockDeepSearchWikiSystem()
    l4 = L4Client(model="qwen3.5:4b")  # qwen3.6:latest 是思考模型不稳定，换 qwen3.5:4b（非思考）

    print("[初始化] L0 SmolLM2 路由...")
    await router.initialize()

    print("[初始化] L4 qwen3.6:latest...")
    await l4.check_ready()

    # 连续执行 3 轮
    results = []
    for i in range(1, runs + 1):
        result = await run_single_test(i, query, router, search_engine, l4)
        results.append(result)

        # 每轮之间稍作暂停
        if i < runs:
            print(f"\n[冷却] 等待 2 秒后执行下一轮...")
            await asyncio.sleep(2)

    # ── 对比统计表 ──────────────────────────────────────────────────────────
    print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                          3 轮 测 试 结 果 对 比                                  ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")

    header = f"{'轮次':^4} | {'L0路由':^7} | {'DeepSearch':^9} | {'L4增强':^7} | {'总耗时':^7} | {'结果数':^5} | {'生成字数':^7} | {'route':^8} | {'intent':^12}"
    sep = "-" * len(header)
    print(header)
    print(sep)

    for r in results:
        print(
            f"{r['round']:^4} | "
            f"{r['l0_ms']:^7.0f}ms | "
            f"{r['search_ms']:^9.0f}ms | "
            f"{r['l4_ms']:^7.0f}ms | "
            f"{r['total_s']:^7.1f}s | "
            f"{r['results_count']:^5} | "
            f"{r['answer_chars']:^7} | "
            f"{r['route']:^8} | "
            f"{r['intent']:^12}"
        )
    print(sep)

    # 统计摘要
    total_times = [r["total_ms"] for r in results]
    l4_times = [r["l4_ms"] for r in results]
    l0_times = [r["l0_ms"] for r in results]
    search_times = [r["search_ms"] for r in results]

    print(f"""
【性能统计】
  L0 路由     : 平均 {sum(l0_times)/len(l0_times):.0f}ms  | 最小 {min(l0_times):.0f}ms  | 最大 {max(l0_times):.0f}ms
  DeepSearch  : 平均 {sum(search_times)/len(search_times):.0f}ms  | 最小 {min(search_times):.0f}ms  | 最大 {max(search_times):.0f}ms
  L4 增强     : 平均 {sum(l4_times)/len(l4_times):.0f}ms  | 最小 {min(l4_times):.0f}ms  | 最大 {max(l4_times):.0f}ms
  全链路总耗时 : 平均 {sum(total_times)/len(total_times)/1000:.1f}s  | 最小 {min(total_times)/1000:.1f}s  | 最大 {max(total_times)/1000:.1f}s
  L4 耗时占比 : {sum(l4_times)/sum(total_times)*100:.0f}%  (主要耗时在 L4 推理)
  L0+Search   : {sum(l0_times+search_times)/sum(total_times)*100:.0f}%
""")

    # 展示第 3 轮完整回答（L4 回答最完整的一次）
    best = results[-1]
    print(f"""
【第 {best['round']} 轮 L4 完整回答】（{best['answer_chars']} 字）
{'─'*60}
{best['answer']}
{'─'*60}
""")


if __name__ == "__main__":
    asyncio.run(main())
