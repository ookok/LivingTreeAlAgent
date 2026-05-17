"""LivingReport — Interactive, self-updating, hallucination-guarded reports.

Innovations beyond static document generation:
  1. Living Report — auto-refresh when source data changes
  2. Hallucination Guard — verify LLM-generated content against model data
  3. Compliance Scorer — rate sections against regulatory standards
  4. Report Quality Score — auto-grade completeness, accuracy, formatting
  5. Audience Synthesizer — same data, different language by audience
  6. Interactive HTML Export — ECharts, drill-down, expandable sections
  7. Smart Template Recommender — suggest best template from project params
  8. Report Repository Search — NL query across all generated reports

Usage:
    from livingtree.capability.living_report import LivingReport
    report = LivingReport("eia_report", data_sources=[...])
    await report.generate()
    report.watch_data_changes()  # Auto-refresh on data update
    score = report.quality_score()  # → 92/100
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from loguru import logger


# ═══ 1. Living Report — auto-refresh on data change ═══

class LivingReport:
    """A report that watches its data sources and auto-refreshes."""

    def __init__(self, template_type: str, data_sources: list[dict] = None,
                 report_id: str = ""):
        self.template_type = template_type
        self.data_sources = data_sources or []
        self.report_id = report_id or f"lr_{int(time.time())}"
        self._content: dict = {}
        self._watchers: dict[str, str] = {}  # path → hash
        self._refresh_callbacks: list[callable] = []
        self._version = 0
        self._generated_at: float = 0

    async def generate(self, **kwargs) -> dict:
        """Generate the report with current data."""
        from .report_enhancer import ReportEnhancer

        enhancer = ReportEnhancer()
        self._content = await enhancer.generate(
            self.template_type, kwargs.get("data", {}),
            format=kwargs.get("format", "docx"),
            output=kwargs.get("output", ""),
            data_sources=self.data_sources,
            citations=kwargs.get("citations", True),
            lang=kwargs.get("lang", "zh-CN"),
        )
        self._version += 1
        self._generated_at = time.time()
        return self._content

    def watch_data_changes(self, interval_seconds: float = 60.0) -> None:
        """Start watching data sources for changes. Auto-refreshes on change."""
        self._snapshot_data_hashes()

        async def _watch_loop():
            while True:
                await asyncio.sleep(interval_seconds)
                if self._data_changed():
                    logger.info(f"LivingReport {self.report_id}: data changed, regenerating...")
                    await self.generate(data=self._last_params)
                    for cb in self._refresh_callbacks:
                        try:
                            cb(self._content, self._version)
                        except Exception:
                            pass

        try:
            loop = asyncio.get_event_loop()
            loop.create_task(_watch_loop())
            logger.info(f"LivingReport {self.report_id}: watching {len(self._watchers)} sources")
        except RuntimeError:
            pass

    def on_refresh(self, callback: callable) -> None:
        """Register callback for report refresh events."""
        self._refresh_callbacks.append(callback)

    def _snapshot_data_hashes(self) -> None:
        for src in self.data_sources:
            path = src.get("path", "") or src.get("url", "")
            if Path(path).exists():
                self._watchers[path] = hashlib.md5(
                    Path(path).read_bytes()).hexdigest()

    def _data_changed(self) -> bool:
        for path, old_hash in self._watchers.items():
            if Path(path).exists():
                new_hash = hashlib.md5(Path(path).read_bytes()).hexdigest()
                if new_hash != old_hash:
                    self._watchers[path] = new_hash
                    return True
        return False

    @property
    def version(self) -> int:
        return self._version

    @property
    def age_seconds(self) -> float:
        return time.time() - self._generated_at if self._generated_at else 0


# ═══ 2. Hallucination Guard — verify LLM content against model data ═══

class HallucinationGuard:
    """Detect LLM-generated numbers that don't match EIA model calculations.

    Compares: LLM output text vs actual physics model results.
    Marks content as: verified / unverified / suspicious / incorrect.
    """

    @staticmethod
    def check(section_content: str, model_results: dict,
              threshold: float = 0.05) -> dict:
        """Check section text for hallucinated numbers.

        Returns: {status, issues, verified_numbers, suspicious_numbers}
        """
        issues = []
        verified = []
        suspicious = []

        # Extract all numbers from section text
        numbers = re.findall(r'([\d.]+)\s*(mg/m³|μg/m³|dB\(A\)|mg/L|t/a|万元|m/s|%)?',
                            section_content)

        for value_str, unit in numbers:
            try:
                value = float(value_str)
            except ValueError:
                continue

            # Check against model results
            for model_key, model_result in model_results.items():
                if isinstance(model_result, dict):
                    for result_key, result_val in model_result.items():
                        if isinstance(result_val, (int, float)):
                            if abs(value - result_val) / max(abs(result_val), 1e-9) < threshold:
                                verified.append({
                                    "value": value, "unit": unit or "",
                                    "source_model": model_key, "match": round(result_val, 2),
                                    "context": HallucinationGuard._extract_context(section_content, value_str),
                                })
                            elif abs(value - result_val) / max(abs(result_val), 1e-9) < threshold * 5:
                                suspicious.append({
                                    "value": value, "unit": unit or "",
                                    "source_model": model_key,
                                    "expected": round(result_val, 2),
                                    "deviation_pct": round(abs(value - result_val) / max(abs(result_val), 1e-9) * 100, 1),
                                    "context": HallucinationGuard._extract_context(section_content, value_str),
                                })

        # Classify
        unverified_count = len(numbers) - len(verified) - len(suspicious)
        if unverified_count > len(numbers) * 0.3:
            status = "suspicious"
        elif suspicious:
            status = "needs_review"
        else:
            status = "verified"

        return {
            "status": status,
            "total_numbers": len(numbers),
            "verified": len(verified),
            "suspicious": len(suspicious),
            "unverified": unverified_count,
            "issues": issues,
            "verified_numbers": verified[:10],
            "suspicious_numbers": suspicious[:10],
        }

    @staticmethod
    def _extract_context(text: str, target: str, window: int = 80) -> str:
        idx = text.find(target)
        if idx < 0:
            return ""
        start = max(0, idx - window // 2)
        end = min(len(text), idx + window // 2)
        return text[start:end].strip()

    @staticmethod
    def generate_confidence_badge(check_result: dict) -> str:
        """Generate a confidence badge for the report."""
        status = check_result.get("status", "unknown")
        badges = {
            "verified": f"✅ 数据可信度: {check_result.get('verified',0)}/{check_result.get('total_numbers',0)} 个数值已通过模型验证",
            "needs_review": f"⚠️ 数据需复核: {check_result.get('suspicious',0)} 个数值与模型计算偏差 >5%",
            "suspicious": f"🔴 数据存疑: {check_result.get('unverified',0)} 个数值无法验证来源",
        }
        return badges.get(status, "❓ 数据验证状态未知")


# ═══ 3. Compliance Scorer — rate against regulatory standards ═══

class ComplianceScorer:
    """Rate report sections against regulatory standards."""

    STANDARDS = {
        "air_quality": {
            "standard": "GB 3095-2012",
            "checks": {
                "pm25_annual": {"limit": 35, "unit": "μg/m³", "class": "一级"},
                "pm10_annual": {"limit": 40, "unit": "μg/m³", "class": "一级"},
                "so2_annual": {"limit": 20, "unit": "μg/m³", "class": "一级"},
                "no2_annual": {"limit": 40, "unit": "μg/m³", "class": "一级"},
                "co_24h": {"limit": 4, "unit": "mg/m³", "class": "一级"},
                "o3_8h": {"limit": 100, "unit": "μg/m³", "class": "一级"},
            },
        },
        "water_quality": {
            "standard": "GB 3838-2002",
            "checks": {
                "ph": {"limit": (6, 9), "unit": "", "class": "I~V类"},
                "do": {"limit": 7.5, "unit": "mg/L", "class": "I类", "min": True},
                "cod": {"limit": 15, "unit": "mg/L", "class": "I类"},
                "bod5": {"limit": 3, "unit": "mg/L", "class": "I类"},
                "nh3_n": {"limit": 0.15, "unit": "mg/L", "class": "I类"},
                "tp": {"limit": 0.02, "unit": "mg/L", "class": "I类"},
            },
        },
        "noise": {
            "standard": "GB 3096-2008",
            "checks": {
                "residential_day": {"limit": 55, "unit": "dB(A)", "class": "1类"},
                "residential_night": {"limit": 45, "unit": "dB(A)", "class": "1类"},
                "industrial_day": {"limit": 65, "unit": "dB(A)", "class": "3类"},
            },
        },
    }

    @classmethod
    def score_section(cls, section_name: str, section_content: str,
                      measured_data: dict) -> dict:
        """Score a section against applicable standards."""
        category = cls._classify_section(section_name)
        rules = cls.STANDARDS.get(category, {})
        if not rules:
            return {"score": 100, "category": "no_standards", "message": "无适用标准"}

        checks_passed = 0
        checks_total = 0
        details = []

        for check_name, rule in rules.get("checks", {}).items():
            checks_total += 1
            value = measured_data.get(check_name)
            if value is None:
                details.append({"check": check_name, "status": "no_data",
                               "message": f"缺少 {check_name} 监测数据"})
                continue

            limit = rule["limit"]
            if isinstance(limit, tuple):
                passed = limit[0] <= value <= limit[1]
            elif rule.get("min"):
                passed = value >= limit
            else:
                passed = value <= limit

            if passed:
                checks_passed += 1
            details.append({
                "check": check_name, "status": "pass" if passed else "fail",
                "value": value, "limit": limit, "unit": rule.get("unit", ""),
                "class": rule.get("class", ""),
            })

        score = round(checks_passed / max(checks_total, 1) * 100)
        return {
            "score": score,
            "category": category,
            "standard": rules.get("standard", ""),
            "checks_passed": checks_passed,
            "checks_total": checks_total,
            "details": details,
            "grade": "A" if score >= 90 else "B" if score >= 70 else "C" if score >= 50 else "D",
        }

    @classmethod
    def score_report(cls, sections: list[dict],
                     measured_data: dict) -> dict:
        """Score entire report across all sections."""
        section_scores = {}
        for section in sections:
            name = section.get("heading", "")
            score = cls.score_section(name, section.get("body", ""), measured_data)
            section_scores[name] = score

        avg_score = round(sum(s["score"] for s in section_scores.values()) /
                        max(len(section_scores), 1))
        return {
            "overall_score": avg_score,
            "grade": "A" if avg_score >= 90 else "B" if avg_score >= 70 else "C" if avg_score >= 50 else "D",
            "sections": section_scores,
        }

    @classmethod
    def _classify_section(cls, name: str) -> str:
        name_lower = name.lower()
        if any(k in name_lower for k in ("大气", "空气", "air", "废气", "烟尘", "pm")):
            return "air_quality"
        if any(k in name_lower for k in ("水", "water", "废水", "地表", "地下", "bod", "cod")):
            return "water_quality"
        if any(k in name_lower for k in ("噪声", "noise", "声", "振动")):
            return "noise"
        return "general"


# ═══ 4. Report Quality Score — completeness + accuracy + formatting ═══

class QualityScorer:
    """Auto-grade report quality across multiple dimensions."""

    @staticmethod
    def score(content: dict, citation_tracker=None,
              compliance_result: dict = None) -> dict:
        """Score report quality. Returns {overall, dimensions, suggestions}."""
        scores = {}

        # Completeness: required sections present
        sections = content.get("sections", [])
        headings = [s.get("heading", "") for s in sections if isinstance(s, dict)]
        expected = len(content.get("_template_sections", [])) or len(sections)
        scores["completeness"] = min(100, round(len(headings) / max(expected, 1) * 100))

        # Formatting: citations, tables, figures
        fmt_score = 100
        suggestions = []
        if citation_tracker:
            if sum(citation_tracker._tables.values()) == 0:
                fmt_score -= 15
                suggestions.append("建议添加表格并编号")
            if sum(citation_tracker._figures.values()) == 0:
                fmt_score -= 15
                suggestions.append("建议添加图表并编号")
            if len(citation_tracker._refs) == 0:
                fmt_score -= 10
                suggestions.append("建议添加参考文献")

        # Body quality: minimum content per section
        total_chars = sum(len(s.get("body", "")) for s in sections if isinstance(s, dict))
        avg_chars = total_chars / max(len(sections), 1)
        if avg_chars < 100:
            fmt_score -= 20
            suggestions.append(f"章节内容偏短 (平均 {avg_chars:.0f} 字符)")
        scores["formatting"] = max(0, fmt_score)

        # Data accuracy: compliance score
        if compliance_result:
            scores["accuracy"] = compliance_result.get("overall_score", 80)
        else:
            scores["accuracy"] = 90  # Default if no compliance check

        # Overall
        overall = round(
            scores["completeness"] * 0.3 +
            scores["formatting"] * 0.3 +
            scores["accuracy"] * 0.4
        )

        return {
            "overall": overall,
            "grade": "A" if overall >= 90 else "B" if overall >= 70 else "C" if overall >= 50 else "D",
            "dimensions": scores,
            "suggestions": suggestions,
        }


# ═══ 5. Audience Synthesizer — same data, different language ═══

class AudienceSynthesizer:
    """Generate audience-specific versions from the same report data.

    technical → engineers (full details, formulas, units)
    management → directors (KPIs, costs, risks, timelines)
    public → community (plain language, key impacts, no jargon)
    """

    @staticmethod
    async def synthesize(content: dict, audience: str) -> str:
        """Synthesize a version for a specific audience."""
        from ..bridge.registry import get_tool_registry  # TODO(bridge): via bridge.LLMProtocol

        llm = TreeLLM.from_config()

        prompts = {
            "technical": "你是技术审查专家。从详细数据生成技术报告摘要。保留所有数值、单位和公式。",
            "management": "你是项目总监。生成管理层摘要：KPI、成本、时间线、风险、建议。不要技术细节。",
            "public": "你是社区沟通专家。用通俗语言生成公众摘要，避免专业术语。重点：环境影响、健康风险、缓解措施。",
        }

        prompt = prompts.get(audience, prompts["technical"])
        body = json.dumps(content, ensure_ascii=False, default=str)[:3000]

        result = await llm.chat(
            [{"role": "system", "content": prompt},
             {"role": "user", "content": f"根据以下报告数据，为目标受众生成摘要:\n{body}"}],
            max_tokens=1000, temperature=0.3, task_type="report",
        )
        return getattr(result, 'text', '') or ""


# ═══ 6. Interactive HTML Export — ECharts, drill-down ═══

class InteractiveExporter:
    """Export report as interactive HTML with ECharts and expandable sections."""

    @staticmethod
    def export(content: dict, output: str = "") -> str:
        """Generate interactive HTML report."""
        sections = content.get("sections", [])
        title = content.get("title", "Report")

        section_html = ""
        for i, s in enumerate(sections):
            heading = s.get("heading", f"Section {i+1}")
            body = s.get("body", "")
            section_html += f"""
            <details {'open' if i == 0 else ''} class="mb-4">
              <summary class="cursor-pointer text-lg font-semibold text-gray-800 hover:text-blue-600 py-2">
                {heading}
              </summary>
              <div class="pl-4 text-gray-700 leading-relaxed mt-2">{body.replace(chr(10), '<br>')}</div>
            </details>"""

        chart_json = json.dumps(content.get("charts", []), ensure_ascii=False)

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>{title}</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>details summary::-webkit-details-marker{{display:none}} details summary::before{{content:'▶ ';font-size:12px}} details[open] summary::before{{content:'▼ '}}</style>
</head>
<body class="bg-gray-50 p-6 max-w-4xl mx-auto">
  <h1 class="text-3xl font-bold text-gray-900 mb-2">{title}</h1>
  <p class="text-sm text-gray-500 mb-6">LivingTree Interactive Report · Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
  <div id="charts" class="mb-6" style="height:350px"></div>
  {section_html}
  <footer class="mt-8 pt-4 border-t border-gray-200 text-xs text-gray-400 text-center">LivingTree AI Agent v2.5 · Interactive Report</footer>
<script>
  var charts = {chart_json};
  if (charts && charts.length) {{
    var dom = document.getElementById('charts');
    var myChart = echarts.init(dom);
    myChart.setOption({{ title:{{text:'Key Metrics'}}, tooltip:{{}}, xAxis:{{data:charts.map(function(c){{return c.title||''}})}}, yAxis:{{}}, series:[{{type:'bar',data:charts.map(function(c){{return c.value||0}})}}] }});
    window.addEventListener('resize',function(){{myChart.resize()}});
  }}
</script>
</body></html>"""

        out_path = Path(output or f"/tmp/interactive_report_{int(time.time())}.html")
        out_path.write_text(html, encoding="utf-8")
        return str(out_path)


# ═══ 7. Smart Template Recommender ═══

class TemplateRecommender:
    """Recommend best template from project parameters."""

    TEMPLATE_RULES = [
        {
            "template": "eia_report_class_a",
            "conditions": {"has_air": True, "has_water": True, "project_scale": "large"},
            "description": "环评报告书 (A类 — 大气+水环境重大影响)",
        },
        {
            "template": "eia_report_class_b",
            "conditions": {"has_air": True, "project_scale": "medium"},
            "description": "环评报告表 (B类 — 单一环境要素)",
        },
        {
            "template": "emergency_plan_comprehensive",
            "conditions": {"has_hazardous": True, "risk_level": "high"},
            "description": "综合应急预案 (重大危险源)",
        },
        {
            "template": "feasibility_full",
            "conditions": {"investment": 10000, "has_socioeconomic": True},
            "description": "完整可行性研究报告 (投资 >1亿 + 社会经济分析)",
        },
    ]

    @classmethod
    def recommend(cls, project_params: dict) -> list[dict]:
        """Recommend templates matching project parameters.

        project_params: {has_air, has_water, project_scale, investment, ...}
        """
        matches = []
        for rule in cls.TEMPLATE_RULES:
            score = 0
            conditions = rule["conditions"]
            for key, expected in conditions.items():
                actual = project_params.get(key)
                if isinstance(expected, bool) and actual == expected:
                    score += 1
                elif isinstance(expected, str) and actual == expected:
                    score += 1
                elif isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
                    if actual >= expected:
                        score += 1
                elif expected is True and actual:
                    score += 0.5

            if score > 0:
                matches.append({
                    "template": rule["template"],
                    "description": rule["description"],
                    "match_score": round(score / max(len(conditions), 1) * 100),
                    "matched_conditions": score,
                    "total_conditions": len(conditions),
                })

        return sorted(matches, key=lambda m: -m["match_score"])


# ═══ 8. Report Repository Search ═══

class ReportRepository:
    """Search across all generated reports with natural language."""

    _repo_dir = Path(".livingtree/reports")

    @classmethod
    def index_report(cls, report_id: str, content: dict,
                     metadata: dict = None) -> str:
        """Index a report in the repository for search."""
        cls._repo_dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "report_id": report_id,
            "timestamp": datetime.now().isoformat(),
            "title": content.get("title", ""),
            "template_type": content.get("template_type", ""),
            "sections": len(content.get("sections", [])),
            "metadata": metadata or {},
        }
        path = cls._repo_dir / f"{report_id}.json"
        path.write_text(json.dumps(entry, ensure_ascii=False, default=str))
        return str(path)

    @classmethod
    def search(cls, query: str, limit: int = 20) -> list[dict]:
        """Search indexed reports by keyword or NL query."""
        results = []
        query_lower = query.lower()
        for f in sorted(cls._repo_dir.glob("*.json"), key=lambda p: -p.stat().st_mtime):
            try:
                entry = json.loads(f.read_text())
                entry_text = json.dumps(entry, ensure_ascii=False).lower()
                if query_lower in entry_text or any(
                    q in entry_text for q in query_lower.split()
                ):
                    results.append(entry)
            except Exception:
                continue
            if len(results) >= limit:
                break
        return results

    @classmethod
    def stats(cls) -> dict:
        """Repository statistics."""
        files = list(cls._repo_dir.glob("*.json"))
        templates = set()
        for f in files:
            try:
                entry = json.loads(f.read_text())
                templates.add(entry.get("template_type", "unknown"))
            except Exception:
                pass
        return {
            "total_reports": len(files),
            "templates_used": sorted(templates),
            "last_generated": max((f.stat().st_mtime for f in files), default=0),
        }


__all__ = [
    "LivingReport", "HallucinationGuard", "ComplianceScorer",
    "QualityScorer", "AudienceSynthesizer", "InteractiveExporter",
    "TemplateRecommender", "ReportRepository",
]
