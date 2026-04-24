"""
知识库钩子集成器
================

将知识库创新功能集成到HermesAgent的运行时钩子中。

钩子位置：
1. send_message 开始 → 记录查询
2. 深度搜索完成 → 存入知识库
3. 知识库搜索完成 → 强化记忆 + 记录引用
4. 会话结束 → 提取并存入会话内容
5. 定时触发 → GC + 遗忘衰减

使用方式：
    from core.knowledge_hooks import setup_knowledge_hooks

    # 在HermesAgent初始化后调用
    agent = HermesAgent(config)
    setup_knowledge_hooks(agent)
"""

import asyncio
import logging
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class KnowledgeHookManager:
    """
    知识库钩子管理器

    统一管理所有知识库相关钩子
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._hooks_enabled = False
        self._agent = None
        self._gc_thread: Optional[threading.Thread] = None
        self._gc_running = False

        # 配置
        self.config = {
            "auto_ingest_search": True,      # 自动摄入搜索结果
            "auto_ingest_conversation": True, # 自动摄入会话内容
            "auto_gc": True,                 # 自动GC
            "gc_interval_minutes": 60,        # GC间隔
            "decay_enabled": True,            # 遗忘衰减
            "decay_interval_hours": 24,       # 衰减检查间隔
        }

        self._initialized = True
        logger.info("[KnowledgeHooks] 知识库钩子管理器初始化完成")

    def _lazy_imports(self):
        """延迟导入知识库模块"""
        try:
            from core.knowledge_auto_ingest import get_kb_ingest, get_kb_gc
            from core.deep_search_kb_integration import get_ds_kb_integration
            from core.knowledge_innovation import (
                get_semantic_dedup,
                get_value_scorer,
                get_active_learner,
                get_kg_enhancer,
                get_forgetting_mechanism,
            )
            return {
                "kb_ingest": get_kb_ingest,
                "kb_gc": get_kb_gc,
                "ds_kb": get_ds_kb_integration,
                "dedup": get_semantic_dedup,
                "scorer": get_value_scorer,
                "learner": get_active_learner,
                "kg": get_kg_enhancer,
                "forgetting": get_forgetting_mechanism,
            }
        except ImportError as e:
            logger.warning(f"[KnowledgeHooks] 导入知识库模块失败: {e}")
            return {}

    def setup_hooks(self, agent):
        """设置知识库钩子"""
        if self._hooks_enabled:
            logger.warning("[KnowledgeHooks] 钩子已启用，跳过")
            return

        self._agent = agent
        self._hooks_enabled = True

        # 启动定时任务
        if self.config["auto_gc"]:
            self._start_gc_thread()

        logger.info("[KnowledgeHooks] 知识库钩子设置完成")

    def _start_gc_thread(self):
        """启动GC线程"""
        if self._gc_thread and self._gc_thread.is_alive():
            return

        self._gc_running = True
        self._gc_thread = threading.Thread(target=self._gc_loop, daemon=True)
        self._gc_thread.start()
        logger.info("[KnowledgeHooks] GC线程已启动")

    def _gc_loop(self):
        """GC循环"""
        while self._gc_running:
            try:
                # 等待间隔
                time.sleep(self.config["gc_interval_minutes"] * 60)

                if not self._gc_running:
                    break

                # 执行GC
                self.run_periodic_gc()

            except Exception as e:
                logger.warning(f"[KnowledgeHooks] GC循环出错: {e}")

    def run_periodic_gc(self):
        """执行周期性GC"""
        try:
            modules = self._lazy_imports()
            if not modules:
                return

            # 1. 遗忘衰减
            if self.config["decay_enabled"]:
                forgetting = modules["forgetting"]()
                forgotten_count = forgetting.apply_decay()
                if forgotten_count > 0:
                    logger.info(f"[KnowledgeHooks] 遗忘衰减: {forgotten_count}条知识被标记")

            # 2. 知识库GC
            gc = modules["kb_gc"]()
            if gc.should_gc():
                result = gc.run_gc(dry_run=False)
                logger.info(f"[KnowledgeHooks] 知识库GC完成: 删除{result['to_delete']}条")

        except Exception as e:
            logger.warning(f"[KnowledgeHooks] 周期性GC失败: {e}")

    # ── 钩子回调 ────────────────────────────────────────────────────────

    def on_query_received(self, query: str):
        """查询接收钩子"""
        if not self.config["auto_ingest_search"]:
            return

        try:
            modules = self._lazy_imports()
            if not modules:
                return

            # 记录到主动学习器
            learner = modules["learner"]()
            learner.on_query(query)

        except Exception as e:
            logger.warning(f"[KnowledgeHooks] on_query_received失败: {e}")

    def on_deep_search_complete(
        self,
        query: str,
        results: List[Dict[str, Any]]
    ):
        """深度搜索完成钩子"""
        if not self.config["auto_ingest_search"]:
            return

        try:
            modules = self._lazy_imports()
            if not modules:
                return

            ds_kb = modules["ds_kb"]()
            stats = ds_kb.ingest_search_results(query, results, source="deep_search")
            logger.info(f"[KnowledgeHooks] 深度搜索摄入: {stats}")

            # 知识图谱增强
            kg = modules["kg"]()
            for result in results[:3]:  # 最多处理3条
                content = result.get("content", result.get("snippet", ""))
                title = result.get("title", "")
                if content:
                    kg.enhance_knowledge(
                        doc_id=f"search_{hash(query) % 100000}",
                        content=content,
                        title=title
                    )

        except Exception as e:
            logger.warning(f"[KnowledgeHooks] on_deep_search_complete失败: {e}")

    def on_kb_search_complete(
        self,
        query: str,
        results: List[Dict[str, Any]]
    ):
        """知识库搜索完成钩子"""
        try:
            modules = self._lazy_imports()
            if not modules:
                return

            # 记录引用
            scorer = modules["scorer"]()
            for result in results:
                doc_id = result.get("doc_id")
                if doc_id:
                    scorer.record_citation(doc_id)

                    # 强化记忆
                    forgetting = modules["forgetting"]()
                    forgetting.on_access(doc_id)

        except Exception as e:
            logger.warning(f"[KnowledgeHooks] on_kb_search_complete失败: {e}")

    def on_session_end(self, session_id: str, messages: List[Dict[str, Any]]):
        """会话结束钩子"""
        if not self.config["auto_ingest_conversation"]:
            return

        try:
            modules = self._lazy_imports()
            if not modules:
                return

            ds_kb = modules["ds_kb"]()
            stats = ds_kb.ingest_session(session_id, messages)
            logger.info(f"[KnowledgeHooks] 会话摄入: {stats}")

        except Exception as e:
            logger.warning(f"[KnowledgeHooks] on_session_end失败: {e}")

    def on_response_generated(
        self,
        query: str,
        response: str,
        context: Optional[Dict[str, Any]] = None
    ):
        """响应生成钩子"""
        try:
            modules = self._lazy_imports()
            if not modules:
                return

            # 知识图谱增强
            kg = modules["kg"]()
            kg.enhance_knowledge(
                doc_id=f"resp_{hash(query) % 100000}",
                content=response,
                title=f"响应: {query[:50]}"
            )

        except Exception as e:
            logger.warning(f"[KnowledgeHooks] on_response_generated失败: {e}")

    def on_user_correction(
        self,
        original_text: str,
        corrected_text: str
    ):
        """用户纠正钩子"""
        try:
            modules = self._lazy_imports()
            if not modules:
                return

            learner = modules["learner"]()
            learner.on_user_correction(original_text, corrected_text)

        except Exception as e:
            logger.warning(f"[KnowledgeHooks] on_user_correction失败: {e}")

    def shutdown(self):
        """关闭钩子"""
        self._gc_running = False
        if self._gc_thread:
            self._gc_thread.join(timeout=5)
        self._hooks_enabled = False
        logger.info("[KnowledgeHooks] 钩子管理器已关闭")


# ── 全局实例 ────────────────────────────────────────────────────────────

_hook_manager: Optional[KnowledgeHookManager] = None


def get_hook_manager() -> KnowledgeHookManager:
    """获取钩子管理器"""
    global _hook_manager
    if _hook_manager is None:
        _hook_manager = KnowledgeHookManager()
    return _hook_manager


def setup_knowledge_hooks(agent) -> KnowledgeHookManager:
    """快速设置钩子"""
    manager = get_hook_manager()
    manager.setup_hooks(agent)
    return manager


# ── HermesAgent 集成补丁 ─────────────────────────────────────────────────

def patch_hermes_agent():
    """
    为HermesAgent打补丁，添加知识库钩子

    这个函数会修改HermesAgent的send_message方法，
    在关键位置插入知识库钩子调用。
    """
    try:
        from core import agent as agent_module
from core.logger import get_logger
logger = get_logger('knowledge_hooks')


        # 检查是否已经打过补丁
        if hasattr(agent_module.HermesAgent, "_knowledge_hooks_patched"):
            logger.info("[KnowledgeHooks] HermesAgent已打过补丁，跳过")
            return

        # 保存原始send_message
        original_send_message = agent_module.HermesAgent.send_message

        def patched_send_message(self, text: str):
            """打补丁后的send_message"""
            # 调用原始方法前：记录查询
            hook_manager = get_hook_manager()
            if hook_manager._hooks_enabled:
                hook_manager.on_query_received(text)

            # 调用原始方法（使用生成器）
            for chunk in original_send_message(self, text):
                yield chunk

        # 保存原始_deep_search方法
        original_deep_search = getattr(agent_module.HermesAgent, "_deep_search", None)

        async def patched_deep_search(self, query: str) -> List[Dict[str, Any]]:
            """打补丁后的深度搜索"""
            results = []
            if original_deep_search:
                results = await original_deep_search(self, query)

            # 搜索完成后：存入知识库
            hook_manager = get_hook_manager()
            if hook_manager._hooks_enabled and results:
                hook_manager.on_deep_search_complete(query, results)

            return results

        # 保存原始_search_knowledge_base方法
        original_kb_search = getattr(agent_module.HermesAgent, "_search_knowledge_base", None)

        def patched_kb_search(self, query: str) -> List[Dict[str, Any]]:
            """打补丁后的知识库搜索"""
            results = []
            if original_kb_search:
                results = original_kb_search(self, query)

            # 搜索完成后：强化记忆
            hook_manager = get_hook_manager()
            if hook_manager._hooks_enabled:
                hook_manager.on_kb_search_complete(query, results)

            return results

        # 应用补丁
        agent_module.HermesAgent.send_message = patched_send_message
        agent_module.HermesAgent._deep_search = patched_deep_search
        agent_module.HermesAgent._search_knowledge_base = patched_kb_search
        agent_module.HermesAgent._knowledge_hooks_patched = True

        logger.info("[KnowledgeHooks] HermesAgent补丁应用成功")

    except Exception as e:
        logger.warning(f"[KnowledgeHooks] HermesAgent补丁失败: {e}")


# ── 测试 ────────────────────────────────────────────────────────────────

def test_hooks():
    """测试钩子"""
    logger.info("=" * 60)
    logger.info("测试知识库钩子")
    logger.info("=" * 60)

    manager = get_hook_manager()
    logger.info(f"钩子管理器状态: 已初始化")

    # 测试查询钩子
    logger.info("\n1. 测试查询钩子")
    manager.on_query_received("什么是Python")
    logger.info("   查询已记录")

    # 测试搜索完成钩子
    logger.info("\n2. 测试搜索完成钩子")
    manager.on_deep_search_complete(
        query="Python教程",
        results=[
            {"title": "Python官方教程", "url": "https://python.org", "snippet": "Python入门指南"},
            {"title": "Python教程", "url": "https://example.com", "snippet": "Python基础教程"},
        ]
    )
    logger.info("   搜索结果已摄入")

    # 测试响应生成钩子
    logger.info("\n3. 测试响应生成钩子")
    manager.on_response_generated(
        query="Python是什么",
        response="Python是一种高级编程语言..."
    )
    logger.info("   响应已处理")

    logger.info("\n" + "=" * 60)
    logger.info("钩子测试完成!")


if __name__ == "__main__":
    test_hooks()
