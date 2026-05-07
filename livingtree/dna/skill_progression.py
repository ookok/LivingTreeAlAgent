"""SkillProgression — 系统技能成长追踪与进步度量.

人类专家的标志性特征：随着经验积累，能力持续提升。
  - 新手: 不确定选什么模型，常出错
  - 熟练: 知道何时用AERSCREEN vs ADMS，错误减少
  - 专家: 能预见问题，给出高质量建议

本模块量化这个成长过程，按技能维度追踪进步曲线：
  1. 技能维度定义: regulatory_compliance, data_analysis, model_selection, ...
  2. 进步指标: 成功率趋势、置信度校准、决策速度、错误类型分布
  3. 里程碑检测: 何时达到"熟练"、"专家"水平
  4. 跨项目对比: "这个项目比之前类似项目做得好吗？"

数据源:
  - FitnessLandscape: 执行轨迹成功率
  - ReasoningChain: 决策验证率
  - MetaMemory: 策略有效性
  - EvolutionStore: 教训数量与质量

Usage:
    prog = get_skill_progression()
    prog.record_outcome(skill="regulatory_compliance", success=True, session="proj_001")
    level = prog.skill_level("regulatory_compliance")  # "proficient"
    report = prog.progress_report()  # 成长报告
"""

from __future__ import annotations

import json
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

PROG_DIR = Path(".livingtree/meta")
PROG_FILE = PROG_DIR / "skill_progression.json"


# ═══════════════════════════════════════════════════════════════════
# Types
# ═══════════════════════════════════════════════════════════════════

@dataclass
class SkillMetric:
    """单个技能的度量."""
    skill: str
    total_attempts: int = 0
    successes: int = 0
    recent_successes: int = 0       # 最近10次
    recent_attempts: int = 0
    avg_confidence: float = 0.5
    avg_latency_ms: float = 0.0
    first_session: str = ""
    last_session: str = ""
    mistake_types: dict[str, int] = field(default_factory=dict)  # {错误类型: 次数}

    @property
    def success_rate(self) -> float:
        return self.successes / max(self.total_attempts, 1)

    @property
    def recent_rate(self) -> float:
        return self.recent_successes / max(self.recent_attempts, 1)

    @property
    def trend(self) -> float:
        """进步趋势: 正值 = 在变好, 负值 = 在变差."""
        if self.recent_attempts < 3:
            return 0.0
        return round(self.recent_rate - self.success_rate, 3)

    @property
    def level(self) -> str:
        """技能水平."""
        if self.total_attempts < 3:
            return "novice"
        rate = self.recent_rate
        if rate >= 0.9 and self.total_attempts >= 10:
            return "expert"
        if rate >= 0.75 and self.total_attempts >= 5:
            return "proficient"
        if rate >= 0.5:
            return "competent"
        return "novice"


@dataclass
class Milestone:
    """技能成长里程碑."""
    skill: str
    level: str
    achieved_at: float
    session: str = ""
    attempts_at_achievement: int = 0


@dataclass
class ProgressReport:
    """完整技能成长报告."""
    skills: dict[str, SkillMetric] = field(default_factory=dict)
    milestones: list[Milestone] = field(default_factory=list)
    total_sessions: int = 0
    overall_trend: float = 0.0        # 整体进步趋势
    strongest_skill: str = ""
    weakest_skill: str = ""
    generated_at: float = field(default_factory=time.time)

    @property
    def summary(self) -> str:
        lines = ["# 技能成长报告", ""]
        for skill, metric in self.skills.items():
            trend_icon = "📈" if metric.trend > 0.05 else ("📉" if metric.trend < -0.05 else "➡️")
            lines.append(
                f"- **{skill}**: {metric.level.upper()} "
                f"(成功率 {metric.recent_rate:.0%}, "
                f"趋势 {trend_icon} {metric.trend:+.0%}, "
                f"{metric.total_attempts}次)")
        if self.milestones:
            lines.append("")
            lines.append("## 里程碑")
            for m in self.milestones[-5:]:
                lines.append(f"- {m.skill}: 达到 **{m.level}** (第{m.attempts_at_achievement}次)")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# Skill Definitions
# ═══════════════════════════════════════════════════════════════════

SKILL_DEFINITIONS: dict[str, str] = {
    "regulatory_compliance": "法规合规 — 正确引用GB标准、识别合规缺口",
    "data_analysis": "数据分析 — 正确解读监测数据、发现异常值",
    "model_selection": "模型选择 — 选择合适的环境扩散模型",
    "document_generation": "文档生成 — 结构完整、格式规范的报告输出",
    "code_engineering": "代码工程 — 正确实现功能、低bug率",
    "retrieval_accuracy": "检索精度 — 找到正确知识的能力",
    "reasoning_quality": "推理质量 — 逻辑连贯、结论有据",
    "cost_efficiency": "成本效率 — 完成任务的最优token使用",
}


# ═══════════════════════════════════════════════════════════════════
# SkillProgression Engine
# ═══════════════════════════════════════════════════════════════════

class SkillProgression:
    """技能成长追踪——量化系统在各维度上的进步."""

    WINDOW_SIZE = 10  # 最近N次用于计算趋势

    def __init__(self):
        self._skills: dict[str, SkillMetric] = {}
        self._milestones: list[Milestone] = []
        self._history: list[dict] = []  # [{skill, success, confidence, latency_ms, session, mistake_type}]
        self._session_count = 0
        self._load()

    # ═══ Record ═══

    def record_outcome(
        self, skill: str, success: bool, confidence: float = 0.5,
        latency_ms: float = 0.0, session: str = "",
        mistake_type: str = "",
    ) -> None:
        """记录一次技能执行的结果.

        Args:
            skill: 技能名称
            success: 是否成功
            confidence: 当时的确信度
            latency_ms: 耗时
            session: 关联会话
            mistake_type: 如果失败，错误类型
        """
        if skill not in self._skills:
            self._skills[skill] = SkillMetric(skill=skill)

        metric = self._skills[skill]
        old_level = metric.level

        metric.total_attempts += 1
        if success:
            metric.successes += 1
        metric.avg_confidence = round(
            (metric.avg_confidence * (metric.total_attempts - 1) + confidence) / metric.total_attempts, 3)
        metric.avg_latency_ms = round(
            (metric.avg_latency_ms * (metric.total_attempts - 1) + latency_ms) / metric.total_attempts, 1)
        if not metric.first_session:
            metric.first_session = session
        metric.last_session = session

        if mistake_type:
            metric.mistake_types[mistake_type] = metric.mistake_types.get(mistake_type, 0) + 1

        # 更新最近窗口
        self._history.append({
            "skill": skill, "success": success, "confidence": confidence,
            "latency_ms": latency_ms, "session": session,
            "mistake_type": mistake_type, "timestamp": time.time(),
        })
        recent = [h for h in self._history[-self.WINDOW_SIZE:] if h["skill"] == skill]
        metric.recent_attempts = len(recent)
        metric.recent_successes = sum(1 for h in recent if h["success"])

        if session:
            self._session_count = max(self._session_count,
                                       len(set(h["session"] for h in self._history)))

        # 里程碑检测
        new_level = metric.level
        if new_level != old_level and new_level in ("proficient", "expert"):
            milestone = Milestone(
                skill=skill, level=new_level,
                achieved_at=time.time(), session=session,
                attempts_at_achievement=metric.total_attempts,
            )
            self._milestones.append(milestone)
            logger.info(f"🎯 SkillProgression: {skill} → {new_level.upper()}! ({metric.total_attempts} attempts)")

        self._save()

    # ═══ Query ═══

    def skill_level(self, skill: str) -> str:
        metric = self._skills.get(skill)
        return metric.level if metric else "unknown"

    def progress_report(self) -> ProgressReport:
        """生成完整技能成长报告."""
        if not self._skills:
            return ProgressReport()

        # 查找最强/最弱技能
        best = max(self._skills.values(), key=lambda m: m.recent_rate)
        worst = min(self._skills.values(), key=lambda m: m.recent_rate)

        # 整体趋势
        trends = [m.trend for m in self._skills.values() if m.recent_attempts >= 3]
        overall = round(sum(trends) / max(len(trends), 1), 3)

        return ProgressReport(
            skills=self._skills,
            milestones=self._milestones,
            total_sessions=self._session_count,
            overall_trend=overall,
            strongest_skill=best.skill,
            weakest_skill=worst.skill,
        )

    def improvement_rate(self, skill: str) -> float:
        """某技能的进步速率（每10次提升多少成功率）."""
        metric = self._skills.get(skill)
        if not metric or metric.total_attempts < 10:
            return 0.0
        return round(metric.trend / max(metric.total_attempts / 10, 1), 3)

    def calibration_error(self, skill: str) -> float:
        """置信度校准误差——agent的高置信度预测是否真的准确."""
        relevant = [h for h in self._history if h["skill"] == skill]
        if len(relevant) < 5:
            return 0.0

        high_conf = [h for h in relevant if h["confidence"] > 0.8]
        if not high_conf:
            return 0.0
        actual = sum(1 for h in high_conf if h["success"]) / len(high_conf)
        return round(abs(0.85 - actual), 3)  # 期望高置信度时成功率≥85%

    def expertise_score(self) -> float:
        """综合专家评分 (0-100)."""
        if not self._skills:
            return 0.0

        weights = {
            "novice": 0.2, "competent": 0.5,
            "proficient": 0.75, "expert": 0.95,
        }
        total_weight = 0.0
        weighted_sum = 0.0

        for skill, metric in self._skills.items():
            w = metric.total_attempts  # 经验越多权重越大
            weighted_sum += weights.get(metric.level, 0.3) * w
            total_weight += w

        if total_weight == 0:
            return 0.0
        return round(weighted_sum / total_weight * 100, 1)

    def recommend_focus(self) -> list[str]:
        """建议集中提升的技能."""
        suggestions = []
        for skill, metric in self._skills.items():
            if metric.trend < -0.05:
                suggestions.append(f"⚠ {skill}: 趋势下降 {metric.trend:+.1%}，需关注")
            elif metric.level == "novice" and metric.total_attempts >= 5:
                suggestions.append(f"📚 {skill}: 新手水平 ({metric.total_attempts}次)，需加强训练")

        # 校准问题
        for skill in self._skills:
            cal = self.calibration_error(skill)
            if cal > 0.3:
                suggestions.append(
                    f"🎯 {skill}: 置信度校准误差 {cal:.1%}，过于自信或不够自信")

        return suggestions

    # ═══ Persistence ═══

    def _save(self):
        try:
            PROG_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                "skills": {
                    s: {
                        "skill": m.skill, "total_attempts": m.total_attempts,
                        "successes": m.successes, "avg_confidence": m.avg_confidence,
                        "avg_latency_ms": m.avg_latency_ms,
                        "first_session": m.first_session, "last_session": m.last_session,
                        "mistake_types": m.mistake_types,
                    }
                    for s, m in self._skills.items()
                },
                "milestones": [
                    {"skill": m.skill, "level": m.level, "achieved_at": m.achieved_at,
                     "session": m.session, "attempts_at_achievement": m.attempts_at_achievement}
                    for m in self._milestones
                ],
                "session_count": self._session_count,
            }
            PROG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.debug(f"SkillProgression save: {e}")

    def _load(self):
        try:
            if not PROG_FILE.exists():
                return
            data = json.loads(PROG_FILE.read_text())
            for s, md in data.get("skills", {}).items():
                self._skills[s] = SkillMetric(**md)
            for md in data.get("milestones", []):
                self._milestones.append(Milestone(**md))
            self._session_count = data.get("session_count", 0)
            logger.info(f"SkillProgression: loaded {len(self._skills)} skills, "
                        f"{len(self._milestones)} milestones")
        except Exception as e:
            logger.debug(f"SkillProgression load: {e}")

    def stats(self) -> dict[str, Any]:
        return {
            "skills_tracked": len(self._skills),
            "total_sessions": self._session_count,
            "milestones": len(self._milestones),
            "expertise_score": self.expertise_score(),
            "strongest": self.progress_report().strongest_skill,
            "weakest": self.progress_report().weakest_skill,
        }


# ── Singleton ──────────────────────────────────────────────────────

_skill_progression: SkillProgression | None = None


def get_skill_progression() -> SkillProgression:
    global _skill_progression
    if _skill_progression is None:
        _skill_progression = SkillProgression()
    return _skill_progression
