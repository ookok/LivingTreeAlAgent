"""
优化引导器测试
==============

测试一键启用所有优化功能：
1. RTK 集成测试
2. Code Review Graph 测试
3. Context Mode 测试

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import pytest
import asyncio

# 导入优化组件
from client.src.business import (
    enable_all_optimizations,
    get_optimization_bootstrapper,
    create_code_review_graph,
    create_context_mode_manager,
    ContextPreprocessor,
)


class TestOptimizationBootstrapper:
    """优化引导器测试"""
    
    def test_enable_all_optimizations(self):
        """测试一键启用所有优化"""
        result = enable_all_optimizations()
        
        assert result["success"] is True
        assert "message" in result
        assert "modules" in result
        
        print(f"启用结果: {result['message']}")
        for module in result["modules"]:
            print(f"  - {module['name']}: {'✓' if module['success'] else '✗'} {module.get('message', '')}")
    
    def test_bootstrapper_instance(self):
        """测试获取优化引导器实例"""
        bootstrapper = get_optimization_bootstrapper()
        
        assert bootstrapper is not None
        assert bootstrapper.is_optimization_enabled() is True
    
    def test_get_full_report(self):
        """测试获取完整报告"""
        bootstrapper = get_optimization_bootstrapper()
        report = bootstrapper.get_full_report()
        
        assert "optimization_enabled" in report
        assert "modules" in report
        assert "summary" in report
        
        print("\n优化报告:")
        print(f"  优化已启用: {report['optimization_enabled']}")
        print(f"  已启用模块: {report['summary']['enabled_modules']}")
        print(f"  缓存命中率: {report['summary']['cache_hit_rate']}")
        print(f"  压缩率: {report['summary']['compression_ratio']}")


class TestCodeReviewGraph:
    """Code Review Graph 测试"""
    
    def test_create_graph(self):
        """测试创建代码审查图谱"""
        graph = create_code_review_graph()
        
        assert graph is not None
    
    @pytest.mark.asyncio
    async def test_analyze_code(self):
        """测试分析代码"""
        code = """
def calculate_sum(a, b):
    result = a + b
    return result

def process_data(data):
    total = 0
    for item in data:
        total += item
    return total
"""
        
        graph = create_code_review_graph()
        result = await graph.analyze(code, "test.py")
        
        assert "file_path" in result
        assert "issues" in result
        assert "complexity" in result
        assert "overall_score" in result
        assert "summary" in result
        
        print(f"\n代码分析结果:")
        print(f"  文件: {result['file_path']}")
        print(f"  综合评分: {result['overall_score']:.1f}")
        print(f"  问题数量: {result['summary']['total_issues']}")
        print(f"  复杂度级别: {result['summary']['complexity_level']}")


class TestContextModeManager:
    """Context Mode 测试"""
    
    def test_create_manager(self):
        """测试创建上下文模式管理器"""
        manager = create_context_mode_manager()
        
        assert manager is not None
    
    def test_get_suggestion(self):
        """测试获取上下文建议"""
        manager = create_context_mode_manager()
        suggestion = manager.get_suggestion("请帮我解释这段代码")
        
        assert "intent" in suggestion
        assert "suggested_sources" in suggestion
        assert "excluded_contexts" in suggestion
        assert "explanation" in suggestion
        
        print(f"\n上下文建议:")
        print(f"  识别意图: {suggestion['intent']}")
        print(f"  建议来源: {suggestion['suggested_sources']}")
        print(f"  说明: {suggestion['explanation']}")
    
    def test_set_mode(self):
        """测试设置模式"""
        manager = create_context_mode_manager()
        
        manager.set_mode("automatic")
        assert manager.get_mode().value == "automatic"
        
        manager.set_mode("manual")
        assert manager.get_mode().value == "manual"
        
        manager.set_mode("selective")
        assert manager.get_mode().value == "selective"


class TestRTKIntegration:
    """RTK 集成测试"""
    
    def test_create_preprocessor(self):
        """测试创建上下文预处理器"""
        preprocessor = ContextPreprocessor()
        
        assert preprocessor is not None
    
    def test_process_messages(self):
        """测试处理消息"""
        preprocessor = ContextPreprocessor()
        
        messages = [
            {"role": "system", "content": "你是一个AI助手"},
            {"role": "user", "content": "你好，这是一个测试消息"},
            {"role": "assistant", "content": "您好！我是AI助手，有什么可以帮您的？"},
        ]
        
        processed = preprocessor.process_messages(messages)
        
        assert isinstance(processed, list)
        assert len(processed) > 0
        
        print(f"\nRTK处理结果:")
        print(f"  原始消息数: {len(messages)}")
        print(f"  处理后消息数: {len(processed)}")
        
        stats = preprocessor.get_stats()
        print(f"  压缩率: {stats.compression_ratio:.1f}%")


class TestIntegration:
    """集成测试"""
    
    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """测试完整工作流"""
        # 1. 启用所有优化
        result = enable_all_optimizations()
        assert result["success"] is True
        
        # 2. 获取引导器
        bootstrapper = get_optimization_bootstrapper()
        
        # 3. 使用代码审查
        code = """
def dangerous_function():
    secret = "hardcoded_secret_123"
    exec("print('hello')")
"""
        analysis = await bootstrapper.analyze_code(code, "test.py")
        assert "overall_score" in analysis
        
        # 4. 获取上下文建议
        suggestion = bootstrapper.get_context_suggestion("帮我修复这个bug")
        assert "intent" in suggestion
        
        print("\n完整工作流测试通过！")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])