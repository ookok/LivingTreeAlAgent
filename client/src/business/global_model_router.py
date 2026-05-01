"""
🌐 全局模型路由器
为整个LivingTreeAI项目提供统一的LLM调用路由

功能：
- 支持20+种模型能力
- 流式调用支持
- 自动fallback机制
- 响应缓存（LRU + 语义缓存）
- 负载均衡
- 历史成功率追踪
- 🆕 智能任务分类器（L0层轻量级评估）
- 🆕 渐进式推理（自动升级降级）
- 🆕 上下文感知路由（根据对话状态动态选择）
- 🆕 资源感知调度（实时监控CPU/GPU/内存）
- 🆕 推理缓存与复用（跨层共享）

分层架构：
L0: SmolLM2 (Fast Reverse Brain) - 快速路由/意图分类
L1: Qwen2.5-1.5B (light weight) - 基础理解
L2: Qwen3.5: 4b (standard) - 中级推理
L3: Qwen3.5: 9b (Advanced) - 高级推理
L4: DeepSeek (Expert) - 深度生成/思考模式
"""

import asyncio
import hashlib
import json
import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, List, Callable, Iterator, AsyncIterator, Tuple, Union
from pathlib import Path
from collections import defaultdict, OrderedDict
from functools import lru_cache
import asyncio.tasks

logger = logging.getLogger(__name__)

# ── Opik 追踪支持 ─────────────────────────────────────────────────
try:
    from business.opik_tracer import (
        is_opik_enabled,
        start_trace,
        log_trace,
    )
    OPIK_TRACER_AVAILABLE = True
except ImportError:
    logger.warning("Opik 追踪模块导入失败，追踪功能将不可用")
    OPIK_TRACER_AVAILABLE = False
    is_opik_enabled = lambda: False
    start_trace = lambda *a, **kw: None
    log_trace = lambda *a, **kw: None


# ============= 专家思考模式支持 =============

# 延迟导入，避免循环导入
_expert_thinking_controller = None

def _get_expert_thinking_controller():
    """获取专家思考模式控制器（延迟加载）"""
    global _expert_thinking_controller
    if _expert_thinking_controller is None:
        try:
            from business.ei_agent.expert_thinking_mode import (
                get_expert_thinking_controller
            )
            _expert_thinking_controller = get_expert_thinking_controller()
        except ImportError as e:
            logger.warning(f"专家思考模式控制器导入失败: {e}")
            return None
    return _expert_thinking_controller


# ============= 自适应路由组件 =============

# 延迟导入自适应路由组件，避免循环导入
_task_classifier = None
_context_router = None
_inference_cache = None

def _get_task_classifier():
    """获取智能任务分类器（延迟加载）"""
    global _task_classifier
    if _task_classifier is None:
        try:
            from business.smart_task_classifier import get_task_classifier
            _task_classifier = get_task_classifier()
        except ImportError as e:
            logger.warning(f"智能任务分类器导入失败: {e}")
            return None
    return _task_classifier

def _get_context_router():
    """获取上下文感知路由器（延迟加载）"""
    global _context_router
    if _context_router is None:
        try:
            from business.context_aware_routing import ContextAwareRouting
            _context_router = ContextAwareRouting(None)  # 稍后设置 router
        except ImportError as e:
            logger.warning(f"上下文感知路由器导入失败: {e}")
            return None
    return _context_router

def _get_inference_cache():
    """获取推理缓存（延迟加载）"""
    global _inference_cache
    if _inference_cache is None:
        try:
            from business.inference_cache import get_inference_cache
            _inference_cache = get_inference_cache()
        except ImportError as e:
            logger.warning(f"推理缓存导入失败: {e}")
            return None
    return _inference_cache


# ============= 能力定义 =============

class ModelCapability(Enum):
    """模型能力（20+种）"""
    # 基础能力
    CHAT = "chat"                           # 对话
    COMPLETION = "completion"               # 文本补全
    
    # 理解与生成
    DOCUMENT_PLANNING = "document_planning" # 文档规划
    CONTENT_GENERATION = "content_generation" # 内容生成
    FORMAT_UNDERSTANDING = "format_understanding"  # 格式理解
    COMPLIANCE_CHECK = "compliance_check"     # 合规检查
    OPTIMIZATION = "optimization"             # 优化建议
    TRANSLATION = "translation"               # 翻译
    SUMMARIZATION = "summarization"           # 摘要
    PARAPHRASE = "paraphrase"               # 改写
    
    # 代码相关
    CODE_GENERATION = "code_generation"       # 代码生成
    CODE_REVIEW = "code_review"             # 代码审查
    CODE_DEBUG = "code_debug"               # 代码调试
    CODE_EXPLANATION = "code_explanation"   # 代码解释
    
    # 知识相关
    KNOWLEDGE_QUERY = "knowledge_query"       # 知识查询
    CONCEPT_EXPLAIN = "concept_explain"       # 概念解释
    WEB_SEARCH = "web_search"               # 网络搜索
    
    # 高级能力
    REASONING = "reasoning"                 # 推理
    PLANNING = "planning"                   # 规划
    DATA_ANALYSIS = "data_analysis"         # 数据分析
    IMAGE_UNDERSTANDING = "image_understanding"  # 图像理解
    
    # 特殊能力
    STREAMING = "streaming"                 # 流式输出
    FUNCTION_CALLING = "function_calling"   # 函数调用
    JSON_MODE = "json_mode"                 # JSON模式
    EMBEDDING = "embedding"                 # 文本向量化


class ModelBackend(Enum):
    """模型后端"""
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    LTAI = "ltai"   # LTAI (LivingTreeAi) 本地细胞模型
    HERDSMAN = "herdsman"  # FlowyAIPC 牧马人引擎
    CUSTOM = "custom"
    MOCK = "mock"  # 测试用


class LogLevel(Enum):
    """日志级别"""
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


class HealthStatus(Enum):
    """健康状态"""
    HEALTHY = "healthy"       # 健康
    DEGRADED = "degraded"    # 降级（部分功能可用）
    UNHEALTHY = "unhealthy"   # 不健康
    UNKNOWN = "unknown"       # 未知


class LoadBalancingStrategy(Enum):
    """负载均衡策略"""
    ROUND_ROBIN = "round_robin"       # 轮询
    LEAST_LOAD = "least_load"         # 最小负载
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"  # 加权轮询
    RANDOM = "random"                 # 随机


class CompressionLevel(Enum):
    """caveman 压缩级别"""
    DISABLED = "disabled"     # 禁用压缩
    LITE = "lite"             # 轻度压缩
    FULL = "full"             # 完全压缩（默认）
    ULTRA = "ultra"           # 极致压缩
    WENYAN = "wenyan"         # 文言文模式（趣味模式）


@dataclass
class RoutingWeights:
    """
    路由三维权重配置
    
    三个维度：
    - capability: 能力评分（质量/成功率/能力匹配度）
    - cost:        成本评分（费用越低分越高）
    - latency:     延迟评分（响应时间越短/负载越低分越高）
    
    权重和为1.0，自动归一化。
    """
    capability: float = 0.4
    cost: float = 0.3
    latency: float = 0.3

    def normalize(self) -> "RoutingWeights":
        """归一化权重（确保总和为1）"""
        total = self.capability + self.cost + self.latency
        if total == 0:
            return RoutingWeights(0.34, 0.33, 0.33)
        return RoutingWeights(
            self.capability / total,
            self.cost / total,
            self.latency / total,
        )

    def to_dict(self) -> dict:
        n = self.normalize()
        return {"capability": round(n.capability, 2), "cost": round(n.cost, 2), "latency": round(n.latency, 2)}


@dataclass
class ModelInfo:
    """模型信息"""
    model_id: str
    name: str
    backend: ModelBackend
    
    # 能力
    capabilities: List[ModelCapability] = field(default_factory=list)
    
    # 性能参数
    max_tokens: int = 4096
    context_length: int = 4096
    quality_score: float = 0.7     # 0-1, 质量评分
    speed_score: float = 0.5       # 0-1, 速度评分
    cost_score: float = 1.0        # 0-1, 1=免费, 0=极贵
    privacy_score: float = 1.0     # 0-1, 1=完全本地
    
    # 状态
    is_available: bool = True
    current_load: int = 0          # 当前负载（正在处理的请求数）
    success_rate: float = 1.0      # 历史成功率
    avg_response_time: float = 0.0  # 平均响应时间（秒）
    
    # 配置
    config: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "model_id": self.model_id,
            "name": self.name,
            "backend": self.backend.value,
            "capabilities": [c.value for c in self.capabilities],
            "max_tokens": self.max_tokens,
            "context_length": self.context_length,
            "quality": round(self.quality_score, 2),
            "speed": round(self.speed_score, 2),
            "cost": round(self.cost_score, 2),
            "privacy": round(self.privacy_score, 2),
            "available": self.is_available,
            "current_load": self.current_load,
            "success_rate": round(self.success_rate, 2),
            "avg_response_time": round(self.avg_response_time, 2),
        }
    
    def supports_capability(self, capability: ModelCapability) -> bool:
        """检查是否支持某能力"""
        return capability in self.capabilities
    
    def can_handle_context(self, context_length: int) -> bool:
        """检查是否能处理指定上下文长度"""
        return self.context_length >= context_length
    
    def update_stats(self, success: bool, response_time: float):
        """更新统计信息"""
        # 更新成功率（指数移动平均）
        alpha = 0.1
        self.success_rate = (1 - alpha) * self.success_rate + alpha * (1.0 if success else 0.0)
        
        # 更新平均响应时间
        if self.avg_response_time == 0:
            self.avg_response_time = response_time
        else:
            self.avg_response_time = (1 - alpha) * self.avg_response_time + alpha * response_time


# ============= 路由策略 =============

class RoutingStrategy(Enum):
    """路由策略"""
    QUALITY = "quality"       # 质量优先
    SPEED = "speed"           # 速度优先
    COST = "cost"             # 成本优先
    PRIVACY = "privacy"       # 隐私优先
    BALANCED = "balanced"     # 均衡模式
    AUTO = "auto"             # 自动选择（根据能力）
    TIER_BASED = "tier_based" # 分层路由（L0-L4）


class ModelTier(Enum):
    """模型分层（L0-L4）
    
    分层含义：
    - L0: 快速路由/意图分类（最快、最轻量）
    - L1: 基础理解（简单问答、关键词提取）
    - L2: 中级推理（摘要、翻译、简单代码）
    - L3: 高级推理/意图理解（复杂推理、代码生成）
    - L4: 深度生成/思考模式（最高质量、最慢）
    """
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"
    
    @classmethod
    def from_string(cls, tier_str: str) -> "ModelTier":
        """从字符串创建（如 "L0", "l1", "3"）"""
        tier_str = tier_str.upper().strip()
        if tier_str.startswith("L"):
            tier_str = tier_str[1:]
        try:
            tier_num = int(tier_str)
            if 0 <= tier_num <= 4:
                return cls(f"L{tier_num}")
        except ValueError:
            pass
        return cls.L0  # 默认 L0


class GlobalModelRouter:
    """
    全局模型路由器
    
    所有LLM调用都应通过此路由器，不应直接调用OllamaClient等
    """
    
    # 任务 → 策略 映射（auto策略时使用）
    TASK_STRATEGY_MAP = {
        ModelCapability.DOCUMENT_PLANNING: RoutingStrategy.BALANCED,
        ModelCapability.CONTENT_GENERATION: RoutingStrategy.QUALITY,
        ModelCapability.FORMAT_UNDERSTANDING: RoutingStrategy.BALANCED,
        ModelCapability.COMPLIANCE_CHECK: RoutingStrategy.QUALITY,
        ModelCapability.OPTIMIZATION: RoutingStrategy.BALANCED,
        ModelCapability.TRANSLATION: RoutingStrategy.SPEED,
        ModelCapability.SUMMARIZATION: RoutingStrategy.SPEED,
        ModelCapability.CODE_GENERATION: RoutingStrategy.QUALITY,
        ModelCapability.CODE_REVIEW: RoutingStrategy.QUALITY,
        ModelCapability.CODE_DEBUG: RoutingStrategy.QUALITY,
        ModelCapability.WEB_SEARCH: RoutingStrategy.SPEED,
        ModelCapability.REASONING: RoutingStrategy.QUALITY,
        ModelCapability.PLANNING: RoutingStrategy.QUALITY,
    }
    
    def __init__(self, default_weights: RoutingWeights = None):
        """
        初始化路由器
        
        Args:
            default_weights: 默认三维权重（BALANCED策略使用），默认 capability=0.4, cost=0.3, latency=0.3
        """
        self.models: Dict[str, ModelInfo] = {}
        self._call_count: Dict[str, int] = defaultdict(int)
        self._rr_index: Dict[str, int] = defaultdict(int)  # 负载均衡轮询索引 {capability_value: index}
        
        # LRU 缓存（OrderedDict，最大 1000 条）
        self._cache: OrderedDict = OrderedDict()  # {hash: response}
        self._cache_timestamps: OrderedDict = OrderedDict()  # {hash: timestamp}
        self._cache_max_size: int = 1000
        
        # TTL 分层（不同 capability 不同 TTL）
        self._ttl_map: Dict[ModelCapability, int] = {
            ModelCapability.CHAT: 3600,           # 聊天 1 小时
            ModelCapability.CODE_GENERATION: 86400, # 代码生成 1 天（更稳定）
            ModelCapability.TRANSLATION: 7200,     # 翻译 2 小时
            ModelCapability.SUMMARIZATION: 3600,   # 摘要 1 小时
            ModelCapability.REASONING: 300,        # 推理 5 分钟（易变）
            ModelCapability.WEB_SEARCH: 60,        # 搜索 1 分钟（实时性）
        }
        self._default_ttl: int = 3600
        
        self.default_weights: RoutingWeights = default_weights or RoutingWeights()
        
        # 分层路由配置（L0-L4）
        self.tier_routing: Dict[ModelTier, str] = {}  # {tier: model_id}
        
        # 只从加密配置文件加载模型（不在代码中硬编码）
        self._load_models_from_encrypted_config()
        # 如果加密配置中没有模型，用默认配置初始化
        if not self.models:
            self._init_default_models()
        
        # 设置默认分层路由
        self._setup_default_tier_routing()
        
        # ========== 自适应路由组件 ==========
        self.task_classifier = _get_task_classifier()
        self.context_router = _get_context_router()
        if self.context_router:
            self.context_router.model_router = self  # 设置反向引用
        self.inference_cache = _get_inference_cache()
        
        # 自适应路由开关
        self.auto_tier_selection_enabled = True
        self.progressive_reasoning_enabled = True
        
        logger.info("✅ 自适应路由组件加载完成")
        
        # ========== 日志级别配置 ==========
        self._log_level: LogLevel = LogLevel.INFO
        self._request_logs: List[dict] = []  # 请求日志列表
        self._max_request_logs: int = 1000   # 最大日志条数
        
        # ========== 健康检查配置 ==========
        self._health_check_interval: int = 60  # 健康检查间隔（秒）
        self._health_check_thread: Optional[threading.Thread] = None
        self._health_check_stop_event = threading.Event()
        self._health_check_running: bool = False
        
        # 健康状态缓存
        self._backend_health: Dict[str, dict] = {}  # {backend_url: {"status": ..., "last_check": ..., "models": [...]}}
        
        # 心跳检测相关字段
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._heartbeat_stop_event = threading.Event()
        self._heartbeat_interval: int = 30  # 心跳间隔（秒）
        self._heartbeat_running: bool = False
        
        # ========== API Key 校验 ==========
        self._api_key_validation_enabled: bool = False
        self._valid_api_keys: List[str] = []  # 有效的 API Key 列表
        self._api_key_header: str = "X-API-Key"  # API Key 请求头
        
        # ========== 负载均衡配置 ==========
        self._load_balancing_enabled: bool = True
        self._load_balancing_strategy: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN
        self._server_weights: Dict[str, float] = {}  # 服务器权重 {url: weight}
        
        # ========== caveman 压缩配置 ==========
        self._caveman_enabled: bool = False  # 是否启用 token 压缩
        self._caveman_level: CompressionLevel = CompressionLevel.FULL  # 压缩级别
        self._caveman_compress_input: bool = False  # 是否压缩输入
        self._caveman_min_tokens: int = 200  # 最小 token 数才触发压缩
        self._caveman_available: bool = False  # caveman 是否可用
        self._caveman_tool = None  # caveman 工具实例
        
        # 检查 caveman 可用性
        self._check_caveman_availability()
        
        # 启动心跳检测和健康检查
        self.start_heartbeat()
        self.start_health_check()
    
    def _check_caveman_availability(self):
        """检查 caveman 是否可用"""
        try:
            from business.tools.caveman_tool import CavemanTool
            self._caveman_tool = CavemanTool()
            self._caveman_available = self._caveman_tool.is_available()
            
            if self._caveman_available:
                logger.info("✅ caveman 压缩工具可用")
            else:
                logger.warning("⚠️ caveman 压缩工具不可用，请安装: pip install caveman")
                
        except ImportError as e:
            logger.warning(f"⚠️ 无法加载 CavemanTool: {e}")
            self._caveman_available = False

    def is_caveman_available(self) -> bool:
        """检查 caveman 是否可用"""
        return self._caveman_available

    def enable_caveman(self, enable: bool):
        """启用/禁用 caveman 压缩"""
        if enable and not self._caveman_available:
            logger.warning("无法启用 caveman 压缩：caveman 不可用")
            return
        self._caveman_enabled = enable
        if enable:
            logger.info("🗜️ caveman token 压缩已启用")
        else:
            logger.info("🗜️ caveman token 压缩已禁用")

    def is_caveman_enabled(self) -> bool:
        """检查是否启用了 caveman 压缩"""
        return self._caveman_enabled and self._caveman_available

    def set_caveman_level(self, level):
        """设置 caveman 压缩级别"""
        if isinstance(level, str):
            try:
                self._caveman_level = CompressionLevel(level.lower())
            except ValueError:
                logger.warning(f"无效的压缩级别: {level}，使用默认级别")
                self._caveman_level = CompressionLevel.FULL
        elif isinstance(level, CompressionLevel):
            self._caveman_level = level
        logger.info(f"🗜️ caveman 压缩级别已设置为: {self._caveman_level.value}")

    def get_caveman_level(self) -> CompressionLevel:
        """获取当前压缩级别"""
        return self._caveman_level

    async def _compress_with_caveman(self, text: str) -> str:
        """使用 caveman 压缩文本"""
        if not self.is_caveman_enabled():
            return text
        if len(text) < self._caveman_min_tokens:
            return text
        try:
            result = await self._caveman_tool.execute(
                text=text,
                level=self._caveman_level.value
            )
            if result.get("success", False):
                compressed = result.get("compressed_text", text)
                ratio = result.get("compression_ratio", 0)
                logger.debug(f"🗜️ 压缩完成: {len(text)} → {len(compressed)} ({ratio:.1%})")
                return compressed
            else:
                logger.warning(f"🗜️ 压缩失败: {result.get('message', 'unknown error')}")
                return text
        except Exception as e:
            logger.error(f"🗜️ 压缩过程中发生错误: {e}")
            return text

    # ------------------------------------------------------------------ #
    #  _setup_default_tier_routing  <<  自动分配 L0-L4 层级  >>
    # ------------------------------------------------------------------ #
    def _setup_default_tier_routing(self):
        """
        根据已加载的模型，自动分配 L0-L4 分层路由。
        
        采用逻辑：
        1. 如果只有一个可用模型：L0-L4 都使用它
        2. 如果有多个可用模型：自动选举分配到不同层级
        
        匹配规则（按 model_id / name 关键词）：
          L0  → 最快最轻量（smollm2 / qwen2.5:1.5b / qwen2.5:0.5b 等）
          L1  → 基础理解（qwen3.5:2b 等）
          L2  → 中级推理（qwen3.5:4b 等）
          L3  → 高级推理（qwen3.5:9b / qwen3.6:35b 等）
          L4  → 深度生成（最大模型 / DeepSeek-V4 / 思考模型）
        """
        # 清空旧配置
        self.tier_routing.clear()

        # 获取所有可用模型
        available_models = [m for m in self.models.values() if m.is_available]
        available_count = len(available_models)

        # 规则1：只有一个模型可用时，所有层级都用它
        if available_count == 1:
            model = available_models[0]
            for tier in ["L0", "L1", "L2", "L3", "L4"]:
                self.tier_routing[tier] = model.model_id
            logger.info(f"[分层路由] 仅有一个可用模型，L0-L4 均使用: {model.name}")
            return

        # 规则2：多个模型可用时，自动选举分配
        # 关键词 → 层级 映射（按优先级从高到低）
        tier_keywords = [
            ("L0", ["smollm2", "qwen2.5:1.5b", "qwen2.5:0.5b", "1.5b", "0.5b"]),
            ("L1", ["qwen3.5:2b", "2b"]),
            ("L2", ["qwen3.5:4b", "4b"]),
            ("L3", ["qwen3.5:9b", "qwen3.6:35b", "9b", "35b"]),
            ("L4", ["qwen3.6", "deepseek-v4", "deepseek-v4-flash", "deepseek-v4-pro", "deepseek", "thinking"]),
        ]

        # 已分配的模型ID集合（避免重复分配）
        assigned_models = set()

        for tier_str, keywords in tier_keywords:
            for model in available_models:
                if model.model_id in assigned_models:
                    continue
                text = (model.model_id + " " + model.name).lower()
                if any(kw in text for kw in keywords):
                    self.tier_routing[tier_str] = model.model_id
                    assigned_models.add(model.model_id)
                    logger.info(f"[分层路由] {tier_str} → {model.name}")
                    break

        # 规则3：如果某些层级未分配，使用剩余可用模型填充
        unassigned_models = [m for m in available_models if m.model_id not in assigned_models]
        tiers = ["L0", "L1", "L2", "L3", "L4"]
        
        for tier_str in tiers:
            if tier_str not in self.tier_routing and unassigned_models:
                model = unassigned_models.pop(0)
                self.tier_routing[tier_str] = model.model_id
                assigned_models.add(model.model_id)
                logger.info(f"[分层路由] 自动填充 {tier_str} → {model.name}")

        # 规则4：如果还有层级未分配，复用已分配的模型（优先高优先级模型）
        for tier_str in tiers:
            if tier_str not in self.tier_routing:
                # 使用第一个已分配的模型
                if assigned_models:
                    first_assigned = next(iter(assigned_models))
                    self.tier_routing[tier_str] = first_assigned
                    model_name = self.models[first_assigned].name
                    logger.info(f"[分层路由] 复用 {tier_str} → {model_name}")

        logger.info(f"[分层路由] 当前配置: {self.tier_routing}")

    def get_tier_model(self, tier: ModelTier) -> Optional[ModelInfo]:
        """
        获取指定层级的模型。
        如果未配置该层级，返回 None。
        """
        tier_key = tier.value if isinstance(tier, ModelTier) else str(tier)
        model_id = self.tier_routing.get(tier_key)
        if not model_id:
            return None
        return self.models.get(model_id)

    def set_tier_model(self, tier: ModelTier, model_id: str) -> bool:
        """
        手动设置指定层级的模型。
        返回 True 表示设置成功。
        """
        if model_id not in self.models:
            logger.error(f"[分层路由] 模型不存在: {model_id}")
            return False
        tier_key = tier.value if isinstance(tier, ModelTier) else str(tier)
        self.tier_routing[tier_key] = model_id
        name = self.models[model_id].name
        logger.info(f"[分层路由] 手动设置 {tier_key} → {name}")
        return True

    # ------------------------------------------------------------------ #
    #  _init_default_models  <<  当加密配置为空时，初始化默认配置  >>
    # ------------------------------------------------------------------ #
    def _init_default_models(self):
        """
        加密配置中没有模型时，调用 setup_default_configs()
        初始化默认配置（所有敏感信息加密存储，不在代码中硬编码）。
        """
        logger.warning("加密配置中无模型，正在初始化默认配置...")
        try:
            from business.encrypted_config import setup_default_configs
            setup_default_configs()
            self._load_models_from_encrypted_config()
            logger.info("✅ 默认配置初始化完成")
        except Exception as e:
            logger.error(f"初始化默认配置失败: {e}")

    # ------------------------------------------------------------------ #
    #  _load_models_from_encrypted_config  <<  唯一加载入口（无硬编码） >>
    # ------------------------------------------------------------------ #
    def _load_models_from_encrypted_config(self):
        """
        从加密配置加载所有模型。
        支持 Ollama（多地址）、DeepSeek API、OpenAI API。
        代码中无任何硬编码的模型/URL/Api_key。
        """
        try:
            from business.encrypted_config import load_model_config

            # ── 1. Ollama 配置（支持多地址）────────────────
            ollama_cfg = load_model_config("ollama") or {}
            servers = ollama_cfg.get("servers", [])
            if not servers and ollama_cfg.get("base_url"):
                # 向后兼容单地址格式
                servers = [{
                    "url": ollama_cfg.get("base_url", "http://localhost:11434"),
                    "priority": 0,
                    "models": ollama_cfg.get("models", []),
                }]

            for srv in servers:
                url = srv.get("url", "http://localhost:11434")
                priority = srv.get("priority", 999)
                for mname in srv.get("models", []):
                    model_id = f"ollama_{mname.replace(':', '_').replace('.', '_')}"
                    if model_id in self.models:
                        continue
                    privacy = 1.0 if ("localhost" in url or "127.0.0.1" in url) else 0.5
                    speed   = max(1.0 - priority * 0.1, 0.1)
                    self.models[model_id] = ModelInfo(
                        model_id=model_id,
                        name=f"{mname} (Ollama)",
                        backend=ModelBackend.OLLAMA,
                        capabilities=[ModelCapability.CHAT,
                                     ModelCapability.CONTENT_GENERATION,
                                     ModelCapability.CODE_GENERATION],
                        max_tokens=4096,
                        context_length=8192,
                        quality_score=0.7,
                        speed_score=speed,
                        cost_score=1.0,
                        privacy_score=privacy,
                        config={"url": url, "model": mname,
                                 "keep_alive": -1, "priority": priority},
                    )
                    logger.info(f"[加载] Ollama {mname} @ {url} (priority={priority})")

            # ── 2. DeepSeek API 配置 ───────────────────────
            ds_cfg = load_model_config("deepseek") or {}
            if ds_cfg.get("api_key"):
                api_key  = ds_cfg["api_key"]
                base_url = ds_cfg.get("base_url", "https://api.deepseek.com")
                for key, mc in (ds_cfg.get("models") or {}).items():
                    model_id = mc.get("model_id", f"deepseek_{key}")
                    if model_id in self.models:
                        continue
                    caps = [
                        getattr(ModelCapability, c.upper(), ModelCapability.CHAT)
                        for c in mc.get("capabilities", [])
                    ]
                    self.models[model_id] = ModelInfo(
                        model_id=model_id,
                        name=f"{mc.get('model_name', key)} (API)",
                        backend=ModelBackend.OPENAI,
                        capabilities=caps,
                        max_tokens=mc.get("max_tokens", 8192),
                        context_length=mc.get("context_length", 32768),
                        quality_score=mc.get("quality_score", 0.8),
                        speed_score=mc.get("speed_score", 0.9),
                        cost_score=mc.get("cost_score", 0.7),
                        privacy_score=0.1,
                        config={"model": mc.get("model_name", key),
                                 "base_url": base_url,
                                 "api_key": api_key,
                                 "timeout": mc.get("timeout", 60)},
                    )
                    logger.info(f"[加载] DeepSeek {mc.get('model_name', key)}")

            # ── 3. OpenAI API 配置（需要 enabled=True）───────
            oai_cfg = load_model_config("openai") or {}
            if oai_cfg.get("enabled") and oai_cfg.get("api_key"):
                api_key  = oai_cfg["api_key"]
                base_url = oai_cfg.get("base_url", "https://api.openai.com/v1")
                for key, mc in (oai_cfg.get("models") or {}).items():
                    model_id = mc.get("model_id", f"openai_{key}")
                    if model_id in self.models:
                        continue
                    caps = [
                        getattr(ModelCapability, c.upper(), ModelCapability.CHAT)
                        for c in mc.get("capabilities", [])
                    ]
                    self.models[model_id] = ModelInfo(
                        model_id=model_id,
                        name=f"{mc.get('model_name', key)} (OpenAI)",
                        backend=ModelBackend.OPENAI,
                        capabilities=caps,
                        max_tokens=mc.get("max_tokens", 4096),
                        context_length=mc.get("context_length", 8192),
                        quality_score=mc.get("quality_score", 0.7),
                        speed_score=mc.get("speed_score", 0.8),
                        cost_score=mc.get("cost_score", 0.5),
                        is_available=oai_cfg.get("enabled", False),
                        config={"model": mc.get("model_name", key),
                                 "base_url": base_url,
                                 "api_key": api_key,
                                 "timeout": mc.get("timeout", 60)},
                    )
                    logger.info(f"[加载] OpenAI {mc.get('model_name', key)}")

            # ── 4. LTAI 细胞模型配置 ─────────────────────────────────────
            ltai_cfg = load_model_config("ltai") or {}
            cells = ltai_cfg.get("cells", [])
            if not cells:
                # 无配置时，自动扫描 cells/ 目录注册已训练的 checkpoint
                from pathlib import Path
                cells_dir = Path(__file__).parent.parent / "llmcore" / "cells"
                if cells_dir.exists():
                    for ckpt in cells_dir.glob("*.pt"):
                        cell_name = ckpt.stem  # e.g. "table_cell_v1"
                        base_name = cell_name.rsplit("_", 1)[0] if "_v" in cell_name else cell_name
                        cells.append({
                            "cell_name": base_name,
                            "checkpoint_path": str(ckpt),
                            "model_id": f"ltai_{base_name}",
                            "capabilities": ["content_generation", "format_understanding"],
                        })

            for cell in cells:
                cell_name = cell.get("cell_name", "table_cell")
                ckpt_path = cell.get("checkpoint_path", "")
                model_id = cell.get("model_id", f"ltai_{cell_name}")
                if model_id in self.models:
                    continue
                caps = [
                    getattr(ModelCapability, c.upper(), ModelCapability.CONTENT_GENERATION)
                    for c in cell.get("capabilities", [])
                ]
                if not caps:
                    caps = [ModelCapability.CONTENT_GENERATION, ModelCapability.FORMAT_UNDERSTANDING]

                self.models[model_id] = ModelInfo(
                    model_id=model_id,
                    name=f"{cell_name} (LTAI)",
                    backend=ModelBackend.LTAI,
                    capabilities=caps,
                    max_tokens=cell.get("max_new_tokens", 256),
                    context_length=1024,
                    quality_score=cell.get("quality_score", 0.6),
                    speed_score=0.95,
                    cost_score=1.0,
                    privacy_score=1.0,
                    is_available=bool(ckpt_path and Path(ckpt_path).exists()),
                    config={
                        "cell_name": cell_name,
                        "checkpoint_path": ckpt_path,
                        "device": cell.get("device", "cpu"),
                        "temperature": cell.get("temperature", 0.8),
                        "top_k": cell.get("top_k", 50),
                        "max_new_tokens": cell.get("max_new_tokens", 256),
                    },
                )
                logger.info(f"[加载] LTAI {cell_name} @ {ckpt_path or '(checkpoint待训练)'}")

            # ── 5. FlowyAIPC 牧马人引擎配置（推荐）────────────────────────────
            herdsman_cfg = load_model_config("herdsman") or {}
            if herdsman_cfg.get("enabled", False) or herdsman_cfg.get("base_url"):
                base_url = herdsman_cfg.get("base_url", "http://localhost:8080/v1")
                api_key = herdsman_cfg.get("api_key", "")
                for key, mc in (herdsman_cfg.get("models") or {}).items():
                    model_id = mc.get("model_id", f"herdsman_{key}")
                    if model_id in self.models:
                        continue
                    caps = [
                        getattr(ModelCapability, c.upper(), ModelCapability.CHAT)
                        for c in mc.get("capabilities", [])
                    ]
                    if not caps:
                        caps = [
                            ModelCapability.CHAT,
                            ModelCapability.CONTENT_GENERATION,
                            ModelCapability.CODE_GENERATION,
                            ModelCapability.REASONING,
                            ModelCapability.SUMMARIZATION,
                            ModelCapability.TRANSLATION,
                        ]
                    self.models[model_id] = ModelInfo(
                        model_id=model_id,
                        name=f"{mc.get('model_name', key)} (Herdsman)",
                        backend=ModelBackend.HERDSMAN,
                        capabilities=caps,
                        max_tokens=mc.get("max_tokens", 8192),
                        context_length=mc.get("context_length", 32768),
                        quality_score=mc.get("quality_score", 0.85),
                        speed_score=mc.get("speed_score", 0.9),
                        cost_score=mc.get("cost_score", 1.0),  # 本地运行，免费
                        privacy_score=1.0,  # 本地运行，隐私安全
                        is_available=True,
                        config={
                            "model": mc.get("model_name", key),
                            "base_url": base_url,
                            "api_key": api_key,
                            "timeout": mc.get("timeout", 60),
                        },
                    )
                    logger.info(f"[加载] FlowyAIPC Herdsman {mc.get('model_name', key)} @ {base_url}")

        except Exception as e:
            logger.error(f"从加密配置加载模型失败: {e}")

    # ------------------------------------------------------------------ #
    def _capability_score(self, model: ModelInfo, context_length: int = 0) -> float:
        """
        能力评分（0-1）
        质量(50%) + 成功率(30%) + 上下文余量(20%)
        """
        quality = model.quality_score
        success = model.success_rate
        if context_length > 0 and model.context_length > 0:
            ctx_ratio = model.context_length / context_length
            ctx_score = min(ctx_ratio / 2.0, 1.0)
        else:
            ctx_score = 1.0
        return quality * 0.5 + success * 0.3 + ctx_score * 0.2

    def _cost_score(self, model: ModelInfo) -> float:
        """
        成本评分（0-1，越高越便宜）
        直接使用 model.cost_score（1.0=免费, 0.0=极贵）
        """
        return model.cost_score

    def _latency_score(self, model: ModelInfo) -> float:
        """
        延迟评分（0-1，越高越快）
        预设速度(30%) + 历史响应时间(40%) + 当前负载(30%)
        """
        speed = model.speed_score
        rt = model.avg_response_time
        time_score = 1.0 / (1.0 + rt * 0.5)  # rt=0→1.0, rt=2→0.5, rt=10→0.09
        load = model.current_load
        load_score = 1.0 / (1.0 + load * 0.2)  # load=0→1.0, load=5→0.5
        return speed * 0.3 + time_score * 0.4 + load_score * 0.3

    def _combined_score(self, model: ModelInfo, context_length: int,
                       weights: RoutingWeights) -> float:
        """三维综合评分 = cap*Wc + cost*Wcost + latency*Wlat"""
        w = weights.normalize()
        return (self._capability_score(model, context_length) * w.capability
                + self._cost_score(model) * w.cost
                + self._latency_score(model) * w.latency)

    def route(self, capability: ModelCapability,
              strategy: RoutingStrategy = RoutingStrategy.AUTO,
              context_length: int = 0,
              exclude_models: List[str] = None,
              weights: RoutingWeights = None) -> Optional[ModelInfo]:
        """
        路由到最佳模型（三维评估）

        Args:
            capability: 需要的能力
            strategy: 路由策略
            context_length: 需要的上下文长度（0=不限制）
            exclude_models: 排除的模型ID列表
            weights: 自定义三维权重（仅BALANCED策略时使用）

        Returns:
            ModelInfo 最佳模型，如无则返回None
        """
        # 1. 确定策略
        if strategy == RoutingStrategy.AUTO:
            strategy = self.TASK_STRATEGY_MAP.get(capability, RoutingStrategy.BALANCED)

        # 2. 筛选候选模型
        exclude_set = set(exclude_models or [])
        candidates = [
            m for m in self.models.values()
            if capability in m.capabilities
            and m.is_available
            and m.model_id not in exclude_set
            and (context_length == 0 or m.can_handle_context(context_length))
        ]

        if not candidates:
            logger.warning(f"无可用模型支持 {capability.value}")
            return None

        # 3. 按策略评分排序
        if strategy == RoutingStrategy.QUALITY:
            candidates.sort(key=lambda m: self._capability_score(m, context_length), reverse=True)

        elif strategy == RoutingStrategy.SPEED:
            candidates.sort(key=lambda m: self._latency_score(m), reverse=True)

        elif strategy == RoutingStrategy.COST:
            candidates.sort(key=lambda m: self._cost_score(m), reverse=True)

        elif strategy == RoutingStrategy.PRIVACY:
            candidates.sort(key=lambda m: m.privacy_score, reverse=True)

        else:  # BALANCED
            w = (weights or self.default_weights)
            candidates.sort(key=lambda m: self._combined_score(m, context_length, w), reverse=True)

        # 4. 负载均衡：同分模型使用轮询（round-robin）
        #    找出所有与第一名同分的模型，按轮询索引选一个
        if candidates:
            w = (weights or self.default_weights).normalize()
            top_score = self._combined_score(candidates[0], context_length, w) if strategy == RoutingStrategy.BALANCED else None

            # 收集所有与最高分相同的模型
            if top_score is not None:
                tied = [m for m in candidates if abs(
                    self._combined_score(m, context_length, w) - top_score
                ) < 1e-6]
            else:
                # 非 BALANCED 策略：用实际排序 key 判断同分
                if strategy == RoutingStrategy.QUALITY:
                    top = self._capability_score(candidates[0], context_length)
                    tied = [m for m in candidates if abs(
                        self._capability_score(m, context_length) - top
                    ) < 1e-6]
                elif strategy == RoutingStrategy.SPEED:
                    top = self._latency_score(candidates[0])
                    tied = [m for m in candidates if abs(
                        self._latency_score(m) - top
                    ) < 1e-6]
                elif strategy == RoutingStrategy.COST:
                    top = self._cost_score(candidates[0])
                    tied = [m for m in candidates if abs(
                        self._cost_score(m) - top
                    ) < 1e-6]
                elif strategy == RoutingStrategy.PRIVACY:
                    top = candidates[0].privacy_score
                    tied = [m for m in candidates if abs(
                        m.privacy_score - top
                    ) < 1e-6]
                else:
                    tied = [candidates[0]]

            if len(tied) > 1:
                # 轮询选择
                cap_key = capability.value + "_" + strategy.value
                idx = self._rr_index.get(cap_key, 0)
                selected = tied[idx % len(tied)]
                self._rr_index[cap_key] = (idx + 1) % len(tied)
                logger.info(f"负载均衡: {len(tied)}个同分模型，轮询选择 {selected.name}")
            else:
                selected = candidates[0]
        else:
            return None

        # 5. 返回最佳模型
        self._call_count[selected.model_id] = self._call_count.get(selected.model_id, 0) + 1

        logger.info(f"模型路由: {capability.value} → {selected.name} (策略: {strategy.value})")
        return selected
    
    def route_with_fallback(self, capability: ModelCapability,
                           strategy: RoutingStrategy = RoutingStrategy.AUTO,
                           context_length: int = 0,
                           weights: RoutingWeights = None) -> List[ModelInfo]:
        """
        路由到模型列表（含fallback，按优先级排序）

        Args:
            capability: 需要的能力
            strategy: 路由策略
            context_length: 需要的上下文长度
            weights: 自定义三维权重（仅BALANCED策略时使用）

        Returns:
            按优先级排序的模型列表，第一个是最佳模型
        """
        # 1. 确定策略
        if strategy == RoutingStrategy.AUTO:
            strategy = self.TASK_STRATEGY_MAP.get(capability, RoutingStrategy.BALANCED)

        # 2. 筛选候选模型
        candidates = [
            m for m in self.models.values()
            if capability in m.capabilities
            and m.is_available
            and (context_length == 0 or m.can_handle_context(context_length))
        ]

        if not candidates:
            return []

        # 3. 按策略评分排序（与route()保持一致）
        if strategy == RoutingStrategy.QUALITY:
            candidates.sort(key=lambda m: self._capability_score(m, context_length), reverse=True)

        elif strategy == RoutingStrategy.SPEED:
            candidates.sort(key=lambda m: self._latency_score(m), reverse=True)

        elif strategy == RoutingStrategy.COST:
            candidates.sort(key=lambda m: self._cost_score(m), reverse=True)

        elif strategy == RoutingStrategy.PRIVACY:
            candidates.sort(key=lambda m: m.privacy_score, reverse=True)

        else:  # BALANCED
            w = (weights or self.default_weights)
            candidates.sort(key=lambda m: self._combined_score(m, context_length, w), reverse=True)

        return candidates
    
    # ------------------------------------------------------------------ #
    #  自适应路由方法  <<  智能任务分类 + 上下文感知 + 渐进式推理  >>
    # ------------------------------------------------------------------ #
    
    def analyze_task(self, prompt: str, context_messages: Optional[List[Dict[str, object]]] = None) -> Dict[str, object]:
        """
        分析任务并建议最优层级
        
        Args:
            prompt: 用户输入
            context_messages: 对话历史消息
            
        Returns:
            分析结果，包含建议的层级和置信度
        """
        result = {
            "task_analysis": None,
            "context_analysis": None,
            "suggested_tier": "L2",
            "confidence": 0.5,
            "reasoning": []
        }
        
        # 1. 任务分类分析
        if self.task_classifier:
            task_analysis = self.task_classifier.analyze(prompt)
            result["task_analysis"] = {
                "complexity": task_analysis.complexity.value,
                "task_type": task_analysis.task_type.value,
                "estimated_tokens": task_analysis.estimated_tokens,
                "confidence": task_analysis.confidence,
                "suggested_tier": task_analysis.suggested_tier,
            }
            result["reasoning"].append(f"任务复杂度: {task_analysis.complexity.value}")
        
        # 2. 上下文分析
        if self.context_router and context_messages:
            context_analysis = self.context_router.analyze_context(context_messages)
            result["context_analysis"] = {
                "total_tokens": context_analysis.total_tokens,
                "message_count": context_analysis.message_count,
                "conversation_state": context_analysis.conversation_state.value,
                "suggested_tier": context_analysis.required_tier,
                "confidence": context_analysis.confidence,
            }
            result["reasoning"].append(f"对话状态: {context_analysis.conversation_state.value}")
        
        # 3. 综合建议层级
        tiers = []
        if result["task_analysis"]:
            tiers.append(result["task_analysis"]["suggested_tier"])
        if result["context_analysis"]:
            tiers.append(result["context_analysis"]["suggested_tier"])
        
        if tiers:
            # 选择最高层级（更保守）
            tier_nums = [int(t[1:]) for t in tiers]
            max_tier_num = max(tier_nums)
            result["suggested_tier"] = f"L{max_tier_num}"
            
            # 计算综合置信度
            confidences = []
            if result["task_analysis"]:
                confidences.append(result["task_analysis"]["confidence"])
            if result["context_analysis"]:
                confidences.append(result["context_analysis"]["confidence"])
            result["confidence"] = sum(confidences) / len(confidences)
        
        logger.info(f"自适应路由分析完成: {result['suggested_tier']} (置信度: {result['confidence']:.2f})")
        return result
    
    def route_with_adaptive(self, prompt: str, 
                           context_messages: Optional[List[Dict[str, object]]] = None,
                           capability: ModelCapability = ModelCapability.CHAT) -> Optional[ModelInfo]:
        """
        使用自适应路由选择最佳模型
        
        Args:
            prompt: 用户输入
            context_messages: 对话历史消息
            capability: 需要的能力
            
        Returns:
            最佳模型，如果没有则返回 None
        """
        if not self.auto_tier_selection_enabled:
            # 如果禁用自适应路由，使用默认路由
            return self.route(capability)
        
        # 1. 分析任务和上下文
        analysis = self.analyze_task(prompt, context_messages)
        suggested_tier = analysis["suggested_tier"]
        
        # 2. 获取该层级的模型
        model_info = self.get_tier_model(suggested_tier)
        
        if model_info:
            logger.info(f"自适应路由: {prompt[:50]}... → {suggested_tier} → {model_info.name}")
            return model_info
        
        # 如果该层级没有模型，使用默认路由
        logger.warning(f"层级 {suggested_tier} 无可用模型，回退到默认路由")
        return self.route(capability)
    
    async def call_with_adaptive(self, prompt: str,
                                system_prompt: str = "",
                                context_messages: Optional[List[Dict[str, object]]] = None,
                                **kwargs) -> str:
        """
        使用自适应路由调用模型
        
        Args:
            prompt: 用户输入
            system_prompt: 系统提示
            context_messages: 对话历史消息
            
        Returns:
            模型响应
        """
        # 1. 检查缓存
        if self.inference_cache:
            cached_response = self.inference_cache.get(prompt, system_prompt)
            if cached_response:
                logger.debug("自适应路由命中缓存")
                return cached_response
        
        # 2. 使用自适应路由选择模型
        analysis = self.analyze_task(prompt, context_messages)
        suggested_tier = analysis["suggested_tier"]
        
        # 3. 如果启用渐进式推理
        if self.progressive_reasoning_enabled:
            try:
                from business.progressive_reasoning import ProgressiveReasoning
                progressive = ProgressiveReasoning(self)
                result = await progressive.run(
                    prompt=prompt,
                    start_tier=suggested_tier,
                    system_prompt=system_prompt,
                    **kwargs
                )
                
                # 缓存结果
                if self.inference_cache:
                    self.inference_cache.set(
                        prompt=prompt,
                        response=result.final_response,
                        system_prompt=system_prompt,
                        tier=result.final_tier,
                        task_type="chat"
                    )
                
                return result.final_response
            except ImportError as e:
                logger.warning(f"渐进式推理不可用: {e}")
        
        # 4. 使用常规调用
        model_info = self.get_tier_model(suggested_tier)
        if model_info:
            response = await self.call_model_async(
                capability=ModelCapability.CHAT,
                prompt=prompt,
                system_prompt=system_prompt,
                model_id=model_info.model_id,
                **kwargs
            )
            
            # 缓存结果
            if self.inference_cache:
                self.inference_cache.set(
                    prompt=prompt,
                    response=response,
                    system_prompt=system_prompt,
                    tier=suggested_tier,
                    task_type="chat"
                )
            
            return response
        
        # 5. 回退到默认调用
        return await self.call_model_async(
            capability=ModelCapability.CHAT,
            prompt=prompt,
            system_prompt=system_prompt,
            **kwargs
        )

    def explain_routing(self, capability: ModelCapability,
                        strategy: RoutingStrategy = RoutingStrategy.AUTO,
                        context_length: int = 0,
                        weights: RoutingWeights = None) -> dict:
        """
        解释路由决策（调试用）
        
        返回各候选模型的三维评分详情，方便理解为什么选某个模型。
        
        Returns:
            {
                "strategy": ...,
                "weights": {...},
                "candidates": [
                    {"model_id": ..., "capability": ..., "cost": ..., "latency": ..., "combined": ...},
                    ...
                ],
                "selected": ...
            }
        """
        # 1. 确定策略
        if strategy == RoutingStrategy.AUTO:
            strategy = self.TASK_STRATEGY_MAP.get(capability, RoutingStrategy.BALANCED)
        
        # 2. 筛选候选
        candidates = [
            m for m in self.models.values()
            if capability in m.capabilities
            and m.is_available
            and (context_length == 0 or m.can_handle_context(context_length))
        ]
        
        if not candidates:
            return {"error": f"无可用模型支持 {capability.value}"}
        
        # 3. 计算各维度评分
        w = (weights or self.default_weights).normalize()
        
        details = []
        for m in candidates:
            cap = self._capability_score(m, context_length)
            cost = self._cost_score(m)
            lat = self._latency_score(m)
            combined = cap * w.capability + cost * w.cost + lat * w.latency
            details.append({
                "model_id": m.model_id,
                "name": m.name,
                "capability": round(cap, 3),
                "cost": round(cost, 3),
                "latency": round(lat, 3),
                "combined": round(combined, 3),
                "quality_score": m.quality_score,
                "speed_score": m.speed_score,
                "cost_score": m.cost_score,
                "success_rate": round(m.success_rate, 3),
                "avg_response_time": round(m.avg_response_time, 3),
                "current_load": m.current_load,
            })
        
        # 按综合分排序
        details.sort(key=lambda x: x["combined"], reverse=True)
        
        return {
            "capability": capability.value,
            "strategy": strategy.value,
            "weights": w.to_dict(),
            "candidates": details,
            "selected": details[0]["model_id"] if details else None,
        }

    def _get_cache_key(self, model: ModelInfo, prompt: str, system_prompt: str = "") -> str:
        """生成缓存key"""
        content = f"{model.model_id}:{prompt}:{system_prompt}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _get_ttl_for_capability(self, capability: ModelCapability) -> int:
        """根据 capability 返回 TTL（秒）"""
        return self._ttl_map.get(capability, self._default_ttl)
    
    def _get_from_cache(self, cache_key: str, capability: ModelCapability = None) -> Optional[str]:
        """
        从缓存获取（LRU 行为）
        
        LRU：访问时移到末尾（最新位置）
        TTL：根据 capability 动态判断过期
        """
        if cache_key not in self._cache:
            return None
        
        # 检查 TTL（使用 capability 对应的 TTL）
        timestamp = self._cache_timestamps.get(cache_key, 0)
        ttl = self._default_ttl
        # 注意：capability 需要从外部传入，这里用默认 TTL
        if time.time() - timestamp > ttl:
            # 过期，删除
            del self._cache[cache_key]
            del self._cache_timestamps[cache_key]
            return None
        
        # LRU：访问时移到末尾（最新位置）
        value = self._cache.pop(cache_key)
        self._cache[cache_key] = value
        self._cache_timestamps.pop(cache_key)
        self._cache_timestamps[cache_key] = time.time()
        
        return value
    
    def _save_to_cache(self, cache_key: str, response: str):
        """
        保存到缓存（LRU 行为）
        
        LRU：新增时检查容量，删除最旧的（队首）
        """
        # 如果已存在，先删除（更新位置）
        if cache_key in self._cache:
            del self._cache[cache_key]
            del self._cache_timestamps[cache_key]
        
        # 新增到末尾（最新位置）
        self._cache[cache_key] = response
        self._cache_timestamps[cache_key] = time.time()
        
        # LRU 淘汰：如果超出容量，删除最旧的（队首）
        while len(self._cache) > self._cache_max_size:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            del self._cache_timestamps[oldest_key]
    
    async def call_model(self, capability: ModelCapability,
                        prompt: str,
                        system_prompt: str = "",
                        strategy: RoutingStrategy = RoutingStrategy.AUTO,
                        context_length: int = 0,
                        use_cache: bool = True,
                        model_id: str = "",  # 新增：直接指定模型ID
                        tier: Optional[ModelTier] = None,  # 新增：分层路由
                        expert_type: Optional[str] = None,  # 新增：专家类型
                        thinking_mode: Optional[str] = None,  # 新增：思考模式
                        rys_config: Optional[dict] = None,  # 新增：RYS层重复配置
                        verify: Optional[dict] = None,  # 新增：LLM-as-a-Verifier 验证配置
                        **kwargs) -> str:
        """
        调用模型（同步返回）
        
        Args:
            capability: 需要的能力
            prompt: 用户提示
            system_prompt: 系统提示
            strategy: 路由策略
            context_length: 需要的上下文长度
            use_cache: 是否使用缓存
            model_id: 直接指定模型ID（不走路由）
            tier: 分层路由（L0-L4，指定后优先使用分层路由）
        
        Returns:
            模型输出文本
        """
        # ── Opik 追踪初始化 ─────────────────────────────────────────
        _opik_trace = None
        _opik_start_time = time.time()
        _opik_input = {
            "capability": capability.value if capability else None,
            "prompt": prompt[:500],  # 只记录前500字符
            "system_prompt": system_prompt[:500],
            "strategy": strategy.value if strategy else None,
            "context_length": context_length,
            "model_id": model_id,
        }

        if OPIK_TRACER_AVAILABLE and is_opik_enabled():
            try:
                _opik_trace = start_trace(
                    name=f"call_model_{capability.value if capability else 'unknown'}",
                    trace_type="llm",
                    metadata={"function": "call_model"}
                )
            except Exception as e:
                logger.warning(f"Opik 追踪初始化失败: {e}")
        
        # ── 注入专家思考模式指令（动态版，无枚举） ─────────────────────────────
        if expert_type or thinking_mode:
            controller = _get_expert_thinking_controller()
            if controller:
                # 设置专家类型（按名称，自动扫描 .livingtree/skills/）
                if expert_type:
                    if not controller.set_expert_by_name(expert_type):
                        logger.warning(f"[思考模式] 设置专家失败: {expert_type}，将尝试自动匹配")

                # 设置思考模式（按名称）
                if thinking_mode:
                    if not controller.set_thinking_mode_by_name(thinking_mode):
                        logger.warning(f"[思考模式] 设置思考模式失败: {thinking_mode}")

                # 如果未指定专家，让控制器自动匹配（在注入时处理）
                # 增强 system_prompt
                system_prompt = controller.get_enhanced_system_prompt(system_prompt)
                config = controller.get_current_config()
                logger.info(f"[思考模式] 已注入: expert={config['expert_name']}, mode={config['thinking_mode']}")
        
        # ── RYS 层重复推理增强 ─────────────────────────────
        if rys_config:
            try:
                from business.rys_engine import (
                    RYSConfig, get_rys_engine, validate_rys_config
                )
                rc = RYSConfig.from_dict(rys_config) if isinstance(rys_config, dict) else rys_config
                # 获取当前模型名用于验证
                target_model = model_id or ""
                if target_model:
                    is_safe, reason = validate_rys_config(rc, target_model)
                    if not is_safe:
                        logger.warning(f"[RYS] 配置不安全: {reason}")
                    else:
                        logger.info(f"[RYS] 层重复配置: {rc.blocks}, 额外+{rc.total_extra_layers}层")
                        # TODO: 当 Ollama/llama.cpp 支持 --repeat-layers 后，
                        # 将 rys_config 注入到 Ollama options 中
                        # 当前记录配置供后续使用
                else:
                    logger.info(f"[RYS] 层重复配置已就绪（待模型确定后验证）")
            except ImportError as e:
                logger.warning(f"[RYS] 引擎导入失败: {e}")
            except Exception as e:
                logger.warning(f"[RYS] 配置处理异常: {e}")
        
        # ── LLM-as-a-Verifier 输出验证 ─────────────────────
        # verify 参数说明（dict）：
        #   "enabled": True,                          # 启用验证
        #   "n_candidates": 3,                        # Best-of-N 候选数
        #   "module": "universal",                    # 使用注册的评估标准
        #   "strategy": "round_robin",                # 选择策略
        #   "threshold": 10.0                         # 通过阈值
        # 当启用时，生成 N 个候选后通过 VerifierEngine 选最优。
        
        # 如果指定了 tier，使用分层路由
        if tier is not None:
            model = self.get_tier_model(tier)
            if not model:
                logger.error(f"分层路由未设置: {tier.value}")
                return ""
        elif model_id:
            # 如果指定了model_id，直接使用该模型
            if model_id not in self.models:
                logger.error(f"模型不存在: {model_id}")
                return ""
            model = self.models[model_id]
        else:
            # 路由到模型
            model = self.route(capability, strategy, context_length)
            if not model:
                return ""
        
        # 检查缓存（传入 capability 以支持 TTL 分层）
        if use_cache:
            cache_key = self._get_cache_key(model, prompt, system_prompt)
            cached = self._get_from_cache(cache_key, capability)
            if cached:
                logger.info(f"缓存命中: {model.name}")
                return cached
        
        # 调用模型
        model.current_load += 1
        start_time = time.time()
        success = False
        response = ""

        try:
            if model.backend == ModelBackend.MOCK:
                response = self._mock_response(prompt)
                success = True

            elif model.backend == ModelBackend.OLLAMA:
                response = await self._call_ollama(model, prompt, system_prompt)
                success = bool(response)

            elif model.backend == ModelBackend.OPENAI:
                response = await self._call_openai(model, prompt, system_prompt)
                success = bool(response)

            elif model.backend == ModelBackend.CUSTOM:
                handler = kwargs.get("handler")
                if handler and callable(handler):
                    response = await handler(prompt, system_prompt)
                    success = bool(response)

            elif model.backend == ModelBackend.LTAI:
                response = await self._call_ltai(model, prompt, system_prompt)
                success = bool(response)

            elif model.backend == ModelBackend.HERDSMAN:
                response = await self._call_openai(model, prompt, system_prompt)
                success = bool(response)

        except Exception as e:
            logger.error(f"模型调用异常: {e}")
            success = False

        finally:
            model.current_load -= 1
            response_time = time.time() - start_time
            model.update_stats(success, response_time)

        # 故障转移：主模型失败时，自动尝试 fallback 列表（排除已失败的主模型）
        if not success:
            logger.warning(f"主模型 {model.name} 调用失败，启动故障转移...")
            try:
                fallback_response = await self.call_model_with_fallback(
                    capability, prompt, system_prompt,
                    strategy, context_length,
                    exclude_model_ids=[model.model_id],
                    **kwargs
                )
                if fallback_response:
                    logger.info(f"故障转移成功，使用 fallback 模型")
                    return fallback_response
            except Exception as e:
                logger.error(f"故障转移异常: {e}")

        # 保存到缓存
        if success and use_cache:
            cache_key = self._get_cache_key(model, prompt, system_prompt)
            self._save_to_cache(cache_key, response)

        return response
    
    async def call_model_with_fallback(self, capability: ModelCapability,
                                      prompt: str,
                                      system_prompt: str = "",
                                      strategy: RoutingStrategy = RoutingStrategy.AUTO,
                                      context_length: int = 0,
                                      exclude_model_ids: List[str] = None,
                                      **kwargs) -> str:
        """
        调用模型（带fallback）

        如果最佳模型失败，自动尝试下一个

        Args:
            exclude_model_ids: 排除的模型ID列表（如已失败的模型）
        """
        models = self.route_with_fallback(capability, strategy, context_length)

        # 排除指定的模型（如已失败的）
        exclude_set = set(exclude_model_ids or [])
        if exclude_set:
            models = [m for m in models if m.model_id not in exclude_set]

        if not models:
            logger.error("Fallback: 排除后无可用模型")
            return ""

        for model in models:
            logger.info(f"尝试模型: {model.name}")
            
            model.current_load += 1
            start_time = time.time()
            success = False
            response = ""
            
            try:
                if model.backend == ModelBackend.OLLAMA:
                    response = await self._call_ollama(model, prompt, system_prompt)
                    success = bool(response)
                
                elif model.backend == ModelBackend.OPENAI:
                    response = await self._call_openai(model, prompt, system_prompt)
                    success = bool(response)
                
                elif model.backend == ModelBackend.CUSTOM:
                    handler = kwargs.get("handler")
                    if handler and callable(handler):
                        response = await handler(prompt, system_prompt)
                        success = bool(response)
                
                elif model.backend == ModelBackend.HERDSMAN:
                    response = await self._call_openai(model, prompt, system_prompt)
                    success = bool(response)
                
                if success:
                    logger.info(f"模型调用成功: {model.name}")
                    return response
                else:
                    logger.warning(f"模型调用失败: {model.name}, 尝试下一个")
            
            except Exception as e:
                logger.error(f"模型调用异常: {model.name}, 错误: {e}")
            
            finally:
                model.current_load -= 1
                response_time = time.time() - start_time
                model.update_stats(success, response_time)
        
        logger.error("所有模型都调用失败")
        return ""
    
    async def call_model_race(self, 
                              capability: ModelCapability,
                              prompt: str,
                              system_prompt: str = "",
                              strategy: RoutingStrategy = RoutingStrategy.AUTO,
                              context_length: int = 0,
                              top_n: int = 3,
                              timeout: float = 60.0,
                              **kwargs) -> str:
        """
        并发 Race 模式：同时调用多个模型，取第一个成功返回的
        
        Args:
            capability: 需要的能力
            prompt: 用户提示
            system_prompt: 系统提示
            strategy: 路由策略
            context_length: 需要的上下文长度
            top_n: 同时调用的模型数量（默认 3 个）
            timeout: 总超时时间（秒）
            **kwargs: 传递给模型调用的参数
        
        Returns:
            第一个成功模型的响应文本
        """
        # 1. 获取候选模型列表
        candidates = self.route_with_fallback(capability, strategy, context_length)
        if not candidates:
            logger.error("Race 模式：无可用模型")
            return ""
        
        # 2. 取前 top_n 个模型
        selected = candidates[:top_n]
        logger.info(f"Race 模式：同时调用 {len(selected)} 个模型")
        
        # 3. 为每个模型创建调用任务
        async def _race_call(model: ModelInfo) -> Tuple[ModelInfo, Optional[str], bool]:
            """单个模型的调用任务"""
            model.current_load += 1
            start_time = time.time()
            success = False
            response = ""
            
            try:
                if model.backend == ModelBackend.OLLAMA:
                    response = await self._call_ollama(model, prompt, system_prompt)
                    success = bool(response)
                
                elif model.backend == ModelBackend.OPENAI:
                    response = await self._call_openai(model, prompt, system_prompt)
                    success = bool(response)
                
                elif model.backend == ModelBackend.CUSTOM:
                    handler = kwargs.get("handler")
                    if handler and callable(handler):
                        response = await handler(prompt, system_prompt)
                        success = bool(response)
                
                elif model.backend == ModelBackend.HERDSMAN:
                    response = await self._call_openai(model, prompt, system_prompt)
                    success = bool(response)
            
            except Exception as e:
                logger.error(f"Race 调用异常 {model.name}: {e}")
            
            finally:
                model.current_load -= 1
                response_time = time.time() - start_time
                model.update_stats(success, response_time)
            
            return model, response, success
        
        # 4. 创建所有任务
        tasks = []
        for model in selected:
            task = asyncio.create_task(_race_call(model))
            tasks.append(task)
        
        # 5. 等待第一个成功返回
        try:
            done = set()
            pending = set(tasks)
            
            while pending:
                # 等待任意一个任务完成
                done_part, pending = await asyncio.wait(
                    pending, 
                    timeout=timeout / len(tasks),  # 每个任务分配相同时间
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # 检查完成的任务
                for task in done_part:
                    model, response, success = task.result()
                    
                    if success:
                        # 成功！取消其他任务
                        for t in pending:
                            t.cancel()
                        logger.info(f"Race 获胜者: {model.name}")
                        
                        # 保存到缓存
                        cache_key = self._get_cache_key(model, prompt, system_prompt)
                        self._save_to_cache(cache_key, response)
                        
                        return response
                
                # 如果所有任务都失败了
                done.update(done_part)
                if len(done) == len(tasks):
                    logger.error("Race 模式：所有模型都失败")
                    return ""
        
        except asyncio.TimeoutError:
            logger.error(f"Race 模式：超时（{timeout}秒）")
            for task in tasks:
                task.cancel()
            return ""
        
        except Exception as e:
            logger.error(f"Race 模式异常: {e}")
            for task in tasks:
                task.cancel()
            return ""
    
    async def call_model_stream(self, capability: ModelCapability,
                                prompt: str,
                                system_prompt: str = "",
                                strategy: RoutingStrategy = RoutingStrategy.AUTO,
                                context_length: int = 0,
                                **kwargs) -> AsyncIterator[str]:
        """
        调用模型（流式返回）
        
        Yields:
            文本片段
        """
        model = self.route(capability, strategy, context_length)
        if not model:
            yield ""
            return
        
        model.current_load += 1
        start_time = time.time()
        success = False
        
        try:
            if model.backend == ModelBackend.OLLAMA:
                async for chunk in self._call_ollama_stream(model, prompt, system_prompt):
                    yield chunk
                success = True
            
            elif model.backend == ModelBackend.OPENAI:
                async for chunk in self._call_openai_stream(model, prompt, system_prompt):
                    yield chunk
                success = True

            elif model.backend == ModelBackend.LTAI:
                async for chunk in self._call_ltai_stream(model, prompt, system_prompt):
                    yield chunk
                success = True

            elif model.backend == ModelBackend.HERDSMAN:
                async for chunk in self._call_openai_stream(model, prompt, system_prompt):
                    yield chunk
                success = True

        except Exception as e:
            logger.error(f"流式调用异常: {e}")
        
        finally:
            model.current_load -= 1
            response_time = time.time() - start_time
            model.update_stats(success, response_time)

            # ── Opik 追踪记录 ─────────────────────────────────
            if _opik_trace is not None:
                try:
                    _opik_end_time = time.time()
                    _opik_latency = _opik_end_time - _opik_start_time

                    _opik_output = {
                        "response": response[:1000] if response else None,  # 只记录前1000字符
                        "latency": _opik_latency,
                        "success": success,
                        "model_name": model.name if 'model' in locals() else None,
                        "backend": model.backend.value if 'model' in locals() else None,
                    }

                    log_trace(
                        _opik_trace,
                        input_data=_opik_input,
                        output_data=_opik_output,
                        metadata={
                            "latency": _opik_latency,
                            "success": success,
                            "model": model.name if 'model' in locals() else None,
                        }
                    )
                except Exception as e:
                    logger.warning(f"Opik 追踪记录失败: {e}")
    
    # ============= 后端调用实现 =============
    
    async def _call_ollama(self, model: ModelInfo, prompt: str,
                           system_prompt: str = "",
                           keep_alive: Optional[int] = None) -> str:
        """调用 Ollama 模型（同步）
        
        Args:
            keep_alive: 模型保持加载时间（秒）
                -1=永久, 0=立即卸载, 60=60秒
                默认从 model.config["keep_alive"] 读取，内置模型默认 -1
        """
        try:
            import aiohttp
            url = model.config.get("url", "http://localhost:11434")
            model_name = model.config.get("model", "qwen2.5")
            
            # keep_alive 参数（默认 -1 = 永久保持）
            if keep_alive is None:
                keep_alive = model.config.get("keep_alive", -1)
            
            payload = {
                "model": model_name,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False,
                "keep_alive": keep_alive,
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{url}/api/generate", json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("response", "")
                    else:
                        logger.error(f"Ollama 调用失败: {resp.status}")
                        return ""
        except Exception as e:
            logger.error(f"Ollama 调用异常: {e}")
            return ""
    
    async def _call_ollama_stream(self, model: ModelInfo, prompt: str,
                                  system_prompt: str = "",
                                  keep_alive: Optional[int] = None) -> AsyncIterator[str]:
        """调用 Ollama 模型（流式）
        
        Args:
            keep_alive: 模型保持加载时间（秒）
                -1=永久, 0=立即卸载, 60=60秒
                默认从 model.config["keep_alive"] 读取，内置模型默认 -1
        """
        try:
            import aiohttp
            url = model.config.get("url", "http://localhost:11434")
            model_name = model.config.get("model", "qwen2.5")
            
            # keep_alive 参数（默认 -1 = 永久保持）
            if keep_alive is None:
                keep_alive = model.config.get("keep_alive", -1)
            
            payload = {
                "model": model_name,
                "prompt": prompt,
                "system": system_prompt,
                "stream": True,
                "keep_alive": keep_alive,
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{url}/api/generate", json=payload) as resp:
                    if resp.status == 200:
                        async for line in resp.content:
                            if line:
                                try:
                                    data = json.loads(line)
                                    if "response" in data:
                                        yield data["response"]
                                except:
                                    pass
        
        except Exception as e:
            logger.error(f"Ollama 流式调用异常: {e}")
    
    async def _call_openai(self, model: ModelInfo, prompt: str,
                           system_prompt: str = "") -> str:
        """调用 OpenAI API 或 OpenAI 兼容端点（使用 requests 替代 openai SDK）"""
        try:
            import requests
            import json
            
            model_name = model.config.get("model", "gpt-3.5-turbo")
            base_url = model.config.get("base_url")  # 支持自定义端点
            api_key = model.config.get("api_key", "dummy")  # 支持自定义key
            timeout = model.config.get("timeout", 60)  # 支持自定义超时（秒）
            
            # 构建 URL（处理 base_url 可能包含 /v1 或不包含的情况）
            if base_url:
                if base_url.rstrip('/').endswith('/v1'):
                    url = f"{base_url.rstrip('/')}/chat/completions"
                else:
                    url = f"{base_url.rstrip('/')}/v1/chat/completions"
            else:
                url = "https://api.openai.com/v1/chat/completions"
            
            # 构建请求头
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            
            # 构建请求体
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "stream": False
            }
            
            # 发送请求
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
            response.raise_for_status()
            
            result = response.json()
            
            # 提取回复文本（兼容 thinking 模型，如 DeepSeek-V4-Pro）
            if "choices" in result and len(result["choices"]) > 0:
                message = result["choices"][0]["message"]
                content = message.get("content", "")
                reasoning = message.get("reasoning_content", "")  # DeepSeek thinking 字段
                
                # 如果有 thinking 内容，拼接到回复中
                if reasoning:
                    # 格式：用 <think> 标签包裹 thinking 内容
                    thinking_text = f"<think>\n{reasoning}\n</think>\n\n"
                    return thinking_text + (content or "")
                else:
                    return content or ""
            else:
                logger.error(f"OpenAI 响应格式错误: {result}")
                return ""
                
        except Exception as e:
            logger.error(f"OpenAI 调用异常: {e}")
            if 'response' in locals():
                logger.error(f"响应内容: {response.text}")
            return ""
    
    async def _call_openai_stream(self, model: ModelInfo, prompt: str,
                                  system_prompt: str = "") -> AsyncIterator[str]:
        """调用 OpenAI API 或兼容端点（流式，使用 requests 替代 openai SDK）"""
        try:
            import requests
            import json
            
            model_name = model.config.get("model", "gpt-3.5-turbo")
            base_url = model.config.get("base_url")
            api_key = model.config.get("api_key", "dummy")
            timeout = model.config.get("timeout", 60)  # 支持自定义超时
            
            # 构建 URL（处理 base_url 可能包含 /v1 或不包含的情况）
            if base_url:
                if base_url.rstrip('/').endswith('/v1'):
                    url = f"{base_url.rstrip('/')}/chat/completions"
                else:
                    url = f"{base_url.rstrip('/')}/v1/chat/completions"
            else:
                url = "https://api.openai.com/v1/chat/completions"
            
            # 构建请求头
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            
            # 构建请求体（流式）
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "stream": True
            }
            
            # 发送流式请求
            with requests.post(url, headers=headers, json=payload, stream=True, timeout=timeout) as response:
                response.raise_for_status()
                
                # 解析 SSE 流（兼容 thinking 模型，如 DeepSeek-V4-Pro）
                in_thinking = False
                thinking_ended = False
                
                for line in response.iter_lines():
                    if line:
                        # line 可能是 bytes
                        if isinstance(line, bytes):
                            line = line.decode('utf-8')
                        line = line.strip()
                        if line.startswith('data: '):
                            data = line[6:]
                            if data == '[DONE]':
                                # 确保 thinking 标签闭合
                                if in_thinking:
                                    yield "\n</think>"
                                break
                            try:
                                chunk = json.loads(data)
                                if "choices" in chunk and len(chunk["choices"]) > 0:
                                    delta = chunk["choices"][0].get("delta", {})
                                    
                                    # 处理 thinking 内容（DeepSeek reasoning_content）
                                    reasoning = delta.get("reasoning_content", "")
                                    if reasoning:
                                        if not in_thinking:
                                            in_thinking = True
                                            thinking_ended = False
                                            yield "<think>\n"
                                        yield reasoning
                                    
                                    # 处理正式回复内容
                                    content = delta.get("content", "")
                                    if content:
                                        if in_thinking and not thinking_ended:
                                            thinking_ended = True
                                            yield "\n</think>\n\n"
                                            in_thinking = False
                                        yield content
                            
                            except json.JSONDecodeError:
                                continue
                
                # 确保 thinking 标签闭合（防止未闭合）
                if in_thinking:
                    yield "\n</think>"
        
        except Exception as e:
            logger.error(f"OpenAI 流式调用异常: {e}")
            if 'response' in locals():
                logger.error(f"响应内容: {response.text}")
            yield ""  # 流式函数需要yield

    # ── LTAI 后端调用（LTAI 细胞）────────────────────────────────────

    async def _call_ltai(self, model: ModelInfo, prompt: str,
                              system_prompt: str = "") -> str:
        """
        调用 LTAI 模型（同步）
        通过 LTAIAdapter 加载本地 nanoGPT checkpoint 做推理。
        """
        try:
            from business.llmcore.adapter import LTAIAdapter, ChatMessage

            cell_name = model.config.get("cell_name", "table_cell")
            checkpoint_path = model.config.get("checkpoint_path", "")
            device = model.config.get("device", "cpu")
            temperature = model.config.get("temperature", 0.8)
            top_k = model.config.get("top_k", 50)
            max_new_tokens = model.config.get("max_new_tokens", 256)

            adapter = LTAIAdapter(
                cell_name=cell_name,
                checkpoint_path=checkpoint_path,
                device=device,
            )

            messages = []
            if system_prompt:
                messages.append(ChatMessage(role="system", content=system_prompt))
            messages.append(ChatMessage(role="user", content=prompt))

            # 非流式收集完整结果
            full_response = []
            import asyncio
            loop = asyncio.get_event_loop()
            # chat_stream 是同步生成器，直接迭代
            for chunk in adapter.chat_stream(
                [{"role": m.role, "content": m.content} for m in messages],
                temperature=temperature,
                top_k=top_k,
                max_new_tokens=max_new_tokens,
            ):
                if chunk.done:
                    break
                full_response.append(chunk.delta)

            return "".join(full_response)

        except Exception as e:
            logger.error(f"LTAI 调用异常: {e}")
            return ""

    async def _call_ltai_stream(self, model: ModelInfo, prompt: str,
                                     system_prompt: str = "") -> AsyncIterator[str]:
        """
        调用 LTAI 模型（流式）
        通过 LTAIAdapter.chat_stream() 流式 yield 文本片段。
        """
        try:
            from business.llmcore.adapter import LTAIAdapter

            cell_name = model.config.get("cell_name", "table_cell")
            checkpoint_path = model.config.get("checkpoint_path", "")
            device = model.config.get("device", "cpu")
            temperature = model.config.get("temperature", 0.8)
            top_k = model.config.get("top_k", 50)
            max_new_tokens = model.config.get("max_new_tokens", 256)

            adapter = LTAIAdapter(
                cell_name=cell_name,
                checkpoint_path=checkpoint_path,
                device=device,
            )

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            import asyncio
            loop = asyncio.get_event_loop()
            for chunk in adapter.chat_stream(
                messages,
                temperature=temperature,
                top_k=top_k,
                max_new_tokens=max_new_tokens,
            ):
                if chunk.done:
                    break
                yield chunk.delta

        except Exception as e:
            logger.error(f"LTAI 流式调用异常: {e}")

    @staticmethod
    def _mock_response(prompt: str) -> str:
        """模拟模型响应（测试用）"""
        return f"[模拟响应] 基于提示生成的内容: {prompt[:50]}..."
    
    def list_models(self, capability: ModelCapability = None) -> List[dict]:
        """列出可用模型"""
        results = []
        for m in self.models.values():
            if capability and capability not in m.capabilities:
                continue
            results.append(m.to_dict())
        return results
    
    def get_stats(self) -> dict:
        """获取路由统计"""
        return {
            "total_models": len(self.models),
            "available_models": sum(1 for m in self.models.values() if m.is_available),
            "call_counts": dict(self._call_count),
            "cache_size": len(self._cache),
        }
    
    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        self._cache_timestamps.clear()
        logger.info("缓存已清空")
    
    # ============= 模型预热 =============
    
    async def warm_up(self, model_id: str = "") -> bool:
        """
        预热模型（加载到 GPU/内存）
        
        Args:
            model_id: 模型ID，空字符串=预热所有 Ollama 模型
        
        Returns:
            是否成功
        """
        if model_id:
            # 预热单个模型
            if model_id not in self.models:
                logger.error(f"模型不存在: {model_id}")
                return False
            
            model = self.models[model_id]
            if model.backend != ModelBackend.OLLAMA:
                logger.warning(f"模型 {model_id} 不是 Ollama 后端，无需预热")
                return True
            
            try:
                # 发送一个简单请求来预热（keep_alive=-1 永久保持）
                response = await self._call_ollama(
                    model, 
                    prompt="hi", 
                    system_prompt="",
                    keep_alive=-1
                )
                logger.info(f"模型预热成功: {model.name}")
                return bool(response)
            
            except Exception as e:
                logger.error(f"模型预热失败 {model.name}: {e}")
                return False
        
        else:
            # 预热所有 Ollama 模型
            results = []
            for model in self.models.values():
                if model.backend == ModelBackend.OLLAMA:
                    success = await self.warm_up(model.model_id)
                    results.append(success)
            
            return all(results) if results else False
    
    def start_keepalive(self, interval: int = 300):
        """
        启动后台心跳任务（防止模型被卸载）
        
        Args:
            interval: 心跳间隔（秒），默认 300 秒（5 分钟）
        """
        import threading
        
        def _keepalive_loop():
            """心跳循环"""
            import asyncio
            
            # 创建新的事件循环（因为在新线程中）
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            while True:
                try:
                    # 发送心跳请求（空 prompt，keep_alive=-1）
                    for model in self.models.values():
                        if model.backend == ModelBackend.OLLAMA:
                            try:
                                loop.run_until_complete(
                                    self._call_ollama(
                                        model,
                                        prompt="",
                                        system_prompt="",
                                        keep_alive=-1
                                    )
                                )
                            except Exception as e:
                                logger.warning(f"心跳失败 {model.name}: {e}")
                    
                    # 等待 interval 秒
                    time.sleep(interval)
                
                except Exception as e:
                    logger.error(f"心跳循环异常: {e}")
                    time.sleep(60)  # 异常后等待 1 分钟再试
        
        # 启动后台线程
        thread = threading.Thread(target=_keepalive_loop, daemon=True)
        thread.start()
        logger.info(f"心跳任务已启动（间隔 {interval} 秒）")
        return thread
    
    def stop_keepalive(self):
        """停止心跳任务（通过设置标志位）"""
        # 注意：当前实现使用 daemon=True 线程，程序退出时自动停止
        # 如果需要手动停止，需要添加标志位
        logger.info("心跳任务将在程序退出时自动停止")

    # ============= 向量化接口 =============

    async def embeddings(
        self,
        texts: Union[str, List[str]],
        model_id: str = "",
        capability: ModelCapability = ModelCapability.EMBEDDING,
    ) -> List[List[float]]:
        """
        文本向量化（异步）

        Args:
            texts: 单个文本或文本列表
            model_id: 直接指定模型 ID（可选，不走路由）
            capability: 能力类型（默认 EMBEDDING）

        Returns:
            向量列表（每个文本对应一个向量）
        """
        # 标准化为列表
        if isinstance(texts, str):
            texts = [texts]

        # 路由到支持 EMBEDDING 的模型
        if model_id:
            if model_id not in self.models:
                logger.error(f"模型不存在: {model_id}")
                return []
            model = self.models[model_id]
        else:
            model = self.route(capability, RoutingStrategy.AUTO)
            if not model:
                logger.error("无可用模型支持 embedding")
                return []

        # 根据后端调用不同 API
        try:
            if model.backend == ModelBackend.OLLAMA:
                return await self._ollama_embeddings(model, texts)
            elif model.backend == ModelBackend.OPENAI:
                return await self._openai_embeddings(model, texts)
            else:
                logger.error(f"不支持的后端用于 embedding: {model.backend}")
                return []
        except Exception as e:
            logger.error(f"embedding 调用异常: {e}")
            return []

    async def _ollama_embeddings(
        self, model: ModelInfo, texts: List[str]
    ) -> List[List[float]]:
        """Ollama 向量化（/api/embeddings）"""
        import aiohttp

        url = model.config.get("url", "http://localhost:11434")
        model_name = model.config.get("model", "qwen2.5")

        results = []
        for text in texts:
            payload = {"model": model_name, "prompt": text}
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{url}/api/embeddings", json=payload
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        embedding = data.get("embedding", [])
                        results.append(embedding)
                    else:
                        logger.warning(f"Ollama embeddings 失败: {resp.status}")
                        results.append([])
        return results

    async def _openai_embeddings(
        self, model: ModelInfo, texts: List[str]
    ) -> List[List[float]]:
        """OpenAI 兼容向量化（/v1/embeddings）"""
        try:
            import openai

            base_url = model.config.get("base_url")
            api_key = model.config.get("api_key", "dummy")
            model_name = model.config.get("model", "text-embedding-ada-002")
            timeout = model.config.get("timeout", 60)

            client = openai.AsyncOpenAI(
                base_url=base_url if base_url else None,
                api_key=api_key,
                timeout=timeout,
            )

            response = await client.embeddings.create(
                model=model_name,
                input=texts,
            )
            return [item.embedding for item in response.data]
        except ImportError:
            logger.error("openai 包未安装，无法使用 OpenAI embeddings")
            return []
        except Exception as e:
            logger.error(f"OpenAI embeddings 调用异常: {e}")
            return []

    # ============= 心跳检测 =============

    def start_heartbeat(self, interval: int = 30):
        """
        启动心跳检测（后台线程）
        
        Args:
            interval: 心跳间隔（秒），默认 30 秒
        """
        if self._heartbeat_running:
            logger.warning("心跳检测已在运行")
            return
        
        self._heartbeat_interval = interval
        self._heartbeat_stop_event.clear()
        self._heartbeat_running = True
        
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True,
            name="ModelRouter-Heartbeat"
        )
        self._heartbeat_thread.start()
        logger.info(f"🌐 心跳检测已启动（间隔: {interval}秒）")

    def stop_heartbeat(self):
        """停止心跳检测"""
        if not self._heartbeat_running:
            return
        
        self._heartbeat_stop_event.set()
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=5)
        self._heartbeat_running = False
        logger.info("⏹️ 心跳检测已停止")

    def _heartbeat_loop(self):
        """
        心跳检测循环（后台线程运行）
        定期 ping 所有 Ollama 服务器，更新模型可用性
        """
        logger.info("🔄 心跳检测线程已启动")
        
        while not self._heartbeat_stop_event.is_set():
            try:
                self._do_heartbeat()
            except Exception as e:
                logger.error(f"心跳检测异常: {e}")
            
            # 等待下一个周期
            self._heartbeat_stop_event.wait(self._heartbeat_interval)
        
        logger.info("🔄 心跳检测线程已退出")

    def _do_heartbeat(self):
        """
        执行一次心跳检测
        1. 收集所有唯一的 Ollama 服务器地址
        2. Ping 每个地址
        3. 根据结果更新模型的 is_available
        """
        # 1. 收集所有唯一的 Ollama 服务器地址
        server_urls = set()
        model_server_map = {}  # {url: [model_id, ...]}
        
        for model_id, model_info in self.models.items():
            if model_info.backend == ModelBackend.OLLAMA:
                url = model_info.config.get("url", "")
                if url:
                    server_urls.add(url)
                    if url not in model_server_map:
                        model_server_map[url] = []
                    model_server_map[url].append(model_id)
        
        if not server_urls:
            return
        
        # 2. Ping 每个服务器
        for url in server_urls:
            is_alive = self._ping_ollama_server(url)
            
            # 3. 更新该服务器上所有模型的 is_available
            model_ids = model_server_map.get(url, [])
            for model_id in model_ids:
                self.models[model_id].is_available = is_alive
            
            status = "✅ 可用" if is_alive else "❌ 不可用"
            logger.debug(f"心跳检测: {url} → {status}")

    def _ping_ollama_server(self, url: str) -> bool:
        """
        Ping 单个 Ollama 服务器
        
        Args:
            url: Ollama 服务器地址（如 http://localhost:11434）
            
        Returns:
            是否可用
        """
        try:
            # 使用 /api/tags 端点检测（不需要模型名）
            test_url = f"{url.rstrip('/')}/api/tags"
            response = requests.get(test_url, timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"Ping Ollama 服务器失败: {url}, 错误: {e}")
            return False

    def get_server_status(self) -> dict:
        """
        获取所有服务器状态（用于 UI 显示）
        
        Returns:
            {url: {"available": bool, "models": [model_id, ...], "priority": int}}
        """
        status = {}
        
        for model_id, model_info in self.models.items():
            if model_info.backend != ModelBackend.OLLAMA:
                continue
            
            url = model_info.config.get("url", "")
            priority = model_info.config.get("priority", 999)
            
            if url not in status:
                status[url] = {
                    "available": model_info.is_available,
                    "models": [],
                    "priority": priority,
                }
            else:
                # 如果任一模型可用，则服务器可用
                if model_info.is_available:
                    status[url]["available"] = True
            
            status[url]["models"].append(model_id)
        
        return status

    # ============= 健康检查机制 =============

    def start_health_check(self, interval: int = 60):
        """
        启动健康检查（后台线程）
        
        Args:
            interval: 健康检查间隔（秒），默认 60 秒
        
        健康检查功能：
        - 自动探测后端可用性（Ollama /api/ps、DeepSeek /health）
        - 动态更新实例健康状态
        - 支持配置健康检查间隔
        """
        if self._health_check_running:
            logger.warning("健康检查已在运行")
            return
        
        self._health_check_interval = interval
        self._health_check_stop_event.clear()
        self._health_check_running = True
        
        self._health_check_thread = threading.Thread(
            target=self._health_check_loop,
            daemon=True,
            name="ModelRouter-HealthCheck"
        )
        self._health_check_thread.start()
        logger.info(f"🏥 健康检查已启动（间隔: {interval}秒）")

    def stop_health_check(self):
        """停止健康检查"""
        if not self._health_check_running:
            return
        
        self._health_check_stop_event.set()
        if self._health_check_thread and self._health_check_thread.is_alive():
            self._health_check_thread.join(timeout=5)
        self._health_check_running = False
        logger.info("⏹️ 健康检查已停止")

    def _health_check_loop(self):
        """
        健康检查循环（后台线程运行）
        定期检查所有后端服务的健康状态
        """
        logger.info("🔄 健康检查线程已启动")
        
        while not self._health_check_stop_event.is_set():
            try:
                self._do_health_check()
            except Exception as e:
                logger.error(f"健康检查异常: {e}")
            
            # 等待下一个周期
            self._health_check_stop_event.wait(self._health_check_interval)
        
        logger.info("🔄 健康检查线程已退出")

    def _do_health_check(self):
        """
        执行一次完整的健康检查
        1. 检查所有 Ollama 后端（/api/ps）
        2. 检查所有 OpenAI/DeepSeek 后端（/health 或 /v1/models）
        3. 更新模型的健康状态
        """
        # 检查 Ollama 后端
        self._check_ollama_backends()
        
        # 检查 OpenAI/DeepSeek 后端
        self._check_openai_backends()

    def _check_ollama_backends(self):
        """检查所有 Ollama 后端健康状态"""
        server_urls = set()
        model_server_map = {}
        
        for model_id, model_info in self.models.items():
            if model_info.backend == ModelBackend.OLLAMA:
                url = model_info.config.get("url", "")
                if url:
                    server_urls.add(url)
                    if url not in model_server_map:
                        model_server_map[url] = []
                    model_server_map[url].append(model_id)
        
        for url in server_urls:
            health_data = self._check_ollama_health(url)
            self._backend_health[url] = health_data
            
            # 更新模型可用性
            for model_id in model_server_map.get(url, []):
                self.models[model_id].is_available = health_data.get("status") == "healthy"
            
            if self._log_level == LogLevel.DEBUG:
                logger.debug(f"Ollama 健康检查: {url} → {health_data.get('status')}")

    def _check_ollama_health(self, url: str) -> dict:
        """
        检查单个 Ollama 后端健康状态
        
        Args:
            url: Ollama 服务器地址
        
        Returns:
            {"status": "healthy"/"unhealthy"/"unknown", "last_check": timestamp, "models": [...], "message": "..."}
        """
        try:
            import aiohttp
            import asyncio
            
            async def _check():
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                    # 使用 /api/ps 端点检测（返回已加载的模型列表）
                    ps_url = f"{url.rstrip('/')}/api/ps"
                    async with session.get(ps_url) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            loaded_models = [m.get("name", "") for m in data.get("models", [])]
                            return {
                                "status": "healthy",
                                "last_check": time.time(),
                                "models": loaded_models,
                                "message": f"Ollama 服务正常，已加载 {len(loaded_models)} 个模型",
                                "backend_type": "ollama",
                                "url": url
                            }
                        else:
                            return {
                                "status": "unhealthy",
                                "last_check": time.time(),
                                "models": [],
                                "message": f"HTTP 状态码: {resp.status}",
                                "backend_type": "ollama",
                                "url": url
                            }
            
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(_check())
            loop.close()
            return result
        
        except Exception as e:
            return {
                "status": "unhealthy",
                "last_check": time.time(),
                "models": [],
                "message": str(e),
                "backend_type": "ollama",
                "url": url
            }

    def _check_openai_backends(self):
        """检查所有 OpenAI/DeepSeek 后端健康状态"""
        server_urls = set()
        model_server_map = {}
        
        for model_id, model_info in self.models.items():
            if model_info.backend == ModelBackend.OPENAI:
                url = model_info.config.get("base_url", "")
                if url:
                    server_urls.add(url)
                    if url not in model_server_map:
                        model_server_map[url] = []
                    model_server_map[url].append(model_id)
        
        for url in server_urls:
            health_data = self._check_openai_health(url)
            self._backend_health[url] = health_data
            
            # 更新模型可用性
            for model_id in model_server_map.get(url, []):
                self.models[model_id].is_available = health_data.get("status") == "healthy"
            
            if self._log_level == LogLevel.DEBUG:
                logger.debug(f"OpenAI/DeepSeek 健康检查: {url} → {health_data.get('status')}")

    def _check_openai_health(self, url: str) -> dict:
        """
        检查单个 OpenAI/DeepSeek 后端健康状态
        
        Args:
            url: 后端服务器地址
        
        Returns:
            {"status": "healthy"/"unhealthy"/"unknown", "last_check": timestamp, "message": "..."}
        """
        try:
            # 尝试多个健康检查端点
            endpoints = [
                "/health",
                "/v1/models",
                "/api/models"
            ]
            
            import requests
            
            for endpoint in endpoints:
                try:
                    check_url = f"{url.rstrip('/')}{endpoint}"
                    response = requests.get(check_url, timeout=10)
                    
                    if response.status_code == 200:
                        try:
                            data = response.json()
                            model_count = len(data.get("data", [])) if isinstance(data, dict) else 0
                            return {
                                "status": "healthy",
                                "last_check": time.time(),
                                "models": data.get("data", [])[:3],  # 返回前3个模型
                                "message": f"服务正常，可用模型: {model_count}",
                                "backend_type": "openai",
                                "url": url
                            }
                        except:
                            return {
                                "status": "healthy",
                                "last_check": time.time(),
                                "models": [],
                                "message": "服务正常（非JSON响应）",
                                "backend_type": "openai",
                                "url": url
                            }
                except Exception:
                    continue
            
            return {
                "status": "unhealthy",
                "last_check": time.time(),
                "models": [],
                "message": "所有端点均不可达",
                "backend_type": "openai",
                "url": url
            }
        
        except Exception as e:
            return {
                "status": "unhealthy",
                "last_check": time.time(),
                "models": [],
                "message": str(e),
                "backend_type": "openai",
                "url": url
            }

    def get_health_summary(self) -> dict:
        """
        获取健康状态摘要
        
        Returns:
            {
                "overall": "healthy"/"degraded"/"unhealthy",
                "backends": {...},
                "available_models": int,
                "total_models": int,
                "last_check": timestamp
            }
        """
        total_models = len(self.models)
        available_models = sum(1 for m in self.models.values() if m.is_available)
        
        # 判断整体状态
        if available_models == 0:
            overall_status = "unhealthy"
        elif available_models == total_models:
            overall_status = "healthy"
        else:
            overall_status = "degraded"
        
        return {
            "overall": overall_status,
            "backends": self._backend_health,
            "available_models": available_models,
            "total_models": total_models,
            "last_check": time.time()
        }

    def set_health_check_interval(self, interval: int):
        """
        设置健康检查间隔
        
        Args:
            interval: 间隔时间（秒）
        """
        self._health_check_interval = interval
        logger.info(f"健康检查间隔已设置为 {interval} 秒")

    # ============= 日志级别配置 =============

    def set_log_level(self, level: Union[str, LogLevel]):
        """
        设置日志级别
        
        Args:
            level: 日志级别（debug/info/warn/error 或 LogLevel 枚举）
        """
        if isinstance(level, str):
            try:
                self._log_level = LogLevel(level.lower())
            except ValueError:
                logger.warning(f"无效的日志级别: {level}，使用默认值 INFO")
                self._log_level = LogLevel.INFO
        elif isinstance(level, LogLevel):
            self._log_level = level
        
        # 设置 logger 级别
        logger_level = {
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.WARN: logging.WARNING,
            LogLevel.ERROR: logging.ERROR
        }.get(self._log_level, logging.INFO)
        
        logging.getLogger(__name__).setLevel(logger_level)
        logger.info(f"日志级别已设置为: {self._log_level.value}")

    def get_log_level(self) -> LogLevel:
        """获取当前日志级别"""
        return self._log_level

    def _log_request(self, model_name: str, capability: ModelCapability, 
                    success: bool, response_time: float):
        """
        记录请求日志
        
        Args:
            model_name: 模型名称
            capability: 能力类型
            success: 是否成功
            response_time: 响应时间（秒）
        """
        log_entry = {
            "timestamp": time.time(),
            "model_name": model_name,
            "capability": capability.value if capability else None,
            "success": success,
            "response_time": response_time,
            "call_count": self._call_count.get(model_name, 0)
        }
        
        # 添加到日志列表
        self._request_logs.append(log_entry)
        
        # 保持日志数量限制
        while len(self._request_logs) > self._max_request_logs:
            self._request_logs.pop(0)

    def get_request_logs(self, limit: int = 100) -> List[dict]:
        """
        获取请求日志
        
        Args:
            limit: 返回日志条数（默认 100）
        
        Returns:
            请求日志列表（按时间倒序）
        """
        return list(reversed(self._request_logs[-limit:]))

    def get_request_stats(self) -> dict:
        """
        获取请求统计信息
        
        Returns:
            {
                "total_requests": int,
                "success_rate": float,
                "avg_response_time": float,
                "model_stats": {model_name: {"count": int, "success_rate": float, "avg_response_time": float}}
            }
        """
        if not self._request_logs:
            return {
                "total_requests": 0,
                "success_rate": 0.0,
                "avg_response_time": 0.0,
                "model_stats": {}
            }
        
        total_requests = len(self._request_logs)
        success_count = sum(1 for log in self._request_logs if log["success"])
        total_response_time = sum(log["response_time"] for log in self._request_logs)
        
        # 按模型统计
        model_stats = {}
        for log in self._request_logs:
            model_name = log["model_name"]
            if model_name not in model_stats:
                model_stats[model_name] = {
                    "count": 0,
                    "success_count": 0,
                    "total_response_time": 0.0
                }
            
            model_stats[model_name]["count"] += 1
            if log["success"]:
                model_stats[model_name]["success_count"] += 1
            model_stats[model_name]["total_response_time"] += log["response_time"]
        
        # 计算每个模型的统计数据
        for model_name, stats in model_stats.items():
            stats["success_rate"] = stats["success_count"] / stats["count"] if stats["count"] > 0 else 0.0
            stats["avg_response_time"] = stats["total_response_time"] / stats["count"] if stats["count"] > 0 else 0.0
            # 移除中间变量
            stats.pop("success_count", None)
            stats.pop("total_response_time", None)
        
        return {
            "total_requests": total_requests,
            "success_rate": success_count / total_requests if total_requests > 0 else 0.0,
            "avg_response_time": total_response_time / total_requests if total_requests > 0 else 0.0,
            "model_stats": model_stats
        }

    # ============= API Key 校验 =============

    def enable_api_key_validation(self, enable: bool):
        """
        启用/禁用 API Key 校验
        
        Args:
            enable: 是否启用 API Key 校验
        """
        self._api_key_validation_enabled = enable
        if enable:
            logger.info("🔐 API Key 校验已启用")
        else:
            logger.info("🔓 API Key 校验已禁用")

    def is_api_key_validation_enabled(self) -> bool:
        """检查是否启用了 API Key 校验"""
        return self._api_key_validation_enabled

    def add_api_key(self, api_key: str):
        """
        添加有效的 API Key
        
        Args:
            api_key: API Key
        """
        if api_key not in self._valid_api_keys:
            self._valid_api_keys.append(api_key)
            logger.info(f"🔑 添加 API Key: {api_key[:8]}...")

    def remove_api_key(self, api_key: str) -> bool:
        """
        移除 API Key
        
        Args:
            api_key: 要移除的 API Key
        
        Returns:
            是否移除成功
        """
        if api_key in self._valid_api_keys:
            self._valid_api_keys.remove(api_key)
            logger.info(f"🔑 移除 API Key: {api_key[:8]}...")
            return True
        return False

    def set_api_keys(self, api_keys: List[str]):
        """
        设置有效的 API Key 列表（覆盖现有列表）
        
        Args:
            api_keys: API Key 列表
        """
        self._valid_api_keys = list(api_keys)
        logger.info(f"🔑 设置了 {len(api_keys)} 个 API Key")

    def validate_api_key(self, api_key: str) -> bool:
        """
        校验 API Key 是否有效
        
        Args:
            api_key: 待校验的 API Key
        
        Returns:
            是否有效
        """
        if not self._api_key_validation_enabled:
            return True
        
        if not api_key:
            return False
        
        return api_key in self._valid_api_keys

    def set_api_key_header(self, header: str):
        """
        设置 API Key 请求头名称
        
        Args:
            header: 请求头名称（如 "X-API-Key"）
        """
        self._api_key_header = header
        logger.info(f"🔑 API Key 请求头已设置为: {header}")

    def get_api_key_header(self) -> str:
        """获取 API Key 请求头名称"""
        return self._api_key_header

    # ============= 负载均衡支持 =============

    def set_load_balancing_enabled(self, enable: bool):
        """
        启用/禁用负载均衡
        
        Args:
            enable: 是否启用负载均衡
        """
        self._load_balancing_enabled = enable
        if enable:
            logger.info("⚖️ 负载均衡已启用")
        else:
            logger.info("⚖️ 负载均衡已禁用")

    def is_load_balancing_enabled(self) -> bool:
        """检查是否启用了负载均衡"""
        return self._load_balancing_enabled

    def set_load_balancing_strategy(self, strategy: Union[str, LoadBalancingStrategy]):
        """
        设置负载均衡策略
        
        Args:
            strategy: 负载均衡策略（round_robin/least_load/weighted_round_robin/random）
        """
        if isinstance(strategy, str):
            try:
                self._load_balancing_strategy = LoadBalancingStrategy(strategy.lower())
            except ValueError:
                logger.warning(f"无效的负载均衡策略: {strategy}，使用默认值 ROUND_ROBIN")
                self._load_balancing_strategy = LoadBalancingStrategy.ROUND_ROBIN
        elif isinstance(strategy, LoadBalancingStrategy):
            self._load_balancing_strategy = strategy
        
        logger.info(f"⚖️ 负载均衡策略已设置为: {self._load_balancing_strategy.value}")

    def get_load_balancing_strategy(self) -> LoadBalancingStrategy:
        """获取当前负载均衡策略"""
        return self._load_balancing_strategy

    def set_server_weight(self, server_url: str, weight: float):
        """
        设置服务器权重（用于加权轮询策略）
        
        Args:
            server_url: 服务器地址
            weight: 权重（正数，越大权重越高）
        """
        if weight <= 0:
            if server_url in self._server_weights:
                del self._server_weights[server_url]
        else:
            self._server_weights[server_url] = weight
        logger.info(f"⚖️ 设置服务器权重: {server_url} = {weight}")

    def get_server_weight(self, server_url: str) -> float:
        """
        获取服务器权重
        
        Args:
            server_url: 服务器地址
        
        Returns:
            权重值（默认为 1.0）
        """
        return self._server_weights.get(server_url, 1.0)

    def select_server(self, servers: List[str]) -> Optional[str]:
        """
        根据负载均衡策略选择服务器
        
        Args:
            servers: 可用服务器列表
        
        Returns:
            选中的服务器地址，如果列表为空返回 None
        """
        if not servers:
            return None
        
        if not self._load_balancing_enabled:
            return servers[0]
        
        strategy = self._load_balancing_strategy
        
        if strategy == LoadBalancingStrategy.ROUND_ROBIN:
            return self._select_round_robin(servers)
        
        elif strategy == LoadBalancingStrategy.LEAST_LOAD:
            return self._select_least_load(servers)
        
        elif strategy == LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN:
            return self._select_weighted_round_robin(servers)
        
        elif strategy == LoadBalancingStrategy.RANDOM:
            return self._select_random(servers)
        
        return servers[0]

    def _select_round_robin(self, servers: List[str]) -> str:
        """轮询选择服务器"""
        key = "lb_round_robin"
        index = self._rr_index.get(key, 0)
        selected = servers[index % len(servers)]
        self._rr_index[key] = (index + 1) % len(servers)
        return selected

    def _select_least_load(self, servers: List[str]) -> str:
        """选择负载最小的服务器"""
        best_server = servers[0]
        min_load = float('inf')
        
        for server_url in servers:
            # 获取该服务器上所有模型的总负载
            total_load = 0
            for model in self.models.values():
                model_url = model.config.get("url", "")
                if model_url == server_url:
                    total_load += model.current_load
            
            if total_load < min_load:
                min_load = total_load
                best_server = server_url
        
        return best_server

    def _select_weighted_round_robin(self, servers: List[str]) -> str:
        """加权轮询选择服务器"""
        # 计算总权重
        total_weight = sum(self.get_server_weight(s) for s in servers)
        
        if total_weight == 0:
            return self._select_round_robin(servers)
        
        # 使用轮询索引计算位置
        key = "lb_weighted_round_robin"
        index = self._rr_index.get(key, 0)
        
        # 根据权重选择
        current = index % total_weight
        cumulative = 0
        
        for server_url in servers:
            weight = self.get_server_weight(server_url)
            cumulative += weight
            if current < cumulative:
                self._rr_index[key] = index + 1
                return server_url
        
        self._rr_index[key] = index + 1
        return servers[0]

    def _select_random(self, servers: List[str]) -> str:
        """随机选择服务器"""
        import random
        return random.choice(servers)

    def get_load_balancing_stats(self) -> dict:
        """
        获取负载均衡统计信息
        
        Returns:
            {
                "strategy": ...,
                "enabled": ...,
                "server_weights": {...},
                "server_loads": {...}
            }
        """
        # 计算每个服务器的负载
        server_loads = {}
        for model in self.models.values():
            server_url = model.config.get("url", "")
            if server_url not in server_loads:
                server_loads[server_url] = {
                    "load": 0,
                    "models": []
                }
            server_loads[server_url]["load"] += model.current_load
            server_loads[server_url]["models"].append(model.model_id)
        
        return {
            "strategy": self._load_balancing_strategy.value,
            "enabled": self._load_balancing_enabled,
            "server_weights": self._server_weights,
            "server_loads": server_loads
        }


# ============= 全局实例 =============

_global_router: Optional[GlobalModelRouter] = None

def get_global_router() -> GlobalModelRouter:
    """获取全局路由器实例（单例）"""
    global _global_router
    if _global_router is None:
        _global_router = GlobalModelRouter()
    return _global_router

def set_global_router(router: GlobalModelRouter):
    """设置全局路由器实例"""
    global _global_router
    _global_router = router


# ============= 同步调用辅助函数 =============

def call_model_sync(capability: ModelCapability,
                    prompt: str,
                    system_prompt: str = "",
                    strategy: RoutingStrategy = RoutingStrategy.AUTO,
                    context_length: int = 0,
                    use_cache: bool = True,
                    model_id: str = "",
                    tier: Optional[ModelTier] = None,
                    expert_type: Optional[str] = None,  # 新增：专家类型
                    thinking_mode: Optional[str] = None,  # 新增：思考模式
                    rys_config: Optional[dict] = None,  # 新增：RYS层重复配置
                    verify: Optional[dict] = None,  # 新增：LLM-as-a-Verifier 验证配置
                    **kwargs) -> str:
    """
    同步调用模型（供非异步函数使用）

    Note: 由于 call_model 已经有 Opik 追踪，这里主要作为入口追踪。
    如果需要独立的追踪，可以取消下面的注释。
    """
    # ── Opik 入口追踪（可选）────────────────────────────────
    # 如果需要为 call_model_sync 添加独立追踪，取消下面的注释
    # _opik_trace = None
    # _opik_start_time = time.time()
    # 
    # if OPIK_TRACER_AVAILABLE and is_opik_enabled():
    #     try:
    #         _opik_trace = start_trace(
    #             name=f"call_model_sync_{capability.value if capability else 'unknown'}",
    #             trace_type="llm",
    #             metadata={"function": "call_model_sync"}
    #         )
    #     except Exception as e:
    #         logger.warning(f"Opik 追踪初始化失败: {e}")

    try:
        result = asyncio.run(
            get_global_router().call_model(
                capability, prompt, system_prompt,
                strategy, context_length, use_cache,
                model_id, tier, expert_type, thinking_mode,
                rys_config, verify, **kwargs
            )
        )

        # ── Opik 入口追踪记录（可选）────────────────────────
        # if _opik_trace is not None:
        #     try:
        #         _opik_end_time = time.time()
        #         _opik_latency = _opik_end_time - _opik_start_time
        # 
        #         log_trace(
        #             _opik_trace,
        #             input_data={
        #                 "capability": capability.value if capability else None,
        #                 "prompt": prompt[:500],
        #             },
        #             output_data={
        #                 "response": result[:1000] if result else None,
        #                 "latency": _opik_latency,
        #             },
        #             metadata={"latency": _opik_latency, "success": bool(result)}
        #         )
        #     except Exception as e:
        #         logger.warning(f"Opik 追踪记录失败: {e}")

        return result

    except Exception as e:
        logger.error(f"call_model_sync 执行失败: {e}")
        # ── Opik 入口追踪记录（失败）──────────────────────
        # if _opik_trace is not None:
        #     try:
        #         log_trace(
        #             _opik_trace,
        #             input_data={"capability": capability.value if capability else None},
        #             output_data={"error": str(e)},
        #             metadata={"success": False, "error": str(e)}
        #         )
        #     except Exception as ex:
        #         logger.warning(f"Opik 追踪记录失败: {ex}")
        raise
    
#     内部使用 asyncio.run() 调用异步的 call_model()
#     # 注意: 如果已有事件循环运行，此方法会失败
#     
#     Args:
#         capability: 需要的能力
#         prompt: 用户提示
#         system_prompt: 系统提示
#         strategy: 路由策略
#         context_length: 需要的上下文长度
#         use_cache: 是否使用缓存
#         model_id: 直接指定模型ID（不走路由）
#     
#     Returns:
#         模型输出文本
#     """
    router = get_global_router()
    
    try:
        # 尝试获取当前事件循环
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 已有运行中的事件循环，使用 run_until_complete
            # 注意：在某些环境中可能不支持
            return asyncio.run_coroutine_threadsafe(
                router.call_model(capability, prompt, system_prompt, strategy, context_length, use_cache, model_id, tier, expert_type, thinking_mode, rys_config=rys_config, verify=verify),
                loop
            ).result(timeout=120)
        else:
            # 没有运行中的循环，使用 asyncio.run()
            return asyncio.run(
                router.call_model(capability, prompt, system_prompt, strategy, context_length, use_cache, model_id, tier, expert_type, thinking_mode, rys_config=rys_config, verify=verify)
            )
    except RuntimeError:
        # 没有事件循环，创建新的
        return asyncio.run(
            router.call_model(capability, prompt, system_prompt, strategy, context_length, use_cache, model_id, tier, expert_type, thinking_mode, rys_config=rys_config, verify=verify)
        )


# ============= Handler 体系 =============

class BaseHandler(ABC):
    """处理器基类（Strategy模式）"""
    
    @abstractmethod
    async def handle(self, prompt: str, system_prompt: str = "", **kwargs) -> str:
        """处理请求"""
        pass
    
    @abstractmethod
    def get_capability(self) -> ModelCapability:
        """返回此处理器处理的能力"""
        pass
    
    def preprocess(self, prompt: str) -> str:
        """预处理（可选覆盖）"""
        return prompt
    
    def postprocess(self, response: str) -> str:
        """后处理（可选覆盖）"""
        return response


class ChatHandler(BaseHandler):
    """通用聊天处理器"""
    
    async def handle(self, prompt: str, system_prompt: str = "", **kwargs) -> str:
        router = get_global_router()
        return await router.call_model(
            capability=ModelCapability.CHAT,
            prompt=prompt,
            system_prompt=system_prompt or "你是一个有用的AI助手。"
        )
    
    def get_capability(self) -> ModelCapability:
        return ModelCapability.CHAT


class CodeGenerationHandler(BaseHandler):
    """代码生成处理器"""
    
    async def handle(self, prompt: str, system_prompt: str = "", **kwargs) -> str:
        # 增强：自动添加代码生成提示
        enhanced_prompt = f"请生成代码，只输出代码本身（不含解释）：\n{prompt}"
        
        router = get_global_router()
        return await router.call_model(
            capability=ModelCapability.CODE_GENERATION,
            prompt=enhanced_prompt,
            system_prompt=system_prompt or "你是一个代码生成助手。只输出代码，不要解释。"
        )
    
    def get_capability(self) -> ModelCapability:
        return ModelCapability.CODE_GENERATION


class ReasoningHandler(BaseHandler):
    """推理处理器（复杂问题）"""
    
    async def handle(self, prompt: str, system_prompt: str = "", **kwargs) -> str:
        # 增强：要求分步推理
        enhanced_prompt = f"请分步思考并给出答案：\n{prompt}"
        
        router = get_global_router()
        return await router.call_model(
            capability=ModelCapability.REASONING,
            prompt=enhanced_prompt,
            system_prompt=system_prompt or "你是一个推理助手。请分步思考，给出详细推理过程。"
        )
    
    def get_capability(self) -> ModelCapability:
        return ModelCapability.REASONING


class TranslationHandler(BaseHandler):
    """翻译处理器"""
    
    def __init__(self, source_lang: str = "auto", target_lang: str = "zh"):
        self.source_lang = source_lang
        self.target_lang = target_lang
    
    async def handle(self, prompt: str, system_prompt: str = "", **kwargs) -> str:
        # 构建翻译提示
        if self.source_lang == "auto":
            translate_prompt = f"翻译成{self.target_lang}：\n{prompt}"
        else:
            translate_prompt = f"从{self.source_lang}翻译成{self.target_lang}：\n{prompt}"
        
        router = get_global_router()
        return await router.call_model(
            capability=ModelCapability.TRANSLATION,
            prompt=translate_prompt,
            system_prompt=system_prompt or f"你是一个翻译助手。只输出翻译结果，不要解释。"
        )
    
    def get_capability(self) -> ModelCapability:
        return ModelCapability.TRANSLATION


class SummarizationHandler(BaseHandler):
    """摘要处理器"""
    
    def __init__(self, max_length: int = 100):
        self.max_length = max_length
    
    async def handle(self, prompt: str, system_prompt: str = "", **kwargs) -> str:
        # 构建摘要提示
        summary_prompt = f"请总结以下内容（不超过{self.max_length}字）：\n\n{prompt}"
        
        router = get_global_router()
        return await router.call_model(
            capability=ModelCapability.SUMMARIZATION,
            prompt=summary_prompt,
            system_prompt=system_prompt or f"你是一个文本摘要助手。总结要简洁准确，不超过{self.max_length}字。"
        )
    
    def get_capability(self) -> ModelCapability:
        return ModelCapability.SUMMARIZATION


class CodeReviewHandler(BaseHandler):
    """代码审查处理器"""
    
    async def handle(self, prompt: str, system_prompt: str = "", **kwargs) -> str:
        # 构建代码审查提示
        review_prompt = f"请审查以下代码，指出问题并给出改进建议：\n\n```\n{prompt}\n```"
        
        router = get_global_router()
        return await router.call_model(
            capability=ModelCapability.CODE_REVIEW,
            prompt=review_prompt,
            system_prompt=system_prompt or "你是一个代码审查专家。关注：bug、性能、安全性、可读性、最佳实践。"
        )
    
    def get_capability(self) -> ModelCapability:
        return ModelCapability.CODE_REVIEW


class DocumentGenerationHandler(BaseHandler):
    """文档生成处理器"""
    
    def __init__(self, doc_type: str = "report"):
        self.doc_type = doc_type  # report, manual, spec, etc.
    
    async def handle(self, prompt: str, system_prompt: str = "", **kwargs) -> str:
        # 构建文档生成提示
        doc_prompt = f"请生成{self.doc_type}文档：\n{prompt}"
        
        router = get_global_router()
        return await router.call_model(
            capability=ModelCapability.DOCUMENT_PLANNING,
            prompt=doc_prompt,
            system_prompt=system_prompt or f"你是一个{self.doc_type}文档生成助手。生成结构清晰、内容完整的文档。"
        )
    
    def get_capability(self) -> ModelCapability:
        return ModelCapability.DOCUMENT_PLANNING


class DataAnalysisHandler(BaseHandler):
    """数据分析处理器"""
    
    async def handle(self, prompt: str, system_prompt: str = "", **kwargs) -> str:
        # 构建数据分析提示
        analysis_prompt = f"请分析以下数据或问题：\n{prompt}"
        
        router = get_global_router()
        return await router.call_model(
            capability=ModelCapability.DATA_ANALYSIS,
            prompt=analysis_prompt,
            system_prompt=system_prompt or "你是一个数据分析助手。提供清晰的分析和可行的建议。"
        )
    
    def get_capability(self) -> ModelCapability:
        return ModelCapability.DATA_ANALYSIS


class CreativeWritingHandler(BaseHandler):
    """创意写作处理器"""
    
    def __init__(self, style: str = "general"):
        self.style = style  # general, poetry, story, marketing, etc.
    
    async def handle(self, prompt: str, system_prompt: str = "", **kwargs) -> str:
        write_prompt = f"请进行创意写作（风格：{self.style}）：\n{prompt}"
        
        router = get_global_router()
        return await router.call_model(
            capability=ModelCapability.CONTENT_GENERATION,
            prompt=write_prompt,
            system_prompt=system_prompt or f"你是一个创意写作助手。风格：{self.style}。"
        )
    
    def get_capability(self) -> ModelCapability:
        return ModelCapability.CONTENT_GENERATION


class QuestionAnsweringHandler(BaseHandler):
    """问答处理器（基于上下文）"""
    
    def __init__(self, context: str = ""):
        self.context = context
    
    async def handle(self, prompt: str, system_prompt: str = "", **kwargs) -> str:
        if self.context:
            qa_prompt = f"基于以下上下文回答问题：\n\n上下文：{self.context}\n\n问题：{prompt}"
        else:
            qa_prompt = prompt
        
        router = get_global_router()
        return await router.call_model(
            capability=ModelCapability.KNOWLEDGE_QUERY,
            prompt=qa_prompt,
            system_prompt=system_prompt or "你是一个问答助手。基于上下文回答，不知道就说不知道。"
        )
    
    def get_capability(self) -> ModelCapability:
        return ModelCapability.KNOWLEDGE_QUERY


# ============= Handler 工厂 =============

class HandlerFactory:
    """处理器工厂（Factory模式）"""
    
    _handlers = {
        ModelCapability.CHAT: ChatHandler,
        ModelCapability.CODE_GENERATION: CodeGenerationHandler,
        ModelCapability.REASONING: ReasoningHandler,
        ModelCapability.TRANSLATION: TranslationHandler,
        ModelCapability.SUMMARIZATION: SummarizationHandler,
        ModelCapability.CODE_REVIEW: CodeReviewHandler,
        ModelCapability.DOCUMENT_PLANNING: DocumentGenerationHandler,
        ModelCapability.DATA_ANALYSIS: DataAnalysisHandler,
        ModelCapability.CONTENT_GENERATION: CreativeWritingHandler,
        ModelCapability.KNOWLEDGE_QUERY: QuestionAnsweringHandler,
    }
    
    @classmethod
    def create_handler(cls, capability: ModelCapability, **kwargs) -> BaseHandler:
        """
        创建处理器
        
        Args:
            capability: 能力
            **kwargs: 传递给处理器构造函数的参数
        
        Returns:
            BaseHandler 处理器实例
        """
        handler_class = cls._handlers.get(capability)
        if not handler_class:
            # 默认使用ChatHandler
            logger.warning(f"未知能力 {capability}，使用ChatHandler")
            return ChatHandler()
        
        return handler_class(**kwargs)
    
    @classmethod
    def register_handler(cls, capability: ModelCapability, handler_class: type):
        """注册自定义处理器"""
        if not issubclass(handler_class, BaseHandler):
            raise ValueError(f"{handler_class} 必须继承 BaseHandler")
        
        cls._handlers[capability] = handler_class
        logger.info(f"注册处理器：{capability.value} → {handler_class.__name__}")


# ============= 便捷函数 =============

async def handle_with_handler(capability: ModelCapability, 
                             prompt: str, 
                             system_prompt: str = "",
                             **kwargs) -> str:
    """
    使用Handler处理请求（便捷函数）
    
    Args:
        capability: 能力
        prompt: 提示
        system_prompt: 系统提示
        **kwargs: 传递给处理器的参数
    
    Returns:
        str: 处理结果
    """
    handler = HandlerFactory.create_handler(capability, **kwargs)
    return await handler.handle(prompt, system_prompt)


# ============= 同步便捷函数 =============

def translate(text: str, source_lang: str = "auto", target_lang: str = "zh") -> str:
    """翻译（同步）"""
    import asyncio
    handler = TranslationHandler(source_lang=source_lang, target_lang=target_lang)
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.run_coroutine_threadsafe(
                handler.handle(text), loop
            ).result(timeout=60)
        else:
            return asyncio.run(handler.handle(text))
    except RuntimeError:
        return asyncio.run(handler.handle(text))


def summarize(text: str, max_length: int = 100) -> str:
    """摘要（同步）"""
    import asyncio
    handler = SummarizationHandler(max_length=max_length)
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.run_coroutine_threadsafe(
                handler.handle(text), loop
            ).result(timeout=60)
        else:
            return asyncio.run(handler.handle(text))
    except RuntimeError:
        return asyncio.run(handler.handle(text))


def review_code(code: str) -> str:
    """代码审查（同步）"""
    import asyncio
    handler = CodeReviewHandler()
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.run_coroutine_threadsafe(
                handler.handle(code), loop
            ).result(timeout=60)
        else:
            return asyncio.run(handler.handle(code))
    except RuntimeError:
        return asyncio.run(handler.handle(code))


def analyze_data(question: str) -> str:
    """数据分析（同步）"""
    import asyncio
    handler = DataAnalysisHandler()
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.run_coroutine_threadsafe(
                handler.handle(question), loop
            ).result(timeout=60)
        else:
            return asyncio.run(handler.handle(question))
    except RuntimeError:
        return asyncio.run(handler.handle(question))


# ============= 情绪感知集成（新增 2026-04-27） =============

async def call_model_with_emotion(
    capability: ModelCapability,
    prompt: str,
    system_prompt: str = "",
    strategy: RoutingStrategy = RoutingStrategy.AUTO,
    context_length: int = 0,
    use_cache: bool = True,
    model_id: str = "",
    tier: Optional[ModelTier] = None,
    expert_type: Optional[str] = None,
    auto_emotion: bool = True,  # 新增：是否自动情绪感知
    **kwargs
) -> str:
    """
    调用模型（支持自动情绪感知）
    
    Args:
        capability: 模型能力
        prompt: 用户消息
        system_prompt: 系统提示
        strategy: 路由策略
        context_length: 上下文长度
        use_cache: 是否使用缓存
        model_id: 指定模型ID
        tier: 分层路由
        expert_type: 专家类型
        auto_emotion: 是否自动进行情绪感知并调整思考模式
        **kwargs: 其他参数
        
    Returns:
        模型输出文本
    """
    # 如果启用自动情绪感知
    if auto_emotion and expert_type:
        try:
            from business.emotion_thinking_integrator import (
                get_emotion_thinking_integrator
            )
            
            integrator = get_emotion_thinking_integrator()
            
            # 处理并增强Prompt
            result, enhanced_prompt = await integrator.process_and_enhance_prompt(
                user_message=prompt,
                base_system_prompt=system_prompt,
                expert_type=expert_type,
                context=None,
            )
            
            # 使用增强后的Prompt调用模型
            router = get_global_router()
            return await router.call_model(
                capability=capability,
                prompt=prompt,
                system_prompt=enhanced_prompt,
                strategy=strategy,
                context_length=context_length,
                use_cache=use_cache,
                model_id=model_id,
                tier=tier,
                **kwargs
            )
        except ImportError as e:
            logger.warning(f"情绪感知集成失败，使用普通调用: {e}")
            # 失败则使用普通调用
    
    # 普通调用（未启用自动情绪感知或失败）
    router = get_global_router()
    return await router.call_model(
        capability=capability,
        prompt=prompt,
        system_prompt=system_prompt,
        strategy=strategy,
        context_length=context_length,
        use_cache=use_cache,
        model_id=model_id,
        tier=tier,
        expert_type=expert_type,
        **kwargs
    )


def call_model_with_emotion_sync(
    capability: ModelCapability,
    prompt: str,
    system_prompt: str = "",
    strategy: RoutingStrategy = RoutingStrategy.AUTO,
    context_length: int = 0,
    use_cache: bool = True,
    model_id: str = "",
    tier: Optional[ModelTier] = None,
    expert_type: Optional[str] = None,
    auto_emotion: bool = True,
    **kwargs
) -> str:
    """
    调用模型（同步版本，支持自动情绪感知）
    
    Args:
        同 call_model_with_emotion
        
    Returns:
        模型输出文本
    """
    import asyncio
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.run_coroutine_threadsafe(
                call_model_with_emotion(
                    capability, prompt, system_prompt, strategy,
                    context_length, use_cache, model_id, tier,
                    expert_type, auto_emotion, **kwargs
                ),
                loop
            ).result(timeout=120)
        else:
            return asyncio.run(
                call_model_with_emotion(
                    capability, prompt, system_prompt, strategy,
                    context_length, use_cache, model_id, tier,
                    expert_type, auto_emotion, **kwargs
                )
            )
    except RuntimeError:
        return asyncio.run(
            call_model_with_emotion(
                capability, prompt, system_prompt, strategy,
                context_length, use_cache, model_id, tier,
                expert_type, auto_emotion, **kwargs
            )
        )


# ============= 全局单例 =============

_global_router_instance = None

def get_router() -> GlobalModelRouter:
    """
    获取全局模型路由器单例
    
    Returns:
        GlobalModelRouter 实例
    """
    global _global_router_instance
    if _global_router_instance is None:
        _global_router_instance = GlobalModelRouter()
    return _global_router_instance
