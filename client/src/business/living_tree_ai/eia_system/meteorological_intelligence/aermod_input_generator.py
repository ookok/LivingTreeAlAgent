"""
AERMOD输入文件生成器
====================

动态生成AERMOD INP输入文件：
1. 源参数解析
2. 气象数据文件路径注入
3. 完整INP模板

Author: Hermes Desktop EIA System
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

from .models import (
    MatchedStation,
    AERMODInput,
    ProjectLocation,
)


@dataclass
class EmissionSource:
    """排放源源参数"""
    source_id: str                    # 源ID (如 "P1", "L1")
    source_type: str = "POINT"        # POINT / VOLUME / AREA / LINE
    x: float = 0.0                    # X坐标 (UTM或相对坐标)
    y: float = 0.0                    # Y坐标
    height: float = 0.0              # 排放口高度 (m)
    temp: float = 293.15              # 烟气温度 (K)
    velocity: float = 0.0            # 出口流速 (m/s)
    diameter: float = 0.0             # 出口直径 (m)
    flow_rate: float = 0.0           # 排放速率 (g/s)
    sigma_z: float = 10.0             # 垂直扩散参数 (m)
    sigma_y: float = 20.0            # 水平扩散参数 (m)
    # 体源参数
    area: float = 0.0                # 面积 (m²)
    release_height: float = 0.0      # 释放高度 (m)

    def to_dict(self) -> Dict:
        return {
            "id": self.source_id,
            "type": self.source_type,
            "x": self.x,
            "y": self.y,
            "height": self.height,
            "q": self.flow_rate,
            "sigma_z": self.sigma_z,
            "sigma_y": self.sigma_y,
            "temp": self.temp,
            "velocity": self.velocity,
            "diameter": self.diameter,
            "area": self.area,
            "release_height": self.release_height,
        }


@dataclass
class AERMODConfig:
    """AERMOD配置"""
    title: str = "AERMOD Simulation"
    base_year: int = 2020
    # 坐标系
    coord_sys: str = "UTM"           # UTM / LAT-LON / STATEPLANE
    utm_zone: int = 50               # UTM zone (50=华东)
    datum: str = "WGS84"
    # 地形
    use_terrain: bool = False
    terrain_file: str = ""
    # 沉降
    use_deposition: bool = False
    # 输出
    output_dir: str = "./output"
    plotfile_type: str = "ALL"       # ALL / SUMM / MAX
    # 浓度标准 (μg/m³)
    standards: Dict[str, float] = field(default_factory=lambda: {
        "SO2": 150,
        "NO2": 80,
        "PM10": 150,
        "PM25": 75,
        "CO": 4000,
    })


class AERMODInputGenerator:
    """
    AERMOD输入文件生成器

    用法：
    ```python
    generator = AERMODInputGenerator()
    generator.configure(base_year=2020, utm_zone=50)

    # 添加排放源
    generator.add_point_source("P1", x=501234, y=3541234, height=15,
                                flow_rate=5.2, temp=373)

    # 生成INP
    inp_path = generator.generate(matched_station, project_dir)
    ```
    """

    def __init__(self, config: Optional[AERMODConfig] = None):
        self.config = config or AERMODConfig()
        self._sources: List[EmissionSource] = []

    def configure(self, **kwargs):
        """配置AERMOD参数"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)

    def clear_sources(self):
        """清空所有源"""
        self._sources = []

    def add_point_source(
        self,
        source_id: str,
        x: float,
        y: float,
        height: float,
        flow_rate: float,
        temp: float = 373.15,
        velocity: float = 0.0,
        diameter: float = 0.0,
        sigma_z: float = 10.0,
        sigma_y: float = 20.0
    ):
        """添加点源"""
        src = EmissionSource(
            source_id=source_id,
            source_type="POINT",
            x=x,
            y=y,
            height=height,
            temp=temp,
            velocity=velocity,
            diameter=diameter,
            flow_rate=flow_rate,
            sigma_z=sigma_z,
            sigma_y=sigma_y
        )
        self._sources.append(src)

    def add_volume_source(
        self,
        source_id: str,
        x: float,
        y: float,
        area: float,
        release_height: float,
        flow_rate: float,
        sigma_z: float = 10.0,
        sigma_y: float = 20.0
    ):
        """添加体源"""
        src = EmissionSource(
            source_id=source_id,
            source_type="VOLUME",
            x=x,
            y=y,
            height=release_height,
            area=area,
            release_height=release_height,
            flow_rate=flow_rate,
            sigma_z=sigma_z,
            sigma_y=sigma_y
        )
        self._sources.append(src)

    def add_area_source(
        self,
        source_id: str,
        x: float,
        y: float,
        area: float,
        height: float,
        flow_rate: float
    ):
        """添加面源"""
        src = EmissionSource(
            source_id=source_id,
            source_type="AREA",
            x=x,
            y=y,
            area=area,
            height=height,
            flow_rate=flow_rate
        )
        self._sources.append(src)

    def _build_co_key(self) -> str:
        """构建CO OPTIONS块"""
        lines = ["CO OPTIONS"]
        if self.config.coord_sys == "UTM":
            lines.append(f"   URBAN UTMUTM {self.config.utm_zone}")
        lines.append(f"   FLAT")
        if self.config.use_terrain:
            lines.append(f"   CONCERR")
            lines.append(f"   TERMN")
        if self.config.use_deposition:
            lines.append(f"   DEPOS")
        return "\n".join(lines)

    def _build_ye_key(self) -> str:
        """构建YE KEYWORD块"""
        return f"   YEAR    {self.config.base_year}"

    def _build_so_source_block(self) -> str:
        """构建SO SOURCE块"""
        lines = ["SO STARTING"]
        lines.append(f"   TITLEONE {self.config.title}")

        for src in self._sources:
            if src.source_type == "POINT":
                lines.append(f"   LOCATION {src.source_id} POINT {src.x:.1f} {src.y:.1f} {src.height:.1f}")
                # 源参数：排放速率, 高度, 温度, 流速, 直径
                lines.append(f"   SRCPARAM {src.source_id} {src.flow_rate:.4f} {src.height:.1f} {src.temp:.1f} {src.velocity:.1f} {src.diameter:.2f}")
            elif src.source_type == "VOLUME":
                lines.append(f"   LOCATION {src.source_id} VOLUME {src.x:.1f} {src.y:.1f} {src.release_height:.1f}")
                lines.append(f"   SRCPARAM {src.source_id} {src.flow_rate:.4f} {src.sigma_z:.1f} {src.sigma_y:.1f}")
            elif src.source_type == "AREA":
                lines.append(f"   LOCATION {src.source_id} AREA {src.x:.1f} {src.y:.1f} {src.height:.1f}")
                lines.append(f"   SRCPARAM {src.source_id} {src.flow_rate:.4f} {src.area:.1f}")

        lines.append("SO FINISHED")
        return "\n".join(lines)

    def _build_me_met_block(self, matched: MatchedStation) -> str:
        """构建ME METEO块"""
        lines = ["ME STARTING"]

        # 气象文件路径
        if matched.met_files:
            sfc_path = Path(matched.met_files.file_sfc).name if matched.met_files.file_sfc else ""
            pc_path = Path(matched.met_files.file_pc).name if matched.met_files.file_pc else ""

            lines.append(f"   SURFFILE {sfc_path}")
            lines.append(f"   PROFFILE {pc_path}")
            lines.append(f"   PROFBASE {matched.station.altitude:.1f}")

        # 站点信息
        lines.append(f"   STA ANEM {matched.station.altitude:.1f}")
        lines.append(f"   URBAN {matched.station.name} {matched.station.altitude:.1f}")

        lines.append("ME FINISHED")
        return "\n".join(lines)

    def _build_re_output_block(self) -> str:
        """构建RE OUTPUT块"""
        lines = ["RE STARTING"]
        lines.append(f"   PLOTFILE {self.config.plotfile_type} ALL {self.config.output_dir}/plotfile.rou")
        lines.append("RE FINISHED")
        return "\n".join(lines)

    def _build_ou_output_block(self) -> str:
        """构建OU OUTPUT块"""
        lines = ["OU STARTING"]
        lines.append(f"   PLOTFILE ALL {self.config.output_dir}/results.pln")
        lines.append("OU FINISHED")
        return "\n".join(lines)

    def generate_inp_content(self, matched: MatchedStation) -> str:
        """
        生成INP文件内容

        Args:
            matched: 匹配的站点信息

        Returns:
            INP文件内容字符串
        """
        blocks = [
            self._build_co_key(),
            "",
            self._build_so_source_block(),
            "",
            self._build_me_met_block(matched),
            "",
            self._build_re_output_block(),
            "",
            self._build_ou_output_block(),
        ]

        return "\n".join(blocks)

    def generate(
        self,
        matched: MatchedStation,
        output_dir: str,
        filename: str = "aermod.inp"
    ) -> str:
        """
        生成INP文件

        Args:
            matched: 匹配的站点信息
            output_dir: 输出目录
            filename: 文件名

        Returns:
            生成的INP文件路径
        """
        # 确保输出目录存在
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # 生成内容
        content = self.generate_inp_content(matched)

        # 写入文件
        inp_path = Path(output_dir) / filename
        inp_path.write_text(content, encoding="utf-8")

        return str(inp_path)

    def generate_for_project(
        self,
        project: ProjectLocation,
        matched: MatchedStation,
        output_dir: str,
        sources: List[Dict[str, Any]]
    ) -> str:
        """
        为项目生成完整的AERMOD输入文件

        Args:
            project: 项目位置
            matched: 匹配的气象站
            output_dir: 输出目录
            sources: 源参数列表

        Returns:
            生成的INP文件路径
        """
        # 清空并重新添加源
        self.clear_sources()
        self.config.title = f"{project.project_name} 大气环境影响预测"

        for src in sources:
            src_type = src.get("type", "POINT").upper()
            if src_type == "POINT":
                self.add_point_source(
                    source_id=src["id"],
                    x=src["x"],
                    y=src["y"],
                    height=src["height"],
                    flow_rate=src["flow_rate"],
                    temp=src.get("temp", 373.15),
                    velocity=src.get("velocity", 0),
                    diameter=src.get("diameter", 0),
                    sigma_z=src.get("sigma_z", 10),
                    sigma_y=src.get("sigma_y", 20)
                )
            elif src_type == "VOLUME":
                self.add_volume_source(
                    source_id=src["id"],
                    x=src["x"],
                    y=src["y"],
                    area=src["area"],
                    release_height=src["release_height"],
                    flow_rate=src["flow_rate"],
                    sigma_z=src.get("sigma_z", 10),
                    sigma_y=src.get("sigma_y", 20)
                )
            elif src_type == "AREA":
                self.add_area_source(
                    source_id=src["id"],
                    x=src["x"],
                    y=src["y"],
                    area=src["area"],
                    height=src["height"],
                    flow_rate=src["flow_rate"]
                )

        return self.generate(matched, output_dir)


# 便捷函数
def generate_aermod_inp(
    project: ProjectLocation,
    matched: MatchedStation,
    sources: List[Dict[str, Any]],
    output_dir: str,
    config: Optional[AERMODConfig] = None
) -> str:
    """
    快捷函数：生成AERMOD输入文件

    Args:
        project: 项目位置
        matched: 匹配的气象站
        sources: 源参数列表
        output_dir: 输出目录
        config: AERMOD配置

    Returns:
        生成的INP文件路径
    """
    generator = AERMODInputGenerator(config)
    return generator.generate_for_project(project, matched, output_dir, sources)


def create_sample_inp(project_name: str, station_name: str) -> str:
    """
    创建示例INP文件内容

    Args:
        project_name: 项目名称
        station_name: 气象站名称

    Returns:
        INP文件内容
    """
    config = AERMODConfig(title=project_name)
    generator = AERMODInputGenerator(config)

    # 添加示例点源
    generator.add_point_source(
        source_id="P1",
        x=501234,
        y=3541234,
        height=15.0,
        flow_rate=5.2,
        temp=373.15,
        velocity=10.0,
        diameter=1.5
    )

    # 创建假的matched对象
    from .models import WeatherStation, MatchedStation, MetDataFile, DataStatus

    station = WeatherStation(
        station_id="58238",
        name=station_name,
        latitude=32.0,
        longitude=118.8,
        altitude=8.9
    )

    project = ProjectLocation(
        project_id="sample",
        project_name=project_name,
        latitude=32.0,
        longitude=118.8
    )

    matched = MatchedStation(
        project=project,
        station=station,
        distance_deg=0.0,
        distance_km=0.0,
        cache_status=DataStatus.MISSING,
        met_files=None
    )

    return generator.generate_inp_content(matched)
