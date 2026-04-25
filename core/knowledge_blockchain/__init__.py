"""
知识区块链模块
管理 AI 智能体的知识资产和价值流通

功能：
- 知识资产铸造和存储
- 知识交易和转让
- 贡献度证明 (PoC - Proof of Contribution)
- 知识图谱索引

Author: LivingTreeAI Team
"""

import hashlib
import json
import time
import uuid
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class KnowledgeType(Enum):
    """知识类型"""
    CODE_SNIPPET = "code_snippet"           # 代码片段
    DESIGN_PATTERN = "design_pattern"       # 设计模式
    SOLUTION = "solution"                   # 解决方案
    INSIGHT = "insight"                     # 洞察发现
    DOCUMENTATION = "documentation"        # 文档
    TUTORIAL = "tutorial"                   # 教程


class KnowledgeStatus(Enum):
    """知识状态"""
    DRAFT = "draft"                         # 草稿
    PUBLISHED = "published"                # 已发布
    TRADING = "trading"                    # 交易中
    ARCHIVED = "archived"                  # 已归档
    REJECTED = "rejected"                  # 已拒绝


@dataclass
class KnowledgeAsset:
    """知识资产"""
    asset_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    asset_type: KnowledgeType = KnowledgeType.CODE_SNIPPET
    title: str = ""
    content: str = ""                      # 知识内容
    content_hash: str = ""                 # 内容哈希
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # 来源信息
    author_id: str = ""
    author_name: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    # 价值信息
    price: float = 0.0                     # 定价
    status: KnowledgeStatus = KnowledgeStatus.DRAFT
    
    # 贡献信息
    citation_count: int = 0                # 被引用次数
    like_count: int = 0                   # 点赞数
    quality_score: float = 0.0             # 质量评分 (0-10)
    
    # 标签
    tags: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.content_hash:
            self.content_hash = self._compute_hash()
    
    def _compute_hash(self) -> str:
        """计算内容哈希"""
        content = f"{self.content}:{self.author_id}:{self.created_at}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict:
        return {
            "asset_id": self.asset_id,
            "asset_type": self.asset_type.value,
            "title": self.title,
            "content": self.content,
            "content_hash": self.content_hash,
            "metadata": self.metadata,
            "author_id": self.author_id,
            "author_name": self.author_name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "price": self.price,
            "status": self.status.value,
            "citation_count": self.citation_count,
            "like_count": self.like_count,
            "quality_score": self.quality_score,
            "tags": self.tags
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'KnowledgeAsset':
        return cls(
            asset_id=data["asset_id"],
            asset_type=KnowledgeType(data["asset_type"]),
            title=data["title"],
            content=data["content"],
            content_hash=data.get("content_hash", ""),
            metadata=data.get("metadata", {}),
            author_id=data.get("author_id", ""),
            author_name=data.get("author_name", ""),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            price=data.get("price", 0.0),
            status=KnowledgeStatus(data.get("status", "draft")),
            citation_count=data.get("citation_count", 0),
            like_count=data.get("like_count", 0),
            quality_score=data.get("quality_score", 0.0),
            tags=data.get("tags", [])
        )


@dataclass
class KnowledgeTransaction:
    """知识交易记录"""
    tx_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    asset_id: str = ""
    from_address: str = ""
    to_address: str = ""
    amount: float = 0.0
    timestamp: float = field(default_factory=time.time)
    status: str = "pending"  # pending, completed, failed
    signature: str = ""


@dataclass
class ContributionRecord:
    """贡献记录"""
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    contributor_id: str = ""
    contribution_type: str = ""            # code, review, test, doc
    description: str = ""
    weight: float = 1.0                    # 贡献权重
    timestamp: float = field(default_factory=time.time)
    verified: bool = False
    block_height: int = 0


class KnowledgeBlock:
    """知识区块"""
    def __init__(self, index: int, timestamp: float, data: Any, prev_hash: str = ""):
        self.index = index
        self.timestamp = timestamp
        self.data = data
        self.prev_hash = prev_hash
        self.hash = self._compute_hash()
    
    def _compute_hash(self) -> str:
        """计算区块哈希"""
        block_data = f"{self.index}:{self.timestamp}:{self.data}:{self.prev_hash}"
        return hashlib.sha256(block_data.encode()).hexdigest()
    
    def to_dict(self) -> Dict:
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "data": self.data if isinstance(self.data, dict) else str(self.data),
            "prev_hash": self.prev_hash,
            "hash": self.hash
        }


class KnowledgeChain:
    """
    知识链
    存储和管理所有知识交易记录
    """
    
    def __init__(self):
        self.chain: List[KnowledgeBlock] = []
        self._create_genesis_block()
    
    def _create_genesis_block(self):
        """创建创世区块"""
        genesis = KnowledgeBlock(0, time.time(), {
            "type": "genesis",
            "message": "LivingTreeAI Knowledge Chain Genesis Block"
        })
        self.chain.append(genesis)
    
    def add_block(self, data: Any) -> KnowledgeBlock:
        """添加新区块"""
        prev_block = self.chain[-1]
        new_block = KnowledgeBlock(
            index=len(self.chain),
            timestamp=time.time(),
            data=data,
            prev_hash=prev_block.hash
        )
        self.chain.append(new_block)
        return new_block
    
    def get_block(self, index: int) -> Optional[KnowledgeBlock]:
        """获取区块"""
        if 0 <= index < len(self.chain):
            return self.chain[index]
        return None
    
    def verify_chain(self) -> Tuple[bool, List[str]]:
        """验证链完整性"""
        errors = []
        
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            prev = self.chain[i - 1]
            
            # 验证哈希
            if current.hash != current._compute_hash():
                errors.append(f"Block {i} hash mismatch")
            
            # 验证链接
            if current.prev_hash != prev.hash:
                errors.append(f"Block {i} prev_hash mismatch")
        
        return len(errors) == 0, errors
    
    def get_chain_length(self) -> int:
        """获取链长度"""
        return len(self.chain)


class KnowledgeMarket:
    """
    知识市场
    买卖知识资产
    """
    
    def __init__(self):
        self.assets: Dict[str, KnowledgeAsset] = {}
        self.transactions: List[KnowledgeTransaction] = []
        self.user_balances: Dict[str, float] = {}  # user_id -> balance
        self.chain = KnowledgeChain()
    
    def mint_asset(self, asset: KnowledgeAsset) -> str:
        """铸造知识资产"""
        self.assets[asset.asset_id] = asset
        asset.status = KnowledgeStatus.PUBLISHED
        
        # 记录到链
        self.chain.add_block({
            "type": "mint",
            "asset_id": asset.asset_id,
            "author_id": asset.author_id
        })
        
        logger.info(f"Asset minted: {asset.asset_id}")
        return asset.asset_id
    
    def list_asset(self, asset_id: str, price: float) -> bool:
        """上架资产"""
        if asset_id not in self.assets:
            return False
        
        asset = self.assets[asset_id]
        if asset.author_id != asset.author_id:  # 验证所有权
            return False
        
        asset.price = price
        asset.status = KnowledgeStatus.TRADING
        return True
    
    def purchase_asset(self, asset_id: str, buyer_id: str) -> Optional[str]:
        """购买资产"""
        if asset_id not in self.assets:
            return None
        
        asset = self.assets[asset_id]
        buyer_balance = self.user_balances.get(buyer_id, 0.0)
        
        if buyer_balance < asset.price:
            logger.warning(f"Buyer {buyer_id} has insufficient balance")
            return None
        
        # 执行交易
        seller_id = asset.author_id
        self.user_balances[buyer_id] -= asset.price
        self.user_balances[seller_id] = self.user_balances.get(seller_id, 0.0) + asset.price
        
        # 创建交易记录
        tx = KnowledgeTransaction(
            asset_id=asset_id,
            from_address=seller_id,
            to_address=buyer_id,
            amount=asset.price,
            status="completed"
        )
        self.transactions.append(tx)
        
        # 更新链
        self.chain.add_block({
            "type": "transfer",
            "tx_id": tx.tx_id,
            "asset_id": asset_id,
            "from": seller_id,
            "to": buyer_id,
            "amount": asset.price
        })
        
        # 更新引用计数
        asset.citation_count += 1
        
        logger.info(f"Asset {asset_id} purchased by {buyer_id}")
        return tx.tx_id
    
    def get_asset(self, asset_id: str) -> Optional[KnowledgeAsset]:
        """获取资产"""
        return self.assets.get(asset_id)
    
    def search_assets(self, query: str, limit: int = 20) -> List[KnowledgeAsset]:
        """搜索资产"""
        results = []
        query_lower = query.lower()
        
        for asset in self.assets.values():
            if asset.status != KnowledgeStatus.PUBLISHED:
                continue
            
            # 标题匹配
            if query_lower in asset.title.lower():
                results.append(asset)
                continue
            
            # 标签匹配
            if any(query_lower in tag.lower() for tag in asset.tags):
                results.append(asset)
                continue
        
        return results[:limit]
    
    def get_popular_assets(self, limit: int = 10) -> List[KnowledgeAsset]:
        """获取热门资产"""
        sorted_assets = sorted(
            self.assets.values(),
            key=lambda a: a.citation_count + a.like_count,
            reverse=True
        )
        return sorted_assets[:limit]
    
    def get_user_assets(self, user_id: str) -> List[KnowledgeAsset]:
        """获取用户资产"""
        return [a for a in self.assets.values() if a.author_id == user_id]
    
    def add_balance(self, user_id: str, amount: float):
        """添加余额"""
        self.user_balances[user_id] = self.user_balances.get(user_id, 0.0) + amount
    
    def get_balance(self, user_id: str) -> float:
        """获取余额"""
        return self.user_balances.get(user_id, 0.0)


class ContributionTracker:
    """
    贡献追踪器
    记录和计算用户贡献度
    """
    
    def __init__(self, market: KnowledgeMarket):
        self.market = market
        self.records: List[ContributionRecord] = []
        self.contributions_by_user: Dict[str, List[ContributionRecord]] = {}
    
    def record_contribution(self, contributor_id: str, contribution_type: str,
                          description: str, weight: float = 1.0) -> str:
        """记录贡献"""
        record = ContributionRecord(
            contributor_id=contributor_id,
            contribution_type=contribution_type,
            description=description,
            weight=weight
        )
        
        self.records.append(record)
        
        if contributor_id not in self.contributions_by_user:
            self.contributions_by_user[contributor_id] = []
        self.contributions_by_user[contributor_id].append(record)
        
        # 记录到链
        self.market.chain.add_block({
            "type": "contribution",
            "record_id": record.record_id,
            "contributor_id": contributor_id,
            "contribution_type": contribution_type,
            "weight": weight
        })
        
        logger.info(f"Contribution recorded: {contributor_id} - {contribution_type}")
        return record.record_id
    
    def verify_contribution(self, record_id: str) -> bool:
        """验证贡献"""
        for record in self.records:
            if record.record_id == record_id:
                record.verified = True
                record.block_height = self.market.chain.get_chain_length()
                return True
        return False
    
    def get_contribution_score(self, contributor_id: str) -> float:
        """计算贡献分数"""
        records = self.contributions_by_user.get(contributor_id, [])
        if not records:
            return 0.0
        
        # 加权求和，已验证的贡献权重更高
        total_score = 0.0
        for record in records:
            weight = record.weight * 2 if record.verified else record.weight
            total_score += weight
        
        return min(total_score / 10.0, 10.0)  # 归一化到 0-10
    
    def get_ranking(self, limit: int = 10) -> List[Tuple[str, float]]:
        """获取贡献排行榜"""
        rankings = []
        for user_id in self.contributions_by_user:
            score = self.get_contribution_score(user_id)
            rankings.append((user_id, score))
        
        rankings.sort(key=lambda x: x[1], reverse=True)
        return rankings[:limit]
    
    def get_user_records(self, contributor_id: str) -> List[ContributionRecord]:
        """获取用户贡献记录"""
        return self.contributions_by_user.get(contributor_id, [])


class KnowledgeIndexer:
    """
    知识索引器
    建立和维护知识图谱索引
    """
    
    def __init__(self, market: KnowledgeMarket):
        self.market = market
        self.type_index: Dict[KnowledgeType, List[str]] = {}  # type -> asset_ids
        self.tag_index: Dict[str, List[str]] = {}  # tag -> asset_ids
        self.author_index: Dict[str, List[str]] = {}  # author_id -> asset_ids
        self._build_indices()
    
    def _build_indices(self):
        """构建索引"""
        for asset_id, asset in self.market.assets.items():
            # 类型索引
            if asset.asset_type not in self.type_index:
                self.type_index[asset.asset_type] = []
            self.type_index[asset.asset_type].append(asset_id)
            
            # 标签索引
            for tag in asset.tags:
                if tag not in self.tag_index:
                    self.tag_index[tag] = []
                self.tag_index[tag].append(asset_id)
            
            # 作者索引
            if asset.author_id not in self.author_index:
                self.author_index[asset.author_id] = []
            self.author_index[asset.author_id].append(asset_id)
    
    def rebuild_indices(self):
        """重建索引"""
        self.type_index.clear()
        self.tag_index.clear()
        self.author_index.clear()
        self._build_indices()
    
    def search_by_type(self, asset_type: KnowledgeType) -> List[KnowledgeAsset]:
        """按类型搜索"""
        asset_ids = self.type_index.get(asset_type, [])
        return [self.market.assets[aid] for aid in asset_ids if aid in self.market.assets]
    
    def search_by_tag(self, tag: str) -> List[KnowledgeAsset]:
        """按标签搜索"""
        asset_ids = self.tag_index.get(tag, [])
        return [self.market.assets[aid] for aid in asset_ids if aid in self.market.assets]
    
    def search_by_author(self, author_id: str) -> List[KnowledgeAsset]:
        """按作者搜索"""
        asset_ids = self.author_index.get(author_id, [])
        return [self.market.assets[aid] for aid in asset_ids if aid in self.market.assets]
    
    def get_related_assets(self, asset_id: str, limit: int = 5) -> List[KnowledgeAsset]:
        """获取相关资产"""
        if asset_id not in self.market.assets:
            return []
        
        asset = self.market.assets[asset_id]
        related = []
        
        # 基于标签的相关
        for tag in asset.tags[:3]:  # 只看前3个标签
            related.extend(self.search_by_tag(tag))
        
        # 基于类型的相关
        related.extend(self.search_by_type(asset.asset_type))
        
        # 去重并排除自己
        seen = {asset_id}
        results = []
        for a in related:
            if a.asset_id not in seen:
                seen.add(a.asset_id)
                results.append(a)
                if len(results) >= limit:
                    break
        
        return results


class KnowledgeWallet:
    """
    知识钱包
    管理用户的知识和积分
    """
    
    def __init__(self, user_id: str, market: KnowledgeMarket, 
                 tracker: ContributionTracker):
        self.user_id = user_id
        self.market = market
        self.tracker = tracker
    
    def get_balance(self) -> float:
        """获取积分余额"""
        return self.market.get_balance(self.user_id)
    
    def get_knowledge_balance(self) -> int:
        """获取知识资产数量"""
        return len(self.market.get_user_assets(self.user_id))
    
    def get_contribution_score(self) -> float:
        """获取贡献分数"""
        return self.tracker.get_contribution_score(self.user_id)
    
    def purchase_knowledge(self, asset_id: str) -> bool:
        """购买知识"""
        tx_id = self.market.purchase_asset(asset_id, self.user_id)
        return tx_id is not None
    
    def publish_knowledge(self, title: str, content: str, 
                         asset_type: KnowledgeType,
                         tags: List[str] = None,
                         price: float = 0.0) -> Optional[str]:
        """发布知识"""
        asset = KnowledgeAsset(
            asset_type=asset_type,
            title=title,
            content=content,
            author_id=self.user_id,
            author_name=self.user_id,  # TODO: 获取真实用户名
            tags=tags or [],
            price=price
        )
        
        asset_id = self.market.mint_asset(asset)
        
        # 记录贡献
        self.tracker.record_contribution(
            self.user_id,
            contribution_type="create_knowledge",
            description=f"Created: {title}",
            weight=2.0
        )
        
        return asset_id
    
    def get_wallet_info(self) -> Dict:
        """获取钱包信息"""
        return {
            "user_id": self.user_id,
            "token_balance": self.get_balance(),
            "knowledge_count": self.get_knowledge_balance(),
            "contribution_score": self.get_contribution_score(),
            "assets": [
                a.to_dict() for a in self.market.get_user_assets(self.user_id)
            ]
        }


# 全局实例
_knowledge_market: Optional[KnowledgeMarket] = None
_contribution_tracker: Optional[ContributionTracker] = None
_knowledge_indexer: Optional[KnowledgeIndexer] = None


def get_knowledge_market() -> KnowledgeMarket:
    """获取知识市场全局实例"""
    global _knowledge_market
    if _knowledge_market is None:
        _knowledge_market = KnowledgeMarket()
    return _knowledge_market


def get_contribution_tracker() -> ContributionTracker:
    """获取贡献追踪器全局实例"""
    global _contribution_tracker
    if _contribution_tracker is None:
        _contribution_tracker = ContributionTracker(get_knowledge_market())
    return _contribution_tracker


def get_knowledge_indexer() -> KnowledgeIndexer:
    """获取知识索引器全局实例"""
    global _knowledge_indexer
    if _knowledge_indexer is None:
        _knowledge_indexer = KnowledgeIndexer(get_knowledge_market())
    return _knowledge_indexer


def create_wallet(user_id: str) -> KnowledgeWallet:
    """创建用户钱包"""
    return KnowledgeWallet(user_id, get_knowledge_market(), get_contribution_tracker())


__all__ = [
    'KnowledgeType',
    'KnowledgeStatus',
    'KnowledgeAsset',
    'KnowledgeTransaction',
    'ContributionRecord',
    'KnowledgeBlock',
    'KnowledgeChain',
    'KnowledgeMarket',
    'ContributionTracker',
    'KnowledgeIndexer',
    'KnowledgeWallet',
    'get_knowledge_market',
    'get_contribution_tracker',
    'get_knowledge_indexer',
    'create_wallet'
]
