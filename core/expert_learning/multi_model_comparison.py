# -*- coding: utf-8 -*-
"""
多模型对比系统 (Multi-Model Comparison)
=====================================

多个模型同时推理并对比结果，支持并行执行和差异分析。

功能:
1. 并行推理 - 同时调用多个模型
2. 差异分析 - 分析模型输出差异
3. 结果排名 - 基于多维度评估排名
4. 可视化对比 - 生成对比报告

Author: LivingTreeAI Agent
Date: 2026-04-24
"""

from __future__ import annotations

import json
import time
import asyncio
from typing import Optional, List, Dict, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import threading


class ComparisonMetric(Enum):
    """对比指标"""
    ACCURACY = "accuracy"
    COHERENCE = "coherence"
    CONCISENESS = "conciseness"
    CREATIVITY = "creativity"
    FACTUALITY = "factuality"


@dataclass
class ModelOutput:
    """模型输出"""
    model_id: str
    model_name: str
    content: str
    latency_ms: float
    timestamp: float = 0
    error: Optional[str] = None
    scores: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self):
        if self.timestamp == 0:
            self.timestamp = time.time()


@dataclass
class ComparisonResult:
    """对比结果"""
    query: str
    outputs: List[ModelOutput]
    best_model: str
    rankings: List[Tuple[str, float]]  # model_id, score
    consensus_summary: str
    differences: List[str]  # 差异列表
    metadata: Dict = field(default_factory=dict)


@dataclass
class DifferenceAnalysis:
    """差异分析"""
    type: str  # factual/logical/stylistic/structural
    models_involved: List[str]
    description: str
    severity: str  # minor/moderate/severe


class MultiModelComparison:
    """
    多模型对比系统

    使用方式:
    ```python
    comparator = MultiModelComparison()

    # 添加模型
    comparator.add_model("model_a", "qwen3.5:9b", ollama_client_a)
    comparator.add_model("model_b", "qwen2.5:1.5b", ollama_client_b)

    # 对比
    result = comparator.compare("解释量子纠缠")
    print(f"最佳: {result.best_model}")
    print(f"排名: {result.rankings}")
    ```
    """

    def __init__(self, timeout_seconds: float = 60.0):
        self.timeout_seconds = timeout_seconds
        self._models: Dict[str, Tuple[str, Any]] = {}  # id -> (name, client)
        self._lock = threading.RLock()
        self._stats = {"total_comparisons": 0, "avg_models_used": 0}

    def add_model(self, model_id: str, model_name: str, client: Any):
        """添加模型"""
        with self._lock:
            self._models[model_id] = (model_name, client)
            print(f"[MultiModelComparison] 添加模型: {model_name} ({model_id})")

    def remove_model(self, model_id: str) -> bool:
        """移除模型"""
        with self._lock:
            if model_id in self._models:
                del self._models[model_id]
                return True
            return False

    def get_models(self) -> List[Dict]:
        """获取模型列表"""
        return [{"id": mid, "name": info[0]} for mid, info in self._models.items()]

    def compare(
        self,
        query: str,
        model_ids: Optional[List[str]] = None,
        context: Optional[Dict] = None,
        metrics: Optional[List[ComparisonMetric]] = None,
    ) -> ComparisonResult:
        """对比多个模型"""
        self._stats["total_comparisons"] += 1
        start_time = time.time()

        # 选择模型
        if model_ids is None:
            model_ids = list(self._models.keys())

        # 填充默认值
        if metrics is None:
            metrics = [ComparisonMetric.ACCURACY, ComparisonMetric.COHERENCE]

        # 并行推理
        outputs = self._run_inference(query, model_ids, context)

        # 评估
        for output in outputs:
            if not output.error:
                output.scores = self._evaluate(output, query, metrics)

        # 排名
        rankings = self._rank_models(outputs)

        # 差异分析
        differences = self._analyze_differences(outputs)

        # 共识总结
        consensus = self._generate_consensus(outputs, query)

        # 最佳模型
        best = rankings[0][0] if rankings else ""

        return ComparisonResult(
            query=query,
            outputs=outputs,
            best_model=best,
            rankings=rankings,
            consensus_summary=consensus,
            differences=differences,
            metadata={
                "comparison_time_ms": (time.time() - start_time) * 1000,
                "models_count": len(outputs),
                "success_count": sum(1 for o in outputs if not o.error),
            }
        )

    def _run_inference(
        self,
        query: str,
        model_ids: List[str],
        context: Optional[Dict],
    ) -> List[ModelOutput]:
        """运行推理"""
        outputs = []

        for model_id in model_ids:
            if model_id not in self._models:
                outputs.append(ModelOutput(
                    model_id=model_id,
                    model_name=model_id,
                    content="",
                    latency_ms=0,
                    error="Model not found",
                ))
                continue

            model_name, client = self._models[model_id]
            start = time.time()

            try:
                if hasattr(client, 'chat_sync'):
                    messages = [{"role": "user", "content": query}]
                    content, _, _ = client.chat_sync(messages, model=model_name)
                elif hasattr(client, 'chat'):
                    response = client.chat(messages=[{"role": "user", "content": query}])
                    content = response.choices[0].message.content
                else:
                    raise ValueError(f"Unsupported client type: {type(client)}")

                outputs.append(ModelOutput(
                    model_id=model_id,
                    model_name=model_name,
                    content=content,
                    latency_ms=(time.time() - start) * 1000,
                ))

            except Exception as e:
                outputs.append(ModelOutput(
                    model_id=model_id,
                    model_name=model_name,
                    content="",
                    latency_ms=(time.time() - start) * 1000,
                    error=str(e),
                ))

        return outputs

    def _evaluate(
        self,
        output: ModelOutput,
        query: str,
        metrics: List[ComparisonMetric],
    ) -> Dict[str, float]:
        """评估输出"""
        scores = {}

        for metric in metrics:
            if metric == ComparisonMetric.ACCURACY:
                scores["accuracy"] = self._score_accuracy(output.content, query)
            elif metric == ComparisonMetric.COHERENCE:
                scores["coherence"] = self._score_coherence(output.content)
            elif metric == ComparisonMetric.CONCISENESS:
                scores["conciseness"] = self._score_conciseness(output.content)
            elif metric == ComparisonMetric.CREATIVITY:
                scores["creativity"] = self._score_creativity(output.content)
            elif metric == ComparisonMetric.FACTUALITY:
                scores["factuality"] = self._score_factuality(output.content)

        # 综合得分
        if scores:
            scores["overall"] = sum(scores.values()) / len(scores)

        return scores

    def _score_accuracy(self, content: str, query: str) -> float:
        """评分准确性"""
        if not content:
            return 0
        # 简化：检查是否包含问询的关键信息
        query_keywords = set(query.lower().split())
        content_keywords = set(content.lower().split())
        overlap = len(query_keywords & content_keywords)
        return min(overlap / max(len(query_keywords), 1) * 2, 1.0)

    def _score_coherence(self, content: str) -> float:
        """评分连贯性"""
        if not content:
            return 0
        # 简化：检查句子完整度
        sentences = content.split('。')
        complete = sum(1 for s in sentences if len(s) > 10)
        return min(complete / max(len(sentences), 1), 1.0)

    def _score_conciseness(self, content: str) -> float:
        """评分简洁性"""
        if not content:
            return 0
        # 适中长度得分最高
        ideal_len = 500
        len_ratio = 1 - abs(len(content) - ideal_len) / ideal_len
        return max(0, min(len_ratio, 1.0))

    def _score_creativity(self, content: str) -> float:
        """评分创意性"""
        if not content:
            return 0
        # 简化：检查是否包含创意词汇
        creative_words = ['想象', '创造', '新颖', '独特', '创新', '设想', '或许', '可能']
        count = sum(1 for w in creative_words if w in content)
        return min(count / 3, 1.0)

    def _score_factuality(self, content: str) -> float:
        """评分事实性"""
        if not content:
            return 0
        # 简化：检查是否包含数据引用
        has_numbers = bool([c for c in content if c.isdigit()])
        return 0.7 if has_numbers else 0.5

    def _rank_models(self, outputs: List[ModelOutput]) -> List[Tuple[str, float]]:
        """排名模型"""
        rankings = []

        for output in outputs:
            if output.error:
                rankings.append((output.model_id, 0))
            else:
                score = output.scores.get("overall", 0.5)
                # 考虑延迟惩罚
                latency_penalty = min(output.latency_ms / 10000, 0.2)
                final_score = score * (1 - latency_penalty)
                rankings.append((output.model_id, final_score))

        rankings.sort(key=lambda x: x[1], reverse=True)
        return rankings

    def _analyze_differences(self, outputs: List[ModelOutput]) -> List[str]:
        """分析差异"""
        differences = []
        valid_outputs = [o for o in outputs if not o.error and o.content]

        if len(valid_outputs) < 2:
            return differences

        # 长度差异
        lengths = [len(o.content) for o in valid_outputs]
        if max(lengths) > min(lengths) * 2:
            differences.append(f"输出长度差异显著: {min(lengths)} vs {max(lengths)} 字符")

        # 结构差异
        structures = [self._get_structure(o.content) for o in valid_outputs]
        if len(set(structures)) > 1:
            differences.append("输出结构不同（列表式/段落式/问答式等）")

        # 关键词差异
        all_keywords = set()
        for o in valid_outputs:
            all_keywords.update(self._extract_keywords(o.content))

        for o in valid_outputs:
            o_keywords = self._extract_keywords(o.content)
            unique = o_keywords - all_keywords
            if unique:
                differences.append(f"{o.model_name} 独特观点: {', '.join(list(unique)[:3])}")

        return differences

    def _get_structure(self, content: str) -> str:
        """获取结构类型"""
        if '1.' in content or '①' in content:
            return "numbered"
        if '•' in content or '-' in content[:10]:
            return "bullets"
        if '?' in content:
            return "qa"
        if content.count('\n\n') > 2:
            return "paragraphs"
        return "mixed"

    def _extract_keywords(self, content: str) -> set:
        """提取关键词"""
        # 简单实现
        words = content.lower().split()
        keywords = {w for w in words if len(w) > 3}
        return keywords

    def _generate_consensus(self, outputs: List[ModelOutput], query: str) -> str:
        """生成共识总结"""
        valid = [o for o in outputs if not o.error and o.content]

        if not valid:
            return "所有模型均无有效输出"

        if len(valid) == 1:
            return f"仅{valid[0].model_name}有有效输出"

        # 检查一致性
        lengths = [len(o.content) for o in valid]
        avg_length = sum(lengths) / len(lengths)

        if max(lengths) < avg_length * 1.5 and min(lengths) > avg_length * 0.5:
            return "多个模型输出长度相近，观点可能一致"

        return f"{len(valid)}个模型均成功响应，平均输出{avg_length:.0f}字符"

    def generate_report(self, result: ComparisonResult) -> str:
        """生成对比报告"""
        lines = []
        lines.append("=" * 60)
        lines.append("多模型对比报告")
        lines.append("=" * 60)
        lines.append(f"\n查询: {result.query}")
        lines.append(f"\n模型数量: {result.metadata.get('models_count', len(result.outputs))}")
        lines.append(f"对比耗时: {result.metadata.get('comparison_time_ms', 0):.0f}ms")

        lines.append("\n" + "-" * 40)
        lines.append("排名结果:")
        lines.append("-" * 40)

        for i, (model_id, score) in enumerate(result.rankings, 1):
            output = next((o for o in result.outputs if o.model_id == model_id), None)
            name = output.model_name if output else model_id
            latency = f"{output.latency_ms:.0f}ms" if output else "N/A"
            error = f" [错误: {output.error}]" if output and output.error else ""

            lines.append(f"{i}. {name} (得分: {score:.3f}, 延迟: {latency}){error}")

            if output and output.scores:
                scores_str = ", ".join(f"{k}={v:.2f}" for k, v in output.scores.items() if k != "overall")
                lines.append(f"   指标: {scores_str}")

        if result.differences:
            lines.append("\n" + "-" * 40)
            lines.append("差异分析:")
            lines.append("-" * 40)
            for diff in result.differences:
                lines.append(f"• {diff}")

        if result.consensus_summary:
            lines.append(f"\n共识: {result.consensus_summary}")

        lines.append("\n" + "=" * 60)
        return "\n".join(lines)

    def get_stats(self) -> Dict:
        """获取统计"""
        return {**self._stats, "registered_models": len(self._models)}


# ═══════════════════════════════════════════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("多模型对比系统测试")
    print("=" * 60)

    comparator = MultiModelComparison()

    print("\n[Test: 模型管理]")
    print(f"  已注册模型: {len(comparator.get_models())}")

    # 模拟输出测试
    class MockOutput:
        def __init__(self, content):
            self.choices = [type('obj', (object,), {'message': type('msg', (object,), {'content': content})()})()]

    print("\n[Test: 结果评估]")
    output = ModelOutput("test", "Test Model", "这是一个测试回答。" * 10, 100)
    scores = comparator._evaluate(output, "测试", [ComparisonMetric.ACCURACY, ComparisonMetric.COHERENCE])
    print(f"  评分: {scores}")

    print("\n[Test: 排名]")
    outputs = [
        ModelOutput("m1", "Model A", "回答A" * 20, 100, scores={"overall": 0.8}),
        ModelOutput("m2", "Model B", "回答B" * 30, 200, scores={"overall": 0.9}),
        ModelOutput("m3", "Model C", "回答C" * 15, 50, scores={"overall": 0.7}),
    ]
    rankings = comparator._rank_models(outputs)
    print(f"  排名: {rankings}")

    print("\n" + "=" * 60)
