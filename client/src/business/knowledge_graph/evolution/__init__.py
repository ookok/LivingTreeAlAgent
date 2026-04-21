"""
持续学习与优化模块
==================

核心循环：
用户使用 → 生成结果 → 专家审核 → 收集反馈
    ↓          ↓          ↓          ↓
日志记录 → 质量评估 → 问题标注 → 模型优化

Author: Hermes Desktop Team
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
import json

from .. import KnowledgeGraph, Entity, Relation, KnowledgeSource


# ============================================================
# 第一部分：反馈类型和配置
# ============================================================

class FeedbackType(Enum):
    """反馈类型"""
    CORRECTION = "correction"      # 纠正
    ADDITION = "addition"         # 补充
    DELETION = "deletion"         # 删除
    RATING = "rating"             # 评分
    COMMENT = "comment"           # 评论


class FeedbackSource(Enum):
    """反馈来源"""
    USER = "user"                 # 用户
    EXPERT = "expert"            # 专家
    SYSTEM = "system"            # 系统
    AI_REVIEW = "ai_review"      # AI审核


@dataclass
class Feedback:
    """反馈"""
    id: str
    feedback_type: FeedbackType
    source: FeedbackSource
    target_id: str  # 关联的实体或关系ID
    content: Any    # 反馈内容
    timestamp: datetime = field(default_factory=datetime.now)
    validated: bool = False
    applied: bool = False


@dataclass
class QualityMetrics:
    """质量指标"""
    accuracy: float = 0.0        # 准确率
    completeness: float = 0.0    # 完整性
    consistency: float = 0.0     # 一致性
    timeliness: float = 0.0      # 时效性
    overall_score: float = 0.0   # 综合得分

    def to_dict(self) -> Dict:
        return {
            "accuracy": self.accuracy,
            "completeness": self.completeness,
            "consistency": self.consistency,
            "timeliness": self.timeliness,
            "overall_score": self.overall_score
        }


# ============================================================
# 第二部分：使用日志
# ============================================================

@dataclass
class UsageLog:
    """使用日志"""
    id: str
    user_id: str
    action: str  # query/generate/export
    input_data: Dict
    output_data: Dict
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: int = 0
    success: bool = True
    error_message: str = ""


class UsageLogger:
    """使用日志记录器"""

    def __init__(self, max_logs: int = 10000):
        self.max_logs = max_logs
        self._logs: List[UsageLog] = []

    def log(self, user_id: str, action: str, input_data: Dict,
            output_data: Dict, duration_ms: int = 0,
            success: bool = True, error: str = "") -> None:
        """记录使用日志"""
        import uuid
        log = UsageLog(
            id=str(uuid.uuid4()),
            user_id=user_id,
            action=action,
            input_data=input_data,
            output_data=output_data,
            duration_ms=duration_ms,
            success=success,
            error_message=error
        )
        self._logs.append(log)

        # 淘汰旧日志
        if len(self._logs) > self.max_logs:
            self._logs = self._logs[-self.max_logs:]

    def get_logs(self, user_id: Optional[str] = None,
                 action: Optional[str] = None,
                 limit: int = 100) -> List[UsageLog]:
        """获取日志"""
        results = self._logs

        if user_id:
            results = [l for l in results if l.user_id == user_id]
        if action:
            results = [l for l in results if l.action == action]

        return results[-limit:]

    def get_statistics(self) -> Dict:
        """获取统计信息"""
        if not self._logs:
            return {}

        total = len(self._logs)
        success = sum(1 for l in self._logs if l.success)
        avg_duration = sum(l.duration_ms for l in self._logs) / total if total > 0 else 0

        actions = {}
        for l in self._logs:
            actions[l.action] = actions.get(l.action, 0) + 1

        return {
            "total_uses": total,
            "success_rate": success / total if total > 0 else 0,
            "avg_duration_ms": avg_duration,
            "action_breakdown": actions
        }


# ============================================================
# 第三部分：反馈收集器
# ============================================================

class FeedbackCollector:
    """反馈收集器"""

    def __init__(self):
        self._feedbacks: List[Feedback] = []

    def add_feedback(self, feedback_type: FeedbackType, source: FeedbackSource,
                    target_id: str, content: Any) -> str:
        """添加反馈"""
        import uuid
        fb = Feedback(
            id=str(uuid.uuid4()),
            feedback_type=feedback_type,
            source=source,
            target_id=target_id,
            content=content
        )
        self._feedbacks.append(fb)
        return fb.id

    def get_feedbacks(self, target_id: Optional[str] = None,
                     source: Optional[FeedbackSource] = None,
                     feedback_type: Optional[FeedbackType] = None) -> List[Feedback]:
        """获取反馈"""
        results = self._feedbacks

        if target_id:
            results = [f for f in results if f.target_id == target_id]
        if source:
            results = [f for f in results if f.source == source]
        if feedback_type:
            results = [f for f in results if f.feedback_type == feedback_type]

        return results

    def get_unvalidated_feedbacks(self) -> List[Feedback]:
        """获取未验证的反馈"""
        return [f for f in self._feedbacks if not f.validated]

    def validate_feedback(self, feedback_id: str, validated: bool = True) -> None:
        """验证反馈"""
        for fb in self._feedbacks:
            if fb.id == feedback_id:
                fb.validated = validated
                break

    def get_statistics(self) -> Dict:
        """获取反馈统计"""
        if not self._feedbacks:
            return {}

        by_type = {}
        by_source = {}
        validated_count = sum(1 for f in self._feedbacks if f.validated)

        for f in self._feedbacks:
            by_type[f.feedback_type.value] = by_type.get(f.feedback_type.value, 0) + 1
            by_source[f.feedback_source.value] = by_source.get(f.feedback_source.value, 0) + 1

        return {
            "total_feedbacks": len(self._feedbacks),
            "validated": validated_count,
            "by_type": by_type,
            "by_source": by_source
        }


# ============================================================
# 第四部分：知识验证器
# ============================================================

class ExpertValidator:
    """专家验证器"""

    def __init__(self):
        self._validation_rules = []

    def add_rule(self, name: str, check_func: Callable, suggestion: str) -> None:
        """添加验证规则"""
        self._validation_rules.append({
            "name": name,
            "check": check_func,
            "suggestion": suggestion
        })

    def validate(self, kg: KnowledgeGraph) -> Dict[str, List[str]]:
        """验证知识图谱"""
        issues = {}

        for rule in self._validation_rules:
            try:
                result = rule["check"](kg)
                if result is not None:
                    if isinstance(result, list):
                        for issue in result:
                            if rule["name"] not in issues:
                                issues[rule["name"]] = []
                            issues[rule["name"]].append(issue)
                    elif result:
                        if rule["name"] not in issues:
                            issues[rule["name"]] = []
                        issues[rule["name"]].append(rule["suggestion"])
            except Exception as e:
                print(f"验证规则执行失败 {rule['name']}: {e}")

        return issues

    def validate_entity(self, entity: Entity) -> List[str]:
        """验证单个实体"""
        issues = []

        # 检查必填字段
        if not entity.name:
            issues.append("实体缺少名称")

        # 检查描述
        if not entity.description and not entity.properties:
            issues.append("实体缺少描述或属性")

        # 检查工艺参数合理性
        if hasattr(entity, 'temperature') and entity.temperature:
            if entity.temperature > 1500 or entity.temperature < -100:
                issues.append(f"工艺温度异常: {entity.temperature}℃")

        if hasattr(entity, 'pressure') and entity.pressure:
            if entity.pressure > 50 or entity.pressure < -0.05:
                issues.append(f"工艺压力异常: {entity.pressure}MPa")

        return issues


# ============================================================
# 第五部分：知识融合器
# ============================================================

class KnowledgeFusion:
    """知识融合器"""

    def __init__(self, strategy: str = "confidence"):
        self.strategy = strategy

    def fuse(self, kg1: KnowledgeGraph, kg2: KnowledgeGraph) -> KnowledgeGraph:
        """融合两个知识图谱"""
        fused = KnowledgeGraph(
            name=f"{kg1.name} + {kg2.name}",
            description="融合后的知识图谱"
        )

        # 合并实体
        for entity in list(kg1.entities.values()) + list(kg2.entities.values()):
            if entity.id not in fused.entities:
                fused.add_entity(entity)
            else:
                # 冲突解决
                existing = fused.entities[entity.id]
                if self.strategy == "confidence":
                    if entity.confidence > existing.confidence:
                        fused.entities[entity.id] = entity
                elif self.strategy == "newer":
                    if entity.updated_at > existing.updated_at:
                        fused.entities[entity.id] = entity

        # 合并关系
        for relation in list(kg1.relations.values()) + list(kg2.relations.values()):
            if relation.id not in fused.relations:
                fused.add_relation(relation)

        return fused

    def resolve_conflict(self, e1: Entity, e2: Entity) -> Entity:
        """解决实体冲突"""
        if self.strategy == "confidence":
            return e1 if e1.confidence > e2.confidence else e2
        elif self.strategy == "newer":
            return e1 if e1.updated_at > e2.updated_at else e2
        else:
            # 默认保留第一个
            return e1


# ============================================================
# 第六部分：版本管理器
# ============================================================

@dataclass
class KnowledgeVersion:
    """知识版本"""
    version: str
    timestamp: datetime
    kg_snapshot: Dict  # 知识图谱序列化
    changes_summary: str
    feedback_count: int


class VersionManager:
    """版本管理器"""

    def __init__(self):
        self._versions: List[KnowledgeVersion] = []
        self._current_version: str = "1.0.0"

    def create_version(self, kg: KnowledgeGraph, changes_summary: str,
                      feedback_count: int) -> KnowledgeVersion:
        """创建新版本"""
        import uuid
        version = KnowledgeVersion(
            version=self._next_version(),
            timestamp=datetime.now(),
            kg_snapshot=kg.to_dict(),
            changes_summary=changes_summary,
            feedback_count=feedback_count
        )
        self._versions.append(version)
        self._current_version = version.version
        return version

    def _next_version(self) -> str:
        """生成下一个版本号"""
        parts = self._current_version.split('.')
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
        patch += 1
        if patch > 9:
            minor += 1
            patch = 0
        if minor > 9:
            major += 1
            minor = 0
        return f"{major}.{minor}.{patch}"

    def get_version(self, version: str) -> Optional[KnowledgeVersion]:
        """获取指定版本"""
        for v in self._versions:
            if v.version == version:
                return v
        return None

    def get_latest_version(self) -> Optional[KnowledgeVersion]:
        """获取最新版本"""
        return self._versions[-1] if self._versions else None

    def list_versions(self) -> List[Dict]:
        """列出所有版本"""
        return [
            {
                "version": v.version,
                "timestamp": v.timestamp.isoformat(),
                "changes_summary": v.changes_summary,
                "feedback_count": v.feedback_count
            }
            for v in reversed(self._versions)
        ]

    def restore_version(self, version: str) -> Optional[KnowledgeGraph]:
        """恢复指定版本"""
        v = self.get_version(version)
        if v:
            return KnowledgeGraph.from_dict(v.kg_snapshot)
        return None


# ============================================================
# 第七部分：持续学习引擎
# ============================================================

class EvolutionEngine:
    """持续学习引擎"""

    def __init__(self):
        self.usage_logger = UsageLogger()
        self.feedback_collector = FeedbackCollector()
        self.validator = ExpertValidator()
        self.fusion = KnowledgeFusion()
        self.version_manager = VersionManager()

        # 设置默认验证规则
        self._setup_default_rules()

    def _setup_default_rules(self) -> None:
        """设置默认验证规则"""

        # 规则1：检查孤立实体
        def check_isolated_entities(kg: KnowledgeGraph) -> List[str]:
            issues = []
            for entity in kg.entities.values():
                has_relation = any(
                    r.source_id == entity.id or r.target_id == entity.id
                    for r in kg.relations.values()
                )
                if not has_relation and len(kg.entities) > 1:
                    issues.append(f"孤立实体: {entity.name}")
            return issues

        self.validator.add_rule(
            "孤立实体检查",
            check_isolated_entities,
            "考虑删除孤立实体或添加关联关系"
        )

        # 规则2：检查工艺链完整性
        def check_process_chain(kg: KnowledgeGraph) -> List[str]:
            issues = []
            processes = [e for e in kg.entities.values()
                        if e.entity_type.value == "Process"]
            for p in processes:
                has_predecessor = any(
                    r.target_id == p.id and r.relation_type.value == "precedes"
                    for r in kg.relations.values()
                )
                has_successor = any(
                    r.source_id == p.id and r.relation_type.value == "succeeds"
                    for r in kg.relations.values()
                )
                if not has_predecessor and not has_successor and len(processes) > 1:
                    issues.append(f"工艺链孤立: {p.name}")
            return issues

        self.validator.add_rule(
            "工艺链完整性",
            check_process_chain,
            "确保工艺按顺序连接"
        )

    def record_usage(self, user_id: str, action: str, input_data: Dict,
                    output_data: Dict, duration_ms: int = 0,
                    success: bool = True, error: str = "") -> None:
        """记录使用"""
        self.usage_logger.log(user_id, action, input_data, output_data,
                             duration_ms, success, error)

    def collect_feedback(self, feedback_type: FeedbackType, source: FeedbackSource,
                        target_id: str, content: Any) -> str:
        """收集反馈"""
        return self.feedback_collector.add_feedback(
            feedback_type, source, target_id, content
        )

    def validate_knowledge(self, kg: KnowledgeGraph) -> Dict[str, List[str]]:
        """验证知识"""
        return self.validator.validate(kg)

    def evolve(self, current_kg: KnowledgeGraph,
              new_data: Optional[KnowledgeGraph] = None) -> KnowledgeGraph:
        """
        知识图谱进化

        流程：
        1. 收集反馈
        2. 验证知识
        3. 融合新知识
        4. 创建新版本
        """
        # 1. 验证现有知识
        issues = self.validate_knowledge(current_kg)
        print(f"验证发现 {sum(len(v) for v in issues.values())} 个问题")

        # 2. 应用反馈
        feedback_count = len(self.feedback_collector.get_feedbacks())
        print(f"收集到 {feedback_count} 条反馈")

        # 3. 融合新数据
        if new_data:
            current_kg = self.fusion.fuse(current_kg, new_data)
            print(f"融合了 {len(new_data.entities)} 个新实体")

        # 4. 创建新版本
        changes = f"验证修复{sum(len(v) for v in issues.values())}项，反馈融合{feedback_count}条"
        self.version_manager.create_version(current_kg, changes, feedback_count)

        return current_kg

    def get_statistics(self) -> Dict:
        """获取统计信息"""
        return {
            "usage": self.usage_logger.get_statistics(),
            "feedback": self.feedback_collector.get_statistics(),
            "versions": self.version_manager.list_versions()
        }

    def get_quality_metrics(self, kg: KnowledgeGraph) -> QualityMetrics:
        """计算质量指标"""
        metrics = QualityMetrics()

        # 准确性：基于置信度
        if kg.entities:
            avg_confidence = sum(e.confidence for e in kg.entities.values()) / len(kg.entities)
            metrics.accuracy = avg_confidence

        # 完整性：基于关系覆盖率
        entity_count = len(kg.entities)
        relation_count = len(kg.relations)
        expected_relations = entity_count * 2  # 粗略估计
        metrics.completeness = min(1.0, relation_count / expected_relations) if expected_relations > 0 else 0

        # 一致性：基于验证结果
        issues = self.validate_knowledge(kg)
        issue_count = sum(len(v) for v in issues.values())
        metrics.consistency = max(0, 1 - issue_count / 20)  # 假设20个问题为0分

        # 时效性：基于更新时间
        if kg.entities:
            latest = max(e.updated_at for e in kg.entities.values())
            age_days = (datetime.now() - latest).days
            metrics.timeliness = max(0, 1 - age_days / 30)  # 30天为0分

        # 综合得分
        metrics.overall_score = (
            metrics.accuracy * 0.3 +
            metrics.completeness * 0.3 +
            metrics.consistency * 0.2 +
            metrics.timeliness * 0.2
        )

        return metrics


# ============================================================
# 第八部分：主控制器
# ============================================================

class KnowledgeGraphSystem:
    """知识图谱系统主控制器"""

    def __init__(self):
        self.evolution = EvolutionEngine()
        self._current_kg: Optional[KnowledgeGraph] = None

    def load_knowledge_graph(self, kg: KnowledgeGraph) -> None:
        """加载知识图谱"""
        self._current_kg = kg

    def get_current_kg(self) -> KnowledgeGraph:
        """获取当前知识图谱"""
        if self._current_kg is None:
            from .. import KnowledgeGraph
            self._current_kg = KnowledgeGraph(name="default")
        return self._current_kg

    def get_quality_report(self) -> Dict:
        """获取质量报告"""
        kg = self.get_current_kg()
        metrics = self.evolution.get_quality_metrics(kg)
        issues = self.evolution.validate_knowledge(kg)
        stats = self.evolution.get_statistics()

        return {
            "quality_metrics": metrics.to_dict(),
            "issues": issues,
            "statistics": stats
        }

    def evolve_knowledge(self, new_data: Optional[KnowledgeGraph] = None) -> None:
        """触发知识进化"""
        self._current_kg = self.evolution.evolve(self._current_kg, new_data)


__all__ = [
    'FeedbackType', 'FeedbackSource', 'Feedback',
    'QualityMetrics', 'UsageLog', 'UsageLogger',
    'FeedbackCollector', 'ExpertValidator', 'KnowledgeFusion',
    'KnowledgeVersion', 'VersionManager', 'EvolutionEngine',
    'KnowledgeGraphSystem'
]
