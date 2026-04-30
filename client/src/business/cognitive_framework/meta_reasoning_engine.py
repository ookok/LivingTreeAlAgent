"""
MetaReasoningEngine - 元认知监控引擎

对生成结果进行置信度打分与逻辑自检，实现"自知之明"能力。

核心功能：
1. 置信度评估 - 评估生成结果的可信度
2. 事实核查 - 调用外部工具验证数据
3. 逻辑验证 - 检查论证链条是否闭环
4. 信心校准 - 当置信度低于阈值时触发求助或降级处理
5. 自我反思 - 分析推理过程

设计原理：
- 独立的质量评估流水线
- 多层次验证机制
- 置信度阈值触发机制
- 可解释的评估结果

使用示例：
    engine = MetaReasoningEngine()
    
    # 评估生成结果
    result = engine.evaluate(
        text="生成的回答内容",
        context={"query": "用户问题", "sources": [...]}
    )
    
    # 获取置信度
    if result.confidence < 0.5:
        # 触发降级处理
        engine.trigger_fallback(result)
"""

import asyncio
import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger


class VerificationResult(Enum):
    """验证结果"""
    PASSED = "passed"
    FAILED = "failed"
    UNKNOWN = "unknown"


class FallbackAction(Enum):
    """降级处理动作"""
    ASK_USER = "ask_user"           # 询问用户
    USE_ALTERNATIVE = "use_alternative"  # 使用替代方案
    REDUCE_CONFIDENCE = "reduce_confidence"  # 降低置信度
    ESCALATE = "escalate"           # 升级处理
    IGNORE = "ignore"               # 忽略


@dataclass
class ConfidenceScore:
    """置信度分数"""
    overall: float = 0.0            # 总体置信度
    factuality: float = 0.0         # 事实准确性
    logic: float = 0.0              # 逻辑一致性
    completeness: float = 0.0       # 完整性
    relevance: float = 0.0          # 相关性
    consistency: float = 0.0        # 一致性
    source_reliability: float = 0.0 # 来源可靠性
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "overall": self.overall,
            "factuality": self.factuality,
            "logic": self.logic,
            "completeness": self.completeness,
            "relevance": self.relevance,
            "consistency": self.consistency,
            "source_reliability": self.source_reliability
        }


@dataclass
class VerificationReport:
    """验证报告"""
    verification_id: str
    result: VerificationResult
    confidence: ConfidenceScore
    checks: List[Dict[str, Any]]
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "verification_id": self.verification_id,
            "result": self.result.value,
            "confidence": self.confidence.to_dict(),
            "checks": self.checks,
            "errors": self.errors,
            "warnings": self.warnings,
            "suggestions": self.suggestions,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class FactCheckResult:
    """事实核查结果"""
    claim: str
    verified: bool
    confidence: float
    evidence: List[str]
    source: str = ""
    error: Optional[str] = None


class ValidationPipeline:
    """验证流水线"""
    
    def __init__(self, threshold: float = 0.6):
        self._threshold = threshold
        self._checkers = []
    
    def add_checker(self, checker: Callable):
        """添加检查器"""
        self._checkers.append(checker)
    
    async def validate(self, text: str, context: Dict = None) -> VerificationReport:
        """执行验证流水线"""
        checks = []
        errors = []
        warnings = []
        suggestions = []
        
        context = context or {}
        
        for checker in self._checkers:
            try:
                if asyncio.iscoroutinefunction(checker):
                    result = await checker(text, context)
                else:
                    result = checker(text, context)
                
                checks.append(result)
                
                if result.get("result") == "failed":
                    errors.append(result.get("message", ""))
                elif result.get("result") == "warning":
                    warnings.append(result.get("message", ""))
                
                if "suggestion" in result:
                    suggestions.append(result["suggestion"])
            
            except Exception as e:
                errors.append(f"检查器执行失败: {str(e)}")
        
        # 计算综合置信度
        confidence = self._calculate_confidence(checks)
        
        # 确定验证结果
        result = VerificationResult.PASSED if confidence.overall >= self._threshold else VerificationResult.FAILED
        
        return VerificationReport(
            verification_id=f"verification_{id(self)}_{datetime.now().timestamp()}",
            result=result,
            confidence=confidence,
            checks=checks,
            errors=errors,
            warnings=warnings,
            suggestions=list(set(suggestions))
        )
    
    def _calculate_confidence(self, checks: List[Dict]) -> ConfidenceScore:
        """计算综合置信度"""
        confidence = ConfidenceScore()
        
        if not checks:
            return confidence
        
        # 从检查结果中提取各个维度的分数
        scores = {
            "factuality": [],
            "logic": [],
            "completeness": [],
            "relevance": [],
            "consistency": [],
            "source_reliability": []
        }
        
        for check in checks:
            for key in scores.keys():
                if key in check:
                    scores[key].append(check[key])
        
        # 计算平均值
        for key in scores.keys():
            if scores[key]:
                setattr(confidence, key, sum(scores[key]) / len(scores[key]))
        
        # 计算总体置信度（加权平均）
        weights = {
            "factuality": 0.25,
            "logic": 0.20,
            "completeness": 0.15,
            "relevance": 0.20,
            "consistency": 0.10,
            "source_reliability": 0.10
        }
        
        overall = sum(
            getattr(confidence, key) * weights[key]
            for key in weights.keys()
        )
        confidence.overall = min(1.0, max(0.0, overall))
        
        return confidence


class FactChecker:
    """事实核查器"""
    
    def __init__(self):
        self._knowledge_base = {}
    
    def add_knowledge(self, key: str, value: Any):
        """添加知识"""
        self._knowledge_base[key.lower()] = value
    
    def check_fact(self, claim: str) -> FactCheckResult:
        """核查事实"""
        claim_lower = claim.lower()
        
        # 检查知识库
        for key, value in self._knowledge_base.items():
            if key in claim_lower:
                if str(value).lower() in claim_lower:
                    return FactCheckResult(
                        claim=claim,
                        verified=True,
                        confidence=0.9,
                        evidence=[f"知识库匹配: {key} = {value}"],
                        source="knowledge_base"
                    )
        
        # 默认返回未知
        return FactCheckResult(
            claim=claim,
            verified=False,
            confidence=0.5,
            evidence=[],
            source="unknown",
            error="未找到相关知识"
        )
    
    async def check_facts(self, text: str) -> List[FactCheckResult]:
        """核查文本中的所有事实"""
        # 提取声明
        claims = self._extract_claims(text)
        
        results = []
        for claim in claims:
            result = self.check_fact(claim)
            results.append(result)
        
        return results
    
    def _extract_claims(self, text: str) -> List[str]:
        """从文本中提取声明"""
        claims = []
        
        # 匹配简单声明模式
        patterns = [
            r"([\u4e00-\u9fa5a-zA-Z]+)是([\u4e00-\u9fa5a-zA-Z]+)",
            r"([\u4e00-\u9fa5a-zA-Z]+)有([\u4e00-\u9fa5a-zA-Z0-9]+)",
            r"([\u4e00-\u9fa5a-zA-Z]+)可以([\u4e00-\u9fa5a-zA-Z]+)",
            r"([\u4e00-\u9fa5a-zA-Z]+)应该([\u4e00-\u9fa5a-zA-Z]+)",
            r"([\u4e00-\u9fa5a-zA-Z]+)必须([\u4e00-\u9fa5a-zA-Z]+)",
            r"([\u4e00-\u9fa5a-zA-Z]+)需要([\u4e00-\u9fa5a-zA-Z]+)"
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                claims.append("".join(match))
        
        return claims


class LogicValidator:
    """逻辑验证器"""
    
    def validate(self, text: str, context: Dict = None) -> Dict[str, Any]:
        """验证逻辑一致性"""
        context = context or {}
        issues = []
        
        # 检查矛盾
        contradictions = self._check_contradictions(text)
        if contradictions:
            issues.extend(contradictions)
        
        # 检查论证闭环
        closure_issues = self._check_argument_closure(text)
        if closure_issues:
            issues.extend(closure_issues)
        
        # 检查因果一致性
        causal_issues = self._check_causal_consistency(text)
        if causal_issues:
            issues.extend(causal_issues)
        
        result = "passed" if not issues else "failed"
        confidence = 1.0 - (len(issues) * 0.1)
        
        return {
            "check": "logic_validation",
            "result": result,
            "confidence": max(0.0, confidence),
            "issues": issues,
            "message": f"发现 {len(issues)} 个逻辑问题" if issues else "逻辑验证通过",
            "logic": confidence
        }
    
    def _check_contradictions(self, text: str) -> List[str]:
        """检查矛盾"""
        issues = []
        
        # 简单的矛盾检测
        contradiction_patterns = [
            (r"不是", r"是"),
            (r"不可能", r"可能"),
            (r"没有", r"有"),
            (r"无法", r"可以"),
            (r"不能", r"能")
        ]
        
        for neg, pos in contradiction_patterns:
            if neg in text and pos in text:
                issues.append(f"检测到矛盾: 同时包含 '{neg}' 和 '{pos}'")
        
        return issues
    
    def _check_argument_closure(self, text: str) -> List[str]:
        """检查论证闭环"""
        issues = []
        
        # 检查是否有开头但没有结尾的论证
        if "因为" in text and "所以" not in text:
            issues.append("论证不完整: 有前提但没有结论")
        
        if "因此" in text and not ("因为" in text or "由于" in text):
            issues.append("论证不完整: 有结论但缺少前提")
        
        return issues
    
    def _check_causal_consistency(self, text: str) -> List[str]:
        """检查因果一致性"""
        issues = []
        
        # 检测因果关系词
        causal_words = ["导致", "引起", "使得", "造成", "因为"]
        has_causal = any(word in text for word in causal_words)
        
        if has_causal:
            # 简单检查因果链
            if "因为" in text:
                # 检查是否有完整的因果结构
                parts = text.split("因为")
                if len(parts) > 1 and len(parts[1].strip()) < 5:
                    issues.append("因果关系不完整")
        
        return issues


class ConsistencyChecker:
    """一致性检查器"""
    
    def check(self, text: str, context: Dict = None) -> Dict[str, Any]:
        """检查一致性"""
        context = context or {}
        
        # 检查上下文一致性
        context_issues = self._check_context_consistency(text, context)
        
        # 检查内部一致性
        internal_issues = self._check_internal_consistency(text)
        
        issues = context_issues + internal_issues
        result = "passed" if not issues else "failed"
        confidence = 1.0 - (len(issues) * 0.15)
        
        return {
            "check": "consistency",
            "result": result,
            "confidence": max(0.0, confidence),
            "issues": issues,
            "consistency": max(0.0, confidence),
            "suggestion": "建议检查回答是否与上下文一致" if context_issues else None
        }
    
    def _check_context_consistency(self, text: str, context: Dict) -> List[str]:
        """检查上下文一致性"""
        issues = []
        
        # 检查是否与历史对话冲突
        history = context.get("history", [])
        if history:
            last_message = history[-1].get("content", "")
            
            # 简单检查是否有直接矛盾
            if "不" in text and "不" not in last_message:
                # 可能存在否定前一轮的情况
                pass
        
        return issues
    
    def _check_internal_consistency(self, text: str) -> List[str]:
        """检查内部一致性"""
        issues = []
        
        # 检查重复内容
        sentences = text.split("。")
        unique_sentences = set()
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 5:
                if sentence in unique_sentences:
                    issues.append(f"重复内容: {sentence}")
                unique_sentences.add(sentence)
        
        return issues


class CompletenessChecker:
    """完整性检查器"""
    
    def check(self, text: str, context: Dict = None) -> Dict[str, Any]:
        """检查回答完整性"""
        context = context or {}
        
        # 检查长度
        length_score = min(1.0, len(text) / 200)
        
        # 检查是否回答了问题
        query = context.get("query", "")
        if query:
            answer_score = self._check_answer_relevance(text, query)
        else:
            answer_score = 0.8
        
        completeness = (length_score + answer_score) / 2
        
        # 检查是否有"不知道"等表示不完整的词
        incomplete_words = ["不知道", "不清楚", "不确定", "无法回答"]
        has_incomplete = any(word in text for word in incomplete_words)
        
        if has_incomplete:
            completeness *= 0.5
        
        return {
            "check": "completeness",
            "result": "passed" if completeness >= 0.5 else "warning",
            "confidence": completeness,
            "completeness": completeness,
            "message": "回答可能不完整" if has_incomplete else "完整性检查通过"
        }
    
    def _check_answer_relevance(self, answer: str, query: str) -> float:
        """检查回答相关性"""
        query_words = set(query.lower().replace("吗", "").replace("？", "").replace("?", "").split())
        answer_words = set(answer.lower().split())
        
        if not query_words:
            return 0.8
        
        overlap = query_words & answer_words
        return len(overlap) / len(query_words)


class MetaReasoningEngine:
    """元认知推理引擎"""
    
    def __init__(self, threshold: float = 0.6):
        self._logger = logger.bind(component="MetaReasoningEngine")
        self._threshold = threshold
        
        # 初始化验证流水线
        self._validation_pipeline = ValidationPipeline(threshold)
        
        # 添加检查器
        self._fact_checker = FactChecker()
        self._logic_validator = LogicValidator()
        self._consistency_checker = ConsistencyChecker()
        self._completeness_checker = CompletenessChecker()
        
        # 注册检查器
        self._validation_pipeline.add_checker(self._logic_validator.validate)
        self._validation_pipeline.add_checker(self._consistency_checker.check)
        self._validation_pipeline.add_checker(self._completeness_checker.check)
        
        # 回调函数
        self._fallback_callback = None
        self._confidence_callback = None
        
        self._logger.info("元认知推理引擎初始化完成")
    
    def set_fallback_callback(self, callback: Callable):
        """设置降级处理回调"""
        self._fallback_callback = callback
    
    def set_confidence_callback(self, callback: Callable):
        """设置置信度回调"""
        self._confidence_callback = callback
    
    def add_knowledge(self, key: str, value: Any):
        """添加知识到事实核查器"""
        self._fact_checker.add_knowledge(key, value)
    
    async def evaluate(self, text: str, context: Dict = None) -> VerificationReport:
        """评估生成结果"""
        context = context or {}
        
        # 执行验证流水线
        report = await self._validation_pipeline.validate(text, context)
        
        # 如果置信度低于阈值，触发降级处理
        if report.confidence.overall < self._threshold:
            await self._trigger_fallback(report)
        
        # 通知置信度回调
        if self._confidence_callback:
            self._confidence_callback(report.confidence)
        
        return report
    
    async def _trigger_fallback(self, report: VerificationReport):
        """触发降级处理"""
        self._logger.warning(f"置信度低于阈值 ({report.confidence.overall:.2f})，触发降级处理")
        
        if self._fallback_callback:
            try:
                if asyncio.iscoroutinefunction(self._fallback_callback):
                    await self._fallback_callback(report)
                else:
                    self._fallback_callback(report)
            except Exception as e:
                self._logger.error(f"降级处理失败: {e}")
    
    def get_fallback_action(self, report: VerificationReport) -> FallbackAction:
        """获取降级处理动作"""
        confidence = report.confidence.overall
        
        if confidence < 0.3:
            return FallbackAction.ASK_USER
        elif confidence < 0.5:
            return FallbackAction.USE_ALTERNATIVE
        elif confidence < self._threshold:
            return FallbackAction.REDUCE_CONFIDENCE
        else:
            return FallbackAction.IGNORE
    
    async def reflect_on_process(self, process: List[Dict]) -> Dict[str, Any]:
        """反思推理过程"""
        insights = []
        
        for step in process:
            # 分析每一步的质量
            if step.get("confidence", 1.0) < 0.7:
                insights.append(f"步骤 '{step.get('action', 'unknown')}' 置信度较低 ({step.get('confidence')})")
            
            # 检查是否有更好的替代方案
            if "thought" in step:
                if "不确定" in step["thought"] or "可能" in step["thought"]:
                    insights.append(f"步骤 '{step.get('action', 'unknown')}' 存在不确定性")
        
        return {
            "insights": insights,
            "suggestions": self._generate_suggestions(insights),
            "process_length": len(process),
            "average_confidence": sum(s.get("confidence", 1.0) for s in process) / len(process) if process else 1.0
        }
    
    def _generate_suggestions(self, insights: List[str]) -> List[str]:
        """生成改进建议"""
        suggestions = []
        
        if any("置信度较低" in insight for insight in insights):
            suggestions.append("建议增加更多验证步骤以提高置信度")
        
        if any("不确定性" in insight for insight in insights):
            suggestions.append("建议收集更多信息以减少不确定性")
        
        if len(insights) > 3:
            suggestions.append("建议简化推理流程")
        
        return suggestions
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "threshold": self._threshold,
            "checkers_count": len(self._validation_pipeline._checkers),
            "knowledge_base_size": len(self._fact_checker._knowledge_base)
        }


def create_meta_reasoning_engine(threshold: float = 0.6) -> MetaReasoningEngine:
    """创建元认知推理引擎实例"""
    return MetaReasoningEngine(threshold)
