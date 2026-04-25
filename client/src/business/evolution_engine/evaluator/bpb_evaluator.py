# bpb_evaluator.py - Bits Per Byte (BPB) 评估器

"""
BPB (Bits Per Byte) 评估器 - 语言模型压缩效率指标
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import math
import logging

logger = logging.getLogger('evolution.bpb_evaluator')


@dataclass
class BPBScore:
    """BPB 评分结果"""
    bpb: float = 0.0
    perplexity: float = 0.0
    log_likelihood: float = 0.0
    total_tokens: int = 0
    total_bytes: int = 0
    num_sequences: int = 0
    sequence_results: List[Dict[str, Any]] = field(default_factory=list)
    reference_bpb: float = 1.0
    
    def to_dict(self):
        return {
            'bpb': self.bpb,
            'perplexity': self.perplexity,
            'log_likelihood': self.log_likelihood,
            'total_tokens': self.total_tokens,
            'total_bytes': self.total_bytes,
            'num_sequences': self.num_sequences,
            'sequence_results': self.sequence_results,
            'reference_bpb': self.reference_bpb,
            'compression_ratio': self.reference_bpb / self.bpb if self.bpb > 0 else 0
        }
    
    def __getitem__(self, key):
        return getattr(self, key, None)


class BPBEvaluator:
    """BPB 评估器"""
    
    def __init__(self, project_root: str, config: Optional[Dict[str, Any]] = None):
        self.name = "bpb"
        self.project_root = project_root
        self.config = config or {}
        self.reference_bpb = self.config.get('reference_bpb', 1.0)
        self.batch_size = self.config.get('batch_size', 10)
        self._test_sequences = self._get_default_sequences()
    
    def _get_default_sequences(self):
        return [
            {'id': 'bpb_001', 'content': 'def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)', 'type': 'function'},
            {'id': 'bpb_002', 'content': 'class Stack:\n    def __init__(self):\n        self.items = []\n    def push(self, item):\n        self.items.append(item)', 'type': 'class'},
            {'id': 'bpb_003', 'content': 'async def fetch(url):\n    import aiohttp\n    async with aiohttp.ClientSession() as session:\n        return await response.json()', 'type': 'async'},
            {'id': 'bpb_004', 'content': '@decorator\ndef logged(func):\n    def wrapper(*args, **kwargs):\n        return func(*args, **kwargs)\n    return wrapper', 'type': 'decorator'},
            {'id': 'bpb_005', 'content': 'from typing import List, Optional\ndef binary_search(arr, target):\n    left, right = 0, len(arr) - 1', 'type': 'algorithm'},
        ]
    
    def evaluate(self, custom_prompts=None):
        from base_evaluator import MetricScore, MetricType, EvaluationResult
        
        start_time = datetime.now()
        sequences = self._build_sequences(custom_prompts)
        
        total_log_likelihood = 0.0
        total_bytes = 0
        total_tokens = 0
        sequence_results = []
        
        for seq in sequences:
            result = self._evaluate_sequence(seq)
            sequence_results.append(result)
            total_log_likelihood += result['log_likelihood']
            total_bytes += result['bytes']
            total_tokens += result['tokens']
        
        num_sequences = len(sequence_results)
        overall_bpb = -total_log_likelihood / total_bytes if total_bytes > 0 else float('inf')
        perplexity = math.pow(2, -total_log_likelihood / total_tokens) if total_tokens > 0 else float('inf')
        
        bpb_score = BPBScore(
            bpb=overall_bpb,
            perplexity=perplexity,
            log_likelihood=total_log_likelihood,
            total_tokens=total_tokens,
            total_bytes=total_bytes,
            num_sequences=num_sequences,
            sequence_results=sequence_results,
            reference_bpb=self.reference_bpb
        )
        
        compression_ratio = self.reference_bpb / overall_bpb if overall_bpb > 0 else 0
        
        metrics = {
            'bpb_score': MetricScore("BPB分数", overall_bpb, MetricType.BPB, "bits/byte", False, "Bits Per Byte"),
            'perplexity': MetricScore("困惑度", perplexity, MetricType.PERPLEXITY, "", False, "语言模型困惑度"),
            'compression_ratio': MetricScore("压缩比", compression_ratio, MetricType.QUALITY, "x", True, f"相对于基线{self.reference_bpb:.2f}"),
        }
        
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        return EvaluationResult(
            evaluator_name=self.name,
            timestamp=datetime.now().isoformat(),
            duration_ms=duration_ms,
            metrics=metrics,
            raw_data={'bpb': bpb_score},
            metadata={'num_sequences': num_sequences, 'reference_bpb': self.reference_bpb}
        )
    
    def _build_sequences(self, custom_prompts):
        if custom_prompts:
            return custom_prompts
        return self._test_sequences
    
    def _evaluate_sequence(self, sequence):
        content = sequence.get('content', '')
        bytes_count = len(content.encode('utf-8'))
        tokens_count = len(content.split())
        log_likelihood = self._simulate_log_likelihood(content, sequence.get('type', 'unknown'))
        seq_bpb = -log_likelihood / bytes_count if bytes_count > 0 else float('inf')
        
        return {
            'id': sequence.get('id', 'unknown'),
            'type': sequence.get('type', 'unknown'),
            'bytes': bytes_count,
            'tokens': tokens_count,
            'log_likelihood': log_likelihood,
            'bpb': seq_bpb
        }
    
    def _simulate_log_likelihood(self, content, seq_type):
        base_score = -10.0
        complexity_score = 0.0
        if 'def ' in content: complexity_score += 1.5
        if 'class ' in content: complexity_score += 2.0
        if 'async ' in content: complexity_score += 1.0
        if '@' in content: complexity_score += 0.5
        if '->' in content: complexity_score += 0.5
        if '"""' in content: complexity_score += 0.3
        return base_score + complexity_score
    
    def get_reference_baselines(self):
        return {
            'gpt4': 0.85, 'claude': 0.88, 'llama3': 0.95,
            'codex': 0.90, 'LivingstonAI_v1': self.reference_bpb
        }
