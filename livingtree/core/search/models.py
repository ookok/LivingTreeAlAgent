"""
免费网络搜索API分层策略 - 数据模型

定义搜索系统所需的所有数据结构和枚举类型
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, List, Any
from datetime import datetime


class TierLevel(Enum):
    """API层级"""
    TIER_1_CN_HIGH = 1  # 国内高稳定性免费API
    TIER_2_CN_VERTICAL = 2  # 国内专业垂直免费API
    TIER_3_GLOBAL = 3  # 国外免费API
    TIER_4_FALLBACK = 4  # 备用方案


class QueryType(Enum):
    """查询类型分类"""
    NEWS = "news"  # 新闻时效
    KNOWLEDGE = "knowledge"  # 百科知识
    TECHNICAL = "technical"  # 技术问题
    LIFE = "life"  # 生活信息
    ACADEMIC = "academic"  # 学术知识
    ENTERTAINMENT = "entertainment"  # 文化娱乐
    POLICY = "policy"  # 政策法规
    GENERAL = "general"  # 通用查询


class APIStatus(Enum):
    """API状态"""
    HEALTHY = "healthy"  # 健康
    DEGRADED = "degraded"  # 降级（可用但慢）
    FAILING = "failing"  # 失败中
    DISABLED = "disabled"  # 禁用


@dataclass
class APIConfig:
    """API配置"""
    name: str
    tier: TierLevel
    api_url: str
    auth_type: str = "none"  # none, api_key, oauth2
    rate_limit: int = 1000  # 每日限制
    rate_limit_unit: str = "day"  # day, minute, second
    timeout: float = 10.0  # 超时时间（秒）
    retry_count: int = 2  # 重试次数
    weight: float = 1.0  # 权重（用于调度）
    
    # 认证信息
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    
    # 支持的查询类型
    supported_types: List[QueryType] = field(default_factory=list)
    
    # 中文支持
    cn_support: bool = True
    
    # 元数据
    description: str = ""
    documentation: str = ""
    
    def get_rate_per_minute(self) -> int:
        """获取每分钟限制"""
        if self.rate_limit_unit == "minute":
            return self.rate_limit
        elif self.rate_limit_unit == "second":
            return self.rate_limit * 60
        else:  # day
            return self.rate_limit // (24 * 60)
    
    def is_available(self) -> bool:
        """检查API是否可用"""
        return self.weight > 0 and self.tier.value <= 4


@dataclass
class APIHealth:
    """API健康状态"""
    api_name: str
    status: APIStatus = APIStatus.HEALTHY
    
    # 可用性指标
    success_rate: float = 1.0  # 成功率
    avg_response_time: float = 0.0  # 平均响应时间
    p95_response_time: float = 0.0  # P95响应时间
    last_check: datetime = field(default_factory=datetime.now)
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    
    # 额度使用
    quota_used: int = 0
    quota_total: int = 1000
    quota_reset_date: Optional[datetime] = None
    
    # 错误统计
    consecutive_failures: int = 0
    total_requests: int = 0
    failed_requests: int = 0
    
    # 质量评分
    quality_score: float = 0.0  # 0-10
    
    def success_rate_percent(self) -> float:
        """成功率百分比"""
        return self.success_rate * 100
    
    def quota_used_percent(self) -> float:
        """额度使用百分比"""
        return (self.quota_used / self.quota_total * 100) if self.quota_total > 0 else 0
    
    def is_healthy(self) -> bool:
        """是否健康"""
        return (
            self.status == APIStatus.HEALTHY and
            self.success_rate >= 0.9 and
            self.consecutive_failures < 3
        )
    
    def needs_degrade(self) -> bool:
        """是否需要降级"""
        return (
            self.status == APIStatus.DEGRADED or
            self.success_rate < 0.8 or
            self.quota_used_percent() > 80
        )


@dataclass
class SearchResult:
    """搜索结果"""
    title: str
    url: str
    snippet: str
    source: str
    source_url: str = ""  # 来源网站URL
    
    # 元数据
    date: Optional[str] = None
    author: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[str] = None
    
    # 评分
    relevance_score: float = 0.0
    quality_score: float = 0.0
    freshness_score: float = 0.0
    
    # API来源
    api_name: str = ""
    tier: TierLevel = TierLevel.TIER_3_GLOBAL
    
    # 额外信息
    extra_data: Dict[str, Any] = field(default_factory=dict)
    
    # 缓存
    cached_at: Optional[datetime] = None
    is_cached: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source": self.source,
            "source_url": self.source_url,
            "date": self.date,
            "author": self.author,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "relevance_score": self.relevance_score,
            "quality_score": self.quality_score,
            "api_name": self.api_name,
            "tier": self.tier.value,
        }


@dataclass
class FusionResult:
    """融合后的搜索结果"""
    results: List[SearchResult]
    
    # 统计
    total_sources: int = 0
    unique_urls: int = 0
    tier_distribution: Dict[TierLevel, int] = field(default_factory=dict)
    
    # 质量指标
    avg_quality_score: float = 0.0
    avg_relevance_score: float = 0.0
    freshness_score: float = 0.0
    
    # 来源
    sources_used: List[str] = field(default_factory=list)
    
    # 元数据
    query: str = ""
    query_type: QueryType = QueryType.GENERAL
    cached: bool = False
    cache_timestamp: Optional[datetime] = None
    
    def get_top_sources(self, n: int = 5) -> List[str]:
        """获取前N个来源"""
        source_counts = {}
        for r in self.results:
            source_counts[r.source] = source_counts.get(r.source, 0) + 1
        return sorted(source_counts.keys(), key=lambda x: source_counts[x], reverse=True)[:n]


@dataclass 
class QueryContext:
    """查询上下文"""
    query: str
    query_type: QueryType = QueryType.GENERAL
    
    # 查询分析
    keywords: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    intent: str = ""
    
    # 约束条件
    require_cn: bool = False  # 必须中文
    require_recent: bool = False  # 必须最新
    require_official: bool = False  # 必须官方
    
    # 用户偏好
    preferred_sources: List[str] = field(default_factory=list)
    blocked_sources: List[str] = field(default_factory=list)
    
    # 结果要求
    max_results: int = 10
    min_quality_score: float = 0.0
    
    # 原始查询
    original_query: str = ""
    
    @classmethod
    def from_query(cls, query: str) -> "QueryContext":
        """从查询字符串创建上下文"""
        ctx = cls(query=query, original_query=query)
        
        # 基础关键词
        ctx.keywords = query.split()
        
        # 查询类型识别
        query_lower = query.lower()
        
        # 新闻时效关键词
        news_keywords = ["今天", "最新", "刚刚", "新闻", "报道", "2026", "2025"]
        if any(kw in query_lower for kw in news_keywords):
            ctx.query_type = QueryType.NEWS
            ctx.require_recent = True
            
        # 百科知识关键词
        knowledge_keywords = ["是什么", "定义", "百科", "解释", "概念"]
        if any(kw in query_lower for kw in knowledge_keywords):
            ctx.query_type = QueryType.KNOWLEDGE
            
        # 技术问题关键词
        technical_keywords = ["代码", "python", "github", "api", "教程", "bug", "如何"]
        if any(kw in query_lower for kw in technical_keywords):
            ctx.query_type = QueryType.TECHNICAL
            ctx.preferred_sources = ["github.com", "stackoverflow.com"]
            
        # 学术知识关键词
        academic_keywords = ["论文", "研究", "arxiv", "学术", "数据", "实验"]
        if any(kw in query_lower for kw in academic_keywords):
            ctx.query_type = QueryType.ACADEMIC
            ctx.preferred_sources = ["arxiv.org", "cnki.net", "scholar.google.com"]
            
        # 文化娱乐关键词
        entertainment_keywords = ["电影", "书籍", "音乐", "豆瓣", "评分"]
        if any(kw in query_lower for kw in entertainment_keywords):
            ctx.query_type = QueryType.ENTERTAINMENT
            ctx.preferred_sources = ["douban.com", "music.163.com"]
            
        # 政策法规关键词
        policy_keywords = ["政策", "规定", "通知", "条例", "法规", "政府"]
        if any(kw in query_lower for kw in policy_keywords):
            ctx.query_type = QueryType.POLICY
            ctx.require_official = True
            ctx.preferred_sources = ["gov.cn"]
            
        # 生活信息关键词
        life_keywords = ["天气", "地址", "电话", "地图", "位置"]
        if any(kw in query_lower for kw in life_keywords):
            ctx.query_type = QueryType.LIFE
            
        return ctx


@dataclass
class RateLimiter:
    """速率限制器"""
    max_requests: int
    window_seconds: int
    requests: List[datetime] = field(default_factory=list)
    
    def is_allowed(self) -> bool:
        """检查是否允许请求"""
        now = datetime.now()
        cutoff = datetime.timestamp(now) - self.window_seconds
        
        # 清理过期记录
        self.requests = [dt for dt in self.requests if datetime.timestamp(dt) > cutoff]
        
        return len(self.requests) < self.max_requests
    
    def record_request(self):
        """记录请求"""
        self.requests.append(datetime.now())
    
    def get_remaining(self) -> int:
        """获取剩余请求次数"""
        now = datetime.now()
        cutoff = datetime.timestamp(now) - self.window_seconds
        self.requests = [dt for dt in self.requests if datetime.timestamp(dt) > cutoff]
        return max(0, self.max_requests - len(self.requests))
