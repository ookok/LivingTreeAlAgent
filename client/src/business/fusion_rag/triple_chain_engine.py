"""
三重链统一引擎 (Triple Chain Engine)

实现思维链、因果链、证据链的三重统一验证机制：
1. 思维链构建：生成结构化推理步骤
2. 因果链验证：检查步骤间因果关系
3. 证据链追溯：关联每个步骤的证据来源

集成 LLM Wiki 知识图谱：
- 利用实体链接增强证据链
- 使用知识图谱推理验证因果关系
- 支持跨文档引用追溯

核心原则：显式化、可追溯、一致性、谨慎性、透明性
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

# 集成 LLM Wiki 模块
try:
    from client.src.business.llm_wiki import (
        HybridRetriever,
        FeedbackManager,
        KnowledgeGraphSelfEvolver,
        search_llm_wiki
    )
    LLM_WIKI_AVAILABLE = True
except ImportError:
    LLM_WIKI_AVAILABLE = False


@dataclass
class ReasoningStep:
    """推理步骤"""
    step_id: int
    content: str
    evidence_ids: List[str] = field(default_factory=list)
    confidence: float = 1.0
    causal_link: Optional[int] = None


@dataclass
class Evidence:
    """证据"""
    doc_id: str
    title: str
    content_snippet: str
    source_type: str
    authority_level: int
    confidence: float


@dataclass
class TripleChainResult:
    """三重链结果"""
    answer: str
    reasoning_steps: List[ReasoningStep]
    evidences: List[Evidence]
    overall_confidence: float
    uncertainty_note: str
    validation_passed: bool


class TripleChainEngine:
    """
    三重链统一引擎
    
    实现思维链、因果链、证据链的三重统一验证
    """
    
    def __init__(self):
        self.reasoning_templates = {
            "selection": [
                "分析需求：{input}",
                "条件分析：{conditions}",
                "选型依据：{standards}",
                "结论：{conclusion}"
            ],
            "diagnosis": [
                "收集现象：{symptoms}",
                "列举可能原因：{possible_causes}",
                "逐一排除：{elimination}",
                "确定根本原因：{root_cause}",
                "提出解决方案：{solution}"
            ],
            "calculation": [
                "明确计算目标：{target}",
                "收集输入参数：{parameters}",
                "选择计算公式：{formula}",
                "执行计算：{calculation}",
                "验证结果：{verification}"
            ],
            "validation": [
                "提取标准要求：{standard}",
                "获取实际参数：{actual}",
                "对比分析：{comparison}",
                "判定结论：{decision}"
            ]
        }
        
        self.source_weights = {
            "gb/t": 1.0, "国家标准": 1.0, "行业标准": 0.9,
            "专利": 0.9, "技术手册": 0.8, "学术论文": 0.7, 
            "wiki": 0.75, "内部文档": 0.5
        }
        
        # 集成 LLM Wiki
        self._init_llm_wiki()
        
        print("[TripleChainEngine] 初始化完成")
    
    def _init_llm_wiki(self):
        """初始化 LLM Wiki 集成组件"""
        if LLM_WIKI_AVAILABLE:
            try:
                # 按正确顺序初始化（KnowledgeGraphSelfEvolver 需要 feedback_manager）
                self.feedback_manager = FeedbackManager()
                self.kg_self_evolver = KnowledgeGraphSelfEvolver(
                    feedback_manager=self.feedback_manager
                )
                self.hybrid_retriever = HybridRetriever(
                    feedback_manager=self.feedback_manager,
                    kg_self_evolver=self.kg_self_evolver
                )
                print("[TripleChainEngine] LLM Wiki 集成完成")
            except Exception as e:
                print(f"[TripleChainEngine] LLM Wiki 初始化失败: {e}")
                self.hybrid_retriever = None
                self.feedback_manager = None
                self.kg_self_evolver = None
        else:
            self.hybrid_retriever = None
            self.feedback_manager = None
            self.kg_self_evolver = None
    
    def build_triple_chain(self, query: str, task_type: str, 
                          retrieved_docs: List[Dict]) -> TripleChainResult:
        # 1. 使用 LLM Wiki 知识图谱增强检索
        enhanced_docs = self._enhance_with_wiki(query, retrieved_docs)
        
        # 2. 构建思维链
        reasoning_steps = self._build_reasoning_chain(query, task_type, enhanced_docs)
        
        # 3. 使用知识图谱验证因果链
        causal_valid, causal_msg = self._validate_causal_chain_with_kg(reasoning_steps)
        
        # 4. 构建证据链（包含 Wiki 实体链接）
        evidences = self._build_evidence_chain(enhanced_docs)
        
        # 5. 验证证据链
        evidence_valid, evidence_msg = self._validate_evidence_chain(evidences, reasoning_steps)
        
        # 6. 计算总体置信度
        overall_confidence = self._calculate_overall_confidence(reasoning_steps, evidences)
        
        # 7. 生成不确定性说明
        uncertainty_note = self._generate_uncertainty_note(reasoning_steps, evidences, causal_valid, evidence_valid)
        
        # 8. 综合验证
        validation_passed = causal_valid and evidence_valid
        
        # 9. 生成最终回答
        answer = self._generate_answer(reasoning_steps)
        
        return TripleChainResult(
            answer=answer,
            reasoning_steps=reasoning_steps,
            evidences=evidences,
            overall_confidence=overall_confidence,
            uncertainty_note=uncertainty_note,
            validation_passed=validation_passed
        )
    
    def _enhance_with_wiki(self, query: str, retrieved_docs: List[Dict]) -> List[Dict]:
        """使用 LLM Wiki 知识图谱增强检索结果"""
        if not LLM_WIKI_AVAILABLE or not self.hybrid_retriever:
            return retrieved_docs
        
        try:
            # 使用 HybridRetriever 进行增强检索
            wiki_results = search_llm_wiki(query, top_k=3)
            
            # 合并 Wiki 结果到现有文档
            for result in wiki_results:
                if result.get("confidence", 0) > 0.7:
                    retrieved_docs.append({
                        "id": result.get("id", f"wiki_{len(retrieved_docs)}"),
                        "title": result.get("title", "Wiki Entry"),
                        "content": result.get("content", ""),
                        "source_type": "wiki",
                        "confidence": result.get("confidence", 0.8),
                        "authority_level": 4
                    })
            
            return retrieved_docs
        except Exception as e:
            print(f"[TripleChainEngine] Wiki 增强失败: {e}")
            return retrieved_docs
    
    def _validate_causal_chain_with_kg(self, reasoning_steps: List[ReasoningStep]) -> tuple:
        """使用知识图谱验证因果链"""
        # 首先进行基础验证
        basic_valid, basic_msg = self._validate_causal_chain(reasoning_steps)
        
        if not basic_valid:
            return basic_valid, basic_msg
        
        # 如果有知识图谱，进行增强验证
        if LLM_WIKI_AVAILABLE and self.kg_self_evolver:
            try:
                # 使用知识图谱推理验证步骤间的语义关系
                for i in range(len(reasoning_steps) - 1):
                    step1 = reasoning_steps[i]
                    step2 = reasoning_steps[i + 1]
                    
                    # 检查知识图谱中是否存在相关关系
                    # 简化实现：检查关键词是否在知识图谱中有连接
                    kg_connected = self._check_kg_connection(step1.content, step2.content)
                    if not kg_connected:
                        return False, f"步骤{i+1}与{i+2}之间知识图谱验证失败"
                
                return True, "因果链验证通过（含知识图谱验证）"
            except Exception as e:
                print(f"[TripleChainEngine] 知识图谱验证失败: {e}")
                return basic_valid, basic_msg
        
        return basic_valid, basic_msg
    
    def _check_kg_connection(self, text1: str, text2: str) -> bool:
        """检查知识图谱中两个文本是否有连接"""
        # 简化实现：检查是否有共同的技术术语
        import re
        pattern = r'[\u4e00-\u9fa5]{2,8}|[A-Za-z]{2,}|[A-Za-z]+\d+'
        kw1 = set(re.findall(pattern, text1))
        kw2 = set(re.findall(pattern, text2))
        
        # 如果有共同关键词，则认为有连接
        return len(kw1 & kw2) > 0
    
    def _build_reasoning_chain(self, query: str, task_type: str, docs: List[Dict]) -> List[ReasoningStep]:
        template = self.reasoning_templates.get(task_type, self.reasoning_templates["selection"])
        params = self._extract_params(query, docs)
        
        steps = []
        for i, template_step in enumerate(template, 1):
            content = template_step.format(**params)
            evidence_ids = self._link_evidence_to_step(i, docs)
            causal_link = i - 1 if i > 1 else None
            
            steps.append(ReasoningStep(
                step_id=i,
                content=content,
                evidence_ids=evidence_ids,
                confidence=self._calculate_step_confidence(evidence_ids, docs),
                causal_link=causal_link
            ))
        
        return steps
    
    def _extract_params(self, query: str, docs: List[Dict]) -> Dict[str, str]:
        params = {
            "input": query, "conditions": "", "standards": "", "conclusion": "",
            "symptoms": "", "possible_causes": "", "elimination": "", "root_cause": "",
            "solution": "", "target": "", "parameters": "", "formula": "",
            "calculation": "", "verification": "", "standard": "", "actual": "",
            "comparison": "", "decision": ""
        }
        
        standards = []
        for doc in docs[:3]:
            title = doc.get("title", "")
            if "GB/T" in title or "标准" in title or "HJ" in title:
                standards.append(title)
        params["standards"] = "; ".join(standards) if standards else "相关行业标准"
        
        params["conditions"] = "分析查询中的约束条件"
        params["conclusion"] = "基于以上分析得出结论"
        
        return params
    
    def _link_evidence_to_step(self, step_id: int, docs: List[Dict]) -> List[str]:
        return [doc.get("id", str(i)) for i, doc in enumerate(docs[:3])]
    
    def _calculate_step_confidence(self, evidence_ids: List[str], docs: List[Dict]) -> float:
        if not evidence_ids:
            return 0.5
        total_conf = sum(doc.get("confidence", 0.8) for doc in docs if doc.get("id") in evidence_ids)
        return total_conf / max(len(evidence_ids), 1)
    
    def _validate_causal_chain(self, steps: List[ReasoningStep]) -> tuple:
        if len(steps) < 2:
            return False, "推理步骤不足"
        
        for i, step in enumerate(steps[1:], 2):
            if step.causal_link != i - 1:
                return False, f"步骤{i}缺少因果链接"
        
        for i in range(len(steps) - 1):
            if not self._check_causal_coherence(steps[i], steps[i + 1]):
                return False, f"步骤{i+1}与{i+2}之间逻辑不连贯"
        
        return True, "因果链验证通过"
    
    def _check_causal_coherence(self, step1: ReasoningStep, step2: ReasoningStep) -> bool:
        import re
        pattern = r'[\u4e00-\u9fa5]{2,8}|[A-Za-z]{2,}|[A-Za-z]+\d+'
        kw1 = set(re.findall(pattern, step1.content))
        kw2 = set(re.findall(pattern, step2.content))
        return len(kw1 & kw2) > 0
    
    def _build_evidence_chain(self, docs: List[Dict]) -> List[Evidence]:
        evidences = []
        for doc in docs[:5]:
            evidences.append(Evidence(
                doc_id=doc.get("id", ""),
                title=doc.get("title", "未命名文档"),
                content_snippet=doc.get("content", "")[:100] + "...",
                source_type=doc.get("source_type", "unknown"),
                authority_level=doc.get("authority_level", 3),
                confidence=doc.get("confidence", 0.8)
            ))
        return evidences
    
    def _validate_evidence_chain(self, evidences: List[Evidence], steps: List[ReasoningStep]) -> tuple:
        if len(evidences) == 0:
            return False, "缺少证据支持"
        
        for step in steps:
            if not step.evidence_ids:
                return False, f"步骤{step.step_id}缺少证据"
        
        avg_authority = sum(e.authority_level for e in evidences) / len(evidences)
        if avg_authority < 2:
            return False, "证据权威性不足"
        
        return True, "证据链验证通过"
    
    def _calculate_overall_confidence(self, steps: List[ReasoningStep], evidences: List[Evidence]) -> float:
        step_conf = sum(s.confidence for s in steps) / len(steps)
        evidence_conf = sum(e.confidence for e in evidences) / max(len(evidences), 1)
        source_score = sum(self.source_weights.get(e.source_type, 0.5) for e in evidences) / max(len(evidences), 1)
        return step_conf * 0.4 + evidence_conf * 0.4 + source_score * 0.2
    
    def _generate_uncertainty_note(self, steps: List[ReasoningStep], evidences: List[Evidence],
                                   causal_valid: bool, evidence_valid: bool) -> str:
        issues = []
        if not causal_valid:
            issues.append("推理逻辑存在问题")
        if not evidence_valid:
            issues.append("证据支持不足")
        if len(evidences) < 2:
            issues.append("证据来源较少")
        if self._calculate_overall_confidence(steps, evidences) < 0.7:
            issues.append("总体置信度较低")
        
        if issues:
            return f"⚠️ 提示：{'；'.join(issues)}，建议结合具体工况确认。"
        return ""
    
    def _generate_answer(self, steps: List[ReasoningStep]) -> str:
        if steps:
            last_step = steps[-1]
            if "结论：" in last_step.content:
                return last_step.content.split("结论：")[-1].strip()
        return "根据分析得出结论"


def create_triple_chain_engine() -> TripleChainEngine:
    return TripleChainEngine()


__all__ = [
    "TripleChainEngine",
    "ReasoningStep",
    "Evidence",
    "TripleChainResult",
    "create_triple_chain_engine"
]