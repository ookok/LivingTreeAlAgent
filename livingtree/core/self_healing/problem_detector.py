"""
问题检测模块 - 自动发现系统问题和异常

功能：
1. 检测运行时异常
2. 分析问题根因
3. 生成问题报告
4. 预测潜在问题
"""

import logging
import time
import traceback
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ProblemSeverity(Enum):
    """问题严重程度"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ProblemCategory(Enum):
    """问题类别"""
    PERFORMANCE = "performance"
    MEMORY = "memory"
    NETWORK = "network"
    CRASH = "crash"
    CONFIGURATION = "configuration"
    DEPENDENCY = "dependency"
    UNKNOWN = "unknown"


@dataclass
class ProblemReport:
    """问题报告"""
    report_id: str
    title: str
    description: str
    severity: ProblemSeverity
    category: ProblemCategory
    location: Dict[str, Any] = None
    metadata: Dict[str, Any] = None
    timestamp: float = None
    resolved: bool = False
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
        if self.location is None:
            self.location = {}
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict:
        return {
            'report_id': self.report_id,
            'title': self.title,
            'description': self.description,
            'severity': self.severity.value,
            'category': self.category.value,
            'location': self.location,
            'metadata': self.metadata,
            'timestamp': self.timestamp,
            'resolved': self.resolved
        }


class ProblemDetector:
    """
    问题检测器 - 自动发现和分析系统问题
    
    检测能力：
    1. 异常检测 - 捕获运行时异常
    2. 性能问题 - 检测性能下降
    3. 资源问题 - 检测资源耗尽
    4. 配置问题 - 检测配置错误
    5. 依赖问题 - 检测依赖缺失
    """
    
    def __init__(self):
        self._reports: Dict[str, ProblemReport] = {}
        self._detection_rules = self._init_rules()
        
        # 检测统计
        self._stats = {
            'total_detected': 0,
            'total_resolved': 0,
            'by_severity': {'info': 0, 'warning': 0, 'error': 0, 'critical': 0},
            'by_category': {}
        }
    
    def _init_rules(self) -> List[Dict]:
        """初始化检测规则"""
        return [
            {
                'name': 'cpu_high',
                'check': lambda m: m.get('cpu_usage', {}).get('value', 0) > 90,
                'severity': ProblemSeverity.CRITICAL,
                'category': ProblemCategory.PERFORMANCE,
                'message': 'CPU使用率过高'
            },
            {
                'name': 'memory_high',
                'check': lambda m: m.get('memory_usage', {}).get('value', 0) > 90,
                'severity': ProblemSeverity.CRITICAL,
                'category': ProblemCategory.MEMORY,
                'message': '内存使用率过高'
            },
            {
                'name': 'disk_high',
                'check': lambda m: m.get('disk_usage', {}).get('value', 0) > 95,
                'severity': ProblemSeverity.ERROR,
                'category': ProblemCategory.PERFORMANCE,
                'message': '磁盘空间不足'
            },
            {
                'name': 'cpu_warning',
                'check': lambda m: m.get('cpu_usage', {}).get('value', 0) > 80,
                'severity': ProblemSeverity.WARNING,
                'category': ProblemCategory.PERFORMANCE,
                'message': 'CPU使用率偏高'
            },
            {
                'name': 'memory_warning',
                'check': lambda m: m.get('memory_usage', {}).get('value', 0) > 85,
                'severity': ProblemSeverity.WARNING,
                'category': ProblemCategory.MEMORY,
                'message': '内存使用率偏高'
            }
        ]
    
    def detect_from_metrics(self, metrics: Dict) -> List[ProblemReport]:
        """从指标中检测问题"""
        reports = []
        
        for rule in self._detection_rules:
            if rule['check'](metrics):
                report = self._create_report(
                    title=rule['message'],
                    description=f"检测到指标异常: {rule['message']}",
                    severity=rule['severity'],
                    category=rule['category'],
                    metadata={'metrics': metrics}
                )
                reports.append(report)
        
        return reports
    
    def detect_from_exception(self, exception: Exception, context: Dict = None) -> Optional[ProblemReport]:
        """从异常中检测问题"""
        import uuid
        
        report_id = str(uuid.uuid4())
        
        # 分析异常类型
        exc_type = type(exception).__name__
        
        # 确定严重程度和类别
        severity = ProblemSeverity.ERROR
        category = ProblemCategory.UNKNOWN
        
        if exc_type in ['MemoryError', 'OutOfMemoryError']:
            severity = ProblemSeverity.CRITICAL
            category = ProblemCategory.MEMORY
        elif exc_type in ['ConnectionError', 'TimeoutError', 'SocketError']:
            severity = ProblemSeverity.ERROR
            category = ProblemCategory.NETWORK
        elif exc_type in ['ImportError', 'ModuleNotFoundError']:
            severity = ProblemSeverity.ERROR
            category = ProblemCategory.DEPENDENCY
        elif exc_type in ['ValueError', 'TypeError', 'AttributeError']:
            severity = ProblemSeverity.WARNING
            category = ProblemCategory.CONFIGURATION
        elif exc_type == 'RuntimeError':
            severity = ProblemSeverity.ERROR
            category = ProblemCategory.UNKNOWN
        
        report = ProblemReport(
            report_id=report_id,
            title=f"异常: {exc_type}",
            description=str(exception),
            severity=severity,
            category=category,
            location={
                'type': exc_type,
                'traceback': traceback.format_exc()
            },
            metadata={
                'context': context,
                'exception_type': exc_type
            }
        )
        
        self._reports[report_id] = report
        self._update_stats(report)
        
        logger.error(f"检测到问题: {report.title} [{severity.value}]")
        return report
    
    def detect_from_log(self, log_entry: Dict) -> Optional[ProblemReport]:
        """从日志中检测问题"""
        level = log_entry.get('level', 'INFO').upper()
        message = log_entry.get('message', '')
        
        if level in ['ERROR', 'CRITICAL']:
            severity = ProblemSeverity.CRITICAL if level == 'CRITICAL' else ProblemSeverity.ERROR
            
            # 尝试分类
            category = ProblemCategory.UNKNOWN
            if 'memory' in message.lower():
                category = ProblemCategory.MEMORY
            elif 'network' in message.lower() or 'connection' in message.lower():
                category = ProblemCategory.NETWORK
            elif 'crash' in message.lower() or 'exception' in message.lower():
                category = ProblemCategory.CRASH
            
            return self._create_report(
                title=f"日志错误: {message[:50]}",
                description=message,
                severity=severity,
                category=category,
                metadata={'log_entry': log_entry}
            )
        
        return None
    
    def predict_problems(self, metrics: Dict) -> List[Dict]:
        """预测潜在问题"""
        predictions = []
        
        # 根据趋势预测
        for name, metric in metrics.items():
            trend = metric.get('trend')
            value = metric.get('value', 0)
            threshold = metric.get('threshold', 0)
            
            if trend == 'increasing' and value > threshold * 0.8:
                predictions.append({
                    'metric': name,
                    'prediction': f"{name} 持续增长，预计将超过阈值",
                    'risk_level': 'high' if value > threshold * 0.9 else 'medium'
                })
        
        return predictions
    
    def get_all_reports(self) -> List[ProblemReport]:
        """获取所有问题报告"""
        return list(self._reports.values())
    
    def get_unresolved_reports(self) -> List[ProblemReport]:
        """获取未解决的问题报告"""
        return [r for r in self._reports.values() if not r.resolved]
    
    def resolve_report(self, report_id: str):
        """标记问题已解决"""
        if report_id in self._reports:
            self._reports[report_id].resolved = True
            self._stats['total_resolved'] += 1
            logger.info(f"问题已解决: {report_id}")
    
    def get_report(self, report_id: str) -> Optional[ProblemReport]:
        """获取单个问题报告"""
        return self._reports.get(report_id)
    
    def get_stats(self) -> Dict:
        """获取检测统计"""
        return {
            **self._stats,
            'unresolved_count': len(self.get_unresolved_reports()),
            'total_reports': len(self._reports)
        }
    
    def _create_report(self, title: str, description: str, severity: ProblemSeverity,
                      category: ProblemCategory, metadata: Dict = None) -> ProblemReport:
        """创建问题报告"""
        import uuid
        
        report_id = str(uuid.uuid4())
        report = ProblemReport(
            report_id=report_id,
            title=title,
            description=description,
            severity=severity,
            category=category,
            metadata=metadata or {}
        )
        
        self._reports[report_id] = report
        self._update_stats(report)
        
        logger.warning(f"检测到问题: {title} [{severity.value}]")
        return report
    
    def _update_stats(self, report: ProblemReport):
        """更新统计"""
        self._stats['total_detected'] += 1
        self._stats['by_severity'][report.severity.value] += 1
        self._stats['by_category'][report.category.value] = \
            self._stats['by_category'].get(report.category.value, 0) + 1