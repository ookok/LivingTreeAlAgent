"""
CadnaA 噪声模型工具 (CadnaATool)
========================================

环评噪声影响预测工具接口：
- 输入：声源数据、地形数据、气象数据、接收点
- 处理：准备CadnaA输入文件 → 调用模型 → 解析输出
- 输出：噪声等值线、噪声级（Ld, Leq, Lnight）

注意：CadnaA 是 DataKustik 商业软件，此工具提供接口层。
实际执行需要安装 CadnaA 或连接到计算集群。

支持的文件格式：
- 输入：.cna (CadnaA 项目文件)
- 地形：.dem, .tif
- 气象：.met
- 输出：.txt, .shp, .tif (噪声等值线）
"""

import os
import subprocess
import tempfile
from typing import Optional, Dict, Any, List
from pathlib import Path
import json

from client.src.business.tools.base_tool import BaseTool
from client.src.business.tools.tool_definition import ToolDefinition, ToolParameter
from client.src.business.tools.tool_result import ToolResult, SUCCESS, ERROR


# ============================================================
# CadnaA 工具参数定义
# ============================================================

CADNAA_TOOL_DEF = ToolDefinition(
    name="cadnaa_tool",
    description="CadnaA 噪声预测模型接口（环评噪声影响预测）",
    category="simulation",
    parameters=[
        ToolParameter("project_type", "string", "项目类型：industrial/transportation/construction", required=True),
        ToolParameter("sound_sources", "array", "声源列表（名称、位置、声功率级）", required=True),
        ToolParameter("terrain_file", "string", "地形文件路径（.dem/.tif）", required=False),
        ToolParameter("meteo_data", "object", "气象数据（温度、湿度、风速）", required=False),
        ToolParameter("receiver_points", "array", "接收点列表（坐标）", required=False),
        ToolParameter("calculation_grid", "object", "计算网格设置（x_min, y_min, x_max, y_max, dx, dy）", required=False),
        ToolParameter("noise_indicators", "array", "噪声指标：[Ld, Leq, Lnight, Lden]", required=False),
        ToolParameter("cadnaa_exe_path", "string", "CadnaA 可执行文件路径（可选）", required=False),
        ToolParameter("work_dir", "string", "工作目录（可选）", required=False),
    ],
    returns={
        "success": "是否成功",
        "data": "噪声预测结果（路径或解析后的数据）",
        "output_files": "输出文件列表",
        "noise_levels": "噪声级统计",
        "contour_files": "等值线文件列表"
    },
    error_codes={
        "CADNAA_NOT_FOUND": "CadnaA 可执行文件未找到",
        "INPUT_INVALID": "输入数据无效",
        "SIMULATION_FAILED": "模拟执行失败",
        "OUTPUT_NOT_FOUND": "输出文件未找到"
    }
)


# ============================================================
# CadnaA 工具实现
# ============================================================

class CadnaATool(BaseTool):
    """
    CadnaA 噪声预测模型工具
    
    功能：
    - 准备 CadnaA 输入文件（.cna 格式）
    - 调用 CadnaA 执行噪声预测
    - 解析输出文件（噪声级、等值线）
    - 生成标准化结果
    
    使用方式：
    1. 本地安装 CadnaA：直接调用
    2. 远程集群：通过 SSH 提交作业
    3. 输出解析：读取文本/Shapefile/GeoTIFF
    """
    
    def __init__(self):
        super().__init__(CADNAA_TOOL_DEF)
        self._cadnaa_exe = self._find_cadnaa()
    
    def _find_cadnaa(self) -> Optional[str]:
        """查找 CadnaA 可执行文件"""
        # 常见安装路径
        possible_paths = [
            r"C:\Program Files\DataKustik\CadnaA\bin\CadnaA.exe",
            r"C:\Program Files (x86)\DataKustik\CadnaA\bin\CadnaA.exe",
            r"C:\CadnaA\bin\CadnaA.exe",
        ]
        
        for path in possible_paths:
            if Path(path).exists():
                return path
        
        # 检查环境变量
        if "CADNAA_HOME" in os.environ:
            exe_path = Path(os.environ["CADNAA_HOME"]) / "bin" / "CadnaA.exe"
            if exe_path.exists():
                return str(exe_path)
        
        return None
    
    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行 CadnaA 噪声预测"""
        project_type = inputs.get("project_type", "industrial")
        work_dir = inputs.get("work_dir", tempfile.mkdtemp(prefix="cadnaa_"))
        cadnaa_exe = inputs.get("cadnaa_exe_path", self._cadnaa_exe)
        
        if not cadnaa_exe or not Path(cadnaa_exe).exists():
            return ERROR(
                error="CADNAA_NOT_FOUND",
                message="CadnaA 可执行文件未找到，请安装 CadnaA 或设置 cadnaa_exe_path"
            ).to_dict()
        
        # 验证输入
        validation_error = self._validate_inputs(inputs)
        if validation_error:
            return ERROR(
                error="INPUT_INVALID",
                message=validation_error
            ).to_dict()
        
        # 准备输入文件
        prepare_result = self._prepare_input_files(inputs, work_dir)
        if not prepare_result.success:
            return prepare_result.to_dict()
        
        project_file = prepare_result.data["project_file"]
        
        # 执行模拟
        run_result = self._run_simulation(cadnaa_exe, project_file, work_dir)
        if not run_result.success:
            return run_result.to_dict()
        
        # 解析输出
        parse_result = self._parse_output(work_dir, inputs.get("noise_indicators"))
        return parse_result.to_dict()
    
    def _validate_inputs(self, inputs: Dict[str, Any]) -> Optional[str]:
        """验证输入数据"""
        sound_sources = inputs.get("sound_sources", [])
        if not sound_sources:
            return "声源数据不能为空"
        
        # 检查声源数据格式
        for i, source in enumerate(sound_sources):
            if not isinstance(source, dict):
                return f"声源 {i} 必须是字典格式"
            if "x" not in source or "y" not in source:
                return f"声源 {i} 必须包含 x, y 坐标"
            if "Lw" not in source and "sound_power" not in source:
                return f"声源 {i} 必须包含声功率级 Lw 或 sound_power"
        
        project_type = inputs.get("project_type", "")
        if project_type not in ["industrial", "transportation", "construction"]:
            return f"不支持的项目类型: {project_type}"
        
        return None
    
    def _prepare_input_files(self, inputs: Dict[str, Any], work_dir: str) -> ToolResult:
        """准备 CadnaA 输入文件（.cna 格式）"""
        try:
            work_path = Path(work_dir)
            work_path.mkdir(parents=True, exist_ok=True)
            
            # 生成 .cna 项目文件
            cna_content = self._generate_cna_file(inputs)
            project_file = work_path / "noise_project.cna"
            
            with open(project_file, "w", encoding="utf-8") as f:
                f.write(cna_content)
            
            # 如果有地形文件，复制到工作目录
            terrain_file = inputs.get("terrain_file")
            if terrain_file and Path(terrain_file).exists():
                import shutil
                shutil.copy(terrain_file, work_path / Path(terrain_file).name)
            
            # 生成气象文件（如果有）
            meteo_data = inputs.get("meteo_data")
            if meteo_data:
                meteo_file = work_path / "meteo.met"
                self._generate_meteo_file(meteo_data, meteo_file)
            
            return SUCCESS(data={
                "project_file": str(project_file),
                "work_dir": work_dir
            })
        except Exception as e:
            return ERROR(
                error="PREPARE_FAILED",
                message=f"准备输入文件失败: {e}"
            )
    
    def _generate_cna_file(self, inputs: Dict[str, Any]) -> str:
        """生成 CadnaA 项目文件（.cna 简化格式）"""
        project_type = inputs.get("project_type", "industrial")
        sound_sources = inputs.get("sound_sources", [])
        receiver_points = inputs.get("receiver_points", [])
        calculation_grid = inputs.get("calculation_grid", {})
        noise_indicators = inputs.get("noise_indicators", ["Ld", "Leq"])
        
        lines = [
            "[CadnaA Project File]",
            f"ProjectType = {project_type}",
            f"NoiseIndicators = {','.join(noise_indicators)}",
            "",
            "[SoundSources]",
        ]
        
        # 添加声源
        for i, source in enumerate(sound_sources):
            x = source.get("x", 0)
            y = source.get("y", 0)
            z = source.get("z", 0)
            lw = source.get("Lw", source.get("sound_power", 0))
            source_type = source.get("type", "point")
            
            lines.append(f"Source{i+1} = {source_type}, {x}, {y}, {z}, {lw}")
        
        # 添加接收点
        if receiver_points:
            lines.append("")
            lines.append("[ReceiverPoints]")
            for i, point in enumerate(receiver_points):
                x = point.get("x", 0)
                y = point.get("y", 0)
                lines.append(f"Point{i+1} = {x}, {y}")
        
        # 添加计算网格
        if calculation_grid:
            lines.append("")
            lines.append("[CalculationGrid]")
            lines.append(f"XMin = {calculation_grid.get('x_min', 0)}")
            lines.append(f"YMin = {calculation_grid.get('y_min', 0)}")
            lines.append(f"XMax = {calculation_grid.get('x_max', 1000)}")
            lines.append(f"YMax = {calculation_grid.get('y_max', 1000)}")
            lines.append(f"DX = {calculation_grid.get('dx', 10)}")
            lines.append(f"DY = {calculation_grid.get('dy', 10)}")
        
        return "\n".join(lines)
    
    def _generate_meteo_file(self, meteo_data: Dict, output_file: Path):
        """生成气象文件"""
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("[Meteorological Data]\n")
            f.write(f"Temperature = {meteo_data.get('temperature', 20)}\n")
            f.write(f"Humidity = {meteo_data.get('humidity', 70)}\n")
            f.write(f"WindSpeed = {meteo_data.get('wind_speed', 2.0)}\n")
            f.write(f"WindDirection = {meteo_data.get('wind_dir', 0)}\n")
    
    def _run_simulation(self, exe_path: str, project_file: str,
                       work_dir: str) -> ToolResult:
        """执行 CadnaA 模拟"""
        try:
            # CadnaA 命令行参数（简化，实际参数需参考 CadnaA 文档）
            cmd = [exe_path, "-project", project_file, "-autorun", "-exit"]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=1800,  # 30 分钟超时
                cwd=work_dir
            )
            
            if result.returncode == 0:
                return SUCCESS(data={
                    "returncode": 0,
                    "stdout": result.stdout[-1000:] if result.stdout else "",
                    "work_dir": work_dir
                })
            else:
                return ERROR(
                    error="SIMULATION_FAILED",
                    message=f"CadnaA 执行失败（返回码 {result.returncode}）: {result.stderr[:500]}"
                )
        except subprocess.TimeoutExpired:
            return ERROR(
                error="SIMULATION_TIMEOUT",
                message="CadnaA 模拟超时（>30分钟）"
            )
        except Exception as e:
            return ERROR(
                error="SIMULATION_ERROR",
                message=f"执行 CadnaA 时出错: {e}"
            )
    
    def _parse_output(self, work_dir: str,
                     noise_indicators: Optional[List[str]]) -> ToolResult:
        """解析 CadnaA 输出文件"""
        work_path = Path(work_dir)
        
        # 查找输出文件
        output_files = {
            "txt": list(work_path.glob("*.txt")),
            "shp": list(work_path.glob("*.shp")),
            "tif": list(work_path.glob("*.tif")),
            "log": list(work_path.glob("*.log")),
        }
        
        # 解析噪声级结果（简化版）
        noise_levels = {}
        for txt_file in output_files["txt"]:
            try:
                with open(txt_file, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    # 提取噪声级（简化正则）
                    import re
                    leq_match = re.search(r"Leq\s*=\s*([\d.]+)", content)
                    if leq_match:
                        noise_levels["Leq"] = float(leq_match.group(1))
            except Exception:
                pass
        
        # 查找等值线文件
        contour_files = {
            "shapefile": [str(f) for f in output_files["shp"]],
            "geotiff": [str(f) for f in output_files["tif"]],
        }
        
        return SUCCESS(data={
            "output_files": {
                "txt": [str(f) for f in output_files["txt"]],
                "shp": [str(f) for f in output_files["shp"]],
                "tif": [str(f) for f in output_files["tif"]],
                "log": [str(f) for f in output_files["log"]],
            },
            "noise_levels": noise_levels,
            "contour_files": contour_files,
            "parse_note": "完整解析需要 CadnaA 后处理工具，当前仅返回文件路径和基本信息"
        })
    
    def get_metadata(self) -> Dict[str, Any]:
        """获取工具元数据"""
        metadata = super().get_metadata()
        metadata["cadnaa_available"] = self._cadnaa_exe is not None
        metadata["cadnaa_path"] = self._cadnaa_exe
        return metadata


# ============================================================
# 便捷函数
# ============================================================

def create_cadnaa_tool() -> CadnaATool:
    """创建 CadnaA 工具实例"""
    return CadnaATool()


def check_cadnaa_availability() -> Dict[str, Any]:
    """检查 CadnaA 可用性"""
    tool = CadnaATool()
    return {
        "available": tool._cadnaa_exe is not None,
        "exe_path": tool._cadnaa_exe,
        "note": "需要安装 DataKustik CadnaA 才能执行噪声预测"
    }


def create_noise_prediction_config(
    project_type: str,
    sound_sources: List[Dict],
    calculation_grid: Dict,
    terrain_file: Optional[str] = None
) -> Dict[str, Any]:
    """
    创建噪声预测配置（便捷函数）
    
    Args:
        project_type: 项目类型（industrial/transportation/construction）
        sound_sources: 声源列表 [{"x": 0, "y": 0, "Lw": 85}, ...]
        calculation_grid: 计算网格 {"x_min": 0, "y_min": 0, "x_max": 1000, "y_max": 1000, "dx": 10, "dy": 10}
        terrain_file: 地形文件路径（可选）
    
    Returns:
        配置字典，可直接传给 CadnaATool.execute()
    """
    return {
        "project_type": project_type,
        "sound_sources": sound_sources,
        "calculation_grid": calculation_grid,
        "terrain_file": terrain_file,
        "noise_indicators": ["Ld", "Leq", "Lnight"],
        "meteo_data": {
            "temperature": 20,
            "humidity": 70,
            "wind_speed": 2.0,
            "wind_dir": 0
        }
    }
