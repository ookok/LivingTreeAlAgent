"""
AI驱动的配置助手 - 智能引导用户完成系统配置
"""

import asyncio
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Callable


@dataclass
class ConfigGap:
    """配置缺口信息"""
    name: str
    description: str
    priority: str  # high, medium, low
    target: Optional[str] = None
    action: Optional[str] = None


@dataclass
class GuideAction:
    """引导动作"""
    type: str  # modal, tooltip, notification
    title: str
    content: str
    action: str
    auto_open: bool = False
    target: Optional[str] = None


class ConfigGuideAssistant:
    """AI驱动的配置助手"""
    
    def __init__(self):
        self._user_profile = {}
        self._config_status = {}
        self._required_configs = [
            "default_model",
            "api_keys",
            "workspace_path",
            "theme",
            "auto_save",
            "notification_enabled"
        ]
    
    async def analyze_and_guide(self, user_context: Dict[str, Any]) -> List[GuideAction]:
        """分析用户上下文并提供配置引导"""
        # 分析用户使用模式
        usage_pattern = self._analyze_usage(user_context)
        
        # 识别配置缺口
        gaps = self._identify_gaps(usage_pattern)
        
        # 生成个性化引导
        guides = self._generate_guides(gaps)
        
        return guides
    
    def _analyze_usage(self, user_context: Dict[str, Any]) -> Dict[str, float]:
        """分析用户使用模式"""
        usage_pattern = {
            "code_execution": user_context.get("code_execution", 0.0),
            "web_search": user_context.get("web_search", 0.0),
            "document_analysis": user_context.get("document_analysis", 0.0),
            "chat_frequency": user_context.get("chat_frequency", 0.0),
            "user_type": user_context.get("user_type", "general")
        }
        return usage_pattern
    
    def _identify_gaps(self, usage_pattern: Dict[str, Any]) -> List[ConfigGap]:
        """识别配置缺口"""
        gaps = []
        
        # 检查必需配置
        for config_key in self._required_configs:
            if config_key not in self._config_status or not self._config_status[config_key]:
                priority = "high" if config_key in ["default_model", "api_keys"] else "medium"
                gaps.append(ConfigGap(
                    name=config_key.replace("_", " ").title(),
                    description=self._get_config_description(config_key),
                    priority=priority,
                    target=f"config.{config_key}"
                ))
        
        # 根据使用模式推荐额外配置
        if usage_pattern.get("code_execution", 0) > 0.7:
            gaps.append(ConfigGap(
                name="代码执行超时",
                description="检测到高频代码执行，建议配置更长的超时时间",
                priority="medium",
                target="config.code_execution_timeout"
            ))
        
        if usage_pattern.get("web_search", 0) > 0.5:
            gaps.append(ConfigGap(
                name="搜索引擎配置",
                description="检测到频繁搜索行为，建议启用多搜索引擎",
                priority="medium",
                target="config.search_providers"
            ))
        
        return gaps
    
    def _get_config_description(self, config_key: str) -> str:
        """获取配置项描述"""
        descriptions = {
            "default_model": "设置默认使用的AI模型",
            "api_keys": "配置API密钥以启用外部服务",
            "workspace_path": "设置工作目录路径",
            "theme": "选择界面主题",
            "auto_save": "启用自动保存功能",
            "notification_enabled": "启用通知提醒"
        }
        return descriptions.get(config_key, f"配置 {config_key}")
    
    def _generate_guides(self, gaps: List[ConfigGap]) -> List[GuideAction]:
        """生成引导内容"""
        guides = []
        
        for gap in gaps:
            if gap.priority == "high":
                guides.append(GuideAction(
                    type="modal",
                    title=f"⚡ 需要配置: {gap.name}",
                    content=gap.description,
                    action=f"配置 {gap.name}",
                    auto_open=True,
                    target=gap.target
                ))
            elif gap.priority == "medium":
                guides.append(GuideAction(
                    type="tooltip",
                    title=f"💡 建议配置",
                    content=f"{gap.name}: {gap.description}",
                    action=f"配置",
                    target=gap.target
                ))
        
        return guides
    
    def update_config_status(self, config_key: str, value: Any):
        """更新配置状态"""
        self._config_status[config_key] = value
    
    def get_config_status(self) -> Dict[str, Any]:
        """获取配置状态"""
        return self._config_status.copy()


def get_config_assistant() -> ConfigGuideAssistant:
    """获取配置助手单例"""
    if not hasattr(get_config_assistant, '_instance'):
        get_config_assistant._instance = ConfigGuideAssistant()
    return get_config_assistant._instance