"""
智能创作与内容监控系统 - 统一调度器

模块功能：
1. 规则引擎 (rule_engine.py) - Trie树敏感词匹配、AC自动机、正则规则
2. 内容识别 (content_recognizer.py) - 财务/法律/项目计划/会议记录识别
3. 归纳汇总 (summarizer.py) - 多类型内容自动归纳
4. 监控引擎 (monitor.py) - 告警处理、多层监控
5. API服务 (server.py) - RESTful API服务器
6. Web界面 (web_dashboard.py) - 响应式管理仪表板

使用方法：
    from business.content_monitor import ContentMonitorServer, create_server
    
    # 方式1: 创建服务器
    server = await create_server({"port": 8765})
    
    # 方式2: 直接使用监控引擎
    from business.content_monitor import ContentMonitor
    monitor = ContentMonitor()
    result = monitor.analyze_content("待检测内容")
    
    # 方式3: 使用内容识别
    from business.content_monitor import ContentRecognizer
    recognizer = ContentRecognizer()
    analysis = recognizer.recognize("财务内容...")
    
    # 方式4: 使用归纳汇总
    from business.content_monitor import ContentSummarizer, ContentType
    summarizer = ContentSummarizer()
    result = summarizer.summarize("内容...", ContentType.FINANCIAL)
"""

from .models import (
    ContentType, AlertLevel, ContentStatus, RuleType, NotificationChannel,
    SensitiveWord, MonitoringRule, ContentItem, SummarizationResult,
    AlertRecord, RecognizedEntity, ContentAnalysis, SystemStats
)

from .monitor import ContentMonitor, AlertHandler
from .rule_engine import RuleEngine
from .content_recognizer import ContentRecognizer
from .summarizer import ContentSummarizer
from .server import ContentMonitorServer, APIServer, DatabaseManager, create_server
from .web_dashboard import get_dashboard_html

__all__ = [
    # 模型
    "ContentType", "AlertLevel", "ContentStatus", "RuleType", "NotificationChannel",
    "SensitiveWord", "MonitoringRule", "ContentItem", "SummarizationResult",
    "AlertRecord", "RecognizedEntity", "ContentAnalysis", "SystemStats",
    # 核心类
    "ContentMonitor", "AlertHandler", "RuleEngine", "ContentRecognizer",
    "ContentSummarizer", "ContentMonitorServer", "APIServer", "DatabaseManager",
    # 工具函数
    "create_server", "get_dashboard_html"
]

__version__ = "1.0.0"
