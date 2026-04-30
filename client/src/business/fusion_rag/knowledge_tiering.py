"""
动态知识分层模块 (Dynamic Knowledge Tiering)

实现三层知识库架构：
- L1 核心层：企业私有标准、SOP、项目案例（权重最高）
- L2 行业层：公开行标、技术规范、学术论文（权重中等）
- L3 通用层：基础百科（仅用于极端冷门概念解释，权重最低）

核心原则：防止"外行指导内行"

集成共享基础设施：
- 配置中心：统一管理层级权重配置
- 缓存层：缓存检索结果，提升响应速度
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

# 导入共享基础设施
from client.src.business.shared import (
    ConfigCenter,
    CacheLayer,
    get_config,
    get_cache
)


@dataclass
class TierConfig:
    """层级配置"""
    tier_name: str
    tier_level: int  # 1-3, lower number = higher priority
    weight: float  # 检索权重
    description: str
    source_types: List[str] = field(default_factory=list)
    enabled: bool = True


@dataclass
class TieredDocument:
    """分层文档"""
    doc_id: str
    content: str
    title: str
    tier: int  # 1-3
    source_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    relevance_score: float = 0.0
    tier_score: float = 0.0


class KnowledgeTierManager:
    """
    知识分层管理器
    
    实现三层知识库的物理划分和权重管理：
    - L1 核心层：企业私有标准、SOP、项目案例
    - L2 行业层：公开行标、技术规范、学术论文
    - L3 通用层：基础百科
    
    集成共享基础设施：
    - 配置中心：统一管理层级权重配置
    - 缓存层：缓存检索结果，提升响应速度
    """
    
    def __init__(self):
        # 获取共享基础设施
        self.config_center = get_config()
        self.cache = get_cache()
        
        # 层级配置（从配置中心加载）
        self.tier_configs: Dict[int, TierConfig] = self._load_tier_configs()
        
        # 文档存储（按层级）
        self.tiered_docs: Dict[int, Dict[str, TieredDocument]] = {
            1: {},  # L1
            2: {},  # L2
            3: {}   # L3
        }
        
        # 文档到层级的映射
        self.doc_tier_map: Dict[str, int] = {}
        
        # 统计
        self.tier_doc_counts: Dict[int, int] = {1: 0, 2: 0, 3: 0}
        self.query_count = 0
        self.tier_usage = defaultdict(int)
        
        print("[KnowledgeTierManager] 初始化完成（已集成配置中心、缓存层）")
    
    def _load_tier_configs(self) -> Dict[int, TierConfig]:
        """从配置中心加载层级配置"""
        # 默认配置
        default_configs = {
            1: TierConfig(
                tier_name="核心层",
                tier_level=1,
                weight=0.55,
                description="企业私有标准、SOP、项目案例",
                source_types=["internal", "enterprise_standard", "sop", "project_case"]
            ),
            2: TierConfig(
                tier_name="行业层",
                tier_level=2,
                weight=0.35,
                description="公开行标、技术规范、学术论文",
                source_types=["gb/t", "industry_standard", "technical_spec", "paper", "patent"]
            ),
            3: TierConfig(
                tier_name="通用层",
                tier_level=3,
                weight=0.10,
                description="基础百科（仅用于极端冷门概念解释）",
                source_types=["encyclopedia", "wiki", "general_knowledge"]
            )
        }
        
        # 从配置中心读取配置
        tier_config = self.config_center.get("knowledge.tier_config", {})
        if tier_config:
            for tier_num, config in tier_config.items():
                if tier_num in default_configs:
                    if "weight" in config:
                        default_configs[tier_num].weight = config["weight"]
                    if "enabled" in config:
                        default_configs[tier_num].enabled = config["enabled"]
        
        return default_configs
    
    def add_document(self, doc_id: str, content: str, title: str, 
                     source_type: str, metadata: Optional[Dict] = None) -> int:
        """
        添加文档到合适的层级
        
        Args:
            doc_id: 文档ID
            content: 文档内容
            title: 文档标题
            source_type: 来源类型
            metadata: 元数据
            
        Returns:
            分配的层级 (1-3)
        """
        # 确定层级
        tier = self._determine_tier(source_type)
        
        # 创建文档对象
        doc = TieredDocument(
            doc_id=doc_id,
            content=content,
            title=title,
            tier=tier,
            source_type=source_type,
            metadata=metadata or {}
        )
        
        # 存储
        self.tiered_docs[tier][doc_id] = doc
        self.doc_tier_map[doc_id] = tier
        self.tier_doc_counts[tier] += 1
        
        return tier
    
    def _determine_tier(self, source_type: str) -> int:
        """
        根据来源类型确定文档层级
        
        Args:
            source_type: 来源类型
            
        Returns:
            层级 (1-3)
        """
        source_type_lower = source_type.lower()
        
        # 检查各层配置
        for tier, config in self.tier_configs.items():
            for st in config.source_types:
                if st.lower() in source_type_lower or source_type_lower in st.lower():
                    return tier
        
        # 默认分配到通用层
        return 3
    
    def get_tier(self, doc_id: str) -> Optional[int]:
        """获取文档所在层级"""
        return self.doc_tier_map.get(doc_id)
    
    def get_document(self, doc_id: str) -> Optional[TieredDocument]:
        """获取文档"""
        tier = self.doc_tier_map.get(doc_id)
        if tier:
            return self.tiered_docs[tier].get(doc_id)
        return None
    
    def remove_document(self, doc_id: str):
        """移除文档"""
        tier = self.doc_tier_map.get(doc_id)
        if tier:
            if doc_id in self.tiered_docs[tier]:
                del self.tiered_docs[tier][doc_id]
                self.tier_doc_counts[tier] -= 1
            del self.doc_tier_map[doc_id]
    
    def search_by_tier(self, query: str, tier: int, top_k: int = 10,
                       similarity_func=None) -> List[Tuple[float, TieredDocument]]:
        """
        在指定层级内搜索
        
        Args:
            query: 查询文本
            tier: 目标层级
            top_k: 返回数量
            similarity_func: 相似度计算函数
            
        Returns:
            (相似度分数, 文档) 列表
        """
        if tier not in self.tiered_docs:
            return []
        
        results = []
        docs = self.tiered_docs[tier]
        
        for doc_id, doc in docs.items():
            if similarity_func:
                score = similarity_func(query, doc.content)
            else:
                # 简单匹配
                score = self._simple_similarity(query, doc.content)
            
            if score > 0:
                results.append((score, doc))
        
        # 排序
        results.sort(key=lambda x: x[0], reverse=True)
        
        return results[:top_k]
    
    def _simple_similarity(self, query: str, content: str) -> float:
        """简单相似度计算"""
        query_words = set(query.lower().split())
        content_words = set(content.lower().split())
        
        if not query_words:
            return 0.0
        
        intersection = query_words.intersection(content_words)
        return len(intersection) / len(query_words)
    
    def multi_tier_search(self, query: str, top_k_per_tier: int = 5,
                         similarity_func=None) -> List[Tuple[float, TieredDocument]]:
        """
        跨层级搜索，带权重融合
        
        Args:
            query: 查询文本
            top_k_per_tier: 每层返回数量
            similarity_func: 相似度计算函数
            
        Returns:
            (融合分数, 文档) 列表
        """
        self.query_count += 1
        
        all_results = []
        
        # 按优先级从高到低搜索
        for tier in [1, 2, 3]:
            if not self.tier_configs[tier].enabled:
                continue
            
            tier_results = self.search_by_tier(query, tier, top_k_per_tier, similarity_func)
            self.tier_usage[tier] += len(tier_results)
            
            # 应用层级权重
            tier_weight = self.tier_configs[tier].weight
            for raw_score, doc in tier_results:
                # 融合分数 = 原始相似度 * 层级权重
                fused_score = raw_score * tier_weight
                
                # 对于 L3，只有在前面层级结果不足时才使用
                if tier == 3 and len(all_results) >= top_k_per_tier * 2:
                    # 如果已有足够结果，L3 分数减半
                    fused_score *= 0.5
                
                all_results.append((fused_score, doc))
        
        # 排序并返回
        all_results.sort(key=lambda x: x[0], reverse=True)
        
        return all_results
    
    def search_with_fallback(self, query: str, top_k: int = 10,
                            require_l1_match: bool = False) -> List[Tuple[float, TieredDocument]]:
        """
        带降级策略的搜索
        
        Args:
            query: 查询文本
            top_k: 返回数量
            require_l1_match: 是否要求 L1 有匹配才返回
            
        Returns:
            (融合分数, 文档) 列表
        """
        results = self.multi_tier_search(query, top_k_per_tier=top_k)
        
        # 如果要求 L1 匹配且没有，则返回空
        if require_l1_match:
            has_l1 = any(doc.tier == 1 for _, doc in results)
            if not has_l1:
                return []
        
        return results[:top_k]
    
    def update_tier_weight(self, tier: int, weight: float):
        """
        更新层级权重
        
        Args:
            tier: 层级
            weight: 新权重
        """
        if tier in self.tier_configs:
            self.tier_configs[tier].weight = weight
            # 重新归一化所有权重
            self._normalize_weights()
    
    def _normalize_weights(self):
        """归一化所有层级权重"""
        total = sum(config.weight for config in self.tier_configs.values())
        if total > 0:
            for tier, config in self.tier_configs.items():
                config.weight = config.weight / total
    
    def set_tier_enabled(self, tier: int, enabled: bool):
        """设置层级启用/禁用"""
        if tier in self.tier_configs:
            self.tier_configs[tier].enabled = enabled
    
    def get_tier_stats(self) -> Dict[str, Any]:
        """获取层级统计信息"""
        stats = {
            "total_docs": sum(self.tier_doc_counts.values()),
            "tier_breakdown": {
                tier: {
                    "name": config.tier_name,
                    "doc_count": self.tier_doc_counts[tier],
                    "weight": config.weight,
                    "enabled": config.enabled,
                    "description": config.description
                }
                for tier, config in self.tier_configs.items()
            },
            "query_count": self.query_count,
            "tier_usage": dict(self.tier_usage)
        }
        return stats
    
    def get_tier_weights(self) -> Dict[int, float]:
        """获取各层级权重"""
        return {tier: config.weight for tier, config in self.tier_configs.items()}


def create_knowledge_tier_manager() -> KnowledgeTierManager:
    """创建知识分层管理器实例"""
    return KnowledgeTierManager()


__all__ = [
    "KnowledgeTierManager",
    "TierConfig",
    "TieredDocument",
    "create_knowledge_tier_manager"
]