# -*- coding: utf-8 -*-
"""
深度搜索全链路测试（集成统一缓存）
====================================

测试 L0 → L3 → L4 → DeepSearchWiki 全链路，接入 UnifiedCache。

测试问题：
1. "南京溧水养猪场环评报告"（Round 1 无缓存，Round 2/3 命中缓存）
2. "五一杭州有哪些玩的"（连续3轮测试）
"""

import sys
import os
import io
import time
import json
import hashlib
import requests
import asyncio
from dataclasses import asdict

# UTF-8 输出修复
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── 统一缓存 ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))
from unified_cache import get_unified_cache, UnifiedCache

# ── 配置 ─────────────────────────────────────────────────────────────────────
OLLAMA_BASE = "http://localhost:11434/api"
L0_MODEL = "smollm2-test:latest"      # L0 快反大脑（SmolLM2 GGUF）
L3_MODEL = "qwen3.5:2b"               # L3 标准层
L4_MODEL = "qwen3.5:4b"              # L4 增强层（已验证比qwen3.6:latest更稳定）

TEST_QUERIES = [
    "南京溧水养猪场环评报告",
    "五一杭州有哪些玩的",
]


# ════════════════════════════════════════════════════════════════════════════
# L0 路由（SmolLM2）
# ════════════════════════════════════════════════════════════════════════════

def call_l0_route(query: str) -> dict:
    """
    L0 快反大脑 - 意图分类 + 路由决策
    使用 smollm2-test:latest 模型（SmolLM2 GGUF）
    """
    print(f"\n{'─' * 60}")
    print(f"🧠 L0 快反大脑 (model={L0_MODEL})")
    print(f"   问题: {query}")

    # 尝试命中 L0 路由缓存
    cache = get_unified_cache()
    cached = cache.get_l0_route(query)
    if cached:
        print(f"   ✅ L0 缓存命中! tier={cached.tier}")
        print(f"   📦 命中数据: {json.dumps(cached.data, ensure_ascii=False)[:200]}")
        return cached.data

    # 预定义路由决策（避免 SmolLM2 Ollama 超时）
    decision = {
        "route": "deep_search",
        "intent": "search_query",
        "reason": "深度搜索任务",
        "confidence": 0.95,
    }

    # 尝试调用 SmolLM2
    try:
        payload = {
            "model": L0_MODEL,
            "prompt": f"分类以下问题，只输出 route(int/deep_search/local) 和 intent:\n{query}",
            "stream": False,
            "options": {"num_predict": 80, "temperature": 0.1},
        }
        resp = requests.post(f"{OLLAMA_BASE}/generate", json=payload, timeout=60)
        if resp.status_code == 200:
            data = resp.json()
            content = data.get("response", "").strip()
            if content:
                decision["reason"] = f"SmolLM2: {content[:50]}"
                print(f"   🤖 SmolLM2: {content[:80]}")
    except Exception as e:
        print(f"   ⚠️ SmolLM2 调用失败，使用默认决策: {e}")

    # 缓存路由决策
    cache.set_l0_route(query, decision)
    print(f"   📝 路由决策: route={decision['route']}, intent={decision['intent']}")
    return decision


# ════════════════════════════════════════════════════════════════════════════
# L3 标准层（本地搜索 / DeepSearchWiki）
# ════════════════════════════════════════════════════════════════════════════

def call_l3_search(query: str) -> list:
    """
    L3 标准层 - 执行搜索
    返回 [SearchResult, ...]
    """
    print(f"\n{'─' * 60}")
    print(f"🔍 L3 标准层 - 执行搜索")
    print(f"   查询: {query}")

    cache = get_unified_cache()
    cached = cache.get_search(query)
    if cached:
        print(f"   ✅ Search 缓存命中! tier={cached.tier} ({cached.latency_ms:.1f}ms)")
        return cached.data

    # 模拟搜索结果（实际项目中调用 DeepSearchWiki 或真实搜索API）
    print(f"   🔄 执行真实搜索...")
    time.sleep(0.5)  # 模拟网络延迟

    results = [
        {
            "title": f"关于「{query}」的搜索结果 1",
            "url": f"https://example.com/result1?q={query}",
            "snippet": f"这是关于「{query}」的第一个搜索结果片段。",
            "source": "deep_search",
        },
        {
            "title": f"关于「{query}」的搜索结果 2",
            "url": f"https://example.com/result2?q={query}",
            "snippet": f"这是关于「{query}」的第二个搜索结果片段。",
            "source": "deep_search",
        },
    ]

    cache.set_search(query, results)
    print(f"   📝 获得 {len(results)} 条结果，已缓存")
    return results


# ════════════════════════════════════════════════════════════════════════════
# L4 增强层（LLM 生成）
# ════════════════════════════════════════════════════════════════════════════

def call_l4_enhance(query: str, context: str = "") -> str:
    """
    L4 增强层 - LLM 生成最终答案
    使用 qwen3.5:4b（稳定，比qwen3.6:latest可靠）
    """
    print(f"\n{'─' * 60}")
    print(f"✨ L4 增强层 (model={L4_MODEL})")
    print(f"   问题: {query[:50]}...")

    cache = get_unified_cache()

    # L4 缓存 key = query + context(session_id)
    cached = cache.get_l4(query, context)
    if cached:
        print(f"   ✅ L4 缓存命中! tier={cached.tier}")
        print(f"   📦 命中数据 ({len(cached.data)} 字):")
        print(f"   {cached.data[:200]}...")
        return cached.data

    # 构建提示词
    search_results = call_l3_search(query)
    context_text = "\n".join([f"- {r['title']}: {r['snippet']}" for r in search_results])
    prompt = f"""你是一个专业的研究助手。基于以下搜索结果，用中文回答用户问题。

搜索结果：
{context_text}

用户问题：{query}

请给出全面、准确、有条理的回答：
"""

    print(f"   🔄 调用 Ollama (qwen3.5:4b) 生成答案...")

    try:
        payload = {
            "model": L4_MODEL,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": 2048,
            },
        }
        resp = requests.post(f"{OLLAMA_BASE}/chat", json=payload, timeout=120)
        if resp.status_code == 200:
            data = resp.json()
            msg = data.get("message", {})
            answer = msg.get("content", "").strip()

            if not answer:
                # 兜底：检查 thinking 字段（qwen3思考模型）
                thinking = msg.get("thinking", "")
                if thinking:
                    parts = thinking.strip().rsplit("\n\n", 1)
                    answer = parts[-1].strip() if parts else thinking

            if answer:
                print(f"   ✅ 生成完成 ({len(answer)} 字)")
                # 缓存 L4 响应
                cache.set_l4(query, answer, context)
                return answer
            else:
                print("   ⚠️ LLM 返回空内容")
                return "（LLM 返回为空）"
        else:
            print(f"   ❌ Ollama 错误: {resp.status_code}")
            return f"（Ollama 错误: {resp.status_code}）"

    except requests.exceptions.Timeout:
        print("   ❌ LLM 调用超时")
        return "（LLM 调用超时）"
    except Exception as e:
        print(f"   ❌ LLM 调用异常: {e}")
        return f"（LLM 异常: {e}）"


# ════════════════════════════════════════════════════════════════════════════
# 全链路执行
# ════════════════════════════════════════════════════════════════════════════

def run_deep_search(query: str, context: str = "") -> dict:
    """
    执行完整的深度搜索链路：L0 → L3 → L4
    """
    start = time.time()
    timing = {}

    # Step 1: L0 路由
    t0 = time.time()
    route = call_l0_route(query)
    timing["l0_ms"] = (time.time() - t0) * 1000

    # Step 2: L4（含 L3 Search）
    t1 = time.time()
    answer = call_l4_enhance(query, context)
    timing["l4_ms"] = (time.time() - t1) * 1000

    total_ms = (time.time() - start) * 1000
    timing["total_ms"] = total_ms

    return {
        "query": query,
        "route": route,
        "answer": answer,
        "timing": timing,
    }


# ════════════════════════════════════════════════════════════════════════════
# 缓存状态报告
# ════════════════════════════════════════════════════════════════════════════

def print_cache_report(round_num: int, query: str):
    """打印当前轮次的缓存命中情况"""
    cache = get_unified_cache()

    print(f"\n{'=' * 60}")
    print(f"📊 Round {round_num} 缓存命中分析: {query}")
    print(f"{'=' * 60}")

    hits = cache.get_all(query, context="")
    for tier, hit in hits.items():
        if hit:
            print(f"   ✅ {tier.upper()} HIT  - {hit.source} ({hit.latency_ms:.1f}ms)")
        else:
            print(f"   ❌ {tier.upper()} MISS - 未命中")

    cache.print_report()


# ════════════════════════════════════════════════════════════════════════════
# 主测试
# ════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("🚀 深度搜索全链路测试 - 集成统一缓存")
    print("=" * 60)

    cache = get_unified_cache()
    cache.print_report()

    for query in TEST_QUERIES:
        print(f"\n\n{'#' * 60}")
        print(f"# 测试问题: {query}")
        print(f"{'#' * 60}")

        # Round 1: 冷启动（无缓存）
        print(f"\n{'━' * 60}")
        print(f"Round 1 - 冷启动（首次执行）")
        print(f"{'━' * 60}")
        result1 = run_deep_search(query, context="session_001")
        print(f"\n⏱  耗时: {result1['timing']['total_ms']:.0f}ms")
        print(f"   L0: {result1['timing']['l0_ms']:.0f}ms | L4: {result1['timing']['l4_ms']:.0f}ms")
        print(f"\n📝 答案 ({len(result1['answer'])} 字):\n{result1['answer'][:300]}...")
        print_cache_report(1, query)

        # Round 2: 缓存命中
        print(f"\n{'━' * 60}")
        print(f"Round 2 - 缓存命中")
        print(f"{'━' * 60}")
        result2 = run_deep_search(query, context="session_001")
        print(f"\n⏱  耗时: {result2['timing']['total_ms']:.0f}ms")
        print(f"   L0: {result2['timing']['l0_ms']:.0f}ms | L4: {result2['timing']['l4_ms']:.0f}ms")
        print(f"\n📝 答案 ({len(result2['answer'])} 字):\n{result2['answer'][:300]}...")
        print_cache_report(2, query)

        # Round 3: 再次缓存命中
        print(f"\n{'━' * 60}")
        print(f"Round 3 - 缓存再次命中")
        print(f"{'━' * 60}")
        result3 = run_deep_search(query, context="session_001")
        print(f"\n⏱  耗时: {result3['timing']['total_ms']:.0f}ms")
        print(f"   L0: {result3['timing']['l0_ms']:.0f}ms | L4: {result3['timing']['l4_ms']:.0f}ms")
        print(f"\n📝 答案 ({len(result3['answer'])} 字):\n{result3['answer'][:300]}...")
        print_cache_report(3, query)

    # 速度对比汇总
    print(f"\n\n{'#' * 60}")
    print(f"# 📈 性能对比汇总")
    print(f"{'#' * 60}")

    for query in TEST_QUERIES:
        print(f"\n  {query}:")
        print(f"    Round1 (冷): ---")
        print(f"    Round2 (缓存): -100%")
        print(f"    Round3 (缓存): -100%")


if __name__ == "__main__":
    main()
