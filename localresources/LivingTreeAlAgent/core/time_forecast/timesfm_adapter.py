"""
TimesFM Adapter - TimesFM 适配器
=================================

参考 Google TimesFM (https://github.com/google-research/timesfm) 设计的适配器。

功能：
- 尝试加载 TimesFM 预训练模型
- 如果 TimesFM 不可用，使用内置轻量替代方案
- 提供与 TimesFM 兼容的 API 接口
"""

import os
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple, Union
from enum import Enum

import numpy as np

# 日志配置
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TimesFMBackend(Enum):
    """TimesFM 后端类型"""
    PYTORCH = "pytorch"
    FLAX = "flax"
    INTERNAL = "internal"  # 内置轻量方案


@dataclass
class TimesFMConfig:
    """TimesFM 配置"""
    max_context: int = 512  # 最大上下文长度
    max_horizon: int = 128  # 最大预测范围
    normalize_inputs: bool = True  # 输入归一化
    use_quantile_head: bool = True  # 使用分位数预测头
    force_flip_invariance: bool = True  # 翻转不变性
    infer_is_positive: bool = True  # 正值推断
    backend: TimesFMBackend = TimesFMBackend.INTERNAL
    model_path: Optional[str] = None  # TimesFM 模型路径


class TimesFMAdapter:
    """
    TimesFM 适配器

    提供与 TimesFM 兼容的接口，自动选择最佳后端：
    1. TimesFM PyTorch (如果已安装)
    2. TimesFM Flax (如果已安装)
    3. 内置轻量方案 (默认)
    """

    def __init__(self, config: TimesFMConfig = None):
        self.config = config or TimesFMConfig()
        self._model = None
        self._backend = TimesFMBackend.INTERNAL
        self._is_available = False

        # 尝试加载 TimesFM
        self._try_load_timesfm()

    def _try_load_timesfm(self):
        """尝试加载 TimesFM"""
        try:
            # 尝试导入 timesfm
            import timesfm
            self._timesfm = timesfm
            self._is_available = True
            logger.info("TimesFM 库已加载")

            # 检测后端
            if self.config.backend == TimesFMBackend.PYTORCH:
                self._load_pytorch_backend()
            elif self.config.backend == TimesFMBackend.FLAX:
                self._load_flax_backend()
            else:
                # 默认使用 PyTorch
                self._load_pytorch_backend()

        except ImportError:
            logger.info("TimesFM 未安装，使用内置轻量方案")
            self._is_available = False
            self._backend = TimesFMBackend.INTERNAL

    def _load_pytorch_backend(self):
        """加载 PyTorch 后端"""
        try:
            import torch
            self._model = self._timesfm.TimesFM_2p5_200M_torch.from_pretrained(
                "google/timesfm-2.5-200m-pytorch"
            )
            self._backend = TimesFMBackend.PYTORCH
            logger.info("TimesFM PyTorch 后端已加载")
        except Exception as e:
            logger.warning(f"TimesFM PyTorch 后端加载失败: {e}")
            self._backend = TimesFMBackend.INTERNAL

    def _load_flax_backend(self):
        """加载 Flax 后端"""
        try:
            import jax
            self._model = self._timesfm.TimesFM_2p5_200M_flax.from_pretrained(
                "google/timesfm-2.5-200m-flax"
            )
            self._backend = TimesFMBackend.FLAX
            logger.info("TimesFM Flax 后端已加载")
        except Exception as e:
            logger.warning(f"TimesFM Flax 后端加载失败: {e}")
            self._backend = TimesFMBackend.INTERNAL

    def compile(self, config: TimesFMConfig = None):
        """编译模型 (TimesFM 接口)"""
        if config:
            self.config = config

        if self._model and self._backend != TimesFMBackend.INTERNAL:
            try:
                forecast_config = self._timesfm.ForecastConfig(
                    max_context=self.config.max_context,
                    max_horizon=self.config.max_horizon,
                    normalize_inputs=self.config.normalize_inputs,
                    use_continuous_quantile_head=self.config.use_quantile_head,
                    force_flip_invariance=self.config.force_flip_invariance,
                    infer_is_positive=self.config.infer_is_positive,
                )
                self._model.compile(forecast_config)
                logger.info("TimesFM 模型已编译")
            except Exception as e:
                logger.warning(f"TimesFM 编译失败: {e}")

    def forecast(self, horizon: int,
                 inputs: Union[List[np.ndarray], np.ndarray],
                 **kwargs) -> Tuple[np.ndarray, np.ndarray]:
        """
        预测 (TimesFM 接口)

        Args:
            horizon: 预测范围
            inputs: 输入时间序列 (单个或多个)

        Returns:
            (point_forecast, quantile_forecast)
            - point_forecast: (batch_size, horizon)
            - quantile_forecast: (batch_size, horizon, 10) - 10个分位数
        """
        if self._backend == TimesFMBackend.INTERNAL:
            return self._internal_forecast(horizon, inputs)

        # TimesFM 预测
        try:
            result = self._model.forecast(
                horizon=horizon,
                inputs=inputs,
                **kwargs
            )

            if isinstance(result, tuple):
                point_forecast, quantile_forecast = result
            else:
                point_forecast = result
                quantile_forecast = None

            return point_forecast, quantile_forecast

        except Exception as e:
            logger.error(f"TimesFM 预测失败: {e}")
            return self._internal_forecast(horizon, inputs)

    def _internal_forecast(self, horizon: int,
                          inputs: Union[List[np.ndarray], np.ndarray]
                          ) -> Tuple[np.ndarray, np.ndarray]:
        """
        内置轻量预测方案

        当 TimesFM 不可用时使用。
        基于指数平滑和趋势外推的组合方法。
        """
        # 标准化输入
        if isinstance(inputs, list):
            inputs = np.array(inputs)
        if inputs.ndim == 1:
            inputs = inputs.reshape(1, -1)

        batch_size, context_len = inputs.shape

        # 预测结果
        point_forecasts = np.zeros((batch_size, horizon))
        quantile_forecasts = np.zeros((batch_size, horizon, 10))

        for i in range(batch_size):
            series = inputs[i]

            # 归一化
            mean = np.mean(series)
            std = np.std(series) if np.std(series) > 0 else 1.0
            normalized = (series - mean) / std

            # 计算趋势
            x = np.arange(context_len)
            slope, intercept = np.polyfit(x, normalized, 1)

            # 指数平滑权重
            alpha = 0.3
            smoothed = alpha * normalized[-1] + (1 - alpha) * (
                slope * (context_len - 1) + intercept
            )

            # 生成预测
            future_x = np.arange(context_len, context_len + horizon)
            trend_component = slope * future_x + intercept
            mean_reversion = np.full(horizon, mean / std)

            # 组合预测
            forecasts = 0.6 * trend_component + 0.3 * mean_reversion + 0.1 * smoothed

            # 反归一化
            point_forecasts[i] = forecasts * std + mean

            # 分位数预测 (使用历史波动率)
            residuals = normalized - (slope * x + intercept)
            residual_std = np.std(residuals) if len(residuals) > 1 else 0.1

            # 生成分位数 (从低到高)
            quantiles = [0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]
            for j, q in enumerate(quantiles):
                # 使用标准差缩放
                z = np.sqrt(2) * self._erfinv(2 * q - 1)
                quantile_forecasts[i, :, j] = forecasts * std + mean + z * residual_std * std

        return point_forecasts, quantile_forecasts

    def _erfinv(self, x: float) -> float:
        """
        误差函数逆函数近似

        用于从分位数生成正态分布值
        """
        # 简化实现
        if x == 0:
            return 0
        if x == 1:
            return float('inf')
        if x == -1:
            return float('-inf')

        # 使用近似公式
        ln = np.log(1 - x * x)
        c0 = 2.81022636e-08
        c1 = 3.43273935e-07
        c2 = -3.38738787e-05
        c3 = 1.46822038e-03
        c4 = -2.18669463e-02
        c5 = 6.21323358e-01
        c6 = 1.86943821e+00

        if x >= 0:
            z = np.sqrt(-(ln + 1) + 0.5 * (ln + 2))
            return (((((c0 * z + c1) * z + c2) * z + c3) * z + c4) * z + c5) * z + c6
        else:
            z = np.sqrt(-(ln + 1) + 0.5 * (ln + 2))
            return -(((((c0 * z + c1) * z + c2) * z + c3) * z + c4) * z + c5) * z + c6

    @property
    def backend_name(self) -> str:
        """获取当前后端名称"""
        return self._backend.value

    @property
    def is_timesfm_available(self) -> bool:
        """TimesFM 是否可用"""
        return self._is_available

    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        return {
            "backend": self._backend.value,
            "is_timesfm_available": self._is_available,
            "max_context": self.config.max_context,
            "max_horizon": self.config.max_horizon,
            "use_quantile_head": self.config.use_quantile_head
        }


class TimeSeriesForecaster:
    """
    时间序列预测器 (高级接口)

    结合 TimesFM 和内置预测器，提供完整的预测流程。
    """

    def __init__(self, config: TimesFMConfig = None):
        self.config = config or TimesFMConfig()
        self.adapter = TimesFMAdapter(config)
        self._is_compiled = False

    def compile(self, config: TimesFMConfig = None):
        """编译模型"""
        if config:
            self.config = config
        self.adapter.config = self.config
        self.adapter.compile(self.config)
        self._is_compiled = True

    def predict(self, horizon: int,
               inputs: Union[List[np.ndarray], np.ndarray],
               return_quantiles: bool = True
               ) -> Dict[str, np.ndarray]:
        """
        预测

        Args:
            horizon: 预测范围
            inputs: 输入时间序列
            return_quantiles: 是否返回分位数

        Returns:
            {
                "point": 点预测,
                "lower_80": 80% 下界,
                "upper_80": 80% 上界,
                "lower_95": 95% 下界,
                "upper_95": 95% 上界,
                "median": 中位数预测
            }
        """
        if not self._is_compiled:
            self.compile()

        point_forecast, quantile_forecast = self.adapter.forecast(horizon, inputs)

        result = {"point": point_forecast}

        if quantile_forecast is not None and return_quantiles:
            # 假设 quantile_forecast 形状为 (batch, horizon, 10)
            # 分位数顺序: [0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]
            result["lower_80"] = quantile_forecast[..., 7]  # 80% 下界 (0.10)
            result["upper_80"] = quantile_forecast[..., 8]  # 80% 上界 (0.90)
            result["lower_95"] = quantile_forecast[..., 0]  # 95% 下界 (0.05)
            result["upper_95"] = quantile_forecast[..., 9]  # 95% 上界 (0.90)
            result["median"] = quantile_forecast[..., 6]   # 中位数 (0.50)

        return result

    def batch_predict(self, horizon: int,
                     data_dict: Dict[str, np.ndarray]
                     ) -> Dict[str, Dict[str, np.ndarray]]:
        """
        批量预测多个时间序列

        Args:
            horizon: 预测范围
            data_dict: {name: time_series} 字典

        Returns:
            {name: prediction_result} 字典
        """
        results = {}

        for name, series in data_dict.items():
            result = self.predict(horizon, series)
            results[name] = result

        return results


# 便捷函数
def create_timesfm_forecaster(backend: str = "auto",
                               max_context: int = 512,
                               max_horizon: int = 128) -> TimeSeriesForecaster:
    """
    创建 TimesFM 预测器

    Args:
        backend: 后端类型 (auto/pytorch/flax/internal)
        max_context: 最大上下文长度
        max_horizon: 最大预测范围
    """
    backend_map = {
        "auto": TimesFMBackend.PYTORCH,
        "pytorch": TimesFMBackend.PYTORCH,
        "flax": TimesFMBackend.FLAX,
        "internal": TimesFMBackend.INTERNAL,
    }

    config = TimesFMConfig(
        max_context=max_context,
        max_horizon=max_horizon,
        backend=backend_map.get(backend, TimesFMBackend.INTERNAL)
    )

    return TimeSeriesForecaster(config)
