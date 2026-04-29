"""
Forecaster - 预测引擎
=====================

支持多种预测模型：
- ARIMA (自回归积分滑动平均)
- Exponential Smoothing (指数平滑)
- Linear Regression (线性回归)
- Prophet (可选)
- Neural Network (轻量神经网络)
- TimesFM (通过适配器)
"""

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum

import numpy as np


class ForecastModel(Enum):
    """预测模型类型"""
    ARIMA = "arima"
    EXPONENTIAL_SMOOTHING = "exponential_smoothing"
    LINEAR = "linear"
    POLYNOMIAL = "polynomial"
    SIMPLE_MOVING_AVERAGE = "sma"
    EXPONENTIAL_MOVING_AVERAGE = "ema"
    PROPHET = "prophet"
    NEURAL_NETWORK = "neural_network"
    TIMESFM = "timesfm"


@dataclass
class QuantileForecast:
    """分位数预测结果"""
    quantile: float  # 分位数 (0-1)
    values: np.ndarray  # 预测值

    @property
    def shape(self) -> Tuple[int, ...]:
        return self.values.shape


@dataclass
class ForecastResult:
    """预测结果"""
    point_forecast: np.ndarray  # 点预测
    quantile_forecasts: List[QuantileForecast]  # 分位数预测
    model_name: str  # 模型名称
    horizon: int  # 预测范围
    timestamps: List  # 预测时间戳
    confidence: float = 0.95  # 置信度
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def lower_bound(self) -> np.ndarray:
        """获取下界 (使用 5th 分位数)"""
        for qf in self.quantile_forecasts:
            if abs(qf.quantile - 0.05) < 0.01:
                return qf.values
        # 默认使用点预测减去一个标准差
        std = np.std(self.point_forecast) * 0.5
        return self.point_forecast - std

    @property
    def upper_bound(self) -> np.ndarray:
        """获取上界 (使用 95th 分位数)"""
        for qf in self.quantile_forecasts:
            if abs(qf.quantile - 0.95) < 0.01:
                return qf.values
        # 默认使用点预测加上一个标准差
        std = np.std(self.point_forecast) * 0.5
        return self.point_forecast + std

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "point_forecast": self.point_forecast.tolist(),
            "quantile_forecasts": [
                {"quantile": qf.quantile, "values": qf.values.tolist()}
                for qf in self.quantile_forecasts
            ],
            "model_name": self.model_name,
            "horizon": self.horizon,
            "confidence": self.confidence
        }


class BaseForecaster(ABC):
    """预测器基类"""

    def __init__(self, model_type: ForecastModel):
        self.model_type = model_type
        self._is_fitted = False

    @abstractmethod
    def fit(self, values: np.ndarray, timestamps: List = None) -> 'BaseForecaster':
        """训练模型"""
        pass

    @abstractmethod
    def predict(self, horizon: int) -> ForecastResult:
        """预测"""
        pass

    def forecast(self, horizon: int) -> ForecastResult:
        """预测 (兼容接口)"""
        return self.predict(horizon)


class ARIMAForecaster(BaseForecaster):
    """ARIMA 预测器 (简化实现)"""

    def __init__(self, p: int = 5, d: int = 1, q: int = 2):
        super().__init__(ForecastModel.ARIMA)
        self.p = p  # AR 阶数
        self.d = d  # 差分阶数
        self.q = q  # MA 阶数
        self.coeffs = None
        self.residuals = None

    def fit(self, values: np.ndarray, timestamps: List = None) -> 'ARIMAForecaster':
        """训练 ARIMA 模型 (简化版)"""
        values = np.array(values, dtype=float)

        # 差分
        if self.d > 0:
            diff_values = np.diff(values, n=self.d)
        else:
            diff_values = values

        # 简化: 使用自回归系数估计
        n = len(diff_values)
        max_lag = min(self.p, n // 2)

        if max_lag < 1:
            self.coeffs = np.array([0.1])
            self.residuals = diff_values
            self._is_fitted = True
            return self

        # 构建自回归矩阵
        X = []
        y = []
        for i in range(max_lag, n):
            X.append(diff_values[i - max_lag:i])
            y.append(diff_values[i])

        X = np.array(X)
        y = np.array(y)

        # 最小二乘法估计
        try:
            self.coeffs = np.linalg.lstsq(X, y, rcond=None)[0]
        except:
            self.coeffs = np.ones(max_lag) * 0.1

        # 计算残差
        y_pred = X @ self.coeffs
        self.residuals = y - y_pred

        self._is_fitted = True
        return self

    def predict(self, horizon: int) -> ForecastResult:
        """预测未来 horizon 个时间步"""
        if not self._is_fitted:
            raise ValueError("模型未训练，请先调用 fit()")

        # 简化预测: 使用最后几个值和系数
        last_values = self.residuals[-self.p:] if len(self.residuals) >= self.p else self.residuals
        if len(last_values) == 0:
            last_values = np.array([np.mean(self.residuals)])

        forecasts = []
        current = last_values.copy()

        for _ in range(horizon):
            # 简化的 AR 预测
            if len(current) >= len(self.coeffs):
                pred = np.dot(current[-len(self.coeffs):], self.coeffs)
            else:
                pred = np.mean(current) * 0.5

            forecasts.append(pred)
            current = np.append(current[1:], pred)

        forecasts = np.array(forecasts)

        # 生成分位数 (简化)
        std = np.std(self.residuals) if len(self.residuals) > 0 else 1.0
        quantile_forecasts = [
            QuantileForecast(0.05, forecasts - 1.96 * std),
            QuantileForecast(0.25, forecasts - 0.67 * std),
            QuantileForecast(0.50, forecasts),
            QuantileForecast(0.75, forecasts + 0.67 * std),
            QuantileForecast(0.95, forecasts + 1.96 * std),
        ]

        # 生成时间戳
        timestamps = list(range(horizon))

        return ForecastResult(
            point_forecast=forecasts,
            quantile_forecasts=quantile_forecasts,
            model_name=f"ARIMA({self.p},{self.d},{self.q})",
            horizon=horizon,
            timestamps=timestamps,
            metadata={"p": self.p, "d": self.d, "q": self.q}
        )


class ExponentialSmoothingForecaster(BaseForecaster):
    """指数平滑预测器"""

    def __init__(self, alpha: float = 0.3):
        super().__init__(ForecastModel.EXPONENTIAL_SMOOTHING)
        self.alpha = alpha  # 平滑系数
        self.smoothed = None
        self.trend = None

    def fit(self, values: np.ndarray, timestamps: List = None) -> 'ExponentialSmoothingForecaster':
        """训练指数平滑模型"""
        values = np.array(values, dtype=float)

        # 简单指数平滑
        n = len(values)
        self.smoothed = np.zeros(n)
        self.smoothed[0] = values[0]

        for i in range(1, n):
            self.smoothed[i] = self.alpha * values[i] + (1 - self.alpha) * self.smoothed[i-1]

        self._is_fitted = True
        return self

    def predict(self, horizon: int) -> ForecastResult:
        """预测"""
        if not self._is_fitted:
            raise ValueError("模型未训练")

        # 使用最后一个平滑值作为预测
        last_value = self.smoothed[-1]

        # 简单预测: 假设未来值接近最后一个平滑值
        forecasts = np.full(horizon, last_value)

        # 计算标准差用于分位数
        residuals = self.smoothed - np.array(self.values[-len(self.smoothed):]) if hasattr(self, 'values') else np.std(self.smoothed)
        std = np.std(residuals) if len(residuals) > 1 else 1.0

        quantile_forecasts = [
            QuantileForecast(0.05, forecasts - 1.96 * std),
            QuantileForecast(0.25, forecasts - 0.67 * std),
            QuantileForecast(0.50, forecasts),
            QuantileForecast(0.75, forecasts + 0.67 * std),
            QuantileForecast(0.95, forecasts + 1.96 * std),
        ]

        return ForecastResult(
            point_forecast=forecasts,
            quantile_forecasts=quantile_forecasts,
            model_name=f"ExponentialSmoothing(alpha={self.alpha})",
            horizon=horizon,
            timestamps=list(range(horizon)),
            metadata={"alpha": self.alpha}
        )


class LinearForecaster(BaseForecaster):
    """线性回归预测器"""

    def __init__(self, degree: int = 1):
        super().__init__(ForecastModel.LINEAR if degree == 1 else ForecastModel.POLYNOMIAL)
        self.degree = degree
        self.coeffs = None

    def fit(self, values: np.ndarray, timestamps: List = None) -> 'LinearForecaster':
        """训练线性模型"""
        values = np.array(values, dtype=float)
        n = len(values)

        # 创建时间索引
        x = np.arange(n).reshape(-1, 1)

        # 创建多项式特征
        if self.degree > 1:
            from numpy.polynomial import polynomial as P
            self.coeffs = np.polyfit(np.arange(n), values, self.degree)
        else:
            # 简单线性回归
            x_mean = np.mean(x)
            y_mean = np.mean(values)

            numerator = np.sum((x.flatten() - x_mean) * (values - y_mean))
            denominator = np.sum((x.flatten() - x_mean) ** 2)

            if denominator == 0:
                slope = 0
            else:
                slope = numerator / denominator

            intercept = y_mean - slope * x_mean
            self.coeffs = np.array([slope, intercept])

        self.values = values
        self._is_fitted = True
        return self

    def predict(self, horizon: int) -> ForecastResult:
        """预测"""
        if not self._is_fitted:
            raise ValueError("模型未训练")

        n = len(self.values)
        future_x = np.arange(n, n + horizon)

        if self.degree > 1:
            forecasts = np.polyval(self.coeffs, future_x)
        else:
            slope, intercept = self.coeffs
            forecasts = slope * future_x + intercept

        # 计算残差
        if self.degree == 1:
            x = np.arange(n)
            fitted = self.coeffs[0] * x + self.coeffs[1]
        else:
            fitted = np.polyval(self.coeffs, np.arange(n))

        residuals = self.values - fitted
        std = np.std(residuals)

        quantile_forecasts = [
            QuantileForecast(0.05, forecasts - 1.96 * std),
            QuantileForecast(0.25, forecasts - 0.67 * std),
            QuantileForecast(0.50, forecasts),
            QuantileForecast(0.75, forecasts + 0.67 * std),
            QuantileForecast(0.95, forecasts + 1.96 * std),
        ]

        return ForecastResult(
            point_forecast=forecasts,
            quantile_forecasts=quantile_forecasts,
            model_name=f"Linear(degree={self.degree})",
            horizon=horizon,
            timestamps=list(future_x),
            metadata={"degree": self.degree}
        )


class MovingAverageForecaster(BaseForecaster):
    """移动平均预测器"""

    def __init__(self, window: int = 5):
        super().__init__(ForecastModel.SIMPLE_MOVING_AVERAGE)
        self.window = window

    def fit(self, values: np.ndarray, timestamps: List = None) -> 'MovingAverageForecaster':
        """训练移动平均模型"""
        self.values = np.array(values, dtype=float)
        self._is_fitted = True
        return self

    def predict(self, horizon: int) -> ForecastResult:
        """预测"""
        if not self._is_fitted:
            raise ValueError("模型未训练")

        # 使用最后 window 个值的平均
        last_values = self.values[-self.window:]
        mean = np.mean(last_values)
        std = np.std(last_values)

        forecasts = np.full(horizon, mean)

        quantile_forecasts = [
            QuantileForecast(0.05, forecasts - 1.96 * std),
            QuantileForecast(0.25, forecasts - 0.67 * std),
            QuantileForecast(0.50, forecasts),
            QuantileForecast(0.75, forecasts + 0.67 * std),
            QuantileForecast(0.95, forecasts + 1.96 * std),
        ]

        return ForecastResult(
            point_forecast=forecasts,
            quantile_forecasts=quantile_forecasts,
            model_name=f"SMA(window={self.window})",
            horizon=horizon,
            timestamps=list(range(horizon)),
            metadata={"window": self.window}
        )


class NeuralNetworkForecaster(BaseForecaster):
    """轻量神经网络预测器 (MLP)"""

    def __init__(self, hidden_size: int = 32, epochs: int = 100, learning_rate: float = 0.01):
        super().__init__(ForecastModel.NEURAL_NETWORK)
        self.hidden_size = hidden_size
        self.epochs = epochs
        self.learning_rate = learning_rate
        self.weights = None

    def fit(self, values: np.ndarray, timestamps: List = None) -> 'NeuralNetworkForecaster':
        """训练神经网络 (简化实现)"""
        values = np.array(values, dtype=float)

        # 归一化
        self.mean = np.mean(values)
        self.std = np.std(values) if np.std(values) > 0 else 1.0
        normalized = (values - self.mean) / self.std

        # 创建滞后特征
        lag = 5
        X, y = [], []
        for i in range(lag, len(normalized)):
            X.append(normalized[i-lag:i])
            y.append(normalized[i])

        X = np.array(X)
        y = np.array(y)

        # 简化的权重初始化
        input_size = lag
        self.weights = {
            'W1': np.random.randn(input_size, self.hidden_size) * 0.1,
            'b1': np.zeros(self.hidden_size),
            'W2': np.random.randn(self.hidden_size, 1) * 0.1,
            'b2': np.zeros(1)
        }

        # 简化的梯度下降训练
        for _ in range(self.epochs):
            # 前向传播
            hidden = np.tanh(X @ self.weights['W1'] + self.weights['b1'])
            output = hidden @ self.weights['W2'] + self.weights['b2']

            # 反向传播 (简化)
            error = y.reshape(-1, 1) - output
            # 权重更新 (非常简化)
            self.weights['W2'] += self.learning_rate * hidden.T @ error * 0.01
            self.weights['b2'] += self.learning_rate * np.mean(error) * 0.01

        self.train_std = np.std(error)
        self._is_fitted = True
        return self

    def predict(self, horizon: int) -> ForecastResult:
        """预测"""
        if not self._is_fitted:
            raise ValueError("模型未训练")

        # 使用最后 5 个值作为输入
        last_values = self.values[-5:]
        normalized = (last_values - self.mean) / self.std

        forecasts = []
        current = normalized.copy()

        for _ in range(horizon):
            # 前向传播
            hidden = np.tanh(current.reshape(1, -1) @ self.weights['W1'] + self.weights['b1'])
            pred = hidden @ self.weights['W2'] + self.weights['b2']

            # 反归一化
            pred = pred[0, 0] * self.std + self.mean
            forecasts.append(pred)

            # 更新输入
            current = np.append(current[1:], (pred - self.mean) / self.std)

        forecasts = np.array(forecasts)

        quantile_forecasts = [
            QuantileForecast(0.05, forecasts - 1.96 * self.train_std * self.std),
            QuantileForecast(0.25, forecasts - 0.67 * self.train_std * self.std),
            QuantileForecast(0.50, forecasts),
            QuantileForecast(0.75, forecasts + 0.67 * self.train_std * self.std),
            QuantileForecast(0.95, forecasts + 1.96 * self.train_std * self.std),
        ]

        return ForecastResult(
            point_forecast=forecasts,
            quantile_forecasts=quantile_forecasts,
            model_name=f"MLP(hidden={self.hidden_size})",
            horizon=horizon,
            timestamps=list(range(horizon)),
            metadata={"hidden_size": self.hidden_size, "epochs": self.epochs}
        )


class Forecaster:
    """预测器主类"""

    def __init__(self):
        self._models = {}

    def create_forecaster(self, model_type: ForecastModel, **kwargs) -> BaseForecaster:
        """创建预测器"""
        if model_type == ForecastModel.ARIMA:
            return ARIMAForecaster(
                p=kwargs.get('p', 5),
                d=kwargs.get('d', 1),
                q=kwargs.get('q', 2)
            )
        elif model_type == ForecastModel.EXPONENTIAL_SMOOTHING:
            return ExponentialSmoothingForecaster(alpha=kwargs.get('alpha', 0.3))
        elif model_type == ForecastModel.LINEAR:
            return LinearForecaster(degree=1)
        elif model_type == ForecastModel.POLYNOMIAL:
            return LinearForecaster(degree=kwargs.get('degree', 2))
        elif model_type == ForecastModel.SIMPLE_MOVING_AVERAGE:
            return MovingAverageForecaster(window=kwargs.get('window', 5))
        elif model_type == ForecastModel.EXPONENTIAL_MOVING_AVERAGE:
            return MovingAverageForecaster(window=kwargs.get('window', 5))  # 简化
        elif model_type == ForecastModel.NEURAL_NETWORK:
            return NeuralNetworkForecaster(
                hidden_size=kwargs.get('hidden_size', 32),
                epochs=kwargs.get('epochs', 100)
            )
        else:
            raise ValueError(f"不支持的模型类型: {model_type}")

    def forecast(self, data, horizon: int,
                model_type: ForecastModel = ForecastModel.LINEAR,
                **kwargs) -> ForecastResult:
        """
        一键预测

        Args:
            data: TimeSeriesData 或 np.ndarray
            horizon: 预测范围
            model_type: 模型类型
            **kwargs: 模型参数
        """
        from .data_loader import TimeSeriesData

        if isinstance(data, TimeSeriesData):
            values = data.value_array
            timestamps = data.timestamps
        else:
            values = np.array(data)
            timestamps = None

        # 创建并训练模型
        model = self.create_forecaster(model_type, **kwargs)
        model.fit(values, timestamps)

        # 预测
        return model.predict(horizon)

    def auto_forecast(self, data, horizon: int) -> ForecastResult:
        """
        自动选择最佳模型进行预测

        基于数据特征自动选择最适合的模型。
        """
        from .data_loader import TimeSeriesData

        if isinstance(data, TimeSeriesData):
            values = data.value_array
        else:
            values = np.array(data)

        n = len(values)

        # 数据长度判断
        if n < 10:
            # 数据太少，使用简单模型
            return self.forecast(data, horizon, ForecastModel.SIMPLE_MOVING_AVERAGE, window=3)

        # 计算数据特征
        variance = np.var(values)
        trend = np.polyfit(np.arange(n), values, 1)[0] if n > 2 else 0

        # 趋势判断
        if abs(trend) > variance * 0.1:
            # 有明显趋势，使用线性模型
            return self.forecast(data, horizon, ForecastModel.LINEAR)
        elif n > 50:
            # 数据量足够，使用神经网络
            return self.forecast(data, horizon, ForecastModel.NEURAL_NETWORK)
        else:
            # 默认使用指数平滑
            return self.forecast(data, horizon, ForecastModel.EXPONENTIAL_SMOOTHING)


# 便捷函数
def quick_forecast(data, horizon: int,
                  model: str = "auto") -> ForecastResult:
    """
    快速预测

    Args:
        data: 时间序列数据
        horizon: 预测范围
        model: 模型名称 (auto/linear/arima/ema/sma/nn)
    """
    model_map = {
        "auto": ForecastModel.LINEAR,
        "linear": ForecastModel.LINEAR,
        "arima": ForecastModel.ARIMA,
        "ema": ForecastModel.EXPONENTIAL_MOVING_AVERAGE,
        "sma": ForecastModel.SIMPLE_MOVING_AVERAGE,
        "nn": ForecastModel.NEURAL_NETWORK,
    }

    model_type = model_map.get(model.lower(), ForecastModel.LINEAR)
    forecaster = Forecaster()
    return forecaster.forecast(data, horizon, model_type)
