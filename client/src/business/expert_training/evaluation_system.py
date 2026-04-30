"""
评估体系模块 (Evaluation System)

工业级的"严苛考试"评估体系：
1. 黄金测试集构建
2. 关键KPI指标定义
3. 专家评分机制
4. 综合评估报告生成

核心原则：不用"准确率"衡量，用工程可用性衡量
"""

import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TestCase:
    """测试用例"""
    case_id: str
    input_data: str
    expected_output: Optional[str] = None
    task_type: str = "general"
    difficulty: int = 1
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class EvaluationResult:
    """评估结果"""
    case_id: str
    model_output: str
    passed: bool
    score: float
    metrics: Dict[str, float] = field(default_factory=dict)
    expert_rating: Optional[int] = None  # 1-5
    expert_comments: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class KPIMetrics:
    """KPI指标"""
    task_completion_rate: float = 0.0      # 能给出有效方案的任务比例
    tool_call_accuracy: float = 0.0        # 正确调用计算工具的比例
    hallucination_rate: float = 0.0        # 生成无法验证的"编造"内容比例
    expert_score: float = 0.0              # 专家盲评平均分
    logic_consistency: float = 0.0         # 逻辑一致性
    term_accuracy: float = 0.0             # 术语准确率
    uncertainty_rate: float = 0.0          # 风险提示率


class EvaluationSystem:
    """
    评估体系
    
    工业级评估体系：
    1. 黄金测试集：功能测试 + 压力测试 + 专家评分
    2. KPI指标：任务完成率、工具调用准确率、幻觉率、专家评分
    3. 综合评估报告
    """
    
    def __init__(self):
        # 测试集
        self.test_cases: Dict[str, TestCase] = {}
        self.results: List[EvaluationResult] = []
        
        # KPI阈值
        self.kpi_thresholds = {
            "task_completion_rate": 0.90,
            "tool_call_accuracy": 0.85,
            "hallucination_rate": 0.03,
            "expert_score": 4.0,
            "logic_consistency": 0.80,
            "term_accuracy": 0.90,
            "uncertainty_rate": 0.30
        }
        
        # 行业术语库（用于术语准确性评估）
        self.industry_terms = {
            "机械制造": ["公差", "配合", "粗糙度", "热处理", "CNC", "加工中心"],
            "电子电气": ["PLC", "MCU", "PCB", "继电器", "变频器", "传感器"],
            "化工": ["反应釜", "精馏塔", "换热器", "催化剂", "工艺"],
            "汽车": ["ECU", "ESP", "ABS", "动力电池", "ADAS"],
            "能源": ["光伏", "风电", "储能", "逆变器", "充电桩"]
        }
        
        # 标准号模式（用于格式检查）
        self.standard_patterns = [
            r'GB/T\s*\d+(?:\.\d+)*',
            r'GB\s*\d+(?:\.\d+)*',
            r'IEC\s*\d+',
            r'ISO\s*\d+'
        ]
        
        # 统计
        self.total_tests = 0
        self.passed_tests = 0
        self.expert_ratings = []
        
        print("[EvaluationSystem] 初始化完成")
    
    def add_test_case(self, case_id: str, input_data: str, expected_output: Optional[str] = None,
                     task_type: str = "general", difficulty: int = 1, tags: Optional[List[str]] = None):
        """
        添加测试用例
        
        Args:
            case_id: 用例ID
            input_data: 输入数据
            expected_output: 期望输出（可选，用于功能测试）
            task_type: 任务类型
            difficulty: 难度 (1-5)
            tags: 标签列表
        """
        test_case = TestCase(
            case_id=case_id,
            input_data=input_data,
            expected_output=expected_output,
            task_type=task_type,
            difficulty=difficulty,
            tags=tags or []
        )
        
        self.test_cases[case_id] = test_case
        print(f"[EvaluationSystem] 添加测试用例: {case_id}")
    
    def load_standard_test_set(self):
        """加载标准测试集"""
        # 功能测试用例
        functional_cases = [
            ("func_001", "为化工厂强腐蚀环境选择流量计，介质为硫酸，温度80℃",
             "推荐选用电磁流量计，电极材质建议哈氏C-276", "selection", 3),
            ("func_002", "计算DN100管道在2MPa压力下的壁厚",
             "根据GB/T 8163标准计算，所需壁厚约为1.07mm", "calculation", 3),
            ("func_003", "验证轴直径50mm，公差等级IT7是否符合标准",
             "IT7级公差在50mm尺寸段为0.025mm", "validation", 2),
            ("func_004", "电机运行时异响且温度升高，分析原因",
             "可能原因包括轴承损坏、润滑不足、过载", "diagnosis", 3),
            ("func_005", "方案A使用304不锈钢成本低，方案B使用316不锈钢耐腐蚀性好，对比评价",
             "建议选择方案B，长期可靠性更优", "comparison", 3)
        ]
        
        # 压力测试用例（模糊需求、矛盾参数、知识缺口）
        stress_cases = [
            ("stress_001", "选择一款好的传感器", None, "selection", 4),
            ("stress_002", "温度要求-100℃，同时要求使用塑料材质", None, "selection", 5),
            ("stress_003", "分析一个不知道是什么设备的故障", None, "diagnosis", 5)
        ]
        
        for case_id, input_data, expected, task_type, difficulty in functional_cases:
            self.add_test_case(case_id, input_data, expected, task_type, difficulty, ["functional"])
        
        for case_id, input_data, expected, task_type, difficulty in stress_cases:
            self.add_test_case(case_id, input_data, expected, task_type, difficulty, ["stress"])
        
        print(f"[EvaluationSystem] 加载了 {len(functional_cases)} 个功能测试用例和 {len(stress_cases)} 个压力测试用例")
    
    def evaluate(self, case_id: str, model_output: str) -> EvaluationResult:
        """
        评估单个测试用例
        
        Args:
            case_id: 测试用例ID
            model_output: 模型输出
            
        Returns:
            评估结果
        """
        test_case = self.test_cases.get(case_id)
        if not test_case:
            raise ValueError(f"测试用例不存在: {case_id}")
        
        self.total_tests += 1
        
        # 计算各项指标
        metrics = self._compute_metrics(model_output, test_case)
        
        # 判断是否通过
        passed = self._is_passed(metrics, test_case)
        
        if passed:
            self.passed_tests += 1
        
        result = EvaluationResult(
            case_id=case_id,
            model_output=model_output,
            passed=passed,
            score=metrics.get("overall", 0.0),
            metrics=metrics
        )
        
        self.results.append(result)
        return result
    
    def _compute_metrics(self, output: str, test_case: TestCase) -> Dict[str, float]:
        """
        计算各项指标
        
        Args:
            output: 模型输出
            test_case: 测试用例
            
        Returns:
            指标字典
        """
        metrics = {}
        
        # 1. 逻辑一致性
        metrics["logic_consistency"] = self._evaluate_logic_consistency(output)
        
        # 2. 术语准确率
        metrics["term_accuracy"] = self._evaluate_term_accuracy(output, test_case.task_type)
        
        # 3. 格式正确性（标准号格式）
        metrics["format_correctness"] = self._evaluate_format_correctness(output)
        
        # 4. 不确定性提示率
        metrics["uncertainty_rate"] = self._evaluate_uncertainty(output)
        
        # 5. 幻觉检测
        metrics["hallucination_score"] = self._detect_hallucination(output)
        
        # 6. 任务完成度
        metrics["completion_score"] = self._evaluate_completion(output, test_case)
        
        # 综合分数
        metrics["overall"] = (
            metrics["logic_consistency"] * 0.2 +
            metrics["term_accuracy"] * 0.2 +
            metrics["format_correctness"] * 0.15 +
            metrics["uncertainty_rate"] * 0.15 +
            (1 - metrics["hallucination_score"]) * 0.2 +
            metrics["completion_score"] * 0.1
        )
        
        return metrics
    
    def _evaluate_logic_consistency(self, output: str) -> float:
        """评估逻辑一致性"""
        # 检查是否有推理步骤
        if any(marker in output for marker in ["因为", "因此", "基于", "根据"]):
            return 0.85
        
        # 检查是否有结构化输出
        if any(pattern in output for pattern in ["1.", "2.", "首先", "其次"]):
            return 0.75
        
        # 简单检查长度
        if len(output) > 100:
            return 0.6
        else:
            return 0.4
    
    def _evaluate_term_accuracy(self, output: str, task_type: str) -> float:
        """评估术语准确率"""
        domain = self._task_type_to_domain(task_type)
        domain_terms = self.industry_terms.get(domain, [])
        
        if not domain_terms:
            return 0.7  # 默认值
        
        # 检查是否使用了正确的行业术语
        found_terms = [t for t in domain_terms if t in output]
        
        if found_terms:
            return min(1.0, 0.6 + len(found_terms) * 0.1)
        else:
            return 0.5
    
    def _evaluate_format_correctness(self, output: str) -> float:
        """评估格式正确性"""
        import re
        
        score = 0.5
        
        for pattern in self.standard_patterns:
            if re.search(pattern, output):
                score += 0.2
        
        # 检查是否有单位
        if any(unit in output for unit in ["MPa", "℃", "mm", "kW"]):
            score += 0.1
        
        return min(1.0, score)
    
    def _evaluate_uncertainty(self, output: str) -> float:
        """评估不确定性提示"""
        uncertainty_markers = ["需确认", "建议", "可能", "需要", "检查"]
        
        found = sum(1 for marker in uncertainty_markers if marker in output)
        
        if found >= 2:
            return 1.0
        elif found == 1:
            return 0.7
        else:
            return 0.3
    
    def _detect_hallucination(self, output: str) -> float:
        """检测幻觉"""
        import re
        
        hallucination_score = 0.0
        
        # 检查是否有虚假标准号
        fake_standard = re.search(r'GB/T\s*\d{1,2}$', output)
        if fake_standard:
            hallucination_score += 0.3
        
        # 检查是否有过于绝对的表述
        absolute_terms = ["绝对", "完全", "必定", "唯一"]
        if any(term in output for term in absolute_terms):
            hallucination_score += 0.2
        
        # 检查是否有无法验证的内容
        unverifiable_patterns = [
            r'研究表明',
            r'据统计',
            r'专家认为'
        ]
        if any(re.search(pattern, output) for pattern in unverifiable_patterns):
            hallucination_score += 0.2
        
        return min(1.0, hallucination_score)
    
    def _evaluate_completion(self, output: str, test_case: TestCase) -> float:
        """评估任务完成度"""
        if not test_case.expected_output:
            # 没有期望输出，基于长度和内容判断
            if len(output) > 200:
                return 0.9
            elif len(output) > 100:
                return 0.7
            elif len(output) > 50:
                return 0.5
            else:
                return 0.3
        else:
            # 有期望输出，计算相似度
            expected = test_case.expected_output
            expected_words = set(expected.lower().split())
            output_words = set(output.lower().split())
            
            intersection = expected_words & output_words
            if intersection:
                return len(intersection) / len(expected_words)
            return 0.0
    
    def _task_type_to_domain(self, task_type: str) -> str:
        """任务类型转领域"""
        mapping = {
            "selection": "机械制造",
            "calculation": "机械制造",
            "validation": "机械制造",
            "diagnosis": "电子电气",
            "comparison": "通用"
        }
        return mapping.get(task_type, "通用")
    
    def _is_passed(self, metrics: Dict[str, float], test_case: TestCase) -> bool:
        """判断是否通过"""
        # 基础要求：综合分数 >= 0.6
        if metrics.get("overall", 0) < 0.6:
            return False
        
        # 幻觉检测：不能太高
        if metrics.get("hallucination_score", 0) > 0.5:
            return False
        
        # 难度调整
        if test_case.difficulty >= 4:
            return metrics.get("overall", 0) >= 0.7
        else:
            return True
    
    def add_expert_rating(self, case_id: str, rating: int, comments: Optional[str] = None):
        """
        添加专家评分
        
        Args:
            case_id: 测试用例ID
            rating: 评分 (1-5)
            comments: 专家评语
        """
        # 查找对应的评估结果
        for result in self.results:
            if result.case_id == case_id:
                result.expert_rating = rating
                result.expert_comments = comments
                self.expert_ratings.append(rating)
                break
    
    def calculate_kpis(self) -> KPIMetrics:
        """计算KPI指标"""
        if not self.results:
            return KPIMetrics()
        
        # 任务完成率
        task_completion_rate = sum(1 for r in self.results if r.passed) / len(self.results)
        
        # 工具调用准确率（需要专门测试）
        tool_cases = [r for r in self.results if "tool" in r.case_id.lower()]
        tool_call_accuracy = sum(1 for r in tool_cases if r.passed) / max(len(tool_cases), 1)
        
        # 幻觉率
        hallucination_rate = sum(r.metrics.get("hallucination_score", 0) for r in self.results) / len(self.results)
        
        # 专家评分
        expert_score = sum(self.expert_ratings) / max(len(self.expert_ratings), 1) if self.expert_ratings else 0
        
        # 逻辑一致性
        logic_consistency = sum(r.metrics.get("logic_consistency", 0) for r in self.results) / len(self.results)
        
        # 术语准确率
        term_accuracy = sum(r.metrics.get("term_accuracy", 0) for r in self.results) / len(self.results)
        
        # 不确定性提示率
        uncertainty_rate = sum(r.metrics.get("uncertainty_rate", 0) for r in self.results) / len(self.results)
        
        return KPIMetrics(
            task_completion_rate=task_completion_rate,
            tool_call_accuracy=tool_call_accuracy,
            hallucination_rate=hallucination_rate,
            expert_score=expert_score,
            logic_consistency=logic_consistency,
            term_accuracy=term_accuracy,
            uncertainty_rate=uncertainty_rate
        )
    
    def generate_report(self) -> Dict[str, Any]:
        """生成综合评估报告"""
        kpis = self.calculate_kpis()
        
        # 检查达标情况
        compliance = {}
        for kpi, value in kpis.__dict__.items():
            threshold = self.kpi_thresholds.get(kpi, 0.0)
            if kpi == "hallucination_rate":
                compliance[kpi] = value <= threshold
            else:
                compliance[kpi] = value >= threshold
        
        # 按任务类型统计
        by_task_type = {}
        for result in self.results:
            case = self.test_cases.get(result.case_id)
            if case:
                task_type = case.task_type
                if task_type not in by_task_type:
                    by_task_type[task_type] = {"total": 0, "passed": 0}
                by_task_type[task_type]["total"] += 1
                by_task_type[task_type]["passed"] += 1 if result.passed else 0
        
        return {
            "report_generated_at": datetime.now().isoformat(),
            "total_test_cases": len(self.test_cases),
            "total_evaluations": len(self.results),
            "pass_rate": self.passed_tests / max(self.total_tests, 1),
            "kpis": {
                "task_completion_rate": kpis.task_completion_rate,
                "tool_call_accuracy": kpis.tool_call_accuracy,
                "hallucination_rate": kpis.hallucination_rate,
                "expert_score": kpis.expert_score,
                "logic_consistency": kpis.logic_consistency,
                "term_accuracy": kpis.term_accuracy,
                "uncertainty_rate": kpis.uncertainty_rate
            },
            "thresholds": self.kpi_thresholds,
            "compliance": compliance,
            "by_task_type": by_task_type,
            "expert_ratings_summary": {
                "count": len(self.expert_ratings),
                "average": sum(self.expert_ratings) / max(len(self.expert_ratings), 1) if self.expert_ratings else 0
            }
        }
    
    def export_report(self, filepath: str):
        """导出评估报告"""
        report = self.generate_report()
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"[EvaluationSystem] 评估报告已导出到 {filepath}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_test_cases": len(self.test_cases),
            "total_evaluations": len(self.results),
            "pass_rate": self.passed_tests / max(self.total_tests, 1),
            "expert_rating_count": len(self.expert_ratings),
            "average_expert_rating": sum(self.expert_ratings) / max(len(self.expert_ratings), 1) if self.expert_ratings else 0
        }


def create_evaluation_system() -> EvaluationSystem:
    """创建评估系统实例"""
    system = EvaluationSystem()
    system.load_standard_test_set()
    return system


__all__ = [
    "EvaluationSystem",
    "TestCase",
    "EvaluationResult",
    "KPIMetrics",
    "create_evaluation_system"
]