"""
TimesFM-style Time Series Forecasting System - 时间预测系统
============================================================

参考 Google TimesFM (https://github.com/google-research/timesfm) 设计的时间序列预测模块。

核心功能：
- 时间序列数据加载与预处理
- 多种预测模型支持 (TimesFM/Prophet/ARIMA/轻量神经网络)
- 分位数预测与不确定性估计
- 预测结果可视化

典型工作流：
    数据输入 → 预处理 → 异常检测 → 模型预测 → 分位数输出 → 可视化
"""

from .data_loader import TimeSeriesData, DataLoader, DataFrequency
from .forecaster import Forecaster, ForecastResult, ForecastModel
from .timesfm_adapter import TimesFMAdapter, TimesFMConfig
from .visualizer import ForecastVisualizer, PlotType

__all__ = [
    # 数据加载
    "TimeSeriesData",
    "DataLoader",
    "DataFrequency",
    # 预测器
    "Forecaster",
    "ForecastResult",
    "ForecastModel",
    # TimesFM 适配器
    "TimesFMAdapter",
    "TimesFMConfig",
    # 可视化
    "ForecastVisualizer",
    "PlotType",
]

__version__ = "1.0.0"
