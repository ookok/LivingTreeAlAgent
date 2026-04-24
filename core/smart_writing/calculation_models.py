# -*- coding: utf-8 -*-
"""
智能写作计算模型库 - Smart Writing Calculation Models (Enhanced)
===============================================================

设计原则：
1. 优先复用系统已有计算引擎（EIA系统、CLIAnything等）
2. 通过外部CLI调用计算工具，不重复造轮子
3. 支持动态注册外部计算模块
4. 提供统一接口，屏蔽底层实现差异

依赖的现有模块：
- core/living_tree_ai/eia_system/calculation_engine.py  → EIA环境计算
- core/cli_anything.py   → 动态生成/调用CLI计算工具
- core/skill_evolution/  → 计算过程自进化

Author: Hermes Desktop Team
"""

import asyncio
import importlib
import json
import logging
import math
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# 计算结果数据模型
# =============================================================================

@dataclass
class CalcResult:
    """计算结果"""
    model_name: str
    result_value: Any
    unit: str = ""
    formula: str = ""
    inputs: Dict[str, Any] = field(default_factory=dict)
    details: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: str = ""
    source: str = "builtin"          # builtin / eia_engine / cli_tool / external

    def to_dict(self) -> Dict:
        return {
            "model": self.model_name,
            "result": self.result_value,
            "unit": self.unit,
            "formula": self.formula,
            "inputs": self.inputs,
            "details": self.details,
            "success": self.success,
            "error": self.error,
            "source": self.source,
        }

    def to_markdown(self) -> str:
        """转为Markdown摘要"""
        if not self.success:
            return f"**{self.model_name}** ❌ 计算失败：{self.error}"
        lines = [f"**{self.model_name}** = `{self.result_value} {self.unit}`"]
        if self.formula:
            lines.append(f"\n公式：{self.formula}")
        if self.details:
            lines.append("\n| 参数 | 值 |")
            lines.append("| --- | --- |")
            for k, v in self.details.items():
                lines.append(f"| {k} | {v} |")
        return "\n".join(lines)


# =============================================================================
# 基础计算器接口
# =============================================================================

class BaseCalculator(ABC):
    """所有计算器的基类"""

    model_name: str = "base"
    category: str = "generic"
    description: str = ""

    @abstractmethod
    def calculate(self, params: Dict[str, Any]) -> CalcResult:
        """执行计算"""

    def validate(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        """参数校验，返回 (是否通过, 错误信息)"""
        return True, ""


# =============================================================================
# ① 财务计算器组（内置，无需外部依赖）
# =============================================================================

class NPVCalculator(BaseCalculator):
    """净现值 NPV 计算"""
    model_name = "NPV"
    category = "financial"
    description = "净现值 = 各年现金流折现之和 - 初始投资"

    def calculate(self, params: Dict[str, Any]) -> CalcResult:
        try:
            investment = float(params.get("initial_investment", 0))
            cashflows = [float(v) for v in params.get("annual_cashflows", [])]
            rate = float(params.get("discount_rate", 8)) / 100.0

            if not cashflows:
                return CalcResult(self.model_name, None, success=False, error="缺少年度现金流参数")

            pv_sum = sum(cf / (1 + rate) ** (i + 1) for i, cf in enumerate(cashflows))
            npv = pv_sum - investment

            details = {f"第{i+1}年现金流折现": f"{cf/(1+rate)**(i+1):.2f} 万元"
                       for i, cf in enumerate(cashflows)}
            details["现金流现值合计"] = f"{pv_sum:.2f} 万元"

            return CalcResult(
                model_name=self.model_name,
                result_value=round(npv, 2),
                unit="万元",
                formula="NPV = Σ[CFt/(1+r)^t] - I₀",
                inputs=params,
                details=details,
                source="builtin"
            )
        except Exception as e:
            return CalcResult(self.model_name, None, success=False, error=str(e))


class IRRCalculator(BaseCalculator):
    """内部收益率 IRR 计算"""
    model_name = "IRR"
    category = "financial"
    description = "使NPV=0的折现率"

    def calculate(self, params: Dict[str, Any]) -> CalcResult:
        try:
            investment = float(params.get("initial_investment", 0))
            cashflows = [float(v) for v in params.get("annual_cashflows", [])]
            all_flows = [-investment] + cashflows

            # 牛顿迭代法
            r = 0.1
            for _ in range(1000):
                npv = sum(cf / (1 + r) ** i for i, cf in enumerate(all_flows))
                d_npv = sum(-i * cf / (1 + r) ** (i + 1) for i, cf in enumerate(all_flows))
                if abs(d_npv) < 1e-12:
                    break
                r_new = r - npv / d_npv
                if abs(r_new - r) < 1e-8:
                    r = r_new
                    break
                r = r_new

            irr_pct = round(r * 100, 2)
            return CalcResult(
                model_name=self.model_name,
                result_value=irr_pct,
                unit="%",
                formula="使 NPV=0 的折现率 r",
                inputs=params,
                source="builtin"
            )
        except Exception as e:
            return CalcResult(self.model_name, None, success=False, error=str(e))


class PaybackCalculator(BaseCalculator):
    """投资回收期计算"""
    model_name = "投资回收期"
    category = "financial"
    description = "累计净现金流由负变正的时间点"

    def calculate(self, params: Dict[str, Any]) -> CalcResult:
        try:
            investment = float(params.get("initial_investment", 0))
            cashflows = [float(v) for v in params.get("annual_cashflows", [])]

            cumulative = -investment
            for i, cf in enumerate(cashflows):
                if cumulative + cf >= 0:
                    years = i + (-cumulative / cf)
                    return CalcResult(
                        model_name=self.model_name,
                        result_value=round(years, 2),
                        unit="年",
                        formula="累计现金流=0 时的年数",
                        inputs=params,
                        details={"到第{}年末累计".format(i): f"{cumulative:.2f} 万元"},
                        source="builtin"
                    )
                cumulative += cf

            return CalcResult(self.model_name, ">项目期", unit="年", inputs=params, source="builtin")
        except Exception as e:
            return CalcResult(self.model_name, None, success=False, error=str(e))


class SensitivityCalculator(BaseCalculator):
    """敏感性分析"""
    model_name = "敏感性分析"
    category = "financial"
    description = "关键参数变动对NPV/IRR的影响程度"

    def calculate(self, params: Dict[str, Any]) -> CalcResult:
        try:
            base_npv = float(params.get("base_npv", 0))
            factors = params.get("factors", {"投资额": -5000, "收入": 8000, "成本": -3000})
            variation = float(params.get("variation_pct", 10)) / 100.0

            sensitivities = {}
            for factor_name, base_val in factors.items():
                delta_val = base_val * variation
                # 简化：假设NPV对各因素的弹性估算
                sensitivity_ratio = abs(delta_val / (base_npv if base_npv != 0 else 1)) * 100
                sensitivities[factor_name] = f"{sensitivity_ratio:.1f}%"

            return CalcResult(
                model_name=self.model_name,
                result_value=sensitivities,
                unit="",
                formula=f"各因素变动±{variation*100:.0f}%时NPV变化率",
                inputs=params,
                details=sensitivities,
                source="builtin"
            )
        except Exception as e:
            return CalcResult(self.model_name, None, success=False, error=str(e))


# =============================================================================
# ② EIA环境计算器组（复用 eia_system/calculation_engine.py）
# =============================================================================

class EIAEngineProxy(BaseCalculator):
    """
    EIA 计算引擎代理
    复用 core/living_tree_ai/eia_system/calculation_engine.py
    """
    model_name = "EIA计算引擎"
    category = "environmental"
    description = "大气扩散/噪声/水质等EIA计算，复用现有EIA引擎"

    def __init__(self):
        self._engine = None

    def _get_engine(self):
        if self._engine is None:
            try:
                sys.path.insert(0, str(Path(__file__).parents[2]))
                from core.living_tree_ai.eia_system.calculation_engine import ModelCalculationEngine
                self._engine = ModelCalculationEngine()
                logger.info("EIA ModelCalculationEngine 加载成功")
            except ImportError as e:
                logger.warning(f"EIA引擎不可用: {e}")
                self._engine = None
        return self._engine

    def calculate(self, params: Dict[str, Any]) -> CalcResult:
        engine = self._get_engine()
        if engine is None:
            # 降级：内置简化高斯模型
            return self._fallback_gaussian(params)

        try:
            # 异步调用同步包装
            from core.living_tree_ai.eia_system.calculation_engine import (
                ComputationInput, ModelType, ModelParameter
            )
            model_type_str = params.get("model_type", "gaussian_plume")
            model_type = ModelType(model_type_str)

            inp = ComputationInput(model_type=model_type, project_id=params.get("project_id", "auto"))
            for k, v in params.get("parameters", {}).items():
                inp.parameters[k] = ModelParameter(name=k, value=v)
            inp.sources = params.get("sources", [])

            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(engine.calculate(inp))
            loop.close()

            return CalcResult(
                model_name=f"EIA-{model_type_str}",
                result_value=result.processed_output,
                unit=params.get("unit", "mg/m³"),
                inputs=params,
                details=result.raw_output or {},
                source="eia_engine"
            )
        except Exception as e:
            logger.error(f"EIA引擎调用失败: {e}")
            return self._fallback_gaussian(params)

    def _fallback_gaussian(self, params: Dict[str, Any]) -> CalcResult:
        """降级：简化高斯烟羽模型"""
        Q = float(params.get("parameters", {}).get("emission_rate", 0.5))   # g/s
        u = float(params.get("parameters", {}).get("wind_speed", 2.0))      # m/s
        H = float(params.get("parameters", {}).get("stack_height", 15.0))   # m
        x = float(params.get("predict_distance", 500))                       # m

        sy = 0.22 * x * (1 + 0.0001 * x) ** -0.5
        sz = 0.16 * x * (1 + 0.0001 * x) ** -0.5
        sz = max(sz, 1.0)

        C = (Q / (math.pi * sy * sz * u)) * math.exp(-H**2 / (2 * sz**2))
        C_ug = C * 1000  # g/m³ → ug/m³

        return CalcResult(
            model_name="高斯烟羽(简化)",
            result_value=round(C_ug, 4),
            unit="ug/m³",
            formula="C = Q/(π·σy·σz·u) · exp(-H²/2σz²)",
            inputs=params,
            details={"σy": round(sy, 2), "σz": round(sz, 2), "距离": f"{x}m"},
            source="builtin_fallback"
        )


class EmissionCalculator(BaseCalculator):
    """污染物排放量核算"""
    model_name = "排放量核算"
    category = "environmental"
    description = "根据活动水平和排放因子核算污染物排放量"

    def calculate(self, params: Dict[str, Any]) -> CalcResult:
        try:
            activity = float(params.get("activity_level", 0))     # 活动水平（如产量t/a）
            factor = float(params.get("emission_factor", 0))       # 排放因子（kg/t）
            efficiency = float(params.get("removal_efficiency", 0)) / 100.0  # 去除效率%

            gross = activity * factor / 1000.0   # kg → t/a
            net = gross * (1 - efficiency)

            return CalcResult(
                model_name=self.model_name,
                result_value=round(net, 4),
                unit="t/a",
                formula="E = A × EF × (1-η)",
                inputs=params,
                details={"有组织排放量": f"{net:.4f} t/a", "污染物去除量": f"{gross-net:.4f} t/a"},
                source="builtin"
            )
        except Exception as e:
            return CalcResult(self.model_name, None, success=False, error=str(e))


class CarbonFootprintCalculator(BaseCalculator):
    """碳足迹计算"""
    model_name = "碳足迹"
    category = "environmental"
    description = "基于IPCC排放因子核算温室气体排放量"

    # 常见排放因子 tCO2/单位
    EMISSION_FACTORS = {
        "electricity": 0.581,   # tCO2/MWh (华中电网2023)
        "coal": 2.66,           # tCO2/t
        "natural_gas": 2.16,    # tCO2/1000m³
        "diesel": 2.63,         # tCO2/t
        "gasoline": 2.30,       # tCO2/t
    }

    def calculate(self, params: Dict[str, Any]) -> CalcResult:
        try:
            energy = params.get("energy_consumption", {})
            total_co2 = 0.0
            breakdown = {}
            for fuel, amount in energy.items():
                factor = self.EMISSION_FACTORS.get(fuel, params.get("custom_factor", {}).get(fuel, 0))
                co2 = float(amount) * factor
                total_co2 += co2
                breakdown[fuel] = f"{co2:.2f} tCO₂"

            return CalcResult(
                model_name=self.model_name,
                result_value=round(total_co2, 2),
                unit="tCO₂/a",
                formula="GHG = Σ(活动量 × 排放因子)",
                inputs=params,
                details=breakdown,
                source="builtin"
            )
        except Exception as e:
            return CalcResult(self.model_name, None, success=False, error=str(e))


# =============================================================================
# ③ 安全计算器组
# =============================================================================

class LSRiskCalculator(BaseCalculator):
    """LS法风险评价（可能性×严重性）"""
    model_name = "LS风险评价"
    category = "safety"
    description = "风险值R=L(可能性)×S(严重性)"

    RISK_LEVEL = {(1, 3): "低风险", (4, 9): "一般风险", (10, 20): "中等风险",
                  (21, 50): "高风险", (51, 9999): "重大风险"}

    def calculate(self, params: Dict[str, Any]) -> CalcResult:
        try:
            L = int(params.get("likelihood", 3))   # 可能性 1-5
            S = int(params.get("severity", 3))      # 严重性 1-5
            R = L * S
            level = next((v for (lo, hi), v in self.RISK_LEVEL.items() if lo <= R <= hi), "未定级")
            return CalcResult(
                model_name=self.model_name,
                result_value=R,
                unit="",
                formula="R = L × S",
                inputs=params,
                details={"L(可能性)": L, "S(严重性)": S, "风险等级": level},
                source="builtin"
            )
        except Exception as e:
            return CalcResult(self.model_name, None, success=False, error=str(e))


class LECRiskCalculator(BaseCalculator):
    """LEC法作业条件危险性分析"""
    model_name = "LEC风险评价"
    category = "safety"
    description = "D=L(发生可能性)×E(暴露频率)×C(后果)"

    RISK_LEVEL = [(320, 9999, "极度危险"), (160, 319, "高度危险"),
                  (70, 159, "显著危险"), (20, 69, "一般危险"), (0, 19, "稍有危险")]

    def calculate(self, params: Dict[str, Any]) -> CalcResult:
        try:
            L = float(params.get("likelihood", 1))      # 0.1-10
            E = float(params.get("exposure_freq", 6))   # 0.5-10
            C = float(params.get("consequence", 7))     # 1-40
            D = L * E * C
            level = next((lv for lo, hi, lv in self.RISK_LEVEL if lo <= D <= hi), "未分级")
            return CalcResult(
                model_name=self.model_name,
                result_value=round(D, 1),
                unit="",
                formula="D = L × E × C",
                inputs=params,
                details={"L": L, "E": E, "C": C, "风险等级": level},
                source="builtin"
            )
        except Exception as e:
            return CalcResult(self.model_name, None, success=False, error=str(e))


# =============================================================================
# ④ 工程经济计算器组
# =============================================================================

class CostEstimateCalculator(BaseCalculator):
    """工程投资估算"""
    model_name = "投资估算"
    category = "engineering"
    description = "按设备费用系数法估算工程总投资"

    # 各类费用系数（相对设备费）
    COEFF = {
        "建筑工程费": 0.45,
        "安装工程费": 0.20,
        "工程建设其他费": 0.15,
        "基本预备费": 0.05,
        "涨价预备费": 0.02,
        "建设期利息": 0.03,
        "流动资金": 0.10,
    }

    def calculate(self, params: Dict[str, Any]) -> CalcResult:
        try:
            equipment_cost = float(params.get("equipment_cost", 1000))
            custom_coeff = params.get("custom_coefficients", {})
            coeff = {**self.COEFF, **custom_coeff}

            breakdown = {"设备购置费": equipment_cost}
            for item, rate in coeff.items():
                breakdown[item] = round(equipment_cost * rate, 2)

            total = sum(breakdown.values())
            return CalcResult(
                model_name=self.model_name,
                result_value=round(total, 2),
                unit="万元",
                formula="总投资 = 设备费 × (1 + Σ系数)",
                inputs=params,
                details=breakdown,
                source="builtin"
            )
        except Exception as e:
            return CalcResult(self.model_name, None, success=False, error=str(e))


# =============================================================================
# ⑤ CLI工具调用计算器（复用 CLIAnything）
# =============================================================================

class CLIToolCalculator(BaseCalculator):
    """
    通过 CLIAnything 动态调用/生成计算工具
    
    流程：
    1. 检查 generated_clis/ 下是否已有对应工具
    2. 有 → 直接运行
    3. 无 → 通过 CLIAnything 生成并运行
    """
    model_name = "CLI工具计算"
    category = "external"
    description = "通过CLIAnything动态调用或生成计算CLI工具"

    CLI_BASE_DIR = Path(__file__).parents[2] / "generated_clis"

    def calculate(self, params: Dict[str, Any]) -> CalcResult:
        tool_name = params.get("tool_name", "")
        tool_args = params.get("tool_args", {})
        tool_script = params.get("tool_script", "")  # 直接指定脚本路径

        if tool_script and Path(tool_script).exists():
            return self._run_script(tool_script, tool_args)

        # 搜索已生成的CLI
        script_path = self._find_existing_tool(tool_name)
        if script_path:
            return self._run_script(str(script_path), tool_args)

        # 降级：尝试通过CLIAnything生成
        return self._generate_and_run(tool_name, tool_args, params.get("description", ""))

    def _find_existing_tool(self, tool_name: str) -> Optional[Path]:
        """搜索已生成的CLI工具"""
        if not self.CLI_BASE_DIR.exists():
            return None
        for p in self.CLI_BASE_DIR.rglob("*.py"):
            if tool_name.lower() in p.stem.lower():
                return p
        return None

    def _run_script(self, script_path: str, args: Dict) -> CalcResult:
        """运行Python脚本计算工具"""
        try:
            args_json = json.dumps(args, ensure_ascii=False)
            result = subprocess.run(
                [sys.executable, script_path, "--input-json", args_json],
                capture_output=True, text=True, timeout=30, encoding="utf-8"
            )
            if result.returncode == 0:
                output = result.stdout.strip()
                try:
                    data = json.loads(output)
                    return CalcResult(
                        model_name=f"CLI:{Path(script_path).stem}",
                        result_value=data.get("result", output),
                        unit=data.get("unit", ""),
                        details=data,
                        source="cli_tool"
                    )
                except json.JSONDecodeError:
                    return CalcResult(
                        model_name=f"CLI:{Path(script_path).stem}",
                        result_value=output,
                        source="cli_tool"
                    )
            else:
                return CalcResult(self.model_name, None, success=False,
                                  error=result.stderr[:500])
        except subprocess.TimeoutExpired:
            return CalcResult(self.model_name, None, success=False, error="工具执行超时")
        except Exception as e:
            return CalcResult(self.model_name, None, success=False, error=str(e))

    def _generate_and_run(self, tool_name: str, args: Dict, description: str) -> CalcResult:
        """通过CLIAnything生成工具"""
        try:
            from core.cli_anything import CLIAnything
            cli = CLIAnything()
            logger.info(f"CLIAnything: 正在生成工具 '{tool_name}'")
            # 注：CLIAnything.generate是异步方法，同步包装
            loop = asyncio.new_event_loop()
            gen_result = loop.run_until_complete(
                cli.generate(description or f"{tool_name}计算工具")
            )
            loop.close()
            if gen_result and gen_result.success:
                script_path = self._find_existing_tool(tool_name)
                if script_path:
                    return self._run_script(str(script_path), args)
            return CalcResult(self.model_name, None, success=False,
                              error=f"未能自动生成工具: {tool_name}")
        except Exception as e:
            return CalcResult(self.model_name, None, success=False, error=str(e))


# =============================================================================
# 计算引擎 - 统一调度入口
# =============================================================================

class CalculationEngine:
    """
    统一计算引擎
    
    路由逻辑：
    1. 优先匹配内置高精度计算器
    2. 环境类优先走 EIA 引擎
    3. 找不到时通过 CLIAnything 动态生成工具
    
    使用示例：
        engine = get_calculation_engine()
        result = engine.calculate("npv", {"initial_investment": 5000, ...})
        print(result.to_markdown())
    """

    def __init__(self):
        self._calculators: Dict[str, BaseCalculator] = {}
        self._eia_proxy: Optional[EIAEngineProxy] = None
        self._cli_calc: Optional[CLIToolCalculator] = None
        self._register_builtins()

    def _register_builtins(self):
        """注册内置计算器"""
        builtins = [
            NPVCalculator(), IRRCalculator(), PaybackCalculator(), SensitivityCalculator(),
            EmissionCalculator(), CarbonFootprintCalculator(),
            LSRiskCalculator(), LECRiskCalculator(),
            CostEstimateCalculator(),
        ]
        for calc in builtins:
            self._calculators[calc.model_name] = calc
            # 同时用英文key注册
            eng_key = calc.category + "_" + calc.model_name
            self._calculators[eng_key] = calc

        # 添加别名
        aliases = {
            "npv": NPVCalculator(),
            "irr": IRRCalculator(),
            "payback": PaybackCalculator(),
            "sensitivity": SensitivityCalculator(),
            "emission": EmissionCalculator(),
            "carbon": CarbonFootprintCalculator(),
            "ls": LSRiskCalculator(),
            "lec": LECRiskCalculator(),
            "cost": CostEstimateCalculator(),
        }
        self._calculators.update(aliases)

    @property
    def eia_proxy(self) -> EIAEngineProxy:
        if self._eia_proxy is None:
            self._eia_proxy = EIAEngineProxy()
        return self._eia_proxy

    @property
    def cli_calc(self) -> CLIToolCalculator:
        if self._cli_calc is None:
            self._cli_calc = CLIToolCalculator()
        return self._cli_calc

    def calculate(self, model_key: str, params: Dict[str, Any]) -> CalcResult:
        """执行计算"""
        key = model_key.lower().strip()

        # 1. 精确匹配
        if key in self._calculators:
            return self._calculators[key].calculate(params)

        # 2. 模糊匹配
        for registered_key, calc in self._calculators.items():
            if key in registered_key.lower() or registered_key.lower() in key:
                return calc.calculate(params)

        # 3. 环境/大气扩散 → EIA引擎
        if any(kw in key for kw in ["gaussian", "dispersion", "noise", "aermod", "扩散", "大气", "噪声"]):
            params.setdefault("model_type", "gaussian_plume")
            return self.eia_proxy.calculate(params)

        # 4. 通用CLI工具
        params["tool_name"] = model_key
        return self.cli_calc.calculate(params)

    def calculate_batch(self, requests: List[Dict]) -> List[CalcResult]:
        """批量计算"""
        results = []
        for req in requests:
            model = req.get("model", "")
            p = req.get("params", {})
            results.append(self.calculate(model, p))
        return results

    def auto_calculate_for_doc(self, doc_type: str, project_info: Dict) -> List[CalcResult]:
        """
        根据文档类型自动执行相关计算
        
        Args:
            doc_type: 文档类型字符串（动态，不固定）
            project_info: 项目信息
        """
        results = []
        doc_lower = doc_type.lower()
        info = project_info

        # 可行性研究报告 → 财务计算全套
        if any(kw in doc_lower for kw in ["可行性", "feasibility", "投资分析"]):
            inv = info.get("investment", 5000)
            cashflows = info.get("annual_cashflows", [inv * 0.25] * 10)
            rate = info.get("discount_rate", 8)
            results.append(self.calculate("npv", {
                "initial_investment": inv, "annual_cashflows": cashflows, "discount_rate": rate
            }))
            results.append(self.calculate("irr", {
                "initial_investment": inv, "annual_cashflows": cashflows
            }))
            results.append(self.calculate("payback", {
                "initial_investment": inv, "annual_cashflows": cashflows
            }))
            results.append(self.calculate("cost", {"equipment_cost": inv * 0.4}))

        # 环评报告 → 排放+扩散计算
        if any(kw in doc_lower for kw in ["环评", "eia", "环境影响", "环境保护"]):
            results.append(self.calculate("emission", {
                "activity_level": info.get("production_scale", 10000),
                "emission_factor": info.get("emission_factor", 0.1),
                "removal_efficiency": info.get("removal_efficiency", 90),
            }))
            results.append(self.calculate("carbon", {
                "energy_consumption": info.get("energy_consumption",
                    {"electricity": 1000, "coal": 500})
            }))
            results.append(self.eia_proxy.calculate({
                "parameters": {
                    "emission_rate": info.get("stack_emission_rate", 0.5),
                    "wind_speed": info.get("wind_speed", 2.0),
                    "stack_height": info.get("stack_height", 15.0)
                },
                "predict_distance": 500
            }))

        # 安全评价 → 风险矩阵计算
        if any(kw in doc_lower for kw in ["安全", "safety", "风险评价", "危险性"]):
            for hazard in info.get("hazards", [{"likelihood": 3, "severity": 4}]):
                results.append(self.calculate("ls", hazard))
                results.append(self.calculate("lec", {
                    "likelihood": hazard.get("likelihood", 3),
                    "exposure_freq": hazard.get("exposure_freq", 6),
                    "consequence": hazard.get("consequence", 7)
                }))

        return results

    def list_models(self) -> List[Dict]:
        """列出所有可用计算模型"""
        seen = set()
        models = []
        for calc in self._calculators.values():
            if calc.model_name not in seen:
                seen.add(calc.model_name)
                models.append({
                    "name": calc.model_name,
                    "category": calc.category,
                    "description": calc.description,
                })
        return models


# =============================================================================
# 单例工厂
# =============================================================================

_engine_instance: Optional[CalculationEngine] = None

def get_calculation_engine() -> CalculationEngine:
    """获取计算引擎单例"""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = CalculationEngine()
    return _engine_instance
