"""
轻量级UI与强化网络层系统 - 中继服务器集成测试
"""

import sys
import os
import io

# 设置 stdout 编码为 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_models():
    """测试数据模型"""
    print("=== 测试数据模型 ===")
    from models import RelayServer, RelayConnection, RelayMessage, RelayPeer
    
    # 测试中继服务器模型
    server = RelayServer(
        id="test",
        host="139.199.124.242",
        port=8888,
        name="腾讯云服务器",
        region="华南",
    )
    print(f"✓ 中继服务器: {server.name} ({server.host}:{server.port})")
    print(f"  质量分数: {server.quality_score}")
    print(f"  健康状态: {server.is_healthy}")
    
    # 测试中继连接
    conn = RelayConnection(
        connection_id="conn_001",
        relay_server_id="test",
    )
    print(f"✓ 中继连接: {conn.connection_id}")
    
    # 测试中继消息
    msg = RelayMessage(
        message_id="msg_001",
        from_peer="peer_a",
        to_peer="peer_b",
        content="Hello",
    )
    print(f"✓ 中继消息: {msg.message_id}")
    
    return True


def test_relay_client():
    """测试中继客户端"""
    print("\n=== 测试中继客户端 ===")
    from relay_client import RelayClient, RelayServerConfig, get_relay_manager, RelayState
    
    # 创建客户端配置
    config = RelayServerConfig(
        host="139.199.124.242",
        port=8888,
        api_key="",
    )
    print(f"✓ 客户端配置: {config.host}:{config.port}")
    
    # 创建客户端
    client = RelayClient("test_peer_001", config)
    print(f"✓ 中继客户端创建: peer_id={client.peer_id}")
    print(f"  初始状态: {client.state.value}")
    
    # 测试服务器管理器
    manager = get_relay_manager()
    print(f"✓ 中继管理器获取成功")
    
    # 检查默认服务器
    primary = manager.get_primary_server()
    if primary:
        print(f"✓ 主服务器: {primary.name} ({primary.host})")
    
    return True


def test_protocol_fallback():
    """测试协议降级"""
    print("\n=== 测试协议降级 ===")
    from protocol_fallback import (
        ProtocolFallbackManager, ProtocolType, 
        ConnectionState, RelayEndpoint
    )
    
    manager = ProtocolFallbackManager()
    print(f"✓ 协议降级管理器创建成功")
    
    # 添加中继端点
    endpoint = manager.add_relay_endpoint(
        host="139.199.124.242",
        port=8888,
        name="腾讯云服务器",
        region="华南",
    )
    print(f"✓ 添加中继端点: {endpoint.name} ({endpoint.host})")
    
    # 获取最佳协议
    best = manager.get_best_protocol("lan")
    print(f"✓ 最佳协议 (LAN): {best.value}")
    
    # 获取最佳中继
    best_relay = manager.get_best_relay_endpoint()
    if best_relay:
        print(f"✓ 最佳中继: {best_relay.name}")
    
    # 获取所有中继
    relays = manager.get_all_relay_endpoints()
    print(f"✓ 中继服务器数量: {len(relays)}")
    
    return True


def test_adaptive_connection():
    """测试自适应连接"""
    print("\n=== 测试自适应连接 ===")
    from adaptive_connection import (
        AdaptiveConnectionPool, ConnectionLoadBalancer,
        ConnectionType, RelayConfig
    )
    
    # 创建连接池
    pool = AdaptiveConnectionPool()
    print(f"✓ 连接池创建成功")
    
    # 添加中继服务器
    relay = pool.add_relay_server(
        host="139.199.124.242",
        port=8888,
        name="腾讯云服务器",
        region="华南",
    )
    print(f"✓ 添加中继服务器: {relay.name}")
    
    # 获取最佳服务器
    best = pool.get_best_relay_server()
    if best:
        print(f"✓ 最佳中继: {best.name} (质量: {best.quality_score})")
    
    # 测试负载均衡器
    lb = ConnectionLoadBalancer()
    lb.add_node("node1", "192.168.1.1", 8080, weight=10)
    lb.add_node("node2", "192.168.1.2", 8080, weight=5)
    print(f"✓ 负载均衡器: 添加了 2 个节点")
    
    return True


def test_quality_monitor():
    """测试质量监控"""
    print("\n=== 测试质量监控 ===")
    from quality_monitor import QualityMonitor, NetworkQuality
    
    monitor = QualityMonitor()
    print(f"✓ 质量监控器创建成功")
    
    # 记录延迟
    monitor.record_latency(25)
    monitor.record_latency(30)
    monitor.record_latency(20)
    print(f"✓ 记录延迟数据")
    
    # 获取质量
    quality = monitor.get_current_quality()
    print(f"✓ 当前质量: {quality.value}")
    
    return True


def test_fast_recovery():
    """测试快速恢复"""
    print("\n=== 测试快速恢复 ===")
    from fast_recovery import FastRecoveryManager, FaultType
    from datetime import datetime
    
    manager = FastRecoveryManager()
    print(f"✓ 快速恢复管理器创建成功")
    
    # 记录故障
    fault = FaultType(
        fault_type=FaultType.NETWORK_TIMEOUT,
        timestamp=datetime.now(),
        message="连接超时",
        details={"host": "139.199.124.242", "port": 8888}
    )
    manager.record_fault(fault)
    print(f"✓ 记录故障: {fault.fault_type.value}")
    
    return True


def test_network_probe():
    """测试网络探测"""
    print("\n=== 测试网络探测 ===")
    from network_probe import NetworkProbeManager
    
    probe = NetworkProbeManager()
    print(f"✓ 网络探测管理器创建成功")
    
    return True


def main():
    """主测试函数"""
    print("=" * 60)
    print("轻量级UI与强化网络层系统 - 中继服务器集成测试")
    print("=" * 60)
    
    tests = [
        ("数据模型", test_models),
        ("中继客户端", test_relay_client),
        ("协议降级", test_protocol_fallback),
        ("自适应连接", test_adaptive_connection),
        ("质量监控", test_quality_monitor),
        ("快速恢复", test_fast_recovery),
        ("网络探测", test_network_probe),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"✗ {name} 测试失败: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {status}: {name}")
    
    print(f"\n总计: {passed}/{total} 通过")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
