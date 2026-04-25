# -*- coding: utf-8 -*-
"""
Intelligent Upgrade Decision Engine - 智能升级决策引擎
====================================================

基于质量评估的动态模型升级决策系统

核心功能：
1. 渐进式升级 - 逐级尝试
2. 预测性升级 - 直接选择合适级别
3. 分治升级 - 不同子问题不同模型
4. 增强式升级 - 草稿→优化模式

Author: LivingTreeAI Agent
Date: 2026-04-24
"""

from __future__ import annotations

import time
from typing import Optional, List, Dict, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import threading


# ═══════════════════════════════════════════════════════════════════════════════
# 升级策略定义
# ═══════════════════════════════════════════════════════════════════════════════

class UpgradeStrategy(Enum):
    """升级策略"""
    GRADUAL = "gradual"           # 渐进式：逐级尝试
    PREDICTIVE = "predictive"     # 预测性：直接选择合适级别
    DIVIDE_CONQUER = "divide"     # 分治：不同子问题不同模型
    ENHANCE = "enhance"           # 增强：草稿→优化模式
    ADAPTIVE = "adaptive"          # 自适应：根据历史学习


class UpgradeReason(Enum):
    """升级原因"""
    LOW_QUALITY = "low_quality"           # 质量不足
    KNOWLEDGE_GAP = "knowledge_gap"      # 知识不足
    REASONING_WEAK = "reasoning_weak"     # 推理能力弱
    EXPRESSION_POOR = "expression_poor"   # 表达能力差
    COMPLEXITY_HIGH = "complexity_high"   # 复杂度高
    USER_REQUEST = "user_request"         # 用户要求高质量
    CRITICAL_DOMAIN = "critical_domain"  # 关键领域（医疗/法律/金融）


@dataclass
class UpgradeCandidate:
    """升级候选"""
    target_level: int
    reason: UpgradeReason
    confidence: float = 0.8
    estimated_cost: float = 0.0
    estimated_time_ms: float = 0.0


@dataclass
class UpgradeDecision:
    """升级决策"""
    should_upgrade: bool
    strategy: UpgradeStrategy
    target_level: int
    reason: UpgradeReason
    confidence: float
    max_attempts: int  # 最大尝试次数，防止无限循环
    alternatives: List[UpgradeCandidate] = field(default_factory=list)
    reasoning: str = ""


@dataclass
class UpgradeHistory:
    """升级历史记录"""
    query: str
    original_level: int
    target_level: int
    quality_before: float
    quality_after: float
    success: bool
    reason: UpgradeReason
    timestamp: float


# ═══════════════════════════════════════════════════════════════════════════════
# 升级决策引擎
# ═══════════════════════════════════════════════════════════════════════════════

class UpgradeDecisionEngine:
    """
    智能升级决策引擎
    
    决策流程：
    1. 分析当前状态
    2. 选择升级策略
    3. 决定目标级别
    4. 限制尝试次数
    """

    # 模型级别定义
    MODEL_LEVELS = {
        0: {"name": "L0-极轻量", "models": ["qwen2.5:0.5b"], "capability": "快速响应"},
        1: {"name": "L1-轻量", "models": ["qwen2.5:1.5b"], "capability": "一般推理"},
        2: {"name": "L2-标准", "models": ["qwen3.5:2b"], "capability": "中等复杂度"},
        3: {"name": "L3-专家", "models": ["qwen3.5:4b"], "capability": "深度推理"},
        4: {"name": "L4-专家+", "models": ["qwen3.5:9b"], "capability": "复杂任务"},
    }
    
    # 关键领域映射（直接使用高级模型）
    CRITICAL_DOMAINS = {
        "医疗": 4, "medicine": 4, "medical": 4,
        "法律": 4, "law": 4, "legal": 4,
        "金融": 4, "finance": 4, "financial": 4,
        "投资": 4, "investment": 4,
        "编程": 3, "代码": 3, "programming": 3,
    }
    
    # 升级成本估算（相对值）
    LEVEL_COST_MULTIPLIER = {0: 1, 1: 2, 2: 4, 3: 8, 4: 16}
    
    # 最大尝试次数
    MAX_UPGRADE_ATTEMPTS = 2
    
    def __init__(
        self,
        max_level: int = 4,
        strategy: UpgradeStrategy = UpgradeStrategy.ADAPTIVE,
        budget_ms: float = 10000,
    ):
        self.max_level = max_level
        self.strategy = strategy
        self.budget_ms = budget_ms
        
        # 历史记录
        self._history: List[UpgradeHistory] = []
        self._history_lock = threading.Lock()
        
        # 统计
        self._stats = defaultdict(int)
        
        # 回调
        self._on_decide: Optional[Callable] = None
        
        # 学习数据：任务类型 → 最佳级别
        self._task_level_map: Dict[str, int] = {}
        
        print("[UpgradeDecisionEngine] 已初始化")
    
    def decide(
        self,
        query: str,
        current_level: int,
        quality_score: float,
        quality_report: Any = None,
        attempt_count: int = 0,
    ) -> UpgradeDecision:
        """
        做出升级决策
        
        Args:
            query: 用户查询
            current_level: 当前模型级别
            quality_score: 当前质量评分
            quality_report: 详细质量报告
            attempt_count: 当前尝试次数
            
        Returns:
            UpgradeDecision: 升级决策
        """
        # 检查是否已达最大级别
        if current_level >= self.max_level:
            return UpgradeDecision(
                should_upgrade=False,
                strategy=self.strategy,
                target_level=current_level,
                reason=UpgradeReason.LOW_QUALITY,
                confidence=1.0,
                max_attempts=0,
                reasoning="已达最高模型级别",
            )
        
        # 检查尝试次数
        if attempt_count >= self.MAX_UPGRADE_ATTEMPTS:
            return UpgradeDecision(
                should_upgrade=False,
                strategy=self.strategy,
                target_level=current_level,
                reason=UpgradeReason.LOW_QUALITY,
                confidence=1.0,
                max_attempts=0,
                reasoning="已达最大升级尝试次数",
            )
        
        # 分析升级原因
        reason, target_level = self._analyze_and_decide(
            query, current_level, quality_score, quality_report
        )
        
        # 检查是否需要升级
        if target_level <= current_level:
            return UpgradeDecision(
                should_upgrade=False,
                strategy=self.strategy,
                target_level=current_level,
                reason=reason,
                confidence=0.8,
                max_attempts=0,
                reasoning="当前级别已足够",
            )
        
        # 选择策略
        strategy = self._select_strategy(query, quality_score, quality_report)
        
        # 根据策略调整目标级别
        if strategy == UpgradeStrategy.GRADUAL:
            target_level = min(current_level + 1, self.max_level)
        elif strategy == UpgradeStrategy.PREDICTIVE:
            # 保持预测的目标级别
            pass
        elif strategy == UpgradeStrategy.ENHANCE:
            # 增强模式：保持在当前级别，草稿后优化
            target_level = current_level
        
        # 生成替代方案
        alternatives = self._generate_alternatives(current_level, reason)
        
        reasoning = self._generate_reasoning(query, reason, target_level, quality_score)
        
        # 触发回调
        if self._on_decide:
            self._on_decide(UpgradeDecision(
                should_upgrade=True,
                strategy=strategy,
                target_level=target_level,
                reason=reason,
                confidence=0.8,
                max_attempts=self.MAX_UPGRADE_ATTEMPTS - attempt_count,
                alternatives=alternatives,
                reasoning=reasoning,
            ))
        
        return UpgradeDecision(
            should_upgrade=True,
            strategy=strategy,
            target_level=target_level,
            reason=reason,
            confidence=0.8,
            max_attempts=self.MAX_UPGRADE_ATTEMPTS - attempt_count,
            alternatives=alternatives,
            reasoning=reasoning,
        )
    
    def _analyze_and_decide(
        self,
        query: str,
        current_level: int,
        quality_score: float,
        quality_report: Any,
    ) -> Tuple[UpgradeReason, int]:
        """分析并决定升级原因和目标级别"""
        
        # 1. 检查关键领域
        for domain, level in self.CRITICAL_DOMAINS.items():
            if domain in query:
                return UpgradeReason.CRITICAL_DOMAIN, level
        
        # 2. 检查历史学习
        task_type = self._infer_task_type(query)
        if task_type in self._task_level_map:
            learned_level = self._task_level_map[task_type]
            if learned_level > current_level:
                return UpgradeReason.USER_REQUEST, learned_level
        
        # 3. 基于质量报告分析
        if quality_report:
            # 准确性不足 → 知识更丰富的模型
            if hasattr(quality_report, 'dimension_scores'):
                dims = quality_report.dimension_scores
                
                # 深度不足
                if 'depth' in dims and dims['depth'].score < 0.4:
                    return UpgradeReason.REASONING_WEAK, current_level + 1
                
                # 准确性不足
                if 'accuracy' in dims and dims['accuracy'].score < 0.5:
                    return UpgradeReason.KNOWLEDGE_GAP, current_level + 1
                
                # 完整性不足
                if 'completeness' in dims and dims['completeness'].score < 0.4:
                    return UpgradeReason.COMPLEXITY_HIGH, min(current_level + 2, self.max_level)
        
        # 4. 基于质量评分
        if quality_score < 0.3:
            return UpgradeReason.LOW_QUALITY, min(current_level + 2, self.max_level)
        elif quality_score < 0.5:
            return UpgradeReason.LOW_QUALITY, current_level + 1
        
        # 5. 基于查询复杂度
        complexity = self._estimate_complexity(query)
        if complexity > 0.8 and current_level < 3:
            return UpgradeReason.COMPLEXITY_HIGH, min(current_level + 2, self.max_level)
        elif complexity > 0.5 and current_level < 2:
            return UpgradeReason.COMPLEXITY_HIGH, current_level + 1
        
        # 质量足够，不需要升级
        return UpgradeReason.LOW_QUALITY, current_level
    
    def _select_strategy(
        self,
        query: str,
        quality_score: float,
        quality_report: Any,
    ) -> UpgradeStrategy:
        """选择升级策略"""
        
        # 如果是自适应策略，根据情况选择
        if self.strategy != UpgradeStrategy.ADAPTIVE:
            return self.strategy
        
        # 质量极低，需要渐进尝试
        if quality_score < 0.3:
            return UpgradeStrategy.GRADUAL
        
        # 高复杂度任务，预测性升级
        complexity = self._estimate_complexity(query)
        if complexity > 0.7:
            return UpgradeStrategy.PREDICTIVE
        
        # 创意任务，增强式
        creative_keywords = ["创作", "写作", "故事", "诗歌", "创意"]
        if any(k in query for k in creative_keywords):
            return UpgradeStrategy.ENHANCE
        
        # 默认渐进式
        return UpgradeStrategy.GRADUAL
    
    def _generate_alternatives(
        self,
        current_level: int,
        reason: UpgradeReason,
    ) -> List[UpgradeCandidate]:
        """生成替代升级方案"""
        alternatives = []
        
        for level in range(current_level + 1, self.max_level + 1):
            alternatives.append(UpgradeCandidate(
                target_level=level,
                reason=reason,
                confidence=1.0 - (level - current_level) * 0.2,
                estimated_cost=self.LEVEL_COST_MULTIPLIER.get(level, 1),
                estimated_time_ms=level * 2000,
            ))
        
        return alternatives
    
    def _generate_reasoning(
        self,
        query: str,
        reason: UpgradeReason,
        target_level: int,
        quality_score: float,
    ) -> str:
        """生成决策推理"""
        level_name = self.MODEL_LEVELS.get(target_level, {}).get("name", f"L{target_level}")
        
        reason_text = {
            UpgradeReason.LOW_QUALITY: f"质量评分 {quality_score:.2f} 低于阈值",
            UpgradeReason.KNOWLEDGE_GAP: "当前模型知识可能不足以回答",
            UpgradeReason.REASONING_WEAK: "需要更强的推理能力",
            UpgradeReason.EXPRESSION_POOR: "需要更好的表达能力",
            UpgradeReason.COMPLEXITY_HIGH: "任务复杂度较高",
            UpgradeReason.USER_REQUEST: "用户要求高质量输出",
            UpgradeReason.CRITICAL_DOMAIN: "涉及关键领域，需要最高质量",
        }.get(reason, "综合分析决定升级")
        
        return f"{reason_text} → 升级到 {level_name}"
    
    def _infer_task_type(self, query: str) -> str:
        """推断任务类型"""
        # 简单关键词匹配
        if any(k in query for k in ["代码", "编程", "function", "def "]):
            return "code"
        if any(k in query for k in ["分析", "推理", "判断"]):
            return "reasoning"
        if any(k in query for k in ["写", "创作", "文章"]):
            return "writing"
        if any(k in query for k in ["翻译"]):
            return "translation"
        if any(k in query for k in ["总结", "摘要"]):
            return "summarization"
        return "general"
    
    def _estimate_complexity(self, query: str) -> float:
        """估算任务复杂度"""
        # 长度
        length_score = min(1.0, len(query) / 500)
        
        # 结构复杂度
        has_condition = 1 if ("如果" in query or "那么" in query) else 0
        has_comparison = 1 if ("还是" in query or "或者" in query) else 0
        structure_score = min(1.0, (has_condition + has_comparison) * 0.3)
        
        # 领域复杂度
        tech_keywords = ["算法", "架构", "系统", "机制", "原理"]
        tech_score = min(1.0, sum(1 for k in tech_keywords if k in query) * 0.2)
        
        return length_score * 0.3 + structure_score * 0.3 + tech_score * 0.4
    
    def record_result(
        self,
        query: str,
        original_level: int,
        target_level: int,
        quality_before: float,
        quality_after: float,
        reason: UpgradeReason,
    ):
        """记录升级结果用于学习"""
        with self._history_lock:
            history = UpgradeHistory(
                query=query,
                original_level=original_level,
                target_level=target_level,
                quality_before=quality_before,
                quality_after=quality_after,
                success=quality_after > quality_before,
                reason=reason,
                timestamp=time.time(),
            )
            self._history.append(history)
            
            # 更新统计
            self._stats["total_upgrades"] += 1
            if quality_after > quality_before:
                self._stats["successful_upgrades"] += 1
            else:
                self._stats["failed_upgrades"] += 1
            
            # 学习：记录任务类型与最佳级别
            task_type = self._infer_task_type(query)
            if quality_after > quality_before and quality_after > 0.6:
                # 成功的升级记录最佳级别
                if task_type not in self._task_level_map:
                    self._task_level_map[task_type] = target_level
                else:
                    # 如果当前成功，更新为更低级别（优化）
                    self._task_level_map[task_type] = min(
                        self._task_level_map[task_type],
                        target_level
                    )
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        with self._history_lock:
            total = self._stats["total_upgrades"]
            success = self._stats["successful_upgrades"]
            
            return {
                "total_upgrades": total,
                "successful_upgrades": success,
                "failed_upgrades": self._stats["failed_upgrades"],
                "success_rate": success / total if total > 0 else 0,
                "task_level_map": self._task_level_map.copy(),
                "history_count": len(self._history),
            }
    
    def set_decide_callback(self, callback: Callable):
        """设置决策回调"""
        self._on_decide = callback


# ═══════════════════════════════════════════════════════════════════════════════
# 增强式升级处理器
# ═══════════════════════════════════════════════════════════════════════════════

class EnhancementProcessor:
    """
    增强式升级处理器
    
    流程：草稿生成 → 质量评估 → 高级优化 → 结果整合
    """
    
    def __init__(
        self,
        base_evaluator: Any = None,
        max_iterations: int = 2,
    ):
        self.base_evaluator = base_evaluator
        self.max_iterations = max_iterations
    
    def process(
        self,
        draft_response: str,
        query: str,
        quality_report: Any,
    ) -> Tuple[str, List[QualityReport]]:
        """
        处理增强流程
        
        Returns:
            (增强后响应, 中间质量报告列表)
        """
        reports = [quality_report]
        current_response = draft_response
        
        for i in range(self.max_iterations):
            if quality_report.overall_score >= 0.7:
                break
            
            # 生成改进提示
            improvement_prompt = self._generate_improvement_prompt(
                query, current_response, quality_report
            )
            
            # 这里应该调用高级模型生成改进版本
            # 由于是框架代码，这里返回原响应
            improved_response = current_response  # TODO: 实际调用
            
            # 评估改进后的质量
            new_report = self.base_evaluator.evaluate(
                improved_response, query
            ) if self.base_evaluator else quality_report
            
            reports.append(new_report)
            current_response = improved_response
            
            if new_report.overall_score >= quality_report.overall_score + 0.1:
                quality_report = new_report
            else:
                break
        
        return current_response, reports
    
    def _generate_improvement_prompt(
        self,
        query: str,
        response: str,
        quality_report: Any,
    ) -> str:
        """生成改进提示"""
        suggestions = quality_report.improvement_suggestions[:3]
        
        prompt = f"""请改进以下回答：

问题：{query}

当前回答：{response}

改进建议：
"""
        for s in suggestions:
            prompt += f"- {s}\n"
        
        return prompt


# ═══════════════════════════════════════════════════════════════════════════════
# 快速决策函数
# ═══════════════════════════════════════════════════════════════════════════════

_engine: Optional[UpgradeDecisionEngine] = None


def get_upgrade_engine() -> UpgradeDecisionEngine:
    """获取升级引擎实例"""
    global _engine
    if _engine is None:
        _engine = UpgradeDecisionEngine()
    return _engine


def quick_decide(
    query: str,
    current_level: int,
    quality_score: float,
    attempt_count: int = 0,
) -> UpgradeDecision:
    """快速决策"""
    engine = get_upgrade_engine()
    return engine.decide(
        query=query,
        current_level=current_level,
        quality_score=quality_score,
        attempt_count=attempt_count,
    )
