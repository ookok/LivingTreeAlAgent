"""
思维链蒸馏器 (Chain of Thought Distiller)
==========================================

从专家模型的思考过程中提取思维链模板，
让本地模型学习推理模式，提升推理能力。

核心原理：
1. 对比分析：专家模型 vs 本地模型的思维链差异
2. 模板提取：从专家思维链中提取可复用的推理模式
3. 模板库：存储和索引思维链模板
4. 提示注入：在本地模型推理时注入相似模板
"""

import json
import time
import hashlib
import logging
import re
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class ReasoningType(Enum):
    CAUSAL = "causal"
    ANALOGICAL = "analogical"
    ABDUCTIVE = "abductive"
    DEDUCTIVE = "deductive"
    INDUCTIVE = "inductive"
    COUNTERFACTUAL = "counterfactual"
    SYSTEMATIC = "systematic"
    METACOGNITIVE = "metacognitive"


@dataclass
class ReasoningStep:
    order: int
    content: str
    reasoning_type: ReasoningType
    confidence: float
    is_key_step: bool


@dataclass
class ChainTemplate:
    id: str
    query_pattern: str
    query_type: str
    reasoning_steps: List[Dict]
    pattern: str
    usage_count: int = 0
    success_rate: float = 0.0
    created_at: float = field(default_factory=time.time)
    last_used: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "query_pattern": self.query_pattern,
            "query_type": self.query_type,
            "reasoning_steps": self.reasoning_steps,
            "pattern": self.pattern,
            "usage_count": self.usage_count,
            "success_rate": self.success_rate,
            "created_at": self.created_at,
            "last_used": self.last_used,
        }


@dataclass
class ReasoningRecord:
    query: str
    expert_reasoning: str
    local_reasoning: str
    expert_answer: str
    local_answer: str
    query_type: ReasoningType
    improvement_score: float
    steps: List[ReasoningStep]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            "query": self.query,
            "expert_reasoning": self.expert_reasoning,
            "local_reasoning": self.local_reasoning,
            "expert_answer": self.expert_answer,
            "local_answer": self.local_answer,
            "query_type": self.query_type.value,
            "improvement_score": self.improvement_score,
            "steps": [
                {"order": s.order, "content": s.content, "type": s.reasoning_type.value,
                 "confidence": s.confidence, "is_key": s.is_key_step}
                for s in self.steps
            ],
            "timestamp": self.timestamp,
        }


class ChainOfThoughtDistiller:
    QUERY_TYPE_KEYWORDS = {
        ReasoningType.CAUSAL: ["为什么", "原因", "导致", "由于", "所以", "因为"],
        ReasoningType.ANALOGICAL: ["像", "类似", "如同", "相比", "区别", "一样"],
        ReasoningType.DEDUCTIVE: ["因此", "所以", "得出", "推导出", "结论"],
        ReasoningType.INDUCTIVE: ["归纳", "总结", "规律", "概括", "从...可见"],
        ReasoningType.ABDUCTIVE: ["最可能", "最合理解释", "推断", "可能是"],
        ReasoningType.COUNTERFACTUAL: ["如果", "假如", "要是", "假设", "要是"],
        ReasoningType.SYSTEMATIC: ["分析", "系统", "全面", "综合", "整体"],
        ReasoningType.METACOGNITIVE: ["思考", "反思", "我觉得", "我的理解"],
    }

    KEY_STEP_SIGNALS = [
        "第一步", "首先", "关键", "核心", "最重要",
        "因为", "所以", "因此", "于是", "接着",
        "观察到", "注意到", "发现", "得出",
        "进一步", "更深层", "本质上"
    ]

    def __init__(self, data_dir: Optional[Path] = None):
        self._data_dir = data_dir or Path.home() / ".livingtree" / "cot_distiller"
        self._data_dir.mkdir(parents=True, exist_ok=True)

        self._templates: Dict[str, ChainTemplate] = {}
        self._query_index: Dict[str, List[str]] = {}
        self._records: List[ReasoningRecord] = []

        self._stats = {
            "total_records": 0,
            "templates_created": 0,
            "templates_used": 0,
            "avg_improvement": 0.0,
        }

        self._load_data()

    def record_reasoning(
        self, query: str, expert_reasoning: str, local_reasoning: str,
        expert_answer: str, local_answer: str,
        expert_meta: Optional[Dict] = None,
    ) -> ReasoningRecord:
        query_type = self._classify_query_type(query)
        expert_steps = self._extract_steps(expert_reasoning)
        local_steps = self._extract_steps(local_reasoning)

        improvement = self._calculate_improvement(
            expert_steps, local_steps, expert_answer, local_answer)

        record = ReasoningRecord(
            query=query, expert_reasoning=expert_reasoning,
            local_reasoning=local_reasoning, expert_answer=expert_answer,
            local_answer=local_answer, query_type=query_type,
            improvement_score=improvement, steps=expert_steps,
        )

        self._records.append(record)
        self._stats["total_records"] += 1

        if improvement > 0.3:
            self._extract_template(record)

        self._save_record(record)
        self._update_stats()
        return record

    def _classify_query_type(self, query: str) -> ReasoningType:
        scores = {rt: 0 for rt in ReasoningType}
        for rt, keywords in self.QUERY_TYPE_KEYWORDS.items():
            for kw in keywords:
                if kw in query:
                    scores[rt] += 1
        if max(scores.values()) == 0:
            return ReasoningType.CAUSAL
        return max(scores, key=scores.get)

    def _extract_steps(self, reasoning: str) -> List[ReasoningStep]:
        steps = []
        sentences = re.split(r'[。\n]', reasoning)
        sentences = [s.strip() for s in sentences if s.strip()]
        current_order = 1

        for sent in sentences:
            is_key = any(signal in sent for signal in self.KEY_STEP_SIGNALS)
            step_type = ReasoningType.CAUSAL
            for rt, keywords in self.QUERY_TYPE_KEYWORDS.items():
                if any(kw in sent for kw in keywords):
                    step_type = rt
                    break

            steps.append(ReasoningStep(
                order=current_order, content=sent[:200],
                reasoning_type=step_type,
                confidence=0.8 if is_key else 0.6, is_key_step=is_key))
            current_order += 1

        return steps

    def _calculate_improvement(
        self, expert_steps: List[ReasoningStep],
        local_steps: List[ReasoningStep],
        expert_answer: str, local_answer: str,
    ) -> float:
        scores = []
        if len(local_steps) > 0:
            step_diff = abs(len(expert_steps) - len(local_steps)) / max(len(expert_steps), 1)
            scores.append(1 - step_diff)
        else:
            scores.append(0.5)

        expert_keys = sum(1 for s in expert_steps if s.is_key_step)
        local_keys = sum(1 for s in local_steps if s.is_key_step)
        if expert_keys > 0:
            scores.append(local_keys / expert_keys)
        else:
            scores.append(1.0)

        answer_sim = self._text_similarity(expert_answer, local_answer)
        scores.append(answer_sim)
        return sum(scores) / len(scores)

    def _text_similarity(self, text1: str, text2: str) -> float:
        if not text1 or not text2:
            return 0.0
        set1 = set(text1)
        set2 = set(text2)
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0

    def _extract_template(self, record: ReasoningRecord):
        template_id = hashlib.md5(
            f"{record.query_type.value}{record.query[:50]}{time.time()}".encode()
        ).hexdigest()[:12]

        query_pattern = self._extract_query_pattern(record.query)
        pattern = self._generate_pattern_summary(record.steps)

        template = ChainTemplate(
            id=template_id, query_pattern=query_pattern,
            query_type=record.query_type.value,
            reasoning_steps=[
                {"order": s.order, "content": s.content,
                 "type": s.reasoning_type.value, "is_key": s.is_key_step}
                for s in record.steps
            ],
            pattern=pattern,
        )

        self._templates[template_id] = template
        self._stats["templates_created"] += 1

        for keyword in query_pattern.split():
            if keyword not in self._query_index:
                self._query_index[keyword] = []
            self._query_index[keyword].append(template_id)

        self._save_template(template)
        logger.info(f"[CoTDistiller] 提取模板: {template_id} (类型: {record.query_type.value})")

    def _extract_query_pattern(self, query: str) -> str:
        pattern = query
        for w in ["为什么", "是什么", "如何", "怎样", "怎么", "请问"]:
            pattern = pattern.replace(w, "")

        keywords = []
        for word in ["分析", "解释", "比较", "判断", "推理"]:
            if word in pattern:
                keywords.append(word)

        entities = re.findall(r'[\u4e00-\u9fff]{2,4}', pattern)
        keywords.extend(entities[:5])
        return " ".join(keywords) if keywords else pattern[:20]

    def _generate_pattern_summary(self, steps: List[ReasoningStep]) -> str:
        if not steps:
            return ""
        key_steps = [s for s in steps if s.is_key_step]
        source = key_steps[:3] if key_steps else steps[:3]
        return " → ".join([
            s.content[:15] + "..." if len(s.content) > 15 else s.content
            for s in source
        ])

    def get_template(self, query: str) -> Optional[ChainTemplate]:
        query_type = self._classify_query_type(query)
        pattern = self._extract_query_pattern(query)

        candidates = []
        for keyword in pattern.split():
            if keyword in self._query_index:
                for tid in self._query_index[keyword]:
                    if tid in self._templates:
                        candidates.append(self._templates[tid])

        candidates = sorted(
            candidates,
            key=lambda t: (
                self._pattern_similarity(query, t.query_pattern),
                t.success_rate, -t.usage_count),
            reverse=True)

        if candidates:
            best = candidates[0]
            best.usage_count += 1
            best.last_used = time.time()
            self._stats["templates_used"] += 1
            return best
        return None

    def _pattern_similarity(self, query: str, template_pattern: str) -> float:
        query_words = set(query)
        pattern_words = set(template_pattern.split())
        intersection = len(query_words & pattern_words)
        union = len(query_words | pattern_words)
        return intersection / union if union > 0 else 0.0

    def get_prompt_hint(self, query: str) -> Optional[str]:
        template = self.get_template(query)
        if not template:
            return None

        hints = [
            f"参考类似问题的推理模式: {template.pattern}",
            "", "推理步骤:",
        ]
        for step in template.reasoning_steps[:5]:
            if step.get("is_key"):
                hints.append(f"  [{step['order']}] {step['content']}")
        return "\n".join(hints)

    def get_stats(self) -> Dict[str, Any]:
        return {
            **self._stats,
            "templates_in_library": len(self._templates),
            "records_in_memory": len(self._records),
        }

    def _save_record(self, record: ReasoningRecord):
        try:
            file_path = self._data_dir / f"record_{int(record.timestamp)}.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(record.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.debug(f"[CoTDistiller] 保存记录失败: {e}")

    def _save_template(self, template: ChainTemplate):
        try:
            file_path = self._data_dir / "templates" / f"{template.id}.json"
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(template.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.debug(f"[CoTDistiller] 保存模板失败: {e}")

    def _load_data(self):
        templates_dir = self._data_dir / "templates"
        if templates_dir.exists():
            for file in templates_dir.glob("*.json"):
                try:
                    with open(file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        template = ChainTemplate(
                            id=data["id"], query_pattern=data["query_pattern"],
                            query_type=data["query_type"],
                            reasoning_steps=data["reasoning_steps"],
                            pattern=data["pattern"],
                            usage_count=data.get("usage_count", 0),
                            success_rate=data.get("success_rate", 0.0),
                            created_at=data.get("created_at", 0),
                            last_used=data.get("last_used", 0),
                        )
                        self._templates[template.id] = template
                        for keyword in template.query_pattern.split():
                            if keyword not in self._query_index:
                                self._query_index[keyword] = []
                            if template.id not in self._query_index[keyword]:
                                self._query_index[keyword].append(template.id)
                except Exception:
                    pass

        for file in sorted(self._data_dir.glob("record_*.json"))[-100:]:
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._records.append(data)
            except Exception:
                pass

        self._stats["total_records"] = len(self._records)
        self._stats["templates_created"] = len(self._templates)

    def _update_stats(self):
        if self._records:
            self._stats["avg_improvement"] = sum(
                r.improvement_score for r in self._records
            ) / len(self._records)


__all__ = [
    "ChainOfThoughtDistiller",
    "ChainTemplate",
    "ReasoningRecord",
    "ReasoningStep",
    "ReasoningType",
]
