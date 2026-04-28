"""
测试健康检查机制和日志级别配置
"""

import sys
import os
import time

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'client', 'src'))

print("测试健康检查机制和日志级别配置...")

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
LogLevel = router_module.LogLevel
HealthStatus = router_module.HealthStatus

# 创建路由器实例
router = GlobalModelRouter()
print("✓ 路由器初始化成功")

# 测试日志级别配置
print("\n测试日志级别配置...")

# 获取默认日志级别
default_level = router.get_log_level()
print(f"✓ 默认日志级别: {default_level.value}")

# 设置日志级别为 DEBUG
router.set_log_level("debug")
assert router.get_log_level() == LogLevel.DEBUG
print("✓ 设置日志级别为 debug")

# 设置日志级别为 WARN
router.set_log_level(LogLevel.WARN)
assert router.get_log_level() == LogLevel.WARN
print("✓ 设置日志级别为 warn")

# 设置日志级别为 INFO（恢复默认）
router.set_log_level("info")
assert router.get_log_level() == LogLevel.INFO
print("✓ 设置日志级别为 info")

# 测试无效日志级别
router.set_log_level("invalid")
assert router.get_log_level() == LogLevel.INFO  # 默认回退到 INFO
print("✓ 无效日志级别正确回退")

# 测试请求日志
print("\n测试请求日志...")

# 模拟记录请求
router._log_request("test-model", router_module.ModelCapability.CHAT, True, 0.5)
router._log_request("test-model", router_module.ModelCapability.CHAT, False, 1.2)
router._log_request("test-model-2", router_module.ModelCapability.CODE_GENERATION, True, 0.8)

# 获取请求日志
logs = router.get_request_logs(limit=10)
assert len(logs) == 3
print("✓ 请求日志记录成功")

# 获取请求统计
stats = router.get_request_stats()
assert stats["total_requests"] == 3
assert stats["success_rate"] == 2/3
print("✓ 请求统计正确")

# 测试健康检查机制
print("\n测试健康检查机制...")

# 检查健康检查是否启动
assert router._health_check_running == True
print("✓ 健康检查已启动")

# 获取健康摘要
health_summary = router.get_health_summary()
assert "overall" in health_summary
assert "available_models" in health_summary
assert "total_models" in health_summary
print("✓ 健康摘要获取成功")

# 测试设置健康检查间隔
router.set_health_check_interval(120)
assert router._health_check_interval == 120
print("✓ 健康检查间隔设置成功")

# 测试停止健康检查
router.stop_health_check()
assert router._health_check_running == False
print("✓ 健康检查停止成功")

# 测试重新启动健康检查
router.start_health_check(60)
assert router._health_check_running == True
print("✓ 健康检查重新启动成功")

print("\n🎉 所有测试通过!")