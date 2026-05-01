"""
类比推理模块 - Analogical Reasoning

功能：
1. 源域和目标域匹配
2. 结构映射
3. 类比迁移
4. 相似性计算
"""

import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AnalogicalMapping:
    """类比映射"""
    source_element: str
    target_element: str
    similarity: float
    relation_type: str  # attribute/relation/function


@dataclass
class AnalogicalResult:
    """类比推理结果"""
    success: bool
    conclusion: Any
    confidence: float = 0.0
    mappings: List[AnalogicalMapping] = None
    reasoning_steps: List[str] = None
    
    def __post_init__(self):
        if self.mappings is None:
            self.mappings = []
        if self.reasoning_steps is None:
            self.reasoning_steps = []


class AnalogicalReasoner:
    """
    类比推理器 - 基于结构映射理论的类比推理
    
    核心思想：
    1. 提取源域和目标域的结构
    2. 建立元素之间的映射
    3. 进行类比迁移
    4. 验证类比有效性
    """
    
    def __init__(self):
        self._analogy_database: List[Dict] = []
        
        # 初始化一些已知类比
        self._init_analogy_database()
    
    def _init_analogy_database(self):
        """初始化类比数据库"""
        self._analogy_database = [
            {
                'source_domain': '太阳系',
                'target_domain': '原子结构',
                'mappings': [
                    {'source': '太阳', 'target': '原子核', 'relation': '中心'},
                    {'source': '行星', 'target': '电子', 'relation': '围绕'},
                    {'source': '引力', 'target': '库仑力', 'relation': '吸引'}
                ]
            },
            {
                'source_domain': '人体',
                'target_domain': '城市',
                'mappings': [
                    {'source': '心脏', 'target': '发电厂', 'relation': '能量供应'},
                    {'source': '血管', 'target': '交通网络', 'relation': '输送'},
                    {'source': '大脑', 'target': '市政府', 'relation': '控制'}
                ]
            },
            {
                'source_domain': '计算机',
                'target_domain': '人脑',
                'mappings': [
                    {'source': 'CPU', 'target': '大脑皮层', 'relation': '处理'},
                    {'source': '内存', 'target': '短期记忆', 'relation': '存储'},
                    {'source': '硬盘', 'target': '长期记忆', 'relation': '存储'}
                ]
            }
        ]
    
    def reason(self, source: str, target: str, query: str = None) -> AnalogicalResult:
        """
        执行类比推理
        
        Args:
            source: 源域描述
            target: 目标域描述
            query: 具体查询（可选）
        
        Returns:
            类比推理结果
        """
        logger.debug(f"类比推理: {source} -> {target}")
        
        steps = [
            "1. 提取源域和目标域",
            "2. 建立结构映射",
            "3. 进行类比迁移"
        ]
        
        # 分析源域和目标域
        source_elements = self._extract_elements(source)
        target_elements = self._extract_elements(target)
        
        # 建立映射
        mappings = self._establish_mappings(source_elements, target_elements)
        
        if mappings:
            # 进行类比迁移
            conclusion = self._analogical_transfer(source, target, mappings, query)
            
            # 计算置信度
            avg_similarity = sum(m.similarity for m in mappings) / len(mappings)
            
            return AnalogicalResult(
                success=True,
                conclusion=conclusion,
                confidence=min(1.0, 0.5 + avg_similarity * 0.5),
                mappings=mappings,
                reasoning_steps=steps
            )
        else:
            return AnalogicalResult(
                success=False,
                conclusion="无法建立有效的类比映射",
                confidence=0.2,
                mappings=[],
                reasoning_steps=steps
            )
    
    def _extract_elements(self, domain: str) -> List[str]:
        """提取域中的元素"""
        # 简化实现：使用关键词提取
        words = domain.lower().replace('、', ',').replace('，', ',').split(',')
        return [w.strip() for w in words if w.strip()]
    
    def _establish_mappings(self, source_elements: List[str], target_elements: List[str]) -> List[AnalogicalMapping]:
        """建立元素之间的映射"""
        mappings = []
        
        # 查找已知类比
        for analogy in self._analogy_database:
            source_domain = analogy['source_domain']
            target_domain = analogy['target_domain']
            
            # 检查是否匹配
            source_match = any(elem in source_domain for elem in source_elements)
            target_match = any(elem in target_domain for elem in target_elements)
            
            if source_match and target_match:
                for mapping in analogy['mappings']:
                    # 检查源元素是否在输入中
                    if any(mapping['source'] in elem for elem in source_elements):
                        mappings.append(AnalogicalMapping(
                            source_element=mapping['source'],
                            target_element=mapping['target'],
                            similarity=0.7,
                            relation_type=mapping['relation']
                        ))
        
        # 如果没有找到已知类比，尝试基于相似性创建映射
        if not mappings and source_elements and target_elements:
            # 简单的长度匹配
            min_len = min(len(source_elements), len(target_elements))
            for i in range(min_len):
                mappings.append(AnalogicalMapping(
                    source_element=source_elements[i],
                    target_element=target_elements[i],
                    similarity=0.5,
                    relation_type='attribute'
                ))
        
        return mappings
    
    def _analogical_transfer(self, source: str, target: str, mappings: List[AnalogicalMapping],
                           query: Optional[str]) -> str:
        """进行类比迁移"""
        if query:
            # 尝试回答具体问题
            for mapping in mappings:
                if mapping.source_element.lower() in query.lower():
                    return f"在 {target} 中，{mapping.source_element} 对应 {mapping.target_element}（{mapping.relation_type}关系）"
        
        # 生成类比描述
        mapping_descriptions = [
            f"{m.source_element} -> {m.target_element}（{m.relation_type}关系）"
            for m in mappings
        ]
        
        return f"通过类比推理找到了相似的解决方案：{'；'.join(mapping_descriptions)}"
    
    def find_analogies(self, domain: str) -> List[Dict]:
        """查找与给定域相关的类比"""
        results = []
        
        for analogy in self._analogy_database:
            if domain.lower() in analogy['source_domain'].lower() or \
               domain.lower() in analogy['target_domain'].lower():
                results.append({
                    'source': analogy['source_domain'],
                    'target': analogy['target_domain'],
                    'mappings': analogy['mappings']
                })
        
        return results
    
    def add_analogy(self, source_domain: str, target_domain: str, mappings: List[Dict]):
        """添加新的类比"""
        self._analogy_database.append({
            'source_domain': source_domain,
            'target_domain': target_domain,
            'mappings': mappings
        })
        logger.info(f"添加类比: {source_domain} -> {target_domain}")
    
    def calculate_similarity(self, domain1: str, domain2: str) -> float:
        """计算两个域之间的相似度"""
        elements1 = set(self._extract_elements(domain1))
        elements2 = set(self._extract_elements(domain2))
        
        if not elements1 or not elements2:
            return 0.0
        
        intersection = elements1.intersection(elements2)
        union = elements1.union(elements2)
        
        return len(intersection) / len(union)