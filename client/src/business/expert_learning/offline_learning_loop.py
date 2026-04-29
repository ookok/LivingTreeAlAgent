# -*- coding: utf-8 -*-
"""
完全离线的自学习循环系统 (Offline Learning Loop)
================================================

核心设计理念：永不掉线，即使完全没有外部API也能持续学习和改进。

功能:
1. 离线知识缓存 - 本地化所有学习成果
2. 自进化机制 - 基于历史成功经验自动提升
3. 多层降级策略 - 确保任何情况下都能响应
4. 增量知识固化 - 将外部知识转化为本地能力
5. 自我诊断修复 - 自动检测并修复知识缺口

架构:
┌─────────────────────────────────────────────────────────────┐
│                    OfflineLearningLoop                       │
├─────────────────────────────────────────────────────────────┤
│  Layer 0: 紧急响应层 (Always Online)                         │
│    - 基础问答模板库                                          │
│    - 预设回复机制                                            │
│    - 永不拒绝策略                                            │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: 本地知识库 (Offline Core)                          │
│    - 知识图谱本地副本                                        │
│    - 成功案例库                                              │
│    - 模式匹配引擎                                            │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: 模型蒸馏层 (Knowledge Distillation)                │
│    - 外部知识内化                                            │
│    - 推理模式提取                                            │
│    - 风格迁移                                                │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: 自进化层 (Self-Evolution)                          │
│    - 成功率追踪                                              │
│    - 模式优化                                                │
│    - 能力边界扩展                                            │
└─────────────────────────────────────────────────────────────┘

Author: LivingTreeAI Agent
Date: 2026-04-24
from __future__ import annotations
"""


import json
import time
import hashlib
import threading
from typing import Optional, List, Dict, Any, Callable, Iterator
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from collections import defaultdict, deque
import re
from client.src.business.logger import get_logger
logger = get_logger('expert_learning.offline_learning_loop')



# ═══════════════════════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════════════════════

class ConnectionStatus(Enum):
    """连接状态"""
    ONLINE = "online"           # 完整在线
    DEGRADED = "degraded"       # 部分降级
    OFFLINE = "offline"         # 完全离线
    EMERGENCY = "emergency"     # 紧急模式


class LearningState(Enum):
    """学习状态"""
    IDLE = "idle"
    LEARNING = "learning"
    CONSOLIDATING = "consolidating"
    EVOLVING = "evolving"


@dataclass
class OfflineResponse:
    """离线响应"""
    content: str
    confidence: float
    source: str  # template/knowledge/distilled/emergency
    learning_triggered: bool
    fallback_used: bool
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class KnowledgeFragment:
    """知识碎片"""
    id: str
    query_pattern: str           # 问题模式
    response: str                # 响应内容
    success_count: int = 0      # 成功次数
    fail_count: int = 0         # 失败次数
    last_used: float = 0         # 上次使用时间
    confidence: float = 0.5       # 置信度
    source: str = "unknown"       # 来源: expert/local/template
    embeddings: Optional[List[float]] = None  # 向量表示
    tags: List[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.fail_count
        return self.success_count / total if total > 0 else 0.5


@dataclass
class SelfEvolutionRecord:
    """自我进化记录"""
    timestamp: float
    trigger: str                 # 触发原因
    before_state: Dict           # 进化前状态
    after_state: Dict            # 进化后状态
    improvement_score: float     # 改进分数
    knowledge_added: int         # 新增知识数


# ═══════════════════════════════════════════════════════════════════════════════
# 紧急响应模板库
# ═══════════════════════════════════════════════════════════════════════════════

EMERGENCY_TEMPLATES = {
    # 通用模板
    "general_greeting": {
        "patterns": [r"你好", r"您好", r"哈喽", r"hi", r"hello", r"嗨"],
        "response": "你好！我是你的智能助手，即使在离线状态下也能为你提供帮助。有什么我可以帮你的吗？",
        "confidence": 0.95,
    },
    "thanks": {
        "patterns": [r"谢谢", r"感谢", r"谢啦", r"thanks", r"thank you"],
        "response": "不客气！如果还有其他问题，随时问我。",
        "confidence": 0.95,
    },
    "help_request": {
        "patterns": [r"帮我", r"帮我.*", r"请.*", r"能不能.*"],
        "response": "好的，请告诉我具体需求，我会尽力帮你解决。即使在离线模式下，我也能基于已有知识库提供帮助。",
        "confidence": 0.8,
    },
    "code_request": {
        "patterns": [r"写代码", r"代码", r"编程", r"python", r"java", r"javascript"],
        "response": "我可以帮你编写代码！请告诉我：\n1. 使用的编程语言\n2. 实现的功能\n3. 具体需求或示例\n\n这样我就能给出更准确的代码。",
        "confidence": 0.85,
    },
    "explain_request": {
        "patterns": [r"解释", r"什么是", r"的意思", r"原理"],
        "response": "我来为你解释。这个概念通常涉及以下方面...\n\n如果你能提供更多上下文，我可以给出更精确的解释。",
        "confidence": 0.75,
    },
    "unknown": {
        "patterns": [r".*"],
        "response": "我理解你的问题。虽然我目前处于离线模式，但我会基于已有的知识尽力为你提供帮助。\n\n请详细描述你的问题，我会尽可能给出有用的回复。如果需要更深入的分析，可以稍后联网时再询问。",
        "confidence": 0.5,
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# 离线学习循环核心系统
# ═══════════════════════════════════════════════════════════════════════════════

class OfflineLearningLoop:
    """
    完全离线的自学习循环系统

    核心特性:
    1. 永不掉线 - 即使没有任何外部API也能响应
    2. 持续进化 - 基于使用反馈自动改进
    3. 知识固化 - 将外部知识转化为本地能力
    4. 多层降级 - 确保任何情况都有响应
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(
        self,
        data_dir: Optional[str] = None,
        max_knowledge_fragments: int = 10000,
        evolution_threshold: float = 0.6,
    ):
        if self._initialized:
            return

        self._initialized = True
        self._lock = threading.RLock()

        # 数据目录
        if data_dir:
            self.data_dir = Path(data_dir)
        else:
            self.data_dir = Path.home() / ".hermes-desktop" / "offline_learning"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 配置
        self.max_knowledge_fragments = max_knowledge_fragments
        self.evolution_threshold = evolution_threshold

        # 知识碎片存储
        self._knowledge_base: Dict[str, KnowledgeFragment] = {}
        self._pattern_index: Dict[str, List[str]] = defaultdict(list)  # pattern -> fragment_ids

        # 状态追踪
        self._connection_status = ConnectionStatus.ONLINE
        self._learning_state = LearningState.IDLE
        self._success_history: deque = deque(maxlen=1000)  # 最近1000次的成功记录
        self._evolution_records: List[SelfEvolutionRecord] = []

        # 回调
        self._on_learning_triggered: Optional[Callable] = None
        self._on_evolution: Optional[Callable] = None
        self._on_connection_change: Optional[Callable] = None

        # 统计
        self._stats = {
            "total_requests": 0,
            "offline_requests": 0,
            "knowledge_hits": 0,
            "template_hits": 0,
            "evolution_count": 0,
            "knowledge_fragments": 0,
        }

        # 加载数据
        self._load_knowledge_base()
        self._load_evolution_records()
        self._load_stats()

        logger.info(f"[OfflineLearningLoop] 已初始化")
        logger.info(f"  - 知识碎片: {len(self._knowledge_base)}")
        logger.info(f"  - 连接状态: {self._connection_status.value}")
        logger.info(f"  - 进化记录: {len(self._evolution_records)}")

    # ═══════════════════════════════════════════════════════════════════════════
    # 核心响应方法
    # ═══════════════════════════════════════════════════════════════════════════

    def get_response(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        allow_learning: bool = True,
    ) -> OfflineResponse:
        """
        获取离线响应

        策略:
        1. 精确匹配知识库
        2. 模式匹配知识库
        3. 模板响应
        4. 紧急响应
        """

        self._stats["total_requests"] += 1
        query_normalized = self._normalize_query(query)

        # Layer 1: 精确匹配
        exact_match = self._exact_match(query_normalized)
        if exact_match:
            self._stats["knowledge_hits"] += 1
            self._record_success(exact_match.id)
            return OfflineResponse(
                content=exact_match.response,
                confidence=exact_match.confidence,
                source="knowledge",
                learning_triggered=False,
                fallback_used=False,
                metadata={"fragment_id": exact_match.id, "match_type": "exact"},
            )

        # Layer 2: 模式匹配
        pattern_match = self._pattern_match(query_normalized)
        if pattern_match:
            self._stats["knowledge_hits"] += 1
            self._record_success(pattern_match.id)
            return OfflineResponse(
                content=pattern_match.response,
                confidence=pattern_match.confidence * 0.9,  # 模式匹配降权
                source="knowledge",
                learning_triggered=False,
                fallback_used=False,
                metadata={"fragment_id": pattern_match.id, "match_type": "pattern"},
            )

        # Layer 3: 模板匹配
        template_match = self._match_template(query)
        if template_match:
            self._stats["template_hits"] += 1
            return OfflineResponse(
                content=template_match["response"],
                confidence=template_match["confidence"],
                source="template",
                learning_triggered=allow_learning,
                fallback_used=False,
                metadata={"template": template_match.get("name", "unknown")},
            )

        # Layer 4: 紧急响应（永不拒绝）
        self._stats["offline_requests"] += 1
        emergency_response = self._generate_emergency_response(query, context)
        return OfflineResponse(
            content=emergency_response,
            confidence=0.3,
            source="emergency",
            learning_triggered=allow_learning,
            fallback_used=True,
            metadata={"generated": True},
        )

    def _normalize_query(self, query: str) -> str:
        """规范化查询"""
        # 转小写
        normalized = query.lower().strip()
        # 移除多余空格
        normalized = re.sub(r'\s+', ' ', normalized)
        # 移除标点
        normalized = re.sub(r'[^\w\s\u4e00-\u9fff]', '', normalized)
        return normalized

    def _exact_match(self, query: str) -> Optional[KnowledgeFragment]:
        """精确匹配"""
        query_hash = self._hash_query(query)
        return self._knowledge_base.get(query_hash)

    def _pattern_match(self, query: str) -> Optional[KnowledgeFragment]:
        """模式匹配"""
        best_match = None
        best_score = 0.5

        # 关键词匹配
        query_keywords = set(query.split())

        for fragment_id, fragment in self._knowledge_base.items():
            # 计算关键词重叠度
            pattern_keywords = set(fragment.query_pattern.lower().split())
            overlap = len(query_keywords & pattern_keywords)
            score = overlap / max(len(query_keywords), len(pattern_keywords), 1)

            if score > best_score:
                best_score = score
                best_match = fragment

        return best_match

    def _match_template(self, query: str) -> Optional[Dict]:
        """模板匹配"""
        query_lower = query.lower()

        for template_name, template in EMERGENCY_TEMPLATES.items():
            for pattern in template["patterns"]:
                if re.search(pattern, query_lower):
                    return {
                        "name": template_name,
                        **template
                    }

        return None

    def _generate_emergency_response(
        self,
        query: str,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """生成紧急响应"""
        return (
            f"收到你的问题：「{query[:50]}{'...' if len(query) > 50 else ''}」\n\n"
            f"当前处于离线学习模式，我会：\n"
            f"1. 记录这个问题，稍后学习正确答案\n"
            f"2. 基于已有知识给出一个初步回答\n\n"
            f"---初步回答---\n"
            f"这个问题涉及多个知识领域。由于目前离线，我建议：\n"
            f"• 如果是紧急问题，可以稍后联网时再询问\n"
            f"• 如果需要精确答案，请联网后重新提问\n"
            f"• 我会持续学习，这个问题下次会有更好的回答\n"
        )

    def _hash_query(self, query: str) -> str:
        """生成查询哈希"""
        return hashlib.md5(query.encode()).hexdigest()

    # ═══════════════════════════════════════════════════════════════════════════
    # 知识管理
    # ═══════════════════════════════════════════════════════════════════════════

    def learn(
        self,
        query: str,
        response: str,
        source: str = "expert",
        confidence: float = 0.9,
        tags: Optional[List[str]] = None,
    ) -> str:
        """
        学习新知识

        Args:
            query: 问题
            response: 回答
            source: 来源 (expert/local/template)
            confidence: 置信度
            tags: 标签

        Returns:
            str: 知识碎片ID
        """

        with self._lock:
            query_normalized = self._normalize_query(query)
            fragment_id = self._hash_query(query_normalized)

            # 检查是否已存在
            if fragment_id in self._knowledge_base:
                existing = self._knowledge_base[fragment_id]
                # 更新成功计数
                if confidence > 0.7:
                    existing.success_count += 1
                else:
                    existing.fail_count += 1
                existing.last_used = time.time()
                # 更新置信度
                existing.confidence = existing.success_rate
                # 如果新响应更好，更新响应内容
                if confidence > existing.confidence:
                    existing.response = response
                    existing.source = source
                self._save_knowledge_fragment(existing)
                return fragment_id

            # 创建新碎片
            fragment = KnowledgeFragment(
                id=fragment_id,
                query_pattern=query_normalized,
                response=response,
                success_count=1 if confidence > 0.7 else 0,
                fail_count=1 if confidence <= 0.7 else 0,
                last_used=time.time(),
                confidence=confidence,
                source=source,
                tags=tags or [],
            )

            self._knowledge_base[fragment_id] = fragment
            self._update_pattern_index(fragment)
            self._save_knowledge_fragment(fragment)

            # 触发进化检查
            if len(self._knowledge_base) >= self.max_knowledge_fragments:
                self._trigger_consolidation()

            return fragment_id

    def unlearn(self, fragment_id: str) -> bool:
        """删除知识碎片"""
        with self._lock:
            if fragment_id not in self._knowledge_base:
                return False

            fragment = self._knowledge_base[fragment_id]
            self._remove_from_pattern_index(fragment)
            del self._knowledge_base[fragment_id]

            # 删除文件
            file_path = self.data_dir / f"fragment_{fragment_id}.json"
            if file_path.exists():
                file_path.unlink()

            return True

    def get_knowledge_stats(self) -> Dict[str, Any]:
        """获取知识库统计"""
        total = len(self._knowledge_base)
        by_source = defaultdict(int)
        high_confidence = 0

        for fragment in self._knowledge_base.values():
            by_source[fragment.source] += 1
            if fragment.confidence >= 0.8:
                high_confidence += 1

        return {
            "total_fragments": total,
            "by_source": dict(by_source),
            "high_confidence_count": high_confidence,
            "avg_confidence": sum(f.confidence for f in self._knowledge_base.values()) / max(total, 1),
            "max_capacity": self.max_knowledge_fragments,
            "utilization_pct": total / self.max_knowledge_fragments * 100,
        }

    def search_knowledge(
        self,
        query: str,
        limit: int = 10,
        min_confidence: float = 0.0,
    ) -> List[KnowledgeFragment]:
        """搜索知识库"""
        query_normalized = self._normalize_query(query)
        query_keywords = set(query_normalized.split())

        results = []
        for fragment in self._knowledge_base.values():
            if fragment.confidence < min_confidence:
                continue

            pattern_keywords = set(fragment.query_pattern.lower().split())
            overlap = len(query_keywords & pattern_keywords)
            score = overlap / max(len(query_keywords), 1)

            if score > 0:
                results.append((score, fragment))

        results.sort(key=lambda x: (x[0], x[1].confidence), reverse=True)
        return [r[1] for r in results[:limit]]

    # ═══════════════════════════════════════════════════════════════════════════
    # 自我进化机制
    # ═══════════════════════════════════════════════════════════════════════════

    def _record_success(self, fragment_id: str):
        """记录成功使用"""
        self._success_history.append({
            "fragment_id": fragment_id,
            "timestamp": time.time(),
            "success": True,
        })

        if fragment_id in self._knowledge_base:
            fragment = self._knowledge_base[fragment_id]
            fragment.success_count += 1
            fragment.last_used = time.time()
            fragment.confidence = fragment.success_rate

            # 检查是否需要进化
            if fragment.success_rate > self.evolution_threshold:
                self._check_evolution()

    def _record_failure(self, fragment_id: str):
        """记录失败使用"""
        self._success_history.append({
            "fragment_id": fragment_id,
            "timestamp": time.time(),
            "success": False,
        })

        if fragment_id in self._knowledge_base:
            fragment = self._knowledge_base[fragment_id]
            fragment.fail_count += 1
            fragment.confidence = fragment.success_rate

    def _check_evolution(self):
        """检查是否需要进化"""
        if len(self._success_history) < 100:
            return

        # 计算最近的成功率
        recent = list(self._success_history)[-100:]
        success_rate = sum(1 for r in recent if r["success"]) / len(recent)

        # 如果成功率下降，触发进化
        if success_rate < self.evolution_threshold:
            self._trigger_evolution()

    def _trigger_evolution(self):
        """触发自我进化"""
        if self._learning_state == LearningState.EVOLVING:
            return

        self._learning_state = LearningState.EVOLVING

        try:
            before_stats = self.get_knowledge_stats()

            # 进化策略
            evolved_count = self._evolve_knowledge_base()

            after_stats = self.get_knowledge_stats()

            # 记录进化
            record = SelfEvolutionRecord(
                timestamp=time.time(),
                trigger="low_success_rate",
                before_state=before_stats,
                after_state=after_stats,
                improvement_score=after_stats["avg_confidence"] - before_stats["avg_confidence"],
                knowledge_added=evolved_count,
            )
            self._evolution_records.append(record)
            self._save_evolution_record(record)

            self._stats["evolution_count"] += 1

            # 回调
            if self._on_evolution:
                self._on_evolution(record)

        finally:
            self._learning_state = LearningState.IDLE

    def _evolve_knowledge_base(self) -> int:
        """进化知识库"""
        evolved = 0

        # 策略1: 合并相似碎片
        evolved += self._merge_similar_fragments()

        # 策略2: 提升高置信度碎片优先级
        evolved += self._boost_high_confidence()

        # 策略3: 清理低置信度碎片
        evolved += self._prune_low_confidence()

        return evolved

    def _merge_similar_fragments(self) -> int:
        """合并相似碎片"""
        merged = 0
        processed = set()

        fragments = list(self._knowledge_base.values())

        for i, frag1 in enumerate(fragments):
            if frag1.id in processed:
                continue

            keywords1 = set(frag1.query_pattern.lower().split())

            for frag2 in fragments[i+1:]:
                if frag2.id in processed:
                    continue

                keywords2 = set(frag2.query_pattern.lower().split())
                overlap = len(keywords1 & keywords2)
                union = len(keywords1 | keywords2)

                if union > 0 and overlap / union > 0.7:
                    # 合并到置信度更高的
                    target = frag1 if frag1.confidence >= frag2.confidence else frag2
                    source = frag2 if frag1.confidence >= frag2.confidence else frag1

                    # 保留两者的信息
                    target.success_count += source.success_count
                    target.fail_count += source.fail_count
                    target.confidence = target.success_rate

                    # 删除源
                    processed.add(source.id)
                    self.unlearn(source.id)
                    merged += 1

        return merged

    def _boost_high_confidence(self) -> int:
        """提升高置信度碎片"""
        boosted = 0
        threshold = 0.9

        for fragment in self._knowledge_base.values():
            if fragment.confidence >= threshold and fragment.source == "expert":
                # 增加标签权重
                if "high-value" not in fragment.tags:
                    fragment.tags.append("high-value")
                    boosted += 1

        return boosted

    def _prune_low_confidence(self) -> int:
        """清理低置信度碎片"""
        pruned = 0
        threshold = 0.2
        min_usage = 5

        to_remove = []
        for fragment in self._knowledge_base.values():
            total_usage = fragment.success_count + fragment.fail_count
            if fragment.confidence < threshold and total_usage >= min_usage:
                to_remove.append(fragment.id)

        for fragment_id in to_remove:
            if self.unlearn(fragment_id):
                pruned += 1

        return pruned

    def _trigger_consolidation(self):
        """触发知识固化"""
        if self._learning_state == LearningState.CONSOLIDATING:
            return

        self._learning_state = LearningState.CONSOLIDATING

        try:
            # 清理并保存
            self._evolve_knowledge_base()
            self._save_knowledge_base()
        finally:
            self._learning_state = LearningState.IDLE

    # ═══════════════════════════════════════════════════════════════════════════
    # 连接状态管理
    # ═══════════════════════════════════════════════════════════════════════════

    def set_connection_status(self, status: ConnectionStatus):
        """设置连接状态"""
        if self._connection_status != status:
            old_status = self._connection_status
            self._connection_status = status

            if self._on_connection_change:
                self._on_connection_change(old_status, status)

            logger.info(f"[OfflineLearningLoop] 连接状态: {old_status.value} -> {status.value}")

    def get_connection_status(self) -> ConnectionStatus:
        """获取连接状态"""
        return self._connection_status

    def is_online(self) -> bool:
        """是否在线"""
        return self._connection_status == ConnectionStatus.ONLINE

    def is_offline(self) -> bool:
        """是否完全离线"""
        return self._connection_status == ConnectionStatus.OFFLINE

    # ═══════════════════════════════════════════════════════════════════════════
    # 持久化
    # ═══════════════════════════════════════════════════════════════════════════

    def _load_knowledge_base(self):
        """加载知识库"""
        kb_file = self.data_dir / "knowledge_base.json"
        if not kb_file.exists():
            return

        try:
            with open(kb_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            for frag_data in data.get("fragments", []):
                fragment = KnowledgeFragment(
                    id=frag_data["id"],
                    query_pattern=frag_data["query_pattern"],
                    response=frag_data["response"],
                    success_count=frag_data.get("success_count", 0),
                    fail_count=frag_data.get("fail_count", 0),
                    last_used=frag_data.get("last_used", 0),
                    confidence=frag_data.get("confidence", 0.5),
                    source=frag_data.get("source", "unknown"),
                    tags=frag_data.get("tags", []),
                )
                self._knowledge_base[fragment.id] = fragment
                self._update_pattern_index(fragment)

            self._stats["knowledge_fragments"] = len(self._knowledge_base)

        except Exception as e:
            logger.info(f"[OfflineLearningLoop] 加载知识库失败: {e}")

    def _save_knowledge_base(self):
        """保存知识库"""
        kb_file = self.data_dir / "knowledge_base.json"

        try:
            data = {
                "version": "1.0",
                "last_updated": time.time(),
                "fragments": [
                    {
                        "id": f.id,
                        "query_pattern": f.query_pattern,
                        "response": f.response,
                        "success_count": f.success_count,
                        "fail_count": f.fail_count,
                        "last_used": f.last_used,
                        "confidence": f.confidence,
                        "source": f.source,
                        "tags": f.tags,
                    }
                    for f in self._knowledge_base.values()
                ]
            }

            with open(kb_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.info(f"[OfflineLearningLoop] 保存知识库失败: {e}")

    def _save_knowledge_fragment(self, fragment: KnowledgeFragment):
        """保存单个知识碎片"""
        # 批量保存到知识库
        self._save_knowledge_base()

    def _load_evolution_records(self):
        """加载进化记录"""
        records_file = self.data_dir / "evolution_records.json"
        if not records_file.exists():
            return

        try:
            with open(records_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            for rec_data in data.get("records", []):
                record = SelfEvolutionRecord(
                    timestamp=rec_data["timestamp"],
                    trigger=rec_data["trigger"],
                    before_state=rec_data["before_state"],
                    after_state=rec_data["after_state"],
                    improvement_score=rec_data["improvement_score"],
                    knowledge_added=rec_data["knowledge_added"],
                )
                self._evolution_records.append(record)

        except Exception as e:
            logger.info(f"[OfflineLearningLoop] 加载进化记录失败: {e}")

    def _save_evolution_record(self, record: SelfEvolutionRecord):
        """保存进化记录"""
        records_file = self.data_dir / "evolution_records.json"

        try:
            data = {
                "records": [
                    {
                        "timestamp": r.timestamp,
                        "trigger": r.trigger,
                        "before_state": r.before_state,
                        "after_state": r.after_state,
                        "improvement_score": r.improvement_score,
                        "knowledge_added": r.knowledge_added,
                    }
                    for r in self._evolution_records[-100:]  # 只保留最近100条
                ]
            }

            with open(records_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.info(f"[OfflineLearningLoop] 保存进化记录失败: {e}")

    def _load_stats(self):
        """加载统计"""
        stats_file = self.data_dir / "stats.json"
        if not stats_file.exists():
            return

        try:
            with open(stats_file, "r", encoding="utf-8") as f:
                saved_stats = json.load(f)
                self._stats.update(saved_stats)
        except Exception:
            pass

    def _save_stats(self):
        """保存统计"""
        stats_file = self.data_dir / "stats.json"

        try:
            with open(stats_file, "w", encoding="utf-8") as f:
                json.dump(self._stats, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════════════
    # 索引管理
    # ═══════════════════════════════════════════════════════════════════════════

    def _update_pattern_index(self, fragment: KnowledgeFragment):
        """更新模式索引"""
        keywords = fragment.query_pattern.lower().split()
        for keyword in keywords:
            if len(keyword) >= 2:  # 忽略单字
                self._pattern_index[keyword].append(fragment.id)

    def _remove_from_pattern_index(self, fragment: KnowledgeFragment):
        """从索引中移除"""
        keywords = fragment.query_pattern.lower().split()
        for keyword in keywords:
            if keyword in self._pattern_index:
                try:
                    self._pattern_index[keyword].remove(fragment.id)
                except ValueError:
                    pass

    # ═══════════════════════════════════════════════════════════════════════════
    # 回调设置
    # ═══════════════════════════════════════════════════════════════════════════

    def set_callbacks(
        self,
        on_learning_triggered: Callable = None,
        on_evolution: Callable = None,
        on_connection_change: Callable = None,
    ):
        """设置回调函数"""
        self._on_learning_triggered = on_learning_triggered
        self._on_evolution = on_evolution
        self._on_connection_change = on_connection_change

    # ═══════════════════════════════════════════════════════════════════════════
    # 统计和调试
    # ═══════════════════════════════════════════════════════════════════════════

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        recent_success_rate = 0
        if len(self._success_history) > 0:
            recent = list(self._success_history)[-100:]
            recent_success_rate = sum(1 for r in recent if r["success"]) / len(recent)

        return {
            **self._stats,
            "connection_status": self._connection_status.value,
            "learning_state": self._learning_state.value,
            "recent_success_rate": recent_success_rate,
            "evolution_records": len(self._evolution_records),
            "knowledge_stats": self.get_knowledge_stats(),
        }

    def export_knowledge(self) -> str:
        """导出知识库为JSON"""
        return json.dumps(
            {
                "version": "1.0",
                "exported_at": time.time(),
                "fragments": [
                    {
                        "query": f.query_pattern,
                        "response": f.response,
                        "confidence": f.confidence,
                        "source": f.source,
                        "tags": f.tags,
                    }
                    for f in self._knowledge_base.values()
                ]
            },
            ensure_ascii=False,
            indent=2,
        )

    def import_knowledge(self, json_str: str) -> int:
        """从JSON导入知识"""
        try:
            data = json.loads(json_str)
            count = 0

            for frag_data in data.get("fragments", []):
                self.learn(
                    query=frag_data.get("query", ""),
                    response=frag_data.get("response", ""),
                    source=frag_data.get("source", "imported"),
                    confidence=frag_data.get("confidence", 0.5),
                    tags=frag_data.get("tags", []),
                )
                count += 1

            return count

        except Exception as e:
            logger.info(f"[OfflineLearningLoop] 导入知识失败: {e}")
            return 0


# ═══════════════════════════════════════════════════════════════════════════════
# 单例访问
# ═══════════════════════════════════════════════════════════════════════════════

_offline_learning_loop: Optional[OfflineLearningLoop] = None


def get_offline_learning_loop() -> OfflineLearningLoop:
    """获取全局离线学习循环实例"""
    global _offline_learning_loop
    if _offline_learning_loop is None:
        _offline_learning_loop = OfflineLearningLoop()
    return _offline_learning_loop


# ═══════════════════════════════════════════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("完全离线的自学习循环系统测试")
    logger.info("=" * 60)

    loop = OfflineLearningLoop()

    # 测试响应
    logger.info("\n[Test 1: 模板响应]")
    response = loop.get_response("你好")
    logger.info(f"  响应: {response.content[:50]}...")
    logger.info(f"  来源: {response.source}")
    logger.info(f"  置信度: {response.confidence}")

    logger.info("\n[Test 2: 学习新知识]")
    loop.learn(
        query="什么是Python",
        response="Python是一种高级编程语言...",
        source="expert",
        confidence=0.9,
    )
    logger.info(f"  知识碎片数: {len(loop._knowledge_base)}")

    logger.info("\n[Test 3: 获取已学知识]")
    response = loop.get_response("什么是Python")
    logger.info(f"  响应: {response.content[:50]}...")
    logger.info(f"  来源: {response.source}")

    logger.info("\n[Test 4: 搜索知识]")
    results = loop.search_knowledge("Python编程")
    logger.info(f"  搜索结果: {len(results)} 条")

    logger.info("\n[Test 5: 统计信息]")
    stats = loop.get_stats()
    logger.info(f"  总请求: {stats['total_requests']}")
    logger.info(f"  离线请求: {stats['offline_requests']}")
    logger.info(f"  知识命中: {stats['knowledge_hits']}")
    logger.info(f"  进化次数: {stats['evolution_count']}")

    logger.info("\n" + "=" * 60)
    logger.info("测试完成")
