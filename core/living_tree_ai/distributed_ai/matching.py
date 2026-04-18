"""
深度匹配策略 (Deep Matching Strategies)

将 AI 能力与客户端功能深度整合：
- 聚合推荐
- 深度搜索
- 智能 IDE
- 智能游戏
- 智能浏览器
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import asyncio


class MatchingType(Enum):
    """匹配类型"""
    AGGREGATION = "aggregation"           # 聚合推荐
    DEEP_SEARCH = "deep_search"           # 深度搜索
    SMART_IDE = "smart_ide"               # 智能IDE
    SMART_GAME = "smart_game"             # 智能游戏
    SMART_BROWSER = "smart_browser"       # 智能浏览器


@dataclass
class MatchingContext:
    """匹配上下文"""
    user_id: str
    matching_type: MatchingType
    source: str                              # 来源应用
    current_content: Any                     # 当前内容
    user_profile: Dict[str, Any]             # 用户画像
    active_sessions: List[str] = None        # 活跃会话


@dataclass
class MatchingResult:
    """匹配结果"""
    items: List[Dict]
    confidence: float
    reasoning: str
    actions: List[str] = None                # 可执行的操作
    metadata: Dict[str, Any] = None


# ============================================================================
# 聚合推荐匹配器
# ============================================================================

class AggregationMatcher:
    """
    聚合推荐：整合多源推荐，去重、合规、排序
    """

    def __init__(self, brain):
        self.brain = brain
        self.interest_tags = {}              # 用户兴趣标签

    async def aggregate_recommendations(
        self,
        user_id: str,
        context: Dict
    ) -> MatchingResult:
        """
        聚合推荐

        流程：
        1. 海外集群：挖掘 GitHub Trending、Reddit 热榜
        2. 中心节点：去重、合规过滤、排序
        3. 边缘节点：缓存"已读"状态
        4. 深度匹配：关联智能 IDE 的"一键导入"
        """

        # 1. 并行获取多源推荐
        sources = await asyncio.gather(
            self.fetch_github_trending(user_id),
            self.fetch_reddit_hot(user_id),
            self.fetch_personalized(user_id),
            return_exceptions=True
        )

        # 2. 合并去重
        all_items = []
        seen_ids = set()
        for source_items in sources:
            if isinstance(source_items, list):
                for item in source_items:
                    item_id = item.get("id", "")
                    if item_id and item_id not in seen_ids:
                        seen_ids.add(item_id)
                        item["_source"] = self.get_source_name(source_items)
                        all_items.append(item)

        # 3. 合规过滤
        filtered_items = await self.filter_compliance(all_items, user_id)

        # 4. 兴趣排序
        ranked_items = self.rank_by_interest(filtered_items, user_id)

        # 5. 生成深度操作
        for item in ranked_items:
            item["actions"] = self.generate_actions(item)

        return MatchingResult(
            items=ranked_items,
            confidence=0.85,
            reasoning="基于兴趣标签和热度综合排序",
            actions=["一键导入", "查看详情", "收藏"]
        )

    async def fetch_github_trending(self, user_id: str) -> List[Dict]:
        """获取 GitHub Trending"""
        # 模拟调用海外集群
        return [
            {
                "id": "gh_1",
                "type": "github",
                "title": "awesome-ai-agents",
                "description": "Awesome AI Agents 列表",
                "url": "https://github.com/...",
                "stars": 15000,
                "tags": ["AI", "Agent"]
            }
        ]

    async def fetch_reddit_hot(self, user_id: str) -> List[Dict]:
        """获取 Reddit 热榜"""
        return [
            {
                "id": "rd_1",
                "type": "reddit",
                "title": "讨论：LLM 的未来发展",
                "url": "https://reddit.com/...",
                "score": 5000,
                "tags": ["LLM", "AI"]
            }
        ]

    async def fetch_personalized(self, user_id: str) -> List[Dict]:
        """获取个性化推荐"""
        return [
            {
                "id": "per_1",
                "type": "personalized",
                "title": "您关注的项目更新",
                "items": []
            }
        ]

    async def filter_compliance(self, items: List[Dict], user_id: str) -> List[Dict]:
        """合规过滤"""
        audit = await self.brain.compliance_gateway.audit_content(
            items,
            source="aggregation",
            user_id=user_id
        )
        return items if audit["passed"] else []

    def rank_by_interest(self, items: List[Dict], user_id: str) -> List[Dict]:
        """按兴趣排序"""
        user_tags = self.interest_tags.get(user_id, [])

        def score(item):
            s = item.get("stars", item.get("score", 0))
            item_tags = set(item.get("tags", []))
            interest_overlap = len(item_tags & set(user_tags))
            return s + interest_overlap * 1000

        return sorted(items, key=score, reverse=True)

    def generate_actions(self, item: Dict) -> List[str]:
        """生成可执行操作"""
        actions = ["查看详情"]
        if item.get("type") == "github":
            actions.append("一键导入IDE")
        return actions

    def get_source_name(self, source) -> str:
        """获取源名称"""
        return "unknown"


# ============================================================================
# 深度搜索匹配器
# ============================================================================

class DeepSearchMatcher:
    """
    深度搜索：关联本地项目与在线资源
    """

    def __init__(self, brain):
        self.brain = brain

    async def deep_search(
        self,
        query: str,
        context: MatchingContext
    ) -> MatchingResult:
        """
        深度搜索

        流程：
        1. 海外集群：执行无限制语义搜索
        2. 中心节点：关联本地项目文件
        3. 边缘节点：缓存高频搜索片段
        4. 深度匹配：返回代码片段 + 本地引用位置
        """

        # 1. 获取搜索结果
        search_results = await self.search_online(query, context)

        # 2. 关联本地项目
        local_references = await self.find_local_references(query, context)

        # 3. 合并结果
        combined = self.merge_results(search_results, local_references)

        # 4. 生成代码片段
        enhanced_results = await self.enhance_with_snippets(combined, context)

        return MatchingResult(
            items=enhanced_results,
            confidence=0.9,
            reasoning="关联在线资源与本地项目",
            actions=["复制代码", "跳转到引用", "添加到收藏"]
        )

    async def search_online(self, query: str, context: MatchingContext) -> List[Dict]:
        """在线搜索"""
        # 模拟调用海外集群
        return [
            {
                "id": "search_1",
                "title": "Python 异步编程详解",
                "url": "https://example.com/python-async",
                "snippet": "asyncio 是 Python 的异步编程库...",
                "source": "web"
            },
            {
                "id": "search_2",
                "title": "Stack Overflow: Python async",
                "url": "https://stackoverflow.com/...",
                "snippet": "使用 async/await 关键字...",
                "source": "stackoverflow"
            }
        ]

    async def find_local_references(self, query: str, context: MatchingContext) -> List[Dict]:
        """查找本地项目引用"""
        # 模拟查找本地文件
        return [
            {
                "id": "local_1",
                "file": "src/utils/async_helper.py",
                "line": 42,
                "content": "async def fetch_data():",
                "source": "local"
            }
        ]

    def merge_results(self, online: List[Dict], local: List[Dict]) -> List[Dict]:
        """合并搜索结果"""
        merged = []
        for item in online:
            item["references"] = []
            merged.append(item)
        for ref in local:
            merged.append(ref)
        return merged

    async def enhance_with_snippets(self, results: List[Dict], context: MatchingContext) -> List[Dict]:
        """增强搜索结果，添加代码片段"""
        for item in results:
            if item.get("snippet"):
                # 提取代码片段
                item["code_snippet"] = self.extract_code(item["snippet"])
        return results

    def extract_code(self, text: str) -> Optional[str]:
        """从文本中提取代码"""
        if "```" in text:
            start = text.find("```") + 3
            end = text.rfind("```")
            return text[start:end].strip()
        return None


# ============================================================================
# 智能 IDE 匹配器
# ============================================================================

class SmartIDEMatcher:
    """
    智能 IDE：代码补全、重构建议、依赖扫描
    """

    def __init__(self, brain):
        self.brain = brain
        self.lsp_services: Dict[str, Any] = {}

    async def handle_ide_request(
        self,
        request_type: str,
        context: MatchingContext
    ) -> MatchingResult:
        """
        处理 IDE 请求

        分层处理：
        - 边缘节点：实时代码补全、LSP 服务
        - 海外集群：复杂重构建议、依赖漏洞扫描
        - 中心节点：同步开发环境配置
        """

        if request_type == "completion":
            return await self.handle_completion(context)
        elif request_type == "refactor":
            return await self.handle_refactor(context)
        elif request_type == "dependency":
            return await self.handle_dependency_scan(context)
        elif request_type == "config_sync":
            return await self.handle_config_sync(context)

        return MatchingResult(items=[], confidence=0.0, reasoning="未知请求类型")

    async def handle_completion(self, context: MatchingContext) -> MatchingResult:
        """处理代码补全"""
        current_file = context.current_content.get("file_path", "")

        # 1. 获取项目上下文
        project_info = self.brain.context_engine.get_context(
            context.user_id,
            "ide_project"
        )

        # 2. 生成补全建议
        suggestions = [
            {
                "id": "comp_1",
                "type": "completion",
                "label": "async def fetch_data()",
                "insert_text": "async def fetch_data(url: str) -> Response:",
                "kind": "function",
                "detail": "异步获取数据",
                "confidence": 0.95
            },
            {
                "id": "comp_2",
                "type": "completion",
                "label": "await asyncio.gather",
                "insert_text": "await asyncio.gather(*tasks)",
                "kind": "function",
                "detail": "并发执行任务",
                "confidence": 0.85
            }
        ]

        return MatchingResult(
            items=suggestions,
            confidence=0.9,
            reasoning=f"基于当前文件 {current_file} 和项目上下文"
        )

    async def handle_refactor(self, context: MatchingContext) -> MatchingResult:
        """处理重构建议"""
        code = context.current_content.get("code", "")

        # 调用海外集群进行深度分析
        suggestions = [
            {
                "id": "ref_1",
                "type": "refactor",
                "title": "提取重复代码为函数",
                "description": "发现3处相似代码，建议提取为通用函数",
                "impact": "降低重复率 30%",
                "actions": ["应用建议"]
            }
        ]

        return MatchingResult(
            items=suggestions,
            confidence=0.8,
            reasoning="基于代码语义分析"
        )

    async def handle_dependency_scan(self, context: MatchingContext) -> MatchingResult:
        """处理依赖漏洞扫描"""
        dependencies = context.current_content.get("dependencies", [])

        # 海外集群执行扫描
        scan_results = [
            {
                "id": "dep_1",
                "type": "security",
                "package": "requests",
                "version": "2.25.1",
                "vulnerability": "CVE-2023-xxxx",
                "severity": "high",
                "fix": "升级到 2.31.0"
            }
        ]

        return MatchingResult(
            items=scan_results,
            confidence=0.95,
            reasoning="调用漏洞数据库进行匹配"
        )

    async def handle_config_sync(self, context: MatchingContext) -> MatchingResult:
        """处理配置同步"""
        configs = [
            {
                "id": "cfg_1",
                "type": "dockerfile",
                "content": "FROM python:3.11\n...",
                "last_modified": "2024-01-15"
            },
            {
                "id": "cfg_2",
                "type": "requirements.txt",
                "content": "flask>=2.0\n...",
                "last_modified": "2024-01-14"
            }
        ]

        return MatchingResult(
            items=configs,
            confidence=1.0,
            reasoning="从配置中心同步"
        )


# ============================================================================
# 智能游戏匹配器
# ============================================================================

class SmartGameMatcher:
    """
    智能游戏：云游戏 NPC AI、存档同步、攻略生成
    """

    def __init__(self, brain):
        self.brain = brain

    async def handle_game_request(
        self,
        request_type: str,
        context: MatchingContext
    ) -> MatchingResult:
        """
        处理游戏请求

        分层处理：
        - 边缘节点：流化渲染、游戏状态缓存
        - 海外集群：NPC 复杂 AI 行为树
        - 中心节点：存档同步、好友状态
        """

        if request_type == "npc_behavior":
            return await self.handle_npc_ai(context)
        elif request_type == "strategy":
            return await self.handle_strategy(context)
        elif request_type == "save_sync":
            return await self.handle_save_sync(context)

        return MatchingResult(items=[], confidence=0.0, reasoning="未知请求类型")

    async def handle_npc_ai(self, context: MatchingContext) -> MatchingResult:
        """处理 NPC AI 决策"""
        game_state = context.current_content

        # 调用海外集群运行 NPC AI
        decisions = [
            {
                "id": "npc_1",
                "npc_id": "merchant_001",
                "action": "greet",
                "dialogue": "欢迎光临！今天有什么需要？",
                "behavior_tree": "merchant_greeting"
            },
            {
                "id": "npc_2",
                "npc_id": "enemy_boss",
                "action": "attack",
                "target": "player_1",
                "skill": "fireball",
                "behavior_tree": "boss_combat"
            }
        ]

        return MatchingResult(
            items=decisions,
            confidence=0.85,
            reasoning="基于游戏状态和 AI 行为树"
        )

    async def handle_strategy(self, context: MatchingContext) -> MatchingResult:
        """生成游戏攻略"""
        game_type = context.current_content.get("game_type", "")

        # 调用深度搜索节点生成实时策略
        strategy = [
            {
                "id": "strat_1",
                "type": "realtime_strategy",
                "title": "Boss 战建议",
                "steps": [
                    "1. 保持距离，避免近战",
                    "2. 等待施法后摇时输出",
                    "3. 血量低于 30% 时使用药水"
                ],
                "success_rate": 0.8
            }
        ]

        return MatchingResult(
            items=strategy,
            confidence=0.75,
            reasoning="基于历史数据和当前局势分析"
        )

    async def handle_save_sync(self, context: MatchingContext) -> MatchingResult:
        """处理存档同步"""
        save_data = {
            "checkpoint": "level_3_boss",
            "inventory": [...],
            "stats": {...}
        }

        return MatchingResult(
            items=[{"type": "save", "data": save_data, "synced": True}],
            confidence=1.0,
            reasoning="存档已同步到云端"
        )


# ============================================================================
# 智能浏览器匹配器
# ============================================================================

class SmartBrowserMatcher:
    """
    智能浏览器：内容提取、广告拦截、知识图谱
    """

    def __init__(self, brain):
        self.brain = brain

    async def handle_browser_request(
        self,
        request_type: str,
        context: MatchingContext
    ) -> MatchingResult:
        """
        处理浏览器请求

        分层处理：
        - 海外集群：抓取并解析原始网页
        - 中心节点：广告拦截规则、隐私脚本注入
        - 边缘节点：压缩图片、缓存静态资源
        """

        if request_type == "content_extract":
            return await self.extract_content(context)
        elif request_type == "ad_block":
            return await self.block_ads(context)
        elif request_type == "knowledge_graph":
            return await self.build_knowledge_graph(context)

        return MatchingResult(items=[], confidence=0.0, reasoning="未知请求类型")

    async def extract_content(self, context: MatchingContext) -> MatchingResult:
        """提取网页关键内容"""
        url = context.current_content.get("url", "")

        # 海外集群抓取
        extracted = {
            "id": "content_1",
            "url": url,
            "title": "Python 异步编程详解",
            "key_points": [
                "asyncio 是 Python 标准库",
                "async/await 语法",
                "协程和任务的区别"
            ],
            "code_examples": [
                "async def main():\n    await asyncio.sleep(1)"
            ],
            "related_topics": ["协程", "事件循环", "异步IO"]
        }

        return MatchingResult(
            items=[extracted],
            confidence=0.9,
            reasoning=f"从 {url} 提取关键信息"
        )

    async def block_ads(self, context: MatchingContext) -> MatchingResult:
        """广告拦截"""
        blocked = [
            {
                "id": "ad_1",
                "type": "banner_ad",
                "selector": "#sidebar-ad",
                "blocked": True
            },
            {
                "id": "ad_2",
                "type": "popup_ad",
                "url": "https://ads.example.com/...",
                "blocked": True
            }
        ]

        return MatchingResult(
            items=blocked,
            confidence=0.95,
            reasoning="应用广告拦截规则"
        )

    async def build_knowledge_graph(self, context: MatchingContext) -> MatchingResult:
        """构建知识图谱"""
        content = context.current_content.get("content", "")

        # 提取实体和关系
        entities = [
            {"id": "e1", "name": "Python", "type": "编程语言"},
            {"id": "e2", "name": "asyncio", "type": "库"},
            {"id": "e3", "name": "异步编程", "type": "概念"}
        ]

        relations = [
            {"from": "e1", "to": "e2", "relation": "包含"},
            {"from": "e2", "to": "e3", "relation": "实现"}
        ]

        return MatchingResult(
            items=[{"entities": entities, "relations": relations}],
            confidence=0.8,
            reasoning="自动构建知识图谱"
        )


# ============================================================================
# 统一匹配调度器
# ============================================================================

class MatchingDispatcher:
    """
    统一匹配调度器
    """

    def __init__(self, brain):
        self.brain = brain
        self.aggregation_matcher = AggregationMatcher(brain)
        self.deep_search_matcher = DeepSearchMatcher(brain)
        self.smart_ide_matcher = SmartIDEMatcher(brain)
        self.smart_game_matcher = SmartGameMatcher(brain)
        self.smart_browser_matcher = SmartBrowserMatcher(brain)

    async def dispatch(self, context: MatchingContext) -> MatchingResult:
        """分发匹配请求"""

        if context.matching_type == MatchingType.AGGREGATION:
            return await self.aggregation_matcher.aggregate_recommendations(
                context.user_id,
                context.current_content
            )

        elif context.matching_type == MatchingType.DEEP_SEARCH:
            return await self.deep_search_matcher.deep_search(
                context.current_content.get("query", ""),
                context
            )

        elif context.matching_type == MatchingType.SMART_IDE:
            return await self.smart_ide_matcher.handle_ide_request(
                context.current_content.get("request_type", "completion"),
                context
            )

        elif context.matching_type == MatchingType.SMART_GAME:
            return await self.smart_game_matcher.handle_game_request(
                context.current_content.get("request_type", "npc_behavior"),
                context
            )

        elif context.matching_type == MatchingType.SMART_BROWSER:
            return await self.smart_browser_matcher.handle_browser_request(
                context.current_content.get("request_type", "content_extract"),
                context
            )

        return MatchingResult(
            items=[],
            confidence=0.0,
            reasoning=f"未知匹配类型: {context.matching_type}"
        )
