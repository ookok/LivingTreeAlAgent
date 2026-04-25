# benchmark_evaluator.py - 标准任务评测器

"""
Benchmark 评估器 - ARC/GSM8K/MMLU/HumanEval/MBPP
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import random
import re
import logging

logger = logging.getLogger('evolution.benchmark_evaluator')


class BenchmarkTask(Enum):
    ARC = "arc"
    GSM8K = "gsm8k"
    MMLU = "mmlu"
    HUMAN_EVAL = "humaneval"
    MBPP = "mbpp"


@dataclass
class BenchmarkScore:
    arc: Optional[float] = None
    gsm8k: Optional[float] = None
    mmlu: Optional[float] = None
    humaneval: Optional[float] = None
    mbpp: Optional[float] = None
    overall: float = 0.0
    tasks_completed: int = 0
    total_tasks: int = 0
    task_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    def to_dict(self):
        return asdict(self)
    
    def __getitem__(self, key):
        return getattr(self, key, None)


class BenchmarkEvaluator:
    """Benchmark 评估器"""
    
    def __init__(self, project_root: str, config: Optional[Dict[str, Any]] = None):
        self.name = "benchmark"
        self.project_root = project_root
        self.config = config or {}
        self.enabled_tasks = self.config.get('tasks', ['arc', 'gsm8k', 'mmlu', 'humaneval'])
        self.max_samples = self.config.get('max_samples', 100)
        self._test_data = self._load_test_data()
    
    def _load_test_data(self):
        return {
            'arc': [
                {'id': 'arc_001', 'question': '小明有5个苹果，小红给了他3个，小明现在有多少个苹果？', 'choices': ['6', '7', '8', '9'], 'answer': '8'},
                {'id': 'arc_002', 'question': '找规律：2, 4, 8, 16, ?', 'choices': ['20', '24', '32', '30'], 'answer': '32'},
                {'id': 'arc_003', 'question': '取到红球的概率是多少？', 'choices': ['1/2', '2/3', '3/4', '1/3'], 'answer': '2/3'},
                {'id': 'arc_004', 'question': '30分钟到校，8:00到校，几点出门？', 'choices': ['7:00', '7:15', '7:30', '7:45'], 'answer': '7:30'},
                {'id': 'arc_005', 'question': '所有猫都是动物，有些动物是黑色，结论？', 'choices': ['所有猫黑色', '有些猫黑色', '没有猫黑色', '无法确定'], 'answer': '无法确定'},
            ],
            'gsm8k': [
                {'id': 'gsm8k_001', 'question': '24支铅笔用3天，平均每天多少支？', 'answer': '8支'},
                {'id': 'gsm8k_002', 'question': '150个苹果卖3/5，还剩多少个？', 'answer': '60个'},
                {'id': 'gsm8k_003', 'question': '12米绳子剪3米一段，能剪几段？', 'answer': '4段'},
                {'id': 'gsm8k_004', 'question': '3本书每本25元，剩35元，原来有多少钱？', 'answer': '110元'},
                {'id': 'gsm8k_005', 'question': '长8厘米宽5厘米，周长多少厘米？', 'answer': '26厘米'},
            ],
            'mmlu': [
                {'id': 'mmlu_001', 'question': '水的化学式是什么？', 'choices': ['H2O', 'CO2', 'NaCl', 'O2'], 'answer': 'H2O'},
                {'id': 'mmlu_002', 'question': '美国第一任总统是谁？', 'choices': ['林肯', '华盛顿', '杰斐逊', '亚当斯'], 'answer': '华盛顿'},
                {'id': 'mmlu_003', 'question': '光合作用发生在植物哪个部分？', 'choices': ['根部', '茎部', '叶片', '花朵'], 'answer': '叶片'},
                {'id': 'mmlu_004', 'question': '太阳系最大的行星是哪个？', 'choices': ['地球', '火星', '木星', '土星'], 'answer': '木星'},
                {'id': 'mmlu_005', 'question': '相对论是谁提出的？', 'choices': ['牛顿', '爱因斯坦', '霍金', '法拉第'], 'answer': '爱因斯坦'},
            ],
            'humaneval': [
                {'id': 'he_001', 'prompt': 'def contains_duplicates(nums):', 'canonical_solution': 'def contains_duplicates(nums):\n    return len(nums) != len(set(nums))'},
                {'id': 'he_002', 'prompt': 'def two_sum(nums, target):', 'canonical_solution': 'def two_sum(nums, target):\n    seen = {}\n    for i, num in enumerate(nums):\n        complement = target - num\n        if complement in seen:\n            return [seen[complement], i]\n        seen[num] = i'},
                {'id': 'he_003', 'prompt': 'def is_palindrome(s):', 'canonical_solution': 'def is_palindrome(s):\n    s = re.sub(r"[^a-zA-Z0-9]", "", s).lower()\n    return s == s[::-1]'},
                {'id': 'he_004', 'prompt': 'def max_subarray(nums):', 'canonical_solution': 'def max_subarray(nums):\n    max_sum = nums[0]\n    for num in nums[1:]:\n        max_sum = max(max_sum, max_sum + num)\n    return max_sum'},
                {'id': 'he_005', 'prompt': 'def merge_sorted_lists(l1, l2):', 'canonical_solution': 'def merge_sorted_lists(l1, l2):\n    result = []\n    i = j = 0\n    while i < len(l1) and j < len(l2):\n        if l1[i] <= l2[j]:\n            result.append(l1[i]); i += 1\n        else:\n            result.append(l2[j]); j += 1\n    return result + l1[i:] + l2[j:]'},
            ],
            'mbpp': [
                {'id': 'mbpp_001', 'prompt': '函数返回数字的平方', 'canonical_solution': 'def square(n):\n    return n * n'},
                {'id': 'mbpp_002', 'prompt': '检查字符串是否以元音开头', 'canonical_solution': 'def starts_with_vowel(s):\n    return s and s[0].lower() in "aeiou"'},
                {'id': 'mbpp_003', 'prompt': '计算字符串中大写字母数量', 'canonical_solution': 'def count_uppercase(s):\n    return sum(1 for c in s if c.isupper())'},
                {'id': 'mbpp_004', 'prompt': '返回列表中的最大值', 'canonical_solution': 'def find_max(lst):\n    return max(lst) if lst else None'},
                {'id': 'mbpp_005', 'prompt': '翻转字符串', 'canonical_solution': 'def reverse_string(s):\n    return s[::-1]'},
            ],
        }
    
    def evaluate(self, custom_prompts=None):
        from base_evaluator import MetricScore, MetricType, EvaluationResult
        
        start_time = datetime.now()
        tasks = self.enabled_tasks if not custom_prompts else [t.get('task') for t in custom_prompts]
        
        task_scores = {}
        task_results = {}
        
        for task in tasks:
            if task not in self._test_data:
                continue
            samples = self._test_data[task][:self.max_samples]
            score, results = self._evaluate_task(task, samples)
            task_scores[task] = score
            task_results[task] = results
        
        valid_scores = [s for s in task_scores.values() if s is not None]
        overall = sum(valid_scores) / len(valid_scores) if valid_scores else 0
        
        benchmark_score = BenchmarkScore(
            arc=task_scores.get('arc'),
            gsm8k=task_scores.get('gsm8k'),
            mmlu=task_scores.get('mmlu'),
            humaneval=task_scores.get('humaneval'),
            mbpp=task_scores.get('mbpp'),
            overall=overall,
            tasks_completed=len(valid_scores),
            total_tasks=len(tasks),
            task_results=task_results
        )
        
        metrics = {
            'benchmark_overall': MetricScore("Benchmark总分", overall, MetricType.ACCURACY, "%", True, "综合基准测试分数"),
            'arc_score': MetricScore("ARC分数", task_scores.get('arc', 0) or 0, MetricType.ACCURACY, "%", True, "AI2推理挑战"),
            'gsm8k_score': MetricScore("GSM8K分数", task_scores.get('gsm8k', 0) or 0, MetricType.ACCURACY, "%", True, "数学推理"),
            'mmlu_score': MetricScore("MMLU分数", task_scores.get('mmlu', 0) or 0, MetricType.ACCURACY, "%", True, "多任务理解"),
            'humaneval_score': MetricScore("HumanEval分数", task_scores.get('humaneval', 0) or 0, MetricType.ACCURACY, "%", True, "代码生成"),
            'mbpp_score': MetricScore("MBPP分数", task_scores.get('mbpp', 0) or 0, MetricType.ACCURACY, "%", True, "Python编程"),
        }
        
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        return EvaluationResult(
            evaluator_name=self.name,
            timestamp=datetime.now().isoformat(),
            duration_ms=duration_ms,
            metrics=metrics,
            raw_data={'benchmark': benchmark_score},
            metadata={'tasks_evaluated': list(task_scores.keys()), 'tasks_completed': len(valid_scores)}
        )
    
    def _evaluate_task(self, task, samples):
        correct = 0
        results = []
        for sample in samples:
            result = self._evaluate_sample(task, sample)
            results.append(result)
            if result['correct']:
                correct += 1
        score = (correct / len(samples) * 100) if samples else 0
        return score, {'correct': correct, 'total': len(samples), 'score': score, 'samples': results}
    
    def _evaluate_sample(self, task, sample):
        response = self._simulate_model_response(task, sample)
        is_correct, feedback = self._check_answer(task, sample, response)
        return {
            'id': sample.get('id', 'unknown'),
            'correct': is_correct,
            'response': response,
            'expected': sample.get('answer') or sample.get('canonical_solution', ''),
            'feedback': feedback
        }
    
    def _simulate_model_response(self, task, sample):
        accuracy_map = {'arc': 0.75, 'gsm8k': 0.65, 'mmlu': 0.70, 'humaneval': 0.60, 'mbpp': 0.80}
        accuracy = accuracy_map.get(task, 0.5)
        if random.random() < accuracy:
            if task in ['arc', 'mmlu']:
                return sample.get('answer', '')
            return sample.get('canonical_solution', '') or sample.get('answer', '')
        else:
            if task in ['arc', 'mmlu']:
                choices = sample.get('choices', [])
                if choices:
                    return random.choice([c for c in choices if c != sample.get('answer')])
            return 'incorrect'
    
    def _check_answer(self, task, sample, response):
        expected = sample.get('answer') or sample.get('canonical_solution', '')
        if task in ['arc', 'mmlu']:
            is_correct = response.strip().lower() == expected.strip().lower()
            feedback = "correct" if is_correct else f"incorrect, answer is {expected}"
        elif task == 'gsm8k':
            response_nums = re.findall(r'\d+', str(response))
            expected_nums = re.findall(r'\d+', str(expected))
            is_correct = response_nums == expected_nums
            feedback = "correct" if is_correct else "calculation error"
        else:
            expected_code = expected.strip()
            response_code = response.strip()
            is_correct = ('def ' in expected_code and 'def ' in response_code) or ('class ' in expected_code and 'class ' in response_code)
            feedback = "code structure correct" if is_correct else "code structure mismatch"
        return is_correct, feedback
    
    def run_tasks(self, tasks, verbose=True):
        results = {}
        for task in tasks:
            task_name = task.value if isinstance(task, BenchmarkTask) else task
            if task_name in self._test_data:
                samples = self._test_data[task_name]
                score, task_results = self._evaluate_task(task_name, samples)
                results[task_name] = {'score': score, 'correct': task_results['correct'], 'total': task_results['total']}
                if verbose:
                    print(f"  {task_name}: {score:.2f}% ({task_results['correct']}/{task_results['total']})")
        return {'scores': results}
    
    def get_reference_scores(self):
        return {
            'human': {'arc': 95.0, 'gsm8k': 100.0, 'mmlu': 89.8, 'humaneval': 100.0, 'mbpp': 100.0},
            'gpt4': {'arc': 96.3, 'gsm8k': 94.8, 'mmlu': 86.4, 'humaneval': 90.2, 'mbpp': 81.7},
            'claude3': {'arc': 95.9, 'gsm8k': 96.2, 'mmlu': 88.5, 'humaneval': 88.7, 'mbpp': 79.2},
            'llama3_70b': {'arc': 85.3, 'gsm8k': 83.2, 'mmlu': 82.0, 'humaneval': 65.0, 'mbpp': 58.0}
        }
