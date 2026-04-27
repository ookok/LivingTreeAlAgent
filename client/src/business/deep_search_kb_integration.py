"""
深度搜索知识库集成
=================

功能：
1. 深度搜索完成后自动存入知识库
2. 会话结束后自动提取并存入知识库
3. 与现有 L4Executor / DeepSearchWikiSystem 集成

使用方式：
    from core.deep_search_kb_integration import DeepSearchKBIntegration

    integration = DeepSearchKBIntegration()
    integration.setup_hooks()  # 注册自动摄入钩子
"""

import logging
import time
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


class DeepSearchKBIntegration:
    """
    深度搜索与知识库集成器

    工作流程：
    1. 用户发起深度搜索
    2. DeepSearchWikiSystem 执行搜索
    3. 搜索结果通过钩子自动存入知识库
    4. 同时支持会话结束后提取关键信息
    """

    def __init__(self):
        self._hooks_registered = False
        self._ingest_callbacks: List[Callable] = []
        self._session_callbacks: List[Callable] = []

        # 统计
        self.stats = {
            "search_results_ingested": 0,
            "sessions_ingested": 0,
            "total_chars": 0,
        }

    # ── 钩子注册 ────────────────────────────────────────────────────────

    def setup_hooks(self):
        """设置自动钩子（调用一次即可）"""
        if self._hooks_registered:
            logger.warning("[DSKBI] 钩子已注册，跳过")
            return

        try:
            # 延迟导入避免循环依赖
            from core.knowledge_auto_ingest import get_kb_ingest, get_kb_hooks, ContentSource

            kb_ingest = get_kb_ingest()
            kb_hooks = get_kb_hooks()

            # 注册搜索结果摄入回调
            kb_ingest.register_callback("search_ingested", self._on_entry_ingested)

            self._hooks_registered = True
            logger.info("[DSKBI] 深度搜索知识库集成钩子已注册")

        except Exception as e:
            logger.error(f"[DSKBI] 钩子注册失败: {e}")

    def register_ingest_callback(self, callback: Callable):
        """注册自定义摄入回调"""
        self._ingest_callbacks.append(callback)

    def register_session_callback(self, callback: Callable):
        """注册会话结束回调"""
        self._session_callbacks.append(callback)

    def _on_entry_ingested(self, entry):
        """条目摄入回调"""
        self.stats["search_results_ingested"] += 1
        self.stats["total_chars"] += len(entry.content)

        for cb in self._ingest_callbacks:
            try:
                cb(entry)
            except Exception as e:
                logger.warning(f"[DSKBI] 回调执行失败: {e}")

    # ── 搜索结果摄入 ─────────────────────────────────────────────────────

    def ingest_search_results(
        self,
        query: str,
        results: List[Dict[str, Any]],
        source: str = "deep_search",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        摄入搜索结果

        Args:
            query: 搜索查询
            results: 搜索结果列表
            source: 来源标识
            metadata: 额外元数据

        Returns:
            摄入统计
        """
        try:
            from core.knowledge_auto_ingest import get_kb_ingest, ContentSource

            kb_ingest = get_kb_ingest()

            # 格式化结果
            formatted_results = []
            for i, r in enumerate(results):
                formatted_results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("content", r.get("snippet", "")),
                    "rank": i,
                    "source": source,
                })

            # 摄入
            stats = kb_ingest.ingest_search_result(
                query=query,
                results=formatted_results,
                metadata={
                    "source": source,
                    "search_engine": source,
                    **(metadata or {})
                }
            )

            self.stats["search_results_ingested"] += stats["ingested"]
            self.stats["total_chars"] += sum(
                len(r["snippet"]) for r in formatted_results[:stats["ingested"]]
            )

            logger.info(f"[DSKBI] 搜索结果摄入: query={query[:30]}, ingested={stats['ingested']}")
            return stats

        except Exception as e:
            logger.error(f"[DSKBI] 摄入搜索结果失败: {e}")
            return {"ingested": 0, "duplicates": 0, "failed": 1}

    def ingest_deep_search_result(
        self,
        query: str,
        wiki_content: str,
        sources: List[str],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        摄入深度搜索Wiki结果

        专门处理 DeepSearchWikiSystem 的输出

        Args:
            query: 搜索查询
            wiki_content: Wiki格式的完整内容
            sources: 来源URL列表
            metadata: 额外元数据

        Returns:
            摄入统计
        """
        try:
            from core.knowledge_auto_ingest import get_kb_ingest, ContentSource, KnowledgeEntry
            import hashlib

            kb_ingest = get_kb_ingest()

            # 生成唯一ID
            doc_id = f"wiki_{hashlib.md5(query.encode()).hexdigest()[:16]}"

            # 构建条目
            entry = KnowledgeEntry(
                doc_id=doc_id,
                content=wiki_content,
                title=f"深度搜索: {query}",
                source=ContentSource.DEEP_SEARCH,
                search_query=query,
                metadata={
                    "type": "wiki",
                    "sources": sources,
                    "search_engine": "deep_search",
                    "created_via": "DeepSearchKBIntegration",
                    **(metadata or {})
                }
            )

            # 保存
            kb_ingest._save_entry(entry)

            # 同时将来源URL单独存入
            for i, url in enumerate(sources[:5]):  # 最多5个来源
                source_id = f"src_{hashlib.md5(url.encode()).hexdigest()[:12]}"
                source_entry = KnowledgeEntry(
                    doc_id=source_id,
                    content=f"来源{i+1}: {url}",
                    title=f"来源: {query}",
                    source=ContentSource.DEEP_SEARCH,
                    source_url=url,
                    search_query=query,
                    metadata={"type": "source_url", "rank": i}
                )
                kb_ingest._save_entry(source_entry)

            self.stats["search_results_ingested"] += 1
            self.stats["total_chars"] += len(wiki_content)

            return {"doc_id": doc_id, "sources_stored": len(sources)}

        except Exception as e:
            logger.error(f"[DSKBI] 摄入Wiki结果失败: {e}")
            return {"failed": 1, "error": str(e)}

    # ── 会话摄入 ────────────────────────────────────────────────────────

    def ingest_session(
        self,
        session_id: str,
        messages: List[Dict[str, Any]],
        user_id: str = "default"
    ) -> Dict[str, Any]:
        """
        摄入会话内容

        Args:
            session_id: 会话ID
            messages: 消息列表 [{"role": str, "content": str, ...}]
            user_id: 用户ID

        Returns:
            摄入统计
        """
        try:
            from core.knowledge_auto_ingest import get_kb_ingest, ConversationExtractor

            kb_ingest = get_kb_ingest()
            extractor = ConversationExtractor()

            stats = {"questions": 0, "facts": 0}

            for msg in messages:
                role = msg.get("role", "")
                content = msg.get("content", "").strip()

                if not content or len(content) < 30:
                    continue

                if role == "user":
                    # 提取问题
                    questions = extractor.extract_questions(content)
                    for q in questions:
                        kb_ingest._save_knowledge_from_text(
                            q, session_id, "question", user_id,
                            kb_ingest._get_source_enum("conversation")
                        )
                        stats["questions"] += 1

                elif role == "assistant":
                    # 提取事实
                    facts = extractor.extract_facts(content)
                    for fact in facts:
                        importance = extractor.estimate_importance(fact)
                        if importance >= 0.5:
                            kb_ingest._save_knowledge_from_text(
                                fact, session_id, "fact", user_id,
                                kb_ingest._get_source_enum("conversation")
                            )
                            stats["facts"] += 1

            self.stats["sessions_ingested"] += 1
            logger.info(f"[DSKBI] 会话摄入: session={session_id}, {stats}")
            return stats

        except Exception as e:
            logger.error(f"[DSKBI] 摄入会话失败: {e}")
            return {"failed": 1, "error": str(e)}

    # ── 查询知识库 ───────────────────────────────────────────────────────

    def query_knowledge(
        self,
        query: str,
        source: Optional[str] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        查询知识库

        Args:
            query: 查询文本
            source: 来源过滤（如 "deep_search", "conversation"）
            top_k: 返回数量

        Returns:
            知识条目列表
        """
        try:
            from core.knowledge_auto_ingest import get_kb_ingest, ContentSource

            kb_ingest = get_kb_ingest()

            source_enum = None
            if source:
                source_enum = ContentSource(source)

            entries = kb_ingest.search_knowledge(
                query=query,
                source=source_enum,
                top_k=top_k
            )

            return [
                {
                    "doc_id": e.doc_id,
                    "content": e.content,
                    "title": e.title,
                    "source": e.source.value,
                    "score": e.relevance_score,
                    "created_at": e.created_at.isoformat(),
                }
                for e in entries
            ]

        except Exception as e:
            logger.error(f"[DSKBI] 查询失败: {e}")
            return []

    # ── 统计 ────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        try:
            from core.knowledge_auto_ingest import get_kb_ingest

            kb_ingest = get_kb_ingest()
            kb_stats = kb_ingest.get_stats()

            return {
                **self.stats,
                "kb_stats": kb_stats,
            }
        except Exception:
            return self.stats

    def get_recent_knowledge(
        self,
        source: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """获取最近的知识"""
        try:
            from core.knowledge_auto_ingest import get_kb_ingest, ContentSource
            import sqlite3

            kb_ingest = get_kb_ingest()

            conn = sqlite3.connect(str(kb_ingest.db_path))
            cursor = conn.cursor()

            if source:
                cursor.execute(
                    """SELECT * FROM knowledge_entries
                       WHERE source = ?
                       ORDER BY created_at DESC
                       LIMIT ?""",
                    (source, limit)
                )
            else:
                cursor.execute(
                    """SELECT * FROM knowledge_entries
                       ORDER BY created_at DESC
                       LIMIT ?""",
                    (limit,)
                )

            rows = cursor.fetchall()
            conn.close()

            results = []
            for row in rows:
                entry = kb_ingest._row_to_entry(row)
                results.append({
                    "doc_id": entry.doc_id,
                    "content": entry.content[:200],
                    "title": entry.title,
                    "source": entry.source.value,
                    "created_at": entry.created_at.isoformat(),
                })

            return results

        except Exception as e:
            logger.error(f"[DSKBI] 获取最近知识失败: {e}")
            return []


# ── 与 L4Executor 集成 ─────────────────────────────────────────────────────

class L4ExecutorKBWrapper:
    """
    L4Executor 知识库包装器

    包装 L4RelayExecutor，自动将执行结果存入知识库
    """

    def __init__(self, executor=None):
        self.executor = executor
        self.ds_kb = DeepSearchKBIntegration()

        # 如果传入 executor，则设置回写回调
        if executor:
            self._setup_write_back()

    def _setup_write_back(self):
        """设置回写回调"""
        def write_back_to_kb(cache_key: str, result: Dict[str, Any]):
            """将结果写入知识库"""
            try:
                # 提取内容
                content = ""
                if isinstance(result, dict):
                    if "content" in result:
                        content = result["content"]
                    elif "choices" in result:
                        choices = result["choices"]
                        if choices and len(choices) > 0:
                            choice = choices[0]
                            if "message" in choice:
                                content = choice["message"].get("content", "")

                if content and len(content) > 100:
                    # 存入知识库
                    self.ds_kb.ingest_search_results(
                        query=cache_key[:50],
                        results=[{"content": content, "title": "L4执行结果", "url": ""}],
                        source="l4_executor"
                    )

            except Exception as e:
                logger.warning(f"[L4KBWrapper] 回写失败: {e}")

        if hasattr(self.executor, "set_write_back_callback"):
            self.executor.set_write_back_callback(write_back_to_kb)

    async def execute_with_kb(self, *args, **kwargs) -> Dict[str, Any]:
        """执行并自动存入知识库"""
        result = await self.executor.execute(*args, **kwargs)
        return result


# ── 与 DeepSearchWikiSystem 集成 ──────────────────────────────────────────

class DeepSearchWikiKBWrapper:
    """
    DeepSearchWikiSystem 知识库包装器

    包装 DeepSearchWikiSystem，自动将Wiki结果存入知识库
    """

    def __init__(self, wiki_system=None):
        self.wiki_system = wiki_system
        self.ds_kb = DeepSearchKBIntegration()

    async def search_with_kb(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        执行搜索并自动存入知识库
        """
        # 执行搜索
        if self.wiki_system:
            result = await self.wiki_system.search(query, **kwargs)
        else:
            # 没有 wiki_system 时的降级
            result = {"content": f"关于 {query} 的搜索结果", "sources": []}

        # 存入知识库
        wiki_content = result.get("content", "")
        sources = result.get("sources", [])

        if wiki_content:
            self.ds_kb.ingest_deep_search_result(
                query=query,
                wiki_content=wiki_content,
                sources=sources,
                metadata={"via": "DeepSearchWikiKBWrapper"}
            )

        return result


# ── 与 SessionDB 集成 ──────────────────────────────────────────────────────

class SessionDBKBWrapper:
    """
    SessionDB 知识库包装器

    在会话结束时自动将会话内容存入知识库
    """

    def __init__(self, session_db=None):
        self.session_db = session_db
        self.ds_kb = DeepSearchKBIntegration()

    def on_session_end(self, session_id: str, user_id: str = "default"):
        """
        会话结束回调

        在 SessionDB 结束会话时调用此方法
        """
        if not self.session_db:
            logger.warning("[SDBKB] SessionDB 未初始化")
            return

        try:
            # 获取会话消息
            messages = self.session_db.get_messages(session_id)

            if messages:
                self.ds_kb.ingest_session(
                    session_id=session_id,
                    messages=[
                        {"role": m.role, "content": m.content}
                        for m in messages
                    ],
                    user_id=user_id
                )

        except Exception as e:
            logger.error(f"[SDBKB] 会话结束处理失败: {e}")


# ── 全局实例 ───────────────────────────────────────────────────────────────

_ds_kb_integration: Optional[DeepSearchKBIntegration] = None


def get_ds_kb_integration() -> DeepSearchKBIntegration:
    """获取集成实例"""
    global _ds_kb_integration
    if _ds_kb_integration is None:
        _ds_kb_integration = DeepSearchKBIntegration()
    return _ds_kb_integration


# ── 测试 ───────────────────────────────────────────────────────────────────

async def test_ds_kb_integration():
    """测试深度搜索知识库集成"""
    print("=" * 60)
    print("测试深度搜索知识库集成")
    print("=" * 60)

    ds_kb = get_ds_kb_integration()

    # 测试1: 摄入搜索结果
    print("\n1. 测试摄入搜索结果")
    results = [
        {"title": "Python教程", "url": "https://python.org", "snippet": "Python是一种高级编程语言"},
        {"title": "JavaScript教程", "url": "https://js.com", "snippet": "JavaScript是一种脚本语言"},
    ]
    stats = ds_kb.ingest_search_results("编程语言教程", results, source="test")
    print(f"   结果: {stats}")

    # 测试2: 摄入Wiki结果
    print("\n2. 测试摄入Wiki结果")
    wiki_stats = ds_kb.ingest_deep_search_result(
        query="机器学习",
        wiki_content="机器学习是人工智能的一个分支，它使用数据来训练模型...",
        sources=["https://wiki.example.com/ml", "https://wiki.example.com/ai"]
    )
    print(f"   结果: {wiki_stats}")

    # 测试3: 查询知识库
    print("\n3. 测试查询知识库")
    kb_results = ds_kb.query_knowledge("Python")
    print(f"   找到 {len(kb_results)} 条结果")

    # 测试4: 统计
    print("\n4. 统计信息")
    stats = ds_kb.get_stats()
    print(f"   {stats}")

    print("\n测试完成!")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_ds_kb_integration())
