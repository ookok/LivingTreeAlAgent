"""
类比迁移引擎 - 核心实现

基于CATS Net（概念化网络）思想，实现跨领域知识迁移。
"""
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple

from ..global_model_router import GlobalModelRouter

logger = logging.getLogger(__name__)


class DomainType(Enum):
    """领域类型"""
    ENVIRONMENTAL = "environmental"  # 环保领域
    FINANCIAL = "financial"          # 金融领域
    ENGINEERING = "engineering"      # 工程领域
    HEALTH = "health"                # 健康领域
    MANAGEMENT = "management"        # 管理领域
    GENERAL = "general"              # 通用领域


@dataclass
class DomainConcept:
    """领域概念"""
    concept_id: str
    name: str
    domain: DomainType
    description: Optional[str] = None
    properties: Dict[str, Any] = field(default_factory=dict)
    related_concepts: List[str] = field(default_factory=list)
    weight: float = 1.0  # 概念重要性权重


@dataclass
class AnalogyMapping:
    """类比映射"""
    source_concept: DomainConcept
    target_concept: DomainConcept
    similarity: float  # 相似度 (0-1)
    mapping_type: str  # direct, indirect, inferred
    confidence: float = 0.0


@dataclass
class TransferResult:
    """迁移结果"""
    success: bool
    source_domain: DomainType
    target_domain: DomainType
    mappings: List[AnalogyMapping] = field(default_factory=list)
    transferred_code: Optional[str] = None
    transferred_logic: Optional[str] = None
    confidence: float = 0.0
    suggestions: List[str] = field(default_factory=list)


class AnalogyTransferEngine:
    """
    类比迁移引擎
    
    核心能力：
    1. 从代码/文档中提取概念
    2. 在不同领域间寻找类比关系
    3. 执行零样本迁移
    4. 生成迁移后的代码
    """
    
    def __init__(self):
        self.model_router = GlobalModelRouter.get_instance()
        
        # 预定义的跨领域概念映射
        self.concept_mappings = {
            # 环保 → 金融
            ("排放量", DomainType.ENVIRONMENTAL): ("成本", DomainType.FINANCIAL),
            ("处理效率", DomainType.ENVIRONMENTAL): ("投资回报率", DomainType.FINANCIAL),
            ("排放标准", DomainType.ENVIRONMENTAL): ("预算上限", DomainType.FINANCIAL),
            ("环境影响", DomainType.ENVIRONMENTAL): ("风险评估", DomainType.FINANCIAL),
            
            # 金融 → 环保
            ("NPV", DomainType.FINANCIAL): ("净环境效益", DomainType.ENVIRONMENTAL),
            ("IRR", DomainType.FINANCIAL): ("环境回报率", DomainType.ENVIRONMENTAL),
            ("敏感性分析", DomainType.FINANCIAL): ("敏感性评估", DomainType.ENVIRONMENTAL),
            
            # 通用概念
            ("风险", DomainType.GENERAL): ("风险", DomainType.GENERAL),
            ("概率", DomainType.GENERAL): ("概率", DomainType.GENERAL),
            ("优化", DomainType.GENERAL): ("优化", DomainType.GENERAL),
            ("模型", DomainType.GENERAL): ("模型", DomainType.GENERAL),
        }
        
        # 领域关键词库
        self.domain_keywords = {
            DomainType.ENVIRONMENTAL: ["排放", "污染", "环保", "环评", "环境", "治理", "监测"],
            DomainType.FINANCIAL: ["财务", "投资", "NPV", "IRR", "现金流", "预算"],
            DomainType.ENGINEERING: ["设计", "结构", "材料", "施工", "工程"],
            DomainType.HEALTH: ["健康", "医疗", "卫生", "风险评估", "暴露"],
            DomainType.MANAGEMENT: ["管理", "流程", "组织", "策略", "规划"],
        }
    
    def detect_domain(self, text: str) -> DomainType:
        """
        检测文本所属领域
        
        Args:
            text: 文本内容
        
        Returns:
            DomainType
        """
        scores = {}
        
        for domain, keywords in self.domain_keywords.items():
            score = sum(1 for kw in keywords if kw in text)
            scores[domain] = score
        
        if max(scores.values()) == 0:
            return DomainType.GENERAL
        
        return max(scores, key=scores.get)
    
    def extract_concepts(self, text: str, domain: Optional[DomainType] = None) -> List[DomainConcept]:
        """
        从文本中提取概念
        
        Args:
            text: 文本内容
            domain: 领域类型（可选，自动检测）
        
        Returns:
            DomainConcept列表
        """
        if domain is None:
            domain = self.detect_domain(text)
        
        concepts = []
        
        # 使用LLM提取概念
        concepts.extend(self._extract_concepts_with_llm(text, domain))
        
        # 添加领域通用概念
        concepts.extend(self._get_domain_default_concepts(domain))
        
        return concepts
    
    def _extract_concepts_with_llm(self, text: str, domain: DomainType) -> List[DomainConcept]:
        """使用LLM提取概念"""
        prompt = f"""
分析以下{domain.value}领域的文本，提取核心概念。

文本：{text[:500]}

请以JSON格式输出概念列表，包含：
- concept_id: 概念ID
- name: 概念名称
- description: 概念描述
- properties: 属性字典（可选）

输出格式：
[
    {{"concept_id": "c1", "name": "概念1", "description": "描述", "properties": {{}}}}
]
"""
        
        try:
            response = self.model_router.call_model_sync(
                capability="reasoning",
                prompt=prompt,
                temperature=0.1
            )
            
            data = json.loads(response)
            concepts = []
            
            for item in data:
                concepts.append(DomainConcept(
                    concept_id=item["concept_id"],
                    name=item["name"],
                    domain=domain,
                    description=item.get("description"),
                    properties=item.get("properties", {})
                ))
            
            return concepts
        
        except Exception as e:
            logger.error(f"概念提取失败: {e}")
            return []
    
    def _get_domain_default_concepts(self, domain: DomainType) -> List[DomainConcept]:
        """获取领域默认概念"""
        defaults = {
            DomainType.ENVIRONMENTAL: [
                DomainConcept("env_pollutant", "污染物", domain, "环境中的有害物质"),
                DomainConcept("env_emission", "排放量", domain, "单位时间排放的污染物量"),
                DomainConcept("env_standard", "排放标准", domain, "法定排放限值"),
            ],
            DomainType.FINANCIAL: [
                DomainConcept("fin_cashflow", "现金流", domain, "资金流入流出"),
                DomainConcept("fin_return", "回报率", domain, "投资回报比例"),
                DomainConcept("fin_risk", "风险", domain, "投资风险"),
            ],
        }
        
        return defaults.get(domain, [])
    
    def find_analogies(self, source_domain: DomainType, target_domain: DomainType) -> List[AnalogyMapping]:
        """
        在不同领域间寻找类比关系
        
        Args:
            source_domain: 源领域
            target_domain: 目标领域
        
        Returns:
            类比映射列表
        """
        mappings = []
        
        # 查找预定义映射
        for (source_name, source_dom), (target_name, target_dom) in self.concept_mappings.items():
            if source_dom == source_domain and target_dom == target_domain:
                source_concept = DomainConcept(
                    concept_id=f"src_{source_name}",
                    name=source_name,
                    domain=source_domain
                )
                target_concept = DomainConcept(
                    concept_id=f"tgt_{target_name}",
                    name=target_name,
                    domain=target_domain
                )
                
                mappings.append(AnalogyMapping(
                    source_concept=source_concept,
                    target_concept=target_concept,
                    similarity=0.8,
                    mapping_type="direct",
                    confidence=0.9
                ))
        
        # 通用概念映射
        for (concept_name, dom), (target_name, tgt_dom) in self.concept_mappings.items():
            if dom == DomainType.GENERAL and tgt_dom == target_domain:
                source_concept = DomainConcept(
                    concept_id=f"src_{concept_name}",
                    name=concept_name,
                    domain=source_domain
                )
                target_concept = DomainConcept(
                    concept_id=f"tgt_{target_name}",
                    name=target_name,
                    domain=target_domain
                )
                
                mappings.append(AnalogyMapping(
                    source_concept=source_concept,
                    target_concept=target_concept,
                    similarity=0.9,
                    mapping_type="direct",
                    confidence=0.85
                ))
        
        return mappings
    
    def transfer_logic(
        self,
        source_code: str,
        source_domain: DomainType,
        target_domain: DomainType,
        source_concepts: Optional[List[DomainConcept]] = None,
        target_concepts: Optional[List[DomainConcept]] = None
    ) -> TransferResult:
        """
        将源领域逻辑迁移到目标领域
        
        Args:
            source_code: 源代码
            source_domain: 源领域
            target_domain: 目标领域
            source_concepts: 源领域概念（可选）
            target_concepts: 目标领域概念（可选）
        
        Returns:
            TransferResult
        """
        # 获取类比映射
        mappings = self.find_analogies(source_domain, target_domain)
        
        if not mappings:
            return TransferResult(
                success=False,
                source_domain=source_domain,
                target_domain=target_domain,
                confidence=0.0,
                suggestions=["未找到可用的类比映射"]
            )
        
        # 生成迁移后的代码
        transferred_code = self._generate_transferred_code(source_code, mappings)
        
        # 计算置信度
        avg_similarity = sum(m.similarity for m in mappings) / len(mappings)
        confidence = avg_similarity * 0.8  # 乘以经验系数
        
        # 生成迁移逻辑描述
        logic_description = self._generate_logic_description(mappings)
        
        return TransferResult(
            success=True,
            source_domain=source_domain,
            target_domain=target_domain,
            mappings=mappings,
            transferred_code=transferred_code,
            transferred_logic=logic_description,
            confidence=confidence,
            suggestions=self._generate_suggestions(mappings)
        )
    
    def _generate_transferred_code(self, source_code: str, mappings: List[AnalogyMapping]) -> str:
        """生成迁移后的代码"""
        # 简单的字符串替换实现
        transferred = source_code
        
        for mapping in mappings:
            source_name = mapping.source_concept.name
            target_name = mapping.target_concept.name
            
            # 替换变量名和注释中的概念
            transferred = transferred.replace(source_name, target_name)
            transferred = transferred.replace(source_name.lower(), target_name.lower())
        
        # 添加迁移说明
        header = f"# 自动迁移代码\n# 源概念 → 目标概念映射:\n"
        for mapping in mappings:
            header += f"#   {mapping.source_concept.name} → {mapping.target_concept.name}\n"
        header += "\n"
        
        return header + transferred
    
    def _generate_logic_description(self, mappings: List[AnalogyMapping]) -> str:
        """生成迁移逻辑描述"""
        lines = []
        for mapping in mappings:
            lines.append(f"- {mapping.source_concept.name} → {mapping.target_concept.name}")
        
        return "概念迁移映射:\n" + "\n".join(lines)
    
    def _generate_suggestions(self, mappings: List[AnalogyMapping]) -> List[str]:
        """生成改进建议"""
        suggestions = []
        
        # 检查是否有低相似度映射
        low_confidence = [m for m in mappings if m.similarity < 0.7]
        if low_confidence:
            suggestions.append("部分概念映射相似度较低，建议人工审核")
        
        # 检查是否有通用概念
        general_concepts = [m for m in mappings if m.source_concept.domain == DomainType.GENERAL]
        if not general_concepts:
            suggestions.append("建议添加更多通用概念以提高迁移准确性")
        
        return suggestions
    
    def analyze_transfer_opportunities(self, code: str) -> List[Dict[str, Any]]:
        """
        分析代码的迁移机会
        
        Args:
            code: 代码内容
        
        Returns:
            迁移机会列表
        """
        source_domain = self.detect_domain(code)
        opportunities = []
        
        # 检查所有其他领域
        for domain in DomainType:
            if domain == source_domain:
                continue
            
            mappings = self.find_analogies(source_domain, domain)
            if mappings:
                opportunities.append({
                    "target_domain": domain.value,
                    "domain_name": self._get_domain_name(domain),
                    "mapping_count": len(mappings),
                    "mappings": [{"source": m.source_concept.name, "target": m.target_concept.name} for m in mappings]
                })
        
        return opportunities
    
    def _get_domain_name(self, domain: DomainType) -> str:
        """获取领域中文名称"""
        names = {
            DomainType.ENVIRONMENTAL: "环保领域",
            DomainType.FINANCIAL: "金融领域",
            DomainType.ENGINEERING: "工程领域",
            DomainType.HEALTH: "健康领域",
            DomainType.MANAGEMENT: "管理领域",
            DomainType.GENERAL: "通用领域",
        }
        return names.get(domain, domain.value)


# 单例模式
_analogy_engine = None


def get_analogy_engine() -> AnalogyTransferEngine:
    """获取类比迁移引擎单例"""
    global _analogy_engine
    if _analogy_engine is None:
        _analogy_engine = AnalogyTransferEngine()
    return _analogy_engine