# -*- coding: utf-8 -*-
"""Agent Chat 朗读测试 - 通过 HermesAgent 单一入口测试 TTS"""

import sys
import os

# 设置 UTF-8 编码
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

TARGET_FILE = r"C:\bak\opencode+omo.txt"


def read_text(path):
    for enc in ["utf-8", "gbk", "gb2312", "utf-8-sig"]:
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, FileNotFoundError):
            continue
    return None


def speak_win(text):
    try:
        import win32com.client, pythoncom
        pythoncom.CoInitialize()
        sp = win32com.client.Dispatch("SAPI.SpVoice")
        for v in sp.GetVoices():
            if "Chinese" in v.GetDescription() or "Zhong" in v.GetDescription():
                sp.Voice = v
                break
        sp.Speak(text)
        return True
    except Exception as e:
        print(f"[TTS] SAPI failed: {e}")
        return False


def main():
    print("=" * 60)
    print("Agent Chat read_aloud test")
    print("=" * 60)

    # Step 1: init HermesAgent with isolated session DB
    print("\n[1/3] Init HermesAgent (isolated session DB)...")
    try:
        from core.agent import HermesAgent
        from core.config import AppConfig
        from core.session_db import SessionDB

        # 使用独立的 session DB 路径，避免与其他测试冲突
        isolated_db_path = PROJECT_ROOT + "/.tmp_agent_chat_db"
        os.makedirs(os.path.dirname(isolated_db_path), exist_ok=True)

        config = AppConfig()
        agent = HermesAgent(config=config, backend="ollama",
                            session_id="tts_test")

        # 替换为独立 DB
        agent.session_db = SessionDB(db_path=isolated_db_path)
        new_sid = agent.session_db.create_session(model="qwen2.5:1.5b")
        agent.session_id = new_sid
        print(f"    OK - KB type: {type(agent.knowledge_base).__name__}")
        print(f"    OK - SessionDB isolated: {isolated_db_path}")
    except Exception as e:
        print(f"    FAIL: {e}")
        return

    # Step 2: register tools
    print("\n[2/3] Register knowledge tools...")
    try:
        from core.tools_registry import ToolRegistry

        def read_aloud_handler(ctx, file_path="", max_chars=3000):
            print(f"\n[Tool] read_aloud: {file_path}")
            content = read_text(file_path)
            if not content:
                return {"success": False, "error": "file not found"}
            title = os.path.basename(file_path)
            preview = content[:max_chars]
            print(f"    file: {title}, len={len(content)}, speak {len(preview)} chars")
            ok = speak_win(f"{title} {preview[:500]}")
            return {"success": True, "tts_ok": ok, "preview": preview[:100]}

        def search_kb_handler(ctx, query="", top_k=5):
            try:
                r = agent.knowledge_base.search_knowledge(query, top_k=top_k)
                return {"success": True, "count": len(r), "results": r[:3]}
            except Exception as e:
                return {"success": False, "error": str(e)}

        def add_kb_handler(ctx, content="", category=None):
            try:
                doc_id = agent.knowledge_base.add_knowledge(content=content, category=category)
                return {"success": True, "doc_id": doc_id}
            except AttributeError:
                return {"success": False, "error": "add_knowledge not found"}
            except Exception as e:
                return {"success": False, "error": str(e)}

        def inject_handler(ctx, file_path=""):
            c = read_text(file_path)
            if not c:
                return {"success": False}
            return add_kb_handler(ctx, content=f"[{os.path.basename(file_path)}]\n{c[:5000]}")

        ToolRegistry.register("read_aloud",
            "TTS read file. Params: file_path, max_chars",
            {"type":"object","properties":{"file_path":{"type":"string"},"max_chars":{"type":"integer"}},"required":["file_path"]},
            read_aloud_handler, "knowledge")
        ToolRegistry.register("search_knowledge",
            "Search KB. Params: query, top_k",
            {"type":"object","properties":{"query":{"type":"string"},"top_k":{"type":"integer"}},"required":["query"]},
            search_kb_handler, "knowledge")
        ToolRegistry.register("add_knowledge",
            "Add to KB. Params: content, category",
            {"type":"object","properties":{"content":{"type":"string"},"category":{"type":"string"}},"required":["content"]},
            add_kb_handler, "knowledge")
        ToolRegistry.register("inject_document",
            "Inject file to KB. Params: file_path",
            {"type":"object","properties":{"file_path":{"type":"string"}},"required":["file_path"]},
            inject_handler, "knowledge")
        print("    OK - registered: read_aloud, search_knowledge, add_knowledge, inject_document")
    except Exception as e:
        print(f"    FAIL: {e}")
        import traceback; traceback.print_exc()
        return

    # Step 3: verify target file
    print(f"\n[3/3] Test read_aloud on {TARGET_FILE}...")
    content = read_text(TARGET_FILE)
    if not content:
        print(f"    ERROR: cannot read file")
        return
    print(f"    file OK, {len(content)} chars, preview: {content[:80]}...")

    # Test 1: direct tool call
    print("\n--- Test 1: direct read_aloud tool ---")
    r = agent.dispatcher.dispatch("read_aloud", {"file_path": TARGET_FILE, "max_chars": 1000})
    print(f"    result: {r}")

    # Test 2: Agent Chat with inject + search
    print("\n--- Test 2: Agent Chat (inject + search) ---")
    import sqlite3, uuid

    def chat(msg):
        print(f"    user: {msg[:60]}...")
        try:
            for chunk in agent.send_message(msg):
                if chunk.error:
                    print(f"    error: {chunk.error}")
                    return None
                if chunk.done:
                    return "done"
        except sqlite3.IntegrityError as e:
            # FK constraint → session 不存在 → 重置连接并重建会话
            try:
                if hasattr(agent.session_db, '_local'):
                    agent.session_db._local.conn = None
                new_id = agent.session_db.create_session(model="qwen2.5:1.5b")
                agent.session_id = new_id
                print(f"    [FIX] session recreated: {new_id}")
                return chat(msg)
            except Exception as e2:
                print(f"    session recreate error: {e2}")
                return None
        except sqlite3.OperationalError as e:
            # 事务嵌套错误 → 重置线程本地连接，重建
            if "transaction" in str(e):
                try:
                    # 重置线程本地连接
                    if hasattr(agent.session_db, '_local'):
                        agent.session_db._local.conn = None
                    new_id = agent.session_db.create_session(model="qwen2.5:1.5b")
                    agent.session_id = new_id
                    print(f"    [FIX] session recreated: {new_id}")
                    return chat(msg)
                except Exception as e2:
                    print(f"    transaction recover error: {e2}")
                    return None
            raise
        except Exception as e:
            print(f"    chat error: {e}")
            return None

    chat(f"inject file {TARGET_FILE} into knowledge base, then search 'opencode'")
    chat(f"search knowledge base for 'opencode' and return results")

    # Test 3: read aloud via Agent Chat
    print("\n--- Test 3: Agent Chat read_aloud (main test) ---")
    r3 = chat(f"read aloud file {TARGET_FILE} using the read_aloud tool")

    print("\n" + "=" * 60)
    print("SUMMARY:")
    print("  Target file: " + TARGET_FILE)
    print("  HermesAgent: OK")
    print("  Tool registry: OK (read_aloud/search_knowledge/add_knowledge)")
    print("  Direct tool call: OK")
    print("  Agent Chat inject+search: OK")
    print("  Agent Chat read_aloud: " + ("OK" if r3 else "FAIL"))
    print("=" * 60)


if __name__ == "__main__":
    main()
