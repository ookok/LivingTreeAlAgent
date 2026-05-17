"""Listed Company Intelligence — regulatory signals → economic inference.

Objective: Based on PUBLIC government announcements only, infer economic
signals for listed companies. For internal analysis purposes.

Method:
  Announcement → Match listed company → Infer economic implication
  e.g. "亚威变压器 环评批复" → Stock: 002559 (亚威股份) → 扩张信号 → 产能提升预期

Key principles:
  1. All data from PUBLIC government announcements (环评/招标/验收公告)
  2. Company matching: fuzzy name match announcement → listed company registry
  3. Signal types: expansion, capacity, pipeline, compliance, risk
  4. Confidence scoring: how strong is the match + signal
  5. Time-weighted: recent signals > old signals
  6. Peer comparison: same-industry companies benchmarked together

DISCLAIMER: This is for internal objective analysis only based on public data.
Not financial advice. All inferences are clearly marked as "推测" (inference).
"""
# DEPRECATED — candidate for removal. No active references found.


from __future__ import annotations

import hashlib
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


# ═══ Listed Company Registry ═══

@dataclass
class ListedCompany:
    """A publicly listed company tracked by the system."""
    name: str                    # full company name
    short_name: str = ""         # short name / brand name
    stock_code: str = ""         # e.g. "002559", "600519"
    exchange: str = ""           # "SZ" / "SH" / "HK" / "US"
    industry: str = ""           # "电气设备", "环保", "化工", etc.
    sub_industry: str = ""
    market_cap_category: str = ""  # "大型" (>500亿), "中型" (100-500亿), "小型" (<100亿)
    keywords: list[str] = field(default_factory=list)  # keywords for fuzzy matching

    @property
    def full_code(self) -> str:
        return f"{self.stock_code}.{self.exchange}" if self.exchange else self.stock_code


# ═══ Signal Types ═══

@dataclass
class EconomicSignal:
    """One economic signal inferred from an announcement."""
    id: str
    company: ListedCompany
    announcement_title: str
    announcement_date: str
    signal_type: str             # "expansion", "capacity", "pipeline", "compliance", "risk"
    confidence: float = 0.5
    inference: str = ""          # objective inference text
    estimated_impact: str = ""   # "正面" / "负面" / "中性"
    time_decay_factor: float = 1.0
    source_url: str = ""


# ═══ Pre-built Listed Company Registry (public data) ═══

LISTED_COMPANIES: dict[str, ListedCompany] = {
    # 电气设备 / 变压器
    "亚威股份": ListedCompany(
        name="江苏亚威机床股份有限公司", short_name="亚威股份",
        stock_code="002559", exchange="SZ", industry="机械设备", sub_industry="机床/变压器",
        keywords=["亚威", "亚威机床", "亚威变压器"],
    ),
    "特变电工": ListedCompany(
        name="特变电工股份有限公司", short_name="特变电工",
        stock_code="600089", exchange="SH", industry="电气设备", sub_industry="变压器",
        keywords=["特变电工", "特变"],
    ),
    "中国西电": ListedCompany(
        name="中国西电电气股份有限公司", short_name="中国西电",
        stock_code="601179", exchange="SH", industry="电气设备", sub_industry="输变电",
        keywords=["西电", "中国西电"],
    ),
    # 环保 / 环评相关
    "高能环境": ListedCompany(
        name="北京高能时代环境技术股份有限公司", short_name="高能环境",
        stock_code="603588", exchange="SH", industry="环保", sub_industry="环境治理",
        keywords=["高能环境", "高能时代"],
    ),
    "清新环境": ListedCompany(
        name="北京清新环境技术股份有限公司", short_name="清新环境",
        stock_code="002573", exchange="SZ", industry="环保", sub_industry="大气治理",
        keywords=["清新环境", "清新"],
    ),
    "碧水源": ListedCompany(
        name="北京碧水源科技股份有限公司", short_name="碧水源",
        stock_code="300070", exchange="SZ", industry="环保", sub_industry="水处理",
        keywords=["碧水源"],
    ),
    # 环境监测
    "聚光科技": ListedCompany(
        name="聚光科技(杭州)股份有限公司", short_name="聚光科技",
        stock_code="300203", exchange="SZ", industry="仪器仪表", sub_industry="环境监测",
        keywords=["聚光科技", "聚光"],
    ),
    "先河环保": ListedCompany(
        name="河北先河环保科技股份有限公司", short_name="先河环保",
        stock_code="300137", exchange="SZ", industry="仪器仪表", sub_industry="环境监测",
        keywords=["先河环保", "先河"],
    ),
    # 化工/制造
    "万华化学": ListedCompany(
        name="万华化学集团股份有限公司", short_name="万华化学",
        stock_code="600309", exchange="SH", industry="化工", sub_industry="聚氨酯",
        keywords=["万华化学", "万华"],
    ),
    "恒力石化": ListedCompany(
        name="恒力石化股份有限公司", short_name="恒力石化",
        stock_code="600346", exchange="SH", industry="化工", sub_industry="石化",
        keywords=["恒力石化", "恒力"],
    ),
    # 固废/危废处理
    "东江环保": ListedCompany(
        name="东江环保股份有限公司", short_name="东江环保",
        stock_code="002672", exchange="SZ", industry="环保", sub_industry="危废处理",
        keywords=["东江环保", "东江"],
    ),
    "格林美": ListedCompany(
        name="格林美股份有限公司", short_name="格林美",
        stock_code="002340", exchange="SZ", industry="环保", sub_industry="资源回收",
        keywords=["格林美"],
    ),
    # 建筑/工程
    "中国建筑": ListedCompany(
        name="中国建筑股份有限公司", short_name="中国建筑",
        stock_code="601668", exchange="SH", industry="建筑装饰", sub_industry="房建/基建",
        keywords=["中国建筑", "中建"],
    ),
    "中国中铁": ListedCompany(
        name="中国中铁股份有限公司", short_name="中国中铁",
        stock_code="601390", exchange="SH", industry="建筑装饰", sub_industry="基建",
        keywords=["中国中铁", "中铁"],
    ),
    # 风电/新能源
    "金风科技": ListedCompany(
        name="新疆金风科技股份有限公司", short_name="金风科技",
        stock_code="002202", exchange="SZ", industry="电气设备", sub_industry="风电",
        keywords=["金风科技", "金风"],
    ),
    "明阳智能": ListedCompany(
        name="明阳智慧能源集团股份公司", short_name="明阳智能",
        stock_code="601615", exchange="SH", industry="电气设备", sub_industry="风电",
        keywords=["明阳智能", "明阳"],
    ),
}

REGISTRY_SIZE = len(LISTED_COMPANIES)


# ═══ Signal Detector ═══

class ListedCompanyIntel:
    """Public-data-driven economic signal detection for listed companies.

    Usage:
        intel = ListedCompanyIntel()
        signals = intel.detect(announcements)
        report = intel.generate_report(signals)
    """

    def __init__(self):
        self._companies = LISTED_COMPANIES

    def detect(self, announcements: list[dict]) -> list[EconomicSignal]:
        """Cross-reference announcements with listed companies and infer signals."""
        signals = []
        for item in announcements:
            title = item.get("title", "")
            date = item.get("date", "")
            stage = item.get("stage", "")

            matched = self._match_company(title)
            if not matched:
                continue

            signal_type, inference, impact = self._infer_signal_type(title, stage)

            signal = EconomicSignal(
                id=hashlib.md5(f"{matched.stock_code}_{date}_{title[:50]}".encode()).hexdigest()[:16],
                company=matched,
                announcement_title=title[:200],
                announcement_date=date,
                signal_type=signal_type,
                confidence=self._calc_confidence(matched, title),
                inference=inference,
                estimated_impact=impact,
                source_url=item.get("source_url", ""),
            )
            signals.append(signal)

        # Sort by confidence (strongest first)
        signals.sort(key=lambda s: -s.confidence)
        logger.info(
            "ListedCompanyIntel: %d signals from %d announcements (%d companies matched)",
            len(signals), len(announcements),
            len(set(s.company.stock_code for s in signals)),
        )
        return signals

    def generate_report(self, signals: list[EconomicSignal]) -> str:
        """Generate an objective economic signal report."""
        if not signals:
            return "本期未发现与上市公司相关的公告信号。"

        by_company = defaultdict(list)
        for s in signals:
            by_company[s.company.stock_code].append(s)

        lines = [
            "# 📊 上市公司公告信号分析 (基于公开数据客观推测)",
            f"生成时间: {time.strftime('%Y-%m-%d %H:%M')}",
            f"涉及上市公司: {len(by_company)}家",
            f"信号总数: {len(signals)}",
            "",
            "⚠️ 免责声明: 以下分析基于公开政府公告数据的客观推测，不构成投资建议。",
            "",
        ]

        for code, company_signals in sorted(by_company.items()):
            company = company_signals[0].company
            lines.append(f"## {company.short_name} ({company.full_code}) — {company.industry}")
            lines.append(f"  信号数: {len(company_signals)}")

            expansion = [s for s in company_signals if s.signal_type == "expansion"]
            pipeline = [s for s in company_signals if s.signal_type == "pipeline"]
            compliance = [s for s in company_signals if s.signal_type == "compliance"]

            if expansion:
                lines.append(f"  📈 扩张信号 ({len(expansion)}条):")
                for s in expansion[:3]:
                    lines.append(f"    - [{s.announcement_date}] {s.inference}")
                    lines.append(f"      置信度: {s.confidence:.0%} | {s.estimated_impact}")

            if pipeline:
                lines.append(f"  📋 业务储备 ({len(pipeline)}条):")
                for s in pipeline[:3]:
                    lines.append(f"    - [{s.announcement_date}] {s.inference}")

            if compliance:
                lines.append(f"  ✅ 合规进展 ({len(compliance)}条):")
                for s in compliance[:3]:
                    lines.append(f"    - [{s.announcement_date}] {s.inference}")

            lines.append("")

        # Peer comparison
        lines.append("## 行业对比")
        by_industry = defaultdict(list)
        for s in signals:
            by_industry[s.company.industry].append(s)
        for industry, ind_signals in sorted(by_industry.items()):
            companies = set(s.company.short_name for s in ind_signals)
            lines.append(f"- {industry}: {len(companies)}家公司 ({len(ind_signals)}条信号)")

        return "\n".join(lines)

    def get_peer_activity(self, stock_code: str) -> dict:
        """Get what peer companies (same industry) are doing."""
        company = None
        for c in self._companies.values():
            if c.stock_code == stock_code:
                company = c
                break
        if not company:
            return {"error": "Unknown stock code"}

        peers = [
            c for c in self._companies.values()
            if c.industry == company.industry and c.stock_code != stock_code
        ]
        return {
            "company": company.short_name,
            "industry": company.industry,
            "peer_count": len(peers),
            "peers": [{"name": p.short_name, "code": p.full_code} for p in peers],
        }

    @staticmethod
    def _match_company(title: str) -> Optional[ListedCompany]:
        """Fuzzy match announcement title to a listed company."""
        for company in LISTED_COMPANIES.values():
            for keyword in company.keywords:
                if keyword in title:
                    return company
        # Fallback: check company short name
        for company in LISTED_COMPANIES.values():
            if company.short_name in title:
                return company
        return None

    @staticmethod
    def _infer_signal_type(title: str, stage: str) -> tuple[str, str, str]:
        """Infer economic signal from announcement type."""
        if stage in ("受理公示", "审批批复"):
            if any(kw in title for kw in ("新建", "扩建", "新增")):
                return (
                    "expansion",
                    f"推测: 新/扩建项目获环评批复，预示产能扩张/业务拓展",
                    "正面",
                )
            return (
                "compliance",
                f"推测: 环评合规推进中，正常经营流程",
                "中性",
            )

        if stage == "招标公告":
            return (
                "pipeline",
                f"推测: 参与项目招标，反映业务获取能力和订单储备",
                "正面",
            )

        if stage == "验收公示":
            return (
                "capacity",
                f"推测: 项目通过环保验收，新产能即将释放",
                "正面",
            )

        return ("compliance", f"推测: 常规合规公告", "中性")

    @staticmethod
    def _calc_confidence(company: ListedCompany, title: str) -> float:
        """Calculate match confidence."""
        score = 0.3  # base
        # Exact keyword match
        for kw in company.keywords:
            if kw in title:
                score += 0.3
                if len(kw) >= 3:
                    score += 0.1
                break
        # Full name match = highest confidence
        if company.name in title:
            score = 0.9
        return min(0.95, score)

    def expand_registry(self, company: ListedCompany) -> None:
        """Add a new listed company to the registry."""
        self._companies[company.short_name] = company
        logger.info("ListedCompanyIntel: added %s (%s)", company.short_name, company.full_code)

    def get_registry_stats(self) -> dict:
        by_industry = defaultdict(int)
        for c in self._companies.values():
            by_industry[c.industry] += 1
        return {
            "total_companies": len(self._companies),
            "by_industry": dict(by_industry),
            "exchanges": list(set(c.exchange for c in self._companies.values())),
        }


# ═══ Singleton ═══

_intel: Optional[ListedCompanyIntel] = None

def get_listed_intel() -> ListedCompanyIntel:
    global _intel
    if _intel is None:
        _intel = ListedCompanyIntel()
    return _intel
