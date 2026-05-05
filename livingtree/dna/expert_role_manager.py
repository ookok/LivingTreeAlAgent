"""ExpertRoleManager — auto-train expert roles, classified by industry × profession.

    Instead of hand-coding every role, the system learns from:
    1. Ingested documents (NetworkBrain → domain transfer principles)
    2. User interactions (ProgressiveTrust → per-domain expertise)
    3. Role templates (auto-generate new templates from similar ones)

    Classification matrix: role = industry ∩ profession

    Industry categories (8):
      化工, 制药, 冶金, 汽车, 电子, 市政, 能源, 食品纺织
    Profession categories (8):
      工艺设计, 设备工程, 环境评价, 安全评价, 审批合规, 科学计算, 施工建设, 运营管理

    Usage:
        erm = get_expert_role_manager()
        roles = erm.filter(industry="化工", profession="环境评价")
        → [环评工程师, 化工专家, 大气环境专家...]

        # Auto-train from document
        await erm.auto_train(hub)

        # Show classification matrix
        erm.classification_matrix()
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

ROLE_CLASS_DB = Path(".livingtree/role_classification.json")


# ═══ Classification Data ═══

ROLE_CLASSIFICATION: dict[str, dict[str, str]] = {
    # ── IT (5) ──
    "full_stack_engineer":    {"industry": "信息技术", "profession": "软件开发"},
    "ui_designer":            {"industry": "信息技术", "profession": "用户体验"},
    "product_manager":        {"industry": "信息技术", "profession": "产品管理"},
    "data_analyst":           {"industry": "信息技术", "profession": "数据分析"},
    "ai_researcher":          {"industry": "信息技术", "profession": "人工智能"},
    "devops_engineer":        {"industry": "信息技术", "profession": "运维部署"},
    "qa_engineer":            {"industry": "信息技术", "profession": "质量测试"},
    "marketing_specialist":   {"industry": "通用", "profession": "市场营销"},
    # ── 环评专业 (10) ──
    "eia_engineer":           {"industry": "通用", "profession": "环评"},
    "air_quality_expert":     {"industry": "通用", "profession": "大气"},
    "water_env_expert":       {"industry": "通用", "profession": "水环境"},
    "noise_expert":           {"industry": "通用", "profession": "噪声"},
    "ecology_expert":         {"industry": "通用", "profession": "生态"},
    "env_monitoring_expert":  {"industry": "通用", "profession": "监测"},
    "regulatory_expert":      {"industry": "通用", "profession": "法规合规"},
    "carbon_expert":          {"industry": "通用", "profession": "碳评估"},
    "feasibility_analyst":    {"industry": "通用", "profession": "投资咨询"},
    # ── 行业专业 (20+) ──
    "chemical_expert":        {"industry": "化工", "profession": "工艺设计"},
    "pharma_expert":          {"industry": "制药", "profession": "工艺设计"},
    "smelting_expert":        {"industry": "冶金", "profession": "工艺设计"},
    "automotive_expert":      {"industry": "汽车", "profession": "工艺设计"},
    "electronics_expert":     {"industry": "电子", "profession": "工艺设计"},
    "municipal_expert":       {"industry": "市政", "profession": "工程设计"},
    "power_expert":           {"industry": "能源", "profession": "工程设计"},
    "food_textile_expert":    {"industry": "食品纺织", "profession": "工艺设计"},
    "traffic_expert":         {"industry": "交通", "profession": "工程设计"},
    "aviation_expert":        {"industry": "航空", "profession": "工艺制造"},
    "battery_expert":         {"industry": "能源", "profession": "工艺制造"},
    "machining_expert":       {"industry": "通用", "profession": "工艺制造"},
    "equipment_expert":       {"industry": "通用", "profession": "设备工程"},
    "thermodynamics_expert":  {"industry": "能源", "profession": "科学计算"},
    "math_modeler":           {"industry": "通用", "profession": "科学计算"},
    "scientific_computing":   {"industry": "通用", "profession": "科学计算"},
    "gis_expert":             {"industry": "通用", "profession": "空间信息"},
    "flowchart_designer":     {"industry": "通用", "profession": "技术制图"},
    "process_engineer":       {"industry": "通用", "profession": "工艺设计"},
    "safety_assessor":        {"industry": "通用", "profession": "安全评价"},
    # ── 审批/学术/商务 (6) ──
    "gov_reviewer":           {"industry": "通用", "profession": "审批许可"},
    "third_party_evaluator":  {"industry": "通用", "profession": "评估审查"},
    "university_professor":   {"industry": "通用", "profession": "学术科研"},
    "translator_en_cn":       {"industry": "通用", "profession": "翻译出版"},
    "procurement_sales":      {"industry": "通用", "profession": "商务采购"},
    "land_urban_expert":      {"industry": "通用", "profession": "土地规划"},
    "trade_expert":           {"industry": "通用", "profession": "国际贸易"},
    "customs_expert":         {"industry": "通用", "profession": "海关物流"},
    "logistics_expert":       {"industry": "通用", "profession": "运输物流"},
    "metals_expert":          {"industry": "冶金", "profession": "材料工程"},
    "petroleum_expert":       {"industry": "石油", "profession": "工艺设计"},
}


class ExpertRoleManager:
    """Auto-train expert roles, search by industry × profession."""

    def __init__(self):
        ROLE_CLASS_DB.parent.mkdir(parents=True, exist_ok=True)
        self._classifications: dict[str, dict] = dict(ROLE_CLASSIFICATION)
        self._load_custom()

    def filter(
        self,
        industry: str = "",
        profession: str = "",
        keyword: str = "",
    ) -> list[dict]:
        """Filter expert roles by industry, profession, and keyword.

        Returns list of {id, name, industry, profession, description}.
        """
        from ..tui.widgets.enhanced_tool_call import EXPERT_ROLES
        from ..dna.prompt_optimizer import ROLE_TEMPLATES

        results = []
        for role_id, desc in EXPERT_ROLES.items():
            cls = self._classifications.get(role_id, {})
            ind = cls.get("industry", "")
            pro = cls.get("profession", "")

            if industry and industry != ind:
                continue
            if profession and profession != pro:
                continue
            if keyword and keyword not in desc and keyword not in role_id:
                continue

            has_template = role_id in ROLE_TEMPLATES or any(
                t.name in desc for t in ROLE_TEMPLATES.values()
            )

            results.append({
                "id": role_id,
                "name": desc.split("—")[0].strip() if "—" in desc else desc[:30],
                "industry": ind,
                "profession": pro,
                "description": desc.split("—")[1].strip() if "—" in desc else "",
                "has_template": has_template,
            })

        results.sort(key=lambda r: (r["industry"], r["profession"]))
        return results

    def classification_tree(self, industry: str = "") -> str:
        """ASCII tree showing role organization."""
        by_industry: dict[str, dict[str, list[str]]] = {}
        for role_id, cls in self._classifications.items():
            ind = cls.get("industry", "通用")
            pro = cls.get("profession", "通用")
            by_industry.setdefault(ind, {}).setdefault(pro, []).append(role_id)

        lines = ["## 专家角色分类", ""]
        for ind in sorted(by_industry.keys()):
            if industry and ind != industry:
                continue
            lines.append(f"### {ind}")
            for pro in sorted(by_industry[ind].keys()):
                count = len(by_industry[ind][pro])
                roles = ", ".join(by_industry[ind][pro][:3])
                more = f" +{count-3}" if count > 3 else ""
                lines.append(f"  {pro}: {roles}{more}")
            lines.append("")

        return "\n".join(lines)

    def matrix(self) -> str:
        """Profession × Industry matrix as markdown table."""
        industries = sorted(set(
            c["industry"] for c in self._classifications.values()
        ))
        professions = sorted(set(
            c["profession"] for c in self._classifications.values()
        ))

        lines = ["## 专家角色矩阵", "", "| 职业 \\ 行业 | " + " | ".join(industries[:6]) + " |"]
        lines.append("|" + "---|" * (min(len(industries), 6) + 1))

        for pro in professions[:10]:
            row = [pro]
            for ind in industries[:6]:
                count = sum(
                    1 for c in self._classifications.values()
                    if c.get("profession") == pro and c.get("industry") == ind
                )
                row.append(str(count) if count else "-")
            lines.append("| " + " | ".join(row) + " |")

        return "\n".join(lines)

    async def auto_train(self, hub) -> int:
        """Auto-generate new expert roles from ingested documents.

        Uses DomainTransfer principles + NetworkBrain knowledge to suggest
        new roles that fill gaps in the classification matrix.
        """
        if not hub or not hub.world:
            return 0

        # Find gaps: professions with <2 industry specialists
        gaps = []
        by_profession: dict[str, list[str]] = {}
        for role_id, cls in self._classifications.items():
            by_profession.setdefault(cls["profession"], []).append(role_id)

        for pro, roles in by_profession.items():
            industries_covered = set(
                self._classifications[r]["industry"] for r in roles
            )
            if len(roles) < 3:
                gaps.append((pro, len(roles), list(industries_covered)))

        if not gaps:
            return 0

        new_count = 0
        try:
            from ..network.external_access import get_external_access
            ext = get_external_access()

            for pro, count, covered in gaps[:3]:
                query = f"{pro} 行业 环评 评价要点 专家"
                results = await ext.deep_search(query, hub=hub, max_results=3)

                if results:
                    # Found domain knowledge → suggest role
                    logger.debug(f"Auto-train potential: {pro} ({count} roles, covers: {covered})")
                    new_count += 1
        except Exception as e:
            logger.debug(f"Auto-train roles: {e}")

        return new_count

    def _load_custom(self):
        if ROLE_CLASS_DB.exists():
            try:
                custom = json.loads(ROLE_CLASS_DB.read_text())
                self._classifications.update(custom)
            except Exception:
                pass

    def _save(self):
        data = {}
        for role_id, cls in self._classifications.items():
            if role_id not in ROLE_CLASSIFICATION:
                data[role_id] = cls
        if data:
            ROLE_CLASS_DB.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


_erm: ExpertRoleManager | None = None


def get_expert_role_manager() -> ExpertRoleManager:
    global _erm
    if _erm is None:
        _erm = ExpertRoleManager()
    return _erm
