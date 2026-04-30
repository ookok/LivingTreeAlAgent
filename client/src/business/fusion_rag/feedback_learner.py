"""
负反馈学习模块 (Feedback Learner)

实现系统持续进化的核心机制：
1. 记录被用户标记为"不相关"的 Query-Result 对
2. 分析原因：术语歧义、来源不准、场景错配
3. 反向调整检索权重或补充同义词表
4. 专家知识注入：允许手动"钉选"关键文档

核心原则：让系统越用越专业

集成共享基础设施：
- 事件总线：发布反馈记录事件，触发增量训练
"""

import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime

# 导入共享基础设施
from business.shared import (
    EventBus,
    get_event_bus,
    EVENTS
)


@dataclass
class FeedbackRecord:
    """反馈记录"""
    query: str
    result_id: str
    result_content: str
    feedback_type: str  # "irrelevant", "relevant", "uncertain"
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    user_id: Optional[str] = None
    context: Optional[str] = None


@dataclass
class LearningInsight:
    """学习洞察"""
    insight_type: str  # "term_ambiguity", "source_issue", "scenario_mismatch", "synonym_needed"
    query: str
    problematic_term: Optional[str] = None
    suggested_fix: Optional[str] = None
    confidence: float = 0.0


@dataclass
class PinnedDocument:
    """钉选文档"""
    doc_id: str
    title: str
    scenarios: List[str]
    priority: int = 1  # 1-5, higher = more important
    pinned_by: str = "system"
    pinned_at: datetime = field(default_factory=datetime.now)


class FeedbackLearner:
    """
    负反馈学习器
    
    实现：
    1. 记录用户反馈
    2. 分析反馈原因
    3. 生成学习洞察
    4. 应用学习到的知识
    5. 支持专家手动钉选
    
    集成共享基础设施：
    - 事件总线：发布反馈记录事件，触发增量训练
    """
    
    def __init__(self):
        # 获取共享基础设施
        self.event_bus = get_event_bus()
        
        # 反馈记录
        self.feedback_records: List[FeedbackRecord] = []
        
        # 钉选文档
        self.pinned_docs: Dict[str, PinnedDocument] = {}
        
        # 学习到的同义词（从反馈中自动发现）
        self.learned_synonyms: Dict[str, Dict[str, int]] = {}  # industry -> {alias: count}
        
        # 学习到的权重调整
        self.learned_weights: Dict[str, float] = {}  # source_type -> weight_adjustment
        
        # 反馈原因统计
        self.feedback_reasons: Dict[str, int] = {}
        
        # 统计
        self.total_feedback = 0
        self.irrelevant_count = 0
        self.relevant_count = 0
        self.learning_count = 0
        
        print("[FeedbackLearner] 初始化完成")
    
    def record_feedback(self, query: str, result_id: str, result_content: str,
                       feedback_type: str, reason: str = "", user_id: Optional[str] = None,
                       context: Optional[str] = None):
        """
        记录用户反馈
        
        Args:
            query: 用户查询
            result_id: 结果文档ID
            result_content: 结果内容
            feedback_type: 反馈类型 ("irrelevant", "relevant", "uncertain")
            reason: 反馈原因
            user_id: 用户ID
            context: 上下文信息
        """
        record = FeedbackRecord(
            query=query,
            result_id=result_id,
            result_content=result_content,
            feedback_type=feedback_type,
            reason=reason,
            user_id=user_id,
            context=context
        )
        
        self.feedback_records.append(record)
        self.total_feedback += 1
        
        if feedback_type == "irrelevant":
            self.irrelevant_count += 1
            # 分析原因并学习
            insights = self._analyze_and_learn(record)
        elif feedback_type == "relevant":
            self.relevant_count += 1
            insights = []
        
        # 更新原因统计
        if reason:
            self.feedback_reasons[reason] = self.feedback_reasons.get(reason, 0) + 1
        
        # 发布反馈记录事件
        self._publish_feedback_event(record, insights)
    
    def _publish_feedback_event(self, record: FeedbackRecord, insights: Optional[List] = None):
        """发布反馈记录事件"""
        event_data = {
            "query": record.query,
            "result_id": record.result_id,
            "feedback_type": record.feedback_type,
            "reason": record.reason,
            "timestamp": record.timestamp.isoformat(),
            "insights": [i.__dict__ for i in insights] if insights else []
        }
        
        self.event_bus.publish(EVENTS["FEEDBACK_RECORDED"], event_data)
        print(f"[FeedbackLearner] 发布反馈事件: {record.feedback_type}")
    
    def _analyze_and_learn(self, record: FeedbackRecord):
        """
        分析负反馈并生成学习洞察
        
        Args:
            record: 反馈记录
        """
        insights = self._analyze_feedback(record)
        
        for insight in insights:
            self._apply_insight(insight)
            self.learning_count += 1
    
    def _analyze_feedback(self, record: FeedbackRecord) -> List[LearningInsight]:
        """
        分析反馈原因
        
        Args:
            record: 反馈记录
            
        Returns:
            学习洞察列表
        """
        insights = []
        query = record.query
        content = record.result_content
        
        # 1. 检查术语歧义
        ambiguity = self._detect_term_ambiguity(query, content)
        if ambiguity:
            insights.append(LearningInsight(
                insight_type="term_ambiguity",
                query=query,
                problematic_term=ambiguity,
                suggested_fix="需要添加同义词或上下文限定",
                confidence=0.7
            ))
        
        # 2. 检查场景错配
        mismatch = self._detect_scenario_mismatch(query, content)
        if mismatch:
            insights.append(LearningInsight(
                insight_type="scenario_mismatch",
                query=query,
                suggested_fix=f"当前结果适用于{mismatch}场景，可能需要按场景过滤",
                confidence=0.6
            ))
        
        # 3. 检查来源问题
        source_issue = self._detect_source_issue(content)
        if source_issue:
            insights.append(LearningInsight(
                insight_type="source_issue",
                query=query,
                suggested_fix=f"来源可信度不足: {source_issue}",
                confidence=0.5
            ))
        
        return insights
    
    def _detect_term_ambiguity(self, query: str, content: str) -> Optional[str]:
        """
        检测术语歧义
        
        Args:
            query: 用户查询
            content: 结果内容
            
        Returns:
            可能存在歧义的术语，或 None
        """
        # 常见歧义词列表
        ambiguous_terms = [
            ("电机", ["电动机", "发电机", "马达"]),
            ("控制", ["自动控制", "手动控制", "远程控制"]),
            ("系统", ["操作系统", "控制系统", "管理系统"]),
            ("设备", ["生产设备", "检测设备", "办公设备"])
        ]
        
        query_lower = query.lower()
        content_lower = content.lower()
        
        for term, variations in ambiguous_terms:
            if term in query_lower:
                # 检查内容中是否包含不同的含义
                found_variations = [v for v in variations if v in content_lower]
                if found_variations:
                    # 判断是否匹配
                    query_has_variation = any(v in query_lower for v in variations)
                    if not query_has_variation:
                        # 查询中没有具体说明，但结果使用了特定含义
                        return term
        
        return None
    
    def _detect_scenario_mismatch(self, query: str, content: str) -> Optional[str]:
        """
        检测场景错配
        
        Args:
            query: 用户查询
            content: 结果内容
            
        Returns:
            结果适用的场景，或 None
        """
        scenario_keywords = {
            "设计": ["设计", "选型", "方案设计"],
            "维护": ["维护", "维修", "故障排除", "保养"],
            "工艺": ["工艺", "加工", "制造", "生产"],
            "安全": ["安全", "规范", "标准", "防护"],
            "检测": ["检测", "测试", "检验", "测量"]
        }
        
        query_scenarios = []
        content_scenarios = []
        
        for scenario, keywords in scenario_keywords.items():
            for keyword in keywords:
                if keyword in query:
                    query_scenarios.append(scenario)
                if keyword in content:
                    content_scenarios.append(scenario)
        
        # 如果查询和内容的场景不重叠，说明可能存在场景错配
        if query_scenarios and content_scenarios:
            if not set(query_scenarios) & set(content_scenarios):
                return ", ".join(content_scenarios)
        
        return None
    
    def _detect_source_issue(self, content: str) -> Optional[str]:
        """
        检测来源问题
        
        Args:
            content: 结果内容
            
        Returns:
            来源问题描述，或 None
        """
        # 检查是否有明显的来源标识
        if "来源：" in content or "参考：" in content:
            return None  # 有明确来源，没问题
        
        # 检查内容是否包含可疑模式
        suspicious_patterns = [
            ("论坛讨论", "论坛"),
            ("个人博客", "博客"),
            ("网友分享", "网友"),
            ("非官方", "非官方")
        ]
        
        for description, pattern in suspicious_patterns:
            if pattern in content:
                return description
        
        return None
    
    def _apply_insight(self, insight: LearningInsight):
        """
        应用学习洞察
        
        Args:
            insight: 学习洞察
        """
        if insight.insight_type == "term_ambiguity" and insight.problematic_term:
            # 记录需要添加同义词的术语
            if "general" not in self.learned_synonyms:
                self.learned_synonyms["general"] = {}
            self.learned_synonyms["general"][insight.problematic_term] = \
                self.learned_synonyms["general"].get(insight.problematic_term, 0) + 1
        
        elif insight.insight_type == "source_issue":
            # 降低不可靠来源的权重
            self.learned_weights["unverified_source"] = \
                self.learned_weights.get("unverified_source", 0) - 0.1
        
        elif insight.insight_type == "scenario_mismatch":
            # 记录需要场景过滤的查询模式
            if "scenario_needs_filter" not in self.learned_weights:
                self.learned_weights["scenario_needs_filter"] = 0
            self.learned_weights["scenario_needs_filter"] += 1
    
    def pin_document(self, doc_id: str, title: str, scenarios: List[str],
                    priority: int = 3, pinned_by: str = "expert"):
        """
        钉选文档（专家知识注入）
        
        Args:
            doc_id: 文档ID
            title: 文档标题
            scenarios: 适用场景列表
            priority: 优先级 (1-5)
            pinned_by: 钉选者
        """
        pinned = PinnedDocument(
            doc_id=doc_id,
            title=title,
            scenarios=scenarios,
            priority=min(5, max(1, priority)),
            pinned_by=pinned_by
        )
        
        self.pinned_docs[doc_id] = pinned
        print(f"[FeedbackLearner] 文档已钉选: {title}")
    
    def unpin_document(self, doc_id: str):
        """取消钉选文档"""
        if doc_id in self.pinned_docs:
            del self.pinned_docs[doc_id]
    
    def get_pinned_docs(self, scenario: Optional[str] = None) -> List[PinnedDocument]:
        """
        获取钉选文档
        
        Args:
            scenario: 场景过滤（可选）
            
        Returns:
            钉选文档列表
        """
        docs = list(self.pinned_docs.values())
        
        if scenario:
            docs = [d for d in docs if scenario in d.scenarios]
        
        # 按优先级排序
        docs.sort(key=lambda x: x.priority, reverse=True)
        
        return docs
    
    def should_prioritize(self, doc_id: str) -> Tuple[bool, int]:
        """
        检查文档是否应该优先召回
        
        Args:
            doc_id: 文档ID
            
        Returns:
            (should_prioritize, priority)
        """
        if doc_id in self.pinned_docs:
            return (True, self.pinned_docs[doc_id].priority)
        return (False, 0)
    
    def get_suggested_synonyms(self, industry: str = "general", min_count: int = 2) -> List[str]:
        """
        获取建议添加的同义词
        
        Args:
            industry: 行业
            min_count: 最小出现次数
            
        Returns:
            建议添加的术语列表
        """
        synonyms = self.learned_synonyms.get(industry, {})
        return [term for term, count in synonyms.items() if count >= min_count]
    
    def get_learning_insights(self) -> Dict[str, Any]:
        """获取学习洞察汇总"""
        return {
            "total_feedback": self.total_feedback,
            "irrelevant_count": self.irrelevant_count,
            "relevant_count": self.relevant_count,
            "learning_count": self.learning_count,
            "suggested_synonyms": self.get_suggested_synonyms(),
            "feedback_reasons": dict(self.feedback_reasons),
            "pinned_doc_count": len(self.pinned_docs),
            "learned_weights": dict(self.learned_weights)
        }
    
    def export_feedback_data(self) -> str:
        """导出反馈数据为JSON"""
        records = []
        for record in self.feedback_records:
            records.append({
                "query": record.query,
                "result_id": record.result_id,
                "feedback_type": record.feedback_type,
                "reason": record.reason,
                "timestamp": record.timestamp.isoformat()
            })
        
        return json.dumps(records, ensure_ascii=False, indent=2)
    
    def import_feedback_data(self, json_data: str):
        """从JSON导入反馈数据"""
        try:
            records = json.loads(json_data)
            for record in records:
                self.record_feedback(
                    query=record["query"],
                    result_id=record["result_id"],
                    result_content="",
                    feedback_type=record["feedback_type"],
                    reason=record.get("reason", "")
                )
            print(f"[FeedbackLearner] 导入了 {len(records)} 条反馈记录")
        except Exception as e:
            print(f"[FeedbackLearner] 导入失败: {e}")


def create_feedback_learner() -> FeedbackLearner:
    """创建反馈学习器实例"""
    return FeedbackLearner()


__all__ = [
    "FeedbackLearner",
    "FeedbackRecord",
    "LearningInsight",
    "PinnedDocument",
    "create_feedback_learner"
]