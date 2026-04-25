# Evolution Engine - 智能IDE自我进化系统

"""
从"执行工具"进化为"设计伙伴"的关键跨越
构建"感知-诊断-规划-执行"闭环自治系统
"""

from .evolution_engine import EvolutionEngine, create_evolution_engine

# 传感器
from .sensors.base import BaseSensor, SensorType, EvolutionSignal
from .sensors.performance_sensor import PerformanceSensor
from .sensors.architecture_smell_sensor import ArchitectureSmellSensor

# 聚合器
from .aggregator.signal_aggregator import SignalAggregator

__all__ = [
    # 主控制器
    'EvolutionEngine',
    'create_evolution_engine',
    
    # 传感器
    'BaseSensor',
    'SensorType',
    'EvolutionSignal',
    'PerformanceSensor',
    'ArchitectureSmellSensor',
    
    # 聚合器
    'SignalAggregator',
]
