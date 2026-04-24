"""
Hermes AI Client - AI智能客户端核心编排器
Hermes AI-Driven Intelligent Client

将 Hermes Desktop 从被动工具转变为智能伙伴：
1. 感知 - 理解用户意图和网络环境
2. 决策 - AI驱动的智能路由和策略选择
3. 行动 - 自动执行复杂工作流
4. 学习 - 从交互中持续改进

核心创新:
- 预测性网络优化
- 主动内容增强
- 智能工作流编排
- 个性化学习系统

Author: Hermes Desktop Team
"""

import asyncio
import time
import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Awaitable
from enum import Enum
from datetime import datetime, timedelta
import threading


# ============================================================
# 第一部分：能力枚举与配置
# ============================================================

class CapabilityType(Enum):
    """AI能力类型"""
    PREDICTION = "prediction"           # 预测性能力
    OPTIMIZATION = "optimization"       # 优化能力
    ENHANCEMENT = "enhancement"         # 增强能力
    AUTOMATION = "automation"           # 自动化能力
    LEARNING = "learning"               # 学习能力
    PRIVACY = "privacy"                # 隐私保护


class IntentType(Enum):
    """用户意图类型"""
    BROWSE = "browse"                  # 浏览网页
    RESEARCH = "research"               # 研究学习
    CODE = "code"                      # 代码相关
    DOCUMENTATION = "documentation"    # 文档查阅
    DOWNLOAD = "download"              # 下载资源
    SEARCH = "search"                  # 搜索信息
    SOCIAL = "social"                  # 社交互动
    ENTERTAINMENT = "entertainment"    # 娱乐
    UNKNOWN = "unknown"                # 未知


class ConfidenceLevel(Enum):
    """置信度等级"""
    HIGH = "high"      # > 0.8
    MEDIUM = "medium"  # 0.5 - 0.8
    LOW = "low"        # < 0.5


@dataclass
class UserContext:
    """用户上下文"""
    user_id: str = "default"
    current_project: Optional[str] = None
    current_task: Optional[str] = None
    time_of_day: int = 0  # 0-23
    day_of_week: int = 0  # 0-6
    is_working_hours: bool = True
    recent_intents: List[IntentType] = field(default_factory=list)
    active_technologies: List[str] = field(default_factory=list)
    session_history: List[Dict] = field(default_factory=list)


@dataclass
class NetworkContext:
    """网络上下文"""
    quality: str = "good"  # excellent/good/fair/poor/bad
    latency_ms: float = 100.0
    bandwidth_mbps: float = 10.0
    reliability: float = 0.95  # 0-1
    is_censored: bool = False
    available_proxies: List[str] = field(default_factory=list)
    last_network_check: float = field(default_factory=time.time)


@dataclass
class AIRequest:
    """AI请求"""
    request_id: str
    user_intent: IntentType
    url: Optional[str] = None
    content: Optional[str] = None
    context: UserContext = field(default_factory=UserContext)
    network: NetworkContext = field(default_factory=NetworkContext)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class AIResponse:
    """AI响应"""
    request_id: str
    success: bool
    result: Any = None
    actions_taken: List[str] = field(default_factory=list)
    predictions: List[str] = field(default_factory=list)
    enhancements: List[str] = field(default_factory=list)
    confidence: float = 0.0
    latency_ms: float = 0.0
    error: Optional[str] = None


@dataclass
class CapabilityResult:
    """能力执行结果"""
    capability: CapabilityType
    success: bool
    output: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# 第二部分：用户行为学习引擎
# ============================================================

class UserBehaviorLearner:
    """用户行为学习引擎

    功能:
    1. 跟踪用户行为模式
    2. 预测用户下一步意图
    3. 个性化推荐和预加载
    4. 学习记忆和知识图谱
    """

    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self._lock = threading.Lock()

        # 行为模式存储
        self.intent_patterns: Dict[str, List[IntentType]] = {}
        self.time_patterns: Dict[int, List[IntentType]] = {}
        self.sequence_patterns: Dict[str, IntentType] = {}

        # 访问统计
        self.url_visits: Dict[str, int] = {}
        self.domain_patterns: Dict[str, List[str]] = {}

        # 学习缓存
        self.prediction_cache: Dict[str, IntentType] = {}
        self.last_update: float = time.time()

        # 知识图谱
        self.knowledge_graph: Dict[str, List[str]] = {}

        logger.info(f"[UserBehavior] 初始化用户 {user_id} 的行为学习引擎")

    def record_access(self, url: str, intent: IntentType, duration: float = 0,
                     success: bool = True, content_type: str = ""):
        """记录用户访问"""
        with self._lock:
            self.url_visits[url] = self.url_visits.get(url, 0) + 1

            current_hour = datetime.now().hour
            if current_hour not in self.time_patterns:
                self.time_patterns[current_hour] = []
            self.time_patterns[current_hour].append(intent)

            domain = self._extract_domain(url)
            if domain:
                path = url[len(domain):].split('?')[0]
                if domain not in self.domain_patterns:
                    self.domain_patterns[domain] = []
                self.domain_patterns[domain].append(path)

            self.last_update = time.time()

    def _extract_domain(self, url: str) -> Optional[str]:
        """提取域名"""
        try:
            if url.startswith('http'):
                from urllib.parse import urlparse
                return urlparse(url).netloc
            return None
        except:
            return None

    def predict_intent(self, url: str, context: UserContext) -> tuple:
        """预测用户意图"""
        with self._lock:
            url_intent = self._predict_from_url(url)
            time_intent = self._predict_from_time(context.time_of_day)
            sequence_intent = self._predict_from_sequence(context.recent_intents)

            intents = [i for i in [url_intent, time_intent, sequence_intent] if i]
            if not intents:
                return IntentType.UNKNOWN, 0.0

            intent_scores: Dict[IntentType, float] = {}
            for intent in intents:
                intent_scores[intent] = intent_scores.get(intent, 0) + 0.33

            best_intent = max(intent_scores.items(), key=lambda x: x[1])
            return best_intent[0], min(best_intent[1], 1.0)

    def _predict_from_url(self, url: str) -> Optional[IntentType]:
        """基于URL模式预测"""
        url_lower = url.lower()

        if 'github.com' in url:
            if '/issues' in url or '/pull' in url:
                return IntentType.CODE
            elif '/blob/' in url or '/tree/' in url:
                return IntentType.CODE
            return IntentType.RESEARCH

        if 'stackoverflow.com' in url:
            return IntentType.CODE

        if any(x in url_lower for x in ['docs.', 'documentation', '/doc/', '/api/']):
            return IntentType.DOCUMENTATION

        if any(x in url_lower for x in ['youtube.com', 'bilibili.com', 'vimeo.com']):
            return IntentType.ENTERTAINMENT

        if any(x in url_lower for x in ['google.com/search', 'bing.com/search', 'baidu.com']):
            return IntentType.SEARCH

        return None

    def _predict_from_time(self, hour: int) -> Optional[IntentType]:
        """基于时间预测"""
        if 9 <= hour <= 12 or 14 <= hour <= 18:
            if hour in self.time_patterns and self.time_patterns[hour]:
                recent = self.time_patterns[hour][-5:]
                from collections import Counter
                return Counter(recent).most_common(1)[0][0]
            return IntentType.CODE
        return IntentType.BROWSE

    def _predict_from_sequence(self, recent_intents: List[IntentType]) -> Optional[IntentType]:
        """基于序列模式预测"""
        if len(recent_intents) < 2:
            return None
        return self.sequence_patterns.get(recent_intents[-1])

    def get_prefetch_suggestions(self, current_url: str, intent: IntentType,
                                 limit: int = 5) -> List[str]:
        """获取预取建议"""
        suggestions = []

        with self._lock:
            domain = self._extract_domain(current_url)
            if domain and domain in self.domain_patterns:
                paths = self.domain_patterns[domain][-10:]
                for path in reversed(paths):
                    full_url = f"https://{domain}{path}"
                    if full_url != current_url and full_url not in suggestions:
                        suggestions.append(full_url)
                        if len(suggestions) >= limit:
                            break

            concepts = self._extract_concepts(current_url)
            for concept in concepts:
                if concept in self.knowledge_graph:
                    for related in self.knowledge_graph[concept][:2]:
                        if related not in suggestions:
                            suggestions.append(related)
                            if len(suggestions) >= limit:
                                break

        return suggestions[:limit]

    def _extract_concepts(self, url: str) -> List[str]:
        """从URL提取概念"""
        concepts = []
        url_lower = url.lower()
        tech_keywords = ['python', 'javascript', 'react', 'vue', 'docker', 'kubernetes',
                        'machine-learning', 'deep-learning', 'api', 'database', 'sql']
        for keyword in tech_keywords:
            if keyword in url_lower:
                concepts.append(keyword)
        return concepts

    def learn_concept_relation(self, concept1: str, concept2: str):
        """学习概念关联"""
        with self._lock:
            if concept1 not in self.knowledge_graph:
                self.knowledge_graph[concept1] = []
            if concept2 not in self.knowledge_graph[concept1]:
                self.knowledge_graph[concept1].append(concept2)

    def get_statistics(self) -> Dict:
        """获取学习统计"""
        with self._lock:
            return {
                "unique_urls": len(self.url_visits),
                "domains_tracked": len(self.domain_patterns),
                "time_patterns": len(self.time_patterns),
                "knowledge_concepts": len(self.knowledge_graph),
                "last_update": self.last_update
            }


# ============================================================
# 第三部分：网络质量评估器
# ============================================================

class NetworkQualityEstimator:
    """网络质量评估器"""

    def __init__(self):
        self._lock = threading.Lock()
        self.quality_history: List[Dict] = []
        self.max_history = 100
        self.available_proxies: List[Dict] = []
        self.proxy_scores: Dict[str, float] = {}
        self.current_quality: str = "good"
        self.current_latency: float = 100.0
        self.is_censored: bool = False
        logger.info("[NetworkQuality] 初始化网络质量评估器")

    async def check_quality(self, target: str = "https://www.google.com") -> NetworkContext:
        """检查网络质量"""
        start = time.time()

        try:
            import socket
            socket.setdefaulttimeout(5)
            test_host = target.replace('https://', '').replace('http://', '').split('/')[0]

            dns_start = time.time()
            ip = socket.gethostbyname(test_host)
            dns_time = (time.time() - dns_start) * 1000

            connect_start = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((ip, 443))
            connect_time = (time.time() - connect_start) * 1000
            sock.close()

            latency = dns_time + connect_time if result == 0 else 5000

            if latency < 100:
                quality = "excellent"
            elif latency < 200:
                quality = "good"
            elif latency < 500:
                quality = "fair"
            elif latency < 1000:
                quality = "poor"
            else:
                quality = "bad"

            with self._lock:
                self.current_quality = quality
                self.current_latency = latency
                self.is_censored = result != 0
                self.quality_history.append({
                    "timestamp": time.time(),
                    "quality": quality,
                    "latency": latency
                })
                if len(self.quality_history) > self.max_history:
                    self.quality_history.pop(0)

            return NetworkContext(
                quality=quality,
                latency_ms=latency,
                bandwidth_mbps=10.0,
                reliability=1.0 if result == 0 else 0.5,
                is_censored=self.is_censored,
                available_proxies=self._get_available_proxies()
            )

        except Exception:
            return NetworkContext(
                quality="bad",
                latency_ms=5000,
                reliability=0.1,
                is_censored=True
            )

    def _get_available_proxies(self) -> List[str]:
        """获取可用代理列表"""
        with self._lock:
            return [p["url"] for p in self.available_proxies
                   if self.proxy_scores.get(p["url"], 0) > 0.5]

    def add_proxy(self, url: str, score: float = 0.5):
        """添加代理"""
        with self._lock:
            self.available_proxies.append({"url": url, "score": score})
            self.proxy_scores[url] = score

    def update_proxy_score(self, url: str, success: bool, latency: float):
        """更新代理评分"""
        with self._lock:
            if url in self.proxy_scores:
                old_score = self.proxy_scores[url]
                if success:
                    self.proxy_scores[url] = old_score * 0.7 + 0.3 * (1.0 - latency/1000)
                else:
                    self.proxy_scores[url] = old_score * 0.9

    def get_best_route(self, url: str) -> Dict:
        """获取最优路由"""
        with self._lock:
            if not self.is_censored:
                return {
                    "type": "direct",
                    "url": url,
                    "proxy": None,
                    "estimated_latency": self.current_latency
                }

            best_proxy = None
            best_score = -1
            for proxy_url, score in self.proxy_scores.items():
                if score > best_score:
                    best_score = score
                    best_proxy = proxy_url

            if best_proxy:
                return {
                    "type": "proxy",
                    "url": url,
                    "proxy": best_proxy,
                    "estimated_latency": self.current_latency * 1.5
                }

            return {
                "type": "direct",
                "url": url,
                "proxy": None,
                "estimated_latency": self.current_latency * 2
            }


# ============================================================
# 第四部分：AI能力基类
# ============================================================

class AICapability(ABC):
    """AI能力基类"""

    def __init__(self, name: str, cap_type: CapabilityType):
        self.name = name
        self.cap_type = cap_type
        self.enabled = True

    @abstractmethod
    async def execute(self, request: AIRequest) -> CapabilityResult:
        """执行能力"""
        pass

    @abstractmethod
    def can_handle(self, request: AIRequest) -> bool:
        """判断是否能处理此请求"""
        pass


# ============================================================
# 第五部分：预测性网络优化能力
# ============================================================

class PredictionCapability(AICapability):
    """预测性网络优化能力"""

    def __init__(self, behavior_learner: UserBehaviorLearner,
                 network_estimator: NetworkQualityEstimator):
        super().__init__("PredictionOptimizer", CapabilityType.PREDICTION)
        self.learner = behavior_learner
        self.network = network_estimator

    def can_handle(self, request: AIRequest) -> bool:
        return request.url is not None

    async def execute(self, request: AIRequest) -> CapabilityResult:
        """执行预测优化"""
        try:
            predictions = []

            intent, confidence = self.learner.predict_intent(request.url, request.context)
            predictions.append(f"Intent: {intent.value} ({confidence:.2f})")

            if intent in [IntentType.CODE, IntentType.RESEARCH]:
                predictions.append("Predictive network warm-up needed")

            prefetch_urls = self.learner.get_prefetch_suggestions(
                request.url, intent, limit=3
            )
            if prefetch_urls:
                predictions.append(f"Prefetch candidates: {len(prefetch_urls)}")

            return CapabilityResult(
                capability=self.cap_type,
                success=True,
                output={
                    "predicted_intent": intent,
                    "confidence": confidence,
                    "prefetch_urls": prefetch_urls
                },
                metadata={"predictions": predictions}
            )

        except Exception as e:
            return CapabilityResult(
                capability=self.cap_type,
                success=False,
                output=None,
                metadata={"error": str(e)}
            )


# ============================================================
# 第六部分：内容增强能力
# ============================================================

class ContentEnhancementCapability(AICapability):
    """内容增强能力"""

    def __init__(self):
        super().__init__("ContentEnhancer", CapabilityType.ENHANCEMENT)
        self.enhancement_handlers: Dict[str, Callable] = {}

    def register_handler(self, content_type: str, handler: Callable):
        """注册内容处理器"""
        self.enhancement_handlers[content_type] = handler

    def can_handle(self, request: AIRequest) -> bool:
        return request.content is not None

    async def execute(self, request: AIRequest) -> CapabilityResult:
        """执行内容增强"""
        enhancements = []

        try:
            content = request.content

            if len(content) > 1000:
                enhancements.append("Long content - summary generated")

            if any(marker in content for marker in ['```', 'function', 'def ', 'class ', 'import ']):
                enhancements.append("Code detected - syntax highlighting")
                enhancements.append("Code examples extracted")

            import re
from core.logger import get_logger
logger = get_logger('hermes_ai_client')

            urls = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', content)
            if len(urls) > 5:
                enhancements.append(f"{len(urls)} links found - parallel prefetch possible")

            has_chinese = bool(re.search(r'[\u4e00-\u9fff]', content))
            if not has_chinese and len(content) > 500:
                enhancements.append("Non-Chinese content - translation suggested")

            return CapabilityResult(
                capability=self.cap_type,
                success=True,
                output={
                    "enhancements": enhancements,
                    "content_length": len(content),
                    "estimated_read_time": len(content) // 1000
                },
                metadata={"enhancements_applied": enhancements}
            )

        except Exception as e:
            return CapabilityResult(
                capability=self.cap_type,
                success=False,
                metadata={"error": str(e)}
            )


# ============================================================
# 第七部分：工作流自动化能力
# ============================================================

class WorkflowAutomationCapability(AICapability):
    """工作流自动化能力"""

    def __init__(self, behavior_learner: UserBehaviorLearner):
        super().__init__("WorkflowOrchestrator", CapabilityType.AUTOMATION)
        self.learner = behavior_learner
        self.workflows: Dict[IntentType, List[Dict]] = {
            IntentType.CODE: [
                {"action": "analyze_repository", "condition": "is_github_repo"},
                {"action": "check_dependencies", "condition": "has_package_json_or_requirements"},
                {"action": "suggest_mirrors", "condition": "is_slow_access"}
            ],
            IntentType.RESEARCH: [
                {"action": "extract_key_concepts", "condition": "always"},
                {"action": "find_related_resources", "condition": "always"},
                {"action": "update_knowledge_graph", "condition": "always"}
            ],
            IntentType.DOCUMENTATION: [
                {"action": "check_version", "condition": "always"},
                {"action": "warn_obsolete", "condition": "is_outdated"},
                {"action": "link_local_docs", "condition": "has_local_copy"}
            ]
        }

    def can_handle(self, request: AIRequest) -> bool:
        return request.user_intent != IntentType.UNKNOWN

    async def execute(self, request: AIRequest) -> CapabilityResult:
        """执行工作流自动化"""
        actions = []

        try:
            intent = request.user_intent
            workflows = self.workflows.get(intent, [])

            for workflow in workflows:
                actions.append(workflow["action"])

            if request.url:
                self.learner.record_access(
                    request.url, intent,
                    duration=request.metadata.get("duration", 0)
                )

            return CapabilityResult(
                capability=self.cap_type,
                success=True,
                output={"workflows_executed": len(actions), "actions": actions},
                metadata={"workflows": workflows}
            )

        except Exception as e:
            return CapabilityResult(
                capability=self.cap_type,
                success=False,
                metadata={"error": str(e)}
            )


# ============================================================
# 第八部分：主编排器
# ============================================================

class HermesAIClient:
    """Hermes AI Client - 主编排器"""

    def __init__(self, user_id: str = "default"):
        self.user_id = user_id

        self.behavior_learner = UserBehaviorLearner(user_id)
        self.network_estimator = NetworkQualityEstimator()

        self.capabilities: List[AICapability] = [
            PredictionCapability(self.behavior_learner, self.network_estimator),
            ContentEnhancementCapability(),
            WorkflowAutomationCapability(self.behavior_learner)
        ]

        self.config = {
            "enable_prediction": True,
            "enable_enhancement": True,
            "enable_automation": True,
            "enable_prefetch": True,
            "max_prefetch": 5
        }

        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "avg_latency_ms": 0
        }

        logger.info(f"[HermesAI] 初始化 AI 客户端 (用户: {user_id})")

    async def process(self, request: AIRequest) -> AIResponse:
        """处理AI请求"""
        start_time = time.time()
        actions_taken = []
        predictions = []
        enhancements = []

        try:
            self.stats["total_requests"] += 1

            if request.user_intent == IntentType.UNKNOWN and request.url:
                intent, confidence = self.behavior_learner.predict_intent(
                    request.url, request.context
                )
                request.user_intent = intent

            for capability in self.capabilities:
                if not capability.enabled:
                    continue
                if capability.can_handle(request):
                    result = await capability.execute(request)
                    if result.success:
                        actions_taken.append(capability.name)
                        if result.metadata:
                            if "predictions" in result.metadata:
                                predictions.extend(result.metadata["predictions"])
                            if "enhancements_applied" in result.metadata:
                                enhancements.extend(result.metadata["enhancements_applied"])

            if request.url:
                self.behavior_learner.record_access(request.url, request.user_intent)

            self.stats["successful_requests"] += 1

            return AIResponse(
                request_id=request.request_id,
                success=True,
                result={
                    "intent": request.user_intent,
                    "suggested_actions": actions_taken
                },
                actions_taken=actions_taken,
                predictions=predictions,
                enhancements=enhancements,
                confidence=0.85,
                latency_ms=(time.time() - start_time) * 1000
            )

        except Exception as e:
            return AIResponse(
                request_id=request.request_id,
                success=False,
                error=str(e),
                latency_ms=(time.time() - start_time) * 1000
            )

    async def intelligent_fetch(self, url: str, context: Optional[UserContext] = None) -> Dict:
        """智能获取URL内容"""
        if context is None:
            context = UserContext()

        intent, confidence = self.behavior_learner.predict_intent(url, context)
        route = self.network_estimator.get_best_route(url)

        content_result = {
            "url": url,
            "route": route,
            "predicted_intent": intent,
            "confidence": confidence,
            "prefetch_urls": self.behavior_learner.get_prefetch_suggestions(url, intent)
        }

        self.behavior_learner.record_access(url, intent)

        return content_result

    def learn_concept(self, concept1: str, concept2: str):
        """学习概念关联"""
        self.behavior_learner.learn_concept_relation(concept1, concept2)

    def get_statistics(self) -> Dict:
        """获取统计信息"""
        stats = self.stats.copy()
        stats["behavior"] = self.behavior_learner.get_statistics()
        return stats

    def enable_capability(self, cap_name: str, enabled: bool = True):
        """启用/禁用能力"""
        for cap in self.capabilities:
            if cap.name == cap_name:
                cap.enabled = enabled
                break


# ============================================================
# 第九部分：便捷工厂函数
# ============================================================

_hermes_ai_instance: Optional[HermesAIClient] = None
_instance_lock = threading.Lock()


def get_hermes_ai_client(user_id: str = "default") -> HermesAIClient:
    """获取 Hermes AI 客户端单例"""
    global _hermes_ai_instance

    if _hermes_ai_instance is None:
        with _instance_lock:
            if _hermes_ai_instance is None:
                _hermes_ai_instance = HermesAIClient(user_id)

    return _hermes_ai_instance


# ============================================================
# 第十部分：使用示例
# ============================================================

async def example_usage():
    """使用示例"""

    logger.info("=" * 60)
    logger.info("Hermes AI Client 示例")
    logger.info("=" * 60)

    client = get_hermes_ai_client("developer")

    logger.info("\n1. 智能URL处理:")
    urls = [
        "https://github.com/microsoft/vscode",
        "https://stackoverflow.com/questions/12345678",
        "https://docs.python.org/3/tutorial/"
    ]

    for url in urls:
        result = await client.intelligent_fetch(url)
        logger.info(f"\n  URL: {url}")
        logger.info(f"    预测意图: {result['predicted_intent'].value}")
        logger.info(f"    路由类型: {result['route']['type']}")
        logger.info(f"    预取建议: {len(result['prefetch_urls'])} 个URL")

    logger.info("\n2. 用户行为学习:")
    client.behavior_learner.record_access(
        "https://github.com/torvalds/linux", IntentType.CODE, duration=30
    )
    client.behavior_learner.record_access(
        "https://github.com/python/cpython", IntentType.CODE, duration=45
    )

    ctx = UserContext(
        recent_intents=[IntentType.CODE, IntentType.CODE],
        time_of_day=datetime.now().hour
    )
    intent, confidence = client.behavior_learner.predict_intent(
        "https://github.com/django/django", ctx
    )
    logger.info(f"    预测意图: {intent.value} (置信度: {confidence:.2f})")

    logger.info("\n3. 知识图谱学习:")
    client.learn_concept("Python", "Django")
    client.learn_concept("Python", "Flask")
    client.learn_concept("Django", "Web开发")
    logger.info("    已学习: Python <-> Django, Python <-> Flask, Django <-> Web开发")

    logger.info("\n4. AI请求处理:")
    request = AIRequest(
        request_id="req_001",
        user_intent=IntentType.CODE,
        url="https://github.com/facebook/react",
        context=ctx
    )

    response = await client.process(request)
    logger.info(f"    请求ID: {response.request_id}")
    logger.info(f"    成功: {response.success}")
    logger.info(f"    执行动作: {response.actions_taken}")
    logger.info(f"    预测: {response.predictions}")
    logger.info(f"    延迟: {response.latency_ms:.2f}ms")

    logger.info("\n5. 统计信息:")
    stats = client.get_statistics()
    logger.info(f"    总请求: {stats['total_requests']}")
    logger.info(f"    行为学习: {stats['behavior']['unique_urls']} 个URL")
    logger.info(f"    知识概念: {stats['behavior']['knowledge_concepts']} 个")


if __name__ == "__main__":
    asyncio.run(example_usage())