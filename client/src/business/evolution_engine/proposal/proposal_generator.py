"""
Proposal Generator - 提案生成器
基于传感器信号和规则模板生成结构化进化提案
"""

import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

from .structured_proposal import (
    StructuredProposal, ProposalType, ProposalPriority, 
    ProposalStatus, RiskLevel, TriggerSignal, ProposalStep
)

logger = logging.getLogger(__name__)


class ProposalTemplate:
    """提案模板"""
    
    # 性能类提案模板
    PERFORMANCE_TEMPLATES = {
        "high_latency": {
            "title": "优化高延迟操作",
            "description": "检测到响应时间超过阈值的操作，建议进行性能优化",
            "priority": ProposalPriority.HIGH,
            "estimated_risk": RiskLevel.LOW,
            "estimated_benefits": {
                "performance_gain": "20-50%",
                "user_experience": "显著提升",
            },
        },
        "memory_leak": {
            "title": "修复内存泄漏",
            "description": "检测到潜在的内存泄漏问题，可能导致长期运行后内存耗尽",
            "priority": ProposalPriority.CRITICAL,
            "estimated_risk": RiskLevel.MEDIUM,
            "estimated_benefits": {
                "stability": "防止内存耗尽崩溃",
                "resource_usage": "降低30-50%",
            },
        },
        "cpu_bottleneck": {
            "title": "优化CPU密集型操作",
            "description": "检测到CPU使用率过高的操作，建议进行算法优化或并行化",
            "priority": ProposalPriority.MEDIUM,
            "estimated_risk": RiskLevel.LOW,
            "estimated_benefits": {
                "cpu_usage": "降低30-60%",
                "throughput": "提升2-3倍",
            },
        },
    }
    
    # 架构类提案模板
    ARCHITECTURE_TEMPLATES = {
        "circular_dependency": {
            "title": "消除循环依赖",
            "description": "检测到模块间存在循环依赖，影响代码的可测试性和可维护性",
            "priority": ProposalPriority.HIGH,
            "estimated_risk": RiskLevel.HIGH,
            "estimated_benefits": {
                "maintainability": "显著提升",
                "testability": "支持单元测试",
                "decoupling": "模块解耦",
            },
        },
        "god_class": {
            "title": "拆分上帝类",
            "description": "检测到类文件过大（上帝类），建议拆分为多个职责单一的类",
            "priority": ProposalPriority.MEDIUM,
            "estimated_risk": RiskLevel.MEDIUM,
            "estimated_benefits": {
                "maintainability": "提升代码可读性",
                "reusability": "提高代码复用性",
                "testability": "便于单元测试",
            },
        },
        "deep_inheritance": {
            "title": "优化继承层次",
            "description": "检测到过深的继承层次，建议使用组合替代继承",
            "priority": ProposalPriority.MEDIUM,
            "estimated_risk": RiskLevel.LOW,
            "estimated_benefits": {
                "flexibility": "提高代码灵活性",
                "simplicity": "简化代码结构",
            },
        },
        "long_method": {
            "title": "拆分过长方法",
            "description": "检测到方法行数过多，建议拆分为多个小方法",
            "priority": ProposalPriority.LOW,
            "estimated_risk": RiskLevel.LOW,
            "estimated_benefits": {
                "readability": "提升可读性",
                "reusability": "提取可复用逻辑",
            },
        },
    }
    
    @classmethod
    def get_template(cls, category: str, signal_type: str) -> Optional[Dict[str, Any]]:
        """获取模板"""
        templates = getattr(cls, f"{category.upper()}_TEMPLATES", {})
        return templates.get(signal_type)


class ProposalGenerator:
    """提案生成器"""
    
    def __init__(self, project_root: str):
        self.project_root = project_root
        self.logger = logging.getLogger(__name__)
        
        # 阈值配置
        self.thresholds = {
            "latency_warning_ms": 1000,
            "latency_critical_ms": 3000,
            "memory_leak_rate_mb_per_hour": 10,
            "cpu_usage_warning": 0.7,
            "cpu_usage_critical": 0.9,
            "circular_dependency_threshold": 1,
            "god_class_lines": 500,
            "god_class_methods": 20,
            "inheritance_depth_warning": 4,
            "inheritance_depth_critical": 6,
            "long_method_lines": 100,
        }
    
    def generate_proposals(
        self, 
        aggregated_signals: List[Dict[str, Any]]
    ) -> List[StructuredProposal]:
        """
        从聚合信号生成提案
        
        Args:
            aggregated_signals: 聚合后的信号列表
            
        Returns:
            结构化提案列表
        """
        proposals = []
        
        for signal in aggregated_signals:
            # 根据信号类型生成提案
            sensor_type = signal.get("sensor_type", "")
            signal_type = signal.get("signal_type", "")
            severity = signal.get("severity", 0.5)
            evidence = signal.get("evidence", {})
            location = signal.get("location")
            
            # 性能类信号
            if sensor_type == "performance":
                proposal = self._generate_performance_proposal(
                    signal_type, severity, evidence, location
                )
                if proposal:
                    proposals.append(proposal)
            
            # 架构类信号
            elif sensor_type == "architecture":
                proposal = self._generate_architecture_proposal(
                    signal_type, severity, evidence, location
                )
                if proposal:
                    proposals.append(proposal)
        
        # 按优先级排序
        proposals.sort(
            key=lambda p: self._priority_sort_key(p.priority),
            reverse=True
        )
        
        self.logger.info(f"生成了 {len(proposals)} 个提案")
        return proposals
    
    def _generate_performance_proposal(
        self,
        signal_type: str,
        severity: float,
        evidence: Dict[str, Any],
        location: Optional[str],
    ) -> Optional[StructuredProposal]:
        """生成性能类提案"""
        template = ProposalTemplate.get_template("performance", signal_type)
        if not template:
            return None
        
        # 创建触发信号
        trigger_signal = TriggerSignal(
            sensor_type="performance",
            signal_type=signal_type,
            severity=severity,
            evidence=evidence,
            location=location,
        )
        
        # 根据严重程度调整优先级
        priority = template["priority"]
        if severity > 0.8:
            priority = ProposalPriority.CRITICAL
        elif severity > 0.6:
            priority = ProposalPriority.HIGH
        elif severity > 0.4:
            priority = ProposalPriority.MEDIUM
        
        # 生成执行步骤
        steps = self._generate_performance_steps(signal_type, evidence, location)
        
        # 创建提案
        proposal = StructuredProposal.create(
            title=template["title"],
            description=self._format_description(template["description"], evidence),
            proposal_type=ProposalType.PERFORMANCE,
            priority=priority,
            signals=[trigger_signal],
            estimated_benefits=template["estimated_benefits"],
            estimated_risk=template["estimated_risk"],
            steps=steps,
            project_root=self.project_root,
        )
        
        return proposal
    
    def _generate_architecture_proposal(
        self,
        signal_type: str,
        severity: float,
        evidence: Dict[str, Any],
        location: Optional[str],
    ) -> Optional[StructuredProposal]:
        """生成架构类提案"""
        template = ProposalTemplate.get_template("architecture", signal_type)
        if not template:
            return None
        
        # 创建触发信号
        trigger_signal = TriggerSignal(
            sensor_type="architecture",
            signal_type=signal_type,
            severity=severity,
            evidence=evidence,
            location=location,
        )
        
        # 根据严重程度调整优先级
        priority = template["priority"]
        if severity > 0.8:
            priority = ProposalPriority.CRITICAL
        elif severity > 0.6:
            priority = ProposalPriority.HIGH
        elif severity > 0.4:
            priority = ProposalPriority.MEDIUM
        
        # 生成执行步骤
        steps = self._generate_architecture_steps(signal_type, evidence, location)
        
        # 创建提案
        proposal = StructuredProposal.create(
            title=template["title"],
            description=self._format_description(template["description"], evidence),
            proposal_type=ProposalType.ARCHITECTURE,
            priority=priority,
            signals=[trigger_signal],
            estimated_benefits=template["estimated_benefits"],
            estimated_risk=template["estimated_risk"],
            steps=steps,
            project_root=self.project_root,
        )
        
        return proposal
    
    def _generate_performance_steps(
        self,
        signal_type: str,
        evidence: Dict[str, Any],
        location: Optional[str],
    ) -> List[ProposalStep]:
        """生成性能类执行步骤"""
        steps = []
        
        if signal_type == "high_latency":
            steps = [
                ProposalStep(
                    step_id="step_1",
                    description="分析性能瓶颈",
                    action_type="analysis",
                    target=location,
                    estimated_time="10分钟",
                    reversible=False,
                    requires_confirmation=False,
                ),
                ProposalStep(
                    step_id="step_2",
                    description="识别优化目标（缓存、算法优化、并行化）",
                    action_type="analysis",
                    target=location,
                    estimated_time="5分钟",
                    reversible=False,
                    requires_confirmation=False,
                ),
                ProposalStep(
                    step_id="step_3",
                    description="实施优化方案",
                    action_type="code_change",
                    target=location,
                    estimated_time="30分钟",
                    reversible=True,
                    requires_confirmation=True,
                ),
                ProposalStep(
                    step_id="step_4",
                    description="验证性能提升",
                    action_type="test",
                    target=location,
                    estimated_time="15分钟",
                    reversible=False,
                    requires_confirmation=False,
                ),
            ]
        
        elif signal_type == "memory_leak":
            steps = [
                ProposalStep(
                    step_id="step_1",
                    description="使用内存分析工具定位泄漏点",
                    action_type="analysis",
                    target=location,
                    estimated_time="20分钟",
                    reversible=False,
                    requires_confirmation=False,
                ),
                ProposalStep(
                    step_id="step_2",
                    description="修复内存泄漏（添加清理逻辑、弱引用等）",
                    action_type="code_change",
                    target=location,
                    estimated_time="45分钟",
                    reversible=True,
                    requires_confirmation=True,
                ),
                ProposalStep(
                    step_id="step_3",
                    description="长时间运行测试验证修复",
                    action_type="test",
                    target=location,
                    estimated_time="1小时",
                    reversible=False,
                    requires_confirmation=False,
                ),
            ]
        
        elif signal_type == "cpu_bottleneck":
            steps = [
                ProposalStep(
                    step_id="step_1",
                    description="分析CPU热点代码",
                    action_type="analysis",
                    target=location,
                    estimated_time="15分钟",
                    reversible=False,
                    requires_confirmation=False,
                ),
                ProposalStep(
                    step_id="step_2",
                    description="优化算法或添加缓存",
                    action_type="code_change",
                    target=location,
                    estimated_time="30分钟",
                    reversible=True,
                    requires_confirmation=True,
                ),
                ProposalStep(
                    step_id="step_3",
                    description="考虑并行化方案",
                    action_type="code_change",
                    target=location,
                    estimated_time="1小时",
                    reversible=True,
                    requires_confirmation=True,
                ),
            ]
        
        return steps
    
    def _generate_architecture_steps(
        self,
        signal_type: str,
        evidence: Dict[str, Any],
        location: Optional[str],
    ) -> List[ProposalStep]:
        """生成架构类执行步骤"""
        steps = []
        
        if signal_type == "circular_dependency":
            modules = evidence.get("modules", [])
            steps = [
                ProposalStep(
                    step_id="step_1",
                    description=f"分析循环依赖链: {' -> '.join(modules)}",
                    action_type="analysis",
                    target=location,
                    estimated_time="15分钟",
                    reversible=False,
                    requires_confirmation=False,
                ),
                ProposalStep(
                    step_id="step_2",
                    description="确定依赖解耦方案（接口抽象/依赖注入/重构模块）",
                    action_type="refactor",
                    target=location,
                    estimated_time="30分钟",
                    reversible=True,
                    requires_confirmation=True,
                ),
                ProposalStep(
                    step_id="step_3",
                    description="逐步消除循环依赖",
                    action_type="code_change",
                    target=location,
                    estimated_time="2-4小时",
                    reversible=True,
                    requires_confirmation=True,
                ),
                ProposalStep(
                    step_id="step_4",
                    description="运行测试确保重构正确",
                    action_type="test",
                    target=location,
                    estimated_time="30分钟",
                    reversible=False,
                    requires_confirmation=False,
                ),
            ]
        
        elif signal_type == "god_class":
            class_name = evidence.get("class_name", "UnknownClass")
            line_count = evidence.get("line_count", 0)
            steps = [
                ProposalStep(
                    step_id="step_1",
                    description=f"分析 {class_name} (共{line_count}行)的职责",
                    action_type="analysis",
                    target=location,
                    estimated_time="20分钟",
                    reversible=False,
                    requires_confirmation=False,
                ),
                ProposalStep(
                    step_id="step_2",
                    description="识别并提取单一职责的子类或模块",
                    action_type="refactor",
                    target=location,
                    estimated_time="1-2小时",
                    reversible=True,
                    requires_confirmation=True,
                ),
                ProposalStep(
                    step_id="step_3",
                    description="创建新类并迁移代码",
                    action_type="code_change",
                    target=location,
                    estimated_time="2-3小时",
                    reversible=True,
                    requires_confirmation=True,
                ),
                ProposalStep(
                    step_id="step_4",
                    description="更新依赖关系并运行测试",
                    action_type="test",
                    target=location,
                    estimated_time="30分钟",
                    reversible=False,
                    requires_confirmation=False,
                ),
            ]
        
        elif signal_type == "deep_inheritance":
            depth = evidence.get("depth", 0)
            steps = [
                ProposalStep(
                    step_id="step_1",
                    description=f"分析继承层次 (深度: {depth})",
                    action_type="analysis",
                    target=location,
                    estimated_time="15分钟",
                    reversible=False,
                    requires_confirmation=False,
                ),
                ProposalStep(
                    step_id="step_2",
                    description="评估使用组合替代继承的可行性",
                    action_type="refactor",
                    target=location,
                    estimated_time="30分钟",
                    reversible=True,
                    requires_confirmation=True,
                ),
                ProposalStep(
                    step_id="step_3",
                    description="重构为组合模式",
                    action_type="code_change",
                    target=location,
                    estimated_time="2-4小时",
                    reversible=True,
                    requires_confirmation=True,
                ),
            ]
        
        elif signal_type == "long_method":
            method_name = evidence.get("method_name", "unknown")
            line_count = evidence.get("line_count", 0)
            steps = [
                ProposalStep(
                    step_id="step_1",
                    description=f"分析 {method_name} (共{line_count}行)",
                    action_type="analysis",
                    target=location,
                    estimated_time="10分钟",
                    reversible=False,
                    requires_confirmation=False,
                ),
                ProposalStep(
                    step_id="step_2",
                    description="识别可独立提取的代码块",
                    action_type="refactor",
                    target=location,
                    estimated_time="15分钟",
                    reversible=True,
                    requires_confirmation=False,
                ),
                ProposalStep(
                    step_id="step_3",
                    description="拆分为多个小方法",
                    action_type="code_change",
                    target=location,
                    estimated_time="30分钟",
                    reversible=True,
                    requires_confirmation=True,
                ),
            ]
        
        return steps
    
    def _format_description(self, template: str, evidence: Dict[str, Any]) -> str:
        """格式化描述，填入证据数据"""
        description = template
        
        # 替换证据中的关键数据
        for key, value in evidence.items():
            placeholder = f"{{{key}}}"
            if placeholder in description:
                description = description.replace(placeholder, str(value))
        
        return description
    
    def _priority_sort_key(self, priority: ProposalPriority) -> int:
        """优先级排序键"""
        priority_order = {
            ProposalPriority.CRITICAL: 4,
            ProposalPriority.HIGH: 3,
            ProposalPriority.MEDIUM: 2,
            ProposalPriority.LOW: 1,
            ProposalPriority.INFO: 0,
        }
        return priority_order.get(priority, 0)
