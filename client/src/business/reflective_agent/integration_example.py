"""
反思式Agent集成示例

展示如何将 ReflectiveAgentLoop 集成到 LivingTreeAgent
"""

import asyncio
from typing import Dict, Any, Optional, Callable, Awaitable

from business.reflective_agent import (
    ReflectiveAgentLoop,
    ReflectiveLoopConfig,
    ExecutionPlan,
    PlanStep,
    StepPriority
)


class LivingTreeAgentWithReflection:
    """
    集成反思能力的 LivingTreeAgent

    扩展原有 LivingTreeAgent，添加执行-反思-改进循环
    """

    def __init__(
        self,
        livingtree_agent,  # 原始 LivingTreeAgent 实例
        config: Optional[ReflectiveLoopConfig] = None
    ):
        self._livingtree = livingtree_agent
        self._config = config or ReflectiveLoopConfig()
        self._reflective_loop = ReflectiveAgentLoop(self._config)

        # 注册 LivingTreeAgent 的工具作为执行器
        self._register_livingtree_tools()

        # 注册降级方案
        self._reflective_loop.register_fallback(self._fallback_handler)

    def _register_livingtree_tools(self):
        """注册 LivingTreeAgent 的工具"""

        # 注册搜索工具
        if hasattr(self._livingtree, 'search'):
            self._reflective_loop.register_executor(
                'search',
                self._wrap_tool(self._livingtree.search)
            )

        # 注册知识库工具
        if hasattr(self._livingtree, 'kb_search'):
            self._reflective_loop.register_executor(
                'kb_search',
                self._wrap_tool(self._livingtree.kb_search)
            )

        # 注册 LLM 工具
        if hasattr(self._livingtree, 'llm_chat'):
            self._reflective_loop.register_executor(
                'llm_chat',
                self._wrap_tool(self._livingtree.llm_chat)
            )

        # 注册文件工具
        if hasattr(self._livingtree, 'file_read'):
            self._reflective_loop.register_executor(
                'file_read',
                self._wrap_tool(self._livingtree.file_read)
            )

    def _wrap_tool(self, tool_func: Callable) -> Callable:
        """包装工具函数为执行器格式"""
        async def wrapper(step: PlanStep) -> Dict[str, Any]:
            params = step.params.copy()
            return await tool_func(**params)
        return wrapper

    async def _fallback_handler(
        self,
        task: str,
        history: list
    ) -> Dict[str, Any]:
        """降级处理器：当反思循环失败时使用原始 LivingTreeAgent"""
        # 使用原始 LivingTreeAgent
        return await self._livingtree.send_message(task)

    async def _plan_task(self, task: str) -> ExecutionPlan:
        """
        任务规划器

        基于 LivingTreeAgent 的意图分类和任务分解能力
        """
        plan = ExecutionPlan(
            plan_id=f"livingtree_{hash(task) % 10000}",
            task=task,
            original_task=task
        )

        # 1. 意图分类
        intent = await self._classify_intent(task)

        # 2. 根据意图生成执行计划
        if intent == "search":
            plan.add_step(PlanStep(
                step_id="s1",
                name="知识搜索",
                action="search",
                params={"query": task}
            ))
        elif intent == "kb_query":
            plan.add_step(PlanStep(
                step_id="s1",
                name="知识库查询",
                action="kb_search",
                params={"query": task}
            ))
        elif intent == "llm_task":
            plan.add_step(PlanStep(
                step_id="s1",
                name="LLM推理",
                action="llm_chat",
                params={"prompt": task}
            ))
        else:
            # 通用任务：使用 LLM
            plan.add_step(PlanStep(
                step_id="s1",
                name="通用处理",
                action="llm_chat",
                params={"prompt": task}
            ))

        return plan

    async def _classify_intent(self, task: str) -> str:
        """意图分类"""
        # 简单关键词匹配
        # 实际应用中可以使用 LivingTreeAgent 的 L0 意图分类
        task_lower = task.lower()

        if any(k in task_lower for k in ["搜索", "查找", "查一下", "search"]):
            return "search"
        elif any(k in task_lower for k in ["知识库", "kb", "知识"]):
            return "kb_query"
        elif any(k in task_lower for k in ["分析", "解释", "写", "生成"]):
            return "llm_task"
        else:
            return "general"

    # ==================== 主接口 ====================

    async def send_message_with_reflection(self, text: str) -> Dict[str, Any]:
        """
        带反思的消息处理

        使用反思式执行循环处理消息
        """
        # 注册规划器
        self._reflective_loop.register_planner(self._plan_task)

        # 执行
        result = await self._reflective_loop.execute_with_reflection(text)

        return {
            "content": result.final_result,
            "success": result.success,
            "attempts": result.attempt_number,
            "reflection": result.reflection_notes
        }

    async def send_message(self, text: str) -> Dict[str, Any]:
        """
        标准消息处理（保持原有接口）
        """
        return await self.send_message_with_reflection(text)

    def get_learning_stats(self) -> Dict[str, Any]:
        """获取学习统计"""
        return {
            "loop_stats": self._reflective_loop.get_stats(),
            "insights": self._reflective_loop.get_learning_insights()
        }


# ==================== 使用示例 ====================

async def main():
    """使用示例"""
    # 假设 livingtree_agent 是已初始化的 LivingTreeAgent 实例
    # livingtree = LivingTreeAgent(config)

    # 创建带反思的版本
    # reflective_livingtree = LivingTreeAgentWithReflection(livingtree)

    # 或者单独使用 ReflectiveAgentLoop
    loop = ReflectiveAgentLoop(ReflectiveLoopConfig(verbose=True))

    # 注册执行器
    async def search_executor(step: PlanStep) -> Dict[str, Any]:
        query = step.params.get("query", "")
        print(f"[搜索] 查询: {query}")
        # 实际搜索逻辑
        return {"results": [f"结果1 for {query}", f"结果2 for {query}"]}

    async def analyze_executor(step: PlanStep) -> Dict[str, Any]:
        data = step.params.get("data", "")
        print(f"[分析] 数据: {data}")
        return {"analysis": f"分析了 {data}"}

    loop.register_executor("search", search_executor)
    loop.register_executor("analyze", analyze_executor)

    # 注册降级
    async def fallback(task: str, history: list) -> Dict[str, Any]:
        print("[降级] 使用降级方案")
        return {"result": "降级结果"}

    loop.register_fallback(fallback)

    # 执行任务
    result = await loop.execute_with_reflection("搜索AI最新进展")

    print(f"\n最终结果:")
    print(f"  状态: {result.status}")
    print(f"  成功: {result.success}")
    print(f"  结果: {result.final_result}")
    print(f"  反思: {result.reflection_notes}")

    # 获取学习洞察
    insights = loop.get_learning_insights()
    print(f"\n学习洞察:")
    print(f"  成功率: {insights['success_rate']:.2%}")
    print(f"  平均尝试: {insights['average_attempts']:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
