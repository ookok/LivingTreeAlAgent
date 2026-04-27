# pattern_miner.py - 模式挖掘器

"""
Pattern Miner - 从历史数据中挖掘有价值的模式

核心功能：
1. 时序模式挖掘 - 发现信号出现的周期性规律
2. 共现模式挖掘 - 发现经常一起出现的信号/提案
3. 因果模式挖掘 - 发现决策-结果之间的因果关系
4. 异常模式检测 - 发现异常行为
"""

import json
import logging
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, Counter
import re

logger = logging.getLogger('evolution.pattern')


@dataclass
class TemporalPattern:
    """时序模式"""
    pattern_id: str
    description: str
    trigger_signals: List[str]  # 触发信号类型
    expected_interval_minutes: int
    confidence: float
    occurrences: int
    last_seen: str
    
    def to_dict(self) -> Dict:
        return {
            'pattern_id': self.pattern_id,
            'description': self.description,
            'trigger_signals': self.trigger_signals,
            'expected_interval_minutes': self.expected_interval_minutes,
            'confidence': self.confidence,
            'occurrences': self.occurrences,
            'last_seen': self.last_seen
        }


@dataclass
class CoOccurrencePattern:
    """共现模式"""
    item_a: str
    item_b: str
    support: float  # 支持度 P(A ∧ B)
    confidence: float  # 置信度 P(B|A)
    lift: float  # 提升度
    
    def to_dict(self) -> Dict:
        return {
            'item_a': self.item_a,
            'item_b': self.item_b,
            'support': self.support,
            'confidence': self.confidence,
            'lift': self.lift
        }


@dataclass
class CausalPattern:
    """因果模式"""
    cause: str  # 原因
    effect: str  # 效果
    causal_strength: float  # 因果强度
    conditions: List[str] = field(default_factory=list)  # 条件
    examples: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            'cause': self.cause,
            'effect': self.effect,
            'causal_strength': self.causal_strength,
            'conditions': self.conditions,
            'examples': self.examples
        }


@dataclass
class AnomalyPattern:
    """异常模式"""
    anomaly_type: str
    description: str
    severity: str
    affected_items: List[str]
    detected_at: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            'anomaly_type': self.anomaly_type,
            'description': self.description,
            'severity': self.severity,
            'affected_items': self.affected_items,
            'detected_at': self.detected_at,
            'metrics': self.metrics
        }


class PatternMiner:
    """
    模式挖掘器
    
    从历史数据中自动发现有价值的行为模式
    """
    
    # 最小支持度阈值
    MIN_SUPPORT = 0.01
    # 最小置信度阈值
    MIN_CONFIDENCE = 0.5
    # 最小提升度阈值
    MIN_LIFT = 1.2
    
    def __init__(self, evolution_log=None):
        self._log = evolution_log
        
        # 时序模式
        self._temporal_patterns: Dict[str, TemporalPattern] = {}
        
        # 共现模式
        self._cooccurrence_patterns: List[CoOccurrencePattern] = []
        
        # 因果模式
        self._causal_patterns: Dict[str, CausalPattern] = {}
        
        # 异常模式
        self._anomaly_patterns: List[AnomalyPattern] = []
        
        # 历史事件流（用于时序分析）
        self._event_stream: List[Dict] = []
        
        # 统计信息
        self._stats = {
            'total_events': 0,
            'patterns_discovered': 0,
            'last_mining': None
        }
    
    def add_event(self, event: Dict[str, Any]):
        """
        添加一个事件到事件流
        
        Args:
            event: {
                'type': 'signal' | 'proposal' | 'execution' | 'decision',
                'timestamp': ISO时间字符串,
                'data': {...}  # 具体数据
            }
        """
        # 标准化时间戳
        if isinstance(event.get('timestamp'), str):
            try:
                dt = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
                event['timestamp'] = dt.isoformat()
            except:
                event['timestamp'] = datetime.now().isoformat()
        else:
            event['timestamp'] = datetime.now().isoformat()
        
        self._event_stream.append(event)
        self._stats['total_events'] += 1
        
        # 限制事件流大小
        if len(self._event_stream) > 10000:
            self._event_stream = self._event_stream[-5000:]
    
    def mine_patterns(self) -> Dict[str, List]:
        """
        执行模式挖掘
        
        Returns:
            包含各类模式的字典
        """
        logger.info("[PatternMiner] 开始挖掘模式...")
        
        # 1. 挖掘时序模式
        self._mine_temporal_patterns()
        
        # 2. 挖掘共现模式
        self._mine_cooccurrence_patterns()
        
        # 3. 挖掘因果模式
        self._mine_causal_patterns()
        
        # 4. 检测异常模式
        self._detect_anomalies()
        
        self._stats['patterns_discovered'] = (
            len(self._temporal_patterns) +
            len(self._cooccurrence_patterns) +
            len(self._causal_patterns)
        )
        self._stats['last_mining'] = datetime.now().isoformat()
        
        logger.info(
            f"[PatternMiner] 挖掘完成: "
            f"{len(self._temporal_patterns)} 时序, "
            f"{len(self._cooccurrence_patterns)} 共现, "
            f"{len(self._causal_patterns)} 因果"
        )
        
        return {
            'temporal': [p.to_dict() for p in self._temporal_patterns.values()],
            'cooccurrence': [p.to_dict() for p in self._cooccurrence_patterns],
            'causal': [p.to_dict() for p in self._causal_patterns.values()],
            'anomalies': [p.to_dict() for p in self._anomaly_patterns]
        }
    
    def _mine_temporal_patterns(self):
        """挖掘时序模式"""
        # 按信号类型分组
        events_by_type: Dict[str, List[Dict]] = defaultdict(list)
        for event in self._event_stream:
            if event.get('type') == 'signal':
                signal_type = event.get('data', {}).get('signal_type', 'unknown')
                events_by_type[signal_type].append(event)
        
        # 分析每个信号类型的出现间隔
        for signal_type, events in events_by_type.items():
            if len(events) < 3:
                continue
            
            # 按时间排序
            events.sort(key=lambda x: x['timestamp'])
            
            # 计算间隔
            intervals = []
            for i in range(1, len(events)):
                dt1 = datetime.fromisoformat(events[i-1]['timestamp'])
                dt2 = datetime.fromisoformat(events[i]['timestamp'])
                interval_minutes = (dt2 - dt1).total_seconds() / 60
                intervals.append(interval_minutes)
            
            # 计算平均间隔和标准差
            if intervals:
                avg_interval = sum(intervals) / len(intervals)
                
                # 检查是否有规律的间隔
                # 简单检查：间隔的变异系数 < 0.5
                variance = sum((x - avg_interval) ** 2 for x in intervals) / len(intervals)
                std_dev = variance ** 0.5
                cv = std_dev / avg_interval if avg_interval > 0 else 1.0
                
                if cv < 0.5:  # 有规律的间隔
                    pattern_id = f"temporal_{signal_type}_{int(avg_interval)}m"
                    
                    # 简化描述
                    if avg_interval < 60:
                        interval_desc = f"每{int(avg_interval)}分钟"
                    elif avg_interval < 1440:
                        interval_desc = f"每{int(avg_interval/60)}小时"
                    else:
                        interval_desc = f"每{int(avg_interval/1440)}天"
                    
                    self._temporal_patterns[pattern_id] = TemporalPattern(
                        pattern_id=pattern_id,
                        description=f"{signal_type} 信号 {interval_desc} 出现",
                        trigger_signals=[signal_type],
                        expected_interval_minutes=int(avg_interval),
                        confidence=1.0 - cv,
                        occurrences=len(events),
                        last_seen=events[-1]['timestamp']
                    )
    
    def _mine_cooccurrence_patterns(self):
        """挖掘共现模式（Apriori 算法简化版）"""
        # 收集每次扫描/提案涉及的信号集合
        transactions: List[Set[str]] = []
        
        current_set: Set[str] = set()
        last_scan_time: Optional[str] = None
        
        for event in self._event_stream:
            if event.get('type') == 'signal':
                signal_type = event.get('data', {}).get('signal_type', 'unknown')
                current_set.add(signal_type)
                last_scan_time = event['timestamp']
            elif event.get('type') == 'proposal' and current_set:
                # 提案结束，收集当前信号集合
                transactions.append(current_set.copy())
                current_set = set()
        
        if len(transactions) < 5:
            return  # 数据不足
        
        # 统计单个项目的出现频率
        item_counts: Counter = Counter()
        for trans in transactions:
            item_counts.update(trans)
        
        total_transactions = len(transactions)
        
        # 找频繁项对
        if len(item_counts) < 2:
            return
        
        # 简化：只检查最频繁的几个项目之间的共现
        top_items = [item for item, _ in item_counts.most_common(20)]
        
        cooccurrence_pairs: List[Tuple[str, str, int]] = []
        
        for i, item_a in enumerate(top_items):
            for item_b in top_items[i+1:]:
                # 计算共现次数
                co_count = sum(1 for trans in transactions if item_a in trans and item_b in trans)
                
                if co_count >= 2:
                    cooccurrence_pairs.append((item_a, item_b, co_count))
        
        # 计算支持度、置信度和提升度
        for item_a, item_b, co_count in cooccurrence_pairs:
            support = co_count / total_transactions
            if support < self.MIN_SUPPORT:
                continue
            
            confidence = co_count / item_counts[item_a] if item_counts[item_a] > 0 else 0
            if confidence < self.MIN_CONFIDENCE:
                continue
            
            # 提升度 = confidence / P(B)
            p_b = item_counts[item_b] / total_transactions
            lift = confidence / p_b if p_b > 0 else 0
            
            if lift < self.MIN_LIFT:
                continue
            
            self._cooccurrence_patterns.append(CoOccurrencePattern(
                item_a=item_a,
                item_b=item_b,
                support=support,
                confidence=confidence,
                lift=lift
            ))
        
        # 按提升度排序
        self._cooccurrence_patterns.sort(key=lambda x: x.lift, reverse=True)
        
        # 只保留 top 50
        self._cooccurrence_patterns = self._cooccurrence_patterns[:50]
    
    def _mine_causal_patterns(self):
        """挖掘因果模式"""
        # 收集 (决策, 结果) 对
        decision_outcomes: List[Tuple[str, str, str]] = []  # (decision_type, target, outcome)
        
        for event in self._event_stream:
            if event.get('type') == 'decision':
                data = event.get('data', {})
                decision_type = data.get('decision_type', '')
                target = data.get('target_id', '')
                outcome = data.get('outcome', '')
                
                if decision_type and target:
                    decision_outcomes.append((decision_type, target, outcome))
            
            elif event.get('type') == 'execution':
                data = event.get('data', {})
                proposal_id = data.get('proposal_id', '')
                status = data.get('status', '')
                
                if proposal_id:
                    decision_outcomes.append(('execution', proposal_id, status))
        
        # 分析因果关系
        # 简化：如果某决策类型在特定outcome中出现频率 > 70%，则认为有因果关系
        
        outcome_by_decision: Dict[str, Counter] = defaultdict(Counter)
        for decision_type, target, outcome in decision_outcomes:
            key = f"{decision_type}:{outcome}"
            outcome_by_decision[key][target] += 1
        
        # 生成因果模式
        for key, counter in outcome_by_decision.items():
            if len(counter) == 1:
                parts = key.split(':')
                decision_type = parts[0]
                outcome = parts[1]
                total = sum(counter.values())
                
                if total >= 3:  # 至少3次观测
                    causal_strength = counter.most_common(1)[0][1] / total
                    
                    if causal_strength > 0.7:
                        pattern_key = f"causal_{decision_type}_{outcome}"
                        
                        self._causal_patterns[pattern_key] = CausalPattern(
                            cause=decision_type,
                            effect=outcome,
                            causal_strength=causal_strength,
                            conditions=[],
                            examples=[f"{decision_type} 导致了 {outcome}"]
                        )
    
    def _detect_anomalies(self):
        """检测异常模式"""
        # 1. 提案成功率异常
        proposal_outcomes = [e for e in self._event_stream if e.get('type') == 'execution']
        
        if len(proposal_outcomes) >= 10:
            success_count = sum(1 for e in proposal_outcomes if e.get('data', {}).get('status') == 'success')
            success_rate = success_count / len(proposal_outcomes)
            
            # 连续失败检测
            recent_events = proposal_outcomes[-20:]
            recent_outcomes = [e.get('data', {}).get('status') for e in recent_events]
            
            # 找连续失败
            consecutive_failures = 0
            max_consecutive_failures = 0
            for outcome in reversed(recent_outcomes):
                if outcome == 'failed':
                    consecutive_failures += 1
                    max_consecutive_failures = max(max_consecutive_failures, consecutive_failures)
                else:
                    consecutive_failures = 0
            
            if max_consecutive_failures >= 5:
                self._anomaly_patterns.append(AnomalyPattern(
                    anomaly_type='consecutive_failures',
                    description=f"检测到连续 {max_consecutive_failures} 次执行失败",
                    severity='high',
                    affected_items=['execution'],
                    detected_at=datetime.now().isoformat(),
                    metrics={
                        'consecutive_failures': max_consecutive_failures,
                        'recent_success_rate': success_rate
                    }
                ))
            
            # 成功率骤降
            if len(proposal_outcomes) >= 30:
                recent_10_success = sum(1 for e in proposal_outcomes[-10:] if e.get('data', {}).get('status') == 'success') / 10
                previous_20_success = sum(1 for e in proposal_outcomes[-30:-10] if e.get('data', {}).get('status') == 'success') / 20
                
                if recent_10_success < previous_20_success * 0.5:  # 下降超过50%
                    self._anomaly_patterns.append(AnomalyPattern(
                        anomaly_type='success_rate_drop',
                        description="执行成功率显著下降",
                        severity='medium',
                        affected_items=['execution'],
                        detected_at=datetime.now().isoformat(),
                        metrics={
                            'recent_rate': recent_10_success,
                            'previous_rate': previous_20_success
                        }
                    ))
        
        # 2. 信号频率异常
        signal_events = [e for e in self._event_stream if e.get('type') == 'signal']
        
        if len(signal_events) >= 20:
            # 检测信号爆发
            recent_signals = signal_events[-20:]
            
            # 按分钟统计
            minute_counts: Counter = Counter()
            for event in recent_signals:
                dt = datetime.fromisoformat(event['timestamp'])
                minute_key = dt.strftime('%Y-%m-%d %H:%M')
                minute_counts[minute_key] += 1
            
            if minute_counts:
                max_per_minute = max(minute_counts.values())
                avg_per_minute = sum(minute_counts.values()) / len(minute_counts)
                
                if max_per_minute > avg_per_minute * 5:  # 爆发阈值
                    peak_minute = minute_counts.most_common(1)[0][0]
                    
                    self._anomaly_patterns.append(AnomalyPattern(
                        anomaly_type='signal_burst',
                        description=f"信号频率异常爆发",
                        severity='medium',
                        affected_items=['signal'],
                        detected_at=datetime.now().isoformat(),
                        metrics={
                            'peak_per_minute': max_per_minute,
                            'avg_per_minute': avg_per_minute,
                            'peak_time': peak_minute
                        }
                    ))
        
        # 3. 提案积压
        pending_proposals = [e for e in self._event_stream 
                            if e.get('type') == 'proposal' 
                            and e.get('data', {}).get('status') == 'pending']
        
        if len(pending_proposals) > 20:
            self._anomaly_patterns.append(AnomalyPattern(
                anomaly_type='proposal_backlog',
                description=f"有 {len(pending_proposals)} 个提案等待处理",
                severity='low',
                affected_items=['proposal'],
                detected_at=datetime.now().isoformat(),
                metrics={'pending_count': len(pending_proposals)}
            ))
    
    def get_patterns_summary(self) -> Dict[str, Any]:
        """获取模式摘要"""
        return {
            'temporal_count': len(self._temporal_patterns),
            'cooccurrence_count': len(self._cooccurrence_patterns),
            'causal_count': len(self._causal_patterns),
            'anomaly_count': len(self._anomaly_patterns),
            'top_cooccurrence': [
                f"{p.item_a} ↔ {p.item_b} (lift={p.lift:.2f})"
                for p in self._cooccurrence_patterns[:5]
            ],
            'temporal_patterns': [
                p.description for p in list(self._temporal_patterns.values())[:5]
            ],
            'stats': self._stats
        }
    
    def get_predictions(self) -> List[Dict]:
        """基于挖掘的模式生成预测"""
        predictions = []
        
        # 1. 基于时序模式预测
        now = datetime.now()
        for pattern in self._temporal_patterns.values():
            last_seen = datetime.fromisoformat(pattern.last_seen)
            elapsed = (now - last_seen).total_seconds() / 60
            
            if elapsed >= pattern.expected_interval_minutes * 0.8:
                predictions.append({
                    'type': 'temporal',
                    'description': f"预期 {pattern.trigger_signals[0]} 信号即将出现",
                    'confidence': pattern.confidence,
                    'urgency': min(1.0, elapsed / pattern.expected_interval_minutes)
                })
        
        # 2. 基于因果模式的预测
        for pattern in self._causal_patterns.values():
            if pattern.causal_strength > 0.8:
                predictions.append({
                    'type': 'causal',
                    'description': f"{pattern.cause} 很可能会导致 {pattern.effect}",
                    'confidence': pattern.causal_strength,
                    'urgency': 0.5
                })
        
        # 按置信度排序
        predictions.sort(key=lambda x: x['confidence'], reverse=True)
        
        return predictions[:10]  # 最多返回10个预测
    
    def export_patterns(self) -> Dict[str, Any]:
        """导出所有模式"""
        return {
            'temporal': [p.to_dict() for p in self._temporal_patterns.values()],
            'cooccurrence': [p.to_dict() for p in self._cooccurrence_patterns],
            'causal': [p.to_dict() for p in self._causal_patterns.values()],
            'exported_at': datetime.now().isoformat()
        }
    
    def import_patterns(self, patterns: Dict[str, Any]):
        """导入模式"""
        # 时序模式
        for p_dict in patterns.get('temporal', []):
            pattern = TemporalPattern(**p_dict)
            self._temporal_patterns[pattern.pattern_id] = pattern
        
        # 共现模式
        for p_dict in patterns.get('cooccurrence', []):
            pattern = CoOccurrencePattern(**p_dict)
            self._cooccurrence_patterns.append(pattern)
        
        # 因果模式
        for p_dict in patterns.get('causal', []):
            pattern = CausalPattern(**p_dict)
            key = f"{pattern.cause}_{pattern.effect}"
            self._causal_patterns[key] = pattern
        
        logger.info(f"[PatternMiner] 导入了 {len(patterns)} 个模式")


# 全局单例
_pattern_miner: Optional[PatternMiner] = None


def get_pattern_miner(evolution_log=None) -> PatternMiner:
    """获取 PatternMiner 单例"""
    global _pattern_miner
    if _pattern_miner is None:
        _pattern_miner = PatternMiner(evolution_log)
    return _pattern_miner
