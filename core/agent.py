"""
Hermes Agent 核心
参考 NousResearch/hermes-agent 的 AIAgent 架构
支持 llama-cpp-python (本地 GGUF) 和 Ollama 两种后端
优先使用 vLLM 引擎
"""
from __future__ import annotations

import re
import time
import json
import threading
import traceback
from pathlib import Path
from typing import Callable, Iterator, Optional, List, Dict, Any
from dataclasses import dataclass

# 日志系统
from core.logger import get_logger
logger = get_logger("core.agent")

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
try:
    from core.config.unified_config import get_config as _get_unified_config
    _uconfig = _get_unified_config()
except Exception:
    _uconfig = None
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
from core.agent_progress import (
    AgentProgress, 
    ProgressPhase, 
    ProgressEmitter,
    get_progress_tracker
)
from core.model_capabilities import (
    ModelCapabilityDetector,
    MultimodalMessageFilter,
    get_capability_detector,
    ThinkingCapability,
    MultimodalCapability,
    ModelCapabilities,
)
from core.task_decomposer import (
    TaskDecomposer,
    SubTaskExecutor,
    TaskDecompositionCallbacks,
    TaskDecomposition,
    SubTask,
    TaskStatus,
)


# ── 懒加载情绪感知模块（避免循环导入）──────────────────────────────
def _lazy_emotion_imports():
    """延迟导入情绪感知模块，直接加载文件绕过 living_tree_ai/__init__.py 的问题导入"""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_emotional_lazy",
        "core/living_tree_ai/neural_layer/emotional.py"
    )
    mod = importlib.util.module_from_spec(spec)
    import sys
    sys.modules["_emotional_lazy"] = mod
    spec.loader.exec_module(mod)
    return mod.EmotionalEncoder, mod.EmotionVector, mod.get_emotional_encoder, mod.EmotionType


# ── L0 意图分类器：规则引擎 + 模型推断 + 情绪感知 ───────────────────

class L0IntentClassifier:
    """
    L0 快速意图分类器

    架构：
    1. 规则快速通道（< 1ms）：高频简单意图直接命中
    2. L0 模型推断（~2-5s）：复杂/模糊意图交给 LLM
    3. 反馈学习：LLM 结果反哺规则引擎（持续优化）

    意图类型：
    - dialogue: 寒暄/情感/短句（跳过 KB/深度搜索）
    - task: 任务/行动（KB 搜索 + L3 模型）
    - search: 知识性提问（KB + 深度搜索 + L4 模型）
    - emotion_aware: 情绪感知（特殊处理，影响回复风格）
    """

    # 预编译正则（避免重复编译）
    _GREETINGS = frozenset({"你好", "您好", "hi", "hello", "hey", "嗨",
                             "谢谢", "感谢", "多谢", "没事", "没关系",
                             "好吧", "行吧", "好的", "嗯嗯", "晚安",
                             "早安", "早上好", "下午好", "晚上好",
                             "再见", "拜拜", "下次见", "哈", "嗯"})
    _EMOTION_WORDS = frozenset({"好累", "好困", "好烦", "好开心", "好难过", "好无聊",
                                "好忙", "好舒服", "心情", "糟了", "完了", "累死了",
                                "太难了", "太简单了", "我靠", "郁闷", "压力", "焦虑"})
    _SEARCH_PREFIXES = frozenset({"什么是", "什么叫", "为什么", "为何", "怎么会",
                                   "怎么是", "怎么能", "怎么样", "怎么选", "怎么用",
                                   "怎么写", "如何", "哪有", "是不是", "会不会",
                                   "能不能", "可不可以", "有多少", "哪个好", "哪个是",
                                   "在哪里", "是什么", "是哪个", "介绍一下", "解释一下",
                                   "说一说", "讲讲", "帮我分析", "帮我查"})
    _TASK_VERBS = frozenset({"帮我", "帮我写", "帮我做", "帮我找", "写一个", "写段",
                              "生成", "创建", "打开", "启动", "做个", "做一下",
                              "执行", "运行", "调用", "做个", "列出", "统计",
                              "对比", "整理", "翻译", "计算"})
    _TASK_SUFFIXES = frozenset({"原理", "步骤", "实现", "代码", "编程", "写",
                                 "安装", "部署", "配置", "运行", "调试"})
    _TECH_KEYWORDS = frozenset({"python", "java", "javascript", "js", "sql", "api",
                                 "http", "代码", "编程", "函数", "算法", "安装",
                                 "部署", "配置", "运行", "调试", "编译", "接口",
                                 "数据库", "服务器", "文件"})

    # 反馈学习：统计规则命中率（用于判断是否需要升级为规则）
    _rule_hit_count: Dict[str, int] = {}
    _rule_miss_count: Dict[str, int] = {}

    def __init__(self, ollama_client: Optional[OllamaClient] = None):
        self._ollama = ollama_client
        # 规则命中率统计（持久化后可用于自动优化）
        self._stats = {"rule_hits": 0, "model_calls": 0, "rule_types": {}}

    def _classify_by_rules(self, query: str) -> Optional[str]:
        """
        规则快速通道（< 1ms）

        Returns:
            None → 未命中，需要 LLM 推断
            str → 意图类型
        """
        q = query.strip()
        q_lower = q.lower()

        # ── 优先级 1: 搜索类（疑问词开头）────────────────────────────
        for prefix in self._SEARCH_PREFIXES:
            if q.startswith(prefix):
                # 「是什么原理」「怎么做」→ task（有技术词）
                if any(suffix in q for suffix in self._TASK_SUFFIXES):
                    self._record_hit("search_prefix+task_suffix")
                    return "task"
                self._record_hit("search_prefix")
                return "search"

        # 问号结尾 → 搜索
        if q.endswith("？") or q.endswith("?"):
            self._record_hit("question_mark")
            return "search"

        # ── 优先级 2: 任务类（行动动词）──────────────────────────────
        for verb in self._TASK_VERBS:
            if verb in q:
                self._record_hit(f"task_verb:{verb}")
                return "task"

        # 技术关键词 → 任务
        if any(kw in q_lower for kw in self._TECH_KEYWORDS):
            self._record_hit("tech_keyword")
            return "task"

        # ── 优先级 3: 疑问词中间出现 → 搜索 ─────────────────────────
        # 处理 "帮我查一下天气"（"怎么"不在开头）、"AI Agent的原理是什么" 等
        mid_question_words = ("怎么", "多少", "什么样", "哪些", "什么型号")
        if any(w in q for w in mid_question_words):
            if any(suffix in q for suffix in self._TASK_SUFFIXES):
                self._record_hit("mid_question+task_suffix")
                return "task"
            self._record_hit("mid_question")
            return "search"

        # ── 优先级 4: 对话类（寒暄/情感/短句）───────────────────────
        # 精确寒暄
        if q_lower in self._GREETINGS:
            self._record_hit("greeting")
            return "dialogue"

        # 情感/状态词
        for word in self._EMOTION_WORDS:
            if word in q:
                self._record_hit(f"emotion:{word}")
                return "emotion_aware"

        # 纯语气词
        if re.fullmatch(r"[哦嗯啊呀哈嘻嘛呢吧！?~。]+", q):
            self._record_hit("pure_interjection")
            return "dialogue"

        # 短句（≤12字）：有问号 → 搜索；否则 → 对话
        if len(q) <= 12:
            self._record_hit("short_sentence")
            return "search" if (q.endswith("？") or q.endswith("?")) else "dialogue"

        # 未命中
        self._record_miss(q)
        return None

    async def _classify_by_llm(self, query: str) -> str:
        """
        L0 模型推断（~2-5s）

        当规则未命中时，调用 LLM 进行意图分类
        """
        self._stats["model_calls"] += 1

        system_prompt = (
            '你是一个意图分类器。请将用户查询分类为以下类型之一：\n'
            "- dialogue: 寒暄、问候、感谢、情感表达（如'今天好累'、'你好'）\n"
            "- task: 有明确行动请求，如'帮我写代码'、'帮我查天气'、'打开文件'\n"
            "- search: 知识性提问，如'什么是AI'、'为什么天空是蓝的'、'Python怎么安装'\n\n"
            '规则：\n'
            "1. 有'帮我/帮我写/帮我做' → task\n"
            "2. 疑问词(什么是/为什么/如何)开头 → search\n"
            "3. 寒暄/情感/短句(≤12字) → dialogue\n"
            "4. 技术关键词(代码/python/部署) → task\n\n"
            "只输出一个词：dialogue 或 task 或 search，不要解释。"
        )

        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=query),
        ]

        if self._ollama:
            full_text = ""
            async for chunk in self._ollama.chat_stream(messages, model=self._ollama._default_model or "qwen2.5:1.5b"):
                if chunk.delta:
                    full_text += chunk.delta
            result = full_text.strip().lower()
            if "task" in result:
                return "task"
            elif "dialogue" in result:
                return "dialogue"
        return "search"

    def _record_hit(self, rule_type: str):
        self._stats["rule_hits"] += 1
        self._stats["rule_types"][rule_type] = self._stats["rule_types"].get(rule_type, 0) + 1

    def _record_miss(self, query: str):
        # 记录未命中的查询（用于反馈学习）
        key = f"miss_{hash(query) % 1000}"
        self._rule_miss_count[key] = self._rule_miss_count.get(key, 0) + 1

    def classify(self, query: str, use_llm_fallback: bool = True) -> Dict[str, Any]:
        """
        主分类入口：规则优先，LLM 兜底

        Args:
            query: 用户查询
            use_llm_fallback: 规则未命中时是否调用 LLM

        Returns:
            {"type": "dialogue"|"task"|"search"|"emotion_aware",
             "confidence": 0.0-1.0,
             "method": "rule"|"llm",
             "stats": {...}}
        """
        # 1. 规则快速通道
        rule_result = self._classify_by_rules(query)
        if rule_result is not None:
            return {
                "type": rule_result,
                "confidence": 0.95,
                "method": "rule",
                "stats": self._stats,
            }

        # 2. LLM 推断（同步简化版本）
        if use_llm_fallback and self._ollama:
            # 同步调用（避免 async 复杂性）
            try:
                import asyncio
                loop = asyncio.new_event_loop()
                result = loop.run_until_complete(self._classify_by_llm(query))
                loop.close()
                return {
                    "type": result,
                    "confidence": 0.85,
                    "method": "llm",
                    "stats": self._stats,
                }
            except Exception as e:
                logger.warning(f"LLM 推断失败: {e}，回退到默认 search")
                return {
                    "type": "search",
                    "confidence": 0.5,
                    "method": "fallback",
                    "stats": self._stats,
                }

        # 3. 完全回退
        return {
            "type": "search",
            "confidence": 0.5,
            "method": "default",
            "stats": self._stats,
        }

    def get_stats(self) -> Dict[str, Any]:
        return self._stats


# ── 数字分身核心：用户画像 + 学习积累 + 情感记忆 ──────────────────

class UserDigitalTwin:
    """
    用户数字分身核心

    通过以下模块持续学习用户：
    - 情绪感知：EmotionVector 追踪用户情感状态
    - 意图积累：高频意图 → 预判用户需求
    - 偏好学习：语言风格、响应偏好、知识盲区
    - 记忆融合：会话历史 + 知识库 + 深度搜索结果

    使用场景：
    1. 预判用户意图（基于历史习惯）
    2. 个性化回复风格（匹配用户偏好）
    3. 知识盲区提醒（系统学过但用户不知道的）
    4. 情感共振（情绪低落时主动关心）
    """

    def __init__(self, user_id: str):
        # 懒加载避免循环导入
        EmotionalEncoder, EmotionVector, get_emotional_encoder, EmotionType = _lazy_emotion_imports()

        self.user_id = user_id
        self._lock = threading.RLock()

        # ── 用户画像 ───────────────────────────────────────────
        self.preferences = {
            "reply_style": "normal",  # normal / concise / detailed
            "language": "chinese",
            "preferred_model": None,   # 用户偏好的模型
            "max_response_length": 2000,
        }

        # ── 学习积累 ───────────────────────────────────────────
        self.intent_history: Dict[str, int] = {}   # {意图类型: 次数}
        self.topic_history: Dict[str, int] = {}    # {话题: 次数}
        self.tool_usage: Dict[str, int] = {}       # {工具名: 使用次数}

        # ── 情感记忆 ───────────────────────────────────────────
        self.emotion_encoder = EmotionalEncoder(node_id=f"twin_{user_id}")
        self.current_emotion: Optional[EmotionVector] = None
        self.emotion_timeline: List[Dict[str, Any]] = []  # 带时间戳的情感历史

        # ── 数字分身状态 ───────────────────────────────────────
        self.level = 1
        self.experience = 0
        self.learned_topics: Set[str] = set()  # 已学习的话题

        # ── 知识盲区 ───────────────────────────────────────────
        # 系统知道但用户经常问的话题（通过统计发现）
        self.knowledge_gaps: List[str] = []

    def record_interaction(self, query: str, intent_type: str,
                           emotion: Optional[EmotionVector] = None,
                           response_length: int = 0):
        """记录一次交互，用于持续学习"""
        with self._lock:
            # 更新意图历史
            self.intent_history[intent_type] = self.intent_history.get(intent_type, 0) + 1

            # 提取简单话题关键词
            keywords = re.findall(r"[\w]{2,}", query)
            for kw in keywords[:5]:  # 取前5个关键词
                self.topic_history[kw] = self.topic_history.get(kw, 0) + 1

            # 更新情感
            if emotion:
                self.current_emotion = emotion
                self.emotion_encoder._update_current_emotion(emotion, factor=0.3)
                self.emotion_timeline.append({
                    "timestamp": time.time(),
                    "valence": emotion.valence,
                    "arousal": emotion.arousal,
                    "dominant": emotion.dominant_emotion().value,
                    "intent": intent_type,
                })
                # 保留最近50条情感记录
                if len(self.emotion_timeline) > 50:
                    self.emotion_timeline.pop(0)

            # 经验积累（每10次交互升1级）
            self.experience += 1
            self.level = self.experience // 10 + 1

    def record_tool_usage(self, tool_name: str):
        """记录工具使用"""
        with self._lock:
            self.tool_usage[tool_name] = self.tool_usage.get(tool_name, 0) + 1

    def get_top_intents(self, top_n: int = 3) -> List[Tuple[str, int]]:
        """获取高频意图（用于预判）"""
        sorted_intents = sorted(self.intent_history.items(), key=lambda x: x[1], reverse=True)
        return sorted_intents[:top_n]

    def get_top_topics(self, top_n: int = 5) -> List[Tuple[str, int]]:
        """获取高频话题"""
        sorted_topics = sorted(self.topic_history.items(), key=lambda x: x[1], reverse=True)
        return sorted_topics[:top_n]

    def get_recent_emotion_trend(self) -> str:
        """分析近期情感趋势"""
        if len(self.emotion_timeline) < 3:
            return "neutral"

        recent = self.emotion_timeline[-5:]
        valence_avg = sum(e["valence"] for e in recent) / len(recent)

        if valence_avg > 0.3:
            return "positive"
        elif valence_avg < -0.3:
            return "negative"
        return "neutral"

    def should_express_care(self) -> bool:
        """判断是否应该主动表达关心"""
        if not self.emotion_timeline:
            return False
        recent = self.emotion_timeline[-3:]
        negative_count = sum(1 for e in recent if e["valence"] < -0.2)
        return negative_count >= 2

    def get_care_response(self) -> str:
        """生成关心语句（基于情感分析）"""
        _, EmotionVector, _, EmotionType = _lazy_emotion_imports()
        if not self.current_emotion:
            return "我注意到你最近可能有些疲惫，有什么我可以帮你的吗？"

        dominant = self.current_emotion.dominant_emotion()
        emotion_responses = {
            EmotionType.SADNESS: "看起来你心情不太好，愿意聊聊吗？",
            EmotionType.ANGER: "感觉你有点烦躁，深呼吸，一起慢慢解决。",
            EmotionType.FEAR: "别担心，有什么让我帮你分担吗？",
            EmotionType.CALM: "挺好的，保持这个状态～",
            EmotionType.JOY: "太棒了！有什么开心的事想分享吗？",
            EmotionType.EXCITEMENT: "看起来你很兴奋！发生什么好事了？",
            EmotionType.NEUTRAL: "我在这里，有什么需要帮忙的？",
        }
        return emotion_responses.get(dominant, "我在这里，有什么需要帮忙的吗？")

    def get_context_for_prompt(self) -> str:
        """生成用于注入 LLM 提示的用户上下文"""
        parts = []

        # 情感状态
        if self.current_emotion:
            dominant = self.current_emotion.dominant_emotion().value
            parts.append(f"用户当前情绪状态: {dominant}（效价={self.current_emotion.valence:.1f}）")

        # 近期趋势
        trend = self.get_recent_emotion_trend()
        if trend != "neutral":
            parts.append(f"用户近期情感趋势: {trend}")

        # 高频话题
        top_topics = self.get_top_topics(3)
        if top_topics:
            topics_str = "、".join(f"{t}({c}次)" for t, c in top_topics)
            parts.append(f"用户高频关注话题: {topics_str}")

        # 关心判断
        if self.should_express_care():
            parts.append("【重要】用户情绪低落，建议先表达关心再处理请求")

        # 数字分身等级（用于决定回复详细程度）
        parts.append(f"数字分身等级: {self.level}（经验值: {self.experience}）")

        return "\n".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """序列化"""
        return {
            "user_id": self.user_id,
            "level": self.level,
            "experience": self.experience,
            "preferences": self.preferences,
            "intent_history": self.intent_history,
            "topic_history": self.topic_history,
            "tool_usage": self.tool_usage,
            "learned_topics": list(self.learned_topics),
            "emotion_timeline": self.emotion_timeline[-20:],  # 只保留最近20条
            "current_emotion": {
                "valence": self.current_emotion.valence if self.current_emotion else 0,
                "arousal": self.current_emotion.arousal if self.current_emotion else 0,
            } if self.current_emotion else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserDigitalTwin":
        """反序列化"""
        _, EmotionVector, _, _ = _lazy_emotion_imports()
        twin = cls(data["user_id"])
        twin.level = data.get("level", 1)
        twin.experience = data.get("experience", 0)
        twin.preferences = data.get("preferences", {})
        twin.intent_history = data.get("intent_history", {})
        twin.topic_history = data.get("topic_history", {})
        twin.tool_usage = data.get("tool_usage", {})
        twin.learned_topics = set(data.get("learned_topics", []))
        twin.emotion_timeline = data.get("emotion_timeline", [])

        em_data = data.get("current_emotion")
        if em_data:
            twin.current_emotion = EmotionVector(
                valence=em_data.get("valence", 0),
                arousal=em_data.get("arousal", 0),
            )
        return twin


# 全局数字分身管理器
_digital_twin_registry: Dict[str, UserDigitalTwin] = {}
_twin_lock = threading.Lock()


def get_user_digital_twin(user_id: str) -> UserDigitalTwin:
    """获取或创建用户数字分身"""
    with _twin_lock:
        if user_id not in _digital_twin_registry:
            _digital_twin_registry[user_id] = UserDigitalTwin(user_id)
        return _digital_twin_registry[user_id]


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
    # 进度回调 (2026-04-25 新增)
    progress: Optional[Callable[['AgentProgress'], None]] = None  # 进度更新
    # 任务分解回调 (2026-04-25 新增)
    task_decomposition: Optional[Callable[['TaskDecomposition'], None]] = None  # 分解完成
    task_progress: Optional[Callable[['TaskDecomposition'], None]] = None  # 子任务进度


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

        # 硬件感知模型选举（L0/L3/L4）
        self._election_result = None
        self._elected_l0: str = ""
        self._elected_l3: str = ""
        self._elected_l4: str = ""
        self._elected_tier: str = ""
        self._gpu_vram_gb: float = 0.0

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

        # ── L0 意图分类器（规则 + LLM 混合）──────────────────────
        self._l0_classifier: Optional[L0IntentClassifier] = None

        # ── 用户数字分身 ─────────────────────────────────────────
        self._user_twin: Optional[UserDigitalTwin] = None
        self._user_id = "default"  # 默认用户，后续可扩展多用户

        # 迭代控制
        self._iteration = 0
        self._max_iterations = config.agent.max_iterations
        self._interrupt_event = threading.Event()
        
        # ── 模型能力检测器 ─────────────────────────────────────────
        self._capability_detector = get_capability_detector(
            ollama_base_url=config.ollama.base_url
        )
        self._multimodal_filter = MultimodalMessageFilter(self._capability_detector)

        # ── 任务分解系统 ────────────────────────────────────────────
        self._decomposer = TaskDecomposer(llm_client=None)
        self._task_executor = SubTaskExecutor()
        self._current_decomposition: Optional[TaskDecomposition] = None

        # 延迟初始化模型客户端
        def init_model():
            try:
                self._init_model_client(backend)
            except Exception as e:
                logger.error(f"后台初始化模型客户端时出错: {e}")
        
        threading.Thread(target=init_model, daemon=True).start()

    def _init_model_client(self, backend: str):
        """初始化模型客户端

        backend="ollama": 直接使用 Ollama 服务（跳过本地模型加载）
        其他 backend: 优先使用本地 vLLM/llama-cpp，失败则回退 Ollama

        自动根据硬件配置选举 L0/L3/L4 模型
        """
        # ── 步骤 0：硬件感知模型选举 ──────────────────────────────
        try:
            from core.model_election import get_elected_models, print_election_report
            election_result = get_elected_models()
            self._election_result = election_result
            self._elected_l0 = election_result.l0_model
            self._elected_l3 = election_result.l3_model
            self._elected_l4 = election_result.l4_model
            self._elected_tier = election_result.tier_level
            self._gpu_vram_gb = election_result.gpu_vram_gb
            print_election_report(election_result)
        except Exception as e:
            logger.warning(f"模型选举失败: {e}，使用默认配置")
            self._elected_l0 = "smollm2:latest"
            self._elected_l3 = "qwen3.5:4b"
            self._elected_l4 = "qwen3.5:9b"
            self._elected_tier = "unknown"

        try:
            # 如果明确指定 ollama，直接创建 OllamaClient（跳过本地模型检测）
            if backend == "ollama":
                logger.info("使用 Ollama 后端")
                self.ollama = OllamaClient(self.config.ollama)
                self._use_unified = False
                self.model = self.ollama
                self._current_backend = ModelBackend.OLLAMA
                logger.info("Ollama 后端初始化成功")
                return

            # 以下处理 vllm / nano_vllm / llama-cpp
            # 首先检查所有后端的可用性
            available_backends = check_local_model_backends()

            # 获取模型路径
            model_path = self._get_default_gguf_model()

            # 根据 backend 参数选择后端
            if backend == "vllm":
                preferred = ModelBackend.VLLM
            elif backend == "nano_vllm":
                preferred = ModelBackend.NANO_VLLM
            elif backend == "llama-cpp":
                preferred = ModelBackend.LLAMA_CPP
            else:
                preferred = ModelBackend.VLLM

            # 如果找到模型路径，尝试使用本地后端
            if model_path:
                # 首先尝试使用统一模型客户端
                logger.debug("尝试使用统一模型客户端加载本地模型")
                try:
                    from core.unified_model_client import create_local_client
                    self.model = create_local_client(model_path)
                    self._use_unified = True
                    self._current_backend = ModelBackend.LLAMA_CPP
                    logger.info("统一模型客户端加载成功")
                    return
                except Exception as e:
                    logger.warning(f"统一模型客户端失败: {e}，尝试 llama-cpp...")

                # 尝试 llama-cpp
                logger.debug("尝试 llama-cpp 后端")
                result = self._priority_loader.load_model(
                    model_path=model_path,
                    backend_preference=preferred,
                    n_ctx=self.config.ollama.num_ctx,
                    n_gpu_layers=-1,
                    n_threads=4,
                )
                if result.success:
                    self._use_unified = False
                    self.model = result.client
                    self._current_backend = result.backend
                    logger.info(f"llama-cpp 成功，后端: {result.backend.value}")
                    return
                else:
                    logger.error(f"llama-cpp 失败: {result.message}")

            # 未找到本地模型或加载失败，回退到 Ollama
            logger.warning("回退到 Ollama 后端")
            self.ollama = OllamaClient(self.config.ollama)
            self._use_unified = False
            self.model = self.ollama
            self._current_backend = ModelBackend.OLLAMA
            logger.info("Ollama 后端初始化成功")

        except Exception as e:
            logger.error(f"模型客户端初始化失败: {e}")
            raise RuntimeError("无法初始化模型客户端")

        # ── L0 意图分类器 + 用户数字分身（所有路径后统一初始化）────
        try:
            self._l0_classifier = L0IntentClassifier(ollama_client=self.ollama)
            logger.info("L0 意图分类器初始化成功")
        except Exception as e:
            logger.warning(f"L0 意图分类器初始化失败: {e}")
            self._l0_classifier = L0IntentClassifier()

        try:
            self._user_twin = get_user_digital_twin(self._user_id)
            logger.info(f"用户数字分身初始化成功 (level={self._user_twin.level})")
        except Exception as e:
            logger.warning(f"用户数字分身初始化失败: {e}")

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
                logger.debug(f"找到默认本地模型: {model_path}")
                return model_path
            else:
                logger.debug("未找到有效的本地模型，跳过")
        
        # 传统方式查找模型
        models_dir = Path(self.config.model_path.models_dir or "models")

        # 支持的 GGUF 文件
        gguf_exts = [".gguf", ".gguf.bin"]

        # 扫描 models 目录
        if models_dir.exists():
            for f in models_dir.rglob("*"):
                # 过滤掉 mmproj 文件
                if f.suffix.lower() in gguf_exts and "mmproj" not in f.name.lower():
                    logger.debug(f"找到默认模型: {f}")
                    return str(f)

        return None

    def _get_current_model_name(self) -> str:
        """获取当前模型名称

        优先级：
        1. config.ollama.default_model（显式配置，优先）
        2. 硬件感知选举的 L4 模型（深度生成）
        3. fallback: qwen2.5:1.5b（系统中保证存在）
        """
        # 优先使用显式配置的模型（即使 _current_backend 尚未设置）
        if self.config.ollama.default_model:
            return self.config.ollama.default_model

        # 使用硬件感知选举的 L4 模型
        if self._elected_l4:
            return self._elected_l4

        if hasattr(self, "_current_backend") and self._current_backend is not None:
            if self._current_backend == ModelBackend.VLLM:
                model_path = self._get_default_gguf_model()
                if model_path:
                    return Path(model_path).stem
        # 默认返回保证存在的轻量模型
        return "qwen2.5:1.5b"

    def get_l0_model(self) -> str:
        """获取 L0 快反模型（用于意图分类/路由）"""
        if self.config.ollama.default_model:
            return self.config.ollama.default_model
        return self._elected_l0 or "smollm2:latest"

    def get_l3_model(self) -> str:
        """获取 L3 推理模型（用于意图理解）"""
        if self.config.ollama.default_model:
            return self.config.ollama.default_model
        return self._elected_l3 or "qwen3.5:4b"

    def get_l4_model(self) -> str:
        """获取 L4 深度模型（用于长文生成/思考）"""
        if self.config.ollama.default_model:
            return self.config.ollama.default_model
        return self._elected_l4 or "qwen3.5:9b"

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
            _init_timeout = _uconfig.get("agent.init_timeout", 10) if _uconfig else 10
            _init_poll = _uconfig.get("delays.polling_medium", 0.5) if _uconfig else 0.5
            start_time = time.time()
            while not self.ollama and not self.model:
                if time.time() - start_time > _init_timeout:  # 可配置超时
                    yield StreamChunk(error="模型客户端初始化超时，请检查 Ollama 服务是否正在运行")
                    return
                time.sleep(_init_poll)
        
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
                    logger.info(f"使用可用模型: {model_name}")
                # 调用 Ollama
                for chunk in self.ollama.chat(messages=messages, model=model_name, **kwargs):
                    yield chunk
                    if chunk.done:
                        break
                return
            except Exception as e:
                import traceback
                traceback.print_exc()
                logger.error(f"Ollama 调用出错: {e}")
            # 如果 Ollama 失败，不 fallback 到其他后端，直接报错
            yield StreamChunk(error=f"Ollama 调用失败: {e}")
            return
        
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
                        logger.debug(f"调用 Nano-vLLM generate_stream，提示词: {prompt[:100]}...")
                        for i, token in enumerate(self.model.generate_stream(prompt, sampling_params)):
                            logger.debug(f"收到 token {i}: {token}")
                            full_text += token
                            yield StreamChunk(delta=token)
                        
                        logger.debug(f"生成完成，总长度: {len(full_text)}")
                        yield StreamChunk(done=True, total_duration=0, eval_count=len(full_text))
                        return
                    except Exception as e:
                        logger.error(f"Nano-vLLM generate_stream 出错: {e}")
                        import traceback
                        traceback.print_exc()
                        # 尝试使用非流式方法
                        if hasattr(self.model, 'generate'):
                            logger.debug("尝试使用 generate 方法")
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
                logger.error(f"模型调用出错: {e}")

        # 所有后端都失败
        yield StreamChunk(error="无法连接到任何模型后端。请确保 Ollama 服务正在运行并已下载模型。")

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

    def _classify_query_type(self, query: str) -> str:
        """
        快速意图分类：将查询分为「对话」「任务」「搜索」三类

        分类逻辑（基于关键词和模式匹配，轻量快速）：
        - 对话 (DIALOGUE): 情感表达、寒暄、无具体任务动词
          例：「今天好累啊」「你好」「谢谢」
        - 任务 (TASK): 有明确的行动请求、代码/工具类关键词
          例：「帮我写代码」「帮我查」「打开」
        - 搜索 (SEARCH): 知识性提问、需要外部检索
          例：「什么是AI」「XXX的原理」「2024年GDP」

        Returns:
            "dialogue" | "task" | "search"
        """
        import re as _re
        query_lower = query.lower().strip()

        # ── 优先级 1：搜索关键词（任何包含搜索意图的短句）────────────
        # 修复bug：搜索词应优先于短句判断
        search_intent_words = (
            "搜索", "查找", "查询", "找一下", "找找",
            "吉奥", "相关", "内容", "资料", "信息",
            "帮我搜", "帮我查", "帮我找",
        )
        if any(kw in query for kw in search_intent_words):
            return "search"

        # ── 优先级 2：搜索类（疑问词开头/结尾 → 知识性提问）────────
        search_question_words = (
            "什么是", "什么是", "什么叫", "什么叫",
            "为什么", "为何", "怎么会",
            "怎么是", "怎么会", "怎么能",
            "怎么样", "怎么选", "怎么用", "怎么写",
            "如何", "哪有", "哪有",
            "是不是", "会不会", "能不能", "可不可以",
            "有多少", "哪个好", "哪个是",
            "在哪里", "是什么", "是哪个",
            "介绍一下", "解释一下", "说一说", "讲讲",
        )
        if any(query.startswith(q) for q in search_question_words):
            # 「是什么原理」「怎么做」→ task（有行动/技术词）
            task_suffixes = ("原理", "步骤", "实现", "代码", "编程", "写",
                           "安装", "部署", "配置", "运行", "调试")
            if any(kw in query for kw in task_suffixes):
                return "task"
            return "search"

        # 问号结尾 → 搜索
        if query.strip().endswith("？") or query.strip().endswith("?"):
            return "search"

        # ── 优先级 3：任务类（行动动词）──────────────────────────
        task_verbs = (
            "帮我", "帮我写", "帮我做", "帮我查", "帮我找",
            "帮我分析", "帮我计算", "帮我整理", "帮我翻译",
            "写一个", "写段", "生成", "创建", "打开", "启动",
            "做个", "做一下", "执行", "运行", "调用",
            "做个", "把", "给", "列出", "统计", "对比",
        )
        if any(kw in query for kw in task_verbs):
            return "task"

        # 代码/技术任务
        tech_keywords = (
            "python", "java", "javascript", "js", "sql", "api", "http",
            "代码", "编程", "函数", "算法", "安装", "部署",
            "配置", "运行", "调试", "编译", "接口",
            "数据库", "服务器", "文件", "代码",
        )
        if any(kw in query_lower for kw in tech_keywords):
            return "task"

        # ── 优先级 3：对话类（寒暄/情感/短句）────────────────────
        # 精确寒暄
        greetings = ("你好", "您好", "hi", "hello", "hey", "嗨",
                    "谢谢", "感谢", "多谢", "没事", "没关系",
                    "好吧", "行吧", "好的", "嗯嗯", "晚安",
                    "早安", "早上好", "下午好", "晚上好",
                    "再见", "拜拜", "下次见", "哈", "嗯")
        if query_lower in greetings:
            return "dialogue"

        # 情感/状态表达
        emotion_words = (
            "好累", "好困", "好烦", "好开心", "好难过", "好无聊",
            "好忙", "好舒服", "心情", "糟了", "完了",
        )
        if any(kw in query for kw in emotion_words):
            return "dialogue"

        # 纯语气词
        if _re.fullmatch(r"[哦嗯啊呀哈嘻嘛呢吧！?~。]+", query.strip()):
            return "dialogue"

        # 短句（≤12字）无明显任务 → 对话
        if len(query.strip()) <= 12:
            return "dialogue"

        # ── 默认：搜索 ─────────────────────────────────────────────
        return "search"

    def send_message(self, text: str) -> Iterator[StreamChunk]:
        """
        发送消息，启动对话循环，返回流式响应迭代器

        管道策略（按意图分类）：
        - dialogue: L0模型 + 无KB/深度搜索 → 快速情感回复
        - task: L3模型 + KB搜索 → 执行任务
        - search: L4模型 + KB + 深度搜索 → 知识性回答
        - emotion_aware: 情绪感知优先，影响回复风格
        """
        # ── 进度发射器 ────────────────────────────────────────────
        progress_emitter = ProgressEmitter(self.callbacks.progress)
        progress_emitter.start()
        
        # 追加用户消息
        self.session_db.append_message(self.session_id, "user", text)

        # 记录消息
        if self._session_stats:
            self._stats_tracker.record_message(self.session_id, "user")

        # ── 情绪感知：提取用户情感向量 ─────────────────────────────
        EmotionVector: type = object  # 类型提示占位
        try:
            _, EmotionVector, _, _ = _lazy_emotion_imports()
            emotion_vec = EmotionVector.from_text_analysis(text)
            logger.debug(f"情绪分析: {emotion_vec.dominant_emotion().value} "
                         f"(valence={emotion_vec.valence:.2f}, arousal={emotion_vec.arousal:.2f})")
        except Exception as e:
            logger.warning(f"情绪分析出错: {e}")
            emotion_vec = None

        # ── 意图分类：决定管道策略（L0分类器）─────────────────────
        progress_emitter.emit_phase(ProgressPhase.INTENT_CLASSIFY, "分析用户意图...")
        if self._l0_classifier:
            intent_result = self._l0_classifier.classify(text)
            query_type = intent_result["type"]
            intent_method = intent_result["method"]
            logger.debug(f"意图分类: {query_type} (方法={intent_method})")
        else:
            # 降级到旧的规则分类器
            query_type = self._classify_query_type(text)
            logger.debug(f"意图分类(降级): {query_type}")

        kb_results: List[Dict[str, Any]] = []
        deep_results: List[Dict[str, Any]] = []

        # ── 情绪感知优先：低落情绪先表达关心 ───────────────────────
        care_expressed = False
        if self._user_twin and emotion_vec:
            # 记录交互到数字分身
            self._user_twin.record_interaction(text, query_type, emotion_vec)
            # 判断是否需要表达关心
            if self._user_twin.should_express_care():
                care_text = self._user_twin.get_care_response()
                logger.debug(f"数字分身 → 表达关心: {care_text}")
                yield StreamChunk(delta=care_text)
                care_expressed = True

        kb_results: List[Dict[str, Any]] = []
        deep_results: List[Dict[str, Any]] = []

        # ── 任务分解：检测是否需要分解为子任务 ────────────────────
        should_decompose = (
            query_type == "task" and
            self._decomposer and
            self._decomposer.should_decompose(text)
        )

        if should_decompose:
            progress_emitter.emit_phase(ProgressPhase.THINKING, "分析任务结构...")

            # 分解任务
            decomposition = self._decomposer.decompose(text)
            self._current_decomposition = decomposition

            logger.info(f"任务分解: {decomposition.total_tasks} 个子任务 "
                        f"(策略: {decomposition.strategy.value})")

            # 触发 UI 回调 - 分解完成
            if self.callbacks.task_decomposition:
                self.callbacks.task_decomposition(decomposition)

            # 发送分解摘要
            summary = f"[任务分解] {decomposition.total_tasks} 个步骤：\n"
            for i, subtask in enumerate(decomposition.subtasks, 1):
                summary += f"{i}. {subtask.title}\n"
            yield StreamChunk(delta=summary)

            # 执行子任务
            progress_emitter.emit_phase(ProgressPhase.EXECUTING, "执行子任务...")

            def task_handler(subtask: SubTask) -> Any:
                """子任务处理器"""
                # 构建子任务提示
                subtask_prompt = f"请{text}，具体执行：{subtask.description}"
                subtask_results = []

                # 对每个子任务执行搜索
                try:
                    results = self._search_knowledge_base(subtask_prompt)
                    subtask_results.extend(results)
                except Exception as e:
                    logger.error(f"子任务搜索出错: {e}")

                # 返回结果
                return {
                    "subtask_id": subtask.task_id,
                    "results": subtask_results,
                    "prompt": subtask_prompt,
                }

            # 流式执行子任务
            for state in self._task_executor.execute_stream(decomposition, task_handler):
                # 触发 UI 回调 - 子任务进度
                if self.callbacks.task_progress:
                    self.callbacks.task_progress(state)

                # 输出当前进度
                progress_text = f"\n[进度 {state.progress_percent:.0f}%] "
                progress_text += f"{state.completed_tasks}/{state.total_tasks} 完成"
                yield StreamChunk(delta=progress_text)

        if query_type == "dialogue":
            # 对话类：跳过 KB/深度搜索，直接用 L0 轻量模型
            model_name = self.get_l0_model()
            logger.debug(f"对话类 → 跳过搜索，使用 L0 模型: {model_name}")
            progress_emitter.emit_phase(ProgressPhase.LLM_GENERATING, "生成回复...")
        else:
            # 任务/搜索类：完整管道
            # 1. 知识库搜索
            progress_emitter.emit_phase(ProgressPhase.KNOWLEDGE_SEARCH, "搜索知识库...")
            logger.debug("执行知识库搜索...")
            try:
                kb_results = self._search_knowledge_base(text)
                logger.info(f"知识库搜索完成，找到 {len(kb_results)} 条结果")
            except Exception as e:
                logger.error(f"知识库搜索出错: {e}")

            # 2. 深度搜索（仅搜索类）
            if query_type == "search":
                progress_emitter.emit_phase(ProgressPhase.DEEP_SEARCH, "执行深度搜索...")
                logger.debug("执行深度搜索...")
                try:
                    deep_results = asyncio.run(self._deep_search(text))
                    logger.info(f"深度搜索完成，找到 {len(deep_results)} 条结果")
                except Exception as e:
                    logger.error(f"深度搜索失败: {e}")

            # 3. 模型路由
            progress_emitter.emit_phase(ProgressPhase.MODEL_ROUTE, "选择最优模型...")
            logger.debug("执行模型路由...")
            model_name = self._route_model(text)
            logger.info(f"选择模型: {model_name}")
            
            progress_emitter.emit_phase(ProgressPhase.LLM_GENERATING, "正在生成回复...")

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

            # 推理回调 - 根据模型能力决定是否启用
            def reasoning_cb(delta: str):
                nonlocal reasoning_content
                reasoning_content += delta
                # 原有回调
                if self.callbacks.thinking:
                    self.callbacks.thinking(delta)
                # 进度回调（thinking 实时输出）
                progress_emitter.emit_thinking(delta)

            # 流式调用 LLM
            content_buffer = ""

            # 构建 kwargs
            llm_kwargs = {}
            if self._iteration == 0 and self._tool_schema:
                # TODO: llama-cpp 暂时不支持 tools，暂不传递
                if self.backend == "ollama":
                    llm_kwargs["tools"] = self._tool_schema
            
            # 根据模型能力决定是否传递 thinking 回调
            can_think = getattr(self, '_current_model_caps', None)
            if can_think and can_think.can_stream_think():
                # 模型支持流式 thinking，启用回调
                if reasoning_cb:
                    llm_kwargs["reasoning_callback"] = reasoning_cb
                logger.debug("启用流式 thinking 输出")
            else:
                # 模型不支持 thinking，不传递回调
                if "reasoning_callback" in llm_kwargs:
                    del llm_kwargs["reasoning_callback"]
                if can_think:
                    logger.debug("模型不支持流式 thinking，跳过")

            # ── 统一调用 _llm_chat（它处理 Ollama/本地模型/HTTP） ──
            for chunk in self._llm_chat(messages, **llm_kwargs):
                # 流式文本：yield 出去让 caller 收到
                if chunk.delta:
                    content_buffer += chunk.delta
                    assistant_text += chunk.delta
                    yield chunk
                    if self.callbacks.stream_delta:
                        self.callbacks.stream_delta(chunk.delta)
                    # 进度回调（流式输出）
                    progress_emitter.emit_stream(chunk.delta)

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
                    # 进度完成
                    progress_emitter.complete("回答已生成")
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

            # 记录到数字分身（工具使用习惯）
            if self._user_twin:
                self._user_twin.record_tool_usage(name)
            
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
            kb_results = self.knowledge_base.search(query, top_k=3)
            
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
            logger.error(f"知识库搜索出错: {e}")
            return []

    async def _deep_search(self, query: str) -> List[Dict[str, Any]]:
        """深度搜索（带降级、纠错和知识库自动存储机制）"""
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
            
            # 如果没有结果，尝试纠错后重试
            if not search_results:
                logger.info("深度搜索无结果，尝试纠错重试...")
                corrected_query = self._fix_typo(query)
                if corrected_query and corrected_query != query:
                    logger.debug(f"纠错后的查询: {corrected_query}")
                    results = await self.tier_router.search(corrected_query, num_results=5)
                    for result in results:
                        search_results.append({
                            "content": f"[纠错] {result.title} " + result.content[:100],
                            "score": result.score,
                            "type": "deep_search",
                            "url": result.url,
                            "source": result.source
                        })
            
            # 如果仍然没有结果，降级到 web_search
            if not search_results:
                logger.warning("深度搜索失败，降级到 web_search...")
                web_results = self._web_search_fallback(query)
                if web_results:
                    logger.info(f"web_search 降级成功，找到 {len(web_results)} 条结果")
                    search_results = web_results
                    
                    # 自动将 web_search 结果存入知识库（供下次搜索命中）
                    self._store_search_results_to_kb(query, web_results)
            
            # 如果有搜索结果，也存入知识库
            elif search_results and not any('web_search_fallback' in str(r) for r in search_results):
                self._store_search_results_to_kb(query, search_results)
            
            return search_results
        except Exception as e:
            logger.error(f"深度搜索出错: {e}")
            # 出错时也尝试 web_search 降级
            logger.error("异常降级到 web_search...")
            web_results = self._web_search_fallback(query)
            if web_results:
                self._store_search_results_to_kb(query, web_results)
            return web_results
    
    def _store_search_results_to_kb(self, query: str, results: List[Dict[str, Any]]) -> None:
        """将搜索结果存入知识库"""
        try:
            if not results:
                return
            
            # 提取关键信息存入知识库
            for result in results[:3]:  # 最多存3条
                content = result.get('content', '')
                url = result.get('url', '')
                source = result.get('source', '')
                
                if content and len(content) > 20:
                    # 存入知识库
                    self.knowledge_base.add_knowledge(
                        content=content,
                        source=f"搜索:{source}",
                        query=query,
                        url=url
                    )
                    logger.info(f"已存入知识库: {content[:50]}...")
        except Exception as e:
            logger.error(f"存入知识库失败: {e}")
    
    def _fix_typo(self, query: str) -> Optional[str]:
        """
        简单的错别字纠错（基于常见错误模式）
        
        返回纠错后的查询，如果无需纠错则返回 None
        """
        # 常见错别字映射（根据用户反馈：吉奥环鹏 → 吉奥环朋）
        typo_fixes = {
            "鹏": "朋",
            "朋": "鹏",
            "地": "的",
            "的": "地",
            "在": "再",
            "再": "在",
            "做": "作",
            "作": "做",
        }
        
        # 检查查询中是否包含常见错别字
        for wrong, correct in typo_fixes.items():
            if wrong in query:
                # 只对中文词汇进行纠错
                fixed = query.replace(wrong, correct, 1)  # 只替换第一个
                return fixed
        
        return None
    
    def _web_search_fallback(self, query: str) -> List[Dict[str, Any]]:
        """
        web_search 降级搜索
        
        当 TierRouter 搜索失败时，使用 web_search 作为降级方案
        """
        try:
            # 导入 web_search 工具
            import urllib.request
            import urllib.parse
            import json
            import re
            
            # 使用 DuckDuckGo HTML 搜索（无需 API Key）
            encoded_query = urllib.parse.quote(query)
            url = f"https://duckduckgo.com/html/?q={encoded_query}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            req = urllib.request.Request(url, headers=headers)
            _search_timeout = _uconfig.get("timeouts.search", 15) if _uconfig else 15
            with urllib.request.urlopen(req, timeout=_search_timeout) as response:
                html = response.read().decode('utf-8', errors='ignore')
            
            # 解析搜索结果
            results = []
            
            # DuckDuckGo HTML 结果解析
            pattern = r'<a class="result__a" href="([^"]+)"[^>]*>([^<]+)</a>'
            matches = re.findall(pattern, html)
            
            # 摘要解析
            snippet_pattern = r'<a class="result__snippet"[^>]*>([^<]+)</a>'
            snippets = re.findall(snippet_pattern, html)
            
            for i, (url, title) in enumerate(matches[:5]):
                # 清理 HTML 实体
                title = re.sub(r'<[^>]+>', '', title)
                title = re.sub(r'&[^;]+;', '', title)
                
                snippet = snippets[i] if i < len(snippets) else ""
                snippet = re.sub(r'<[^>]+>', '', snippet)
                snippet = re.sub(r'&[^;]+;', '', snippet)
                
                results.append({
                    "content": f"{title}: {snippet[:150]}",
                    "score": 0.8 - i * 0.1,
                    "type": "web_search_fallback",
                    "url": url,
                    "source": "duckduckgo"
                })
            
            return results
            
        except Exception as e:
            logger.error(f"web_search 降级失败: {e}")
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
                model_name = result.model.name
            else:
                model_name = self._get_current_model_name()
            
            # ── 检测模型能力 ─────────────────────────────────────────
            if hasattr(self, '_capability_detector'):
                caps = self._capability_detector.detect(model_name)
                logger.debug(f"模型能力: {caps.get_capability_summary()}")
                
                # 存储当前模型能力（用于流式输出决策）
                self._current_model_caps = caps
            else:
                self._current_model_caps = None
            
            return model_name
        except Exception as e:
            logger.error(f"模型路由出错: {e}")
            model_name = self._get_current_model_name()
            self._current_model_caps = None
            return model_name

    def _build_enhanced_prompt(self, query: str, kb_results: List[Dict], deep_results: List[Dict]) -> str:
        """构建增强的提示"""
        prompt_parts = []

        # 系统提示
        prompt_parts.append(
            "你是生命之树AI（LivingTreeAl），一款由 AI 驱动的桌面助手，运行在本地 Windows 环境中。"
            "你可以通过各种工具来帮助用户完成任务。"
        )

        # ── 数字分身上下文（用户画像 + 情感状态）──────────────────
        if self._user_twin:
            twin_context = self._user_twin.get_context_for_prompt()
            if twin_context:
                prompt_parts.append(f"\n## 用户数字分身上下文\n{twin_context}\n")

        # ── 知识库结果 ─────────────────────────────────────────────
        if kb_results:
            prompt_parts.append("\n## 知识库信息")
            for i, result in enumerate(kb_results[:3], 1):
                content = result.get("content", "").strip()
                if content:
                    prompt_parts.append(f"{i}. {content}")

        # ── 深度搜索结果 ─────────────────────────────────────────
        if deep_results:
            prompt_parts.append("\n## 搜索结果")
            for i, result in enumerate(deep_results[:3], 1):
                content = result.get("content", "").strip()
                if content:
                    prompt_parts.append(f"{i}. {content}")

        # ── 用户查询 ──────────────────────────────────────────────
        prompt_parts.append(f"\n## 用户问题\n{query}")
        prompt_parts.append("\n请基于以上信息，提供详细、准确的回答。")

        return "\n".join(prompt_parts)

    # ── 模型能力检测 ─────────────────────────────────────────────────

    def get_model_capabilities(self, model_name: str = None) -> "ModelCapabilities":
        """
        获取模型能力信息

        Args:
            model_name: 模型名称，默认使用当前模型

        Returns:
            ModelCapabilities: 模型能力描述
        """
        if model_name is None:
            model_name = self._get_current_model_name()

        if hasattr(self, '_capability_detector'):
            return self._capability_detector.detect(model_name)
        return None

    def check_multimodal_support(self, content_type: str) -> bool:
        """
        检查当前模型是否支持特定多模态内容

        Args:
            content_type: 内容类型（"image", "audio", "video"）

        Returns:
            True 如果支持
        """
        model_name = self._get_current_model_name()
        caps = self.get_model_capabilities(model_name)

        if caps is None:
            return False

        return self._capability_detector.can_process_multimodal(model_name, content_type)

    def filter_multimodal_message(
        self, messages: List[dict]
    ) -> tuple[List[dict], List[str]]:
        """
        过滤消息中不支持的多模态内容

        Args:
            messages: 消息列表

        Returns:
            (过滤后的消息, 被过滤的内容描述列表)
        """
        model_name = self._get_current_model_name()
        return self._multimodal_filter.filter_messages(model_name, messages)

    # ── 任务分解接口 ─────────────────────────────────────────────────

    def should_decompose_task(self, task: str) -> bool:
        """
        判断任务是否需要分解

        Args:
            task: 任务描述

        Returns:
            True 如果需要分解
        """
        return self._decomposer.should_decompose(task)

    def decompose_task(self, task: str) -> TaskDecomposition:
        """
        手动分解任务

        Args:
            task: 任务描述

        Returns:
            TaskDecomposition: 分解结果
        """
        return self._decomposer.decompose(task)

    def get_current_decomposition(self) -> Optional[TaskDecomposition]:
        """
        获取当前任务的分解结果

        Returns:
            当前分解结果，如果未分解则返回 None
        """
        return self._current_decomposition

    def interrupt_task(self):
        """中断当前任务执行"""
        self._interrupt_event.set()
        self._task_executor.interrupt()

    def execute_decomposition(
        self,
        decomposition: TaskDecomposition,
        task_handler: Callable[[SubTask], Any] = None,
    ) -> Iterator[TaskDecomposition]:
        """
        执行任务分解（手动模式）

        Args:
            decomposition: 分解结果
            task_handler: 自定义任务处理器

        Yields:
            TaskDecomposition: 每个步骤完成后的状态
        """
        for state in self._task_executor.execute_stream(decomposition, task_handler):
            yield state
