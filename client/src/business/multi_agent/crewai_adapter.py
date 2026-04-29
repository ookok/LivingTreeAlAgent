"""
CrewAI Agent Adapter for BaseTool Integration

将 CrewAI Agent 适配为项目标准 BaseTool，
支持工具共享、上下文传递和多Agent协作。
"""

import os
import sys
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
from enum import Enum

# 正确的导入路径
from client.src.business.tools.base_tool import BaseTool, AgentCallResult

# 定义本地 ModelCapability 枚举（避免依赖 global_model_router）
class ModelCapability(Enum):
    """模型能力枚举（简化版）"""
    CHAT = "chat"
    REASONING = "reasoning"
    SUMMARIZE = "summarize"
    TRANSLATE = "translate"
    CODE = "code"
    ANALYSIS = "analysis"


class CrewAIAgentAdapter(BaseTool):
    """
    CrewAI Agent 适配器
    
    将 CrewAI Agent 包装为 BaseTool，使其能无缝集成到
    项目的工具注册表和任务执行流程中。
    
    核心特性：
    1. 工具共享 - 将项目工具传递给 CrewAI Agent
    2. 上下文传递 - 支持任务链和多Agent协作
    3. 记忆集成 - 利用项目的记忆系统
    4. 监控集成 - 支持 Opik 追踪（如果已安装）
    """
    
    def __init__(
        self,
        name: str,
        role: str,
        goal: str,
        backstory: str,
        tools: Optional[List[Callable]] = None,
        verbose: bool = False,
        max_iter: int = 20,
        max_execution_time: Optional[int] = None,
        allow_delegation: bool = False,
        shared_tools: Optional[List[BaseTool]] = None,
        enable_memory: bool = True,
        enable_monitoring: bool = True
    ):
        """
        初始化 CrewAI Agent 适配器
        
        Args:
            name: 工具名称（BaseTool 标识）
            role: Agent 角色（CrewAI）
            goal: Agent 目标（CrewAI）
            backstory: Agent 背景故事（CrewAI）
            tools: CrewAI 格式的工具列表
            verbose: 是否详细输出
            max_iter: 最大迭代次数
            max_execution_time: 最大执行时间（秒）
            allow_delegation: 是否允许委托
            shared_tools: 项目 BaseTool 列表（将转换为 CrewAI 工具）
            enable_memory: 是否启用项目记忆集成
            enable_monitoring: 是否启用监控（Opik）
        """
        # 先设置属性（用于 @property 方法，必须在 super().__init__() 之前）
        self._name = name
        self._description = f"{role}: {goal}"
        self._category = "ai"  # CrewAI Agent 是 AI 工具
        
        # 初始化 BaseTool（不传递参数，BaseTool.__init__() 不接受参数）
        super().__init__()
        
        self.role = role
        self.goal = goal
        self.backstory = backstory
        self.verbose = verbose
        self.max_iter = max_iter
        self.max_execution_time = max_execution_time
        self.allow_delegation = allow_delegation
        
        # 工具转换
        self.shared_tools = shared_tools or []
        self.crewai_tools = tools or []
        
        # 特性开关
        self.enable_memory = enable_memory
        self.enable_monitoring = enable_monitoring
        
        # CrewAI Agent 实例（延迟初始化）
        self._agent = None
        self._memory = None
        
        # 执行历史
        self.execution_history = []
    
    @property
    def name(self) -> str:
        """工具名称"""
        return self._name
    
    @property
    def description(self) -> str:
        """工具描述"""
        return self._description
    
    @property
    def category(self) -> str:
        """工具类别"""
        return self._category
    
    def _init_agent(self):
        """延迟初始化 CrewAI Agent"""
        if self._agent is not None:
            return self._agent
        
        try:
            from crewai import Agent
            
            # 转换项目工具为 CrewAI 工具
            converted_tools = self._convert_tools()
            all_tools = converted_tools + self.crewai_tools
            
            # 创建 CrewAI Agent
            self._agent = Agent(
                role=self.role,
                goal=self.goal,
                backstory=self.backstory,
                tools=all_tools,
                verbose=self.verbose,
                max_iter=self.max_iter,
                max_execution_time=self.max_execution_time,
                allow_delegation=self.allow_delegation
            )
            
            # 集成项目记忆系统
            if self.enable_memory:
                self._init_memory()
            
            return self._agent
            
        except ImportError:
            raise ImportError(
                "CrewAI not installed. Please install it with: pip install crewai"
            )
    
    def _convert_tools(self) -> List[Callable]:
        """
        将项目 BaseTool 转换为 CrewAI 工具
        
        Returns:
            CrewAI 兼容的工具列表
        """
        converted = []
        
        for base_tool in self.shared_tools:
            # 创建包装函数
            def create_wrapper(tool: BaseTool) -> Callable:
                def tool_wrapper(*args, **kwargs) -> Any:
                    """将 BaseTool 包装为 CrewAI 工具"""
                    try:
                        # 智能参数映射：将 CrewAI 传递的参数映射给 BaseTool
                        mapped_kwargs = self._map_parameters(tool, *args, **kwargs)
                        
                        # 调用 BaseTool
                        result = tool.execute(**mapped_kwargs)
                        
                        # 处理 AgentCallResult
                        if isinstance(result, AgentCallResult):
                            if result.success:
                                return result.data
                            else:
                                raise Exception(result.error)
                        return result
                    except Exception as e:
                        if self.verbose:
                            print(f"[CrewAIAgentAdapter] Tool {tool.name} failed: {e}")
                        raise
                
                # 设置函数元数据（CrewAI 使用）
                tool_wrapper.__name__ = base_tool.name
                
                # 增强文档字符串：添加参数说明
                param_desc = self._format_parameters(tool.parameters)
                tool_wrapper.__doc__ = f"{base_tool.description}\n\n参数:\n{param_desc}"
                
                return tool_wrapper
            
            converted.append(create_wrapper(base_tool))
        
        return converted
    
    def _map_parameters(self, tool: BaseTool, *args, **kwargs) -> Dict[str, Any]:
        """
        将 CrewAI 传递的参数映射给 BaseTool
        
        Args:
            tool: BaseTool 实例
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            映射后的参数字典
        """
        # 如果有关键字参数，直接使用
        if kwargs:
            return kwargs
        
        # 如果有位置参数，尝试映射给 BaseTool 的第一个参数
        if args:
            # 获取 BaseTool 的参数列表
            tool_params = tool.parameters
            if tool_params and isinstance(tool_params, dict):
                param_names = list(tool_params.keys())
                if param_names:
                    # 将第一个位置参数映射给第一个参数名
                    return {param_names[0]: args[0]}
        
        # 默认：返回空字典
        return {}
    
    def _format_parameters(self, parameters: Dict[str, str]) -> str:
        """
        格式化 BaseTool 的参数，用于生成 CrewAI 工具的文档字符串
        
        Args:
            parameters: BaseTool 的参数字典
            
        Returns:
            格式化后的参数字符串
        """
        if not parameters:
            return "无参数"
        
        lines = []
        for param_name, param_type in parameters.items():
            lines.append(f"  {param_name} ({param_type})")
        
        return "\n".join(lines)
    
    def _init_memory(self):
        """初始化项目记忆系统集成"""
        try:
            from client.src.business.intelligent_memory.memory_manager import MemoryManager
            
            self._memory = MemoryManager()
            
            if self.verbose:
                print(f"[CrewAIAgentAdapter] Memory integration enabled for {self.name}")
                
        except ImportError:
            if self.verbose:
                print(f"[CrewAIAgentAdapter] Memory not available for {self.name}")
    
    def register(self):
        """
        注册到 ToolRegistry
        
        将当前 CrewAI Agent Adapter 注册到全局 ToolRegistry，
        使其可以被其他组件发现和使用。
        """
        try:
            from client.src.business.tools.tool_registry import ToolRegistry, ToolDefinition
            
            registry = ToolRegistry.get_instance()
            tool_def = ToolDefinition(
                name=self.name,
                description=self.description,
                handler=self.execute,
                parameters=self.parameters,
                returns="AgentCallResult",
                category=self.category,
                version="1.0",
                author="CrewAI Adapter"
            )
            registry.register(tool_def)
            
            if self.verbose:
                print(f"[CrewAIAgentAdapter] Registered {self.name} to ToolRegistry")
                
        except ImportError:
            if self.verbose:
                print(f"[CrewAIAgentAdapter] ToolRegistry not available")
    
    @property
    def parameters(self) -> Dict[str, str]:
        """工具参数（从 BaseTool 要求）"""
        # CrewAI Agent 至少需要 prompt 参数
        return {
            "prompt": "string (必需) - 输入提示",
            "context": "string (可选) - 上下文信息"
        }
    
    def execute(self, **kwargs) -> AgentCallResult:
        """
        执行 CrewAI Agent
        
        Args:
            kwargs: 执行参数，支持：
                - prompt: 输入提示（必需）
                - context: 上下文信息（可选）
                - tools: 额外工具（可选）
                
        Returns:
            AgentCallResult: 执行结果
        """
        try:
            # 获取输入
            prompt = kwargs.get("prompt") or kwargs.get("input")
            if not prompt:
                return AgentCallResult(
                    success=False,
                    error="Missing required parameter: 'prompt' or 'input'"
                )
            
            context = kwargs.get("context", "")
            
            # 初始化 Agent
            agent = self._init_agent()
            
            # 监控集成（如果启用）
            if self.enable_monitoring:
                self._start_monitoring(prompt)
            
            # 执行 Agent
            if self.verbose:
                print(f"\n[CrewAIAgentAdapter] Executing agent: {self.name}")
                print(f"[CrewAIAgentAdapter] Prompt: {prompt[:100]}...")
            
            start_time = datetime.now()
            
            # 使用 CrewAI Agent 的 kickoff 方法
            result = agent.kickoff(
                inputs={
                    "prompt": prompt,
                    "context": context
                }
            )
            
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            
            # 记录执行历史
            self.execution_history.append({
                "timestamp": start_time.isoformat(),
                "prompt": prompt,
                "context": context,
                "result": result.raw if hasattr(result, 'raw') else str(result),
                "execution_time": execution_time
            })
            
            # 监控结束
            if self.enable_monitoring:
                self._end_monitoring(result, execution_time)
            
            # 返回结果
            return AgentCallResult(
                success=True,
                data=result.raw if hasattr(result, 'raw') else str(result),
                metadata={
                    "agent_name": self.name,
                    "role": self.role,
                    "execution_time": execution_time,
                    "history_length": len(self.execution_history)
                }
            )
            
        except Exception as e:
            error_msg = f"CrewAI Agent execution failed: {str(e)}"
            
            if self.verbose:
                print(f"[CrewAIAgentAdapter] Error: {error_msg}")
            
            return AgentCallResult(
                success=False,
                error=error_msg,
                metadata={
                    "agent_name": self.name,
                    "error_type": type(e).__name__
                }
            )
    
    def _start_monitoring(self, prompt: str):
        """启动监控（Opik 集成）"""
        try:
            from client.src.business.opik_tracer import opik_tracer
            
            if opik_tracer.is_enabled():
                opik_tracer.start_trace(
                    name=f"crewai_agent_{self.name}",
                    inputs={"prompt": prompt}
                )
        except ImportError:
            pass  # Opik 未安装
    
    def _end_monitoring(self, result: Any, execution_time: float):
        """结束监控"""
        try:
            from client.src.business.opik_tracer import opik_tracer
            
            if opik_tracer.is_enabled():
                opik_tracer.end_trace(
                    outputs={
                        "result": result.raw if hasattr(result, 'raw') else str(result),
                        "execution_time": execution_time
                    }
                )
        except ImportError:
            pass  # Opik 未安装
    
    def get_execution_history(self) -> List[Dict]:
        """
        获取执行历史
        
        Returns:
            执行历史列表
        """
        return self.execution_history
    
    def clear_history(self):
        """清空执行历史"""
        self.execution_history = []
    
    @classmethod
    def create_from_config(cls, config: Dict[str, Any]) -> 'CrewAIAgentAdapter':
        """
        从配置字典创建适配器
        
        Args:
            config: 配置字典，包含：
                - name: 工具名称
                - role: Agent 角色
                - goal: Agent 目标
                - backstory: Agent 背景
                - tools: 工具列表（可选）
                - verbose: 是否详细输出（可选）
                
        Returns:
            CrewAIAgentAdapter 实例
        """
        return cls(
            name=config["name"],
            role=config["role"],
            goal=config["goal"],
            backstory=config["backstory"],
            tools=config.get("tools", []),
            verbose=config.get("verbose", False),
            max_iter=config.get("max_iter", 20),
            allow_delegation=config.get("allow_delegation", False),
            enable_memory=config.get("enable_memory", True),
            enable_monitoring=config.get("enable_monitoring", True)
        )


class CrewAICrewAdapter(BaseTool):
    """
    CrewAI Crew 适配器
    
    将 CrewAI Crew（多Agent协作）包装为 BaseTool，
    支持 sequential、hierarchical 流程。
    """
    
    def __init__(
        self,
        name: str,
        agents: List[CrewAIAgentAdapter],
        tasks: List[Dict[str, Any]],
        process: str = "sequential",
        verbose: bool = False,
        manager_llm: Optional[str] = None,
        enable_monitoring: bool = True
    ):
        """
        初始化 CrewAI Crew 适配器
        
        Args:
            name: 工具名称
            agents: CrewAIAgentAdapter 列表
            tasks: 任务配置列表
            process: 流程类型（sequential/hierarchical）
            verbose: 是否详细输出
            manager_llm: 管理器 LLM（hierarchical 模式需要）
            enable_monitoring: 是否启用监控
        """
        # 先设置属性（必须在 super().__init__() 之前）
        self._name = name
        self._description = f"CrewAI Crew with {len(agents)} agents"
        self._category = "ai"  # CrewAI Crew 是 AI 工具
        
        # 初始化 BaseTool
        super().__init__()
        
        self.agents = agents
        self.tasks_config = tasks
        self.process = process
        self.verbose = verbose
        self.manager_llm = manager_llm
        self.enable_monitoring = enable_monitoring
        
        # CrewAI 实例（延迟初始化）
        self._crew = None
        self.execution_history = []
    
    @property
    def name(self) -> str:
        """工具名称"""
        return self._name
    
    @property
    def description(self) -> str:
        """工具描述"""
        return self._description
    
    @property
    def category(self) -> str:
        """工具类别"""
        return self._category
    
    def _init_crew(self):
        """延迟初始化 CrewAI Crew"""
        if self._crew is not None:
            return self._crew
        
        try:
            from crewai import Crew, Agent, Task, Process
            
            # 转换 Agent
            crewai_agents = [adapter._init_agent() for adapter in self.agents]
            
            # 转换 Task
            crewai_tasks = []
            for task_config in self.tasks_config:
                task = Task(
                    description=task_config["description"],
                    expected_output=task_config["expected_output"],
                    agent=crewai_agents[task_config.get("agent_index", 0)]
                )
                crewai_tasks.append(task)
            
            # 确定流程类型
            process_map = {
                "sequential": Process.sequential,
                "hierarchical": Process.hierarchical
            }
            crewai_process = process_map.get(self.process, Process.sequential)
            
            # 创建 Crew
            crew_kwargs = {
                "agents": crewai_agents,
                "tasks": crewai_tasks,
                "process": crewai_process,
                "verbose": self.verbose
            }
            
            if self.process == "hierarchical" and self.manager_llm:
                crew_kwargs["manager_llm"] = self.manager_llm
            
            self._crew = Crew(**crew_kwargs)
            
            return self._crew
            
        except ImportError:
            raise ImportError(
                "CrewAI not installed. Please install it with: pip install crewai"
            )
    
    def execute(self, **kwargs) -> AgentCallResult:
        """
        执行 CrewAI Crew
        
        Args:
            kwargs: 执行参数，支持：
                - inputs: 输入字典
                
        Returns:
            AgentCallResult: 执行结果
        """
        try:
            # 获取输入
            inputs = kwargs.get("inputs", {})
            
            # 初始化 Crew
            crew = self._init_crew()
            
            if self.verbose:
                print(f"\n[CrewAICrewAdapter] Executing crew: {self.name}")
                print(f"[CrewAICrewAdapter] Process: {self.process}")
                print(f"[CrewAICrewAdapter] Agents: {[a.role for a in crew.agents]}")
            
            start_time = datetime.now()
            
            # 执行 Crew
            result = crew.kickoff(inputs=inputs)
            
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            
            # 记录执行历史
            self.execution_history.append({
                "timestamp": start_time.isoformat(),
                "inputs": inputs,
                "result": result.raw if hasattr(result, 'raw') else str(result),
                "execution_time": execution_time
            })
            
            # 返回结果
            return AgentCallResult(
                success=True,
                data=result.raw if hasattr(result, 'raw') else str(result),
                metadata={
                    "crew_name": self.name,
                    "process": self.process,
                    "agents_count": len(self.agents),
                    "tasks_count": len(self.tasks_config),
                    "execution_time": execution_time
                }
            )
            
        except Exception as e:
            error_msg = f"CrewAI Crew execution failed: {str(e)}"
            
            if self.verbose:
                print(f"[CrewAICrewAdapter] Error: {error_msg}")
            
            return AgentCallResult(
                success=False,
                error=error_msg,
                metadata={
                    "crew_name": self.name,
                    "error_type": type(e).__name__
                }
            )
    
    @classmethod
    def create_sequential_crew(
        cls,
        name: str,
        agents_config: List[Dict],
        tasks_config: List[Dict],
        **kwargs
    ) -> 'CrewAICrewAdapter':
        """
        创建 sequential 流程的 Crew
        
        Args:
            name: Crew 名称
            agents_config: Agent 配置列表
            tasks_config: Task 配置列表
            **kwargs: 其他参数
            
        Returns:
            CrewAICrewAdapter 实例
        """
        # 创建 Agent 适配器
        agents = [
            CrewAIAgentAdapter.create_from_config(config)
            for config in agents_config
        ]
        
        return cls(
            name=name,
            agents=agents,
            tasks=tasks_config,
            process="sequential",
            **kwargs
        )
    
    @classmethod
    def create_hierarchical_crew(
        cls,
        name: str,
        agents_config: List[Dict],
        tasks_config: List[Dict],
        manager_llm: str,
        **kwargs
    ) -> 'CrewAICrewAdapter':
        """
        创建 hierarchical 流程的 Crew
        
        Args:
            name: Crew 名称
            agents_config: Agent 配置列表
            tasks_config: Task 配置列表
            manager_llm: 管理器 LLM
            **kwargs: 其他参数
            
        Returns:
            CrewAICrewAdapter 实例
        """
        # 创建 Agent 适配器
        agents = [
            CrewAIAgentAdapter.create_from_config(config)
            for config in agents_config
        ]
        
        return cls(
            name=name,
            agents=agents,
            tasks=tasks_config,
            process="hierarchical",
            manager_llm=manager_llm,
            **kwargs
        )


def convert_crewai_agent_to_tool(
    role: str,
    goal: str,
    backstory: str,
    tools: Optional[List[Callable]] = None,
    **kwargs
) -> CrewAIAgentAdapter:
    """
    快速将 CrewAI Agent 转换为 BaseTool
    
    Args:
        role: Agent 角色
        goal: Agent 目标
        backstory: Agent 背景
        tools: 工具列表
        **kwargs: 其他参数
        
    Returns:
        CrewAIAgentAdapter 实例
    """
    name = kwargs.get("name", f"crewai_{role.lower().replace(' ', '_')}")
    
    return CrewAIAgentAdapter(
        name=name,
        role=role,
        goal=goal,
        backstory=backstory,
        tools=tools,
        **kwargs
    )


# 导出
__all__ = [
    'CrewAIAgentAdapter',
    'CrewAICrewAdapter',
    'convert_crewai_agent_to_tool'
]
