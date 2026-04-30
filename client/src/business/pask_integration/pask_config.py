"""
PASKConfig - PASK 主动式智能体配置
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class MemoryConfig:
    """记忆系统配置"""
    workspace_max_size: int = 100  # 工作空间最大条目数
    user_memory_max_size: int = 1000  # 用户记忆最大条目数
    global_memory_max_size: int = 10000  # 全局记忆最大条目数
    memory_retention_days: int = 365  # 记忆保留天数
    auto_cleanup: bool = True  # 自动清理过期记忆


@dataclass
class DemandDetectionConfig:
    """需求检测配置"""
    intent_threshold: float = 0.7  # 意图置信度阈值
    max_history_length: int = 50  # 历史对话最大长度
    latency_ms: int = 100  # 延迟约束（毫秒）
    enable_streaming: bool = True  # 启用流式检测


@dataclass
class ProactiveConfig:
    """主动式行为配置"""
    enable_proactivity: bool = True  # 启用主动行为
    max_actions_per_session: int = 5  # 每会话最大主动行为数
    action_confidence_threshold: float = 0.8  # 行为置信度阈值
    min_time_between_actions: int = 30  # 行为间隔最小时间（秒）


@dataclass
class PASKConfig:
    """PASK 整体配置"""
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    demand_detection: DemandDetectionConfig = field(default_factory=DemandDetectionConfig)
    proactive: ProactiveConfig = field(default_factory=ProactiveConfig)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory": {
                "workspace_max_size": self.memory.workspace_max_size,
                "user_memory_max_size": self.memory.user_memory_max_size,
                "global_memory_max_size": self.memory.global_memory_max_size,
                "memory_retention_days": self.memory.memory_retention_days,
                "auto_cleanup": self.memory.auto_cleanup
            },
            "demand_detection": {
                "intent_threshold": self.demand_detection.intent_threshold,
                "max_history_length": self.demand_detection.max_history_length,
                "latency_ms": self.demand_detection.latency_ms,
                "enable_streaming": self.demand_detection.enable_streaming
            },
            "proactive": {
                "enable_proactivity": self.proactive.enable_proactivity,
                "max_actions_per_session": self.proactive.max_actions_per_session,
                "action_confidence_threshold": self.proactive.action_confidence_threshold,
                "min_time_between_actions": self.proactive.min_time_between_actions
            }
        }
    
    def load_from_dict(self, data: Dict[str, Any]):
        if "memory" in data:
            self.memory.workspace_max_size = data["memory"].get("workspace_max_size", 100)
            self.memory.user_memory_max_size = data["memory"].get("user_memory_max_size", 1000)
            self.memory.global_memory_max_size = data["memory"].get("global_memory_max_size", 10000)
            self.memory.memory_retention_days = data["memory"].get("memory_retention_days", 365)
            self.memory.auto_cleanup = data["memory"].get("auto_cleanup", True)
        
        if "demand_detection" in data:
            self.demand_detection.intent_threshold = data["demand_detection"].get("intent_threshold", 0.7)
            self.demand_detection.max_history_length = data["demand_detection"].get("max_history_length", 50)
            self.demand_detection.latency_ms = data["demand_detection"].get("latency_ms", 100)
            self.demand_detection.enable_streaming = data["demand_detection"].get("enable_streaming", True)
        
        if "proactive" in data:
            self.proactive.enable_proactivity = data["proactive"].get("enable_proactivity", True)
            self.proactive.max_actions_per_session = data["proactive"].get("max_actions_per_session", 5)
            self.proactive.action_confidence_threshold = data["proactive"].get("action_confidence_threshold", 0.8)
            self.proactive.min_time_between_actions = data["proactive"].get("min_time_between_actions", 30)