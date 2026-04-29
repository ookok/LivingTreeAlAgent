# -*- coding: utf-8 -*-
"""
去中心化知识区块链系统 - 区块链核心

实现知识区块链的数据结构和链式管理
"""

import asyncio
import logging
import json
import os
import hashlib
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict

from .models import (
    Block, BlockHeader, Transaction, KnowledgeUnit,
    KnowledgeMetadata, KnowledgeContent, VerificationInfo, ValueInfo,
    generate_knowledge_id, calculate_merkle_root
)

logger = logging.getLogger(__name__)


class BlockchainState(Enum):
    """区块链状态"""
    INITIALIZING = "initializing"
    SYNCING = "syncing"
    RUNNING = "running"
    PAUSED = "paused"


@dataclass
class ChainStats:
    """链统计"""
    block_count: int = 0
    transaction_count: int = 0
    knowledge_count: int = 0
    total_size: int = 0
    last_block_time: Optional[datetime] = None


class KnowledgeBlockchain:
    """知识区块链"""

    def __init__(
        self,
        node_id: str,
        storage: 'DistributedStorage',
        genesis_knowledge: Optional[List[Dict[str, Any]]] = None
    ):
        """
        初始化区块链
        
        Args:
            node_id: 节点ID
            storage: 分布式存储
            genesis_knowledge: 创世知识
        """
        self.node_id = node_id
        self.storage = storage
        self.genesis_knowledge = genesis_knowledge or []
        
        # 内存中的链
        self.chain: List[Block] = []
        self.pending_transactions: List[Transaction] = []
        self.knowledge_cache: Dict[str, KnowledgeUnit] = {}
        
        # 索引
        self.knowledge_index: Dict[str, str] = {}
        self.tx_index: Dict[str, str] = {}
        self.address_index: Dict[str, List[str]] = defaultdict(list)
        
        # 状态
        self.state = BlockchainState.INITIALIZING
        
        logger.info(f"初始化知识区块链: {node_id}")

    async def initialize(self) -> bool:
        """初始化区块链"""
        try:
            loaded = await self._load_chain()
            
            if not loaded or not self.chain:
                await self._create_genesis_block()
            
            self.state = BlockchainState.RUNNING
            logger.info(f"✅ 区块链初始化完成，共 {len(self.chain)} 个区块")
            return True
            
        except Exception as e:
            logger.error(f"❌ 区块链初始化失败: {e}")
            return False

    async def stop(self):
        """停止区块链"""
        await self._save_chain()
        self.state = BlockchainState.PAUSED
        logger.info("区块链已停止")

    # ==================== 区块操作 ====================

    async def _create_genesis_block(self) -> Block:
        """创建创世区块"""
        logger.info("创建创世区块...")
        
        genesis_txs = []
        for k_data in self.genesis_knowledge:
            tx = Transaction(
                tx_id=self._generate_tx_id(),
                tx_type="knowledge_create",
                sender_id="genesis",
                data=k_data
            )
            genesis_txs.append(tx)
        
        header = BlockHeader(
            version=0,
            previous_block_hash="0" * 64,
            timestamp=datetime(2024, 1, 1, 0, 0, 0),
            difficulty_target=0
        )
        
        genesis_block = Block(
            header=header,
            transactions=genesis_txs,
            consensus_proof="genesis"
        )
        
        self.chain.append(genesis_block)
        
        for tx in genesis_txs:
            await self._process_genesis_tx(tx)
        
        await self._save_block(genesis_block)
        
        logger.info(f"✅ 创世区块创建成功，包含 {len(genesis_txs)} 个初始知识")
        return genesis_block

    async def add_block(self, transactions: List[Transaction]) -> Optional[Block]:
        """添加新区块"""
        if not transactions:
            return None
        
        try:
            previous_block = self.chain[-1]
            
            header = BlockHeader(
                version=len(self.chain),
                previous_block_hash=previous_block.block_hash,
                timestamp=datetime.now(),
                difficulty_target=self._calculate_difficulty()
            )
            
            header.knowledge_merkle_root = calculate_merkle_root(transactions)
            header.state_merkle_root = self._calculate_state_root()
            
            block = Block(
                header=header,
                transactions=transactions,
                consensus_proof=""
            )
            
            if not await self._verify_proof_of_knowledge(block):
                logger.warning("工作证明验证失败")
                return None
            
            self.chain.append(block)
            
            for tx in transactions:
                await self._process_transaction(tx, block.block_hash)
            
            await self._save_block(block)
            await self._save_chain()
            
            logger.info(f"✅ 区块添加成功: #{block.block_number} ({len(transactions)} 个交易)")
            return block
            
        except Exception as e:
            logger.error(f"添加区块失败: {e}")
            return None

    async def _verify_proof_of_knowledge(self, block: Block) -> bool:
        """验证知识证明"""
        difficulty = block.header.difficulty_target
        hash_str = block.block_hash
        leading_zeros = len(hash_str) - len(hash_str.lstrip('0'))
        return leading_zeros >= difficulty

    def _calculate_difficulty(self) -> int:
        """计算难度"""
        if len(self.chain) < 2:
            return 1
        
        last_block = self.chain[-1]
        second_last = self.chain[-2]
        
        time_diff = (last_block.header.timestamp - second_last.header.timestamp).total_seconds()
        
        if time_diff < 30:
            return min(last_block.header.difficulty_target + 1, 6)
        elif time_diff > 120:
            return max(last_block.header.difficulty_target - 1, 1)
        
        return last_block.header.difficulty_target

    def _calculate_state_root(self) -> str:
        """计算状态Merkle根"""
        state_data = {
            "knowledge_count": len(self.knowledge_cache),
            "tx_count": sum(len(b.transactions) for b in self.chain),
            "timestamp": datetime.now().isoformat()
        }
        
        return hashlib.sha256(json.dumps(state_data, sort_keys=True).encode()).hexdigest()

    # ==================== 交易处理 ====================

    async def _process_genesis_tx(self, tx: Transaction):
        """处理创世交易"""
        if tx.tx_type == "knowledge_create":
            knowledge = self._tx_to_knowledge(tx)
            if knowledge:
                self.knowledge_cache[knowledge.knowledge_id] = knowledge
                self.knowledge_index[knowledge.knowledge_id] = "genesis"

    async def _process_transaction(self, tx: Transaction, block_hash: str):
        """处理交易"""
        try:
            if tx.tx_type == "knowledge_create":
                knowledge = self._tx_to_knowledge(tx)
                if knowledge:
                    self.knowledge_cache[knowledge.knowledge_id] = knowledge
                    self.knowledge_index[knowledge.knowledge_id] = block_hash
            
            elif tx.tx_type == "knowledge_verify":
                knowledge_id = tx.data.get("knowledge_id")
                if knowledge_id in self.knowledge_cache:
                    knowledge = self.knowledge_cache[knowledge_id]
                    is_valid = tx.data.get("is_valid", False)
                    
                    knowledge.verification_info.verification_count += 1
                    if is_valid:
                        knowledge.verification_info.pass_count += 1
                    
                    total = knowledge.verification_info.verification_count
                    passed = knowledge.verification_info.pass_count
                    knowledge.verification_info.pass_rate = passed / total if total > 0 else 0
                    
                    knowledge.verification_info.last_verification_time = tx.timestamp
                    knowledge.verification_info.verifier_ids.append(tx.sender_id)
                    if tx.data.get("comments"):
                        knowledge.verification_info.verification_comments.append(tx.data["comments"])
            
            elif tx.tx_type == "knowledge_spread":
                knowledge_id = tx.data.get("knowledge_id")
                if knowledge_id in self.knowledge_cache:
                    self.knowledge_cache[knowledge_id].value_info.spread_count += 1
            
            elif tx.tx_type == "knowledge_learn":
                knowledge_id = tx.data.get("knowledge_id")
                if knowledge_id in self.knowledge_cache:
                    self.knowledge_cache[knowledge_id].value_info.learning_count += 1
                    self.knowledge_cache[knowledge_id].learning_records.append({
                        "learner_id": tx.sender_id,
                        "learned_at": tx.timestamp.isoformat() if tx.timestamp else None
                    })
            
            self.tx_index[tx.tx_id] = block_hash
            self.address_index[tx.sender_id].append(tx.tx_id)
            
        except Exception as e:
            logger.error(f"处理交易失败: {e}")

    def _tx_to_knowledge(self, tx: Transaction) -> Optional[KnowledgeUnit]:
        """交易转知识单元"""
        try:
            data = tx.data
            
            metadata = KnowledgeMetadata(
                knowledge_id=data.get("knowledge_id", tx.tx_id),
                creator_id=tx.sender_id,
                created_at=tx.timestamp,
                updated_at=tx.timestamp,
                knowledge_type=data.get("knowledge_type", "concept"),
                domain_tags=data.get("domain_tags", []),
                language=data.get("language", "zh-CN")
            )
            
            content = KnowledgeContent(
                title=data.get("title", ""),
                summary=data.get("summary", ""),
                content=data.get("content", ""),
                references=data.get("references", []),
                attachments=data.get("attachments", {}),
                keywords=data.get("keywords", [])
            )
            
            return KnowledgeUnit(
                metadata=metadata,
                content=content,
                verification_info=VerificationInfo(),
                value_info=ValueInfo()
            )
            
        except Exception as e:
            logger.error(f"转换交易为知识失败: {e}")
            return None

    # ==================== 查询接口 ====================

    def get_block(self, block_hash: str) -> Optional[Block]:
        """获取区块"""
        for block in self.chain:
            if block.block_hash == block_hash:
                return block
        return None

    def get_block_by_number(self, number: int) -> Optional[Block]:
        """按编号获取区块"""
        if 0 <= number < len(self.chain):
            return self.chain[number]
        return None

    def get_transaction(self, tx_id: str) -> Optional[Tuple[Transaction, Block]]:
        """获取交易"""
        block_hash = self.tx_index.get(tx_id)
        if not block_hash:
            return None
        
        block = self.get_block(block_hash)
        if not block:
            return None
        
        for tx in block.transactions:
            if tx.tx_id == tx_id:
                return tx, block
        
        return None

    def get_knowledge(self, knowledge_id: str) -> Optional[KnowledgeUnit]:
        """获取知识"""
        return self.knowledge_cache.get(knowledge_id)

    def get_chain_length(self) -> int:
        """获取链长度"""
        return len(self.chain)

    def get_stats(self) -> ChainStats:
        """获取链统计"""
        return ChainStats(
            block_count=len(self.chain),
            transaction_count=sum(len(b.transactions) for b in self.chain),
            knowledge_count=len(self.knowledge_cache),
            last_block_time=self.chain[-1].header.timestamp if self.chain else None
        )

    # ==================== 链验证 ====================

    async def verify_chain(self) -> Tuple[bool, str]:
        """验证链完整性"""
        if not self.chain:
            return False, "链为空"
        
        if self.chain[0].header.version != 0:
            return False, "创世区块版本错误"
        
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]
            
            if current.header.previous_block_hash != previous.block_hash:
                return False, f"区块 {i} 链接错误"
            
            if current.block_hash[:current.header.difficulty_target] != "0" * current.header.difficulty_target:
                return False, f"区块 {i} 哈希不符合难度"
        
        return True, "链验证通过"

    # ==================== 存储 ====================

    async def _save_block(self, block: Block):
        """保存区块到存储"""
        try:
            key = f"block_{block.block_hash}"
            await self.storage.put(key, json.dumps(block.to_dict(), ensure_ascii=False))
        except Exception as e:
            logger.error(f"保存区块失败: {e}")

    async def _save_chain(self):
        """保存链索引"""
        try:
            chain_info = {
                "length": len(self.chain),
                "hashes": [b.block_hash for b in self.chain],
                "last_update": datetime.now().isoformat()
            }
            await self.storage.put("chain_index", json.dumps(chain_info))
        except Exception as e:
            logger.error(f"保存链索引失败: {e}")

    async def _load_chain(self) -> bool:
        """加载链"""
        try:
            chain_info_str = await self.storage.get("chain_index")
            if not chain_info_str:
                return False
            
            chain_info = json.loads(chain_info_str)
            
            self.chain = []
            for block_hash in chain_info.get("hashes", []):
                block_data_str = await self.storage.get(f"block_{block_hash}")
                if block_data_str:
                    block_data = json.loads(block_data_str)
                    block = Block(
                        header=BlockHeader(**block_data["header"]),
                        transactions=[Transaction(**tx) for tx in block_data.get("transactions", [])],
                        validator_signatures=block_data.get("validator_signatures", []),
                        consensus_proof=block_data.get("consensus_proof", "")
                    )
                    self.chain.append(block)
                    
                    for tx in block.transactions:
                        self.tx_index[tx.tx_id] = block_hash
                        self.address_index[tx.sender_id].append(tx.tx_id)
                        
                        if tx.tx_type == "knowledge_create":
                            knowledge = self._tx_to_knowledge(tx)
                            if knowledge:
                                self.knowledge_cache[knowledge.knowledge_id] = knowledge
                                self.knowledge_index[knowledge.knowledge_id] = block_hash
            
            return len(self.chain) > 0
            
        except Exception as e:
            logger.error(f"加载链失败: {e}")
            return False

    # ==================== 同步 ====================

    async def sync(self) -> bool:
        """与网络同步"""
        self.state = BlockchainState.SYNCING
        
        try:
            valid_txs = []
            for tx in self.pending_transactions:
                if await self._validate_transaction(tx):
                    valid_txs.append(tx)
            
            self.pending_transactions = valid_txs
            self.state = BlockchainState.RUNNING
            return True
            
        except Exception as e:
            logger.error(f"同步失败: {e}")
            self.state = BlockchainState.RUNNING
            return False

    async def _validate_transaction(self, tx: Transaction) -> bool:
        """验证交易"""
        if not tx.tx_id or not tx.sender_id:
            return False
        
        if tx.signature and not self._verify_signature(tx):
            return False
        
        if tx.tx_id in self.tx_index:
            return False
        
        return True

    def _verify_signature(self, tx: Transaction) -> bool:
        """验证签名"""
        return True

    # ==================== 辅助方法 ====================

    def _generate_tx_id(self) -> str:
        """生成交易ID"""
        import time
        import random
        
        data = f"{self.node_id}{time.time()}{random.randint(0, 10000)}"
        return hashlib.sha256(data.encode()).hexdigest()[:32]

    def get_block_count(self) -> int:
        """获取区块数量"""
        return len(self.chain)

    def get_transaction_count(self) -> int:
        """获取交易数量"""
        return sum(len(b.transactions) for b in self.chain)

    def get_last_block_time(self) -> Optional[datetime]:
        """获取最后区块时间"""
        if self.chain:
            return self.chain[-1].header.timestamp
        return None
