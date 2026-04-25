# aggregator/signal_aggregator.py - 信号聚合器

"""
SignalAggregator - 信号聚合器

功能：
1. 多源信号融合（RRF + 加权平均）
2. 信号去重与合并
3. 信号优先级排序
4. 信号有效性验证
"""

from typing import List, Dict, Any, Optional
from collections import defaultdict
import hashlib
from datetime import datetime, timedelta
import logging

from ..sensors.base import SensorType, EvolutionSignal

logger = logging.getLogger('evolution.aggregator')


class SignalAggregator:
    """
    信号聚合器
    
    将多个传感器的信号进行融合、去重、排序
    """
    
    # 信号类型权重配置
    SENSOR_WEIGHTS = {
        SensorType.PERFORMANCE: 0.3,
        SensorType.ERROR_PATTERN: 0.25,
        SensorType.SECURITY_VULN: 0.3,
        SensorType.ARCHITECTURE_SMELL: 0.2,
        SensorType.TECHNICAL_DEBT: 0.15,
        SensorType.COMPETITOR_TREND: 0.1,
        SensorType.COST_ANALYSIS: 0.15,
        SensorType.USER_WORKFLOW: 0.2,
        SensorType.RESOURCE_USAGE: 0.2,
        SensorType.SATISFACTION: 0.15,
    }
    
    # 严重程度分数
    SEVERITY_SCORES = {
        'critical': 3,
        'warning': 2,
        'info': 1,
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # 信号缓冲区
        self._signal_buffer: List[EvolutionSignal] = []
        
        # 聚合历史
        self._last_aggregation: Optional[datetime] = None
        self._aggregation_interval = timedelta(
            seconds=self.config.get('aggregation_interval_seconds', 3600)
        )
        
        # 自定义权重（可选）
        if 'sensor_weights' in self.config:
            self.SENSOR_WEIGHTS.update(self.config['sensor_weights'])
        
        logger.info(f"[SignalAggregator] 初始化完成，聚合间隔: {self._aggregation_interval}")
    
    def add_signal(self, signal: EvolutionSignal):
        """
        添加信号到缓冲区
        
        Args:
            signal: 进化信号
        """
        self._signal_buffer.append(signal)
        logger.debug(
            f"[SignalAggregator] 信号添加: {signal.signal_type} "
            f"({signal.sensor_type.value}, 置信度={signal.confidence:.0%})"
        )
    
    def add_signals(self, signals: List[EvolutionSignal]):
        """
        批量添加信号
        
        Args:
            signals: 信号列表
        """
        for signal in signals:
            self.add_signal(signal)
    
    def aggregate(
        self,
        min_confidence: float = 0.5,
        max_age_hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        执行信号聚合
        
        Args:
            min_confidence: 最小置信度阈值
            max_age_hours: 信号最大存活时间（小时）
        
        Returns:
            聚合后的信号组列表
        """
        if not self._signal_buffer:
            logger.debug("[SignalAggregator] 信号缓冲区为空")
            return []
        
        # 1. 过滤过期信号
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        active_signals = [
            s for s in self._signal_buffer
            if s.confidence >= min_confidence and s.timestamp > cutoff_time
        ]
        
        if not active_signals:
            logger.debug("[SignalAggregator] 没有有效信号")
            self._signal_buffer.clear()
            return []
        
        # 2. 按信号类型分组
        signals_by_type = defaultdict(list)
        for signal in active_signals:
            signals_by_type[signal.signal_type].append(signal)
        
        # 3. 对每组信号进行融合
        aggregated_groups = []
        
        for signal_type, signals in signals_by_type.items():
            group = self._fuse_signal_group(signals)
            if group:
                aggregated_groups.append(group)
        
        # 4. 按严重程度和置信度排序
        aggregated_groups.sort(
            key=lambda x: (
                -self._severity_score(x['severity']),
                -x['avg_confidence'],
                -x['signal_count']
            )
        )
        
        # 5. 清理缓冲区
        self._signal_buffer.clear()
        self._last_aggregation = datetime.now()
        
        logger.info(
            f"[SignalAggregator] 聚合完成: {len(aggregated_groups)} 个信号组, "
            f"共 {len(active_signals)} 个原始信号"
        )
        
        return aggregated_groups
    
    def _fuse_signal_group(self, signals: List[EvolutionSignal]) -> Optional[Dict[str, Any]]:
        """融合一组同类信号"""
        if not signals:
            return None
        
        # 收集所有证据
        all_evidence: List[str] = []
        all_affected_files: set = set()
        all_metrics: Dict[str, List[float]] = defaultdict(list)
        
        for signal in signals:
            all_evidence.extend(signal.evidence)
            all_affected_files.update(signal.affected_files)
            
            for key, value in signal.metrics.items():
                if isinstance(value, (int, float)):
                    all_metrics[key].append(float(value))
        
        # 聚合数值指标（均值）
        aggregated_metrics = {
            key: sum(values) / len(values) 
            for key, values in all_metrics.items()
        }
        
        # 计算平均置信度（加权）
        total_weight = 0
        weighted_confidence = 0
        for signal in signals:
            weight = self.SENSOR_WEIGHTS.get(signal.sensor_type, 0.2)
            weighted_confidence += signal.confidence * weight
            total_weight += weight
        avg_confidence = weighted_confidence / total_weight if total_weight > 0 else 0
        
        # 确定最严重级别
        max_severity = max(
            signals, 
            key=lambda s: self.SEVERITY_SCORES.get(s.severity, 0)
        ).severity
        
        # 生成聚合ID
        aggregated_id = hashlib.md5(
            f"{signals[0].signal_type}_{signals[0].sensor_type.value}".encode()
        ).hexdigest()[:12]
        
        return {
            'signal_type': signals[0].signal_type,
            'sensor_type': signals[0].sensor_type.value,
            'signal_count': len(signals),
            'severity': max_severity,
            'avg_confidence': avg_confidence,
            'evidence': list(set(all_evidence))[:10],  # 最多10条证据
            'affected_files': list(all_affected_files)[:20],  # 最多20个文件
            'metrics': aggregated_metrics,
            'sample_signals': [s.to_dict() for s in signals[:3]],  # 保留前3个样本
            'aggregated_id': aggregated_id,
            'timestamps': [s.timestamp.isoformat() for s in signals],
        }
    
    def _severity_score(self, severity: str) -> int:
        """获取严重程度分数"""
        return self.SEVERITY_SCORES.get(severity, 0)
    
    def get_pending_signals(self) -> List[EvolutionSignal]:
        """获取待处理的信号（不清空）"""
        return self._signal_buffer.copy()
    
    def clear_buffer(self):
        """清空信号缓冲区"""
        count = len(self._signal_buffer)
        self._signal_buffer.clear()
        logger.info(f"[SignalAggregator] 缓冲区已清空 ({count} 个信号)")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取聚合统计"""
        return {
            'buffer_size': len(self._signal_buffer),
            'last_aggregation': self._last_aggregation.isoformat() if self._last_aggregation else None,
            'aggregation_interval_seconds': self._aggregation_interval.total_seconds(),
        }
    
    def get_signals_by_sensor(self) -> Dict[str, int]:
        """按传感器类型统计信号数量"""
        counts = defaultdict(int)
        for signal in self._signal_buffer:
            counts[signal.sensor_type.value] += 1
        return dict(counts)
