"""
ThinkBeforeExecute - 先思考再执行机制

参考 andrej-karpathy-skills 的"先思考再编码"原则。

核心功能：
1. 在执行任务前，先列出假设、提出歧义、澄清需求
2. 避免默认执行错误方向
3. 支持反思和自我修正
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from loguru import logger
from datetime import datetime
from enum import Enum


class ThinkingStatus(Enum):
    """思考状态"""
    NOT_STARTED = "not_started"
    THINKING = "thinking"
    NEEDS_CLARIFICATION = "needs_clarification"
    READY_TO_EXECUTE = "ready_to_execute"
    COMPLETED = "completed"


@dataclass
class Assumption:
    """假设记录"""
    id: str
    content: str
    confidence: float = 0.5  # 置信度 0-1
    verified: bool = False
    verification_method: Optional[str] = None


@dataclass
class Ambiguity:
    """歧义记录"""
    id: str
    question: str
    clarification: Optional[str] = None
    resolved: bool = False


@dataclass
class Clarification:
    """澄清请求"""
    id: str
    question: str
    options: Optional[List[str]] = None
    response: Optional[str] = None


@dataclass
class ThinkingResult:
    """思考结果"""
    task: str
    status: ThinkingStatus
    assumptions: List[Ambiguity] = field(default_factory=list)
    ambiguities: List[Ambiguity] = field(default_factory=list)
    clarifications: List[Clarification] = field(default_factory=list)
    plan: Optional[str] = None
    estimated_steps: int = 0
    warnings: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


class ThinkBeforeExecute:
    """
    先思考再执行机制
    
    参考 andrej-karpathy-skills 的"先思考再编码"原则：
    1. 在执行前花时间思考
    2. 列出所有假设
    3. 识别歧义并澄清
    4. 制定详细计划
    5. 再执行
    
    核心流程：
    1. 理解任务
    2. 列出假设
    3. 识别歧义
    4. 澄清需求（如果需要）
    5. 制定执行计划
    6. 执行任务
    """
    
    def __init__(self, llm_client=None):
        self._logger = logger.bind(component="ThinkBeforeExecute")
        self._llm = llm_client
    
    async def think(self, task: str, context: Optional[Dict[str, Any]] = None) -> ThinkingResult:
        """
        对任务进行思考
        
        Args:
            task: 任务描述
            context: 上下文信息
            
        Returns:
            ThinkingResult - 思考结果
        """
        self._logger.info(f"开始思考任务: {task}")
        
        result = ThinkingResult(
            task=task,
            status=ThinkingStatus.THINKING
        )
        
        # 1. 理解任务
        await self._understand_task(task, context, result)
        
        # 2. 列出假设
        await self._list_assumptions(task, context, result)
        
        # 3. 识别歧义
        await self._identify_ambiguities(task, context, result)
        
        # 4. 检查是否需要澄清
        if result.ambiguities and not all(a.resolved for a in result.ambiguities):
            result.status = ThinkingStatus.NEEDS_CLARIFICATION
            self._logger.info(f"任务存在歧义，需要澄清: {len(result.ambiguities)} 个")
            return result
        
        # 5. 制定执行计划
        await self._create_plan(task, context, result)
        
        # 6. 准备执行
        result.status = ThinkingStatus.READY_TO_EXECUTE
        self._logger.info("思考完成，准备执行")
        
        return result
    
    async def _understand_task(self, task: str, context: Optional[Dict[str, Any]], result: ThinkingResult):
        """理解任务"""
        self._logger.debug("阶段 1: 理解任务")
        
        if context:
            result.warnings.append(f"上下文信息: {len(context)} 项")
    
    async def _list_assumptions(self, task: str, context: Optional[Dict[str, Any]], result: ThinkingResult):
        """列出假设"""
        self._logger.debug("阶段 2: 列出假设")
        
        # 使用 LLM 分析任务并列出假设
        prompt = f"""
你是一个严谨的分析师。请分析以下任务并列出所有可能的假设：

任务：{task}

上下文信息：{context or '无'}

请列出你在执行此任务时会做出的所有假设，包括：
1. 关于输入数据的假设
2. 关于环境的假设
3. 关于工具可用性的假设
4. 关于预期输出的假设

请以 JSON 格式输出，包含 assumptions 数组，每个元素包含 id、content、confidence（0-1）：
"""
        
        try:
            response = await self._call_llm(prompt)
            
            import json
            data = json.loads(response)
            
            for i, assumption_data in enumerate(data.get("assumptions", [])):
                assumption = Assumption(
                    id=f"assumption_{i+1}",
                    content=assumption_data.get("content", ""),
                    confidence=assumption_data.get("confidence", 0.5)
                )
                result.assumptions.append(assumption)
                
        except Exception as e:
            self._logger.warning(f"自动分析假设失败，使用默认假设: {e}")
            # 添加一些通用假设
            default_assumptions = [
                {"content": "任务描述是准确的", "confidence": 0.9},
                {"content": "所需工具可用", "confidence": 0.7},
                {"content": "数据格式符合预期", "confidence": 0.7}
            ]
            for i, assumption_data in enumerate(default_assumptions):
                assumption = Assumption(
                    id=f"assumption_{i+1}",
                    content=assumption_data.get("content", ""),
                    confidence=assumption_data.get("confidence", 0.5)
                )
                result.assumptions.append(assumption)
    
    async def _identify_ambiguities(self, task: str, context: Optional[Dict[str, Any]], result: ThinkingResult):
        """识别歧义"""
        self._logger.debug("阶段 3: 识别歧义")
        
        # 使用 LLM 分析任务并识别歧义
        prompt = f"""
你是一个严谨的分析师。请分析以下任务并识别所有潜在的歧义：

任务：{task}

上下文信息：{context or '无'}

请列出所有可能存在歧义的地方，需要澄清的问题。

请以 JSON 格式输出，包含 ambiguities 数组，每个元素包含 id、question：
"""
        
        try:
            response = await self._call_llm(prompt)
            
            import json
            data = json.loads(response)
            
            for i, ambiguity_data in enumerate(data.get("ambiguities", [])):
                ambiguity = Ambiguity(
                    id=f"ambiguity_{i+1}",
                    question=ambiguity_data.get("question", "")
                )
                result.ambiguities.append(ambiguity)
                
        except Exception as e:
            self._logger.warning(f"自动识别歧义失败: {e}")
    
    async def clarify(self, ambiguity_id: str, response: str, result: ThinkingResult):
        """
        澄清歧义
        
        Args:
            ambiguity_id: 歧义 ID
            response: 用户的澄清回答
            result: 思考结果对象
        """
        for ambiguity in result.ambiguities:
            if ambiguity.id == ambiguity_id:
                ambiguity.clarification = response
                ambiguity.resolved = True
                self._logger.info(f"歧义已澄清: {ambiguity.question} -> {response}")
                break
    
    async def _create_plan(self, task: str, context: Optional[Dict[str, Any]], result: ThinkingResult):
        """制定执行计划"""
        self._logger.debug("阶段 4: 制定执行计划")
        
        # 使用 LLM 生成执行计划
        prompt = f"""
你是一个经验丰富的项目规划师。请为以下任务制定详细的执行计划：

任务：{task}

上下文信息：{context or '无'}

已知假设：
{[a.content for a in result.assumptions]}

请以 JSON 格式输出执行计划，包含：
- plan: 详细的执行步骤描述
- steps: 步骤数量估计
- tools: 可能需要使用的工具列表
"""
        
        try:
            response = await self._call_llm(prompt)
            
            import json
            data = json.loads(response)
            
            result.plan = data.get("plan", "")
            result.estimated_steps = data.get("steps", 5)
            
            self._logger.debug(f"执行计划已制定，预计 {result.estimated_steps} 步")
            
        except Exception as e:
            self._logger.warning(f"自动生成计划失败，使用默认计划: {e}")
            result.plan = f"1. 理解任务\n2. 收集必要数据\n3. 执行主要操作\n4. 验证结果\n5. 生成报告"
            result.estimated_steps = 5
    
    def get_clarification_questions(self, result: ThinkingResult) -> List[str]:
        """获取需要澄清的问题列表"""
        return [a.question for a in result.ambiguities if not a.resolved]
    
    def is_ready_to_execute(self, result: ThinkingResult) -> bool:
        """检查是否准备好执行"""
        return result.status == ThinkingStatus.READY_TO_EXECUTE
    
    def needs_clarification(self, result: ThinkingResult) -> bool:
        """检查是否需要澄清"""
        return result.status == ThinkingStatus.NEEDS_CLARIFICATION
    
    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM"""
        if self._llm is not None:
            return await self._llm.chat(prompt)
        else:
            # 模拟 LLM 响应
            import json
            if "assumption" in prompt.lower():
                return json.dumps({
                    "assumptions": [
                        {"id": "1", "content": "任务描述准确", "confidence": 0.9},
                        {"id": "2", "content": "所需工具可用", "confidence": 0.7}
                    ]
                })
            elif "ambiguity" in prompt.lower():
                return json.dumps({
                    "ambiguities": []
                })
            elif "plan" in prompt.lower():
                return json.dumps({
                    "plan": "1. 分析任务\n2. 收集数据\n3. 执行操作\n4. 验证结果",
                    "steps": 4,
                    "tools": []
                })
            return json.dumps({})