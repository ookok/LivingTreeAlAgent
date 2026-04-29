"""
认知框架协作者 (Cognitive Framework Collaborator)

核心设计理念：
1. 逆向构建框架：从时间轴（纵向）和比较轴（横向）两个维度搭建认知骨架
2. 坚守能力圈：输出清晰可靠的框架、脉络和对比，而非无法验证的深度专业细节
3. 效率与深度的平衡：先搭建全局认知框架，再标注关键节点和存疑点
4. 对抗认知偏差：通过时间线和对比轴补全认知盲区
5. 积累元能力：持续优化"如何高效认知一个新领域"的元方法
"""

import re
import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict
import os


# ==================== 数据模型 ====================

class QuestionType(Enum):
    """问题类型枚举"""
    CONCEPTUAL = "conceptual"           # 概念理解型
    PROCEDURAL = "procedural"            # 流程操作型
    COMPARATIVE = "comparative"         # 比较分析型
    CAUSAL = "causal"                   # 因果关系型
    EVALUATIVE = "evaluative"           # 评价判断型
    HISTORICAL = "historical"           # 历史演变型
    TECHNICAL = "technical"             # 技术细节型
    PRACTICAL = "practical"             # 实践应用型
    UNKNOWN = "unknown"                  # 未知类型


class DomainCategory(Enum):
    """领域分类枚举"""
    TECHNOLOGY = "technology"           # 科技
    SCIENCE = "science"                 # 科学
    BUSINESS = "business"               # 商业
    ECONOMICS = "economics"             # 经济
    FINANCE = "finance"                 # 金融
    LAW = "law"                         # 法律
    HISTORY = "history"                 # 历史
    CULTURE = "culture"                 # 文化
    PHILOSOPHY = "philosophy"           # 哲学
    MEDICINE = "medicine"               # 医学
    EDUCATION = "education"             # 教育
    ARTS = "arts"                       # 艺术
    SOCIAL = "social"                   # 社会
    POLITICS = "politics"               # 政治
    OTHER = "other"                     # 其他


class ConfidenceLevel(Enum):
    """置信度等级"""
    HIGH = "high"          # 高置信度 (>0.85)
    MEDIUM = "medium"      # 中置信度 (0.5-0.85)
    LOW = "low"            # 低置信度 (<0.5)
    UNCERTAIN = "uncertain" # 不确定


class NodeStatus(Enum):
    """认知节点状态"""
    VERIFIED = "verified"          # 已验证
    LIKELY = "likely"             # 可能是
    POSSIBLE = "possible"         # 可能是（存疑）
    CONTROVERSIAL = "controversial" # 有争议
    UNKNOWN = "unknown"           # 未知


@dataclass
class TimeAxisNode:
    """时间轴节点"""
    period: str                    # 时期/阶段名称
    start_year: Optional[int]      # 开始年份
    end_year: Optional[int]        # 结束年份
    key_events: List[str]           # 关键事件
    characteristics: List[str]      # 阶段特征
    significance: str               # 重要性描述
    confidence: ConfidenceLevel     # 置信度
    notes: str = ""                # 备注说明


@dataclass
class ComparisonAxisNode:
    """比较轴节点"""
    dimension: str                 # 比较维度
    subject_a: str                 # 比较对象A
    subject_b: str                 # 比较对象B
    a_features: Dict[str, str]     # A的特征
    b_features: Dict[str, str]     # B的特征
    key_difference: str            # 核心差异
    similarity: str                # 共同点
    confidence: ConfidenceLevel    # 置信度
    source_hint: str = ""          # 信息来源提示


@dataclass
class CognitiveNode:
    """认知地图节点"""
    id: str
    title: str                     # 节点标题
    content: str                   # 节点内容
    node_type: str                 # 节点类型: core/key/expand/risk/unknown
    status: NodeStatus              # 节点状态
    confidence: ConfidenceLevel    # 置信度
    priority: int                   # 优先级 1-5
    tags: List[str]                # 标签
    references: List[str]          # 参考资料
    verification_hint: str = ""    # 验证建议
    children: List[str] = field(default_factory=list)  # 子节点ID列表


@dataclass
class CognitiveFramework:
    """认知框架"""
    id: str
    question: str                  # 原始问题
    question_type: QuestionType    # 问题类型
    domain: DomainCategory         # 所属领域
    
    # 时间轴（纵向）
    time_axis: List[TimeAxisNode]  # 时间轴节点列表
    
    # 比较轴（横向）
    comparison_axis: List[ComparisonAxisNode]  # 比较轴节点列表
    
    # 认知地图
    cognitive_map: Dict[str, CognitiveNode]  # 认知节点字典
    
    # 核心结论
    core_conclusion: str           # 核心结论
    key_insights: List[str]       # 关键洞察
    risk_areas: List[str]          # 风险区域/存疑点
    
    # 元信息
    confidence_overall: float      # 整体置信度
    created_at: str                # 创建时间
    exploration_guide: str = ""    # 探索引导
    
    # 统计信息
    total_nodes: int = 0
    verified_nodes: int = 0
    uncertain_nodes: int = 0


@dataclass
class MetaMethod:
    """元方法记录"""
    id: str
    domain: str                    # 领域
    pattern: str                   # 认知模式
    effectiveness: float          # 有效性评分
    success_count: int             # 成功次数
    total_count: int              # 总使用次数
    notes: str                    # 备注
    last_used: str                 # 最后使用时间
    improvement_hints: List[str]   # 改进建议


@dataclass
class FrameworkAnalysis:
    """框架分析结果"""
    question_type: QuestionType
    domain: DomainCategory
    key_concepts: List[str]
    implied_comparison: bool       # 是否暗示需要比较
    implied_history: bool          # 是否暗示需要历史
    implied_depth: int              # 需要的深度等级 1-5
    implied_breadth: int           # 需要的广度等级 1-5


# ==================== 核心引擎 ====================

class CognitiveFrameworkAnalyzer:
    """
    认知框架分析器
    分析用户问题，识别类型和领域，构建认知框架
    """
    
    # 问题类型关键词映射
    QUESTION_TYPE_PATTERNS = {
        QuestionType.CONCEPTUAL: [
            r"什么是", r"什么叫", r"是什么", r"概念", r"定义", r"本质",
            r"含义", r"内涵", r"核心思想", r"基本原理"
        ],
        QuestionType.PROCEDURAL: [
            r"怎么做", r"如何", r"步骤", r"流程", r"方法",
            r"操作", r"实现", r"使用", r"应用"
        ],
        QuestionType.COMPARATIVE: [
            r"比较", r"区别", r"差异", r"不同", r"对比",
            r"vs", r"versus", r"哪个好", r"优劣", r"相比"
        ],
        QuestionType.CAUSAL: [
            r"为什么", r"原因", r"因为", r"导致", r"因果",
            r"影响", r"结果", r"因素", r"机制"
        ],
        QuestionType.EVALUATIVE: [
            r"评价", r"判断", r"评估", r"好不好", r"如何看",
            r"分析", r"优缺点", r"利弊", r"应该"
        ],
        QuestionType.HISTORICAL: [
            r"历史", r"演变", r"发展", r"起源", r"过去",
            r"历程", r"变化", r"进化", r"前世今生"
        ],
        QuestionType.TECHNICAL: [
            r"技术", r"原理", r"架构", r"实现", r"算法",
            r"协议", r"机制", r"系统", r"代码"
        ],
        QuestionType.PRACTICAL: [
            r"实践", r"案例", r"例子", r"应用", r"场景",
            r"经验", r"技巧", r"建议", r"注意"
        ]
    }
    
    # 领域分类关键词映射
    DOMAIN_PATTERNS = {
        DomainCategory.TECHNOLOGY: [
            r"软件", r"硬件", r"编程", r"代码", r"算法", r"数据",
            r"AI", r"人工智能", r"机器学习", r"深度学习", r"互联网"
        ],
        DomainCategory.FINANCE: [
            r"股票", r"债券", r"基金", r"投资", r"理财", r"金融",
            r"银行", r"保险", r"期货", r"期权", r"汇率"
        ],
        DomainCategory.BUSINESS: [
            r"商业", r"企业", r"公司", r"管理", r"运营", r"营销",
            r"品牌", r"战略", r"创业", r"商业模式"
        ],
        DomainCategory.ECONOMICS: [
            r"经济", r"GDP", r"CPI", r"通胀", r"紧缩", r"宏观",
            r"微观", r"市场", r"供需", r"政策"
        ],
        DomainCategory.SCIENCE: [
            r"物理", r"化学", r"生物", r"天文", r"地理", r"科学",
            r"实验", r"研究", r"理论"
        ],
        DomainCategory.LAW: [
            r"法律", r"法规", r"条例", r"规定", r"司法", r"判决",
            r"权利", r"义务", r"合同", r"协议"
        ],
        DomainCategory.HISTORY: [
            r"历史", r"朝代", r"战争", r"革命", r"事件", r"人物",
            r"古代", r"近代", r"现代"
        ],
        DomainCategory.MEDICINE: [
            r"医学", r"疾病", r"治疗", r"药物", r"健康", r"医疗",
            r"诊断", r"预防", r"保健"
        ],
        DomainCategory.PHILOSOPHY: [
            r"哲学", r"思想", r"主义", r"理论", r"观点", r"认识",
            r"存在", r"价值", r"伦理"
        ]
    }
    
    def __init__(self):
        self._analysis_cache = {}
    
    def analyze(self, question: str) -> FrameworkAnalysis:
        """
        分析问题，返回框架分析结果
        
        Args:
            question: 用户问题
            
        Returns:
            FrameworkAnalysis: 框架分析结果
        """
        # 清理问题文本
        clean_question = question.strip()
        
        # 识别问题类型
        question_type = self._identify_question_type(clean_question)
        
        # 识别领域
        domain = self._identify_domain(clean_question)
        
        # 提取关键概念
        key_concepts = self._extract_key_concepts(clean_question)
        
        # 判断是否需要比较
        implied_comparison = self._check_implied_comparison(clean_question)
        
        # 判断是否需要历史
        implied_history = self._check_implied_history(clean_question)
        
        # 评估深度和广度需求
        depth, breadth = self._estimate_depth_breadth(clean_question, question_type)
        
        return FrameworkAnalysis(
            question_type=question_type,
            domain=domain,
            key_concepts=key_concepts,
            implied_comparison=implied_comparison,
            implied_history=implied_history,
            implied_depth=depth,
            implied_breadth=breadth
        )
    
    def _identify_question_type(self, question: str) -> QuestionType:
        """识别问题类型"""
        scores = {}
        
        for qtype, patterns in self.QUESTION_TYPE_PATTERNS.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, question):
                    score += 1
            scores[qtype] = score
        
        # 返回得分最高的类型
        if max(scores.values()) > 0:
            return max(scores, key=scores.get)
        return QuestionType.UNKNOWN
    
    def _identify_domain(self, question: str) -> DomainCategory:
        """识别领域分类"""
        scores = {}
        
        for domain, patterns in self.DOMAIN_PATTERNS.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, question):
                    score += 1
            scores[domain] = score
        
        if max(scores.values()) > 0:
            return max(scores, key=scores.get)
        return DomainCategory.OTHER
    
    def _extract_key_concepts(self, question: str) -> List[str]:
        """提取关键概念"""
        # 移除常见停用词
        stop_words = {"的", "是", "了", "在", "和", "与", "或", "如何", "怎么", "什么", "为什么", "哪个"}
        
        # 简单分词（基于标点和空格）
        words = re.split(r'[,，\s]+', question)
        
        # 过滤停用词和短词
        concepts = [w for w in words if w not in stop_words and len(w) >= 2]
        
        # 去重并返回
        return list(dict.fromkeys(concepts))[:10]
    
    def _check_implied_comparison(self, question: str) -> bool:
        """检查是否暗示需要比较"""
        comparison_indicators = [
            r"比较", r"区别", r"差异", r"不同", r"对比",
            r"vs", r"和.*哪个", r".*还是.*", r"相比"
        ]
        return any(re.search(p, question) for p in comparison_indicators)
    
    def _check_implied_history(self, question: str) -> bool:
        """检查是否暗示需要历史"""
        history_indicators = [
            r"历史", r"演变", r"发展", r"起源", r"过去",
            r"历程", r"变化", r"进化", r"前世今生", r"由来"
        ]
        return any(re.search(p, question) for p in history_indicators)
    
    def _estimate_depth_breadth(self, question: str, qtype: QuestionType) -> Tuple[int, int]:
        """估计需要的深度和广度"""
        # 基于问题类型估计
        type_estimates = {
            QuestionType.CONCEPTUAL: (3, 2),
            QuestionType.PROCEDURAL: (4, 2),
            QuestionType.COMPARATIVE: (2, 4),
            QuestionType.CAUSAL: (4, 3),
            QuestionType.EVALUATIVE: (3, 4),
            QuestionType.HISTORICAL: (5, 3),
            QuestionType.TECHNICAL: (4, 2),
            QuestionType.PRACTICAL: (3, 3),
            QuestionType.UNKNOWN: (2, 2)
        }
        
        base_depth, base_breadth = type_estimates.get(qtype, (2, 2))
        
        # 基于问题长度调整
        length_factor = min(len(question) / 100, 1.5)
        
        # 基于问号数量调整（可能有多个子问题）
        question_marks = question.count('？') + question.count('?')
        
        return (
            min(int(base_depth * length_factor), 5),
            min(base_breadth + question_marks, 5)
        )


class TimeAxisBuilder:
    """
    时间轴构建器
    负责构建纵向（历时）认知框架
    """
    
    def __init__(self):
        self._timeline_templates = self._load_timeline_templates()
    
    def _load_timeline_templates(self) -> Dict[str, Dict]:
        """加载时间轴模板"""
        return {
            "generic": {
                "early_stage": {"duration": "早期", "key_points": ["起源", "萌芽"]},
                "development": {"duration": "发展期", "key_points": ["快速成长", "标准形成"]},
                "maturity": {"duration": "成熟期", "key_points": ["稳定", "完善"]},
                "modern": {"duration": "当代", "key_points": ["创新", "变革"]}
            }
        }
    
    def build_time_axis(
        self,
        topic: str,
        domain: DomainCategory,
        depth: int = 3
    ) -> List[TimeAxisNode]:
        """
        构建时间轴
        
        Args:
            topic: 主题
            domain: 领域
            depth: 深度等级 1-5
            
        Returns:
            List[TimeAxisNode]: 时间轴节点列表
        """
        # 根据领域和深度构建时间轴
        if domain == DomainCategory.TECHNOLOGY:
            return self._build_tech_timeline(topic, depth)
        elif domain == DomainCategory.HISTORY:
            return self._build_history_timeline(topic, depth)
        elif domain == DomainCategory.SCIENCE:
            return self._build_science_timeline(topic, depth)
        elif domain == DomainCategory.FINANCE:
            return self._build_finance_timeline(topic, depth)
        else:
            return self._build_generic_timeline(topic, depth)
    
    def _build_tech_timeline(self, topic: str, depth: int) -> List[TimeAxisNode]:
        """构建科技领域时间轴"""
        nodes = [
            TimeAxisNode(
                period="理论萌芽期",
                start_year=1940,
                end_year=1970,
                key_events=[
                    "基础理论研究",
                    "概念提出"
                ],
                characteristics=[
                    "以理论研究为主",
                    "实践应用有限"
                ],
                significance="为后续发展奠定理论基础",
                confidence=ConfidenceLevel.MEDIUM
            ),
            TimeAxisNode(
                period="技术突破期",
                start_year=1970,
                end_year=2000,
                key_events=[
                    "关键技术突破",
                    "原型系统出现"
                ],
                characteristics=[
                    "从理论走向实践",
                    "技术路线逐渐清晰"
                ],
                significance="证明技术可行性",
                confidence=ConfidenceLevel.MEDIUM
            ),
            TimeAxisNode(
                period="应用扩展期",
                start_year=2000,
                end_year=2020,
                key_events=[
                    "大规模应用开始",
                    "生态系统形成"
                ],
                characteristics=[
                    "应用场景不断拓展",
                    "产业生态逐步完善"
                ],
                significance="从实验室走向千家万户",
                confidence=ConfidenceLevel.HIGH
            )
        ]
        
        if depth >= 4:
            nodes.append(
                TimeAxisNode(
                    period="智能进化期",
                    start_year=2020,
                    end_year=None,
                    key_events=[
                        "AI赋能",
                        "跨领域融合"
                    ],
                    characteristics=[
                        "智能化程度提升",
                        "与其他技术融合"
                    ],
                    significance="开启新一轮创新浪潮",
                    confidence=ConfidenceLevel.LOW,
                    notes="⚠️ 未来发展存在不确定性"
                )
            )
        
        return nodes
    
    def _build_history_timeline(self, topic: str, depth: int) -> List[TimeAxisNode]:
        """构建历史领域时间轴"""
        return [
            TimeAxisNode(
                period="起源阶段",
                start_year=None,
                end_year=None,
                key_events=["历史起源待考"],
                characteristics=["资料有限"],
                significance="追溯根源",
                confidence=ConfidenceLevel.UNCERTAIN,
                notes="建议查阅专业史料"
            ),
            TimeAxisNode(
                period="形成期",
                start_year=None,
                end_year=None,
                key_events=["重要发展阶段"],
                characteristics=["特征逐渐形成"],
                significance="奠定后续发展基础",
                confidence=ConfidenceLevel.MEDIUM
            ),
            TimeAxisNode(
                period="成熟期",
                start_year=None,
                end_year=None,
                key_events=["高峰期"],
                characteristics=["制度化、规范化"],
                significance="达到历史高峰",
                confidence=ConfidenceLevel.MEDIUM
            ),
            TimeAxisNode(
                period="当代转型",
                start_year=None,
                end_year=datetime.now().year,
                key_events=["现代转型"],
                characteristics=["适应新环境"],
                significance="历史的新篇章",
                confidence=ConfidenceLevel.HIGH
            )
        ][:depth]
    
    def _build_science_timeline(self, topic: str, depth: int) -> List[TimeAxisNode]:
        """构建科学领域时间轴"""
        return [
            TimeAxisNode(
                period="观察发现期",
                start_year=None,
                end_year=None,
                key_events=["现象观察", "数据收集"],
                characteristics=["描述性研究"],
                significance="积累第一手资料",
                confidence=ConfidenceLevel.HIGH
            ),
            TimeAxisNode(
                period="理论建构期",
                start_year=None,
                end_year=None,
                key_events=["假说提出", "理论建构"],
                characteristics=["解释性研究"],
                significance="形成理论框架",
                confidence=ConfidenceLevel.MEDIUM
            ),
            TimeAxisNode(
                period="实验验证期",
                start_year=None,
                end_year=None,
                key_events=["实验设计", "验证检验"],
                characteristics=["实证研究"],
                significance="检验理论正确性",
                confidence=ConfidenceLevel.HIGH
            ),
            TimeAxisNode(
                period="应用拓展期",
                start_year=None,
                end_year=None,
                key_events=["技术转化", "应用推广"],
                characteristics=["应用研究"],
                significance="服务社会需求",
                confidence=ConfidenceLevel.MEDIUM
            )
        ][:depth]
    
    def _build_finance_timeline(self, topic: str, depth: int) -> List[TimeAxisNode]:
        """构建金融领域时间轴"""
        return [
            TimeAxisNode(
                period="传统阶段",
                start_year=1900,
                end_year=1980,
                key_events=["传统业务模式", "监管框架形成"],
                characteristics=["相对稳定", "监管主导"],
                significance="奠定现代金融基础",
                confidence=ConfidenceLevel.HIGH
            ),
            TimeAxisNode(
                period="自由化阶段",
                start_year=1980,
                end_year=2008,
                key_events=["金融创新", "市场扩张"],
                characteristics=["放松管制", "产品多样化"],
                significance="推动金融快速发展",
                confidence=ConfidenceLevel.HIGH
            ),
            TimeAxisNode(
                period="监管强化期",
                start_year=2008,
                end_year=2020,
                key_events=["金融危机", "监管改革"],
                characteristics=["风险意识增强", "监管收紧"],
                significance="重塑金融监管框架",
                confidence=ConfidenceLevel.HIGH
            ),
            TimeAxisNode(
                period="数字化转型",
                start_year=2020,
                end_year=None,
                key_events=["金融科技", "数字化转型"],
                characteristics=["技术驱动", "业务创新"],
                significance="金融业态深刻变革",
                confidence=ConfidenceLevel.MEDIUM,
                notes="⚠️ 发展趋势仍在演进中"
            )
        ][:depth]
    
    def _build_generic_timeline(self, topic: str, depth: int) -> List[TimeAxisNode]:
        """构建通用时间轴"""
        return [
            TimeAxisNode(
                period="起源",
                start_year=None,
                end_year=None,
                key_events=["开始形成"],
                characteristics=["初始状态"],
                significance="追溯源头",
                confidence=ConfidenceLevel.MEDIUM
            ),
            TimeAxisNode(
                period="发展",
                start_year=None,
                end_year=None,
                key_events=["逐步发展"],
                characteristics=["成长壮大"],
                significance="积累势能",
                confidence=ConfidenceLevel.MEDIUM
            ),
            TimeAxisNode(
                period="成熟",
                start_year=None,
                end_year=None,
                key_events=["达到成熟"],
                characteristics=["体系完善"],
                significance="形成稳定格局",
                confidence=ConfidenceLevel.HIGH
            )
        ][:depth]


class ComparisonAxisBuilder:
    """
    比较轴构建器
    负责构建横向（共时）认知框架
    """
    
    def __init__(self):
        self._comparison_templates = self._load_comparison_templates()
    
    def _load_comparison_templates(self) -> Dict:
        """加载比较模板"""
        return {
            "tech": {
                "dimensions": ["性能", "成本", "易用性", "生态", "前景"]
            },
            "business": {
                "dimensions": ["市场规模", "增长速度", "盈利模式", "竞争格局", "进入壁垒"]
            },
            "concept": {
                "dimensions": ["定义", "特点", "优缺点", "适用场景", "与其他概念的关系"]
            }
        }
    
    def build_comparison_axis(
        self,
        subject_a: str,
        subject_b: str,
        dimension: str = "general",
        domain: DomainCategory = DomainCategory.OTHER
    ) -> List[ComparisonAxisNode]:
        """
        构建比较轴
        
        Args:
            subject_a: 比较对象A
            subject_b: 比较对象B
            dimension: 比较维度
            domain: 领域
            
        Returns:
            List[ComparisonAxisNode]: 比较轴节点列表
        """
        # 根据领域选择比较维度
        dimensions = self._get_domain_dimensions(domain)
        
        nodes = []
        for dim in dimensions:
            node = ComparisonAxisNode(
                dimension=dim,
                subject_a=subject_a,
                subject_b=subject_b,
                a_features={},
                b_features={},
                key_difference=f"{dim}维度的核心差异",
                similarity=f"{dim}维度的共同点",
                confidence=ConfidenceLevel.MEDIUM,
                source_hint="建议查阅官方文档或权威资料"
            )
            nodes.append(node)
        
        return nodes
    
    def _get_domain_dimensions(self, domain: DomainCategory) -> List[str]:
        """获取领域特定的比较维度"""
        domain_dimensions = {
            DomainCategory.TECHNOLOGY: ["技术原理", "性能表现", "开发成本", "生态系统", "发展趋势"],
            DomainCategory.FINANCE: ["收益水平", "风险特征", "流动性", "门槛要求", "监管环境"],
            DomainCategory.BUSINESS: ["市场规模", "增长潜力", "盈利模式", "竞争态势", "核心资源"],
            DomainCategory.SCIENCE: ["研究方法", "理论深度", "实证支持", "应用范围", "发展前景"],
            DomainCategory.OTHER: ["定义", "特点", "优缺点", "适用场景", "发展趋势"]
        }
        return domain_dimensions.get(domain, domain_dimensions[DomainCategory.OTHER])


class CognitiveMapGenerator:
    """
    认知地图生成器
    整合时间轴和比较轴，生成认知地图
    """
    
    def __init__(self):
        self._node_counter = 0
    
    def generate_cognitive_map(
        self,
        framework: CognitiveFramework,
        analysis: FrameworkAnalysis
    ) -> Dict[str, CognitiveNode]:
        """
        生成认知地图
        
        Args:
            framework: 认知框架
            analysis: 框架分析
            
        Returns:
            Dict[str, CognitiveNode]: 认知节点字典
        """
        nodes = {}
        
        # 1. 创建核心节点
        core_node = self._create_core_node(framework, analysis)
        nodes[core_node.id] = core_node
        
        # 2. 创建时间轴节点
        for i, time_node in enumerate(framework.time_axis):
            map_node = self._create_time_map_node(time_node, core_node.id, i)
            nodes[map_node.id] = map_node
            core_node.children.append(map_node.id)
        
        # 3. 创建比较轴节点
        for i, comp_node in enumerate(framework.comparison_axis):
            map_node = self._create_comparison_map_node(comp_node, core_node.id, i)
            nodes[map_node.id] = map_node
            core_node.children.append(map_node.id)
        
        # 4. 创建风险节点
        for risk in framework.risk_areas:
            risk_node = self._create_risk_node(risk, core_node.id)
            nodes[risk_node.id] = risk_node
            core_node.children.append(risk_node.id)
        
        return nodes
    
    def _create_core_node(
        self,
        framework: CognitiveFramework,
        analysis: FrameworkAnalysis
    ) -> CognitiveNode:
        """创建核心节点"""
        return CognitiveNode(
            id="core_0",
            title=f"【核心】{analysis.key_concepts[0] if analysis.key_concepts else '主题'}",
            content=framework.core_conclusion,
            node_type="core",
            status=NodeStatus.VERIFIED,
            confidence=ConfidenceLevel.HIGH if framework.confidence_overall > 0.7 else ConfidenceLevel.MEDIUM,
            priority=1,
            tags=["核心概念", framework.domain.value],
            references=[],
            verification_hint=""
        )
    
    def _create_time_map_node(
        self,
        time_node: TimeAxisNode,
        parent_id: str,
        index: int
    ) -> CognitiveNode:
        """创建时间轴映射节点"""
        content = f"**{time_node.period}**"
        if time_node.start_year:
            content += f" ({time_node.start_year}"
            if time_node.end_year:
                content += f"-{time_node.end_year}"
            content += ")"
        content += f"\n\n特点: {', '.join(time_node.characteristics[:2])}"
        content += f"\n关键: {', '.join(time_node.key_events[:2])}"
        if time_node.notes:
            content += f"\n\n{time_node.notes}"
        
        return CognitiveNode(
            id=f"time_{index}",
            title=f"📅 {time_node.period}",
            content=content,
            node_type="key" if time_node.significance else "expand",
            status=NodeStatus.LIKELY if time_node.confidence == ConfidenceLevel.HIGH else NodeStatus.POSSIBLE,
            confidence=time_node.confidence,
            priority=2 if "核心" in time_node.significance or "基础" in time_node.significance else 3,
            tags=["时间轴", time_node.period],
            references=[],
            verification_hint="建议查阅该时期的历史资料"
        )
    
    def _create_comparison_map_node(
        self,
        comp_node: ComparisonAxisNode,
        parent_id: str,
        index: int
    ) -> CognitiveNode:
        """创建比较轴映射节点"""
        content = f"**{comp_node.dimension}**\n\n"
        content += f"| 维度 | {comp_node.subject_a} | {comp_node.subject_b} |\n"
        content += f"|------|------|------|\n"
        content += f"| 特征 | 待填充 | 待填充 |\n\n"
        content += f"**核心差异**: {comp_node.key_difference}\n"
        content += f"**共同点**: {comp_node.similarity}\n\n"
        content += f"⚠️ *{comp_node.source_hint}*"
        
        return CognitiveNode(
            id=f"comp_{index}",
            title=f"⚖️ {comp_node.dimension}",
            content=content,
            node_type="key",
            status=NodeStatus.POSSIBLE,
            confidence=comp_node.confidence,
            priority=2,
            tags=["比较", comp_node.dimension],
            references=[],
            verification_hint=comp_node.source_hint
        )
    
    def _create_risk_node(
        self,
        risk: str,
        parent_id: str
    ) -> CognitiveNode:
        """创建风险节点"""
        return CognitiveNode(
            id=f"risk_{hash(risk) % 10000}",
            title=f"⚠️ {risk}",
            content=f"此区域存在不确定性或认知盲区：\n\n{risk}\n\n**建议**: 进行交叉验证，查阅权威资料",
            node_type="risk",
            status=NodeStatus.CONTROVERSIAL,
            confidence=ConfidenceLevel.LOW,
            priority=5,
            tags=["风险", "存疑"],
            references=[],
            verification_hint="建议咨询专家或查阅多方资料"
        )


class FrameworkGenerator:
    """
    认知框架生成器
    整合所有组件，生成完整的认知框架
    """
    
    def __init__(self):
        self.analyzer = CognitiveFrameworkAnalyzer()
        self.time_builder = TimeAxisBuilder()
        self.comp_builder = ComparisonAxisBuilder()
        self.map_generator = CognitiveMapGenerator()
        self._framework_id = 0
    
    def generate_framework(
        self,
        question: str,
        comparison_subjects: Optional[Tuple[str, str]] = None
    ) -> CognitiveFramework:
        """
        生成认知框架
        
        Args:
            question: 用户问题
            comparison_subjects: (可选) 比较对象元组 (A, B)
            
        Returns:
            CognitiveFramework: 认知框架
        """
        self._framework_id += 1
        
        # 1. 分析问题
        analysis = self.analyzer.analyze(question)
        
        # 2. 构建时间轴
        time_axis = []
        if analysis.implied_history or analysis.question_type in [
            QuestionType.HISTORICAL, QuestionType.TECHNICAL
        ]:
            time_axis = self.time_builder.build_time_axis(
                question,
                analysis.domain,
                depth=analysis.implied_depth
            )
        
        # 3. 构建比较轴
        comparison_axis = []
        if analysis.implied_comparison and comparison_subjects:
            subject_a, subject_b = comparison_subjects
            comparison_axis = self.comp_builder.build_comparison_axis(
                subject_a,
                subject_b,
                domain=analysis.domain
            )
        
        # 4. 生成核心结论
        core_conclusion = self._generate_core_conclusion(question, analysis)
        
        # 5. 生成关键洞察
        key_insights = self._generate_key_insights(analysis, time_axis, comparison_axis)
        
        # 6. 识别风险区域
        risk_areas = self._identify_risk_areas(analysis, time_axis, comparison_axis)
        
        # 7. 生成探索引导
        exploration_guide = self._generate_exploration_guide(
            question, analysis, risk_areas
        )
        
        # 8. 计算整体置信度
        confidence = self._calculate_overall_confidence(
            analysis, time_axis, comparison_axis
        )
        
        # 9. 创建框架对象
        framework = CognitiveFramework(
            id=f"cf_{self._framework_id}",
            question=question,
            question_type=analysis.question_type,
            domain=analysis.domain,
            time_axis=time_axis,
            comparison_axis=comparison_axis,
            cognitive_map={},
            core_conclusion=core_conclusion,
            key_insights=key_insights,
            risk_areas=risk_areas,
            confidence_overall=confidence,
            created_at=datetime.now().isoformat(),
            exploration_guide=exploration_guide
        )
        
        # 10. 生成认知地图
        framework.cognitive_map = self.map_generator.generate_cognitive_map(
            framework, analysis
        )
        
        # 11. 更新统计
        framework.total_nodes = len(framework.cognitive_map)
        framework.verified_nodes = sum(
            1 for n in framework.cognitive_map.values()
            if n.status == NodeStatus.VERIFIED
        )
        framework.uncertain_nodes = sum(
            1 for n in framework.cognitive_map.values()
            if n.status in [NodeStatus.POSSIBLE, NodeStatus.CONTROVERSIAL, NodeStatus.UNKNOWN]
        )
        
        return framework
    
    def _generate_core_conclusion(
        self,
        question: str,
        analysis: FrameworkAnalysis
    ) -> str:
        """生成核心结论"""
        domain_desc = {
            DomainCategory.TECHNOLOGY: "技术领域",
            DomainCategory.FINANCE: "金融领域",
            DomainCategory.BUSINESS: "商业领域",
            DomainCategory.SCIENCE: "科学领域",
            DomainCategory.OTHER: "相关领域"
        }
        
        type_desc = {
            QuestionType.CONCEPTUAL: "概念理解",
            QuestionType.PROCEDURAL: "方法流程",
            QuestionType.COMPARATIVE: "比较分析",
            QuestionType.CAUSAL: "因果关系",
            QuestionType.EVALUATIVE: "评价判断",
            QuestionType.HISTORICAL: "历史演变",
            QuestionType.TECHNICAL: "技术细节",
            QuestionType.PRACTICAL: "实践应用"
        }
        
        return (
            f"这是一个{type_desc.get(analysis.question_type, '综合性')}问题，"
            f"属于{domain_desc.get(analysis.domain, '一般')}。\n\n"
            f"我将为您搭建一个包含{'时间轴(纵向)' if analysis.implied_history else ''}"
            f"{'和' if analysis.implied_history and analysis.implied_comparison else ''}"
            f"{'比较轴(横向)' if analysis.implied_comparison else ''}的认知框架。"
        )
    
    def _generate_key_insights(
        self,
        analysis: FrameworkAnalysis,
        time_axis: List[TimeAxisNode],
        comparison_axis: List[ComparisonAxisNode]
    ) -> List[str]:
        """生成关键洞察"""
        insights = []
        
        # 基于问题类型的洞察
        if analysis.question_type == QuestionType.CONCEPTUAL:
            insights.append("这个问题涉及核心概念，建议先理解基本定义")
        elif analysis.question_type == QuestionType.COMPARATIVE:
            insights.append("这是一个比较型问题，需要从多维度进行横向对比")
        elif analysis.question_type == QuestionType.HISTORICAL:
            insights.append("这是历史演变问题，需要关注时间线上的关键节点")
        
        # 基于领域的洞察
        if analysis.domain == DomainCategory.TECHNOLOGY:
            insights.append("技术领域变化快，需要关注最新发展趋势")
        elif analysis.domain == DomainCategory.FINANCE:
            insights.append("金融领域风险较高，需要注意信息的时效性和来源可靠性")
        
        # 基于深度的洞察
        if analysis.implied_depth >= 4:
            insights.append("您需要深入了解，建议查阅专业资料或咨询专家")
        
        return insights
    
    def _identify_risk_areas(
        self,
        analysis: FrameworkAnalysis,
        time_axis: List[TimeAxisNode],
        comparison_axis: List[ComparisonAxisNode]
    ) -> List[str]:
        """识别风险区域"""
        risks = []
        
        # 时间轴中的不确定性
        for node in time_axis:
            if node.confidence in [ConfidenceLevel.LOW, ConfidenceLevel.UNCERTAIN]:
                risks.append(f"关于{node.period}的信息存在不确定性：{node.notes or '资料有限'}")
        
        # 比较轴中的待填充项
        for node in comparison_axis:
            if node.confidence == ConfidenceLevel.LOW:
                risks.append(f"{node.dimension}维度的比较需要更多资料支撑")
        
        # 基于领域的通用风险
        if analysis.domain == DomainCategory.FINANCE:
            risks.append("金融数据可能存在时效性问题，请以最新官方数据为准")
        elif analysis.domain == DomainCategory.MEDICINE:
            risks.append("医学信息专业性强，建议咨询专业医生")
        
        return risks
    
    def _generate_exploration_guide(
        self,
        question: str,
        analysis: FrameworkAnalysis,
        risks: List[str]
    ) -> str:
        """生成探索引导"""
        guide = "## 🎯 探索引导\n\n"
        guide += "**建议的探索顺序：**\n\n"
        
        # 基于问题类型建议探索顺序
        if analysis.implied_history:
            guide += "1️⃣ **先看时间轴**：了解演变历程，建立纵向认知\n"
        if analysis.implied_comparison:
            guide += "2️⃣ **再看比较轴**：横向对比差异，深化横向认知\n"
        guide += "3️⃣ **然后看核心**：把握整体框架和关键结论\n"
        guide += "4️⃣ **最后看风险**：了解存疑点和需要验证的信息\n\n"
        
        # 添加风险提醒
        if risks:
            guide += "⚠️ **特别提醒**：\n"
            for risk in risks[:2]:
                guide += f"- {risk}\n"
        
        guide += "\n💡 **持续优化**：如您在探索过程中有新发现，欢迎补充，我将更新这个认知框架"
        
        return guide
    
    def _calculate_overall_confidence(
        self,
        analysis: FrameworkAnalysis,
        time_axis: List[TimeAxisNode],
        comparison_axis: List[ComparisonAxisNode]
    ) -> float:
        """计算整体置信度"""
        # 基础置信度
        base_confidence = 0.7
        
        # 根据问题类型调整
        type_adjustments = {
            QuestionType.CONCEPTUAL: 0.1,
            QuestionType.HISTORICAL: -0.2,
            QuestionType.COMPARATIVE: 0.0,
            QuestionType.TECHNICAL: -0.1,
            QuestionType.UNKNOWN: -0.3
        }
        base_confidence += type_adjustments.get(analysis.question_type, 0)
        
        # 根据时间轴节点置信度调整
        if time_axis:
            avg_confidence = sum(
                1.0 if n.confidence == ConfidenceLevel.HIGH else
                0.6 if n.confidence == ConfidenceLevel.MEDIUM else
                0.3 if n.confidence == ConfidenceLevel.LOW else 0.1
                for n in time_axis
            ) / len(time_axis)
            base_confidence = base_confidence * 0.7 + avg_confidence * 0.3
        
        # 确保在0-1范围内
        return max(0.0, min(1.0, base_confidence))


class CognitiveFrameworkRenderer:
    """
    认知框架渲染器
    将认知框架渲染为可读的文本格式
    """
    
    def __init__(self):
        self._confidence_emoji = {
            ConfidenceLevel.HIGH: "🟢",
            ConfidenceLevel.MEDIUM: "🟡",
            ConfidenceLevel.LOW: "🔴",
            ConfidenceLevel.UNCERTAIN: "⚪"
        }
    
    def render(self, framework: CognitiveFramework) -> str:
        """
        渲染认知框架为文本
        
        Args:
            framework: 认知框架
            
        Returns:
            str: 渲染后的文本
        """
        output = []
        
        # 1. 头部信息
        output.append(self._render_header(framework))
        
        # 2. 核心结论
        output.append(self._render_core_conclusion(framework))
        
        # 3. 认知地图概览
        output.append(self._render_map_overview(framework))
        
        # 4. 时间轴
        if framework.time_axis:
            output.append(self._render_time_axis(framework))
        
        # 5. 比较轴
        if framework.comparison_axis:
            output.append(self._render_comparison_axis(framework))
        
        # 6. 关键洞察
        if framework.key_insights:
            output.append(self._render_key_insights(framework))
        
        # 7. 风险区域
        if framework.risk_areas:
            output.append(self._render_risk_areas(framework))
        
        # 8. 探索引导
        output.append(self._render_exploration_guide(framework))
        
        # 9. 置信度评估
        output.append(self._render_confidence_assessment(framework))
        
        return "\n\n".join(output)
    
    def _render_header(self, framework: CognitiveFramework) -> str:
        """渲染头部信息"""
        header = f"""
# 🧠 认知框架：{framework.question[:50]}{'...' if len(framework.question) > 50 else ''}

**框架ID**: `{framework.id}`  
**问题类型**: {framework.question_type.value}  
**所属领域**: {framework.domain.value}  
**生成时间**: {framework.created_at[:19]}
"""
        return header.strip()
    
    def _render_core_conclusion(self, framework: CognitiveFramework) -> str:
        """渲染核心结论"""
        return f"""
## 📌 核心结论

{framework.core_conclusion}
"""
    
    def _render_map_overview(self, framework: CognitiveFramework) -> str:
        """渲染认知地图概览"""
        return f"""
## 🗺️ 认知地图概览

| 统计项 | 数值 |
|-------|------|
| 总节点数 | {framework.total_nodes} |
| 已验证节点 | {framework.verified_nodes} {self._confidence_emoji[ConfidenceLevel.HIGH]} |
| 存疑节点 | {framework.uncertain_nodes} {self._confidence_emoji[ConfidenceLevel.LOW]} |

**节点关系图**:
```
{' → '.join([framework.cognitive_map['core_0'].title[:10]] + [f"...({len(framework.cognitive_map)-1}个子节点)"])}
```
"""
    
    def _render_time_axis(self, framework: CognitiveFramework) -> str:
        """渲染时间轴"""
        output = "## 📅 时间轴（纵向演变）\n\n"
        
        for i, node in enumerate(framework.time_axis):
            emoji = self._confidence_emoji.get(node.confidence, "⚪")
            
            # 时间范围
            time_range = ""
            if node.start_year:
                time_range = f"({node.start_year}"
                if node.end_year:
                    time_range += f" - {node.end_year}"
                elif node == framework.time_axis[-1]:
                    time_range += " - 现在"
                time_range += ")"
            
            output += f"""
### {emoji} {i+1}. {node.period} {time_range}

**关键事件**: {', '.join(node.key_events)}

**阶段特征**: {', '.join(node.characteristics)}

**重要性**: {node.significance}
"""
            if node.notes:
                output += f"\n> ⚠️ {node.notes}\n"
            output += "\n---\n"
        
        return output
    
    def _render_comparison_axis(self, framework: CognitiveFramework) -> str:
        """渲染比较轴"""
        output = "## ⚖️ 比较轴（横向差异）\n\n"
        
        for i, node in enumerate(framework.comparison_axis):
            emoji = self._confidence_emoji.get(node.confidence, "⚪")
            
            output += f"""
### {emoji} {i+1}. {node.dimension}

**{node.subject_a} vs {node.subject_b}**

| 维度 | {node.subject_a} | {node.subject_b} |
|------|------|------|
"""
            for key in node.a_features:
                output += f"| {key} | {node.a_features[key]} | {node.b_features.get(key, '-')} |\n"
            
            output += f"""
**核心差异**: {node.key_difference}

**共同点**: {node.similarity}

> 💡 {node.source_hint}
"""
            output += "\n---\n"
        
        return output
    
    def _render_key_insights(self, framework: CognitiveFramework) -> str:
        """渲染关键洞察"""
        output = "## 💡 关键洞察\n\n"
        
        for i, insight in enumerate(framework.key_insights):
            output += f"{i+1}. {insight}\n"
        
        return output
    
    def _render_risk_areas(self, framework: CognitiveFramework) -> str:
        """渲染风险区域"""
        output = "## ⚠️ 风险区域 / 存疑点\n\n"
        
        for i, risk in enumerate(framework.risk_areas):
            output += f"{i+1}. {risk}\n"
        
        output += "\n> 🛡️ **安全边际建议**: 对于上述存疑点，建议查阅权威资料或咨询专业人士进行交叉验证。\n"
        
        return output
    
    def _render_exploration_guide(self, framework: CognitiveFramework) -> str:
        """渲染探索引导"""
        return f"""
## 🎯 探索引导

{framework.exploration_guide}
"""
    
    def _render_confidence_assessment(self, framework: CognitiveFramework) -> str:
        """渲染置信度评估"""
        conf_level = "高" if framework.confidence_overall > 0.7 else "中" if framework.confidence_overall > 0.5 else "低"
        conf_emoji = "🟢" if framework.confidence_overall > 0.7 else "🟡" if framework.confidence_overall > 0.5 else "🔴"
        
        return f"""
## 📊 置信度评估

**整体置信度**: {conf_emoji} {conf_level} ({framework.confidence_overall:.0%})

| 评估维度 | 置信度 | 说明 |
|---------|-------|------|
| 问题理解 | 🟢 高 | 基于问题结构分析 |
| 领域定位 | 🟢 高 | 基于关键词匹配 |
| 框架构建 | {conf_emoji} {conf_level} | 基于可用的认知资源 |
| 风险识别 | 🟡 中 | 已尽力识别存疑点 |

---
*🤖 此框架由AI辅助构建，核心目的是帮您快速建立认知地图。*
*请根据实际情况对具体内容进行验证和补充。*
"""


# ==================== 主系统类 ====================

class CognitiveFrameworkCollaborator:
    """
    认知框架协作者主类
    
    整合所有组件，提供完整的认知框架协作服务
    """
    
    def __init__(self):
        self.generator = FrameworkGenerator()
        self.renderer = CognitiveFrameworkRenderer()
        self._cache = {}
    
    def collaborate(
        self,
        question: str,
        comparison_subjects: Optional[Tuple[str, str]] = None,
        return_framework: bool = False
    ) -> str:
        """
        与用户协作，构建认知框架
        
        Args:
            question: 用户问题
            comparison_subjects: (可选) 比较对象元组 (A, B)
            return_framework: 是否返回框架对象
            
        Returns:
            str: 渲染后的认知框架文本
            (或 tuple: (framework, text) 如果 return_framework=True)
        """
        # 生成框架
        framework = self.generator.generate_framework(question, comparison_subjects)
        
        # 渲染输出
        output = self.renderer.render(framework)
        
        if return_framework:
            return framework, output
        return output
    
    def update_framework(
        self,
        framework: CognitiveFramework,
        user_feedback: str
    ) -> CognitiveFramework:
        """
        根据用户反馈更新框架
        
        Args:
            framework: 现有框架
            user_feedback: 用户反馈
            
        Returns:
            CognitiveFramework: 更新后的框架
        """
        # 简单的反馈处理
        # TODO: 实现更复杂的反馈学习机制
        
        if "补充" in user_feedback or "增加" in user_feedback:
            # 增加新节点
            pass
        
        return framework


# ==================== 快捷函数 ====================

_cfc_instance = None

def get_cognitive_collaborator() -> CognitiveFrameworkCollaborator:
    """获取认知框架协作者单例"""
    global _cfc_instance
    if _cfc_instance is None:
        _cfc_instance = CognitiveFrameworkCollaborator()
    return _cfc_instance


def collaborate(question: str, comparison: Tuple[str, str] = None) -> str:
    """
    快速协作接口
    
    Args:
        question: 用户问题
        comparison: (可选) 比较对象 (A, B)
        
    Returns:
        str: 认知框架文本
    """
    collaborator = get_cognitive_collaborator()
    return collaborator.collaborate(question, comparison)
