"""
知识区块链单元测试

Author: LivingTreeAI Team
"""

import pytest
import sys
sys.path.insert(0, 'f:/mhzyapp/LivingTreeAlAgent')

from core.knowledge_blockchain import (
    KnowledgeType, KnowledgeStatus, KnowledgeAsset,
    KnowledgeTransaction, ContributionRecord,
    KnowledgeChain, KnowledgeBlock, KnowledgeMarket,
    ContributionTracker, KnowledgeIndexer, KnowledgeWallet
)


class TestKnowledgeAsset:
    """测试知识资产"""
    
    def test_create_asset(self):
        """测试创建知识资产"""
        asset = KnowledgeAsset(
            asset_type=KnowledgeType.CODE_SNIPPET,
            title="快速排序算法",
            content="def quicksort(arr): ...",
            author_id="user_001",
            author_name="Alice",
            tags=["algorithm", "python"],
            price=10.0
        )
        
        assert asset.asset_id is not None
        assert asset.title == "快速排序算法"
        assert asset.asset_type == KnowledgeType.CODE_SNIPPET
        assert asset.content_hash is not None
        assert len(asset.tags) == 2
    
    def test_asset_serialization(self):
        """测试资产序列化"""
        asset = KnowledgeAsset(
            asset_type=KnowledgeType.SOLUTION,
            title="解决内存泄漏",
            content="Solution content",
            author_id="user_001",
            price=5.0
        )
        
        data = asset.to_dict()
        restored = KnowledgeAsset.from_dict(data)
        
        assert restored.asset_id == asset.asset_id
        assert restored.title == asset.title
        assert restored.asset_type == asset.asset_type


class TestKnowledgeChain:
    """测试知识链"""
    
    def test_create_chain(self):
        """测试创建链"""
        chain = KnowledgeChain()
        
        assert len(chain.chain) == 1
        assert chain.chain[0].index == 0
    
    def test_add_block(self):
        """测试添加区块"""
        chain = KnowledgeChain()
        
        block1 = chain.add_block({"type": "test", "data": "test1"})
        assert block1.index == 1
        assert len(chain.chain) == 2
        
        block2 = chain.add_block({"type": "test", "data": "test2"})
        assert block2.index == 2
        assert block2.prev_hash == block1.hash
    
    def test_verify_chain(self):
        """测试链验证"""
        chain = KnowledgeChain()
        
        chain.add_block({"type": "test", "data": "test1"})
        chain.add_block({"type": "test", "data": "test2"})
        
        is_valid, errors = chain.verify_chain()
        assert is_valid
        assert len(errors) == 0


class TestKnowledgeMarket:
    """测试知识市场"""
    
    @pytest.fixture
    def market(self):
        return KnowledgeMarket()
    
    def test_mint_asset(self, market):
        """测试铸造资产"""
        asset = KnowledgeAsset(
            asset_type=KnowledgeType.DESIGN_PATTERN,
            title="单例模式",
            content="class Singleton: ...",
            author_id="user_001",
            author_name="Bob"
        )
        
        asset_id = market.mint_asset(asset)
        
        assert asset_id is not None
        assert asset.status == KnowledgeStatus.PUBLISHED
        
        retrieved = market.get_asset(asset_id)
        assert retrieved is not None
        assert retrieved.title == "单例模式"
    
    def test_purchase_asset(self, market):
        """测试购买资产"""
        # 铸造资产
        asset = KnowledgeAsset(
            asset_type=KnowledgeType.CODE_SNIPPET,
            title="Test Code",
            content="print('hello')",
            author_id="seller_001",
            author_name="Seller",
            price=10.0
        )
        market.mint_asset(asset)
        
        # 设置买家余额
        market.add_balance("buyer_001", 100.0)
        initial_balance = market.get_balance("buyer_001")
        
        # 购买
        tx_id = market.purchase_asset(asset.asset_id, "buyer_001")
        
        assert tx_id is not None
        assert market.get_balance("buyer_001") == initial_balance - 10.0
    
    def test_search_assets(self, market):
        """测试搜索资产"""
        # 创建多个资产
        for i in range(5):
            asset = KnowledgeAsset(
                asset_type=KnowledgeType.CODE_SNIPPET,
                title=f"Algorithm {i}",
                content=f"Algorithm {i} content",
                author_id="user_001",
                tags=["algorithm"] if i < 3 else ["web"]
            )
            market.mint_asset(asset)
        
        # 搜索
        results = market.search_assets("algorithm")
        assert len(results) >= 3
    
    def test_get_popular_assets(self, market):
        """测试获取热门资产"""
        # 创建并购买资产
        for i in range(3):
            asset = KnowledgeAsset(
                asset_type=KnowledgeType.SOLUTION,
                title=f"Solution {i}",
                content=f"Solution {i}",
                author_id="user_001",
                price=5.0
            )
            market.mint_asset(asset)
        
        # 增加引用
        market.assets[asset.asset_id].citation_count = 100
        
        popular = market.get_popular_assets(limit=2)
        assert len(popular) <= 2


class TestContributionTracker:
    """测试贡献追踪器"""
    
    @pytest.fixture
    def tracker(self):
        market = KnowledgeMarket()
        return ContributionTracker(market)
    
    def test_record_contribution(self, tracker):
        """测试记录贡献"""
        record_id = tracker.record_contribution(
            contributor_id="user_001",
            contribution_type="code",
            description="Wrote quicksort",
            weight=2.0
        )
        
        assert record_id is not None
        assert len(tracker.records) == 1
    
    def test_verify_contribution(self, tracker):
        """测试验证贡献"""
        record_id = tracker.record_contribution(
            contributor_id="user_001",
            contribution_type="review",
            description="Reviewed PR #123"
        )
        
        success = tracker.verify_contribution(record_id)
        
        assert success
        record = tracker.records[0]
        assert record.verified is True
    
    def test_get_contribution_score(self, tracker):
        """测试计算贡献分数"""
        # 添加多个贡献
        for i in range(3):
            tracker.record_contribution(
                contributor_id="user_001",
                contribution_type="code",
                description=f"Code {i}",
                weight=1.0
            )
        
        # 验证部分
        tracker.verify_contribution(tracker.records[0].record_id)
        tracker.verify_contribution(tracker.records[1].record_id)
        
        score = tracker.get_contribution_score("user_001")
        assert score > 0
    
    def test_get_ranking(self, tracker):
        """测试排行榜"""
        for i in range(3):
            user_id = f"user_{i}"
            for j in range(i + 1):
                tracker.record_contribution(
                    contributor_id=user_id,
                    contribution_type="code",
                    description=f"Contribution {j}",
                    weight=1.0
                )
        
        rankings = tracker.get_ranking(limit=3)
        
        assert len(rankings) == 3
        # user_2 贡献最多，应该在前面
        assert rankings[0][0] == "user_2"


class TestKnowledgeIndexer:
    """测试知识索引"""
    
    @pytest.fixture
    def indexer(self):
        market = KnowledgeMarket()
        
        # 添加一些测试资产
        assets = [
            KnowledgeAsset(
                asset_type=KnowledgeType.CODE_SNIPPET,
                title="Quick Sort",
                content="quicksort code",
                author_id="user_001",
                tags=["algorithm", "python"]
            ),
            KnowledgeAsset(
                asset_type=KnowledgeType.DESIGN_PATTERN,
                title="Observer Pattern",
                content="observer code",
                author_id="user_002",
                tags=["design", "pattern"]
            ),
            KnowledgeAsset(
                asset_type=KnowledgeType.CODE_SNIPPET,
                title="Merge Sort",
                content="mergesort code",
                author_id="user_001",
                tags=["algorithm", "python"]
            )
        ]
        
        for asset in assets:
            market.mint_asset(asset)
        
        return KnowledgeIndexer(market)
    
    def test_search_by_type(self, indexer):
        """测试按类型搜索"""
        results = indexer.search_by_type(KnowledgeType.CODE_SNIPPET)
        assert len(results) == 2
    
    def test_search_by_tag(self, indexer):
        """测试按标签搜索"""
        results = indexer.search_by_tag("algorithm")
        assert len(results) == 2
    
    def test_search_by_author(self, indexer):
        """测试按作者搜索"""
        results = indexer.search_by_author("user_001")
        assert len(results) == 2
    
    def test_get_related_assets(self, indexer):
        """测试获取相关资产"""
        # 获取第一个算法资产的 ID
        code_assets = indexer.search_by_type(KnowledgeType.CODE_SNIPPET)
        if code_assets:
            related = indexer.get_related_assets(code_assets[0].asset_id, limit=2)
            assert len(related) <= 2


class TestKnowledgeWallet:
    """测试知识钱包"""
    
    @pytest.fixture
    def wallet(self):
        market = KnowledgeMarket()
        tracker = ContributionTracker(market)
        
        # 设置初始余额
        market.add_balance("user_001", 100.0)
        
        return KnowledgeWallet("user_001", market, tracker)
    
    def test_get_balance(self, wallet):
        """测试获取余额"""
        assert wallet.get_balance() == 100.0
    
    def test_publish_knowledge(self, wallet):
        """测试发布知识"""
        asset_id = wallet.publish_knowledge(
            title="My Algorithm",
            content="algorithm code",
            asset_type=KnowledgeType.CODE_SNIPPET,
            tags=["test"],
            price=5.0
        )
        
        assert asset_id is not None
        assert wallet.get_knowledge_balance() == 1
    
    def test_get_wallet_info(self, wallet):
        """测试获取钱包信息"""
        info = wallet.get_wallet_info()
        
        assert info["user_id"] == "user_001"
        assert info["token_balance"] == 100.0
        assert "contribution_score" in info


# 运行测试
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
