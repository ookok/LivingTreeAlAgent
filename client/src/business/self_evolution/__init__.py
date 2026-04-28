"""
自我进化引擎包

包含以下核心组件：
1. ToolMissingDetector - 工具缺失检测器
2. AutonomousToolCreator - 自主工具创建器
3. ActiveLearningLoop - 主动学习循环
4. SelfReflectionEngine - 自我反思引擎
5. UserClarificationRequester - 用户交互澄清器
6. SafeAutonomousToolCreator - 安全的自主工具创建器（含沙箱/安全检查/回滚）
7. ProxySourceManager - 代理源管理器（代理池/自动测试/自动切换）
8. CLIToolDiscoverer - CLI 工具发现器（扫描PATH/帮助解析/自动封装）
9. ModelAutoDetectorAndUpgrader - 模型自动检测与升级器（能力测试/对比/自动升级）
10. DeterministicExecutor - 确定性执行器（有状态可干预运行时）
11. ModelNativeDSL - LLM优化的领域特定语言
12. AntiRationalizationTable - 反合理化表（防止错误推理模式）

核心原则：不预置逻辑和模板，一切通过学习、交互和反馈不断进化
"""

from client.src.business.self_evolution.tool_missing_detector import ToolMissingDetector
from client.src.business.self_evolution.autonomous_tool_creator import AutonomousToolCreator
from client.src.business.self_evolution.active_learning_loop import ActiveLearningLoop
from client.src.business.self_evolution.self_reflection_engine import SelfReflectionEngine
from client.src.business.self_evolution.user_clarification_requester import UserClarificationRequester
from client.src.business.self_evolution.safe_autonomous_tool_creator import SafeAutonomousToolCreator
from client.src.business.self_evolution.proxy_source_manager import ProxySourceManager
from client.src.business.self_evolution.cli_tool_discoverer import CLIToolDiscoverer
from client.src.business.self_evolution.model_auto_detector_and_upgrader import (
    ModelAutoDetectorAndUpgrader,
    ModelProfile,
    UpgradeDecision,
)
from client.src.business.self_evolution.deterministic_executor import (
    DeterministicExecutor,
    ExecutionStatus,
    InterventionType,
    ExecutionSnapshot,
    ExecutionStep,
    ExecutionContext,
)
from client.src.business.self_evolution.model_native_dsl import (
    ModelNativeDSL,
    DSLTokenType,
    DSLCommand,
    DSLToken,
    DSLNode,
)
from client.src.business.self_evolution.anti_rationalization_table import (
    AntiRationalizationTable,
    AntiRationalizationRule,
)
from typing import Any, Dict, List
from loguru import logger

__all__ = [
    # 基础组件（5 个）
    "ToolMissingDetector",
    "AutonomousToolCreator",
    "ActiveLearningLoop",
    "SelfReflectionEngine",
    "UserClarificationRequester",
    # 安全与增强组件（4 个）
    "SafeAutonomousToolCreator",
    "ProxySourceManager",
    "CLIToolDiscoverer",
    "ModelAutoDetectorAndUpgrader",
    "ModelProfile",
    "UpgradeDecision",
    # 确定性执行与 DSL（2 个）
    "DeterministicExecutor",
    "ExecutionStatus",
    "InterventionType",
    "ExecutionSnapshot",
    "ExecutionStep",
    "ExecutionContext",
    "ModelNativeDSL",
    "DSLTokenType",
    "DSLCommand",
    "DSLToken",
    "DSLNode",
    # 反合理化表
    "AntiRationalizationTable",
    "AntiRationalizationRule",
    # 整合引擎
    "SelfEvolutionEngine",
    "enable_self_evolution_for_agent",
]


class SelfEvolutionEngine:
    """
    自我进化引擎（整合接口）
    
    整合所有自我进化相关组件，提供统一接口。
    
    核心能力：
    1. 自主发现缺失功能 → ToolMissingDetector
    2. 自主学习 → ActiveLearningLoop
    3. 自主创建工具 → AutonomousToolCreator / SafeAutonomousToolCreator
    4. 自主完善功能 → SelfReflectionEngine
    5. 自主升级模型 → ModelAutoDetectorAndUpgrader
    6. 代理源自动管理 → ProxySourceManager
    7. CLI 工具自动发现 → CLIToolDiscoverer
    8. 用户交互澄清 → UserClarificationRequester
    """
    
    def __init__(self, llm_client=None, safe_mode: bool = True):
        """
        初始化自我进化引擎
        
        Args:
            llm_client: LLM 客户端
            safe_mode: 安全模式（启用 SafeAutonomousToolCreator）
        """
        # 基础组件
        self._detector = ToolMissingDetector(llm_client)
        self._learning_loop = ActiveLearningLoop(llm_client)
        self._reflection_engine = SelfReflectionEngine(llm_client)
        self._clarification_requester = UserClarificationRequester()
        
        # 工具创建（安全模式或基础模式）
        if safe_mode:
            self._creator = SafeAutonomousToolCreator(
                llm_client=llm_client,
                require_user_confirmation=True,
                sandbox_enabled=True,
            )
        else:
            self._creator = AutonomousToolCreator(llm_client=llm_client)
        
        # 增强组件
        self._proxy_manager = ProxySourceManager()
        self._cli_discoverer = CLIToolDiscoverer()
        self._model_detector = ModelAutoDetectorAndUpgrader(
            require_user_confirmation=True,
        )
        
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
        
        # 2. 挂载自主工具创建（安全模式）
        agent.tool_creator = self._creator
        
        # 3. 挂载主动学习循环
        agent.learning_loop = self._learning_loop
        
        # 4. 挂载自我反思引擎
        agent.reflection_engine = self._reflection_engine
        
        # 5. 挂载用户交互澄清器
        agent.clarification_requester = self._clarification_requester
        
        # 6. 挂载代理源管理器
        agent.proxy_manager = self._proxy_manager
        
        # 7. 挂载 CLI 工具发现器
        agent.cli_discoverer = self._cli_discoverer
        
        # 8. 挂载模型自动检测与升级器
        agent.model_detector = self._model_detector
        
        self._logger.info("自我进化能力已启用（9 个组件）")
    
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
            
            # 3. 创建缺失工具（安全模式）
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
    
    async def discover_system_tools(self, max_tools: int = 50) -> List[dict]:
        """
        发现系统 CLI 工具
        
        Args:
            max_tools: 最多发现数量
            
        Returns:
            发现的工具列表
        """
        return await self._cli_discoverer.discover(max_tools)
    
    async def check_model_upgrades(self) -> List[dict]:
        """
        检查是否有可升级的模型
        
        Returns:
            升级决策列表
        """
        profiles = await self._model_detector.detect_and_evaluate()
        return [p.to_dict() for p in profiles]
    
    async def refresh_proxy_pool(self):
        """刷新代理池"""
        await self._proxy_manager.refresh_proxies()
    
    def get_status(self) -> Dict[str, Any]:
        """获取自我进化引擎状态"""
        return {
            "components": 9,
            "safe_mode": isinstance(self._creator, SafeAutonomousToolCreator),
            "proxy_stats": self._proxy_manager.get_stats(),
            "model_stats": self._model_detector.get_stats(),
            "discovered_tools": len(self._cli_discoverer._discovered),
        }


# 便捷函数
async def enable_self_evolution_for_agent(agent, llm_client=None, safe_mode: bool = True):
    """
    为智能体启用自我进化能力（便捷函数）
    
    Args:
        agent: 智能体实例
        llm_client: LLM 客户端（可选）
        safe_mode: 是否启用安全模式（默认 True）
    """
    engine = SelfEvolutionEngine(llm_client, safe_mode=safe_mode)
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
        print("测试 SelfEvolutionEngine v2（9 个组件）")
        print("=" * 60)
        
        # 创建引擎
        engine = SelfEvolutionEngine(safe_mode=True)
        
        # 测试状态
        print("\n测试引擎状态...")
        status = engine.get_status()
        print(f"  组件数: {status['components']}")
        print(f"  安全模式: {status['safe_mode']}")
        print(f"  已发现工具: {status['discovered_tools']}")
        
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
