"""
测试效果可验证机制
"""

import sys
import os

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'client', 'src'))

# 测试效果可验证机制
print("测试效果可验证机制...")

# 直接导入模块
import importlib.util
tool_module_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'client', 'src', 'business', 'tools', 'base_tool.py'
)
spec = importlib.util.spec_from_file_location("base_tool", tool_module_path)
tool_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool_module)

VerificationStatus = tool_module.VerificationStatus
AgentCallResult = tool_module.AgentCallResult

# 测试创建成功结果
result = AgentCallResult.success(data={"result": "test"}, message="执行成功")
assert result.success is True
assert result.data == {"result": "test"}
print("✓ 创建成功结果")

# 测试验证状态默认值
assert result.verification["status"] == VerificationStatus.UNVERIFIED.value
assert result.verification["score"] == 0.0
print("✓ 默认验证状态正确")

# 测试设置验证信息
criteria = ["数据完整性", "格式正确性", "结果准确性"]
checks = [
    {"name": "数据不为空", "passed": True, "value": True},
    {"name": "格式正确", "passed": True, "value": "json"},
    {"name": "结果符合预期", "passed": True, "value": 100}
]
result.set_verification(criteria, checks, 0.95, "所有验证项通过")

assert result.verification["status"] == VerificationStatus.VERIFIED.value
assert result.verification["score"] == 0.95
assert result.verification["passed_count"] == 3
assert result.verification["total_checks"] == 3
print("✓ 设置验证信息成功")

# 测试 is_verified 方法
assert result.is_verified() is True
print("✓ is_verified 方法正确")

# 测试验证摘要
summary = result.get_verification_summary()
assert "验证状态: verified" in summary
assert "分数: 0.95" in summary
assert "通过: 3/3" in summary
print("✓ 验证摘要正确")

# 测试部分验证状态
checks_partial = [
    {"name": "数据不为空", "passed": True, "value": True},
    {"name": "格式正确", "passed": True, "value": "json"},
    {"name": "结果符合预期", "passed": False, "value": 90}
]
result_partial = AgentCallResult.success(data={"result": "partial"})
result_partial.set_verification(criteria, checks_partial, 0.67, "部分验证项通过")

assert result_partial.verification["status"] == VerificationStatus.PARTIAL.value
assert result_partial.is_verified() is False
print("✓ 部分验证状态正确")

# 测试验证失败状态
checks_failed = [
    {"name": "数据不为空", "passed": False, "value": False},
    {"name": "格式正确", "passed": False, "value": "invalid"}
]
result_failed = AgentCallResult.success(data={"result": "failed"})
result_failed.set_verification(criteria, checks_failed, 0.0, "所有验证项失败")

assert result_failed.verification["status"] == VerificationStatus.FAILED.value
print("✓ 验证失败状态正确")

# 测试转换为字典和 JSON
result_dict = result.to_dict()
assert "verification" in result_dict
assert result_dict["verification"]["status"] == "verified"

json_str = result.to_json()
assert '"status": "verified"' in json_str
print("✓ 字典和 JSON 转换正确")

print("\n🎉 所有测试通过!")