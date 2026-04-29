"""
合规性检查器 (Compliance Checker)
==============================

检查环评报告是否符合相关标准和规范。
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional


class ComplianceLevel(Enum):
    """合规等级"""
    PASS = "pass"           # 通过
    WARNING = "warning"     # 警告
    FAIL = "fail"          # 不合格
    INFO = "info"           # 提示


@dataclass
class ComplianceItem:
    """合规检查项"""
    item_id: str
    category: str                    # 检查类别
    name: str                         # 检查项名称
    description: str = ""             # 描述
    level: ComplianceLevel            # 合规等级
    standard: str = ""               # 依据标准
    actual_value: str = ""           # 实际值
    limit_value: str = ""            # 限值
    suggestion: str = ""             # 整改建议
    checked_at: datetime = field(default_factory=datetime.now)


class ComplianceChecker:
    """
    合规性检查器

    用法:
        checker = ComplianceChecker()

        # 执行合规检查
        results = await checker.check(
            project=project_config,
            data=extracted_data,
            calculation_results=calc_results
        )

        # 获取检查报告
        report = checker.generate_report(results)
    """

    def __init__(self):
        self._rules: list[dict] = []
        self._load_default_rules()

    def _load_default_rules(self) -> None:
        """加载默认规则"""
        # 大气污染物排放标准
        self._rules.extend([
            {
                "id": "air_emission_standard",
                "category": "大气污染物排放",
                "name": "颗粒物排放浓度",
                "standard": "GB 16297-1996",
                "limit": "120",
                "unit": "mg/m³"
            },
            {
                "id": "vocs_emission_standard",
                "category": "大气污染物排放",
                "name": "VOCs排放浓度",
                "standard": "GB 16297-1996",
                "limit": "60",
                "unit": "mg/m³"
            },
            {
                "id": "so2_emission_standard",
                "category": "大气污染物排放",
                "name": "二氧化硫排放浓度",
                "standard": "GB 16297-1996",
                "limit": "550",
                "unit": "mg/m³"
            },
            {
                "id": "nox_emission_standard",
                "category": "大气污染物排放",
                "name": "氮氧化物排放浓度",
                "standard": "GB 16297-1996",
                "limit": "240",
                "unit": "mg/m³"
            },
        ])

        # 水污染物排放标准
        self._rules.extend([
            {
                "id": "water_cod_standard",
                "category": "水污染物排放",
                "name": "COD排放浓度",
                "standard": "GB 8978-1996",
                "limit": "100",
                "unit": "mg/L"
            },
            {
                "id": "water_nh3_standard",
                "category": "水污染物排放",
                "name": "氨氮排放浓度",
                "standard": "GB 8978-1996",
                "limit": "15",
                "unit": "mg/L"
            },
            {
                "id": "water_ss_standard",
                "category": "水污染物排放",
                "name": "悬浮物排放浓度",
                "standard": "GB 8978-1996",
                "limit": "70",
                "unit": "mg/L"
            },
        ])

        # 噪声标准
        self._rules.extend([
            {
                "id": "noise_day_standard",
                "category": "噪声",
                "name": "昼间噪声（边界）",
                "standard": "GB 12348-2008",
                "limit": "65",
                "unit": "dB(A)"
            },
            {
                "id": "noise_night_standard",
                "category": "噪声",
                "name": "夜间噪声（边界）",
                "standard": "GB 12348-2008",
                "limit": "55",
                "unit": "dB(A)"
            },
        ])

        # 卫生防护距离
        self._rules.extend([
            {
                "id": "protection_distance",
                "category": "卫生防护距离",
                "name": "防护距离达标",
                "standard": "GB 11659-2011",
                "limit": "100",
                "unit": "m"
            },
        ])

        # 危险废物
        self._rules.extend([
            {
                "id": "hazardous_waste_storage",
                "category": "危险废物",
                "name": "危废暂存间",
                "standard": "GB 18597-2001",
                "limit": "50",
                "unit": "m²"
            },
        ])

    async def check(
        self,
        project,
        data: dict,
        calculation_results: dict
    ) -> list[dict]:
        """
        执行合规检查

        Args:
            project: 项目配置
            data: 提取的数据
            calculation_results: 计算结果

        Returns:
            list[dict]: 检查结果
        """
        results = []

        # 检查大气污染物
        air_sources = calculation_results.get("air_sources", [])
        results.extend(await self._check_air_pollution(air_sources))

        # 检查水污染物
        water_sources = calculation_results.get("water_sources", [])
        results.extend(await self._check_water_pollution(water_sources))

        # 检查噪声
        noise_sources = calculation_results.get("noise_sources", [])
        results.extend(await self._check_noise(noise_sources))

        # 检查卫生防护距离
        if "protection_zones" in data:
            results.extend(await self._check_protection_distance(data["protection_zones"]))

        # 检查一般项目要求
        results.extend(await self._check_general_requirements(project, data))

        return results

    async def _check_air_pollution(self, sources: list) -> list[dict]:
        """检查大气污染物"""
        results = []

        for source in sources:
            emission_rate = source.get("emission_rate", 0)

            # 颗粒物
            if emission_rate > 0:
                results.append({
                    "item_id": "air_emission_check",
                    "category": "大气污染物排放",
                    "name": f"{source.get('name', '污染源')}排放检查",
                    "level": "pass" if emission_rate < 100 else "warning",
                    "standard": "GB 16297-1996",
                    "actual_value": f"{emission_rate} g/s",
                    "limit_value": "满足排放要求",
                    "suggestion": "" if emission_rate < 100 else "建议加强废气治理"
                })

        return results

    async def _check_water_pollution(self, sources: list) -> list[dict]:
        """检查水污染物"""
        results = []

        for source in sources:
            concentration = source.get("concentration", 0)

            if concentration > 0:
                limit = 100  # COD
                level = "pass" if concentration <= limit else "fail"

                results.append({
                    "item_id": f"water_check_{source.get('source_id', 'unknown')}",
                    "category": "水污染物排放",
                    "name": f"{source.get('name', '污染源')}排放检查",
                    "level": level,
                    "standard": "GB 8978-1996",
                    "actual_value": f"COD {concentration} mg/L",
                    "limit_value": f"{limit} mg/L",
                    "suggestion": "" if level == "pass" else "需提高污水处理工艺"
                })

        return results

    async def _check_noise(self, sources: list) -> list[dict]:
        """检查噪声"""
        results = []

        for source in sources:
            level = source.get("predicted_level", 0)

            if level > 0:
                day_limit = 65
                night_limit = 55
                level_str = "pass" if level <= day_limit else "warning"

                results.append({
                    "item_id": f"noise_check_{source.get('source_id', 'unknown')}",
                    "category": "噪声",
                    "name": f"{source.get('name', '噪声源')}预测检查",
                    "level": level_str,
                    "standard": "GB 12348-2008",
                    "actual_value": f"{level} dB(A)",
                    "limit_value": f"昼间≤{day_limit} dB(A)",
                    "suggestion": "" if level <= day_limit else "建议增加隔声措施"
                })

        return results

    async def _check_protection_distance(self, zones: list) -> list[dict]:
        """检查防护距离"""
        results = []

        for zone in zones:
            distance = zone.get("distance", 0)

            if distance > 0:
                results.append({
                    "item_id": f"protection_{zone.get('zone_id', 'unknown')}",
                    "category": "卫生防护距离",
                    "name": f"防护距离检查",
                    "level": "pass" if distance <= 200 else "warning",
                    "standard": "GB 11659-2011",
                    "actual_value": f"{distance} m",
                    "limit_value": "满足要求",
                    "suggestion": "" if distance <= 200 else "防护距离不足，需调整布局"
                })

        return results

    async def _check_general_requirements(self, project, data: dict) -> list[dict]:
        """检查一般项目要求"""
        results = []

        # 项目选址
        if project.location:
            results.append({
                "item_id": "location_check",
                "category": "项目选址",
                "name": "建设地点合理性",
                "level": "info",
                "standard": "规划符合性",
                "actual_value": project.location,
                "limit_value": "符合规划",
                "suggestion": "建议核实选址符合性"
            })

        # 行业类别
        if project.industry:
            results.append({
                "item_id": "industry_check",
                "category": "行业类别",
                "name": "行业类别准确性",
                "level": "info",
                "standard": "国民经济行业分类",
                "actual_value": project.industry,
                "limit_value": "准确",
                "suggestion": ""
            })

        # 设备清单
        equipment = data.get("equipment_list", [])
        if len(equipment) > 0:
            results.append({
                "item_id": "equipment_check",
                "category": "工程分析",
                "name": "设备清单完整性",
                "level": "pass",
                "standard": "设备清单要求",
                "actual_value": f"共{len(equipment)}台/套",
                "limit_value": "完整",
                "suggestion": ""
            })

        # 工艺流程
        processes = data.get("processes", [])
        if len(processes) > 0:
            results.append({
                "item_id": "process_check",
                "category": "工程分析",
                "name": "工艺流程完整性",
                "level": "pass",
                "standard": "工艺流程要求",
                "actual_value": f"共{len(processes)}个工艺单元",
                "limit_value": "完整",
                "suggestion": ""
            })

        return results

    def generate_report(self, results: list[dict]) -> str:
        """
        生成合规检查报告

        Args:
            results: 检查结果

        Returns:
            str: HTML 报告
        """
        # 统计
        total = len(results)
        passed = len([r for r in results if r.get("level") == "pass"])
        warnings = len([r for r in results if r.get("level") == "warning"])
        failed = len([r for r in results if r.get("level") == "fail"])

        # 按类别分组
        by_category = {}
        for r in results:
            cat = r.get("category", "其他")
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(r)

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>合规性检查报告</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: "Microsoft YaHei", SimSun, serif;
            font-size: 14px;
            padding: 20mm;
            max-width: 210mm;
            margin: 0 auto;
        }}
        h1 {{ text-align: center; font-size: 24px; margin: 30px 0; }}
        .summary {{
            background: #f5f5f5;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            text-align: center;
        }}
        .summary-item {{ padding: 15px; }}
        .summary-item.total {{ background: #E3F2FD; }}
        .summary-item.passed {{ background: #E8F5E9; }}
        .summary-item.warning {{ background: #FFF3E0; }}
        .summary-item.failed {{ background: #FFEBEE; }}
        .summary-number {{ font-size: 32px; font-weight: bold; }}
        .category {{ margin: 30px 0; }}
        .category h2 {{ font-size: 18px; border-bottom: 2px solid #1976D2; padding-bottom: 5px; margin-bottom: 15px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
        th {{ background: #f5f5f5; }}
        .pass {{ color: #4CAF50; }}
        .warning {{ color: #FF9800; }}
        .fail {{ color: #F44336; }}
        .level-badge {{
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 12px;
        }}
        .level-pass {{ background: #E8F5E9; color: #4CAF50; }}
        .level-warning {{ background: #FFF3E0; color: #FF9800; }}
        .level-fail {{ background: #FFEBEE; color: #F44336; }}
        .level-info {{ background: #E3F2FD; color: #1976D2; }}
    </style>
</head>
<body>
    <h1>📋 合规性检查报告</h1>

    <div class="summary">
        <div class="summary-grid">
            <div class="summary-item total">
                <div class="summary-number">{total}</div>
                <div>检查项总数</div>
            </div>
            <div class="summary-item passed">
                <div class="summary-number">{passed}</div>
                <div>合格</div>
            </div>
            <div class="summary-item warning">
                <div class="summary-number">{warnings}</div>
                <div>警告</div>
            </div>
            <div class="summary-item failed">
                <div class="summary-number">{failed}</div>
                <div>不合格</div>
            </div>
        </div>
    </div>
"""

        for category, items in by_category.items():
            html += f"""
    <div class="category">
        <h2>{category}</h2>
        <table>
            <thead>
                <tr>
                    <th>检查项</th>
                    <th>依据标准</th>
                    <th>实际值</th>
                    <th>限值</th>
                    <th>状态</th>
                    <th>建议</th>
                </tr>
            </thead>
            <tbody>
"""

            for item in items:
                level = item.get("level", "info")
                level_class = f"level-{level}"
                level_text = {"pass": "合格", "warning": "警告", "fail": "不合格", "info": "提示"}.get(level, level)

                html += f"""
                <tr>
                    <td>{item.get('name', '')}</td>
                    <td>{item.get('standard', '-')}</td>
                    <td>{item.get('actual_value', '-')}</td>
                    <td>{item.get('limit_value', '-')}</td>
                    <td><span class="level-badge {level_class}">{level_text}</span></td>
                    <td>{item.get('suggestion', '-')}</td>
                </tr>
"""

            html += """
            </tbody>
        </table>
    </div>
"""

        html += f"""
    <div style="margin-top: 30px; text-align: right;">
        <p>检查时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
    </div>
</body>
</html>
"""

        return html

    def get_summary(self, results: list[dict]) -> dict:
        """获取检查摘要"""
        return {
            "total": len(results),
            "passed": len([r for r in results if r.get("level") == "pass"]),
            "warnings": len([r for r in results if r.get("level") == "warning"]),
            "failed": len([r for r in results if r.get("level") == "fail"]),
            "pass_rate": round(len([r for r in results if r.get("level") == "pass"]) / max(len(results), 1) * 100, 1)
        }


async def check_compliance(project, data: dict, calculation_results: dict) -> list[dict]:
    """便捷函数：执行合规检查"""
    checker = ComplianceChecker()
    return await checker.check(project, data, calculation_results)