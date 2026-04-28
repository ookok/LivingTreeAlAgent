"""
绿色 AI 模块

节能策略：
- 动态模型选择：简单任务用小型模型，复杂任务用大型模型
- 模型自动休眠：空闲一段时间后自动停止模型
- 结果缓存：相同问题直接返回缓存结果
- 批量处理：多个任务合并处理
"""

from .energy_aware_scheduler import EnergyAwareScheduler

__all__ = ["EnergyAwareScheduler"]