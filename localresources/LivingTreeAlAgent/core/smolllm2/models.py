# -*- coding: utf-8 -*-
"""
SmolLM2 L0 快反大脑 - 数据模型
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime


class RouteType(Enum):
    """路由类型"""
    CACHE = "cache"       # 缓存命中
    LOCAL = "local"      # 本地执行
    SEARCH = "search"    # 联网搜索
    HEAVY = "heavy"      # 重型推理（大模型）
    HUMAN = "human"      # 转人工


class IntentType(Enum):
    """意图类型"""
    # 简单任务
    GREETING = "greeting"           # 问候
    SIMPLE_QUESTION = "simple_q"     # 简单问答
    FORMAT_CLEAN = "format_clean"    # 格式清洗
    JSON_EXTRACT = "json_extract"    # JSON 提取
    QUICK_REPLY = "quick_reply"      # 快速回复

    # 中等任务
    CODE_SIMPLE = "code_simple"      # 简单代码
    SEARCH_QUERY = "search_query"    # 搜索查询
    SUMMARIZE_SHORT = "summarize"    # 短文摘要

    # 复杂任务
    CODE_COMPLEX = "code_complex"    # 复杂代码
    LONG_WRITING = "long_writing"   # 长文写作
    REASONING = "reasoning"         # 复杂推理
    ANALYSIS = "analysis"           # 深度分析

    # 特殊
    UNKNOWN = "unknown"              # 未知


@dataclass
class SmolLM2Config:
    """SmolLM2 配置"""
    # 模型 ID
    model_id: str = "second-state/SmolLM2-135M-Instruct-GGUF"
    gguf_filename: str = "smollm2-135m-instruct-q4_k_m.gguf"

    # Ollama 配置
    ollama_model_name: str = "smollm2-135m"
    ollama_host: str = "http://localhost:11434"
    num_ctx: int = 2048
    temperature: float = 0.1
    num_gpu: int = 0  # CPU 运行

    # 路由配置
    fast_threshold_ms: int = 1000       # 快反阈值
    cache_threshold_chars: int = 500    # 缓存判定长度
    heavy_threshold_chars: int = 1000   # 重型判定长度（调整为1000，确保长文本正确路由）

    # 系统提示词
    system_prompt: str = """你是一个轻量级意图分类器。

任务：对用户输入进行快速分类。

路由选项：
- cache: 缓存命中，需要查缓存的问题
- local: 本地执行，简单格式化、JSON提取、代码补全等
- search: 联网搜索，需要最新信息的问题
- heavy: 重型推理，复杂分析、长文写作、深度推理
- human: 转人工，敏感投诉、无法处理的问题

意图选项：
- greeting: 问候语（你好、早上好等）
- simple_q: 简单问答（是什么、有没有、多久等）
- format_clean: 格式清洗（整理、格式化、纠错等）
- json_extract: JSON提取（提取信息转为JSON）
- quick_reply: 快速回复（客服场景的标准回复）
- code_simple: 简单代码（单行补全、简单函数）
- search_query: 搜索查询（查价格、查库存、查状态）
- summarize: 短文摘要（100字以内的摘要请求）
- code_complex: 复杂代码（多文件、架构设计）
- long_writing: 长文写作（报告、文章、方案）
- reasoning: 复杂推理（逻辑推导、多步分析）
- analysis: 深度分析（对比分析、趋势分析）
- unknown: 无法判断

输出格式（只输出JSON，不要其他内容）：
{"route": "local", "intent": "format_clean", "reason": "简单格式化任务", "confidence": 0.9}

只输出JSON，不要解释。"""


@dataclass
class RouteDecision:
    """路由决策结果"""
    route: RouteType
    intent: IntentType
    reason: str
    confidence: float = 0.0
    latency_ms: float = 0.0
    model_used: str = "smollm2-135m"
    fallback: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "route": self.route.value,
            "intent": self.intent.value,
            "reason": self.reason,
            "confidence": self.confidence,
            "latency_ms": self.latency_ms,
            "model_used": self.model_used,
            "fallback": self.fallback,
        }

    @property
    def is_fast(self) -> bool:
        """是否快速响应"""
        return self.route in (RouteType.CACHE, RouteType.LOCAL)

    @property
    def needs_cloud(self) -> bool:
        """是否需要云端大模型"""
        return self.route in (RouteType.HEAVY, RouteType.SEARCH)


@dataclass
class CachedResponse:
    """缓存响应"""
    prompt_hash: str
    response: str
    created_at: datetime = field(default_factory=datetime.now)
    hit_count: int = 0
    source: str = "local"  # cache/local/search

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt_hash": self.prompt_hash,
            "response": self.response,
            "created_at": self.created_at.isoformat(),
            "hit_count": self.hit_count,
            "source": self.source,
        }


@dataclass
class RouteStats:
    """路由统计"""
    total_requests: int = 0
    cache_hits: int = 0
    local_executions: int = 0
    search_requests: int = 0
    heavy_inferences: int = 0
    human_escalations: int = 0

    avg_latency_ms: float = 0.0
    fast_response_rate: float = 0.0  # <1s 响应率

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": self.total_requests,
            "cache": self.cache_hits,
            "local": self.local_executions,
            "search": self.search_requests,
            "heavy": self.heavy_inferences,
            "human": self.human_escalations,
            "avg_latency_ms": self.avg_latency_ms,
            "fast_response_rate": self.fast_response_rate,
        }
