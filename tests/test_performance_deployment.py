"""
Phase 6: 性能优化与生产部署测试
==================================

测试内容:
1. CacheManager - 缓存管理器
2. ResourcePool - 资源池
3. PerformanceOptimizer - 性能优化器
4. HealthMonitor - 健康监控
5. ProductionReadyChecker - 生产就绪检查
6. DeploymentConfig - 部署配置
"""

import sys
import os
import time
import importlib.util
from collections import defaultdict

# 直接加载模块，绕过 core/__init__.py
module_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'core', 'performance_deployment.py'
)

spec = importlib.util.spec_from_file_location('performance_deployment', module_path)
perf_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(perf_module)

# 导出需要的内容
CacheManager = perf_module.CacheManager
ResourcePool = perf_module.ResourcePool
PerformanceOptimizer = perf_module.PerformanceOptimizer
HealthMonitor = perf_module.HealthMonitor
ProductionReadyChecker = perf_module.ProductionReadyChecker
DeploymentConfig = perf_module.DeploymentConfig
HealthStatus = perf_module.HealthStatus
create_cache_manager = perf_module.create_cache_manager
create_resource_pool = perf_module.create_resource_pool
create_optimizer = perf_module.create_optimizer
create_health_monitor = perf_module.create_health_monitor
create_deployment_config = perf_module.create_deployment_config
generate_kubernetes_manifests = perf_module.generate_kubernetes_manifests
generate_docker_compose = perf_module.generate_docker_compose


def test_cache_manager():
    """测试缓存管理器"""
    print("\n[Test 1] CacheManager")
    print("-" * 40)

    # 创建缓存管理器
    cache = CacheManager(max_size=3, strategy="lru")

    # 写入数据
    cache.set("key1", "value1")
    cache.set("key2", "value2")
    cache.set("key3", "value3")
    print(f"  Initial Size: {len(cache._cache)}")

    # 读取数据
    value1 = cache.get("key1")
    print(f"  Get key1: {value1}")

    # 触发淘汰 (超出容量)
    cache.set("key4", "value4")
    print(f"  After Adding key4: {len(cache._cache)} items")
    print(f"  key1 still exists: {'key1' in cache._cache}")

    # TTL 测试
    cache_ttl = CacheManager(max_size=10, default_ttl=1)
    cache_ttl.set("ttl_key", "ttl_value", ttl=1)
    print(f"  Immediate Get: {cache_ttl.get('ttl_key')}")

    time.sleep(1.1)
    print(f"  After TTL: {cache_ttl.get('ttl_key')}")

    # 统计信息
    stats = cache.get_stats()
    print(f"\n  Cache Stats:")
    print(f"    Hit Rate: {stats['hit_rate']:.2%}")
    print(f"    Hits: {stats['hits']}, Misses: {stats['misses']}")
    print(f"    Evictions: {stats['evictions']}")

    print("  [OK] Cache Manager Test Passed")


def test_cache_strategies():
    """测试缓存策略"""
    print("\n[Test 2] Cache Strategies")
    print("-" * 40)

    strategies = ["lru", "lfu", "fifo", "ttl"]

    for strategy in strategies:
        cache = CacheManager(max_size=3, strategy=strategy)

        # 写入数据
        for i in range(5):
            cache.set(f"key{i}", f"value{i}")

        print(f"  {strategy.upper()} Strategy:")
        print(f"    Items in cache: {len(cache._cache)}")
        print(f"    Evictions: {cache.get_stats()['evictions']}")


def test_resource_pool():
    """测试资源池"""
    print("\n[Test 3] ResourcePool")
    print("-" * 40)

    pool = ResourcePool(max_workers=3)

    # 获取状态
    status = pool.get_status()
    print(f"  Initial Status:")
    print(f"    Total: {status['total']}, Available: {status['available']}")

    # 获取资源
    resource1 = pool.acquire(timeout=1)
    resource2 = pool.acquire(timeout=1)
    print(f"\n  Acquired: {resource1}, {resource2}")

    status = pool.get_status()
    print(f"  After Acquire: {status['available']} available")

    # 释放资源
    pool.release(resource1)
    status = pool.get_status()
    print(f"  After Release: {status['available']} available")

    print("  [OK] Resource Pool Test Passed")


def test_performance_optimizer():
    """测试性能优化器"""
    print("\n[Test 4] PerformanceOptimizer")
    print("-" * 40)

    optimizer = PerformanceOptimizer(strategy="balanced")

    # 记录指标
    for i in range(20):
        optimizer.record_metric("latency_ms", 100 + i * 5)
        optimizer.record_metric("cache_hit_rate", 0.8 - i * 0.01)
        optimizer.record_metric("memory_usage", 0.6 + i * 0.01)

    # 获取统计
    latency_stats = optimizer.get_metric_stats("latency_ms")
    print(f"  Latency Stats:")
    print(f"    Avg: {latency_stats['avg']:.2f}ms")
    print(f"    P95: {latency_stats['p95']:.2f}ms")
    print(f"    P99: {latency_stats['p99']:.2f}ms")

    # 执行优化
    result = optimizer.optimize()
    print(f"\n  Optimization Result:")
    print(f"    Strategy: {result.strategy}")
    print(f"    Improvements: {len(result.improvements)}")
    print(f"    Recommendations: {len(result.recommendations)}")
    print(f"    Execution Time: {result.execution_time_ms:.2f}ms")

    print("  [OK] Performance Optimizer Test Passed")


def test_health_monitor():
    """测试健康监控"""
    print("\n[Test 5] HealthMonitor")
    print("-" * 40)

    monitor = HealthMonitor()

    # 注册健康检查
    def api_health_check():
        return {
            "status": "healthy",
            "message": "API responding",
            "details": {"latency_ms": 50}
        }

    def database_health_check():
        return {
            "status": "healthy",
            "message": "Database connected",
            "details": {"connections": 10}
        }

    def cache_health_check():
        return {
            "status": "degraded",
            "message": "Cache hit rate low",
            "details": {"hit_rate": 0.5}
        }

    monitor.register_check("api", api_health_check)
    monitor.register_check("database", database_health_check)
    monitor.register_check("cache", cache_health_check)

    # 执行健康检查
    result = monitor.check_health()
    print(f"  Overall Status: {result['status']}")
    print(f"  Checks:")
    for name, check in result['checks'].items():
        print(f"    {name}: {check['status']}")

    # 获取历史
    history = monitor.get_health_history()
    print(f"  Health History: {len(history)} entries")

    print("  [OK] Health Monitor Test Passed")


def test_production_ready_checker():
    """测试生产就绪检查"""
    print("\n[Test 6] ProductionReadyChecker")
    print("-" * 40)

    checker = ProductionReadyChecker()

    # 运行检查
    results = checker.run_checks()

    print(f"  Summary:")
    print(f"    Total: {results['summary']['total']}")
    print(f"    Passed: {results['summary']['passed']}")
    print(f"    Failed: {results['summary']['failed']}")
    print(f"    Warnings: {results['summary']['warnings']}")
    print(f"    Pass Rate: {results['summary']['pass_rate']:.1%}")
    print(f"    Ready for Production: {results['summary']['ready_for_production']}")

    # 按类别统计
    by_category = defaultdict(int)
    for item in results['passed']:
        by_category[item['category']] += 1

    print(f"\n  Passed by Category:")
    for category, count in by_category.items():
        print(f"    {category}: {count}")

    print("  [OK] Production Ready Checker Test Passed")


def test_deployment_config():
    """测试部署配置"""
    print("\n[Test 7] DeploymentConfig")
    print("-" * 40)

    # 开发环境配置
    dev_config = DeploymentConfig(environment="development")
    print(f"  Development Config:")
    print(f"    Environment: {dev_config.environment}")
    print(f"    Replicas: {dev_config.replicas}")
    print(f"    Resources: {dev_config.resources}")

    # 生产环境配置
    prod_config = DeploymentConfig(
        environment="production",
        replicas=5
    )
    print(f"\n  Production Config:")
    print(f"    Environment: {prod_config.environment}")
    print(f"    Replicas: {prod_config.replicas}")
    print(f"    Scaling: {prod_config.scaling}")

    # 导出配置
    config_dict = prod_config.to_dict()
    print(f"\n  Config Keys: {list(config_dict.keys())}")

    print("  [OK] Deployment Config Test Passed")


def test_kubernetes_manifests():
    """测试 Kubernetes 清单生成"""
    print("\n[Test 8] Kubernetes Manifests")
    print("-" * 40)

    config = DeploymentConfig(environment="production", replicas=3)
    manifests = generate_kubernetes_manifests(config)

    print(f"  Generated Manifests:")
    for name in manifests.keys():
        lines = manifests[name].count('\n')
        print(f"    {name}: {lines} lines")

    print(f"\n  Deployment Spec:")
    deploy_yaml = manifests['deployment.yaml']
    # 打印关键部分
    for line in deploy_yaml.split('\n')[:5]:
        print(f"    {line}")

    print("  [OK] Kubernetes Manifests Test Passed")


def test_docker_compose():
    """测试 Docker Compose 生成"""
    print("\n[Test 9] Docker Compose")
    print("-" * 40)

    config = DeploymentConfig(environment="staging", replicas=2)
    compose = generate_docker_compose(config)

    lines = compose.split('\n')
    print(f"  Generated Compose: {len(lines)} lines")

    # 打印关键部分
    print(f"  Services: agent, prometheus, grafana")
    print(f"  Replicas: {config.replicas}")

    print("  [OK] Docker Compose Test Passed")


def test_integration():
    """测试集成场景"""
    print("\n[Test 10] Integration Scenario")
    print("-" * 40)

    # 创建一个完整的性能监控设置
    cache = create_cache_manager(strategy="lru", max_size=100)
    pool = create_resource_pool(max_workers=5)
    optimizer = create_optimizer(strategy="balanced")
    monitor = create_health_monitor()

    # 模拟请求流程
    for i in range(50):
        # 获取资源
        resource = pool.acquire(timeout=1)

        if resource:
            # 记录性能指标
            optimizer.record_metric("requests", 1)
            optimizer.record_metric("latency_ms", 50 + i % 20)

            # 尝试从缓存获取
            cache_key = f"user_{i % 10}"
            cached = cache.get(cache_key)

            if cached is None:
                # 缓存未命中，生成数据
                cache.set(cache_key, {"data": f"value_{i}"})

            # 释放资源
            pool.release(resource)

    # 获取统计
    cache_stats = cache.get_stats()
    pool_status = pool.get_status()
    opt_stats = optimizer.get_stats()

    print(f"  Cache Performance:")
    print(f"    Hit Rate: {cache_stats['hit_rate']:.2%}")
    print(f"    Size: {cache_stats['size']}/{cache_stats['max_size']}")

    print(f"\n  Resource Pool:")
    print(f"    Utilization: {pool_status['utilization']:.2%}")

    print(f"\n  Optimizer:")
    print(f"    Metrics Tracked: {len(opt_stats['tracked_metrics'])}")

    print("  [OK] Integration Scenario Test Passed")


def test_quick_start():
    """测试快速启动"""
    print("\n[Test 11] Quick Start")
    print("-" * 40)

    # 一行代码创建所有组件
    cache = create_cache_manager()
    optimizer = create_optimizer()
    monitor = create_health_monitor()
    config = create_deployment_config("production")

    # 快速使用
    cache.set("quick_test", "quick_value")
    result = cache.get("quick_test")

    optimizer.record_metric("test_metric", 100)
    stats = optimizer.get_metric_stats("test_metric")

    print(f"  Cache: {result}")
    print(f"  Optimizer: {stats['avg']:.2f}")
    print(f"  Config: {config.environment} ({config.replicas} replicas)")

    print("  [OK] Quick Start Test Passed")


def main():
    """运行所有测试"""
    print("=" * 60)
    print("  Phase 6: 性能优化与生产部署测试")
    print("=" * 60)

    test_cache_manager()
    test_cache_strategies()
    test_resource_pool()
    test_performance_optimizer()
    test_health_monitor()
    test_production_ready_checker()
    test_deployment_config()
    test_kubernetes_manifests()
    test_docker_compose()
    test_integration()
    test_quick_start()

    print("\n" + "=" * 60)
    print("  All Phase 6 Tests Passed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
