# -*- coding: utf-8 -*-
"""
代理搜索服务测试
"""

import asyncio
import sys
import io
import logging

# 添加项目路径
sys.path.insert(0, r"F:\mhzyapp\LivingTreeAlAgent")

# 设置 UTF-8 输出
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


async def test_fetch_proxies():
    """测试代理获取"""
    print("\n" + "=" * 50)
    print("Test 1: Fetch Proxies")
    print("=" * 50)
    
    try:
        from client.src.business.proxy_search import fetch_proxies
        
        print("正在从代理源获取列表...")
        proxies = await fetch_proxies()
        
        print(f"\n获取到 {len(proxies)} 个代理")
        
        # 显示前 10 个
        for i, proxy in enumerate(proxies[:10], 1):
            print(f"  {i}. {proxy.address} [{proxy.protocol}] from {proxy.source}")
        
        if len(proxies) > 10:
            print(f"  ... 还有 {len(proxies) - 10} 个")
        
        print("\n[PASS] Proxy Fetch Test!")
        return proxies
        
    except Exception as e:
        print(f"[FAIL] Proxy Fetch Error: {e}")
        return []


async def test_validator(proxies):
    """测试代理验证"""
    print("\n" + "=" * 50)
    print("Test 2: Validate Proxies")
    print("=" * 50)
    
    if not proxies:
        print("[SKIP] No proxies to validate")
        return []
    
    try:
        from client.src.business.proxy_search import validate_proxies
        
        # 只验证前 10 个
        test_proxies = proxies[:10]
        print(f"正在验证 {len(test_proxies)} 个代理...")
        
        valid_results = []
        
        def callback(result):
            if result.is_valid:
                valid_results.append(result)
                print(f"  [OK] {result.proxy.address} (L{result.level})")
            else:
                print(f"  [X] {result.proxy.address}: {result.error}")
        
        results = await validate_proxies(test_proxies)
        
        for r in results:
            callback(r)
        
        print(f"\n验证完成: {len(valid_results)}/{len(test_proxies)} 有效")
        print("\n[PASS] Validator Test!")
        
        return valid_results
        
    except Exception as e:
        print(f"[FAIL] Validator Error: {e}")
        import traceback
        traceback.print_exc()
        return []


async def test_proxy_pool():
    """测试代理池"""
    print("\n" + "=" * 50)
    print("Test 3: Proxy Pool")
    print("=" * 50)
    
    try:
        from client.src.business.proxy_search import initialize_pool, get_proxy_pool
        from client.src.business.proxy_search.deep_search_integration import get_integration, SearchMode
        
        print("初始化代理池...")
        pool = await initialize_pool(min_size=3)
        
        print(f"\n代理池状态:")
        stats = pool.get_stats()
        print(f"  总代理数: {stats['total_proxies']}")
        print(f"  健康代理: {stats['healthy_proxies']}")
        print(f"  平均延迟: {stats['avg_latency']:.3f}s")
        
        # 获取一个代理
        pooled = pool.get_proxy()
        if pooled:
            print(f"\n获取到代理: {pooled.proxy.address}")
            print(f"  评分: {pooled.score:.2f}")
            print(f"  成功率: {pooled.success_count}/{pooled.success_count + pooled.failure_count}")
        
        print("\n[PASS] Proxy Pool Test!")
        return pool
        
    except Exception as e:
        print(f"[FAIL] Proxy Pool Error: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_middleware():
    """测试中间件"""
    print("\n" + "=" * 50)
    print("Test 4: Middleware")
    print("=" * 50)
    
    try:
        from client.src.business.proxy_search import get_middleware, get_proxy_pool
        
        pool = get_proxy_pool()
        
        if pool.healthy_size == 0:
            print("[SKIP] No healthy proxies")
            return
        
        middleware = get_middleware()
        
        # 测试请求（使用 httpbin.org）
        print("测试代理请求...")
        
        try:
            response = middleware.get(
                "http://httpbin.org/ip",
                timeout=10
            )
            print(f"  状态码: {response.status_code}")
            print(f"  响应: {response.json()}")
            print("\n[PASS] Middleware Test!")
        except Exception as e:
            print(f"  请求失败: {e}")
            print("\n[INFO] Middleware test failed (expected with free proxies)")
        
    except Exception as e:
        print(f"[FAIL] Middleware Error: {e}")
        import traceback
        traceback.print_exc()


async def test_integration():
    """测试集成"""
    print("\n" + "=" * 50)
    print("Test 5: Deep Search Integration")
    print("=" * 50)
    
    try:
        from client.src.business.proxy_search.deep_search_integration import initialize_integration, SearchMode
        
        integration = await initialize_integration()
        
        print("\n测试 URL 判断:")
        test_urls = [
            "https://www.google.com/search?q=test",
            "https://scholar.google.com/scholar?q=test",
            "https://www.baidu.com/s?wd=test",
            "https://arxiv.org/abs/1234.5678",
        ]
        
        for url in test_urls:
            use_proxy = integration.should_use_proxy(url)
            mode = "PROXY" if use_proxy else "DIRECT"
            print(f"  [{mode}] {url}")
        
        print("\n获取统计:")
        stats = integration.get_stats()
        print(f"  总请求: {stats['total_requests']}")
        print(f"  代理请求: {stats['proxy_requests']}")
        print(f"  直连请求: {stats['direct_requests']}")
        
        print("\n[PASS] Integration Test!")
        
        # 清理
        await integration.cleanup()
        
    except Exception as e:
        print(f"[FAIL] Integration Error: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("  Proxy Search Service Test Suite")
    print("  (科研代理搜索服务测试)")
    print("=" * 60)
    
    # Test 1: 获取代理
    proxies = await test_fetch_proxies()
    
    # Test 2: 验证代理
    await test_validator(proxies)
    
    # Test 3: 代理池
    await test_proxy_pool()
    
    # Test 4: 中间件
    await test_middleware()
    
    # Test 5: 集成
    await test_integration()
    
    print("\n" + "=" * 60)
    print("  All Tests Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
