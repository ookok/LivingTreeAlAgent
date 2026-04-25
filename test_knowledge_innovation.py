# -*- coding: utf-8 -*-
"""
test_knowledge_innovation.py - 知识库创新功能测试
==================================================

测试5条创新建议：
1. 语义去重引擎 (SemanticDeduplicator)
2. 知识价值评估系统 (KnowledgeValueScorer)
3. 主动学习触发器 (ActiveLearningTrigger)
4. 知识图谱增强 (KnowledgeGraphEnhancer)
5. 遗忘机制 + 强化复习 (ForgettingMechanism)

同时测试 Agent Chat 的3个查询：
1. "五一郑州有什么好玩的"
2. "今年是2026年，五一去郑州玩"
3. "我想写小说"
"""

import sys
import os
import time

# 设置控制台编码
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)


def test_innovation_modules():
    """测试5条创新建议"""
    print("=" * 70)
    print("测试 1-5: 知识库创新模块")
    print("=" * 70)

    from client.src.business.knowledge_innovation import (
        test_innovation_modules as test_modules,
    )

    # 运行内置测试
    test_modules()

    print("\n" + "=" * 70)
    print("创新模块测试完成!")
    print("=" * 70)


def test_agent_chat_query(chat, query: str, test_num: int):
    """测试单个Agent Chat查询"""
    print(f"\n{'=' * 70}")
    print(f"测试 {test_num}: Agent Chat 查询")
    print(f"Query: {query}")
    print("=" * 70)

    start_time = time.time()

    try:
        # 调用Agent Chat
        response = chat.chat(query, max_wait=60)
        elapsed = time.time() - start_time

        # 输出结果
        print(f"\n[响应时间: {elapsed:.1f}秒]")
        print(f"\n[回复内容]:")
        print("-" * 50)
        print(response[:1000] if len(response) > 1000 else response)
        if len(response) > 1000:
            print(f"... (省略 {len(response) - 1000} 字)")
        print("-" * 50)

        return response

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n[错误] {e}")
        print(f"[耗时: {elapsed:.1f}秒]")
        return None


def test_agent_chat_queries():
    """测试Agent Chat的3个查询"""
    print("\n" + "=" * 70)
    print("测试 6-8: Agent Chat 3个查询")
    print("=" * 70)

    from core.agent_chat import create_agent_chat

    # 创建独立的测试DB
    test_db = os.path.join(PROJECT_ROOT, ".tmp_knowledge_test.db")

    # 清理旧DB
    if os.path.exists(test_db):
        try:
            os.remove(test_db)
        except:
            pass

    print("\n正在初始化 Agent Chat...")

    try:
        chat = create_agent_chat(
            backend="ollama",
            session_db_path=test_db,
        )
        print("Agent Chat 初始化成功!")

        # 测试查询1
        test_agent_chat_query(chat, "五一郑州有什么好玩的", 6)

        # 测试查询2
        test_agent_chat_query(chat, "今年是2026年，五一去郑州玩", 7)

        # 测试查询3
        test_agent_chat_query(chat, "我想写小说", 8)

        print("\n" + "=" * 70)
        print("Agent Chat 测试完成!")
        print("=" * 70)

        return True

    except Exception as e:
        print(f"\n[错误] Agent Chat 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # 清理测试DB
        if os.path.exists(test_db):
            try:
                os.remove(test_db)
            except:
                pass


def test_knowledge_hooks():
    """测试知识库钩子"""
    print("\n" + "=" * 70)
    print("测试 9: 知识库钩子")
    print("=" * 70)

    from client.src.business.knowledge_hooks import test_hooks, get_hook_manager

    # 测试钩子
    test_hooks()

    # 获取钩子统计
    manager = get_hook_manager()
    print("\n钩子管理器状态:")
    print(f"  - 钩子启用: {manager._hooks_enabled}")
    print(f"  - 自动摄入搜索: {manager.config['auto_ingest_search']}")
    print(f"  - 自动GC: {manager.config['auto_gc']}")
    print(f"  - 遗忘衰减: {manager.config['decay_enabled']}")


def main():
    """主测试函数"""
    print("=" * 70)
    print("知识库创新功能综合测试")
    print("=" * 70)
    print(f"\n测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. 测试创新模块
    test_innovation_modules()

    # 2. 测试知识库钩子
    test_knowledge_hooks()

    # 3. 测试Agent Chat查询
    test_agent_chat_queries()

    print("\n" + "=" * 70)
    print("所有测试完成!")
    print("=" * 70)


if __name__ == "__main__":
    main()
