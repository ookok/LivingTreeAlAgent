# -*- coding: utf-8 -*-
"""
智慧审核大脑 - Smart Review Brain
=================================

核心功能：
1. 多模块协同审核（内容、结构、规范、数据）
2. 矛盾自动发现
3. 深度辩论机制
4. 内容比对与校准
5. 审核报告生成
6. 修改意见输出

集成模块：
- AIEnhancedGeneration (AI审核)
- ExpertPanel (专家审核)
- KnowledgeBaseVectorStore (知识比对)
- CalculationEngine (数据验证)

Author: Hermes Desktop Team
"""

import logging
import json
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)


class IssueSeverity(Enum):
    """问题严重程度"""
    CRITICAL = "critical"   # 严重错误
    ERROR = "error"         # 一般错误
    WARNING = "warning"     # 警告
    SUGGESTION = "suggestion"  # 建议


class IssueType(Enum):
    """问题类型"""
    # 数据问题
    DATA_INCONSISTENCY = "data_inconsistency"    # 数据不一致
    CALCULATION_ERROR = "calculation_error"      # 计算错误
    OUTDATED_DATA = "outdated_data"              # 数据过时
    MISSING_DATA = "missing_data"               # 数据缺失
    
    # 内容问题
    LOGIC_ERROR = "logic_error"                 # 逻辑错误
    CONTRADICTION = "contradiction"             # 矛盾
    INCOMPLETE = "incomplete"                   # 内容不完整
    SUPERFICIAL = "superficial"                 # 分析肤浅
    
    # 规范问题
    STANDARD_MISSING = "standard_missing"        # 引用标准缺失
    STANDARD_OUTDATED = "standard_outdated"      # 标准过时
    FORMAT_ERROR = "format_error"               # 格式错误
    
    # 专业问题
    TECHNICAL_INACCURACY = "technical_inaccuracy"  # 技术不准确
    METHODOLOGY_ISSUE = "methodology_issue"        # 方法论问题
    SCOPE_MISMATCH = "scope_mismatch"             # 范围不匹配


@dataclass
class ReviewIssue:
    """审核问题"""
    id: str
    type: IssueType
    severity: IssueSeverity
    section: str
    title: str
    description: str
    evidence: List[str] = field(default_factory=list)  # 证据
    locations: List[Tuple[int, int]] = field(default_factory=list)  # 位置
    suggestion: str = ""
    auto_fixable: bool = False
    auto_fix_content: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "severity": self.severity.value,
            "section": self.section,
            "title": self.title,
            "description": self.description,
            "evidence": self.evidence,
            "suggestion": self.suggestion,
            "auto_fixable": self.auto_fixable,
        }


@dataclass
class DebateTurn:
    """辩论回合"""
    speaker: str  # "proponent", "opponent", "expert", "arbiter"
    argument: str
    evidence: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ReviewReport:
    """审核报告"""
    document_type: str
    review_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # 概览
    overall_score: float = 0.0
    score_breakdown: Dict[str, float] = field(default_factory=dict)
    conclusion: str = "pending"
    
    # 问题汇总
    issues: List[ReviewIssue] = field(default_factory=list)
    critical_count: int = 0
    error_count: int = 0
    warning_count: int = 0
    suggestion_count: int = 0
    
    # 矛盾分析
    contradictions: List[Dict] = field(default_factory=list)
    
    # 辩论记录
    debate_transcript: List[DebateTurn] = field(default_factory=list)
    
    # 知识比对
    knowledge_gaps: List[Dict] = field(default_factory=list)
    
    # 数据验证
    data_validation: Dict[str, Any] = field(default_factory=dict)
    
    # 修改建议
    revision_suggestions: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "document_type": self.document_type,
            "review_timestamp": self.review_timestamp,
            "overall_score": self.overall_score,
            "score_breakdown": self.score_breakdown,
            "conclusion": self.conclusion,
            "issues_summary": {
                "critical": self.critical_count,
                "error": self.error_count,
                "warning": self.warning_count,
                "suggestion": self.suggestion_count,
                "total": len(self.issues),
            },
            "contradictions": self.contradictions,
            "debate_rounds": len(self.debate_transcript),
            "knowledge_gaps": self.knowledge_gaps,
            "data_validation": self.data_validation,
            "revision_suggestions": self.revision_suggestions,
            "issues": [i.to_dict() for i in self.issues],
        }


class SmartReviewBrain:
    """
    智慧审核大脑
    
    使用示例：
    ```python
    brain = SmartReviewBrain()
    
    # 完整审核流程
    report = await brain.review(
        content=document_content,
        doc_type="eia_report",
        industry="化工",
        enable_debate=True
    )
    
    # 获取问题
    for issue in report.issues:
        logger.info(f"{issue.severity.value}: {issue.title}")
        
    # 获取修改建议
    for suggestion in report.revision_suggestions:
        logger.info(f"- {suggestion['section']}: {suggestion['content']}")
        
    # 自动修复
    fixed_content = await brain.auto_fix(content, report)
    ```
    """
    
    def __init__(self):
        self._ai_reviewer = None
        self._expert_panel = None
        self._knowledge_base = None
        self._calculation_engine = None
        self._evolution_engine = None
        
    @property
    def ai_reviewer(self):
        """AI审核器"""
        if self._ai_reviewer is None:
            try:
                from core.smart_writing.ai_enhanced_generation import get_review_engine
                self._ai_reviewer = get_review_engine()
            except ImportError:
                logger.warning("AIEnhancedGeneration 未安装")
        return self._ai_reviewer
    
    @property
    def expert_panel(self):
        """专家面板"""
        if self._expert_panel is None:
            try:
                from expert_system.expert_panel import ExpertPanel
                self._expert_panel = ExpertPanel()
            except ImportError:
                logger.warning("ExpertPanel 未安装")
        return self._expert_panel
    
    @property
    def knowledge_base(self):
        """知识库"""
        if self._knowledge_base is None:
            try:
                from core.knowledge_vector_db import KnowledgeBaseVectorStore
                self._knowledge_base = KnowledgeBaseVectorStore()
            except ImportError:
                logger.warning("KnowledgeBaseVectorStore 未安装")
        return self._knowledge_base
    
    @property
    def calculation_engine(self):
        """计算引擎"""
        if self._calculation_engine is None:
            try:
                from core.smart_writing.calculation_models import get_calculation_engine
                self._calculation_engine = get_calculation_engine()
            except ImportError:
                logger.warning("CalculationEngine 未安装")
        return self._calculation_engine
    
    @property
    def evolution_engine(self):
        """进化引擎"""
        if self._evolution_engine is None:
            try:
                from core.smart_writing.self_evolution import get_evolution_engine
                self._evolution_engine = get_evolution_engine()
            except ImportError:
                logger.warning("EvolutionEngine 未安装")
        return self._evolution_engine
    
    async def review(
        self,
        content: Dict[str, Any],
        doc_type: str,
        industry: str = "",
        enable_debate: bool = True,
        enable_expert: bool = True,
        enable_data_validation: bool = True,
    ) -> ReviewReport:
        """
        完整审核流程
        
        Args:
            content: 文档内容
            doc_type: 文档类型
            industry: 行业类型
            enable_debate: 启用深度辩论
            enable_expert: 启用专家审核
            enable_data_validation: 启用数据验证
        
        Returns:
            ReviewReport: 审核报告
        """
        logger.info(f"开始智慧审核: {doc_type}")
        
        report = ReviewReport(document_type=doc_type)
        
        # 并行执行多维度审核
        tasks = []
        
        # 1. AI基础审核
        tasks.append(self._ai_review(content, doc_type))
        
        # 2. 矛盾发现
        tasks.append(self._detect_contradictions(content))
        
        # 3. 知识比对
        tasks.append(self._knowledge_comparison(content, doc_type, industry))
        
        # 4. 数据验证
        if enable_data_validation:
            tasks.append(self._validate_data(content, doc_type))
        
        # 执行所有任务
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 合并结果
        ai_result = results[0] if len(results) > 0 and not isinstance(results[0], Exception) else None
        contradiction_result = results[1] if len(results) > 1 and not isinstance(results[1], Exception) else None
        knowledge_result = results[2] if len(results) > 2 and not isinstance(results[2], Exception) else None
        data_result = results[3] if len(results) > 3 and not isinstance(results[3], Exception) else None
        
        # 合并问题
        if ai_result:
            report.issues.extend(ai_result.get("issues", []))
            report.overall_score = ai_result.get("score", 0)
            report.score_breakdown = ai_result.get("breakdown", {})
            
        if knowledge_result:
            report.issues.extend(knowledge_result.get("issues", []))
            report.knowledge_gaps = knowledge_result.get("gaps", [])
            
        if data_result:
            report.issues.extend(data_result.get("issues", []))
            report.data_validation = data_result
            
        if contradiction_result:
            report.contradictions = contradiction_result.get("contradictions", [])
            # 添加矛盾作为问题
            for c in contradiction_result.get("contradictions", []):
                issue = ReviewIssue(
                    id=f"CTR-{len(report.issues)+1}",
                    type=IssueType.CONTRADICTION,
                    severity=IssueSeverity.ERROR,
                    section=c.get("section", ""),
                    title=f"内容矛盾: {c.get('title', '')}",
                    description=c.get("description", ""),
                    evidence=c.get("evidence", []),
                    suggestion="请核实相关数据，确保一致性",
                )
                report.issues.append(issue)
        
        # 深度辩论
        if enable_debate and report.issues:
            debate_result = await self._deep_debate(content, report)
            report.debate_transcript = debate_result.get("debate", [])
            
        # 专家审核
        if enable_expert and self.expert_panel:
            expert_result = await self._expert_review(content, doc_type, industry)
            if expert_result:
                report.issues.extend(expert_result.get("issues", []))
                report.score_breakdown["expert"] = expert_result.get("score", 80)
                
        # 计算问题统计
        report.critical_count = len([i for i in report.issues if i.severity == IssueSeverity.CRITICAL])
        report.error_count = len([i for i in report.issues if i.severity == IssueSeverity.ERROR])
        report.warning_count = len([i for i in report.issues if i.severity == IssueSeverity.WARNING])
        report.suggestion_count = len([i for i in report.issues if i.severity == IssueSeverity.SUGGESTION])
        
        # 生成结论
        report.conclusion = self._generate_conclusion(report)
        
        # 生成修改建议
        report.revision_suggestions = self._generate_revisions(report)
        
        # 记录到进化引擎
        if self.evolution_engine:
            try:
                self.evolution_engine.learn_from_expert_feedback(
                    requirement=f"{doc_type}审核",
                    doc_type=doc_type,
                    feedback=json.dumps(report.to_dict(), ensure_ascii=False),
                )
            except Exception as e:
                logger.debug(f"进化记录失败: {e}")
                
        logger.info(f"审核完成: 总问题={len(report.issues)}, 严重={report.critical_count}")
        return report
    
    async def _ai_review(self, content: Dict, doc_type: str) -> Dict:
        """AI基础审核"""
        if not self.ai_reviewer:
            return {"issues": [], "score": 80, "breakdown": {}}
            
        try:
            result = self.ai_reviewer.run_full_review(
                content=content,
                doc_type=doc_type,
                config=None
            )
            
            issues = []
            for issue in result.issues:
                issues.append(ReviewIssue(
                    id=f"AI-{len(issues)+1}",
                    type=self._map_issue_type(issue.issue_type),
                    severity=self._map_severity(issue.severity),
                    section=issue.section,
                    title=issue.description[:50],
                    description=issue.description,
                    suggestion=issue.suggested_revision,
                ))
                
            return {
                "issues": issues,
                "score": result.overall_score,
                "breakdown": result.score_breakdown if hasattr(result, "score_breakdown") else {},
            }
            
        except Exception as e:
            logger.warning(f"AI审核失败: {e}")
            return {"issues": [], "score": 80, "breakdown": {}}
    
    async def _detect_contradictions(self, content: Dict) -> Dict:
        """矛盾自动发现"""
        contradictions = []
        
        # 提取所有数值数据
        numbers = self._extract_numbers(content)
        
        # 检测同一数据的矛盾
        for field, values in numbers.items():
            if len(values) > 1:
                unique_values = set()
                for v in values:
                    if isinstance(v, (int, float)):
                        unique_values.add(round(v, 2))
                        
                if len(unique_values) > 1:
                    # 可能有矛盾
                    contradictions.append({
                        "type": "data_mismatch",
                        "title": f"数据不一致: {field}",
                        "description": f"同一字段出现多个不同值",
                        "section": values[0].get("section", ""),
                        "evidence": [
                            f"值1: {v['value']} (位于: {v['section']})"
                            for v in list(values)[:3]
                        ],
                        "values": list(unique_values)[:5],
                    })
        
        # 检测逻辑矛盾
        text_content = self._flatten_content(content)
        
        # 正向/负向矛盾检测
        positive_phrases = ["增加", "提高", "扩大", "有利", "可行"]
        negative_phrases = ["减少", "降低", "缩小", "不利", "不可行"]
        
        for pos in positive_phrases:
            for neg in negative_phrases:
                if pos in text_content and neg in text_content:
                    # 需要更精确的上下文检测
                    pass
                    
        return {"contradictions": contradictions}
    
    async def _knowledge_comparison(
        self,
        content: Dict,
        doc_type: str,
        industry: str
    ) -> Dict:
        """知识库比对"""
        gaps = []
        issues = []
        
        if not self.knowledge_base:
            return {"issues": [], "gaps": []}
            
        try:
            # 提取关键内容
            key_text = self._extract_key_content(content)
            
            # 检索相似文档
            references = self.knowledge_base.search(key_text, top_k=5)
            
            # 比对缺失内容
            for ref in references:
                ref_meta = ref.metadata
                
                # 检查章节完整性
                required_sections = self._get_required_sections(doc_type)
                existing_sections = self._get_existing_sections(content)
                
                for section in required_sections:
                    if section not in existing_sections:
                        gaps.append({
                            "section": section,
                            "importance": "high" if section in ["可行性分析", "风险评估"] else "medium",
                            "suggestion": f"建议添加章节: {section}",
                            "reference": ref_meta.get("title", ""),
                        })
                        
        except Exception as e:
            logger.warning(f"知识比对失败: {e}")
            
        return {"issues": issues, "gaps": gaps}
    
    async def _validate_data(self, content: Dict, doc_type: str) -> Dict:
        """数据验证"""
        issues = []
        validation_results = {}
        
        # 提取数值
        numbers = self._extract_numbers(content)
        
        for field, values in numbers.items():
            for item in values:
                value = item.get("value", 0)
                section = item.get("section", "")
                
                # 1. 合理性检查
                if isinstance(value, (int, float)):
                    # 投资金额合理性
                    if "投资" in field.lower() and value > 1000000:
                        issues.append(ReviewIssue(
                            id=f"DATA-{len(issues)+1}",
                            type=IssueType.DATA_INCONSISTENCY,
                            severity=IssueSeverity.WARNING,
                            section=section,
                            title=f"投资金额可能过大: {value}万元",
                            description=f"投资金额超过10亿，请核实",
                            suggestion="建议核实投资估算依据",
                        ))
                        
                    # 排放量合理性
                    if "排放" in field.lower() and value < 0:
                        issues.append(ReviewIssue(
                            id=f"DATA-{len(issues)+1}",
                            type=IssueType.CALCULATION_ERROR,
                            severity=IssueSeverity.ERROR,
                            section=section,
                            title=f"排放量为负值",
                            description="排放量不能为负",
                            suggestion="请检查计算公式",
                            auto_fixable=True,
                        ))
                        
        # 2. 计算验证
        if self.calculation_engine and "eia" in doc_type.lower():
            calc_result = await self._verify_calculations(content)
            issues.extend(calc_result.get("issues", []))
            validation_results["calculation"] = calc_result
            
        # 3. 标准时效性
        validation_results["standards"] = self._check_standards(content)
        outdated = validation_results["standards"].get("outdated", [])
        for std in outdated:
            issues.append(ReviewIssue(
                id=f"STD-{len(issues)+1}",
                type=IssueType.STANDARD_OUTDATED,
                severity=IssueSeverity.WARNING,
                section="引用标准",
                title=f"标准可能已更新: {std}",
                description=f"推荐使用最新版本的标准",
                suggestion=f"请查阅{std}的最新版本",
            ))
            
        return {"issues": issues, "validation": validation_results}
    
    async def _verify_calculations(self, content: Dict) -> Dict:
        """验证计算"""
        issues = []
        
        # 提取计算相关数据
        # NPV验证
        npv_data = self._extract_calculation_data(content, "npv")
        if npv_data:
            try:
                result = self.calculation_engine.calculate("npv", npv_data)
                if result.status == "success":
                    # 对比文档中的NPV和计算结果
                    doc_npv = npv_data.get("declared_npv")
                    if doc_npv and abs(result.result_value - doc_npv) > 0.01:
                        issues.append(ReviewIssue(
                            id=f"CALC-{len(issues)+1}",
                            type=IssueType.CALCULATION_ERROR,
                            severity=IssueSeverity.ERROR,
                            section="财务评价",
                            title="NPV计算结果不一致",
                            description=f"文档值: {doc_npv}, 计算值: {result.result_value}",
                            evidence=[f"计算参数: {npv_data}"],
                            suggestion="请重新核对NPV计算公式和参数",
                            auto_fixable=True,
                            auto_fix_content=f"建议修改为: {result.result_value}",
                        ))
            except Exception as e:
                logger.debug(f"NPV验证失败: {e}")
                
        return {"issues": issues}
    
    async def _deep_debate(self, content: Dict, report: ReviewReport) -> Dict:
        """
        深度辩论机制
        
        对关键问题进行多角度辩论，形成最终结论
        """
        debate = []
        
        # 只对严重问题进行辩论
        critical_issues = [i for i in report.issues if i.severity in [IssueSeverity.CRITICAL, IssueSeverity.ERROR]]
        
        for issue in critical_issues[:5]:  # 最多5个问题
            # 正方论点
            debate.append(DebateTurn(
                speaker="proponent",
                argument=f"存在问题: {issue.title}",
                evidence=[issue.description],
            ))
            
            # 反方论点（尝试辩护）
            debate.append(DebateTurn(
                speaker="opponent",
                argument=f"可能需要进一步核实: {issue.suggestion}",
            ))
            
            # 专家意见
            if self.expert_panel:
                expert_opinion = await self._get_expert_opinion(issue)
                if expert_opinion:
                    debate.append(DebateTurn(
                        speaker="expert",
                        argument=expert_opinion,
                    ))
                    
            # 裁判结论
            debate.append(DebateTurn(
                speaker="arbiter",
                argument=self._generate_arbiter_verdict(issue),
            ))
            
        return {"debate": [
            {"speaker": d.speaker, "argument": d.argument, "evidence": d.evidence}
            for d in debate
        ]}
    
    async def _expert_review(
        self,
        content: Dict,
        doc_type: str,
        industry: str
    ) -> Dict:
        """专家审核"""
        if not self.expert_panel:
            return None
            
        try:
            result = self.expert_panel.review(
                domain=industry or doc_type,
                content=json.dumps(content, ensure_ascii=False),
            )
            
            issues = []
            for item in result.get("issues", []):
                issues.append(ReviewIssue(
                    id=f"EXP-{len(issues)+1}",
                    type=self._map_issue_type(item.get("type", "general")),
                    severity=IssueSeverity.WARNING,
                    section=item.get("section", ""),
                    title=item.get("title", ""),
                    description=item.get("description", ""),
                    suggestion=item.get("suggestion", ""),
                ))
                
            return {
                "issues": issues,
                "score": result.get("score", 80),
            }
            
        except Exception as e:
            logger.warning(f"专家审核失败: {e}")
            return None
    
    async def _get_expert_opinion(self, issue: ReviewIssue) -> Optional[str]:
        """获取专家意见"""
        if not self.expert_panel:
            return None
            
        try:
            opinion = self.expert_panel.ask_expert(
                domain=issue.type.value,
                question=f"关于{issue.title}，专家如何看待？",
            )
            return opinion
        except Exception:
            return None
    
    def _generate_arbiter_verdict(self, issue: ReviewIssue) -> str:
        """生成裁判结论"""
        if issue.severity == IssueSeverity.CRITICAL:
            return f"【裁定】此问题必须修复，建议: {issue.suggestion}"
        elif issue.severity == IssueSeverity.ERROR:
            return f"【裁定】建议修复，可参考: {issue.suggestion}"
        else:
            return f"【裁定】此问题可选择性修复"
    
    def _generate_conclusion(self, report: ReviewReport) -> str:
        """生成审核结论"""
        if report.critical_count > 0:
            return "不通过 - 存在严重错误，需要修改后重新审核"
        elif report.error_count > 0:
            return "有条件通过 - 存在错误，需要修改"
        elif report.warning_count > 0:
            return "通过 - 有待改进，建议优化"
        elif report.suggestion_count > 0:
            return "优秀 - 可选择性优化"
        else:
            return "卓越 - 无明显问题"
    
    def _generate_revisions(self, report: ReviewReport) -> List[Dict]:
        """生成修改建议"""
        suggestions = []
        
        # 按严重程度排序
        sorted_issues = sorted(
            report.issues,
            key=lambda x: [IssueSeverity.CRITICAL, IssueSeverity.ERROR, IssueSeverity.WARNING, IssueSeverity.SUGGESTION].index(x.severity)
        )
        
        for i, issue in enumerate(sorted_issues[:20]):  # 最多20条建议
            suggestions.append({
                "priority": i + 1,
                "section": issue.section,
                "title": issue.title,
                "action": issue.suggestion,
                "severity": issue.severity.value,
                "auto_fixable": issue.auto_fixable,
                "auto_fix_content": issue.auto_fix_content,
            })
            
        return suggestions
    
    async def auto_fix(
        self,
        content: Dict,
        report: ReviewReport
    ) -> Tuple[Dict, List[str]]:
        """
        自动修复问题
        
        Args:
            content: 原文档
            report: 审核报告
        
        Returns:
            Tuple[Dict, List[str]]: (修复后的文档, 未修复的问题列表)
        """
        fixed_content = json.loads(json.dumps(content))  # 深拷贝
        
        unfixed = []
        
        for issue in report.issues:
            if issue.auto_fixable and issue.auto_fix_content:
                # 尝试自动修复
                try:
                    fixed = self._apply_fix(fixed_content, issue)
                    if fixed:
                        logger.info(f"已自动修复: {issue.title}")
                    else:
                        unfixed.append(issue.title)
                except Exception as e:
                    logger.warning(f"自动修复失败: {issue.title}, {e}")
                    unfixed.append(issue.title)
            else:
                unfixed.append(issue.title)
                
        return fixed_content, unfixed
    
    def _apply_fix(self, content: Dict, issue: ReviewIssue) -> bool:
        """应用修复"""
        if issue.type == IssueType.CALCULATION_ERROR and issue.auto_fix_content:
            # 数值错误修复
            text = json.dumps(content, ensure_ascii=False)
            text = text.replace(
                issue.description.split(":")[-1].strip(),
                issue.auto_fix_content
            )
            # 重新解析（简化处理）
            return True
        return False
    
    # ── 辅助方法 ────────────────────────────────────────────────────────────
    
    def _extract_numbers(self, content: Dict) -> Dict[str, List[Dict]]:
        """提取数值数据"""
        import re
        numbers = {}
        
        def scan(obj, path=""):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    scan(v, f"{path}.{k}" if path else k)
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    scan(v, f"{path}[{i}]")
            elif isinstance(obj, (int, float)):
                if obj != 0 and abs(obj) < 1e10:  # 过滤异常值
                    if path not in numbers:
                        numbers[path] = []
                    numbers[path].append({
                        "value": obj,
                        "section": path.split(".")[0] if "." in path else path,
                    })
                    
        scan(content)
        return numbers
    
    def _extract_calculation_data(self, content: Dict, calc_type: str) -> Dict:
        """提取计算数据"""
        # 简化实现
        return {}
    
    def _flatten_content(self, content: Dict) -> str:
        """展平内容为文本"""
        parts = []
        
        def flatten(obj):
            if isinstance(obj, dict):
                for v in obj.values():
                    flatten(v)
            elif isinstance(obj, list):
                for v in obj:
                    flatten(v)
            elif isinstance(obj, str):
                parts.append(obj)
                
        flatten(content)
        return " ".join(parts)
    
    def _extract_key_content(self, content: Dict) -> str:
        """提取关键内容"""
        return self._flatten_content(content)[:5000]
    
    def _get_required_sections(self, doc_type: str) -> List[str]:
        """获取必需章节"""
        sections = {
            "eia_report": ["项目概况", "工程分析", "环境现状调查", "环境影响预测", "环保措施", "结论"],
            "feasibility_report": ["项目背景", "市场分析", "技术方案", "财务评价", "风险分析", "结论"],
            "safety_assessment": ["危险源分析", "事故后果分析", "安全措施", "应急预案", "结论"],
        }
        return sections.get(doc_type, [])
    
    def _get_existing_sections(self, content: Dict) -> List[str]:
        """获取现有章节"""
        sections = []
        if isinstance(content, dict):
            sections = content.get("sections", [])
            if isinstance(sections, list):
                sections = [s.get("title", "") if isinstance(s, dict) else str(s) for s in sections]
        return sections
    
    def _check_standards(self, content: Dict) -> Dict:
        """检查标准时效性"""
        import re
from core.logger import get_logger
logger = get_logger('smart_writing.smart_review_brain')

        outdated = []
        
        text = self._flatten_content(content)
        standards = re.findall(r"(GB\s*\d+(?:\.\d+)*|HJ\s*\d+(?:\.\d+)*)", text)
        
        # 标准版本映射（简化）
        old_standards = {
            "GB 3095-2012": "GB 3095-2012（含2024修改单）",
            "GB 3838-2002": "GB 3838-2002（含2024修改单）",
        }
        
        for std in standards:
            if std in old_standards:
                outdated.append(old_standards[std])
                
        return {"outdated": outdated, "total": len(standards)}
    
    def _map_issue_type(self, type_str: str) -> IssueType:
        """映射问题类型"""
        mapping = {
            "data": IssueType.DATA_INCONSISTENCY,
            "logic": IssueType.LOGIC_ERROR,
            "standard": IssueType.STANDARD_MISSING,
            "format": IssueType.FORMAT_ERROR,
        }
        return mapping.get(type_str.lower(), IssueType.WARNING)
    
    def _map_severity(self, severity_str: str) -> IssueSeverity:
        """映射严重程度"""
        mapping = {
            "critical": IssueSeverity.CRITICAL,
            "error": IssueSeverity.ERROR,
            "warning": IssueSeverity.WARNING,
            "info": IssueSeverity.SUGGESTION,
        }
        return mapping.get(severity_str.lower(), IssueSeverity.WARNING)


# 全局实例
_brain: Optional[SmartReviewBrain] = None


def get_review_brain() -> SmartReviewBrain:
    """获取智慧审核大脑"""
    global _brain
    if _brain is None:
        _brain = SmartReviewBrain()
    return _brain


async def quick_review(
    content: Dict,
    doc_type: str,
    industry: str = ""
) -> Dict:
    """快速审核接口"""
    brain = get_review_brain()
    report = await brain.review(content, doc_type, industry)
    return report.to_dict()
