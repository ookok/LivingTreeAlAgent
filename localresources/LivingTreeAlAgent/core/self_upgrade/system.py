# system.py — 自我升级系统统一调度器

import asyncio
from typing import Optional, Dict, Any, List
from pathlib import Path

from .models import SystemConfig, EvolutionTask, HumanVerdict
from .debate_engine import DebateEngine, get_debate_engine
from .external_absorption import ExternalAbsorption, get_external_absorption
from .safety_pipeline import SafetyPipeline, get_safety_pipeline
from .knowledge_base import KnowledgeBase, get_knowledge_base
from .human_reviewer import HumanReviewer, get_human_reviewer
from .evolution_scheduler import EvolutionScheduler, get_evolution_scheduler


class SelfUpgradeSystem:
    """
    智能体自我升级系统 — 统一调度器

    整合四大引擎：
    1. 本地左右互搏 (DebateEngine)
    2. 外部营养吸收 (ExternalAbsorption)
    3. 安全审查管道 (SafetyPipeline)
    4. 人类修正回路 (HumanReviewer)

    提供统一入口，协调各组件工作
    """

    def __init__(self, config: Optional[SystemConfig] = None):
        self.config = config or SystemConfig()
        self.data_dir = Path.home() / ".hermes-desktop" / "self_upgrade"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 组件
        self._debate_engine: Optional[DebateEngine] = None
        self._external_absorption: Optional[ExternalAbsorption] = None
        self._safety_pipeline: Optional[SafetyPipeline] = None
        self._knowledge_base: Optional[KnowledgeBase] = None
        self._human_reviewer: Optional[HumanReviewer] = None
        self._scheduler: Optional[EvolutionScheduler] = None

        # 状态
        self._enabled = True
        self._initialized = False

    # ============================================================
    # 组件访问
    # ============================================================

    @property
    def debate(self) -> DebateEngine:
        if self._debate_engine is None:
            self._debate_engine = get_debate_engine()
        return self._debate_engine

    @property
    def external(self) -> ExternalAbsorption:
        if self._external_absorption is None:
            self._external_absorption = get_external_absorption()
        return self._external_absorption

    @property
    def safety(self) -> SafetyPipeline:
        if self._safety_pipeline is None:
            self._safety_pipeline = get_safety_pipeline()
        return self._safety_pipeline

    @property
    def knowledge(self) -> KnowledgeBase:
        if self._knowledge_base is None:
            self._knowledge_base = get_knowledge_base()
        return self._knowledge_base

    @property
    def reviewer(self) -> HumanReviewer:
        if self._human_reviewer is None:
            self._human_reviewer = get_human_reviewer()
        return self._human_reviewer

    @property
    def scheduler(self) -> EvolutionScheduler:
        if self._scheduler is None:
            self._scheduler = get_evolution_scheduler()
        return self._scheduler

    # ============================================================
    # 核心 API
    # ============================================================

    def is_enabled(self) -> bool:
        """系统是否启用"""
        return self._enabled

    def enable(self):
        """启用系统"""
        self._enabled = True
        self.scheduler.start()
        print("[SelfUpgradeSystem] Enabled")

    def disable(self):
        """禁用系统"""
        self._enabled = False
        self.scheduler.stop()
        print("[SelfUpgradeSystem] Disabled")

    # --------------------------------------------------------
    # 辩论相关
    # --------------------------------------------------------

    async def run_debate(
        self,
        topic: str,
        category: str = "general",
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        运行辩论并返回辩论ID

        Returns:
            debate_id: 辩论记录ID
        """
        record = await self.debate.debate(
            topic=topic,
            topic_category=category,
            context=context,
        )
        return record.id

    def get_debate(self, debate_id: str) -> Optional[Dict[str, Any]]:
        """获取辩论详情"""
        return self.reviewer.get_debate_detail(debate_id)

    def list_debates(self, limit: int = 20) -> List[Dict[str, Any]]:
        """列出辩论记录"""
        records = self.debate.list_records(limit=limit)
        return [self.reviewer._format_debate_summary(r) for r in records]

    def review_debate(
        self,
        debate_id: str,
        verdict: HumanVerdict,
        conclusion: Optional[str] = None,
        notes: str = "",
    ) -> bool:
        """审核辩论"""
        if verdict == HumanVerdict.APPROVED:
            return self.reviewer.approve_debate(debate_id, conclusion, notes)
        elif verdict == HumanVerdict.REVISED:
            if conclusion:
                return self.reviewer.revise_debate(debate_id, conclusion, notes)
            return False
        elif verdict == HumanVerdict.REJECTED:
            return self.reviewer.reject_debate(debate_id, notes)
        return False

    # --------------------------------------------------------
    # 外部吸收相关
    # --------------------------------------------------------

    async def fetch_external(
        self,
        source: str = "github",
        repo: str = "microsoft/vscode",
    ) -> int:
        """
        抓取外部内容

        Returns:
            抓取数量
        """
        if source == "github":
            contents = await self.external.fetch_github_issues(repo, limit=10)
            for content in contents:
                await self.external.absorb(
                    source=self.external.__class__.__name__,
                    content=content,
                )
            return len(contents)
        return 0

    def get_pending_insights(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取待吸收洞察"""
        insights = self.reviewer.get_pending_insights(limit=limit)
        return [self.reviewer._format_insight_summary(i) for i in insights]

    def absorb_insight(
        self,
        insight_id: str,
        knowledge_key: str,
        category: str = "external",
    ) -> bool:
        """吸收洞察到知识库"""
        return self.reviewer.absorb_insight(insight_id, knowledge_key, category)

    # --------------------------------------------------------
    # 安全审查
    # --------------------------------------------------------

    def check_safety(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """安全审查内容"""
        result = self.safety.check(content, metadata)
        return {
            "passed": result.passed,
            "level": result.level.value,
            "issues": result.issues,
            "warnings": result.warnings,
        }

    def add_block_keyword(self, keyword: str, reason: str = ""):
        """添加拦截关键词"""
        self.safety.add_to_block_list(keyword, reason)

    def add_warn_keyword(self, keyword: str, reason: str = ""):
        """添加警告关键词"""
        self.safety.add_to_warn_list(keyword, reason)

    # --------------------------------------------------------
    # 知识库
    # --------------------------------------------------------

    def add_knowledge(
        self,
        category: str,
        key: str,
        value: str,
        tags: Optional[List[str]] = None,
    ) -> bool:
        """直接添加知识"""
        try:
            self.knowledge.add(
                category=category,
                key=key,
                value=value,
                tags=tags,
                human_verdict=HumanVerdict.APPROVED,
            )
            return True
        except:
            return False

    def get_knowledge(
        self,
        category: Optional[str] = None,
        keyword: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """查询知识"""
        if keyword:
            entries = self.knowledge.search(keyword, limit=limit)
        else:
            entries = self.knowledge.get_all(category=category, limit=limit)

        return [
            {
                "id": e.id,
                "category": e.category,
                "key": e.key,
                "value": e.value,
                "version": e.version,
                "verdict": e.human_verdict.value,
                "tags": e.tags,
                "updated_at": e.updated_at.strftime("%Y-%m-%d %H:%M"),
            }
            for e in entries
        ]

    def update_knowledge_verdict(
        self,
        entry_id: str,
        verdict: HumanVerdict,
        new_value: Optional[str] = None,
    ) -> bool:
        """更新知识裁决"""
        return self.knowledge.update_verdict(entry_id, verdict, new_value)

    # --------------------------------------------------------
    # 待审核项
    # --------------------------------------------------------

    def get_pending_review(self) -> Dict[str, Any]:
        """获取所有待审核项"""
        return self.reviewer.get_all_pending()

    # --------------------------------------------------------
    # 统计
    # --------------------------------------------------------

    def get_full_stats(self) -> Dict[str, Any]:
        """获取完整统计"""
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
                "total": len(self.debate.list_records(limit=1000)),
                "pending": len(self.reviewer.get_pending_debates()),
            },
            "insights": self.external.get_stats(),
            "safety": self.safety.get_stats(),
            "knowledge": self.knowledge.get_stats(),
            "scheduler": self.scheduler.get_stats(),
        }

    # --------------------------------------------------------
    # 触发器
    # --------------------------------------------------------

    def trigger_conflict(
        self,
        original_belief: str,
        user_correction: str,
        context: Optional[Dict[str, Any]] = None,
    ):
        """触发冲突辩论"""
        self.scheduler.trigger_conflict(original_belief, user_correction, context)

    def trigger_manual_debate(
        self,
        topic: str,
        category: str = "general",
    ):
        """手动触发辩论"""
        self.scheduler.trigger_manual("debate", topic, {"category": category})

    def trigger_publish_check(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EvolutionTask:
        """触发发布前检查"""
        return self.scheduler.trigger_publish_check(content, metadata)


# 全局单例
_system: Optional[SelfUpgradeSystem] = None


def get_self_upgrade_system() -> SelfUpgradeSystem:
    global _system
    if _system is None:
        _system = SelfUpgradeSystem()
    return _system
