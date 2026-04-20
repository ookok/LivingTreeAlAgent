"""OpenHarness 引擎集成 - Agent Loop 实现"""

import asyncio
from typing import Dict, Any, Optional, List, Callable, AsyncGenerator
from dataclasses import dataclass


@dataclass
class AgentEvent:
    """Agent 事件"""
    type: str  # "thinking", "tool_call", "tool_result", "finish"
    data: Dict[str, Any]
    timestamp: float = 0.0


class OpenHarnessEngine:
    """OpenHarness 引擎 - 实现 Agent Loop"""
    
    def __init__(self):
        """初始化引擎"""
        self.tools = {}
        self.skills = {}
        self.memory = {}
        self.permissions = {}
    
    def register_tool(self, name: str, func: Callable, description: str):
        """注册工具"""
        self.tools[name] = {
            "func": func,
            "description": description
        }
    
    def register_skill(self, name: str, skill: Dict[str, Any]):
        """注册技能"""
        self.skills[name] = skill
    
    async def agent_loop(
        self,
        prompt: str,
        model: Callable,
        max_steps: int = 10
    ) -> AsyncGenerator[AgentEvent, None]:
        """Agent 主循环"""
        step = 0
        context = {"prompt": prompt, "history": []}
        
        while step < max_steps:
            step += 1
            
            # 思考阶段
            yield AgentEvent(
                type="thinking",
                data={"step": step, "context": context}
            )
            
            # 调用模型
            response = await model(context)
            
            # 处理工具调用
            if isinstance(response, dict) and "tool_call" in response:
                tool_call = response["tool_call"]
                tool_name = tool_call["name"]
                tool_args = tool_call.get("args", {})
                
                yield AgentEvent(
                    type="tool_call",
                    data={"tool_name": tool_name, "args": tool_args}
                )
                
                # 执行工具
                if tool_name in self.tools:
                    tool_func = self.tools[tool_name]["func"]
                    try:
                        tool_result = await tool_func(**tool_args)
                        yield AgentEvent(
                            type="tool_result",
                            data={"tool_name": tool_name, "result": tool_result}
                        )
                        context["history"].append({
                            "type": "tool_call",
                            "tool_name": tool_name,
                            "args": tool_args,
                            "result": tool_result
                        })
                    except Exception as e:
                        yield AgentEvent(
                            type="tool_result",
                            data={"tool_name": tool_name, "error": str(e)}
                        )
                        context["history"].append({
                            "type": "tool_call",
                            "tool_name": tool_name,
                            "args": tool_args,
                            "error": str(e)
                        })
                else:
                    yield AgentEvent(
                        type="tool_result",
                        data={"tool_name": tool_name, "error": "Tool not found"}
                    )
            else:
                # 完成阶段
                yield AgentEvent(
                    type="finish",
                    data={"response": response, "steps": step}
                )
                break
    
    async def run_agent(
        self,
        prompt: str,
        model: Callable,
        max_steps: int = 10
    ) -> Dict[str, Any]:
        """运行 Agent 并返回最终结果"""
        events = []
        async for event in self.agent_loop(prompt, model, max_steps):
            events.append(event)
            if event.type == "finish":
                return {
                    "response": event.data["response"],
                    "steps": event.data["steps"],
                    "events": events
                }
        
        return {
            "response": "Agent stopped due to max steps reached",
            "steps": max_steps,
            "events": events
        }
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """获取可用工具"""
        return [
            {
                "name": name,
                "description": tool["description"]
            }
            for name, tool in self.tools.items()
        ]
    
    def get_available_skills(self) -> List[str]:
        """获取可用技能"""
        return list(self.skills.keys())
