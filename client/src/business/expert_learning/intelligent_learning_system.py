# -*- coding: utf-8 -*-
"""
智能学习系统统一入口 (Intelligent Learning System)
=================================================

整合六大核心模块的统一系统：
1. 完全离线的自学习循环 (OfflineLearningLoop)
2. 多模型知识一致性验证 (KnowledgeConsistencyVerifier)
3. 自动模型选择策略 (AutoModelSelector)
4. 成本优化引擎 (CostOptimizer)
5. 多模型对比系统 (MultiModelComparison)
6. 模型性能监控 (EnhancedPerformanceMonitor)

架构:
┌─────────────────────────────────────────────────────────────┐
│              IntelligentLearningSystem                          │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐   │
│  │              统一API层                                │   │
│  │   process() / learn() / optimize() / monitor()      │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  ┌────────────┐ ┌────────────┐ ┌────────────┐           │
│  │ OfflineLoop│ │Consistency │ │AutoSelector│           │
│  │ (永不掉线) │ │ (质量保障) │ │ (智能选模) │           │
│  └────────────┘ └────────────┘ └────────────┘           │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐           │
│  │CostOptimizer│ │Comparison │ │ Performance │           │
│  │ (成本优化) │ │ (多模型对比) │ │ (性能监控) │           │
│  └────────────┘ └────────────┘ └────────────┘           │
└─────────────────────────────────────────────────────────────┘

Author: LivingTreeAI Agent
Date: 2026-04-24
"""

from client.src.business.logger import get_logger
logger = get_logger('expert_learning.intelligent_learning_system')

from __future__ import annotations

import json
import time
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
import threading


# ═══════════════════════════════════════════════════════════════════════════════
# 导入子模块
# ═══════════════════════════════════════════════════════════════════════════════

def _import_modules():
    """延迟导入子模块"""
    global OfflineLearningLoop, KnowledgeConsistencyVerifier
    global AutoModelSelector, CostOptimizer, MultiModelComparison
    global EnhancedPerformanceMonitor, get_offline_learning_loop

    try:
        from client.src.business.expert_learning.offline_learning_loop import (
            OfflineLearningLoop, get_offline_learning_loop,
            ConnectionStatus as OfflineStatus
        )
        from client.src.business.expert_learning.knowledge_consistency import (
            KnowledgeConsistencyVerifier, ConsensusLevel, VerificationStatus
        )
        from client.src.business.expert_learning.auto_model_selector import (
            AutoModelSelector, TaskType
        )
        from client.src.business.expert_learning.cost_optimizer import (
            CostOptimizer, CostMode
        )
        from client.src.business.expert_learning.multi_model_comparison import (
            MultiModelComparison
        )
        from client.src.business.expert_learning.enhanced_performance_monitor import (

            EnhancedPerformanceMonitor, MetricType
        )
        return True
    except ImportError as e:
        logger.info(f"[IntelligentLearningSystem] 模块导入失败: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class LearningResult:
    """学习结果"""
    success: bool
    content: str
    source: str  # offline/online/verified/hybrid
    confidence: float
    metadata: Dict = field(default_factory=dict)


@dataclass
class SystemStatus:
    """系统状态"""
    is_online: bool
    connection_quality: float  # 0-1
    active_models: int
    budget_remaining: float
    system_health: float  # 0-1
    alerts_count: int


# ═══════════════════════════════════════════════════════════════════════════════
# 智能学习系统
# ═══════════════════════════════════════════════════════════════════════════════

class IntelligentLearningSystem:
    """
    智能学习系统统一入口

    整合六大核心能力：
    1. 永不掉线的离线学习
    2. 多模型一致性验证
    3. 自动模型选择
    4. 成本优化
    5. 多模型对比
    6. 性能监控

    使用方式:
    ```python
    system = IntelligentLearningSystem()

    # 处理请求（自动选择最优策略）
    result = system.process("解释量子计算原理")
    logger.info(result.content)

    # 学习新知识
    system.learn(query="...", response="...")

    # 获取系统状态
    status = system.get_status()
    logger.info(f"系统健康度: {status.system_health}")

    # 获取优化建议
    tips = system.get_optimization_tips()
    ```
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(
        self,
        config: Optional[Dict] = None,
    ):
        if self._initialized:
            return

        self._initialized = True
        self.config = config or {}

        # 尝试导入模块
        if not _import_modules():
            raise ImportError("无法导入必要的子模块")

        # ── 初始化子模块 ──────────────────────────────────────────────

        # 1. 离线学习循环
        self._offline_loop = get_offline_learning_loop()

        # 2. 知识一致性验证器
        self._consistency_verifier = KnowledgeConsistencyVerifier(
            min_models=2,
            consensus_threshold=0.6,
        )

        # 3. 自动模型选择器
        self._model_selector = AutoModelSelector(
            prefer_free=True,
            latency_budget_ms=5000,
        )

        # 4. 成本优化引擎
        self._cost_optimizer = CostOptimizer(
            default_daily=self.config.get("daily_budget", 5.0),
        )

        # 5. 多模型对比系统
        self._comparator = MultiModelComparison()

        # 6. 性能监控
        self._performance_monitor = EnhancedPerformanceMonitor(
            latency_threshold_ms=self.config.get("latency_threshold", 5000),
            quality_threshold=self.config.get("quality_threshold", 0.6),
        )

        # ── 状态 ────────────────────────────────────────────────────

        self._connection_status = "online"  # online/degraded/offline
        self._total_requests = 0

        # ── 回调 ────────────────────────────────────────────────────

        self._on_learning: Optional[Callable] = None
        self._on_optimization: Optional[Callable] = None

        logger.info("[IntelligentLearningSystem] 智能学习系统初始化完成")
        logger.info(f"  配置: {json.dumps(self.config, ensure_ascii=False)}")

    # ═══════════════════════════════════════════════════════════════════════════
    # 核心处理方法
    # ═══════════════════════════════════════════════════════════════════════════

    def process(
        self,
        query: str,
        context: Optional[Dict] = None,
        require_verification: bool = False,
        allow_online: bool = True,
    ) -> LearningResult:
        """
        处理查询（核心入口）

        策略:
        1. 首先尝试离线响应
        2. 如果需要且允许，调用在线模型
        3. 如果需要验证，进行多模型一致性检查
        4. 记录学习

        Args:
            query: 查询
            context: 上下文
            require_verification: 是否需要一致性验证
            allow_online: 是否允许使用在线模型

        Returns:
            LearningResult
        """
        self._total_requests += 1

        # ── Step 1: 离线响应 ──────────────────────────────────────

        offline_response = self._offline_loop.get_response(
            query=query,
            context=context,
            allow_learning=True,
        )

        if not offline_response.fallback_used:
            # 离线直接命中
            return LearningResult(
                success=True,
                content=offline_response.content,
                source="offline",
                confidence=offline_response.confidence,
                metadata={"match_type": offline_response.metadata.get("match_type", "unknown")},
            )

        # ── Step 2: 在线增强（如果允许）─────────────────────────────

        if allow_online:
            # 推荐模型
            recommendation = self._model_selector.recommend(query)

            # 检查预算
            budget_ok = self._cost_optimizer.can_afford(
                recommendation.primary_model.model_id,
                estimated_tokens := len(query) * 2,
                output_tokens := estimated_tokens * 2,
            )

            if budget_ok:
                # 使用模型生成
                content, quality = self._use_model(
                    recommendation.primary_model,
                    query,
                    context,
                )

                # 记录性能
                self._performance_monitor.record_request(
                    model_id=recommendation.primary_model.model_id,
                    model_name=recommendation.primary_model.model_name,
                    latency_ms=recommendation.estimated_latency_ms,
                    success=True,
                    quality_score=quality,
                )

                # 学习这个问答
                self._offline_loop.learn(
                    query=query,
                    response=content,
                    source="online",
                    confidence=quality,
                )

                # 一致性验证（如果需要）
                if require_verification:
                    verified = self._verify_response(query, content)
                    if not verified:
                        return LearningResult(
                            success=True,
                            content=content,
                            source="online_unverified",
                            confidence=quality * 0.8,
                            metadata={"verified": False},
                        )

                return LearningResult(
                    success=True,
                    content=content,
                    source="online",
                    confidence=quality,
                    metadata={"model": recommendation.primary_model.model_name},
                )

        # ── Step 3: 返回离线响应 ────────────────────────────────────

        return LearningResult(
            success=True,
            content=offline_response.content,
            source="offline_fallback",
            confidence=offline_response.confidence,
            metadata={"fallback": True},
        )

    def _use_model(
        self,
        model: Any,
        query: str,
        context: Optional[Dict],
    ) -> tuple:
        """使用模型生成响应"""
        # 简化实现：实际使用时调用真实的模型客户端
        return f"[{model.model_name}]: {query}", 0.8

    def _verify_response(self, query: str, content: str) -> bool:
        """验证响应"""
        result = self._consistency_verifier.quick_check(query, content)
        return result.get("estimated_confidence", 0.5) >= 0.6

    # ═══════════════════════════════════════════════════════════════════════════
    # 学习方法
    # ═══════════════════════════════════════════════════════════════════════════

    def learn(
        self,
        query: str,
        response: str,
        source: str = "manual",
        quality: float = 0.8,
    ):
        """学习新知识"""
        self._offline_loop.learn(
            query=query,
            response=response,
            source=source,
            confidence=quality,
        )

        if self._on_learning:
            self._on_learning(query, response)

    def learn_batch(self, knowledge_pairs: List[Dict]):
        """批量学习"""
        for item in knowledge_pairs:
            self.learn(
                query=item["query"],
                response=item["response"],
                source=item.get("source", "batch"),
                quality=item.get("quality", 0.8),
            )

    # ═══════════════════════════════════════════════════════════════════════════
    # 模型管理
    # ═══════════════════════════════════════════════════════════════════════════

    def register_model(
        self,
        model_id: str,
        model_name: str,
        client: Any,
        capabilities: Dict,
    ):
        """注册模型到所有相关模块"""
        # 自动选择器
        self._model_selector.register_model(model_id, model_name, capabilities)

        # 知识一致性验证
        self._consistency_verifier.register_model(model_id, model_name, client)

        # 多模型对比
        self._comparator.add_model(model_id, model_name, client)

        # 成本优化
        if capabilities.get("cost_per_1k_tokens", 0) == 0:
            self._cost_optimizer.register_free_model(model_id)
        else:
            self._cost_optimizer.set_pricing(
                model_id,
                capabilities.get("input_cost", 0),
                capabilities.get("output_cost", 0),
            )

        logger.info(f"[IntelligentLearningSystem] 模型注册完成: {model_name}")

    def set_connection_status(self, status: str):
        """设置连接状态"""
        self._connection_status = status

        if status == "offline":
            self._offline_loop.set_connection_status(OfflineStatus.OFFLINE)
        elif status == "degraded":
            self._offline_loop.set_connection_status(OfflineStatus.DEGRADED)
        else:
            self._offline_loop.set_connection_status(OfflineStatus.ONLINE)

    # ═══════════════════════════════════════════════════════════════════════════
    # 查询方法
    # ═══════════════════════════════════════════════════════════════════════════

    def get_status(self) -> SystemStatus:
        """获取系统状态"""
        # 预算状态
        budget = self._cost_optimizer.get_budget_status("daily")

        # 健康状态
        report = self._performance_monitor.get_report(period="1h")

        # 在线状态
        is_online = self._connection_status == "online"

        return SystemStatus(
            is_online=is_online,
            connection_quality=1.0 if is_online else 0.3,
            active_models=len(self._model_selector.get_model_list()),
            budget_remaining=budget.remaining,
            system_health=report.overall_health,
            alerts_count=len(report.alerts),
        )

    def get_stats(self) -> Dict:
        """获取详细统计"""
        return {
            "total_requests": self._total_requests,
            "offline_loop": self._offline_loop.get_stats(),
            "consistency": self._consistency_verifier.get_stats(),
            "model_selector": self._model_selector.get_stats(),
            "cost_optimizer": self._cost_optimizer.get_stats(),
            "comparator": self._comparator.get_stats(),
            "performance_monitor": self._performance_monitor.get_stats(),
        }

    def get_optimization_tips(self) -> List[str]:
        """获取优化建议"""
        tips = []

        # 成本优化建议
        tips.extend(self._cost_optimizer.get_optimization_tips())

        # 性能建议
        report = self._performance_monitor.get_report(period="1h")
        tips.extend(report.recommendations)

        # 离线学习建议
        kb_stats = self._offline_loop.get_knowledge_stats()
        if kb_stats["utilization_pct"] < 30:
            tips.append("知识库利用率较低，可以导入更多知识提升离线能力")

        return tips

    # ═══════════════════════════════════════════════════════════════════════════
    # 高级功能
    # ═══════════════════════════════════════════════════════════════════════════

    def compare_models(
        self,
        query: str,
        model_ids: Optional[List[str]] = None,
    ) -> Dict:
        """对比多个模型"""
        result = self._comparator.compare(query, model_ids)
        return {
            "best_model": result.best_model,
            "rankings": result.rankings,
            "differences": result.differences,
            "consensus": result.consensus_summary,
            "report": self._comparator.generate_report(result),
        }

    def verify_knowledge(
        self,
        query: str,
        answer: str,
    ) -> Dict:
        """验证知识一致性"""
        result = self._consistency_verifier.quick_check(query, answer)
        return {
            "estimated_confidence": result["estimated_confidence"],
            "extracted_facts": result["extracted_facts"],
            "fact_count": result["fact_count"],
        }

    def get_cost_report(self, period: str = "weekly") -> Dict:
        """获取成本报告"""
        return self._cost_optimizer.get_savings_report(period)

    def get_performance_report(self, period: str = "1h") -> Dict:
        """获取性能报告"""
        report = self._performance_monitor.get_report(period=period)
        return {
            "period": report.period,
            "total_requests": report.total_requests,
            "overall_health": report.overall_health,
            "models": [
                {
                    "model_id": p.model_id,
                    "avg_latency": p.avg_latency_ms,
                    "error_rate": p.error_rate,
                    "health": p.health_score,
                }
                for p in report.model_performances
            ],
            "alerts": [
                {"type": a.alert_type, "message": a.message, "severity": a.severity}
                for a in report.alerts
            ],
            "recommendations": report.recommendations,
        }

    def search_knowledge(self, query: str, limit: int = 10) -> List[Dict]:
        """搜索本地知识"""
        results = self._offline_loop.search_knowledge(query, limit=limit)
        return [
            {
                "query": r.query_pattern,
                "response": r.response,
                "confidence": r.confidence,
                "success_rate": r.success_rate,
            }
            for r in results
        ]

    # ═══════════════════════════════════════════════════════════════════════════
    # 回调设置
    # ═══════════════════════════════════════════════════════════════════════════

    def set_callbacks(
        self,
        on_learning: Callable = None,
        on_optimization: Callable = None,
    ):
        """设置回调"""
        self._on_learning = on_learning
        self._on_optimization = on_optimization


# ═══════════════════════════════════════════════════════════════════════════════
# 单例访问
# ═══════════════════════════════════════════════════════════════════════════════

_intelligent_system: Optional[IntelligentLearningSystem] = None


def get_intelligent_learning_system(config: Optional[Dict] = None) -> IntelligentLearningSystem:
    """获取智能学习系统实例"""
    global _intelligent_system
    if _intelligent_system is None:
        _intelligent_system = IntelligentLearningSystem(config)
    return _intelligent_system


# ═══════════════════════════════════════════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logger.info("=" * 70)
    logger.info("智能学习系统统一入口测试")
    logger.info("=" * 70)

    try:
        system = get_intelligent_learning_system({"daily_budget": 5.0})

        logger.info("\n[Test 1: 处理查询]")
        result = system.process("你好")
        logger.info(f"  来源: {result.source}")
        logger.info(f"  置信度: {result.confidence:.2f}")
        logger.info(f"  内容: {result.content[:50]}...")

        logger.info("\n[Test 2: 学习新知识]")
        system.learn("Python是什么", "Python是一种高级编程语言...", source="expert", quality=0.9)
        logger.info("  知识已学习")

        logger.info("\n[Test 3: 搜索知识]")
        results = system.search_knowledge("Python")
        logger.info(f"  找到 {len(results)} 条相关知识")

        logger.info("\n[Test 4: 系统状态]")
        status = system.get_status()
        logger.info(f"  在线: {status.is_online}")
        logger.info(f"  健康度: {status.system_health:.2f}")
        logger.info(f"  预算剩余: ${status.budget_remaining:.2f}")

        logger.info("\n[Test 5: 优化建议]")
        tips = system.get_optimization_tips()
        for tip in tips:
            logger.info(f"  • {tip}")

        logger.info("\n[Test 6: 详细统计]")
        stats = system.get_stats()
        logger.info(f"  总请求: {stats['total_requests']}")
        logger.info(f"  离线知识: {stats['offline_loop']['knowledge_stats']['total_fragments']}")
        logger.info(f"  注册模型: {stats['model_selector']['registered_models']}")

    except ImportError as e:
        logger.info(f"\n测试跳过（模块未完全安装）: {e}")
    except Exception as e:
        logger.info(f"\n测试失败: {e}")

    logger.info("\n" + "=" * 70)
