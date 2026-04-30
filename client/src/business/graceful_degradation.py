"""
优雅降级管理器 - 多级降级策略
"""

from typing import Dict, Set
from enum import Enum


class DegradationLevel(Enum):
    """降级级别"""
    NORMAL = 0         # 正常运行
    LIGHT = 1          # 轻度降级
    SEVERE = 2         # 重度降级
    EMERGENCY = 3      # 紧急模式


class GracefulDegradation:
    """优雅降级管理器"""
    
    def __init__(self):
        self._features: Dict[str, bool] = {}
        self._degradation_level = DegradationLevel.NORMAL
        self._feature_levels: Dict[str, int] = {}
        
        # 注册所有功能及其降级级别
        self._register_features()
    
    def _register_features(self):
        """注册功能及其降级级别"""
        # level=0: 始终可用（核心功能）
        # level=1: 轻度降级时禁用
        # level=2: 重度降级时禁用
        # level=3: 紧急模式时禁用
        
        self._feature_levels = {
            # 核心功能 - 始终可用
            "text_chat": 0,
            "basic_memory": 0,
            "system_health": 0,
            
            # 轻度降级时禁用
            "image_generation": 1,
            "video_processing": 1,
            "code_execution": 1,
            
            # 重度降级时禁用
            "web_search": 2,
            "external_api_calls": 2,
            "complex_analysis": 2,
            
            # 紧急模式时禁用
            "non_critical_data_sync": 3,
            "analytics_tracking": 3,
            "background_tasks": 3,
        }
        
        # 初始化所有功能为启用状态
        for feature in self._feature_levels:
            self._features[feature] = True
    
    def set_degradation_level(self, level: int):
        """设置降级级别"""
        self._degradation_level = DegradationLevel(level)
        
        # 根据级别禁用相应功能
        for feature, disable_level in self._feature_levels.items():
            self._features[feature] = disable_level > level
    
    def get_degradation_level(self) -> int:
        """获取当前降级级别"""
        return self._degradation_level.value
    
    def is_feature_enabled(self, feature: str) -> bool:
        """检查功能是否启用"""
        return self._features.get(feature, False)
    
    def get_disabled_features(self) -> Set[str]:
        """获取禁用的功能列表"""
        return {feature for feature, enabled in self._features.items() if not enabled}
    
    def enable_feature(self, feature: str):
        """启用功能"""
        if feature in self._features:
            self._features[feature] = True
    
    def disable_feature(self, feature: str):
        """禁用功能"""
        if feature in self._features:
            self._features[feature] = False
    
    def get_status_summary(self) -> Dict[str, any]:
        """获取状态摘要"""
        return {
            "degradation_level": self._degradation_level.name,
            "enabled_features": [f for f, enabled in self._features.items() if enabled],
            "disabled_features": self.get_disabled_features(),
            "total_features": len(self._features),
            "enabled_count": sum(1 for enabled in self._features.values() if enabled)
        }


def get_degradation_manager() -> GracefulDegradation:
    """获取优雅降级管理器单例"""
    if not hasattr(get_degradation_manager, '_instance'):
        get_degradation_manager._instance = GracefulDegradation()
    return get_degradation_manager._instance


from enum import Enum  # noqa: E402