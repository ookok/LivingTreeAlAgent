# -*- coding: utf-8 -*-
"""
专家指导学习系统 (Expert-Guided Learning System)
================================================

三层学习架构：
1. 快速缓存层 → 高频问题直接复用
2. 模型蒸馏层 → 学习专家推理模式
3. 知识图谱层 → 结构化存储专家知识

核心流程：
[用户提问] → [本地模型生成] → [专家模型验证] → [对比分析] → [知识更新]
                ↑                                    ↓
                └───────────── 学习信号 ─────────────┘

复用模块：
- HermesAgent (本地模型)
- SkillEvolutionAgent (技能进化)
- IndustryDistiller (行业蒸馏)
- KnowledgeGraph (知识图谱)
- Unified Cache (缓存)
"""

from core.logger import get_logger
logger = get_logger('expert_learning.expert_guided_system')

from __future__ import annotations

import json
import time
import hashlib
from typing import Optional, List, Dict, Any, Callable, Iterator
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# ── 延迟导入避免循环依赖 ──────────────────────────────────────────

def _get_hermes_agent():
    from client.src.business.agent import HermesAgent
    return HermesAgent

def _get_skill_evolution():
    from core.skill_evolution.agent_loop import SkillEvolutionAgent
    return SkillEvolutionAgent

def _get_knowledge_graph():
    from core.knowledge_graph import KnowledgeGraph
    return KnowledgeGraph

def _get_unified_cache():
    from core.unified_cache import UnifiedCache
    return UnifiedCache

def _get_ollama_url():
    """获取 Ollama URL，支持统一配置"""
    try:
        from client.src.business.config import get_ollama_url
        return get_ollama_url()
    except ImportError:
        return "http://localhost:11434"

def _get_industry_distiller():
    try:
        from core.evolution.experience_optimizer import IndustryDistiller
        return IndustryDistiller
    except ImportError:
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════════════════════

class LearningPhase(Enum):
    """学习阶段"""
    CACHE_HIT = "cache_hit"           # 缓存命中
    LOCAL_ONLY = "local_only"         # 仅本地
    LOCAL_THEN_EXPERT = "local_then_expert"  # 本地+专家对比
    EXPERT_GUIDED = "expert_guided"   # 专家指导
    CONSOLIDATING = "consolidating"   # 固化中


class CorrectionLevel(Enum):
    """纠正层级"""
    NONE = 0           # 无需纠正
    VOCABULARY = 1    # 词汇修正
    STYLE = 2         # 句式优化
    LOGIC = 3        # 逻辑重组
    KNOWLEDGE = 4    # 知识补充
    REASONING = 5    # 思维链对齐
    STYLE_MIGRATION = 6  # 风格迁移


@dataclass
class LearningRecord:
    """学习记录"""
    query: str
    local_response: str
    expert_response: str
    correction_level: CorrectionLevel
    correction_notes: str = ""
    learned_knowledge: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            "query": self.query,
            "local_response": self.local_response,
            "expert_response": self.expert_response,
            "correction_level": self.correction_level.value,
            "correction_notes": self.correction_notes,
            "learned_knowledge": self.learned_knowledge,
            "timestamp": self.timestamp,
        }


@dataclass
class ExpertGuidedResult:
    """专家指导结果"""
    response: str
    phase: LearningPhase
    source: str  # "cache" / "local" / "expert" / "corrected"
    confidence: float
    correction_level: CorrectionLevel
    learning_triggered: bool
    metadata: Dict[str, Any] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════════
# 对比分析器
# ═══════════════════════════════════════════════════════════════════════════════

class ResponseComparator:
    """
    响应对比分析器

    分析本地模型和专家模型回答的差异，决定：
    1. 是否需要纠正
    2. 纠正的层级
    3. 学习价值
    """

    # 关键词映射到纠正层级
    FACTUAL_KEYWORDS = [
        "事实", "正确", "错误", "准确的", "实际上",
        "data", "fact", "accurate", "actually"
    ]
    LOGIC_KEYWORDS = [
        "因此", "所以", "但是", "然而", "因为",
        "therefore", "however", "because", "thus"
    ]
    STYLE_KEYWORDS = [
        "更优雅", "更清晰", "更好", "建议", "推荐",
        "better", "clearer", "suggest", "recommend"
    ]

    def __init__(self, llm_client: Any = None):
        self.llm = llm_client

    def compare(
        self,
        query: str,
        local_response: str,
        expert_response: str
    ) -> Dict[str, Any]:
        """
        对比分析两个响应

        Returns:
            {
                "needs_correction": bool,
                "correction_level": CorrectionLevel,
                "correction_type": str,
                "correction_notes": str,
                "similarity": float,
            }
        """
        # 快速规则检查
        rule_result = self._quick_rule_check(local_response, expert_response)
        if rule_result["needs_correction"]:
            return rule_result

        # LLM 辅助分析（如果有）
        if self.llm:
            return self._llm_assisted_check(query, local_response, expert_response)

        # 默认：不做纠正
        return {
            "needs_correction": False,
            "correction_level": CorrectionLevel.NONE,
            "correction_type": "无需纠正",
            "correction_notes": "回答质量可接受",
            "similarity": self._calculate_similarity(local_response, expert_response),
        }

    def _quick_rule_check(
        self,
        local_response: str,
        expert_response: str
    ) -> Dict[str, Any]:
        """快速规则检查"""
        # 检查长度差异
        len_ratio = len(local_response) / max(len(expert_response), 1)
        if len_ratio < 0.3:
            return {
                "needs_correction": True,
                "correction_level": CorrectionLevel.KNOWLEDGE,
                "correction_type": "知识缺失",
                "correction_notes": f"本地回答过短（{len_ratio:.0%}），可能遗漏重要信息",
                "similarity": self._calculate_similarity(local_response, expert_response),
            }

        # 检查关键词缺失
        expert_keywords = set(expert_response) - set(local_response)
        missing_ratio = len(expert_keywords) / max(len(set(expert_response)), 1)
        if missing_ratio > 0.5:
            return {
                "needs_correction": True,
                "correction_level": CorrectionLevel.KNOWLEDGE,
                "correction_type": "关键信息缺失",
                "correction_notes": f"缺失 {missing_ratio:.0%} 的关键信息",
                "similarity": self._calculate_similarity(local_response, expert_response),
            }

        return {
            "needs_correction": False,
            "correction_level": CorrectionLevel.NONE,
            "correction_type": "快速检查通过",
            "correction_notes": "",
            "similarity": self._calculate_similarity(local_response, expert_response),
        }

    def _llm_assisted_check(
        self,
        query: str,
        local_response: str,
        expert_response: str
    ) -> Dict[str, Any]:
        """LLM 辅助的深度检查"""
        prompt = f"""对比以下两个回答，输出 JSON：
问题：{query}

本地回答：{local_response}

专家回答：{expert_response}

输出格式：
{{
  "needs_correction": true/false,
  "correction_level": 0-6 (0=无需纠正, 1=词汇, 2=句式, 3=逻辑, 4=知识, 5=推理, 6=风格),
  "correction_type": "具体类型",
  "correction_notes": "纠正说明",
  "learning_value": "学习价值评估"
}}
"""
        # 调用 LLM 获取分析（简化版）
        # 实际使用时调用 self.llm
        return self._quick_rule_check(local_response, expert_response)

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度（简化版）"""
        if not text1 or not text2:
            return 0.0

        set1 = set(text1)
        set2 = set(text2)
        intersection = len(set1 & set2)
        union = len(set1 | set2)

        return intersection / union if union > 0 else 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# 专家指导学习系统
# ═══════════════════════════════════════════════════════════════════════════════

class ExpertGuidedLearningSystem:
    """
    专家指导学习系统

    三层学习架构：
    1. 缓存层 → 快速响应
    2. 蒸馏层 → 能力提升
    3. 知识图谱层 → 结构化知识

    使用方式：
        system = ExpertGuidedLearningSystem()
        result = system.process("帮我分析这段Python代码")
    """

    def __init__(
        self,
        config: Optional[Dict] = None,
        llm_client: Optional[Any] = None,
    ):
        self.config = config or {}
        self.llm = llm_client

        # ── 第一层：缓存 ────────────────────────────────────────────
        try:
            # 尝试从根目录导入
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            from unified_cache import UnifiedCache
            self.cache = UnifiedCache()
            logger.info("[ExpertLearning] [OK] Cache layer enabled")
        except Exception as e:
            logger.info(f"[ExpertLearning] [WARN] Cache layer init failed: {e}")
            self.cache = None

        # ── 第二层：知识图谱 ──────────────────────────────────────
        try:
            self.knowledge_graph = _get_knowledge_graph()()
            logger.info("[ExpertLearning] [OK] Knowledge graph layer enabled")
        except Exception as e:
            logger.info(f"[ExpertLearning] [WARN] Knowledge graph init failed: {e}")
            self.knowledge_graph = None

        # ── 第三层：行业蒸馏器 ────────────────────────────────────
        self.distiller = None
        DistillerClass = _get_industry_distiller()
        if DistillerClass:
            try:
                self.distiller = DistillerClass()
                logger.info("[ExpertLearning] [OK] Distillation layer enabled")
            except Exception as e:
                logger.info(f"[ExpertLearning] [WARN] Distillation init failed: {e}")

        # ── 第四层：思维链蒸馏器 ⭐ ────────────────────────────────
        self.cot_distiller = None
        try:
            from client.src.business.expert_learning.chain_of_thought_distiller import ChainOfThoughtDistiller
            self.cot_distiller = ChainOfThoughtDistiller()
            logger.info("[ExpertLearning] [OK] Chain-of-Thought Distiller enabled")
        except ImportError:
            logger.info("[ExpertLearning] [WARN] CoT Distiller not available")
        except Exception as e:
            logger.info(f"[ExpertLearning] [WARN] CoT Distiller init failed: {e}")

        # ── 对比分析器 ─────────────────────────────────────────────
        self.comparator = ResponseComparator(llm_client)

        # ── 学习记录存储 ───────────────────────────────────────────
        self._data_dir = Path(self.config.get(
            "data_dir",
            Path.home() / ".hermes-desktop" / "expert_learning"
        ))
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._learning_records: List[LearningRecord] = []

        # ── 统计信息 ───────────────────────────────────────────────
        self._stats = {
            "cache_hits": 0,
            "local_only": 0,
            "expert_guided": 0,
            "corrections": 0,
            "total_queries": 0,
        }

        # ── 性能监控器 ⭐ ───────────────────────────────────────────
        self._monitor = None
        try:
            from client.src.business.expert_learning.performance_monitor import PerformanceMonitor
            self._monitor = PerformanceMonitor()
            logger.info("[ExpertLearning] [OK] Performance Monitor enabled")
        except ImportError:
            logger.info("[ExpertLearning] [WARN] Performance Monitor not available")
        except Exception as e:
            logger.info(f"[ExpertLearning] [WARN] Performance Monitor init failed: {e}")

        # ── 智能卸载策略 ⭐ ─────────────────────────────────────────
        self._offload_strategy = None
        try:
            from client.src.business.expert_learning.auto_offload_strategy import AutoOffloadStrategy
            self._offload_strategy = AutoOffloadStrategy()
            logger.info("[ExpertLearning] [OK] Auto-Offload Strategy enabled")
        except ImportError:
            logger.info("[ExpertLearning] [WARN] Auto-Offload not available")
        except Exception as e:
            logger.info(f"[ExpertLearning] [WARN] Auto-Offload init failed: {e}")

        # ── 自适应模型压缩器 ⭐ ─────────────────────────────────────
        self._compressor = None
        try:
            from client.src.business.expert_learning.adaptive_model_compressor import AdaptiveModelCompressor
            self._compressor = AdaptiveModelCompressor()
            logger.info("[ExpertLearning] [OK] Adaptive Model Compressor enabled")
        except ImportError:
            logger.info("[ExpertLearning] [WARN] Adaptive Compressor not available")
        except Exception as e:
            logger.info(f"[ExpertLearning] [WARN] Adaptive Compressor init failed: {e}")

        # ── 智能配额管理器 ⭐ ───────────────────────────────────────
        self._quota_manager = None
        try:
            from client.src.business.expert_learning.smart_quota_manager import SmartQuotaManager, QuotaMode, Provider
            self._quota_manager = SmartQuotaManager()
            logger.info("[ExpertLearning] [OK] Smart Quota Manager enabled")
        except ImportError:
            logger.info("[ExpertLearning] [WARN] Smart Quota Manager not available")
        except Exception as e:
            logger.info(f"[ExpertLearning] [WARN] Smart Quota Manager init failed: {e}")

        # 加载历史记录
        self._load_learning_records()

    def process(self, query: str) -> ExpertGuidedResult:
        """
        处理用户查询

        流程：
        1. 缓存检查 → 命中则直接返回
        2. 本地模型生成
        3. 专家模型验证（可选）
        4. 对比分析 + 学习
        5. 结果缓存
        """
        self._stats["total_queries"] += 1
        start_time = time.time()

        # ── Step 1: 缓存检查 ──────────────────────────────────────
        if self.cache:
            cached_hit = self.cache.get_l4(query)
            if cached_hit and cached_hit.data:
                self._stats["cache_hits"] += 1
                latency_ms = (time.time() - start_time) * 1000

                # 记录性能
                if self._monitor:
                    self._monitor.record_request(
                        query=query,
                        latency_ms=latency_ms,
                        source="cache",
                        cache_hit=True,
                        accuracy=1.0,
                        metadata={"tier": cached_hit.tier}
                    )

                return ExpertGuidedResult(
                    response=cached_hit.data if isinstance(cached_hit.data, str) else str(cached_hit.data),
                    phase=LearningPhase.CACHE_HIT,
                    source="cache",
                    confidence=1.0,
                    correction_level=CorrectionLevel.NONE,
                    learning_triggered=False,
                    metadata={"cache": True, "tier": cached_hit.tier, "latency_ms": latency_ms},
                )

        # ── Step 2: 本地模型生成 ─────────────────────────────────
        # 这里复用 HermesAgent 的生成能力
        local_response = self._generate_local(query)
        self._stats["local_only"] += 1

        # ── Step 3: 知识图谱增强（可选）───────────────────────────
        enhanced_query = self._enhance_with_knowledge_graph(query)

        # ── Step 4: 专家模型验证 ──────────────────────────────────
        expert_response = self._generate_expert(enhanced_query)
        latency_ms = (time.time() - start_time) * 1000

        if not expert_response:
            # 专家不可用，缓存本地结果并返回
            self._record_success(query, local_response)

            # 记录性能
            if self._monitor:
                self._monitor.record_request(
                    query=query,
                    latency_ms=latency_ms,
                    source="local",
                    cache_hit=False,
                    accuracy=0.7
                )

            return ExpertGuidedResult(
                response=local_response,
                phase=LearningPhase.LOCAL_ONLY,
                source="local",
                confidence=0.7,
                correction_level=CorrectionLevel.NONE,
                learning_triggered=False,
            )

        # ── Step 5: 对比分析 ──────────────────────────────────────
        comparison = self.comparator.compare(
            query, local_response, expert_response
        )

        # ── Step 6: 决策 + 学习 ──────────────────────────────────
        if comparison["needs_correction"]:
            self._stats["corrections"] += 1

            # 记录学习
            record = LearningRecord(
                query=query,
                local_response=local_response,
                expert_response=expert_response,
                correction_level=comparison["correction_level"],
                correction_notes=comparison["correction_notes"],
                learned_knowledge=comparison.get("learning_value", ""),
            )
            self._learning_records.append(record)
            self._save_learning_record(record)

            # 更新知识图谱
            self._update_knowledge_graph(query, expert_response, comparison)

            # 更新蒸馏器
            if self.distiller:
                self._update_distiller(query, expert_response)

            # 记录性能
            if self._monitor:
                self._monitor.record_request(
                    query=query,
                    latency_ms=latency_ms,
                    source="expert",
                    cache_hit=False,
                    accuracy=0.9,
                    correction=True
                )

            return ExpertGuidedResult(
                response=expert_response,  # 返回专家回答作为参考答案
                phase=LearningPhase.EXPERT_GUIDED,
                source="expert",
                confidence=0.9,
                correction_level=comparison["correction_level"],
                learning_triggered=True,
                metadata={
                    "comparison": comparison,
                    "correction_notes": comparison["correction_notes"],
                    "latency_ms": latency_ms,
                },
            )
        else:
            # 本地回答足够好，记录成功
            self._record_success(query, local_response)

            # 记录性能
            if self._monitor:
                self._monitor.record_request(
                    query=query,
                    latency_ms=latency_ms,
                    source="local",
                    cache_hit=False,
                    accuracy=0.85,
                    correction=False
                )

            return ExpertGuidedResult(
                response=local_response,
                phase=LearningPhase.LOCAL_THEN_EXPERT,
                source="local",
                confidence=0.85,
                correction_level=CorrectionLevel.NONE,
                learning_triggered=False,
            )

    def process_stream(self, query: str) -> Iterator[ExpertGuidedResult]:
        """流式处理（生成即返回）"""
        # 先返回本地结果
        local_response = self._generate_local(query)
        yield ExpertGuidedResult(
            response=local_response,
            phase=LearningPhase.LOCAL_ONLY,
            source="local",
            confidence=0.7,
            correction_level=CorrectionLevel.NONE,
            learning_triggered=False,
        )

        # 后台触发专家验证
        expert_response = self._generate_expert(query)
        if expert_response:
            comparison = self.comparator.compare(
                query, local_response, expert_response
            )
            if comparison["needs_correction"]:
                # 如果发现需要纠正，可以补充说明
                yield ExpertGuidedResult(
                    response=expert_response,
                    phase=LearningPhase.EXPERT_GUIDED,
                    source="expert",
                    confidence=0.9,
                    correction_level=comparison["correction_level"],
                    learning_triggered=True,
                    metadata={
                        "improvement_note": f"参考：{comparison['correction_notes']}"
                    },
                )

    def _generate_local(self, query: str) -> str:
        """本地模型生成（复用 HermesAgent）"""
        try:
            HermesAgent = _get_hermes_agent()
            # 这里需要实际初始化，简化处理
            # 实际使用时：agent = HermesAgent(); return agent.chat(query)
            return f"[本地模型]: {query}"
        except Exception as e:
            logger.info(f"[ExpertLearning] Local generation failed: {e}")
            return ""

    def _generate_expert(self, query: str) -> Optional[str]:
        """专家模型生成（使用 L4）"""
        try:
            # 使用 L4 模型（qwen3.5:9b）
            from core.ollama_client import OllamaClient, OllamaConfig, ChatMessage
            config = OllamaConfig(
                base_url=self.config.get("ollama_url") or _get_ollama_url()
            )
            client = OllamaClient(config)
            messages = [ChatMessage(role="user", content=query)]
            # 使用 chat_sync 同步获取完整响应
            content, reasoning, _ = client.chat_sync(
                messages,
                model=self.config.get("expert_model", "qwen3.5:9b")
            )
            return content
        except Exception as e:
            logger.info(f"[ExpertLearning] Expert generation failed: {e}")
            return None

    def _enhance_with_knowledge_graph(self, query: str) -> str:
        """用知识图谱增强查询"""
        if not self.knowledge_graph:
            return query

        try:
            # 检索相关实体
            entities = self.knowledge_graph.get_entities_by_name(query)
            if entities:
                context = "\n".join([e.name for e in entities[:5]])
                return f"参考知识：{context}\n\n问题：{query}"
        except Exception:
            pass

        return query

    def _update_knowledge_graph(
        self,
        query: str,
        expert_response: str,
        comparison: Dict
    ):
        """更新知识图谱"""
        if not self.knowledge_graph:
            return

        try:
            # 提取关键实体和关系
            self.knowledge_graph.add_entity(
                name=query[:100],
                entity_type="learning_topic",
                properties={
                    "expert_response": expert_response[:500],
                    "correction_level": comparison["correction_level"].value,
                }
            )
        except Exception as e:
            logger.info(f"[ExpertLearning] Knowledge graph update failed: {e}")

    def _update_distiller(self, query: str, expert_response: str):
        """更新蒸馏器"""
        if not self.distiller:
            return

        try:
            from core.evolution.models import DistillationCategory
            self.distiller.record_behavior(
                category=DistillationCategory.USER_HABIT,
                keywords=self._extract_keywords(query),
                context={"query": query, "expert": expert_response[:200]},
                module="expert_learning",
            )
        except Exception as e:
            logger.info(f"[ExpertLearning] Distiller update failed: {e}")

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        # 简化实现
        keywords = []
        for word in ["分析", "生成", "创建", "优化", "学习", "推理"]:
            if word in text:
                keywords.append(word)
        return keywords if keywords else ["general"]

    def _record_success(self, query: str, response: str):
        """记录本地模型成功"""
        # 缓存成功结果
        if self.cache:
            try:
                self.cache.set_l4(query, response)
            except Exception:
                pass

    def _save_learning_record(self, record: LearningRecord):
        """保存学习记录"""
        try:
            file_path = self._data_dir / f"learning_{int(record.timestamp)}.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(record.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.info(f"[ExpertLearning] Save learning record failed: {e}")

    def _load_learning_records(self):
        """加载历史学习记录"""
        try:
            for file in self._data_dir.glob("learning_*.json"):
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    record = LearningRecord(
                        query=data["query"],
                        local_response=data["local_response"],
                        expert_response=data["expert_response"],
                        correction_level=CorrectionLevel(int(data["correction_level"])),
                        correction_notes=data.get("correction_notes", ""),
                        learned_knowledge=data.get("learned_knowledge", ""),
                        timestamp=data.get("timestamp", 0),
                    )
                    self._learning_records.append(record)
        except Exception:
            pass

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = self._stats["total_queries"]
        return {
            **self._stats,
            "cache_hit_rate": self._stats["cache_hits"] / total if total > 0 else 0,
            "correction_rate": self._stats["corrections"] / total if total > 0 else 0,
            "learning_records": len(self._learning_records),
        }

    def get_performance_metrics(self, period: str = "1h") -> Dict[str, Any]:
        """
        获取性能指标（性能监控器接口）

        Args:
            period: 时间窗口 "5m", "15m", "1h", "24h"

        Returns:
            包含性能快照和调优建议的完整报告
        """
        if self._monitor:
            report = self._monitor.get_performance_report()
            # 合并学习系统特有指标
            report["learning_system"] = {
                "stats": self.get_stats(),
                "learning_records": len(self._learning_records),
                "cot_templates": self.cot_distiller.get_stats() if self.cot_distiller else {},
                "system_health_score": report.get("system_health", 0)
            }
            return report
        else:
            # 无监控器时返回基础统计
            return {
                "learning_system": {
                    "stats": self.get_stats(),
                    "learning_records": len(self._learning_records),
                },
                "monitor_available": False
            }

    def set_anomaly_callback(self, callback: Callable):
        """设置异常回调"""
        if self._monitor:
            self._monitor.set_anomaly_callback(callback)

    def set_threshold_callback(self, callback: Callable):
        """设置阈值超限回调"""
        if self._monitor:
            self._monitor.set_threshold_callback(callback)

    def evaluate_complexity(self, query: str) -> Optional[Dict[str, Any]]:
        """
        评估查询复杂度

        Returns:
            包含复杂度指标和推荐决策的字典
        """
        if not self._offload_strategy:
            return None

        metrics = self._offload_strategy.evaluate_complexity(query)
        decision = self._offload_strategy.decide(query, metrics)

        return {
            "complexity_score": metrics.complexity_score,
            "reasoning_depth": metrics.reasoning_depth,
            "recommended_model": decision.recommended_model,
            "offload_decision": decision.decision.value,
            "reason": decision.reason,
            "use_expert": decision.use_expert,
            "learn_from_expert": decision.learn_from_expert,
            "technical_terms": metrics.technical_terms,
            "is_reasoning": metrics.is_reasoning,
            "has_code": metrics.has_code,
        }

    def get_offload_stats(self) -> Optional[Dict[str, Any]]:
        """获取卸载策略统计"""
        if self._offload_strategy:
            return self._offload_strategy.get_stats()
        return None

    def record_domain_request(
        self,
        domain: str,
        latency_ms: float,
        success: bool = True,
        used_expert: bool = False,
        cache_hit: bool = False
    ):
        """记录领域请求（用于自适应压缩）"""
        if self._compressor:
            self._compressor.record_request(
                domain=domain,
                latency_ms=latency_ms,
                success=success,
                used_expert=used_expert,
                cache_hit=cache_hit
            )

    def get_compression_plan(self) -> Optional[Dict[str, Any]]:
        """获取模型压缩计划"""
        if self._compressor:
            return self._compressor.get_compression_plan()
        return None

    def get_compressor_stats(self) -> Optional[Dict[str, Any]]:
        """获取压缩器统计"""
        if self._compressor:
            return self._compressor.get_stats()
        return None

    # ── 配额管理器方法 ⭐ ────────────────────────────────────────

    def get_quota_mode(self) -> Optional[str]:
        """获取当前配额模式"""
        if self._quota_manager:
            return self._quota_manager.get_mode().value
        return None

    def set_quota_mode(self, mode: str, locked: bool = False) -> bool:
        """
        设置配额模式

        Args:
            mode: 模式名称 (harvest/maintenance/conservation)
            locked: 是否锁定

        Returns:
            bool: 是否成功
        """
        if not self._quota_manager:
            return False
        try:
            from client.src.business.expert_learning.smart_quota_manager import QuotaMode
            mode_enum = QuotaMode(mode)
            self._quota_manager.set_mode(mode_enum, locked=locked)
            return True
        except Exception:
            return False

    def can_use_external_api(
        self,
        provider: str = "deepseek",
        estimated_tokens: int = 1000,
        priority: str = "normal"
    ) -> bool:
        """检查是否可以使用外部API"""
        if not self._quota_manager:
            return True  # 默认允许
        try:
            from client.src.business.expert_learning.smart_quota_manager import Provider
            provider_enum = Provider(provider)
            return self._quota_manager.can_call(provider_enum, estimated_tokens, priority)
        except Exception:
            return True

    def get_quota_stats(self, period: str = "daily") -> Optional[Dict[str, Any]]:
        """获取配额使用统计"""
        if self._quota_manager:
            return self._quota_manager.get_usage_stats(period)
        return None

    def get_quota_recommendation(self) -> Optional[Dict[str, Any]]:
        """获取配额模式推荐"""
        if not self._quota_manager:
            return None
        rec = self._quota_manager.get_recommendation()
        return {
            "current_mode": rec.current_mode.value,
            "recommended_mode": rec.recommended_mode.value,
            "reason": rec.reason,
            "urgency": rec.urgency,
        }

    def record_api_cost(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
        success: bool = True,
    ) -> None:
        """记录API调用成本"""
        if self._quota_manager:
            try:
                from client.src.business.expert_learning.smart_quota_manager import Provider
                self._quota_manager.record_usage(
                    provider=Provider(provider),
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    success=success,
                    latency_ms=latency_ms,
                )
            except Exception:
                pass  # 忽略无效的provider

    # ── 外部提供者配置方法 ⭐ ───────────────────────────────────────

    def get_provider_manager(self):
        """获取外部提供者管理器"""
        try:
            from client.src.business.expert_learning.external_provider_config import get_provider_manager
            return get_provider_manager()
        except ImportError:
            return None

    def add_external_provider(
        self,
        name: str,
        provider_type: str,
        api_key: str = "",
        cost_type: str = "paid",
        endpoint_base_url: str = "",
        priority: int = 100,
        default_model: str = "",
        **kwargs
    ) -> Optional[str]:
        """
        添加外部API提供者

        Args:
            name: 显示名称
            provider_type: 提供者类型 (openai/deepseek/anthropic/ollama/groq等)
            api_key: API Key (可选)
            cost_type: 费用类型 (free/freemium/paid)
            endpoint_base_url: API基础URL (可选)
            priority: 优先级 (数字越小越高)
            default_model: 默认模型名

        Returns:
            str: 提供者ID 或 None
        """
        pm = self.get_provider_manager()
        if not pm:
            return None

        try:
            from client.src.business.expert_learning.external_provider_config import ProviderType, CostType


            p_type = ProviderType(provider_type.lower())
            c_type = CostType(cost_type.lower())

            return pm.add_provider(
                name=name,
                provider_type=p_type,
                api_key=api_key,
                cost_type=c_type,
                endpoint_base_url=endpoint_base_url,
                priority=priority,
                default_model=default_model,
                **kwargs
            )
        except Exception as e:
            logger.info(f"[ExpertLearning] 添加提供者失败: {e}")
            return None

    def list_external_providers(self, include_free_first: bool = True) -> List[Dict[str, Any]]:
        """
        列出所有外部提供者

        Args:
            include_free_first: 是否优先显示免费的

        Returns:
            List[Dict]: 提供者信息列表
        """
        pm = self.get_provider_manager()
        if not pm:
            return []

        providers = pm.get_available_providers(include_free_first=include_free_first)
        return [
            {
                "id": p.id,
                "name": p.name,
                "type": p.provider_type.value,
                "cost_type": p.cost_type.value,
                "is_free": p.is_free(),
                "enabled": p.enabled,
                "priority": p.priority,
                "default_model": p.default_model,
                "use_count": p.use_count,
                "daily_limit": p.daily_limit,
            }
            for p in providers
        ]

    def enable_provider(self, provider_id: str, enabled: bool = True) -> bool:
        """启用/禁用提供者"""
        pm = self.get_provider_manager()
        if not pm:
            return False
        return pm.set_enabled(provider_id, enabled)

    def remove_external_provider(self, provider_id: str) -> bool:
        """删除外部提供者"""
        pm = self.get_provider_manager()
        if not pm:
            return False
        return pm.remove_provider(provider_id)

    def get_free_providers(self) -> List[Dict[str, Any]]:
        """获取所有免费提供者"""
        pm = self.get_provider_manager()
        if not pm:
            return []

        free = pm.get_available_providers(include_free_first=True)
        free = [p for p in free if p.is_free()]
        return [
            {
                "id": p.id,
                "name": p.name,
                "type": p.provider_type.value,
                "default_model": p.default_model,
                "description": p.description,
            }
            for p in free
        ]

    def select_best_provider(
        self,
        estimated_tokens: int = 1000,
        prefer_free: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        选择最优提供者

        Args:
            estimated_tokens: 预估输入token数
            prefer_free: 是否优先免费

        Returns:
            Dict: 最优提供者信息 或 None
        """
        if self._quota_manager:
            return self._quota_manager.select_best_provider(
                estimated_tokens=estimated_tokens,
                prefer_free=prefer_free,
            )
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# 便捷工厂函数
# ═══════════════════════════════════════════════════════════════════════════════

def create_expert_learning_system(
    config: Optional[Dict] = None,
    llm_client: Optional[Any] = None,
) -> ExpertGuidedLearningSystem:
    """创建专家指导学习系统"""
    return ExpertGuidedLearningSystem(config=config, llm_client=llm_client)


# ═══════════════════════════════════════════════════════════════════════════════
# 与 HermesAgent 集成
# ═══════════════════════════════════════════════════════════════════════════════

class HermesAgentWithExpertLearning:
    """
    集成专家学习的 HermesAgent

    在原有 HermesAgent 基础上增加：
    1. 专家模型对比学习
    2. 自动知识蒸馏
    3. 渐进式能力提升
    """

    def __init__(self, agent: Any, config: Optional[Dict] = None):
        self.agent = agent
        self.learning_system = create_expert_learning_system(config)
        self.enable_learning = config.get("enable_expert_learning", True)

    def chat(self, message: str) -> str:
        """聊天入口（带学习）"""
        if not self.enable_learning:
            return self.agent.chat(message)

        result = self.learning_system.process(message)
        return result.response

    def chat_stream(self, message: str) -> Iterator:
        """流式聊天（带学习）"""
        if not self.enable_learning:
            yield from self.agent.send_message(message)
        else:
            yield from self.learning_system.process_stream(message)

    def get_learning_stats(self) -> Dict[str, Any]:
        """获取学习统计"""
        return self.learning_system.get_stats()
