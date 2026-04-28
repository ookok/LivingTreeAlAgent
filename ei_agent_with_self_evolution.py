"""
EIAgent with Self-Evolution Capabilities

演示 EIAgent 具备自我学习和自我进化能力
"""

import sys
import os
import asyncio
import logging

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

logger = logging.getLogger(__name__)


class EIAgentWithSelfEvolution:
    """
    EIAgent with Self-Evolution Capabilities
    
    功能：
    1. 自我学习能力 - 主动学习新知识
    2. 自我进化能力 - 自动创建和改进工具
    3. 自我反思能力 - 分析任务执行并改进
    """
    
    def __init__(self, llm_client=None):
        """初始化 EIAgent with Self-Evolution"""
        logger.info("[EIAgent] 初始化 EIAgent with Self-Evolution...")
        
        # 初始化自我进化引擎
        self.self_evolution_engine = None
        self.self_evolution_enabled = False
        
        try:
            from client.src.business.self_evolution import SelfEvolutionEngine
            self.self_evolution_engine = SelfEvolutionEngine(llm_client)
            self.self_evolution_enabled = True
            logger.info("[EIAgent] 自我进化引擎初始化成功")
        except ImportError as e:
            logger.warning(f"[EIAgent] 自我进化引擎初始化失败: {e}")
        
        # 初始化其他组件
        self._init_components()
        
        logger.info("[EIAgent] EIAgent with Self-Evolution 初始化完成")
    
    def _init_components(self):
        """初始化其他组件"""
        # 初始化 FusionRAG 知识库
        try:
            from client.src.business.fusion_rag.knowledge_base import KnowledgeBaseLayer
            self.knowledge_base = KnowledgeBaseLayer()
            logger.info("[EIAgent] FusionRAG KnowledgeBase 初始化成功")
        except Exception as e:
            logger.warning(f"[EIAgent] FusionRAG 初始化失败: {e}")
            self.knowledge_base = None
    
    async def execute_task(self, task: str, task_type: str = "unknown", params: dict = None) -> dict:
        """
        执行任务（带自我反思）
        
        Args:
            task: 任务描述
            task_type: 任务类型
            params: 任务参数
            
        Returns:
            执行结果
        """
        logger.info(f"[EIAgent] 执行任务: {task}")
        
        try:
            # 执行任务
            if task_type == "report_generation":
                result = await self._generate_report(params or {})
            elif task_type == "regulation_retrieval":
                result = await self._retrieve_regulations(params or {})
            else:
                result = {"status": "completed", "message": f"任务执行完成: {task}"}
            
            # 自我反思（如果启用了自我进化）
            if self.self_evolution_enabled and self.self_evolution_engine:
                logger.info(f"[EIAgent] 开始自我反思...")
                reflection = await self.self_evolution_engine.analyze_and_improve(task, result)
                
                logger.info(f"[EIAgent] 自我反思完成: success={reflection.get('reflection', {}).get('success')}")
                
                # 如果有创建的工具，添加到结果中
                if reflection.get("created_tools"):
                    result["created_tools"] = reflection["created_tools"]
            
            return result
            
        except Exception as e:
            logger.error(f"[EIAgent] 任务执行失败: {e}")
            
            # 自我反思（失败时更重要）
            if self.self_evolution_enabled and self.self_evolution_engine:
                logger.info(f"[EIAgent] 开始自我反思（失败）...")
                reflection = await self.self_evolution_engine.analyze_and_improve(
                    task, {"status": "failed", "error": str(e)}
                )
                return {
                    "status": "failed",
                    "error": str(e),
                    "reflection": reflection
                }
            
            return {"status": "failed", "error": str(e)}
    
    async def start_active_learning(self, max_iterations: int = 10):
        """
        开始主动学习
        
        Args:
            max_iterations: 最大迭代次数
        """
        if not self.self_evolution_enabled or not self.self_evolution_engine:
            logger.warning("[EIAgent] 自我进化未启用，无法开始主动学习")
            return
        
        logger.info(f"[EIAgent] 开始主动学习（最多 {max_iterations} 次迭代）...")
        await self.self_evolution_engine.start_active_learning(max_iterations)
    
    def enable_self_evolution(self, enabled: bool = True):
        """启用/禁用自我进化能力"""
        self.self_evolution_enabled = enabled
        logger.info(f"[EIAgent] 自我进化: {'启用' if enabled else '禁用'}")
    
    def get_self_evolution_status(self) -> dict:
        """获取自我进化状态"""
        if not self.self_evolution_engine:
            return {"enabled": False, "reason": "引擎未初始化"}
        
        return {
            "enabled": self.self_evolution_enabled,
            "engine_initialized": True,
        }
    
    # 任务执行方法（占位符）
    async def _generate_report(self, params: dict) -> dict:
        """生成环评报告"""
        logger.info(f"[EIAgent] 生成环评报告: {params.get('project_name', '')}")
        return {
            "status": "completed",
            "task_type": "report_generation",
            "project_name": params.get("project_name", ""),
        }
    
    async def _retrieve_regulations(self, params: dict) -> dict:
        """检索法规"""
        logger.info(f"[EIAgent] 检索法规: {params.get('query', '')}")
        
        results = []
        if self.knowledge_base:
            try:
                search_results = self.knowledge_base.search(
                    query=params.get("query", ""),
                    top_k=10
                )
                results = [{"content": r.get("content", "")} for r in search_results]
            except Exception as e:
                logger.error(f"[EIAgent] 法规检索失败: {e}")
        
        return {
            "status": "completed",
            "task_type": "regulation_retrieval",
            "count": len(results),
            "regulations": results
        }


async def test_ei_agent_with_self_evolution():
    """测试 EIAgent with Self-Evolution"""
    print("=" * 60)
    print("测试 EIAgent with Self-Evolution")
    print("=" * 60)
    
    # 创建 EIAgent
    print("\n1. 创建 EIAgent with Self-Evolution...")
    agent = EIAgentWithSelfEvolution()
    
    # 检查自我进化状态
    print("\n2. 检查自我进化状态...")
    status = agent.get_self_evolution_status()
    print(f"   状态: {status}")
    
    # 测试执行任务
    print("\n3. 测试执行任务（带自我反思）...")
    result = await agent.execute_task(
        task="获取苹果公司的财报数据并分析",
        task_type="report_generation",
        params={"project_name": "苹果公司分析"}
    )
    print(f"   结果: {result}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    asyncio.run(test_ei_agent_with_self_evolution())
