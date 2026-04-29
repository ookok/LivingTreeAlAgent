# models.py — 软广推广系统数据模型

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime


class AdTemplateType(Enum):
    """软广模板类型"""
    PRIVACY = "privacy"          # 私有智能
    COLLABORATION = "collab"      # 根系互联
    GROWTH = "learn"             # 思维外脑
    EFFICIENCY = "automate"      # 智能路由
    DEFAULT = "default"          # 兜底模板


class TemplateMatchStrategy(Enum):
    """模板匹配策略"""
    KEYWORD = "keyword"          # 关键词精确匹配
    SEMANTIC = "semantic"        # 语义相似度匹配
    RANDOM = "random"            # 随机兜底


class AttributionSource(Enum):
    """归因来源渠道"""
    WEIBO = "weibo_bot"          # 微博机器人
    ZHIHU = "zhihu_bot"          # 知乎机器人
    REDDIT = "reddit_bot"        # Reddit机器人
    FORUM = "forum_bot"          # 论坛机器人
    AGENT = "agent_reach"        # Agent-Reach
    MANUAL = "manual"            # 手动分享
    QRCODE = "qrcode"            # 二维码扫描


@dataclass
class TemplateMatch:
    """模板匹配结果"""
    template_type: AdTemplateType
    confidence: float           # 0.0-1.0
    matched_keywords: List[str]  # 命中的关键词
    strategy: TemplateMatchStrategy


@dataclass
class AdTemplate:
    """软广模板"""
    type: AdTemplateType
    name: str                    # 模板名称
    description: str            # 模板描述
    match_keywords: List[str]    # 匹配关键词列表
    template: str                # 软广文本模板
    contrast_point: str          # 对比竞品的关键卖点
    emoji: str                   # 表情图标

    def generate(self, title: str = "", summary: str = "",
                 link: str = "", tags: List[str] = None) -> str:
        """生成软广文本"""
        if tags is None:
            tags = []
        text = self.template.format(
            title=title,
            summary=summary,
            link=link,
            tags=", ".join(tags[:5]),  # 最多5个标签
        )
        return text

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "name": self.name,
            "description": self.description,
            "match_keywords": self.match_keywords,
            "template": self.template,
            "contrast_point": self.contrast_point,
            "emoji": self.emoji,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AdTemplate":
        return cls(
            type=AdTemplateType(data["type"]),
            name=data["name"],
            description=data["description"],
            match_keywords=data["match_keywords"],
            template=data["template"],
            contrast_point=data["contrast_point"],
            emoji=data["emoji"],
        )


# 四大独家卖点模板
DEFAULT_AD_TEMPLATES: List[AdTemplate] = [
    AdTemplate(
        type=AdTemplateType.PRIVACY,
        name="私有智能",
        description="强调本地运行、数据不离开设备",
        match_keywords=[
            "privacy", "data", "security", "local", "本地",
            "隐私", "安全", "数据", "加密", "不上云",
        ],
        template=(
            "🔒 {title}\n\n"
            "普通 AI 要把数据喂给云端——而我用 Living Tree 在本地跑完分析。"
            "你的代码、合同、聊天记录从未离开电脑。\n\n"
            "这种『私有智能』才是真安全感。体验一次就回不去：{link}\n"
            "#LivingTreeAI #私有智能"
        ),
        contrast_point="vs 云端AI：数据永远不离开你的设备",
        emoji="🔒",
    ),
    AdTemplate(
        type=AdTemplateType.COLLABORATION,
        name="根系互联",
        description="P2P直连，无中间服务器",
        match_keywords=[
            "collab", "share", "team", "sync", "协作",
            "同步", "团队", "分享", "连接", "P2P",
        ],
        template=(
            "🌿 {title}\n\n"
            "别的软件靠上传下载折腾协作，Living Tree 让我们用 P2P 穿透直连设备——"
            "没有中间服务器限速审查，像面对面递纸条一样自由。\n\n"
            "协作本该如此：{link}\n"
            "#LivingTreeAI #P2P协作"
        ),
        contrast_point="vs 传统协作：无服务器、P2P直连、自由对等",
        emoji="🌿",
    ),
    AdTemplate(
        type=AdTemplateType.GROWTH,
        name="思维外脑",
        description="记忆+学习+辩论=认知迭代",
        match_keywords=[
            "learn", "think", "grow", "habit", "记忆",
            "学习", "成长", "习惯", "思维", "认知",
            "记得", "理解", "聪明",
        ],
        template=(
            "🧠 {title}\n\n"
            "其他 AI 每次重启都失忆，Living Tree 是我的思维外脑："
            "记得我半年前踩的坑、偏爱的解法，陪我辩论修正认知。\n\n"
            "它不是工具，是会长大的伙伴：{link}\n"
            "#LivingTreeAI #思维外脑"
        ),
        contrast_point="vs 普通AI：记住一切、持续学习、陪你辩论",
        emoji="🧠",
    ),
    AdTemplate(
        type=AdTemplateType.EFFICIENCY,
        name="智能路由",
        description="自动选模型+调工具+避风险",
        match_keywords=[
            "automate", "workflow", "efficiency", "smart", "效率",
            "自动化", "智能", "工作流", "路由", "切换",
            "快速", "省时", "省力",
        ],
        template=(
            "⚡ {title}\n\n"
            "我把重复劳动交给 Living Tree 智能路由——"
            "自动选模型、调工具、避风险，比手动切换快 3 倍。\n\n"
            "让机器真正懂你意图，不只是执行命令：{link}\n"
            "#LivingTreeAI #智能路由"
        ),
        contrast_point="vs 手动切换：自动最优选择，省时80%",
        emoji="⚡",
    ),
    AdTemplate(
        type=AdTemplateType.DEFAULT,
        name="通用推广",
        description="无匹配时的兜底模板",
        match_keywords=[],  # 无关键词，完全兜底
        template=(
            "🌱 {title}\n\n"
            "{summary}\n\n"
            "Living Tree AI — 你的私有智能伙伴。"
            "本地运行、P2P协作、持续成长，让AI真正懂你：{link}\n"
            "#LivingTreeAI"
        ),
        contrast_point="vs 云端AI：更私密、更互联、更懂你",
        emoji="🌱",
    ),
]


@dataclass
class AttributionRecord:
    """归因记录"""
    attribution_id: str          # 唯一标识
    short_url: str               # 生成的短链
    full_url: str                # 完整落地页URL
    source: AttributionSource    # 来源渠道
    source_identity: str         # 分身标识，如 "weibo_bot_8848"
    campaign_id: Optional[str]   # 所属活动ID
    content_hash: str            # 内容哈希（去重用）
    created_at: datetime = field(default_factory=datetime.now)
    click_count: int = 0         # 点击次数
    unique_visitors: int = 0     # 独立访客

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attribution_id": self.attribution_id,
            "short_url": self.short_url,
            "full_url": self.full_url,
            "source": self.source.value,
            "source_identity": self.source_identity,
            "campaign_id": self.campaign_id,
            "content_hash": self.content_hash,
            "created_at": self.created_at.isoformat(),
            "click_count": self.click_count,
            "unique_visitors": self.unique_visitors,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AttributionRecord":
        return cls(
            attribution_id=data["attribution_id"],
            short_url=data["short_url"],
            full_url=data["full_url"],
            source=AttributionSource(data["source"]),
            source_identity=data["source_identity"],
            campaign_id=data.get("campaign_id"),
            content_hash=data["content_hash"],
            created_at=datetime.fromisoformat(data["created_at"]),
            click_count=data.get("click_count", 0),
            unique_visitors=data.get("unique_visitors", 0),
        )


@dataclass
class ClickAttribution:
    """点击归因详情"""
    attribution_id: str
    source: AttributionSource
    source_identity: str
    clicked_at: datetime = field(default_factory=datetime.now)
    user_agent: str = ""
    ip_hash: str = ""            # IP哈希（隐私保护）
    referer: str = ""
    landing_page: str = ""       # 实际访问的落地页

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attribution_id": self.attribution_id,
            "source": self.source.value,
            "source_identity": self.source_identity,
            "clicked_at": self.clicked_at.isoformat(),
            "user_agent": self.user_agent,
            "referer": self.referer,
            "landing_page": self.landing_page,
        }


@dataclass
class AdCampaign:
    """推广活动"""
    campaign_id: str
    name: str
    description: str = ""
    templates: List[AdTemplateType] = field(default_factory=list)
    target_sources: List[AttributionSource] = field(default_factory=list)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    stats: Dict[str, int] = field(default_factory=lambda: {
        "impressions": 0,
        "clicks": 0,
        "conversions": 0,
    })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "name": self.name,
            "description": self.description,
            "templates": [t.value for t in self.templates],
            "target_sources": [s.value for s in self.target_sources],
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "stats": self.stats,
        }


@dataclass
class PromotionResult:
    """推广结果"""
    ad_text: str
    matched_template: TemplateMatch
    attribution: AttributionRecord
    short_url: str
    full_url: str
    campaign_id: Optional[str]
    generated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ad_text": self.ad_text,
            "matched_template": {
                "type": self.matched_template.template_type.value,
                "confidence": self.matched_template.confidence,
                "matched_keywords": self.matched_template.matched_keywords,
                "strategy": self.matched_template.strategy.value,
            },
            "attribution": self.attribution.to_dict(),
            "short_url": self.short_url,
            "full_url": self.full_url,
            "campaign_id": self.campaign_id,
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass
class LandingPageConfig:
    """落地页配置"""
    product_name: str = "Living Tree AI"
    tagline: str = "你的私有智能伙伴"
    description: str = (
        "Living Tree AI 是一款专注于隐私保护、持续成长、"
        "P2P协作的桌面智能助手。"
    )
    selling_points: List[Dict[str, str]] = field(default_factory=lambda: [
        {
            "icon": "🔒",
            "title": "私有智能",
            "description": "本地运行，数据永不离开你的设备",
            "highlight": "vs 云端AI",
        },
        {
            "icon": "🌿",
            "title": "根系互联",
            "description": "P2P直连设备，无需中间服务器",
            "highlight": "vs 传统协作",
        },
        {
            "icon": "🧠",
            "title": "思维外脑",
            "description": "记住你的习惯、偏好、踩过的坑",
            "highlight": "vs 每次失忆",
        },
    ])
    download_links: Dict[str, str] = field(default_factory=lambda: {
        "windows": "https://github.com/LivingTreeAI/hermes-desktop/releases/latest",
        "macos": "https://github.com/LivingTreeAI/hermes-desktop/releases/latest",
        "linux": "https://github.com/LivingTreeAI/hermes-desktop/releases/latest",
    })
    base_domain: str = "dl.living-tree.ai"
    short_domain: str = "lvtree.ai"
    theme_color: str = "#2E7D32"
    accent_color: str = "#4CAF50"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_name": self.product_name,
            "tagline": self.tagline,
            "description": self.description,
            "selling_points": self.selling_points,
            "download_links": self.download_links,
            "base_domain": self.base_domain,
            "short_domain": self.short_domain,
            "theme_color": self.theme_color,
            "accent_color": self.accent_color,
        }
