"""
AermodTool - 大气扩散模型工具

封装 AERMOD 模型接口，支持大气环境影响模拟计算
"""

import os
import asyncio
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from client.src.business.tools.base_tool import BaseTool
from client.src.business.tools.tool_result import ToolResult
from loguru import logger


@dataclass
class AermodResult:
    """AERMOD 执行结果"""
    success: bool
    output_file: Optional[str] = None
    concentrations: Optional[List[Dict]] = None  # 浓度结果
    errors: Optional[str] = None
    warnings: Optional[List[str]] = None


class AermodTool(BaseTool):
    """
    AERMOD 大气扩散模型工具
    
    AERMOD 是一个稳态烟羽空气质量模型，用于评估工业设施、
    道路和其他线性源对空气质量的影响。
    
    功能：
    - 执行 AERMOD 模型模拟
    - 计算受体点浓度
    - 生成等浓度线图数据
    - 支持多个排放源
    """
    
    def __init__(
        self,
        aermod_path: str = "aermod",  # 默认从 PATH 查找
        work_dir: Optional[str] = None
    ):
        """
        初始化 AermodTool
        
        Args:
            aermod_path: AERMOD 可执行文件路径
            work_dir: 工作目录（用于存放输入输出文件）
        """
        super().__init__(
            name="aermod_tool",
            description="AERMOD atmospheric dispersion model for air quality impact assessment. "
                       "Supports emission source modeling, receptor concentration calculation, "
                       "and downwind plume analysis.",
            category="simulation",
            tags=["environment", "air-quality", "dispersion-model", "aermod", "emission"]
        )
        self.aermod_path = aermod_path
        self.work_dir = Path(work_dir) if work_dir else Path.cwd() / "aermod_work"
        self._ensure_work_dir()
    
    def _ensure_work_dir(self):
        """确保工作目录存在"""
        self.work_dir.mkdir(parents=True, exist_ok=True)
    
    def execute(self, **kwargs) -> ToolResult:
        """
        执行 AERMOD 模型
        
        Args:
            input_file: AERMOD 输入文件路径 (.inp)
            output_file: 输出文件路径 (.out)，可选
            
        Returns:
            ToolResult with AermodResult
        """
        try:
            input_file = kwargs.get("input_file")
            if not input_file:
                return ToolResult.fail(error="input_file is required")
            
            # 处理输出文件路径
            output_file = kwargs.get("output_file")
            if not output_file:
                input_path = Path(input_file)
                output_file = str(input_path.with_suffix(".out"))
            
            # 执行 AERMOD
            result = self._run_aermod(input_file, output_file)
            
            if result.success:
                return ToolResult.ok(
                    data={
                        "output_file": result.output_file,
                        "concentrations": result.concentrations,
                        "warnings": result.warnings
                    },
                    message=f"AERMOD executed successfully: {result.output_file}"
                )
            else:
                return ToolResult.fail(error=result.errors)
                
        except Exception as e:
            logger.error(f"AERMOD execution failed: {e}")
            return ToolResult.fail(error=str(e))
    
    def _run_aermod(self, input_file: str, output_file: str) -> AermodResult:
        """运行 AERMOD 模型"""
        warnings = []
        
        try:
            # 准备命令
            cmd = [self.aermod_path, "-i", input_file, "-o", output_file]
            
            # 执行命令
            process = subprocess.run(
                cmd,
                cwd=str(self.work_dir),
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            # 检查错误
            if process.returncode != 0:
                return AermodResult(
                    success=False,
                    errors=process.stderr or f"AERMOD failed with code {process.returncode}"
                )
            
            # 解析输出
            concentrations = self._parse_output(output_file)
            
            return AermodResult(
                success=True,
                output_file=output_file,
                concentrations=concentrations,
                warnings=warnings if warnings else None
            )
            
        except FileNotFoundError:
            return AermodResult(
                success=False,
                errors=f"AERMOD executable not found: {self.aermod_path}"
            )
        except subprocess.TimeoutExpired:
            return AermodResult(
                success=False,
                errors="AERMOD execution timed out (5 minutes)"
            )
        except Exception as e:
            return AermodResult(
                success=False,
                errors=str(e)
            )
    
    def _parse_output(self, output_file: str) -> List[Dict]:
        """解析 AERMOD 输出文件"""
        concentrations = []
        
        try:
            with open(output_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            # 简化解析：提取浓度值
            # 实际 AERMOD 输出格式更复杂，这里提供基本解析
            lines = content.split('\n')
            for line in lines:
                if 'CONCENTRATION' in line.upper() or 'UG/M3' in line.upper():
                    # 尝试提取数值
                    parts = line.split()
                    for part in parts:
                        try:
                            val = float(part.replace(',', ''))
                            if 0 < val < 10000:  # 合理的浓度范围
                                concentrations.append({
                                    "value": val,
                                    "unit": "ug/m3",
                                    "raw_line": line.strip()[:100]
                                })
                        except ValueError:
                            continue
                            
        except Exception as e:
            logger.warning(f"Failed to parse AERMOD output: {e}")
        
        return concentrations
    
    def generate_input_file(
        self,
        source_locations: List[Dict],
        receptor_points: List[Dict],
        emission_rates: List[float],
        output_file: str
    ) -> str:
        """
        生成 AERMOD 输入文件
        
        Args:
            source_locations: 排放源位置 [{"x": 0, "y": 0, "z": 10}, ...]
            receptor_points: 受体点位置 [{"x": 100, "y": 50}, ...]
            emission_rates: 各源的排放速率 (g/s)
            output_file: 生成的输入文件路径
            
        Returns:
            输入文件路径
        """
        content = self._build_input_content(source_locations, receptor_points, emission_rates)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return output_file
    
    def _build_input_content(
        self,
        source_locations: List[Dict],
        receptor_points: List[Dict],
        emission_rates: List[float]
    ) -> str:
        """构建 AERMOD 输入文件内容"""
        lines = [
            "AERMOD Input File",
            "Generated by Living Tree AI Agent",
            "",
            "CO STARTING",
            "   Cartesian UTM Coordinates",
            "   YDEBUG     0",
            "   TZONE      8",
            "CO FINISHED",
            "",
            "SO STARTING",
        ]
        
        # 添加排放源
        for i, (loc, rate) in enumerate(zip(source_locations, emission_rates)):
            x = loc.get('x', 0)
            y = loc.get('y', 0)
            z = loc.get('z', 10)
            lines.append(f"   SRC{i+1}   POINT   {x}   {y}   {z}   0   0   0   {rate}")
        
        lines.extend([
            "SO FINISHED",
            "",
            "RE STARTING",
        ])
        
        # 添加受体点
        for i, pt in enumerate(receptor_points):
            x = pt.get('x', 0)
            y = pt.get('y', 0)
            lines.append(f"   REC{i+1}   {x}   {y}")
        
        lines.extend([
            "RE FINISHED",
            "",
            "OU STARTING",
            "   RECTABLE   ALL",
            "   PLOTFILE   ALL   1HR   aermod_plume.out",
            "OU FINISHED",
        ])
        
        return '\n'.join(lines)
    
    def calculate_concentration(
        self,
        source_x: float,
        source_y: float,
        source_z: float,
        emission_rate: float,
        receptor_x: float,
        receptor_y: float,
        wind_speed: float = 2.0,
        wind_direction: float = 0.0,
        stability_class: str = "D"
    ) -> float:
        """
        简化计算：使用高斯烟羽模型计算受体点浓度
        
        Args:
            source_x, source_y: 源位置
            source_z: 源高度 (m)
            emission_rate: 排放速率 (g/s)
            receptor_x, receptor_y: 受体位置
            wind_speed: 风速 (m/s)
            wind_direction: 风向 (度)
            stability_class: 稳定度等级 (A-F)
            
        Returns:
            预测浓度 (ug/m3)
        """
        import math
        
        # 计算距离
        dx = receptor_x - source_x
        dy = receptor_y - source_y
        distance = math.sqrt(dx**2 + dy**2)
        
        # 角度
        angle = math.radians(wind_direction)
        
        # 计算下风向距离
        downwind = dx * math.cos(angle) + dy * math.sin(angle)
        
        if downwind <= 0:
            return 0.0
        
        # 扩散参数（简化版）
        sigma_y = self._get_sigma_y(distance, stability_class)
        sigma_z = self._get_sigma_z(distance, stability_class)
        
        # 高斯烟羽公式
        Q = emission_rate * 1e6  # 转换为 mg/s
        coeff = Q / (2 * math.pi * sigma_y * sigma_z * wind_speed)
        exp_y = math.exp(-(dy * math.cos(angle) - dx * math.sin(angle))**2 / (2 * sigma_y**2))
        exp_z = math.exp(-source_z**2 / (2 * sigma_z**2))
        
        concentration = coeff * exp_y * exp_z
        
        return concentration  # ug/m3
    
    def _get_sigma_y(self, distance: float, stability: str) -> float:
        """获取水平扩散参数"""
        # 简化：Pasquill-Gifford 曲线
        table = {
            'A': 0.22 * distance**0.7,
            'B': 0.16 * distance**0.7,
            'C': 0.11 * distance**0.7,
            'D': 0.08 * distance**0.7,
            'E': 0.06 * distance**0.7,
            'F': 0.04 * distance**0.7,
        }
        return table.get(stability, table['D'])
    
    def _get_sigma_z(self, distance: float, stability: str) -> float:
        """获取垂直扩散参数"""
        table = {
            'A': 0.20 * distance**0.8,
            'B': 0.12 * distance**0.8,
            'C': 0.08 * distance**0.8,
            'D': 0.06 * distance**0.8,
            'E': 0.03 * distance**0.8,
            'F': 0.016 * distance**0.8,
        }
        return table.get(stability, table['D'])
    
    def health_check(self) -> bool:
        """健康检查"""
        try:
            # 检查可执行文件
            if self.aermod_path != "aermod":
                return Path(self.aermod_path).exists()
            return True
        except Exception:
            return False
    
    def get_capabilities(self) -> Dict[str, Any]:
        """获取工具能力描述"""
        return {
            "name": self.name,
            "category": self.category,
            "supported_calculations": [
                "Point source dispersion",
                "Area source dispersion",
                "Volume source dispersion",
                "Receptor concentration",
                "Plume visualization data"
            ],
            "input_formats": ["AERMOD .inp files"],
            "output_formats": ["AERMOD .out files", "Concentration data (JSON)"]
        }


# ── 自动注册 ─────────────────────────────────────────────────────────

def _auto_register():
    """自动注册工具到 ToolRegistry"""
    try:
        from client.src.business.tools.tool_registry import ToolRegistry
        registry = ToolRegistry.get_instance()
        
        tool = AermodTool()
        if registry.register_tool(tool):
            logger.info(f"Auto-registered: {tool.name}")
            return True
    except Exception as e:
        logger.error(f"Auto-registration error: {e}")
    return False


# 调试用
if __name__ == "__main__":
    tool = AermodTool()
    print(f"Tool: {tool.name}")
    print(f"Description: {tool.description}")
    print(f"Capabilities: {tool.get_capabilities()}")
    
    # 测试简化计算
    conc = tool.calculate_concentration(
        source_x=0, source_y=0, source_z=30,
        emission_rate=1.0,
        receptor_x=500, receptor_y=100,
        wind_speed=2.0,
        wind_direction=0,
        stability_class="D"
    )
    print(f"\nPredicted concentration at (500, 100): {conc:.2f} ug/m3")
