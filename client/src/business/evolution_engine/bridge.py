# -*- coding: utf-8 -*-
"""
Evolution-Intent Bridge - Evolution Engine 与 IntentEngine 联动
==============================================================

核心功能：
1. 意图 → 进化信号：将用户意图转化为 Evolution Engine 的触发信号
2. 进化 → 意图增强：将 Evolution Engine 的洞察用于增强意图解析
3. 反馈闭环：将意图执行结果反馈给 Evolution Engine 学习

Author: Hermes Desktop Team
from __future__ import annotations
"""


import logging
from typing import Optional, Dict, Any, List, Callable, TYPE_CHECKING
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

if TYPE_CHECKING:
    from client.src.business.intent_engine import IntentEngine
    from client.src.business.intent_engine.intent_types import Intent, IntentType, IntentPriority
    from client.src.business.evolution_engine import EvolutionEngine

logger = logging.getLogger(__name__)


# ==================== 数据模型 ====================

class IntentSignalType(Enum):
    """意图信号类型（映射到 EvolutionSignal）"""
    # 代码生成相关
    CODE_GENERATION = "code_generation"
    CODE_MODIFICATION = "code_modification"
    CODE_REFACTOR = "code_refactor"
    
    # 调试相关
    DEBUGGING = "debugging"
    BUG_FIX = "bug_fix"
    
    # 分析相关
    CODE_UNDERSTANDING = "code_understanding"
    CODE_REVIEW = "code_review"
    PERFORMANCE_ANALYSIS = "performance_analysis"
    
    # 设计相关
    API_DESIGN = "api_design"
    DATABASE_DESIGN = "database_design"
    
    # 部署相关
    DEPLOYMENT = "deployment"
    
    # 知识相关
    KNOWLEDGE_QUERY = "knowledge_query"
    CONCEPT_EXPLANATION = "concept_explanation"
    
    # 其他
    UNKNOWN = "unknown"


@dataclass
class IntentSignal:
    """意图信号 - IntentEngine 与 EvolutionEngine 之间的桥梁"""
    # 信号来源
    query: str  # 原始查询
    intent_type: IntentSignalType
    
    # 意图详情
    action: str  # 动作（编写/修复/分析等）
    target: str  # 目标（登录接口/性能问题等）
    tech_stack: List[str] = field(default_factory=list)  # 技术栈
    
    # 质量指标
    confidence: float = 0.0  # 置信度
    completeness: float = 0.0  # 完整性
    priority: str = "medium"  # 优先级
    
    # 元数据
    timestamp: datetime = field(default_factory=datetime.now)
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_evolution_signal(self) -> Dict[str, Any]:
        """转换为 EvolutionEngine 格式"""
        return {
            'source': 'intent_engine',
            'signal_type': self.intent_type.value,
            'query': self.query,
            'action': self.action,
            'target': self.target,
            'tech_stack': self.tech_stack,
            'confidence': self.confidence,
            'completeness': self.completeness,
            'priority': self.priority,
            'timestamp': self.timestamp.isoformat(),
        }


@dataclass
class ExecutionFeedback:
    """执行反馈 - 从 IntentEngine 执行结果到 EvolutionEngine"""
    intent_id: str
    success: bool
    duration_ms: float
    output: str  # 执行结果摘要
    errors: List[str] = field(default_factory=list)
    quality_score: float = 0.0  # 质量评分
    user_satisfaction: Optional[float] = None  # 用户满意度（如果可用）
    
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_evolution_record(self) -> Dict[str, Any]:
        """转换为 EvolutionEngine 记录格式"""
        return {
            'intent_id': self.intent_id,
            'success': self.success,
            'duration_ms': self.duration_ms,
            'quality_score': self.quality_score,
            'user_satisfaction': self.user_satisfaction,
            'error_count': len(self.errors),
            'timestamp': self.timestamp.isoformat(),
        }


@dataclass
class LearningEnhancement:
    """学习增强 - 从 EvolutionEngine 到 IntentEngine"""
    # 基于历史学习的洞察
    similar_intents: List[Dict[str, Any]] = field(default_factory=list)
    
    # 成功模式
    successful_patterns: List[str] = field(default_factory=list)
    
    # 风险提示
    risk_warnings: List[str] = field(default_factory=list)
    
    # 建议模型
    suggested_model: str = ""
    
    # 额外上下文
    context: Dict[str, Any] = field(default_factory=dict)


# ==================== 联动桥接器 ====================

class EvolutionIntentBridge:
    """
    Evolution-Intent 桥接器
    
    在 IntentEngine 和 EvolutionEngine 之间建立双向通信：
    - IntentEngine → EvolutionEngine：发送信号、反馈执行结果
    - EvolutionEngine → IntentEngine：提供学习增强、风险警告
    """
    
    def __init__(
        self,
        intent_engine: Optional['IntentEngine'] = None,
        evolution_engine: Optional['EvolutionEngine'] = None,
    ):
        self.intent_engine = intent_engine
        self.evolution_engine = evolution_engine
        
        # 回调钩子
        self._on_signal_emitted: Optional[Callable] = None
        self._on_feedback_received: Optional[Callable] = None
        
        # 统计
        self.stats = {
            'signals_sent': 0,
            'feedback_received': 0,
            'enhancements_provided': 0,
        }
    
    # ==================== 连接管理 ====================
    
    def connect_intent_engine(self, engine: 'IntentEngine'):
        """连接 IntentEngine"""
        self.intent_engine = engine
        logger.info("IntentEngine 已连接")
    
    def connect_evolution_engine(self, engine: 'EvolutionEngine'):
        """连接 EvolutionEngine"""
        self.evolution_engine = engine
        logger.info("EvolutionEngine 已连接")
    
    def set_hooks(
        self,
        on_signal: Optional[Callable] = None,
        on_feedback: Optional[Callable] = None,
    ):
        """设置回调钩子"""
        self._on_signal_emitted = on_signal
        self._on_feedback_received = on_feedback
    
    # ==================== 核心功能 ====================
    
    def process_intent(self, query: str) -> 'Intent':
        """
        处理用户意图（IntentEngine → EvolutionEngine 联动）
        
        流程：
        1. 调用 IntentEngine.parse() 解析意图
        2. 根据意图生成 Evolution 信号
        3. 获取 Evolution 增强（如果可用）
        4. 返回增强后的意图结果
        
        Args:
            query: 自然语言查询
        
        Returns:
            Intent: 解析后的意图（可能包含增强信息）
        """
        if not self.intent_engine:
            raise RuntimeError("IntentEngine 未连接")
        
        # 1. 解析意图
        intent = self.intent_engine.parse(query)
        
        # 2. 发送信号到 EvolutionEngine
        signal = self._create_signal_from_intent(intent)
        self._emit_signal(signal)
        
        # 3. 获取 Evolution 增强
        if self.evolution_engine:
            enhancement = self._get_learning_enhancement(intent)
            if enhancement:
                # 将增强信息附加到 intent 的 context
                intent.context = {
                    **(intent.context or {}),
                    'evolution_enhancement': asdict(enhancement) if hasattr(enhancement, '__dataclass_fields__') else enhancement,
                }
        
        return intent
    
    def _create_signal_from_intent(self, intent: 'Intent') -> IntentSignal:
        """从 Intent 创建 Evolution 信号"""
        # 映射 IntentType → IntentSignalType
        type_mapping = {
            'CODE_GENERATION': IntentSignalType.CODE_GENERATION,
            'CODE_MODIFICATION': IntentSignalType.CODE_MODIFICATION,
            'CODE_REFACTOR': IntentSignalType.CODE_REFACTOR,
            'DEBUGGING': IntentSignalType.DEBUGGING,
            'BUG_FIX': IntentSignalType.BUG_FIX,
            'CODE_UNDERSTANDING': IntentSignalType.CODE_UNDERSTANDING,
            'CODE_REVIEW': IntentSignalType.CODE_REVIEW,
            'PERFORMANCE_ANALYSIS': IntentSignalType.PERFORMANCE_ANALYSIS,
            'API_DESIGN': IntentSignalType.API_DESIGN,
            'DATABASE_DESIGN': IntentSignalType.DATABASE_DESIGN,
            'DEPLOYMENT': IntentSignalType.DEPLOYMENT,
            'KNOWLEDGE_QUERY': IntentSignalType.KNOWLEDGE_QUERY,
            'CONCEPT_EXPLANATION': IntentSignalType.CONCEPT_EXPLANATION,
        }
        
        signal_type = type_mapping.get(
            intent.intent_type.value.upper() if hasattr(intent.intent_type, 'value') else str(intent.intent_type),
            IntentSignalType.UNKNOWN
        )
        
        # 确定优先级
        priority_map = {
            'high': ['DEPLOYMENT', 'BUG_FIX', 'CODE_REFACTOR'],
            'medium': ['CODE_GENERATION', 'CODE_MODIFICATION', 'DEBUGGING'],
            'low': ['KNOWLEDGE_QUERY', 'CONCEPT_EXPLANATION'],
        }
        priority = 'medium'
        for p, types in priority_map.items():
            if signal_type.value.upper() in types:
                priority = p
                break
        
        return IntentSignal(
            query=intent.raw_input,
            intent_type=signal_type,
            action=intent.action or '',
            target=intent.target or '',
            tech_stack=intent.tech_stack or [],
            confidence=intent.confidence,
            completeness=intent.completeness,
            priority=priority,
            timestamp=datetime.now(),
        )
    
    def _emit_signal(self, signal: IntentSignal):
        """发送信号到 EvolutionEngine"""
        if not self.evolution_engine:
            return
        
        try:
            # 转换为 EvolutionEngine 格式
            evolution_signal = signal.to_evolution_signal()
            
            # 记录到 PatternMiner
            from client.src.business.evolution_engine.memory import PatternMiner, get_pattern_miner
            pattern_miner = get_pattern_miner()
            if pattern_miner:
                pattern_miner.add_event({
                    'type': 'intent_signal',
                    'timestamp': datetime.now().isoformat(),
                    'data': evolution_signal,
                })
            
            self.stats['signals_sent'] += 1
            
            # 触发回调
            if self._on_signal_emitted:
                self._on_signal_emitted(signal)
                
        except Exception as e:
            logger.error(f"发送信号失败: {e}")
    
    def _get_learning_enhancement(self, intent: 'Intent') -> Optional[LearningEnhancement]:
        """获取 EvolutionEngine 学习增强"""
        try:
            # 获取洞察
            insights = self.evolution_engine.get_learning_insights()
            
            # 查找与当前意图相关的洞察
            relevant_insights = [
                i for i in insights
                if i.get('category') == intent.intent_type.value.lower()
                or any(tech in str(i.get('description', '')) for tech in intent.tech_stack)
            ][:3]  # 最多3条
            
            # 获取模式
            patterns = self.evolution_engine.get_patterns_summary()
            
            enhancement = LearningEnhancement(
                similar_intents=relevant_insights,
                successful_patterns=self._extract_patterns(patterns),
                risk_warnings=self._generate_risk_warnings(intent, insights),
                suggested_model=self.intent_engine.suggest_model(intent) if self.intent_engine else '',
                context={
                    'pattern_count': len(patterns),
                    'insight_count': len(relevant_insights),
                }
            )
            
            self.stats['enhancements_provided'] += 1
            return enhancement
            
        except Exception as e:
            logger.error(f"获取学习增强失败: {e}")
            return None
    
    def _extract_patterns(self, patterns: Dict[str, Any]) -> List[str]:
        """提取模式摘要"""
        result = []
        
        # 时序模式
        temporal = patterns.get('temporal_patterns', [])
        if temporal:
            result.append(f"时序模式: {len(temporal)} 个")
        
        # 共现模式
        co_occurrence = patterns.get('co_occurrence_patterns', [])
        if co_occurrence:
            result.append(f"共现模式: {len(co_occurrence)} 个")
        
        return result[:3]  # 最多3条
    
    def _generate_risk_warnings(
        self,
        intent: 'Intent',
        insights: List[Dict]
    ) -> List[str]:
        """生成风险警告"""
        warnings = []
        
        # 基于置信度
        if intent.confidence < 0.6:
            warnings.append("意图置信度较低，建议补充更多细节")
        
        # 基于完整性
        if intent.completeness < 0.5:
            warnings.append("意图信息不完整，可能影响执行效果")
        
        # 基于洞察
        for insight in insights:
            if insight.get('category') == 'execution' and insight.get('success') is False:
                warnings.append(f"历史执行警告: {insight.get('description', '')[:50]}")
        
        return warnings[:2]  # 最多2条
    
    # ==================== 反馈闭环 ====================
    
    def report_execution_result(self, feedback: ExecutionFeedback):
        """
        报告执行结果给 EvolutionEngine（闭环反馈）
        
        Args:
            feedback: 执行反馈
        """
        if not self.evolution_engine:
            return
        
        try:
            # 记录到 LearningEngine
            from client.src.business.evolution_engine.memory import LearningEngine, get_learning_engine
            learning_engine = get_learning_engine()
            
            if learning_engine:
                # 模拟信号（用于学习）
                signals = [{
                    'type': 'execution_feedback',
                    'quality': feedback.quality_score,
                    'duration': feedback.duration_ms,
                    'error_count': len(feedback.errors),
                }]
                
                # 执行结果
                execution_result = {
                    'success': feedback.success,
                    'quality_score': feedback.quality_score,
                    'duration_ms': feedback.duration_ms,
                }
                
                learning_engine.learn_from_execution(
                    proposal_type='intent_execution',
                    proposal_id=feedback.intent_id,
                    signals=signals,
                    execution_result=execution_result,
                )
            
            # 记录到 PatternMiner
            from client.src.business.evolution_engine.memory import PatternMiner, get_pattern_miner
            pattern_miner = get_pattern_miner()
            if pattern_miner:
                pattern_miner.add_event({
                    'type': 'execution_feedback',
                    'timestamp': datetime.now().isoformat(),
                    'data': feedback.to_evolution_record(),
                })
            
            self.stats['feedback_received'] += 1
            
            # 触发回调
            if self._on_feedback_received:
                self._on_feedback_received(feedback)
                
        except Exception as e:
            logger.error(f"报告执行结果失败: {e}")
    
    # ==================== 便捷方法 ====================
    
    def quick_process(self, query: str) -> Dict[str, Any]:
        """
        快速处理：解析 + 执行 + 反馈一站式
        
        Args:
            query: 自然语言查询
        
        Returns:
            Dict: 包含意图、结果和增强信息
        """
        # 解析意图
        intent = self.process_intent(query)
        
        return {
            'intent': intent,
            'enhancement': intent.context.get('evolution_enhancement') if intent.context else None,
            'stats': self.stats.copy(),
        }
    
    def get_bridge_status(self) -> Dict[str, Any]:
        """获取桥接器状态"""
        return {
            'intent_engine_connected': self.intent_engine is not None,
            'evolution_engine_connected': self.evolution_engine is not None,
            'stats': self.stats,
        }


# ==================== 辅助函数 ====================

def asdict(obj):
    """将 dataclass 转换为 dict"""
    if hasattr(obj, '__dataclass_fields__'):
        return {
            k: asdict(v) if hasattr(v, '__dataclass_fields__') else v
            for k, v in obj.__dict__.items()
            if not k.startswith('_')
        }
    return obj


# ==================== 工厂函数 ====================

def create_bridge(
    intent_engine: Optional['IntentEngine'] = None,
    evolution_engine: Optional['EvolutionEngine'] = None,
) -> EvolutionIntentBridge:
    """
    创建 Evolution-Intent 桥接器
    
    Args:
        intent_engine: IntentEngine 实例
        evolution_engine: EvolutionEngine 实例
    
    Returns:
        EvolutionIntentBridge 实例
    """
    return EvolutionIntentBridge(intent_engine, evolution_engine)


def create_full_bridge() -> EvolutionIntentBridge:
    """
    创建完整桥接器（自动初始化两个引擎）
    
    Returns:
        配置完整的 EvolutionIntentBridge
    """
    from client.src.business.intent_engine import IntentEngine
    from client.src.business.evolution_engine import create_evolution_engine
    
    # 初始化引擎
    intent_engine = IntentEngine()
    evolution_engine = create_evolution_engine(project_root=".")
    
    # 创建桥接器
    bridge = create_bridge(intent_engine, evolution_engine)
    
    return bridge


# ==================== 导出 ====================

__all__ = [
    'EvolutionIntentBridge',
    'IntentSignal',
    'IntentSignalType',
    'ExecutionFeedback',
    'LearningEnhancement',
    'create_bridge',
    'create_full_bridge',
]
