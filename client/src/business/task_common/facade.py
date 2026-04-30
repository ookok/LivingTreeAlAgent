"""
Task Common - 门面类

为所有任务分解器提供统一调用接口（门面模式）。
不修改原有实现，只包装调用。
"""

from typing import List, Dict, Any, Optional
from business.task_common import (
    BaseTaskDecomposer,
    DecomposedTask,
    DecomposerType,
    create_decomposer,
    auto_select_decomposer,
)
import logging

logger = logging.getLogger(__name__)


class TaskDecomposerFacade:
    """
    任务分解器门面
    
    为所有任务分解器提供统一接口。
    内部根据类型路由到具体实现。
    
    Usage:
        facade = TaskDecomposerFacade()
        
        # 自动选择分解器
        result = facade.decompose("帮我分析这段代码")
        
        # 指定分解器类型
        result = facade.decompose(
            "优化系统性能",
            decomposer_type=DecomposerType.SMART
        )
        
        # 执行步骤
        facade.execute_step(result, "step_1")
    """
    
    def __init__(self):
        self._decomposers: Dict[str, BaseTaskDecomposer] = {}
        logger.info("[TaskDecomposerFacade] 初始化完成")
    
    def decompose(
        self,
        task: str,
        decomposer_type: Optional[DecomposerType] = None,
        **kwargs,
    ) -> DecomposedTask:
        """
        分解任务（自动选择或指定分解器）
        
        Args:
            task: 任务描述
            decomposer_type: 分解器类型（None 则自动选择）
            **kwargs: 传递给分解器的参数
            
        Returns:
            分解后的任务
        """
        if decomposer_type is None:
            decomposer_type = auto_select_decomposer(task)
            logger.info(f"[TaskDecomposerFacade] 自动选择分解器: {decomposer_type.value}")
        
        decomposer = self._get_decomposer(decomposer_type)
        return decomposer.decompose(task, **kwargs)
    
    def execute_step(
        self,
        task: DecomposedTask,
        step_id: str,
        decomposer_type: Optional[DecomposerType] = None,
        **kwargs,
    ) -> Any:
        """
        执行步骤
        
        Args:
            task: 分解后的任务
            step_id: 步骤 ID
            decomposer_type: 分解器类型（None 则使用默认）
            **kwargs: 执行参数
            
        Returns:
            执行结果
        """
        if decomposer_type is None:
            decomposer_type = DecomposerType.BASIC
        
        decomposer = self._get_decomposer(decomposer_type)
        return decomposer.execute_step(task, step_id, **kwargs)
    
    def refine(
        self,
        task: DecomposedTask,
        feedback: str,
        decomposer_type: Optional[DecomposerType] = None,
        **kwargs,
    ) -> DecomposedTask:
        """
        根据反馈优化分解
        
        Args:
            task: 分解后的任务
            feedback: 用户反馈
            decomposer_type: 分解器类型（None 则使用默认）
            **kwargs: 优化参数
            
        Returns:
            优化后的任务
        """
        if decomposer_type is None:
            decomposer_type = DecomposerType.BASIC
        
        decomposer = self._get_decomposer(decomposer_type)
        return decomposer.refine(task, feedback, **kwargs)
    
    def _get_decomposer(self, decomposer_type: DecomposerType) -> BaseTaskDecomposer:
        """获取分解器实例（单例）"""
        if decomposer_type not in self._decomposers:
            self._decomposers[decomposer_type] = create_decomposer(decomposer_type)
            logger.info(f"[TaskDecomposerFacade] 创建分解器: {decomposer_type.value}")
        
        return self._decomposers[decomposer_type]
    
    def list_decomposers(self) -> List[str]:
        """列出所有已创建的分解器"""
        return [t.value for t in self._decomposers.keys()]
    
    def clear(self):
        """清空所有分解器实例"""
        self._decomposers.clear()
        logger.info("[TaskDecomposerFacade] 已清空所有分解器")


# ============================================================
# 便捷函数
# ============================================================

_default_facade: Optional[TaskDecomposerFacade] = None


def get_task_decomposer_facade() -> TaskDecomposerFacade:
    """获取默认门面实例（单例）"""
    global _default_facade
    if _default_facade is None:
        _default_facade = TaskDecomposerFacade()
    return _default_facade


def decompose_task(task: str, **kwargs) -> DecomposedTask:
    """
    便捷函数：分解任务
    
    Args:
        task: 任务描述
        **kwargs: 传递给分解器的参数
        
    Returns:
        分解后的任务
    """
    facade = get_task_decomposer_facade()
    return facade.decompose(task, **kwargs)


def execute_step(task: DecomposedTask, step_id: str, **kwargs) -> Any:
    """
    便捷函数：执行步骤
    
    Args:
        task: 分解后的任务
        step_id: 步骤 ID
        **kwargs: 执行参数
        
    Returns:
        执行结果
    """
    facade = get_task_decomposer_facade()
    return facade.execute_step(task, step_id, **kwargs)


__all__ = [
    "TaskDecomposerFacade",
    "get_task_decomposer_facade",
    "decompose_task",
    "execute_step",
]
