"""Economic Engine — 成本-速度-质量三元悖论经济范式.

将经济理性植入 Agent 的每个决策环节：

  1. TrilemmaVector — 量化任务在成本/速度/质量三个维度的表现
  2. EconomicPolicy — 可配置的三元权重 + 硬约束（最大预算、最低质量）
  3. ROIModel — 投入产出比计算：task_value / estimated_cost
  4. ComplianceGate — 合法合规审查（敏感数据、法规红线、环评合规）
  5. EconomicOrchestrator — 经济决策编排器：评估→决策→追踪→优化

核心公式：
  ROI = TaskValue / TotalCost
  Score = w_cost × cost_score + w_speed × speed_score + w_quality × quality_score
  Go/NoGo = Score > min_score AND ComplianceCheck.passed AND Cost < Budget

集成点:
  - TreeLLM 路由: economic_policy.select_model(task_complexity)
  - LifeEngine 执前: orchestrator.evaluate(task) → Go/NoGo/Replan
  - CostAware 扩展: 接入 EconomicPolicy 的预算分配
  - FitnessLandscape: economic_score 作为 Pareto 新维度

定价数据源: DeepSeek API 2026-05 优惠价
  Pro:   input ¥3/M output ¥6/M
  Flash: input ¥1/M output ¥2/M
"""

from __future__ import annotations

import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from loguru import logger


# ═══════════════════════════════════════════════════════════════════
# Trilemma Vector — 三元评分
# ═══════════════════════════════════════════════════════════════════

@dataclass
class TrilemmaVector:
    """任务在成本-速度-质量三个维度的归一化评分 (0-1, 越高越好).

    cost_score:   成本越低→评分越高 (1.0 = 零成本)
    speed_score:  速度越快→评分越高 (1.0 = 即时响应)
    quality_score: 质量越高→评分越高 (1.0 = 完美输出)
    """
    cost_score: float = 0.5
    speed_score: float = 0.5
    quality_score: float = 0.5

    def as_tuple(self) -> tuple[float, float, float]:
        return (self.cost_score, self.speed_score, self.quality_score)

    def weighted_score(self, weights: EconomicPolicy | None = None) -> float:
        """加权综合评分。默认均衡权重。"""
        if weights is None:
            w = (0.33, 0.33, 0.34)
        else:
            w = (weights.cost_weight, weights.speed_weight, weights.quality_weight)
        return round(
            self.cost_score * w[0] + self.speed_score * w[1] + self.quality_score * w[2], 4)

    def dominates(self, other: TrilemmaVector) -> bool:
        """Pareto 支配关系: self 在所有维度 ≥ other 且至少一维严格 > """
        a = self.as_tuple()
        b = other.as_tuple()
        return all(ai >= bi for ai, bi in zip(a, b)) and any(ai > bi for ai, bi in zip(a, b))

    @classmethod
    def from_raw(
        cls,
        estimated_cost_yuan: float,
        estimated_ms: float,
        predicted_quality: float,
        budget_yuan: float = 20.0,
        timeout_ms: float = 120_000.0,
    ) -> TrilemmaVector:
        """从原始估算值计算三元向量.

        Args:
            estimated_cost_yuan: 预估花费（元）
            estimated_ms: 预估耗时（毫秒）
            predicted_quality: 预判质量（0-1，来自 PlanValidator）
            budget_yuan: 预算上限，用于归一化
            timeout_ms: 超时阈值，用于归一化
        """
        cost_score = max(0.0, 1.0 - estimated_cost_yuan / max(budget_yuan, 0.01))
        speed_score = max(0.0, 1.0 - estimated_ms / max(timeout_ms, 1))
        quality_score = max(0.0, min(1.0, predicted_quality))
        return cls(
            cost_score=round(cost_score, 3),
            speed_score=round(speed_score, 3),
            quality_score=round(quality_score, 3),
        )


# ═══════════════════════════════════════════════════════════════════
# Economic Policy — 经济策略配置
# ═══════════════════════════════════════════════════════════════════

class ComplianceLevel(str, Enum):
    STRICT = "strict"
    NORMAL = "normal"
    PERMISSIVE = "permissive"


@dataclass
class EconomicPolicy:
    """可配置的经济策略——控制三元悖论的权衡偏好.

    属性:
        cost_weight:   成本权重 (0-1)
        speed_weight:  速度权重 (0-1)
        quality_weight: 质量权重 (0-1)
        min_score:     最低综合评分阈值（低于此不执行）
        max_daily_budget_yuan: 每日预算上限（元）
        max_task_budget_yuan:  单任务预算上限（元）
        min_quality_threshold: 最低质量阈值（低于此拒绝执行）
        compliance_level:      合规审查级别
        degradation_enabled:   是否启用自动降级（Pro→Flash）
        roi_threshold:         最低 ROI 阈值（低于此不执行）

    预设策略:
        ECONOMY:   成本优先 (0.60/0.15/0.25) — 日常任务
        BALANCED:  均衡模式 (0.33/0.33/0.34) — 默认
        QUALITY:   质量优先 (0.15/0.15/0.70) — 关键产出
        SPEED:     速度优先 (0.15/0.70/0.15) — 交互会话
    """
    cost_weight: float = 0.33
    speed_weight: float = 0.33
    quality_weight: float = 0.34
    min_score: float = 0.3
    max_daily_budget_yuan: float = 50.0
    max_task_budget_yuan: float = 10.0
    min_quality_threshold: float = 0.4
    compliance_level: ComplianceLevel = ComplianceLevel.NORMAL
    degradation_enabled: bool = True
    roi_threshold: float = 0.5

    def __post_init__(self):
        total = self.cost_weight + self.speed_weight + self.quality_weight
        if abs(total - 1.0) > 0.001:
            # Auto-normalize
            self.cost_weight /= total
            self.speed_weight /= total
            self.quality_weight /= total

    @classmethod
    def economy(cls) -> EconomicPolicy:
        """成本优先策略——日常批处理、低优先级任务."""
        return cls(
            cost_weight=0.60, speed_weight=0.15, quality_weight=0.25,
            min_score=0.25, max_daily_budget_yuan=20.0, max_task_budget_yuan=3.0,
            min_quality_threshold=0.35, roi_threshold=0.3,
        )

    @classmethod
    def balanced(cls) -> EconomicPolicy:
        """均衡策略——默认模式."""
        return cls(
            cost_weight=0.33, speed_weight=0.33, quality_weight=0.34,
            min_score=0.3, max_daily_budget_yuan=50.0, max_task_budget_yuan=10.0,
            min_quality_threshold=0.4, roi_threshold=0.5,
        )

    @classmethod
    def quality(cls) -> EconomicPolicy:
        """质量优先策略——环评报告、法律文书等关键产出."""
        return cls(
            cost_weight=0.15, speed_weight=0.15, quality_weight=0.70,
            min_score=0.4, max_daily_budget_yuan=100.0, max_task_budget_yuan=30.0,
            min_quality_threshold=0.7, roi_threshold=0.4,
        )

    @classmethod
    def speed(cls) -> EconomicPolicy:
        """速度优先策略——实时交互、用户等待."""
        return cls(
            cost_weight=0.15, speed_weight=0.70, quality_weight=0.15,
            min_score=0.2, max_daily_budget_yuan=30.0, max_task_budget_yuan=5.0,
            min_quality_threshold=0.3, roi_threshold=0.3,
        )

    def select_model(self, task_complexity: float = 0.5,
                     preferred_provider: str = "auto",
                     requirements: dict | None = None) -> str:
        """根据策略、任务复杂度和能力需求选择模型.

        Args:
            task_complexity: 0-1，任务复杂度
            preferred_provider: "auto"|"deepseek"|"qwen"|"openai"|...
            requirements: 可选的能力需求 dict:
                reasoning: bool, tool_call: bool, structured_output: bool,
                attachment: bool, min_context: int,
                max_input_cost_cny: float, modalities_input: list[str]

        Returns:
            模型 ID 字符串
        """
        requirements = requirements or {}

        # ── models.dev capability selection removed (module deleted) ──

        # ── Static routing (fallback) ──
        # Quality-heavy + high complexity → top reasoning model
        if self.quality_weight > 0.5 and task_complexity > 0.5:
            if preferred_provider == "qwen":
                return "qwen/qwen3.6-plus"
            if preferred_provider == "deepseek":
                return "deepseek/deepseek-v4-pro"
            return "qwen/qwen3.6-plus"

        # Cost-heavy or low complexity → cheapest flash
        if self.cost_weight > 0.5 or task_complexity < 0.3:
            if preferred_provider == "qwen":
                return "qwen/qwen3.6-flash"
            if preferred_provider == "deepseek":
                return "deepseek/deepseek-v4-flash"
            return "qwen/qwen3.6-flash"

        # Speed-heavy → fastest flash
        if self.speed_weight > 0.5:
            if preferred_provider == "deepseek":
                return "deepseek/deepseek-v4-flash"
            return "qwen/qwen3.6-flash"

        # Default: complexity-based routing
        if task_complexity > 0.6:
            if preferred_provider == "qwen":
                return "qwen/qwen3.6-plus"
            return "deepseek/deepseek-v4-pro"
        if preferred_provider == "qwen":
            return "qwen/qwen3.6-flash"
        return "deepseek/deepseek-v4-flash"

    def to_dict(self) -> dict[str, Any]:
        return {
            "cost_weight": self.cost_weight,
            "speed_weight": self.speed_weight,
            "quality_weight": self.quality_weight,
            "min_score": self.min_score,
            "max_daily_budget_yuan": self.max_daily_budget_yuan,
            "max_task_budget_yuan": self.max_task_budget_yuan,
            "min_quality_threshold": self.min_quality_threshold,
            "compliance_level": self.compliance_level.value,
            "degradation_enabled": self.degradation_enabled,
            "roi_threshold": self.roi_threshold,
        }


# ═══════════════════════════════════════════════════════════════════
# ROI Model — 投入产出比
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ROIResult:
    """投入产出比计算结果."""
    task_id: str = ""
    task_value: float = 1.0       # 任务创造的经济价值（归一化）
    estimated_cost_yuan: float = 0.0  # 预估成本（元）
    actual_cost_yuan: float = 0.0     # 实际成本（元）
    roi_estimate: float = 0.0     # 预估 ROI
    roi_actual: float = 0.0       # 实际 ROI
    trilemma: TrilemmaVector = field(default_factory=TrilemmaVector)
    score: float = 0.0            # 综合经济评分
    approved: bool = False        # 是否通过经济审查
    reason: str = ""


class ROIModel:
    """投入产出比模型——量化"这个任务值得做吗？"

    任务价值估算基于:
      - 任务类型（代码生成 > 文档润色 > 闲聊）
      - 任务复杂度（越复杂价值越高）
      - 用户优先级（紧急任务价值更高）
      - 历史相似任务的 ROI

    成本估算基于:
      - 预估 token 消耗 × 模型单价
      - 历史相似任务的实际成本
    """

    # 任务类型基准价值（归一化）
    TASK_VALUE_BASE: dict[str, float] = {
        "code_generation": 3.0,       # 生成代码: 直接创造生产力
        "code_review": 2.0,           # 代码审查: 避免 bug 成本
        "document_generation": 2.5,   # 文档生成: 节省人力
        "data_analysis": 2.0,         # 数据分析: 决策支持
        "environmental_report": 5.0,  # 环评报告: 高合规价值
        "bug_fix": 2.5,               # 修复 bug: 避免损失
        "research": 1.5,              # 研究: 知识积累
        "question": 0.5,              # 问答: 低价值
        "chat": 0.2,                  # 闲聊: 最低价值
        "general": 1.0,               # 通用: 基准
    }

    # LLM 定价 (CNY/1M tokens)
    MODEL_PRICE_INPUT: dict[str, float] = {
        "deepseek/deepseek-v4-pro": 3.0,
        "deepseek/deepseek-v4-flash": 1.0,
        # ═══ SenseTime (商汤) — 限时免费 ═══
        "sensetime/SenseChat-Turbo": 0.0,
        "sensetime/SenseChat-Pro": 0.0,
        # ═══ Qwen (千问) — USD→CNY @7.25 ═══
        "qwen/qwen3.6-plus": 2.90,
        "qwen/qwen3.6-flash": 0.73,
        "qwen/qwen3.6-max-preview": 8.70,
        "qwen/qwen3-max": 8.70,
        "qwen/qwen-plus": 2.90,
        "qwen/qwen-flash": 0.36,
        "qwen/qwen3.5-plus": 2.90,
        "qwen/qwen3.5-flash": 0.73,
        "qwen/qwq-plus": 5.80,
        "qwen/qvq-max": 8.70,
    }
    MODEL_PRICE_OUTPUT: dict[str, float] = {
        "deepseek/deepseek-v4-pro": 6.0,
        "deepseek/deepseek-v4-flash": 2.0,
        # ═══ SenseTime (商汤) — 限时免费 ═══
        "sensetime/SenseChat-Turbo": 0.0,
        "sensetime/SenseChat-Pro": 0.0,
        # ═══ Qwen (千问) — USD→CNY @7.25 ═══
        "qwen/qwen3.6-plus": 17.40,
        "qwen/qwen3.6-flash": 2.90,
        "qwen/qwen3.6-max-preview": 43.50,
        "qwen/qwen3-max": 43.50,
        "qwen/qwen-plus": 8.70,
        "qwen/qwen-flash": 2.90,
        "qwen/qwen3.5-plus": 17.40,
        "qwen/qwen3.5-flash": 2.90,
        "qwen/qwq-plus": 17.40,
        "qwen/qvq-max": 43.50,
    }

    def __init__(self):
        self._history: list[ROIResult] = []
        self._total_value = 0.0
        self._total_cost = 0.0

    def estimate_value(
        self, task_type: str, complexity: float = 0.5,
        user_priority: float = 0.5, task_desc: str = "",
    ) -> float:
        """估算任务价值.

        Args:
            task_type: 任务类型（见 TASK_VALUE_BASE）
            complexity: 0-1 任务复杂度
            user_priority: 0-1 用户优先级
            task_desc: 任务描述（用于上下文调整）

        Returns:
            归一化任务价值（越高 = 越值得做）
        """
        base = self.TASK_VALUE_BASE.get(task_type, 1.0)

        # 复杂度调整: 复杂任务价值更高
        complexity_mult = 0.5 + complexity

        # 优先级调整: 紧急任务价值翻倍
        priority_mult = 0.5 + user_priority

        # 任务描述中检测关键信号
        desc_bonus = 0.0
        desc_lower = task_desc.lower()
        if any(kw in desc_lower for kw in
               ["环评", "environmental", "合规", "compliance", "法律", "legal"]):
            desc_bonus += 2.0
        if any(kw in desc_lower for kw in ["紧急", "urgent", "critical", "关键"]):
            desc_bonus += 1.0
        if any(kw in desc_lower for kw in ["安全", "security", "漏洞", "vulnerability"]):
            desc_bonus += 1.5

        value = base * complexity_mult * priority_mult + desc_bonus
        return round(max(0.1, value), 2)

    def estimate_cost(
        self, estimated_tokens: int, model: str = "deepseek/deepseek-v4-flash",
    ) -> float:
        """估算任务成本（元）.

        使用平均价格 (input+output)/2 进行估算。
        """
        in_price = self.MODEL_PRICE_INPUT.get(model, 1.0)
        out_price = self.MODEL_PRICE_OUTPUT.get(model, 2.0)
        avg_price = (in_price + out_price) / 2
        cost = estimated_tokens / 1_000_000 * avg_price
        return round(cost, 4)

    def evaluate(
        self, task_id: str, task_type: str, estimated_tokens: int,
        model: str, complexity: float = 0.5, user_priority: float = 0.5,
        predicted_quality: float = 0.5, policy: EconomicPolicy | None = None,
        task_desc: str = "",
    ) -> ROIResult:
        """综合评估任务的经济可行性.

        Returns:
            ROIResult 含预估 ROI、三元评分、通过/拒绝.
        """
        policy = policy or EconomicPolicy.balanced()
        value = self.estimate_value(task_type, complexity, user_priority, task_desc)
        cost = self.estimate_cost(estimated_tokens, model)
        roi = value / max(cost, 0.0001)

        trilemma = TrilemmaVector.from_raw(
            estimated_cost_yuan=cost,
            estimated_ms=estimated_tokens * 0.02,  # ~50 tok/ms
            predicted_quality=predicted_quality,
            budget_yuan=policy.max_task_budget_yuan,
        )
        score = trilemma.weighted_score(policy)

        approved = (
            roi >= policy.roi_threshold
            and score >= policy.min_score
            and predicted_quality >= policy.min_quality_threshold
            and cost <= policy.max_task_budget_yuan
        )

        reason_parts = []
        if roi < policy.roi_threshold:
            reason_parts.append(f"ROI {roi:.2f} < 阈值 {policy.roi_threshold}")
        if score < policy.min_score:
            reason_parts.append(f"综合评分 {score:.3f} < 阈值 {policy.min_score}")
        if predicted_quality < policy.min_quality_threshold:
            reason_parts.append(
                f"预测质量 {predicted_quality:.2f} < 阈值 {policy.min_quality_threshold}")
        if cost > policy.max_task_budget_yuan:
            reason_parts.append(
                f"预估成本 ¥{cost:.2f} > 单任务预算 ¥{policy.max_task_budget_yuan:.2f}")

        result = ROIResult(
            task_id=task_id,
            task_value=value,
            estimated_cost_yuan=cost,
            roi_estimate=round(roi, 2),
            trilemma=trilemma,
            score=round(score, 4),
            approved=approved,
            reason="; ".join(reason_parts) if reason_parts else "通过经济审查",
        )

        self._total_value += value
        self._total_cost += cost
        logger.info(
            f"ROIModel: task '{task_id}' | value={value:.1f} cost=¥{cost:.3f} "
            f"ROI={roi:.1f}x | {'✓ 通过' if approved else '✗ 拒绝'}"
        )
        return result

    def record_actual(self, result: ROIResult, actual_cost_yuan: float) -> ROIResult:
        """记录实际成本，计算实际 ROI."""
        result.actual_cost_yuan = actual_cost_yuan
        result.roi_actual = round(
            result.task_value / max(actual_cost_yuan, 0.0001), 2)
        self._history.append(result)
        # Keep last 100
        if len(self._history) > 100:
            self._history = self._history[-100:]
        return result

    def cumulative_roi(self) -> float:
        """累计 ROI."""
        if self._total_cost == 0:
            return 0.0
        return round(self._total_value / self._total_cost, 2)

    def stats(self) -> dict[str, Any]:
        approved_count = sum(1 for r in self._history if r.approved)
        total = max(len(self._history), 1)
        return {
            "total_tasks": len(self._history),
            "approval_rate": round(approved_count / total, 3),
            "cumulative_roi": self.cumulative_roi(),
            "total_value": round(self._total_value, 2),
            "total_cost_yuan": round(self._total_cost, 4),
            "avg_task_value": round(
                sum(r.task_value for r in self._history) / total, 2),
            "avg_cost_yuan": round(
                sum(r.estimated_cost_yuan for r in self._history) / total, 4),
        }


# ═══════════════════════════════════════════════════════════════════
# Compliance Gate — 合法合规审查
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ComplianceResult:
    """合规审查结果."""
    passed: bool = True
    checks: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    risk_level: str = "low"    # low / medium / high / critical
    requires_approval: bool = False
    notes: str = ""


class ComplianceGate:
    """合法合规审查门控——确保所有操作在法规红线内.

    审查维度:
      1. 数据安全: 敏感信息泄露检测（身份证号、银行卡、密码等）
      2. 环评合规: 环境法规红线（伪造数据、瞒报排放等）
      3. 知识产权: 代码授权检查、第三方库许可合规
      4. 商业合规: 反垄断、商业秘密保护
      5. 用户权益: 用户数据隐私、知情同意

    集成: 在 EconomicOrchestrator.evaluate() 之前调用。
    """

    # 敏感信息正则模式
    SENSITIVE_PATTERNS: dict[str, str] = {
        "身份证号": r"\b\d{17}[\dXx]\b",
        "手机号": r"\b1[3-9]\d{9}\b",
        "银行卡号": r"\b\d{16,19}\b",
        "密码明文": r"(?i)(password|passwd|secret)\s*[=:]\s*\S+",
        "API密钥": r"(?i)(api[_-]?key|access[_-]?token)\s*[=:]\s*\S+",
    }

    # 环评合规红线关键字
    ENV_REDLINES: list[str] = [
        "伪造监测数据", "篡改检测报告", "瞒报排放量",
        "环评造假", "虚假验收", "违规排放",
        "未批先建", "越权审批",
    ]

    # 高风险代码模式
    DANGEROUS_CODE_PATTERNS: dict[str, str] = {
        "删除数据库": r"(?i)DROP\s+(TABLE|DATABASE)",
        "格式化磁盘": r"(?i)mkfs\.|format\s+[A-Z]:",
        "删除系统文件": r"(?i)rm\s+-rf\s+/(etc|usr|var|boot)",
        "提权操作": r"(?i)chmod\s+777\s+/",
        "反弹Shell": r"(?i)nc\s+-e\s+/bin/(bash|sh)|bash\s+-i\s+>&",
    }

    def __init__(self, level: ComplianceLevel = ComplianceLevel.NORMAL):
        self._level = level
        self._violation_count = 0

    def check_task(self, task_desc: str, task_type: str = "general",
                   code_snippets: str = "", user_context: str = "") -> ComplianceResult:
        """对任务进行合规审查.

        Args:
            task_desc: 任务描述
            task_type: 任务类型
            code_snippets: 涉及的代码片段（可选）
            user_context: 用户上下文（可选）

        Returns:
            ComplianceResult 审查结果.
        """
        if self._level == ComplianceLevel.PERMISSIVE:
            return ComplianceResult(
                passed=True, checks=["宽松模式: 跳过合规审查"],
                risk_level="low")

        checks: list[str] = []
        violations: list[str] = []

        # 1. 敏感信息检测
        sens_check = self._check_sensitive(task_desc + user_context)
        checks.append("敏感信息检测: " + ("✓" if not sens_check else "✗ 发现敏感信息"))
        violations.extend(sens_check)

        # 2. 环评合规红线
        env_check = self._check_env_compliance(task_desc)
        checks.append("环评合规: " + ("✓" if not env_check else "✗ 触碰红线"))
        violations.extend(env_check)

        # 3. 代码安全审查（如涉及代码）
        if code_snippets and self._level != ComplianceLevel.PERMISSIVE:
            code_check = self._check_dangerous_code(code_snippets)
            checks.append("代码安全: " + ("✓" if not code_check else "✗ 检测到危险代码"))
            violations.extend(code_check)

        # 4. 综合风险评级
        risk_level = "low"
        if len(violations) >= 3:
            risk_level = "critical"
        elif len(violations) >= 2:
            risk_level = "high"
        elif len(violations) >= 1:
            risk_level = "medium"

        passed = len(violations) == 0
        if self._level == ComplianceLevel.STRICT and risk_level != "low":
            passed = False  # 严格模式: medium 也不允许

        result = ComplianceResult(
            passed=passed,
            checks=checks,
            violations=violations,
            risk_level=risk_level,
            requires_approval=risk_level in ("high", "critical"),
            notes=f"审查级别: {self._level.value}, 风险: {risk_level}",
        )

        if violations:
            self._violation_count += len(violations)
            logger.warning(
                f"ComplianceGate: {len(violations)} violations, risk={risk_level}")
        return result

    def _check_sensitive(self, text: str) -> list[str]:
        if not text:
            return []
        import re
        findings = []
        for label, pattern in self.SENSITIVE_PATTERNS.items():
            if re.search(pattern, text):
                findings.append(f"发现疑似{label}: {pattern}")
        return findings

    def _check_env_compliance(self, text: str) -> list[str]:
        if not text:
            return []
        findings = []
        text_lower = text.lower()
        for redline in self.ENV_REDLINES:
            if redline in text:
                findings.append(f"环评红线: {redline}")
        # Also check English variants
        env_en = {
            "falsify monitoring data": "伪造监测数据",
            "tamper with report": "篡改报告",
            "conceal emissions": "瞒报排放",
        }
        for en, cn in env_en.items():
            if en in text_lower:
                findings.append(f"环评红线(EN): {cn}")
        return findings

    def _check_dangerous_code(self, code: str) -> list[str]:
        if not code:
            return []
        import re
        findings = []
        for label, pattern in self.DANGEROUS_CODE_PATTERNS.items():
            if re.search(pattern, code, re.IGNORECASE):
                findings.append(f"危险代码: {label}")
        return findings

    def stats(self) -> dict[str, Any]:
        return {
            "violation_count": self._violation_count,
            "level": self._level.value,
        }


# ═══════════════════════════════════════════════════════════════════
# Economic Decision — 经济决策结果
# ═══════════════════════════════════════════════════════════════════

@dataclass
class EconomicDecision:
    """经济编排器的单次决策结果."""
    task_id: str = ""
    task_desc: str = ""
    go: bool = False                    # 是否执行
    policy: str = "balanced"            # 采用的策略名
    selected_model: str = "deepseek/deepseek-v4-flash"
    trilemma: TrilemmaVector = field(default_factory=TrilemmaVector)
    roi: ROIResult = field(default_factory=ROIResult)
    compliance: ComplianceResult = field(default_factory=ComplianceResult)
    estimated_tokens: int = 0
    estimated_cost_yuan: float = 0.0
    estimated_ms: float = 0.0
    suggestion: str = ""                # 如果不执行，建议什么
    decided_at: float = field(default_factory=time.time)

    def summary(self) -> str:
        status = "✓ GO" if self.go else "✗ NOGO"
        return (
            f"[{status}] {self.task_id} | {self.policy} | "
            f"模型={self.selected_model.split('/')[-1]} | "
            f"ROI={self.roi.roi_estimate:.1f}x | "
            f"成本≈¥{self.estimated_cost_yuan:.3f} | "
            f"合规={'✓' if self.compliance.passed else '✗'}"
        )


# ═══════════════════════════════════════════════════════════════════
# Economic Orchestrator — 经济决策编排器
# ═══════════════════════════════════════════════════════════════════

class EconomicOrchestrator:
    """经济决策编排器——在所有关键决策点注入经济理性.

    工作流:
      1. 选择策略: 根据任务类型自动选择 ECONOMY/BALANCED/QUALITY/SPEED
      2. 合规审查: ComplianceGate.check_task()
      3. ROI 评估: ROIModel.evaluate()
      4. 模型选择: EconomicPolicy.select_model()
      5. 综合决策: 三元评分 + ROI + 合规 → Go/NoGo/Replan
      6. 执行后: 记录实际成本，更新 ROI 模型

    集成点:
      - LifeEngine: 执行前调用 evaluate()
      - TreeLLM: 模型选择调用 select_model()
      - CostAware: 预算检查调用 check_budget()
    """

    def __init__(
        self,
        roi_model: ROIModel | None = None,
        compliance_gate: ComplianceGate | None = None,
        thermo_budget = None,
        revenue_engine = None,
    ):
        self.roi = roi_model or ROIModel()
        self.compliance = compliance_gate or ComplianceGate()
        self.thermo = thermo_budget  # KL budget cascade source
        self.revenue = revenue_engine  # Revenue tracking + billing
        self._decisions: list[EconomicDecision] = []
        self._daily_cost_tracker: dict[str, float] = defaultdict(float)  # date → total_yuan
        self._session_budgets: dict[str, float] = {}

    def select_policy(self, task_type: str, user_priority: float = 0.5) -> EconomicPolicy:
        """根据任务类型自动选择经济策略.

        映射:
          environmental_report, legal → QUALITY
          code_generation, code_review → BALANCED
          question, chat → ECONOMY
          realtime, interactive → SPEED
        """
        quality_types = {"environmental_report", "legal_document", "compliance_check"}
        speed_types = {"question", "chat", "interactive", "realtime"}
        economy_types = {"batch_job", "background", "low_priority"}

        if task_type in quality_types or user_priority > 0.8:
            return EconomicPolicy.quality()
        elif task_type in speed_types:
            return EconomicPolicy.speed()
        elif task_type in economy_types:
            return EconomicPolicy.economy()
        else:
            return EconomicPolicy.balanced()

    def evaluate(
        self,
        task_id: str,
        task_desc: str,
        task_type: str = "general",
        estimated_tokens: int = 5000,
        complexity: float = 0.5,
        user_priority: float = 0.5,
        predicted_quality: float = 0.5,
        code_snippets: str = "",
        user_context: str = "",
        daily_spent_yuan: float = 0.0,
    ) -> EconomicDecision:
        """综合评估任务——Go/NoGo/Replan 决策.

        Returns:
            EconomicDecision 含所有评估维度.
        """
        # 0. 简单任务穿透：complexity < 0.2 的简单查询直接放行，避免"ROI低"误杀
        if complexity < 0.2 and estimated_tokens < 1000:
            return EconomicDecision(
                task_id=task_id, task_desc=task_desc,
                go=True, policy="economy_bypass",
                selected_model="deepseek/deepseek-v4-flash",
                trilemma=TrilemmaVector(cost_score=1.0, speed_score=1.0, quality_score=0.6),
                roi=ROIResult(approved=True, roi_estimate=9.0),
                compliance=ComplianceResult(passed=True),
                estimated_tokens=estimated_tokens,
                suggestion="简单任务 — 经济审查自动放行",
            )

        # 1. 选择策略
        policy = self.select_policy(task_type, user_priority)

        # 2. 合规审查
        comp_result = self.compliance.check_task(
            task_desc, task_type, code_snippets, user_context)

        # 3. 预算检查
        if daily_spent_yuan >= policy.max_daily_budget_yuan:
            return EconomicDecision(
                task_id=task_id, task_desc=task_desc,
                go=False, policy=policy.__class__.__name__.lower(),
                compliance=comp_result,
                suggestion=f"日预算已耗尽 (¥{daily_spent_yuan:.2f}/¥{policy.max_daily_budget_yuan:.2f})",
            )

        # 4. 模型选择 (KL budget cascade influence)
        model = policy.select_model(complexity)

        # ── KL budget cascade: influence model tier selection ──
        if self.thermo and hasattr(self.thermo, 'kl_budget'):
            kl_budget = self.thermo.kl_budget
            if kl_budget > 0.5 and model == "deepseek/deepseek-v4-flash" and complexity > 0.5:
                # KL budget allows exploring higher tier for complex tasks
                if self.thermo.consume_kl_budget(0.3):
                    model = "deepseek/deepseek-v4-pro"
            elif kl_budget < 0.1 and model == "deepseek/deepseek-v4-pro" and complexity < 0.6:
                # Low KL budget → conserve, use flash
                model = "deepseek/deepseek-v4-flash"
                self.thermo.contribute_kl_budget(0.1)  # Reward conservation

        # 5. ROI 评估
        roi_result = self.roi.evaluate(
            task_id=task_id, task_type=task_type,
            estimated_tokens=estimated_tokens, model=model,
            complexity=complexity, user_priority=user_priority,
            predicted_quality=predicted_quality, policy=policy,
            task_desc=task_desc,
        )

        # 6. 综合决策
        go = roi_result.approved and comp_result.passed

        # 如果不通过但合规风险为 low，可尝试降级到 Flash 再评估
        suggestion = ""
        if not go and comp_result.passed:
            # 尝试降级
            flash_roi = self.roi.evaluate(
                task_id=f"{task_id}_flash", task_type=task_type,
                estimated_tokens=estimated_tokens,
                model="deepseek/deepseek-v4-flash",
                complexity=complexity, user_priority=user_priority,
                predicted_quality=predicted_quality * 0.9,  # Flash 质量略低
                policy=policy, task_desc=task_desc,
            )
            if flash_roi.approved and policy.degradation_enabled:
                go = True
                model = "deepseek/deepseek-v4-flash"
                roi_result = flash_roi
                suggestion = "已降级至 Flash 模型以通过经济审查"
                # KL budget cascade: reward budget-saving downgrade
                if self.thermo and hasattr(self.thermo, 'contribute_kl_budget'):
                    self.thermo.contribute_kl_budget(0.1)
            else:
                suggestion = roi_result.reason

        if not go and not comp_result.passed:
            suggestion = f"合规未通过: {comp_result.notes}"

        decision = EconomicDecision(
            task_id=task_id,
            task_desc=task_desc,
            go=go,
            policy=policy.__class__.__name__.lower(),
            selected_model=model,
            trilemma=roi_result.trilemma,
            roi=roi_result,
            compliance=comp_result,
            estimated_tokens=estimated_tokens,
            estimated_cost_yuan=roi_result.estimated_cost_yuan,
            estimated_ms=estimated_tokens * 0.02,
            suggestion=suggestion,
        )

        self._decisions.append(decision)
        if len(self._decisions) > 200:
            self._decisions = self._decisions[-200:]

        logger.info(decision.summary())
        return decision

    def record_actual(
        self, decision: EconomicDecision, actual_cost_yuan: float,
    ) -> None:
        """记录实际执行成本."""
        self.roi.record_actual(decision.roi, actual_cost_yuan)

        # 更新每日成本追踪
        from datetime import date
        today = date.today().isoformat()
        self._daily_cost_tracker[today] += actual_cost_yuan

    def check_daily_budget(
        self, policy: EconomicPolicy | None = None,
    ) -> tuple[float, float, bool]:
        """检查当日预算使用情况."""
        from datetime import date
        today = date.today().isoformat()
        spent = self._daily_cost_tracker.get(today, 0.0)
        policy = policy or EconomicPolicy.balanced()
        remaining = max(0.0, policy.max_daily_budget_yuan - spent)
        exceeded = spent >= policy.max_daily_budget_yuan
        return (spent, remaining, exceeded)

    def session_budget_remaining(
        self, session_id: str, allocated_yuan: float,
    ) -> float:
        """会话预算审计."""
        spent = self._session_budgets.get(session_id, 0.0)
        return max(0.0, allocated_yuan - spent)

    def stats(self) -> dict[str, Any]:
        decisions = self._decisions
        total = max(len(decisions), 1)
        go_count = sum(1 for d in decisions if d.go)
        from datetime import date
        today = date.today().isoformat()
        return {
            "total_decisions": len(decisions),
            "go_rate": round(go_count / total, 3),
            "avg_roi": round(
                sum(d.roi.roi_estimate for d in decisions) / total, 2),
            "avg_cost_yuan": round(
                sum(d.estimated_cost_yuan for d in decisions) / total, 4),
            "daily_spent_yuan": round(self._daily_cost_tracker.get(today, 0.0), 4),
            "cumulative_roi": self.roi.cumulative_roi(),
            "compliance_violations": self.compliance.stats()["violation_count"],
        }


# ═══════════════════════════════════════════════════════════════════
# Adaptive Economic Scheduler — 自适应经济调度器
# ═══════════════════════════════════════════════════════════════════

class AdaptiveEconomicScheduler:
    """自适应经济调度器 — 根据时段/紧急度/累计ROI动态切换策略.

    时段策略:
      工作时间 (9:00-18:00): BALANCED — 快速响应
      晚间 (18:00-23:00): ECONOMY — 节省成本
      深夜 (23:00-9:00): ECONOMY — 批处理优先
      周末: ECONOMY — 节省成本

    紧急度覆盖:
      紧急任务 (priority>0.8): 强制 QUALITY，不限时段

    累计ROI覆盖:
      高 ROI (>5x): 放宽预算 +50%
      低 ROI (<1x): 收紧预算 -30%
    """

    def __init__(self):
        self._roi_model: ROIModel | None = None
        self._switch_count = 0
        self._current_policy = "balanced"

    def select_policy(
        self,
        user_priority: float = 0.5,
        roi_model: ROIModel | None = None,
    ) -> EconomicPolicy:
        """根据当前上下文自动选择最优经济策略.

        Args:
            user_priority: 0-1 用户优先级
            roi_model: 可选ROI模型用于累计ROI检查

        Returns:
            EconomicPolicy with optimal weights and budget
        """
        from datetime import datetime

        now = datetime.now()
        hour = now.hour
        weekday = now.weekday()  # 0=Mon, 6=Sun
        is_weekend = weekday >= 5

        # 1. 紧急度覆盖：紧急任务强制质量优先
        if user_priority > 0.8:
            policy = EconomicPolicy.quality()
            self._current_policy = "quality"
            self._switch_count += 1
            logger.info(f"AdaptiveScheduler: QUALITY (priority={user_priority:.2f})")
            return policy

        # 2. 时段选择
        if is_weekend or hour >= 23 or hour < 9:
            policy = EconomicPolicy.economy()
            policy_name = "economy"
        elif 9 <= hour < 18:
            policy = EconomicPolicy.balanced()
            policy_name = "balanced"
        else:  # 18:00-23:00
            policy = EconomicPolicy.economy()
            policy_name = "economy"

        # 3. 累计ROI覆盖
        if roi_model:
            cum_roi = roi_model.cumulative_roi()
            if cum_roi > 5.0:
                # 高ROI: 放宽预算50%
                policy.max_daily_budget_yuan *= 1.5
                policy.max_task_budget_yuan *= 1.5
                policy.roi_threshold *= 0.7
                logger.info(f"AdaptiveScheduler: budget+50% (cumulative ROI={cum_roi:.1f}x)")
            elif cum_roi < 1.0 and cum_roi > 0:
                # 低ROI: 收紧预算30%
                policy.max_daily_budget_yuan *= 0.7
                policy.max_task_budget_yuan *= 0.7
                policy.roi_threshold *= 1.3
                logger.info(f"AdaptiveScheduler: budget-30% (cumulative ROI={cum_roi:.1f}x)")

        if self._current_policy != policy_name:
            self._switch_count += 1
            self._current_policy = policy_name
            logger.info(f"AdaptiveScheduler: switched to {policy_name.upper()} "
                        f"(hour={hour}, weekend={is_weekend}, priority={user_priority:.2f})")

        return policy

    def stats(self) -> dict[str, Any]:
        return {
            "switch_count": self._switch_count,
            "current_policy": self._current_policy,
        }


# ═══════════════════════════════════════════════════════════════════
# Singleton
# ═══════════════════════════════════════════════════════════════════

_economic_orchestrator: EconomicOrchestrator | None = None


def get_economic_orchestrator(
    roi_model: ROIModel | None = None,
    compliance_gate: ComplianceGate | None = None,
) -> EconomicOrchestrator:
    """Get or create the singleton EconomicOrchestrator.
    
    Auto-wires ThermoBudget for KL budget cascade (Go/NoGo + model tier).
    """
    global _economic_orchestrator
    if _economic_orchestrator is None:
        # ── Wire ThermoBudget into economic decisions ──
        try:
            from .thermo_budget import get_thermo_budget
            thermo = get_thermo_budget()
        except Exception:
            thermo = None
        # ── Wire RevenueEngine for cost/revenue tracking ──
        try:
            from ..market.revenue_engine import get_investment_engine
            revenue = get_investment_engine()
        except Exception:
            revenue = None
        _economic_orchestrator = EconomicOrchestrator(
            roi_model=roi_model, compliance_gate=compliance_gate,
            thermo_budget=thermo, revenue_engine=revenue)
    return _economic_orchestrator


def reset_economic_orchestrator() -> None:
    """Test helper."""
    global _economic_orchestrator
    _economic_orchestrator = None
