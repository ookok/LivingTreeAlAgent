"""
配置场景选择器 - 提供预设的场景化配置模板
"""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class SceneConfig:
    """场景配置"""
    name: str
    icon: str
    description: str
    configs: Dict[str, Any]


class ConfigSceneSelector:
    """配置场景选择器"""
    
    SCENES: Dict[str, SceneConfig] = {
        "developer": SceneConfig(
            name="开发者模式",
            icon="👨‍💻",
            description="适合代码开发、调试、自动化",
            configs={
                "default_model": "claude-3-sonnet",
                "code_execution": True,
                "auto_save": True,
                "theme": "dark",
                "code_execution_timeout": 60,
                "enable_syntax_highlight": True
            }
        ),
        "researcher": SceneConfig(
            name="研究模式",
            icon="🔬",
            description="适合文献搜索、数据分析、报告撰写",
            configs={
                "default_model": "claude-3-opus",
                "web_search": True,
                "rag_enabled": True,
                "theme": "light",
                "auto_save": True,
                "document_analysis_enabled": True
            }
        ),
        "creative": SceneConfig(
            name="创意模式",
            icon="🎨",
            description="适合写作、设计、创意生成",
            configs={
                "default_model": "claude-3-sonnet",
                "image_generation": True,
                "writing_assistant": True,
                "theme": "dark",
                "auto_save": True,
                "creative_mode": True
            }
        ),
        "enterprise": SceneConfig(
            name="企业模式",
            icon="🏢",
            description="适合团队协作、会议管理、办公自动化",
            configs={
                "default_model": "claude-3-opus",
                "team_collaboration": True,
                "meeting_scheduler": True,
                "security_enabled": True,
                "theme": "dark",
                "audit_log_enabled": True
            }
        ),
        "general": SceneConfig(
            name="通用模式",
            icon="🌟",
            description="适合日常使用，平衡各项功能",
            configs={
                "default_model": "claude-3-haiku",
                "auto_save": True,
                "theme": "light",
                "notification_enabled": True
            }
        )
    }
    
    def __init__(self):
        self._current_scene = None
        self._config_manager = None
    
    def set_config_manager(self, config_manager):
        """设置配置管理器"""
        self._config_manager = config_manager
    
    def get_scenes(self) -> Dict[str, SceneConfig]:
        """获取所有场景"""
        return self.SCENES
    
    def get_scene(self, scene_name: str) -> SceneConfig:
        """获取指定场景"""
        return self.SCENES.get(scene_name)
    
    def apply_scene(self, scene_name: str) -> bool:
        """应用场景配置"""
        scene = self.SCENES.get(scene_name)
        if not scene:
            return False
        
        self._current_scene = scene_name
        
        if self._config_manager:
            for key, value in scene.configs.items():
                self._config_manager.set(key, value)
        else:
            # 直接存储配置（如果没有配置管理器）
            from .config_provider import ConfigProvider
            ConfigProvider.set(key, value)
        
        return True
    
    def get_current_scene(self) -> str:
        """获取当前场景"""
        return self._current_scene
    
    def get_scene_recommendations(self) -> Dict[str, float]:
        """获取场景推荐度"""
        recommendations = {}
        for name, scene in self.SCENES.items():
            recommendations[name] = self._calculate_recommendation(name)
        return recommendations
    
    def _calculate_recommendation(self, scene_name: str) -> float:
        """计算场景推荐度"""
        return 0.5  # 默认值，实际实现中可基于用户行为计算