"""
L4 执行器测试
测试四级缓存金字塔与 RelayFreeLLM 网关集成
"""

import asyncio
import sys
import os

# 添加项目根目录到 path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def log(msg, ok=True):
    """打印日志"""
    prefix = "[OK]" if ok else "[FAIL]"
    print(f"{prefix} {msg}")


async def test_l4_executor():
    """测试 L4 执行器"""
    print("=" * 60)
    print("L4 Executor Test")
    print("=" * 60)

    # 1. 测试导入
    print("\n[1] Module Import...")
    try:
        from client.src.business.fusion_rag import (
            L4RelayExecutor,
            get_l4_executor,
            execute_via_l4,
            WriteBackCache,
            L4AwareRouter
        )
        log("Module import successful")
    except ImportError as e:
        log(f"Module import failed: {e}", ok=False)
        return False

    # 2. 测试 L4RelayExecutor 单例
    print("\n[2] Singleton Test...")
    try:
        executor1 = get_l4_executor()
        executor2 = get_l4_executor()
        assert executor1 is executor2, "Singleton failed"
        log("Singleton mode OK")
        print(f"  - Gateway: {executor1.gateway_url}")
        print(f"  - Direct Available: {executor1._direct_available}")
    except Exception as e:
        log(f"Singleton test failed: {e}", ok=False)

    # 3. 测试健康检查
    print("\n[3] Health Check...")
    try:
        health = await executor1.health_check()
        log("Health check completed")
        print(f"  - Relay Gateway: {health['relay_gateway']}")
        print(f"  - Direct Ollama: {health['direct_ollama']}")
    except Exception as e:
        log(f"Health check failed: {e}", ok=False)

    # 4. 测试统计
    print("\n[4] Stats Test...")
    try:
        stats = executor1.get_stats()
        log("Stats retrieved")
        print(f"  - Total: {stats['total_requests']}")
        print(f"  - Relay: {stats['relay_requests']}")
        print(f"  - Direct: {stats['direct_requests']}")
    except Exception as e:
        log(f"Stats failed: {e}", ok=False)

    # 5. 测试 WriteBackCache
    print("\n[5] WriteBackCache Test...")
    try:
        cache = WriteBackCache()
        log("WriteBackCache created")
        cache.start()
        await cache.write_back(
            [{"role": "user", "content": "test"}],
            {"choices": [{"message": {"content": "test response"}}]}
        )
        await asyncio.sleep(0.5)
        await cache.stop()
        log("WriteBackCache test completed")
    except Exception as e:
        log(f"WriteBackCache test failed: {e}", ok=False)

    # 6. 测试 L4AwareRouter
    print("\n[6] L4AwareRouter Test...")
    try:
        router = L4AwareRouter(l4_executor=executor1)
        log("L4AwareRouter created")

        # 测试 LLM 执行决策
        decision = router.decide_llm_execution(
            query="test",
            fused_results=[{"fused_score": 0.6}],
            strategy="balanced"
        )
        print(f"  - Decision (low conf): {decision.value}")

        decision2 = router.decide_llm_execution(
            query="test",
            fused_results=[{"fused_score": 0.9}],
            strategy="balanced"
        )
        print(f"  - Decision (high conf): {decision2.value}")

    except Exception as e:
        log(f"L4AwareRouter test failed: {e}", ok=False)

    print("\n" + "=" * 60)
    print("Test Completed")
    print("=" * 60)

    return True


async def test_fusion_engine_integration():
    """测试 FusionEngine L4 集成"""
    print("\n" + "=" * 60)
    print("FusionEngine L4 Integration Test")
    print("=" * 60)

    try:
        from client.src.business.fusion_rag import FusionEngine, get_l4_executor

        executor = get_l4_executor()
        engine = FusionEngine(top_k=5, l4_executor=executor)

        log("FusionEngine created")
        print(f"  - L4 Enabled: {engine.l4_executor is not None}")

        # 测试带 L4 兜底的查询
        messages = [{"role": "user", "content": "hello"}]
        layer_results = {}

        print("\nTesting query_with_l4_fallback...")
        result = await engine.query_with_l4_fallback(
            messages=messages,
            layer_results=layer_results,
            strategy="balanced"
        )

        log("Query completed")
        print(f"  - Source: {result['source']}")

    except Exception as e:
        log(f"FusionEngine integration test failed: {e}", ok=False)

    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(test_l4_executor())
    asyncio.run(test_fusion_engine_integration())
