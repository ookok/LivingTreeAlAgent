"""
EIAgent 适配器 - 接入系统 Agent 架构
==============================================

让 EIAgent 作为系统 AgentOrchestrator 中的一个 Agent 节点，
复用 FusionRAG（IntelligentRouter）做知识库，复用 TrainingAgent 做专家训练。

架构：
- EIAgent 注册为 AgentType.EIA
- 使用 FusionRAG.KnowledgeBaseLayer 做知识库检索
- 使用 TrainingAgent 做专家训练（复用系统成熟框架）
- 使用 ScraplingEngine 做爬虫（通过 ecological_environment_crawler）
"""

import os
import sys
import json
import logging
import asyncio
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

# 确保项目根目录在 sys.path 中
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from business.agent_orchestration import (
    AgentType, AgentCapability, Agent, AgentFactory,
    AgentOrchestrator, TaskContext, TaskStatus, TaskPriority,
    get_orchestrator,
    TaskExecutor  # 正确的基类名称
)
from business.nanochat_config import config as app_config

# 导入统一工具层（Phase 3 新增）
from business.base_agents.base_agent import BaseToolAgent, ToolCallResult
from business.tools.register_all_tools import register_all_tools

logger = logging.getLogger(__name__)

# 导入自我进化引擎
try:
    from business.self_evolution import SelfEvolutionEngine
    from business.self_evolution.tool_missing_detector import ToolMissingDetector
    from business.self_evolution.self_reflection_engine import SelfReflectionEngine
    SELF_EVOLUTION_AVAILABLE = True
    print('[EIAgent] 自我进化引擎导入成功')
except ImportError as e:
    print(f'[EIAgent] 自我进化引擎导入失败: {e}')
    SELF_EVOLUTION_AVAILABLE = False




# ── EIAgent 执行器 ─────────────────────────────────────────────────────────────

class EIAgentExecutor(TaskExecutor):
    """
    EIAgent 任务执行器
    负责执行环评相关的任务（报告生成、法规检索、排污系数查询等）
    复用系统 FusionRAG 做知识库，复用 TrainingAgent 做专家训练
    """

    def __init__(self):
        self._running_tasks: Dict[str, asyncio.Task] = {}
        
        # 初始化统一工具层（Phase 3 新增）
        # 自动注册所有 BaseTool 子类工具
        try:
            register_all_tools()
            logger.info("[EIAgentExecutor] 统一工具层初始化成功")
        except Exception as e:
            logger.warning(f"[EIAgentExecutor] 统一工具层初始化失败: {e}")
        
        # 注入 BaseToolAgent 能力
        self._tool_agent = BaseToolAgent(enabled_toolsets=["core", "geospatial", "eia"])

        # 初始化 FusionRAG 知识库
        try:
            from business.fusion_rag.knowledge_base import KnowledgeBaseLayer
            self.knowledge_base = KnowledgeBaseLayer()
            logger.info("[EIAgentExecutor] FusionRAG KnowledgeBase 初始化成功")
        except Exception as e:
            logger.warning(f"[EIAgentExecutor] FusionRAG 初始化失败: {e}")
            self.knowledge_base = None

        # 初始化 TrainingAgent（专家训练）
        try:
            from business.training_agent import TrainingAgent
            self.training_agent = TrainingAgent(config=app_config)
            logger.info("[EIAgentExecutor] TrainingAgent 初始化成功")
        except Exception as e:
            logger.warning(f"[EIAgentExecutor] TrainingAgent 初始化失败: {e}")
            self.training_agent = None

        # 初始化自我进化引擎
        if 'SELF_EVOLUTION_AVAILABLE' in globals() and SELF_EVOLUTION_AVAILABLE:
            try:
                from business.self_evolution import SelfEvolutionEngine
                self.self_evolution_engine = SelfEvolutionEngine()
                self.self_evolution_enabled = True
                logger.info("[EIAgentExecutor] 自我进化引擎初始化成功")
            except Exception as e:
                logger.warning(f"[EIAgentExecutor] 自我进化引擎初始化失败: {e}")
                self.self_evolution_engine = None
                self.self_evolution_enabled = False
        else:
            self.self_evolution_engine = None
            self.self_evolution_enabled = False

    async def execute(self, task: TaskContext, agent: Agent) -> Any:
        """
        执行环评任务
        根据 task.description 和 task.params 决定具体执行什么
        """
        logger.info(f"[EIAgent] 执行任务: {task.task_id} - {task.description}")

        task_type = task.params.get("task_type", "unknown")
        params = task.params.get("params", {})

        try:
            if task_type == "report_generation":
                result = await self._generate_report(params)
            elif task_type == "regulation_retrieval":
                result = await self._retrieve_regulations(params)
            elif task_type == "pollution_coefficient":
                result = await self._query_pollution_coefficient(params)
            elif task_type == "attachment_parsing":
                result = await self._parse_attachment(params)
            elif task_type == "environmental_impact_assessment":
                result = await self._assess_environmental_impact(params)
            elif task_type == "risk_assessment":
                result = await self._assess_risk(params)
            elif task_type == "expert_training":
                result = await self._run_expert_training(params)
            else:
                result = {"error": f"未知任务类型: {task_type}"}

            logger.info(f"[EIAgent] 任务完成: {task.task_id}")

            # 自我反思（如果启用了自我进化）
            if hasattr(self, 'self_evolution_enabled') and self.self_evolution_enabled:
                try:
                    reflection = await self.self_evolution_engine.reflect_on_task_execution(
                        task.description, result
                    )
                    logger.info(f"[EIAgent] 自我反思完成: success={reflection.get('success')}")
                    
                    # 如果发现能力缺失，尝试创建工具
                    if reflection.get("missing_capabilities"):
                        logger.info(f"[EIAgent] 发现能力缺失: {reflection['missing_capabilities']}")
                except Exception as e:
                    logger.error(f"[EIAgent] 自我反思失败: {e}")
            
            return result

        except Exception as e:
            logger.error(f"[EIAgent] 任务失败: {task.task_id} - {e}")
            return {"error": str(e)}


    # ── 自我进化控制 ─────────────────────────────────────────────────────
    
    def enable_self_evolution(self, enabled: bool = True):
        """启用/禁用自我进化能力"""
        self.self_evolution_enabled = enabled
        if enabled and self.self_evolution_engine is None:
            try:
                from business.self_evolution import SelfEvolutionEngine
                self.self_evolution_engine = SelfEvolutionEngine()
                logger.info("[EIAgentExecutor] 自我进化引擎已启用")
            except Exception as e:
                logger.error(f"[EIAgent] 启用自我进化失败: {e}")
                self.self_evolution_enabled = False
        else:
            logger.info(f"[EIAgent] 自我进化: {'启用' if enabled else '禁用'}")
    
    async def start_active_learning(self, max_iterations: int = 10):
        """开始主动学习（如果启用了自我进化）"""
        if not hasattr(self, 'self_evolution_enabled') or not self.self_evolution_enabled:
            logger.warning("[EIAgent] 自我进化未启用，无法开始主动学习")
            return
        
        if self.self_evolution_engine is None:
            logger.warning("[EIAgent] 自我进化引擎未初始化")
            return
        
        try:
            await self.self_evolution_engine.start_active_learning(max_iterations)
            logger.info("[EIAgent] 主动学习完成")
        except Exception as e:
            logger.error(f"[EIAgent] 主动学习失败: {e}")
    
    def get_self_evolution_status(self) -> dict:
        """获取自我进化状态"""
        return {
            "enabled": getattr(self, 'self_evolution_enabled', False),
            "engine_initialized": self.self_evolution_engine is not None,
            "reflection_history_count": len(getattr(self.self_evolution_engine, '_reflection_history', []))
        }

    async def cancel(self, task_id: str) -> bool:
        """取消任务"""
        if task_id in self._running_tasks:
            self._running_tasks[task_id].cancel()
            del self._running_tasks[task_id]
            return True
        return False

    # ── 统一工具层接口 (Phase 3) ─────────────────────────────────────

    def discover_tools(self, task: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        语义搜索发现适合环评任务的工具。
        
        可以发现：大气扩散模型、距离计算、地图API、高程数据、OCR等。
        
        Args:
            task: 任务描述
            max_results: 最大返回数量
            
        Returns:
            工具定义列表
        """
        return self._tool_agent.discover_tools(task, max_results=max_results)
    
    async def execute_tool_async(
        self,
        tool_name: str,
        context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> ToolCallResult:
        """
        异步执行工具（EIAgent 主用方法）。
        
        环评任务大多涉及文件 I/O 和网络请求，使用异步接口更高效。
        
        Args:
            tool_name: 工具名称
            context: 可选上下文
            **kwargs: 工具参数
            
        Returns:
            ToolCallResult
        """
        return await self._tool_agent.execute_tool_async(tool_name, context, **kwargs)
    
    def execute_tool(self, tool_name: str, **kwargs) -> ToolCallResult:
        """
        同步执行工具。
        
        Args:
            tool_name: 工具名称
            **kwargs: 工具参数
            
        Returns:
            ToolCallResult
        """
        return self._tool_agent.execute_tool(tool_name, **kwargs)
    
    def get_tool_stats(self) -> Dict[str, Any]:
        """获取工具使用统计"""
        return self._tool_agent.get_tool_stats()
    
    def get_tool_descriptions(self) -> str:
        """获取工具描述文本"""
        return self._tool_agent.get_tool_descriptions()

    # ── 知识库检索（复用 FusionRAG）────────────────────────────────────────────

    async def _retrieve_regulations(self, params: Dict) -> Dict:
        """检索法规（复用 FusionRAG）"""
        query = params.get("query", "")
        logger.info(f"[EIAgent] 检索法规: {query}")

        results = []
        if self.knowledge_base:
            try:
                # 使用 FusionRAG 知识库检索
                # search() 返回格式：
                # [{"id", "doc_id", "title", "content", "type", "score", ...}]
                search_results = self.knowledge_base.search(
                    query=query,
                    top_k=10,
                    doc_type="regulation"  # 只搜索法规类型
                )
                results = [
                    {
                        "id": r.get("id", ""),
                        "doc_id": r.get("doc_id", ""),
                        "title": r.get("title", ""),
                        "content": r.get("content", ""),
                        "type": r.get("type", ""),
                        "score": r.get("score", 0.0),
                        "source": f"doc_id: {r.get('doc_id', '')}",
                        "metadata": {}
                    }
                    for r in search_results
                ]
                logger.info(f"[EIAgent] 检索到 {len(results)} 条法规")
            except Exception as e:
                logger.error(f"[EIAgent] 法规检索失败: {e}")

        return {
            "status": "completed",
            "task_type": "regulation_retrieval",
            "query": query,
            "regulations": results,
            "count": len(results)
        }

    async def _query_pollution_coefficient(self, params: Dict) -> Dict:
        """查询排污系数（复用系统数据）"""
        industry = params.get("industry", "")
        pollutant = params.get("pollutant", "")
        logger.info(f"[EIAgent] 查询排污系数: {industry} - {pollutant}")

        # 从 data/pollution_coefficients.json 中查询
        data_file = os.path.join(os.path.dirname(__file__), "data", "pollution_coefficients.json")
        coefficient = None

        try:
            if os.path.exists(data_file):
                with open(data_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # 根据行业查找排污系数
                    for item in data.get("industries", []):
                        if item.get("name") == industry:
                            for p in item.get("pollutants", []):
                                if p.get("name") == pollutant:
                                    coefficient = p.get("coefficient")
                                    break
                            break
        except Exception as e:
            logger.error(f"[EIAgent] 查询排污系数失败: {e}")

        return {
            "status": "completed",
            "task_type": "pollution_coefficient",
            "industry": industry,
            "pollutant": pollutant,
            "coefficient": coefficient
        }

    # ── 报告生成 ─────────────────────────────────────────────────────────────

    async def _generate_report(self, params: Dict) -> Dict:
        """
        生成环评报告 - Phase 3 增强版。
        
        使用统一工具层：
        - intelligent_ocr: 附件识别
        - markitdown_converter: 模板转换
        """
        project_name = params.get("project_name", "")
        industry = params.get("industry", "")
        template_path = params.get("template_path", "")
        attachments = params.get("attachments", [])
        logger.info(f"[EIAgent] 生成环评报告: {project_name} ({industry})")

        # 1. 使用 FusionRAG 检索相关法规和模板
        regulations = await self._retrieve_regulations({"query": f"{industry} 环评 法规"})

        results = {
            "status": "completed",
            "task_type": "report_generation",
            "project_name": project_name,
            "industry": industry,
            "regulations_count": regulations.get("count", 0),
            "tools_used": [],
        }
        
        # 2. 解析附件（使用工具层）
        parsed_attachments = []
        for attachment in attachments[:3]:  # 最多3个附件
            file_path = attachment.get("path", "")
            if not file_path:
                continue
            try:
                parse_result = self.execute_tool(
                    "intelligent_ocr",
                    file_path=file_path,
                )
                if parse_result.success:
                    parsed_attachments.append({
                        "file": file_path,
                        "content": parse_result.data,
                    })
                    results["tools_used"].append("intelligent_ocr")
            except Exception as e:
                logger.warning(f"[EIAgent] 附件解析失败 {file_path}: {e}")
        
        results["parsed_attachments"] = parsed_attachments
        results["report_path"] = f"/path/to/report/{project_name}.docx"  # TODO: 接入 Word 模板生成
        results["message"] = "报告生成完成（附件已解析，待接入 Word 模板引擎）"
        
        return results

    # ── 附件解析 ─────────────────────────────────────────────────────────────

    async def _parse_attachment(self, params: Dict) -> Dict:
        """
        解析附件（PDF/Word/Excel）- Phase 3 增强版。
        
        使用统一工具层调用 intelligent_ocr 工具。
        支持格式：.pdf, .doc, .docx, .xls, .xlsx
        """
        file_path = params.get("file_path", "")
        logger.info(f"[EIAgent] 解析附件: {file_path}")

        result = {
            "status": "completed",
            "task_type": "attachment_parsing",
            "file_path": file_path,
            "parsed_content": "",
            "tools_used": [],
        }
        
        if not file_path:
            result["message"] = "未提供文件路径"
            return result
        
        # 使用 intelligent_ocr 工具解析文档
        try:
            ocr_result = self.execute_tool(
                "intelligent_ocr",
                file_path=file_path,
            )
            
            if ocr_result.success:
                result["parsed_content"] = ocr_result.data
                result["tools_used"].append("intelligent_ocr")
                result["message"] = f"附件解析成功（工具：intelligent_ocr，耗时 {ocr_result.duration_ms:.0f}ms）"
                logger.info(f"[EIAgent] intelligent_ocr 成功: {file_path}")
            else:
                result["message"] = f"附件解析失败: {ocr_result.error}"
                logger.warning(f"[EIAgent] intelligent_ocr 失败: {ocr_result.error}")
                
        except Exception as e:
            result["message"] = f"附件解析异常: {str(e)}"
            logger.error(f"[EIAgent] 附件解析异常: {e}")
        
        return result

    # ── 环境影响评估 ─────────────────────────────────────────────────────────

    async def _assess_environmental_impact(self, params: Dict) -> Dict:
        """
        环境影响评估 - Phase 3 增强版。
        
        使用统一工具层调用专业计算工具：
        - AermodTool: 大气扩散模型（Gaussian plume）
        - DistanceTool: 敏感点距离计算
        - MapAPITool: 坐标解析与地理编码
        """
        project_name = params.get("project_name", "")
        logger.info(f"[EIAgent] 环境影响评估: {project_name}")
        
        # 提取环评关键参数
        source_x = params.get("source_x")  # 污染源经度
        source_y = params.get("source_y")  # 污染源纬度
        source_z = params.get("source_z", 10.0)  # 源高(m)
        emission_rate = params.get("emission_rate", 1.0)  # 排放率(g/s)
        wind_speed = params.get("wind_speed", 2.0)  # 风速(m/s)
        receptor_points = params.get("receptor_points", [])  # 敏感点列表
        
        results = {
            "status": "pending",
            "task_type": "environmental_impact_assessment",
            "project_name": project_name,
            "calculations": {},
            "tools_used": [],
        }
        
        # 1. 尝试使用 AermodTool 计算大气扩散
        if source_x and source_y:
            try:
                # 语义搜索确认工具存在
                tools = self.discover_tools("大气扩散 环境影响评估")
                
                # 调用 AermodTool
                calc_result = await self.execute_tool_async(
                    "aermod_tool",
                    context={"task": "环境影响评估", "project": project_name},
                    source_x=source_x,
                    source_y=source_y,
                    source_z=source_z,
                    emission_rate=emission_rate,
                    receptor_x=receptor_points[0].get("x", source_x) if receptor_points else source_x,
                    receptor_y=receptor_points[0].get("y", source_y) if receptor_points else source_y,
                    receptor_z=receptor_points[0].get("z", 1.5) if receptor_points else 1.5,
                    wind_speed=wind_speed,
                )
                
                results["calculations"]["aermod"] = {
                    "tool_name": calc_result.name,
                    "success": calc_result.success,
                    "data": calc_result.data,
                    "error": calc_result.error,
                    "duration_ms": calc_result.duration_ms,
                }
                results["tools_used"].append("aermod_tool")
                logger.info(f"[EIAgent] AermodTool 执行结果: success={calc_result.success}")
                
            except Exception as e:
                logger.warning(f"[EIAgent] AermodTool 调用失败: {e}")
                results["calculations"]["aermod"] = {"error": str(e)}
        
        # 2. 尝试使用 DistanceTool 计算敏感点距离
        if source_x and source_y and receptor_points:
            try:
                distances = []
                for receptor in receptor_points[:5]:  # 最多5个敏感点
                    dist_result = self.execute_tool(
                        "distance_tool",
                        method="haversine",
                        from_lat=source_y,
                        from_lon=source_x,
                        to_lat=receptor.get("y", source_y),
                        to_lon=receptor.get("x", source_x),
                    )
                    if dist_result.success:
                        distances.append({
                            "name": receptor.get("name", "未知敏感点"),
                            "distance_km": dist_result.data.get("distance_km", 0),
                        })
                
                results["calculations"]["distances"] = distances
                results["tools_used"].append("distance_tool")
                logger.info(f"[EIAgent] DistanceTool 计算了 {len(distances)} 个敏感点距离")
                
            except Exception as e:
                logger.warning(f"[EIAgent] DistanceTool 调用失败: {e}")
                results["calculations"]["distances"] = {"error": str(e)}
        
        # 3. 综合评估结果
        aermod_success = results["calculations"].get("aermod", {}).get("success", False)
        has_distances = bool(results["calculations"].get("distances"))
        
        if aermod_success or has_distances:
            results["status"] = "completed"
            results["impact_score"] = 0.75  # TODO: 基于计算结果的真实评分
            results["message"] = "环境影响评估完成（工具层驱动）"
        else:
            results["status"] = "completed"
            results["impact_score"] = None
            results["message"] = "环境影响评估完成（工具层调用失败，返回占位结果）"
        
        return results

    # ── 风险评估 ─────────────────────────────────────────────────────────────

    async def _assess_risk(self, params: Dict) -> Dict:
        """
        风险评估 - Phase 3 增强版。
        
        使用统一工具层辅助风险判断：
        - DistanceTool: 计算与敏感目标的距离
        - MapAPITool: 识别周边风险设施
        """
        project_name = params.get("project_name", "")
        logger.info(f"[EIAgent] 风险评估: {project_name}")
        
        source_x = params.get("source_x")
        source_y = params.get("source_y")
        risk_type = params.get("risk_type", "general")  # general, fire, explosion, toxic
        sensitive_points = params.get("sensitive_points", [])
        
        results = {
            "status": "completed",
            "task_type": "risk_assessment",
            "project_name": project_name,
            "risk_level": "low",  # 默认低风险
            "tools_used": [],
            "calculations": {},
        }
        
        # 1. 使用语义搜索发现相关工具
        try:
            tools = self.discover_tools(f"{risk_type}风险 距离计算 敏感目标")
            logger.info(f"[EIAgent] 发现 {len(tools)} 个相关工具")
        except Exception as e:
            logger.warning(f"[EIAgent] 工具搜索失败: {e}")
        
        # 2. 计算与敏感目标的距离
        if source_x and source_y and sensitive_points:
            try:
                risk_distances = []
                for sp in sensitive_points[:5]:
                    dist_result = self.execute_tool(
                        "distance_tool",
                        method="haversine",
                        from_lat=source_y,
                        from_lon=source_x,
                        to_lat=sp.get("y", source_y),
                        to_lon=sp.get("x", source_x),
                    )
                    if dist_result.success:
                        d = dist_result.data.get("distance_km", 999)
                        risk_distances.append({
                            "name": sp.get("name", "未知"),
                            "type": sp.get("type", "一般"),
                            "distance_km": d,
                            "is_within_buffer": d < 0.5,  # 500m缓冲
                        })
                
                results["calculations"]["sensitive_distances"] = risk_distances
                results["tools_used"].append("distance_tool")
                
                # 基于距离更新风险等级
                within_buffer = sum(1 for r in risk_distances if r["is_within_buffer"])
                if within_buffer >= 3:
                    results["risk_level"] = "high"
                    results["message"] = f"高风险：{within_buffer} 个敏感目标位于 500m 缓冲区内"
                elif within_buffer >= 1:
                    results["risk_level"] = "medium"
                    results["message"] = f"中等风险：{within_buffer} 个敏感目标位于 500m 缓冲区内"
                else:
                    results["risk_level"] = "low"
                    results["message"] = f"低风险：所有 {len(risk_distances)} 个敏感目标均位于 500m 缓冲区外"
                    
            except Exception as e:
                logger.warning(f"[EIAgent] 风险距离计算失败: {e}")
                results["calculations"]["sensitive_distances"] = {"error": str(e)}
        else:
            results["message"] = "风险评估完成（缺少坐标或敏感点数据）"
        
        return results

    # ── 专家训练（复用 TrainingAgent）────────────────────────────────────────

    async def _run_expert_training(self, params: Dict) -> Dict:
        """运行专家训练（复用系统 TrainingAgent）"""
        logger.info(f"[EIAgent] 运行专家训练")

        if not self.training_agent:
            return {
                "status": "failed",
                "task_type": "expert_training",
                "error": "TrainingAgent 未初始化"
            }

        try:
            # 复用 TrainingAgent 的能力
            # 例如：训练环评专家模型
            result = {
                "status": "completed",
                "task_type": "expert_training",
                "message": "专家训练功能待完善（需接入 TrainingAgent 的具体方法）"
            }
            logger.info(f"[EIAgent] 专家训练完成")
            return result

        except Exception as e:
            logger.error(f"[EIAgent] 专家训练失败: {e}")
            return {"status": "failed", "error": str(e)}


# ── EIAgent 适配器（主类）───────────────────────────────────────────────────────

class EIAgentAdapter:
    """
    EIAgent 适配器
    作为系统 AgentOrchestrator 中的一个 Agent 节点
    """

    def __init__(self):
        self.orchestrator = get_orchestrator()
        self.executor = EIAgentExecutor()
        self.agent: Optional[Agent] = None
        self._registered = False
        
        # 已加载的技能和专家角色缓存
        self._loaded_skills: Dict[str, str] = {}
        self._loaded_agents: Dict[str, str] = {}
        
        # 注册到 AgentRegistry（接收技能和专家角色变化通知）
        self._register_to_agent_registry()

    def _register_to_agent_registry(self):
        """注册到 AgentRegistry，接收技能和专家角色变化通知"""
        try:
            from business.agent_registry import get_agent_registry
            registry = get_agent_registry()
            registry.register("ei_agent", self, {
                "type": "ei_specialist",
                "description": "环评专家智能体"
            })
            print("[EIAgentAdapter] 已注册到 AgentRegistry")
        except Exception as e:
            print(f"[EIAgentAdapter] 注册到 AgentRegistry 失败: {e}")
    
    def on_skills_changed(self, active_skills: Set[str]):
        """
        响应技能变化（由 AgentRegistry 调用）
        """
        print(f"[EIAgentAdapter] 收到技能变化通知: {len(active_skills)} 个启用技能")
        
        # 计算变化
        old_skills = set(self._loaded_skills.keys())
        added = active_skills - old_skills
        removed = old_skills - active_skills
        
        # 加载新增技能
        for skill_name in added:
            self._load_skill(skill_name)
        
        # 卸载移除的技能
        for skill_name in removed:
            if skill_name in self._loaded_skills:
                del self._loaded_skills[skill_name]
                print(f"[EIAgentAdapter] 卸载技能: {skill_name}")
        
        print(f"[EIAgentAdapter] 当前已加载技能: {list(self._loaded_skills.keys())}")
    
    def on_agents_changed(self, active_agents: Set[str]):
        """
        响应专家角色变化（由 AgentRegistry 调用）
        """
        print(f"[EIAgentAdapter] 收到专家角色变化通知: {len(active_agents)} 个启用专家角色")
        
        # 计算变化
        old_agents = set(self._loaded_agents.keys())
        added = active_agents - old_agents
        removed = old_agents - active_agents
        
        # 加载新增专家角色
        for agent_name in added:
            self._load_agent(agent_name)
        
        # 卸载移除的专家角色
        for agent_name in removed:
            if agent_name in self._loaded_agents:
                del self._loaded_agents[agent_name]
                print(f"[EIAgentAdapter] 卸载专家角色: {agent_name}")
        
        print(f"[EIAgentAdapter] 当前已加载专家角色: {list(self._loaded_agents.keys())}")
    
    def _load_skill(self, skill_name: str) -> bool:
        """加载单个技能"""
        try:
            from business.agent_registry import get_agent_registry
            registry = get_agent_registry()
            content = registry.load_content(skill_name, content_type="skill")
            
            if content:
                self._loaded_skills[skill_name] = content
                print(f"[EIAgentAdapter] 加载技能成功: {skill_name}")
                return True
            else:
                print(f"[EIAgentAdapter] 找不到技能内容: {skill_name}")
                return False
        except Exception as e:
            print(f"[EIAgentAdapter] 加载技能失败 {skill_name}: {e}")
            return False
    
    def _load_agent(self, agent_name: str) -> bool:
        """加载单个专家角色"""
        try:
            from business.agent_registry import get_agent_registry
            registry = get_agent_registry()
            content = registry.load_content(agent_name, content_type="agent")
            
            if content:
                self._loaded_agents[agent_name] = content
                print(f"[EIAgentAdapter] 加载专家角色成功: {agent_name}")
                return True
            else:
                print(f"[EIAgentAdapter] 找不到专家角色内容: {agent_name}")
                return False
        except Exception as e:
            print(f"[EIAgentAdapter] 加载专家角色失败 {agent_name}: {e}")
            return False
    
    def get_loaded_context(self) -> str:
        """
        获取已加载技能和专家角色的上下文（用于注入到对话提示词）
        """
        if not self._loaded_skills and not self._loaded_agents:
            return ""
        
        context_parts = ["\n\n## 已启用技能与专家角色\n"]
        
        # 加载的技能
        if self._loaded_skills:
            context_parts.append("\n### 已启用技能\n")
            for skill_name, content in self._loaded_skills.items():
                context_parts.append(f"\n#### {skill_name}\n")
                context_parts.append(content)
                context_parts.append("\n")
        
        # 加载的专家角色
        if self._loaded_agents:
            context_parts.append("\n### 已启用专家角色\n")
            for agent_name, content in self._loaded_agents.items():
                context_parts.append(f"\n#### {agent_name}\n")
                context_parts.append(content)
                context_parts.append("\n")
        
        return "\n".join(context_parts)
    
    def register(self) -> str:
        """注册 EIAgent 到 AgentOrchestrator"""
        if self._registered:
            logger.warning("[EIAgentAdapter] 已经注册过")
            return self.agent.agent_id if self.agent else ""


        # 创建 EIAgent 实例
        self.agent = AgentFactory.create_agent(
            agent_type=AgentType.EIA,
            name="EIAgent",
            config={
                "description": "环评报告生成智能体",
                "version": "3.0",
                "use_fusion_rag": True,
                "use_training_agent": True,
                "use_scrapling": True
            }
        )

        # 注册到编排器
        agent_id = self.orchestrator.register_agent(self.agent)
        self._registered = True

        # 启动编排器（如果未启动）
        asyncio.create_task(self.orchestrator.start())

        logger.info(f"[EIAgentAdapter] EIAgent 注册成功: {agent_id}")
        return agent_id

    def unregister(self) -> bool:
        """注销 EIAgent"""
        if not self._registered or not self.agent:
            return False

        success = self.orchestrator.unregister_agent(self.agent.agent_id)
        if success:
            self._registered = False
            self.agent = None
            logger.info("[EIAgentAdapter] EIAgent 注销成功")

        return success

    def submit_task(
        self,
        task_type: str,
        params: Dict,
        priority: TaskPriority = TaskPriority.NORMAL
    ) -> str:
        """
        提交环评任务
        
        Args:
            task_type: 任务类型（report_generation, regulation_retrieval, etc.）
            params: 任务参数
            priority: 优先级
            
        Returns:
            任务ID
        """
        if not self._registered:
            self.register()

        # 创建任务描述
        descriptions = {
            "report_generation": f"生成环评报告: {params.get('project_name', '')}",
            "regulation_retrieval": f"检索法规: {params.get('query', '')}",
            "pollution_coefficient": f"查询排污系数: {params.get('industry', '')}",
            "attachment_parsing": f"解析附件: {params.get('file_path', '')}",
            "environmental_impact_assessment": f"环境影响评估: {params.get('project_name', '')}",
            "risk_assessment": f"风险评估: {params.get('project_name', '')}",
            "expert_training": "专家训练"
        }

        description = descriptions.get(task_type, f"未知任务: {task_type}")

        # 提交到编排器
        task_id = self.orchestrator.submit_task(
            description=description,
            priority=priority,
            timeout=600,  # 10分钟超时
            task_type=task_type,
            params={"task_type": task_type, "params": params}
        )

        logger.info(f"[EIAgentAdapter] 任务已提交: {task_id} - {description}")
        return task_id

    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """获取任务状态"""
        return self.orchestrator.get_task_status(task_id)

    def get_task_result(self, task_id: str) -> Any:
        """获取任务结果"""
        return self.orchestrator.get_task_result(task_id)

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        return asyncio.get_event_loop().run_until_complete(
            self.orchestrator.cancel_task(task_id)
        )


# ── 全局实例 ──────────────────────────────────────────────────────────────────

_adapter: Optional[EIAgentAdapter] = None


def get_ei_agent_adapter() -> EIAgentAdapter:
    """获取全局 EIAgentAdapter 实例"""
    global _adapter
    if _adapter is None:
        _adapter = EIAgentAdapter()
    return _adapter


# ── 便捷函数 ──────────────────────────────────────────────────────────────────

def submit_ei_task(
    task_type: str,
    params: Dict,
    priority: TaskPriority = TaskPriority.NORMAL
) -> str:
    """提交环评任务（便捷函数）"""
    adapter = get_ei_agent_adapter()
    return adapter.submit_task(task_type, params, priority)


def register_ei_agent() -> str:
    """注册 EIAgent（便捷函数）"""
    adapter = get_ei_agent_adapter()
    return adapter.register()


# ── 测试代码 ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # 测试注册
    adapter = get_ei_agent_adapter()
    agent_id = adapter.register()
    print(f"EIAgent 注册成功: {agent_id}")

    # 测试提交任务
    task_id = adapter.submit_task(
        task_type="report_generation",
        params={"project_name": "测试项目", "industry": "机械制造"}
    )
    print(f"任务已提交: {task_id}")

    # 查看状态
    status = adapter.get_task_status(task_id)
    print(f"任务状态: {status}")
