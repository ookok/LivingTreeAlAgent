"""
ThinOrchestrator - 薄编排器

实现 GSD 的薄编排器模式：
- 为每个任务生成具有新鲜上下文的专门代理
- 防止上下文腐烂（Context Rot）
- 提高代理决策质量

核心思想：协调器很薄，只负责生成专门代理，每个代理启动时上下文窗口是干净的

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
import asyncio
import time


class AgentType(Enum):
    """专门代理类型"""
    PLANNER = "planner"           # 规划代理
    PLAN_CHECKER = "plan_checker" # 计划检查代理
    EXECUTOR = "executor"         # 执行代理
    VERIFIER = "verifier"         # 验证代理
    DEBUGGER = "debugger"         # 调试代理
    CODE_REVIEWER = "code_reviewer" # 代码审查代理
    RESEARCHER = "researcher"     # 研究代理
    ANALYZER = "analyzer"         # 分析代理


class TaskStage(Enum):
    """任务阶段"""
    DISCUSS = "discuss"    # 需求讨论
    PLAN = "plan"          # 方案规划
    EXECUTE = "execute"    # 执行任务
    VERIFY = "verify"      # 验证结果


@dataclass
class TaskStep:
    """
    任务步骤
    
    代表任务的一个原子步骤。
    """
    step_id: str
    description: str
    stage: TaskStage
    agent_type: AgentType
    dependencies: List[str] = field(default_factory=list)
    status: str = "pending"
    result: Optional[Dict[str, Any]] = None


@dataclass
class TaskPlan:
    """
    任务计划
    
    包含多个步骤的完整计划。
    """
    plan_id: str
    task_description: str
    steps: List[TaskStep] = field(default_factory=list)
    created_at: float = field(default_factory=lambda: time.time())


@dataclass
class ExecutionResult:
    """
    执行结果
    """
    plan_id: str
    success: bool
    results: List[Dict[str, Any]] = field(default_factory=list)
    execution_time: float = 0.0


class SpecializedAgent:
    """
    专门代理
    
    为特定任务设计的代理，每个代理启动时上下文窗口是干净的。
    """
    
    def __init__(self, agent_type: AgentType, context: Dict[str, Any] = None):
        self._agent_type = agent_type
        self._context = context or {}
        self._logger = logger.bind(component=f"Agent_{agent_type.value}")
        
        # 初始化代理的专门能力
        self._init_capabilities()
        
        self._logger.debug(f"✅ 创建专门代理: {agent_type.value}")
    
    def _init_capabilities(self):
        """初始化代理能力"""
        self._capabilities = {
            AgentType.PLANNER: self._plan_task,
            AgentType.PLAN_CHECKER: self._check_plan,
            AgentType.EXECUTOR: self._execute_step,
            AgentType.VERIFIER: self._verify_result,
            AgentType.DEBUGGER: self._debug_problem,
            AgentType.CODE_REVIEWER: self._review_code,
            AgentType.RESEARCHER: self._research_topic,
            AgentType.ANALYZER: self._analyze_data,
        }
    
    async def execute(self, task: str) -> Dict[str, Any]:
        """
        执行任务
        
        Args:
            task: 任务描述
            
        Returns:
            执行结果
        """
        executor = self._capabilities.get(self._agent_type)
        if executor:
            return await executor(task)
        return {"error": f"未知代理类型: {self._agent_type}"}
    
    async def _plan_task(self, task: str) -> Dict[str, Any]:
        """规划任务"""
        self._logger.info(f"📋 规划任务: {task}")
        
        # 简化实现：生成任务计划
        steps = [
            {"step_id": "step_1", "description": "分析需求", "stage": "plan"},
            {"step_id": "step_2", "description": "设计方案", "stage": "plan"},
            {"step_id": "step_3", "description": "执行实现", "stage": "execute"},
            {"step_id": "step_4", "description": "验证结果", "stage": "verify"},
        ]
        
        return {"success": True, "plan": steps, "agent_type": self._agent_type.value}
    
    async def _check_plan(self, plan: str) -> Dict[str, Any]:
        """检查计划"""
        self._logger.info(f"🔍 检查计划")
        
        # 简化实现：模拟9维度验证
        checks = [
            {"dimension": "可行性", "status": "pass", "score": 0.9},
            {"dimension": "完整性", "status": "pass", "score": 0.85},
            {"dimension": "风险评估", "status": "pass", "score": 0.8},
            {"dimension": "资源需求", "status": "pass", "score": 0.95},
            {"dimension": "时间估算", "status": "pass", "score": 0.75},
        ]
        
        return {"success": True, "checks": checks, "agent_type": self._agent_type.value}
    
    async def _execute_step(self, step: str) -> Dict[str, Any]:
        """执行步骤"""
        self._logger.info(f"⚡ 执行步骤: {step}")
        
        # 简化实现：模拟执行
        await asyncio.sleep(0.5)  # 模拟执行时间
        
        return {"success": True, "output": f"执行结果: {step}", "agent_type": self._agent_type.value}
    
    async def _verify_result(self, result: str) -> Dict[str, Any]:
        """验证结果"""
        self._logger.info(f"✅ 验证结果")
        
        # 简化实现：模拟验证
        verification = {
            "goal_met": True,
            "quality_score": 0.92,
            "issues": [],
            "recommendations": [],
        }
        
        return {"success": True, "verification": verification, "agent_type": self._agent_type.value}
    
    async def _debug_problem(self, problem: str) -> Dict[str, Any]:
        """调试问题"""
        self._logger.info(f"🔧 调试问题: {problem}")
        
        return {"success": True, "analysis": "问题分析完成", "fix_suggestion": "建议修复方案", "agent_type": self._agent_type.value}
    
    async def _review_code(self, code: str) -> Dict[str, Any]:
        """代码审查"""
        self._logger.info(f"📝 代码审查")
        
        return {"success": True, "issues_found": 2, "suggestions": ["优化性能", "增加测试"], "agent_type": self._agent_type.value}
    
    async def _research_topic(self, topic: str) -> Dict[str, Any]:
        """研究主题"""
        self._logger.info(f"🔬 研究主题: {topic}")
        
        return {"success": True, "findings": ["发现1", "发现2", "发现3"], "sources": ["来源1", "来源2"], "agent_type": self._agent_type.value}
    
    async def _analyze_data(self, data: str) -> Dict[str, Any]:
        """分析数据"""
        self._logger.info(f"📊 分析数据")
        
        return {"success": True, "insights": ["洞察1", "洞察2"], "metrics": {"key": "value"}, "agent_type": self._agent_type.value}


class ThinOrchestrator:
    """
    薄编排器
    
    核心功能：
    1. 为每个任务生成具有新鲜上下文的专门代理
    2. 协调代理之间的工作流程
    3. 防止上下文腐烂
    
    工作流程：
    1. 规划阶段：生成计划（使用PlannerAgent）
    2. 执行阶段：为每个任务生成专门的Agent（新鲜上下文）
    3. 验证阶段：使用VerifierAgent（新鲜上下文）
    """
    
    def __init__(self):
        self._logger = logger.bind(component="ThinOrchestrator")
        
        # 代理工厂
        self._agent_factory = {
            AgentType.PLANNER: lambda ctx: SpecializedAgent(AgentType.PLANNER, ctx),
            AgentType.PLAN_CHECKER: lambda ctx: SpecializedAgent(AgentType.PLAN_CHECKER, ctx),
            AgentType.EXECUTOR: lambda ctx: SpecializedAgent(AgentType.EXECUTOR, ctx),
            AgentType.VERIFIER: lambda ctx: SpecializedAgent(AgentType.VERIFIER, ctx),
            AgentType.DEBUGGER: lambda ctx: SpecializedAgent(AgentType.DEBUGGER, ctx),
            AgentType.CODE_REVIEWER: lambda ctx: SpecializedAgent(AgentType.CODE_REVIEWER, ctx),
            AgentType.RESEARCHER: lambda ctx: SpecializedAgent(AgentType.RESEARCHER, ctx),
            AgentType.ANALYZER: lambda ctx: SpecializedAgent(AgentType.ANALYZER, ctx),
        }
        
        # 执行历史
        self._execution_history: List[ExecutionResult] = []
        
        self._logger.info("✅ ThinOrchestrator 初始化完成")
    
    def _create_agent(self, agent_type: AgentType, context: Dict[str, Any] = None) -> SpecializedAgent:
        """
        创建专门代理（新鲜上下文）
        
        Args:
            agent_type: 代理类型
            context: 上下文信息
            
        Returns:
            专门代理实例（带有新鲜上下文）
        """
        factory = self._agent_factory.get(agent_type)
        if factory:
            # 每个代理获得专门的、干净的上下文
            return factory(context or {})
        raise ValueError(f"未知代理类型: {agent_type}")
    
    async def execute_task(self, task_description: str) -> ExecutionResult:
        """
        执行任务（完整流程）
        
        Args:
            task_description: 任务描述
            
        Returns:
            执行结果
        """
        start_time = time.time()
        plan_id = f"plan_{int(time.time())}"
        
        self._logger.info(f"🚀 开始执行任务: {task_description}")
        
        try:
            # ========== 阶段1: 规划 ==========
            self._logger.info("📋 阶段1: 规划")
            planner = self._create_agent(AgentType.PLANNER, {"task": task_description})
            plan_result = await planner.execute(task_description)
            
            if not plan_result.get("success"):
                return ExecutionResult(
                    plan_id=plan_id,
                    success=False,
                    results=[plan_result],
                    execution_time=time.time() - start_time
                )
            
            # ========== 阶段2: 计划检查 ==========
            self._logger.info("🔍 阶段2: 计划检查")
            plan_checker = self._create_agent(AgentType.PLAN_CHECKER, {"plan": plan_result})
            check_result = await plan_checker.execute(str(plan_result))
            
            if not check_result.get("success"):
                return ExecutionResult(
                    plan_id=plan_id,
                    success=False,
                    results=[plan_result, check_result],
                    execution_time=time.time() - start_time
                )
            
            # ========== 阶段3: 执行 ==========
            self._logger.info("⚡ 阶段3: 执行")
            results = [plan_result, check_result]
            steps = plan_result.get("plan", [])
            
            for step in steps:
                executor = self._create_agent(AgentType.EXECUTOR, {"step": step})
                step_result = await executor.execute(step.get("description", str(step)))
                results.append(step_result)
                
                if not step_result.get("success"):
                    # 如果步骤失败，调用调试代理
                    debugger = self._create_agent(AgentType.DEBUGGER, {"problem": step_result})
                    debug_result = await debugger.execute(str(step_result))
                    results.append(debug_result)
            
            # ========== 阶段4: 验证 ==========
            self._logger.info("✅ 阶段4: 验证")
            verifier = self._create_agent(AgentType.VERIFIER, {"results": results})
            verify_result = await verifier.execute(str(results))
            results.append(verify_result)
            
            execution_time = time.time() - start_time
            
            self._logger.info(f"🎉 任务执行完成 (耗时: {execution_time:.2f}s)")
            
            # 保存执行历史
            execution_result = ExecutionResult(
                plan_id=plan_id,
                success=True,
                results=results,
                execution_time=execution_time
            )
            self._execution_history.append(execution_result)
            
            return execution_result
        
        except Exception as e:
            execution_time = time.time() - start_time
            self._logger.error(f"❌ 任务执行失败: {e}")
            
            return ExecutionResult(
                plan_id=plan_id,
                success=False,
                results=[{"error": str(e)}],
                execution_time=execution_time
            )
    
    async def execute_stage(self, task_description: str, stage: TaskStage) -> Dict[str, Any]:
        """
        执行单个阶段
        
        Args:
            task_description: 任务描述
            stage: 阶段
            
        Returns:
            阶段执行结果
        """
        stage_agent_map = {
            TaskStage.DISCUSS: AgentType.RESEARCHER,
            TaskStage.PLAN: AgentType.PLANNER,
            TaskStage.EXECUTE: AgentType.EXECUTOR,
            TaskStage.VERIFY: AgentType.VERIFIER,
        }
        
        agent_type = stage_agent_map.get(stage)
        if not agent_type:
            return {"error": f"未知阶段: {stage}"}
        
        agent = self._create_agent(agent_type, {"task": task_description})
        return await agent.execute(task_description)
    
    def get_execution_history(self) -> List[ExecutionResult]:
        """获取执行历史"""
        return self._execution_history
    
    def get_available_agents(self) -> List[str]:
        """获取可用代理列表"""
        return [agent_type.value for agent_type in AgentType]


# 创建全局实例
thin_orchestrator = ThinOrchestrator()


def get_thin_orchestrator() -> ThinOrchestrator:
    """获取薄编排器实例"""
    return thin_orchestrator


# 测试函数
async def test_thin_orchestrator():
    """测试薄编排器"""
    import sys
    logger.remove()
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)
    
    print("=" * 60)
    print("测试 ThinOrchestrator")
    print("=" * 60)
    
    orchestrator = ThinOrchestrator()
    
    # 1. 测试可用代理
    print("\n[1] 测试可用代理...")
    agents = orchestrator.get_available_agents()
    print(f"    ✓ 可用代理数: {len(agents)}")
    print(f"    ✓ 代理列表: {agents}")
    
    # 2. 测试执行单个阶段
    print("\n[2] 测试执行单个阶段...")
    result = await orchestrator.execute_stage("分析数据", TaskStage.DISCUSS)
    print(f"    ✓ 阶段执行结果: {result.get('success')}")
    print(f"    ✓ 代理类型: {result.get('agent_type')}")
    
    # 3. 测试完整任务执行
    print("\n[3] 测试完整任务执行...")
    result = await orchestrator.execute_task("创建一个数据分析报告")
    print(f"    ✓ 任务执行成功: {result.success}")
    print(f"    ✓ 执行耗时: {result.execution_time:.2f}s")
    print(f"    ✓ 步骤数: {len(result.results)}")
    
    # 4. 测试执行历史
    print("\n[4] 测试执行历史...")
    history = orchestrator.get_execution_history()
    print(f"    ✓ 执行历史记录数: {len(history)}")
    
    print("\n" + "=" * 60)
    print("🎉 所有测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_thin_orchestrator())