"""
Mike21 水动力模型工具 (Mike21Tool)
========================================

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
import json

from client.src.business.tools.base_tool import BaseTool
from client.src.business.tools.tool_definition import ToolDefinition, ToolParameter
from client.src.business.tools.tool_result import ToolResult, SUCCESS, ERROR


# ============================================================
# Mike21 工具参数定义
# ============================================================

MIKE21_TOOL_DEF = ToolDefinition(
    name="mike21_tool",
    description="Mike21 水动力和水质模型接口（环评水影响预测）",
    category="simulation",
    parameters=[
        ToolParameter("simulation_type", "string", "模拟类型：hydrodynamic/water_quality/particle_tracking", required=True),
        ToolParameter("mesh_file", "string", "网格文件路径（.mesh 或 .dfsu）", required=False),
        ToolParameter("boundary_conditions", "object", "边界条件字典", required=False),
        ToolParameter("simulation_time", "object", "模拟时间设置（start_time, end_time, dt）", required=False),
        ToolParameter("output_variables", "array", "输出变量列表", required=False),
        ToolParameter("model_exe_path", "string", "Mike21 可执行文件路径（可选）", required=False),
        ToolParameter("work_dir", "string", "工作目录（可选）", required=False),
    ],
    returns={
        "success": "是否成功",
        "data": "模拟结果（路径或解析后的数据）",
        "output_files": "输出文件列表",
        "summary": "模拟摘要"
    },
    error_codes={
        "MESH_NOT_FOUND": "网格文件不存在",
        "MIKE21_NOT_FOUND": "Mike21 可执行文件未找到",
        "SIMULATION_FAILED": "模拟执行失败",
        "OUTPUT_NOT_FOUND": "输出文件未找到"
    }
)


# ============================================================
# Mike21 工具实现
# ============================================================

class Mike21Tool(BaseTool):
    """
    Mike21 水动力模型工具
    
    功能：
    - 准备 Mike21 输入文件（.m21fm 格式）
    - 调用 Mike21 执行模拟
    - 解析输出文件（.dfsu, .dfs2）
    - 生成标准化结果
    
    使用方式：
    1. 本地安装 Mike21：直接调用
    2. 远程集群：通过 SSH 提交作业
    3. 输出解析：读取 DFS 文件
    """
    
    def __init__(self):
        super().__init__(MIKE21_TOOL_DEF)
        self._mike21_exe = self._find_mike21()
    
    def _find_mike21(self) -> Optional[str]:
        """查找 Mike21 可执行文件"""
        # 常见安装路径
        possible_paths = [
            r"C:\Program Files\DHI\MIKE21\bin\Mike21.exe",
            r"C:\Program Files (x86)\DHI\MIKE21\bin\Mike21.exe",
            "/usr/local/dhi/mike21/bin/Mike21",
        ]
        
        for path in possible_paths:
            if Path(path).exists():
                return path
        
        # 检查环境变量
        import os
        if "MIKE21_HOME" in os.environ:
            exe_path = Path(os.environ["MIKE21_HOME"]) / "bin" / "Mike21.exe"
            if exe_path.exists():
                return str(exe_path)
        
        return None
    
    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行 Mike21 模拟"""
        simulation_type = inputs.get("simulation_type", "hydrodynamic")
        work_dir = inputs.get("work_dir", tempfile.mkdtemp(prefix="mike21_"))
        model_exe = inputs.get("model_exe_path", self._mike21_exe)
        
        if not model_exe or not Path(model_exe).exists():
            return ERROR(
                error="MIKE21_NOT_FOUND",
                message="Mike21 可执行文件未找到，请安装 Mike21 或设置 model_exe_path"
            ).to_dict()
        
        # 准备输入文件
        prepare_result = self._prepare_input_files(inputs, work_dir)
        if not prepare_result.success:
            return prepare_result.to_dict()
        
        input_file = prepare_result.data["input_file"]
        
        # 执行模拟
        run_result = self._run_simulation(model_exe, input_file, work_dir)
        if not run_result.success:
            return run_result.to_dict()
        
        # 解析输出
        parse_result = self._parse_output(work_dir, inputs.get("output_variables"))
        return parse_result.to_dict()
    
    def _prepare_input_files(self, inputs: Dict[str, Any], work_dir: str) -> ToolResult:
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
            
            return SUCCESS(data={
                "input_file": str(input_file),
                "work_dir": work_dir
            })
        except Exception as e:
            return ERROR(
                error="PREPARE_FAILED",
                message=f"准备输入文件失败: {e}"
            )
    
    def _generate_m21fm_config(self, inputs: Dict[str, Any]) -> str:
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
    
    def _run_simulation(self, exe_path: str, input_file: str,
                       work_dir: str) -> ToolResult:
        """执行 Mike21 模拟"""
        try:
            cmd = [exe_path, "-input", input_file, "-workdir", work_dir]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,  # 1 小时超时
                cwd=work_dir
            )
            
            if result.returncode == 0:
                return SUCCESS(data={
                    "returncode": 0,
                    "stdout": result.stdout[-1000:] if result.stdout else "",  # 截断
                    "work_dir": work_dir
                })
            else:
                return ERROR(
                    error="SIMULATION_FAILED",
                    message=f"Mike21 执行失败（返回码 {result.returncode}）: {result.stderr[:500]}"
                )
        except subprocess.TimeoutExpired:
            return ERROR(
                error="SIMULATION_TIMEOUT",
                message="Mike21 模拟超时（>1小时）"
            )
        except Exception as e:
            return ERROR(
                error="SIMULATION_ERROR",
                message=f"执行 Mike21 时出错: {e}"
            )
    
    def _parse_output(self, work_dir: str,
                     output_variables: Optional[List[str]]) -> ToolResult:
        """解析 Mike21 输出文件"""
        work_path = Path(work_dir)
        
        # 查找输出文件
        output_files = {
            "dfsu": list(work_path.glob("*.dfsu")),
            "dfs2": list(work_path.glob("*.dfs2")),
            "log": list(work_path.glob("*.log")),
        }
        
        # 解析日志文件（简化版）
        summary = {}
        for log_file in output_files["log"]:
            try:
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    log_content = f.read()
                    # 提取关键信息（简化）
                    if "simulation completed" in log_content.lower():
                        summary["status"] = "completed"
                    else:
                        summary["status"] = "unknown"
            except Exception:
                pass
        
        # TODO: 使用 mikeio 库解析 DFS 文件
        # import mikeio
        # ds = mikeio.read("output.dfsu")
        
        return SUCCESS(data={
            "output_files": {
                "dfsu": [str(f) for f in output_files["dfsu"]],
                "dfs2": [str(f) for f in output_files["dfs2"]],
                "log": [str(f) for f in output_files["log"]],
            },
            "summary": summary,
            "parse_note": "完整解析需要 mikeio 库，当前仅返回文件路径"
        })
    
    def validate_inputs(self, inputs: Dict[str, Any]) -> Optional[str]:
        """验证输入参数"""
        simulation_type = inputs.get("simulation_type", "")
        if simulation_type not in ["hydrodynamic", "water_quality", "particle_tracking"]:
            return f"不支持的模拟类型: {simulation_type}"
        
        mesh_file = inputs.get("mesh_file")
        if mesh_file and not Path(mesh_file).exists():
            return f"网格文件不存在: {mesh_file}"
        
        return None
    
    def get_metadata(self) -> Dict[str, Any]:
        """获取工具元数据"""
        metadata = super().get_metadata()
        metadata["mike21_available"] = self._mike21_exe is not None
        metadata["mike21_path"] = self._mike21_exe
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
        "available": tool._mike21_exe is not None,
        "exe_path": tool._mike21_exe,
        "note": "需要安装 DHI Mike21 才能执行模拟"
    }
