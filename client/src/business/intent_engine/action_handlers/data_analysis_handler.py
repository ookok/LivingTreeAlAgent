# -*- coding: utf-8 -*-
"""
数据分析动作处理器
==================

处理数据分析意图：
- DATA_ANALYSIS: 数据分析
- DATA_VISUALIZATION: 数据可视化

使用 GlobalModelRouter 调用数据分析能力。
from __future__ import annotations
"""


import logging
from typing import Optional
from pathlib import Path

from ..intent_types import IntentType
from .base import (
    BaseActionHandler,
    ActionContext,
    ActionResult,
    ActionResultStatus,
)

logger = logging.getLogger(__name__)


class DataAnalysisHandler(BaseActionHandler):
    """
    数据分析处理器

    支持的意图：
    - DATA_ANALYSIS
    - DATA_VISUALIZATION

    上下文参数：
    - data: 要分析的数据（文本/文件路径/URL）
    - analysis_type: 分析类型（descriptive/diagnostic/predictive/prescriptive）
    - output_format: 输出格式（text/table/json/visualization）
    """

    @property
    def name(self) -> str:
        return "DataAnalysisHandler"

    @property
    def supported_intents(self) -> list:
        return [IntentType.DATA_ANALYSIS, IntentType.DATA_VISUALIZATION]

    @property
    def priority(self) -> int:
        return 60

    async def handle(self, ctx: ActionContext) -> ActionResult:
        """
        执行数据分析

        ctx.kwargs 可以包含：
        - data: 数据内容或文件路径
        - data_file: 数据文件路径（CSV/JSON/XLSX）
        - analysis_type: 分析类型
        - output_format: 输出格式
        - visualization_type: 可视化类型（bar/line/scatter/histogram/heatmap）
        """
        try:
            data = ctx.extra.get("data", "")
            data_file = ctx.extra.get("data_file", "")
            analysis_type = ctx.extra.get("analysis_type", "descriptive")
            output_format = ctx.extra.get("output_format", "text")

            # 如果没有直接提供数据，尝试从文件读取
            if not data and data_file:
                data = self._read_data_file(data_file)

            if not data and ctx.intent.target:
                data = ctx.intent.target

            if not data:
                return ActionResult(
                    status=ActionResultStatus.NEED_CLARIFY,
                    clarification_prompt="请提供需要分析的数据（直接输入或指定文件路径）",
                )

            logger.info(f"执行数据分析: type={analysis_type}, format={output_format}")

            result = await self._do_analyze(data, analysis_type, output_format, ctx.extra)

            suggestions = [
                "可指定 analysis_type 改变分析类型",
                "可指定 output_format 改变输出格式（text/table/json/visualization）",
            ]
            if output_format == "text":
                suggestions.append("尝试 output_format='visualization' 生成可视化")

            return ActionResult(
                status=ActionResultStatus.SUCCESS,
                output=result,
                output_type=output_format,
                suggestions=suggestions,
            )

        except Exception as e:
            logger.error(f"数据分析失败: {e}")
            return ActionResult(
                status=ActionResultStatus.FAILURE,
                error=f"数据分析失败: {str(e)}",
            )

    async def _do_analyze(self, data: str, analysis_type: str,
                            output_format: str, extra: dict) -> str:
        """调用 GlobalModelRouter 执行数据分析"""
        try:
            from client.src.business.global_model_router import (
                get_global_router, ModelCapability,
            )
        except ImportError:
            from .base import get_llm_client, LLMError
            client = get_llm_client()
            prompt = self._build_prompt(data, analysis_type, output_format, extra)
            result = client.chat(prompt=prompt, temperature=0.3)
            return result["content"]

        router = get_global_router()

        analysis_hint = {
            "descriptive": "描述性分析：总结基本统计信息、分布、趋势",
            "diagnostic": "诊断性分析：找出问题根源、异常原因",
            "predictive": "预测性分析：基于历史数据预测未来趋势",
            "prescriptive": "规范性分析：给出行动建议和决策支持",
        }.get(analysis_type, "描述性分析：总结基本统计信息")

        format_hint = {
            "text": "用自然语言描述分析结果",
            "table": "用表格形式展示分析结果",
            "json": "用 JSON 格式输出分析结果",
            "visualization": "描述如何可视化此数据（图表类型、字段映射）",
        }.get(output_format, "用自然语言描述分析结果")

        viz_type = extra.get("visualization_type", "")
        viz_hint = f"\n推荐图表类型：{viz_type}" if viz_type else ""

        prompt = f"""请对以下数据进行{analysis_type}分析。

分析要求：
- {analysis_hint}
- {format_hint}{viz_hint}
- 给出具体、可操作的洞察

数据：
```
{data[:3000]}
```

分析结果："""

        system = "你是一个专业的数据分析师。准确分析数据，给出有价值的洞察。"

        result = await router.call_model(
            capability=ModelCapability.DATA_ANALYSIS,
            prompt=prompt,
            system_prompt=system,
            temperature=0.3,
        )

        content = result.get("content", "").strip()
        if not content:
            raise RuntimeError("数据分析返回空内容")

        return content

    def _read_data_file(self, file_path: str) -> str:
        """读取数据文件"""
        try:
            path = Path(file_path)
            if not path.exists():
                return ""

            suffix = path.suffix.lower()
            if suffix == ".csv":
                return path.read_text(encoding="utf-8")
            elif suffix == ".json":
                import json
                data = json.loads(path.read_text(encoding="utf-8"))
                return json.dumps(data, ensure_ascii=False, indent=2)
            elif suffix in (".xlsx", ".xls"):
                return f"[Excel 文件: {file_path}]（请安装 openpyxl 以读取 Excel 文件）"
            else:
                return path.read_text(encoding="utf-8")

        except Exception as e:
            logger.warning(f"读取数据文件失败: {e}")
            return ""

    def _build_prompt(self, data: str, analysis_type: str,
                     output_format: str, extra: dict) -> str:
        """构建分析提示词（fallback 用）"""
        analysis_hint = {
            "descriptive": "描述性分析：总结基本统计信息、分布、趋势",
            "diagnostic": "诊断性分析：找出问题根源、异常原因",
            "predictive": "预测性分析：基于历史数据预测未来趋势",
            "prescriptive": "规范性分析：给出行动建议和决策支持",
        }.get(analysis_type, "描述性分析")

        format_hint = {
            "text": "用自然语言描述分析结果",
            "table": "用表格形式展示分析结果",
            "json": "用 JSON 格式输出分析结果",
            "visualization": "描述如何可视化此数据",
        }.get(output_format, "用自然语言描述")

        return f"""请对以下数据进行{analysis_type}分析。

分析要求：
- {analysis_hint}
- {format_hint}

数据：
```
{data[:3000]}
```

分析结果："""
