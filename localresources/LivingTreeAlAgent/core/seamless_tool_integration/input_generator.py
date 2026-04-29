"""
Input Generator - 输入文件自动生成器

负责：
1. 从项目数据生成AERMOD/CALPUFF输入文件
2. 自动获取气象数据
3. 生成评价范围和受体网格
4. 处理土地利用和地形数据
"""

import os
import json
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
import math


class ScaleType(Enum):
    """评价尺度"""
    LOCAL = "local"           # 局地尺度 (≤50km)
    REGIONAL = "regional"     # 区域尺度 (>50km)


class MeteorologyDataSource(Enum):
    """气象数据来源"""
    AUTO_DOWNLOAD = "auto"    # 自动下载
    USER_UPLOAD = "upload"    # 用户上传
    DEFAULT = "default"       # 默认数据


@dataclass
class SourceParams:
    """污染源参数"""
    source_id: str = "S1"
    source_name: str = ""

    # 位置 (经纬度)
    latitude: float = 0.0
    longitude: float = 0.0

    # 源类型
    source_type: str = "POINT"  # POINT, AREA, VOLUME, LINE

    # 排放参数
    emission_rate: float = 0.0    # g/s
    emission_height: float = 0.0  # m
    exit_velocity: float = 0.0    # m/s
    exit_temperature: float = 0.0 # K

    # 烟囱参数
    stack_diameter: float = 0.0   # m
    stack_height: float = 0.0    # m

    #  Building dimensions (for downwash)
    building_height: float = 0.0
    building_width: float = 0.0
    building_length: float = 0.0


@dataclass
class ReceptorGrid:
    """受体网格"""
    # 网格类型
    grid_type: str = "CARTESIAN"  # CARTESIAN, LATLON

    # 中心点
    center_x: float = 0.0
    center_y: float = 0.0

    # 网格范围
    x_min: float = -5000.0  # m
    x_max: float = 5000.0
    y_min: float = -5000.0
    y_max: float = 5000.0

    # 分辨率
    x_step: float = 100.0   # m
    y_step: float = 100.0

    # 离散受体点
    discrete_receptors: List[Tuple[float, float]] = field(default_factory=list)

    @property
    def x_count(self) -> int:
        return int((self.x_max - self.x_min) / self.x_step) + 1

    @property
    def y_count(self) -> int:
        return int((self.y_max - self.y_min) / self.y_step) + 1

    @property
    def total_points(self) -> int:
        return self.x_count * self.y_count + len(self.discrete_receptors)


@dataclass
class MeteorologyData:
    """气象数据"""
    data_source: MeteorologyDataSource = MeteorologyDataSource.AUTO_DOWNLOAD

    # 站点信息
    station_id: str = ""
    station_name: str = ""
    station_latitude: float = 0.0
    station_longitude: float = 0.0

    # 数据文件路径
    data_file: str = ""

    # 时间范围
    start_date: datetime = field(default_factory=datetime.now)
    end_date: datetime = field(default_factory=lambda: datetime.now() + timedelta(days=365))

    # 数据年份
    data_year: int = 2024


@dataclass
class ProjectData:
    """
    项目数据 - 所有输入参数的统一封装

    使用示例：
    ```python
    project = ProjectData(
        project_name="南京XX化工厂",
        location=(118.78, 32.04),  # 经纬度
        scale=ScaleType.LOCAL,
        pollutants=["SO2", "NOx", "PM25"],
        emission_sources=[...],
        meteorology=MeteorologyData(station_id="58362")
    )
    ```
    """
    # 基本信息
    project_name: str = ""
    project_id: str = ""

    # 位置
    latitude: float = 0.0
    longitude: float = 0.0
    location_name: str = ""

    # 评价尺度
    scale: ScaleType = ScaleType.LOCAL

    # 预测因子
    pollutants: List[str] = field(default_factory=list)

    # 污染源
    emission_sources: List[SourceParams] = field(default_factory=list)

    # 气象数据
    meteorology: MeteorologyData = field(default_factory=MeteorologyData)

    # 受体网格
    receptor_grid: ReceptorGrid = field(default_factory=ReceptorGrid)

    # 输出选项
    output_options: Dict[str, Any] = field(default_factory=dict)

    # 其他参数
    terrain_type: str = "FLAT"  # FLAT, COMPLEX
    land_use: str = "RURAL"     # RURAL, URBAN, SUBURBAN

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "project_name": self.project_name,
            "project_id": self.project_id,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "location_name": self.location_name,
            "scale": self.scale.value,
            "pollutants": self.pollutants,
            "terrain_type": self.terrain_type,
            "land_use": self.land_use,
        }


class BaseInputGenerator:
    """输入文件生成器基类"""

    def __init__(self, project_data: ProjectData):
        self.project_data = project_data

    def generate(self, output_dir: str) -> Dict[str, str]:
        """
        生成输入文件

        Args:
            output_dir: 输出目录

        Returns:
            生成的文件路径字典
        """
        raise NotImplementedError


class AermodInputGenerator(BaseInputGenerator):
    """
    AERMOD输入文件生成器

    生成标准AERMOD输入文件格式：
    - 路径文件名 (.pfl)
    - 气象数据文件 (.met)
    - 源参数文件 (.src)
    - 主输入文件 (.inp)

    AERMOD输入文件结构：
    ```
    CO STARTING
    TITLE     项目标题
    MODELOPT  CONC   REG   PRIME
    AVERTIME  1  3  8  24
    POLLUTID  PM25
    OPENFILE  ...
    ... 更多参数
    CO FINISHED

    SOURCECALC 
    SOURCE     S1 ...
    SRCGRPS    ALL
    ...
    OUTPUT     TABLES
    ```

    使用示例：
    ```python
    generator = AermodInputGenerator(project_data)
    files = generator.generate("/tmp/aermod")
    # files = {'input': '/tmp/aermod.inp', 'output': '/tmp/aermod.out'}
    ```
    """

    # AERMOD污染物代码映射
    POLLUTANT_CODES = {
        "SO2": "SO2",
        "NOx": "NOX",
        "NO2": "NO2",
        "PM10": "PM10",
        "PM25": "PM2.5",
        "VOCs": "VOC",
        "CO": "CO",
        "O3": "O3",
    }

    def __init__(self, project_data: ProjectData):
        super().__init__(project_data)
        self.template_dir = self._get_template_dir()

    def _get_template_dir(self) -> str:
        """获取模板目录"""
        base_dir = Path(__file__).parent
        return base_dir / "templates"

    def generate(self, output_dir: str) -> Dict[str, str]:
        """
        生成AERMOD输入文件

        Args:
            output_dir: 输出目录

        Returns:
            文件路径字典
        """
        os.makedirs(output_dir, exist_ok=True)

        files = {}

        # 生成主输入文件
        input_file = os.path.join(output_dir, "aermod.inp")
        with open(input_file, 'w', encoding='utf-8') as f:
            f.write(self._generate_main_input())
        files['input'] = input_file

        # 生成源参数文件
        source_file = os.path.join(output_dir, "sources.txt")
        with open(source_file, 'w', encoding='utf-8') as f:
            f.write(self._generate_source_params())
        files['sources'] = source_file

        # 生成受体网格文件
        receptor_file = os.path.join(output_dir, "receptors.txt")
        with open(receptor_file, 'w', encoding='utf-8') as f:
            f.write(self._generate_receptor_grid())
        files['receptors'] = receptor_file

        # 生成气象数据文件（占位，实际从气象服务获取）
        meteo_file = os.path.join(output_dir, "meteo.dat")
        with open(meteo_file, 'w', encoding='utf-8') as f:
            f.write(self._generate_meteo_file())
        files['meteo'] = meteo_file

        # 生成批处理脚本
        bat_file = os.path.join(output_dir, "run_aermod.bat")
        with open(bat_file, 'w', encoding='utf-8') as f:
            f.write(self._generate_batch_script())
        files['batch'] = bat_file

        return files

    def _generate_main_input(self) -> str:
        """生成主输入文件内容"""

        # 处理污染物代码
        pollutants = []
        for p in self.project_data.pollutants:
            code = self.POLLUTANT_CODES.get(p, p)
            if code not in pollutants:
                pollutants.append(code)

        pollute_line = " ".join(pollutants) if pollutants else "SO2"

        # 处理源组
        source_ids = [s.source_id for s in self.project_data.emission_sources]
        source_grp_line = " ".join(source_ids) if source_ids else "ALL"

        # 计算网格范围
        grid = self.project_data.receptor_grid

        template = f"""CO STARTING
TITLE     {self.project_data.project_name or 'Air Quality Prediction'}
MODELOPT  CONC   REG   PRIME    CSD    DRYDPLT    WETPLT
AVERTIME  1  3  8  24
POLLUTID  {pollute_line}
RUNORNOT  RUN
EXECUTABLE {''}

** 路径文件名
PATHOFILE  {self.project_data.project_name or 'model'}.pfl

** 气象数据
METFILE    meteo.dat

** 输出选项
OUTPUT     TABLES   MAXIFILE   MAX TABLE

** 评价范围
GRIDCART   GRID1  COORD   {grid.center_x}   {grid.center_y}
           XYINC   {grid.x_min}   {grid.x_max}   {grid.x_step}
                   {grid.y_min}   {grid.y_max}   {grid.y_step}

** 时均选项
RE              ALL

CO FINISHED

** 源参数
SOURCECALC

{source_grp_line}

** {len(source_ids)} 个污染源
{self._generate_sources_block()}

** 受体
{self._generate_receptors_block()}

** 输出文件
OUTFILE   {self.project_data.project_name or 'result'}.out

** 结束
END
"""
        return template

    def _generate_sources_block(self) -> str:
        """生成源参数块"""
        blocks = []

        for source in self.project_data.emission_sources:
            if source.source_type == "POINT":
                block = f"""SRCGROUP  {source.source_id}
SOURCE    {source.source_id}  POINT  {source.source_name or source.source_id}
SRCPARAM  {source.source_id}
           {source.emission_rate}   {source.stack_height}
           {source.exit_velocity}   {source.exit_temperature}
           {source.stack_diameter}
LOCATOR   {source.source_id}  {source.latitude}  {source.longitude}  0
"""
            else:
                block = f"""SOURCE    {source.source_id}  {source.source_type}
SRCPARAM  {source.source_id}  {source.emission_rate}
"""
            blocks.append(block)

        return "\n".join(blocks)

    def _generate_receptors_block(self) -> str:
        """生成受体块"""
        grid = self.project_data.receptor_grid

        block = f"""** 网格受体
REGRID    CARTESIAN  GRID1  {grid.x_count}  {grid.y_count}

** 离散受体
"""
        for i, (x, y) in enumerate(grid.discrete_receptors):
            block += f"DISCRETE  RECEPTOR  {i+1}  {x}  {y}\n"

        return block

    def _generate_source_params(self) -> str:
        """生成源参数说明"""
        lines = ["# AERMOD源参数说明", ""]

        for source in self.project_data.emission_sources:
            lines.append(f"# 源ID: {source.source_id}")
            lines.append(f"# 名称: {source.source_name}")
            lines.append(f"# 类型: {source.source_type}")
            lines.append(f"# 坐标: ({source.latitude}, {source.longitude})")
            lines.append(f"# 排放速率: {source.emission_rate} g/s")
            lines.append(f"# 排放高度: {source.stack_height} m")
            lines.append(f"# 出口速度: {source.exit_velocity} m/s")
            lines.append(f"# 出口温度: {source.exit_temperature} K")
            lines.append(f"# 烟囱直径: {source.stack_diameter} m")
            lines.append("")

        return "\n".join(lines)

    def _generate_receptor_grid(self) -> str:
        """生成受体网格说明"""
        grid = self.project_data.receptor_grid

        lines = ["# AERMOD受体网格说明", ""]
        lines.append(f"# 网格类型: {grid.grid_type}")
        lines.append(f"# 中心点: ({grid.center_x}, {grid.center_y})")
        lines.append(f"# X范围: {grid.x_min} ~ {grid.x_max} m, 步长 {grid.x_step} m")
        lines.append(f"# Y范围: {grid.y_min} ~ {grid.y_max} m, 步长 {grid.y_step} m")
        lines.append(f"# 网格点数: {grid.total_points}")
        lines.append("")

        return "\n".join(lines)

    def _generate_meteo_file(self) -> str:
        """生成气象数据文件占位符"""
        meteo = self.project_data.meteorology

        return f"""# 气象数据文件
# 数据来源: {meteo.data_source.value}
# 站点: {meteo.station_name or meteo.station_id}
# 年份: {meteo.data_year}
#
# 实际气象数据需要从以下方式获取：
# 1. 国家气象科学数据中心
# 2. 地面气象观测数据
# 3. 探空数据
#
# 建议使用 AERMET 预处理气象数据
"""

    def _generate_batch_script(self) -> str:
        """生成批处理脚本"""
        # 使用默认安装路径
        from .model_deployer import ModelDeployer
        exe_path = os.path.join(
            ModelDeployer.DEFAULT_TOOLS_DIR,
            "aermod",
            "aermod.exe"
        )

        return f"""@echo off
REM AERMOD运行脚本 - 自动生成
REM 项目: {self.project_data.project_name}
REM 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

echo 开始运行AERMOD...
echo.

REM 设置路径
set AERMOD_PATH={exe_path}
set WORK_DIR=%~dp0

REM 运行模型
"%AERMOD_PATH%" {self.project_data.project_name or 'aermod'}.inp

if errorlevel 1 (
    echo.
    echo 运行出错，请检查输入文件！
    pause
) else (
    echo.
    echo 运行完成！结果文件：{self.project_data.project_name or 'result'}.out
)

pause
"""


class CalpuffInputGenerator(BaseInputGenerator):
    """
    CALPUFF输入文件生成器

    CALPUFF是一个更复杂的模型，需要多个输入文件：
    - CALPUFF.INP (主控制文件)
    - DATSAV.TXT (数据路径)
    - 气象数据文件
    - 地形数据文件
    """

    def generate(self, output_dir: str) -> Dict[str, str]:
        """生成CALPUFF输入文件"""
        os.makedirs(output_dir, exist_ok=True)

        files = {}

        # 主输入文件
        input_file = os.path.join(output_dir, "CALPUFF.INP")
        with open(input_file, 'w', encoding='utf-8') as f:
            f.write(self._generate_main_input())
        files['input'] = input_file

        # 数据路径文件
        datsav_file = os.path.join(output_dir, "DATSAV.TXT")
        with open(datsav_file, 'w', encoding='utf-8') as f:
            f.write(self._generate_datsav())
        files['datsav'] = datsav_file

        return files

    def _generate_main_input(self) -> str:
        """生成CALPUFF主输入文件"""
        return f"""** CALPUFF Input File
** Project: {self.project_data.project_name}
** Generated: {datetime.now()}

&CALPROC  IO_TYPE=1, ... /

&NAMP
  PNAME='{self.project_data.project_name}'
/

...
"""

    def _generate_datsav(self) -> str:
        """生成数据路径文件"""
        return f"""** CALPUFF Data Paths
** Project: {self.project_data.project_name}

/path/to/meteo/
/path/to/terrain/
/path/to/landuse/
"""


class InputGenerator:
    """
    输入生成器工厂

    根据工具类型自动选择生成器

    使用示例：
    ```python
    generator = InputGenerator.create("aermod", project_data)
    files = generator.generate("/tmp/output")
    ```
    """

    _generators = {
        "aermod": AermodInputGenerator,
        "calpuff": CalpuffInputGenerator,
    }

    @classmethod
    def create(cls, tool_type: str, project_data: ProjectData) -> BaseInputGenerator:
        """
        创建输入生成器

        Args:
            tool_type: 工具类型
            project_data: 项目数据

        Returns:
            对应的生成器实例
        """
        generator_class = cls._generators.get(tool_type.lower())
        if not generator_class:
            raise ValueError(f"不支持的工具类型: {tool_type}")

        return generator_class(project_data)

    @classmethod
    def register(cls, tool_type: str, generator_class: type):
        """注册新的生成器"""
        cls._generators[tool_type.lower()] = generator_class


# 便捷函数
def quick_generate(tool_type: str, project_data: ProjectData, output_dir: str) -> Dict[str, str]:
    """
    快速生成输入文件

    使用示例：
    ```python
    files = quick_generate("aermod", project_data, "/tmp/aermod")
    print(f"生成文件: {list(files.keys())}")
    ```
    """
    generator = InputGenerator.create(tool_type, project_data)
    return generator.generate(output_dir)
