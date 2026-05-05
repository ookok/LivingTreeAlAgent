"""NetworkBrain — autonomous internet knowledge ingestion engine.

    The system's "eyes and ears". Continuously scans the internet for new
    knowledge, digests it, and indexes it for future use. No user interaction
    required — the brain learns on its own.

    Sources:
    1. arXiv papers (cs.AI, stat.ML, physics, environmental science)
    2. GitHub trending repos + release monitoring
    3. StackOverflow high-score answers → solution patterns
    4. HackerNews top stories → tech trend analysis
    5. RSS/Atom feeds → configurable, any source
    6. Industry standard/regulation monitors

    Pipeline per source:
      fetch → dedup → extract → classify → verify (cross-source) → index

    Runs on LifeDaemon cycle. Configurable schedules per source.
    All discovered knowledge feeds into:
    - IntelligentKB (semantic search)
    - DocumentKB (full-text)
    - SkillRouter (new tool patterns)
    - DomainTransfer (cross-domain principles)

    Usage:
        brain = get_network_brain()
        await brain.start(hub)      # begins continuous ingestion
        digest = await brain.digest_arxiv(hub)     # one-off
        report = brain.today_report()              # what was learned today

    Command:
        /brain status — what's being ingested right now
        /brain report — today's learning summary
        /brain search <q> — search ingested knowledge
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from loguru import logger

BRAIN_DIR = Path(".livingtree/brain")
INGESTED_DB = BRAIN_DIR / "ingested.json"
SOURCES_CONFIG = BRAIN_DIR / "sources.json"
DIGEST_LOG = BRAIN_DIR / "daily_digest.jsonl"


# ═══ Knowledge Atom ═══

@dataclass
class KnowledgeAtom:
    id: str                           # content hash
    source: str                       # arxiv, github, stackoverflow, hackernews, rss
    source_url: str = ""
    title: str = ""
    content: str = ""                 # extracted text
    summary: str = ""                 # LLM-generated summary
    methodology: str = ""             # extracted method/approach
    patterns: list[str] = field(default_factory=list)  # code patterns, formulas
    tags: list[str] = field(default_factory=list)
    category: str = ""                # domain classification
    confidence: float = 0.5
    cross_verified: bool = False      # confirmed by multiple sources
    ingested_at: float = 0.0
    relevance_score: float = 0.0      # LLM relevance to user's work


# ═══ Core Ingestion Engine ═══

class NetworkBrain:
    """Autonomous internet knowledge ingestion pipeline."""

    SOURCES_TEMPLATE = {
        "arxiv": {
            "enabled": True,
            "schedule": "daily",
            "categories": ["cs.AI", "cs.LG", "stat.ML", "physics.ao-ph"],
            "max_per_fetch": 30,
            "keywords": ["transformer", "diffusion", "reinforcement", "agent",
                        "environmental", "climate", "air quality", "emission"],
        },
        "github_trending": {
            "enabled": True,
            "schedule": "daily",
            "topics": ["ai", "llm", "agent", "python", "environmental-science"],
            "max_per_fetch": 20,
        },
        "github_releases": {
            "enabled": True,
            "schedule": "daily",
            "repos": [],
            "max_per_fetch": 10,
        },
        "stackoverflow": {
            "enabled": True,
            "schedule": "weekly",
            "tags": ["python", "machine-learning", "nlp", "data-science"],
            "min_score": 10,
            "max_per_fetch": 20,
        },
        "hackernews": {
            "enabled": True,
            "schedule": "daily",
            "min_points": 50,
            "max_per_fetch": 15,
        },
        "rss": {
            "enabled": True,
            "schedule": "hourly",
            "feeds": [],
        },
    }

    def __init__(self):
        BRAIN_DIR.mkdir(parents=True, exist_ok=True)
        self._ingested: dict[str, KnowledgeAtom] = {}    # content_hash → atom
        self._sources: dict = dict(self.SOURCES_TEMPLATE)
        self._today_count: int = 0
        self._total_count: int = 0
        self._today_atoms: list[KnowledgeAtom] = []
        self._load()

    async def ingest_cycle(self, hub=None):
        """One full ingestion cycle. Called by LifeDaemon.

        Respects per-source schedules. Runs all due sources.
        """
        now = datetime.now()
        count = 0

        for source_name, config in self._sources.items():
            if not config.get("enabled"):
                continue
            if not self._is_due(source_name, now):
                continue

            try:
                handler = getattr(self, f"_fetch_{source_name}", None)
                if handler and hub:
                    atoms = await handler(hub, config)
                    new_atoms = self._ingest_batch(atoms, hub)
                    count += len(new_atoms)
                    self._update_last_run(source_name)
            except Exception as e:
                logger.debug(f"Brain {source_name}: {e}")

        if count > 0:
            logger.info(f"🧠 NetworkBrain: +{count} new atoms ({self._total_count} total)")
            self._save()

        return count

    # ═══ Source: arXiv ═══

    async def _fetch_arxiv(self, hub, config: dict) -> list[KnowledgeAtom]:
        """Fetch recent papers from arXiv API per configured categories."""
        atoms = []
        categories = config.get("categories", ["cs.AI"])
        keywords = config.get("keywords", [])
        max_n = config.get("max_per_fetch", 30)

        for cat in categories[:3]:
            try:
                url = (
                    f"http://export.arxiv.org/api/query?"
                    f"search_query=cat:{cat}&sortBy=submittedDate&sortOrder=descending&max_results={max_n}"
                )
                req = urllib.request.Request(url, headers={"User-Agent": "LivingTreeBrain/2.1"})
                with urllib.request.urlopen(req, timeout=20) as resp:
                    xml_text = resp.read().decode("utf-8", errors="replace")

                root = ET.fromstring(xml_text)
                ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

                for entry in root.findall("atom:entry", ns)[:max_n]:
                    title = entry.findtext("atom:title", "", ns).strip().replace("\n", " ")
                    summary = entry.findtext("atom:summary", "", ns).strip()[:1000]
                    link = entry.find("atom:id", ns)
                    arxiv_id = link.text.strip() if link is not None and link.text else ""
                    pdf_url = arxiv_id.replace("abs", "pdf") if "abs" in arxiv_id else arxiv_id

                    # Keyword filter
                    text_lower = (title + summary).lower()
                    if keywords and not any(k in text_lower for k in keywords):
                        continue

                    atom = KnowledgeAtom(
                        id=self._hash_content(title + summary[:500]),
                        source="arxiv",
                        source_url=pdf_url,
                        title=title[:300],
                        content=summary[:2000],
                        tags=[cat, *([k for k in keywords if k in text_lower])],
                        category=cat,
                        ingested_at=time.time(),
                    )
                    atoms.append(atom)
            except Exception as e:
                logger.debug(f"arXiv {cat}: {e}")

        return atoms

    # ═══ Source: GitHub Trending ═══

    async def _fetch_github_trending(self, hub, config: dict) -> list[KnowledgeAtom]:
        """Fetch trending repos from GitHub."""
        atoms = []
        topics = config.get("topics", ["ai", "llm"])

        try:
            url = "https://api.github.com/search/repositories?q=" + urllib.parse.quote(
                " OR ".join(f"topic:{t}" for t in topics[:3])
            ) + "&sort=stars&order=desc&per_page=20"

            req = urllib.request.Request(url, headers={
                "User-Agent": "LivingTreeBrain/2.1",
                "Accept": "application/vnd.github+json",
            })
            # Try with mirror first
            for try_url in [url, f"https://ghproxy.com/{url}"]:
                try:
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        data = json.loads(resp.read().decode("utf-8", errors="replace"))
                    break
                except Exception:
                    continue
            else:
                return atoms

            for item in data.get("items", [])[:config.get("max_per_fetch", 20)]:
                atom = KnowledgeAtom(
                    id=self._hash_content(f"github:{item.get('full_name','')}"),
                    source="github_trending",
                    source_url=item.get("html_url", ""),
                    title=item.get("full_name", ""),
                    content=item.get("description", "")[:500],
                    summary=f"⭐ {item.get('stargazers_count', 0)} | Language: {item.get('language', '?')}",
                    tags=[t for t in item.get("topics", [])[:5]],
                    category="github",
                    ingested_at=time.time(),
                )
                atoms.append(atom)
        except Exception as e:
            logger.debug(f"GitHub trending: {e}")

        return atoms

    # ═══ Source: GitHub Releases ═══

    async def _fetch_github_releases(self, hub, config: dict) -> list[KnowledgeAtom]:
        """Check configured repos for new releases."""
        atoms = []
        repos = config.get("repos", [])
        if not repos:
            try:
                from ..treellm.core import TreeLLM
                repos = [
                    "microsoft/vscode", "pytorch/pytorch", "huggingface/transformers",
                    "langchain-ai/langchain", "AUTOMATIC1111/stable-diffusion-webui",
                ]
            except Exception:
                repos = ["pytorch/pytorch", "huggingface/transformers"]

        for repo in repos[:config.get("max_per_fetch", 10)]:
            try:
                url = f"https://api.github.com/repos/{repo}/releases/latest"
                req = urllib.request.Request(url, headers={
                    "User-Agent": "LivingTreeBrain/2.1",
                    "Accept": "application/vnd.github+json",
                })
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="replace"))

                content_id = f"{repo}:{data.get('tag_name','')}"
                atom = KnowledgeAtom(
                    id=self._hash_content(content_id),
                    source="github_releases",
                    source_url=data.get("html_url", ""),
                    title=f"{repo} {data.get('tag_name', '')}",
                    content=data.get("body", "")[:1000],
                    summary=f"Release: {data.get('name', '')}",
                    tags=["release", *repo.split("/")],
                    category="release",
                    ingested_at=time.time(),
                )
                atoms.append(atom)
            except Exception:
                pass

        return atoms

    # ═══ Source: StackOverflow ═══

    async def _fetch_stackoverflow(self, hub, config: dict) -> list[KnowledgeAtom]:
        """Fetch high-score answers from StackOverflow via StackExchange API."""
        atoms = []
        tags = config.get("tags", ["python", "machine-learning"])
        min_score = config.get("min_score", 10)

        for tag in tags[:3]:
            try:
                url = (
                    f"https://api.stackexchange.com/2.3/questions?"
                    f"order=desc&sort=votes&tagged={tag}&site=stackoverflow"
                    f"&filter=withbody&pagesize=10"
                )
                req = urllib.request.Request(url, headers={"User-Agent": "LivingTreeBrain/2.1"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="replace"))

                for item in data.get("items", []):
                    if item.get("score", 0) < min_score:
                        continue
                    # Extract solution patterns from accepted answer
                    body = item.get("body", "")[:3000]
                    patterns = self._extract_code_patterns(body)

                    atom = KnowledgeAtom(
                        id=self._hash_content(f"so:{item.get('question_id','')}"),
                        source="stackoverflow",
                        source_url=item.get("link", ""),
                        title=item.get("title", "")[:200],
                        content=item.get("body_markdown", body)[:2000],
                        summary=f"Score: {item.get('score',0)} | Answers: {item.get('answer_count',0)}",
                        patterns=patterns,
                        tags=[tag, "stackoverflow"],
                        category="qa",
                        ingested_at=time.time(),
                    )
                    atoms.append(atom)
            except Exception as e:
                logger.debug(f"SO {tag}: {e}")

        return atoms

    # ═══ Source: HackerNews ═══

    async def _fetch_hackernews(self, hub, config: dict) -> list[KnowledgeAtom]:
        """Fetch top HackerNews stories with high points."""
        atoms = []
        min_points = config.get("min_points", 50)

        try:
            url = "https://hacker-news.firebaseio.com/v0/topstories.json"
            req = urllib.request.Request(url, headers={"User-Agent": "LivingTreeBrain/2.1"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                top_ids = json.loads(resp.read().decode("utf-8", errors="replace"))[:30]

            for item_id in top_ids[:15]:
                try:
                    item_url = f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
                    req2 = urllib.request.Request(item_url, headers={"User-Agent": "LivingTreeBrain/2.1"})
                    with urllib.request.urlopen(req2, timeout=8) as resp:
                        item = json.loads(resp.read().decode("utf-8", errors="replace"))

                    if item.get("score", 0) >= min_points and item.get("title"):
                        atom = KnowledgeAtom(
                            id=self._hash_content(f"hn:{item_id}"),
                            source="hackernews",
                            source_url=item.get("url", f"https://news.ycombinator.com/item?id={item_id}"),
                            title=item.get("title", "")[:300],
                            content=item.get("text", "")[:1000] or item.get("url", ""),
                            summary=f"Points: {item.get('score',0)} | Comments: {item.get('descendants',0)}",
                            tags=["hackernews"],
                            category="tech_news",
                            ingested_at=time.time(),
                        )
                        atoms.append(atom)
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"HN: {e}")

        return atoms

    # ═══ Source: RSS Feeds ═══

    async def _fetch_rss(self, hub, config: dict) -> list[KnowledgeAtom]:
        """Generic RSS/Atom feed parser."""
        atoms = []
        feeds = config.get("feeds", [])

        for feed_url in feeds[:10]:
            try:
                req = urllib.request.Request(feed_url, headers={"User-Agent": "LivingTreeBrain/2.1"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    xml_text = resp.read().decode("utf-8", errors="replace")

                root = ET.fromstring(xml_text)
                # RSS 2.0
                for item in root.iter("item"):
                    title = (item.findtext("title") or "").strip()
                    link = (item.findtext("link") or "").strip()
                    desc = (item.findtext("description") or "")[:1000]
                    if title and link:
                        atom = KnowledgeAtom(
                            id=self._hash_content(f"rss:{link}"),
                            source="rss",
                            source_url=link,
                            title=title[:300],
                            content=re.sub(r'<[^>]+>', '', desc)[:1000],
                            tags=["rss"],
                            category="feed",
                            ingested_at=time.time(),
                        )
                        atoms.append(atom)

                # Atom format
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                for entry in root.findall("atom:entry", ns):
                    title = (entry.findtext("atom:title", "", ns) or "").strip()
                    link_el = entry.find("atom:link", ns)
                    link = link_el.get("href", "") if link_el is not None else ""
                    summary = (entry.findtext("atom:summary", "", ns) or "")[:1000]
                    if title and link:
                        atom = KnowledgeAtom(
                            id=self._hash_content(f"rss:{link}"),
                            source="rss",
                            source_url=link,
                            title=title[:300],
                            content=re.sub(r'<[^>]+>', '', summary)[:1000],
                            tags=["rss"],
                            category="feed",
                            ingested_at=time.time(),
                        )
                        atoms.append(atom)
            except Exception as e:
                logger.debug(f"RSS {feed_url[:50]}: {e}")

        return atoms

    # ═══ Ingestion Pipeline ═══

    def _ingest_batch(self, atoms: list[KnowledgeAtom], hub) -> list[KnowledgeAtom]:
        """Dedup, classify, and index a batch of knowledge atoms.

        Returns only new atoms (not previously ingested).
        """
        new_atoms = []

        for atom in atoms:
            # Dedup
            if atom.id in self._ingested:
                continue

            # Check similarity (same title, different URL)
            is_dup = False
            for existing in self._ingested.values():
                if self._title_similarity(atom.title, existing.title) > 0.85:
                    existing.cross_verified = True
                    is_dup = True
                    break
            if is_dup:
                continue

            self._ingested[atom.id] = atom
            new_atoms.append(atom)
            self._today_atoms.append(atom)
            self._today_count += 1

        self._total_count = len(self._ingested)
        return new_atoms

    # ═══ LLM Deep Digest ═══

    async def deep_digest(self, hub, max_items: int = 10):
        """LLM-powered deep digestion: extract methodology, verify, classify.

        Runs on unprocessed atoms to enrich them with AI analysis.
        """
        if not hub or not hub.world:
            return

        unprocessed = [
            a for a in self._ingested.values()
            if not a.methodology and a.summary
        ]
        unprocessed = sorted(unprocessed, key=lambda a: -a.ingested_at)[:max_items]
        if not unprocessed:
            return

        llm = hub.world.consciousness._llm
        for atom in unprocessed:
            try:
                result = await llm.chat(
                    messages=[{"role": "user", "content": (
                        f"Analyze this knowledge item and extract:\n"
                        f"1. Methodology/approach used\n"
                        f"2. Specific patterns or formulas\n"
                        f"3. Relevance to: AI agent systems, document generation, environmental science\n\n"
                        f"TITLE: {atom.title}\n"
                        f"CONTENT: {atom.content[:2000]}\n"
                        f"SOURCE: {atom.source}\n\n"
                        'Output JSON: {"methodology": "...", "patterns": ["..."], '
                        '"relevance_score": 0.0-1.0, "category": "specific_domain"}'
                    )}],
                    provider=getattr(llm, '_elected', ''),
                    temperature=0.2, max_tokens=400, timeout=15,
                )
                if result and result.text:
                    m = re.search(r'\{[\s\S]*\}', result.text)
                    if m:
                        d = json.loads(m.group())
                        atom.methodology = d.get("methodology", "")[:500]
                        atom.patterns = d.get("patterns", [])[:5]
                        atom.relevance_score = d.get("relevance_score", 0.5)
                        atom.category = d.get("category", atom.category)
                        atom.confidence = 0.8
            except Exception:
                pass

        self._save()

    # ═══ Reporting ═══

    def today_report(self) -> str:
        """Generate today's learning report."""
        if not self._today_atoms:
            return "🧠 今日未摄入新知识"

        by_source = {}
        for a in self._today_atoms:
            by_source.setdefault(a.source, []).append(a)

        lines = [f"🧠 今日学习: {len(self._today_atoms)} 条", ""]
        for source, atoms in by_source.items():
            lines.append(f"### {source} ({len(atoms)})")
            for a in atoms[:5]:
                lines.append(f"- {a.title[:100]}")
                if a.summary:
                    lines.append(f"  {a.summary[:120]}")
            if len(atoms) > 5:
                lines.append(f"  ... 还有 {len(atoms) - 5} 条")
            lines.append("")

        return "\n".join(lines)

    def search(self, query: str, limit: int = 10) -> list[KnowledgeAtom]:
        """Search ingested knowledge."""
        q = query.lower()
        results = []
        for atom in self._ingested.values():
            score = 0
            if q in atom.title.lower():
                score = 3
            elif q in atom.content.lower():
                score = 2
            elif any(q in t.lower() for t in atom.tags):
                score = 1
            if q in (atom.methodology or "").lower():
                score += 2
            if score:
                atom.relevance_score = score
                results.append(atom)

        results.sort(key=lambda a: -a.relevance_score)
        return results[:limit]

    def stats(self) -> dict:
        return {
            "total_ingested": self._total_count,
            "today": self._today_count,
            "by_source": {
                s: sum(1 for a in self._ingested.values() if a.source == s)
                for s in set(a.source for a in self._ingested.values())
            },
            "by_category": {
                c: sum(1 for a in self._ingested.values() if a.category == c)
                for c in set(a.category for a in self._ingested.values() if a.category)
            },
            "cross_verified": sum(1 for a in self._ingested.values() if a.cross_verified),
            "with_methodology": sum(1 for a in self._ingested.values() if a.methodology),
        }

    # ═══ Scheduling ═══

    def _is_due(self, source_name: str, now: datetime) -> bool:
        schedule = self._sources.get(source_name, {}).get("schedule", "daily")
        last = self._sources.get(source_name, {}).get("_last_run", 0)

        intervals = {"hourly": 3600, "daily": 86400, "weekly": 604800}
        interval = intervals.get(schedule, 86400)

        return (now.timestamp() - last) >= interval

    def _update_last_run(self, source_name: str):
        if source_name in self._sources:
            self._sources[source_name]["_last_run"] = time.time()

    # ═══ Helpers ═══

    @staticmethod
    def _hash_content(content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()[:20]

    @staticmethod
    def _title_similarity(t1: str, t2: str) -> float:
        if not t1 or not t2:
            return 0.0
        words1 = set(t1.lower().split())
        words2 = set(t2.lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = words1 & words2
        return len(intersection) / max(len(words1), len(words2))

    @staticmethod
    def _extract_code_patterns(text: str) -> list[str]:
        patterns = []
        for m in re.finditer(r'<code>(.*?)</code>', text, re.DOTALL):
            code = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(code) > 10 and len(code) < 500:
                patterns.append(code[:200])
        return patterns[:3]

    # ═══ Persistence ═══

    def _save(self):
        data = {
            "total_count": self._total_count,
            "sources": self._sources,
            "ingested": {
                aid: {
                    "id": a.id, "source": a.source, "source_url": a.source_url,
                    "title": a.title, "content": a.content[:1000], "summary": a.summary,
                    "methodology": a.methodology, "patterns": a.patterns,
                    "tags": a.tags, "category": a.category,
                    "confidence": a.confidence, "cross_verified": a.cross_verified,
                    "ingested_at": a.ingested_at, "relevance_score": a.relevance_score,
                }
                for aid, a in list(self._ingested.items())[-500:]  # keep last 500
            },
        }
        INGESTED_DB.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _load(self):
        if not INGESTED_DB.exists():
            return
        try:
            data = json.loads(INGESTED_DB.read_text(encoding="utf-8"))
            self._sources = data.get("sources", dict(self.SOURCES_TEMPLATE))
            self._total_count = data.get("total_count", 0)
            for aid, ad in data.get("ingested", {}).items():
                self._ingested[aid] = KnowledgeAtom(
                    id=ad.get("id", ""), source=ad.get("source", ""),
                    source_url=ad.get("source_url", ""), title=ad.get("title", ""),
                    content=ad.get("content", ""), summary=ad.get("summary", ""),
                    methodology=ad.get("methodology", ""),
                    patterns=ad.get("patterns", []), tags=ad.get("tags", []),
                    category=ad.get("category", ""), confidence=ad.get("confidence", 0.5),
                    cross_verified=ad.get("cross_verified", False),
                    ingested_at=ad.get("ingested_at", 0),
                    relevance_score=ad.get("relevance_score", 0),
                )
        except Exception:
            pass


_brain: NetworkBrain | None = None


def get_network_brain() -> NetworkBrain:
    global _brain
    if _brain is None:
        _brain = NetworkBrain()
    return _brain
