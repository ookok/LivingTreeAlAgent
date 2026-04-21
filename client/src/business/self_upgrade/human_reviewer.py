# human_reviewer.py — 思维审核室
# 展示辩论记录与外部吸收结论，人类可删除/改写/打标签

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple

from .models import (
    DebateRecord, ExternalInsight, KnowledgeEntry,
    HumanVerdict, DebateVerdict, ExternalSource
)


class HumanReviewer:
    """
    思维审核室

    功能：
    1. 展示辩论记录（供审核）
    2. 展示外部吸收洞察（待吸收）
    3. 人类操作：认可/修改/驳回
    4. 确认后同步到知识库
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path.home() / ".hermes-desktop" / "self_upgrade"
        self.reviews_dir = self.data_dir / "reviews"
        self.reviews_dir.mkdir(parents=True, exist_ok=True)

        # 缓存
        self._debate_engine = None
        self._knowledge_base = None
        self._external_absorption = None

    # ============================================================
    # 依赖注入
    # ============================================================

    @property
    def debate_engine(self):
        if self._debate_engine is None:
            from .debate_engine import get_debate_engine
            self._debate_engine = get_debate_engine()
        return self._debate_engine

    @property
    def knowledge_base(self):
        if self._knowledge_base is None:
            from .knowledge_base import get_knowledge_base
            self._knowledge_base = get_knowledge_base()
        return self._knowledge_base

    @property
    def external_absorption(self):
        if self._external_absorption is None:
            from .external_absorption import get_external_absorption
            self._external_absorption = get_external_absorption()
        return self._external_absorption

    # ============================================================
    # 待审核项
    # ============================================================

    def get_pending_debates(self, limit: int = 20) -> List[DebateRecord]:
        """获取待审核的辩论记录"""
        records = self.debate_engine.list_records(limit=limit)
        return [r for r in records if r.human_verdict == HumanVerdict.PENDING]

    def get_pending_insights(self, limit: int = 20) -> List[ExternalInsight]:
        """获取待审核的外部洞察"""
        return self.external_absorption.list_insights(absorbed=False, limit=limit)

    def get_all_pending(self) -> Dict[str, Any]:
        """获取所有待审核项"""
        pending_debates = self.get_pending_debates()
        pending_insights = self.get_pending_insights()

        return {
            "pending_debates": [
                self._format_debate_summary(r) for r in pending_debates
            ],
            "pending_insights": [
                self._format_insight_summary(i) for i in pending_insights
            ],
            "total_pending": len(pending_debates) + len(pending_insights),
        }

    # ============================================================
    # 审核操作
    # ============================================================

    def approve_debate(
        self,
        debate_id: str,
        conclusion: Optional[str] = None,
        notes: str = "",
    ) -> bool:
        """
        认可辩论结论

        Args:
            debate_id: 辩论ID
            conclusion: 可选的新结论（替换原有）
            notes: 审核备注
        """
        verdict = HumanVerdict.APPROVED
        record = self.debate_engine.load_record(debate_id)
        if not record:
            return False

        # 更新辩论记录
        self.debate_engine.update_human_verdict(
            debate_id, verdict, notes
        )

        # 同步到知识库
        final_conclusion = conclusion or record.final_conclusion
        self.knowledge_base.add(
            category=f"debate_{record.topic_category}",
            key=f"conclusion_{record.id}",
            value=final_conclusion,
            source_debate_id=debate_id,
            human_verdict=verdict,
            tags=[record.topic_category, "debate"],
        )

        return True

    def revise_debate(
        self,
        debate_id: str,
        new_conclusion: str,
        notes: str = "",
    ) -> bool:
        """
        修改辩论结论
        """
        verdict = HumanVerdict.REVISED
        record = self.debate_engine.load_record(debate_id)
        if not record:
            return False

        # 更新辩论记录
        self.debate_engine.update_human_verdict(debate_id, verdict, notes)

        # 同步到知识库
        self.knowledge_base.add(
            category=f"debate_{record.topic_category}",
            key=f"conclusion_{record.id}",
            value=new_conclusion,
            source_debate_id=debate_id,
            human_verdict=verdict,
            tags=[record.topic_category, "debate", "revised"],
        )

        return True

    def reject_debate(self, debate_id: str, reason: str = "") -> bool:
        """
        驳回辩论结论
        """
        verdict = HumanVerdict.REJECTED
        self.debate_engine.update_human_verdict(
            debate_id, verdict, reason
        )
        return True

    def absorb_insight(
        self,
        insight_id: str,
        knowledge_key: str,
        category: str = "external",
    ) -> bool:
        """
        吸收外部洞察到知识库
        """
        insight = self.external_absorption.load_insight(insight_id)
        if not insight:
            return False

        # 添加到知识库
        self.knowledge_base.add(
            category=category,
            key=knowledge_key,
            value=insight.content_summary,
            source_external_id=insight_id,
            human_verdict=HumanVerdict.APPROVED,
            tags=[insight.source.value, "external"],
        )

        # 标记为已吸收
        self.external_absorption.mark_absorbed(insight_id)
        return True

    def dismiss_insight(self, insight_id: str, reason: str = "") -> bool:
        """忽略外部洞察"""
        # 直接标记为已吸收但不入库
        return self.external_absorption.mark_absorbed(insight_id)

    # ============================================================
    # 格式化（供 UI 显示）
    # ============================================================

    def _format_debate_summary(self, record: DebateRecord) -> Dict[str, Any]:
        return {
            "id": record.id,
            "topic": record.topic,
            "category": record.topic_category,
            "verdict": record.verdict.value,
            "conclusion": record.final_conclusion,
            "conservative_count": len(record.conservative_args),
            "radical_count": len(record.radical_args),
            "contradictions": record.contradictions,
            "created_at": record.created_at.strftime("%Y-%m-%d %H:%M"),
            "needs_review": len(record.contradictions) > 0 or record.verdict == DebateVerdict.INCONCLUSIVE,
        }

    def _format_insight_summary(self, insight: ExternalInsight) -> Dict[str, Any]:
        return {
            "id": insight.id,
            "source": insight.source.value,
            "title": insight.source_title,
            "summary": insight.content_summary[:100] + "..." if len(insight.content_summary) > 100 else insight.content_summary,
            "key_points": insight.key_points[:3],
            "difference": insight.difference_flagged,
            "safety": insight.safety_level.value,
            "created_at": insight.created_at.strftime("%Y-%m-%d %H:%M"),
        }

    def get_debate_detail(self, debate_id: str) -> Optional[Dict[str, Any]]:
        """获取辩论详情"""
        record = self.debate_engine.load_record(debate_id)
        if not record:
            return None

        return {
            "id": record.id,
            "topic": record.topic,
            "category": record.topic_category,
            "verdict": record.verdict.value,
            "human_verdict": record.human_verdict.value,
            "human_notes": record.human_notes,
            "conclusion": record.final_conclusion,
            "contradictions": record.contradictions,
            "conservative_args": [
                {
                    "论点": a.论点,
                    "论据": a.论据,
                    "反驳": a.反驳,
                    "confidence": a.confidence,
                } for a in record.conservative_args
            ],
            "radical_args": [
                {
                    "论点": a.论点,
                    "论据": a.论据,
                    "反驳": a.反驳,
                    "confidence": a.confidence,
                } for a in record.radical_args
            ],
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
        }

    # ============================================================
    # 统计
    # ============================================================

    def get_review_stats(self) -> Dict[str, Any]:
        """获取审核统计"""
        records = self.debate_engine.list_records(limit=1000)
        insights = self.external_absorption.list_insights(limit=1000)

        pending_debates = [r for r in records if r.human_verdict == HumanVerdict.PENDING]
        approved_debates = [r for r in records if r.human_verdict == HumanVerdict.APPROVED]
        rejected_debates = [r for r in records if r.human_verdict == HumanVerdict.REJECTED]

        return {
            "debates": {
                "total": len(records),
                "pending": len(pending_debates),
                "approved": len(approved_debates),
                "rejected": len(rejected_debates),
            },
            "insights": {
                "total": len(insights),
                "absorbed": sum(1 for i in insights if i.absorbed),
                "pending": sum(1 for i in insights if not i.absorbed),
            },
            "knowledge": self.knowledge_base.get_stats(),
        }


# 全局单例
_human_reviewer: Optional[HumanReviewer] = None


def get_human_reviewer() -> HumanReviewer:
    global _human_reviewer
    if _human_reviewer is None:
        _human_reviewer = HumanReviewer()
    return _human_reviewer
