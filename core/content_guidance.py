"""
内容分析引导模块 (Phase 3)
============================

基于内容深度分析生成智能追问，超越简单的关键词匹配

功能：
1. ContentAnalyzer - 内容类型识别与语义分析
2. ContentQualityEvaluator - 内容质量评估
3. SemanticGuidanceGenerator - 语义追问生成器
4. DomainGuidanceStrategies - 领域特定追问策略

设计原则：
- 深度语义理解，不仅仅是关键词匹配
- 领域感知，根据内容类型定制追问
- 质量评估，识别回答的完整性
- 多维度分析，多角度理解内容
"""

from typing import Optional, Callable, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import re
import hashlib
from collections import Counter

# 尝试导入 PyQt6 组件（可选）
try:
    from PyQt6.QtWidgets import QWidget
    from PyQt6.QtCore import QObject, pyqtSignal
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False
    QObject = object


# ============== 内容类型枚举 ==============

class ContentType(Enum):
    """内容类型"""
    CODE = "code"                    # 代码
    DOCUMENTATION = "documentation"  # 文档
    DATA = "data"                    # 数据/表格
    EXPLANATION = "explanation"       # 解释说明
    TUTORIAL = "tutorial"            # 教程/步骤
    COMPARISON = "comparison"         # 对比分析
    ANALYSIS = "analysis"            # 分析报告
    DISCUSSION = "discussion"         # 讨论
    QUESTION_ANSWER = "question_answer"  # 问答
    UNKNOWN = "unknown"              # 未知


class ContentQuality(Enum):
    """内容质量等级"""
    EXCELLENT = "excellent"          # 优秀 - 完整且深入
    GOOD = "good"                   # 良好 - 完整但可深化
    ADEQUATE = "adequate"            # 达标 - 基本回答问题
    INCOMPLETE = "incomplete"        # 不完整 - 缺少关键信息
    POOR = "poor"                    # 较差 - 需要重大改进


class GuidanceDepth(Enum):
    """追问深度"""
    SURFACE = "surface"             # 表面 - 简单确认
    MODERATE = "moderate"           # 中等 - 扩展理解
    DEEP = "deep"                   # 深入 - 深度探讨


# ============== 数据结构 ==============

@dataclass
class ContentAnalysis:
    """内容分析结果"""
    content_type: ContentType         # 内容类型
    confidence: float = 0.0          # 类型识别置信度
    
    # 语义信号
    has_code: bool = False           # 包含代码
    has_data: bool = False           # 包含数据/表格
    has_steps: bool = False          # 包含步骤
    has_comparison: bool = False     # 包含对比
    has_examples: bool = False       # 包含示例
    has_definitions: bool = False    # 包含定义
    has_analysis: bool = False       # 包含分析
    
    # 语义特征
    sentiment: str = "neutral"       # 情感倾向
    complexity: float = 0.5          # 复杂度 0-1
    technical_depth: float = 0.5     # 技术深度 0-1
    
    # 结构特征
    length: int = 0                  # 内容长度
    sentence_count: int = 0          # 句子数量
    paragraph_count: int = 0         # 段落数量
    structure_score: float = 0.5     # 结构化程度 0-1
    
    # 关键实体
    entities: Dict[str, List[str]] = field(default_factory=dict)
    
    # 主题
    topics: List[str] = field(default_factory=list)
    
    # 语言
    language: str = "zh"             # 语言检测


@dataclass
class QualityAssessment:
    """质量评估结果"""
    quality: ContentQuality          # 质量等级
    completeness: float = 0.5        # 完整性 0-1
    accuracy: float = 0.5            # 准确性 0-1
    clarity: float = 0.5             # 清晰度 0-1
    
    # 改进点
    missing_info: List[str] = field(default_factory=list)  # 缺失信息
    unclear_parts: List[str] = field(default_factory=list)  # 不清晰部分
    potential_errors: List[str] = field(default_factory=list)  # 可能错误
    
    # 优点
    strengths: List[str] = field(default_factory=list)     # 优点
    
    # 置信度
    confidence: float = 0.5          # 评估置信度


@dataclass
class SemanticGuidanceResult:
    """语义追问结果"""
    questions: List[str]             # 追问列表
    question_types: List[str] = field(default_factory=list)  # 追问类型
    depth: GuidanceDepth = GuidanceDepth.MODERATE  # 追问深度
    
    # 关联信号
    related_signals: List[str] = field(default_factory=list)  # 关联的语义信号
    domain: str = "general"          # 所属领域
    
    # 质量评估
    quality_assessment: Optional[QualityAssessment] = None
    
    # 元数据
    analysis: Optional[ContentAnalysis] = None
    confidence: float = 0.5


# ============== 内容类型识别器 ==============

class ContentTypeDetector:
    """
    内容类型识别器
    
    基于多维度特征识别内容类型
    """
    
    # 代码特征
    CODE_INDICATORS = [
        r'```[\s\S]*?```',           # 代码块
        r'def\s+\w+\s*\(',           # Python 函数
        r'function\s+\w+\s*\(',      # JS 函数
        r'class\s+\w+',             # 类定义
        r'import\s+\w+',             # 导入语句
        r'const\s+\w+\s*=',         # 常量声明
        r'var\s+\w+\s*=',           # 变量声明
        r'let\s+\w+\s*=',           # let 声明
        r'=>\s*{',                  # 箭头函数
        r'if\s*\(.*\)\s*{',         # if 语句
        r'for\s*\(.*\)\s*{',        # for 循环
        r'return\s+',               # 返回语句
    ]
    
    # 数据特征
    DATA_INDICATORS = [
        r'\d+\.\d+%?',              # 百分比
        r'\$\d+',                   # 美元金额
        r'¥\d+',                    # 人民币金额
        r'\d{4}-\d{2}-\d{2}',       # 日期
        r'\|.*\|.*\|',              # Markdown 表格
        r'^\s*\|',                  # 表格行
        r'(同比|环比|增长|下降)',     # 同比环比
        r'(总计|合计|平均|占比)',     # 统计术语
    ]
    
    # 步骤特征
    STEP_INDICATORS = [
        r'第一步|第二步|第三步',
        r'首先|然后|接着|最后',
        r'1\.|2\.|3\.',
        r'\d+\.\s+\w+',
        r'步骤\s*\d+',
        r'流程：',
        r'操作如下：',
    ]
    
    # 对比特征
    COMPARISON_INDICATORS = [
        r'相比|对比|比较',
        r'优于|劣于|不同于',
        r'一方面.*另一方面',
        r'但是|然而|不过',
        r'(A|B)比|比.*更',
        r'差异|区别|不同',
    ]
    
    # 示例特征
    EXAMPLE_INDICATORS = [
        r'例如|比如|举例',
        r'举个例子|打个比方',
        r'比如：|例如：',
        r'假设.*情况',
    ]
    
    # 定义特征
    DEFINITION_INDICATORS = [
        r'是.*指|所谓.*就是',
        r'定义为|含义是',
        r'指的是|表示',
    ]
    
    def __init__(self):
        """初始化识别器"""
        self._compile_patterns()
    
    def _compile_patterns(self):
        """预编译所有模式"""
        self._code_patterns = [re.compile(p) for p in self.CODE_INDICATORS]
        self._data_patterns = [re.compile(p) for p in self.DATA_INDICATORS]
        self._step_patterns = [re.compile(p) for p in self.STEP_INDICATORS]
        self._comparison_patterns = [re.compile(p) for p in self.COMPARISON_INDICATORS]
        self._example_patterns = [re.compile(p) for p in self.EXAMPLE_INDICATORS]
        self._definition_patterns = [re.compile(p) for p in self.DEFINITION_INDICATORS]
    
    def detect(self, content: str) -> Tuple[ContentType, float]:
        """
        检测内容类型
        
        Args:
            content: 内容文本
            
        Returns:
            Tuple[ContentType, float]: 内容类型和置信度
        """
        scores = {
            ContentType.CODE: 0.0,
            ContentType.DATA: 0.0,
            ContentType.TUTORIAL: 0.0,
            ContentType.COMPARISON: 0.0,
            ContentType.DOCUMENTATION: 0.0,
            ContentType.EXPLANATION: 0.0,
            ContentType.ANALYSIS: 0.0,
            ContentType.QUESTION_ANSWER: 0.0,
        }
        
        # 检测代码
        code_matches = sum(1 for p in self._code_patterns if p.search(content))
        scores[ContentType.CODE] = min(code_matches * 0.3, 1.0)
        
        # 检测数据
        data_matches = sum(1 for p in self._data_patterns if p.search(content))
        scores[ContentType.DATA] = min(data_matches * 0.25, 1.0)
        
        # 检测步骤
        step_matches = sum(1 for p in self._step_patterns if p.search(content))
        scores[ContentType.TUTORIAL] = min(step_matches * 0.35, 1.0)
        
        # 检测对比
        comparison_matches = sum(1 for p in self._comparison_patterns if p.search(content))
        scores[ContentType.COMPARISON] = min(comparison_matches * 0.4, 1.0)
        
        # 检测文档
        if len(content) > 500:
            scores[ContentType.DOCUMENTATION] += 0.3
        if '\n\n' in content:
            scores[ContentType.DOCUMENTATION] += 0.2
        
        # 检测解释
        definition_matches = sum(1 for p in self._definition_patterns if p.search(content))
        if definition_matches > 0:
            scores[ContentType.EXPLANATION] = min(definition_matches * 0.4, 0.8)
        
        # 检测问答
        if '？' in content or '?' in content:
            scores[ContentType.QUESTION_ANSWER] += 0.3
        if '答：' in content or '答案：' in content:
            scores[ContentType.QUESTION_ANSWER] += 0.4
        
        # 检测分析
        analysis_keywords = ['分析', '原因', '结果', '影响', '因素']
        analysis_matches = sum(content.count(kw) for kw in analysis_keywords)
        if analysis_matches >= 2:
            scores[ContentType.ANALYSIS] = min(analysis_matches * 0.2, 0.8)
        
        # 找到最高分
        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]
        
        # 如果最高分很低，返回未知
        if best_score < 0.2:
            return ContentType.UNKNOWN, 0.0
        
        return best_type, best_score
    
    def get_semantic_signals(self, content: str) -> Dict[str, bool]:
        """
        获取语义信号
        
        Args:
            content: 内容文本
            
        Returns:
            Dict[str, bool]: 语义信号字典
        """
        return {
            "has_code": any(p.search(content) for p in self._code_patterns),
            "has_data": any(p.search(content) for p in self._data_patterns),
            "has_steps": any(p.search(content) for p in self._step_patterns),
            "has_comparison": any(p.search(content) for p in self._comparison_patterns),
            "has_examples": any(p.search(content) for p in self._example_patterns),
            "has_definitions": any(p.search(content) for p in self._definition_patterns),
        }


# ============== 内容分析器 ==============

class ContentAnalyzer:
    """
    内容分析器
    
    综合分析内容的多维度特征
    """
    
    # 复杂度评估关键词
    COMPLEXITY_INCREASERS = [
        '然而', '但是', '不过', '然而',
        '因此', '所以', '由于', '既然',
        '递归', '迭代', '并发', '异步',
        '多线程', '分布式', '微服务',
    ]
    
    COMPLEXITY_DECREASERS = [
        '简单', '基础', '基本', '首先',
        '简单来说', '换句话说', '也就是说',
    ]
    
    # 技术深度关键词
    TECHNICAL_TERMS = [
        'API', '接口', '架构', '设计模式',
        '算法', '数据结构', '性能', '优化',
        '并发', '缓存', '索引', '事务',
        'OOP', '函数式', '响应式',
    ]
    
    def __init__(self):
        """初始化分析器"""
        self.type_detector = ContentTypeDetector()
    
    def analyze(self, content: str) -> ContentAnalysis:
        """
        分析内容
        
        Args:
            content: 内容文本
            
        Returns:
            ContentAnalysis: 分析结果
        """
        # 类型检测
        content_type, type_confidence = self.type_detector.detect(content)
        
        # 语义信号
        signals = self.type_detector.get_semantic_signals(content)
        
        # 结构分析
        sentences = self._split_sentences(content)
        paragraphs = self._split_paragraphs(content)
        
        # 复杂度评估
        complexity = self._evaluate_complexity(content)
        
        # 技术深度评估
        tech_depth = self._evaluate_technical_depth(content)
        
        # 语言检测
        language = self._detect_language(content)
        
        # 实体提取
        entities = self._extract_entities(content)
        
        # 主题提取
        topics = self._extract_topics(content, content_type)
        
        return ContentAnalysis(
            content_type=content_type,
            confidence=type_confidence,
            has_code=signals['has_code'],
            has_data=signals['has_data'],
            has_steps=signals['has_steps'],
            has_comparison=signals['has_comparison'],
            has_examples=signals['has_examples'],
            has_definitions=signals['has_definitions'],
            has_analysis=content_type == ContentType.ANALYSIS,
            complexity=complexity,
            technical_depth=tech_depth,
            length=len(content),
            sentence_count=len(sentences),
            paragraph_count=len(paragraphs),
            structure_score=self._evaluate_structure(content, sentences, paragraphs),
            entities=entities,
            topics=topics,
            language=language,
        )
    
    def _split_sentences(self, text: str) -> List[str]:
        """拆分句子"""
        # 按中英文句号、问号、感叹号拆分
        sentences = re.split(r'[。！？.?!]', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _split_paragraphs(self, text: str) -> List[str]:
        """拆分段落"""
        paragraphs = text.split('\n\n')
        return [p.strip() for p in paragraphs if p.strip()]
    
    def _evaluate_complexity(self, content: str) -> float:
        """评估复杂度"""
        score = 0.5
        
        # 句子数量（太长可能复杂）
        sentences = self._split_sentences(content)
        if len(sentences) > 20:
            score += 0.1
        elif len(sentences) < 5:
            score -= 0.1
        
        # 关键词影响
        content_lower = content.lower()
        for kw in self.COMPLEXITY_INCREASERS:
            if kw in content_lower:
                score += 0.05
        
        for kw in self.COMPLEXITY_DECREASERS:
            if kw in content_lower:
                score -= 0.05
        
        # 嵌套结构（括号嵌套）
        nested = content.count('(') + content.count('[') + content.count('{')
        if nested > 10:
            score += 0.15
        
        return max(0.0, min(1.0, score))
    
    def _evaluate_technical_depth(self, content: str) -> float:
        """评估技术深度"""
        score = 0.3
        
        content_lower = content.lower()
        tech_count = sum(1 for term in self.TECHNICAL_TERMS if term.lower() in content_lower)
        
        # 技术术语密度
        if tech_count >= 5:
            score = 0.8
        elif tech_count >= 3:
            score = 0.6
        elif tech_count >= 1:
            score = 0.4
        
        # 代码块增加技术深度
        if '```' in content:
            score += 0.1
        
        return min(1.0, score)
    
    def _detect_language(self, content: str) -> str:
        """检测语言"""
        # 简单检测：统计中英文字符比例
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', content))
        english_chars = len(re.findall(r'[a-zA-Z]', content))
        total = chinese_chars + english_chars
        
        if total == 0:
            return 'unknown'
        
        if chinese_chars / total > 0.5:
            return 'zh'
        elif english_chars / total > 0.5:
            return 'en'
        else:
            return 'mixed'
    
    def _extract_entities(self, content: str) -> Dict[str, List[str]]:
        """提取实体"""
        entities = {}
        
        # 文件路径
        file_paths = re.findall(r'[\w/\\.]+\.[\w]+', content)
        if file_paths:
            entities['files'] = list(set(file_paths))[:10]  # 最多10个
        
        # URL
        urls = re.findall(r'https?://[^\s]+', content)
        if urls:
            entities['urls'] = list(set(urls))[:5]
        
        # 代码块中的函数名
        func_names = re.findall(r'(?:def|function|class)\s+(\w+)', content)
        if func_names:
            entities['functions'] = list(set(func_names))[:10]
        
        # 数字（保留关键数字）
        numbers = re.findall(r'\d+(?:\.\d+)?%?', content)
        if len(numbers) > 5:  # 只有数据内容才提取
            entities['numbers'] = numbers[:20]
        
        return entities
    
    def _extract_topics(self, content: str, content_type: ContentType) -> List[str]:
        """提取主题"""
        topics = []
        
        # 基于内容类型的默认主题
        type_topics = {
            ContentType.CODE: ['编程', '代码', '开发'],
            ContentType.DATA: ['数据', '统计', '分析'],
            ContentType.TUTORIAL: ['教程', '指南', '步骤'],
            ContentType.COMPARISON: ['对比', '比较', '分析'],
            ContentType.DOCUMENTATION: ['文档', '说明'],
            ContentType.EXPLANATION: ['解释', '概念', '定义'],
            ContentType.ANALYSIS: ['分析', '研究', '报告'],
            ContentType.QUESTION_ANSWER: ['问答', '解答'],
        }
        
        if content_type in type_topics:
            topics.extend(type_topics[content_type])
        
        # 关键词主题
        keyword_topics = {
            'Python': ['Python', 'Python编程'],
            'JavaScript': ['JavaScript', 'JS'],
            'API': ['API', '接口'],
            '数据库': ['数据库', 'DB'],
            '测试': ['测试', '测试驱动'],
            '部署': ['部署', 'DevOps'],
            '性能': ['性能', '优化'],
            '安全': ['安全', '加密'],
        }
        
        content_lower = content.lower()
        for keyword, topic_list in keyword_topics.items():
            if keyword.lower() in content_lower:
                topics.extend(topic_list)
        
        return list(set(topics))[:5]  # 最多5个主题
    
    def _evaluate_structure(self, content: str, sentences: List[str], paragraphs: List[str]) -> float:
        """评估结构化程度"""
        score = 0.3
        
        # 有明确的段落结构
        if len(paragraphs) >= 3:
            score += 0.2
        elif len(paragraphs) >= 2:
            score += 0.1
        
        # 有列表结构
        list_patterns = [
            r'^\d+\.',           # 数字列表
            r'^[a-zA-Z]\.',      # 字母列表
            r'^[-*]\s',          # 符号列表
        ]
        list_count = sum(
            len(re.findall(p, content, re.MULTILINE))
            for p in list_patterns
        )
        if list_count >= 3:
            score += 0.2
        elif list_count >= 1:
            score += 0.1
        
        # 有代码块
        if '```' in content:
            score += 0.15
        
        # 有表格
        if '|' in content and content.count('|') >= 3:
            score += 0.1
        
        return min(1.0, score)


# ============== 内容质量评估器 ==============

class ContentQualityEvaluator:
    """
    内容质量评估器
    
    评估内容的完整性、准确性、清晰度
    """
    
    # 完整性检查项
    COMPLETENESS_CHECKS = {
        'definition': {
            'patterns': [r'是.*指', r'所谓', r'定义为'],
            'weight': 0.2,
            'issue': '缺少定义或概念解释',
        },
        'example': {
            'patterns': [r'例如', r'比如', r'比如是'],
            'weight': 0.2,
            'issue': '缺少示例',
        },
        'step': {
            'patterns': [r'步骤', r'首先', r'然后', r'最后'],
            'weight': 0.15,
            'issue': '缺少步骤说明',
        },
        'reason': {
            'patterns': [r'因为', r'由于', r'所以', r'因此'],
            'weight': 0.15,
            'issue': '缺少原因解释',
        },
        'limitation': {
            'patterns': [r'但是', r'然而', r'不过', r'限制'],
            'weight': 0.1,
            'issue': '缺少限制或注意事项',
        },
        'alternative': {
            'patterns': [r'也可以', r'另一种', r'或者'],
            'weight': 0.1,
            'issue': '缺少替代方案',
        },
        'summary': {
            'patterns': [r'总之', r'总而言之', r'总结'],
            'weight': 0.1,
            'issue': '缺少总结',
        },
    }
    
    # 清晰度检查
    CLARITY_CHECKS = [
        (r'[\u4e00-\u9fff]{30,}', '段落过长'),  # 中文字符超过30个无断句
        (r'\([^)]{50,}\)', '括号内容过长'),  # 括号内超过50个字符
        (r'\s{3,}', '多余的空行或空格'),
    ]
    
    def __init__(self):
        """初始化评估器"""
        self._compile_checks()
    
    def _compile_checks(self):
        """预编译检查模式"""
        for key, check in self.COMPLETENESS_CHECKS.items():
            check['compiled'] = [re.compile(p) for p in check['patterns']]
    
    def evaluate(
        self,
        content: str,
        content_type: ContentType,
        intent_type: str = ""
    ) -> QualityAssessment:
        """
        评估内容质量
        
        Args:
            content: 内容文本
            content_type: 内容类型
            intent_type: 意图类型
            
        Returns:
            QualityAssessment: 质量评估结果
        """
        # 完整性评估
        completeness, missing = self._evaluate_completeness(content, content_type)
        
        # 准确性评估（简化版）
        accuracy = self._evaluate_accuracy(content)
        
        # 清晰度评估
        clarity, unclear = self._evaluate_clarity(content)
        
        # 识别优点
        strengths = self._identify_strengths(content, content_type)
        
        # 识别可能错误
        potential_errors = self._check_potential_errors(content)
        
        # 综合评分
        quality_score = completeness * 0.4 + accuracy * 0.3 + clarity * 0.3
        quality = self._score_to_quality(quality_score)
        
        return QualityAssessment(
            quality=quality,
            completeness=completeness,
            accuracy=accuracy,
            clarity=clarity,
            missing_info=missing,
            unclear_parts=unclear,
            potential_errors=potential_errors,
            strengths=strengths,
            confidence=0.7,  # 简化版置信度
        )
    
    def _evaluate_completeness(self, content: str, content_type: ContentType) -> Tuple[float, List[str]]:
        """
        评估完整性
        
        Returns:
            Tuple[float, List[str]]: 完整度分数和缺失项列表
        """
        score = 0.0
        missing = []
        
        # 根据内容类型选择检查项
        checks_to_apply = self.COMPLETENESS_CHECKS.copy()
        
        # 不同类型侧重点不同
        if content_type == ContentType.TUTORIAL:
            # 教程类重点检查步骤
            checks_to_apply['step']['weight'] = 0.3
        elif content_type == ContentType.EXPLANATION:
            # 解释类重点检查定义和原因
            checks_to_apply['definition']['weight'] = 0.3
            checks_to_apply['reason']['weight'] = 0.25
        elif content_type == ContentType.CODE:
            # 代码类检查示例和注释
            checks_to_apply['example']['weight'] = 0.25
        
        # 执行检查
        for key, check in checks_to_apply.items():
            if any(p.search(content) for p in check['compiled']):
                score += check['weight']
            else:
                missing.append(check['issue'])
        
        return min(1.0, score), missing
    
    def _evaluate_accuracy(self, content: str) -> float:
        """
        评估准确性
        
        简化版：检查是否有明显的逻辑错误信号
        """
        score = 0.9  # 默认高分
        
        # 检查矛盾信号
        contradiction_signals = [
            (r'但是.*然而', -0.1),  # 但后面跟着然而
            (r'然而.*但是', -0.1),
        ]
        
        for pattern, penalty in contradiction_signals:
            if re.search(pattern, content):
                score += penalty
        
        # 检查不确定信号（可能表示准确性低）
        uncertainty_signals = [
            r'大概', r'可能', r'也许', r'应该.*吧',
        ]
        
        uncertainty_count = sum(len(re.findall(p, content)) for p in uncertainty_signals)
        if uncertainty_count >= 3:
            score -= 0.1
        
        return max(0.5, min(1.0, score))
    
    def _evaluate_clarity(self, content: str) -> Tuple[float, List[str]]:
        """
        评估清晰度
        
        Returns:
            Tuple[float, List[str]]: 清晰度分数和不清晰部分列表
        """
        score = 0.8  # 默认高分
        unclear = []
        
        for pattern, issue in self.CLARITY_CHECKS:
            matches = re.findall(pattern, content)
            if matches:
                unclear.append(f"{issue} ({len(matches)}处)")
                score -= 0.05 * len(matches)
        
        # 检查是否有乱码或异常字符
        if re.search(r'[^\u4e00-\u9fff\w\s.,!?;:()，。！？；：（）、\-\'\"`~@#$%^&*_+=\[\]{}|\\/<>]', content):
            # 有异常字符
            score -= 0.1
        
        return max(0.5, min(1.0, score)), unclear[:5]  # 最多5项
    
    def _identify_strengths(self, content: str, content_type: ContentType) -> List[str]:
        """识别内容优点"""
        strengths = []
        
        # 基于内容特征识别优点
        if content_type == ContentType.TUTORIAL and re.search(r'步骤|首先|然后|最后', content):
            strengths.append('结构清晰，步骤完整')
        
        if content_type == ContentType.EXPLANATION and re.search(r'例如|比如|举例', content):
            strengths.append('有具体示例，易于理解')
        
        if re.search(r'```[\s\S]*?```', content):
            strengths.append('包含代码示例')
        
        if re.search(r'\|.*\|', content):
            strengths.append('有表格或结构化数据')
        
        if re.search(r'但是|然而|不过', content):
            strengths.append('有局限性或注意事项说明')
        
        if len(content) > 500 and content_type == ContentType.ANALYSIS:
            strengths.append('内容详细，分析深入')
        
        return strengths[:5]  # 最多5个优点
    
    def _check_potential_errors(self, content: str) -> List[str]:
        """检查潜在错误"""
        errors = []
        
        # 检查明显的逻辑问题
        # 1. 括号不匹配
        if content.count('(') != content.count(')'):
            errors.append('括号可能不匹配')
        
        # 2. 引号不匹配
        if content.count('"') % 2 != 0:
            errors.append('引号可能不匹配')
        
        # 3. 代码块不匹配
        code_blocks = re.findall(r'```', content)
        if len(code_blocks) % 2 != 0:
            errors.append('代码块可能未正确关闭')
        
        return errors[:3]  # 最多3个
    
    def _score_to_quality(self, score: float) -> ContentQuality:
        """将分数转换为质量等级"""
        if score >= 0.85:
            return ContentQuality.EXCELLENT
        elif score >= 0.7:
            return ContentQuality.GOOD
        elif score >= 0.5:
            return ContentQuality.ADEQUATE
        elif score >= 0.3:
            return ContentQuality.INCOMPLETE
        else:
            return ContentQuality.POOR


# ============== 领域特定追问策略 ==============

class DomainGuidanceStrategies:
    """
    领域特定追问策略
    
    根据内容类型和领域生成针对性追问
    """
    
    # 代码领域追问策略
    CODE_STRATEGY = {
        'has_code': [
            "需要我解释这段代码的原理吗？",
            "需要添加单元测试吗？",
            "需要优化这段代码的性能吗？",
        ],
        'no_example': [
            "需要我提供一个完整的示例吗？",
            "需要我展示更多使用案例吗？",
        ],
        'has_error': [
            "需要我帮你调试这个错误吗？",
            "需要我分析错误原因吗？",
        ],
    }
    
    # 文档领域追问策略
    DOCUMENTATION_STRATEGY = {
        'short': [
            "需要我详细展开说明吗？",
            "需要补充更多细节吗？",
        ],
        'no_structure': [
            "需要我帮你整理成更结构化的格式吗？",
            "需要我添加目录和索引吗？",
        ],
    }
    
    # 数据分析领域追问策略
    DATA_STRATEGY = {
        'has_data': [
            "需要我帮你可视化这些数据吗？",
            "需要我进行更深入的数据分析吗？",
        ],
        'no_conclusion': [
            "需要我总结一下数据的关键发现吗？",
            "需要我提供数据背后的洞察吗？",
        ],
    }
    
    # 教程领域追问策略
    TUTORIAL_STRATEGY = {
        'no_prerequisite': [
            "需要我说明前置条件吗？",
            "需要我介绍相关的背景知识吗？",
        ],
        'no_alternative': [
            "还有其他实现方式需要我介绍吗？",
            "需要我对比不同方案的优缺点吗？",
        ],
    }
    
    # 解释领域追问策略
    EXPLANATION_STRATEGY = {
        'no_example': [
            "需要我举例说明吗？",
            "需要我打个比方帮助理解吗？",
        ],
        'no_depth': [
            "需要我深入解释原理吗？",
            "需要我介绍相关概念吗？",
        ],
    }
    
    @classmethod
    def get_strategy(cls, content_type: ContentType) -> Dict:
        """获取对应内容类型的策略"""
        strategies = {
            ContentType.CODE: cls.CODE_STRATEGY,
            ContentType.DOCUMENTATION: cls.DOCUMENTATION_STRATEGY,
            ContentType.DATA: cls.DATA_STRATEGY,
            ContentType.TUTORIAL: cls.TUTORIAL_STRATEGY,
            ContentType.EXPLANATION: cls.EXPLANATION_STRATEGY,
        }
        return strategies.get(content_type, {})
    
    @classmethod
    def generate_questions(
        cls,
        content_type: ContentType,
        analysis: ContentAnalysis,
        quality: QualityAssessment
    ) -> List[str]:
        """
        根据内容类型和评估生成追问
        
        Args:
            content_type: 内容类型
            analysis: 内容分析结果
            quality: 质量评估结果
            
        Returns:
            List[str]: 追问列表
        """
        questions = []
        strategy = cls.get_strategy(content_type)
        
        if not strategy:
            return questions
        
        # 根据分析结果选择追问
        # 1. 代码相关
        if 'has_code' in strategy and analysis.has_code:
            questions.extend(strategy['has_code'])
        
        if 'no_example' in strategy and not analysis.has_examples:
            questions.extend(strategy['no_example'])
        
        # 2. 数据相关
        if 'has_data' in strategy and analysis.has_data:
            questions.extend(strategy['has_data'])
        
        if 'no_conclusion' in strategy and '总结' not in quality.strengths:
            questions.extend(strategy['no_conclusion'])
        
        # 3. 教程相关
        if 'no_prerequisite' in strategy and analysis.has_steps:
            questions.extend(strategy['no_prerequisite'])
        
        if 'no_alternative' in strategy and not analysis.has_comparison:
            questions.extend(strategy['no_alternative'])
        
        # 4. 解释相关
        if 'no_depth' in strategy and analysis.complexity < 0.5:
            questions.extend(strategy['no_depth'])
        
        # 5. 通用追问（基于质量评估）
        if quality.completeness < 0.6:
            questions.append("需要我补充更多细节吗？")
        
        if quality.clarity < 0.7:
            questions.append("需要我用更简单的方式解释吗？")
        
        # 去重
        return list(dict.fromkeys(questions))[:5]  # 最多5个


# ============== 语义追问生成器 ==============

class SemanticGuidanceGenerator:
    """
    语义追问生成器
    
    基于内容深度分析生成智能追问
    """
    
    # 通用追问模板
    GENERAL_QUESTIONS = {
        'deep': [
            "需要我深入解释这个概念吗？",
            "需要我介绍相关的背景知识吗？",
            "需要我分析这个问题的原因吗？",
        ],
        'wide': [
            "还有其他方面需要了解吗？",
            "需要我介绍相关的知识点吗？",
            "需要我提供更多的案例吗？",
        ],
        'practical': [
            "需要我提供具体的操作步骤吗？",
            "需要我帮你实现这个功能吗？",
            "需要我提供代码示例吗？",
        ],
    }
    
    # 语义信号到追问的映射
    SIGNAL_TO_QUESTION = {
        'has_code': [
            "需要我详细解释这段代码吗？",
            "需要我帮你优化这段代码吗？",
        ],
        'has_data': [
            "需要我帮你可视化这些数据吗？",
            "需要我进行更深入的分析吗？",
        ],
        'has_steps': [
            "需要我详细说明每个步骤吗？",
            "需要我提供更具体的操作指南吗？",
        ],
        'has_comparison': [
            "需要我更详细地对比两者的优缺点吗？",
            "需要我帮你选择更适合的方案吗？",
        ],
        'has_examples': [
            "需要更多这样的例子吗？",
            "需要我举一个实际应用的例子吗？",
        ],
        'has_definitions': [
            "需要我更详细地解释这个概念吗？",
            "需要我介绍相关的术语吗？",
        ],
        'has_analysis': [
            "需要我深入分析这个结论的原因吗？",
            "需要我提供更多的数据支持吗？",
        ],
    }
    
    def __init__(self):
        """初始化生成器"""
        self.analyzer = ContentAnalyzer()
        self.evaluator = ContentQualityEvaluator()
    
    def generate(
        self,
        content: str,
        intent_type: str = "",
        context: Dict[str, Any] = None
    ) -> SemanticGuidanceResult:
        """
        生成语义追问
        
        Args:
            content: 内容文本
            intent_type: 意图类型
            context: 上下文信息
            
        Returns:
            SemanticGuidanceResult: 追问结果
        """
        context = context or {}
        
        # 1. 内容分析
        analysis = self.analyzer.analyze(content)
        
        # 2. 质量评估
        quality = self.evaluator.evaluate(content, analysis.content_type, intent_type)
        
        # 3. 生成追问
        questions = []
        question_types = []
        related_signals = []
        
        # 策略1: 领域特定追问
        domain_questions = DomainGuidanceStrategies.generate_questions(
            analysis.content_type, analysis, quality
        )
        if domain_questions:
            questions.extend(domain_questions)
            question_types.extend(['domain'] * len(domain_questions))
        
        # 策略2: 语义信号追问
        signals = {
            'has_code': analysis.has_code,
            'has_data': analysis.has_data,
            'has_steps': analysis.has_steps,
            'has_comparison': analysis.has_comparison,
            'has_examples': analysis.has_examples,
            'has_definitions': analysis.has_definitions,
            'has_analysis': analysis.has_analysis,
        }
        
        for signal, has_signal in signals.items():
            if has_signal and signal in self.SIGNAL_TO_QUESTION:
                signal_questions = self.SIGNAL_TO_QUESTION[signal]
                questions.extend(signal_questions)
                question_types.extend(['signal'] * len(signal_questions))
                related_signals.append(signal)
        
        # 策略3: 通用追问（根据深度选择）
        depth = self._determine_depth(analysis, quality)
        general_questions = self.GENERAL_QUESTIONS.get(depth.value, [])
        if general_questions:
            questions.extend(general_questions)
            question_types.extend(['general'] * len(general_questions))
        
        # 策略4: 质量改进追问
        if quality.missing_info:
            questions.append("需要我补充哪些内容？")
            question_types.append('quality')
        
        # 去重并限制数量
        questions, question_types = self._deduplicate(questions, question_types)
        questions = questions[:5]
        question_types = question_types[:5]
        
        return SemanticGuidanceResult(
            questions=questions,
            question_types=question_types,
            depth=depth,
            related_signals=related_signals,
            domain=analysis.content_type.value,
            quality_assessment=quality,
            analysis=analysis,
            confidence=self._calculate_confidence(analysis, quality),
        )
    
    def _determine_depth(
        self,
        analysis: ContentAnalysis,
        quality: QualityAssessment
    ) -> GuidanceDepth:
        """确定追问深度"""
        # 基于复杂度和技术深度
        if analysis.complexity > 0.7 or analysis.technical_depth > 0.7:
            return GuidanceDepth.DEEP
        elif analysis.complexity > 0.4 or analysis.technical_depth > 0.4:
            return GuidanceDepth.MODERATE
        else:
            return GuidanceDepth.SURFACE
    
    def _deduplicate(
        self,
        questions: List[str],
        question_types: List[str]
    ) -> Tuple[List[str], List[str]]:
        """去重"""
        seen = set()
        unique_questions = []
        unique_types = []
        
        for q, t in zip(questions, question_types):
            normalized = q.strip().lower()
            if normalized not in seen:
                seen.add(normalized)
                unique_questions.append(q)
                unique_types.append(t)
        
        return unique_questions, unique_types
    
    def _calculate_confidence(
        self,
        analysis: ContentAnalysis,
        quality: QualityAssessment
    ) -> float:
        """计算置信度"""
        # 基于分析置信度和质量评估置信度
        base = 0.5
        base += analysis.confidence * 0.25
        base += quality.confidence * 0.25
        
        # 基于内容长度（太短置信度低）
        if analysis.length < 100:
            base -= 0.1
        elif analysis.length > 500:
            base += 0.1
        
        return max(0.3, min(0.95, base))


# ============== 便捷函数 ==============

def analyze_content(content: str) -> ContentAnalysis:
    """
    快速分析内容
    
    Args:
        content: 内容文本
        
    Returns:
        ContentAnalysis: 分析结果
    """
    analyzer = ContentAnalyzer()
    return analyzer.analyze(content)


def evaluate_quality(
    content: str,
    content_type: ContentType = None,
    intent_type: str = ""
) -> QualityAssessment:
    """
    快速评估内容质量
    
    Args:
        content: 内容文本
        content_type: 内容类型（可选，自动检测）
        intent_type: 意图类型
        
    Returns:
        QualityAssessment: 质量评估结果
    """
    evaluator = ContentQualityEvaluator()
    
    if content_type is None:
        detector = ContentTypeDetector()
        content_type, _ = detector.detect(content)
    
    return evaluator.evaluate(content, content_type, intent_type)


def generate_semantic_guidance(
    content: str,
    intent_type: str = "",
    context: Dict[str, Any] = None
) -> SemanticGuidanceResult:
    """
    快速生成语义追问
    
    Args:
        content: 内容文本
        intent_type: 意图类型
        context: 上下文信息
        
    Returns:
        SemanticGuidanceResult: 追问结果
    """
    generator = SemanticGuidanceGenerator()
    return generator.generate(content, intent_type, context)


# ============== 导出 ==============

__all__ = [
    # 枚举
    'ContentType',
    'ContentQuality',
    'GuidanceDepth',
    # 数据结构
    'ContentAnalysis',
    'QualityAssessment',
    'SemanticGuidanceResult',
    # 分析器
    'ContentTypeDetector',
    'ContentAnalyzer',
    'ContentQualityEvaluator',
    # 生成器
    'DomainGuidanceStrategies',
    'SemanticGuidanceGenerator',
    # 便捷函数
    'analyze_content',
    'evaluate_quality',
    'generate_semantic_guidance',
]
