"""
环评工艺管理器 (EIA Process Manager)
====================================

四层智能体协同中枢：
1. 工艺理解 → 2. 工艺扩展 → 3. 环保分析 → 4. 可视化

作者：Hermes Desktop AI Team
"""

import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime

from business.eia_process import (
    ProcessType, EIAReport, ProcessStep, Pollutant, EIAMitigation
)
from business.eia_process.agents.process_parser import ProcessParser
from business.eia_process.agents.process_expander import ProcessExpander
from business.eia_process.agents.eia_analyst import EIAAnalyst
from business.eia_process.agents.visualization_agent import VisualizationAgent
from business.eia_process.knowledge.knowledge_base import EIAProcessKnowledgeBase

logger = logging.getLogger(__name__)


class EIAProcessManager:
    """
    环评工艺管理器 - 四层智能体协同中枢

    使用示例：
        manager = EIAProcessManager()

        # 一键生成完整环评工艺章节
        result = manager.generate("上料、喷砂、打磨、喷漆")

        # 分步执行
        parser_result = manager.parse_process("上料、喷砂、打磨、喷漆")
        expanded = manager.expand_process(parser_result.standard_steps)
        eia = manager.analyze_environmental(expanded.complete_chain)
        graphics = manager.generate_graphics(expanded.complete_chain, eia)
    """

    def __init__(self, storage_dir: str = None):
        """初始化管理器"""
        # 初始化四层智能体
        self.parser = ProcessParser()
        self.expander = ProcessExpander()
        self.analyst = EIAAnalyst()
        self.visualizer = VisualizationAgent()

        # 初始化知识库
        self.knowledge_base = EIAProcessKnowledgeBase(storage_dir)

        # 任务历史
        self.tasks: Dict[str, Dict] = {}
        self._task_counter = 0

        logger.info("环评工艺管理器初始化完成")

    def generate(self, raw_input: str,
                project_name: str = "",
                progress_callback: Callable = None) -> Dict[str, Any]:
        """
        一键生成完整环评工艺章节

        Args:
            raw_input: 原始工艺描述，如 "上料、喷砂、打磨、喷漆"
            project_name: 项目名称（可选）
            progress_callback: 进度回调函数

        Returns:
            完整的环评报告数据
        """
        logger.info(f"开始生成环评工艺: {raw_input}")
        task_id = self._create_task(raw_input)

        try:
            # Step 1: 工艺理解
            if progress_callback:
                progress_callback(1, "解析工艺...")
            parse_result = self.parser.parse(raw_input)
            self._update_task(task_id, "parse", parse_result)

            # Step 2: 工艺扩展
            if progress_callback:
                progress_callback(2, "扩展工艺链...")
            expand_result = self.expander.expand(
                parse_result.standard_steps,
                parse_result.process_type
            )
            self._update_task(task_id, "expand", expand_result)

            # Step 3: 环保分析
            if progress_callback:
                progress_callback(3, "分析环境影响...")
            eia_result = self.analyst.analyze(
                expand_result.get("complete_chain", []),
                expand_result.get("equipment", [])
            )
            self._update_task(task_id, "analyze", eia_result)

            # Step 4: 可视化
            if progress_callback:
                progress_callback(4, "生成图表...")
            graphics = self.visualizer.generate_complete_report_graphics(
                expand_result.get("complete_chain", []),
                {
                    "air_pollutants": eia_result.air_pollutants,
                    "water_pollutants": eia_result.water_pollutants,
                    "solid_wastes": eia_result.solid_wastes,
                },
                eia_result.mitigation_measures
            )
            self._update_task(task_id, "visualize", graphics)

            # 编译完整报告
            report = self._compile_report(
                raw_input=raw_input,
                project_name=project_name,
                parse_result=parse_result,
                expand_result=expand_result,
                eia_result=eia_result,
                graphics=graphics,
            )

            if progress_callback:
                progress_callback(5, "完成!")

            logger.info(f"环评工艺生成完成: {len(report['process_steps'])}道工序, "
                       f"{len(report['air_pollutants'])}种废气")

            return report

        except Exception as e:
            logger.error(f"环评工艺生成失败: {e}")
            return {"error": str(e), "task_id": task_id}

    def parse_process(self, raw_input: str) -> Dict[str, Any]:
        """
        解析工艺（第一步）

        Args:
            raw_input: 原始工艺描述

        Returns:
            解析结果
        """
        result = self.parser.parse(raw_input)
        return self.parser.parse_to_dict(raw_input)

    def expand_process(self, steps: List[str], process_type: ProcessType = None) -> Dict[str, Any]:
        """
        扩展工艺（第二步）

        Args:
            steps: 标准化工序列表
            process_type: 工艺类型

        Returns:
            扩展结果
        """
        return self.expander.expand_to_dict(steps, process_type)

    def analyze_environmental(self, process_chain: List[str],
                             equipment: List[str] = None) -> Any:
        """
        环保分析（第三步）

        Args:
            process_chain: 工艺链
            equipment: 设备列表

        Returns:
            环保分析结果
        """
        return self.analyst.analyze(process_chain, equipment)

    def generate_graphics(self, process_chain: List[str],
                         eia_result: Any) -> Dict[str, str]:
        """
        生成可视化（第四步）

        Args:
            process_chain: 工艺链
            eia_result: 环保分析结果

        Returns:
            图形数据
        """
        pollutants = {
            "air_pollutants": eia_result.air_pollutants if hasattr(eia_result, 'air_pollutants') else [],
            "water_pollutants": eia_result.water_pollutants if hasattr(eia_result, 'water_pollutants') else [],
            "solid_wastes": eia_result.solid_wastes if hasattr(eia_result, 'solid_wastes') else [],
        }

        mitigation = eia_result.mitigation_measures if hasattr(eia_result, 'mitigation_measures') else []

        return self.visualizer.generate_complete_report_graphics(process_chain, pollutants, mitigation)

    def _compile_report(self, raw_input: str,
                       project_name: str,
                       parse_result: Any,
                       expand_result: Dict,
                       eia_result: Any,
                       graphics: Dict) -> Dict[str, Any]:
        """编译完整报告"""
        # 构建工艺步骤列表
        process_steps = []
        for i, step_name in enumerate(expand_result.get("complete_chain", [])):
            is_original = step_name in expand_result.get("original_steps", [])
            process_steps.append({
                "序号": i + 1,
                "工序名称": step_name,
                "是否原始": "是" if is_original else "否",
                "参数": expand_result.get("parameters", {}).get(step_name, {}),
            })

        # 构建污染物列表
        air_pollutants = []
        for p in (eia_result.air_pollutants or []):
            air_pollutants.append({
                "序号": p.code if hasattr(p, 'code') else "",
                "污染物名称": p.name,
                "产生量": f"{p.amount}{p.unit}" if hasattr(p, 'amount') else "",
                "排放标准": f"{p.standard}{p.standard_limit}" if hasattr(p, 'standard') else "",
                "控制措施": p.control_measure if hasattr(p, 'control_measure') else "",
            })

        water_pollutants = []
        for p in (eia_result.water_pollutants or []):
            water_pollutants.append({
                "序号": p.code if hasattr(p, 'code') else "",
                "污染物名称": p.name,
                "产生量": f"{p.amount}{p.unit}" if hasattr(p, 'amount') else "",
                "排放标准": f"{p.standard}{p.standard_limit}" if hasattr(p, 'standard') else "",
            })

        solid_wastes = []
        for p in (eia_result.solid_wastes or []):
            solid_wastes.append({
                "序号": p.code if hasattr(p, 'code') else "",
                "废物名称": p.name,
                "产生量": f"{p.amount}{p.unit}" if hasattr(p, 'amount') else "",
                "属性": "危险废物" if "危险" in p.name else "一般固废",
                "处置措施": p.control_measure if hasattr(p, 'control_measure') else "",
            })

        # 构建防治措施
        mitigation_measures = []
        for m in (eia_result.mitigation_measures or []):
            mitigation_measures.append({
                "类型": m.type,
                "措施": m.measure,
                "去除效率": f"{m.removal_efficiency}%" if hasattr(m, 'removal_efficiency') else "",
                "投资估算": f"{m.investment}万元" if hasattr(m, 'investment') else "",
            })

        return {
            # 基本信息
            "project_name": project_name or "环评项目",
            "process_name": raw_input,
            "industry": parse_result.industry if hasattr(parse_result, 'industry') else "",
            "complexity": parse_result.complexity if hasattr(parse_result, 'complexity') else "",

            # 工艺信息
            "raw_steps": expand_result.get("original_steps", []),
            "complete_chain": expand_result.get("complete_chain", []),
            "process_steps": process_steps,
            "equipment": expand_result.get("equipment", []),
            "materials": expand_result.get("materials", {}),
            "energy_consumption": expand_result.get("energy_consumption", 0),

            # 污染物
            "air_pollutants": air_pollutants,
            "water_pollutants": water_pollutants,
            "solid_wastes": solid_wastes,
            "noise_sources": [
                {"名称": p.name, "声级": f"{p.amount}{p.unit}"}
                for p in (eia_result.noise_sources or [])
            ],

            # 防治措施
            "mitigation_measures": mitigation_measures,

            # 环境影响
            "environmental_impact": eia_result.environmental_impact if hasattr(eia_result, 'environmental_impact') else {},

            # 合规性
            "compliance_status": eia_result.compliance_status if hasattr(eia_result, 'compliance_status') else {},

            # 风险评估
            "risk_assessment": eia_result.risk_assessment if hasattr(eia_result, 'risk_assessment') else {},

            # 图形
            "graphics": {
                "process_flowchart": graphics.get("process_flowchart", ""),
                "pollutant_flowchart": graphics.get("pollutant_flowchart", ""),
                "mitigation_flowchart": graphics.get("mitigation_flowchart", ""),
            },

            # 元数据
            "confidence": expand_result.get("confidence", 0),
            "created_at": datetime.now().isoformat(),
            "version": "1.0",
        }

    def _create_task(self, raw_input: str) -> str:
        """创建任务"""
        self._task_counter += 1
        task_id = f"eia_task_{self._task_counter}"
        self.tasks[task_id] = {
            "id": task_id,
            "input": raw_input,
            "status": "running",
            "created_at": datetime.now(),
            "steps": {},
        }
        return task_id

    def _update_task(self, task_id: str, step: str, result: Any):
        """更新任务状态"""
        if task_id in self.tasks:
            self.tasks[task_id]["steps"][step] = result
            self.tasks[task_id]["last_update"] = datetime.now()

    def get_task(self, task_id: str) -> Optional[Dict]:
        """获取任务"""
        return self.tasks.get(task_id)

    def list_tasks(self, limit: int = 10) -> List[Dict]:
        """列出任务"""
        tasks = sorted(self.tasks.values(), key=lambda t: t.get("created_at", datetime.now()), reverse=True)
        return tasks[:limit]

    def export_report(self, report: Dict[str, Any], format: str = "json") -> str:
        """
        导出报告

        Args:
            report: 报告数据
            format: 格式 (json/markdown/html)

        Returns:
            格式化后的报告字符串
        """
        if format == "json":
            import json
            return json.dumps(report, ensure_ascii=False, indent=2)

        elif format == "markdown":
            return self._to_markdown(report)

        elif format == "html":
            return self._to_html(report)

        return str(report)

    def _to_markdown(self, report: Dict) -> str:
        """转换为Markdown"""
        lines = [
            f"# {report.get('project_name', '环评工艺分析报告')}\n",
            f"**工艺**: {report.get('process_name', '')}",
            f"**行业**: {report.get('industry', '')}",
            f"**复杂度**: {report.get('complexity', '')}",
            f"**生成时间**: {report.get('created_at', '')}\n",
            "---\n",
            "## 一、工艺流程\n",
        ]

        # 工艺链
        chain = report.get("complete_chain", [])
        for i, step in enumerate(chain, 1):
            lines.append(f"{i}. {step}")

        # 设备
        if report.get("equipment"):
            lines.append("\n### 主要设备")
            for eq in report["equipment"]:
                lines.append(f"- {eq}")

        # 废气
        if report.get("air_pollutants"):
            lines.append("\n## 二、废气污染物")
            lines.append("| 序号 | 污染物 | 产生量 | 排放标准 |")
            lines.append("|------|--------|--------|----------|")
            for p in report["air_pollutants"]:
                lines.append(f"| {p.get('序号', '')} | {p.get('污染物名称', '')} | {p.get('产生量', '')} | {p.get('排放标准', '')} |")

        # 废水
        if report.get("water_pollutants"):
            lines.append("\n## 三、废水污染物")
            lines.append("| 序号 | 污染物 | 产生量 | 排放标准 |")
            lines.append("|------|--------|--------|----------|")
            for p in report["water_pollutants"]:
                lines.append(f"| {p.get('序号', '')} | {p.get('污染物名称', '')} | {p.get('产生量', '')} | {p.get('排放标准', '')} |")

        # 固废
        if report.get("solid_wastes"):
            lines.append("\n## 四、固体废物")
            lines.append("| 序号 | 废物名称 | 产生量 | 属性 | 处置措施 |")
            lines.append("|------|---------|--------|------|----------|")
            for p in report["solid_wastes"]:
                lines.append(f"| {p.get('序号', '')} | {p.get('废物名称', '')} | {p.get('产生量', '')} | {p.get('属性', '')} | {p.get('处置措施', '')} |")

        # 防治措施
        if report.get("mitigation_measures"):
            lines.append("\n## 五、污染防治措施")
            for m in report["mitigation_measures"]:
                lines.append(f"- **{m.get('类型', '')}**: {m.get('措施', '')} (效率: {m.get('去除效率', '')})")

        # 风险评估
        if report.get("risk_assessment"):
            ra = report["risk_assessment"]
            lines.append("\n## 六、环境风险评估")
            lines.append(f"- **风险等级**: {ra.get('风险等级', '')}")
            if ra.get("重大风险源"):
                lines.append("\n**重大风险源**:")
                for risk in ra["重大风险源"]:
                    lines.append(f"- {risk}")

        # 流程图
        if report.get("graphics", {}).get("process_flowchart"):
            lines.append("\n## 七、工艺流程图\n")
            lines.append("```mermaid")
            lines.append(report["graphics"]["process_flowchart"])
            lines.append("```")

        return "\n".join(lines)

    def _to_html(self, report: Dict) -> str:
        """转换为HTML"""
        md = self._to_markdown(report)
        # 简单转换，实际应使用markdown库
        html = md.replace("\n", "<br>")
        html = html.replace("# ", "<h1>").replace("</h1>", "</h1>", 1)
        html = html.replace("## ", "<h2>").replace("</h2>", "</h2>", 1)
        html = html.replace("### ", "<h3>").replace("</h3>", "</h3>", 1)
        html = html.replace("**", "<strong>").replace("**", "</strong>")
        html = html.replace("- ", "<li>")
        html = html.replace("| ", "<tr>").replace(" |", "</tr>")
        return f"<html><body>{html}</body></html>"
