"""
本地文件系统极速搜索模块
Everything-Style 实现

架构设计
========

目标：实现毫秒级本地文件搜索，接近 Everything 的性能

核心原理
--------
1. SQLite FTS5 全文索引 - 毫秒级搜索
2. 多线程并行索引 - 高速构建
3. USN Journal 增量更新（Windows）- 实时同步
4. 内存缓存 - 热点文件预加载
5. 异步初始化 - 后台构建不阻塞

集成到 FusionRAG
----------------
作为 L1.5 层插入现有架构：
L0: ExactCache (5ms)
L1: SessionCache (15ms)
L1.5: LocalFileIndex (10ms) ← 新增
L2: KnowledgeBase (50ms)
L3: Database (100ms)
L4: LLM (异步)

模块结构
--------
core/local_file_search/
├── __init__.py              # 模块入口
├── indexer.py               # FastFileIndexer 核心
├── usn_monitor.py           # USN Journal 监听
├── sqlite_fts.py            # SQLite FTS5 全文搜索
├── incremental_sync.py      # 增量同步
├── file_classifier.py       # 文件类型分类
└── router.py                # FusionRAG 集成路由

使用方式
--------
1. 后台异步初始化索引（首次运行）
2. USN Journal 增量更新（Windows）
3. FTS5 毫秒级搜索
4. 搜索结果直接返回文件路径
"""

from .indexer import FastFileIndexer, FileSearchResult, FileType, get_file_indexer, quick_search
from .file_classifier import FileClassifier, FileCategory, get_classifier
from .router import LocalFileSearchRouter, IntentType, get_local_file_router, search_files
from .incremental_sync import IncrementalSync, IncrementalIndexer, SyncStrategy
from .sqlite_fts import SQLiteFTSSearch
from .usn_monitor import USNJournalMonitor, USNJournalReader, USNChange, is_usn_available

__all__ = [
    # 核心索引
    'FastFileIndexer',
    'FileSearchResult',
    'FileType',
    'get_file_indexer',
    'quick_search',
    
    # 文件分类
    'FileClassifier',
    'FileCategory',
    'get_classifier',
    
    # 路由集成
    'LocalFileSearchRouter',
    'IntentType',
    'get_local_file_router',
    'search_files',
    
    # 增量同步
    'IncrementalSync',
    'IncrementalIndexer',
    'SyncStrategy',
    
    # FTS
    'SQLiteFTSSearch',
    
    # USN Journal
    'USNJournalMonitor',
    'USNJournalReader',
    'USNChange',
    'is_usn_available',
]
