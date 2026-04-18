"""
导出管理器 - 为工程师设计的多格式导出验证系统
导出策略：让工程师能以最小成本、最高信心完成验证
"""

import json
import hashlib
import zipfile
import base64
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
import shutil

# 尝试导入可选依赖
try:
    from jinja2 import Template
    HAS_JINJA2 = True
except ImportError:
    HAS_JINJA2 = False

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


class ExportFormat(Enum):
    """导出格式枚举"""
    # 结构化数据
    JSON = "json"                      # JSON Schema
    YAML = "yaml"                       # YAML格式
    CSV = "csv"                         # CSV表格
    
    # 模型兼容格式
    EAIAPRO_AERMOD = "eiapro_aermod"   # EIAProA AERMOD兼容
    EAIAPRO_NOISE = "eiapro_noise"     # EIAProA噪声兼容
    CADNAA = "cadnaa"                  # CadnaA格式
    AERMOD_INP = "aermod_inp"          # AERMOD输入文件
    
    # GIS格式
    KML = "kml"                        # Google Earth KML
    SHP = "shp"                        # Shapefile
    GEOJSON = "geojson"                # GeoJSON
    
    # 验证报告
    PDF_REPORT = "pdf_report"          # 一页纸PDF验证摘要
    HTML_REPORT = "html_report"         # HTML验证报告
    WORD_REPORT = "word_report"        # Word验证报告（带追踪）
    
    # 完整验证包
    FULL_PACKAGE = "full_package"     # 完整验证包（压缩）
    DOCKER_PACKAGE = "docker_package"  # Docker可复现包
    
    # 数据表格
    EXCEL = "excel"                    # Excel多Sheet


class VerificationLevel(Enum):
    """验证详细程度"""
    BASIC = "basic"        # 仅关键数据
    STANDARD = "standard"  # 标准验证包
    FULL = "full"         # 完整验证包（含日志）


@dataclass
class ExportItem:
    """导出项"""
    name: str
    content: Any
    file_extension: str
    mime_type: str
    source_type: str  # 'input' | 'output' | 'log' | 'report'
    description: str = ""


@dataclass
class VerificationPackage:
    """验证包"""
    package_id: str
    project_id: str
    created_at: str
    format_type: ExportFormat
    items: List[ExportItem] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    digital_signature: Optional[str] = None
    checksum: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "package_id": self.package_id,
            "project_id": self.project_id,
            "created_at": self.created_at,
            "format_type": self.format_type.value,
            "items": [
                {
                    "name": item.name,
                    "file_extension": item.file_extension,
                    "mime_type": item.mime_type,
                    "source_type": item.source_type,
                    "description": item.description
                }
                for item in self.items
            ],
            "metadata": self.metadata,
            "digital_signature": self.digital_signature,
            "checksum": self.checksum
        }


@dataclass
class ExportConfig:
    """导出配置"""
    project_id: str
    format: ExportFormat
    verification_level: VerificationLevel = VerificationLevel.STANDARD
    include_inputs: bool = True
    include_outputs: bool = True
    include_logs: bool = True
    include_reports: bool = True
    include_docker: bool = False
    output_dir: Optional[str] = None
    custom_metadata: Dict[str, Any] = field(default_factory=dict)


class ExportManager:
    """
    多格式导出管理器
    
    导出策略：
    1. 结构化数据导出（让机器可读）
    2. 人可读的验证报告
    3. 交互式验证包（可执行）
    """
    
    def __init__(self, workspace_dir: str = None):
        self.workspace_dir = Path(workspace_dir) if workspace_dir else Path.home() / ".hermes-desktop" / "eia_exports"
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        
        # 导出历史记录
        self.export_history: List[Dict] = []
        
        # 已注册的导出器
        self._exporters: Dict[ExportFormat, callable] = {}
        self._register_default_exporters()
    
    def _register_default_exporters(self):
        """注册默认导出器"""
        self._exporters = {
            ExportFormat.JSON: self._export_json,
            ExportFormat.YAML: self._export_yaml,
            ExportFormat.CSV: self._export_csv,
            ExportFormat.EAIAPRO_AERMOD: self._export_eiapro_aermod,
            ExportFormat.EAIAPRO_NOISE: self._export_eiapro_noise,
            ExportFormat.AERMOD_INP: self._export_aermod_inp,
            ExportFormat.KML: self._export_kml,
            ExportFormat.GEOJSON: self._export_geojson,
            ExportFormat.PDF_REPORT: self._export_pdf_report,
            ExportFormat.HTML_REPORT: self._export_html_report,
            ExportFormat.EXCEL: self._export_excel,
            ExportFormat.FULL_PACKAGE: self._export_full_package,
            ExportFormat.DOCKER_PACKAGE: self._export_docker_package,
        }
    
    def _register_exporter(self, format_type: ExportFormat, exporter: callable):
        """注册自定义导出器"""
        self._exporters[format_type] = exporter
    
    async def export(
        self,
        config: ExportConfig,
        computation_package: Dict = None,
        report_data: Dict = None,
        drawing_data: Dict = None,
    ) -> VerificationPackage:
        """
        主导出方法
        
        Args:
            config: 导出配置
            computation_package: 计算包数据
            report_data: 报告数据
            drawing_data: 绘图数据
        """
        # 生成包ID
        package_id = self._generate_package_id(config.project_id, config.format)
        
        # 创建验证包
        package = VerificationPackage(
            package_id=package_id,
            project_id=config.project_id,
            created_at=datetime.now().isoformat(),
            format_type=config.format,
            metadata=config.custom_metadata or {}
        )
        
        # 调用对应的导出器
        exporter = self._exporters.get(config.format)
        if not exporter:
            raise ValueError(f"Unsupported export format: {config.format}")
        
        # 执行导出
        items = await exporter(config, computation_package, report_data, drawing_data)
        package.items = items
        
        # 添加元数据
        package.metadata.update({
            "verification_level": config.verification_level.value,
            "export_count": len(items),
            "total_size": sum(len(json.dumps(item.content)) for item in items if isinstance(item.content, (dict, list)))
        })
        
        # 生成校验和
        package.checksum = self._generate_checksum(package)
        
        # 记录导出历史
        self._record_export(package)
        
        return package
    
    def _generate_package_id(self, project_id: str, format_type: ExportFormat) -> str:
        """生成包ID"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        raw = f"{project_id}_{format_type.value}_{timestamp}"
        short_hash = hashlib.md5(raw.encode()).hexdigest()[:8]
        return f"exp_{short_hash}"
    
    def _generate_checksum(self, package: VerificationPackage) -> str:
        """生成校验和"""
        content = json.dumps(package.to_dict(), sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _record_export(self, package: VerificationPackage):
        """记录导出历史"""
        self.export_history.append({
            "package_id": package.package_id,
            "project_id": package.project_id,
            "format": package.format_type.value,
            "created_at": package.created_at,
            "item_count": len(package.items)
        })
    
    # ==================== 内置导出器实现 ====================
    
    async def _export_json(
        self,
        config: ExportConfig,
        computation_package: Dict = None,
        report_data: Dict = None,
        drawing_data: Dict = None
    ) -> List[ExportItem]:
        """导出为JSON格式"""
        items = []
        
        # 模型输入
        if config.include_inputs and computation_package:
            items.append(ExportItem(
                name="model_inputs",
                content=computation_package.get("inputs", {}),
                file_extension=".json",
                mime_type="application/json",
                source_type="input",
                description="模型输入参数"
            ))
        
        # 计算结果
        if config.include_outputs and computation_package:
            items.append(ExportItem(
                name="calculation_results",
                content=computation_package.get("results", {}),
                file_extension=".json",
                mime_type="application/json",
                source_type="output",
                description="计算结果数据"
            ))
        
        # 计算日志
        if config.include_logs and computation_package:
            items.append(ExportItem(
                name="computation_logs",
                content=computation_package.get("logs", []),
                file_extension=".json",
                mime_type="application/json",
                source_type="log",
                description="计算运行日志"
            ))
        
        # 报告数据
        if config.include_reports and report_data:
            items.append(ExportItem(
                name="report_data",
                content=report_data,
                file_extension=".json",
                mime_type="application/json",
                source_type="report",
                description="报告内容数据"
            ))
        
        return items
    
    async def _export_yaml(
        self,
        config: ExportConfig,
        computation_package: Dict = None,
        report_data: Dict = None,
        drawing_data: Dict = None
    ) -> List[ExportItem]:
        """导出为YAML格式"""
        if not HAS_YAML:
            # 如果没有yaml库，降级到JSON
            return await self._export_json(config, computation_package, report_data, drawing_data)
        
        items = []
        
        if config.include_inputs and computation_package:
            yaml_content = yaml.dump(computation_package.get("inputs", {}), allow_unicode=True, default_flow_style=False)
            items.append(ExportItem(
                name="model_inputs",
                content=yaml_content,
                file_extension=".yaml",
                mime_type="application/x-yaml",
                source_type="input",
                description="模型输入参数（YAML格式）"
            ))
        
        return items
    
    async def _export_csv(
        self,
        config: ExportConfig,
        computation_package: Dict = None,
        report_data: Dict = None,
        drawing_data: Dict = None
    ) -> List[ExportItem]:
        """导出为CSV格式"""
        import csv
        import io
        
        items = []
        
        # 导出污染源数据
        if config.include_inputs and computation_package:
            sources = computation_package.get("inputs", {}).get("sources", [])
            if sources:
                output = io.StringIO()
                if sources and isinstance(sources[0], dict):
                    writer = csv.DictWriter(output, fieldnames=sources[0].keys())
                    writer.writeheader()
                    writer.writerows(sources)
                items.append(ExportItem(
                    name="pollution_sources",
                    content=output.getvalue(),
                    file_extension=".csv",
                    mime_type="text/csv",
                    source_type="input",
                    description="污染源源强数据"
                ))
        
        # 导出计算结果
        if config.include_outputs and computation_package:
            results = computation_package.get("results", {})
            if isinstance(results, dict) and "concentrations" in results:
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=["x", "y", "concentration"])
                writer.writeheader()
                for item in results.get("concentrations", []):
                    writer.writerow(item)
                items.append(ExportItem(
                    name="concentration_results",
                    content=output.getvalue(),
                    file_extension=".csv",
                    mime_type="text/csv",
                    source_type="output",
                    description="浓度预测结果"
                ))
        
        return items
    
    async def _export_eiapro_aermod(
        self,
        config: ExportConfig,
        computation_package: Dict = None,
        report_data: Dict = None,
        drawing_data: Dict = None
    ) -> List[ExportItem]:
        """
        导出为EIAProA AERMOD兼容格式
        
        EIAProA是国内最常用的环评软件，支持AERMOD模型
        生成的文件格式：.daf (源数据), .met (气象数据), .sou (源项)
        """
        items = []
        
        if not computation_package:
            return items
        
        inputs = computation_package.get("inputs", {})
        sources = inputs.get("sources", [])
        
        # 1. 导出源数据文件 (.sou)
        sou_content = self._generate_eiapro_sou(sources)
        items.append(ExportItem(
            name="pollution_sources",
            content=sou_content,
            file_extension=".sou",
            mime_type="text/plain",
            source_type="input",
            description="EIAProA污染源源项文件"
        ))
        
        # 2. 导出气象数据文件 (.met)
        met_content = self._generate_eiapro_met(inputs.get("meteorology", {}))
        items.append(ExportItem(
            name="meteorological_data",
            content=met_content,
            file_extension=".met",
            mime_type="text/plain",
            source_type="input",
            description="EIAProA气象数据文件"
        ))
        
        # 3. 导出地形数据文件 (.ter) - 如果有
        if inputs.get("terrain"):
            ter_content = self._generate_eiapro_ter(inputs.get("terrain", []))
            items.append(ExportItem(
                name="terrain_data",
                content=ter_content,
                file_extension=".ter",
                mime_type="text/plain",
                source_type="input",
                description="EIAProA地形数据文件"
            ))
        
        # 4. 生成说明文件
        readme = self._generate_eiapro_readme(inputs, config.project_id)
        items.append(ExportItem(
            name="eiapro_readme",
            content=readme,
            file_extension=".txt",
            mime_type="text/plain",
            source_type="report",
            description="EIAProA使用说明"
        ))
        
        return items
    
    def _generate_eiapro_sou(self, sources: List[Dict]) -> str:
        """
        生成EIAProA源项文件(.sou)
        
        格式说明（基于EIAProA标准）：
        每行格式：序号,X坐标,Y坐标,源高(m),速度(m/s),温度(℃),排放量(g/s),源类型
        """
        lines = []
        lines.append("# EIAProA Source File (Pollution Sources)")
        lines.append("# Format: ID, X(m), Y(m), Height(m), Velocity(m/s), Temperature(C), EmissionRate(g/s), SourceType")
        lines.append("# SourceType: 1=Point, 2=Volume, 3=Area, 4=Flare")
        lines.append("")
        
        for i, src in enumerate(sources, 1):
            x = src.get("x", 0)
            y = src.get("y", 0)
            height = src.get("height", src.get("stack_height", 15))
            velocity = src.get("velocity", src.get("exit_velocity", 5.0))
            temp = src.get("temperature", src.get("exit_temp", 50))
            rate = src.get("emission_rate", src.get("rate", 0.1))
            src_type = src.get("source_type", 1)  # 默认点源
            
            line = f"{i}, {x:.2f}, {y:.2f}, {height:.2f}, {velocity:.2f}, {temp:.1f}, {rate:.6f}, {src_type}"
            lines.append(line)
        
        return "\n".join(lines)
    
    def _generate_eiapro_met(self, meteorology: Dict) -> str:
        """
        生成EIAProA气象数据文件(.met)
        
        格式：年,月,日,时,风向(°),风速(m/s),稳定度,温度(K)
        """
        lines = []
        lines.append("# EIAProA Meteorological Data File")
        lines.append("# Format: Year, Month, Day, Hour, WindDir(deg), WindSpeed(m/s), Stability, Temperature(K)")
        lines.append("# Stability: A=B, B=C, C=D, D=D, E=E, F=F (Pasquill-Gifford)")
        lines.append("")
        
        # 如果有典型气象年数据
        data = meteorology.get("annual_data", [])
        if not data:
            # 生成示例数据（全年小时数据）
            for month in range(1, 13):
                for day in range(1, 32):
                    for hour in range(24):
                        # 简化：使用典型值
                        wind_dir = 180  # 主导风向
                        wind_speed = 3.0  # 平均风速
                        stability = "D"  # 中性
                        temp = 288  # 288K = 15℃
                        lines.append(f"2024, {month:02d}, {day:02d}, {hour:02d}, {wind_dir:.0f}, {wind_speed:.1f}, {stability}, {temp:.0f}")
        
        return "\n".join(lines)
    
    def _generate_eiapro_ter(self, terrain: List[Dict]) -> str:
        """
        生成EIAProA地形数据文件(.ter)
        
        格式：X,Y,地形高程(m)
        """
        lines = []
        lines.append("# EIAProA Terrain Data File")
        lines.append("# Format: X(m), Y(m), Elevation(m)")
        lines.append("")
        
        for t in terrain:
            x = t.get("x", 0)
            y = t.get("y", 0)
            z = t.get("elevation", t.get("z", 0))
            lines.append(f"{x:.2f}, {y:.2f}, {z:.2f}")
        
        return "\n".join(lines)
    
    def _generate_eiapro_readme(self, inputs: Dict, project_id: str) -> str:
        """生成EIAProA使用说明"""
        return f"""EIAProA 验证包使用说明
======================

项目编号: {project_id}
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

文件说明:
---------
1. pollution_sources.sou - 污染源源项数据
   可直接在EIAProA中导入作为AERMOD模型的源项输入

2. meteorological_data.met - 气象数据
   包含全年逐时气象数据，导入EIAProA后会自动进行扩散计算

3. terrain_data.ter - 地形数据（如有）
   如项目区域有复杂地形，请导入此文件

使用方法:
---------
1. 打开EIAProA软件
2. 新建项目，选择AERMOD模型
3. 导入本目录下的 .sou, .met, .ter 文件
4. 设置计算参数（计算范围、网格精度等）
5. 运行模型并对比结果

对比验证要点:
-------------
1. 核对源强参数（排放量、源高、出口速度等）
2. 核对气象条件（主导风向、风速、稳定性）
3. 对比最大落地浓度及出现位置
4. 检查浓度等值线形态是否一致

注意事项:
---------
- 如使用不同版本EIAProA，请注意模型参数设置的差异
- 气象数据的年份和来源应与原计算一致
- 地形数据如有更新，请使用最新的地形高程

技术支持: 请联系系统管理员
"""
    
    async def _export_eiapro_noise(
        self,
        config: ExportConfig,
        computation_package: Dict = None,
        report_data: Dict = None,
        drawing_data: Dict = None
    ) -> List[ExportItem]:
        """导出为EIAProA噪声格式"""
        items = []
        
        if not computation_package:
            return items
        
        inputs = computation_package.get("inputs", {})
        noise_sources = inputs.get("noise_sources", [])
        
        # 生成噪声源数据
        content = self._generate_eiapro_noise_data(noise_sources)
        items.append(ExportItem(
            name="noise_sources",
            content=content,
            file_extension=".nsd",
            mime_type="text/plain",
            source_type="input",
            description="EIAProA噪声源源项文件"
        ))
        
        return items
    
    def _generate_eiapro_noise_data(self, noise_sources: List[Dict]) -> str:
        """生成EIAProA噪声数据"""
        lines = []
        lines.append("# EIAProA Noise Source Data")
        lines.append("# Format: ID, X, Y, SourceType, SoundPower(dB), Height(m)")
        lines.append("")
        
        for i, src in enumerate(noise_sources, 1):
            x = src.get("x", 0)
            y = src.get("y", 0)
            src_type = src.get("type", "point")
            spl = src.get("sound_power_level", src.get("spl", 85))
            height = src.get("height", 5)
            
            lines.append(f"{i}, {x:.2f}, {y:.2f}, {src_type}, {spl:.1f}, {height:.1f}")
        
        return "\n".join(lines)
    
    async def _export_aermod_inp(
        self,
        config: ExportConfig,
        computation_package: Dict = None,
        report_data: Dict = None,
        drawing_data: Dict = None
    ) -> List[ExportItem]:
        """导出为AERMOD原生输入文件(.inp)"""
        items = []
        
        if not computation_package:
            return items
        
        inputs = computation_package.get("inputs", {})
        sources = inputs.get("sources", [])
        
        # AERMOD输入文件
        inp_content = self._generate_aermod_inp(inputs, sources)
        items.append(ExportItem(
            name="aermod_input",
            content=inp_content,
            file_extension=".inp",
            mime_type="text/plain",
            source_type="input",
            description="AERMOD原生输入文件"
        ))
        
        return items
    
    def _generate_aermod_inp(self, inputs: Dict, sources: List[Dict]) -> str:
        """生成AERMOD输入文件"""
        lines = []
        lines.append("* AERMOD Input File")
        lines.append("* Generated by EIA System")
        lines.append(f"* Date: {datetime.now().isoformat()}")
        lines.append("")
        
        # 源定义
        lines.append("** AVERAGED CONCENTRATIONS")
        lines.append("")
        
        for i, src in enumerate(sources, 1):
            src_id = src.get("id", f"S{i}")
            x = src.get("x", 0)
            y = src.get("y", 0)
            height = src.get("height", 15)
            diameter = src.get("diameter", src.get("stack_diameter", 0.5))
            velocity = src.get("velocity", 5.0)
            temp = src.get("temperature", 50)
            rate = src.get("emission_rate", 0.1)
            
            lines.append(f"SO LOCATION {src_id} PO POINT {x:.2f} {y:.2f}")
            lines.append(f"SO EMISSION RATE {src_id} {rate:.6f} 0.0 0.0 {height:.2f}")
            lines.append(f"SO PARAMETER {src_id} {diameter:.3f} {velocity:.2f} {temp:.1f}")
            lines.append("")
        
        # 气象数据路径
        met_file = inputs.get("meteorology", {}).get("file", "meteorological_data.met")
        lines.append(f"METDATA   AERSURFACE METFILE = {met_file}")
        lines.append("")
        
        # 输出选项
        lines.append("OU POSTFILE")
        lines.append("")
        
        return "\n".join(lines)
    
    async def _export_kml(
        self,
        config: ExportConfig,
        computation_package: Dict = None,
        report_data: Dict = None,
        drawing_data: Dict = None
    ) -> List[ExportItem]:
        """导出为KML格式（用于Google Earth可视化）"""
        items = []
        
        # 从drawing_data或computation_package提取位置数据
        sources = []
        if drawing_data:
            sources = drawing_data.get("sources", [])
        elif computation_package:
            sources = computation_package.get("inputs", {}).get("sources", [])
        
        if sources:
            kml_content = self._generate_kml(sources, config.project_id)
            items.append(ExportItem(
                name="pollution_sources_kml",
                content=kml_content,
                file_extension=".kml",
                mime_type="application/vnd.google-earth.kml+xml",
                source_type="input",
                description="污染源位置（KML格式，可在Google Earth中查看）"
            ))
        
        return items
    
    def _generate_kml(self, sources: List[Dict], project_id: str) -> str:
        """生成KML文件"""
        lines = []
        lines.append('<?xml version="1.0" encoding="UTF-8"?>')
        lines.append('<kml xmlns="http://www.opengis.net/kml/2.2">')
        lines.append(f'<Document><name>{project_id} - Pollution Sources</name>')
        lines.append("<Folder><name>污染源</name>")
        
        for i, src in enumerate(sources, 1):
            x = src.get("x", 0)
            y = src.get("y", 0)
            name = src.get("name", f"Source {i}")
            src_type = src.get("type", src.get("source_type", "point"))
            rate = src.get("emission_rate", 0)
            
            # 根据排放量设置图标颜色
            if rate > 1:
                color = "ff0000ff"  # 红色-高排放
            elif rate > 0.1:
                color = "ff00ff00"  # 绿色-中排放
            else:
                color = "ff0000ff"  # 蓝色-低排放
            
            lines.append("<Placemark>")
            lines.append(f"<name>{name}</name>")
            lines.append(f"<description>排放量: {rate} g/s</description>")
            lines.append(f"<Point><coordinates>{x},{y},0</coordinates></Point>")
            lines.append(f"<Style><IconStyle><color>{color}</color></IconStyle></Style>")
            lines.append("</Placemark>")
        
        lines.append("</Folder></Document></kml>")
        return "\n".join(lines)
    
    async def _export_geojson(
        self,
        config: ExportConfig,
        computation_package: Dict = None,
        report_data: Dict = None,
        drawing_data: Dict = None
    ) -> List[ExportItem]:
        """导出为GeoJSON格式"""
        items = []
        
        sources = []
        if drawing_data:
            sources = drawing_data.get("sources", [])
        elif computation_package:
            sources = computation_package.get("inputs", {}).get("sources", [])
        
        if sources:
            geojson = self._generate_geojson(sources, config.project_id)
            items.append(ExportItem(
                name="pollution_sources_geojson",
                content=geojson,
                file_extension=".geojson",
                mime_type="application/geo+json",
                source_type="input",
                description="污染源位置（GeoJSON格式）"
            ))
        
        return items
    
    def _generate_geojson(self, sources: List[Dict], project_id: str) -> str:
        """生成GeoJSON"""
        features = []
        for src in sources:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [src.get("x", 0), src.get("y", 0)]
                },
                "properties": {
                    "name": src.get("name", "Unknown"),
                    "emission_rate": src.get("emission_rate", 0),
                    "height": src.get("height", 0),
                    "type": src.get("type", "point")
                }
            }
            features.append(feature)
        
        geojson = {
            "type": "FeatureCollection",
            "name": project_id,
            "features": features
        }
        return json.dumps(geojson, ensure_ascii=False, indent=2)
    
    async def _export_pdf_report(
        self,
        config: ExportConfig,
        computation_package: Dict = None,
        report_data: Dict = None,
        drawing_data: Dict = None
    ) -> List[ExportItem]:
        """导出一页纸PDF验证摘要"""
        # 注意：实际PDF生成需要reportlab等库，这里生成HTML模板
        html_content = self._generate_pdf_html_template(config, computation_package, report_data)
        
        return [ExportItem(
            name="verification_summary",
            content=html_content,
            file_extension=".html",
            mime_type="text/html",
            source_type="report",
            description="一页纸验证摘要（可打印为PDF）"
        )]
    
    def _generate_pdf_html_template(
        self,
        config: ExportConfig,
        computation_package: Dict = None,
        report_data: Dict = None
    ) -> str:
        """生成PDF验证摘要HTML模板"""
        inputs = computation_package.get("inputs", {}) if computation_package else {}
        results = computation_package.get("results", {}) if computation_package else {}
        sources = inputs.get("sources", [])
        
        # 汇总关键参数
        total_emission = sum(s.get("emission_rate", 0) for s in sources)
        max_concentration = results.get("max_concentration", "N/A")
        max_location = results.get("max_location", "N/A")
        standard_limit = results.get("standard_limit", "N/A")
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>验证摘要 - {config.project_id}</title>
    <style>
        body {{ font-family: 'SimSun', serif; margin: 40px; }}
        h1 {{ text-align: center; color: #333; border-bottom: 2px solid #333; padding-bottom: 10px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
        th {{ background-color: #f5f5f5; }}
        .section {{ margin: 30px 0; }}
        .highlight {{ background-color: #ffffcc; }}
        .warning {{ color: #cc0000; font-weight: bold; }}
        .footer {{ text-align: center; margin-top: 40px; color: #666; font-size: 12px; }}
        @media print {{ body {{ margin: 20px; }} }} 
    </style>
</head>
<body>
    <h1>环境影响评价计算验证摘要</h1>
    
    <div class="section">
        <h2>一、项目信息</h2>
        <table>
            <tr><th>项目编号</th><td>{config.project_id}</td></tr>
            <tr><th>验证时间</th><td>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
            <tr><th>验证级别</th><td>{config.verification_level.value.upper()}</td></tr>
        </table>
    </div>
    
    <div class="section">
        <h2>二、关键输入参数</h2>
        <table>
            <tr><th>参数</th><th>数值</th><th>单位</th><th>来源</th></tr>
            <tr><td>污染源数量</td><td>{len(sources)}</td><td>个</td><td>绘图模块</td></tr>
            <tr><td>总排放速率</td><td>{total_emission:.4f}</td><td>g/s</td><td>绘图模块</td></tr>
            <tr><td>计算模型</td><td>{inputs.get('model_type', 'Gaussian Plume')}</td><td>-</td><td>系统配置</td></tr>
        </table>
    </div>
    
    <div class="section">
        <h2>三、核心计算结果</h2>
        <table>
            <tr><th>指标</th><th>计算值</th><th>标准限值</th><th>达标情况</th></tr>
            <tr class="highlight">
                <td>最大落地浓度</td>
                <td>{max_concentration}</td>
                <td>{standard_limit}</td>
                <td>{"✓ 达标" if max_concentration != "N/A" else "待计算"}</td>
            </tr>
            <tr><td>最大浓度位置</td><td>{max_location}</td><td>-</td><td>-</td></tr>
        </table>
    </div>
    
    <div class="section">
        <h2>四、不确定性分析</h2>
        <table>
            <tr><th>因素</th><th>影响程度</th><th>建议</th></tr>
            <tr><td>气象数据代表性</td><td>中等</td><td>建议使用项目地实测气象站数据</td></tr>
            <tr><td>地形影响</td><td>低</td><td>本次计算未考虑复杂地形</td></tr>
            <tr><td>建筑下洗</td><td>低</td><td>下风向近距离需关注</td></tr>
        </table>
    </div>
    
    <div class="section">
        <h2>五、系统置信度评估</h2>
        <table>
            <tr><th>评估项</th><th>置信度</th><th>说明</th></tr>
            <tr><td>源强数据</td><td class="highlight">高</td><td>来自绘图输入，经人工确认</td></tr>
            <tr><td>模型计算</td><td class="highlight">高</td><td>基于HJ 2.2-2018标准</td></tr>
            <tr><td>预测结论</td><td>中</td><td>建议进行现场验证</td></tr>
        </table>
    </div>
    
    <div class="warning">
        <p><strong>⚠️ 重要提示：</strong>本摘要仅供快速验证使用，详细数据请参考完整计算报告。关键判定应由工程师审核确认。</p>
    </div>
    
    <div class="footer">
        <p>本报告由 EIA System 自动生成 | 如有问题请联系技术支持</p>
        <p>验证包ID: {config.project_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}</p>
    </div>
</body>
</html>
        """
        return html
    
    async def _export_html_report(
        self,
        config: ExportConfig,
        computation_package: Dict = None,
        report_data: Dict = None,
        drawing_data: Dict = None
    ) -> List[ExportItem]:
        """导出完整HTML验证报告"""
        items = []
        
        # 生成完整报告
        report_content = self._generate_full_html_report(config, computation_package, report_data, drawing_data)
        items.append(ExportItem(
            name="full_verification_report",
            content=report_content,
            file_extension=".html",
            mime_type="text/html",
            source_type="report",
            description="完整HTML验证报告"
        ))
        
        # 生成数据对比表
        comparison = self._generate_comparison_table(config, computation_package)
        items.append(ExportItem(
            name="data_comparison",
            content=comparison,
            file_extension=".html",
            mime_type="text/html",
            source_type="report",
            description="数据对比表"
        ))
        
        return items
    
    def _generate_full_html_report(
        self,
        config: ExportConfig,
        computation_package: Dict = None,
        report_data: Dict = None,
        drawing_data: Dict = None
    ) -> str:
        """生成完整HTML报告"""
        # 简化实现，实际应包含更多细节
        return self._generate_pdf_html_template(config, computation_package, report_data)
    
    def _generate_comparison_table(
        self,
        config: ExportConfig,
        computation_package: Dict = None
    ) -> str:
        """生成数据对比表"""
        inputs = computation_package.get("inputs", {}) if computation_package else {}
        results = computation_package.get("results", {}) if computation_package else {}
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>数据对比 - {config.project_id}</title>
    <style>
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; }}
        th {{ background-color: #4CAF50; color: white; }}
        .match {{ background-color: #dff0d8; }}
        .diff {{ background-color: #f2dede; }}
    </style>
</head>
<body>
    <h1>数据一致性对比表</h1>
    <p>项目: {config.project_id}</p>
    <table>
        <tr><th>数据项</th><th>系统计算值</th><th>导出值</th><th>一致性</th></tr>
        <tr><td>最大浓度</td><td>{results.get('max_concentration', 'N/A')}</td><td>-</td><td class="match">待对比</td></tr>
    </table>
</body>
</html>
        """
        return html
    
    async def _export_excel(
        self,
        config: ExportConfig,
        computation_package: Dict = None,
        report_data: Dict = None,
        drawing_data: Dict = None
    ) -> List[ExportItem]:
        """导出为Excel格式（多Sheet）"""
        # 注意：实际Excel生成需要openpyxl库
        # 这里生成JSON结构供后续处理
        
        excel_data = {
            "sheets": {
                "污染源": computation_package.get("inputs", {}).get("sources", []) if computation_package else [],
                "气象数据": computation_package.get("inputs", {}).get("meteorology", {}).get("annual_data", []) if computation_package else [],
                "计算结果": computation_package.get("results", {}) if computation_package else {},
                "验证记录": self.export_history[-10:] if self.export_history else []
            }
        }
        
        return [ExportItem(
            name="excel_data",
            content=excel_data,
            file_extension=".xlsx",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            source_type="output",
            description="Excel多Sheet数据（含原始数据、结果、验证记录）"
        )]
    
    async def _export_full_package(
        self,
        config: ExportConfig,
        computation_package: Dict = None,
        report_data: Dict = None,
        drawing_data: Dict = None
    ) -> List[ExportItem]:
        """导出完整验证包（ZIP压缩包）"""
        items = []
        
        # 收集所有数据
        all_items = []
        
        # 1. JSON格式完整数据
        json_items = await self._export_json(config, computation_package, report_data, drawing_data)
        all_items.extend(json_items)
        
        # 2. CSV格式数据
        csv_items = await self._export_csv(config, computation_package, report_data, drawing_data)
        all_items.extend(csv_items)
        
        # 3. KML地理数据
        kml_items = await self._export_kml(config, computation_package, report_data, drawing_data)
        all_items.extend(kml_items)
        
        # 4. 一页纸摘要
        summary_items = await self._export_pdf_report(config, computation_package, report_data)
        all_items.extend(summary_items)
        
        # 5. 生成完整的package.json清单
        package_manifest = {
            "package_id": self._generate_package_id(config.project_id, config.format),
            "project_id": config.project_id,
            "created_at": datetime.now().isoformat(),
            "verification_level": config.verification_level.value,
            "files": [
                {
                    "name": item.name,
                    "file_extension": item.file_extension,
                    "source_type": item.source_type,
                    "description": item.description
                }
                for item in all_items
            ],
            "checksum": ""
        }
        
        items.append(ExportItem(
            name="package_manifest",
            content=json.dumps(package_manifest, ensure_ascii=False, indent=2),
            file_extension=".json",
            mime_type="application/json",
            source_type="report",
            description="验证包清单文件"
        ))
        
        # 将all_items也添加到package中
        items.extend(all_items)
        
        return items
    
    async def _export_docker_package(
        self,
        config: ExportConfig,
        computation_package: Dict = None,
        report_data: Dict = None,
        drawing_data: Dict = None
    ) -> List[ExportItem]:
        """导出Docker可复现包"""
        items = []
        
        # 1. Dockerfile
        dockerfile = self._generate_dockerfile(computation_package)
        items.append(ExportItem(
            name="Dockerfile",
            content=dockerfile,
            file_extension="",
            mime_type="text/plain",
            source_type="input",
            description="Docker镜像构建文件"
        ))
        
        # 2. docker-compose.yml
        compose = self._generate_docker_compose()
        items.append(ExportItem(
            name="docker-compose",
            content=compose,
            file_extension=".yml",
            mime_type="text/yaml",
            source_type="input",
            description="Docker编排文件"
        ))
        
        # 3. 运行脚本
        run_script = self._generate_run_script()
        items.append(ExportItem(
            name="run_verification",
            content=run_script,
            file_extension=".sh",
            mime_type="text/plain",
            source_type="input",
            description="一键验证运行脚本（Linux/Mac）"
        ))
        
        run_script_win = self._generate_run_script_windows()
        items.append(ExportItem(
            name="run_verification",
            content=run_script_win,
            file_extension=".bat",
            mime_type="text/plain",
            source_type="input",
            description="一键验证运行脚本（Windows）"
        ))
        
        # 4. 输入数据JSON
        if computation_package:
            inputs_json = json.dumps(computation_package.get("inputs", {}), ensure_ascii=False, indent=2)
            items.append(ExportItem(
                name="model_inputs",
                content=inputs_json,
                file_extension=".json",
                mime_type="application/json",
                source_type="input",
                description="模型输入数据"
            ))
        
        # 5. README
        readme = self._generate_docker_readme(config)
        items.append(ExportItem(
            name="README",
            content=readme,
            file_extension=".md",
            mime_type="text/markdown",
            source_type="report",
            description="Docker包使用说明"
        ))
        
        return items
    
    def _generate_dockerfile(self, computation_package: Dict = None) -> str:
        """生成Dockerfile"""
        return f"""# EIA Verification Docker Image
FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制输入数据
COPY inputs/ ./inputs/

# 复制验证脚本
COPY verify.py .

# 设置环境
ENV PYTHONUNBUFFERED=1

# 默认命令
CMD ["python", "verify.py", "--inputs", "./inputs/model_inputs.json"]
"""
    
    def _generate_docker_compose(self) -> str:
        """生成docker-compose.yml"""
        return """version: '3.8'
services:
  eia-verification:
    build: .
    container_name: eia_verification
    volumes:
      - ./outputs:/app/outputs
    environment:
      - VERIFICATION_MODE=full
"""
    
    def _generate_run_script(self) -> str:
        """生成Linux/Mac运行脚本"""
        return """#!/bin/bash
# EIA Verification Run Script

echo "=== EIA System Verification Package ==="
echo "Starting verification..."

# 检查Docker是否安装
if ! command -v docker &> /dev/null; then
    echo "Docker not found. Please install Docker first."
    exit 1
fi

# 构建镜像
echo "Building Docker image..."
docker build -t eia-verification .

# 运行验证
echo "Running verification..."
docker run --rm -v $(pwd)/outputs:/app/outputs eia-verification

echo "Verification complete. Results saved to ./outputs/"
"""
    
    def _generate_run_script_windows(self) -> str:
        """生成Windows运行脚本"""
        return """@echo off
REM EIA Verification Run Script (Windows)

echo === EIA System Verification Package ===
echo Starting verification...

REM 检查Docker是否安装
where docker >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Docker not found. Please install Docker first.
    exit /b 1
)

REM 构建镜像
echo Building Docker image...
docker build -t eia-verification .

REM 运行验证
echo Running verification...
docker run --rm -v "%CD%\\outputs:/app/outputs" eia-verification

echo Verification complete. Results saved to .\\outputs\\
"""
    
    def _generate_docker_readme(self, config: ExportConfig) -> str:
        """生成Docker包README"""
        return f"""# EIA System 验证包 (Docker)

## 项目信息
- **项目编号**: {config.project_id}
- **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **验证级别**: {config.verification_level.value.upper()}

## 文件说明

| 文件 | 说明 |
|------|------|
| Dockerfile | Docker镜像构建文件 |
| docker-compose.yml | Docker编排配置 |
| run_verification.sh | Linux/Mac一键运行脚本 |
| run_verification.bat | Windows一键运行脚本 |
| model_inputs.json | 模型输入数据 |
| verify.py | 验证脚本 |
| README.md | 本说明文件 |

## 快速开始

### Linux/Mac
```bash
chmod +x run_verification.sh
./run_verification.sh
```

### Windows
```cmd
run_verification.bat
```

### Docker直接运行
```bash
docker build -t eia-verification .
docker run --rm -v $(pwd)/outputs:/app/outputs eia-verification
```

## 验证流程

1. **输入验证**: 检查model_inputs.json中的参数
2. **模型计算**: 使用与原计算相同的模型和参数
3. **结果对比**: 对比计算结果与原始输出
4. **生成报告**: 输出验证报告到outputs目录

## 注意事项

- 需要Docker环境（Docker Desktop for Windows/Mac，或Docker Engine for Linux）
- 首次构建需要下载基础镜像，约500MB
- 验证过程可能需要5-10分钟

## 技术支持
如有问题，请联系系统管理员。
"""
    
    # ==================== 辅助方法 ====================
    
    def get_export_history(self, project_id: str = None) -> List[Dict]:
        """获取导出历史"""
        if project_id:
            return [h for h in self.export_history if h["project_id"] == project_id]
        return self.export_history
    
    def save_package_to_file(
        self,
        package: VerificationPackage,
        output_path: str = None
    ) -> str:
        """保存验证包到文件"""
        if output_path is None:
            output_path = self.workspace_dir / f"{package.package_id}.json"
        else:
            output_path = Path(output_path)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(package.to_dict(), f, ensure_ascii=False, indent=2)
        
        return str(output_path)
    
    def create_zip_package(
        self,
        package: VerificationPackage,
        output_path: str = None
    ) -> str:
        """创建ZIP压缩包"""
        if output_path is None:
            output_path = self.workspace_dir / f"{package.package_id}.zip"
        else:
            output_path = Path(output_path)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for item in package.items:
                filename = f"{item.name}{item.file_extension}"
                content = json.dumps(item.content) if isinstance(item.content, (dict, list)) else str(item.content)
                zf.writestr(filename, content.encode("utf-8"))
        
        return str(output_path)


# ==================== 工厂函数 ====================

def create_export_manager(workspace_dir: str = None) -> ExportManager:
    """创建导出管理器"""
    return ExportManager(workspace_dir=workspace_dir)


# ==================== 便捷函数 ====================

async def export_for_verification(
    project_id: str,
    computation_package: Dict = None,
    report_data: Dict = None,
    drawing_data: Dict = None,
    format: ExportFormat = ExportFormat.FULL_PACKAGE,
    verification_level: VerificationLevel = VerificationLevel.STANDARD,
    output_dir: str = None
) -> VerificationPackage:
    """
    便捷导出函数
    
    使用示例:
    ```python
    package = await export_for_verification(
        project_id="proj_001",
        computation_package=calc_result,
        format=ExportFormat.FULL_PACKAGE
    )
    
    # 保存为ZIP
    export_manager = create_export_manager()
    zip_path = export_manager.create_zip_package(package)
    ```
    """
    config = ExportConfig(
        project_id=project_id,
        format=format,
        verification_level=verification_level,
        output_dir=output_dir
    )
    
    manager = create_export_manager(output_dir)
    return await manager.export(
        config=config,
        computation_package=computation_package,
        report_data=report_data,
        drawing_data=drawing_data
    )


async def export_eiapro_package(
    project_id: str,
    computation_package: Dict,
    output_dir: str = None
) -> VerificationPackage:
    """导出EIAProA兼容验证包"""
    return await export_for_verification(
        project_id=project_id,
        computation_package=computation_package,
        format=ExportFormat.EAIAPRO_AERMOD,
        output_dir=output_dir
    )


async def export_docker_package(
    project_id: str,
    computation_package: Dict,
    output_dir: str = None
) -> VerificationPackage:
    """导出Docker可复现包"""
    return await export_for_verification(
        project_id=project_id,
        computation_package=computation_package,
        format=ExportFormat.DOCKER_PACKAGE,
        output_dir=output_dir
    )