"""
ToolChainOrchestrator - 工具链编排器

参考 Archon 的"执行可重复"设计，实现强制执行序列。

核心功能：
1. 关键流程定义为工作流（如"环评报告生成流程"）
2. 强制执行序列（规划 → 数据收集 → 分析 → 报告生成）
3. AI 只能在指定环节提供智能能力，避免随机跳过步骤
4. 支持流程模板化和版本管理
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from loguru import logger
from datetime import datetime
from enum import Enum
import json
import os


class ExecutionPhase(Enum):
    """执行阶段"""
    PLANNING = "planning"           # 规划阶段
    DATA_COLLECTION = "data_collection"  # 数据收集阶段
    ANALYSIS = "analysis"           # 分析阶段
    REPORT_GENERATION = "report_generation"  # 报告生成阶段
    REVIEW = "review"               # 审核阶段
    EXECUTION = "execution"         # 执行阶段


class PhaseStatus(Enum):
    """阶段状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class PhaseDefinition:
    """阶段定义"""
    phase: ExecutionPhase
    name: str
    description: str
    required: bool = True
    ai_enabled: bool = False  # 是否允许 AI 参与
    tools: List[str] = field(default_factory=list)
    next_phases: List[ExecutionPhase] = field(default_factory=list)


@dataclass
class ToolChain:
    """工具链定义"""
    id: str
    name: str
    description: str = ""
    version: str = "1.0.0"
    phases: Dict[ExecutionPhase, PhaseDefinition] = field(default_factory=dict)
    entry_phase: ExecutionPhase = ExecutionPhase.PLANNING
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class ExecutionRecord:
    """执行记录"""
    phase: ExecutionPhase
    status: PhaseStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class ToolChainInstance:
    """工具链实例"""
    instance_id: str
    chain_id: str
    status: PhaseStatus = PhaseStatus.PENDING
    current_phase: ExecutionPhase = ExecutionPhase.PLANNING
    execution_records: List[ExecutionRecord] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ToolChainOrchestrator:
    """
    工具链编排器
    
    核心功能：
    1. 定义强制执行序列
    2. 确保流程按顺序执行，不跳过必需步骤
    3. AI 只能在指定环节提供智能能力
    4. 支持流程模板化和版本管理
    """
    
    def __init__(self):
        self._logger = logger.bind(component="ToolChainOrchestrator")
        self._chains: Dict[str, ToolChain] = {}
        self._instances: Dict[str, ToolChainInstance] = {}
        self._tool_registry = None
        self._load_default_chains()
    
    def _load_default_chains(self):
        """加载默认工具链"""
        # 创建环评报告生成流程
        self._create_environment_report_chain()
    
    def _create_environment_report_chain(self):
        """创建环评报告生成流程"""
        chain = ToolChain(
            id="environment_report",
            name="环评报告生成流程",
            description="环境影响评价报告生成的标准流程"
        )
        
        # 规划阶段 - AI 参与
        chain.phases[ExecutionPhase.PLANNING] = PhaseDefinition(
            phase=ExecutionPhase.PLANNING,
            name="规划",
            description="确定评价范围、标准和方法",
            required=True,
            ai_enabled=True,
            tools=["project_scanner", "standard_finder"],
            next_phases=[ExecutionPhase.DATA_COLLECTION]
        )
        
        # 数据收集阶段 - 确定性执行
        chain.phases[ExecutionPhase.DATA_COLLECTION] = PhaseDefinition(
            phase=ExecutionPhase.DATA_COLLECTION,
            name="数据收集",
            description="收集环境监测数据、现状调查等",
            required=True,
            ai_enabled=False,
            tools=["data_fetcher", "sensor_reader", "survey_collector"],
            next_phases=[ExecutionPhase.ANALYSIS]
        )
        
        # 分析阶段 - AI 参与
        chain.phases[ExecutionPhase.ANALYSIS] = PhaseDefinition(
            phase=ExecutionPhase.ANALYSIS,
            name="分析",
            description="进行环境影响分析和预测",
            required=True,
            ai_enabled=True,
            tools=["impact_analyzer", "model_runner"],
            next_phases=[ExecutionPhase.REPORT_GENERATION]
        )
        
        # 报告生成阶段 - AI 参与
        chain.phases[ExecutionPhase.REPORT_GENERATION] = PhaseDefinition(
            phase=ExecutionPhase.REPORT_GENERATION,
            name="报告生成",
            description="生成正式的环评报告",
            required=True,
            ai_enabled=True,
            tools=["report_generator", "doc_formatter"],
            next_phases=[ExecutionPhase.REVIEW]
        )
        
        # 审核阶段 - AI 参与
        chain.phases[ExecutionPhase.REVIEW] = PhaseDefinition(
            phase=ExecutionPhase.REVIEW,
            name="审核",
            description="审核报告内容和格式",
            required=True,
            ai_enabled=True,
            tools=["report_validator", "quality_checker"],
            next_phases=[]
        )
        
        self._chains[chain.id] = chain
        self._logger.info(f"加载工具链: {chain.name}")
    
    def set_tool_registry(self, tool_registry):
        """设置工具注册中心"""
        self._tool_registry = tool_registry
    
    def get_chain(self, chain_id: str) -> Optional[ToolChain]:
        """获取工具链"""
        return self._chains.get(chain_id)
    
    def list_chains(self) -> List[Dict[str, Any]]:
        """列出所有工具链"""
        result = []
        for chain in self._chains.values():
            phases_info = []
            for phase_def in chain.phases.values():
                phases_info.append({
                    "phase": phase_def.phase.value,
                    "name": phase_def.name,
                    "required": phase_def.required,
                    "ai_enabled": phase_def.ai_enabled
                })
            
            result.append({
                "id": chain.id,
                "name": chain.name,
                "description": chain.description,
                "version": chain.version,
                "phase_count": len(chain.phases),
                "phases": phases_info
            })
        return result
    
    def create_instance(self, chain_id: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        创建工具链实例
        
        Args:
            chain_id: 工具链 ID
            context: 初始上下文
            
        Returns:
            实例 ID
        """
        if chain_id not in self._chains:
            raise ValueError(f"工具链不存在: {chain_id}")
        
        chain = self._chains[chain_id]
        instance_id = f"chain_{chain_id}_{int(datetime.now().timestamp())}"
        
        instance = ToolChainInstance(
            instance_id=instance_id,
            chain_id=chain_id,
            current_phase=chain.entry_phase,
            context=context or {}
        )
        
        # 初始化执行记录
        for phase in chain.phases:
            instance.execution_records.append(ExecutionRecord(
                phase=phase,
                status=PhaseStatus.PENDING
            ))
        
        self._instances[instance_id] = instance
        self._logger.info(f"创建工具链实例: {instance_id}")
        
        return instance_id
    
    async def execute_chain(self, instance_id: str) -> Dict[str, Any]:
        """
        执行整个工具链
        
        Args:
            instance_id: 实例 ID
            
        Returns:
            执行结果
        """
        if instance_id not in self._instances:
            return {"error": f"实例不存在: {instance_id}"}
        
        instance = self._instances[instance_id]
        chain = self._chains[instance.chain_id]
        
        instance.status = PhaseStatus.IN_PROGRESS
        instance.started_at = datetime.now()
        
        try:
            current_phase = instance.current_phase
            
            while current_phase:
                phase_def = chain.phases.get(current_phase)
                if not phase_def:
                    break
                
                await self._execute_phase(instance, chain, phase_def)
                
                # 检查是否必须完成此阶段
                if phase_def.required and self._get_phase_status(instance, current_phase) != PhaseStatus.COMPLETED:
                    return {
                        "success": False,
                        "instance_id": instance_id,
                        "error": f"必需阶段未完成: {phase_def.name}",
                        "current_phase": current_phase.value
                    }
                
                # 获取下一个阶段
                current_phase = self._get_next_phase(instance, chain, current_phase)
            
            instance.status = PhaseStatus.COMPLETED
            instance.completed_at = datetime.now()
            
            self._logger.info(f"工具链执行完成: {instance_id}")
            
            return {
                "success": True,
                "instance_id": instance_id,
                "context": instance.context,
                "execution_records": [
                    {
                        "phase": r.phase.value,
                        "status": r.status.value,
                        "result": r.result
                    } for r in instance.execution_records
                ]
            }
        except Exception as e:
            instance.status = PhaseStatus.FAILED
            self._logger.error(f"工具链执行失败 {instance_id}: {e}")
            
            return {
                "success": False,
                "instance_id": instance_id,
                "error": str(e),
                "current_phase": instance.current_phase.value
            }
    
    async def _execute_phase(self, instance: ToolChainInstance, chain: ToolChain, phase_def: PhaseDefinition):
        """执行单个阶段"""
        self._logger.info(f"执行阶段: {phase_def.name} ({phase_def.phase.value})")
        
        # 更新执行记录
        record = self._get_or_create_record(instance, phase_def.phase)
        record.status = PhaseStatus.IN_PROGRESS
        record.started_at = datetime.now()
        
        try:
            # 执行阶段工具
            phase_result = await self._execute_phase_tools(instance, phase_def)
            record.result = phase_result
            record.status = PhaseStatus.COMPLETED
            
            # 如果允许 AI 参与，调用 AI 处理
            if phase_def.ai_enabled:
                ai_result = await self._execute_ai_assistance(instance, phase_def)
                if ai_result:
                    record.result["ai_assistance"] = ai_result
                    instance.context.update(ai_result.get("context_updates", {}))
            
            record.completed_at = datetime.now()
            self._logger.info(f"阶段完成: {phase_def.name}")
            
        except Exception as e:
            record.status = PhaseStatus.FAILED
            record.error = str(e)
            self._logger.error(f"阶段执行失败 {phase_def.name}: {e}")
            raise
    
    async def _execute_phase_tools(self, instance: ToolChainInstance, phase_def: PhaseDefinition) -> Dict[str, Any]:
        """执行阶段工具"""
        results = {}
        
        for tool_name in phase_def.tools:
            if self._tool_registry:
                result = await self._tool_registry.execute(tool_name, **instance.context)
                results[tool_name] = result.data
        
        return results
    
    async def _execute_ai_assistance(self, instance: ToolChainInstance, phase_def: PhaseDefinition) -> Optional[Dict[str, Any]]:
        """执行 AI 辅助"""
        # 这里可以调用 LLM 进行分析、总结等
        # 具体实现取决于 AI 服务的配置
        
        self._logger.debug(f"AI 辅助阶段: {phase_def.name}")
        
        return {
            "assisted": True,
            "phase": phase_def.phase.value,
            "context_updates": {}
        }
    
    def _get_next_phase(self, instance: ToolChainInstance, chain: ToolChain, current_phase: ExecutionPhase) -> Optional[ExecutionPhase]:
        """获取下一个阶段"""
        phase_def = chain.phases.get(current_phase)
        if not phase_def or not phase_def.next_phases:
            return None
        
        # 检查下一阶段是否满足条件
        for next_phase in phase_def.next_phases:
            if next_phase in chain.phases:
                return next_phase
        
        return None
    
    def _get_phase_status(self, instance: ToolChainInstance, phase: ExecutionPhase) -> PhaseStatus:
        """获取阶段状态"""
        for record in instance.execution_records:
            if record.phase == phase:
                return record.status
        return PhaseStatus.PENDING
    
    def _get_or_create_record(self, instance: ToolChainInstance, phase: ExecutionPhase) -> ExecutionRecord:
        """获取或创建执行记录"""
        for record in instance.execution_records:
            if record.phase == phase:
                return record
        
        record = ExecutionRecord(phase=phase, status=PhaseStatus.PENDING)
        instance.execution_records.append(record)
        return record
    
    def validate_chain(self, chain_id: str) -> List[str]:
        """验证工具链定义"""
        errors = []
        
        chain = self._chains.get(chain_id)
        if not chain:
            errors.append(f"工具链不存在: {chain_id}")
            return errors
        
        # 检查必需阶段是否有后继
        for phase, phase_def in chain.phases.items():
            if phase_def.required and not phase_def.next_phases and phase != ExecutionPhase.REVIEW:
                errors.append(f"必需阶段 {phase_def.name} 没有后继阶段")
        
        return errors