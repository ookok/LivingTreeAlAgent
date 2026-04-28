"""
测试反合理化表和 ToolResult 强制验证功能
"""

import pytest
from client.src.business.self_evolution.anti_rationalization_table import (
    AntiRationalizationTable,
    AntiRationalizationRule,
)
from client.src.business.tools.tool_registry import ToolResult


class TestAntiRationalizationTable:
    """反合理化表测试"""
    
    def test_load_default_rules(self):
        """测试加载默认规则"""
        table = AntiRationalizationTable()
        rules = table.get_all_rules()
        
        assert len(rules) > 0
        assert any(r["category"] == "code_quality" for r in rules)
        assert any(r["category"] == "testing" for r in rules)
        assert any(r["category"] == "security" for r in rules)
    
    def test_check_statement_triggers_rule(self):
        """测试语句触发反合理化规则"""
        table = AntiRationalizationTable()
        
        # 测试常见错误模式
        triggered = table.check_statement("这个代码看起来没问题")
        assert len(triggered) > 0
        assert any("看起来没问题" in r.pattern for r in triggered)
    
    def test_check_statement_no_trigger(self):
        """测试正常语句不触发规则"""
        table = AntiRationalizationTable()
        
        triggered = table.check_statement("测试通过率为 95%，覆盖所有边界条件")
        assert len(triggered) == 0
    
    def test_get_verification_requirements(self):
        """测试获取验证要求"""
        table = AntiRationalizationTable()
        
        requirements = table.get_verification_requirements("看起来没问题")
        assert len(requirements) > 0
        assert any("测试" in req or "证据" in req for req in requirements)
    
    def test_add_custom_rule(self):
        """测试添加自定义规则"""
        table = AntiRationalizationTable()
        initial_count = len(table.get_all_rules())
        
        table.add_custom_rule(
            pattern="这个只是小问题",
            description="低估问题严重性",
            counter_argument="小问题可能累积成大问题",
            verification_required="提供问题严重性评估报告",
            category="custom"
        )
        
        rules = table.get_all_rules()
        assert len(rules) == initial_count + 1
        assert any(r["pattern"] == "这个只是小问题" for r in rules)
    
    def test_generate_reflection_prompt_with_trigger(self):
        """测试生成包含触发的反思提示词"""
        table = AntiRationalizationTable()
        
        prompt = table.generate_reflection_prompt(
            task="实现用户登录功能",
            result="看起来没问题，应该能工作"
        )
        
        assert "反合理化" in prompt or "错误推理" in prompt
        assert "看起来没问题" in prompt
        assert "应该能工作" in prompt
    
    def test_generate_reflection_prompt_without_trigger(self):
        """测试生成无触发的反思提示词"""
        table = AntiRationalizationTable()
        
        prompt = table.generate_reflection_prompt(
            task="修复 bug #123",
            result="已添加单元测试，测试覆盖率 95%，所有测试通过"
        )
        
        assert "反思" in prompt
        # 应该不包含错误模式警告
        assert "检测到以下可能的错误推理模式" not in prompt


class TestToolResultValidation:
    """ToolResult 强制验证测试"""
    
    def test_success_result_requires_evidence(self):
        """测试成功结果需要验证证据"""
        result = ToolResult.success_result(data={"output": "test"})
        
        validation_error = result.validate()
        assert validation_error is not None
        assert "evidence" in validation_error
    
    def test_success_result_with_evidence(self):
        """测试成功结果带验证证据"""
        result = ToolResult.success_result(
            data={"output": "test"},
            evidence={
                "test_passed": True,
                "coverage": 95.0,
                "test_output": "All tests passed"
            }
        )
        
        validation_error = result.validate()
        assert validation_error is None
    
    def test_error_result_requires_error_message(self):
        """测试失败结果需要错误信息"""
        result = ToolResult(success=False, data=None)
        
        validation_error = result.validate()
        assert validation_error is not None
        assert "error" in validation_error
    
    def test_error_result_with_message(self):
        """测试失败结果带错误信息"""
        result = ToolResult.error_result(error="连接超时")
        
        validation_error = result.validate()
        assert validation_error is None
    
    def test_anti_rationalization_check_triggered(self):
        """测试反合理化检查触发"""
        result = ToolResult(
            success=True,
            data={"output": "test"},
            evidence={"test_output": "passed"},
            anti_rationalization_check={
                "triggered_patterns": ["看起来没问题"]
            }
        )
        
        validation_error = result.validate()
        assert validation_error is not None
        assert "反合理化模式" in validation_error
    
    def test_anti_rationalization_check_clean(self):
        """测试反理化检查通过"""
        result = ToolResult(
            success=True,
            data={"output": "test"},
            evidence={"test_output": "passed"},
            anti_rationalization_check={
                "triggered_patterns": []
            }
        )
        
        validation_error = result.validate()
        assert validation_error is None
    
    def test_evidence_field_types(self):
        """测试 evidence 字段支持多种类型"""
        # 测试带证据的结果
        evidence = {
            "test_cases": ["test_1", "test_2"],
            "coverage_percent": 95.0,
            "screenshots": ["/path/to/screenshot.png"],
            "benchmark_results": {"time_ms": 120}
        }
        
        result = ToolResult.success_result(
            data={"result": "success"},
            evidence=evidence
        )
        
        assert result.evidence == evidence
        assert result.validate() is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])