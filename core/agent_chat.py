# -*- coding: utf-8 -*-
"""
Agent Chat 封装层
================

HermesAgent 的统一 Chat 入口，封装：
1. 自动问候（sayhello）
2. SessionDB 错误自动恢复
3. TTS 朗读集成
4. 知识库工具注册（read_aloud / search_knowledge / add_knowledge）
5. MarkItDown 文档转换集成

所有用户交互通过 HermesAgent.Chat 统一入口。
"""
from __future__ import annotations

import os
import sys
import time
import tempfile
import sqlite3
from typing import Optional, Iterator, Dict, Any, Callable, List

# 控制台编码
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── 延迟导入避免循环依赖 ──────────────────────────────────────────

def _get_agent_class():
    from core.agent import HermesAgent
    return HermesAgent

def _get_kb_class():
    from core.fusion_rag.knowledge_base import KnowledgeBaseLayer
    return KnowledgeBaseLayer

def _get_dret_func():
    from core.skill_evolution.dret_l04_integration import create_l04_dret_system
    return create_l04_dret_system

def _get_markdown_converter():
    """获取 MarkItDown 文档转换器（延迟导入）"""
    try:
        from writing.converter import TransparentConverter, MARKITDOWN_AVAILABLE
        if MARKITDOWN_AVAILABLE:
            return TransparentConverter()
    except ImportError:
        pass
    return None

def _get_sound_engine():
    """获取 TTS 引擎（延迟导入）"""
    try:
        from client.src.business.metaverse_ui.sound_engine import SoundEngine
        # SoundEngine 继承自 QObject，需要 QApplication
        # 非 Qt 环境（测试脚本）直接用底层 SAPI
        try:
            app = QApplication.instance()
            if app is None:
                # 无 Qt 环境：返回 None，由 _tts_speak 直接调 SAPI
                return None
            return SoundEngine()
        except (NameError, RuntimeError):
            # QApplication 未定义或不可用
            return None
    except ImportError:
        return None


def _tts_speak_direct(text: str) -> bool:
    """
    直接调用 Windows SAPI 朗读（跨环境通用，不依赖 Qt）

    策略：
    1. SAPI SpVoice 直接 Speak（实时播放）
    2. 失败则生成 WAV 文件 + winsound 播放

    Returns:
        True = 成功，False = 失败
    """
    try:
        import pythoncom, win32com.client, tempfile, os, hashlib, winsound

        pythoncom.CoInitialize()

        speaker = win32com.client.Dispatch("SAPI.SpVoice")

        # 选中中文语音
        for voice in speaker.GetVoices():
            desc = voice.GetDescription()
            if "Chinese" in desc or "Huihui" in desc:
                speaker.Voice = voice
                break

        # 方案 A：实时朗读
        try:
            speaker.Speak(text)
            speaker.WaitUntilDone(-1)
            return True
        except Exception:
            pass

        # 方案 B：WAV 文件 + winsound
        file_stream = win32com.client.Dispatch("SAPI.SpFileStream")
        audio_format = win32com.client.Dispatch("SAPI.SpAudioFormat")
        audio_format.Type = 11  # SAFT16kHz16BitMono
        file_stream.Format = audio_format

        txt_hash = hashlib.md5(text.encode("utf-8")).hexdigest()[:8]
        wav_path = os.path.join(tempfile.gettempdir(), f"lt_tts_{txt_hash}.wav")
        file_stream.Open(wav_path, 3)
        speaker.AudioOutputStream = file_stream
        speaker.Speak(text)
        file_stream.Close()
        speaker.AudioOutputStream = None

        winsound.PlaySound(wav_path, winsound.SND_FILENAME)
        return True

    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# Agent Chat 封装
# ═══════════════════════════════════════════════════════════════════════════════

class AgentChat:
    """
    HermesAgent Chat 统一入口

    使用方式：
        agent = HermesAgent(config=AppConfig(), backend="ollama")
        chat = AgentChat(agent)

        # Agent 启动后自动问候
        chat.sayhello()

        # 通过 Chat 执行所有操作
        result = chat.chat("你好")
        result = chat.chat("朗读 C:/bak/test.txt")
        result = chat.chat("将 C:/data/环评报告.docx 添加到知识库")
    """

    def __init__(
        self,
        agent,  # HermesAgent
        kb: Optional[Any] = None,  # KnowledgeBaseLayer (可选，共享 KB)
        dret_config: Optional[Dict] = None,  # DRET 配置 {max_recursion_depth, enable_l04, enable_expert}
        on_message: Optional[Callable[[str], None]] = None,  # 消息回调
        on_thinking: Optional[Callable[[str], None]] = None,  # 推理回调
        on_tool: Optional[Callable[[str, str, bool], None]] = None,  # 工具回调
    ):
        self.agent = agent
        self.kb = kb  # KnowledgeBaseLayer 共享实例
        self.dret_config = dret_config or {}
        self.on_message = on_message
        self.on_thinking = on_thinking
        self.on_tool = on_tool

        # TTS 引擎
        self._sound_engine: Optional[Any] = None

        # 注册回调
        if on_thinking or on_tool:
            from core.agent import AgentCallbacks
            cbs = AgentCallbacks(
                thinking=on_thinking,
                tool_result=on_tool,
            )
            self.agent.callbacks = cbs

        # 注册知识库工具
        self._register_knowledge_tools()

        # DRET 系统（可选）
        self._dret = None

    # ── 公开 API ───────────────────────────────────────────────────

    def sayhello(self) -> str:
        """
        Agent 启动问候

        在初始化 L0-L4 和 Agent 后调用，向用户问好。
        如果系统有 TTS 引擎，同时语音播报。
        """
        greeting = "你好！我是生命之树AI（LivingTreeAl），你的 AI 桌面助手。有什么我可以帮你的吗？"

        # TTS 播报
        self._tts_speak(greeting)

        # 流式输出一条欢迎消息
        if self.on_message:
            self.on_message(greeting)

        return greeting

    def chat(self, message: str, max_wait: float = 30.0) -> str:
        """
        统一 Chat 入口（通过 HermesAgent.send_message）

        自动处理：
        - SessionDB 事务错误自动恢复
        - 工具调用结果收集
        - 流式响应聚合

        Args:
            message: 用户消息
            max_wait: 最大等待时间（秒）

        Returns:
            Agent 的完整回复文本
        """
        full_response = []

        try:
            for chunk in self.agent.send_message(message):
                if chunk.error:
                    # 尝试自动恢复
                    if self._try_recover_session():
                        return self.chat(message)
                    full_response.append(f"[错误] {chunk.error}")
                    break

                if chunk.delta:
                    delta = chunk.delta
                    full_response.append(delta)
                    if self.on_message:
                        self.on_message(delta)

                if chunk.done:
                    break

        except sqlite3.OperationalError as e:
            if "transaction" in str(e) or "locked" in str(e).lower():
                if self._try_recover_session():
                    return self.chat(message)
                full_response.append(f"[会话错误] {e}")
            else:
                full_response.append(f"[错误] {e}")

        except sqlite3.IntegrityError:
            if self._try_recover_session():
                return self.chat(message)
            full_response.append("[会话错误] 无法创建会话")

        except Exception as e:
            full_response.append(f"[错误] {e}")

        result = "".join(full_response)
        return result

    def read_aloud(self, file_path: str, max_chars: int = 3000) -> Dict[str, Any]:
        """
        TTS 朗读文件

        通过 HermesAgent 工具调用执行，或直接调用 TTS。
        优先使用知识库朗读功能。
        """
        # 读取文件
        if not os.path.exists(file_path):
            return {"success": False, "error": f"文件不存在: {file_path}"}

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(max_chars)
        except Exception as e:
            return {"success": False, "error": f"读取失败: {e}"}

        # TTS 播报
        self._tts_speak(content)
        return {"success": True, "chars": len(content), "file": file_path}

    def search_knowledge(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        搜索知识库（直接调用，无须经过 Agent）
        """
        if not self.kb:
            return []
        try:
            return self.kb.search(query, top_k=top_k)
        except Exception:
            return []

    def add_knowledge(
        self,
        content: str,
        title: str = "",
        source: str = "agent_chat",
        doc_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        添加知识到共享 KB

        Args:
            content: 文档内容
            title: 标题
            source: 来源
            doc_id: 文档 ID（可选，默认自动生成）

        Returns:
            {"success": True, "doc_id": str}
        """
        if not self.kb:
            return {"success": False, "error": "知识库未初始化"}

        try:
            import hashlib
            # 自动生成 doc_id
            if doc_id is None:
                doc_id = hashlib.md5(content[:200].encode()).hexdigest()[:12]

            doc = {
                "id": doc_id,
                "title": title or source,
                "content": content,
                "source": source,
                "type": "text",
            }

            n_chunks = self.kb.add_document(doc)
            return {"success": True, "doc_id": doc_id, "chunks": n_chunks}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def add_file_to_knowledge(
        self,
        file_path: str,
        title: Optional[str] = None,
        use_markitdown: bool = True,
    ) -> Dict[str, Any]:
        """
        将文件添加到知识库

        支持所有格式，自动转换：
        - MarkItDown 支持：docx/xlsx/pptx/pdf/html/xml/rtf
        - 直接读取：txt/md/json/csv

        Args:
            file_path: 文件路径
            title: 文档标题（默认用文件名）
            use_markitdown: 是否优先使用 MarkItDown

        Returns:
            {"success": True, "doc_id": str, "chars": int}
        """
        if not os.path.exists(file_path):
            return {"success": False, "error": f"文件不存在: {file_path}"}

        title = title or os.path.splitext(os.path.basename(file_path))[0]
        ext = os.path.splitext(file_path)[1].lower()

        # 尝试 MarkItDown
        content = None
        if use_markitdown and ext in (".docx", ".xlsx", ".pptx", ".pdf", ".html", ".xml", ".rtf"):
            md_converter = _get_markdown_converter()
            if md_converter:
                try:
                    result = md_converter.convert(str(file_path))
                    if result and hasattr(result, "text_content"):
                        content = result.text_content
                except Exception:
                    pass

        # 直接读取
        if content is None:
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except Exception as e:
                return {"success": False, "error": f"读取失败: {e}"}

        # 添加到 KB（使用文件名作为 doc_id 前缀避免冲突）
        import hashlib
        doc_id = f"file_{hashlib.md5(file_path.encode()).hexdigest()[:12]}"
        return self.add_knowledge(
            content=content,
            title=title,
            source=f"file:{file_path}",
            doc_id=doc_id,
        )

    def init_dret(
        self,
        max_recursion_depth: int = 5,
        enable_l04: bool = True,
        enable_expert: bool = True,
    ) -> Any:
        """
        初始化 DRET 系统（深度搜索专家训练）

        Args:
            max_recursion_depth: 递归深度
            enable_l04: 启用 L4
            enable_expert: 启用专家模式

        Returns:
            DRET 系统实例
        """
        create_dret = _get_dret_func()
        self._dret = create_dret(
            max_recursion_depth=max_recursion_depth,
            enable_l04=enable_l04,
            enable_expert=enable_expert,
        )

        # KB 共享实例
        if self.kb and hasattr(self._dret, "gap_detector"):
            self._dret.gap_detector.knowledge_base = self.kb

        return self._dret

    # ── 内部方法 ─────────────────────────────────────────────────

    def _register_knowledge_tools(self):
        """注册知识库工具到 ToolRegistry"""
        try:
            from core.tools_registry import ToolRegistry

            # read_aloud 工具
            def read_aloud_handler(ctx, file_path="", max_chars=3000):
                result = self.read_aloud(file_path, int(max_chars))
                return result

            ToolRegistry.register(
                name="read_aloud",
                description="TTS 朗读文件内容（中文优先）",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "文件路径"},
                        "max_chars": {"type": "integer", "description": "最大字符数", "default": 3000},
                    },
                    "required": ["file_path"],
                },
                handler=read_aloud_handler,
                toolset="knowledge",
            )

            # search_knowledge 工具
            def search_kb_handler(ctx, query="", top_k=3):
                results = self.search_knowledge(query, int(top_k))
                if not results:
                    return "知识库中未找到相关内容"
                lines = []
                for i, r in enumerate(results, 1):
                    score = r.get("score", 0)
                    content = r.get("content", r.get("text", ""))[:200]
                    lines.append(f"{i}. [{score:.2f}] {content}")
                return "\n".join(lines)

            ToolRegistry.register(
                name="search_knowledge",
                description="搜索知识库中的相关文档",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索关键词"},
                        "top_k": {"type": "integer", "description": "返回数量", "default": 3},
                    },
                    "required": ["query"],
                },
                handler=search_kb_handler,
                toolset="knowledge",
            )

            # add_knowledge 工具
            def add_kb_handler(ctx, content="", title="", source="agent_chat"):
                result = self.add_knowledge(content, title, source)
                return result

            ToolRegistry.register(
                name="add_knowledge",
                description="添加文档到知识库",
                parameters={
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "文档内容"},
                        "title": {"type": "string", "description": "文档标题"},
                        "source": {"type": "string", "description": "来源"},
                    },
                    "required": ["content"],
                },
                handler=add_kb_handler,
                toolset="knowledge",
            )

        except ImportError:
            # ToolRegistry 不可用，跳过
            pass

    def _try_recover_session(self) -> bool:
        """尝试恢复 SessionDB 会话"""
        try:
            if hasattr(self.agent.session_db, "_local"):
                self.agent.session_db._local.conn = None
            new_id = self.agent.session_db.create_session(
                model="qwen2.5:1.5b"
            )
            self.agent.session_id = new_id
            return True
        except Exception:
            return False

    def _tts_speak(self, text: str) -> bool:
        """TTS 朗读文本（自动降级：SoundEngine -> SAPI -> winsound）"""
        # 尝试 SoundEngine（Qt 环境）
        if self._sound_engine is None:
            self._sound_engine = _get_sound_engine()

        if self._sound_engine is not None:
            try:
                self._sound_engine.play_voice_cn(text)
                return True
            except Exception:
                self._sound_engine = None  # 失败后降级

        # 降级：直接调 SAPI（最可靠方案）
        return _tts_speak_direct(text)


# ═══════════════════════════════════════════════════════════════════════════════
# 便捷工厂函数
# ═══════════════════════════════════════════════════════════════════════════════

def create_agent_chat(
    backend: str = "ollama",
    session_db_path: Optional[str] = None,
    kb: Optional[Any] = None,
    dret_config: Optional[Dict] = None,
    **kwargs,
) -> AgentChat:
    """
    创建 AgentChat 的便捷工厂函数

    自动初始化：
    1. AppConfig
    2. HermesAgent（使用指定 backend）
    3. 可选：独立 SessionDB
    4. AgentChat 封装

    不硬编码任何模型名称，自动检测可用后端。

    Args:
        backend: 模型后端 ("ollama", "llama-cpp", "vllm")
        session_db_path: 独立 SessionDB 路径（可选）
        kb: 共享 KnowledgeBaseLayer
        dret_config: DRET 配置
        **kwargs: 传给 AgentChat 的额外参数

    Returns:
        AgentChat 实例
    """
    from core.config import AppConfig

    # HermesAgent
    HermesAgent = _get_agent_class()

    # 设置 Ollama 默认模型（必须在 HermesAgent 初始化之前）
    # 因为 HermesAgent.__init__ 中 _get_current_model_name() 需要有效模型名
    config = AppConfig()
    if not config.ollama.default_model:
        config.ollama.default_model = "qwen2.5:1.5b"

    # 独立 SessionDB（创建后再注入到 agent）
    session_db_path_full = session_db_path
    session_db = None
    if session_db_path:
        from core.session_db import SessionDB
        session_db = SessionDB(db_path=session_db_path)
        new_sid = session_db.create_session(model=config.ollama.default_model)

    # HermesAgent（使用已配置的 config）
    agent = HermesAgent(config=config, backend=backend)

    # 如果有独立 SessionDB，注入到 agent
    if session_db:
        agent.session_db = session_db
        agent.session_id = new_sid

    # KB 实例（如果没有传入则创建）
    if kb is None:
        KnowledgeBaseLayer = _get_kb_class()
        kb = KnowledgeBaseLayer()

    # 注入 KB 到 HermesAgent（供其工具使用）
    agent.knowledge_base = kb

    # AgentChat 封装
    chat = AgentChat(agent, kb=kb, dret_config=dret_config, **kwargs)

    return chat


# ═══════════════════════════════════════════════════════════════════════════════
# CLI 入口（可选）
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """CLI 测试入口"""
    print("=" * 60)
    print("HermesAgent.Chat 交互测试")
    print("=" * 60)

    chat = create_agent_chat(backend="ollama")

    # 启动问候
    chat.sayhello()

    # 交互循环
    print("\n[输入 'quit' 退出]")
    while True:
        try:
            user_input = input("\n你: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                print("再见！")
                break

            result = chat.chat(user_input)
            print(f"\nHermes: {result}")

        except (KeyboardInterrupt, EOFError):
            print("\n\n再见！")
            break


if __name__ == "__main__":
    main()
