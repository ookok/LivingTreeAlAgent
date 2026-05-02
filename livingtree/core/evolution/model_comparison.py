"""
多模型对比系统 (Multi-Model Comparison)
=====================================

多个模型同时推理并对比结果，支持并行执行和差异分析。
"""

import time
import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import threading

logger = logging.getLogger(__name__)


class ComparisonMetric(Enum):
    ACCURACY = "accuracy"
    COHERENCE = "coherence"
    CONCISENESS = "conciseness"
    CREATIVITY = "creativity"
    FACTUALITY = "factuality"


@dataclass
class ModelOutput:
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
    query: str
    outputs: List[ModelOutput]
    best_model: str
    rankings: List[Tuple[str, float]]
    consensus_summary: str
    differences: List[str]
    metadata: Dict = field(default_factory=dict)


class MultiModelComparison:
    def __init__(self, timeout_seconds: float = 60.0):
        self.timeout_seconds = timeout_seconds
        self._models: Dict[str, Tuple[str, Any]] = {}
        self._lock = threading.RLock()
        self._stats = {"total_comparisons": 0, "avg_models_used": 0}

    def add_model(self, model_id: str, model_name: str, client: Any):
        with self._lock:
            self._models[model_id] = (model_name, client)
            logger.info(f"[MultiModelComparison] 添加模型: {model_name} ({model_id})")

    def remove_model(self, model_id: str) -> bool:
        with self._lock:
            if model_id in self._models:
                del self._models[model_id]
                return True
            return False

    def get_models(self) -> List[Dict]:
        return [{"id": mid, "name": info[0]} for mid, info in self._models.items()]

    def compare(
        self, query: str, model_ids: Optional[List[str]] = None,
        context: Optional[Dict] = None,
        metrics: Optional[List[ComparisonMetric]] = None,
    ) -> ComparisonResult:
        self._stats["total_comparisons"] += 1
        start_time = time.time()

        if model_ids is None:
            model_ids = list(self._models.keys())
        if metrics is None:
            metrics = [ComparisonMetric.ACCURACY, ComparisonMetric.COHERENCE]

        outputs = self._run_inference(query, model_ids, context)

        for output in outputs:
            if not output.error:
                output.scores = self._evaluate(output, query, metrics)

        rankings = self._rank_models(outputs)
        differences = self._analyze_differences(outputs)
        consensus = self._generate_consensus(outputs, query)
        best = rankings[0][0] if rankings else ""

        return ComparisonResult(
            query=query, outputs=outputs, best_model=best,
            rankings=rankings, consensus_summary=consensus,
            differences=differences,
            metadata={
                "comparison_time_ms": (time.time() - start_time) * 1000,
                "models_count": len(outputs),
                "success_count": sum(1 for o in outputs if not o.error),
            })

    def _run_inference(self, query: str, model_ids: List[str],
                       context: Optional[Dict]) -> List[ModelOutput]:
        outputs = []
        for model_id in model_ids:
            if model_id not in self._models:
                outputs.append(ModelOutput(model_id=model_id, model_name=model_id,
                                           content="", latency_ms=0,
                                           error="Model not found"))
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
                    model_id=model_id, model_name=model_name,
                    content=content,
                    latency_ms=(time.time() - start) * 1000))

            except Exception as e:
                outputs.append(ModelOutput(
                    model_id=model_id, model_name=model_name,
                    content="", latency_ms=(time.time() - start) * 1000,
                    error=str(e)))

        return outputs

    def _evaluate(self, output: ModelOutput, query: str,
                  metrics: List[ComparisonMetric]) -> Dict[str, float]:
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

        if scores:
            scores["overall"] = sum(scores.values()) / len(scores)
        return scores

    def _score_accuracy(self, content: str, query: str) -> float:
        if not content:
            return 0
        query_keywords = set(query.lower().split())
        content_keywords = set(content.lower().split())
        overlap = len(query_keywords & content_keywords)
        return min(overlap / max(len(query_keywords), 1) * 2, 1.0)

    def _score_coherence(self, content: str) -> float:
        if not content:
            return 0
        sentences = content.split('。')
        complete = sum(1 for s in sentences if len(s) > 10)
        return min(complete / max(len(sentences), 1), 1.0)

    def _score_conciseness(self, content: str) -> float:
        if not content:
            return 0
        ideal_len = 500
        len_ratio = 1 - abs(len(content) - ideal_len) / ideal_len
        return max(0, min(len_ratio, 1.0))

    def _score_creativity(self, content: str) -> float:
        if not content:
            return 0
        creative_words = ['想象', '创造', '新颖', '独特', '创新', '设想', '或许', '可能']
        count = sum(1 for w in creative_words if w in content)
        return min(count / 3, 1.0)

    def _score_factuality(self, content: str) -> float:
        if not content:
            return 0
        has_numbers = bool([c for c in content if c.isdigit()])
        return 0.7 if has_numbers else 0.5

    def _rank_models(self, outputs: List[ModelOutput]) -> List[Tuple[str, float]]:
        rankings = []
        for output in outputs:
            if output.error:
                rankings.append((output.model_id, 0))
            else:
                score = output.scores.get("overall", 0.5)
                latency_penalty = min(output.latency_ms / 10000, 0.2)
                final_score = score * (1 - latency_penalty)
                rankings.append((output.model_id, final_score))
        rankings.sort(key=lambda x: x[1], reverse=True)
        return rankings

    def _analyze_differences(self, outputs: List[ModelOutput]) -> List[str]:
        differences = []
        valid_outputs = [o for o in outputs if not o.error and o.content]
        if len(valid_outputs) < 2:
            return differences

        lengths = [len(o.content) for o in valid_outputs]
        if max(lengths) > min(lengths) * 2:
            differences.append(f"输出长度差异显著: {min(lengths)} vs {max(lengths)} 字符")

        structures = [self._get_structure(o.content) for o in valid_outputs]
        if len(set(structures)) > 1:
            differences.append("输出结构不同（列表式/段落式/问答式等）")

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
        words = content.lower().split()
        return {w for w in words if len(w) > 3}

    def _generate_consensus(self, outputs: List[ModelOutput], query: str) -> str:
        valid = [o for o in outputs if not o.error and o.content]
        if not valid:
            return "所有模型均无有效输出"
        if len(valid) == 1:
            return f"仅{valid[0].model_name}有有效输出"

        lengths = [len(o.content) for o in valid]
        avg_length = sum(lengths) / len(lengths)
        if max(lengths) < avg_length * 1.5 and min(lengths) > avg_length * 0.5:
            return "多个模型输出长度相近，观点可能一致"
        return f"{len(valid)}个模型均成功响应，平均输出{avg_length:.0f}字符"

    def generate_report(self, result: ComparisonResult) -> str:
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
                scores_str = ", ".join(
                    f"{k}={v:.2f}" for k, v in output.scores.items() if k != "overall")
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
        return {**self._stats, "registered_models": len(self._models)}


__all__ = [
    "MultiModelComparison",
    "ComparisonMetric",
    "ModelOutput",
    "ComparisonResult",
]
