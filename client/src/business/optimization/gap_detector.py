"""
GapDetector - 智能缺口检测器

核心功能：
1. 检测任务中的知识缺口
2. 识别参数完整性
3. 评估知识覆盖率
4. 生成补充问题
5. 评估生成风险

支持的缺口类型：
- 参数缺失：必要参数未提供
- 知识盲区：所需知识不在知识库中
- 数据冲突：提供的数据存在矛盾
- 风险评估：任务完成风险评估
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class GapInfo:
    """缺口信息"""
    gap_type: str  # parameter_missing/knowledge_gap/data_conflict/risk
    description: str
    severity: str = "medium"  # low/medium/high/critical
    suggested_questions: List[str] = field(default_factory=list)
    confidence: float = 0.5


@dataclass
class GapDetectionResult:
    """缺口检测结果"""
    has_gaps: bool
    gaps: List[GapInfo] = field(default_factory=list)
    risk_score: float = 0.0  # 0-1，越高风险越大
    coverage_rate: float = 1.0  # 0-1，知识覆盖率


class GapDetector:
    """智能缺口检测器"""
    
    def __init__(self):
        self._logger = logger.bind(component="GapDetector")
        
        # 已知参数类型
        self._required_params = {
            "document_generation": ["topic", "length", "style"],
            "data_analysis": ["data_source", "analysis_type", "output_format"],
            "code_generation": ["language", "purpose", "framework"],
            "calculation": ["formula", "parameters", "precision"]
        }
        
        # 风险评估因子
        self._risk_factors = {
            "parameter_missing": 0.3,
            "knowledge_gap": 0.4,
            "data_conflict": 0.5,
            "complexity": 0.2
        }
        
        self._logger.info("GapDetector 初始化完成")
    
    def detect_gaps(self, task_type: str, task_data: Dict[str, Any]) -> GapDetectionResult:
        """
        检测任务中的缺口
        
        Args:
            task_type: 任务类型
            task_data: 任务数据
        
        Returns:
            缺口检测结果
        """
        gaps = []
        risk_score = 0.0
        
        # 1. 检测参数缺失
        param_gaps = self._detect_parameter_gaps(task_type, task_data)
        gaps.extend(param_gaps)
        
        # 2. 检测知识缺口
        knowledge_gaps = self._detect_knowledge_gaps(task_type, task_data)
        gaps.extend(knowledge_gaps)
        
        # 3. 检测数据冲突
        conflict_gaps = self._detect_data_conflicts(task_data)
        gaps.extend(conflict_gaps)
        
        # 4. 评估风险
        risk_score = self._calculate_risk(gaps, task_type)
        
        # 5. 计算知识覆盖率
        coverage_rate = self._calculate_coverage(task_type, task_data)
        
        return GapDetectionResult(
            has_gaps=len(gaps) > 0,
            gaps=gaps,
            risk_score=risk_score,
            coverage_rate=coverage_rate
        )
    
    def _detect_parameter_gaps(self, task_type: str, task_data: Dict[str, Any]) -> List[GapInfo]:
        """检测参数缺失"""
        gaps = []
        
        required = self._required_params.get(task_type, [])
        missing = [p for p in required if p not in task_data or not task_data[p]]
        
        if missing:
            questions = [f"请提供{param}参数" for param in missing]
            
            gaps.append(GapInfo(
                gap_type="parameter_missing",
                description=f"缺少必要参数: {', '.join(missing)}",
                severity="high" if len(missing) > len(required) / 2 else "medium",
                suggested_questions=questions,
                confidence=0.9
            ))
        
        return gaps
    
    def _detect_knowledge_gaps(self, task_type: str, task_data: Dict[str, Any]) -> List[GapInfo]:
        """检测知识缺口"""
        gaps = []
        
        # 简化实现：检查关键概念是否在知识库中
        key_concepts = self._extract_key_concepts(task_type, task_data)
        
        for concept in key_concepts:
            if not self._is_concept_in_knowledge_base(concept):
                questions = [
                    f"关于{concept}，您能提供更多背景信息吗？",
                    f"您希望我如何处理{concept}相关内容？"
                ]
                
                gaps.append(GapInfo(
                    gap_type="knowledge_gap",
                    description=f"知识盲区: {concept}",
                    severity="medium",
                    suggested_questions=questions,
                    confidence=0.7
                ))
        
        return gaps
    
    def _extract_key_concepts(self, task_type: str, task_data: Dict[str, Any]) -> List[str]:
        """提取关键概念"""
        concepts = []
        
        if task_type == "document_generation":
            topic = task_data.get("topic", "")
            if topic:
                concepts.extend(topic.split())
        
        elif task_type == "data_analysis":
            concepts.append(task_data.get("analysis_type", ""))
        
        elif task_type == "code_generation":
            concepts.append(task_data.get("language", ""))
            concepts.append(task_data.get("framework", ""))
        
        return [c for c in concepts if c]
    
    def _is_concept_in_knowledge_base(self, concept: str) -> bool:
        """检查概念是否在知识库中"""
        # 简化实现：模拟知识库检查
        known_concepts = {"人工智能", "机器学习", "深度学习", "Python", "数据分析", "文档生成"}
        return concept.lower() in (c.lower() for c in known_concepts)
    
    def _detect_data_conflicts(self, task_data: Dict[str, Any]) -> List[GapInfo]:
        """检测数据冲突"""
        gaps = []
        
        # 检查冲突
        if "deadline" in task_data and "priority" in task_data:
            deadline = task_data["deadline"]
            priority = task_data["priority"]
            
            if priority == "high" and deadline > 7:  # 高优先级但截止日期远
                gaps.append(GapInfo(
                    gap_type="data_conflict",
                    description="高优先级任务但截止日期较远",
                    severity="low",
                    suggested_questions=["是否需要调整优先级或截止日期？"],
                    confidence=0.6
                ))
        
        return gaps
    
    def _calculate_risk(self, gaps: List[GapInfo], task_type: str) -> float:
        """计算风险分数"""
        risk = 0.0
        
        for gap in gaps:
            factor = self._risk_factors.get(gap.gap_type, 0.2)
            severity_multiplier = {"low": 0.3, "medium": 0.6, "high": 0.9, "critical": 1.0}[gap.severity]
            risk += factor * severity_multiplier * gap.confidence
        
        # 任务复杂度因子
        complexity = self._estimate_complexity(task_type)
        risk += complexity * self._risk_factors["complexity"]
        
        return min(1.0, risk)
    
    def _estimate_complexity(self, task_type: str) -> float:
        """估计任务复杂度"""
        complexity_map = {
            "document_generation": 0.5,
            "data_analysis": 0.7,
            "code_generation": 0.8,
            "calculation": 0.4
        }
        return complexity_map.get(task_type, 0.5)
    
    def _calculate_coverage(self, task_type: str, task_data: Dict[str, Any]) -> float:
        """计算知识覆盖率"""
        key_concepts = self._extract_key_concepts(task_type, task_data)
        
        if not key_concepts:
            return 1.0
        
        known_count = sum(1 for c in key_concepts if self._is_concept_in_knowledge_base(c))
        return known_count / len(key_concepts)
    
    def generate_followup_questions(self, gaps: List[GapInfo]) -> List[str]:
        """生成跟进问题"""
        questions = []
        
        for gap in gaps:
            questions.extend(gap.suggested_questions)
        
        return questions[:5]  # 最多返回5个问题


# 单例模式
_gap_detector_instance = None

def get_gap_detector() -> GapDetector:
    """获取缺口检测器实例"""
    global _gap_detector_instance
    if _gap_detector_instance is None:
        _gap_detector_instance = GapDetector()
    return _gap_detector_instance


if __name__ == "__main__":
    print("=" * 60)
    print("GapDetector 测试")
    print("=" * 60)
    
    detector = get_gap_detector()
    
    # 测试1：参数完整的任务
    print("\n[1] 参数完整的任务")
    task_data1 = {
        "topic": "人工智能",
        "length": "中等",
        "style": "技术文档"
    }
    result = detector.detect_gaps("document_generation", task_data1)
    print(f"有缺口: {result.has_gaps}")
    print(f"风险评分: {result.risk_score:.2f}")
    print(f"知识覆盖率: {result.coverage_rate:.2f}")
    
    # 测试2：缺少参数的任务
    print("\n[2] 缺少参数的任务")
    task_data2 = {
        "topic": "量子计算"
    }
    result = detector.detect_gaps("document_generation", task_data2)
    print(f"有缺口: {result.has_gaps}")
    print(f"风险评分: {result.risk_score:.2f}")
    print(f"知识覆盖率: {result.coverage_rate:.2f}")
    print("缺口详情:")
    for gap in result.gaps:
        print(f"  - {gap.gap_type}: {gap.description} ({gap.severity})")
    
    # 测试3：生成跟进问题
    print("\n[3] 生成跟进问题")
    questions = detector.generate_followup_questions(result.gaps)
    for i, question in enumerate(questions, 1):
        print(f"  {i}. {question}")
    
    # 测试4：代码生成任务
    print("\n[4] 代码生成任务")
    task_data3 = {
        "language": "Rust",
        "purpose": "高性能计算",
        "framework": "TensorFlow"
    }
    result = detector.detect_gaps("code_generation", task_data3)
    print(f"有缺口: {result.has_gaps}")
    print(f"风险评分: {result.risk_score:.2f}")
    print(f"知识覆盖率: {result.coverage_rate:.2f}")
    print("缺口详情:")
    for gap in result.gaps:
        print(f"  - {gap.description}")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)