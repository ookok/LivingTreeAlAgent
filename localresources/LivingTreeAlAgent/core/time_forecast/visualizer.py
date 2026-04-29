"""
Forecast Visualizer - 预测结果可视化
====================================

支持多种可视化输出：
- Matplotlib 图表
- HTML 交互式图表
- ASCII 终端图表
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Union
from enum import Enum
from pathlib import Path

import numpy as np


class PlotType(Enum):
    """图表类型"""
    LINE = "line"           # 折线图
    AREA = "area"          # 面积图
    BAR = "bar"            # 柱状图
    SCATTER = "scatter"    # 散点图
    MULTI = "multi"        # 多序列图
    FORECAST = "forecast"  # 预测专用图


@dataclass
class PlotStyle:
    """图表样式"""
    title: str = "Time Series Forecast"
    xlabel: str = "Time"
    ylabel: str = "Value"
    figsize: tuple = (12, 6)
    dpi: int = 100
    grid: bool = True
    legend: bool = True
    color_original: str = "#2196F3"    # 蓝色 - 原始数据
    color_forecast: str = "#FF9800"     # 橙色 - 预测
    color_confidence: str = "#90CAF9"   # 浅蓝 - 置信区间
    color_upper: str = "#FFCC80"        # 浅橙 - 上界
    color_lower: str = "#BBDEFB"        # 浅蓝 - 下界
    line_width: float = 2.0
    alpha: float = 0.3  # 置信区间透明度


class ForecastVisualizer:
    """预测结果可视化器"""

    def __init__(self):
        self._matplotlib_available = True
        self._plotly_available = self._check_plotly()

    def _check_plotly(self):
        """检查 plotly 是否可用"""
        try:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
            self._plotly = __import__('plotly.graph_objects', fromlist=['go'])
            self._plotly.subplots = __import__('plotly.subplots', fromlist=['make_subplots'])
            return True
        except ImportError:
            return False

    def plot_to_matplotlib(self, data, forecast,
                          style: PlotStyle = None,
                          output_path: str = None) -> Any:
        """
        使用 Matplotlib 绘制预测图

        Args:
            data: 原始时间序列数据
            forecast: 预测结果
            style: 图表样式
            output_path: 输出路径

        Returns:
            matplotlib Figure 对象
        """
        if not self._matplotlib_available:
            try:
                import matplotlib
                matplotlib.use('Agg')  # 无头模式
                import matplotlib.pyplot as plt
                self._plt = plt
            except ImportError:
                raise ImportError("matplotlib 未安装，请运行: pip install matplotlib")
        else:
            import matplotlib.pyplot as plt
            self._plt = plt

        style = style or PlotStyle()

        fig, ax = self._plt.subplots(figsize=style.figsize, dpi=style.dpi)

        # 绘制原始数据
        if hasattr(data, 'values'):
            x_orig = range(len(data.values))
            y_orig = data.values
            timestamps = data.timestamps
        else:
            x_orig = range(len(data))
            y_orig = data
            timestamps = None

        ax.plot(x_orig, y_orig,
                color=style.color_original,
                linewidth=style.line_width,
                label='Original')

        # 绘制预测
        horizon = len(forecast.point_forecast)
        x_forecast = range(len(y_orig), len(y_orig) + horizon)
        ax.plot(x_forecast, forecast.point_forecast,
                color=style.color_forecast,
                linewidth=style.line_width,
                label='Forecast')

        # 绘制置信区间
        if hasattr(forecast, 'lower_bound') and hasattr(forecast, 'upper_bound'):
            ax.fill_between(x_forecast,
                           forecast.lower_bound,
                           forecast.upper_bound,
                           color=style.color_confidence,
                           alpha=style.alpha,
                           label='95% Confidence')

        # 设置标题和标签
        ax.set_title(style.title, fontsize=14, fontweight='bold')
        ax.set_xlabel(style.xlabel, fontsize=12)
        ax.set_ylabel(style.ylabel, fontsize=12)

        if style.grid:
            ax.grid(True, alpha=0.3)

        if style.legend:
            ax.legend(loc='best')

        self._plt.tight_layout()

        # 保存
        if output_path:
            fig.savefig(output_path, dpi=style.dpi, bbox_inches='tight')

        return fig

    def plot_to_plotly(self, data, forecast,
                       style: PlotStyle = None,
                       output_path: str = None) -> Any:
        """
        使用 Plotly 绘制交互式图表

        Args:
            data: 原始时间序列数据
            forecast: 预测结果
            style: 图表样式
            output_path: 输出路径

        Returns:
            plotly Figure 对象
        """
        if not self._plotly_available:
            raise ImportError("plotly 未安装，请运行: pip install plotly")

        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        style = style or PlotStyle()

        # 创建图形
        fig = make_subplots(specs=[[{"secondary_y": False}]])

        # 原始数据
        if hasattr(data, 'values'):
            y_orig = data.values
        else:
            y_orig = data

        fig.add_trace(go.Scatter(
            x=list(range(len(y_orig))),
            y=y_orig,
            mode='lines',
            name='Original',
            line=dict(color=style.color_original, width=style.line_width)
        ))

        # 预测数据
        horizon = len(forecast.point_forecast)
        x_forecast = list(range(len(y_orig), len(y_orig) + horizon))

        fig.add_trace(go.Scatter(
            x=x_forecast,
            y=forecast.point_forecast,
            mode='lines',
            name='Forecast',
            line=dict(color=style.color_forecast, width=style.line_width)
        ))

        # 置信区间
        if hasattr(forecast, 'lower_bound') and hasattr(forecast, 'upper_bound'):
            fig.add_trace(go.Scatter(
                x=x_forecast + x_forecast[::-1],
                y=list(forecast.upper_bound) + list(forecast.lower_bound)[::-1],
                fill='toself',
                fillcolor=style.color_confidence,
                line=dict(color='lightblue'),
                name='95% Confidence',
                opacity=style.alpha
            ))

        # 更新布局
        fig.update_layout(
            title=style.title,
            xaxis_title=style.xlabel,
            yaxis_title=style.ylabel,
            hovermode='x unified',
            showlegend=True,
            width=style.figsize[0] * 100,
            height=style.figsize[1] * 100
        )

        # 保存
        if output_path:
            if output_path.endswith('.html'):
                fig.write_html(output_path)
            else:
                fig.write_image(output_path)

        return fig

    def plot_to_ascii(self, data, forecast,
                     width: int = 80, height: int = 20) -> str:
        """
        生成 ASCII 图表 (用于终端)

        Args:
            data: 原始时间序列数据
            forecast: 预测结果
            width: 图表宽度
            height: 图表高度

        Returns:
            ASCII 图表字符串
        """
        # 合并数据
        if hasattr(data, 'values'):
            y_orig = np.array(data.values)
        else:
            y_orig = np.array(data)

        y_forecast = forecast.point_forecast

        # 合并并归一化到高度范围
        y_all = np.concatenate([y_orig, y_forecast])
        y_min, y_max = y_all.min(), y_all.max()

        if y_max == y_min:
            y_max = y_min + 1

        # 归一化
        y_norm = ((y_all - y_min) / (y_max - y_min) * (height - 1)).astype(int)

        # 构建 ASCII 图形
        lines = [[' ' for _ in range(width)] for _ in range(height)]

        # 计算列映射
        n_points = len(y_norm)
        if n_points > width:
            # 降采样
            step = n_points / width
            indices = [(int(i * step), i) for i in range(width)]
        else:
            indices = [(i, i * n_points // width) for i in range(n_points)]

        # 绘制数据点
        for col, idx in indices:
            if idx < len(y_norm):
                row = height - 1 - y_norm[idx]
                if 0 <= row < height:
                    lines[row][col] = '•'

        # 绘制预测部分 (用不同字符)
        orig_len = len(y_orig)
        for col, idx in indices:
            if idx >= orig_len:
                forecast_idx = idx - orig_len
                if forecast_idx < len(y_forecast):
                    # 反归一化预测点
                    y_val = y_forecast[forecast_idx]
                    row = height - 1 - int((y_val - y_min) / (y_max - y_min) * (height - 1))
                    if 0 <= row < height:
                        lines[row][col] = '◆'

        # 添加边框
        result_lines = []
        result_lines.append('┌' + '─' * (width - 2) + '┐')

        for line in lines:
            result_lines.append('│' + ''.join(line) + '│')

        result_lines.append('└' + '─' * (width - 2) + '┘')

        # 添加图例
        result_lines.append('')
        result_lines.append(f'  ●  Original (蓝色)    ◆  Forecast (橙色)')
        result_lines.append(f'  范围: {y_min:.2f} ~ {y_max:.2f}')
        result_lines.append(f'  原始数据点: {len(y_orig)}    预测点: {len(y_forecast)}')

        return '\n'.join(result_lines)

    def plot_forecast_comparison(self, data_list: List,
                                 forecast_list: List,
                                 labels: List[str] = None,
                                 style: PlotStyle = None) -> Any:
        """
        绘制多序列对比图

        Args:
            data_list: 原始数据列表
            forecast_list: 预测结果列表
            labels: 序列标签
            style: 图表样式

        Returns:
            图表对象
        """
        style = style or PlotStyle()

        if labels is None:
            labels = [f'Series {i+1}' for i in range(len(data_list))]

        if self._plotly_available:
            return self._plotly_comparison(data_list, forecast_list, labels, style)
        else:
            return self._matplotlib_comparison(data_list, forecast_list, labels, style)

    def _plotly_comparison(self, data_list, forecast_list, labels, style):
        """使用 Plotly 绘制对比图"""
        import plotly.graph_objects as go

        fig = go.Figure()

        colors = ['#2196F3', '#4CAF50', '#FF9800', '#E91E63', '#9C27B0']

        for i, (data, forecast) in enumerate(zip(data_list, forecast_list)):
            color = colors[i % len(colors)]

            # 原始数据
            if hasattr(data, 'values'):
                y_orig = data.values
            else:
                y_orig = data

            fig.add_trace(go.Scatter(
                x=list(range(len(y_orig))),
                y=y_orig,
                mode='lines',
                name=f'{labels[i]} - Original',
                line=dict(color=color, width=2)
            ))

            # 预测
            horizon = len(forecast.point_forecast)
            x_forecast = list(range(len(y_orig), len(y_orig) + horizon))

            fig.add_trace(go.Scatter(
                x=x_forecast,
                y=forecast.point_forecast,
                mode='lines',
                name=f'{labels[i]} - Forecast',
                line=dict(color=color, width=2, dash='dash')
            ))

        fig.update_layout(
            title='Forecast Comparison',
            xaxis_title='Time',
            yaxis_title='Value',
            hovermode='x unified',
            showlegend=True
        )

        return fig

    def _matplotlib_comparison(self, data_list, forecast_list, labels, style):
        """使用 Matplotlib 绘制对比图"""
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            raise ImportError("matplotlib 未安装")

        fig, ax = plt.subplots(figsize=style.figsize)

        colors = ['#2196F3', '#4CAF50', '#FF9800', '#E91E63', '#9C27B0']

        for i, (data, forecast) in enumerate(zip(data_list, forecast_list)):
            color = colors[i % len(colors)]

            # 原始数据
            if hasattr(data, 'values'):
                y_orig = data.values
            else:
                y_orig = data

            ax.plot(y_orig, color=color, linewidth=2, label=f'{labels[i]} - Original')

            # 预测
            horizon = len(forecast.point_forecast)
            x_forecast = range(len(y_orig), len(y_orig) + horizon)
            ax.plot(x_forecast, forecast.point_forecast,
                   color=color, linewidth=2, linestyle='--',
                   label=f'{labels[i]} - Forecast')

        ax.set_title('Forecast Comparison', fontsize=14, fontweight='bold')
        ax.set_xlabel('Time', fontsize=12)
        ax.set_ylabel('Value', fontsize=12)
        ax.grid(True, alpha=0.3)
        ax.legend(loc='best')

        plt.tight_layout()
        return fig


# 便捷函数
def quick_plot(data, forecast, format: str = "matplotlib",
              output_path: str = None) -> Any:
    """
    快速绘图

    Args:
        data: 时间序列数据
        forecast: 预测结果
        format: 输出格式 (matplotlib/plotly/ascii)
        output_path: 输出路径
    """
    visualizer = ForecastVisualizer()

    if format == "matplotlib":
        return visualizer.plot_to_matplotlib(data, forecast, output_path=output_path)
    elif format == "plotly":
        return visualizer.plot_to_plotly(data, forecast, output_path=output_path)
    elif format == "ascii":
        return visualizer.plot_to_ascii(data, forecast)
    else:
        raise ValueError(f"不支持的格式: {format}")
