"""
Hermes Agent 核心
参考 NousResearch/hermes-agent 的 AIAgent 架构
支持 llama-cpp-python (本地 GGUF) 和 Ollama 两种后端
优先使用 vLLM 引擎
"""

import re
import time
import json
import threading
import traceback
from pathlib import Path
from typing import Callable, Iterator, Optional
from dataclasses import dataclass

from core.ollama_client import OllamaClient, ChatMessage, StreamChunk
from core.unified_model_client import (
    UnifiedModelClient,
    UnifiedModelManager,
    create_local_client,
    LLAMA_CPP_AVAILABLE,
)
from core.session_db import SessionDB
from core.memory_manager import MemoryManager
from core.tools_registry import ToolRegistry, ToolDispatcher, SCHEMA
from core.config import AppConfig
from core.session_stats import SessionStats, get_stats_tracker
from core.model_priority_loader import (
    ModelBackend,
    LocalModelPriorityLoader,
    get_priority_loader,
    check_local_model_backends,
)


# ── 回调定义 ────────────────────────────────────────────────────────

@dataclass
class AgentCallbacks:
    """Agent 运行时回调"""
    stream_delta: Optional[Callable[[str], None]] = None     # 文本 token
    thinking: Optional[Callable[[str], None]] = None         # 推理内容
    tool_start: Optional[Callable[[str, str], None]] = None  # 工具开始
    tool_result: Optional[Callable[[str, str, bool], None]] = None  # 工具结果
    approval_needed: Optional[Callable[[str, str, str], bool]] = None  # 审批
    stats_update: Optional[Callable[['SessionStats'], None]] = None  # 统计更新回调


# ── Hermes Agent ───────────────────────────────────────────────────

class HermesAgent:
    """
    Hermes Agent 核心类

    参考 hermes-agent 的 AIAgent 设计：
    - 对话循环（run_conversation）
    - 工具执行（_execute_tool_calls）
    - 上下文压缩（_context_compress）
    - 记忆保存（_save_memory）

    支持后端（按优先级）：
    - vLLM：最高性能，支持张量并行
    - Nano-vLLM：轻量级 vLLM 实现
    - Ollama：通过 Ollama 服务调用模型
    - llama-cpp-python：直接加载 GGUF 模型，无需 Ollama
    """

    def __init__(
        self,
        config: AppConfig,
        session_id: str | None = None,
        callbacks: AgentCallbacks | None = None,
        backend: str = "vllm",  # "vllm", "nano_vllm", "ollama", "llama-cpp"
    ):
        self.config = config
        self.callbacks = callbacks or AgentCallbacks()
        self.backend = backend

        # 会话统计追踪器
        self._stats_tracker = get_stats_tracker()
        self._session_stats: Optional[SessionStats] = None

        # 模型优先级加载器
        self._priority_loader = get_priority_loader()

        # 模型客户端
        self._init_model_client(backend)

        # 其他组件
        self.session_db = SessionDB()
        self.memory = MemoryManager()

        # 会话
        self.session_id = session_id or self.session_db.create_session(
            model=self._get_current_model_name()
        )

        # 启动会话统计追踪
        self._session_stats = self._stats_tracker.start_session(self.session_id)

        # 工具系统
        self._register_tools()
        self.dispatcher = ToolDispatcher({})
        self.enabled_toolsets = config.agent.enabled_toolsets
        self._tool_schema = self._build_tool_schema()

        # 迭代控制
        self._iteration = 0
        self._max_iterations = config.agent.max_iterations
        self._interrupt_event = threading.Event()

    def _init_model_client(self, backend: str):
        """初始化模型客户端，优先使用 vLLM"""
        
        # 首先检查所有后端的可用性
        available_backends = check_local_model_backends()
        
        # 获取模型路径
        model_path = self._get_default_gguf_model()
        if not model_path:
            raise FileNotFoundError(
                "未找到默认 GGUF 模型。\n"
                "请将 GGUF 模型放入 models/ 目录，或在设置中指定模型路径。"
            )
        
        # 根据 backend 参数选择后端
        if backend == "vllm":
            preferred = ModelBackend.VLLM
        elif backend == "nano_vllm":
            preferred = ModelBackend.NANO_VLLM
        elif backend == "ollama":
            preferred = ModelBackend.OLLAMA
        elif backend == "llama-cpp":
            preferred = ModelBackend.LLAMA_CPP
        else:
            # 默认优先 vLLM
            preferred = ModelBackend.VLLM
        
        # 使用优先级加载器
        result = self._priority_loader.load_model(
            model_path=model_path,
            backend_preference=preferred,
            n_ctx=self.config.ollama.context_length,
            n_gpu_layers=-1,
            n_threads=4,
        )
        
        if result.success:
            self._use_unified = False
            self.model = result.client
            self._current_backend = result.backend
            print(f"[HermesAgent] 模型加载成功，使用后端: {result.backend.value}")
        else:
            # 如果所有后端都失败，回退到 Ollama
            print(f"[HermesAgent] 警告: {result.message}，尝试 Ollama...")
            self.ollama = OllamaClient(self.config.ollama)
            self._use_unified = False
            self.model = None
            self._current_backend = ModelBackend.OLLAMA

    def _get_default_gguf_model(self) -> Optional[str]:
        """获取默认 GGUF 模型路径"""
        models_dir = Path(self.config.models_dir or "models")

        # 支持的 GGUF 文件
        gguf_exts = [".gguf", ".gguf.bin"]

        # 扫描 models 目录
        if models_dir.exists():
            for f in models_dir.rglob("*"):
                if f.suffix.lower() in gguf_exts:
                    return str(f)

        return None

    def _get_current_model_name(self) -> str:
        """获取当前模型名称"""
        if hasattr(self, '_current_backend'):
            if self._current_backend == ModelBackend.VLLM:
                model_path = self._get_default_gguf_model()
                if model_path:
                    return Path(model_path).stem
            elif self._current_backend == ModelBackend.OLLAMA:
                return self.config.ollama.default_model
        return self.config.ollama.default_model

    # ── 工具注册 ────────────────────────────────────────────────

    def _register_tools(self):
        """注册所有内置工具"""
        from core.tools_file import register_file_tools
        from core.tools_terminal import register_terminal_tools
        from core.tools_writing import register_writing_tools
        from core.tools_ollama import register_model_tools

        register_file_tools(self)
        register_terminal_tools(self)
        register_writing_tools(self)
        register_model_tools(self)

    def _build_tool_schema(self) -> list[dict]:
        """构建 OpenAI tools schema"""
        tools = ToolRegistry.get_all_tools(self.enabled_toolsets)
        return ToolRegistry.to_openai_schema(tools)

    # ── 模型调用（统一接口）─────────────────────────────────────────

    def _llm_chat(self, messages: list[ChatMessage], **kwargs) -> Iterator[StreamChunk]:
        """
        统一的 LLM 调用接口
        根据 backend 自动选择 llama-cpp 或 ollama
        """
        if self.backend == "llama-cpp":
            # llama-cpp-python 适配
            from core.unified_model_client import Message as UnifiedMessage, GenerationConfig

            # 转换为统一格式
            unified_messages = []
            for m in messages:
                unified_messages.append(UnifiedMessage(role=m.role, content=m.content))

            config = GenerationConfig(
                temperature=self.config.ollama.temperature,
                top_p=self.config.ollama.top_p,
                top_k=40,
                max_tokens=self.config.ollama.max_tokens,
            )

            # 流式输出
            full_text = ""
            for token in self.model.chat_stream(unified_messages, config):
                full_text += token
                yield StreamChunk(delta=token)

            yield StreamChunk(done=True, total_duration=0, eval_count=len(full_text))

        else:
            # Ollama
            yield from self.ollama.chat(
                messages=messages,
                model=self.current_model,
                **kwargs
            )

    # ── 对话循环 ────────────────────────────────────────────────

    def _notify_stats(self):
        """通知统计更新"""
        if self.callbacks.stats_update and self._session_stats:
            self.callbacks.stats_update(self._session_stats)
    
    def _record_token_usage(self, usage: dict):
        """记录 Token 使用"""
        if usage and self._session_stats:
            prompt = usage.get("prompt_tokens", 0)
            completion = usage.get("completion_tokens", 0)
            self._stats_tracker.record_tokens(self.session_id, prompt, completion)
            self._notify_stats()

    def send_message(self, text: str) -> Iterator[StreamChunk]:
        """
        发送消息，启动对话循环，返回流式响应迭代器
        """
        # 追加用户消息
        self.session_db.append_message(self.session_id, "user", text)
        
        # 记录消息
        if self._session_stats:
            self._stats_tracker.record_message(self.session_id, "user")

        # 对话循环
        assistant_text = ""
        tool_call_results: list[dict] = []

        while self._iteration < self._max_iterations:
            if self._interrupt_event.is_set():
                break

            # 获取 LLM 消息历史
            messages = self._build_messages()
            reasoning_content = ""

            # 推理回调
            def reasoning_cb(delta: str):
                nonlocal reasoning_content
                reasoning_content += delta
                if self.callbacks.thinking:
                    self.callbacks.thinking(delta)

            # 流式调用 LLM
            content_buffer = ""

            # 构建 kwargs
            llm_kwargs = {}
            if self._iteration == 0 and self._tool_schema:
                # TODO: llama-cpp 暂时不支持 tools，暂不传递
                if self.backend == "ollama":
                    llm_kwargs["tools"] = self._tool_schema
            if reasoning_cb:
                llm_kwargs["reasoning_callback"] = reasoning_cb

            for chunk in self._llm_chat(messages, **llm_kwargs):
                if chunk.error:
                    yield chunk
                    return

                # 流式文本
                if chunk.delta:
                    content_buffer += chunk.delta
                    assistant_text += chunk.delta
                    if self.callbacks.stream_delta:
                        self.callbacks.stream_delta(chunk.delta)

                # 工具调用
                if chunk.tool_calls:
                    tool_results = self._execute_tools(chunk.tool_calls)
                    tool_call_results.extend(tool_results)

                    # 追加工具结果到消息历史
                    for tr in tool_results:
                        role_msg = "assistant"
                        content = tr["result"] if tr["success"] else f"错误: {tr['error']}"
                        self.session_db.append_message(
                            self.session_id, "tool", content,
                            tool_name=tr["tool_name"]
                        )

                    # 继续循环（需要再次调用 LLM）
                    self._iteration += 1
                    break

                # 完成
                if chunk.done:
                    # 保存助手消息
                    if assistant_text:
                        self.session_db.append_message(
                            self.session_id, "assistant", assistant_text,
                            reasoning=reasoning_content
                        )
                    yield StreamChunk(done=True)
                    return

            # 文本完成（非工具调用）
            else:
                if assistant_text:
                    self.session_db.append_message(
                        self.session_id, "assistant", assistant_text,
                        reasoning=reasoning_content
                    )
                yield StreamChunk(done=True)
                return

        # 超限
        yield StreamChunk(error=f"达到最大迭代次数 ({self._max_iterations})")

    def _build_messages(self) -> list[ChatMessage]:
        """构建 LLM 消息历史"""
        # 系统提示
        system_prompt = self._build_system_prompt()

        # 从数据库获取消息
        db_messages = self.session_db.get_messages_for_llm(self.session_id)

        result = [ChatMessage(role="system", content=system_prompt)]
        for m in db_messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            # 工具消息处理
            if role == "tool":
                tc = m.get("tool_calls")
                if tc:
                    result.append(ChatMessage(role="tool", content=json.dumps(tc)))
                else:
                    result.append(ChatMessage(role="tool", content=content))
            else:
                result.append(ChatMessage(role=role, content=content))

        return result

    def _build_system_prompt(self) -> str:
        """构建系统提示（参考 hermes-agent _build_system_prompt）"""
        parts = []

        # 1. 核心指令
        parts.append(
            "你是 Hermes，一款由 AI 驱动的桌面助手，运行在本地 Windows 环境中。"
            "你可以通过各种工具来帮助用户完成任务。"
        )

        # 2. 记忆上下文
        mem_ctx = self.memory.get_combined_context()
        if mem_ctx.strip():
            parts.append(f"\n## 记忆上下文\n{mem_ctx}\n")

        # 3. 可用工具说明
        tools_desc = self._describe_tools()
        if tools_desc:
            parts.append(f"\n## 可用工具\n{tools_desc}\n")

        # 4. 写作指导
        parts.append(
            "\n## 写作模式\n"
            "当用户要求创建文档时，使用 create_document 工具。\n"
            "当用户要求修改文档时，使用 edit_document 工具。\n"
            "支持 Markdown 格式，使用 .md 扩展名保存。\n"
        )

        return "\n\n".join(parts)

    def _describe_tools(self) -> str:
        """生成工具描述文本（供系统提示使用）"""
        lines = []
        for t in ToolRegistry.get_all_tools(self.enabled_toolsets):
            lines.append(f"- **{t.name}**: {t.description}")
        return "\n".join(lines)

    def _execute_tools(self, tool_calls: list[dict]) -> list[dict]:
        """执行工具调用列表"""
        results = []
        for tc in tool_calls:
            func = tc.get("function", {})
            name = func.get("name", "")
            args_str = func.get("arguments", "{}")

            # 解析参数
            try:
                args = json.loads(args_str) if isinstance(args_str, str) else args_str
            except Exception:
                args = {}

            if self.callbacks.tool_start:
                self.callbacks.tool_start(name, args_str)

            # 记录工具调用
            if self._session_stats:
                self._stats_tracker.record_tool_call(self.session_id, name, args_str)
            
            # 检测 URL 访问
            if name in ("web_fetch", "browse_url", "fetch_url", "visit_url") and isinstance(args, dict):
                url = args.get("url") or args.get("url") or args.get("link", "")
                if url:
                    if self._session_stats:
                        self._stats_tracker.record_url_visit(self.session_id, url)
            
            # 记录过程消息
            if self._session_stats:
                self._stats_tracker.record_message(self.session_id, "tool")
                self._notify_stats()

            # 执行
            result = self.dispatcher.dispatch(name, args)
            success = result.get("success", False)
            result_text = json.dumps(result, ensure_ascii=False, indent=2)

            if self.callbacks.tool_result:
                self.callbacks.tool_result(name, result_text, success)

            results.append({
                "tool_name": name,
                "success": success,
                "result": result_text,
                "error": result.get("error", ""),
            })

        return results

    # ── 控制 ────────────────────────────────────────────────────

    def interrupt(self):
        """从外部线程中断"""
        self._interrupt_event.set()

    def switch_model(self, model: str):
        """切换模型"""
        self.current_model = model
        self.config.ollama.default_model = model

    def reset_session(self):
        """重置会话"""
        self.session_db.clear_messages(self.session_id)
        self._iteration = 0

    def close(self):
        """关闭 Agent"""
        # 结束会话统计追踪
        if self._session_stats:
            self._stats_tracker.end_session(self.session_id)
        self.session_db.end_session(self.session_id)
    
    def get_session_stats(self) -> Optional[SessionStats]:
        """获取当前会话统计"""
        if self._session_stats:
            return self._session_stats
        return self._stats_tracker.get_stats(self.session_id)
    
    def get_stats_summary(self) -> str:
        """获取统计摘要"""
        stats = self.get_session_stats()
        if stats:
            return stats.get_summary()
        return "无统计信息"

    def get_session_info(self):
        return self.session_db.get_session(self.session_id)

    def search_memory(self, query: str) -> list[dict]:
        """搜索记忆"""
        return self.session_db.search_messages(query)
