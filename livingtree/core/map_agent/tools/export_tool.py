"""
截图与导出工具 (Export Tool)

功能：将当前地图视口（View）渲染为高清图片。

关键参数：
- 分辨率（300dpi用于印刷）
- 图例
- 比例尺
- 指北针

自动化逻辑：Agent写完报告章节后，自动调用此工具，将生成的图片插入Word文档的对应位置。

支持的输出格式：
- PNG（默认）
- JPEG
- PDF
- SVG
"""
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import base64
from enum import Enum
from dataclasses import dataclass, field


class ExportFormat(Enum):
    """输出格式"""
    PNG = "png"
    JPEG = "jpeg"
    PDF = "pdf"
    SVG = "svg"


class DPILevel(Enum):
    """分辨率等级"""
    SCREEN = 96      # 屏幕显示
    PRINT = 150      # 一般印刷
    HIGH_QUALITY = 300  # 高质量印刷


@dataclass
class MapView:
    """地图视口"""
    center: Tuple[float, float]  # 中心点坐标
    zoom: int = 15  # 缩放级别
    width: int = 800  # 宽度（像素）
    height: int = 600  # 高度（像素）
    layers: List[str] = field(default_factory=list)  # 图层列表


@dataclass
class ExportOptions:
    """导出选项"""
    format: ExportFormat = ExportFormat.PNG
    dpi: DPILevel = DPILevel.PRINT
    include_legend: bool = True
    include_scale_bar: bool = True
    include_compass: bool = True
    include_title: bool = True
    title: str = ""
    legend_items: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ExportResult:
    """导出结果"""
    success: bool = True
    message: str = ""
    file_path: str = ""
    format: ExportFormat = ExportFormat.PNG
    dpi: DPILevel = DPILevel.PRINT
    width: int = 0
    height: int = 0


class ExportTool:
    """
    截图与导出工具
    
    核心能力：
    1. 将地图视口导出为图片
    2. 支持多种格式和分辨率
    3. 添加图例、比例尺、指北针
    4. 批量导出
    """
    
    def __init__(self):
        self.output_dir = "output/maps"
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
    
    def export_map(self, view: MapView, options: ExportOptions = None) -> ExportResult:
        """
        导出地图
        
        Args:
            view: 地图视口
            options: 导出选项
        
        Returns:
            ExportResult
        """
        if options is None:
            options = ExportOptions()
        
        try:
            filename = self._generate_filename(options.format)
            filepath = os.path.join(self.output_dir, filename)
            
            self._render_map(view, options, filepath)
            
            file_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
            
            return ExportResult(
                success=True,
                message=f"地图导出成功，文件大小: {self._format_file_size(file_size)}",
                file_path=filepath,
                format=options.format,
                dpi=options.dpi,
                width=view.width,
                height=view.height
            )
        
        except Exception as e:
            return ExportResult(
                success=False,
                message=f"导出失败: {str(e)}"
            )
    
    def batch_export(self, views: List[MapView], options: ExportOptions = None) -> List[ExportResult]:
        """批量导出多个地图"""
        results = []
        for i, view in enumerate(views):
            result = self.export_map(view, options)
            if result.success:
                result.message = f"地图{i+1}导出成功"
            results.append(result)
        
        return results
    
    def generate_report_images(self, project_data: Dict[str, Any]) -> List[ExportResult]:
        """为项目报告生成所有需要的地图图片"""
        results = []
        
        # 项目位置图
        location_view = MapView(
            center=project_data.get("location", (116.4074, 39.9042)),
            zoom=13,
            width=800,
            height=600,
            layers=["road", "building", "label"]
        )
        
        location_options = ExportOptions(
            title=f"{project_data.get('name', '项目')}位置图",
            legend_items=[
                {"color": "#FF0000", "label": "项目位置"},
                {"color": "#00FF00", "label": "道路"},
                {"color": "#0000FF", "label": "水体"}
            ]
        )
        
        results.append(self.export_map(location_view, location_options))
        
        # 环境影响范围图
        impact_view = MapView(
            center=project_data.get("location", (116.4074, 39.9042)),
            zoom=15,
            width=800,
            height=600,
            layers=["buffer", "sensitive_points"]
        )
        
        impact_options = ExportOptions(
            title=f"{project_data.get('name', '项目')}环境影响范围图",
            legend_items=[
                {"color": "#FF0000", "label": "项目边界"},
                {"color": "#FFFF00", "label": "卫生防护距离(300m)"},
                {"color": "#FF6B6B", "label": "敏感点"}
            ]
        )
        
        results.append(self.export_map(impact_view, impact_options))
        
        # 交通区位图
        traffic_view = MapView(
            center=project_data.get("location", (116.4074, 39.9042)),
            zoom=12,
            width=800,
            height=600,
            layers=["highway", "road", "railway"]
        )
        
        traffic_options = ExportOptions(
            title=f"{project_data.get('name', '项目')}交通区位图",
            legend_items=[
                {"color": "#FF6347", "label": "高速公路"},
                {"color": "#4169E1", "label": "国道"},
                {"color": "#32CD32", "label": "省道"}
            ]
        )
        
        results.append(self.export_map(traffic_view, traffic_options))
        
        return results
    
    def _generate_filename(self, format: ExportFormat) -> str:
        """生成文件名"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"map_{timestamp}.{format.value}"
    
    def _render_map(self, view: MapView, options: ExportOptions, filepath: str):
        """渲染地图（模拟实现）"""
        # 创建简单的PNG图片作为占位符
        png_data = self._create_placeholder_png(view.width, view.height)
        
        with open(filepath, 'wb') as f:
            f.write(png_data)
    
    def _create_placeholder_png(self, width: int, height: int) -> bytes:
        """创建简单的PNG占位图片"""
        # 使用最小的有效PNG图片
        min_png = (
            b'\x89PNG\r\n\x1a\n'
            b'\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
            b'\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n\x0a\x2d\xb4\x00\x00\x00\x00'
            b'IEND\xaeB`\x82'
        )
        return min_png
    
    def _format_file_size(self, size: int) -> str:
        """格式化文件大小"""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.2f} KB"
        else:
            return f"{size / (1024 * 1024):.2f} MB"
    
    def _get_timestamp(self) -> str:
        """获取时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()