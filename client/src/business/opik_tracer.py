"""
📊 Opik 追踪模块

为 LivingTreeAI 提供 LLM 调用追踪、监控和性能分析。
集成 Opik SDK，支持：
- LLM 调用追踪
- Token 使用监控
- 成本分析
- 性能分析
- 错误追踪
"""

import functools
import logging
import time
from typing import Optional, Dict, Any, Callable, Union
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ============= Opik 配置 =============

try:
    import opik

    OPIK_AVAILABLE = True
except ImportError:
    logger.warning("Opik SDK 未安装，追踪功能将不可用")
    OPIK_AVAILABLE = False


@dataclass
class OpikConfig:
    """Opik 配置"""
    enabled: bool = True
    use_local: bool = True  # 使用本地部署
    workspace: Optional[str] = None
    api_key: Optional[str] = None
    project_name: str = "livingtree-ai"
    auto_init: bool = True  # 自动初始化

    # 追踪选项
    trace_llm_calls: bool = True
    trace_tool_calls: bool = True
    trace_agent_calls: bool = True

    # 性能监控
    monitor_token_usage: bool = True
    monitor_cost: bool = True
    monitor_latency: bool = True


# 全局配置
_global_config: Optional[OpikConfig] = None
_opik_initialized: bool = False


def configure_opik(config: Optional[OpikConfig] = None) -> bool:
    """
    配置并初始化 Opik

    Args:
        config: OpikConfig 实例，如果为 None 则使用默认配置

    Returns:
        bool: 是否初始化成功
    """
    global _global_config, _opik_initialized

    if not OPIK_AVAILABLE:
        logger.error("Opik SDK 未安装，请运行: pip install opik")
        return False

    if config is None:
        config = OpikConfig()

    _global_config = config

    try:
        if config.use_local:
            opik.configure(use_local=True)
            logger.info("✅ Opik 已配置为本地模式")
        else:
            if config.api_key:
                opik.configure(api_key=config.api_key, workspace=config.workspace)
            logger.info(f"✅ Opik 已配置为云端模式 (workspace: {config.workspace})")

        _opik_initialized = True
        logger.info(f"✅ Opik 初始化成功 (project: {config.project_name})")
        return True

    except Exception as e:
        logger.error(f"❌ Opik 初始化失败: {e}")
        return False


def is_opik_enabled() -> bool:
    """检查 Opik 是否启用"""
    if not OPIK_AVAILABLE:
        return False

    if _global_config is None:
        return False

    return _global_config.enabled and _opik_initialized


# ============= 追踪装饰器 =============

def trace_llm_call(func: Optional[Callable] = None, *, name: Optional[str] = None):
    """
    追踪 LLM 调用的装饰器

    Usage:
        @trace_llm_call
        def call_model(...):
            ...

        @trace_llm_call(name="my_llm_call")
        def another_call(...):
            ...
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if not is_opik_enabled():
                return fn(*args, **kwargs)

            trace_name = name or fn.__name__
            start_time = time.time()

            # 创建 Opik trace
            trace = opik.trace(name=trace_name, type="llm")

            try:
                # 记录输入
                input_data = {
                    "model": kwargs.get("model", args[0] if args else None),
                    "messages": kwargs.get("messages", []),
                    "temperature": kwargs.get("temperature", 0.7),
                    "max_tokens": kwargs.get("max_tokens", 4096),
                }

                # 执行函数
                result = fn(*args, **kwargs)

                # 记录输出
                end_time = time.time()
                latency = end_time - start_time

                output_data = {
                    "response": result if isinstance(result, str) else str(result),
                    "latency": latency,
                }

                # 尝试提取 token 使用
                if isinstance(result, dict):
                    if "usage" in result:
                        output_data["token_usage"] = result["usage"]

                trace.log(
                    input=input_data,
                    output=output_data,
                    metadata={
                        "latency": latency,
                        "success": True,
                    }
                )

                return result

            except Exception as e:
                end_time = time.time()
                latency = end_time - start_time

                trace.log(
                    input=input_data if 'input_data' in locals() else {},
                    output={"error": str(e)},
                    metadata={
                        "latency": latency,
                        "success": False,
                        "error": str(e),
                    }
                )

                raise

        return wrapper

    if func is None:
        return decorator
    else:
        return decorator(func)


def trace_tool_call(func: Optional[Callable] = None, *, name: Optional[str] = None):
    """
    追踪 Tool 调用的装饰器

    Usage:
        @trace_tool_call
        def execute_tool(...):
            ...
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if not is_opik_enabled():
                return fn(*args, **kwargs)

            trace_name = name or f"tool_{fn.__name__}"
            start_time = time.time()

            trace = opik.trace(name=trace_name, type="tool")

            try:
                input_data = {
                    "args": str(args),
                    "kwargs": str(kwargs),
                }

                result = fn(*args, **kwargs)

                end_time = time.time()
                latency = end_time - start_time

                trace.log(
                    input=input_data,
                    output={"result": str(result)},
                    metadata={
                        "latency": latency,
                        "success": True,
                    }
                )

                return result

            except Exception as e:
                end_time = time.time()
                latency = end_time - start_time

                trace.log(
                    input=input_data if 'input_data' in locals() else {},
                    output={"error": str(e)},
                    metadata={
                        "latency": latency,
                        "success": False,
                        "error": str(e),
                    }
                )

                raise

        return wrapper

    if func is None:
        return decorator
    else:
        return decorator(func)


def trace_agent_call(func: Optional[Callable] = None, *, name: Optional[str] = None):
    """
    追踪 Agent 调用的装饰器

    Usage:
        @trace_agent_call
        def run_agent(...):
            ...
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if not is_opik_enabled():
                return fn(*args, **kwargs)

            trace_name = name or f"agent_{fn.__name__}"
            start_time = time.time()

            trace = opik.trace(name=trace_name, type="agent")

            try:
                input_data = {
                    "args": str(args),
                    "kwargs": str(kwargs),
                }

                result = fn(*args, **kwargs)

                end_time = time.time()
                latency = end_time - start_time

                trace.log(
                    input=input_data,
                    output={"result": str(result)},
                    metadata={
                        "latency": latency,
                        "success": True,
                    }
                )

                return result

            except Exception as e:
                end_time = time.time()
                latency = end_time - start_time

                trace.log(
                    input=input_data if 'input_data' in locals() else {},
                    output={"error": str(e)},
                    metadata={
                        "latency": latency,
                        "success": False,
                        "error": str(e),
                    }
                )

                raise

        return wrapper

    if func is None:
        return decorator
    else:
        return decorator(func)


# ============= 手动追踪接口 =============

def start_trace(name: str, trace_type: str = "generic", metadata: Optional[Dict] = None):
    """
    手动开始一个 trace

    Args:
        name: trace 名称
        trace_type: trace 类型 ("llm", "tool", "agent", "generic")
        metadata: 元数据

    Returns:
        Opik trace 对象
    """
    if not is_opik_enabled():
        return None

    trace = opik.trace(name=name, type=trace_type, metadata=metadata or {})
    return trace


def log_trace(trace, input_data: Any, output_data: Any, metadata: Optional[Dict] = None):
    """
    记录 trace 的输入和输出

    Args:
        trace: Opik trace 对象
        input_data: 输入数据
        output_data: 输出数据
        metadata: 元数据
    """
    if trace is None:
        return

    try:
        trace.log(
            input=input_data,
            output=output_data,
            metadata=metadata or {}
        )
    except Exception as e:
        logger.error(f"记录 trace 失败: {e}")


# ============= 初始化函数 =============

def init_opik_for_livingtree(config: Optional[OpikConfig] = None) -> bool:
    """
    为 LivingTreeAI 项目初始化 Opik

    Args:
        config: 可选的配置对象

    Returns:
        bool: 是否初始化成功
    """
    default_config = OpikConfig(
        enabled=True,
        use_local=True,  # 默认使用本地部署
        project_name="livingtree-ai",
        trace_llm_calls=True,
        trace_tool_calls=True,
        trace_agent_calls=True,
        monitor_token_usage=True,
        monitor_cost=True,
        monitor_latency=True,
    )

    if config:
        # 合并配置
        final_config = OpikConfig(
            enabled=config.enabled if config.enabled is not None else default_config.enabled,
            use_local=config.use_local if config.use_local is not None else default_config.use_local,
            workspace=config.workspace or default_config.workspace,
            api_key=config.api_key or default_config.api_key,
            project_name=config.project_name or default_config.project_name,
            trace_llm_calls=config.trace_llm_calls if config.trace_llm_calls is not None else default_config.trace_llm_calls,
            trace_tool_calls=config.trace_tool_calls if config.trace_tool_calls is not None else default_config.trace_tool_calls,
            trace_agent_calls=config.trace_agent_calls if config.trace_agent_calls is not None else default_config.trace_agent_calls,
            monitor_token_usage=config.monitor_token_usage if config.monitor_token_usage is not None else default_config.monitor_token_usage,
            monitor_cost=config.monitor_cost if config.monitor_cost is not None else default_config.monitor_cost,
            monitor_latency=config.monitor_latency if config.monitor_latency is not None else default_config.monitor_latency,
        )
    else:
        final_config = default_config

    return configure_opik(final_config)


# ============= 导出 =============

__all__ = [
    "OpikConfig",
    "configure_opik",
    "is_opik_enabled",
    "trace_llm_call",
    "trace_tool_call",
    "trace_agent_call",
    "start_trace",
    "log_trace",
    "init_opik_for_livingtree",
    "OPIK_AVAILABLE",
]
