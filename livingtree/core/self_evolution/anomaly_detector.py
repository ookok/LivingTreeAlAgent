"""
AnomalyDetector - 异常征兆检测器

参考 agent-skills 的异常征兆检测机制，在任务执行过程中实时检测异常信号，
自动触发修正流程。

核心功能：
1. 实时检测异常征兆（性能下降、错误率上升、响应时间变长等）
2. 预测潜在问题（基于历史数据和模式匹配）
3. 自动触发预防性修正流程
4. 提供异常报告和建议
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from loguru import logger
from datetime import datetime
from enum import Enum
import time


class AnomalySeverity(Enum):
    """异常严重程度"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AnomalyType(Enum):
    """异常类型"""
    PERFORMANCE_DEGRADATION = "performance_degradation"
    ERROR_RATE_INCREASE = "error_rate_increase"
    RESPONSE_TIME_SPIKE = "response_time_spike"
    UNEXPECTED_OUTPUT = "unexpected_output"
    LOOP_DETECTION = "loop_detection"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    CONNECTION_FAILURE = "connection_failure"


@dataclass
class AnomalyEvent:
    """异常事件"""
    anomaly_id: str
    type: AnomalyType
    severity: AnomalySeverity
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    context: Dict[str, Any] = field(default_factory=dict)
    detected_by: str = "AnomalyDetector"
    resolved: bool = False


@dataclass
class MetricSnapshot:
    """指标快照"""
    timestamp: datetime = field(default_factory=datetime.now)
    response_time_ms: float = 0.0
    error_count: int = 0
    success_rate: float = 1.0
    token_usage: int = 0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0


class AnomalyDetector:
    """
    异常征兆检测器
    
    核心功能：
    1. 实时检测异常征兆
    2. 预测潜在问题
    3. 自动触发预防性修正流程
    4. 提供异常报告和建议
    """
    
    def __init__(self):
        self._logger = logger.bind(component="AnomalyDetector")
        self._anomaly_callbacks: List[Callable[[AnomalyEvent], None]] = []
        self._metrics_history: List[MetricSnapshot] = []
        self._max_history_size = 100
        self._anomaly_events: List[AnomalyEvent] = []
        
        # 阈值配置
        self._thresholds = {
            "response_time_warning_ms": 3000,
            "response_time_critical_ms": 10000,
            "error_rate_warning": 0.1,
            "error_rate_critical": 0.3,
            "success_rate_warning": 0.9,
            "success_rate_critical": 0.7,
            "memory_warning_mb": 1000,
            "memory_critical_mb": 1500,
            "cpu_warning_percent": 80,
            "cpu_critical_percent": 95
        }
    
    def register_callback(self, callback: Callable[[AnomalyEvent], None]):
        """
        注册异常回调函数
        
        Args:
            callback: 当检测到异常时调用的函数
        """
        self._anomaly_callbacks.append(callback)
    
    def record_metrics(self, **kwargs):
        """
        记录性能指标
        
        Args:
            response_time_ms: 响应时间（毫秒）
            error_count: 错误数量
            success_rate: 成功率
            token_usage: token 使用量
            memory_usage_mb: 内存使用（MB）
            cpu_usage_percent: CPU 使用率（%）
        """
        snapshot = MetricSnapshot(
            response_time_ms=kwargs.get("response_time_ms", 0.0),
            error_count=kwargs.get("error_count", 0),
            success_rate=kwargs.get("success_rate", 1.0),
            token_usage=kwargs.get("token_usage", 0),
            memory_usage_mb=kwargs.get("memory_usage_mb", 0.0),
            cpu_usage_percent=kwargs.get("cpu_usage_percent", 0.0)
        )
        
        self._metrics_history.append(snapshot)
        
        # 保持历史记录大小
        if len(self._metrics_history) > self._max_history_size:
            self._metrics_history.pop(0)
        
        # 检测异常
        self._detect_anomalies(snapshot)
    
    def _detect_anomalies(self, snapshot: MetricSnapshot):
        """检测异常"""
        anomalies = []
        
        # 检测响应时间异常
        if snapshot.response_time_ms > self._thresholds["response_time_critical_ms"]:
            anomalies.append(AnomalyEvent(
                anomaly_id=f"anomaly_{int(time.time())}",
                type=AnomalyType.RESPONSE_TIME_SPIKE,
                severity=AnomalySeverity.CRITICAL,
                message=f"响应时间严重超时: {snapshot.response_time_ms:.2f}ms",
                context={"response_time_ms": snapshot.response_time_ms}
            ))
        elif snapshot.response_time_ms > self._thresholds["response_time_warning_ms"]:
            anomalies.append(AnomalyEvent(
                anomaly_id=f"anomaly_{int(time.time())}",
                type=AnomalyType.RESPONSE_TIME_SPIKE,
                severity=AnomalySeverity.WARNING,
                message=f"响应时间超出预期: {snapshot.response_time_ms:.2f}ms",
                context={"response_time_ms": snapshot.response_time_ms}
            ))
        
        # 检测成功率异常
        if snapshot.success_rate < self._thresholds["success_rate_critical"]:
            anomalies.append(AnomalyEvent(
                anomaly_id=f"anomaly_{int(time.time())}",
                type=AnomalyType.ERROR_RATE_INCREASE,
                severity=AnomalySeverity.CRITICAL,
                message=f"成功率严重下降: {snapshot.success_rate:.2%}",
                context={"success_rate": snapshot.success_rate}
            ))
        elif snapshot.success_rate < self._thresholds["success_rate_warning"]:
            anomalies.append(AnomalyEvent(
                anomaly_id=f"anomaly_{int(time.time())}",
                type=AnomalyType.ERROR_RATE_INCREASE,
                severity=AnomalySeverity.WARNING,
                message=f"成功率下降: {snapshot.success_rate:.2%}",
                context={"success_rate": snapshot.success_rate}
            ))
        
        # 检测内存异常
        if snapshot.memory_usage_mb > self._thresholds["memory_critical_mb"]:
            anomalies.append(AnomalyEvent(
                anomaly_id=f"anomaly_{int(time.time())}",
                type=AnomalyType.RESOURCE_EXHAUSTION,
                severity=AnomalySeverity.CRITICAL,
                message=f"内存使用严重过高: {snapshot.memory_usage_mb:.2f}MB",
                context={"memory_usage_mb": snapshot.memory_usage_mb}
            ))
        elif snapshot.memory_usage_mb > self._thresholds["memory_warning_mb"]:
            anomalies.append(AnomalyEvent(
                anomaly_id=f"anomaly_{int(time.time())}",
                type=AnomalyType.RESOURCE_EXHAUSTION,
                severity=AnomalySeverity.WARNING,
                message=f"内存使用过高: {snapshot.memory_usage_mb:.2f}MB",
                context={"memory_usage_mb": snapshot.memory_usage_mb}
            ))
        
        # 检测 CPU 异常
        if snapshot.cpu_usage_percent > self._thresholds["cpu_critical_percent"]:
            anomalies.append(AnomalyEvent(
                anomaly_id=f"anomaly_{int(time.time())}",
                type=AnomalyType.RESOURCE_EXHAUSTION,
                severity=AnomalySeverity.CRITICAL,
                message=f"CPU 使用率过高: {snapshot.cpu_usage_percent:.1f}%",
                context={"cpu_usage_percent": snapshot.cpu_usage_percent}
            ))
        elif snapshot.cpu_usage_percent > self._thresholds["cpu_warning_percent"]:
            anomalies.append(AnomalyEvent(
                anomaly_id=f"anomaly_{int(time.time())}",
                type=AnomalyType.RESOURCE_EXHAUSTION,
                severity=AnomalySeverity.WARNING,
                message=f"CPU 使用率较高: {snapshot.cpu_usage_percent:.1f}%",
                context={"cpu_usage_percent": snapshot.cpu_usage_percent}
            ))
        
        # 检测性能趋势（基于历史数据）
        self._detect_performance_trend(anomalies)
        
        # 处理检测到的异常
        for anomaly in anomalies:
            self._handle_anomaly(anomaly)
    
    def _detect_performance_trend(self, anomalies: List[AnomalyEvent]):
        """检测性能趋势"""
        if len(self._metrics_history) < 10:
            return
        
        recent = self._metrics_history[-10:]
        avg_response_time = sum(s.response_time_ms for s in recent) / len(recent)
        
        # 检测响应时间持续上升趋势
        if len(recent) >= 5:
            trend = recent[-1].response_time_ms - recent[0].response_time_ms
            if trend > 1000:  # 上升超过 1 秒
                anomalies.append(AnomalyEvent(
                    anomaly_id=f"anomaly_{int(time.time())}",
                    type=AnomalyType.PERFORMANCE_DEGRADATION,
                    severity=AnomalySeverity.WARNING,
                    message=f"响应时间持续上升趋势: +{trend:.0f}ms",
                    context={"trend_ms": trend, "avg_response_time_ms": avg_response_time}
                ))
    
    def detect_unexpected_output(self, task: str, result: Any, context: Dict[str, Any] = None):
        """
        检测意外输出
        
        Args:
            task: 任务描述
            result: 执行结果
            context: 上下文信息
        """
        unexpected_patterns = [
            "error",
            "exception",
            "failed",
            "timeout",
            "connection refused",
            "server error",
            "500",
            "404",
            "429",
            "rate limit",
            "internal server error"
        ]
        
        result_str = str(result).lower()
        
        for pattern in unexpected_patterns:
            if pattern in result_str:
                anomaly = AnomalyEvent(
                    anomaly_id=f"anomaly_{int(time.time())}",
                    type=AnomalyType.UNEXPECTED_OUTPUT,
                    severity=AnomalySeverity.WARNING,
                    message=f"检测到意外输出模式: {pattern}",
                    context={
                        "task": task,
                        "pattern": pattern,
                        "result": str(result)[:200],
                        **(context or {})
                    }
                )
                self._handle_anomaly(anomaly)
                break
    
    def detect_loop(self, task_history: List[Dict[str, Any]]) -> bool:
        """
        检测循环行为
        
        Args:
            task_history: 任务历史记录
            
        Returns:
            是否检测到循环
        """
        if len(task_history) < 5:
            return False
        
        recent_tasks = task_history[-5:]
        task_names = [t.get("task", "") for t in recent_tasks]
        
        # 检测连续重复的任务
        if len(set(task_names)) == 1:
            anomaly = AnomalyEvent(
                anomaly_id=f"anomaly_{int(time.time())}",
                type=AnomalyType.LOOP_DETECTION,
                severity=AnomalySeverity.CRITICAL,
                message=f"检测到循环行为: 连续执行相同任务 {len(task_names)} 次",
                context={"task_name": task_names[0], "repeat_count": len(task_names)}
            )
            self._handle_anomaly(anomaly)
            return True
        
        # 检测周期性循环（任务序列重复）
        if len(task_history) >= 10:
            pattern1 = tuple(task_history[-10:-5])
            pattern2 = tuple(task_history[-5:])
            if pattern1 == pattern2:
                anomaly = AnomalyEvent(
                    anomaly_id=f"anomaly_{int(time.time())}",
                    type=AnomalyType.LOOP_DETECTION,
                    severity=AnomalySeverity.WARNING,
                    message="检测到周期性循环模式",
                    context={"pattern_length": 5}
                )
                self._handle_anomaly(anomaly)
                return True
        
        return False
    
    def _handle_anomaly(self, anomaly: AnomalyEvent):
        """处理异常事件"""
        self._anomaly_events.append(anomaly)
        self._logger.warning(f"检测到异常: {anomaly.type.value} - {anomaly.message}")
        
        # 触发回调
        for callback in self._anomaly_callbacks:
            try:
                callback(anomaly)
            except Exception as e:
                self._logger.error(f"异常回调失败: {e}")
    
    def get_anomalies(self, severity: Optional[AnomalySeverity] = None) -> List[AnomalyEvent]:
        """
        获取异常事件列表
        
        Args:
            severity: 严重程度筛选（可选）
            
        Returns:
            异常事件列表
        """
        if severity:
            return [a for a in self._anomaly_events if a.severity == severity]
        return self._anomaly_events
    
    def get_unresolved_anomalies(self) -> List[AnomalyEvent]:
        """获取未解决的异常事件"""
        return [a for a in self._anomaly_events if not a.resolved]
    
    def resolve_anomaly(self, anomaly_id: str) -> bool:
        """
        标记异常为已解决
        
        Args:
            anomaly_id: 异常 ID
            
        Returns:
            是否成功
        """
        for anomaly in self._anomaly_events:
            if anomaly.anomaly_id == anomaly_id:
                anomaly.resolved = True
                self._logger.info(f"异常已解决: {anomaly_id}")
                return True
        return False
    
    def get_health_report(self) -> Dict[str, Any]:
        """获取健康报告"""
        unresolved = self.get_unresolved_anomalies()
        critical_count = len([a for a in unresolved if a.severity == AnomalySeverity.CRITICAL])
        warning_count = len([a for a in unresolved if a.severity == AnomalySeverity.WARNING])
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_anomalies": len(self._anomaly_events),
            "unresolved_anomalies": len(unresolved),
            "critical_count": critical_count,
            "warning_count": warning_count,
            "status": "healthy" if critical_count == 0 else "degraded" if warning_count > 0 else "critical",
            "recent_metrics": self._metrics_history[-5:] if self._metrics_history else []
        }
    
    def suggest_correction(self, anomaly: AnomalyEvent) -> Dict[str, Any]:
        """
        提供修正建议
        
        Args:
            anomaly: 异常事件
            
        Returns:
            修正建议
        """
        suggestions = {
            AnomalyType.PERFORMANCE_DEGRADATION: {
                "action": "优化性能",
                "suggestions": [
                    "检查是否有重复计算",
                    "考虑引入缓存机制",
                    "优化查询语句",
                    "考虑异步处理"
                ]
            },
            AnomalyType.ERROR_RATE_INCREASE: {
                "action": "排查错误原因",
                "suggestions": [
                    "检查外部服务状态",
                    "验证输入参数有效性",
                    "增加重试机制",
                    "检查 API 密钥和权限"
                ]
            },
            AnomalyType.RESPONSE_TIME_SPIKE: {
                "action": "降低响应延迟",
                "suggestions": [
                    "检查网络连接",
                    "考虑使用就近节点",
                    "增加超时时间",
                    "检查服务端负载"
                ]
            },
            AnomalyType.UNEXPECTED_OUTPUT: {
                "action": "验证输出",
                "suggestions": [
                    "检查工具返回格式",
                    "验证数据完整性",
                    "增加错误处理",
                    "添加输出验证"
                ]
            },
            AnomalyType.LOOP_DETECTION: {
                "action": "打破循环",
                "suggestions": [
                    "设置最大重试次数",
                    "增加状态检查",
                    "添加退出条件",
                    "考虑人工干预"
                ]
            },
            AnomalyType.RESOURCE_EXHAUSTION: {
                "action": "释放资源",
                "suggestions": [
                    "清理缓存",
                    "释放未使用的对象",
                    "考虑扩容",
                    "优化内存使用"
                ]
            },
            AnomalyType.RATE_LIMIT_EXCEEDED: {
                "action": "调整请求频率",
                "suggestions": [
                    "增加请求间隔",
                    "使用批处理",
                    "申请更高限额",
                    "考虑使用多个 API 密钥"
                ]
            },
            AnomalyType.CONNECTION_FAILURE: {
                "action": "恢复连接",
                "suggestions": [
                    "检查网络连接",
                    "验证服务器地址",
                    "增加重试机制",
                    "考虑备用服务器"
                ]
            }
        }
        
        return suggestions.get(anomaly.type, {
            "action": "未知异常",
            "suggestions": ["请手动检查"]
        })