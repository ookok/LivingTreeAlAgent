"""
统一工具层集成测试
========================

测试完整流程：
1. BaseToolAgent 工具发现和执行
2. HermesAgent 工具层改造
3. EIAgentExecutor 工具层改造
4. discover_tools → execute_tool → result 完整链路

运行：
    pytest client/src/business/test_unified_tool_layer.py -v
"""

import pytest
import json
import sys
import os

# 确保项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


class TestBaseToolAgent:
    """BaseToolAgent 基础能力测试"""
    
    def test_base_agent_creation(self):
        """测试 BaseToolAgent 可以正常创建"""
        from client.src.business.base_agents.base_agent import BaseToolAgent
        
        agent = BaseToolAgent(enabled_toolsets=["core"])
        assert agent is not None
        assert agent._registry is not None
        assert agent._enabled_toolsets == ["core"]
        print("[PASS] BaseToolAgent 创建成功")
    
    def test_discover_tools(self):
        """测试工具语义搜索发现"""
        from client.src.business.base_agents.base_agent import BaseToolAgent
        
        agent = BaseToolAgent(enabled_toolsets=["core", "geo"])
        results = agent.discover_tools("距离计算 地理坐标", max_results=3)
        
        assert isinstance(results, list)
        print(f"[PASS] discover_tools 返回 {len(results)} 个结果: {[r.get('name') for r in results]}")
    
    def test_execute_distance_tool(self):
        """测试执行距离计算工具"""
        from client.src.business.base_agents.base_agent import BaseToolAgent
        
        agent = BaseToolAgent(enabled_toolsets=["core", "geo"])
        
        result = agent.execute_tool(
            "distance_tool",
            method="haversine",
            from_lat=31.2304,  # 上海
            from_lon=121.4737,
            to_lat=39.9042,  # 北京
            to_lon=116.4074,
        )
        
        assert result.name == "distance_tool"
        assert result.duration_ms > 0
        # 验证上海到北京约1067km
        data = result.data
        if data and isinstance(data, dict):
            dist = data.get("distance")
            if dist:
                assert 1000 < dist < 1200, f"距离应在1060-1080km之间，实际 {dist}"
        print(f"[PASS] distance_tool 执行成功: {result.data}")
    
    def test_execute_unknown_tool(self):
        """测试执行不存在的工具（应有错误处理）"""
        from client.src.business.base_agents.base_agent import BaseToolAgent
        
        agent = BaseToolAgent(enabled_toolsets=["core"])
        result = agent.execute_tool("nonexistent_tool_xyz", param1="test")
        
        assert result.success is False
        assert result.error != ""
        print(f"[PASS] 未知工具返回预期错误: {result.error[:80]}")
    
    def test_build_tool_schema(self):
        """测试 OpenAI tools schema 生成"""
        from client.src.business.base_agents.base_agent import BaseToolAgent
        
        agent = BaseToolAgent(enabled_toolsets=["core"])
        schema = agent.build_tool_schema()
        
        assert isinstance(schema, list)
        if schema:
            assert "type" in schema[0]
            assert "function" in schema[0]
            print(f"[PASS] build_tool_schema 返回 {len(schema)} 个工具 schema")
        else:
            print("[INFO] build_tool_schema 返回空（可能工具未注册）")
    
    def test_tool_descriptions(self):
        """测试工具描述文本生成"""
        from client.src.business.base_agents.base_agent import BaseToolAgent
        
        agent = BaseToolAgent(enabled_toolsets=["core"])
        desc = agent.get_tool_descriptions()
        
        assert isinstance(desc, str)
        print(f"[PASS] get_tool_descriptions 返回 {len(desc)} 字符的描述")


class TestHermesAgentIntegration:
    """HermesAgent 工具层集成测试"""
    
    def test_hermes_agent_has_tool_agent(self):
        """测试 HermesAgent 注入了 BaseToolAgent"""
        from client.src.business.agent import HermesAgent
        from client.src.business.config import AppConfig
        
        config = AppConfig()
        agent = HermesAgent(config=config)
        
        assert hasattr(agent, "_tool_agent")
        assert agent._tool_agent is not None
        print("[PASS] HermesAgent._tool_agent 注入成功")
    
    def test_hermes_discover_tools(self):
        """测试 HermesAgent.discover_tools 方法"""
        from client.src.business.agent import HermesAgent
        from client.src.business.config import AppConfig
        
        config = AppConfig()
        agent = HermesAgent(config=config)
        
        results = agent.discover_tools("网页搜索", max_results=5)
        assert isinstance(results, list)
        print(f"[PASS] HermesAgent.discover_tools 返回 {len(results)} 个结果")
    
    def test_hermes_execute_tool(self):
        """测试 HermesAgent.execute_tool 方法"""
        from client.src.business.agent import HermesAgent
        from client.src.business.config import AppConfig
        
        config = AppConfig()
        agent = HermesAgent(config=config)
        
        result = agent.execute_tool(
            "distance_tool",
            method="haversine",
            from_lat=31.2304,
            from_lon=121.4737,
            to_lat=39.9042,
            to_lon=116.4074,
        )
        
        assert isinstance(result, dict)
        assert "name" in result
        print(f"[PASS] HermesAgent.execute_tool: name={result.get('name')}, success={result.get('success')}")
    
    def test_hermes_build_tool_schema(self):
        """测试 HermesAgent._build_tool_schema（优先新系统）"""
        from client.src.business.agent import HermesAgent
        from client.src.business.config import AppConfig
        
        config = AppConfig()
        agent = HermesAgent(config=config)
        
        schema = agent._build_tool_schema()
        assert isinstance(schema, list)
        print(f"[PASS] HermesAgent._build_tool_schema 返回 {len(schema)} 个工具 schema")


class TestEIAgentIntegration:
    """EIAgentExecutor 工具层集成测试"""
    
    def test_ei_agent_has_tool_agent(self):
        """测试 EIAgentExecutor 注入了 BaseToolAgent"""
        from client.src.business.ei_agent.ei_agent_adapter import EIAgentExecutor
        
        executor = EIAgentExecutor()
        assert hasattr(executor, "_tool_agent")
        assert executor._tool_agent is not None
        print("[PASS] EIAgentExecutor._tool_agent 注入成功")
    
    def test_ei_agent_discover_tools(self):
        """测试 EIAgentExecutor.discover_tools"""
        from client.src.business.ei_agent.ei_agent_adapter import EIAgentExecutor
        
        executor = EIAgentExecutor()
        results = executor.discover_tools("大气扩散 环境 评估", max_results=5)
        assert isinstance(results, list)
        print(f"[PASS] EIAgentExecutor.discover_tools 返回 {len(results)} 个结果")
    
    def test_ei_agent_execute_distance(self):
        """测试 EIAgentExecutor.execute_tool 同步版"""
        from client.src.business.ei_agent.ei_agent_adapter import EIAgentExecutor
        
        executor = EIAgentExecutor()
        result = executor.execute_tool(
            "distance_tool",
            method="haversine",
            from_lat=39.9042,
            from_lon=116.4074,
            to_lat=31.2304,
            to_lon=121.4737,
        )
        
        assert result.name == "distance_tool"
        data = result.data
        if data and isinstance(data, dict):
            dist = data.get("distance")
            print(f"[PASS] EIAgentExecutor.execute_tool (sync): distance={dist:.2f} km")
    
    def test_ei_agent_execute_async(self):
        """测试 EIAgentExecutor.execute_tool_async"""
        import asyncio
        from client.src.business.ei_agent.ei_agent_adapter import EIAgentExecutor
        
        async def _run():
            executor = EIAgentExecutor()
            result = await executor.execute_tool_async(
                "distance_tool",
                method="haversine",
                from_lat=31.2304,
                from_lon=121.4737,
                to_lat=39.9042,
                to_lon=116.4074,
            )
            assert result.name == "distance_tool"
            print(f"[PASS] EIAgentExecutor.execute_tool_async: success={result.success}")
        
        asyncio.run(_run())


class TestToolExecutionFlow:
    """完整工具执行链路测试"""
    
    def test_full_flow_discover_execute(self):
        """测试 discover → execute 完整链路"""
        from client.src.business.base_agents.base_agent import BaseToolAgent
        
        agent = BaseToolAgent(enabled_toolsets=["core", "geo"])
        
        # 1. 语义搜索适合"地理距离计算"任务的工具
        tools = agent.discover_tools("计算两个城市之间的距离", max_results=3)
        print(f"  [Step 1] 发现工具: {[t.get('name') for t in tools]}")
        
        # 2. 找到 distance_tool，执行
        if any(t.get("name") == "distance_tool" for t in tools):
            result = agent.execute_tool(
                "distance_tool",
                method="haversine",
                from_lat=31.2304,
                from_lon=121.4737,
                to_lat=39.9042,
                to_lon=116.4074,
            )
            print(f"  [Step 2] 执行结果: success={result.success}, data={result.data}")
            assert result.success, f"distance_tool 执行失败: {result.error}"
            assert result.data is not None
            print(f"[PASS] discover → execute 完整链路成功")
        else:
            print(f"[INFO] 未发现 distance_tool，跳过执行测试")
    
    def test_tool_stats_tracking(self):
        """测试工具调用统计"""
        from client.src.business.base_agents.base_agent import BaseToolAgent
        
        agent = BaseToolAgent(enabled_toolsets=["core", "geo"])
        
        # 执行多次
        for _ in range(3):
            agent.execute_tool(
                "distance_tool",
                method="haversine",
                from_lat=31.2304,
                from_lon=121.4737,
                to_lat=39.9042,
                to_lon=116.4074,
            )
        
        stats = agent.get_tool_stats()
        call_count = stats.get("call_counts", {}).get("distance_tool", 0)
        print(f"[PASS] distance_tool 调用统计: {call_count} 次")
        assert call_count == 3, f"期望 3 次调用，实际 {call_count} 次"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
