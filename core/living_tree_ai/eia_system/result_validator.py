"""
结果验证器 (Result Validator)
===========================

核心理念：
- 工程师是最终把关人
- "一键复现"让验证成本降到最低
- 每个计算都有完整的审计链

验证流程：
┌────────────┐    ┌────────────┐    ┌────────────┐
│  查看结果   │ →  │  复现计算   │ →  │  对比验证   │
│            │    │            │    │            │
└────────────┘    └────────────┘    └─────┬──────┘
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    ↓                     ↓                     ↓
              ┌──────────┐          ┌──────────┐          ┌──────────┐
              │  ✅ 一致  │          │  ⚠️ 差异  │          │  ❌ 失败  │
              │  审核通过 │          │  需人工判断│          │  需排查  │
              └──────────┘          └──────────┘          └──────────┘
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional


class VerificationLevel(Enum):
    """验证等级"""
    FULL = "full"               # 完全复现
    PARTIAL = "partial"         # 部分验证
    QUICK = "quick"            # 快速校验


class VerificationResult(Enum):
    """验证结果"""
    MATCH = "match"             # 完全一致
    DIFFERENCE_WITHIN_TOLERANCE = "difference_within_tolerance"  # 差异在容差内
    DIFFERENCE_EXCEEDS_TOLERANCE = "difference_exceeds_tolerance"  # 差异超出容差
    COMPUTATION_ERROR = "computation_error"  # 计算错误
    PARAMETER_CHANGED = "parameter_changed"  # 参数已变更


@dataclass
class VerificationReport:
    """验证报告"""
    verification_id: str

    # 基本信息
    package_id: str
    model_type: str
    verification_level: VerificationLevel

    # 验证结果
    result: VerificationResult
    is_verified: bool

    # 对比数据
    original_value: Any
    reproduced_value: Any
    absolute_difference: float = 0.0
    relative_difference: float = 0.0  # 百分比

    # 容差设置
    tolerance: float = 0.01  # 1%
    tolerance_type: str = "relative"  # relative or absolute

    # 差异分析
    differences: dict = field(default_factory=dict)

    # 建议
    suggestions: list = field(default_factory=list)

    # 验证人
    verified_by: str = "engineer"
    verified_at: datetime = field(default_factory=datetime.now)
    notes: str = ""


@dataclass
class ComputationHistory:
    """计算历史记录"""
    history_id: str
    package_id: str

    # 计算信息
    model_type: str
    parameters_summary: dict

    # 结果摘要
    max_concentration: float
    max_location: tuple

    # 元数据
    created_at: datetime
    created_by: str
    computation_time: float  # 秒

    # 指纹
    fingerprint: str


class ResultValidator:
    """
    结果验证器

    核心理念：
    - 一键复现计算
    - 自动对比验证
    - 生成可审计的验证报告

    用法:
        validator = ResultValidator()

        # 记录计算历史
        validator.record_computation(package)

        # 一键复现验证
        report = await validator.verify(
            package_id="pkg_xxx",
            engine=calculation_engine
        )

        # 获取验证历史
        history = validator.get_verification_history(project_id)
    """

    def __init__(self, data_dir: str = "./data/eia/verification"):
        self.data_dir = data_dir
        self._verification_reports: dict[str, VerificationReport] = {}
        self._computation_history: dict[str, list[ComputationHistory]] = {}
        self._packages: dict[str, dict] = {}  # 存储计算包

    async def verify(
        self,
        package_id: str,
        engine,  # ModelCalculationEngine
        verification_level: VerificationLevel = VerificationLevel.FULL,
        tolerance: float = 0.01
    ) -> VerificationReport:
        """
        验证计算结果（一键复现）

        Args:
            package_id: 计算包ID
            engine: 模型计算引擎
            verification_level: 验证等级
            tolerance: 容差（默认1%）

        Returns:
            VerificationReport: 验证报告
        """
        # 获取计算包
        package = self._packages.get(package_id)
        if not package:
            raise ValueError(f"计算包 {package_id} 不存在")

        # 创建验证报告
        report = VerificationReport(
            verification_id=f"vr_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            package_id=package_id,
            model_type=package.get("model_type", ""),
            verification_level=verification_level,
            result=VerificationResult.MATCH,
            is_verified=False,
            original_value=package.get("max_concentration", 0),
            reproduced_value=0,
            tolerance=tolerance
        )

        try:
            # 重新执行计算
            input_data = self._reconstruct_input(package)
            new_result = await engine.calculate(input_data)

            report.reproduced_value = new_result.raw_output.get("max_concentration", 0)

            # 计算差异
            if report.original_value > 0:
                report.absolute_difference = abs(
                    report.original_value - report.reproduced_value
                )
                report.relative_difference = (
                    report.absolute_difference / report.original_value
                )

            # 判断验证结果
            if report.absolute_difference < 1e-10:  # 完全一致
                report.result = VerificationResult.MATCH
                report.is_verified = True
                report.suggestions = ["✅ 计算结果完全复现，验证通过"]

            elif report.relative_difference <= tolerance:
                report.result = VerificationResult.DIFFERENCE_WITHIN_TOLERANCE
                report.is_verified = True
                report.suggestions = [
                    f"⚠️ 差异率 {report.relative_difference*100:.2f}% 在容差范围内",
                    "可能原因：浮点运算精度差异、随机数种子变化等",
                    "建议：检查模型实现是否一致"
                ]

            else:
                report.result = VerificationResult.DIFFERENCE_EXCEEDS_TOLERANCE
                report.is_verified = False
                report.suggestions = [
                    f"❌ 差异率 {report.relative_difference*100:.2f}% 超出容差",
                    "可能原因：参数变更、模型实现不一致",
                    "建议：请检查输入参数是否与原始计算一致"
                ]

                # 详细差异分析
                report.differences = {
                    "original": package.get("parameters", {}),
                    "reproduced": {k: v.value for k, v in input_data.parameters.items()},
                    "output_changed": True
                }

        except Exception as e:
            report.result = VerificationResult.COMPUTATION_ERROR
            report.is_verified = False
            report.suggestions = [f"❌ 计算复现失败: {str(e)}"]

        # 保存验证报告
        self._verification_reports[report.verification_id] = report

        return report

    def _reconstruct_input(self, package_data: dict) -> ComputationInput:
        """从存储的数据重建计算输入"""
        from .calculation_engine import ComputationInput, ModelParameter, ModelType

        input_data = ComputationInput(
            model_type=ModelType(package_data.get("model_type", "gaussian_plume")),
            project_id=package_data.get("project_id", "")
        )

        # 重建参数
        for name, param_data in package_data.get("parameters", {}).items():
            if isinstance(param_data, dict):
                input_data.parameters[name] = ModelParameter(
                    name=name,
                    value=param_data.get("value", 0),
                    unit=param_data.get("unit", ""),
                    description=param_data.get("description", "")
                )
            else:
                input_data.parameters[name] = ModelParameter(name=name, value=param_data)

        # 重建源
        input_data.sources = package_data.get("sources", [])

        return input_data

    def record_computation(
        self,
        package: 'ComputationPackage',
        project_id: str,
        recorded_by: str = "system"
    ) -> str:
        """
        记录计算历史

        Args:
            package: 计算包
            project_id: 项目ID
            recorded_by: 记录人

        Returns:
            str: 历史记录ID
        """
        history_id = f"hist_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

        history = ComputationHistory(
            history_id=history_id,
            package_id=package.package_id,
            model_type=package.result.model_type.value,
            parameters_summary={
                k: v.value for k, v in package.input.parameters.items()
            },
            max_concentration=package.result.max_concentration,
            max_location=(
                package.result.max_concentration_x,
                package.result.max_concentration_y
            ),
            created_at=datetime.now(),
            created_by=recorded_by,
            computation_time=package.result.execution_time,
            fingerprint=package.package_hash
        )

        # 存储
        if project_id not in self._computation_history:
            self._computation_history[project_id] = []

        self._computation_history[project_id].append(history)

        # 存储计算包
        self._store_package(package)

        return history_id

    def _store_package(self, package: 'ComputationPackage') -> None:
        """存储计算包"""
        package_data = {
            "package_id": package.package_id,
            "model_type": package.result.model_type.value,
            "project_id": package.input.project_id,
            "parameters": {
                k: {
                    "value": v.value,
                    "unit": v.unit,
                    "source": v.source.value,
                    "description": v.description
                }
                for k, v in package.input.parameters.items()
            },
            "sources": package.input.sources,
            "max_concentration": package.result.max_concentration,
            "max_location": (
                package.result.max_concentration_x,
                package.result.max_concentration_y
            ),
            "computed_at": package.result.computed_at.isoformat() if package.result.computed_at else "",
            "fingerprint": package.package_hash,
            "created_at": package.created_at.isoformat()
        }

        self._packages[package.package_id] = package_data

    def get_verification_history(
        self,
        project_id: str = None,
        limit: int = 50
    ) -> list[dict]:
        """
        获取验证历史

        Args:
            project_id: 项目ID（可选）
            limit: 返回数量限制

        Returns:
            list: 验证历史列表
        """
        if project_id:
            history = self._computation_history.get(project_id, [])
        else:
            # 合并所有项目
            history = []
            for h_list in self._computation_history.values():
                history.extend(h_list)

        # 排序
        history.sort(key=lambda x: x.created_at, reverse=True)

        # 转换为字典
        return [
            {
                "history_id": h.history_id,
                "package_id": h.package_id,
                "model_type": h.model_type,
                "max_concentration": h.max_concentration,
                "max_location": h.max_location,
                "created_at": h.created_at.isoformat(),
                "created_by": h.created_by,
                "computation_time": h.computation_time,
                "fingerprint": h.fingerprint
            }
            for h in history[:limit]
        ]

    def get_package(self, package_id: str) -> dict:
        """获取计算包"""
        return self._packages.get(package_id, {})

    def generate_verification_report_html(
        self,
        report: VerificationReport
    ) -> str:
        """生成验证报告HTML"""
        status_icons = {
            VerificationResult.MATCH: "✅",
            VerificationResult.DIFFERENCE_WITHIN_TOLERANCE: "⚠️",
            VerificationResult.DIFFERENCE_EXCEEDS_TOLERANCE: "❌",
            VerificationResult.COMPUTATION_ERROR: "💥"
        }

        status_text = {
            VerificationResult.MATCH: "验证通过",
            VerificationResult.DIFFERENCE_WITHIN_TOLERANCE: "差异在容差内",
            VerificationResult.DIFFERENCE_EXCEEDS_TOLERANCE: "差异超出容差",
            VerificationResult.COMPUTATION_ERROR: "计算错误"
        }

        suggestions_html = "".join([
            f"<li>{s}</li>" for s in report.suggestions
        ])

        return f"""
<div class="verification-report">
    <h3>🔍 计算复现验证报告</h3>

    <table class="info-table">
        <tr><th>验证ID</th><td>{report.verification_id}</td></tr>
        <tr><th>计算包ID</th><td>{report.package_id}</td></tr>
        <tr><th>模型类型</th><td>{report.model_type}</td></tr>
        <tr><th>验证等级</th><td>{report.verification_level.value}</td></tr>
    </table>

    <div class="result-box {'pass' if report.is_verified else 'fail'}">
        <h4>{status_icons.get(report.result, '')} {status_text.get(report.result, '')}</h4>
    </div>

    <h4>对比数据</h4>
    <table class="data-table">
        <tr><th>指标</th><th>原始值</th><th>复现值</th><th>差异</th></tr>
        <tr>
            <td>最大浓度</td>
            <td>{report.original_value:.6f}</td>
            <td>{report.reproduced_value:.6f}</td>
            <td>{report.absolute_difference:.6f} ({report.relative_difference*100:.2f}%)</td>
        </tr>
    </table>

    <h4>容差设置</h4>
    <p>容差类型: {report.tolerance_type}</p>
    <p>容差值: {report.tolerance*100:.1f}%</p>

    {'<h4>差异分析</h4><pre>' + json.dumps(report.differences, indent=2, ensure_ascii=False) + '</pre>' if report.differences else ''}

    <h4>建议</h4>
    <ul>
        {suggestions_html}
    </ul>

    <div class="meta">
        <p>验证人: {report.verified_by}</p>
        <p>验证时间: {report.verified_at.strftime('%Y-%m-%d %H:%M:%S')}</p>
        {f"<p>备注: {report.notes}</p>" if report.notes else ""}
    </div>
</div>
"""

    def batch_verify(
        self,
        package_ids: list[str],
        engine,  # ModelCalculationEngine
        callback: Callable = None
    ) -> list[VerificationReport]:
        """
        批量验证

        Args:
            package_ids: 计算包ID列表
            engine: 模型计算引擎
            callback: 进度回调

        Returns:
            list[VerificationReport]: 验证报告列表
        """
        reports = []

        for i, package_id in enumerate(package_ids):
            report = asyncio.run(self.verify(package_id, engine))
            reports.append(report)

            if callback:
                callback(i + 1, len(package_ids), report)

        return reports


def create_result_validator(data_dir: str = "./data/eia/verification") -> ResultValidator:
    """创建结果验证器实例"""
    return ResultValidator(data_dir=data_dir)