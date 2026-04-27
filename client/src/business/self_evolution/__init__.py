"""
自我进化引擎包

包含以下核心组件：
1. ToolMissingDetector - 工具缺失检测器
2. AutonomousToolCreator - 自主工具创建器
3. ActiveLearningLoop - 主动学习循环
4. SelfReflectionEngine - 自我反思引擎
5. UserClarificationRequester - 用户交互澄清器
"""

from client.src.business.self_evolution.tool_missing_detector import ToolMissingDetector
from client.src.business.self_evolution.autonomous_tool_creator import AutonomousToolCreator
from client.src.business.self_evolution.active_learning_loop import ActiveLearningLoop
from client.src.business.self_evolution.self_reflection_engine import SelfReflectionEngine
from client.src.business.self_evolution.user_clarification_requester import UserClarificationRequester

__all__ = [
    "ToolMissingDetector",
    "AutonomousToolCreator",
    "ActiveLearningLoop",
    "SelfReflectionEngine",
    "UserClarificationRequester",
]


class SelfEvolutionEngine:
    """
    自我进化引擎（整合接口）
    
    整合所有自我进化相关组件，提供统一接口。
    """
    
    def __init__(self, llm_client=None):
        """
        初始化自我进化引擎
        
        Args:
            llm_client: LLM 客户端
        """
        self._detector = ToolMissingDetector(llm_client)
        self._creator = AutonomousToolCreator(llm_client)
        self._learning_loop = ActiveLearningLoop(llm_client)
        self._reflection_engine = SelfReflectionEngine(llm_client)
        self._clarification_requester = UserClarificationRequester()
        
        self._logger = logger.bind(component="SelfEvolutionEngine")
    
    async def enable_self_evolution(self, agent):
        """
        为智能体启用自我进化能力
        
        Args:
            agent: 智能体实例（如 EIAgent）
        """
        self._logger.info(f"为 {agent.__class__.__name__} 启用自我进化能力...")
        
        # 1. 挂载工具缺失检测
        agent.tool_missing_detector = self._detector
        
        # 2. 挂载自主工具创建
        agent.tool_creator = self._creator
        
        # 3. 挂载主动学习循环
        agent.learning_loop = self._learning_loop
        
        # 4. 挂载自我反思引擎
        agent.reflection_engine = self._reflection_engine
        
        # 5. 挂载用户交互澄清器
        agent.clarification_requester = self._clarification_requester
        
        self._logger.info("自我进化能力已启用")
    
    async def analyze_and_improve(self, task: str, execution_result: Any) -> Dict[str, Any]:
        """
        分析任务执行并改进
        
        Args:
            task: 任务描述
            execution_result: 执行结果
            
        Returns:
            改进结果字典
        """
        self._logger.info(f"分析并改进: {task[:50]}...")
        
        # 1. 反思任务执行
        reflection = await self._reflection_engine.reflect_on_task_execution(
            task, execution_result
        )
        
        # 2. 如果失败，检测缺失工具
        if not reflection.get("success"):
            missing_tools = await self._detector.detect_missing_tools(
                task, None  # 使用默认工具列表
            )
            
            # 3. 创建缺失工具
            created_tools = []
            for tool_name in missing_tools:
                success, file_path = await self._creator.create_tool(
                    tool_name, f"自动创建的 {tool_name} 工具"
                )
                if success:
                    created_tools.append(tool_name)
            
            return {
                "reflection": reflection,
                "missing_tools": missing_tools,
                "created_tools": created_tools
            }
        
        return {"reflection": reflection}
    
    async def start_active_learning(self, max_iterations: int = 10):
        """
        开始主动学习
        
        Args:
            max_iterations: 最大迭代次数
        """
        self._logger.info(f"开始主动学习（最多 {max_iterations} 次迭代）...")
        await self._learning_loop.start_learning_loop(max_iterations)
    
    async def request_user_clarification(
        self,
        question: str,
        options: List[str] = None
    ) -> str:
        """
        请求用户澄清
        
        Args:
            question: 问题
            options: 选项列表
            
        Returns:
            用户回复
        """
        return await self._clarification_requester.request_clarification(
            question, options
        )


# 便捷函数
async def enable_self_evolution_for_agent(agent, llm_client=None):
    """
    为智能体启用自我进化能力（便捷函数）
    
    Args:
        agent: 智能体实例
        llm_client: LLM 客户端（可选）
    """
    engine = SelfEvolutionEngine(llm_client)
    await engine.enable_self_evolution(agent)
    return engine


if __name__ == "__main__":
    # 测试自我进化引擎
    import sys
    import os
    
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    
    # 配置 loguru
    logger.remove()
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)
    
    async def test_self_evolution_engine():
        """测试自我进化引擎"""
        print("=" * 60)
        print("测试 SelfEvolutionEngine")
        print("=" * 60)
        
        # 创建引擎
        engine = SelfEvolutionEngine()
        
        # 测试分析并改进
        print("\n测试分析并改进...")
        task = "获取苹果公司的财报数据并分析"
        execution_result = "失败：缺少 financial_data_fetcher 工具"
        
        result = await engine.analyze_and_improve(task, execution_result)
        
        print(f"\n[结果] 分析完成:")
        print(f"  成功: {result.get('reflection', {}).get('success')}")
        print(f"  缺失工具: {result.get('missing_tools', [])}")
        print(f"  创建工具: {result.get('created_tools', [])}")
        
        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)
    
    asyncio.run(test_self_evolution_engine())
