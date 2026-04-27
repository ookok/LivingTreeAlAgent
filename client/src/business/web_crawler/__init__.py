"""
Web Crawler - Scrapling 封装模块

基于 Scrapling 框架的高性能网页内容提取。
支持自适应解析、反爬绕过、并发爬取。

用法：
    from client.src.business.web_crawler import ScraplingEngine
    
    engine = ScraplingEngine()
    content = await engine.extract("https://example.com")
    
    # 批量提取
    results = await engine.batch_extract([url1, url2, ...])
"""

from .engine import ScraplingEngine, extract_with_scrapling
from .adaptive_parser import AdaptiveParser

__all__ = [
    "ScraplingEngine",
    "extract_with_scrapling",
    "AdaptiveParser",
]
