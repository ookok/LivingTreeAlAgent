# -*- coding: utf-8 -*-
"""
思维链蒸馏器 (Chain of Thought Distiller)
==========================================

创新功能：从专家模型的思考过程中提取思维链模板，
让本地模型学习推理模式，提升推理能力。

核心原理：
1. 对比分析：专家模型 vs 本地模型的思维链差异
2. 模板提取：从专家思维链中提取可复用的推理模式
3. 模板库：存储和索引思维链模板
4. 提示注入：在本地模型推理时注入相似模板

使用示例：
    distiller = ChainOfThoughtDistiller()

    # 记录专家思维链
    distiller.record_reasoning(
        query="为什么天空是蓝色的",
        expert_reasoning="1. 先识别问题类型（物理/光学）...",
        local_reasoning="天空是蓝色的因为...",
        expert_answer="因为瑞利散射..."
    )

    # 获取相似模板
    template = distiller.get_template("为什么海水是蓝色的")
    if template:
        print(f"使用模板: {template['pattern']}")
"""

from __future__ import annotations

import json
import time
import hashlib
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
import re


# ═══════════════════════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════════════════════

class ReasoningType(Enum):
    """推理类型"""
    CAUSAL = "causal"           # 因果推理
    ANALOGICAL = "analogical"   # 类比推理
    ABDUCTIVE = "abductive"     # 溯因推理
    DEDUCTIVE = "deductive"     # 演绎推理
    INDUCTIVE = "inductive"    # 归纳推理
    COUNTERFACTUAL = "counterfactual"  # 反事实推理
    SYSTEMATIC = "systematic"   # 系统性推理
    METACOGNITIVE = "metacognitive"  # 元认知


@dataclass
class ReasoningStep:
    """推理步骤"""
    order: int           # 步骤序号
    content: str        # 步骤内容
    reasoning_type: ReasoningType  # 推理类型
    confidence: float   # 置信度
    is_key_step: bool   # 是否是关键步骤


@dataclass
class ChainTemplate:
    """思维链模板"""
    id: str
    query_pattern: str           # 问题模式（提取的关键词）
    query_type: str             # 问题类型
    reasoning_steps: List[Dict] # 推理步骤列表
    pattern: str                # 模式摘要
    usage_count: int = 0        # 使用次数
    success_rate: float = 0.0   # 成功率
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
    """推理记录"""
    query: str
    expert_reasoning: str
    local_reasoning: str
    expert_answer: str
    local_answer: str
    query_type: ReasoningType
    improvement_score: float  # 0-1，改进程度
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


# ═══════════════════════════════════════════════════════════════════════════════
# 思维链蒸馏器
# ═══════════════════════════════════════════════════════════════════════════════

class ChainOfThoughtDistiller:
    """
    思维链蒸馏器

    功能：
    1. 记录专家和本地模型的推理过程
    2. 提取思维链模板
    3. 分析推理差异
    4. 提供相似问题的模板提示
    """

    # 问题类型关键词
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

    # 关键推理信号词
    KEY_STEP_SIGNALS = [
        "第一步", "首先", "关键", "核心", "最重要",
        "因为", "所以", "因此", "于是", "接着",
        "观察到", "注意到", "发现", "得出",
        "进一步", "更深层", "本质上"
    ]

    def __init__(self, data_dir: Optional[Path] = None):
        """
        Args:
            data_dir: 数据存储目录
        """
        self._data_dir = data_dir or Path.home() / ".hermes-desktop" / "cot_distiller"
        self._data_dir.mkdir(parents=True, exist_ok=True)

        # 模板库
        self._templates: Dict[str, ChainTemplate] = {}
        self._query_index: Dict[str, List[str]] = {}  # 关键词 -> 模板ID

        # 推理记录
        self._records: List[ReasoningRecord] = []

        # 统计
        self._stats = {
            "total_records": 0,
            "templates_created": 0,
            "templates_used": 0,
            "avg_improvement": 0.0,
        }

        # 加载已有数据
        self._load_data()

    def record_reasoning(
        self,
        query: str,
        expert_reasoning: str,
        local_reasoning: str,
        expert_answer: str,
        local_answer: str,
        expert_meta: Optional[Dict] = None,
    ) -> ReasoningRecord:
        """
        记录专家和本地模型的推理过程

        Args:
            query: 用户问题
            expert_reasoning: 专家模型的推理过程
            local_reasoning: 本地模型的推理过程
            expert_answer: 专家模型的答案
            local_answer: 本地模型的答案

        Returns:
            ReasoningRecord
        """
        # 分析问题类型
        query_type = self._classify_query_type(query)

        # 提取推理步骤
        expert_steps = self._extract_steps(expert_reasoning)
        local_steps = self._extract_steps(local_reasoning)

        # 计算改进分数
        improvement = self._calculate_improvement(
            expert_steps, local_steps, expert_answer, local_answer
        )

        # 创建记录
        record = ReasoningRecord(
            query=query,
            expert_reasoning=expert_reasoning,
            local_reasoning=local_reasoning,
            expert_answer=expert_answer,
            local_answer=local_answer,
            query_type=query_type,
            improvement_score=improvement,
            steps=expert_steps,
        )

        self._records.append(record)
        self._stats["total_records"] += 1

        # 如果改进明显，提取模板
        if improvement > 0.3:
            self._extract_template(record)

        # 保存
        self._save_record(record)
        self._update_stats()

        return record

    def _classify_query_type(self, query: str) -> ReasoningType:
        """分类问题类型"""
        scores = {rt: 0 for rt in ReasoningType}

        for rt, keywords in self.QUERY_TYPE_KEYWORDS.items():
            for kw in keywords:
                if kw in query:
                    scores[rt] += 1

        if max(scores.values()) == 0:
            return ReasoningType.CAUSAL  # 默认

        return max(scores, key=scores.get)

    def _extract_steps(self, reasoning: str) -> List[ReasoningStep]:
        """从推理文本中提取步骤"""
        steps = []

        # 按句子分割
        sentences = re.split(r'[。\n]', reasoning)
        sentences = [s.strip() for s in sentences if s.strip()]

        # 按序号分割（如果有）
        numbered_pattern = r'^\s*(\d+[.)、]|\[?\d+\]?)\s*'
        current_order = 1

        for sent in sentences:
            # 检查是否关键步骤
            is_key = any(signal in sent for signal in self.KEY_STEP_SIGNALS)

            # 判断推理类型
            step_type = ReasoningType.CAUSAL
            for rt, keywords in self.QUERY_TYPE_KEYWORDS.items():
                if any(kw in sent for kw in keywords):
                    step_type = rt
                    break

            steps.append(ReasoningStep(
                order=current_order,
                content=sent[:200],  # 截断
                reasoning_type=step_type,
                confidence=0.8 if is_key else 0.6,
                is_key_step=is_key,
            ))
            current_order += 1

        return steps

    def _calculate_improvement(
        self,
        expert_steps: List[ReasoningStep],
        local_steps: List[ReasoningStep],
        expert_answer: str,
        local_answer: str,
    ) -> float:
        """计算改进分数"""
        scores = []

        # 步骤数量差异
        if len(local_steps) > 0:
            step_diff = abs(len(expert_steps) - len(local_steps)) / max(len(expert_steps), 1)
            scores.append(1 - step_diff)
        else:
            scores.append(0.5)

        # 关键步骤覆盖
        expert_keys = sum(1 for s in expert_steps if s.is_key_step)
        local_keys = sum(1 for s in local_steps if s.is_key_step)
        if expert_keys > 0:
            key_coverage = local_keys / expert_keys
            scores.append(key_coverage)
        else:
            scores.append(1.0)

        # 答案相似度
        answer_sim = self._text_similarity(expert_answer, local_answer)
        scores.append(answer_sim)

        return sum(scores) / len(scores)

    def _text_similarity(self, text1: str, text2: str) -> float:
        """简单文本相似度"""
        if not text1 or not text2:
            return 0.0

        set1 = set(text1)
        set2 = set(text2)
        intersection = len(set1 & set2)
        union = len(set1 | set2)

        return intersection / union if union > 0 else 0.0

    def _extract_template(self, record: ReasoningRecord):
        """从记录中提取模板"""
        # 生成唯一 ID
        template_id = hashlib.md5(
            f"{record.query_type.value}{record.query[:50]}{time.time()}".encode()
        ).hexdigest()[:12]

        # 提取问题模式（关键词）
        query_pattern = self._extract_query_pattern(record.query)

        # 生成模式摘要
        pattern = self._generate_pattern_summary(record.steps)

        # 创建模板
        template = ChainTemplate(
            id=template_id,
            query_pattern=query_pattern,
            query_type=record.query_type.value,
            reasoning_steps=[
                {
                    "order": s.order,
                    "content": s.content,
                    "type": s.reasoning_type.value,
                    "is_key": s.is_key_step,
                }
                for s in record.steps
            ],
            pattern=pattern,
        )

        self._templates[template_id] = template
        self._stats["templates_created"] += 1

        # 更新索引
        for keyword in query_pattern.split():
            if keyword not in self._query_index:
                self._query_index[keyword] = []
            self._query_index[keyword].append(template_id)

        # 保存模板
        self._save_template(template)

        print(f"[CoTDistiller] 提取模板: {template_id} (类型: {record.query_type.value})")

    def _extract_query_pattern(self, query: str) -> str:
        """提取问题模式"""
        # 移除常见疑问词
        pattern = query
        for w in ["为什么", "是什么", "如何", "怎样", "怎么", "请问"]:
            pattern = pattern.replace(w, "")

        # 提取关键词
        keywords = []
        for word in ["分析", "解释", "比较", "判断", "推理"]:
            if word in pattern:
                keywords.append(word)

        # 添加名词实体
        entities = re.findall(r'[\u4e00-\u9fff]{2,4}', pattern)
        keywords.extend(entities[:5])

        return " ".join(keywords) if keywords else pattern[:20]

    def _generate_pattern_summary(self, steps: List[ReasoningStep]) -> str:
        """生成模式摘要"""
        if not steps:
            return ""

        key_steps = [s for s in steps if s.is_key_step]
        if key_steps:
            # 提取关键步骤的关键词
            summary = " → ".join([
                s.content[:15] + "..." if len(s.content) > 15 else s.content
                for s in key_steps[:3]
            ])
        else:
            # 使用前几个步骤
            summary = " → ".join([
                s.content[:15] + "..." if len(s.content) > 15 else s.content
                for s in steps[:3]
            ])

        return summary

    def get_template(self, query: str) -> Optional[ChainTemplate]:
        """
        根据问题获取相似模板

        Args:
            query: 用户问题

        Returns:
            最相似的模板，或 None
        """
        # 分类问题类型
        query_type = self._classify_query_type(query)

        # 提取关键词
        pattern = self._extract_query_pattern(query)

        # 搜索相似模板
        candidates = []
        for keyword in pattern.split():
            if keyword in self._query_index:
                for tid in self._query_index[keyword]:
                    if tid in self._templates:
                        candidates.append(self._templates[tid])

        # 按相似度和成功率排序
        candidates = sorted(
            candidates,
            key=lambda t: (
                self._pattern_similarity(query, t.query_pattern),
                t.success_rate,
                -t.usage_count  # 优先使用次数多的
            ),
            reverse=True
        )

        if candidates:
            best = candidates[0]
            best.usage_count += 1
            best.last_used = time.time()
            self._stats["templates_used"] += 1
            return best

        return None

    def _pattern_similarity(self, query: str, template_pattern: str) -> float:
        """计算查询与模板的相似度"""
        query_words = set(query)
        pattern_words = set(template_pattern.split())
        intersection = len(query_words & pattern_words)
        union = len(query_words | pattern_words)
        return intersection / union if union > 0 else 0.0

    def get_prompt_hint(self, query: str) -> Optional[str]:
        """
        获取提示（用于注入到本地模型）

        Args:
            query: 用户问题

        Returns:
            提示文本，或 None
        """
        template = self.get_template(query)
        if not template:
            return None

        # 生成提示
        hints = [
            f"参考类似问题的推理模式: {template.pattern}",
            "",
            "推理步骤:",
        ]

        for step in template.reasoning_steps[:5]:
            if step.get("is_key"):
                hints.append(f"  [{step['order']}] {step['content']}")

        return "\n".join(hints)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self._stats,
            "templates_in_library": len(self._templates),
            "records_in_memory": len(self._records),
        }

    # ── 持久化 ──────────────────────────────────────────────────────────

    def _save_record(self, record: ReasoningRecord):
        """保存推理记录"""
        try:
            file_path = self._data_dir / f"record_{int(record.timestamp)}.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(record.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CoTDistiller] 保存记录失败: {e}")

    def _save_template(self, template: ChainTemplate):
        """保存模板"""
        try:
            file_path = self._data_dir / "templates" / f"{template.id}.json"
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(template.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CoTDistiller] 保存模板失败: {e}")

    def _load_data(self):
        """加载已有数据"""
        # 加载模板
        templates_dir = self._data_dir / "templates"
        if templates_dir.exists():
            for file in templates_dir.glob("*.json"):
                try:
                    with open(file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        template = ChainTemplate(
                            id=data["id"],
                            query_pattern=data["query_pattern"],
                            query_type=data["query_type"],
                            reasoning_steps=data["reasoning_steps"],
                            pattern=data["pattern"],
                            usage_count=data.get("usage_count", 0),
                            success_rate=data.get("success_rate", 0.0),
                            created_at=data.get("created_at", 0),
                            last_used=data.get("last_used", 0),
                        )
                        self._templates[template.id] = template

                        # 更新索引
                        for keyword in template.query_pattern.split():
                            if keyword not in self._query_index:
                                self._query_index[keyword] = []
                            if template.id not in self._query_index[keyword]:
                                self._query_index[keyword].append(template.id)
                except Exception:
                    pass

        # 加载最近记录
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
        """更新统计"""
        if self._records:
            self._stats["avg_improvement"] = sum(
                r.improvement_score for r in self._records
            ) / len(self._records)


# ═══════════════════════════════════════════════════════════════════════════════
# 与 ExpertGuidedLearningSystem 集成
# ═══════════════════════════════════════════════════════════════════════════════

class ExpertGuidedLearningSystem:
    """前向兼容：添加思维链蒸馏支持"""

    def __init__(self, config=None, llm_client=None):
        # ... 原有初始化 ...

        # 思维链蒸馏器
        self._cot_distiller = ChainOfThoughtDistiller()
        print("[ExpertLearning] ✅ 思维链蒸馏器已启用")

    def _generate_expert(self, query: str) -> Optional[str]:
        """专家模型生成（增强版：包含思维链）"""
        # ... 原有逻辑 ...

        # 如果有思维链提示
        hint = self._cot_distiller.get_prompt_hint(query)
        if hint:
            print(f"[ExpertLearning] 使用思维链提示: {hint[:50]}...")

        # 返回响应
        return response


def create_expert_learning_system(
    config=None,
    llm_client=None,
) -> ExpertGuidedLearningSystem:
    """创建专家指导学习系统（增强版）"""
    return ExpertGuidedLearningSystem(config=config, llm_client=llm_client)
