"""
QualityValidator - 质量验证引擎

核心功能：
1. 事实核查：检查生成内容与源数据一致性
2. 逻辑验证：确保论证链条完整
3. 格式检查：符合行业文档规范
4. 迭代优化：基于验证结果自动修正

验证维度：
- 事实准确性
- 逻辑一致性
- 格式规范性
- 风格一致性
- 完整性
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class ValidationIssue:
    """验证问题"""
    issue_type: str  # factual/logical/format/style/completeness
    description: str
    severity: str = "warning"  # info/warning/error/critical
    location: str = ""  # 问题位置
    suggestion: str = ""  # 改进建议
    confidence: float = 0.5


@dataclass
class ValidationResult:
    """验证结果"""
    passed: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    scores: Dict[str, float] = field(default_factory=dict)  # 各维度评分
    overall_score: float = 0.0


class QualityValidator:
    """质量验证引擎"""
    
    def __init__(self):
        self._logger = logger.bind(component="QualityValidator")
        
        # 验证规则权重
        self._rule_weights = {
            "factual": 0.3,
            "logical": 0.25,
            "format": 0.2,
            "style": 0.15,
            "completeness": 0.1
        }
        
        # 格式规范
        self._format_rules = {
            "min_length": 100,
            "max_length": 100000,
            "max_sentence_length": 200,
            "min_paragraphs": 2
        }
        
        self._logger.info("QualityValidator 初始化完成")
    
    def validate(self, content: str, source_data: Optional[Dict] = None, 
                reference_style: Optional[str] = None) -> ValidationResult:
        """
        执行质量验证
        
        Args:
            content: 待验证内容
            source_data: 源数据（用于事实核查）
            reference_style: 参考风格（用于风格一致性检查）
        
        Returns:
            验证结果
        """
        issues = []
        
        # 1. 事实核查
        factual_issues = self._validate_factual(content, source_data)
        issues.extend(factual_issues)
        
        # 2. 逻辑验证
        logical_issues = self._validate_logical(content)
        issues.extend(logical_issues)
        
        # 3. 格式检查
        format_issues = self._validate_format(content)
        issues.extend(format_issues)
        
        # 4. 风格一致性检查
        style_issues = self._validate_style(content, reference_style)
        issues.extend(style_issues)
        
        # 5. 完整性检查
        completeness_issues = self._validate_completeness(content, source_data)
        issues.extend(completeness_issues)
        
        # 计算各维度评分
        scores = self._calculate_scores(issues)
        
        # 计算综合评分
        overall_score = self._calculate_overall_score(scores)
        
        # 判断是否通过
        passed = overall_score >= 0.7 and not any(i.severity in ["error", "critical"] for i in issues)
        
        return ValidationResult(
            passed=passed,
            issues=issues,
            scores=scores,
            overall_score=overall_score
        )
    
    def _validate_factual(self, content: str, source_data: Optional[Dict]) -> List[ValidationIssue]:
        """事实核查"""
        issues = []
        
        if not source_data:
            return issues
        
        # 检查关键数据一致性
        for key, expected_value in source_data.items():
            if isinstance(expected_value, str) and expected_value:
                if expected_value.lower() not in content.lower():
                    issues.append(ValidationIssue(
                        issue_type="factual",
                        description=f"关键信息未包含: {key}",
                        severity="warning",
                        suggestion=f"请确保内容包含'{expected_value}'相关信息",
                        confidence=0.8
                    ))
        
        return issues
    
    def _validate_logical(self, content: str) -> List[ValidationIssue]:
        """逻辑验证"""
        issues = []
        
        sentences = self._split_sentences(content)
        
        # 检查句子连贯性
        for i in range(len(sentences) - 1):
            current = sentences[i]
            next_sentence = sentences[i + 1]
            
            if not self._has_coherence(current, next_sentence):
                issues.append(ValidationIssue(
                    issue_type="logical",
                    description=f"第{i+1}句与第{i+2}句逻辑不连贯",
                    severity="warning",
                    suggestion="请检查句子之间的逻辑连接",
                    confidence=0.6
                ))
        
        # 检查因果关系
        if "因为" in content or "所以" in content:
            if not self._has_valid_causality(content):
                issues.append(ValidationIssue(
                    issue_type="logical",
                    description="因果关系表述不完整",
                    severity="warning",
                    suggestion="请确保因果关系清晰完整",
                    confidence=0.5
                ))
        
        return issues
    
    def _split_sentences(self, content: str) -> List[str]:
        """分割句子"""
        import re
        return [s.strip() for s in re.split(r'[。！？\n]', content) if s.strip()]
    
    def _has_coherence(self, sentence1: str, sentence2: str) -> bool:
        """检查句子连贯性"""
        words1 = sentence1.lower().split()
        words2 = sentence2.lower().split()
        
        # 检查是否有共同词汇
        common_words = set(words1) & set(words2)
        return len(common_words) > 0 or len(sentence1) < 10 or len(sentence2) < 10
    
    def _has_valid_causality(self, content: str) -> bool:
        """检查因果关系有效性"""
        return content.count("因为") == content.count("所以")
    
    def _validate_format(self, content: str) -> List[ValidationIssue]:
        """格式检查"""
        issues = []
        
        # 检查长度
        length = len(content)
        if length < self._format_rules["min_length"]:
            issues.append(ValidationIssue(
                issue_type="format",
                description=f"内容过短 ({length}字符)",
                severity="warning",
                suggestion=f"建议至少{self._format_rules['min_length']}字符",
                confidence=0.9
            ))
        
        if length > self._format_rules["max_length"]:
            issues.append(ValidationIssue(
                issue_type="format",
                description=f"内容过长 ({length}字符)",
                severity="info",
                suggestion=f"建议不超过{self._format_rules['max_length']}字符",
                confidence=0.8
            ))
        
        # 检查句子长度
        sentences = self._split_sentences(content)
        for i, sentence in enumerate(sentences):
            if len(sentence) > self._format_rules["max_sentence_length"]:
                issues.append(ValidationIssue(
                    issue_type="format",
                    description=f"第{i+1}句过长 ({len(sentence)}字符)",
                    severity="warning",
                    location=f"句子{i+1}",
                    suggestion="建议拆分长句",
                    confidence=0.7
                ))
        
        # 检查段落数
        paragraphs = [p for p in content.split('\n\n') if p.strip()]
        if len(paragraphs) < self._format_rules["min_paragraphs"]:
            issues.append(ValidationIssue(
                issue_type="format",
                description=f"段落数不足 ({len(paragraphs)}段)",
                severity="info",
                suggestion=f"建议至少{self._format_rules['min_paragraphs']}段",
                confidence=0.6
            ))
        
        return issues
    
    def _validate_style(self, content: str, reference_style: Optional[str]) -> List[ValidationIssue]:
        """风格一致性检查"""
        issues = []
        
        if not reference_style:
            return issues
        
        # 检查正式度
        formal_words = {"综上所述", "据此", "因此", "然而", "此外", "首先", "其次"}
        informal_words = {"嗯", "啊", "哦", "吧", "嘛", "嘞"}
        
        formal_count = sum(1 for w in formal_words if w in content)
        informal_count = sum(1 for w in informal_words if w in content)
        
        if informal_count > formal_count and reference_style == "formal":
            issues.append(ValidationIssue(
                issue_type="style",
                description="语言风格不够正式",
                severity="warning",
                suggestion="建议使用更正式的表达方式",
                confidence=0.7
            ))
        
        return issues
    
    def _validate_completeness(self, content: str, source_data: Optional[Dict]) -> List[ValidationIssue]:
        """完整性检查"""
        issues = []
        
        if not source_data:
            return issues
        
        # 检查是否覆盖所有关键要点
        key_points = source_data.get("key_points", [])
        if key_points:
            missing_points = []
            for point in key_points:
                if point.lower() not in content.lower():
                    missing_points.append(point)
            
            if missing_points:
                issues.append(ValidationIssue(
                    issue_type="completeness",
                    description=f"缺少关键要点: {', '.join(missing_points)}",
                    severity="error",
                    suggestion=f"请补充以下要点: {', '.join(missing_points)}",
                    confidence=0.8
                ))
        
        return issues
    
    def _calculate_scores(self, issues: List[ValidationIssue]) -> Dict[str, float]:
        """计算各维度评分"""
        scores = {}
        
        for issue_type in self._rule_weights.keys():
            type_issues = [i for i in issues if i.issue_type == issue_type]
            
            if not type_issues:
                scores[issue_type] = 1.0
            else:
                # 根据严重程度扣分
                penalty = sum(self._get_penalty(i) for i in type_issues)
                scores[issue_type] = max(0.0, 1.0 - penalty)
        
        return scores
    
    def _get_penalty(self, issue: ValidationIssue) -> float:
        """计算问题惩罚值"""
        penalty_map = {
            "info": 0.02,
            "warning": 0.05,
            "error": 0.15,
            "critical": 0.3
        }
        return penalty_map.get(issue.severity, 0.05) * issue.confidence
    
    def _calculate_overall_score(self, scores: Dict[str, float]) -> float:
        """计算综合评分"""
        total = 0.0
        for issue_type, weight in self._rule_weights.items():
            total += scores.get(issue_type, 0.5) * weight
        return total
    
    def suggest_fixes(self, issues: List[ValidationIssue]) -> List[str]:
        """生成修复建议"""
        suggestions = []
        
        for issue in issues:
            if issue.suggestion:
                suggestions.append(issue.suggestion)
        
        return suggestions


# 单例模式
_quality_validator_instance = None

def get_quality_validator() -> QualityValidator:
    """获取质量验证器实例"""
    global _quality_validator_instance
    if _quality_validator_instance is None:
        _quality_validator_instance = QualityValidator()
    return _quality_validator_instance


if __name__ == "__main__":
    print("=" * 60)
    print("QualityValidator 测试")
    print("=" * 60)
    
    validator = get_quality_validator()
    
    # 测试1：完整内容
    print("\n[1] 完整内容验证")
    content1 = """人工智能是研究、开发用于模拟、延伸和扩展人的智能的理论、方法、技术及应用系统的一门新技术科学。
    人工智能领域的研究包括机器人、语言识别、图像识别、自然语言处理和专家系统等。
    人工智能从诞生以来，理论和技术日益成熟，应用领域也不断扩大。"""
    
    result = validator.validate(content1)
    print(f"通过验证: {result.passed}")
    print(f"综合评分: {result.overall_score:.2f}")
    print("各维度评分:")
    for dim, score in result.scores.items():
        print(f"  {dim}: {score:.2f}")
    
    # 测试2：有问题的内容
    print("\n[2] 有问题的内容验证")
    content2 = "AI很厉害。它能做很多事情。"
    
    result = validator.validate(content2)
    print(f"通过验证: {result.passed}")
    print(f"综合评分: {result.overall_score:.2f}")
    print("问题列表:")
    for issue in result.issues:
        print(f"  - [{issue.severity}] {issue.description}")
    
    # 测试3：带源数据的验证
    print("\n[3] 带源数据的验证")
    content3 = "机器学习是人工智能的一个分支。"
    source_data = {
        "key_concepts": ["机器学习", "深度学习", "神经网络"],
        "key_points": ["机器学习定义", "应用场景"]
    }
    
    result = validator.validate(content3, source_data)
    print(f"通过验证: {result.passed}")
    print(f"综合评分: {result.overall_score:.2f}")
    print("修复建议:")
    suggestions = validator.suggest_fixes(result.issues)
    for i, suggestion in enumerate(suggestions, 1):
        print(f"  {i}. {suggestion}")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)