#!/usr/bin/env python3
"""验证 BaseProxyManager 独立工作"""
import sys
sys.path.insert(0, "client/src")

import asyncio
from client.src.business.base_proxy_manager import BaseProxyManager, BaseProxy, ProxyStatus

# 子类实现具体的代理获取
class MyProxyManager(BaseProxyManager):
    async def fetch_proxies(self):
        # 模拟返回 3 个测试代理
        return [
            BaseProxy(host="proxy1.example.com", port=8080, source="test"),
            BaseProxy(host="proxy2.example.com", port=8080, source="test"),
            BaseProxy(host="proxy3.example.com", port=8080, source="test"),
        ]
    
    async def validate_proxy(self, proxy):
        # 模拟验证：所有代理都可用
        return True, 100.0

# 测试 1: 刷新代理池
mgr = MyProxyManager(max_pool_size=10, validation_level=0)
added = asyncio.run(mgr.refresh_pool())
assert added == 3, f"代理池刷新失败: {added}"
print(f"[PASS] 测试1: 刷新代理池 (added={added})")

# 测试 2: 获取最佳代理
proxy = mgr.get_best_proxy()
assert proxy is not None, "获取最佳代理失败"
print(f"[PASS] 测试2: 获取最佳代理 ({proxy.host})")

# 测试 3: 轮询获取
p1 = mgr.get_round_robin()
p2 = mgr.get_round_robin()
assert p1 is not None and p2 is not None, "轮询失败"
print(f"[PASS] 测试3: 轮询获取")

# 测试 4: 标记成功/失败
mgr.mark_success(proxy, 50.0)
mgr.mark_failure(proxy)
assert proxy.success_count == 1, f"成功计数错误: {proxy.success_count}"
assert proxy.failure_count == 1, f"失败计数错误: {proxy.failure_count}"
print("[PASS] 测试4: 标记成功/失败")

# 测试 5: 按策略获取
proxy_best = mgr.get_by_strategy("best")
proxy_rr = mgr.get_by_strategy("round_robin")
proxy_rand = mgr.get_by_strategy("random")
assert all(p is not None for p in [proxy_best, proxy_rr, proxy_rand]), "策略获取失败"
print("[PASS] 测试5: 按策略获取")

# 测试 6: 统计信息
stats = mgr.get_stats()
assert "total_proxies" in stats, "统计信息缺失"
print(f"[PASS] 测试6: 统计信息 ({stats})")

# 测试 7: BaseProxy.score()
score = proxy.score()
assert 0 <= score <= 1, f"评分超出范围: {score}"
print(f"[PASS] 测试7: 代理评分 ({score:.3f})")

print("\n[OK] BaseProxyManager 验证通过")
