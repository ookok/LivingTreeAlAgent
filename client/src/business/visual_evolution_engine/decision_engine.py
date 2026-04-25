# -*- coding: utf-8 -*-
"""
决策引擎 - Decision Engine
=========================

功能：
1. 升级决策树生成
2. 多维度评估
3. 时机优化
4. 风险评估
5. 决策可视化

Author: Hermes Desktop Team
"""

import time
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 数据模型
# ─────────────────────────────────────────────────────────────────────────────

class DecisionType(Enum):
    """决策类型"""
    UPGRADE = "upgrade"
    ROLLBACK = "rollback"
    POSTPONE = "postpone"
    SKIP = "skip"


class DecisionNodeType(Enum):
    """决策节点类型"""
    CONDITION = "condition"  # 条件判断
    ACTION = "action"  # 执行动作
    OUTCOME = "outcome"  # 结果


@dataclass
class DecisionNode:
    """决策树节点"""
    node_id: str
    node_type: DecisionNodeType
    label: str
    description: str = ""
    
    # 条件节点属性
    condition: str = ""  # 条件表达式
    true_child: Optional[str] = None  # 条件为真的子节点ID
    false_child: Optional[str] = None  # 条件为假的子节点ID
    
    # 动作节点属性
    action: str = ""
    action_args: Dict[str, Any] = field(default_factory=dict)
    
    # 结果节点属性
    outcome: str = ""
    outcome_type: DecisionType = DecisionType.SKIP
    
    # 可视化属性
    status: str = "pending"  # pending, active, passed, failed
    score: float = 0.0  # 决策得分


@dataclass
class DecisionTree:
    """决策树"""
    tree_id: str
    title: str
    description: str
    created_at: datetime = field(default_factory=datetime.now)
    
    nodes: Dict[str, DecisionNode] = field(default_factory=dict)
    root_id: str = ""
    
    # 执行路径
    current_node_id: str = ""
    path: List[str] = field(default_factory=list)  # 走过的路径
    outcome: Optional[DecisionType] = None
    
    # 评分
    total_score: float = 0.0
    recommendation: str = ""


@dataclass
class EvaluationCriteria:
    """评估标准"""
    # 资源评估
    resource_sufficient: bool = False
    disk_available_gb: float = 0.0
    memory_available_gb: float = 0.0
    
    # 时机评估
    business_idle: bool = False
    optimal_window: bool = False
    recommended_time: Optional[datetime] = None
    
    # 兼容性评估
    compatibility_checked: bool = False
    compatibility_score: float = 0.0
    
    # 风险评估
    risk_level: str = "low"
    risk_factors: List[str] = field(default_factory=list)
    
    # 收益评估
    expected_improvement: float = 0.0
    improvement_areas: List[str] = field(default_factory=list)


@dataclass
class UpgradeRecommendation:
    """升级建议"""
    recommendation_id: str
    created_at: datetime = field(default_factory=datetime.now)
    
    # 基本信息
    from_model: str = ""
    to_model: str = ""
    
    # 评估结果
    evaluation: EvaluationCriteria = field(default_factory=EvaluationCriteria)
    
    # 决策树
    decision_tree: Optional[DecisionTree] = None
    
    # 最终建议
    recommended_action: DecisionType = DecisionType.POSTPONE
    confidence: float = 0.0  # 置信度
    reasoning: str = ""
    
    # 最佳时机
    recommended_time: Optional[datetime] = None
    estimated_duration_minutes: float = 0.0
    
    # 备选方案
    alternatives: List[Dict[str, Any]] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# 决策引擎
# ─────────────────────────────────────────────────────────────────────────────

class EvolutionDecisionEngine:
    """
    进化决策引擎
    
    功能：
    1. 生成决策树
    2. 多维度评估
    3. 时机优化
    4. 风险量化
    5. 建议生成
    """
    
    # 决策阈值配置
    THRESHOLDS = {
        "min_disk_gb": 10.0,  # 最低磁盘空间
        "min_memory_gb": 8.0,  # 最低可用内存
        "max_cpu_percent": 70,  # 最大CPU使用率
        "max_memory_percent": 75,  # 最大内存使用率
        "optimal_download_speed_mbps": 5.0,  # 最佳下载速度
        "idle_window_minutes": 30,  # 空闲窗口最小时间
    }
    
    def __init__(self):
        self._decision_callbacks: List[Callable[[UpgradeRecommendation], None]] = []
    
    # ── 主决策流程 ──────────────────────────────────────────────────────────
    
    async def evaluate_upgrade(
        self,
        from_model: str,
        to_model: str,
        system_data: Dict[str, Any]
    ) -> UpgradeRecommendation:
        """
        评估升级建议
        
        Args:
            from_model: 当前模型
            to_model: 目标模型
            system_data: 系统数据（来自SystemMonitor）
            
        Returns:
            升级建议
        """
        rec_id = f"REC-{int(time.time())}"
        
        # 1. 执行多维度评估
        evaluation = await self._evaluate_all_dimensions(from_model, to_model, system_data)
        
        # 2. 生成决策树
        decision_tree = self._generate_decision_tree(from_model, to_model, evaluation)
        
        # 3. 确定最终建议
        recommended_action, confidence, reasoning = self._determine_recommendation(
            evaluation, decision_tree
        )
        
        # 4. 计算最佳时机
        recommended_time = self._calculate_optimal_time(evaluation, system_data)
        
        # 5. 生成备选方案
        alternatives = self._generate_alternatives(evaluation)
        
        return UpgradeRecommendation(
            recommendation_id=rec_id,
            from_model=from_model,
            to_model=to_model,
            evaluation=evaluation,
            decision_tree=decision_tree,
            recommended_action=recommended_action,
            confidence=confidence,
            reasoning=reasoning,
            recommended_time=recommended_time,
            estimated_duration_minutes=evaluation.evaluation.get("estimated_time", 60),
            alternatives=alternatives,
        )
    
    async def _evaluate_all_dimensions(
        self,
        from_model: str,
        to_model: str,
        system_data: Dict[str, Any]
    ) -> EvaluationCriteria:
        """多维度评估"""
        evaluation = EvaluationCriteria()
        
        # 1. 资源评估
        resources = system_data.get("resources", {})
        disk = system_data.get("disk", {})
        gpu = system_data.get("gpu", {})
        
        disk_available = disk.get("free_gb", 0)
        memory_available = resources.get("memory_available_gb", 0)
        
        # 目标模型大小估算（从模型名推断）
        target_size_gb = self._estimate_model_size(to_model)
        
        evaluation.resource_sufficient = (
            disk_available > target_size_gb + 5 and  # 目标大小 + 5GB缓冲
            memory_available > self.THRESHOLDS["min_memory_gb"]
        )
        evaluation.disk_available_gb = disk_available
        evaluation.memory_available_gb = memory_available
        
        # 2. 时机评估
        cpu_percent = resources.get("cpu_percent", 0)
        memory_percent = resources.get("memory_percent", 0)
        
        evaluation.business_idle = (
            cpu_percent < self.THRESHOLDS["max_cpu_percent"] and
            memory_percent < self.THRESHOLDS["max_memory_percent"]
        )
        
        # 计算最佳窗口
        if not evaluation.business_idle:
            # 估算等待时间
            evaluation.optimal_window = False
            evaluation.recommended_time = self._estimate_idle_time(
                cpu_percent, memory_percent
            )
        else:
            evaluation.optimal_window = True
            evaluation.recommended_time = datetime.now()
        
        # 3. 兼容性评估（简化实现）
        evaluation.compatibility_checked = True
        evaluation.compatibility_score = 0.95  # 简化，假设95%兼容
        
        # 4. 风险评估
        risk_factors = []
        
        if disk_available < target_size_gb + 10:
            risk_factors.append("磁盘空间紧张")
        
        if memory_available < self.THRESHOLDS["min_memory_gb"]:
            risk_factors.append("可用内存不足")
        
        if not evaluation.business_idle:
            risk_factors.append("业务繁忙，升级可能中断")
        
        if evaluation.compatibility_score < 0.9:
            risk_factors.append("可能存在兼容性问题")
        
        if risk_factors:
            if len(risk_factors) >= 3:
                evaluation.risk_level = "high"
            else:
                evaluation.risk_level = "medium"
        else:
            evaluation.risk_level = "low"
        
        evaluation.risk_factors = risk_factors
        
        # 5. 收益评估
        evaluation.expected_improvement = 15.0  # 简化估算
        evaluation.improvement_areas = [
            "推理准确率",
            "上下文理解",
            "指令跟随",
        ]
        
        # 存储评估数据供后续使用
        evaluation.evaluation = {
            "target_size_gb": target_size_gb,
            "cpu_percent": cpu_percent,
            "memory_percent": memory_percent,
            "estimated_time": target_size_gb / 5 * 60,  # 假设5GB/分钟
        }
        
        return evaluation
    
    def _estimate_model_size(self, model_name: str) -> float:
        """估算模型大小"""
        # 从模型名推断大小
        size_map = {
            "1b": 1.5,
            "3b": 3.5,
            "7b": 8.0,
            "14b": 16.0,
            "32b": 36.0,
            "70b": 80.0,
        }
        
        import re
        for size, gb in size_map.items():
            if size in model_name.lower():
                return gb
        
        return 8.0  # 默认7B
    
    def _estimate_idle_time(self, cpu_percent: float, memory_percent: float) -> datetime:
        """估算空闲时间"""
        # 简化估算：假设每小时会有一段时间空闲
        # 实际应该基于历史数据预测
        
        # 计算距离下一小时的分钟数
        now = datetime.now()
        minutes_to_next_hour = 60 - now.minute
        
        # 加上一些缓冲
        estimated_minutes = max(30, minutes_to_next_hour + 15)
        
        return datetime.now() + timedelta(minutes=estimated_minutes)
    
    # ── 决策树生成 ──────────────────────────────────────────────────────────
    
    def _generate_decision_tree(
        self,
        from_model: str,
        to_model: str,
        evaluation: EvaluationCriteria
    ) -> DecisionTree:
        """生成决策树"""
        tree_id = f"DT-{int(time.time())}"
        
        tree = DecisionTree(
            tree_id=tree_id,
            title=f"升级决策: {from_model} → {to_model}",
            description="通过决策树分析确定最优升级策略",
        )
        
        # 节点1: 根节点 - 资源检查
        node1 = DecisionNode(
            node_id="root",
            node_type=DecisionNodeType.CONDITION,
            label="资源是否充足?",
            description=f"磁盘: {evaluation.disk_available_gb:.1f}GB, 内存: {evaluation.memory_available_gb:.1f}GB",
            condition=f"disk >= {evaluation.evaluation.get('target_size_gb', 10) + 5} and memory >= {self.THRESHOLDS['min_memory_gb']}",
            true_child="timing",
            false_child="insufficient_resources",
        )
        tree.nodes["root"] = node1
        
        # 节点2: 时机检查
        node2 = DecisionNode(
            node_id="timing",
            node_type=DecisionNodeType.CONDITION,
            label="业务是否空闲?",
            description=f"CPU: {evaluation.evaluation.get('cpu_percent', 0):.0f}%, 内存: {evaluation.evaluation.get('memory_percent', 0):.0f}%",
            condition=f"cpu < {self.THRESHOLDS['max_cpu_percent']} and memory < {self.THRESHOLDS['max_memory_percent']}",
            true_child="compatibility",
            false_child="wait_for_idle",
        )
        tree.nodes["timing"] = node2
        
        # 节点3: 兼容性检查
        node3 = DecisionNode(
            node_id="compatibility",
            node_type=DecisionNodeType.CONDITION,
            label="兼容性检查",
            description=f"兼容性得分: {evaluation.compatibility_score:.0%}",
            condition=f"compatibility >= 0.8",
            true_child="risk_assessment",
            false_child="review_compatibility",
        )
        tree.nodes["compatibility"] = node3
        
        # 节点4: 风险评估
        node4 = DecisionNode(
            node_id="risk_assessment",
            node_type=DecisionNodeType.CONDITION,
            label="风险等级",
            description=f"风险: {evaluation.risk_level}",
            condition=f"risk != 'high'",
            true_child="approved",
            false_child="manual_review",
        )
        tree.nodes["risk_assessment"] = node4
        
        # 结果节点
        tree.nodes["insufficient_resources"] = DecisionNode(
            node_id="insufficient_resources",
            node_type=DecisionNodeType.OUTCOME,
            label="资源不足",
            description="建议释放资源或扩展存储",
            outcome="资源不足，建议先释放空间",
            outcome_type=DecisionType.POSTPONE,
        )
        
        tree.nodes["wait_for_idle"] = DecisionNode(
            node_id="wait_for_idle",
            node_type=DecisionNodeType.OUTCOME,
            label="等待空闲窗口",
            description=f"建议时间: {evaluation.recommended_time.strftime('%H:%M') if evaluation.recommended_time else '待确定'}",
            outcome=f"建议在{evaluation.recommended_time.strftime('%H:%M') if evaluation.recommended_time else '系统空闲时'}执行",
            outcome_type=DecisionType.POSTPONE,
        )
        
        tree.nodes["review_compatibility"] = DecisionNode(
            node_id="review_compatibility",
            node_type=DecisionNodeType.OUTCOME,
            label="需要兼容性审查",
            outcome="建议先在小范围测试兼容性",
            outcome_type=DecisionType.POSTPONE,
        )
        
        tree.nodes["manual_review"] = DecisionNode(
            node_id="manual_review",
            node_type=DecisionNodeType.OUTCOME,
            label="需要人工审核",
            outcome="风险较高，建议人工评估后决定",
            outcome_type=DecisionType.SKIP,
        )
        
        tree.nodes["approved"] = DecisionNode(
            node_id="approved",
            node_type=DecisionNodeType.OUTCOME,
            label="建议升级",
            description=f"预计耗时: {evaluation.evaluation.get('estimated_time', 60):.0f}分钟",
            outcome="资源充足，业务空闲，风险可控，建议升级",
            outcome_type=DecisionType.UPGRADE,
        )
        
        tree.root_id = "root"
        
        return tree
    
    def _determine_recommendation(
        self,
        evaluation: EvaluationCriteria,
        decision_tree: DecisionTree
    ) -> tuple:
        """确定最终建议"""
        # 基于评估结果做出决策
        confidence = 0.0
        reasoning = ""
        
        if not evaluation.resource_sufficient:
            return DecisionType.POSTPONE, 0.95, "资源不足，需要释放空间"
        
        if evaluation.risk_level == "high":
            return DecisionType.SKIP, 0.85, "风险等级高，需要人工审核"
        
        if not evaluation.optimal_window:
            return DecisionType.POSTPONE, 0.90, f"建议在{evaluation.recommended_time.strftime('%H:%M') if evaluation.recommended_time else '空闲时'}执行"
        
        if evaluation.compatibility_score < 0.8:
            return DecisionType.POSTPONE, 0.80, "存在兼容性问题，建议先测试"
        
        # 所有检查都通过
        confidence = (
            evaluation.compatibility_score * 0.3 +
            (1.0 if evaluation.risk_level == "low" else 0.7) * 0.3 +
            (1.0 if evaluation.optimal_window else 0.6) * 0.2 +
            0.2  # 基础分
        )
        
        return DecisionType.UPGRADE, confidence, "各项检查通过，建议执行升级"
    
    def _calculate_optimal_time(
        self,
        evaluation: EvaluationCriteria,
        system_data: Dict[str, Any]
    ) -> Optional[datetime]:
        """计算最佳执行时间"""
        if evaluation.optimal_window:
            return datetime.now()
        
        return evaluation.recommended_time or (datetime.now() + timedelta(hours=1))
    
    def _generate_alternatives(self, evaluation: EvaluationCriteria) -> List[Dict[str, Any]]:
        """生成备选方案"""
        alternatives = []
        
        # 方案1: 立即执行
        if evaluation.resource_sufficient and evaluation.optimal_window:
            alternatives.append({
                "type": "immediate",
                "label": "立即执行",
                "description": "当前系统资源充足，建议立即执行",
                "risk": "low",
                "time": "now",
            })
        
        # 方案2: 等待空闲
        if not evaluation.optimal_window:
            alternatives.append({
                "type": "wait",
                "label": "等待空闲窗口",
                "description": f"建议在 {evaluation.recommended_time.strftime('%H:%M') if evaluation.recommended_time else '系统空闲时'} 执行",
                "risk": "medium",
                "time": evaluation.recommended_time.isoformat() if evaluation.recommended_time else None,
            })
        
        # 方案3: 手动执行
        alternatives.append({
            "type": "manual",
            "label": "手动控制",
            "description": "由用户在合适时机手动触发升级",
            "risk": "low",
            "time": "manual",
        })
        
        return alternatives
    
    # ── 决策树遍历 ────────────────────────────────────────────────────────
    
    async def traverse_decision_tree(
        self,
        tree: DecisionTree,
        system_data: Dict[str, Any],
        on_node_visit: Optional[Callable[[str, DecisionNode], None]] = None
    ) -> DecisionType:
        """遍历决策树"""
        current_id = tree.root_id
        tree.current_node_id = current_id
        path = []
        
        while current_id:
            node = tree.nodes.get(current_id)
            if not node:
                break
            
            path.append(current_id)
            tree.path = path
            
            if on_node_visit:
                on_node_visit(current_id, node)
            
            # 更新节点状态
            node.status = "active"
            
            if node.node_type == DecisionNodeType.OUTCOME:
                tree.outcome = node.outcome_type
                return node.outcome_type
            
            # 评估条件（简化实现）
            condition_result = self._evaluate_condition(node.condition, system_data)
            node.status = "passed" if condition_result else "failed"
            
            # 移动到下一个节点
            if node.node_type == DecisionNodeType.CONDITION:
                current_id = node.true_child if condition_result else node.false_child
                tree.current_node_id = current_id
            else:
                break
        
        return DecisionType.SKIP
    
    def _evaluate_condition(self, condition: str, system_data: Dict[str, Any]) -> bool:
        """评估条件"""
        # 简化实现，实际应该解析和执行条件表达式
        try:
            # 简单的字符串替换
            resources = system_data.get("resources", {})
            disk = system_data.get("disk", {})
            
            eval_str = condition
            eval_str = eval_str.replace("disk", str(disk.get("free_gb", 0)))
            eval_str = eval_str.replace("memory", str(resources.get("memory_available_gb", 0)))
            eval_str = eval_str.replace("cpu", str(resources.get("cpu_percent", 0)))
            eval_str = eval_str.replace("compatibility", "0.95")
            eval_str = eval_str.replace("risk", f"'{system_data.get('evaluation', {}).get('risk_level', 'low')}'")
            
            return eval(eval_str)
        except Exception as e:
            logger.error(f"条件评估失败: {e}")
            return False
    
    # ── 可视化数据生成 ──────────────────────────────────────────────────────
    
    def get_tree_visualization_data(self, tree: DecisionTree) -> Dict[str, Any]:
        """获取决策树可视化数据"""
        nodes = []
        edges = []
        
        for node_id, node in tree.nodes.items():
            # 节点数据
            node_data = {
                "id": node_id,
                "label": node.label,
                "type": node.node_type.value,
                "status": node.status,
                "description": node.description,
            }
            
            if node.node_type == DecisionNodeType.OUTCOME:
                node_data["outcome"] = node.outcome
                node_data["outcomeType"] = node.outcome_type.value
            
            nodes.append(node_data)
            
            # 边数据
            if node.true_child:
                edges.append({
                    "from": node_id,
                    "to": node.true_child,
                    "label": "是",
                    "style": "solid",
                })
            
            if node.false_child:
                edges.append({
                    "from": node_id,
                    "to": node.false_child,
                    "label": "否",
                    "style": "dashed",
                })
        
        return {
            "nodes": nodes,
            "edges": edges,
            "currentNode": tree.current_node_id,
            "path": tree.path,
            "outcome": tree.outcome.value if tree.outcome else None,
        }


# ─────────────────────────────────────────────────────────────────────────────
# 单例访问
# ─────────────────────────────────────────────────────────────────────────────

_decision_engine: Optional[EvolutionDecisionEngine] = None


def get_decision_engine() -> EvolutionDecisionEngine:
    """获取决策引擎单例"""
    global _decision_engine
    if _decision_engine is None:
        _decision_engine = EvolutionDecisionEngine()
    return _decision_engine
