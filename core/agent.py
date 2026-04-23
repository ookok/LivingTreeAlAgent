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
from typing import Callable, Iterator, Optional, List, Dict, Any
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

# 搜索相关导入
import asyncio
from core.knowledge_vector_db import KnowledgeBaseVectorStore
from core.knowledge_graph import KnowledgeGraph
from core.search.tier_router import TierRouter
from core.linkmind_router import LinkMindRouter, RouteRequest, ModelCapability
from core.discourse_rag import DiscourseAwareRAG


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

        # 模型客户端 - 延迟初始化
        self._current_backend = None
        self.model = None
        self.ollama = None
        self._use_unified = False

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

        # 搜索系统
        self.knowledge_base = KnowledgeBaseVectorStore()
        self.knowledge_graph = KnowledgeGraph()
        self.tier_router = TierRouter()
        self.model_router = LinkMindRouter()
        self.rag = DiscourseAwareRAG()

        # 迭代控制
        self._iteration = 0
        self._max_iterations = config.agent.max_iterations
        self._interrupt_event = threading.Event()
        
        # 延迟初始化模型客户端
        def init_model():
            try:
                self._init_model_client(backend)
            except Exception as e:
                print(f"[HermesAgent] 后台初始化模型客户端时出错: {e}")
        
        threading.Thread(target=init_model, daemon=True).start()

    def _init_model_client(self, backend: str):
        """初始化模型客户端，优先使用 vLLM"""
        
        try:
            # 首先检查所有后端的可用性
            available_backends = check_local_model_backends()
            
            # 获取模型路径
            model_path = self._get_default_gguf_model()
            
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
            
            # 如果找到模型路径，尝试使用本地后端
            if model_path:
                # 首先尝试使用统一模型客户端，这是最可靠的本地模型加载方式
                print("[HermesAgent] 尝试使用统一模型客户端加载本地模型")
                try:
                    from core.unified_model_client import create_local_client
                    self.model = create_local_client(model_path)
                    self._use_unified = True
                    self._current_backend = ModelBackend.LLAMA_CPP
                    print("[HermesAgent] 已回退到统一模型客户端")
                except Exception as e:
                    print(f"[HermesAgent] 初始化统一模型客户端时出错: {e}")
                    # 尝试使用 llama-cpp 后端
                    print("[HermesAgent] 尝试使用 llama-cpp 后端加载本地模型")
                    result = self._priority_loader.load_model(
                        model_path=model_path,
                        backend_preference=ModelBackend.LLAMA_CPP,
                        n_ctx=self.config.ollama.num_ctx,
                        n_gpu_layers=-1,
                        n_threads=4,
                    )
                    
                    if result.success:
                        self._use_unified = False
                        self.model = result.client
                        self._current_backend = result.backend
                        print(f"[HermesAgent] 模型加载成功，使用后端: {result.backend.value}")
                    else:
                        # 如果 llama-cpp 失败，尝试 Ollama
                        print(f"[HermesAgent] llama-cpp 加载失败: {result.message}，尝试 Ollama...")
                        try:
                            self.ollama = OllamaClient(self.config.ollama)
                            self._use_unified = False
                            self.model = self.ollama
                            self._current_backend = ModelBackend.OLLAMA
                            print("[HermesAgent] 已回退到 Ollama 后端")
                        except Exception as e2:
                            print(f"[HermesAgent] 初始化 Ollama 后端时出错: {e2}")
                            raise RuntimeError("无法初始化任何模型后端")
            else:
                # 未找到本地模型，直接使用 Ollama
                print("[HermesAgent] 未找到本地 GGUF 模型，使用 Ollama 后端")
                try:
                    self.ollama = OllamaClient(self.config.ollama)
                    self._use_unified = False
                    self.model = self.ollama
                    self._current_backend = ModelBackend.OLLAMA
                except Exception as e:
                    print(f"[HermesAgent] 初始化 Ollama 后端时出错: {e}")
                    raise RuntimeError("无法初始化 Ollama 后端，请确保 Ollama 服务正在运行")
        except Exception as e:
            print(f"[HermesAgent] 初始化模型客户端时出错: {e}")
            # 回退到 Ollama
            try:
                self.ollama = OllamaClient(self.config.ollama)
                self._use_unified = False
                self.model = self.ollama
                self._current_backend = ModelBackend.OLLAMA
                print("[HermesAgent] 已回退到 Ollama 后端")
            except Exception as e2:
                print(f"[HermesAgent] 初始化 Ollama 后端时出错: {e2}")
                raise RuntimeError("无法初始化任何模型后端，请确保 Ollama 服务正在运行")

    def _get_default_gguf_model(self) -> Optional[str]:
        """获取默认 GGUF 模型路径"""
        from core.model_manager import ModelManager
        model_manager = ModelManager(self.config)
        
        # 获取所有可用的本地模型
        local_models = model_manager.get_available_local_models()
        if local_models:
            # 过滤掉 mmproj 文件，只选择真正的模型文件
            valid_models = [m for m in local_models if "mmproj" not in m.name.lower()]
            if valid_models:
                # 优先使用第一个可用的本地模型
                model_path = valid_models[0].path
                print(f"[HermesAgent] 找到默认本地模型: {model_path}")
                return model_path
            else:
                print("[HermesAgent] 未找到有效的本地模型，跳过")
        
        # 传统方式查找模型
        models_dir = Path(self.config.model_path.models_dir or "models")

        # 支持的 GGUF 文件
        gguf_exts = [".gguf", ".gguf.bin"]

        # 扫描 models 目录
        if models_dir.exists():
            for f in models_dir.rglob("*"):
                # 过滤掉 mmproj 文件
                if f.suffix.lower() in gguf_exts and "mmproj" not in f.name.lower():
                    print(f"[HermesAgent] 找到默认模型: {f}")
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
                if self.config.ollama.default_model:
                    return self.config.ollama.default_model
                else:
                    # 如果没有设置默认模型，返回一个常用的模型名称
                    return "qwen2.5:0.5b"
        # 默认返回一个轻量级模型
        return "qwen2.5:0.5b"

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
        # 确保模型客户端已初始化
        if not self.ollama and not self.model:
            # 等待模型客户端初始化
            import time
            start_time = time.time()
            while not self.ollama and not self.model:
                if time.time() - start_time > 10:  # 10秒超时
                    yield StreamChunk(error="模型客户端初始化超时，请检查 Ollama 服务是否正在运行")
                    return
                time.sleep(0.5)
        
        # 尝试使用 Ollama 后端
        if self.ollama:
            try:
                model_name = self._get_current_model_name()
                # 检查模型是否存在
                models = self.ollama.list_models()
                if not models:
                    yield StreamChunk(error="Ollama 中没有可用模型。请先下载模型，例如：\nollama pull llama2\nollama pull gemma:2b\nollama pull qwen2.5:0.5b")
                    return
                # 检查指定的模型是否存在
                model_exists = any(m.name == model_name for m in models)
                if not model_exists:
                    # 使用第一个可用模型
                    model_name = models[0].name
                    print(f"[HermesAgent] 使用可用模型: {model_name}")
                # 调用 Ollama
                yield from self.ollama.chat(
                    messages=messages,
                    model=model_name,
                    **kwargs
                )
                return
            except Exception as e:
                print(f"[HermesAgent] Ollama 调用出错: {e}")
        
        # 尝试使用本地模型
        if self.model:
            try:
                # 构建提示
                prompt = "\n".join([f"{m.role}: {m.content}" for m in messages])
                prompt += "\nassistant:"
                
                # 尝试使用 chat 方法
                if hasattr(self.model, 'chat'):
                    model_name = self._get_current_model_name()
                    yield from self.model.chat(
                        messages=messages,
                        model=model_name,
                        **kwargs
                    )
                    return
                # 尝试使用 chat_stream 方法
                elif hasattr(self.model, 'chat_stream'):
                    from core.unified_model_client import Message as UnifiedMessage, GenerationConfig

                    # 转换为统一格式
                    unified_messages = []
                    for m in messages:
                        unified_messages.append(UnifiedMessage(role=m.role, content=m.content))

                    config = GenerationConfig(
                        temperature=self.config.agent.temperature,
                        top_p=0.9,
                        top_k=40,
                        max_tokens=self.config.agent.max_tokens,
                    )

                    # 流式输出
                    full_text = ""
                    for token in self.model.chat_stream(unified_messages, config):
                        full_text += token
                        yield StreamChunk(delta=token)

                    yield StreamChunk(done=True, total_duration=0, eval_count=len(full_text))
                    return
                # 尝试使用 generate_stream 方法（Nano-vLLM）
                elif hasattr(self.model, 'generate_stream'):
                    from core.nano_vllm import SamplingParams
                    
                    # 创建采样参数
                    sampling_params = SamplingParams(
                        temperature=self.config.agent.temperature,
                        top_p=0.9,
                        max_tokens=self.config.agent.max_tokens
                    )
                    
                    # 流式输出
                    full_text = ""
                    try:
                        print(f"[HermesAgent] 调用 Nano-vLLM generate_stream，提示词: {prompt[:100]}...")
                        for i, token in enumerate(self.model.generate_stream(prompt, sampling_params)):
                            print(f"[HermesAgent] 收到 token {i}: {token}")
                            full_text += token
                            yield StreamChunk(delta=token)
                        
                        print(f"[HermesAgent] 生成完成，总长度: {len(full_text)}")
                        yield StreamChunk(done=True, total_duration=0, eval_count=len(full_text))
                        return
                    except Exception as e:
                        print(f"[HermesAgent] Nano-vLLM generate_stream 出错: {e}")
                        import traceback
                        traceback.print_exc()
                        # 尝试使用非流式方法
                        if hasattr(self.model, 'generate'):
                            print(f"[HermesAgent] 尝试使用 generate 方法")
                            result = self.model.generate(prompt, sampling_params)
                            if result:
                                if hasattr(result, '__iter__') and not isinstance(result, str):
                                    for item in result:
                                        if hasattr(item, 'text'):
                                            yield StreamChunk(delta=item.text)
                                            yield StreamChunk(done=True)
                                            return
                                elif isinstance(result, str):
                                    yield StreamChunk(delta=result)
                                    yield StreamChunk(done=True)
                                    return
                # 尝试使用 generate 方法
                elif hasattr(self.model, 'generate'):
                    # 生成文本
                    result = self.model.generate(prompt)
                    if result:
                        # 处理不同的返回格式
                        if hasattr(result, '__iter__') and not isinstance(result, str):
                            # 如果是列表或其他可迭代对象
                            for item in result:
                                if hasattr(item, 'text'):
                                    yield StreamChunk(delta=item.text)
                                    yield StreamChunk(done=True)
                                    return
                        elif isinstance(result, str):
                            yield StreamChunk(delta=result)
                            yield StreamChunk(done=True)
                            return
            except Exception as e:
                print(f"[HermesAgent] 模型调用出错: {e}")
        
        # 所有后端都失败，给出明确的错误信息
        yield StreamChunk(error="无法连接到任何模型后端。请确保：\n1. Ollama 服务正在运行\n2. 已下载至少一个模型\n3. 已安装必要的依赖（如 llama-cpp-python）")

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

        # 1. 知识库搜索
        print("[HermesAgent] 执行知识库搜索...")
        kb_results = self._search_knowledge_base(text)
        print(f"[HermesAgent] 知识库搜索完成，找到 {len(kb_results)} 条结果")

        # 2. 深度搜索
        print("[HermesAgent] 执行深度搜索...")
        try:
            deep_results = asyncio.run(self._deep_search(text))
            print(f"[HermesAgent] 深度搜索完成，找到 {len(deep_results)} 条结果")
        except Exception as e:
            print(f"[HermesAgent] 深度搜索失败: {e}")
            deep_results = []

        # 3. 模型路由
        print("[HermesAgent] 执行模型路由...")
        model_name = self._route_model(text)
        print(f"[HermesAgent] 选择模型: {model_name}")

        # 4. 构建增强的提示
        enhanced_prompt = self._build_enhanced_prompt(text, kb_results, deep_results)

        # 对话循环
        assistant_text = ""
        tool_call_results: list[dict] = []

        while self._iteration < self._max_iterations:
            if self._interrupt_event.is_set():
                break

            # 获取 LLM 消息历史
            messages = self._build_messages(enhanced_prompt)
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

    def _build_messages(self, enhanced_prompt: Optional[str] = None) -> list[ChatMessage]:
        """构建 LLM 消息历史"""
        # 系统提示
        if enhanced_prompt:
            system_prompt = enhanced_prompt
        else:
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
            "你是生命之树AI（LivingTreeAl），一款由 AI 驱动的桌面助手，运行在本地 Windows 环境中。"
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

    def _search_knowledge_base(self, query: str) -> List[Dict[str, Any]]:
        """搜索知识库"""
        try:
            # 向量数据库搜索
            kb_results = self.knowledge_base.search_knowledge(query, top_k=3)
            
            # 知识图谱搜索
            graph_results = []
            entities = self.knowledge_graph.get_entities_by_name(query)
            for entity in entities[:2]:
                related = self.knowledge_graph.get_relations(entity.entity_id, direction="both")
                for related_entity, relation in related[:2]:
                    graph_results.append({
                        "content": f"{entity.name} {relation.relation_type.value} {related_entity.name}",
                        "score": 0.8,
                        "type": "knowledge_graph"
                    })
            
            return kb_results + graph_results
        except Exception as e:
            print(f"[HermesAgent] 知识库搜索出错: {e}")
            return []

    async def _deep_search(self, query: str) -> List[Dict[str, Any]]:
        """深度搜索"""
        try:
            results = await self.tier_router.search(query, num_results=5)
            search_results = []
            for result in results:
                search_results.append({
                    "content": result.title + " " + result.content[:100],
                    "score": result.score,
                    "type": "deep_search",
                    "url": result.url,
                    "source": result.source
                })
            return search_results
        except Exception as e:
            print(f"[HermesAgent] 深度搜索出错: {e}")
            return []

    def _route_model(self, query: str) -> str:
        """模型路由"""
        try:
            request = RouteRequest(
                task_type="chat",
                required_capabilities=[ModelCapability.CHAT],
                preferred_models=[self._get_current_model_name()]
            )
            result = self.model_router.route(request)
            if result.success and result.model:
                return result.model.name
            return self._get_current_model_name()
        except Exception as e:
            print(f"[HermesAgent] 模型路由出错: {e}")
            return self._get_current_model_name()

    def _build_enhanced_prompt(self, query: str, kb_results: List[Dict], deep_results: List[Dict]) -> str:
        """构建增强的提示"""
        prompt_parts = []
        
        # 系统提示
        prompt_parts.append("你是生命之树AI（LivingTreeAl），一款由 AI 驱动的桌面助手，运行在本地 Windows 环境中。")
        
        # 知识库结果
        if kb_results:
            prompt_parts.append("\n## 知识库信息")
            for i, result in enumerate(kb_results[:3], 1):
                content = result.get("content", "").strip()
                if content:
                    prompt_parts.append(f"{i}. {content}")
        
        # 深度搜索结果
        if deep_results:
            prompt_parts.append("\n## 搜索结果")
            for i, result in enumerate(deep_results[:3], 1):
                content = result.get("content", "").strip()
                if content:
                    prompt_parts.append(f"{i}. {content}")
        
        # 用户查询
        prompt_parts.append(f"\n## 用户问题\n{query}")
        prompt_parts.append("\n请基于以上信息，提供详细、准确的回答。")
        
        return "\n".join(prompt_parts)
