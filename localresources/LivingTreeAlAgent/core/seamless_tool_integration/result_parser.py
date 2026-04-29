"""
Result Parser - 结果解析器

负责：
1. 解析AERMOD/CALPUFF输出文件
2. 提取浓度数据
3. 统计分析
4. 超标判定
5. 生成报告数据
"""

import os
import re
import json
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from pathlib import Path
import struct


class Pollutant(Enum):
    """污染物枚举"""
    SO2 = "SO2"
    NO2 = "NO2"
    NOx = "NOx"
    PM10 = "PM10"
    PM25 = "PM2.5"
    VOCs = "VOCs"
    CO = "CO"
    O3 = "O3"


@dataclass
class ConcentrationData:
    """
    浓度数据点

    表示一个受体点位的浓度计算结果
    """
    # 位置
    x: float = 0.0          # X坐标 (m)
    y: float = 0.0          # Y坐标 (m)
    latitude: float = 0.0  # 纬度
    longitude: float = 0.0 # 经度

    # 浓度值 (μg/m³)
    concentration: float = 0.0

    # 统计量
    average: float = 0.0
    max: float = 0.0
    min: float = 0.0

    # 出现时间
    max_time: Optional[str] = None


@dataclass
class MaxResult:
    """
    最大值结果

    包含各评价指标的最大浓度值
    """
    # 污染物
    pollutant: str = ""

    # 最大值类型
    max_type: str = ""  # MAX, AVE_1H, AVE_8H, AVE_24H, ANNUAL

    # 最大浓度值 (μg/m³)
    value: float = 0.0

    # 出现位置
    x: float = 0.0
    y: float = 0.0

    # 出现时间
    occurrence_time: Optional[str] = None

    # 超标倍数
    exceedance_ratio: float = 0.0

    # 是否超标
    is_exceedance: bool = False


@dataclass
class PredictionResult:
    """
    预测结果 - 完整的结果封装

    包含所有预测数据和分析结果
    """
    # 基本信息
    project_name: str = ""
    tool_type: str = ""       # aermod, calpuff, etc.
    prediction_date: datetime = field(default_factory=datetime.now)

    # 数据源
    source_files: List[str] = field(default_factory=list)

    # 浓度数据网格
    concentration_grid: List[ConcentrationData] = field(default_factory=list)

    # 最大值结果
    max_results: List[MaxResult] = field(default_factory=list)

    # 统计摘要
    statistics: Dict[str, Any] = field(default_factory=dict)

    # 原始输出文本
    raw_output: str = ""

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def max_concentration(self) -> float:
        """获取所有数据中的最大浓度"""
        if not self.concentration_grid:
            return 0.0
        return max(c.concentration for c in self.concentration_grid)

    @property
    def exceedance_count(self) -> int:
        """超标点位数量"""
        return sum(1 for r in self.max_results if r.is_exceedance)

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "project_name": self.project_name,
            "tool_type": self.tool_type,
            "prediction_date": self.prediction_date.isoformat(),
            "max_concentration": self.max_concentration,
            "exceedance_count": self.exceedance_count,
            "statistics": self.statistics,
            "max_results": [
                {
                    "pollutant": r.pollutant,
                    "max_type": r.max_type,
                    "value": r.value,
                    "x": r.x,
                    "y": r.y,
                    "is_exceedance": r.is_exceedance
                }
                for r in self.max_results
            ]
        }


class BaseResultParser:
    """结果解析器基类"""

    # 标准浓度限值 (μg/m³)
    STANDARD_LIMITS = {
        "SO2": {
            "1H": 500,      # 1小时平均
            "3H": 800,      # 3小时平均
            "24H": 150,     # 24小时平均
            "ANNUAL": 60    # 年平均
        },
        "NO2": {
            "1H": 200,      # 1小时平均
            "24H": 80,      # 24小时平均
            "ANNUAL": 40    # 年平均
        },
        "PM10": {
            "24H": 150,     # 24小时平均
            "ANNUAL": 70    # 年平均
        },
        "PM25": {
            "24H": 75,      # 24小时平均
            "ANNUAL": 35    # 年平均
        },
        "CO": {
            "1H": 10000,    # 1小时平均 (10mg/m³)
            "24H": 4000     # 24小时平均 (4mg/m³)
        },
        "O3": {
            "1H": 200,      # 1小时平均
            "8H": 160       # 8小时平均
        }
    }

    def __init__(self):
        self.raw_content = ""

    def parse(self, file_path: str) -> PredictionResult:
        """解析结果文件"""
        raise NotImplementedError

    def check_exceedance(self, value: float, pollutant: str, avg_type: str) -> Tuple[bool, float]:
        """
        检查是否超标

        Returns:
            (是否超标, 超标倍数)
        """
        limits = self.STANDARD_LIMITS.get(pollutant, {})
        limit = limits.get(avg_type, float('inf'))

        if limit == float('inf'):
            return False, 0.0

        exceedance = value > limit
        ratio = value / limit if exceedance else 0.0

        return exceedance, ratio


class AermodResultParser(BaseResultParser):
    """
    AERMOD结果解析器

    解析AERMOD输出文件，提取：
    - 最大浓度值
    - 各受体点浓度
    - 日均、小时均浓度
    """

    # AERMOD输出文件中的关键字
    MAX_PATTERN = re.compile(r'MAX\s+(\d+\.?\d*)\s+(\w+)\s+AT\s+\(?([-\d.]+),\s*([-\d.]+)\)')
    VALUE_PATTERN = re.compile(r'^\s*([-\d.]+)\s+([-\d.]+)\s+([\d.]+)\s*([YN]?)\s*$', re.MULTILINE)
    GRID_PATTERN = re.compile(r'GRID\s+(\d+)\s+(\d+)\s+([-\d.]+)\s+([-\d.]+)')

    def parse(self, file_path: str) -> PredictionResult:
        """
        解析AERMOD输出文件

        Args:
            file_path: 输出文件路径

        Returns:
            PredictionResult
        """
        result = PredictionResult()
        result.tool_type = "aermod"

        if not os.path.exists(file_path):
            result.metadata["error"] = f"文件不存在: {file_path}"
            return result

        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            self.raw_content = f.read()
            result.raw_output = self.raw_content

        # 提取最大浓度
        result.max_results = self._extract_max_values()

        # 提取网格数据
        result.concentration_grid = self._extract_grid_data()

        # 统计
        result.statistics = self._calculate_statistics(result.concentration_grid)

        return result

    def _extract_max_values(self) -> List[MaxResult]:
        """提取最大浓度值"""
        results = []

        for match in self.MAX_PATTERN.finditer(self.raw_content):
            value = float(match.group(1))
            avg_type = match.group(2)
            x = float(match.group(3))
            y = float(match.group(4))

            # 推断污染物（从上下文）
            pollutant = self._infer_pollutant(avg_type)

            # 检查超标
            exceedance, ratio = self.check_exceedance(value, pollutant, avg_type)

            results.append(MaxResult(
                pollutant=pollutant,
                max_type=avg_type,
                value=value,
                x=x,
                y=y,
                exceedance_ratio=ratio,
                is_exceedance=exceedance
            ))

        return results

    def _infer_pollutant(self, avg_type: str) -> str:
        """推断污染物类型"""
        # 通常AERMOD输出会按污染物分别处理
        # 这里根据上下文简单推断
        pollutant_map = {
            "SO2": "SO2",
            "NO2": "NO2",
            "PM10": "PM10",
            "PM25": "PM2.5",
        }

        # 查找最近的污染物标识
        for pollutant in pollutant_map:
            pattern = re.compile(rf'{pollutant}.*{avg_type}', re.IGNORECASE)
            if pattern.search(self.raw_content):
                return pollutant_map[pollutant]

        return "UNKNOWN"

    def _extract_grid_data(self) -> List[ConcentrationData]:
        """提取网格浓度数据"""
        data = []

        for match in self.VALUE_PATTERN.finditer(self.raw_content):
            x = float(match.group(1))
            y = float(match.group(2))
            concentration = float(match.group(3))

            data.append(ConcentrationData(
                x=x,
                y=y,
                concentration=concentration
            ))

        return data

    def _calculate_statistics(self, grid_data: List[ConcentrationData]) -> Dict[str, Any]:
        """计算统计信息"""
        if not grid_data:
            return {}

        concentrations = [d.concentration for d in grid_data]

        return {
            "total_points": len(grid_data),
            "mean": sum(concentrations) / len(concentrations),
            "max": max(concentrations),
            "min": min(concentrations),
            "std": self._standard_deviation(concentrations),
            "percentile_95": self._percentile(concentrations, 95),
            "percentile_99": self._percentile(concentrations, 99),
        }

    @staticmethod
    def _standard_deviation(values: List[float]) -> float:
        """计算标准差"""
        if not values:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5

    @staticmethod
    def _percentile(values: List[float], p: float) -> float:
        """计算百分位数"""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * p / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]


class CalpuffResultParser(BaseResultParser):
    """
    CALPUFF结果解析器

    解析CALPUFF的 .dat 和 .grb 文件
    """

    def parse(self, file_path: str) -> PredictionResult:
        """解析CALPUFF输出文件"""
        result = PredictionResult()
        result.tool_type = "calpuff"

        # CALPUFF输出格式更复杂，需要更多解析逻辑
        # 这里提供基本框架

        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                result.raw_output = f.read()

        return result


class ResultParser:
    """
    结果解析器工厂

    根据工具类型自动选择解析器

    使用示例：
    ```python
    parser = ResultParser.create("aermod")
    result = parser.parse("/path/to/output.out")
    print(f"最大浓度: {result.max_concentration}")
    ```
    """

    _parsers = {
        "aermod": AermodResultParser,
        "calpuff": CalpuffResultParser,
    }

    @classmethod
    def create(cls, tool_type: str) -> BaseResultParser:
        """创建解析器"""
        parser_class = cls._parsers.get(tool_type.lower())
        if not parser_class:
            raise ValueError(f"不支持的工具类型: {tool_type}")
        return parser_class()

    @classmethod
    def register(cls, tool_type: str, parser_class: type):
        """注册新的解析器"""
        cls._parsers[tool_type.lower()] = parser_class

    @classmethod
    def parse_auto(cls, file_path: str, tool_type: Optional[str] = None) -> PredictionResult:
        """
        自动解析

        如果tool_type未指定，会尝试根据文件内容推断

        Args:
            file_path: 结果文件路径
            tool_type: 工具类型

        Returns:
            PredictionResult
        """
        if tool_type is None:
            # 根据文件扩展名或内容推断
            if file_path.endswith('.out') or file_path.endswith('.lst'):
                tool_type = "aermod"
            elif file_path.endswith('.dat'):
                tool_type = "calpuff"
            else:
                tool_type = "aermod"  # 默认

        parser = cls.create(tool_type)
        return parser.parse(file_path)


class ReportGenerator:
    """
    报告生成器

    从预测结果生成分析报告
    """

    def __init__(self, result: PredictionResult):
        self.result = result

    def generate_text_report(self) -> str:
        """Generate text report"""
        lines = [
            "=" * 60,
            f"Air Quality Prediction Analysis Report",
            "=" * 60,
            "",
            f"Project: {self.result.project_name}",
            f"Tool: {self.result.tool_type.upper()}",
            f"Date: {self.result.prediction_date.strftime('%Y-%m-%d %H:%M')}",
            "",
            "-" * 60,
            "1. Prediction Summary",
            "-" * 60,
            "",
        ]

        # Max concentration results
        if self.result.max_results:
            lines.append("Max concentration by pollutant:")
            lines.append("")
            for max_r in self.result.max_results:
                exceed_str = f"EXCEEDANCE {max_r.exceedance_ratio:.2f}x" if max_r.is_exceedance else "OK"
                lines.append(
                    f"  {max_r.pollutant} ({max_r.max_type}): "
                    f"{max_r.value:.2f} ug/m3 - {exceed_str}"
                )
            lines.append("")

        # Statistics
        stats = self.result.statistics
        if stats:
            lines.append("Statistics:")
            lines.append(f"  Total points: {stats.get('total_points', 0)}")
            lines.append(f"  Mean: {stats.get('mean', 0):.2f} ug/m3")
            lines.append(f"  Max: {stats.get('max', 0):.2f} ug/m3")
            lines.append(f"  Min: {stats.get('min', 0):.2f} ug/m3")
            lines.append(f"  Std: {stats.get('std', 0):.2f}")
            lines.append("")

        # Exceedance analysis
        if self.result.exceedance_count > 0:
            lines.append("-" * 60)
            lines.append("WARNING: EXCEEDANCE DETECTED")
            lines.append("-" * 60)
            lines.append(f"Exceedance points: {self.result.exceedance_count}")
            lines.append("")
            lines.append("Recommendations:")
            lines.append("  1. Analyze cause and adjust emission parameters")
            lines.append("  2. Consider increasing protection distance")
            lines.append("  3. Evaluate need for stricter emission controls")
            lines.append("")
        else:
            lines.append("[OK] All monitoring points are within limits")
            lines.append("")

        lines.append("=" * 60)
        lines.append("Report generated: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

        return "\n".join(lines)

    def generate_json_report(self) -> Dict:
        """生成JSON格式报告"""
        return self.result.to_dict()


# 便捷函数
def parse_result(file_path: str, tool_type: Optional[str] = None) -> PredictionResult:
    """
    快速解析结果文件

    使用示例：
    ```python
    result = parse_result("/path/to/aermod.out", "aermod")
    print(f"最大浓度: {result.max_concentration}")
    ```
    """
    return ResultParser.parse_auto(file_path, tool_type)


def generate_report(result: PredictionResult, format: str = "text") -> str:
    """
    生成报告

    Args:
        result: 预测结果
        format: 报告格式 (text/json)

    Returns:
        报告内容
    """
    generator = ReportGenerator(result)

    if format == "json":
        return json.dumps(generator.generate_json_report(), ensure_ascii=False, indent=2)
    else:
        return generator.generate_text_report()
