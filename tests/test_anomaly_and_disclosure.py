"""
测试异常征兆检测和渐进式信息披露功能
"""

import pytest
from client.src.business.self_evolution.anomaly_detector import (
    AnomalyDetector,
    AnomalyType,
    AnomalySeverity,
    MetricSnapshot
)
from client.src.business.hermes_agent.progressive_disclosure import (
    ProgressiveDisclosure,
    DisclosureLevel,
    TaskType,
    DisclosureContext,
    ExpertRole
)


class TestAnomalyDetector:
    """异常征兆检测器测试"""
    
    def test_detect_response_time_spike(self):
        """测试响应时间异常检测"""
        detector = AnomalyDetector()
        
        anomaly_count_before = len(detector.get_anomalies())
        
        # 模拟响应时间超时
        detector.record_metrics(response_time_ms=12000)
        
        anomalies = detector.get_anomalies()
        assert len(anomalies) > anomaly_count_before
        
        # 检查是否检测到响应时间异常
        response_anomalies = [a for a in anomalies if a.type == AnomalyType.RESPONSE_TIME_SPIKE]
        assert len(response_anomalies) > 0
        assert response_anomalies[0].severity == AnomalySeverity.CRITICAL
    
    def test_detect_resource_exhaustion(self):
        """测试资源耗尽检测"""
        detector = AnomalyDetector()
        
        # 模拟高内存使用
        detector.record_metrics(memory_usage_mb=1200)
        
        anomalies = detector.get_anomalies()
        memory_anomalies = [a for a in anomalies if a.type == AnomalyType.RESOURCE_EXHAUSTION]
        assert len(memory_anomalies) > 0
        assert memory_anomalies[0].severity == AnomalySeverity.WARNING
    
    def test_detect_unexpected_output(self):
        """测试意外输出检测"""
        detector = AnomalyDetector()
        
        # 模拟错误输出
        detector.detect_unexpected_output(
            task="获取数据",
            result="Error: Connection refused"
        )
        
        anomalies = detector.get_anomalies()
        unexpected_anomalies = [a for a in anomalies if a.type == AnomalyType.UNEXPECTED_OUTPUT]
        assert len(unexpected_anomalies) > 0
    
    def test_detect_loop(self):
        """测试循环检测"""
        detector = AnomalyDetector()
        
        # 模拟循环任务历史
        task_history = [
            {"task": "相同任务"},
            {"task": "相同任务"},
            {"task": "相同任务"},
            {"task": "相同任务"},
            {"task": "相同任务"},
        ]
        
        result = detector.detect_loop(task_history)
        assert result is True
        
        anomalies = detector.get_anomalies()
        loop_anomalies = [a for a in anomalies if a.type == AnomalyType.LOOP_DETECTION]
        assert len(loop_anomalies) > 0
    
    def test_get_health_report(self):
        """测试获取健康报告"""
        detector = AnomalyDetector()
        
        report = detector.get_health_report()
        
        assert "timestamp" in report
        assert "total_anomalies" in report
        assert "status" in report
        assert report["status"] == "healthy"
    
    def test_suggest_correction(self):
        """测试修正建议"""
        detector = AnomalyDetector()
        
        anomaly = detector.get_anomalies()[0] if detector.get_anomalies() else None
        if anomaly:
            suggestion = detector.suggest_correction(anomaly)
            assert "action" in suggestion
            assert "suggestions" in suggestion
    
    def test_resolve_anomaly(self):
        """测试标记异常已解决"""
        detector = AnomalyDetector()
        detector.record_metrics(response_time_ms=5000)
        
        anomalies = detector.get_unresolved_anomalies()
        assert len(anomalies) > 0
        
        anomaly_id = anomalies[0].anomaly_id
        result = detector.resolve_anomaly(anomaly_id)
        assert result is True
        
        unresolved = detector.get_unresolved_anomalies()
        assert anomaly_id not in [a.anomaly_id for a in unresolved]


class TestProgressiveDisclosure:
    """渐进式信息披露测试"""
    
    def test_get_relevant_roles(self):
        """测试获取相关专家角色"""
        disclosure = ProgressiveDisclosure()
        
        roles = disclosure.get_relevant_roles(TaskType.CODE)
        assert "code_expert" in roles
        
        roles = disclosure.get_relevant_roles(TaskType.TESTING)
        assert "testing_expert" in roles
        
        roles = disclosure.get_relevant_roles(TaskType.DESIGN)
        assert "design_expert" in roles
    
    def test_disclosure_level_progression(self):
        """测试披露级别递进"""
        disclosure = ProgressiveDisclosure()
        
        # 最小披露（低完成度、低参与度、低复杂度）
        context = DisclosureContext(
            task_type=TaskType.CODE,
            current_level=DisclosureLevel.MINIMAL,
            task_completion=0.0,
            user_engagement=0.1,
            complexity=0.1
        )
        result = disclosure.disclose(context)
        assert result["disclosure_level"] == DisclosureLevel.MINIMAL.value
        
        # 完整披露（高完成度、高参与度、高复杂度）
        context = DisclosureContext(
            task_type=TaskType.CODE,
            current_level=DisclosureLevel.FULL,
            task_completion=1.0,
            user_engagement=1.0,
            complexity=1.0
        )
        result = disclosure.disclose(context)
        assert result["disclosure_level"] == DisclosureLevel.FULL.value
    
    def test_disclosure_content(self):
        """测试披露内容"""
        disclosure = ProgressiveDisclosure()
        
        context = DisclosureContext(
            task_type=TaskType.CODE,
            current_level=DisclosureLevel.BASIC,
            task_completion=0.5
        )
        result = disclosure.disclose(context)
        
        assert "expert_roles" in result
        assert len(result["expert_roles"]) > 0
        
        # 检查角色描述不为空
        for role in result["expert_roles"]:
            assert role["name"]
            assert role["description"]
    
    def test_estimate_token_savings(self):
        """测试 token 节省估算"""
        disclosure = ProgressiveDisclosure()
        
        context = DisclosureContext(
            task_type=TaskType.CODE,
            current_level=DisclosureLevel.MINIMAL,
            task_completion=0.1
        )
        
        savings = disclosure.estimate_token_savings(context)
        
        assert "savings_percent" in savings
        assert "estimated_token_savings" in savings
        assert savings["estimated_token_savings"] >= 0
    
    def test_suggest_next_disclosure(self):
        """测试建议下一个披露级别"""
        disclosure = ProgressiveDisclosure()
        
        level = disclosure.suggest_next_disclosure(0.1)
        assert level == DisclosureLevel.MINIMAL
        
        level = disclosure.suggest_next_disclosure(0.3)
        assert level == DisclosureLevel.BASIC
        
        level = disclosure.suggest_next_disclosure(0.6)
        assert level == DisclosureLevel.DETAILED
        
        level = disclosure.suggest_next_disclosure(0.9)
        assert level == DisclosureLevel.FULL
    
    def test_enable_disable_role(self):
        """测试启用/禁用角色"""
        disclosure = ProgressiveDisclosure()
        
        # 禁用角色
        disclosure.disable_role("code_expert")
        roles = disclosure.get_relevant_roles(TaskType.CODE)
        assert "code_expert" not in roles
        
        # 重新启用
        disclosure.enable_role("code_expert")
        roles = disclosure.get_relevant_roles(TaskType.CODE)
        assert "code_expert" in roles
    
    def test_add_custom_role(self):
        """测试添加自定义角色"""
        disclosure = ProgressiveDisclosure()
        
        custom_role = ExpertRole(
            name="安全专家",
            description="精通安全审计",
            skills=["安全审计", "渗透测试"],
            task_types=[TaskType.ANALYSIS],
            disclosure_templates={
                DisclosureLevel.MINIMAL: "安全专家可用",
                DisclosureLevel.FULL: "安全专家：精通安全审计和渗透测试"
            }
        )
        
        disclosure.add_custom_role(custom_role)
        
        roles = disclosure.get_relevant_roles(TaskType.ANALYSIS)
        assert "安全专家" in roles


if __name__ == "__main__":
    pytest.main([__file__, "-v"])