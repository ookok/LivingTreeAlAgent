# -*- coding: utf-8 -*-
"""
动作处理器基类
================

定义所有动作处理器的统一接口和数据结构。
"""

from __future__ import annotations

import time
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from ..intent_types import Intent, IntentType

logger = logging.getLogger(__name__)


class ActionResultStatus(Enum):
    """动作执行状态"""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"       # 部分成功
    NEED_CLARIFY = "clarify"  # 需要澄清
    SKIPPED = "skipped"        # 跳过（不适用于此处理器）


@dataclass
class ActionContext:
    """
    动作执行上下文
    
    承载意图解析结果和运行环境信息，
    在 IntentActionBridge → ActionHandler 之间传递。
    """
    # 解析后的意图
    intent: Intent = field(default_factory=Intent)
    
    # 运行环境
    working_dir: str = "."
    project_root: str = ""
    
    # LLM 配置
    ollama_url: str = ""
    model_name: str = ""  # 空字符串=从系统配置读取 L3
    temperature: float = 0.3
    
    # 选项
    use_cache: bool = True
    stream: bool = False
    timeout: float = 300.0
    
    # 额外参数（由调用方传入）
    extra: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent_type": self.intent.intent_type.value,
            "action": self.intent.action,
            "target": self.intent.target,
            "tech_stack": self.intent.tech_stack,
            "constraints": [c.to_dict() for c in self.intent.constraints],
            "working_dir": self.working_dir,
        }


@dataclass
class ActionResult:
    """
    动作执行结果
    
    统一的返回结构，所有处理器都必须返回此类型。
    """
    status: ActionResultStatus = ActionResultStatus.SUCCESS
    
    # 核心输出
    output: Any = None               # 主要输出内容（文本/代码/数据）
    output_type: str = "text"        # 输出类型: text, code, file_path, data, plan
    
    # 执行信息
    steps: List[Dict[str, Any]] = field(default_factory=list)
    execution_time: float = 0.0
    tokens_used: int = 0
    
    # 错误信息
    error: Optional[str] = None
    
    # 澄清请求（当 status=NEED_CLARIFY 时使用）
    clarification_prompt: str = ""
    
    # 后续建议
    suggestions: List[str] = field(default_factory=list)
    
    # 附件（文件路径等）
    artifacts: List[str] = field(default_factory=list)
    
    def is_success(self) -> bool:
        return self.status == ActionResultStatus.SUCCESS
    
    def is_failed(self) -> bool:
        return self.status == ActionResultStatus.FAILED
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "output_type": self.output_type,
            "output_preview": str(self.output)[:200] if self.output else None,
            "steps_count": len(self.steps),
            "execution_time": self.execution_time,
            "error": self.error,
            "suggestions": self.suggestions,
            "artifacts": self.artifacts,
        }


class BaseActionHandler(ABC):
    """
    动作处理器基类
    
    所有意图→动作的映射处理器都应继承此类。
    
    使用方式：
        class MyHandler(BaseActionHandler):
            @property
            def supported_intents(self) -> List[IntentType]:
                return [IntentType.CODE_GENERATION]
            
            def handle(self, ctx: ActionContext) -> ActionResult:
                # 实现具体的执行逻辑
                ...
                return ActionResult(output=result_text)
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """处理器名称（用于日志和注册）"""
        ...
    
    @property
    @abstractmethod
    def supported_intents(self) -> List[IntentType]:
        """支持的意图类型列表"""
        ...
    
    @property
    def priority(self) -> int:
        """处理器优先级（数值越小优先级越高），默认 100"""
        return 100
    
    def can_handle(self, intent_type: IntentType) -> bool:
        """检查是否能处理该意图类型"""
        return intent_type in self.supported_intents
    
    @abstractmethod
    def handle(self, ctx: ActionContext) -> ActionResult:
        """
        执行动作
        
        Args:
            ctx: 动作执行上下文（包含意图和环境信息）
            
        Returns:
            ActionResult: 执行结果
        """
        ...
    
    def _make_result(
        self,
        output: Any = None,
        output_type: str = "text",
        suggestions: Optional[List[str]] = None,
        artifacts: Optional[List[str]] = None,
    ) -> ActionResult:
        """快速构建成功结果"""
        return ActionResult(
            status=ActionResultStatus.SUCCESS,
            output=output,
            output_type=output_type,
            suggestions=suggestions or [],
            artifacts=artifacts or [],
        )
    
    def _make_error(self, error: str) -> ActionResult:
        """快速构建失败结果"""
        return ActionResult(
            status=ActionResultStatus.FAILED,
            error=error,
        )
    
    def _make_clarify(self, prompt: str) -> ActionResult:
        """快速构建澄清请求"""
        return ActionResult(
            status=ActionResultStatus.NEED_CLARIFY,
            clarification_prompt=prompt,
        )


# ── LLM 客户端（所有 Handler 共享）───────────────────────────────────────


class LLMError(Exception):
    """LLM 调用错误基类"""

    def __init__(self, message: str, error_type: str = "unknown", recoverable: bool = True):
        super().__init__(message)
        self.error_type = error_type   # timeout / connection / auth / rate_limit / server / parse
        self.recoverable = recoverable  # 是否可重试


class LLMClient:
    """
    统一 LLM 客户端

    所有 Handler 共享同一个调用逻辑，支持：
    - 自动回退：requests → urllib（无需第三方依赖）
    - 超时重试：可配置重试次数和退避策略
    - 错误分类：区分 timeout / connection / auth / rate_limit / server
    - Token 统计：返回 token 用量
    - 流式支持：SSE 流式读取（可选）
    """

    def __init__(
        self,
        default_url: str = "",
        default_model: str = "",
        default_timeout: float = 300.0,
        max_retries: int = 2,
        retry_backoff: float = 1.0,
    ):
        # 从系统配置读取默认值（未显式传入时）
        if not default_url or not default_model:
            try:
                from client.src.business.config_provider import get_ollama_url, get_l3_model
                default_url = default_url or get_ollama_url()
                default_model = default_model or get_l3_model()
            except Exception:
                default_url = default_url or "http://www.mogoo.com.cn:8899/v1"
                default_model = default_model or "qwen3.5:4b"
        self.default_url = default_url.rstrip("/")
        self.default_model = default_model
        self.default_timeout = default_timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff

        # HTTP 后端（延迟选择）
        self._http_backend: Optional[str] = None  # "requests" | "urllib"
        self._requests = None

    def _get_backend(self) -> str:
        """探测可用的 HTTP 后端"""
        if self._http_backend is not None:
            return self._http_backend
        try:
            import requests as _r
            self._requests = _r
            self._http_backend = "requests"
            logger.debug("LLMClient: 使用 requests 后端")
        except ImportError:
            self._http_backend = "urllib"
            logger.debug("LLMClient: 使用 urllib 后端（内置）")
        return self._http_backend

    def chat(
        self,
        prompt: str,
        url: str = "",
        model: str = "",
        temperature: float = 0.3,
        timeout: float = 0,
        system_prompt: str = "",
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        调用 LLM Chat Completions API

        Args:
            prompt: 用户消息
            url: API 地址（默认使用 default_url）
            model: 模型名（默认使用 default_model）
            temperature: 温度参数
            timeout: 超时（0 = 使用 default_timeout）
            system_prompt: 系统提示词
            stream: 是否流式

        Returns:
            {"content": str, "tokens_used": int, "model": str, "duration": float}

        Raises:
            LLMError: 分类后的错误
        """
        base_url = (url or self.default_url).rstrip("/")
        model_name = model or self.default_model
        actual_timeout = timeout or self.default_timeout

        # 构建消息
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model_name,
            "messages": messages,
            "stream": stream,
            "temperature": temperature,
        }

        # 构建请求 URL（兼容 /v1 前缀）
        api_url = f"{base_url}/chat/completions"
        if "/v1/" not in base_url and not base_url.endswith("/v1"):
            # 尝试标准 OpenAI 兼容路径
            api_url = f"{base_url}/v1/chat/completions"

        # 带重试的调用
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                start = time.time()
                if stream:
                    result = self._do_stream(api_url, payload, actual_timeout)
                else:
                    result = self._do_request(api_url, payload, actual_timeout)
                result["duration"] = time.time() - start
                return result
            except LLMError as e:
                last_error = e
                if not e.recoverable or attempt >= self.max_retries:
                    raise
                wait = self.retry_backoff * (2 ** attempt)
                logger.warning(f"LLM 调用失败 ({e.error_type})，{wait:.1f}s 后重试 ({attempt + 1}/{self.max_retries})")
                time.sleep(wait)

        raise last_error  # type: ignore

    def _do_request(self, url: str, payload: dict, timeout: float) -> Dict[str, Any]:
        """同步 HTTP 请求"""
        backend = self._get_backend()

        if backend == "requests":
            return self._do_requests(url, payload, timeout)
        else:
            return self._do_urllib(url, payload, timeout)

    def _do_requests(self, url: str, payload: dict, timeout: float) -> Dict[str, Any]:
        """requests 后端"""
        import requests as req

        try:
            resp = req.post(url, json=payload, timeout=timeout)
        except req.exceptions.Timeout:
            raise LLMError(f"请求超时 ({timeout}s)", "timeout", recoverable=True)
        except req.exceptions.ConnectionError as e:
            raise LLMError(f"连接失败: {e}", "connection", recoverable=True)

        # 错误分类
        if resp.status_code == 401:
            raise LLMError(f"认证失败 (HTTP {resp.status_code})", "auth", recoverable=False)
        if resp.status_code == 429:
            raise LLMError(f"请求限流 (HTTP {resp.status_code})", "rate_limit", recoverable=True)
        if resp.status_code >= 500:
            raise LLMError(f"服务器错误 (HTTP {resp.status_code})", "server", recoverable=True)
        if resp.status_code >= 400:
            raise LLMError(f"请求错误 (HTTP {resp.status_code}): {resp.text[:200]}", "client", recoverable=False)

        try:
            data = resp.json()
        except Exception:
            raise LLMError(f"响应解析失败: {resp.text[:200]}", "parse", recoverable=False)

        content = ""
        tokens_used = 0
        model_name = payload.get("model", "")

        if "choices" in data and data["choices"]:
            choice = data["choices"][0]
            content = choice.get("message", {}).get("content", "")
            model_name = choice.get("model", model_name)

        if "usage" in data:
            tokens_used = data["usage"].get("total_tokens", 0)

        return {
            "content": content or "",
            "tokens_used": tokens_used,
            "model": model_name,
        }

    def _do_urllib(self, url: str, payload: dict, timeout: float) -> Dict[str, Any]:
        """urllib 后端（无需第三方依赖）"""
        import urllib.request
        import urllib.error
        import json as _json

        body = _json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.URLError as e:
            if isinstance(e.reason, TimeoutError) or "timed out" in str(e.reason):
                raise LLMError(f"请求超时 ({timeout}s)", "timeout", recoverable=True)
            raise LLMError(f"连接失败: {e.reason}", "connection", recoverable=True)
        except Exception as e:
            if "timed out" in str(e):
                raise LLMError(f"请求超时 ({timeout}s)", "timeout", recoverable=True)
            raise LLMError(f"请求失败: {e}", "connection", recoverable=True)

        try:
            data = _json.loads(raw)
        except Exception:
            raise LLMError(f"响应解析失败: {raw[:200]}", "parse", recoverable=False)

        # HTTP 状态检查（urllib 对 4xx/5xx 不抛异常）
        # OpenAI 兼容 API 在错误时仍返回 JSON，检查 error 字段
        if "error" in data and isinstance(data["error"], dict):
            err = data["error"]
            code = err.get("code", "")
            msg = err.get("message", str(err))
            if "auth" in code.lower() or "unauthorized" in msg.lower():
                raise LLMError(f"认证失败: {msg}", "auth", recoverable=False)
            if "rate" in code.lower() or "limit" in code.lower():
                raise LLMError(f"请求限流: {msg}", "rate_limit", recoverable=True)
            raise LLMError(f"API 错误: {msg}", "server", recoverable=True)

        content = ""
        tokens_used = 0
        model_name = payload.get("model", "")

        if "choices" in data and data["choices"]:
            choice = data["choices"][0]
            content = choice.get("message", {}).get("content", "")
            model_name = choice.get("model", model_name)

        if "usage" in data:
            tokens_used = data["usage"].get("total_tokens", 0)

        return {
            "content": content or "",
            "tokens_used": tokens_used,
            "model": model_name,
        }

    def _do_stream(self, url: str, payload: dict, timeout: float) -> Dict[str, Any]:
        """SSE 流式请求，收集完整内容后返回"""
        backend = self._get_backend()
        collected_parts = []

        if backend == "requests":
            import requests as req
            try:
                resp = req.post(url, json=payload, timeout=timeout, stream=True)
                resp.raise_for_status()
                for line in resp.iter_lines(decode_unicode=True):
                    if line and line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            import json as _json
                            chunk = _json.loads(data_str)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            if "content" in delta:
                                collected_parts.append(delta["content"])
                        except Exception:
                            continue
            except req.exceptions.Timeout:
                raise LLMError(f"流式请求超时 ({timeout}s)", "timeout", recoverable=True)
            except Exception as e:
                raise LLMError(f"流式请求失败: {e}", "connection", recoverable=True)
        else:
            import urllib.request
            import urllib.error
            import json as _json
            body = _json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url, data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    for raw_line in resp:
                        line = raw_line.decode("utf-8").strip()
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str.strip() == "[DONE]":
                                break
                            try:
                                chunk = _json.loads(data_str)
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                if "content" in delta:
                                    collected_parts.append(delta["content"])
                            except Exception:
                                continue
            except Exception as e:
                if "timed out" in str(e):
                    raise LLMError(f"流式请求超时 ({timeout}s)", "timeout", recoverable=True)
                raise LLMError(f"流式请求失败: {e}", "connection", recoverable=True)

        return {
            "content": "".join(collected_parts),
            "tokens_used": 0,  # 流式模式无法精确统计
            "model": payload.get("model", ""),
        }


# 全局共享实例
_shared_llm_client: Optional[LLMClient] = None


def get_llm_client(**kwargs) -> LLMClient:
    """获取共享 LLM 客户端"""
    global _shared_llm_client
    if _shared_llm_client is None:
        _shared_llm_client = LLMClient(**kwargs)
    return _shared_llm_client
