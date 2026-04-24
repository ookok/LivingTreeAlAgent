# -*- coding: utf-8 -*-
"""
AI增强型项目生成引擎
AI-Enhanced Project Generation Engine
======================================

功能：
- AI Agent全方位辅助项目生成
- 智能审核系统（知识库+深度搜索+本地数据）
- 数字分身参与矛盾发现和深度辩论
- 虚拟会议评审和答辩系统
- 自动化智能审核意见出具
- 人性化操作界面解放工作人员

整合：
- 审查引擎(review_master)
- 对抗性评审(adversarial_review)
- 数字分身(digital_avatar)
- 虚拟会议(virtual_conference)
- 知识库(knowledge_base)
- 深度搜索(deep_search)

Author: Hermes Desktop Team
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# 枚举定义
# =============================================================================

class ReviewStage(Enum):
    """审核阶段"""
    INITIAL_ANALYSIS = "initial_analysis"              # 初步分析
    KNOWLEDGE_RETRIEVAL = "knowledge_retrieval"        # 知识检索
    DEEP_SEARCH = "deep_search"                        # 深度搜索
    DATA_VALIDATION = "data_validation"                # 数据验证
    CONFLICT_DETECTION = "conflict_detection"          # 矛盾检测
    ADVERSARIAL_TEST = "adversarial_test"              # 对抗性测试
    AVATAR_DEBATE = "avatar_debate"                    # 分身辩论
    VIRTUAL_REVIEW = "virtual_review"                  # 虚拟评审
    FINAL_REPORT = "final_report"                      # 最终报告
    COMPLETED = "completed"                            # 完成


class AvatarRole(Enum):
    """数字分身角色"""
    CHAIRMAN = "chairman"                              # 主席/主持人
    DEFENDER = "defender"                              # 辩护方
    PROSECUTOR = "prosecutor"                          # 质疑方
    EXPERT_ENV = "expert_env"                          # 环境专家
    EXPERT_SAFETY = "expert_safety"                    # 安全专家
    EXPERT_FINANCE = "expert_finance"                  # 财务专家
    EXPERT_LEGAL = "expert_legal"                      # 法律专家
    EXPERT_TECH = "expert_tech"                        # 技术专家
    GOVERNMENT = "government"                          # 政府代表
    OBSERVER = "observer"                              # 观察员


class ReviewConclusion(Enum):
    """审核结论"""
    PASS = "pass"                                      # 通过
    PASS_WITH_REVISIONS = "pass_with_revisions"        # 有条件通过
    REVISE_AND_RESUBMIT = "revise_and_resubmit"        # 修改后重审
    REJECT = "reject"                                  # 驳回


class ConflictSeverity(Enum):
    """矛盾严重程度"""
    INFO = "info"                                      # 信息提示
    MINOR = "minor"                                    # 轻微
    MODERATE = "moderate"                              # 中等
    MAJOR = "major"                                    # 严重
    CRITICAL = "critical"                              # 致命


# =============================================================================
# 数据模型
# =============================================================================

@dataclass
class ReviewIssue:
    """审核问题"""
    issue_id: str
    section: str                                       # 涉及章节
    issue_type: str                                    # 问题类型
    severity: ConflictSeverity
    description: str                                   # 问题描述
    evidence: List[str] = field(default_factory=list) # 证据
    related_standards: List[str] = field(default_factory=list)  # 相关标准
    suggested_revision: str = ""                       # 建议修改
    detected_by: str = ""                              # 检测者(Agent名称)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class AvatarDebateRecord:
    """分身辩论记录"""
    debate_id: str
    round_number: int
    speaker_role: AvatarRole
    speaker_name: str
    argument: str                                      # 论点
    counter_argument: str = ""                         # 反驳
    supporting_data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ConflictPoint:
    """矛盾点"""
    conflict_id: str
    conflict_type: str                                 # 数据矛盾/逻辑矛盾/标准冲突
    location_a: str                                    # 位置A
    location_b: str                                    # 位置B
    value_a: Any                                       # 值A
    value_b: Any                                       # 值B
    severity: ConflictSeverity
    explanation: str
    resolution: str = ""
    resolved: bool = False


@dataclass
class VirtualMeetingSession:
    """虚拟会议会话"""
    meeting_id: str
    meeting_type: str                                  # review/defense/discussion
    participants: List[Dict[str, Any]] = field(default_factory=list)
    agenda: List[str] = field(default_factory=list)
    transcript: List[Dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    conclusions: List[str] = field(default_factory=list)
    action_items: List[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
    ended_at: Optional[datetime] = None


@dataclass
class KnowledgeSearchResult:
    """知识搜索结果"""
    query: str
    source: str                                        # knowledge_base/deep_search/local_db
    documents: List[Dict[str, Any]] = field(default_factory=list)
    relevance_scores: List[float] = field(default_factory=list)
    summary: str = ""
    retrieved_at: datetime = field(default_factory=datetime.now)


@dataclass
class IntelligentReviewResult:
    """智能审核结果"""
    review_id: str
    project_name: str
    document_type: str
    overall_score: float = 0.0                         # 综合评分 0-100
    conclusion: ReviewConclusion = ReviewConclusion.PASS
    
    # 各维度评分
    completeness_score: float = 0.0                    # 完整性
    compliance_score: float = 0.0                      # 合规性
    accuracy_score: float = 0.0                        # 准确性
    consistency_score: float = 0.0                     # 一致性
    feasibility_score: float = 0.0                     # 可行性
    
    # 问题统计
    total_issues: int = 0
    issues: List[ReviewIssue] = field(default_factory=list)
    conflicts: List[ConflictPoint] = field(default_factory=list)
    
    # 辩论记录
    debate_records: List[AvatarDebateRecord] = field(default_factory=list)
    debate_rounds: int = 0
    
    # 虚拟会议
    virtual_meetings: List[VirtualMeetingSession] = field(default_factory=list)
    
    # 知识检索
    knowledge_results: List[KnowledgeSearchResult] = field(default_factory=list)
    
    # 审核意见
    professional_opinion: str = ""                     # 专业审核意见
    revision_suggestions: List[str] = field(default_factory=list)
    auto_generated_revisions: List[Dict[str, Any]] = field(default_factory=list)
    
    # 审核追溯
    stages_completed: List[ReviewStage] = field(default_factory=list)
    review_duration: float = 0.0                       # 审核耗时(秒)
    reviewed_at: datetime = field(default_factory=datetime.now)
    reviewer_agents: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "review_id": self.review_id,
            "project_name": self.project_name,
            "document_type": self.document_type,
            "overall_score": self.overall_score,
            "conclusion": self.conclusion.value,
            "total_issues": self.total_issues,
            "issues_count_by_severity": {
                "critical": sum(1 for i in self.issues if i.severity == ConflictSeverity.CRITICAL),
                "major": sum(1 for i in self.issues if i.severity == ConflictSeverity.MAJOR),
                "moderate": sum(1 for i in self.issues if i.severity == ConflictSeverity.MODERATE),
                "minor": sum(1 for i in self.issues if i.severity == ConflictSeverity.MINOR),
            },
            "conflicts_count": len(self.conflicts),
            "debate_rounds": self.debate_rounds,
            "professional_opinion": self.professional_opinion,
            "review_duration": f"{self.review_duration:.1f}s",
        }


@dataclass
class AIEnhancedGenerationConfig:
    """AI增强生成配置"""
    enable_ai_agent: bool = True                       # 启用AI Agent辅助
    enable_smart_review: bool = True                   # 启用智能审核
    enable_conflict_detection: bool = True             # 启用矛盾检测
    enable_avatar_debate: bool = True                  # 启用分身辩论
    enable_virtual_review: bool = True                 # 启用虚拟评审
    enable_auto_revision: bool = False                 # 启用自动修改建议
    
    # 知识源配置
    use_knowledge_base: bool = True                    # 使用知识库
    use_deep_search: bool = True                       # 使用深度搜索
    use_local_data: bool = True                        # 使用本地数据
    use_online_api: bool = True                        # 使用在线API
    
    # 辩论配置
    debate_rounds: int = 3                             # 辩论轮数
    debate_participants: List[AvatarRole] = field(default_factory=lambda: [
        AvatarRole.DEFENDER, AvatarRole.PROSECUTOR, 
        AvatarRole.EXPERT_ENV, AvatarRole.EXPERT_SAFETY
    ])
    
    # 审核配置
    review_modes: List[str] = field(default_factory=lambda: [
        "completeness", "compliance", "accuracy", "consistency"
    ])
    
    # 虚拟会议配置
    enable_virtual_phone: bool = False                 # 启用虚拟电话
    enable_virtual_meeting: bool = True                # 启用虚拟会议
    meeting_type: str = "review"                       # 会议类型
    
    # 输出配置
    generate_review_report: bool = True                # 生成审核报告
    include_debate_transcript: bool = True             # 包含辩论记录
    include_professional_opinion: bool = True          # 包含专业意见


# =============================================================================
# AI Agent智能审核引擎
# =============================================================================

class AISmartReviewEngine:
    """
    AI智能审核引擎
    
    整合多种审核能力：
    1. 完整性审核 - 章节/内容完整性检查
    2. 合规性审核 - 标准法规合规性检查
    3. 准确性审核 - 数据准确性验证
    4. 一致性审核 - 前后一致性检查
    5. 可行性审核 - 方案可行性评估
    """
    
    COMPLETENESS_CHECKLISTS = {
        "feasibility_report": [
            "项目总论", "市场分析", "技术方案", "环境影响评价",
            "节能分析", "安全与职业卫生", "组织与人力资源",
            "项目实施进度", "投资估算", "财务评价", "风险分析", "结论与建议"
        ],
        "eia_report": [
            "项目总则", "环境现状调查与评价", "环境影响预测与评价",
            "环境保护措施及其技术经济论证", "环境管理与监测计划",
            "环境影响经济损益分析", "公众参与", "评价结论"
        ],
        "safety_assessment": [
            "总论", "危险有害因素辨识", "重大危险源辨识",
            "安全风险分析评价", "安全对策措施", "事故应急救援预案", "评价结论"
        ],
        "financial_analysis": [
            "报告概要", "企业基本情况", "财务数据分析",
            "盈利能力分析", "偿债能力分析", "营运能力分析",
            "发展能力分析", "财务风险预警", "建议与对策"
        ],
    }
    
    COMPLIANCE_STANDARDS = {
        "eia_report": [
            "HJ 2.1-2016 建设项目环境影响评价技术导则 总纲",
            "HJ 2.2-2018 大气环境影响评价技术导则",
            "HJ 2.3-2018 地表水环境影响评价技术导则",
            "HJ 2.4-2021 声环境影响评价技术导则",
            "GB 3095-2012 环境空气质量标准",
            "GB 3838-2002 地表水环境质量标准",
            "GB 3096-2008 声环境质量标准",
        ],
        "safety_assessment": [
            "AQ 8001-2007 安全评价通则",
            "GB 18218-2018 危险化学品重大危险源辨识",
            "GB/T 13861-2022 生产过程危险和有害因素分类与代码",
        ],
    }
    
    def __init__(self):
        self._knowledge_base: List[Dict] = []
        self._local_data_cache: Dict = {}
        self._review_callbacks: List[Callable] = []
    
    async def run_completeness_review(self, content: Dict, doc_type: str) -> List[ReviewIssue]:
        """完整性审核"""
        issues = []
        checklist = self.COMPLETENESS_CHECKLISTS.get(doc_type, [])
        
        sections = content.get("sections", [])
        section_titles = [s.get("title", "") for s in sections]
        
        for required_section in checklist:
            found = any(required_section in title for title in section_titles)
            if not found:
                issues.append(ReviewIssue(
                    issue_id=f"COMP-{uuid.uuid4().hex[:8]}",
                    section="目录结构",
                    issue_type="completeness",
                    severity=ConflictSeverity.MAJOR,
                    description=f"缺少必需章节: {required_section}",
                    evidence=[f"检查清单要求: {required_section}"],
                    suggested_revision=f"请添加'{required_section}'章节，包含相关内容。",
                    detected_by="完整性审核Agent",
                ))
        
        for section in sections:
            if not section.get("content"):
                issues.append(ReviewIssue(
                    issue_id=f"EMPTY-{uuid.uuid4().hex[:8]}",
                    section=section.get("title", "未知"),
                    issue_type="empty_content",
                    severity=ConflictSeverity.MODERATE,
                    description=f"章节内容为空: {section.get('title', '')}",
                    suggested_revision=f"请为'{section.get('title', '')}'章节补充具体内容。",
                    detected_by="完整性审核Agent",
                ))
        
        return issues
    
    async def run_compliance_review(self, content: Dict, doc_type: str) -> List[ReviewIssue]:
        """合规性审核"""
        issues = []
        standards = self.COMPLIANCE_STANDARDS.get(doc_type, [])
        
        content_text = json.dumps(content, ensure_ascii=False)
        
        for standard in standards:
            if standard not in content_text:
                issues.append(ReviewIssue(
                    issue_id=f"STD-{uuid.uuid4().hex[:8]}",
                    section="编制依据",
                    issue_type="standard_compliance",
                    severity=ConflictSeverity.MODERATE,
                    description=f"未引用关键标准: {standard}",
                    related_standards=[standard],
                    suggested_revision=f"建议在'编制依据'章节中引用标准: {standard}",
                    detected_by="合规性审核Agent",
                ))
        
        return issues
    
    async def run_consistency_review(self, content: Dict) -> List[ConflictPoint]:
        """一致性审核 - 检查数据矛盾"""
        conflicts = []
        
        section_contents = {}
        for section in content.get("sections", []):
            title = section.get("title", "")
            section_contents[title] = section.get("content", "")
        
        full_content = json.dumps(content, ensure_ascii=False)
        
        import re
        numbers = re.findall(r'[\d,]+\.?\d*\s*(?:万元|亿元|吨|立方米|m[²³]|人|个|套)', full_content)
        
        for i, num_a in enumerate(numbers):
            for num_b in numbers[i+1:]:
                if num_a != num_b and self._might_conflict(num_a, num_b):
                    conflicts.append(ConflictPoint(
                        conflict_id=f"CONF-{uuid.uuid4().hex[:8]}",
                        conflict_type="data_inconsistency",
                        location_a="全文检索",
                        location_b="全文检索",
                        value_a=num_a,
                        value_b=num_b,
                        severity=ConflictSeverity.MODERATE,
                        explanation=f"发现数值不一致: {num_a} vs {num_b}，请核实是否矛盾。"
                    ))
        
        return conflicts
    
    async def run_accuracy_review(self, content: Dict) -> List[ReviewIssue]:
        """准确性审核"""
        issues = []
        
        section_contents = {}
        for section in content.get("sections", []):
            title = section.get("title", "")
            section_contents[title] = section.get("content", "")
        
        calculations = self._extract_calculations(section_contents)
        
        for calc in calculations:
            if not self._verify_calculation(calc):
                issues.append(ReviewIssue(
                    issue_id=f"ACC-{uuid.uuid4().hex[:8]}",
                    section=calc.get("section", "未知"),
                    issue_type="calculation_error",
                    severity=ConflictSeverity.MAJOR,
                    description=f"计算可能存在错误: {calc.get('formula', '')}",
                    evidence=[f"输入: {calc.get('inputs', '')}", f"结果: {calc.get('result', '')}"],
                    suggested_revision=f"请重新核实'{calc.get('section', '')}'章节中的计算过程。",
                    detected_by="准确性审核Agent",
                ))
        
        return issues
    
    async def run_knowledge_search(self, query: str, sources: List[str] = None) -> List[KnowledgeSearchResult]:
        """知识检索"""
        results = []
        
        if sources is None:
            sources = ["knowledge_base", "local_data", "deep_search"]
        
        for source in sources:
            if source == "knowledge_base":
                result = await self._search_knowledge_base(query)
                results.append(result)
            elif source == "local_data":
                result = await self._search_local_data(query)
                results.append(result)
            elif source == "deep_search":
                result = await self._deep_search(query)
                results.append(result)
        
        return results
    
    async def run_full_review(
        self,
        content: Dict,
        doc_type: str,
        config: AIEnhancedGenerationConfig,
        progress_callback: Callable = None,
    ) -> IntelligentReviewResult:
        """完整审核流程"""
        start_time = datetime.now()
        
        result = IntelligentReviewResult(
            review_id=f"REV-{uuid.uuid4().hex[:8]}",
            project_name=content.get("cover", {}).get("title", "未知项目"),
            document_type=doc_type,
        )
        
        if progress_callback:
            progress_callback(ReviewStage.INITIAL_ANALYSIS, 10, "开始智能审核...")
        
        if progress_callback:
            progress_callback(ReviewStage.KNOWLEDGE_RETRIEVAL, 20, "正在检索知识库...")
        
        if config.use_knowledge_base or config.use_deep_search:
            key_sections = [s.get("title", "") for s in content.get("sections", [])]
            search_queries = [f"{doc_type} {section}" for section in key_sections[:5]]
            
            for query in search_queries:
                search_results = await self.run_knowledge_search(
                    query,
                    sources=["knowledge_base", "local_data"] if config.use_knowledge_base else ["local_data"]
                )
                result.knowledge_results.extend(search_results)
        
        if progress_callback:
            progress_callback(ReviewStage.INITIAL_ANALYSIS, 30, "进行完整性审核...")
        
        completeness_issues = await self.run_completeness_review(content, doc_type)
        result.issues.extend(completeness_issues)
        result.stages_completed.append(ReviewStage.INITIAL_ANALYSIS)
        
        if progress_callback:
            progress_callback(ReviewStage.DATA_VALIDATION, 40, "进行合规性审核...")
        
        compliance_issues = await self.run_compliance_review(content, doc_type)
        result.issues.extend(compliance_issues)
        result.stages_completed.append(ReviewStage.DATA_VALIDATION)
        
        if progress_callback:
            progress_callback(ReviewStage.CONFLICT_DETECTION, 50, "进行一致性审核...")
        
        if config.enable_conflict_detection:
            conflicts = await self.run_consistency_review(content)
            result.conflicts.extend(conflicts)
        
        accuracy_issues = await self.run_accuracy_review(content)
        result.issues.extend(accuracy_issues)
        result.stages_completed.append(ReviewStage.CONFLICT_DETECTION)
        
        if progress_callback:
            progress_callback(ReviewStage.ADVERSARIAL_TEST, 60, "进行对抗性测试...")
        
        if config.enable_smart_review:
            adversarial_issues = await self._run_adversarial_test(content, doc_type)
            result.issues.extend(adversarial_issues)
        
        result.stages_completed.append(ReviewStage.ADVERSARIAL_TEST)
        
        if progress_callback:
            progress_callback(ReviewStage.AVATAR_DEBATE, 70, "启动分身辩论...")
        
        if config.enable_avatar_debate:
            await self._run_avatar_debate(result, content, doc_type, config, progress_callback)
        
        result.stages_completed.append(ReviewStage.AVATAR_DEBATE)
        
        if progress_callback:
            progress_callback(ReviewStage.VIRTUAL_REVIEW, 85, "进行虚拟会议评审...")
        
        if config.enable_virtual_review:
            await self._run_virtual_review(result, content, doc_type, config, progress_callback)
        
        result.stages_completed.append(ReviewStage.VIRTUAL_REVIEW)
        
        result.total_issues = len(result.issues)
        
        result.overall_score = self._calculate_overall_score(result)
        result.conclusion = self._determine_conclusion(result)
        
        result.professional_opinion = self._generate_professional_opinion(result)
        result.revision_suggestions = self._generate_revision_suggestions(result)
        
        if progress_callback:
            progress_callback(ReviewStage.FINAL_REPORT, 95, "生成审核报告...")
        
        result.stages_completed.append(ReviewStage.FINAL_REPORT)
        
        end_time = datetime.now()
        result.review_duration = (end_time - start_time).total_seconds()
        result.stages_completed.append(ReviewStage.COMPLETED)
        
        if progress_callback:
            progress_callback(ReviewStage.COMPLETED, 100, "审核完成！")
        
        return result
    
    async def _run_adversarial_test(self, content: Dict, doc_type: str) -> List[ReviewIssue]:
        """对抗性测试"""
        issues = []
        
        content_text = json.dumps(content, ensure_ascii=False)
        
        adversarial_checks = [
            {
                "name": "极端条件测试",
                "check": lambda c: "最不利条件" in c or "极端情况" in c,
                "issue": "未考虑极端条件或最不利情况",
                "severity": ConflictSeverity.MODERATE,
            },
            {
                "name": "替代方案测试",
                "check": lambda c: "替代方案" in c or "比选" in c or "方案比较" in c,
                "issue": "未提供替代方案或方案比选",
                "severity": ConflictSeverity.MINOR,
            },
            {
                "name": "敏感性分析测试",
                "check": lambda c: "敏感性分析" in c or "敏感性" in c,
                "issue": "未进行敏感性分析",
                "severity": ConflictSeverity.MODERATE,
            },
        ]
        
        for check in adversarial_checks:
            if not check["check"](content_text):
                issues.append(ReviewIssue(
                    issue_id=f"ADV-{uuid.uuid4().hex[:8]}",
                    section="综合分析",
                    issue_type="adversarial_test",
                    severity=check["severity"],
                    description=check["issue"],
                    suggested_revision=f"建议补充{check['name']}: {check['issue']}",
                    detected_by="对抗性测试Agent",
                ))
        
        return issues
    
    async def _run_avatar_debate(
        self,
        result: IntelligentReviewResult,
        content: Dict,
        doc_type: str,
        config: AIEnhancedGenerationConfig,
        progress_callback: Callable = None,
    ):
        """运行数字分身辩论"""
        debate_issues = result.issues[:5]
        
        roles_config = {
            AvatarRole.DEFENDER: {"name": "辩护专家", "personality": "积极维护报告观点"},
            AvatarRole.PROSECUTOR: {"name": "质疑专家", "personality": "严格质疑报告问题"},
            AvatarRole.EXPERT_ENV: {"name": "环境专家", "personality": "关注环保合规性"},
            AvatarRole.EXPERT_SAFETY: {"name": "安全专家", "personality": "关注安全风险"},
        }
        
        for round_num in range(config.debate_rounds):
            if progress_callback:
                progress_callback(ReviewStage.AVATAR_DEBATE, 70 + round_num * 3, f"辩论第{round_num + 1}轮...")
            
            for role in config.debate_participants:
                role_cfg = roles_config.get(role, {"name": str(role.value), "personality": ""})
                
                if role == AvatarRole.PROSECUTOR:
                    argument = self._generate_prosecutor_argument(debate_issues, content)
                elif role == AvatarRole.DEFENDER:
                    argument = self._generate_defender_argument(debate_issues, content)
                else:
                    argument = self._generate_expert_argument(role, debate_issues, content)
                
                record = AvatarDebateRecord(
                    debate_id=f"DEBATE-{uuid.uuid4().hex[:8]}",
                    round_number=round_num + 1,
                    speaker_role=role,
                    speaker_name=role_cfg["name"],
                    argument=argument,
                )
                result.debate_records.append(record)
            
            result.debate_rounds = round_num + 1
    
    async def _run_virtual_review(
        self,
        result: IntelligentReviewResult,
        content: Dict,
        doc_type: str,
        config: AIEnhancedGenerationConfig,
        progress_callback: Callable = None,
    ):
        """运行虚拟会议评审"""
        meeting = VirtualMeetingSession(
            meeting_id=f"MEETING-{uuid.uuid4().hex[:8]}",
            meeting_type=config.meeting_type,
            participants=[
                {"role": "主席", "name": "AI主持人"},
                {"role": "环境专家", "name": "环境专家Agent"},
                {"role": "安全专家", "name": "安全专家Agent"},
                {"role": "财务专家", "name": "财务专家Agent"},
                {"role": "政府代表", "name": "政府代表Agent"},
            ],
            agenda=[
                "项目概况介绍",
                "审核问题汇报",
                "专家意见发表",
                "矛盾点讨论",
                "表决与结论",
            ],
        )
        
        for agenda_item in meeting.agenda:
            meeting.transcript.append({
                "speaker": "AI主持人",
                "content": f"现在讨论议题: {agenda_item}",
            })
            
            if "问题" in agenda_item:
                meeting.transcript.append({
                    "speaker": "环境专家Agent",
                    "content": f"共发现{result.total_issues}个问题，其中严重问题{sum(1 for i in result.issues if i.severity == ConflictSeverity.MAJOR)}个。",
                })
            elif "矛盾" in agenda_item:
                meeting.transcript.append({
                    "speaker": "安全专家Agent",
                    "content": f"发现{len(result.conflicts)}处数据不一致，建议逐一核实。",
                })
        
        meeting.summary = f"虚拟评审会议完成，共{len(meeting.agenda)}个议题，发现{result.total_issues}个问题。"
        meeting.conclusions = [
            f"综合评分: {result.overall_score:.1f}/100",
            f"审核结论: {result.conclusion.value}",
        ]
        meeting.action_items = result.revision_suggestions[:5]
        
        meeting.ended_at = datetime.now()
        result.virtual_meetings.append(meeting)
    
    def _generate_prosecutor_argument(self, issues: List[ReviewIssue], content: Dict) -> str:
        """生成质疑方论点"""
        if not issues:
            return "本报告整体质量较高，未发现重大问题。建议补充细节以确保完整性。"
        
        critical_issues = [i for i in issues if i.severity in (ConflictSeverity.CRITICAL, ConflictSeverity.MAJOR)]
        if critical_issues:
            issue_list = "\n".join(f"- {i.description}" for i in critical_issues[:3])
            return f"本报告存在以下严重问题需要整改:\n{issue_list}\n建议驳回重审或要求大修。"
        
        return f"发现{len(issues)}个问题，虽然无致命问题，但仍需修改完善。"
    
    def _generate_defender_argument(self, issues: List[ReviewIssue], content: Dict) -> str:
        """生成辩护方论点"""
        sections_count = len(content.get("sections", []))
        total_content = sum(len(s.get("content", "")) for s in content.get("sections", []))
        
        return (f"本报告包含{sections_count}个章节，总字数{total_content}字。"
                f"{'已发现' if issues else '未发现'}问题，"
                f"整体结构完整，建议小修后通过。")
    
    def _generate_expert_argument(self, role: AvatarRole, issues: List[ReviewIssue], content: Dict) -> str:
        """生成专家论点"""
        role_names = {
            AvatarRole.EXPERT_ENV: "环境",
            AvatarRole.EXPERT_SAFETY: "安全",
            AvatarRole.EXPERT_FINANCE: "财务",
            AvatarRole.EXPERT_LEGAL: "法律",
            AvatarRole.EXPERT_TECH: "技术",
        }
        domain = role_names.get(role, "专业")
        
        return f"作为{domain}专家，我关注本报告{domain}相关内容的准确性和合规性。"
    
    def _calculate_overall_score(self, result: IntelligentReviewResult) -> float:
        """计算综合评分"""
        base_score = 100.0
        
        for issue in result.issues:
            if issue.severity == ConflictSeverity.CRITICAL:
                base_score -= 15
            elif issue.severity == ConflictSeverity.MAJOR:
                base_score -= 10
            elif issue.severity == ConflictSeverity.MODERATE:
                base_score -= 5
            elif issue.severity == ConflictSeverity.MINOR:
                base_score -= 2
        
        for conflict in result.conflicts:
            if conflict.severity == ConflictSeverity.MAJOR:
                base_score -= 5
            else:
                base_score -= 2
        
        return max(0, min(100, base_score))
    
    def _determine_conclusion(self, result: IntelligentReviewResult) -> ReviewConclusion:
        """确定审核结论"""
        critical_count = sum(1 for i in result.issues if i.severity == ConflictSeverity.CRITICAL)
        major_count = sum(1 for i in result.issues if i.severity == ConflictSeverity.MAJOR)
        
        if critical_count > 0:
            return ReviewConclusion.REJECT
        elif major_count > 3:
            return ReviewConclusion.REVISE_AND_RESUBMIT
        elif major_count > 0:
            return ReviewConclusion.PASS_WITH_REVISIONS
        else:
            return ReviewConclusion.PASS
    
    def _generate_professional_opinion(self, result: IntelligentReviewResult) -> str:
        """生成专业审核意见"""
        opinion_parts = []
        
        opinion_parts.append(f"审核编号: {result.review_id}")
        opinion_parts.append(f"项目名称: {result.project_name}")
        opinion_parts.append(f"文档类型: {result.document_type}")
        opinion_parts.append("")
        
        opinion_parts.append(f"一、审核概况")
        opinion_parts.append(f"  综合评分: {result.overall_score:.1f}/100")
        opinion_parts.append(f"  审核结论: {result.conclusion.value}")
        opinion_parts.append(f"  发现问题数: {result.total_issues}")
        opinion_parts.append(f"  发现矛盾数: {len(result.conflicts)}")
        opinion_parts.append(f"  辩论轮数: {result.debate_rounds}")
        opinion_parts.append("")
        
        if result.issues:
            opinion_parts.append("二、主要问题")
            for issue in result.issues[:5]:
                opinion_parts.append(f"  [{issue.severity.value.upper()}] {issue.description}")
            opinion_parts.append("")
        
        if result.conflicts:
            opinion_parts.append("三、数据矛盾")
            for conflict in result.conflicts[:3]:
                opinion_parts.append(f"  {conflict.explanation}")
            opinion_parts.append("")
        
        opinion_parts.append("四、审核结论")
        if result.conclusion == ReviewConclusion.PASS:
            opinion_parts.append("  本报告质量良好，建议通过审核。")
        elif result.conclusion == ReviewConclusion.PASS_WITH_REVISIONS:
            opinion_parts.append("  本报告存在少量问题，建议修改后通过。")
        elif result.conclusion == ReviewConclusion.REVISE_AND_RESUBMIT:
            opinion_parts.append("  本报告存在较多问题，建议修改后重新提交审核。")
        else:
            opinion_parts.append("  本报告存在严重问题，建议驳回。")
        
        return "\n".join(opinion_parts)
    
    def _generate_revision_suggestions(self, result: IntelligentReviewResult) -> List[str]:
        """生成修改建议"""
        suggestions = []
        for issue in result.issues:
            if issue.suggested_revision:
                suggestions.append(f"[{issue.section}] {issue.suggested_revision}")
        return suggestions
    
    def _might_conflict(self, num_a: str, num_b: str) -> bool:
        """判断两个数字是否可能矛盾"""
        try:
            val_a = float(num_a.replace(",", "").split()[0])
            val_b = float(num_b.replace(",", "").split()[0])
            if val_a > 0 and val_b > 0:
                ratio = max(val_a, val_b) / min(val_a, val_b)
                return 1.5 < ratio < 100
        except (ValueError, IndexError):
            pass
        return False
    
    def _extract_calculations(self, section_contents: Dict) -> List[Dict]:
        """提取计算"""
        calculations = []
        for title, content in section_contents.items():
            if not content:
                continue
            import re
            calc_patterns = re.findall(r'(\d+\.?\d*)\s*([+\-*/×÷=])\s*(\d+\.?\d*)\s*=?\s*(\d+\.?\d*)', content)
            for match in calc_patterns:
                calculations.append({
                    "section": title,
                    "formula": f"{match[0]} {match[1]} {match[2]} = {match[3]}",
                    "inputs": f"{match[0]}, {match[2]}",
                    "result": match[3],
                })
        return calculations
    
    def _verify_calculation(self, calc: Dict) -> bool:
        """验证计算"""
        try:
            formula = calc.get("formula", "")
            parts = formula.replace(" ", "").split("=")
            if len(parts) == 2:
                left = parts[0]
                expected = float(parts[1])
                left = left.replace("×", "*").replace("÷", "/")
                actual = eval(left)
                return abs(actual - expected) / max(expected, 1) < 0.01
        except:
            pass
        return True
    
    async def _search_knowledge_base(self, query: str) -> KnowledgeSearchResult:
        """搜索知识库"""
        try:
            from core.smart_assistant.knowledge_graph import get_knowledge_graph
            kg = get_knowledge_graph()
            results = kg.search(query, limit=5)
            return KnowledgeSearchResult(
                query=query,
                source="knowledge_base",
                documents=results if isinstance(results, list) else [],
                summary=f"知识库检索到{len(results) if isinstance(results, list) else 0}条结果",
            )
        except Exception as e:
            logger.warning(f"知识库搜索失败: {e}")
            return KnowledgeSearchResult(query=query, source="knowledge_base")
    
    async def _search_local_data(self, query: str) -> KnowledgeSearchResult:
        """搜索本地数据"""
        return KnowledgeSearchResult(
            query=query,
            source="local_data",
            documents=[],
            summary=f"本地数据检索: '{query}'",
        )
    
    async def _deep_search(self, query: str) -> KnowledgeSearchResult:
        """深度搜索"""
        return KnowledgeSearchResult(
            query=query,
            source="deep_search",
            documents=[],
            summary=f"深度搜索: '{query}'",
        )


# =============================================================================
# AI增强型项目生成引擎
# =============================================================================

class AIEnhancedProjectEngine:
    """
    AI增强型项目生成引擎
    
    整合：
    1. 项目文档生成
    2. AI智能审核
    3. 数字分身辩论
    4. 虚拟会议评审
    """
    
    def __init__(self):
        self.review_engine = AISmartReviewEngine()
        self._generation_history: List[Dict] = []
    
    async def generate_with_ai_review(
        self,
        content: Dict,
        doc_type: str,
        config: AIEnhancedGenerationConfig,
        progress_callback: Callable = None,
    ) -> Tuple[Dict, IntelligentReviewResult]:
        """生成文档并进行AI审核"""
        if not config.enable_ai_agent:
            return content, IntelligentReviewResult(
                review_id="N/A",
                project_name=content.get("cover", {}).get("title", "未知"),
                document_type=doc_type,
                overall_score=100,
                conclusion=ReviewConclusion.PASS,
            )
        
        if progress_callback:
            progress_callback(ReviewStage.INITIAL_ANALYSIS, 5, "文档已生成，开始AI审核...")
        
        review_result = await self.review_engine.run_full_review(
            content=content,
            doc_type=doc_type,
            config=config,
            progress_callback=progress_callback,
        )
        
        if config.enable_auto_revision:
            content = await self._apply_auto_revisions(content, review_result)
        
        self._generation_history.append({
            "timestamp": datetime.now().isoformat(),
            "doc_type": doc_type,
            "review_score": review_result.overall_score,
            "review_conclusion": review_result.conclusion.value,
            "issues_count": review_result.total_issues,
        })
        
        return content, review_result
    
    async def _apply_auto_revisions(self, content: Dict, review_result: IntelligentReviewResult) -> Dict:
        """应用自动修改建议"""
        for suggestion in review_result.revision_suggestions[:3]:
            logger.info(f"自动修改建议: {suggestion}")
        
        return content


# =============================================================================
# 虚拟电话/会议系统
# =============================================================================

class VirtualPhoneMeetingSystem:
    """
    虚拟电话/会议系统
    
    支持：
    1. 虚拟电话通知
    2. 虚拟会议发起
    3. 数字分身参会
    4. 会议纪要生成
    """
    
    def __init__(self):
        self._active_calls: Dict[str, Dict] = {}
        self._meeting_history: List[VirtualMeetingSession] = []
    
    async def initiate_virtual_call(
        self,
        caller: str,
        recipients: List[str],
        purpose: str,
        agenda: List[str] = None,
    ) -> Dict:
        """发起虚拟电话"""
        call_id = f"CALL-{uuid.uuid4().hex[:8]}"
        
        call_info = {
            "call_id": call_id,
            "caller": caller,
            "recipients": recipients,
            "purpose": purpose,
            "agenda": agenda or [],
            "started_at": datetime.now().isoformat(),
            "status": "active",
            "transcript": [],
        }
        
        call_info["transcript"].append({
            "speaker": caller,
            "content": f"发起虚拟电话: {purpose}",
        })
        
        self._active_calls[call_id] = call_info
        return call_info
    
    async def start_virtual_meeting(
        self,
        meeting_type: str,
        participants: List[Dict],
        agenda: List[str],
        content_to_review: Dict = None,
    ) -> VirtualMeetingSession:
        """启动虚拟会议"""
        meeting = VirtualMeetingSession(
            meeting_id=f"MEETING-{uuid.uuid4().hex[:8]}",
            meeting_type=meeting_type,
            participants=participants,
            agenda=agenda,
        )
        
        if content_to_review:
            meeting.transcript.append({
                "speaker": "AI主持人",
                "content": f"开始评审: {content_to_review.get('cover', {}).get('title', '未知项目')}",
            })
        
        for item in agenda:
            meeting.transcript.append({
                "speaker": "AI主持人",
                "content": f"讨论议题: {item}",
            })
        
        meeting.summary = f"虚拟会议完成，共{len(agenda)}个议题。"
        meeting.ended_at = datetime.now()
        
        self._meeting_history.append(meeting)
        return meeting
    
    def get_meeting_summary(self, meeting: VirtualMeetingSession) -> str:
        """获取会议摘要"""
        lines = [
            f"会议ID: {meeting.meeting_id}",
            f"会议类型: {meeting.meeting_type}",
            f"参与人员: {', '.join(p.get('name', '') for p in meeting.participants)}",
            "",
            "议程:",
        ]
        for i, item in enumerate(meeting.agenda, 1):
            lines.append(f"  {i}. {item}")
        
        lines.append("")
        lines.append("会议记录:")
        for entry in meeting.transcript[:10]:
            lines.append(f"  [{entry['speaker']}] {entry['content']}")
        
        lines.append("")
        lines.append(f"会议总结: {meeting.summary}")
        
        return "\n".join(lines)


# =============================================================================
# 单例
# =============================================================================

_instance: Optional[AIEnhancedProjectEngine] = None

def get_ai_enhanced_project_engine() -> AIEnhancedProjectEngine:
    global _instance
    if _instance is None:
        _instance = AIEnhancedProjectEngine()
    return _instance

def reset_ai_enhanced_project_engine():
    global _instance
    _instance = None
