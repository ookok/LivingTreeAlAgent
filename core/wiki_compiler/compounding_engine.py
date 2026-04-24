"""
复利效应引擎 - Compounding Engine

核心理念：摄入的内容越多，新材料被解读时所处的上下文就越丰富。

与传统笔记的区别：
- 传统笔记：第100条笔记不会让第50条笔记变聪明
- LLM Wiki：第100个来源的处理建立在一个已经蒸馏了前99个来源知识的wiki之上

复利效应的实现：
1. Cross-Context Enrichment - 跨上下文丰富
2. Knowledge Compilation - 知识编译
3. Compounding Queries - 复利查询
4. Dream Cycle - 夜间循环
"""

import os
import json
import time
import hashlib
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class CompoundingContext:
    """复利上下文"""
    topic: str                         # 主题
    accumulated_summary: str = ""      # 累积摘要
    key_insights: List[str] = field(default_factory=list)  # 关键洞察
    source_count: int = 0             # 来源数量
    confidence: float = 0.5           # 置信度
    related_topics: List[str] = field(default_factory=list)  # 相关主题
    last_enriched: float = field(default_factory=time.time)

    def enrich(self, new_content: str, new_insights: List[str]):
        """丰富上下文"""
        self.source_count += 1
        self.key_insights.extend(new_insights)
        self.key_insights = list(set(self.key_insights))  # 去重

        # 更新累积摘要
        if not self.accumulated_summary:
            self.accumulated_summary = new_content[:200]
        else:
            # 简化的摘要更新
            self.accumulated_summary = f"{self.accumulated_summary[:100]}... + {new_content[:100]}..."

        # 置信度随来源增加而提升（有上限）
        self.confidence = min(0.95, self.confidence + 0.01)
        self.last_enriched = time.time()


@dataclass
class CompoundingRecord:
    """复利记录"""
    timestamp: float
    query: str
    context_before: str  # 复利前的上下文
    context_after: str   # 复利后的上下文
    new_insights: List[str]
    confidence_delta: float


class CompoundingEngine:
    """
    复利效应引擎

    主要功能：
    1. 维护跨会话的知识累积上下文
    2. 实现"第N个查询比第N-1个更聪明"
    3. 夜间循环：自动整理和强化知识
    4. 知识链条：追踪知识的演进过程
    """

    def __init__(
        self,
        persist_path: str = "~/.hermes-desktop/wiki_compounder",
        max_contexts: int = 100
    ):
        self.persist_path = Path(os.path.expanduser(persist_path))
        self.max_contexts = max_contexts
        self._lock = threading.RLock()

        # 复利上下文存储
        self._contexts: Dict[str, CompoundingContext] = {}

        # 复利历史记录
        self._records: List[CompoundingRecord] = []

        # 全局知识累积
        self._global_summary: str = ""
        self._global_insights: List[str] = []
        self._source_count: int = 0

        # 统计
        self._stats = {
            "total_queries": 0,
            "total_enrichments": 0,
            "avg_confidence_boost": 0.0,
            "context_hits": 0
        }

        # 初始化
        self.persist_path.mkdir(parents=True, exist_ok=True)
        self._load_state()

    def _load_state(self):
        """加载状态"""
        contexts_path = self.persist_path / "contexts.json"
        if contexts_path.exists():
            try:
                with open(contexts_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for topic, ctx_data in data.get("contexts", {}).items():
                        self._contexts[topic] = CompoundingContext(
                            topic=topic,
                            accumulated_summary=ctx_data.get("accumulated_summary", ""),
                            key_insights=ctx_data.get("key_insights", []),
                            source_count=ctx_data.get("source_count", 0),
                            confidence=ctx_data.get("confidence", 0.5),
                            related_topics=ctx_data.get("related_topics", []),
                            last_enriched=ctx_data.get("last_enriched", time.time())
                        )
                    self._global_summary = data.get("global_summary", "")
                    self._global_insights = data.get("global_insights", [])
                    self._source_count = data.get("source_count", 0)
                    self._records = [
                        CompoundingRecord(**r) for r in data.get("records", [])
                    ]
            except Exception as e:
                logger.info(f"[CompoundingEngine] 加载状态失败: {e}")

        stats_path = self.persist_path / "stats.json"
        if stats_path.exists():
            try:
                with open(stats_path, 'r', encoding='utf-8') as f:
                    self._stats = json.load(f)
            except:
                pass

    def _save_state(self):
        """保存状态"""
        try:
            contexts_data = {
                "contexts": {
                    topic: {
                        "accumulated_summary": ctx.accumulated_summary,
                        "key_insights": ctx.key_insights,
                        "source_count": ctx.source_count,
                        "confidence": ctx.confidence,
                        "related_topics": ctx.related_topics,
                        "last_enriched": ctx.last_enriched
                    }
                    for topic, ctx in self._contexts.items()
                },
                "global_summary": self._global_summary,
                "global_insights": self._global_insights,
                "source_count": self._source_count,
                "records": [
                    {
                        "timestamp": r.timestamp,
                        "query": r.query,
                        "context_before": r.context_before,
                        "context_after": r.context_after,
                        "new_insights": r.new_insights,
                        "confidence_delta": r.confidence_delta
                    }
                    for r in self._records[-100:]  # 只保存最近100条
                ]
            }
            with open(self.persist_path / "contexts.json", 'w', encoding='utf-8') as f:
                json.dump(contexts_data, f, ensure_ascii=False, indent=2)

            with open(self.persist_path / "stats.json", 'w', encoding='utf-8') as f:
                json.dump(self._stats, f, ensure_ascii=False)
        except Exception as e:
            logger.info(f"[CompoundingEngine] 保存状态失败: {e}")

    def get_context_for_query(self, query: str) -> Tuple[str, float]:
        """
        获取查询的复利上下文

        Returns:
            (enriched_context, confidence_boost)
        """
        with self._lock:
            self._stats["total_queries"] += 1

            # 提取查询关键词
            keywords = self._extract_keywords(query)

            # 查找相关上下文
            best_context = None
            best_relevance = 0.0

            for topic, ctx in self._contexts.items():
                relevance = self._compute_relevance(query, topic, ctx)
                if relevance > best_relevance and relevance > 0.3:
                    best_relevance = relevance
                    best_context = ctx

            if best_context:
                self._stats["context_hits"] += 1
                confidence_boost = best_context.confidence * best_relevance
                enriched = self._enrich_query_with_context(query, best_context)
                return enriched, confidence_boost

            # 使用全局上下文
            if self._global_insights:
                self._stats["context_hits"] += 1
                global_context = CompoundingContext(
                    topic="global",
                    accumulated_summary=self._global_summary,
                    key_insights=self._global_insights,
                    confidence=min(0.8, self._source_count * 0.01)
                )
                confidence_boost = global_context.confidence * 0.5
                return self._enrich_query_with_context(query, global_context), confidence_boost

            return query, 0.0

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        import re
from core.logger import get_logger
logger = get_logger('wiki_compiler.compounding_engine')

        # 简单分词
        words = re.findall(r'[\w]+', text.lower())
        # 过滤停用词
        stopwords = {'的', '是', '在', '了', '和', '与', '或', '一个', '什么', '怎么', '如何', '为什么'}
        return [w for w in words if w not in stopwords and len(w) > 1]

    def _compute_relevance(
        self,
        query: str,
        topic: str,
        ctx: CompoundingContext
    ) -> float:
        """计算查询与上下文的关联度"""
        query_keywords = set(self._extract_keywords(query))
        topic_keywords = set(self._extract_keywords(topic))
        insight_keywords = set()
        for insight in ctx.key_insights:
            insight_keywords.update(self._extract_keywords(insight))

        # Jaccard 相似度
        if not query_keywords:
            return 0.0

        intersection = len(query_keywords & topic_keywords | insight_keywords)
        union = len(query_keywords | topic_keywords | insight_keywords)

        return intersection / union if union > 0 else 0.0

    def _enrich_query_with_context(
        self,
        query: str,
        ctx: CompoundingContext
    ) -> str:
        """用上下文丰富查询"""
        if not ctx.key_insights:
            return query

        # 将关键洞察作为上下文追加
        enriched = query
        if ctx.accumulated_summary:
            enriched = f"{query}\n\n[相关背景: {ctx.accumulated_summary[:200]}...]"
        if ctx.key_insights:
            insights_str = "; ".join(ctx.key_insights[:3])
            enriched += f"\n\n[已知洞察: {insights_str}]"

        return enriched

    def enrich_with_new_knowledge(
        self,
        content: str,
        topic: str,
        insights: List[str] = None,
        source_id: str = None
    ):
        """
        用新知识丰富上下文

        这是复利效应的核心：新知识被整合到现有上下文中，
        使得未来的查询能够建立在这个累积知识之上
        """
        with self._lock:
            self._source_count += 1
            self._stats["total_enrichments"] += 1

            # 获取或创建上下文
            if topic not in self._contexts:
                self._contexts[topic] = CompoundingContext(topic=topic)

            ctx = self._contexts[topic]

            # 记录复利前的状态
            context_before = ctx.accumulated_summary[:100]
            confidence_before = ctx.confidence

            # 丰富上下文
            ctx.enrich(content, insights or [])

            # 发现相关主题
            related = self._discover_related_topics(topic, content)
            ctx.related_topics.extend(related)
            ctx.related_topics = list(set(ctx.related_topics))[:10]

            # 更新全局累积
            self._global_insights.extend(insights or [])
            self._global_insights = list(set(self._global_insights))[-100:]  # 保留最近100条

            if not self._global_summary:
                self._global_summary = content[:500]
            else:
                # 简化的全局摘要更新
                self._global_summary = f"{self._global_summary[:200]}... + {content[:200]}..."

            # 记录复利
            record = CompoundingRecord(
                timestamp=time.time(),
                query=f"enrich:{topic}",
                context_before=context_before,
                context_after=ctx.accumulated_summary[:100],
                new_insights=insights or [],
                confidence_delta=ctx.confidence - confidence_before
            )
            self._records.append(record)

            # LRU 淘汰不常用的上下文
            if len(self._contexts) > self.max_contexts:
                self._evict_least_valuable_context()

            self._save_state()

    def _discover_related_topics(self, topic: str, content: str) -> List[str]:
        """发现相关主题"""
        related = []
        content_lower = content.lower()

        # 简单的共现分析
        for other_topic, ctx in self._contexts.items():
            if other_topic == topic:
                continue
            if any(keyword in content_lower for keyword in self._extract_keywords(ctx.topic)):
                related.append(other_topic)

        return related[:5]

    def _evict_least_valuable_context(self):
        """淘汰价值最低的上下文"""
        if not self._contexts:
            return

        # 计算每个上下文的价值分数
        value_scores = {}
        for topic, ctx in self._contexts.items():
            # 价值 = 来源数 * 置信度 * (1 / (1 + 距今时间))
            age = (time.time() - ctx.last_enriched) / 86400  # 天
            value = ctx.source_count * ctx.confidence / (1 + age * 0.1)
            value_scores[topic] = value

        # 淘汰价值最低的
        min_topic = min(value_scores, key=value_scores.get)
        del self._contexts[min_topic]

    def run_dream_cycle(self, wiki_pages: List[Any] = None) -> Dict[str, Any]:
        """
        运行夜间循环（Dream Cycle）

        在用户睡眠时自动：
        1. 整理和强化已有知识
        2. 发现潜在矛盾
        3. 生成新的洞察
        4. 更新置信度
        """
        with self._lock:
            dream_results = {
                "insights_generated": 0,
                "contradictions_found": 0,
                "pages_updated": 0,
                "new_relationships": []
            }

            # 1. 强化高价值上下文
            high_value_contexts = [
                ctx for ctx in self._contexts.values()
                if ctx.confidence > 0.7 and ctx.source_count > 3
            ]

            for ctx in high_value_contexts:
                # 简化的强化逻辑：确认现有洞察
                confirmed_insights = []
                for insight in ctx.key_insights[:5]:
                    # 模拟 LLM 确认洞察
                    confirmed_insights.append(insight)
                ctx.key_insights = confirmed_insights + ctx.key_insights[:3]
                ctx.confidence = min(0.95, ctx.confidence + 0.05)
                dream_results["insights_generated"] += 1

            # 2. 更新统计
            total_boost = sum(r.confidence_delta for r in self._records[-10:])
            self._stats["avg_confidence_boost"] = total_boost / max(len(self._records[-10:]), 1)

            self._save_state()

            return dream_results

    def get_compounding_insights(self) -> Dict[str, Any]:
        """获取复利洞察"""
        return {
            "source_count": self._source_count,
            "active_contexts": len(self._contexts),
            "total_records": len(self._records),
            "context_hits": self._stats["context_hits"],
            "hit_rate": self._stats["context_hits"] / max(self._stats["total_queries"], 1),
            "avg_confidence_boost": self._stats["avg_confidence_boost"],
            "total_enrichments": self._stats["total_enrichments"],
            "top_contexts": [
                {
                    "topic": ctx.topic,
                    "source_count": ctx.source_count,
                    "confidence": ctx.confidence,
                    "key_insights": ctx.key_insights[:3]
                }
                for ctx in sorted(
                    self._contexts.values(),
                    key=lambda c: c.source_count * c.confidence,
                    reverse=True
                )[:5]
            ],
            "global_insights": self._global_insights[-10:]
        }

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self._stats,
            "source_count": self._source_count,
            "active_contexts": len(self._contexts),
            "total_records": len(self._records)
        }