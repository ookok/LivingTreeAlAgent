"""
分层代理架构

借鉴 Google ADK 的分层代理架构，优化工作流引擎
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import asyncio


class AgentType(Enum):
    """代理类型"""
    LLM = "llm"                    # LLM 代理
    SEQUENTIAL = "sequential"      # 顺序执行代理
    PARALLEL = "parallel"          # 并行执行代理
    LOOP = "loop"                  # 循环执行代理
    COORDINATOR = "coordinator"    # 协调器代理


@dataclass
class AgentConfig:
    """代理配置"""
    name: str
    description: str = ""
    model: str = "gpt-4o"
    temperature: float = 0.7
    max_tokens: int = 2000
    timeout: int = 60
    retry_count: int = 3
    output_key: str = ""


@dataclass
class AgentResult:
    """代理执行结果"""
    success: bool
    result: Any = None
    error: str = ""
    output_key: str = ""
    steps: int = 0


class BaseAgent:
    """基础代理类"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.sub_agents: List["BaseAgent"] = []
    
    def add_sub_agent(self, agent: "BaseAgent"):
        """添加子代理"""
        self.sub_agents.append(agent)
    
    async def execute(self, context: Dict[str, Any]) -> AgentResult:
        """执行代理"""
        raise NotImplementedError
    
    def _update_context(self, context: Dict[str, Any], key: str, value: Any):
        """更新上下文"""
        if key:
            context[key] = value


class LlmAgent(BaseAgent):
    """LLM 代理"""
    
    def __init__(self, config: AgentConfig, instruction: str):
        super().__init__(config)
        self.instruction = instruction
        self.agent_type = AgentType.LLM
    
    async def execute(self, context: Dict[str, Any]) -> AgentResult:
        """执行 LLM 代理"""
        try:
            # 准备提示
            prompt = self._prepare_prompt(context)
            
            # 调用 LLM
            result = await self._call_llm(prompt)
            
            # 更新上下文
            if self.config.output_key:
                self._update_context(context, self.config.output_key, result)
            
            return AgentResult(
                success=True,
                result=result,
                output_key=self.config.output_key,
                steps=1
            )
            
        except Exception as e:
            return AgentResult(
                success=False,
                error=str(e),
                output_key=self.config.output_key
            )
    
    def _prepare_prompt(self, context: Dict[str, Any]) -> str:
        """准备提示"""
        # 替换上下文变量
        prompt = self.instruction
        for key, value in context.items():
            placeholder = f"{{{key}}}"
            if placeholder in prompt:
                prompt = prompt.replace(placeholder, str(value))
        return prompt
    
    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM"""
        # 这里应该调用实际的 LLM API
        # 简化实现
        return f"LLM response to: {prompt[:100]}..."


class SequentialAgent(BaseAgent):
    """顺序执行代理"""
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.agent_type = AgentType.SEQUENTIAL
    
    async def execute(self, context: Dict[str, Any]) -> AgentResult:
        """顺序执行子代理"""
        total_steps = 0
        last_result = None
        
        for agent in self.sub_agents:
            result = await agent.execute(context)
            total_steps += result.steps
            
            if not result.success:
                return AgentResult(
                    success=False,
                    error=result.error,
                    steps=total_steps
                )
            
            last_result = result.result
        
        return AgentResult(
            success=True,
            result=last_result,
            output_key=self.config.output_key,
            steps=total_steps
        )


class ParallelAgent(BaseAgent):
    """并行执行代理"""
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.agent_type = AgentType.PARALLEL
    
    async def execute(self, context: Dict[str, Any]) -> AgentResult:
        """并行执行子代理"""
        if not self.sub_agents:
            return AgentResult(
                success=True,
                result=None,
                steps=0
            )
        
        # 并发执行所有子代理
        tasks = [agent.execute(context) for agent in self.sub_agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        total_steps = 0
        failed_results = []
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed_results.append((i, str(result)))
            else:
                total_steps += result.steps
                if not result.success:
                    failed_results.append((i, result.error))
        
        if failed_results:
            return AgentResult(
                success=False,
                error=f"部分代理执行失败: {failed_results}",
                steps=total_steps
            )
        
        return AgentResult(
            success=True,
            result=[r.result if hasattr(r, 'result') else None for r in results],
            output_key=self.config.output_key,
            steps=total_steps
        )


class LoopAgent(BaseAgent):
    """循环执行代理"""
    
    def __init__(self, config: AgentConfig, max_iterations: int = 10, stop_condition: Optional[Callable] = None):
        super().__init__(config)
        self.agent_type = AgentType.LOOP
        self.max_iterations = max_iterations
        self.stop_condition = stop_condition
    
    async def execute(self, context: Dict[str, Any]) -> AgentResult:
        """循环执行子代理直到满足停止条件"""
        total_steps = 0
        iteration = 0
        
        while iteration < self.max_iterations:
            # 检查停止条件
            if self.stop_condition and self.stop_condition(context, iteration):
                break
            
            # 执行子代理
            for agent in self.sub_agents:
                result = await agent.execute(context)
                total_steps += result.steps
                
                if not result.success:
                    return AgentResult(
                        success=False,
                        error=result.error,
                        steps=total_steps
                    )
            
            iteration += 1
        
        return AgentResult(
            success=True,
            result=context.get(self.config.output_key),
            output_key=self.config.output_key,
            steps=total_steps
        )


class CoordinatorAgent(BaseAgent):
    """协调器代理"""
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.agent_type = AgentType.COORDINATOR
    
    async def execute(self, context: Dict[str, Any]) -> AgentResult:
        """协调子代理执行"""
        # 分析任务
        task = context.get("task", "")
        
        # 根据任务类型选择子代理
        selected_agent = self._select_agent(task)
        
        if not selected_agent:
            return AgentResult(
                success=False,
                error="没有合适的子代理处理此任务"
            )
        
        # 执行选中的子代理
        result = await selected_agent.execute(context)
        
        return AgentResult(
            success=result.success,
            result=result.result,
            output_key=self.config.output_key,
            steps=result.steps
        )
    
    def _select_agent(self, task: str) -> Optional[BaseAgent]:
        """选择合适的子代理"""
        task_lower = task.lower()
        
        for agent in self.sub_agents:
            # 简单的关键词匹配
            if "research" in task_lower or "search" in task_lower:
                if "researcher" in agent.config.name.lower():
                    return agent
            elif "execute" in task_lower or "run" in task_lower:
                if "executor" in agent.config.name.lower():
                    return agent
            elif "greet" in task_lower or "hello" in task_lower:
                if "greeter" in agent.config.name.lower():
                    return agent
        
        # 默认返回第一个子代理
        return self.sub_agents[0] if self.sub_agents else None


class AgentTeam:
    """代理团队"""
    
    def __init__(self, name: str):
        self.name = name
        self.root_agent: Optional[BaseAgent] = None
        self.all_agents: Dict[str, BaseAgent] = {}
    
    def set_root_agent(self, agent: BaseAgent):
        """设置根代理"""
        self.root_agent = agent
        self._register_agent(agent)
    
    def _register_agent(self, agent: BaseAgent):
        """注册代理"""
        self.all_agents[agent.config.name] = agent
        
        # 递归注册子代理
        for sub_agent in agent.sub_agents:
            self._register_agent(sub_agent)
    
    async def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        """执行团队任务"""
        if not self.root_agent:
            return AgentResult(
                success=False,
                error="没有设置根代理"
            )
        
        # 初始化上下文
        if context is None:
            context = {}
        context["task"] = task
        
        # 执行根代理
        return await self.root_agent.execute(context)
    
    def get_agent(self, name: str) -> Optional[BaseAgent]:
        """获取代理"""
        return self.all_agents.get(name)
    
    def list_agents(self) -> List[str]:
        """列出所有代理"""
        return list(self.all_agents.keys())


# 工厂函数
def create_llm_agent(
    name: str,
    instruction: str,
    model: str = "gpt-4o",
    output_key: str = ""
) -> LlmAgent:
    """创建 LLM 代理"""
    config = AgentConfig(
        name=name,
        description=instruction,
        model=model,
        output_key=output_key
    )
    return LlmAgent(config, instruction)


def create_sequential_agent(name: str) -> SequentialAgent:
    """创建顺序执行代理"""
    config = AgentConfig(
        name=name,
        description="顺序执行代理"
    )
    return SequentialAgent(config)


def create_parallel_agent(name: str) -> ParallelAgent:
    """创建并行执行代理"""
    config = AgentConfig(
        name=name,
        description="并行执行代理"
    )
    return ParallelAgent(config)


def create_loop_agent(
    name: str,
    max_iterations: int = 10,
    stop_condition: Optional[Callable] = None
) -> LoopAgent:
    """创建循环执行代理"""
    config = AgentConfig(
        name=name,
        description="循环执行代理"
    )
    return LoopAgent(config, max_iterations, stop_condition)


def create_coordinator_agent(name: str) -> CoordinatorAgent:
    """创建协调器代理"""
    config = AgentConfig(
        name=name,
        description="协调器代理"
    )
    return CoordinatorAgent(config)


def create_agent_team(name: str) -> AgentTeam:
    """创建代理团队"""
    return AgentTeam(name)
