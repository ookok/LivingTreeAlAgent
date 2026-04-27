"""
ToolChainOrchestrator - 工具链自动编排器

基于 TaskDecomposer 的工具链自动编排系统。

架构设计：
1. TaskDecomposer 分解任务为多个步骤
2. 每个步骤映射到可用工具
3. 按依赖顺序自动执行工具链
4. 步骤间自动传递数据
5. 处理执行失败和重试

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from loguru import logger

from client.src.business.task_decomposer import TaskDecomposer, DecomposedTask, TaskStep, StepStatus
from client.src.business.tools.tool_registry import ToolRegistry
from client.src.business.global_model_router import GlobalModelRouter


class ChainExecutionStatus(Enum):
    """工具链执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class ToolChainStep:
    """工具链步骤"""
    step_id: str
    task_step: TaskStep  # 来自 TaskDecomposer
    tool_name: str  # 映射到的工具名称
    tool_input: Dict[str, Any] = field(default_factory=dict)
    tool_output: Any = None
    status: ChainExecutionStatus = ChainExecutionStatus.PENDING
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class ToolChainResult:
    """工具链执行结果"""
    chain_id: str
    original_task: str
    steps: List[ToolChainStep]
    status: ChainExecutionStatus
    final_output: Any = None
    
    @property
    def completed_steps(self) -> int:
        return sum(1 for s in self.steps if s.status == ChainExecutionStatus.COMPLETED)
    
    @property
    def total_steps(self) -> int:
        return len(self.steps)
    
    @property
    def progress(self) -> float:
        if self.total_steps == 0:
            return 0.0
        return self.completed_steps / self.total_steps


class ToolChainOrchestrator:
    """
    工具链自动编排器
    
    功能：
    1. 使用 TaskDecomposer 分解任务
    2. 自动映射每个步骤到可用工具
    3. 按依赖顺序执行工具链
    4. 自动处理步骤间数据传递
    5. 失败重试和错误处理
    
    用法：
        orchestrator = ToolChainOrchestrator()
        result = await orchestrator.execute_chain("生成环境影响评估报告")
    """
    
    def __init__(
        self,
        max_parallel_steps: int = 3,
        default_max_retries: int = 3,
    ):
        """
        初始化工具链编排器
        
        Args:
            max_parallel_steps: 最大并行步骤数
            default_max_retries: 默认最大重试次数
        """
        self._decomposer = TaskDecomposer()
        self._registry = ToolRegistry.get_instance()
        self._router = GlobalModelRouter.get_instance()
        self._max_parallel = max_parallel_steps
        self._default_max_retries = default_max_retries
        self._logger = logger.bind(component="ToolChainOrchestrator")
    
    async def execute_chain(self, task: str, context: Optional[Dict] = None) -> ToolChainResult:
        """
        执行工具链
        
        Args:
            task: 任务描述
            context: 初始上下文（可选）
            
        Returns:
            ToolChainResult 执行结果
        """
        self._logger.info(f"开始执行工具链: {task[:50]}...")
        
        # 1. 分解任务
        self._logger.info("步骤 1: 分解任务...")
        decomposed = self._decompose_task(task)
        
        if not decomposed or not decomposed.steps:
            return ToolChainResult(
                chain_id=self._generate_chain_id(),
                original_task=task,
                steps=[],
                status=ChainExecutionStatus.FAILED,
            )
        
        # 2. 映射工具
        self._logger.info("步骤 2: 映射工具...")
        chain_steps = await self._map_tools_to_steps(decomposed, context)
        
        # 3. 执行工具链
        self._logger.info("步骤 3: 执行工具链...")
        result = await self._execute_steps(chain_steps, context)
        
        self._logger.info(f"工具链执行完成: status={result.status.value}")
        
        return result
    
    def _decompose_task(self, task: str) -> Optional[DecomposedTask]:
        """分解任务"""
        try:
            # 检测任务类型
            task_type = self._decomposer.detect_task_type(task)
            self._logger.info(f"检测任务类型: {task_type}")
            
            # 分解任务
            decomposed = self._decomposer.decompose(task, task_type=task_type)
            
            self._logger.info(f"任务分解为 {decomposed.total_steps} 个步骤")
            for step in decomposed.steps:
                self._logger.info(f"  - {step.title}: {step.description}")
            
            return decomposed
            
        except Exception as e:
            self._logger.error(f"任务分解失败: {e}")
            return None
    
    async def _map_tools_to_steps(
        self,
        decomposed: DecomposedTask,
        context: Optional[Dict],
    ) -> List[ToolChainStep]:
        """
        将分解后的步骤映射到可用工具
        
        使用 LLM 分析每个步骤，选择合适的工具。
        """
        chain_steps = []
        
        for step in decomposed.steps:
            # 使用 LLM 为步骤选择工具
            tool_name = await self._select_tool_for_step(step, context)
            
            chain_step = ToolChainStep(
                step_id=step.step_id,
                task_step=step,
                tool_name=tool_name,
                max_retries=self._default_max_retries,
            )
            chain_steps.append(chain_step)
            
            self._logger.info(f"步骤 '{step.title}' 映射到工具: {tool_name}")
        
        return chain_steps
    
    async def _select_tool_for_step(
        self,
        step: TaskStep,
        context: Optional[Dict],
    ) -> str:
        """
        为步骤选择合适的工具
        
        返回工具名称。如果找不到合适工具，返回空字符串。
        """
        # 获取可用工具列表
        available_tools = self._registry.list_tools()
        tool_descriptions = []
        for tool in available_tools:
            tool_descriptions.append(f"- {tool.name}: {tool.description}")
        
        prompt = f"""你是工具选择专家。

任务步骤：
标题：{step.title}
描述：{step.description}
指令：{step.instruction}

可用工具列表：
{chr(10).join(tool_descriptions[:20])}  
# 只显示前 20 个工具

请为这个步骤选择最合适的工具。

请以 JSON 格式输出：
{{
    "selected_tool": "工具名称",
    "reason": "选择理由",
    "confidence": 0.9
}}

只输出 JSON，不要有其他内容。"""

        try:
            response = await self._router.call_model_sync(
                capability="reasoning",
                prompt=prompt,
                temperature=0.1,
            )
            
            # 解析响应
            if hasattr(response, 'thinking') and response.thinking:
                text = response.thinking
            elif hasattr(response, 'content') and response.content:
                text = response.content
            else:
                text = str(response)
            
            # 提取 JSON
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                tool_name = result.get("selected_tool", "")
                
                # 验证工具是否存在
                if any(t.name == tool_name for t in available_tools):
                    return tool_name
                
        except Exception as e:
            self._logger.error(f"选择工具失败: {e}")
        
        return ""  # 没有找到合适工具
    
    async def _execute_steps(
        self,
        chain_steps: List[ToolChainStep],
        context: Optional[Dict],
    ) -> ToolChainResult:
        """执行工具链步骤"""
        
        chain_id = self._generate_chain_id()
        result = ToolChainResult(
            chain_id=chain_id,
            original_task=chain_steps[0].task_step.description if chain_steps else "",
            steps=chain_steps,
            status=ChainExecutionStatus.RUNNING,
        )
        
        # 构建步骤依赖图
        step_dict = {s.step_id: s for s in chain_steps}
        
        # 执行步骤（按依赖顺序，支持有限并行）
        completed = set()
        failed = set()
        
        while len(completed) + len(failed) < len(chain_steps):
            # 找出可执行步骤
            executable = []
            for step in chain_steps:
                if step.step_id in completed or step.step_id in failed:
                    continue
                # 检查依赖是否满足
                task_step = step.task_step
                deps_met = all(
                    dep_id in completed
                    for dep_id in task_step.depends_on
                )
                if deps_met or not task_step.depends_on:
                    executable.append(step)
                    if len(executable) >= self._max_parallel:
                        break
            
            if not executable:
                break  # 没有可执行步骤，退出
            
            # 并行执行
            tasks = [
                self._execute_single_step(step, result, context)
                for step in executable
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理结果
            for step, step_result in zip(executable, results):
                if isinstance(step_result, Exception):
                    step.status = ChainExecutionStatus.FAILED
                    step.error = str(step_result)
                    failed.add(step.step_id)
                elif step_result.get("success"):
                    step.status = ChainExecutionStatus.COMPLETED
                    step.tool_output = step_result.get("output")
                    completed.add(step.step_id)
                else:
                    step.status = ChainExecutionStatus.FAILED
                    step.error = step_result.get("error", "未知错误")
                    failed.add(step.step_id)
            
            # 如果连续失败，退出
            if len(failed) > 0 and len(completed) == 0:
                break
        
        # 更新最终状态
        if len(failed) == 0:
            result.status = ChainExecutionStatus.COMPLETED
        elif len(completed) > 0:
            result.status = ChainExecutionStatus.PARTIAL
        else:
            result.status = ChainExecutionStatus.FAILED
        
        # 生成最终输出
        result.final_output = self._generate_final_output(result)
        
        return result
    
    async def _execute_single_step(
        self,
        chain_step: ToolChainStep,
        chain_result: ToolChainResult,
        context: Optional[Dict],
    ) -> Dict[str, Any]:
        """执行单个步骤"""
        step = chain_step.task_step
        tool_name = chain_step.tool_name
        
        self._logger.info(f"执行步骤: {step.title} (工具: {tool_name})")
        
        # 准备工具输入
        tool_input = self._prepare_tool_input(step, chain_result, context)
        chain_step.tool_input = tool_input
        
        # 调用工具
        if not tool_name:
            # 没有工具，使用 LLM 直接处理
            return await self._execute_step_with_llm(step, tool_input)
        else:
            # 使用工具
            return await self._execute_step_with_tool(chain_step, tool_input)
    
    def _prepare_tool_input(
        self,
        step: TaskStep,
        chain_result: ToolChainResult,
        context: Optional[Dict],
    ) -> Dict[str, Any]:
        """准备工具输入（合并上下文和前序步骤输出）"""
        tool_input = {}
        
        # 加入初始上下文
        if context:
            tool_input.update(context)
        
        # 加入前序步骤的输出
        for prev_step in chain_result.steps:
            if prev_step.status == ChainExecutionStatus.COMPLETED and prev_step.tool_output:
                # 使用步骤标题作为 key
                key = prev_step.task_step.title.lower().replace(" ", "_")
                tool_input[key] = prev_step.tool_output
        
        # 加入步骤指令
        tool_input["instruction"] = step.instruction
        
        return tool_input
    
    async def _execute_step_with_llm(
        self,
        step: TaskStep,
        tool_input: Dict[str, Any],
    ) -> Dict[str, Any]:
        """使用 LLM 直接执行步骤（无工具时）"""
        prompt = f"""你是任务执行专家。

步骤标题：{step.title}
步骤描述：{step.description}
步骤指令：{step.instruction}

输入数据：
{json.dumps(tool_input, ensure_ascii=False, indent=2)}

请执行这个步骤，给出结果。"""

        try:
            response = await self._router.call_model_sync(
                capability="reasoning",
                prompt=prompt,
            )
            
            if hasattr(response, 'thinking') and response.thinking:
                output = response.thinking
            elif hasattr(response, 'content') and response.content:
                output = response.content
            else:
                output = str(response)
            
            return {
                "success": True,
                "output": output,
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    async def _execute_step_with_tool(
        self,
        chain_step: ToolChainStep,
        tool_input: Dict[str, Any],
    ) -> Dict[str, Any]:
        """使用工具执行步骤"""
        tool_name = chain_step.tool_name
        
        try:
            # 从注册表获取工具
            tool = self._registry.get_tool(tool_name)
            if not tool:
                return {
                    "success": False,
                    "error": f"工具 {tool_name} 未找到",
                }
            
            # 执行工具
            result = tool.execute(**tool_input)
            
            if result.success:
                return {
                    "success": True,
                    "output": result.data,
                }
            else:
                return {
                    "success": False,
                    "error": result.error,
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    def _generate_final_output(self, result: ToolChainResult) -> str:
        """生成最终输出摘要"""
        lines = [
            f"# 工具链执行结果",
            f"",
            f"- 任务: {result.original_task}",
            f"- 状态: {result.status.value}",
            f"- 进度: {result.completed_steps}/{result.total_steps} ({result.progress*100:.1f}%)",
            f"",
            f"## 步骤详情",
        ]
        
        for step in result.steps:
            status_icon = "✅" if step.status == ChainExecutionStatus.COMPLETED else "❌"
            lines.append(f"{status_icon} {step.task_step.title}")
            if step.error:
                lines.append(f"  错误: {step.error}")
            if step.tool_output:
                output_str = str(step.tool_output)[:200]
                lines.append(f"  输出: {output_str}...")
        
        return "\n".join(lines)
    
    def _generate_chain_id(self) -> str:
        """生成工具链 ID"""
        import uuid
        return f"chain_{uuid.uuid4().hex[:8]}"


async def test_tool_chain_orchestrator():
    """测试工具链编排器"""
    import sys
    
    logger.remove()
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)
    
    print("=" * 60)
    print("测试 ToolChainOrchestrator")
    print("=" * 60)
    
    # 创建编排器
    orchestrator = ToolChainOrchestrator()
    
    # 测试任务
    test_task = "分析某城市的空气质量变化趋势，并生成报告"
    
    print(f"\n测试任务: {test_task}")
    
    # 执行工具链
    result = await orchestrator.execute_chain(test_task)
    
    print(f"\n[结果]")
    print(f"状态: {result.status.value}")
    print(f"进度: {result.completed_steps}/{result.total_steps}")
    print(f"\n最终输出:\n{result.final_output}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_tool_chain_orchestrator())
