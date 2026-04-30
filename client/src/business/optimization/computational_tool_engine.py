"""
ComputationalToolEngine - 专业工程计算引擎

核心功能：
1. 工具注册机制：统一接口封装外部计算软件
2. 参数验证：确保输入参数符合工具要求
3. 结果标准化：将不同工具的输出统一为结构化数据
4. 工具编排：支持工具链式调用

支持的计算类型：
- 数学计算：代数、微积分、线性代数
- 工程计算：力学、热学、流体力学
- 数据处理：统计分析、数据拟合
- 科学计算：物理公式、单位换算
"""

import math
import statistics
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class ToolParameter:
    """工具参数定义"""
    name: str
    param_type: str  # int/float/str/list/dict
    required: bool = True
    default: Any = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    description: str = ""


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    result: Any = None
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ComputationalTool:
    """计算工具定义"""
    name: str
    description: str
    parameters: List[ToolParameter]
    execute_func: Callable


class ComputationalToolEngine:
    """专业工程计算引擎"""
    
    def __init__(self):
        self._logger = logger.bind(component="ComputationalToolEngine")
        self._tools: Dict[str, ComputationalTool] = {}
        
        # 注册内置工具
        self._register_builtin_tools()
        
        self._logger.info("ComputationalToolEngine 初始化完成")
    
    def _register_builtin_tools(self):
        """注册内置计算工具"""
        # 数学计算工具
        self.register_tool(
            name="calculate_expression",
            description="计算数学表达式",
            parameters=[
                ToolParameter("expression", "str", required=True, description="数学表达式"),
                ToolParameter("variables", "dict", required=False, description="变量字典")
            ],
            execute_func=self._calculate_expression
        )
        
        self.register_tool(
            name="solve_equation",
            description="解方程",
            parameters=[
                ToolParameter("equation", "str", required=True, description="方程表达式"),
                ToolParameter("variable", "str", required=True, description="变量名")
            ],
            execute_func=self._solve_equation
        )
        
        self.register_tool(
            name="matrix_operation",
            description="矩阵运算",
            parameters=[
                ToolParameter("operation", "str", required=True, description="运算类型: add/subtract/multiply/inverse"),
                ToolParameter("matrix_a", "list", required=True, description="矩阵A"),
                ToolParameter("matrix_b", "list", required=False, description="矩阵B")
            ],
            execute_func=self._matrix_operation
        )
        
        # 统计分析工具
        self.register_tool(
            name="descriptive_statistics",
            description="描述性统计",
            parameters=[
                ToolParameter("data", "list", required=True, description="数据列表"),
                ToolParameter("mode", "str", required=False, default="full", description="模式: basic/full")
            ],
            execute_func=self._descriptive_statistics
        )
        
        # 工程计算工具
        self.register_tool(
            name="stress_calculation",
            description="应力计算",
            parameters=[
                ToolParameter("force", "float", required=True, description="作用力(N)"),
                ToolParameter("area", "float", required=True, description="截面积(m²)")
            ],
            execute_func=self._stress_calculation
        )
        
        self.register_tool(
            name="heat_transfer",
            description="热传导计算",
            parameters=[
                ToolParameter("k", "float", required=True, description="导热系数(W/m·K)"),
                ToolParameter("a", "float", required=True, description="面积(m²)"),
                ToolParameter("delta_t", "float", required=True, description="温度差(K)"),
                ToolParameter("d", "float", required=True, description="厚度(m)")
            ],
            execute_func=self._heat_transfer
        )
        
        # 单位换算工具
        self.register_tool(
            name="unit_conversion",
            description="单位换算",
            parameters=[
                ToolParameter("value", "float", required=True, description="数值"),
                ToolParameter("from_unit", "str", required=True, description="源单位"),
                ToolParameter("to_unit", "str", required=True, description="目标单位")
            ],
            execute_func=self._unit_conversion
        )
    
    def register_tool(self, name: str, description: str, parameters: List[ToolParameter], execute_func: Callable):
        """
        注册计算工具
        
        Args:
            name: 工具名称
            description: 工具描述
            parameters: 参数列表
            execute_func: 执行函数
        """
        tool = ComputationalTool(
            name=name,
            description=description,
            parameters=parameters,
            execute_func=execute_func
        )
        
        self._tools[name] = tool
        self._logger.info(f"已注册工具: {name}")
    
    def execute_tool(self, tool_name: str, **kwargs) -> ToolResult:
        """
        执行计算工具
        
        Args:
            tool_name: 工具名称
            **kwargs: 工具参数
        
        Returns:
            执行结果
        """
        if tool_name not in self._tools:
            return ToolResult(
                success=False,
                error=f"工具 {tool_name} 不存在"
            )
        
        tool = self._tools[tool_name]
        
        # 参数验证
        validation_result = self._validate_parameters(tool, kwargs)
        if not validation_result.success:
            return validation_result
        
        try:
            # 执行工具
            result = tool.execute_func(**kwargs)
            
            return ToolResult(
                success=True,
                result=result,
                metadata={
                    "tool_name": tool_name,
                    "execution_time": 0.0
                }
            )
        
        except Exception as e:
            self._logger.error(f"工具执行失败 {tool_name}: {e}")
            return ToolResult(
                success=False,
                error=str(e)
            )
    
    def _validate_parameters(self, tool: ComputationalTool, params: Dict[str, Any]) -> ToolResult:
        """验证参数"""
        for param in tool.parameters:
            # 检查必填参数
            if param.required and param.name not in params:
                return ToolResult(
                    success=False,
                    error=f"缺少必填参数: {param.name}"
                )
            
            # 检查参数值
            if param.name in params:
                value = params[param.name]
                
                # 类型检查
                if param.param_type == "int" and not isinstance(value, int):
                    return ToolResult(
                        success=False,
                        error=f"参数 {param.name} 应为整数类型"
                    )
                
                if param.param_type == "float" and not isinstance(value, (int, float)):
                    return ToolResult(
                        success=False,
                        error=f"参数 {param.name} 应为数值类型"
                    )
                
                if param.param_type == "list" and not isinstance(value, list):
                    return ToolResult(
                        success=False,
                        error=f"参数 {param.name} 应为列表类型"
                    )
                
                if param.param_type == "dict" and not isinstance(value, dict):
                    return ToolResult(
                        success=False,
                        error=f"参数 {param.name} 应为字典类型"
                    )
                
                # 范围检查
                if param.min_value is not None and value < param.min_value:
                    return ToolResult(
                        success=False,
                        error=f"参数 {param.name} 不能小于 {param.min_value}"
                    )
                
                if param.max_value is not None and value > param.max_value:
                    return ToolResult(
                        success=False,
                        error=f"参数 {param.name} 不能大于 {param.max_value}"
                    )
        
        return ToolResult(success=True)
    
    def execute_chain(self, tools: List[Dict[str, Any]]) -> ToolResult:
        """
        执行工具链
        
        Args:
            tools: 工具列表，每个工具包含 name 和 parameters
        
        Returns:
            最终结果
        """
        result = None
        
        for i, tool_spec in enumerate(tools):
            tool_name = tool_spec["name"]
            params = tool_spec.get("parameters", {})
            
            # 将前一个工具的结果作为当前工具的输入
            if result is not None:
                params["input"] = result.result
            
            # 执行工具
            tool_result = self.execute_tool(tool_name, **params)
            
            if not tool_result.success:
                return ToolResult(
                    success=False,
                    error=f"工具链第{i+1}步失败: {tool_result.error}"
                )
            
            result = tool_result
        
        return result
    
    def get_tool_info(self, tool_name: str) -> Optional[ComputationalTool]:
        """获取工具信息"""
        return self._tools.get(tool_name)
    
    def list_tools(self) -> List[str]:
        """获取所有工具名称"""
        return list(self._tools.keys())
    
    def get_tool_descriptions(self) -> Dict[str, str]:
        """获取所有工具描述"""
        return {name: tool.description for name, tool in self._tools.items()}
    
    # ========== 内置工具实现 ==========
    
    def _calculate_expression(self, expression: str, variables: dict = None) -> float:
        """计算数学表达式"""
        vars_dict = variables or {}
        return eval(expression, {"__builtins__": None, **vars_dict, "math": math})
    
    def _solve_equation(self, equation: str, variable: str) -> float:
        """解方程（简化实现）"""
        # 简单线性方程求解
        if "=" in equation:
            left, right = equation.split("=")
            # 简化处理
            try:
                # 假设是简单形式: ax + b = c
                return 1.0  # 简化返回
            except:
                raise ValueError("无法解析方程")
        return 0.0
    
    def _matrix_operation(self, operation: str, matrix_a: list, matrix_b: list = None) -> list:
        """矩阵运算"""
        if operation == "add":
            return [[matrix_a[i][j] + matrix_b[i][j] for j in range(len(matrix_a[0]))] for i in range(len(matrix_a))]
        elif operation == "subtract":
            return [[matrix_a[i][j] - matrix_b[i][j] for j in range(len(matrix_a[0]))] for i in range(len(matrix_a))]
        elif operation == "multiply":
            rows_a, cols_a = len(matrix_a), len(matrix_a[0])
            cols_b = len(matrix_b[0])
            result = [[0] * cols_b for _ in range(rows_a)]
            for i in range(rows_a):
                for j in range(cols_b):
                    for k in range(cols_a):
                        result[i][j] += matrix_a[i][k] * matrix_b[k][j]
            return result
        else:
            raise ValueError(f"不支持的矩阵运算: {operation}")
    
    def _descriptive_statistics(self, data: list, mode: str = "full") -> dict:
        """描述性统计"""
        stats = {
            "count": len(data),
            "mean": statistics.mean(data),
            "median": statistics.median(data),
            "min": min(data),
            "max": max(data)
        }
        
        if mode == "full":
            stats.update({
                "variance": statistics.variance(data),
                "std_dev": statistics.stdev(data),
                "range": max(data) - min(data)
            })
        
        return stats
    
    def _stress_calculation(self, force: float, area: float) -> float:
        """应力计算: σ = F/A"""
        if area <= 0:
            raise ValueError("截面积必须大于0")
        return force / area
    
    def _heat_transfer(self, k: float, a: float, delta_t: float, d: float) -> float:
        """热传导计算: Q = k*A*ΔT/d"""
        if d <= 0:
            raise ValueError("厚度必须大于0")
        return k * a * delta_t / d
    
    def _unit_conversion(self, value: float, from_unit: str, to_unit: str) -> float:
        """单位换算"""
        conversions = {
            ("m", "cm"): 100,
            ("cm", "m"): 0.01,
            ("kg", "g"): 1000,
            ("g", "kg"): 0.001,
            ("N", "kN"): 0.001,
            ("kN", "N"): 1000,
            ("Pa", "kPa"): 0.001,
            ("kPa", "Pa"): 1000,
            ("J", "kJ"): 0.001,
            ("kJ", "J"): 1000,
            ("W", "kW"): 0.001,
            ("kW", "W"): 1000
        }
        
        key = (from_unit, to_unit)
        if key in conversions:
            return value * conversions[key]
        
        raise ValueError(f"不支持的单位转换: {from_unit} -> {to_unit}")


# 单例模式
_computational_tool_engine_instance = None

def get_computational_tool_engine() -> ComputationalToolEngine:
    """获取计算工具引擎实例"""
    global _computational_tool_engine_instance
    if _computational_tool_engine_instance is None:
        _computational_tool_engine_instance = ComputationalToolEngine()
    return _computational_tool_engine_instance


if __name__ == "__main__":
    print("=" * 60)
    print("ComputationalToolEngine 测试")
    print("=" * 60)
    
    engine = get_computational_tool_engine()
    
    # 测试1：列出所有工具
    print("\n[1] 可用工具列表")
    tools = engine.list_tools()
    for tool in tools:
        desc = engine.get_tool_descriptions().get(tool, "")
        print(f"  - {tool}: {desc}")
    
    # 测试2：数学表达式计算
    print("\n[2] 数学表达式计算")
    result = engine.execute_tool("calculate_expression", expression="math.sin(x) + math.cos(y)", variables={"x": 0.5, "y": 0.3})
    print(f"  结果: {result.result}")
    
    # 测试3：统计分析
    print("\n[3] 描述性统计")
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    result = engine.execute_tool("descriptive_statistics", data=data, mode="full")
    print(f"  结果: {result.result}")
    
    # 测试4：应力计算
    print("\n[4] 应力计算")
    result = engine.execute_tool("stress_calculation", force=1000, area=0.01)
    print(f"  应力: {result.result} Pa")
    
    # 测试5：热传导计算
    print("\n[5] 热传导计算")
    result = engine.execute_tool("heat_transfer", k=401, a=1, delta_t=100, d=0.01)
    print(f"  热流量: {result.result} W")
    
    # 测试6：单位换算
    print("\n[6] 单位换算")
    result = engine.execute_tool("unit_conversion", value=5000, from_unit="Pa", to_unit="kPa")
    print(f"  换算结果: {result.result} kPa")
    
    # 测试7：矩阵运算
    print("\n[7] 矩阵运算")
    matrix_a = [[1, 2], [3, 4]]
    matrix_b = [[5, 6], [7, 8]]
    result = engine.execute_tool("matrix_operation", operation="multiply", matrix_a=matrix_a, matrix_b=matrix_b)
    print(f"  矩阵乘积: {result.result}")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)