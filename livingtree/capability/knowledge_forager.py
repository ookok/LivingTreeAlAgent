"""Knowledge Forager — AI's autonomous food chain for government announcements.

Four integrated capabilities:
  1. AUTO-PATROL:    Scheduled scanning of registered sites, change detection
  2. AUTO-GRAPH:     Entity extraction (project/company/standard/date) + relationship network
  3. SUCCESSION:     Multi-stage timeline tracking (受理→拟批→批复→验收)
  4. DAILY BRIEF:    Auto-generated morning intelligence report

Design philosophy:
  The Forager is the AI's "food gathering" system. It doesn't wait for
  user queries — it actively hunts, digests, and connects knowledge.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import threading
import time
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


# ═══ 1. Food Map — Registered site registry ═══

@dataclass
class FoodSource:
    """A registered knowledge source (site) on the food map."""
    domain: str
    url: str
    category: str = "env"           # env / infra / policy / tech
    scan_interval_hours: int = 24
    last_scan: float = 0.0
    last_item_count: int = 0
    item_fingerprints: set = field(default_factory=set)
    priority: int = 0               # higher = scan first
    enabled: bool = True
    notes: str = ""


# ═══ 2. Auto-Graph — Entity relationship network ═══

@dataclass
class EntityNode:
    """A node in the knowledge graph."""
    id: str
    name: str
    entity_type: str  # "project", "company", "standard", "location", "date", "status"
    aliases: list[str] = field(default_factory=list)
    occurrences: int = 1
    first_seen: str = ""
    last_seen: str = ""


@dataclass
class EntityRelation:
    """A relationship between two entities."""
    source_id: str
    target_id: str
    relation_type: str  # "submitted_by", "approved_on", "references_standard", "located_in", "preceded_by"
    evidence: str = ""  # the announcement text that supports this relation
    confidence: float = 1.0


@dataclass
class KnowledgeGraph:
    """Entity-relationship network built from announcements."""
    nodes: dict[str, EntityNode] = field(default_factory=dict)
    relations: list[EntityRelation] = field(default_factory=list)

    def add_entity(self, name: str, entity_type: str, occurrence_date: str = "") -> str:
        eid = hashlib.md5(f"{name}:{entity_type}".encode()).hexdigest()[:12]
        if eid in self.nodes:
            node = self.nodes[eid]
            node.occurrences += 1
            node.last_seen = occurrence_date or node.last_seen
        else:
            self.nodes[eid] = EntityNode(
                id=eid, name=name, entity_type=entity_type,
                first_seen=occurrence_date, last_seen=occurrence_date,
            )
        return eid

    def add_relation(self, source: str, target: str, rel_type: str, evidence: str = "") -> None:
        sid = self._find_entity_id(source)
        tid = self._find_entity_id(target)
        if not sid or not tid:
            return
        self.relations.append(EntityRelation(
            source_id=sid, target_id=tid, relation_type=rel_type, evidence=evidence[:200],
        ))

    def _find_entity_id(self, name: str) -> Optional[str]:
        """Find entity node ID by name (fuzzy match)."""
        for eid, node in self.nodes.items():
            if node.name == name or name in node.name or node.name in name:
                return eid
        return None

    def query(self, entity_name: str, entity_type: str = "") -> dict:
        """Query all relations for an entity."""
        eid = hashlib.md5(f"{entity_name}:{entity_type}".encode()).hexdigest()[:12]
        related = []
        for rel in self.relations:
            if rel.source_id == eid:
                target = self.nodes.get(rel.target_id)
                if target:
                    related.append(f"{rel.relation_type} → {target.name}")
            elif rel.target_id == eid:
                source = self.nodes.get(rel.source_id)
                if source:
                    related.append(f"← {rel.relation_type} from {source.name}")
        return {"entity": entity_name, "relations": related}


# ═══ 3. Succession — Project timeline tracker ═══

@dataclass
class ProjectStage:
    """One stage in a project's approval lifecycle."""
    stage: str           # "受理公示", "拟批准公示", "审批批复", "验收公示", "招标公告"
    date: str
    source_url: str
    summary: str = ""
    attachments: list[str] = field(default_factory=list)


@dataclass
class ProjectTimeline:
    """Complete lifecycle tracking for one project."""
    project_id: str
    project_name: str
    company: str = ""
    location: str = ""
    stages: list[ProjectStage] = field(default_factory=list)
    first_seen: str = ""
    last_seen: str = ""
    total_days: int = 0        # days from first to last stage


class SuccessionTracker:
    """Tracks projects across multiple announcement stages.

    Merges same-company/same-project announcements into timelines.
    Detects stage transitions (受理→拟批→批复→验收).
    """

    STAGE_ORDER = ["招标公告", "受理公示", "拟批准公示", "审批批复", "验收公示"]

    def __init__(self):
        self._timelines: dict[str, ProjectTimeline] = {}
        self._name_index: dict[str, str] = {}  # normalized name → project_id

    def ingest(self, title: str, date: str, source_url: str,
               attachments: list[str] = None) -> ProjectTimeline:
        """Ingest an announcement and link it to its project timeline."""
        pid = self._find_or_create_project(title)
        timeline = self._timelines[pid]

        stage = self._detect_stage(title)
        timeline.stages.append(ProjectStage(
            stage=stage, date=date, source_url=source_url,
            summary=title[:200], attachments=attachments or [],
        ))
        timeline.stages.sort(key=lambda s: s.date)

        if not timeline.first_seen or date < timeline.first_seen:
            timeline.first_seen = date
        timeline.last_seen = date

        if len(timeline.stages) >= 2:
            d1 = self._parse_date(timeline.first_seen)
            d2 = self._parse_date(timeline.last_seen)
            if d1 and d2:
                timeline.total_days = (d2 - d1).days

        company = self._extract_company(title)
        if company and not timeline.company:
            timeline.company = company

        return timeline

    def get_timeline(self, project_name: str) -> Optional[ProjectTimeline]:
        key = self._normalize_name(project_name)
        pid = self._name_index.get(key)
        if pid:
            return self._timelines.get(pid)

        # Fuzzy lookup by keyword overlap
        best_pid = None
        best_score = 0.0
        for existing_key, existing_pid in self._name_index.items():
            score = self._keyword_overlap(project_name, existing_key)
            if score > best_score and score > 0.3:
                best_score = score
                best_pid = existing_pid

        return self._timelines.get(best_pid) if best_pid else None

    def get_active_projects(self, since_days: int = 90) -> list[ProjectTimeline]:
        cutoff = time.strftime("%Y-%m-%d", time.localtime(time.time() - since_days * 86400))
        return [t for t in self._timelines.values() if t.last_seen >= cutoff]

    def get_stats(self) -> dict:
        total_stages = sum(len(t.stages) for t in self._timelines.values())
        multi_stage = sum(1 for t in self._timelines.values() if len(t.stages) >= 2)
        return {
            "total_projects": len(self._timelines),
            "total_stages": total_stages,
            "multi_stage_projects": multi_stage,
            "avg_stages_per_project": total_stages / max(len(self._timelines), 1),
            "avg_days_to_approval": sum(
                t.total_days for t in self._timelines.values() if t.total_days > 0
            ) / max(sum(1 for t in self._timelines.values() if t.total_days > 0), 1),
        }

    def _find_or_create_project(self, title: str) -> str:
        key = self._normalize_name(title)
        if key in self._name_index:
            return self._name_index[key]

        # Fuzzy match by company + keywords
        company = self._extract_company(title)
        if company:
            company_key = self._normalize_name(company)
            for existing_key, existing_pid in self._name_index.items():
                if company_key in existing_key:
                    # Check keyword overlap
                    if self._keyword_overlap(title, existing_key) > 0.3:
                        return existing_pid

        pid = hashlib.md5(title.encode()).hexdigest()[:16]
        self._name_index[key] = pid
        self._timelines[pid] = ProjectTimeline(project_id=pid, project_name=title[:200])
        return pid

    @staticmethod
    def _detect_stage(title: str) -> str:
        stage_keywords = [
            ("受理公示", ["受理公示", "受理"]),
            ("拟批准公示", ["拟批准", "拟批"]),
            ("审批批复", ["审批", "批复", "决定公告"]),
            ("验收公示", ["验收", "竣工"]),
            ("招标公告", ["招标", "施工"]),
        ]
        for stage, keywords in stage_keywords:
            if any(kw in title for kw in keywords):
                return stage
        return "其他公告"

    @staticmethod
    def _extract_company(title: str) -> str:
        patterns = [
            r'([\u4e00-\u9fff]{3,20}有限公司)',
            r'([\u4e00-\u9fff]{3,20}集团)',
            r'([\u4e00-\u9fff]{2,15}厂)',
        ]
        for pat in patterns:
            m = re.search(pat, title)
            if m:
                return m.group(1)
        return ""

    @staticmethod
    def _normalize_name(name: str) -> str:
        for prefix in ["[建设项目环评受理公示]", "[环评审批决定公告]", "[拟批准公示]", "[验收公示]",
                       "[受理公示]", "[审批批复]", "[招标公告]", "[环评受理]"]:
            name = name.replace(prefix, "")
        return re.sub(r'\s+', '', name.lower())[:100]

    @staticmethod
    def _keyword_overlap(a: str, b: str) -> float:
        words_a = set(re.findall(r'[\u4e00-\u9fff]{2,}', a))
        words_b = set(re.findall(r'[\u4e00-\u9fff]{2,}', b))
        if not words_a or not words_b:
            return 0.0
        return len(words_a & words_b) / len(words_a | words_b)

    @staticmethod
    def _parse_date(date_str: str):
        from datetime import datetime
        for fmt in ["%Y-%m-%d", "%Y-%m", "%Y"]:
            try:
                return datetime.strptime(date_str[:10], fmt)
            except ValueError:
                continue
        return None


# ═══ 4. Daily Brief — Auto-generated morning report ═══

@dataclass
class DailyBrief:
    """Auto-generated intelligence report."""
    date: str = ""
    title: str = ""
    total_new_items: int = 0
    new_projects: int = 0
    stage_transitions: list[str] = field(default_factory=list)
    company_highlights: list[dict] = field(default_factory=list)
    standard_mentions: list[str] = field(default_factory=list)
    trend_analysis: str = ""
    recommendations: list[str] = field(default_factory=list)
    raw_text: str = ""


# ═══ 5. Knowledge Forager — Unified engine ═══

class KnowledgeForager:
    """AI's autonomous food gathering system.

    Capabilities:
      - food_map:      registered site registry with patrol schedule
      - auto_patrol:   scheduled scanning + change detection
      - auto_graph:    entity extraction + relationship building
      - succession:    multi-stage project timeline tracking
      - daily_brief:   auto-generated morning report

    Usage:
        forager = KnowledgeForager()
        await forager.register_site("haian", "https://www.haian.gov.cn/...")
        await forager.patrol()  # scan all registered sites
        brief = forager.generate_daily_brief()
    """

    def __init__(self, data_dir: str = ""):
        self._data_dir = data_dir or os.path.expanduser("~/.livingtree/forager")
        os.makedirs(self._data_dir, exist_ok=True)

        self.food_map: dict[str, FoodSource] = {}
        self.graph = KnowledgeGraph()
        self.succession = SuccessionTracker()
        self._items_seen: set[str] = set()  # hash fingerprints of seen items
        self._lock = threading.RLock()
        self._patrol_count: int = 0
        self._last_patrol: float = 0.0

        self._load_food_map()

    # ═══ Food Map ═══

    async def register_site(self, name: str, url: str, category: str = "env",
                            interval_hours: int = 24, priority: int = 0) -> FoodSource:
        from urllib.parse import urlparse
        domain = urlparse(url).hostname or name

        source = FoodSource(
            domain=domain, url=url, category=category,
            scan_interval_hours=interval_hours, priority=priority,
        )
        self.food_map[name] = source
        self._save_food_map()
        logger.info("Forager: registered food source '%s' (%s)", name, domain)
        return source

    def get_due_sources(self) -> list[FoodSource]:
        now = time.time()
        due = []
        for source in self.food_map.values():
            if not source.enabled:
                continue
            hours_since_scan = (now - source.last_scan) / 3600 if source.last_scan else float('inf')
            if hours_since_scan >= source.scan_interval_hours:
                due.append(source)
        due.sort(key=lambda s: -s.priority)
        return due

    # ═══ Auto Patrol ═══

    async def patrol(self, max_sources: int = 10, hub: Any = None) -> dict:
        """Scan all due sites and ingest new knowledge."""
        due = self.get_due_sources()[:max_sources]
        if not due:
            return {"status": "no_due_sources", "scanned": 0}

        results = {"status": "ok", "scanned": 0, "new_items": 0, "by_source": {}}

        for source in due:
            try:
                from .intelligence_collector import IntelligenceCollector
                collector = IntelligenceCollector()
                collect_result = await collector.collect_from_url(
                    source.url, deep=True, hub=hub, use_llm=False,  # use skill cache
                )

                # Change detection
                new_count = self._detect_new_items(collect_result)

                source.last_scan = time.time()
                source.last_item_count = collect_result.items_found
                self._patrol_count += 1
                self._last_patrol = time.time()

                results["scanned"] += 1
                results["new_items"] += new_count
                results["by_source"][source.domain] = {
                    "total": collect_result.items_found,
                    "new": new_count,
                    "stored": collect_result.stored,
                    "updated": collect_result.updated,
                }

                # Feed into graph + succession
                await self._digest_results(collect_result)

            except Exception as e:
                logger.warning("Forager patrol '%s' failed: %s", source.domain, e)
                results["by_source"][source.domain] = {"error": str(e)}

        self._save_food_map()
        self._save_graph()
        logger.info("Forager: patrol #%d done — %d sources, %d new items",
                   self._patrol_count, results["scanned"], results["new_items"])
        return results

    # ═══ Web Search Hunting — find scattered announcements ═══

    async def hunt(
        self,
        project_name: str,
        hub: Any = None,
        max_results: int = 20,
    ) -> dict:
        """Search the web for announcements about a specific project/company.

        Useful when:
          - 验收公示 is on a company website, not a government portal
          - 环评审批 appears on industry forums
          - 招标公告 is scattered across multiple bidding platforms

        Uses UnifiedSearch (SparkSearch + DDG) to find scattered sources.
        """
        results = {"project": project_name, "found": 0, "sources": [], "items": []}

        try:
            from .unified_search import search
            search_queries = [
                f"{project_name} 验收公示",
                f"{project_name} 环评 批复",
                f"{project_name} 环境影响评价",
                f"{project_name} 竣工验收",
            ]

            all_results = []
            for query in search_queries[:3]:
                hits = await search(query, limit=5)
                all_results.extend(hits)

            if not all_results:
                return results

            # Deduplicate by URL
            seen = set()
            unique = []
            for hit in all_results:
                url = getattr(hit, 'url', '') or getattr(hit, 'link', '')
                if url and url not in seen:
                    seen.add(url)
                    unique.append(hit)

            # Collect from each found URL
            from .intelligence_collector import IntelligenceCollector
            collector = IntelligenceCollector()

            for hit in unique[:min(max_results, 10)]:
                url = getattr(hit, 'url', '') or getattr(hit, 'link', '')
                if not url:
                    continue

                try:
                    self._session.respect_rate_limit(min_delay=1.0, max_delay=2.0)
                    collect_result = await collector.collect_from_url(
                        url, deep=True, hub=hub, use_llm=False,
                    )
                    if collect_result.items_found > 0:
                        results["sources"].append({
                            "url": url,
                            "title": getattr(hit, 'title', ''),
                            "items": collect_result.items_found,
                            "stored": collect_result.stored,
                        })
                        results["found"] += collect_result.stored
                        for d in collect_result.details[:3]:
                            results["items"].append(d)

                        await self._digest_results(collect_result)
                except Exception as e:
                    logger.debug("Hunt source '%s' failed: %s", url[:60], e)

            self._save_graph()

        except Exception as e:
            logger.warning("Hunt '%s' failed: %s", project_name, e)
            results["error"] = str(e)

        logger.info("Forager: hunt '%s' — found %d items from %d sources",
                   project_name, results["found"], len(results["sources"]))
        return results

    async def hunt_batch(self, projects: list[str], hub: Any = None) -> dict:
        """Hunt for multiple projects in parallel."""
        import asyncio as _aio
        tasks = [self.hunt(p, hub) for p in projects[:10]]
        results = await _aio.gather(*tasks, return_exceptions=True)
        total = sum(
            r.get("found", 0) if isinstance(r, dict) else 0
            for r in results
        )
        return {"projects": len(projects), "total_found": total}

    # ═══ Login Session — authenticated site access ═══

    def create_login_session(self, site_name: str, login_url: str,
                             username: str = "", password: str = "",
                             token: str = "") -> dict:
        auth_config = {
            "site": site_name, "login_url": login_url,
            "auth_mode": "form" if username else "token" if token else "none",
            "created_at": time.strftime("%Y-%m-%d %H:%M"),
        }
        auth_path = os.path.join(self._data_dir, f"auth_{site_name}.json")
        try:
            with open(auth_path, "w") as f:
                json.dump(auth_config, f)
        except Exception:
            pass
        return auth_config

    async def login(self, site_name: str, username: str = "",
                    password: str = "") -> Optional[str]:
        auth_path = os.path.join(self._data_dir, f"auth_{site_name}.json")
        try:
            if os.path.exists(auth_path):
                with open(auth_path) as f:
                    login_url = json.load(f).get("login_url", "")
                if login_url and username and password:
                    import aiohttp
                    async with aiohttp.ClientSession() as session:
                        payload = {"username": username, "password": password}
                        async with session.post(login_url, data=payload,
                                               timeout=aiohttp.ClientTimeout(total=15)) as resp:
                            if resp.status in (200, 302):
                                cookie_str = "; ".join(f"{k}={v.value}" for k, v in resp.cookies.items())
                                self._session.cookies = dict(resp.cookies)
                                self._session.headers["Cookie"] = cookie_str
                                logger.info("Forager: login OK for '%s'", site_name)
                                return cookie_str
        except Exception as e:
            logger.warning("Forager login failed '%s': %s", site_name, e)
        return None

    @staticmethod
    def detect_login_required(html: str) -> Optional[str]:
        import re
        for ind in ["请登录", "用户登录", "sign in", "login"]:
            if ind in html.lower():
                m = re.search(r'(?:href|action)=["\']([^"\']*(?:login|signin|auth)[^"\']*)', html)
                return m.group(1) if m else "/login"
        return None

    async def _digest_results(self, collect_result) -> None:
        """Digest collected items into graph + succession."""
        for detail in collect_result.details:
            if detail.get("decision") not in ("新增", "更新"):
                continue

            title = detail.get("title", "")
            date_str = detail.get("date", "") or time.strftime("%Y-%m-%d")

            # Entity extraction
            company = self._extract_entity_company(title)
            project = self._extract_entity_project(title)
            location = self._extract_entity_location(title)
            standards = self._extract_entity_standards(title)

            if company:
                self.graph.add_entity(company, "company", date_str)
            if project:
                pid = self.graph.add_entity(project, "project", date_str)
                if company:
                    cid = self.graph.add_entity(company, "company", date_str)
                    self.graph.add_relation(project, company, "submitted_by")
            if location:
                self.graph.add_entity(location, "location", date_str)
            for std in standards:
                self.graph.add_entity(std, "standard", date_str)
                if project:
                    self.graph.add_relation(project, std, "references_standard")

            # Succession tracking
            self.succession.ingest(title, date_str, detail.get("source", ""))

    # ═══ Daily Brief ═══

    def generate_daily_brief(self, hub: Any = None) -> DailyBrief:
        """Generate a morning intelligence report."""
        today = time.strftime("%Y-%m-%d")
        brief = DailyBrief(date=today, title=f"📰 LivingTree 情报日报 — {today}")

        # Stats
        stats = self.succession.get_stats()
        brief.total_new_items = stats["total_stages"]
        brief.new_projects = stats["total_projects"]

        # Active project timelines
        active = self.succession.get_active_projects(since_days=30)
        for proj in active[:10]:
            if len(proj.stages) >= 2:
                stages_str = " → ".join(
                    f"{s.stage}({s.date})" for s in proj.stages[-3:]
                )
                brief.stage_transitions.append(f"{proj.project_name[:60]}: {stages_str}")

        # Company highlights
        companies = Counter()
        for proj in self.succession._timelines.values():
            if proj.company:
                companies[proj.company] += len(proj.stages)
        for company, count in companies.most_common(5):
            brief.company_highlights.append({"name": company, "announcements": count})

        # Standard mentions
        std_counts = Counter()
        for node in self.graph.nodes.values():
            if node.entity_type == "standard":
                std_counts[node.name] = node.occurrences
        brief.standard_mentions = [s for s, _ in std_counts.most_common(5)]

        # Trend analysis
        avg_days = stats.get("avg_days_to_approval", 0)
        if avg_days > 0:
            brief.trend_analysis = f"本月项目平均审批周期: {avg_days:.0f}天"
        if brief.stage_transitions:
            brief.trend_analysis += f" | 推进中项目: {len(brief.stage_transitions)}个"

        brief.recommendations = self._generate_recommendations(brief)

        # Format
        brief.raw_text = self._format_brief(brief)
        return brief

    def _generate_recommendations(self, brief: DailyBrief) -> list[str]:
        recs = []
        if brief.new_projects > 10:
            recs.append("建议本周重点关注环评审批进度")
        if brief.standard_mentions:
            recs.append(f"本月高频标准: {', '.join(brief.standard_mentions[:3])}")
        if brief.stage_transitions:
            recs.append(f"{len([s for s in brief.stage_transitions if '批复' in s])}个项目已批复")
        return recs

    def _format_brief(self, brief: DailyBrief) -> str:
        lines = [
            f"# {brief.title}",
            f"新增项目: {brief.new_projects} | 总公告条数: {brief.total_new_items}",
            "",
        ]

        if brief.stage_transitions:
            lines.append("## 项目进展")
            for t in brief.stage_transitions[:10]:
                lines.append(f"- {t}")

        if brief.company_highlights:
            lines.append("\n## 活跃主体")
            for c in brief.company_highlights:
                lines.append(f"- {c['name']}: {c['announcements']}条公告")

        if brief.standard_mentions:
            lines.append("\n## 高频引用标准")
            for s in brief.standard_mentions:
                lines.append(f"- {s}")

        if brief.trend_analysis:
            lines.append(f"\n## 趋势\n{brief.trend_analysis}")

        if brief.recommendations:
            lines.append("\n## 建议")
            for r in brief.recommendations:
                lines.append(f"- {r}")

        return "\n".join(lines)

    # ═══ Persistence ═══

    def _load_food_map(self) -> None:
        path = os.path.join(self._data_dir, "food_map.json")
        try:
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                for name, d in data.items():
                    self.food_map[name] = FoodSource(
                        domain=d.get("domain", ""), url=d.get("url", ""),
                        category=d.get("category", "env"),
                        scan_interval_hours=d.get("scan_interval_hours", 24),
                        last_scan=d.get("last_scan", 0),
                        priority=d.get("priority", 0),
                        enabled=d.get("enabled", True),
                    )
        except Exception:
            pass

    def _save_food_map(self) -> None:
        path = os.path.join(self._data_dir, "food_map.json")
        try:
            data = {
                name: {
                    "domain": s.domain, "url": s.url, "category": s.category,
                    "scan_interval_hours": s.scan_interval_hours,
                    "last_scan": s.last_scan, "priority": s.priority,
                    "enabled": s.enabled,
                }
                for name, s in self.food_map.items()
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _save_graph(self) -> None:
        path = os.path.join(self._data_dir, "knowledge_graph.json")
        try:
            data = {
                "nodes": {
                    nid: {"name": n.name, "type": n.entity_type,
                          "occurrences": n.occurrences, "first": n.first_seen, "last": n.last_seen}
                    for nid, n in self.graph.nodes.items()
                },
                "relations": [
                    {"source": r.source_id, "target": r.target_id,
                     "type": r.relation_type, "evidence": r.evidence[:100]}
                    for r in self.graph.relations[-500:]
                ],
                "projects": {
                    pid: {
                        "name": t.project_name, "company": t.company,
                        "stages": [(s.stage, s.date) for s in t.stages],
                        "total_days": t.total_days,
                    }
                    for pid, t in self.succession._timelines.items()
                },
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _detect_new_items(self, collect_result) -> int:
        new_count = 0
        for detail in collect_result.details:
            fp = hashlib.md5(
                (detail.get("title", "") + detail.get("date", "")).encode()
            ).hexdigest()[:16]
            if fp not in self._items_seen:
                self._items_seen.add(fp)
                new_count += 1
        return new_count

    # ═══ Entity Extractors ═══

    @staticmethod
    def _extract_entity_company(title: str) -> str:
        patterns = [
            r'([\u4e00-\u9fff]{3,20}有限公司)',
            r'([\u4e00-\u9fff]{3,20}集团)',
            r'([\u4e00-\u9fff]{2,10}厂)',
        ]
        for pat in patterns:
            m = re.search(pat, title)
            if m:
                return m.group(1)
        return ""

    @staticmethod
    def _extract_entity_project(title: str) -> str:
        patterns = [
            r'(.{5,30}项目)',
            r'(.{5,30}工程)',
        ]
        for pat in patterns:
            m = re.search(pat, title)
            if m:
                return m.group(1)[:100]
        return title.split("项目")[0][:100] if "项目" in title else title[:100]

    @staticmethod
    def _extract_entity_location(title: str) -> str:
        patterns = [
            r'(海安\S*[区县镇村])',
            r'([\u4e00-\u9fff]{2,4}高新区)',
            r'([\u4e00-\u9fff]{2,4}园区)',
        ]
        for pat in patterns:
            m = re.search(pat, title)
            if m:
                return m.group(1)
        return ""

    @staticmethod
    def _extract_entity_standards(title: str) -> list[str]:
        patterns = [
            r'(GB\s*\d{4,}[.-]*\d*)',
            r'(HJ\s*\d+[.-]*\d*)',
            r'(DB\d{2}/\d+)',
        ]
        results = []
        for pat in patterns:
            results.extend(re.findall(pat, title))
        return list(set(results))

    def get_stats(self) -> dict:
        return {
            "food_sources": len(self.food_map),
            "patrol_count": self._patrol_count,
            "graph_nodes": len(self.graph.nodes),
            "graph_relations": len(self.graph.relations),
            "projects": self.succession.get_stats(),
            "items_indexed": len(self._items_seen),
        }


# ═══ Singleton ═══

_forager: Optional[KnowledgeForager] = None
_forager_lock = threading.Lock()


def get_forager() -> KnowledgeForager:
    global _forager
    if _forager is None:
        with _forager_lock:
            if _forager is None:
                _forager = KnowledgeForager()
    return _forager
