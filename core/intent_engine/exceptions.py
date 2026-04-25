# -*- coding: utf-8 -*-
"""
统一异常体系 + 优雅降级 - IntentEngine Exceptions
==================================================

解决核心问题：**错误处理散乱、无分类、无降级策略**

当前项目中各模块的异常处理方式不统一：
- 有些直接 raise Exception("...")
- 有些返回 None
- 有些 print 错误后继续执行
- 没有统一的错误码和恢复机制

本模块提供：

1. **层次化异常体系**: 基础 → 领域 → 具体（3 层）
2. **错误编码**: 可机器解析的错误码（如 INTENT.001, LLM.003）
3. **优雅降级**: 每种异常都有对应的 fallback 策略
4. **上下文保留**: 异常携带完整的执行上下文，便于诊断
5. **链式追踪**: cause chain 保留完整调用栈

使用示例：
    from core.intent_engine.exceptions import (
        IntentError, LLMError, HandlerError,
        graceful_fallback,
    )
    
    try:
        result = bridge.parse_and_execute(query)
    except LLMTimeoutError as e:
        # 自动降级：用更小的模型重试
        result = graceful_fallback(e)
    except IntentParseError as e:
        # 降级：返回通用意图
        result = e.fallback_response()
    
Author: LivingTreeAI Team
Version: 1.0.0
"""

from __future__ import annotations

import traceback
import time
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Type


# ── 错误级别 ──────────────────────────────────────────────────────


class ErrorSeverity(Enum):
    """错误严重程度"""
    CRITICAL = auto()     # 系统不可用，需要立即干预
    HIGH = auto()         # 功能受损，需要关注
    MEDIUM = auto()       # 功能受限但可继续
    LOW = auto()          # 轻微问题，不影响主流程
    INFO = auto()         # 信息性，非错误


class RecoveryStrategy(Enum):
    """恢复/降级策略"""
    NONE = "none"                    # 无法恢复
    RETRY = "retry"                  # 重试
    FALLBACK_MODEL = "fallback_model"  # 降级模型（如大模型→小模型）
    FALLBACK_HANDLER = "fallback_handler"  # 降级处理器
    CACHE_RESULT = "cache_result"    # 返回缓存结果
    DEFAULT_RESPONSE = "default_response"  # 返回默认响应
    SKIP_AND_CONTINUE = "skip"       # 跳过继续


# ── 核心异常基类 ──────────────────────────────────────────────────


@dataclass
class ErrorContext:
    """
    错误上下文 — 记录出错时的完整环境
    
    用于：
    - 日志记录
    - 错误上报
    - 诊断分析
    - 用户友好的错误提示生成
    """
    # 发生位置
    module: str = ""
    function: str = ""
    line: int = 0
    
    # 输入数据
    input_summary: str = ""          # 输入摘要（脱敏）
    input_size: int = 0
    
    # 执行环境
    timestamp: float = 0.0
    session_id: str = ""
    trace_id: str = ""
    
    # 执行状态
    step_name: str = ""              # 当前步骤名称（来自 TaskTracer）
    elapsed_ms: float = 0.0          # 出错时已耗时
    
    # 相关数据
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module": self.module,
            "function": self.function,
            "line": self.line,
            "input_summary": self.input_summary[:100],
            "step": self.step_name,
            "elapsed_ms": round(self.elapsed_ms, 1),
        }


class BaseIntentError(Exception):
    """
    所有 IntentEngine 异常的基类
    
    特性：
    - 错误码（machine-readable）
    - 严重程度
    - 降级策略
    - 完整上下文
    - 链式原因追踪
    """

    # 子类必须定义这些类属性
    error_code: str = "BASE.000"
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    recovery: RecoveryStrategy = RecoveryStrategy.DEFAULT_RESPONSE
    user_message_template: str = "发生了一个错误: {error}"
    
    def __init__(
        self,
        message: str,
        *,
        context: Optional[ErrorContext] = None,
        cause: Optional[Exception] = None,
        **template_vars,
    ):
        super().__init__(message)
        self.message = message
        self.context = context or ErrorContext(timestamp=time.time())
        
        # 链式原因
        self.__cause__ = cause
        
        # 模板变量
        self._vars = {"error": message, **template_vars}
        
        # 调用栈快照
        self._tb_str = traceback.format_exc() if not isinstance(self.__cause__, type(None)) else ""
    
    @property
    def code(self) -> str:
        return self.error_code

    @property
    def user_message(self) -> str:
        """面向用户的友好提示"""
        try:
            return self.user_message_template.format(**self._vars)
        except (KeyError, ValueError):
            return self.message

    @property
    def diagnostic_info(self) -> Dict[str, Any]:
        """诊断信息字典（用于日志和上报）"""
        return {
            "code": self.error_code,
            "severity": self.severity.name,
            "recovery": self.recovery.value,
            "message": self.message,
            "user_message": self.user_message,
            "context": self.context.to_dict(),
            "cause_type": type(self.__cause__).__name__ if self.__cause__ else None,
            "cause_msg": str(self.__cause__)[:200] if self.__cause__ else None,
        }
    
    def to_json(self) -> str:
        import json
        return json.dumps(self.diagnostic_info, ensure_ascii=False, default=str)

    def fallback_response(
        self,
        default_output: Any = None,
    ) -> Dict[str, Any]:
        """
        生成降级响应
        
        根据 recovery 策略返回一个安全的默认结果。
        """
        response = {
            "status": "degraded",
            "error_code": self.error_code,
            "user_message": self.user_message,
            "original_error": self.message,
            "recovery_strategy": self.recovery.value,
        }
        
        if self.recovery == RecoveryStrategy.DEFAULT_RESPONSE:
            response["output"] = default_output or {
                "text": f"抱歉，{self.user_message}",
                "suggestions": [
                    "请检查输入是否正确",
                    "可以尝试换个方式描述需求",
                ],
            }
        elif self.recovery == RecoveryStrategy.SKIP_AND_CONTINUE:
            response["output"] = None
            response["skipped"] = True
        
        return response


# ── 意图引擎层异常 ────────────────────────────────────────────────


class IntentError(BaseIntentError):
    """意图引擎相关错误的基类"""
    user_message_template = "意图理解出现了一点小问题: {error}"


class IntentParseError(IntentError):
    """意图解析失败（规则匹配全部失败）"""
    error_code = "INTENT.001"
    severity = ErrorSeverity.MEDIUM
    recovery = RecoveryStrategy.FALLBACK_HANDLER
    user_message_template = "我没能完全理解您的意思，能换种方式说吗？\n原始: {input}"


class IntentClassifierError(IntentError):
    """意图分类失败"""
    error_code = "INTENT.002"
    severity = ErrorSeverity.MEDIUM
    recovery = RecoveryStrategy.DEFAULT_RESPONSE
    user_message_template = "无法确定任务类型，将按通用方式处理"


class IntentContextLostError(IntentError):
    """上下文丢失（多轮对话中话题切换检测失败）"""
    error_code = "INTENT.003"
    severity = ErrorSeverity.LOW
    recovery = RecoveryStrategy.NONE
    user_message_template = "之前的对话上下文已丢失，我们将开始新的对话"


class CompositeIntentTooComplex(IntentError):
    """复合意图过于复杂（子意图过多）"""
    error_code = "INTENT.004"
    severity = ErrorSeverity.HIGH
    recovery = RecoveryStrategy.SKIP_AND_CONTINUE
    user_message_template = "您的请求包含了太多任务，我会分步处理最重要的部分"


class StateMachineError(IntentError):
    """意图状态机错误"""
    error_code = "INTENT.010"
    severity = ErrorSeverity.MEDIUM
    recovery = RecoveryStrategy.DEFAULT_RESPONSE


# ── LLM 层异常 ────────────────────────────────────────────────────


class LLMBaseError(BaseIntentError):
    """LLM 调用相关错误的基类"""
    user_message_template = "AI 模型服务暂时出了点问题: {error}"


class LLMConnectionError(LLMBaseError):
    """连接失败"""
    error_code = "LLM.001"
    severity = ErrorSeverity.HIGH
    recovery = RecoveryStrategy.RETRY
    user_message_template = "无法连接到 AI 服务，正在尝试重新连接..."


class LLMTimeoutError(LLMBaseError):
    """超时"""
    error_code = "LLM.002"
    severity = ErrorSeverity.HIGH
    recovery = RecoveryStrategy.FALLBACK_MODEL
    user_message_template = "AI 思考时间太长了，让我试试更快的方式..."


class LLMRateLimitError(LLMBaseError):
    """限流"""
    error_code = "LLM.003"
    severity = ErrorSeverity.MEDIUM
    recovery = RecoveryStrategy.RETRY
    user_message_template = "AI 服务繁忙，请稍后再试或简化您的需求"


class LLMAuthError(LLMBaseError):
    """认证失败"""
    error_code = "LLM.004"
    severity = ErrorSeverity.CRITICAL
    recovery = RecoveryStrategy.NONE
    user_message_template = "AI 服务认证失败，请联系管理员"


class LLMResponseParseError(LLMBaseError):
    """响应解析失败"""
    error_code = "LLM.005"
    severity = ErrorSeverity.MEDIUM
    recovery = RecoveryStrategy.RETRY
    user_message_template = "AI 的回复格式有问题，正在重试..."


class LLMModelNotFoundError(LLMBaseError):
    """模型不存在"""
    error_code = "LLM.006"
    severity = ErrorSeverity.HIGH
    recovery = RecoveryStrategy.FALLBACK_MODEL
    user_message_template = "请求的 AI 模型不可用，正在切换到备用模型..."


# ── Handler 层异常 ────────────────────────────────────────────────


class HandlerError(BaseIntentError):
    """Handler 执行相关错误的基类"""
    user_message_template = "任务执行过程中出现了问题: {error}"


class HandlerNotRegisteredError(HandlerError):
    """没有注册对应的处理器"""
    error_code = "HANDLER.001"
    severity = ErrorSeverity.MEDIUM
    recovery = RecoveryStrategy.DEFAULT_RESPONSE
    user_message_template = "暂不支持这种类型的任务: {type}"


class HandlerExecutionError(HandlerError):
    """处理器内部执行错误"""
    error_code = "HANDLER.002"
    severity = ErrorSeverity.HIGH
    recovery = RecoveryStrategy.CACHE_RESULT
    user_message_template = "任务执行失败: {error}\n建议：检查代码是否有语法错误"


class HandlerInputValidationError(HandlerError):
    """输入验证失败"""
    error_code = "HANDLER.003"
    severity = ErrorSeverity.LOW
    recovery = RecoveryStrategy.DEFAULT_RESPONSE
    user_message_template = "输入信息不完整，需要更多信息: {missing}"


class FileOperationError(HandlerError):
    """文件操作错误"""
    error_code = "HANDLER.010"
    severity = ErrorSeverity.MEDIUM
    recovery = RecoveryStrategy.SKIP_AND_CONTINUE
    user_message_template = "文件操作失败: {error}"


# ── Bridge 层异常 ────────────────────────────────────────────────


class BridgeError(BaseIntentError):
    """Bridge 桥接器错误基类"""


class BridgeConfigError(BridgeError):
    """配置错误"""
    error_code = "BRIDGE.001"
    severity = ErrorSeverity.HIGH
    recovery = RecoveryStrategy.NONE
    user_message_template = "系统配置有误，请联系管理员: {error}"


class BridgeRoutingError(BridgeError):
    """路由失败（找不到合适的 Handler）"""
    error_code = "BRIDGE.002"
    severity = ErrorSeverity.MEDIUM
    recovery = RecoveryStrategy.DEFAULT_RESPONSE
    user_message_template = "无法找到合适的处理程序来处理这个请求"


# ── 降级工具函数 ──────────────────────────────────────────────────


def graceful_fallback(error: BaseIntentError, **kwargs) -> Dict[str, Any]:
    """
    统一的优雅降级入口
    
    根据异常类型自动选择最佳降级策略。
    
    Usage:
        try:
            result = bridge.execute(intent)
        except BaseIntentError as e:
            result = graceful_fallback(e)
    """
    logger.warning(f"[Fallback] {error.code}: {error.message} "
                   f"(strategy={error.recovery.value})")

    # 策略分发
    strategy = error.recovery
    
    if strategy == RecoveryStrategy.DEFAULT_RESPONSE:
        return error.fallback_response(**kwargs)
    
    elif strategy == RecoveryStrategy.FALLBACK_MODEL and hasattr(error, 'context'):
        # 尝试用更小的模型
        ctx = error.context or {}
        model_fallback = kwargs.get("fallback_model_fn")
        if model_fallback and callable(model_fallback):
            try:
                return model_fallback(ctx.extra.get("query", ""), 
                                      model=kwargs.get("fallback_model", "qwen2.5:1.5b"))
            except Exception as retry_err:
                logger.error(f"[Fallback] 降级模型也失败了: {retry_err}")
                return error.fallback_response(**kwargs)
    
    elif strategy == RecoveryStrategy.SKIP_AND_CONTINUE:
        return {
            "status": "skipped",
            "error_code": error.code,
            "output": None,
            "user_message": error.user_message,
        }
    
    elif strategy == RecoveryStrategy.RETRY:
        retry_fn = kwargs.get("retry_fn")
        if retry_fn and callable(retry_fn):
            max_retries = kwargs.get("max_retries", 2)
            for attempt in range(max_retries):
                try:
                    return retry_fn(attempt=attempt)
                except Exception as retry_err:
                    logger.warning(f"[Fallback] 第 {attempt+1} 次重试失败: {retry_err}")
            return error.fallback_response(**kwargs)
    
    # 默认：返回降级响应
    return error.fallback_response(**kwargs)


def safe_execute(
    fn: Callable,
    *args,
    fallback=None,
    error_context: Optional[ErrorContext] = None,
    reraise: bool = False,
    expected_errors: Optional[List[Type[BaseIntentError]]] = None,
    **kwargs,
) -> Any:
    """
    安全执行包装器
    
    自动捕获异常并降级。
    
    Usage:
        result = safe_execute(
            bridge.execute, intent,
            fallback={"status": "ok", "output": "备用结果"},
            error_context=ErrorContext(module="bridge", function="execute"),
            expected_errors=[LLMTimeoutError, HandlerExecutionError],
        )
    """
    try:
        return fn(*args, **kwargs)
    except BaseIntentError as e:
        # 如果在预期错误列表中，降级处理
        if expected_errors is None or any(isinstance(e, t) for t in expected_errors):
            if reraise:
                raise
            logger.debug(f"[SafeExecute] 捕获预期异常: {e.code}")
            return fallback if fallback is not None else graceful_fallback(e)
        # 不在预期列表中，继续上抛
        raise
    except Exception as e:
        # 将普通异常包装为 HandlerExecutionError
        wrapped = HandlerExecutionError(
            str(e),
            context=error_context,
            cause=e,
        )
        if reraise:
            raise wrapped
        logger.warning(f"[SafeExecute] 包装未预期异常: {e}")
        return fallback if fallback is not None else graceful_fallback(wrapped)


def classify_exception(exc: Exception) -> BaseIntentError:
    """
    将任意 Python 异常分类为 IntentEngine 异常体系
    
    用于第三方库抛出的非标准异常的统一处理。
    """
    msg = str(exc).lower()
    exc_type = type(exc).__name__
    
    # 连接相关
    if any(kw in msg for kw in ("connection", "connect", "network", "refused", "timeout", "timed out")):
        if "timeout" in msg or "timed out" in msg:
            return LLMTimeoutError(msg, cause=exc)
        return LLMConnectionError(msg, cause=exc)
    
    # HTTP 状态码
    if "401" in msg or "unauthorized" in msg or "auth" in msg:
        return LLMAuthError(msg, cause=exc)
    if "429" in msg or "rate" in msg or "limit" in msg or "too many" in msg:
        return LLMRateLimitError(msg, cause=exc)
    if "500" in msg or "502" in msg or "503" in msg:
        return LLMConnectionError(msg, cause=exc)
    
    # 解析相关
    if "json" in msg or "parse" in msg or "decode" in msg:
        return LLMResponseParseError(msg, cause=exc)
    
    # 文件相关
    if any(kw in msg for kw in ("file", "permission", "not found", "ioerror")):
        return FileOperationError(msg, cause=exc)
    
    # 默认包装为 Handler 执行错误
    return HandlerExecutionError(str(exc), cause=exc)


# ── 全局错误处理器注册表 ──────────────────────────────────────────

class ErrorHandlerRegistry:
    """
    错误处理器注册表
    
    允许全局注册特定异常类型的自定义处理逻辑。
    """
    
    _handlers: Dict[str, Callable] = {}
    
    @classmethod
    def register(cls, error_code: str, handler: Callable):
        cls._handlers[error_code] = handler
    
    @classmethod
    def handle(cls, error: BaseIntentError) -> Any:
        handler = cls._handlers.get(error.error_code)
        if handler:
            return handler(error)
        return error.fallback_response()


# ── 测试入口 ──────────────────────────────────────────────────────


def _test_exceptions():
    print("=" * 60)
    print("统一异常体系测试")
    print("=" * 60)
    
    # 1. 创建各类异常
    errors = [
        LLMTimeoutError("请求超过300秒",
                        context=ErrorContext(module="llm_client", function="chat"),
                       ),
        IntentParseError("无法识别意图",
                         template_vars={"input": "xyzabc"},
                        ),
        HandlerNotRegisteredError("没有 CODE_GENERATION 处理器",
                                   template_vars={"type": "CODE_GENERATION"},
                                  ),
        FileOperationError("权限不足: /root/secret.txt"),
    ]
    
    print("\n--- 异常实例 ---")
    for e in errors:
        print(f"\n[{e.code}] {e.severity.name}")
        print(f"  原始: {e.message}")
        print(f"  用户提示: {e.user_message}")
        print(f"  降级策略: {e.recovery.value}")
        print(f"  降级响应 keys: {list(e.fallback_response().keys())}")

    # 2. graceful_fallback 测试
    print("\n\n--- 优雅降级测试 ---")
    try:
        raise LLMTimeoutError("Ollama 响应超时")
    except LLMTimeoutError as e:
        result = graceful_fallback(e)
        print(f"  status: {result['status']}")
        print(f"  user_message: {result.get('user_message', '')[:60]}")

    # 3. classify_exception 测试
    print("\n\n--- 异常分类测试 ---")
    test_exceptions = [
        ConnectionRefusedError("Connection refused"),
        TimeoutError("Request timed out after 30 seconds"),
        FileNotFoundError("No such file: /tmp/data.json"),
        ValueError("Invalid JSON: unexpected EOF"),
    ]
    for exc in test_exceptions:
        classified = classify_exception(exc)
        print(f"  {exc_type.__name__}:20s → {classified.code} ({classified.severity.name})")


if __name__ == "__main__":
    _test_exceptions()
