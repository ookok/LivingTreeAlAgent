"""
上下文帮助系统 - Context Help

功能：
1. 在需要配置时自动显示帮助
2. 提供"刚好足够"的帮助信息
3. 支持可交互的帮助卡片
4. 进度保存与恢复

使用示例：
    help_system = ContextHelp()
    
    # 获取功能帮助卡片
    card = help_system.get_help_card("weather_api")
    print(card.title)  # "需要配置天气API"
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class HelpLevel(Enum):
    """帮助级别"""
    MINIMAL = "minimal"       # 最简帮助
    STANDARD = "standard"     # 标准帮助
    DETAILED = "detailed"     # 详细帮助


@dataclass
class HelpCard:
    """
    帮助卡片
    
    Attributes:
        card_id: 卡片ID
        feature_id: 功能标识符
        title: 标题
        content: 内容（支持Markdown）
        why_needed: 为什么需要这个
        time_estimate: 需要多少时间
        benefits: 有什么好处
        level: 帮助级别
        actions: 可执行的动作
        guide_flow_id: 关联的引导流程ID
    """
    card_id: str
    feature_id: str
    title: str
    content: str
    why_needed: str = ""
    time_estimate: str = ""
    benefits: List[str] = field(default_factory=list)
    level: HelpLevel = HelpLevel.STANDARD
    actions: List[Dict[str, Any]] = field(default_factory=list)
    guide_flow_id: Optional[str] = None
    priority: int = 0  # 显示优先级
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "card_id": self.card_id,
            "feature_id": self.feature_id,
            "title": self.title,
            "content": self.content,
            "why_needed": self.why_needed,
            "time_estimate": self.time_estimate,
            "benefits": self.benefits,
            "level": self.level.value,
            "actions": self.actions,
            "guide_flow_id": self.guide_flow_id,
            "priority": self.priority,
        }
    
    def to_markdown(self) -> str:
        """转换为Markdown格式"""
        md = f"## {self.title}\n\n"
        
        if self.why_needed:
            md += f"**为什么需要这个？**\n{self.why_needed}\n\n"
        
        if self.time_estimate:
            md += f"**需要多少时间？**\n{self.time_estimate}\n\n"
        
        if self.benefits:
            md += "**有什么好处？**\n"
            for benefit in self.benefits:
                md += f"- {benefit}\n"
            md += "\n"
        
        md += f"\n{self.content}\n"
        
        if self.actions:
            md += "\n**操作选项：**\n"
            for action in self.actions:
                md += f"- [{action['title']}]({action.get('url', '#')})\n"
        
        return md


class ContextHelp:
    """
    上下文帮助系统
    
    在需要时提供刚好足够的帮助信息
    """
    
    _instance: Optional["ContextHelp"] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # 帮助模板
        self._help_templates: Dict[str, HelpCard] = {}
        self._init_builtin_templates()
        
        self._initialized = True
        logger.info("ContextHelp initialized")
    
    def _init_builtin_templates(self):
        """初始化内置帮助模板"""
        
        # OpenWeatherMap API 帮助
        self._help_templates["weather_api"] = HelpCard(
            card_id="help_weather_api",
            feature_id="weather_api",
            title="需要配置天气 API Key",
            content="天气数据需要通过 API 获取。配置后可以访问实时天气、预报、空气质量等功能。",
            why_needed="获取实时天气数据，提高预测准确性，启用高级气象功能",
            time_estimate="✅ 注册: 2分钟\n✅ 获取Key: 1分钟\n✅ 配置: 10秒\n**总计: 约3分钟**",
            benefits=[
                "1000次/天免费调用",
                "比公开数据准确30%",
                "支持40种气象要素",
            ],
            level=HelpLevel.STANDARD,
            actions=[
                {"title": "🚀 一键配置（推荐）", "url": "guide:weather_api", "type": "guide"},
                {"title": "已有Key？直接粘贴", "url": "config:paste", "type": "input"},
                {"title": "使用免费方案", "url": "impl:openmeteo", "type": "switch"},
            ],
            priority=10,
        )
        
        # 高德地图帮助
        self._help_templates["map_service"] = HelpCard(
            card_id="help_map_service",
            feature_id="map_service",
            title="需要配置地图服务",
            content="地图功能需要地图服务支持。有多个提供商可选。",
            why_needed="提供地图展示、地理编码、路径规划等功能",
            time_estimate="✅ 注册: 3分钟\n✅ 配置: 1分钟",
            benefits=[
                "支持国内精确地图",
                "提供路径规划",
                "地理编码服务",
            ],
            level=HelpLevel.STANDARD,
            actions=[
                {"title": "🚀 一键配置高德地图", "url": "guide:amap", "type": "guide"},
                {"title": "使用OpenStreetMap（免费）", "url": "impl:osm", "type": "switch"},
            ],
            priority=8,
        )
        
        # OpenAI API 帮助
        self._help_templates["openai_api"] = HelpCard(
            card_id="help_openai_api",
            feature_id="openai_api",
            title="需要配置 OpenAI API Key",
            content="AI 对话功能需要 OpenAI API Key。配置后可以使用 GPT-4 等高级模型。",
            why_needed="启用 AI 对话、代码生成、复杂推理等高级功能",
            time_estimate="✅ 注册: 5分钟\n✅ 获取Key: 1分钟\n✅ 配置: 10秒",
            benefits=[
                "GPT-4 模型能力",
                "复杂任务处理",
                "代码生成与调试",
            ],
            level=HelpLevel.STANDARD,
            actions=[
                {"title": "🚀 一键配置（推荐）", "url": "guide:openai", "type": "guide"},
                {"title": "使用 Claude（备选）", "url": "guide:claude", "type": "guide"},
                {"title": "使用本地模型（免费）", "url": "impl:qwen_local", "type": "switch"},
            ],
            priority=9,
        )
        
        # Ollama 帮助
        self._help_templates["ollama"] = HelpCard(
            card_id="help_ollama",
            feature_id="ollama",
            title="需要配置 Ollama 本地模型",
            content="Ollama 允许在本地运行大语言模型，保护隐私，无需联网。",
            why_needed="提供本地 AI 能力，保护隐私，无需 API 费用",
            time_estimate="✅ 下载: 5-10分钟（取决于网速）\n✅ 安装: 2分钟\n✅ 拉取模型: 3-5分钟",
            benefits=[
                "完全免费使用",
                "保护数据隐私",
                "无需联网",
            ],
            level=HelpLevel.STANDARD,
            actions=[
                {"title": "🚀 一键安装 Ollama", "url": "guide:ollama", "type": "guide"},
                {"title": "手动安装指南", "url": "https://ollama.com/download", "type": "external"},
            ],
            priority=7,
        )
        
        # 通用功能帮助
        self._help_templates["generic"] = HelpCard(
            card_id="help_generic",
            feature_id="generic",
            title="功能需要配置",
            content="此功能需要配置后才能使用。",
            why_needed="启用完整功能体验",
            time_estimate="取决于具体功能",
            benefits=["解锁高级功能", "提升使用体验"],
            level=HelpLevel.MINIMAL,
            actions=[
                {"title": "开始配置", "url": "guide:start", "type": "guide"},
            ],
            priority=0,
        )
    
    def get_help_card(
        self, 
        feature_id: str,
        level: HelpLevel = HelpLevel.STANDARD,
        user_context: Optional[Dict[str, Any]] = None
    ) -> HelpCard:
        """
        获取帮助卡片
        
        Args:
            feature_id: 功能标识符
            level: 帮助级别
            user_context: 用户上下文
        
        Returns:
            HelpCard
        """
        # 查找模板
        card = self._help_templates.get(feature_id)
        
        if card is None:
            # 使用通用模板
            card = self._help_templates.get("generic")
            if card:
                card = HelpCard(
                    card_id=f"help_{feature_id}",
                    feature_id=feature_id,
                    title=f"需要配置 {feature_id}",
                    content=card.content,
                    priority=5,
                )
        
        return card
    
    def get_minimal_help(self, feature_id: str) -> str:
        """获取最小化帮助文本"""
        card = self.get_help_card(feature_id, HelpLevel.MINIMAL)
        return f"{card.title}\n\n{card.content}"
    
    def get_standard_help(self, feature_id: str) -> str:
        """获取标准帮助Markdown"""
        card = self.get_help_card(feature_id, HelpLevel.STANDARD)
        return card.to_markdown()
    
    def get_detailed_help(self, feature_id: str) -> str:
        """获取详细帮助Markdown"""
        card = self.get_help_card(feature_id, HelpLevel.DETAILED)
        return card.to_markdown()
    
    def get_actionable_help(
        self, 
        feature_id: str,
        user_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        获取可操作帮助
        
        返回结构化的帮助信息，包含可执行的动作
        """
        card = self.get_help_card(feature_id, HelpLevel.STANDARD, user_context)
        
        return {
            "title": card.title,
            "content": card.content,
            "why_needed": card.why_needed,
            "time_estimate": card.time_estimate,
            "benefits": card.benefits,
            "primary_action": card.actions[0] if card.actions else None,
            "secondary_actions": card.actions[1:] if len(card.actions) > 1 else [],
            "guide_flow_id": card.guide_flow_id,
        }
    
    def register_help_template(self, card: HelpCard):
        """
        注册帮助模板
        
        Args:
            card: 帮助卡片
        """
        self._help_templates[card.feature_id] = card
    
    def get_all_help_cards(self) -> List[HelpCard]:
        """获取所有帮助卡片（按优先级排序）"""
        cards = list(self._help_templates.values())
        cards.sort(key=lambda c: c.priority, reverse=True)
        return cards
    
    def get_pending_help(self, features_need_config: List[str]) -> List[HelpCard]:
        """
        获取待处理帮助列表
        
        Args:
            features_need_config: 需要配置的功能列表
        
        Returns:
            按优先级排序的帮助卡片
        """
        cards = []
        for feature_id in features_need_config:
            card = self.get_help_card(feature_id)
            cards.append(card)
        
        # 按优先级排序
        cards.sort(key=lambda c: c.priority, reverse=True)
        return cards
    
    def generate_help_text(
        self, 
        feature_id: str, 
        context: Dict[str, Any]
    ) -> str:
        """
        根据上下文生成个性化帮助文本
        
        Args:
            feature_id: 功能标识符
            context: 上下文信息
        """
        card = self.get_help_card(feature_id)
        
        # 根据上下文调整文本
        tech_level = context.get("tech_level", "intermediate")
        
        if tech_level == "beginner":
            # 新手：更友好的语言
            text = f"💡 **{card.title}**\n\n"
            text += f"看起来您想使用这个功能！让我来帮您设置。\n\n"
            text += f"⏱️ {card.time_estimate}\n\n"
        else:
            # 高级用户：简洁
            text = f"**{card.title}**\n\n"
            text += f"{card.content}\n\n"
        
        return text


# 全局实例
_help: Optional[ContextHelp] = None


def get_context_help() -> ContextHelp:
    """获取上下文帮助系统全局实例"""
    global _help
    if _help is None:
        _help = ContextHelp()
    return _help