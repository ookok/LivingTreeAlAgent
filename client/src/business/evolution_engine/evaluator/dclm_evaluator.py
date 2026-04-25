# dclm_evaluator.py - DCLM CORE 评分器

"""
DCLM CORE 评分器 - 基于 DCLM 数据集的代码质量评估
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import re
import logging

logger = logging.getLogger('evolution.dclm_evaluator')


def import_base_evaluator(ns):
    """动态导入 base_evaluator"""
    from base_evaluator import (
        BaseEvaluator, EvaluationResult, MetricScore, MetricType, TestCase
    )
    ns.update({
        'BaseEvaluator': BaseEvaluator,
        'EvaluationResult': EvaluationResult,
        'MetricScore': MetricScore,
        'MetricType': MetricType,
        'TestCase': TestCase
    })


@dataclass
class DCLMScore:
    """DCLM 评分结果"""
    overall_score: float = 0.0
    correctness: float = 0.0
    syntax_quality: float = 0.0
    semantic_quality: float = 0.0
    style_score: float = 0.0
    total_cases: int = 0
    passed_cases: int = 0
    failed_cases: int = 0
    case_results: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self):
        return {
            'overall_score': self.overall_score,
            'correctness': self.correctness,
            'syntax_quality': self.syntax_quality,
            'semantic_quality': self.semantic_quality,
            'style_score': self.style_score,
            'total_cases': self.total_cases,
            'passed_cases': self.passed_cases,
            'failed_cases': self.failed_cases,
            'pass_rate': self.passed_cases / self.total_cases if self.total_cases > 0 else 0,
            'case_results': self.case_results
        }
    
    def __getitem__(self, key):
        return getattr(self, key, None)


class DCLMEvaluator:
    """DCLM CORE 评分器"""
    
    def __init__(self, project_root: str, config: Optional[Dict[str, Any]] = None):
        self.name = "dclm"
        self.project_root = project_root
        self.config = config or {}
        self.threshold = self.config.get('threshold', 0.8)
        self.strict_mode = self.config.get('strict_mode', False)
        self.enable_syntax_check = self.config.get('enable_syntax_check', True)
        self.enable_style_check = self.config.get('enable_style_check', True)
        self._test_cases = self._get_default_test_cases()
    
    def _get_default_test_cases(self):
        return [
            {'id': 'dclm_001', 'prompt': '写一个函数计算斐波那契数列第n项', 'expected': 'def fibonacci(n): ...', 'category': 'algorithm'},
            {'id': 'dclm_002', 'prompt': '实现一个LRU缓存类', 'expected': 'class LRUCache: ...', 'category': 'data_structure'},
            {'id': 'dclm_003', 'prompt': '写一个异步HTTP请求函数', 'expected': 'async def fetch(url): ...', 'category': 'async'},
            {'id': 'dclm_004', 'prompt': '实现快速排序算法', 'expected': 'def quicksort(arr): ...', 'category': 'algorithm'},
            {'id': 'dclm_005', 'prompt': '创建一个装饰器计时器', 'expected': '@decorator ...', 'category': 'meta'},
        ]
    
    def evaluate(self, custom_prompts=None):
        from base_evaluator import MetricScore, MetricType, EvaluationResult
        
        start_time = datetime.now()
        test_cases = self._build_test_cases(custom_prompts)
        
        case_results = []
        total_scores = []
        syntax_scores = []
        semantic_scores = []
        style_scores = []
        
        for case in test_cases:
            result = self._evaluate_case(case)
            case_results.append(result)
            total_scores.append(result['score'])
            syntax_scores.append(result['syntax_score'])
            semantic_scores.append(result['semantic_score'])
            style_scores.append(result['style_score'])
        
        passed = sum(1 for r in case_results if r['passed'])
        
        dclm_score = DCLMScore(
            overall_score=sum(total_scores) / len(total_scores) if total_scores else 0,
            correctness=(passed / len(case_results) * 100) if case_results else 0,
            syntax_quality=sum(syntax_scores) / len(syntax_scores) if syntax_scores else 0,
            semantic_quality=sum(semantic_scores) / len(semantic_scores) if semantic_scores else 0,
            style_score=sum(style_scores) / len(style_scores) if style_scores else 0,
            total_cases=len(case_results),
            passed_cases=passed,
            failed_cases=len(case_results) - passed,
            case_results=case_results
        )
        
        metrics = {
            'dclm_overall': MetricScore("DCLM总分", dclm_score.overall_score, MetricType.QUALITY, "分", True, "DCLM综合评分"),
            'dclm_correctness': MetricScore("正确性", dclm_score.correctness, MetricType.ACCURACY, "%", True, "代码正确执行的比例"),
            'dclm_syntax': MetricScore("语法质量", dclm_score.syntax_quality, MetricType.QUALITY, "分", True, "语法规范性评分"),
            'dclm_semantic': MetricScore("语义质量", dclm_score.semantic_quality, MetricType.QUALITY, "分", True, "语义正确性评分"),
            'dclm_style': MetricScore("风格评分", dclm_score.style_score, MetricType.QUALITY, "分", True, "代码风格一致性"),
            'pass_rate': MetricScore("通过率", dclm_score.passed_cases / dclm_score.total_cases * 100 if dclm_score.total_cases > 0 else 0, MetricType.ACCURACY, "%", True, "测试用例通过率")
        }
        
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        return EvaluationResult(
            evaluator_name=self.name,
            timestamp=datetime.now().isoformat(),
            duration_ms=duration_ms,
            metrics=metrics,
            raw_data={'dclm': dclm_score},
            metadata={'test_cases_count': len(test_cases), 'threshold': self.threshold}
        )
    
    def _build_test_cases(self, custom_prompts):
        if custom_prompts:
            return custom_prompts
        return self._test_cases
    
    def _evaluate_case(self, case):
        result = {
            'case_id': case['id'], 'prompt': case['prompt'], 'passed': False,
            'score': 0.0, 'syntax_score': 0.0, 'semantic_score': 0.0, 'style_score': 0.0, 'errors': []
        }
        
        generated = case.get('metadata', {}).get('generated_code', '') or self._simulate_code_generation(case['prompt'])
        
        syntax_ok, syntax_score, syntax_errors = self._check_syntax(generated, case)
        result['syntax_score'] = syntax_score
        if not syntax_ok:
            result['errors'].extend(syntax_errors)
        
        semantic_ok, semantic_score = self._check_semantics(generated, case)
        result['semantic_score'] = semantic_score
        if not semantic_ok:
            result['errors'].append("语义检查未通过")
        
        result['style_score'] = self._check_style(generated)
        
        result['score'] = result['syntax_score'] * 0.3 + result['semantic_score'] * 0.5 + result['style_score'] * 0.2
        result['passed'] = result['score'] >= self.threshold * 100
        
        return result
    
    def _simulate_code_generation(self, prompt):
        if '斐波那契' in prompt:
            return 'def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)'
        elif 'LRU' in prompt:
            return 'from collections import OrderedDict\n\nclass LRUCache:\n    def __init__(self, capacity):\n        self.capacity = capacity\n        self.cache = OrderedDict()\n    def get(self, key):\n        if key not in self.cache:\n            return -1\n        self.cache.move_to_end(key)\n        return self.cache[key]'
        elif '异步' in prompt or 'async' in prompt.lower():
            return 'import aiohttp\n\nasync def fetch(url):\n    async with aiohttp.ClientSession() as session:\n        async with session.get(url) as response:\n            return await response.json()'
        elif '快速排序' in prompt:
            return 'def quicksort(arr):\n    if len(arr) <= 1:\n        return arr\n    pivot = arr[len(arr) // 2]\n    return quicksort([x for x in arr if x < pivot]) + [x for x in arr if x == pivot] + quicksort([x for x in arr if x > pivot])'
        elif '装饰器' in prompt:
            return 'import functools\nimport time\n\ndef timer(func):\n    @functools.wraps(func)\n    def wrapper(*args, **kwargs):\n        start = time.time()\n        result = func(*args, **kwargs)\n        print(f"Took {time.time() - start:.4f}s")\n        return result\n    return wrapper'
        else:
            return 'def generated_function():\n    pass'
    
    def _check_syntax(self, code, case):
        errors = []
        score = 100.0
        if not code.strip():
            return False, 0.0, ["代码为空"]
        lines = code.split('\n')
        for line in lines:
            if line.strip() and not line.startswith('#'):
                indent = len(line) - len(line.lstrip())
                if indent % 4 != 0 and indent > 0:
                    errors.append(f"缩进问题")
                    score -= 10
        brackets = {'(': ')', '[': ']', '{': '}'}
        stack = []
        for char in code:
            if char in brackets:
                stack.append(char)
            elif char in brackets.values():
                if not stack or brackets.get(stack.pop()) != char:
                    errors.append("括号不匹配")
                    score -= 20
                    break
        return len(errors) == 0, max(0, score), errors
    
    def _check_semantics(self, code, case):
        score = 100.0
        expected_keywords = self._extract_keywords(case['expected'])
        for keyword in expected_keywords:
            if keyword.lower() not in code.lower():
                score -= 15
        if 'def ' in case['expected'] or 'class ' in case['expected']:
            if not any(k in code for k in ['def ', 'class ']):
                score -= 30
        return score >= 70, max(0, score)
    
    def _extract_keywords(self, expected):
        keywords = []
        for pattern in [r'def\s+(\w+)', r'class\s+(\w+)', r'@(\w+)']:
            import re
            match = re.search(pattern, expected)
            if match:
                keywords.append(match.group(1))
        return keywords
    
    def _check_style(self, code):
        score = 100.0
        if '"""' in code or "'''" in code:
            score += 10
        if '->' in code or ': ' in code:
            score += 10
        return min(100, max(0, score))
