"""
实体管理 - 数据模型定义

定义实体识别与解析所需的数据结构。

作者: LivingTreeAI Team
日期: 2026-04-30
版本: 1.0.0
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional


class EntityType(Enum):
    """实体类型枚举"""
    # 通用类型
    PERSON = "person"           # 人物
    ORGANIZATION = "organization"  # 组织
    LOCATION = "location"       # 地点
    DATE = "date"               # 时间
    NUMBER = "number"           # 数字
    EMAIL = "email"             # 邮箱
    PHONE = "phone"             # 电话
    URL = "url"                 # 网址
    
    # 技术领域
    TECH_TERM = "tech_term"     # 技术术语
    PRODUCT = "product"         # 产品
    CONCEPT = "concept"         # 概念
    ALGORITHM = "algorithm"     # 算法
    FRAMEWORK = "framework"     # 框架
    LANGUAGE = "language"       # 编程语言
    
    # 业务领域
    COMPANY = "company"         # 公司
    EVENT = "event"             # 事件
    DOCUMENT = "document"       # 文档
    PROJECT = "project"         # 项目
    TAG = "tag"                 # 标签
    
    # 未知类型
    UNKNOWN = "unknown"         # 未知


@dataclass
class Entity:
    """实体基本信息"""
    text: str                   # 实体文本
    entity_type: EntityType     # 实体类型
    start: int                  # 在文本中的起始位置
    end: int                    # 在文本中的结束位置
    confidence: float = 0.0     # 识别置信度 (0-1)
    metadata: Dict[str, Any] = field(default_factory=dict)  # 附加信息


@dataclass
class ResolvedEntity:
    """解析后的实体信息"""
    entity: Entity              # 原始实体
    canonical_name: str         # 规范化名称
    entity_id: Optional[str] = None  # 知识库ID
    description: Optional[str] = None  # 描述
    aliases: List[str] = field(default_factory=list)  # 别名列表
    attributes: Dict[str, Any] = field(default_factory=dict)  # 属性
    confidence: float = 0.0     # 解析置信度
    source: Optional[str] = None  # 来源知识库


@dataclass
class EntityRelation:
    """实体关系"""
    subject: str                # 主体实体ID
    predicate: str              # 关系类型
    object: str                 # 客体实体ID
    confidence: float = 0.0     # 关系置信度
    source: Optional[str] = None  # 来源


@dataclass
class KnowledgeBaseEntry:
    """知识库条目"""
    entity_id: str
    name: str
    type: EntityType
    description: str
    aliases: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    relations: List[EntityRelation] = field(default_factory=list)
    source_url: Optional[str] = None
    last_updated: Optional[str] = None


@dataclass
class EntitySearchResult:
    """实体搜索结果"""
    entity: ResolvedEntity
    score: float                # 匹配分数
    match_type: str             # 匹配类型: exact, fuzzy, semantic


@dataclass
class EntityRecognitionResult:
    """实体识别结果"""
    text: str                   # 原始文本
    entities: List[Entity]      # 识别出的实体列表
    entity_count: int           # 实体数量
    processing_time: float      # 处理时间（秒）