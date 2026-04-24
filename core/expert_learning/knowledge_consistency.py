# -*- coding: utf-8 -*-
"""
多模型知识一致性验证系统 (Knowledge Consistency Verifier)
=========================================================

核心设计理念：让多个模型同时推理，通过一致性检测确保答案质量。

功能:
1. 多模型并行推理 - 同时调用多个模型生成答案
2. 一致性检测 - 检测多个答案之间的共识程度
3. 投票机制 - 多数投票决定最终答案
4. 争议检测 - 识别模型之间的分歧
5. 置信度评估 - 基于一致性给出置信度评分

Author: LivingTreeAI Agent
Date: 2026-04-24
"""

from __future__ import annotations

import json
import time
import hashlib
import asyncio
import threading
from typing import Optional, List, Dict, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import Counter
import re


# ═══════════════════════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════════════════════

class ConsensusLevel(Enum):
    """共识等级"""
    FULL = "full"           # 完全一致
    HIGH = "high"          # 高度一致
    PARTIAL = "partial"    # 部分一致
    LOW = "low"            # 低度一致
    CONFLICT = "conflict"  # 冲突


class VerificationStatus(Enum):
    """验证状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class ModelResponse:
    """模型响应"""
    model_id: str
    model_name: str
    content: str
    latency_ms: float
    confidence: float = 0.5
    timestamp: float = 0
    error: Optional[str] = None
    key_facts: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.timestamp == 0:
            self.timestamp = time.time()


@dataclass
class ConsistencyResult:
    """一致性验证结果"""
    consensus_level: ConsensusLevel
    consensus_score: float
    agreeing_models: List[str]
    conflicting_models: List[str]
    key_facts_agreement: Dict[str, float]
    final_answer: str
    confidence: float
    disputed_facts: List[str] = field(default_factory=list)
    verification_time_ms: float = 0
    models_used: List[str] = field(default_factory=list)


@dataclass
class VerificationReport:
    """验证报告"""
    query: str
    status: VerificationStatus
    result: Optional[ConsistencyResult]
    all_responses: List[ModelResponse]
    recommendation: str
    metadata: Dict[str, Any] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════════
# 一致性检测算法
# ═══════════════════════════════════════════════════════════════════════════════

class ConsistencyChecker:
    """一致性检测算法"""

    def __init__(self, min_consensus_threshold: float = 0.6):
        self.min_consensus_threshold = min_consensus_threshold

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度"""
        words1 = self._tokenize(text1)
        words2 = self._tokenize(text2)

        if not words1 or not words2:
            return 0.0

        # Jaccard
        set1, set2 = set(words1), set(words2)
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        jaccard = intersection / union if union > 0 else 0.0

        # Length ratio
        len_ratio = min(len(text1), len(text2)) / max(len(text1), len(text2), 1)

        return jaccard * 0.7 + len_ratio * 0.3

    def extract_key_facts(self, text: str) -> List[str]:
        """提取关键事实"""
        facts = []

        # Numbers with units
        number_patterns = [
            r'\d+(?:\.\d+)?%',
            r'\d+(?:\.\d+)?\s*(?:个|条|次|年|月|日|时|分|秒|元|美元)',
            r'\d{4}[-/年]\d{1,2}',
        ]
        for pattern in number_patterns:
            matches = re.findall(pattern, text)
            facts.extend(matches)

        # Proper nouns
        proper_nouns = re.findall(r'[\u4e00-\u9fff]{2,}(?:公司|大学|国家|组织)|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+', text)
        facts.extend(proper_nouns)

        return list(set(facts))[:10]

    def calculate_fact_agreement(self, responses: List[ModelResponse]) -> Tuple[Dict[str, float], List[str]]:
        """计算关键事实一致性"""
        all_facts = []
        for response in responses:
            all_facts.extend(response.key_facts)

        fact_counter = Counter(all_facts)
        total_models = len(responses)

        fact_agreement = {}
        disputed_facts = []

        for fact, count in fact_counter.items():
            agreement = count / total_models
            fact_agreement[fact] = agreement
            if agreement < 0.5:
                disputed_facts.append(fact)

        return fact_agreement, disputed_facts

    def _tokenize(self, text: str) -> List[str]:
        """简单分词"""
        tokens = re.findall(r'[\w]+', text.lower())
        stopwords = {'的', '了', '是', '在', '和', '与', '或', '这', '那', '有', '我', '你', '他'}
        return [t for t in tokens if len(t) > 1 and t not in stopwords]


# ═══════════════════════════════════════════════════════════════════════════════
# 多模型推理器
# ═══════════════════════════════════════════════════════════════════════════════

class MultiModelInferrer:
    """多模型并行推理器"""

    def __init__(self, timeout_seconds: float = 30.0):
        self.timeout_seconds = timeout_seconds
        self._model_clients: Dict[str, Dict] = {}

    def register_model(self, model_id: str, model_name: str, client: Any):
        """注册模型"""
        self._model_clients[model_id] = {"name": model_name, "client": client}

    async def infer_async(self, query: str, model_ids: List[str], context: Optional[Dict] = None) -> List[ModelResponse]:
        """异步并行推理"""
        tasks = []
        for model_id in model_ids:
            if model_id in self._model_clients:
                tasks.append(self._call_model(model_id, query, context))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [
            r if not isinstance(r, Exception) else ModelResponse(model_id="error", model_name="error", content="", latency_ms=0, error=str(r))
            for r in results
        ]

    async def _call_model(self, model_id: str, query: str, context: Optional[Dict]) -> ModelResponse:
        """调用单个模型"""
        start_time = time.time()
        model_info = self._model_clients.get(model_id, {})

        if not model_info:
            return ModelResponse(model_id=model_id, model_name=model_id, content="", latency_ms=0, error="Model not found")

        try:
            client = model_info["client"]
            model_name = model_info["name"]

            if hasattr(client, 'chat_sync'):
                messages = [{"role": "user", "content": query}]
                content, _, _ = client.chat_sync(messages, model=model_name)
            elif hasattr(client, 'chat'):
                response = await asyncio.wait_for(asyncio.to_thread(client.chat, messages=[{"role": "user", "content": query}]), timeout=self.timeout_seconds)
                content = response.choices[0].message.content
            else:
                raise ValueError(f"Unsupported client type: {type(client).__name__}")

            latency_ms = (time.time() - start_time) * 1000
            checker = ConsistencyChecker()
            key_facts = checker.extract_key_facts(content)

            return ModelResponse(model_id=model_id, model_name=model_name, content=content, latency_ms=latency_ms, confidence=0.8, key_facts=key_facts)

        except Exception as e:
            return ModelResponse(model_id=model_id, model_name=model_info.get("name", model_id), content="", latency_ms=(time.time() - start_time) * 1000, error=str(e))

    def infer_sync(self, query: str, model_ids: List[str], context: Optional[Dict] = None) -> List[ModelResponse]:
        """同步推理"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self.infer_async(query, model_ids, context))


# ═══════════════════════════════════════════════════════════════════════════════
# 投票决策器
# ═══════════════════════════════════════════════════════════════════════════════

class VotingDecider:
    """投票决策器"""

    def __init__(self, similarity_threshold: float = 0.7):
        self.similarity_threshold = similarity_threshold
        self._checker = ConsistencyChecker()

    def decide(self, responses: List[ModelResponse], strategy: str = "majority") -> Tuple[str, List[str], List[str]]:
        """决策最终答案"""
        valid = [r for r in responses if not r.error]
        if not valid:
            return "无法获取有效答案", [], []
        if len(valid) == 1:
            return valid[0].content, [valid[0].model_id], []

        return self._majority_vote(valid) if strategy == "majority" else self._similarity_vote(valid)

    def _majority_vote(self, responses: List[ModelResponse]) -> Tuple[str, List[str], List[str]]:
        """多数投票"""
        groups: Dict[str, List[ModelResponse]] = {}
        for r in responses:
            key = r.content[:100]
            if key not in groups:
                groups[key] = []
            groups[key].append(r)

        max_group = max(groups.values(), key=len)
        agreeing = [r.model_id for r in max_group]
        conflicting = [r.model_id for r in responses if r.model_id not in agreeing]
        final = max(max_group, key=lambda r: len(r.content)).content

        return final, agreeing, conflicting

    def _similarity_vote(self, responses: List[ModelResponse]) -> Tuple[str, List[str], List[str]]:
        """相似度投票"""
        agreeing_groups = []
        processed = set()

        for i, r1 in enumerate(responses):
            if r1.model_id in processed:
                continue
            group = [r1]
            for r2 in responses[i+1:]:
                if r2.model_id in processed:
                    continue
                if self._checker.calculate_similarity(r1.content, r2.content) >= self.similarity_threshold:
                    group.append(r2)
                    processed.add(r2.model_id)
            agreeing_groups.append(group)
            processed.add(r1.model_id)

        max_group = max(agreeing_groups, key=len)
        agreeing = [r.model_id for r in max_group]
        conflicting = [r.model_id for r in responses if r.model_id not in agreeing]

        return max(max_group, key=lambda r: len(r.content)).content, agreeing, conflicting


# ═══════════════════════════════════════════════════════════════════════════════
# 知识一致性验证器
# ═══════════════════════════════════════════════════════════════════════════════

class KnowledgeConsistencyVerifier:
    """
    多模型知识一致性验证器

    使用方式:
    ```python
    verifier = KnowledgeConsistencyVerifier()
    verifier.register_model("ollama_9b", "qwen3.5:9b", ollama_client)
    report = verifier.verify("太阳从哪边升起？")
    print(report.result.consensus_level)
    ```
    """

    def __init__(self, min_models: int = 2, consensus_threshold: float = 0.6, timeout_seconds: float = 30.0):
        self.min_models = min_models
        self.consensus_threshold = consensus_threshold
        self.timeout_seconds = timeout_seconds

        self._inferrer = MultiModelInferrer(timeout_seconds)
        self._checker = ConsistencyChecker(min_consensus_threshold=consensus_threshold)
        self._voter = VotingDecider()

        self._stats = {"total_verifications": 0, "full_consensus_count": 0, "partial_consensus_count": 0, "conflict_count": 0}

    def register_model(self, model_id: str, model_name: str, client: Any):
        """注册模型"""
        self._inferrer.register_model(model_id, model_name, client)

    def get_registered_models(self) -> List[Dict[str, str]]:
        """获取已注册的模型"""
        return [{"id": mid, "name": info["name"]} for mid, info in self._inferrer._model_clients.items()]

    def verify(self, query: str, model_ids: Optional[List[str]] = None, context: Optional[Dict] = None, wait_for_all: bool = True) -> VerificationReport:
        """验证查询的一致性"""
        start_time = time.time()
        self._stats["total_verifications"] += 1

        if model_ids is None:
            model_ids = list(self._inferrer._model_clients.keys())

        if len(model_ids) < self.min_models:
            return VerificationReport(query=query, status=VerificationStatus.FAILED, result=None, all_responses=[], recommendation="注册的模型数量不足", metadata={"error": "min_models_not_met"})

        responses = self._inferrer.infer_sync(query, model_ids, context)
        valid = [r for r in responses if not r.error]

        if len(valid) < self.min_models:
            return VerificationReport(query=query, status=VerificationStatus.FAILED, result=None, all_responses=responses, recommendation="有效模型响应不足", metadata={"error": "insufficient_responses"})

        result = self._analyze_consistency(query, valid)
        verification_time_ms = (time.time() - start_time) * 1000

        return VerificationReport(
            query=query, status=VerificationStatus.COMPLETED,
            result=ConsistencyResult(
                consensus_level=result["level"], consensus_score=result["score"],
                agreeing_models=result["agreeing"], conflicting_models=result["conflicting"],
                key_facts_agreement=result["fact_agreement"], final_answer=result["final_answer"],
                confidence=result["confidence"], disputed_facts=result["disputed_facts"],
                verification_time_ms=verification_time_ms, models_used=[r.model_id for r in valid]
            ),
            all_responses=responses, recommendation=self._generate_recommendation(result),
            metadata={"models_count": len(valid), "verification_time_ms": verification_time_ms}
        )

    def _analyze_consistency(self, query: str, responses: List[ModelResponse]) -> Dict:
        """分析一致性"""
        similarities = []
        for i, r1 in enumerate(responses):
            for r2 in responses[i+1:]:
                similarities.append(self._checker.calculate_similarity(r1.content, r2.content))

        avg_similarity = sum(similarities) / len(similarities) if similarities else 0
        fact_agreement, disputed_facts = self._checker.calculate_fact_agreement(responses)
        final_answer, agreeing, conflicting = self._voter.decide(responses)

        if avg_similarity >= 0.8:
            level = ConsensusLevel.FULL
        elif avg_similarity >= 0.6:
            level = ConsensusLevel.HIGH
        elif avg_similarity >= 0.4:
            level = ConsensusLevel.PARTIAL
        elif avg_similarity >= 0.2:
            level = ConsensusLevel.LOW
        else:
            level = ConsensusLevel.CONFLICT

        agreeing_ratio = len(agreeing) / len(responses)
        confidence = agreeing_ratio * avg_similarity

        if level == ConsensusLevel.FULL:
            self._stats["full_consensus_count"] += 1
        elif level in [ConsensusLevel.HIGH, ConsensusLevel.PARTIAL]:
            self._stats["partial_consensus_count"] += 1
        else:
            self._stats["conflict_count"] += 1

        return {"level": level, "score": avg_similarity, "final_answer": final_answer, "agreeing": agreeing, "conflicting": conflicting, "fact_agreement": fact_agreement, "disputed_facts": disputed_facts, "confidence": confidence}

    def _generate_recommendation(self, result: Dict) -> str:
        """生成建议"""
        level = result["level"]
        if level == ConsensusLevel.FULL:
            return "答案高度可信，多个模型完全一致。"
        elif level == ConsensusLevel.HIGH:
            return "答案可信，大多数模型意见一致。"
        elif level == ConsensusLevel.PARTIAL:
            return f"答案部分可信，存在{len(result['disputed_facts'])}个争议点，建议核实。"
        elif level == ConsensusLevel.LOW:
            return "答案可信度较低，建议查阅多个来源后判断。"
        else:
            return "模型之间存在严重分歧，建议咨询专业人士。"

    def get_stats(self) -> Dict:
        """获取统计"""
        total = self._stats["total_verifications"]
        if total == 0:
            return {**self._stats, "consensus_rate": 0}
        return {**self._stats, "consensus_rate": self._stats["full_consensus_count"] / total, "conflict_rate": self._stats["conflict_count"] / total}

    def quick_check(self, query: str, answer: str) -> Dict:
        """快速检查单个答案"""
        key_facts = self._checker.extract_key_facts(answer)
        return {"query": query, "answer": answer, "extracted_facts": key_facts, "fact_count": len(key_facts), "estimated_confidence": min(len(key_facts) * 0.1 + 0.3, 0.9)}


# ═══════════════════════════════════════════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("多模型知识一致性验证系统测试")
    print("=" * 60)

    verifier = KnowledgeConsistencyVerifier()

    print("\n[Test 1: 相似度计算]")
    checker = ConsistencyChecker()
    text1 = "Python是一种高级编程语言，广泛用于Web开发、数据分析和AI领域。"
    text2 = "Python是高级编程语言，常用于Web、数据分析和人工智能。"
    print(f"  相似度: {checker.calculate_similarity(text1, text2):.2%}")

    print("\n[Test 2: 关键事实提取]")
    text3 = "2024年GDP增长5.2%，腾讯公司市值超过3万亿元。"
    print(f"  事实: {checker.extract_key_facts(text3)}")

    print("\n[Test 3: 投票决策]")
    voter = VotingDecider()
    responses = [
        ModelResponse("m1", "模型A", "答案是Python。", 100),
        ModelResponse("m2", "模型B", "答案是Python。", 150),
        ModelResponse("m3", "模型C", "答案是Java。", 200),
    ]
    answer, agreeing, conflicting = voter.decide(responses)
    print(f"  答案: {answer}")
    print(f"  同意: {agreeing}, 反对: {conflicting}")

    print("\n" + "=" * 60)
