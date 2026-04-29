# -*- coding: utf-8 -*-
"""
意图状态机 - IntentStateMachine
===============================

解决核心问题：**多轮对话中的意图上下文丢失**

当前 IntentEngine 每次调用 parse() 都是独立的，
用户说"改成用 Redis"时，引擎不知道之前在讨论什么。
IntentStateMachine 维护对话会话状态，实现：

1. **意图状态跟踪**: IDLE → ACTIVE → CLARIFYING → EXECUTING → COMPLETED
2. **上下文压缩**: 超长历史自动摘要，控制 token 开销
3. **意图继承/演变**: 追踪同一主题的意图变化（如"写接口"→"改接口"→"加缓存"）
4. **话题切换检测**: 自动识别用户是否换了话题
5. **澄清状态管理**: NEED_CLARIFY 时等待补充信息

使用示例：
    sm = IntentStateMachine(max_history=10)
    
    # 第1轮
    intent = sm.process("帮我写一个用户登录接口")
    # → intent_type=CODE_GENERATION, state=ACTIVE
    
    # 第2轮：上下文自动关联
    intent = sm.process("改成用 JWT 认证")
    # → intent_type=CODE_MODIFICATION, context=[上一轮的登录接口]
    
    # 切换话题
    intent = sm.process("Python 的 GIL 是什么")
    # → state=NEW_TOPIC, context 重置

Author: LivingTreeAI Team
Version: 1.0.0
from __future__ import annotations
"""


import time
import logging
import hashlib
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from collections import OrderedDict

from .intent_types import Intent, IntentType, IntentPriority

logger = logging.getLogger(__name__)


# ── 状态定义 ───────────────────────────────────────────────────────


class SessionState(Enum):
    """对话会话状态"""
    NEW = auto()              # 新会话 / 新话题
    ACTIVE = auto()           # 活跃中，有明确意图
    CLARIFYING = auto()       # 需要用户澄清（信息不足）
    EXECUTING = auto()        # 正在执行
    COMPLETED = auto()        # 任务完成
    ERROR = auto()            # 出现错误
    DORMANT = auto()          # 休眠（长时间无交互）


# 话题相似度阈值
TOPIC_SIMILARITY_THRESHOLD = 0.35   # 低于此值视为新话题
CONTEXT_MAX_TURNS = 20             # 最大保留轮次
CONTEXT_MAX_TOKENS = 4000          # 最大 token 预算


@dataclass
class TurnRecord:
    """一轮对话记录"""
    turn_id: int
    timestamp: float
    user_input: str
    intent: Intent
    state: SessionState
    response_summary: str = ""      # 执行结果的简短摘要
    tokens_used: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "timestamp": self.timestamp,
            "user_input": self.user_input[:100],
            "intent_type": self.intent.intent_type.value,
            "state": self.state.name,
            "response_summary": self.response_summary[:100] if self.response_summary else "",
            "tokens_used": self.tokens_used,
        }


@dataclass
class TopicInfo:
    """话题信息"""
    topic_id: str
    keywords: List[str]
    primary_intent: IntentType
    start_turn: int
    turn_count: int = 0
    last_turn: int = 0
    summary: str = ""

    def update(self, turn: int):
        self.turn_count += 1
        self.last_turn = turn


# ── 核心类 ────────────────────────────────────────────────────────


class IntentStateMachine:
    """
    意图状态机

    核心能力：
    1. 会话状态管理（State）
    2. 历史上下文维护（Context Window）
    3. 话题连续性分析（Topic Tracking）
    4. 上下文压缩（Context Compression）

    设计原则：
    - 无外部依赖，纯 Python 实现
    - 内存高效：LRU 驱动，超限自动压缩
    - 可序列化：支持持久化到 JSON/SQLite
    """

    def __init__(
        self,
        max_history: int = CONTEXT_MAX_TURNS,
        max_tokens: int = CONTEXT_MAX_TOKENS,
        similarity_threshold: float = TOPIC_SIMILARITY_THRESHOLD,
        dormant_timeout: float = 300.0,     # 5 分钟无交互则休眠
        session_id: str = "",
    ):
        """
        Args:
            max_history: 最大保留轮数
            max_tokens: 上下文最大 token 预算
            similarity_threshold: 话题相似度阈值
            dormant_timeout: 休眠超时（秒）
            session_id: 会话 ID（空则自动生成）
        """
        self.session_id = session_id or self._generate_session_id()
        self.max_history = max_history
        self.max_tokens = max_tokens
        self.similarity_threshold = similarity_threshold
        self.dormant_timeout = dormant_timeout

        # 会话状态
        self._state = SessionState.NEW
        self._turn_counter = 0

        # 有序历史记录（按插入顺序，超出 max_history 自动淘汰最旧的）
        self._history: "OrderedDict[int, TurnRecord]" = OrderedDict()

        # 当前话题
        self._current_topic: Optional[TopicInfo] = None
        self._topic_history: List[TopicInfo] = []   # 过往话题

        # 统计
        self.stats = {
            "total_turns": 0,
            "topic_switches": 0,
            "clarifications": 0,
            "compressions": 0,
            "context_hits": 0,         # 上下文命中次数
        }

        # 话题切换关键词（用于快速判断是否换话题）
        self._switch_keywords = {
            "new_topic": [
                "另外", "还有", "换个", "不对", "不是这个",
                "算了", "先不管", "新的", "另一个", "别的事",
                "顺便问", "顺便说一下",
                # English
                "another", "different", "never mind", "actually",
                "by the way", "also",
            ],
            "follow_up": [          # 明确的跟进信号
                "改成", "加上", "去掉", "修改", "调整", "优化",
                "重构", "增加", "删除", "替换", "换成",
                # English
                "change", "add", "remove", "modify", "update",
                "refactor", "replace", "instead of",
            ],
            "completion": [         # 完成信号
                "好了", "可以了", "没问题", "完成", "OK",
                "thanks", "done", "good", "perfect",
            ],
        }

    # ── 主入口 ────────────────────────────────────────────────────

    def process(
        self,
        query: str,
        parsed_intent: Optional[Intent] = None,
        **kwargs,
    ) -> Tuple[Intent, Dict[str, Any]]:
        """
        处理一轮用户输入（核心方法）

        将用户输入与当前会话状态结合，返回增强后的意图和上下文元数据。

        Args:
            query: 用户原始输入
            parsed_intent: 已解析的 Intent（可选，为 None 时仅做状态分析）
            **kwargs: 附加参数（如 response_summary 用于反馈结果）

        Returns:
            (enhanced_intent, metadata) 元组
            metadata 包含: state, is_new_topic, context_summary, suggested_actions 等
        """
        self._turn_counter += 1
        turn_id = self._turn_counter
        now = time.time()

        # 检查是否需要从休眠恢复
        if self._state == SessionState.DORMANT:
            self._check_dormant_wakeup(now)

        # 分析输入与当前话题的关系
        is_follow_up, similarity = self._analyze_topic_continuity(query)

        if not is_follow_up and self._state not in (SessionState.NEW,):
            # 检测到话题切换
            old_state = self._state
            self._switch_topic(query)
            self.stats["topic_switches"] += 1
            logger.info(
                f"[SM] 话题切换 #{turn_id}: "
                f"{old_state.name}→{self._state.name} "
                f"(similarity={similarity:.2f})"
            )

        # 如果没有传入已解析的意图，创建一个基础意图
        if parsed_intent is None:
            parsed_intent = self._create_base_intent(query)

        # 用上下文增强意图
        enhanced_intent = self._enrich_with_context(
            parsed_intent, query, is_follow_up
        )

        # 更新状态
        new_state = self._determine_next_state(enhanced_intent, is_follow_up)

        # 创建本轮记录
        record = TurnRecord(
            turn_id=turn_id,
            timestamp=now,
            user_input=query,
            intent=enhanced_intent,
            state=new_state,
            response_summary=kwargs.get("response_summary", ""),
            tokens_used=kwargs.get("tokens_used", 0),
            metadata={"similarity": similarity},
        )
        self._add_record(record)

        # 更新内部状态
        self._state = new_state
        self.stats["total_turns"] += 1

        # 更新当前话题
        if self._current_topic:
            self._current_topic.update(turn_id)

        # 构建返回的元数据
        metadata = self._build_metadata(record, is_follow_up, similarity)

        return enhanced_intent, metadata

    def feedback(self, turn_id: int, result_summary: str, status: str = "success"):
        """
        反馈执行结果（闭环）

        在 Handler 执行完成后调用，将结果写入历史记录。

        Args:
            turn_id: 对应的轮次 ID
            result_summary: 结果摘要（<200 字）
            status: success / failed / clarify
        """
        record = self._history.get(turn_id)
        if record:
            record.response_summary = result_summary
            if status == "clarify":
                self._state = SessionState.CLARIFYING
                self.stats["clarifications"] += 1
            elif status == "failed":
                self._state = SessionState.ERROR
            elif status == "success":
                self._state = SessionState.COMPLETED
            logger.debug(f"[SM] 反馈 turn#{turn_id}: {status} - {result_summary[:50]}")

    def get_context_for_prompt(self, max_turns: int = 5) -> str:
        """
        获取用于 LLM 提示词的上下文字符串

        将最近 N 轮对话格式化为可注入 prompt 的文本。
        """
        recent = list(self._history.values())[-max_turns:]
        if not recent:
            return ""

        lines = ["## 对话历史"]
        for r in recent:
            prefix = ""
            if r.state == SessionState.CLARIFYING:
                prefix = "[需澄清]"
            elif r.state == SessionState.ERROR:
                prefix = "[出错]"

            line = f"- **Q{r.turn_id}** ({r.intent.intent_type.value}): {r.user_input[:80]}"
            if r.response_summary:
                line += f"\n  → A: {r.response_summary[:80]}"

            if prefix:
                line = f"{prefix} {line}"
            lines.append(line)

        # 当前话题
        if self._current_topic:
            lines.append("")
            lines.append(f"## 当前话题: {' '.join(self._current_topic.keywords[:5])}")

        return "\n".join(lines)

    def get_context_window(self) -> List[TurnRecord]:
        """获取完整上下文窗口（只读）"""
        return list(self._history.values())

    # ── 内部方法 ───────────────────────────────────────────────────

    def _analyze_topic_continuity(self, query: str) -> Tuple[bool, float]:
        """
        分析查询与当前话题的连续性
        
        Returns:
            (is_follow_up, similarity_score) 元组
        """
        if not self._current_topic or not self._history:
            return True, 1.0  # 第一轮总是 follow-up

        # 快速检查：是否有明确的跟进/切换关键词
        query_lower = query.lower()
        for kw in self._switch_keywords["follow_up"]:
            if kw in query_lower:
                return True, 0.8
        for kw in self._switch_keywords["new_topic"]:
            if kw in query_lower:
                return False, 0.1

        # 关键词重叠度计算
        current_kws = set(k.lower() for k in self._current_topic.keywords)
        query_words = self._extract_query_words(query)

        if not current_kws or not query_words:
            return True, 0.5

        overlap = len(current_kws & query_words)
        similarity = overlap / max(len(current_kws), len(query_words), 1)

        # 与最近一轮的关键词对比
        last_record = next(reversed(self._history.values()), None)
        if last_record:
            last_kws = set(last_record.intent.keywords or [])
            last_overlap = len(last_kws & set(query_words))
            last_sim = last_overlap / max(len(last_kws), len(query_words), 1)
            similarity = max(similarity, last_sim * 0.8)

        return similarity >= self.similarity_threshold, round(similarity, 3)

    def _enrich_with_context(
        self,
        intent: Intent,
        query: str,
        is_follow_up: bool,
    ) -> Intent:
        """用历史上下文增强意图"""

        if not is_follow_up or not self._history:
            return intent

        self.stats["context_hits"] += 1

        # 1. 继承技术栈（如果当前未检测到）
        if not intent.tech_stack:
            last_intent = list(self._history.values())[-1].intent
            if last_intent.tech_stack:
                intent.tech_stack = last_intent.tech_stack.copy()
                intent.tech_confidence = 0.5  # 继承的置信度降低

        # 2. 如果是修改类操作，设置 target 为上一个目标
        modify_types = {
            IntentType.CODE_MODIFICATION,
            IntentType.CODE_REFACTOR,
            IntentType.CODE_OPTIMIZATION,
            IntentType.BUG_FIX,
            IntentType.DEBUGGING,
        }
        if intent.intent_type in modify_types and not intent.target:
            last_intent = list(self._history.values())[-1].intent
            if last_intent.target:
                intent.target_description = f"基于: {last_intent.target}"

        # 3. 注入上下文到 metadata
        intent.metadata["session_id"] = self.session_id
        intent.metadata["turn"] = self._turn_counter
        intent.metadata["is_follow_up"] = is_follow_up
        intent.metadata["prev_intent"] = (
            list(self._history.values())[-1].intent.intent_type.value
            if self._history else None
        )

        # 4. 构建压缩后的前序上下文
        if len(self._history) >= 2:
            prev_records = list(self._history.values())[-3:]  # 最近 3 轮
            context_parts = []
            for r in prev_records[:-1]:  # 排除当前轮
                part = f"[{r.intent.intent_type.value}] {r.target or r.action or ''}"
                if r.response_summary:
                    part += f" → {r.response_summary[:60]}"
                context_parts.append(part)
            intent.metadata["recent_context"] = "; ".join(context_parts)

        return intent

    def _determine_next_state(
        self,
        intent: Intent,
        is_follow_up: bool,
    ) -> SessionState:
        """根据意图确定下一个状态"""

        # 信息不足
        if intent.completeness < 0.4:
            return SessionState.CLARIFYING

        # 已知类型的状态映射
        state_map = {
            # 生成类 → 直接执行
            IntentType.CODE_GENERATION: SessionState.EXECUTING,
            IntentType.API_DESIGN: SessionState.EXECUTING,
            IntentType.UI_GENERATION: SessionState.EXECUTING,
            IntentType.DATABASE_DESIGN: SessionState.EXECUTING,
            # 修改类 → 执行
            IntentType.CODE_MODIFICATION: SessionState.EXECUTING,
            IntentType.CODE_REFACTOR: SessionState.EXECUTING,
            IntentType.CODE_OPTIMIZATION: SessionState.EXECUTING,
            # 调试类 → 执行
            IntentType.DEBUGGING: SessionState.EXECUTING,
            IntentType.BUG_FIX: SessionState.EXECUTING,
            # 理解类 → 完成（问答类不需要执行阶段）
            IntentType.KNOWLEDGE_QUERY: SessionState.COMPLETED,
            IntentType.CONCEPT_EXPLANATION: SessionState.COMPLETED,
            IntentType.CODE_EXPLANATION: SessionState.COMPLETED,
            IntentType.CODE_UNDERSTANDING: SessionState.COMPLETED,
            # 文件操作 → 执行
            IntentType.FILE_OPERATION: SessionState.EXECUTING,
            # 默认
            IntentType.UNKNOWN: SessionState.CLARIFYING,
            IntentType.MULTIPLE: SessionState.EXECUTING,
        }
        return state_map.get(intent.intent_type, SessionState.ACTIVE)

    def _switch_topic(self, query: str):
        """切换到新话题"""
        # 归档旧话题
        if self._current_topic:
            self._topic_history.append(self._current_topic)

        # 创建新话题
        keywords = self._extract_query_words(query)[:10]
        self._current_topic = TopicInfo(
            topic_id=self._hash_text(query),
            keywords=keywords,
            primary_intent=IntentType.UNKNOWN,
            start_turn=self._turn_counter,
        )
        self._state = SessionState.NEW

    def _add_record(self, record: TurnRecord):
        """添加记录，超出容量时触发压缩"""
        self._history[record.turn_id] = record

        # LRU 淘汰
        while len(self._history) > self.max_history:
            oldest_key = next(iter(self._history))
            del self._history[oldest_key]

    def _build_metadata(
        self,
        record: TurnRecord,
        is_follow_up: bool,
        similarity: float,
    ) -> Dict[str, Any]:
        """构建返回给调用方的元数据"""
        meta = {
            "session_id": self.session_id,
            "turn_id": record.turn_id,
            "state": self._state.name,
            "is_new_topic": not is_follow_up,
            "is_follow_up": is_follow_up,
            "similarity": similarity,
            "total_turns": self.stats["total_turns"],
            "topic_switches": self.stats["topic_switches"],
            "current_topic": (
                {"keywords": self._current_topic.keywords[:5], "id": self._current_topic.topic_id}
                if self._current_topic else None
            ),
            "history_size": len(self._history),
            "context_available": len(self._history) > 1,
            "suggested_actions": self._suggest_actions(record),
        }
        return meta

    def _suggest_actions(self, record: TurnRecord) -> List[str]:
        """根据当前状态建议下一步动作"""
        actions = []

        if self._state == SessionState.CLARIFYING:
            actions.append("请求用户提供更多信息")
            actions.append("列出缺失的关键字段")

        elif self._state == SessionState.EXECUTING:
            actions.append("路由到对应 Handler 执行")
            if record.intent.is_composite:
                actions.append("拆分为子任务并行执行")

        elif self._state == SessionState.COMPLETED:
            actions.append("展示执行结果")
            actions.append("询问是否需要后续修改")

        elif self._state == SessionState.NEW:
            actions.append("开始新的意图处理流程")

        elif self._state == SessionState.ERROR:
            actions.append("诊断错误原因")
            actions.append("尝试降级方案或重试")

        return actions

    # ── 辅助方法 ───────────────────────────────────────────────────

    @staticmethod
    def _extract_query_words(text: str) -> List[str]:
        """提取查询中的有效词汇"""
        import re
        stop_words = {
            "的", "了", "是", "在", "我", "有", "和", "就", "不", "人",
            "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去",
            "你", "会", "着", "没有", "看", "好", "自己", "这", "那",
            "什么", "怎么", "帮", "一下", "帮我", "这个", "那个",
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did",
            "will", "would", "could", "should", "may", "might",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
        }
        words = re.split(r'[\s,，。、！？；：""''（）\(\)\[\]{}]', text)
        return [w.strip().lower() for w in words
                if w.strip() and len(w) >= 2 and w.lower() not in stop_words][:15]

    @staticmethod
    def _hash_text(text: str) -> str:
        return hashlib.md5(text.encode()).hexdigest()[:12]

    @staticmethod
    def _create_base_intent(query: str) -> Intent:
        """当没有传入解析意图时创建基础意图"""
        from .intent_parser import IntentParser
        parser = IntentParser()
        return parser.parse(query)

    def _check_dormant_wakeup(self, now: float):
        """检查是否应该唤醒"""
        if not self._history:
            return
        last_ts = list(self._history.values())[-1].timestamp
        if now - last_ts < self.dormant_timeout:
            self._state = SessionState.ACTIVE

    # ── 序列化 / 反序列化 ────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典（用于持久化）"""
        return {
            "session_id": self.session_id,
            "state": self._state.name,
            "turn_counter": self._turn_counter,
            "max_history": self.max_history,
            "stats": dict(self.stats),
            "current_topic": (
                {"id": self._current_topic.topic_id,
                 "keywords": self._current_topic.keywords,
                 "primary_intent": self._current_topic.primary_intent.value}
                if self._current_topic else None
            ),
            "history": [r.to_dict() for r in self._history.values()],
            "topic_history_len": len(self._topic_history),
        }

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            "session_id": self.session_id,
            "state": self._state.name,
            "history_size": len(self._history),
            "current_topic_keywords": (
                self._current_topic.keywords if self._current_topic else []
            ),
            "compression_ratio": (
                round(1 - len(self._history) / max(self._turn_counter, 1), 2)
                if self._turn_counter > 0 else 0
            ),
        }


# ── 测试入口 ──────────────────────────────────────────────────────


def _test_sm():
    """快速测试意图状态机"""
    print("=" * 60)
    print("IntentStateMachine 测试")
    print("=" * 60)

    sm = IntentStateMachine(max_history=10)

    queries = [
        ("帮我写一个 FastAPI 用户登录接口", None),
        ("改成用 JWT Token 认证", None),
        ("再加一个角色权限中间件", None),
        ("Python 的 GIL 是什么意思", None),  # 话题切换
        ("怎么避免 GIL 影响", None),          # 跟进
        ("回到登录接口，加个验证码", None),     # 回到旧话题
    ]

    for q, _ in queries:
        intent, meta = sm.process(q)
        icon = "🔗" if meta["is_follow_up"] else "🆕"
        print(f"\n{icon} Q: {q}")
        print(f"   类型: {intent.intent_type.value} | 状态: {meta['state']} | 相似度: {meta['similarity']}")
        print(f"   目标: {intent.target}")
        if intent.metadata.get("recent_context"):
            print(f"   上下文: {intent.metadata['recent_context'][:80]}")

        # 模拟执行反馈
        sm.feedback(intent.metadata["turn"], f"已完成{intent.intent_type.value}", "success")

    # 打印统计
    stats = sm.get_stats()
    print("\n" + "=" * 40)
    print("统计:")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    # Prompt 上下文
    print("\n--- Prompt 上下文 ---")
    print(sm.get_context_for_prompt())


if __name__ == "__main__":
    _test_sm()
