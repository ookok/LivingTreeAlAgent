# sensors/base.py - 传感器基类

"""
Evolution Engine 传感器基类
定义传感器通用接口和数据结构
"""

from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
import time
import threading
import logging

logger = logging.getLogger('evolution.sensor.base')


class SensorType(Enum):
    """传感器类型"""
    # 运行时性能
    PERFORMANCE = "performance"          # API响应、内存泄漏、CPU瓶颈
    ERROR_PATTERN = "error_pattern"      # 高频异常、日志分析
    RESOURCE_USAGE = "resource_usage"    # 内存/CPU/磁盘使用率
    
    # 代码质量
    ARCHITECTURE_SMELL = "arch_smell"   # 循环依赖、上帝类
    TECHNICAL_DEBT = "tech_debt"         # 过期API、冗余代码
    SECURITY_VULN = "security_vuln"      # 安全漏洞、SCA扫描
    
    # 生态情报
    COMPETITOR_TREND = "competitor"      # GitHub趋势、新框架
    COST_ANALYSIS = "cost_analysis"       # 云成本、资源浪费
    
    # 用户行为
    USER_WORKFLOW = "user_workflow"      # 绕路操作、重复求助
    SATISFACTION = "satisfaction"        # 用户满意度埋点


@dataclass
class EvolutionSignal:
    """进化信号"""
    signal_id: str
    sensor_type: SensorType
    timestamp: datetime
    
    # 信号来源
    source_module: str
    
    # 信号内容
    signal_type: str           # e.g., "high_latency", "circular_dependency"
    severity: str              # "critical" / "warning" / "info"
    evidence: List[str]        # 具体证据
    affected_files: List[str]  # 受影响文件
    metrics: Dict[str, float] # 量化指标
    
    # 置信度
    confidence: float          # 0.0 ~ 1.0
    false_positive_rate: float # 误报率
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "signal_id": self.signal_id,
            "sensor_type": self.sensor_type.value,
            "timestamp": self.timestamp.isoformat(),
            "source_module": self.source_module,
            "signal_type": self.signal_type,
            "severity": self.severity,
            "evidence": self.evidence,
            "affected_files": self.affected_files,
            "metrics": self.metrics,
            "confidence": self.confidence,
            "false_positive_rate": self.false_positive_rate,
        }


class BaseSensor(ABC):
    """
    传感器基类
    
    所有传感器必须继承此类并实现 scan() 方法
    """
    
    def __init__(
        self,
        name: str,
        sensor_type: SensorType,
        config: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.sensor_type = sensor_type
        self.config = config or {}
        
        # 状态
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_scan_time: Optional[datetime] = None
        
        # 信号回调
        self.on_signal: Optional[Callable[[EvolutionSignal], None]] = None
        
        # 信号缓冲
        self._signal_buffer: List[EvolutionSignal] = []
        self._buffer_lock = threading.Lock()
        
        logger.info(f"[{self.name}] 传感器初始化")
    
    def start(self):
        """启动传感器"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info(f"[{self.name}] 传感器启动")
    
    def stop(self):
        """停止传感器"""
        self._running = False
        
        if self._thread:
            self._thread.join(timeout=5)
        
        logger.info(f"[{self.name}] 传感器停止")
    
    def _run_loop(self):
        """后台运行循环"""
        scan_interval = self.config.get('scan_interval', 3600)  # 默认1小时
        
        while self._running:
            try:
                signals = self.scan()
                
                for signal in signals:
                    self._emit_signal(signal)
                
                self._last_scan_time = datetime.now()
                
            except Exception as e:
                logger.error(f"[{self.name}] 扫描异常: {e}")
            
            # 休眠
            time.sleep(scan_interval)
    
    @abstractmethod
    def scan(self) -> List[EvolutionSignal]:
        """
        执行扫描，返回检测到的信号
        
        Returns:
            进化信号列表
        """
        pass
    
    def _emit_signal(self, signal: EvolutionSignal):
        """发射信号"""
        with self._buffer_lock:
            self._signal_buffer.append(signal)
        
        # 触发回调
        if self.on_signal:
            try:
                self.on_signal(signal)
            except Exception as e:
                logger.error(f"[{self.name}] 信号回调异常: {e}")
        
        logger.info(
            f"[{self.name}] 信号发射: {signal.signal_type} "
            f"({signal.severity}, 置信度={signal.confidence:.0%})"
        )
    
    def _create_signal(
        self,
        signal_type: str,
        severity: str,
        evidence: List[str],
        metrics: Optional[Dict[str, float]] = None,
        affected_files: Optional[List[str]] = None,
        confidence: float = 0.8,
        false_positive_rate: float = 0.1
    ) -> EvolutionSignal:
        """
        创建信号的便捷方法
        
        Args:
            signal_type: 信号类型
            severity: 严重程度
            evidence: 证据列表
            metrics: 指标字典
            affected_files: 受影响文件
            confidence: 置信度
            false_positive_rate: 误报率
        """
        return EvolutionSignal(
            signal_id=f"{self.sensor_type.value}_{signal_type}_{int(time.time() * 1000)}",
            sensor_type=self.sensor_type,
            timestamp=datetime.now(),
            source_module=self.name,
            signal_type=signal_type,
            severity=severity,
            evidence=evidence,
            affected_files=affected_files or [],
            metrics=metrics or {},
            confidence=confidence,
            false_positive_rate=false_positive_rate
        )
    
    def get_buffered_signals(self) -> List[EvolutionSignal]:
        """获取缓冲的信号并清空缓冲区"""
        with self._buffer_lock:
            signals = self._signal_buffer.copy()
            self._signal_buffer.clear()
            return signals
    
    def get_last_scan_time(self) -> Optional[datetime]:
        """获取上次扫描时间"""
        return self._last_scan_time
