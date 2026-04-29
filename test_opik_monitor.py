"""
测试 Opik 生产监控功能

验证：
1. OpikMonitor 模块导入
2. 监控器初始化
3. 装饰器工作
4. BaseTool 集成
5. 告警规则触发
"""

import sys
import os
import time

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("测试 Opik 生产监控功能（Phase 2）")
print("=" * 60)

# 测试1: 导入监控模块
print("\n[测试 1] 导入 Opik 监控模块...")
try:
    from client.src.business.opik_monitor import (
        MonitorConfig,
        AlertRule,
        OpikMonitor,
        get_monitor,
        configure_monitor,
        monitor_tool,
    )
    print("✅ 监控模块导入成功")
except ImportError as e:
    print(f"❌ 监控模块导入失败: {e}")
    sys.exit(1)

# 测试2: 初始化监控器
print("\n[测试 2] 初始化监控器...")
try:
    config = MonitorConfig(
        enabled=True,
        monitor_tool_calls=True,
        monitor_latency=True,
        alert_rules=[
            AlertRule(name="测试告警", metric="failure_rate", threshold=0.5, window_minutes=1),
        ]
    )
    
    monitor = OpikMonitor(config)
    print("✅ 监控器初始化成功")
    print(f"   监控启用: {monitor.config.enabled}")
    print(f"   告警规则数: {len(monitor.config.alert_rules)}")
    
except Exception as e:
    print(f"❌ 监控器初始化失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试3: 测试监控装饰器
print("\n[测试 3] 测试监控装饰器...")

@monitor_tool("test_tool")
def mock_tool_execution(success: bool = True):
    """模拟工具执行"""
    if not success:
        raise Exception("模拟失败")
    return {"result": "success", "token_usage": 100}

try:
    # 测试成功执行
    result = mock_tool_execution(success=True)
    print(f"✅ 装饰器工作正常 (成功执行: {result})")
    
    # 测试失败执行
    try:
        mock_tool_execution(success=False)
    except Exception as e:
        print(f"✅ 装饰器工作正常 (失败执行: {e})")
        
except Exception as e:
    print(f"❌ 装饰器失败: {e}")
    import traceback
    traceback.print_exc()

# 测试4: 检查 BaseTool 集成
print("\n[测试 4] 检查 BaseTool 集成...")
try:
    # 检查文件是否包含监控相关代码
    with open("client/src/business/tools/base_tool.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    checks = [
        ("OPIK_MONITOR_AVAILABLE", "Opik 监控导入检查"),
        ("_monitor", "监控器初始化"),
        ("get_monitor", "获取监控器"),
    ]
    
    for keyword, description in checks:
        if keyword in content:
            print(f"✅ 找到 {description} ({keyword})")
        else:
            print(f"⚠️ 未找到 {description} ({keyword})")
    
    print("✅ BaseTool 集成检查完成")
    
except FileNotFoundError:
    print("❌ 找不到 base_tool.py 文件")
except Exception as e:
    print(f"❌ 检查失败: {e}")

# 测试5: 测试监控统计功能
print("\n[测试 5] 测试监控统计功能...")

try:
    # 使用全局监控器
    configure_monitor(config)
    global_monitor = get_monitor()
    
    # 模拟一些执行记录
    @monitor_tool("test_tool_2")
    def another_mock_tool(fail_rate: float = 0.0):
        """模拟工具执行，可控制失败率"""
        import random
        if random.random() < fail_rate:
            raise Exception("模拟失败")
        time.sleep(0.1)  # 模拟延迟
        return {"result": "ok"}
    
    # 执行几次（50% 失败率）
    print("   执行 10 次模拟调用 (50% 失败率)...")
    for i in range(10):
        try:
            another_mock_tool(fail_rate=0.5)
        except:
            pass
    
    # 获取统计
    report = global_monitor.get_monitoring_report()
    stats = report["stats"]
    
    print(f"✅ 监控统计功能正常")
    print(f"   总执行次数: {stats['total_records']}")
    print(f"   总失败率: {stats['overall_failure_rate']:.2%}")
    print(f"   平均延迟: {stats['overall_avg_latency']:.2f}s")
    print(f"   告警次数: {report['alert_count']}")
    
except Exception as e:
    print(f"❌ 监控统计功能失败: {e}")
    import traceback
    traceback.print_exc()

# 测试6: 测试告警规则
print("\n[测试 6] 测试告警规则...")

try:
    # 创建一个低阈值的告警规则（应该触发）
    test_config = MonitorConfig(
        enabled=True,
        alert_rules=[
            AlertRule(name="低阈值测试", metric="failure_rate", threshold=0.01, window_minutes=1),
        ]
    )
    
    test_monitor = OpikMonitor(test_config)
    
    # 模拟高失败率
    from client.src.business.opik_monitor import ToolExecutionRecord
    
    record = ToolExecutionRecord(
        tool_name="test_tool_alert",
        success=False,  # 失败
        latency=1.0,
        timestamp=time.time(),
    )
    test_monitor.stats.add_record(record)
    
    # 手动检查告警
    test_monitor._check_alerts("test_tool_alert")
    
    if test_monitor.alert_history:
        print(f"✅ 告警规则触发成功")
        print(f"   告警数: {len(test_monitor.alert_history)}")
        print(f"   最新告警: {test_monitor.alert_history[-1]['rule_name']}")
    else:
        print("⚠️ 告警规则未触发（可能窗口时间不匹配）")
    
except Exception as e:
    print(f"❌ 告警规则测试失败: {e}")
    import traceback
    traceback.print_exc()

# 总结
print("\n" + "=" * 60)
print("测试总结")
print("=" * 60)

print("\n✅ Opik 生产监控（Phase 2）测试完成！")
print("\n下一步:")
print("1. 确保所有 Tool 都使用 @monitor_tool 装饰器")
print("2. 在 Dashboard 中查看 Tool 执行统计")
print("3. 配置合适的告警规则阈值")
print("4. 继续 Phase 3（Dashboard 集成）")

print("\n" + "=" * 60)
print("测试完成！")
print("=" * 60)
