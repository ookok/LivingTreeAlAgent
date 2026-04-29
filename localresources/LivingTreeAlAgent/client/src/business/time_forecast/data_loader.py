"""
Time Series Data Loader - 时间序列数据加载器
=============================================

支持多种数据源的时间序列加载：
- CSV/Excel 文件
- Pandas DataFrame
- NumPy 数组
- 实时数据流
"""

import re
import csv
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple, Union
from enum import Enum
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np


class DataFrequency(Enum):
    """数据频率"""
    MINUTE = "minute"           # 分钟级
    HOURLY = "hourly"           # 小时级
    DAILY = "daily"             # 日级
    WEEKLY = "weekly"            # 周级
    MONTHLY = "monthly"          # 月级
    QUARTERLY = "quarterly"      # 季度级
    YEARLY = "yearly"           # 年级
    IRREGULAR = "irregular"      # 不规则


@dataclass
class TimeSeriesPoint:
    """时间序列点"""
    timestamp: datetime
    value: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TimeSeriesData:
    """时间序列数据"""
    name: str = "unnamed"
    values: List[float] = field(default_factory=list)
    timestamps: List[datetime] = field(default_factory=list)
    frequency: DataFrequency = DataFrequency.DAILY
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if len(self.values) != len(self.timestamps):
            raise ValueError("values 和 timestamps 长度必须一致")

    @property
    def length(self) -> int:
        """数据点数量"""
        return len(self.values)

    @property
    def start_time(self) -> Optional[datetime]:
        """开始时间"""
        return self.timestamps[0] if self.timestamps else None

    @property
    def end_time(self) -> Optional[datetime]:
        """结束时间"""
        return self.timestamps[-1] if self.timestamps else None

    @property
    def value_array(self) -> np.ndarray:
        """值数组"""
        return np.array(self.values)

    @property
    def mean(self) -> float:
        """均值"""
        return float(np.mean(self.values)) if self.values else 0.0

    @property
    def std(self) -> float:
        """标准差"""
        return float(np.std(self.values)) if self.values else 0.0

    @property
    def min(self) -> float:
        """最小值"""
        return float(np.min(self.values)) if self.values else 0.0

    @property
    def max(self) -> float:
        """最大值"""
        return float(np.max(self.values)) if self.values else 0.0

    def to_numpy(self) -> Tuple[np.ndarray, np.ndarray]:
        """转换为 NumPy 数组"""
        return np.array(self.timestamps, dtype='datetime64'), self.value_array

    def get_segment(self, start_idx: int, end_idx: int) -> 'TimeSeriesData':
        """获取数据段"""
        return TimeSeriesData(
            name=self.name,
            values=self.values[start_idx:end_idx],
            timestamps=self.timestamps[start_idx:end_idx],
            frequency=self.frequency,
            metadata=self.metadata
        )

    def split(self, train_ratio: float = 0.8) -> Tuple['TimeSeriesData', 'TimeSeriesData']:
        """分割训练集和测试集"""
        split_idx = int(len(self.values) * train_ratio)
        train_data = self.get_segment(0, split_idx)
        test_data = self.get_segment(split_idx, len(self.values))
        return train_data, test_data

    def detect_anomalies(self, threshold: float = 3.0) -> List[int]:
        """
        基于标准差检测异常值

        Args:
            threshold: 标准差倍数阈值

        Returns:
            异常值索引列表
        """
        if len(self.values) < 3:
            return []

        values = self.value_array
        mean = np.mean(values)
        std = np.std(values)

        if std == 0:
            return []

        anomaly_indices = []
        for i, v in enumerate(values):
            z_score = abs((v - mean) / std)
            if z_score > threshold:
                anomaly_indices.append(i)

        return anomaly_indices

    def resample(self, target_frequency: DataFrequency) -> 'TimeSeriesData':
        """重采样到目标频率"""
        if self.frequency == target_frequency:
            return self

        # 简化实现：按目标频率聚合
        if len(self.values) == 0:
            return TimeSeriesData(name=self.name, frequency=target_frequency)

        values = self.value_array
        timestamps = self.timestamps

        # 计算每个目标频率区间的聚合值
        if target_frequency == DataFrequency.DAILY:
            # 按天聚合
            days = {}
            for i, (ts, v) in enumerate(zip(timestamps, values)):
                day_key = ts.date()
                if day_key not in days:
                    days[day_key] = []
                days[day_key].append(v)

            new_values = [np.mean(vlist) for vlist in days.values()]
            from datetime import datetime as dt
            new_timestamps = [dt.combine(k, dt.min.time()) for k in days.keys()]

        elif target_frequency == DataFrequency.MONTHLY:
            # 按月聚合
            months = {}
            for i, (ts, v) in enumerate(zip(timestamps, values)):
                month_key = (ts.year, ts.month)
                if month_key not in months:
                    months[month_key] = []
                months[month_key].append(v)

            from datetime import date
            new_values = [np.mean(vlist) for vlist in months.values()]
            new_timestamps = [date(y, m, 1) for (y, m) in months.keys()]

        else:
            # 其他频率暂不支持，返回原数据
            return self

        return TimeSeriesData(
            name=self.name,
            values=new_values,
            timestamps=new_timestamps,
            frequency=target_frequency,
            metadata=self.metadata
        )


class BaseDataLoader(ABC):
    """数据加载器基类"""

    @abstractmethod
    def load(self, source: Any) -> TimeSeriesData:
        """加载时间序列数据"""
        pass


class CSVLoader(BaseDataLoader):
    """CSV 文件加载器"""

    def __init__(self, time_col: str = "timestamp", value_col: str = "value",
                 date_format: str = "%Y-%m-%d"):
        self.time_col = time_col
        self.value_col = value_col
        self.date_format = date_format

    def load(self, source: Union[str, Path]) -> TimeSeriesData:
        """从 CSV 文件加载"""
        path = Path(source)

        timestamps = []
        values = []

        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    # 解析时间
                    ts_str = row.get(self.time_col, row.get('time', row.get('date', '')))
                    ts = self._parse_timestamp(ts_str)
                    if ts is None:
                        continue

                    # 解析值
                    val_str = row.get(self.value_col, row.get('value', row.get('y', '0')))
                    val = float(val_str)

                    timestamps.append(ts)
                    values.append(val)
                except (ValueError, KeyError):
                    continue

        if not timestamps:
            raise ValueError(f"CSV 文件中未找到有效数据: {path}")

        # 推断频率
        frequency = self._infer_frequency(timestamps)

        return TimeSeriesData(
            name=path.stem,
            values=values,
            timestamps=timestamps,
            frequency=frequency,
            metadata={"source": str(path)}
        )

    def _parse_timestamp(self, ts_str: str) -> Optional[datetime]:
        """解析时间戳"""
        ts_str = ts_str.strip()

        # 尝试多种格式
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%Y/%m/%d %H:%M:%S",
            "%d-%m-%Y",
            "%m/%d/%Y",
            "%Y-%m-%dT%H:%M:%S",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(ts_str, fmt)
            except ValueError:
                continue

        # 尝试解析为 Unix 时间戳
        try:
            ts_float = float(ts_str)
            if ts_float > 1e12:  # 毫秒级
                ts_float /= 1000
            return datetime.fromtimestamp(ts_float)
        except ValueError:
            pass

        return None

    def _infer_frequency(self, timestamps: List[datetime]) -> DataFrequency:
        """推断数据频率"""
        if len(timestamps) < 2:
            return DataFrequency.IRRUGULAR

        # 计算平均时间间隔
        intervals = []
        for i in range(1, len(timestamps)):
            delta = timestamps[i] - timestamps[i-1]
            intervals.append(delta.total_seconds())

        avg_interval = sum(intervals) / len(intervals)

        # 根据平均间隔判断频率
        minute_threshold = 120  # 2分钟
        hour_threshold = 45 * 60  # 45分钟
        day_threshold = 36 * 60 * 60  # 36小时
        week_threshold = 10 * 24 * 60 * 60  # 10天

        if avg_interval < minute_threshold:
            return DataFrequency.MINUTE
        elif avg_interval < hour_threshold:
            return DataFrequency.HOURLY
        elif avg_interval < day_threshold:
            return DataFrequency.DAILY
        elif avg_interval < week_threshold:
            return DataFrequency.WEEKLY
        else:
            return DataFrequency.MONTHLY


class NumpyLoader(BaseDataLoader):
    """NumPy 数组加载器"""

    def load(self, source: Tuple[np.ndarray, np.ndarray],
             name: str = "numpy_data") -> TimeSeriesData:
        """
        从 NumPy 数组加载

        Args:
            source: (values, timestamps) 元组
            name: 数据名称
        """
        values, timestamps = source

        if isinstance(timestamps, np.ndarray):
            # 尝试转换为 datetime 列表
            ts_list = []
            for ts in timestamps:
                if isinstance(ts, (int, float)):
                    ts_list.append(datetime.fromtimestamp(ts))
                elif isinstance(ts, np.datetime64):
                    ts_list.append(ts.astype('datetime64[ns]').astype(datetime))
                else:
                    ts_list.append(ts)
        else:
            ts_list = list(timestamps)

        return TimeSeriesData(
            name=name,
            values=list(values),
            timestamps=ts_list,
            frequency=DataFrequency.IRRUGULAR
        )


class DataFrameLoader(BaseDataLoader):
    """Pandas DataFrame 加载器 (可选)"""

    def __init__(self, time_col: str = "timestamp", value_col: str = "value"):
        self.time_col = time_col
        self.value_col = value_col
        self._pd = None

    def _try_import_pandas(self):
        """尝试导入 pandas"""
        if self._pd is None:
            try:
                import pandas as pd
                self._pd = pd
            except ImportError:
                raise ImportError("pandas 未安装，请运行: pip install pandas")
        return self._pd

    def load(self, source) -> TimeSeriesData:
        """从 DataFrame 加载"""
        pd = self._try_import_pandas()

        if not isinstance(source, pd.DataFrame):
            raise ValueError("source 必须是 pandas DataFrame")

        timestamps = []
        values = []

        for _, row in source.iterrows():
            ts = row[self.time_col]
            val = row[self.value_col]

            if pd.isna(val):
                continue

            if isinstance(ts, str):
                from .data_loader import CSVLoader
                ts = CSVLoader()._parse_timestamp(ts)

            timestamps.append(ts)
            values.append(float(val))

        return TimeSeriesData(
            name="dataframe",
            values=values,
            timestamps=timestamps,
            frequency=DataFrequency.IRRUGULAR
        )


class DataLoader:
    """时间序列数据加载器"""

    def __init__(self):
        self.loaders = {
            '.csv': CSVLoader(),
            '.txt': CSVLoader(),
        }
        self._numpy_loader = NumpyLoader()
        self._dataframe_loader = DataFrameLoader()

    def load(self, source: Any, name: str = None) -> TimeSeriesData:
        """
        加载时间序列数据

        Args:
            source: 文件路径 (str/Path) 或 NumPy 数组
            name: 数据名称
        """
        if isinstance(source, (str, Path)):
            path = Path(source)
            ext = path.suffix.lower()

            if ext in self.loaders:
                data = self.loaders[ext].load(path)
                if name:
                    data.name = name
                return data
            else:
                raise ValueError(f"不支持的文件格式: {ext}")

        elif isinstance(source, tuple):
            return self._numpy_loader.load(source, name or "numpy_data")

        elif hasattr(source, 'iloc'):  # Pandas DataFrame
            data = self._dataframe_loader.load(source)
            if name:
                data.name = name
            return data

        else:
            raise ValueError(f"不支持的数据源类型: {type(source)}")

    def supported_formats(self) -> List[str]:
        """支持的文件格式"""
        return list(self.loaders.keys())


# 便捷函数
def load_timeseries(file_path: str, time_col: str = "timestamp",
                   value_col: str = "value") -> TimeSeriesData:
    """快速加载时间序列"""
    loader = CSVLoader(time_col=time_col, value_col=value_col)
    return loader.load(file_path)
