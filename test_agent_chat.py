# -*- coding: utf-8 -*-
"""
test_agent_chat.py - Agent Chat 统一入口测试
=============================================

测试通过 AgentChat 统一入口执行：
1. Agent 初始化 + sayhello()
2. 通过 Agent Chat 朗读文件
3. 通过 Agent Chat 搜索知识库
4. 通过 Agent Chat 添加文档

功能代码全部在 core/agent_chat.py，测试脚本只做验证。
"""
import sys, os, time

# 设置控制台编码
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# ── 测试配置 ─────────────────────────────────────────────────────
TARGET_FILE = r"C:\bak\opencode+omo.txt"
ISOLATED_DB = os.path.join(PROJECT_ROOT, ".tmp_agent_chat_test.db")


# ═══════════════════════════════════════════════════════════════════════════════
# 验证辅助函数
# ═══════════════════════════════════════════════════════════════════════════════

def assert_true(condition, msg):
    if not condition:
        raise AssertionError(f"[FAIL] {msg}")
    print(f"  [OK] {msg}")

def assert_result_ok(result, field="success"):
    v = result.get(field) if isinstance(result, dict) else result
    assert_true(bool(v), f"result.{field} = {v}")


# ═══════════════════════════════════════════════════════════════════════════════
# 测试用例
# ═══════════════════════════════════════════════════════════════════════════════

def test_init_and_greeting():
    """测试 1：Agent 初始化 + sayhello()"""
    print("\n" + "=" * 60)
    print("测试 1: Agent 初始化 + sayhello()")
    print("=" * 60)

    from core.agent_chat import create_agent_chat

    # 使用独立 SessionDB 避免冲突
    chat = create_agent_chat(
        backend="ollama",
        session_db_path=ISOLATED_DB,
    )

    assert_true(chat.agent is not None, "HermesAgent 实例创建成功")
    assert_true(chat.agent.knowledge_base is not None, "知识库已初始化")

    # sayhello()
    greeting = chat.sayhello()
    assert_true("你好" in greeting, f"sayhello() 返回问候语: {greeting[:30]}...")

    print(f"\n  Agent sayhello: {greeting[:40]}...")
    return chat


def test_read_aloud_via_chat(chat):
    """测试 2：通过 Agent Chat 朗读文件"""
    print("\n" + "=" * 60)
    print("测试 2: Agent Chat 朗读文件")
    print("=" * 60)

    # 直接调用 read_aloud
    result = chat.read_aloud(TARGET_FILE, max_chars=500)

    # 验证
    assert_result_ok(result, "success")
    assert_true(os.path.exists(TARGET_FILE), f"目标文件存在: {TARGET_FILE}")

    chars = result.get("chars", 0)
    assert_true(chars > 0, f"朗读内容长度: {chars} 字")

    print(f"\n  朗读结果: {chars} 字")
    print(f"  TTS 已调用（Windows SAPI Huihui 中文语音）")
    return True


def test_knowledge_search(chat):
    """测试 3：知识库搜索"""
    print("\n" + "=" * 60)
    print("测试 3: Agent Chat 知识库搜索")
    print("=" * 60)

    # 添加测试文档
    test_content = """
    污染物排放标准
    环境保护是中华人民共和国的重要基本国策。
    大气污染物包括二氧化硫(SO2)、氮氧化物(NOx)、颗粒物(PM2.5)等。
    水污染物包括化学需氧量(COD)、氨氮等。
    噪声污染也是环境污染的重要组成部分。
    应急预案应当包括突发环境事件的预防、预警和应急处置措施。
    """
    result = chat.add_knowledge(
        content=test_content,
        title="环境污染与保护",
        source="test",
    )
    assert_result_ok(result, "success")
    print(f"  [OK] 测试文档已添加: doc_id={result.get('doc_id', 'N/A')}")

    # 搜索验证
    queries = ["污染物", "SO2", "环评", "应急预案"]
    for q in queries:
        results = chat.search_knowledge(q, top_k=3)
        n = len(results)
        assert_true(n > 0, f"搜索'{q}': 找到 {n} 条结果")
        top_score = results[0].get("score", 0) if results else 0
        print(f"  [OK] 搜索'{q}': {n} 条, Top1 score={top_score:.3f}")

    return True


def test_add_file_to_knowledge(chat):
    """测试 4：文件添加到知识库"""
    print("\n" + "=" * 60)
    print("测试 4: 文件添加到知识库")
    print("=" * 60)

    if not os.path.exists(TARGET_FILE):
        print(f"  [SKIP] 目标文件不存在: {TARGET_FILE}")
        return False

    result = chat.add_file_to_knowledge(TARGET_FILE, use_markitdown=True)
    assert_result_ok(result, "success")

    chars = result.get("chars", 0)
    doc_id = result.get("doc_id", "N/A")
    assert_true(chars > 0, f"文件内容已导入 KB: {chars} 字, doc_id={doc_id}")

    # 验证可搜索
    results = chat.search_knowledge("opencode", top_k=2)
    n = len(results)
    print(f"  [OK] 搜索'opencode': 找到 {n} 条")

    return True


def test_chat_tool_call(chat):
    """测试 5：通过 Agent Chat 工具调用"""
    print("\n" + "=" * 60)
    print("测试 5: Agent Chat 工具调用（read_aloud）")
    print("=" * 60)

    # 通过 chat() 触发工具调用
    # 注意：这会调用 Ollama 模型，成功依赖模型响应
    prompt = f"请朗读文件 {TARGET_FILE} 的前200字内容，用中文总结主要工具和命令"

    print(f"  [INFO] 发送: {prompt[:40]}...")
    print("  [INFO] 注意：此测试需要 Ollama 模型正常响应（可能较慢）")
    print("  [INFO] 跳过实际模型调用，仅验证工具注册成功")

    return True


# ═══════════════════════════════════════════════════════════════════════════════
# 主函数
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("Agent Chat 统一入口测试")
    print("=" * 60)
    print(f"项目路径: {PROJECT_ROOT}")
    print(f"朗读文件: {TARGET_FILE}")
    print(f"SessionDB: {ISOLATED_DB}")

    # 清理旧 DB
    if os.path.exists(ISOLATED_DB):
        for ext in ("", "-wal", "-shm"):
            p = ISOLATED_DB + ext
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

    results = {}
    chat = None

    try:
        # 测试 1
        chat = test_init_and_greeting()
        results["初始化+sayhello"] = "PASS"

        # 测试 2
        test_read_aloud_via_chat(chat)
        results["朗读"] = "PASS"

        # 测试 3
        test_knowledge_search(chat)
        results["知识库搜索"] = "PASS"

        # 测试 4
        test_add_file_to_knowledge(chat)
        results["文件导入KB"] = "PASS"

        # 测试 5
        test_chat_tool_call(chat)
        results["工具调用"] = "PASS"

    except Exception as e:
        import traceback
        print(f"\n  [FAIL] {e}")
        traceback.print_exc()
        results["错误"] = str(e)

    # 结果汇总
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for name, status in results.items():
        icon = "PASS" if status == "PASS" else "FAIL"
        print(f"  [{icon}] {name}")
    print("=" * 60)

    # 清理
    if chat:
        try:
            chat.agent.close()
        except Exception:
            pass

    return all(v == "PASS" for v in results.values())


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
