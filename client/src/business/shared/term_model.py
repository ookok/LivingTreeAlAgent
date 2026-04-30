"""
统一术语模型 (Unified Term Model)

消除各模块中重复的术语定义，提供统一的数据结构。
"""

from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional
from datetime import datetime


@dataclass
class Term:
    """
    统一术语模型
    
    替代以下重复定义：
    - TermEntry (auto_term_table_builder.py)
    - TermMapping (document_driven_dictionary.py)
    - DialectEntry (industry_dialect.py)
    """
    
    dialect_term: str           # 内部叫法/方言
    standard_term: str          # 标准术语
    source_file: str            # 出处文件
    confidence: float = 1.0     # 置信度 (0-1)
    term_type: str = "unknown"  # 术语类型：设备、材料、工艺、标准等
    industry: str = "通用"       # 所属行业
    context: str = ""           # 上下文说明
    remark: str = ""            # 备注
    created_at: datetime = None # 创建时间
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        if self.created_at:
            data['created_at'] = self.created_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Term':
        """从字典创建"""
        if 'created_at' in data and data['created_at']:
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        return cls(**data)
    
    def __eq__(self, other):
        if isinstance(other, Term):
            return (self.dialect_term == other.dialect_term and 
                    self.standard_term == other.standard_term)
        return False
    
    def __hash__(self):
        return hash((self.dialect_term, self.standard_term))


@dataclass
class TermConflict:
    """术语冲突"""
    dialect_term: str
    mappings: list  # List[Term]
    resolved: bool = False
    resolution: Optional[Term] = None


@dataclass
class TermStatistics:
    """术语统计"""
    total_terms: int = 0
    by_industry: Dict[str, int] = field(default_factory=dict)
    by_type: Dict[str, int] = field(default_factory=dict)
    avg_confidence: float = 0.0


class TermNormalizer:
    """
    术语归一化器
    
    统一处理术语的大小写、空格等规范化操作。
    """
    
    @staticmethod
    def normalize(text: str) -> str:
        """
        规范化文本
        
        Args:
            text: 原始文本
            
        Returns:
            规范化后的文本
        """
        if not text:
            return ""
        
        # 去除首尾空格
        result = text.strip()
        
        # 统一大小写（工业术语通常使用大写缩写）
        if result.isupper():
            return result
        
        # 保留首字母大写
        return result
    
    @staticmethod
    def is_abbreviation(text: str) -> bool:
        """判断是否为缩写"""
        return text.isupper() and len(text) <= 10
    
    @staticmethod
    def extract_abbreviation(full_term: str) -> str:
        """从全称提取缩写"""
        words = full_term.replace('(', ' ').replace(')', ' ').split()
        return ''.join(word[0].upper() for word in words if word)


__all__ = [
    "Term",
    "TermConflict",
    "TermStatistics",
    "TermNormalizer"
]