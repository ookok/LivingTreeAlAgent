"""User Profile Engine — deep profile construction + competitor tracking.

Builds a rich user profile from collected data + self-learning:
  - Company metrics (revenue, employees, qualification level)
  - Service capabilities (domains, geographic radius, pricing)
  - Bidding history (won/lost, price range, competitors)
  - Competitor intelligence (who bids on same projects, their win rate)
  - Idle capacity (current parallel projects)

This drives ALL downstream engines (scoring, bidding, pricing, investment).
"""

from __future__ import annotations

import json
import os
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class UserProfile:
    """Complete user/company profile for market intelligence."""
    company_name: str = ""
    role: str = ""                    # eia_engineer, env_engineer, etc.

    # Company metrics
    annual_revenue: str = ""          # e.g. "500-1000万"
    employee_count: int = 0
    qualification_level: str = ""     # 甲级/乙级/丙级
    service_radius: str = ""          # "省内" / "全国" / "本地市"
    established_year: int = 0

    # Capabilities
    service_domains: list[str] = field(default_factory=list)  # [大气, 水, 噪声, 生态]
    avg_bidding_price: str = ""       # "10-50万"
    price_range: tuple[float, float] = (0.0, 0.0)  # (min, max)

    # Activity
    projects_won: int = 0
    projects_lost: int = 0
    total_revenue_generated: float = 0.0  # 万元
    known_competitors: list[str] = field(default_factory=list)
    idle_capacity: int = 0            # how many more projects can handle

    # Learning
    profile_confidence: float = 0.3   # increases as more data collected
    last_updated: str = ""
    data_sources: list[str] = field(default_factory=list)


@dataclass
class Competitor:
    """A known competitor extracted from announcements."""
    name: str
    domains: list[str] = field(default_factory=list)
    win_count: int = 0
    total_bids: int = 0
    avg_price: float = 0.0
    first_seen: str = ""
    last_seen: str = ""
    threat_level: str = "low"  # "high" / "medium" / "low"

    @property
    def win_rate(self) -> float:
        return self.win_count / max(self.total_bids, 1)


class UserProfileEngine:
    """Deep user profile builder + competitor intelligence.

    Usage:
        engine = UserProfileEngine()
        profile = engine.build("环评工程师", collected_data)
        engine.update(profile, new_announcement)
        engine.analyze_competitors(profile)
    """

    def __init__(self, data_dir: str = ""):
        self._data_dir = data_dir or os.path.expanduser("~/.livingtree/profiles")
        os.makedirs(self._data_dir, exist_ok=True)
        self._competitors: dict[str, Competitor] = {}

    def build(self, role: str, collected_data: list[dict] = None) -> UserProfile:
        """Build or load a user profile."""
        profile = self._load(role) or UserProfile(role=role)

        if collected_data:
            for item in collected_data:
                self._ingest_item(profile, item)

        profile.profile_confidence = min(1.0, profile.profile_confidence + 0.1)
        profile.last_updated = time.strftime("%Y-%m-%d %H:%M")
        self._save(profile)
        return profile

    def update(self, profile: UserProfile, announcement: dict) -> None:
        """Update profile from a new announcement."""
        self._ingest_item(profile, announcement)
        profile.last_updated = time.strftime("%Y-%m-%d %H:%M")
        self._save(profile)

    def analyze_competitors(self, announcements: list[dict]) -> list[Competitor]:
        """Extract and analyze competitors from announcement data."""
        for item in announcements:
            title = item.get("title", "")
            status = item.get("status", "")
            # Look for company names in approval/winning contexts
            if status in ("审批批复", "已批", "中标"):
                companies = self._extract_company_names(title)
                for company in companies:
                    if company not in self._competitors:
                        self._competitors[company] = Competitor(
                            name=company,
                            first_seen=item.get("date", ""),
                        )
                    comp = self._competitors[company]
                    comp.last_seen = item.get("date", comp.last_seen)
                    comp.total_bids += 1

        # Calculate threat levels
        for comp in self._competitors.values():
            if comp.win_rate > 0.5 or comp.win_count >= 3:
                comp.threat_level = "high"
            elif comp.win_rate > 0.2:
                comp.threat_level = "medium"

        return sorted(self._competitors.values(), key=lambda c: -c.win_count)

    def get_competitor_report(self, profile: UserProfile) -> str:
        comps = self.analyze_competitors([])
        lines = ["## 竞争对手情报"]
        for c in comps[:10]:
            icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}[c.threat_level]
            lines.append(
                f"{icon} {c.name}: 中标{c.win_count}次/{c.total_bids}次 "
                f"(中标率{c.win_rate:.0%}) 均价{c.avg_price:.0f}万"
            )
        return "\n".join(lines) if comps else "暂未发现竞争对手"

    def get_capacity_report(self, profile: UserProfile) -> str:
        lines = [
            f"## {profile.company_name or '用户'} 产能分析",
            f"已中标: {profile.projects_won}个项目",
            f"预计空闲产能: {profile.idle_capacity}个项目",
            f"建议安全容量: {profile.projects_won + profile.idle_capacity}个项目",
        ]
        if profile.idle_capacity > 0:
            lines.append(f"⚡ 可承接新项目: {profile.idle_capacity}个")
        if profile.projects_won >= 5:
            lines.append("⚠️ 项目较多，建议评估是否需扩产")
        return "\n".join(lines)

    def _ingest_item(self, profile: UserProfile, item: dict) -> None:
        title = item.get("title", "")
        status = item.get("status", "")
        date = item.get("date", "")

        if status in ("审批批复", "已批"):
            profile.projects_won = max(profile.projects_won, profile.projects_won + 1)
        if status == "招标公告":
            profile.idle_capacity = max(0, 5 - profile.projects_won)

        # Domain detection
        domains = []
        if "大气" in title or "废气" in title: domains.append("大气")
        if "水" in title or "废水" in title: domains.append("水")
        if "噪声" in title: domains.append("噪声")
        if "生态" in title: domains.append("生态")
        if "固废" in title: domains.append("固废")
        for d in domains:
            if d not in profile.service_domains:
                profile.service_domains.append(d)

        # Revenue estimation from project descriptions
        if "亿" in title:
            profile.annual_revenue = "1亿+"
        elif "千万" in title or "万" in title:
            profile.annual_revenue = "1000-5000万"

        if not profile.data_sources:
            profile.data_sources.append("announcement_analysis")

    @staticmethod
    def _extract_company_names(title: str) -> list[str]:
        patterns = [
            r'([\u4e00-\u9fff]{3,20}(?:有限|股份|集团|科技|环保|环境|工程|检测|咨询)公司)',
            r'([\u4e00-\u9fff]{2,10}(?:院|所|中心|站))',
        ]
        results = []
        for pat in patterns:
            results.extend(re.findall(pat, title))
        return list(set(results))

    def _load(self, role: str) -> Optional[UserProfile]:
        path = os.path.join(self._data_dir, f"{role}.json")
        try:
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                return UserProfile(**{k: v for k, v in data.items() if k in UserProfile.__dataclass_fields__})
        except Exception:
            pass
        return None

    def _save(self, profile: UserProfile) -> None:
        path = os.path.join(self._data_dir, f"{profile.role}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({k: v for k, v in profile.__dict__.items() if not k.startswith("_")},
                         f, indent=2, ensure_ascii=False)
        except Exception:
            pass


# Singleton
_profile_engine: Optional[UserProfileEngine] = None

def get_profile_engine() -> UserProfileEngine:
    global _profile_engine
    if _profile_engine is None:
        _profile_engine = UserProfileEngine()
    return _profile_engine
