"""
对话管理层 - Conversation Orchestrator

核心功能：
1. 对话状态机（管理澄清流程）
2. 上下文管理（记忆历史对话）
3. 意图识别与槽位填充
4. 渐进式需求澄清流程
"""

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json
import os
from pathlib import Path

from business.global_model_router import GlobalModelRouter, ModelCapability


class ConversationState(Enum):
    """对话状态定义"""
    INITIAL = "initial"
    EXPLORING = "exploring"
    CONTEXT_BUILDING = "context_building"
    DEEP_DIVE = "deep_dive"
    SPECIFICATION = "specification"
    CONFIRMING = "confirming"
    COMPLETE = "complete"


class IntentType(Enum):
    """意图类型"""
    REQUIREMENT_DESCRIPTION = "requirement_description"
    FUNCTIONAL_REQUIREMENT = "functional_requirement"
    NON_FUNCTIONAL_REQUIREMENT = "non_functional_requirement"
    CONSTRAINT = "constraint"
    EXAMPLE = "example"
    QUESTION = "question"
    CONFIRMATION = "confirmation"
    REJECTION = "rejection"


@dataclass
class ConversationTurn:
    """对话回合"""
    turn_id: str
    user_input: str
    assistant_response: str
    intent: IntentType
    timestamp: datetime = field(default_factory=datetime.now)
    context_update: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RequirementContext:
    """需求上下文"""
    functional: List[Dict[str, Any]] = field(default_factory=list)
    non_functional: Dict[str, Any] = field(default_factory=dict)
    constraints: List[str] = field(default_factory=list)
    user_stories: List[Dict[str, Any]] = field(default_factory=list)
    acceptance_criteria: List[str] = field(default_factory=list)
    files: List[Dict[str, str]] = field(default_factory=list)
    business_context: Dict[str, Any] = field(default_factory=dict)
    user_profiles: List[Dict[str, Any]] = field(default_factory=list)
    success_metrics: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ClarificationQuestion:
    """澄清问题"""
    question: str
    priority: int
    category: str
    target_field: Optional[str] = None
    expected_format: Optional[str] = None


class ConversationOrchestrator:
    """
    对话编排器 - 管理需求澄清的完整流程
    
    五阶段澄清模型：
    1. 需求探索 → 开放式提问、关键词提取、需求分类
    2. 上下文建立 → 业务场景澄清、用户画像定义、约束条件收集
    3. 深度挖掘 → 功能点分解、用户流程梳理、异常场景识别
    4. 规格化 → 验收标准定义、优先级排序、依赖关系识别
    5. 确认与生成 → 需求文档生成、原型建议、开发计划草拟
    """

    def __init__(self):
        self._router = GlobalModelRouter()
        self._conversations: Dict[str, Dict[str, Any]] = {}
        self._context_cache: Dict[str, RequirementContext] = {}
        
        self._state_handlers = {
            ConversationState.INITIAL: self._handle_initial,
            ConversationState.EXPLORING: self._handle_exploring,
            ConversationState.CONTEXT_BUILDING: self._handle_context_building,
            ConversationState.DEEP_DIVE: self._handle_deep_dive,
            ConversationState.SPECIFICATION: self._handle_specification,
            ConversationState.CONFIRMING: self._handle_confirming,
            ConversationState.COMPLETE: self._handle_complete
        }

    def start_conversation(self, user_id: str) -> str:
        """
        开始新对话
        
        Args:
            user_id: 用户ID
            
        Returns:
            对话ID
        """
        conversation_id = f"conv_{user_id}_{int(datetime.now().timestamp())}"
        
        self._conversations[conversation_id] = {
            "user_id": user_id,
            "state": ConversationState.INITIAL,
            "turns": [],
            "context": RequirementContext(),
            "created_at": datetime.now()
        }
        
        self._context_cache[conversation_id] = RequirementContext()
        
        return conversation_id

    async def process_user_input(self, conversation_id: str, user_input: str) -> Dict[str, Any]:
        """
        处理用户输入
        
        Args:
            conversation_id: 对话ID
            user_input: 用户输入
            
        Returns:
            处理结果
        """
        if conversation_id not in self._conversations:
            return {"error": "对话不存在"}
        
        conversation = self._conversations[conversation_id]
        state = conversation["state"]
        
        # 意图识别
        intent = await self._recognize_intent(user_input, conversation["context"])
        
        # 根据当前状态处理输入
        handler = self._state_handlers.get(state)
        if handler:
            result = await handler(conversation_id, user_input, intent)
        else:
            result = {"response": "未知状态，请重新开始"}
        
        # 添加对话回合
        conversation["turns"].append(ConversationTurn(
            turn_id=f"turn_{len(conversation['turns'])}",
            user_input=user_input,
            assistant_response=result.get("response", ""),
            intent=intent,
            context_update=result.get("context_update", {})
        ))
        
        # 更新状态
        if "next_state" in result:
            conversation["state"] = result["next_state"]
        
        return result

    async def _recognize_intent(self, user_input: str, context: RequirementContext) -> IntentType:
        """识别用户意图"""
        prompt = f"""
分析以下用户输入，判断意图类型：

用户输入: {user_input}

意图类型选项：
- requirement_description: 描述需求
- functional_requirement: 功能需求
- non_functional_requirement: 非功能需求（性能、安全等）
- constraint: 约束条件
- example: 举例说明
- question: 提问
- confirmation: 确认
- rejection: 拒绝/否定

只返回意图类型名称。
"""

        try:
            response = await self._router.call_model(
                capability=ModelCapability.REASONING,
                prompt=prompt,
                temperature=0.1
            )
            
            return IntentType(response.strip())
        except:
            return IntentType.REQUIREMENT_DESCRIPTION

    async def _handle_initial(self, conversation_id: str, user_input: str, intent: IntentType) -> Dict[str, Any]:
        """处理初始状态"""
        if intent == IntentType.REQUIREMENT_DESCRIPTION and user_input.strip():
            # 有需求描述，进入探索阶段
            context = self._context_cache[conversation_id]
            context.functional.append({"description": user_input})
            
            questions = await self._generate_initial_questions(user_input)
            
            return {
                "response": questions[0]["question"],
                "next_state": ConversationState.EXPLORING,
                "context_update": {"requirement": user_input}
            }
        
        return {
            "response": "您好！我是您的需求分析助手。请描述您的需求，我会帮助您逐步澄清并生成完整的需求文档。",
            "next_state": ConversationState.INITIAL
        }

    async def _handle_exploring(self, conversation_id: str, user_input: str, intent: IntentType) -> Dict[str, Any]:
        """处理探索阶段"""
        context = self._context_cache[conversation_id]
        
        # 分析用户输入并更新上下文
        await self._update_context_from_input(context, user_input, intent)
        
        # 检查信息缺口
        gap_analysis = await self._detect_information_gaps(context)
        
        if gap_analysis["gaps"]:
            # 还有信息缺口，继续提问
            question = gap_analysis["next_question"]
            return {
                "response": question,
                "next_state": ConversationState.EXPLORING,
                "context_update": gap_analysis.get("context_update", {})
            }
        
        # 进入上下文建立阶段
        return {
            "response": "好的，我已经了解了您的基本需求。接下来让我了解一些业务背景信息...\n\n请问这个功能的目标用户是谁？",
            "next_state": ConversationState.CONTEXT_BUILDING
        }

    async def _handle_context_building(self, conversation_id: str, user_input: str, intent: IntentType) -> Dict[str, Any]:
        """处理上下文建立阶段"""
        context = self._context_cache[conversation_id]
        
        # 更新业务上下文
        if not context.business_context.get("user_profile"):
            context.user_profiles.append({"description": user_input})
            return {
                "response": "了解。这个功能会在什么场景下使用？",
                "next_state": ConversationState.CONTEXT_BUILDING
            }
        elif not context.business_context.get("usage_scenario"):
            context.business_context["usage_scenario"] = user_input
            return {
                "response": "明白了。是否有任何约束条件需要考虑？（如技术限制、时间限制、预算等）",
                "next_state": ConversationState.CONTEXT_BUILDING
            }
        else:
            context.constraints.append(user_input)
            return {
                "response": "好的。现在让我们深入探讨具体的功能细节...\n\n您提到的这个功能主要包含哪些具体操作？",
                "next_state": ConversationState.DEEP_DIVE
            }

    async def _handle_deep_dive(self, conversation_id: str, user_input: str, intent: IntentType) -> Dict[str, Any]:
        """处理深度挖掘阶段"""
        context = self._context_cache[conversation_id]
        
        # 功能点分解
        functional_items = await self._parse_functional_items(user_input)
        context.functional.extend(functional_items)
        
        # 检查是否需要更多细节
        if len(context.functional) < 3:
            return {
                "response": "了解。还有其他功能需要补充吗？",
                "next_state": ConversationState.DEEP_DIVE
            }
        
        return {
            "response": "很好！现在让我们定义验收标准...\n\n对于这些功能，您期望的成功指标是什么？",
            "next_state": ConversationState.SPECIFICATION
        }

    async def _handle_specification(self, conversation_id: str, user_input: str, intent: IntentType) -> Dict[str, Any]:
        """处理规格化阶段"""
        context = self._context_cache[conversation_id]
        
        # 添加成功指标
        context.success_metrics.append({"description": user_input, "type": "success_metric"})
        
        # 询问验收标准
        if len(context.acceptance_criteria) == 0:
            return {
                "response": "明白了。请描述一个典型的用户故事或验收场景？",
                "next_state": ConversationState.SPECIFICATION
            }
        else:
            context.acceptance_criteria.append(user_input)
            return {
                "response": "好的！让我整理一下收集到的需求...\n\n确认一下，我理解的是否正确：\n\n" + await self._generate_summary(context),
                "next_state": ConversationState.CONFIRMING
            }

    async def _handle_confirming(self, conversation_id: str, user_input: str, intent: IntentType) -> Dict[str, Any]:
        """处理确认阶段"""
        if intent == IntentType.CONFIRMATION or "是" in user_input or "对" in user_input:
            return {
                "response": "太棒了！需求确认完成。我将为您生成完整的需求文档...",
                "next_state": ConversationState.COMPLETE
            }
        elif intent == IntentType.REJECTION or "不" in user_input or "修改" in user_input:
            return {
                "response": "好的，请告诉我需要修改的部分...",
                "next_state": ConversationState.SPECIFICATION
            }
        
        return {
            "response": "您确认以上需求描述正确吗？（请回答是/否）",
            "next_state": ConversationState.CONFIRMING
        }

    async def _handle_complete(self, conversation_id: str, user_input: str, intent: IntentType) -> Dict[str, Any]:
        """处理完成阶段"""
        context = self._context_cache[conversation_id]
        
        # 生成需求文档
        document = await self._generate_requirement_document(context)
        
        return {
            "response": document,
            "next_state": ConversationState.COMPLETE,
            "document_generated": True
        }

    async def _generate_initial_questions(self, requirement: str) -> List[Dict[str, Any]]:
        """生成初始澄清问题"""
        prompt = f"""
根据以下需求描述，生成3个最关键的澄清问题：

需求: {requirement}

输出格式（JSON）:
[
    {{"question": "问题1", "priority": 1, "category": "功能"}},
    {{"question": "问题2", "priority": 2, "category": "业务"}},
    {{"question": "问题3", "priority": 3, "category": "约束"}}
]
"""

        try:
            response = await self._router.call_model(
                capability=ModelCapability.REASONING,
                prompt=prompt,
                temperature=0.2
            )
            return json.loads(response)
        except:
            return [
                {"question": "这个功能的主要用户是谁？", "priority": 1, "category": "用户"},
                {"question": "预期的性能指标是什么？", "priority": 2, "category": "性能"},
                {"question": "有哪些技术或业务约束？", "priority": 3, "category": "约束"}
            ]

    async def _detect_information_gaps(self, context: RequirementContext) -> Dict[str, Any]:
        """检测信息缺口"""
        gaps = []
        next_question = ""
        
        # 完整性检测
        if not context.functional:
            gaps.append("缺少功能需求描述")
            next_question = "请描述您需要的功能？"
        elif len(context.functional) < 2:
            gaps.append("功能描述不够详细")
            next_question = "能否提供更多功能细节？"
        elif not context.user_profiles:
            gaps.append("缺少用户画像")
            next_question = "目标用户是谁？"
        elif not context.business_context.get("usage_scenario"):
            gaps.append("缺少使用场景")
            next_question = "使用场景是什么？"
        
        return {
            "gaps": gaps,
            "next_question": next_question,
            "completeness_score": min(100, len(context.functional) * 20 + len(context.user_profiles) * 10)
        }

    async def _update_context_from_input(self, context: RequirementContext, user_input: str, intent: IntentType):
        """根据用户输入更新上下文"""
        if intent == IntentType.FUNCTIONAL_REQUIREMENT:
            context.functional.append({"description": user_input})
        elif intent == IntentType.NON_FUNCTIONAL_REQUIREMENT:
            # 尝试解析非功能需求
            if "秒" in user_input or "响应" in user_input:
                context.non_functional["performance"] = user_input
            elif "安全" in user_input:
                context.non_functional["security"] = user_input
        elif intent == IntentType.CONSTRAINT:
            context.constraints.append(user_input)

    async def _parse_functional_items(self, user_input: str) -> List[Dict[str, Any]]:
        """解析功能项"""
        prompt = f"""
分析以下描述，提取功能项：

描述: {user_input}

输出格式（JSON）:
[
    {{"name": "功能名称", "description": "功能描述", "priority": "high|medium|low"}}
]
"""

        try:
            response = await self._router.call_model(
                capability=ModelCapability.REASONING,
                prompt=prompt,
                temperature=0.2
            )
            return json.loads(response)
        except:
            return [{"name": user_input, "description": user_input, "priority": "medium"}]

    async def _generate_summary(self, context: RequirementContext) -> str:
        """生成需求摘要"""
        summary = "功能需求：\n"
        for i, func in enumerate(context.functional[:3], 1):
            summary += f"{i}. {func.get('name', func.get('description', ''))}\n"
        
        if context.user_profiles:
            summary += f"\n目标用户：{context.user_profiles[0].get('description', '')}\n"
        
        if context.business_context.get("usage_scenario"):
            summary += f"使用场景：{context.business_context['usage_scenario']}\n"
        
        if context.non_functional:
            summary += f"\n非功能需求：{context.non_functional}\n"
        
        return summary

    async def _generate_requirement_document(self, context: RequirementContext) -> str:
        """生成完整的需求文档"""
        prompt = f"""
根据以下需求上下文，生成完整的需求规格说明书：

功能需求: {json.dumps(context.functional)}
非功能需求: {json.dumps(context.non_functional)}
约束条件: {context.constraints}
用户画像: {json.dumps(context.user_profiles)}
业务场景: {context.business_context}
验收标准: {context.acceptance_criteria}
成功指标: {json.dumps(context.success_metrics)}

请按照以下结构输出：
1. 项目概述
2. 功能需求（带优先级）
3. 非功能需求
4. 用户流程描述
5. 验收标准
"""

        try:
            response = await self._router.call_model(
                capability=ModelCapability.REASONING,
                prompt=prompt,
                temperature=0.2
            )
            return response
        except:
            return "需求文档生成失败，请重试。"

    def get_conversation_context(self, conversation_id: str) -> Optional[RequirementContext]:
        """获取对话上下文"""
        return self._context_cache.get(conversation_id)

    def get_conversation_state(self, conversation_id: str) -> Optional[ConversationState]:
        """获取对话状态"""
        conversation = self._conversations.get(conversation_id)
        return conversation["state"] if conversation else None


def get_conversation_orchestrator() -> ConversationOrchestrator:
    """获取对话编排器单例"""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = ConversationOrchestrator()
    return _orchestrator_instance


_orchestrator_instance = None