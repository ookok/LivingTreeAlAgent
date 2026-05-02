# evolution_evaluator.py - Evolution Evaluator 主控制器

"""
Evolution Evaluator - 量化评估框架

评估维度：
- DCLM CORE: 代码生成质量评估
- BPB: 语言建模压缩效率
- Benchmark: 标准任务性能 (ARC/GSM8K/MMLU/HumanEval)
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum
import json
import logging
import threading
import statistics

logger = logging.getLogger('evolution.evaluator')


class EvaluationMode(Enum):
    FULL = "full"
    QUICK = "quick"
    TARGETED = "targeted"
    CONTINUOUS = "continuous"


class CapabilityDimension(Enum):
    CODE_GENERATION = "code_generation"
    REASONING = "reasoning"
    KNOWLEDGE = "knowledge"
    COMPRESSION = "compression"
    ACCURACY = "accuracy"
    SAFETY = "safety"


@dataclass
class CapabilityScore:
    dimension: CapabilityDimension
    score: float
    trend: str = "stable"
    change_percent: float = 0.0
    benchmarks: Dict[str, float] = field(default_factory=dict)
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
    
    def to_dict(self):
        return {
            'dimension': self.dimension.value,
            'score': self.score,
            'trend': self.trend,
            'change_percent': self.change_percent,
            'benchmarks': self.benchmarks,
            'timestamp': self.timestamp
        }


@dataclass
class EvolutionMetrics:
    total_evaluations: int = 0
    successful_evaluations: int = 0
    failed_evaluations: int = 0
    average_score: float = 0.0
    improvement_rate: float = 0.0
    trend_history: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self):
        return asdict(self)


class EvolutionEvaluator:
    """Evolution Evaluator - 量化评估主控制器"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, project_root: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._initialized = True
        self.config = config or {}
        self.project_root = Path(project_root) if project_root else Path.cwd()
        
        self._evaluators = {}
        self._evaluation_history = []
        self._capability_scores = {}
        self._metrics = EvolutionMetrics()
        
        self._init_evaluators()
        self._load_history()
        
        logger.info("[EvolutionEvaluator] Initialized")
    
    def _init_evaluators(self):
        """初始化所有评估器"""
        from dclm_evaluator import DCLMEvaluator
        from bpb_evaluator import BPBEvaluator
        from benchmark_evaluator import BenchmarkEvaluator
        
        if self.config.get('dclm', {}).get('enabled', True):
            self._evaluators['dclm'] = DCLMEvaluator(str(self.project_root), self.config.get('dclm', {}))
        
        if self.config.get('bpb', {}).get('enabled', True):
            self._evaluators['bpb'] = BPBEvaluator(str(self.project_root), self.config.get('bpb', {}))
        
        if self.config.get('benchmark', {}).get('enabled', True):
            self._evaluators['benchmark'] = BenchmarkEvaluator(str(self.project_root), self.config.get('benchmark', {}))
        
        logger.info(f"[EvolutionEvaluator] Initialized {len(self._evaluators)} evaluators")
    
    def _load_history(self):
        history_file = self.project_root / '.evolution_db' / 'evaluation_history.json'
        if history_file.exists():
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._evaluation_history = [self._result_from_dict(item) for item in data.get('history', [])]
                    self._metrics = EvolutionMetrics(**data.get('metrics', {}))
            except Exception as e:
                logger.warning(f"[EvolutionEvaluator] Failed to load history: {e}")
    
    def _result_from_dict(self, d):
        from base_evaluator import EvaluationResult, MetricScore, MetricType
        metrics = {k: MetricScore(**v) for k, v in d.get('metrics', {}).items()}
        return EvaluationResult(evaluator_name=d.get('evaluator_name', ''), metrics=metrics, raw_data=d.get('raw_data', {}), errors=d.get('errors'))
    
    def _save_history(self):
        history_file = self.project_root / '.evolution_db' / 'evaluation_history.json'
        history_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = {
                'history': [
                    {
                        'evaluator_name': r.evaluator_name,
                        'metrics': {k: v.to_dict() for k, v in r.metrics.items()},
                        'raw_data': r.raw_data,
                        'errors': r.errors,
                        'timestamp': r.timestamp,
                        'duration_ms': r.duration_ms
                    }
                    for r in self._evaluation_history[-100:]
                ],
                'metrics': asdict(self._metrics)
            }
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[EvolutionEvaluator] Failed to save history: {e}")
    
    def evaluate(self, mode: EvaluationMode = EvaluationMode.QUICK, target: Optional[List[str]] = None, custom_prompts: Optional[List[Dict[str, Any]]] = None):
        from base_evaluator import EvaluationResult, MetricScore
        
        evaluators_to_run = []
        if target:
            evaluators_to_run = [self._evaluators.get(t) for t in target if t in self._evaluators]
        elif mode == EvaluationMode.FULL:
            evaluators_to_run = list(self._evaluators.values())
        elif mode == EvaluationMode.QUICK:
            evaluators_to_run = [self._evaluators.get('dclm'), self._evaluators.get('benchmark')]
        else:
            evaluators_to_run = list(self._evaluators.values())
        
        evaluators_to_run = [e for e in evaluators_to_run if e is not None]
        
        if not evaluators_to_run:
            return EvaluationResult(evaluator_name="evolution_evaluator", metrics={}, raw_data={}, errors=["No evaluators available"])
        
        all_metrics = {}
        all_raw_data = {}
        errors = []
        
        for evaluator in evaluators_to_run:
            try:
                result = evaluator.evaluate(custom_prompts=custom_prompts)
                all_metrics.update(result.metrics)
                all_raw_data[result.evaluator_name] = result.raw_data
            except Exception as e:
                logger.error(f"[EvolutionEvaluator] {evaluator.name} evaluation failed: {e}")
                errors.append(f"{evaluator.name}: {str(e)}")
        
        result = EvaluationResult(
            evaluator_name="evolution_evaluator",
            timestamp=datetime.now().isoformat(),
            metrics=all_metrics,
            raw_data=all_raw_data,
            errors=errors if errors else None
        )
        
        self._evaluation_history.append(result)
        self._update_metrics()
        self._save_history()
        self._update_capability_scores(result)
        
        logger.info(f"[EvolutionEvaluator] Evaluation complete: {len(all_metrics)} metrics")
        return result
    
    def _update_metrics(self):
        from base_evaluator import MetricScore
        if not self._evaluation_history:
            return
        self._metrics.total_evaluations = len(self._evaluation_history)
        self._metrics.successful_evaluations = sum(1 for r in self._evaluation_history if not r.errors)
        self._metrics.failed_evaluations = sum(1 for r in self._evaluation_history if r.errors)
        recent = self._evaluation_history[-10:]
        all_scores = [m.value for r in recent for m in r.metrics.values() if isinstance(m, MetricScore)]
        if all_scores:
            self._metrics.average_score = statistics.mean(all_scores)
    
    def _get_overall_score(self, result):
        from base_evaluator import MetricScore
        scores = [m.value for m in result.metrics.values() if isinstance(m, MetricScore)]
        return statistics.mean(scores) if scores else 0.0
    
    def _update_capability_scores(self, result):
        from dclm_evaluator import DCLMScore
        from bpb_evaluator import BPBScore
        from benchmark_evaluator import BenchmarkScore
        
        if 'dclm' in result.raw_data:
            dclm_data = result.raw_data['dclm']
            if isinstance(dclm_data, DCLMScore):
                self._update_dimension_score(CapabilityDimension.CODE_GENERATION, dclm_data.overall_score, {'dclm': dclm_data.overall_score})
        
        if 'bpb' in result.raw_data:
            bpb_data = result.raw_data['bpb']
            if isinstance(bpb_data, BPBScore):
                normalized_score = max(0, 100 - bpb_data.bpb * 10)
                self._update_dimension_score(CapabilityDimension.COMPRESSION, normalized_score, {'bpb': bpb_data.bpb})
        
        if 'benchmark' in result.raw_data:
            bench_data = result.raw_data['benchmark']
            if isinstance(bench_data, BenchmarkScore):
                self._update_dimension_score(CapabilityDimension.REASONING, bench_data.get('gsm8k', 0) or bench_data.overall, {'gsm8k': bench_data.get('gsm8k', 0)})
                self._update_dimension_score(CapabilityDimension.KNOWLEDGE, bench_data.get('mmlu', 0) or bench_data.overall, {'mmlu': bench_data.get('mmlu', 0)})
                self._update_dimension_score(CapabilityDimension.ACCURACY, bench_data.get('arc', 0) or bench_data.overall, {'arc': bench_data.get('arc', 0)})
    
    def _update_dimension_score(self, dimension, new_score, benchmarks):
        prev_score = self._capability_scores.get(dimension)
        prev_value = prev_score.score if prev_score else 0.0
        
        if prev_value == 0:
            trend = "stable"
            change_percent = 0.0
        elif new_score > prev_value * 1.05:
            trend = "up"
            change_percent = ((new_score - prev_value) / prev_value) * 100
        elif new_score < prev_value * 0.95:
            trend = "down"
            change_percent = ((new_score - prev_value) / prev_value) * 100
        else:
            trend = "stable"
            change_percent = 0.0
        
        self._capability_scores[dimension] = CapabilityScore(
            dimension=dimension, score=new_score, trend=trend, change_percent=change_percent, benchmarks=benchmarks
        )
    
    def get_capability_report(self):
        return {
            'timestamp': datetime.now().isoformat(),
            'dimensions': {dim.value: score.to_dict() for dim, score in self._capability_scores.items()},
            'overall_score': self._get_overall_capability_score(),
            'capability_level': self._get_capability_level(),
            'trend_summary': self._get_trend_summary()
        }
    
    def _get_overall_capability_score(self):
        if not self._capability_scores:
            return 0.0
        return statistics.mean([s.score for s in self._capability_scores.values()])
    
    def _get_capability_level(self):
        score = self._get_overall_capability_score()
        if score >= 80: return "Excellent"
        elif score >= 60: return "Good"
        elif score >= 40: return "Average"
        elif score >= 20: return "Poor"
        else: return "Very Poor"
    
    def _get_trend_summary(self):
        trends = {dim.value: {'trend': s.trend, 'change_percent': s.change_percent} for dim, s in self._capability_scores.items()}
        improving = sum(1 for s in self._capability_scores.values() if s.trend == "up")
        declining = sum(1 for s in self._capability_scores.values() if s.trend == "down")
        return {
            'by_dimension': trends,
            'improving_count': improving,
            'declining_count': declining,
            'stable_count': len(self._capability_scores) - improving - declining
        }
    
    def get_metrics(self):
        return self._metrics
    
    def get_stats(self):
        return {
            'enabled_evaluators': list(self._evaluators.keys()),
            'total_evaluations': self._metrics.total_evaluations,
            'success_rate': (self._metrics.successful_evaluations / self._metrics.total_evaluations * 100 if self._metrics.total_evaluations > 0 else 0),
            'average_score': self._metrics.average_score,
            'improvement_rate': self._metrics.improvement_rate,
            'capability_scores_count': len(self._capability_scores)
        }
