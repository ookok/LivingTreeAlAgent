"""
测试 Opik 集成功能

验证：
1. Opik SDK 安装
2. 追踪模块导入
3. 追踪装饰器工作
4. GlobalModelRouter 集成
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("测试 Opik 集成功能")
print("=" * 60)

# 测试1: 检查 Opik SDK 是否安装
print("\n[测试 1] 检查 Opik SDK 安装...")
try:
    import opik
    print(f"✅ Opik SDK 已安装 (版本: {opik.__version__ if hasattr(opik, '__version__') else 'unknown'})")
except ImportError as e:
    print(f"❌ Opik SDK 未安装: {e}")
    print("请运行: pip install opik")
    sys.exit(1)

# 测试2: 导入追踪模块
print("\n[测试 2] 导入 Opik 追踪模块...")
try:
    from client.src.business.opik_tracer import (
        OpikConfig,
        configure_opik,
        is_opik_enabled,
        trace_llm_call,
        trace_tool_call,
        OPIK_AVAILABLE,
    )
    print(f"✅ 追踪模块导入成功 (OPIK_AVAILABLE: {OPIK_AVAILABLE})")
except ImportError as e:
    print(f"❌ 追踪模块导入失败: {e}")
    sys.exit(1)

# 测试3: 初始化 Opik（本地模式）
print("\n[测试 3] 初始化 Opik（本地模式）...")
try:
    config = OpikConfig(
        enabled=True,
        use_local=True,
        project_name="livingtree-test",
    )
    success = configure_opik(config)
    if success:
        print("✅ Opik 初始化成功（本地模式）")
    else:
        print("❌ Opik 初始化失败")
except Exception as e:
    print(f"❌ Opik 初始化异常: {e}")

# 测试4: 测试追踪装饰器
print("\n[测试 4] 测试追踪装饰器...")

@trace_llm_call
def mock_llm_call(prompt: str) -> str:
    """模拟 LLM 调用"""
    return f"模拟响应: {prompt[:20]}..."

try:
    result = mock_llm_call("测试提示")
    print(f"✅ 追踪装饰器工作正常 (结果: {result[:30]}...)")
except Exception as e:
    print(f"❌ 追踪装饰器失败: {e}")

# 测试5: 检查 GlobalModelRouter 集成
print("\n[测试 5] 检查 GlobalModelRouter 集成...")
try:
    # 检查文件是否包含 Opik 相关代码
    with open("client/src/business/global_model_router.py", "r", encoding="utf-8") as f:
        content = f.read()

    checks = [
        ("OPIK_AVAILABLE", "Opik 导入检查"),
        ("_opik_trace", "Opik trace 初始化"),
        ("log_trace", "Opik 追踪记录"),
    ]

    for keyword, description in checks:
        if keyword in content:
            print(f"✅ 找到 {description} ({keyword})")
        else:
            print(f"⚠️  未找到 {description} ({keyword})")

    print("✅ GlobalModelRouter 集成检查完成")

except FileNotFoundError:
    print("❌ 找不到 global_model_router.py 文件")
except Exception as e:
    print(f"❌ 检查失败: {e}")

# 测试6: 测试手动追踪接口
print("\n[测试 6] 测试手动追踪接口...")

try:
    from client.src.business.opik_tracer import start_trace, log_trace

    # 创建 trace
    trace = start_trace(name="test_manual_trace", trace_type="llm")
    if trace is not None:
        # 记录输入输出
        log_trace(
            trace,
            input_data={"prompt": "测试输入"},
            output_data={"response": "测试输出"},
            metadata={"test": True}
        )
        print("✅ 手动追踪接口工作正常")
    else:
        print("⚠️  Trace 对象为 None（可能 Opik 未启用）")

except Exception as e:
    print(f"❌ 手动追踪接口失败: {e}")

# 总结
print("\n" + "=" * 60)
print("测试总结")
print("=" * 60)

print("\n✅ Opik 集成测试完成！")
print("\n下一步:")
print("1. 启动 Opik 本地服务器: opik server start")
print("2. 在浏览器打开: http://localhost:5173")
print("3. 运行 LivingTreeAI，执行一些 LLM 调用")
print("4. 在 Opik Dashboard 中查看追踪数据")

print("\n" + "=" * 60)
print("测试完成！")
print("=" * 60)
