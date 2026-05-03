"""
Self-Upgrade System — 智能体自我升级引擎

四大升级引擎（闭环架构）：

1. DebateEngine（本地左右互搏）— Hermes 分饰保守派/激进派对辩
2. ExternalAbsorption（外部营养吸收）— 从 GitHub/Reddit 等平台吸收新知
3. SafetyPipeline（安全审查管道）— 4 层安全过滤（关键词→模式→链接→来源）
4. HumanReviewer（人类修正回路）— 展示辩论/外部洞察，人类可审核

辅助组件：
- KnowledgeBase: SQLite 进化知识库（版本管理 + 过期机制）
- EvolutionScheduler: 闲置调度器（idle/conflict/publish/manual）

从 client/src/business/self_upgrade/ 迁移，修复 4 个 bug：
  - evolution_scheduler.py 硬编码 legacy import → 改用 livingtree config
  - external_absorption.py check_safety() 循环导入风险 → 改为实例方法
  - debate_engine.py 硬编码 system_brain → 可注入 model_func
  - knowledge_base.py SQL 直接字符串 verdict → 使用 HumanVerdict enum
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


# ═══════════════════════════════════════════════════════════════════════
# 1. 数据模型
# ═══════════════════════════════════════════════════════════════════════

class DebateRole(Enum):
    CONSERVATIVE = "conservative"  # 保守派 — 稳健、风险规避
    RADICAL = "radical"            # 激进派 — 创新、风险偏好
    MEDIATOR = "mediator"          # 调解者 — 综合两边


class DebateVerdict(Enum):
    CONSERVATIVE_WINS = "conservative_wins"
    RADICAL_WINS = "radical_wins"
    COMPROMISE = "compromise"
    INCONCLUSIVE = "inconclusive"
    TBD = "tbd"


class ExternalSource(Enum):
    REDDIT = "reddit"
    ZHIHU = "zhihu"
    WEIBO = "weibo"
    GITHUB = "github"
    NEWS = "news"
    UNKNOWN = "unknown"


class HumanVerdict(Enum):
    APPROVED = "approved"
    REVISED = "revised"
    REJECTED = "rejected"
    PENDING = "pending"


class SafetyLevel(Enum):
    SAFE = "safe"
    REVIEW = "review"
    BLOCK = "block"


@dataclass
class DebateArgument:
    role: DebateRole
    point: str = ""            # 论点 (renamed from 论点 for code clarity)
    evidence: List[str] = field(default_factory=list)  # 论据
    rebuttal: str = ""          # 反驳
    confidence: float = 0.5

    # Backward compat: allow Chinese attribute access
    def __getattr__(self, name: str):
        _map = {"论点": "point", "论据": "evidence", "反驳": "rebuttal"}
        if name in _map:
            return getattr(self, _map[name])
        raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")


@dataclass
class DebateRecord:
    id: str
    topic: str
    topic_category: str = "general"
    context: Dict[str, Any] = field(default_factory=dict)
    conservative_args: List[DebateArgument] = field(default_factory=list)
    radical_args: List[DebateArgument] = field(default_factory=list)
    verdict: DebateVerdict = DebateVerdict.TBD
    final_conclusion: str = ""
    contradictions: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    human_verdict: HumanVerdict = HumanVerdict.PENDING
    human_notes: str = ""


@dataclass
class ExternalInsight:
    id: str
    source: ExternalSource
    source_url: str = ""
    source_title: str = ""
    content_summary: str = ""
    key_points: List[str] = field(default_factory=list)
    local_belief: str = ""
    difference_flagged: str = ""
    absorbed: bool = False
    absorbed_at: Optional[datetime] = None
    safety_level: SafetyLevel = SafetyLevel.SAFE
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class KnowledgeEntry:
    id: str
    category: str
    key: str
    value: str
    source_debate_id: Optional[str] = None
    source_external_id: Optional[str] = None
    human_verdict: HumanVerdict = HumanVerdict.PENDING
    version: int = 1
    previous_value: str = ""
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    expired_at: Optional[datetime] = None


@dataclass
class SafetyCheckResult:
    passed: bool
    level: SafetyLevel
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvolutionTask:
    id: str
    task_type: str  # debate | external | review | safety
    trigger: str = "manual"  # idle | conflict | publish | manual
    status: str = "pending"
    topic: str = ""
    result_summary: str = ""
    error_message: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


@dataclass
class SystemConfig:
    idle_trigger_minutes: int = 5
    auto_debate_enabled: bool = True
    auto_external_enabled: bool = True
    auto_safety_enabled: bool = True
    reddit_enabled: bool = False
    zhihu_enabled: bool = False
    weibo_enabled: bool = False
    safety_level_strict: bool = True
    require_human_review: bool = True
    max_arguments_per_side: int = 3
    debate_rounds: int = 2


# ═══════════════════════════════════════════════════════════════════════
# 2. DebateEngine — 本地左右互搏辩论引擎
# ═══════════════════════════════════════════════════════════════════════

class DebateEngine:
    """左右互搏辩论引擎 — 保守派 vs 激进派"""

    def __init__(self, data_dir: Optional[Path] = None,
                 model_func: Optional[Callable] = None):
        self.data_dir = data_dir or Path.home() / ".livingtree" / "self_upgrade"
        self.debates_dir = self.data_dir / "debates"
        self.debates_dir.mkdir(parents=True, exist_ok=True)
        self._model_func = model_func  # 可注入模型调用函数

        self._conservative_prompt = (
            "你是谨慎稳健的思考者「守」。强调风险控制、渐进改进、关注失败模式。"
            "针对以下辩题，提出 {n} 个论点。输出 JSON: "
            '{{"arguments":[{{"point":"核心观点","evidence":["论据1","论据2"],'
            '"rebuttal":"回应反驳","confidence":0.7}}]}}'
        )
        self._radical_prompt = (
            "你是创新进取的思考者「进」。强调创新突破、愿意承担可控风险。"
            "针对以下辩题，提出 {n} 个论点。输出 JSON: "
            '{{"arguments":[{{"point":"核心观点","evidence":["论据1","论据2"],'
            '"rebuttal":"回应反驳","confidence":0.7}}]}}'
        )

    def _gen_id(self) -> str:
        return f"debate_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"

    async def debate(self, topic: str, topic_category: str = "general",
                     context: Optional[Dict[str, Any]] = None,
                     n_arguments: int = 3,
                     use_model: bool = True) -> DebateRecord:
        record = DebateRecord(
            id=self._gen_id(), topic=topic,
            topic_category=topic_category, context=context or {},
        )
        ctx = context or {}

        record.conservative_args = await self._gen_args(
            DebateRole.CONSERVATIVE, topic, ctx, n_arguments, use_model)
        record.radical_args = await self._gen_args(
            DebateRole.RADICAL, topic, ctx, n_arguments, use_model)
        record = await self._cross_examine(record, use_model)
        record = await self._mediate(record, use_model)
        record.contradictions = self._find_contradictions(record)
        self._save_record(record)
        return record

    async def _gen_args(self, role: DebateRole, topic: str,
                        context: Dict[str, Any], n: int,
                        use_model: bool) -> List[DebateArgument]:
        prompt_tmpl = self._conservative_prompt if role == DebateRole.CONSERVATIVE else self._radical_prompt
        ctx_str = ""
        if context:
            ctx_str = "\n\n参考上下文：\n" + json.dumps(context, ensure_ascii=False, indent=2)

        full_prompt = f"""{prompt_tmpl.format(n=n)}

辩题：{topic}
{ctx_str}"""

        if use_model and self._model_func:
            try:
                result = await self._model_func(full_prompt)
                return self._parse_response(result, role)
            except Exception as e:
                pass  # fallback to templates

        return self._fallback_args(role, topic, n)

    def _parse_response(self, response: str, role: DebateRole) -> List[DebateArgument]:
        try:
            data = json.loads(response)
            return [
                DebateArgument(
                    role=role,
                    point=item.get("point", item.get("论点", "")),
                    evidence=item.get("evidence", item.get("论据", [])),
                    rebuttal=item.get("rebuttal", item.get("反驳", "")),
                    confidence=item.get("confidence", 0.5),
                )
                for item in data.get("arguments", [])
            ]
        except json.JSONDecodeError:
            return self._fallback_args(role, "", 3)

    async def _cross_examine(self, record: DebateRecord,
                              use_model: bool) -> DebateRecord:
        for arg in record.radical_args:
            if use_model and self._model_func:
                try:
                    resp = await self._model_func(
                        f"保守派反驳: {arg.point} (证据: {'; '.join(arg.evidence)}). 50字内。")
                    arg.rebuttal = resp.strip()[:200]
                except Exception:
                    arg.rebuttal = "[需要人工审核]"
            else:
                arg.rebuttal = "[需要人工审核]"

        for arg in record.conservative_args:
            if use_model and self._model_func:
                try:
                    resp = await self._model_func(
                        f"激进派反驳: {arg.point} (证据: {'; '.join(arg.evidence)}). 50字内。")
                    arg.rebuttal = resp.strip()[:200]
                except Exception:
                    arg.rebuttal = "[需要人工审核]"
            else:
                arg.rebuttal = "[需要人工审核]"

        return record

    async def _mediate(self, record: DebateRecord,
                        use_model: bool) -> DebateRecord:
        con_view = "\n".join(
            f"- {a.point} (置信度:{a.confidence})" for a in record.conservative_args)
        rad_view = "\n".join(
            f"- {a.point} (置信度:{a.confidence})" for a in record.radical_args)

        prompt = f"""调解者「衡」综合辩论：

辩题：{record.topic}
保守派「守」观点：\n{con_view}
激进派「进」观点：\n{rad_view}

输出 JSON: {{"verdict":"conservative_wins/radical_wins/compromise/inconclusive","conclusion":"100字内"}}"""

        if use_model and self._model_func:
            try:
                result = await self._model_func(prompt)
                data = json.loads(result)
                v = data.get("verdict", "inconclusive").lower()
                record.verdict = {
                    "conservative": DebateVerdict.CONSERVATIVE_WINS,
                    "radical": DebateVerdict.RADICAL_WINS,
                    "compromise": DebateVerdict.COMPROMISE,
                }.get(v, DebateVerdict.INCONCLUSIVE)
                record.final_conclusion = data.get("conclusion", "")
            except Exception:
                record.verdict = DebateVerdict.INCONCLUSIVE
                record.final_conclusion = "[需要人工裁决]"
        else:
            record.verdict = DebateVerdict.INCONCLUSIVE
            record.final_conclusion = "[需要人工裁决]"

        record.updated_at = datetime.now()
        return record

    def _find_contradictions(self, record: DebateRecord) -> List[str]:
        contradictions = []
        for ca in record.conservative_args:
            for ra in record.radical_args:
                if abs(ca.confidence - ra.confidence) > 0.4:
                    contradictions.append(
                        f"置信度冲突：保守派({ca.confidence}) vs 激进派({ra.confidence})")
        if record.verdict == DebateVerdict.INCONCLUSIVE:
            contradictions.append("辩论未能得出明确结论，需人工裁决")
        return contradictions

    @staticmethod
    def _fallback_args(role: DebateRole, topic: str, n: int) -> List[DebateArgument]:
        if role == DebateRole.CONSERVATIVE:
            templates = [
                ("稳定性优先", ["方案经过验证", "风险可控", "用户熟悉"], 0.7),
                ("渐进改进更安全", ["避免剧烈变化", "便于回滚", "降低学习成本"], 0.6),
                ("保守策略降低风险", ["减少未知因素", "保护已有投入", "稳妥推进"], 0.5),
            ]
        else:
            templates = [
                ("创新带来突破", ["可能获得更大收益", "解决根本问题", "创造新机会"], 0.7),
                ("敢于尝试新方法", ["探索更多可能性", "发现隐藏机会", "突破思维定式"], 0.6),
                ("激进策略加速进化", ["快速试错迭代", "抓住窗口期", "领先竞争对手"], 0.5),
            ]
        return [
            DebateArgument(
                role=role, point=f"{topic} - {t[0]}",
                evidence=list(t[1]), confidence=t[2],
            )
            for t in templates[:n]
        ]

    def _save_record(self, record: DebateRecord) -> None:
        file_path = self.debates_dir / f"{record.id}.json"
        data = {
            "id": record.id, "topic": record.topic,
            "topic_category": record.topic_category,
            "context": record.context,
            "conservative_args": [
                {"point": a.point, "evidence": a.evidence,
                 "rebuttal": a.rebuttal, "confidence": a.confidence}
                for a in record.conservative_args
            ],
            "radical_args": [
                {"point": a.point, "evidence": a.evidence,
                 "rebuttal": a.rebuttal, "confidence": a.confidence}
                for a in record.radical_args
            ],
            "verdict": record.verdict.value,
            "final_conclusion": record.final_conclusion,
            "contradictions": record.contradictions,
            "human_verdict": record.human_verdict.value,
            "human_notes": record.human_notes,
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_record(self, debate_id: str) -> Optional[DebateRecord]:
        file_path = self.debates_dir / f"{debate_id}.json"
        if not file_path.exists():
            return None
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
        record = DebateRecord(
            id=data["id"], topic=data["topic"],
            topic_category=data.get("topic_category", "general"),
            context=data.get("context", {}),
            verdict=DebateVerdict(data.get("verdict", "tbd")),
            final_conclusion=data.get("final_conclusion", ""),
            contradictions=data.get("contradictions", []),
            human_verdict=HumanVerdict(data.get("human_verdict", "pending")),
            human_notes=data.get("human_notes", ""),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )
        record.conservative_args = [
            DebateArgument(role=DebateRole.CONSERVATIVE,
                           point=a.get("point", a.get("论点", "")),
                           evidence=a.get("evidence", a.get("论据", [])),
                           rebuttal=a.get("rebuttal", a.get("反驳", "")),
                           confidence=a.get("confidence", 0.5))
            for a in data.get("conservative_args", [])
        ]
        record.radical_args = [
            DebateArgument(role=DebateRole.RADICAL,
                           point=a.get("point", a.get("论点", "")),
                           evidence=a.get("evidence", a.get("论据", [])),
                           rebuttal=a.get("rebuttal", a.get("反驳", "")),
                           confidence=a.get("confidence", 0.5))
            for a in data.get("radical_args", [])
        ]
        return record

    def list_records(self, limit: int = 20) -> List[DebateRecord]:
        records = []
        for f in sorted(self.debates_dir.glob("debate_*.json"), reverse=True)[:limit]:
            rec = self.load_record(f.stem)
            if rec:
                records.append(rec)
        return records

    def update_verdict(self, debate_id: str, verdict: HumanVerdict,
                       notes: str = "") -> bool:
        record = self.load_record(debate_id)
        if not record:
            return False
        record.human_verdict = verdict
        record.human_notes = notes
        record.updated_at = datetime.now()
        self._save_record(record)
        return True


# ═══════════════════════════════════════════════════════════════════════
# 3. ExternalAbsorption — 外部营养吸收
# ═══════════════════════════════════════════════════════════════════════

class ExternalAbsorption:
    """外部营养吸收器 — 从 GitHub/Reddit/Zhihu 等平台抓取并消化内容"""

    def __init__(self, data_dir: Optional[Path] = None,
                 safety_check: Optional[Callable[[str, Optional[Dict]], SafetyCheckResult]] = None):
        self.data_dir = data_dir or Path.home() / ".livingtree" / "self_upgrade"
        self.insights_dir = self.data_dir / "external_insights"
        self.insights_dir.mkdir(parents=True, exist_ok=True)
        self._safety_check = safety_check

        self._platforms = {
            "reddit": {
                "enabled": False,
                "subreddits": ["MachineLearning", "programming", "artificial"],
            },
            "zhihu": {
                "enabled": False,
                "topics": ["人工智能", "机器学习", "编程"],
            },
            "github": {
                "enabled": True,
                "repos": ["microsoft/vscode", "openai/gym"],
            },
        }

    async def fetch_github_issues(self, repo: str,
                                   limit: int = 10) -> List[Dict[str, Any]]:
        try:
            from github import Github
            token = os.environ.get("GITHUB_TOKEN")
            if not token:
                return []
            g = Github(token)
            repo_obj = g.get_repo(repo)
            issues = repo_obj.get_issues(state="open", sort="created")[:limit]
            return [{
                "title": i.title, "body": i.body or "",
                "url": i.html_url, "comments": i.comments,
                "labels": [l.name for l in i.labels],
                "created_at": i.created_at.isoformat(),
            } for i in issues]
        except ImportError:
            return []
        except Exception as e:
            return []

    async def fetch_reddit_trending(self, subreddit: str,
                                     limit: int = 10) -> List[Dict[str, Any]]:
        return []  # 需要 Reddit API 认证

    async def fetch_zhihu_daily(self, topic: str,
                                 limit: int = 10) -> List[Dict[str, Any]]:
        return []  # 需要知乎 OAuth

    async def absorb(self, source: ExternalSource,
                     content: Dict[str, Any],
                     local_belief: str = "") -> ExternalInsight:
        insight = ExternalInsight(
            id=str(uuid.uuid4()),
            source=source,
            source_url=content.get("url", ""),
            source_title=content.get("title", ""),
            content_summary=self._summarize(content),
            key_points=self._extract_key_points(content),
            local_belief=local_belief,
        )
        if local_belief:
            insight.difference_flagged = self._find_difference(
                insight.key_points, local_belief)

        # 安全审查 — 使用注入的 check 或内置简化版
        if self._safety_check:
            result = self._safety_check(
                insight.content_summary + " " + " ".join(insight.key_points))
            insight.safety_level = result.level
        else:
            insight.safety_level = SafetyLevel.SAFE

        self._save_insight(insight)
        return insight

    @staticmethod
    def _summarize(content: Dict[str, Any]) -> str:
        body = content.get("body", "") or content.get("text", "") or ""
        title = content.get("title", "")
        if len(body) > 300:
            return f"{title} — {body[:300]}..."
        return f"{title} — {body}"

    @staticmethod
    def _extract_key_points(content: Dict[str, Any]) -> List[str]:
        points = []
        title = content.get("title", "")
        if title:
            points.append(title)
        labels = content.get("labels", []) or content.get("tags", [])
        if labels:
            points.extend([f"标签: {l}" for l in labels[:3]])
        comments = content.get("comments", 0)
        if comments and comments > 10:
            points.append(f"高热度讨论 ({comments} 评论)")
        return points[:5]

    @staticmethod
    def _find_difference(external_points: List[str], local_belief: str) -> str:
        local_words = set(local_belief.lower().split())
        for point in external_points:
            point_words = set(point.lower().split())
            if len(local_words & point_words) < 2:
                return f"新观点: {point}"
        return "与本地认知一致"

    def _insight_path(self, insight_id: str) -> Path:
        return self.insights_dir / f"{insight_id}.json"

    def _save_insight(self, insight: ExternalInsight) -> None:
        data = {
            "id": insight.id, "source": insight.source.value,
            "source_url": insight.source_url,
            "source_title": insight.source_title,
            "content_summary": insight.content_summary,
            "key_points": insight.key_points,
            "local_belief": insight.local_belief,
            "difference_flagged": insight.difference_flagged,
            "absorbed": insight.absorbed,
            "absorbed_at": insight.absorbed_at.isoformat() if insight.absorbed_at else None,
            "safety_level": insight.safety_level.value,
            "created_at": insight.created_at.isoformat(),
        }
        with open(self._insight_path(insight.id), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_insight(self, insight_id: str) -> Optional[ExternalInsight]:
        path = self._insight_path(insight_id)
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return ExternalInsight(
            id=data["id"],
            source=ExternalSource(data["source"]),
            source_url=data["source_url"],
            source_title=data["source_title"],
            content_summary=data["content_summary"],
            key_points=data["key_points"],
            local_belief=data["local_belief"],
            difference_flagged=data["difference_flagged"],
            absorbed=data["absorbed"],
            absorbed_at=datetime.fromisoformat(data["absorbed_at"]) if data["absorbed_at"] else None,
            safety_level=SafetyLevel(data["safety_level"]),
            created_at=datetime.fromisoformat(data["created_at"]),
        )

    def list_insights(self, source: Optional[ExternalSource] = None,
                      absorbed: Optional[bool] = None,
                      limit: int = 50) -> List[ExternalInsight]:
        insights = []
        for f in sorted(self.insights_dir.glob("*.json"), reverse=True):
            if len(insights) >= limit:
                break
            insight = self.load_insight(f.stem)
            if not insight:
                continue
            if source and insight.source != source:
                continue
            if absorbed is not None and insight.absorbed != absorbed:
                continue
            insights.append(insight)
        return insights

    def mark_absorbed(self, insight_id: str) -> bool:
        insight = self.load_insight(insight_id)
        if not insight:
            return False
        insight.absorbed = True
        insight.absorbed_at = datetime.now()
        self._save_insight(insight)
        return True

    def get_stats(self) -> Dict[str, Any]:
        insights = self.list_insights(limit=1000)
        return {
            "total": len(insights),
            "absorbed": sum(1 for i in insights if i.absorbed),
            "pending": sum(1 for i in insights if not i.absorbed),
            "by_source": {
                s.value: sum(1 for i in insights if i.source == s)
                for s in ExternalSource
            },
        }


# ═══════════════════════════════════════════════════════════════════════
# 4. SafetyPipeline — 安全审查管道
# ═══════════════════════════════════════════════════════════════════════

class SafetyPipeline:
    """安全审查管道 — 4 层过滤"""

    DANGEROUS_PATTERNS = [
        (r"<script[^>]*>.*?</script>", "XSS注入风险"),
        (r"javascript:", "JavaScript协议"),
        (r"on\w+\s*=", "事件处理器注入"),
        (r"\b\d{15,18}\b", "疑似身份证号"),
        (r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", "疑似银行卡号"),
        (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "邮箱地址"),
    ]

    SUSPICIOUS_PATTERNS = [
        (r"https?://[^\s<>\"']+", "外部链接"),
        (r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "IP地址"),
    ]

    UNSAFE_DOMAINS = [
        "phishing", "malware", "spam", "scam",
        "888", "bet", "casino", "gambling",
    ]

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path.home() / ".livingtree" / "safety"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._block_list: List[Dict] = self._load_json("block_list.json")
        self._warn_list: List[Dict] = self._load_json("warn_list.json")
        self._strict_mode = True

    def check(self, content: str,
              metadata: Optional[Dict[str, Any]] = None) -> SafetyCheckResult:
        result = SafetyCheckResult(
            passed=True, level=SafetyLevel.SAFE,
            details=metadata or {})

        # Layer 1: 关键词
        kw = self._check_keywords(content)
        if not kw["passed"]:
            result.passed = False
            result.level = SafetyLevel.BLOCK
            result.issues.extend(kw["issues"])
            return result
        if kw["warnings"]:
            result.warnings.extend(kw["warnings"])
            if self._strict_mode:
                result.level = SafetyLevel.REVIEW

        # Layer 2: 模式匹配
        pat = self._check_patterns(content)
        if not pat["passed"]:
            result.passed = False
            result.level = SafetyLevel.BLOCK
            result.issues.extend(pat["issues"])
            return result
        if pat["warnings"]:
            result.warnings.extend(pat["warnings"])
            if self._strict_mode and result.level != SafetyLevel.REVIEW:
                result.level = SafetyLevel.REVIEW

        # Layer 3: 外部链接
        link = self._check_external_links(content)
        if link["warnings"]:
            result.warnings.extend(link["warnings"])

        # Layer 4: 来源检查
        if metadata:
            src = self._check_source(metadata)
            if src["issues"]:
                result.issues.extend(src["issues"])
                result.passed = False
                result.level = SafetyLevel.BLOCK

        return result

    def check_batch(self, contents: List[str]) -> List[SafetyCheckResult]:
        return [self.check(c) for c in contents]

    def add_to_block_list(self, keyword: str, reason: str = "") -> None:
        entry = {"keyword": keyword, "reason": reason,
                 "added_at": datetime.now().isoformat()}
        if keyword not in [e["keyword"] for e in self._block_list]:
            self._block_list.append(entry)
            self._save_json("block_list.json", self._block_list)

    def add_to_warn_list(self, keyword: str, reason: str = "") -> None:
        entry = {"keyword": keyword, "reason": reason,
                 "added_at": datetime.now().isoformat()}
        if keyword not in [e["keyword"] for e in self._warn_list]:
            self._warn_list.append(entry)
            self._save_json("warn_list.json", self._warn_list)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "block_list_size": len(self._block_list),
            "warn_list_size": len(self._warn_list),
            "strict_mode": self._strict_mode,
        }

    def _check_keywords(self, content: str) -> Dict:
        issues = []
        warnings = []
        content_lower = content.lower()
        for entry in self._block_list:
            if entry["keyword"].lower() in content_lower:
                issues.append(f"拦截词命中: {entry['keyword']}")
        for entry in self._warn_list:
            if entry["keyword"].lower() in content_lower:
                warnings.append(f"警告词命中: {entry['keyword']}")
        return {"passed": len(issues) == 0, "issues": issues, "warnings": warnings}

    def _check_patterns(self, content: str) -> Dict:
        issues = []
        warnings = []
        for pattern, desc in self.DANGEROUS_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE | re.DOTALL):
                issues.append(f"危险模式: {desc}")
        for pattern, desc in self.SUSPICIOUS_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                warnings.append(f"可疑模式: {desc}")
        return {"passed": len(issues) == 0, "issues": issues, "warnings": warnings}

    def _check_external_links(self, content: str) -> Dict:
        warnings = []
        urls = re.findall(r'https?://[^\s<>"\']+', content)
        for url in urls:
            try:
                domain = url.split('/')[2].lower()
                for unsafe in self.UNSAFE_DOMAINS:
                    if unsafe in domain:
                        warnings.append(f"可疑域名: {domain}")
                        break
            except Exception:
                pass
        return {"warnings": warnings}

    @staticmethod
    def _check_source(metadata: Dict[str, Any]) -> Dict:
        issues = []
        source = metadata.get("source", "").lower()
        if source in ("unknown", "anonymous", "untrusted"):
            issues.append(f"不可信来源: {source}")
        return {"issues": issues}

    def _load_json(self, filename: str) -> List[Dict]:
        path = self.data_dir / filename
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _save_json(self, filename: str, data: List[Dict]) -> None:
        with open(self.data_dir / filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════════════════════
# 5. KnowledgeBase — 进化知识库
# ═══════════════════════════════════════════════════════════════════════

class KnowledgeBase:
    """进化知识库 — SQLite + 版本管理 + 过期机制"""

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path.home() / ".livingtree" / "self_upgrade"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "knowledge.db"
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_entries (
                    id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    source_debate_id TEXT,
                    source_external_id TEXT,
                    human_verdict TEXT DEFAULT 'pending',
                    version INTEGER DEFAULT 1,
                    previous_value TEXT,
                    tags TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    expired_at TEXT,
                    UNIQUE(category, key)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_kb_category ON knowledge_entries(category)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_kb_key ON knowledge_entries(key)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_kb_verdict ON knowledge_entries(human_verdict)")
            conn.commit()

    def add(self, category: str, key: str, value: str,
            source_debate_id: Optional[str] = None,
            source_external_id: Optional[str] = None,
            tags: Optional[List[str]] = None,
            human_verdict: HumanVerdict = HumanVerdict.PENDING,
            expired_at: Optional[datetime] = None) -> KnowledgeEntry:
        entry = KnowledgeEntry(
            id=str(uuid.uuid4()), category=category, key=key, value=value,
            source_debate_id=source_debate_id,
            source_external_id=source_external_id,
            human_verdict=human_verdict,
            tags=tags or [], expired_at=expired_at,
        )
        conn = self._conn()
        row = conn.execute(
            "SELECT id, value FROM knowledge_entries WHERE category=? AND key=?",
            (category, key)).fetchone()

        if row:
            entry.id = row["id"]
            entry.version = self._get_version(category, key) + 1
            entry.previous_value = row["value"]
            conn.execute("""
                UPDATE knowledge_entries
                SET value=?, version=?, previous_value=?, human_verdict=?,
                    updated_at=?, tags=?, expired_at=?
                WHERE id=?
            """, (value, entry.version, row["value"], human_verdict.value,
                  datetime.now().isoformat(),
                  json.dumps(tags or [], ensure_ascii=False),
                  expired_at.isoformat() if expired_at else None,
                  entry.id))
        else:
            conn.execute("""
                INSERT INTO knowledge_entries
                (id, category, key, value, source_debate_id, source_external_id,
                 human_verdict, tags, created_at, updated_at, expired_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (entry.id, category, key, value, source_debate_id,
                  source_external_id, human_verdict.value,
                  json.dumps(tags or [], ensure_ascii=False),
                  datetime.now().isoformat(), datetime.now().isoformat(),
                  expired_at.isoformat() if expired_at else None))
        conn.commit()
        conn.close()
        return entry

    def get(self, category: str, key: str) -> Optional[KnowledgeEntry]:
        conn = self._conn()
        row = conn.execute("""
            SELECT * FROM knowledge_entries
            WHERE category=? AND key=? AND (expired_at IS NULL OR expired_at > ?)
            ORDER BY version DESC LIMIT 1
        """, (category, key, datetime.now().isoformat())).fetchone()
        conn.close()
        return self._row_to_entry(row) if row else None

    def get_all(self, category: Optional[str] = None,
                verdict: Optional[HumanVerdict] = None,
                limit: int = 100) -> List[KnowledgeEntry]:
        conn = self._conn()
        query = "SELECT * FROM knowledge_entries WHERE 1=1"
        params: List[Any] = []
        if category:
            query += " AND category=?"
            params.append(category)
        if verdict:
            query += " AND human_verdict=?"
            params.append(verdict.value)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [self._row_to_entry(r) for r in rows]

    def search(self, keyword: str, limit: int = 20) -> List[KnowledgeEntry]:
        conn = self._conn()
        rows = conn.execute("""
            SELECT * FROM knowledge_entries
            WHERE (key LIKE ? OR value LIKE ? OR tags LIKE ?)
            ORDER BY updated_at DESC LIMIT ?
        """, (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", limit)).fetchall()
        conn.close()
        return [self._row_to_entry(r) for r in rows]

    def update_verdict(self, entry_id: str, verdict: HumanVerdict,
                       new_value: Optional[str] = None) -> bool:
        conn = self._conn()
        if new_value:
            row = conn.execute(
                "SELECT value FROM knowledge_entries WHERE id=?", (entry_id,)).fetchone()
            if row:
                version = self._get_version_by_id(entry_id) + 1
                conn.execute("""
                    UPDATE knowledge_entries
                    SET value=?, version=?, previous_value=?, human_verdict=?,
                        updated_at=?
                    WHERE id=?
                """, (new_value, version, row["value"], verdict.value,
                      datetime.now().isoformat(), entry_id))
        else:
            conn.execute("""
                UPDATE knowledge_entries
                SET human_verdict=?, updated_at=?
                WHERE id=?
            """, (verdict.value, datetime.now().isoformat(), entry_id))
        conn.commit()
        affected = conn.total_changes
        conn.close()
        return affected > 0

    def delete(self, entry_id: str) -> bool:
        conn = self._conn()
        conn.execute("DELETE FROM knowledge_entries WHERE id=?", (entry_id,))
        conn.commit()
        affected = conn.total_changes
        conn.close()
        return affected > 0

    def get_stats(self) -> Dict[str, Any]:
        conn = self._conn()
        total = conn.execute("SELECT COUNT(*) FROM knowledge_entries").fetchone()[0]
        approved = conn.execute(
            "SELECT COUNT(*) FROM knowledge_entries WHERE human_verdict=?",
            (HumanVerdict.APPROVED.value,)).fetchone()[0]
        pending = conn.execute(
            "SELECT COUNT(*) FROM knowledge_entries WHERE human_verdict=?",
            (HumanVerdict.PENDING.value,)).fetchone()[0]
        rejected = conn.execute(
            "SELECT COUNT(*) FROM knowledge_entries WHERE human_verdict=?",
            (HumanVerdict.REJECTED.value,)).fetchone()[0]
        cats = [r[0] for r in conn.execute(
            "SELECT DISTINCT category FROM knowledge_entries").fetchall()]
        conn.close()
        return {
            "total": total, "approved": approved,
            "pending": pending, "rejected": rejected,
            "categories": cats,
        }

    def _get_version(self, category: str, key: str) -> int:
        conn = self._conn()
        row = conn.execute(
            "SELECT MAX(version) FROM knowledge_entries WHERE category=? AND key=?",
            (category, key)).fetchone()
        conn.close()
        return row[0] or 0

    def _get_version_by_id(self, entry_id: str) -> int:
        conn = self._conn()
        row = conn.execute(
            "SELECT version FROM knowledge_entries WHERE id=?", (entry_id,)).fetchone()
        conn.close()
        return row["version"] if row else 0

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> KnowledgeEntry:
        return KnowledgeEntry(
            id=row["id"], category=row["category"],
            key=row["key"], value=row["value"],
            source_debate_id=row["source_debate_id"],
            source_external_id=row["source_external_id"],
            human_verdict=HumanVerdict(row["human_verdict"]),
            version=row["version"],
            previous_value=row["previous_value"] or "",
            tags=json.loads(row["tags"]) if row["tags"] else [],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            expired_at=datetime.fromisoformat(row["expired_at"]) if row["expired_at"] else None,
        )


# ═══════════════════════════════════════════════════════════════════════
# 6. HumanReviewer — 思维审核室
# ═══════════════════════════════════════════════════════════════════════

class HumanReviewer:
    """思维审核室 — 展示辩论/洞察，人类操作：认可/修改/驳回"""

    def __init__(self, debate_engine: Optional[DebateEngine] = None,
                 knowledge_base: Optional[KnowledgeBase] = None,
                 external_absorption: Optional[ExternalAbsorption] = None):
        self.debate_engine = debate_engine or DebateEngine()
        self.knowledge_base = knowledge_base or KnowledgeBase()
        self.external_absorption = external_absorption or ExternalAbsorption()

    def get_pending_debates(self, limit: int = 20) -> List[DebateRecord]:
        records = self.debate_engine.list_records(limit=limit)
        return [r for r in records if r.human_verdict == HumanVerdict.PENDING]

    def get_pending_insights(self, limit: int = 20) -> List[ExternalInsight]:
        return self.external_absorption.list_insights(absorbed=False, limit=limit)

    def get_all_pending(self) -> Dict[str, Any]:
        pending_debates = self.get_pending_debates()
        pending_insights = self.get_pending_insights()
        return {
            "pending_debates": [self._format_debate_summary(r) for r in pending_debates],
            "pending_insights": [self._format_insight_summary(i) for i in pending_insights],
            "total_pending": len(pending_debates) + len(pending_insights),
        }

    def approve_debate(self, debate_id: str, conclusion: Optional[str] = None,
                       notes: str = "") -> bool:
        record = self.debate_engine.load_record(debate_id)
        if not record:
            return False
        self.debate_engine.update_verdict(debate_id, HumanVerdict.APPROVED, notes)
        self.knowledge_base.add(
            category=f"debate_{record.topic_category}",
            key=f"conclusion_{record.id}",
            value=conclusion or record.final_conclusion,
            source_debate_id=debate_id,
            human_verdict=HumanVerdict.APPROVED,
            tags=[record.topic_category, "debate"],
        )
        return True

    def revise_debate(self, debate_id: str, new_conclusion: str,
                      notes: str = "") -> bool:
        record = self.debate_engine.load_record(debate_id)
        if not record:
            return False
        self.debate_engine.update_verdict(debate_id, HumanVerdict.REVISED, notes)
        self.knowledge_base.add(
            category=f"debate_{record.topic_category}",
            key=f"conclusion_{record.id}",
            value=new_conclusion,
            source_debate_id=debate_id,
            human_verdict=HumanVerdict.REVISED,
            tags=[record.topic_category, "debate", "revised"],
        )
        return True

    def reject_debate(self, debate_id: str, reason: str = "") -> bool:
        return self.debate_engine.update_verdict(
            debate_id, HumanVerdict.REJECTED, reason)

    def absorb_insight(self, insight_id: str, knowledge_key: str,
                       category: str = "external") -> bool:
        insight = self.external_absorption.load_insight(insight_id)
        if not insight:
            return False
        self.knowledge_base.add(
            category=category, key=knowledge_key,
            value=insight.content_summary,
            source_external_id=insight_id,
            human_verdict=HumanVerdict.APPROVED,
            tags=[insight.source.value, "external"],
        )
        return self.external_absorption.mark_absorbed(insight_id)

    def get_debate_detail(self, debate_id: str) -> Optional[Dict[str, Any]]:
        record = self.debate_engine.load_record(debate_id)
        if not record:
            return None
        return {
            "id": record.id, "topic": record.topic,
            "category": record.topic_category,
            "verdict": record.verdict.value,
            "human_verdict": record.human_verdict.value,
            "human_notes": record.human_notes,
            "conclusion": record.final_conclusion,
            "contradictions": record.contradictions,
            "conservative_args": [
                {"point": a.point, "evidence": a.evidence,
                 "rebuttal": a.rebuttal, "confidence": a.confidence}
                for a in record.conservative_args
            ],
            "radical_args": [
                {"point": a.point, "evidence": a.evidence,
                 "rebuttal": a.rebuttal, "confidence": a.confidence}
                for a in record.radical_args
            ],
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
        }

    @staticmethod
    def _format_debate_summary(record: DebateRecord) -> Dict[str, Any]:
        return {
            "id": record.id, "topic": record.topic,
            "category": record.topic_category,
            "verdict": record.verdict.value,
            "conclusion": record.final_conclusion,
            "conservative_count": len(record.conservative_args),
            "radical_count": len(record.radical_args),
            "contradictions": record.contradictions,
            "created_at": record.created_at.strftime("%Y-%m-%d %H:%M"),
            "needs_review": len(record.contradictions) > 0 or record.verdict == DebateVerdict.INCONCLUSIVE,
        }

    @staticmethod
    def _format_insight_summary(insight: ExternalInsight) -> Dict[str, Any]:
        summary = insight.content_summary
        return {
            "id": insight.id, "source": insight.source.value,
            "title": insight.source_title,
            "summary": (summary[:100] + "...") if len(summary) > 100 else summary,
            "key_points": insight.key_points[:3],
            "difference": insight.difference_flagged,
            "safety": insight.safety_level.value,
            "created_at": insight.created_at.strftime("%Y-%m-%d %H:%M"),
        }


# ═══════════════════════════════════════════════════════════════════════
# 7. EvolutionScheduler — 进化任务调度器
# ═══════════════════════════════════════════════════════════════════════

class EvolutionScheduler:
    """进化任务调度器 — idle/conflict/publish/manual 触发"""

    def __init__(self, idle_minutes: int = 5, check_interval: int = 30):
        self.idle_minutes = idle_minutes
        self._idle_check_interval = check_interval
        self._last_activity = time.time()
        self._running = False
        self._thread: Optional[threading.Thread] = None

        self._on_idle_debate: Optional[Callable] = None
        self._on_idle_external: Optional[Callable] = None
        self._on_conflict: Optional[Callable] = None
        self._on_publish: Optional[Callable] = None

        self.tasks: List[EvolutionTask] = []

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._idle_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def record_activity(self) -> None:
        self._last_activity = time.time()

    def _idle_loop(self) -> None:
        while self._running:
            try:
                if self._is_idle():
                    self._trigger_idle_evolution()
                time.sleep(self._idle_check_interval)
            except Exception:
                pass

    def _is_idle(self) -> bool:
        return (time.time() - self._last_activity) >= (self.idle_minutes * 60)

    def trigger_idle_debate(self, topic: str,
                            context: Optional[Dict] = None) -> EvolutionTask:
        task = EvolutionTask(
            id=self._gen_id(), task_type="debate", trigger="idle",
            topic=topic)
        self._run_task(task, context)
        return task

    def trigger_conflict(self, original_belief: str,
                         user_correction: str,
                         context: Optional[Dict] = None) -> EvolutionTask:
        task = EvolutionTask(
            id=self._gen_id(), task_type="debate", trigger="conflict",
            topic=f"用户纠正: {original_belief[:50]}",
        )
        self._run_task(task, {
            **(context or {}),
            "original_belief": original_belief,
            "user_correction": user_correction,
        })
        return task

    def trigger_publish_check(self, content: str,
                               metadata: Optional[Dict] = None) -> EvolutionTask:
        task = EvolutionTask(
            id=self._gen_id(), task_type="safety", trigger="publish",
            topic="发布前安全审查",
        )
        safety = SafetyPipeline()
        result = safety.check(content, metadata)
        task.result_summary = ("通过" if result.passed else "拦截") + f", 等级: {result.level.value}"
        task.status = "completed"
        task.completed_at = datetime.now()
        if not result.passed:
            task.error_message = "; ".join(result.issues)
        self.tasks.append(task)
        return task

    def trigger_manual(self, task_type: str, topic: str,
                       context: Optional[Dict] = None) -> EvolutionTask:
        task = EvolutionTask(
            id=self._gen_id(), task_type=task_type, trigger="manual",
            topic=topic)
        self._run_task(task, context)
        return task

    def _run_task(self, task: EvolutionTask,
                  context: Optional[Dict]) -> None:
        task.status = "running"
        self.tasks.append(task)
        try:
            if task.task_type == "debate":
                self._execute_debate(task, context)
            elif task.task_type == "external":
                self._execute_external(task, context)
            elif task.task_type == "safety":
                self._execute_safety(task, context)
            else:
                task.status = "completed"
                task.result_summary = "等待人工审核"
        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
        task.completed_at = datetime.now()

    def _execute_debate(self, task: EvolutionTask,
                        context: Optional[Dict]) -> None:
        engine = DebateEngine()
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            record = loop.run_until_complete(engine.debate(
                topic=task.topic,
                topic_category=context.get("category", "general") if context else "general",
                context=context or {},
            ))
            loop.close()
            task.result_summary = f"辩论完成，结论: {record.final_conclusion[:100]}"
            task.status = "completed"
        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)

    def _execute_external(self, task: EvolutionTask,
                           context: Optional[Dict]) -> None:
        absorber = ExternalAbsorption()
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            insights = loop.run_until_complete(
                absorber.fetch_github_issues("microsoft/vscode", limit=5))
            loop.close()
            task.result_summary = f"抓取 {len(insights)} 条外部内容"
            task.status = "completed"
        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)

    def _execute_safety(self, task: EvolutionTask,
                         context: Optional[Dict]) -> None:
        content = context.get("content", "") if context else ""
        safety = SafetyPipeline()
        result = safety.check(content, context)
        task.result_summary = "通过" if result.passed else "拦截"
        task.status = "completed"

    def _trigger_idle_evolution(self) -> None:
        if self._on_idle_debate:
            topic = self._pick_idle_topic()
            if topic:
                try:
                    self._on_idle_debate(topic)
                except Exception:
                    pass
        if self._on_idle_external:
            try:
                self._on_idle_external()
            except Exception:
                pass

    def _pick_idle_topic(self) -> str:
        kb = KnowledgeBase()
        pending = kb.get_all(verdict=HumanVerdict.PENDING, limit=5)
        if pending:
            return f"重新审视: {pending[0].key}"
        return "AI 助手的最佳交互模式是什么？"

    @staticmethod
    def _gen_id() -> str:
        return f"evo_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    def get_recent_tasks(self, limit: int = 20) -> List[EvolutionTask]:
        return sorted(self.tasks, key=lambda t: t.created_at, reverse=True)[:limit]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_tasks": len(self.tasks),
            "running": sum(1 for t in self.tasks if t.status == "running"),
            "completed": sum(1 for t in self.tasks if t.status == "completed"),
            "failed": sum(1 for t in self.tasks if t.status == "failed"),
            "idle_minutes": self.idle_minutes,
            "seconds_since_activity": int(time.time() - self._last_activity),
        }


# ═══════════════════════════════════════════════════════════════════════
# 8. SelfUpgradeSystem — 统一调度器
# ═══════════════════════════════════════════════════════════════════════

class SelfUpgradeSystem:
    """智能体自我升级系统 — 统一调度入口"""

    def __init__(self, config: Optional[SystemConfig] = None,
                 model_func: Optional[Callable] = None):
        self.config = config or SystemConfig()
        self._model_func = model_func

        # 初始化组件（依赖注入）
        self._safety_pipeline = SafetyPipeline()
        self._debate_engine = DebateEngine(model_func=model_func)
        self._external_absorption = ExternalAbsorption(
            safety_check=self._safety_pipeline.check)
        self._knowledge_base = KnowledgeBase()
        self._human_reviewer = HumanReviewer(
            debate_engine=self._debate_engine,
            knowledge_base=self._knowledge_base,
            external_absorption=self._external_absorption,
        )
        self._scheduler = EvolutionScheduler(
            idle_minutes=config.idle_trigger_minutes)

        self._enabled = True

    # ── 组件访问 ──

    @property
    def debate(self) -> DebateEngine:
        return self._debate_engine

    @property
    def external(self) -> ExternalAbsorption:
        return self._external_absorption

    @property
    def safety(self) -> SafetyPipeline:
        return self._safety_pipeline

    @property
    def knowledge(self) -> KnowledgeBase:
        return self._knowledge_base

    @property
    def reviewer(self) -> HumanReviewer:
        return self._human_reviewer

    @property
    def scheduler(self) -> EvolutionScheduler:
        return self._scheduler

    # ── 生命周期 ──

    def is_enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        self._enabled = True
        self._scheduler.start()

    def disable(self) -> None:
        self._enabled = False
        self._scheduler.stop()

    # ── 辩论 ──

    async def run_debate(self, topic: str, category: str = "general",
                         context: Optional[Dict[str, Any]] = None) -> str:
        record = await self._debate_engine.debate(
            topic=topic, topic_category=category, context=context)
        return record.id

    def get_debate(self, debate_id: str) -> Optional[Dict[str, Any]]:
        return self._human_reviewer.get_debate_detail(debate_id)

    def list_debates(self, limit: int = 20) -> List[Dict[str, Any]]:
        records = self._debate_engine.list_records(limit=limit)
        return [self._human_reviewer._format_debate_summary(r) for r in records]

    def review_debate(self, debate_id: str, verdict: HumanVerdict,
                      conclusion: Optional[str] = None,
                      notes: str = "") -> bool:
        if verdict == HumanVerdict.APPROVED:
            return self._human_reviewer.approve_debate(debate_id, conclusion, notes)
        elif verdict == HumanVerdict.REVISED:
            if conclusion:
                return self._human_reviewer.revise_debate(debate_id, conclusion, notes)
            return False
        elif verdict == HumanVerdict.REJECTED:
            return self._human_reviewer.reject_debate(debate_id, notes)
        return False

    # ── 外部吸收 ──

    async def fetch_external(self, source: str = "github",
                              repo: str = "microsoft/vscode") -> int:
        if source == "github":
            contents = await self._external_absorption.fetch_github_issues(repo, limit=10)
            for content in contents:
                await self._external_absorption.absorb(
                    source=ExternalSource.GITHUB, content=content)
            return len(contents)
        return 0

    def get_pending_insights(self, limit: int = 20) -> List[Dict[str, Any]]:
        insights = self._human_reviewer.get_pending_insights(limit=limit)
        return [self._human_reviewer._format_insight_summary(i) for i in insights]

    def absorb_insight(self, insight_id: str, knowledge_key: str,
                       category: str = "external") -> bool:
        return self._human_reviewer.absorb_insight(insight_id, knowledge_key, category)

    # ── 安全审查 ──

    def check_safety(self, content: str,
                     metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        result = self._safety_pipeline.check(content, metadata)
        return {
            "passed": result.passed, "level": result.level.value,
            "issues": result.issues, "warnings": result.warnings,
        }

    def add_block_keyword(self, keyword: str, reason: str = "") -> None:
        self._safety_pipeline.add_to_block_list(keyword, reason)

    def add_warn_keyword(self, keyword: str, reason: str = "") -> None:
        self._safety_pipeline.add_to_warn_list(keyword, reason)

    # ── 知识库 ──

    def add_knowledge(self, category: str, key: str, value: str,
                      tags: Optional[List[str]] = None) -> bool:
        try:
            self._knowledge_base.add(
                category=category, key=key, value=value, tags=tags,
                human_verdict=HumanVerdict.APPROVED)
            return True
        except Exception:
            return False

    def get_knowledge(self, category: Optional[str] = None,
                      keyword: Optional[str] = None,
                      limit: int = 20) -> List[Dict[str, Any]]:
        if keyword:
            entries = self._knowledge_base.search(keyword, limit=limit)
        else:
            entries = self._knowledge_base.get_all(category=category, limit=limit)
        return [{
            "id": e.id, "category": e.category, "key": e.key,
            "value": e.value, "version": e.version,
            "verdict": e.human_verdict.value, "tags": e.tags,
            "updated_at": e.updated_at.strftime("%Y-%m-%d %H:%M"),
        } for e in entries]

    def update_knowledge_verdict(self, entry_id: str, verdict: HumanVerdict,
                                 new_value: Optional[str] = None) -> bool:
        return self._knowledge_base.update_verdict(entry_id, verdict, new_value)

    # ── 待审核 ──

    def get_pending_review(self) -> Dict[str, Any]:
        return self._human_reviewer.get_all_pending()

    # ── 统计 ──

    def get_full_stats(self) -> Dict[str, Any]:
        return {
            "system": {
                "enabled": self._enabled,
                "config": {
                    "idle_trigger_minutes": self.config.idle_trigger_minutes,
                    "auto_debate": self.config.auto_debate_enabled,
                    "auto_external": self.config.auto_external_enabled,
                },
            },
            "debates": {
                "total": len(self._debate_engine.list_records(limit=1000)),
                "pending": len(self._human_reviewer.get_pending_debates()),
            },
            "insights": self._external_absorption.get_stats(),
            "safety": self._safety_pipeline.get_stats(),
            "knowledge": self._knowledge_base.get_stats(),
            "scheduler": self._scheduler.get_stats(),
        }

    # ── 触发器 ──

    def trigger_conflict(self, original_belief: str,
                         user_correction: str,
                         context: Optional[Dict[str, Any]] = None) -> None:
        self._scheduler.trigger_conflict(original_belief, user_correction, context)

    def trigger_manual_debate(self, topic: str,
                               category: str = "general") -> None:
        self._scheduler.trigger_manual("debate", topic, {"category": category})

    def trigger_publish_check(self, content: str,
                               metadata: Optional[Dict[str, Any]] = None
                               ) -> EvolutionTask:
        return self._scheduler.trigger_publish_check(content, metadata)


# ═══════════════════════════════════════════════════════════════════════
# 9. 全局单例
# ═══════════════════════════════════════════════════════════════════════

_system: Optional[SelfUpgradeSystem] = None


def get_self_upgrade_system() -> SelfUpgradeSystem:
    global _system
    if _system is None:
        _system = SelfUpgradeSystem()
    return _system


# Convenience function for backward compatibility
def check_safety(content: str,
                 metadata: Optional[Dict[str, Any]] = None) -> SafetyCheckResult:
    """快捷安全审查（向后兼容 external_absorption）"""
    return get_self_upgrade_system().safety.check(content, metadata)


def create_self_upgrade_system(model_func: Optional[Callable] = None
                               ) -> SelfUpgradeSystem:
    """创建 SelfUpgradeSystem 实例"""
    return SelfUpgradeSystem(model_func=model_func)
