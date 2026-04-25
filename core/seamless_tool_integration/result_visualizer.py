"""
Result Visualizer - 结果可视化

负责：
1. 等值线图绘制
2. 数据表格展示
3. 超标分析图表
4. 导出Word/PDF报告
5. 地图叠加显示
"""

from core.logger import get_logger
logger = get_logger('seamless_tool_integration.result_visualizer')

import os
import io
from typing import Optional, Dict, List, Tuple, Any
from pathlib import Path
import json

# 尝试导入可视化库
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    from matplotlib import cm
    from matplotlib import colors as mcolors
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

try:
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem
    from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QPixmap, QImage
    HAS_PYQT = True
except ImportError:
    HAS_PYQT = False


class BaseVisualizer:
    """可视化器基类"""

    def __init__(self, result):
        self.result = result

    def create_figure(self):
        """创建图表"""
        raise NotImplementedError


class ContourMapVisualizer(BaseVisualizer):
    """
    等值线图可视化

    生成浓度分布等值线图

    使用示例：
    ```python
    visualizer = ContourMapVisualizer(result)
    image = visualizer.create_figure()
    # 保存或显示
    visualizer.save("contour.png", dpi=300)
    ```
    """

    # 污染物对应的颜色映射
    COLORMAPS = {
        "SO2": "YlOrRd",
        "NO2": "Oranges",
        "PM10": "Reds",
        "PM25": "hot_r",
        "VOCs": "Purples",
        "CO": "Greys",
        "O3": "Blues"
    }

    def __init__(self, result, pollutant: str = "SO2"):
        super().__init__(result)
        self.pollutant = pollutant
        self.colormap = self.COLORMAPS.get(pollutant, "YlOrRd")

    def create_figure(
        self,
        figsize: Tuple[int, int] = (12, 10),
        dpi: int = 100,
        show_grid: bool = True,
        show_colorbar: bool = True,
        title: Optional[str] = None
    ) -> Any:
        """
        创建等值线图

        Args:
            figsize: 图像尺寸 (宽, 高)
            dpi: 分辨率
            show_grid: 是否显示网格
            show_colorbar: 是否显示颜色条
            title: 图表标题

        Returns:
            matplotlib Figure对象
        """
        if not HAS_MATPLOTLIB:
            raise ImportError("需要安装 matplotlib: pip install matplotlib")

        if not HAS_NUMPY:
            raise ImportError("需要安装 numpy: pip install numpy")

        fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

        # 准备数据
        grid_data = self.result.concentration_grid
        if not grid_data:
            ax.text(0.5, 0.5, "无数据", ha='center', va='center', fontsize=16)
            return fig

        # 提取坐标和浓度
        x_coords = [d.x for d in grid_data]
        y_coords = [d.y for d in grid_data]
        concentrations = [d.concentration for d in grid_data]

        # 创建网格
        x_min, x_max = min(x_coords), max(x_coords)
        y_min, y_max = min(y_coords), max(y_coords)

        # 使用散点插值创建网格数据
        try:
            from scipy.interpolate import griddata
            xi = np.linspace(x_min, x_max, 100)
            yi = np.linspace(y_min, y_max, 100)
            Xi, Yi = np.meshgrid(xi, yi)

            Zi = griddata(
                (x_coords, y_coords),
                concentrations,
                (Xi, Yi),
                method='cubic'
            )

            # 绘制等值线填充
            levels = np.linspace(np.nanmin(Zi), np.nanmax(Zi), 20)
            cf = ax.contourf(Xi, Yi, Zi, levels=levels, cmap=self.colormap, alpha=0.8)

            # 绘制等值线
            cs = ax.contour(Xi, Yi, Zi, levels=levels, colors='black', linewidths=0.5, alpha=0.5)

        except Exception:
            # scipy不可用，使用简单的散点图
            scatter = ax.scatter(
                x_coords, y_coords,
                c=concentrations,
                cmap=self.colormap,
                s=50, alpha=0.8
            )

        # 设置轴标签
        ax.set_xlabel('X 坐标 (m)', fontsize=12)
        ax.set_ylabel('Y 坐标 (m)', fontsize=12)

        # 标题
        if title:
            ax.set_title(title, fontsize=14, fontweight='bold')
        else:
            ax.set_title(f'{self.pollutant} 浓度分布 (μg/m³)', fontsize=14, fontweight='bold')

        # 网格
        if show_grid:
            ax.grid(True, linestyle='--', alpha=0.5)

        # 颜色条
        if show_colorbar:
            cbar = plt.colorbar(cf if 'cf' in dir() else scatter, ax=ax, shrink=0.8)
            cbar.set_label('浓度 (μg/m³)', fontsize=11)

        # 标记最大值位置
        max_point = max(grid_data, key=lambda d: d.concentration)
        ax.plot(max_point.x, max_point.y, 'k*', markersize=15, label=f'最大值点 ({max_point.concentration:.1f})')
        ax.legend()

        plt.tight_layout()
        return fig

    def save(self, filepath: str, dpi: int = 300, **kwargs):
        """保存图像"""
        fig = self.create_figure(**kwargs)
        fig.savefig(filepath, dpi=dpi, bbox_inches='tight')
        plt.close(fig)

    def get_bytes(self, format: str = "png", dpi: int = 100) -> bytes:
        """获取图像字节数据"""
        fig = self.create_figure(dpi=dpi)
        buf = io.BytesIO()
        fig.savefig(buf, format=format, dpi=dpi, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return buf.read()


class DataTableVisualizer:
    """
    数据表格可视化

    生成结果数据表格

    使用示例：
    ```python
    visualizer = DataTableVisualizer(result)
    visualizer.show_table()  # 显示表格
    visualizer.export_csv("results.csv")  # 导出CSV
    ```
    """

    def __init__(self, result):
        self.result = result

    def create_table_widget(self) -> Optional['QTableWidget']:
        """创建Qt表格控件"""
        if not HAS_PYQT:
            raise ImportError("需要安装 PyQt6")

        table = QTableWidget()

        # 设置行列数
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(['X坐标(m)', 'Y坐标(m)', '浓度(μg/m³)', '经度', '纬度'])

        # 填充数据
        grid_data = self.result.concentration_grid
        table.setRowCount(len(grid_data))

        for i, data in enumerate(grid_data):
            table.setItem(i, 0, QTableWidgetItem(f"{data.x:.1f}"))
            table.setItem(i, 1, QTableWidgetItem(f"{data.y:.1f}"))
            table.setItem(i, 2, QTableWidgetItem(f"{data.concentration:.2f}"))
            table.setItem(i, 3, QTableWidgetItem(f"{data.longitude:.6f}" if data.longitude else "-"))
            table.setItem(i, 4, QTableWidgetItem(f"{data.latitude:.6f}" if data.latitude else "-"))

        # 自动调整列宽
        table.resizeColumnsToContents()

        return table

    def to_csv(self) -> str:
        """导出为CSV格式"""
        lines = ["X,Y,浓度(μg/m³),经度,纬度"]

        for data in self.result.concentration_grid:
            lines.append(
                f"{data.x:.1f},{data.y:.1f},{data.concentration:.2f},"
                f"{data.longitude:.6f if data.longitude else ''},"
                f"{data.latitude:.6f if data.latitude else ''}"
            )

        return "\n".join(lines)

    def export_csv(self, filepath: str):
        """导出CSV文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.to_csv())


class StatisticsVisualizer(BaseVisualizer):
    """
    统计分析可视化

    生成统计图表：
    - 直方图
    - 饼图
    - 箱线图
    """

    def create_figure(self, figsize: Tuple[int, int] = (14, 6)) -> Any:
        """创建统计图表"""
        if not HAS_MATPLOTLIB:
            raise ImportError("需要安装 matplotlib")

        fig, axes = plt.subplots(1, 3, figsize=figsize)

        grid_data = self.result.concentration_grid
        if not grid_data:
            for ax in axes:
                ax.text(0.5, 0.5, "无数据", ha='center', va='center')
            return fig

        concentrations = [d.concentration for d in grid_data]

        # 1. 浓度分布直方图
        ax1 = axes[0]
        ax1.hist(concentrations, bins=30, color='steelblue', alpha=0.7, edgecolor='black')
        ax1.axvline(np.mean(concentrations), color='red', linestyle='--', label=f'均值: {np.mean(concentrations):.2f}')
        ax1.set_xlabel('浓度 (μg/m³)')
        ax1.set_ylabel('频数')
        ax1.set_title('浓度分布直方图')
        ax1.legend()

        # 2. 箱线图
        ax2 = axes[1]
        bp = ax2.boxplot(concentrations, patch_artist=True)
        bp['boxes'][0].set_facecolor('lightblue')
        ax2.set_ylabel('浓度 (μg/m³)')
        ax2.set_title('浓度箱线图')

        # 标注统计值
        stats_text = f"均值: {np.mean(concentrations):.2f}\n中位数: {np.median(concentrations):.2f}\n最大值: {max(concentrations):.2f}"
        ax2.text(1.2, np.mean(concentrations), stats_text, fontsize=10, verticalalignment='center')

        # 3. 超标状态饼图
        ax3 = axes[2]
        exceedance_count = self.result.exceedance_count
        normal_count = len(grid_data) - exceedance_count

        if exceedance_count > 0:
            sizes = [normal_count, exceedance_count]
            labels = [f'达标\n{normal_count}点', f'超标\n{exceedance_count}点']
            colors = ['#4CAF50', '#F44336']
            explode = (0, 0.1)
        else:
            sizes = [len(grid_data)]
            labels = ['达标']
            colors = ['#4CAF50']
            explode = ()

        ax3.pie(sizes, explode=explode, labels=labels, colors=colors,
                autopct='%1.1f%%', shadow=True, startangle=90)
        ax3.set_title('达标/超标分布')

        plt.tight_layout()
        return fig


class MaxValueVisualizer(BaseVisualizer):
    """
    最大值可视化

    展示各污染物的最大浓度及其超标情况
    """

    def create_figure(self, figsize: Tuple[int, int] = (12, 6)) -> Any:
        """创建最大值对比图"""
        if not HAS_MATPLOTLIB:
            raise ImportError("需要安装 matplotlib")

        fig, ax = plt.subplots(figsize=figsize)

        max_results = self.result.max_results
        if not max_results:
            ax.text(0.5, 0.5, "无数据", ha='center', va='center')
            return fig

        # 准备数据
        labels = [f"{r.pollutant}\n({r.max_type})" for r in max_results]
        values = [r.value for r in max_results]

        # 颜色：超标红色，达标绿色
        colors = ['#F44336' if r.is_exceedance else '#4CAF50' for r in max_results]

        # 绘制条形图
        bars = ax.bar(labels, values, color=colors, alpha=0.8, edgecolor='black')

        # 在条形上标注数值
        for bar, result in zip(bars, max_results):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                    f'{result.value:.1f}',
                    ha='center', va='bottom', fontsize=10)

            if result.is_exceedance:
                ax.text(bar.get_x() + bar.get_width()/2., height/2,
                        f'超标{result.exceedance_ratio:.2f}倍',
                        ha='center', va='center', color='white', fontsize=9)

        ax.set_xlabel('污染物 (平均类型)')
        ax.set_ylabel('最大浓度 (μg/m³)')
        ax.set_title('各污染物最大浓度')
        ax.grid(axis='y', alpha=0.3)

        # 添加图例
        from matplotlib.patches import Patch

        legend_elements = [
            Patch(facecolor='#4CAF50', label='达标'),
            Patch(facecolor='#F44336', label='超标')
        ]
        ax.legend(handles=legend_elements, loc='upper right')

        plt.tight_layout()
        return fig


class ResultVisualizer:
    """
    结果可视化工厂

    提供统一的结果可视化接口

    使用示例：
    ```python
    viz = ResultVisualizer(result)

    # 获取各种图表
    contour_fig = viz.get_contour_map(pollutant="PM25")
    stats_fig = viz.get_statistics()
    max_fig = viz.get_max_values()

    # 导出报告
    viz.export_report("report.pdf")
    ```
    """

    def __init__(self, result):
        self.result = result

    def get_contour_map(
        self,
        pollutant: str = "SO2",
        figsize: Tuple[int, int] = (12, 10),
        dpi: int = 100
    ) -> Any:
        """获取等值线图"""
        visualizer = ContourMapVisualizer(self.result, pollutant)
        return visualizer.create_figure(figsize=figsize, dpi=dpi)

    def get_statistics(self, figsize: Tuple[int, int] = (14, 6)) -> Any:
        """获取统计图表"""
        visualizer = StatisticsVisualizer(self.result)
        return visualizer.create_figure(figsize=figsize)

    def get_max_values(self, figsize: Tuple[int, int] = (12, 6)) -> Any:
        """获取最大值图表"""
        visualizer = MaxValueVisualizer(self.result)
        return visualizer.create_figure(figsize=figsize)

    def get_table_widget(self):
        """获取数据表格"""
        visualizer = DataTableVisualizer(self.result)
        return visualizer.create_table_widget()

    def save_all(self, output_dir: str, dpi: int = 200):
        """
        保存所有图表

        Args:
            output_dir: 输出目录
            dpi: 分辨率
        """
        os.makedirs(output_dir, exist_ok=True)

        # 等值线图
        try:
            contour_viz = ContourMapVisualizer(self.result)
            contour_viz.save(
                os.path.join(output_dir, "contour_map.png"),
                dpi=dpi
            )
        except Exception as e:
            logger.info(f"等值线图保存失败: {e}")

        # 统计图
        try:
            stats_viz = StatisticsVisualizer(self.result)
            fig = stats_viz.create_figure()
            fig.savefig(os.path.join(output_dir, "statistics.png"), dpi=dpi, bbox_inches='tight')
        except Exception as e:
            logger.info(f"统计图保存失败: {e}")

        # 最大值图
        try:
            max_viz = MaxValueVisualizer(self.result)
            fig = max_viz.create_figure()
            fig.savefig(os.path.join(output_dir, "max_values.png"), dpi=dpi, bbox_inches='tight')
        except Exception as e:
            logger.info(f"最大值图保存失败: {e}")

        # CSV数据
        try:
            table_viz = DataTableVisualizer(self.result)
            table_viz.export_csv(os.path.join(output_dir, "concentration_data.csv"))
        except Exception as e:
            logger.info(f"CSV导出失败: {e}")

        # JSON报告
        try:
            report_path = os.path.join(output_dir, "report.json")
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(self.result.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.info(f"JSON报告保存失败: {e}")

    def get_summary_html(self) -> str:
        """
        生成HTML摘要

        用于在UI中嵌入显示
        """
        stats = self.result.statistics
        max_results = self.result.max_results

        html = f"""
        <div class="result-summary">
            <h3>预测结果摘要</h3>
            <table>
                <tr><th>指标</th><th>数值</th></tr>
                <tr><td>评价点数</td><td>{stats.get('total_points', 0)}</td></tr>
                <tr><td>平均浓度</td><td>{stats.get('mean', 0):.2f} μg/m³</td></tr>
                <tr><td>最大浓度</td><td>{stats.get('max', 0):.2f} μg/m³</td></tr>
                <tr><td>超标点数</td><td>{self.result.exceedance_count}</td></tr>
            </table>

            <h4>各污染物最大浓度</h4>
            <ul>
        """

        for r in max_results:
            status = "⚠️ 超标" if r.is_exceedance else "✓ 达标"
            html += f"<li>{r.pollutant} ({r.max_type}): {r.value:.2f} μg/m³ - {status}</li>"

        html += """
            </ul>
        </div>
        """
        return html


# 便捷函数
def quick_visualize(result, output_path: str, chart_type: str = "contour"):
    """
    快速可视化

    Args:
        result: PredictionResult
        output_path: 输出路径
        chart_type: 图表类型 (contour/stats/max)
    """
    viz = ResultVisualizer(result)

    if chart_type == "contour":
        viz.get_contour_map().savefig(output_path)
    elif chart_type == "stats":
        viz.get_statistics().savefig(output_path)
    elif chart_type == "max":
        viz.get_max_values().savefig(output_path)
