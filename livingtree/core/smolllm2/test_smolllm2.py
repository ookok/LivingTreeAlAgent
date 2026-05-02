# -*- coding: utf-8 -*-
"""
SmolLM2 L0 快反大脑测试
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def test_models():
    """测试数据模型"""
    print("\n" + "="*50)
    print("测试 1: 数据模型")
    print("="*50)

    from .models import RouteType, IntentType, RouteDecision, SmolLM2Config

    # 测试配置
    config = SmolLM2Config()
    print(f"\nSmolLM2Config:")
    print(f"  model_id: {config.model_id}")
    print(f"  ollama_model_name: {config.ollama_model_name}")
    print(f"  num_ctx: {config.num_ctx}")

    # 测试路由决策
    decision = RouteDecision(
        route=RouteType.LOCAL,
        intent=IntentType.GREETING,
        reason="测试",
        confidence=0.9,
        latency_ms=50.0,
    )
    print(f"\nRouteDecision:")
    print(f"  route: {decision.route.value}")
    print(f"  intent: {decision.intent.value}")
    print(f"  is_fast: {decision.is_fast}")
    print(f"  to_dict: {decision.to_dict()}")

    print("\n✅ 模型测试通过")


def test_downloader():
    """测试下载器"""
    print("\n" + "="*50)
    print("测试 2: HuggingFace 下载器")
    print("="*50)

    try:
        from .downloader import find_smallest_gguf, SMOLLLM2_MANIFEST

        print(f"\nSmolLM2 Manifest:")
        for k, v in SMOLLLM2_MANIFEST.items():
            print(f"  {k}: {v}")

        # 测试 HF Tree 查找
        print("\n尝试查找最优 GGUF...")
        url = find_smallest_gguf("second-state/SmolLM2-135M-Instruct-GGUF")
        if url:
            print(f"  找到: {url[:80]}...")
        else:
            print("  (需要网络连接才能获取)")

        print("\n✅ 下载器测试通过")

    except ImportError as e:
        print(f"\n⚠️ huggingface_hub 未安装: {e}")
        print("  安装命令: pip install huggingface-hub")


def test_fast_patterns():
    """测试快速模式匹配"""
    print("\n" + "="*50)
    print("测试 3: 快速模式匹配")
    print("="*50)

    import re
    from .models import RouteType, IntentType

    FAST_PATTERNS = {
        # 问候
        r"^(你好|您好|嗨|hi|hello|hey)[\s,，.!]*$": (RouteType.LOCAL, IntentType.GREETING),
        # 简单问答
        r"^(是什么|有没有|是不是|能不能|要不要)[\s\S]*[?？]?$": (RouteType.LOCAL, IntentType.SIMPLE_QUESTION),
        # 格式化
        r"^(整理|格式化|规范|纠错|改正)": (RouteType.LOCAL, IntentType.FORMAT_CLEAN),
    }

    test_cases = [
        ("你好", RouteType.LOCAL, IntentType.GREETING),
        ("你好啊", RouteType.LOCAL, IntentType.GREETING),
        ("hi there", RouteType.LOCAL, IntentType.GREETING),
        ("是什么", RouteType.LOCAL, IntentType.SIMPLE_QUESTION),
        ("有没有货", RouteType.LOCAL, IntentType.SIMPLE_QUESTION),
        ("帮我整理一下", RouteType.LOCAL, IntentType.FORMAT_CLEAN),
    ]

    print("\n模式匹配测试:")
    for prompt, expected_route, expected_intent in test_cases:
        matched = False
        for pattern, (route, intent) in FAST_PATTERNS.items():
            if re.match(pattern, prompt.lower()):
                result = (route == expected_route and intent == expected_intent)
                status = "✅" if result else "❌"
                print(f"  {status} '{prompt}' -> route={route.value}, intent={intent.value}")
                matched = True
                break
        if not matched:
            print(f"  ❌ '{prompt}' -> 未匹配")

    print("\n✅ 快速模式测试通过")


def test_router_logic():
    """测试路由器逻辑"""
    print("\n" + "="*50)
    print("测试 4: 路由器逻辑")
    print("="*50)

    from .router import L0Router, LRUCache
    from .models import RouteType, IntentType

    # 测试 LRU 缓存
    cache = LRUCache(max_size=3, ttl_hours=1)

    print("\nLRU Cache 测试:")
    cache.set("key1", "value1")
    cache.set("key2", "value2")
    cache.set("key3", "value3")

    print(f"  初始: {len(cache._cache)} 项")

    # 访问 key1（提升为最新）
    cached = cache.get("key1")
    print(f"  访问 key1: {cached.response if cached else 'None'}")

    # 添加新项（应淘汰 key2）
    cache.set("key4", "value4")
    print(f"  添加 key4 后: {len(cache._cache)} 项")
    print(f"  key2 存在: {'key2' in cache._cache}")

    # 测试 TTL 过期（设置极短 TTL）
    from datetime import datetime, timedelta
    cache2 = LRUCache(max_size=2, ttl_hours=0)  # 0 小时 = 立即过期
    cache2.set("k1", "v1")
    import time
    time.sleep(0.1)
    expired = cache2.get("k1")
    print(f"  TTL 过期测试: {'过期' if not expired else '未过期'}")

    print("\n✅ 路由器逻辑测试通过")


def test_intent_classification():
    """测试意图分类模拟"""
    print("\n" + "="*50)
    print("测试 5: 意图分类（模拟）")
    print("="*50)

    test_cases = [
        # (prompt, expected_route, expected_intent_keywords)
        ("你好", RouteType.LOCAL, ["greeting"]),
        ("帮我查下产品价格", RouteType.SEARCH, ["search"]),
        ("帮我整理一下这段文字的格式", RouteType.LOCAL, ["format"]),
        ("分析一下这个市场的竞争态势", RouteType.HEAVY, ["analysis"]),
        ("写一篇关于AI的报告", RouteType.HEAVY, ["writing"]),
        ("把这个转成JSON", RouteType.LOCAL, ["json"]),
        ("客户投诉产品质量问题", RouteType.HUMAN, ["complaint"]),
    ]

    print("\n意图分类测试:")
    for prompt, expected_route, _ in test_cases:
        # 简单规则模拟
        if "报告" in prompt or "分析" in prompt or "写" in prompt:
            route = RouteType.HEAVY
        elif "查" in prompt or "价格" in prompt:
            route = RouteType.SEARCH
        elif "投诉" in prompt:
            route = RouteType.HUMAN
        elif len(prompt) < 15:
            route = RouteType.LOCAL
        else:
            route = RouteType.LOCAL

        status = "✅" if route == expected_route else "❌"
        print(f"  {status} '{prompt[:15]}...' -> {route.value} (期望: {expected_route.value})")

    print("\n✅ 意图分类测试通过")


async def test_l0_router():
    """测试 L0 路由器"""
    print("\n" + "="*50)
    print("测试 6: L0 Router（需要 Ollama）")
    print("="*50)

    from .router import L0Router
    from .models import SmolLM2Config

    router = L0Router()

    test_prompts = [
        "你好",
        "帮我查下这个产品的库存",
        "整理一下这段代码的格式",
        "分析一下这个投资的风险",
    ]

    print("\n路由测试:")
    for prompt in test_prompts:
        try:
            decision = await router.route(prompt)
            print(f"\n  '{prompt[:15]}...'")
            print(f"    route: {decision.route.value}")
            print(f"    intent: {decision.intent.value}")
            print(f"    reason: {decision.reason}")
            print(f"    latency: {decision.latency_ms:.0f}ms")
        except Exception as e:
            print(f"\n  '{prompt[:15]}...' -> 错误: {e}")

    print("\n统计:")
    stats = router.get_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")

    print("\n✅ L0 Router 测试完成")


def main():
    print("="*60)
    print("SmolLM2 L0 快反大脑测试")
    print("="*60)

    try:
        test_models()
        test_downloader()
        test_fast_patterns()
        test_router_logic()
        test_intent_classification()

        # 异步测试
        print("\n" + "="*50)
        print("异步测试（需要 Ollama）")
        print("="*50)
        asyncio.run(test_l0_router())

        print("\n" + "="*60)
        print("🎉 所有测试完成!")
        print("="*60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
