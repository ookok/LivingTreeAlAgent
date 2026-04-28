"""
测试工作区管理器和智能体主动反馈功能
"""

import pytest
from client.src.business.workspace_manager import WorkspaceManager
from client.src.business.hermes_agent.proactive_feedback_agent import (
    ProactiveFeedbackAgent,
    FeedbackType,
    FeedbackPriority
)


class TestWorkspaceManager:
    """工作区管理器测试"""
    
    def test_singleton(self):
        """测试单例模式"""
        wm1 = WorkspaceManager.get_instance()
        wm2 = WorkspaceManager.get_instance()
        assert wm1 is wm2
    
    def test_create_workspace(self):
        """测试创建工作区"""
        wm = WorkspaceManager.get_instance()
        workspace = wm.create_workspace(
            name="测试工作区",
            description="测试描述",
            model_config={"model": "test-model"}
        )
        
        assert workspace is not None
        assert workspace.name == "测试工作区"
        assert workspace.config.model_config["model"] == "test-model"
    
    def test_switch_workspace(self):
        """测试切换工作区"""
        wm = WorkspaceManager.get_instance()
        workspace = wm.create_workspace(name="切换测试")
        
        result = wm.switch_workspace(workspace.workspace_id)
        assert result is True
        
        active = wm.get_active_workspace()
        assert active.workspace_id == workspace.workspace_id
    
    def test_get_workspace_config(self):
        """测试获取工作区配置"""
        wm = WorkspaceManager.get_instance()
        model_config = wm.get_workspace_model_config()
        tools_config = wm.get_workspace_tools_config()
        skills_config = wm.get_workspace_skills_config()
        
        assert isinstance(model_config, dict)
        assert isinstance(tools_config, dict)
        assert isinstance(skills_config, dict)


class TestProactiveFeedbackAgent:
    """智能体主动反馈测试"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """在每个测试前重置状态"""
        fa = ProactiveFeedbackAgent.get_instance()
        fa._feedbacks = []
        fa._comments = []
    
    def test_singleton(self):
        """测试单例模式"""
        fa1 = ProactiveFeedbackAgent.get_instance()
        fa2 = ProactiveFeedbackAgent.get_instance()
        assert fa1 is fa2
    
    def test_report_issue(self):
        """测试报告问题"""
        fa = ProactiveFeedbackAgent.get_instance()
        feedback = fa.report_issue(
            agent_id="test-agent",
            title="测试问题",
            message="测试问题详情",
            priority=FeedbackPriority.HIGH
        )
        
        assert feedback.type == FeedbackType.ERROR
        assert feedback.priority == FeedbackPriority.HIGH
        assert feedback.title == "测试问题"
    
    def test_suggest_improvement(self):
        """测试建议改进"""
        fa = ProactiveFeedbackAgent.get_instance()
        feedback = fa.suggest_improvement(
            agent_id="test-agent",
            title="测试建议",
            message="测试建议详情"
        )
        
        assert feedback.type == FeedbackType.SUGGESTION
    
    def test_add_comment(self):
        """测试添加评论"""
        fa = ProactiveFeedbackAgent.get_instance()
        comment = fa.add_comment(
            agent_id="test-agent",
            content="测试评论内容"
        )
        
        assert comment.content == "测试评论内容"
        assert comment.likes == 0
    
    def test_like_comment(self):
        """测试点赞评论"""
        fa = ProactiveFeedbackAgent.get_instance()
        comment = fa.add_comment(agent_id="test-agent", content="点赞测试")
        
        result = fa.like_comment(comment.comment_id)
        assert result is True
        
        assert comment.likes == 1
    
    def test_resolve_feedback(self):
        """测试标记反馈已解决"""
        fa = ProactiveFeedbackAgent.get_instance()
        feedback = fa.report_issue(
            agent_id="test-agent",
            title="待解决问题",
            message="测试"
        )
        
        result = fa.resolve_feedback(feedback.feedback_id)
        assert result is True
        
        assert feedback.resolved is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])