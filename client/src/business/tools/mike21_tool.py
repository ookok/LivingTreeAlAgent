"""
Mike21 水动力模型工具 (Mike21Tool)
==========================================

环评水动力模拟工具接口：
- 输入：水文数据、边界条件、网格文件
- 处理：准备Mike21输入文件 → 调用模型 → 解析输出
- 输出：水流场、水质浓度场、二维/三维结果

注意：Mike21 是 DHI 商业软件，此工具提供接口层。
实际执行需要安装 Mike21 或连接到计算集群。

支持的文件格式：
- 网格文件：.mesh (Mike21 格式）
- 边界条件：.bnd
- 参数文件：.m21fm
- 输出文件：.dfsu, .dfs2
"""

import os
import subprocess
import tempfile
from typing import Optional, Dict, Any, List
from pathlib import Path

from business.tools.base_tool import BaseTool
from business.tools.tool_result import ToolResult


# ============================================================
# Mike21Tool 主类
# ============================================================

class Mike21Tool(BaseTool):
    """
    Mike21 水动力模型工具

    支持模式（通过 mode 参数选择）：
    - hydrodynamic      : 水动力模拟
    - water_quality     : 水质模拟
    - particle_tracking : 粒子追踪
    - parse_output      : 解析已有输出文件（需 mikeio）

    使用方式：
    tool = Mike21Tool()
    result = tool.execute(mode="hydrodynamic", work_dir="/tmp/mike21")
    """

    def __init__(self):
        super().__init__(
            name="mike21_tool",
            description=(
                "Mike21 hydrodynamic and water quality model interface for EIA. "
                "Supports simulation type selection (hydrodynamic/water_quality/particle_tracking), "
                "input file generation (.m21fm), simulation execution, "
                "and output parsing (.dfsu/.dfs2 via mikeio)."
            ),
            category="environmental_simulation",
            tags=["water", "hydrodynamic", "Mike21", "DHI", "EIA", "mikeio"]
        )
        self._mike21_exe = self._find_mike21()
        self._mikeio_available = self._check_mikeio()

    def _check_mikeio(self) -> bool:
        try:
            import mikeio
            return True
        except ImportError:
            return False

    def _find_mike21(self) -> Optional[str]:
        """查找 Mike21 可执行文件"""
        possible_paths = [
            r"C:\Program Files\DHI\Mike21\bin\Mike21.exe",
            r"C:\Program Files (x86)\DHI\Mike21\bin\Mike21.exe",
            "/usr/local/dhi/mike21/bin/mike21",
        ]
        for path in possible_paths:
            if Path(path).exists():
                return path

        # 检查 PATH
        from shutil import which
        exe = which("Mike21") or which("mike21")
        if exe:
            return exe

        # 检查环境变量
        if "MIKE21_HOME" in os.environ:
            exe_path = Path(os.environ["MIKE21_HOME"]) / "bin" / "Mike21.exe"
            if exe_path.exists():
                return str(exe_path)

        return None

    def execute(self, **kwargs) -> ToolResult:
        """
        执行 Mike21 模拟或相关操作

        Args:
            mode: 操作模式 (hydrodynamic/water_quality/particle_tracking/parse_output)
            simulation_type: 模拟类型（传递给 .m21fm 配置）
            mesh_file: 网格文件路径（.mesh 或 .dfsu）
            boundary_conditions: 边界条件字典
            simulation_time: 模拟时间设置 {"start_time", "end_time", "dt"}
            output_variables: 输出变量列表
            model_exe_path: Mike21 可执行文件路径（可选）
            work_dir: 工作目录（可选）
            output_dir: 输出目录（用于 parse_output 模式）
        """
        mode = kwargs.get("mode", "hydrodynamic")

        if mode in ("hydrodynamic", "water_quality", "particle_tracking"):
            return self._run_simulation(kwargs)
        elif mode == "parse_output":
            return self._parse_output(kwargs)
        else:
            return ToolResult.fail(
                error="UNKNOWN_MODE",
                message=f"未知模式: {mode}，支持: hydrodynamic, water_quality, particle_tracking, parse_output"
            )

    def _run_simulation(self, params: Dict) -> ToolResult:
        """执行 Mike21 模拟"""
        simulation_type = params.get("simulation_type", "hydrodynamic")
        work_dir = params.get("work_dir", tempfile.mkdtemp(prefix="mike21_"))
        model_exe = params.get("model_exe_path", self._mike21_exe)

        if not model_exe or not Path(model_exe).exists():
            return ToolResult.fail(
                error="MIKE21_NOT_FOUND",
                message="Mike21 可执行文件未找到，请安装 Mike21 或设置 model_exe_path",
                data={"install_hint": "https://www.mikepoweredbydhi.com/products/mike-21"}
            )

        # 准备输入文件
        prepare_result = self._prepare_input_files(params, work_dir)
        if not prepare_result.success:
            return prepare_result

        input_file = prepare_result.data["input_file"]

        # 执行模拟
        try:
            cmd = [model_exe, "-input", input_file, "-workdir", work_dir]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,  # 1 小时超时
                cwd=work_dir
            )

            if result.returncode == 0:
                return ToolResult.ok(
                    data={
                        "returncode": 0,
                        "stdout": result.stdout[-2000:] if result.stdout else "",
                        "work_dir": work_dir,
                        "simulation_type": simulation_type,
                    },
                    message=f"Mike21 模拟完成（{simulation_type}），工作目录: {work_dir}"
                )
            else:
                return ToolResult.fail(
                    error="SIMULATION_FAILED",
                    message=f"Mike21 执行失败（返回码 {result.returncode}）: {result.stderr[:500]}",
                    data={"stdout": result.stdout[-1000:] if result.stdout else "",
                          "stderr": result.stderr[-1000:] if result.stderr else ""}
                )
        except subprocess.TimeoutExpired:
            return ToolResult.fail(
                error="SIMULATION_TIMEOUT",
                message="Mike21 模拟超时（>1小时）",
                data={"work_dir": work_dir}
            )
        except Exception as e:
            return ToolResult.fail(
                error="SIMULATION_ERROR",
                message=f"执行 Mike21 时出错: {e}"
            )

    def _prepare_input_files(self, inputs: Dict, work_dir: str) -> ToolResult:
        """准备 Mike21 输入文件（.m21fm 格式）"""
        try:
            work_path = Path(work_dir)
            work_path.mkdir(parents=True, exist_ok=True)

            simulation_type = inputs.get("simulation_type", "hydrodynamic")

            # 生成 .m21fm 配置文件
            config = self._generate_m21fm_config(inputs)
            input_file = work_path / f"{simulation_type}.m21fm"

            with open(input_file, "w", encoding="utf-8") as f:
                f.write(config)

            # 如果有网格文件，复制到工作目录
            mesh_file = inputs.get("mesh_file")
            if mesh_file and Path(mesh_file).exists():
                import shutil
                shutil.copy(mesh_file, work_path / Path(mesh_file).name)

            return ToolResult.ok(
                data={
                    "input_file": str(input_file),
                    "work_dir": work_dir
                }
            )
        except Exception as e:
            return ToolResult.fail(
                error="PREPARE_FAILED",
                message=f"准备输入文件失败: {e}"
            )

    def _generate_m21fm_config(self, inputs: Dict) -> str:
        """生成 Mike21 配置文件（.m21fm 简化格式）"""
        simulation_type = inputs.get("simulation_type", "hydrodynamic")
        simulation_time = inputs.get("simulation_time", {})

        lines = [
            "[MIKE21]",
            f"SimulationType = {simulation_type}",
            "",
            "[Time]",
            f"StartTime = {simulation_time.get('start_time', '2026-01-01 00:00:00')}",
            f"EndTime = {simulation_time.get('end_time', '2026-01-02 00:00:00')}",
            f"TimeStep = {simulation_time.get('dt', 60)}",
            "",
            "[Output]",
            f"OutputVariables = {','.join(inputs.get('output_variables', ['WaterLevel', 'CurrentSpeed']))}",
            "",
            "[BoundaryConditions]",
        ]

        # 添加边界条件
        bc = inputs.get("boundary_conditions", {})
        for name, value in bc.items():
            lines.append(f"{name} = {value}")

        return "\n".join(lines)

    def _parse_output(self, params: Dict) -> ToolResult:
        """解析 Mike21 输出文件（使用 mikeio）"""
        output_dir = params.get("output_dir", params.get("work_dir", "."))
        work_path = Path(output_dir)

        # 查找输出文件
        output_files = {
            "dfsu": list(work_path.glob("*.dfsu")),
            "dfs2": list(work_path.glob("*.dfs2")),
            "log": list(work_path.glob("*.log")),
        }

        result_data = {
            "output_files": {
                "dfsu": [str(f) for f in output_files["dfsu"]],
                "dfs2": [str(f) for f in output_files["dfs2"]],
                "log": [str(f) for f in output_files["log"]],
            }
        }

        # 使用 mikeio 解析（如果可用）
        if self._mikeio_available:
            try:
                import mikeio
                parsed = {}
                for dfsu_file in output_files["dfsu"]:
                    ds = mikeio.read(dfsu_file)
                    parsed[dfsu_file] = {
                        "variables": list(ds.data_vars) if hasattr(ds, "data_vars") else "unknown",
                        "shape": ds.shape if hasattr(ds, "shape") else "unknown",
                    }
                result_data["parsed"] = parsed
                result_data["mikeio_used"] = True
            except Exception as e:
                result_data["mikeio_error"] = str(e)
                result_data["mikeio_used"] = False
        else:
            result_data["mikeio_used"] = False
            result_data["mikeio_hint"] = "pip install mikeio 以解析 DFS 文件"

        # 解析日志文件（简化版）
        summary = {}
        for log_file in output_files["log"]:
            try:
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    log_content = f.read()
                    if "simulation completed" in log_content.lower():
                        summary["status"] = "completed"
                    else:
                        summary["status"] = "unknown"
            except Exception:
                pass
        result_data["summary"] = summary

        return ToolResult.ok(
            data=result_data,
            message=f"输出解析完成，DFS 文件: {len(output_files['dfsu'])} 个" +
                    ("" if self._mikeio_available else "（安装 mikeio 可深度解析）")
        )

    def get_metadata(self) -> Dict[str, Any]:
        """获取工具元数据"""
        metadata = super().get_metadata()
        metadata["mike21_available"] = self._mike21_exe is not None
        metadata["mike21_path"] = self._mike21_exe
        metadata["mikeio_available"] = self._mikeio_available
        return metadata


# ============================================================
# 便捷函数
# ============================================================

def create_mike21_tool() -> Mike21Tool:
    """创建 Mike21 工具实例"""
    return Mike21Tool()


def check_mike21_availability() -> Dict[str, Any]:
    """检查 Mike21 可用性"""
    tool = Mike21Tool()
    return {
        "mike21_available": tool._mike21_exe is not None,
        "mikeio_available": tool._mikeio_available,
        "exe_path": tool._mike21_exe,
        "note": "需要安装 DHI Mike21 才能执行模拟，pip install mikeio 可解析输出文件"
    }
