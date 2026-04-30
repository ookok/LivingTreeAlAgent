# -*- coding: utf-8 -*-
"""
智能提示系统集成 (Intelligent Hints Integration)
==============================================

将 SmartUISystem 与 intelligent_hints 模块集成，
实现 UI 操作预测与智能提示的协同工作。

集成方式:
1. ContextSniffer → 捕获操作 → SmartUISystem 记录
2. HintIntentEngine → 生成提示 → SmartUISystem 预测增强
3. HintMemory → 反馈收集 → SmartUISystem 学习

Author: LivingTreeAI Team
Date: 2026-04-24
"""

from business.logger import get_logger
logger = get_logger('ui_evolution.hints_integration')

import json
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime

# 导入 intelligent_hints 模块
try:
    from business.intelligent_hints import (
        ContextSniffer,
        ContextInfo,
        HintIntentEngine,
        GeneratedHint,
        HintType,
        HintLevel,
        HintMemory,
        GlobalAirIcon,
        get_context_sniffer,
        get_hint_engine,
        get_hint_memory,
        get_global_air_icon,
    )
    from business.intelligent_hints.global_signals import emit_hint_signal, HintSignalType
    
    HINTS_AVAILABLE = True
except ImportError:
    HINTS_AVAILABLE = False
    ContextSniffer = None
    ContextInfo = None


# =============================================================================
# 集成配置
# =============================================================================

@dataclass
class UIHintsConfig:
    """UI 提示配置"""
    # 预测启用
    enable_prediction: bool = True
    
    # 置信度阈值
    high_confidence_threshold: float = 0.7
    medium_confidence_threshold: float = 0.5
    
    # 显示设置
    show_prediction_badge: bool = True
    prediction_badge_timeout: float = 3.0  # 秒
    
    # 进化设置
    enable_evolution: bool = True
    instant_learning: bool = True
    
    # 知识库
    use_knowledge_base: bool = True


# =============================================================================
# UI 操作拦截器
# =============================================================================

class UIOperationInterceptor:
    """
    UI 操作拦截器
    
    拦截 UI 操作，记录到 SmartUISystem，
    并在 GlobalAirIcon 上显示预测建议。
    """
    
    def __init__(
        self,
        smart_ui_system,  # SmartUISystem
        config: UIHintsConfig = None,
    ):
        self.smart_ui = smart_ui_system
        self.config = config or UIHintsConfig()
        
        self._current_session_id: str = ""
        self._last_prediction: Optional[Dict] = None
        self._prediction_callbacks: List[Callable] = []
        
        self._lock = threading.Lock()
    
    def set_session(self, session_id: str):
        """设置当前会话"""
        self._current_session_id = session_id
    
    def on_operation(
        self,
        action_type: str,
        action_target: str,
        action_value: str = "",
        context: Dict[str, Any] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        操作事件回调
        
        当用户执行操作时调用此方法。
        """
        with self._lock:
            # 1. 处理操作并获取预测
            result = self.smart_ui.process_operation(
                action_type=action_type,
                action_target=action_target,
                action_value=action_value,
                context=context,
                session_id=self._current_session_id,
            )
            
            # 2. 如果有预测且置信度足够，显示提示
            if result.suggestion.is_confident and self.config.enable_prediction:
                self._show_prediction_toast(result.suggestion)
                
                # 3. 触发回调
                for callback in self._prediction_callbacks:
                    try:
                        callback(result.suggestion, result)
                    except Exception:
                        pass
            
            return {
                "suggestion": result.suggestion.to_dict(),
                "prediction_time_ms": result.prediction_time_ms,
            }
    
    def _show_prediction_toast(self, suggestion):
        """显示预测提示"""
        if not HINTS_AVAILABLE:
            return
        
        try:
            # 在 GlobalAirIcon 上显示预测
            air_icon = get_global_air_icon()
            if air_icon:
                air_icon.show_prediction_badge(
                    suggestion.action,
                    suggestion.confidence,
                    timeout=self.config.prediction_badge_timeout,
                )
        except Exception:
            pass
    
    def on_feedback(
        self,
        feedback: str,
        actual_action: str = "",
        corrected_action: str = "",
    ):
        """反馈事件回调"""
        self.smart_ui.record_feedback(
            feedback=feedback,
            actual_action=actual_action,
            corrected_action=corrected_action,
        )
    
    def register_prediction_callback(self, callback: Callable):
        """注册预测回调"""
        self._prediction_callbacks.append(callback)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        return self.smart_ui.get_stats()


# =============================================================================
# 提示增强器
# =============================================================================

class HintEnhancer:
    """
    提示增强器
    
    使用 SmartUISystem 的预测能力增强 intelligent_hints 的提示。
    """
    
    def __init__(
        self,
        smart_ui_system,  # SmartUISystem
        hint_intent_engine = None,  # HintIntentEngine
    ):
        self.smart_ui = smart_ui_system
        self.hint_engine = hint_intent_engine or (get_hint_engine() if HINTS_AVAILABLE else None)
    
    def enhance_hint(
        self,
        hint: GeneratedHint,
        session_id: str = None,
    ) -> GeneratedHint:
        """
        增强提示
        
        在生成提示后，使用 SmartUISystem 预测进一步增强。
        """
        if not self.config.enable_prediction:
            return hint
        
        # 获取当前预测
        prediction = self.smart_ui.predict_and_suggest(session_id)
        
        if prediction.is_confident:
            # 添加预测相关的提示
            hint.content += f"\n\n💡 下一步可能: {prediction.action}"
            hint.metadata["next_prediction"] = prediction.to_dict()
        
        return hint
    
    def should_show_hint(
        self,
        context: ContextInfo,
        hint: GeneratedHint,
    ) -> bool:
        """
        判断是否应该显示提示
        
        使用预测结果辅助决策。
        """
        # 如果预测置信度很高，可能不需要额外提示
        prediction = self.smart_ui.predict_and_suggest(context.session_id)
        
        if prediction.is_confident and prediction.confidence > 0.9:
            # 预测非常确定，可能不需要打扰用户
            # 除非提示是重要的警告
            if hint.level != HintLevel.WARNING:
                return False
        
        return True
    
    config = UIHintsConfig()


# =============================================================================
# 反馈桥接器
# =============================================================================

class FeedbackBridge:
    """
    反馈桥接器
    
    桥接 intelligent_hints 和 SmartUISystem 的反馈机制。
    """
    
    def __init__(
        self,
        feedback_collector,  # FeedbackCollector
        evolution_scheduler,  # EvolutionScheduler
    ):
        self.feedback_collector = feedback_collector
        self.evolution_scheduler = evolution_scheduler
        
        # 反馈映射
        self._feedback_map = {
            "accept": "accepted",
            "reject": "rejected",
            "correct": "corrected",
            "dismiss": "dismissed",
            "ignore": "ignored",
        }
    
    def on_hint_feedback(
        self,
        hint_id: str,
        feedback: str,
        context: Dict[str, Any] = None,
    ):
        """
        处理来自 intelligent_hints 的提示反馈
        """
        # 转换反馈类型
        feedback_type = self._feedback_map.get(feedback.lower(), "ignored")
        
        # 记录到反馈收集器
        self.feedback_collector.record_prediction(
            predicted_action=hint_id,
            confidence=0.5,  # 假设
            source="hint_engine",
            context=context,
        )
        self.feedback_collector.record_feedback(
            FeedbackType[feedback_type.upper()],
        )
        
        # 触发进化
        self.evolution_scheduler.trigger_learning(
            context=context.get("scene", ""),
            action=hint_id,
            sequence=[],  # 从 context 获取
            success=(feedback_type == "accepted"),
        )
    
    def on_prediction_feedback(
        self,
        predicted_action: str,
        confidence: float,
        source: str,
        feedback: str,
        actual_action: str = "",
        corrected_action: str = "",
    ):
        """
        处理来自 SmartUISystem 的预测反馈
        """
        feedback_type = self._feedback_map.get(feedback.lower(), "ignored")
        
        # 记录反馈
        self.feedback_collector.record_prediction(
            predicted_action=predicted_action,
            confidence=confidence,
            source=source,
        )
        self.feedback_collector.record_feedback(
            FeedbackType[feedback_type.upper()],
            actual_action=actual_action,
            corrected_action=corrected_action,
        )
        
        # 触发进化
        success = feedback_type in ["accepted", "corrected"]
        self.evolution_scheduler.trigger_learning(
            context=predicted_action,
            action=corrected_action or actual_action or predicted_action,
            sequence=[],
            success=success,
        )


# =============================================================================
# 便捷函数
# =============================================================================

def create_ui_hints_integration(
    enable_prediction: bool = True,
    enable_evolution: bool = True,
) -> Optional[UIOperationInterceptor]:
    """
    创建 UI 提示集成
    
    使用示例:
    ```python
    from business.ui_evolution import create_ui_hints_integration
    
    # 创建集成
    interceptor = create_ui_hints_integration(
        enable_prediction=True,
        enable_evolution=True,
    )
    
    # 在 UI 操作时调用
    interceptor.on_operation("click", "send_btn")
    
    # 用户响应后调用
    interceptor.on_feedback("accept")
    ```
    """
    if not HINTS_AVAILABLE:
        logger.info("警告: intelligent_hints 模块不可用")
        return None
    
    try:
        # 导入 SmartUISystem
        from .smart_ui_system import get_smart_ui_system

        
        # 创建系统
        smart_ui = get_smart_ui_system()
        
        # 创建配置
        config = UIHintsConfig(
            enable_prediction=enable_prediction,
            enable_evolution=enable_evolution,
        )
        
        # 创建拦截器
        return UIOperationInterceptor(smart_ui, config)
        
    except Exception as e:
        logger.info(f"创建 UI 提示集成失败: {e}")
        return None


def enable_context_sniffer_integration(interceptor: UIOperationInterceptor):
    """
    启用 ContextSniffer 集成
    
    将 SmartUISystem 集成到 ContextSniffer 的事件流中。
    """
    if not HINTS_AVAILABLE:
        return
    
    try:
        sniffer = get_context_sniffer()
        
        # 注册操作钩子
        def on_context_change(context: ContextInfo):
            # 从上下文提取操作信息
            if hasattr(context, 'action_type'):
                interceptor.on_operation(
                    action_type=context.action_type,
                    action_target=context.action_target or "",
                    action_value=context.action_value or "",
                    context=context.metadata,
                )
        
        # 添加钩子
        sniffer.add_hook(
            hook_id="smart_ui_predictor",
            name="智能预测器",
            callback=on_context_change,
            priority=50,
        )
        
    except Exception as e:
        logger.info(f"启用 ContextSniffer 集成失败: {e}")


# =============================================================================
# 导出
# =============================================================================

__all__ = [
    "UIHintsConfig",
    "UIOperationInterceptor",
    "HintEnhancer",
    "FeedbackBridge",
    "create_ui_hints_integration",
    "enable_context_sniffer_integration",
]
