"""
推理模型客户端
支持获取思考过程的模型（DeepSeek-R1、Qwen2.5-Reasoning 等）

功能：
1. 思考过程提取与展示
2. 输入参数记录
3. 超时重连机制
4. 连接时间自动优化
"""

import json
import time
import threading
import re
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List, Iterator, Generator
from dataclasses import dataclass, field
from dataclasses import dataclass, field
from enum import Enum

import requests

from business.config import OllamaConfig
from business.ollama_client import ChatMessage, StreamChunk


class ReasoningModelType(Enum):
    """推理模型类型"""
    DEEPSEEK_R1 = "deepseek-r1"
    QWEN_REASONING = "qwen2.5-reasoning"
    LLAMA_REASONING = "llama3.2-reasoning"
    GENERIC = "generic"  # 通用推理模型


@dataclass
class ReasoningConfig:
    """推理模型配置"""
    model_name: str = "deepseek-r1:7b"
    base_url: str = "http://localhost:11434"
    timeout: float = 120.0
    connect_timeout: float = 10.0
    max_retries: int = 3
    retry_delay: float = 2.0
    reasoning_enabled: bool = True
    max_reasoning_tokens: int = 2048
    temperature: float = 0.6
    num_ctx: int = 32768

    # 连接时间追踪
    track_connection_times: bool = True
    optimal_timeout: Optional[float] = None


@dataclass
class GenerationResult:
    """生成结果"""
    final_answer: str
    reasoning: str = ""
    raw_output: str = ""
    input_params: Dict[str, Any] = field(default_factory=dict)
    model_type: ReasoningModelType = ReasoningModelType.GENERIC
    duration: float = 0.0
    tokens_used: int = 0
    success: bool = True
    error: str = ""


@dataclass
class ConnectionTimeRecord:
    """连接时间记录"""
    timestamp: float
    connect_time: float  # 连接耗时（秒）
    first_token_time: float  # 首个 token 耗时（秒）
    total_time: float  # 总耗时（秒）
    success: bool
    error: str = ""


class ReasoningModelClient:
    """
    推理模型客户端

    支持：
    1. DeepSeek-R1 系列（原生推理字段）
    2. Qwen2.5-Reasoning（think 标签）
    3. 带 CoT 提示的通用模型
    """

    # 支持推理的模型前缀
    REASONING_MODEL_PATTERNS = {
        ReasoningModelType.DEEPSEEK_R1: ["deepseek-r1", "deepseek-coder-r1"],
        ReasoningModelType.QWEN_REASONING: ["qwen2.5-reasoning", "qwq"],
        ReasoningModelType.LLAMA_REASONING: ["llama3.2-reasoning"],
    }

    def __init__(
        self,
        config: ReasoningConfig = None,
        ollama_config: OllamaConfig = None
    ):
        """
        初始化推理模型客户端

        Args:
            config: 推理配置
            ollama_config: Ollama 配置（用于兼容性）
        """
        self.config = config or ReasoningConfig()
        self.ollama_config = ollama_config

        # HTTP Session
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

        # 连接时间记录
        self._connection_times: List[ConnectionTimeRecord] = []
        self._connection_lock = threading.Lock()

        # 重连状态
        self._is_connected = False
        self._connection_lock = threading.Lock()

        # 检测模型类型
        self._model_type = self._detect_model_type()

    def _detect_model_type(self) -> ReasoningModelType:
        """检测模型类型"""
        model_name_lower = self.config.model_name.lower()

        for model_type, patterns in self.REASONING_MODEL_PATTERNS.items():
            for pattern in patterns:
                if pattern in model_name_lower:
                    return model_type

        return ReasoningModelType.GENERIC

    # ── 连接管理 ──────────────────────────────────────────────────────

    def connect(self) -> bool:
        """
        建立连接并测试

        Returns:
            是否连接成功
        """
        start_time = time.time()

        try:
            response = self._session.get(
                f"{self.config.base_url}/api/tags",
                timeout=self.config.connect_timeout
            )

            connect_time = time.time() - start_time

            if response.status_code == 200:
                with self._connection_lock:
                    self._is_connected = True
                    self._record_connection_time(connect_time, 0, connect_time, True)
                return True

        except requests.exceptions.Timeout:
            self._record_connection_time(
                self.config.connect_timeout, 0, self.config.connect_timeout,
                False, "连接超时"
            )
        except Exception as e:
            self._record_connection_time(
                time.time() - start_time, 0, time.time() - start_time,
                False, str(e)
            )

        with self._connection_lock:
            self._is_connected = False

        return False

    def reconnect(self) -> bool:
        """
        重新连接（带重试）

        Returns:
            是否重连成功
        """
        for attempt in range(self.config.max_retries):
            if self.connect():
                return True

            if attempt < self.config.max_retries - 1:
                time.sleep(self.config.retry_delay * (attempt + 1))

        return False

    def disconnect(self):
        """断开连接"""
        with self._connection_lock:
            self._is_connected = False

    def is_connected(self) -> bool:
        """检查连接状态"""
        with self._connection_lock:
            return self._is_connected

    # ── 生成（同步）───────────────────────────────────────────────────

    def generate(
        self,
        prompt: str,
        system_prompt: str = None,
        reasoning_callback: Callable[[str], None] = None,
        stream_callback: Callable[[str], None] = None
    ) -> GenerationResult:
        """
        同步生成（带思考过程）

        Args:
            prompt: 提示词
            system_prompt: 系统提示
            reasoning_callback: 思考过程回调
            stream_callback: 流式输出回调

        Returns:
            GenerationResult，包含 final_answer 和 reasoning
        """
        start_time = time.time()

        # 构建消息
        messages = []
        if system_prompt:
            messages.append(ChatMessage(role="system", content=system_prompt))
        messages.append(ChatMessage(role="user", content=prompt))

        # 检测模型类型并选择生成方式
        if self._model_type == ReasoningModelType.DEEPSEEK_R1:
            return self._generate_deepseek(messages, start_time, reasoning_callback, stream_callback)
        elif self._model_type == ReasoningModelType.QWEN_REASONING:
            return self._generate_qwen_reasoning(messages, start_time, reasoning_callback, stream_callback)
        else:
            return self._generate_generic(messages, start_time, reasoning_callback, stream_callback)

    def _generate_deepseek(
        self,
        messages: List[ChatMessage],
        start_time: float,
        reasoning_cb: Callable,
        stream_cb: Callable
    ) -> GenerationResult:
        """DeepSeek-R1 专用生成"""
        reasoning_content = ""
        final_content = ""

        try:
            payload = {
                "model": self.config.model_name,
                "messages": [{"role": m.role, "content": m.content} for m in messages],
                "stream": True,
                "options": {
                    "temperature": self.config.temperature,
                    "num_ctx": self.config.num_ctx,
                }
            }

            # DeepSeek 特有参数
            if "deepseek-r1" in self.config.model_name.lower():
                payload["think"] = True  # 启用思考过程

            first_token_time = None
            response = self._session.post(
                f"{self.config.base_url}/api/chat",
                json=payload,
                stream=True,
                timeout=self.config.timeout
            )

            for line in response.iter_lines():
                if not line:
                    continue

                try:
                    data = json.loads(line)
                    delta = data.get("message", {}).get("content", "")

                    if first_token_time is None:
                        first_token_time = time.time() - start_time

                    # 检测思考内容（DeepSeek 使用 think 标签）
                    if "<think>" in delta:
                        # 提取思考部分
                        think_match = re.search(r"<think>([\s\S]*?)</think>", delta)
                        if think_match:
                            think_content = think_match.group(1)
                            reasoning_content += think_content
                            if reasoning_cb:
                                reasoning_cb(think_content)
                        # 提取回答部分
                        answer_match = re.search(r"</think>([\s\S]*)", delta)
                        if answer_match:
                            final_content += answer_match.group(1)
                            if stream_cb:
                                stream_cb(answer_match.group(1))
                    else:
                        final_content += delta
                        if stream_cb:
                            stream_cb(delta)

                except json.JSONDecodeError:
                    continue

            total_time = time.time() - start_time

            # 记录连接时间
            self._record_connection_time(
                first_token_time or total_time,
                first_token_time or total_time,
                total_time,
                True
            )

            return GenerationResult(
                final_answer=final_content.strip(),
                reasoning=reasoning_content.strip(),
                raw_output=f"<think>{reasoning_content}</think>\n\n{final_content}",
                model_type=ReasoningModelType.DEEPSEEK_R1,
                duration=total_time,
                input_params=self._get_input_params(messages)
            )

        except Exception as e:
            return GenerationResult(
                final_answer="",
                success=False,
                error=str(e),
                duration=time.time() - start_time
            )

    def _generate_qwen_reasoning(
        self,
        messages: List[ChatMessage],
        start_time: float,
        reasoning_cb: Callable,
        stream_cb: Callable
    ) -> GenerationResult:
        """Qwen 推理模型生成"""
        reasoning_content = ""
        final_content = ""
        in_thinking = False

        try:
            payload = {
                "model": self.config.model_name,
                "messages": [{"role": m.role, "content": m.content} for m in messages],
                "stream": True,
                "options": {
                    "temperature": self.config.temperature,
                    "num_ctx": self.config.num_ctx,
                }
            }

            first_token_time = None
            response = self._session.post(
                f"{self.config.base_url}/v1/chat/completions",
                json=payload,
                stream=True,
                timeout=self.config.timeout
            )

            for line in response.iter_lines():
                if not line:
                    continue

                try:
                    data = json.loads(line)
                    choices = data.get("choices", [])
                    if not choices:
                        continue

                    delta = choices[0].get("delta", {}).get("content", "")

                    if first_token_time is None:
                        first_token_time = time.time() - start_time

                    # Qwen 使用特定标记表示思考
                    if "<|think|>" in delta or "<think>" in delta:
                        in_thinking = True
                        think_text = re.sub(r"<\|think\|>|<\/think>|<think>|<\/think>", "", delta)
                        reasoning_content += think_text
                        if reasoning_cb:
                            reasoning_cb(think_text)
                    elif "</think>" in delta or "</think>" in delta:
                        in_thinking = False
                        think_text = re.sub(r"<\|think\|>|<\/think>|<think>|<\/think>", "", delta)
                        if think_text:
                            reasoning_content += think_text
                            if reasoning_cb:
                                reasoning_cb(think_text)
                    elif in_thinking:
                        reasoning_content += delta
                        if reasoning_cb:
                            reasoning_cb(delta)
                    else:
                        final_content += delta
                        if stream_cb:
                            stream_cb(delta)

                except json.JSONDecodeError:
                    continue

            total_time = time.time() - start_time
            self._record_connection_time(
                first_token_time or total_time,
                first_token_time or total_time,
                total_time,
                True
            )

            return GenerationResult(
                final_answer=final_content.strip(),
                reasoning=reasoning_content.strip(),
                raw_output=f"{reasoning_content}\n\n{final_content}",
                model_type=ReasoningModelType.QWEN_REASONING,
                duration=total_time,
                input_params=self._get_input_params(messages)
            )

        except Exception as e:
            return GenerationResult(
                final_answer="",
                success=False,
                error=str(e),
                duration=time.time() - start_time
            )

    def _generate_generic(
        self,
        messages: List[ChatMessage],
        start_time: float,
        reasoning_cb: Callable,
        stream_cb: Callable
    ) -> GenerationResult:
        """通用模型生成（带 CoT 提示）"""
        # 为通用模型添加思考引导
        cot_messages = list(messages)

        # 在用户消息后添加思考引导
        for i, msg in enumerate(cot_messages):
            if msg.role == "user":
                cot_messages[i] = ChatMessage(
                    role="user",
                    content=f"{msg.content}\n\n请先逐步思考，展示你的推理过程，然后再给出最终答案。"
                )
                break

        reasoning_content = ""
        final_content = ""

        try:
            payload = {
                "model": self.config.model_name,
                "messages": [{"role": m.role, "content": m.content} for m in cot_messages],
                "stream": True,
                "options": {
                    "temperature": self.config.temperature,
                    "num_ctx": self.config.num_ctx,
                }
            }

            first_token_time = None
            response = self._session.post(
                f"{self.config.base_url}/v1/chat/completions",
                json=payload,
                stream=True,
                timeout=self.config.timeout
            )

            # 解析思考标记
            reasoning_markers = ["思考：", "推理：", "步骤：", "分析：", "reasoning:", "thinking:"]
            answer_markers = ["最终答案：", "答案是：", "所以", "因此", "final answer:", "答案:"]

            in_reasoning = False
            buffer = ""

            for line in response.iter_lines():
                if not line:
                    continue

                try:
                    data = json.loads(line)
                    choices = data.get("choices", [])
                    if not choices:
                        continue

                    delta = choices[0].get("delta", {}).get("content", "")

                    if first_token_time is None:
                        first_token_time = time.time() - start_time

                    buffer += delta

                    # 检测进入思考模式
                    for marker in reasoning_markers:
                        if marker in buffer.lower():
                            in_reasoning = True
                            parts = buffer.split(marker, 1)
                            if len(parts) == 2:
                                reasoning_content += parts[1] if parts[1] else ""
                                buffer = ""
                            else:
                                reasoning_content += parts[0]
                                buffer = ""
                            if reasoning_cb:
                                reasoning_cb(delta)
                            break

                    # 检测进入回答模式
                    if in_reasoning:
                        for marker in answer_markers:
                            if marker in buffer:
                                in_reasoning = False
                                parts = buffer.split(marker, 1)
                                reasoning_content += parts[0] if parts[0] else ""
                                final_content = parts[1] if len(parts) > 1 else ""
                                buffer = ""
                                if stream_cb and parts[1]:
                                    stream_cb(parts[1])
                                break

                        if in_reasoning and reasoning_cb:
                            reasoning_cb(delta)
                    else:
                        final_content += delta
                        if stream_cb:
                            stream_cb(delta)

                except json.JSONDecodeError:
                    continue

            # 处理剩余 buffer
            if in_reasoning:
                reasoning_content += buffer
            else:
                final_content += buffer

            total_time = time.time() - start_time
            self._record_connection_time(
                first_token_time or total_time,
                first_token_time or total_time,
                total_time,
                True
            )

            return GenerationResult(
                final_answer=final_content.strip(),
                reasoning=reasoning_content.strip(),
                raw_output=f"{reasoning_content}\n\n{final_content}",
                model_type=ReasoningModelType.GENERIC,
                duration=total_time,
                input_params=self._get_input_params(messages)
            )

        except Exception as e:
            return GenerationResult(
                final_answer="",
                success=False,
                error=str(e),
                duration=time.time() - start_time
            )

    def _get_input_params(self, messages: List[ChatMessage]) -> Dict[str, Any]:
        """获取输入参数"""
        return {
            "model": self.config.model_name,
            "model_type": self._model_type.value,
            "base_url": self.config.base_url,
            "messages": [{"role": m.role, "content": m.content[:200]} for m in messages],
            "temperature": self.config.temperature,
            "num_ctx": self.config.num_ctx,
            "timeout": self.config.timeout,
            "connect_timeout": self.config.connect_timeout,
        }

    # ── 连接时间优化 ──────────────────────────────────────────────────

    def _record_connection_time(
        self,
        connect_time: float,
        first_token_time: float,
        total_time: float,
        success: bool,
        error: str = ""
    ):
        """记录连接时间"""
        if not self.config.track_connection_times:
            return

        with self._connection_lock:
            record = ConnectionTimeRecord(
                timestamp=time.time(),
                connect_time=connect_time,
                first_token_time=first_token_time,
                total_time=total_time,
                success=success,
                error=error
            )
            self._connection_times.append(record)

            # 保持最近 100 条记录
            if len(self._connection_times) > 100:
                self._connection_times = self._connection_times[-100:]

            # 更新最优超时
            self._update_optimal_timeout()

    def _update_optimal_timeout(self):
        """根据历史记录更新最优超时时间"""
        successful_times = [
            r.first_token_time for r in self._connection_times[-20:]
            if r.success and r.first_token_time > 0
        ]

        if successful_times:
            # 使用 P95 作为最优超时
            sorted_times = sorted(successful_times)
            p95_index = int(len(sorted_times) * 0.95)
            self.config.optimal_timeout = sorted_times[p95_index] * 1.5  # 留 50% 余量

    def get_connection_stats(self) -> Dict[str, Any]:
        """获取连接统计"""
        with self._connection_lock:
            if not self._connection_times:
                return {"total_requests": 0, "avg_time": 0, "success_rate": 0}

            recent = self._connection_times[-20:]
            successful = [r for r in recent if r.success]

            return {
                "total_requests": len(self._connection_times),
                "recent_requests": len(recent),
                "success_rate": len(successful) / len(recent) if recent else 0,
                "avg_connect_time": sum(r.connect_time for r in successful) / len(successful) if successful else 0,
                "avg_first_token_time": sum(r.first_token_time for r in successful) / len(successful) if successful else 0,
                "avg_total_time": sum(r.total_time for r in successful) / len(successful) if successful else 0,
                "optimal_timeout": self.config.optimal_timeout,
                "p95_timeout": self.config.optimal_timeout * 0.67 if self.config.optimal_timeout else None,
            }

    def get_optimal_timeout(self) -> float:
        """
        获取最优超时时间

        基于历史连接时间自动调整
        """
        if self.config.optimal_timeout:
            return self.config.optimal_timeout

        # 默认超时
        return self.config.timeout

    # ── 工具方法 ──────────────────────────────────────────────────────

    def generate_with_retry(
        self,
        prompt: str,
        system_prompt: str = None,
        max_attempts: int = None,
        reasoning_callback: Callable[[str], None] = None,
        stream_callback: Callable[[str], None] = None
    ) -> GenerationResult:
        """
        带重试的生成

        Args:
            prompt: 提示词
            system_prompt: 系统提示
            max_attempts: 最大重试次数
            reasoning_callback: 思考回调
            stream_callback: 流式回调

        Returns:
            GenerationResult
        """
        max_attempts = max_attempts or self.config.max_retries

        for attempt in range(max_attempts):
            result = self.generate(
                prompt, system_prompt, reasoning_callback, stream_callback
            )

            if result.success:
                return result

            # 重试前重连
            if attempt < max_attempts - 1:
                time.sleep(self.config.retry_delay * (attempt + 1))
                self.reconnect()

        return result

    def list_available_reasoning_models(self) -> List[str]:
        """列出可用的推理模型"""
        try:
            response = self._session.get(
                f"{self.config.base_url}/api/tags",
                timeout=5
            )

            if response.status_code == 200:
                models = response.json().get("models", [])
                reasoning_models = []

                for model in models:
                    name = model.get("name", "").lower()
                    for pattern_list in self.REASONING_MODEL_PATTERNS.values():
                        for pattern in pattern_list:
                            if pattern in name:
                                reasoning_models.append(model.get("name"))
                                break

                return reasoning_models

        except Exception:
            pass

        return []

    def close(self):
        """关闭客户端"""
        self.disconnect()
        self._session.close()


# ── 与 OllamaClient 的集成 ──────────────────────────────────────────

def create_reasoning_client(
    model_name: str = "deepseek-r1:7b",
    base_url: str = "http://localhost:11434",
    **kwargs
) -> ReasoningModelClient:
    """创建推理模型客户端的便捷函数"""
    config = ReasoningConfig(
        model_name=model_name,
        base_url=base_url,
        **kwargs
    )
    return ReasoningModelClient(config)
