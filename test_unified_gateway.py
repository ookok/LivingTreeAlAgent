"""
测试统一模型网关
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def test_l0_boot():
    """测试 L0 启动"""
    print("\n" + "="*55)
    print("  L0 Boot Test")
    print("="*55)
    
    from core.tier_model.tier0_init import SystemHealthChecker, BootSequence
    
    # 快速健康检查
    boot = BootSequence()
    result = await boot.quick_health_check()
    
    print("\n  Quick Health Check:")
    for key, value in result.items():
        status = "[OK]" if value else "[--]"
        print(f"    {status} {key}: {value}")
    
    # 完整启动报告
    report = await boot.boot()
    
    print(f"\n  Boot Report:")
    print(f"    Status:    {report.status.value}")
    print(f"    Duration:  {report.duration_ms:.0f}ms")
    
    if report.ollama:
        print(f"    Ollama:    {report.ollama.status.value} ({report.ollama.latency_ms:.0f}ms)")
    
    if report.gpu:
        print(f"    GPU:       {report.gpu.status.value}")
        if report.gpu.metadata.get("memory_total_gb"):
            print(f"               {report.gpu.metadata.get('memory_total_gb', 0):.0f}GB total")
    
    if report.memory:
        print(f"    Memory:    {report.memory.status.value}")
        print(f"               {report.memory.metadata.get('available_gb', 0):.1f}GB / {report.memory.metadata.get('total_gb', 0):.1f}GB")
    
    print(f"\n  Local Models: {', '.join(report.local_models) or 'None'}")
    print(f"  Recommended:  {report.recommended_tier} / {report.recommended_model}")


async def test_hardware_profile():
    """测试硬件感知"""
    print("\n" + "="*55)
    print("  Hardware Profile Test")
    print("="*55)
    
    from core.tier_model.unified_model_gateway import HardwareAwareRouter
    
    router = HardwareAwareRouter()
    profile = await router.get_profile()
    
    print(f"\n  CPU:    {profile.cpu_cores} cores, {profile.cpu_available*100:.0f}% available")
    print(f"  Memory: {profile.memory_available_gb:.1f}GB / {profile.memory_total_gb:.1f}GB ({profile.memory_percent*100:.0f}%)")
    print(f"  GPU:    {'Yes' if profile.has_gpu else 'No'} {profile.gpu_name}")
    if profile.has_gpu:
        print(f"          {profile.gpu_memory_available_mb:.0f}MB / {profile.gpu_memory_total_mb:.0f}MB available")
    print(f"  Network: {'Available' if profile.network_available else 'Unavailable'}")


async def test_model_selection():
    """测试模型选择"""
    print("\n" + "="*55)
    print("  Model Selection Test")
    print("="*55)
    
    from core.tier_model.unified_model_gateway import (
        HardwareAwareRouter,
        TierLevel,
        DEFAULT_MODEL_REGISTRY,
    )
    
    router = HardwareAwareRouter()
    
    # 测试不同层级选择
    test_cases = [
        ("No hint (auto)", None),
        ("Force L2", TierLevel.L2),
        ("Force L3", TierLevel.L3),
        ("Force L4", TierLevel.L4),
    ]
    
    print("\n  Model Selection by Tier:")
    for name, tier in test_cases:
        model_name, config, profile = await router.select_model(tier_hint=tier, prefer_local=True)
        print(f"\n    {name}:")
        print(f"      Model:   {model_name}")
        print(f"      Tier:    {config.tier.value}")
        print(f"      Provider: {config.provider.value}")
        print(f"      Memory:  {config.min_memory_gb:.1f}GB")


async def test_unified_gateway():
    """测试统一网关"""
    print("\n" + "="*55)
    print("  Unified Gateway Test")
    print("="*55)
    
    from core.tier_model.unified_model_gateway import UnifiedModelGateway, ChatRequest
    
    gateway = UnifiedModelGateway()
    await gateway.initialize()
    
    # 获取状态
    status = gateway.get_status()
    print(f"\n  Gateway Status:")
    print(f"    Ollama Ready:  {status.ollama_ready}")
    print(f"    Remote Ready:  {status.remote_ready}")
    print(f"    Local Models:  {len(status.local_models)}")
    
    # 获取统计
    stats = gateway.get_stats()
    print(f"\n  Stats:")
    print(f"    Total Requests: {stats['total_requests']}")
    print(f"    Avg Latency:    {stats['avg_latency_ms']:.0f}ms")
    
    # 测试简单查询
    print("\n  Testing simple queries:")
    
    test_queries = [
        "你好",
        "1+1等于几？",
        "什么是Python？",
    ]
    
    for query in test_queries:
        request = ChatRequest(query=query)
        response = await gateway.chat(request)
        print(f"\n    Q: {query}")
        print(f"    A: {response.content[:50]}...")
        print(f"    Tier: {response.tier.value}, Model: {response.model}")


async def main():
    print("""
    +========================================================+
    |     LivingTreeAI L0-L4 集成测试                       |
    +========================================================+
    """)
    
    await test_l0_boot()
    await test_hardware_profile()
    await test_model_selection()
    
    # 网关测试（可能需要 Ollama）
    try:
        await test_unified_gateway()
    except Exception as e:
        print(f"\n  Gateway test skipped: {e}")
    
    print("\n" + "="*55)
    print("  All tests completed!")
    print("="*55)


if __name__ == "__main__":
    asyncio.run(main())
