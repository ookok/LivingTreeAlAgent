# learning_engine.py - 强化学习引擎

"""
Learning Engine - 从历史数据中学习，优化提案生成

核心功能：
1. 追踪提案-执行的因果关系
2. 计算各类提案的成功率
3. 根据历史表现调整提案权重
4. 生成学习建议
"""

import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict
import math

logger = logging.getLogger('evolution.learning')


@dataclass
class ProposalMetrics:
    """提案指标"""
    proposal_type: str
    total_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    avg_execution_time_ms: float = 0.0
    total_execution_time_ms: float = 0.0
    avg_signal_strength: float = 0.0
    total_signal_strength: float = 0.0
    
    @property
    def success_rate(self) -> float:
        if self.total_count == 0:
            return 0.0
        return self.success_count / self.total_count
    
    @property
    def avg_execution_time(self) -> float:
        if self.success_count == 0:
            return 0.0
        return self.total_execution_time_ms / self.success_count


@dataclass
class SignalPattern:
    """信号模式"""
    signal_type: str
    severity: str
    location_pattern: str  # 正则或前缀
    associated_proposal_types: List[str] = field(default_factory=list)
    success_rate: float = 0.0
    avg_impact: float = 0.0
    sample_count: int = 0
    
    def update(self, proposal_type: str, success: bool, impact: float):
        self.sample_count += 1
        if proposal_type not in self.associated_proposal_types:
            self.associated_proposal_types.append(proposal_type)
        
        # 增量更新成功率
        if success:
            self.success_count = getattr(self, 'success_count', 0) + 1
        self.total_count = getattr(self, 'total_count', 0) + 1
        self.success_rate = self.success_count / self.total_count if self.total_count > 0 else 0
        
        # 增量更新平均影响
        self.avg_impact = (self.avg_impact * (self.sample_count - 1) + impact) / self.sample_count


@dataclass
class LearningInsight:
    """学习洞察"""
    insight_type: str  # 'success_pattern', 'failure_pattern', 'optimization', 'warning'
    title: str
    description: str
    evidence: List[str] = field(default_factory=list)
    confidence: float = 0.0
    recommendations: List[str] = field(default_factory=list)


class LearningEngine:
    """
    强化学习引擎
    
    从历史执行数据中学习，优化未来提案生成
    """
    
    def __init__(self, evolution_log=None):
        self._log = evolution_log
        
        # 提案类型指标
        self._proposal_metrics: Dict[str, ProposalMetrics] = {}
        
        # 信号模式
        self._signal_patterns: Dict[str, SignalPattern] = {}
        
        # 决策因素权重
        self._factor_weights: Dict[str, float] = {
            'severity': 0.3,
            'signal_strength': 0.2,
            'past_success_rate': 0.25,
            'execution_time': 0.15,
            'risk_level': 0.1
        }
        
        # 学习参数
        self._learning_rate = 0.1
        self._discount_factor = 0.9
        self._exploration_rate = 0.1
        
        # 缓存
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = 300  # 5分钟
    
    def learn_from_execution(
        self,
        proposal_type: str,
        proposal_id: str,
        signals: List[Dict],
        execution_result: Dict[str, Any]
    ):
        """
        从执行结果中学习
        
        Args:
            proposal_type: 提案类型
            proposal_id: 提案ID
            signals: 触发的信号列表
            execution_result: 执行结果 {'status': 'success'/'failed', 'duration_ms': float, ...}
        """
        success = execution_result.get('status') == 'success'
        duration_ms = execution_result.get('duration_ms', 0)
        
        # 更新提案类型指标
        self._update_proposal_metrics(proposal_type, success, duration_ms)
        
        # 更新信号模式
        for signal in signals:
            pattern_key = self._get_signal_pattern_key(signal)
            impact = self._calculate_impact(execution_result)
            self._update_signal_pattern(pattern_key, proposal_type, success, impact)
        
        # 学习决策因素
        self._learn_decision_factors(proposal_id, signals, success)
        
        # 清空缓存
        self._cache.clear()
        
        logger.info(f"[LearningEngine] 学习完成: {proposal_type}, success={success}")
    
    def _update_proposal_metrics(
        self,
        proposal_type: str,
        success: bool,
        duration_ms: float
    ):
        """更新提案指标"""
        if proposal_type not in self._proposal_metrics:
            self._proposal_metrics[proposal_type] = ProposalMetrics(
                proposal_type=proposal_type
            )
        
        metrics = self._proposal_metrics[proposal_type]
        metrics.total_count += 1
        
        if success:
            metrics.success_count += 1
            metrics.total_execution_time_ms += duration_ms
            metrics.avg_execution_time_ms = metrics.total_execution_time_ms / metrics.success_count
        else:
            metrics.failure_count += 1
    
    def _get_signal_pattern_key(self, signal: Dict) -> str:
        """生成信号模式键"""
        signal_type = signal.get('type', 'unknown')
        severity = signal.get('severity', 'unknown')
        location = signal.get('location', '')
        
        # 提取位置前缀（文件路径）
        if location:
            parts = location.split('/')
            location_prefix = '/'.join(parts[:2]) if len(parts) > 2 else location
        else:
            location_prefix = 'unknown'
        
        return f"{signal_type}:{severity}:{location_prefix}"
    
    def _update_signal_pattern(
        self,
        pattern_key: str,
        proposal_type: str,
        success: bool,
        impact: float
    ):
        """更新信号模式"""
        if pattern_key not in self._signal_patterns:
            parts = pattern_key.split(':')
            self._signal_patterns[pattern_key] = SignalPattern(
                signal_type=parts[0] if len(parts) > 0 else 'unknown',
                severity=parts[1] if len(parts) > 1 else 'unknown',
                location_pattern=parts[2] if len(parts) > 2 else 'unknown'
            )
        
        pattern = self._signal_patterns[pattern_key]
        pattern.update(proposal_type, success, impact)
    
    def _calculate_impact(self, execution_result: Dict) -> float:
        """计算执行影响"""
        # 简单模型：基于状态和步骤完成率
        base_impact = 1.0 if execution_result.get('status') == 'success' else -1.0
        
        steps_completed = execution_result.get('steps_completed', 0)
        steps_total = execution_result.get('steps_total', 1)
        completion_rate = steps_completed / steps_total if steps_total > 0 else 0
        
        return base_impact * completion_rate
    
    def _learn_decision_factors(
        self,
        proposal_id: str,
        signals: List[Dict],
        success: bool
    ):
        """学习决策因素权重"""
        # 简单的策略梯度更新
        reward = 1.0 if success else -1.0
        
        # 根据结果调整因素权重
        for signal in signals:
            severity = signal.get('severity', 'unknown')
            severity_weight = self._get_severity_score(severity)
            
            # 更新 severity 权重
            self._factor_weights['severity'] += self._learning_rate * reward * severity_weight
            self._factor_weights['severity'] = max(0, min(1, self._factor_weights['severity']))
    
    def _get_severity_score(self, severity: str) -> float:
        """获取严重程度分数"""
        scores = {
            'critical': 1.0,
            'high': 0.75,
            'medium': 0.5,
            'low': 0.25
        }
        return scores.get(severity.lower(), 0.3)
    
    def get_proposal_score(
        self,
        proposal_type: str,
        signal_strength: float,
        risk_level: str,
        estimated_time_ms: float
    ) -> float:
        """
        计算提案评分
        
        综合考虑历史成功率和各类因素
        """
        # 历史成功率
        metrics = self._proposal_metrics.get(proposal_type)
        success_rate = metrics.success_rate if metrics else 0.5
        
        # 风险调整
        risk_penalty = {
            'critical': 0.5,
            'high': 0.75,
            'medium': 0.9,
            'low': 1.0
        }.get(risk_level.lower(), 0.8)
        
        # 时间效率（越快越好）
        if metrics and metrics.avg_execution_time > 0:
            time_factor = min(1.0, metrics.avg_execution_time / estimated_time_ms)
        else:
            time_factor = 0.8  # 默认值
        
        # 综合评分
        score = (
            success_rate * self._factor_weights['past_success_rate'] +
            signal_strength * self._factor_weights['signal_strength'] +
            risk_penalty * self._factor_weights['risk_level'] +
            time_factor * self._factor_weights['execution_time']
        )
        
        return min(1.0, max(0.0, score))
    
    def get_recommended_proposal_types(self, signals: List[Dict]) -> List[Tuple[str, float]]:
        """
        根据当前信号推荐提案类型
        
        Returns:
            List of (proposal_type, score) sorted by score
        """
        # 统计当前信号
        signal_types = defaultdict(list)
        for signal in signals:
            pattern_key = self._get_signal_pattern_key(signal)
            if pattern_key in self._signal_patterns:
                signal_types[pattern_key].append(self._signal_patterns[pattern_key])
        
        # 统计提案类型得分
        proposal_scores: Dict[str, List[float]] = defaultdict(list)
        
        for pattern_key, patterns in signal_types.items():
            for pattern in patterns:
                for proposal_type in pattern.associated_proposal_types:
                    score = pattern.success_rate * pattern.avg_impact
                    proposal_scores[proposal_type].append(score)
        
        # 计算平均得分
        recommendations = []
        for proposal_type, scores in proposal_scores.items():
            avg_score = sum(scores) / len(scores)
            recommendations.append((proposal_type, avg_score))
        
        # 排序
        recommendations.sort(key=lambda x: x[1], reverse=True)
        return recommendations
    
    def get_insights(self, days: int = 7) -> List[LearningInsight]:
        """生成学习洞察"""
        insights = []
        
        # 1. 成功模式分析
        success_patterns = self._analyze_success_patterns()
        for pattern in success_patterns:
            insights.append(LearningInsight(
                insight_type='success_pattern',
                title='成功模式发现',
                description=pattern['description'],
                evidence=pattern['evidence'],
                confidence=pattern['confidence'],
                recommendations=pattern['recommendations']
            ))
        
        # 2. 失败模式分析
        failure_patterns = self._analyze_failure_patterns()
        for pattern in failure_patterns:
            insights.append(LearningInsight(
                insight_type='failure_pattern',
                title='失败模式警告',
                description=pattern['description'],
                evidence=pattern['evidence'],
                confidence=pattern['confidence'],
                recommendations=pattern['recommendations']
            ))
        
        # 3. 优化建议
        optimizations = self._generate_optimizations()
        for opt in optimizations:
            insights.append(LearningInsight(
                insight_type='optimization',
                title='优化建议',
                description=opt['description'],
                recommendations=opt['recommendations']
            ))
        
        return insights
    
    def _analyze_success_patterns(self) -> List[Dict]:
        """分析成功模式"""
        patterns = []
        
        for proposal_type, metrics in self._proposal_metrics.items():
            if metrics.success_rate > 0.8 and metrics.total_count >= 3:
                patterns.append({
                    'description': f'{proposal_type} 提案有很高的成功率 ({metrics.success_rate:.1%})',
                    'evidence': [
                        f'样本数: {metrics.total_count}',
                        f'成功数: {metrics.success_count}',
                        f'平均执行时间: {metrics.avg_execution_time:.0f}ms'
                    ],
                    'confidence': min(0.9, metrics.success_rate),
                    'recommendations': [
                        f'可以更多地使用 {proposal_type} 提案',
                        '考虑提高该类型提案的优先级'
                    ]
                })
        
        return patterns
    
    def _analyze_failure_patterns(self) -> List[Dict]:
        """分析失败模式"""
        patterns = []
        
        for proposal_type, metrics in self._proposal_metrics.items():
            if metrics.success_rate < 0.5 and metrics.total_count >= 3:
                patterns.append({
                    'description': f'{proposal_type} 提案成功率较低 ({metrics.success_rate:.1%})',
                    'evidence': [
                        f'样本数: {metrics.total_count}',
                        f'失败数: {metrics.failure_count}'
                    ],
                    'confidence': min(0.9, 1 - metrics.success_rate),
                    'recommendations': [
                        f'需要改进 {proposal_type} 的执行策略',
                        '考虑在执行前增加更多验证步骤'
                    ]
                })
        
        return patterns
    
    def _generate_optimizations(self) -> List[Dict]:
        """生成优化建议"""
        optimizations = []
        
        # 1. 信号模式优化
        for pattern_key, pattern in self._signal_patterns.items():
            if pattern.sample_count >= 5 and pattern.success_rate > 0.7:
                optimizations.append({
                    'description': f'信号组合 {pattern.signal_type} + {pattern.severity} 效果好',
                    'recommendations': [
                        '增加该信号组合的检测灵敏度',
                        '优先触发关联的提案类型'
                    ]
                })
        
        # 2. 执行时间优化
        slow_proposals = [
            (pt, m) for pt, m in self._proposal_metrics.items()
            if m.success_count > 0 and m.avg_execution_time_ms > 60000  # > 1分钟
        ]
        
        if slow_proposals:
            optimizations.append({
                'description': f'发现 {len(slow_proposals)} 种较慢的提案类型',
                'recommendations': [
                    '考虑并行化执行步骤',
                    '增加超时限制避免长时间阻塞'
                ]
            })
        
        return optimizations
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取学习统计"""
        total_samples = sum(m.total_count for m in self._proposal_metrics.values())
        
        return {
            'total_samples': total_samples,
            'proposal_types_count': len(self._proposal_metrics),
            'signal_patterns_count': len(self._signal_patterns),
            'factor_weights': self._factor_weights,
            'proposal_metrics': {
                pt: {
                    'total': m.total_count,
                    'success': m.success_count,
                    'success_rate': m.success_rate,
                    'avg_time_ms': m.avg_execution_time
                }
                for pt, m in self._proposal_metrics.items()
            }
        }
    
    def export_weights(self) -> Dict[str, float]:
        """导出学习到的权重"""
        return self._factor_weights.copy()
    
    def import_weights(self, weights: Dict[str, float]):
        """导入权重（用于迁移或恢复）"""
        for key, value in weights.items():
            if key in self._factor_weights:
                self._factor_weights[key] = value
        
        logger.info(f"[LearningEngine] 导入了 {len(weights)} 个权重")


# 全局单例
_learning_engine: Optional[LearningEngine] = None


def get_learning_engine(evolution_log=None) -> LearningEngine:
    """获取 LearningEngine 单例"""
    global _learning_engine
    if _learning_engine is None:
        _learning_engine = LearningEngine(evolution_log)
    return _learning_engine
