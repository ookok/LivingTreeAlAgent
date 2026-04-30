"""
FusionRAG 集成路由
将本地文件搜索作为 L1.5 层集成到 FusionRAG 架构中

集成架构
--------
L0: ExactCache (5ms)      - 精确匹配缓存
L1: SessionCache (15ms)   - 会话上下文缓存
L1.5: LocalFileIndex (10ms) ← 新增本地文件搜索层
L2: KnowledgeBase (50ms)  - 知识库检索
L3: Database (100ms)      - 数据库查询
L4: LLM (异步)             - 大模型生成

使用方式
--------
from client.src.business.local_file_search.router import LocalFileSearchRouter

router = LocalFileSearchRouter()

# 1. 初始化索引（后台异步）
router.init_index()

# 2. 搜索
results = router.search("*.pdf")

# 3. 集成到 FusionRAG
layer_results = router.execute_as_layer(query)
"""

import os
import sys
import re
import time
import asyncio
import threading
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class IntentType(Enum):
    """本地文件搜索意图类型"""
    FILE_FIND = "file_find"           # 找文件
    FOLDER_FIND = "folder_find"       # 找文件夹
    RECENT_FILES = "recent_files"     # 最近文件
    LARGE_FILES = "large_files"      # 大文件
    CODE_SEARCH = "code_search"       # 代码搜索
    DOC_SEARCH = "doc_search"         # 文档搜索
    MEDIA_SEARCH = "media_search"     # 媒体搜索
    CONFIG_SEARCH = "config_search"   # 配置搜索
    GENERAL = "general"              # 通用搜索


@dataclass
class SearchQuery:
    """搜索查询"""
    original: str                    # 原始查询
    intent: IntentType               # 意图类型
    keywords: List[str]              # 关键词
    filters: Dict[str, Any]          # 过滤器
    limit: int = 20                  # 返回限制


@dataclass
class LayerResult:
    """层级检索结果"""
    layer: str                       # 层名称
    results: List[Dict]              # 结果列表
    latency_ms: float                # 延迟
    source: str                      # 来源
    confidence: float = 1.0          # 置信度


class LocalFileSearchRouter:
    """
    本地文件搜索路由器
    
    集成到 FusionRAG 的四层缓存架构中
    作为 L1.5 层，介于精确缓存和知识库之间
    """
    
    # 意图模式匹配
    INTENT_PATTERNS = {
        IntentType.FILE_FIND: [
            r'(?:找|搜索|查找|定位)(?:到?|着|一下)?(.*?)(?:文件?)',
            r'(?:文件?|文档)(?:叫|名|名称是?|路径)(.*)',
            r'.*?\.(py|js|java|cpp|txt|md|pdf|doc)',
        ],
        IntentType.FOLDER_FIND: [
            r'(?:找|搜索|查找)(?:到?|着)?(.*?)(?:文件夹?|目录)',
            r'(?:在哪|位置)(.*?)(?:文件夹?|目录)',
        ],
        IntentType.RECENT_FILES: [
            r'最近(?:打开|使用|修改)?(?:的)?(?:文件?|文档)',
            r'.*recent.*',
        ],
        IntentType.LARGE_FILES: [
            r'(?:大|超大)(?:的|过)?(?:文件?|文档)',
            r'(?:最大的|最占用)(?:文件?|空间)',
        ],
        IntentType.CODE_SEARCH: [
            r'(?:代码?|源码|script)(?:文件?|搜索)',
            r'.*\.(py|js|java|cpp|c|h|go|rs|rb|php|ts)',
        ],
        IntentType.DOC_SEARCH: [
            r'(?:文档?|报告|手册|pdf|doc)(?:搜索|查找)',
            r'.*\.(pdf|doc|docx|txt|md|rtf)',
        ],
        IntentType.MEDIA_SEARCH: [
            r'(?:图片?|照片|视频|音频|音乐)(?:文件?|搜索)',
            r'.*\.(jpg|png|mp4|mp3|wav|gif|avi|mkv)',
        ],
        IntentType.CONFIG_SEARCH: [
            r'(?:配置|config)(?:文件?|搜索)',
            r'.*\.(json|yaml|yml|xml|toml|ini|conf)',
        ],
    }
    
    # 文件类型过滤
    FILE_TYPE_FILTERS = {
        IntentType.CODE_SEARCH: {'file_type': 'code'},
        IntentType.DOC_SEARCH: {'file_type': 'document'},
        IntentType.MEDIA_SEARCH: {'file_type': 'image'},
    }
    
    def __init__(self, db_path: str = None):
        """
        初始化路由器
        
        Args:
            db_path: 索引数据库路径
        """
        # 数据目录
        data_dir = Path(__file__).parent.parent.parent.parent / "data" / "file_index"
        data_dir.mkdir(parents=True, exist_ok=True)
        
        self.db_path = db_path or str(data_dir / "file_index.db")
        
        # 索引器
        self._indexer = None
        self._indexer_initialized = False
        self._init_lock = threading.Lock()
        
        # 统计
        self._stats = {
            "total_searches": 0,
            "cache_hits": 0,
            "avg_latency_ms": 0,
            "by_intent": {},
        }
        
        # 缓存
        self._cache: Dict[str, LayerResult] = {}
        self._cache_max_size = 100
        
        logger.info(f"[LocalFileSearchRouter] 初始化完成，数据库: {self.db_path}")
    
    def _ensure_indexer(self):
        """确保索引器已初始化"""
        if self._indexer is not None:
            return
        
        with self._init_lock:
            if self._indexer is not None:
                return
            
            try:
                from .indexer import FastFileIndexer
                self._indexer = FastFileIndexer(db_path=self.db_path)
                self._indexer.init_database()
                logger.info("[LocalFileSearchRouter] 索引器初始化完成")
            except Exception as e:
                logger.error(f"[LocalFileSearchRouter] 索引器初始化失败: {e}")
                self._indexer = None
    
    def init_index(self, paths: List[str] = None, background: bool = True):
        """
        初始化索引
        
        Args:
            paths: 要索引的路径
            background: 是否后台运行
        """
        self._ensure_indexer()
        
        if self._indexer_initialized:
            logger.info("[LocalFileSearchRouter] 索引已初始化")
            return
        
        if background:
            thread = threading.Thread(
                target=self._do_index,
                args=(paths,),
                daemon=True
            )
            thread.start()
            logger.info("[LocalFileSearchRouter] 后台索引启动")
        else:
            self._do_index(paths)
    
    def _do_index(self, paths: List[str] = None):
        """执行索引"""
        try:
            self._indexer.build_index(paths)
            self._indexer_initialized = True
            logger.info("[LocalFileSearchRouter] 索引构建完成")
        except Exception as e:
            logger.error(f"[LocalFileSearchRouter] 索引构建失败: {e}")
    
    def parse_intent(self, query: str) -> SearchQuery:
        """
        解析查询意图
        
        Args:
            query: 原始查询
            
        Returns:
            解析后的搜索查询
        """
        query_lower = query.lower()
        
        # 匹配意图
        detected_intent = IntentType.GENERAL
        for intent, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    detected_intent = intent
                    break
            if detected_intent != IntentType.GENERAL:
                break
        
        # 提取关键词
        keywords = self._extract_keywords(query)
        
        # 提取过滤器
        filters = self._extract_filters(query)
        
        # 添加基于意图的过滤器
        if detected_intent in self.FILE_TYPE_FILTERS:
            filters.update(self.FILE_TYPE_FILTERS[detected_intent])
        
        # 提取数量限制
        limit = self._extract_limit(query)
        
        return SearchQuery(
            original=query,
            intent=detected_intent,
            keywords=keywords,
            filters=filters,
            limit=limit
        )
    
    def _extract_keywords(self, query: str) -> List[str]:
        """提取关键词"""
        # 移除常见停用词
        stop_words = {'找', '搜索', '查找', '定位', '在', '哪里', '的', '文件', '文件夹', '最近', '打开'}
        
        words = re.split(r'[\s,，、]+', query)
        keywords = [w for w in words if w and w not in stop_words]
        
        # 如果没有关键词，尝试提取文件名模式
        if not keywords:
            ext_match = re.findall(r'\.(\w+)', query)
            if ext_match:
                keywords = [f'.{ext}' for ext in ext_match]
        
        return keywords
    
    def _extract_filters(self, query: str) -> Dict[str, Any]:
        """提取过滤器"""
        filters = {}
        
        # 文件大小过滤
        size_match = re.search(r'(?:大于|小于|超过|小于|小于等于|大于等于)(?:.*?)?(\d+)(MB|GB|KB)', query)
        if size_match:
            value, unit = size_match.groups()
            multipliers = {'KB': 1024, 'MB': 1024**2, 'GB': 1024**3}
            filters['min_size'] = int(value) * multipliers.get(unit, 1)
        
        # 扩展名过滤
        ext_match = re.findall(r'\.(\w+)', query)
        if ext_match:
            filters['extension'] = [f'.{ext.lower()}' for ext in ext_match]
        
        return filters
    
    def _extract_limit(self, query: str) -> int:
        """提取数量限制"""
        match = re.search(r'(?:前|只|返回)(?:.*?)?(\d+)', query)
        if match:
            return min(int(match.group(1)), 100)
        return 20
    
    def search(self, query: str, limit: int = None) -> List[Dict]:
        """
        搜索文件
        
        Args:
            query: 搜索查询
            limit: 返回数量
            
        Returns:
            搜索结果列表
        """
        start_time = time.time()
        self._stats["total_searches"] += 1
        
        # 检查缓存
        cache_key = query
        if cache_key in self._cache:
            self._stats["cache_hits"] += 1
            return self._cache[cache_key].results[:limit]
        
        # 确保索引器可用
        self._ensure_indexer()
        
        if self._indexer is None or not self._indexer_initialized:
            return []
        
        # 解析意图
        search_query = self.parse_intent(query)
        
        if limit is None:
            limit = search_query.limit
        
        # 执行搜索
        results = []
        try:
            # 构建搜索词
            search_term = search_query.keywords[0] if search_query.keywords else query
            
            # 执行索引搜索
            search_results = self._indexer.search(
                search_term,
                limit=limit * 2,  # 多取一些用于过滤
                file_type=search_query.filters.get('file_type'),
                min_size=search_query.filters.get('min_size', 0),
                max_size=search_query.filters.get('max_size'),
            )
            
            # 转换结果
            for r in search_results[:limit]:
                result_dict = r.to_dict()
                result_dict['intent'] = search_query.intent.value
                results.append(result_dict)
            
        except Exception as e:
            logger.error(f"[LocalFileSearchRouter] 搜索失败: {e}")
        
        # 更新统计
        elapsed = (time.time() - start_time) * 1000
        self._update_stats(search_query.intent, elapsed)
        
        # 缓存结果
        layer_result = LayerResult(
            layer="local_file",
            results=results,
            latency_ms=elapsed,
            source="file_index",
            confidence=0.95 if results else 0.0
        )
        self._cache[cache_key] = layer_result
        
        # 清理缓存
        if len(self._cache) > self._cache_max_size:
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        
        logger.debug(f"[LocalFileSearchRouter] 搜索 '{query}' 完成，{len(results)} 结果，{elapsed:.1f}ms")
        
        return results
    
    def _update_stats(self, intent: IntentType, latency_ms: float):
        """更新统计"""
        intent_name = intent.value
        if intent_name not in self._stats["by_intent"]:
            self._stats["by_intent"][intent_name] = {"count": 0, "avg_latency_ms": 0}
        
        stats = self._stats["by_intent"][intent_name]
        count = stats["count"]
        avg = stats["avg_latency_ms"]
        
        stats["count"] = count + 1
        stats["avg_latency_ms"] = (avg * count + latency_ms) / (count + 1)
        
        # 更新全局平均延迟
        total = self._stats["total_searches"]
        current_avg = self._stats["avg_latency_ms"]
        self._stats["avg_latency_ms"] = (current_avg * (total - 1) + latency_ms) / total
    
    async def search_async(self, query: str, limit: int = None) -> List[Dict]:
        """异步搜索"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.search(query, limit))
    
    def execute_as_layer(
        self,
        query: str,
        strategy: str = "balanced"
    ) -> LayerResult:
        """
        作为 FusionRAG 层执行
        
        Args:
            query: 查询
            strategy: 路由策略
            
        Returns:
            层级结果
        """
        start_time = time.time()
        
        results = self.search(query)
        
        elapsed = (time.time() - start_time) * 1000
        
        return LayerResult(
            layer="local_file",
            results=results,
            latency_ms=elapsed,
            source="file_index",
            confidence=0.95 if results else 0.0
        )
    
    def should_activate(self, query: str) -> bool:
        """
        判断是否应该激活本地文件搜索层
        
        Args:
            query: 查询文本
            
        Returns:
            是否激活
        """
        # 检测是否包含文件搜索意图
        query_lower = query.lower()
        
        # 文件相关关键词
        file_keywords = [
            '找', '搜索', '查找', '定位', '文件', '文档', '夹', '目录',
            '在哪', '哪里', '打开', '最近', '大文件', '代码', '源码',
        ]
        
        # 文件扩展名
        has_extension = bool(re.search(r'\.\w{1,10}', query))
        
        # 文件意图关键词
        has_file_intent = any(kw in query_lower for kw in file_keywords)
        
        return has_file_intent or has_extension
    
    def get_layer_config(self) -> Dict[str, Any]:
        """
        获取层配置
        
        Returns:
            FusionRAG 层配置
        """
        return {
            "name": "local_file",
            "layer": 1.5,  # L1.5 层
            "priority": 15,
            "max_latency_ms": 10,
            "weight_base": 0.15,
            "parallel": True,
            "requires_index": True,
            "index_initialized": self._indexer_initialized,
            "indexed_files": self._indexer._indexed_count if self._indexer else 0,
            "index_size_mb": self._indexer.get_index_size() / (1024*1024) if self._indexer else 0,
        }
    
    def get_stats(self) -> Dict:
        """获取统计"""
        return {
            **self._stats,
            "cache_size": len(self._cache),
            "index_initialized": self._indexer_initialized,
            "indexed_files": self._indexer._indexed_count if self._indexer else 0,
        }


# ==================== FusionRAG 集成补丁 ====================

def patch_fusion_rag_router():
    """
    补丁 FusionRAG 的 IntelligentRouter
    
    将本地文件搜索作为 L1.5 层集成
    """
    try:
        from client.src.business.fusion_rag.intelligent_router import IntelligentRouter
        
        # 保存原始配置
        original_layer_configs = IntelligentRouter.__dict__.get('_original_layer_configs')
        
        if original_layer_configs is None:
            # 保存原始配置
            IntelligentRouter._original_layer_configs = {
                "exact_cache": {
                    "max_latency_ms": 5,
                    "weight_base": 0.35,
                    "priority": 1,
                    "parallel": True
                },
                "session_cache": {
                    "max_latency_ms": 15,
                    "weight_base": 0.25,
                    "priority": 2,
                    "parallel": True
                },
                "knowledge_base": {
                    "max_latency_ms": 50,
                    "weight_base": 0.30,
                    "priority": 3,
                    "parallel": True
                },
                "database": {
                    "max_latency_ms": 100,
                    "weight_base": 0.10,
                    "priority": 4,
                    "parallel": True
                }
            }
        
        # 添加 L1.5 层
        IntelligentRouter.layer_configs["local_file"] = {
            "max_latency_ms": 10,
            "weight_base": 0.15,
            "priority": 1.5,
            "parallel": True
        }
        
        # 更新意图映射
        original_intent_map = IntelligentRouter.__dict__.get('_original_intent_layer_map')
        if original_intent_map is None:
            IntelligentRouter._original_intent_layer_map = {
                "factual": ["exact_cache", "knowledge_base", "database"],
                "conversational": ["exact_cache", "session_cache", "knowledge_base"],
                "procedural": ["exact_cache", "knowledge_base"],
                "creative": ["exact_cache", "session_cache"],
                "hybrid": ["exact_cache", "session_cache", "knowledge_base", "database"]
            }
        
        # 添加文件搜索意图
        IntelligentRouter.intent_layer_map["file_search"] = [
            "local_file", "exact_cache", "knowledge_base"
        ]
        
        logger.info("[LocalFileSearchRouter] FusionRAG 补丁已应用")
        
    except ImportError as e:
        logger.warning(f"[LocalFileSearchRouter] 无法导入 FusionRAG: {e}")


# ==================== 全局单例 ====================

_router_instance: Optional[LocalFileSearchRouter] = None
_router_lock = threading.Lock()


def get_local_file_router() -> LocalFileSearchRouter:
    """获取全局单例"""
    global _router_instance
    with _router_lock:
        if _router_instance is None:
            _router_instance = LocalFileSearchRouter()
        return _router_instance


async def async_search_files(query: str, limit: int = 20) -> List[Dict]:
    """异步搜索文件的快捷函数"""
    router = get_local_file_router()
    return await router.search_async(query, limit)


def search_files(query: str, limit: int = 20) -> List[Dict]:
    """搜索文件的快捷函数"""
    router = get_local_file_router()
    return router.search(query, limit)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    router = LocalFileSearchRouter()
    
    # 初始化索引（后台）
    router.init_index()
    
    # 测试意图解析
    print("\n意图解析测试:")
    test_queries = [
        "找一下 *.py 文件",
        "搜索 main.js",
        "最近的文档有哪些",
        "大于 10MB 的文件",
        "配置文件的路径",
        "代码文件在哪里",
    ]
    
    for q in test_queries:
        sq = router.parse_intent(q)
        print(f"  '{q}'")
        print(f"    -> 意图: {sq.intent.value}, 关键词: {sq.keywords}, 过滤器: {sq.filters}")
    
    # 等待索引完成
    import time
    print("\n等待索引构建...")
    while not router._indexer_initialized:
        time.sleep(1)
    
    # 搜索测试
    print("\n搜索测试:")
    results = router.search("*.py", limit=5)
    for r in results[:5]:
        print(f"  {r['path']}")
    
    print(f"\n统计: {router.get_stats()}")
    print(f"层配置: {router.get_layer_config()}")
