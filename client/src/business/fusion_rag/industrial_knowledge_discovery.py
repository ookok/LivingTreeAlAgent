"""
工业知识发现系统 (Industrial Knowledge Discovery System)

整合优化的知识发现核心模块：
1. 源头治理层：数据准入、元数据tagging、术语归一化
2. 检索对齐层：混合检索、行业过滤、上下文改写
3. 输出验证层：多维度相关性打分、来源溯源、不确定性提示
4. 持续进化层：负反馈学习、专家校准、图谱更新

核心原则：宁可召回不足，不可幻觉泛滥
"""

import json
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class DiscoveryResult:
    """知识发现结果"""
    query: str
    normalized_query: str
    documents: List["RetrievedDocument"]
    final_answer: str
    reasoning: List[str]
    uncertainty: float
    sources: List[str]
    confidence_score: float


@dataclass
class RetrievedDocument:
    """检索到的文档"""
    doc_id: str
    title: str
    content: str
    tier: int
    source_type: str
    authority_level: int
    similarity_score: float
    tier_score: float
    final_score: float
    industry_match: bool


@dataclass
class GovernanceStats:
    """治理统计"""
    total_docs_checked: int = 0
    passed_docs: int = 0
    rejected_docs: int = 0
    pass_rate: float = 0.0
    industry_match_rate: float = 0.0
    hallucination_rate: float = 0.0
    user_acceptance_rate: float = 0.0


class IndustrialKnowledgeDiscovery:
    """
    工业知识发现系统
    
    整合以下模块实现闭环治理：
    1. IndustryGovernance - 源头治理
    2. KnowledgeTierManager - 知识分层
    3. IndustryFilter - 行业过滤
    4. RelevanceScorer - 相关性打分
    5. FeedbackLearner - 负反馈学习
    6. IndustryDialectDict - 行业方言词典
    """
    
    def __init__(self):
        # 延迟导入，避免循环依赖
        self.governance = None
        self.tier_manager = None
        self.industry_filter = None
        self.relevance_scorer = None
        self.feedback_learner = None
        self.dialect_dict = None
        
        # 初始化子模块
        self._init_modules()
        
        # 配置参数
        self.target_industry = "机械制造"
        self.min_confidence_threshold = 0.6
        self.max_hallucination_rate = 0.03
        self.enable_uncertainty_prompt = True
        
        # 统计信息
        self.stats = GovernanceStats()
        
        print("[IndustrialKnowledgeDiscovery] 初始化完成")
    
    def _init_modules(self):
        """初始化子模块"""
        from .industry_governance import create_industry_governance
        from .knowledge_tiering import create_knowledge_tier_manager
        from .industry_filter import create_industry_filter
        from .relevance_scorer import create_relevance_scorer
        from .feedback_learner import create_feedback_learner
        from .industry_dialect import create_industry_dialect_dict
        
        self.governance = create_industry_governance()
        self.tier_manager = create_knowledge_tier_manager()
        self.industry_filter = create_industry_filter()
        self.relevance_scorer = create_relevance_scorer()
        self.feedback_learner = create_feedback_learner()
        self.dialect_dict = create_industry_dialect_dict()
    
    def set_target_industry(self, industry: str):
        """设置目标行业"""
        self.target_industry = industry
        self.industry_filter.set_target_industry(industry)
        print(f"[IndustrialKnowledgeDiscovery] 目标行业已设置为: {industry}")
    
    def discover(self, query: str, top_k: int = 10) -> DiscoveryResult:
        """
        执行完整的知识发现流程
        
        Args:
            query: 用户查询
            top_k: 返回文档数量
            
        Returns:
            DiscoveryResult
        """
        # 阶段1：输入控制 - 术语归一化和方言转换
        normalized_query = self._normalize_query(query)
        
        # 阶段2：检索对齐 - 混合检索 + 行业过滤
        retrieved_docs = self._retrieve_documents(normalized_query, top_k)
        
        # 阶段3：输出验证 - 多维度打分和过滤
        validated_docs = self._validate_documents(retrieved_docs)
        
        # 阶段4：生成回答和思维链
        result = self._generate_result(query, normalized_query, validated_docs)
        
        return result
    
    def _normalize_query(self, query: str) -> str:
        """
        阶段1：输入控制 - 术语归一化和方言转换
        
        1. 将方言转换为标准术语
        2. 术语归一化处理
        3. 行业化改写查询
        """
        # 1. 方言转换
        converted_query = self.dialect_dict.expand_query(query, self.target_industry)
        
        # 2. 术语归一化
        normalized_query = self.governance.normalize_query(converted_query, self.target_industry)
        
        # 3. 行业化改写
        enriched_query = self._enrich_with_industry_context(normalized_query)
        
        print(f"[IndustrialKnowledgeDiscovery] 查询转换: {query} -> {enriched_query}")
        return enriched_query
    
    def _enrich_with_industry_context(self, query: str) -> str:
        """为查询添加行业上下文"""
        industry_contexts = {
            "机械制造": "机械设计 加工工艺 设备选型",
            "电子电气": "电路设计 PLC控制 嵌入式系统",
            "化工": "化工工艺 反应工程 安全规范",
            "环评": "环境影响 污染源识别 环保措施",
            "汽车": "汽车设计 动力系统 智能驾驶"
        }
        
        context = industry_contexts.get(self.target_industry, "")
        if context and context not in query:
            return f"{query} {context}"
        
        return query
    
    def _retrieve_documents(self, query: str, top_k: int) -> List[RetrievedDocument]:
        """
        阶段2：检索对齐 - 混合检索 + 行业过滤
        
        1. 关键词检索
        2. 向量检索
        3. 行业过滤器
        4. 行业感知重排序
        """
        # 使用分层检索
        tier_results = self.tier_manager.multi_tier_search(query, top_k_per_tier=top_k)
        
        # 转换为统一格式
        retrieved_docs = []
        for score, doc in tier_results:
            # 获取文档标签
            tag = self.governance.get_document_tag(doc.doc_id)
            
            retrieved_docs.append(RetrievedDocument(
                doc_id=doc.doc_id,
                title=doc.title,
                content=doc.content,
                tier=doc.tier,
                source_type=doc.source_type,
                authority_level=tag.authority_level if tag else 1,
                similarity_score=score,
                tier_score=self.tier_manager.tier_configs[doc.tier].weight,
                final_score=score,
                industry_match=True  # 默认匹配
            ))
        
        # 应用行业过滤器
        filtered_docs = self.industry_filter.filter_documents(
            retrieved_docs, self.target_industry
        )
        
        # 行业感知重排序
        reranked_docs = self._industry_aware_rerank(filtered_docs)
        
        return reranked_docs[:top_k]
    
    def _industry_aware_rerank(self, docs: List[RetrievedDocument]) -> List[RetrievedDocument]:
        """
        行业感知重排序
        
        优先提升包含：
        - 标准号（如GB/T）
        - 型号规格
        - 行业术语的片段
        """
        for doc in docs:
            bonus = 0.0
            
            # 标准号加分
            if "GB/T" in doc.title or "GB/T" in doc.content:
                bonus += 0.2
            if "HJ " in doc.title or "HJ " in doc.content:
                bonus += 0.15
            
            # 型号规格加分
            if re.search(r'[A-Z]+\d+', doc.title):
                bonus += 0.1
            
            # 行业术语加分
            industry_terms = self.governance.synonym_tables.get(self.target_industry, {})
            for term in industry_terms.values():
                if term in doc.content:
                    bonus += 0.05
                    break
            
            doc.final_score = doc.similarity_score * doc.tier_score + bonus
        
        # 排序
        docs.sort(key=lambda x: x.final_score, reverse=True)
        return docs
    
    def _validate_documents(self, docs: List[RetrievedDocument]) -> List[RetrievedDocument]:
        """
        阶段3：输出验证 - 多维度打分和过滤
        
        1. 领域匹配度检查
        2. 时效性检查
        3. 权威性检查
        4. 置信度检查
        5. 低于阈值自动丢弃
        """
        validated = []
        
        for doc in docs:
            # 多维度打分
            scores = self.relevance_scorer.score(
                doc=doc,
                query="",  # 查询已在检索阶段使用
                industry=self.target_industry
            )
            
            # 综合打分
            overall_score = scores.get("final_score", 0.5)
            
            # 低于阈值则丢弃
            if overall_score >= self.min_confidence_threshold:
                doc.final_score = overall_score
                validated.append(doc)
        
        # 统计行业匹配率
        if docs:
            self.stats.industry_match_rate = len(validated) / len(docs)
        
        return validated
    
    def _generate_result(self, original_query: str, normalized_query: str, 
                        docs: List[RetrievedDocument]) -> DiscoveryResult:
        """
        阶段4：生成回答和思维链
        
        1. 综合文档内容
        2. 生成思维链
        3. 添加不确定性提示
        4. 暴露来源
        """
        # 如果没有找到有效文档
        if not docs:
            return DiscoveryResult(
                query=original_query,
                normalized_query=normalized_query,
                documents=[],
                final_answer="未找到相关知识，请尝试其他查询或联系专家。",
                reasoning=[],
                uncertainty=1.0,
                sources=[],
                confidence_score=0.0
            )
        
        # 提取来源
        sources = [f"{doc.title} (层级{L}{doc.tier})" for doc in docs[:5]]
        
        # 计算置信度
        avg_confidence = sum(doc.final_score for doc in docs) / len(docs)
        
        # 生成思维链
        reasoning = self._generate_reasoning(docs)
        
        # 生成最终回答（简化版）
        final_answer = self._synthesize_answer(docs, reasoning)
        
        # 添加不确定性提示
        if self.enable_uncertainty_prompt and avg_confidence < 0.7:
            final_answer += "\n\n⚠️ 提示：该信息通用性较强，建议结合具体工况确认。"
        
        return DiscoveryResult(
            query=original_query,
            normalized_query=normalized_query,
            documents=docs,
            final_answer=final_answer,
            reasoning=reasoning,
            uncertainty=1.0 - avg_confidence,
            sources=sources,
            confidence_score=avg_confidence
        )
    
    def _generate_reasoning(self, docs: List[RetrievedDocument]) -> List[str]:
        """生成思维链"""
        reasoning = []
        
        # 步骤1：分析查询
        reasoning.append("1. 分析用户查询，提取核心需求")
        
        # 步骤2：检索过程
        reasoning.append(f"2. 在{L1核心层}/{L2行业层}/{L3通用层}检索相关知识")
        
        # 步骤3：筛选过程
        reasoning.append("3. 应用行业过滤器筛选相关文档")
        
        # 步骤4：验证过程
        reasoning.append("4. 多维度验证文档相关性和权威性")
        
        # 步骤5：综合过程
        reasoning.append("5. 综合分析得出结论")
        
        return reasoning
    
    def _synthesize_answer(self, docs: List[RetrievedDocument], reasoning: List[str]) -> str:
        """综合文档内容生成回答"""
        # 简单示例：提取前3个文档的关键信息
        content_snippets = []
        
        for i, doc in enumerate(docs[:3], 1):
            # 提取关键片段
            snippet = doc.content[:200].strip()
            content_snippets.append(f"{i}. {snippet}")
        
        answer = "\n\n".join(content_snippets)
        return answer
    
    def record_feedback(self, query: str, doc_id: str, content: str, feedback_type: str):
        """
        记录用户反馈（用于持续进化）
        
        Args:
            query: 用户查询
            doc_id: 文档ID
            content: 文档内容
            feedback_type: irrelevant/relevant/uncertain
        """
        self.feedback_learner.record_feedback(query, doc_id, content, feedback_type)
        
        # 分析反馈并更新系统
        if feedback_type == "irrelevant":
            self._handle_negative_feedback(query, doc_id)
    
    def _handle_negative_feedback(self, query: str, doc_id: str):
        """处理负反馈，优化检索模型"""
        # 分析原因
        analysis = self.feedback_learner.analyze_negative_feedback(query, doc_id)
        
        # 根据分析结果进行优化
        if analysis.get("reason") == "term_ambiguity":
            # 术语歧义：添加同义词
            self._add_synonym_based_on_feedback(query, analysis)
        
        elif analysis.get("reason") == "scene_mismatch":
            # 场景错配：加强行业过滤
            self.industry_filter.strengthen_filter()
        
        elif analysis.get("reason") == "source_inaccuracy":
            # 来源不准：降低该来源权重
            self._adjust_source_weight(doc_id, -0.1)
    
    def _add_synonym_based_on_feedback(self, query: str, analysis: Dict[str, Any]):
        """根据反馈添加同义词"""
        ambiguous_term = analysis.get("term")
        if ambiguous_term:
            # 这里可以自动或人工添加同义词
            print(f"[IndustrialKnowledgeDiscovery] 建议添加同义词: {ambiguous_term}")
    
    def _adjust_source_weight(self, doc_id: str, delta: float):
        """调整文档来源权重"""
        doc = self.tier_manager.get_document(doc_id)
        if doc:
            # 调整该类型文档的权重
            tier = doc.tier
            current_weight = self.tier_manager.tier_configs[tier].weight
            new_weight = max(0.01, min(1.0, current_weight + delta))
            self.tier_manager.update_tier_weight(tier, new_weight)
    
    def add_synonym(self, industry: str, dialect_term: str, standard_term: str):
        """添加行业同义词"""
        self.governance.load_synonym_table(industry, {dialect_term: standard_term})
        self.dialect_dict.add_entry(dialect_term, standard_term, industry)
    
    def add_document(self, doc_id: str, title: str, content: str, source_type: str, 
                    source: str = "unknown") -> bool:
        """
        添加文档到知识库（带准入验证）
        
        Args:
            doc_id: 文档ID
            title: 文档标题
            content: 文档内容
            source_type: 来源类型
            source: 来源描述
            
        Returns:
            是否添加成功
        """
        # 验证文档
        validation = self.governance.validate_document(doc_id, title, content, source)
        
        if validation["passed"]:
            # 添加到分层管理器
            self.tier_manager.add_document(doc_id, content, title, source_type)
            self.stats.total_docs_checked += 1
            self.stats.passed_docs += 1
            return True
        
        self.stats.total_docs_checked += 1
        self.stats.rejected_docs += 1
        return False
    
    def pin_document(self, doc_id: str, title: str, scenarios: List[str], priority: int = 5):
        """
        钉选关键文档（专家知识注入）
        
        Args:
            doc_id: 文档ID
            title: 文档标题
            scenarios: 适用场景列表
            priority: 优先级 (1-5)
        """
        # 提高该文档所在层级的权重
        tier = self.tier_manager.get_tier(doc_id)
        if tier:
            current_weight = self.tier_manager.tier_configs[tier].weight
            boost_factor = 1.0 + (priority - 3) * 0.1
            self.tier_manager.update_tier_weight(tier, current_weight * boost_factor)
        
        print(f"[IndustrialKnowledgeDiscovery] 已钉选文档: {title}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取治理统计信息"""
        governance_stats = self.governance.get_stats()
        tier_stats = self.tier_manager.get_tier_stats()
        
        return {
            "governance": governance_stats,
            "tiering": tier_stats,
            "target_industry": self.target_industry,
            "min_confidence_threshold": self.min_confidence_threshold,
            "hallucination_rate": self.stats.hallucination_rate,
            "user_acceptance_rate": self.stats.user_acceptance_rate
        }
    
    def export_config(self, filepath: str):
        """导出配置到文件"""
        config = {
            "target_industry": self.target_industry,
            "min_confidence_threshold": self.min_confidence_threshold,
            "max_hallucination_rate": self.max_hallucination_rate,
            "enable_uncertainty_prompt": self.enable_uncertainty_prompt,
            "tier_weights": self.tier_manager.get_tier_weights()
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    
    def import_config(self, filepath: str):
        """从文件导入配置"""
        with open(filepath, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        self.target_industry = config.get("target_industry", self.target_industry)
        self.min_confidence_threshold = config.get("min_confidence_threshold", 0.6)
        self.max_hallucination_rate = config.get("max_hallucination_rate", 0.03)
        self.enable_uncertainty_prompt = config.get("enable_uncertainty_prompt", True)
        
        if "tier_weights" in config:
            for tier, weight in config["tier_weights"].items():
                self.tier_manager.update_tier_weight(int(tier), weight)


def create_industrial_knowledge_discovery() -> IndustrialKnowledgeDiscovery:
    """创建工业知识发现系统实例"""
    return IndustrialKnowledgeDiscovery()


# 行业白名单来源
INDUSTRY_SOURCE_WHITELIST = [
    "gb/t", "国标", "国家标准",
    "行标", "行业标准",
    "技术手册", "操作手册",
    "专利", "专利文献",
    "权威论文", "学术论文",
    "内部项目文档", "企业标准", "SOP"
]

# 行业黑名单来源
INDUSTRY_SOURCE_BLACKLIST = [
    "通用百科", "百度百科", "维基百科",
    "新闻", "论坛帖子", "博客", "社交媒体"
]


__all__ = [
    "IndustrialKnowledgeDiscovery",
    "DiscoveryResult",
    "RetrievedDocument",
    "GovernanceStats",
    "create_industrial_knowledge_discovery",
    "INDUSTRY_SOURCE_WHITELIST",
    "INDUSTRY_SOURCE_BLACKLIST"
]