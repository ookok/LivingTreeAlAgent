"""
多Agent编排器 (Multi-Agent Orchestrator)
遵循自我进化原则：从任务执行中学习最优协作模式，而非预置固定流程

架构指南参考: docs/LIVINGTREE_ARCHITECTURE_GUIDE.md (章节 5.4.2)

核心借鉴: Rowboat (匹配度60%, 借鉴性75%)
- Agent团队协作模式
- 动态任务分解
- 并行执行与结果整合
"""
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from pathlib import Path
import json
import logging
import asyncio
from enum import Enum

from client.src.business.global_model_router import GlobalModelRouter, ModelCapability
from client.src.business.hermes_agent.intent_recognizer import Intent


logger = logging.getLogger(__name__)


class AgentRole(Enum):
    """Agent角色 - 从学习中扩展"""
    COORDINATOR = "coordinator"  # 协调者
    SPECIALIST = "specialist"    # 专业者
    REVIEWER = "reviewer"      # 审核者
    SYNTHESIZER = "synthesizer"  # 整合者


@dataclass
class Agent:
    """Agent定义 - 从学习中优化"""
    name: str
    role: AgentRole
    capabilities: List[str] = field(default_factory=list)
    success_rate: float = 0.0
    total_tasks: int = 0
    avg_execution_time: float = 0.0

    def update_performance(self, success: bool, execution_time: float):
        """更新性能统计"""
        self.total_tasks += 1
        if success:
            self.success_rate = (self.success_rate * (self.total_tasks - 1) + 1.0) / self.total_tasks
        else:
            self.success_rate = (self.success_rate * (self.total_tasks - 1)) / self.total_tasks
        
        # 更新平均执行时间
        self.avg_execution_time = (
            self.avg_execution_time * (self.total_tasks - 1) + execution_time
        ) / self.total_tasks


@dataclass
class SubTask:
    """子任务"""
    id: str
    description: str
    assigned_agent: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    result: Optional[Any] = None
    status: str = "pending"  # pending, running, completed, failed


class MultiAgentOrchestrator:
    """
    多Agent编排器

    核心原则：
    ❌ 不预置固定的Agent协作流程
    ✅ 从任务中动态分解子任务
    ✅ 学习任务与Agent的最佳匹配
    ✅ 动态优化协作模式
    ✅ 记录执行结果，持续进化

    协作流程：
    1. 分解任务到子任务
    2. 分配给专业Agent
    3. 并行执行
    4. 整合结果
    5. 学习优化
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.router = GlobalModelRouter()
        self.storage_path = storage_path or Path.home() / ".livingtree" / "multi_agent_orch.json"
        
        # 注册的Agent
        self.agents: Dict[str, Agent] = {}
        
        # 任务分配历史（从学习中优化）
        self.task_agent_mapping: Dict[str, List[str]] = {}  # task_type -> [agent_names]
        
        # 协作模式（从学习中识别）
        self.collaboration_patterns: Dict[str, Dict[str, Any]] = {}
        
        self._load_orch_data()

    def _load_orch_data(self):
        """加载编排数据"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # 加载Agent
                    for agent_data in data.get("agents", []):
                        agent = Agent(**agent_data)
                        self.agents[agent.name] = agent
                    
                    self.task_agent_mapping = data.get("task_agent_mapping", {})
                    self.collaboration_patterns = data.get("collaboration_patterns", {})
                
                logger.info(f"✅ 已加载 {len(self.agents)} 个Agent，{len(self.task_agent_mapping)} 个任务映射")
            except Exception as e:
                logger.warning(f"⚠️ 加载编排数据失败: {e}")

    def _save_orch_data(self):
        """保存编排数据"""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                "agents": [
                    {
                        "name": a.name,
                        "role": a.role.value,
                        "capabilities": a.capabilities,
                        "success_rate": a.success_rate,
                        "total_tasks": a.total_tasks,
                        "avg_execution_time": a.avg_execution_time
                    }
                    for a in self.agents.values()
                ],
                "task_agent_mapping": self.task_agent_mapping,
                "collaboration_patterns": self.collaboration_patterns
            }
            
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"❌ 保存编排数据失败: {e}")

    async def orchestrate(self, task: str) -> Dict[str, Any]:
        """
        多Agent编排入口

        流程：
        1. 分解任务到子任务
        2. 分配给专业Agent
        3. 并行执行
        4. 整合结果
        5. 学习优化
        """
        logger.info(f"🎭 开始多Agent编排: {task[:50]}...")

        # 1. 分解任务
        subtasks = await self._decompose(task)
        logger.info(f"  📋 分解出 {len(subtasks)} 个子任务")

        # 2. 分配Agent
        assignments = await self._assign_agents(subtasks)
        logger.info(f"  👥 分配给 {len(set(a['agent'] for a in assignments))} 个Agent")

        # 3. 并行执行
        results = await self._execute_parallel(assignments)
        logger.info(f"  ⚡ 执行完成，成功 {sum(1 for r in results if r['status'] == 'completed')}/{len(results)}")

        # 4. 整合结果
        synthesized = await self._synthesize(task, results)

        # 5. 学习优化
        await self._learn_from_execution(task, subtasks, assignments, results)

        self._save_orch_data()

        return {
            "task": task,
            "subtasks": [st.__dict__ for st in subtasks],
            "results": results,
            "synthesized_result": synthesized,
            "success_rate": sum(1 for r in results if r['status'] == 'completed') / len(results)
        }

    async def _decompose(self, task: str) -> List[SubTask]:
        """
        分解任务

        学习型实现：
        - 先尝试匹配已学习的分解模式
        - 如果未学习，使用LLM分解
        - 记录新模式
        """
        # 尝试匹配已学习的模式
        task_type = self._identify_task_type(task)
        
        if task_type in self.collaboration_patterns:
            pattern = self.collaboration_patterns[task_type]
            logger.info(f"🎯 使用已学习分解模式: {task_type}")
            
            # 使用学习的模式生成子任务
            subtasks = []
            for i, step in enumerate(pattern.get("decomposition", [])):
                subtasks.append(SubTask(
                    id=f"st_{i}",
                    description=step["description"],
                    dependencies=step.get("dependencies", [])
                ))
            
            return subtasks

        # 未学习，使用LLM分解
        logger.info(f"🧠 学习新分解模式: {task_type}")
        
        prompt = f"""
作为一个任务分解专家，将以下任务分解为子任务。

任务: {task}

要求：
1. 分解为 3-7 个子任务
2. 明确子任务间的依赖关系
3. 每个子任务应该是独立的
4. 返回 JSON 格式。

返回格式:
{{
    "decomposition": [
        {{"description": "子任务1描述", "dependencies": []}},
        {{"description": "子任务2描述", "dependencies": ["st_0"]}},
        ...
    ]
}}

只返回 JSON，不要有其他内容。
"""

        try:
            response = self.router.call_model_sync(
                capability=ModelCapability.REASONING,
                prompt=prompt,
                temperature=0.2
            )
            result = json.loads(response)

            subtasks = []
            for i, step in enumerate(result.get("decomposition", [])):
                subtasks.append(SubTask(
                    id=f"st_{i}",
                    description=step["description"],
                    dependencies=step.get("dependencies", [])
                ))

            # 学习新模式
            if task_type not in self.collaboration_patterns:
                self.collaboration_patterns[task_type] = {
                    "decomposition": result["decomposition"],
                    "usage_count": 1,
                    "success_rate": 0.5
                }
            else:
                self.collaboration_patterns[task_type]["usage_count"] += 1

            return subtasks

        except Exception as e:
            logger.error(f"❌ 任务分解失败: {e}")
            # 兜底：单个子任务
            return [SubTask(id="st_0", description=task)]

    def _identify_task_type(self, task: str) -> str:
        """识别任务类型"""
        task_lower = task.lower()

        if any(kw in task_lower for kw in ["分析", "analyze", "analysis"]):
            return "analysis"
        elif any(kw in task_lower for kw in ["生成", "创建", "create", "generate"]):
            return "generation"
        elif any(kw in task_lower for kw in ["搜索", "查找", "search"]):
            return "search"
        else:
            return "general"

    async def _assign_agents(self, subtasks: List[SubTask]) -> List[Dict[str, Any]]:
        """
        分配Agent

        学习型实现：
        - 根据子任务描述，选择最合适的Agent
        - 从任务-Agent映射中学习
        - 考虑Agent的性能和可用性
        """
        assignments = []

        for subtask in subtasks:
            # 选择Agent
            agent_name = await self._select_agent(subtask)
            
            assignments.append({
                "subtask_id": subtask.id,
                "subtask_description": subtask.description,
                "agent": agent_name
            })

            subtask.assigned_agent = agent_name

        return assignments

    async def _select_agent(self, subtask: SubTask) -> str:
        """选择最合适的Agent"""
        # 如果还没有注册的Agent，创建默认Agent
        if not self.agents:
            self._create_default_agents()

        # 使用LLM选择
        agent_descriptions = [
            f"{name}: {agent.role.value} (成功率: {agent.success_rate:.2%})"
            for name, agent in self.agents.items()
        ]

        prompt = f"""
作为一个Agent选择专家，为以下子任务选择最合适的Agent。

子任务: {subtask.description}
可用Agent:
{chr(10).join(agent_descriptions)}

要求：
1. 选择最适合的Agent
2. 考虑Agent的角色和能力
3. 返回 JSON 格式。

返回格式:
{{
    "selected_agent": "agent_name",
    "reason": "选择理由"
}}

只返回 JSON，不要有其他内容。
"""

        try:
            response = self.router.call_model_sync(
                capability=ModelCapability.REASONING,
                prompt=prompt,
                temperature=0.1
            )
            result = json.loads(response)
            agent_name = result.get("selected_agent", "")

            if agent_name in self.agents:
                return agent_name
        except Exception as e:
            logger.error(f"❌ 选择Agent失败: {e}")

        # 兜底：选择第一个Agent
        return list(self.agents.keys())[0] if self.agents else "default"

    def _create_default_agents(self):
        """创建默认Agent"""
        self.agents["coordinator"] = Agent(
            name="coordinator",
            role=AgentRole.COORDINATOR,
            capabilities=["task_decomposition", "result_synthesis"]
        )
        self.agents["specialist"] = Agent(
            name="specialist",
            role=AgentRole.SPECIALIST,
            capabilities=["domain_expertise", "detailed_analysis"]
        )
        self.agents["reviewer"] = Agent(
            name="reviewer",
            role=AgentRole.REVIEWER,
            capabilities=["quality_check", "error_detection"]
        )
        logger.info(f"✅ 已创建 {len(self.agents)} 个默认Agent")

    async def _execute_parallel(self, assignments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        并行执行子任务

        学习型实现：
        - 考虑依赖关系
        - 并行执行无依赖的任务
        - 记录执行时间
        """
        results = []

        # 简化：串行执行（实际应该并行）
        for assignment in assignments:
            start_time = asyncio.get_event_loop().time()

            # 模拟执行
            agent_name = assignment["agent"]
            subtask_desc = assignment["subtask_description"]

            logger.info(f"  🔧 Agent [{agent_name}] 执行: {subtask_desc[:30]}...")

            # 模拟执行时间
            await asyncio.sleep(0.1)
            execution_time = asyncio.get_event_loop().time() - start_time

            # 模拟结果
            result = {
                "subtask_id": assignment["subtask_id"],
                "agent": agent_name,
                "result": f"模拟执行结果: {subtask_desc}",
                "status": "completed",
                "execution_time": execution_time
            }

            results.append(result)

            # 更新Agent性能
            if agent_name in self.agents:
                self.agents[agent_name].update_performance(True, execution_time)

        return results

    async def _synthesize(self, task: str, results: List[Dict[str, Any]]) -> str:
        """整合结果"""
        prompt = f"""
作为一个结果整合专家，整合以下子任务的结果。

原始任务: {task}

子任务结果:
{chr(10).join(f"{i+1}. [{r['agent']}] {r['result']}" for i, r in enumerate(results))}

要求：
1. 整合所有子任务的结果
2. 生成最终的完整结果
3. 返回整合后的结果文本。

只返回整合结果，不要有其他内容。
"""

        try:
            synthesized = self.router.call_model_sync(
                capability=ModelCapability.REASONING,
                prompt=prompt,
                temperature=0.3
            )
            return synthesized
        except Exception as e:
            logger.error(f"❌ 结果整合失败: {e}")
            return f"整合失败: {str(e)}"

    async def _learn_from_execution(
        self,
        task: str,
        subtasks: List[SubTask],
        assignments: List[Dict[str, Any]],
        results: List[Dict[str, Any]]
    ):
        """从执行中学习，优化编排策略"""
        task_type = self._identify_task_type(task)
        success_rate = sum(1 for r in results if r['status'] == 'completed') / len(results)

        # 更新协作模式
        if task_type in self.collaboration_patterns:
            pattern = self.collaboration_patterns[task_type]
            old_success_rate = pattern.get("success_rate", 0.5)
            
            # 更新成功率
            pattern["success_rate"] = (
                old_success_rate * pattern.get("usage_count", 1) + success_rate
            ) / (pattern.get("usage_count", 1) + 1)
            
            pattern["usage_count"] = pattern.get("usage_count", 1) + 1

            logger.info(f"📈 更新协作模式: {task_type} 成功率 {pattern['success_rate']:.2%}")

    async def register_agent(self, name: str, role: AgentRole, capabilities: List[str]) -> bool:
        """注册新Agent"""
        if name in self.agents:
            logger.warning(f"⚠️ Agent已存在: {name}")
            return False

        self.agents[name] = Agent(
            name=name,
            role=role,
            capabilities=capabilities
        )

        self._save_orch_data()
        logger.info(f"✅ 已注册Agent: {name} ({role.value})")
        return True

    async def get_orchestrator_stats(self) -> Dict[str, Any]:
        """获取编排统计"""
        if not self.agents:
            return {"total_agents": 0}

        return {
            "total_agents": len(self.agents),
            "total_patterns": len(self.collaboration_patterns),
            "agent_stats": [
                {
                    "name": a.name,
                    "role": a.role.value,
                    "success_rate": round(a.success_rate, 2),
                    "total_tasks": a.total_tasks,
                    "avg_execution_time": round(a.avg_execution_time, 2)
                }
                for a in sorted(self.agents.values(), key=lambda x: x.success_rate, reverse=True)
            ],
            "collaboration_patterns": [
                {
                    "task_type": task_type,
                    "usage_count": pattern.get("usage_count", 0),
                    "success_rate": round(pattern.get("success_rate", 0), 2)
                }
                for task_type, pattern in self.collaboration_patterns.items()
            ]
        }
