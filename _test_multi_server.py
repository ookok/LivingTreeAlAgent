"""
测试多地址配置 + 心跳检测
"""
import sys
import os

# 强制 UTF-8 编码（Windows 终端兼容）
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from client.src.business.encrypted_config import setup_default_configs, load_model_config
from client.src.business.global_model_router import GlobalModelRouter, ModelTier, ModelCapability, RoutingStrategy


def test_multi_server_config():
    """测试 1：多地址配置是否正确加载"""
    print("=" * 60)
    print("测试 1：多地址配置加载")
    print("=" * 60)

    # 设置默认配置（会写入多地址配置）
    setup_default_configs()

    # 加载 Ollama 配置
    ollama_config = load_model_config("ollama")
    if not ollama_config:
        print("[FAIL] 无法加载 Ollama 配置")
        return False

    servers = ollama_config.get("servers", [])
    if not servers:
        print("[FAIL] 配置中没有 servers 字段")
        return False

    print(f"[OK] 加载到 {len(servers)} 个服务器配置：")
    for s in servers:
        url = s.get("url", "")
        priority = s.get("priority", 999)
        models = s.get("models", [])
        print(f"  - {url} (priority={priority}, models={len(models)})")

    return True


def test_global_router_loading():
    """测试 2：GlobalModelRouter 是否正确加载多地址模型"""
    print("\n" + "=" * 60)
    print("测试 2：GlobalModelRouter 多地址模型加载")
    print("=" * 60)

    router = GlobalModelRouter()

    # 统计 Ollama 模型
    ollama_models = {k: v for k, v in router.models.items() if v.backend.value == "ollama"}
    print(f"[OK] 共加载 {len(ollama_models)} 个 Ollama 模型：")

    for model_id, model_info in ollama_models.items():
        url = model_info.config.get("url", "")
        priority = model_info.config.get("priority", 999)
        available = model_info.is_available
        print(f"  - {model_id}: url={url}, priority={priority}, available={available}")

    return True


def test_heartbeat():
    """测试 3：心跳检测是否正常工作"""
    print("\n" + "=" * 60)
    print("测试 3：心跳检测")
    print("=" * 60)

    router = GlobalModelRouter()

    # 手动执行一次心跳检测
    print("[心跳] 执行一次心跳检测...")
    router._do_heartbeat()

    # 查看服务器状态
    status = router.get_server_status()
    print(f"[OK] 服务器状态（{len(status)} 个）：")
    for url, info in status.items():
        available = info["available"]
        priority = info["priority"]
        models = info["models"]
        status_str = "✅ 可用" if available else "❌ 不可用"
        print(f"  - {url}: {status_str}, priority={priority}, models={models}")

    return True


def test_routing_with_availability():
    """测试 4：路由是否优先选择可用模型（本地优先）"""
    print("\n" + "=" * 60)
    print("测试 4：路由选举（本地优先 + 可用模型）")
    print("=" * 60)

    router = GlobalModelRouter()

    # 先执行心跳检测，更新 is_available
    router._do_heartbeat()

    # 测试路由：选择一个能力（如 CHAT）
    capability = ModelCapability.CHAT
    selected = router.route(capability=capability, strategy=RoutingStrategy.BALANCED)

    if not selected:
        print(f"[FAIL] 没有可用模型支持 {capability.value}")
        return False

    print(f"[OK] 路由结果：")
    print(f"  - 模型：{selected.name} ({selected.model_id})")
    print(f"  - 后端：{selected.backend.value}")
    print(f"  - URL：{selected.config.get('url', '')}")
    print(f"  - 可用：{selected.is_available}")

    # 检查是否本地优先
    url = selected.config.get("url", "")
    if "localhost" in url or "127.0.0.1" in url:
        print(f"[OK] 本地优先策略生效：选择了本地模型")
    else:
        print(f"[WARN] 没有选择本地模型，可能本地 Ollama 不可用")

    return True


def test_tier_routing():
    """测试 5：L0-L4 分层路由是否正确"""
    print("\n" + "=" * 60)
    print("测试 5：L0-L4 分层路由")
    print("=" * 60)

    router = GlobalModelRouter()

    # 先执行心跳检测
    router._do_heartbeat()

    for tier in [ModelTier.L0, ModelTier.L1, ModelTier.L2, ModelTier.L3, ModelTier.L4]:
        model = router.get_tier_model(tier)
        if model:
            url = model.config.get("url", "")
            available = model.is_available
            print(f"[OK] {tier.value} → {model.name} ({model.model_id}), url={url}, available={available}")
        else:
            print(f"[WARN] {tier.value} 没有设置模型")

    return True


def main():
    """运行所有测试"""
    print("🧪 多地址配置 + 心跳检测 测试")
    print("=" * 60)

    results = []

    try:
        r1 = test_multi_server_config()
        results.append(("多地址配置加载", r1))
    except Exception as e:
        print(f"[ERROR] 测试 1 异常：{e}")
        results.append(("多地址配置加载", False))

    try:
        r2 = test_global_router_loading()
        results.append(("GlobalModelRouter 加载", r2))
    except Exception as e:
        print(f"[ERROR] 测试 2 异常：{e}")
        results.append(("GlobalModelRouter 加载", False))

    try:
        r3 = test_heartbeat()
        results.append(("心跳检测", r3))
    except Exception as e:
        print(f"[ERROR] 测试 3 异常：{e}")
        results.append(("心跳检测", False))

    try:
        r4 = test_routing_with_availability()
        results.append(("路由选举", r4))
    except Exception as e:
        print(f"[ERROR] 测试 4 异常：{e}")
        results.append(("路由选举", False))

    try:
        r5 = test_tier_routing()
        results.append(("L0-L4 分层路由", r5))
    except Exception as e:
        print(f"[ERROR] 测试 5 异常：{e}")
        results.append(("L0-L4 分层路由", False))

    # 汇总
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {status} - {name}")

    failed = sum(1 for _, r in results if not r)
    if failed == 0:
        print("\n🎉 所有测试通过！")
    else:
        print(f"\n⚠️ 有 {failed} 个测试失败")


if __name__ == "__main__":
    main()
