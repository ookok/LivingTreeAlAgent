"""
测试智能体原生接口和共享知识/记忆层
"""

import sys
import os
import asyncio

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'client', 'src'))

from business.tools.base_tool import BaseTool, AgentCallResult, ToolNodeType
from business.shared_memory_manager import SharedMemoryManager, MemoryType


class TestTool(BaseTool):
    """测试工具"""
    
    @property
    def name(self) -> str:
        return "test_tool"
    
    @property
    def description(self) -> str:
        return "测试工具描述"
    
    @property
    def category(self) -> str:
        return "test"
    
    @property
    def parameters(self) -> dict:
        return {"input": "输入参数"}
    
    def _get_required_parameters(self) -> list:
        """定义必需参数"""
        return ["input"]
    
    async def execute(self, **kwargs):
        input_value = kwargs.get("input", "")
        return {"processed": input_value.upper()}


async def run_tests():
    """运行所有测试"""
    # 测试智能体原生接口
    print("测试智能体原生接口...")

    # 创建工具实例
    tool = TestTool()

    # 测试智能体调用接口
    result = await tool.agent_call(input="hello")
    assert result.success is True
    assert result.data == {"processed": "HELLO"}
    print("✓ 智能体调用接口工作正常")

    # 测试参数验证
    result = await tool.agent_call()  # 缺少参数
    assert result.success is False
    assert "缺少必需参数" in result.error
    print("✓ 参数验证工作正常")

    # 测试结构化 JSON 输出
    json_result = result.to_json()
    assert "success" in json_result
    assert "error" in json_result
    print("✓ 结构化 JSON 输出工作正常")

    # 测试 SKILL.md 生成
    skill_md = tool.get_skill_md()
    assert "# test_tool" in skill_md
    assert "## 描述" in skill_md
    print("✓ SKILL.md 生成工作正常")

    # 测试 agent_info
    agent_info = tool.agent_info
    assert agent_info["name"] == "test_tool"
    assert "call_format" in agent_info
    assert "examples" in agent_info
    print("✓ agent_info 工作正常")

    # 测试共享知识/记忆层
    print("\n测试共享知识/记忆层...")

    # 获取共享记忆管理器实例
    memory_manager = SharedMemoryManager.get_instance()

    # 创建用户画像
    profile = memory_manager.create_user_profile("user_001", "测试用户", "test@example.com")
    assert profile.user_id == "user_001"
    assert profile.name == "测试用户"
    print("✓ 创建用户画像成功")

    # 更新用户画像
    memory_manager.add_user_skill("user_001", "Python")
    memory_manager.add_user_preference("user_001", "theme", "dark")
    updated_profile = memory_manager.get_user_profile("user_001")
    assert "Python" in updated_profile.skills
    assert updated_profile.preferences["theme"] == "dark"
    print("✓ 更新用户画像成功")

    # 创建项目上下文
    project = memory_manager.create_project("project_001", "测试项目", "项目描述")
    assert project.project_id == "project_001"
    print("✓ 创建项目上下文成功")

    # 添加项目工具
    memory_manager.add_project_tool("project_001", "test_tool")
    updated_project = memory_manager.get_project("project_001")
    assert "test_tool" in updated_project.tools
    print("✓ 添加项目工具成功")

    # 设置和获取记忆
    memory_manager.set_memory("test_key", "test_value", MemoryType.TEMPORARY)
    value = memory_manager.get_memory("test_key")
    assert value == "test_value"
    print("✓ 设置和获取记忆成功")

    # 搜索记忆
    results = memory_manager.search_memories("test")
    assert len(results) > 0
    print("✓ 搜索记忆成功")

    # 记录工具使用
    memory_manager.record_tool_usage(
        tool_name="test_tool",
        user_id="user_001",
        project_id="project_001",
        parameters={"input": "test"},
        result={"success": True},
        success=True,
        execution_time=0.5
    )
    usage_history = memory_manager.get_tool_usage_history(user_id="user_001")
    assert len(usage_history) > 0
    print("✓ 工具使用记录成功")

    # 获取用户上下文
    user_context = memory_manager.get_user_context("user_001")
    assert "user_id" in user_context
    assert "profile" in user_context
    print("✓ 获取用户上下文成功")

    print("\n🎉 所有测试通过!")


if __name__ == "__main__":
    asyncio.run(run_tests())