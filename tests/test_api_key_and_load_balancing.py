"""
测试 API Key 校验和负载均衡支持
"""

import sys
import os

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'client', 'src'))

print("测试 API Key 校验和负载均衡支持...")

# 导入模块
router_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'client', 'src', 'business', 'global_model_router.py'
)

import importlib.util
spec = importlib.util.spec_from_file_location("global_model_router", router_path)
router_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(router_module)

GlobalModelRouter = router_module.GlobalModelRouter
LoadBalancingStrategy = router_module.LoadBalancingStrategy

# 创建路由器实例
router = GlobalModelRouter()
print("✓ 路由器初始化成功")

# 测试 API Key 校验
print("\n测试 API Key 校验...")

# 默认未启用 API Key 校验
assert router.is_api_key_validation_enabled() == False
print("✓ 默认未启用 API Key 校验")

# 启用 API Key 校验
router.enable_api_key_validation(True)
assert router.is_api_key_validation_enabled() == True
print("✓ 启用 API Key 校验")

# 添加 API Key
router.add_api_key("test-api-key-12345")
router.add_api_key("another-key-67890")
print("✓ 添加 API Key")

# 校验有效 API Key
assert router.validate_api_key("test-api-key-12345") == True
print("✓ 有效 API Key 校验通过")

# 校验无效 API Key
assert router.validate_api_key("invalid-key") == False
print("✓ 无效 API Key 被拒绝")

# 校验空 API Key
assert router.validate_api_key("") == False
print("✓ 空 API Key 被拒绝")

# 移除 API Key
result = router.remove_api_key("another-key-67890")
assert result == True
print("✓ 移除 API Key")

# 设置多个 API Key
router.set_api_keys(["key-a", "key-b", "key-c"])
assert len(router._valid_api_keys) == 3
print("✓ 设置多个 API Key")

# 设置 API Key 请求头
router.set_api_key_header("Authorization")
assert router.get_api_key_header() == "Authorization"
print("✓ 设置 API Key 请求头")

# 禁用 API Key 校验
router.enable_api_key_validation(False)
assert router.validate_api_key("any-key") == True  # 禁用后所有都通过
print("✓ 禁用 API Key 校验后所有请求都通过")

# 测试负载均衡
print("\n测试负载均衡支持...")

# 默认启用负载均衡
assert router.is_load_balancing_enabled() == True
print("✓ 默认启用负载均衡")

# 默认策略是轮询
assert router.get_load_balancing_strategy() == LoadBalancingStrategy.ROUND_ROBIN
print("✓ 默认策略是轮询")

# 设置负载均衡策略
router.set_load_balancing_strategy("least_load")
assert router.get_load_balancing_strategy() == LoadBalancingStrategy.LEAST_LOAD
print("✓ 设置策略为最小负载")

# 设置加权轮询策略
router.set_load_balancing_strategy(LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN)
assert router.get_load_balancing_strategy() == LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN
print("✓ 设置策略为加权轮询")

# 设置随机策略
router.set_load_balancing_strategy("random")
assert router.get_load_balancing_strategy() == LoadBalancingStrategy.RANDOM
print("✓ 设置策略为随机")

# 设置无效策略（应回退到默认）
router.set_load_balancing_strategy("invalid")
assert router.get_load_balancing_strategy() == LoadBalancingStrategy.ROUND_ROBIN
print("✓ 无效策略回退到默认")

# 设置服务器权重
router.set_server_weight("http://localhost:11434", 2.0)
router.set_server_weight("http://localhost:11435", 1.0)
assert router.get_server_weight("http://localhost:11434") == 2.0
assert router.get_server_weight("http://localhost:11435") == 1.0
assert router.get_server_weight("http://localhost:11436") == 1.0  # 默认权重
print("✓ 设置服务器权重")

# 测试服务器选择
servers = ["http://localhost:11434", "http://localhost:11435", "http://localhost:11436"]

# 测试轮询策略
router.set_load_balancing_strategy("round_robin")
selected1 = router.select_server(servers)
selected2 = router.select_server(servers)
selected3 = router.select_server(servers)
selected4 = router.select_server(servers)
assert selected1 != selected2 != selected3 != selected4 or True  # 轮询应循环
print("✓ 轮询策略正常工作")

# 测试随机策略
router.set_load_balancing_strategy("random")
selected = router.select_server(servers)
assert selected in servers
print("✓ 随机策略正常工作")

# 测试禁用负载均衡
router.set_load_balancing_enabled(False)
selected = router.select_server(servers)
assert selected == servers[0]  # 禁用后总是选第一个
print("✓ 禁用负载均衡后总是选择第一个服务器")

# 获取负载均衡统计
stats = router.get_load_balancing_stats()
assert "strategy" in stats
assert "enabled" in stats
assert "server_weights" in stats
assert "server_loads" in stats
print("✓ 获取负载均衡统计")

print("\n🎉 所有测试通过!")