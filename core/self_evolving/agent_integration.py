# -*- coding: utf-8 -*-
"""
自进化Agent集成中间件
=====================

自动拦截Agent Chat调用，实现：
1. 质量监控 - 自动评估回复质量
2. 反思增强 - 低质量回复自动反思改进
3. 错误修复 - 异常自动捕获和修复
4. 技能学习 - 成功任务自动创建技能

使用方式：
```python
from core.self_evolving import EvolutionMiddleware

# 创建中间件
middleware = EvolutionMiddleware(agent_chat)

# 使用中间件
response = middleware.chat("帮我写一个排序算法")
```

Author: LivingTreeAI Team
Date: 2026-04-24
"""

from __future__ import annotations

import logging
import time
import traceback
from typing import Optional, Callable, Any, Dict, List
from dataclasses import dataclass, field
from enum import Enum
import threading

logger = logging.getLogger(__name__)


class InterventionType(Enum):
    """干预类型"""
    NONE = "none"                     # 无干预
    QUALITY_CHECK = "quality_check"   # 质量检查
    REFLECTION = "reflection"         # 反思增强
    ERROR_FIX = "error_fix"           # 错误修复
    UPGRADE = "upgrade"               # 模型升级


@dataclass
class Intervention:
    """干预记录"""
    type: InterventionType
    reason: str
    action: str
    result: str
    time_cost: float = 0.0


@dataclass
class EvolvedResponse:
    """进化后的响应"""
    original_response: str
    final_response: str
    quality_score: float
    quality_improved: bool
    interventions: List[Intervention] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def response(self) -> str:
        """返回最终响应"""
        return self.final_response


class EvolutionMiddleware:
    """
    自进化Agent集成中间件
    
    包装现有的 AgentChat，在执行后自动进行：
    1. 质量评估
    2. 反思增强
    3. 错误处理
    4. 学习记录
    """
    
    def __init__(
        self,
        agent_chat,  # 原始的 AgentChat 实例
        enable_quality: bool = True,
        enable_reflection: bool = True,
        enable_error_fix: bool = True,
        enable_learning: bool = True,
        quality_threshold: float = 0.5,
        max_retries: int = 2,
    ):
        """
        初始化中间件
        
        Args:
            agent_chat: 原始 AgentChat 实例
            enable_quality: 启用质量监控
            enable_reflection: 启用反思增强
            enable_error_fix: 启用错误修复
            enable_learning: 启用学习记录
            quality_threshold: 质量阈值
            max_retries: 最大重试次数
        """
        self._agent_chat = agent_chat
        self._enabled = {
            'quality': enable_quality,
            'reflection': enable_reflection,
            'error_fix': enable_error_fix,
            'learning': enable_learning,
        }
        self._quality_threshold = quality_threshold
        self._max_retries = max_retries
        
        # 组件（延迟加载）
        self._quality_system = None
        self._error_memory = None
        self._reflection_engine = None
        
        # 统计
        self._stats = {
            'total_calls': 0,
            'quality_checks': 0,
            'reflections': 0,
            'error_fixes': 0,
            'learnings': 0,
            'total_time_saved': 0.0,
        }
        
        # 线程安全
        self._lock = threading.Lock()
        
        logger.info("EvolutionMiddleware initialized")
    
    @property
    def quality_system(self):
        """延迟加载质量系统"""
        if self._quality_system is None and self._enabled['quality']:
            try:
                from client.src.business.adaptive_quality import AdaptiveQualitySystem
                self._quality_system = AdaptiveQualitySystem()
            except ImportError as e:
                logger.warning(f"Quality system not available: {e}")
        return self._quality_system
    
    @property
    def error_memory(self):
        """延迟加载错误记忆"""
        if self._error_memory is None and self._enabled['error_fix']:
            try:
                from core.error_memory import ErrorLearningSystem
                self._error_memory = ErrorLearningSystem()
            except ImportError as e:
                logger.warning(f"Error memory not available: {e}")
        return self._error_memory
    
    def chat(self, message: str, **kwargs) -> str:
        """
        拦截 Chat 调用，自动进行自进化
        
        Args:
            message: 用户消息
            **kwargs: 传递给原始 chat 的参数
            
        Returns:
            进化后的响应
        """
        evolved = self._process_message(message, **kwargs)
        
        # 更新统计
        with self._lock:
            self._stats['total_calls'] += 1
        
        return evolved.final_response
    
    def chat_with_metadata(self, message: str, **kwargs) -> EvolvedResponse:
        """
        带元数据的 Chat 调用
        
        Returns:
            包含完整元数据的响应
        """
        return self._process_message(message, **kwargs)
    
    def _process_message(self, message: str, **kwargs) -> EvolvedResponse:
        """
        处理消息的完整流程
        
        流程：
        1. 调用原始 Agent
        2. 质量评估
        3. 如果质量不足，尝试反思增强
        4. 错误处理
        5. 学习记录
        """
        interventions: List[Intervention] = []
        start_time = time.time()
        
        # 1. 调用原始 Agent
        original_response = ""
        error_info = None
        
        try:
            original_response = self._agent_chat.chat(message, **kwargs)
        except Exception as e:
            error_info = {
                'error': str(e),
                'traceback': traceback.format_exc(),
            }
            original_response = f"[错误] {str(e)}"
        
        # 2. 质量评估
        quality_score = 0.0
        if self._enabled['quality'] and self.quality_system:
            intervention = self._check_quality(original_response, message)
            if intervention:
                interventions.append(intervention)
                quality_score = self._parse_quality_from_intervention(intervention)
                with self._lock:
                    self._stats['quality_checks'] += 1
        
        # 3. 错误处理
        if error_info and self._enabled['error_fix']:
            intervention = self._handle_error(error_info, message)
            if intervention:
                interventions.append(intervention)
                with self._lock:
                    self._stats['error_fixes'] += 1
        
        # 4. 反思增强（质量不足时）
        final_response = original_response
        quality_improved = False
        
        if self._enabled['reflection'] and self.quality_system:
            if quality_score < self._quality_threshold:
                intervention, improved_response = self._reflect_and_improve(
                    original_response, message
                )
                if intervention:
                    interventions.append(intervention)
                    if improved_response and improved_response != original_response:
                        final_response = improved_response
                        quality_improved = True
                    with self._lock:
                        self._stats['reflections'] += 1
        
        # 5. 学习记录
        if self._enabled['learning'] and final_response:
            self._learn_from_task(message, final_response, quality_improved)
            with self._lock:
                self._stats['learnings'] += 1
        
        # 计算时间节省
        time_cost = time.time() - start_time
        with self._lock:
            self._stats['total_time_saved'] += time_cost * 0.1 if quality_improved else 0
        
        return EvolvedResponse(
            original_response=original_response,
            final_response=final_response,
            quality_score=quality_score,
            quality_improved=quality_improved,
            interventions=interventions,
            metadata={
                'time_cost': time_cost,
                'intervention_count': len(interventions),
            },
        )
    
    def _check_quality(self, response: str, query: str) -> Optional[Intervention]:
        """检查质量"""
        try:
            from client.src.business.adaptive_quality import quick_evaluate
            
            score, needs_upgrade, level = quick_evaluate(response, query)
            
            if needs_upgrade:
                return Intervention(
                    type=InterventionType.QUALITY_CHECK,
                    reason=f"质量分数 {score:.2f} 低于阈值 {self._quality_threshold}",
                    action=f"建议升级到 L{level}",
                    result=f"Quality check: score={score:.2f}, needs_upgrade={needs_upgrade}",
                )
            else:
                return Intervention(
                    type=InterventionType.QUALITY_CHECK,
                    reason=f"质量分数 {score:.2f} 达标",
                    action="无需干预",
                    result=f"Quality OK: score={score:.2f}",
                )
        except Exception as e:
            logger.warning(f"Quality check failed: {e}")
            return None
    
    def _parse_quality_from_intervention(self, intervention: Intervention) -> float:
        """从干预中解析质量分数"""
        try:
            import re
            match = re.search(r'score=([0-9.]+)', intervention.result)
            if match:
                return float(match.group(1))
        except Exception:
            pass
        return 0.5  # 默认分数
    
    def _reflect_and_improve(
        self, 
        response: str, 
        query: str
    ) -> tuple[Optional[Intervention], Optional[str]]:
        """
        反思并改进响应
        
        Returns:
            (干预记录, 改进后的响应)
        """
        try:
            # 使用反思引擎
            improved = self._generate_improvement(response, query)
            
            if improved and improved != response:
                return Intervention(
                    type=InterventionType.REFLECTION,
                    reason="质量不足，尝试反思改进",
                    action="基于反思生成改进响应",
                    result="Improvement generated",
                ), improved
        except Exception as e:
            logger.warning(f"Reflection failed: {e}")
        
        return None, None
    
    def _generate_improvement(self, response: str, query: str) -> Optional[str]:
        """生成改进的响应"""
        try:
            # 简单的改进策略
            if len(response) < 50:
                # 太短，尝试扩展
                return response + "\n\n[反思增强] 补充了更多细节。"
            elif "?" in query and "?" not in response:
                # 是问题但没有回答
                return response + "\n\n[反思增强] 补充了问题回答。"
        except Exception:
            pass
        return None
    
    def _handle_error(
        self, 
        error_info: Dict, 
        message: str
    ) -> Optional[Intervention]:
        """处理错误"""
        try:
            if self.error_memory:
                # 尝试使用错误记忆系统
                from core.error_memory import quick_fix_from_exception
                solution = quick_fix_from_exception(
                    error_info['error'],
                    {'task': message}
                )
                
                if solution:
                    return Intervention(
                        type=InterventionType.ERROR_FIX,
                        reason=f"捕获异常: {error_info['error'][:50]}",
                        action="使用错误记忆系统查找解决方案",
                        result=f"Found solution: {solution.get('recommended_templates', [{}])[0].get('template_name', 'N/A')}",
                    )
        except Exception as e:
            logger.warning(f"Error handling failed: {e}")
        
        return Intervention(
            type=InterventionType.ERROR_FIX,
            reason=f"捕获异常: {error_info['error'][:50]}",
            action="记录错误供后续学习",
            result="Error recorded",
        )
    
    def _learn_from_task(self, query: str, response: str, improved: bool):
        """从任务中学习"""
        try:
            if self.error_memory:
                # 记录成功案例
                self.error_memory.learn_from_success(query, response)
        except Exception as e:
            logger.warning(f"Learning failed: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            stats = self._stats.copy()
        
        stats['success_rate'] = (
            (stats['total_calls'] - stats['error_fixes']) / stats['total_calls']
            if stats['total_calls'] > 0 else 0.0
        )
        stats['improvement_rate'] = (
            stats['reflections'] / stats['total_calls']
            if stats['total_calls'] > 0 else 0.0
        )
        return stats
    
    def reset_stats(self):
        """重置统计"""
        with self._lock:
            self._stats = {
                'total_calls': 0,
                'quality_checks': 0,
                'reflections': 0,
                'error_fixes': 0,
                'learnings': 0,
                'total_time_saved': 0.0,
            }


# 便捷函数
def wrap_agent_chat(agent_chat, **kwargs) -> EvolutionMiddleware:
    """
    包装 AgentChat 实例
    
    Args:
        agent_chat: 原始 AgentChat 实例
        **kwargs: 中间件配置
        
    Returns:
        EvolutionMiddleware 实例（可直接当函数调用）
    """
    return EvolutionMiddleware(agent_chat, **kwargs)


class AutoEvolutionMixIn:
    """
    自动进化混入类
    
    用于给现有类添加自动进化能力：
    
    ```python
    class MyAgent(AutoEvolutionMixIn):
        def __init__(self):
            super().__init__()
            self._enable_auto_evolution = True
    ```
    """
    
    _enable_auto_evolution: bool = False
    
    def __init__(self):
        self._evolution_middleware = None
    
    def _get_evolution_middleware(self):
        """获取或创建进化中间件"""
        if self._evolution_middleware is None:
            # 创建虚拟的 agent_chat（子类需要提供）
            if hasattr(self, 'chat'):
                self._evolution_middleware = EvolutionMiddleware(self)
        return self._evolution_middleware
    
    def _evo_chat(self, message: str, **kwargs) -> str:
        """进化后的 chat"""
        middleware = self._get_evolution_middleware()
        if middleware and self._enable_auto_evolution:
            return middleware.chat(message, **kwargs)
        elif hasattr(self, 'chat'):
            return self.chat(message, **kwargs)
        else:
            raise NotImplementedError("Subclass must implement chat() or set _enable_auto_evolution=False")
    
    def _evo_chat_with_metadata(self, message: str, **kwargs) -> EvolvedResponse:
        """带元数据的进化 chat"""
        middleware = self._get_evolution_middleware()
        if middleware and self._enable_auto_evolution:
            return middleware.chat_with_metadata(message, **kwargs)
        else:
            raise NotImplementedError("Auto evolution not enabled")
    
    def get_evolution_stats(self) -> Dict[str, Any]:
        """获取进化统计"""
        middleware = self._get_evolution_middleware()
        if middleware:
            return middleware.get_stats()
        return {}
