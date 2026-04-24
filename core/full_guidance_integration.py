"""
完整追问系统集成 (Phase 4)
===========================

整合 Phase 1-4 的所有追问能力：
- Phase 1: 模板基础追问
- Phase 2: UI 追问按钮（外部模块）
- Phase 3: 内容分析引导
- Phase 4: LLM 增强引导

提供统一的追问生成接口
"""

from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass, field

# 导入所有 Phase 的模块
from .agent_chat_enhancer import (
    EnhancedAgentChat,
    ChatIntent,
    IntentAnalysis,
    ChatContext,
    GuidanceResult,
    GuidanceGenerator,
)

from .content_guidance import (
    ContentType,
    GuidanceDepth,
    ContentAnalysis,
    QualityAssessment,
    SemanticGuidanceResult,
    SemanticGuidanceGenerator,
    generate_semantic_guidance,
)

from .llm_guidance import (
    LLMGuidanceConfig,
    LLMSource,
    GuidanceStrategy,
    TriggerCondition,
    LLMGuidanceResult,
    HybridGuidanceResult,
    LLMGuidanceGenerator,
    GuidanceTrigger,
    HybridGuidanceGenerator,
    create_llm_generator,
    create_hybrid_generator,
)


@dataclass
class FullGuidanceResult:
    """
    完整追问结果（整合 Phase 1-4）
    
    包含所有来源的追问和分析
    """
    # Phase 1: 模板追问
    template_questions: List[str] = field(default_factory=list)
    template_confidence: float = 0.0
    
    # Phase 3: 内容分析追问
    semantic_questions: List[str] = field(default_factory=list)
    content_analysis: Optional[ContentAnalysis] = None
    quality_assessment: Optional[QualityAssessment] = None
    
    # Phase 4: LLM 追问
    llm_questions: List[str] = field(default_factory=list)
    llm_confidence: float = 0.0
    llm_latency: float = 0.0
    
    # 合并结果
    all_questions: List[str] = field(default_factory=list)
    
    # 策略信息
    strategy_used: str = "none"
    final_confidence: float = 0.0
    
    # 来源追踪
    question_sources: Dict[str, str] = field(default_factory=dict)
    
    @property
    def questions(self) -> List[str]:
        """获取所有追问（兼容接口）"""
        return self.all_questions


class FullGuidanceEngine:
    """
    完整追问引擎
    
    整合所有追问生成策略
    """
    
    def __init__(
        self,
        enable_template: bool = True,
        enable_semantic: bool = True,
        enable_llm: bool = True,
        llm_config: Optional[LLMGuidanceConfig] = None,
    ):
        """
        Args:
            enable_template: 启用水模板追问（Phase 1）
            enable_semantic: 启用语义追问（Phase 3）
            enable_llm: 启用水 LLM 追问（Phase 4）
            llm_config: LLM 配置
        """
        # Phase 1: 模板生成器
        self.enable_template = enable_template
        self._template_generator = GuidanceGenerator() if enable_template else None
        
        # Phase 3: 语义生成器
        self.enable_semantic = enable_semantic
        self._semantic_generator = SemanticGuidanceGenerator() if enable_semantic else None
        
        # Phase 4: LLM/混合生成器
        self.enable_llm = enable_llm
        if enable_llm:
            llm_config = llm_config or LLMGuidanceConfig()
            self._hybrid_generator = HybridGuidanceGenerator(llm_config)
        else:
            self._hybrid_generator = None
        
        # 回调
        self._on_template_generated: Optional[Callable[[List[str]], None]] = None
        self._on_semantic_generated: Optional[Callable[[SemanticGuidanceResult], None]] = None
        self._on_llm_generated: Optional[Callable[[LLMGuidanceResult], None]] = None
    
    def set_template_callback(self, callback: Callable[[List[str]], None]):
        """设置模板追问回调"""
        self._on_template_generated = callback
    
    def set_semantic_callback(self, callback: Callable[[SemanticGuidanceResult], None]):
        """设置语义追问回调"""
        self._on_semantic_generated = callback
    
    def set_llm_callback(self, callback: Callable[[LLMGuidanceResult], None]):
        """设置 LLM 追问回调"""
        self._on_llm_generated = callback
    
    def generate(
        self,
        user_message: str,
        response: str,
        intent: Optional[ChatIntent] = None,
        context: Optional[ChatContext] = None,
        intent_analysis: Optional[IntentAnalysis] = None,
    ) -> FullGuidanceResult:
        """
        生成完整追问（整合 Phase 1-4）
        
        Args:
            user_message: 用户消息
            response: AI 回答
            intent: 意图类型
            context: 对话上下文
            intent_analysis: 意图分析结果
            
        Returns:
            FullGuidanceResult: 完整追问结果
        """
        result = FullGuidanceResult()
        
        # 构建上下文字典
        ctx_dict = {}
        if context:
            ctx_dict = {
                'message_count': context.message_count,
                'followup_count': context.followup_count,
                'topic': context.topic,
            }
        
        # ========== Phase 1: 模板追问 ==========
        template_questions = []
        if self.enable_template and self._template_generator and intent:
            template_result = self._template_generator.generate(
                intent=intent,
                response=response,
                context=context,
                user_message=user_message,
            )
            template_questions = template_result.questions
            result.template_questions = template_questions
            result.template_confidence = template_result.confidence
            
            if self._on_template_generated:
                self._on_template_generated(template_questions)
        
        # ========== Phase 3: 语义追问 ==========
        semantic_questions = []
        if self.enable_semantic and self._semantic_generator:
            intent_str = intent.value if intent else ""
            
            semantic_result = self._semantic_generator.generate(
                content=response,
                intent_type=intent_str,
                context=ctx_dict,
            )
            semantic_questions = semantic_result.questions
            result.semantic_questions = semantic_questions
            result.content_analysis = semantic_result.analysis
            result.quality_assessment = semantic_result.quality_assessment
            
            if self._on_semantic_generated:
                self._on_semantic_generated(semantic_result)
        
        # ========== Phase 4: LLM/混合追问 ==========
        llm_questions = []
        content_type = "general"
        if result.content_analysis:
            content_type = result.content_analysis.content_type.value
        
        if self.enable_llm and self._hybrid_generator:
            # 计算规则置信度
            rule_questions = template_questions + semantic_questions
            rule_confidence = max(result.template_confidence, semantic_result.confidence if semantic_result else 0)
            
            # 生成混合追问
            hybrid_result = self._hybrid_generator.generate(
                rule_questions=rule_questions,
                rule_confidence=rule_confidence,
                user_message=user_message,
                response=response,
                intent=intent_str if intent else "",
                content_type=content_type,
                context=ctx_dict,
            )
            
            llm_questions = hybrid_result.llm_questions
            result.llm_questions = llm_questions
            result.llm_confidence = hybrid_result.llm_confidence
            result.llm_latency = 0.0  # 可从 hybrid_result 获取
            result.question_sources.update(hybrid_result.question_sources)
            
            if self._on_llm_generated:
                llm_result = LLMGuidanceResult(
                    questions=llm_questions,
                    confidence=hybrid_result.llm_confidence,
                )
                self._on_llm_callback(llm_result)
        
        # ========== 合并所有追问 ==========
        result.all_questions = self._merge_all_questions(
            template_questions,
            semantic_questions,
            llm_questions,
            result.question_sources,
        )
        
        # 计算最终置信度
        confidences = []
        if result.template_questions:
            confidences.append(result.template_confidence)
        if result.semantic_questions:
            confidences.append(semantic_result.confidence if semantic_result else 0)
        if result.llm_questions:
            confidences.append(result.llm_confidence)
        
        result.final_confidence = sum(confidences) / len(confidences) if confidences else 0.5
        
        # 策略描述
        strategies = []
        if result.template_questions:
            strategies.append("template")
        if result.semantic_questions:
            strategies.append("semantic")
        if result.llm_questions:
            strategies.append("llm")
        result.strategy_used = "+".join(strategies) if strategies else "none"
        
        return result
    
    def _on_llm_callback(self, llm_result: LLMGuidanceResult):
        """触发 LLM 回调"""
        if self._on_llm_generated:
            self._on_llm_generated(llm_result)
    
    def _merge_all_questions(
        self,
        template_q: List[str],
        semantic_q: List[str],
        llm_q: List[str],
        sources: Dict[str, str],
    ) -> List[str]:
        """合并所有来源的追问"""
        seen = set()
        result = []
        
        # 按优先级添加
        for q in template_q:
            normalized = q.lower().strip()
            if normalized not in seen:
                seen.add(normalized)
                result.append(q)
                sources[q] = "template"
        
        for q in semantic_q:
            normalized = q.lower().strip()
            if normalized not in seen:
                seen.add(normalized)
                result.append(q)
                sources[q] = "semantic"
        
        for q in llm_q:
            normalized = q.lower().strip()
            if normalized not in seen:
                seen.add(normalized)
                result.append(q)
                sources[q] = "llm"
        
        return result[:5]  # 最多5个
    
    def is_llm_available(self) -> bool:
        """检查 LLM 是否可用"""
        if not self.enable_llm or not self._hybrid_generator:
            return False
        return self._hybrid_generator.llm_generator.is_available()
    
    def get_llm_models(self) -> List[str]:
        """获取可用的 LLM 模型"""
        if not self._hybrid_generator:
            return []
        return self._hybrid_generator.llm_generator.client.list_models()


class FullGuidanceAgentChat(EnhancedAgentChat):
    """
    完整追问增强 AgentChat
    
    在 EnhancedAgentChat 基础上集成 Phase 3-4 功能
    """
    
    def __init__(
        self,
        base_chat,
        enable_intent: bool = True,
        enable_compress: bool = True,
        enable_context: bool = True,
        enable_guidance: bool = True,
        enable_content_analysis: bool = True,
        enable_llm: bool = True,
        llm_config: Optional[LLMGuidanceConfig] = None,
    ):
        """
        Args:
            base_chat: 原始 AgentChat
            enable_intent: 启用意图识别
            enable_compress: 启用 Query 压缩
            enable_context: 启用上下文管理
            enable_guidance: 启用追问生成
            enable_content_analysis: 启用水内容分析（Phase 3）
            enable_llm: 启用水 LLM（Phase 4）
            llm_config: LLM 配置
        """
        # 调用父类（已包含 Phase 1）
        super().__init__(
            base_chat=base_chat,
            enable_intent=enable_intent,
            enable_compress=enable_compress,
            enable_context=enable_context,
            enable_guidance=enable_guidance,
        )
        
        # Phase 3-4 组件
        self.enable_content_analysis = enable_content_analysis
        self.enable_llm = enable_llm
        
        # 完整追问引擎
        self._guidance_engine = FullGuidanceEngine(
            enable_template=True,
            enable_semantic=enable_content_analysis,
            enable_llm=enable_llm,
            llm_config=llm_config,
        )
        
        # 回调
        self._on_full_guidance: Optional[Callable[[FullGuidanceResult], None]] = None
        
        # 最后结果
        self._last_full_guidance: Optional[FullGuidanceResult] = None
    
    def set_full_guidance_callback(self, callback: Callable[[FullGuidanceResult], None]):
        """设置完整追问回调"""
        self._on_full_guidance = callback
    
    def get_full_guidance(self) -> Optional[FullGuidanceResult]:
        """获取完整追问结果"""
        return self._last_full_guidance
    
    def chat(
        self,
        message: str,
        max_wait: float = 30.0,
        stream_callback: Optional[Callable[[str], None]] = None,
        force_compress: bool = False,
    ) -> str:
        """
        增强版 Chat 入口（整合 Phase 1-4）
        
        Args:
            message: 用户消息
            max_wait: 最大等待时间
            stream_callback: 流式输出回调
            force_compress: 强制压缩
            
        Returns:
            str: Agent 响应
        """
        # 调用父类的 chat（Phase 1）
        response = super().chat(
            message=message,
            max_wait=max_wait,
            stream_callback=stream_callback,
            force_compress=force_compress,
        )
        
        # Phase 3-4: 生成完整追问
        self._generate_full_guidance(message, response)
        
        return response
    
    def _generate_full_guidance(self, user_message: str, response: str):
        """生成完整追问"""
        # 获取意图分析
        intent_analysis = None
        if self._intent_classifier:
            ctx = self._context_manager.get_context(self.session_id) if self._context_manager else None
            intent_analysis = self._intent_classifier.classify(user_message, ctx)
        
        intent = intent_analysis.intent if intent_analysis else None
        context = self._context_manager.get_context(self.session_id) if self._context_manager else None
        
        # 生成完整追问
        self._last_full_guidance = self._guidance_engine.generate(
            user_message=user_message,
            response=response,
            intent=intent,
            context=context,
            intent_analysis=intent_analysis,
        )
        
        # 更新父类的追问结果
        if self._last_guidance and self._last_full_guidance:
            self._last_guidance.questions = self._last_full_guidance.all_questions
        
        # 触发回调
        if self._on_full_guidance and self._last_full_guidance:
            self._on_full_guidance(self._last_full_guidance)
    
    def append_full_guidance_to_response(self, response: str) -> str:
        """
        将完整追问追加到响应
        
        Args:
            response: 原始响应
            
        Returns:
            str: 带追问的响应
        """
        if not self._last_full_guidance or not self._last_full_guidance.all_questions:
            return response
        
        questions = self._last_full_guidance.all_questions
        if not questions:
            return response
        
        # 根据来源添加不同的引导前缀
        guidance_text = "\n\n---\n**💬 您可能还想问：**\n"
        for i, q in enumerate(questions, 1):
            guidance_text += f"{i}. {q}\n"
        
        return response + guidance_text
    
    def is_llm_available(self) -> bool:
        """检查 LLM 是否可用"""
        return self._guidance_engine.is_llm_available()
    
    def get_llm_models(self) -> List[str]:
        """获取可用的 LLM 模型"""
        return self._guidance_engine.get_llm_models()


def create_full_guidance_chat(
    base_chat,
    enable_llm: bool = True,
    model: str = "qwen2.5:1.5b",
    api_base: str = "http://localhost:11434",
) -> FullGuidanceAgentChat:
    """
    创建完整追问增强 AgentChat
    
    Args:
        base_chat: 原始 AgentChat
        enable_llm: 是否启用 LLM
        model: LLM 模型
        api_base: LLM API 地址
        
    Returns:
        FullGuidanceAgentChat: 增强后的 AgentChat
    """
    llm_config = None
    if enable_llm:
        llm_config = LLMGuidanceConfig(
            source=LLMSource.OLLAMA_LOCAL,
            model=model,
            api_base=api_base,
        )
    
    return FullGuidanceAgentChat(
        base_chat=base_chat,
        enable_llm=enable_llm,
        llm_config=llm_config,
    )


# ============== 便捷函数 ==============

def quick_full_guidance(
    user_message: str,
    response: str,
    intent: str = "",
    content_type: str = "general",
    enable_llm: bool = True,
) -> Dict[str, Any]:
    """
    快速生成完整追问
    
    Args:
        user_message: 用户消息
        response: AI 回答
        intent: 意图类型
        content_type: 内容类型
        enable_llm: 是否启用 LLM
        
    Returns:
        Dict: 包含所有来源的追问
    """
    # 语义追问
    semantic = generate_semantic_guidance(response, intent)
    
    result = {
        'template_questions': [],
        'semantic_questions': semantic.questions,
        'llm_questions': [],
        'all_questions': semantic.questions[:5],
        'content_type': content_type,
        'quality': None,
    }
    
    if semantic.quality_assessment:
        result['quality'] = {
            'level': semantic.quality_assessment.quality.value,
            'completeness': semantic.quality_assessment.completeness,
            'missing_info': semantic.quality_assessment.missing_info,
        }
    
    # LLM 追问
    if enable_llm:
        try:
            llm_result = quick_llm_guidance(
                user_message=user_message,
                response=response,
                intent=intent,
                content_type=content_type,
            )
            result['llm_questions'] = llm_result
            
            # 合并
            seen = set(s.lower() for s in result['all_questions'])
            for q in llm_result:
                if q.lower() not in seen:
                    result['all_questions'].append(q)
                    seen.add(q.lower())
            
            result['all_questions'] = result['all_questions'][:5]
        except Exception:
            pass
    
    return result


# ============== 导出 ==============

__all__ = [
    # 核心类
    'FullGuidanceResult',
    'FullGuidanceEngine',
    'FullGuidanceAgentChat',
    # 创建函数
    'create_full_guidance_chat',
    # 便捷函数
    'quick_full_guidance',
    # Phase 3-4 导出
    'LLMGuidanceConfig',
    'LLMSource',
    'GuidanceStrategy',
    'TriggerCondition',
    'LLMGuidanceResult',
    'HybridGuidanceResult',
    'LLMGuidanceGenerator',
    'GuidanceTrigger',
    'HybridGuidanceGenerator',
    'create_llm_generator',
    'create_hybrid_generator',
    'quick_llm_guidance',
]
