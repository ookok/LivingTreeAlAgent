"""
DeepKE-LLM 术语抽取模块

基于 DeepKE-LLM 实现行业术语自动抽取和关系构建
为 IndustryGovernance 提供智能术语识别能力

核心功能：
1. 术语识别与分类
2. 关系抽取（同义词、上下位关系）
3. 术语定义生成
4. 行业词典自动构建
"""

import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime

# 导入共享基础设施
from client.src.business.shared import (
    Term,
    EventBus,
    CacheLayer,
    get_event_bus,
    get_cache,
    EVENTS
)


@dataclass
class ExtractedTerm:
    """抽取的术语信息"""
    term: str
    category: str
    definition: str = ""
    confidence: float = 0.0
    source_text: str = ""
    position: Tuple[int, int] = (0, 0)


@dataclass
class TermRelation:
    """术语关系"""
    term1: str
    relation_type: str  # 同义词、上下位、组成关系等
    term2: str
    confidence: float = 0.0


class DeepKETermExtractor:
    """
    DeepKE-LLM 术语抽取器
    
    提供基于大语言模型的术语抽取能力：
    - 使用 Agent Adapter 进行术语识别
    - 支持多种行业领域
    - 自动构建术语关系
    """
    
    def __init__(self):
        self.event_bus = get_event_bus()
        self.cache = get_cache()
        
        # 术语分类体系
        self.term_categories = {
            "设备": ["电机", "泵", "阀门", "传感器", "控制器"],
            "材料": ["钢材", "塑料", "合金", "复合材料"],
            "工艺": ["加工", "焊接", "热处理", "涂装"],
            "标准": ["国标", "行标", "规范", "标准"],
            "概念": ["理论", "原理", "方法", "技术"]
        }
        
        # 关系类型定义
        self.relation_types = ["同义词", "上位词", "下位词", "组成部分", "属性", "应用场景"]
        
        # 初始化 Agent
        self._init_agent()
        
        print("[DeepKETermExtractor] 初始化完成")
    
    def _init_agent(self):
        """初始化 Agent"""
        try:
            from client.src.business.agent_adapter import create_agent_adapter, AgentConfig
            
            self.agent = create_agent_adapter(AgentConfig(
                agent_type="local",
                model_name="Qwen/Qwen2.5-7B-Instruct",
                max_tokens=4096,
                temperature=0.3  # 较低温度保证稳定性
            ))
            self.use_agent = True
            print("[DeepKETermExtractor] Agent 初始化成功")
        except Exception as e:
            print(f"[DeepKETermExtractor] Agent 初始化失败，使用规则匹配模式: {e}")
            self.use_agent = False
    
    async def extract_terms(self, text: str, industry: str = "通用") -> List[ExtractedTerm]:
        """
        从文本中抽取行业术语
        
        Args:
            text: 输入文本
            industry: 目标行业
            
        Returns:
            抽取的术语列表
        """
        if self.use_agent:
            return await self._extract_with_agent(text, industry)
        else:
            return self._extract_with_rules(text, industry)
    
    async def _extract_with_agent(self, text: str, industry: str) -> List[ExtractedTerm]:
        """使用 Agent 抽取术语"""
        prompt = f"""请从以下文本中抽取{industry}领域的专业术语：

文本：
{text[:2000]}

要求：
1. 识别专业术语及其所属类别
2. 提供术语的简要定义
3. 输出 JSON 格式，包含 terms 数组

输出格式：
{{
  "terms": [
    {{"term": "术语名称", "category": "类别", "definition": "定义", "confidence": 0.9}}
  ]
}}

类别可选值：设备、材料、工艺、标准、概念、其他
"""
        
        try:
            response = await self.agent.async_generate(prompt)
            result = json.loads(response.content)
            
            extracted = []
            for item in result.get("terms", []):
                extracted.append(ExtractedTerm(
                    term=item.get("term", ""),
                    category=item.get("category", "其他"),
                    definition=item.get("definition", ""),
                    confidence=item.get("confidence", 0.0)
                ))
            
            return extracted
        except Exception as e:
            print(f"[DeepKETermExtractor] Agent 抽取失败: {e}")
            return self._extract_with_rules(text, industry)
    
    def _extract_with_rules(self, text: str, industry: str) -> List[ExtractedTerm]:
        """使用规则匹配抽取术语（降级方案）"""
        extracted = []
        
        # 行业关键词匹配
        industry_keywords = {
            "机械制造": ["电机", "PLC", "CNC", "轴承", "齿轮", "液压", "气动", "夹具"],
            "电子电气": ["MCU", "PCB", "传感器", "继电器", "变频器", "伺服", "MOS管"],
            "化工": ["反应器", "精馏塔", "换热器", "泵", "阀门", "催化剂"],
            "汽车": ["ECU", "ESP", "ABS", "动力电池", "充电桩", "ADAS"],
            "能源": ["光伏", "风电", "储能", "逆变器", "智能电网"]
        }
        
        keywords = industry_keywords.get(industry, [])
        keywords.extend(industry_keywords.get("通用", []))
        
        for keyword in keywords:
            if keyword in text:
                extracted.append(ExtractedTerm(
                    term=keyword,
                    category="设备",
                    confidence=0.7
                ))
        
        return extracted
    
    async def extract_relations(self, text: str, industry: str = "通用") -> List[TermRelation]:
        """
        从文本中抽取术语关系
        
        Args:
            text: 输入文本
            industry: 目标行业
            
        Returns:
            抽取的关系列表
        """
        if self.use_agent:
            return await self._extract_relations_with_agent(text, industry)
        else:
            return self._extract_relations_with_rules(text)
    
    async def _extract_relations_with_agent(self, text: str, industry: str) -> List[TermRelation]:
        """使用 Agent 抽取关系"""
        prompt = f"""请分析以下文本中的术语关系：

文本：
{text[:2000]}

要求：
1. 识别术语之间的关系
2. 关系类型：同义词、上位词、下位词、组成部分、属性、应用场景
3. 输出 JSON 格式

输出格式：
{{
  "relations": [
    {{"term1": "术语1", "relation_type": "关系类型", "term2": "术语2", "confidence": 0.9}}
  ]
}}
"""
        
        try:
            response = await self.agent.async_generate(prompt)
            result = json.loads(response.content)
            
            relations = []
            for item in result.get("relations", []):
                if item.get("relation_type") in self.relation_types:
                    relations.append(TermRelation(
                        term1=item.get("term1", ""),
                        relation_type=item.get("relation_type", ""),
                        term2=item.get("term2", ""),
                        confidence=item.get("confidence", 0.0)
                    ))
            
            return relations
        except Exception as e:
            print(f"[DeepKETermExtractor] 关系抽取失败: {e}")
            return []
    
    def _extract_relations_with_rules(self, text: str) -> List[TermRelation]:
        """使用规则抽取关系（降级方案）"""
        relations = []
        
        # 同义词模式匹配
        synonym_patterns = [
            ("又称", "同义词"),
            ("也叫", "同义词"),
            ("简称", "同义词"),
            ("全称是", "同义词"),
            ("即", "同义词"),
            ("也就是", "同义词")
        ]
        
        for pattern, rel_type in synonym_patterns:
            if pattern in text:
                # 简单提取前后术语
                parts = text.split(pattern)
                if len(parts) >= 2:
                    term1 = parts[0].strip().split()[-1] if parts[0].strip() else ""
                    term2 = parts[1].strip().split()[0] if parts[1].strip() else ""
                    if term1 and term2:
                        relations.append(TermRelation(term1, rel_type, term2, 0.8))
        
        return relations
    
    async def build_industry_dict(self, documents: List[str], industry: str) -> Dict[str, Any]:
        """
        从文档集合构建行业词典
        
        Args:
            documents: 文档列表
            industry: 行业名称
            
        Returns:
            行业词典
        """
        all_terms = []
        all_relations = []
        
        # 从每个文档抽取术语
        for doc in documents:
            terms = await self.extract_terms(doc, industry)
            all_terms.extend(terms)
            
            relations = await self.extract_relations(doc, industry)
            all_relations.extend(relations)
        
        # 去重并构建词典
        term_dict = {}
        for term in all_terms:
            if term.term not in term_dict or term.confidence > term_dict[term.term].confidence:
                term_dict[term.term] = term
        
        # 构建关系映射
        relation_map = {}
        for rel in all_relations:
            key = (rel.term1, rel.relation_type)
            if key not in relation_map or rel.confidence > relation_map[key].confidence:
                relation_map[key] = rel
        
        return {
            "industry": industry,
            "terms": {k: v.__dict__ for k, v in term_dict.items()},
            "relations": [r.__dict__ for r in relation_map.values()],
            "created_at": datetime.now().isoformat(),
            "total_terms": len(term_dict),
            "total_relations": len(relation_map)
        }
    
    def generate_term_definition(self, term: str, industry: str) -> str:
        """
        为术语生成定义
        
        Args:
            term: 术语名称
            industry: 行业领域
            
        Returns:
            术语定义
        """
        if not self.use_agent:
            return f"{term} 是 {industry} 领域的专业术语。"
        
        prompt = f"""请为以下{industry}领域术语提供详细定义：

术语：{term}

要求：
1. 术语的基本定义
2. 主要特点
3. 应用场景
4. 相关术语

请用简洁的语言描述。
"""
        
        try:
            response = self.agent.generate(prompt)
            return response.content
        except Exception as e:
            print(f"[DeepKETermExtractor] 定义生成失败: {e}")
            return f"{term} 是 {industry} 领域的专业术语。"


class IndustryDictBuilder:
    """
    行业词典构建器
    
    结合 DeepKE-LLM 和行业治理模块，自动构建行业术语词典
    """
    
    def __init__(self):
        self.extractor = DeepKETermExtractor()
        self.event_bus = get_event_bus()
    
    async def build_and_export(self, documents: List[str], industry: str, 
                               export_path: str = None) -> Dict[str, Any]:
        """
        构建并导出行业词典
        
        Args:
            documents: 文档列表
            industry: 行业名称
            export_path: 导出路径（可选）
            
        Returns:
            行业词典
        """
        print(f"[IndustryDictBuilder] 开始构建 {industry} 行业词典...")
        
        # 构建词典
        dictionary = await self.extractor.build_industry_dict(documents, industry)
        
        # 导出到文件
        if export_path:
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(dictionary, f, ensure_ascii=False, indent=2)
            print(f"[IndustryDictBuilder] 词典已导出到: {export_path}")
        
        # 发布事件
        self.event_bus.publish(EVENTS["DICTIONARY_BUILT"], {
            "industry": industry,
            "total_terms": dictionary["total_terms"],
            "total_relations": dictionary["total_relations"],
            "timestamp": datetime.now().isoformat()
        })
        
        return dictionary
    
    async def update_existing_dict(self, governance, documents: List[str], industry: str):
        """
        更新现有的行业治理术语表
        
        Args:
            governance: IndustryGovernance 实例
            documents: 新文档列表
            industry: 行业名称
        """
        print(f"[IndustryDictBuilder] 更新 {industry} 术语表...")
        
        # 抽取术语和关系
        all_terms = []
        for doc in documents:
            terms = await self.extractor.extract_terms(doc, industry)
            all_terms.extend(terms)
            
            relations = await self.extractor.extract_relations(doc, industry)
            for rel in relations:
                if rel.relation_type == "同义词":
                    governance.add_term(rel.term1, rel.term2, industry)
        
        # 添加新术语
        for term in all_terms:
            if term.confidence > 0.7:
                # 如果没有定义标准术语，使用自身作为标准术语
                governance.add_term(term.term, term.term, industry)
        
        print(f"[IndustryDictBuilder] {industry} 术语表更新完成")


# 创建全局实例
_term_extractor = DeepKETermExtractor()
_dict_builder = IndustryDictBuilder()


def get_term_extractor() -> DeepKETermExtractor:
    """获取术语抽取器实例"""
    return _term_extractor


def get_dict_builder() -> IndustryDictBuilder:
    """获取词典构建器实例"""
    return _dict_builder


__all__ = [
    "ExtractedTerm",
    "TermRelation",
    "DeepKETermExtractor",
    "IndustryDictBuilder",
    "get_term_extractor",
    "get_dict_builder"
]