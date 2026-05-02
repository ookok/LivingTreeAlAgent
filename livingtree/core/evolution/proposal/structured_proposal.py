"""
Structured Proposal - 结构化进化提案定义
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid


class ProposalType(Enum):
    """提案类型"""
    PERFORMANCE = "performance"           # 性能优化
    ARCHITECTURE = "architecture"        # 架构重构
    CODE_QUALITY = "code_quality"        # 代码质量
    REFACTORING = "refactoring"          # 重构
    SECURITY = "security"                # 安全加固
    TESTING = "testing"                  # 测试增强
    DOCUMENTATION = "documentation"      # 文档完善
    UNKNOWN = "unknown"                   # 未知类型


class ProposalPriority(Enum):
    """提案优先级"""
    CRITICAL = "critical"    # P0 - 必须立即处理
    HIGH = "high"            # P1 - 高优先级
    MEDIUM = "medium"       # P2 - 中优先级
    LOW = "low"             # P3 - 低优先级
    INFO = "info"           # P4 - 信息级


class ProposalStatus(Enum):
    """提案状态"""
    PENDING = "pending"      # 待处理
    APPROVED = "approved"   # 已批准
    REJECTED = "rejected"   # 已拒绝
    EXECUTING = "executing" # 执行中
    COMPLETED = "completed" # 已完成
    FAILED = "failed"       # 执行失败


class RiskLevel(Enum):
    """风险等级"""
    NONE = "none"           # 无风险
    LOW = "low"            # 低风险
    MEDIUM = "medium"      # 中风险
    HIGH = "high"          # 高风险
    CRITICAL = "critical" # 极高风险


@dataclass
class TriggerSignal:
    """触发信号"""
    sensor_type: str
    signal_type: str
    severity: float          # 严重程度 0-1
    evidence: Dict[str, Any] # 证据数据
    location: Optional[str] = None  # 位置（如文件路径）
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sensor_type": self.sensor_type,
            "signal_type": self.signal_type,
            "severity": self.severity,
            "evidence": self.evidence,
            "location": self.location,
        }


@dataclass
class ProposalStep:
    """提案执行步骤"""
    step_id: str
    description: str
    action_type: str         # "code_change", "config_change", "refactor", "test", "review"
    target: Optional[str] = None  # 目标文件/模块
    changes: Optional[Dict[str, Any]] = None  # 具体变更
    estimated_time: Optional[str] = None  # 预估时间
    reversible: bool = True  # 是否可逆
    requires_confirmation: bool = True  # 是否需要用户确认
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "description": self.description,
            "action_type": self.action_type,
            "target": self.target,
            "changes": self.changes,
            "estimated_time": self.estimated_time,
            "reversible": self.reversible,
            "requires_confirmation": self.requires_confirmation,
        }


@dataclass
class StructuredProposal:
    """结构化进化提案"""
    proposal_id: str
    title: str
    description: str
    proposal_type: ProposalType
    priority: ProposalPriority
    
    # 触发信号
    signals: List[TriggerSignal] = field(default_factory=list)
    
    # 收益评估
    estimated_benefits: Dict[str, Any] = field(default_factory=dict)
    estimated_risk: RiskLevel = RiskLevel.LOW
    
    # 执行步骤
    steps: List[ProposalStep] = field(default_factory=list)
    
    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    project_root: Optional[str] = None
    
    # 状态
    status: ProposalStatus = ProposalStatus.PENDING
    approved_by: Optional[str] = None
    executed_at: Optional[datetime] = None
    
    # 执行结果
    execution_result: Optional[Dict[str, Any]] = None
    
    @classmethod
    def create(
        cls,
        title: str,
        description: str,
        proposal_type: ProposalType,
        priority: ProposalPriority,
        signals: List[TriggerSignal],
        estimated_benefits: Dict[str, Any],
        estimated_risk: RiskLevel = RiskLevel.LOW,
        steps: List[ProposalStep] = None,
        project_root: str = None,
    ) -> "StructuredProposal":
        """创建提案工厂方法"""
        proposal_id = f"prop_{uuid.uuid4().hex[:12]}"
        
        return cls(
            proposal_id=proposal_id,
            title=title,
            description=description,
            proposal_type=proposal_type,
            priority=priority,
            signals=signals,
            estimated_benefits=estimated_benefits,
            estimated_risk=estimated_risk,
            steps=steps or [],
            project_root=project_root,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "proposal_id": self.proposal_id,
            "title": self.title,
            "description": self.description,
            "proposal_type": self.proposal_type.value,
            "priority": self.priority.value,
            "signals": [s.to_dict() for s in self.signals],
            "estimated_benefits": self.estimated_benefits,
            "estimated_risk": self.estimated_risk.value,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "project_root": self.project_root,
            "status": self.status.value,
            "approved_by": self.approved_by,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "execution_result": self.execution_result,
        }
    
    def add_step(self, step: ProposalStep) -> None:
        """添加执行步骤"""
        self.steps.append(step)
        self.updated_at = datetime.now()
    
    def get_summary(self) -> str:
        """获取提案摘要"""
        signal_count = len(self.signals)
        step_count = len(self.steps)
        return f"[{self.priority.value.upper()}] {self.title} ({signal_count} signals, {step_count} steps)"
    
    def get_risk_emoji(self) -> str:
        """获取风险表情"""
        risk_emoji_map = {
            RiskLevel.NONE: "✅",
            RiskLevel.LOW: "🟢",
            RiskLevel.MEDIUM: "🟡",
            RiskLevel.HIGH: "🟠",
            RiskLevel.CRITICAL: "🔴",
        }
        return risk_emoji_map.get(self.estimated_risk, "❓")
