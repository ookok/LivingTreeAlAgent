# community_evolution.py — 社区驱动架构进化系统

import asyncio
import re
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import hashlib


logger = logging.getLogger(__name__)


# ============ 热点数据模型 ============

@dataclass
class HotArticle:
    """热点文章"""
    id: str
    title: str
    url: str
    source: str  # github_trending / hackernews / reddit / zhihu
    summary: str = ""
    keywords: List[str] = None
    relevance_score: float = 0.0
    architecture_impact: str = ""
    posted_at: Optional[int] = None
    collected_at: int = 0
    author: str = ""

    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "summary": self.summary,
            "keywords": self.keywords,
            "relevance_score": self.relevance_score,
            "architecture_impact": self.architecture_impact,
            "posted_at": self.posted_at,
            "collected_at": self.collected_at,
            "author": self.author,
        }


@dataclass
class EvolutionProposal:
    """架构升级提案"""
    id: str
    title: str
    content: str  # Markdown
    referenced_article_id: Optional[str] = None
    referenced_library: Optional[str] = None
    original_link: str = ""
    impact_analysis: str = ""
    risk_assessment: str = ""
    benefits: List[str] = None
    status: str = "draft"  # draft / proposed / discussing / approved / rejected
    upvotes: int = 0
    author_client_id: str = ""
    created_at: int = 0
    published_at: Optional[int] = None
    decided_at: Optional[int] = None
    decision_note: str = ""

    def __post_init__(self):
        if self.benefits is None:
            self.benefits = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "referenced_article_id": self.referenced_article_id,
            "referenced_library": self.referenced_library,
            "original_link": self.original_link,
            "impact_analysis": self.impact_analysis,
            "risk_assessment": self.risk_assessment,
            "benefits": self.benefits,
            "status": self.status,
            "upvotes": self.upvotes,
            "author_client_id": self.author_client_id,
            "created_at": self.created_at,
            "published_at": self.published_at,
            "decided_at": self.decided_at,
            "decision_note": self.decision_note,
        }


# ============ 热点文章爬虫 ============

class HotArticleCollector:
    """
    热点文章采集器

    采集源:
    1. GitHub Trending - 热门项目
    2. HackerNews - 技术讨论
    3. Reddit - 社区热点
    4. 技术博客 - AI/编程相关
    """

    def __init__(self, cache_dir: Path = None):
        if cache_dir is None:
            cache_dir = Path.home() / ".hermes-desktop" / "upgrade_scanner" / "hot_articles"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_dir = cache_dir
        self._cache_file = cache_dir / "articles.json"
        self._articles: Dict[str, HotArticle] = {}
        self._load_cache()

    def _load_cache(self):
        """加载缓存"""
        if self._cache_file.exists():
            try:
                data = json.loads(self._cache_file.read_text(encoding="utf-8"))
                for k, v in data.items():
                    self._articles[k] = HotArticle(**v)
            except Exception:
                pass

    def _save_cache(self):
        """保存缓存"""
        try:
            data = {k: v.to_dict() for k, v in self._articles.items()}
            self._cache_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")

    def _generate_id(self, url: str) -> str:
        """生成文章ID"""
        return hashlib.md5(url.encode()).hexdigest()[:12]

    async def collect_github_trending(
        self,
        language: str = "Python",
        since: str = "daily",
    ) -> List[HotArticle]:
        """
        采集GitHub Trending

        Args:
            language: 编程语言
            since: 时间范围 (daily/weekly/monthly)

        Returns:
            List[HotArticle]: 热点文章列表
        """
        articles = []

        try:
            import aiohttp
            url = f"https://api.github.com/search/repositories"
            params = {
                "q": f"language:{language} created:>{self._get_date_range(since)}",
                "sort": "stars",
                "order": "desc",
                "per_page": 20,
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for item in data.get("items", []):
                            article = HotArticle(
                                id=self._generate_id(item["html_url"]),
                                title=item.get("name", ""),
                                url=item.get("html_url", ""),
                                source="github_trending",
                                summary=item.get("description", ""),
                                keywords=[language, "trending"],
                                relevance_score=min(1.0, item.get("stargazers_count", 0) / 10000),
                                architecture_impact=self._assess_impact(item),
                                posted_at=int(datetime.fromisoformat(
                                    item.get("created_at", "2024-01-01").replace("Z", "+00:00")
                                ).timestamp()),
                                collected_at=int(time.time()),
                                author=item.get("owner", {}).get("login", ""),
                            )
                            articles.append(article)
                            self._articles[article.id] = article
        except Exception as e:
            logger.error(f"GitHub Trending collection failed: {e}")

        self._save_cache()
        return articles

    def _get_date_range(self, since: str) -> str:
        """获取日期范围"""
        now = datetime.now()
        if since == "daily":
            delta = 1
        elif since == "weekly":
            delta = 7
        else:  # monthly
            delta = 30

        return (now - timedelta(days=delta)).strftime("%Y-%m-%d")

    def _assess_impact(self, repo_info: Dict) -> str:
        """评估对架构的影响"""
        desc = repo_info.get("description", "").lower()
        name = repo_info.get("name", "").lower()

        impact_indicators = {
            "替换": ["replace", "alternative", "替代"],
            "优化": ["optimize", "fast", "performance", "优化", "加速"],
            "新架构": ["nextgen", "v2", "重构", "rewrite"],
            "工具": ["cli", "tool", "工具"],
        }

        impacts = []
        for impact, keywords in impact_indicators.items():
            if any(k in desc or k in name for k in keywords):
                impacts.append(impact)

        return ", ".join(impacts) if impacts else "一般"

    async def collect_hackernews(self, limit: int = 20) -> List[HotArticle]:
        """采集HackerNews"""
        articles = []

        try:
            import aiohttp
            # 获取top stories
            async with aiohttp.ClientSession() as session:
                # 获取前N个故事ID
                async with session.get(
                    "https://hacker-news.firebaseio.com/v0/topstories.json"
                ) as resp:
                    if resp.status == 200:
                        story_ids = await resp.json()

                        # 获取前limit个
                        for story_id in story_ids[:limit]:
                            article = await self._fetch_hn_story(session, story_id)
                            if article:
                                articles.append(article)
                                self._articles[article.id] = article
        except Exception as e:
            logger.error(f"HackerNews collection failed: {e}")

        self._save_cache()
        return articles

    async def _fetch_hn_story(self, session, story_id: int) -> Optional[HotArticle]:
        """获取单个HN故事"""
        try:
            url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if not data or data.get("type") != "story":
                        return None

                    return HotArticle(
                        id=self._generate_id(f"hn_{story_id}"),
                        title=data.get("title", ""),
                        url=data.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                        source="hackernews",
                        summary="",
                        keywords=self._extract_keywords(data.get("title", "")),
                        posted_at=data.get("time"),
                        collected_at=int(time.time()),
                        author=data.get("by", ""),
                    )
        except Exception:
            pass

        return None

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        keywords = []
        tech_keywords = [
            "AI", "LLM", "Python", "Rust", "Go", "JavaScript",
            "database", "cache", "API", "microservice", "kubernetes",
            "docker", "devops", "security", "performance",
        ]

        text_upper = text.upper()
        for kw in tech_keywords:
            if kw.upper() in text_upper:
                keywords.append(kw.lower())

        return keywords[:5]

    def get_all_articles(self) -> List[HotArticle]:
        """获取所有缓存文章"""
        return list(self._articles.values())

    def get_recent_articles(self, days: int = 7) -> List[HotArticle]:
        """获取最近N天的文章"""
        cutoff = int(time.time()) - days * 86400
        return [
            a for a in self._articles.values()
            if a.collected_at > cutoff
        ]


# ============ 架构升级提案生成器 ============

class ProposalGenerator:
    """
    架构升级提案生成器

    功能:
    1. 分析热点文章与当前架构的关联
    2. 生成升级建议帖
    3. 评估收益/风险
    """

    def __init__(
        self,
        collector: HotArticleCollector = None,
        current_modules_getter: Callable = None,
    ):
        self._collector = collector or HotArticleCollector()
        self._current_modules_getter = current_modules_getter
        self._proposals: Dict[str, EvolutionProposal] = {}
        self._load_proposals()

    def _load_proposals(self):
        """加载提案"""
        proposals_file = Path.home() / ".hermes-desktop" / "upgrade_scanner" / "proposals.json"
        if proposals_file.exists():
            try:
                data = json.loads(proposals_file.read_text(encoding="utf-8"))
                for k, v in data.items():
                    self._proposals[k] = EvolutionProposal(**v)
            except Exception:
                pass

    def _save_proposals(self):
        """保存提案"""
        proposals_file = Path.home() / ".hermes-desktop" / "upgrade_scanner" / "proposals.json"
        try:
            data = {k: v.to_dict() for k, v in self._proposals.items()}
            proposals_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            logger.error(f"Failed to save proposals: {e}")

    def _generate_proposal_id(self) -> str:
        """生成提案ID"""
        return hashlib.md5(f"proposal:{time.time()}".encode()).hexdigest()[:12]

    def generate_proposal(
        self,
        article: HotArticle,
        candidate_library: Dict[str, Any] = None,
    ) -> EvolutionProposal:
        """
        基于热点文章生成提案

        Args:
            article: 热点文章
            candidate_library: 候选开源库信息

        Returns:
            EvolutionProposal: 提案
        """
        proposal_id = self._generate_proposal_id()

        # 生成提案内容
        title = f"[架构升级思考] {article.title}"

        content = f"""# {title}

## 背景

来源: [{article.source}]({article.url})

{article.summary}

## 原链接

{article.original_link}

## 影响评估

**架构影响**: {article.architecture_impact or '待评估'}

"""

        if candidate_library:
            content += f"""
## 候选替代库

- **库名**: {candidate_library.get('name', 'N/A')}
- **Stars**: {candidate_library.get('stars', 0)}
- **地址**: {candidate_library.get('url', 'N/A')}
- **描述**: {candidate_library.get('description', 'N/A')}

"""

        content += f"""
## 收益分析

"""

        if candidate_library:
            benefits = [
                f"减少自研维护成本 (Stars: {candidate_library.get('stars', 0)})",
                "功能更完善，经过社区验证",
                "持续更新和Bug修复",
            ]
            for b in benefits:
                content += f"- {b}\n"
        else:
            content += "- 待分析\n"

        content += f"""
## 风险评估

- 引入外部依赖
- 迁移成本
- 协议兼容性

## 建议

"""

        if candidate_library:
            content += f"""
1. **评估阶段**: 对比 {candidate_library.get('name')} 与当前实现
2. **封装测试**: 使用适配器封装，保持接口不变
3. **小范围试点**: 先在非核心模块试用
4. **全面推广**: 验证稳定后全面替换
"""

        proposal = EvolutionProposal(
            id=proposal_id,
            title=title,
            content=content,
            referenced_article_id=article.id,
            referenced_library=candidate_library.get("name") if candidate_library else None,
            original_link=article.url,
            impact_analysis=article.architecture_impact or "待评估",
            benefits=benefits if candidate_library else [],
            status="draft",
            author_client_id="system",
            created_at=int(time.time()),
        )

        self._proposals[proposal_id] = proposal
        self._save_proposals()

        return proposal

    def auto_generate_proposals(
        self,
        relevance_threshold: float = 0.5,
    ) -> List[EvolutionProposal]:
        """
        自动生成提案

        Args:
            relevance_threshold: 相关性阈值

        Returns:
            List[EvolutionProposal]: 新生成的提案
        """
        proposals = []
        articles = self._collector.get_recent_articles(days=7)

        # 获取当前模块列表
        current_modules = []
        if self._current_modules_getter:
            try:
                current_modules = self._current_modules_getter()
            except Exception:
                pass

        for article in articles:
            # 检查是否已生成过
            if any(p.referenced_article_id == article.id for p in self._proposals.values()):
                continue

            # 评估相关性
            article.relevance_score = self._calculate_relevance(article, current_modules)

            if article.relevance_score >= relevance_threshold:
                proposal = self.generate_proposal(article)
                proposals.append(proposal)

        return proposals

    def _calculate_relevance(
        self,
        article: HotArticle,
        current_modules: List[str],
    ) -> float:
        """计算与当前架构的相关性"""
        score = 0.0

        # 基础分
        if article.relevance_score > 0:
            score += article.relevance_score * 0.3

        # 关键词匹配
        module_keywords = {
            "pdf": ["pdf", "document", "parser"],
            "markdown": ["markdown", "parser", "render"],
            "http": ["http", "client", "request"],
            "async": ["async", "await", "concurrency"],
            "cache": ["cache", "redis", "memory"],
            "database": ["database", "sql", "orm"],
        }

        for module, keywords in module_keywords.items():
            if module in current_modules:
                title_lower = article.title.lower()
                summary_lower = article.summary.lower()
                if any(k in title_lower or k in summary_lower for k in keywords):
                    score += 0.2

        # 来源权重
        if article.source == "github_trending":
            score += 0.2

        return min(1.0, score)

    def publish_proposal(self, proposal_id: str) -> bool:
        """发布提案到社区"""
        if proposal_id not in self._proposals:
            return False

        proposal = self._proposals[proposal_id]
        proposal.status = "proposed"
        proposal.published_at = int(time.time())
        self._save_proposals()

        # TODO: 实际发布到中继服务器或论坛
        logger.info(f"Published proposal {proposal_id}: {proposal.title}")

        return True

    def upvote_proposal(self, proposal_id: str) -> int:
        """为提案点赞"""
        if proposal_id in self._proposals:
            self._proposals[proposal_id].upvotes += 1
            self._save_proposals()
            return self._proposals[proposal_id].upvotes
        return 0

    def decide_proposal(
        self,
        proposal_id: str,
        decision: str,  # approved / rejected
        note: str = "",
    ) -> bool:
        """提案表决"""
        if proposal_id not in self._proposals:
            return False

        proposal = self._proposals[proposal_id]
        proposal.status = decision
        proposal.decided_at = int(time.time())
        proposal.decision_note = note
        self._save_proposals()

        return True

    def get_proposal(self, proposal_id: str) -> Optional[EvolutionProposal]:
        """获取提案"""
        return self._proposals.get(proposal_id)

    def get_all_proposals(self) -> List[EvolutionProposal]:
        """获取所有提案"""
        return list(self._proposals.values())

    def get_proposals_by_status(self, status: str) -> List[EvolutionProposal]:
        """按状态获取提案"""
        return [p for p in self._proposals.values() if p.status == status]

    def get_top_proposals(self, limit: int = 10) -> List[EvolutionProposal]:
        """获取热门提案"""
        return sorted(
            self._proposals.values(),
            key=lambda p: p.upvotes,
            reverse=True,
        )[:limit]


# ============ 社区进化调度器 ============

class CommunityEvolutionScheduler:
    """
    社区进化调度器

    功能:
    1. 定期采集热点
    2. 自动生成提案
    3. 推送通知
    """

    def __init__(
        self,
        collector: HotArticleCollector = None,
        proposal_generator: ProposalGenerator = None,
    ):
        self._collector = collector or HotArticleCollector()
        self._generator = proposal_generator or ProposalGenerator(
            collector=self._collector,
        )
        self._running = False
        self._last_collect_time: Optional[int] = None
        self._notifications: List[Dict] = []

    async def start(self, interval_hours: float = 24.0):
        """
        启动调度

        Args:
            interval_hours: 采集间隔(小时)
        """
        self._running = True

        while self._running:
            try:
                await self._run_collection_cycle()
            except Exception as e:
                logger.error(f"Collection cycle failed: {e}")

            await asyncio.sleep(interval_hours * 3600)

    def stop(self):
        """停止调度"""
        self._running = False

    async def _run_collection_cycle(self):
        """执行采集周期"""
        logger.info("Starting collection cycle...")

        # 1. 采集热点
        await self._collector.collect_github_trending()
        await self._collector.collect_hackernews()

        # 2. 生成提案
        new_proposals = self._generator.auto_generate_proposals()

        # 3. 生成通知
        for proposal in new_proposals:
            self._notifications.append({
                "type": "new_proposal",
                "proposal_id": proposal.id,
                "title": proposal.title,
                "relevance": self._get_referenced_article(proposal).relevance_score,
                "timestamp": int(time.time()),
            })

        self._last_collect_time = int(time.time())
        logger.info(f"Collection cycle completed. Generated {len(new_proposals)} proposals.")

    def _get_referenced_article(self, proposal: EvolutionProposal) -> Optional[HotArticle]:
        """获取引用的文章"""
        if proposal.referenced_article_id:
            return self._collector._articles.get(proposal.referenced_article_id)
        return None

    def get_notifications(self) -> List[Dict]:
        """获取通知"""
        return self._notifications.copy()

    def clear_notifications(self):
        """清空通知"""
        self._notifications.clear()

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计"""
        proposals = self._generator.get_all_proposals()

        return {
            "total_articles": len(self._collector.get_all_articles()),
            "recent_articles": len(self._collector.get_recent_articles(days=7)),
            "total_proposals": len(proposals),
            "proposals_by_status": {
                status: len(self._generator.get_proposals_by_status(status))
                for status in ["draft", "proposed", "discussing", "approved", "rejected"]
            },
            "top_proposals": [
                {"id": p.id, "title": p.title, "upvotes": p.upvotes}
                for p in self._generator.get_top_proposals(5)
            ],
            "last_collect_time": self._last_collect_time,
        }


# ============ 全局实例 ============

_collector: Optional[HotArticleCollector] = None
_proposal_generator: Optional[ProposalGenerator] = None
_scheduler: Optional[CommunityEvolutionScheduler] = None


def get_hot_collector() -> HotArticleCollector:
    """获取热点采集器"""
    global _collector
    if _collector is None:
        _collector = HotArticleCollector()
    return _collector


def get_proposal_generator() -> ProposalGenerator:
    """获取提案生成器"""
    global _proposal_generator
    if _proposal_generator is None:
        _proposal_generator = ProposalGenerator(collector=get_hot_collector())
    return _proposal_generator


def get_evolution_scheduler() -> CommunityEvolutionScheduler:
    """获取进化调度器"""
    global _scheduler
    if _scheduler is None:
        _scheduler = CommunityEvolutionScheduler(
            collector=get_hot_collector(),
            proposal_generator=get_proposal_generator(),
        )
    return _scheduler
