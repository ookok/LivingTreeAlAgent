"""
Agent 框架测试套件

测试 AgentAdapter 层和 AgentWorkflow 框架
"""

import pytest
import asyncio
from client.src.business.agent_adapter import (
    create_agent_adapter, 
    AgentConfig, 
    get_supported_agents
)
# 导入适配器模块以注册它们
from client.src.business.agent_adapter import openai_adapter, qwen_adapter, local_adapter
from client.src.business.agent_workflow import (
    WorkflowBuilder, 
    execute_workflow, 
    register_workflow
)
from client.src.business.agent_workflow.automation_workflows import (
    register_all_automation_workflows,
    AutoDocumentGenerator,
    AutoTestGenerator
)


class TestAgentAdapter:
    """Agent Adapter 测试"""
    
    def test_supported_agents(self):
        """测试支持的 Agent 类型"""
        agents = get_supported_agents()
        assert "openai" in agents
        assert "qwen" in agents
        assert "local" in agents
    
    def test_create_openai_adapter(self):
        """测试创建 OpenAI 适配器"""
        config = AgentConfig(
            agent_type="openai",
            api_key="test-api-key",
            model_name="gpt-4o"
        )
        adapter = create_agent_adapter(config)
        assert adapter is not None
        assert adapter.config.agent_type == "openai"
    
    def test_create_qwen_adapter(self):
        """测试创建 Qwen 适配器"""
        config = AgentConfig(
            agent_type="qwen",
            api_key="test-api-key",
            model_name="qwen-max"
        )
        adapter = create_agent_adapter(config)
        assert adapter is not None
        assert adapter.config.agent_type == "qwen"
    
    def test_create_local_adapter(self):
        """测试创建本地模型适配器"""
        config = AgentConfig(
            agent_type="local",
            model_name="Qwen/Qwen2.5-7B-Instruct"
        )
        adapter = create_agent_adapter(config)
        assert adapter is not None
        assert adapter.config.agent_type == "local"
    
    def test_unknown_agent_type(self):
        """测试未知 Agent 类型"""
        config = AgentConfig(agent_type="unknown")
        with pytest.raises(ValueError):
            create_agent_adapter(config)


class TestWorkflowBuilder:
    """工作流构建器测试"""
    
    def test_build_sequential_workflow(self):
        """测试构建顺序工作流"""
        builder = WorkflowBuilder("test_sequential", "sequential")
        
        def action1(vars):
            vars["step1"] = "done"
            return vars
        
        def action2(vars):
            vars["step2"] = "done"
            return vars
        
        workflow = builder.start()\
            .action("step1", action1)\
            .action("step2", action2)\
            .end()\
            .build()
        
        assert workflow.workflow_id == "test_sequential"
        assert workflow.start_node == "start"
        assert "end" in workflow.end_nodes
    
    def test_build_decision_workflow(self):
        """测试构建决策工作流"""
        builder = WorkflowBuilder("test_decision", "decision")
        
        def check_condition(vars):
            return vars.get("value", 0) > 10
        
        def action_if(vars):
            vars["result"] = "if"
            return vars
        
        def action_else(vars):
            vars["result"] = "else"
            return vars
        
        workflow = builder.start()\
            .decision("check", check_condition)\
            .then("if_branch", action_if)\
            .else_("else_branch", action_else)\
            .end()\
            .build()
        
        assert workflow.workflow_id == "test_decision"
    
    def test_build_parallel_workflow(self):
        """测试构建并行工作流"""
        builder = WorkflowBuilder("test_parallel", "parallel")
        
        def branch1(vars):
            vars["branch1"] = "done"
            return vars
        
        def branch2(vars):
            vars["branch2"] = "done"
            return vars
        
        workflow = builder.start()\
            .action("branch1", branch1)\
            .action("branch2", branch2)\
            .end()\
            .build()
        
        assert workflow.workflow_id == "test_parallel"


class TestWorkflowExecution:
    """工作流执行测试"""
    
    @pytest.mark.asyncio
    async def test_execute_sequential_workflow(self):
        """测试执行顺序工作流"""
        builder = WorkflowBuilder("test_seq_exec", "sequential")
        
        def action1(vars):
            vars["count"] = vars.get("count", 0) + 1
            return vars
        
        def action2(vars):
            vars["count"] = vars.get("count", 0) + 1
            return vars
        
        workflow = builder.start()\
            .action("step1", action1)\
            .action("step2", action2)\
            .end()\
            .build()
        
        register_workflow(workflow)
        
        result = await execute_workflow("test_seq_exec", {"count": 0})
        
        assert result.success
        assert result.output["count"] == 2
    
    @pytest.mark.asyncio
    async def test_execute_decision_workflow_true(self):
        """测试执行决策工作流（条件为真）"""
        builder = WorkflowBuilder("test_dec_exec", "decision")
        
        def check(vars):
            return vars.get("value", 0) > 5
        
        def action_if(vars):
            vars["result"] = "greater"
            return vars
        
        def action_else(vars):
            vars["result"] = "less_or_equal"
            return vars
        
        workflow = builder.start()\
            .decision("check", check)\
            .then("if_branch", action_if)\
            .else_("else_branch", action_else)\
            .end()\
            .build()
        
        register_workflow(workflow)
        
        result = await execute_workflow("test_dec_exec", {"value": 10})
        
        assert result.success
        assert result.output["result"] == "greater"
    
    @pytest.mark.asyncio
    async def test_execute_decision_workflow_false(self):
        """测试执行决策工作流（条件为假）"""
        builder = WorkflowBuilder("test_dec_exec2", "decision")
        
        def check(vars):
            return vars.get("value", 0) > 5
        
        def action_if(vars):
            vars["result"] = "greater"
            return vars
        
        def action_else(vars):
            vars["result"] = "less_or_equal"
            return vars
        
        workflow = builder.start()\
            .decision("check", check)\
            .then("if_branch", action_if)\
            .else_("else_branch", action_else)\
            .end()\
            .build()
        
        register_workflow(workflow)
        
        result = await execute_workflow("test_dec_exec2", {"value": 3})
        
        assert result.success
        assert result.output["result"] == "less_or_equal"


class TestAutomationWorkflows:
    """自动化工作流测试"""
    
    @pytest.mark.asyncio
    async def test_auto_doc_workflow(self):
        """测试自动文档生成工作流"""
        register_all_automation_workflows()
        
        test_code = """def add(a: int, b: int) -> int:
    \"\"\"加法函数\"\"\"
    return a + b
"""
        
        result = await execute_workflow("auto_doc_gen", {
            "code": test_code,
            "output_path": "test_docs.md"
        })
        
        assert result.success
        assert "documentation" in result.output
    
    @pytest.mark.asyncio
    async def test_auto_test_workflow(self):
        """测试自动测试生成工作流"""
        register_all_automation_workflows()
        
        test_code = """def multiply(a: int, b: int) -> int:
    \"\"\"乘法函数\"\"\"
    return a * b
"""
        
        result = await execute_workflow("auto_test_gen", {
            "code": test_code,
            "requirements": "测试乘法函数的各种输入情况"
        })
        
        assert result.success
        assert "test_code" in result.output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
