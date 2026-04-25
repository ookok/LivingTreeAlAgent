"""
测试智能模型路由器
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.visual_evolution_engine.smart_router import (
    SmartModelRouter,
    route_model,
    HardwareProfiler,
    DEFAULT_MODEL_REGISTRY,
    ModelProvider,
    RoutingDecision,
)


def print_decision(decision: RoutingDecision, title: str = "路由决策"):
    """打印路由决策"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)
    print(f"  选择模型: {decision.selected_model}")
    print(f"  提供者:   {decision.selected_provider.value}")
    print(f"  原因:     {decision.reason}")
    print(f"  置信度:   {decision.confidence:.0%}")
    print(f"  满足要求: {'是' if decision.meets_requirements else '否'}")
    
    if decision.hardware_profile:
        hp = decision.hardware_profile
        print(f"\n  硬件配置:")
        print(f"    CPU:   {hp.cpu_cores} 核, 评分: {hp.cpu_score:.1f}")
        print(f"    内存:   {hp.available_memory_gb:.1f}GB / {hp.total_memory_gb:.1f}GB")
        print(f"    GPU:   {'有' if hp.has_gpu else '无'} {hp.gpu_name or ''}")
        if hp.has_gpu:
            print(f"    GPU内存: {hp.available_gpu_memory_mb:.0f}MB / {hp.total_gpu_memory_mb:.0f}MB")
    
    if decision.alternatives:
        print(f"\n  备选方案:")
        for i, (provider, model) in enumerate(decision.alternatives, 1):
            print(f"    {i}. {provider.value}: {model}")


def test_hardware_profile():
    """测试硬件评估"""
    print("\n" + "="*60)
    print("  硬件能力评估")
    print("="*60)
    
    profile = HardwareProfiler.get_current_profile()
    
    print(f"\n  CPU:   {profile.cpu_cores} 核")
    print(f"  内存:   {profile.total_memory_gb:.1f}GB 总计, {profile.available_memory_gb:.1f}GB 可用")
    print(f"  GPU:   {'有' if profile.has_gpu else '无'}")
    if profile.has_gpu:
        print(f"         {profile.gpu_name}")
        print(f"         {profile.total_gpu_memory_mb:.0f}MB 总计, {profile.available_gpu_memory_mb:.0f}MB 可用")
    print(f"  网络:   {'可用' if profile.network_available else '不可用'}")
    
    return profile


def test_default_models():
    """测试默认模型注册表"""
    print("\n" + "="*60)
    print("  模型注册表")
    print("="*60)
    
    local = DEFAULT_MODEL_REGISTRY.list_local_models()
    remote = DEFAULT_MODEL_REGISTRY.list_remote_models()
    
    print(f"\n  本地模型 ({len(local)} 个):")
    for m in sorted(local, key=lambda x: x.priority):
        print(f"    - {m.name}: 内存 {m.min_memory_gb:.0f}GB, GPU {m.min_gpu_memory_mb:.0f}MB, 优先级 {m.priority}")
    
    print(f"\n  远程模型 ({len(remote)} 个):")
    for m in sorted(remote, key=lambda x: x.priority, reverse=True):
        print(f"    - {m.name} ({m.provider.value}): ${m.cost_per_million:.2f}/M tokens")


def test_routing_decisions():
    """测试各种路由场景"""
    print("\n" + "="*60)
    print("  路由决策测试")
    print("="*60)
    
    router = SmartModelRouter()
    profile = HardwareProfiler.get_current_profile()
    
    # 场景1: 强制指定大模型
    decision1 = router.route(preferred_model="qwen2.5:14b")
    print_decision(decision1, "场景1: 指定 qwen2.5:14b")
    
    # 场景2: 指定小模型
    decision2 = router.route(preferred_model="qwen2.5:0.5b")
    print_decision(decision2, "场景2: 指定 qwen2.5:0.5b")
    
    # 场景3: 按任务类型
    for task in ["fast", "chat", "coding", "reasoning"]:
        decision = router.route(task_type=task)
        print_decision(decision, f"场景3-{task}: 任务类型 = {task}")
    
    # 场景4: 默认路由
    decision4 = router.route()
    print_decision(decision4, "场景4: 默认路由")


def test_model_compatibility():
    """测试模型兼容性检查"""
    print("\n" + "="*60)
    print("  模型兼容性检查")
    print("="*60)
    
    profile = HardwareProfiler.get_current_profile()
    
    test_models = [
        "qwen2.5:0.5b",
        "qwen2.5:3b",
        "qwen2.5:7b",
        "qwen2.5:14b",
        "qwen2.5:32b",
    ]
    
    print(f"\n  当前硬件: {profile.cpu_cores}核CPU, {profile.available_memory_gb:.1f}GB内存")
    if profile.has_gpu:
        print(f"               {profile.total_gpu_memory_mb:.0f}MB GPU")
    
    print("\n  兼容性列表:")
    for model_name in test_models:
        req = DEFAULT_MODEL_REGISTRY.get(model_name)
        if req:
            can_run, reason = HardwareProfiler.can_run_model(profile, req)
            status = "[OK]" if can_run else "[XX]"
            print(f"    {status} {model_name}: {reason}")
        else:
            print(f"    [--] {model_name}: 未注册")


def main():
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║           智能模型路由器 - 测试脚本                          ║
    ║                                                            ║
    ║  功能: 根据硬件资源自动选择最优模型(本地/远程)                ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    # 1. 测试硬件评估
    test_hardware_profile()
    
    # 2. 测试模型注册表
    test_default_models()
    
    # 3. 测试兼容性
    test_model_compatibility()
    
    # 4. 测试路由决策
    test_routing_decisions()
    
    print("\n" + "="*60)
    print("  测试完成!")
    print("="*60)


if __name__ == "__main__":
    main()
