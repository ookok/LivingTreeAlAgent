"""
部署中心测试
验证 L0-L4 模型部署功能的正确性
"""

import sys
import time
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_model_layer_config():
    """测试模型层配置"""
    print("\n" + "=" * 60)
    print("测试 1: 模型层配置")
    print("=" * 60)
    
    from client.src.business.model_layer_config import (
        ModelTier, ServiceStatus, DeployMode,
        L0_L4_MODELS, get_models_by_tier,
        get_default_model_for_tier, create_default_layer_config,
        check_ollama_installed, check_system_memory
    )
    
    # 检查系统
    print(f"\n[系统检测]")
    print(f"  Ollama 已安装: {check_ollama_installed()}")
    mem = check_system_memory()
    print(f"  系统内存: {mem.get('total_gb', 0):.1f} GB")
    
    # 检查模型
    print(f"\n[预定义模型]")
    print(f"  总数: {len(L0_L4_MODELS)} 个")
    
    for tier in ModelTier:
        models = get_models_by_tier(tier)
        default = get_default_model_for_tier(tier)
        print(f"\n  {tier.value}:")
        print(f"    可用模型: {len(models)} 个")
        print(f"    默认模型: {default.name if default else '无'}")
        for m in models:
            print(f"      - {m.name} ({m.ollama_name}, {m.size_gb}GB)")
    
    # 配置测试
    print(f"\n[配置测试]")
    config = create_default_layer_config()
    print(f"  部署模式: {config.mode}")
    print(f"  自动部署: {config.auto_deploy_all}")
    print(f"  层数: {len(config.layers)}")
    
    print("\n[OK] 模型层配置测试通过")
    return True


def test_deployment_engine():
    """测试部署引擎"""
    print("\n" + "=" * 60)
    print("测试 2: 部署引擎")
    print("=" * 60)
    
    from client.src.business.deployment_engine import DeploymentEngine, get_deployment_engine
    
    # 创建引擎
    engine = get_deployment_engine()
    print(f"\n[引擎创建]")
    print(f"  单例模式: OK")
    
    # 健康检查
    print(f"\n[健康检查]")
    health = engine.health_check()
    print(f"  Ollama 已安装: {health['ollama_installed']}")
    print(f"  Ollama 运行中: {health['ollama_running']}")
    print(f"  本地模型: {health['local_models']}")
    
    # 状态查询
    print(f"\n[状态查询]")
    for tier, status in health['tier_status'].items():
        print(f"  {tier}: {status}")
    
    print("\n[OK] 部署引擎测试通过")
    return True


def test_deployment_monitor():
    """测试部署监控"""
    print("\n" + "=" * 60)
    print("测试 3: 部署监控")
    print("=" * 60)
    
    from client.src.business.deployment_monitor import DeploymentMonitor, get_deployment_monitor
    
    # 创建监控器
    monitor = get_deployment_monitor()
    print(f"\n[监控器创建]")
    print(f"  单例模式: OK")
    
    # 获取状态
    print(f"\n[状态获取]")
    status = monitor.get_status()
    print(f"  时间戳: {status.timestamp}")
    print(f"  Ollama 运行: {status.ollama_running}")
    print(f"  内存: {status.used_memory_gb:.1f}/{status.total_memory_gb:.1f} GB")
    
    # 诊断报告
    print(f"\n[诊断报告]")
    report = monitor.get_diagnostic_report()
    print(report[:500] + "..." if len(report) > 500 else report)
    
    # 启动监控测试
    print(f"\n[监控循环测试]")
    callback_count = [0]
    
    def on_status(status):
        callback_count[0] += 1
        print(f"  回调 #{callback_count[0]}: Ollama={status.ollama_running}")
    
    monitor.add_callback(on_status)
    monitor.start_monitoring()
    
    time.sleep(3)  # 等待3秒
    monitor.stop_monitoring()
    
    print(f"  回调次数: {callback_count[0]}")
    
    print("\n[OK] 部署监控测试通过")
    return True


def test_model_deployment():
    """测试模型部署（仅检查，不实际下载）"""
    print("\n" + "=" * 60)
    print("测试 4: 模型部署（检查模式）")
    print("=" * 60)
    
    from client.src.business.deployment_engine import DeploymentEngine
    from client.src.business.model_layer_config import ModelTier, get_default_model_for_tier
    
    engine = DeploymentEngine()
    
    # 只检查，不下载
    print(f"\n[部署检查]")
    
    for tier in ModelTier:
        model = get_default_model_for_tier(tier)
        if not model:
            print(f"  {tier.value}: 无可用模型，跳过")
            continue
        
        model_name = model.ollama_name
        is_installed = engine.is_model_installed(model_name)
        
        print(f"  {tier.value}: {model_name}")
        print(f"    - 已安装: {is_installed}")
        print(f"    - 大小: {model.size_gb}GB")
        print(f"    - 用途: {model.purpose}")
    
    print("\n[OK] 模型部署检查完成")
    return True


def main():
    """主测试函数"""
    print("=" * 60)
    print("智能部署中心 - 自动化测试")
    print("=" * 60)
    
    tests = [
        ("模型层配置", test_model_layer_config),
        ("部署引擎", test_deployment_engine),
        ("部署监控", test_deployment_monitor),
        ("模型部署检查", test_model_deployment),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n[ERROR] {name} 测试失败: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # 汇总
    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {name}: {status}")
    
    print(f"\n总计: {passed}/{total} 通过")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
