"""
内容引导集成模块 (Phase 3)
===========================

将内容分析引导集成到 EnhancedAgentChat

功能：
1. ContentAwareEnhancedAgentChat - 支持内容分析的增强 AgentChat
2. 追问策略增强 - 基于内容类型的智能追问
3. UI 集成 - 与 GuidancePanel 无缝集成
"""

from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass, field

# 导入 Phase 1 和 Phase 2 的模块
from .agent_chat_enhancer import (
    EnhancedAgentChat,
    ChatIntent,
    IntentAnalysis,
    ChatContext,
    GuidanceResult,
)

# 导入 Phase 3 的模块
from .content_guidance import (
    ContentType,
    ContentQuality,
    GuidanceDepth,
    ContentAnalysis,
    QualityAssessment,
    SemanticGuidanceResult,
    SemanticGuidanceGenerator,
    analyze_content,
    evaluate_quality,
    generate_semantic_guidance,
)


@dataclass
class EnhancedGuidanceResult:
    """增强版追问结果（Phase 1 + Phase 3 合并）"""
    # Phase 1 结果
    basic_questions: List[str] = field(default_factory=list)
    basic_strategy: str = ""
    basic_confidence: float = 0.0
    
    # Phase 3 结果
    semantic_questions: List[str] = field(default_factory=list)
    content_analysis: Optional[ContentAnalysis] = None
    quality_assessment: Optional[QualityAssessment] = None
    guidance_depth: GuidanceDepth = GuidanceDepth.MODERATE
    
    # 合并的追问（去重）
    all_questions: List[str] = field(default_factory=list)
    
    # 元数据
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def questions(self) -> List[str]:
        """获取所有追问（兼容 Phase 1 接口）"""
        return self.all_questions
    
    @property
    def strategy(self) -> str:
        """获取策略描述"""
        strategies = []
        if self.basic_questions:
            strategies.append("template")
        if self.semantic_questions:
            strategies.append("semantic")
        return "+".join(strategies) if strategies else "none"


class ContentAwareEnhancedAgentChat(EnhancedAgentChat):
    """
    内容感知增强 AgentChat
    
    在 EnhancedAgentChat 基础上增加：
    1. 内容类型识别
    2. 内容质量评估
    3. 语义追问生成
    4. 领域特定追问策略
    """
    
    def __init__(
        self,
        base_chat,
        enable_intent: bool = True,
        enable_compress: bool = True,
        enable_context: bool = True,
        enable_guidance: bool = True,
        enable_content_analysis: bool = True,  # Phase 3 新增
        max_guidance_questions: int = 5,        # Phase 3 增加到 5 个
    ):
        """
        Args:
            base_chat: 原始 AgentChat 实例
            enable_intent: 启用意图识别
            enable_compress: 启用 Query 压缩
            enable_context: 启用上下文管理
            enable_guidance: 启用追问生成
            enable_content_analysis: 启用内容分析（Phase 3）
            max_guidance_questions: 最大追问数量
        """
        # 调用父类初始化
        super().__init__(
            base_chat=base_chat,
            enable_intent=enable_intent,
            enable_compress=enable_compress,
            enable_context=enable_context,
            enable_guidance=enable_guidance,
            max_guidance_questions=max_guidance_questions,
        )
        
        # Phase 3 新增
        self.enable_content_analysis = enable_content_analysis
        self._semantic_generator = SemanticGuidanceGenerator() if enable_content_analysis else None
        
        # 回调
        self._on_content_analyzed: Optional[Callable[[ContentAnalysis], None]] = None
        self._on_quality_evaluated: Optional[Callable[[QualityAssessment], None]] = None
        
        # 上一次的增强追问结果
        self._last_enhanced_guidance: Optional[EnhancedGuidanceResult] = None
    
    def set_content_analysis_callback(self, callback: Callable[[ContentAnalysis], None]):
        """设置内容分析回调"""
        self._on_content_analyzed = callback
    
    def set_quality_evaluation_callback(self, callback: Callable[[QualityAssessment], None]):
        """设置质量评估回调"""
        self._on_quality_evaluated = callback
    
    def get_content_analysis(self) -> Optional[ContentAnalysis]:
        """获取上一次的内容分析结果"""
        if self._last_enhanced_guidance:
            return self._last_enhanced_guidance.content_analysis
        return None
    
    def get_quality_assessment(self) -> Optional[QualityAssessment]:
        """获取上一次的质量评估结果"""
        if self._last_enhanced_guidance:
            return self._last_enhanced_guidance.quality_assessment
        return None
    
    def get_enhanced_guidance(self) -> Optional[EnhancedGuidanceResult]:
        """获取增强版追问结果"""
        return self._last_enhanced_guidance
    
    def analyze_response(
        self,
        response: str,
        intent_type: str = ""
    ) -> SemanticGuidanceResult:
        """
        分析响应内容并生成语义追问
        
        Args:
            response: AI 响应内容
            intent_type: 意图类型
            
        Returns:
            SemanticGuidanceResult: 语义追问结果
        """
        if not self._semantic_generator:
            return SemanticGuidanceResult(questions=[])
        
        context = {}
        if self._context_manager:
            ctx = self._context_manager.get_context(self.session_id)
            context = {
                'message_count': ctx.message_count,
                'followup_count': ctx.followup_count,
                'topic': ctx.topic,
            }
        
        return self._semantic_generator.generate(response, intent_type, context)
    
    def chat(
        self,
        message: str,
        max_wait: float = 30.0,
        stream_callback: Optional[Callable[[str], None]] = None,
        force_compress: bool = False,
    ) -> str:
        """
        增强版 Chat 入口（集成 Phase 3 内容分析）
        
        Args:
            message: 用户消息
            max_wait: 最大等待时间
            stream_callback: 流式输出回调
            force_compress: 强制压缩
            
        Returns:
            str: Agent 响应
        """
        # 复用父类的 chat 方法（保持 Phase 1 和 Phase 2 的功能）
        response = super().chat(
            message=message,
            max_wait=max_wait,
            stream_callback=stream_callback,
            force_compress=force_compress,
        )
        
        # Phase 3: 内容分析（可选）
        if self.enable_content_analysis and self._semantic_generator:
            self._perform_content_analysis(response)
        
        return response
    
    def _perform_content_analysis(self, response: str):
        """执行内容分析"""
        # 获取原始意图（如果有）
        intent_type = ""
        if self._last_guidance and self._last_guidance.intent:
            intent_type = self._last_guidance.intent.value
        
        # 执行语义追问生成
        semantic_result = self.analyze_response(response, intent_type)
        
        # 合并 Phase 1 和 Phase 3 的追问
        basic_questions = self._last_guidance.questions if self._last_guidance else []
        
        # 去重合并
        seen = set()
        all_questions = []
        for q in basic_questions + semantic_result.questions:
            normalized = q.strip().lower()
            if normalized not in seen:
                seen.add(normalized)
                all_questions.append(q)
        
        # 构建增强结果
        self._last_enhanced_guidance = EnhancedGuidanceResult(
            basic_questions=basic_questions,
            basic_strategy=self._last_guidance.strategy if self._last_guidance else "",
            basic_confidence=self._last_guidance.confidence if self._last_guidance else 0.0,
            semantic_questions=semantic_result.questions,
            content_analysis=semantic_result.analysis,
            quality_assessment=semantic_result.quality_assessment,
            guidance_depth=semantic_result.depth,
            all_questions=all_questions[:self.max_guidance_questions],
            confidence=(self._last_guidance.confidence if self._last_guidance else 0.5 + semantic_result.confidence) / 2,
            metadata={
                'content_type': semantic_result.domain,
                'question_types': semantic_result.question_types,
                'related_signals': semantic_result.related_signals,
            }
        )
        
        # 触发回调
        if self._on_content_analyzed and semantic_result.analysis:
            self._on_content_analyzed(semantic_result.analysis)
        
        if self._on_quality_evaluated and semantic_result.quality_assessment:
            self._on_quality_evaluated(semantic_result.quality_assessment)
        
        # 更新父类的追问结果（保持兼容）
        if self._last_guidance:
            self._last_guidance.questions = self._last_enhanced_guidance.all_questions
    
    def append_enhanced_guidance_to_response(self, response: str) -> str:
        """
        将增强追问追加到响应末尾
        
        Args:
            response: 原始响应
            
        Returns:
            str: 带追问的响应
        """
        if not self._last_enhanced_guidance or not self._last_enhanced_guidance.all_questions:
            return response
        
        questions = self._last_enhanced_guidance.all_questions
        if not questions:
            return response
        
        # 根据内容类型添加不同的引导前缀
        content_type = self._last_enhanced_guidance.content_analysis.content_type.value if self._last_enhanced_guidance.content_analysis else "general"
        
        guidance_prefix = {
            'code': "**💻 代码相关：**",
            'documentation': "**📄 文档相关：**",
            'data': "**📊 数据相关：**",
            'tutorial': "**📝 教程相关：**",
            'explanation': "**💡 概念相关：**",
            'comparison': "**⚖️ 对比相关：**",
            'analysis': "**🔍 分析相关：**",
        }.get(content_type, "**💬 您可能还想问：**")
        
        # 构建追问文本
        guidance_text = f"\n\n---\n{guidance_prefix}\n"
        for i, q in enumerate(questions, 1):
            guidance_text += f"{i}. {q}\n"
        
        # 添加质量提示（可选）
        if self._last_enhanced_guidance.quality_assessment:
            quality = self._last_enhanced_guidance.quality_assessment
            if quality.missing_info:
                hint = f"\n📝 *提示：回答{'、'.join(quality.missing_info[:2])}*"
                guidance_text += hint
        
        return response + guidance_text


def enhance_agent_chat_with_content(
    base_chat,
    enable_intent: bool = True,
    enable_compress: bool = True,
    enable_context: bool = True,
    enable_guidance: bool = True,
    enable_content_analysis: bool = True,
    max_guidance_questions: int = 5,
) -> ContentAwareEnhancedAgentChat:
    """
    增强现有 AgentChat（集成 Phase 3 内容分析）
    
    Args:
        base_chat: AgentChat 实例
        enable_intent: 启用意图识别
        enable_compress: 启用 Query 压缩
        enable_context: 启用上下文管理
        enable_guidance: 启用追问生成
        enable_content_analysis: 启用内容分析（Phase 3）
        max_guidance_questions: 最大追问数量
        
    Returns:
        ContentAwareEnhancedAgentChat: 增强后的 AgentChat
    """
    return ContentAwareEnhancedAgentChat(
        base_chat=base_chat,
        enable_intent=enable_intent,
        enable_compress=enable_compress,
        enable_context=enable_context,
        enable_guidance=enable_guidance,
        enable_content_analysis=enable_content_analysis,
        max_guidance_questions=max_guidance_questions,
    )


# ============== 便捷函数 ==============

def quick_content_analysis(content: str) -> Dict[str, Any]:
    """
    快速内容分析（返回可读字典）
    
    Args:
        content: 内容文本
        
    Returns:
        Dict: 分析结果字典
    """
    result = analyze_content(content)
    quality = evaluate_quality(content, result.content_type)
    
    return {
        'content_type': result.content_type.value,
        'type_confidence': result.confidence,
        'has_code': result.has_code,
        'has_data': result.has_data,
        'has_steps': result.has_steps,
        'has_examples': result.has_examples,
        'complexity': result.complexity,
        'technical_depth': result.technical_depth,
        'length': result.length,
        'quality': quality.quality.value,
        'completeness': quality.completeness,
        'clarity': quality.clarity,
        'missing_info': quality.missing_info,
        'strengths': quality.strengths,
        'topics': result.topics,
    }


def generate_intelligent_guidance(
    content: str,
    intent_type: str = "",
    include_analysis: bool = True
) -> Dict[str, Any]:
    """
    生成智能追问（一体化函数）
    
    Args:
        content: 内容文本
        intent_type: 意图类型
        include_analysis: 是否包含详细分析
        
    Returns:
        Dict: 追问和分析结果
    """
    result = generate_semantic_guidance(content, intent_type)
    
    output = {
        'questions': result.questions,
        'depth': result.depth.value,
        'domain': result.domain,
        'confidence': result.confidence,
        'question_types': result.question_types,
        'related_signals': result.related_signals,
    }
    
    if include_analysis and result.analysis:
        output['analysis'] = {
            'content_type': result.analysis.content_type.value,
            'complexity': result.analysis.complexity,
            'technical_depth': result.analysis.technical_depth,
            'has_code': result.analysis.has_code,
            'has_data': result.analysis.has_data,
            'topics': result.analysis.topics,
        }
    
    if include_analysis and result.quality_assessment:
        output['quality'] = {
            'level': result.quality_assessment.quality.value,
            'completeness': result.quality_assessment.completeness,
            'clarity': result.quality_assessment.clarity,
            'missing_info': result.quality_assessment.missing_info,
            'strengths': result.quality_assessment.strengths,
        }
    
    return output


# ============== 导出 ==============

__all__ = [
    # 增强的 AgentChat
    'ContentAwareEnhancedAgentChat',
    'enhance_agent_chat_with_content',
    # 数据结构
    'EnhancedGuidanceResult',
    # Phase 3 核心
    'ContentType',
    'ContentQuality',
    'GuidanceDepth',
    'ContentAnalysis',
    'QualityAssessment',
    'SemanticGuidanceResult',
    'SemanticGuidanceGenerator',
    # 便捷函数
    'analyze_content',
    'evaluate_quality',
    'generate_semantic_guidance',
    'quick_content_analysis',
    'generate_intelligent_guidance',
]
