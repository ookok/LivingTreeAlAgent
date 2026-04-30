"""
HermesAgent Enhancements - 三个核心能力的集成

将 ProactiveDiscoveryAgent、ToolChainOrchestrator、SelfReflectionEngine
集成到 HermesAgent 主流程。

使用方法：
    from business.hermes_agent_enhancements import enhance_hermes_agent
    enhance_hermes_agent(agent)
"""

import asyncio
import json
import threading
from typing import Any, Dict, List, Optional

from business.hermes_agent.proactive_discovery_agent import ProactiveDiscoveryAgent
from business.tool_chain_orchestrator import ToolChainOrchestrator
from business.self_evolution.self_reflection_engine import SelfReflectionEngine
from business.self_evolution.tool_self_repairer import ToolSelfRepairer


def enhance_hermes_agent(agent):
    """
    增强 HermesAgent，集成三个核心能力。
    
    Args:
        agent: HermesAgent 实例
    """
    # 1. 初始化主动工具发现
    agent._proactive_agent = ProactiveDiscoveryAgent(
        enabled_toolsets=agent.enabled_toolsets,
        auto_install=True,
    )
    
    # 2. 初始化工具链编排器
    agent._tool_chain_orchestrator = ToolChainOrchestrator(
        max_parallel_steps=3,
        default_max_retries=3,
    )
    
    # 3. 初始化自我反思引擎
    agent._reflection_engine = SelfReflectionEngine()
    agent._tool_repairer = ToolSelfRepairer()
    
    # 4. 替换 _execute_tools 方法
    agent._execute_tools_original = agent._execute_tools
    agent._execute_tools = lambda tool_calls: _enhanced_execute_tools(agent, tool_calls)
    
    # 5. 增强 send_message 方法
    agent._send_message_original = agent.send_message
    agent.send_message = lambda text: _enhanced_send_message(agent, text)
    
    print("[HermesAgent] 已集成三个核心能力：主动工具发现、工具链编排、自我反思")


def _enhanced_send_message(agent, text: str):
    """
    增强版 send_message：
    1. 使用 ProactiveDiscoveryAgent 主动发现缺失工具
    2. 复杂任务使用 ToolChainOrchestrator
    3. 工具执行后使用 SelfReflectionEngine 反思
    """
    # 1. 主动工具发现：分析任务并安装缺失工具
    try:
        # 在新线程中运行异步代码
        def discover_tools():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    agent._proactive_agent.execute_task(text)
                )
                print(f"[增强] 主动工具发现完成: {result.get('status')}")
            finally:
                loop.close()
        
        thread = threading.Thread(target=discover_tools, daemon=True)
        thread.start()
        thread.join(timeout=30)  # 最多等待30秒
    except Exception as e:
        print(f"[增强] 主动工具发现失败: {e}")
    
    # 2. 调用原始的 send_message
    return agent._send_message_original(text)


def _enhanced_execute_tools(agent, tool_calls: list[dict]) -> list[dict]:
    """
    增强版 _execute_tools：
    1. 执行工具
    2. 使用 SelfReflectionEngine 反思执行结果
    3. 如果失败，使用 ToolSelfRepairer 修复
    """
    results = []
    
    for tc in tool_calls:
        func = tc.get("function", {})
        name = func.get("name", "")
        args_str = func.get("arguments", "{}")
        
        # 解析参数
        try:
            args = json.loads(args_str) if isinstance(args_str, str) else args_str
        except Exception:
            args = {}
        
        # 执行工具
        result = agent.dispatcher.dispatch(name, args)
        success = result.get("success", False)
        result_text = json.dumps(result, ensure_ascii=False, indent=2)
        
        # 增强：使用 SelfReflectionEngine 反思
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                reflection = loop.run_until_complete(
                    agent._reflection_engine.reflect_on_tool_execution(
                        tool_name=name,
                        tool_input=args,
                        tool_output=result.get("data"),
                        error=result.get("error") if not success else None,
                    )
                )
                
                # 如果反思中触发了自动修复
                if reflection.get("auto_repair_attempted"):
                    repair_result = reflection.get("auto_repair_result", {})
                    print(f"[增强] 工具自动修复: {name}, 结果: {repair_result.get('message')}")
                    
                    # 如果修复成功，重新执行工具
                    if repair_result.get("success"):
                        print(f"[增强] 重新执行工具: {name}")
                        result = agent.dispatcher.dispatch(name, args)
            finally:
                loop.close()
        except Exception as e:
            print(f"[增强] 反思工具执行失败: {e}")
        
        results.append({
            "tool_name": name,
            "success": success,
            "result": result_text,
            "error": result.get("error", ""),
        })
    
    return results


def execute_complex_task(agent, task: str) -> Dict[str, Any]:
    """
    执行复杂任务（使用 ToolChainOrchestrator）。
    
    Args:
        agent: HermesAgent 实例
        task: 任务描述
        
    Returns:
        执行结果
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                agent._tool_chain_orchestrator.execute_chain(task)
            )
            return {
                "success": True,
                "result": result,
            }
        finally:
            loop.close()
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


# 需要在文件顶部添加 json 导入
import json
