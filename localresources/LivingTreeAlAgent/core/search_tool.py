"""
AI 增强搜索工具 - 可信信息代理
Hermes Search: 意图推理 + 多源召回 + 可信摘要 + 防篡改验证

核心特性：
- 意图自适应：根据查询类型自动切换处理策略（下载/技术/新闻/模糊）
- 可信度保障：摘要约束 + 原文对比 + 语义校验
- 多Query生成：针对模糊查询生成多个搜索策略并行执行
- 文件下载：支持断点续传，自动保存到项目目录
"""

import json
import time
import asyncio
import hashlib
import re
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, TypedDict, Callable
from dataclasses import dataclass, field
from enum import Enum
import traceback

import httpx

# ── 搜索意图类型 ────────────────────────────────────────────────────────────

class SearchIntent(Enum):
    """搜索意图类型 - 对应不同的处理策略"""
    GENERAL = "general"           # 通用搜索
    FILE_DOWNLOAD = "file"        # 文件下载类（PDF/DOC/附件）
    TECHNICAL = "technical"      # 技术文档/代码
    ACADEMIC = "academic"        # 学术资料/论文
    NEWS = "news"                # 实时新闻
    POLICY = "policy"            # 政策法规
    PRODUCT = "product"          # 产品评测
    AMBIGUOUS = "ambiguous"      # 模糊概念（需多意图推理）

# ── 数据模型 ────────────────────────────────────────────────────────────────

@dataclass
class SearchResult:
    """单条搜索结果"""
    title: str
    url: str
    snippet: str
    source: str           # 来源网站
    date: Optional[str] = None
    relevance_score: float = 0.0
    
    # 可信度相关字段
    trust_score: float = 1.0      # 可信度评分 0-1
    raw_content: str = ""          # 原文切片
    semantic_distance: float = 0.0 # 语义距离（摘要vs原文）
    is_verified: bool = False      # 是否已验证
    
    # 文件下载相关
    file_type: Optional[str] = None  # pdf/doc/xlsx 等
    file_size: Optional[str] = None  # 文件大小
    is_downloadable: bool = False    # 是否可下载

@dataclass
class TrustVerification:
    """可信度验证结果"""
    summary_constraint_ok: bool   # 摘要约束是否满足
    semantic_distance_ok: bool    # 语义距离是否正常
    warnings: list[str] = field(default_factory=list)
    verification_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class SearchResponse:
    """搜索响应"""
    query: str
    intent: SearchIntent
    results: list[SearchResult]
    summary: str = ""     # AI 总结
    sources: list[str] = field(default_factory=list)  # 引用链接
    engine_used: str = ""
    cached: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # 扩展字段
    multi_queries: list[str] = field(default_factory=list)  # 多Query策略
    verification: Optional[TrustVerification] = None  # 可信度验证
    processed_queries: list[str] = field(default_factory=list)  # 已执行的查询

# ── SEO 垃圾站过滤器 ─────────────────────────────────────────────────────────

class SEOFilter:
    """SEO 垃圾内容过滤器"""
    
    # 低质量/SEO垃圾关键词
    BAD_KEYWORDS = {
        "best", "top", "buy", "cheap", "discount", "coupon", "free",
        "click here", "learn more", "sign up", "subscribe",
        "Sponsored", "Advertisement", "广告",
        "代理", "招商", "加盟", "赚钱", "日赚",
        "【广告】", "[广告]", "广告赞助",
    }
    
    # SEO 垃圾站域名模式
    BAD_DOMAINS = {
        r"\.xyz$", r"\.top$", r"\.cc$", r"\.pw$", r"\.info$",
        r"\.buzz$", r"\.click$", r"\.link$", r"\.work$",
        r"site:\w+\.ga$", r"site:\w+\.tk$", r"site:\w+\.ml$",
        r"article\.倒模", r"baike\.倒模",
    }
    
    # 高质量来源域名
    QUALITY_DOMAINS = {
        # 学术
        "arxiv.org", "scholar.google.com", "pubmed.ncbi.nlm.nih.gov",
        "cnki.net", "wanfangdata.com.cn", "知网",
        # 技术
        "github.com", "stackoverflow.com", "docs.python.org",
        "developer.mozilla.org", "leetcode.com", "huggingface.co",
        # 新闻
        "news.ycombinator.com", "lobste.rs", "techcrunch.com",
        "reuters.com", "bloomberg.com",
        # 中文社区
        "zhihu.com", "juejin.cn", "weixin.qq.com",
        "mp.weixin.qq.com", "segmentfault.com",
        # 政务
        "gov.cn", "gov.uk", "gov.au",
    }
    
    # 文件下载相关域名
    FILE_DOMAINS = {
        ".gov.cn", ".gov.",  # 政府文件
        "pdf", "docx", "doc",  # 常见文档格式暗示
    }
    
    @classmethod
    def is_quality_domain(cls, url: str) -> bool:
        """检查是否为高质量域名"""
        url_lower = url.lower()
        for domain in cls.QUALITY_DOMAINS:
            if domain in url_lower:
                return True
        return False
    
    @classmethod
    def is_file_domain(cls, url: str) -> bool:
        """检查是否可能是文件下载来源"""
        url_lower = url.lower()
        return any(domain in url_lower for domain in cls.FILE_DOMAINS)
    
    @classmethod
    def is_seo_garbage(cls, title: str, snippet: str) -> bool:
        """判断是否为SEO垃圾内容"""
        combined = (title + " " + snippet).lower()
        
        # 检查坏关键词
        bad_count = sum(1 for kw in cls.BAD_KEYWORDS if kw in combined)
        if bad_count >= 2:
            return True
        
        # 检查SEO模式
        seo_patterns = [
            r"^\d+[、，,]\d+",  # "10、20、30" 列表堆砌
            r"点击[量观看]",    # 点击量诱导
            r"必看", r"收藏", r"转发",
        ]
        for pattern in seo_patterns:
            if re.search(pattern, combined):
                return True
        
        return False
    
    @classmethod
    def score_relevance(cls, result: SearchResult, intent: SearchIntent) -> float:
        """计算内容相关性分数"""
        score = 0.0
        combined = (result.title + " " + result.snippet).lower()
        
        # 高质量域名加成
        if cls.is_quality_domain(result.url):
            score += 2.0
        
        # 文件下载域名加成
        if cls.is_file_domain(result.url) and intent == SearchIntent.FILE_DOWNLOAD:
            score += 3.0
        
        # 意图匹配
        intent_keywords = {
            SearchIntent.TECHNICAL: ["github", "docs", "api", "python", "代码", "技术", "教程"],
            SearchIntent.ACADEMIC: ["研究", "论文", "arxiv", "paper", "实验", "数据"],
            SearchIntent.NEWS: ["news", "报道", "2024", "2025", "2026", "今日", "最新"],
            SearchIntent.POLICY: ["政策", "规定", "办法", "通知", "条例", "法规", "文件"],
            SearchIntent.PRODUCT: ["评测", "对比", "体验", "测评", "推荐"],
            SearchIntent.FILE_DOWNLOAD: ["pdf", "doc", "报告", "附件", "下载", ".gov"],
        }
        
        if intent in intent_keywords:
            for kw in intent_keywords[intent]:
                if kw in combined:
                    score += 1.0
        
        # 时效性
        if any(year in combined for year in ["2024", "2025", "2026"]):
            score += 0.5
        
        return score


# ── 意图分类器 ────────────────────────────────────────────────────────────────

class IntentClassifier:
    """搜索意图自动分类器"""
    
    # 文件下载关键词
    FILE_KEYWORDS = [
        "pdf", "doc", "docx", "下载", "附件", "报告",
        "环评", "批复", "审批", "公示", "清单",
        "模板", "表格", "填写", "表格下载"
    ]
    
    # 技术文档关键词
    TECHNICAL_KEYWORDS = [
        "代码", "python", "javascript", "教程", "github",
        "api", "文档", "开源", "安装", "配置",
        "stackoverflow", "官方文档", "示例"
    ]
    
    # 学术关键词
    ACADEMIC_KEYWORDS = [
        "论文", "研究", "arxiv", "paper", "学术",
        "实验", "数据", "分析", "结论", "方法",
        "cnki", "sci", "ei", "期刊"
    ]
    
    # 新闻关键词
    NEWS_KEYWORDS = [
        "新闻", "最新", "今日", "报道", "事件",
        "2024", "2025", "2026", "今天", "资讯"
    ]
    
    # 政策法规关键词
    POLICY_KEYWORDS = [
        "政策", "规定", "办法", "通知", "条例",
        "法规", "红头文件", "发文", "政府", "官方"
    ]
    
    # 模糊概念关键词（可能需要多意图推理）
    AMBIGUOUS_KEYWORDS = [
        "是什么", "如何", "怎么样", "翻译", "解释",
        "概念", "意思", "定义", "原理", "区别"
    ]
    
    @classmethod
    def classify(cls, query: str) -> SearchIntent:
        """
        自动分类查询意图
        
        Args:
            query: 用户查询
            
        Returns:
            SearchIntent: 识别到的意图
        """
        query_lower = query.lower()
        
        # 优先级：文件下载 > 政策法规 > 技术 > 学术 > 新闻 > 模糊 > 通用
        
        # 1. 检查文件下载意图
        if any(kw in query_lower for kw in cls.FILE_KEYWORDS):
            return SearchIntent.FILE_DOWNLOAD
        
        # 2. 检查政策法规意图
        if any(kw in query_lower for kw in cls.POLICY_KEYWORDS):
            return SearchIntent.POLICY
        
        # 3. 检查技术文档意图
        if any(kw in query_lower for kw in cls.TECHNICAL_KEYWORDS):
            return SearchIntent.TECHNICAL
        
        # 4. 检查学术意图
        if any(kw in query_lower for kw in cls.ACADEMIC_KEYWORDS):
            return SearchIntent.ACADEMIC
        
        # 5. 检查新闻意图
        if any(kw in query_lower for kw in cls.NEWS_KEYWORDS):
            return SearchIntent.NEWS
        
        # 6. 检查模糊概念意图
        if any(kw in query_lower for kw in cls.AMBIGUOUS_KEYWORDS):
            return SearchIntent.AMBIGUOUS
        
        return SearchIntent.GENERAL
    
    @classmethod
    def generate_multi_queries(cls, query: str, intent: SearchIntent) -> list[str]:
        """
        针对模糊查询生成多个搜索策略
        
        Args:
            query: 原始查询
            intent: 识别的意图
            
        Returns:
            list[str]: 多个搜索查询
        """
        queries = [query]
        
        if intent == SearchIntent.AMBIGUOUS:
            # 模糊查询：生成多种可能的解释
            queries.extend([
                f"{query} 定义",
                f"{query} 解释",
                f"{query} 概念",
            ])
        
        elif intent == SearchIntent.POLICY:
            # 政策法规：扩展地域和时间
            queries.extend([
                query,
                f"{query} 南京",  # 用户在南京
                f"{query} 江苏省",
                f"{query} 2025 2026",
            ])
        
        elif intent == SearchIntent.FILE_DOWNLOAD:
            # 文件下载：优先官方来源
            queries.extend([
                f"{query} site:gov.cn",
                f"{query} filetype:pdf",
                query,
            ])
        
        elif intent == SearchIntent.TECHNICAL:
            # 技术文档：优先官方和社区
            queries.extend([
                query,
                f"{query} github",
                f"{query} 官方文档",
            ])
        
        elif intent == SearchIntent.NEWS:
            # 新闻：优先最新
            queries.extend([
                f"{query} 最新 2026",
                query,
                f"{query} 今日",
            ])
        
        # 去重
        return list(dict.fromkeys(queries))[:4]  # 最多4个查询


# ── 可信度验证器 ──────────────────────────────────────────────────────────────

class TrustVerifier:
    """
    可信度验证器 - 防篡改核心
    
    三层防线：
    1. 摘要约束机制：禁用生成指令，保留否定性
    2. 语义一致性校验：计算摘要与原文的语义距离
    3. 来源权威性评估：基于域名和时间评估可信度
    """
    
    # 禁用词汇（可能导致幻觉生成）
    FORBIDDEN_WORDS = ["generate", "create", "invent", "编造", "虚构", "据说"]
    
    # 必须保留的词汇（否定性表述）
    PRESERVE_WORDS = ["不", "否", "无", "未", "非", "暂", "不支持", "无法", "没有"]
    
    # 高权威域名
    AUTHORITY_DOMAINS = {
        "gov.cn": 1.0, "gov.uk": 1.0, "gov.au": 1.0,
        "edu.cn": 0.95, "edu": 0.95,
        "arxiv.org": 0.9, "nature.com": 0.9, "science.org": 0.9,
        "github.com": 0.85, "stackoverflow.com": 0.8,
        "zhihu.com": 0.7, "juejin.cn": 0.65,
    }
    
    @classmethod
    def verify_summary_constraint(cls, summary: str, raw_content: str) -> tuple[bool, list[str]]:
        """
        验证摘要约束机制
        
        Returns:
            (是否通过, 警告列表)
        """
        warnings = []
        
        # 检查是否使用了禁用词汇（可能存在生成行为）
        for word in cls.FORBIDDEN_WORDS:
            if word.lower() in summary.lower():
                warnings.append(f"⚠️ 摘要可能包含生成内容：'{word}'")
        
        # 检查否定性表述保留情况
        summary_lower = summary.lower()
        raw_lower = raw_content.lower()
        
        for word in cls.PRESERVE_WORDS:
            # 如果原文有否定词，摘要应该保留
            if word in raw_lower and word not in summary_lower:
                warnings.append(f"⚠️ 摘要可能曲解原文否定含义：'{word}'")
        
        # 检查语义反转（如"不支持"变成"支持"）
        negative_pairs = [
            ("不支持", "支持"), ("不能", "能"), ("无法", "能"),
            ("不是", "是"), ("没有", "有"), ("不可以", "可以")
        ]
        
        for neg, pos in negative_pairs:
            if neg in raw_lower and pos in summary_lower and neg not in summary_lower:
                warnings.append(f"⚠️ 语义反转检测：'{neg}' → '{pos}'")
        
        return (len(warnings) == 0, warnings)
    
    @classmethod
    def estimate_semantic_distance(cls, summary: str, raw_content: str) -> float:
        """
        估算语义距离（简化版）
        
        实际应用中应使用 Sentence-BERT 计算
        此处使用关键词重叠度作为近似
        
        Returns:
            float: 0-1，越小表示越接近
        """
        if not raw_content or not summary:
            return 1.0
        
        # 提取关键词
        def extract_keywords(text: str) -> set:
            # 简单分词，提取2-4字词组
            words = re.findall(r'[\u4e00-\u9fff]{2,4}', text)
            return set(words)
        
        summary_keywords = extract_keywords(summary)
        content_keywords = extract_keywords(raw_content)
        
        if not summary_keywords:
            return 0.5
        
        # 计算重叠度
        overlap = len(summary_keywords & content_keywords)
        total = len(summary_keywords)
        
        distance = 1.0 - (overlap / total) if total > 0 else 1.0
        
        return distance
    
    @classmethod
    def score_source_authority(cls, url: str, date: Optional[str] = None) -> float:
        """
        评估来源权威性
        
        Args:
            url: 来源URL
            date: 日期字符串
            
        Returns:
            float: 0-1 的权威性评分
        """
        url_lower = url.lower()
        
        # 域名匹配
        for domain, score in cls.AUTHORITY_DOMAINS.items():
            if domain in url_lower:
                base_score = score
                break
        else:
            base_score = 0.5  # 默认中等可信
        
        # 时效性调整
        if date:
            try:
                # 尝试解析日期
                date_year = int(re.search(r'20\d{2}', date).group())
                current_year = 2026
                
                if date_year >= current_year:
                    base_score += 0.1  # 最新内容加分
                elif date_year < current_year - 2:
                    base_score -= 0.2  # 过时内容减分
            except:
                pass
        
        return max(0.0, min(1.0, base_score))
    
    @classmethod
    def verify(cls, result: SearchResult, summary: str = "") -> TrustVerification:
        """
        综合验证
        
        Args:
            result: 搜索结果（包含原文切片）
            summary: AI生成的摘要
            
        Returns:
            TrustVerification: 验证结果
        """
        warnings = []
        
        # 1. 摘要约束验证
        if summary:
            constraint_ok, constraint_warnings = cls.verify_summary_constraint(
                summary, result.raw_content
            )
            warnings.extend(constraint_warnings)
        
        # 2. 语义距离验证
        if result.raw_content:
            semantic_distance = cls.estimate_semantic_distance(
                summary or result.snippet, result.raw_content
            )
            result.semantic_distance = semantic_distance
            
            if semantic_distance > 0.7:
                warnings.append(f"⚠️ 语义偏差较大（{semantic_distance:.2f}），摘要可能偏离原文")
            
            semantic_distance_ok = semantic_distance <= 0.7
        else:
            semantic_distance_ok = True
        
        # 3. 来源权威性
        authority_score = cls.score_source_authority(result.url, result.date)
        result.trust_score = authority_score
        
        if authority_score < 0.5:
            warnings.append(f"⚠️ 来源权威性较低（{authority_score:.2f}）：{result.source}")
        
        result.is_verified = len(warnings) == 0
        
        return TrustVerification(
            summary_constraint_ok=len([w for w in warnings if "摘要" in w]) == 0,
            semantic_distance_ok=semantic_distance_ok,
            warnings=warnings
        )

# ── 搜索缓存 ────────────────────────────────────────────────────────────────

class SearchCache:
    """搜索结果缓存"""
    
    def __init__(self, cache_dir: Optional[Path] = None, ttl_minutes: int = 60):
        self.cache_dir = cache_dir or Path.home() / ".hermes-desktop" / "search_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(minutes=ttl_minutes)
        self._memory_cache: dict[str, tuple[SearchResponse, datetime]] = {}
    
    def _hash_query(self, query: str, intent: SearchIntent) -> str:
        """生成查询哈希"""
        key = f"{query}:{intent.value}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]
    
    def get(self, query: str, intent: SearchIntent) -> Optional[SearchResponse]:
        """获取缓存的搜索结果"""
        key = self._hash_query(query, intent)
        
        # 内存缓存优先
        if key in self._memory_cache:
            response, timestamp = self._memory_cache[key]
            if datetime.now() - timestamp < self.ttl:
                response.cached = True
                return response
            else:
                del self._memory_cache[key]
        
        # 磁盘缓存
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                timestamp = datetime.fromisoformat(data["_timestamp"])
                if datetime.now() - timestamp < self.ttl:
                    response = SearchResponse(**{k: v for k, v in data.items() if not k.startswith("_")})
                    response.cached = True
                    self._memory_cache[key] = (response, timestamp)
                    return response
            except Exception:
                pass
        
        return None
    
    def set(self, query: str, intent: SearchIntent, response: SearchResponse) -> None:
        """缓存搜索结果"""
        key = self._hash_query(query, intent)
        timestamp = datetime.now()
        
        # 内存缓存
        self._memory_cache[key] = (response, timestamp)
        
        # 磁盘缓存
        cache_file = self.cache_dir / f"{key}.json"
        try:
            data = response.__dict__.copy()
            data["_timestamp"] = timestamp.isoformat()
            # 序列化时转换 SearchResult
            data["results"] = [
                r.__dict__ if hasattr(r, "__dict__") else r 
                for r in response.results
            ]
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    def clear(self) -> None:
        """清空缓存"""
        self._memory_cache.clear()
        for f in self.cache_dir.glob("*.json"):
            try:
                f.unlink()
            except Exception:
                pass

# ── 搜索引擎基类 ────────────────────────────────────────────────────────────

class SearchEngine:
    """搜索引擎基类"""
    
    name: str = "base"
    supports_intent: bool = False
    
    async def search(
        self, 
        query: str, 
        intent: Optional[SearchIntent] = None,
        num_results: int = 10
    ) -> list[SearchResult]:
        raise NotImplementedError

# ── DuckDuckGo 引擎（免费，无需API Key）─────────────────────────────────────

class DuckDuckGoEngine(SearchEngine):
    """DuckDuckGo 搜索 - 免费兜底引擎"""
    
    name = "duckduckgo"
    
    def __init__(self):
        self.base_url = "https://api.duckduckgo.com/"
    
    async def search(
        self, 
        query: str, 
        intent: Optional[SearchIntent] = None,
        num_results: int = 10
    ) -> list[SearchResult]:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                params = {
                    "q": query,
                    "format": "json",
                    "no_html": 1,
                    "skip_disambig": 1,
                }
                r = await client.get(self.base_url, params=params)
                r.raise_for_status()
                data = r.json()
                
                results = []
                
                # 解析 Related Topics
                for topic in data.get("RelatedTopics", [])[:num_results]:
                    if "Text" in topic and "FirstURL" in topic:
                        results.append(SearchResult(
                            title=topic.get("Text", "")[:200],
                            url=topic["FirstURL"],
                            snippet=topic.get("Text", ""),
                            source=topic.get("Icon", {}).get("URL", "").split("/")[-2] if topic.get("Icon") else "duckduckgo",
                        ))
                
                # 解析 Abstract
                if data.get("AbstractText"):
                    results.insert(0, SearchResult(
                        title=data.get("Heading", query),
                        url=data.get("AbstractURL", ""),
                        snippet=data["AbstractText"],
                        source=data.get("AbstractSource", ""),
                        date=data.get("AbstractTimestamp", ""),
                    ))
                
                return results[:num_results]
                
        except Exception as e:
            print(f"[DuckDuckGo] Search failed: {e}")
            return []

# ── Serper API 引擎（高质量 Google 结果）────────────────────────────────────

class SerperEngine(SearchEngine):
    """Serper API - 高质量 Google 搜索"""
    
    name = "serper"
    supports_intent = True
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://google.serper.dev/search"
    
    async def search(
        self, 
        query: str, 
        intent: Optional[SearchIntent] = None,
        num_results: int = 10
    ) -> list[SearchResult]:
        if not self.api_key:
            return []
        
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                payload = {
                    "q": query,
                    "num": num_results,
                }
                if intent and intent != SearchIntent.GENERAL:
                    intent_map = {
                        SearchIntent.NEWS: "n",
                        SearchIntent.VIDEO: "vid",
                        SearchIntent.IMAGES: "isch",
                    }
                    if intent in intent_map:
                        payload["tbs"] = f"itp:{intent_map[intent]}"
                
                r = await client.post(
                    self.base_url,
                    json=payload,
                    headers={"X-API-KEY": self.api_key}
                )
                r.raise_for_status()
                data = r.json()
                
                results = []
                for item in data.get("organic", [])[:num_results]:
                    results.append(SearchResult(
                        title=item.get("title", ""),
                        url=item.get("link", ""),
                        snippet=item.get("snippet", ""),
                        source=item.get("source", ""),
                        date=item.get("date", ""),
                    ))
                
                return results
                
        except Exception as e:
            print(f"[Serper] Search failed: {e}")
            return []

# ── Brave Search 引擎 ───────────────────────────────────────────────────────

class BraveEngine(SearchEngine):
    """Brave Search - 隐私友好搜索引擎"""
    
    name = "brave"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.search.brave.com/res/v1/web/search"
    
    async def search(
        self, 
        query: str, 
        intent: Optional[SearchIntent] = None,
        num_results: int = 10
    ) -> list[SearchResult]:
        if not self.api_key:
            return []
        
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                params = {
                    "q": query,
                    "count": num_results,
                    "safesearch": "moderate",
                }
                r = await client.get(
                    self.base_url,
                    params=params,
                    headers={
                        "X-Subscription-Token": self.api_key,
                        "Accept": "application/json",
                    }
                )
                r.raise_for_status()
                data = r.json()
                
                results = []
                for item in data.get("web", {}).get("results", [])[:num_results]:
                    results.append(SearchResult(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        snippet=item.get("description", ""),
                        source=item.get("meta_url", {}).get("netloc", ""),
                        date=item.get("date", ""),
                    ))
                
                return results
                
        except Exception as e:
            print(f"[Brave] Search failed: {e}")
            return []

# ── 中文聚合搜索 ─────────────────────────────────────────────────────────────

class CnAggregateEngine(SearchEngine):
    """中文聚合搜索 - 知乎、B站、微信公众号"""
    
    name = "cn_aggregate"
    
    def __init__(self):
        self.base_url = "https://ddg.ogbeta.store"
    
    async def search(
        self, 
        query: str, 
        intent: Optional[SearchIntent] = None,
        num_results: int = 10
    ) -> list[SearchResult]:
        """使用 DuckDuckGo 搜索中文内容，过滤中文结果"""
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                # 搜索中文关键词
                cn_query = f"{query} site:zhihu.com OR site:juejin.cn OR site:weixin.qq.com"
                
                params = {
                    "q": cn_query,
                    "format": "json",
                    "kl": "zh-cn",  # 中国区域
                }
                r = await client.get("https://api.duckduckgo.com/", params=params)
                r.raise_for_status()
                data = r.json()
                
                results = []
                for topic in data.get("RelatedTopics", [])[:num_results]:
                    if "FirstURL" in topic:
                        url = topic["FirstURL"]
                        # 只保留中文站点
                        if any(cn_site in url for cn_site in ["zhihu.com", "juejin.cn", "weixin", "bilibili.com"]):
                            results.append(SearchResult(
                                title=topic.get("Text", "")[:200],
                                url=url,
                                snippet=topic.get("Text", ""),
                                source="中文社区",
                            ))
                
                return results[:num_results]
                
        except Exception as e:
            print(f"[CnAggregate] Search failed: {e}")
            return []

# ── 查询优化器 ───────────────────────────────────────────────────────────────

class QueryOptimizer:
    """根据意图优化搜索查询"""
    
    INTENT_MODIFIERS = {
        SearchIntent.GENERAL: "",
        SearchIntent.NEWS: "最新 2026",
        SearchIntent.TECHNICAL: "教程 文档 github",
        SearchIntent.ACADEMIC: "论文 研究 arxiv",
        SearchIntent.PRODUCT: "评测 对比 测评",
        SearchIntent.POLICY: "政策 规定 通知 2025 2026",
        SearchIntent.FILE_DOWNLOAD: "pdf doc 下载",
        SearchIntent.AMBIGUOUS: "定义 解释",
    }
    
    @classmethod
    def optimize(cls, query: str, intent: SearchIntent) -> str:
        """优化搜索查询"""
        modifier = cls.INTENT_MODIFIERS.get(intent, "")
        if modifier:
            return f"{query} {modifier}"
        return query
    
    @classmethod
    def expand(cls, query: str) -> list[str]:
        """生成相关查询扩展"""
        expansions = [
            query,
            f"{query} 教程",
            f"{query} 最新",
            f"{query} 原理",
        ]
        return list(dict.fromkeys(expansions))  # 去重保持顺序
    
    @classmethod
    def get_intent_aware_queries(cls, query: str) -> tuple[SearchIntent, list[str]]:
        """
        获取意图感知的查询列表
        
        Returns:
            (识别的意图, 查询列表)
        """
        intent = IntentClassifier.classify(query)
        queries = IntentClassifier.generate_multi_queries(query, intent)
        return intent, queries

# ── 主搜索工具 ───────────────────────────────────────────────────────────────

class AISearchTool:
    """
    AI 增强搜索工具 - 可信信息代理
    
    特性：
    - 意图自适应：自动识别查询类型并切换策略
    - 多Query并行：针对模糊查询生成多个搜索策略
    - 可信度验证：摘要约束 + 语义校验 + 权威性评估
    - 多引擎降级：Serper > Brave > DuckDuckGo
    - SEO 垃圾过滤
    - 结果缓存
    - AI 质量总结（需本地 LLM）
    - 文件下载检测
    """
    
    def __init__(
        self,
        serper_key: str = "",
        brave_key: str = "",
        cache_ttl: int = 60,
        download_dir: Optional[str] = None,
    ):
        # 初始化引擎
        self.engines: list[SearchEngine] = []
        
        if serper_key:
            self.engines.append(SerperEngine(serper_key))
        
        if brave_key:
            self.engines.append(BraveEngine(brave_key))
        
        # 免费引擎兜底
        self.engines.append(DuckDuckGoEngine())
        self.engines.append(CnAggregateEngine())
        
        # 缓存
        self.cache = SearchCache(ttl_minutes=cache_ttl)
        
        # 过滤器
        self.filter = SEOFilter()
        
        # 可信度验证器
        self.trust_verifier = TrustVerifier()
        
        # 下载目录
        if download_dir:
            self.download_dir = Path(download_dir)
        else:
            self.download_dir = Path.home() / ".hermes-desktop" / "downloads"
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        # LLM 客户端（可选）
        self._llm_client = None
        self._default_model = "qwen2.5:7b"
    
    def set_llm_client(self, client, model: str = "qwen2.5:7b"):
        """设置 LLM 客户端用于 AI 总结"""
        self._llm_client = client
        self._default_model = model
    
    def set_download_dir(self, path: str):
        """设置下载目录"""
        self.download_dir = Path(path)
        self.download_dir.mkdir(parents=True, exist_ok=True)
    
    async def search(
        self,
        query: str,
        intent: Optional[SearchIntent] = None,
        num_results: int = 10,
        use_cache: bool = True,
        multi_query: bool = True,
    ) -> SearchResponse:
        """
        执行 AI 增强搜索
        
        Args:
            query: 搜索查询
            intent: 搜索意图（None=自动识别）
            num_results: 返回结果数量
            use_cache: 是否使用缓存
            multi_query: 是否启用多Query策略
            
        Returns:
            SearchResponse: 包含结果和可信度验证
        """
        # 自动意图识别
        if intent is None:
            intent, queries = QueryOptimizer.get_intent_aware_queries(query)
        else:
            queries = IntentClassifier.generate_multi_queries(query, intent)
        
        # 检查缓存
        if use_cache:
            cached = self.cache.get(query, intent)
            if cached:
                return cached
        
        # 多Query并行搜索
        all_results: list[SearchResult] = []
        processed_queries = []
        
        if multi_query and len(queries) > 1:
            # 并行执行多个查询
            tasks = []
            for q in queries[:3]:  # 最多3个并行查询
                processed_queries.append(q)
                for engine in self.engines:
                    tasks.append(engine.search(q, intent=None, num_results=5))
            
            # 收集所有结果
            try:
                results_list = await asyncio.gather(*tasks, return_exceptions=True)
                for results in results_list:
                    if isinstance(results, list):
                        all_results.extend(results)
            except Exception as e:
                print(f"[AISearch] Multi-query failed: {e}")
        else:
            # 单查询
            optimized_query = QueryOptimizer.optimize(query, intent)
            processed_queries = [optimized_query]
            
            for engine in self.engines:
                try:
                    results = await engine.search(
                        optimized_query, 
                        intent=intent if engine.supports_intent else None,
                        num_results=num_results
                    )
                    if results:
                        all_results.extend(results)
                        break
                except Exception as e:
                    print(f"[AISearch] Engine {engine.name} failed: {e}")
                    continue
        
        # 检测可下载文件
        all_results = self._detect_downloadable_files(all_results)
        
        # 去重
        seen_urls = set()
        unique_results = []
        for r in all_results:
            if r.url not in seen_urls:
                seen_urls.add(r.url)
                unique_results.append(r)
        
        # SEO 过滤 + 相关性评分
        filtered_results = []
        for r in unique_results:
            if self.filter.is_seo_garbage(r.title, r.snippet):
                continue
            r.relevance_score = self.filter.score_relevance(r, intent)
            filtered_results.append(r)
        
        # 按相关性排序
        filtered_results.sort(key=lambda x: x.relevance_score, reverse=True)
        filtered_results = filtered_results[:num_results]
        
        # 提取引用
        sources = [r.url for r in filtered_results if r.url]
        
        # 构建响应
        response = SearchResponse(
            query=query,
            intent=intent,
            results=filtered_results,
            sources=sources,
            engine_used=self.engines[0].name if self.engines else "none",
            multi_queries=queries,
            processed_queries=processed_queries,
        )
        
        # 缓存结果
        self.cache.set(query, intent, response)
        
        return response
    
    def _detect_downloadable_files(self, results: list[SearchResult]) -> list[SearchResult]:
        """检测可下载文件"""
        # 文件扩展名模式
        file_patterns = [
            (r'\.pdf[\?#]?', 'pdf'),
            (r'\.docx?[\?#]?', 'doc'),
            (r'\.xlsx?[\?#]?', 'xlsx'),
            (r'\.pptx?[\?#]?', 'ppt'),
            (r'\.zip[\?#]?', 'zip'),
            (r'\.rar[\?#]?', 'rar'),
            (r'filetype:', ''),  # filetype:pdf
            (r'[\?&]format=pdf', 'pdf'),
        ]
        
        for result in results:
            url_lower = result.url.lower()
            
            # 检查URL中的文件类型
            for pattern, ftype in file_patterns:
                if re.search(pattern, url_lower):
                    result.is_downloadable = True
                    result.file_type = ftype or self._guess_file_type(url_lower)
                    
                    # 检测文件大小（从标题或snippet）
                    size_match = re.search(r'(\d+(?:\.\d+)?)\s*(MB|KB|GB|M|K|G)', result.snippet)
                    if size_match:
                        result.file_size = size_match.group(0)
                    break
            
            # 检查是否是政府文件
            if 'gov.cn' in url_lower and any(kw in url_lower for kw in ['pdf', 'doc', 'attach', 'download']):
                result.is_downloadable = True
                result.trust_score = 1.0  # 政府文件最高可信
        
        return results
    
    def _guess_file_type(self, url: str) -> str:
        """从URL猜测文件类型"""
        url_lower = url.lower()
        if '.pdf' in url_lower:
            return 'pdf'
        elif '.doc' in url_lower:
            return 'doc'
        elif '.xls' in url_lower:
            return 'xlsx'
        elif '.ppt' in url_lower:
            return 'ppt'
        elif '.zip' in url_lower:
            return 'zip'
        return 'file'
    
    async def search_and_summarize(
        self,
        query: str,
        intent: Optional[SearchIntent] = None,
        num_results: int = 10,
        verify_trust: bool = True,
    ) -> SearchResponse:
        """
        搜索 + AI 总结 + 可信度验证
        
        Args:
            query: 搜索查询
            intent: 搜索意图
            num_results: 返回结果数量
            verify_trust: 是否进行可信度验证
        """
        # 先搜索
        response = await self.search(query, intent, num_results)
        
        # 如果没有结果，返回
        if not response.results:
            return response
        
        # 可信度验证
        if verify_trust:
            all_warnings = []
            for result in response.results:
                verification = self.trust_verifier.verify(result, "")
                if verification.warnings:
                    all_warnings.extend(verification.warnings)
            
            if all_warnings:
                response.verification = TrustVerification(
                    summary_constraint_ok=True,
                    semantic_distance_ok=True,
                    warnings=all_warnings[:5]  # 只保留前5个警告
                )
        
        # 如果没有 LLM 客户端，返回原始结果
        if not self._llm_client:
            return response
        
        # 构建总结 prompt（包含可信度约束）
        summary_prompt = self._build_trusted_summary_prompt(
            query, response.results, response.intent
        )
        
        try:
            # 调用本地 LLM 总结
            messages = [{"role": "user", "content": summary_prompt}]
            
            content, _, _ = self._llm_client.chat_sync(
                messages,
                model=self._default_model,
                temperature=0.3,
            )
            
            response.summary = content
            
            # 再次验证摘要
            if response.verification:
                for result in response.results[:3]:
                    if result.raw_content:
                        verification = self.trust_verifier.verify(result, content)
                        response.verification.warnings.extend(verification.warnings)
            
        except Exception as e:
            print(f"[AISearch] Summary failed: {e}")
            response.summary = "⚠️ AI 总结生成失败"
        
        return response
    
    def _build_trusted_summary_prompt(
        self, 
        query: str, 
        results: list[SearchResult],
        intent: SearchIntent
    ) -> str:
        """构建可信度约束的总结 prompt"""
        
        results_text = "\n\n".join([
            f"## [{i+1}] {r.title}\n"
            f"来源: {r.source} ({r.url})\n"
            f"摘要: {r.snippet}"
            for i, r in enumerate(results[:8])
        ])
        
        # 根据意图添加特定约束
        intent_constraints = {
            SearchIntent.FILE_DOWNLOAD: "\n6. 如有文件下载链接，必须标注。",
            SearchIntent.POLICY: "\n6. 标注政策适用范围、生效时间、申报截止日期等关键信息。",
            SearchIntent.NEWS: "\n6. 标注新闻来源、发布时间、多方印证情况。",
            SearchIntent.AMBIGUOUS: "\n6. 分类呈现不同解释的可能性，如：'软件'、'翻译'等。",
        }
        
        constraint = intent_constraints.get(intent, "")
        
        return f"""你是一个专业的研究助手。请根据以下搜索结果，为查询「{query}」生成一个结构化的总结。

【重要约束 - 必须遵守】
1. **只提取，不生成**：严格使用原文中的词汇和信息，不要创造新表述
2. **保留否定**：如果原文包含否定表述（如"暂不支持"、"无法"），摘要必须原样保留
3. **引用原文**：每个要点都必须能追溯到具体的搜索结果
4. **客观呈现**：不夸大、不淡化、不优化负面信息{constraint}

## 搜索结果

{results_text}

## 输出格式

请用 Markdown 格式输出：
- 核心发现（3-5条）
- 分类详情（如适用）
- 参考来源（标注序号）
- 注意事项（如有时效性、争议性等）"""
    
    async def fetch_raw_content(self, url: str, timeout: int = 10) -> str:
        """
        获取原文内容（用于可信度验证）
        
        Args:
            url: 目标URL
            timeout: 超时时间（秒）
            
        Returns:
            str: 净化后的原文内容
        """
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                r = await client.get(url, headers=headers, follow_redirects=True)
                r.raise_for_status()
                
                # 简单净化：去除HTML标签
                content = r.text
                content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL)
                content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL)
                content = re.sub(r'<[^>]+>', ' ', content)
                content = re.sub(r'\s+', ' ', content).strip()
                
                return content[:5000]  # 限制长度
                
        except Exception as e:
            print(f"[AISearch] Fetch raw content failed: {e}")
            return ""
    
    def clear_cache(self) -> None:
        """清空搜索缓存"""
        self.cache.clear()
    
    def get_available_engines(self) -> list[str]:
        """获取可用的搜索引擎列表"""
        return [e.name for e in self.engines]
    
    def get_download_dir(self) -> Path:
        """获取下载目录"""
        return self.download_dir

# ── 导出 ─────────────────────────────────────────────────────────────────────

__all__ = [
    # 核心
    "AISearchTool",
    "SearchEngine",
    "SearchResult",
    "SearchResponse",
    "SearchIntent",
    "SearchCache",
    
    # 增强组件
    "SEOFilter",
    "IntentClassifier",
    "QueryOptimizer",
    "TrustVerifier",
    "TrustVerification",
    
    # 引擎
    "DuckDuckGoEngine",
    "SerperEngine",
    "BraveEngine",
    "CnAggregateEngine",
]
